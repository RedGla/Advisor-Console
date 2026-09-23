"""Exercise duplicate consolidation and uniqueness in an isolated PG schema."""
import importlib.util
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pytest

from database import engine


def test_duplicate_migration_preserves_totals_and_enforces_uniqueness():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/8b2c3d4e5f6a_unique_daily_usage_counter.py"
    spec = importlib.util.spec_from_file_location("quota_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    # All DDL is rolled back, including the temporary schema. No global schema
    # downgrade or production data is involved in this migration test.
    schema = "migration_test_" + uuid.uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            connection.execute(text("""
                CREATE TABLE usage_counters (
                    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, date_str TEXT NOT NULL,
                    messages_today INTEGER, tokens_today INTEGER, est_spend_today FLOAT
                )
            """))
            connection.execute(text("""
                INSERT INTO usage_counters VALUES
                ('a', 'u1', '2026-09-23', 1, 10, 0.1),
                ('b', 'u1', '2026-09-23', 2, 20, 0.2),
                ('c', 'u1', '2026-09-23', NULL, NULL, NULL),
                ('d', 'u1', '2026-09-24', 4, 40, 0.4),
                ('e', 'u2', '2026-09-23', 5, 50, 0.5)
            """))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            rows = connection.execute(text("SELECT * FROM usage_counters ORDER BY id")).all()
            assert len(rows) == 3
            assert rows[0][:5] == ('a', 'u1', '2026-09-23', 3, 30)
            assert rows[0][5] == pytest.approx(0.3)
            assert rows[1][:5] == ('d', 'u1', '2026-09-24', 4, 40)
            assert rows[2][:5] == ('e', 'u2', '2026-09-23', 5, 50)
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(text("""
                        INSERT INTO usage_counters VALUES ('f', 'u1', '2026-09-23', 0, 0, 0)
                    """))
            with Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            connection.execute(text("""
                INSERT INTO usage_counters VALUES ('f', 'u1', '2026-09-23', 0, 0, 0)
            """))
        finally:
            transaction.rollback()
