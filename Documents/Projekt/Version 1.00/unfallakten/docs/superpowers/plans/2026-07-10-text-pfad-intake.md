# Text-Pfad für die Intake-Pipeline – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reine E-Mail-Texte (`payload_typ='text'`) laufen durch die Intake-Pipeline (Klassifikation + Aktenzeichen), erscheinen verschachtelt mit ihren Anhängen in der Review-Queue, und jeder Anhang zeigt den vollen E-Mail-Kontext.

**Architecture:** Eine Verzweigung am Anfang von `verarbeite_dokument` unterscheidet Text- von Datei-Payloads; ab der Textgewinnung läuft identischer Code (Klassifikation/Extraktion/Matching arbeiten bereits auf reinem Text). Das Review-Backend liefert zusätzlich `payload_typ`, einen `eltern_email`-Block (Anhang→Body) und Gruppierungs-Bezüge; das Frontend rendert Textblock, Kontext-Box und verschachtelte Liste.

**Tech Stack:** Python 3.12 / Flask / SQLite (`sqlite3`), pytest · React / Vite / Vitest + @testing-library/react.

## Global Constraints

- RA-MICRO SQL Server ist **read-only** — nur SQLite schreiben.
- Kein `executescript()`; ALTER TABLE braucht explizites `conn.commit()` davor+danach. (In diesem Plan gibt es **keine** Migration.)
- Alt-Pfade unverändert (Doppelschreiben-Prinzip); Datei-Verarbeitungsweg (`payload_typ='datei'`) bleibt bitgenau erhalten.
- Zielsprache Deutsch (Kommentare/Meldungen), keine unnötigen Abstraktionen, keine Kommentare außer bei nicht-offensichtlichem Verhalten.
- Branch: `intake-stufe1`. Vor dem Backfill-Lauf (Task 6): Sicherungskopie der SQLite-DB.
- Nicht im Umfang: Spam-Filter, umgekehrte Navigation (E-Mail→Anhangliste), Text→PDF-Rendering.
- Backend-Tests via Docker: `docker exec unfallakten-backend-dev python -m pytest <pfad> -q`. Frontend-Tests: `docker exec unfallakten-frontend-dev npm test` (Vitest).

---

### Task 1: Text-Zweig in der Pipeline

**Files:**
- Modify: `backend/intake/pipeline.py` (`_lade_dokument`, `verarbeite_dokument`; neuer Helper `_synth_seite`)
- Test: `backend/tests/test_intake_pipeline_textpfad.py` (neu)

**Interfaces:**
- Consumes: `SeitenText` (aus `..intake.text_extraktion`, bereits importiert), `extrahiere_seiten`, `aggregierte_textquelle`, `klassifiziere_stufe1/2`, `extrahiere_felder`, `finde_kandidaten`, `markiere_bereit`.
- Produces: `verarbeite_dokument(intake_id)` verarbeitet `payload_typ='text'` ohne Arbeitskopie; `_synth_seite(text: str) -> SeitenText`.

- [ ] **Step 1: Failing test schreiben**

> Robustheits-Hinweis: `pipeline.py`, `queue.py` und `database.py` halten je eigene `get_connection`-Referenzen. Statt `get_connection` zu mocken (fragil über Modulgrenzen), dem bestehenden DB-Setup-Muster aus `backend/tests/test_intake_pipeline_s16a.py` folgen (echte Temp-/Test-DB, `INTAKE_ARCHIV_ROOT`/`DB_PATH` via Fixture). Das folgende Skelett zeigt die Assertions; die DB-Bereitstellung an das vorhandene Fixture angleichen.

`backend/tests/test_intake_pipeline_textpfad.py`:

```python
import json
import sqlite3
import unittest
from unittest import mock

from backend.db import database
from backend.intake import pipeline


def _mk_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE intake_dokumente (
            id INTEGER PRIMARY KEY, sha256 TEXT, original_pfad TEXT,
            arbeitskopie_pfad TEXT, payload_typ TEXT, structured_payload TEXT,
            klasse TEXT, klasse_quelle TEXT, konfidenz REAL, parse_json TEXT,
            textquelle TEXT, registry_version TEXT, llm_stack TEXT,
            queue_status TEXT, versuch_zaehler INTEGER DEFAULT 0,
            naechster_versuch TEXT, fehler_detail TEXT, worker_lease TEXT
        );
        CREATE TABLE zustellungen (
            id INTEGER PRIMARY KEY, intake_dokument_id INTEGER, quelle TEXT,
            signale_json TEXT, parent_id INTEGER
        );
        """
    )
    return conn


class TestTextPfad(unittest.TestCase):
    def setUp(self):
        self.conn = _mk_conn()
        self.conn.execute(
            "INSERT INTO intake_dokumente (id, sha256, payload_typ, "
            "structured_payload, queue_status) VALUES "
            "(1, 'abc', 'text', ?, 'neu')",
            ("Sehr geehrte Damen und Herren, unser Zeichen 285/26. MfG",),
        )
        self.conn.commit()
        self._patch = mock.patch.object(
            database, "get_connection", return_value=self.conn
        )
        # get_connection wird als Kontextmanager genutzt -> __enter__/__exit__
        self.conn.__enter__ = lambda *a: self.conn
        self.conn.__exit__ = lambda *a: False
        self._patch.start()

    def tearDown(self):
        self._patch.stop()

    def test_text_payload_wird_bereit_ohne_arbeitskopie(self):
        ok = pipeline.verarbeite_dokument(1)
        self.assertTrue(ok)
        row = self.conn.execute(
            "SELECT queue_status, klasse, textquelle, parse_json "
            "FROM intake_dokumente WHERE id=1"
        ).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        self.assertEqual(row["textquelle"], "email_text")
        parse = json.loads(row["parse_json"])
        self.assertIn("285/26", parse["text_gesamt"])
```

- [ ] **Step 2: Test läuft rot**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_pipeline_textpfad.py -q`
Expected: FAIL — heutiger Code wirft „Arbeitskopie fehlt".

- [ ] **Step 3: `_synth_seite` + Verzweigung implementieren**

In `backend/intake/pipeline.py` neuen Helper direkt vor `verarbeite_dokument` einfügen:

```python
def _synth_seite(text: str) -> SeitenText:
    """E-Mail-Text als synthetische Ein-Seiten-Struktur (kein PDF/OCR)."""
    return SeitenText(nr=1, text=text, braucht_ocr=False,
                      ratio_salat=0.0, textquelle="email_text")
```

`_lade_dokument` SELECT um zwei Spalten erweitern:

```python
        row = conn.execute(
            "SELECT id, sha256, arbeitskopie_pfad, original_pfad, "
            "       payload_typ, structured_payload, "
            "       klasse, klasse_quelle, konfidenz "
            "FROM intake_dokumente WHERE id=?", (intake_id,)
        ).fetchone()
```

In `verarbeite_dokument` den Block (heute Zeilen ~136–157) ersetzen:

```python
        dok = _lade_dokument(intake_id)

        if dok.get("payload_typ") == "text":
            text_roh = (dok.get("structured_payload") or "")
            if not text_roh.strip():
                raise RuntimeError("Text-Payload ohne Inhalt")
            seiten = [_synth_seite(text_roh)]
            text_gesamt = text_roh
            textquelle = "email_text"
        else:
            arbeit = dok.get("arbeitskopie_pfad")
            if not arbeit or not os.path.isfile(arbeit):
                raise RuntimeError(f"Arbeitskopie fehlt: {arbeit}")
            with open(arbeit, "rb") as f:
                pdf_bytes = f.read()
            seiten = extrahiere_seiten(pdf_bytes)
            if not seiten:
                raise RuntimeError("Keine Seiten extrahierbar")
            for s in seiten:
                if s.braucht_ocr:
                    s.text = _ocr_seite(pdf_bytes, s.nr, dok["sha256"])
                    s.textquelle = "ocr"
            text_gesamt = "\n\n".join(s.text for s in seiten if s.text)
            textquelle = aggregierte_textquelle(seiten)
