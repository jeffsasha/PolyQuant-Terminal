import os
from pathlib import Path
import pytest

@pytest.fixture
def store():
    from polyquant.store import Store
    dsn=os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        values=dict(line.split('=',1) for line in Path('.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
        dsn=values['DATABASE_URL'].rsplit('/',1)[0]+'/polyquant_test'
    assert dsn.rsplit('/',1)[-1]=='polyquant_test','Tests refuse a non-test database'
    db=Store(dsn); db.migrate()
    with db.connect() as c:
        c.execute('TRUNCATE accounts, orders, fills, positions, postings, decisions, audit, sessions, datasets, settlements, equity_snapshots CASCADE')
    db.bootstrap()
    yield db
    db.close()
