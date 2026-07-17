"""
Bugfix KW-04: Eine Rechenquelle fuer Antrag 1, Schadentabelle, Differenz-Satz.

generiere_klageschrift() hatte drei unabhaengige Rechenwege: Antrag 1 (Summe der
checked cfg-Positionen), Schadentabelle (aus akte_daten["schaden"], DB-Werte,
ignoriert Checkboxen) und Differenz-Satz (schaden_gesamt - gesamt_reguliert_tbl,
wobei gesamt_reguliert_tbl nur positionsgebundene Zahlungen kennt). Diese drei
Werte konnten sich widersprechen.

Testmuster: generiere_klageschrift() wird echt aufgerufen (kein Mock), das
DOCX-Ergebnis per zipfile entpackt und word/document.xml als Text geprueft.
"""
import io
import json
import os
import sys
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.word.klage_service import generiere_klageschrift


def _position(key, label, betrag, betrag_original=None, checked=True):
    return {
        "key": key,
        "label": label,
        "betrag": betrag,
        "betragOriginal": betrag_original if betrag_original is not None else betrag,
        "checked": checked,
    }


def _akte_daten(positionen, schaden=None, reg_agg=None, abrechnungen=None, vorsteuer="N"):
    return {
        "akte": {"aktenzeichen": "55/26", "erstellt_am": "2026-01-01"},
        "mandant": {
            "vorname": "Max", "name": "Mustermann",
            "anschrift": "Musterstr. 1", "plz": "63067", "ort": "Offenbach",
            "anrede": "1", "vorsteuer": vorsteuer,
        },
        "kanzlei": {},
        "unfalldetails": {"schilderung": "Der Beklagte fuhr auf das Fahrzeug auf."},
        "klage_config": {
            "beklagte": [{
                "rolle_klage": "beklagter",
                "versicherung": "Test-Versicherung AG",
                "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
            }],
            "positionen": positionen,
        },
        "schaden": schaden or {},
        "reg_agg": reg_agg or {},
        "abrechnungen": abrechnungen or [],
        "personenschaden": {},
    }


