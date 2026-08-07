"""
Tests fuer _mandant_adresse (distanz_routes): lokale beteiligte-Tabelle
zuerst, read-only RA-MICRO-Fallback wenn lokal kein Mandant mit Adresse
(Befund 1280/25: frische RA-MICRO-Akten haben lokal 0 beteiligte-Zeilen).
Beide Datenquellen sind gemockt.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Beteiligter:
    def __init__(self, rolle="mandant", anschrift="", plz="", ort=""):
        self.rolle = rolle
        self.anschrift = anschrift
        self.plz = plz
        self.ort = ort


RAMICRO_MANDANT = {"mandant": {"name": "Mustermann",
                               "anschrift": "Andréstr. 10",
                               "plz": "63067", "ort": "Offenbach"},
                   "gegner": None, "alle_gegner": [], "sonstige": []}


class TestMandantAdresse(unittest.TestCase):
    def _rufe(self, lokal, ramicro):
        from backend.routers.distanz_routes import _mandant_adresse
        with mock.patch("backend.models.schaden.hole_beteiligte_by_akte",
                        return_value=lokal), \
             mock.patch("backend.word.word_service._lade_beteiligte_aus_ramicro",
                        return_value=ramicro) as m_ra:
            return _mandant_adresse("1280/25"), m_ra

    def test_lokaler_mandant_gewinnt_ohne_ramicro_zugriff(self):
        adresse, m_ra = self._rufe(
            [_Beteiligter(anschrift="Hauptstr. 1", plz="63065", ort="Offenbach")],
            RAMICRO_MANDANT)
        self.assertEqual(adresse, "Hauptstr. 1, 63065 Offenbach")
        m_ra.assert_not_called()

    def test_ohne_lokale_beteiligte_greift_ramicro(self):
        adresse, m_ra = self._rufe([], RAMICRO_MANDANT)
        self.assertEqual(adresse, "Andréstr. 10, 63067 Offenbach")
        m_ra.assert_called_once_with("1280/25")

    def test_lokaler_mandant_ohne_adresse_faellt_auf_ramicro_zurueck(self):
        adresse, _ = self._rufe([_Beteiligter()], RAMICRO_MANDANT)
        self.assertEqual(adresse, "Andréstr. 10, 63067 Offenbach")

    def test_nirgends_mandant_liefert_none(self):
        adresse, _ = self._rufe(
            [], {"mandant": None, "gegner": None,
                 "alle_gegner": [], "sonstige": []})
        self.assertIsNone(adresse)

    def test_ramicro_mandant_ohne_adresse_liefert_none(self):
        adresse, _ = self._rufe(
            [], {"mandant": {"name": "X", "anschrift": "", "plz": "", "ort": ""},
                 "gegner": None, "alle_gegner": [], "sonstige": []})
        self.assertIsNone(adresse)


if __name__ == "__main__":
    unittest.main()
