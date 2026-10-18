from pathlib import Path
source=Path('work/brti/public_followup_probe.py').read_text()
exec(compile(source.split('\nresults=[]\n')[0],str(Path('work/brti/public_followup_probe.py').resolve()),'exec'))
all_markets=[]
listing_logs=[]
for offset in range(0,800,100):
    listing,listingrec=get('/v1/markets',{'closed':'true','categories':'crypto','includeHidden':'true','limit':100,'offset':offset,'endDateMin':'2026-10-16T18:00:00Z','endDateMax':'2026-10-16T21:30:00Z'})
    listing_logs.append(listingrec)
    page=(listing or {}).get('markets',[])
    all_markets.extend(page)
    candidates=[m for m in all_markets if (m.get('assetPriceTerms') or {}).get('horizon')=='1h' and (m.get('assetPriceTerms') or {}).get('indexSymbol')=='BRTI' and (m.get('assetPriceTerms') or {}).get('settlementPrice')]
    if len(candidates)>=3 or not page:break
results=[]
for m in candidates[:3]:
    data,rec=get('/v1/market/id/'+m['id'])
    if not data or 'market' not in data:continue
    m=data['market'];t=m.get('assetPriceTerms') or {}
    entry={'id':m['id'],'slug':m['slug'],'status':m.get('status'),'ep3Status':m.get('ep3Status'),'closed':m.get('closed'),'active':m.get('active'),'outcomePrices':m.get('outcomePrices'),'marketSides':m.get('marketSides'),'detail_body':rec['body_file'],'terms':t,'description':m.get('description')}
    entry['open_check'],_=history(epoch(t['windowStart']))
    entry['close_check'],_=history(epoch(t['windowEnd']))
    entry['settlement_route'],sr=get('/v1/markets/'+m['slug']+'/settlement');entry['settlement_route_body']=sr.get('body_file')
    results.append(entry)
(OUT/'summary.json').write_text(json.dumps({'scope':'PUBLIC_READ_ONLY_NO_CREDENTIALS_NO_ORDERS','listing_bodies':[r.get('body_file') for r in listing_logs],'market_count':len(all_markets),'discovery_complete':not page,'markets':results},indent=2)+'\n')
print('OUTPUT',OUT)
