# Aktenanlage aus der ReviewQueue — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aktenanlage direkt aus der ReviewQueue: Dialog sammelt Mandats-/Unfalldaten (vorbefüllt aus dem Gutachten-Parse), erzeugt eine RA-MICRO-OMA-XML in einen überwachten Ordner, das System erkennt die von RA-MICRO angelegte Akte read-only und schlägt das AZ am Review-Eintrag vor.

**Architecture:** Neue SQLite-Tabelle `aktenanlage_vorgaenge` (Migration 66) + neues Blueprint `/aktenanlage` (Service `aktenanlage_service.py`, XML-Generator `ramicro/oma_xml.py`, Erkennung `ramicro/akten_erkennung.py`). Frontend: gemeinsamer `AktenanlageDialog` (ReviewQueue vorbefüllt + Aktensuche leer), Banner/Chip/Status-Leiste in der ReviewQueueView, Lazy-Erkennung im bestehenden 30-s-Poll. Spec: `docs/superpowers/specs/2026-07-30-aktenanlage-design.md`.

**Tech Stack:** Flask-Blueprints, SQLite (schema_manager-Migrationen), pymssql read-only (RA-MICRO), `xml.etree.ElementTree`, React 18 (inline styles, Theme-Tokens `T`), pytest, Vitest.

## Global Constraints

- **RA-MICRO ist read-only** — niemals in die RA-MICRO SQL-Server-DB schreiben; geschrieben wird nur die XML-Datei in den Export-Ordner und nach SQLite.
- **Freigabe bleibt manuell** — kein Auto-Freigeben; das erkannte AZ wird nur vorausgewählt (INTAKE_REVIEW_PFLICHT).
- **Migrations-Regeln:** kein `executescript()`, explizites `conn.commit()` vor und nach DDL, Migration atomar in EINEM Edit schreiben (Flask-Reloader-Falle).
- **Git:** Branch `aktenanlage` von `main`. Git-Wurzel ist das Home-Verzeichnis — `git add` NUR mit expliziten Pfaden, NIEMALS `git add -A`. Jeder Commit endet mit dem Trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` (zweites `-m`).
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten. UI-Texte auf Deutsch.
- **Frontend-Styling:** ausschließlich inline `style`-Objekte mit Theme-Tokens `T` aus `../config/theme.js` (kein CSS). Dialoge = handgerolltes fixed-Overlay (Muster `FreigabeDialog`/`NeueAkteModal`).
- **Backend-Tests laufen im Container:** `docker exec unfallakten-backend-dev python -m pytest backend/tests/<datei> -v`. **Frontend-Tests auf dem Host:** `cd frontend; npm test -- <datei>`.
- Options-Werte in der XML: `HERR`/`FRAU`/`FIRMA` (Spiegel der RA-MICRO-Anrede-Codes 1/2/4), Datumsangaben ISO `JJJJ-MM-TT`.

**Vorbereitung (einmalig, vor Task 1):**

```bash
cd "/c/Users/HAL9000/Documents/Projekt/Version 1.00/unfallakten"
git checkout -b aktenanlage
```

---

### Task 1: Migration 66 — Tabelle `aktenanlage_vorgaenge`

**Files:**
- Modify: `backend/db/schema_manager.py` (MIGRATIONS-Dict bei Eintrag `65:` um `66:` ergänzen; if/elif-Kette in `run_migrations()` nach `elif version == 65:`; Handler `_run_migration_66` nach `_run_migration_65` einfügen)
- Test: `backend/tests/test_aktenanlage_routes.py` (neu, erster Test)

**Interfaces:**
- Produces: Tabelle `aktenanlage_vorgaenge` mit Spalten `id, intake_dokument_id, zustellung_id, status, formular_json, xml_pfad, mandant_nachname, mandant_vorname, mandant_adressnr, erkanntes_az, angelegt_am, angelegt_von, erkannt_am`. Status-Werte: `laeuft | akte_erkannt | abgeschlossen | abgebrochen`.

- [ ] **Step 1: Failing Test schreiben**

`backend/tests/test_aktenanlage_routes.py` neu anlegen (Setup-Muster aus `test_intake_routes.py` übernommen — `DB_PATH` VOR den Reloads setzen):

```python
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

