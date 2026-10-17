from pathlib import Path
from datetime import timedelta
from decimal import Decimal as D
import uuid
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .types import AccountState,ExperimentConfig,jsonable,utcnow,ACCOUNT_IDS,BOT_PROFILES
from .clock import risk_day_id
from .risk import config_for


class Store:
    def __init__(self,dsn): self.dsn=dsn; self.writer=None
    def connect(self): return psycopg.connect(self.dsn,row_factory=dict_row)
    def migrate(self):
        with self.connect() as c: c.execute((Path(__file__).resolve().parents[2]/'migrations/001_core.sql').read_text())
    def bootstrap(self):
        with self.connect() as c:
            for name in ACCOUNT_IDS:
                c.execute('INSERT INTO accounts(id,day_id,config) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
                          (name,risk_day_id(utcnow()),Jsonb(jsonable(config_for(name,BOT_PROFILES.get(name))))))
    def acquire_writer(self):
        if self.writer: return True
        c=self.connect(); row=c.execute('SELECT pg_try_advisory_lock(5042026) AS locked').fetchone()
        if not row['locked']: c.close(); return False
        self.writer=c; return True
    def close(self):
        if self.writer: self.writer.close(); self.writer=None
    def audit(self,action,account=None,payload=None,c=None):
        if c is None:
            with self.connect() as conn: self.audit(action,account,payload,conn)
        else: c.execute('INSERT INTO audit(action,account_id,payload) VALUES(%s,%s,%s)',(action,account,Jsonb(jsonable(payload or {}))))
    def state(self,account_id,marks=None):
        with self.connect() as c:
            a=c.execute('SELECT * FROM accounts WHERE id=%s',(account_id,)).fetchone()
            if not a: raise ValueError('Unknown account')
            positions=c.execute("SELECT * FROM positions WHERE account_id=%s AND status='OPEN' AND qty>0",(account_id,)).fetchall()
            pending=c.execute("SELECT * FROM orders WHERE account_id=%s AND status='PENDING_ARRIVAL'",(account_id,)).fetchall()
        equity=a['cash']+sum(((marks or {}).get((p['market_id'],p['direction']),D('0'))*p['qty'] for p in positions),D('0'))
        return AccountState(account_id,a['cash'],a['reserved'],equity,a['day_start'],tuple(positions),tuple(pending),
                            tuple(a['halts']),a['consecutive_losses'],a['cooldown_until'],risk_day_ready=a['day_id']==risk_day_id(utcnow()) and not a['risk_baseline_pending'])
    def reserve(self,intent,maximum_cost,arrival_at=None,market=None,validator=None):
        if maximum_cost<0: raise ValueError('Invalid reservation')
        with self.connect() as c:
            account=c.execute('SELECT * FROM accounts WHERE id=%s FOR UPDATE',(intent.account_id,)).fetchone()
            if account['halts'] or maximum_cost>account['cash']-account['reserved']: return False
            if validator is not None and not validator(): return False
            existing=c.execute("SELECT id FROM orders WHERE id=%s OR (%s<>'manual_discretionary' AND account_id=%s AND market_id=%s AND strategy=%s)",
                (intent.id,intent.strategy,intent.account_id,intent.market_id,intent.strategy)).fetchone()
            if existing: return False
            c.execute('INSERT INTO orders(id,account_id,market_id,side,qty,limit_price,reserved,status,strategy,scenario,probability,arrival_at,horizon) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (intent.id,intent.account_id,intent.market_id,intent.side,intent.qty,intent.limit,maximum_cost,'PENDING_ARRIVAL',intent.strategy,intent.scenario,intent.probability,arrival_at or utcnow(),market.horizon if market else None))
            c.execute('UPDATE accounts SET reserved=reserved+%s WHERE id=%s',(maximum_cost,intent.account_id))
            self.audit('PAPER_ORDER_RESERVED',intent.account_id,{'order_id':intent.id,'maximum_cost':maximum_cost},c)
            return True
    def commit_execution(self,order_id,result):
        with self.connect() as c:
            row=c.execute('SELECT account_id FROM orders WHERE id=%s',(order_id,)).fetchone()
            if not row: raise ValueError('Unknown order')
            account=c.execute('SELECT * FROM accounts WHERE id=%s FOR UPDATE',(row['account_id'],)).fetchone()
            order=c.execute('SELECT * FROM orders WHERE id=%s FOR UPDATE',(order_id,)).fetchone()
            if order['status']!='PENDING_ARRIVAL': return
            if result.qty>order['qty'] or (order['side'].startswith('BUY') and result.cost+result.fees>order['reserved']):
                raise ValueError('Execution exceeds approved reservation')
            if account['halts'] and result.qty: raise ValueError('Execution blocked by persistent halt')
            direction=order['side'].split('_')[-1]
            delta=D('0')
            if result.qty:
                if order['side'].startswith('BUY'):
                    delta=-(result.cost+result.fees)
                    c.execute("INSERT INTO positions(account_id,market_id,direction,qty,cost,fees,horizon) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(account_id,market_id,direction) WHERE status='OPEN' DO UPDATE SET qty=positions.qty+EXCLUDED.qty,cost=positions.cost+EXCLUDED.cost,fees=positions.fees+EXCLUDED.fees",
                        (order['account_id'],order['market_id'],direction,result.qty,result.cost,result.fees,order['horizon']))
                    postings=[('CASH',delta),('INVENTORY',result.cost),('FEES',result.fees)]
                else:
                    p=c.execute("SELECT * FROM positions WHERE account_id=%s AND market_id=%s AND direction=%s AND status='OPEN' FOR UPDATE",(order['account_id'],order['market_id'],direction)).fetchone()
                    if not p or p['qty']<result.qty: raise ValueError('Uncovered sale prohibited')
                    basis=(p['cost']*result.qty/p['qty']).quantize(D('0.00000001'))
                    entry_fees=(p['fees']*result.qty/p['qty']).quantize(D('0.00000001'))
                    delta=result.cost-result.fees
                    closed=result.qty==p['qty']
                    c.execute("UPDATE positions SET qty=qty-%s,cost=cost-%s,fees=fees-%s,realized_pnl=realized_pnl+%s,status=%s,settled_at=%s WHERE id=%s",
                        (result.qty,basis,entry_fees,result.cost-basis-entry_fees-result.fees,'CLOSED' if closed else 'OPEN',utcnow() if closed else None,p['id']))
                    if closed: self.update_loss_streak(order['account_id'],c)
                    postings=[('CASH',delta),('INVENTORY',-basis),('FEES',result.fees),('REALIZED',basis-result.cost)]
                for i,f in enumerate(result.fills):
                    c.execute('INSERT INTO fills(id,order_id,price,qty,fee) VALUES(%s,%s,%s,%s,%s)',(f'{order_id}:{i}',order_id,f.price,f.qty,f.fee))
                for bucket,amount in postings:
                    c.execute('INSERT INTO postings(group_id,account_id,bucket,amount) VALUES(%s,%s,%s,%s)',(order_id,order['account_id'],bucket,amount))
            c.execute('UPDATE accounts SET cash=cash+%s,reserved=reserved-%s WHERE id=%s',(delta,order['reserved'],order['account_id']))
            c.execute('UPDATE orders SET status=%s,reason=%s,book_version=%s,reserved=0 WHERE id=%s',(result.status,result.reason,result.book_version,order_id))
            self.audit('PAPER_EXECUTION',order['account_id'],{'order_id':order_id,'result':jsonable(result)},c)
    def cancel(self,order_id,reason='CANCELED'):
        from .types import ExecutionResult
        self.commit_execution(order_id,ExecutionResult((), 'CANCELED',reason))
    def reconcile(self):
        with self.connect() as c: rows=c.execute("SELECT id FROM orders WHERE status='PENDING_ARRIVAL'").fetchall()
        for row in rows: self.cancel(row['id'],'RESTART_GAP_NO_INVENTED_FILL')
        self.audit('RESTART_RECONCILED')
    def halt(self,account_id,reason):
        with self.connect() as c:
            a=c.execute('SELECT * FROM accounts WHERE id=%s FOR UPDATE',(account_id,)).fetchone()
            reasons=list(dict.fromkeys(a['halts']+[reason]))
            c.execute('UPDATE accounts SET halts=%s WHERE id=%s',(Jsonb(reasons),account_id))
            if reason=='DAILY_LOSS_LIMIT' and reason not in a['halts']:
                c.execute('UPDATE accounts SET daily_halt_day=%s WHERE id=%s',(risk_day_id(utcnow()),account_id))
            rows=c.execute("SELECT id FROM orders WHERE account_id=%s AND status='PENDING_ARRIVAL'",(account_id,)).fetchall()
            for row in rows:
                c.execute("UPDATE orders SET status='CANCELED',reason=%s,reserved=0 WHERE id=%s",(reason,row['id']))
            c.execute('UPDATE accounts SET reserved=0 WHERE id=%s',(account_id,))
            self.audit('TRADING_HALTED',account_id,{'reasons':reasons},c)
    def resume(self,account_id):
        with self.connect() as c:
            a=c.execute('SELECT * FROM accounts WHERE id=%s FOR UPDATE',(account_id,)).fetchone()
            if 'DAILY_LOSS_LIMIT' in a['halts'] and a['daily_halt_day']==risk_day_id(utcnow()): raise ValueError('Daily loss lock cannot be cleared in the same risk day')
            if any(r in a['halts'] for r in ['STORAGE_LIMIT','PERSISTENCE_FAILED']): raise ValueError('Resolve storage/persistence fault before resuming')
            c.execute("UPDATE accounts SET halts='[]'::jsonb,daily_halt_day=NULL WHERE id=%s",(account_id,))
            self.audit('MANUAL_RESUME',account_id,c=c)
    def decision(self,account_id,market_id,strategy,payload):
        identity=str(uuid.uuid4())
        with self.connect() as c: c.execute('INSERT INTO decisions(id,account_id,market_id,strategy,payload) VALUES(%s,%s,%s,%s,%s)',(identity,account_id,market_id,strategy,Jsonb(jsonable(payload))))
        return identity
    def history(self,table,limit=100):
        if table not in ['orders','fills','positions','decisions','audit','datasets','equity_snapshots','settlements']: raise ValueError('Invalid history type')
        with self.connect() as c: return c.execute(f'SELECT * FROM {table} ORDER BY '+('created_at DESC' if table!='positions' else 'id DESC')+' LIMIT %s',(min(limit,500),)).fetchall()
    def performance(self):
        with self.connect() as c:
            rows=c.execute("SELECT a.id, (SELECT COUNT(*) FROM fills f JOIN orders o ON o.id=f.order_id WHERE o.account_id=a.id) AS fill_count, COALESCE((SELECT -SUM(p.amount) FROM postings p WHERE p.account_id=a.id AND p.bucket IN ('REALIZED','SETTLEMENT_PNL','FEES')),0) AS net_realized_pnl FROM accounts a").fetchall()
        return {row['id']:{'fill_count':row['fill_count'],'net_realized_pnl':row['net_realized_pnl']} for row in rows}
    def get_order(self,identity):
        with self.connect() as c: return c.execute('SELECT * FROM orders WHERE id=%s',(identity,)).fetchone()
    def fills(self,limit=100):
        with self.connect() as c:
            return c.execute('SELECT f.*,o.account_id,o.market_id,o.side,o.book_version,o.scenario FROM fills f JOIN orders o ON o.id=f.order_id ORDER BY f.created_at DESC LIMIT %s',(min(limit,500),)).fetchall()
    def update_loss_streak(self,account_id,c):
        settled=c.execute("SELECT realized_pnl+payout-cost-fees AS pnl FROM positions WHERE account_id=%s AND status IN ('SETTLED','CLOSED') ORDER BY settled_at DESC,id DESC",(account_id,)).fetchall()
        losses=0
        for position in settled:
            if position['pnl']>=0: break
            losses+=1
        previous=c.execute('SELECT consecutive_losses,cooldown_until FROM accounts WHERE id=%s',(account_id,)).fetchone()
        cooldown=previous['cooldown_until'] if previous['consecutive_losses']==losses else utcnow()+timedelta(minutes=30) if losses>=3 else None
        c.execute('UPDATE accounts SET consecutive_losses=%s,cooldown_until=%s WHERE id=%s',(losses,cooldown,account_id))
    def pending_due(self,at):
        with self.connect() as c: return c.execute("SELECT * FROM orders WHERE status='PENDING_ARRIVAL' AND arrival_at<=%s ORDER BY created_at",(at,)).fetchall()
    def save_manifest(self,manifest):
        if manifest:
            with self.connect() as c: c.execute('INSERT INTO datasets(id,filename,sha256,bytes,events,first_at,last_at) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',tuple(manifest[k] for k in ['id','filename','sha256','bytes','events','first_at','last_at']))
    def settle_market(self,market_id,outcome,revision_id,final=False,provenance=None):
        if not final: return
        if outcome not in ['UP','DOWN','VOID']: raise ValueError('Unsupported final outcome')
        with self.connect() as c:
            if c.execute('SELECT id FROM settlements WHERE id=%s',(revision_id,)).fetchone(): return
            rows=c.execute('SELECT DISTINCT account_id FROM positions WHERE market_id=%s ORDER BY account_id',(market_id,)).fetchall()
            for account in rows:
                account_id=account['account_id']
                c.execute('SELECT id FROM accounts WHERE id=%s FOR UPDATE',(account_id,))
                positions=c.execute("SELECT * FROM positions WHERE account_id=%s AND market_id=%s AND status IN ('OPEN','SETTLED') FOR UPDATE",(account_id,market_id)).fetchall()
                for p in positions:
                    payment=p['cost'] if outcome=='VOID' else p['qty'] if p['direction']==outcome else D('0')
                    difference=payment-p['payout']
                    c.execute('UPDATE accounts SET cash=cash+%s WHERE id=%s',(difference,account_id))
                    postings=[('CASH',difference),('SETTLEMENT_PNL',-difference)]
                    if p['status']=='OPEN': postings=[('CASH',payment),('INVENTORY',-p['cost']),('SETTLEMENT_PNL',p['cost']-payment)]
                    for bucket,amount in postings:
                        c.execute('INSERT INTO postings(group_id,account_id,bucket,amount) VALUES(%s,%s,%s,%s)',(revision_id+':'+str(p['id']),account_id,bucket,amount))
                    c.execute("UPDATE positions SET status='SETTLED',payout=%s,settled_at=COALESCE(settled_at,now()) WHERE id=%s",(payment,p['id']))
                self.update_loss_streak(account_id,c)
                self.audit('OFFICIAL_SETTLEMENT_APPLIED',account_id,{'market_id':market_id,'outcome':outcome,'revision':revision_id},c)
            c.execute('INSERT INTO settlements(id,market_id,outcome,payload) VALUES(%s,%s,%s,%s)',(revision_id,market_id,outcome,Jsonb(jsonable({'final':True,'provenance':provenance}))))
    def roll_days(self,marks=None,per_account_marks=None):
        day=risk_day_id(utcnow())
        for account_id in ACCOUNT_IDS:
            account_marks=(per_account_marks or {}).get(account_id,marks) or {}
            state=self.state(account_id,account_marks)
            ready=all((p['market_id'],p['direction']) in account_marks for p in state.positions)
            with self.connect() as c:
                a=c.execute('SELECT * FROM accounts WHERE id=%s FOR UPDATE',(account_id,)).fetchone()
                if a['day_id']==day:continue
                if not ready:
                    if not a['risk_baseline_pending']:
                        c.execute('UPDATE accounts SET risk_baseline_pending=true WHERE id=%s',(account_id,))
                        self.audit('RISK_DAY_BASELINE_DEFERRED',account_id,{'risk_day':day,'prior_baseline':a['day_start']},c)
                    continue
                # After a source gap, never lower the last known baseline and hide losses.
                baseline=max(a['day_start'],state.equity) if a['risk_baseline_pending'] else state.equity
                c.execute('UPDATE accounts SET day_start=%s,day_id=%s,risk_baseline_pending=false WHERE id=%s',(baseline,day,account_id))
                self.audit('RISK_DAY_BASELINE_SET',account_id,{'risk_day':day,'baseline':baseline,'carried_after_gap':a['risk_baseline_pending']},c)
    def save_instrument(self,market):
        import hashlib,json
        raw=jsonable(market.raw); version=hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()
        with self.connect() as c:
            c.execute('INSERT INTO instrument_versions(id,version,raw) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(market.id,version,Jsonb(raw)))

    def held_instruments(self):
        with self.connect() as c:
            return c.execute("SELECT DISTINCT ON (v.id) v.raw FROM instrument_versions v JOIN positions p ON p.market_id=v.id WHERE (p.status='OPEN' AND p.qty>0) OR p.status='SETTLED' ORDER BY v.id,v.created_at DESC").fetchall()
