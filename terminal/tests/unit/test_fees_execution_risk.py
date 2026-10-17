from datetime import timedelta,datetime,timezone
from decimal import Decimal as D
import pytest
from polyquant.types import MarketTerms,BookSnapshot,ReferenceSnapshot,AccountState,OrderIntent,ExperimentConfig,utcnow

def context():
    now=utcnow()
    market=MarketTerms('fixture','fixture','15m',now-timedelta(minutes=5),now+timedelta(minutes=10),D('80000'),status='MARKET_STATUS_OPEN')
    book=BookSnapshot('fixture',((D('.49'),D('20')),),((D('.50'),D('2')),(D('.55'),D('3'))),now,now,'book1')
    ref=ReferenceSnapshot(D('80050'),now,now,True,reason='')
    return now,market,book,ref

def test_fee_rounding_and_effective_dates():
    from polyquant.fees import FeeModel
    from polyquant.types import Fill
    model=FeeModel()
    assert model.fees((Fill(D('.50'),D('100')),),utcnow())==[D('1.74')]
    assert model.round(D('.025'))==D('.02') and model.round(D('.035'))==D('.04')
    fills=tuple(Fill(D('.50'),D('1')) for _ in range(10))
    charges=model.fees(fills,utcnow())
    assert sum(charges)<=D('.17')
    assert model.maker_coefficient(datetime(2026,10,19,16,59,tzinfo=timezone.utc))==D('-.0125')
    assert model.maker_coefficient(datetime(2026,10,19,17,0,tzinfo=timezone.utc))==0
    with pytest.raises(ValueError): model.fees(fills,datetime(2025,1,1,tzinfo=timezone.utc))

def test_sweep_depth_limit_and_maker_nonfill():
    from polyquant.execution import sweep
    now,market,book,ref=context()
    order=OrderIntent('fixture','probability','fixture','BUY_UP',D('4'),D('.60'),probability=D('.9'),scenario='optimistic')
    result=sweep(order,book,market.tick,now)
    assert result.qty==4 and result.vwap==D('.525')
    tight=OrderIntent('tight','probability','fixture','BUY_UP',D('4'),D('.52'),scenario='optimistic')
    result=sweep(tight,book,market.tick,now)
    assert result.qty==2 and result.status=='PARTIALLY_FILLED_AND_CANCELED'
    assert sweep(order,book,market.tick,now,passive=True).qty==0

def test_risk_reference_stale_fee_budget_and_daily_loss():
    from polyquant.risk import RiskManager
    now,market,book,ref=context(); risk=RiskManager(); cfg=ExperimentConfig()
    order=OrderIntent('one','probability','fixture','BUY_UP',D('4'),D('.60'),probability=D('.9'))
    assert risk.evaluate(order,AccountState('probability'),market,book,ref,cfg,now).allowed
    assert 'REFERENCE_RECONCILIATION_FAILED' in risk.evaluate(order,AccountState('probability'),market,book,ReferenceSnapshot(),cfg,now).reasons
    assert 'STALE_BOOK' in risk.evaluate(order,AccountState('probability'),market,book,ref,cfg,now+timedelta(seconds=3)).reasons
    big=OrderIntent('big','probability','fixture','BUY_UP',D('10'),D('.50'),probability=D('.9'))
    assert 'PER_TRADE_LOSS_LIMIT' in risk.evaluate(big,AccountState('probability'),market,book,ref,cfg,now).reasons
    assert 'DAILY_LOSS_LIMIT' in risk.evaluate(order,AccountState('probability',cash=D('980'),equity=D('980')),market,book,ref,cfg,now).reasons

def test_down_mapping_and_stress_do_not_fill_above_limit():
    from polyquant.execution import sweep
    now,market,book,ref=context()
    # Buying DOWN consumes the complement of YES bids, not YES offers.
    order=OrderIntent('down','book','fixture','BUY_DOWN',D('2'),D('.51'),scenario='optimistic')
    result=sweep(order,book,market.tick,now)
    assert result.qty==2 and result.vwap==D('.51')
    order=OrderIntent('stress','book','fixture','BUY_UP',D('2'),D('.50'),scenario='stress')
    assert sweep(order,book,market.tick,now).qty==0
