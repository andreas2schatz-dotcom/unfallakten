# US-02 IMAP Auto-Polling – Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatisches 5-Minuten-IMAP-Polling für 4 Kanzlei-Accounts (unfall@, termin@, bussgeld@, info@) mit per-Account-Toggle und konfigurierbarem Intervall im Health-Dashboard.

**Architecture:** Ein APScheduler-Job tickt jede Minute; er liest aus `imap_polling_config` welche Accounts aktiv sind und wann sie zuletzt liefen. Pro Account wird `fuehre_import_lauf_durch()` mit account-spezifischer IMAP-Config aufgerufen wenn der Account fällig ist. Intervall und Toggles werden über zwei neue Endpoints konfiguriert und im Health-Dashboard angezeigt.

**Tech Stack:** Python 3.11, Flask, APScheduler (flask-apscheduler), SQLite, React 18

---

## File-Map

| Aktion  | Datei                                              | Zweck                                      |
|---------|---------------------------------------------------|--------------------------------------------|
| CREATE  | `backend/email_import/polling_service.py`         | Polling-Logik: hole_accounts, fuehre_polling_durch |
| MODIFY  | `backend/db/schema_manager.py`                    | Migration 43: imap_polling_config          |
| MODIFY  | `backend/routers/system_routes.py`                | GET + PATCH /system/imap-polling           |
| MODIFY  | `backend/system/health_service.py`                | get_status: imap als Account-Array         |
| MODIFY  | `backend/app.py`                                  | Zweiter APScheduler-Job                    |
| MODIFY  | `frontend/src/api.js`                             | apiSystem.getImapPolling + patchImapPolling|
| MODIFY  | `frontend/src/views/EinstellungenView.jsx`        | IMAP-Polling UI im system_status Tab       |
| MODIFY  | `.env.example`                                    | Neue Account-Variablen dokumentieren       |
| CREATE  | `backend/tests/test_us02_polling.py`              | Alle Backend-Tests                         |

---

## Task 1: Schema-Migration 43 — Tabelle `imap_polling_config`

**Files:**
- Modify: `backend/db/schema_manager.py`
- Create: `backend/tests/test_us02_polling.py`

- [ ] **Schritt 1: Testdatei anlegen (schlägt fehl)**

Neue Datei: `backend/tests/test_us02_polling.py`

```python
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
```

- [ ] **Schritt 2: Test ausführen — muss FAIL sein**

```
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten"
python -m pytest backend/tests/test_us02_polling.py -v
```

Erwartetes Ergebnis: `ImportError: cannot import name '_run_migration_43'`

- [ ] **Schritt 3a: MIGRATIONS-Dict in schema_manager.py erweitern**

In `backend/db/schema_manager.py` die Zeile:
```python
    42: "-- migration_42_eml_dateityp",  # Handled by _run_migration_42
}
```
ersetzen durch:
```python
    42: "-- migration_42_eml_dateityp",  # Handled by _run_migration_42
    43: "-- migration_43_imap_polling",  # Handled by _run_migration_43
}
```

- [ ] **Schritt 3b: Funktion `_run_migration_43` einfügen**

In `backend/db/schema_manager.py` direkt nach `_run_migration_42()` einfügen:

```python
def _run_migration_43(conn: sqlite3.Connection) -> None:
    """Erstellt imap_polling_config Tabelle mit 4 Account-Seed-Rows."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS imap_polling_config (
            account        TEXT PRIMARY KEY,
            aktiv          INTEGER NOT NULL DEFAULT 1,
            intervall_min  INTEGER NOT NULL DEFAULT 5,
            letzter_lauf   TEXT,
            letzter_status TEXT,
            letzter_fehler TEXT
        );
        INSERT OR IGNORE INTO imap_polling_config (account, aktiv, intervall_min)
            VALUES ('unfall',   1, 5);
        INSERT OR IGNORE INTO imap_polling_config (account, aktiv, intervall_min)
            VALUES ('termin',   1, 5);
        INSERT OR IGNORE INTO imap_polling_config (account, aktiv, intervall_min)
            VALUES ('bussgeld', 1, 5);
        INSERT OR IGNORE INTO imap_polling_config (account, aktiv, intervall_min)
            VALUES ('info',     1, 5);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (43, "Migration 43 – imap_polling_config (US-02)"),
    )
    logger.info("Migration 43: imap_polling_config angelegt.")
```

