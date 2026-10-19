import asyncio
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from polyquant.reference import ReferenceVerifier,index_close_at,summarize_checks
from polyquant.types import MarketTerms

# Market 1483123 (BTC 15m, 2026-10-16 18:15-18:30 UTC); official anchors and 1S closes from docs/BRTI_FOLLOWUP_RESEARCH.md.
START=datetime(2026,10,16,18,15,tzinfo=timezone.utc); END=START+timedelta(minutes=15)
CLOSES={int(START.timestamp())-2:'81220.10',int(START.timestamp())-1:'81221.17',int(START.timestamp()):'81220.80',
        int(END.timestamp())-2:'81285.11',int(END.timestamp())-1:'81285.77',int(END.timestamp()):'81285.90'}


def market(identity='1483123'):
    return MarketTerms(identity,'btc-updown-15m-'+identity,'15m',START,END,Decimal('81221.17'))


class Transport:
    def __init__(self,status='MARKET_STATUS_RESOLVED',settlement='81285.77',closes=CLOSES):
        self.status=status;self.settlement=settlement;self.closes=closes;self.calls=[]
    async def request(self,method,path,params=None):
        self.calls.append((method,path,dict(params or {})))
        if path.startswith('/v1/market/slug/'):
            terms={'priceToBeat':{'value':'81221.17','currency':'USD'}}
            if self.settlement: terms['settlementPrice']={'value':self.settlement,'currency':'USD'}
            return {'market':{'id':path.rsplit('-',1)[-1],'status':self.status,'assetPriceTerms':terms}},{}
        candles=[{'timestamp':t,'close':self.closes[t],'tickCount':60} for t in range(params['from'],params['to']+1) if t in self.closes]
        return {'series':[{'asset':{'symbol':'btc'},'candles':candles}]},{}


def test_index_close_requires_exact_positive_tick_second():
    payload={'series':[{'asset':{'symbol':'btc'},'candles':[{'timestamp':10,'close':'1.00','tickCount':60},{'timestamp':11,'close':'2.00','tickCount':0}]}]}
    assert index_close_at(payload,10)==Decimal('1.00')
    assert index_close_at(payload,11) is None
    assert index_close_at(payload,12) is None


def test_resolved_market_matches_both_anchors_at_t_minus_one_second():
    transport=Transport();verifier=ReferenceVerifier(transport)
    result=asyncio.run(verifier.check(market()))
    assert result['match'] and [a['index'] for a in result['anchors']]==[Decimal('81221.17'),Decimal('81285.77')]
    assert all(method=='GET' for method,_,_ in transport.calls)
    assert [p['from']+1 for _,path,p in transport.calls if path=='/v1/asset-prices/history']==[int(START.timestamp())-1,int(END.timestamp())-1]


def test_mismatch_is_reported_not_hidden():
    result=asyncio.run(ReferenceVerifier(Transport(settlement='81285.90')).check(market()))
    assert not result['match'] and result['anchors'][1]['official']==Decimal('81285.90')
    summary=summarize_checks([result]*5)
    assert summary['status']=='MISMATCH' and summary['matched']==0 and len(summary['mismatches'])==3


def test_unresolved_or_missing_data_is_retried_not_counted():
    assert asyncio.run(ReferenceVerifier(Transport(status='MARKET_STATUS_CLOSED')).check(market())) is None
    assert asyncio.run(ReferenceVerifier(Transport(settlement=None)).check(market())) is None
    assert asyncio.run(ReferenceVerifier(Transport(closes={})).check(market())) is None
    verifier=ReferenceVerifier(Transport(status='MARKET_STATUS_CLOSED'));verifier.enqueue(market())
    assert asyncio.run(verifier.run_due(END+timedelta(seconds=10)))==[] and verifier.queue['1483123'][2]==0
    asyncio.run(verifier.run_due(END+timedelta(minutes=1)))
    assert verifier.queue['1483123'][2]==1 and verifier.snapshot()['checked']==0


def test_status_needs_minimum_markets_and_finishes_each_market_once():
    verifier=ReferenceVerifier(Transport())
    for identity in ['1','2','3']: verifier.enqueue(market(identity))
    assert verifier.snapshot()['status']=='PENDING' and verifier.snapshot()['pending']==3
    added=asyncio.run(verifier.run_due(END+timedelta(minutes=1),limit=3))
    assert [r['market_id'] for r in added]==['1','2','3']
    snapshot=verifier.snapshot()
    assert snapshot['status']=='VERIFIED' and snapshot['checked']==3 and snapshot['pending']==0
    verifier.enqueue(market('1'))
    assert verifier.snapshot()['pending']==0
