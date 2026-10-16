import asyncio,hashlib,hmac,json,os,uuid
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI,Request,Response,HTTPException,Depends
from fastapi.responses import JSONResponse,StreamingResponse
from pydantic import BaseModel,ConfigDict,Field
from .config import Settings
from .store import Store
from .runtime import Runtime
from .auth import Sessions,verify_password
from .types import OrderIntent,decimal,jsonable,utcnow
from .replay import Replay

class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password:str=Field(max_length=256)
class AccountCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    account_id:Literal['probability','momentum','book']='probability'
class PaperTicket(AccountCommand):
    id:str=Field(min_length=8,max_length=100)
    market_id:str=Field(max_length=80)
    side:Literal['BUY_UP','BUY_DOWN','SELL_UP','SELL_DOWN']
    qty:str=Field(max_length=24)
    limit:str=Field(max_length=24)
    scenario:Literal['optimistic','base','conservative','stress']='conservative'


def create_app(store=None,settings=None,runtime_factory=Runtime):
    settings=settings or Settings.from_env(); store=store or Store(settings.database_url)
    sessions=Sessions(store)
    @asynccontextmanager
    async def lifespan(app):
        store.migrate(); store.bootstrap()
        app.state.runtime=runtime_factory(store,settings)
        await app.state.runtime.start()
        yield
        await app.state.runtime.close()
    app=FastAPI(title='PolyQuant Paper Terminal',lifespan=lifespan,docs_url=None,redoc_url=None)
    @app.middleware('http')
    async def boundary(request,call_next):
        if request.headers.get('host') not in ['127.0.0.1:8000','127.0.0.1:3000','localhost:8000','localhost:3000','backend:8000']:
            return JSONResponse({'detail':'Invalid local host'},400)
        if request.method not in ['GET','HEAD','OPTIONS'] and request.headers.get('origin')!=settings.web_origin:
            return JSONResponse({'detail':'Origin denied'},403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        return response
    @app.exception_handler(Exception)
    async def internal_error(request,error):
        return JSONResponse({'detail':'Local service error. Check data health and private local logs.'},500)
    def authenticated(request:Request):
        session=sessions.get(request.cookies.get('polyquant_session'))
        if not session: raise HTTPException(401,'Sign in required')
        if request.method not in ['GET','HEAD'] and not hmac.compare_digest(request.headers.get('x-csrf-token',''),session['csrf']):
            raise HTTPException(403,'CSRF validation failed')
        return session
    @app.get('/health')
    def health():
        with store.connect() as c: c.execute('SELECT 1')
        return {'status':'running','mode':'PAPER','reference_validated':False,'trading_ready':False}
    @app.post('/login')
    def login(payload:Login,request:Request,response:Response):
        ip=request.client.host if request.client else 'local'
        if sessions.limited(ip): raise HTTPException(429,'Too many attempts. Try again in one minute.')
        if not verify_password(payload.password,os.environ.get('POLYQUANT_PASSWORD_HASH','')):
            sessions.failed(ip); raise HTTPException(401,'Incorrect password')
        token,csrf=sessions.create(ip)
        response.set_cookie('polyquant_session',token,httponly=True,samesite='strict',max_age=43200,path='/')
        store.audit('LOCAL_LOGIN')
        return {'csrf':csrf,'mode':'PAPER'}
    @app.get('/session')
    def session(value=Depends(authenticated)): return {'csrf':value['csrf'],'mode':'PAPER'}
    @app.post('/logout')
    def logout(request:Request,response:Response,value=Depends(authenticated)):
        sessions.delete(request.cookies['polyquant_session']); response.delete_cookie('polyquant_session'); return {'ok':True}
    @app.get('/state')
    def state(value=Depends(authenticated)): return app.state.runtime.snapshot()
    @app.get('/events')
    async def events(request:Request,value=Depends(authenticated)):
        async def stream():
            while not await request.is_disconnected():
                if not sessions.get(request.cookies.get('polyquant_session')): break
                state=app.state.runtime.snapshot()
                yield 'event: state\ndata: '+json.dumps(state)+'\n\n'
                await asyncio.sleep(2)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'X-Accel-Buffering':'no'})
    @app.get('/candles')
    async def candles(timeframe:Literal['1m','5m','15m','1h']='1m',value=Depends(authenticated)):
        try: rows=await app.state.runtime.spot_provider.candles(timeframe)
        except Exception: return {'source':'Coinbase BTC-USD spot','status':'UNAVAILABLE','candles':[]}
        return {'source':'Coinbase BTC-USD spot','status':'REAL_DATA','candles':rows}
    @app.get('/decisions/{identity}')
    def decision(identity:str,value=Depends(authenticated)):
        with store.connect() as c: row=c.execute('SELECT * FROM decisions WHERE id=%s',(identity,)).fetchone()
        if not row: raise HTTPException(404,'Decision not found')
        return jsonable(row)
    @app.post('/paper/start')
    def start(value=Depends(authenticated)):
        raise HTTPException(409,'Reference reconciliation failed. Reference-dependent strategies remain disabled.')
    @app.post('/paper/stop')
    def stop(payload:AccountCommand,value=Depends(authenticated)):
        store.halt(payload.account_id,'MANUAL_STOP'); return {'status':'HALTED','mode':'PAPER'}
    @app.post('/paper/pause')
    def pause(payload:AccountCommand,value=Depends(authenticated)):
        store.halt(payload.account_id,'MANUAL_PAUSE'); return {'status':'PAUSED'}
    @app.post('/paper/resume')
    def resume(payload:AccountCommand,value=Depends(authenticated)):
        try: store.resume(payload.account_id)
        except ValueError as error: raise HTTPException(409,str(error))
        return {'status':'REFERENCE_BLOCKED','reference_validated':False}
    def intent(payload):
        try:
            qty=decimal(payload.qty); price=decimal(payload.limit)
            if qty<=0 or qty>1000000 or not 0<price<1: raise ValueError('Invalid quantity or price')
        except ValueError as error: raise HTTPException(422,str(error))
        return OrderIntent(payload.id,payload.account_id,payload.market_id,payload.side,qty,price,'manual',None,payload.scenario)
    @app.post('/paper/preview')
    def preview(payload:PaperTicket,value=Depends(authenticated)):
        return jsonable(app.state.runtime.engine.preview(intent(payload)))
    @app.post('/paper/orders')
    def order(payload:PaperTicket,value=Depends(authenticated)):
        return jsonable(app.state.runtime.engine.submit(intent(payload)))
    @app.get('/datasets/{identity}/replay')
    def replay(identity:str,value=Depends(authenticated)):
        with store.connect() as c: manifest=c.execute('SELECT * FROM datasets WHERE id=%s',(identity,)).fetchone()
        if not manifest: raise HTTPException(404,'Dataset not found')
        try: rows=app.state.runtime.recorder.read(manifest)
        except ValueError as error: raise HTTPException(409,str(error))
        return Replay().run(rows)
    @app.post('/recordings/seal')
    def seal(value=Depends(authenticated)):
        manifest=app.state.runtime.recorder.seal(); store.save_manifest(manifest)
        return {'manifest':manifest}
    return app


app=create_app()
