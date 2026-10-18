from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from polyquant.strategies import book as module
from polyquant.types import AccountState,OrderIntent,ReferenceSnapshot,ExperimentConfig
from polyquant.risk import RiskManager
from test_fees_execution_risk import context


def test_book_signal_requires_distinct_fresh_sustained_observations():
    assert hasattr(module,'ExperimentalBookStrategy'),'Experimental automated strategy is missing'
    strategy=module.ExperimentalBookStrategy();at,market,book,_=context()
    for i in range(3):
        now=at+timedelta(seconds=i*5)
        current=replace(book,source_at=now,received_at=now,version=str(i))
        result=strategy.observe(current,now)
        assert result['action']==('BUY_UP' if i==2 else 'NO_TRADE')
    assert result['probability'] is None and result['validated'] is False
    assert len(result['observations'])==3
    down=replace(book,market_id='hourly',bids=((D('.49'),D('2')),),asks=((D('.50'),D('20')),))
    for i in range(3):
        now=at+timedelta(seconds=i*5)
        result=strategy.observe(replace(down,source_at=now,received_at=now,version='d'+str(i)),now)
    assert result['action']=='BUY_DOWN'


def test_duplicate_source_stale_gap_and_neutral_reset_signal():
    assert hasattr(module,'ExperimentalBookStrategy'),'Experimental automated strategy is missing'
    strategy=module.ExperimentalBookStrategy();at,_,book,_=context()
    assert strategy.observe(book,at)['action']=='NO_TRADE'
    assert strategy.observe(replace(book,version='same-source'),at)['action']=='NO_TRADE'
    assert len(strategy.history[book.market_id])==1
    assert 'STALE_BOOK' in strategy.observe(book,at+timedelta(seconds=4))['reasons']
    for i in range(2):
        now=at+timedelta(seconds=10+i*5)
        assert strategy.observe(replace(book,source_at=now,received_at=now,version=str(i)),now)['action']=='NO_TRADE'
    neutral=replace(book,bids=((D('.49'),D('5')),),asks=((D('.50'),D('5')),))
    now=at+timedelta(seconds=20)
    assert 'IMBALANCE_BELOW_THRESHOLD' in strategy.observe(replace(neutral,source_at=now,received_at=now,version='neutral'),now)['reasons']
    now=at+timedelta(seconds=25)
    assert strategy.observe(replace(book,source_at=now,received_at=now,version='new'),now)['action']=='NO_TRADE'


def test_experiment_exception_is_exact_pair_and_keeps_hard_risk():
    at,market,book,_=context();risk=RiskManager()
    intent=OrderIntent('bot-fixture','book_experiment',market.id,'BUY_UP',D('1'),D('.51'),'book-imbalance-experiment-v1')
    decision=risk.evaluate(intent,AccountState('book_experiment'),market,book,ReferenceSnapshot(),ExperimentConfig(),at)
    assert decision.allowed,decision.reasons
    for spoof in [replace(intent,account_id='probability'),replace(intent,strategy='manual_discretionary'),replace(intent,account_id='book')]:
        assert 'REFERENCE_RECONCILIATION_FAILED' in risk.evaluate(spoof,AccountState(spoof.account_id),market,book,ReferenceSnapshot(),ExperimentConfig(),at).reasons
    assert 'PER_TRADE_LOSS_LIMIT' in risk.evaluate(replace(intent,qty=D('100')),AccountState('book_experiment'),market,book,ReferenceSnapshot(),ExperimentConfig(),at).reasons
    assert 'DAILY_LOSS_LIMIT' in risk.evaluate(intent,AccountState('book_experiment',cash=D('980'),equity=D('980')),market,book,ReferenceSnapshot(),ExperimentConfig(),at).reasons
