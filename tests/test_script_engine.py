import tempfile,json
from pathlib import Path
from fastapi.testclient import TestClient

def test_script_versions_scene_isolation_and_generation(monkeypatch):
    from backend.app import main,script_engine
    with tempfile.TemporaryDirectory() as d:
        main.DB=Path(d)/'scripts.sqlite3'
        with TestClient(main.app) as c:
            ch=c.get('/api/v1/channels').json()[0]['id']
            idea=c.post('/api/v1/ideas',json={'channel_id':ch,'title':'Guerra no SMP','description':'Conflito por território'}).json()
            pid=c.post('/api/v1/ideas/'+idea['id']+'/promote').json()['id']
            assert c.get(f'/api/v1/projects/{pid}/scripts').json() is None
            initial={'concept':'Disputa por uma base','promise':'Descobrir quem controla a base','provisional_title':'A disputa pela base','scenes':[{'objective':'Abrir conflito','beat':'hook','duration_seconds':20,'visual':'Ataque à base'},{'objective':'Contexto','beat':'open_loop','duration_seconds':40},{'objective':'Resolver','beat':'payoff','duration_seconds':30}]}
            first=c.post(f'/api/v1/projects/{pid}/scripts',json={'content':initial})
            assert first.status_code==201,first.text
            script=first.json();assert script['revision']==1
            scenes=script['version']['content']['scenes'];unchanged=scenes[1].copy()
            scene={**scenes[0],'narration':'A base está sob ataque'}
            second=c.patch(f'/api/v1/projects/{pid}/scripts/scenes/{scenes[0]["id"]}',json={'expected_revision':1,'scene':scene})
            assert second.status_code==200,second.text
            assert second.json()['version']['content']['scenes'][1]==unchanged
            assert c.patch(f'/api/v1/projects/{pid}/scripts/scenes/{scenes[0]["id"]}',json={'expected_revision':1,'scene':scene}).status_code==409
            analysis=c.get(f'/api/v1/projects/{pid}/scripts/analyze').json()
            assert analysis['estimated_duration_seconds']==90 and analysis['scene_count']==3
            assert 'OPEN_LOOP_WITHOUT_PAYOFF' not in analysis['alerts']
            versions=c.get(f'/api/v1/projects/{pid}/scripts/versions').json();assert len(versions)==2
            restored=c.post(f'/api/v1/projects/{pid}/scripts/versions/{versions[-1]["id"]}/restore',params={'expected_revision':2}).json()
            assert restored['revision']==3 and restored['version']['content']['scenes'][0]['narration']==''
            assert len(c.get(f'/api/v1/projects/{pid}/scripts/versions').json())==3
            generated=json.dumps({'concept':'Novo conflito','promise':'Resolver disputa','provisional_title':'A batalha','scenes':[{'objective':'Início','beat':'hook'},{'objective':'Risco','beat':'stakes'},{'objective':'Desfecho','beat':'payoff'}]})
            monkeypatch.setattr(script_engine.OllamaProvider,'generate',lambda *args: generated)
            ai=c.post(f'/api/v1/projects/{pid}/scripts/generate',json={'model':'fixture','expected_revision':3})
            assert ai.status_code==201,ai.text
            assert ai.json()['revision']==4 and ai.json()['version']['state']=='DRAFT'
            assert json.loads(ai.json()['version']['source_json'])['style_dna']=='UNAVAILABLE'
            monkeypatch.setattr(script_engine.OllamaProvider,'generate',lambda *args: (_ for _ in ()).throw(OSError('offline')))
            assert c.post(f'/api/v1/projects/{pid}/scripts/generate',json={'model':'local','expected_revision':4}).status_code==503
        with TestClient(main.app) as c:
            assert c.get(f'/api/v1/projects/{pid}/scripts').json()['revision']==4
