# Priorisierte Fragebogen-Liste in der Review-Queue — Umsetzungsplan

> **Für agentische Bearbeiter:** ERFORDERLICHE SUB-SKILL: `superpowers:subagent-driven-development` (empfohlen) oder `superpowers:executing-plans`, um diesen Plan Aufgabe für Aufgabe umzusetzen. Die Schritte nutzen Checkbox-Syntax (`- [ ]`) zur Verfolgung.

**Ziel:** Unfallfragebögen von der Kanzlei-Website erscheinen in der Review-Queue in einer eigenen, priorisierten Sektion mit geprüfter Aktenzuordnung (grün / prüfen / neue Akte), statt als Klasse `sonstiges` unterzugehen.

**Architektur:** Ein neues, reines Ableitungsmodul gewinnt Suchmerkmale aus den strukturierten Bogenfeldern (Mandantenadresse, Kennzeichen, Unfalltag, Nachname). Die Intake-Pipeline erkennt Fragebögen am schema-validierten Payload, stempelt eine eigene Dokumentenklasse und reicht die abgeleiteten Signale an Klassifikator und Akten-Matching weiter. Das Matching erhält rollenrichtige Kennzeichen- und Unfalltag-Wege gegen RA-MICRO (nur lesend). Eine Bewertungsfunktion verdichtet die Kandidatenliste zu einer Ampel, die der Queue-Endpunkt mitliefert und das Frontend als abgesetzte Sektion darstellt.

**Tech-Stack:** Python 3.12 / Flask / SQLite · pytest + unittest · React 18 / Vite · Vitest + Testing Library · RA-MICRO über pymssql (read-only)

**Spezifikation:** `docs/superpowers/specs/2026-08-27-fragebogen-favoritenliste-design.md`

## Globale Randbedingungen

- **RA-MICRO ist read-only.** Nur `SELECT` auf `tblAkten`, `tblAdressen`, `tblAktenBeteiligte`, `_tbl0WDMDaten`. Geschrieben wird ausschließlich in die SQLite-Datenbank des Unfallakten-Systems.
- **Die menschliche Freigabe bleibt der einzige Schreibweg in die Akte** (`INTAKE_REVIEW_PFLICHT`, Default `True`). Keine automatische Zuordnung, keine automatische Freigabe.
- **Zielsprache Deutsch** in allen nutzersichtbaren Texten, Log-Meldungen und Commit-Nachrichten.
- **Keine Kommentare im Code** außer bei nicht-offensichtlichem Verhalten.
- **Keine unnötigen Abstraktionen** — nur umsetzen, was in diesem Plan steht.
- **Tests dürfen nie gegen echtes RA-MICRO laufen.** RA-MICRO-Zugriffe werden gemockt; wo Modulcode `_RAMICRO_VERFUEGBAR` prüft, im Test auf `False` setzen.
- **Jede Test-Fixture setzt ihren eigenen `DB_PATH`** (Muster siehe `backend/tests/test_intake_akten_matching.py:24`).
- **Kein `git add -A`.** Die Git-Wurzel dieses Projekts liegt in `C:\Users\HAL9000`, nicht im Projektordner. Immer explizite Pfade angeben.
- **Der Klassen-Generator läuft auf dem Host**, nicht im Container: `py tools/gen_dokumentenklassen.py` aus der Projektwurzel.
- Backend-Tests: `docker exec unfallakten-backend-dev python -m pytest backend/tests/<datei> -v`
- Frontend-Tests: `docker exec unfallakten-frontend-dev npx vitest run src/views/<datei>`

## Dateiübersicht

| Datei | Verantwortung |
|---|---|
| `backend/intake/fragebogen_signale.py` | **neu** — Erkennung eines Bogen-Payloads und Ableitung der Suchmerkmale. Reine Funktionen, kein DB-Zugriff. |
| `backend/intake/fragebogen_zuordnung.py` | **neu** — verdichtet eine Kandidatenliste zur Ampel (grün / prüfen / neue Akte). Reine Funktion. |
| `backend/registry/klassen/fragebogen.yaml` | **neu** — Dokumentenklasse in der Registry (SSOT). |
| `backend/intake/pipeline.py` | Erkennt Bogen-Payloads, stempelt die Klasse bindend, reichert die Signalliste an. |
| `backend/intake/akten_matching.py` | Liest die neuen Signalschlüssel, sucht rollenrichtig nach Kennzeichen und nach Unfalltag. |
| `backend/ramicro/email_matching.py` | **neu darin:** `suche_kandidaten_in_ramicro` — mehrere Treffer statt einem, mit `varM-KZ` / `varG-KZ` / `varU-TAG` / Nachname. |
| `backend/routers/intake_routes.py` | Queue-Endpunkt liefert `ist_fragebogen`, `bogen_kopf`, `zuordnung`. |
| `backend/email_import/import_service.py` | Fehlender `review_pflicht_aktiv()`-Guard im Erstkontakt-Weg. |
| `backend/routers/email_routes.py` | Erstkontakt-Routen entfernen. |
| `backend/routers/dashboard_routes.py` | Zähler `fragebogen_neu` entfernen. |
| `frontend/src/views/ReviewQueueView.jsx` | Sektion, Ampel-Chips, Anlage-Knopf, Vorbefüllung. |
| `frontend/src/views/email_import/UnfallEmailView.jsx` | Erstkontakt-Karte entfernen. |
| `frontend/src/api.js` | Erstkontakt-Helfer entfernen. |

---

## Task 1: Signalableitung aus dem Bogen

**Dateien:**
- Anlegen: `backend/intake/fragebogen_signale.py`
- Test: `backend/tests/test_fragebogen_signale.py`

**Schnittstellen:**
- Verbraucht: `backend.email_import.fragebogen_parser.parse_fragebogen_anhang(json_bytes) -> dict | None`
- Liefert:
  - `erkenne_fragebogen(payload_typ: str | None, text_gesamt: str | None) -> dict | None`
  - `normiere_kennzeichen(roh: str | None) -> str | None`
  - `baue_signale(bogen: dict) -> dict`
  - `baue_kopf(bogen: dict) -> dict` mit den Schlüsseln `mandant_name`, `kennzeichen`, `unfalltag`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `backend/tests/test_fragebogen_signale.py`:

```python
"""Unit-Tests fuer backend/intake/fragebogen_signale.py.

Die Kennzeichen-Schreibweisen stammen aus echten Unfallboegen im
Produktivsystem (Stand 2026-08-27) -- Mandanten tippen frei ein.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.fragebogen_signale import (
    baue_kopf, baue_signale, erkenne_fragebogen, normiere_kennzeichen,
)


def _bogen_json(**ueberschreibungen):
    basis = {
        "meta": {"formular": "unfallbogen", "version": "2.1"},
        "mandant": {"name": "Golovin", "vorname": "Paul",
                     "email": "PaulGolovin@web.de", "telefon": "01785799951"},
        "gegner": {"fahrer": "Brochner",
                    "fahrzeug": {"kennzeichen": "MTK-DB801"}},
        "unfall": {"datum": "2026-08-03", "ort": "Mainhausen"},
        "sachschaden": {"eigenes_fahrzeug": {"kennzeichen": "WÜ PG 777"}},
    }
    basis.update(ueberschreibungen)
    return json.dumps(basis, ensure_ascii=False)


class TestNormiereKennzeichen(unittest.TestCase):
    def test_echte_schreibweisen_werden_zum_schluessel(self):
        faelle = [
            ("WÜ PG 777",  "WÜPG777"),
            ("OF A-418",   "OFA418"),
            ("OFGM891",    "OFGM891"),
            ("OF CJ 828",  "OFCJ828"),
            ("OF-BR 1612", "OFBR1612"),
            ("of-br 1612", "OFBR1612"),
        ]
        for roh, erwartet in faelle:
            with self.subTest(roh=roh):
                self.assertEqual(normiere_kennzeichen(roh), erwartet)

    def test_freitext_wird_verworfen(self):
        for roh in ("k.A. Fußgänger", "siehe Akte", "unbekannt", "", None,
                    "12345", "ABCDEFG"):
            with self.subTest(roh=roh):
                self.assertIsNone(normiere_kennzeichen(roh))


class TestErkenneFragebogen(unittest.TestCase):
    def test_gueltiger_bogen_wird_erkannt(self):
        bogen = erkenne_fragebogen("text", _bogen_json())
        self.assertIsNotNone(bogen)
        self.assertEqual(bogen["mandant"]["name"], "Golovin")

    def test_pdf_payload_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("pdf", _bogen_json()))

    def test_fremdes_json_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("text", '{"meta": {}}'))

    def test_kein_json_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("text", "Sehr geehrte Damen"))

    def test_leerer_text_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("text", ""))
        self.assertIsNone(erkenne_fragebogen("text", None))


class TestBaueSignale(unittest.TestCase):
    def test_vollstaendiger_bogen(self):
        s = baue_signale(erkenne_fragebogen("text", _bogen_json()))
        self.assertEqual(s["dokument_art"], "fragebogen")
        self.assertEqual(s["mandant_email"], "paulgolovin@web.de")
        self.assertEqual(s["kfz_mandant"], "WÜPG777")
        self.assertEqual(s["kfz_gegner"], "MTKDB801")
        self.assertEqual(s["nachname"], "Golovin")
        self.assertEqual(s["unfalltag"], "2026-08-03")
        self.assertNotIn("az", s)

    def test_aktenzeichen_wird_normiert_uebernommen(self):
        roh = json.loads(_bogen_json())
        roh["meta"]["aktenzeichen"] = "641/26AS"
        s = baue_signale(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(s["az"], "641/26")

    def test_fussgaenger_ohne_kennzeichen(self):
        roh = json.loads(_bogen_json())
        roh["sachschaden"]["eigenes_fahrzeug"]["kennzeichen"] = "k.A. Fußgänger"
        roh["gegner"]["fahrzeug"]["kennzeichen"] = "siehe Akte"
        s = baue_signale(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertNotIn("kfz_mandant", s)
        self.assertNotIn("kfz_gegner", s)
        self.assertEqual(s["mandant_email"], "paulgolovin@web.de")

    def test_leere_felder_erzeugen_keine_signale(self):
        roh = json.loads(_bogen_json())
        roh["mandant"] = {"name": "", "email": "  "}
        roh["unfall"] = {}
        roh["sachschaden"] = {}
        roh["gegner"] = {}
        s = baue_signale(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(s, {"dokument_art": "fragebogen"})


class TestBaueKopf(unittest.TestCase):
    def test_kopf_fuer_die_listenanzeige(self):
        k = baue_kopf(erkenne_fragebogen("text", _bogen_json()))
        self.assertEqual(k["mandant_name"], "Paul Golovin")
        self.assertEqual(k["kennzeichen"], "WÜ PG 777")
        self.assertEqual(k["unfalltag"], "2026-08-03")

    def test_kopf_zeigt_rohes_kennzeichen_auch_wenn_unbrauchbar(self):
        roh = json.loads(_bogen_json())
        roh["sachschaden"]["eigenes_fahrzeug"]["kennzeichen"] = "k.A. Fußgänger"
        k = baue_kopf(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(k["kennzeichen"], "k.A. Fußgänger")

    def test_kopf_ohne_vorname(self):
        roh = json.loads(_bogen_json())
        roh["mandant"]["vorname"] = None
        k = baue_kopf(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(k["mandant_name"], "Golovin")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_signale.py -v
```

Erwartet: `ModuleNotFoundError: No module named 'backend.intake.fragebogen_signale'`

- [ ] **Schritt 3: Modul schreiben**

Datei `backend/intake/fragebogen_signale.py`:

```python
"""Ableitung von Such-Signalen aus einem Website-Unfallbogen.

Reine Lesefunktionen ohne Datenbankzugriff. Der Bogen ist ein schema-
validierter JSON-Datensatz -- seine Felder werden direkt verwendet, statt
Kennzeichen und Datum per Regex aus dem Volltext zu raten.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

# 1-3 Unterscheidungsbuchstaben, 1-2 Erkennungsbuchstaben, 1-4 Ziffern --
# nach dem Entfernen aller Trennzeichen. Faengt Freitext wie "siehe Akte"
# oder "k.A. Fussgaenger" ab.
_KFZ_GUELTIG = re.compile(r"^[A-ZÄÖÜ]{1,3}[A-Z]{1,2}\d{1,4}$")
_KFZ_MUELL = re.compile(r"[^A-ZÄÖÜ0-9]")


def erkenne_fragebogen(payload_typ: Optional[str],
                       text_gesamt: Optional[str]) -> Optional[Dict[str, Any]]:
    """Gibt den geparsten Bogen zurueck, sonst None.

    Ein Fragebogen ist ein Text-Payload, dessen JSON gegen
    ``meta.formular == "unfallbogen"`` und das Bogen-Schema validiert.
    """
    if payload_typ != "text" or not text_gesamt or not text_gesamt.strip():
        return None
    from ..email_import.fragebogen_parser import parse_fragebogen_anhang
    try:
        return parse_fragebogen_anhang(text_gesamt.encode("utf-8"))
    except Exception:
        return None


def normiere_kennzeichen(roh: Optional[str]) -> Optional[str]:
    """Freie Eingabe -> Suchschluessel, oder None wenn unbrauchbar."""
    if not roh:
        return None
    norm = _KFZ_MUELL.sub("", str(roh).upper())
    return norm if _KFZ_GUELTIG.match(norm) else None


def baue_signale(bogen: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Suchmerkmale fuer Klassifikator und Akten-Matching."""
    if not bogen:
        return {}
    mandant = bogen.get("mandant") or {}
    gegner = bogen.get("gegner") or {}
    unfall = bogen.get("unfall") or {}
    eigenes = (bogen.get("sachschaden") or {}).get("eigenes_fahrzeug") or {}
    gegner_kfz = gegner.get("fahrzeug") or {}

    signal: Dict[str, Any] = {"dokument_art": "fragebogen"}

    if bogen.get("aktenzeichen"):
        signal["az"] = bogen["aktenzeichen"]

    mail = (mandant.get("email") or "").strip().lower()
    if mail:
        signal["mandant_email"] = mail

    kfz_m = normiere_kennzeichen(eigenes.get("kennzeichen"))
    if kfz_m:
        signal["kfz_mandant"] = kfz_m

    kfz_g = normiere_kennzeichen(gegner_kfz.get("kennzeichen"))
    if kfz_g:
        signal["kfz_gegner"] = kfz_g

    nachname = (mandant.get("name") or "").strip()
    if nachname:
        signal["nachname"] = nachname

    tag = (unfall.get("datum") or "").strip()
    if tag:
        signal["unfalltag"] = tag

    return signal


def baue_kopf(bogen: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Anzeigewerte fuer die Zeile in der Review-Queue.

    Zeigt das Kennzeichen bewusst so, wie der Mandant es eingetippt hat --
    auch wenn es als Suchschluessel unbrauchbar ist.
    """
    if not bogen:
        return {"mandant_name": None, "kennzeichen": None, "unfalltag": None}
    mandant = bogen.get("mandant") or {}
    eigenes = (bogen.get("sachschaden") or {}).get("eigenes_fahrzeug") or {}
    teile = [(mandant.get("vorname") or "").strip(),
             (mandant.get("name") or "").strip()]
    return {
        "mandant_name": " ".join(t for t in teile if t) or None,
        "kennzeichen": (eigenes.get("kennzeichen") or "").strip() or None,
        "unfalltag": ((bogen.get("unfall") or {}).get("datum") or "").strip()
                      or None,
    }
```

- [ ] **Schritt 4: Test laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_signale.py -v
```

Erwartet: alle Tests grün.

- [ ] **Schritt 5: Committen**

```bash
git add "backend/intake/fragebogen_signale.py" "backend/tests/test_fragebogen_signale.py"
git commit -m "feat(intake): Suchmerkmale aus den strukturierten Bogenfeldern ableiten"
```

---

## Task 2: Dokumentenklasse `fragebogen` und Pipeline-Erkennung

**Dateien:**
- Anlegen: `backend/registry/klassen/fragebogen.yaml`
- Ändern: `backend/intake/pipeline.py:171-230` (Klassenentscheidung), `backend/intake/pipeline.py:208` (Signalliste)
- Generiert: `frontend/src/config/dokumentenklassen.generated.js`, `backend/registry/klasse_ereignistyp.yaml`, `backend/registry/rechnungstyp_mapping.yaml`
- Test: `backend/tests/test_fragebogen_pipeline_klasse.py`

**Schnittstellen:**
- Verbraucht: `erkenne_fragebogen`, `baue_signale` aus Task 1
- Liefert: Intake-Dokumente eines Bogens tragen nach dem Pipeline-Lauf `klasse='fragebogen'`, `klasse_quelle='fragebogen'`, `konfidenz=1.0`; die abgeleiteten Signale stehen `klassifiziere_stufe1` und `finde_kandidaten` zur Verfügung.

- [ ] **Schritt 1: Registry-Datei anlegen**

Datei `backend/registry/klassen/fragebogen.yaml`:

```yaml
klasse: fragebogen

# Keine Marker: ein Fragebogen wird nicht am Text erkannt, sondern am
# schema-validierten JSON-Payload (siehe intake/fragebogen_signale.py).
marker: []

regex_felder: {}

schema:
  mandant_name: string
  kennzeichen: string
  unfalltag: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Unfallfragebogen
richtung: eingehend
bezeichnung_label: Unfallfragebogen
bezeichnung_felder:
  datum: unfalltag
```

- [ ] **Schritt 2: Generator auf dem Host laufen lassen**

Aus der Projektwurzel, **nicht** im Container:

```bash
py tools/gen_dokumentenklassen.py
```

Erwartet: `frontend/src/config/dokumentenklassen.generated.js` enthält jetzt `{ value: "fragebogen", label: "Unfallfragebogen" }`.

Prüfen:

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_gen_dokumentenklassen_guard.py -v
```

Erwartet: PASS. Schlägt der Guard fehl, wurde der Generator nicht gelaufen oder nicht auf dem Host.

- [ ] **Schritt 3: Den fehlschlagenden Test schreiben**

Datei `backend/tests/test_fragebogen_pipeline_klasse.py`:

```python
"""Die Pipeline erkennt einen Unfallbogen am Payload und stempelt die
Klasse verbindlich -- unabhaengig vom Textklassifikator, der auf dem
JSON-Text nur 'sonstiges' liefern wuerde.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BOGEN = {
    "meta": {"formular": "unfallbogen", "version": "2.1"},
    "mandant": {"name": "Golovin", "vorname": "Paul",
                 "email": "paulgolovin@web.de"},
    "gegner": {"fahrzeug": {"kennzeichen": "MTK-DB801"}},
    "unfall": {"datum": "2026-08-03", "ort": "Mainhausen"},
    "sachschaden": {"eigenes_fahrzeug": {"kennzeichen": "WÜ PG 777"}},
}


def _setup_db(name):
    fd, pfad = tempfile.mkstemp(prefix=f"fbklasse_{name}_", suffix=".sqlite")
    os.close(fd)
    import backend.db.database as _db
    _db.DB_PATH = pfad
    os.environ["DB_PATH"] = pfad
    from backend.db.schema_manager import init_db
    init_db()
    return pfad


class TestFragebogenKlasse(unittest.TestCase):
    def setUp(self):
        _setup_db(self._testMethodName)
        from backend.db.database import get_connection
        self.get_connection = get_connection

    def _lege_text_dokument(self, text):
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status) "
                "VALUES (?, 'text', ?, 'neu')",
                (f"sha-{len(text)}-{hash(text) & 0xffff}", text),
            )
            return cur.lastrowid

    def _verarbeite(self, intake_id):
        from backend.intake import pipeline
        with mock.patch.object(pipeline, "klassifiziere_stufe2",
                                return_value=("sonstiges", 0.5)), \
             mock.patch.object(pipeline, "extrahiere_felder",
                                return_value={"felder": {}}), \
             mock.patch("backend.intake.akten_matching._suche_in_ramicro",
                         return_value=[]):
            return pipeline.verarbeite_dokument(intake_id)

    def _klasse(self, intake_id):
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT klasse, klasse_quelle, konfidenz "
                "FROM intake_dokumente WHERE id=?", (intake_id,)
            ).fetchone()
        return dict(row)

    def test_bogen_bekommt_klasse_fragebogen(self):
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        self.assertTrue(self._verarbeite(iid))
        d = self._klasse(iid)
        self.assertEqual(d["klasse"], "fragebogen")
        self.assertEqual(d["klasse_quelle"], "fragebogen")
        self.assertEqual(d["konfidenz"], 1.0)

    def test_normale_email_bleibt_unveraendert(self):
        iid = self._lege_text_dokument("Sehr geehrte Damen und Herren,\n\n"
                                        "anbei die Rechnung.")
        self.assertTrue(self._verarbeite(iid))
        d = self._klasse(iid)
        self.assertEqual(d["klasse"], "sonstiges")
        self.assertEqual(d["klasse_quelle"], "auto")

    def test_manuelle_klasse_bleibt_bindend(self):
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET klasse='gutachten', "
                "klasse_quelle='manuell' WHERE id=?", (iid,))
        self.assertTrue(self._verarbeite(iid))
        self.assertEqual(self._klasse(iid)["klasse"], "gutachten")

    def test_reparse_haelt_die_klasse(self):
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        self._verarbeite(iid)
        self._verarbeite(iid)
        self.assertEqual(self._klasse(iid)["klasse"], "fragebogen")

    def test_signale_erreichen_das_matching(self):
        from backend.intake import pipeline
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        gesehen = {}

        def _merke(text, signale):
            gesehen["signale"] = list(signale)
            return []

        with mock.patch.object(pipeline, "klassifiziere_stufe2",
                                return_value=("sonstiges", 0.5)), \
             mock.patch.object(pipeline, "extrahiere_felder",
                                return_value={"felder": {}}), \
             mock.patch.object(pipeline, "finde_kandidaten", _merke):
            pipeline.verarbeite_dokument(iid)

        zusammen = {k: v for s in gesehen["signale"] for k, v in s.items()}
        self.assertEqual(zusammen["mandant_email"], "paulgolovin@web.de")
        self.assertEqual(zusammen["kfz_mandant"], "WÜPG777")
        self.assertEqual(zusammen["unfalltag"], "2026-08-03")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 4: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_pipeline_klasse.py -v
```

Erwartet: `test_bogen_bekommt_klasse_fragebogen` schlägt fehl mit `'sonstiges' != 'fragebogen'`.

- [ ] **Schritt 5: Pipeline anpassen**

In `backend/intake/pipeline.py`, bei den Importen oben ergänzen:

```python
from .fragebogen_signale import baue_signale, erkenne_fragebogen
```

Dann in `verarbeite_dokument` den Block zwischen dem Laden der Signale und der Klassenentscheidung ersetzen. Bisher (`pipeline.py:208-229`):

```python
        signale = _lade_zustellungs_signale(intake_id)
        kandidaten, hinweise = klassifiziere_stufe1(text_gesamt, signale,
                                                     registry)
```

Neu:

```python
        signale = _lade_zustellungs_signale(intake_id)
        bogen = erkenne_fragebogen(dok.get("payload_typ"), text_gesamt)
        if bogen is not None:
            signale = signale + [baue_signale(bogen)]
        kandidaten, hinweise = klassifiziere_stufe1(text_gesamt, signale,
                                                     registry)
```

Und die Klassenentscheidung (`pipeline.py:218-229`) ersetzen. Bisher:

```python
        ist_manuell = dok.get("klasse_quelle") == "manuell"
        if ist_manuell and dok.get("klasse"):
            klasse = dok["klasse"]
            konfidenz = dok.get("konfidenz") if dok.get("konfidenz") is not None else 1.0
            neue_klasse_quelle = "manuell"
        else:
            klasse = klasse_auto
            konfidenz = konfidenz_auto
            neue_klasse_quelle = "auto"
```

Neu:

```python
        ist_manuell = dok.get("klasse_quelle") == "manuell"
        if ist_manuell and dok.get("klasse"):
            klasse = dok["klasse"]
            konfidenz = dok.get("konfidenz") if dok.get("konfidenz") is not None else 1.0
            neue_klasse_quelle = "manuell"
        elif bogen is not None:
            # Schema-validiert, keine Vermutung: der Textklassifikator
            # saehe im JSON-Payload nur 'sonstiges'.
            klasse = "fragebogen"
            konfidenz = 1.0
            neue_klasse_quelle = "fragebogen"
        else:
            klasse = klasse_auto
            konfidenz = konfidenz_auto
            neue_klasse_quelle = "auto"
```

- [ ] **Schritt 6: Tests laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_pipeline_klasse.py backend/tests/test_gen_dokumentenklassen_guard.py -v
```

Erwartet: alle grün.

- [ ] **Schritt 7: Regression der Intake-Nachbarn prüfen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_akten_matching.py backend/tests/test_s19_intake_write_guard.py backend/tests/test_s19d_e2e_no_intake_writes.py backend/tests/test_fragebogen_freigabe_e2e.py -v
```

Erwartet: alle grün. Kein Test darf sich durch die neue Klasse verändern.

- [ ] **Schritt 8: Committen**

```bash
git add "backend/registry/klassen/fragebogen.yaml" "backend/registry/klasse_ereignistyp.yaml" "backend/registry/rechnungstyp_mapping.yaml" "frontend/src/config/dokumentenklassen.generated.js" "backend/intake/pipeline.py" "backend/tests/test_fragebogen_pipeline_klasse.py"
git commit -m "feat(intake): Dokumentenklasse fragebogen, von der Pipeline verbindlich gestempelt"
```

---

## Task 3: Akten-Matching liest die neuen Signale

**Dateien:**
- Ändern: `backend/intake/akten_matching.py` (Score-Konstanten oben, `_sammle_signale_mails:84`, `_sammle_signale_kfz:97`, `_suche_kfz_in_sqlite:145`, neu `_suche_unfalltag_in_sqlite`, `finde_kandidaten:299`)
- Test: `backend/tests/test_fragebogen_matching.py`

**Schnittstellen:**
- Verbraucht: die Signalschlüssel aus Task 1 (`mandant_email`, `kfz_mandant`, `kfz_gegner`, `nachname`, `unfalltag`)
- Liefert: `finde_kandidaten` gibt `AktenKandidat`-Objekte mit den Quellen `mandanten_mail`, `kfz_mandant`, `kfz_gegner`, `unfalltag`, `unfalltag_name` zurück; Scores nach der Staffel unten.

Neue Score-Staffel (die alten Konstanten bleiben für andere Dokumentarten bestehen):

| Merkmal | Konstante | Score |
|---|---|---|
| Aktenzeichen exakt | `SCORE_AZ_EXAKT` | 1,0 |
| Aktenzeichen ohne Kürzel | `SCORE_AZ_BASIS` | 0,9 |
| Mandanten-E-Mail | `SCORE_MANDANTEN_MAIL` | 0,8 |
| Eigenes Kennzeichen | `SCORE_KFZ_MANDANT` | 0,8 |
| Unfalltag **und** Nachname | `SCORE_UNFALLTAG_NAME` | 0,7 |
| Kennzeichen (Altweg, unbestimmte Rolle) | `SCORE_KFZ` | 0,7 |
| Absender-E-Mail (Altweg) | `SCORE_MAIL` | 0,6 |
| Unfalltag allein | `SCORE_UNFALLTAG` | 0,5 |
| Gegner-Kennzeichen | `SCORE_KFZ_GEGNER` | 0,5 |
| Name + Datum (Altweg) | `SCORE_NAME_DATUM` | 0,5 |
| Nachname allein | `SCORE_MANDANTENNAME` | 0,4 |

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `backend/tests/test_fragebogen_matching.py`:

```python
"""Akten-Matching mit den Signalen aus einem Unfallbogen.

RA-MICRO ist gemockt -- keine Netzwerkzugriffe.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup_db(name):
    fd, pfad = tempfile.mkstemp(prefix=f"fbmatch_{name}_", suffix=".sqlite")
    os.close(fd)
    import backend.db.database as _db
    _db.DB_PATH = pfad
    os.environ["DB_PATH"] = pfad
    from backend.db.schema_manager import init_db
    init_db()
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                      "VALUES ('742/26', '2026-08-03', 'offen')")
        conn.execute("INSERT INTO unfallakte (az, unfalldatum, status) "
                      "VALUES ('900/26', '2026-08-03', 'offen')")
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, email, "
            "kfz_kennzeichen) VALUES "
            "('742/26', 'mandant', 'Golovin', 'paulgolovin@web.de', "
            "'WÜ PG 777')")
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, kfz_kennzeichen) "
            "VALUES ('742/26', 'gegner', 'Brochner', 'MTK-DB 801')")
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name) "
            "VALUES ('900/26', 'mandant', 'Schmitt')")
    return pfad


class TestFragebogenMatching(unittest.TestCase):
    def setUp(self):
        _setup_db(self._testMethodName)
        self.patcher = mock.patch(
            "backend.intake.akten_matching._suche_in_ramicro",
            return_value=[])
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _finde(self, **signal):
        from backend.intake.akten_matching import finde_kandidaten
        return finde_kandidaten("", [dict(dokument_art="fragebogen", **signal)])

    def test_mandanten_mail_trifft(self):
        k = self._finde(mandant_email="paulgolovin@web.de")
        self.assertEqual(k[0].akte_az, "742/26")
        self.assertEqual(k[0].score, 0.8)
        self.assertEqual(k[0].quelle, "mandanten_mail")

    def test_eigenes_kennzeichen_trifft_die_mandantenzeile(self):
        k = self._finde(kfz_mandant="WÜPG777")
        self.assertEqual(k[0].akte_az, "742/26")
        self.assertEqual(k[0].score, 0.8)
        self.assertEqual(k[0].quelle, "kfz_mandant")

    def test_eigenes_kennzeichen_trifft_keine_gegnerzeile(self):
        k = self._finde(kfz_mandant="MTKDB801")
        self.assertEqual(k, [])

    def test_gegnerkennzeichen_trifft_schwach(self):
        k = self._finde(kfz_gegner="MTKDB801")
        self.assertEqual(k[0].akte_az, "742/26")
        self.assertEqual(k[0].score, 0.5)
        self.assertEqual(k[0].quelle, "kfz_gegner")

    def test_unfalltag_mit_name_schlaegt_unfalltag_allein(self):
        k = self._finde(unfalltag="2026-08-03", nachname="Golovin")
        nach_az = {x.akte_az: x for x in k}
        self.assertEqual(nach_az["742/26"].score, 0.7)
        self.assertEqual(nach_az["742/26"].quelle, "unfalltag_name")
        self.assertEqual(nach_az["900/26"].score, 0.5)
        self.assertEqual(nach_az["900/26"].quelle, "unfalltag")

    def test_unfalltag_ohne_treffer(self):
        self.assertEqual(self._finde(unfalltag="2020-01-01"), [])

    def test_bester_score_gewinnt_pro_akte(self):
        k = self._finde(mandant_email="paulgolovin@web.de",
                         unfalltag="2026-08-03", nachname="Golovin")
        treffer = [x for x in k if x.akte_az == "742/26"]
        self.assertEqual(len(treffer), 1)
        self.assertEqual(treffer[0].score, 0.8)

    def test_altweg_bleibt_unberuehrt(self):
        from backend.intake.akten_matching import finde_kandidaten
        k = finde_kandidaten("Kennzeichen WÜ-PG 777 im Gutachten", [])
        self.assertTrue(any(x.quelle == "kfz" for x in k))


if __name__ == "__main__":
    unittest.main()
```

Hinweis zum letzten Test: `WÜ-PG 777` ist die Schreibweise, die das alte Volltext-Muster erkennt — er belegt, dass der Altweg für Nicht-Fragebögen unverändert arbeitet.

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_matching.py -v
```

Erwartet: `test_mandanten_mail_trifft` schlägt mit `IndexError: list index out of range` fehl.

- [ ] **Schritt 3: Score-Konstanten und Kandidaten-Feld ergänzen**

In `backend/intake/akten_matching.py` nach `SCORE_MANDANTENNAME` (Zeile 20) einfügen:

```python
# Fragebogen-Signale (strukturierte Bogenfelder, kein Regex-Raten).
SCORE_MANDANTEN_MAIL = 0.8
SCORE_KFZ_MANDANT = 0.8
SCORE_UNFALLTAG_NAME = 0.7
SCORE_UNFALLTAG = 0.5
SCORE_KFZ_GEGNER = 0.5
```

Die Datenklasse `AktenKandidat` (Zeile 55) um ein optionales Feld erweitern, damit
die Kurzbezeichnung aus RA-MICRO bis in die Anzeige durchgereicht werden kann.
Bestehende Aufrufe bleiben gültig, weil das Feld einen Standardwert hat:

```python
@dataclass
class AktenKandidat:
    akte_az: str
    score: float
    quelle: str
    treffer: str  # was matched: kanonisches AZ, Kennzeichen, Mail, Name
    bezeichnung: Optional[str] = None  # sAktenKurzBezeichnung, nur RA-Micro
```

- [ ] **Schritt 4: Sammelfunktionen und Suchen ergänzen**

In `_sammle_signale_mails` (`akten_matching.py:84`) die Feldliste erweitern. Bisher:

```python
        mail = s.get("absender") or s.get("absender_email")
```

Neu:

```python
        mail = s.get("absender") or s.get("absender_email")
```

bleibt unverändert; darunter eine eigene Sammelfunktion ergänzen:

```python
def _sammle_signale_feld(signale: Iterable[dict], feld: str) -> List[str]:
    """Einzelnes Signalfeld ueber alle Zustellungen einsammeln."""
    ergebnis: List[str] = []
    for s in signale or ():
        if not isinstance(s, dict):
            continue
        wert = s.get(feld)
        if wert:
            wert = str(wert).strip()
            if wert and wert not in ergebnis:
                ergebnis.append(wert)
    return ergebnis
```

Dann die rollenrichtige Kennzeichen-Suche und die Unfalltag-Suche ergänzen (neue Funktionen, direkt nach `_suche_kfz_in_sqlite`):

```python
def _suche_kfz_rolle_in_sqlite(kfz_kandidaten: Sequence[str], rolle: str,
                               score: float, quelle: str
                               ) -> List[AktenKandidat]:
    """Kennzeichen-Suche mit Rollenfilter (Fragebogen-Weg)."""
    ergebnis: List[AktenKandidat] = []
    if not kfz_kandidaten:
        return ergebnis
    with get_connection() as conn:
        for kfz in kfz_kandidaten:
            norm = _kfz_norm(kfz)
            if not norm:
                continue
            rows = conn.execute(
                "SELECT DISTINCT akte_id FROM beteiligte "
                "WHERE rolle = ? "
                "  AND UPPER(REPLACE(REPLACE(kfz_kennzeichen,' ',''),'-','')) = ?",
                (rolle, norm),
            ).fetchall()
            for row in rows:
                if row["akte_id"]:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["akte_id"], score=score,
                        quelle=quelle, treffer=kfz,
                    ))
    return ergebnis


def _suche_unfalltag_in_sqlite(tage: Sequence[str], nachnamen: Sequence[str]
                               ) -> List[AktenKandidat]:
    """Unfalltag aus dem Bogenfeld (ISO), optional verstaerkt durch den
    Nachnamen des Mandanten."""
    ergebnis: List[AktenKandidat] = []
    if not tage:
        return ergebnis
    namen_oben = [n.upper() for n in nachnamen if n]
    with get_connection() as conn:
        for tag in tage:
            rows = conn.execute(
                "SELECT DISTINCT u.az, b.name "
                "FROM unfallakte u "
                "LEFT JOIN beteiligte b ON b.akte_id = u.az "
                "  AND b.rolle = 'mandant' "
                "WHERE u.unfalldatum = ?",
                (tag,),
            ).fetchall()
            for row in rows:
                name_oben = (row["name"] or "").upper()
                if name_oben and name_oben in namen_oben:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["az"], score=SCORE_UNFALLTAG_NAME,
                        quelle="unfalltag_name",
                        treffer=f"{row['name']} + {tag}",
                    ))
                else:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["az"], score=SCORE_UNFALLTAG,
                        quelle="unfalltag", treffer=tag,
                    ))
    return ergebnis
