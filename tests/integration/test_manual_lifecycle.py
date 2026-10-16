from dataclasses import replace
from decimal import Decimal as D
from datetime import timedelta
from polyquant.types import OrderIntent,ReferenceSnapshot,ExecutionResult,Fill
from polyquant.execution import PaperExecutionEngine
from polyquant.clock import ReplayClock
from test_fees_execution_risk import context


def test_manual_buy_sell_rebuy_uses_real_arrival_levels_and_frees_slot(store):
    now,market,book,_=context();clock=ReplayClock(now)
    engine=PaperExecutionEngine(store,{market.id:market},{market.id:book},lambda:ReferenceSnapshot(),clock)
    buy=OrderIntent('manual-buy-1','manual',market.id,'BUY_UP',D('1'),D('.52'),'manual_discretionary',scenario='base')
    assert engine.submit(buy).allowed
    clock.advance(now+timedelta(seconds=1));engine.books[market.id]=replace(book,source_at=clock.now(),received_at=clock.now(),version='arrival-buy');engine.process_due()
    position=store.state('manual').positions[0]
    assert position['qty']==1 and position['cost']==D('.50')
    sell=replace(buy,id='manual-sell-1',side='SELL_UP',limit=D('.48'))
    assert engine.submit(sell).allowed
    clock.advance(now+timedelta(seconds=2));engine.books[market.id]=replace(book,source_at=clock.now(),received_at=clock.now(),version='arrival-sell');engine.process_due()
    assert not store.state('manual').positions
    # A genuinely new capture at the new time, not pretending the old book stayed fresh.
    engine.books[market.id]=replace(book,source_at=clock.now(),received_at=clock.now(),version='book2')
    assert engine.submit(replace(buy,id='manual-buy-2')).allowed
    assert store.state('probability').cash==1000
    with store.connect() as c: assert c.execute('SELECT SUM(amount) AS total FROM postings').fetchone()['total']==0


def test_partial_sale_allocates_remaining_entry_fees_and_does_not_sell_twice(store):
    buy=OrderIntent('basis-buy','manual','fixture','BUY_UP',D('4'),D('.5'),'manual_discretionary')
    assert store.reserve(buy,D('2.1'))
    store.commit_execution(buy.id,ExecutionResult((Fill(D('.5'),D('4'),D('.08')),),'FILLED'))
    sell=replace(buy,id='basis-sell',side='SELL_UP',qty=D('2'),limit=D('.6'))
    assert store.reserve(sell,D('.04'))
    store.commit_execution(sell.id,ExecutionResult((Fill(D('.6'),D('2'),D('.03')),),'FILLED'))
    position=store.state('manual').positions[0]
    assert position['qty']==2 and position['cost']==1 and position['fees']==D('.04')

def test_arrival_cannot_consume_a_snapshot_captured_before_arrival(store):
    now,market,book,ref=context();clock=ReplayClock(now)
    engine=PaperExecutionEngine(store,{market.id:market},{market.id:book},lambda:ref,clock)
    order=OrderIntent('signal-book-is-not-arrival','probability',market.id,'BUY_UP',D('1'),D('.52'),probability=D('.9'),scenario='base')
    assert engine.submit(order).allowed
    clock.advance(now+timedelta(seconds=1));engine.process_due()
    assert not store.state('probability').positions
    assert store.get_order(order.id)['reason']=='ARRIVAL_BOOK_NOT_OBSERVED'
