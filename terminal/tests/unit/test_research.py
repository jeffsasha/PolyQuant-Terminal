from datetime import timedelta
import pytest
from polyquant.types import utcnow

def test_probability_models_settlement_average_and_ties():
    from polyquant.strategies.probability import path_probability
    # Last tick is above 100; settlement average is below 100.
    assert path_probability([[97,102]],100,average_seconds=2)==0
    assert path_probability([[100,100]],100,average_seconds=2)==1
    assert path_probability([[99,99],[101,101]],100,average_seconds=2)==.5
    with pytest.raises(ValueError): path_probability([[100,100]],100)

def test_replay_uses_availability_and_is_reproducible():
    from polyquant.replay import causal_events,Replay
    at=utcnow()
    rows=[{'id':'later','source_at':at.isoformat(),'available_at':(at+timedelta(seconds=10)).isoformat(),'sequence':2,'kind':'book','payload':{}},
          {'id':'now','source_at':at.isoformat(),'available_at':at.isoformat(),'sequence':1,'kind':'book','payload':{}}]
    assert [r['id'] for r in causal_events(rows,at)]==['now']
    assert Replay().run(rows)==Replay().run(rows)
    assert Replay().run(rows)['net_pnl']=='0'
    assert Replay().run(rows)['status']=='REFERENCE_BLOCKED'

def test_time_splits_purge_overlapping_outcomes():
    from polyquant.research import chronological_split
    assert chronological_split([0,100,200,1000,2000],1500,embargo=3600)['train']==[]
    assert chronological_split([0,100,200,1000,10000],9000,embargo=3600)['train']==[0,100,200,1000]
