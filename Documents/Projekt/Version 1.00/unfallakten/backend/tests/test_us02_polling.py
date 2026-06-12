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


from unittest.mock import patch
from datetime import datetime, timedelta


class TestHoleAccounts(unittest.TestCase):

    def _setup_db(self):
        conn = _fresh_conn()
        _run_migration_43(conn)
        return conn

    def _mock_gc(self, conn):
        """Gibt einen Mock zurück, der get_connection als Context-Manager simuliert."""
        m = patch("backend.email_import.polling_service.get_connection")
        mock = m.start()
        mock.return_value.__enter__ = lambda s: conn
        mock.return_value.__exit__ = lambda s, *a: None
        self.addCleanup(m.stop)
        return mock

    def test_gibt_vier_accounts_zurueck(self):
        from backend.email_import import polling_service
        conn = self._setup_db()
        self._mock_gc(conn)
        with patch.dict(os.environ, {
            "EMAIL_HOST": "imap.example.com",
            "EMAIL_USER_UNFALL": "unfall@a.de", "EMAIL_PASSWORD_UNFALL": "pw1",
            "EMAIL_USER_TERMIN": "termin@a.de", "EMAIL_PASSWORD_TERMIN": "pw2",
            "EMAIL_USER_BUSSGELD": "b@a.de",    "EMAIL_PASSWORD_BUSSGELD": "pw3",
            "EMAIL_USER_INFO": "info@a.de",     "EMAIL_PASSWORD_INFO": "pw4",
        }):
            accounts = polling_service.hole_accounts()
        self.assertEqual(len(accounts), 4)

    def test_passwort_vorhanden_true_wenn_env_gesetzt(self):
        from backend.email_import import polling_service
        conn = self._setup_db()
        self._mock_gc(conn)
        with patch.dict(os.environ, {
            "EMAIL_HOST": "imap.example.com",
            "EMAIL_USER_UNFALL": "unfall@a.de",
            "EMAIL_PASSWORD_UNFALL": "geheim",
        }):
            accounts = polling_service.hole_accounts()
        unfall = next(a for a in accounts if a["account"] == "unfall")
        self.assertTrue(unfall["passwort_vorhanden"])

    def test_passwort_vorhanden_false_wenn_password_fehlt(self):
        from backend.email_import import polling_service
        conn = self._setup_db()
        self._mock_gc(conn)
        # kein EMAIL_PASSWORD_INFO gesetzt
        env = {"EMAIL_HOST": "imap.example.com"}
        with patch.dict(os.environ, env, clear=True):
            accounts = polling_service.hole_accounts()
        info = next(a for a in accounts if a["account"] == "info")
        self.assertFalse(info["passwort_vorhanden"])

    def test_account_felder_vorhanden(self):
        from backend.email_import import polling_service
        conn = self._setup_db()
        self._mock_gc(conn)
        with patch.dict(os.environ, {"EMAIL_HOST": "x"}, clear=True):
            accounts = polling_service.hole_accounts()
        for feld in ("account", "aktiv", "intervall_min", "passwort_vorhanden",
                     "letzter_lauf", "letzter_status", "letzter_fehler"):
            self.assertIn(feld, accounts[0])


class TestIstFaellig(unittest.TestCase):

    def test_none_letzter_lauf_ist_faellig(self):
        from backend.email_import.polling_service import _ist_faellig
        self.assertTrue(_ist_faellig(None, 5))

    def test_alter_lauf_ist_faellig(self):
        from backend.email_import.polling_service import _ist_faellig
        sechs_min_her = (datetime.now() - timedelta(minutes=6)).isoformat(timespec="seconds")
        self.assertTrue(_ist_faellig(sechs_min_her, 5))

    def test_frischer_lauf_ist_nicht_faellig(self):
        from backend.email_import.polling_service import _ist_faellig
        eine_min_her = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
        self.assertFalse(_ist_faellig(eine_min_her, 5))

    def test_ungueltige_zeitangabe_ist_faellig(self):
        from backend.email_import.polling_service import _ist_faellig
        self.assertTrue(_ist_faellig("kein-datum", 5))


