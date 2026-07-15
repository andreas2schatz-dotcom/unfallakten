# PDF-Splitting im Review-UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein mehrseitiges Sammel-PDF im Review-Dialog entlang von Seitengrenzen in mehrere eigenständige Dokumente auftrennen, die danach einzeln durch die normale Intake-Pipeline laufen.

**Architecture:** Ein neuer, isoliert testbarer Service `backend/intake/split_service.py` zerlegt das Arbeitskopie-PDF mit PyMuPDF in Seitengruppen, legt je Gruppe über die bestehende Persistenz (`oder_intake_dokument_fuer_datei`) ein neues Intake-Dokument mit `queue_status='neu'` an (der Worker klassifiziert es automatisch) und markiert das Original als „aufgeteilt" (Soft-Delete). Drei neue Endpoints (`/split`, `/seiten`, Seiten-`/thumbnail`) und ein Frontend-Dialog mit Seiten-Miniaturen und Scheren-Trennern.

**Tech Stack:** Python/Flask, SQLite, PyMuPDF (`fitz`, bereits installiert), React (Vite), Vitest, pytest/unittest.

## Global Constraints

- **RA-MICRO read-only** — niemals in die RA-MICRO-DB schreiben, nur SQLite.
- **`INTAKE_REVIEW_PFLICHT` gewahrt** — Split schreibt ausschließlich Intake-Tabellen (`intake_dokumente`, `zustellungen`); **nie** Akten-Tabellen. Jeder Teil braucht weiterhin eine menschliche Freigabe.
- **Migrationen** additiv, nullable, idempotent (PRAGMA table_info), mit **explizitem `conn.commit()`** um jedes `ALTER`, **kein `executescript()`** (Muster: `_run_migration_57`).
- **Zielsprache Deutsch** in UI-Texten und Meldungen.
- **Keine Kommentare** außer bei nicht-offensichtlichem Verhalten.
- **Deploy-Reihenfolge:** Migration 58 muss vor App-Start auf dem Volume liegen (sonst `no such column`). Für aktuelles Setup irrelevant (kein Prod-Host, Go-Live vertagt).

## File Structure

**Neu:**
- `backend/intake/split_service.py` — PDF-Primitive (`pdf_seiten_zahl`, `extrahiere_seiten_pdf`, `rendere_thumbnail`), `validiere_gruppen`, `teile_dokument`, `SplitFehler`.
- `backend/tests/test_migration_58.py` — Spalten-Existenz + Idempotenz.
- `backend/tests/test_intake_split_service.py` — Service-Unit + E2E.
- `backend/tests/test_intake_split_routes.py` — Route-Tests.
- `frontend/src/views/splitLogik.js` — reine Funktionen (`gruppenAusSchnitten`, `schnittUmschalten`, `istAufteilbar`).
- `frontend/src/views/splitLogik.test.js` — Vitest der reinen Funktionen.
- `frontend/src/views/SplitDialog.jsx` — Dialog-Komponente.

**Geändert:**
- `backend/db/schema_manager.py` — Migration 58 (Dict-Eintrag + Handler + Dispatch-Zweig).
- `backend/routers/intake_routes.py` — 3 Endpoints, `Response`-Import, `_VERWERFEN_GRUENDE += 'aufgeteilt'`.
- `backend/tests/test_s19_intake_write_guard.py` — `split_service.py` in `INTAKE_PFADE` (Defense-in-depth).
- `frontend/src/api.js` — `apiIntake.seiten`, `apiIntake.split`.
- `frontend/src/views/ReviewQueueView.jsx` — Aufteilen-Button + `SplitDialog`-Einbindung.

**Design-Verfeinerung ggü. Spec:** Der Audit-Link läuft über die Spalte `aufgeteilt_aus_id` (Teil → Original) plus `zustellungen.roh_referenz='split:<id>'`; **kein** `korrektur_log`-Eintrag (hält `split_service` von `intake_routes` entkoppelt, strukturierter Link statt Freitext). Atomarität: alle Teile werden zuerst angelegt (idempotent per `sha256`-Dedup), das Original wird **zuletzt** markiert — bricht ein Schritt ab, bleibt das Original reviewbar (kein Halbstatus, kein Datenverlust), ein erneuter Aufruf dedupliziert die Teile.

---

### Task 1: Migration 58 — `intake_dokumente.aufgeteilt_aus_id`

**Files:**
- Modify: `backend/db/schema_manager.py` (MIGRATIONS-Dict bei Z.307-311; neuer Handler nach `_run_migration_57` ~Z.927; Dispatch bei Z.1329-1343)
- Test: `backend/tests/test_migration_58.py`

**Interfaces:**
- Produces: Spalte `intake_dokumente.aufgeteilt_aus_id INTEGER` (nullable); Handler `_run_migration_58(conn)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migration_58.py
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="mig58_")
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


class TestMigration58(unittest.TestCase):
    def test_spalte_vorhanden(self):
        sm, db_mod = _fresh_db("vorhanden")
        with db_mod.get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
            version = conn.execute(
                "SELECT MAX(version) FROM schema_version").fetchone()[0]
        self.assertIn("aufgeteilt_aus_id", cols)
        self.assertGreaterEqual(version, 58)

    def test_idempotent(self):
        sm, db_mod = _fresh_db("idem")
        with db_mod.get_connection() as conn:
            sm._run_migration_58(conn)  # zweiter Lauf darf nicht werfen
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
        self.assertIn("aufgeteilt_aus_id", cols)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_migration_58.py -v`
Expected: FAIL (`AttributeError: module ... has no attribute '_run_migration_58'` bzw. Spalte fehlt / Version < 58).

- [ ] **Step 3: Write minimal implementation**

