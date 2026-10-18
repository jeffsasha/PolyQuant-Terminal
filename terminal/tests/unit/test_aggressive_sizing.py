from dataclasses import replace
from decimal import Decimal as D
from polyquant import risk as module
from polyquant.types import AccountState,OrderIntent,ReferenceSnapshot
from test_fees_execution_risk import context


def test_aggressive_profile_is_isolated_and_exact_strategy_pair():
    assert hasattr(module,'config_for'),'Per-account risk profiles are missing'
    cfg=module.config_for('book_aggressive','book-imbalance-aggressive-v2')
    assert cfg.exposure_limit==D('.80') and cfg.risk_per_trade==D('.40') and cfg.cadence_limit==D('.40')
    assert cfg.daily_loss==D('.20')
    assert module.config_for('book_experiment','book-imbalance-experiment-v1').risk_per_trade==D('.005')
    assert module.config_for('manual','book-imbalance-aggressive-v2').exposure_limit==D('.05')
    assert module.config_for('book_aggressive','manual_discretionary').exposure_limit==D('.05')


def test_sizer_scales_with_equity_includes_fees_and_never_rounds_above_budget():
    assert hasattr(module,'size_aggressive'),'Adaptive quantity sizing is missing'
    at,market,book,_=context();deep=replace(book,bids=((D('.49'),D('5000')),),asks=((D('.50'),D('5000')),))
    account=AccountState('book_aggressive')
    small=module.size_aggressive(account,market,deep,'BUY_UP',D('.51'))
    large=module.size_aggressive(replace(account,cash=D('2000'),equity=D('2000')),market,deep,'BUY_UP',D('.51'))
    assert small['qty']>1 and large['qty']>small['qty']
    assert small['maximum_cost']<=D('350') and large['maximum_cost']<=D('700')
    assert small['qty']%market.minimum_qty==0
    from polyquant.fees import FeeModel
    extra=small['qty']+market.minimum_qty
    assert extra*D('.51')+FeeModel().reserve_fee(extra)>D('350')


def test_sizer_counts_pending_and_paid_fees_and_limits_visible_depth():
    assert hasattr(module,'size_aggressive'),'Adaptive quantity sizing is missing'
    _,market,book,_=context()
    sized=module.size_aggressive(AccountState('book_aggressive'),market,book,'BUY_UP',D('.51'))
    assert sized['qty']<=D('1')  # Half of two displayed contracts at executable price.
    deep=replace(book,asks=((D('.50'),D('5000')),))
    held={'market_id':'hourly','horizon':'1h','cost':D('650'),'fees':D('40')}
    account=AccountState('book_aggressive',positions=(held,))
    sized=module.size_aggressive(account,market,deep,'BUY_UP',D('.51'))
    assert sized['maximum_cost']<=D('10')  # 70% target minus cost AND fees.
    pending={'market_id':'pending-hourly','horizon':'1h','reserved':D('690')}
    pending_size=module.size_aggressive(replace(account,positions=(),pending=(pending,),reserved=D('690')),market,deep,'BUY_UP',D('.51'))
    assert pending_size['maximum_cost']<=D('10')
    tiny=module.size_aggressive(replace(account,cash=D('.001')),market,deep,'BUY_UP',D('.51'))
    assert tiny['qty']==0 and tiny['reasons']


def test_aggressive_hard_cap_cannot_be_bypassed_and_conservative_unchanged():
    assert hasattr(module,'config_for'),'Per-account risk profiles are missing'
    at,market,book,_=context();risk=module.RiskManager();cfg=module.config_for('book_aggressive','book-imbalance-aggressive-v2')
    intent=OrderIntent('aggressive-fixture','book_aggressive',market.id,'BUY_UP',D('600'),D('.51'),'book-imbalance-aggressive-v2')
    assert risk.evaluate(intent,AccountState('book_aggressive'),market,book,ReferenceSnapshot(),cfg,at).allowed
    assert 'PER_TRADE_LOSS_LIMIT' in risk.evaluate(replace(intent,qty=D('1000')),AccountState('book_aggressive'),market,book,ReferenceSnapshot(),cfg,at).reasons
    held={'market_id':'other','horizon':'1h','cost':D('750'),'fees':D('49')}
    small=replace(intent,qty=D('2'))
    result=risk.evaluate(small,AccountState('book_aggressive',positions=(held,)),market,book,ReferenceSnapshot(),cfg,at)
    assert 'COMBINED_EXPOSURE_LIMIT' in result.reasons
    spoof=replace(intent,account_id='probability')
    assert 'REFERENCE_RECONCILIATION_FAILED' in risk.evaluate(spoof,AccountState('probability'),market,book,ReferenceSnapshot(),module.config_for(spoof.account_id,spoof.strategy),at).reasons
