import os, sqlite3, uuid, json, logging, shutil
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from urllib.request import Request, urlopen
from urllib.error import URLError
from fastapi import FastAPI, HTTPException, Request as WebRequest
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.getenv('MANOGUS_DB', ROOT / 'database' / 'manogus.sqlite3'))
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('manogus')
app = FastAPI(title='MANOGUS CONTENT OS', version='0.1.0')

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
@contextmanager
def conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA journal_mode=WAL')
    try:
        yield c
        c.commit()
    except:
        c.rollback(); raise
    finally: c.close()

def migrate():
    sql = (ROOT / 'database/migrations/versions/001_foundation.sql').read_text()
    with conn() as c:
        c.executescript(sql)
        for handle, focus in [('MANOGUS','Minecraft Anarchy'),('MANOGUSSS','Minecraft SMP')]:
            c.execute('INSERT OR IGNORE INTO channels(id,handle,focus,created_at,updated_at) VALUES(?,?,?,?,?)',(uid(),handle,focus,now(),now()))

@app.on_event('startup')
def startup():
    migrate()
    research.migrate()
    trends.migrate()
    reference_analyzer.migrate()
    script_engine.migrate()

@app.exception_handler(HTTPException)
async def problem(request: WebRequest, exc: HTTPException):
    return JSONResponse({'code':str(exc.status_code),'message':exc.detail,'request_id':request.headers.get('x-request-id',uid())},status_code=exc.status_code,media_type='application/problem+json')

def row(c, table, id):
    x=c.execute(f'SELECT * FROM "{table}" WHERE id=?',(id,)).fetchone()
    if not x: raise HTTPException(404,f'{table}: registro não encontrado')
    return dict(x)
def audit(c, action, entity, id, before=None, after=None):
    c.execute('INSERT INTO audit_events(id,action,entity,entity_id,before_json,after_json,created_at) VALUES(?,?,?,?,?,?,?)',(uid(),action,entity,id,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),now()))

class IdeaIn(BaseModel):
    channel_id: str
    title: str = Field(min_length=1,max_length=200)
    description: str = ''
    lifecycle_state: str = 'inbox'
class NewProject(BaseModel):
    channel_id: str
    title: str = Field(min_length=1,max_length=200)
    notes: str = ""

