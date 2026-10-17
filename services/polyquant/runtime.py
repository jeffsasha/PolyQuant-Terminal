import asyncio,contextlib,time,uuid,math
from .venue.transport import RateLimitCooldown
from datetime import timedelta
from collections import deque
from decimal import Decimal as D
from .types import utcnow,jsonable,MarketEvent,ExperimentConfig,ReferenceSnapshot,ACCOUNT_IDS,MarketTerms,OrderIntent,BOT_ACCOUNT
from .venue.us import USDataAdapter
from .reference import ReferenceProvider,SpotProvider
from .recorder import Recorder,StorageHalt
from .execution import PaperExecutionEngine,sweep
from .settlement import SettlementProvider
from .strategies.probability import ProbabilityStrategy
from .strategies.momentum import MomentumStrategy
from .strategies.book import BookStrategy,ExperimentalBookStrategy


class Runtime:
    def __init__(self,store,settings):
        self.store=store; self.settings=settings; self.venue=USDataAdapter()
        self.reference_provider=ReferenceProvider(self.venue.transport); self.spot_provider=SpotProvider()
        self.reference=ReferenceSnapshot(); self.spot=None; self.markets={}; self.books={}
        self.recorder=Recorder(settings.data_dir/'raw',quota=settings.raw_quota)
        self.engine=PaperExecutionEngine(store,self.markets,self.books,lambda:self.reference)
        self.events=deque(maxlen=2000); self.sequence=0; self.connection_epoch=str(uuid.uuid4())
        self.errors={}; self.tasks=[]; self.running=True; self.collection=True; self.latency_ms=None
        self.last_discovery=None; self.last_update=None; self.strategies=[ProbabilityStrategy(),MomentumStrategy(),BookStrategy()]
        self.book_locks={}; self.command_locks={}; self.settlement_checks={}; self.settlement=SettlementProvider(self.venue.transport,store)
        self.bot_enabled=False; self.book_strategy=ExperimentalBookStrategy(); self.bot_signals={}
        self.bot_tick_lock=asyncio.Lock()
        self.started_at=utcnow(); self.stream_status='NOT_CONFIGURED'; self.last_stream=None; self.gaps=0
    def event(self,kind,payload,market_id=None,source_at=None):
        self.sequence+=1; at=utcnow()
        event=MarketEvent(str(uuid.uuid4()),market_id,kind,source_at,at,at,self.sequence,payload)
        try:
            self.recorder.append(event)
            if self.recorder.events>=60: self.store.save_manifest(self.recorder.seal())
        except (StorageHalt,OSError) as error:
            reason='STORAGE_LIMIT' if isinstance(error,StorageHalt) else 'PERSISTENCE_FAILED'
            self.persistence_halt(reason)
            raise StorageHalt(reason) from None
        except Exception:
            self.persistence_halt('PERSISTENCE_FAILED')
            raise StorageHalt('PERSISTENCE_FAILED') from None
        self.events.append(event); self.last_update=at
        return event
    def persistence_halt(self,reason):
        self.collection=False; self.recorder.halted=True; self.errors['recorder']=reason
        for name in ACCOUNT_IDS:
            try: self.store.halt(name,reason)
            except Exception: self.errors['database']='PERSISTENCE_FAILED'
    async def start(self):
        if not self.store.acquire_writer(): raise RuntimeError('Another trading writer owns this database')
        try:
            for manifest in self.recorder.recover(): self.store.save_manifest(manifest)
            if self.recorder.recovery_errors: self.persistence_halt('PERSISTENCE_FAILED')
        except Exception: self.persistence_halt('PERSISTENCE_FAILED')
        self.store.reconcile(); self.stop_bot('RESTART_REQUIRES_RUN'); self.store.audit('RUNTIME_STARTED',payload={'mode':'PAPER','reference_validated':False})
        for row in self.store.held_instruments():
            market=MarketTerms.from_raw(row['raw']); self.markets[market.id]=market
        self.tasks=[asyncio.create_task(loop()) for loop in [self.data_loop,self.book_loop,self.execution_loop,self.settlement_loop,self.strategy_loop,self.bot_loop,self.stream_loop]]
    async def close(self):
        self.running=False
        for task in self.tasks: task.cancel()
        for task in self.tasks:
            with contextlib.suppress(asyncio.CancelledError): await task
        try: self.store.save_manifest(self.recorder.seal())
        except Exception: self.persistence_halt('PERSISTENCE_FAILED')
        finally:
            await self.venue.close(); await self.spot_provider.close(); self.store.close()
    async def data_loop(self):
        while self.running:
            if not self.collection: await asyncio.sleep(5); continue
            try:
                if not self.last_discovery or (utcnow()-self.last_discovery).total_seconds()>45:
                    found=await self.venue.discover()
                    for market in found:
                        self.event('instrument',market.raw,market.id)
                        self.store.save_instrument(market); self.markets[market.id]=market
                    # Retain ended instruments only while a holding needs settlement.
                    held={p['market_id'] for name in ACCOUNT_IDS for p in self.store.state(name).positions}
                    for identity in list(self.markets):
                        if self.markets[identity].end<utcnow() and identity not in held:
                            self.markets.pop(identity,None); self.books.pop(identity,None)
                            self.errors.pop('book:'+identity,None)
                    self.last_discovery=utcnow(); self.errors.pop('discovery',None)
                try:
                    ref=await self.reference_provider.latest()
                    self.event('index',jsonable(ref),source_at=ref.source_at); self.reference=ref; self.errors.pop('index',None)
                except Exception as error: self.errors['index']=type(error).__name__
                try:
                    spot=await self.spot_provider.latest(); self.event('spot',spot); self.spot=spot; self.errors.pop('spot',None)
                except Exception as error: self.errors['spot']=type(error).__name__
                self.store.roll_days(self.marks())
            except StorageHalt: pass
            except Exception as error:
                self.errors['discovery']=type(error).__name__; self.gaps+=1
            await asyncio.sleep(10)
    async def capture_book(self,identity):
        if not self.collection: raise StorageHalt('Collection is halted')
        market=self.markets.get(identity)
        if not market: raise ValueError('Market not discovered')
        async with self.book_locks.setdefault(identity,asyncio.Lock()):
            started=time.monotonic()
            book,raw=await self.venue.book(market,fresh=True)
            self.event('book',raw,identity,book.source_at)
            previous=self.books.get(identity)
            if not previous or (book.source_at and (not previous.source_at or book.source_at>=previous.source_at)):
                self.books[identity]=book
            self.latency_ms=round((time.monotonic()-started)*1000,1)
            self.errors.pop('book:'+identity,None)
            return self.books.get(identity,book)
    async def book_loop(self):
        while self.running:
            if self.collection:
                for market in list(self.markets.values()):
                    if not market.start<=utcnow()<market.end: continue
                    try: await self.capture_book(market.id)
                    except Exception as error: self.errors['book:'+market.id]=type(error).__name__
            await asyncio.sleep(5)
    async def preview_order(self,intent):
        try: book=await self.capture_book(intent.market_id)
        except Exception as error:
            self.errors['book:'+intent.market_id]=type(error).__name__
            limited=isinstance(error,RateLimitCooldown) or getattr(getattr(error,'response',None),'status_code',None)==429
            retry=math.ceil(max(0,getattr(getattr(self.venue,'transport',None),'blocked_until',0)-time.monotonic()))
            return {'allowed':False,'reasons':['VENUE_RATE_LIMITED' if limited else 'BOOK_REFRESH_FAILED'],'maximum_cost':None,'estimate':None,'retry_after':retry}
        decision=self.engine.preview(intent); result=jsonable(decision)
        result.update({'order_id':intent.id,'book_version':book.version,'source_at':book.source_at.isoformat() if book.source_at else None,'estimate':None})
        if book.fresh(utcnow()):
            estimate=sweep(intent,book,self.markets[intent.market_id].tick,utcnow())
            result['estimate']={'qty':str(estimate.qty),'cost':str(estimate.cost),'fees':str(estimate.fees),'vwap':str(estimate.vwap) if estimate.vwap else None,'label':'PREVIEW_ONLY_NOT_A_FILL'}
        return result
    async def place_order(self,intent):
        async with self.command_locks.setdefault(intent.account_id,asyncio.Lock()):
            previous=self.store.get_order(intent.id)
            if previous:
                if any(previous[key]!=value for key,value in [('account_id',intent.account_id),('market_id',intent.market_id),('side',intent.side),('qty',intent.qty),('limit_price',intent.limit),('scenario',intent.scenario)]):
                    raise ValueError('Order ID already belongs to a different request')
                return {'allowed':True,'reasons':[],'order_id':intent.id,'status':previous['status']}
            preview=await self.preview_order(intent)
            if preview['allowed']: decision=self.engine.submit(intent)
            else:
                self.engine.reject(intent,preview['reasons'])
                return {**preview,'status':'REJECTED'}
            order=self.store.get_order(intent.id)
            return {**jsonable(decision),'order_id':intent.id,'status':order['status'] if order else 'REJECTED'}
    async def process_arrivals_once(self):
        due=self.store.pending_due(utcnow())
        for identity in dict.fromkeys(row['market_id'] for row in due):
            selected=[row['id'] for row in due if row['market_id']==identity]
            try: await self.capture_book(identity)
            except Exception as error:
                self.errors['arrival:'+identity]=type(error).__name__
                for order in selected: self.store.cancel(order,'ARRIVAL_BOOK_REFRESH_FAILED')
                continue
            self.engine.process_due(utcnow(),order_ids=selected)
    async def execution_loop(self):
        while self.running:
            try: await self.process_arrivals_once()
            except Exception as error: self.errors['execution']=type(error).__name__;self.persistence_halt('PERSISTENCE_FAILED')
            await asyncio.sleep(.05)
    async def settlement_loop(self):
        while self.running:
            for row in self.store.held_instruments():
                market=MarketTerms.from_raw(row['raw'])
                if market.end>utcnow(): continue
                if self.settlement_checks.get(market.id,market.end)>utcnow(): continue
                try:
                    status=await self.settlement.reconcile(market)
                    self.settlement_checks[market.id]=utcnow()+timedelta(seconds=300 if status=='SETTLED' else 10)
                    if status=='SETTLED': self.errors.pop('settlement:'+market.id,None)
                    else: self.errors['settlement:'+market.id]=status
                except Exception as error:
                    self.errors['settlement:'+market.id]=type(error).__name__
                    self.settlement_checks[market.id]=utcnow()+timedelta(seconds=30)
            await asyncio.sleep(10)
    def bot_status(self):
        account=self.store.state(BOT_ACCOUNT)
        return {'account_id':BOT_ACCOUNT,'status':'STOPPED' if not self.bot_enabled else 'HALTED' if account.halts else 'RUNNING',
                'enabled':self.bot_enabled,'validated':False,'strategy':self.book_strategy.version,
                'config':self.book_strategy.config,'config_hash':self.book_strategy.config_hash,
                'signals':self.bot_signals,'halts':account.halts,'restart_requires_run':True}
    def run_bot(self):
        if not self.collection or self.recorder.halted:raise ValueError('Resolve collection/persistence fault before RUN')
        if self.bot_enabled:
            if self.store.state(BOT_ACCOUNT).halts:raise ValueError('Bot is halted; STOP and resolve the risk lock before RUN')
            return self.bot_status()
        self.store.resume(BOT_ACCOUNT)
        self.book_strategy.history.clear();self.bot_signals.clear()
        self.store.audit('EXPERIMENTAL_BOT_RUN',BOT_ACCOUNT,{'config':self.book_strategy.config,'config_hash':self.book_strategy.config_hash})
        self.bot_enabled=True
        return self.bot_status()
    def stop_bot(self,reason='BOT_STOPPED'):
        self.bot_enabled=False
        self.book_strategy.history.clear()
        self.store.halt(BOT_ACCOUNT,reason)
        self.store.audit('EXPERIMENTAL_BOT_STOP',BOT_ACCOUNT,{'reason':reason,'positions_retained':True})
        return self.bot_status()
    async def bot_tick(self):
        async with self.bot_tick_lock:
            if not self.bot_enabled:return
            for market in list(self.markets.values()):
                if not market.start<=utcnow()<market.end:continue
                account=self.store.state(BOT_ACCOUNT)
                reasons=list(account.halts)
                if account.cooldown_until and utcnow()<account.cooldown_until:reasons.append('LOSS_COOLDOWN')
                if any(p.get('horizon')==market.horizon for p in account.positions+account.pending):reasons.append('CADENCE_POSITION_LIMIT')
                if (market.end-utcnow()).total_seconds()<={'15m':120,'1h':300}[market.horizon]:reasons.append('NO_ENTRY_WINDOW')
                identity=str(uuid.uuid5(uuid.NAMESPACE_URL,self.book_strategy.version+':'+market.id))
                if self.store.get_order(identity):reasons.append('MARKET_ATTEMPT_ALREADY_RECORDED')
                signal={'action':'NO_TRADE','reasons':reasons,'validated':False,'config_hash':self.book_strategy.config_hash}
                if not reasons:
                    try:
                        book=await self.capture_book(market.id)
                        # STOP can arrive while the read is in flight. Never reserve after it.
                        if not self.bot_enabled:return
                        signal=self.book_strategy.observe(book,utcnow())
                        if signal['action'].startswith('BUY_'):
                            down=signal['action'].endswith('DOWN')
                            price=(1-book.bids[0][0] if down else book.asks[0][0])+market.tick
                            qty=max(D('1'),market.minimum_qty)//market.minimum_qty*market.minimum_qty
                            if not D('.05')<=price<=D('.90'):
                                signal={**signal,'action':'NO_TRADE','reasons':['ENTRY_PRICE_RANGE']}
                            else:
                                intent=OrderIntent(identity,BOT_ACCOUNT,market.id,signal['action'],qty,price,self.book_strategy.version,None,'conservative')
                                decision=self.engine.submit(intent)
                                signal={**signal,'action':'ORDER_SUBMITTED' if decision.allowed else 'REJECTED',
                                        'side':intent.side,'order_id':identity,'qty':str(qty),'limit':str(price),
                                        'maximum_cost':str(decision.maximum_cost),'reasons':list(decision.reasons)}
                    except StorageHalt: return
                    except Exception as error:
                        self.book_strategy.history.pop(market.id,None)
                        limited=isinstance(error,RateLimitCooldown) or getattr(getattr(error,'response',None),'status_code',None)==429
                        signal={**signal,'action':'NO_TRADE','reasons':['VENUE_RATE_LIMITED' if limited else 'BOOK_REFRESH_FAILED'],'error':type(error).__name__}
                self.bot_signals[market.horizon]={'market_id':market.id,'at':utcnow(),**signal}
                self.store.decision(BOT_ACCOUNT,market.id,self.book_strategy.version,self.bot_signals[market.horizon])
            active=set(self.markets)
            self.book_strategy.history={k:v for k,v in self.book_strategy.history.items() if k in active}
    async def bot_loop(self):
        while self.running:
            try:await self.bot_tick()
            except Exception as error:
                self.errors['bot']=type(error).__name__
                self.stop_bot('BOT_ERROR')
            await asyncio.sleep(5)
    async def strategy_loop(self):
        while self.running:
            try:
                for market in list(self.markets.values()):
                    if not market.start<=utcnow()<market.end: continue
                    for strategy in self.strategies:
                        signal=strategy.evaluate(list(self.events),market,self.store.state(strategy.name),ExperimentConfig(),utcnow(),False)
                        self.store.decision(strategy.name,market.id,strategy.name,signal)
                for name in ACCOUNT_IDS:
                    account=self.store.state(name,self.marks())
                    with self.store.connect() as c: c.execute('INSERT INTO equity_snapshots(account_id,equity) VALUES(%s,%s)',(name,account.equity))
            except Exception as error: self.errors['strategy']=type(error).__name__
            await asyncio.sleep(30)
    def marks(self):
        result={}
        for identity,book in self.books.items():
            if book.fresh(utcnow()) and book.bids and book.asks:
                result[(identity,'UP')]=book.bids[0][0]; result[(identity,'DOWN')]=1-book.asks[0][0]
        return result
    async def stream_loop(self):
        import os
        key=os.environ.get('POLYMARKET_US_KEY_ID'); secret=os.environ.get('POLYMARKET_US_SECRET_KEY')
        if not key or not secret: return
        # Import only the official market-data socket, never an SDK order client.
        from polymarket_us.websocket.markets import MarketsWebSocket
        delay=1
        while self.running:
            socket=None
            try:
                selected={m.slug:m for m in self.markets.values() if m.end>utcnow()}
                if not selected: await asyncio.sleep(3); continue
                queue=asyncio.Queue(maxsize=256)
                socket=MarketsWebSocket(key_id=key,secret_key=secret)
                def receive(frame):
                    try: queue.put_nowait(frame)
                    except asyncio.QueueFull: self.errors['stream']='BACKLOG'; self.stream_status='BACKLOG'
                socket.on('message',receive); socket.on('close',lambda:receive({'_closed':True}))
                socket.on('error',lambda error:receive({'_error':type(error).__name__}))
                await socket.connect(); await socket.subscribe_market_data('polyquant-books',list(selected))
                await socket.subscribe_trades('polyquant-trades',list(selected))
                self.stream_status='CONNECTED'; delay=1
                while self.running:
                    frame=await asyncio.wait_for(queue.get(),timeout=20)
                    if '_closed' in frame or '_error' in frame: raise ConnectionError('Market stream disconnected')
                    if self.stream_status=='BACKLOG': raise ConnectionError('Stream backlog; snapshot resync required')
                    self.last_stream=utcnow()
                    if set(selected)!={m.slug for m in self.markets.values() if m.end>utcnow()}: break
                    data=frame.get('marketData')
                    if data and data.get('marketSlug') in selected:
                        from .market_data import normalize_book
                        market=selected[data['marketSlug']]; book=normalize_book(market.id,frame,{},utcnow())
                        self.event('book',frame,market.id,book.source_at); self.books[market.id]=book
                    elif frame.get('trade'): self.event('trade',frame)
            except asyncio.CancelledError: raise
            except Exception as error:
                self.stream_status='DISCONNECTED'; self.errors['stream']=type(error).__name__; self.gaps+=1
            finally:
                if socket: await socket.close()
            await asyncio.sleep(delay); delay=min(delay*2,30)
    def snapshot(self):
        now=utcnow(); markets=[]
        for market in sorted(self.markets.values(),key=lambda m:m.horizon):
            book=self.books.get(market.id); features=BookStrategy().features(book) if book else None
            item={'id':market.id,'slug':market.slug,'horizon':market.horizon,'start':market.start,'end':market.end,
                  'threshold':market.threshold,'status':market.status,'tick':market.tick,'minimum_qty':market.minimum_qty,
                  'signal':'NO TRADE','model_probability':None,'net_edge':None,'imbalance':features.get('imbalance') if features else None,
                  'book':jsonable(book) if book else None,'book_fresh':book.fresh(now) if book else False,
                  'source_age_seconds':(now-book.source_at).total_seconds() if book and book.source_at else None}
            markets.append(item)
        accounts=[jsonable(self.store.state(name,self.marks())) for name in ACCOUNT_IDS]
        return jsonable({'bot':self.bot_status(),'copy_trading':{'status':'UNAVAILABLE_US_IDENTIFIABLE_TRADE_FEED','enabled':False},'mode':'PAPER','environment':'production','server_time':now,'started_at':self.started_at,
            'collection':self.collection,'engine_state':'REFERENCE_BLOCKED','reference_validated':False,
            'rest_cooldown_seconds':math.ceil(max(0,getattr(getattr(self.venue,'transport',None),'blocked_until',0)-time.monotonic())),
            'manual_trading_ready':self.collection and not self.store.state('manual').halts and any(book.fresh(now) for book in self.books.values()),
            'reference':self.reference,'spot':self.spot,'markets':markets,'accounts':accounts,
            'http_latency_ms':self.latency_ms,'last_update':self.last_update,'stream_status':self.stream_status,
            'last_stream':self.last_stream,'gap_count':self.gaps,'errors':self.errors,'recorder':self.recorder.status(),
            'decisions':self.store.history('decisions',60),'orders':self.store.history('orders',60),
            'fills':self.store.fills(100),'datasets':self.store.history('datasets',60),
            'equity_history':self.store.history('equity_snapshots',120),
            'position_history':self.store.history('positions',100),'settlements':self.store.history('settlements',100),
            'performance':self.store.performance(),
            'research':{'status':'INSUFFICIENT_EVIDENCE','calibration':None,
                        'message':'Models are unfitted. Reference reconciliation must pass before reference-dependent strategies activate.'}})
