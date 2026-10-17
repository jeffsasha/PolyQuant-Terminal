import hashlib,json
from .types import BookSnapshot,decimal,timestamp


def normalize_book(market_id,raw,headers,received_at):
    data=raw.get('marketData') or {}
    def levels(name):
        rows=[]
        for row in data.get(name,[]):
            if row['px'].get('currency')!='USD': raise ValueError('Unsupported book currency')
            rows.append((decimal(str(row['px']['value'])),decimal(str(row['qty']))))
        return tuple(rows)
    source=timestamp(data['transactTime']) if data.get('transactTime') else None
    version=hashlib.sha256(json.dumps(raw,sort_keys=True,default=str).encode()).hexdigest()
    return BookSnapshot(market_id,levels('bids'),levels('offers'),source,received_at,version,
                        data.get('state',''),int(headers['age']) if headers.get('age','').isdigit() else None)
