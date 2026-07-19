# Klage-Wizard „Entwurf speichern" (Paket 1/4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-07-19-klage-wizard-entwurf-speichern-design.md` (freigegeben RA Schatz 2026-07-19)

**Goal:** Der Klage-Wizard-Zustand überlebt Reload/Akten-Wechsel: expliziter Speichern-Knopf, Fortsetzen-Dialog beim Öffnen, Schließen-Guard, Positions-Abgleich gegen den frischen Aktenstand — Speicherung in SQLite (Tabelle `klage_entwurf`, Migration 61).

**Architektur:** Backend: neue Tabelle `klage_entwurf` (eine Zeile je Akte, Upsert) + drei Endpoints `GET/PUT/DELETE /akten/<az>/klage/entwurf` auf dem bestehenden `klage_bp` (Blueprint-Prefix ist bereits `/akten/<path:akte_id>/klage` — die Spec-Pfade `/klage/entwurf/<akte>` werden auf diese bestehende Konvention abgebildet). Frontend: reines Logik-Modul `klageEntwurfLogik.js` (Serialisierung, Fingerprint-Dirty-Erkennung, Positions-Reconcile, Format-Version-Prüfung), Dialog-Komponente `KlageEntwurfDialog.jsx`, exportierte Kleinkomponenten in `KlageWizard.jsx` (Statusleiste im Footer, Schließen-Guard, Änderungs-Hinweisbox) nach dem bestehenden `TextVeraltetBadge`-Muster. Der gesamte Wizard-Zustand bleibt in `KlageSection.jsx` (dort liegen die 58 `useState`; `KlageWizard.jsx` ist kontrollierte Präsentation).

**Tech Stack:** Python/Flask + SQLite (Backend), React + Vitest (Frontend), pytest.

## Global Constraints

- **TDD strikt:** erst fehlschlagender Test, dann Implementierung.
- **RA-MICRO read-only** — alle Schreibzugriffe nur SQLite.
- **Migration 61 — Reloader-Falle:** `schema_manager.py` braucht 3 Edits (Dict-Eintrag, Dispatch, Handler). Der Flask-Reloader des Dev-Containers stempelt sonst einen Zwischenstand auf das Docker-Volume `dev-data` ([[feedback_migration_reloader_trap]]). **Vor Task 1 den Dev-Backend-Container stoppen** (`docker compose stop backend` im Projekt-Root), nach Abschluss von Task 1 wieder starten und auf der Dev-DB `SELECT MAX(version) FROM schema_version` = 61 verifizieren. Kein `executescript()`, explizite `conn.commit()` um DDL ([[feedback_migration_executescript]]).
- **Deploy-Reihenfolge (falls je Prod):** Migration 61 vor App-Code aufs Volume, sonst „no such column/table".
- **AZ-Normalisierung:** in den neuen Endpoints IMMER `_pruefe_akte`-Rückgabewert nutzen (`az = getattr(akte_obj, "aktenzeichen", akte_id)`), nie den rohen URL-Param ([[feedback_pruefe_akte_normalisierung]]).
- **Baseline:** Backend hat bekannte Alt-Failure-Cluster (`test_modul2/3/4/7`, `test_sv_portal`, `test_prd27`, zuletzt 204f) — Abnahmekriterium ist **null NEUE Failures**. Frontend: alle Vitest grün (zuletzt 223) + `npm run build` grün.
- **Test-Ausführung:** Backend aus dem Projekt-Root `unfallakten/`: `python -m pytest backend/tests/<datei> -v` (conftest.py setzt die Env-Vars). Frontend aus `frontend/`: `npx vitest run <datei>` bzw. `npm run build`. NIEMALS `run_in_background`, immer blockierend, Timeout bis 600000 ms.
- **Keine Code-Kommentare** außer bei nicht-offensichtlichem Verhalten (Projektregel).
- **Branch:** `klage-wizard-entwurf` (von `main` abzweigen, erster Schritt Task 1). Commits deutsch im bestehenden Stil (`feat(klage): …`). Git-Wurzel ist das Home-Verzeichnis — NIE `git add -A`, immer Dateien einzeln stagen ([[feedback_git_root_ist_home]]).
- **Zeilennummern** in diesem Plan: Stand `main` 68ba3e49 (Erhebung 2026-07-19). Vor jedem Edit die Stelle frisch per Grep/Read verifizieren.

**Spec-Interpretationen (bei Umsetzung nicht neu diskutieren):**
1. Die Spec speichert Positionen als „key + checked", verlangt aber die Änderungsmeldung „Geänderter Betrag". Dafür wird je Position zusätzlich `betrag` (der offene Betrag zum Speicherzeitpunkt) und `label` (für lesbare Meldungen) im Entwurf abgelegt — **nur** zur Diff-Anzeige; übernommen wird immer der frische Betrag.
2. `entwurf_json` enthält ALLE Zustände, die `oeffneWizard()` initialisiert (die Spec-Aufzählung ist eine Teilmenge): zusätzlich `wizardVerzugDatum`, `wizardVerzugDokDatum`, `wizardHqTyp`, `wizardHb`, `wizardRvgBereitsGezahlt`, `wizardGerichtBest`, `wizardAntraegeBasis` (ohne die gespeicherte Basis würde der bestehende `TextVeraltetBadge`-Mechanismus nach dem Fortsetzen nicht anschlagen). NICHT enthalten: Gericht, `rvgData`/`wizardRvgAussergData` (werden neu berechnet), `kiLaedt`, `gespeichertGb`.
3. `DELETE /entwurf` wird lt. Spec gebaut, hat aber im Frontend bewusst KEINEN Aufrufer: „Neu beginnen" löscht nicht (Schutz vor Fehlklick, Entwurf wird erst beim nächsten Speichern überschrieben).
4. Schlägt das Laden des Entwurfs beim Öffnen fehl (Serverfehler ≠ 404), startet der Wizard frisch — wie heute; der Entwurf in der DB bleibt dabei unangetastet, bis der Nutzer aktiv speichert.

---

### Task 1: Migration 61 — Tabelle `klage_entwurf`

**Files:**
- Modify: `backend/db/schema_manager.py` — 3 Stellen: `MIGRATIONS`-Dict (letzter Eintrag `60:` bei `:314`), Dispatch-Kette in `run_migrations` (`elif version == 60:` bei `:1459`), neuer Handler `_run_migration_61` (neben `_run_migration_60` bei `:1010`)
- Test: `backend/tests/test_migration_61.py` (neu)
- KEIN Edit an `backend/db/schema.py` (neuere Tabellen entstehen nur per Migration, `CREATE TABLE IF NOT EXISTS` deckt frische DBs ab)

**Interfaces:**
- Consumes: `schema_version`-Tabelle, `unfallakte(az)` als FK-Ziel, `logger` (im Modul vorhanden).
- Produces: Tabelle `klage_entwurf` mit Spalten `id INTEGER PK`, `akte_id TEXT NOT NULL UNIQUE REFERENCES unfallakte(az) ON DELETE CASCADE`, `entwurf_json TEXT NOT NULL`, `format_version INTEGER NOT NULL`, `gespeichert_am TEXT NOT NULL DEFAULT (datetime('now','localtime'))`. Spätere Tasks verlassen sich exakt auf diese Namen.

- [ ] **Step 0: Dev-Backend stoppen + Branch anlegen**

```powershell
docker compose stop backend
git checkout -b klage-wizard-entwurf
```

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`backend/tests/test_migration_61.py` (vollständig, Muster `test_migration_60.py`):

```python
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig61_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return sm, db_mod


class TestMigration61(unittest.TestCase):
    def test_tabelle_vorhanden_nach_init(self):
        sm, db_mod = _fresh_db("vorhanden")
        with db_mod.get_connection() as conn:
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(klage_entwurf)").fetchall()}
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertEqual(
            spalten,
            {"id", "akte_id", "entwurf_json", "format_version", "gespeichert_am"})
        self.assertGreaterEqual(version, 61)

    def test_akte_id_unique(self):
        sm, db_mod = _fresh_db("unique")
        import sqlite3
        with db_mod.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('61/26', '2026-02-01', 'offen')")
            conn.execute(
                "INSERT INTO klage_entwurf (akte_id, entwurf_json, format_version) "
                "VALUES ('61/26', '{}', 1)")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO klage_entwurf (akte_id, entwurf_json, format_version) "
                    "VALUES ('61/26', '{}', 1)")

    def test_migration_zieht_fehlende_tabelle_nach(self):
        sm, db_mod = _fresh_db("nachziehen")
        with db_mod.get_connection() as conn:
            conn.execute("DROP TABLE klage_entwurf")
            conn.commit()
            sm._run_migration_61(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(klage_entwurf)").fetchall()}
        self.assertIn("entwurf_json", spalten)

    def test_idempotent(self):
        sm, db_mod = _fresh_db("idem")
        with db_mod.get_connection() as conn:
            sm._run_migration_61(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(klage_entwurf)").fetchall()}
        self.assertIn("entwurf_json", spalten)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `python -m pytest backend/tests/test_migration_61.py -v`
Expected: FAIL (`klage_entwurf` existiert nicht / `_run_migration_61` fehlt: AttributeError bzw. leere Spaltenmenge).

- [ ] **Step 3: Migration implementieren — alle 3 Edits an `schema_manager.py` zügig nacheinander (Container ist gestoppt)**

(a) `MIGRATIONS`-Dict, direkt nach dem `60:`-Eintrag (`:314`):

```python
    61: "-- migration_61_klage_entwurf",  # Handled by _run_migration_61 (Klage-Wizard Entwurf)