_tmp_dir = tempfile.mkdtemp(prefix="aktenanlage_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"aa_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")
    export_dir = os.path.join(_tmp_dir, f"oma_{test_id}")
    shutil.rmtree(export_dir, ignore_errors=True)
    os.makedirs(export_dir, exist_ok=True)
    os.environ["OMA_EXPORT_PFAD"] = export_dir

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


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


FORMULAR = {
    "mandant": {"anrede": "herr", "titel": "", "vorname": "Abdessamad",
                "nachname": "Achkour Zejli", "strasse": "Wiener Straße 61",
                "plz": "60599", "ort": "Frankfurt am Main", "telefon": "",
                "email": "", "geburtstag": "", "iban": "", "bank": "",
                "rsv_name": "", "rsv_nummer": "", "bekannt_adressnr": ""},
    "unfall": {"unfalldatum": "2026-04-10", "unfallort": "Offenbach",
               "kennzeichen": "F-RX 4243"},
    "gegner": {"anrede": "", "vorname": "", "nachname": "", "strasse": "",
               "plz": "", "ort": "", "kennzeichen": ""},
    "versicherung": {"name": "KRAVAG-LOGISTIC Versicherungs-AG",
                     "schadennummer": "45-11-22"},
    "gutachter": {"bezeichnung": "KFZ-Sachverständigenbüro Cassese",
                  "strasse": "Frankfurter Straße 97", "plz": "63067",
                  "ort": "Offenbach am Main", "telefon": "", "email": "",
                  "gutachten_nr": "GA-202604-1189"},
}


class TestMigration66(unittest.TestCase):
    def setUp(self):
        self.client = _setup("mig66")

    def test_tabelle_und_spalten_vorhanden(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r["name"] for r in
                       conn.execute("PRAGMA table_info(aktenanlage_vorgaenge)")}
        for spalte in ("id", "intake_dokument_id", "zustellung_id", "status",
                       "formular_json", "xml_pfad", "mandant_nachname",
                       "mandant_vorname", "mandant_adressnr", "erkanntes_az",
                       "angelegt_am", "angelegt_von", "erkannt_am"):
            self.assertIn(spalte, spalten)

    def test_schema_version_66_gestempelt(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM schema_version").fetchone()
        self.assertGreaterEqual(row["v"], 66)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -v`
Expected: FAIL (`aktenanlage_vorgaenge` hat keine Spalten / Version < 66)

- [ ] **Step 3: Migration implementieren (EIN Edit!)**

In `backend/db/schema_manager.py`, alle drei Stellen **in einem einzigen Edit-Vorgang** (Reloader-Falle):

(a) Im `MIGRATIONS`-Dict nach der Zeile `65: "-- migration_65_standardtext_override",  # Handled by _run_migration_65`:

```python
    66: "-- migration_66_aktenanlage",  # Handled by _run_migration_66
```

(b) In `run_migrations()` nach `elif version == 65:` / `_run_migration_65(conn)`:

```python
            elif version == 66:
                _run_migration_66(conn)
```

(c) Handler direkt nach `_run_migration_65` einfügen:

```python
def _run_migration_66(conn: sqlite3.Connection) -> None:
    """
    Migration 66 - aktenanlage_vorgaenge (Aktenanlage aus der ReviewQueue).

    Ein Vorgang = eine erzeugte OMA-XML fuer den RA-MICRO-Import.
    Kein executescript, explizite Commits um DDL (Reloader-Falle).
    """
    conn.commit()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS aktenanlage_vorgaenge ("
        " id                 INTEGER PRIMARY KEY AUTOINCREMENT,"
        " intake_dokument_id INTEGER REFERENCES intake_dokumente(id),"
        " zustellung_id      INTEGER REFERENCES zustellungen(id),"
        " status             TEXT NOT NULL DEFAULT 'laeuft'"
        "   CHECK(status IN ('laeuft','akte_erkannt',"
        "                    'abgeschlossen','abgebrochen')),"
        " formular_json      TEXT NOT NULL,"
        " xml_pfad           TEXT NOT NULL,"
        " mandant_nachname   TEXT NOT NULL,"
        " mandant_vorname    TEXT,"
        " mandant_adressnr   TEXT,"
        " erkanntes_az       TEXT,"
        " angelegt_am        TEXT NOT NULL DEFAULT (datetime('now','localtime')),"
        " angelegt_von       INTEGER,"
        " erkannt_am         TEXT)"
    )
    conn.commit()
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aktenanlage_status "
        "ON aktenanlage_vorgaenge(status)"
    )
    conn.commit()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (66, "Migration 66 - aktenanlage_vorgaenge (Aktenanlage ReviewQueue)"),
    )
    logger.info("Migration 66 abgeschlossen (aktenanlage_vorgaenge).")
```

- [ ] **Step 4: Test laufen lassen — muss bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_aktenanlage_routes.py
git commit -m "feat(aktenanlage): Migration 66 aktenanlage_vorgaenge" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: OMA-XML-Generator (`ramicro/oma_xml.py`)

**Files:**
- Create: `backend/ramicro/oma_xml.py`
- Test: `backend/tests/test_oma_xml.py`

**Interfaces:**
- Consumes: Formular-Dict (Struktur = `FORMULAR` aus Task 1: Gruppen `mandant`, `unfall`, `gegner`, `versicherung`, `gutachter`; alle Werte Strings).
- Produces: `erzeuge_oma_xml(formular: dict) -> str` (kompletter XML-String mit Deklaration) und `schreibe_oma_xml(formular: dict, ziel_ordner) -> pathlib.Path` (atomar: `.tmp` + `os.replace`, Rückgabe = finaler Pfad). Wirft `OSError`, wenn `ziel_ordner` kein Verzeichnis ist.

- [ ] **Step 1: Failing Tests schreiben**

`backend/tests/test_oma_xml.py`:

```python
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.ramicro.oma_xml import erzeuge_oma_xml, schreibe_oma_xml
from backend.tests.test_aktenanlage_routes import FORMULAR


class TestErzeugeOmaXml(unittest.TestCase):
    def _root(self, formular=None):
        return ET.fromstring(erzeuge_oma_xml(formular or FORMULAR))

    def test_grundstruktur(self):
        root = self._root()
        self.assertEqual(root.tag, "Onlinemandat")
        self.assertEqual(
            root.findtext("Rechtsangelegenheiten/Rechtsangelegenheit/value"),
            "VERKEHRSUNFALL")
        self.assertIsNotNone(root.find("Mandantenliste/Mandant"))
        self.assertIsNotNone(root.find("tvm"))

    def test_mandant_felder(self):
        root = self._root()
        m = root.find("Mandantenliste/Mandant")
        self.assertEqual(m.findtext("Person/Nachname"), "Achkour Zejli")
        self.assertEqual(m.findtext("Person/Vorname"), "Abdessamad")
        self.assertEqual(m.findtext("Person/Anrede/value"), "HERR")
        self.assertEqual(m.findtext("Adresse/PLZ"), "60599")
        self.assertEqual(m.findtext("Bekannt/value"), "1")
        self.assertEqual(m.findtext("Bekannt/text"), "Nein")

    def test_anrede_frau_und_firma(self):
        f = {**FORMULAR, "mandant": {**FORMULAR["mandant"], "anrede": "frau"}}
        self.assertEqual(
            self._root(f).findtext("Mandantenliste/Mandant/Person/Anrede/value"),
            "FRAU")
        f = {**FORMULAR, "mandant": {**FORMULAR["mandant"], "anrede": "firma"}}
        self.assertEqual(
            self._root(f).findtext("Mandantenliste/Mandant/Person/Anrede/value"),
            "FIRMA")

    def test_bekannt_ja_mit_adressnr(self):
        f = {**FORMULAR,
             "mandant": {**FORMULAR["mandant"], "bekannt_adressnr": "12345"}}
        root = self._root(f)
        self.assertEqual(
            root.findtext("Mandantenliste/Mandant/Bekannt/value"), "2")
        self.assertEqual(
            root.findtext("Mandantenliste/Mandant/Bekannt/text"), "Ja")
        self.assertIn("12345", root.findtext("Zusatzangaben/Text"))

    def test_unfalldaten_in_zusatzangaben(self):
        text = self._root().findtext("Zusatzangaben/Text")
        self.assertIn("2026-04-10", text)
        self.assertIn("Offenbach", text)
        self.assertIn("F-RX 4243", text)
        self.assertIn("GA-202604-1189", text)

    def test_beteiligte_versicherung_und_gutachter(self):
        root = self._root()
        bez = [b.findtext("Versicherung/Bezeichnung") or
               b.findtext("Andere/Bezeichnung")
               for b in root.findall("Beteiligtenliste/Beteiligter")]
        self.assertIn("KRAVAG-LOGISTIC Versicherungs-AG", bez)
        self.assertIn("KFZ-Sachverständigenbüro Cassese", bez)

    def test_gegner_nur_bei_namen(self):
        self.assertIsNone(self._root().find("Gegnerliste/Gegner"))
        f = {**FORMULAR,
             "gegner": {**FORMULAR["gegner"], "nachname": "Bicer"}}
        self.assertEqual(
            self._root(f).findtext("Gegnerliste/Gegner/Person/Nachname"),
            "Bicer")

    def test_escaping_umlaute_und_ampersand(self):
        f = {**FORMULAR,
             "versicherung": {"name": "Müller & Söhne", "schadennummer": ""}}
        xml_text = erzeuge_oma_xml(f)
        self.assertIn("Müller &amp; Söhne", xml_text)
        ET.fromstring(xml_text)


class TestSchreibeOmaXml(unittest.TestCase):
    def test_atomar_geschrieben(self):
        ordner = tempfile.mkdtemp(prefix="oma_out_")
        pfad = schreibe_oma_xml(FORMULAR, ordner)
        self.assertTrue(pfad.exists())
        self.assertTrue(pfad.name.startswith("onlinemandat_"))
        self.assertTrue(pfad.name.endswith(".xml"))
        self.assertIn("achkour_zejli", pfad.name)
        tmp_reste = [f for f in os.listdir(ordner) if f.endswith(".tmp")]
        self.assertEqual(tmp_reste, [])
        ET.fromstring(pfad.read_text(encoding="utf-8"))

    def test_fehler_bei_fehlendem_ordner(self):
        with self.assertRaises(OSError):
            schreibe_oma_xml(FORMULAR, "/nicht/vorhanden/ordner_xyz")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_oma_xml.py -v`
Expected: FAIL mit `ModuleNotFoundError: backend.ramicro.oma_xml`

- [ ] **Step 3: Generator implementieren**

`backend/ramicro/oma_xml.py`:

```python
"""OMA-XML-Generator (RA-MICRO Onlinemandat, Muster: beispieloma.xml)."""
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ANREDEN = {"herr": ("HERR", "Herr"),
           "frau": ("FRAU", "Frau"),
           "firma": ("FIRMA", "Firma")}


def _feld(parent, tag, name, wert=""):
    el = ET.SubElement(parent, tag, {"typ": "feld", "name": name})
    el.text = (wert or "").strip()
    return el


def _option(parent, tag, name, value, text):
    el = ET.SubElement(parent, tag, {"typ": "option", "name": name})
    ET.SubElement(el, "value").text = value
    ET.SubElement(el, "text").text = text
    return el


def _person_block(parent, daten):
    person = ET.SubElement(parent, "Person")
    value, text = ANREDEN.get((daten.get("anrede") or "").lower(), ("", ""))
    _option(person, "Anrede", "Anrede", value, text)
    _feld(person, "AndereAnredeBezeichnung", "Andere Anrede")
    _feld(person, "Titel", "Titel", daten.get("titel"))
    _feld(person, "Adelstitel", "Adelstitel")
    _feld(person, "Vorname", "Vorname", daten.get("vorname"))
    _feld(person, "Nachname", "Nachname", daten.get("nachname"))
    _feld(person, "Geburtstag", "Geburtstag", daten.get("geburtstag"))
    _feld(person, "Geburtsort", "Geburtsort")
    _feld(person, "Geburtsname", "Geburtsname")
    _feld(person, "Staatsangehoerigkeit", "Staatsangehoerigkeit")
    _feld(person, "IdNr", "IdNr")


def _adresse_block(parent, daten):
    adresse = ET.SubElement(parent, "Adresse")
    _feld(adresse, "Strasse", "Straße Nr.", daten.get("strasse"))
    _feld(adresse, "Adresszusatz", "Adresszusatz")
    _feld(adresse, "PLZ", "PLZ", daten.get("plz"))
    _feld(adresse, "Ort", "Ort", daten.get("ort"))
    _feld(adresse, "Land", "Land", "Deutschland")
    ET.SubElement(adresse, "LKZ", {"typ": "data"}).text = "DE"


def _kontakt_block(parent, daten):
    kontakt = ET.SubElement(parent, "Kontakt")
    _feld(kontakt, "Telefon", "Telefon", daten.get("telefon"))
    _feld(kontakt, "Mobiltelefon", "Mobiltelefon")
    _feld(kontakt, "EMail", "E-Mail", daten.get("email"))


def _zusatz_text(formular):
    unfall = formular.get("unfall") or {}
    gutachter = formular.get("gutachter") or {}
    mandant = formular.get("mandant") or {}
    zeilen = []
    if unfall.get("unfalldatum"):
        zeilen.append(f"Unfalldatum: {unfall['unfalldatum']}")
    if unfall.get("unfallort"):
        zeilen.append(f"Unfallort: {unfall['unfallort']}")
    if unfall.get("kennzeichen"):
        zeilen.append(f"Amtl. Kennzeichen Mandant: {unfall['kennzeichen']}")
    if gutachter.get("gutachten_nr"):
        zeilen.append(f"Gutachten-Nr.: {gutachter['gutachten_nr']}")
    if mandant.get("bekannt_adressnr"):
        zeilen.append("Bestandsmandant, RA-MICRO Adressnummer: "
                      f"{mandant['bekannt_adressnr']}")
    zeilen.append("Angelegt über das Unfallakten-System (Aktenanlage).")
    return "\n".join(zeilen)


def erzeuge_oma_xml(formular: dict) -> str:
    mandant = formular.get("mandant") or {}
    gegner = formular.get("gegner") or {}
    versicherung = formular.get("versicherung") or {}
    gutachter = formular.get("gutachter") or {}

    root = ET.Element("Onlinemandat", {
        "typ": "gruppe", "name": "Datenblatt für neue Mandanten"})

    ra = ET.SubElement(root, "Rechtsangelegenheiten", {
        "typ": "gruppe", "name": "Startseite"})
    _option(ra, "Rechtsangelegenheit", "Rechtsangelegenheit",
            "VERKEHRSUNFALL", "Verkehrsunfall")
    _feld(ra, "AndereAngelegenheitBezeichnung", "Andere Angelegenheit",
          "Verkehrsrecht")

    mliste = ET.SubElement(root, "Mandantenliste", {
        "typ": "gruppe", "name": "Daten zum Mandant"})
    m = ET.SubElement(mliste, "Mandant", {
        "typ": "gruppe", "name": "1. Mandant"})
    ET.SubElement(m, "Nr", {"typ": "data"}).text = "1"
    if mandant.get("bekannt_adressnr"):
        _option(m, "Bekannt",
                "Waren Sie schon einmal Mandant in unserer Kanzlei?",
                "2", "Ja")
    else:
        _option(m, "Bekannt",
                "Waren Sie schon einmal Mandant in unserer Kanzlei?",
                "1", "Nein")
    _person_block(m, mandant)
    _adresse_block(m, mandant)
    _kontakt_block(m, mandant)
    konto = ET.SubElement(m, "Konto")
    _feld(konto, "IBAN", "IBAN", mandant.get("iban"))
    _feld(konto, "Bank", "Bank", mandant.get("bank"))
    _feld(konto, "BIC", "BIC")
    rsv = ET.SubElement(m, "Rechtsschutzversicherer")
    _feld(rsv, "Name", "Rechtsschutzversicherung", mandant.get("rsv_name"))
    _feld(rsv, "Versicherungsnummer", "Versicherungsnummer",
          mandant.get("rsv_nummer"))
    mv = ET.SubElement(m, "Versicherung")
    _feld(mv, "Name", "Name der Versicherung")
    _feld(mv, "Schadennummer", "Schadennummer, Vertragsnummer, o.ä.")

    gliste = ET.SubElement(root, "Gegnerliste", {
        "typ": "gruppe", "name": "Daten zum Gegner"})
    if (gegner.get("nachname") or "").strip():
        g = ET.SubElement(gliste, "Gegner", {
            "typ": "gruppe", "name": "1. Gegner"})
        ET.SubElement(g, "Nr", {"typ": "data"}).text = "1"
        _person_block(g, gegner)
        _adresse_block(g, gegner)
        _kontakt_block(g, gegner)

    bliste = ET.SubElement(root, "Beteiligtenliste", {
        "typ": "gruppe", "name": "Daten zu Beteiligten"})
    if (versicherung.get("name") or "").strip():
        b = ET.SubElement(bliste, "Beteiligter", {
            "typ": "gruppe", "name": "Beteiligter: Versicherung"})
        ET.SubElement(b, "Nr", {"typ": "data"})
        vgrp = ET.SubElement(b, "Versicherung", {
            "typ": "gruppe", "name": "Versicherung"})
        _feld(vgrp, "Bezeichnung", "Bezeichnung", versicherung.get("name"))
        _feld(vgrp, "Aktenzeichen", "Aktenzeichen/Vorgangsnummer",
              versicherung.get("schadennummer"))
    if (gutachter.get("bezeichnung") or "").strip():
        b = ET.SubElement(bliste, "Beteiligter", {
            "typ": "gruppe", "name": "Beteiligter: Gutachter"})
        ET.SubElement(b, "Nr", {"typ": "data"})
        agrp = ET.SubElement(b, "Andere", {
            "typ": "gruppe", "name": "Andere Beteiligte"})
        _feld(agrp, "Bezeichnung", "Bezeichnung", gutachter.get("bezeichnung"))
        _feld(agrp, "Aktenzeichen", "Aktenzeichen/Vorgangsnummer",
              gutachter.get("gutachten_nr"))
        _feld(agrp, "Strasse", "Straße Nr.", gutachter.get("strasse"))
        _feld(agrp, "Adresszusatz", "Adresszusatz")
        _feld(agrp, "PLZ", "PLZ", gutachter.get("plz"))
        _feld(agrp, "Ort", "Ort", gutachter.get("ort"))
        _feld(agrp, "Land", "Land", "Deutschland")
        ET.SubElement(agrp, "LKZ", {"typ": "data"}).text = "DE"
        _feld(agrp, "Telefon", "Telefon", gutachter.get("telefon"))
        _feld(agrp, "Mobiltelefon", "Mobiltelefon")
        _feld(agrp, "EMail", "E-Mail", gutachter.get("email"))

    zusatz = ET.SubElement(root, "Zusatzangaben", {
        "typ": "gruppe", "name": "Daten an Anwalt senden"})
    _feld(zusatz, "Text", "Weitere Hinweise", _zusatz_text(formular))
    _feld(zusatz, "VerbindlicheAnfrageAkzeptiert",
          "Rechtsverbindliche Anfrage", "X")
    _feld(zusatz, "DatenschutzVereinbarungAkzeptiert",
          "Datenschutzerklärung akzeptiert", "X")
    ET.SubElement(root, "tvm")

    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            + ET.tostring(root, encoding="unicode"))


def _slug(text: str) -> str:
    text = (text or "unbekannt").lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(alt, neu)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unbekannt"


def schreibe_oma_xml(formular: dict, ziel_ordner) -> Path:
    ordner = Path(ziel_ordner)
    if not ordner.is_dir():
        raise OSError(f"OMA-Export-Ordner existiert nicht: {ordner}")
    nachname = _slug((formular.get("mandant") or {}).get("nachname"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ziel = ordner / f"onlinemandat_{stamp}_{nachname}.xml"
    tmp = ziel.with_suffix(".tmp")
    tmp.write_text(erzeuge_oma_xml(formular), encoding="utf-8")
    os.replace(tmp, ziel)
    return ziel
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_oma_xml.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add backend/ramicro/oma_xml.py backend/tests/test_oma_xml.py
git commit -m "feat(aktenanlage): OMA-XML-Generator mit atomarem Schreiben" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: RA-MICRO-Helfer — Adress-Details, Akten je Adresse, Akten-Erkennung

**Files:**
- Modify: `backend/ramicro/adress_service.py` (zwei Funktionen ergänzen)
- Create: `backend/ramicro/akten_erkennung.py`
- Test: `backend/tests/test_ramicro_aktenanlage.py`

**Interfaces:**
- Consumes: `get_ramicro_connection`, `RaMicroNichtAktiv`, `RaMicroVerbindungsFehler` aus `backend/ramicro/connector.py`.
- Produces:
  - `adress_service.hole_adresse_details(adressnr: int) -> dict | None` mit Keys `adressnr, anrede, name, vorname, firmenzeile, strasse, plz, ort, telefon, email` (Strings, `anrede` = RA-MICRO-Code "1"/"2"/"4"…). Offline → `None`.
  - `adress_service.akten_zu_adresse(adressnr: int) -> list[dict]` mit Keys `az, kurzbezeichnung`. Offline → `[]`.
  - `akten_erkennung.finde_neue_akten(seit_iso: str, nachname: str = "", adressnr: str = "") -> dict` mit Keys `verfuegbar: bool`, `treffer: list[{az, kurzbezeichnung}]`. Ohne Suchkriterium → `{"verfuegbar": True, "treffer": []}`. Offline/Fehler → `{"verfuegbar": False, "treffer": []}`.

- [ ] **Step 1: Failing Tests schreiben**

`backend/tests/test_ramicro_aktenanlage.py`:

```python
import os
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.ramicro import adress_service, akten_erkennung
from backend.ramicro.connector import RaMicroVerbindungsFehler


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self.cur = _FakeCursor(rows)

    def cursor(self):
        return self.cur


def _fake_connection(rows):
    @contextmanager
    def _cm():
        yield _FakeConn(rows)
    return _cm


def _offline():
    @contextmanager
    def _cm():
        raise RaMicroVerbindungsFehler("offline")
        yield
    return _cm


ADRESSE = {"adressnr": 12345, "anrede": "1", "name": "Achkour Zejli",
           "vorname": "Abdessamad", "firmenzeile": "",
           "strasse": "Wiener Straße 61", "plz": "60599",
           "ort": "Frankfurt am Main", "telefon": "069/1234",
           "email": "a@b.de"}


class TestHoleAdresseDetails(unittest.TestCase):
    def test_liefert_alle_felder(self):
        with patch.object(adress_service, "get_ramicro_connection",
                          _fake_connection([ADRESSE])):
            d = adress_service.hole_adresse_details(12345)
        self.assertEqual(d["strasse"], "Wiener Straße 61")
        self.assertEqual(d["plz"], "60599")
        self.assertEqual(d["anrede"], "1")

    def test_offline_liefert_none(self):
        with patch.object(adress_service, "get_ramicro_connection",
                          _offline()):
            self.assertIsNone(adress_service.hole_adresse_details(1))


class TestAktenZuAdresse(unittest.TestCase):
    def test_liefert_akten(self):
        rows = [{"az": "285/26", "kurzbezeichnung": "Zejli ./. KRAVAG"}]
        with patch.object(adress_service, "get_ramicro_connection",
                          _fake_connection(rows)):
            akten = adress_service.akten_zu_adresse(12345)
        self.assertEqual(akten, [{"az": "285/26",
                                  "kurzbezeichnung": "Zejli ./. KRAVAG"}])

    def test_offline_liefert_leer(self):
        with patch.object(adress_service, "get_ramicro_connection",
                          _offline()):
            self.assertEqual(adress_service.akten_zu_adresse(1), [])


class TestFindeNeueAkten(unittest.TestCase):
    def test_ohne_kriterium_leer_aber_verfuegbar(self):
        erg = akten_erkennung.finde_neue_akten("2026-07-30 10:00:00")
        self.assertEqual(erg, {"verfuegbar": True, "treffer": []})

    def test_treffer_nach_nachname(self):
        rows = [{"az": "301/26", "kurzbezeichnung": "Zejli ./. KRAVAG"}]
        with patch.object(akten_erkennung, "get_ramicro_connection",
                          _fake_connection(rows)):
            erg = akten_erkennung.finde_neue_akten(
                "2026-07-30 10:00:00", nachname="Achkour Zejli")
        self.assertTrue(erg["verfuegbar"])
        self.assertEqual(erg["treffer"][0]["az"], "301/26")

    def test_adressnr_hat_vorrang(self):
        rows = [{"az": "302/26", "kurzbezeichnung": ""}]
        with patch.object(akten_erkennung, "get_ramicro_connection",
                          _fake_connection(rows)) as _:
            erg = akten_erkennung.finde_neue_akten(
                "2026-07-30 10:00:00", nachname="X", adressnr="12345")
        self.assertEqual(erg["treffer"][0]["az"], "302/26")

    def test_offline(self):
        with patch.object(akten_erkennung, "get_ramicro_connection",
                          _offline()):
            erg = akten_erkennung.finde_neue_akten(
                "2026-07-30 10:00:00", nachname="X")
        self.assertEqual(erg, {"verfuegbar": False, "treffer": []})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_ramicro_aktenanlage.py -v`
Expected: FAIL (`akten_erkennung` fehlt, `hole_adresse_details` fehlt)

- [ ] **Step 3: Implementieren**

(a) In `backend/ramicro/adress_service.py` ans Dateiende anhängen (Muster wie die bestehenden Funktionen; Spaltennamen aus `ramicro_akte_routes.py`, `[sStraße]` mit ß in eckigen Klammern):

```python
def hole_adresse_details(adressnr: int) -> dict | None:
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT TOP 1
                    iAdressnummer     AS adressnr,
                    sAnrede           AS anrede,
                    sNachname         AS name,
                    sVorname          AS vorname,
                    sErsteAdresszeile AS firmenzeile,
                    [sStraße]         AS strasse,
                    sPLZ              AS plz,
                    sOrt              AS ort,
                    sTelefon          AS telefon,
                    sEMail            AS email
                FROM tblAdressen
                WHERE iAdressnummer = %s
                """,
                (adressnr,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {k: (row[k] if k == "adressnr" else (row[k] or ""))
                    for k in ("adressnr", "anrede", "name", "vorname",
                              "firmenzeile", "strasse", "plz", "ort",
                              "telefon", "email")}
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Adress-Detail nicht möglich: %s", e)
        return None
    except Exception as e:
        logger.warning("Adress-Detail fehlgeschlagen (adressnr=%s): %s",
                       adressnr, e)
        return None


def akten_zu_adresse(adressnr: int) -> list[dict]:
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT TOP 10
                    a.sAktenNummer          AS az,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung
                FROM tblAktenBeteiligte b
                INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
                WHERE b.iAdressnummer = %s
                  AND b.bDeaktiviert = 0
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer DESC
                """,
                (adressnr,),
            )
            return [{"az": r["az"], "kurzbezeichnung": r["kurzbezeichnung"] or ""}
                    for r in cur.fetchall()]
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Akten-zu-Adresse nicht möglich: %s", e)
        return []
    except Exception as e:
        logger.warning("Akten-zu-Adresse fehlgeschlagen (adressnr=%s): %s",
                       adressnr, e)
        return []
```

(b) `backend/ramicro/akten_erkennung.py` neu:

```python
"""Read-only-Erkennung neu angelegter RA-MICRO-Akten (Aktenanlage-Feature).

dtAnlage-Existenz ist nicht in jeder Installation belegt (siehe Spec
Abschnitt 9) -- bei Abfragefehlern wird 'nicht verfuegbar' gemeldet,
die manuelle Zuordnung bleibt immer moeglich.
"""
import logging

from .connector import (get_ramicro_connection, RaMicroNichtAktiv,
                        RaMicroVerbindungsFehler)

logger = logging.getLogger(__name__)


def finde_neue_akten(seit_iso: str, nachname: str = "",
                     adressnr: str = "") -> dict:
    nachname = (nachname or "").strip()
    adressnr = (adressnr or "").strip()
    if not nachname and not adressnr:
        return {"verfuegbar": True, "treffer": []}
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            if adressnr:
                person_filter = "b.iAdressnummer = %(adressnr)s"
            else:
                person_filter = "adr.sNachname LIKE %(nachname)s"
            cur.execute(
                f"""
                SELECT DISTINCT TOP 5
                    a.sAktenNummer          AS az,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung
                FROM tblAkten a
                INNER JOIN tblAktenBeteiligte b ON b.GUIDAkte = a.GUIDAkte
                LEFT JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.iBeteiligtenArt = 1
                  AND b.bDeaktiviert = 0
                  AND {person_filter}
                  AND a.dtAnlage >= %(seit)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                """,
                {"adressnr": adressnr, "nachname": f"%{nachname}%",
                 "seit": seit_iso},
            )
            treffer = [{"az": r["az"],
                        "kurzbezeichnung": r["kurzbezeichnung"] or ""}
                       for r in cur.fetchall()]
            return {"verfuegbar": True, "treffer": treffer}
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Akten-Erkennung nicht möglich: %s", e)
        return {"verfuegbar": False, "treffer": []}
    except Exception as e:
        logger.warning("Akten-Erkennung fehlgeschlagen: %s", e)
        return {"verfuegbar": False, "treffer": []}
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_ramicro_aktenanlage.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/ramicro/adress_service.py backend/ramicro/akten_erkennung.py backend/tests/test_ramicro_aktenanlage.py
git commit -m "feat(aktenanlage): RA-MICRO-Helfer Adress-Details + Akten-Erkennung (read-only)" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Service + Blueprint `/aktenanlage` (Vorgänge)

**Files:**
- Create: `backend/services/aktenanlage_service.py`
- Create: `backend/routers/aktenanlage_routes.py`
- Modify: `backend/app.py` (Import + `app.register_blueprint(aktenanlage_bp)` alphabetisch bei den anderen)
- Test: `backend/tests/test_aktenanlage_routes.py` (erweitern)

**Interfaces:**
- Consumes: `schreibe_oma_xml` (Task 2), `finde_neue_akten` (Task 3), `erstelle_oder_hole_akte(az, bearbeiter_id=None, ..., unfalldatum="", unfallort=None, ...)` aus `backend/models/akte.py`.
- Produces (Service):
  - `class VorgangExistiertFehler(Exception)`
  - `lege_vorgang_an(formular, intake_dokument_id=None, zustellung_id=None, benutzer_id=None) -> dict` — wirft `ValueError` (Pflichtfelder), `VorgangExistiertFehler` (laufender Vorgang zum selben Intake-Dokument), `OSError` (Ordner).
  - `hole_offene_vorgaenge() -> dict` mit `{"vorgaenge": [...], "ramicro_verfuegbar": bool}`; Vorgangs-Dict-Keys: `id, intake_dokument_id, zustellung_id, status, mandant_name, erkanntes_az, kandidaten, angelegt_am, angelegt_vor_s, warnung`.
  - `brich_vorgang_ab(vorgang_id) -> bool` (löscht XML-Datei, Status `abgebrochen`).
  - `schliesse_vorgang_ab(vorgang_id) -> bool` (nur aus `akte_erkannt`, Status `abgeschlossen`).
  - `schliesse_vorgaenge_bei_freigabe(intake_dokument_id, akte_az) -> dict | None` mit `{"geschlossen": [ids], "hinweis": str|None}`.
- Produces (Routen): `POST /aktenanlage` (201, Body `{intake_dokument_id?, zustellung_id?, formular}`) · `GET /aktenanlage/offen` · `POST /aktenanlage/<id>/abbrechen` · `POST /aktenanlage/<id>/abschliessen`.

- [ ] **Step 1: Failing Tests ergänzen**

In `backend/tests/test_aktenanlage_routes.py` anhängen:

```python
def _lege_intake_an(sha_suffix="a", klasse="gutachten"):
    from backend.db.database import get_connection
    uploads = os.environ["UPLOAD_DIR"]
    os.makedirs(uploads, exist_ok=True)
    pfad = os.path.join(uploads, f"arbeit_{sha_suffix}.pdf")
    with open(pfad, "wb") as f:
        f.write(b"%PDF-1.4\n%dummy\n")
    sha = (sha_suffix * 64)[:64]
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO intake_dokumente "
            "(sha256, arbeitskopie_pfad, klasse, klasse_quelle, konfidenz, "
            " queue_status, parse_json, registry_version) "
            "VALUES (?, ?, ?, 'auto', 0.9, 'bereit_zur_review', '{}', 'v1')",
            (sha, pfad, klasse),
        )
        return cur.lastrowid


def _lege_zustellung_an(intake_id, parent_id=None, absender="x@svb-cassese.de",
                        signale=None):
    from backend.db.database import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO zustellungen "
            "(intake_dokument_id, quelle, absender, parent_id, signale_json) "
            "VALUES (?, 'imap', ?, ?, ?)",
            (intake_id, absender, parent_id,
             json.dumps(signale or {})),
        )
        return cur.lastrowid


class TestAktenanlageEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = _setup("endpoints")
        self.headers = _auth_header(self.client)

    def _anlegen(self, intake_id=None, zustellung_id=None, formular=None):
        return self.client.post("/aktenanlage", headers=self.headers, json={
            "intake_dokument_id": intake_id,
            "zustellung_id": zustellung_id,
            "formular": formular or FORMULAR,
        })

    def test_anlegen_erzeugt_vorgang_und_xml(self):
        r = self._anlegen()
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        v = r.get_json()["vorgang"]
        self.assertEqual(v["status"], "laeuft")
        self.assertEqual(v["mandant_name"], "Abdessamad Achkour Zejli")
        xmls = [f for f in os.listdir(os.environ["OMA_EXPORT_PFAD"])
                if f.endswith(".xml")]
        self.assertEqual(len(xmls), 1)

    def test_anlegen_ohne_nachname_422(self):
        f = {**FORMULAR, "mandant": {**FORMULAR["mandant"], "nachname": ""}}
        r = self._anlegen(formular=f)
        self.assertEqual(r.status_code, 422)

    def test_anlegen_ohne_unfalldatum_422(self):
        f = {**FORMULAR, "unfall": {**FORMULAR["unfall"], "unfalldatum": ""}}
        r = self._anlegen(formular=f)
        self.assertEqual(r.status_code, 422)

    def test_doppelter_vorgang_pro_intake_409(self):
        did = _lege_intake_an("d")
        zid = _lege_zustellung_an(did)
        self.assertEqual(self._anlegen(did, zid).status_code, 201)
        self.assertEqual(self._anlegen(did, zid).status_code, 409)

    def test_offen_erkennung_eindeutig(self):
        did = _lege_intake_an("e")
        zid = _lege_zustellung_an(did)
        self._anlegen(did, zid)
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True,
                                 "treffer": [{"az": "301/26",
                                              "kurzbezeichnung": "Zejli"}]}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ramicro_verfuegbar"])
        v = d["vorgaenge"][0]
        self.assertEqual(v["status"], "akte_erkannt")
        self.assertEqual(v["erkanntes_az"], "301/26")

    def test_offen_erkennung_mehrdeutig_bleibt_laeuft(self):
        did = _lege_intake_an("f")
        self._anlegen(did, _lege_zustellung_an(did))
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True,
                                 "treffer": [{"az": "301/26",
                                              "kurzbezeichnung": ""},
                                             {"az": "302/26",
                                              "kurzbezeichnung": ""}]}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        v = r.get_json()["vorgaenge"][0]
        self.assertEqual(v["status"], "laeuft")
        self.assertEqual([k["az"] for k in v["kandidaten"]],
                         ["301/26", "302/26"])

    def test_offen_ramicro_offline(self):
        did = _lege_intake_an("g")
        self._anlegen(did, _lege_zustellung_an(did))
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": False, "treffer": []}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        d = r.get_json()
        self.assertFalse(d["ramicro_verfuegbar"])
        self.assertEqual(d["vorgaenge"][0]["status"], "laeuft")

    def test_leerer_vorgang_erkannt_legt_schattenakte_an(self):
        self._anlegen()
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True,
                                 "treffer": [{"az": "305/26",
                                              "kurzbezeichnung": ""}]}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        v = r.get_json()["vorgaenge"][0]
        self.assertEqual(v["status"], "akte_erkannt")
        from backend.db.database import get_connection
        with get_connection() as conn:
            akte = conn.execute(
                "SELECT unfalldatum, unfallort FROM unfallakte WHERE az=?",
                ("305/26",)).fetchone()
        self.assertIsNotNone(akte)
        self.assertEqual(akte["unfalldatum"], "2026-04-10")
        self.assertEqual(akte["unfallort"], "Offenbach")

    def test_abbrechen_loescht_xml(self):
        r = self._anlegen()
        vid = r.get_json()["vorgang"]["id"]
        xmls_vor = [f for f in os.listdir(os.environ["OMA_EXPORT_PFAD"])
                    if f.endswith(".xml")]
        self.assertEqual(len(xmls_vor), 1)
        r2 = self.client.post(f"/aktenanlage/{vid}/abbrechen",
                              headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        xmls_nach = [f for f in os.listdir(os.environ["OMA_EXPORT_PFAD"])
                     if f.endswith(".xml")]
        self.assertEqual(xmls_nach, [])
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True, "treffer": []}):
            offen = self.client.get("/aktenanlage/offen",
                                    headers=self.headers).get_json()
        self.assertEqual(offen["vorgaenge"], [])

    def test_abschliessen_nur_aus_akte_erkannt(self):
        r = self._anlegen()
        vid = r.get_json()["vorgang"]["id"]
        r2 = self.client.post(f"/aktenanlage/{vid}/abschliessen",
                              headers=self.headers)
        self.assertEqual(r2.status_code, 409)
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -v`
Expected: neue Tests FAIL mit 404 (`/aktenanlage` existiert nicht)

- [ ] **Step 3: Service implementieren**

`backend/services/aktenanlage_service.py`:

```python
"""Aktenanlage-Vorgaenge: OMA-XML schreiben, RA-MICRO-Erkennung, Abschluss."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from ..db.database import get_connection
from ..ramicro.oma_xml import schreibe_oma_xml
from ..ramicro.akten_erkennung import finde_neue_akten

logger = logging.getLogger(__name__)

WARN_SEKUNDEN = 15 * 60


class VorgangExistiertFehler(Exception):
    pass


def _export_ordner() -> Path:
    return Path(os.environ.get("OMA_EXPORT_PFAD", "/app/oma_export"))


def _sekunden_seit(ts: str) -> int:
    try:
        t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return max(0, int((datetime.now() - t).total_seconds()))
    except Exception:
        return 0


def _vorgang_dict(row: dict, kandidaten=None) -> dict:
    name = " ".join(x for x in (row["mandant_vorname"],
                                row["mandant_nachname"]) if x)
    vor_s = _sekunden_seit(row["angelegt_am"])
    return {
        "id": row["id"],
        "intake_dokument_id": row["intake_dokument_id"],
        "zustellung_id": row["zustellung_id"],
        "status": row["status"],
        "mandant_name": name,
        "erkanntes_az": row["erkanntes_az"],
        "kandidaten": kandidaten or [],
        "angelegt_am": row["angelegt_am"],
        "angelegt_vor_s": vor_s,
        "warnung": row["status"] == "laeuft" and vor_s > WARN_SEKUNDEN,
    }


def hole_vorgang(vorgang_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM aktenanlage_vorgaenge WHERE id=?",
            (vorgang_id,)).fetchone()
    return _vorgang_dict(dict(row)) if row else None


def lege_vorgang_an(formular: dict, intake_dokument_id=None,
                    zustellung_id=None, benutzer_id=None) -> dict:
    mandant = formular.get("mandant") or {}
    unfall = formular.get("unfall") or {}
    nachname = (mandant.get("nachname") or "").strip()
    if not nachname:
        raise ValueError("Mandant-Nachname ist Pflicht.")
    if not (unfall.get("unfalldatum") or "").strip():
        raise ValueError("Unfalldatum ist Pflicht.")

    if intake_dokument_id is not None:
        with get_connection() as conn:
            offen = conn.execute(
                "SELECT id FROM aktenanlage_vorgaenge "
                "WHERE intake_dokument_id=? "
                "  AND status IN ('laeuft','akte_erkannt')",
                (intake_dokument_id,)).fetchone()
        if offen:
            raise VorgangExistiertFehler(
                f"Für dieses Dokument läuft bereits Aktenanlage-Vorgang "
                f"{offen['id']}.")

    xml_pfad = schreibe_oma_xml(formular, _export_ordner())

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO aktenanlage_vorgaenge "
            "(intake_dokument_id, zustellung_id, formular_json, xml_pfad, "
            " mandant_nachname, mandant_vorname, mandant_adressnr, "
            " angelegt_von) VALUES (?,?,?,?,?,?,?,?)",
            (intake_dokument_id, zustellung_id, json.dumps(formular),
             str(xml_pfad), nachname,
             (mandant.get("vorname") or "").strip() or None,
             (mandant.get("bekannt_adressnr") or "").strip() or None,
             benutzer_id),
        )
        vorgang_id = cur.lastrowid
    logger.info("Aktenanlage-Vorgang %s angelegt (XML: %s)",
                vorgang_id, xml_pfad)
    return hole_vorgang(vorgang_id)


def _uebernimm_unfalldaten(akte_az: str, formular_json: str) -> None:
    try:
        unfall = (json.loads(formular_json).get("unfall") or {})
    except Exception:
        unfall = {}
    with get_connection() as conn:
        if (unfall.get("unfalldatum") or "").strip():
            conn.execute(
                "UPDATE unfallakte SET unfalldatum=? "
                "WHERE az=? AND (unfalldatum IS NULL OR unfalldatum='')",
                (unfall["unfalldatum"].strip(), akte_az))
        if (unfall.get("unfallort") or "").strip():
            conn.execute(
                "UPDATE unfallakte SET unfallort=? "
                "WHERE az=? AND (unfallort IS NULL OR unfallort='')",
                (unfall["unfallort"].strip(), akte_az))


def hole_offene_vorgaenge() -> dict:
    with get_connection() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM aktenanlage_vorgaenge "
            "WHERE status IN ('laeuft','akte_erkannt') ORDER BY id")]

    vorgaenge = []
    ramicro_ok = True
    for row in rows:
        kandidaten = []
        if row["status"] == "laeuft":
            erg = finde_neue_akten(row["angelegt_am"],
                                   nachname=row["mandant_nachname"],
                                   adressnr=row["mandant_adressnr"] or "")
            if not erg["verfuegbar"]:
                ramicro_ok = False
            elif len(erg["treffer"]) == 1:
                az = erg["treffer"][0]["az"]
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE aktenanlage_vorgaenge "
                        "SET status='akte_erkannt', erkanntes_az=?, "
                        "    erkannt_am=datetime('now','localtime') "
                        "WHERE id=?", (az, row["id"]))
                row["status"] = "akte_erkannt"
                row["erkanntes_az"] = az
                if row["intake_dokument_id"] is None:
                    try:
                        from ..models.akte import erstelle_oder_hole_akte
                        erstelle_oder_hole_akte(az)
                        _uebernimm_unfalldaten(az, row["formular_json"])
                    except Exception as exc:
                        logger.warning(
                            "Schattenakte für %s nicht anlegbar: %s", az, exc)
            elif len(erg["treffer"]) > 1:
                kandidaten = erg["treffer"]
        vorgaenge.append(_vorgang_dict(row, kandidaten))
    return {"vorgaenge": vorgaenge, "ramicro_verfuegbar": ramicro_ok}


def brich_vorgang_ab(vorgang_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT xml_pfad, status FROM aktenanlage_vorgaenge WHERE id=?",
            (vorgang_id,)).fetchone()
        if not row or row["status"] not in ("laeuft", "akte_erkannt"):
            return False
        conn.execute(
            "UPDATE aktenanlage_vorgaenge SET status='abgebrochen' "
            "WHERE id=?", (vorgang_id,))
    try:
        Path(row["xml_pfad"]).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("XML %s nicht löschbar: %s", row["xml_pfad"], exc)
    return True


def schliesse_vorgang_ab(vorgang_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE aktenanlage_vorgaenge SET status='abgeschlossen' "
            "WHERE id=? AND status='akte_erkannt'", (vorgang_id,))
        return cur.rowcount > 0


def schliesse_vorgaenge_bei_freigabe(intake_dokument_id: int,
                                     akte_az: str) -> dict | None:
    with get_connection() as conn:
        zust = conn.execute(
            "SELECT id, parent_id FROM zustellungen "
            "WHERE intake_dokument_id=? ORDER BY id LIMIT 1",
            (intake_dokument_id,)).fetchone()
        gruppe = (zust["parent_id"] or zust["id"]) if zust else None
        rows = [dict(r) for r in conn.execute(
            "SELECT v.* FROM aktenanlage_vorgaenge v "
            "LEFT JOIN zustellungen z ON z.id = v.zustellung_id "
            "WHERE v.status IN ('laeuft','akte_erkannt') "
            "  AND (v.intake_dokument_id = ? "
            "       OR (? IS NOT NULL AND COALESCE(z.parent_id, z.id) = ?))",
            (intake_dokument_id, gruppe, gruppe))]

    if not rows:
        return None
    geschlossen = []
    hinweis = None
    for row in rows:
        with get_connection() as conn:
            conn.execute(
                "UPDATE aktenanlage_vorgaenge SET status='abgeschlossen' "
                "WHERE id=?", (row["id"],))
        geschlossen.append(row["id"])
        if row["erkanntes_az"] and row["erkanntes_az"] == akte_az:
            _uebernimm_unfalldaten(akte_az, row["formular_json"])
        elif row["erkanntes_az"]:
            hinweis = (f"Aktenanlage-Vorgang {row['id']} geschlossen; die in "
                       f"RA-MICRO angelegte Akte {row['erkanntes_az']} "
                       "bleibt bestehen.")
    return {"geschlossen": geschlossen, "hinweis": hinweis}
```

- [ ] **Step 4: Blueprint implementieren**

`backend/routers/aktenanlage_routes.py`:

```python
import logging

from flask import Blueprint, g, jsonify, request

from ..auth.middleware import login_erforderlich
from ..services.aktenanlage_service import (
    VorgangExistiertFehler, brich_vorgang_ab, hole_offene_vorgaenge,
    lege_vorgang_an, schliesse_vorgang_ab)

logger = logging.getLogger(__name__)

aktenanlage_bp = Blueprint("aktenanlage", __name__,
                           url_prefix="/aktenanlage")


def _j(daten, status=200):
    return jsonify(daten), status


def _err(msg, status=400, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status


@aktenanlage_bp.route("", methods=["POST"])
@login_erforderlich
def post_anlegen():
    payload = request.get_json(silent=True) or {}
    try:
        vorgang = lege_vorgang_an(
            payload.get("formular") or {},
            intake_dokument_id=payload.get("intake_dokument_id"),
            zustellung_id=payload.get("zustellung_id"),
            benutzer_id=getattr(g, "benutzer_id", None),
        )
    except VorgangExistiertFehler as e:
        return _err(str(e), 409)
    except ValueError as e:
        return _err(str(e), 422)
    except OSError as e:
        return _err(f"OMA-Export-Ordner nicht beschreibbar: {e}", 500)
    return _j({"vorgang": vorgang}, 201)


@aktenanlage_bp.route("/offen", methods=["GET"])
@login_erforderlich
def get_offen():
    return _j(hole_offene_vorgaenge())


@aktenanlage_bp.route("/<int:vorgang_id>/abbrechen", methods=["POST"])
@login_erforderlich
def post_abbrechen(vorgang_id: int):
    if not brich_vorgang_ab(vorgang_id):
        return _err("Vorgang nicht gefunden oder nicht offen.", 409)
    return _j({"ok": True})


@aktenanlage_bp.route("/<int:vorgang_id>/abschliessen", methods=["POST"])
@login_erforderlich
def post_abschliessen(vorgang_id: int):
    if not schliesse_vorgang_ab(vorgang_id):
        return _err("Vorgang nicht im Status 'akte_erkannt'.", 409)
    return _j({"ok": True})
```

In `backend/app.py`: bei den Router-Imports `from .routers.aktenanlage_routes import aktenanlage_bp` ergänzen und in der Registrierungsliste alphabetisch `app.register_blueprint(aktenanlage_bp)` (direkt nach `akten_bp`).

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -v`
Expected: alle Tests passed (2 aus Task 1 + 10 neue)

- [ ] **Step 6: Commit**

```bash
git add backend/services/aktenanlage_service.py backend/routers/aktenanlage_routes.py backend/app.py backend/tests/test_aktenanlage_routes.py
git commit -m "feat(aktenanlage): Service + Blueprint /aktenanlage (Vorgaenge, Erkennung, Abbruch)" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Adress-Endpoints (Dubletten-Check + Gutachter-Vorlage)

**Files:**
- Modify: `backend/routers/aktenanlage_routes.py`
- Test: `backend/tests/test_aktenanlage_routes.py` (erweitern)

**Interfaces:**
- Consumes: `suche_adressen(q)`, `hole_adresse_details(nr)`, `akten_zu_adresse(nr)` aus `backend/ramicro/adress_service.py`; Tabelle `email_absender_vorlagen` (Spalten `name, domain, kategorie, aktiv, ramicro_adressnr`).
- Produces:
  - `GET /aktenanlage/adressen?q=<text>` → `{"treffer": [{adressnr, name, vorname, email}]}`
  - `GET /aktenanlage/adresse/<int:adressnr>` → `{"adresse": {...}|null, "akten": [{az, kurzbezeichnung}]}`
  - `GET /aktenanlage/gutachter-vorlage?zustellung_id=<id>` → `{"vorlage": {name, adressnr, adresse}|null}`

- [ ] **Step 1: Failing Tests ergänzen**

In `backend/tests/test_aktenanlage_routes.py` anhängen:

```python
class TestAdressEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = _setup("adressen")
        self.headers = _auth_header(self.client)

    def test_adressen_suche(self):
        with patch("backend.routers.aktenanlage_routes.suche_adressen",
                   return_value=[{"adressnr": 12345, "name": "Achkour Zejli",
                                  "vorname": "Abdessamad", "email": ""}]):
            r = self.client.get("/aktenanlage/adressen?q=Achkour",
                                headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["treffer"][0]["adressnr"], 12345)

    def test_adress_detail_mit_akten(self):
        with patch("backend.routers.aktenanlage_routes.hole_adresse_details",
                   return_value={"adressnr": 12345, "anrede": "1",
                                 "name": "Achkour Zejli",
                                 "vorname": "Abdessamad", "firmenzeile": "",
                                 "strasse": "Wiener Straße 61",
                                 "plz": "60599", "ort": "Frankfurt",
                                 "telefon": "", "email": ""}), \
             patch("backend.routers.aktenanlage_routes.akten_zu_adresse",
                   return_value=[{"az": "285/26",
                                  "kurzbezeichnung": "Zejli ./. KRAVAG"}]):
            r = self.client.get("/aktenanlage/adresse/12345",
                                headers=self.headers)
        d = r.get_json()
        self.assertEqual(d["adresse"]["strasse"], "Wiener Straße 61")
        self.assertEqual(d["akten"][0]["az"], "285/26")

    def test_gutachter_vorlage(self):
        from backend.db.database import get_connection
        did = _lege_intake_an("gv")
        zid = _lege_zustellung_an(did, absender="Büro <info@svb-cassese.de>")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO email_absender_vorlagen "
                "(name, domain, kategorie, ramicro_adressnr) "
                "VALUES ('SV-Büro Cassese', 'svb-cassese.de', 'gutachter', "
                "        '777')")
        with patch("backend.routers.aktenanlage_routes.hole_adresse_details",
                   return_value={"adressnr": 777, "anrede": "4",
                                 "name": "Cassese", "vorname": "",
                                 "firmenzeile": "SVB Cassese",
                                 "strasse": "Frankfurter Straße 97",
                                 "plz": "63067", "ort": "Offenbach",
                                 "telefon": "", "email": ""}):
            r = self.client.get(
                f"/aktenanlage/gutachter-vorlage?zustellung_id={zid}",
                headers=self.headers)
        v = r.get_json()["vorlage"]
        self.assertEqual(v["name"], "SV-Büro Cassese")
        self.assertEqual(v["adresse"]["plz"], "63067")

    def test_gutachter_vorlage_unbekannte_domain(self):
        did = _lege_intake_an("gu")
        zid = _lege_zustellung_an(did, absender="wer@unbekannt.de")
        r = self.client.get(
            f"/aktenanlage/gutachter-vorlage?zustellung_id={zid}",
            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json()["vorlage"])
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -k "Adress or gutachter" -v`
Expected: FAIL mit 404

- [ ] **Step 3: Routen implementieren**

In `backend/routers/aktenanlage_routes.py` — Imports ergänzen:

```python
import re

from ..db.database import get_connection
from ..ramicro.adress_service import (akten_zu_adresse, hole_adresse_details,
                                      suche_adressen)
```

Routen anhängen:

```python
@aktenanlage_bp.route("/adressen", methods=["GET"])
@login_erforderlich
def get_adressen():
    q = (request.args.get("q") or "").strip()
    return _j({"treffer": suche_adressen(q)})


@aktenanlage_bp.route("/adresse/<int:adressnr>", methods=["GET"])
@login_erforderlich
def get_adresse(adressnr: int):
    return _j({"adresse": hole_adresse_details(adressnr),
               "akten": akten_zu_adresse(adressnr)})


def _domain_aus_absender(absender: str) -> str:
    m = re.search(r"@([A-Za-z0-9.-]+)", absender or "")
    return m.group(1).lower().rstrip(">").strip() if m else ""


@aktenanlage_bp.route("/gutachter-vorlage", methods=["GET"])
@login_erforderlich
def get_gutachter_vorlage():
    zustellung_id = request.args.get("zustellung_id", type=int)
    if not zustellung_id:
        return _err("zustellung_id fehlt", 422)
    with get_connection() as conn:
        zust = conn.execute(
            "SELECT absender FROM zustellungen WHERE id=?",
            (zustellung_id,)).fetchone()
        domain = _domain_aus_absender(zust["absender"] if zust else "")
        vorlage = None
        if domain:
            vorlage = conn.execute(
                "SELECT name, ramicro_adressnr FROM email_absender_vorlagen "
                "WHERE LOWER(domain)=? AND kategorie='gutachter' AND aktiv=1",
                (domain,)).fetchone()
    if not vorlage:
        return _j({"vorlage": None})
    adresse = None
    if vorlage["ramicro_adressnr"]:
        try:
            adresse = hole_adresse_details(int(vorlage["ramicro_adressnr"]))
        except (TypeError, ValueError):
            adresse = None
    return _j({"vorlage": {"name": vorlage["name"],
                           "adressnr": vorlage["ramicro_adressnr"],
                           "adresse": adresse}})
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -v`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/aktenanlage_routes.py backend/tests/test_aktenanlage_routes.py
git commit -m "feat(aktenanlage): Adress-Endpoints Dubletten-Check + Gutachter-Vorlage" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Freigabe-Hook — Vorgang schließen + Unfalldaten übernehmen

**Files:**
- Modify: `backend/routers/intake_routes.py` (in `post_freigabe`, nach dem `_schreibe_freigabe_ereignisse`-Aufruf, vor der Response)
- Test: `backend/tests/test_aktenanlage_routes.py` (erweitern)

**Interfaces:**
- Consumes: `schliesse_vorgaenge_bei_freigabe(intake_dokument_id, akte_az)` (Task 4).
- Produces: `POST /intake/dokument/<id>/freigabe`-Response erhält zusätzliches Feld `"aktenanlage": {geschlossen, hinweis} | null`.

- [ ] **Step 1: Failing Tests ergänzen**

In `backend/tests/test_aktenanlage_routes.py` anhängen:

```python
class TestFreigabeHook(unittest.TestCase):
    def setUp(self):
        self.client = _setup("hook")
        self.headers = _auth_header(self.client)

    def _vorgang_mit_gruppe(self):
        body = _lege_intake_an("h1", klasse="sonstiges")
        z_body = _lege_zustellung_an(body)
        gutachten = _lege_intake_an("h2")
        z_g = _lege_zustellung_an(gutachten, parent_id=z_body)
        rechnung = _lege_intake_an("h3", klasse="rechnung")
        _lege_zustellung_an(rechnung, parent_id=z_body)
        r = self.client.post("/aktenanlage", headers=self.headers, json={
            "intake_dokument_id": gutachten, "zustellung_id": z_g,
            "formular": FORMULAR})
        vid = r.get_json()["vorgang"]["id"]
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE aktenanlage_vorgaenge "
                "SET status='akte_erkannt', erkanntes_az='310/26' "
                "WHERE id=?", (vid,))
        return vid, gutachten, rechnung

    def test_freigabe_auf_erkanntes_az_schliesst_und_uebernimmt(self):
        vid, gutachten, _ = self._vorgang_mit_gruppe()
        r = self.client.post(f"/intake/dokument/{gutachten}/freigabe",
                             headers=self.headers,
                             json={"akte_az": "310/26"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        d = r.get_json()
        self.assertIn(vid, d["aktenanlage"]["geschlossen"])
        from backend.db.database import get_connection
        with get_connection() as conn:
            v = conn.execute(
                "SELECT status FROM aktenanlage_vorgaenge WHERE id=?",
                (vid,)).fetchone()
            akte = conn.execute(
                "SELECT unfalldatum, unfallort FROM unfallakte WHERE az=?",
                ("310/26",)).fetchone()
        self.assertEqual(v["status"], "abgeschlossen")
        self.assertEqual(akte["unfalldatum"], "2026-04-10")
        self.assertEqual(akte["unfallort"], "Offenbach")

    def test_geschwister_freigabe_schliesst_vorgang_der_gruppe(self):
        vid, _, rechnung = self._vorgang_mit_gruppe()
        r = self.client.post(f"/intake/dokument/{rechnung}/freigabe",
                             headers=self.headers,
                             json={"akte_az": "310/26"})
        self.assertEqual(r.status_code, 200)
        self.assertIn(vid, r.get_json()["aktenanlage"]["geschlossen"])

    def test_freigabe_auf_anderes_az_liefert_hinweis(self):
        vid, gutachten, _ = self._vorgang_mit_gruppe()
        r = self.client.post(f"/intake/dokument/{gutachten}/freigabe",
                             headers=self.headers,
                             json={"akte_az": "44/22"})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()["aktenanlage"]
        self.assertIn(vid, d["geschlossen"])
        self.assertIn("310/26", d["hinweis"])

    def test_freigabe_ohne_vorgang_liefert_null(self):
        did = _lege_intake_an("h4")
        _lege_zustellung_an(did)
        r = self.client.post(f"/intake/dokument/{did}/freigabe",
                             headers=self.headers,
                             json={"akte_az": "44/22"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json()["aktenanlage"])
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -k "Hook" -v`
Expected: FAIL (`KeyError: 'aktenanlage'`)

- [ ] **Step 3: Hook implementieren**

In `backend/routers/intake_routes.py`, in `post_freigabe` direkt vor dem abschließenden `return _j({...})` (nach der Fragebogen-Übernahme):

```python
    aktenanlage_info = None
    try:
        from ..services.aktenanlage_service import (
            schliesse_vorgaenge_bei_freigabe)
        aktenanlage_info = schliesse_vorgaenge_bei_freigabe(intake_id, akte_az)
    except Exception as exc:
        logger.warning("Aktenanlage-Abschluss nach Freigabe fehlgeschlagen: %s",
                       exc)
```

Und im Response-Dict das Feld ergänzen:

```python
    return _j({
        "ok": True,
        "dokument_id": dokument_id,
        "freigabe_id": freigabe_id,
        "akte_az": akte_az,
        "fragebogen_uebernahme": uebernahme_ergebnis,
        "aktenanlage": aktenanlage_info,
    })
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen (inkl. Bestandstests)**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py backend/tests/test_intake_routes.py -v`
Expected: alle passed (Bestand darf nicht brechen)

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_aktenanlage_routes.py
git commit -m "feat(aktenanlage): Freigabe-Hook schliesst Vorgaenge + Unfalldaten-Uebernahme" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Queue-Response um `absender_kategorie` erweitern

**Files:**
- Modify: `backend/routers/intake_routes.py` (`hole_queue`)
- Test: `backend/tests/test_aktenanlage_routes.py` (erweitern)

**Interfaces:**
- Produces: Jeder Queue-Eintrag aus `GET /intake/queue` enthält zusätzlich `"absender_kategorie": str|null` (aus `zustellungen.signale_json`, Key `absender_kategorie`, top-level).

- [ ] **Step 1: Failing Test ergänzen**

```python
class TestQueueAbsenderKategorie(unittest.TestCase):
    def setUp(self):
        self.client = _setup("queuekat")
        self.headers = _auth_header(self.client)

    def test_queue_liefert_absender_kategorie(self):
        did = _lege_intake_an("q1")
        _lege_zustellung_an(did, signale={"absender_kategorie": "gutachter"})
        r = self.client.get("/intake/queue", headers=self.headers)
        eintrag = [e for e in r.get_json()["eintraege"]
                   if e["id"] == did][0]
        self.assertEqual(eintrag["absender_kategorie"], "gutachter")

    def test_queue_ohne_signal_null(self):
        did = _lege_intake_an("q2")
        _lege_zustellung_an(did, signale={})
        r = self.client.get("/intake/queue", headers=self.headers)
        eintrag = [e for e in r.get_json()["eintraege"]
                   if e["id"] == did][0]
        self.assertIsNone(eintrag["absender_kategorie"])
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -k "AbsenderKategorie" -v`
Expected: FAIL (`KeyError: 'absender_kategorie'`)

- [ ] **Step 3: Implementieren**

In `hole_queue` (`backend/routers/intake_routes.py`) im SELECT nach `"       z.betreff AS betreff "` ergänzen:

```python
            "       , json_extract(z.signale_json, '$.absender_kategorie') "
            "         AS absender_kategorie "
```

und im `eintraege.append({...})`-Dict:

```python
            "absender_kategorie": r["absender_kategorie"],
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py backend/tests/test_intake_routes.py -v`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_aktenanlage_routes.py
git commit -m "feat(aktenanlage): Queue liefert absender_kategorie aus signale_json" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Gutachten-Schema um Auftraggeber-Felder erweitern

**Files:**
- Modify: `backend/registry/klassen/gutachten.yaml` (im `schema:`-Block)
- Test: `backend/tests/test_aktenanlage_routes.py` (erweitern)

**Interfaces:**
- Produces: `parse_json.felder` von Gutachten kann zusätzlich enthalten: `auftraggeber_anrede, auftraggeber_vorname, auftraggeber_nachname, auftraggeber_strasse, auftraggeber_plz, auftraggeber_ort` (alle `string`; LLM-Extraktion läuft über das Schema automatisch mit, `extrahiere_felder` iteriert `schema.keys()`).

- [ ] **Step 1: Failing Test ergänzen**

```python
class TestGutachtenSchema(unittest.TestCase):
    def test_auftraggeber_felder_im_schema(self):
        import yaml
        pfad = os.path.join(os.path.dirname(__file__), "..",
                            "registry", "klassen", "gutachten.yaml")
        with open(pfad, encoding="utf-8") as f:
            daten = yaml.safe_load(f)
        for feld in ("auftraggeber_anrede", "auftraggeber_vorname",
                     "auftraggeber_nachname", "auftraggeber_strasse",
                     "auftraggeber_plz", "auftraggeber_ort"):
            self.assertIn(feld, daten["schema"], feld)
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py -k "GutachtenSchema" -v`
Expected: FAIL

- [ ] **Step 3: Schema erweitern**

In `backend/registry/klassen/gutachten.yaml` im `schema:`-Block direkt nach `gutachter: string` einfügen (Einrückung wie die Nachbarzeilen):

```yaml
  auftraggeber_anrede: string
  auftraggeber_vorname: string
  auftraggeber_nachname: string
  auftraggeber_strasse: string
  auftraggeber_plz: string
  auftraggeber_ort: string
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen (inkl. Registry-Loader-Bestand)**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_aktenanlage_routes.py backend/tests/test_intake_routes.py -v`
Expected: alle passed

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klassen/gutachten.yaml backend/tests/test_aktenanlage_routes.py
git commit -m "feat(aktenanlage): gutachten.yaml um Auftraggeber-Felder erweitert" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Frontend — `apiAktenanlage` + `AktenanlageDialog`

**Files:**
- Modify: `frontend/src/api.js` (neues Modul nach `apiIntake`)
- Create: `frontend/src/components/AktenanlageDialog.jsx`
- Test: `frontend/src/components/AktenanlageDialog.test.jsx`

**Interfaces:**
- Consumes: Endpoints aus Task 4/5; `request()` aus `api.js`; Theme `T`.
- Produces:
  - `apiAktenanlage` mit Methoden `anlegen(payload)`, `offen()`, `abbrechen(id)`, `abschliessen(id)`, `adressSuche(q)`, `adressDetail(nr)`, `gutachterVorlage(zustellungId)`.
  - `AktenanlageDialog({ intakeDokumentId=null, zustellungId=null, prefill=null, onClose, onAngelegt, onUebernehmeAz=null })` — ruft bei Erfolg `onAngelegt(vorgang)`; `onUebernehmeAz(az)` beim Klick „Dokument dieser Akte zuordnen" im Dubletten-Check.
  - Exportierte Helfer: `LEERES_FORMULAR`, `mischeVorbefuellung(prefill)`, `validiereFormular(felder)`, `baueVorbefuellung(detail, absenderInfo)`.

- [ ] **Step 1: Failing Tests schreiben**

`frontend/src/components/AktenanlageDialog.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({
  apiAktenanlage: {
    anlegen: vi.fn(),
    adressSuche: vi.fn().mockResolvedValue({ treffer: [] }),
    adressDetail: vi.fn(),
    gutachterVorlage: vi.fn(),
  },
}));

import AktenanlageDialog, {
  LEERES_FORMULAR, mischeVorbefuellung, validiereFormular, baueVorbefuellung,
} from "./AktenanlageDialog.jsx";

describe("validiereFormular", () => {
  it("meldet fehlenden Nachnamen und fehlendes Unfalldatum", () => {
    const e = validiereFormular(LEERES_FORMULAR);
    expect(e.nachname).toBeTruthy();
    expect(e.unfalldatum).toBeTruthy();
  });
  it("ist leer bei gefuellten Pflichtfeldern", () => {
    const f = mischeVorbefuellung({
      mandant: { nachname: "Zejli" },
      unfall: { unfalldatum: "2026-04-10" },
    });
    expect(validiereFormular(f)).toEqual({});
  });
});

describe("baueVorbefuellung", () => {
  const detail = {
    parse: {
      felder: {
        auftraggeber_anrede: "herr",
        auftraggeber_vorname: "Abdessamad",
        auftraggeber_nachname: "Achkour Zejli",
        auftraggeber_strasse: "Wiener Straße 61",
        auftraggeber_plz: "60599",
        auftraggeber_ort: "Frankfurt am Main",
        schadendatum: "2026-04-10",
        kennzeichen: "F-RX 4243",
        versicherung_name: "KRAVAG",
        schadennummer_versicherung: "45-11",
        sv_buero: "SVB Cassese",
        auftragsnummer: "GA-202604-1189",
      },
    },
  };
  it("mappt Gutachten-Felder in das Formular", () => {
    const f = baueVorbefuellung(detail, null);
    expect(f.mandant.nachname).toBe("Achkour Zejli");
    expect(f.mandant.plz).toBe("60599");
    expect(f.unfall.unfalldatum).toBe("2026-04-10");
    expect(f.unfall.kennzeichen).toBe("F-RX 4243");
    expect(f.versicherung.name).toBe("KRAVAG");
    expect(f.versicherung.schadennummer).toBe("45-11");
    expect(f.gutachter.bezeichnung).toBe("SVB Cassese");
    expect(f.gutachter.gutachten_nr).toBe("GA-202604-1189");
  });
  it("Identifier-Treffer ueberschreibt Gutachter-Bezeichnung und Adresse", () => {
    const info = {
      name: "KFZ-SV-Büro Cassese",
      adresse: { strasse: "Frankfurter Straße 97", plz: "63067",
                 ort: "Offenbach", telefon: "0151", email: "i@c.de" },
    };
    const f = baueVorbefuellung(detail, info);
    expect(f.gutachter.bezeichnung).toBe("KFZ-SV-Büro Cassese");
    expect(f.gutachter.plz).toBe("63067");
  });
  it("kommt mit leerem Detail klar", () => {
    const f = baueVorbefuellung(null, null);
    expect(f.mandant.nachname).toBe("");
  });
});

describe("AktenanlageDialog Rendering", () => {
  it("zeigt Pflichtfelder und Buttons", () => {
    render(<AktenanlageDialog onClose={() => {}} onAngelegt={() => {}} />);
    expect(screen.getByText("Neue Akte anlegen (RA-MICRO)")).toBeTruthy();
    expect(screen.getAllByText(/Nachname/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Unfalldatum/)).toBeTruthy();
    expect(screen.getByText("Akte anlegen")).toBeTruthy();
    expect(screen.getByText("Abbrechen")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd frontend; npm test -- src/components/AktenanlageDialog.test.jsx`
Expected: FAIL (Modul existiert nicht)

- [ ] **Step 3: `apiAktenanlage` in `api.js` ergänzen**

Direkt nach dem `apiIntake`-Objekt in `frontend/src/api.js`:

```jsx
export const apiAktenanlage = {
  anlegen:      (payload) => request('/aktenanlage', {
    method: 'POST', body: JSON.stringify(payload) }),
  offen:        ()        => request('/aktenanlage/offen'),
  abbrechen:    (id)      => request(`/aktenanlage/${id}/abbrechen`, { method: 'POST' }),
  abschliessen: (id)      => request(`/aktenanlage/${id}/abschliessen`, { method: 'POST' }),
  adressSuche:  (q)       => request(`/aktenanlage/adressen?q=${encodeURIComponent(q)}`),
  adressDetail: (nr)      => request(`/aktenanlage/adresse/${nr}`),
  gutachterVorlage: (zustellungId) =>
    request(`/aktenanlage/gutachter-vorlage?zustellung_id=${zustellungId}`),
};
```

- [ ] **Step 4: Dialog implementieren**

`frontend/src/components/AktenanlageDialog.jsx`:

```jsx
import React, { useEffect, useRef, useState } from "react";
import T from "../config/theme.js";
import { apiAktenanlage } from "../api.js";

export const LEERES_FORMULAR = {
  mandant: { anrede: "", titel: "", vorname: "", nachname: "", strasse: "",
             plz: "", ort: "", telefon: "", email: "", geburtstag: "",
             iban: "", bank: "", rsv_name: "", rsv_nummer: "",
             bekannt_adressnr: "" },
  unfall: { unfalldatum: "", unfallort: "", kennzeichen: "" },
  gegner: { anrede: "", vorname: "", nachname: "", strasse: "", plz: "",
            ort: "", kennzeichen: "" },
  versicherung: { name: "", schadennummer: "" },
  gutachter: { bezeichnung: "", strasse: "", plz: "", ort: "", telefon: "",
               email: "", gutachten_nr: "" },
};

export function mischeVorbefuellung(prefill) {
  const basis = JSON.parse(JSON.stringify(LEERES_FORMULAR));
  if (!prefill) return basis;
  for (const gruppe of Object.keys(basis)) {
    Object.assign(basis[gruppe], prefill[gruppe] || {});
  }
  return basis;
}

export function validiereFormular(felder) {
  const e = {};
  if (!(felder.mandant?.nachname || "").trim()) e.nachname = "Pflichtfeld";
  const datum = (felder.unfall?.unfalldatum || "").trim();
  if (!datum) e.unfalldatum = "Pflichtfeld";
  else if (!/^\d{4}-\d{2}-\d{2}$/.test(datum))
    e.unfalldatum = "Format JJJJ-MM-TT";
  return e;
}

export function baueVorbefuellung(detail, absenderInfo) {
  const f = detail?.parse?.felder || {};
  const s = (v) => (v == null ? "" : String(v));
  return mischeVorbefuellung({
    mandant: {
      anrede: s(f.auftraggeber_anrede).toLowerCase(),
      vorname: s(f.auftraggeber_vorname),
      nachname: s(f.auftraggeber_nachname),
      strasse: s(f.auftraggeber_strasse),
      plz: s(f.auftraggeber_plz),
      ort: s(f.auftraggeber_ort),
    },
    unfall: {
      unfalldatum: s(f.schadendatum),
      kennzeichen: s(f.kennzeichen),
    },
    versicherung: {
      name: s(f.versicherung_name),
      schadennummer: s(f.schadennummer_versicherung),
    },
    gutachter: {
      bezeichnung: s(absenderInfo?.name || f.sv_buero || f.gutachter),
      strasse: s(absenderInfo?.adresse?.strasse),
      plz: s(absenderInfo?.adresse?.plz),
      ort: s(absenderInfo?.adresse?.ort),
      telefon: s(absenderInfo?.adresse?.telefon),
      email: s(absenderInfo?.adresse?.email),
      gutachten_nr: s(f.auftragsnummer),
    },
  });
}

const ANREDE_OPTIONEN = [["", "—"], ["herr", "Herr"], ["frau", "Frau"],
                         ["firma", "Firma"]];

export default function AktenanlageDialog({
  intakeDokumentId = null, zustellungId = null, prefill = null,
  onClose, onAngelegt, onUebernehmeAz = null,
}) {
  const [felder, setFelder] = useState(() => mischeVorbefuellung(prefill));
  const [fehler, setFehler] = useState({});
  const [speichert, setSpeichert] = useState(false);
  const [adressTreffer, setAdressTreffer] = useState(null);
  const [adressAkten, setAdressAkten] = useState(null);
  const suchTimer = useRef(null);

  const set = (gruppe, key, wert) =>
    setFelder(f => ({ ...f, [gruppe]: { ...f[gruppe], [key]: wert } }));

  useEffect(() => {
    if (suchTimer.current) clearTimeout(suchTimer.current);
    const q = (felder.mandant.nachname || "").trim();
    if (q.length < 2 || felder.mandant.bekannt_adressnr) {
      setAdressTreffer(null);
      return;
    }
    suchTimer.current = setTimeout(async () => {
      try {
        const d = await apiAktenanlage.adressSuche(q);
        setAdressTreffer(d.treffer || []);
      } catch { setAdressTreffer(null); }
    }, 300);
    return () => suchTimer.current && clearTimeout(suchTimer.current);
  }, [felder.mandant.nachname, felder.mandant.bekannt_adressnr]);

  const uebernehmeAdresse = async (adressnr) => {
    try {
      const d = await apiAktenanlage.adressDetail(adressnr);
      const a = d.adresse;
      if (a) {
        setFelder(f => ({ ...f, mandant: { ...f.mandant,
          anrede: a.anrede === "2" ? "frau" : a.anrede === "4" ? "firma" : "herr",
          vorname: a.vorname || f.mandant.vorname,
          nachname: a.name || f.mandant.nachname,
          strasse: a.strasse || f.mandant.strasse,
          plz: a.plz || f.mandant.plz,
          ort: a.ort || f.mandant.ort,
          telefon: a.telefon || f.mandant.telefon,
          email: a.email || f.mandant.email,
          bekannt_adressnr: String(adressnr),
        }}));
      }
      setAdressAkten(d.akten || []);
      setAdressTreffer(null);
    } catch { /* Anlage bleibt moeglich */ }
  };

  const anlegen = async () => {
    const errs = validiereFormular(felder);
    if (Object.keys(errs).length) { setFehler(errs); return; }
    setSpeichert(true); setFehler({});
    try {
      const res = await apiAktenanlage.anlegen({
        intake_dokument_id: intakeDokumentId,
        zustellung_id: zustellungId,
        formular: felder,
      });
      onAngelegt(res.vorgang);
    } catch (e) {
      setFehler({ allgemein: e?.message || "Fehler bei der Aktenanlage." });
    } finally { setSpeichert(false); }
  };

  const inp = (gruppe, key, label, opts = {}) => (
    <label style={{ display: "block", marginBottom: 8, flex: opts.flex || 1 }}>
      <span style={{ fontSize: T.textXs, color: T.textMuted }}>
        {label}{opts.pflicht ? " *" : ""}
      </span>
      <input
        value={felder[gruppe][key]}
        onChange={e => set(gruppe, key, e.target.value)}
        placeholder={opts.placeholder || ""}
        style={{ width: "100%", boxSizing: "border-box", padding: "6px 10px",
                 border: `1px solid ${opts.fehler ? T.red : T.border}`,
                 borderRadius: 4, fontSize: T.textSm }}
      />
      {opts.fehler && (
        <span style={{ fontSize: T.textXs, color: T.redText }}>
          {opts.fehler}
        </span>
      )}
    </label>
  );

  const gruppeTitel = (text) => (
    <div style={{ fontSize: T.textSm, fontWeight: 600, color: T.navy,
                  margin: "14px 0 6px", borderBottom: `1px solid ${T.border}`,
                  paddingBottom: 4 }}>
      {text}
    </div>
  );

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
               zIndex: 1000, display: "flex", alignItems: "center",
               justifyContent: "center" }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: T.cardBg, borderRadius: 12,
                    boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
                    padding: "1.5rem", width: "100%", maxWidth: 640,
                    maxHeight: "90vh", overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between",
                      alignItems: "center", marginBottom: 8 }}>
          <h2 style={{ margin: 0, fontFamily: T.fontDisplay, color: T.navy,
                       fontSize: T.textLg }}>
            Neue Akte anlegen (RA-MICRO)
          </h2>
          <button onClick={onClose}
            style={{ border: "none", background: "transparent",
                     cursor: "pointer", fontSize: "1.1rem" }}>✕</button>
        </div>
        <div style={{ background: T.amberBg, color: T.amberText,
                      border: `1px solid ${T.amber}`, borderRadius: 4,
                      padding: "6px 10px", fontSize: T.textXs,
                      marginBottom: 10 }}>
          Erzeugt eine OMA-XML im überwachten Ordner — RA-MICRO legt die Akte
          selbstständig an und vergibt das Aktenzeichen.
        </div>

        {gruppeTitel("Mandant")}
        <div style={{ display: "flex", gap: 8 }}>
          <label style={{ display: "block", marginBottom: 8, width: 110 }}>
            <span style={{ fontSize: T.textXs, color: T.textMuted }}>Anrede</span>
            <select value={felder.mandant.anrede}
              onChange={e => set("mandant", "anrede", e.target.value)}
              style={{ width: "100%", padding: "6px 4px",
                       border: `1px solid ${T.border}`, borderRadius: 4,
                       fontSize: T.textSm }}>
              {ANREDE_OPTIONEN.map(([v, t]) =>
                <option key={v} value={v}>{t}</option>)}
            </select>
          </label>
          {inp("mandant", "vorname", "Vorname")}
          {inp("mandant", "nachname", "Nachname",
               { pflicht: true, fehler: fehler.nachname })}
        </div>
        {felder.mandant.bekannt_adressnr && (
          <div style={{ background: T.blueBg, color: T.blueText,
                        borderRadius: 4, padding: "4px 8px",
                        fontSize: T.textXs, marginBottom: 8 }}>
            Bestandsmandant — RA-MICRO Adressnummer{" "}
            {felder.mandant.bekannt_adressnr}
            <button onClick={() => { set("mandant", "bekannt_adressnr", "");
                                     setAdressAkten(null); }}
              style={{ marginLeft: 8, border: "none",
                       background: "transparent", color: T.blueText,
                       cursor: "pointer", textDecoration: "underline",
                       fontSize: T.textXs }}>
              lösen
            </button>
          </div>
        )}
        {adressTreffer && adressTreffer.length > 0 && (
          <div style={{ border: `1px solid ${T.amber}`, background: T.amberBg,
                        borderRadius: 4, padding: 8, marginBottom: 8 }}>
            <div style={{ fontSize: T.textXs, color: T.amberText,
                          marginBottom: 4 }}>
              ⚠ Im RA-MICRO-Adressbestand gefunden — Dublette vermeiden:
            </div>
            {adressTreffer.map(t => (
              <button key={t.adressnr} onClick={() => uebernehmeAdresse(t.adressnr)}
                style={{ display: "block", width: "100%", textAlign: "left",
                         border: "none", background: "transparent",
                         cursor: "pointer", padding: "4px 2px",
                         fontSize: T.textSm }}>
                <code>AdrNr {t.adressnr}</code> — {t.vorname} {t.name}
                {t.email ? ` · ${t.email}` : ""}
              </button>
            ))}
          </div>
        )}
        {adressAkten && adressAkten.length > 0 && (
          <div style={{ border: `1px solid ${T.blue}`, background: T.blueBg,
                        borderRadius: 4, padding: 8, marginBottom: 8 }}>
            <div style={{ fontSize: T.textXs, color: T.blueText,
                          marginBottom: 4 }}>
              Bestehende Akten dieser Person — gehört der Unfall dazu?
            </div>
            {adressAkten.map(a => (
              <div key={a.az} style={{ display: "flex", gap: 8,
                                       alignItems: "center",
                                       fontSize: T.textSm, padding: "2px 0" }}>
                <code>{a.az}</code>
                <span style={{ flex: 1 }}>{a.kurzbezeichnung}</span>
                {onUebernehmeAz && (
                  <button onClick={() => onUebernehmeAz(a.az)}
                    style={{ border: `1px solid ${T.blue}`,
                             background: "transparent", color: T.blueText,
                             borderRadius: 4, padding: "2px 8px",
                             cursor: "pointer", fontSize: T.textXs }}>
                    Dokument dieser Akte zuordnen
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("mandant", "strasse", "Straße Nr.", { flex: 2 })}
          {inp("mandant", "plz", "PLZ")}
          {inp("mandant", "ort", "Ort", { flex: 2 })}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {inp("mandant", "telefon", "Telefon")}
          {inp("mandant", "email", "E-Mail", { flex: 2 })}
        </div>
        <details style={{ marginBottom: 8 }}>
          <summary style={{ fontSize: T.textXs, color: T.textMuted,
                            cursor: "pointer" }}>
            Weitere Mandantendaten (Geburtsdatum, Bank, Rechtsschutz)
          </summary>
          <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
            {inp("mandant", "geburtstag", "Geburtsdatum (JJJJ-MM-TT)")}
            {inp("mandant", "iban", "IBAN", { flex: 2 })}
            {inp("mandant", "bank", "Bank")}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {inp("mandant", "rsv_name", "Rechtsschutzversicherung", { flex: 2 })}
            {inp("mandant", "rsv_nummer", "RSV-Versicherungsnummer")}
          </div>
        </details>

        {gruppeTitel("Unfall")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("unfall", "unfalldatum", "Unfalldatum (JJJJ-MM-TT)",
               { pflicht: true, fehler: fehler.unfalldatum })}
          {inp("unfall", "unfallort", "Unfallort", { flex: 2 })}
          {inp("unfall", "kennzeichen", "Amtl. Kennzeichen")}
        </div>

        {gruppeTitel("Gegner (optional)")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gegner", "vorname", "Vorname")}
          {inp("gegner", "nachname", "Nachname")}
          {inp("gegner", "kennzeichen", "Kennzeichen")}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gegner", "strasse", "Straße Nr.", { flex: 2 })}
          {inp("gegner", "plz", "PLZ")}
          {inp("gegner", "ort", "Ort", { flex: 2 })}
        </div>

        {gruppeTitel("Gegnerische Versicherung (optional)")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("versicherung", "name", "Name", { flex: 2 })}
          {inp("versicherung", "schadennummer", "Schadennummer")}
        </div>

        {gruppeTitel("Gutachter")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gutachter", "bezeichnung", "Bezeichnung", { flex: 2 })}
          {inp("gutachter", "gutachten_nr", "Gutachten-Nr.")}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gutachter", "strasse", "Straße Nr.", { flex: 2 })}
          {inp("gutachter", "plz", "PLZ")}
          {inp("gutachter", "ort", "Ort", { flex: 2 })}
        </div>

        {fehler.allgemein && (
          <div style={{ background: T.redBg, color: T.redText,
                        border: `1px solid ${T.redLight}`, borderRadius: 4,
                        padding: "8px 10px", fontSize: T.textSm,
                        marginBottom: 8 }}>
            {fehler.allgemein}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end",
                      marginTop: 12 }}>
          <button onClick={onClose} disabled={speichert}
            style={{ padding: "8px 16px", background: T.offWhite,
                     border: `1px solid ${T.border}`, borderRadius: 4,
                     cursor: speichert ? "wait" : "pointer" }}>
            Abbrechen
          </button>
          <button onClick={anlegen} disabled={speichert}
            style={{ padding: "8px 16px", background: T.accent,
                     color: T.white, border: "none", borderRadius: 4,
                     cursor: speichert ? "wait" : "pointer",
                     fontWeight: 600 }}>
            {speichert ? "Wird angelegt …" : "Akte anlegen"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `cd frontend; npm test -- src/components/AktenanlageDialog.test.jsx`
Expected: alle passed

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/components/AktenanlageDialog.jsx frontend/src/components/AktenanlageDialog.test.jsx
git commit -m "feat(aktenanlage): apiAktenanlage + AktenanlageDialog mit Dubletten-Check" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: ReviewQueue-Integration (Banner, Button, Chip, Status-Leiste)

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx`
- Test: `frontend/src/views/ReviewQueueView.aktenanlage.test.jsx`

**Interfaces:**
- Consumes: `apiAktenanlage` (Task 9), `AktenanlageDialog` + `baueVorbefuellung` (Task 9), Queue-Feld `absender_kategorie` (Task 7), Vorgangs-Dicts aus `GET /aktenanlage/offen` (Task 4).
- Produces (exportierte Helfer/Komponenten für Tests): `zeigeAktenanlageVorschlag(item)`, `gruppenKey(item)`, `vorgangFuerEintrag(item, vorgaenge, queue)`, `AnlageChip({ vorgang })`, `AktenanlageLeiste({ vorgaenge, ramicroVerfuegbar, onSpringe, onOeffneAkte, onAbbrechen })`.

- [ ] **Step 1: Failing Tests schreiben**

`frontend/src/views/ReviewQueueView.aktenanlage.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  zeigeAktenanlageVorschlag, gruppenKey, vorgangFuerEintrag,
  AnlageChip, AktenanlageLeiste,
} from "./ReviewQueueView.jsx";

const GUTACHTEN_OHNE_AKTE = {
  id: 7, klasse: "gutachten", absender_kategorie: "gutachter",
  akte_kandidat_top: null, zustellung_id: 20, parent_zustellung_id: 10,
};

describe("zeigeAktenanlageVorschlag", () => {
  it("true bei Gutachten + Gutachter-Identifier + keinen Kandidaten", () => {
    expect(zeigeAktenanlageVorschlag(GUTACHTEN_OHNE_AKTE)).toBe(true);
  });
  it("false bei vorhandenem Kandidaten", () => {
    expect(zeigeAktenanlageVorschlag({
      ...GUTACHTEN_OHNE_AKTE,
      akte_kandidat_top: { akte_az: "44/22" },
    })).toBe(false);
  });
  it("false ohne Gutachter-Identifier", () => {
    expect(zeigeAktenanlageVorschlag({
      ...GUTACHTEN_OHNE_AKTE, absender_kategorie: null })).toBe(false);
  });
  it("false bei anderer Klasse", () => {
    expect(zeigeAktenanlageVorschlag({
      ...GUTACHTEN_OHNE_AKTE, klasse: "rechnung" })).toBe(false);
  });
});

describe("gruppenKey / vorgangFuerEintrag", () => {
  const queue = [
    { id: 7, zustellung_id: 20, parent_zustellung_id: 10 },
    { id: 8, zustellung_id: 21, parent_zustellung_id: 10 },
    { id: 9, zustellung_id: 30, parent_zustellung_id: null },
  ];
  const vorgaenge = [{ id: 1, intake_dokument_id: 7, status: "akte_erkannt",
                       erkanntes_az: "310/26" }];
  it("gruppenKey nimmt parent vor eigener zustellung", () => {
    expect(gruppenKey(queue[0])).toBe(10);
    expect(gruppenKey(queue[2])).toBe(30);
  });
  it("findet Vorgang fuer Traeger-Eintrag", () => {
    expect(vorgangFuerEintrag(queue[0], vorgaenge, queue).id).toBe(1);
  });
  it("findet Vorgang fuer Geschwister derselben Gruppe", () => {
    expect(vorgangFuerEintrag(queue[1], vorgaenge, queue).id).toBe(1);
  });
  it("null fuer fremde Eintraege", () => {
    expect(vorgangFuerEintrag(queue[2], vorgaenge, queue)).toBeNull();
  });
});

describe("AnlageChip", () => {
  it("laeuft-Zustand", () => {
    render(<AnlageChip vorgang={{ status: "laeuft", warnung: false }} />);
    expect(screen.getByText(/Aktenanlage läuft/)).toBeTruthy();
  });
  it("erkannt-Zustand mit AZ", () => {
    render(<AnlageChip vorgang={{ status: "akte_erkannt",
                                  erkanntes_az: "310/26" }} />);
    expect(screen.getByText(/310\/26/)).toBeTruthy();
  });
  it("Warnung bei langer Laufzeit", () => {
    render(<AnlageChip vorgang={{ status: "laeuft", warnung: true }} />);
    expect(screen.getByText(/ungewöhnlich lange/)).toBeTruthy();
  });
});

describe("AktenanlageLeiste", () => {
  it("unsichtbar ohne Vorgaenge", () => {
    const { container } = render(
      <AktenanlageLeiste vorgaenge={[]} ramicroVerfuegbar={true}
        onSpringe={() => {}} onOeffneAkte={() => {}} onAbbrechen={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
  it("zeigt Zaehler und Offline-Hinweis", () => {
    render(<AktenanlageLeiste
      vorgaenge={[{ id: 1, status: "laeuft", mandant_name: "Zejli",
                    intake_dokument_id: 7, warnung: false },
                  { id: 2, status: "akte_erkannt", mandant_name: "Maier",
                    erkanntes_az: "311/26", intake_dokument_id: null }]}
      ramicroVerfuegbar={false}
      onSpringe={() => {}} onOeffneAkte={() => {}} onAbbrechen={() => {}} />);
    expect(screen.getByText(/1 Aktenanlage läuft/)).toBeTruthy();
    expect(screen.getByText(/1 Akte erkannt/)).toBeTruthy();
    expect(screen.getByText(/RA-MICRO nicht erreichbar/)).toBeTruthy();
    expect(screen.getByText("öffnen")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `cd frontend; npm test -- src/views/ReviewQueueView.aktenanlage.test.jsx`
Expected: FAIL (Exporte existieren nicht)

- [ ] **Step 3: Helfer + Komponenten in `ReviewQueueView.jsx` implementieren**

(a) Imports oben ergänzen (`apiAktenanlage` in die bestehende `../api.js`-Import-Zeile aufnehmen; neuer Komponenten-Import):

```jsx
import AktenanlageDialog, { baueVorbefuellung } from "../components/AktenanlageDialog.jsx";
```

(b) Exportierte Helfer + Komponenten auf Modulebene (z. B. nach `sortiereGruppen`):

```jsx
export function zeigeAktenanlageVorschlag(item) {
  return item?.klasse === "gutachten"
    && item?.absender_kategorie === "gutachter"
    && !item?.akte_kandidat_top;
}

export function gruppenKey(item) {
  return item?.parent_zustellung_id || item?.zustellung_id || null;
}

export function vorgangFuerEintrag(item, vorgaenge, queue) {
  if (!item) return null;
  const key = gruppenKey(item);
  return (vorgaenge || []).find(v => {
    if (v.intake_dokument_id === item.id) return true;
    if (!key || v.intake_dokument_id == null) return false;
    const traeger = (queue || []).find(q => q.id === v.intake_dokument_id);
    return traeger ? gruppenKey(traeger) === key : false;
  }) || null;
}

export function AnlageChip({ vorgang }) {
  if (!vorgang) return null;
  let text, farbe;
  if (vorgang.status === "akte_erkannt") {
    text = `✅ Akte ${vorgang.erkanntes_az} angelegt`;
    farbe = T.green;
  } else if (vorgang.warnung) {
    text = "⚠ Aktenanlage läuft ungewöhnlich lange — in RA-MICRO prüfen";
    farbe = T.amber;
  } else {
    text = "⏳ Aktenanlage läuft";
    farbe = T.blue;
  }
  return (
    <span style={{ fontSize: T.textXs, fontFamily: T.fontMono,
                   background: farbe + "22", color: farbe,
                   borderRadius: 8, padding: "1px 8px" }}>
      {text}
    </span>
  );
}

export function AktenanlageLeiste({ vorgaenge, ramicroVerfuegbar,
                                    onSpringe, onOeffneAkte, onAbbrechen }) {
  if (!vorgaenge || vorgaenge.length === 0) return null;
  const laufend = vorgaenge.filter(v => v.status === "laeuft");
  const erkannt = vorgaenge.filter(v => v.status === "akte_erkannt");
  return (
    <div style={{ padding: "8px 14px", borderBottom: `1px solid ${T.border}`,
                  background: T.blueBg, fontSize: T.textXs }}>
      <div style={{ color: T.blueText, fontWeight: 600, marginBottom: 4 }}>
        {laufend.length > 0 && `⏳ ${laufend.length} Aktenanlage läuft`}
        {laufend.length > 0 && erkannt.length > 0 && " · "}
        {erkannt.length > 0 && `✅ ${erkannt.length} Akte erkannt`}
        {!ramicroVerfuegbar && (
          <span style={{ color: T.amberText }}>
            {" "}· RA-MICRO nicht erreichbar — Erkennung pausiert
          </span>
        )}
      </div>
      {vorgaenge.map(v => (
        <div key={v.id} style={{ display: "flex", gap: 6,
                                 alignItems: "center", padding: "2px 0" }}>
          <span style={{ flex: 1, color: T.text }}>
            {v.status === "akte_erkannt" ? "✅" : v.warnung ? "⚠" : "⏳"}{" "}
            {v.mandant_name}
            {v.erkanntes_az ? ` → ${v.erkanntes_az}` : ""}
          </span>
          {v.intake_dokument_id != null && (
            <button onClick={() => onSpringe(v.intake_dokument_id)}
              style={{ border: "none", background: "transparent",
                       color: T.blueText, cursor: "pointer",
                       textDecoration: "underline", fontSize: T.textXs }}>
              zum Eintrag
            </button>
          )}
          {v.intake_dokument_id == null && v.status === "akte_erkannt" && (
            <button onClick={() => onOeffneAkte(v)}
              style={{ border: "none", background: "transparent",
                       color: T.blueText, cursor: "pointer",
                       textDecoration: "underline", fontSize: T.textXs }}>
              öffnen
            </button>
          )}
          <button onClick={() => onAbbrechen(v.id)}
            title="Vorgang abbrechen (XML wird gelöscht)"
            style={{ border: "none", background: "transparent",
                     color: T.redText, cursor: "pointer",
                     fontSize: T.textXs }}>
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `cd frontend; npm test -- src/views/ReviewQueueView.aktenanlage.test.jsx`
Expected: alle passed

- [ ] **Step 5: Verdrahtung in der Hauptkomponente + DetailPanel**

(a) In `ReviewQueueView` (Hauptkomponente) neue States + Poll-Erweiterung — in `laden` nach dem `apiIntake.queue()`-Block:

```jsx
  const [vorgaenge, setVorgaenge] = useState([]);
  const [ramicroVerfuegbar, setRamicroVerfuegbar] = useState(true);
  const [anlageDialog, setAnlageDialog] = useState(null);
```

und innerhalb von `laden` (gleicher `useCallback`, nach dem Queue-Teil):

```jsx
    try {
      const a = await apiAktenanlage.offen();
      setVorgaenge(a.vorgaenge || []);
      setRamicroVerfuegbar(a.ramicro_verfuegbar !== false);
    } catch { /* Leiste bleibt beim letzten Stand */ }
```

(b) Leiste direkt nach dem Queue-Header-`<div>` (nach dem Sortier-Toggle-Button-Block, vor `<div style={{ flex: 1, overflow: "auto" }}>`):

```jsx
        <AktenanlageLeiste
          vorgaenge={vorgaenge}
          ramicroVerfuegbar={ramicroVerfuegbar}
          onSpringe={id => setAktivId(id)}
          onOeffneAkte={async v => {
            await apiAktenanlage.abschliessen(v.id).catch(() => {});
            onOpenAkte({ az: v.erkanntes_az, az_roh: v.erkanntes_az,
                         label: v.erkanntes_az });
            laden();
          }}
          onAbbrechen={async id => {
            await apiAktenanlage.abbrechen(id).catch(() => {});
            laden();
          }}
        />
```

(c) `QueueEintrag`: neue Prop `vorgang` — in der Badge-Zeile nach `<DegradationBadge item={item} />`:

```jsx
        <AnlageChip vorgang={vorgang} />
```

und an den Aufrufstellen von `<QueueEintrag …>` (Gruppen-Rendering) `vorgang={vorgangFuerEintrag(item, vorgaenge, queue)}` durchreichen.

(d) `DetailPanel`: neue Props `vorgang` und `onAktenanlage` (Signatur erweitern; Aufruf `<DetailPanel key={aktivId} … vorgang={vorgangFuerEintrag(aktuellerEintrag, vorgaenge, queue)} onAktenanlage={() => setAnlageDialog({ item: aktuellerEintrag })} />` — `aktuellerEintrag` = Queue-Item mit `id === aktivId`).

Im DetailPanel:
- **Banner** direkt nach dem Kopfbereich (vor dem bestehenden Melde-Banner), nur wenn kein Vorgang existiert:

```jsx
        {!vorgang && zeigeAktenanlageVorschlag(item) && (
          <div style={{ padding: "10px 12px", marginBottom: 12,
                        background: T.amberBg, color: T.amberText,
                        border: `1px solid ${T.amber}`, borderRadius: 4,
                        fontSize: T.textSm, display: "flex",
                        alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: "1.1rem" }}>🆕</span>
            <span style={{ flex: 1 }}>
              Vermutlich neue Akte: Gutachten von bestätigtem Gutachter,
              kein Treffer im Bestand.
            </span>
            <button onClick={onAktenanlage}
              style={{ padding: "6px 12px", background: T.accent,
                       color: T.white, border: "none", borderRadius: 4,
                       cursor: "pointer", fontWeight: 600 }}>
              Akte anlegen
            </button>
          </div>
        )}
        {vorgang && (
          <div style={{ marginBottom: 12 }}>
            <AnlageChip vorgang={vorgang} />
            {vorgang.kandidaten?.length > 1 && (
              <div style={{ marginTop: 6, fontSize: T.textXs }}>
                Mehrere neue Akten gefunden — bitte wählen:{" "}
                {vorgang.kandidaten.map(k => (
                  <button key={k.az} onClick={() => setGewaehlteAkte(k.az)}
                    style={{ marginRight: 6, border: `1px solid ${T.border}`,
                             background: T.cardBg, borderRadius: 4,
                             padding: "2px 8px", cursor: "pointer",
                             fontFamily: T.fontMono, fontSize: T.textXs }}>
                    {k.az}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
```

Hinweis: `item` ist im DetailPanel der Queue-Eintrag — falls das DetailPanel bisher nur `id` bekommt, zusätzlich `item={aktuellerEintrag}` durchreichen.

- **AZ-Vorauswahl** (im DetailPanel, bei den bestehenden Hooks):

```jsx
  useEffect(() => {
    if (vorgang?.status === "akte_erkannt" && vorgang.erkanntes_az
        && !gewaehlteAkte) {
      setGewaehlteAkte(vorgang.erkanntes_az);
    }
  }, [vorgang, gewaehlteAkte]);
```

- **Immer-Button** im „Akte zuordnen"-Abschnitt, direkt nach dem freien AZ-`<input>`:

```jsx
          <button onClick={onAktenanlage} disabled={!!vorgang}
            style={{ marginTop: 8, padding: "6px 12px",
                     background: "transparent", color: T.accent,
                     border: `1px dashed ${T.accent}`, borderRadius: 4,
                     cursor: vorgang ? "default" : "pointer",
                     fontSize: T.textSm, width: "100%" }}>
            ➕ Neue Akte anlegen (RA-MICRO)
          </button>
```

(e) Dialog-Rendering am Ende der Hauptkomponente (neben den anderen Dialogen). Die Vorbefüllung braucht das Detail + die Gutachter-Vorlage — beim Öffnen laden:

```jsx
      {anlageDialog && (
        <AktenanlageDialogLoader
          item={anlageDialog.item}
          onClose={() => setAnlageDialog(null)}
          onAngelegt={() => { setAnlageDialog(null); laden(); }}
          onUebernehmeAz={az => { setAnlageDialog(null);
                                  setAktivId(anlageDialog.item.id); }}
        />
      )}
```

mit der kleinen Loader-Komponente auf Modulebene (lädt Detail + Vorlage, reicht Prefill weiter):

```jsx
function AktenanlageDialogLoader({ item, onClose, onAngelegt,
                                   onUebernehmeAz }) {
  const [prefill, setPrefill] = useState(null);
  const [geladen, setGeladen] = useState(false);
  useEffect(() => {
    let aktiv = true;
    (async () => {
      let detail = null, vorlage = null;
      try { detail = await apiIntake.detail(item.id); } catch {}
      if (item.zustellung_id) {
        try {
          const d = await apiAktenanlage.gutachterVorlage(item.zustellung_id);
          vorlage = d.vorlage;
        } catch {}
      }
      if (aktiv) {
        setPrefill(baueVorbefuellung(detail, vorlage));
        setGeladen(true);
      }
    })();
    return () => { aktiv = false; };
  }, [item]);
  if (!geladen) return null;
  return (
    <AktenanlageDialog
      intakeDokumentId={item.id}
      zustellungId={item.zustellung_id}
      prefill={prefill}
      onClose={onClose}
      onAngelegt={onAngelegt}
      onUebernehmeAz={onUebernehmeAz}
    />
  );
}
```

- [ ] **Step 6: Alle Frontend-Tests laufen lassen (Regression)**

Run: `cd frontend; npm test`
Expected: alle passed (auch die bestehenden ReviewQueueView-Tests)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.aktenanlage.test.jsx
git commit -m "feat(aktenanlage): ReviewQueue-Integration Banner, Button, Chip, Status-Leiste" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: Aktensuche — `NeueAkteModal` durch `AktenanlageDialog` ersetzen

**Files:**
- Modify: `frontend/src/views/AktensucheView.jsx`

**Interfaces:**
- Consumes: `AktenanlageDialog` (Task 9). Der leere Einstieg übergibt KEIN `intakeDokumentId`/`zustellungId`/`prefill`.

- [ ] **Step 1: Umbau**

In `frontend/src/views/AktensucheView.jsx`:
1. Import ergänzen: `import AktenanlageDialog from "../components/AktenanlageDialog.jsx";`
2. Die komplette Funktion `NeueAkteModal` (Z. ~277–400) löschen.
3. Das Rendering `{neueAkteOffen && (<NeueAkteModal … />)}` ersetzen durch:

```jsx
    {neueAkteOffen && (
      <AktenanlageDialog
        onClose={() => setNeueAkteOffen(false)}
        onAngelegt={(vorgang) => {
          setNeueAkteOffen(false);
          setToast(`Aktenanlage angestoßen (${vorgang.mandant_name}) — ` +
                   "RA-MICRO legt die Akte an. Fortschritt: Review-Queue.");
        }}
        onUebernehmeAz={(az) => {
          setNeueAkteOffen(false);
          onOpenAkte({ az, az_roh: az, label: az });
        }}
      />
    )}
```

Der „+ Neue Akte"-Trigger-Button bleibt unverändert.

- [ ] **Step 2: Frontend-Tests + Lint-Check**

Run: `cd frontend; npm test`
Expected: alle passed. Zusätzlich prüfen, dass `NeueAkteModal` nirgends mehr referenziert wird:
Run: `grep -rn "NeueAkteModal" frontend/src`
Expected: keine Treffer

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AktensucheView.jsx
git commit -m "feat(aktenanlage): Aktensuche nutzt AktenanlageDialog statt NeueAkteModal" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: Infrastruktur (Export-Ordner) + Doku + Gesamtlauf

**Files:**
- Modify: `docker-compose.yml` (backend-Service: env + volume)
- Modify: `docker-compose.prod.yml` (backend-Service: env + volume)
- Modify: `.env.example`
- Modify: `docs/TODO.md` (PRD-NEW als umgesetzt vermerken, Verifikationspunkte aufnehmen)
- Modify: `docs/CHANGELOG.md` (Protokoll-Eintrag)

**Interfaces:**
- Produces: Container-Pfad `/app/oma_export` (env `OMA_EXPORT_PFAD`), Host-Pfad via `OMA_EXPORT_HOST_PFAD` (Default `./oma_export`).

- [ ] **Step 1: Compose + .env.example**

In `docker-compose.yml`, Service `backend` — unter `environment:` ergänzen:

```yaml
      OMA_EXPORT_PFAD: /app/oma_export
```

unter `volumes:` ergänzen:

```yaml
      - ${OMA_EXPORT_HOST_PFAD:-./oma_export}:/app/oma_export
```

Dasselbe Paar in `docker-compose.prod.yml` beim backend-Service.

In `.env.example` anhängen:

```
# Aktenanlage: Ordner, den RA-MICRO auf OMA-XML-Dateien ueberwacht
# (Host-Pfad; im Container immer /app/oma_export)
OMA_EXPORT_HOST_PFAD=./oma_export
```

- [ ] **Step 2: Container neu erstellen und Backend-Gesamtlauf**

Run: `docker compose up -d --force-recreate backend` (Compose-Änderung ⇒ force-recreate)
Dann: `docker exec unfallakten-backend-dev python -m pytest backend/tests/ -x -q`
Expected: gesamte Suite grün

- [ ] **Step 3: Doku**

`docs/CHANGELOG.md`: neuen Eintrag oben anfügen (Muster der bestehenden Einträge) — Titel „Aktenanlage aus der ReviewQueue (PRD-NEW)", Stichpunkte: Migration 66, OMA-XML-Generator, `/aktenanlage`-Blueprint, Erkennung read-only über `dtAnlage`, Freigabe-Hook, Queue-`absender_kategorie`, `AktenanlageDialog` (ersetzt NeueAkteModal), ReviewQueue-Banner/Chip/Leiste, Spec-/Plan-Pfade, Commit-Hashes.

`docs/TODO.md`: unter „Kritisch / Bald" den Eintrag **PRD-NEW** ersetzen durch einen Hinweis in „In Arbeit" oder „Erledigt" (je nach Abnahmestand) mit den drei offenen Verifikationspunkten aus der Spec (Abschnitt 9): Adressnummer-Referenz „Bekannt=Ja", konkreter `OMA_EXPORT_HOST_PFAD` (RA Schatz), Options-Labels/Datumsformat + `dtAnlage`-Spalte beim ersten echten Import.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml docker-compose.prod.yml .env.example docs/TODO.md docs/CHANGELOG.md
git commit -m "feat(aktenanlage): OMA-Export-Ordner (Compose/.env) + Doku PRD-NEW" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Manueller Abnahmetest (RA Schatz, außerhalb des Plans)**

Kein Automatisierungs-Schritt — Checkliste für den Browser-/RA-MICRO-Test:
1. `OMA_EXPORT_HOST_PFAD` in `.env` auf den echten überwachten Ordner setzen, `docker compose up -d --force-recreate backend`.
2. Gutachten-Mail (Cassese) in die Queue laufen lassen → Banner „Vermutlich neue Akte" erscheint.
3. Dialog öffnen → Vorbefüllung prüfen → „Akte anlegen" → XML liegt im Ordner, RA-MICRO importiert.
4. Nach RA-MICRO-Anlage: Chip „✅ Akte … angelegt", AZ vorausgewählt, Freigeben → Unfalldatum in der Akte.
5. Verifikationspunkte Spec Abschnitt 9: „Bekannt=Ja"-Import, `FRAU`/`FIRMA`, ISO-Datum, `dtAnlage`-Spalte.

---

## Plan-Selbstreview (erledigt)

- **Spec-Abdeckung:** 3.1 Banner→Task 10 · 3.2 Button→Task 10 · 3.3 Chip/AZ-Vorauswahl→Task 10 · 3.4 Geschwister→Task 4/6/10 (`gruppenKey`) · 3.5 Leiste→Task 10 · 3.6 leerer Einstieg→Task 4 (Schattenakte bei Erkennung) + 11 · 4 Dialog/Vorbefüllung→Task 8/9 · 4.1 Dubletten-Check→Task 3/5/9 · 5.1 Tabelle→Task 1 · 5.2 Endpoints→Task 4/5 · 5.3 XML→Task 2 · 5.4 Abschluss→Task 4/6 · 5.5 Frontend→Task 9–11 · 6 Fehlerfälle→Tests in Task 2/4/6 + UI Task 10 · 7 Tests→je Task · Ordner/Env→Task 12.
- **Typ-Konsistenz:** Formular-Struktur (`FORMULAR`/`LEERES_FORMULAR`) identisch zwischen Backend-Tests, `oma_xml.py`, Service und Dialog; Vorgangs-Dict-Keys (`mandant_name`, `erkanntes_az`, `kandidaten`, `warnung`, `angelegt_vor_s`) konsistent zwischen Service (Task 4) und Frontend (Task 10).
- **Bewusste Abweichung im Detail:** Der Warn-Chip nach 15 min kommt als `warnung`-Flag vom Backend (Server-Zeit), nicht aus dem Frontend berechnet.
