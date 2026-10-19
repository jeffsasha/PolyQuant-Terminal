import httpx,ssl,uuid
from collections import deque
from datetime import timedelta
from decimal import Decimal
from .types import ReferenceSnapshot,decimal,utcnow,timestamp

REFERENCE_RULE='Official anchor = BRTI 1S history close at T-1s (the 1S series is already the trailing 60-second average)'


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


def index_close_at(payload,second):
    """The positive-tick 1S close whose bucket starts at `second`, or None."""
    series=next((s for s in payload.get('series',[]) if s.get('asset',{}).get('symbol')=='btc'),None)
    for candle in (series or {}).get('candles',[]):
        if int(candle.get('timestamp',-1))==second and candle.get('tickCount',0)>0: return decimal(str(candle['close']))
    return None


def official_usd(amount):
    return decimal(str(amount['value'])) if amount and amount.get('currency')=='USD' and amount.get('value') is not None else None


def summarize_checks(results,minimum=3):
    """VERIFIED needs `minimum` resolved markets and no mismatch among the retained results."""
    results=list(results); mismatches=[r for r in results if not r['match']]
    status='MISMATCH' if mismatches else 'VERIFIED' if len(results)>=minimum else 'PENDING'
    return {'status':status,'rule':REFERENCE_RULE,'checked':len(results),'matched':len(results)-len(mismatches),
            'minimum':minimum,'mismatches':mismatches[-3:],'last':results[-1] if results else None}


class ReferenceVerifier:
    """Cross-checks each resolved market's official priceToBeat and settlementPrice against the 1S BRTI history at
    T-1s. Evidence only: it never opens a trading gate. Model strategies stay disabled until they are fitted."""
    minimum=3; first_check=timedelta(seconds=45); retry=timedelta(seconds=60); attempts=10
    def __init__(self,transport,keep=48):
        self.transport=transport; self.results=deque(maxlen=keep); self.queue={}; self.finished=set()
    def enqueue(self,market):
        if market.id not in self.finished and market.id not in self.queue: self.queue[market.id]=[market,market.end+self.first_check,0]
    async def run_due(self,now=None,limit=1):
        now=now or utcnow(); added=[]
        for identity,item in sorted(self.queue.items(),key=lambda pair:pair[1][1])[:limit]:
            market,due,tries=item
            if due>now: break
            try: result=await self.check(market)
            except Exception: result=None
            if result is not None: self.results.append(result); added.append(result)
            if result is not None or tries+1>=self.attempts: self.queue.pop(identity,None); self.finished.add(identity)
            else: item[1]=now+self.retry; item[2]=tries+1
        return added
    async def check(self,market):
        detail,_=await self.transport.request('GET','/v1/market/slug/'+market.slug,{'_pq_read':uuid.uuid4().hex})
        raw=detail.get('market') or {}
        if str(raw.get('id'))!=market.id: raise ValueError('Reference check instrument mismatch')
        if raw.get('status')!='MARKET_STATUS_RESOLVED': return None
        terms=raw.get('assetPriceTerms') or {}
        anchors=[]
        for name,official,boundary in [('open',official_usd(terms.get('priceToBeat')),market.start),('close',official_usd(terms.get('settlementPrice')),market.end)]:
            if official is None: return None
            second=int((boundary-timedelta(seconds=1)).timestamp())
            payload,_=await self.transport.request('GET','/v1/asset-prices/history',{
                'assets':'crypto:btc','from':second-1,'to':second+1,'bucket':'ASSET_PRICE_BUCKET_1S'})
            index=index_close_at(payload,second)
            if index is None: return None
            anchors.append({'anchor':name,'boundary':boundary,'official':official,'index':index,'match':index==official})
        return {'market_id':market.id,'slug':market.slug,'horizon':market.horizon,'checked_at':utcnow(),'anchors':anchors,
                'match':all(a['match'] for a in anchors)}
    def snapshot(self): return {**summarize_checks(self.results,self.minimum),'pending':len(self.queue)}
