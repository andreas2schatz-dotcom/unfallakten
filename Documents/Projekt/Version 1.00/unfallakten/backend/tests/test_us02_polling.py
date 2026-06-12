import os, sys, sqlite3, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("FLASK_SECRET_KEY", "test-us02")

from backend.db.schema_manager import _run_migration_43


def _fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT);"
    )
    return conn


class TestMigration43(unittest.TestCase):

    def test_tabelle_wird_erstellt(self):
        conn = _fresh_conn()
        _run_migration_43(conn)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        self.assertIn("imap_polling_config", tables)

    def test_spalten_vorhanden(self):
        conn = _fresh_conn()
        _run_migration_43(conn)
        spalten = {r[1] for r in conn.execute(
            "PRAGMA table_info(imap_polling_config)"
        ).fetchall()}
        self.assertGreaterEqual(spalten, {
            "account", "aktiv", "intervall_min",
            "letzter_lauf", "letzter_status", "letzter_fehler",
        })

    def test_vier_seed_rows(self):
        conn = _fresh_conn()
        _run_migration_43(conn)
        rows = conn.execute(
            "SELECT account FROM imap_polling_config ORDER BY account"
        ).fetchall()
        self.assertEqual(sorted(r["account"] for r in rows),
                         ["bussgeld", "info", "termin", "unfall"])

    def test_default_aktiv_und_intervall(self):
        conn = _fresh_conn()
        _run_migration_43(conn)
        row = conn.execute(
            "SELECT aktiv, intervall_min FROM imap_polling_config WHERE account='unfall'"
        ).fetchone()
        self.assertEqual(row["aktiv"], 1)
        self.assertEqual(row["intervall_min"], 5)

    def test_idempotent(self):
        conn = _fresh_conn()
        _run_migration_43(conn)
        _run_migration_43(conn)  # darf keinen Fehler werfen
        count = conn.execute(
            "SELECT COUNT(*) FROM imap_polling_config"
        ).fetchone()[0]
        self.assertEqual(count, 4)

    def test_schema_version_eingetragen(self):
        conn = _fresh_conn()
        _run_migration_43(conn)
        row = conn.execute(
            "SELECT version FROM schema_version WHERE version=43"
        ).fetchone()
        self.assertIsNotNone(row)


if __name__ == "__main__":
    unittest.main()
