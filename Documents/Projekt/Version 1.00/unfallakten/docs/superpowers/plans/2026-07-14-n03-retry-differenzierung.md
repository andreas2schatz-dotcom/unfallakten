# N-03 Retry-Differenzierung + Degradations-Hinweis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LLM/GLM-bedingte Fehler im Intake-Retry-Pfad differenziert behandeln (Timeout→Backoff, Ressourcendruck→zurückstellen, reproduzierbar→kein Retry) und dem Reviewer sichtbar machen, wenn die KI-Extraktion ausgefallen ist („nur Regex").

**Architecture:** Zwei unabhängige Einheiten. (1) Eine reine Klassifikations­funktion in `queue.py`, die `markiere_fehler` je Kategorie anders verzweigen lässt — kein neuer `queue_status`, keine Migration. (2) Ein Degradations-Signal, das `extrahiere_felder` als `llm_status` liefert, die Pipeline in `parse_json.degradation` + neue Spalte `llm_degradiert` (Migration 57) stempelt, und das Frontend als Queue-Badge + Detail-Hinweis zeigt.

**Tech Stack:** Python 3 / SQLite (WAL) / Flask-Blueprint · React (Vite) · pytest (unittest.TestCase) · Vitest + @testing-library/react.

## Global Constraints

- Branch: `intake-stufe1` (nicht `main`).
- RA-MICRO strikt **read-only** — nur SQLite schreiben.
- Keine unnötigen Abstraktionen; keine Kommentare außer bei nicht-offensichtlichem Verhalten.
- Migrationen: **kein `executescript()`**, ALTER TABLE mit explizitem `conn.commit()` davor+danach, idempotent per `PRAGMA table_info`. Vor Migration 57 **Sicherungskopie** der aktiven Volume-DB (`/app/data`).
- Der „schluck-und-gib-`None`"-Vertrag der LLM/GLM-Services bleibt **unangetastet** (load-bearing Regex/Tesseract-Fallback).
- Alt-Pfade / `INTAKE_REVIEW_PFLICHT` unberührt. Golden-File-Tests (`test_registry_golden.py`, `test_s16a_golden_e2e.py`, `test_s18_review_e2e.py`) bleiben grün.
- Deutsche Zielsprache in allen Nutzertexten.

---

## File Structure

- `backend/intake/queue.py` — **modify**: `klassifiziere_fehler()` + Verzweigung in `markiere_fehler()`.
- `backend/services/llm_service.py` — **modify**: öffentliches `ist_aktiviert()`.
- `backend/intake/extraktion.py` — **modify**: `extrahiere_felder()` liefert zusätzlich `llm_status`.
- `backend/db/schema_manager.py` — **modify**: Migration 57 (`intake_dokumente.llm_degradiert`).
- `backend/intake/pipeline.py` — **modify**: `llm_degradiert` + `parse_json.degradation` stempeln.
- `backend/routers/intake_routes.py` — **modify**: `hole_queue` + `hole_detail` liefern die neuen Felder.
- `frontend/src/views/ReviewQueueView.jsx` — **modify**: Queue-Badge + Detail-Hinweis.
- Tests: `backend/tests/test_intake_queue.py`, `test_intake_extraktion.py`, `test_n03_degradation.py` (neu), `test_intake_routes.py`, `frontend/src/views/ReviewQueueView.degradation.test.jsx` (neu), plus ein `llm_service`-Test.

---

### Task 1: `klassifiziere_fehler` — reine Klassifikationsfunktion

**Files:**
- Modify: `backend/intake/queue.py` (nach `_iso`, vor `enqueue`)
- Test: `backend/tests/test_intake_queue.py`

**Interfaces:**
- Produces: `klassifiziere_fehler(meldung: str) -> str` — liefert genau eines von `"timeout"`, `"ressourcendruck"`, `"reproduzierbar"`, `"unbekannt"`.

- [ ] **Step 1: Failing test schreiben** — ans Ende von `test_intake_queue.py` anfügen:

```python
class TestFehlerKlassifikation(unittest.TestCase):
    def test_timeout(self):
        from backend.intake.queue import klassifiziere_fehler
        self.assertEqual(klassifiziere_fehler("LLM Timeout nach 60s"), "timeout")
        self.assertEqual(klassifiziere_fehler("Read timed out."), "timeout")

    def test_ressourcendruck(self):
        from backend.intake.queue import klassifiziere_fehler
        for m in ("Connection refused", "Verbindungsfehler zum Server",
                  "HTTP 503 Service Unavailable", "connection reset by peer",
                  "too many requests"):
            self.assertEqual(klassifiziere_fehler(m), "ressourcendruck", m)

    def test_reproduzierbar(self):
        from backend.intake.queue import klassifiziere_fehler
        for m in ("Keine Seiten extrahierbar", "Text-Payload ohne Inhalt",
                  "cannot open broken document", "Arbeitskopie fehlt: /x.pdf",
                  "not a PDF"):
            self.assertEqual(klassifiziere_fehler(m), "reproduzierbar", m)

    def test_default_unbekannt(self):
        from backend.intake.queue import klassifiziere_fehler
        self.assertEqual(klassifiziere_fehler("irgendein anderer fehler"), "unbekannt")
        self.assertEqual(klassifiziere_fehler(""), "unbekannt")
        self.assertEqual(klassifiziere_fehler(None), "unbekannt")

    def test_timeout_hat_vorrang_vor_connection(self):
        from backend.intake.queue import klassifiziere_fehler
        self.assertEqual(
            klassifiziere_fehler("connection timed out"), "timeout")
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `python -m pytest backend/tests/test_intake_queue.py::TestFehlerKlassifikation -v`
Expected: FAIL (`ImportError: cannot import name 'klassifiziere_fehler'`)

- [ ] **Step 3: Implementieren** — in `backend/intake/queue.py` nach `_iso(...)` einfügen:

```python
RUECKSTELL_S = 900  # 15 min: Ressourcendruck-Rueckstellung (N-03)

_MUSTER_TIMEOUT = ("timeout", "timed out", "zeitueberschreitung",
                   "zeitüberschreitung")
_MUSTER_RESSOURCE = ("connection", "verbindung", "refused", "reset by peer",
                     "broken pipe", " 503", " 502", "overload", "ueberlast",
                     "überlast", "unavailable", "too many requests",
                     "temporarily")
_MUSTER_REPRODUZIERBAR = ("keine seiten extrahierbar", "ohne inhalt",
                          "cannot open", "damaged", "not a pdf", "no /root",
                          "invalid", "unsupported", "arbeitskopie fehlt")


def klassifiziere_fehler(meldung: str) -> str:
    """Ordnet eine Fehlermeldung einer Retry-Kategorie zu (N-03).

    Timeout hat Vorrang vor Ressourcendruck (ein Read-Timeout ist mit Backoff
    behebbar). Default 'unbekannt' -> wird wie 'timeout' retriet (sicher).
    """
    m = (meldung or "").lower()
    if any(s in m for s in _MUSTER_TIMEOUT):
        return "timeout"
    if any(s in m for s in _MUSTER_RESSOURCE):
        return "ressourcendruck"
    if any(s in m for s in _MUSTER_REPRODUZIERBAR):
        return "reproduzierbar"
    return "unbekannt"
```

- [ ] **Step 4: Test laufen lassen, grün prüfen**

Run: `python -m pytest backend/tests/test_intake_queue.py::TestFehlerKlassifikation -v`
Expected: PASS (5 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/intake/queue.py backend/tests/test_intake_queue.py
git commit -m "feat(intake): N-03 klassifiziere_fehler (Retry-Kategorien)"
```

---

### Task 2: `markiere_fehler` verzweigt je Kategorie

**Files:**
- Modify: `backend/intake/queue.py` (`markiere_fehler`, aktuell ca. Zeile 127-171)
- Test: `backend/tests/test_intake_queue.py`

**Interfaces:**
- Consumes: `klassifiziere_fehler` (Task 1), `RUECKSTELL_S` (Task 1), `MAX_VERSUCHE`, `BACKOFF_S`, `_iso` (bestehend).
- Produces: `markiere_fehler(intake_dokument_id: int, fehler_meldung: str) -> None` mit unverändertem Signaturvertrag, aber kategorieabhängigem Verhalten.

- [ ] **Step 1: Failing tests schreiben** — ans Ende von `test_intake_queue.py` anfügen:

```python
class TestMarkiereFehlerKategorien(_BaseQueueTest):
    def _status(self, did):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return dict(conn.execute(
                "SELECT queue_status, versuch_zaehler, naechster_versuch, "
                "fehler_detail FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone())

    def test_ressourcendruck_stellt_zurueck_ohne_zaehler(self):
        from backend.intake.queue import markiere_fehler
        did = self._lege_dokument_an()
        markiere_fehler(did, "Connection refused")
        r = self._status(did)
        self.assertEqual(r["queue_status"], "neu")
        self.assertEqual(r["versuch_zaehler"], 0)          # NICHT erhoeht
        self.assertIsNotNone(r["naechster_versuch"])       # verschoben
        self.assertEqual(r["fehler_detail"], "Connection refused")

    def test_ressourcendruck_vergiftet_nie(self):
        from backend.intake.queue import markiere_fehler
        did = self._lege_dokument_an()
        for _ in range(5):
            markiere_fehler(did, "HTTP 503 Service Unavailable")
        r = self._status(did)
        self.assertEqual(r["queue_status"], "neu")         # nie pipeline_fehler
        self.assertEqual(r["versuch_zaehler"], 0)

    def test_reproduzierbar_kein_retry(self):
        from backend.intake.queue import markiere_fehler
        did = self._lege_dokument_an()
        markiere_fehler(did, "Keine Seiten extrahierbar")
        r = self._status(did)
        self.assertEqual(r["queue_status"], "pipeline_fehler")  # sofort
        self.assertEqual(r["versuch_zaehler"], 0)               # kein Backoff
        self.assertEqual(r["fehler_detail"], "Keine Seiten extrahierbar")

    def test_timeout_backoff_wie_bisher(self):
        from backend.intake.queue import markiere_fehler
        did = self._lege_dokument_an()
        markiere_fehler(did, "LLM Timeout nach 60s")
        r = self._status(did)
        self.assertEqual(r["queue_status"], "neu")
        self.assertEqual(r["versuch_zaehler"], 1)          # erhoeht
        self.assertIsNotNone(r["naechster_versuch"])

    def test_unbekannt_poison_pill_nach_max(self):
        from backend.intake.queue import markiere_fehler
        did = self._lege_dokument_an()
        for _ in range(3):
            markiere_fehler(did, "voellig anderer fehler")
        r = self._status(did)
        self.assertEqual(r["queue_status"], "pipeline_fehler")
        self.assertEqual(r["versuch_zaehler"], 3)
```