```

Der restliche Code ab `registry = lade_registry(...)` bleibt **unverändert** (nutzt `text_gesamt`, `seiten`, `textquelle`).

- [ ] **Step 4: Test läuft grün**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_pipeline_textpfad.py -q`
Expected: PASS.

- [ ] **Step 5: Regression Datei-Weg prüfen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_pipeline_s16a.py backend/tests/test_s16a_golden_e2e.py -q`
Expected: keine neuen Failures gegenüber Baseline (bekannte Alt-Failures bleiben).

- [ ] **Step 6: Commit**

```bash
git add "backend/intake/pipeline.py" "backend/tests/test_intake_pipeline_textpfad.py"
git commit -m "feat(intake): Text-Zweig in der Pipeline (E-Mail-Body ohne Arbeitskopie)"
```

---

### Task 2: `hole_detail` liefert `payload_typ` + `eltern_email`

**Files:**
- Modify: `backend/routers/intake_routes.py` (`hole_detail`; neuer Helper `_lade_eltern_email`)
- Test: `backend/tests/test_intake_detail_eltern.py` (neu)

**Interfaces:**
- Consumes: `_parse`, `get_connection`.
- Produces: `hole_detail`-Response enthält `payload_typ` (str) und `eltern_email` (dict|null) mit Schlüsseln `intake_id, absender, betreff, empfangen_am, text, akte_az`.

- [ ] **Step 1: Failing test schreiben**

`backend/tests/test_intake_detail_eltern.py`:

```python
import json
import sqlite3
import unittest
from unittest import mock

from backend.routers import intake_routes


