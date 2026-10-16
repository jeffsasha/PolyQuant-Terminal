import math,random

def chronological_split(outcome_times,boundary,embargo=3600):
    return {'train':[x for x in outcome_times if x<boundary-embargo],
            'embargo':[x for x in outcome_times if boundary-embargo<=x<boundary],
            'test':[x for x in outcome_times if x>=boundary]}

def probability_metrics(predictions,outcomes):
    if not predictions or len(predictions)!=len(outcomes): return {'brier':None,'log_loss':None,'samples':0}
    if any(not math.isfinite(p) or not 0<=p<=1 for p in predictions): raise ValueError('Invalid probability')
    if any(y not in [0,1] for y in outcomes): raise ValueError('Invalid binary outcome')
    n=len(outcomes)
    return {'brier':sum((p-y)**2 for p,y in zip(predictions,outcomes))/n,
            'log_loss':-sum(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12)) for p,y in zip(predictions,outcomes))/n,'samples':n}

def block_bootstrap(blocks,seed=417,repetitions=1000):
    if len(blocks)<2: return {'lower':None,'upper':None,'status':'INSUFFICIENT_BLOCKS'}
    rng=random.Random(seed); samples=[]
    for _ in range(repetitions):
        selected=[rng.choice(blocks) for _ in blocks]
        samples.append(sum(sum(b) for b in selected)/sum(len(b) for b in selected))
    samples.sort()
    return {'lower':samples[int(repetitions*.025)],'upper':samples[int(repetitions*.975)],'status':'RESEARCH_ONLY'}
