#!/usr/bin/env python3
"""Native encrypted-at-rest permissions; restore only to a new disposable database."""
import argparse,json,os,subprocess,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local
sys.path.insert(0,str(local.ROOT/'services'))
import psycopg
from psycopg.conninfo import conninfo_to_dict

TABLES=['accounts','orders','fills','positions','postings','audit','settlements','datasets','equity_snapshots','instrument_versions']

def environment(database=None):
    values=conninfo_to_dict(local.env()['DATABASE_URL']);env=dict(os.environ)
    for source,target in [('host','PGHOST'),('port','PGPORT'),('user','PGUSER'),('password','PGPASSWORD'),('dbname','PGDATABASE')]:
        if source in values: env[target]=values[source]
    if database: env['PGDATABASE']=database
    return env

def run(command,env):
    result=subprocess.run([str(local.PG/command[0]),*command[1:]],env=env,capture_output=True)
    if result.returncode: raise RuntimeError('Database backup command failed; no credentials are printed')
    return result.stdout

def fingerprint(database=None):
    env=environment(database)
    with psycopg.connect(host=env['PGHOST'],port=env['PGPORT'],user=env['PGUSER'],password=env['PGPASSWORD'],dbname=env['PGDATABASE']) as c:
        result={table:c.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in TABLES}
        result['account_state']=[tuple(str(v) for v in row) for row in c.execute('SELECT id,cash,reserved,day_start,day_id,halts,config FROM accounts ORDER BY id').fetchall()]
        return result

def backup(destination):
    destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if destination.exists(): raise ValueError('Refusing to overwrite an existing backup')
    descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            result=subprocess.run([str(local.PG/'pg_dump'),'--format=custom','--no-owner','--no-acl'],env=environment(),stdout=stream,stderr=subprocess.PIPE)
        if result.returncode: raise RuntimeError('Backup failed')
    except BaseException:
        destination.unlink(missing_ok=True);raise

def verify(destination):
    # Collection should be stopped during a comparable snapshot drill.
    target='polyquant_restore_'+uuid.uuid4().hex[:12]
    expected=fingerprint();run(['createdb',target],environment())
    try:
        run(['pg_restore','--exit-on-error','--no-owner','--no-acl','--dbname='+target,str(destination)],environment(target))
        actual=fingerprint(target)
        if actual!=expected: raise RuntimeError('Restored state differs; stop collection before the comparison drill')
        print('Restore verification passed: table counts and account money, reservations, halts and configs match.')
    finally: run(['dropdb',target],environment())

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['backup','verify']);parser.add_argument('file',type=Path);args=parser.parse_args()
    try:
        if args.command=='backup': backup(args.file);print('Backup saved with owner-only permissions. Raw recordings must be backed up separately.')
        else: verify(args.file)
    except Exception as error:
        print(type(error).__name__+': backup/restore did not complete. No credentials are printed.',file=sys.stderr);sys.exit(1)
