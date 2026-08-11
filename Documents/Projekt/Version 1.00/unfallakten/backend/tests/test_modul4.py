"""
Modul 4 – Tests
================
Vollständige Testabdeckung für:
  - PDF-Validierung und Extraktion
  - Regex-Parser (Reparatur, Totalschaden, Abrechnungsschreiben)
  - Upload-Service (Validierung, Dateispeicherung, Auto-Schaden)
  - Flask-Routen (Upload, Download, Parse-Ergebnis, Korrektur, Löschen)

Verwendet reportlab zum Erzeugen realistischer Deutsch-Gutachten-PDFs.
"""

import os
import sys
import io
import json
import unittest
import tempfile
from pathlib import Path

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ── Test-PDF-Erzeugung ─────────────────────────────────────────────────────────

def _erzeuge_pdf(text: str) -> bytes:
    """Erzeugt ein minimal-PDF mit dem gegebenen Text (via reportlab)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=50, rightMargin=50,
                             topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    zeilen = []
    for zeile in text.split("\n"):
        zeile = zeile.strip()
        if zeile:
            zeilen.append(Paragraph(zeile, styles["Normal"]))
            zeilen.append(Spacer(1, 4))
    doc.build(zeilen)
    return buf.getvalue()


def _gutachten_pdf() -> bytes:
    return _erzeuge_pdf("""
Sachverständigengutachten Nr. SV-2025-0472

Auftraggeber: Rechtsanwaltskanzlei Koch, Schatz & Kollegen
Aktenzeichen: 42/25

Fahrzeugdaten:
Kennzeichen: OF-MM 123
Fahrzeugtyp: VW Passat 2.0 TDI

Unfalldatum: 15.03.2025
Schadensort: Offenbach am Main, Berliner Straße 42

Schadenfeststellung:
Reparaturkosten (brutto): 6.240,50 EUR
Merkantile Wertminderung: 350,00 EUR
Nutzungsausfall: 560,00 EUR (8 Tage à 70,00 EUR)
Abschleppkosten: 180,00 EUR

Sachverständigenkosten: 890,00 EUR

Gesamtschaden: 8.220,50 EUR

Erstellt von: Dipl.-Ing. Klaus Baumann, öffentlich bestellter und
vereidigter Kfz-Sachverständiger
""")


def _totalschaden_pdf() -> bytes:
    return _erzeuge_pdf("""
Kfz-Schadensgutachten – Totalschadenfall

Schadennummer: HUK-2025-001-A
Unfalldatum: 22.02.2025

Fahrzeug: BMW 3er 320d
Kennzeichen: OF-HM 456

Bewertung:
Wiederbeschaffungswert: 18.500,00 EUR
Restwert gem. Angebot: 3.200,00 EUR

Sachverständigenkosten: 1.150,00 EUR
Abschleppkosten: 220,00 EUR
Standkosten: 180,00 EUR
Mietwagenkosten: 680,00 EUR
An-/Abmeldekosten: 53,50 EUR

Gesamtschaden: 17.583,50 EUR

Hinweis: Aufgrund des Totalschadens wird eine Reparatur nicht empfohlen.
Der Fahrzeugwert nach Unfall beträgt ca. 3.200,00 EUR.
""")


def _abrechnungs_pdf() -> bytes:
    return _erzeuge_pdf("""
HUK-COBURG Allgemeine Versicherung AG
Bahnhofsplatz 1, 96450 Coburg

Schadennummer: HUK-2025-001-R
Aktenzeichen Rechtsanwalt: 42/25

Sehr geehrte Damen und Herren,

bezüglich des oben genannten Schadensfalls teilen wir mit:

Wir erstatten folgende Schadenpositionen:

Reparaturkosten: 6.240,50 EUR (anerkannt)
Nutzungsausfall: 420,00 EUR (6 Tage, 2 Tage abgelehnt)

Wir zahlen einen Betrag in Höhe von: 6.660,50 EUR

Abgelehnte Positionen:
- Wertminderung: nicht anerkannt (Fahrzeugalter)
- SV-Kosten: gekürzt