- [ ] **Step 2: Test laufen lassen, Fehlschlag prüfen**

Run: `python -m pytest backend/tests/test_intake_queue.py::TestMarkiereFehlerKategorien -v`
Expected: FAIL (`test_ressourcendruck_*` + `test_reproduzierbar_*`, weil aktuell alles Backoff macht)

- [ ] **Step 3: `markiere_fehler` ersetzen** — die bestehende Funktion in `backend/intake/queue.py` vollständig durch diese Fassung ersetzen:

```python
def markiere_fehler(intake_dokument_id: int, fehler_meldung: str) -> None:
    """Fehler-Abschluss mit kategorieabhaengigem Verhalten (N-03).

    * ressourcendruck -> zurueckstellen: bleibt 'neu', naechster_versuch=+15min,
      versuch_zaehler UNVERAENDERT (transienter Backend-Ausfall vergiftet nicht).
    * reproduzierbar  -> KEIN Retry: sofort 'pipeline_fehler'.
    * timeout/unbekannt -> Backoff 1/5/30, nach MAX_VERSUCHE 'pipeline_fehler'.
    """
    kategorie = klassifiziere_fehler(fehler_meldung)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT versuch_zaehler FROM intake_dokumente WHERE id=?",
            (intake_dokument_id,),
        ).fetchone()
        if not row:
            logger.error("markiere_fehler: ID %s nicht gefunden", intake_dokument_id)
            return
        zaehler = int(row["versuch_zaehler"] or 0)

        if kategorie == "ressourcendruck":
            naechster = _iso(datetime.now() + timedelta(seconds=RUECKSTELL_S))
            conn.execute(
                "UPDATE intake_dokumente SET queue_status='neu', "
                "worker_lease=NULL, fehler_detail=?, naechster_versuch=? "
                "WHERE id=?",
                (fehler_meldung, naechster, intake_dokument_id),
            )
            logger.warning(
                "Dokument %s: Ressourcendruck -> zurueckgestellt +%ds "
                "(Zaehler unveraendert %d): %s",
                intake_dokument_id, RUECKSTELL_S, zaehler, fehler_meldung,
            )
            return

        if kategorie == "reproduzierbar":
            conn.execute(
                "UPDATE intake_dokumente SET queue_status='pipeline_fehler', "
                "worker_lease=NULL, fehler_detail=? WHERE id=?",
                (fehler_meldung, intake_dokument_id),
            )
            logger.warning(
                "Dokument %s: reproduzierbarer Fehler -> pipeline_fehler "
                "(kein Retry): %s",
                intake_dokument_id, fehler_meldung,
            )
            return

        neuer_zaehler = zaehler + 1
        if neuer_zaehler >= MAX_VERSUCHE:
            conn.execute(
                "UPDATE intake_dokumente SET "
                "queue_status='pipeline_fehler', versuch_zaehler=?, "
                "worker_lease=NULL, fehler_detail=? "
                "WHERE id=?",
                (neuer_zaehler, fehler_meldung, intake_dokument_id),
            )
            logger.warning(
                "Dokument %s: pipeline_fehler nach %d Versuchen (%s)",
                intake_dokument_id, neuer_zaehler, fehler_meldung,
            )
        else:
            backoff_s = BACKOFF_S[min(neuer_zaehler - 1, len(BACKOFF_S) - 1)]
            naechster = _iso(datetime.now() + timedelta(seconds=backoff_s))
            conn.execute(
                "UPDATE intake_dokumente SET "
                "queue_status='neu', versuch_zaehler=?, worker_lease=NULL, "
                "fehler_detail=?, naechster_versuch=? "
                "WHERE id=?",
                (neuer_zaehler, fehler_meldung, naechster, intake_dokument_id),
            )
            logger.info(
                "Dokument %s: Fehler %d/%d, retry in %ds (%s)",
                intake_dokument_id, neuer_zaehler, MAX_VERSUCHE,
                backoff_s, fehler_meldung,
            )
```

