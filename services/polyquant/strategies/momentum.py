import math

class MomentumStrategy:
    name='momentum'; version='momentum-0.1-unfitted'
    def features(self,prices):
        if len(prices)<3 or any(p<=0 for p in prices): return None
        returns=[math.log(b/a) for a,b in zip(prices,prices[1:])]
        mean=sum(returns)/len(returns)
        volatility=math.sqrt(sum((v-mean)**2 for v in returns)/len(returns))
        return {'log_return':sum(returns),'realized_volatility':volatility,'observations':len(returns)}
    def evaluate(self,events,market,account,config,at,reference_validated=False):
        return {'action':'NO_TRADE','probability':None,'reasons':['OFFLINE_MODEL_NOT_FITTED','REFERENCE_RECONCILIATION_FAILED'],
                'model_version':self.version,'config_hash':config.hash}
