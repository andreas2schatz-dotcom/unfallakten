# Fragebogen-Feld-Übernahme bei Freigabe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Beim Freigeben eines Unfallbogens die geparsten Felder (Mandant/Gegner/Unfall/Personenschaden) als editierbare, bestätigbare Vorschau in die Akte übernehmen.

**Architecture:** Neues Service-Modul `backend/services/fragebogen_uebernahme.py` kapselt Vorschau-Berechnung und fill-empty-/overwrite-Schreiben. `intake_routes.py` bekommt ein `ist_fragebogen`-Flag, einen Vorschau-Endpoint und einen Übernahme-Aufruf in `post_freigabe`. Voraussetzung: Text-Dokument-Freigabe wird repariert (Payload-Materialisierung). Frontend zeigt die editierbare Übernahme-Sektion im Freigabe-Dialog.

**Tech Stack:** Python 3 / Flask / SQLite (`get_connection`), React (Vite) / Vitest, unittest.

## Global Constraints

- **RA-MICRO ist read-only** — ausschließlich in SQLite schreiben.
- **Menschliche Freigabe = einzige Schreib-Op Richtung Akte.** Diese Übernahme dockt genau dort an.
- **Alt-Pfade unter `INTAKE_REVIEW_PFLICHT=false` unangetastet** lassen; die alten `_ergaenze_*` in `import_service.py` bleiben eingefroren (Rollback-Anker).
- **TDD**, keine unnötigen Abstraktionen, **Deutsch** (Code-Kommentare nur bei nicht-offensichtlichem Verhalten).
- **Keine DB-Migration** — alle Zieltabellen (`beteiligte`, `unfallakte`, `unfalldetails`, `personenschaden`) existieren.
- Tests im **Vordergrund** laufen lassen, committen, dann melden. Nach Signaturänderungen die **volle** Suite, nicht nur Golden.
- Spec: `docs/superpowers/specs/2026-07-14-fragebogen-feld-uebernahme-design.md`.

---

## Feld-Mapping (verbindlich, Referenz für alle Tasks)

Bogen-JSON (aus `parse_fragebogen_anhang`) → Akten-Spalte:

**Mandant** → `beteiligte` (rolle='mandant'):
`name→name`, `vorname→vorname`, `strasse→anschrift`, `plz→plz`, `ort→ort`, `email→email`, `telefon→telefon`, `iban→iban`, `vorsteuerabzug=='ja'→vorsteuer='Y'` (sonst kein Feld).

**Gegner** → `beteiligte` (rolle='gegner'):
`fahrer→name`, `fahrzeug.kennzeichen→kfz_kennzeichen`, `fahrzeug.fabrikat→notizen`, `versicherung.name→versicherung`, `versicherung.nummer→vers_nr`, `versicherung.schadennummer→schaden_nr`.

**Unfall** → `unfallakte`: `datum→unfalldatum`, `ort→unfallort`; → `unfalldetails`: `schilderung→schilderung` (mit `[Uhrzeit: <zeit>] `-Präfix, wenn `zeit` gesetzt), `polizei.aktenzeichen→ermittlungsakte_az`.

**Personenschaden** → `personenschaden`:
`verletzter.geburtsdatum→geburtsdatum`, `verletzungen→verletzungen_text`, `krankenhaus.name→krankenhaus_name` (+`krankenhaus_aufenthalt=1`), `krankenhaus.von→krankenhaus_von`, `krankenhaus.bis→krankenhaus_bis`, `hauskrank.von→krank_von` (+`krankgeschrieben=1`), `hauskrank.bis→krank_bis`.

---

## Task 1: Text-Dokument-Freigabe reparieren

`post_freigabe` bricht heute für Text-Dokumente (Fragebogen/E-Mail-Body, `payload_typ='text'`, keine Arbeitskopie) mit HTTP 500 ab, weil `output_adapter.schreibe_dokument` eine Datei-Arbeitskopie verlangt. Diese Task materialisiert den `structured_payload` beim Freigeben zu einer Datei.

**Files:**
- Modify: `backend/routers/intake_routes.py` (Imports oben; neuer Helper `_sichere_text_arbeitskopie`; Aufruf in `post_freigabe` vor `schreibe_dokument`)
- Test: `backend/tests/test_fragebogen_freigabe_e2e.py` (neu; wird in Task 6 erweitert)

**Interfaces:**
- Consumes: `output_adapter.schreibe_dokument(intake_dok, akte_az, freigegeben_von)` (unverändert).
- Produces: `_sichere_text_arbeitskopie(dok: dict) -> Optional[str]` — Pfad einer materialisierten Arbeitskopie für Text-Dokumente, sonst der vorhandene Pfad bzw. `None`.

- [ ] **Step 1: Write the failing test**

Neue Datei `backend/tests/test_fragebogen_freigabe_e2e.py` (Harness nach Vorbild `test_n08_baseline_freigabe.py`):

```python
"""
Fragebogen-Feld-Uebernahme bei Freigabe -- End-to-End.

Task 1: Text-Dokument (Fragebogen) laesst sich freigeben -> dokumente-Zeile
entsteht (Materialisierung der Arbeitskopie). Weitere Tests (Feld-Uebernahme)
kommen in Task 6.
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

FRAGEBOGEN_JSON = {
    "meta": {"formular": "unfallbogen", "version": "2.1", "aktenzeichen": "44/22"},
    "mandant": {"name": "Riccio", "vorname": "Marco", "telefon": "069 8402271"},
    "gegner": {"fahrer": "Khaniani",
               "fahrzeug": {"kennzeichen": "OF-KH 1234"},
               "versicherung": {"name": "HUK-Coburg"}},
    "unfall": {"datum": "2026-03-12", "ort": "Kaiserstrasse Offenbach"},
    "personenschaden": None,
}


class _FragebogenFreigabeBasis(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="frb_")
        os.environ["DB_PATH"] = os.path.join(self._tmp, "unfallakten.db")
        os.environ["UPLOAD_DIR"] = os.path.join(self._tmp, "uploads")
        os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)

        import backend.db.database as db_mod
        import backend.models.benutzer as ben_mod
        import backend.models.akte as akte_mod
        import backend.models.dokument as dok_mod
        import backend.auth.jwt_handler as jwt_mod
        import backend.auth.middleware as mw_mod
        import backend.auth.service as svc_mod
        import backend.routers.auth_routes as routes_mod
        import backend.app as app_mod
        for m in (db_mod, ben_mod, akte_mod, dok_mod, jwt_mod, mw_mod,
                  svc_mod, routes_mod, app_mod):
            importlib.reload(m)

        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, status) VALUES ('44/22', 'offen')")

    def tearDown(self):
        import shutil
        for var in ("DB_PATH", "UPLOAD_DIR"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def _lege_fragebogen_intake_an(self, payload=None, sha="frb1"):
        from backend.db.database import get_connection
        roh = json.dumps(payload or FRAGEBOGEN_JSON, ensure_ascii=False)
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status, klasse, parse_json) "
                "VALUES (?, 'text', ?, 'bereit_zur_review', 'sonstiges', '{}')",
                ((sha * 64)[:64], roh),
            )
            return cur.lastrowid


class TestTextFreigabeLegtDokumentAn(_FragebogenFreigabeBasis):
    def test_text_dokument_freigabe_erzeugt_dokumente_zeile(self):
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe",
                             json={"akte_az": "44/22"}, headers=headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        from backend.db.database import get_connection
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'").fetchone()[0]
        self.assertEqual(n, 1, "Freigabe eines Text-Dokuments legt eine dokumente-Zeile an")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_fragebogen_freigabe_e2e.py -v`
Expected: FAIL — Freigabe liefert 500 „Arbeitskopie fehlt" (dokumente bleibt 0).

- [ ] **Step 3: Add imports at top of `intake_routes.py`**

