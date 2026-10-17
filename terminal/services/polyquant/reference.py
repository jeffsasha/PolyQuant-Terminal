import httpx,ssl
from decimal import Decimal
from .types import ReferenceSnapshot,decimal,utcnow,timestamp


class ReferenceProvider:
    def __init__(self,transport): self.transport=transport
    async def latest(self):
        end=int(utcnow().timestamp())-1
        payload,_=await self.transport.request('GET','/v1/asset-prices/history',{
            'assets':'crypto:btc','from':end-30,'to':end,'bucket':'ASSET_PRICE_BUCKET_1S'})
        series=next((s for s in payload.get('series',[]) if s.get('asset',{}).get('symbol')=='btc'),None)
        candles=(series or {}).get('candles',[])
        if not candles or candles[-1].get('tickCount',0)<=0: raise ValueError('Reference has no valid latest tick')
        last=candles[-1]
        return ReferenceSnapshot(decimal(str(last['close'])),__import__('datetime').datetime.fromtimestamp(last['timestamp'],__import__('datetime').timezone.utc),utcnow(),False)


class SpotProvider:
    def __init__(self):
        from pathlib import Path
        context=ssl.create_default_context(cafile='/etc/ssl/cert.pem' if Path('/etc/ssl/cert.pem').exists() else None)
        self.client=httpx.AsyncClient(base_url='https://api.exchange.coinbase.com',verify=context,timeout=12,follow_redirects=False)
    async def latest(self):
        response=await self.client.get('/products/BTC-USD/ticker'); response.raise_for_status()
        raw=response.json(parse_float=Decimal)
        return {'value':str(decimal(str(raw['price']))),'source':'Coinbase BTC-USD spot','source_at':raw.get('time'),
                'received_at':utcnow().isoformat(),'volume':raw.get('volume')}
    async def candles(self,timeframe='1m'):
        seconds={'1m':60,'5m':300,'15m':900,'1h':3600}[timeframe]
        response=await self.client.get('/products/BTC-USD/candles',params={'granularity':seconds})
        response.raise_for_status()
        raw=response.json()
        if not isinstance(raw,list): raise ValueError('Invalid spot candle schema')
        return [{'time':int(row[0]),'low':row[1],'high':row[2],'open':row[3],'close':row[4],'volume':row[5]} for row in sorted(raw,key=lambda r:r[0])]
    async def close(self): await self.client.aclose()
