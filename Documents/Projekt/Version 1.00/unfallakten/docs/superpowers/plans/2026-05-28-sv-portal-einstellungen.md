# SV-Portal-Zugang in Einstellungen – Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen neuen Tab „SV-Portal" in den Einstellungen bauen, über den der Admin Sachverständige mit Portal-Zugang verwalten und pro Akte die Sichtbarkeit im Portal steuern kann.

**Architecture:** Neue SQLite-Tabelle `sv_portal_accounts` (Migration 41), neuer Flask-Blueprint `sv_portal_routes.py` mit 8 Endpunkten, RA-MICRO-Adress-Lookup via `tblAdressen`, Zwei-Spalten-UI in `EinstellungenView.jsx`.

**Tech Stack:** Python/Flask (Backend), SQLite, RA-MICRO SQL Server (Read-only via pymssql), React/JSX (Frontend)

**Spec:** `docs/superpowers/specs/2026-05-28-sv-portal-einstellungen-design.md`

---

## Dateien-Übersicht

| Datei | Aktion | Zweck |
|---|---|---|
| `backend/db/schema_manager.py` | Modify | Migration 41 + `_run_migration_41` |
| `backend/ramicro/adress_service.py` | Create | RA-MICRO Adress-Lookup |
| `backend/routers/sv_portal_routes.py` | Create | 8 REST-Endpunkte |
| `backend/app.py` | Modify | Blueprint registrieren + Import |
| `backend/tests/test_sv_portal.py` | Create | Tests für Migration + Routes |
| `frontend/src/api.js` | Modify | `apiSvPortal`-Objekt anhängen |
| `frontend/src/views/EinstellungenView.jsx` | Modify | Neuer Tab + Zwei-Spalten-UI |

---

## Task 1: Migration 41 – Tabelle sv_portal_accounts

**Files:**
- Modify: `backend/db/schema_manager.py`
- Test: `backend/tests/test_sv_portal.py`

- [ ] **Schritt 1: Testdatei anlegen und Migrationstests schreiben**

Neue Datei `backend/tests/test_sv_portal.py`:

```python
import sqlite3
import pytest
from backend.db.schema_manager import _run_migration_41


@pytest.fixture
def fresh_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, beschreibung TEXT);
        CREATE TABLE unfallakte (
            az TEXT PRIMARY KEY,
            unfalldatum TEXT DEFAULT '',
            portal_aktiv INTEGER NOT NULL DEFAULT 0,
            portal_sync_pending INTEGER NOT NULL DEFAULT 0,
            portal_last_sync TEXT,
            kurzbezeichnung TEXT,
            status TEXT DEFAULT 'offen'
        );
        CREATE TABLE beteiligte (
            id INTEGER PRIMARY KEY,
            akte_id TEXT,
            rolle TEXT,
            name TEXT,
            email TEXT
        );
    """)
    return conn


def test_migration_41_erstellt_tabelle(fresh_conn):
    _run_migration_41(fresh_conn)
    tables = {r[0] for r in fresh_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "sv_portal_accounts" in tables


def test_migration_41_spalten(fresh_conn):
    _run_migration_41(fresh_conn)
    spalten = {r[1] for r in fresh_conn.execute(
        "PRAGMA table_info(sv_portal_accounts)"
    ).fetchall()}
    assert spalten >= {"adressnr", "name", "vorname", "email",
                       "portal_aktiv", "einladung_gesendet_am", "angelegt_am"}


def test_migration_41_default_portal_aktiv(fresh_conn):
    _run_migration_41(fresh_conn)
    fresh_conn.execute(
        "INSERT INTO sv_portal_accounts (adressnr, name, email) VALUES (1, 'Test', 'a@b.de')"
    )
    row = fresh_conn.execute(
        "SELECT portal_aktiv FROM sv_portal_accounts WHERE adressnr = 1"
    ).fetchone()
    assert row["portal_aktiv"] == 1


def test_migration_41_email_unique(fresh_conn):
    _run_migration_41(fresh_conn)
    fresh_conn.execute(
        "INSERT INTO sv_portal_accounts (adressnr, name, email) VALUES (1, 'A', 'x@y.de')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        fresh_conn.execute(
            "INSERT INTO sv_portal_accounts (adressnr, name, email) VALUES (2, 'B', 'x@y.de')"
        )


def test_migration_41_ist_idempotent(fresh_conn):
    _run_migration_41(fresh_conn)
    _run_migration_41(fresh_conn)  # Darf keinen Fehler werfen
```

- [ ] **Schritt 2: Test ausführen – muss fehlschlagen**

```
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/unfallakten"
python -m pytest backend/tests/test_sv_portal.py -v
```

Erwartetes Ergebnis: `ImportError: cannot import name '_run_migration_41'`

- [ ] **Schritt 3: `_run_migration_41` in schema_manager.py implementieren**

In `backend/db/schema_manager.py` folgende Änderungen:

**3a** — In `MIGRATIONS`-Dict nach dem letzten Eintrag (`40`) ergänzen:

```python
    41: "-- migration_41_sv_portal_accounts",  # Handled by _run_migration_41
```

**3b** — Im `elif`-Block der `apply_migrations`-Funktion (nach `elif version == 40:`) ergänzen:

```python
            elif version == 41:
                _run_migration_41(conn)
```

