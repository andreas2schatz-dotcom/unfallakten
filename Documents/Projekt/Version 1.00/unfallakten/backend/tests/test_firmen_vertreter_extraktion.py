"""
Bugfix Vertreter-Lookup (828/24-Nachtest): HTML-Entities wurden durch
Leerzeichen ersetzt (Umlaute weg), und bei einer AG kamen
Geschaeftsfuehrer-Treffer fremder Impressen durch.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.routers.firmen_routes import (
    _extrahiere_vertreter,
    _funktion_default,
    _rechtsform,
)


def _html(inhalt):
    return f"<html><body><div>Impressum</div><p>{inhalt}</p></body></html>"


class TestExtrahiereVertreter(unittest.TestCase):
    def test_umlaute_aus_entities_bleiben_erhalten(self):
        html = _html("Gesch&auml;ftsf&uuml;hrer: Markus Groi&szlig;")
        treffer = _extrahiere_vertreter(html, "Gesch\xe4ftsf\xfchrer")
        self.assertEqual(treffer[0]["name"], "Markus Groi\xdf")
        self.assertEqual(treffer[0]["funktion"], "Gesch\xe4ftsf\xfchrer")

    def test_numerische_entities(self):
        html = _html("Vorstand: J&#252;rgen M&#246;ller")
        treffer = _extrahiere_vertreter(html, "Vorstand")
        self.assertEqual(treffer[0]["name"], "J\xfcrgen M\xf6ller")

    def test_ag_filtert_geschaeftsfuehrer_treffer(self):
        html = _html(
            "Gesch&auml;ftsf&uuml;hrer: Hans Fremd<br>"
            "Vorstand: Petra Richtig"
        )
        treffer = _extrahiere_vertreter(html, "Vorstand")
        namen = [t["name"] for t in treffer]
        self.assertIn("Petra Richtig", namen)
        self.assertNotIn("Hans Fremd", namen)

    def test_gmbh_filtert_vorstand_treffer(self):
        html = _html(
            "Vorstand: Petra Fremd<br>"
            "Gesch&auml;ftsf&uuml;hrer: Hans Richtig"
        )
        treffer = _extrahiere_vertreter(html, "Gesch\xe4ftsf\xfchrer")
        namen = [t["name"] for t in treffer]
        self.assertIn("Hans Richtig", namen)
        self.assertNotIn("Petra Fremd", namen)

    def test_vertreten_durch_mit_funktionswort_wird_zerlegt(self):
        html = _html("vertreten durch: Gesch&auml;ftsf&uuml;hrer Markus Groi&szlig;")
        treffer = _extrahiere_vertreter(html, "Gesch\xe4ftsf\xfchrer")
        self.assertEqual(treffer[0]["name"], "Markus Groi\xdf")
        self.assertEqual(treffer[0]["funktion"], "Gesch\xe4ftsf\xfchrer")

    def test_vertreten_durch_funktionswort_widerspricht_rechtsform(self):
        # AG erwartet Vorstand -> GF-Treffer aus fremdem Impressum fliegt raus
        html = _html("vertreten durch: Gesch&auml;ftsf&uuml;hrer Markus Fremd")
        self.assertEqual(_extrahiere_vertreter(html, "Vorstand"), [])

    def test_strasse_wird_nicht_teil_des_namens(self):
        html = _html("vertreten durch: Vorstand Markus Groi&szlig; Hansastra&szlig;e 19")
        treffer = _extrahiere_vertreter(html, "Vorstand")
        self.assertEqual(treffer[0]["name"], "Markus Groi\xdf")

    def test_unbekannte_rechtsform_laesst_alles_durch(self):
        html = _html("Inhaber: Klaus Klein")
        treffer = _extrahiere_vertreter(html, "gesetzlicher Vertreter")
        self.assertEqual(treffer[0]["funktion"], "Inhaber")

    def test_leeres_html(self):
        self.assertEqual(_extrahiere_vertreter("", "Vorstand"), [])
        self.assertEqual(_extrahiere_vertreter(None, "Vorstand"), [])


class TestFunktionDefault(unittest.TestCase):
    def test_kgaa_ist_vorstand_nicht_gf(self):
        self.assertEqual(_funktion_default("KGAA"), "Vorstand")

    def test_bestehende_faelle(self):
        self.assertEqual(_funktion_default("GMBH"), "Gesch\xe4ftsf\xfchrer")
        self.assertEqual(_funktion_default("AG"), "Vorstand")
        self.assertEqual(_funktion_default(""), "gesetzlicher Vertreter")


class TestRechtsform(unittest.TestCase):
    def test_ag_nur_als_eigenes_wort(self):
        self.assertEqual(_rechtsform("ADAC Autoversicherung AG"), "AG")
        self.assertEqual(_rechtsform("Magna Automotive"), "")

    def test_gmbh_co_kg_vor_gmbh(self):
        self.assertEqual(_rechtsform("Spedition Krause GmbH & Co. KG"), "GMBH & CO. KG")


if __name__ == "__main__":
    unittest.main()