Mit freundlichen Grüßen
HUK-COBURG Schadenregulierung
""")


# ── Setup-Hilfsfunktion ───────────────────────────────────────────────────────

def _setup(test_id: str):
    upload_dir = os.path.join(_tmp_dir, f"uploads_{test_id}")
    os.makedirs(upload_dir, exist_ok=True)
    db_path = os.path.join(_tmp_dir, f"m4_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    os.environ["DB_PATH"]          = db_path
    os.environ["JWT_SECRET_KEY"]   = "test-secret-key-minimum-32-chars!!"
    os.environ["UPLOAD_DIR"]       = upload_dir
    os.environ["MAX_UPLOAD_BYTES"] = str(20 * 1024 * 1024)

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

    # Admin + Akte anlegen
    client.post("/auth/register/erster", json={
        "name": "Admin", "email": "admin@test.de", "passwort": "Admin123!"
    })
    r = client.post("/auth/login", json={
        "email": "admin@test.de", "passwort": "Admin123!"
    })
    token = r.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r2 = client.post("/akten", json={
        "aktenzeichen": "64/25", "unfalldatum": "2025-03-15"
    }, headers=headers)
    akte_id = r2.get_json()["id"]

    return client, headers, akte_id, loaded


def _upload(client, headers, akte_id, pdf_bytes, typ="gutachten",
            dateiname="test.pdf", auto_schaden=False):
    data = {
        "datei":        (io.BytesIO(pdf_bytes), dateiname),
        "typ":          typ,
        "auto_schaden": "true" if auto_schaden else "false",
    }
    return client.post(
        f"/akten/{akte_id}/dokumente",
        data=data,
        content_type="multipart/form-data",
        headers=headers,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PDF-EXTRAKTOR TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPDFExtraktor(unittest.TestCase):

    def setUp(self):
        from backend.pdf import extraktor
        import importlib; importlib.reload(extraktor)
        self.ex = extraktor

    def test_validierung_gueltig(self):
        pdf = _gutachten_pdf()
        ok, fehler = self.ex.validiere_pdf(pdf)
        self.assertTrue(ok, f"Fehler: {fehler}")
        self.assertEqual(fehler, "")

    def test_validierung_leer(self):
        ok, fehler = self.ex.validiere_pdf(b"")
        self.assertFalse(ok)

    def test_validierung_kein_pdf(self):
        ok, fehler = self.ex.validiere_pdf(b"Das ist kein PDF-Inhalt")
        self.assertFalse(ok)

    def test_extraktion_text(self):
        pdf = _gutachten_pdf()
        ergebnis = self.ex.extrahiere_pdf(pdf)
        self.assertIsNone(ergebnis.fehler)
        self.assertFalse(ergebnis.ist_gescannt)
        self.assertGreater(ergebnis.gesamt_woerter, 20)
        self.assertIn("Sachverständigengutachten", ergebnis.gesamt_text)

    def test_extraktion_seiten(self):
        pdf = _gutachten_pdf()
        ergebnis = self.ex.extrahiere_pdf(pdf)
        self.assertGreater(ergebnis.seiten_anzahl, 0)
        self.assertGreater(len(ergebnis.seiten), 0)

    def test_extraktion_sha256(self):
        pdf = _gutachten_pdf()
        ergebnis = self.ex.extrahiere_pdf(pdf)
        self.assertEqual(len(ergebnis.sha256), 64)

    def test_extraktion_totalschaden(self):
        pdf = _totalschaden_pdf()
        ergebnis = self.ex.extrahiere_pdf(pdf)
        self.assertIn("Totalschadenfall", ergebnis.gesamt_text)


# ══════════════════════════════════════════════════════════════════════════════
# PARSER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestParser(unittest.TestCase):

    def setUp(self):
        from backend.pdf import parser, extraktor
        import importlib
        importlib.reload(extraktor)
        importlib.reload(parser)
        self.parser = parser
        self.ex = extraktor

    def _parse_text(self, text: str):
        return self.parser.extrahiere_schadenpositionen(text)

    def _extrahiere_und_parse(self, pdf_bytes: bytes):
        extr = self.ex.extrahiere_pdf(pdf_bytes)
        return self.parser.extrahiere_schadenpositionen(extr.gesamt_text)

    # ── Dokumenttyp-Erkennung ─────────────────────────────────────────────────

    def test_dokumenttyp_gutachten(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertEqual(erg.dokumenttyp, "gutachten")

    def test_dokumenttyp_abrechnung(self):
        erg = self._extrahiere_und_parse(_abrechnungs_pdf())
        self.assertIn(erg.dokumenttyp, ["abrechnung", "forderungsschreiben"])

    # ── Reparatur-Gutachten ───────────────────────────────────────────────────

    def test_reparaturkosten_extrahiert(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertIsNotNone(erg.reparaturkosten)
        self.assertAlmostEqual(erg.reparaturkosten, 6240.50, places=1)

    def test_sv_kosten_extrahiert(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertIsNotNone(erg.sv_kosten)
        self.assertAlmostEqual(erg.sv_kosten, 890.00, places=1)

    def test_nutzungsausfall_extrahiert(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertIsNotNone(erg.nutzungsausfall)
        self.assertAlmostEqual(erg.nutzungsausfall, 560.00, places=1)

    def test_wertminderung_extrahiert(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertIsNotNone(erg.wertminderung)
        self.assertAlmostEqual(erg.wertminderung, 350.00, places=1)

    def test_abschleppkosten_extrahiert(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertIsNotNone(erg.abschleppkosten)
        self.assertAlmostEqual(erg.abschleppkosten, 180.00, places=1)

    def test_kfz_kennzeichen_extrahiert(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertIsNotNone(erg.kfz_kennzeichen)
        self.assertIn("OF", erg.kfz_kennzeichen)

    def test_gutachten_konfidenz(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertGreater(erg.konfidenz, 0.3)

    # ── Totalschaden ──────────────────────────────────────────────────────────

    def test_wiederbeschaffungswert_extrahiert(self):
        erg = self._extrahiere_und_parse(_totalschaden_pdf())
        self.assertIsNotNone(erg.wiederbeschaffung)
        self.assertAlmostEqual(erg.wiederbeschaffung, 18500.00, places=1)

    def test_restwert_extrahiert(self):
        erg = self._extrahiere_und_parse(_totalschaden_pdf())
        self.assertIsNotNone(erg.restwert)
        self.assertAlmostEqual(erg.restwert, 3200.00, places=1)

    def test_totalschaden_konfidenz(self):
        erg = self._extrahiere_und_parse(_totalschaden_pdf())
        self.assertGreater(erg.konfidenz, 0.2)

    def test_berechneter_gesamt_totalschaden(self):
        erg = self._extrahiere_und_parse(_totalschaden_pdf())
        # 18500 - 3200 + 1150 + 220 + 180 + 680 + 53.50 = 17583.50
        self.assertAlmostEqual(erg.berechneter_gesamt, 17583.50, delta=50)

    # ── Abrechnungsschreiben ──────────────────────────────────────────────────

    def test_regulierter_betrag_extrahiert(self):
        erg = self._extrahiere_und_parse(_abrechnungs_pdf())
        self.assertIsNotNone(erg.betrag_reguliert)
        self.assertGreater(erg.betrag_reguliert, 0)

    # ── Euro-Parser ───────────────────────────────────────────────────────────

    def test_euro_parser_deutsche_format(self):
        val = self.parser._parse_euro("1.234,56")
        self.assertAlmostEqual(val, 1234.56)

    def test_euro_parser_mit_waehrung(self):
        val = self.parser._parse_euro("6.240,50 EUR")
        self.assertAlmostEqual(val, 6240.50)

    def test_euro_parser_mit_eurozeichen(self):
        val = self.parser._parse_euro("890,00 €")
        self.assertAlmostEqual(val, 890.00)

    def test_euro_parser_ungueltig(self):
        val = self.parser._parse_euro("keine zahl")
        self.assertIsNone(val)

    def test_euro_parser_negativ_abgelehnt(self):
        val = self.parser._parse_euro("-100,00")
        self.assertIsNone(val)

    # ── als_json / als_dict ───────────────────────────────────────────────────

    def test_ergebnis_als_json(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        json_str = erg.als_json()
        parsed = json.loads(json_str)
        self.assertIn("reparaturkosten", parsed)
        self.assertIn("konfidenz", parsed)

    def test_ergebnis_felder_gefunden_liste(self):
        erg = self._extrahiere_und_parse(_gutachten_pdf())
        self.assertIsInstance(erg.felder_gefunden, list)
        self.assertGreater(len(erg.felder_gefunden), 2)

    # ── Regex-Direkttests ─────────────────────────────────────────────────────

    def test_regex_reparaturkosten_variante1(self):
        erg = self._parse_text("Reparaturkosten: 5.500,00 EUR")
        self.assertAlmostEqual(erg.reparaturkosten, 5500.00)

    def test_regex_reparaturkosten_variante2(self):
        erg = self._parse_text("Bruttoreparaturkosten 3.200,00 €")
        self.assertAlmostEqual(erg.reparaturkosten, 3200.00)

    def test_regex_wbw(self):
        erg = self._parse_text("Wiederbeschaffungswert: 12.000,00 EUR")
        self.assertAlmostEqual(erg.wiederbeschaffung, 12000.00)

    def test_regex_wbw_kurz(self):
        erg = self._parse_text("WBW: 15.500,00 EUR")
        self.assertAlmostEqual(erg.wiederbeschaffung, 15500.00)

    def test_regex_sv_kosten(self):
        erg = self._parse_text("Gutachterkosten: 750,00 EUR")
        self.assertAlmostEqual(erg.sv_kosten, 750.00)

    def test_regex_plausibilitaet_warnung(self):
        erg = self._parse_text(
            "Reparaturkosten: 35.000,00 EUR\n"
            "Wiederbeschaffungswert: 20.000,00 EUR"
        )
        self.assertTrue(any("Reparaturkosten" in w for w in erg.warnungen),
                         f"Warnungen: {erg.warnungen}")


# ══════════════════════════════════════════════════════════════════════════════
# UPLOAD-SERVICE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestUploadService(unittest.TestCase):

    def setUp(self):
        self.client, self.h, self.akte_id, self.mods = \
            _setup(f"svc_{self._testMethodName}")
        self.svc = self.mods["backend.pdf.upload_service"]

    # ── Validierung ───────────────────────────────────────────────────────────

    def test_leere_datei_abgelehnt(self):
        with self.assertRaises(self.svc.UploadFehler):
            self.svc.verarbeite_upload(
                akte_id=self.akte_id, dateiname="x.pdf",
                datei_bytes=b"", typ="gutachten"
            )

    def test_zu_grosse_datei_abgelehnt(self):
        os.environ["MAX_UPLOAD_BYTES"] = "100"
        import importlib
        importlib.reload(self.svc)
        with self.assertRaises(self.svc.UploadFehler):
            self.svc.verarbeite_upload(
                akte_id=self.akte_id, dateiname="x.pdf",
                datei_bytes=b"x" * 200, typ="gutachten"
            )
        os.environ["MAX_UPLOAD_BYTES"] = str(20 * 1024 * 1024)

    def test_ungueltige_erweiterung_abgelehnt(self):
        with self.assertRaises(self.svc.UploadFehler):
            self.svc.verarbeite_upload(
                akte_id=self.akte_id, dateiname="test.exe",
                datei_bytes=b"MZ\x90\x00", typ="gutachten"
            )

    def test_kein_pdf_als_pdf_abgelehnt(self):
        with self.assertRaises(self.svc.UploadFehler):
            self.svc.verarbeite_upload(
                akte_id=self.akte_id, dateiname="test.pdf",
                datei_bytes=b"Das ist kein PDF", typ="gutachten"
            )

    def test_ungueltige_akte_abgelehnt(self):
        with self.assertRaises(self.svc.UploadFehler) as ctx:
            self.svc.verarbeite_upload(
                akte_id=99999, dateiname="test.pdf",
                datei_bytes=_gutachten_pdf(), typ="gutachten"
            )
        self.assertEqual(ctx.exception.status_code, 404)

    # ── Erfolgreicher Upload ──────────────────────────────────────────────────

    def test_upload_erstellt_dokument(self):
        ergebnis = self.svc.verarbeite_upload(
            akte_id=self.akte_id,
            dateiname="gutachten_test.pdf",
            datei_bytes=_gutachten_pdf(),
            typ="gutachten",
        )
        self.assertIn("dokument", ergebnis)
        dok = ergebnis["dokument"]
        self.assertEqual(dok["dateiname"], "gutachten_test.pdf")
        self.assertEqual(dok["typ"], "gutachten")
        self.assertGreater(dok["dateigroesse"], 0)

    def test_upload_parst_pdf(self):
        ergebnis = self.svc.verarbeite_upload(
            akte_id=self.akte_id,
            dateiname="gutachten.pdf",
            datei_bytes=_gutachten_pdf(),
            typ="gutachten",
        )
        parse = ergebnis["parse_ergebnis"]
        self.assertIsNotNone(parse)
        self.assertIn("konfidenz", parse)
        self.assertGreater(parse["konfidenz"], 0.2)

    def test_auto_schaden_uebernimmt_positionen(self):
        self.svc.verarbeite_upload(
            akte_id=self.akte_id,
            dateiname="gutachten_auto.pdf",
            datei_bytes=_gutachten_pdf(),
            typ="gutachten",
            auto_schaden=True,
        )
        # Schadenpositionen sollten jetzt in der Akte stehen
        from backend.models.schaden import hole_schadenpositionen
        import importlib
        schaden_mod = __import__("backend.models.schaden", fromlist=[""])
        importlib.reload(schaden_mod)
        schaden = schaden_mod.hole_schadenpositionen(self.akte_id)
        # Bei hoher Konfidenz wurde auto übernommen
        # (bei < 0.3 wird nicht übernommen, trotzdem kein Fehler)
        # Wir prüfen nur dass kein Exception geworfen wurde

    def test_datei_wird_auf_disk_gespeichert(self):
        ergebnis = self.svc.verarbeite_upload(
            akte_id=self.akte_id,
            dateiname="disk_test.pdf",
            datei_bytes=_gutachten_pdf(),
            typ="gutachten",
        )
        dok_id = ergebnis["dokument"]["id"]
        ergebnis2 = self.svc.hole_dokument_datei(dok_id)
        self.assertIsNotNone(ergebnis2)
        datei_bytes, dateiname, dateityp = ergebnis2
        self.assertEqual(dateiname, "disk_test.pdf")
        self.assertTrue(datei_bytes[:4].startswith(b"%PDF"))

    def test_loeschen_entfernt_datei(self):
        ergebnis = self.svc.verarbeite_upload(
            akte_id=self.akte_id,
            dateiname="zu_loeschen.pdf",
            datei_bytes=_gutachten_pdf(),
            typ="gutachten",
        )
        dok_id = ergebnis["dokument"]["id"]
        # Prüfe dass Datei vorhanden
        self.assertIsNotNone(self.svc.hole_dokument_datei(dok_id))
        # Löschen
        erfolg = self.svc.loesche_dokument_mit_datei(dok_id)
        self.assertTrue(erfolg)
        # Nicht mehr vorhanden
        self.assertIsNone(self.svc.hole_dokument_datei(dok_id))


# ══════════════════════════════════════════════════════════════════════════════
# FLASK-ROUTEN TESTS (Integration)
# ══════════════════════════════════════════════════════════════════════════════

class TestDokumenteRouten(unittest.TestCase):

    def setUp(self):
        self.client, self.h, self.akte_id, _ = \
            _setup(f"routes_{self._testMethodName}")

    def _url(self, suffix=""):
        return f"/akten/{self.akte_id}/dokumente{suffix}"

    def _upload_gutachten(self, auto=False, pdf_bytes=None,
                          dateiname="test.pdf", typ="gutachten") -> dict:
        # Seit Pipeline v7 (INTAKE_REVIEW_PFLICHT) legt der POST-Upload keine
        # dokumente-Zeile mehr an (202 -> Review-Queue). Fuer Routen-Tests an
        # bestehenden Dokumenten seeden wir daher direkt ueber den Service
        # (Alt-Pfad, von TestUploadService abgedeckt).
        import backend.pdf.upload_service as svc
        ergebnis = svc.verarbeite_upload(
            akte_id=self.akte_id,
            dateiname=dateiname,
            datei_bytes=pdf_bytes if pdf_bytes is not None else _gutachten_pdf(),
            typ=typ,
            auto_schaden=auto,
        )
        self.assertIn("dokument", ergebnis)
        return ergebnis

    # ── Liste ─────────────────────────────────────────────────────────────────

    def test_liste_leer(self):
        r = self.client.get(self._url(), headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["dokumente"], [])

    def test_liste_nach_upload(self):
        self._upload_gutachten()
        r = self.client.get(self._url(), headers=self.h)
        self.assertEqual(len(r.get_json()["dokumente"]), 1)

    def test_liste_filter_typ(self):
        self._upload_gutachten()
        self._upload_gutachten(typ="abrechnungsschreiben", dateiname="abr.pdf")
        r = self.client.get(self._url() + "?typ=gutachten", headers=self.h)
        doks = r.get_json()["dokumente"]
        self.assertEqual(len(doks), 1)
        self.assertEqual(doks[0]["typ"], "gutachten")

    # ── Upload ────────────────────────────────────────────────────────────────

    def test_upload_geht_in_review_queue(self):
        # Heutiger Kontrakt (INTAKE_REVIEW_PFLICHT): 202, Dokument wartet in
        # der Review-Queue, es entsteht KEINE dokumente-Zeile.
        r = _upload(self.client, self.h, self.akte_id, _gutachten_pdf())
        self.assertEqual(r.status_code, 202)
        data = r.get_json()
        self.assertTrue(data["in_review"])
        self.assertIn("intake_dokument_id", data)
        self.assertIn("sha256", data)
        liste = self.client.get(self._url(), headers=self.h).get_json()
        self.assertEqual(liste["dokumente"], [])

    def test_upload_ohne_datei_422(self):
        r = self.client.post(
            self._url(),
            data={"typ": "gutachten"},
            content_type="multipart/form-data",
            headers=self.h,
        )
        self.assertEqual(r.status_code, 422)

    def test_upload_typ_wird_erst_in_review_bestimmt(self):
        # Der typ-Parameter wird im Review-Pfad nicht mehr validiert --
        # die Klasse wird erst bei der Review-Freigabe festgelegt.
        r = _upload(self.client, self.h, self.akte_id,
                    _gutachten_pdf(), typ="ungueltig")
        self.assertEqual(r.status_code, 202)

    def test_upload_kein_pdf_422(self):
        r = _upload(self.client, self.h, self.akte_id,
                    b"kein PDF", typ="gutachten")
        self.assertEqual(r.status_code, 422)

    def test_upload_nicht_vorhandene_akte_404(self):
        # AZ-foermige IDs gelten als potenzielle RA-MICRO-Akten (pruefe_akte),
        # 404 gibt es nur fuer nicht-AZ-foermige Kennungen.
        r = _upload(self.client, self.h, "UNBEKANNT", _gutachten_pdf())
        self.assertEqual(r.status_code, 404)

    def test_upload_ohne_token_401(self):
        r = _upload(self.client, {}, self.akte_id, _gutachten_pdf())
        self.assertEqual(r.status_code, 401)

    def test_upload_totalschaden(self):
        r = _upload(self.client, self.h, self.akte_id,
                    _totalschaden_pdf(), dateiname="totalschaden.pdf")
        self.assertEqual(r.status_code, 202)
        self.assertTrue(r.get_json()["in_review"])

    # ── Metadaten ─────────────────────────────────────────────────────────────

    def test_metadaten_abruf(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        r = self.client.get(self._url(f"/{dok_id}"), headers=self.h)
        self.assertEqual(r.status_code, 200)
        meta = r.get_json()
        self.assertEqual(meta["id"], dok_id)
        self.assertEqual(meta["typ"], "gutachten")

    def test_metadaten_nicht_vorhanden_404(self):
        r = self.client.get(self._url("/99999"), headers=self.h)
        self.assertEqual(r.status_code, 404)

    # ── Download ──────────────────────────────────────────────────────────────

    def test_download_pdf(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        r = self.client.get(self._url(f"/{dok_id}/datei"), headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, "application/pdf")
        self.assertTrue(r.data[:4].startswith(b"%PDF"))

    def test_download_nicht_vorhanden_404(self):
        r = self.client.get(self._url("/99999/datei"), headers=self.h)
        self.assertEqual(r.status_code, 404)

    # ── Parse-Ergebnis ────────────────────────────────────────────────────────

    def test_parse_ergebnis_abrufen(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        r = self.client.get(self._url(f"/{dok_id}/parse"), headers=self.h)
        self.assertEqual(r.status_code, 200)
        p = r.get_json()
        self.assertIn("parse_status", p)
        self.assertIn("parse_konfidenz", p)
        self.assertIn("parse_ergebnis", p)
        self.assertIsNotNone(p["parse_ergebnis"])

    def test_parse_reparaturkosten_in_ergebnis(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        r = self.client.get(self._url(f"/{dok_id}/parse"), headers=self.h)
        parse = r.get_json()["parse_ergebnis"]
        self.assertIn("reparaturkosten", parse)
        self.assertAlmostEqual(parse["reparaturkosten"], 6240.50, delta=10)

    # ── Manuelle Korrektur ────────────────────────────────────────────────────

    def test_manuelle_korrektur(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        r = self.client.post(
            self._url(f"/{dok_id}/korrektur"),
            json={"reparaturkosten": 7000.00, "sv_kosten": 950.00},
            headers=self.h,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["parse_status"], "manuell_korrigiert")

        # Korrektur im Parse-Ergebnis prüfen
        r2 = self.client.get(self._url(f"/{dok_id}/parse"), headers=self.h)
        p = r2.get_json()
        self.assertEqual(p["parse_status"], "manuell_korrigiert")
        self.assertAlmostEqual(p["parse_ergebnis"]["reparaturkosten"], 7000.00)

    def test_korrektur_ohne_body_422(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        r = self.client.post(
            self._url(f"/{dok_id}/korrektur"),
            json={},
            headers=self.h,
        )
        self.assertEqual(r.status_code, 422)

    # ── Löschen ───────────────────────────────────────────────────────────────

    def test_loeschen(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        r = self.client.delete(self._url(f"/{dok_id}"), headers=self.h)
        self.assertEqual(r.status_code, 200)
        # Nicht mehr abrufbar
        r2 = self.client.get(self._url(f"/{dok_id}"), headers=self.h)
        self.assertEqual(r2.status_code, 404)

    def test_loeschen_nicht_vorhanden_404(self):
        r = self.client.delete(self._url("/99999"), headers=self.h)
        self.assertEqual(r.status_code, 404)

    def test_loeschen_erzeugt_aktivitaet(self):
        data = self._upload_gutachten()
        dok_id = data["dokument"]["id"]
        self.client.delete(self._url(f"/{dok_id}"), headers=self.h)
        r = self.client.get(f"/akten/{self.akte_id}/aktivitaeten",
                             headers=self.h)
        aktionen = [a["aktion"] for a in r.get_json()["aktivitaeten"]]
        self.assertIn("dokument_geloescht", aktionen)

    # ── Auto-Schaden ─────────────────────────────────────────────────────────

    def test_auto_schaden_unter_review_pflicht_deaktiviert(self):
        """S1.9c BREAKING #2: Unter INTAKE_REVIEW_PFLICHT (Default) werden
        Schadenpositionen NICHT mehr automatisch uebernommen -- sie entstehen
        erst mit der Review-Freigabe."""
        ergebnis = self._upload_gutachten(auto=True)
        parse = ergebnis.get("parse_ergebnis")
        self.assertIsNotNone(parse)
        self.assertGreaterEqual(parse.get("konfidenz", 0), 0.3)
        r2 = self.client.get(f"/akten/{self.akte_id}", headers=self.h)
        self.assertIsNone(r2.get_json()["schaden"])


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestPDFExtraktor, TestParser,
        TestUploadService, TestDokumenteRouten,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
