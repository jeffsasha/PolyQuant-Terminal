import hashlib
from dataclasses import replace
from pathlib import Path
from fastapi.testclient import TestClient
from polyquant.runtime import Runtime
from polyquant.config import Settings
from polyquant.types import utcnow
from test_fees_execution_risk import context


def test_authenticated_preview_place_fill_exit_idempotency_and_cancel(store,tmp_path,monkeypatch):
    from polyquant.api import create_app
    now,market,book,_=context();instances=[]
    salt='11'*16;digest=hashlib.scrypt(b'fixture-password',salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    monkeypatch.setenv('POLYQUANT_PASSWORD_HASH',salt+':'+digest)
    class FixtureVenue:
        async def book(self,market,fresh=False):
            at=utcnow();return replace(book,source_at=at,received_at=at,version=at.isoformat()),{'fixture':True}
        async def close(self):pass
    class TestRuntime(Runtime):
        async def start(self):
            await self.venue.close();self.venue=FixtureVenue();self.markets[market.id]=market
            self.store.acquire_writer();instances.append(self)
    app=create_app(store,Settings(store.dsn,tmp_path),TestRuntime)
    with TestClient(app,base_url='http://127.0.0.1:8000') as c:
        origin={'Origin':'http://127.0.0.1:3000'}
        login=c.post('/login',headers=origin,json={'password':'fixture-password'});assert login.status_code==200
        headers={**origin,'x-csrf-token':login.json()['csrf']}
        payload={'id':'api-manual-buy','account_id':'manual','market_id':market.id,'side':'BUY_UP','qty':'1','limit':'0.52','scenario':'optimistic'}
        preview=c.post('/paper/preview',headers=headers,json=payload)
        assert preview.status_code==200 and preview.json()['allowed'],preview.json()
        assert preview.json()['estimate']['qty']=='1'
        placed=c.post('/paper/orders',headers=headers,json=payload)
        assert placed.status_code==200 and placed.json()['status']=='PENDING_ARRIVAL',placed.json()
        c.portal.call(instances[0].process_arrivals_once)
        assert c.get('/paper/orders/api-manual-buy').json()['status']=='FILLED'
        assert store.state('manual').positions[0]['qty']==1
        assert c.post('/paper/orders',headers=headers,json=payload).json()['status']=='FILLED'
        sell={**payload,'id':'api-manual-cancel','side':'SELL_UP','limit':'0.48'}
        assert c.post('/paper/orders',headers=headers,json=sell).json()['allowed']
        assert c.post('/paper/orders/api-manual-cancel/cancel',headers=headers).json()['status']=='CANCELED'
        assert store.state('manual').positions[0]['qty']==1
        sell['id']='api-manual-exit'
        assert c.post('/paper/orders',headers=headers,json=sell).json()['allowed']
        c.portal.call(instances[0].process_arrivals_once)
        assert c.get('/paper/orders/api-manual-exit').json()['status']=='FILLED'
        assert not store.state('manual').positions
        blocked={**payload,'id':'api-strategy-blocked','account_id':'probability'}
        assert 'REFERENCE_RECONCILIATION_FAILED' in c.post('/paper/preview',headers=headers,json=blocked).json()['reasons']
        assert store.state('probability').cash==1000
