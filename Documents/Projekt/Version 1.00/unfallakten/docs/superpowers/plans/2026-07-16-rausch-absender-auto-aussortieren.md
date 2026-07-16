# Rausch-Absender auto-aussortieren + Papierkorb — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Placetel- und beA-Benachrichtigungen auf `info@` beim Eingang automatisch aus der Review-Queue aussortieren (Soft-Delete), plus ein Papierkorb zum Einsehen/Wiederherstellen.

**Architecture:** Eine YAML-Registry (`rausch_absender.yaml`) mappt Absender-Domains auf eine Policy (`nur_body`/`komplett`). Ein reines Regel-Modul liest sie fail-loud. Der IMAP-Adapter markiert nach dem Anlegen der Intake-Dokumente die passenden per gemeinsamem `auto_verwerfen`-Helfer als verworfen (`verworfen_von=NULL` = System) — derselbe Soft-Delete wie der manuelle Verwerfen-Button. Zwei neue Endpunkte + ein Frontend-Umschalter bilden den Papierkorb.

**Tech Stack:** Python/Flask, SQLite, PyYAML, React (Vite/Vitest), Pytest/unittest.

## Global Constraints

- **RA-MICRO ist read-only** — dieses Feature schreibt ausschließlich in SQLite-Intake-Tabellen (`intake_dokumente`, `korrektur_log`). Keine Akten-Tabellen.
- **`INTAKE_REVIEW_PFLICHT` gewahrt** — es wird kein neuer Schreibweg in Akten-Tabellen eröffnet; nur Soft-Delete/Restore auf `intake_dokumente`.
- **Zielsprache Deutsch** (Nutzer ist Rechtsanwalt, nicht technisch).
- **Keine unnötigen Abstraktionen; keine Kommentare** außer bei nicht-offensichtlichem Verhalten.
- **Keine Migration** — `verworfen_grund`/`verworfen_am`/`verworfen_von` existieren seit Migration 53.
- **Konfig-Werte verbatim:** Placetel-Domain `placetel.de` → `nur_body`; beA-Domain `bea-brak.de` → `komplett`. Erlaubte Policies: `nur_body`, `komplett`. Neuer Verwerf-Grund: `rauschen`.
- **Fail-loud Registry-Laden** wie `backend/intake/registry_loader.py` — defektes/fehlendes YAML → `RuntimeError`.
- Branch: `rausch-absender-aussortieren` (bereits angelegt, Spec darauf committet).

---

## File Structure

- **Create** `backend/registry/rausch_absender.yaml` — Absender→Policy-Konfig.
- **Create** `backend/intake/rausch_regel.py` — fail-loud Loader + reine `policy_fuer_domain`.
- **Create** `backend/intake/verwerfen.py` — gemeinsamer `auto_verwerfen`-Helfer (System- + manuelles Verwerfen).
- **Modify** `backend/intake/adapter_imap.py` — `verarbeite_email` ruft die Regel + `auto_verwerfen`.
- **Modify** `backend/routers/intake_routes.py` — `post_verwerfen` nutzt `auto_verwerfen`; neu `GET /intake/papierkorb` + `POST /intake/dokument/<id>/wiederherstellen`; `_VERWERFEN_GRUENDE += {"rauschen"}`.
- **Modify** `frontend/src/api.js` — `papierkorb()` + `wiederherstellen(id)`.
- **Modify** `frontend/src/views/ReviewQueueView.jsx` — Queue/Papierkorb-Umschalter, Papierkorb-Liste, `grundLabel` (exportiert, pure).
- **Create** Tests: `backend/tests/test_rausch_regel.py`, `backend/tests/test_auto_verwerfen.py`, `backend/tests/test_rausch_aussortieren_e2e.py`, `backend/tests/test_papierkorb_routes.py`, `frontend/src/views/ReviewQueueView.papierkorb.test.jsx`.

---

## Task 1: Rausch-Regel Registry + Modul

**Files:**
- Create: `backend/registry/rausch_absender.yaml`
- Create: `backend/intake/rausch_regel.py`
- Test: `backend/tests/test_rausch_regel.py`

**Interfaces:**
- Produces:
  - `rausch_regel.lade_regeln(pfad: str | None = None, *, reload: bool = False) -> dict[str, str]` — `{domain: policy}`, fail-loud.
  - `rausch_regel.policy_fuer_domain(domain: str | None) -> str | None` — `'nur_body' | 'komplett' | None`.
  - `rausch_regel.standard_pfad() -> str` — Default-Pfad, per Env `INTAKE_RAUSCH_REGISTRY_PFAD` überschreibbar.

- [ ] **Step 1: Konfig-Datei anlegen**

Create `backend/registry/rausch_absender.yaml`:

```yaml
# Rausch-Absender: E-Mails, die beim Eingang automatisch aussortiert werden.
# policy nur_body   -> Body verwerfen, Anhaenge (z.B. Faxe) behalten
# policy komplett   -> Body + alle Anhaenge verwerfen
- domain: placetel.de
  policy: nur_body
- domain: bea-brak.de
  policy: komplett
```

- [ ] **Step 2: Failing tests schreiben**

Create `backend/tests/test_rausch_regel.py`:

```python
"""Tests fuer backend/intake/rausch_regel.py (Rausch-Absender-Regel)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake import rausch_regel


def _schreibe_yaml(inhalt: str) -> str:
    fd, pfad = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(inhalt)
    return pfad


class TestPolicyFuerDomain(unittest.TestCase):
    def test_placetel_ist_nur_body(self):
        self.assertEqual(rausch_regel.policy_fuer_domain("placetel.de"), "nur_body")

    def test_bea_ist_komplett(self):
        self.assertEqual(rausch_regel.policy_fuer_domain("bea-brak.de"), "komplett")

    def test_grossschreibung_egal(self):
        self.assertEqual(rausch_regel.policy_fuer_domain("Placetel.DE"), "nur_body")

    def test_unbekannte_domain_none(self):
        self.assertIsNone(rausch_regel.policy_fuer_domain("versicherung.de"))

    def test_none_domain_none(self):
        self.assertIsNone(rausch_regel.policy_fuer_domain(None))
        self.assertIsNone(rausch_regel.policy_fuer_domain(""))


class TestLadeRegeln(unittest.TestCase):
    def test_gueltige_yaml(self):
        pfad = _schreibe_yaml(
            "- domain: a.de\n  policy: nur_body\n"
            "- domain: b.de\n  policy: komplett\n"
        )
        self.addCleanup(os.remove, pfad)
        regeln = rausch_regel.lade_regeln(pfad, reload=True)
        self.assertEqual(regeln, {"a.de": "nur_body", "b.de": "komplett"})

    def test_unbekannte_policy_wirft(self):
        pfad = _schreibe_yaml("- domain: a.de\n  policy: quatsch\n")
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_doppelte_domain_wirft(self):
        pfad = _schreibe_yaml(
            "- domain: a.de\n  policy: nur_body\n"
            "- domain: a.de\n  policy: komplett\n"
        )
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_fehlendes_feld_wirft(self):
        pfad = _schreibe_yaml("- domain: a.de\n")
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_wurzel_kein_list_wirft(self):
        pfad = _schreibe_yaml("domain: a.de\npolicy: nur_body\n")
        self.addCleanup(os.remove, pfad)
        with self.assertRaises(RuntimeError):
            rausch_regel.lade_regeln(pfad, reload=True)

    def test_standard_registry_laedt(self):
        regeln = rausch_regel.lade_regeln(rausch_regel.standard_pfad(), reload=True)
        self.assertEqual(regeln.get("placetel.de"), "nur_body")
        self.assertEqual(regeln.get("bea-brak.de"), "komplett")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Test laufen lassen → FAIL**

Run: `cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/unfallakten" && python -m pytest backend/tests/test_rausch_regel.py -q`
Expected: FAIL (`ModuleNotFoundError: backend.intake.rausch_regel`).

- [ ] **Step 4: Modul implementieren**

Create `backend/intake/rausch_regel.py`:

```python
"""
Rausch-Absender-Regel.

Laedt backend/registry/rausch_absender.yaml (fail-loud) und beantwortet, ob
eine Absender-Domain automatisch aussortiert wird und mit welcher Policy:

    nur_body  -> E-Mail-Body verwerfen, Anhaenge behalten (Placetel: Fax bleibt)
    komplett  -> Body + alle Anhaenge verwerfen (beA-Benachrichtigung)

Kein Treffer -> None (unangetastet).
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_ERLAUBTE_POLICIES = ("nur_body", "komplett")

_cache: Dict[str, Dict[str, str]] = {}


def standard_pfad() -> str:
    env_pfad = os.environ.get("INTAKE_RAUSCH_REGISTRY_PFAD")
    if env_pfad:
        return os.path.normpath(env_pfad)
    hier = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(
        os.path.join(hier, "..", "registry", "rausch_absender.yaml")
    )


def lade_regeln(pfad: Optional[str] = None, *, reload: bool = False) -> Dict[str, str]:
    pfad_norm = os.path.normpath(pfad or standard_pfad())
    if not reload and pfad_norm in _cache:
        return _cache[pfad_norm]

    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML nicht installiert (PyYAML>=6.0).") from exc

    if not os.path.isfile(pfad_norm):
        logger.error("Rausch-Registry fehlt: %s", pfad_norm)
        raise RuntimeError(f"Rausch-Registry fehlt: {pfad_norm}")

    try:
        with open(pfad_norm, "rb") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        msg = f"YAML-Syntaxfehler in {pfad_norm}: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    if not isinstance(data, list):
        raise RuntimeError(
            f"Rausch-Registry {pfad_norm}: Wurzel muss eine Liste sein, "
            f"ist {type(data).__name__}"
        )

    regeln: Dict[str, str] = {}
    for i, eintrag in enumerate(data):
        if not isinstance(eintrag, dict):
            raise RuntimeError(f"Eintrag {i} in {pfad_norm} ist kein Mapping.")
        domain = eintrag.get("domain")
        policy = eintrag.get("policy")
        if not isinstance(domain, str) or not domain.strip():
            raise RuntimeError(f"Eintrag {i} in {pfad_norm}: 'domain' fehlt/leer.")
        if policy not in _ERLAUBTE_POLICIES:
            raise RuntimeError(
                f"Eintrag {i} in {pfad_norm}: 'policy' {policy!r} unbekannt "
                f"(erlaubt: {_ERLAUBTE_POLICIES})."
            )
        dom = domain.strip().lower()
        if dom in regeln:
            raise RuntimeError(f"Doppelte domain {dom!r} in {pfad_norm}.")
        regeln[dom] = policy

    _cache[pfad_norm] = regeln
    logger.info("Rausch-Registry geladen: %d Absender aus %s", len(regeln), pfad_norm)
    return regeln


def policy_fuer_domain(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    return lade_regeln().get(domain.strip().lower())
```

- [ ] **Step 5: Test laufen lassen → PASS**

Run: `python -m pytest backend/tests/test_rausch_regel.py -q`
Expected: PASS (11 Tests).

- [ ] **Step 6: Commit**