Nach `import logging` (Zeile ~32) ergänzen:

```python
import os
from pathlib import Path
```

- [ ] **Step 4: Add the helper `_sichere_text_arbeitskopie`**

In `intake_routes.py` direkt vor `def post_freigabe` einfügen:

```python
def _upload_basis() -> Path:
    default = Path(__file__).resolve().parent.parent / "uploads"
    return Path(os.environ.get("UPLOAD_DIR") or default)


def _sichere_text_arbeitskopie(dok: Dict[str, Any]) -> Optional[str]:
    """Materialisiert den Payload eines Text-Dokuments als Datei-Arbeitskopie.

    output_adapter.schreibe_dokument verlangt eine Datei; Text-Dokumente
    (Fragebogen/E-Mail-Body) haben keine. Gibt den (vorhandenen oder neu
    geschriebenen) Pfad zurueck, oder None, wenn es kein Text-Dokument ist.
    """
    if dok.get("payload_typ") != "text":
        return None
    vorhanden = dok.get("arbeitskopie_pfad")
    if vorhanden and os.path.isfile(vorhanden):
        return vorhanden
    inhalt = dok.get("structured_payload") or ""
    ziel_dir = _upload_basis() / "intake_text"
    ziel_dir.mkdir(parents=True, exist_ok=True)
    pfad = ziel_dir / f"dok_{dok['id']}.txt"
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)
```

- [ ] **Step 5: Wire it into `post_freigabe`**

In `post_freigabe`, den `schreibe_dokument`-Block ersetzen. Vorher:

```python
    try:
        dokument_id = schreibe_dokument(dok, akte_az,
                                         freigegeben_von=benutzer_id)
```

Nachher:

```python
    text_pfad = _sichere_text_arbeitskopie(dok)
    if text_pfad:
        dok = {**dok, "arbeitskopie_pfad": text_pfad}
    try:
        dokument_id = schreibe_dokument(dok, akte_az,
                                         freigegeben_von=benutzer_id)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_fragebogen_freigabe_e2e.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_fragebogen_freigabe_e2e.py
git commit -m "fix(intake): Text-Dokument-Freigabe -- Payload als Arbeitskopie materialisieren"
```

---

## Task 2: Service — Erkennung + Mandant/Gegner (beteiligte)

**Files:**
- Create: `backend/services/fragebogen_uebernahme.py`
- Test: `backend/tests/test_fragebogen_uebernahme.py` (neu)

**Interfaces:**
- Consumes: `backend.email_import.fragebogen_parser.parse_fragebogen_anhang(bytes) -> dict|None`; `backend.db.database.get_connection`.
- Produces:
  - `parse_fragebogen_payload(structured_payload: Optional[str]) -> Optional[dict]`
  - `_norm(v) -> str`
  - `_vorschau_felder(geparste: list[tuple], akte_werte: dict) -> list[dict]` (feld_dict: `{"feld","label","geparst","akte_wert","ist_leer","konflikt"}`)
  - `_geparst_mandant(m: dict) -> list[tuple]`, `_akte_mandant(conn, akte_az) -> dict`
  - `_geparst_gegner(g: dict) -> list[tuple]`, `_akte_gegner(conn, akte_az) -> dict`
  - `_schreibe_beteiligte(conn, akte_az, rolle, aenderungen: dict) -> None`

- [ ] **Step 1: Write the failing test**

Neue Datei `backend/tests/test_fragebogen_uebernahme.py`:

```python
"""Service fragebogen_uebernahme -- Vorschau + Schreiben (Task 2-4)."""
import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _ServiceBasis(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="frbsvc_")
        os.environ["DB_PATH"] = os.path.join(self._tmp, "unfallakten.db")
        os.environ["UPLOAD_DIR"] = os.path.join(self._tmp, "uploads")

        import backend.db.database as db_mod
        import backend.models.akte as akte_mod
        import backend.app as app_mod
        for m in (db_mod, akte_mod, app_mod):
            importlib.reload(m)
        app_mod.erstelle_app({"TESTING": True})  # legt Schema an

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az, status) VALUES ('44/22', 'offen')")

    def tearDown(self):
        import shutil
        for var in ("DB_PATH", "UPLOAD_DIR"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestErkennung(_ServiceBasis):
    def test_parse_erkennt_unfallbogen(self):
        from backend.services.fragebogen_uebernahme import parse_fragebogen_payload
        roh = '{"meta":{"formular":"unfallbogen","version":"2.1"},"mandant":{"name":"X"}}'
        parsed = parse_fragebogen_payload(roh)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["mandant"]["name"], "X")

    def test_parse_lehnt_fremdes_json_ab(self):
        from backend.services.fragebogen_uebernahme import parse_fragebogen_payload
        self.assertIsNone(parse_fragebogen_payload('{"meta":{"formular":"rechnung"}}'))
        self.assertIsNone(parse_fragebogen_payload(None))


class TestVorschauBeteiligte(_ServiceBasis):
    def test_mandant_leer_und_konflikt(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import (
            _geparst_mandant, _akte_mandant, _vorschau_felder)
        with get_connection() as conn:
            conn.execute("INSERT INTO beteiligte (akte_id, rolle, name, ort) "
                         "VALUES ('44/22', 'mandant', 'Riccio', 'Offenbach')")
            akte = _akte_mandant(conn, "44/22")
        felder = _vorschau_felder(
            _geparst_mandant({"name": "Riccio", "ort": "Neu-Isenburg",
                              "telefon": "069 1"}),
            akte)
        nach_feld = {f["feld"]: f for f in felder}
        self.assertTrue(nach_feld["telefon"]["ist_leer"])
        self.assertFalse(nach_feld["telefon"]["konflikt"])
        self.assertFalse(nach_feld["name"]["ist_leer"])
        self.assertFalse(nach_feld["name"]["konflikt"])   # gleich
        self.assertTrue(nach_feld["ort"]["konflikt"])     # Offenbach != Neu-Isenburg
        self.assertNotIn("iban", nach_feld)               # kein geparster Wert -> nicht gelistet

    def test_gegner_ohne_akte_zeile_alles_leer(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import (
            _geparst_gegner, _akte_gegner, _vorschau_felder)
        with get_connection() as conn:
            akte = _akte_gegner(conn, "44/22")
        felder = _vorschau_felder(
            _geparst_gegner({"fahrer": "K", "versicherung": {"name": "HUK"}}), akte)
        self.assertTrue(all(f["ist_leer"] for f in felder))


class TestSchreibeBeteiligte(_ServiceBasis):
    def test_insert_und_fill_empty(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_beteiligte
        with get_connection() as conn:
            _schreibe_beteiligte(conn, "44/22", "mandant",
                                 {"name": "Riccio", "telefon": "069 1"})
            row = conn.execute("SELECT name, telefon FROM beteiligte "
                               "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
        self.assertEqual(row["name"], "Riccio")
        self.assertEqual(row["telefon"], "069 1")

    def test_update_ueberschreibt_gesetzte_spalte(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_beteiligte
        with get_connection() as conn:
            conn.execute("INSERT INTO beteiligte (akte_id, rolle, ort) "
                         "VALUES ('44/22', 'mandant', 'Offenbach')")
            _schreibe_beteiligte(conn, "44/22", "mandant", {"ort": "Neu-Isenburg"})
            row = conn.execute("SELECT ort FROM beteiligte "
                               "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
        self.assertEqual(row["ort"], "Neu-Isenburg")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_fragebogen_uebernahme.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.services.fragebogen_uebernahme`.

- [ ] **Step 3: Create the service module (recognition + beteiligte)**

Neue Datei `backend/services/fragebogen_uebernahme.py`:

```python
"""
Fragebogen-Feld-Uebernahme bei Freigabe.

Einzige sanktionierte Stelle, die geparste Fragebogen-Felder in Akten-
Stammdaten (beteiligte / unfallakte / unfalldetails / personenschaden)
schreibt. Ausgeloest ausschliesslich durch die manuelle Review-Freigabe.

Semantik: leeres Aktenfeld -> fuellen; abweichendes Feld -> nur ueberschreiben,
wenn der bestaetigte Wert vom aktuellen Akten-Wert abweicht. Deckungsgleiche
oder unveraenderte Felder bleiben unangetastet.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..db.database import get_connection

logger = logging.getLogger(__name__)

ABSCHNITTE: Tuple[str, ...] = ("mandant", "gegner", "unfall", "personenschaden")
_LABELS = {
    "mandant": "Mandant",
    "gegner": "Gegner & Versicherung",
    "unfall": "Unfall",
    "personenschaden": "Personenschaden",
}


def parse_fragebogen_payload(structured_payload: Optional[str]) -> Optional[dict]:
    """Re-parst das rohe Fragebogen-JSON (intake_dokumente.structured_payload).

    Gibt das strukturierte Dict (mandant/gegner/unfall/personenschaden) zurueck
    oder None, wenn es kein gueltiger Unfallbogen ist.
    """
    if not structured_payload:
        return None
    from ..email_import.fragebogen_parser import parse_fragebogen_anhang
    return parse_fragebogen_anhang(structured_payload.encode("utf-8"))


def _norm(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _vorschau_felder(geparste: List[Tuple[str, str, Any]],
                     akte_werte: Dict[str, Any]) -> List[dict]:
    """Baut die Feldliste fuer die Vorschau. Nur Felder mit nichtleerem
    geparstem Wert werden gelistet."""
    out: List[dict] = []
    for feld, label, wert in geparste:
        if not _norm(wert):
            continue
        akte = akte_werte.get(feld)
        leer = _norm(akte) == ""
        konflikt = (not leer) and _norm(akte).casefold() != _norm(wert).casefold()
        out.append({
            "feld": feld, "label": label, "geparst": wert,
            "akte_wert": akte, "ist_leer": leer, "konflikt": konflikt,
        })
    return out


# ── Mandant / Gegner (beteiligte) ────────────────────────────────────────────

def _geparst_mandant(m: dict) -> List[Tuple[str, str, Any]]:
    vs = "Y" if (m.get("vorsteuerabzug") == "ja") else None
    return [
        ("name", "Name", m.get("name")),
        ("vorname", "Vorname", m.get("vorname")),
        ("anschrift", "Straße", m.get("strasse")),
        ("plz", "PLZ", m.get("plz")),
        ("ort", "Ort", m.get("ort")),
        ("email", "E-Mail", m.get("email")),
        ("telefon", "Telefon", m.get("telefon")),
        ("iban", "IBAN", m.get("iban")),
        ("vorsteuer", "Vorsteuer", vs),
    ]


def _akte_mandant(conn, akte_az: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT name, vorname, anschrift, plz, ort, email, telefon, iban, vorsteuer "
        "FROM beteiligte WHERE akte_id=? AND rolle='mandant'", (akte_az,)).fetchone()
    return dict(row) if row else {}


def _geparst_gegner(g: dict) -> List[Tuple[str, str, Any]]:
    fz = g.get("fahrzeug") or {}
    ver = g.get("versicherung") or {}
    return [
        ("name", "Fahrer", g.get("fahrer")),
        ("kfz_kennzeichen", "Kennzeichen", fz.get("kennzeichen")),
        ("notizen", "Fabrikat", fz.get("fabrikat")),
        ("versicherung", "Versicherung", ver.get("name")),
        ("vers_nr", "Vers.-Nr.", ver.get("nummer")),
        ("schaden_nr", "Schaden-Nr.", ver.get("schadennummer")),
    ]


def _akte_gegner(conn, akte_az: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT name, kfz_kennzeichen, notizen, versicherung, vers_nr, schaden_nr "
        "FROM beteiligte WHERE akte_id=? AND rolle='gegner'", (akte_az,)).fetchone()
    return dict(row) if row else {}


def _schreibe_beteiligte(conn, akte_az: str, rolle: str,
                         aenderungen: Dict[str, Any]) -> None:
    if not aenderungen:
        return
    row = conn.execute("SELECT id FROM beteiligte WHERE akte_id=? AND rolle=?",
                       (akte_az, rolle)).fetchone()
    if row is None:
        # beteiligte.name ist NOT NULL -> beim Neuanlegen ohne Namen leer setzen.
        spalten = dict(aenderungen)
        spalten.setdefault("name", "")
        cols = ["akte_id", "rolle"] + list(spalten)
        werte = [akte_az, rolle] + list(spalten.values())
        platz = ", ".join(["?"] * len(cols))
        conn.execute(f"INSERT INTO beteiligte ({', '.join(cols)}) VALUES ({platz})",
                     werte)
    else:
        setzt = ", ".join(f"{k}=?" for k in aenderungen)
        conn.execute(f"UPDATE beteiligte SET {setzt} WHERE id=?",
                     list(aenderungen.values()) + [row["id"]])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_fragebogen_uebernahme.py -v`