- [ ] **Schritt 3c: Dispatch in `run_migrations()` eintragen**

In der elif-Kette in `run_migrations()`, nach `elif version == 42: _run_migration_42(conn)` einfügen:

```python
            elif version == 43:
                _run_migration_43(conn)
```

- [ ] **Schritt 4: Test ausführen — muss PASS sein**

```
python -m pytest backend/tests/test_us02_polling.py::TestMigration43 -v
```

Erwartetes Ergebnis: 6 × PASSED

- [ ] **Schritt 5: Commit**

```
git add backend/db/schema_manager.py backend/tests/test_us02_polling.py
git commit -m "feat(db): Migration 43 – imap_polling_config Tabelle (US-02)"
```

---

## Task 2: polling_service.py — `hole_accounts()` und Hilfsfunktionen

**Files:**
- Create: `backend/email_import/polling_service.py`
- Modify: `backend/tests/test_us02_polling.py`

- [ ] **Schritt 1: Tests anfügen (schlagen fehl)**

An `backend/tests/test_us02_polling.py` **anhängen**:

```python
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
```

- [ ] **Schritt 2: Test ausführen — muss FAIL sein**

```
python -m pytest backend/tests/test_us02_polling.py::TestHoleAccounts backend/tests/test_us02_polling.py::TestIstFaellig -v
```

Erwartetes Ergebnis: `ModuleNotFoundError: No module named 'backend.email_import.polling_service'`

- [ ] **Schritt 3: polling_service.py erstellen**

Neue Datei: `backend/email_import/polling_service.py`

```python
"""
US-02 – IMAP Auto-Polling Service
===================================
Verwaltet das automatische Polling für 4 IMAP-Accounts.
Job-Funktion fuehre_polling_durch() wird von APScheduler jede Minute aufgerufen.
"""

import os
import logging
from datetime import datetime

from ..db.database import get_connection
from .import_service import fuehre_import_lauf_durch

logger = logging.getLogger(__name__)

ACCOUNTS = ["unfall", "termin", "bussgeld", "info"]


def _env(key: str) -> str:
    return os.environ.get(key, "").strip()


def _imap_config_fuer_account(account: str) -> dict | None:
    """Baut IMAP-Config für einen Account aus ENV-Vars. None wenn Credentials fehlen."""
    host     = _env("EMAIL_HOST")
    user     = _env(f"EMAIL_USER_{account.upper()}")
    password = _env(f"EMAIL_PASSWORD_{account.upper()}")
    if not host or not user or not password:
        return None
    return {
        "host":      host,
        "port":      int(_env("EMAIL_PORT") or "993"),
        "user":      user,
        "password":  password,
        "folder":    _env("EMAIL_FOLDER") or "INBOX",
        "max_fetch": int(_env("EMAIL_MAX_FETCH") or "50"),
        "ssl":       (_env("EMAIL_PORT") or "993") != "143",
    }


def hole_accounts() -> list[dict]:
    """Liest alle Account-Rows aus DB und ergänzt ENV-Credential-Status."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT account, aktiv, intervall_min, letzter_lauf, "
            "       letzter_status, letzter_fehler "
            "FROM imap_polling_config ORDER BY account"
        ).fetchall()
    result = []
    for row in rows:
        account = row["account"]
        cfg = _imap_config_fuer_account(account)
        result.append({
            "account":            account,
            "aktiv":              bool(row["aktiv"]),
            "intervall_min":      row["intervall_min"],
            "passwort_vorhanden": cfg is not None,
            "letzter_lauf":       row["letzter_lauf"],
            "letzter_status":     row["letzter_status"],
            "letzter_fehler":     row["letzter_fehler"],
        })
    return result


def _ist_faellig(letzter_lauf: str | None, intervall_min: int) -> bool:
    """True wenn Account noch nie lief (None) oder Intervall abgelaufen."""
    if letzter_lauf is None:
        return True
    try:
        letzter = datetime.fromisoformat(letzter_lauf)
        return (datetime.now() - letzter).total_seconds() >= intervall_min * 60
    except (ValueError, TypeError):
        return True


def _schreibe_status(account: str, status: str, fehler: str | None) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE imap_polling_config "
            "SET letzter_lauf=?, letzter_status=?, letzter_fehler=? "
            "WHERE account=?",
            (datetime.now().isoformat(timespec="seconds"), status, fehler, account),
        )


def fuehre_polling_durch() -> None:
    """APScheduler-Job: importiert für jeden fälligen aktiven Account."""
    try:
        accounts = hole_accounts()
    except Exception as e:
        logger.error("IMAP-Polling: DB-Fehler beim Laden der Accounts: %s", e)
        return

    for acc in accounts:
        account = acc["account"]
        if not acc["aktiv"]:
            continue
        if not acc["passwort_vorhanden"]:
            _schreibe_status(
                account, "fehler",
                f"EMAIL_PASSWORD_{account.upper()} nicht in .env gesetzt",
            )
            continue
        if not _ist_faellig(acc["letzter_lauf"], acc["intervall_min"]):
            continue

        logger.info("IMAP-Polling: Starte Import für %s", account)
        try:
            cfg = _imap_config_fuer_account(account)
            fuehre_import_lauf_durch(imap_config=cfg)
            _schreibe_status(account, "ok", None)
            logger.info("IMAP-Polling: %s erfolgreich.", account)
        except Exception as e:
            logger.error("IMAP-Polling: Fehler bei %s: %s", account, e)
            _schreibe_status(account, "fehler", str(e)[:500])
```