- [ ] **Step 4: Tests laufen lassen, grün prüfen** (neue + bestehende Backoff-Tests)

Run: `python -m pytest backend/tests/test_intake_queue.py -v`
Expected: PASS (alle, inkl. bestehende `TestMarkiereFehler*`/Backoff-Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/intake/queue.py backend/tests/test_intake_queue.py
git commit -m "feat(intake): N-03 markiere_fehler verzweigt je Fehlerkategorie"
```

---

### Task 3: `llm_service.ist_aktiviert()`

**Files:**
- Modify: `backend/services/llm_service.py` (nahe `get_active_model`, ca. Zeile 57)
- Test: `backend/tests/test_intake_extraktion.py` (kleiner Zusatztest genügt)

**Interfaces:**
- Produces: `llm_service.ist_aktiviert() -> bool` — spiegelt das `LLM_ENABLED`-Flag (`_ENABLED`).

- [ ] **Step 1: Failing test** — ans Ende von `test_intake_extraktion.py` anfügen:

```python
def test_ist_aktiviert_spiegelt_enabled_flag():
    from backend.services import llm_service
    assert llm_service.ist_aktiviert() is llm_service._ENABLED
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest backend/tests/test_intake_extraktion.py::test_ist_aktiviert_spiegelt_enabled_flag -v`
Expected: FAIL (`AttributeError: module ... has no attribute 'ist_aktiviert'`)

- [ ] **Step 3: Implementieren** — in `backend/services/llm_service.py` nach `get_active_model` einfügen:

```python
def ist_aktiviert() -> bool:
    """True, wenn LLM_ENABLED gesetzt ist (N-03 Degradations-Erkennung)."""
    return _ENABLED
```

- [ ] **Step 4: Grün prüfen**

Run: `python -m pytest backend/tests/test_intake_extraktion.py::test_ist_aktiviert_spiegelt_enabled_flag -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/llm_service.py backend/tests/test_intake_extraktion.py
git commit -m "feat(llm): oeffentliches ist_aktiviert() fuer Degradations-Check"
```

---

### Task 4: `extrahiere_felder` liefert `llm_status`

**Files:**
- Modify: `backend/intake/extraktion.py` (`extrahiere_felder`, ca. Zeile 45-97)
- Test: `backend/tests/test_intake_extraktion.py`

**Interfaces:**
- Consumes: `llm_service.ist_aktiviert` (Task 3).
- Produces: `extrahiere_felder(...)` gibt im Ergebnis-Dict zusätzlich `"llm_status"` ∈ `{"ok","aus","ausgefallen"}` zurück. `"felder"`/`"llm_konflikt"` unverändert. `"aus"` = kein Schema **oder** LLM deaktiviert (keine Störung); `"ausgefallen"` = aktiviert, aber Rückgabe leer/None; `"ok"` = aktiviert + Werte da.

- [ ] **Step 1: Failing tests** — in `test_intake_extraktion.py` neue Testklasse anfügen (nutzt `_registry()`-Helper der Datei — falls die Datei einen anderen Registry-Aufbau nutzt, denselben Aufbau wie `test_llm_ist_primaer_quelle_wenn_erfolgreich` übernehmen):

```python
class TestLlmStatus(unittest.TestCase):
    def _registry(self):
        # gleicher Aufbau wie in test_llm_ist_primaer_quelle_wenn_erfolgreich
        class _R:
            klassen = {"abrechnung": {"schema": {"betrag": "geld"},
                                      "regex_felder": {}}}
        return _R()

    def test_status_ok_wenn_aktiv_und_werte(self):
        from unittest import mock
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value={"betrag": "100"}):
            erg = extraktion.extrahiere_felder("txt", "abrechnung", self._registry())
        self.assertEqual(erg["llm_status"], "ok")

    def test_status_ausgefallen_wenn_aktiv_aber_none(self):
        from unittest import mock
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value=None):
            erg = extraktion.extrahiere_felder("txt", "abrechnung", self._registry())
        self.assertEqual(erg["llm_status"], "ausgefallen")

    def test_status_aus_wenn_deaktiviert(self):
        from unittest import mock
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=False), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value=None):
            erg = extraktion.extrahiere_felder("txt", "abrechnung", self._registry())
        self.assertEqual(erg["llm_status"], "aus")

    def test_status_aus_bei_unbekannter_klasse(self):
        from backend.intake import extraktion
        class _R:
            klassen = {}
        erg = extraktion.extrahiere_felder("txt", "gibtsnicht", _R())
        self.assertEqual(erg.get("llm_status"), "aus")
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest backend/tests/test_intake_extraktion.py::TestLlmStatus -v`
Expected: FAIL (`KeyError: 'llm_status'`)

- [ ] **Step 3: Implementieren** — in `backend/intake/extraktion.py`:

Frühen Rückgabepfad für unbekannte Klasse (aktuell `return {"felder": {}}`) ersetzen durch:

```python
    if not eintrag:
        return {"felder": {}, "llm_status": "aus"}