Im MIGRATIONS-Dict (nach Z.311) ergänzen:
```python
    58: "-- migration_58_intake_aufgeteilt_aus_id",  # Handled by _run_migration_58 (PDF-Splitting Review-UI)
```

Neuen Handler nach `_run_migration_57` einfügen:
```python
def _run_migration_58(conn: sqlite3.Connection) -> None:
    """
    Migration 58 - intake_dokumente.aufgeteilt_aus_id (PDF-Splitting Review-UI).

    Verweist ein durch Aufteilen entstandenes Teil-Dokument auf sein
    Ursprungs-Dokument. "Original -> seine Teile" per Rueckwaerts-Abfrage
    (WHERE aufgeteilt_aus_id = <id>), keine Doppelspeicherung.

    Additives ALTER TABLE, nullable INTEGER, kein Datenverlust. Idempotent per
    PRAGMA table_info. Explizites conn.commit() (feedback_migration_executescript).
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(intake_dokumente)"
        ).fetchall()
    }
    if "aufgeteilt_aus_id" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE intake_dokumente ADD COLUMN aufgeteilt_aus_id INTEGER"
        )
        conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (58, "Migration 58 - intake_dokumente.aufgeteilt_aus_id "
             "(PDF-Splitting Review-UI)"),
    )
    logger.info("Migration 58 abgeschlossen (intake_dokumente.aufgeteilt_aus_id).")
```

Im `run_migrations()`-Dispatch (nach dem `elif version == 57:`-Zweig, vor `else:`):
```python
            elif version == 58:
                _run_migration_58(conn)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_migration_58.py -v`
Expected: PASS (beide Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_migration_58.py
git commit -m "feat(intake): Migration 58 -- intake_dokumente.aufgeteilt_aus_id"
```

---

### Task 2: PDF-Primitive + Gruppen-Validierung in `split_service.py`

**Files:**
- Create: `backend/intake/split_service.py`
- Test: `backend/tests/test_intake_split_service.py`

**Interfaces:**
- Produces:
  - `class SplitFehler(Exception)` mit Attribut `.status: int`.
  - `pdf_seiten_zahl(pdf_bytes: bytes) -> int`
  - `extrahiere_seiten_pdf(pdf_bytes: bytes, von: int, bis: int) -> bytes` (1-basiert, inklusive)
  - `rendere_thumbnail(pdf_bytes: bytes, seite_nr: int, breite: int = 150) -> bytes` (PNG)
  - `validiere_gruppen(gruppen: list[list[int]], seiten_gesamt: int) -> None` (wirft `SplitFehler(…, 422)`)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_intake_split_service.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import fitz  # PyMuPDF
from backend.intake import split_service as ss


def _mehrseitiges_pdf(n: int) -> bytes:
    doc = fitz.open()
    for i in range(n):
        page = doc.new_page()
        page.insert_text((72, 72), f"Seite {i + 1}")
    out = doc.tobytes()
    doc.close()
    return out


class TestPdfPrimitive(unittest.TestCase):
    def test_seiten_zahl(self):
        self.assertEqual(ss.pdf_seiten_zahl(_mehrseitiges_pdf(5)), 5)

    def test_extrahiere_seiten_pdf(self):
        teil = ss.extrahiere_seiten_pdf(_mehrseitiges_pdf(5), 1, 3)
        self.assertEqual(ss.pdf_seiten_zahl(teil), 3)
        teil2 = ss.extrahiere_seiten_pdf(_mehrseitiges_pdf(5), 4, 5)
        self.assertEqual(ss.pdf_seiten_zahl(teil2), 2)

    def test_rendere_thumbnail_ist_png(self):
        png = ss.rendere_thumbnail(_mehrseitiges_pdf(2), 1)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))


class TestValidiereGruppen(unittest.TestCase):
    def test_gueltig(self):
        ss.validiere_gruppen([[1, 2, 3], [4, 5]], 5)  # kein Fehler

    def test_zu_wenige_gruppen(self):
        with self.assertRaises(ss.SplitFehler) as ctx:
            ss.validiere_gruppen([[1, 2, 3, 4, 5]], 5)
        self.assertEqual(ctx.exception.status, 422)

    def test_luecke(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2], [4, 5]], 5)  # 3 fehlt

    def test_ueberdeckung_falsch(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2], [3, 4]], 5)  # 5 fehlt

    def test_nicht_zusammenhaengend(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 3], [2, 4, 5]], 5)

    def test_leere_gruppe(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2, 3], []], 5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_split_service.py -v`
Expected: FAIL (`ModuleNotFoundError: backend.intake.split_service`).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/intake/split_service.py
"""
Aufteilen mehrseitiger Intake-PDFs entlang von Seitengrenzen (PDF-Splitting).

Reine PDF-Primitive (PyMuPDF) + Gruppen-Validierung; die Orchestrierung
(teile_dokument) folgt in Task 3. Schreibt ausschliesslich Intake-Tabellen,
nie Akten-Tabellen (INTAKE_REVIEW_PFLICHT bleibt gewahrt).
"""
from __future__ import annotations

import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class SplitFehler(Exception):
    """Fachlicher Split-Fehler mit HTTP-Status (422 = ungueltig, 409 = Zustand)."""

    def __init__(self, meldung: str, status: int):
        super().__init__(meldung)
        self.status = status


def pdf_seiten_zahl(pdf_bytes: bytes) -> int:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


def extrahiere_seiten_pdf(pdf_bytes: bytes, von: int, bis: int) -> bytes:
    """Neues PDF mit den Seiten von..bis (1-basiert, inklusive)."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as src:
        neu = fitz.open()
        neu.insert_pdf(src, from_page=von - 1, to_page=bis - 1)
        out = neu.tobytes()
        neu.close()
    return out


def rendere_thumbnail(pdf_bytes: bytes, seite_nr: int, breite: int = 150) -> bytes:
    """PNG-Miniatur der Seite (1-basiert), skaliert auf ``breite`` px."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc.load_page(seite_nr - 1)
        zoom = breite / page.rect.width if page.rect.width else 1.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")


def validiere_gruppen(gruppen: list[list[int]], seiten_gesamt: int) -> None:
    """Gruppen muessen zusammenhaengend die Seiten 1..N lueckenlos, in
    Reihenfolge und ohne Ueberlappung abdecken; mindestens 2 Gruppen."""
    if not isinstance(gruppen, list) or len(gruppen) < 2:
        raise SplitFehler("Mindestens 2 Teile erforderlich.", 422)
    erwartet = 1
    for gruppe in gruppen:
        if not gruppe:
            raise SplitFehler("Leere Gruppe nicht erlaubt.", 422)
        for p in gruppe:
            if p != erwartet:
                raise SplitFehler(
                    "Teile muessen die Seiten 1..N lueckenlos und "
                    "zusammenhaengend abdecken.", 422)
            erwartet += 1
    if erwartet - 1 != seiten_gesamt:
        raise SplitFehler(
            f"Teile decken {erwartet - 1} Seiten ab, das PDF hat "
            f"{seiten_gesamt}.", 422)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_split_service.py -v`
Expected: PASS (alle Tests in `TestPdfPrimitive` + `TestValidiereGruppen`).

- [ ] **Step 5: Commit**

```bash
git add backend/intake/split_service.py backend/tests/test_intake_split_service.py
git commit -m "feat(intake): split_service PDF-Primitive + Gruppen-Validierung"
```

---

### Task 3: `teile_dokument` — Orchestrierung (Teile anlegen, Original markieren)

**Files:**
- Modify: `backend/intake/split_service.py`
- Test: `backend/tests/test_intake_split_service.py` (neue Klasse `TestTeileDokument`)

**Interfaces:**
- Consumes: `oder_intake_dokument_fuer_datei(bytes, ext) -> (int, str)` und `erzeuge_zustellung(intake_dokument_id, quelle, *, absender, betreff, empfangen_am, signale, konto, roh_referenz) -> int` aus `backend/intake/_persistenz.py`; `get_connection` aus `backend/db/database.py`.
- Produces: `teile_dokument(intake_id: int, gruppen: list[list[int]], benutzer_id: int | None) -> list[int]` (gibt die neuen Teil-IDs zurück).

- [ ] **Step 1: Write the failing test**

```python
# in backend/tests/test_intake_split_service.py ergaenzen (oben ergaenzen:)
import importlib
import tempfile

_tmp = tempfile.mkdtemp(prefix="split_svc_")


def _setup_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["INTAKE_ARCHIV_ROOT"] = os.path.join(_tmp, f"archiv_{name}")
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return db_mod


def _lege_original_an(db_mod, pdf_bytes, queue_status="bereit_zur_review",
                       payload_typ="datei", mit_zustellung=True):
    from backend.intake._persistenz import (
        oder_intake_dokument_fuer_datei, erzeuge_zustellung)
    intake_id, _sha = oder_intake_dokument_fuer_datei(pdf_bytes, "pdf")
    with db_mod.get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET queue_status=?, payload_typ=? WHERE id=?",
            (queue_status, payload_typ, intake_id))
    if mit_zustellung:
        erzeuge_zustellung(
            intake_id, "imap", absender="schaden@versicherer.de",
            betreff="Sammel-Anlage", empfangen_am="2026-07-15T09:00:00",
            signale={"az": "44/22"}, roh_referenz="msg-1")
    return intake_id


