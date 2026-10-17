import datetime as dt,hashlib,json,ssl,time,urllib.request,urllib.error
from pathlib import Path
out=Path('work/brti')/dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-sources');out.mkdir()
urls=[
'https://docs.polymarket.us/api-reference/asset-prices/overview.md',
'https://docs.polymarket.us/trader-guide/crypto-schema.md',
'https://docs.polymarket.us/faqs/crypto-faqs.md',
'https://docs.polymarket.us/api-reference/market/overview.md',
'https://docs.polymarket.us/changelog.md',
'https://docs.polymarket.us/api-reference/oapi-schemas/asset-prices-schema.json',
'https://docs.polymarket.us/learn/markets/market-resolution.md',
'https://docs.cfbenchmarks.com/CME%20CF%20Real%20Time%20Indices%20Methodology.pdf',
'https://docs.cfbenchmarks.com/api/rest/latest-values/',
'https://docs.cfbenchmarks.com/api/rest/historical-values/',
'https://polymarketexchange.com/files/legal/latest/rulebook',
]
log=[]
for i,url in enumerate(urls,1):
    rec={'url':url,'method':'GET','authenticated':False,'started_at':dt.datetime.now(dt.timezone.utc).isoformat()};start=time.monotonic()
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'PolyQuant-public-BRTI-research/1.0'},method='GET')
        try:r=urllib.request.urlopen(req,context=ssl.create_default_context(cafile='/etc/ssl/cert.pem'),timeout=20)
        except urllib.error.HTTPError as e:r=e
        with r:
            body=r.read(6_000_001);assert len(body)<=6_000_000
            rec.update(status=r.status,final_url=r.url,body_file=f'{i:03d}.body',sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),response_headers={k.lower():v for k,v in r.headers.items() if k.lower() in ('date','etag','last-modified','content-type','cache-control','age')})
            (out/rec['body_file']).write_bytes(body)
    except Exception as e:rec['error']=str(e)
    rec['received_at']=dt.datetime.now(dt.timezone.utc).isoformat();rec['elapsed_seconds']=round(time.monotonic()-start,6);log.append(rec)
    (out/'requests.json').write_text(json.dumps(log,indent=2)+'\n');print(rec.get('status'),url,rec.get('error',''),flush=True)
print('OUTPUT',out)