class TestFuehrePollingDurch(unittest.TestCase):

    def _setup(self, env_overrides=None):
        conn = _fresh_conn()
        _run_migration_43(conn)
        env = {
            "EMAIL_HOST": "imap.example.com",
            "EMAIL_USER_UNFALL":   "unfall@a.de",   "EMAIL_PASSWORD_UNFALL":   "pw1",
            "EMAIL_USER_TERMIN":   "termin@a.de",   "EMAIL_PASSWORD_TERMIN":   "pw2",
            "EMAIL_USER_BUSSGELD": "bussgeld@a.de", "EMAIL_PASSWORD_BUSSGELD": "pw3",
            "EMAIL_USER_INFO":     "info@a.de",     "EMAIL_PASSWORD_INFO":     "pw4",
        }
        if env_overrides:
            env.update(env_overrides)
        return conn, env

    def _mock_gc(self, conn, module):
        m = patch(f"{module}.get_connection")
        mock = m.start()
        mock.return_value.__enter__ = lambda s: conn
        mock.return_value.__exit__ = lambda s, *a: None
        self.addCleanup(m.stop)
        return mock

    def test_inaktiver_account_wird_uebersprungen(self):
        from backend.email_import import polling_service
        conn, env = self._setup()
        conn.execute("UPDATE imap_polling_config SET aktiv=0 WHERE account='unfall'")
        self._mock_gc(conn, "backend.email_import.polling_service")
        with patch("backend.email_import.polling_service.fuehre_import_lauf_durch"), \
             patch.dict(os.environ, env, clear=True):
            polling_service.fuehre_polling_durch()
        row = conn.execute(
            "SELECT letzter_lauf FROM imap_polling_config WHERE account='unfall'"
        ).fetchone()
        self.assertIsNone(row["letzter_lauf"])

    def test_account_ohne_passwort_bekommt_fehler_status(self):
        from backend.email_import import polling_service
        conn, env = self._setup({"EMAIL_PASSWORD_INFO": ""})
        self._mock_gc(conn, "backend.email_import.polling_service")
        with patch("backend.email_import.polling_service.fuehre_import_lauf_durch"), \
             patch.dict(os.environ, env, clear=True):
            polling_service.fuehre_polling_durch()
        row = conn.execute(
            "SELECT letzter_status, letzter_fehler FROM imap_polling_config WHERE account='info'"
        ).fetchone()
        self.assertEqual(row["letzter_status"], "fehler")
        self.assertIn("EMAIL_PASSWORD_INFO", row["letzter_fehler"])

    def test_nicht_faelliger_account_wird_uebersprungen(self):
        from backend.email_import import polling_service
        gerade_jetzt = datetime.now().isoformat(timespec="seconds")
        conn, env = self._setup()
        conn.execute(
            "UPDATE imap_polling_config SET letzter_lauf=?, aktiv=1 WHERE account='unfall'",
            (gerade_jetzt,)
        )
        conn.execute("UPDATE imap_polling_config SET aktiv=0 WHERE account != 'unfall'")
        self._mock_gc(conn, "backend.email_import.polling_service")
        with patch("backend.email_import.polling_service.fuehre_import_lauf_durch") as mock_imp, \
             patch.dict(os.environ, env, clear=True):
            polling_service.fuehre_polling_durch()
        mock_imp.assert_not_called()

    def test_faelliger_account_ruft_import_auf(self):
        from backend.email_import import polling_service
        vor_10_min = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
        conn, env = self._setup()
        conn.execute("UPDATE imap_polling_config SET aktiv=0")
        conn.execute(
            "UPDATE imap_polling_config SET aktiv=1, letzter_lauf=? WHERE account='unfall'",
            (vor_10_min,)
        )
        self._mock_gc(conn, "backend.email_import.polling_service")
        with patch("backend.email_import.polling_service.fuehre_import_lauf_durch") as mock_imp, \
             patch.dict(os.environ, env, clear=True):
            polling_service.fuehre_polling_durch()
        mock_imp.assert_called_once()
        cfg = mock_imp.call_args.kwargs.get("imap_config")
        self.assertEqual(cfg["user"], "unfall@a.de")

    def test_fehler_bei_einem_account_bricht_andere_nicht_ab(self):
        from backend.email_import import polling_service
        conn, env = self._setup()
        self._mock_gc(conn, "backend.email_import.polling_service")

        call_count = {"n": 0}
        def mock_import(imap_config=None, **kwargs):
            call_count["n"] += 1
            if imap_config and imap_config["user"].startswith("unfall"):
                raise RuntimeError("IMAP-Fehler")

        with patch("backend.email_import.polling_service.fuehre_import_lauf_durch", side_effect=mock_import), \
             patch.dict(os.environ, env, clear=True):
            polling_service.fuehre_polling_durch()

        self.assertGreater(call_count["n"], 1)


