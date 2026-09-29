import os,tempfile
from pathlib import Path
from datetime import datetime,timezone,timedelta
from fastapi.testclient import TestClient

def test_research_flow(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        from backend.app import main,research
        main.DB=Path(d)/'research.db'
        os.environ['YOUTUBE_API_KEY']='fixture-key'
        now=datetime.now(timezone.utc)
        published=(now-timedelta(days=2)).isoformat()
        class Fixture:
            views=1000
            def get(self,endpoint,params):
                if endpoint=='search':
                    assert params['publishedAfter'] and params['regionCode']=='US' and params['maxResults']==50
                    return {'items':[{'id':{'videoId':'abc123'}},{'id':{'videoId':'abc123'}}]}
                return {'items':[{'id':'abc123','snippet':{'channelId':'creator1','channelTitle':'Creator','title':'Minecraft Anarchy Challenge','publishedAt':published,'thumbnails':{'medium':{'url':'https://i.ytimg.com/vi/abc123/mqdefault.jpg'}}},'contentDetails':{'duration':'PT12M'},'statistics':{'viewCount':str(self.views),'likeCount':'55'}}]}
        fixture=Fixture();monkeypatch.setattr(research,'_provider_factory',lambda key:fixture)
        with TestClient(main.app) as client:
            ch=client.get('/api/v1/channels').json()[0]['id']
            assert client.post('/api/v1/research/search',json={'keyword':'Minecraft Anarchy','target_channel_id':ch,'window_days':14}).status_code==422
            run=client.post('/api/v1/research/search',json={'keyword':'Minecraft Anarchy','target_channel_id':ch,'window_days':7,'difficulty':3}).json()
            assert run['result_count']==1
            video=client.get('/api/v1/research/videos',params={'run_id':run['id']}).json()['items'][0]
            vid=video['id'];m=video['metrics']
            assert m['views']['value']==1000 and m['views_day']['value']>0
            assert m['average_vph']['value']>0 and m['observed_vph']['value'] is None
            assert m['outlier_score']['value'] is None and m['click_appeal']['value'] is None
            assert client.post(f'/api/v1/research/videos/{vid}/click-appeal',json={'title_scores':[4,4,4,4],'thumbnail_scores':[3,3,3,3],'visual_evidence':'Miniatura legível e focada','review_note':'Título e visual coerentes'}).json()['value']==70
            fixture.views=1300
            # Move the first observation 2h back to simulate a previously collected real API response.
            with main.conn() as c:c.execute('UPDATE video_snapshots SET captured_at=? WHERE video_id=?',((now-timedelta(hours=2)).isoformat(),vid))
            refreshed=client.post(f'/api/v1/research/videos/{vid}/refresh').json()['metrics']
            assert 140<refreshed['observed_vph']['value']<160
            assert refreshed['recent_vph_1h']['value'] is None
            assert refreshed['recent_vph_6h']['value'] is None
            assert len(client.get(f'/api/v1/videos/{vid}/snapshots').json())==2
            op=client.post(f'/api/v1/research/runs/{run["id"]}/opportunity',params={'target_channel_id':ch,'difficulty':3}).json()
            assert op['score'] is None and 'TREND_REQUIRES_TWO_PERIODS_WITH_OBSERVED_GROWTH' in op['missing']
            assert len(client.get('/api/v1/opportunities',params={'target_channel_id':ch}).json())==1
        os.environ.pop('YOUTUBE_API_KEY',None)