- [ ] **Schritt 4: Tests ausführen — müssen PASS sein**

```
python -m pytest backend/tests/test_us02_polling.py::TestHoleAccounts backend/tests/test_us02_polling.py::TestIstFaellig -v
```

Erwartetes Ergebnis: 8 × PASSED

- [ ] **Schritt 5: Commit**

```
git add backend/email_import/polling_service.py backend/tests/test_us02_polling.py
git commit -m "feat(email): polling_service – hole_accounts, _ist_faellig (US-02)"
```

---

## Task 3: `fuehre_polling_durch()` — Scheduler-Logik testen

**Files:**
- Modify: `backend/tests/test_us02_polling.py`

- [ ] **Schritt 1: Tests anfügen**

An `backend/tests/test_us02_polling.py` **anhängen**:

```python
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
```

- [ ] **Schritt 2: Tests ausführen — müssen PASS sein**

```
python -m pytest backend/tests/test_us02_polling.py::TestFuehrePollingDurch -v
```

Erwartetes Ergebnis: 5 × PASSED

- [ ] **Schritt 3: Commit**

```
git add backend/tests/test_us02_polling.py
git commit -m "test(email): fuehre_polling_durch Scheduler-Logik Tests (US-02)"
```

---

## Task 4: Backend-Endpoints `GET` + `PATCH /system/imap-polling`

**Files:**
- Modify: `backend/routers/system_routes.py`
- Modify: `backend/tests/test_us02_polling.py`

- [ ] **Schritt 1: Endpoint-Tests anfügen**

An `backend/tests/test_us02_polling.py` **anhängen**:

```python
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
            resp = cls.client.post("/auth/login", json={
                "email": "schatz@anwalt-offenbach.de",
                "passwort": "As155255",
            })
            data = json.loads(resp.data)
            cls.token = data.get("access_token", "")

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
```

- [ ] **Schritt 2: Tests ausführen — müssen FAIL sein**

```
python -m pytest backend/tests/test_us02_polling.py::TestImapPollingEndpoints -v
```

Erwartetes Ergebnis: 404 (Endpoints noch nicht vorhanden)

- [ ] **Schritt 3: Flask-Import in system_routes.py erweitern**

In `backend/routers/system_routes.py` die erste Import-Zeile:
```python
from flask import Blueprint, jsonify
```
ersetzen durch:
```python
from flask import Blueprint, jsonify, request
```

- [ ] **Schritt 4: Endpoints in system_routes.py einfügen**

Nach dem bestehenden `/system/ramicro/retry`-Endpoint anfügen:

```python
@system_bp.route("/system/imap-polling", methods=["GET"])
@login_erforderlich
def imap_polling_status():
    from ..email_import.polling_service import hole_accounts
    return jsonify({"accounts": hole_accounts()})


@system_bp.route("/system/imap-polling", methods=["PATCH"])
@login_erforderlich
def imap_polling_speichern():
    from ..email_import.polling_service import hole_accounts
    from ..db.database import get_connection
    daten = request.get_json(silent=True) or {}
    intervall_min = daten.get("intervall_min")
    accounts_map  = daten.get("accounts", {})
    ERLAUBTE = {"unfall", "termin", "bussgeld", "info"}

    if intervall_min is not None:
        try:
            intervall_min = int(intervall_min)
            if not (1 <= intervall_min <= 1440):
                return jsonify({"fehler": "intervall_min muss zwischen 1 und 1440 liegen."}), 422
        except (TypeError, ValueError):
            return jsonify({"fehler": "intervall_min muss eine Zahl sein."}), 422

    with get_connection() as conn:
        for account, aktiv in accounts_map.items():
            if account not in ERLAUBTE:
                continue
            conn.execute(
                "UPDATE imap_polling_config SET aktiv=? WHERE account=?",
                (1 if aktiv else 0, account),
            )
        if intervall_min is not None:
            conn.execute(
                "UPDATE imap_polling_config SET intervall_min=?",
                (intervall_min,),
            )
    return jsonify({"accounts": hole_accounts()})
```

- [ ] **Schritt 5: Tests ausführen — müssen PASS sein**

```
python -m pytest backend/tests/test_us02_polling.py::TestImapPollingEndpoints -v
```

Erwartetes Ergebnis: 6 × PASSED

- [ ] **Schritt 6: Commit**

```
git add backend/routers/system_routes.py backend/tests/test_us02_polling.py
git commit -m "feat(api): GET+PATCH /system/imap-polling Endpoints (US-02)"
```

---

## Task 5: `health_service.py` — imap als Account-Array

**Files:**
- Modify: `backend/system/health_service.py`
- Modify: `backend/tests/test_health_service.py`

- [ ] **Schritt 1: Bestehenden Test anpassen**

In `backend/tests/test_health_service.py` die Methode `test_response_enthaelt_imap_und_sv_portal_keys` ersetzen:

```python
    def test_response_enthaelt_imap_und_sv_portal_keys(self):
        hs = _reload()
        with patch("backend.system.health_service.hole_accounts", return_value=[]):
            status = hs.get_status()
        self.assertIn("imap", status)
        self.assertIn("sv_portal", status)
        self.assertIsInstance(status["imap"], list)
        self.assertFalse(status["sv_portal"]["konfiguriert"])
```

- [ ] **Schritt 2: Test ausführen — muss FAIL sein**

```
python -m pytest backend/tests/test_health_service.py::TestGetStatus::test_response_enthaelt_imap_und_sv_portal_keys -v
```

Erwartetes Ergebnis: FAIL (patch-Target existiert noch nicht in health_service)

- [ ] **Schritt 3: health_service.py ersetzen**

`backend/system/health_service.py` vollständig ersetzen:

```python
import logging
from datetime import datetime

from ..ramicro.connector import verbindung_pruefen

logger = logging.getLogger(__name__)

_cache: dict = {
    "ramicro": {"ok": None, "letzter_sync_ts": None, "fehler": None}
}


def check_ramicro() -> None:
    result = verbindung_pruefen()
    war_ok = _cache["ramicro"]["ok"]
    jetzt_ok = result["status"] == "ok"
    if war_ok is not None and war_ok != jetzt_ok:
        if jetzt_ok:
            logger.info("RA-Micro: Verbindung wiederhergestellt")
        else:
            logger.warning("RA-Micro: Verbindung unterbrochen – %s",
                           result.get("meldung", ""))
    _cache["ramicro"] = {
        "ok": jetzt_ok,
        "letzter_sync_ts": datetime.now(),
        "fehler": result.get("meldung") if not jetzt_ok else None,
    }


def hole_accounts():
    from ..email_import.polling_service import hole_accounts as _hole_accounts
    return _hole_accounts()


def get_status() -> dict:
    rm = _cache["ramicro"]
    letzter_sync_vor_s = None
    if rm["letzter_sync_ts"] is not None:
        letzter_sync_vor_s = int(
            (datetime.now() - rm["letzter_sync_ts"]).total_seconds()
        )
    try:
        imap_accounts = hole_accounts()
    except Exception:
        imap_accounts = []
    return {
        "ramicro": {
            "ok": rm["ok"],
            "letzter_sync_vor_s": letzter_sync_vor_s,
            "fehler": rm["fehler"],
        },
        "imap": imap_accounts,
        "sv_portal": {"ok": None, "konfiguriert": False},
    }
```

- [ ] **Schritt 4: Alle health_service Tests ausführen — müssen PASS sein**

```
python -m pytest backend/tests/test_health_service.py -v
```

Erwartetes Ergebnis: alle PASSED

- [ ] **Schritt 5: Commit**