import json


def _make_app():
    os.environ["FLASK_SECRET_KEY"] = "test-us02"
    from backend.app import erstelle_app
    return erstelle_app(test_config={"TESTING": True})


class TestImapPollingEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = _make_app()
        cls.client = cls.app.test_client()
        with cls.app.app_context():
            from backend.db.database import get_connection
            from backend.auth.jwt_handler import erstelle_access_token
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT id FROM benutzer WHERE email=? AND aktiv=1 LIMIT 1",
                    ("schatz@anwalt-offenbach.de",),
                ).fetchone()
                benutzer_id = row["id"] if row else 1
            cls.token = erstelle_access_token(benutzer_id, "admin")

    def _auth(self):
        return {"Authorization": f"Bearer {self.token}"}

    def test_get_gibt_vier_accounts_zurueck(self):
        resp = self.client.get("/system/imap-polling", headers=self._auth())
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertIn("accounts", data)
        self.assertEqual(len(data["accounts"]), 4)
        self.assertEqual(
            {a["account"] for a in data["accounts"]},
            {"unfall", "termin", "bussgeld", "info"},
        )

    def test_get_felder_vollstaendig(self):
        resp = self.client.get("/system/imap-polling", headers=self._auth())
        acc = json.loads(resp.data)["accounts"][0]
        for feld in ("account", "aktiv", "intervall_min", "passwort_vorhanden",
                     "letzter_lauf", "letzter_status", "letzter_fehler"):
            self.assertIn(feld, acc)

    def test_patch_setzt_intervall_auf_alle_accounts(self):
        resp = self.client.patch(
            "/system/imap-polling", json={"intervall_min": 15}, headers=self._auth()
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        for acc in data["accounts"]:
            self.assertEqual(acc["intervall_min"], 15)
        # Cleanup: Intervall zurücksetzen
        self.client.patch(
            "/system/imap-polling", json={"intervall_min": 5}, headers=self._auth()
        )

    def test_patch_deaktiviert_account(self):
        resp = self.client.patch(
            "/system/imap-polling",
            json={"accounts": {"termin": False}},
            headers=self._auth(),
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        termin = next(a for a in data["accounts"] if a["account"] == "termin")
        self.assertFalse(termin["aktiv"])
        # Cleanup
        self.client.patch(
            "/system/imap-polling",
            json={"accounts": {"termin": True}},
            headers=self._auth(),
        )

    def test_patch_ungueltige_intervall_gibt_422(self):
        resp = self.client.patch(
            "/system/imap-polling", json={"intervall_min": 9999}, headers=self._auth()
        )
        self.assertEqual(resp.status_code, 422)

    def test_get_ohne_auth_gibt_401_oder_403(self):
        resp = self.client.get("/system/imap-polling")
        self.assertIn(resp.status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
