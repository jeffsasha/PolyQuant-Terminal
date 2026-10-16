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