```

- [ ] **Schritt 5: `finde_kandidaten` verdrahten**

In `finde_kandidaten` (`akten_matching.py:299`) nach der Zeile `mails = _sammle_signale_mails(signale)` ergänzen:

```python
    # Fragebogen-Signale: strukturierte Felder, kein Regex-Raten.
    mandanten_mails = _sammle_signale_feld(signale, "mandant_email")
    kfz_mandant = _sammle_signale_feld(signale, "kfz_mandant")
    kfz_gegner = _sammle_signale_feld(signale, "kfz_gegner")
    nachnamen = _sammle_signale_feld(signale, "nachname")
    unfalltage = _sammle_signale_feld(signale, "unfalltag")
```

Und im Ergebnisblock nach `ergebnisse.extend(_suche_name_und_datum_in_sqlite(text))` ergänzen:

```python
    for mail in mandanten_mails:
        for k in _suche_mail_in_sqlite([mail]):
            ergebnisse.append(AktenKandidat(
                akte_az=k.akte_az, score=SCORE_MANDANTEN_MAIL,
                quelle="mandanten_mail", treffer=mail,
            ))
    ergebnisse.extend(_suche_kfz_rolle_in_sqlite(
        kfz_mandant, "mandant", SCORE_KFZ_MANDANT, "kfz_mandant"))
    ergebnisse.extend(_suche_kfz_rolle_in_sqlite(
        kfz_gegner, "gegner", SCORE_KFZ_GEGNER, "kfz_gegner"))
    ergebnisse.extend(_suche_unfalltag_in_sqlite(unfalltage, nachnamen))
```

Der Namens-Fallback `if not ergebnisse:` muss **nach** diesem Block stehen — verschiebe ihn dorthin, falls er davor liegt.

- [ ] **Schritt 6: Tests laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_matching.py backend/tests/test_intake_akten_matching.py backend/tests/test_s17_akten_matching_e2e.py -v
```

Erwartet: alle grün. Die beiden Altweg-Testdateien belegen, dass Nicht-Fragebögen unverändert arbeiten.

- [ ] **Schritt 7: Committen**

```bash
git add "backend/intake/akten_matching.py" "backend/tests/test_fragebogen_matching.py"
git commit -m "feat(intake): Akten-Matching nutzt Bogenfelder, Kennzeichen rollenrichtig"
```

---

## Task 4: RA-MICRO-Suche für Bogen-Signale

**Dateien:**
- Ändern: `backend/ramicro/email_matching.py` (neue Funktion am Ende, bestehende bleiben unangetastet)
- Ändern: `backend/intake/akten_matching.py:266-297` (`_suche_in_ramicro`)
- Test: `backend/tests/test_fragebogen_ramicro.py`

**Schnittstellen:**
- Verbraucht: Signalschlüssel aus Task 1
- Liefert: `suche_kandidaten_in_ramicro(merkmale: dict) -> list[tuple[str, str, str]]` mit Tupeln `(akte_az, methode, treffer)`. Methoden: `mandanten_mail`, `kfz_mandant`, `kfz_gegner`, `unfalltag`, `nachname`. Die Rangfolge zu Scores geschieht im Aufrufer.

**Wichtig:** Die bestehende `suche_akte_in_ramicro` bleibt unverändert — sie hat zwei weitere Aufrufer (`import_service.py:260`, `akten_matching.py:284`) und einen Test, der sie mockt (`test_email_import_fk_guard.py:119`).

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `backend/tests/test_fragebogen_ramicro.py`:

```python
"""RA-MICRO-Suche fuer Bogen-Signale. Die Datenbankschicht ist gemockt --
geprueft wird, WELCHE Abfragen mit WELCHEN Werten gestellt werden und wie
die Treffer zurueckkommen. Es wird ausschliesslich gelesen.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Cursor:
    """Minimaler Cursor: liefert je Aufruf die naechste vorbereitete Antwort
    und merkt sich die abgesetzten SQL-Texte samt Parametern."""

    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.aufrufe = []

    def execute(self, sql, params=None):
        self.aufrufe.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.antworten.pop(0) if self.antworten else None

    def fetchall(self):
        return self.antworten.pop(0) if self.antworten else []


def _mock_verbindung(cursor):
    conn = mock.MagicMock()
    conn.cursor.return_value = cursor
    ctx = mock.MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = False
    return ctx


class TestSucheKandidatenInRamicro(unittest.TestCase):
    def _suche(self, merkmale, antworten):
        from backend.ramicro import email_matching
        cur = _Cursor(antworten)
        with mock.patch.object(email_matching, "get_ramicro_connection",
                                return_value=_mock_verbindung(cur)):
            treffer = email_matching.suche_kandidaten_in_ramicro(merkmale)
        return treffer, cur

    def test_mandanten_mail_liefert_treffer(self):
        treffer, cur = self._suche(
            {"mandant_email": "paulgolovin@web.de"},
            [[{"az": "742/26", "bezeichnung": "Golovin/Brochner"}]],
        )
        self.assertEqual(treffer, [("742/26", "mandanten_mail",
                                     "paulgolovin@web.de",
                                     "Golovin/Brochner")])
        sql, params = cur.aufrufe[0]
        self.assertIn("tblAdressen", sql)
        self.assertIn("sAktenKurzBezeichnung", sql)
        self.assertIn("dtAblage", sql)
        self.assertEqual(params, ("paulgolovin@web.de",))

    def test_eigenes_kennzeichen_fragt_varM_KZ(self):
        treffer, cur = self._suche(
            {"kfz_mandant": "WÜPG777"},
            [[{"az": "742/26", "bezeichnung": "Golovin/Brochner"}]],
        )
        self.assertEqual(treffer[0][1], "kfz_mandant")
        sql, _ = cur.aufrufe[0]
        self.assertIn("varM-KZ", sql)
        self.assertNotIn("varG-KZ", sql)

    def test_gegnerkennzeichen_fragt_varG_KZ(self):
        _, cur = self._suche({"kfz_gegner": "MTKDB801"}, [[]])
        sql, _ = cur.aufrufe[0]
        self.assertIn("varG-KZ", sql)

    def test_unfalltag_wird_ins_ramicro_format_uebersetzt(self):
        _, cur = self._suche({"unfalltag": "2026-08-03"}, [[]])
        sql, params = cur.aufrufe[0]
        self.assertIn("varU-TAG", sql)
        self.assertEqual(params, ("03.08.26%",))

    def test_nachname_wird_gesucht(self):
        treffer, cur = self._suche(
            {"nachname": "Golovin"},
            [[{"az": "742/26", "bezeichnung": "Golovin/Brochner"}]],
        )
        self.assertEqual(treffer[0][1], "nachname")
        sql, params = cur.aufrufe[0]
        self.assertIn("sNachname", sql)
        self.assertEqual(params, ("Golovin",))

    def test_mehrere_merkmale_ergeben_mehrere_treffer(self):
        treffer, _ = self._suche(
            {"mandant_email": "harti.clan@freenet.de", "nachname": "Hartmann"},
            [[{"az": "751/26", "bezeichnung": "Hartmann/Guthier"}],
             [{"az": "751/26", "bezeichnung": "Hartmann/Guthier"},
              {"az": "990/26", "bezeichnung": "Hartmann/Weber"}]],
        )
        self.assertIn(("751/26", "mandanten_mail", "harti.clan@freenet.de",
                        "Hartmann/Guthier"), treffer)
        self.assertIn(("990/26", "nachname", "Hartmann", "Hartmann/Weber"),
                       treffer)

    def test_leere_merkmale_fragen_nichts(self):
        treffer, cur = self._suche({}, [])
        self.assertEqual(treffer, [])
        self.assertEqual(cur.aufrufe, [])

    def test_verbindungsfehler_liefert_leere_liste(self):
        from backend.ramicro import email_matching
        from backend.ramicro.connector import RaMicroVerbindungsFehler
        with mock.patch.object(email_matching, "get_ramicro_connection",
                                side_effect=RaMicroVerbindungsFehler("weg")):
            self.assertEqual(
                email_matching.suche_kandidaten_in_ramicro(
                    {"nachname": "Golovin"}),
                [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_ramicro.py -v
```

Erwartet: `AttributeError: module ... has no attribute 'suche_kandidaten_in_ramicro'`

- [ ] **Schritt 3: Funktion schreiben**

Am Ende von `backend/ramicro/email_matching.py` anfügen:

```python
# ── Fragebogen-Signale: mehrere Kandidaten statt eines Treffers ──────────────

_AKTIV_FILTER = ("(a.dtAblage IS NULL "
                 "OR CAST(a.dtAblage AS DATE) = '1899-12-30')")

_WDM_KZ_SQL = """
    SELECT DISTINCT a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung
    FROM _tbl0WDMDaten w
    INNER JOIN tblAkten a ON a.sAktenNummer = w.AktenNr
    WHERE w.sName = %s
      AND UPPER(REPLACE(REPLACE(CAST(w.Value AS nvarchar(50)),' ',''),'-','')) = %s
      AND {aktiv}
"""

_WDM_TAG_SQL = """
    SELECT DISTINCT a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung
    FROM _tbl0WDMDaten w
    INNER JOIN tblAkten a ON a.sAktenNummer = w.AktenNr
    WHERE w.sName = 'varU-TAG'
      AND CAST(w.Value AS nvarchar(50)) LIKE %s
      AND {aktiv}
"""

_MAIL_SQL = """
    SELECT DISTINCT a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung
    FROM tblAdressen adr
    INNER JOIN tblAktenBeteiligte b ON b.GUIDAdresse = adr.GUIDAdresse
    INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
    WHERE LOWER(adr.sEMail) = %s
      AND b.bDeaktiviert = 0
      AND {aktiv}
"""

_NAME_SQL = """
    SELECT DISTINCT a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung
    FROM tblAdressen adr
    INNER JOIN tblAktenBeteiligte b ON b.GUIDAdresse = adr.GUIDAdresse
    INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
    WHERE adr.sNachname = %s
      AND b.bDeaktiviert = 0
      AND {aktiv}
"""


def suche_kandidaten_in_ramicro(
        merkmale: dict) -> list[tuple[str, str, str, Optional[str]]]:
    """Sucht Akten-Kandidaten zu den Signalen eines Unfallbogens.

    Anders als ``suche_akte_in_ramicro`` bricht diese Funktion nicht beim
    ersten Treffer ab -- die Bewertung geschieht im Aufrufer.

    Args:
        merkmale: Signal-Dict mit den optionalen Schluesseln
            ``mandant_email``, ``kfz_mandant``, ``kfz_gegner``,
            ``unfalltag`` (ISO), ``nachname``.

    Returns:
        Liste von ``(akte_az, methode, treffer, kurzbezeichnung)``. Leer bei
        fehlenden Merkmalen oder wenn RA-MICRO nicht erreichbar ist.

    Nur lesend.
    """
    from ..utils.datum import iso_zu_ramicro

    abfragen = []
    mail = (merkmale.get("mandant_email") or "").strip().lower()
    if mail:
        abfragen.append((_MAIL_SQL, (mail,), "mandanten_mail", mail))
    kfz_m = (merkmale.get("kfz_mandant") or "").strip().upper()
    if kfz_m:
        abfragen.append((_WDM_KZ_SQL, ("varM-KZ", kfz_m), "kfz_mandant", kfz_m))
    kfz_g = (merkmale.get("kfz_gegner") or "").strip().upper()
    if kfz_g:
        abfragen.append((_WDM_KZ_SQL, ("varG-KZ", kfz_g), "kfz_gegner", kfz_g))
    tag = (merkmale.get("unfalltag") or "").strip()
    if tag:
        abfragen.append((_WDM_TAG_SQL, (f"{iso_zu_ramicro(tag)}%",),
                          "unfalltag", tag))
    name = (merkmale.get("nachname") or "").strip()
    if name:
        abfragen.append((_NAME_SQL, (name,), "nachname", name))

    if not abfragen:
        return []

    ergebnis: list[tuple[str, str, str, Optional[str]]] = []
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            for sql, params, methode, treffer in abfragen:
                try:
                    cur.execute(sql.format(aktiv=_AKTIV_FILTER), params)
                    for row in cur.fetchall() or ():
                        az = row["az"] if row else None
                        if az:
                            ergebnis.append((_az_basis(az), methode, treffer,
                                              row.get("bezeichnung")))
                except Exception as e:
                    logger.debug("RA-Micro-Teilabfrage %s fehlgeschlagen: %s",
                                  methode, e)
    except RaMicroNichtAktiv:
        logger.debug("RA-Micro nicht aktiv -- Bogen-Suche uebersprungen.")
    except RaMicroVerbindungsFehler as e:
        logger.warning("RA-Micro nicht erreichbar: %s", e)
    except Exception as e:
        logger.warning("RA-Micro Bogen-Suche Fehler: %s", e)

    return ergebnis
```

