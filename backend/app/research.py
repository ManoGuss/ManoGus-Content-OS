"""YouTube discovery, immutable observations, and conservative derived metrics."""
import json, os, re, statistics
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from .main import conn, row, uid, now, ROOT

router=APIRouter(prefix='/api/v1')
MIGRATION=ROOT/'database/migrations/versions/002_research.sql'

def migrate():
    with conn() as c:c.executescript(MIGRATION.read_text())

def dt(x):return datetime.fromisoformat(x.replace('Z','+00:00'))
def metric(name,value,reason=None,as_of=None,origin='CALCULATED',sample_size=None):
    return {'name':name,'value':round(value,3) if value is not None else None,'provenance':origin,'reason':reason,'as_of':as_of,'formula_version':'research-v1','sample_size':sample_size}
def duration(value):
    m=re.fullmatch(r'P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?',value or '')
    return sum(int(v or 0)*factor for v,factor in zip(m.groups(),(86400,3600,60,1))) if m else None

class YouTubeClient:
    base='https://www.googleapis.com/youtube/v3/'
    def __init__(self,key):self.key=key
    def get(self,endpoint,params):
        url=self.base+endpoint+'?'+urlencode({**params,'key':self.key})
        try:
            with urlopen(Request(url,headers={'User-Agent':'MANOGUS-Content-OS/0.2'}),timeout=15) as r:return json.load(r)
        except HTTPError as e:
            try:reason=json.load(e).get('error',{}).get('errors',[{}])[0].get('reason','api_error')
            except Exception:reason='api_error'
            raise HTTPException(429 if reason in ('quotaExceeded','rateLimitExceeded','userRateLimitExceeded') else 502,f'YouTube API: {reason}')
        except (URLError,TimeoutError):raise HTTPException(503,'YouTube API indisponível')

_provider_factory=lambda key:YouTubeClient(key)
def provider(key):return _provider_factory(key)

class SearchInput(BaseModel):
    keyword:str=Field(min_length=2,max_length=100)
    region:str=Field(default='US',pattern='^(US|CA|GB|AU)$')
    window_days:int=Field(default=7)
    target_channel_id:str
    difficulty:int|None=Field(default=None,ge=1,le=5)
    def validated(self):
        if self.window_days not in (7,90,180):raise HTTPException(422,'Janela permitida: 7, 90 ou 180 dias')
        return self

def snapshots(c,vid):return [dict(x) for x in c.execute('SELECT * FROM video_snapshots WHERE video_id=? ORDER BY captured_at',(vid,))]
def cohort(c,video,latest):
    age=(dt(latest['captured_at'])-dt(video['published_at'])).total_seconds()/3600
    if age<=0:return None,0
    peers=c.execute('SELECT v.* FROM videos v WHERE v.creator_channel_id=? AND v.id<>? AND v.kind=? AND v.published_at<?',(video['creator_channel_id'],video['id'],video['kind'],video['published_at'])).fetchall()
    vals=[]
    for p in peers:
        pd=dict(p)
        if pd['duration_s'] and video['duration_s'] and not .5<=pd['duration_s']/video['duration_s']<=2:continue
        candidates=[]
        for s in snapshots(c,pd['id']):
            a=(dt(s['captured_at'])-dt(pd['published_at'])).total_seconds()/3600
            if s['views'] is not None and abs(a-age)<=max(age*.2,1):candidates.append((abs(a-age),s['views']))
        if candidates:vals.append(min(candidates)[1])
    if len(vals)<5:return None,len(vals)
    return (latest['views']+100)/(statistics.median(vals)+100),len(vals)

