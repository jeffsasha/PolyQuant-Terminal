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


def spawn(name,args,cwd):
    pidfile=DATA/(name+'.pid')
    if pidfile.exists():
        pid=int(pidfile.read_text()); command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
        if str(ROOT) in command: return
    log=(DATA/(name+'.log')).open('ab')
    process=subprocess.Popen(args,cwd=cwd,env=env(),stdout=log,stderr=log,start_new_session=True)
    pidfile.write_text(str(process.pid))


def main():
    command=sys.argv[1] if len(sys.argv)>1 else 'start'
    if command in ['db','start','backend','web']:
        database()
        if command in ['start','backend']:
            spawn('backend',[str(ROOT/'.venv/bin/python'),'-m','uvicorn','polyquant.api:app','--host','127.0.0.1','--port','8000'],ROOT)
        if command in ['start','web']:
            spawn('web',[str(NODE),str(ROOT/'apps/web/node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port','3000'],ROOT/'apps/web')
        print('Workspace database is running on 127.0.0.1:55432.')
        if command!='db': print('Terminal: http://127.0.0.1:3000 — password is in .local/login-password.txt')
    elif command=='stop':
        for name in ['web','backend']:
            p=DATA/(name+'.pid')
            if p.exists():
                pid=int(p.read_text()); text=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout
                if str(ROOT) in text: os.kill(pid,signal.SIGTERM)
                p.unlink()
        subprocess.run([str(PG/'pg_ctl'),'-D',str(DATA/'postgres'),'stop','-m','fast'],check=False)
    else:
        print('Use: python3 scripts/local.py db|start|backend|web|stop'); return 2
    return 0


if __name__=='__main__': raise SystemExit(main())