```
git add backend/system/health_service.py backend/tests/test_health_service.py
git commit -m "feat(health): get_status liefert IMAP-Polling-Status als Array (US-02)"
```

---

## Task 6: `app.py` — zweiter APScheduler-Job

**Files:**
- Modify: `backend/app.py`

- [ ] **Schritt 1: Scheduler-Block in app.py erweitern**

Den bestehenden Scheduler-Block (ca. Zeile 182–197):

```python
    if not app.testing:
        from .system.health_service import check_ramicro as _check_ramicro
        scheduler = APScheduler()
        app.config["SCHEDULER_API_ENABLED"] = False
        scheduler.init_app(app)
        scheduler.add_job(
            id="health_ramicro",
            func=_check_ramicro,
            trigger="interval",
            seconds=60,
            replace_existing=True,
        )
        scheduler.start()
        import threading as _threading
        _threading.Thread(target=_check_ramicro, daemon=True).start()
        logger.info("APScheduler gestartet: RA-Micro Health-Check alle 60s")
```

ersetzen durch:

```python
    if not app.testing:
        from .system.health_service import check_ramicro as _check_ramicro
        from .email_import.polling_service import fuehre_polling_durch as _imap_polling
        scheduler = APScheduler()
        app.config["SCHEDULER_API_ENABLED"] = False
        scheduler.init_app(app)
        scheduler.add_job(
            id="health_ramicro",
            func=_check_ramicro,
            trigger="interval",
            seconds=60,
            replace_existing=True,
        )
        scheduler.add_job(
            id="imap_polling",
            func=_imap_polling,
            trigger="interval",
            seconds=60,
            replace_existing=True,
        )
        scheduler.start()
        import threading as _threading
        _threading.Thread(target=_check_ramicro, daemon=True).start()
        logger.info("APScheduler gestartet: RA-Micro Health-Check + IMAP-Polling alle 60s")
```

- [ ] **Schritt 2: App-Start manuell prüfen**

```
python -m backend.app
```

Im Log muss erscheinen:
```
APScheduler gestartet: RA-Micro Health-Check + IMAP-Polling alle 60s
```

App startet ohne Fehler. Mit `Ctrl+C` abbrechen.

- [ ] **Schritt 3: Commit**

```
git add backend/app.py
git commit -m "feat(scheduler): IMAP-Polling APScheduler-Job alle 60s (US-02)"
```

---

## Task 7: `api.js` — neue `apiSystem`-Funktionen

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Schritt 1: apiSystem-Objekt erweitern**

In `frontend/src/api.js` den Block (ca. Zeile 1037):

```js
export const apiSystem = {
  getStatus: () => request("/system/status"),
  retryRamicro: () => request("/system/ramicro/retry", { method: "POST" }),
};
```

ersetzen durch:

```js
export const apiSystem = {
  getStatus: () => request("/system/status"),
  retryRamicro: () => request("/system/ramicro/retry", { method: "POST" }),
  getImapPolling: () => request("/system/imap-polling"),
  patchImapPolling: (data) => request("/system/imap-polling", {
    method: "PATCH",
    body: JSON.stringify(data),
  }),
};
```

- [ ] **Schritt 2: Commit**

```
git add frontend/src/api.js
git commit -m "feat(api): apiSystem.getImapPolling + patchImapPolling (US-02)"
```

---

## Task 8: `EinstellungenView.jsx` — IMAP-Polling UI

**Files:**
- Modify: `frontend/src/views/EinstellungenView.jsx`

- [ ] **Schritt 1: State-Variablen einfügen**

Nach der `sysRetryLaedt`-State-Deklaration (ca. Zeile 74) einfügen:

```jsx
  const [imapIntervall,  setImapIntervall]  = useState(5);
  const [imapSpeichert,  setImapSpeichert]  = useState(false);
```

- [ ] **Schritt 2: Tab-useEffect erweitern**

Das bestehende `useEffect` für `tab` (ca. Zeile 163):

```jsx
  useEffect(() => {
    if (tab === "sv_portal") ladeSvListe();
    if (tab === "system_status") {
      setSysLaedt(true);
      apiSystem.getStatus()
        .then(setSysStatus)
        .catch(() => {})
        .finally(() => setSysLaedt(false));
    }
  }, [tab]);
```

ersetzen durch:

```jsx
  useEffect(() => {
    if (tab === "sv_portal") ladeSvListe();
    if (tab === "system_status") {
      setSysLaedt(true);
      apiSystem.getStatus()
        .then(d => {
          setSysStatus(d);
          if (Array.isArray(d.imap) && d.imap.length > 0) {
            setImapIntervall(d.imap[0].intervall_min ?? 5);
          }
        })
        .catch(() => {})
        .finally(() => setSysLaedt(false));
    }
  }, [tab]);
```

- [ ] **Schritt 3: 30s-Polling-useEffect einfügen**

Direkt nach dem gerade geänderten useEffect einfügen:

```jsx
  useEffect(() => {
    if (tab !== "system_status") return;
    const id = setInterval(() => {
      apiSystem.getStatus()
        .then(d => {
          setSysStatus(d);
          if (Array.isArray(d.imap) && d.imap.length > 0) {
            setImapIntervall(prev => d.imap[0].intervall_min ?? prev);
          }
        })
        .catch(() => {});
    }, 30_000);
    return () => clearInterval(id);
  }, [tab]);
```

- [ ] **Schritt 4: IMAP-Block im system_status Tab ersetzen**

Den bestehenden IMAP-Placeholder (ca. Zeilen 1172–1184):

```jsx
                  {/* IMAP */}
                  <div style={{ color: T.textMuted, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", padding: "0.5rem 0 0.25rem" }}>E-Mail (IMAP)</div>
                  <div style={{ background: T.surface, borderRadius: 8, padding: "0.75rem 1rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <span style={{ width: 10, height: 10, borderRadius: "50%", display: "inline-block", flexShrink: 0,
                        background: sysStatus.imap?.konfiguriert ? (sysStatus.imap.ok === true ? "#2ecc71" : sysStatus.imap.ok === false ? "#e74c3c" : "#f39c12") : "#888" }} />
                      <div>
                        <div style={{ color: T.text, fontWeight: 600 }}>{sysStatus.imap?.konfiguriert ? "IMAP konfiguriert" : "IMAP nicht konfiguriert"}</div>
                        <div style={{ color: T.textMuted, fontSize: "0.8rem" }}>
                          {sysStatus.imap?.konfiguriert ? "Automatisches Polling noch nicht aktiv" : "EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD in .env setzen"}
                        </div>
                      </div>
                    </div>
                  </div>
```

ersetzen durch:

```jsx
                  {/* IMAP Polling */}
                  <div style={{ color: T.textMuted, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", padding: "0.5rem 0 0.25rem" }}>E-Mail Polling</div>

                  <div style={{ background: T.surface, borderRadius: 8, padding: "0.75rem 1rem", marginBottom: 6, display: "flex", alignItems: "center", gap: 12 }}>
                    <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", fontWeight: 600, color: T.text, flexShrink: 0 }}>Intervall:</span>
                    <select
                      value={imapIntervall}
                      onChange={e => setImapIntervall(parseInt(e.target.value))}
                      style={{ padding: "4px 8px", border: `1px solid ${T.border}`, borderRadius: 6, fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", background: T.white }}
                    >
                      {[5, 10, 15, 30].map(v => (
                        <option key={v} value={v}>{v} Minuten</option>
                      ))}
                    </select>
                    <Btn
                      disabled={imapSpeichert || !Array.isArray(sysStatus?.imap)}
                      style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                      onClick={async () => {
                        setImapSpeichert(true);
                        try {
                          const res = await apiSystem.patchImapPolling({ intervall_min: imapIntervall });
                          setSysStatus(prev => ({ ...prev, imap: res.accounts }));
                          setToast("Polling-Intervall gespeichert.");
                        } catch { setToast("Fehler beim Speichern."); }
                        finally { setImapSpeichert(false); }
                      }}
                    >
                      {imapSpeichert ? "Speichern …" : "Speichern"}
                    </Btn>
                  </div>

                  {(Array.isArray(sysStatus?.imap) ? sysStatus.imap : []).map(acc => {
                    const dotFarbe = !acc.passwort_vorhanden ? "#888"
                      : acc.letzter_status === "ok"     ? "#2ecc71"
                      : acc.letzter_status === "fehler"  ? "#e74c3c"
                      : "#f39c12";
                    return (
                      <div key={acc.account} style={{ background: T.surface, borderRadius: 8, padding: "0.65rem 1rem", marginBottom: 6, display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ width: 10, height: 10, borderRadius: "50%", display: "inline-block", flexShrink: 0, background: dotFarbe }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontFamily: "'Figtree',sans-serif", color: T.text, fontWeight: 600, fontSize: "0.875rem" }}>
                            {acc.account}@anwalt-offenbach.de
                          </div>
                          <div style={{ fontFamily: "'Figtree',sans-serif", color: T.textMuted, fontSize: "0.78rem" }}>
                            {!acc.passwort_vorhanden
                              ? `EMAIL_PASSWORD_${acc.account.toUpperCase()} fehlt in .env`
                              : acc.letzter_lauf
                                ? `Letzter Lauf: ${acc.letzter_lauf.slice(0, 16).replace("T", " ")}`
                                : "Noch nie gelaufen"}
                            {acc.letzter_fehler && (
                              <span style={{ color: "#e74c3c", marginLeft: 8 }}>
                                — {acc.letzter_fehler}
                              </span>
                            )}
                          </div>
                        </div>
                        <div
                          onClick={async () => {
                            if (!acc.passwort_vorhanden) return;
                            try {
                              const res = await apiSystem.patchImapPolling({
                                accounts: { [acc.account]: !acc.aktiv },
                              });
                              setSysStatus(prev => ({ ...prev, imap: res.accounts }));
                            } catch { setToast("Fehler beim Speichern."); }
                          }}
                          title={acc.passwort_vorhanden ? "" : "Passwort fehlt in .env"}
                          style={{
                            width: 42, height: 24, borderRadius: 12,
                            background: acc.aktiv && acc.passwort_vorhanden ? "#2ecc71" : T.border,
                            position: "relative",
                            cursor: acc.passwort_vorhanden ? "pointer" : "not-allowed",
                            opacity: acc.passwort_vorhanden ? 1 : 0.45,
                            transition: "background 0.2s", flexShrink: 0,
                          }}>
                          <div style={{
                            position: "absolute", top: 3,
                            left: acc.aktiv && acc.passwort_vorhanden ? 21 : 3,
                            width: 18, height: 18, borderRadius: 9, background: "#fff",
                            transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                          }} />
                        </div>
                      </div>
                    );
                  })}

                  {!Array.isArray(sysStatus?.imap) && sysLaedt && (
                    <div style={{ color: T.textFaint, fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", padding: "0.5rem 0" }}>
                      Lade …
                    </div>
                  )}
```

- [ ] **Schritt 5: Commit**

```
git add frontend/src/views/EinstellungenView.jsx
git commit -m "feat(ui): IMAP-Polling Toggle + Intervall im Health-Dashboard (US-02)"
```

---

## Task 9: `.env.example` aktualisieren

**Files:**
- Modify: `.env.example`

- [ ] **Schritt 1: Neuen Abschnitt einfügen**

In `.env.example` nach dem bestehenden E-Mail-Abschnitt (nach `# EMAIL_MAX_FETCH=50`) einfügen:

```
# -----------------------------------------------------------------------------
#  IMAP AUTO-POLLING  (US-02 – pro Account eigenes Passwort)
# -----------------------------------------------------------------------------
# Gemeinsamer Server für alle Accounts: EMAIL_HOST + EMAIL_PORT (oben).
# Pro Account: eigene Adresse + eigenes Passwort.
# Fehlt ein Eintrag, wird das Polling für diesen Account automatisch deaktiviert.

# EMAIL_USER_UNFALL=unfall@anwalt-offenbach.de
# EMAIL_PASSWORD_UNFALL=BITTE_ERSETZEN

# EMAIL_USER_TERMIN=termin@anwalt-offenbach.de
# EMAIL_PASSWORD_TERMIN=BITTE_ERSETZEN

# EMAIL_USER_BUSSGELD=bussgeld@anwalt-offenbach.de
# EMAIL_PASSWORD_BUSSGELD=BITTE_ERSETZEN

# EMAIL_USER_INFO=info@anwalt-offenbach.de
# EMAIL_PASSWORD_INFO=BITTE_ERSETZEN
```

- [ ] **Schritt 2: Commit**

```
git add .env.example
git commit -m "docs(env): IMAP Auto-Polling Account-Vars dokumentiert (US-02)"
```

---

## Gesamttest nach Abschluss

```
python -m pytest backend/tests/test_us02_polling.py backend/tests/test_health_service.py -v
```

Erwartetes Ergebnis: alle Tests PASSED, kein FAILED.
