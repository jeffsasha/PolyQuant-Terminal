import gzip,hashlib,json,os,shutil,uuid,zlib
from pathlib import Path
from threading import RLock
from .types import jsonable

class StorageHalt(RuntimeError): pass

class Recorder:
    def __init__(self,directory,quota=10_000_000_000,minimum_free=2_000_000_000):
        self.directory=Path(directory); self.directory.mkdir(parents=True,exist_ok=True)
        self.quota=quota; self.minimum_free=minimum_free; self.halted=False
        self.current=None; self.events=0; self.first=None; self.last=None
        self.lock=RLock(); self.recovery_errors=[]
    def status(self):
        with self.lock:
            used=sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())
            return {'used_bytes':used,'quota_bytes':self.quota,'warning':used>=self.quota*.8,
                    'halted':self.halted,'free_bytes':shutil.disk_usage(self.directory).free,
                    'recovery_errors':self.recovery_errors}
    def append(self,event):
        with self.lock:
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
    def write_manifest(self,path,result):
        destination=path.with_suffix('.manifest.json')
        temporary=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp')
        with temporary.open('x') as f:
            json.dump(result,f,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(temporary,destination)
        descriptor=os.open(self.directory,os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    def seal(self):
        with self.lock:
            if self.current is None: return None
            raw=self.current.read_bytes()
            result={'id':self.current.stem,'filename':self.current.name,'sha256':hashlib.sha256(raw).hexdigest(),
                    'bytes':len(raw),'events':self.events,'first_at':self.first.isoformat(),'last_at':self.last.isoformat()}
            self.write_manifest(self.current,result)
            self.current=None; self.events=0
            return result
    def recover(self):
        """Register durable captures after a crash; quarantine incomplete originals without deletion."""
        with self.lock:
            manifests=[]
            self.recovery_errors=[p.name for p in self.directory.glob('*.quarantine')]
            for path in sorted(self.directory.glob('*.jsonl.gz')):
                try:
                    raw=path.read_bytes()
                    rows=[json.loads(line) for line in gzip.decompress(raw).splitlines()]
                    if not rows or any(not isinstance(row,dict) or 'received_at' not in row for row in rows):
                        raise ValueError('Invalid recorded events')
                    manifest_path=path.with_suffix('.manifest.json')
                    if manifest_path.exists():
                        result=json.loads(manifest_path.read_text());self.read(result)
                        if result['filename']!=path.name: raise ValueError('Manifest does not match segment')
                    else:
                        result={'id':path.stem,'filename':path.name,'sha256':hashlib.sha256(raw).hexdigest(),
                                'bytes':len(raw),'events':len(rows),'first_at':rows[0]['received_at'],'last_at':rows[-1]['received_at']}
                        self.write_manifest(path,result)
                    manifests.append(result)
                except (ValueError,KeyError,TypeError,EOFError,gzip.BadGzipFile,zlib.error):
                    quarantine=path.with_name(path.name+'.quarantine')
                    if quarantine.exists(): quarantine=path.with_name(path.name+'.'+uuid.uuid4().hex+'.quarantine')
                    path.rename(quarantine);self.recovery_errors.append(quarantine.name)
            self.halted=bool(self.recovery_errors)
            return manifests
    def read(self,manifest):
        with self.lock:
            path=(self.directory/manifest['filename']).resolve()
            if path.parent!=self.directory.resolve(): raise ValueError('Invalid dataset path')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=manifest['sha256']: raise ValueError('Dataset checksum mismatch')
            rows=[json.loads(line) for line in gzip.decompress(raw).splitlines()]
            if len(rows)!=manifest['events']: raise ValueError('Dataset event count mismatch')
            return rows