class TestTeileDokument(unittest.TestCase):
    def test_split_legt_teile_an_und_markiert_original(self):
        db_mod = _setup_db("happy")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(5))

        kinder = ss.teile_dokument(oid, [[1, 2, 3], [4, 5]], benutzer_id=7)

        self.assertEqual(len(kinder), 2)
        with db_mod.get_connection() as conn:
            for kid in kinder:
                row = conn.execute(
                    "SELECT queue_status, payload_typ, aufgeteilt_aus_id "
                    "FROM intake_dokumente WHERE id=?", (kid,)).fetchone()
                self.assertEqual(row["queue_status"], "neu")
                self.assertEqual(row["payload_typ"], "datei")
                self.assertEqual(row["aufgeteilt_aus_id"], oid)
                z = conn.execute(
                    "SELECT absender, signale_json, roh_referenz FROM zustellungen "
                    "WHERE intake_dokument_id=?", (kid,)).fetchone()
                self.assertEqual(z["absender"], "schaden@versicherer.de")
                self.assertIn("44/22", z["signale_json"])
                self.assertEqual(z["roh_referenz"], f"split:{oid}")
            orig = conn.execute(
                "SELECT verworfen_grund, verworfen_am, verworfen_von "
                "FROM intake_dokumente WHERE id=?", (oid,)).fetchone()
            self.assertEqual(orig["verworfen_grund"], "aufgeteilt")
            self.assertIsNotNone(orig["verworfen_am"])
            self.assertEqual(orig["verworfen_von"], 7)

    def test_teil_seitenzahl_stimmt(self):
        db_mod = _setup_db("seiten")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(5))
        kinder = ss.teile_dokument(oid, [[1, 2, 3], [4, 5]], benutzer_id=None)
        with db_mod.get_connection() as conn:
            pfade = [conn.execute(
                "SELECT arbeitskopie_pfad FROM intake_dokumente WHERE id=?",
                (k,)).fetchone()["arbeitskopie_pfad"] for k in kinder]
        with open(pfade[0], "rb") as f:
            self.assertEqual(ss.pdf_seiten_zahl(f.read()), 3)
        with open(pfade[1], "rb") as f:
            self.assertEqual(ss.pdf_seiten_zahl(f.read()), 2)

    def test_text_payload_wird_abgelehnt(self):
        db_mod = _setup_db("text")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(3), payload_typ="text")
        with self.assertRaises(ss.SplitFehler) as ctx:
            ss.teile_dokument(oid, [[1, 2], [3]], benutzer_id=None)
        self.assertEqual(ctx.exception.status, 422)

    def test_doppel_split_ist_409(self):
        db_mod = _setup_db("doppel")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(4))
        ss.teile_dokument(oid, [[1, 2], [3, 4]], benutzer_id=None)
        with self.assertRaises(ss.SplitFehler) as ctx:
            ss.teile_dokument(oid, [[1, 2], [3, 4]], benutzer_id=None)
        self.assertEqual(ctx.exception.status, 409)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_split_service.py::TestTeileDokument -v`
Expected: FAIL (`AttributeError: module ... has no attribute 'teile_dokument'`).

- [ ] **Step 3: Write minimal implementation**

Am Anfang von `split_service.py` die Importe ergänzen:
```python
import json
import os
from datetime import datetime, timezone

