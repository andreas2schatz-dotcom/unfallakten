"""
Modul 5 – Tests
================
Vollständige Testabdeckung für Word-Dokumentgenerierung:
  - Styling-Helpers (fmt_euro, fmt_datum)
  - Forderungsschreiben (mit/ohne Schaden, Teilhaftung)
  - Sachstandsanfrage (mit/ohne Regulierungen)
  - Abrechnungsübersicht (offen / abgeschlossen)
  - Word-Service (DB-Integration, alle Typen)
  - Flask-Routen (POST generieren, GET Vorschau)
"""

import os
import sys
import io
import json
import unittest
import tempfile

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Test-Datensätze ────────────────────────────────────────────────────────────

KANZLEI = {
    "name":    "Rechtsanwaltskanzlei Koch, Schatz & Kollegen",
    "strasse": "Frankfurter Straße 12",
    "ort":     "63065 Offenbach am Main",
    "telefon": "069 / 83 10 99 - 0",
    "email":   "info@anwalt-offenbach.de",
}

AKTE_VOLL = {
    "id": 1, "aktenzeichen": "42/25",
    "unfalldatum": "2025-03-15", "unfallort": "Offenbach, Berliner Str. 12",
    "status": "in_regulierung", "haftungsquote": 100.0, "notizen": None,
}

MANDANT = {
    "id": 1, "rolle": "mandant", "name": "Müller", "vorname": "Hans",
    "anschrift": "Teststraße 1", "plz": "63065", "ort": "Offenbach",
    "telefon": "069-111222", "email": "hans@test.de",
    "kfz_kennzeichen": "OF-HM 1", "kfz_typ": "VW Passat",
    "versicherung": None, "vers_nr": None, "schaden_nr": None,
    "iban": "DE89370400440532013000", "firma": None,
}

GEGNER = {
    "id": 2, "rolle": "gegner", "name": "Bauer", "vorname": "Klaus",
    "anschrift": "Gegnerstr. 5", "plz": "60313", "ort": "Frankfurt",
    "telefon": None, "email": None,
    "kfz_kennzeichen": "F-KB 42", "kfz_typ": "BMW 3er",
    "versicherung": "HUK Coburg", "vers_nr": "HUK-2025-001",
    "schaden_nr": "HUK-S-001-A", "iban": None, "firma": None,
}

SCHADEN = {
    "reparaturkosten": 6240.50,
    "wiederbeschaffung": None, "restwert": None,
    "wertminderung": 350.00, "nutzungsausfall": 560.00,
    "mietwagenkosten": None, "sv_kosten": 890.00,
    "abschleppkosten": 180.00, "standkosten": None,
    "anabmeldekosten": None, "schmerzensgeld": None,
    "sonstiges": None, "sonstiges_beschr": None,
    "gesamt_brutto": 8220.50,
}

SCHADEN_TOTAL = {
    "reparaturkosten": None,
    "wiederbeschaffung": 18500.00, "restwert": 3200.00,
    "wertminderung": None, "nutzungsausfall": None,
    "mietwagenkosten": 680.00, "sv_kosten": 1150.00,
    "abschleppkosten": 220.00, "standkosten": 180.00,
    "anabmeldekosten": 53.50, "schmerzensgeld": None,
    "sonstiges": None, "sonstiges_beschr": None,
    "gesamt_brutto": 17583.50,
}

REGULIERUNGEN = [
    {
        "id": 1, "datum": "2025-04-10",
        "betrag_gefordert": 8220.50, "betrag_reguliert": 6180.00,
        "differenz": 2040.50, "status": "teilreguliert",
        "vers_referenz": "HUK-2025-001-R",
        "kuerz_begruendung": "Wertminderung abgelehnt",
    }
]


def _akte_daten(schaden=None, regulierungen=None, status="offen",
                haftung=100.0) -> dict:
    akte = dict(AKTE_VOLL)
    akte["status"] = status
    akte["haftungsquote"] = haftung
    return {
        "akte":          akte,
        "mandant":       dict(MANDANT),
        "gegner":        dict(GEGNER),
        "schaden":       schaden,
        "regulierungen": regulierungen or [],
        "kanzlei":       KANZLEI,
    }


def _ist_docx(data: bytes) -> bool:
    """Prüft ob Bytes ein gültiges DOCX (ZIP)-Format haben."""
    return data[:4] == b"PK\x03\x04"