- [ ] **Schritt 4: Test laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_ramicro.py -v
```

Erwartet: alle grün.

- [ ] **Schritt 5: Aufruf in `akten_matching.py` verdrahten**

`_suche_in_ramicro` (`akten_matching.py:266`) gibt bisher Tupel zurück, die der Aufrufer erst in `AktenKandidat` umbaut. Weil jetzt ein fünftes Feld dazukommt, liefert die Funktion die Kandidaten direkt. Sie hat nur diesen einen Aufrufer. Die ganze Funktion ersetzen durch:

```python
def _suche_in_ramicro(text: str,
                     az_kandidaten: Sequence[str],
                     kfz_kandidaten: Sequence[str],
                     mails: Sequence[str],
                     bogen_merkmale: Optional[dict] = None,
                     ) -> List[AktenKandidat]:
    """Bruecke zu RA-Micro (nur lesend).

    Zwei Wege: der bestehende Einzeltreffer ueber
    ``suche_akte_in_ramicro`` und -- bei einem Fragebogen -- die
    Kandidatensuche ueber die strukturierten Bogenmerkmale.
    """
    ergebnis: List[AktenKandidat] = []

    try:
        from ..ramicro.email_matching import suche_akte_in_ramicro
    except Exception as exc:
        logger.debug("RA-Micro-Modul nicht importierbar: %s", exc)
        return ergebnis

    az, erkannt, methode = suche_akte_in_ramicro(
        list(az_kandidaten), list(kfz_kandidaten),
        mails[0] if mails else "",
    )
    if az:
        score_map = {
            "aktenzeichen":     SCORE_AZ_EXAKT,
            "kfz_kennzeichen":  SCORE_KFZ,
            "absender_email":   SCORE_MAIL,
        }
        ergebnis.append(AktenKandidat(
            akte_az=az,
            score=score_map.get(methode or "", SCORE_AZ_BASIS),
            quelle=methode or "az_exakt",
            treffer=erkannt or "",
        ))

    if bogen_merkmale:
        try:
            from ..ramicro.email_matching import suche_kandidaten_in_ramicro
            bogen_scores = {
                "mandanten_mail": SCORE_MANDANTEN_MAIL,
                "kfz_mandant":    SCORE_KFZ_MANDANT,
                "unfalltag":      SCORE_UNFALLTAG,
                "kfz_gegner":     SCORE_KFZ_GEGNER,
                "nachname":       SCORE_MANDANTENNAME,
            }
            for az_tr, meth, treffer, bez in suche_kandidaten_in_ramicro(
                    bogen_merkmale):
                ergebnis.append(AktenKandidat(
                    akte_az=az_tr,
                    score=bogen_scores.get(meth, SCORE_MANDANTENNAME),
                    quelle=meth, treffer=treffer, bezeichnung=bez,
                ))
        except Exception as exc:
            logger.warning("RA-Micro-Bogensuche fehlgeschlagen: %s", exc)

    return ergebnis
```

In `finde_kandidaten` den Aufrufblock entsprechend anpassen. Bisher:

```python
    try:
        for az, score, quelle, treffer in _suche_in_ramicro(
            text, az_kandidaten, kfz_kandidaten, mails,
        ):
            ergebnisse.append(AktenKandidat(
                akte_az=az, score=score, quelle=quelle, treffer=treffer,
            ))
    except Exception as exc:
        logger.warning("RA-Micro-Kandidaten-Suche fehlgeschlagen: %s", exc)
```

Neu:

```python
    bogen_merkmale = None
    for s in signale or ():
        if isinstance(s, dict) and s.get("dokument_art") == "fragebogen":
            bogen_merkmale = s
            break
    try:
        ergebnisse.extend(_suche_in_ramicro(
            text, az_kandidaten, kfz_kandidaten, mails, bogen_merkmale,
        ))
    except Exception as exc:
        logger.warning("RA-Micro-Kandidaten-Suche fehlgeschlagen: %s", exc)
```

Und in der Verdichtung am Ende von `finde_kandidaten` die Kurzbezeichnung retten, damit sie nicht verlorengeht, wenn ein Treffer ohne Bezeichnung denselben Score hat:

```python
    beste: dict = {}
    for k in ergebnisse:
        vorher = beste.get(k.akte_az)
        if vorher is None or k.score > vorher.score:
            if vorher is not None and k.bezeichnung is None:
                k.bezeichnung = vorher.bezeichnung
            beste[k.akte_az] = k
        elif vorher.bezeichnung is None and k.bezeichnung:
            vorher.bezeichnung = k.bezeichnung
```

- [ ] **Schritt 5b: Kurzbezeichnung in `parse_json` mitschreiben**

In `backend/intake/pipeline.py` den Aufbau von `akten_kandidaten_json` (Zeile 249) erweitern:

```python
        akten_kandidaten_json = [
            {"akte_az": k.akte_az,
             "score": round(k.score, 3),
             "quelle": k.quelle,
             "treffer": k.treffer,
             "bezeichnung": k.bezeichnung}
            for k in akten_kandidaten
        ]
```

- [ ] **Schritt 6: Tests laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_ramicro.py backend/tests/test_fragebogen_matching.py backend/tests/test_intake_akten_matching.py backend/tests/test_email_import_fk_guard.py -v
```

Erwartet: alle grün.

- [ ] **Schritt 7: Committen**

```bash
git add "backend/ramicro/email_matching.py" "backend/intake/akten_matching.py" "backend/tests/test_fragebogen_ramicro.py"
git commit -m "feat(ramicro): Bogen-Kandidatensuche ueber varM-KZ, varG-KZ, varU-TAG und Nachname"
```

---

## Task 5: Ampel-Bewertung und Queue-Endpunkt

**Dateien:**
- Anlegen: `backend/intake/fragebogen_zuordnung.py`
- Ändern: `backend/routers/intake_routes.py:134-197` (`hole_queue`)
- Test: `backend/tests/test_fragebogen_zuordnung.py`, `backend/tests/test_fragebogen_queue_endpunkt.py`

**Schnittstellen:**
- Verbraucht: `akten_kandidaten` aus `parse_json` (Liste von `{akte_az, score, quelle, treffer}`)
- Liefert: `bewerte(kandidaten: list[dict]) -> dict` mit
  `{"ampel": "gruen"|"pruefen"|"neu", "akte_az": str|None, "kurzbezeichnung": str|None, "begruendung": str|None, "kandidaten_anzahl": int}`
- Queue-Endpunkt liefert je Eintrag zusätzlich `ist_fragebogen: bool`, `bogen_kopf: dict|None`, `zuordnung: dict|None`

Klartext-Begründungen:

| Quelle | Begründung |
|---|---|
| `aktenzeichen`, `az_exakt`, `az_basis` | „Aktenzeichen im Bogen" |
| `mandanten_mail` | „Mandanten-E-Mail" |
| `kfz_mandant` | „eigenes Kennzeichen" |
| `unfalltag_name` | „Unfalltag + Name" |
| `unfalltag` | „Unfalltag" |
| `kfz_gegner` | „Kennzeichen des Gegners" |
| `nachname`, `mandantenname` | „Nachname" |

- [ ] **Schritt 1: Den fehlschlagenden Test für die Bewertung schreiben**

Datei `backend/tests/test_fragebogen_zuordnung.py`:

```python
"""Verdichtung der Kandidatenliste zur Ampel."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.fragebogen_zuordnung import bewerte


def _k(az, score, quelle, bezeichnung=None):
    return {"akte_az": az, "score": score, "quelle": quelle, "treffer": "x",
            "bezeichnung": bezeichnung}


class TestBewerte(unittest.TestCase):
    def test_ohne_kandidaten_neue_akte(self):
        e = bewerte([])
        self.assertEqual(e["ampel"], "neu")
        self.assertIsNone(e["akte_az"])
        self.assertIsNone(e["kurzbezeichnung"])
        self.assertEqual(e["kandidaten_anzahl"], 0)

    def test_none_wie_leer(self):
        self.assertEqual(bewerte(None)["ampel"], "neu")

    def test_ein_starker_kandidat_ist_gruen(self):
        e = bewerte([_k("742/26", 0.8, "mandanten_mail", "Golovin/Brochner")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["akte_az"], "742/26")
        self.assertEqual(e["kurzbezeichnung"], "Golovin/Brochner")
        self.assertEqual(e["begruendung"], "Mandanten-E-Mail")

    def test_ohne_kurzbezeichnung_kein_absturz(self):
        e = bewerte([_k("742/26", 0.8, "mandanten_mail")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertIsNone(e["kurzbezeichnung"])

    def test_aktenzeichen_ist_gruen(self):
        e = bewerte([_k("641/26", 1.0, "aktenzeichen")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["begruendung"], "Aktenzeichen im Bogen")

    def test_unfalltag_mit_name_ist_gruen(self):
        e = bewerte([_k("742/26", 0.7, "unfalltag_name")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["begruendung"], "Unfalltag + Name")

    def test_schwacher_kandidat_ist_pruefen(self):
        e = bewerte([_k("900/26", 0.5, "unfalltag")])
        self.assertEqual(e["ampel"], "pruefen")
        self.assertEqual(e["akte_az"], "900/26")
        self.assertEqual(e["begruendung"], "Unfalltag")

    def test_gegnerkennzeichen_allein_ist_pruefen(self):
        self.assertEqual(
            bewerte([_k("742/26", 0.5, "kfz_gegner")])["ampel"], "pruefen")

    def test_zwei_starke_kandidaten_sind_pruefen(self):
        e = bewerte([_k("751/26", 0.8, "mandanten_mail"),
                      _k("848/25", 0.8, "mandanten_mail")])
        self.assertEqual(e["ampel"], "pruefen")
        self.assertEqual(e["kandidaten_anzahl"], 2)

    def test_starker_kandidat_neben_schwachem_bleibt_gruen(self):
        e = bewerte([_k("742/26", 0.8, "mandanten_mail"),
                      _k("900/26", 0.5, "unfalltag")])
        self.assertEqual(e["ampel"], "gruen")
        self.assertEqual(e["akte_az"], "742/26")
        self.assertEqual(e["kandidaten_anzahl"], 2)

    def test_unbekannte_quelle_bekommt_lesbaren_ersatz(self):
        e = bewerte([_k("742/26", 0.9, "irgendwas")])
        self.assertEqual(e["begruendung"], "irgendwas")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_zuordnung.py -v
```

Erwartet: `ModuleNotFoundError: No module named 'backend.intake.fragebogen_zuordnung'`

- [ ] **Schritt 3: Modul schreiben**

Datei `backend/intake/fragebogen_zuordnung.py`:

