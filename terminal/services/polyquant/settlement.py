"""Official binary payout; never infer finality from BTC reference history."""
import hashlib,json,uuid
from .types import MarketTerms,decimal,jsonable,utcnow


def authoritative_outcome(detail,payout):
    raw=detail.get('market') or {}
    try: market=MarketTerms.from_raw(raw)
    except (ValueError,KeyError,TypeError): return None
    if market.status!='MARKET_STATUS_RESOLVED' or not market.closed: return None
    if payout.get('slug')!=market.slug or isinstance(payout.get('settlement'),bool): return None
    try: value=decimal(payout['settlement'])
    except (ValueError,KeyError): return None
    if value not in [0,1] or payout.get('settlementPreliminaryFlag') is True: return None
    return 'UP' if value==1 else 'DOWN'


class SettlementProvider:
    def __init__(self,transport,store): self.transport=transport;self.store=store
    async def reconcile(self,market):
        params={'_pq_read':uuid.uuid4().hex}
        detail,dh=await self.transport.request('GET','/v1/market/slug/'+market.slug,params)
        if (detail.get('market') or {}).get('id')!=market.id: raise ValueError('Settlement instrument mismatch')
        if (detail.get('market') or {}).get('status')!='MARKET_STATUS_RESOLVED': return 'PENDING_FINALITY'
        payout,ph=await self.transport.request('GET','/v1/markets/'+market.slug+'/settlement',params)
        outcome=authoritative_outcome(detail,payout)
        if outcome is None: return 'PENDING_FINALITY'
        with self.store.connect() as c:
            last=c.execute('SELECT id,outcome FROM settlements WHERE market_id=%s ORDER BY created_at DESC LIMIT 1',(market.id,)).fetchone()
        if last and last['outcome']==outcome: return 'SETTLED'
        canonical=json.dumps({'market_id':market.id,'slug':market.slug,'outcome':outcome,'previous':last['id'] if last else None},sort_keys=True)
        revision=hashlib.sha256(canonical.encode()).hexdigest()
        evidence={'observed_at':utcnow(),'detail':detail,'payout':payout,'http':{label:{k:h[k] for k in ['date','age','cf-cache-status'] if k in h} for label,h in [('detail',dh),('payout',ph)]}}
        self.store.settle_market(market.id,outcome,revision,final=True,provenance=evidence)
        return 'SETTLED'