```

(b) Dispatch in `run_migrations`, nach `elif version == 60:` (`:1459–1460`):

```python
            elif version == 61:
                _run_migration_61(conn)
```

(c) Handler, direkt nach `_run_migration_60` (`:1045`):

```python
def _run_migration_61(conn: sqlite3.Connection) -> None:
    """
    Migration 61 - Neue Tabelle klage_entwurf (Klage-Wizard Entwurf speichern).

    Eine Zeile je Akte (akte_id UNIQUE, Upsert per ON CONFLICT). entwurf_json
    traegt den kompletten Wizard-Zustand als JSON, format_version erkennt
    Entwuerfe aelterer Wizard-Staende (Fortsetzen-Dialog bietet dann nur
    "Neu beginnen"). Kein executescript, explizite Commits um DDL
    (feedback_migration_executescript / Reloader-Falle).
    """
    conn.commit()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS klage_entwurf (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id         TEXT    NOT NULL UNIQUE
                            REFERENCES unfallakte(az) ON DELETE CASCADE,
            entwurf_json    TEXT    NOT NULL,
            format_version  INTEGER NOT NULL,
            gespeichert_am  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (61, "Migration 61 - Tabelle klage_entwurf (Klage-Wizard Entwurf)"),
    )
    logger.info("Migration 61 abgeschlossen (Tabelle klage_entwurf).")
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python -m pytest backend/tests/test_migration_61.py -v`
Expected: 4 passed.

Zusätzlich Regressionscheck der Migrationskette: `python -m pytest backend/tests/test_migration_58.py backend/tests/test_migration_59.py backend/tests/test_migration_60.py -v` → alle grün.

- [ ] **Step 5: Dev-Backend starten + Dev-DB verifizieren**

```powershell
docker compose start backend
docker compose exec backend python -c "import sqlite3; c=sqlite3.connect('/data/unfallakten.db'); print(c.execute('SELECT MAX(version) FROM schema_version').fetchone()); print(c.execute(\"SELECT name FROM sqlite_master WHERE name='klage_entwurf'\").fetchone())"
```

Expected: `(61,)` und `('klage_entwurf',)`. (Pfad der Dev-DB ggf. frisch verifizieren — aktive DB liegt im Docker-Volume `dev-data`, NICHT in `backend/data/`.)

- [ ] **Step 6: Commit**

```powershell
git add backend/db/schema_manager.py backend/tests/test_migration_61.py
git commit -m "feat(klage): Migration 61 - Tabelle klage_entwurf (Entwurf speichern, Paket 1)"
```

---

### Task 2: Endpoints GET/PUT/DELETE `/akten/<az>/klage/entwurf`

**Files:**
- Modify: `backend/routers/klage_routes.py` (Handler ans Dateiende hinter `speichere_gericht` `:1452–1484`; Imports oben `:22–31` prüfen/ergänzen)
- Test: `backend/tests/test_klage_entwurf.py` (neu)

**Interfaces:**
- Consumes: Tabelle `klage_entwurf` (Task 1), `klage_bp` (`url_prefix="/akten/<path:akte_id>/klage"`), `get_connection` (bereits importiert), `_j`/`_err`-Helfer (`:45–46`), `login_erforderlich` (bereits importiert), `pruefe_akte` aus `backend/routers/_helpers.py`.
- Produces (Frontend-Vertrag für Task 4/6):
  - `GET /akten/<az>/klage/entwurf` → 200 `{"entwurf_json": <str>, "format_version": <int>, "gespeichert_am": <"YYYY-MM-DD HH:MM:SS">}` | 404 `{"fehler": …}` wenn Akte oder Entwurf fehlt.
  - `PUT /akten/<az>/klage/entwurf` Body `{"entwurf": <object>, "format_version": <int>=1}` → 200 `{"ok": true, "gespeichert_am": …}` | 422 bei fehlendem/falschem Feld | 404 Akte unbekannt.
  - `DELETE /akten/<az>/klage/entwurf` → 200 `{"ok": true}` (idempotent, auch ohne vorhandenen Entwurf).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`backend/tests/test_klage_entwurf.py` (vollständig; Harness ist das exakte Muster aus `test_klage_kw27_gericht_persistenz.py:29–103` — Temp-DB via `DB_PATH`, `importlib.reload`-Liste, `erstelle_app({"TESTING": True})`, Login-Header):

```python
"""
Klage-Wizard Entwurf speichern (Paket 1): GET/PUT/DELETE /akten/<az>/klage/entwurf.
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp(prefix="klage_entwurf_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"entwurf_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")

    import backend.db.database as db_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.dokument as dok_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as routes_mod
    import backend.app as app_mod

    for m in (db_mod, ben_mod, akte_mod, dok_mod,
              jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
        importlib.reload(m)

    app = app_mod.erstelle_app({"TESTING": True})
    client = app.test_client()

    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('61/26', '2026-02-01', 'offen')"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestKlageEntwurfEndpoints(unittest.TestCase):
    az = "61/26"

    def setUp(self):
        self._alte_db = os.environ.get("DB_PATH")
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def tearDown(self):
        if self._alte_db:
            os.environ["DB_PATH"] = self._alte_db

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_tmp_dir, ignore_errors=True)

    def _put(self, az=None, body=None):
        return self.client.put(
            f"/akten/{az or self.az}/klage/entwurf",
            json=body if body is not None else {
                "entwurf": {"wizardStep": 7, "wizardSachverhaltText": "Text ä ö ü"},
                "format_version": 1,
            },
            headers=self.headers,
        )

    def test_get_ohne_entwurf_404(self):
        r = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r.status_code, 404)

    def test_put_dann_get(self):
        r = self._put()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(r.get_json()["ok"])
        self.assertTrue(r.get_json()["gespeichert_am"])

        r2 = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        d = r2.get_json()
        self.assertEqual(d["format_version"], 1)
        self.assertIn('"wizardStep": 7', d["entwurf_json"])
        self.assertIn("ä ö ü", d["entwurf_json"])
        self.assertTrue(d["gespeichert_am"])

    def test_put_ist_upsert_eine_zeile(self):
        self._put()
        self._put(body={"entwurf": {"wizardStep": 9}, "format_version": 2})
        from backend.db.database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT format_version FROM klage_entwurf WHERE akte_id = ?",
                (self.az,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["format_version"], 2)

    def test_put_validierung_422(self):
        self.assertEqual(self._put(body={"format_version": 1}).status_code, 422)
        self.assertEqual(
            self._put(body={"entwurf": "kein-objekt", "format_version": 1}).status_code, 422)
        self.assertEqual(
            self._put(body={"entwurf": {}, "format_version": "1"}).status_code, 422)
        self.assertEqual(
            self._put(body={"entwurf": {}}).status_code, 422)

    def test_az_normalisierung(self):
        r = self._put(az="6126")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r2 = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r2.status_code, 200)

    def test_unbekannte_akte_404(self):
        r = self._put(az="999/99")
        self.assertEqual(r.status_code, 404)

    def test_delete_idempotent(self):
        self._put()
        r = self.client.delete(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r2.status_code, 404)
        r3 = self.client.delete(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r3.status_code, 200)


if __name__ == "__main__":
    unittest.main()
```

Hinweis zu `test_unbekannte_akte_404`: `_pruefe_akte` gibt für ein wohlgeformtes, aber unbekanntes AZ (`999/99`) ein `SimpleNamespace` zurück (RA-MICRO-only-Fall). Der PUT läuft dann in den FK-Fehler (`REFERENCES unfallakte(az)`) — der Handler fängt `sqlite3.IntegrityError` und antwortet 404 (siehe Step 3).

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_entwurf.py -v`
Expected: FAIL, alle Requests auf `/entwurf` mit 404/405 (Route existiert nicht).

- [ ] **Step 3: Endpoints implementieren**

In `backend/routers/klage_routes.py` — Imports prüfen: `json` und `sqlite3` per Grep im Datei-Kopf verifizieren, fehlende ergänzen (`import json`, `import sqlite3`); dazu `from ._helpers import pruefe_akte as _pruefe_akte`. Dann ans Dateiende:

```python
@klage_bp.route("/entwurf", methods=["GET"])
@login_erforderlich
def hole_klage_entwurf(akte_id: str):
    """
    GET /akten/<az>/klage/entwurf
    Liefert den gespeicherten Wizard-Entwurf; 404 wenn keiner existiert.
    """
    akte_obj = _pruefe_akte(akte_id)
    if not akte_obj:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = getattr(akte_obj, "aktenzeichen", akte_id)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT entwurf_json, format_version, gespeichert_am "
            "FROM klage_entwurf WHERE akte_id = ?", (az,)
        ).fetchone()
    if not row:
        return _err("Kein Entwurf vorhanden.", 404)
    return _j({
        "entwurf_json": row["entwurf_json"],
        "format_version": row["format_version"],
        "gespeichert_am": row["gespeichert_am"],
    })


@klage_bp.route("/entwurf", methods=["PUT"])
@login_erforderlich
def speichere_klage_entwurf(akte_id: str):
    """
    PUT /akten/<az>/klage/entwurf
    Upsert des Wizard-Entwurfs. Body: { entwurf: <Objekt>, format_version: <int> }
    """
    akte_obj = _pruefe_akte(akte_id)
    if not akte_obj:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = getattr(akte_obj, "aktenzeichen", akte_id)

    daten = request.get_json(silent=True) or {}
    entwurf = daten.get("entwurf")
    fv = daten.get("format_version")
    if not isinstance(entwurf, dict):
        return _err("entwurf (Objekt) ist erforderlich.", 422)
    if not isinstance(fv, int) or isinstance(fv, bool) or fv < 1:
        return _err("format_version (Ganzzahl >= 1) ist erforderlich.", 422)

    entwurf_json = json.dumps(entwurf, ensure_ascii=False)
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO klage_entwurf
                       (akte_id, entwurf_json, format_version, gespeichert_am)
                   VALUES (?, ?, ?, datetime('now','localtime'))
                   ON CONFLICT(akte_id) DO UPDATE SET
                       entwurf_json   = excluded.entwurf_json,
                       format_version = excluded.format_version,
                       gespeichert_am = excluded.gespeichert_am""",
                (az, entwurf_json, fv)
            )
            row = conn.execute(
                "SELECT gespeichert_am FROM klage_entwurf WHERE akte_id = ?",
                (az,)
            ).fetchone()
    except sqlite3.IntegrityError:
        # Akte existiert nur in RA-MICRO, nicht in SQLite -> FK schlaegt an
        return _err(f"Akte {az} ist nicht in der lokalen Datenbank angelegt.", 404)
    return _j({"ok": True, "gespeichert_am": row["gespeichert_am"]})