class ProjectPatch(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    notes: str = ''
    state: str = 'planning'
    revision: int
class RefIn(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    url: str = ''
    notes: str = ''
class TaskIn(BaseModel):
    title: str = Field(min_length=1,max_length=200)
class TaskPatch(BaseModel):
    title: str = Field(min_length=1,max_length=200)
    done: bool
class SettingIn(BaseModel):
    value: str

@app.get('/api/v1/health')
def health(): return {'status':'ok'}
@app.get('/api/v1/channels')
def channels():
    with conn() as c:return [dict(x) for x in c.execute('SELECT * FROM channels ORDER BY handle')]
@app.get('/api/v1/dashboard')
def dashboard(channel_id:str):
    with conn() as c:
        row(c,'channels',channel_id)
        return {k:c.execute(f'SELECT COUNT(*) FROM {table} WHERE channel_id=?',(channel_id,)).fetchone()[0] for k,table in [('ideas','ideas'),('projects','projects'),('references','references')]}
@app.get('/api/v1/ideas')
def ideas(channel_id:str):
    with conn() as c:return [dict(x) for x in c.execute('SELECT * FROM ideas WHERE channel_id=? ORDER BY created_at DESC',(channel_id,))]
@app.post('/api/v1/ideas',status_code=201)
def create_idea(data:IdeaIn):
    with conn() as c:
        row(c,'channels',data.channel_id)
        id=uid();c.execute('INSERT INTO ideas(id,channel_id,title,description,lifecycle_state,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(id,data.channel_id,data.title,data.description,data.lifecycle_state,now(),now()))
        result=row(c,'ideas',id);audit(c,'create','idea',id,after=result);return result
@app.post('/api/v1/ideas/{id}/promote',status_code=201)
def promote(id:str):
    with conn() as c:
        idea=row(c,'ideas',id)
        existing=c.execute('SELECT * FROM projects WHERE idea_id=?',(id,)).fetchone()
        if existing:return dict(existing)
        pid=uid();c.execute('INSERT INTO projects(id,channel_id,idea_id,title,notes,state,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(pid,idea['channel_id'],id,idea['title'],idea['description'],'planning',1,now(),now()))
        c.execute("UPDATE ideas SET lifecycle_state='developing',updated_at=? WHERE id=?",(now(),id))
        result=row(c,'projects',pid);audit(c,'promote','project',pid,after=result);return result
@app.post('/api/v1/projects',status_code=201)
def create_project(data:NewProject):
    with conn() as c:
        row(c,'channels',data.channel_id)
        idea_id=uid();project_id=uid();stamp=now()
        c.execute('INSERT INTO ideas(id,channel_id,title,description,lifecycle_state,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',(idea_id,data.channel_id,data.title,data.notes,'developing',stamp,stamp))
        c.execute('INSERT INTO projects(id,channel_id,idea_id,title,notes,state,revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',(project_id,data.channel_id,idea_id,data.title,data.notes,'planning',1,stamp,stamp))
        result=row(c,'projects',project_id)
        audit(c,'create','project',project_id,after=result)
        return result
@app.get('/api/v1/projects')
def projects(channel_id:str):
    with conn() as c:return [dict(x) for x in c.execute('SELECT * FROM projects WHERE channel_id=? ORDER BY created_at DESC',(channel_id,))]
@app.get('/api/v1/projects/{id}')
def project(id:str):
    with conn() as c:
        result=row(c,'projects',id)
        result['references']=[dict(x) for x in c.execute('SELECT * FROM "references" WHERE project_id=? ORDER BY created_at',(id,))]
        result['tasks']=[dict(x) for x in c.execute('SELECT * FROM tasks WHERE project_id=? ORDER BY created_at',(id,))]
        return result
@app.patch('/api/v1/projects/{id}')
def edit_project(id:str,data:ProjectPatch):
    with conn() as c:
        old=row(c,'projects',id)
        if old['revision'] != data.revision:raise HTTPException(409,'Projeto alterado em outra sessão. Recarregue antes de salvar.')
        c.execute('INSERT INTO project_versions(id,project_id,revision,snapshot_json,created_at) VALUES(?,?,?,?,?)',(uid(),id,old['revision'],json.dumps(old,ensure_ascii=False),now()))
        c.execute('UPDATE projects SET title=?,notes=?,state=?,revision=revision+1,updated_at=? WHERE id=?',(data.title,data.notes,data.state,now(),id))
        result=row(c,'projects',id);audit(c,'update','project',id,old,result);return result
@app.get('/api/v1/projects/{id}/versions')
def versions(id:str):
    with conn() as c:
        row(c,'projects',id);return [dict(x) for x in c.execute('SELECT * FROM project_versions WHERE project_id=? ORDER BY revision DESC',(id,))]
@app.post('/api/v1/projects/{id}/references',status_code=201)
def add_ref(id:str,data:RefIn):
    with conn() as c:
        p=row(c,'projects',id);rid=uid()
        if c.execute('SELECT COUNT(*) FROM "references" WHERE project_id=?',(id,)).fetchone()[0]>=3:raise HTTPException(422,'Máximo de três referências principais por projeto')
        c.execute('INSERT INTO "references"(id,channel_id,project_id,title,url,notes,created_at) VALUES(?,?,?,?,?,?,?)',(rid,p['channel_id'],id,data.title,data.url,data.notes,now()))
        result=row(c,'references',rid);audit(c,'create','reference',rid,after=result);return result
@app.post('/api/v1/projects/{id}/tasks',status_code=201)
def add_task(id:str,data:TaskIn):
    with conn() as c:
        row(c,'projects',id);tid=uid()
        c.execute('INSERT INTO tasks(id,project_id,title,done,created_at,updated_at) VALUES(?,?,?,?,?,?)',(tid,id,data.title,0,now(),now()))
        result=row(c,'tasks',tid);audit(c,'create','task',tid,after=result);return result
@app.patch('/api/v1/tasks/{id}')
def edit_task(id:str,data:TaskPatch):
    with conn() as c:
        old=row(c,'tasks',id);c.execute('UPDATE tasks SET title=?,done=?,updated_at=? WHERE id=?',(data.title,int(data.done),now(),id))
        result=row(c,'tasks',id);audit(c,'update','task',id,old,result);return result
@app.get('/api/v1/settings')
def settings():
    with conn() as c:return {x['key']:x['value'] for x in c.execute('SELECT * FROM settings')}
@app.put('/api/v1/settings/{key}')
def put_setting(key:str,data:SettingIn):
    if key not in ('ollama_model','timezone'):raise HTTPException(422,'Configuração não permitida')
    with conn() as c:
        c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,data.value));audit(c,'update','setting',key);return {'key':key,'value':data.value}
class AIProvider:
    def generate(self,prompt:str,model:str)->str:raise NotImplementedError
class OllamaProvider(AIProvider):
    def generate(self,prompt:str,model:str)->str:
        req=Request('http://127.0.0.1:11434/api/generate',data=json.dumps({'model':model,'prompt':prompt,'stream':False}).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=60) as response:return json.load(response)['response']
@app.get('/api/v1/capabilities')
def capabilities():
    try:
        with urlopen('http://127.0.0.1:11434/api/tags',timeout=1) as response:ollama=response.status==200
    except (URLError,TimeoutError):ollama=False
    return {'foundation':'IMPLEMENTED','ollama':'IMPLEMENTED' if ollama else 'BLOCKED_EXTERNAL_CONFIG','research':'UNAVAILABLE','analytics':'BLOCKED_EXTERNAL_CONFIG'}
@app.get('/api/v1/audit')
def audits(limit:int=50):
    with conn() as c:return [dict(x) for x in c.execute('SELECT id,action,entity,entity_id,created_at FROM audit_events ORDER BY created_at DESC LIMIT ?',(min(limit,100),))]
@app.post('/api/v1/backups',status_code=201)
def backup():
    directory=ROOT/'database/backups';directory.mkdir(parents=True,exist_ok=True)
    name=f"manogus-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uid()[:8]}.sqlite3"
    target=directory/name
    with conn() as c:
        dest=sqlite3.connect(target)
        try:c.backup(dest)
        finally:dest.close()
        bid=uid();c.execute('INSERT INTO backups(id,filename,created_at) VALUES(?,?,?)',(bid,name,now()));audit(c,'create','backup',bid)
    return {'id':bid,'filename':name}
@app.get('/api/v1/backups')
def backups():
    with conn() as c:return [dict(x) for x in c.execute('SELECT * FROM backups ORDER BY created_at DESC')]

from . import research
app.include_router(research.router)

from . import trends
app.include_router(trends.router)

from . import reference_analyzer
app.include_router(reference_analyzer.router)

from . import script_engine
app.include_router(script_engine.router)