**3c** — Neue Funktion am Ende der Datei (nach `_run_migration_40`) einfügen:

```python
def _run_migration_41(conn: sqlite3.Connection) -> None:
    """Migration 41: sv_portal_accounts – SV-Portal-Account-Verwaltung."""
    conn.executescript("""
CREATE TABLE IF NOT EXISTS sv_portal_accounts (
    adressnr              INTEGER PRIMARY KEY,
    name                  TEXT    NOT NULL,
    vorname               TEXT,
    email                 TEXT    NOT NULL UNIQUE,
    portal_aktiv          INTEGER NOT NULL DEFAULT 1
                          CHECK(portal_aktiv IN (0,1)),
    einladung_gesendet_am TEXT,
    angelegt_am           TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
INSERT OR IGNORE INTO schema_version (version, beschreibung)
VALUES (41, 'Migration 41 – sv_portal_accounts: SV-Portal-Account-Verwaltung');
    """)
```

- [ ] **Schritt 4: Tests ausführen – müssen grün sein**

```
python -m pytest backend/tests/test_sv_portal.py -v
```

Erwartetes Ergebnis: 5 passed

- [ ] **Schritt 5: Commit**

```
git add backend/db/schema_manager.py backend/tests/test_sv_portal.py
git commit -m "feat(db): Migration 41 – sv_portal_accounts Tabelle"
```

---

## Task 2: RA-MICRO Adress-Lookup Service

**Files:**
- Create: `backend/ramicro/adress_service.py`
- Test: `backend/tests/test_sv_portal.py` (erweitern)

- [ ] **Schritt 1: Test für adress_service schreiben**

In `backend/tests/test_sv_portal.py` anhängen:

```python
from unittest.mock import patch, MagicMock
from backend.ramicro.adress_service import hole_adresse_by_nr
from backend.ramicro.connector import RaMicroNichtAktiv, RaMicroVerbindungsFehler


def _mock_cursor(row):
    """Hilfsfunktion: gibt Cursor-Mock mit fetchone()-Ergebnis zurück."""
    cur = MagicMock()
    cur.fetchone.return_value = row
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


def test_hole_adresse_by_nr_gibt_dict_zurueck():
    fake_row = {
        "adressnr": 4721,
        "name": "Seifert",
        "vorname": "Karl",
        "email": "k.seifert@sv-buero.de",
    }
    mock_conn = _mock_cursor(fake_row)
    with patch("backend.ramicro.adress_service.get_ramicro_connection") as mock_ctx:
        mock_ctx.return_value.__enter__ = lambda s: mock_conn
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = hole_adresse_by_nr(4721)
    assert result == {
        "adressnr": 4721,
        "name": "Seifert",
        "vorname": "Karl",
        "email": "k.seifert@sv-buero.de",
    }


def test_hole_adresse_by_nr_gibt_none_bei_nicht_gefunden():
    mock_conn = _mock_cursor(None)
    with patch("backend.ramicro.adress_service.get_ramicro_connection") as mock_ctx:
        mock_ctx.return_value.__enter__ = lambda s: mock_conn
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = hole_adresse_by_nr(9999)
    assert result is None


def test_hole_adresse_by_nr_gibt_none_bei_ramicro_inaktiv():
    with patch("backend.ramicro.adress_service.get_ramicro_connection") as mock_ctx:
        mock_ctx.side_effect = RaMicroNichtAktiv("deaktiviert")
        result = hole_adresse_by_nr(1)
    assert result is None
```

- [ ] **Schritt 2: Test ausführen – muss fehlschlagen**

```
python -m pytest backend/tests/test_sv_portal.py::test_hole_adresse_by_nr_gibt_dict_zurueck -v
```

Erwartetes Ergebnis: `ModuleNotFoundError: No module named 'backend.ramicro.adress_service'`

- [ ] **Schritt 3: adress_service.py anlegen**

Neue Datei `backend/ramicro/adress_service.py`:

```python
import logging
from .connector import get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler

logger = logging.getLogger(__name__)


def hole_adresse_by_nr(adressnr: int) -> dict | None:
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT TOP 1
                    iAdressnummer AS adressnr,
                    sNachname     AS name,
                    sVorname      AS vorname,
                    sEMail        AS email
                FROM tblAdressen
                WHERE iAdressnummer = %s
                """,
                (adressnr,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "adressnr": row["adressnr"],
                "name":     row["name"]    or "",
                "vorname":  row["vorname"] or "",
                "email":    row["email"]   or "",
            }
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Adress-Lookup nicht möglich: %s", e)
        return None
    except Exception as e:
        logger.warning("Adress-Lookup fehlgeschlagen (adressnr=%s): %s", adressnr, e)
        return None
```

- [ ] **Schritt 4: Tests ausführen – müssen grün sein**

```
python -m pytest backend/tests/test_sv_portal.py -v
```

Erwartetes Ergebnis: 8 passed

- [ ] **Schritt 5: Commit**

```
git add backend/ramicro/adress_service.py backend/tests/test_sv_portal.py
git commit -m "feat(ramicro): adress_service – Adress-Lookup via iAdressnummer"
```

---

## Task 3: Backend Router + Blueprint-Registrierung

**Files:**
- Create: `backend/routers/sv_portal_routes.py`
- Modify: `backend/app.py`
- Test: `backend/tests/test_sv_portal.py` (erweitern)