```bash
git add backend/registry/rausch_absender.yaml backend/intake/rausch_regel.py backend/tests/test_rausch_regel.py
git commit -m "feat(intake): Rausch-Absender-Registry + Regel-Modul (fail-loud)"
```

---

## Task 2: `auto_verwerfen`-Helfer + Route-Refactor

**Files:**
- Create: `backend/intake/verwerfen.py`
- Modify: `backend/routers/intake_routes.py` (`post_verwerfen`, ca. Zeile 454-473)
- Test: `backend/tests/test_auto_verwerfen.py`

**Interfaces:**
- Consumes: nichts aus Task 1.
- Produces: `verwerfen.auto_verwerfen(intake_id: int, *, grund: str, kommentar: str | None = None, benutzer_id: int | None = None) -> str | None` — liefert `verworfen_am` (UTC-ISO) bei Erfolg, `None` wenn übersprungen (bereits verworfen/freigegeben/nicht gefunden). Öffnet die DB-Connection selbst.

- [ ] **Step 1: Failing tests schreiben**

Create `backend/tests/test_auto_verwerfen.py`:

```python
"""Tests fuer backend/intake/verwerfen.py::auto_verwerfen."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(test_id, tmp_dir):
    db_path = os.path.join(tmp_dir, f"av_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    for m in (db_mod, sm_mod):
        importlib.reload(m)
    sm_mod.create_schema()
    sm_mod.run_migrations()
    return db_mod


class TestAutoVerwerfen(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="av_test_")
        self.db = _fresh_db(self._testMethodName, self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _lege_dok_an(self, sha, status="bereit_zur_review"):
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente (sha256, payload_typ, queue_status) "
                "VALUES (?, 'text', ?)", (sha, status),
            )
            return cur.lastrowid

    def test_setzt_soft_delete_und_log_als_system(self):
        from backend.intake.verwerfen import auto_verwerfen
        did = self._lege_dok_an("s1")
        ts = auto_verwerfen(did, grund="rauschen", kommentar="Auto: Test")
        self.assertIsNotNone(ts)
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_grund, verworfen_am, verworfen_von "
                "FROM intake_dokumente WHERE id=?", (did,),
            ).fetchone()
            log = conn.execute(
                "SELECT feld, wert_alt, wert_neu, benutzer_id FROM korrektur_log "
                "WHERE intake_dokument_id=? AND feld='verworfen'", (did,),
            ).fetchone()
        self.assertEqual(row["verworfen_grund"], "rauschen")
        self.assertIsNotNone(row["verworfen_am"])
        self.assertIsNone(row["verworfen_von"])
        self.assertEqual(log["wert_alt"], "bereit_zur_review")
        self.assertIsNone(log["benutzer_id"])
        self.assertEqual(json.loads(log["wert_neu"])["kommentar"], "Auto: Test")

    def test_bereits_verworfenes_wird_uebersprungen(self):
        from backend.intake.verwerfen import auto_verwerfen
        did = self._lege_dok_an("s2")
        self.assertIsNotNone(auto_verwerfen(did, grund="rauschen"))
        self.assertIsNone(auto_verwerfen(did, grund="rauschen"))

    def test_freigegebenes_wird_uebersprungen(self):
        from backend.intake.verwerfen import auto_verwerfen
        did = self._lege_dok_an("s3", status="freigegeben")
        self.assertIsNone(auto_verwerfen(did, grund="rauschen"))
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_am FROM intake_dokumente WHERE id=?", (did,),
            ).fetchone()
        self.assertIsNone(row["verworfen_am"])

    def test_unbekannte_id_none(self):
        from backend.intake.verwerfen import auto_verwerfen
        self.assertIsNone(auto_verwerfen(999999, grund="rauschen"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen → FAIL**

Run: `python -m pytest backend/tests/test_auto_verwerfen.py -q`
Expected: FAIL (`ModuleNotFoundError: backend.intake.verwerfen`).

- [ ] **Step 3: Helfer implementieren**

Create `backend/intake/verwerfen.py`:

```python
"""
Gemeinsamer Soft-Delete-Helfer fuer Intake-Dokumente.

Setzt verworfen_grund/am/von und schreibt eine korrektur_log-Zeile. Wird
sowohl von der manuellen Route (post_verwerfen) als auch von der
automatischen Rausch-Absender-Regel (adapter_imap) genutzt.

verworfen_von = None kennzeichnet die automatische Aussortierung (System).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ..db.database import get_connection

logger = logging.getLogger(__name__)

_VERWERFBARE_STATUS = ("neu", "bereit_zur_review", "pipeline_fehler")


def auto_verwerfen(
    intake_id: int,
    *,
    grund: str,
    kommentar: Optional[str] = None,
    benutzer_id: Optional[int] = None,
) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT queue_status, verworfen_am, klasse, registry_version "
            "FROM intake_dokumente WHERE id=?", (intake_id,),
        ).fetchone()
        if row is None:
            logger.error("auto_verwerfen: ID %s nicht gefunden", intake_id)
            return None
        if row["verworfen_am"] is not None:
            return None
        if row["queue_status"] not in _VERWERFBARE_STATUS:
            return None

        jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE intake_dokumente "
            "SET verworfen_grund=?, verworfen_am=?, verworfen_von=? WHERE id=?",
            (grund, jetzt, benutzer_id, intake_id),
        )
        wert_neu = json.dumps({"grund": grund, "kommentar": kommentar},
                              ensure_ascii=False)
        conn.execute(
            "INSERT INTO korrektur_log "
            "(intake_dokument_id, feld, wert_alt, wert_neu, klasse, "
            " registry_version, benutzer_id) "
            "VALUES (?, 'verworfen', ?, ?, ?, ?, ?)",
            (intake_id, row["queue_status"], wert_neu, row["klasse"],
             row["registry_version"], benutzer_id),
        )
    logger.info("auto_verwerfen: Intake %s grund=%s benutzer=%s",
                intake_id, grund, benutzer_id)
    return jetzt
```

- [ ] **Step 4: Test laufen lassen → PASS**

Run: `python -m pytest backend/tests/test_auto_verwerfen.py -q`
Expected: PASS (4 Tests).

- [ ] **Step 5: `post_verwerfen` auf den Helfer umstellen**

In `backend/routers/intake_routes.py`: oben bei den Imports (nach `from ..intake import split_service`, ca. Zeile 44) ergänzen:

```python
from ..intake.verwerfen import auto_verwerfen
```

Dann den DB-Block in `post_verwerfen` (aktuell die `with get_connection() as conn:`-Passage mit UPDATE + `_log_korrektur`, ca. Zeile 454-468) **ersetzen** durch:

```python
    verworfen_am = auto_verwerfen(
        intake_id, grund=grund, kommentar=kommentar, benutzer_id=benutzer_id,
    )
    if verworfen_am is None:
        return _err("Dokument konnte nicht verworfen werden.", 409)

    logger.info("Intake %s verworfen: grund=%s benutzer=%s",
                 intake_id, grund, benutzer_id)
    return _j({"ok": True, "verworfen": True,
                "verworfen_grund": grund, "verworfen_am": verworfen_am})
```

(Die vorgelagerten Guards — `grund`-Whitelist 400, 404 bei nicht gefunden, 409 bei bereits verworfen, 409 bei falschem Status — bleiben unverändert stehen. Nur der Schreibblock + Return werden ersetzt. Das alte `from datetime import datetime, timezone` / `jetzt = …` in der Funktion entfällt, da `auto_verwerfen` den Zeitstempel liefert.)

- [ ] **Step 6: Regression + neue Tests laufen lassen → PASS**

Run: `python -m pytest backend/tests/test_intake_routes.py -k Verwerfen backend/tests/test_auto_verwerfen.py -q`
Expected: PASS (bestehende `TestVerwerfen`-Tests unverändert grün + 4 neue).

- [ ] **Step 7: Commit**

```bash
git add backend/intake/verwerfen.py backend/tests/test_auto_verwerfen.py backend/routers/intake_routes.py
git commit -m "refactor(intake): auto_verwerfen-Helfer, post_verwerfen nutzt ihn"
```

---

## Task 3: Adapter-Integration (Auto-Aussortierung)

**Files:**
- Modify: `backend/intake/adapter_imap.py` (`verarbeite_email`, Import-Block + Ende der Funktion)
- Modify: `backend/routers/intake_routes.py` (`_VERWERFEN_GRUENDE`, Zeile 401-402)
- Test: `backend/tests/test_rausch_aussortieren_e2e.py`

**Interfaces:**
- Consumes: `rausch_regel.policy_fuer_domain` (Task 1), `verwerfen.auto_verwerfen` (Task 2), bestehendes `_domain_aus_from_header` (adapter_imap).
- Produces: keine neue öffentliche API — Verhaltensänderung in `verarbeite_email`.

- [ ] **Step 1: Failing tests schreiben**

Create `backend/tests/test_rausch_aussortieren_e2e.py`:

```python
"""E2E: adapter_imap.verarbeite_email sortiert Rausch-Absender automatisch aus."""
import os
import sys
import shutil
import tempfile
import unittest
import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(test_id, tmp_dir):
    db_path = os.path.join(tmp_dir, f"rausch_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    for m in (db_mod, sm_mod):
        importlib.reload(m)
    sm_mod.create_schema()
    sm_mod.run_migrations()
    return db_mod


def _minimales_pdf(sig=b""):
    return (
        b"%PDF-1.4\n%" + sig + b"\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n190\n%%EOF\n"
    )


def _email(von, body="Body.", anhaenge=None):
    msg = MIMEMultipart()
    msg["Subject"] = "Test"
    msg["From"] = von
    msg["To"] = "info@anwalt-offenbach.de"
    msg["Date"] = "Mon, 15 Mar 2025 10:30:00 +0100"
    msg["Message-ID"] = f"<{uuid.uuid4().hex}@test.de>"
    msg.attach(MIMEText(body, "plain", "utf-8"))
    for name, daten in (anhaenge or []):
        teil = MIMEApplication(daten, _subtype="pdf")
        teil.add_header("Content-Disposition", "attachment", filename=name)
        msg.attach(teil)
    return msg.as_bytes()


class TestRauschAussortieren(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="rausch_e2e_")
        os.environ["INTAKE_ARCHIV_ROOT"] = self._tmp
        self.db = _fresh_db(self._testMethodName, self._tmp)

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("INTAKE_ARCHIV_ROOT", None)

    def _verworfen(self, intake_id):
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_am, verworfen_grund, verworfen_von "
                "FROM intake_dokumente WHERE id=?", (intake_id,),
            ).fetchone()
        return row

    def test_placetel_ohne_anhang_body_verworfen(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(_email("no-reply@placetel.de"), konto="info")
        row = self._verworfen(res["body"]["intake_dokument_id"])
        self.assertIsNotNone(row["verworfen_am"])
        self.assertEqual(row["verworfen_grund"], "rauschen")
        self.assertIsNone(row["verworfen_von"])

    def test_placetel_mit_fax_body_weg_anhang_bleibt(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(
            _email("no-reply@placetel.de",
                   anhaenge=[("fax.pdf", _minimales_pdf(b"fax1"))]),
            konto="info",
        )
        self.assertIsNotNone(
            self._verworfen(res["body"]["intake_dokument_id"])["verworfen_am"])
        anhang_id = res["anhaenge"][0]["intake_dokument_id"]
        self.assertIsNone(self._verworfen(anhang_id)["verworfen_am"])

    def test_bea_mit_anhang_body_und_anhang_verworfen(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(
            _email("noreply@bea-brak.de",
                   anhaenge=[("info.pdf", _minimales_pdf(b"bea1"))]),
            konto="info",
        )
        self.assertIsNotNone(
            self._verworfen(res["body"]["intake_dokument_id"])["verworfen_am"])
        anhang_id = res["anhaenge"][0]["intake_dokument_id"]
        self.assertIsNotNone(self._verworfen(anhang_id)["verworfen_am"])

    def test_bea_ohne_anhang_body_verworfen(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(_email("noreply@bea-brak.de"), konto="info")
        self.assertIsNotNone(
            self._verworfen(res["body"]["intake_dokument_id"])["verworfen_am"])

    def test_normaler_absender_bleibt(self):
        from backend.intake.adapter_imap import verarbeite_email
        res = verarbeite_email(
            _email("mailer@versicherung.de",
                   anhaenge=[("brief.pdf", _minimales_pdf(b"v1"))]),
            konto="info",
        )
        self.assertIsNone(
            self._verworfen(res["body"]["intake_dokument_id"])["verworfen_am"])
        anhang_id = res["anhaenge"][0]["intake_dokument_id"]
        self.assertIsNone(self._verworfen(anhang_id)["verworfen_am"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen → FAIL**

Run: `python -m pytest backend/tests/test_rausch_aussortieren_e2e.py -q`
Expected: FAIL (Body wird nicht verworfen — `verworfen_am` ist None).

- [ ] **Step 3: Adapter verdrahten**

In `backend/intake/adapter_imap.py` beim Import-Block (nach den `from ._persistenz import …`-Zeilen, ca. Zeile 38) ergänzen:

```python
from .rausch_regel import policy_fuer_domain
from .verwerfen import auto_verwerfen
```

In `verarbeite_email`: die bestehende Domain-Extraktion in eine Variable heben. Aktuell (ca. Zeile 304-306):

```python
    absender_signale = _absender_signale_fuer_domain(
        _domain_aus_from_header(absender)
    )
```

ersetzen durch:

```python
    domain = _domain_aus_from_header(absender)
    absender_signale = _absender_signale_fuer_domain(domain)
```

Direkt **vor** dem `return {`-Statement am Funktionsende (nach der Anhang-Schleife, ca. Zeile 353) einfügen:

```python
    policy = policy_fuer_domain(domain)
    if policy:
        auto_verwerfen(
            body_intake_id, grund="rauschen",
            kommentar=f"Auto: Rausch-Absender ({domain}, {policy})",
        )
        if policy == "komplett":
            for a in anhang_ergebnisse:
                auto_verwerfen(
                    a["intake_dokument_id"], grund="rauschen",
                    kommentar=f"Auto: Rausch-Absender ({domain}, {policy})",
                )
```

- [ ] **Step 4: `rauschen` in die Verwerf-Grund-Whitelist aufnehmen**

In `backend/routers/intake_routes.py` (Zeile 401-402) `_VERWERFEN_GRUENDE` erweitern:

```python
_VERWERFEN_GRUENDE = {"spam", "duplikat", "nicht_relevant",
                       "falsche_kanzlei", "sonstiges", "aufgeteilt", "rauschen"}
```

- [ ] **Step 5: Test laufen lassen → PASS**

Run: `python -m pytest backend/tests/test_rausch_aussortieren_e2e.py backend/tests/test_intake_adapter.py -q`
Expected: PASS (5 neue E2E + bestehende Adapter-Tests unverändert grün).

- [ ] **Step 6: Commit**

```bash
git add backend/intake/adapter_imap.py backend/routers/intake_routes.py backend/tests/test_rausch_aussortieren_e2e.py
git commit -m "feat(intake): Placetel/beA beim Eingang automatisch aussortieren"
```

---

## Task 4: Papierkorb-Backend (Liste + Wiederherstellen)

**Files:**
- Modify: `backend/routers/intake_routes.py` (zwei neue Routen, z.B. nach `post_verwerfen`)
- Test: `backend/tests/test_papierkorb_routes.py`

**Interfaces:**
- Consumes: bestehende Helfer `_j`, `_err`, `_lade_intake`, `_log_korrektur`, `get_connection`, `login_erforderlich`.
- Produces: `GET /intake/papierkorb` → `{"eintraege": [...]}`; `POST /intake/dokument/<id>/wiederherstellen` → `{"ok": True, "wiederhergestellt": True}`.

- [ ] **Step 1: Failing tests schreiben**

Create `backend/tests/test_papierkorb_routes.py`. Nutzt dieselbe App-Client-/Auth-Fixture wie `test_intake_routes.py` — den dortigen Aufbau (Client, `self.headers`, `_lege_intake_pdf_an`) spiegeln:

```python
"""Tests fuer GET /intake/papierkorb + POST /intake/dokument/<id>/wiederherstellen."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Fixture-Aufbau (App-Client + Auth-Header + _lege_intake_pdf_an + frische DB)
# aus test_intake_routes.py uebernehmen. Hier nur die neuen Faelle:
from backend.tests.test_intake_routes import (  # type: ignore
    _TestBasis, _lege_intake_pdf_an,
)
from backend.db.database import get_connection