class TestElternEmail(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE intake_dokumente (id INTEGER PRIMARY KEY, sha256 TEXT,
              original_pfad TEXT, arbeitskopie_pfad TEXT, payload_typ TEXT,
              structured_payload TEXT, klasse TEXT, klasse_quelle TEXT,
              konfidenz REAL, queue_status TEXT, textquelle TEXT,
              registry_version TEXT, llm_stack TEXT, prioritaet_frist INTEGER,
              fehler_detail TEXT, erstellt_am TEXT, parse_json TEXT,
              verworfen_am TEXT);
            CREATE TABLE zustellungen (id INTEGER PRIMARY KEY,
              intake_dokument_id INTEGER, quelle TEXT, absender TEXT,
              auth_status TEXT, betreff TEXT, empfangen_am TEXT, parent_id INTEGER,
              konto TEXT, roh_referenz TEXT, erstellt_am TEXT);
            CREATE TABLE freigaben (id INTEGER PRIMARY KEY, intake_dokument_id INTEGER,
              akte_az TEXT, dokument_id INTEGER, freigegeben_von INTEGER,
              freigegeben_am TEXT);
            """
        )
        # Body (intake 1, zust 10) + Anhang (intake 2, zust 11 parent=10)
        self.conn.execute("INSERT INTO intake_dokumente (id, payload_typ, "
            "structured_payload, parse_json) VALUES (1,'text','Body-Text', ?)",
            (json.dumps({"text_gesamt": "Body mit 285/26",
                         "akten_kandidaten": [{"akte_az": "285/26"}]}),))
        self.conn.execute("INSERT INTO intake_dokumente (id, payload_typ) "
            "VALUES (2,'datei')")
        self.conn.execute("INSERT INTO zustellungen (id, intake_dokument_id, "
            "absender, betreff, empfangen_am, parent_id) VALUES "
            "(10, 1, 'sv@example.de', 'Ihr Brief', '2026-07-10', NULL)")
        self.conn.execute("INSERT INTO zustellungen (id, intake_dokument_id, "
            "parent_id) VALUES (11, 2, 10)")
        self.conn.commit()
        self.conn.__enter__ = lambda *a: self.conn
        self.conn.__exit__ = lambda *a: False
        self._p = mock.patch.object(intake_routes, "get_connection",
                                    return_value=self.conn)
        self._p.start()
        self._li = mock.patch.object(intake_routes, "_lade_intake",
            side_effect=lambda i: dict(self.conn.execute(
                "SELECT * FROM intake_dokumente WHERE id=?", (i,)).fetchone()))
        self._li.start()

    def tearDown(self):
        self._p.stop(); self._li.stop()

    def test_anhang_liefert_eltern_email(self):
        with intake_routes.intake_bp.make_setup_state(mock.Mock(), {}, first=False):
            pass
        resp, status = intake_routes.hole_detail(2)
        data = resp.get_json()
        self.assertEqual(status, 200)
        self.assertEqual(data["payload_typ"], "datei")
        self.assertIsNotNone(data["eltern_email"])
        self.assertEqual(data["eltern_email"]["absender"], "sv@example.de")
        self.assertEqual(data["eltern_email"]["akte_az"], "285/26")

    def test_email_selbst_hat_keine_eltern(self):
        resp, status = intake_routes.hole_detail(1)
        data = resp.get_json()
        self.assertEqual(data["payload_typ"], "text")
        self.assertIsNone(data["eltern_email"])
```

> Hinweis: `hole_detail` ist mit `@login_erforderlich` dekoriert. Falls der direkte Funktionsaufruf am Decorator scheitert, stattdessen den Test über einen Flask-Testclient mit gültigem Token fahren (Muster: `backend/tests/test_intake_routes.py::setUp`). Die Assertions bleiben identisch.

- [ ] **Step 2: Test läuft rot**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_detail_eltern.py -q`
Expected: FAIL — `payload_typ`/`eltern_email` fehlen in der Response.

- [ ] **Step 3: Helper + Response-Felder implementieren**

In `backend/routers/intake_routes.py` Helper vor `hole_detail` einfügen:

```python
def _lade_eltern_email(conn, intake_id: int) -> Optional[Dict[str, Any]]:
    """Voller E-Mail-Kontext eines Anhangs: ueber zustellung.parent_id die
    Body-Zustellung finden und aus deren intake_dokument Text + AZ ziehen."""
    kind = conn.execute(
        "SELECT parent_id FROM zustellungen "
        "WHERE intake_dokument_id=? AND parent_id IS NOT NULL "
        "ORDER BY id ASC LIMIT 1", (intake_id,)
    ).fetchone()
    if not kind:
        return None
    parent = conn.execute(
        "SELECT z.intake_dokument_id AS iid, z.absender, z.betreff, "
        "       z.empfangen_am, i.parse_json "
        "FROM zustellungen z JOIN intake_dokumente i "
        "  ON i.id = z.intake_dokument_id "
        "WHERE z.id=?", (kind["parent_id"],)
    ).fetchone()
    if not parent:
        return None
    parse = _parse(parent["parse_json"])
    kand = parse.get("akten_kandidaten") or []
    return {
        "intake_id": parent["iid"],
        "absender": parent["absender"],
        "betreff": parent["betreff"],
        "empfangen_am": parent["empfangen_am"],
        "text": parse.get("text_gesamt", ""),
        "akte_az": kand[0]["akte_az"] if kand else None,
    }
```

In `hole_detail` innerhalb des `with get_connection() as conn:`-Blocks nach den bestehenden Queries ergänzen:

```python
        eltern_email = _lade_eltern_email(conn, intake_id)
```

Im Response-Dict zwei Felder hinzufügen (neben `arbeitskopie_pfad`):

```python
        "payload_typ": dok.get("payload_typ"),
        ...
        "eltern_email": eltern_email,
```

- [ ] **Step 4: Test läuft grün**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_detail_eltern.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "backend/routers/intake_routes.py" "backend/tests/test_intake_detail_eltern.py"
git commit -m "feat(review): hole_detail liefert payload_typ + eltern_email-Kontext"
```

---

### Task 3: `hole_queue` liefert Gruppierungs-Bezüge

**Files:**
- Modify: `backend/routers/intake_routes.py` (`hole_queue`)
- Test: `backend/tests/test_intake_queue_gruppen.py` (neu)

**Interfaces:**
- Produces: jeder Queue-Eintrag enthält zusätzlich `payload_typ`, `zustellung_id` (int|null), `parent_zustellung_id` (int|null), `absender` (str|null), `betreff` (str|null).

- [ ] **Step 1: Failing test schreiben**

`backend/tests/test_intake_queue_gruppen.py`:

```python
import sqlite3, unittest
from unittest import mock
from backend.routers import intake_routes


class TestQueueGruppen(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE intake_dokumente (id INTEGER PRIMARY KEY, sha256 TEXT,
              klasse TEXT, klasse_quelle TEXT, konfidenz REAL, queue_status TEXT,
              prioritaet_frist INTEGER, erstellt_am TEXT, fehler_detail TEXT,
              parse_json TEXT, payload_typ TEXT, verworfen_am TEXT);
            CREATE TABLE zustellungen (id INTEGER PRIMARY KEY,
              intake_dokument_id INTEGER, absender TEXT, betreff TEXT,
              parent_id INTEGER);
            """
        )
        self.conn.execute("INSERT INTO intake_dokumente (id, queue_status, "
            "payload_typ, erstellt_am) VALUES (1,'bereit_zur_review','text','2026-07-10 08:00')")
        self.conn.execute("INSERT INTO intake_dokumente (id, queue_status, "
            "payload_typ, erstellt_am) VALUES (2,'bereit_zur_review','datei','2026-07-10 08:01')")
        self.conn.execute("INSERT INTO zustellungen (id, intake_dokument_id, "
            "absender, betreff, parent_id) VALUES (10,1,'sv@x.de','Brief',NULL)")
        self.conn.execute("INSERT INTO zustellungen (id, intake_dokument_id, "
            "parent_id) VALUES (11,2,10)")
        self.conn.commit()
        self.conn.__enter__ = lambda *a: self.conn
        self.conn.__exit__ = lambda *a: False
        self._p = mock.patch.object(intake_routes, "get_connection",
                                    return_value=self.conn)
        self._p.start()

    def tearDown(self):
        self._p.stop()

    def test_gruppen_bezuege_vorhanden(self):
        resp, status = intake_routes.hole_queue()
        eintraege = {e["id"]: e for e in resp.get_json()["eintraege"]}
        self.assertEqual(eintraege[1]["payload_typ"], "text")
        self.assertEqual(eintraege[1]["zustellung_id"], 10)
        self.assertIsNone(eintraege[1]["parent_zustellung_id"])
        self.assertEqual(eintraege[1]["absender"], "sv@x.de")
        self.assertEqual(eintraege[2]["parent_zustellung_id"], 10)
