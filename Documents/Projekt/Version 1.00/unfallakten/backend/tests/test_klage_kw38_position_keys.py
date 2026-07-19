"""
KW-38: Waechter-Test fuer POSITION_KEYS (backend/models/abrechnungsschreiben.py).

Sichert die Synchronitaet mit der kanonischen Frontend-Map
frontend/src/config/klagePositionKeys.js (KLAGE_KEY_MAP + KEYS_OHNE_POSITION),
die aus drei identischen Fahrzeugschaden-Maps in KlageSection.jsx/KlageWizard.jsx
zusammengefuehrt wurde. Reiner Waechter: ist direkt gruen, schlaegt erst fehl,
wenn POSITION_KEYS sich aendert, ohne dass die FE-Datei nachgezogen wird.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.abrechnungsschreiben import POSITION_KEYS

ERWARTET = {
    "reparaturkosten", "wiederbeschaffung", "restwert",
    "wertminderung", "nutzungsausfall", "mietwagenkosten",
    "sv_kosten", "abschleppkosten", "restkraftstoff", "standkosten",
    "anabmeldekosten", "schmerzensgeld", "sonstiges",
    "reparatur_brutto", "reparatur_netto",
    "wbw", "wbw_netto", "wbw_brutto", "wba",
    "fahrzeugschaden", "kostenpauschale",
    "ra_gebuehren", "mwst_abzug", "pruefbericht_abzug",
    "rep_gutachten_netto", "rep_rechnung_netto", "rep_rechnung_brutto",
    "verdienstausfall", "haushalt", "unkostenpauschale", "kostennb",
    "vorschuss",
    "sonstiges_wdm_1", "sonstiges_wdm_2", "sonstiges_wdm_3",
    "sonstiges_wdm_4", "sonstiges_wdm_5", "sonstiges_wdm_6",
}


class TestKw38KeyVertrag(unittest.TestCase):
    def test_position_keys_unveraendert(self):
        self.assertEqual(
            set(POSITION_KEYS), ERWARTET,
            "POSITION_KEYS geaendert - frontend/src/config/klagePositionKeys.js "
            "(KLAGE_KEY_MAP / KEYS_OHNE_POSITION) und deren Spiegel-Liste in "
            "frontend/src/config/__tests__/klagePositionKeys.test.js nachziehen!",
        )


if __name__ == "__main__":
    unittest.main()
