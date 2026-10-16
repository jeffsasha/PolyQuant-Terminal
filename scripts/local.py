#!/usr/bin/env python3
"""Start/stop a workspace-owned PostgreSQL, API and web server. No system service."""
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'.local'
PG=Path('/opt/homebrew/opt/postgresql@17/bin')
NODE=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
PNPM=NODE.parents[1]/'node_modules/pnpm/bin/pnpm.cjs'


def env():
    result=dict(os.environ)
    path=ROOT/'.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1); result[key]=value
    result['PYTHONPATH']=str(ROOT/'services')
    result['PATH']=str(NODE.parent)+os.pathsep+result.get('PATH','')
    result['NODE_EXTRA_CA_CERTS']='/etc/ssl/cert.pem'
    result['SSL_CERT_FILE']='/etc/ssl/cert.pem'
    return result


def database():
    DATA.mkdir(mode=0o700,exist_ok=True)
    if not (ROOT/'.env').exists():
        password=secrets.token_urlsafe(32)
        login=secrets.token_urlsafe(16)
        salt=secrets.token_hex(16)
        import hashlib
        digest=hashlib.scrypt(login.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        for path,text in [(DATA/'pg-password',password), (DATA/'login-password.txt',login+'\n'),
                          (ROOT/'.env',f'LIVE_TRADING_ENABLED=false\nDATABASE_URL=postgresql://polyquant:{password}@127.0.0.1:55432/polyquant\nPOLYQUANT_DATA_DIR={DATA}\nWEB_ORIGIN=http://127.0.0.1:3000\nPOLYQUANT_PASSWORD_HASH={salt}:{digest}\nPOLYMARKET_US_KEY_ID=\nPOLYMARKET_US_SECRET_KEY=\n')]:
            path.write_text(text); path.chmod(0o600)
    if not (DATA/'postgres/PG_VERSION').exists():
        subprocess.run([str(PG/'initdb'),'-D',str(DATA/'postgres'),'-U','polyquant','--auth=scram-sha-256',
                        '--pwfile='+str(DATA/'pg-password'),'--locale=C','--encoding=UTF8'],check=True,stdout=subprocess.DEVNULL)
        with (DATA/'postgres/postgresql.conf').open('a') as f:
            f.write("\nlisten_addresses='127.0.0.1'\nport=55432\nunix_socket_directories='"+str(DATA).replace("'","''")+"'\n")
    status=subprocess.run([str(PG/'pg_ctl'),'-D',str(DATA/'postgres'),'status'],stdout=subprocess.DEVNULL)
    if status.returncode:
        subprocess.run([str(PG/'pg_ctl'),'-D',str(DATA/'postgres'),'-l',str(DATA/'postgres.log'),'start'],check=True,stdout=subprocess.DEVNULL)
    e=env(); e['PGPASSWORD']=(DATA/'pg-password').read_text().strip()
    query=subprocess.run([str(PG/'psql'),'-h','127.0.0.1','-p','55432','-U','polyquant','-d','postgres','-Atc',
                          "SELECT datname FROM pg_database WHERE datname IN ('polyquant','polyquant_test')"],env=e,capture_output=True,text=True,check=True).stdout
    for name in ['polyquant','polyquant_test']:
        if name not in query.splitlines():
            subprocess.run([str(PG/'createdb'),'-h','127.0.0.1','-p','55432','-U','polyquant',name],env=e,check=True)


def owned_process(pid,name):
    command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout.strip()
    if not command: return False
    expected=ROOT/'apps/web' if name=='web' else ROOT
    rows=subprocess.run(['/usr/sbin/lsof','-a','-p',str(pid),'-d','cwd','-Fn'],capture_output=True,text=True).stdout.splitlines()
    cwd=next((line[1:] for line in rows if line.startswith('n')),None)
    identity=('next-server' in command or str(ROOT/'apps/web/node_modules/next') in command) if name=='web' else 'uvicorn polyquant.api:app' in command
    return cwd==str(expected) and identity


def listener_pids(name):
    port='3000' if name=='web' else '8000'
    output=subprocess.run(['/usr/sbin/lsof','-nP','-t','-iTCP:'+port,'-sTCP:LISTEN'],capture_output=True,text=True).stdout
    return list(dict.fromkeys(int(line) for line in output.splitlines() if line.isdigit()))


def stop_process(name):
    pidfile=DATA/(name+'.pid')
    pid=int(pidfile.read_text()) if pidfile.exists() else None
    if pid is None or not owned_process(pid,name):
        candidates=[value for value in listener_pids(name) if owned_process(value,name)]
        if not candidates:
            pidfile.unlink(missing_ok=True);return
        pid=candidates[0]
    if owned_process(pid,name):
        os.kill(pid,signal.SIGTERM)
        for _ in range(100):
            if not owned_process(pid,name): break
            time.sleep(.1)
        else:
            os.kill(pid,signal.SIGKILL)
            for _ in range(30):
                if not owned_process(pid,name): break
                time.sleep(.1)
            else: raise RuntimeError('Owned service did not stop; database remains running')
    pidfile.unlink()


def spawn(name,args,cwd):
    pidfile=DATA/(name+'.pid')
    if pidfile.exists():
        pid=int(pidfile.read_text())
        if owned_process(pid,name): return
    listeners=listener_pids(name)
    if listeners:
        if len(listeners)==1 and owned_process(listeners[0],name):
            pidfile.write_text(str(listeners[0]));return
        raise RuntimeError(f'{name} port is occupied by another process; refusing to start or stop it')
    log=(DATA/(name+'.log')).open('ab')
    child_env=env()
    if name=='web':
        child_env={key:value for key,value in child_env.items() if not key.startswith(('POLYMARKET_', 'POLYQUANT_', 'PG')) and key!='DATABASE_URL'}
    process=subprocess.Popen(args,cwd=cwd,env=child_env,stdout=log,stderr=log,start_new_session=True)
    pidfile.write_text(str(process.pid))


def ready(name):
    port=3000 if name=='web' else 8000
    path='/' if name=='web' else '/health'
    for _ in range(100):
        pid=int((DATA/(name+'.pid')).read_text())
        try:
            if owned_process(pid,name) and listener_pids(name)==[pid]:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=1) as response:
                    if response.status==200: return
        except (OSError,ValueError): pass
        time.sleep(.1)
    raise RuntimeError(f'{name} did not become ready; inspect its private local log')


def main():
    command=sys.argv[1] if len(sys.argv)>1 else 'start'
    if command in ['db','start','backend','web']:
        database()
        if command in ['start','backend']:
            spawn('backend',[str(ROOT/'.venv/bin/python'),'-m','uvicorn','polyquant.api:app','--host','127.0.0.1','--port','8000','--timeout-graceful-shutdown','5'],ROOT)
        if command in ['start','web']:
            spawn('web',[str(NODE),str(ROOT/'apps/web/node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port','3000'],ROOT/'apps/web')
        if command in ['start','backend']: ready('backend')
        if command in ['start','web']: ready('web')
        print('Workspace database is running on 127.0.0.1:55432.')
        if command!='db': print('Terminal: http://127.0.0.1:3000 — password is in .local/login-password.txt')
    elif command=='stop':
        for name in ['web','backend']:
            stop_process(name)
        subprocess.run([str(PG/'pg_ctl'),'-D',str(DATA/'postgres'),'stop','-m','fast'],check=False)
    else:
        print('Use: python3 scripts/local.py db|start|backend|web|stop'); return 2
    return 0


if __name__=='__main__': raise SystemExit(main())