def _document_xml(docx_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        return z.read("word/document.xml").decode("utf-8")


class TestKlageServiceDocxVorlageLadbar(unittest.TestCase):
    def test_generiere_klageschrift_liefert_docx_bytes(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        doc_bytes = generiere_klageschrift(akte_daten)
        self.assertTrue(doc_bytes.startswith(b"PK"))
        xml = _document_xml(doc_bytes)
        self.assertIn("<w:document", xml)


class TestKW04EineRechenquelle(unittest.TestCase):
    def test_a_abgewaehlte_position_erscheint_nicht_und_satz_endet_bei_antrag1(self):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=700.0, betrag_original=1000.0, checked=True),
            _position("sv_kosten", "Sachverstaendigenkosten", betrag=250.0, betrag_original=250.0, checked=False),
        ]
        schaden = {"wertminderung": 1000.0, "sv_kosten": 250.0}
        reg_agg = {"wertminderung": {"gesamt_reguliert": 300.0}}
        abrechnungen = [{"gesamt_reguliert": 300.0}]
        akte_daten = _akte_daten(positionen, schaden, reg_agg, abrechnungen)

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertNotIn("Sachverständigenkosten", xml)
        self.assertIn("Merkantile Wertminderung", xml)
        self.assertIn("1.000,00", xml)
        self.assertIn("700,00 €", xml)
        self.assertIn(
            "Die Differenz des geforderten Gesamtbetrages in Höhe von 1.000,00 € "
            "abzgl. der oben gezeigten geleisteten Zahlungen in Höhe von 300,00 € "
            "beträgt 700,00 € und wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )

    def test_b_ungebundener_vorschuss_erscheint_als_zeile_und_satz_bleibt_konsistent(self):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=700.0, betrag_original=1200.0, checked=True),
        ]
        schaden = {"wertminderung": 1200.0}
        reg_agg = {"wertminderung": {"gesamt_reguliert": 200.0}}
        abrechnungen = [{"gesamt_reguliert": 500.0}]
        akte_daten = _akte_daten(positionen, schaden, reg_agg, abrechnungen)

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("Zahlung ohne Positionszuordnung", xml)
        self.assertIn("300,00", xml)
        self.assertIn(
            "Die Differenz des geforderten Gesamtbetrages in Höhe von 1.200,00 € "
            "abzgl. der oben gezeigten geleisteten Zahlungen in Höhe von 500,00 € "
            "beträgt 700,00 € und wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )

    def test_c_betrag_genettet_kleiner_betragoriginal_tabelle_zeigt_100_prozent(self):
        positionen = [
            _position("nutzungsausfall", "Nutzungsausfall", betrag=650.0, betrag_original=900.0, checked=True),
        ]
        schaden = {"nutzungsausfall": 850.0}
        reg_agg = {"nutzungsausfall": {"gesamt_reguliert": 250.0}}
        abrechnungen = [{"gesamt_reguliert": 250.0}]
        akte_daten = _akte_daten(positionen, schaden, reg_agg, abrechnungen)

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("900,00", xml)
        self.assertNotIn("850,00", xml)
        self.assertIn("650,00 €", xml)
        self.assertIn(
            "Die Differenz des geforderten Gesamtbetrages in Höhe von 900,00 € "
            "abzgl. der oben gezeigten geleisteten Zahlungen in Höhe von 250,00 € "
            "beträgt 650,00 € und wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )

    def test_d_nichts_reguliert_vereinfachter_satz(self):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=400.0, betrag_original=400.0, checked=True),
        ]
        schaden = {"wertminderung": 400.0}
        akte_daten = _akte_daten(positionen, schaden, reg_agg={}, abrechnungen=[])

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn(
            "Der Gesamtbetrag in Höhe von 400,00 € wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )
        self.assertNotIn("Die Beklagte hat folgende Zahlungen auf den Schaden geleistet", xml)
        self.assertNotIn("Die Differenz des geforderten Gesamtbetrages", xml)


class TestKW04Finding1ExtrasCheckedFilter(unittest.TestCase):
    def test_e_extra_position_abgewaehlt_erscheint_nicht_und_keine_phantom_zahlungen(self):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=400.0, betrag_original=400.0, checked=True),
            _position("extra_Bergungskosten", "Bergungskosten", betrag=150.0, betrag_original=150.0, checked=False),
        ]
        schaden = {
            "wertminderung": 400.0,
            "wdm_extras_json": json.dumps([
                {"label": "Bergungskosten", "betrag": 150.0, "netto": 126.05},
            ]),
        }
        akte_daten = _akte_daten(positionen, schaden, reg_agg={}, abrechnungen=[])

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertNotIn("Bergungskosten", xml)
        self.assertIn(
            "Der Gesamtbetrag in Höhe von 400,00 € wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )
        self.assertNotIn("Die Beklagte hat folgende Zahlungen auf den Schaden geleistet", xml)
        self.assertNotIn("Die Differenz des geforderten Gesamtbetrages", xml)

    def test_f_extra_position_checked_erscheint_mit_betragoriginal(self):
        positionen = [
            _position("extra_Bergungskosten", "Bergungskosten", betrag=126.05, betrag_original=150.0, checked=True),
        ]
        schaden = {
            "wdm_extras_json": json.dumps([
                {"label": "Bergungskosten", "betrag": 126.05, "netto": 126.05},
            ]),
        }
        reg_agg = {}
        abrechnungen = [{"gesamt_reguliert": 23.95}]
        akte_daten = _akte_daten(positionen, schaden, reg_agg, abrechnungen)

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("Bergungskosten", xml)
        self.assertIn("150,00", xml)
        self.assertIn("126,05 €", xml)
        self.assertIn(
            "Die Differenz des geforderten Gesamtbetrages in Höhe von 150,00 € "
            "abzgl. der oben gezeigten geleisteten Zahlungen in Höhe von 23,95 € "
            "beträgt 126,05 € und wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )


class TestKW39VorsteuerNebenkostenDocx(unittest.TestCase):
    def test_vorsteuer_mandant_sv_kosten_netto_konsistent_mit_antrag1(self):
        positionen = [
            _position("sv_kosten", "Kosten des Sachverständigen (brutto)",
                       betrag=200.0, betrag_original=200.0, checked=True),
        ]
        schaden = {
            "sv_kosten_netto": 200.0, "sv_kosten_ust": 38.0, "sv_kosten": 999.0,
        }
        akte_daten = _akte_daten(positionen, schaden, reg_agg={}, abrechnungen=[], vorsteuer="J")

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("200,00", xml)
        self.assertNotIn("999,00", xml)
        self.assertIn(
            "Der Gesamtbetrag in Höhe von 200,00 € wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )


if __name__ == "__main__":
    unittest.main()
