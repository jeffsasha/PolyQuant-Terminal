from datetime import datetime,timezone
from decimal import Decimal
import pytest

def test_money_validation_and_utc():
    from polyquant.types import decimal,timestamp
    assert decimal('0.10')+decimal('0.20')==Decimal('0.30')
    for value in ['NaN','Infinity','-Infinity',0.1]:
        with pytest.raises(ValueError): decimal(value)
    with pytest.raises(ValueError): timestamp('2026-10-16T18:00:00')

def test_risk_day_dst_and_frozen_hash():
    from polyquant.clock import risk_day_id
    from polyquant.types import ExperimentConfig
    assert risk_day_id(datetime(2026,10,16,20,59,tzinfo=timezone.utc))=='2026-10-15'
    assert risk_day_id(datetime(2026,10,16,21,0,tzinfo=timezone.utc))=='2026-10-16'
    assert risk_day_id(datetime(2026,11,2,21,59,tzinfo=timezone.utc))=='2026-11-01'
    assert risk_day_id(datetime(2026,11,2,22,0,tzinfo=timezone.utc))=='2026-11-02'
    assert ExperimentConfig().hash==ExperimentConfig().hash

def test_typed_discovery_rejects_duration_mismatch():
    from polyquant.types import MarketTerms
    raw={'id':'fixture','slug':'do-not-parse','active':True,'closed':False,'assetPriceTerms':{
        'marketType':'ASSET_PRICE_MARKET_TYPE_UP_DOWN','asset':{'assetClass':'ASSET_CLASS_CRYPTO','symbol':'btc'},
        'indexSymbol':'BRTI','horizon':'15m','windowStart':'2026-10-16T18:00:00Z','windowEnd':'2026-10-16T18:15:00Z','priceToBeat':{'value':'80000','currency':'USD'}}}
    assert MarketTerms.from_raw(raw).horizon=='15m'
    raw['assetPriceTerms']['horizon']='1h'
    with pytest.raises(ValueError): MarketTerms.from_raw(raw)