```

Danach den LLM-Block (die Zeilen von `llm_werte = llm_service.extrahiere_nach_schema(...)` bis vor den `felder`-Aufbau) so anpassen, dass `llm_status` bestimmt wird:

```python
    schema = eintrag.get("schema") or {}
    llm_aktiv = llm_service.ist_aktiviert()
    llm_roh = llm_service.extrahiere_nach_schema(
        schema, llm_text if llm_text is not None else text)
    llm_werte = llm_roh if isinstance(llm_roh, dict) else {}

    if not schema or not llm_aktiv:
        llm_status = "aus"
    elif not llm_werte:
        llm_status = "ausgefallen"
    else:
        llm_status = "ok"
```

Am Ende `llm_status` ins Ergebnis aufnehmen — das bestehende `ergebnis: Dict[str, Any] = {"felder": felder}` erweitern:

```python
    ergebnis: Dict[str, Any] = {"felder": felder, "llm_status": llm_status}
```

(Der `llm_konflikt`-Block bleibt unverändert. Der unconditional Aufruf von `extrahiere_nach_schema` bleibt erhalten — kein Verhaltenswechsel für bestehende Tests, die ohne `LLM_ENABLED` mocken.)

- [ ] **Step 4: Grün prüfen** (neue + alle bestehenden Extraktions-Tests)

Run: `python -m pytest backend/tests/test_intake_extraktion.py -v`
Expected: PASS (alle)

- [ ] **Step 5: Commit**

```bash
git add backend/intake/extraktion.py backend/tests/test_intake_extraktion.py
git commit -m "feat(intake): N-03 extrahiere_felder liefert llm_status"
```

---

### Task 5: Migration 57 — `intake_dokumente.llm_degradiert`

**Files:**
- Modify: `backend/db/schema_manager.py` (MIGRATIONS-Dict ~Zeile 310, neuer Handler nahe `_run_migration_56` ~Zeile 855, Dispatch ~Zeile 1303)
- Test: `backend/tests/test_n03_degradation.py` (neu)

**Interfaces:**
- Produces: Spalte `intake_dokumente.llm_degradiert INTEGER` (nullable). Migrationsnummer **57**.

- [ ] **Step 1: Failing test** — neue Datei `backend/tests/test_n03_degradation.py`:

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _BaseDbTest(unittest.TestCase):
    def setUp(self):
        fd, self._db = tempfile.mkstemp(prefix="n03_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt = _db.DB_PATH
        _db.DB_PATH = self._db
        os.environ["DB_PATH"] = self._db
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db)
        except OSError:
            pass


class TestMigration57(_BaseDbTest):
    def test_spalte_existiert_und_nullable(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r[1]: r for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
        self.assertIn("llm_degradiert", spalten)
        self.assertEqual(spalten["llm_degradiert"][3], 0)  # notnull=0

    def test_idempotent(self):
        from backend.db.schema_manager import _run_migration_57
        from backend.db.database import get_connection
        with get_connection() as conn:
            _run_migration_57(conn)  # zweiter Lauf darf nicht werfen
            self.assertIn("llm_degradiert", {r[1] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()})
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest backend/tests/test_n03_degradation.py::TestMigration57 -v`
Expected: FAIL (`AttributeError: ... _run_migration_57` bzw. Spalte fehlt)

- [ ] **Step 3a: MIGRATIONS-Dict erweitern** — in `backend/db/schema_manager.py` nach der `56:`-Zeile (~Zeile 310):

```python
    57: "-- migration_57_intake_llm_degradiert",  # Handled by _run_migration_57 (N-03 Degradations-Signal)
```

- [ ] **Step 3b: Handler ergänzen** — direkt nach `_run_migration_56(...)` (~Zeile 897) einfügen:

```python
def _run_migration_57(conn: sqlite3.Connection) -> None:
    """
    Migration 57 (N-03) - intake_dokumente.llm_degradiert.

    Flag (0/1/NULL): 1 = KI-Feldextraktion war eingeschaltet, lieferte aber
    nichts (weggeschluckter LLM-Fehler) -> Review-Queue zeigt "nur Regex".
    Additives ALTER TABLE, nullable INTEGER, kein Datenverlust. Idempotent per
    PRAGMA table_info. Explizites conn.commit() (feedback_migration_executescript).
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(intake_dokumente)"
        ).fetchall()
    }
    if "llm_degradiert" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE intake_dokumente ADD COLUMN llm_degradiert INTEGER"
        )
        conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (57, "Migration 57 - intake_dokumente.llm_degradiert "
             "(N-03 Degradations-Signal)"),
    )
    logger.info("Migration 57 abgeschlossen (intake_dokumente.llm_degradiert).")
```

- [ ] **Step 3c: Dispatch ergänzen** — im `for version in sorted(pending)`-Block nach dem `version == 56`-Zweig (~Zeile 1303):

