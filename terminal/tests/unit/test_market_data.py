from datetime import timedelta
from decimal import Decimal
import pytest
from polyquant.types import utcnow

def test_book_requires_valid_current_snapshot():
    from polyquant.market_data import normalize_book
    at=utcnow()
    raw={'marketData':{'state':'MARKET_STATE_OPEN','transactTime':at.isoformat(),
         'bids':[{'px':{'value':'0.49','currency':'USD'},'qty':'4'}],
         'offers':[{'px':{'value':'0.51','currency':'USD'},'qty':'5'}]}}
    book=normalize_book('test',raw,{},at)
    assert book.bids[0]==(Decimal('0.49'),Decimal('4'))
    assert book.fresh(at+timedelta(seconds=1))
    assert not book.fresh(at+timedelta(seconds=3))
    raw['marketData']['bids'][0]['px']['value']='0.52'
    with pytest.raises(ValueError): normalize_book('test',raw,{},at)

def test_missing_source_time_is_not_fresh():
    from polyquant.market_data import normalize_book
    at=utcnow()
    book=normalize_book('test',{'marketData':{'state':'MARKET_STATE_OPEN','bids':[],'offers':[]}}, {'age':'24'},at)
    assert book.cache_age==24
    assert not book.fresh(at)

def test_fresh_book_reads_request_distinct_cache_keys_and_keep_actual_age():
    import asyncio
    from types import SimpleNamespace
    from polyquant.venue.us import USDataAdapter
    calls=[];now=utcnow()
    class Transport:
        async def request(self,method,path,params=None):
            calls.append((method,path,params))
            return {'marketData':{'state':'MARKET_STATE_OPEN','transactTime':now.isoformat(),'bids':[],'offers':[]}}, {'age':'20'}
    adapter=object.__new__(USDataAdapter);adapter.transport=Transport()
    market=SimpleNamespace(id='fixture',slug='fixture')
    first,_=asyncio.run(adapter.book(market,fresh=True));asyncio.run(adapter.book(market,fresh=True))
    assert calls[0][0]=='GET' and calls[0][2]!=calls[1][2]
    assert first.cache_age==20 and not first.fresh(now)
