import hashlib,hmac,secrets
from datetime import timedelta
from .types import utcnow


def verify_password(password,encoded):
    try:
        salt,expected=encoded.split(':')
        actual=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
        return hmac.compare_digest(actual,expected)
    except (ValueError,TypeError): return False


class Sessions:
    def __init__(self,store): self.store=store; self.failures={}
    def limited(self,ip):
        now=utcnow(); self.failures[ip]=[at for at in self.failures.get(ip,[]) if now-at<timedelta(minutes=1)]
        return len(self.failures[ip])>=5
    def failed(self,ip): self.failures.setdefault(ip,[]).append(utcnow())
    def create(self,ip):
        token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
        with self.store.connect() as c:
            c.execute('INSERT INTO sessions(hash,csrf,expires_at) VALUES(%s,%s,%s)',
                      (hashlib.sha256(token.encode()).hexdigest(),csrf,utcnow()+timedelta(hours=12)))
        self.failures.pop(ip,None)
        return token,csrf
    def get(self,token):
        if not token: return None
        with self.store.connect() as c:
            return c.execute('SELECT csrf,expires_at FROM sessions WHERE hash=%s AND expires_at>now()',
                             (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    def delete(self,token):
        with self.store.connect() as c: c.execute('DELETE FROM sessions WHERE hash=%s',(hashlib.sha256(token.encode()).hexdigest(),))
