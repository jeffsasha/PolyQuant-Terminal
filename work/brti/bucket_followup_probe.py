from pathlib import Path
source=Path('work/brti/public_followup_probe.py').read_text()
exec(compile(source.split('\nresults=[]\n')[0],str(Path('work/brti/public_followup_probe.py').resolve()),'exec'))
rows=[]
for T in (1791313200,1792173600,1792174500):
    for bucket in ('ASSET_PRICE_BUCKET_1S','ASSET_PRICE_BUCKET_5S','ASSET_PRICE_BUCKET_1M'):
        data,rec=get('/v1/asset-prices/history',{'assets':'crypto:btc','from':T-60,'to':T-1,'bucket':bucket})
        rows.append({'T':T,'bucket':bucket,'body_file':rec.get('body_file'),'series':data})
(OUT/'summary.json').write_text(json.dumps({'scope':'PUBLIC_READ_ONLY_NO_CREDENTIALS_NO_ORDERS','rows':rows},indent=2)+'\n')
print('OUTPUT',OUT)