```python
            elif version == 57:
                _run_migration_57(conn)
```

- [ ] **Step 4: Grün prüfen**

Run: `python -m pytest backend/tests/test_n03_degradation.py::TestMigration57 -v`
Expected: PASS (2 Tests)

- [ ] **Step 5: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_n03_degradation.py
git commit -m "feat(db): Migration 57 intake_dokumente.llm_degradiert (N-03)"
```

---

### Task 6: Pipeline stempelt `llm_degradiert` + `parse_json.degradation`

**Files:**
- Modify: `backend/intake/pipeline.py` (`verarbeite_dokument`, `parse_dict`-Aufbau ~Zeile 246-291)
- Test: `backend/tests/test_n03_degradation.py`

**Interfaces:**
- Consumes: `extraktion["llm_status"]` (Task 4), Spalte `llm_degradiert` (Task 5).
- Produces: bei `llm_status == "ausgefallen"` → `intake_dokumente.llm_degradiert = 1` und `parse_json["degradation"] = {"llm_extraktion": "ausgefallen"}`; sonst `llm_degradiert = 0`, kein `degradation`-Key.

- [ ] **Step 1: Failing test** — an `test_n03_degradation.py` anfügen. Der Test legt ein Text-Payload-Dokument an (einfachster Pfad, kein PDF/OCR nötig) und mockt die Extraktion:

```python
class TestPipelineDegradation(_BaseDbTest):
    def _text_dok(self, text="Sehr geehrte Damen und Herren, Rechnung anbei."):
        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status) "
                "VALUES (?, 'text', ?, 'neu')",
                ("s" + "0" * 63, text),
            )
            return cur.lastrowid

    def _row(self, did):
        from backend.db.database import get_connection
        import json
        with get_connection() as conn:
            r = dict(conn.execute(
                "SELECT llm_degradiert, parse_json FROM intake_dokumente "
                "WHERE id=?", (did,)).fetchone())
        r["parse"] = json.loads(r["parse_json"]) if r["parse_json"] else {}
        return r

    def test_ausgefallen_setzt_flag_und_marker(self):
        from unittest import mock
        from backend.intake import pipeline
        did = self._text_dok()
        with mock.patch("backend.intake.pipeline.extrahiere_felder",
                        return_value={"felder": {}, "llm_status": "ausgefallen"}):
            pipeline.verarbeite_dokument(did)
        r = self._row(did)
        self.assertEqual(r["llm_degradiert"], 1)
        self.assertEqual(r["parse"].get("degradation"),
                         {"llm_extraktion": "ausgefallen"})

    def test_aus_setzt_kein_marker(self):
        from unittest import mock
        from backend.intake import pipeline
        did = self._text_dok()
        with mock.patch("backend.intake.pipeline.extrahiere_felder",
                        return_value={"felder": {}, "llm_status": "aus"}):
            pipeline.verarbeite_dokument(did)
        r = self._row(did)
        self.assertEqual(r["llm_degradiert"], 0)
        self.assertIsNone(r["parse"].get("degradation"))
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest backend/tests/test_n03_degradation.py::TestPipelineDegradation -v`
Expected: FAIL (`llm_degradiert` ist NULL, kein `degradation`-Key)

- [ ] **Step 3a: Degradation aus `llm_status` ableiten** — in `pipeline.verarbeite_dokument`, direkt nach `llm_konflikt = extraktion.get("llm_konflikt")` (~Zeile 232):

```python
        llm_status = extraktion.get("llm_status")
        llm_degradiert = 1 if llm_status == "ausgefallen" else 0
```

- [ ] **Step 3b: Marker in `parse_dict`** — nach dem `if llm_konflikt:`-Block (vor `parse_json = json.dumps(...)`, ~Zeile 274):

```python
        if llm_degradiert:
            parse_dict["degradation"] = {"llm_extraktion": "ausgefallen"}
```

- [ ] **Step 3c: Spalte im UPDATE mitschreiben** — das bestehende `UPDATE intake_dokumente SET ...` (~Zeile 282-290) um `llm_degradiert` erweitern:

```python
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET "
                "klasse=?, klasse_quelle=?, konfidenz=?, "
                "textquelle=?, registry_version=?, llm_stack=?, parse_json=?, "
                "ocr_ratio_salat=?, ocr_quote_woerter=?, llm_degradiert=? "
                "WHERE id=?",
                (klasse, neue_klasse_quelle, konfidenz, textquelle,
                 registry.version, _llm_stack_json(), parse_json,
                 ocr_ratio_salat, ocr_quote_woerter, llm_degradiert, intake_id),
            )