@klage_bp.route("/entwurf", methods=["DELETE"])
@login_erforderlich
def loesche_klage_entwurf(akte_id: str):
    """
    DELETE /akten/<az>/klage/entwurf
    Loescht den Entwurf; idempotent (200 auch ohne vorhandenen Entwurf).
    """
    akte_obj = _pruefe_akte(akte_id)
    if not akte_obj:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = getattr(akte_obj, "aktenzeichen", akte_id)
    with get_connection() as conn:
        conn.execute("DELETE FROM klage_entwurf WHERE akte_id = ?", (az,))
    return _j({"ok": True})
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `python -m pytest backend/tests/test_klage_entwurf.py -v`
Expected: 7 passed.

Regressionscheck Klage-Routen: `python -m pytest backend/tests/test_klage_kw27_gericht_persistenz.py backend/tests/test_klage_kw18_route.py -v` → grün.

- [ ] **Step 5: Commit**

```powershell
git add backend/routers/klage_routes.py backend/tests/test_klage_entwurf.py
git commit -m "feat(klage): Endpoints GET/PUT/DELETE /klage/entwurf (Upsert, AZ-Normalisierung)"
```

---

### Task 3: Reines Logik-Modul `klageEntwurfLogik.js`

**Files:**
- Create: `frontend/src/sections/klageEntwurfLogik.js`
- Test: `frontend/src/sections/klageEntwurfLogik.test.js` (co-located, `.js` — Muster `splitLogik.js`/`splitLogik.test.js`)

**Interfaces:**
- Consumes: nichts (reine Funktionen, keine React-/API-Imports).
- Produces (exakt diese Namen nutzen Task 4–8):
  - `ENTWURF_FORMAT_VERSION` — `1` (Integer; bei künftigen Wizard-Umbauten hochzählen)
  - `serialisiereEntwurf(state) -> object` — Snapshot; Keys spiegeln die State-Namen aus `KlageSection.jsx` wörtlich (einzige Ausnahme: `positionen` aus `state.wizardPos`, reduziert auf `{key, checked, betrag, label}`)
  - `parseEntwurf(row) -> {ok: true, entwurf} | {ok: false}` — prüft `format_version === ENTWURF_FORMAT_VERSION` und JSON-Parsebarkeit (korrupt ⇒ `{ok: false}`, wirft nie)
  - `reconcilePositionen(entwurfPositionen, frischePositionen) -> {positionen, aenderungen}` — `positionen` hat Form/Reihenfolge der frischen Positionen (inkl. frischer Beträge), `checked` aus dem Entwurf; `aenderungen` ist ein String-Array für die gelbe Hinweis-Box
  - `formatGespeichertAm(iso) -> string` — `"2026-07-19 14:32:05"` → `"19.07., 14:32"`

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`frontend/src/sections/klageEntwurfLogik.test.js` (vollständig):

```js
import { describe, it, expect } from "vitest";
import {
  ENTWURF_FORMAT_VERSION,
  serialisiereEntwurf,
  parseEntwurf,
  reconcilePositionen,
  formatGespeichertAm,
} from "./klageEntwurfLogik.js";

const beispielState = {
  wizardStep: 7, wizardMaxStep: 8,
  aktLegTyp: "eigentum", aktLegFreigabe: "freigabe", aktLegDatum: "2026-03-01",
  auslandsunfall: false,
  wizardSachverhaltText: "SV", wizardSachverhaltManuell: true,
  wizardUnfallText: "U", wizardRwText: "RW",
  wizardVerzugText: "V", wizardVerzugManuell: false,
  wizardVerzugDatum: "2026-04-01", wizardVerzugDokDatum: "2026-03-15",
  wizardAntraegeText: "A", wizardAntraegeManuell: false, wizardAntraegeBasis: null,
  wizardGebuehrenText: "G", wizardGebuehrenManuell: false,
  wizardPos: [
    { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5, betragOriginal: 1500, checked: true },
    { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25, checked: false },
  ],
  wizardMitSG: true, wizardSGMind: 500,
  wizardHq: 100, wizardHqTyp: "gegnerisch", wizardHb: "Auffahrunfall",
  wizardMitFestSg: false, wizardMitFestSach: false,
  wizardRvgAussergOv: "", wizardRvgBereitsGezahlt: "",
  wizardGerichtBest: true,
};

describe("serialisiereEntwurf", () => {
  it("uebernimmt Zustaende unter den State-Namen und reduziert Positionen", () => {
    const e = serialisiereEntwurf(beispielState);
    expect(e.wizardStep).toBe(7);
    expect(e.wizardSachverhaltManuell).toBe(true);
    expect(e.wizardGerichtBest).toBe(true);
    expect(e.positionen).toEqual([
      { key: "reparatur", checked: true, betrag: 1200.5, label: "Reparaturkosten" },
      { key: "unkostenpauschale", checked: false, betrag: 25, label: "Unkostenpauschale" },
    ]);
    expect(e).not.toHaveProperty("wizardPos");
    expect(e).not.toHaveProperty("rvgData");
    expect(e).not.toHaveProperty("wizardRvgAussergData");
  });

  it("ist deterministisch (Fingerprint-Grundlage)", () => {
    expect(JSON.stringify(serialisiereEntwurf(beispielState)))
      .toBe(JSON.stringify(serialisiereEntwurf({ ...beispielState })));
  });
});

describe("parseEntwurf", () => {
  const gueltig = {
    entwurf_json: JSON.stringify(serialisiereEntwurf(beispielState)),
    format_version: ENTWURF_FORMAT_VERSION,
    gespeichert_am: "2026-07-19 14:32:05",
  };

  it("akzeptiert gueltigen Entwurf", () => {
    const p = parseEntwurf(gueltig);
    expect(p.ok).toBe(true);
    expect(p.entwurf.wizardStep).toBe(7);
  });

  it("lehnt fremde format_version ab", () => {
    expect(parseEntwurf({ ...gueltig, format_version: 99 }).ok).toBe(false);
  });

  it("lehnt korruptes JSON ab ohne zu werfen", () => {
    expect(parseEntwurf({ ...gueltig, entwurf_json: "{kaputt" }).ok).toBe(false);
    expect(parseEntwurf({ ...gueltig, entwurf_json: '"nur-string"' }).ok).toBe(false);
    expect(parseEntwurf(null).ok).toBe(false);
  });
});

describe("reconcilePositionen", () => {
  const entwurfPos = [
    { key: "reparatur", checked: true, betrag: 1200.5, label: "Reparaturkosten" },
    { key: "abschleppkosten", checked: true, betrag: 300, label: "Abschleppkosten" },
    { key: "unkostenpauschale", checked: false, betrag: 25, label: "Unkostenpauschale" },
  ];

  it("uebernimmt checked aus dem Entwurf, Betraege aus der frischen Akte", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5, checked: true },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25, checked: true },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    const rep = r.positionen.find(p => p.key === "reparatur");
    const unk = r.positionen.find(p => p.key === "unkostenpauschale");
    expect(rep.checked).toBe(true);
    expect(unk.checked).toBe(false);
  });

  it("neue Position erscheint mit checked=false und Meldung", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5 },
      { key: "abschleppkosten", label: "Abschleppkosten", betrag: 300 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
      { key: "standkosten", label: "Standkosten", betrag: 90 },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    expect(r.positionen.find(p => p.key === "standkosten").checked).toBe(false);
    expect(r.aenderungen.some(a => a.includes("Neue Position") && a.includes("Standkosten"))).toBe(true);
  });

  it("weggefallene Position wird entfernt und gemeldet", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    expect(r.positionen.some(p => p.key === "abschleppkosten")).toBe(false);
    expect(r.aenderungen.some(a => a.includes("entfallen") && a.includes("Abschleppkosten"))).toBe(true);
  });

  it("geaenderter Betrag: frischer Betrag gilt, Meldung mit alt und neu", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 900 },
      { key: "abschleppkosten", label: "Abschleppkosten", betrag: 300 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
    ];
    const r = reconcilePositionen(entwurfPos, frisch);
    expect(r.positionen.find(p => p.key === "reparatur").betrag).toBe(900);
    const meldung = r.aenderungen.find(a => a.includes("Betrag"));
    expect(meldung).toContain("Reparaturkosten");
    expect(meldung).toContain("1200,50");
    expect(meldung).toContain("900,00");
  });

  it("unveraendert: leere Aenderungsliste", () => {
    const frisch = [
      { key: "reparatur", label: "Reparaturkosten", betrag: 1200.5 },
      { key: "abschleppkosten", label: "Abschleppkosten", betrag: 300 },
      { key: "unkostenpauschale", label: "Unkostenpauschale", betrag: 25 },
    ];
    expect(reconcilePositionen(entwurfPos, frisch).aenderungen).toEqual([]);
  });

  it("vertraegt leere/fehlende Eingaben", () => {
    expect(reconcilePositionen(null, []).positionen).toEqual([]);
    expect(reconcilePositionen(null, []).aenderungen).toEqual([]);
  });
});

describe("formatGespeichertAm", () => {
  it("formatiert SQLite-localtime", () => {
    expect(formatGespeichertAm("2026-07-19 14:32:05")).toBe("19.07., 14:32");
  });
  it("vertraegt leere/kaputte Werte", () => {
    expect(formatGespeichertAm("")).toBe("");
    expect(formatGespeichertAm(null)).toBe("");
    expect(formatGespeichertAm("unfug")).toBe("unfug");
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run (aus `frontend/`): `npx vitest run src/sections/klageEntwurfLogik.test.js`
Expected: FAIL (Modul existiert nicht).

- [ ] **Step 3: Modul implementieren**

`frontend/src/sections/klageEntwurfLogik.js` (vollständig):

```js
// Klage-Wizard "Entwurf speichern" (Paket 1): reine Logik ohne React/API.
// ENTWURF_FORMAT_VERSION bei jedem Umbau des Entwurf-Schemas hochzaehlen --
// alte Entwuerfe bieten dann im Oeffnen-Dialog nur noch "Neu beginnen".

