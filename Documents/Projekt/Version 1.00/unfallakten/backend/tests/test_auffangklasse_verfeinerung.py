"""Die Auffangklasse `sonstiges` wird nachtraeglich verfeinert.

Beide Klassen (lichtbild, versicherungsschreiben) tragen bewusst keine Marker.
Sie duerfen NUR greifen, wo der Klassifikator sonst `sonstiges` liefert --
sonst zoegen sie abfotografierte Rechnungen und Abrechnungsschreiben an sich.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-auffangklasse")

from backend.intake.klassifikator import verfeinere_auffangklasse


def _bild(name="IMG_0195.jpeg"):
    return [{"dateiname": name}]


def _versicherer():
    return [{"absender_kategorie": "versicherung",
             "versicherer_name": "HUK-COBURG Versicherung"}]


class TestLichtbild(unittest.TestCase):

    def test_bilddatei_aus_sonstiges_wird_lichtbild(self):
        self.assertEqual(
            verfeinere_auffangklasse("sonstiges", _bild()), ("lichtbild", "bilddatei"))

    def test_alle_gaengigen_bildendungen(self):
        for name in ("foto.jpg", "Foto.JPEG", "bild.png", "IMG_1.HEIC",
                     "IMG-20260830-WA0001.jpg"):
            self.assertEqual(
                verfeinere_auffangklasse("sonstiges", _bild(name))[0], "lichtbild", name)

    def test_abfotografierte_rechnung_behaelt_ihre_klasse(self):
        """Der wichtigste Fall: 8 der 46 Bilddateien im Bestand sind
        abfotografierte Dokumente und korrekt erkannt."""
        self.assertEqual(
            verfeinere_auffangklasse("rechnung", _bild()), ("rechnung", None))

    def test_pdf_wird_kein_lichtbild(self):
        self.assertEqual(
            verfeinere_auffangklasse("sonstiges", [{"dateiname": "Anschreiben.pdf"}]),
            ("sonstiges", None))

    def test_ohne_dateinamen_kein_lichtbild(self):
        self.assertEqual(verfeinere_auffangklasse("sonstiges", []), ("sonstiges", None))


class TestVersicherungsschreiben(unittest.TestCase):

    def test_versicherer_aus_sonstiges_wird_versicherungsschreiben(self):
        self.assertEqual(
            verfeinere_auffangklasse("sonstiges", _versicherer()),
            ("versicherungsschreiben", "absender"))

    def test_abrechnungsschreiben_bleibt_abrechnungsschreiben(self):
        self.assertEqual(
            verfeinere_auffangklasse("abrechnungsschreiben", _versicherer()),
            ("abrechnungsschreiben", None))

    def test_gutachter_wird_nicht_versicherungsschreiben(self):
        self.assertEqual(
            verfeinere_auffangklasse("sonstiges",
                                     [{"absender_kategorie": "gutachter"}]),
            ("sonstiges", None))

    def test_unbekannter_absender_bleibt_sonstiges(self):
        self.assertEqual(
            verfeinere_auffangklasse("sonstiges", [{"absender_email": "a@gmail.com"}]),
            ("sonstiges", None))


class TestVorrang(unittest.TestCase):

    def test_bild_schlaegt_absender(self):
        """Ein Foto vom Versicherer bleibt ein Foto."""
        self.assertEqual(
            verfeinere_auffangklasse("sonstiges", _bild() + _versicherer())[0],
            "lichtbild")

    def test_signale_ohne_dict_stoeren_nicht(self):
        self.assertEqual(
            verfeinere_auffangklasse("sonstiges", [None, "quatsch", {"dateiname": "a.jpg"}])[0],
            "lichtbild")


class TestRegistry(unittest.TestCase):

    def test_beide_klassen_stehen_in_der_registry_und_ohne_marker(self):
        from backend.intake.registry_loader import lade_registry, standard_pfad
        reg = lade_registry(standard_pfad())
        for name in ("lichtbild", "versicherungsschreiben"):
            self.assertIn(name, reg.klassen)
            self.assertEqual(reg.klassen[name].get("marker") or [], [],
                             f"{name} darf keine Marker tragen")


if __name__ == "__main__":
    unittest.main()
