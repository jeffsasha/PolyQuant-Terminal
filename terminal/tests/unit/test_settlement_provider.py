from decimal import Decimal as D
from polyquant.types import MarketTerms,utcnow
from datetime import timedelta


def detail():
    now=utcnow()
    return {'market':{'id':'test','slug':'test','active':True,'closed':True,'status':'MARKET_STATUS_RESOLVED','assetPriceTerms':{'marketType':'ASSET_PRICE_MARKET_TYPE_UP_DOWN','asset':{'symbol':'btc','assetClass':'ASSET_CLASS_CRYPTO'},'indexSymbol':'BRTI','horizon':'15m','windowStart':(now-timedelta(minutes=20)).isoformat(),'windowEnd':(now-timedelta(minutes=5)).isoformat(),'priceToBeat':{'value':'80000','currency':'USD'}}}}


def test_only_matching_resolved_binary_payoffs_are_final():
    from polyquant.settlement import authoritative_outcome
    raw=detail()
    assert authoritative_outcome(raw,{'slug':'test','settlement':1})=='UP'
    assert authoritative_outcome(raw,{'slug':'test','settlement':0})=='DOWN'
    assert authoritative_outcome(raw,{'slug':'wrong','settlement':1}) is None
    assert authoritative_outcome(raw,{'slug':'test','settlement':D('81000')}) is None
    assert authoritative_outcome(raw,{'slug':'test','settlement':True}) is None
    raw['market']['status']='MARKET_STATUS_CLOSED'
    assert authoritative_outcome(raw,{'slug':'test','settlement':1}) is None