export const ENTWURF_FORMAT_VERSION = 1;

export function serialisiereEntwurf(s) {
  return {
    wizardStep: s.wizardStep,
    wizardMaxStep: s.wizardMaxStep,
    aktLegTyp: s.aktLegTyp,
    aktLegFreigabe: s.aktLegFreigabe,
    aktLegDatum: s.aktLegDatum,
    auslandsunfall: !!s.auslandsunfall,
    wizardSachverhaltText: s.wizardSachverhaltText,
    wizardSachverhaltManuell: !!s.wizardSachverhaltManuell,
    wizardUnfallText: s.wizardUnfallText,
    wizardRwText: s.wizardRwText,
    wizardVerzugText: s.wizardVerzugText,
    wizardVerzugManuell: !!s.wizardVerzugManuell,
    wizardVerzugDatum: s.wizardVerzugDatum,
    wizardVerzugDokDatum: s.wizardVerzugDokDatum,
    wizardAntraegeText: s.wizardAntraegeText,
    wizardAntraegeManuell: !!s.wizardAntraegeManuell,
    wizardAntraegeBasis: s.wizardAntraegeBasis ?? null,
    wizardGebuehrenText: s.wizardGebuehrenText,
    wizardGebuehrenManuell: !!s.wizardGebuehrenManuell,
    positionen: (s.wizardPos || []).map(p => ({
      key: p.key,
      checked: !!p.checked,
      betrag: p.betrag ?? 0,
      label: p.label ?? p.key,
    })),
    wizardMitSG: !!s.wizardMitSG,
    wizardSGMind: s.wizardSGMind ?? 0,
    wizardHq: s.wizardHq ?? 100,
    wizardHqTyp: s.wizardHqTyp ?? "gegnerisch",
    wizardHb: s.wizardHb ?? "",
    wizardMitFestSg: !!s.wizardMitFestSg,
    wizardMitFestSach: !!s.wizardMitFestSach,
    wizardRvgAussergOv: s.wizardRvgAussergOv ?? "",
    wizardRvgBereitsGezahlt: s.wizardRvgBereitsGezahlt ?? "",
    wizardGerichtBest: !!s.wizardGerichtBest,
  };
}

export function parseEntwurf(row) {
  if (!row || typeof row.entwurf_json !== "string") return { ok: false };
  if (row.format_version !== ENTWURF_FORMAT_VERSION) return { ok: false };
  try {
    const entwurf = JSON.parse(row.entwurf_json);
    if (!entwurf || typeof entwurf !== "object" || Array.isArray(entwurf)) {
      return { ok: false };
    }
    return { ok: true, entwurf };
  } catch {
    return { ok: false };
  }
}

const fmtEur = n =>
  (Number(n) || 0).toFixed(2).replace(".", ",") + " €";

export function reconcilePositionen(entwurfPositionen, frischePositionen) {
  const alt = new Map((entwurfPositionen || []).map(p => [p.key, p]));
  const frischKeys = new Set((frischePositionen || []).map(p => p.key));
  const aenderungen = [];

  const positionen = (frischePositionen || []).map(p => {
    const a = alt.get(p.key);
    if (!a) {
      aenderungen.push(`Neue Position: ${p.label ?? p.key}`);
      return { ...p, checked: false };
    }
    if (Math.abs((Number(a.betrag) || 0) - (Number(p.betrag) || 0)) > 0.005) {
      aenderungen.push(
        `Betrag geändert: ${p.label ?? p.key} (${fmtEur(a.betrag)} → ${fmtEur(p.betrag)})`
      );
    }
    return { ...p, checked: !!a.checked };
  });

  (entwurfPositionen || []).forEach(a => {
    if (!frischKeys.has(a.key)) {
      aenderungen.push(`Position entfallen: ${a.label ?? a.key}`);
    }
  });

  return { positionen, aenderungen };
}

export function formatGespeichertAm(iso) {
  if (!iso) return "";
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if (!m) return String(iso);
  return `${m[3]}.${m[2]}., ${m[4]}:${m[5]}`;
}
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/sections/klageEntwurfLogik.test.js`
Expected: alle Tests passed.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/sections/klageEntwurfLogik.js frontend/src/sections/klageEntwurfLogik.test.js
git commit -m "feat(klage): Entwurf-Logikmodul (Serialisierung, parseEntwurf, Positions-Reconcile)"
```

---

### Task 4: API-Helfer + Speichern-Infrastruktur in `KlageSection.jsx`

**Files:**
- Modify: `frontend/src/api.js` — `apiKlage`-Objekt (`:295–337`), drei Zeilen ergänzen
- Modify: `frontend/src/sections/KlageSection.jsx` — Imports (`:2–16`), exportierter Helfer neben `gerichtSpeichernOderWarnen` (`:44–52`), neue States beim Wizard-State-Block (`:205–252`), `speichereEntwurf`/`aktuellerEntwurf` im Komponentenrumpf, Auto-Save in `wizardGenerieren` (Erfolgspfad bei `:552`)
- Test: `frontend/src/sections/KlageSection.entwurf.test.jsx` (neu)

**Interfaces:**
- Consumes: `serialisiereEntwurf`, `ENTWURF_FORMAT_VERSION` (Task 3); Endpoint-Vertrag (Task 2); `request`-Wrapper in `api.js`.
- Produces:
  - `api.js`: `apiKlage.entwurfLaden(az)`, `apiKlage.entwurfSpeichern(az, body)`, `apiKlage.entwurfLoeschen(az)`
  - `KlageSection.jsx` Export: `entwurfSpeichernRemote(akteId, entwurf) -> Promise<{ok: true, gespeichertAm} | {ok: false, fehler}>`
  - Komponentenintern (Task 5–8 verdrahten dagegen): `speichereEntwurf() -> Promise<boolean>`, `aktuellerEntwurf() -> object`, States `entwurfLetzterStand`, `entwurfGespeichertAm`, `entwurfFehler`, `entwurfLaeuft`, `entwurfDialog`, `entwurfAenderungen`, abgeleitetes `entwurfDirty`

- [ ] **Step 1: Fehlschlagenden Test schreiben**

