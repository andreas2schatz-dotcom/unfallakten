"""Dokumentdatum aus Registry-Rolle + geparsten Feldern."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestDokumentDatumAbleitung(unittest.TestCase):
    def setUp(self):
        from backend.intake.registry_loader import lade_registry, standard_pfad
        self.reg = lade_registry(standard_pfad())

    def _ab(self, klasse, felder, **kw):
        from backend.services.dokument_bezeichnung import (
            dokument_datum_aus_feldern,
        )
        return dokument_datum_aus_feldern(klasse, felder, self.reg, **kw)

    def test_gutachten_nutzt_besichtigungsdatum(self):
        self.assertEqual(
            self._ab("gutachten", {"besichtigungsdatum": "14.03.2024"}),
            "2024-03-14",
        )

    def test_rechnung_nutzt_rechnungsdatum(self):
        self.assertEqual(
            self._ab("mietwagenrechnung", {"rechnungsdatum": "2024-05-02"}),
            "2024-05-02",
        )

    def test_abrechnungsschreiben_nutzt_schreibdatum(self):
        self.assertEqual(
            self._ab("abrechnungsschreiben", {"schreibdatum": "01.06.2024"}),
            "2024-06-01",
        )

    def test_zeitstempel_wird_auf_das_datum_gekuerzt(self):
        self.assertEqual(
            self._ab("gutachten", {"besichtigungsdatum": "2024-03-14 09:12:00"}),
            "2024-03-14",
        )

    def test_ohne_feld_kein_datum(self):
        self.assertIsNone(self._ab("gutachten", {}))

    def test_unlesbares_datum_ergibt_none(self):
        self.assertIsNone(self._ab("gutachten", {"besichtigungsdatum": "Fruehjahr"}))

    def test_pruefbericht_hat_keine_datumsrolle(self):
        self.assertIsNone(self._ab("pruefbericht", {"vorgangsnummer": "4711"}))

    def test_sonstiges_ohne_eigenes_feld_hat_kein_datum(self):
        self.assertIsNone(self._ab("sonstiges", {}))

    def test_sonstiges_nutzt_das_eigene_feld(self):
        self.assertEqual(
            self._ab("sonstiges", {"datum": "03.02.2024"}), "2024-02-03")

    def test_fragebogen_uebernimmt_den_unfalltag_nicht(self):
        self.assertIsNone(
            self._ab("fragebogen", {"unfalltag": "27.04.2022"}))

    def test_unbekannte_klasse_ergibt_none(self):
        self.assertIsNone(self._ab("gibtsnicht", {"datum": "01.01.2024"}))

    def test_ohne_registry_ergibt_none(self):
        from backend.services.dokument_bezeichnung import (
            dokument_datum_aus_feldern,
        )
        self.assertIsNone(
            dokument_datum_aus_feldern("gutachten",
                                        {"besichtigungsdatum": "14.03.2024"},
                                        None)
        )


if __name__ == "__main__":
    unittest.main()
