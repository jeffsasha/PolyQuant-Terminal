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

def test_restart_recovers_unsealed_and_unregistered_segments(tmp_path):
    from polyquant.recorder import Recorder
    now=utcnow(); event=MarketEvent('durable','fixture','book',now,now,now,1,{})
    first=Recorder(tmp_path,minimum_free=0);first.append(event)
    restored=Recorder(tmp_path,minimum_free=0)
    manifests=restored.recover()
    assert len(manifests)==1 and manifests[0]['events']==1
    assert restored.read(manifests[0])[0]['id']=='durable'
    assert restored.recover()==manifests


def test_incomplete_segment_preserved_with_visible_recovery_halt(tmp_path):
    from polyquant.recorder import Recorder
    broken=tmp_path/'broken.jsonl.gz';broken.write_bytes(b'incomplete-gzip')
    r=Recorder(tmp_path,minimum_free=0)
    assert r.recover()==[]
    assert r.halted and r.recovery_errors
    assert (tmp_path/'broken.jsonl.gz.quarantine').read_bytes()==b'incomplete-gzip'


def test_manual_seal_serializes_with_append(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from polyquant.recorder import Recorder
    now=utcnow();r=Recorder(tmp_path,minimum_free=0)
    event=MarketEvent('one','fixture','book',now,now,now,1,{})
    r.append(event);path=r.current;started=Event();release=Event();appended=Event()
    original=Path.read_bytes
    def controlled(p):
        if p==path: started.set();release.wait(2)
        return original(p)
    monkeypatch.setattr(Path,'read_bytes',controlled)
    def append(): r.append(event);appended.set()
    with ThreadPoolExecutor(2) as pool:
        sealed=pool.submit(r.seal);assert started.wait(2)
        writing=pool.submit(append)
        try: assert not appended.wait(.05),'Append raced a sealing segment'
        finally: release.set()
        manifest=sealed.result();writing.result()
    assert len(r.read(manifest))==1
    assert r.seal()['events']==1