```

- [ ] **Step 4: Grün prüfen** (neue Tests + Pipeline-Regression)

Run: `python -m pytest backend/tests/test_n03_degradation.py backend/tests/test_intake_pipeline_s16a.py backend/tests/test_n02_ocr_qualitaet.py -v`
Expected: PASS (alle)

- [ ] **Step 5: Commit**

```bash
git add backend/intake/pipeline.py backend/tests/test_n03_degradation.py
git commit -m "feat(intake): N-03 Pipeline stempelt llm_degradiert + degradation"
```

---

### Task 7: `hole_queue` + `hole_detail` liefern die neuen Felder

**Files:**
- Modify: `backend/routers/intake_routes.py` (`hole_queue` ~Zeile 120-166, `hole_detail` parse-Block ~Zeile 257-264)
- Test: `backend/tests/test_intake_routes.py`

**Interfaces:**
- Consumes: Spalte `llm_degradiert` (Task 5), `parse_json.degradation` (Task 6).
- Produces: Queue-Eintrag enthält `"llm_degradiert"`; Detail-`parse` enthält `"degradation"`.

- [ ] **Step 1: Failing test** — Muster aus dem bestehenden N-02-Queue-Test (`test_intake_routes.py`, sucht nach `ocr_ratio_salat`) übernehmen und für `llm_degradiert` spiegeln. Test: ein Dokument mit `llm_degradiert=1` + `parse_json` mit `degradation` anlegen, `GET /intake/queue` bzw. `GET /intake/dokument/<id>` aufrufen, Feld prüfen. Konkret (an die vorhandene Testklasse/Fixtures der Datei anpassen — Client + Auth wie bei den bestehenden Intake-Routen-Tests):

```python
    def test_queue_liefert_llm_degradiert(self):
        did = self._intake_dokument(  # bestehender Helper der Testklasse
            queue_status="bereit_zur_review", llm_degradiert=1)
        r = self.client.get("/intake/queue", headers=self._auth())
        eintrag = next(e for e in r.get_json()["eintraege"] if e["id"] == did)
        self.assertEqual(eintrag["llm_degradiert"], 1)

    def test_detail_liefert_degradation(self):
        import json
        did = self._intake_dokument(
            queue_status="bereit_zur_review",
            parse_json=json.dumps({"degradation": {"llm_extraktion": "ausgefallen"}}))
        r = self.client.get(f"/intake/dokument/{did}", headers=self._auth())
        self.assertEqual(r.get_json()["parse"]["degradation"],
                         {"llm_extraktion": "ausgefallen"})
```

Falls der Datei-Helper `_intake_dokument(...)` die Kwargs `llm_degradiert`/`parse_json` noch nicht kennt, den Helper entsprechend erweitern (INSERT-Spaltenliste ergänzen).

- [ ] **Step 2: Fehlschlag prüfen**

Run: `python -m pytest backend/tests/test_intake_routes.py -k "llm_degradiert or degradation" -v`
Expected: FAIL (`KeyError`/`None`)

- [ ] **Step 3a: `hole_queue`** — in der SELECT-Spaltenliste (~Zeile 125) `i.llm_degradiert` ergänzen:

```python
            "       i.ocr_ratio_salat, i.ocr_quote_woerter, i.llm_degradiert, "
```

und im `eintraege.append({...})`-Dict (~Zeile 160) nach `ocr_quote_woerter`:

```python
            "llm_degradiert": r["llm_degradiert"],
```

- [ ] **Step 3b: `hole_detail`** — im `"parse": {...}`-Block (~Zeile 257-264) nach `"llm_konflikt": parse.get("llm_konflikt"),`:

```python
            "degradation": parse.get("degradation"),
```

- [ ] **Step 4: Grün prüfen**

Run: `python -m pytest backend/tests/test_intake_routes.py -v`
Expected: PASS (alle, inkl. bestehende)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_intake_routes.py
git commit -m "feat(intake): N-03 Queue/Detail liefern llm_degradiert + degradation"
```

---

### Task 8: Frontend — Queue-Badge + Detail-Hinweis

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (Badge nahe `OcrBadge` ~Zeile 131-144 + Einbau in `QueueEintrag` ~Zeile 176; Detail-Hinweis im `DetailPanel` ~Zeile 806)
- Test: `frontend/src/views/ReviewQueueView.degradation.test.jsx` (neu)

**Interfaces:**
- Consumes: Queue-Item-Feld `llm_degradiert` (Task 7), Detail-Feld `detail.parse.degradation` (Task 7).
- Produces: exportierte reine Funktion `istDegradiert(item) -> boolean`; sichtbares Badge „nur Regex" + Detail-Hinweisbox.

- [ ] **Step 1: Failing test** — neue Datei `frontend/src/views/ReviewQueueView.degradation.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { istDegradiert } from "./ReviewQueueView.jsx";

describe("istDegradiert", () => {
  it("true bei llm_degradiert === 1", () => {
    expect(istDegradiert({ llm_degradiert: 1 })).toBe(true);
  });
  it("false bei 0/null/undefined", () => {
    expect(istDegradiert({ llm_degradiert: 0 })).toBe(false);
    expect(istDegradiert({ llm_degradiert: null })).toBe(false);
    expect(istDegradiert({})).toBe(false);
    expect(istDegradiert(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Fehlschlag prüfen**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.degradation.test.jsx`
