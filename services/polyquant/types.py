from dataclasses import dataclass,field,asdict
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
import hashlib
import json


def decimal(value) -> Decimal:
    if isinstance(value,float): raise ValueError('Financial values must be decimal strings')
    try: result=Decimal(value)
    except (InvalidOperation,TypeError,ValueError): raise ValueError('Invalid decimal') from None
    if not result.is_finite(): raise ValueError('Decimal must be finite')
    return result


def timestamp(value) -> datetime:
    result=value if isinstance(value,datetime) else datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def utcnow(): return datetime.now(timezone.utc)


def jsonable(value):
    def encode(item):
        if hasattr(item,'__dataclass_fields__'): return asdict(item)
        if isinstance(item,datetime): return item.isoformat()
        if isinstance(item,Decimal): return str(item)
        raise TypeError('Unsupported JSON value')
    return json.loads(json.dumps(value,default=encode))


@dataclass(frozen=True)
class MarketTerms:
    id:str
    slug:str
    horizon:str
    start:datetime
    end:datetime
    threshold:Decimal|None
    active:bool=True
    closed:bool=False
    status:str=''
    tick:Decimal=Decimal('0.01')
    minimum_qty:Decimal=Decimal('0.01')
    rules:str=''
    raw:dict=field(default_factory=dict,compare=False)

    @classmethod
    def from_raw(cls,raw):
        t=raw.get('assetPriceTerms') or {}; a=t.get('asset') or {}
        if (t.get('marketType')!='ASSET_PRICE_MARKET_TYPE_UP_DOWN' or a.get('symbol','').lower()!='btc'
            or a.get('assetClass')!='ASSET_CLASS_CRYPTO' or t.get('indexSymbol')!='BRTI' or t.get('horizon') not in ['15m','1h']):
            raise ValueError('Unsupported typed instrument')
        start,end=timestamp(t['windowStart']),timestamp(t['windowEnd'])
        if (end-start).total_seconds()!={'15m':900,'1h':3600}[t['horizon']]: raise ValueError('Inconsistent window')
        threshold=None; p=t.get('priceToBeat')
        if p and p.get('currency')=='USD':
            threshold=decimal(str(p['value']))
            if threshold<=0: raise ValueError('Invalid reference threshold')
        return cls(str(raw['id']),raw['slug'],t['horizon'],start,end,threshold,raw.get('active') is True,
            raw.get('closed') is True,raw.get('status',''),decimal(str(raw.get('orderPriceMinTickSize') or '0.01')),
            decimal(str(raw.get('minimumTradeQty') or '0.01')),raw.get('description',''),raw)


@dataclass(frozen=True)
class BookSnapshot:
    market_id:str
    bids:tuple
    asks:tuple
    source_at:datetime|None
    received_at:datetime
    version:str
    state:str='MARKET_STATE_OPEN'
    cache_age:int|None=None

    def __post_init__(self):
        for levels in [self.bids,self.asks]:
            for p,q in levels:
                if not (decimal(p)>0 and p<1 and decimal(q)>0): raise ValueError('Invalid book level')
        if tuple(sorted(self.bids,reverse=True))!=self.bids or tuple(sorted(self.asks))!=self.asks:
            raise ValueError('Unsorted order book')
        if self.bids and self.asks and self.bids[0][0]>=self.asks[0][0]: raise ValueError('Crossed book')

    def fresh(self,at,max_age=2):
        if self.source_at is None: return False
        if self.cache_age is not None and not 0<=self.cache_age<=max_age: return False
        ages=[(at-self.received_at).total_seconds(),(at-self.source_at).total_seconds()]
        return self.state=='MARKET_STATE_OPEN' and all(0<=age<=max_age for age in ages)


@dataclass(frozen=True)
class ReferenceSnapshot:
    value:Decimal|None=None
    source_at:datetime|None=None
    received_at:datetime|None=None
    validated:bool=False
    source:str='Polymarket US BRTI history'
    reason:str='REFERENCE_RECONCILIATION_FAILED'


@dataclass(frozen=True)
class ExperimentConfig:
    version:str='baseline-0.1'
    scenario:str='conservative'
    risk_per_trade:Decimal=Decimal('0.005')
    exposure_limit:Decimal=Decimal('0.05')
    cadence_limit:Decimal=Decimal('0.025')
    daily_loss:Decimal=Decimal('0.02')
    min_edge:Decimal=Decimal('0.03')
    max_spread:Decimal=Decimal('0.05')
    max_positions:int=2
    seed:int=417
    @property
    def hash(self): return hashlib.sha256(json.dumps(jsonable(self),sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class OrderIntent:
    id:str
    account_id:str
    market_id:str
    side:str
    qty:Decimal
    limit:Decimal
    strategy:str='manual'
    probability:Decimal|None=None
    scenario:str='conservative'


@dataclass(frozen=True)
class Fill:
    price:Decimal
    qty:Decimal
    fee:Decimal=Decimal('0')
    liquidity:str='TAKER'


@dataclass(frozen=True)
class ExecutionResult:
    fills:tuple=()
    status:str='CANCELED'
    reason:str='NO_LIQUIDITY'
    book_version:str=''
    @property
    def qty(self): return sum((f.qty for f in self.fills),Decimal('0'))
    @property
    def cost(self): return sum((f.price*f.qty for f in self.fills),Decimal('0'))
    @property
    def fees(self): return sum((f.fee for f in self.fills),Decimal('0'))
    @property
    def vwap(self): return self.cost/self.qty if self.qty else None


@dataclass(frozen=True)
class AccountState:
    id:str
    cash:Decimal=Decimal('1000')
    reserved:Decimal=Decimal('0')
    equity:Decimal=Decimal('1000')
    day_start_equity:Decimal=Decimal('1000')
    positions:tuple=()
    pending:tuple=()
    halts:tuple=()
    consecutive_losses:int=0
    cooldown_until:datetime|None=None


@dataclass(frozen=True)
class RiskDecision:
    allowed:bool
    reasons:tuple
    maximum_cost:Decimal=Decimal('0')


@dataclass(frozen=True)
class MarketEvent:
    id:str
    market_id:str|None
    kind:str
    source_at:datetime|None
    received_at:datetime
    available_at:datetime
    sequence:int
    payload:dict
    environment:str='production'