```python
"""Verdichtet die Akten-Kandidaten eines Unfallbogens zu einer Ampel.

gruen   -- genau ein starker Kandidat, Zuordnung steht
pruefen -- mehrere starke Kandidaten oder nur ein schwaches Merkmal
neu     -- kein Kandidat, vermutlich ein Neumandat
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

STARK_AB = 0.7

_BEGRUENDUNG = {
    "aktenzeichen":   "Aktenzeichen im Bogen",
    "az_exakt":       "Aktenzeichen im Bogen",
    "az_basis":       "Aktenzeichen im Bogen",
    "mandanten_mail": "Mandanten-E-Mail",
    "kfz_mandant":    "eigenes Kennzeichen",
    "unfalltag_name": "Unfalltag + Name",
    "unfalltag":      "Unfalltag",
    "kfz_gegner":     "Kennzeichen des Gegners",
    "nachname":       "Nachname",
    "mandantenname":  "Nachname",
}


def begruendung(quelle: Optional[str]) -> Optional[str]:
    if not quelle:
        return None
    return _BEGRUENDUNG.get(quelle, quelle)


def bewerte(kandidaten: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    liste = [k for k in (kandidaten or []) if k and k.get("akte_az")]
    if not liste:
        return {"ampel": "neu", "akte_az": None, "kurzbezeichnung": None,
                "begruendung": None, "kandidaten_anzahl": 0}

    sortiert = sorted(liste, key=lambda k: k.get("score") or 0.0, reverse=True)
    bester = sortiert[0]
    starke = [k for k in sortiert if (k.get("score") or 0.0) >= STARK_AB]

    if len(starke) == 1:
        ampel = "gruen"
    else:
        ampel = "pruefen"

    return {
        "ampel": ampel,
        "akte_az": bester["akte_az"],
        "kurzbezeichnung": bester.get("bezeichnung"),
        "begruendung": begruendung(bester.get("quelle")),
        "kandidaten_anzahl": len(sortiert),
    }
```

- [ ] **Schritt 4: Test laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_zuordnung.py -v
```

Erwartet: alle grün.

- [ ] **Schritt 5: Den fehlschlagenden Test für den Endpunkt schreiben**

Datei `backend/tests/test_fragebogen_queue_endpunkt.py`:

```python
"""GET /intake/queue liefert Fragebogen-Kennzeichnung, Kopfdaten und Ampel."""
import importlib
import json
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="fbqueue_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BOGEN = {
    "meta": {"formular": "unfallbogen", "version": "2.1"},
    "mandant": {"name": "Golovin", "vorname": "Paul",
                 "email": "paulgolovin@web.de"},
    "gegner": {"fahrzeug": {"kennzeichen": "MTK-DB801"}},
    "unfall": {"datum": "2026-08-03"},
    "sachschaden": {"eigenes_fahrzeug": {"kennzeichen": "WÜ PG 777"}},
}


def _setup(test_id: str):
    """Muster aus backend/tests/test_abschluss_routes.py:12 -- eigener
    DB_PATH je Test, danach die Module neu laden, damit sie ihn sehen."""
    db_path = os.path.join(_tmp_dir, f"fbq_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")
    os.environ["RAMICRO_AKTIV"] = "false"

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
    return app.test_client()


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login fehlgeschlagen: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestQueueEndpunkt(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def _lege_eintrag(self, payload, klasse, kandidaten):
        from backend.db.database import get_connection
        parse = {"text_gesamt": payload, "felder": {},
                  "akten_kandidaten": kandidaten}
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status, "
                " klasse, klasse_quelle, konfidenz, parse_json) "
                "VALUES (?, 'text', ?, 'bereit_zur_review', ?, ?, 1.0, ?)",
                (f"sha-{klasse}-{len(payload)}", payload, klasse,
                 "fragebogen" if klasse == "fragebogen" else "auto",
                 json.dumps(parse, ensure_ascii=False)))
            return cur.lastrowid

    def _queue(self):
        r = self.client.get("/intake/queue", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()["eintraege"]

    def test_fragebogen_traegt_kopf_und_ampel(self):
        self._lege_eintrag(
            json.dumps(BOGEN, ensure_ascii=False), "fragebogen",
            [{"akte_az": "742/26", "score": 0.8, "quelle": "mandanten_mail",
              "treffer": "paulgolovin@web.de",
              "bezeichnung": "Golovin/Brochner"}])
        e = self._queue()[0]
        self.assertTrue(e["ist_fragebogen"])
        self.assertEqual(e["bogen_kopf"]["mandant_name"], "Paul Golovin")
        self.assertEqual(e["bogen_kopf"]["kennzeichen"], "WÜ PG 777")
        self.assertEqual(e["bogen_kopf"]["unfalltag"], "2026-08-03")
        self.assertEqual(e["zuordnung"]["ampel"], "gruen")
        self.assertEqual(e["zuordnung"]["akte_az"], "742/26")
        self.assertEqual(e["zuordnung"]["kurzbezeichnung"], "Golovin/Brochner")
        self.assertEqual(e["zuordnung"]["begruendung"], "Mandanten-E-Mail")

    def test_fragebogen_ohne_kandidat_ist_neu(self):
        self._lege_eintrag(json.dumps(BOGEN, ensure_ascii=False),
                            "fragebogen", [])
        e = self._queue()[0]
        self.assertEqual(e["zuordnung"]["ampel"], "neu")

    def test_normales_dokument_ohne_bogenfelder(self):
        self._lege_eintrag("Sehr geehrte Damen und Herren", "sonstiges", [])
        e = self._queue()[0]
        self.assertFalse(e["ist_fragebogen"])
        self.assertIsNone(e["bogen_kopf"])
        self.assertIsNone(e["zuordnung"])

    def test_bestehende_felder_bleiben_erhalten(self):
        self._lege_eintrag("Sehr geehrte Damen und Herren", "sonstiges", [])
        e = self._queue()[0]
        for feld in ("id", "klasse", "konfidenz", "queue_status",
                      "erstellt_am", "akte_kandidat_top", "payload_typ"):
            self.assertIn(feld, e)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 6: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_queue_endpunkt.py -v
```

Erwartet: `KeyError: 'ist_fragebogen'`

- [ ] **Schritt 7: Endpunkt erweitern**

In `backend/routers/intake_routes.py` oben ergänzen:

```python
from ..intake.fragebogen_signale import baue_kopf, erkenne_fragebogen
from ..intake.fragebogen_zuordnung import bewerte as bewerte_zuordnung
```

In `hole_queue` die SQL-Spaltenliste um `i.structured_payload` und `i.parse_json` erweitern (aktuell werden nur einzelne `json_extract`-Ausdrücke geholt):

```python
            "SELECT i.id, i.sha256, i.klasse, i.klasse_quelle, i.konfidenz, "
            "       i.queue_status, i.prioritaet_frist, i.erstellt_am, "
            "       i.fehler_detail, i.payload_typ, i.structured_payload, "
            "       i.parse_json, "
```

Im Aufbau von `eintraege` nach `top = json.loads(top_json) if top_json else None` ergänzen:

```python
        bogen = None
        if r["klasse"] == "fragebogen":
            bogen = erkenne_fragebogen(r["payload_typ"],
                                        r["structured_payload"])
        kopf = baue_kopf(bogen) if bogen else None
        zuordnung = None
        if bogen:
            try:
                parse = json.loads(r["parse_json"] or "{}")
            except (TypeError, ValueError):
                parse = {}
            zuordnung = bewerte_zuordnung(parse.get("akten_kandidaten"))
```

Und im `eintraege.append({...})` die drei Felder anfügen:

```python
            "ist_fragebogen": bogen is not None,
            "bogen_kopf": kopf,
            "zuordnung": zuordnung,
```

- [ ] **Schritt 8: Tests laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_queue_endpunkt.py backend/tests/test_fragebogen_zuordnung.py -v
```

Erwartet: alle grün.

- [ ] **Schritt 9: Committen**

```bash
git add "backend/intake/fragebogen_zuordnung.py" "backend/routers/intake_routes.py" "backend/tests/test_fragebogen_zuordnung.py" "backend/tests/test_fragebogen_queue_endpunkt.py"
git commit -m "feat(intake): Queue-Endpunkt liefert Bogenkopf und Ampel-Zuordnung"
```

---

## Task 6: Favoritenliste im Frontend

**Dateien:**
- Ändern: `frontend/src/views/ReviewQueueView.jsx` (neue Helfer nach `gruppenKey:83`, neue Komponenten, Listenaufbau ab `:1929`)
- Test: `frontend/src/views/ReviewQueueView.favoriten.test.jsx`

**Schnittstellen:**
- Verbraucht: `ist_fragebogen`, `bogen_kopf`, `zuordnung` aus Task 5
- Liefert (exportiert für Tests):
  - `teileQueue(gruppen) -> { boegen: Gruppe[], uebrige: Gruppe[] }`
  - `ampelText(zuordnung) -> { farbe: string, text: string }`
  - `FragebogenEintrag({ item, aktiv, onClick, onVerwerfen, onAktenanlage })`

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `frontend/src/views/ReviewQueueView.favoriten.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  teileQueue, ampelText, FragebogenEintrag,
} from "./ReviewQueueView.jsx";

const bogen = (id, zuordnung) => ({
  eintrag: {
    id, klasse: "fragebogen", ist_fragebogen: true,
    erstellt_am: "2026-08-15 12:45",
    bogen_kopf: { mandant_name: "Paul Golovin", kennzeichen: "WÜ PG 777",
                  unfalltag: "2026-08-03" },
    zuordnung,
  },
  kinder: [],
});

const sonstiges = (id) => ({
  eintrag: { id, klasse: "gutachten", ist_fragebogen: false,
             erstellt_am: "2026-08-14 09:00" },
  kinder: [],
});

describe("teileQueue", () => {
  it("trennt Fragebögen von den übrigen Dokumenten", () => {
    const g = [sonstiges(1), bogen(2, { ampel: "gruen" }), sonstiges(3)];
    const { boegen, uebrige } = teileQueue(g);
    expect(boegen.map(x => x.eintrag.id)).toEqual([2]);
    expect(uebrige.map(x => x.eintrag.id)).toEqual([1, 3]);
  });

  it("leere Eingabe ergibt zwei leere Listen", () => {
    expect(teileQueue([])).toEqual({ boegen: [], uebrige: [] });
    expect(teileQueue(null)).toEqual({ boegen: [], uebrige: [] });
  });

  it("ein Fragebogen erscheint nicht doppelt", () => {
    const g = [bogen(2, { ampel: "neu" })];
    const { boegen, uebrige } = teileQueue(g);
    expect(boegen).toHaveLength(1);
    expect(uebrige).toHaveLength(0);
  });
});

describe("ampelText", () => {
  it("grün nennt Aktenzeichen und Kurzbezeichnung", () => {
    const a = ampelText({ ampel: "gruen", akte_az: "742/26",
                          kurzbezeichnung: "Golovin/Brochner",
                          begruendung: "Mandanten-E-Mail" });
    expect(a.text).toContain("742/26");
    expect(a.text).toContain("Golovin/Brochner");
  });

  it("grün ohne Kurzbezeichnung nennt nur das Aktenzeichen", () => {
    const a = ampelText({ ampel: "gruen", akte_az: "742/26" });
    expect(a.text).toBe("→ 742/26");
  });

  it("prüfen nennt die Anzahl der Kandidaten", () => {
    const a = ampelText({ ampel: "pruefen", kandidaten_anzahl: 2 });
    expect(a.text).toContain("PRÜFEN");
  });

  it("neu meldet die neue Akte", () => {
    expect(ampelText({ ampel: "neu" }).text).toContain("NEUE AKTE");
  });

  it("ohne Zuordnung kein Absturz", () => {
    expect(ampelText(null).text).toBe("");
  });
});

describe("FragebogenEintrag", () => {
  const basis = {
    id: 834, klasse: "fragebogen", ist_fragebogen: true,
    erstellt_am: "2026-08-15 12:45",
    bogen_kopf: { mandant_name: "Paul Golovin", kennzeichen: "WÜ PG 777",
                  unfalltag: "2026-08-03" },
  };

  it("zeigt Name, Kennzeichen und Unfalltag", () => {
    render(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "gruen", akte_az: "742/26",
                                     begruendung: "Mandanten-E-Mail" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}} />);
    expect(screen.getByText(/Paul Golovin/)).toBeTruthy();
    expect(screen.getByText(/WÜ PG 777/)).toBeTruthy();
    expect(screen.getByText(/03\.08\.2026/)).toBeTruthy();
    expect(screen.getByText(/Mandanten-E-Mail/)).toBeTruthy();
  });

  it("Anlage-Knopf nur bei neuer Akte", () => {
    const { rerender } = render(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "gruen", akte_az: "742/26" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}} />);
    expect(screen.queryByRole("button", { name: /Akte anlegen/ })).toBeNull();

    rerender(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "neu" } }}
      aktiv={false} onClick={() => {}} onVerwerfen={() => {}}
      onAktenanlage={() => {}} />);
    expect(screen.getByRole("button", { name: /Akte anlegen/ })).toBeTruthy();
  });

  it("Anlage-Knopf öffnet den Dialog ohne die Zeile zu aktivieren", async () => {
    const onAktenanlage = vi.fn();
    const onClick = vi.fn();
    render(<FragebogenEintrag
      item={{ ...basis, zuordnung: { ampel: "neu" } }}
      aktiv={false} onClick={onClick} onVerwerfen={() => {}}
      onAktenanlage={onAktenanlage} />);
    await userEvent.click(
      screen.getByRole("button", { name: /Akte anlegen/ }));
    expect(onAktenanlage).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });
});
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-frontend-dev npx vitest run src/views/ReviewQueueView.favoriten.test.jsx
```

Erwartet: Fehlschlag, `teileQueue is not a function`.

- [ ] **Schritt 3: Helfer und Komponente schreiben**

In `frontend/src/views/ReviewQueueView.jsx` nach `gruppenKey` (Zeile 83) einfügen:

```jsx
export function teileQueue(gruppen) {
  const boegen = [], uebrige = [];
  (gruppen || []).forEach(g => {
    if (g?.eintrag?.ist_fragebogen) boegen.push(g);
    else uebrige.push(g);
  });
  return { boegen, uebrige };
}

const AMPEL_FARBEN = {
  gruen:   { rand: "#1a7f37", grund: "#e8f5ec", schrift: "#1a7f37" },
  pruefen: { rand: "#9a6700", grund: "#fff6e0", schrift: "#9a6700" },
  neu:     { rand: "#0969da", grund: "#e8f0fb", schrift: "#0969da" },
};

export function ampelText(zuordnung) {
  if (!zuordnung) return { farbe: "neu", text: "" };
  if (zuordnung.ampel === "gruen") {
    const kurz = zuordnung.kurzbezeichnung;
    return { farbe: "gruen",
             text: kurz ? `→ ${zuordnung.akte_az} · ${kurz}`
                        : `→ ${zuordnung.akte_az}` };
  }
  if (zuordnung.ampel === "pruefen") {
    const n = zuordnung.kandidaten_anzahl || 0;
    return { farbe: "pruefen",
             text: n > 1 ? `PRÜFEN · ${n} Kandidaten` : "PRÜFEN" };
  }
  return { farbe: "neu", text: "NEUE AKTE" };
}

function fmtTag(iso) {
  if (!iso || iso.length !== 10) return iso || "";
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}`;
}

