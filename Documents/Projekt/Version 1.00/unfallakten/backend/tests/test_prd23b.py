"""
PRD-23b – Unit-Tests
=====================
Testet rechnung_parser.py (Session 2) und belege_routes.py-Hilfsfunktionen (Session 1).
Keine DB-Verbindung erforderlich – reine Logik-Tests.

Ausfuehren:
  cd backend
  python -m pytest tests/test_prd23b.py -v
  # oder ohne pytest:
  python -m unittest tests.test_prd23b -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Hinweis: frueher wurden hier pdfplumber/flask/werkzeug/jwt via sys.modules
# gestubbt. Das hat die spaeter importierten Tests (test_sv_portal,
# test_s16*, test_modul8 u. a.) reihenfolge-abhaengig kaputtgemacht. Die
# Abhaengigkeiten stehen in requirements.txt und sind installiert -- die
# Stubs sind unnoetig. Fuer die auth.middleware nutzen wir einen lokalen
# Import-Guard, damit dieser Test auch dann laeuft, wenn das Modul im
# aktuellen Prozess noch nicht geladen wurde (kein sys.modules-Eingriff).

from backend.parsers.rechnung_parser import parse_rechnung, RechnungParseResult
from backend.routers.belege_routes import (
    _ist_firma,
    _position_aus_firmenname,
    _domain_aus_email,
    _klassifiziere_eakte_dok,
)


# ══════════════════════════════════════════════════════════════════════════════
# rechnung_parser.py
# ══════════════════════════════════════════════════════════════════════════════

class TestRechnungParserVollstaendig(unittest.TestCase):
    """Branch 1: Alle drei Werte vorhanden und konsistent → konfidenz 0.95"""

    TEXT = """
    Kfz-Müller GmbH
    Rechnungsnummer: RM-2024-1042
    Rechnungsdatum: 15.03.2024

    Nettobetrag          3.235,29 €
    Mehrwertsteuer 19 %    614,71 €
    Gesamtbetrag inkl. MwSt  3.850,00 €
    """

    def test_netto(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.nettobetrag, 3235.29, places=1)

    def test_mwst(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.mwst_betrag, 614.71, places=1)

    def test_brutto(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.bruttobetrag, 3850.00, places=1)

    def test_konfidenz_hoch(self):
        r = parse_rechnung(self.TEXT)
        self.assertGreaterEqual(r.konfidenz, 0.90)

    def test_keine_warnungen(self):
        r = parse_rechnung(self.TEXT)
        self.assertEqual(r.warnungen, [])

    def test_rechnungsnummer(self):
        r = parse_rechnung(self.TEXT)
        self.assertEqual(r.rechnungsnummer, "RM-2024-1042")

    def test_datum(self):
        r = parse_rechnung(self.TEXT)
        self.assertEqual(r.rechnungsdatum, "2024-03-15")


class TestRechnungParserInkonsistent(unittest.TestCase):
    """Branch 1b: Alle drei da, aber Netto+MwSt weicht >2€ von Brutto ab → konfidenz 0.60"""

    TEXT = """
    Nettobetrag 1.000,00 €
    MwSt. 19 % 190,00 €
    Gesamtbetrag: 1.500,00 €
    """

    def test_konfidenz_niedrig(self):
        r = parse_rechnung(self.TEXT)
        self.assertLess(r.konfidenz, 0.75)

    def test_warnung_gesetzt(self):
        r = parse_rechnung(self.TEXT)
        self.assertTrue(len(r.warnungen) > 0)
        self.assertIn("Plausibilitaet", r.warnungen[0])


class TestRechnungParserBruttoUndNetto(unittest.TestCase):
    """Branch 2: Brutto + Netto, kein MwSt-Wert → mwst = brutto - netto, konfidenz 0.90"""

    TEXT = """
    Nettobetrag: 420,17 EUR
    Rechnungsbetrag: 500,00 EUR
    """

    def test_mwst_abgeleitet(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.mwst_betrag, 79.83, places=1)

    def test_konfidenz(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.konfidenz, 0.90, places=2)


class TestRechnungParserBruttoUndMwst(unittest.TestCase):
    """Branch 3: Brutto + MwSt, kein Netto → netto = brutto - mwst, konfidenz 0.85"""

    TEXT = """
    zzgl. 19% MwSt: 95,00 €
    Endbetrag: 595,00 €
    """

    def test_netto_abgeleitet(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.nettobetrag, 500.00, places=0)

    def test_konfidenz(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.konfidenz, 0.85, places=2)


class TestRechnungParserNurBrutto(unittest.TestCase):
    """Branch 4: Nur Bruttobetrag → netto = brutto/1.19, konfidenz 0.65"""

    TEXT = """
    Zu zahlen: 1.190,00 EUR
    """

    def test_netto_aus_brutto(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.nettobetrag, 1000.00, places=0)

    def test_mwst_aus_brutto(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.mwst_betrag, 190.00, places=0)

    def test_konfidenz(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.konfidenz, 0.65, places=2)

    def test_warnung_gesetzt(self):
        r = parse_rechnung(self.TEXT)
        self.assertTrue(any("Bruttobetrag" in w for w in r.warnungen))


class TestRechnungParserNurNetto(unittest.TestCase):
    """Branch 5: Nur Nettobetrag → brutto = netto*1.19, konfidenz 0.65"""

    TEXT = """
    Nettobetrag  2.000,00 €
    """

    def test_brutto_aus_netto(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.bruttobetrag, 2380.00, places=0)

    def test_konfidenz(self):
        r = parse_rechnung(self.TEXT)
        self.assertAlmostEqual(r.konfidenz, 0.65, places=2)


class TestRechnungParserKeineBetraege(unittest.TestCase):
    """Branch 6: Kein Betrag gefunden → konfidenz 0.0"""

    TEXT = """
    Sehr geehrter Herr Mustermann,
    bitte prüfen Sie unser Angebot.
    """

    def test_konfidenz_null(self):
        r = parse_rechnung(self.TEXT)
        self.assertEqual(r.konfidenz, 0.0)

    def test_warnungen(self):
        r = parse_rechnung(self.TEXT)
        self.assertTrue(len(r.warnungen) > 0)

    def test_felder_leer(self):
        r = parse_rechnung(self.TEXT)
        self.assertIsNone(r.nettobetrag)
        self.assertIsNone(r.bruttobetrag)


class TestRechnungParserMuster(unittest.TestCase):
    """Verschiedene Formatvarianten der Patterns."""

    def test_gesamtbetrag_inkl_mwst(self):
        r = parse_rechnung("Gesamtbetrag inkl. MwSt: 595,00 EUR")
        self.assertAlmostEqual(r.bruttobetrag, 595.00, places=2)

    def test_rechnungsbetrag(self):
        r = parse_rechnung("Rechnungsbetrag: 1.234,56 €")
        self.assertAlmostEqual(r.bruttobetrag, 1234.56, places=2)

    def test_zahlungsbetrag(self):
        r = parse_rechnung("Zahlungsbetrag: 380,00 EUR")
        self.assertAlmostEqual(r.bruttobetrag, 380.00, places=2)

    def test_netto_variante_summe(self):
        r = parse_rechnung("Summe netto: 840,34 €\nRechnungsbetrag: 1.000,00 €")
        self.assertAlmostEqual(r.nettobetrag, 840.34, places=2)

    def test_mwst_variante_ust(self):
        r = parse_rechnung("USt. 19 %: 159,66 €\nRechnungsbetrag: 1.000,00 €")
        self.assertAlmostEqual(r.mwst_betrag, 159.66, places=2)

    def test_datum_ohne_label(self):
        # Fallback-Datum ohne Schlüsselwort
        r = parse_rechnung("Zu zahlen: 100,00 €\nAusgestellt am 01.12.2023")
        self.assertEqual(r.rechnungsdatum, "2023-12-01")

    def test_rechnungsnummer_variante_re_nr(self):
        r = parse_rechnung("Re.-Nr.: 2024/042\nZu zahlen: 100,00 €")
        self.assertIn("2024", r.rechnungsnummer)


# ══════════════════════════════════════════════════════════════════════════════
# belege_routes.py – Hilfsfunktionen
# ══════════════════════════════════════════════════════════════════════════════

class TestIstFirma(unittest.TestCase):

    def test_anrede_firma(self):
        self.assertTrue(_ist_firma({"anrede": "Firma", "vorname": "", "rolle": "sonstiger"}))

    def test_anrede_firma_lowercase(self):
        self.assertTrue(_ist_firma({"anrede": "firma", "vorname": "", "rolle": "sonstiger"}))

    def test_kein_vorname_kein_mandant(self):
        self.assertTrue(_ist_firma({"anrede": "", "vorname": "", "rolle": "sonstiger"}))

    def test_kein_vorname_aber_mandant(self):
        # Mandant ohne Vorname ist keine Firma
        self.assertFalse(_ist_firma({"anrede": "", "vorname": "", "rolle": "mandant"}))

    def test_hat_vorname(self):
        self.assertFalse(_ist_firma({"anrede": "", "vorname": "Hans", "rolle": "sonstiger"}))

    def test_natuerliche_person(self):
        self.assertFalse(_ist_firma({"anrede": "Herr", "vorname": "Hans", "rolle": "sonstiger"}))


class TestPositionAusFirmenname(unittest.TestCase):

    def test_werkstatt(self):
        self.assertEqual(_position_aus_firmenname("Kfz-Werkstatt Müller GmbH"), "rep_rechnung_netto")

    def test_karosserie(self):
        self.assertEqual(_position_aus_firmenname("Karosserie & Lack Schmidt"), "rep_rechnung_netto")

    def test_mietwagen(self):
        self.assertEqual(_position_aus_firmenname("Mietwagen Weber KG"), "mietwagenkosten_netto")

    def test_hertz(self):
        self.assertEqual(_position_aus_firmenname("Hertz Deutschland GmbH"), "mietwagenkosten_netto")

    def test_sixt(self):
        self.assertEqual(_position_aus_firmenname("Sixt SE"), "mietwagenkosten_netto")

    def test_abschlepp(self):
        self.assertEqual(_position_aus_firmenname("Pannendienst ADAC"), "abschleppkosten")

    def test_bergung(self):
        self.assertEqual(_position_aus_firmenname("Bergung & Abschlepp Nord GmbH"), "abschleppkosten")

    def test_standplatz(self):
        self.assertEqual(_position_aus_firmenname("Depot und Abstellplatz AG"), "standkosten_netto")

    def test_unbekannt(self):
        self.assertIsNone(_position_aus_firmenname("Blumenladen Rosengarten"))

    def test_leer(self):
        self.assertIsNone(_position_aus_firmenname(""))

    def test_none(self):
        self.assertIsNone(_position_aus_firmenname(None))


class TestDomainAusEmail(unittest.TestCase):

    def test_normal(self):
        self.assertEqual(_domain_aus_email("info@kfz-mueller.de"), "kfz-mueller.de")

    def test_grossbuchstaben_normalisiert(self):
        self.assertEqual(_domain_aus_email("RECHNUNG@KFZ-MUELLER.DE"), "kfz-mueller.de")

    def test_kein_at(self):
        self.assertIsNone(_domain_aus_email("keineat.de"))

    def test_leer(self):
        self.assertIsNone(_domain_aus_email(""))

    def test_none(self):
        self.assertIsNone(_domain_aus_email(None))

    def test_whitespace_entfernt(self):
        self.assertEqual(_domain_aus_email("info@beispiel.de  "), "beispiel.de")


class TestKlassifiziereEakteDok(unittest.TestCase):

    def _sv(self, email="sv@gutachter.de"):
        return {"rolle": "sachverstaendiger", "name": "SV-Büro Beispiel", "vorname": "", "anrede": "", "email": email}

    def _firma(self, name, email=""):
        return {"rolle": "sonstiger", "name": name, "vorname": "", "anrede": "Firma", "email": email}

    def test_sv_domain_match(self):
        dok = {"absender_domain": "gutachter.de", "anzeigename": "Gutachten.pdf"}
        beteiligte = [self._sv("sv@gutachter.de")]
        r = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer=False)
        self.assertIsNotNone(r)
        self.assertEqual(r["position_key"], "sv_kosten")
        self.assertAlmostEqual(r["konfidenz"], 0.90, places=2)

    def test_sv_domain_match_vorsteuer(self):
        dok = {"absender_domain": "gutachter.de", "anzeigename": "Gutachten.pdf"}
        beteiligte = [self._sv("sv@gutachter.de")]
        r = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer=True)
        self.assertEqual(r["position_key"], "sv_kosten_netto")

    def test_firma_domain_match(self):
        dok = {"absender_domain": "kfz-mueller.de", "anzeigename": "Rechnung.pdf"}
        beteiligte = [self._firma("Kfz-Werkstatt Müller GmbH", "info@kfz-mueller.de")]
        r = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer=False)
        self.assertIsNotNone(r)
        self.assertEqual(r["position_key"], "rep_rechnung_netto")
        self.assertAlmostEqual(r["konfidenz"], 0.90, places=2)

    def test_firma_name_heuristik(self):
        # Kein Domain-Match, aber Firmenname trifft
        dok = {"absender_domain": "", "anzeigename": "Dokument.pdf"}
        beteiligte = [self._firma("Mietwagen Schneider GmbH", "")]
        r = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer=False)
        self.assertIsNotNone(r)
        self.assertEqual(r["position_key"], "mietwagenkosten_netto")
        self.assertAlmostEqual(r["konfidenz"], 0.60, places=2)

    def test_dateiname_fallback(self):
        dok = {"absender_domain": "", "anzeigename": "Rechnung_2024.pdf"}
        beteiligte = []
        r = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer=False)
        self.assertIsNotNone(r)
        self.assertIsNone(r["position_key"])
        self.assertAlmostEqual(r["konfidenz"], 0.40, places=2)

    def test_kein_treffer(self):
        dok = {"absender_domain": "", "anzeigename": "Brief.pdf"}
        beteiligte = []
        r = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer=False)
        self.assertIsNone(r)

    def test_natuerliche_person_wird_ignoriert(self):
        # Beteiligter mit Vorname ist keine Firma → kein Firmen-Treffer
        dok = {"absender_domain": "mueller.de", "anzeigename": "X.pdf"}
        beteiligte = [{"rolle": "sonstiger", "name": "Müller", "vorname": "Hans", "anrede": "", "email": "hans@mueller.de"}]
        r = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer=False)
        # Kein Domain-Match als Firma, also maximal Dateiname-Fallback oder None
        self.assertTrue(r is None or r.get("konfidenz", 1) < 0.70)


if __name__ == "__main__":
    unittest.main(verbosity=2)