def metrics(c,video):
    ss=snapshots(c,video['id']);valid=[s for s in ss if s['views'] is not None]
    latest=valid[-1] if valid else None;as_of=latest['captured_at'] if latest else None
    age=(dt(as_of)-dt(video['published_at'])).total_seconds()/3600 if latest else 0
    views=latest['views'] if latest else None
    out={'views':metric('views',views,'NO_PUBLIC_COUNT' if views is None else None,as_of,'REAL'),
         'views_day':metric('views_day',views/(age/24) if views is not None and age>=1 else None,'AGE_UNDER_1H_OR_NO_VIEWS' if age<1 or views is None else None,as_of),
         'average_vph':metric('average_vph',views/age if views is not None and age>=1 else None,'AGE_UNDER_1H_OR_NO_VIEWS' if age<1 or views is None else None,as_of)}
    pair=None
    for a in reversed(valid[:-1]):
        hours=(dt(as_of)-dt(a['captured_at'])).total_seconds()/3600
        if 1<=hours<=168:pair=(a,hours);break
    observed=None if not pair or views<pair[0]['views'] else (views-pair[0]['views'])/pair[1]
    out['observed_vph']=metric('observed_vph',observed,'COUNTER_CORRECTION' if pair and views<pair[0]['views'] else 'INSUFFICIENT_SNAPSHOTS' if observed is None else None,as_of,sample_size=2 if pair else 0)
    for window in (1,6,12,24):
        selected=None
        if latest and (datetime.now(timezone.utc)-dt(as_of)).total_seconds()<=7200:
            candidates=[(abs((dt(as_of)-dt(a['captured_at'])).total_seconds()/3600-window),a) for a in valid[:-1] if (dt(as_of)-dt(a['captured_at'])).total_seconds()>=1800]
            if candidates:
                error,a=min(candidates,key=lambda x:x[0]);hours=(dt(as_of)-dt(a['captured_at'])).total_seconds()/3600
                if error<=window*.25 and views>=a['views']:selected=(views-a['views'])/hours
        out[f'recent_vph_{window}h']=metric(f'recent_vph_{window}h',selected,'NO_RECENT_PAIR' if selected is None else None,as_of,sample_size=2 if selected is not None else 0)
    score,n=cohort(c,video,latest) if latest else (None,0)
    out['outlier_score']=metric('outlier_score',score,'INSUFFICIENT_COMPARABLE_COHORT' if score is None else None,as_of,sample_size=n)
    analysis=c.execute('SELECT * FROM research_analyses WHERE video_id=? ORDER BY created_at DESC LIMIT 1',(video['id'],)).fetchone()
    out['click_appeal']=metric('click_appeal',analysis['click_appeal'] if analysis else None,'MANUAL_REVIEW_REQUIRED' if not analysis else None,analysis['created_at'] if analysis else None,'INFERRED',1 if analysis else 0)
    return out

def store_video(c,item,run_id=None,rank=0,captured=None):
    sn=item.get('snippet',{});stats=item.get('statistics',{});youtube_id=item['id'];channel_yid=sn['channelId'];captured=captured or now()
    creator=c.execute('SELECT id FROM creator_channels WHERE youtube_id=?',(channel_yid,)).fetchone()
    cid=creator['id'] if creator else uid()
    c.execute('INSERT INTO creator_channels(id,youtube_id,title,observed_at) VALUES(?,?,?,?) ON CONFLICT(youtube_id) DO UPDATE SET title=excluded.title,observed_at=excluded.observed_at',(cid,channel_yid,sn.get('channelTitle',''),captured))
    existing=c.execute('SELECT id FROM videos WHERE youtube_id=?',(youtube_id,)).fetchone();vid=existing['id'] if existing else uid()
    length=duration(item.get('contentDetails',{}).get('duration',''))
    kind='unknown' if length is None else 'short' if length<=180 else 'long'
    if sn.get('liveBroadcastContent') in ('live','upcoming'):kind='live'
    thumb=sn.get('thumbnails',{}).get('medium',{}).get('url')
    c.execute('INSERT INTO videos(id,youtube_id,creator_channel_id,title,published_at,duration_s,kind,thumbnail_url,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(youtube_id) DO UPDATE SET title=excluded.title,duration_s=excluded.duration_s,kind=excluded.kind,thumbnail_url=excluded.thumbnail_url,updated_at=excluded.updated_at',(vid,youtube_id,cid,sn['title'],sn['publishedAt'],length,kind,thumb,captured,captured))
    if run_id:c.execute('INSERT OR IGNORE INTO source_records(run_id,video_id,rank) VALUES(?,?,?)',(run_id,vid,rank))
    # A snapshot is inserted only after a fresh videos.list response, never from cache or search snippet.
    def count(k):return int(stats[k]) if k in stats else None
    c.execute('INSERT INTO video_snapshots(id,video_id,views,likes,comments,captured_at,source_run_id,source) VALUES(?,?,?,?,?,?,?,?)',(uid(),vid,count('viewCount'),count('likeCount'),count('commentCount'),captured,run_id,'YOUTUBE_DATA_API'))
    return vid

