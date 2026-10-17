from decimal import Decimal,ROUND_HALF_EVEN
import math,random


def path_probability(paths,threshold,average_seconds=60):
    if not paths: raise ValueError('Historical paths required')
    wins=0
    for path in paths:
        if len(path)<average_seconds or not all(math.isfinite(float(v)) and v>0 for v in path): raise ValueError('Incomplete or invalid historical path')
        tail=path[-average_seconds:]
        value=(sum(Decimal(str(v)) for v in tail)/Decimal(len(tail))).quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)
        wins+=value>=Decimal(str(threshold)).quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)
    return wins/len(paths)


def zero_drift_probability(spot,threshold,volatility,seconds):
    if min(spot,threshold,volatility,seconds)<=0: raise ValueError('Positive inputs required')
    z=math.log(spot/threshold)/(volatility*math.sqrt(seconds))
    return .5*(1+math.erf(z/math.sqrt(2)))


class ProbabilityStrategy:
    name='probability'
    version='probability-0.1-unfitted'
    def evaluate(self,events,market,account,config,at,reference_validated=False):
        # The runtime never supplies True until the documented discrepancy is resolved in code.
        reasons=['REFERENCE_RECONCILIATION_FAILED'] if not reference_validated else []
        available=[e for e in events if e.available_at<=at]
        if len(available)<120: reasons.append('MODEL_WARMUP_INSUFFICIENT')
        reasons.append('OFFLINE_MODEL_NOT_FITTED')
        return {'action':'NO_TRADE','probability':None,'reasons':reasons,'model_version':self.version,
                'config_hash':config.hash,'available_observations':len(available)}


def fit_probability(paths,threshold,seed=417):
    if len(paths)<200: raise ValueError('At least 200 independent path samples required for this research fit')
    p=path_probability(paths,threshold)
    rng=random.Random(seed)
    estimates=sorted(path_probability([rng.choice(paths) for _ in paths],threshold) for _ in range(500))
    return {'probability':p,'lower_bound':estimates[12],'upper_bound':estimates[487],
            'seed':seed,'samples':len(paths),'target':'rounded final-window average','research_only':True}
