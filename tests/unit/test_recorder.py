import json,gzip
from pathlib import Path
import pytest
from polyquant.types import MarketEvent,utcnow

def test_persisted_events_hash_and_quota(tmp_path):
    from polyquant.recorder import Recorder,StorageHalt
    now=utcnow(); r=Recorder(tmp_path,quota=2000,minimum_free=0)
    event=MarketEvent('event','fixture','book',now,now,now,1,{'price':'0.50'})
    r.append(event); manifest=r.seal()
    events=r.read(manifest)
    assert events[0]['payload']['price']=='0.50'
    assert manifest['events']==1 and manifest['bytes']>0
    Path(tmp_path/manifest['filename']).write_bytes(b'corrupted')
    with pytest.raises(ValueError): r.read(manifest)
    tiny=Recorder(tmp_path/'tiny',quota=10,minimum_free=0)
    with pytest.raises(StorageHalt): tiny.append(event)
    assert tiny.halted