class TestPapierkorb(_TestBasis):
    def test_verworfenes_erscheint_im_papierkorb_nicht_in_queue(self):
        did = _lege_intake_pdf_an("p1", queue_status="bereit_zur_review")
        self.client.post(f"/intake/dokument/{did}/verwerfen",
                         json={"grund": "rauschen"}, headers=self.headers)

        q = self.client.get("/intake/queue", headers=self.headers).get_json()
        self.assertNotIn(did, [e["id"] for e in q["eintraege"]])

        p = self.client.get("/intake/papierkorb", headers=self.headers).get_json()
        eintrag = next(e for e in p["eintraege"] if e["id"] == did)
        self.assertEqual(eintrag["verworfen_grund"], "rauschen")
        self.assertIsNotNone(eintrag["verworfen_am"])

    def test_wiederherstellen_holt_zurueck_in_queue(self):
        did = _lege_intake_pdf_an("p2", queue_status="bereit_zur_review")
        self.client.post(f"/intake/dokument/{did}/verwerfen",
                         json={"grund": "rauschen"}, headers=self.headers)

        r = self.client.post(f"/intake/dokument/{did}/wiederherstellen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(r.get_json()["wiederhergestellt"])

        with get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_am, verworfen_grund FROM intake_dokumente "
                "WHERE id=?", (did,),
            ).fetchone()
        self.assertIsNone(row["verworfen_am"])
        self.assertIsNone(row["verworfen_grund"])

        q = self.client.get("/intake/queue", headers=self.headers).get_json()
        self.assertIn(did, [e["id"] for e in q["eintraege"]])

    def test_wiederherstellen_nicht_verworfenes_409(self):
        did = _lege_intake_pdf_an("p3", queue_status="bereit_zur_review")
        r = self.client.post(f"/intake/dokument/{did}/wiederherstellen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 409)

    def test_wiederherstellen_unbekannt_404(self):
        r = self.client.post("/intake/dokument/999999/wiederherstellen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
```

> Hinweis für den Implementierer: `test_intake_routes.py` exportiert die Testbasis ggf. unter einem anderen Namen. Vor dem Schreiben `test_intake_routes.py` öffnen und die dortige Basisklasse + den Doc-Anlage-Helfer (`_lege_intake_pdf_an`, akzeptiert `queue_status=`) verwenden; falls keine wiederverwendbare Basisklasse existiert, das `setUp` (frische DB, App-Client, Login → `self.headers`) daraus in dieses File kopieren.

- [ ] **Step 2: Test laufen lassen → FAIL**

Run: `python -m pytest backend/tests/test_papierkorb_routes.py -q`
Expected: FAIL (404 für `/intake/papierkorb` — Route existiert nicht).

- [ ] **Step 3: Routen implementieren**

In `backend/routers/intake_routes.py` nach `post_verwerfen` einfügen:

```python
# ─── GET /intake/papierkorb ───────────────────────────────────────────────────

@intake_bp.route("/papierkorb", methods=["GET"])
@login_erforderlich
def hole_papierkorb():
    """Verworfene Intake-Dokumente, neueste zuerst (Soft-Delete-Papierkorb)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT i.id, i.klasse, i.konfidenz, i.queue_status, "
            "       i.erstellt_am, i.payload_typ, "
            "       i.verworfen_grund, i.verworfen_am, i.verworfen_von, "
            "       z.absender AS absender, z.betreff AS betreff "
            "FROM intake_dokumente i "
            "LEFT JOIN (SELECT intake_dokument_id, MIN(id) AS min_id "
            "           FROM zustellungen GROUP BY intake_dokument_id) ze "
            "  ON ze.intake_dokument_id = i.id "
            "LEFT JOIN zustellungen z ON z.id = ze.min_id "
            "WHERE i.verworfen_am IS NOT NULL "
            "ORDER BY i.verworfen_am DESC "
            "LIMIT 200"
        ).fetchall()

    eintraege = [{
        "id": r["id"],
        "klasse": r["klasse"],
        "konfidenz": r["konfidenz"],
        "queue_status": r["queue_status"],
        "erstellt_am": r["erstellt_am"],
        "payload_typ": r["payload_typ"],
        "verworfen_grund": r["verworfen_grund"],
        "verworfen_am": r["verworfen_am"],
        "verworfen_von": r["verworfen_von"],
        "absender": r["absender"],
        "betreff": r["betreff"],
    } for r in rows]
    return _j({"eintraege": eintraege})


# ─── POST /intake/dokument/<id>/wiederherstellen ──────────────────────────────

@intake_bp.route("/dokument/<int:intake_id>/wiederherstellen", methods=["POST"])
@login_erforderlich
def post_wiederherstellen(intake_id: int):
    """Macht den Soft-Delete rueckgaengig -- Dokument kehrt in die Queue zurueck."""
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    if not dok.get("verworfen_am"):
        return _err("Dokument ist nicht verworfen.", 409)

    benutzer_id = getattr(g, "benutzer_id", None)
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente "
            "SET verworfen_grund=NULL, verworfen_am=NULL, verworfen_von=NULL "
            "WHERE id=?", (intake_id,),
        )
        _log_korrektur(
            conn, intake_id, feld="wiederhergestellt",
            wert_alt=dok.get("verworfen_grund"), wert_neu=None,
            klasse=dok.get("klasse"),
            registry_version=dok.get("registry_version"),
            benutzer_id=benutzer_id,
        )

    logger.info("Intake %s wiederhergestellt: benutzer=%s", intake_id, benutzer_id)
    return _j({"ok": True, "wiederhergestellt": True})
```

- [ ] **Step 4: Test laufen lassen → PASS**

Run: `python -m pytest backend/tests/test_papierkorb_routes.py -q`
Expected: PASS (4 Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_papierkorb_routes.py
git commit -m "feat(intake): Papierkorb-Endpunkte (Liste + Wiederherstellen)"
```

---

## Task 5: Frontend — Papierkorb-Umschalter + Wiederherstellen

**Files:**
- Modify: `frontend/src/api.js` (`apiIntake`, ca. Zeile 1055-1084)
- Modify: `frontend/src/views/ReviewQueueView.jsx`
- Test: `frontend/src/views/ReviewQueueView.papierkorb.test.jsx`

**Interfaces:**
- Consumes: Backend-Endpunkte aus Task 4.
- Produces: exportierte pure Funktion `grundLabel(grund: string) -> string` (für Vitest), UI-Umschalter.

- [ ] **Step 1: API-Methoden ergänzen**

In `frontend/src/api.js` im `apiIntake`-Objekt (vor der schließenden `};`, nach `split:`) ergänzen:

```javascript
  papierkorb:       ()   => request('/intake/papierkorb'),
  wiederherstellen: (id) => request(`/intake/dokument/${id}/wiederherstellen`, {
    method: 'POST',
  }),
```

- [ ] **Step 2: Failing test für `grundLabel` schreiben**

Create `frontend/src/views/ReviewQueueView.papierkorb.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { grundLabel } from "./ReviewQueueView.jsx";

describe("grundLabel (Papierkorb)", () => {
  it("uebersetzt bekannte Gruende", () => {
    expect(grundLabel("rauschen")).toBe("Rauschen");
    expect(grundLabel("spam")).toBe("Spam");
    expect(grundLabel("duplikat")).toBe("Duplikat");
  });

  it("faellt fuer unbekannte Gruende auf den Rohwert zurueck", () => {
    expect(grundLabel("xyz")).toBe("xyz");
  });

  it("liefert leeren String fuer null/undefined", () => {
    expect(grundLabel(null)).toBe("");
    expect(grundLabel(undefined)).toBe("");
  });
});
```

- [ ] **Step 3: Test laufen lassen → FAIL**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.papierkorb.test.jsx`
Expected: FAIL (`grundLabel` nicht exportiert).

- [ ] **Step 4: `grundLabel` implementieren**

In `frontend/src/views/ReviewQueueView.jsx` bei den übrigen Top-Level-Exports (z.B. neben `export function gruppiereQueue`) ergänzen:

```jsx
const GRUND_LABELS = {
  rauschen: "Rauschen",
  spam: "Spam",
  duplikat: "Duplikat",
  nicht_relevant: "Nicht relevant",
  falsche_kanzlei: "Falsche Kanzlei",
  aufgeteilt: "Aufgeteilt",
  sonstiges: "Sonstiges",
};

export function grundLabel(grund) {
  if (!grund) return "";
  return GRUND_LABELS[grund] || grund;
}
```

- [ ] **Step 5: Test laufen lassen → PASS**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.papierkorb.test.jsx`
Expected: PASS (3 Tests).

- [ ] **Step 6: Papierkorb-Ansicht in `ReviewQueueView` verdrahten**

In der `ReviewQueueView`-Komponente (ab Zeile 1244):

(a) State + Loader ergänzen (nach `const [klassen, setKlassen] = useState([]);`):

```jsx
  const [ansicht, setAnsicht] = useState("queue");  // "queue" | "papierkorb"
  const [papierkorb, setPapierkorb] = useState([]);

  const ladePapierkorb = useCallback(async () => {
    try {
      const d = await apiIntake.papierkorb();
      setPapierkorb(d.eintraege || []);
    } catch (e) { setLadeError(e.message); }
  }, []);

  useEffect(() => {
    if (ansicht === "papierkorb") ladePapierkorb();
  }, [ansicht, ladePapierkorb]);

  const doWiederherstellen = useCallback(async (id) => {
    try {
      await apiIntake.wiederherstellen(id);
      ladePapierkorb();
      laden();
    } catch (e) { setLadeError(e.message); }
  }, [ladePapierkorb, laden]);
```

(b) Im Queue-Listen-Header (der `T.navy`-Block, ca. Zeile 1321-1331) unter der Zählzeile einen Umschalter ergänzen:

```jsx
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            {["queue", "papierkorb"].map(a => (
              <button key={a} onClick={() => setAnsicht(a)}
                style={{
                  flex: 1, padding: "4px 8px", fontSize: T.textXs,
                  fontWeight: 600, cursor: "pointer", borderRadius: 4,
                  border: `1px solid ${T.white}40`,
                  background: ansicht === a ? T.white : "transparent",
                  color: ansicht === a ? T.navy : T.white,
                }}>
                {a === "queue" ? "Queue" : "Papierkorb"}
              </button>
            ))}
          </div>
```

(c) Im scrollbaren Listen-Container (ca. Zeile 1333-1357) die Darstellung nach `ansicht` verzweigen. Den bestehenden `gruppiereQueue(queue).map(...)`-Block **nur** rendern, wenn `ansicht === "queue"`, und einen Papierkorb-Zweig ergänzen:

```jsx
          {ansicht === "papierkorb" && !papierkorb.length && (
            <div style={{ padding: 20, color: T.textMuted, fontSize: T.textSm, textAlign: "center" }}>
              Papierkorb leer.
            </div>
          )}
          {ansicht === "papierkorb" && papierkorb.map(item => (
            <div key={item.id} style={{
              padding: "10px 12px", borderBottom: `1px solid ${T.border}`,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{
                  fontSize: T.textXs, fontWeight: 600, color: T.textMuted,
                  border: `1px solid ${T.border}`, borderRadius: 4, padding: "1px 6px",
                }}>{grundLabel(item.verworfen_grund)}</span>
                <div style={{ flex: 1 }} />
                <button onClick={() => doWiederherstellen(item.id)}
                  style={{
                    border: `1px solid ${T.accent}`, background: T.accentPale,
                    color: T.accent, cursor: "pointer", padding: "3px 8px",
                    fontSize: T.textXs, fontWeight: 600, borderRadius: 4,
                  }}>Wiederherstellen</button>
              </div>
              <div style={{ fontSize: T.textSm, color: T.text }}>
                {item.payload_typ === "text" && <span title="E-Mail">📧 </span>}
                <strong>{item.klasse || "unbekannt"}</strong>
              </div>
              {(item.absender || item.betreff) && (
                <div style={{ fontSize: T.textXs, color: T.textMuted, marginTop: 2 }}>
                  {item.absender || ""}{item.betreff ? ` · ${item.betreff}` : ""}
                </div>
              )}
              <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 2 }}>
                #{item.id} · verworfen {item.verworfen_am}
              </div>
            </div>
          ))}
```

Den bestehenden `gruppiereQueue(queue).map(...)`-Block in `{ansicht === "queue" && ( … )}` einfassen (das `!queue.length`-Leer-Hinweis-JSX ebenfalls nur im Queue-Zweig zeigen).

- [ ] **Step 7: Frontend-Suite laufen lassen → PASS**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS (neue `grundLabel`-Tests grün, bestehende Suite unverändert, Build grün).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api.js frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.papierkorb.test.jsx
git commit -m "feat(review): Papierkorb-Ansicht mit Wiederherstellen"
```

---

## Task 6: Verifikation im laufenden DEV-System

**Files:** keine (manuelle/gescriptete Verifikation).

- [ ] **Step 1: Voller Backend-Lauf (keine neuen Failures)**

Run: `python -m pytest backend/tests/ -q`
Expected: Die neuen Tests grün; keine **neuen** Failures ggü. der Baseline (bekannte Alt-Cluster `test_modul2/3/4/7`, `sv_portal`, `prd27` dürfen wie gehabt rot sein). Bei Unsicherheit denselben Lauf auf `main` (bzw. via `git stash`) gegenprüfen.

- [ ] **Step 2: Registry lädt beim App-Start (fail-loud verifizieren)**

Run: `python -c "from backend.intake.rausch_regel import lade_regeln; print(lade_regeln())"`
Expected: `{'placetel.de': 'nur_body', 'bea-brak.de': 'komplett'}`.

- [ ] **Step 3: DEV-Smoke (echte App)**

Nutze die verify-/run-Skill bzw. den laufenden DEV-Container:
- Eine Test-Mail von `no-reply@placetel.de` **ohne** Anhang einspeisen → Body erscheint **nicht** in `GET /intake/queue`, **erscheint** in `GET /intake/papierkorb` (Grund `rauschen`, `verworfen_von` NULL).
- Eine `no-reply@placetel.de`-Mail **mit** PDF → nur das PDF in der Queue, Body im Papierkorb.
- `noreply@bea-brak.de` mit PDF → Body **und** PDF im Papierkorb.
- Im UI „Papierkorb" öffnen → „Wiederherstellen" bei einem Eintrag → verschwindet aus dem Papierkorb, taucht (nach Worker-Lauf) wieder in der Queue auf.
- Testdaten rückstandsfrei aufräumen.

- [ ] **Step 4: Abschluss-Review + TODO-Eintrag**

Superpowers:requesting-code-review (Whole-Feature). Danach `docs/TODO.md` Punkt 1 (Filterregeln) als erledigt/umgesetzt markieren mit Verweis auf Spec + Plan, und ggf. Memory `[[unfallakten-pipeline-v7]]` fortschreiben.

---

## Self-Review

**Spec coverage:**
- Auto-Aussortieren beim Eingang → Task 3. ✓
- Per-Dokument-Policy (`nur_body`/`komplett`) → Task 1 (Regel) + Task 3 (Anwendung). ✓
- Erkennung an Absender-Domain → Task 3 nutzt `_domain_aus_from_header`. ✓
- YAML-Registry fail-loud → Task 1. ✓
- Kein Betreff-Muster / kein SPF-DKIM-Gate → nicht implementiert (bewusst). ✓
- `auto_verwerfen`-Helfer (System, `verworfen_von=NULL`, Guard) + Route-Reuse → Task 2. ✓
- `_VERWERFEN_GRUENDE += rauschen`, keine Migration → Task 3. ✓
- Papierkorb: `GET /intake/papierkorb` + `POST …/wiederherstellen` → Task 4. ✓
- Frontend Umschalter + Wiederherstellen → Task 5. ✓
- Auto-verworfene `neu`-Docs laufen harmlos durch den Worker → keine Code-Änderung nötig, in Spec dokumentiert. ✓

**Placeholder scan:** Keine TBD/TODO in Code-Schritten; jeder Code-Schritt zeigt vollständigen Code. Einzige „nachschlagen"-Stelle: Task 4 Testbasis-Import aus `test_intake_routes.py` — dort explizit als Anweisung mit Fallback (setUp kopieren) beschrieben, kein Platzhalter im Produktivcode.

**Type consistency:** `policy_fuer_domain(domain) -> str|None` (Task 1) wird in Task 3 mit `domain` (aus `_domain_aus_from_header`) aufgerufen. `auto_verwerfen(...) -> str|None` (Task 2) wird in Task 3 (Rückgabe ignoriert) und in `post_verwerfen` (Task 2, `None`→409) konsistent genutzt. `grundLabel(grund)->string` (Task 5) konsistent in Test + Komponente. Endpunkt-Namen `papierkorb`/`wiederherstellen` in api.js (Task 5) == Routen (Task 4).
