"""Manual Google Trends CSV adapter. Relative indices are scoped to an export."""
import csv, hashlib, io, re
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from urllib.parse import urlparse
from .main import conn, uid, now, ROOT
router=APIRouter(prefix='/api/v1/trends')
MAX_BYTES=256_000
class TrendsAdapter:
    def parse(self,csv_text:str,term:str):raise NotImplementedError

def date_part(value):
    value=value.strip()
    for fmt in ('%Y-%m-%d','%Y-%m','%Y/%m/%d','%m/%d/%Y'):
        try:
            d=datetime.strptime(value,fmt).date()
            return d.isoformat()
        except ValueError:pass
    raise ValueError('Data inválida; use YYYY-MM-DD, YYYY-MM ou MM/DD/YYYY')

class ManualCsvTrendsAdapter(TrendsAdapter):
    def parse(self,csv_text:str,term:str):
        lines=csv_text.lstrip('\ufeff').replace('\r\n','\n').splitlines()
        # Official exports commonly prepend a category and a blank line.
        header_at=next((i for i,line in enumerate(lines[:8]) if line.strip().lower().startswith(('week,','day,','month,','date,','semana,','dia,','mês,'))),None)
        if header_at is None:raise ValueError('Cabeçalho temporal não encontrado (Week, Day, Month ou Date)')
        rows=list(csv.reader(io.StringIO('\n'.join(lines[header_at:]))))
        if len(rows)<2:raise ValueError('CSV sem observações')
        columns=rows[0]
        if len(columns)!=2:raise ValueError('Exporte uma única série/termo por CSV; comparações múltiplas não são combinadas')
        if term.casefold() not in columns[1].casefold():raise ValueError('O termo informado não corresponde à coluna exportada')
        points=[];seen=set()
        for row in rows[1:]:
            if not row or all(not x.strip() for x in row):continue
            if len(row)!=2:raise ValueError('Linha CSV com número de colunas diferente do cabeçalho')
            parts=re.split(r'\s+-\s+',row[0].strip())
            if len(parts)>2:raise ValueError('Intervalo inválido')
            start=date_part(parts[0]);end=date_part(parts[-1])
            if end<start:raise ValueError('Fim anterior ao início')
            raw=row[1].strip()
            if raw=='<1':value=None
            elif raw.isascii() and raw.isdigit() and 0<=int(raw)<=100:value=int(raw)
            else:raise ValueError('Índice inválido; use inteiro 0–100 ou <1')
            if (start,end) in seen:raise ValueError('Período duplicado')
            seen.add((start,end));points.append((start,end,value))
            if len(points)>10000:raise ValueError('Máximo de 10.000 observações')
        if not points:raise ValueError('CSV sem observações')
        if points!=sorted(points):raise ValueError('Períodos fora de ordem')
        return points

class ImportIn(BaseModel):
    term:str=Field(min_length=2,max_length=100)
    region:str=Field(pattern='^(US|CA|GB|AU|BR|WORLD)$')
    timeframe:str=Field(min_length=2,max_length=50)
    source_ref:str=Field(min_length=5,max_length=500)
    normalization_group:str=Field(min_length=3,max_length=100)
    csv_text:str=Field(min_length=12)

def migrate():
    with conn() as c:c.executescript((ROOT/'database/migrations/versions/003_trends.sql').read_text())

_adapter=ManualCsvTrendsAdapter()
@router.post('/import',status_code=201)
def import_trends(data:ImportIn):
    parsed=urlparse(data.source_ref)
    if parsed.scheme!='https' or parsed.hostname not in ('trends.google.com','support.google.com'):
        raise HTTPException(422,'A fonte deve ser uma URL HTTPS do Google Trends')
    if len(data.csv_text.encode('utf-8'))>MAX_BYTES:raise HTTPException(413,'CSV excede 256 KB')
    try:points=_adapter.parse(data.csv_text,data.term)
    except ValueError as e:raise HTTPException(422,str(e))
    # Hash includes declared scope: the same export cannot silently change context.
    content='\x1f'.join([data.term.casefold(),data.region,data.timeframe,data.source_ref,data.normalization_group,data.csv_text])
    digest=hashlib.sha256(content.encode()).hexdigest()
    with conn() as c:
        existing=c.execute('SELECT id FROM trend_series WHERE sha256=?',(digest,)).fetchone()
        if existing:return {'id':existing['id'],'point_count':len(points),'duplicate':True}
        sid=uid();c.execute('INSERT INTO trend_series(id,term,region,timeframe,source_ref,normalization_group,method,sha256,imported_at,point_count,scale_note) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,data.term,data.region,data.timeframe,data.source_ref,data.normalization_group,'MANUAL_GOOGLE_TRENDS_CSV',digest,now(),len(points),'Índice relativo 0–100 dentro da exportação; <1 significa valor abaixo de 1, armazenado como indisponível'))
        c.executemany('INSERT INTO trend_points(id,series_id,period_start,period_end,interest_index) VALUES(?,?,?,?,?)',[(uid(),sid,a,b,v) for a,b,v in points])
        return {'id':sid,'point_count':len(points),'duplicate':False}
@router.get('/series')
def list_series(term:str|None=None,region:str|None=None):
    with conn() as c:
        q='SELECT id,term,region,timeframe,source_ref,normalization_group,method,imported_at,point_count,scale_note FROM trend_series WHERE 1=1';args=[]
        if term:q+=' AND term=?';args.append(term)
        if region:q+=' AND region=?';args.append(region)
        q+=' ORDER BY imported_at DESC LIMIT 100'
        return [dict(x) for x in c.execute(q,args)]
@router.get('/series/{id}')
def get_series(id:str):
    with conn() as c:
        s=c.execute('SELECT id,term,region,timeframe,source_ref,normalization_group,method,imported_at,point_count,scale_note FROM trend_series WHERE id=?',(id,)).fetchone()
        if not s:raise HTTPException(404,'Série não encontrada')
        return {**dict(s),'points':[dict(x) for x in c.execute('SELECT period_start,period_end,interest_index FROM trend_points WHERE series_id=? ORDER BY period_start',(id,))]}
