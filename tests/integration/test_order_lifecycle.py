from decimal import Decimal as D
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from polyquant.types import OrderIntent,ReferenceSnapshot
from test_fees_execution_risk import context

def test_arrival_rechecks_reference_and_releases_capital(store):
    from polyquant.execution import PaperExecutionEngine
    now,market,book,ref=context()
    current=[ref]
    engine=PaperExecutionEngine(store,{market.id:market},{market.id:book},lambda:current[0])
    order=OrderIntent('arrival','probability',market.id,'BUY_UP',D('2'),D('.5'),probability=D('.9'),scenario='base')
    assert engine.submit(order).allowed
    current[0]=ReferenceSnapshot()
    engine.process_due(now+timedelta(seconds=1))
    assert store.state('probability').cash==D('1000')
    assert not store.state('probability').positions
    assert store.state('probability').reserved==0

def test_concurrent_reservations_enforce_cadence_slot(store):
    from polyquant.execution import PaperExecutionEngine
    now,market,book,ref=context()
    second=replace(market,id='other',slug='other')
    second_book=replace(book,market_id='other')
    engine=PaperExecutionEngine(store,{market.id:market,second.id:second},{market.id:book,second.id:second_book},lambda:ref)
    orders=[OrderIntent('concurrent-'+m.id,'probability',m.id,'BUY_UP',D('2'),D('.5'),probability=D('.9')) for m in [market,second]]
    with ThreadPoolExecutor(max_workers=2) as pool: decisions=list(pool.map(engine.submit,orders))
    assert sum(d.allowed for d in decisions)==1
    assert len(store.state('probability').pending)==1