Expected: PASS (5 Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/fragebogen_uebernahme.py backend/tests/test_fragebogen_uebernahme.py
git commit -m "feat(intake): fragebogen_uebernahme -- Erkennung + Mandant/Gegner-Vorschau/Schreiben"
```

---

## Task 3: Service — Unfall + Personenschaden

**Files:**
- Modify: `backend/services/fragebogen_uebernahme.py` (Unfall- und Personenschaden-Funktionen anhängen)
- Test: `backend/tests/test_fragebogen_uebernahme.py` (Tests ergänzen)

**Interfaces:**
- Produces:
  - `_geparst_unfall(u: dict) -> list[tuple]`, `_akte_unfall(conn, akte_az) -> dict`, `_schreibe_unfall(conn, akte_az, aenderungen: dict) -> None`
  - `_geparst_personenschaden(ps: dict) -> list[tuple]`, `_akte_personenschaden(conn, akte_az) -> dict`, `_schreibe_personenschaden(conn, akte_az, aenderungen: dict) -> None`

- [ ] **Step 1: Write the failing test**

In `test_fragebogen_uebernahme.py` ergänzen:

```python
class TestVorschauUnfall(_ServiceBasis):
    def test_schilderung_mit_uhrzeit_prefix(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import (
            _geparst_unfall, _akte_unfall, _vorschau_felder)
        with get_connection() as conn:
            akte = _akte_unfall(conn, "44/22")
        felder = _vorschau_felder(
            _geparst_unfall({"datum": "2026-03-12", "ort": "OF",
                             "zeit": "14:20", "schilderung": "Auffahrunfall"}), akte)
        nach = {f["feld"]: f for f in felder}
        self.assertEqual(nach["schilderung"]["geparst"], "[Uhrzeit: 14:20] Auffahrunfall")
        self.assertTrue(nach["unfalldatum"]["ist_leer"])

    def test_schreibe_unfall_beide_tabellen(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_unfall
        with get_connection() as conn:
            _schreibe_unfall(conn, "44/22",
                             {"unfalldatum": "2026-03-12", "schilderung": "X"})
            a = conn.execute("SELECT unfalldatum FROM unfallakte WHERE az='44/22'").fetchone()
            d = conn.execute("SELECT schilderung FROM unfalldetails WHERE akte_id='44/22'").fetchone()
        self.assertEqual(a["unfalldatum"], "2026-03-12")
        self.assertEqual(d["schilderung"], "X")


class TestVorschauPersonenschaden(_ServiceBasis):
    def test_schreibe_setzt_abgeleitete_flags(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import _schreibe_personenschaden
        with get_connection() as conn:
            _schreibe_personenschaden(conn, "44/22",
                                      {"krankenhaus_name": "Klinikum", "krank_von": "2026-03-13"})
            row = conn.execute(
                "SELECT krankenhaus_name, krankenhaus_aufenthalt, krankgeschrieben "
                "FROM personenschaden WHERE akte_id='44/22'").fetchone()
        self.assertEqual(row["krankenhaus_name"], "Klinikum")
        self.assertEqual(row["krankenhaus_aufenthalt"], 1)
        self.assertEqual(row["krankgeschrieben"], 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_fragebogen_uebernahme.py -k "Unfall or Personenschaden" -v`
Expected: FAIL — `ImportError`/`AttributeError` (`_geparst_unfall` fehlt).

- [ ] **Step 3: Append implementation to the service module**

Ans Ende von `backend/services/fragebogen_uebernahme.py`:

```python
# ── Unfall (unfallakte + unfalldetails) ──────────────────────────────────────

def _geparst_unfall(u: dict) -> List[Tuple[str, str, Any]]:
    zeit = u.get("zeit")
    schild = u.get("schilderung")
    if zeit:
        schild_final = f"[Uhrzeit: {zeit}] {schild}" if schild else f"[Uhrzeit: {zeit}]"
    else:
        schild_final = schild
    pol = (u.get("polizei") or {}).get("aktenzeichen")
    return [
        ("unfalldatum", "Unfalldatum", u.get("datum")),
        ("unfallort", "Unfallort", u.get("ort")),
        ("schilderung", "Schilderung", schild_final),
        ("ermittlungsakte_az", "Ermittlungsakte-AZ", pol),
    ]


def _akte_unfall(conn, akte_az: str) -> Dict[str, Any]:
    a = conn.execute("SELECT unfalldatum, unfallort FROM unfallakte WHERE az=?",
                     (akte_az,)).fetchone()
    d = conn.execute("SELECT schilderung, ermittlungsakte_az FROM unfalldetails "
                     "WHERE akte_id=?", (akte_az,)).fetchone()
    return {
        "unfalldatum": a["unfalldatum"] if a else None,
        "unfallort": a["unfallort"] if a else None,
        "schilderung": d["schilderung"] if d else None,
        "ermittlungsakte_az": d["ermittlungsakte_az"] if d else None,
    }


def _schreibe_unfall(conn, akte_az: str, aenderungen: Dict[str, Any]) -> None:
    akte_cols = {k: v for k, v in aenderungen.items()
                 if k in ("unfalldatum", "unfallort")}
    det_cols = {k: v for k, v in aenderungen.items()
                if k in ("schilderung", "ermittlungsakte_az")}
    if akte_cols:
        setzt = ", ".join(f"{k}=?" for k in akte_cols)
        conn.execute(f"UPDATE unfallakte SET {setzt} WHERE az=?",
                     list(akte_cols.values()) + [akte_az])
    if det_cols:
        row = conn.execute("SELECT id FROM unfalldetails WHERE akte_id=?",
                           (akte_az,)).fetchone()
        if row is None:
            cols = ["akte_id"] + list(det_cols)
            platz = ", ".join(["?"] * len(cols))
            conn.execute(f"INSERT INTO unfalldetails ({', '.join(cols)}) VALUES ({platz})",
                         [akte_az] + list(det_cols.values()))
        else:
            setzt = ", ".join(f"{k}=?" for k in det_cols)
            conn.execute(f"UPDATE unfalldetails SET {setzt} WHERE id=?",
                         list(det_cols.values()) + [row["id"]])


# ── Personenschaden ──────────────────────────────────────────────────────────

def _geparst_personenschaden(ps: dict) -> List[Tuple[str, str, Any]]:
    ps = ps or {}
    verletzter = ps.get("verletzter") or {}
    kh = ps.get("krankenhaus") or {}
    hk = ps.get("hauskrank") or {}
    return [
        ("geburtsdatum", "Geburtsdatum", verletzter.get("geburtsdatum")),
        ("verletzungen_text", "Verletzungen", ps.get("verletzungen")),
        ("krankenhaus_name", "Krankenhaus", kh.get("name")),
        ("krankenhaus_von", "KH von", kh.get("von")),
        ("krankenhaus_bis", "KH bis", kh.get("bis")),
        ("krank_von", "AU von", hk.get("von")),
        ("krank_bis", "AU bis", hk.get("bis")),
    ]


def _akte_personenschaden(conn, akte_az: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT geburtsdatum, verletzungen_text, krankenhaus_name, "
        "       krankenhaus_von, krankenhaus_bis, krank_von, krank_bis "
        "FROM personenschaden WHERE akte_id=?", (akte_az,)).fetchone()
    return dict(row) if row else {}


def _schreibe_personenschaden(conn, akte_az: str, aenderungen: Dict[str, Any]) -> None:
    voll = dict(aenderungen)
    if "krankenhaus_name" in voll:
        voll["krankenhaus_aufenthalt"] = 1
    if "krank_von" in voll:
        voll["krankgeschrieben"] = 1
    row = conn.execute("SELECT id FROM personenschaden WHERE akte_id=?",
                       (akte_az,)).fetchone()
    if row is None:
        cols = ["akte_id"] + list(voll)
        platz = ", ".join(["?"] * len(cols))
        conn.execute(f"INSERT INTO personenschaden ({', '.join(cols)}) VALUES ({platz})",
                     [akte_az] + list(voll.values()))
    else:
        setzt = ", ".join(f"{k}=?" for k in voll)
        conn.execute(f"UPDATE personenschaden SET {setzt} WHERE id=?",
                     list(voll.values()) + [row["id"]])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_fragebogen_uebernahme.py -v`
Expected: PASS (alle bisherigen + 3 neue).

- [ ] **Step 5: Commit**

```bash
git add backend/services/fragebogen_uebernahme.py backend/tests/test_fragebogen_uebernahme.py
git commit -m "feat(intake): fragebogen_uebernahme -- Unfall + Personenschaden"
```

---

## Task 4: Service — Dispatcher `baue_vorschau` / `vorschau_liste` / `uebernehme`

**Files:**
- Modify: `backend/services/fragebogen_uebernahme.py`
- Test: `backend/tests/test_fragebogen_uebernahme.py`

**Interfaces:**
- Consumes: alle Section-Funktionen aus Task 2/3.
- Produces:
  - `baue_vorschau(akte_az: str, parsed: dict) -> dict` — `{sec: {"felder": [...]}}` für alle `ABSCHNITTE`.
  - `vorschau_liste(akte_az: str, parsed: dict) -> list` — `[{"key","label","felder"}]` in `ABSCHNITTE`-Reihenfolge.
  - `uebernehme(akte_az: str, werte: dict, aktive_abschnitte: list) -> dict` — `{"geschrieben":[...],"uebersprungen":[...],"fehler":[...]}`.

- [ ] **Step 1: Write the failing test**

In `test_fragebogen_uebernahme.py` ergänzen:

```python
_PARSED = {
    "mandant": {"name": "Riccio", "ort": "Neu-Isenburg", "telefon": "069 1"},
    "gegner": {"fahrer": "Khaniani"},
    "unfall": {"datum": "2026-03-12"},
    "personenschaden": None,
}


class TestDispatcher(_ServiceBasis):
    def test_baue_vorschau_alle_abschnitte(self):
        from backend.services.fragebogen_uebernahme import baue_vorschau, ABSCHNITTE
        v = baue_vorschau("44/22", _PARSED)
        self.assertEqual(set(v), set(ABSCHNITTE))
        felder = {f["feld"] for f in v["mandant"]["felder"]}
        self.assertEqual(felder, {"name", "ort", "telefon"})

    def test_vorschau_liste_reihenfolge_und_labels(self):
        from backend.services.fragebogen_uebernahme import vorschau_liste
        liste = vorschau_liste("44/22", _PARSED)
        self.assertEqual([a["key"] for a in liste],
                         ["mandant", "gegner", "unfall", "personenschaden"])
        self.assertEqual(liste[0]["label"], "Mandant")

    def test_uebernehme_fuellt_und_ueberspringt_inaktiv(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import uebernehme
        werte = {
            "mandant": {"name": "Riccio", "telefon": "069 1"},
            "gegner": {"name": "Khaniani"},
        }
        erg = uebernehme("44/22", werte, ["mandant"])  # gegner inaktiv
        with get_connection() as conn:
            m = conn.execute("SELECT telefon FROM beteiligte "
                             "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
            g = conn.execute("SELECT COUNT(*) FROM beteiligte "
                             "WHERE akte_id='44/22' AND rolle='gegner'").fetchone()[0]
        self.assertEqual(m["telefon"], "069 1")
        self.assertEqual(g, 0)   # inaktiver Abschnitt nicht geschrieben
        self.assertTrue(any(x["feld"] == "telefon" for x in erg["geschrieben"]))

    def test_uebernehme_ueberschreibt_nur_bei_abweichung(self):
        from backend.db.database import get_connection
        from backend.services.fragebogen_uebernahme import uebernehme
        with get_connection() as conn:
            conn.execute("INSERT INTO beteiligte (akte_id, rolle, ort) "
                         "VALUES ('44/22', 'mandant', 'Offenbach')")
        # gleicher Wert -> uebersprungen; abweichender -> geschrieben
        erg = uebernehme("44/22",
                         {"mandant": {"ort": "Offenbach", "telefon": "069 1"}},
                         ["mandant"])
        self.assertTrue(any(x["feld"] == "ort" and x["grund"] == "unveraendert"
                            for x in erg["uebersprungen"]))
        erg2 = uebernehme("44/22", {"mandant": {"ort": "Neu-Isenburg"}}, ["mandant"])
        with get_connection() as conn:
            row = conn.execute("SELECT ort FROM beteiligte "
                               "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
        self.assertEqual(row["ort"], "Neu-Isenburg")
        self.assertTrue(any(x["feld"] == "ort" for x in erg2["geschrieben"]))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_fragebogen_uebernahme.py -k Dispatcher -v`
Expected: FAIL — `ImportError` (`baue_vorschau` fehlt).

- [ ] **Step 3: Append the dispatcher to the service module**

Ans Ende von `backend/services/fragebogen_uebernahme.py`:

```python
# ── Dispatch-Tabellen + oeffentliche API ─────────────────────────────────────

_GEPARST = {
    "mandant": _geparst_mandant, "gegner": _geparst_gegner,
    "unfall": _geparst_unfall, "personenschaden": _geparst_personenschaden,
}
_AKTE = {
    "mandant": _akte_mandant, "gegner": _akte_gegner,
    "unfall": _akte_unfall, "personenschaden": _akte_personenschaden,
}
_SCHREIBE = {
    "mandant": lambda c, a, ae: _schreibe_beteiligte(c, a, "mandant", ae),
    "gegner": lambda c, a, ae: _schreibe_beteiligte(c, a, "gegner", ae),
    "unfall": _schreibe_unfall, "personenschaden": _schreibe_personenschaden,
}


def baue_vorschau(akte_az: str, parsed: dict) -> Dict[str, dict]:
    parsed = parsed or {}
    ergebnis: Dict[str, dict] = {}
    with get_connection() as conn:
        for sec in ABSCHNITTE:
            geparst = _GEPARST[sec](parsed.get(sec) or {})
            akte = _AKTE[sec](conn, akte_az)
            ergebnis[sec] = {"felder": _vorschau_felder(geparst, akte)}
    return ergebnis


def vorschau_liste(akte_az: str, parsed: dict) -> List[dict]:
    roh = baue_vorschau(akte_az, parsed)
    return [{"key": sec, "label": _LABELS[sec], "felder": roh[sec]["felder"]}
            for sec in ABSCHNITTE]


def uebernehme(akte_az: str, werte: dict,
               aktive_abschnitte: List[str]) -> Dict[str, list]:
    """Schreibt bestaetigte Werte je aktivem Abschnitt: leer -> fuellen,
    abweichend -> ueberschreiben (nur bei echter Abweichung). Pro Abschnitt
    Best-Effort: ein fehlgeschlagener Abschnitt stoppt die anderen nicht."""
    werte = werte or {}
    aktiv = set(aktive_abschnitte or [])
    geschrieben: List[dict] = []
    uebersprungen: List[dict] = []
    fehler: List[dict] = []
    for sec in ABSCHNITTE:
        if sec not in aktiv:
            continue
        eingaben = werte.get(sec) or {}
        if not eingaben:
            continue
        sec_geschrieben: List[dict] = []
        sec_uebersprungen: List[dict] = []
        try:
            # Eigene Transaktion je Abschnitt: schlaegt ein Abschnitt fehl,
            # rollt get_connection ihn komplett zurueck (kein Teil-Write),
            # andere Abschnitte bleiben committet (Best-Effort).
            with get_connection() as conn:
                akte = _AKTE[sec](conn, akte_az)
                aenderungen: Dict[str, Any] = {}
                for feld, neu in eingaben.items():
                    neu_n = _norm(neu)
                    if not neu_n:
                        sec_uebersprungen.append({"abschnitt": sec, "feld": feld,
                                                  "grund": "leer"})
                        continue
                    akt = _norm(akte.get(feld))
                    if akt == "" or akt.casefold() != neu_n.casefold():
                        aenderungen[feld] = neu
                        sec_geschrieben.append({"abschnitt": sec, "feld": feld,
                                                "wert": neu})
                    else:
                        sec_uebersprungen.append({"abschnitt": sec, "feld": feld,
                                                  "grund": "unveraendert"})
                if aenderungen:
                    _SCHREIBE[sec](conn, akte_az, aenderungen)
            geschrieben.extend(sec_geschrieben)
            uebersprungen.extend(sec_uebersprungen)
        except Exception as exc:
            logger.error("Fragebogen-Uebernahme Abschnitt %s (Akte %s): %s",
                         sec, akte_az, exc, exc_info=True)
            fehler.append({"abschnitt": sec, "fehler": str(exc)})
    return {"geschrieben": geschrieben, "uebersprungen": uebersprungen,
            "fehler": fehler}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_fragebogen_uebernahme.py -v`
Expected: PASS (alle Service-Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/fragebogen_uebernahme.py backend/tests/test_fragebogen_uebernahme.py
git commit -m "feat(intake): fragebogen_uebernahme -- Dispatcher baue_vorschau/vorschau_liste/uebernehme"
```

---

## Task 5: Route — `ist_fragebogen` + Vorschau-Endpoint

**Files:**
- Modify: `backend/routers/intake_routes.py` (Import; `hole_detail` erweitern; neuer Endpoint)
- Test: `backend/tests/test_fragebogen_freigabe_e2e.py` (Tests ergänzen)

**Interfaces:**
- Consumes: `fragebogen_uebernahme.parse_fragebogen_payload`, `vorschau_liste`.
- Produces:
  - `hole_detail`-Response enthält zusätzlich `"ist_fragebogen": bool`.
  - `GET /intake/dokument/<id>/fragebogen-vorschau?akte_az=X` → `{"akte_az": str, "abschnitte": [...]}`; 422 ohne `akte_az` oder wenn kein Fragebogen.

- [ ] **Step 1: Write the failing test**

In `test_fragebogen_freigabe_e2e.py` ergänzen:

```python
class TestVorschauEndpoint(_FragebogenFreigabeBasis):
    def test_detail_meldet_ist_fragebogen(self):
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        r = self.client.get(f"/intake/dokument/{did}", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["ist_fragebogen"])

    def test_vorschau_endpoint_liefert_abschnitte(self):
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        r = self.client.get(
            f"/intake/dokument/{did}/fragebogen-vorschau?akte_az=44%2F22",
            headers=headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        body = r.get_json()
        self.assertEqual(body["akte_az"], "44/22")
        keys = [a["key"] for a in body["abschnitte"]]
        self.assertEqual(keys, ["mandant", "gegner", "unfall", "personenschaden"])

    def test_vorschau_422_ohne_akte_az(self):
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        r = self.client.get(f"/intake/dokument/{did}/fragebogen-vorschau",
                            headers=headers)
        self.assertEqual(r.status_code, 422)

    def test_vorschau_422_bei_nicht_fragebogen(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status) "
                "VALUES ('nofrb0000', 'text', 'nur text', 'bereit_zur_review')")
            did = cur.lastrowid
        headers = self._login()
        r = self.client.get(
            f"/intake/dokument/{did}/fragebogen-vorschau?akte_az=44%2F22",
            headers=headers)
        self.assertEqual(r.status_code, 422)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_fragebogen_freigabe_e2e.py -k Vorschau -v`
Expected: FAIL — `ist_fragebogen` fehlt / Endpoint 404.

- [ ] **Step 3: Add the service import**

In `intake_routes.py` bei den Imports (nach `from ..ramicro.output_adapter import schreibe_dokument`) ergänzen:

```python
from ..services.fragebogen_uebernahme import (
    parse_fragebogen_payload, vorschau_liste, uebernehme,
)
```

- [ ] **Step 4: Add `ist_fragebogen` to `hole_detail`**

In `hole_detail`, im Return-Dict (`_j({...})`) nach `"payload_typ": dok.get("payload_typ"),` ergänzen:

```python
        "ist_fragebogen": parse_fragebogen_payload(dok.get("structured_payload")) is not None,
```

- [ ] **Step 5: Add the vorschau endpoint**

Direkt nach `hole_detail` (vor der `hole_pdf`-Route) einfügen:

```python
@intake_bp.route("/dokument/<int:intake_id>/fragebogen-vorschau", methods=["GET"])
@login_erforderlich
def fragebogen_vorschau(intake_id: int):
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    akte_az = (request.args.get("akte_az") or "").strip()
    if not akte_az:
        return _err("Feld 'akte_az' fehlt", 422)
    parsed = parse_fragebogen_payload(dok.get("structured_payload"))
    if parsed is None:
        return _err("Dokument ist kein Fragebogen", 422)
    return _j({"akte_az": akte_az, "abschnitte": vorschau_liste(akte_az, parsed)})
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_fragebogen_freigabe_e2e.py -v`
Expected: PASS (Task-1-Test + 4 neue).

- [ ] **Step 7: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_fragebogen_freigabe_e2e.py
git commit -m "feat(intake): ist_fragebogen-Flag + Fragebogen-Vorschau-Endpoint"
```

---

## Task 6: Route — Übernahme in `post_freigabe`

**Files:**
- Modify: `backend/routers/intake_routes.py` (`post_freigabe`)
- Test: `backend/tests/test_fragebogen_freigabe_e2e.py`

**Interfaces:**
- Consumes: `uebernehme(akte_az, werte, aktive_abschnitte)`.
- Produces: `post_freigabe`-Response enthält zusätzlich `"fragebogen_uebernahme": {...}|None`. Payload akzeptiert `fragebogen_uebernahme: {"abschnitte":[...], "werte":{...}}`.

- [ ] **Step 1: Write the failing test**

In `test_fragebogen_freigabe_e2e.py` ergänzen:

```python
class TestFreigabeUebernahme(_FragebogenFreigabeBasis):
    def _freigabe(self, did, headers, werte, abschnitte):
        return self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22",
                  "fragebogen_uebernahme": {"abschnitte": abschnitte, "werte": werte}},
            headers=headers)

    def test_freigabe_uebernimmt_felder_in_beteiligte(self):
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        r = self._freigabe(
            did, headers,
            {"mandant": {"name": "Riccio", "telefon": "069 8402271"},
             "gegner": {"name": "Khaniani"}},
            ["mandant", "gegner"])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertIn("fragebogen_uebernahme", r.get_json())
        from backend.db.database import get_connection
        with get_connection() as conn:
            m = conn.execute("SELECT telefon FROM beteiligte "
                             "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
            g = conn.execute("SELECT name FROM beteiligte "
                             "WHERE akte_id='44/22' AND rolle='gegner'").fetchone()
        self.assertEqual(m["telefon"], "069 8402271")
        self.assertEqual(g["name"], "Khaniani")

    def test_freigabe_ueberschreibt_abweichendes_feld(self):
        from backend.db.database import get_connection
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        with get_connection() as conn:
            conn.execute("INSERT INTO beteiligte (akte_id, rolle, ort) "
                         "VALUES ('44/22', 'mandant', 'Offenbach')")
        r = self._freigabe(did, headers,
                           {"mandant": {"ort": "Neu-Isenburg"}}, ["mandant"])
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        with get_connection() as conn:
            row = conn.execute("SELECT ort FROM beteiligte "
                               "WHERE akte_id='44/22' AND rolle='mandant'").fetchone()
        self.assertEqual(row["ort"], "Neu-Isenburg")

    def test_freigabe_ohne_uebernahme_block_bleibt_gueltig(self):
        did = self._lege_fragebogen_intake_an()
        headers = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe",
                             json={"akte_az": "44/22"}, headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json()["fragebogen_uebernahme"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_fragebogen_freigabe_e2e.py -k Uebernahme -v`
Expected: FAIL — Response hat kein `fragebogen_uebernahme`; Felder nicht geschrieben.

- [ ] **Step 3: Wire `uebernehme` into `post_freigabe`**

In `post_freigabe`, nach dem `_schreibe_freigabe_ereignisse(...)`-Aufruf und vor `logger.info("Freigabe intake=...")`, einfügen:

```python
    # Fragebogen-Feld-Uebernahme (nur wenn Payload-Block vorhanden UND das
    # Dokument tatsaechlich ein Fragebogen ist). Best-Effort: ein Fehler bricht
    # die bereits erfolgte Freigabe nicht ab.
    uebernahme_ergebnis = None
    ueb = payload.get("fragebogen_uebernahme")
    if ueb:
        try:
            parsed = parse_fragebogen_payload(dok.get("structured_payload"))
            if parsed is not None:
                uebernahme_ergebnis = uebernehme(
                    akte_az,
                    ueb.get("werte") or {},
                    ueb.get("abschnitte") or [],
                )
        except Exception as exc:
            logger.error("Freigabe %s: Fragebogen-Uebernahme fehlgeschlagen: %s",
                         intake_id, exc, exc_info=True)
            uebernahme_ergebnis = {"fehler": str(exc)}
```

- [ ] **Step 4: Add the result to the response**

Den Return von `post_freigabe` erweitern:

```python
    return _j({
        "ok": True,
        "dokument_id": dokument_id,
        "freigabe_id": freigabe_id,
        "akte_az": akte_az,
        "fragebogen_uebernahme": uebernahme_ergebnis,
    })
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_fragebogen_freigabe_e2e.py -v`
Expected: PASS (alle E2E-Tests).

- [ ] **Step 6: Run the guard + full intake suite (Signaturänderung an geteilter Route)**

Run: `python -m pytest backend/tests/test_s19_intake_write_guard.py backend/tests/test_s19d_e2e_no_intake_writes.py backend/tests/test_intake_routes.py -v`
Expected: PASS — beide Guards bleiben grün (Auto-Pfade schreiben weiterhin nichts; neues Modul nicht in der AST-Whitelist nötig).

- [ ] **Step 7: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_fragebogen_freigabe_e2e.py
git commit -m "feat(intake): Freigabe uebernimmt Fragebogen-Felder in die Akte (Best-Effort)"
```

---

## Task 7: Frontend — Vorschau-UI im Freigabe-Dialog

**Files:**
- Modify: `frontend/src/api.js` (neue Methode `fragebogenVorschau`)
- Modify: `frontend/src/views/ReviewQueueView.jsx` (pure Helfer, `FragebogenUebernahme`-Komponente, Einbindung in `DetailPanel`/`FreigabeDialog`/`doFreigabe`)
- Test: `frontend/src/views/ReviewQueueView.fragebogen.test.jsx` (neu)

**Interfaces:**
- Consumes: `apiIntake.fragebogenVorschau(id, akteAz)` → `{akte_az, abschnitte:[{key,label,felder:[{feld,label,geparst,akte_wert,ist_leer,konflikt}]}]}`.
- Produces:
  - `abschnittHatAufgabe(felder) -> boolean`
  - `initialUebernahme(abschnitte) -> {aktive: string[], collapsed: string[], werte: object}`
  - `baueUebernahmePayload(abschnitte, state) -> {abschnitte, werte}`
  - `FragebogenUebernahme` React-Komponente (Named Export).

- [ ] **Step 1: Add the api method**

In `frontend/src/api.js`, im `apiIntake`-Objekt nach `detail:` ergänzen:

```javascript
  fragebogenVorschau: (id, akteAz) =>
    request(`/intake/dokument/${id}/fragebogen-vorschau?akte_az=${encodeURIComponent(akteAz)}`),
```

- [ ] **Step 2: Write the failing test**

Neue Datei `frontend/src/views/ReviewQueueView.fragebogen.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  abschnittHatAufgabe, initialUebernahme, baueUebernahmePayload,
  FragebogenUebernahme,
} from "./ReviewQueueView.jsx";

const ABSCHNITTE = [
  { key: "mandant", label: "Mandant", felder: [
    { feld: "name", label: "Name", geparst: "Riccio", akte_wert: "Riccio", ist_leer: false, konflikt: false },
    { feld: "telefon", label: "Telefon", geparst: "069 1", akte_wert: null, ist_leer: true, konflikt: false },
    { feld: "ort", label: "Ort", geparst: "Neu-Isenburg", akte_wert: "Offenbach", ist_leer: false, konflikt: true },
  ]},
  { key: "gegner", label: "Gegner", felder: [] },
];

describe("Fragebogen-Uebernahme Helfer", () => {
  it("abschnittHatAufgabe: leer oder konflikt = Aufgabe", () => {
    expect(abschnittHatAufgabe(ABSCHNITTE[0].felder)).toBe(true);
    expect(abschnittHatAufgabe([{ ist_leer: false, konflikt: false }])).toBe(false);
    expect(abschnittHatAufgabe([])).toBe(false);
  });

  it("initialUebernahme: alle Abschnitte mit Feldern aktiv, ohne Aufgabe eingeklappt", () => {
    const s = initialUebernahme(ABSCHNITTE);
    expect(s.aktive).toContain("mandant");
    expect(s.aktive).not.toContain("gegner");   // keine Felder
    // werte: leer -> geparst, konflikt -> akte_wert, gleich -> nicht enthalten
    expect(s.werte.mandant.telefon).toBe("069 1");
    expect(s.werte.mandant.ort).toBe("Offenbach");
    expect(s.werte.mandant.name).toBeUndefined();
  });

  it("baueUebernahmePayload: nur aktive Abschnitte + editierbare Felder", () => {
    const s = initialUebernahme(ABSCHNITTE);
    const p = baueUebernahmePayload(ABSCHNITTE, s);
    expect(p.abschnitte).toEqual(["mandant"]);
    expect(p.werte.mandant).toEqual({ telefon: "069 1", ort: "Offenbach" });
  });

  it("rendert leere, Konflikt- und gesperrte Felder", () => {
    const s = initialUebernahme(ABSCHNITTE);
    render(<FragebogenUebernahme abschnitte={ABSCHNITTE} state={s}
             onToggle={() => {}} onFeld={() => {}} onAdopt={() => {}} />);
    expect(screen.getByText("Telefon")).toBeInTheDocument();
    expect(screen.getByText(/Bogen übernehmen/)).toBeInTheDocument();  // Konflikt-Feld
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.fragebogen.test.jsx`
Expected: FAIL — Exports fehlen.

- [ ] **Step 4: Add pure helpers + component to `ReviewQueueView.jsx`**

Vor `function FreigabeDialog(` einfügen:

```jsx
export function abschnittHatAufgabe(felder) {
  return (felder || []).some(f => f.ist_leer || f.konflikt);
}

// Editierbar sind nur leere und abweichende Felder. Default-Wert: leer -> geparst,
// Konflikt -> Akten-Wert (bleibt, bis der SB "Bogen uebernehmen" klickt).
function editierbareFelder(felder) {
  return (felder || []).filter(f => f.ist_leer || f.konflikt);
}

export function initialUebernahme(abschnitte) {
  const aktive = [];
  const collapsed = [];
  const werte = {};
  (abschnitte || []).forEach(a => {
    if (!a.felder || !a.felder.length) return;
    aktive.push(a.key);
    if (!abschnittHatAufgabe(a.felder)) collapsed.push(a.key);
    const w = {};
    editierbareFelder(a.felder).forEach(f => {
      w[f.feld] = f.ist_leer ? (f.geparst ?? "") : (f.akte_wert ?? "");
    });
    werte[a.key] = w;
  });
  return { aktive, collapsed, werte };
}

export function baueUebernahmePayload(abschnitte, state) {
  const werte = {};
  (abschnitte || []).forEach(a => {
    if (!state.aktive.includes(a.key)) return;
    werte[a.key] = { ...(state.werte[a.key] || {}) };
  });
  return { abschnitte: [...state.aktive], werte };
}

export function FragebogenUebernahme({ abschnitte, state, onToggle, onFeld, onAdopt }) {
  const sichtbar = (abschnitte || []).filter(a => a.felder && a.felder.length);
  if (!sichtbar.length) return null;
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: T.textSm, fontWeight: 600, marginBottom: 6 }}>
        Fragebogen-Übernahme
      </div>
      <div style={{ border: `1px solid ${T.border}`, borderRadius: 8, overflow: "hidden" }}>
        {sichtbar.map(a => {
          const aktiv = state.aktive.includes(a.key);
          const zu = state.collapsed.includes(a.key);
          const felder = editierbareFelder(a.felder);
          return (
            <div key={a.key} style={{ borderTop: `1px solid ${T.border}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8,
                            padding: "8px 10px", background: T.surface, cursor: "pointer" }}
                   onClick={() => onToggle(a.key, "collapsed")}>
                <input type="checkbox" checked={aktiv}
                       onClick={e => e.stopPropagation()}
                       onChange={() => onToggle(a.key, "aktiv")} />
                <strong style={{ fontSize: T.textSm }}>{a.label}</strong>
                <span style={{ marginLeft: "auto", fontSize: T.textXs, color: T.textMuted }}>
                  {zu ? "▸" : "▾"}
                </span>
              </div>
              {aktiv && !zu && (
                <div style={{ padding: "6px 10px", display: "grid", gap: 6 }}>
                  {felder.map(f => (
                    <div key={f.feld} style={{ display: "grid",
                         gridTemplateColumns: "110px 1fr", gap: 8, alignItems: "start" }}>
                      <label style={{ fontSize: T.textXs, color: T.textMid, paddingTop: 6 }}>
                        {f.label}
                      </label>
                      <div>
                        <input
                          value={state.werte[a.key]?.[f.feld] ?? ""}
                          onChange={e => onFeld(a.key, f.feld, e.target.value)}
                          style={{ width: "100%", boxSizing: "border-box",
                                   padding: "5px 8px", fontSize: T.textSm,
                                   border: `1px solid ${f.konflikt ? T.amber : T.greenLight}`,
                                   borderRadius: 4,
                                   background: f.konflikt ? T.amberBg : T.white }}
                        />
                        {f.konflikt && (
                          <div style={{ display: "flex", gap: 8, alignItems: "center",
                                        marginTop: 3, fontSize: T.textXs, color: T.amberText }}>
                            <span>⚠ Akte: {f.akte_wert} · Bogen: {f.geparst}</span>
                            <button type="button" onClick={() => onAdopt(a.key, f.feld, f.geparst)}
                              style={{ fontSize: T.textXs, border: `1px solid ${T.amber}`,
                                       background: "transparent", color: T.amberText,
                                       borderRadius: 4, padding: "1px 6px", cursor: "pointer" }}>
                              Bogen übernehmen
                            </button>
                          </div>
                        )}
                        {f.ist_leer && (
                          <div style={{ fontSize: T.textXs, color: T.greenText, marginTop: 3 }}>
                            leer → wird gefüllt
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.fragebogen.test.jsx`
Expected: PASS.

- [ ] **Step 6: Wire the component into `DetailPanel` + `FreigabeDialog` + `doFreigabe`**

6a. In `DetailPanel` bei den `useState`-Hooks ergänzen:

```jsx
  const [fbVorschau, setFbVorschau] = useState(null);
  const [fbState, setFbState] = useState(null);
```

6b. Nach dem bestehenden `useEffect(() => { if (id) laden(); }, [id, laden]);` einen Vorschau-Effekt ergänzen (lädt bei Fragebogen + gewählter Akte, neu bei Akten-Wechsel):

```jsx
  useEffect(() => {
    if (!detail?.ist_fragebogen || !gewaehlteAkte) { setFbVorschau(null); setFbState(null); return; }
    let aktiv = true;
    apiIntake.fragebogenVorschau(id, gewaehlteAkte)
      .then(d => { if (!aktiv) return;
        setFbVorschau(d.abschnitte);
        setFbState(initialUebernahme(d.abschnitte)); })
      .catch(() => { if (aktiv) { setFbVorschau(null); setFbState(null); } });
    return () => { aktiv = false; };
  }, [id, detail?.ist_fragebogen, gewaehlteAkte]);
```

6c. In `doFreigabe` den Payload erweitern:

```jsx
      await apiIntake.freigabe(id, {
        akte_az: gewaehlteAkte,
        kandidaten_ereignisse: ereignisse,
        ersetzt_ids: ids,
        fragebogen_uebernahme: (fbVorschau && fbState)
          ? baueUebernahmePayload(fbVorschau, fbState) : undefined,
      });
```

6d. Im `FreigabeDialog`-Aufruf (im JSX von `DetailPanel`) die neuen Props durchreichen:

```jsx
          <FreigabeDialog
            dokument={detail}
            akteAz={gewaehlteAkte}
            ereignisse={ereignisse}
            ersetztIds={ersetztIds}
            ereignistypen={ereignistypen}
            fbVorschau={fbVorschau}
            fbState={fbState}
            onFbToggle={(key, art) => setFbState(s => {
              if (art === "aktiv") {
                const an = s.aktive.includes(key);
                return { ...s, aktive: an ? s.aktive.filter(k => k !== key) : [...s.aktive, key] };
              }
              const zu = s.collapsed.includes(key);
              return { ...s, collapsed: zu ? s.collapsed.filter(k => k !== key) : [...s.collapsed, key] };
            })}
            onFbFeld={(sec, feld, wert) => setFbState(s => ({
              ...s, werte: { ...s.werte, [sec]: { ...s.werte[sec], [feld]: wert } } }))}
            onFbAdopt={(sec, feld, wert) => setFbState(s => ({
              ...s, werte: { ...s.werte, [sec]: { ...s.werte[sec], [feld]: wert } } }))}
            onErsetztChange={setErsetztIds}
            onEreignisAdd={/* unveraendert */ () => {
              const eingehende = (ereignistypen || []).filter(t => t.richtung === "eingehend");
              const kandidat = `${(detail.klasse || "").toLowerCase()}_eingegangen`;
              const passt = eingehende.find(t => t.typ === kandidat);
              const default_typ = passt ? passt.typ : (eingehende[0]?.typ || kandidat);
              setEreignisse(prev => [...prev, { typ: default_typ, positionen: [] }]);
            }}
            onEreignisChange={(i, neu) => setEreignisse(prev => prev.map((e, j) => j === i ? neu : e))}
            onEreignisDel={i => setEreignisse(prev => prev.filter((_, j) => j !== i))}
            onConfirm={doFreigabe}
            onCancel={() => setZeigeFreigabe(false)}
            laeuft={aktion}
          />
```

6e. In der `FreigabeDialog`-Signatur die neuen Props annehmen und die Komponente rendern. Signatur erweitern:

```jsx
function FreigabeDialog({ dokument, akteAz, ereignisse, ersetztIds,
                          ereignistypen, onEreignisChange,
                          onErsetztChange, onEreignisAdd, onEreignisDel,
                          onConfirm, onCancel, laeuft,
                          fbVorschau, fbState, onFbToggle, onFbFeld, onFbAdopt }) {
```

Und im JSX von `FreigabeDialog` direkt nach dem einleitenden `<div style={{ color: T.textMuted, ... }}>…</div>` (vor dem Ereignis-Vorschläge-Block) einfügen:

```jsx
        {fbVorschau && fbState && (
          <FragebogenUebernahme
            abschnitte={fbVorschau} state={fbState}
            onToggle={onFbToggle} onFeld={onFbFeld} onAdopt={onFbAdopt} />
        )}
```

- [ ] **Step 7: Run the full frontend suite (Signaturänderung an geteilter Komponente)**

Run: `cd frontend && npx vitest run`
Expected: PASS — die neue Datei + alle bestehenden `ReviewQueueView.*`-Tests bleiben grün.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api.js frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.fragebogen.test.jsx
git commit -m "feat(intake): Fragebogen-Uebernahme-UI im Freigabe-Dialog"
```

---

## Abschluss

- [ ] **Volle Backend-Suite** gegen die v7-Baseline (204f) laufen lassen; null neue Failures in berührten Dateien erwarten:
  Run: `python -m pytest backend/tests -q`
- [ ] **Volle Frontend-Suite**: `cd frontend && npx vitest run`
- [ ] Kurzer manueller Rauchtest (optional, `verify`-Skill): Fragebogen in der Review-Queue öffnen, Akte wählen, Vorschau prüfen, „Bogen übernehmen" testen, freigeben, Akte kontrollieren.
- [ ] Memory-/TODO-Eintrag aktualisieren (Fragebogen-Feld-Übernahme erledigt).

## Spec-Coverage (Self-Review)

- Erkennung (`ist_fragebogen`, `parse_fragebogen_payload`) → Task 2 + 5. ✅
- Service `baue_vorschau`/`uebernehme`/`vorschau_liste` → Task 2–4. ✅
- Feld-Mapping alle vier Abschnitte → Task 2 (Mandant/Gegner) + 3 (Unfall/Personenschaden). ✅
- Konflikt überschreibbar, Standard = Akten-Wert → `_vorschau_felder.konflikt`, `uebernehme` overwrite-only-on-diff (Task 4), UI-Default `initialUebernahme` (Task 7). ✅
- Vorschau-Endpoint (422-Fälle) → Task 5. ✅
- `post_freigabe` Best-Effort-Übernahme + Response → Task 6. ✅
- Text-Dokument-Freigabe (Voraussetzung, Abschnitt 0) → Task 1. ✅
- Abschnitts-Checkboxen + Auto-Collapse → Task 7 (`initialUebernahme.collapsed`, Toggle). ✅
- Guards unberührt/ergänzt → Task 6 Step 6. ✅
- Keine Migration → kein Task nötig. ✅