from ..db.database import get_connection
from ._persistenz import oder_intake_dokument_fuer_datei, erzeuge_zustellung
```

Funktion ans Ende von `split_service.py` anhängen:
```python
def teile_dokument(intake_id: int, gruppen: list[list[int]],
                    benutzer_id: int | None) -> list[int]:
    """Zerlegt das Arbeitskopie-PDF in die angegebenen Seitengruppen.

    Legt je Gruppe ein neues Intake-Dokument (queue_status='neu', der Worker
    klassifiziert automatisch) mit vererbter Zustellung an und markiert das
    Original zuletzt als 'aufgeteilt'. Bricht ein Schritt vorher ab, bleibt das
    Original reviewbar; Teile sind per sha256 idempotent.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM intake_dokumente WHERE id=?", (intake_id,)).fetchone()
    if not row:
        raise SplitFehler("Intake-Dokument nicht gefunden.", 404)
    dok = dict(row)

    if dok.get("payload_typ") != "datei":
        raise SplitFehler("Nur Datei-Dokumente koennen aufgeteilt werden.", 422)
    if dok.get("verworfen_am"):
        raise SplitFehler(
            "Dokument ist verworfen/aufgeteilt und kann nicht aufgeteilt "
            "werden.", 409)
    if dok.get("queue_status") not in ("bereit_zur_review", "pipeline_fehler", "neu"):
        raise SplitFehler(
            f"Dokument im Status {dok.get('queue_status')!r} kann nicht "
            f"aufgeteilt werden.", 409)

    pfad = dok.get("arbeitskopie_pfad")
    if not pfad or not os.path.isfile(pfad):
        raise SplitFehler("Arbeitskopie fehlt.", 422)
    with open(pfad, "rb") as f:
        pdf_bytes = f.read()

    seiten_gesamt = pdf_seiten_zahl(pdf_bytes)
    if seiten_gesamt < 2:
        raise SplitFehler("Dokument hat weniger als 2 Seiten.", 422)
    validiere_gruppen(gruppen, seiten_gesamt)

    with get_connection() as conn:
        zust = conn.execute(
            "SELECT quelle, absender, betreff, empfangen_am, signale_json, konto "
            "FROM zustellungen WHERE intake_dokument_id=? ORDER BY id ASC LIMIT 1",
            (intake_id,)).fetchone()
    quelle = (zust["quelle"] if zust else None) or "upload"
    absender = zust["absender"] if zust else None
    betreff = zust["betreff"] if zust else None
    empfangen_am = zust["empfangen_am"] if zust else None
    konto = zust["konto"] if zust else None
    signale = json.loads(zust["signale_json"]) if (zust and zust["signale_json"]) else None

    kinder: list[int] = []
    for gruppe in gruppen:
        teil_bytes = extrahiere_seiten_pdf(pdf_bytes, gruppe[0], gruppe[-1])
        kind_id, _sha = oder_intake_dokument_fuer_datei(teil_bytes, "pdf")
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET aufgeteilt_aus_id=? WHERE id=?",
                (intake_id, kind_id))
        erzeuge_zustellung(
            kind_id, quelle, absender=absender, betreff=betreff,
            empfangen_am=empfangen_am, signale=signale, konto=konto,
            roh_referenz=f"split:{intake_id}")
        kinder.append(kind_id)

    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente "
            "SET verworfen_grund='aufgeteilt', verworfen_am=?, verworfen_von=? "
            "WHERE id=?",
            (jetzt, benutzer_id, intake_id))
    return kinder
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_intake_split_service.py -v`
Expected: PASS (alle Klassen inkl. `TestTeileDokument`).

- [ ] **Step 5: Commit**

```bash
git add backend/intake/split_service.py backend/tests/test_intake_split_service.py
git commit -m "feat(intake): teile_dokument -- Teile anlegen + Original markieren"
```

---

### Task 4: Endpoints `/split`, `/seiten`, Seiten-`/thumbnail` + Guard

**Files:**
- Modify: `backend/routers/intake_routes.py` (Import `Response` bei Z.39; `_VERWERFEN_GRUENDE` bei Z.383; neue Routen ans Ende der Datei)
- Modify: `backend/tests/test_s19_intake_write_guard.py` (Z.21-27: `split_service.py` in `INTAKE_PFADE`)
- Test: `backend/tests/test_intake_split_routes.py`

**Interfaces:**
- Consumes: `split_service.teile_dokument`, `.pdf_seiten_zahl`, `.rendere_thumbnail`, `.SplitFehler`; Route-Helfer `_lade_intake`, `_err`, `_j`.
- Produces: `POST /intake/dokument/<id>/split` (Body `{"gruppen": [[...],[...]]}` → `{"ok": true, "teile": [id, id]}`); `GET /intake/dokument/<id>/seiten` → `{"seiten": N}`; `GET /intake/dokument/<id>/seite/<n>/thumbnail` → `image/png`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_intake_split_routes.py
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="split_routes_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import fitz


def _pdf(n):
    doc = fitz.open()
    for i in range(n):
        doc.new_page().insert_text((72, 72), f"S{i+1}")
    out = doc.tobytes()
    doc.close()
    return out


def _setup(test_id):
    db_path = os.path.join(_tmp, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp, f"up_{test_id}")
    os.environ["INTAKE_ARCHIV_ROOT"] = os.path.join(_tmp, f"arch_{test_id}")

    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    import backend.auth.middleware as mw_mod
    import backend.routers.intake_routes as ir_mod
    import backend.app as app_mod
    for m in (db_mod, sm, mw_mod, ir_mod, app_mod):
        importlib.reload(m)
    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _original(pdf_bytes, queue_status="bereit_zur_review", payload_typ="datei"):
    from backend.intake._persistenz import oder_intake_dokument_fuer_datei
    from backend.db.database import get_connection
    iid, _ = oder_intake_dokument_fuer_datei(pdf_bytes, "pdf")
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET queue_status=?, payload_typ=? WHERE id=?",
            (queue_status, payload_typ, iid))
    return iid


class TestSplitRoutes(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self.id().split(".")[-1])
        self.headers = _auth(self.client)

    def test_split_200_und_teile(self):
        oid = _original(_pdf(5))
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2, 3], [4, 5]]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(r.get_json()["teile"]), 2)

    def test_split_422_ungueltige_gruppen(self):
        oid = _original(_pdf(5))
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2, 3, 4, 5]]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 422)

    def test_split_422_text(self):
        oid = _original(_pdf(3), payload_typ="text")
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2], [3]]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 422)

    def test_split_409_doppelt(self):
        oid = _original(_pdf(4))
        self.client.post(f"/intake/dokument/{oid}/split",
                         json={"gruppen": [[1, 2], [3, 4]]}, headers=self.headers)
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2], [3, 4]]}, headers=self.headers)
        self.assertEqual(r.status_code, 409)

    def test_seiten_endpoint(self):
        oid = _original(_pdf(7))
        r = self.client.get(f"/intake/dokument/{oid}/seiten", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["seiten"], 7)

    def test_thumbnail_png(self):
        oid = _original(_pdf(3))
        r = self.client.get(f"/intake/dokument/{oid}/seite/1/thumbnail",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "image/png")

    def test_thumbnail_404_ausserhalb(self):
        oid = _original(_pdf(3))
        r = self.client.get(f"/intake/dokument/{oid}/seite/9/thumbnail",
                            headers=self.headers)
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_intake_split_routes.py -v`
Expected: FAIL (404, weil die Routen noch nicht existieren).

- [ ] **Step 3: Write minimal implementation**

In `backend/routers/intake_routes.py` den Flask-Import (Z.39) um `Response` erweitern:
```python
from flask import Blueprint, g, jsonify, request, send_file, Response
```

`split_service` importieren (bei den `..intake`-Importen, ~Z.45):
```python
from ..intake import split_service
```

`_VERWERFEN_GRUENDE` (Z.383) um `"aufgeteilt"` ergänzen:
```python
_VERWERFEN_GRUENDE = {"spam", "duplikat", "nicht_relevant",
                       "falsche_kanzlei", "sonstiges", "aufgeteilt"}
```

Neue Routen ans Ende der Datei anhängen:
```python
@intake_bp.route("/dokument/<int:intake_id>/split", methods=["POST"])
@login_erforderlich
def post_split(intake_id: int):
    """Teilt ein Sammel-PDF entlang Seitengrenzen in mehrere Intake-Dokumente.

    Payload: { "gruppen": [[1,2,3],[4,5]] }  (1-basierte, zusammenhaengende
    Seitenlisten, die 1..N lueckenlos abdecken).
    """
    payload = request.get_json(silent=True) or {}
    gruppen = payload.get("gruppen")
    if (not isinstance(gruppen, list) or not gruppen or not all(
            isinstance(g_, list) and g_ and all(isinstance(p, int) for p in g_)
            for g_ in gruppen)):
        return _err("Feld 'gruppen' muss eine Liste nicht-leerer Seitenlisten "
                    "(Ganzzahlen) sein.", 422)
    try:
        teile = split_service.teile_dokument(
            intake_id, gruppen, getattr(g, "benutzer_id", None))
    except split_service.SplitFehler as e:
        return _err(str(e), e.status)
    logger.info("Intake %s aufgeteilt in %s", intake_id, teile)
    return _j({"ok": True, "teile": teile})


@intake_bp.route("/dokument/<int:intake_id>/seiten", methods=["GET"])
@login_erforderlich
def hole_seitenzahl(intake_id: int):
    """Echte PDF-Seitenzahl (fuer den Aufteilen-Dialog, nicht die 30er-Kappung)."""
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    if dok.get("payload_typ") != "datei":
        return _err("Nur Datei-Dokumente haben Seiten", 422)
    pfad = dok.get("arbeitskopie_pfad")
    if not pfad or not os.path.isfile(pfad):
        return _err("Arbeitskopie fehlt", 404)
    with open(pfad, "rb") as f:
        return _j({"seiten": split_service.pdf_seiten_zahl(f.read())})


@intake_bp.route("/dokument/<int:intake_id>/seite/<int:seite_nr>/thumbnail",
                 methods=["GET"])
@login_erforderlich
def hole_thumbnail(intake_id: int, seite_nr: int):
    """PNG-Miniatur einer Seite fuer den Aufteilen-Dialog (Auth per ?token=)."""
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    pfad = dok.get("arbeitskopie_pfad")
    if not pfad or not os.path.isfile(pfad):
        return _err("Arbeitskopie fehlt", 404)
    with open(pfad, "rb") as f:
        pdf_bytes = f.read()
    if seite_nr < 1 or seite_nr > split_service.pdf_seiten_zahl(pdf_bytes):
        return _err("Seite ausserhalb des Bereichs", 404)
    return Response(split_service.rendere_thumbnail(pdf_bytes, seite_nr),
                    mimetype="image/png")
```

In `backend/tests/test_s19_intake_write_guard.py` den Tupel `INTAKE_PFADE` (Z.22-27) um den Split-Service ergänzen (Defense-in-depth — er ruft keine verbotenen Akten-Writer, der Guard fixiert das):
```python
INTAKE_PFADE = (
    os.path.join(BACKEND_ROOT, "email_import", "import_service.py"),
    os.path.join(BACKEND_ROOT, "email_import", "fragebogen_parser.py"),
    os.path.join(BACKEND_ROOT, "pdf", "upload_service.py"),
    os.path.join(BACKEND_ROOT, "routers", "dokumente_routes.py"),
    os.path.join(BACKEND_ROOT, "routers", "eakte_routes.py"),
    os.path.join(BACKEND_ROOT, "intake", "split_service.py"),
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_intake_split_routes.py backend/tests/test_s19_intake_write_guard.py -v`
Expected: PASS (alle Split-Routen-Tests + Guard bleibt grün).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_intake_split_routes.py backend/tests/test_s19_intake_write_guard.py
git commit -m "feat(intake): Endpoints /split, /seiten, /thumbnail + Guard-Abdeckung"
```

---

### Task 5: Frontend — reine Logik `splitLogik.js`

**Files:**
- Create: `frontend/src/views/splitLogik.js`
- Test: `frontend/src/views/splitLogik.test.js`

**Interfaces:**
- Produces:
  - `gruppenAusSchnitten(seitenGesamt: number, schnitte: number[]): number[][]` — `schnitte` = „Schnitt nach Seite p" (1..N-1) → zusammenhängende Gruppen.
  - `schnittUmschalten(schnitte: number[], pos: number): number[]` — toggelt einen Schnitt (sortiert).
  - `istAufteilbar(detail: object): boolean` — `payload_typ === "datei"`.

- [ ] **Step 1: Write the failing test**

```javascript
// frontend/src/views/splitLogik.test.js
import { describe, it, expect } from "vitest";
import { gruppenAusSchnitten, schnittUmschalten, istAufteilbar } from "./splitLogik.js";

describe("gruppenAusSchnitten", () => {
  it("ohne Schnitt: eine Gruppe mit allen Seiten", () => {
    expect(gruppenAusSchnitten(5, [])).toEqual([[1, 2, 3, 4, 5]]);
  });
  it("ein Schnitt nach Seite 3", () => {
    expect(gruppenAusSchnitten(5, [3])).toEqual([[1, 2, 3], [4, 5]]);
  });
  it("mehrere Schnitte, unsortiert und dedupliziert", () => {
    expect(gruppenAusSchnitten(6, [4, 2, 2])).toEqual([[1, 2], [3, 4], [5, 6]]);
  });
  it("ignoriert Schnitte ausserhalb 1..N-1", () => {
    expect(gruppenAusSchnitten(3, [0, 3, 9])).toEqual([[1, 2, 3]]);
  });
});

describe("schnittUmschalten", () => {
  it("fuegt einen Schnitt hinzu (sortiert)", () => {
    expect(schnittUmschalten([3], 1)).toEqual([1, 3]);
  });
  it("entfernt einen vorhandenen Schnitt", () => {
    expect(schnittUmschalten([1, 3], 3)).toEqual([1]);
  });
});

describe("istAufteilbar", () => {
  it("true fuer datei", () => {
    expect(istAufteilbar({ payload_typ: "datei" })).toBe(true);
  });
  it("false fuer text", () => {
    expect(istAufteilbar({ payload_typ: "text" })).toBe(false);
  });
  it("false fuer null/undefined", () => {
    expect(istAufteilbar(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/views/splitLogik.test.js`
Expected: FAIL (Modul `./splitLogik.js` nicht gefunden).

- [ ] **Step 3: Write minimal implementation**

```javascript
// frontend/src/views/splitLogik.js
// Reine Logik fuer den Aufteilen-Dialog: Schnitte <-> Seitengruppen.
// "schnitt nach Seite p" bedeutet: zwischen Seite p und p+1 (1 <= p <= N-1).

export function gruppenAusSchnitten(seitenGesamt, schnitte) {
  const cuts = [...new Set(schnitte)]
    .filter((p) => p >= 1 && p < seitenGesamt)
    .sort((a, b) => a - b);
  const gruppen = [];
  let start = 1;
  for (const c of cuts) {
    const g = [];
    for (let p = start; p <= c; p++) g.push(p);
    gruppen.push(g);
    start = c + 1;
  }
  const rest = [];
  for (let p = start; p <= seitenGesamt; p++) rest.push(p);
  gruppen.push(rest);
  return gruppen;
}

export function schnittUmschalten(schnitte, pos) {
  return schnitte.includes(pos)
    ? schnitte.filter((p) => p !== pos)
    : [...schnitte, pos].sort((a, b) => a - b);
}

export function istAufteilbar(detail) {
  return !!detail && detail.payload_typ === "datei";
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/views/splitLogik.test.js`
Expected: PASS (alle Beschreibungen).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/splitLogik.js frontend/src/views/splitLogik.test.js
git commit -m "feat(intake): Frontend splitLogik -- Schnitte/Gruppen (rein, getestet)"
```

---

### Task 6: Frontend — `SplitDialog` + API-Anbindung + Button in `ReviewQueueView`

**Files:**
- Create: `frontend/src/views/SplitDialog.jsx`
- Modify: `frontend/src/api.js` (`apiIntake`-Objekt, Z.1052-1074)
- Modify: `frontend/src/views/ReviewQueueView.jsx` (Import; `DetailPanel`-Kopf Z.930-944; State + Render)

**Interfaces:**
- Consumes: `apiIntake.seiten`, `apiIntake.split`, `gruppenAusSchnitten`, `schnittUmschalten` aus Task 5.
- Produces: `SplitDialog({ docId, thumbUrl, onDone, onClose })` — Default-Export.

- [ ] **Step 1: `apiIntake` erweitern**

In `frontend/src/api.js` im `apiIntake`-Objekt (nach `klassen:`) ergänzen:
```javascript
  seiten: (id)            => request(`/intake/dokument/${id}/seiten`),
  split:  (id, gruppen)   => request(`/intake/dokument/${id}/split`, {
    method: 'POST', body: JSON.stringify({ gruppen }),
  }),
```

- [ ] **Step 2: `SplitDialog.jsx` schreiben**

```jsx
// frontend/src/views/SplitDialog.jsx
import { useState, useEffect } from "react";
import { apiIntake } from "../api.js";
import { gruppenAusSchnitten, schnittUmschalten } from "./splitLogik.js";

export default function SplitDialog({ docId, thumbUrl, onDone, onClose }) {
  const [seiten, setSeiten] = useState(null);
  const [schnitte, setSchnitte] = useState([]);
  const [fehler, setFehler] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let aktiv = true;
    apiIntake.seiten(docId)
      .then((r) => { if (aktiv) setSeiten(r.seiten); })
      .catch(() => { if (aktiv) setFehler("Seiten konnten nicht geladen werden."); });
    return () => { aktiv = false; };
  }, [docId]);

  const gruppen = seiten ? gruppenAusSchnitten(seiten, schnitte) : [];

  const aufteilen = async () => {
    setBusy(true);
    setFehler(null);
    try {
      await apiIntake.split(docId, gruppen);
      onDone();
    } catch (e) {
      setFehler(e?.message || "Aufteilen fehlgeschlagen.");
      setBusy(false);
    }
  };

  const overlay = {
    position: "fixed", inset: 0, background: "rgba(0,0,0,.45)",
    display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
  };
  const box = {
    background: "#fff", borderRadius: 10, padding: 20, maxWidth: "90vw",
    maxHeight: "85vh", overflow: "auto", boxShadow: "0 10px 40px rgba(0,0,0,.3)",
  };

  return (
    <div style={overlay} onClick={onClose}>
      <div style={box} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>✂ Dokument aufteilen</h3>
        {seiten === null && !fehler && <p>Lade Seiten …</p>}
        {seiten !== null && (
          <>
            <p style={{ fontSize: 13, opacity: 0.7 }}>
              Klick zwischen zwei Seiten setzt/entfernt einen Schnitt.
            </p>
            <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 2 }}>
              {Array.from({ length: seiten }, (_, i) => i + 1).map((n) => (
                <div key={n} style={{ display: "flex", alignItems: "center" }}>
                  <div style={{ textAlign: "center" }}>
                    <img src={thumbUrl(n)} alt={`Seite ${n}`}
                      style={{ width: 70, height: 92, objectFit: "contain",
                        border: "1px solid #ccc", borderRadius: 4, background: "#fafafa" }} />
                    <div style={{ fontSize: 11, opacity: 0.7 }}>{n}</div>
                  </div>
                  {n < seiten && (
                    <button
                      onClick={() => setSchnitte((s) => schnittUmschalten(s, n))}
                      title={schnitte.includes(n) ? "Schnitt entfernen" : "Hier schneiden"}
                      style={{
                        width: 26, alignSelf: "stretch", cursor: "pointer",
                        border: "none", background: "transparent",
                        color: schnitte.includes(n) ? "#e0663a" : "#bbb",
                        fontSize: 16,
                      }}>✂</button>
                  )}
                </div>
              ))}
            </div>

            <p style={{ fontSize: 13, fontWeight: 600, marginTop: 16 }}>
              Ergebnis — {gruppen.length} Teil{gruppen.length === 1 ? "" : "e"}
            </p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {gruppen.map((g, i) => (
                <span key={i} style={{
                  border: "1px solid #3b82f6", borderRadius: 8, padding: "6px 10px",
                  fontSize: 12,
                }}>
                  Teil {i + 1} · Seiten {g[0]}{g.length > 1 ? `–${g[g.length - 1]}` : ""}
                </span>
              ))}
            </div>

            {fehler && <p style={{ color: "#c0392b", fontSize: 13 }}>{fehler}</p>}

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 18 }}>
              <button onClick={onClose} disabled={busy}>Abbrechen</button>
              <button onClick={aufteilen} disabled={busy || schnitte.length < 1}
                style={{ background: "#2563eb", color: "#fff", border: "none",
                  borderRadius: 6, padding: "6px 14px", cursor: "pointer" }}>
                In {gruppen.length} Teile aufteilen
              </button>
            </div>
          </>
        )}
        {fehler && seiten === null && <p style={{ color: "#c0392b" }}>{fehler}</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Button + Dialog in `ReviewQueueView.jsx` einbinden**

Import oben in `ReviewQueueView.jsx` ergänzen:
```javascript
import SplitDialog from "./SplitDialog.jsx";
```

In `DetailPanel` neben dem State der Komponente ergänzen:
```javascript
  const [splitOffen, setSplitOffen] = useState(false);
  const thumbUrl = (n) => {
    const token = tokenStore.getAccess();
    return `${API_BASE}/intake/dokument/${id}/seite/${n}/thumbnail?token=${encodeURIComponent(token)}`;
  };
```

Im Kopf-`<div>` mit den Buttons (direkt vor dem `🖨 Drucken`-Button, Z.930-943) den Aufteilen-Button einfügen:
```jsx
              <button onClick={() => setSplitOffen(true)}
                disabled={detail.payload_typ !== "datei"}
                title={detail.payload_typ !== "datei"
                  ? "Nur PDF-Dokumente koennen aufgeteilt werden"
                  : "Dokument aufteilen"}
                style={{
                  padding: "4px 10px", fontSize: T.textXs, fontWeight: 600,
                  background: T.offWhite, color: T.navy,
                  border: `1px solid ${T.border}`, borderRadius: 4,
                  cursor: detail.payload_typ !== "datei" ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap",
                  opacity: detail.payload_typ !== "datei" ? 0.5 : 1,
                }}>
                ✂ Aufteilen
              </button>
```

Am Ende des `DetailPanel`-Returns (vor dem schließenden Fragment/Wrapper) den Dialog rendern. `onDrop` ist der bestehende Queue-Reload-Callback, den auch der Verwerfen-Flow nach Erfolg aufruft (im `DetailPanel`-Props als `onAktion`/Reload vorhanden — denselben verwenden):
```jsx
      {splitOffen && (
        <SplitDialog
          docId={id}
          thumbUrl={thumbUrl}
          onClose={() => setSplitOffen(false)}
          onDone={() => { setSplitOffen(false); onAktion?.(); }}
        />
      )}
```

> Hinweis für den Umsetzer: `onAktion` ist der Platzhalter für den bereits existierenden Reload-/Deselect-Callback, den `DetailPanel` nach `verwerfen` aufruft (die Queue neu laden, Auswahl zurücksetzen). Verwende exakt denselben Callback-Namen, den `DetailPanel` schon für den Verwerfen-Erfolg nutzt (in `ReviewQueueView.jsx` prüfen und übernehmen — nicht neu erfinden).

- [ ] **Step 4: Verifizieren**

Run: `cd frontend && npx vitest run` (gesamte Suite — bestehende Tests bleiben grün; keine neue Render-Testpflicht, die Logik ist in Task 5 abgedeckt).
Zusätzlich manuell (nach `npm run dev` bzw. Docker-DEV): Dokument mit ≥2 Seiten öffnen → „✂ Aufteilen" → Miniaturen erscheinen → Schnitt setzen → „In 2 Teile aufteilen" → Original verschwindet, zwei Teile erscheinen nach Worker-Lauf in der Queue.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api.js frontend/src/views/SplitDialog.jsx frontend/src/views/ReviewQueueView.jsx
git commit -m "feat(intake): Aufteilen-Dialog + Button im Review-UI"
```

---

## Self-Review

**Spec coverage:**
- UX (Button, Dialog, Scheren, Teile-Vorschau, echte Seitenzahl, ausgegraut bei Nicht-Datei) → Task 6 + Task 4 (`/seiten`, `/thumbnail`).
- Ansatz A (Teile = neue Dokumente, Auto-Klassifikation via `queue_status='neu'`) → Task 3.
- `split_service` + Vorbedingungen/Validierung/Transaktion → Task 2 + 3.
- Endpoints `/split`, `/thumbnail` (+ `/seiten` für echte Seitenzahl) → Task 4.
- Migration 58 (`aufgeteilt_aus_id` + Verwerfen-Grund `aufgeteilt`) → Task 1 + Task 4.
- Zustellungs-Vererbung → Task 3.
- Fehlerfälle 422/409/Dedup → Task 3 + 4.
- Invarianten (nur Intake-Tabellen, Guard) → Task 4 (Guard-Whitelist).
- Tests (Service, Migration, Routen, Thumbnail, Frontend rein) → Task 1,2,3,4,5.

**Abweichungen von der Spec (bewusst, oben dokumentiert):** (1) Audit-Link via `aufgeteilt_aus_id` + `roh_referenz` statt `korrektur_log` (Entkopplung). (2) „Alles-oder-nichts" → „Original zuletzt markieren, Teile sha-idempotent" (die Persistenz-Helfer committen je Aufruf; das gewählte Vorgehen verhindert jeden Halbstatus mit Datenverlust, was das eigentliche Ziel ist).

**Placeholder-Scan:** Der einzige nicht-verbatim Punkt ist der Reload-Callback-Name in Task 6 Step 3 (`onAktion?.()`) — bewusst als „an bestehenden Verwerfen-Reload angleichen" markiert, mit Prüf-Anweisung, weil der exakte Name erst beim Umsetzen aus `ReviewQueueView.jsx` zu übernehmen ist.

**Typ-Konsistenz:** `gruppen: list[list[int]]` einheitlich (Route ↔ `teile_dokument` ↔ `validiere_gruppen`); `teile`-Rückgabe = `list[int]` (Route-JSON `{"teile": [...]}`); Frontend `gruppenAusSchnitten` liefert `number[][]`, `apiIntake.split(id, gruppen)` sendet `{gruppen}`.
