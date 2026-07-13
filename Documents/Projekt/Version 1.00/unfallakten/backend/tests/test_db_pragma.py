"""
N-09 – SQLite-Härtung: WAL + busy_timeout
==========================================
Regressions-Guard fuer die zwei Betriebs-Invarianten von get_raw_connection():
  - journal_mode = WAL  (Mehrleser/ein Schreiber)
  - busy_timeout = 30000 ms  (Schreib-Lock-Wartezeit vor Kollegen-Rollout)

busy_timeout wird sowohl vom Connect-Parameter timeout=30 als auch vom
expliziten PRAGMA gesetzt (belt-and-suspenders): der PRAGMA haelt die
Invariante auch dann, wenn der Connect-Parameter je entfernt wuerde.
"""

import pytest

from backend.db import database


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "pragma_test.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    return db_file


def test_journal_mode_ist_wal(temp_db):
    conn = database.get_raw_connection()
    try:
        modus = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert modus.lower() == "wal"
    finally:
        conn.close()


def test_busy_timeout_ist_30000(temp_db):
    conn = database.get_raw_connection()
    try:
        wert = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert wert == 30000
    finally:
        conn.close()