Expected: FAIL (`istDegradiert is not a function`)

- [ ] **Step 3a: Pure Funktion + Badge** — in `frontend/src/views/ReviewQueueView.jsx` direkt nach `OcrBadge` (~Zeile 144) einfügen:

```jsx
export function istDegradiert(item) {
  return item?.llm_degradiert === 1;
}

function DegradationBadge({ item }) {
  if (!istDegradiert(item)) return null;
  return (
    <span title="Feld-Extraktion ohne KI (nur Regex) — Felder bitte manuell pruefen."
      style={{
        background: T.amber + "22", color: T.amber, padding: "1px 7px",
        borderRadius: 8, fontSize: T.textXs, fontFamily: T.fontMono,
        whiteSpace: "nowrap",
      }}>
      nur Regex
    </span>
  );
}
```

- [ ] **Step 3b: Badge in `QueueEintrag`** — nach `<OcrBadge item={item} />` (~Zeile 176):

```jsx
        <DegradationBadge item={item} />
```

- [ ] **Step 3c: Detail-Hinweis** — im `DetailPanel`, nach dem `klassifikation.hinweise`-Block (~Zeile 806-811, direkt nach dessen schließendem `) : null}`) einfügen:

```jsx
          {detail.parse?.degradation?.llm_extraktion === "ausgefallen" && (
            <div role="alert" style={{
              marginTop: 8, padding: "6px 10px", borderRadius: 4,
              background: T.amber + "18", color: T.amber,
              fontSize: T.textXs, border: `1px solid ${T.amber}55`,
            }}>
              ⚠ Extraktion ohne KI (nur Regex) — Felder bitte manuell prüfen.
            </div>
          )}
```

- [ ] **Step 4a: Pure-Funktions-Test grün prüfen**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.degradation.test.jsx`
Expected: PASS

- [ ] **Step 4b: Gesamte Frontend-Suite grün prüfen** (keine Regression)

Run: `cd frontend && npx vitest run`
Expected: PASS (bestehende 52 + neue)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.degradation.test.jsx
git commit -m "feat(review): N-03 Degradations-Badge + Detail-Hinweis (nur Regex)"
```

---

### Task 9: Abschluss-Verifikation (voller Lauf + Doku)

**Files:**
- Modify: `docs/TODO.md` (N-03-Eintrag als erledigt), Memory-Update `project_unfallakten_pipeline_v7.md`.

- [ ] **Step 1: Voller Backend-Lauf, v7-Baseline gegenprüfen**

Run: `python -m pytest backend/tests/ -q`
Expected: Keine **neuen** Failures gegenüber der Baseline (204f/732p + N-01/N-02-Zusätze). Alle N-03-Dateien grün. Alt-Cluster-Failures (test_modul2/3/4/7, Auth) sind vorbestehend — per `git stash` gegenprüfen, falls unsicher.

- [ ] **Step 2: Golden-Files explizit grün prüfen**

Run: `python -m pytest backend/tests/test_registry_golden.py backend/tests/test_s16a_golden_e2e.py backend/tests/test_s18_review_e2e.py -v`
Expected: PASS (unverändert)

- [ ] **Step 3: TODO.md + Memory aktualisieren** — N-03 als erledigt eintragen (Reihenfolge: nächste offene = N-04/N-05 + Folge-Task Fragebogen-Feld-Übernahme), Kernpunkte notieren (Swallow bleibt; Ressourcendruck ohne harte Grenze; Migration 57).

- [ ] **Step 4: Commit**

```bash
git add docs/TODO.md
git commit -m "docs(todo): N-03 Retry-Differenzierung + Degradations-Hinweis erledigt"
```

---

## Self-Review-Ergebnis

- **Spec-Abdeckung:** Teil 1 (Klassifikation + Verzweigung) → Tasks 1-2. Teil 2 (llm_status → Marker → Queue-Badge + Detail-Hinweis, inkl. Migration 57 lt. Nutzerentscheidung „auch Queue-Badge") → Tasks 3-8. Ressourcendruck „keine harte Grenze" → Task 2 `test_ressourcendruck_vergiftet_nie`. Golden-Files → Task 9.
- **Platzhalter:** keine — jeder Code-Step enthält den vollständigen Code; Test-Steps nennen exakte Kommandos/Erwartung. Die einzigen „an bestehende Fixtures anpassen"-Hinweise (Task 7/Task 4 Registry) verweisen auf konkrete, im Repo vorhandene Vorlagen (N-02-Queue-Test bzw. `test_llm_ist_primaer_quelle_wenn_erfolgreich`).
- **Typ-Konsistenz:** `klassifiziere_fehler`→`markiere_fehler` (Kategorie-Strings identisch), `llm_status`∈{ok,aus,ausgefallen} durchgängig (Task 4→6), `llm_degradiert` 0/1 durchgängig (Task 5→6→7→8), `istDegradiert` identisch benannt in Test + Implementierung + Nutzung.
