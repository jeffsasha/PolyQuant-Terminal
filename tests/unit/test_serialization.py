from decimal import Decimal
from polyquant.types import jsonable,ReferenceSnapshot,utcnow


def test_nested_reference_is_structured_not_a_python_repr():
    result=jsonable({'reference':ReferenceSnapshot(value=Decimal('81584.98'),source_at=utcnow())})
    assert isinstance(result['reference'],dict)
    assert result['reference']['value']=='81584.98'
    assert result['reference']['validated'] is False