def _docx_text(data: bytes) -> str:
    """Extrahiert Rohtext aus DOCX-Bytes."""
    import zipfile
    from xml.etree import ElementTree as ET
    zeilen = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                xml = zf.read(name)
                root = ET.fromstring(xml)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                for t in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"):
                    if t.text:
                        zeilen.append(t.text)
    return " ".join(zeilen)


# ── App-Setup ──────────────────────────────────────────────────────────────────

def _setup(test_id: str):
    upload_dir = os.path.join(_tmp_dir, f"up_{test_id}")
    os.makedirs(upload_dir, exist_ok=True)
    db_path = os.path.join(_tmp_dir, f"m5_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    os.environ["DB_PATH"]        = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-chars!!"
    os.environ["UPLOAD_DIR"]     = upload_dir

    import importlib
    mods = [
        "backend.db.database", "backend.db.schema_manager",
        "backend.models.benutzer", "backend.models.akte",
        "backend.models.schaden", "backend.models.dokument",
        "backend.auth.jwt_handler", "backend.auth.middleware",
        "backend.auth.service", "backend.auth.validierung",
        "backend.routers.auth_routes", "backend.routers.akten_routes",
        "backend.routers.beteiligte_routes", "backend.routers.schaden_routes",
        "backend.pdf.extraktor", "backend.pdf.parser",
        "backend.pdf.upload_service", "backend.routers.dokumente_routes",
        "backend.word.styling", "backend.word.forderungsschreiben_wv",
        "backend.word.sachstandsanfrage", "backend.word.abrechnungsuebersicht",
        "backend.word.word_service", "backend.routers.word_routes",
        "backend.app",
    ]
    loaded = {}
    for mod in mods:
        m = __import__(mod, fromlist=[""])
        importlib.reload(m)
        loaded[mod] = m

    app = loaded["backend.app"].erstelle_app()
    app.config["TESTING"] = True
    client = app.test_client()

    # Admin + Akte + Beteiligte + Schaden anlegen
    client.post("/auth/register/erster", json={
        "name": "Admin", "email": "admin@test.de", "passwort": "Admin123!"
    })
    r = client.post("/auth/login", json={
        "email": "admin@test.de", "passwort": "Admin123!"
    })
    token = r.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r2 = client.post("/akten", json={
        "aktenzeichen": "955/25", "unfalldatum": "2025-03-15",
        "unfallort": "Offenbach, Berliner Str. 12",
    }, headers=headers)
    akte_id = r2.get_json()["id"]

    # Mandant
    client.post(f"/akten/{akte_id}/beteiligte", json={
        "rolle": "mandant", "name": "Müller", "vorname": "Hans",
        "kfz_kennzeichen": "OF-HM 1",
    }, headers=headers)

    # Gegner
    client.post(f"/akten/{akte_id}/beteiligte", json={
        "rolle": "gegner", "name": "Bauer", "vorname": "Klaus",
        "versicherung": "HUK Coburg", "schaden_nr": "HUK-001-A",
    }, headers=headers)

    # Schaden
    client.put(f"/akten/{akte_id}/schaden", json={
        "reparaturkosten": 6240.50, "sv_kosten": 890.0,
        "nutzungsausfall": 560.0, "wertminderung": 350.0,
        "abschleppkosten": 180.0,
    }, headers=headers)

    return client, headers, akte_id, loaded


# ══════════════════════════════════════════════════════════════════════════════
# STYLING TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestStyling(unittest.TestCase):

    def setUp(self):
        from backend.word import styling
        import importlib; importlib.reload(styling)
        self.s = styling

    def test_fmt_euro_ganz(self):
        self.assertEqual(self.s.fmt_euro(1234.56), "1.234,56 €")

    def test_fmt_euro_tausend(self):
        self.assertEqual(self.s.fmt_euro(18500.0), "18.500,00 €")

    def test_fmt_euro_none(self):
        self.assertEqual(self.s.fmt_euro(None), "–")

    def test_fmt_euro_null(self):
        self.assertEqual(self.s.fmt_euro(0.0), "0,00 €")

    def test_fmt_datum_iso(self):
        self.assertEqual(self.s.fmt_datum("2025-03-15"), "15.03.2025")

    def test_fmt_datum_leer(self):
        self.assertEqual(self.s.fmt_datum(""), "–")

    def test_fmt_datum_none(self):
        self.assertEqual(self.s.fmt_datum(None), "–")

    def test_erstelle_dokument(self):
        doc = self.s.erstelle_dokument()
        self.assertIsNotNone(doc)
        from docx.shared import Cm
        section = doc.sections[0]
        # Seitenränder gesetzt
        self.assertAlmostEqual(
            section.left_margin.cm, self.s.RAND_LINKS.cm, places=1
        )


# ══════════════════════════════════════════════════════════════════════════════
# FORDERUNGSSCHREIBEN TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestForderungsschreiben(unittest.TestCase):
    """Tests für den Produktiv-Generator forderungsschreiben_wv
    (Vorlagen-Rendering; der Legacy-Generator forderungsschreiben.py
    wurde 2026-08-11 entfernt)."""

    def setUp(self):
        from backend.word import forderungsschreiben_wv
        import importlib; importlib.reload(forderungsschreiben_wv)
        self.gen = forderungsschreiben_wv.generiere_forderungsschreiben_wv

    def test_erzeugt_docx(self):
        data = self.gen(_akte_daten(SCHADEN))
        self.assertTrue(_ist_docx(data), "Kein gültiges DOCX")
        self.assertGreater(len(data), 5000)

    def test_enthaelt_aktenzeichen(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("42/25", text)

    def test_enthaelt_mandant(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("Müller", text)

    def test_enthaelt_versicherung(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("HUK", text)

    def test_enthaelt_reparaturkosten(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("6.240,50", text)

    def test_gesamtbetrag_mit_unkostenpauschale_default(self):
        """8.220,50 € Positionen + 30,00 € Default-Unkostenpauschale."""
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("8.250,50", text)

    def test_ohne_schaden(self):
        """Dokument muss auch ohne Schadenpositionen generierbar sein."""
        data = self.gen(_akte_daten(schaden=None))
        self.assertTrue(_ist_docx(data))
        text = _docx_text(data)
        self.assertIn("42/25", text)

    def test_totalschaden(self):
        """Totalschadenfall mit Wiederbeschaffung und Restwert."""
        data = self.gen(_akte_daten(SCHADEN_TOTAL))
        text = _docx_text(data)
        self.assertIn("18.500,00", text)
        self.assertIn("3.200,00", text)

    def test_ohne_mandant_und_gegner(self):
        """Fail-loud-Platzhalter wenn keine Beteiligten vorhanden."""
        daten = _akte_daten(SCHADEN)
        daten["mandant"] = None
        daten["gegner"]  = None
        data = self.gen(daten)
        self.assertTrue(_ist_docx(data))
        self.assertIn("KEINE ADRESSE ERFASST", _docx_text(data))

    def test_schmerzensgeld_freitext_wdm_crasht_nicht(self):
        """I-3: varSCHMGELD mit Freitext (z.B. 'ca. 2.500 EUR') darf die
        Generierung nicht abbrechen."""
        from unittest.mock import patch
        daten = _akte_daten(SCHADEN)
        daten["wdm_roh"] = {"varANSPR-SG": "Ja", "varSCHMGELD": "ca. 2.500 EUR"}
        with patch("backend.services.standardtext_registry.hole_texte_aufgeloest",
                   return_value={"sg_beweis_atteste": "Atteste"}):
            data = self.gen(daten)
        self.assertTrue(_ist_docx(data))


# ══════════════════════════════════════════════════════════════════════════════
# SACHSTANDSANFRAGE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestSachstandsanfrage(unittest.TestCase):

    def setUp(self):
        from backend.word import sachstandsanfrage
        import importlib; importlib.reload(sachstandsanfrage)
        self.gen = sachstandsanfrage.generiere_sachstandsanfrage

    def test_erzeugt_docx(self):
        data = self.gen(_akte_daten(SCHADEN))
        self.assertTrue(_ist_docx(data))

    def test_enthaelt_aktenzeichen(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("42/25", text)

    def test_enthaelt_fristwort(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("Frist", text)

    def test_mit_regulierungen(self):
        data = self.gen(_akte_daten(SCHADEN, REGULIERUNGEN))
        text = _docx_text(data)
        self.assertIn("6.180,00", text)

    def test_ohne_regulierungen(self):
        data = self.gen(_akte_daten(SCHADEN, regulierungen=[]))
        text = _docx_text(data)
        self.assertIn("noch", text.lower())

    def test_androhung_klage(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("gerichtliche", text.lower())

    def test_gesamtschaden_erscheint(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("8.220,50", text)


# ══════════════════════════════════════════════════════════════════════════════
# ABRECHNUNGSÜBERSICHT TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestAbrechnungsuebersicht(unittest.TestCase):

    def setUp(self):
        from backend.word import abrechnungsuebersicht
        import importlib; importlib.reload(abrechnungsuebersicht)
        self.gen = abrechnungsuebersicht.generiere_abrechnungsuebersicht

    def test_erzeugt_docx(self):
        data = self.gen(_akte_daten(SCHADEN))
        self.assertTrue(_ist_docx(data))

    def test_enthaelt_mandant(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("Müller", text)

    def test_enthaelt_gesamtschaden(self):
        data = self.gen(_akte_daten(SCHADEN))
        text = _docx_text(data)
        self.assertIn("8.220,50", text)

    def test_ausstehend_berechnet(self):
        """Ohne Regulierung muss der volle Betrag ausstehend sein."""
        data = self.gen(_akte_daten(SCHADEN, regulierungen=[]))
        text = _docx_text(data)
        # "Noch ausstehend" oder Betrag muss auftauchen
        self.assertIn("ausstehend", text.lower())

    def test_vollreguliert_status(self):
        """Bei Vollregulierung soll der abgeschlossen-Text erscheinen."""
        reg_voll = [{
            "datum": "2025-05-01",
            "betrag_gefordert": 8220.50,
            "betrag_reguliert": 8220.50,
            "differenz": 0.0,
            "status": "vollreguliert",
            "vers_referenz": "HUK-VOLL",
            "kuerz_begruendung": None,
        }]
        data = self.gen(_akte_daten(SCHADEN, reg_voll, status="abgeschlossen"))
        text = _docx_text(data)
        self.assertIn("vollständig", text.lower())

    def test_mit_teilregulierung(self):
        data = self.gen(_akte_daten(SCHADEN, REGULIERUNGEN, status="in_regulierung"))
        text = _docx_text(data)
        self.assertIn("6.180,00", text)
        self.assertIn("Regulierungsverlauf", text)

    def test_totalschaden(self):
        data = self.gen(_akte_daten(SCHADEN_TOTAL))
        text = _docx_text(data)
        self.assertIn("18.500,00", text)
        self.assertIn("3.200,00", text)

    def test_ohne_schaden(self):
        data = self.gen(_akte_daten(schaden=None))
        self.assertTrue(_ist_docx(data))

    def test_status_badge_offen(self):
        data = self.gen(_akte_daten(SCHADEN, status="offen"))
        text = _docx_text(data)
        self.assertIn("offen", text.lower())

    def test_status_badge_klage(self):
        data = self.gen(_akte_daten(SCHADEN, status="klage"))
        text = _docx_text(data)
        self.assertIn("Klage", text)


# ══════════════════════════════════════════════════════════════════════════════
# WORD-SERVICE TESTS (DB-Integration)
# ══════════════════════════════════════════════════════════════════════════════

class TestWordService(unittest.TestCase):

    def setUp(self):
        os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, "svc_uploads")
        os.makedirs(os.environ["UPLOAD_DIR"], exist_ok=True)
        db_path = os.path.join(_tmp_dir, "svc_test.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.environ["DB_PATH"]        = db_path
        os.environ["JWT_SECRET_KEY"] = "test-key-32chars-minimum!!!!!"

        import importlib
        for mod in [
            "backend.db.database", "backend.db.schema_manager",
            "backend.models.benutzer", "backend.models.akte",
            "backend.models.schaden", "backend.models.dokument",
            "backend.word.styling", "backend.word.forderungsschreiben_wv",
            "backend.word.sachstandsanfrage", "backend.word.abrechnungsuebersicht",
            "backend.word.word_service",
        ]:
            importlib.reload(__import__(mod, fromlist=[""]))

        from backend.db.schema_manager import init_db
        init_db()
        from backend.models.benutzer import erstelle_benutzer
        from backend.models.akte import erstelle_akte
        from backend.models.schaden import (
            erstelle_beteiligten, setze_schadenpositionen
        )

        self.user = erstelle_benutzer("Admin", "a@b.de", "Admin1234!", "admin")
        self.akte = erstelle_akte("25-SVC-001", "2025-03-15",
                                   self.user.id, unfallort="Offenbach")
        erstelle_beteiligten(self.akte.id, "mandant", "Müller",
                              vorname="Hans")
        erstelle_beteiligten(self.akte.id, "gegner", "Bauer",
                              versicherung="HUK", schaden_nr="HUK-001")
        setze_schadenpositionen(
            self.akte.id, self.user.id,
            reparaturkosten=6240.50, sv_kosten=890.0
        )

        from backend.word.word_service import generiere_und_speichere, WordFehler
        self.generiere = generiere_und_speichere
        self.WordFehler = WordFehler

    def test_alle_typen_generierbar(self):
        for typ in ["forderungsschreiben", "sachstandsanfrage",
                    "abrechnungsuebersicht"]:
            ergebnis = self.generiere(self.akte.id, typ,
                                       self.user.id, in_db=False)
            self.assertTrue(_ist_docx(ergebnis["bytes"]),
                             f"{typ}: kein DOCX")
            self.assertIn(typ, ergebnis["dateiname"])

    def test_db_eintrag_wird_angelegt(self):
        ergebnis = self.generiere(self.akte.id, "forderungsschreiben",
                                   self.user.id, in_db=True)
        self.assertIsNotNone(ergebnis["dokument"])
        self.assertIn("id", ergebnis["dokument"])

    def test_kein_db_eintrag_bei_in_db_false(self):
        ergebnis = self.generiere(self.akte.id, "sachstandsanfrage",
                                   self.user.id, in_db=False)
        self.assertIsNone(ergebnis["dokument"])

    def test_ungueltige_akte_404(self):
        with self.assertRaises(self.WordFehler) as ctx:
            self.generiere(99999, "forderungsschreiben")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_ungültiger_typ_422(self):
        with self.assertRaises(self.WordFehler) as ctx:
            self.generiere(self.akte.id, "geheimbrief")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_registry_typ_ohne_generator_422(self):
        """I-1: Registry-Typen ohne Word-Generator (z.B. mahnschreiben)
        müssen sauber mit 422 abgelehnt werden statt KeyError-500."""
        with self.assertRaises(self.WordFehler) as ctx:
            self.generiere(self.akte.id, "mahnschreiben",
                           self.user.id, in_db=False)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_wdm_vorsteuer_override_greift(self):
        """I-6: varSSTF=J aus WDM muss das SQLite-Vorsteuer-Flag des
        Mandanten überschreiben."""
        from unittest.mock import patch
        from backend.word import word_service as ws
        from backend.models.akte import hole_akte_by_id
        akte = hole_akte_by_id(self.akte.id)
        with patch.object(ws, "_lade_wdm_kontrollvars",
                          return_value={"varSSTF": "J"}):
            daten = ws._lade_akte_daten(self.akte.id, akte,
                                        dok_typ="forderungsschreiben")
        self.assertEqual((daten["mandant"] or {}).get("vorsteuer"), "Y")

    def test_dateiname_enthaelt_aktenzeichen(self):
        ergebnis = self.generiere(self.akte.id, "forderungsschreiben",
                                   in_db=False)
        self.assertIn("25-SVC-001", ergebnis["dateiname"])

    def test_forderungshistorie_entspricht_brief(self):
        """C-1: Die Historie muss exakt die Positionen des Briefs übernehmen
        (kanonische Keys, unter dem Aktenzeichen, inkl. Unkostenpauschale)."""
        self.generiere(self.akte.id, "forderungsschreiben",
                       self.user.id, in_db=True)
        from backend.models.forderung import hole_forderung_positionen
        pos = hole_forderung_positionen("25-SVC-001")
        d = {p.position_key: p.betrag_gefordert for p in pos}
        self.assertEqual(d.get("rep_gutachten_netto"), 6240.50)
        self.assertEqual(d.get("sv_kosten"), 890.0)
        self.assertEqual(d.get("unkostenpauschale"), 30.0)
        self.assertNotIn("reparaturkosten", d)

    def test_gebuehren_streitwert_dedupliziert_schreiben(self):
        """I-8: Streitwert-Fallback darf Positionen über mehrere Schreiben
        nicht doppelt zählen — es zählt der Stand des letzten Schreibens."""
        from backend.word import word_service as ws
        from backend.db.database import get_connection
        az = "25-SVC-001"
        with get_connection() as conn:
            for nr, betrag in ((1, 500.0), (2, 300.0)):
                conn.execute(
                    """
                    INSERT INTO forderung_positionen
                        (akte_id, forderungsschreiben_nr, datum, position_key,
                         position_label, betrag_gefordert, status)
                    VALUES (?, ?, date('now'), 'nutzungsausfall',
                            'Nutzungsausfallschaden', ?, 'gefordert')
                    """,
                    (az, nr, betrag),
                )
        ctx = ws._lade_gebuehren_kontext(az)
        self.assertEqual(ctx["streitwert"], 300.0)

    def test_bytes_sind_nicht_leer(self):
        ergebnis = self.generiere(self.akte.id, "abrechnungsuebersicht",
                                   in_db=False)
        self.assertGreater(len(ergebnis["bytes"]), 5000)


# ══════════════════════════════════════════════════════════════════════════════
# FLASK-ROUTEN TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestWordRouten(unittest.TestCase):

    def setUp(self):
        self.client, self.h, self.akte_id, _ = \
            _setup(f"wr_{self._testMethodName}")

    def _url(self, suffix=""):
        return f"/akten/{self.akte_id}/dokumente/word{suffix}"

    def _post(self, typ: str) -> object:
        return self.client.post(
            self._url(),
            json={"typ": typ},
            headers=self.h,
        )

    # ── POST /word ─────────────────────────────────────────────────────────────

    def test_forderungsschreiben_generieren(self):
        r = self._post("forderungsschreiben")
        self.assertEqual(r.status_code, 201)
        data = r.get_json()
        self.assertIn("dateiname", data)
        self.assertIn("groesse", data)
        self.assertIn("dokument", data)
        self.assertIn("download_url", data)
        self.assertGreater(data["groesse"], 5000)

    def test_sachstandsanfrage_generieren(self):
        r = self._post("sachstandsanfrage")
        self.assertEqual(r.status_code, 201)
        self.assertIn("955-25", r.get_json()["dateiname"])

    def test_abrechnungsuebersicht_generieren(self):
        r = self._post("abrechnungsuebersicht")
        self.assertEqual(r.status_code, 201)
        self.assertIn("abrechnungsuebersicht", r.get_json()["dateiname"])

    def test_ungültiger_typ_422(self):
        r = self._post("geheimbrief")
        self.assertEqual(r.status_code, 422)

    def test_fehlender_typ_422(self):
        r = self.client.post(self._url(), json={}, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_nicht_vorhandene_akte_404(self):
        r = self.client.post(
            "/akten/99999/dokumente/word",
            json={"typ": "forderungsschreiben"},
            headers=self.h,
        )
        self.assertEqual(r.status_code, 404)

    def test_ohne_token_401(self):
        r = self.client.post(self._url(), json={"typ": "forderungsschreiben"})
        self.assertEqual(r.status_code, 401)

    def test_dokument_in_db_nach_post(self):
        """Nach POST muss das Dokument in der Datenbank eingetragen sein."""
        r = self._post("forderungsschreiben")
        dok_id = r.get_json()["dokument"]["id"]
        # Dokument über allgemeinen Dokumente-Endpunkt abrufbar
        r2 = self.client.get(
            f"/akten/{self.akte_id}/dokumente/{dok_id}",
            headers=self.h,
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.get_json()["dateityp"], "docx")

    # ── GET /word/<typ>/vorschau ───────────────────────────────────────────────

    def test_vorschau_forderungsschreiben(self):
        r = self.client.get(
            self._url("/forderungsschreiben/vorschau"),
            headers=self.h,
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("wordprocessingml", r.content_type)
        self.assertTrue(_ist_docx(r.data))

    def test_vorschau_sachstandsanfrage(self):
        r = self.client.get(
            self._url("/sachstandsanfrage/vorschau"),
            headers=self.h,
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(_ist_docx(r.data))
        self.assertIn("sachstandsanfrage", r.headers.get("Content-Disposition", ""))

    def test_vorschau_abrechnungsuebersicht(self):
        r = self.client.get(
            self._url("/abrechnungsuebersicht/vorschau"),
            headers=self.h,
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(_ist_docx(r.data))

    def test_vorschau_kein_db_eintrag(self):
        """Vorschau darf keinen DB-Eintrag anlegen."""
        # Anzahl Dokumente vorher
        r1 = self.client.get(
            f"/akten/{self.akte_id}/dokumente", headers=self.h
        )
        anzahl_vorher = len(r1.get_json()["dokumente"])

        self.client.get(self._url("/forderungsschreiben/vorschau"),
                         headers=self.h)

        r2 = self.client.get(
            f"/akten/{self.akte_id}/dokumente", headers=self.h
        )
        anzahl_nachher = len(r2.get_json()["dokumente"])
        self.assertEqual(anzahl_vorher, anzahl_nachher,
                          "Vorschau hat fälschlicherweise DB-Eintrag angelegt")

    def test_vorschau_ungültiger_typ_422(self):
        r = self.client.get(
            self._url("/quatsch/vorschau"),
            headers=self.h,
        )
        self.assertEqual(r.status_code, 422)

    def test_vorschau_nicht_vorhandene_akte_404(self):
        r = self.client.get(
            "/akten/99999/dokumente/word/forderungsschreiben/vorschau",
            headers=self.h,
        )
        self.assertEqual(r.status_code, 404)

    def test_vorschau_inhalt_korrekt(self):
        """Generiertes DOCX muss das Aktenzeichen enthalten."""
        r = self.client.get(
            self._url("/forderungsschreiben/vorschau"),
            headers=self.h,
        )
        text = _docx_text(r.data)
        self.assertIn("955/25", text)


class TestBerechnePositionen(unittest.TestCase):
    """Unit-Tests für die kanonische Positionsliste (C-1/V-3):
    eine Quelle für Brief-Tabelle UND Forderungshistorie."""

    def setUp(self):
        from backend.word import forderungsschreiben_wv
        import importlib; importlib.reload(forderungsschreiben_wv)
        self.fn = forderungsschreiben_wv.berechne_positionen

    def _map(self, res):
        return {p["key"]: p["betrag"] for p in res}

    def test_fiktiv_nutzt_gutachten_key(self):
        pm = self._map(self.fn({"rep_gutachten_netto": 5000.0}, vorsteuer=False))
        self.assertEqual(pm["rep_gutachten_netto"], 5000.0)
        self.assertNotIn("reparaturkosten", pm)
        self.assertEqual(pm["unkostenpauschale"], 30.0)

    def test_legacy_reparaturkosten_wird_gutachten_key(self):
        pm = self._map(self.fn({"reparaturkosten": 6240.50}, vorsteuer=False))
        self.assertEqual(pm["rep_gutachten_netto"], 6240.50)
        self.assertNotIn("reparaturkosten", pm)

    def test_totalschaden_restwert_negativ(self):
        pm = self._map(self.fn(
            {"wiederbeschaffung": 18500.0, "restwert": 3200.0}, vorsteuer=False))
        self.assertEqual(pm["wiederbeschaffung"], 18500.0)
        self.assertEqual(pm["restwert"], -3200.0)
        self.assertNotIn("wertminderung", pm)

    def test_konkret_brutto_ohne_vorsteuer(self):
        pm = self._map(self.fn(
            {"rep_rechnung_netto": 1000.0, "rep_rechnung_brutto": 1190.0,
             "abrechnungsart": "konkret"}, vorsteuer=False))
        self.assertEqual(pm["rep_rechnung_brutto"], 1190.0)
        self.assertNotIn("rep_rechnung_netto", pm)

    def test_konkret_netto_mit_vorsteuer(self):
        pm = self._map(self.fn(
            {"rep_rechnung_netto": 1000.0, "rep_rechnung_brutto": 1190.0,
             "abrechnungsart": "konkret"}, vorsteuer=True))
        self.assertEqual(pm["rep_rechnung_netto"], 1000.0)
        self.assertNotIn("rep_rechnung_brutto", pm)

    def test_nebenkosten_brutto_umrechnung(self):
        pm = self._map(self.fn(
            {"rep_gutachten_netto": 1.0, "sv_kosten_netto": 100.0,
             "sv_kosten_ust": 19.0}, vorsteuer=False))
        self.assertEqual(pm["sv_kosten"], 119.0)

    def test_nullzeilen_gefiltert(self):
        pm = self._map(self.fn(
            {"rep_gutachten_netto": 5000.0, "nutzungsausfall": 0.0},
            vorsteuer=False))
        self.assertNotIn("nutzungsausfall", pm)

    def test_summe_entspricht_tabelle(self):
        from backend.word.forderungsschreiben_wv import _baue_tabelle
        schaden = {"rep_gutachten_netto": 5000.0, "wertminderung": 350.0,
                   "nutzungsausfall": 560.0}
        _, gesamt = _baue_tabelle(schaden, vorsteuer=False)
        erwartet = sum(p["betrag"] for p in self.fn(schaden, vorsteuer=False))
        self.assertEqual(round(gesamt, 2), round(erwartet, 2))


class TestBauePosMap(unittest.TestCase):
    """Unit-Tests für _baue_pos_map (Summierung + Key-Normalisierung)."""

    def setUp(self):
        from backend.word.abrechnungsuebersicht_service import _baue_pos_map
        self.fn = _baue_pos_map

    def test_einzelne_abrechnung(self):
        pm = self.fn([{"positionen": [
            {"position_key": "sv_kosten", "betrag_reguliert": 450.0},
        ]}])
        self.assertEqual(pm["sv_kosten"]["reguliert"], 450.0)

    def test_summe_zweier_abrechnungen(self):
        """Kernbug: zwei Abrechnungen mit gleicher Position müssen summiert werden."""
        pm = self.fn([
            {"positionen": [{"position_key": "sv_kosten", "betrag_reguliert": 300.0}]},
            {"positionen": [{"position_key": "sv_kosten", "betrag_reguliert": 150.0}]},
        ])
        self.assertEqual(pm["sv_kosten"]["reguliert"], 450.0)

    def test_key_normalise_wbw(self):
        pm = self.fn([{"positionen": [
            {"position_key": "wbw", "betrag_reguliert": 18500.0},
        ]}])
        self.assertIn("wiederbeschaffung", pm)
        self.assertNotIn("wbw", pm)
        self.assertEqual(pm["wiederbeschaffung"]["reguliert"], 18500.0)

    def test_key_normalise_reparatur_brutto(self):
        pm = self.fn([{"positionen": [
            {"position_key": "reparatur_brutto", "betrag_reguliert": 3000.0},
        ]}])
        self.assertIn("rep_gutachten_netto", pm)
        self.assertNotIn("reparatur_brutto", pm)

    def test_key_normalise_kostenpauschale(self):
        pm = self.fn([{"positionen": [
            {"position_key": "kostenpauschale", "betrag_reguliert": 25.0},
        ]}])
        self.assertIn("unkostenpauschale", pm)
        self.assertNotIn("kostenpauschale", pm)

    def test_key_normalise_sonstiges_wdm(self):
        pm = self.fn([{"positionen": [
            {"position_key": "sonstiges_wdm_3", "betrag_reguliert": 100.0},
        ]}])
        self.assertIn("extra_wdm_ss3", pm)
        self.assertNotIn("sonstiges_wdm_3", pm)

    def test_mixed_keys_summiert_nach_normalisierung(self):
        """wbw + wiederbeschaffung aus verschiedenen Abrechnungen = eine Summe."""
        pm = self.fn([
            {"positionen": [{"position_key": "wbw", "betrag_reguliert": 10000.0}]},
            {"positionen": [{"position_key": "wiederbeschaffung", "betrag_reguliert": 5000.0}]},
        ])
        self.assertEqual(pm["wiederbeschaffung"]["reguliert"], 15000.0)

    def test_art_wbw_ohne_position_key_normalisiert(self):
        """art='wbw' ohne position_key (Live-PDF-Import-Pfad) → wiederbeschaffung."""
        pm = self.fn([{"positionen": [
            {"art": "wbw", "betrag_reguliert": 18500.0},
        ]}])
        self.assertIn("wiederbeschaffung", pm)
        self.assertNotIn("wbw", pm)
        self.assertEqual(pm["wiederbeschaffung"]["reguliert"], 18500.0)

    def test_none_reguliert_ignoriert(self):
        pm = self.fn([{"positionen": [
            {"position_key": "sv_kosten", "betrag_reguliert": None},
        ]}])
        self.assertNotIn("sv_kosten", pm)

    def test_leere_liste(self):
        self.assertEqual(self.fn([]), {})

    def test_art_fallback(self):
        """position_key fehlt → art wird verwendet."""
        pm = self.fn([{"positionen": [
            {"art": "sv_kosten", "betrag_reguliert": 200.0},
        ]}])
        self.assertIn("sv_kosten", pm)
        self.assertEqual(pm["sv_kosten"]["reguliert"], 200.0)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestStyling,
        TestForderungsschreiben,
        TestSachstandsanfrage,
        TestAbrechnungsuebersicht,
        TestWordService,
        TestWordRouten,
        TestBerechnePositionen,
        TestBauePosMap,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
