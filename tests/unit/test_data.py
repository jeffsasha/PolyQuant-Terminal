
def test_cached_snapshot_is_not_fresh_even_with_recent_source_timestamp():
    from polyquant.types import BookSnapshot,utcnow
    from decimal import Decimal as D
    now=utcnow()
    book=BookSnapshot('fixture',((D('.4'),D('1')),),((D('.5'),D('1')),),now,now,'cached',cache_age=30)
    assert not book.fresh(now)
