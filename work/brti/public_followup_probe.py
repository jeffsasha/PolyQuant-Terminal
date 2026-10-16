"""Bounded read-only public research; no config, credentials, or application imports."""
import datetime as dt
import decimal
import hashlib
import json
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent
OUT=ROOT/dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-followup')
OUT.mkdir()
LOG=[]
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError('Redirect rejected')
OPENER=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile='/etc/ssl/cert.pem')))
def get(path,query=None):
    assert path.startswith(('/v1/market/id/','/v1/market/slug/','/v1/asset-prices/history','/v1/markets'))
    url='https://gateway.polymarket.us'+path+('?' + urllib.parse.urlencode(query) if query else '')
    rec={'url':url,'method':'GET','authenticated':False,'started_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    start=time.monotonic(); body=b''
    try:
        req=urllib.request.Request(url,headers={'Accept':'application/json','Cache-Control':'no-cache','User-Agent':'PolyQuant-public-BRTI-research/1.0'},method='GET')
        try: response=OPENER.open(req,timeout=20)
        except urllib.error.HTTPError as e: response=e
        with response:
            body=response.read(3_000_001)
            assert len(body)<=3_000_000
            rec['status']=response.status
            rec['response_headers']={k.lower():v for k,v in response.headers.items() if k.lower() in ('date','age','cache-control','etag','last-modified','cf-cache-status','content-type','cf-ray')}
        rec['sha256']=hashlib.sha256(body).hexdigest(); rec['bytes']=len(body)
        rec['body_file']=f'{len(LOG)+1:03d}.body'
        (OUT/rec['body_file']).write_bytes(body)
        data=json.loads(body)
    except Exception as e:
        rec['error']=str(e);data=None
    rec['received_at']=dt.datetime.now(dt.timezone.utc).isoformat();rec['elapsed_seconds']=round(time.monotonic()-start,6)
    LOG.append(rec);(OUT/'requests.json').write_text(json.dumps(LOG,indent=2)+'\n')
    print(rec.get('status'),path,rec.get('error',''),flush=True)
    return data,rec

def epoch(s):return int(dt.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp())
D=decimal.Decimal

def history(T):
    data,rec=get('/v1/asset-prices/history',{'assets':'crypto:btc','from':T-60,'to':T,'bucket':'ASSET_PRICE_BUCKET_1S'})
    if not data or not data.get('series'):return {'error':'no series','request':rec},None
    s=data['series'][0];cs=s.get('candles',[]); by={int(c['timestamp']):c for c in cs}
    ans={'request_body':rec.get('body_file'),'request_sha256':rec.get('sha256'),'effective_from':s.get('from'),'effective_to':s.get('to'),'count':len(cs),'timestamps_complete':sorted(by)==list(range(T-60,T+1)), 'tick_counts':sorted(set(c.get('tickCount') for c in cs)),'all_ohlc_equal':all(len({c['open'],c['high'],c['low'],c['close']})==1 for c in cs)}
    if ans['timestamps_complete']:
        ans.update(mean_pre=str((sum(D(by[t]['close']) for t in range(T-60,T))/60).quantize(D('.01'))),mean_inclusive=str((sum(D(by[t]['close']) for t in range(T-59,T+1))/60).quantize(D('.01'))),last_pre=by[T-1]['close'],at_boundary=by[T]['close'],first_pre=by[T-60]['close'])
    return ans,by

results=[]
ids=['1483123','1000588','1000678','1467903','1000736']
# Additional hourly identities are taken from the previous complete official inventory.
prior=Path('../../PolyQuant-Terminal-Design/verification/production/20261016T181707.484046Z')
# Resolve relative to repository root rather than diagnostic directory.
prior=Path('../PolyQuant-Terminal-Design/verification/production/20261016T181707.484046Z')
extra=[]
for f in sorted(prior.glob('*.body')):
    try: obj=json.loads(f.read_bytes())
    except (ValueError,UnicodeError):continue
    for m in obj.get('markets',[]):
        terms=m.get('assetPriceTerms') or {}
        if terms.get('horizon')=='1h' and terms.get('windowStart') in ('2026-10-16T19:00:00Z','2026-10-16T20:00:00Z'):
            extra.append(m['id'])
ids+=list(dict.fromkeys(extra))
for ident in ids+['slug:cpc-btc-updown-15m-2026-10-06-1900z','slug:cpc-btc-updown-15m-2026-09-21-0015z']:
    path='/v1/market/slug/'+ident[5:] if ident.startswith('slug:') else '/v1/market/id/'+ident
    data,rec=get(path)
    if not data or 'market' not in data:
        results.append({'identity':ident,'error':'detail unavailable','request':rec});continue
    m=data['market'];terms=m.get('assetPriceTerms') or {};entry={'id':m['id'],'slug':m['slug'],'status':m.get('status'),'detail_body':rec.get('body_file'),'terms':terms,'description':m.get('description')}
    if terms.get('windowStart'):
        entry['open_check'],_=history(epoch(terms['windowStart']))
    if terms.get('settlementPrice'):
        entry['close_check'],_=history(epoch(terms['windowEnd']))
        entry['settlement_route'],settle_rec=get('/v1/markets/'+m['slug']+'/settlement')
        entry['settlement_route_body']=settle_rec.get('body_file')
    results.append(entry)
# Same exact windows as previous five: preserve hash and price comparison separately.
prior_checks=Path('../PolyQuant-Terminal-Design/verification/production/20261016T181849.863538Z-reference-checks')
comparisons=[]
for rec in json.loads((prior_checks/'requests.json').read_text())[:5]:
    u=urllib.parse.urlsplit(rec['url']);data,new=get(u.path,dict(urllib.parse.parse_qsl(u.query)))
    old=json.loads((prior_checks/rec['body_file']).read_bytes())
    comparisons.append({'url':rec['url'],'old_sha256':rec['sha256'],'new_sha256':new.get('sha256'),'new_body':new.get('body_file'),'raw_bytes_equal':rec['sha256']==new.get('sha256'),'parsed_equal':data==old})
(OUT/'summary.json').write_text(json.dumps({'scope':'PUBLIC_READ_ONLY_NO_CREDENTIALS_NO_ORDERS','markets':results,'repeat_comparisons':comparisons},indent=2)+'\n')
print('OUTPUT',OUT,flush=True)
