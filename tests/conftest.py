import os
from pathlib import Path
import pytest

@pytest.fixture
def store():
    from polyquant.store import Store
    dsn=os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        with Path('.env').open() as source:
            database=next(line.strip().split('=',1)[1] for line in source if line.startswith('DATABASE_URL='))
        dsn=database.rsplit('/',1)[0]+'/polyquant_test'
    assert dsn.rsplit('/',1)[-1]=='polyquant_test','Tests refuse a non-test database'
    db=Store(dsn); db.migrate()
    with db.connect() as c:
        c.execute('TRUNCATE accounts, orders, fills, positions, postings, decisions, audit, sessions, datasets, settlements, equity_snapshots CASCADE')
    db.bootstrap()
    yield db
    db.close()
