import asyncio
from ..types import MarketTerms,utcnow
from ..market_data import normalize_book
from .transport import ReadOnlyUSTransport


class USDataAdapter:
    def __init__(self):
        self.transport=ReadOnlyUSTransport()
        self.last_discovery_complete=False

    async def discover(self):
        result=[]; seen=set(); offset=0; self.last_discovery_complete=False
        for _ in range(30):
            payload,_=await self.transport.request('GET','/v1/markets',{
                'categories':'crypto','includeHidden':'true','closed':'false','limit':100,'offset':offset})
            rows=payload.get('markets')
            if not isinstance(rows,list): raise ValueError('Discovery schema changed')
            if not rows: self.last_discovery_complete=True; break
            for raw in rows:
                identity=str(raw.get('id'))
                if identity in seen: raise ValueError('Duplicate discovery records; inventory is not reconciled')
                seen.add(identity)
                try: market=MarketTerms.from_raw(raw)
                except (ValueError,KeyError,TypeError,AttributeError): continue
                if market.end>utcnow() and market.active and not market.closed: result.append(market)
            offset+=len(rows)
            await asyncio.sleep(.1)
        if not self.last_discovery_complete: raise ValueError('Discovery page cap reached')
        return result

    async def book(self,market):
        raw,headers=await self.transport.request('GET',f'/v1/markets/{market.slug}/book')
        at=utcnow()
        return normalize_book(market.id,raw,headers,at),raw

    async def close(self): await self.transport.close()