`frontend/src/sections/KlageSection.entwurf.test.jsx` (Muster `KlageSection.gericht.test.jsx` — der `../api.js`-Mock muss ALLE fünf von KlageSection importierten Exporte auflisten):

```jsx
import { describe, it, expect, vi } from "vitest";

vi.mock("../api.js", () => ({
  akten: {},
  apiKlage: { entwurfSpeichern: vi.fn() },
  apiGebuehren: {},
  apiFirmen: {},
  beteiligte: {},
}));

import { apiKlage } from "../api.js";
import { entwurfSpeichernRemote } from "./KlageSection.jsx";
import { ENTWURF_FORMAT_VERSION } from "./klageEntwurfLogik.js";

describe("entwurfSpeichernRemote", () => {
  it("sendet entwurf + format_version und liefert gespeichert_am zurueck", async () => {
    apiKlage.entwurfSpeichern.mockResolvedValueOnce({
      ok: true, gespeichert_am: "2026-07-19 14:32:05",
    });
    const r = await entwurfSpeichernRemote("61/26", { wizardStep: 3 });
    expect(apiKlage.entwurfSpeichern).toHaveBeenCalledWith("61/26", {
      entwurf: { wizardStep: 3 },
      format_version: ENTWURF_FORMAT_VERSION,
    });
    expect(r).toEqual({ ok: true, gespeichertAm: "2026-07-19 14:32:05" });
  });

  it("liefert bei Fehlern eine lesbare Warnung statt zu werfen", async () => {
    apiKlage.entwurfSpeichern.mockRejectedValueOnce({ status: 500, message: "kaputt" });
    const r = await entwurfSpeichernRemote("61/26", { wizardStep: 3 });
    expect(r.ok).toBe(false);
    expect(r.fehler).toMatch(/nicht gespeichert/i);
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `npx vitest run src/sections/KlageSection.entwurf.test.jsx`
Expected: FAIL (`entwurfSpeichernRemote` nicht exportiert).

- [ ] **Step 3: Implementieren**

(a) `frontend/src/api.js`, im `apiKlage`-Objekt hinter `gerichtSpeichern` (Stil der Nachbarzeilen):

```js
  entwurfLaden:     (az)       => request(`/akten/${az}/klage/entwurf`),
  entwurfSpeichern: (az, body) => request(`/akten/${az}/klage/entwurf`, {
                                    method: 'PUT', body: JSON.stringify(body) }),
  entwurfLoeschen:  (az)       => request(`/akten/${az}/klage/entwurf`, { method: 'DELETE' }),
```

(b) `KlageSection.jsx` — Import ergänzen (bei den bestehenden Imports `:2–16`):

```js
import {
  ENTWURF_FORMAT_VERSION,
  serialisiereEntwurf,
  parseEntwurf,
  reconcilePositionen,
} from "./klageEntwurfLogik.js";
```

(c) Exportierter Helfer, direkt unter `gerichtSpeichernOderWarnen` (`:52`):

```js
export async function entwurfSpeichernRemote(akteId, entwurf) {
  try {
    const r = await apiKlage.entwurfSpeichern(akteId, {
      entwurf,
      format_version: ENTWURF_FORMAT_VERSION,
    });
    return { ok: true, gespeichertAm: r.gespeichert_am };
  } catch {
    return {
      ok: false,
      fehler: "Entwurf konnte nicht gespeichert werden – Änderungen sind noch nicht gesichert.",
    };
  }
}
```

(d) Neue States, ans Ende des Wizard-State-Blocks (nach `:252`):

```js
  const [entwurfLetzterStand, setEntwurfLetzterStand]   = useState(null);
  const [entwurfGespeichertAm, setEntwurfGespeichertAm] = useState(null);
  const [entwurfFehler, setEntwurfFehler]               = useState(null);
  const [entwurfLaeuft, setEntwurfLaeuft]               = useState(false);
  const [entwurfDialog, setEntwurfDialog]               = useState(null);
  const [entwurfAenderungen, setEntwurfAenderungen]     = useState([]);
```

(e) Im Komponentenrumpf (z. B. nach `oeffneWizard`):

```js
  const aktuellerEntwurf = () => serialisiereEntwurf({
    wizardStep, wizardMaxStep, aktLegTyp, aktLegFreigabe, aktLegDatum,
    auslandsunfall, wizardSachverhaltText, wizardSachverhaltManuell,
    wizardUnfallText, wizardRwText, wizardVerzugText, wizardVerzugManuell,
    wizardVerzugDatum, wizardVerzugDokDatum, wizardAntraegeText,
    wizardAntraegeManuell, wizardAntraegeBasis, wizardGebuehrenText,
    wizardGebuehrenManuell, wizardPos, wizardMitSG, wizardSGMind,
    wizardHq, wizardHqTyp, wizardHb, wizardMitFestSg, wizardMitFestSach,
    wizardRvgAussergOv, wizardRvgBereitsGezahlt, wizardGerichtBest,
  });

  const entwurfDirty = wizardOffen &&
    JSON.stringify(aktuellerEntwurf()) !== entwurfLetzterStand;

  const speichereEntwurf = async () => {
    const entwurf = aktuellerEntwurf();
    setEntwurfLaeuft(true);
    setEntwurfFehler(null);
    const r = await entwurfSpeichernRemote(akteId, entwurf);
    setEntwurfLaeuft(false);
    if (r.ok) {
      setEntwurfLetzterStand(JSON.stringify(entwurf));
      setEntwurfGespeichertAm(r.gespeichertAm);
      return true;
    }
    setEntwurfFehler(r.fehler);
    return false;
  };
```

(f) Auto-Save nach erfolgreichem Generieren: in `wizardGenerieren` im Erfolgspfad unmittelbar VOR `setWizardOffen(false)` (`:552`, frisch verifizieren):

```js
      await speichereEntwurf();
```

(Spec: „beim erfolgreichen Generieren wird der aktuelle Stand einmal automatisch gespeichert, damit Entwurf und erzeugtes DOCX übereinstimmen". Schlägt das Speichern fehl, schließt der Wizard trotzdem — das DOCX ist erzeugt, der Fehler stand im Footer.)

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/sections/KlageSection.entwurf.test.jsx` → passed.
Regressionscheck: `npx vitest run src/sections` → alle bestehenden KlageSection-/KlageWizard-Tests grün.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/api.js frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageSection.entwurf.test.jsx
git commit -m "feat(klage): Entwurf-API-Helfer + Speichern-Infrastruktur in KlageSection"
```

---

### Task 5: Speichern-Knopf + Statusanzeige im Wizard-Footer

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` — neue exportierte Komponente `EntwurfStatusLeiste` (auf Modulebene, neben `TextVeraltetBadge` `:1984`), Einbau in den Footer (`:2756–2799`, zwischen Hinweis-Block `:2774–2783` und Weiter-Button `:2785`), neue Props am Hauptkomponenten-Signaturkopf
- Modify: `frontend/src/sections/KlageSection.jsx` — Prop-Verdrahtung am `<KlageWizard>`-Aufruf (`:576–700`)
- Test: `frontend/src/sections/KlageWizard.entwurf.test.jsx` (neu)

**Interfaces:**
- Consumes: `formatGespeichertAm` (Task 3); aus Task 4: `speichereEntwurf`, `entwurfDirty`, `entwurfGespeichertAm`, `entwurfFehler`, `entwurfLaeuft`.
- Produces: Export `EntwurfStatusLeiste({ dirty, gespeichertAm, fehler, laeuft, onSpeichern })`; neue `KlageWizard`-Props `onEntwurfSpeichern`, `entwurfDirty`, `entwurfGespeichertAm`, `entwurfFehler`, `entwurfLaeuft` (Task 7 nutzt `entwurfDirty` + `onEntwurfSpeichern` weiter).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`frontend/src/sections/KlageWizard.entwurf.test.jsx` (Muster `KlageWizard.antraege-dirty.test.jsx`: exportierte Kleinkomponenten standalone testen):

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EntwurfStatusLeiste } from "./KlageWizard.jsx";