export function FragebogenEintrag({ item, aktiv, onClick, onVerwerfen,
                                     onAktenanlage }) {
  const kopf = item.bogen_kopf || {};
  const { farbe, text } = ampelText(item.zuordnung);
  const f = AMPEL_FARBEN[farbe] || AMPEL_FARBEN.neu;
  const zeigeAnlage = item.zuordnung?.ampel === "neu";
  return (
    <div onClick={onClick}
      style={{
        padding: "10px 12px",
        borderBottom: `1px solid ${T.border}`,
        cursor: "pointer",
        background: aktiv ? T.accentPale : "transparent",
        borderLeft: aktiv ? `3px solid ${T.accent}` : "3px solid transparent",
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8,
                    marginBottom: 4 }}>
        <span style={{
          fontSize: T.textXs, fontWeight: 700, borderRadius: 4,
          padding: "1px 6px", border: `1px solid ${f.rand}`,
          background: f.grund, color: f.schrift,
        }}>{text}</span>
        <div style={{ flex: 1 }} />
        <button type="button"
          onClick={e => { e.stopPropagation(); onVerwerfen(item); }}
          aria-label="Dokument verwerfen"
          style={{
            border: `1px solid ${T.redLight}`, background: T.redBg,
            color: T.redText, cursor: "pointer", padding: "3px 8px",
            fontSize: T.textXs, fontWeight: 600, borderRadius: 4,
            lineHeight: 1.1,
          }}>Verwerfen</button>
      </div>
      <div style={{ fontSize: T.textSm, color: T.text }}>
        <span title="Unfallfragebogen">📝 </span>
        <strong>{kopf.mandant_name || "Ohne Namen"}</strong>
      </div>
      <div style={{ fontSize: T.textXs, color: T.textMuted, marginTop: 2 }}>
        {[kopf.kennzeichen, fmtTag(kopf.unfalltag)]
          .filter(Boolean).join(" · ")}
      </div>
      {item.zuordnung?.begruendung && (
        <div style={{ fontSize: T.textXs, color: T.textMuted, marginTop: 2 }}>
          Treffer: {item.zuordnung.begruendung}
        </div>
      )}
      <div style={{ fontSize: T.textXs, color: T.textFaint, marginTop: 2 }}>
        #{item.id} · {item.erstellt_am}
      </div>
      {zeigeAnlage && (
        <button type="button"
          onClick={e => { e.stopPropagation(); onAktenanlage(item); }}
          style={{
            marginTop: 6, border: `1px solid ${T.accent}`,
            background: T.accentPale, color: T.accent, cursor: "pointer",
            padding: "3px 8px", fontSize: T.textXs, fontWeight: 600,
            borderRadius: 4,
          }}>Akte anlegen</button>
      )}
    </div>
  );
}
```

- [ ] **Schritt 4: Liste umbauen**

In `ReviewQueueView` die Ableitung ergänzen (nach `const gruppen = useMemo(...)`, Zeile 1853):

```jsx
  const { boegen, uebrige } = useMemo(() => teileQueue(gruppen), [gruppen]);
```

Im Render-Block `{ansicht === "queue" && (<>...</>)}` (Zeile 1935) den `gruppen.map(...)`-Aufruf ersetzen durch:

```jsx
              {boegen.length > 0 && (
                <div style={{ background: "#fbf9f2",
                              borderBottom: `2px solid ${T.border}` }}>
                  <div style={{
                    padding: "6px 12px", fontSize: T.textXs, fontWeight: 700,
                    letterSpacing: "0.06em", color: T.navy,
                  }}>
                    ⭐ UNFALLFRAGEBÖGEN ({boegen.length})
                  </div>
                  {boegen.map(g => (
                    <FragebogenEintrag key={g.eintrag.id} item={g.eintrag}
                      aktiv={aktivId === g.eintrag.id}
                      onClick={() => setAktivId(g.eintrag.id)}
                      onVerwerfen={setVerwerfenDok}
                      onAktenanlage={it => setAnlageDialog({ item: it })} />
                  ))}
                </div>
              )}
              {boegen.length > 0 && uebrige.length > 0 && (
                <div style={{
                  padding: "6px 12px", fontSize: T.textXs, fontWeight: 700,
                  letterSpacing: "0.06em", color: T.textMuted,
                  borderBottom: `1px solid ${T.border}`,
                }}>
                  ÜBRIGE DOKUMENTE ({uebrige.length})
                </div>
              )}
              {uebrige.map(gruppe => (
                <React.Fragment key={gruppe.eintrag.id}>
                  <QueueEintrag item={gruppe.eintrag}
                    aktiv={aktivId === gruppe.eintrag.id}
                    onClick={() => setAktivId(gruppe.eintrag.id)}
                    onVerwerfen={setVerwerfenDok}
                    vorgang={vorgangFuerEintrag(gruppe.eintrag, vorgaenge, queue)} />
                  {gruppe.kinder.map(k => (
                    <QueueEintrag key={k.id} item={k} aktiv={aktivId === k.id}
                      onClick={() => setAktivId(k.id)}
                      onVerwerfen={setVerwerfenDok} eingerueckt
                      vorgang={vorgangFuerEintrag(k, vorgaenge, queue)} />
                  ))}
                </React.Fragment>
              ))}
```

- [ ] **Schritt 5: Tests laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-frontend-dev npx vitest run src/views/ReviewQueueView.favoriten.test.jsx src/views/ReviewQueueView.fragebogen.test.jsx
```

Erwartet: alle grün. Die zweite Datei belegt, dass die bestehende Feld-Übernahme unberührt bleibt.

- [ ] **Schritt 6: Committen**

```bash
git add "frontend/src/views/ReviewQueueView.jsx" "frontend/src/views/ReviewQueueView.favoriten.test.jsx"
git commit -m "feat(review-queue): priorisierte Sektion fuer Unfallfrageboegen mit Ampel"
```

---

## Task 7: Aktenanlage aus Bogendaten vorbefüllen

**Dateien:**
- Ändern: `frontend/src/views/ReviewQueueView.jsx` (`zeigeAktenanlageVorschlag:77`, `AktenanlageDialogLoader:2039`, neue Funktion `bogenVorbefuellung`)
- Test: `frontend/src/views/ReviewQueueView.favoriten.test.jsx` (ergänzen)

**Schnittstellen:**
- Verbraucht: `detail.parse.text_gesamt` (der Bogen-JSON) aus `apiIntake.detail`
- Liefert: `bogenVorbefuellung(detailJson) -> object | null` im Format, das `AktenanlageDialog` über `prefill` erwartet (`mandant`-Gruppe mit `nachname`, `vorname`, `strasse`, `plz`, `ort`, `telefon`, `email`; `unfall`-Gruppe mit `unfalldatum`, `unfallort`, `kennzeichen`)

- [ ] **Schritt 1: Den fehlschlagenden Test ergänzen**

An `frontend/src/views/ReviewQueueView.favoriten.test.jsx` anhängen (Import oben um `bogenVorbefuellung` und `zeigeAktenanlageVorschlag` erweitern):

```jsx
describe("bogenVorbefuellung", () => {
  const roh = JSON.stringify({
    meta: { formular: "unfallbogen", version: "2.1" },
    mandant: { name: "Golovin", vorname: "Paul", strasse: "Bergstr. 1",
               plz: "63075", ort: "Offenbach am Main",
               telefon: "01785799951", email: "paulgolovin@web.de" },
    unfall: { datum: "2026-08-03", ort: "Mainhausen" },
    sachschaden: { eigenes_fahrzeug: { kennzeichen: "WÜ PG 777" } },
  });

  it("übernimmt Mandanten- und Unfalldaten", () => {
    const p = bogenVorbefuellung(roh);
    expect(p.mandant.nachname).toBe("Golovin");
    expect(p.mandant.vorname).toBe("Paul");
    expect(p.mandant.plz).toBe("63075");
    expect(p.mandant.email).toBe("paulgolovin@web.de");
    expect(p.unfall.unfalldatum).toBe("2026-08-03");
    expect(p.unfall.unfallort).toBe("Mainhausen");
    expect(p.unfall.kennzeichen).toBe("WÜ PG 777");
  });

  it("liefert null bei fremdem Inhalt", () => {
    expect(bogenVorbefuellung("Sehr geehrte Damen")).toBeNull();
    expect(bogenVorbefuellung('{"meta":{}}')).toBeNull();
    expect(bogenVorbefuellung(null)).toBeNull();
  });
});

describe("zeigeAktenanlageVorschlag", () => {
  it("gilt für Fragebögen ohne Treffer", () => {
    expect(zeigeAktenanlageVorschlag({
      klasse: "fragebogen", ist_fragebogen: true,
      zuordnung: { ampel: "neu" },
    })).toBe(true);
  });

  it("gilt nicht für Fragebögen mit Treffer", () => {
    expect(zeigeAktenanlageVorschlag({
      klasse: "fragebogen", ist_fragebogen: true,
      zuordnung: { ampel: "gruen", akte_az: "742/26" },
    })).toBe(false);
  });

  it("der Gutachten-Fall bleibt erhalten", () => {
    expect(zeigeAktenanlageVorschlag({
      klasse: "gutachten", absender_kategorie: "gutachter",
      akte_kandidat_top: null,
    })).toBe(true);
  });
});
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-frontend-dev npx vitest run src/views/ReviewQueueView.favoriten.test.jsx
```

Erwartet: `bogenVorbefuellung is not a function` und der Fragebogen-Fall in `zeigeAktenanlageVorschlag` schlägt fehl.

