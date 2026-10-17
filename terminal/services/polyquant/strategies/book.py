class BookStrategy:
    name='book'; version='book-0.1-unfitted'
    def features(self,book):
        if not book.bids or not book.asks: return None
        bp,bq=book.bids[0]; ap,aq=book.asks[0]
        total=bq+aq
        return {'spread':str(ap-bp),'imbalance':str((bq-aq)/total),'microprice':str((ap*bq+bp*aq)/total)}
    def evaluate(self,events,market,account,config,at,reference_validated=False):
        return {'action':'NO_TRADE','probability':None,'reasons':['OFFLINE_MODEL_NOT_FITTED'],
                'model_version':self.version,'config_hash':config.hash}


class ExperimentalBookStrategy:
    """Frozen directional heuristic; no calibrated probability or profitability claim."""
    version='book-imbalance-experiment-v1'
    account_id='book_experiment'
    config={'version':version,'levels':3,'imbalance_threshold':'0.20','confirmations':3,
            'minimum_signal_span_seconds':4,'maximum_signal_span_seconds':30,'maximum_gap_seconds':20,
            'maximum_spread':'0.05','minimum_entry_price':'0.05','maximum_entry_price':'0.90',
            'target_contracts':'1','scenario':'conservative','exit':'OFFICIAL_SETTLEMENT',
            'attempts_per_market':1,'validated':False}
    def __init__(self,account_id='book_experiment'):
        import hashlib,json
        from ..types import BOT_PROFILES,AGGRESSIVE_ACCOUNT
        self.account_id=account_id;self.version=BOT_PROFILES[account_id];self.config=dict(type(self).config)
        if account_id==AGGRESSIVE_ACCOUNT:
            self.config.update({'version':self.version,'target_contracts':None,'sizing':'ADAPTIVE_FEE_INCLUSIVE',
                                'target_allocation':'0.70','cadence_target':'0.35','maximum_allocation':'0.80',
                                'per_trade_loss_cap':'0.40','cadence_cap':'0.40','daily_entry_loss_halt':'0.20'})
        self.config_hash=hashlib.sha256(json.dumps(self.config,sort_keys=True).encode()).hexdigest()
        self.history={}
    def observe(self,book,at):
        from decimal import Decimal as D
        observations=self.history.setdefault(book.market_id,[])
        result={'action':'NO_TRADE','probability':None,'validated':False,'model_version':self.version,
                'config_hash':self.config_hash,'book_version':book.version,'reasons':[]}
        if not book.fresh(at):result['reasons'].append('STALE_BOOK')
        if not book.bids or not book.asks:result['reasons'].append('INSUFFICIENT_LIQUIDITY')
        if result['reasons']:
            observations.clear();return result
        spread=book.asks[0][0]-book.bids[0][0]
        bid_qty=sum((q for _,q in book.bids[:3]),D('0'));ask_qty=sum((q for _,q in book.asks[:3]),D('0'))
        imbalance=(bid_qty-ask_qty)/(bid_qty+ask_qty)
        result['features']={'spread':str(spread),'top3_bid_qty':str(bid_qty),'top3_ask_qty':str(ask_qty),'imbalance':str(imbalance)}
        if spread>D(self.config['maximum_spread']):result['reasons'].append('SPREAD_LIMIT')
        if abs(imbalance)<D(self.config['imbalance_threshold']):result['reasons'].append('IMBALANCE_BELOW_THRESHOLD')
        if result['reasons']:
            observations.clear();return result
        direction='UP' if imbalance>0 else 'DOWN'
        if observations and (observations[-1]['direction']!=direction or (at-observations[-1]['received_at']).total_seconds()>20):observations.clear()
        # A new cache key/body hash is not a new source observation.
        if observations and book.source_at<=observations[-1]['source_at']:
            result['reasons']=['DUPLICATE_SOURCE_OBSERVATION'];return result
        observations.append({'source_at':book.source_at,'received_at':at,'book_version':book.version,'direction':direction,'imbalance':str(imbalance)})
        observations[:]=[v for v in observations[-3:] if (at-v['received_at']).total_seconds()<=30]
        result['observations']=list(observations)
        if len(observations)<3 or (at-observations[0]['received_at']).total_seconds()<4:
            result['reasons']=['SIGNAL_WARMUP'];return result
        result['action']='BUY_'+direction
        return result