@router.post('/research/search',status_code=201)
def search(data:SearchInput):
    data.validated()
    key=os.getenv('YOUTUBE_API_KEY')
    if not key:raise HTTPException(503,'Configure YOUTUBE_API_KEY no ambiente do backend')
    with conn() as c:row(c,'channels',data.target_channel_id)
    requested=now();start=(datetime.now(timezone.utc)-timedelta(days=data.window_days)).isoformat().replace('+00:00','Z')
    client=provider(key)
    # One page (<=50) is explicit; quota and coverage are not represented as exhaustive.
    result=client.get('search',{'part':'snippet','q':data.keyword,'type':'video','regionCode':data.region,'relevanceLanguage':'en','maxResults':50,'order':'date','publishedAfter':start,'publishedBefore':requested.replace('+00:00','Z')})
    ids=list(dict.fromkeys(x.get('id',{}).get('videoId') for x in result.get('items',[]) if x.get('id',{}).get('videoId')))
    hydrated=client.get('videos',{'part':'snippet,contentDetails,statistics','id':','.join(ids),'maxResults':50}) if ids else {'items':[]}
    by_id={item['id']:item for item in hydrated.get('items',[])}
    with conn() as c:
        run=uid();c.execute('INSERT INTO source_runs(id,keyword,region,window_days,requested_at,completed_at,status,result_count,coverage_note) VALUES(?,?,?,?,?,?,?,?,?)',(run,data.keyword,data.region,data.window_days,requested,now(),'completed',len(by_id),'Primeira página de busca; amostra não exaustiva'))
        for rank,yid in enumerate(ids):
            if yid in by_id:store_video(c,by_id[yid],run,rank)
        if data.difficulty is not None:score_opportunity(c,run,data.target_channel_id,data.difficulty)
        return {'id':run,'status':'completed','result_count':len(by_id),'coverage_note':'Primeira página de busca; amostra não exaustiva','as_of':requested}

def score_opportunity(c,run_id,channel_id,difficulty):
    run=row(c,'source_runs',run_id);vids=[dict(x) for x in c.execute('SELECT v.* FROM videos v JOIN source_records sr ON sr.video_id=v.id WHERE sr.run_id=?',(run_id,))]
    outs=[metrics(c,v) for v in vids]
    outliers=[m['outlier_score']['value'] for m in outs if m['outlier_score']['value'] is not None]
    clicks=[m['click_appeal']['value'] for m in outs if m['click_appeal']['value'] is not None]
    recent=[];older=[]
    cutoff=dt(run['requested_at'])
    for v in c.execute('SELECT v.* FROM videos v JOIN source_records sr ON sr.video_id=v.id JOIN source_runs r ON r.id=sr.run_id WHERE r.keyword=? AND r.region=? GROUP BY v.id',(run['keyword'],run['region'])):
        item=dict(v);age=(cutoff-dt(item['published_at'])).total_seconds()/86400
        if age<0 or age>90:continue
        observed=metrics(c,item)['observed_vph']['value']
        (recent if age<=7 else older).append((item['id'],observed))
    trend=None
    if len(recent)>=5 and len(older)>=5:
        fresh=[x for _,x in recent if x is not None];historical=[x for _,x in older if x is not None]
        if len(fresh)>=5 and len(historical)>=5:
            acceleration=statistics.median(fresh)/(statistics.median(historical)+1)
            acceleration_score=max(0,min(100,50+25*__import__('math').log2(max(acceleration,.01))))
            density=(len(recent)/7)/(len(older)/83)
            density_score=max(0,min(100,50+25*__import__('math').log2(max(density,.01))))
            trend=round(.6*acceleration_score+.4*density_score,3)
    missing=[]
    if trend is None:missing.append('TREND_REQUIRES_TWO_PERIODS_WITH_OBSERVED_GROWTH')
    if not outliers:missing.append('OUTLIER_COHORT_INSUFFICIENT')
    if difficulty is None:missing.append('PRODUCTION_REVIEW_REQUIRED')
    if not clicks:missing.append('CLICK_APPEAL_REVIEW_REQUIRED')
    evidence=min(100,statistics.median(outliers)*50) if outliers else None
    click=statistics.mean(clicks) if clicks else None
    components={'trend':trend,'outlier_evidence':evidence,'click_appeal':click,'production_ease':(6-difficulty)*20 if difficulty else None}
    # v1 uses only measured/reviewed components; missing optional components renormalize.
    weights={'trend':.25,'outlier_evidence':.20,'click_appeal':.15,'production_ease':.10}
    score=round(sum(components[k]*w for k,w in weights.items() if components[k] is not None)/sum(w for k,w in weights.items() if components[k] is not None),3) if trend is not None and evidence is not None and difficulty is not None else None
    existing=c.execute('SELECT id FROM research_opportunities WHERE run_id=? AND target_channel_id=?',(run_id,channel_id)).fetchone()
    oid=existing['id'] if existing else uid()
    c.execute('INSERT INTO research_opportunities(id,run_id,target_channel_id,topic,difficulty,trend_score,outlier_evidence,click_appeal,score,missing_json,components_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id,target_channel_id) DO UPDATE SET difficulty=excluded.difficulty,trend_score=excluded.trend_score,outlier_evidence=excluded.outlier_evidence,click_appeal=excluded.click_appeal,score=excluded.score,missing_json=excluded.missing_json,components_json=excluded.components_json',(oid,run_id,channel_id,run['keyword'],difficulty,trend,evidence,click,score,json.dumps(missing),json.dumps(components),now()))
    return {'id':oid,'topic':run['keyword'],'score':score,'missing':missing,'components':components,'provenance':'INFERRED'}