- [ ] **Schritt 3: Umsetzen**

In `frontend/src/views/ReviewQueueView.jsx` `zeigeAktenanlageVorschlag` (Zeile 77) ersetzen:

```jsx
export function zeigeAktenanlageVorschlag(item) {
  if (item?.ist_fragebogen) return item?.zuordnung?.ampel === "neu";
  return item?.klasse === "gutachten"
    && item?.absender_kategorie === "gutachter"
    && !item?.akte_kandidat_top;
}
```

Neue Funktion daneben ergänzen:

```jsx
export function bogenVorbefuellung(rohJson) {
  let d = null;
  try { d = JSON.parse(rohJson); } catch { return null; }
  if (!d || d?.meta?.formular !== "unfallbogen") return null;
  const m = d.mandant || {};
  const u = d.unfall || {};
  const ef = (d.sachschaden || {}).eigenes_fahrzeug || {};
  return {
    mandant: {
      nachname: m.name || "", vorname: m.vorname || "",
      strasse: m.strasse || "", plz: m.plz || "", ort: m.ort || "",
      telefon: m.telefon || "", email: m.email || "",
    },
    unfall: {
      unfalldatum: u.datum || "", unfallort: u.ort || "",
      kennzeichen: ef.kennzeichen || "",
    },
  };
}
```

In `AktenanlageDialogLoader` (Zeile 2039) die Vorbefüllung um den Bogen-Fall erweitern. Bisher:

```jsx
      if (aktiv) {
        setPrefill(baueVorbefuellung(detail, vorlage));
        setGeladen(true);
      }
```

Neu:

```jsx
      if (aktiv) {
        const ausBogen = item.ist_fragebogen
          ? bogenVorbefuellung(detail?.parse?.text_gesamt)
          : null;
        setPrefill(ausBogen || baueVorbefuellung(detail, vorlage));
        setGeladen(true);
      }
```

- [ ] **Schritt 4: Tests laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-frontend-dev npx vitest run src/views/
```

Erwartet: die gesamte Frontend-Suite grün.

- [ ] **Schritt 5: Committen**

```bash
git add "frontend/src/views/ReviewQueueView.jsx" "frontend/src/views/ReviewQueueView.favoriten.test.jsx"
git commit -m "feat(review-queue): Aktenanlage aus Fragebogendaten vorbefuellen"
```

---

## Task 8: Doppelweg stilllegen

**Dateien:**
- Ändern: `backend/email_import/import_service.py:1095` (Guard)
- Ändern: `backend/routers/email_routes.py:949` und `:977` (Routen entfernen)
- Ändern: `backend/routers/dashboard_routes.py:129-142` (Zähler entfernen)
- Ändern: `frontend/src/api.js:432-441` (Helfer entfernen)
- Ändern: `frontend/src/views/email_import/UnfallEmailView.jsx` (Karte entfernen)
- Löschen: `frontend/src/views/email_import/components/FragebogenErstkontaktKarte.jsx`
- Test: `backend/tests/test_fragebogen_kein_doppelweg.py`

**Schnittstellen:**
- Verbraucht: nichts aus vorherigen Tasks
- Liefert: Unter `INTAKE_REVIEW_PFLICHT` (Default) schreibt der Import keine Zeile mehr in `fragebogen_erstkontakt`; der Dashboard-Block liefert `gesamt == emails_nicht_zugeordnet`.

Die Tabelle `fragebogen_erstkontakt` bleibt bestehen — sie ist leer, und eine Migration nur zum Löschen wäre unnötiges Risiko.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `backend/tests/test_fragebogen_kein_doppelweg.py`:

```python
"""Unter INTAKE_REVIEW_PFLICHT laeuft der Fragebogen-Flow ausschliesslich
ueber die Review-Queue. Der Erstkontakt-Weg ist stillgelegt.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BOGEN_OHNE_AZ = {
    "meta": {"formular": "unfallbogen", "version": "2.1"},
    "hat_aktenzeichen": False,
    "aktenzeichen": None,
    "mandant": {"name": "Golovin", "email": "paulgolovin@web.de"},
    "gegner": {"fahrzeug": {"kennzeichen": "MTK-DB801"}},
    "unfall": {"datum": "2026-08-03"},
    "sachschaden": {},
    "personenschaden": None,
    "_roh": {"meta": {"formular": "unfallbogen"}},
}


def _setup(name):
    fd, pfad = tempfile.mkstemp(prefix=f"fbdoppel_{name}_", suffix=".sqlite")
    os.close(fd)
    import backend.db.database as _db
    _db.DB_PATH = pfad
    os.environ["DB_PATH"] = pfad
    from backend.db.schema_manager import init_db
    init_db()
    return pfad


class TestKeinDoppelweg(unittest.TestCase):
    def setUp(self):
        self._alt = os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        _setup(self._testMethodName)

    def tearDown(self):
        if self._alt is not None:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt
        else:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)

    def _zaehle_erstkontakt(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM fragebogen_erstkontakt").fetchone()[0]

    def test_stub_schreibt_nicht_unter_review_pflicht(self):
        from backend.email_import import import_service as isvc
        isvc._fragebogen_neuer_mandant_stub(
            BOGEN_OHNE_AZ,
            {"absender_email": "unfall@anwalt-offenbach.de",
             "message_id": "<a@b>", "betreff": "Unfallbogen: Golovin"},
            {"fehler": 0},
        )
        self.assertEqual(self._zaehle_erstkontakt(), 0)

    def test_altpfad_schreibt_weiterhin(self):
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        from backend.email_import import import_service as isvc
        isvc._fragebogen_neuer_mandant_stub(
            BOGEN_OHNE_AZ,
            {"absender_email": "unfall@anwalt-offenbach.de",
             "message_id": "<a@b>", "betreff": "Unfallbogen: Golovin"},
            {"fehler": 0},
        )
        self.assertEqual(self._zaehle_erstkontakt(), 1)

    def test_dashboard_zaehlt_keine_erstkontakte_mehr(self):
        from backend.routers import dashboard_routes
        from backend.db.database import get_connection
        with get_connection() as conn:
            block = dashboard_routes._lade_eingaenge(conn)
        self.assertNotIn("fragebogen_neu", block)
        self.assertEqual(block["gesamt"], block["emails_nicht_zugeordnet"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_kein_doppelweg.py -v
```

Erwartet: `test_stub_schreibt_nicht_unter_review_pflicht` schlägt fehl mit `1 != 0`.

- [ ] **Schritt 3: Guard einbauen**

In `backend/email_import/import_service.py` in `_fragebogen_neuer_mandant_stub` (Zeile 1095) direkt nach dem Docstring einfügen:

```python
    from ..intake.feature_flags import review_pflicht_aktiv
    if review_pflicht_aktiv():
        logger.debug(
            "K-P1: _fragebogen_neuer_mandant_stub uebersprungen -- "
            "Fragebogen liegt bereits in der Review-Queue")
        return
```

Den Docstring um den Hinweis erweitern, analog zu den Schwesterfunktionen:

```python
    """
    Stub: Speichert Fragebogen-Daten in fragebogen_erstkontakt.

    S1.9d / K-P1: unter INTAKE_REVIEW_PFLICHT NICHT AKTIV -- Frageboegen
    werden ausschliesslich ueber die Review-Queue bearbeitet.
    """
```

- [ ] **Schritt 4: Dashboard-Zähler entfernen**

In `backend/routers/dashboard_routes.py` den `try`-Block um `fragebogen_erstkontakt` (Zeilen 130-136) sowie den Schlüssel `fragebogen_neu` und den Summanden in `gesamt` entfernen. Das Ergebnis:

```python
    return {
        "emails_nicht_zugeordnet": emails,
        "gesamt":                  emails,
    }
```

Die Bedingung `AND (email_typ IS NULL OR email_typ != 'fragebogen')` in der Abfrage darüber bleibt unverändert — Fragebogen-Mails sollen auch weiterhin nicht als „nicht zugeordnet" gezählt werden.

- [ ] **Schritt 5: Tests laufen lassen, Erfolg bestätigen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests/test_fragebogen_kein_doppelweg.py backend/tests/test_s19d_e2e_no_intake_writes.py backend/tests/test_s19d_fragebogen_flag.py -v
```

Erwartet: alle grün.

- [ ] **Schritt 6: Frontend aufräumen**

Datei löschen:

```bash
rm "frontend/src/views/email_import/components/FragebogenErstkontaktKarte.jsx"
```

In `frontend/src/api.js` die Einträge `fragebogenErstkontakt` und `fragebogenErstkontaktStatus` samt Kommentarzeile (Zeilen 432-441) entfernen.

In `frontend/src/views/email_import/UnfallEmailView.jsx` entfernen:
- den Import in Zeile 8
- die beiden Ladeaufrufe (Zeilen 98 und 148) samt zugehörigem State
- die Handler-Funktion um Zeile 222
- den Anzeigeblock „Fragebogen-Erstkontakt" (Zeilen 385-415)

In `backend/routers/email_routes.py` die beiden Routen `fragebogen_erstkontakt_liste` (Zeile 949) und `fragebogen_erstkontakt_status_setzen` (Zeile 977) entfernen.

- [ ] **Schritt 7: Vollsuiten laufen lassen**

```bash
docker exec unfallakten-backend-dev python -m pytest backend/tests -q
docker exec unfallakten-frontend-dev npx vitest run
```

Erwartet: beide Suiten grün. Schlägt ein Test wegen der entfernten Routen fehl, ist er Teil der Stilllegung und wird mit entfernt — aber nur, wenn er ausschließlich den Erstkontakt-Weg prüft.

- [ ] **Schritt 8: Committen**

```bash
git add "backend/email_import/import_service.py" "backend/routers/email_routes.py" "backend/routers/dashboard_routes.py" "frontend/src/api.js" "frontend/src/views/email_import/UnfallEmailView.jsx" "backend/tests/test_fragebogen_kein_doppelweg.py"
git add -u "frontend/src/views/email_import/components/FragebogenErstkontaktKarte.jsx"
git commit -m "refactor(fragebogen): Erstkontakt-Doppelweg stillgelegt, Review-Queue ist der einzige Ort"
```

---

## Abnahme im Betrieb

Nach Abschluss aller Tasks, an den echten Daten:

- [ ] **Reparse der acht Altfälle.** In der Review-Queue je Bogen (474, 475, 476, 527, 613, 672, 727, 834) den Reparse-Knopf drücken und rund zehn Sekunden warten.
- [ ] **Sektion prüfen.** Die Liste muss oben „⭐ Unfallfragebögen (8)" zeigen, darunter „Übrige Dokumente".
- [ ] **Ampeln prüfen.** Erwartete Zuordnungen:

| # | Mandant | Erwartet |
|---|---|---|
| 474 | Tim Englert | 🟢 675/26 |
| 475 | Mack Gideon | 🟢 710/26 |
| 476 | Perisa Petrovic | 🟢 641/26 (Aktenzeichen im Bogen) |
| 527 | Paul Golovin | 🟢 742/26 |
| 613 | Sandra Hartmann | 🟢 751/26 (848/25 ist abgelegt) |
| 672 | Bernd Rügner | 🟢 749/26 |
| 727 | Bernharda Darowski | 🟢 760/26 |
| 834 | Ingelor Reinhard | 🟢 768/26 |

- [ ] **Eine Freigabe durchspielen.** Einen grünen Bogen öffnen, die vorgeschlagene Akte bestätigen, die Feld-Übernahme prüfen (Mandant/Gegner/Unfall/Personenschaden), freigeben. Der Eintrag muss aus der Sektion verschwinden, das Dokument in der Akte als „Unfallfragebogen vom …" erscheinen.
- [ ] **Blauen Fall prüfen.** Sollte kein Bogen blau sein, den Knopf ersatzweise an einem Testbogen ohne bekannte Merkmale prüfen: Der Anlage-Dialog muss mit Name, Anschrift, Telefon, E-Mail, Kennzeichen und Unfalltag vorbefüllt öffnen.
- [ ] **`unfall@`-Reiter prüfen.** Die Karte „Fragebogen-Erstkontakt" ist verschwunden, der Reiter funktioniert im Übrigen unverändert.
