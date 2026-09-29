import os,tempfile
from pathlib import Path
from fastapi.testclient import TestClient

def test_persistent_flow():
    with tempfile.TemporaryDirectory() as d:
        os.environ['MANOGUS_DB']=str(Path(d)/'test.db')
        from backend.app import main
        main.DB=Path(os.environ['MANOGUS_DB'])
        with TestClient(main.app) as client:
            channels=client.get('/api/v1/channels').json()
            assert len(channels)==2
            ch=channels[0]['id']
            idea=client.post('/api/v1/ideas',json={'channel_id':ch,'title':'Teste de fluxo'}).json()
            p=client.post(f"/api/v1/ideas/{idea['id']}/promote").json()
            client.post(f"/api/v1/projects/{p['id']}/references",json={'title':'Vídeo A','url':'https://youtube.com/watch?v=example'}).raise_for_status()
            t=client.post(f"/api/v1/projects/{p['id']}/tasks",json={'title':'Gravar abertura'}).json()
            client.patch(f"/api/v1/tasks/{t['id']}",json={'title':'Gravar abertura','done':True}).raise_for_status()
            updated=client.patch(f"/api/v1/projects/{p['id']}",json={'title':'Novo título','notes':'Salvo','state':'production','revision':1}).json()
            assert updated['revision']==2
            assert client.patch(f"/api/v1/projects/{p['id']}",json={'title':'Conflito','revision':1}).status_code==409
        with TestClient(main.app) as client:
            reopened=client.get(f"/api/v1/projects/{p['id']}").json()
            assert reopened['title']=='Novo título' and reopened['notes']=='Salvo'
            assert reopened['references'][0]['title']=='Vídeo A'
            assert reopened['tasks'][0]['done']==1
            assert client.get('/api/v1/ideas',params={'channel_id':channels[1]['id']}).json()==[]
            assert client.post('/api/v1/backups').status_code==201
