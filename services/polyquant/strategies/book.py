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