@router.get('/research/runs')
def list_runs():
    with conn() as c:return [dict(x) for x in c.execute('SELECT * FROM source_runs ORDER BY requested_at DESC LIMIT 50')]
@router.get('/research/runs/{id}')
def get_run(id:str):
    with conn() as c:return row(c,'source_runs',id)
@router.get('/research/videos')
def list_videos(run_id:str):
    with conn() as c:
        run=row(c,'source_runs',run_id)
        items=[dict(x) for x in c.execute('SELECT v.* FROM videos v JOIN source_records sr ON sr.video_id=v.id WHERE sr.run_id=? ORDER BY sr.rank LIMIT 50',(run_id,))]
        return {'items':[{**v,'metrics':metrics(c,v)} for v in items],'coverage':run['coverage_note'],'as_of':run['completed_at']}
@router.get('/videos/{id}/snapshots')
def get_snapshots(id:str):
    with conn() as c:row(c,'videos',id);return snapshots(c,id)
@router.get('/research/videos/{id}')
def get_video(id:str):
    with conn() as c:
        v=row(c,'videos',id);return {**v,'snapshots':snapshots(c,id),'metrics':metrics(c,v)}
@router.post('/research/videos/{id}/refresh')
def refresh(id:str):
    key=os.getenv('YOUTUBE_API_KEY')
    if not key:raise HTTPException(503,'Configure YOUTUBE_API_KEY no backend')
    with conn() as c:v=row(c,'videos',id)
    items=provider(key).get('videos',{'part':'snippet,contentDetails,statistics','id':v['youtube_id']}).get('items',[])
    if not items:raise HTTPException(404,'Vídeo indisponível na API')
    with conn() as c:
        store_video(c,items[0]);return {'video_id':id,'metrics':metrics(c,row(c,'videos',id))}
class AppealInput(BaseModel):
    title_scores:list[int]=Field(min_length=4,max_length=4)
    thumbnail_scores:list[int]=Field(min_length=4,max_length=4)
    visual_evidence:str=Field(min_length=5,max_length=500)
    review_note:str=Field(min_length=5,max_length=1000)
@router.post('/research/videos/{id}/click-appeal')
def appeal(id:str,data:AppealInput):
    if any(not 0<=v<=5 for v in data.title_scores+data.thumbnail_scores):raise HTTPException(422,'Notas devem estar entre 0 e 5')
    with conn() as c:
        v=row(c,'videos',id)
        if not v['thumbnail_url']:raise HTTPException(422,'Miniatura indisponível; avaliação visual impossível')
        score=(sum(data.title_scores)+sum(data.thumbnail_scores))/40*100
        c.execute('INSERT INTO research_analyses(id,video_id,title_rubric,thumbnail_rubric,visual_evidence,review_note,click_appeal,created_at) VALUES(?,?,?,?,?,?,?,?)',(uid(),id,json.dumps(data.title_scores),json.dumps(data.thumbnail_scores),data.visual_evidence,data.review_note,score,now()))
        return metrics(c,v)['click_appeal']
@router.post('/research/runs/{id}/opportunity')
def opportunity(id:str,target_channel_id:str,difficulty:int=Query(ge=1,le=5)):
    with conn() as c:
        row(c,'channels',target_channel_id)
        return score_opportunity(c,id,target_channel_id,difficulty)
@router.get('/opportunities')
def opportunities(target_channel_id:str):
    with conn() as c:
        row(c,'channels',target_channel_id)
        return [{**dict(x),'missing':json.loads(x['missing_json']),'components':json.loads(x['components_json'])} for x in c.execute('SELECT * FROM research_opportunities WHERE target_channel_id=? ORDER BY created_at DESC',(target_channel_id,))]
