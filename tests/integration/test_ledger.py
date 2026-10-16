from decimal import Decimal as D
from polyquant.types import OrderIntent,ExecutionResult,Fill

def test_atomic_fill_is_balanced_and_idempotent(store):
    order=OrderIntent('one','probability','fixture','BUY_UP',D('4'),D('0.50'))
    assert store.reserve(order,D('2.10'))
    assert store.state('probability').reserved==D('2.10')
    result=ExecutionResult((Fill(D('0.50'),D('4'),D('0.07')),),'FILLED','', 'book-1')
    store.commit_execution('one',result)
    store.commit_execution('one',result)
    state=store.state('probability')
    assert state.cash==D('997.93') and state.reserved==0
    assert len(state.positions)==1
    assert store.state('momentum').cash==D('1000')
    with store.connect() as c:
        assert c.execute('SELECT SUM(amount) AS total FROM postings').fetchone()['total']==0

def test_cancel_and_restart_release_reservations(store):
    from polyquant.store import Store
    order=OrderIntent('pending','probability','fixture','BUY_UP',D('2'),D('0.50'))
    store.reserve(order,D('1.10'))
    restored=Store(store.dsn)
    assert restored.state('probability').reserved==D('1.10')
    restored.reconcile()
    assert restored.state('probability').reserved==0
    assert restored.state('probability').cash==D('1000')

def test_insufficient_capital_rolls_back(store):
    order=OrderIntent('large','probability','fixture','BUY_UP',D('3000'),D('0.50'))
    assert not store.reserve(order,D('1500'))
    assert store.state('probability').reserved==0

def test_halt_cancels_pending_and_survives_reconnect(store):
    from polyquant.store import Store
    store.reserve(OrderIntent('p','probability','fixture','BUY_UP',D('2'),D('0.5')),D('1.1'))
    store.halt('probability','MANUAL_STOP')
    assert Store(store.dsn).state('probability').halts==('MANUAL_STOP',)
    assert store.state('probability').reserved==0

def test_single_writer_lock(store):
    from polyquant.store import Store
    other=Store(store.dsn)
    assert store.acquire_writer()
    assert not other.acquire_writer()
    store.close()
    assert other.acquire_writer()
    other.close()
