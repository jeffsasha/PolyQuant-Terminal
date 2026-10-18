import asyncio
from dataclasses import replace
from datetime import timedelta
from test_manual_api import paper_client
from polyquant.types import utcnow


def test_run_stop_both_cadences_and_no_duplicate_orders(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    assert c.post('/bot/run',headers=headers,json={'account_id':'book_experiment'}).status_code==200
    hourly=replace(market,id='fixture-1h',slug='fixture-1h',horizon='1h',end=utcnow()+timedelta(minutes=40))
    r.markets[hourly.id]=hourly
    async def tick():
        for values in r.book_strategy.history.values():
            for i,value in enumerate(values): value['received_at']-=timedelta(seconds=5*(len(values)-i))
        await r.bot_tick()
    for _ in range(3):c.portal.call(tick)
    orders=[o for o in store.history('orders') if o['account_id']=='book_experiment']
    assert {o['horizon'] for o in orders}=={'15m','1h'}
    assert all(o['strategy']=='book-imbalance-experiment-v1' and o['scenario']=='conservative' for o in orders)
    for _ in range(3):c.portal.call(tick)
    assert len([o for o in store.history('orders') if o['account_id']=='book_experiment'])==2
    assert c.post('/bot/stop',headers=headers,json={}).status_code==200
    assert not r.bot_enabled and all(store.get_order(o['id'])['status']=='CANCELED' for o in orders)
    assert store.state('book_experiment').reserved==0
    c.portal.call(tick)
    assert len([o for o in store.history('orders') if o['account_id']=='book_experiment'])==2
    assert c.get('/state').json()['bot']['status']=='STOPPED'


def test_bot_stop_during_source_read_and_daily_lock_cannot_be_bypassed(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    assert c.post('/bot/run',headers=headers,json={'account_id':'book_experiment'}).status_code==200
    original=r.capture_book
    async def stopping_read(identity):
        book=await original(identity);r.stop_bot();return book
    r.capture_book=stopping_read
    c.portal.call(r.bot_tick)
    assert not store.history('orders') and not r.bot_enabled
    store.halt('book_experiment','DAILY_LOSS_LIMIT')
    assert c.post('/bot/run',headers=headers,json={'account_id':'book_experiment'}).status_code==409
    assert not r.bot_enabled
    payload={'id':'manual-bot-spoof','account_id':'book_experiment','market_id':market.id,'side':'BUY_UP','qty':'1','limit':'0.51'}
    assert c.post('/paper/orders',headers=headers,json=payload).status_code in (403,422)
    assert c.post('/bot/run',headers={'Origin':'http://127.0.0.1:3000'},json={}).status_code==403


def test_automatic_arrivals_fill_and_stop_retains_holdings(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    c.post('/bot/run',headers=headers,json={'account_id':'book_experiment'})
    async def tick():
        for values in r.book_strategy.history.values():
            for i,value in enumerate(values):value['received_at']-=timedelta(seconds=5*(len(values)-i))
        await r.bot_tick()
    for _ in range(3):c.portal.call(tick)
    orders=store.history('orders');assert len(orders)==1
    c.portal.call(asyncio.sleep,1.1)
    c.portal.call(r.process_arrivals_once)
    assert store.get_order(orders[0]['id'])['status']=='FILLED'
    assert store.state('book_experiment').positions
    c.post('/bot/stop',headers=headers,json={})
    assert store.state('book_experiment').positions
    assert store.state('manual').cash==1000 and not store.state('manual').positions


def test_run_failure_cannot_arm_and_emergency_stop_covers_other_account(store,paper_client,monkeypatch):
    c,headers,instances,_=paper_client;r=instances[0]
    original=store.audit
    def broken(action,*args,**kwargs):
        if action=='EXPERIMENTAL_BOT_RUN':raise OSError('fixture audit failure')
        return original(action,*args,**kwargs)
    monkeypatch.setattr(store,'audit',broken)
    try:r.run_bot('book_experiment')
    except OSError:pass
    assert not r.bot_enabled,'RUN must not arm before successful audit persistence'
    monkeypatch.setattr(store,'audit',original)
    assert c.post('/bot/run',headers=headers,json={'account_id':'book_experiment'}).status_code==200
    assert c.post('/paper/stop',headers=headers,json={'account_id':'manual'}).status_code==200
    assert not r.bot_enabled and store.state('book_experiment').halts
