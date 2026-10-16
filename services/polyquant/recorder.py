import gzip,hashlib,json,os,shutil,uuid
from pathlib import Path
from .types import jsonable,utcnow

class StorageHalt(RuntimeError): pass

class Recorder:
    def __init__(self,directory,quota=10_000_000_000,minimum_free=2_000_000_000):
        self.directory=Path(directory); self.directory.mkdir(parents=True,exist_ok=True)
        self.quota=quota; self.minimum_free=minimum_free; self.halted=False
        self.current=None; self.events=0; self.first=None; self.last=None
    def status(self):
        used=sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())
        return {'used_bytes':used,'quota_bytes':self.quota,'warning':used>=self.quota*.8,
                'halted':self.halted,'free_bytes':shutil.disk_usage(self.directory).free}
    def append(self,event):
        if self.halted: raise StorageHalt('Recorder is halted')
        encoded=gzip.compress((json.dumps(jsonable(event),sort_keys=True)+'\n').encode(),mtime=0)
        status=self.status()
        if status['used_bytes']+len(encoded)+1024>self.quota or status['free_bytes']<self.minimum_free:
            self.halted=True; raise StorageHalt('STORAGE_LIMIT')
        if self.current is None:
            self.current=self.directory/(str(uuid.uuid4())+'.jsonl.gz'); self.events=0; self.first=event.received_at
        with self.current.open('ab') as f: f.write(encoded); f.flush(); os.fsync(f.fileno())
        self.events+=1; self.last=event.received_at
        return event
    def seal(self):
        if self.current is None: return None
        raw=self.current.read_bytes()
        result={'id':self.current.stem,'filename':self.current.name,'sha256':hashlib.sha256(raw).hexdigest(),
                'bytes':len(raw),'events':self.events,'first_at':self.first.isoformat(),'last_at':self.last.isoformat()}
        self.current.with_suffix('.manifest.json').write_text(json.dumps(result,indent=2))
        self.current=None; self.events=0
        return result
    def read(self,manifest):
        path=(self.directory/manifest['filename']).resolve()
        if path.parent!=self.directory.resolve(): raise ValueError('Invalid dataset path')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=manifest['sha256']: raise ValueError('Dataset checksum mismatch')
        rows=[json.loads(line) for line in gzip.decompress(raw).splitlines()]
        if len(rows)!=manifest['events']: raise ValueError('Dataset event count mismatch')
        return rows
