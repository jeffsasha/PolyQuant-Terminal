from datetime import timedelta
from dataclasses import replace
from decimal import Decimal as D,ROUND_DOWN
from .types import Fill,ExecutionResult,ExperimentConfig,OrderIntent,utcnow
from .fees import FeeModel
from .risk import RiskManager

SCENARIOS={'optimistic':(0,D('1'),0),'base':(.5,D('1'),0),
           'conservative':(1,D('.5'),1),'stress':(3,D('.25'),3)}


def sweep(intent,book,tick,at,passive=False,consumed=None):
    if passive: return ExecutionResult(reason='MAKER_QUEUE_UNOBSERVED',book_version=book.version)
    if intent.scenario not in SCENARIOS: raise ValueError('Unknown execution scenario')
    buying=intent.side.startswith('BUY'); down=intent.side.endswith('DOWN')
    source=(book.bids if down else book.asks) if buying else (book.asks if down else book.bids)
    levels=[(1-p if down else p,q) for p,q in source]
    _,depth,penalty=SCENARIOS[intent.scenario]
    remaining=intent.qty; fills=[]
    for price,qty in levels:
        price+=tick*penalty*(1 if buying else -1)
        if not 0<price<1 or (buying and price>intent.limit) or (not buying and price<intent.limit): continue
        available=max(D('0'),(qty*depth-(consumed or {}).get((intent.side,price),D('0')))).quantize(D('.01'),rounding=ROUND_DOWN)
        size=min(available,remaining)
        if size<=0: continue
        fills.append(Fill(price,size)); remaining-=size
        if remaining<=0: break
    charges=FeeModel().fees(fills,at)
    if fills and intent.scenario in ['conservative','stress']:
        # Aggregated levels hide counterparty fills; charge the order-level bound.
        upper=FeeModel.round(sum((FeeModel().exact(f.price,f.qty) for f in fills),D('0')))
        charges[-1]+=upper-sum(charges,D('0'))
    fills=tuple(replace(f,fee=fee) for f,fee in zip(fills,charges))
    status='FILLED' if fills and remaining==0 else 'PARTIALLY_FILLED_AND_CANCELED' if fills else 'CANCELED'
    return ExecutionResult(fills,status,'' if fills else 'NO_ELIGIBLE_ARRIVAL_LIQUIDITY',book.version)


class PaperExecutionEngine:
    def __init__(self,store,markets,books,reference,clock=None):
        from .clock import Clock
        self.store=store; self.markets=markets; self.books=books; self.reference=reference
        self.clock=clock or Clock(); self.risk=RiskManager(); self.consumed={}
    def preview(self,intent):
        market=self.markets.get(intent.market_id); book=self.books.get(intent.market_id)
        if not market or not book:
            from .types import RiskDecision
            return RiskDecision(False,('MARKET_DATA_UNAVAILABLE',))
        return self.risk.evaluate(intent,self.store.state(intent.account_id),market,book,self.reference(),ExperimentConfig(),self.clock.now())
    def submit(self,intent):
        decision=self.preview(intent)
        if not decision.allowed:
            self.reject(intent,decision.reasons)
            return decision
        delay=SCENARIOS[intent.scenario][0]
        ok=self.store.reserve(intent,decision.maximum_cost,self.clock.now()+timedelta(seconds=delay),
                              market=self.markets[intent.market_id],validator=lambda:self.preview(intent).allowed)
        if not ok:
            from .types import RiskDecision
            return RiskDecision(False,('DUPLICATE_OR_CONCURRENT_RISK_REJECTION',))
        return decision
    def reject(self,intent,reasons,phase='ADMISSION'):
        if 'DAILY_LOSS_LIMIT' in reasons: self.store.halt(intent.account_id,'DAILY_LOSS_LIMIT')
        self.store.decision(intent.account_id,intent.market_id,intent.strategy,{'action':'REJECTED','phase':phase,'reasons':reasons,'intent':intent})
    def process_due(self,at=None,order_ids=None):
        at=at or self.clock.now(); results=[]
        for row in self.store.pending_due(at):
            if order_ids is not None and row['id'] not in order_ids: continue
            intent=OrderIntent(row['id'],row['account_id'],row['market_id'],row['side'],row['qty'],row['limit_price'],row['strategy'],row['probability'],row['scenario'])
            market=self.markets.get(intent.market_id); book=self.books.get(intent.market_id)
            if book and book.received_at<row['arrival_at']:
                self.store.cancel(intent.id,'ARRIVAL_BOOK_NOT_OBSERVED'); continue
            if not market or not book or not book.fresh(at) or market.end<=at or self.store.state(intent.account_id).halts:
                self.store.cancel(intent.id,'ARRIVAL_REVALIDATION_FAILED'); continue
            account=self.store.state(intent.account_id)
            account=replace(account,reserved=account.reserved-row['reserved'],
                            pending=tuple(p for p in account.pending if p['id']!=row['id']))
            admission=self.risk.evaluate(intent,account,market,book,self.reference(),ExperimentConfig(),at)
            if not admission.allowed:
                self.reject(intent,admission.reasons,'ARRIVAL')
                self.store.cancel(intent.id,'ARRIVAL_'+','.join(admission.reasons)); continue
            key=(intent.account_id,intent.market_id,book.version)
            used=self.consumed.setdefault(key,{})
            result=sweep(intent,book,market.tick,at,consumed=used)
            self.store.commit_execution(intent.id,result)
            for fill in result.fills: used[(intent.side,fill.price)]=used.get((intent.side,fill.price),D('0'))+fill.qty
            results.append(result)
        # Keep only the current version per market; old books cannot be used again.
        self.consumed={k:v for k,v in self.consumed.items() if self.books.get(k[1]) and self.books[k[1]].version==k[2]}
        return results
    def cancel_remaining(self,order_id): self.store.cancel(order_id)


class LiveExecutionEngine:
    def submit(self,*args,**kwargs): raise RuntimeError('Live trading is disabled at the code boundary')
