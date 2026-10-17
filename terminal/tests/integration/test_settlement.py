from decimal import Decimal as D
from polyquant.types import OrderIntent,ExecutionResult,Fill

def test_final_settlement_pays_once_and_corrections_compensate(store):
    store.reserve(OrderIntent('open','probability','fixture','BUY_UP',D('4'),D('.5')),D('2.10'))
    store.commit_execution('open',ExecutionResult((Fill(D('.5'),D('4'),D('.07')),),'FILLED'))
    store.settle_market('fixture','UP','official-revision-1',final=False)
    assert store.state('probability').cash==D('997.93')
    store.settle_market('fixture','UP','official-revision-1',final=True)
    store.settle_market('fixture','UP','official-revision-1',final=True)
    assert store.state('probability').cash==D('1001.93')
    assert not store.state('probability').positions
    store.settle_market('fixture','DOWN','official-revision-2',final=True)
    assert store.state('probability').cash==D('997.93')
    with store.connect() as c:
        assert c.execute('SELECT SUM(amount) AS total FROM postings').fetchone()['total']==0

def test_daily_halt_cannot_resume_same_day(store):
    import pytest
    store.halt('probability','DAILY_LOSS_LIMIT')
    with pytest.raises(ValueError): store.resume('probability')

def test_daily_halt_resumes_explicitly_after_risk_day_rollover(store,monkeypatch):
    from datetime import timedelta
    import polyquant.store as module
    from polyquant.types import utcnow
    now=utcnow();monkeypatch.setattr(module,'utcnow',lambda:now)
    store.halt('probability','DAILY_LOSS_LIMIT')
    monkeypatch.setattr(module,'utcnow',lambda:now+timedelta(days=1))
    store.roll_days()
    assert store.state('probability').halts==('DAILY_LOSS_LIMIT',)
    store.resume('probability')
    assert store.state('probability').halts==()

def test_official_correction_chain_can_return_to_a_prior_outcome(store):
    import asyncio
    from polyquant.settlement import SettlementProvider
    from polyquant.types import MarketTerms
    from test_settlement_provider import detail
    raw=detail();market=MarketTerms.from_raw(raw['market'])
    order=OrderIntent('correction-revert','manual',market.id,'BUY_UP',D('4'),D('.5'),'manual_discretionary')
    store.reserve(order,D('2.10'));store.commit_execution(order.id,ExecutionResult((Fill(D('.5'),D('4'),D('.07')),),'FILLED'))
    payout=[1]
    class Transport:
        async def request(self,method,path,params=None):
            return (raw if '/market/slug/' in path else {'slug':market.slug,'settlement':payout[0]}),{}
    provider=SettlementProvider(Transport(),store)
    for value,cash in [(1,D('1001.93')),(0,D('997.93')),(1,D('1001.93')),(1,D('1001.93'))]:
        payout[0]=value;assert asyncio.run(provider.reconcile(market))=='SETTLED';assert store.state('manual').cash==cash
    with store.connect() as c:
        assert c.execute('SELECT count(*) AS count FROM settlements').fetchone()['count']==3
        assert c.execute('SELECT SUM(amount) AS total FROM postings').fetchone()['total']==0
