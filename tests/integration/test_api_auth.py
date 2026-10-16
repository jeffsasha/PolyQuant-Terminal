import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from polyquant.config import Settings

class FixtureRuntime:
    def __init__(self,store,settings): self.store=store; self.settings=settings; self.collection=True
    async def start(self): pass
    async def close(self): pass
    def snapshot(self): return {'mode':'PAPER','reference_validated':False,'fixture':True}

def client_for(store,monkeypatch):
    from polyquant.api import create_app
    salt='00'*16
    digest=hashlib.scrypt(b'fixture-password',salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    monkeypatch.setenv('POLYQUANT_PASSWORD_HASH',salt+':'+digest)
    return TestClient(create_app(store,Settings(store.dsn,Path('.local/test-api')),FixtureRuntime),base_url='http://127.0.0.1:8000')

def test_login_csrf_origin_and_live_routes(store,monkeypatch):
    with client_for(store,monkeypatch) as client:
        assert client.get('/state').status_code==401
        origin={'Origin':'http://127.0.0.1:3000'}
        assert client.post('/login',json={'password':'wrong'},headers=origin).status_code==401
        response=client.post('/login',json={'password':'fixture-password'},headers=origin)
        assert response.status_code==200
        csrf=response.json()['csrf']
        assert 'httponly' in response.headers['set-cookie'].lower()
        assert client.get('/state').json()['reference_validated'] is False
        assert client.post('/paper/stop',json={'account_id':'probability'},headers=origin).status_code==403
        headers={**origin,'X-CSRF-Token':csrf}
        assert client.post('/paper/stop',json={'account_id':'probability'},headers=headers).status_code==200
        assert store.state('probability').halts==('MANUAL_STOP',)
        assert client.post('/paper/start',headers=headers).status_code==409
        assert client.post('/orders',json={},headers=headers).status_code==404
        assert client.post('/paper/orders',json={'mode':'LIVE'},headers=headers).status_code==422
        assert client.post('/logout',headers={**headers,'Origin':'https://evil.test'}).status_code==403
        assert client.get('/state',headers={'Host':'evil.test'}).status_code==400

def test_login_rate_limit(store,monkeypatch):
    with client_for(store,monkeypatch) as client:
        for _ in range(5): assert client.post('/login',json={'password':'wrong'},headers={'Origin':'http://127.0.0.1:3000'}).status_code==401
        assert client.post('/login',json={'password':'wrong'},headers={'Origin':'http://127.0.0.1:3000'}).status_code==429
