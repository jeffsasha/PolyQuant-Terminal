import hashlib,json
from .types import timestamp


def causal_events(events,at):
    rows=[e for e in events if timestamp(e['available_at'])<=at]
    return sorted(rows,key=lambda e:(timestamp(e['available_at']),e['sequence']))


class Replay:
    def run(self,events):
        rows=sorted(events,key=lambda e:(timestamp(e['available_at']),e['sequence']))
        digest=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()
        # Preserve the production reference block during replay; do not synthesize fills.
        return {'status':'REFERENCE_BLOCKED','dataset_hash':digest,'events_replayed':len(rows),
                'book_events':sum(e.get('kind')=='book' for e in rows),
                'markets':len({e.get('market_id') for e in rows if e.get('market_id')}),
                'orders':0,'fills':0,'gross_pnl':'0','fees':'0','net_pnl':'0',
                'calibration':None,'research_status':'INSUFFICIENT_EVIDENCE',
                'reasons':['REFERENCE_RECONCILIATION_FAILED','OFFLINE_MODEL_NOT_FITTED'],
                'scenarios':['optimistic','base','conservative','stress'],'combined_returns':False}
