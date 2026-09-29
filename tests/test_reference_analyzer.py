import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

def test_reference_analysis_versions_and_boundaries(monkeypatch):
    from backend.app import main,reference_analyzer
    with tempfile.TemporaryDirectory() as d:
        main.DB=Path(d)/'reference.sqlite3'
        with TestClient(main.app) as c:
            channel=c.get('/api/v1/channels').json()[0]['id']
            idea=c.post('/api/v1/ideas',json={'channel_id':channel,'title':'Minecraft mistério'}).json()
            project=c.post('/api/v1/ideas/'+idea['id']+'/promote').json()
            ref=c.post('/api/v1/projects/'+project['id']+'/references',json={'title':'Referência A','url':'https://www.youtube.com/watch?v=example'}).json();rid=ref['id']
            base={'title_mechanism':'Promessa de descoberta concreta','narrative':[]}
            a=c.post('/api/v1/references/'+rid+'/analyze',json=base)
            assert a.status_code==201,a.text
            assert 'NARRATIVE_UNAVAILABLE_WITH_METADATA_ONLY' in a.json()['limitations']
            bad={**base,'narrative':[{'type':'hook','mechanism':'Abre pergunta','evidence':'0:10','confidence':.8,'origin':'OBSERVED'}]}
            assert c.post('/api/v1/references/'+rid+'/analyze',json=bad).status_code==422
            t=c.post('/api/v1/references/'+rid+'/transcripts',json={'content':'Texto autorizado com abertura, conflito e consequência observáveis.','origin':'USER_PROVIDED','rights_note':'Fornecido com autorização para análise','language':'pt'})
            assert t.status_code==201,t.text
            assert c.post('/api/v1/references/'+rid+'/transcripts',json={'content':'Texto autorizado com abertura, conflito e consequência observáveis.','origin':'USER_PROVIDED','rights_note':'Fornecido com autorização para análise','language':'pt'}).json()['duplicate']
            a2=c.post('/api/v1/references/'+rid+'/analyze',json=bad)
            assert a2.status_code==201 and a2.json()['version']==2
            records=c.get('/api/v1/references/'+rid+'/analyses').json()
            assert records[0]['stale'] is False and records[1]['stale'] is True
            assert records[0]['narrative'][0]['origin']=='OBSERVED'
            assert 'content' not in c.get('/api/v1/references/'+rid+'/transcripts').text
            assert c.post('/api/v1/references/nonexistent/analyze',json=base).status_code==404
            monkeypatch.setattr(reference_analyzer.OllamaProvider,'generate',lambda *args: (_ for _ in ()).throw(OSError('offline')))
            assert c.post('/api/v1/references/'+rid+'/analyze-with-ollama',json={'model':'test'}).status_code==503
        with TestClient(main.app) as c:
            assert len(c.get('/api/v1/references/'+rid+'/analyses').json())==2