describe("EntwurfStatusLeiste", () => {
  it("zeigt Speichern-Knopf und ruft onSpeichern", () => {
    const onSpeichern = vi.fn();
    render(<EntwurfStatusLeiste dirty={true} gespeichertAm={null}
      fehler={null} laeuft={false} onSpeichern={onSpeichern} />);
    fireEvent.click(screen.getByRole("button", { name: /Entwurf speichern/ }));
    expect(onSpeichern).toHaveBeenCalledTimes(1);
  });

  it("dirty: zeigt 'Ungespeicherte Änderungen'", () => {
    render(<EntwurfStatusLeiste dirty={true} gespeichertAm={"2026-07-19 14:32:05"}
      fehler={null} laeuft={false} onSpeichern={() => {}} />);
    expect(screen.getByText(/Ungespeicherte Änderungen/)).toBeInTheDocument();
  });

  it("gespeichert: zeigt Zeitstempel", () => {
    render(<EntwurfStatusLeiste dirty={false} gespeichertAm={"2026-07-19 14:32:05"}
      fehler={null} laeuft={false} onSpeichern={() => {}} />);
    expect(screen.getByText(/Gespeichert 19\.07\., 14:32/)).toBeInTheDocument();
  });

  it("fehler hat Vorrang und Knopf ist waehrend laeuft gesperrt", () => {
    render(<EntwurfStatusLeiste dirty={true} gespeichertAm={null}
      fehler={"Entwurf konnte nicht gespeichert werden"} laeuft={true}
      onSpeichern={() => {}} />);
    expect(screen.getByText(/nicht gespeichert/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Entwurf speichern/ })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.entwurf.test.jsx`
Expected: FAIL (`EntwurfStatusLeiste` nicht exportiert).

- [ ] **Step 3: Implementieren**

(a) `KlageWizard.jsx`, Modulebene neben `TextVeraltetBadge` — Farben/Abstände an den Stil der Nachbar-Buttons im Footer angleichen (Theme-Objekt `T` verwenden, frisch nachsehen wie `TextVeraltetBadge` es macht):

```jsx
export function EntwurfStatusLeiste({ dirty, gespeichertAm, fehler, laeuft, onSpeichern }) {
  let status = "";
  let statusFarbe = "#6b7280";
  if (fehler) { status = fehler; statusFarbe = "#dc2626"; }
  else if (dirty) { status = "Ungespeicherte Änderungen"; statusFarbe = "#b45309"; }
  else if (gespeichertAm) {
    status = `Gespeichert ${formatGespeichertAm(gespeichertAm)}`;
    statusFarbe = "#15803d";
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
      <button onClick={onSpeichern} disabled={laeuft}
        style={{ padding: "0.4rem 0.8rem", cursor: laeuft ? "wait" : "pointer" }}>
        💾 Entwurf speichern
      </button>
      {status && <span style={{ fontSize: "0.8rem", color: statusFarbe }}>{status}</span>}
    </div>
  );
}
```

Dazu oben in `KlageWizard.jsx`: `import { formatGespeichertAm } from "./klageEntwurfLogik.js";`

(b) Props am Hauptkomponenten-Kopf von `KlageWizard` ergänzen: `onEntwurfSpeichern, entwurfDirty, entwurfGespeichertAm, entwurfFehler, entwurfLaeuft` (Destrukturierung der bestehenden Props frisch nachsehen).

(c) Footer (`:2756–2799`): zwischen dem Hinweis-Block und dem `{step < STEPS.length && …}`-Weiter-Button einfügen:

```jsx
            <EntwurfStatusLeiste dirty={entwurfDirty} gespeichertAm={entwurfGespeichertAm}
              fehler={entwurfFehler} laeuft={entwurfLaeuft} onSpeichern={onEntwurfSpeichern} />
```

(d) `KlageSection.jsx`, `<KlageWizard>`-Aufruf (`:576 ff.`), Props ergänzen:

```jsx
        onEntwurfSpeichern={speichereEntwurf}
        entwurfDirty={entwurfDirty}
        entwurfGespeichertAm={entwurfGespeichertAm}
        entwurfFehler={entwurfFehler}
        entwurfLaeuft={entwurfLaeuft}
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/sections/KlageWizard.entwurf.test.jsx` → passed.
Regressionscheck: `npx vitest run src/sections` → grün.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.entwurf.test.jsx
git commit -m "feat(klage): Speichern-Knopf + Dirty-Status im Wizard-Footer"
```

---

### Task 6: Öffnen-Dialog (Fortsetzen / Neu beginnen / Format-Mismatch) + Wizard-Restore

**Files:**
- Create: `frontend/src/sections/KlageEntwurfDialog.jsx`
- Modify: `frontend/src/sections/KlageSection.jsx` — `oeffneWizard` (`:411–492`) refaktorieren in `berechneWizardPositionen` + `initialisiereWizardFrisch` + neues async `oeffneWizard`; neu `initialisiereWizardAusEntwurf`; Dialog-Render neben `{wizardOffen && …}` (`:575`)
- Test: `frontend/src/sections/KlageEntwurfDialog.test.jsx` (neu)

**Interfaces:**
- Consumes: `apiKlage.entwurfLaden` (Task 4), `parseEntwurf`, `reconcilePositionen`, `formatGespeichertAm` (Task 3), States aus Task 4.
- Produces: `KlageEntwurfDialog({ typ, gespeichertAm, step, onFortsetzen, onNeuBeginnen, onAbbrechen })` mit `typ: "fortsetzen" | "mismatch"`; `KlageSection`-intern `initialisiereWizardFrisch()`, `initialisiereWizardAusEntwurf(entwurf, gespeichertAm)`, `berechneWizardPositionen() -> Array` (Task 8 zeigt `entwurfAenderungen` an, die hier gesetzt werden).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`frontend/src/sections/KlageEntwurfDialog.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import KlageEntwurfDialog from "./KlageEntwurfDialog.jsx";

describe("KlageEntwurfDialog", () => {
  it("fortsetzen: zeigt Datum + Schritt und beide Optionen", () => {
    const onFortsetzen = vi.fn();
    const onNeuBeginnen = vi.fn();
    render(<KlageEntwurfDialog typ="fortsetzen" gespeichertAm="2026-07-19 14:32:05"
      step={7} onFortsetzen={onFortsetzen} onNeuBeginnen={onNeuBeginnen}
      onAbbrechen={() => {}} />);
    expect(screen.getByText(/Entwurf vom 19\.07\., 14:32/)).toBeInTheDocument();
    expect(screen.getByText(/Schritt 7 von 10/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Fortsetzen/ }));
    expect(onFortsetzen).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /Neu beginnen/ }));
    expect(onNeuBeginnen).toHaveBeenCalledTimes(1);
  });

  it("mismatch: nur 'Neu beginnen' + Hinweis auf aeltere Programmversion", () => {
    render(<KlageEntwurfDialog typ="mismatch" onFortsetzen={() => {}}
      onNeuBeginnen={() => {}} onAbbrechen={() => {}} />);
    expect(screen.getByText(/älteren Programmversion/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Fortsetzen/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Neu beginnen/ })).toBeInTheDocument();
  });

  it("abbrechen ruft onAbbrechen", () => {
    const onAbbrechen = vi.fn();
    render(<KlageEntwurfDialog typ="fortsetzen" gespeichertAm="2026-07-19 14:32:05"
      step={2} onFortsetzen={() => {}} onNeuBeginnen={() => {}}
      onAbbrechen={onAbbrechen} />);
    fireEvent.click(screen.getByRole("button", { name: /Abbrechen/ }));
    expect(onAbbrechen).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `npx vitest run src/sections/KlageEntwurfDialog.test.jsx`
Expected: FAIL (Datei existiert nicht).

- [ ] **Step 3: Dialog-Komponente implementieren**

`frontend/src/sections/KlageEntwurfDialog.jsx` (vollständig; Overlay-/Karten-Styling an bestehende Modals im Projekt angleichen — z. B. den Guard/Dialog-Stil in `KlageWizard.jsx` frisch nachsehen):

```jsx
import { formatGespeichertAm } from "./klageEntwurfLogik.js";

export default function KlageEntwurfDialog({
  typ, gespeichertAm, step, onFortsetzen, onNeuBeginnen, onAbbrechen,
}) {
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100 }}>
      <div style={{ background: "#fff", borderRadius: "10px", padding: "1.5rem",
        maxWidth: "26rem", width: "90%", boxShadow: "0 10px 30px rgba(0,0,0,0.25)" }}>
        {typ === "fortsetzen" ? (
          <>
            <h3 style={{ margin: "0 0 0.5rem" }}>Gespeicherter Entwurf gefunden</h3>
            <p>
              Entwurf vom {formatGespeichertAm(gespeichertAm)}{" "}
              (Schritt {step} von 10) — fortsetzen oder neu beginnen?
            </p>
          </>
        ) : (
          <>
            <h3 style={{ margin: "0 0 0.5rem" }}>Entwurf nicht verwendbar</h3>
            <p>
              Der gespeicherte Entwurf stammt aus einer älteren Programmversion
              und kann nicht fortgesetzt werden.
            </p>
          </>
        )}
        <div style={{ display: "flex", gap: "0.6rem", justifyContent: "flex-end",
          marginTop: "1rem" }}>
          <button onClick={onAbbrechen}>Abbrechen</button>
          <button onClick={onNeuBeginnen}>Neu beginnen</button>
          {typ === "fortsetzen" && (
            <button onClick={onFortsetzen} style={{ fontWeight: 600 }}>
              ▶ Fortsetzen
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Dialog-Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/sections/KlageEntwurfDialog.test.jsx` → passed.

- [ ] **Step 5: `oeffneWizard` refaktorieren + Restore verdrahten**

In `KlageSection.jsx` (`:411–492`, frisch verifizieren) — drei Umbauten:

(a) Aus dem heutigen `oeffneWizard`-Rumpf die Positionsberechnung (die `_regMap`/`_workPos`-Passage von `const _regMap = {}` bis einschließlich der zweiten `_workPos`-Zuweisung) unverändert in eine neue Funktion heben:

```js
  const berechneWizardPositionen = () => {
    // ... exakt der heutige Block aus oeffneWizard (Zeilen 417–447) ...
    return _workPos;
  };
```

(b) Den Rest des heutigen `oeffneWizard` in `initialisiereWizardFrisch` umbenennen; darin `setWizardPos(berechneWizardPositionen())` statt des Inline-Blocks, und am Ende zusätzlich die Entwurf-States zurücksetzen:

```js
    setEntwurfLetzterStand(null);
    setEntwurfGespeichertAm(null);
    setEntwurfFehler(null);
    setEntwurfAenderungen([]);
```

(c) Neues `oeffneWizard` + Restore:

```js
  const oeffneWizard = async () => {
    let row = null;
    try {
      row = await apiKlage.entwurfLaden(akteId);
    } catch {
      // 404 (kein Entwurf) oder Serverfehler: wie bisher frisch starten
    }
    if (!row) { initialisiereWizardFrisch(); return; }
    const p = parseEntwurf(row);
    if (p.ok) {
      setEntwurfDialog({
        typ: "fortsetzen", entwurf: p.entwurf, gespeichertAm: row.gespeichert_am,
      });
    } else {
      setEntwurfDialog({ typ: "mismatch" });
    }
  };

  const initialisiereWizardAusEntwurf = (e, gespeichertAm) => {
    const rec = reconcilePositionen(e.positionen, berechneWizardPositionen());
    setWizardPos(rec.positionen);
    setEntwurfAenderungen(rec.aenderungen);
    setAktLegTyp(e.aktLegTyp ?? "eigentum");
    setAktLegFreigabe(e.aktLegFreigabe ?? "freigabe");
    setAktLegDatum(e.aktLegDatum ?? "");
    setAuslandsunfall(!!e.auslandsunfall);
    setWizardSachverhaltText(e.wizardSachverhaltText ?? "");
    setWizardSachverhaltManuell(!!e.wizardSachverhaltManuell);
    setWizardUnfallText(e.wizardUnfallText ?? "");
    setWizardRwText(e.wizardRwText ?? "");
    setWizardVerzugText(e.wizardVerzugText ?? "");
    setWizardVerzugManuell(!!e.wizardVerzugManuell);
    setWizardVerzugDatum(e.wizardVerzugDatum ?? "");
    setWizardVerzugDokDatum(e.wizardVerzugDokDatum ?? "");
    setWizardAntraegeText(e.wizardAntraegeText ?? "");
    setWizardAntraegeManuell(!!e.wizardAntraegeManuell);
    setWizardAntraegeBasis(e.wizardAntraegeBasis ?? null);
    setWizardGebuehrenText(e.wizardGebuehrenText ?? "");
    setWizardGebuehrenManuell(!!e.wizardGebuehrenManuell);
    setWizardMitSG(!!e.wizardMitSG);
    setWizardSGMind(e.wizardSGMind ?? 0);
    setWizardHq(e.wizardHq ?? 100);
    setWizardHqTyp(e.wizardHqTyp ?? "gegnerisch");
    setWizardHb(e.wizardHb ?? "");
    setWizardMitFestSg(!!e.wizardMitFestSg);
    setWizardMitFestSach(!!e.wizardMitFestSach);
    setWizardRvgAussergOv(e.wizardRvgAussergOv ?? "");
    setWizardRvgBereitsGezahlt(e.wizardRvgBereitsGezahlt ?? "");
    setWizardGerichtBest(!!e.wizardGerichtBest);
    setWizardRvgAussergData(null);
    setEntwurfLetzterStand(JSON.stringify(e));
    setEntwurfGespeichertAm(gespeichertAm);
    setEntwurfFehler(null);
    setWizardMaxStep(e.wizardMaxStep || 1);
    setWizardStep(e.wizardStep || 1);
    setWizardOffen(true);
  };
```

(`setEntwurfLetzterStand(JSON.stringify(e))` absichtlich auf den GESPEICHERTEN Entwurf, nicht den reconciled Zustand: hat der Abgleich etwas geändert, zeigt der Footer korrekt „Ungespeicherte Änderungen".)

(d) Dialog-Render in `KlageSection.jsx`, direkt vor `{wizardOffen && …}` (`:575`); Import `KlageEntwurfDialog` oben ergänzen:

```jsx
      {entwurfDialog && (
        <KlageEntwurfDialog
          typ={entwurfDialog.typ}
          gespeichertAm={entwurfDialog.gespeichertAm}
          step={entwurfDialog.entwurf?.wizardStep || 1}
          onFortsetzen={() => {
            const d = entwurfDialog;
            setEntwurfDialog(null);
            initialisiereWizardAusEntwurf(d.entwurf, d.gespeichertAm);
          }}
          onNeuBeginnen={() => { setEntwurfDialog(null); initialisiereWizardFrisch(); }}
          onAbbrechen={() => setEntwurfDialog(null)}
        />
      )}
```

„Neu beginnen" ruft bewusst NICHT `apiKlage.entwurfLoeschen` (Spec: Schutz vor Fehlklick — Entwurf wird erst beim nächsten Speichern überschrieben).

- [ ] **Step 6: Alle Sections-Tests laufen lassen**

Run: `npx vitest run src/sections`
Expected: alle grün (die beiden `oeffneWizard`-Buttons `:979`/`:1356` funktionieren unverändert — async Handler ist für `onClick` transparent).

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/sections/KlageEntwurfDialog.jsx frontend/src/sections/KlageEntwurfDialog.test.jsx frontend/src/sections/KlageSection.jsx
git commit -m "feat(klage): Oeffnen-Dialog Entwurf fortsetzen/neu beginnen + Wizard-Restore mit Positions-Reconcile"
```

---

### Task 7: Schließen-Guard bei ungespeicherten Änderungen

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` — neue exportierte Komponente `SchliessenGuardDialog` (Modulebene), interner State + `schliessenAnfordern` im Hauptkomponentenrumpf, Umverdrahtung der drei Schließ-Stellen: Escape-Handler (`:2523–2527`), Backdrop-Klick (`:2558–2560`), Header-X (`:2595`)
- Test: erweitern `frontend/src/sections/KlageWizard.entwurf.test.jsx`

**Interfaces:**
- Consumes: Props `entwurfDirty`, `onEntwurfSpeichern` (Task 5), bestehendes `onClose`-Prop, `laedt`-Bedingungen der drei Schließ-Stellen.
- Produces: Export `SchliessenGuardDialog({ onEntwurfSpeichern, onClose, onZurueck })`. Wichtig: der programmatische Close nach erfolgreichem Generieren (`setWizardOffen(false)` in `KlageSection`) läuft NICHT über `onClose` des Wizards und bleibt guard-frei — so soll es sein (dort wurde gerade auto-gespeichert).

- [ ] **Step 1: Fehlschlagende Tests ergänzen**

In `KlageWizard.entwurf.test.jsx` anhängen:

```jsx
import { SchliessenGuardDialog } from "./KlageWizard.jsx";
import { waitFor } from "@testing-library/react";

describe("SchliessenGuardDialog", () => {
  it("Speichern & Schließen: erst speichern, bei Erfolg schliessen", async () => {
    const onEntwurfSpeichern = vi.fn().mockResolvedValue(true);
    const onClose = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern}
      onClose={onClose} onZurueck={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(onEntwurfSpeichern).toHaveBeenCalledTimes(1);
  });

  it("Speichern schlaegt fehl: nicht schliessen, zurueck zum Wizard", async () => {
    const onEntwurfSpeichern = vi.fn().mockResolvedValue(false);
    const onClose = vi.fn();
    const onZurueck = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern}
      onClose={onClose} onZurueck={onZurueck} />);
    fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await waitFor(() => expect(onZurueck).toHaveBeenCalledTimes(1));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("Verwerfen schliesst ohne zu speichern", () => {
    const onEntwurfSpeichern = vi.fn();
    const onClose = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern}
      onClose={onClose} onZurueck={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Verwerfen/ }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onEntwurfSpeichern).not.toHaveBeenCalled();
  });

  it("Zurueck zum Wizard schliesst nur den Dialog", () => {
    const onZurueck = vi.fn();
    const onClose = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={() => {}}
      onClose={onClose} onZurueck={onZurueck} />);
    fireEvent.click(screen.getByRole("button", { name: /Zurück zum Wizard/ }));
    expect(onZurueck).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.entwurf.test.jsx`
Expected: neue Tests FAIL (`SchliessenGuardDialog` nicht exportiert), Task-5-Tests weiter grün.

- [ ] **Step 3: Implementieren**

(a) `KlageWizard.jsx`, Modulebene:

```jsx
export function SchliessenGuardDialog({ onEntwurfSpeichern, onClose, onZurueck }) {
  const [laeuft, setLaeuft] = useState(false);
  const speichernUndSchliessen = async () => {
    setLaeuft(true);
    const ok = await onEntwurfSpeichern();
    setLaeuft(false);
    if (ok) onClose();
    else onZurueck();
  };
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1200 }}>
      <div style={{ background: "#fff", borderRadius: "10px", padding: "1.5rem",
        maxWidth: "24rem", width: "90%", boxShadow: "0 10px 30px rgba(0,0,0,0.25)" }}>
        <h3 style={{ margin: "0 0 0.5rem" }}>Ungespeicherte Änderungen</h3>
        <p>Der Entwurf wurde seit der letzten Speicherung geändert.</p>
        <div style={{ display: "flex", gap: "0.6rem", justifyContent: "flex-end",
          marginTop: "1rem", flexWrap: "wrap" }}>
          <button onClick={onZurueck} disabled={laeuft}>Zurück zum Wizard</button>
          <button onClick={onClose} disabled={laeuft}>Verwerfen</button>
          <button onClick={speichernUndSchliessen} disabled={laeuft}
            style={{ fontWeight: 600 }}>
            💾 Speichern &amp; schließen
          </button>
        </div>
      </div>
    </div>
  );
}
```

(`useState` ist in `KlageWizard.jsx` bereits importiert — verifizieren.)

(b) Im Hauptkomponentenrumpf von `KlageWizard`:

```jsx
  const [zeigeSchliessenGuard, setZeigeSchliessenGuard] = useState(false);
  const schliessenAnfordern = () => {
    if (entwurfDirty) setZeigeSchliessenGuard(true);
    else onClose();
  };
```

(c) Die drei Schließ-Stellen umverdrahten (jeweils `onClose(...)` → `schliessenAnfordern()`; die bestehenden `!laedt`-Bedingungen unverändert lassen): Escape-Handler `:2523–2527`, Backdrop-Klick `:2558–2560`, Header-X `:2595`. Achtung beim Escape-`useEffect`: `schliessenAnfordern` in die Dependency-Liste aufnehmen bzw. das bestehende Muster der Effect-Deps dort spiegeln (frisch nachsehen).

(d) Guard-Dialog rendern (im Modal-JSX, neben den anderen Overlays):

```jsx
        {zeigeSchliessenGuard && (
          <SchliessenGuardDialog
            onEntwurfSpeichern={onEntwurfSpeichern}
            onClose={() => { setZeigeSchliessenGuard(false); onClose(); }}
            onZurueck={() => setZeigeSchliessenGuard(false)}
          />
        )}
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/sections` → alle grün (insbesondere bestehende Close-Tests des Wizards: ohne `entwurfDirty`-Prop ist `entwurfDirty` undefined → `schliessenAnfordern` schließt direkt, Verhalten unverändert).

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.entwurf.test.jsx
git commit -m "feat(klage): Schliessen-Guard bei ungespeicherten Entwurfs-Aenderungen"
```

---

### Task 8: Gelbe Hinweis-Box „Seit dem Entwurf geändert"

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` — neue exportierte Komponente `EntwurfAenderungenBox` (Modulebene), Render oben im Inhaltsbereich des Wizards (direkt unter dem Header/über dem Step-Inhalt, Stelle frisch suchen), neue Props `entwurfAenderungen`, `onAenderungenGelesen`
- Modify: `frontend/src/sections/KlageSection.jsx` — Prop-Verdrahtung am `<KlageWizard>`-Aufruf
- Test: erweitern `frontend/src/sections/KlageWizard.entwurf.test.jsx`

**Interfaces:**
- Consumes: `entwurfAenderungen`-State + Setter (Task 4/6).
- Produces: Export `EntwurfAenderungenBox({ aenderungen, onSchliessen })` — rendert `null` bei leerer Liste.

- [ ] **Step 1: Fehlschlagende Tests ergänzen**

In `KlageWizard.entwurf.test.jsx` anhängen:

```jsx
import { EntwurfAenderungenBox } from "./KlageWizard.jsx";

describe("EntwurfAenderungenBox", () => {
  it("rendert nichts bei leerer Liste", () => {
    const { container } = render(
      <EntwurfAenderungenBox aenderungen={[]} onSchliessen={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("listet Aenderungen und laesst sich schliessen", () => {
    const onSchliessen = vi.fn();
    render(<EntwurfAenderungenBox
      aenderungen={["Neue Position: Standkosten", "Betrag geändert: Reparaturkosten (1200,50 € → 900,00 €)"]}
      onSchliessen={onSchliessen} />);
    expect(screen.getByText(/Seit dem Entwurf geändert/)).toBeInTheDocument();
    expect(screen.getByText(/Neue Position: Standkosten/)).toBeInTheDocument();
    expect(screen.getByText(/1200,50 € → 900,00 €/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /✕/ }));
    expect(onSchliessen).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `npx vitest run src/sections/KlageWizard.entwurf.test.jsx`
Expected: neue Tests FAIL.

- [ ] **Step 3: Implementieren**

(a) `KlageWizard.jsx`, Modulebene (Farbschema wie `TextVeraltetBadge` — amber; frisch nachsehen und angleichen):

```jsx
export function EntwurfAenderungenBox({ aenderungen, onSchliessen }) {
  if (!aenderungen || aenderungen.length === 0) return null;
  return (
    <div style={{ background: "#fef3c7", border: "1px solid #f59e0b",
      borderRadius: "8px", padding: "0.75rem 1rem", margin: "0.75rem 1.5rem 0",
      display: "flex", gap: "0.75rem", alignItems: "flex-start" }}>
      <div style={{ flex: 1 }}>
        <b>Seit dem Entwurf geändert:</b>
        <ul style={{ margin: "0.35rem 0 0", paddingLeft: "1.2rem" }}>
          {aenderungen.map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      </div>
      <button onClick={onSchliessen} aria-label="✕"
        style={{ background: "none", border: "none", cursor: "pointer",
          fontSize: "1rem", lineHeight: 1 }}>✕</button>
    </div>
  );
}
```

(b) Props `entwurfAenderungen`, `onAenderungenGelesen` am Hauptkomponenten-Kopf ergänzen; Render direkt unter dem Wizard-Header (über dem Step-Inhalt):

```jsx
        <EntwurfAenderungenBox aenderungen={entwurfAenderungen}
          onSchliessen={onAenderungenGelesen} />
```

(c) `KlageSection.jsx`, `<KlageWizard>`-Props:

```jsx
        entwurfAenderungen={entwurfAenderungen}
        onAenderungenGelesen={() => setEntwurfAenderungen([])}
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `npx vitest run src/sections` → alle grün.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageSection.jsx frontend/src/sections/KlageWizard.entwurf.test.jsx
git commit -m "feat(klage): Hinweis-Box 'Seit dem Entwurf geaendert' nach Fortsetzen"
```

---

### Task 9: Endabnahme — volle Suiten, Build, Doku

**Files:**
- Modify: `docs/DATAMODEL.md` — Tabelle `klage_entwurf` dokumentieren (Bestandsformat der Datei nachsehen und spiegeln: Spalten, Migration 61, Zweck „ein Wizard-Entwurf je Akte, Upsert")
- Modify: `docs/TODO.md` — Klage-Wizard-Verbesserungsrunde: Paket 1 (Entwurf speichern) als umgesetzt markieren (Bestandsformat spiegeln)

**Interfaces:**
- Consumes: alle vorigen Tasks.
- Produces: abnahmefertiger Branch `klage-wizard-entwurf`.

- [ ] **Step 1: Volle Backend-Suite**

Run (blockierend, Timeout 600000 ms; notfalls in zwei Hälften): `python -m pytest backend/tests/ -q`
Expected: **null NEUE Failures** gegenüber der Baseline (bekannte Alt-Cluster `test_modul2/3/4/7`, `test_sv_portal`, `test_prd27` dürfen unverändert rot sein). Neue Tests `test_migration_61.py` + `test_klage_entwurf.py` grün.

- [ ] **Step 2: Volle Frontend-Suite + Build**

Run (aus `frontend/`): `npx vitest run` und danach `npm run build`
Expected: alle Vitest grün (Baseline zuletzt 223 + die neuen Entwurf-Tests), Build ohne Fehler.

- [ ] **Step 3: DEV-Smoke am laufenden System**

Im Browser (Dev-Server): Akte mit Klage-Daten öffnen → Wizard öffnen (kein Dialog, da kein Entwurf) → auf Schritt 3 Text ändern → „💾 Entwurf speichern" → Status „Gespeichert …" → Wizard per X schließen (kein Guard, da gespeichert) → Wizard erneut öffnen → Dialog „Entwurf vom …" → Fortsetzen → Schritt 3 + Texte da → Text ändern → X → Guard-Dialog erscheint → „Zurück zum Wizard" → speichern → schließen. Ergebnis im Plan-Kontext festhalten.

- [ ] **Step 4: Doku aktualisieren + Commit**

`docs/DATAMODEL.md` (klage_entwurf ergänzen) und `docs/TODO.md` (Paket 1 abhaken) im jeweiligen Bestandsformat.

```powershell
git add docs/DATAMODEL.md docs/TODO.md
git commit -m "docs(klage): DATAMODEL klage_entwurf + TODO Paket 1 Entwurf speichern umgesetzt"
```

- [ ] **Step 5: Abschluss**

REQUIRED SUB-SKILL: `superpowers:finishing-a-development-branch` — Freigabe durch RA Schatz einholen, danach (wie bei S3–S6) per FF-Merge in `main`. Nicht pushen (main ist lokal ohnehin ahead origin).
