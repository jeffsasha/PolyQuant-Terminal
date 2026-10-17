import asyncio
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from test_manual_api import paper_client
from polyquant.types import utcnow
from test_fees_execution_risk import context


def test_aggressive_run_sizes_both_cadences_and_preserves_original_account(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    response=c.post('/bot/run',headers=headers,json={'account_id':'book_aggressive'})
    assert response.status_code==200,response.json()
    hourly=replace(market,id='aggressive-hourly',slug='aggressive-hourly',horizon='1h',end=utcnow()+timedelta(minutes=40))
    r.markets[hourly.id]=hourly
    _,_,book,_=context()
    async def deep_source(terms,fresh=False):
        at=utcnow()
        return replace(book,market_id=terms.id,bids=((D('.49'),D('10000')),),asks=((D('.50'),D('5000')),),source_at=at,received_at=at,version=at.isoformat()),{'fixture':'deep-book'}
    r.venue.book=deep_source
    async def tick():
        for values in r.book_strategy.history.values():
            for i,value in enumerate(values):value['received_at']-=timedelta(seconds=5*(len(values)-i))
        await r.bot_tick()
    for _ in range(3):c.portal.call(tick)
    orders=[o for o in store.history('orders') if o['account_id']=='book_aggressive']
    assert {o['horizon'] for o in orders}=={'15m','1h'}
    assert all(o['qty']>100 and o['strategy']=='book-imbalance-aggressive-v2' for o in orders)
    assert sum(o['reserved'] for o in orders)<=700
    assert store.state('book_experiment').cash==1000 and not store.state('book_experiment').pending
    c.portal.call(asyncio.sleep,1.1);c.portal.call(r.process_arrivals_once)
    assert all(store.get_order(o['id'])['status']=='FILLED' for o in orders)
    assert len(store.state('book_aggressive').positions)==2
    state=c.get('/state').json();assert state['bot']['config']['target_allocation']=='0.70'
    assert state['bot']['risk']['exposure_limit']=='0.80'
    assert c.post('/bot/run',headers=headers,json={'account_id':'book_experiment'}).status_code==409
    c.post('/bot/stop',headers=headers,json={})
    assert len(store.state('book_aggressive').positions)==2
    assert c.post('/paper/orders',headers=headers,json={'id':'aggr-manual-spoof','account_id':'book_aggressive','market_id':market.id,'side':'BUY_UP','qty':'1','limit':'0.51'}).status_code==403


def test_aggressive_equity_uses_liquidation_depth_and_fees_not_zero_or_midpoint(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    assert hasattr(r.engine,'account_state'),'Execution-side portfolio valuation is missing'
    with store.connect() as db:
        db.execute("UPDATE accounts SET cash=650 WHERE id='book_aggressive'")
        db.execute("INSERT INTO positions(account_id,market_id,direction,qty,cost,fees,horizon) VALUES('book_aggressive',%s,'UP',100,340,10,'15m')",(market.id,))
    _,_,book,_=context();at=utcnow()
    r.books[market.id]=replace(book,bids=((D('.49'),D('1000')),),source_at=at,received_at=at)
    state=r.engine.account_state('book_aggressive')
    assert D('695')<state.equity<D('698')  # $650 cash + conservative net liquidation, never mid.
    r.books[market.id]=replace(r.books[market.id],bids=((D('.49'),D('2')),))
    assert r.engine.account_state('book_aggressive').equity==650  # Cannot prove a full liquidation.


def test_missing_portfolio_depth_blocks_without_inventing_a_daily_loss_lock(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    assert hasattr(r.engine,'account_state'),'Execution-side portfolio valuation is missing'
    with store.connect() as db:
        db.execute("UPDATE accounts SET cash=650 WHERE id='book_aggressive'")
        db.execute("INSERT INTO positions(account_id,market_id,direction,qty,cost,fees,horizon) VALUES('book_aggressive',%s,'UP',600,340,10,'15m')",(market.id,))
    _,_,book,_=context();r.books[market.id]=book
    account=r.engine.account_state('book_aggressive')
    assert hasattr(account,'valuation_ready'),'Missing valuation must be distinguished from an actual drawdown'
    assert not account.valuation_ready
    from polyquant.types import OrderIntent,ReferenceSnapshot
    from polyquant.risk import RiskManager,config_for
    hourly=replace(market,id='new-hourly',horizon='1h',end=utcnow()+timedelta(minutes=40))
    intent=OrderIntent('no-invented-loss','book_aggressive',hourly.id,'BUY_UP',D('1'),D('.51'),'book-imbalance-aggressive-v2')
    result=RiskManager().evaluate(intent,account,hourly,book,ReferenceSnapshot(),config_for(intent.account_id,intent.strategy),utcnow())
    assert 'PORTFOLIO_VALUATION_UNAVAILABLE' in result.reasons
    assert 'DAILY_LOSS_LIMIT' not in result.reasons


def test_snapshot_values_same_market_separately_for_each_account_size(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    with store.connect() as db:
        db.execute("UPDATE accounts SET cash=500 WHERE id='book_aggressive'")
        db.execute("INSERT INTO positions(account_id,market_id,direction,qty,cost,fees,horizon) VALUES('book_aggressive',%s,'UP',1000,490,10,'15m')",(market.id,))
        db.execute("UPDATE accounts SET cash=999.49 WHERE id='book_experiment'")
        db.execute("INSERT INTO positions(account_id,market_id,direction,qty,cost,fees,horizon) VALUES('book_experiment',%s,'UP',1,0.49,0.02,'15m')",(market.id,))
    _,_,book,_=context();r.books[market.id]=book
    accounts={a['id']:a for a in c.get('/state').json()['accounts']}
    assert D(accounts['book_aggressive']['equity'])==500,'A small account mark must not value a larger unliquidatable position'
    assert D(accounts['book_experiment']['equity'])>999.49


def test_unavailable_rollover_keeps_baseline_blocks_then_carries_it_forward(store,paper_client,monkeypatch):
    from datetime import datetime,timezone
    import polyquant.store as module
    from polyquant.clock import risk_day_id
    from polyquant.risk import RiskManager,config_for
    from polyquant.types import OrderIntent,ReferenceSnapshot
    c,headers,instances,market=paper_client
    day=datetime(2026,10,18,22,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'utcnow',lambda:day)
    with store.connect() as db:
        db.execute("UPDATE accounts SET cash=650,day_start=1000,day_id=%s WHERE id='book_aggressive'",(risk_day_id(day-timedelta(days=1)),))
        db.execute("INSERT INTO positions(account_id,market_id,direction,qty,cost,fees,horizon) VALUES('book_aggressive',%s,'UP',600,340,10,'15m')",(market.id,))
    store.roll_days(per_account_marks={'book_aggressive':{}})
    account=store.state('book_aggressive')
    assert account.day_start_equity==1000,'Unavailable marks must never overwrite baseline with cash-only equity'
    assert hasattr(account,'risk_day_ready') and not account.risk_day_ready
    assert c.post('/bot/run',headers=headers,json={'account_id':'book_aggressive'}).status_code==409
    # The first reliable mark next day proves only $750 equity. Preserve the previous $1,000 baseline.
    store.roll_days(per_account_marks={'book_aggressive':{(market.id,'UP'):D('100')/D('600')}})
    account=store.state('book_aggressive',{(market.id,'UP'):D('100')/D('600')})
    assert account.risk_day_ready and account.day_start_equity==1000 and account.equity==750
    _,_,book,_=context();hourly=replace(market,id='baseline-hourly',horizon='1h',end=utcnow()+timedelta(minutes=40))
    intent=OrderIntent('baseline-risk','book_aggressive',hourly.id,'BUY_UP',D('1'),D('.51'),'book-imbalance-aggressive-v2')
    decision=RiskManager().evaluate(intent,account,hourly,book,ReferenceSnapshot(),config_for(intent.account_id,intent.strategy),utcnow())
    assert 'DAILY_LOSS_LIMIT' in decision.reasons


def test_stop_run_profile_switch_discards_inflight_previous_profile_read(store,paper_client):
    c,headers,instances,market=paper_client;r=instances[0]
    c.post('/bot/run',headers=headers,json={'account_id':'book_experiment'})
    source=r.capture_book
    async def switched(identity):
        book=await source(identity)
        r.stop_bot();r.run_bot('book_aggressive')
        return book
    r.capture_book=switched
    c.portal.call(r.bot_tick)
    assert r.book_strategy.history=={} and r.bot_signals=={},'The stopped generation must not warm the newly armed profile'
