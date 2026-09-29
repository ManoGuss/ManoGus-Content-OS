import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

def test_trends_import_and_reopen():
    from backend.app import main
    with tempfile.TemporaryDirectory() as d:
        main.DB=Path(d)/'trends.sqlite3'
        payload={'term':'Minecraft SMP','region':'US','timeframe':'past 90 days','source_ref':'https://trends.google.com/trends/explore?q=Minecraft%20SMP','normalization_group':'export-2026-09-29-US','csv_text':'Category: All categories\n\nWeek,Minecraft SMP: (United States)\n2026-08-01 - 2026-08-07,50\n2026-08-08 - 2026-08-14,<1\n2026-08-15 - 2026-08-21,100\n'}
        with TestClient(main.app) as c:
            first=c.post('/api/v1/trends/import',json=payload)
            assert first.status_code==201,first.text
            id=first.json()['id'];assert first.json()['point_count']==3
            assert c.post('/api/v1/trends/import',json=payload).json()['duplicate'] is True
            assert c.get('/api/v1/trends/series',params={'term':'Minecraft SMP'}).json()[0]['id']==id
            assert c.get('/api/v1/trends/series/'+id).json()['points'][1]['interest_index'] is None
            bad={**payload,'csv_text':payload['csv_text'].replace('100','120')}
            assert c.post('/api/v1/trends/import',json=bad).status_code==422
            multi={**payload,'csv_text':'Week,Minecraft SMP,Minecraft Anarchy\n2026-08-01,50,30'}
            assert c.post('/api/v1/trends/import',json=multi).status_code==422
        with TestClient(main.app) as c:
            assert len(c.get('/api/v1/trends/series/'+id).json()['points'])==3