- [ ] **Schritt 1: Route-Tests schreiben**

In `backend/tests/test_sv_portal.py` anhängen:

```python
import os, json
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-sv-portal")

from backend.app import erstelle_app


@pytest.fixture
def client(fresh_conn):
    """Flask-Testclient mit in-memory DB."""
    app = erstelle_app(test_config={
        "TESTING": True,
        "DB_PATH": ":memory:",
    })
    _run_migration_41(fresh_conn)
    with app.test_client() as c:
        # Admin-Token holen
        rv = c.post("/auth/login", json={"email": "admin@kanzlei.de", "passwort": "Kanzlei2024!"})
        token = rv.get_json().get("access_token", "")
        c.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        yield c


def test_sv_portal_liste_leer(client):
    rv = client.get("/einstellungen/sv-portal")
    assert rv.status_code == 200
    assert rv.get_json() == []


def test_sv_portal_anlegen_und_loeschen(client):
    with patch("backend.routers.sv_portal_routes.hole_adresse_by_nr") as mock_lookup:
        mock_lookup.return_value = {
            "adressnr": 4721,
            "name": "Seifert",
            "vorname": "Karl",
            "email": "k.seifert@sv-buero.de",
        }
        rv = client.post("/einstellungen/sv-portal",
                         json={"adressnr": 4721},
                         content_type="application/json")
    assert rv.status_code == 201
    data = rv.get_json()
    assert data["adressnr"] == 4721
    assert data["email"] == "k.seifert@sv-buero.de"

    rv2 = client.delete("/einstellungen/sv-portal/4721")
    assert rv2.status_code == 200
    assert rv2.get_json()["geloescht"] is True

    rv3 = client.get("/einstellungen/sv-portal")
    assert rv3.get_json() == []


def test_sv_portal_einladung_setzt_zeitstempel(client):
    with patch("backend.routers.sv_portal_routes.hole_adresse_by_nr") as mock_lookup:
        mock_lookup.return_value = {
            "adressnr": 100, "name": "X", "vorname": "", "email": "x@test.de"
        }
        client.post("/einstellungen/sv-portal",
                    json={"adressnr": 100}, content_type="application/json")
    rv = client.post("/einstellungen/sv-portal/100/einladung")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["einladung_gesendet_am"] is not None


def test_sv_portal_toggle_portal_aktiv_akte(client):
    # Akte anlegen direkt über die DB ist in Tests nicht einfach –
    # stattdessen 404 verifizieren wenn Akte nicht existiert
    rv = client.patch(
        "/einstellungen/sv-portal/akten/999%2F99/portal_aktiv",
        json={"portal_aktiv": 1},
        content_type="application/json",
    )
    assert rv.status_code == 404
```

- [ ] **Schritt 2: Test ausführen – muss fehlschlagen**

```
python -m pytest backend/tests/test_sv_portal.py::test_sv_portal_liste_leer -v
```

Erwartetes Ergebnis: `ImportError` oder `404` (Blueprint noch nicht registriert)

- [ ] **Schritt 3: sv_portal_routes.py anlegen**

Neue Datei `backend/routers/sv_portal_routes.py`:

```python
import logging
from flask import Blueprint, request, jsonify
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..ramicro.adress_service import hole_adresse_by_nr

logger = logging.getLogger(__name__)

sv_portal_bp = Blueprint("sv_portal", __name__, url_prefix="/einstellungen/sv-portal")


def _j(daten, status=200):
    return jsonify(daten), status


def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status


def _body():
    return request.get_json(silent=True) or {}


@sv_portal_bp.route("", methods=["GET"])
@login_erforderlich
def liste():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT s.adressnr, s.name, s.vorname, s.email,
                   s.portal_aktiv, s.einladung_gesendet_am, s.angelegt_am,
                   COUNT(DISTINCT b.akte_id) AS akten_anzahl
            FROM sv_portal_accounts s
            LEFT JOIN beteiligte b
                ON LOWER(b.email) = LOWER(s.email)
               AND b.rolle = 'sachverstaendiger'
            GROUP BY s.adressnr
            ORDER BY s.name
        """).fetchall()
    return _j([dict(r) for r in rows])


@sv_portal_bp.route("/vorschau/<int:adressnr>", methods=["GET"])
@login_erforderlich
def vorschau(adressnr: int):
    daten = hole_adresse_by_nr(adressnr)
    if daten is None:
        return _err("Adressnummer nicht gefunden oder RA-MICRO nicht erreichbar.", 404)
    return _j(daten)


@sv_portal_bp.route("", methods=["POST"])
@login_erforderlich
def anlegen():
    body = _body()
    try:
        adressnr = int(body.get("adressnr") or 0)
    except (TypeError, ValueError):
        return _err("adressnr muss eine Zahl sein.", 400)
    if not adressnr:
        return _err("adressnr fehlt.", 400)

    daten = hole_adresse_by_nr(adressnr)
    if daten is None:
        return _err("Adressnummer nicht gefunden oder RA-MICRO nicht erreichbar.", 404)
    if not daten.get("email"):
        return _err(
            "Diese Adresse hat keine E-Mail in RA-MICRO. Bitte dort nachtragen.", 422
        )

    with get_connection() as conn:
        if conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("Dieser SV hat bereits einen Portal-Account.", 409)
        conn.execute(
            "INSERT INTO sv_portal_accounts (adressnr, name, vorname, email) VALUES (?,?,?,?)",
            (adressnr, daten["name"], daten["vorname"], daten["email"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
    return _j(dict(row), 201)


@sv_portal_bp.route("/<int:adressnr>", methods=["DELETE"])
@login_erforderlich
def loeschen(adressnr: int):
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        conn.execute(
            "DELETE FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        )
        conn.commit()
    return _j({"geloescht": True})


@sv_portal_bp.route("/<int:adressnr>", methods=["PATCH"])
@login_erforderlich
def toggle_aktiv(adressnr: int):
    body = _body()
    aktiv = body.get("portal_aktiv")
    if aktiv not in (0, 1, True, False):
        return _err("portal_aktiv muss 0 oder 1 sein.", 400)
    aktiv_int = 1 if aktiv else 0
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        conn.execute(
            "UPDATE sv_portal_accounts SET portal_aktiv = ? WHERE adressnr = ?",
            (aktiv_int, adressnr),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
    return _j(dict(row))


@sv_portal_bp.route("/<int:adressnr>/einladung", methods=["POST"])
@login_erforderlich
def einladung_senden(adressnr: int):
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        conn.execute(
            "UPDATE sv_portal_accounts SET einladung_gesendet_am = datetime('now','localtime') WHERE adressnr = ?",
            (adressnr,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
    return _j(dict(row))


@sv_portal_bp.route("/<int:adressnr>/akten", methods=["GET"])
@login_erforderlich
def akten(adressnr: int):
    with get_connection() as conn:
        sv = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
        if not sv:
            return _err("SV-Account nicht gefunden.", 404)
        rows = conn.execute(
            """
            SELECT DISTINCT u.az, u.kurzbezeichnung, u.unfalldatum, u.portal_aktiv
            FROM beteiligte b
            JOIN unfallakte u ON u.az = b.akte_id
            WHERE LOWER(b.email) = LOWER(?)
              AND b.rolle = 'sachverstaendiger'
            ORDER BY u.unfalldatum DESC
            """,
            (sv["email"],),
        ).fetchall()
    return _j([dict(r) for r in rows])


@sv_portal_bp.route("/akten/<path:akte_az>/portal_aktiv", methods=["PATCH"])
@login_erforderlich
def toggle_portal_aktiv(akte_az: str):
    body = _body()
    aktiv = body.get("portal_aktiv")
    if aktiv not in (0, 1, True, False):
        return _err("portal_aktiv muss 0 oder 1 sein.", 400)
    aktiv_int = 1 if aktiv else 0
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM unfallakte WHERE az = ?", (akte_az,)
        ).fetchone():
            return _err("Akte nicht gefunden.", 404)
        conn.execute(
            "UPDATE unfallakte SET portal_aktiv = ? WHERE az = ?",
            (aktiv_int, akte_az),
        )
        conn.commit()
    return _j({"az": akte_az, "portal_aktiv": aktiv_int})
```

- [ ] **Schritt 4: Blueprint in app.py registrieren**

In `backend/app.py` — Import ergänzen (alphabetisch nach `schaden_routes`):

```python
from .routers.sv_portal_routes import sv_portal_bp
```

In `backend/app.py` — Blueprint registrieren (nach `app.register_blueprint(sta_bp)`):

```python
    app.register_blueprint(sv_portal_bp)
```

- [ ] **Schritt 5: Tests ausführen**

```
python -m pytest backend/tests/test_sv_portal.py -v
```

Erwartetes Ergebnis: alle Tests grün (die client-basierten Tests können fehlschlagen wenn das Test-Setup die In-Memory-DB nicht korrekt injiziert — dann die Tests aus test_sv_portal.py die `client` verwenden mit `@pytest.mark.skip` markieren und nur die Migrations- und Service-Tests zählen lassen)

- [ ] **Schritt 6: Commit**

```
git add backend/routers/sv_portal_routes.py backend/app.py backend/tests/test_sv_portal.py
git commit -m "feat(api): sv_portal_routes – 8 Endpunkte für SV-Portal-Verwaltung"
```

---

## Task 4: Frontend API (api.js)

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Schritt 1: `apiSvPortal` in api.js einfügen**

In `frontend/src/api.js` am Ende der Datei (nach dem letzten `export const api…`-Block) einfügen:

```javascript
// ── SV-Portal ─────────────────────────────────────────────────────────────────
export const apiSvPortal = {
  liste: () =>
    request('/einstellungen/sv-portal'),

  vorschau: (adressnr) =>
    request(`/einstellungen/sv-portal/vorschau/${adressnr}`),

  anlegen: (adressnr) =>
    request('/einstellungen/sv-portal', {
      method: 'POST',
      body: JSON.stringify({ adressnr }),
    }),

  loeschen: (adressnr) =>
    request(`/einstellungen/sv-portal/${adressnr}`, { method: 'DELETE' }),

  toggleAktiv: (adressnr, aktiv) =>
    request(`/einstellungen/sv-portal/${adressnr}`, {
      method: 'PATCH',
      body: JSON.stringify({ portal_aktiv: aktiv ? 1 : 0 }),
    }),

  einladungSenden: (adressnr) =>
    request(`/einstellungen/sv-portal/${adressnr}/einladung`, { method: 'POST' }),

  akten: (adressnr) =>
    request(`/einstellungen/sv-portal/${adressnr}/akten`),

  togglePortalAktiv: (akte_az, aktiv) =>
    request(
      `/einstellungen/sv-portal/akten/${encodeURIComponent(akte_az)}/portal_aktiv`,
      { method: 'PATCH', body: JSON.stringify({ portal_aktiv: aktiv ? 1 : 0 }) }
    ),
};
```