```

- [ ] **Step 2: Test läuft rot**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_queue_gruppen.py -q`
Expected: FAIL (KeyError `payload_typ`).

- [ ] **Step 3: Query + Response erweitern**

In `hole_queue` das SELECT ersetzen (korrelierte Subqueries liefern die früheste Zustellung je Dokument):

```python
        rows = conn.execute(
            "SELECT i.id, i.sha256, i.klasse, i.klasse_quelle, i.konfidenz, "
            "       i.queue_status, i.prioritaet_frist, i.erstellt_am, "
            "       i.fehler_detail, i.parse_json, i.payload_typ, "
            "  (SELECT z.id FROM zustellungen z WHERE z.intake_dokument_id=i.id "
            "     ORDER BY z.id ASC LIMIT 1) AS zustellung_id, "
            "  (SELECT z.parent_id FROM zustellungen z WHERE z.intake_dokument_id=i.id "
            "     ORDER BY z.id ASC LIMIT 1) AS parent_zustellung_id, "
            "  (SELECT z.absender FROM zustellungen z WHERE z.intake_dokument_id=i.id "
            "     ORDER BY z.id ASC LIMIT 1) AS absender, "
            "  (SELECT z.betreff FROM zustellungen z WHERE z.intake_dokument_id=i.id "
            "     ORDER BY z.id ASC LIMIT 1) AS betreff "
            "FROM intake_dokumente i "
            "WHERE i.queue_status IN ('bereit_zur_review','pipeline_fehler') "
            "  AND i.verworfen_am IS NULL "
            "ORDER BY i.erstellt_am ASC, i.id ASC, "
            "         COALESCE(i.konfidenz, 0) DESC"
        ).fetchall()
```

Im Eintrag-Dict fünf Felder ergänzen:

```python
            "payload_typ": r["payload_typ"],
            "zustellung_id": r["zustellung_id"],
            "parent_zustellung_id": r["parent_zustellung_id"],
            "absender": r["absender"],
            "betreff": r["betreff"],
```

- [ ] **Step 4: Test läuft grün**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_queue_gruppen.py backend/tests/test_intake_routes.py -q`
Expected: PASS (inkl. bestehender Queue-Tests).

- [ ] **Step 5: Commit**

```bash
git add "backend/routers/intake_routes.py" "backend/tests/test_intake_queue_gruppen.py"
git commit -m "feat(review): hole_queue liefert Gruppierungs-Bezuege (payload_typ, parent)"
```

---

### Task 4: Frontend – Textblock + Eltern-E-Mail-Box im DetailPanel

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (`DetailPanel`)
- Test: `frontend/src/views/__tests__/DetailPanelText.test.jsx` (neu)

**Interfaces:**
- Consumes: `hole_detail`-Felder `payload_typ`, `parse.text_gesamt`, `eltern_email` (Task 2).

- [ ] **Step 1: Failing test schreiben**

`frontend/src/views/__tests__/DetailPanelText.test.jsx` — testet die reine Darstellungslogik. Falls `DetailPanel` nicht isoliert testbar ist (API-Fetch im Effekt), eine kleine reine Render-Hilfe `EmailKontextBox({ eltern })` + `TextVorschau({ text })` aus `ReviewQueueView.jsx` exportieren und diese testen:

```jsx
import { render, screen } from '@testing-library/react';
import { EmailKontextBox, TextVorschau } from '../ReviewQueueView.jsx';

test('EmailKontextBox zeigt Absender, Betreff und AZ', () => {
  render(<EmailKontextBox eltern={{
    absender: 'sv@x.de', betreff: 'Ihr Brief', empfangen_am: '2026-07-10',
    text: 'Body mit 285/26', akte_az: '285/26',
  }} />);
  expect(screen.getByText(/sv@x\.de/)).toBeInTheDocument();
  expect(screen.getByText(/285\/26/)).toBeInTheDocument();
  expect(screen.getByText(/Kam mit E-Mail/i)).toBeInTheDocument();
});

