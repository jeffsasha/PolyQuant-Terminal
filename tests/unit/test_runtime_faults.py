from types import SimpleNamespace
from collections import deque
import pytest
from polyquant.runtime import Runtime
from polyquant.recorder import StorageHalt

def test_disk_io_failure_latches_collection_and_persistent_halts():
    halts=[]
    def broken(event):raise OSError('Simulated disk I/O failure')
    runtime=object.__new__(Runtime)
    runtime.sequence=0;runtime.collection=True;runtime.errors={};runtime.events=deque();runtime.last_update=None
    runtime.recorder=SimpleNamespace(append=broken,halted=False,events=0)
    runtime.store=SimpleNamespace(halt=lambda account,reason:halts.append((account,reason)))
    with pytest.raises(StorageHalt):runtime.event('book',{})
    assert not runtime.collection and runtime.recorder.halted
    assert runtime.errors['recorder']=='PERSISTENCE_FAILED'
    assert {account for account,_ in halts}=={'manual','verification','probability','momentum','book','book_experiment'} and all(reason=='PERSISTENCE_FAILED' for _,reason in halts)
    assert not runtime.events and runtime.last_update is None