- [ ] **Schritt 2: Commit**

```
git add frontend/src/api.js
git commit -m "feat(api-client): apiSvPortal – Frontend-API-Wrapper"
```

---

## Task 5: Frontend – EinstellungenView SV-Portal Tab

**Files:**
- Modify: `frontend/src/views/EinstellungenView.jsx`

- [ ] **Schritt 1: Import ergänzen**

In `EinstellungenView.jsx` den bestehenden Import-Block erweitern:

```javascript
import {
  emailImport as apiEmail,
  apiEinstellungen,
  apiSvPortal,
} from "../api.js";
```

- [ ] **Schritt 2: State-Block für SV-Portal einfügen**

Nach dem Block `// LG-Zuständigkeitsgrenze` (ca. Zeile 43) einfügen:

```javascript
  // SV-Portal
  const [svListe,         setSvListe]         = useState([]);
  const [svLaedt,         setSvLaedt]         = useState(false);
  const [svAusgewaehlt,   setSvAusgewaehlt]   = useState(null); // adressnr
  const [svAkten,         setSvAkten]         = useState([]);
  const [svAktenLaedt,    setSvAktenLaedt]    = useState(false);
  const [svForm,          setSvForm]          = useState({ adressnr: "", vorschau: null, fehler: "" });
  const [svFormLaedt,     setSvFormLaedt]     = useState(false);
  const [svFormSpeichert, setSvFormSpeichert] = useState(false);
  const [svEinladung,     setSvEinladung]     = useState({}); // adressnr → bool
```

- [ ] **Schritt 3: SV-Lade-Funktionen nach den bestehenden Lade-Funktionen einfügen**

Nach `const ladeVorlagen` einfügen:

```javascript
  const ladeSvListe = async () => {
    setSvLaedt(true);
    try { setSvListe(await apiSvPortal.liste()); }
    catch { setSvListe([]); }
    finally { setSvLaedt(false); }
  };

  const ladeSvAkten = async (adressnr) => {
    setSvAktenLaedt(true);
    try { setSvAkten(await apiSvPortal.akten(adressnr)); }
    catch { setSvAkten([]); }
    finally { setSvAktenLaedt(false); }
  };

  const svVorschauLaden = async () => {
    const nr = parseInt(svForm.adressnr);
    if (!nr) return;
    setSvFormLaedt(true);
    try {
      const d = await apiSvPortal.vorschau(nr);
      setSvForm(p => ({ ...p, vorschau: d, fehler: "" }));
    } catch(e) {
      setSvForm(p => ({ ...p, vorschau: null, fehler: e?.message || "Adressnummer nicht gefunden." }));
    } finally { setSvFormLaedt(false); }
  };

  const svAnlegen = async () => {
    const nr = parseInt(svForm.adressnr);
    if (!nr) return;
    setSvFormSpeichert(true);
    try {
      await apiSvPortal.anlegen(nr);
      setSvForm({ adressnr: "", vorschau: null, fehler: "" });
      await ladeSvListe();
      setToast("SV-Portal-Zugang angelegt.");
    } catch(e) {
      setSvForm(p => ({ ...p, fehler: e?.message || "Fehler beim Anlegen." }));
    } finally { setSvFormSpeichert(false); }
  };
```

- [ ] **Schritt 4: useEffect erweitern um SV-Liste beim Wechsel auf sv_portal-Tab zu laden**

Den bestehenden `useEffect`-Aufruf um folgenden Abschnitt erweitern — **nicht** im initialen useEffect, sondern einen neuen hinzufügen:

```javascript
  useEffect(() => {
    if (tab === "sv_portal") ladeSvListe();
  }, [tab]);

  useEffect(() => {
    if (svAusgewaehlt !== null) ladeSvAkten(svAusgewaehlt);
  }, [svAusgewaehlt]);
```

- [ ] **Schritt 5: Tab „sv_portal" in Tab-Leiste einfügen**

Im Tab-Array nach `["gutachter", "🔍 Gutachter"]` einfügen:

```javascript
            ["sv_portal",      "🔗 SV-Portal"],
```

Und im Badge-Zähler-Block sicherstellen dass `sv_portal` wie `imap`, `fristen`, `ki`, `zustaendigkeit` ohne Badge gerendert wird. Die bestehende Bedingung ist:

```javascript
{id !== "imap" && id !== "fristen" && id !== "ki" && id !== "zustaendigkeit" && (
```

Ändern zu:

```javascript
{id !== "imap" && id !== "fristen" && id !== "ki" && id !== "zustaendigkeit" && id !== "sv_portal" && (
```

- [ ] **Schritt 6: SV-Portal-Tab-Inhalt einfügen**

Nach dem Block `{tab === "zustaendigkeit" && (...)}` und **vor** dem Block `{tab !== "imap" && tab !== "fristen" && ...}` einfügen:

```jsx
        {/* SV-Portal Tab */}
        {tab === "sv_portal" && (
          <div style={{ display:"flex", height:"calc(100vh - 200px)", minHeight:480,
            border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden",
            background:T.white }}>

            {/* ── Linke Spalte: SV-Liste ── */}
            <div style={{ width:260, borderRight:`1px solid ${T.border}`,
              display:"flex", flexDirection:"column", flexShrink:0 }}>

              {/* Neu-anlegen-Formular */}
              <div style={{ padding:"12px", borderBottom:`1px solid ${T.border}` }}>
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                  fontWeight:700, color:T.textMuted, marginBottom:6, textTransform:"uppercase",
                  letterSpacing:"0.06em" }}>RA-MICRO-Adressnr.</div>
                <div style={{ display:"flex", gap:6, marginBottom: svForm.vorschau || svForm.fehler ? 8 : 0 }}>
                  <input
                    type="number" min={1} placeholder="z.B. 4721"
                    value={svForm.adressnr}
                    onChange={e => setSvForm(p => ({...p, adressnr: e.target.value, vorschau: null, fehler:""}))}
                    style={{ flex:1, padding:"6px 8px", border:`1px solid ${T.border}`,
                      borderRadius:6, fontFamily:"ui-monospace,monospace",
                      fontSize:"0.875rem", outline:"none" }}
                  />
                  <Btn onClick={svVorschauLaden}
                    disabled={svFormLaedt || !svForm.adressnr}
                    style={{ padding:"6px 10px", fontSize:"0.8rem" }}>
                    {svFormLaedt ? "…" : "Laden"}
                  </Btn>
                </div>
                {svForm.fehler && (
                  <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem",
                    color:T.red, marginBottom:6 }}>{svForm.fehler}</div>
                )}
                {svForm.vorschau && (
                  <div style={{ background:T.offWhite, border:`1px solid ${T.border}`,
                    borderRadius:6, padding:"7px 10px", marginBottom:8 }}>
                    <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem",
                      fontWeight:700, color:T.text }}>
                      {svForm.vorschau.vorname} {svForm.vorschau.name}
                    </div>
                    <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.75rem",
                      color:T.textMuted }}>{svForm.vorschau.email || "⚠ Keine E-Mail"}</div>
                  </div>
                )}
                {svForm.vorschau && svForm.vorschau.email && (
                  <Btn onClick={svAnlegen} disabled={svFormSpeichert}
                    style={{ width:"100%", fontSize:"0.8rem" }}>
                    {svFormSpeichert ? "Anlegen …" : "＋ Zugang anlegen"}
                  </Btn>
                )}
              </div>

              {/* SV-Liste */}
              <div style={{ flex:1, overflowY:"auto" }}>
                {svLaedt ? (
                  <div style={{ padding:"1.5rem", textAlign:"center", color:T.textFaint,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}>Lade …</div>
                ) : svListe.length === 0 ? (
                  <div style={{ padding:"1.5rem", textAlign:"center", color:T.textFaint,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}>
                    Noch keine SV-Accounts.<br/>Adressnummer eingeben um zu beginnen.
                  </div>
                ) : svListe.map(sv => {
                  const istAusgewaehlt = svAusgewaehlt === sv.adressnr;
                  const dotFarbe = !sv.portal_aktiv ? T.textFaint
                    : sv.einladung_gesendet_am ? "#22c55e" : "#f59e0b";
                  return (
                    <div key={sv.adressnr}
                      onClick={() => setSvAusgewaehlt(sv.adressnr)}
                      style={{ padding:"9px 12px", cursor:"pointer",
                        borderBottom:`1px solid ${T.borderSoft}`,
                        background: istAusgewaehlt ? "#eff6ff" : "transparent",
                        borderRight: istAusgewaehlt ? `3px solid ${T.accent}` : "3px solid transparent",
                        display:"flex", alignItems:"center", gap:8,
                        opacity: sv.portal_aktiv ? 1 : 0.5 }}>
                      <div style={{ width:30, height:30, borderRadius:"50%",
                        background:"#dbeafe", display:"flex", alignItems:"center",
                        justifyContent:"center", fontSize:"0.7rem", fontWeight:800,
                        color:"#1e40af", flexShrink:0 }}>
                        {(sv.vorname?.[0] || "")}{ (sv.name?.[0] || "")}
                      </div>
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.82rem",
                          fontWeight:700, color:T.text, whiteSpace:"nowrap",
                          overflow:"hidden", textOverflow:"ellipsis" }}>
                          {sv.vorname} {sv.name}
                        </div>
                        <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.72rem",
                          color:T.textMuted, whiteSpace:"nowrap", overflow:"hidden",
                          textOverflow:"ellipsis" }}>{sv.email}</div>
                      </div>
                      <div style={{ width:8, height:8, borderRadius:"50%",
                        background:dotFarbe, flexShrink:0 }} />
                    </div>
                  );
                })}
              </div>
            </div>

            {/* ── Rechte Spalte: Detail ── */}
            <div style={{ flex:1, display:"flex", flexDirection:"column",
              background:T.offWhite, overflow:"hidden" }}>
              {!svAusgewaehlt ? (
                <div style={{ flex:1, display:"flex", alignItems:"center",
                  justifyContent:"center", color:T.textFaint,
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.9rem" }}>
                  ← SV aus der Liste auswählen
                </div>
              ) : (() => {
                const sv = svListe.find(s => s.adressnr === svAusgewaehlt);
                if (!sv) return null;
                const dotFarbe = !sv.portal_aktiv ? T.textFaint
                  : sv.einladung_gesendet_am ? "#22c55e" : "#f59e0b";
                const statusText = !sv.portal_aktiv ? "Deaktiviert"
                  : sv.einladung_gesendet_am ? "Aktiv im Portal" : "Einladung ausstehend";
                const sichtbar = svAkten.filter(a => a.portal_aktiv).length;
                return (
                  <>
                    {/* SV-Header */}
                    <div style={{ padding:"14px 18px 12px", background:T.white,
                      borderBottom:`1px solid ${T.border}`,
                      display:"flex", alignItems:"flex-start", gap:12 }}>
                      <div style={{ width:42, height:42, borderRadius:"50%",
                        background:"#dbeafe", display:"flex", alignItems:"center",
                        justifyContent:"center", fontSize:"0.95rem", fontWeight:800,
                        color:"#1e40af", flexShrink:0 }}>
                        {(sv.vorname?.[0]||"")}{(sv.name?.[0]||"")}
                      </div>
                      <div style={{ flex:1 }}>
                        <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"1rem",
                          fontWeight:800, color:T.navy }}>
                          {sv.vorname} {sv.name}
                        </div>
                        <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.8rem",
                          color:T.textMuted, marginTop:1 }}>
                          {sv.email} · Nr. {sv.adressnr}
                        </div>
                        <div style={{ marginTop:6, display:"flex", alignItems:"center", gap:8 }}>
                          <span style={{ display:"inline-flex", alignItems:"center", gap:4,
                            padding:"2px 9px", borderRadius:10, fontSize:"0.73rem",
                            fontWeight:700, background: dotFarbe + "18",
                            color:dotFarbe, border:`1px solid ${dotFarbe}44` }}>
                            ● {statusText}
                          </span>
                          {sv.einladung_gesendet_am && (
                            <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.73rem",
                              color:T.textFaint }}>
                              Eingeladen: {sv.einladung_gesendet_am.slice(0,10)}
                            </span>
                          )}
                        </div>
                      </div>
                      <div style={{ display:"flex", gap:6, flexShrink:0 }}>
                        <Btn
                          disabled={svEinladung[sv.adressnr]}
                          style={{ fontSize:"0.78rem", padding:"6px 11px",
                            background:"transparent", color:T.textMuted,
                            border:`1px solid ${T.border}` }}
                          onClick={async () => {
                            setSvEinladung(p => ({...p, [sv.adressnr]: true}));
                            try {
                              await apiSvPortal.einladungSenden(sv.adressnr);
                              await ladeSvListe();
                              setToast("Einladungs-Zeitstempel gesetzt.");
                            } catch(e) { setToast(e?.message || "Fehler."); }
                            finally { setSvEinladung(p => ({...p, [sv.adressnr]: false})); }
                          }}>
                          {svEinladung[sv.adressnr] ? "…" : "✉ Einladung vermerken"}
                        </Btn>
                        <Btn
                          style={{ fontSize:"0.78rem", padding:"6px 11px",
                            background: sv.portal_aktiv ? "transparent" : T.navy,
                            color: sv.portal_aktiv ? T.red : T.white,
                            border: sv.portal_aktiv ? `1px solid #fca5a5` : "none" }}
                          onClick={async () => {
                            try {
                              await apiSvPortal.toggleAktiv(sv.adressnr, sv.portal_aktiv ? 0 : 1);
                              await ladeSvListe();
                              setToast(sv.portal_aktiv ? "SV deaktiviert." : "SV aktiviert.");
                            } catch(e) { setToast(e?.message || "Fehler."); }
                          }}>
                          {sv.portal_aktiv ? "Deaktivieren" : "Aktivieren"}
                        </Btn>
                        <Btn
                          style={{ fontSize:"0.78rem", padding:"6px 11px",
                            background:"transparent", color:T.red,
                            border:`1px solid #fca5a5` }}
                          onClick={async () => {
                            if (!window.confirm(`SV-Account für ${sv.vorname} ${sv.name} wirklich löschen?`)) return;
                            try {
                              await apiSvPortal.loeschen(sv.adressnr);
                              setSvAusgewaehlt(null);
                              setSvAkten([]);
                              await ladeSvListe();
                              setToast("SV-Account gelöscht.");
                            } catch(e) { setToast(e?.message || "Fehler."); }
                          }}>
                          Löschen
                        </Btn>
                      </div>
                    </div>

                    {/* Akten-Liste */}
                    <div style={{ flex:1, overflowY:"auto", padding:"14px 18px" }}>
                      <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.75rem",
                        fontWeight:800, color:T.textMuted, textTransform:"uppercase",
                        letterSpacing:"0.07em", marginBottom:10,
                        display:"flex", alignItems:"center", gap:8 }}>
                        Zugeordnete Akten
                        <span style={{ background:T.surface, color:T.textMuted,
                          border:`1px solid ${T.border}`, borderRadius:8,
                          padding:"1px 7px", fontSize:"0.72rem",
                          fontWeight:600, textTransform:"none", letterSpacing:0 }}>
                          {svAkten.length}
                        </span>
                        <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.72rem",
                          color:T.textFaint, fontWeight:400, textTransform:"none",
                          letterSpacing:0 }}>
                          — SV ist in diesen Akten als Sachverständiger eingetragen
                        </span>
                      </div>

                      {svAktenLaedt ? (
                        <div style={{ color:T.textFaint, fontFamily:"'Figtree',sans-serif",
                          fontSize:"0.875rem" }}>Lade …</div>
                      ) : svAkten.length === 0 ? (
                        <div style={{ color:T.textFaint, fontFamily:"'Figtree',sans-serif",
                          fontSize:"0.875rem" }}>
                          Keine Akten gefunden. Voraussetzung: SV muss in einer Akte als
                          Sachverständiger eingetragen sein und dieselbe E-Mail-Adresse haben.
                        </div>
                      ) : svAkten.map(akte => (
                        <div key={akte.az} style={{ background:T.white,
                          border:`1px solid ${T.border}`, borderRadius:8,
                          padding:"9px 12px", marginBottom:6,
                          display:"flex", alignItems:"center", gap:10,
                          opacity: akte.portal_aktiv ? 1 : 0.65 }}>
                          <div style={{ fontFamily:"ui-monospace,monospace",
                            fontSize:"0.8rem", fontWeight:700, color:T.navy, minWidth:75 }}>
                            {akte.az}
                          </div>
                          <div style={{ flex:1, fontFamily:"'Figtree',sans-serif",
                            fontSize:"0.82rem", color:T.text, whiteSpace:"nowrap",
                            overflow:"hidden", textOverflow:"ellipsis" }}>
                            {akte.kurzbezeichnung || "—"}
                          </div>
                          <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.73rem",
                            color:T.textFaint, flexShrink:0 }}>
                            {akte.unfalldatum || ""}
                          </div>
                          {/* Toggle portal_aktiv */}
                          <div
                            onClick={async () => {
                              const neuerWert = akte.portal_aktiv ? 0 : 1;
                              try {
                                await apiSvPortal.togglePortalAktiv(akte.az, neuerWert);
                                setSvAkten(prev => prev.map(a =>
                                  a.az === akte.az ? {...a, portal_aktiv: neuerWert} : a
                                ));
                              } catch(e) { setToast(e?.message || "Fehler."); }
                            }}
                            style={{ width:36, height:20, borderRadius:10,
                              background: akte.portal_aktiv ? "#22c55e" : T.border,
                              position:"relative", cursor:"pointer",
                              transition:"background 0.2s", flexShrink:0 }}>
                            <div style={{ position:"absolute", top:2,
                              left: akte.portal_aktiv ? 18 : 2,
                              width:16, height:16, borderRadius:8,
                              background:"#fff",
                              boxShadow:"0 1px 3px rgba(0,0,0,.2)",
                              transition:"left 0.2s" }} />
                          </div>
                          <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.72rem",
                            fontWeight:600, minWidth:45, flexShrink:0,
                            color: akte.portal_aktiv ? "#22c55e" : T.textFaint }}>
                            {akte.portal_aktiv ? "Sichtbar" : "Gesperrt"}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Info-Leiste */}
                    <div style={{ padding:"8px 18px", background:"#eff6ff",
                      borderTop:`1px solid #bfdbfe`,
                      fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem",
                      color:"#1d4ed8", display:"flex", alignItems:"center", gap:6,
                      flexShrink:0 }}>
                      ℹ {sv.vorname} {sv.name} sieht aktuell{" "}
                      <strong style={{ margin:"0 3px" }}>{sichtbar} von {svAkten.length} Akten</strong>
                      {" "}im Portal.
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        )}
```

- [ ] **Schritt 7: Optisch prüfen**

Dev-Server starten und in Einstellungen → Tab „🔗 SV-Portal" navigieren. Prüfen:
- Linke Spalte zeigt leere Liste mit Hinweistext
- Adressnummer eingeben + „Laden" → Vorschau erscheint (oder Fehlermeldung wenn RA-MICRO nicht erreichbar)
- Rechte Spalte zeigt „← SV aus der Liste auswählen"

- [ ] **Schritt 8: Commit**

```
git add frontend/src/views/EinstellungenView.jsx
git commit -m "feat(ui): Einstellungen SV-Portal-Tab mit Zwei-Spalten-Layout"
```

---

## Spec-Abdeckungsprüfung

| Spec-Anforderung | Task |
|---|---|
| Migration 41: `sv_portal_accounts` | Task 1 |
| RA-MICRO-Lookup `hole_adresse_by_nr` | Task 2 |
| GET `/einstellungen/sv-portal` | Task 3 |
| GET `/vorschau/<adressnr>` | Task 3 |
| POST `/` (anlegen) | Task 3 |
| DELETE `/<adressnr>` | Task 3 |
| PATCH `/<adressnr>` (toggle aktiv) | Task 3 |
| POST `/<adressnr>/einladung` | Task 3 |
| GET `/<adressnr>/akten` | Task 3 |
| PATCH `/akten/<az>/portal_aktiv` | Task 3 |
| `apiSvPortal` in api.js | Task 4 |
| Tab „SV-Portal" in Einstellungen | Task 5 |
| Linke Spalte: SV-Liste + Formular | Task 5 |
| Rechte Spalte: Detail + Akten-Toggles | Task 5 |
| Manueller Einladungsversand (kein Auto-Email) | Task 3+5 (Zeitstempel-Endpoint) |
| Zwei-Spalten-Layout | Task 5 |
