import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

def test_full_daily_flow_persists_after_reopen():
    from backend.app import main
    with tempfile.TemporaryDirectory() as d:
        main.DB=Path(d)/'daily.sqlite3'
        with TestClient(main.app) as c:
            channel=next(x for x in c.get('/api/v1/channels').json() if x['handle']=='MANOGUS')
            idea=c.post('/api/v1/ideas',json={'channel_id':channel['id'],'title':'Servidor perigoso','description':'Experimento Anarchy'}).json()
            project=c.post('/api/v1/ideas/'+idea['id']+'/promote').json();pid=project['id']
            ids=[]
            for i in range(3):
                r=c.post(f'/api/v1/projects/{pid}/references',json={'title':f'Referência {i+1}','url':f'https://www.youtube.com/watch?v=ref{i}'});assert r.status_code==201,r.text;ids.append(r.json()['id'])
            assert c.post(f'/api/v1/projects/{pid}/references',json={'title':'Quarta'}).status_code==422
            script=c.post(f'/api/v1/projects/{pid}/scripts',json={'content':{'concept':'Infiltração','promise':'Descobrir o perigo','provisional_title':'Entrei no servidor','scenes':[{'objective':'Gancho','beat':'hook','visual':'Mapa do servidor'},{'objective':'Desfecho','beat':'payoff','gameplay':'Escapar'}]}})
            assert script.status_code==201,script.text
            task=c.post(f'/api/v1/projects/{pid}/tasks',json={'title':'Gravar o gancho'}).json()
            c.patch('/api/v1/tasks/'+task['id'],json={'title':'Gravar o gancho','done':True}).raise_for_status()
            c.patch('/api/v1/projects/'+pid,json={'title':'Servidor perigoso','notes':'Gravar sábado','state':'production','revision':1}).raise_for_status()
        with TestClient(main.app) as c:
            p=c.get('/api/v1/projects/'+pid).json()
            assert p['notes']=='Gravar sábado' and p['revision']==2
            assert len(p['references'])==3 and {r['id'] for r in p['references']}==set(ids)
            assert len(p['tasks'])==1 and p['tasks'][0]['done']==1
            assert c.get(f'/api/v1/projects/{pid}/scripts').json()['version']['content']['scenes'][1]['objective']=='Desfecho'
            other=next(x for x in c.get('/api/v1/channels').json() if x['handle']=='MANOGUSSS')
            assert c.get('/api/v1/projects',params={'channel_id':other['id']}).json()==[]

def test_direct_project_creation():
    from backend.app import main
    with tempfile.TemporaryDirectory() as d:
        main.DB=Path(d)/'direct.sqlite3'
        with TestClient(main.app) as c:
            ch=c.get('/api/v1/channels').json()[0]['id']
            p=c.post('/api/v1/projects',json={'channel_id':ch,'title':'Projeto direto'}).json()
            assert p['idea_id'] and c.get('/api/v1/projects/'+p['id']).json()['title']=='Projeto direto'
            assert len(c.get('/api/v1/ideas',params={'channel_id':ch}).json())==1