test('TextVorschau rendert den E-Mail-Text', () => {
  render(<TextVorschau text={'Zeile A\nZeile B'} />);
  expect(screen.getByText(/Zeile A/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Test läuft rot**

Run: `docker exec unfallakten-frontend-dev npm test -- --run DetailPanelText`
Expected: FAIL — Komponenten nicht exportiert.

- [ ] **Step 3: Komponenten implementieren + einbinden**

In `frontend/src/views/ReviewQueueView.jsx` zwei benannte Exports ergänzen:

```jsx
export function TextVorschau({ text }) {
  return (
    <pre style={{
      whiteSpace: "pre-wrap", wordBreak: "break-word",
      fontFamily: T.fontBody, fontSize: T.textSm, color: T.text,
      background: T.offWhite, border: `1px solid ${T.border}`,
      borderRadius: 6, padding: 12, maxHeight: "60vh", overflow: "auto",
    }}>{text || "(kein Text)"}</pre>
  );
}

export function EmailKontextBox({ eltern }) {
  if (!eltern) return null;
  return (
    <div style={{
      border: `1px solid ${T.accent}`, background: T.accentPale,
      borderRadius: 8, padding: 12, marginBottom: 12, fontSize: T.textSm,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>📧 Kam mit E-Mail</div>
      <div><strong>Absender:</strong> {eltern.absender || "—"}</div>
      <div><strong>Betreff:</strong> {eltern.betreff || "—"}</div>
      <div><strong>Datum:</strong> {eltern.empfangen_am || "—"}</div>
      {eltern.akte_az && (
        <div><strong>Aktenzeichen:</strong> {eltern.akte_az}</div>
      )}
      <details style={{ marginTop: 6 }}>
        <summary style={{ cursor: "pointer" }}>E-Mail-Text anzeigen</summary>
        <TextVorschau text={eltern.text} />
      </details>
    </div>
  );
}
```

Im `DetailPanel`-Render: wenn `detail.payload_typ === "text"`, statt des PDF-`iframe` `<TextVorschau text={detail.parse?.text_gesamt} />` zeigen; unabhängig davon `<EmailKontextBox eltern={detail.eltern_email} />` oberhalb der Vorschau rendern. Die bestehende iframe-Anzeige bleibt für `payload_typ !== "text"`.

- [ ] **Step 4: Test läuft grün**

Run: `docker exec unfallakten-frontend-dev npm test -- --run DetailPanelText`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "frontend/src/views/ReviewQueueView.jsx" "frontend/src/views/__tests__/DetailPanelText.test.jsx"
git commit -m "feat(review): E-Mail-Text lesbar + Eltern-E-Mail-Box am Anhang"
```

---

### Task 5: Frontend – Verschachtelte Queue (Variante A)

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (Liste in `ReviewQueueView` + `QueueEintrag`)
- Test: `frontend/src/views/__tests__/QueueGruppen.test.jsx` (neu)

**Interfaces:**
- Consumes: Queue-Felder `payload_typ`, `zustellung_id`, `parent_zustellung_id`, `absender`, `betreff` (Task 3).
- Produces: reine Funktion `gruppiereQueue(eintraege) -> Array<{ eintrag, kinder: [] }>`.

- [ ] **Step 1: Failing test schreiben**

`frontend/src/views/__tests__/QueueGruppen.test.jsx`:

```jsx
import { gruppiereQueue } from '../ReviewQueueView.jsx';

test('Anhang wird unter seine E-Mail gruppiert', () => {
  const eintraege = [
    { id: 1, zustellung_id: 10, parent_zustellung_id: null, payload_typ: 'text' },
    { id: 2, zustellung_id: 11, parent_zustellung_id: 10, payload_typ: 'datei' },
    { id: 3, zustellung_id: 12, parent_zustellung_id: null, payload_typ: 'datei' },
  ];
  const gruppen = gruppiereQueue(eintraege);
  expect(gruppen).toHaveLength(2);          // E-Mail(1)+Kind(2), Standalone(3)
  expect(gruppen[0].eintrag.id).toBe(1);
  expect(gruppen[0].kinder.map(k => k.id)).toEqual([2]);
  expect(gruppen[1].eintrag.id).toBe(3);
  expect(gruppen[1].kinder).toEqual([]);
});

test('Anhang ohne sichtbare Eltern wird eigene Wurzel', () => {
  const gruppen = gruppiereQueue([
    { id: 9, zustellung_id: 90, parent_zustellung_id: 77, payload_typ: 'datei' },
  ]);
  expect(gruppen).toHaveLength(1);
  expect(gruppen[0].eintrag.id).toBe(9);
});
```

- [ ] **Step 2: Test läuft rot**

Run: `docker exec unfallakten-frontend-dev npm test -- --run QueueGruppen`
Expected: FAIL — `gruppiereQueue` nicht exportiert.

- [ ] **Step 3: `gruppiereQueue` + verschachteltes Rendern implementieren**

In `frontend/src/views/ReviewQueueView.jsx` benannten Export ergänzen:

```jsx
export function gruppiereQueue(eintraege) {
  const nachZust = new Map();
  eintraege.forEach(e => {
    if (e.zustellung_id != null) nachZust.set(e.zustellung_id, e);
  });
  const gruppen = [];
  const zuKind = new Map();
  eintraege.forEach(e => {
    const p = e.parent_zustellung_id;
    if (p != null && nachZust.has(p)) {
      if (!zuKind.has(p)) zuKind.set(p, []);
      zuKind.get(p).push(e);
    }
  });
  const istKind = new Set();
  zuKind.forEach(kinder => kinder.forEach(k => istKind.add(k.id)));
  eintraege.forEach(e => {
    if (istKind.has(e.id)) return;
    gruppen.push({ eintrag: e, kinder: zuKind.get(e.zustellung_id) || [] });
  });
  return gruppen;
}
```

In `ReviewQueueView` die flache `queue.map(...)`-Liste ersetzen: `gruppiereQueue(queue).map(gruppe => ...)` — pro Gruppe zuerst `QueueEintrag` für `gruppe.eintrag` (E-Mail-Kopf: bei `payload_typ==='text'` Icon 📧 + `absender`/`betreff` anzeigen), dann `gruppe.kinder.map(k => <QueueEintrag ... eingerueckt />)`. `QueueEintrag` erhält ein optionales Prop `eingerueckt` (bool): bei `true` `marginLeft: 26` + linke blaue Randlinie (`borderLeft: 2px solid ${T.accent}40`) und 📎-Icon. Bestehende Props (`aktiv`, `onClick`, `onVerwerfen`) unverändert durchreichen.

- [ ] **Step 4: Test läuft grün**

Run: `docker exec unfallakten-frontend-dev npm test -- --run QueueGruppen`
Expected: PASS.

- [ ] **Step 5: Gesamte Frontend-Suite prüfen**

Run: `docker exec unfallakten-frontend-dev npm test -- --run`
Expected: alle grün (bestehende 32 + neue).

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/views/ReviewQueueView.jsx" "frontend/src/views/__tests__/QueueGruppen.test.jsx"
git commit -m "feat(review): verschachtelte Queue (E-Mail-Kopf + eingerueckte Anhaenge)"
```

---

### Task 6: Backfill der 52 aufgelaufenen Text-Fehler

**Files:**
- Create: `scripts/backfill_textpfad.py`
- Test: manuell (Einmal-Lauf gegen Live-DB nach Deploy)

**Interfaces:**
- Consumes: `backend.intake.queue.enqueue`, `get_connection`.

- [ ] **Step 1: Skript schreiben**

`scripts/backfill_textpfad.py`:

```python
"""Reiht pipeline_fehler-Text-Dokumente einmalig neu ein (Text-Pfad-Deploy).

Idempotent: verarbeitet nur queue_status='pipeline_fehler' AND payload_typ='text'.
Vor dem Lauf MUSS ein DB-Backup existieren (siehe Step 2)."""
from backend.db.database import get_connection
from backend.intake.queue import enqueue

with get_connection() as conn:
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM intake_dokumente "
        "WHERE queue_status='pipeline_fehler' AND payload_typ='text' "
        "  AND verworfen_am IS NULL"
    ).fetchall()]

print(f"Neu einzureihen: {len(ids)} Text-Dokumente")
for i in ids:
    enqueue(i)
print("Fertig. Worker verarbeitet sie beim naechsten Tick (max. 10s).")
```

- [ ] **Step 2: DB-Backup + Lauf (nach Deploy von Task 1–5)**

```bash
docker exec unfallakten-backend-dev sh -c 'cp /app/data/unfallakten.db /app/data/unfallakten.db.bak_pre_textbackfill_$(date +%Y%m%d_%H%M%S)'
docker exec unfallakten-backend-dev python scripts/backfill_textpfad.py
```
Expected: „Neu einzureihen: 52 Text-Dokumente" (Zahl kann abweichen, wenn zwischenzeitlich welche verworfen wurden).

- [ ] **Step 3: Ergebnis verifizieren (nach ~2–5 Min)**

```bash
docker exec unfallakten-backend-dev python -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print('pipeline_fehler text:', c.execute(\"SELECT COUNT(*) FROM intake_dokumente WHERE queue_status='pipeline_fehler' AND payload_typ='text'\").fetchone()[0])"
```
Expected: 0 (oder nur solche mit leerem `structured_payload` → definierter Fehler, akzeptabel).

- [ ] **Step 4: Commit**

```bash
git add "scripts/backfill_textpfad.py"
git commit -m "chore(intake): Backfill-Skript fuer aufgelaufene Text-Fehler"
```

---

## Reihenfolge & Abnahme

Tasks 1→5 in Reihenfolge (jeweils lauffähig + Tests grün, bevor der nächste beginnt). Task 6 erst **nach** Deploy von 1–5 auf den laufenden Container. Abnahmekriterien der Spec (Abschnitt „Abnahmekriterien") gelten je Task.
