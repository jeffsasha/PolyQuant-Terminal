from dataclasses import replace
from decimal import Decimal as D
from datetime import timedelta
from polyquant.types import OrderIntent,AccountState,ReferenceSnapshot,ExperimentConfig
from polyquant.risk import RiskManager
from test_fees_execution_risk import context


def test_discretionary_account_does_not_require_an_unfitted_probability():
    now,market,book,_=context()
    intent=OrderIntent('manual-paper','manual',market.id,'BUY_UP',D('1'),D('.52'),'manual_discretionary')
    result=RiskManager().evaluate(intent,AccountState('manual'),market,book,ReferenceSnapshot(),ExperimentConfig(),now)
    assert result.allowed,result.reasons


def test_discretionary_cannot_bypass_actual_safety_or_strategy_gates():
    now,market,book,_=context();risk=RiskManager();config=ExperimentConfig()
    intent=OrderIntent('manual-paper','manual',market.id,'BUY_UP',D('1'),D('.52'),'manual_discretionary')
    assert 'STALE_BOOK' in risk.evaluate(intent,AccountState('manual'),market,book,ReferenceSnapshot(),config,now+timedelta(seconds=3)).reasons
    assert 'PER_TRADE_LOSS_LIMIT' in risk.evaluate(replace(intent,qty=D('20')),AccountState('manual'),market,book,ReferenceSnapshot(),config,now).reasons
    automatic=replace(intent,account_id='probability',strategy='probability')
    assert 'REFERENCE_RECONCILIATION_FAILED' in risk.evaluate(automatic,AccountState('probability'),market,book,ReferenceSnapshot(),config,now).reasons
    spoof=replace(intent,account_id='probability')
    assert 'REFERENCE_RECONCILIATION_FAILED' in risk.evaluate(spoof,AccountState('probability'),market,book,ReferenceSnapshot(),config,now).reasons
