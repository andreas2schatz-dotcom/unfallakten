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

from backend.word.klage_service import generiere_klageschrift, berechne_rvg, _beweis


def _position(key, label, betrag, betrag_original=None, checked=True):
    return {
        "key": key,
        "label": label,
        "betrag": betrag,
        "betragOriginal": betrag_original if betrag_original is not None else betrag,
        "checked": checked,
    }


def _akte_daten(positionen, schaden=None, reg_agg=None, abrechnungen=None, vorsteuer="N",
                 mit_schmerzensgeld=False, schmerzensgeld_mindest=0.0):
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
            "mit_schmerzensgeld": mit_schmerzensgeld,
            "schmerzensgeld_mindest": schmerzensgeld_mindest,
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


class TestKW07SchmerzensgeldNichtDoppelt(unittest.TestCase):
    def test_mit_sg_toggle_aktiv_position_fliegt_aus_antrag1_tabelle_und_gegenstandswert(self):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=400.0, betrag_original=400.0, checked=True),
            _position("schmerzensgeld", "Schmerzensgeld", betrag=2000.0, betrag_original=2000.0, checked=True),
        ]
        schaden = {"wertminderung": 400.0, "schmerzensgeld": 2000.0}
        akte_daten = _akte_daten(
            positionen, schaden, reg_agg={}, abrechnungen=[],
            mit_schmerzensgeld=True, schmerzensgeld_mindest=2000.0,
        )

        xml = _document_xml(generiere_klageschrift(akte_daten))

        # Gegenstandswert = klagebetrag_ohne_SG (400) + schmerzensgeld_mindest (2000)
        self.assertIn("2.400,00", xml)
        # Antrag 1 nur mit dem Sachschaden, ohne die bezifferte SG-Position
        self.assertIn(
            "Die Beklagte wird verurteilt, an den Kläger 400,00 € "
            "nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz "
            "seit Rechtshängigkeit zu zahlen.",
            xml,
        )
        # Tabelle/Differenz-Satz: schaden_gesamt == klagebetrag == 400 (SG raus)
        self.assertIn(
            "Der Gesamtbetrag in Höhe von 400,00 € wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )
        # unbezifferter SG-Antrag bleibt vorhanden
        self.assertIn(
            "wobei die Höhe nicht weniger als 2.000,00 € betragen sollte",
            xml,
        )

    def test_ohne_sg_toggle_position_bleibt_beziffert_kein_unbezifferter_antrag(self):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=400.0, betrag_original=400.0, checked=True),
            _position("schmerzensgeld", "Schmerzensgeld", betrag=2000.0, betrag_original=2000.0, checked=True),
        ]
        schaden = {"wertminderung": 400.0, "schmerzensgeld": 2000.0}
        akte_daten = _akte_daten(
            positionen, schaden, reg_agg={}, abrechnungen=[],
            mit_schmerzensgeld=False, schmerzensgeld_mindest=0.0,
        )

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("2.400,00", xml)
        self.assertIn(
            "Die Beklagte wird verurteilt, an den Kläger 2.400,00 € "
            "nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz "
            "seit Rechtshängigkeit zu zahlen.",
            xml,
        )
        self.assertIn(
            "Der Gesamtbetrag in Höhe von 2.400,00 € wird mit dem Klageantrag zu 1 geltend gemacht.",
            xml,
        )
        self.assertIn("Schmerzensgeld", xml)
        self.assertNotIn("nicht weniger als", xml)


class TestKW05EinleitungEigentumTyp(unittest.TestCase):
    def test_a_geleast_maennlich_halter_und_besitzer_kein_eigentuemer_satz_leasing_block_vorhanden(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"]["anrede"] = "1"
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = "geleast"
        akte_daten["unfalldetails"]["_wdm_mandant_kz"] = "OF-XY 123"

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("Halter und unmittelbarer Besitzer", xml)
        self.assertNotIn("ist Eigentümer des", xml)
        self.assertIn("Leasinggeberin", xml)

    def test_b_eigentum_genau_ein_eigentumssatz(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"]["anrede"] = "1"
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = "eigentum"
        akte_daten["unfalldetails"]["_wdm_mandant_kz"] = "OF-XY 123"

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertEqual(xml.count("ist Eigentümer des"), 1)
        self.assertNotIn("§ 1006", xml)

    def test_e_eigentum_mandant_ist_fahrer_paragraph1006_erhalten_kein_doppelter_satz(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"]["anrede"] = "1"
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = "eigentum"
        akte_daten["unfalldetails"]["_wdm_mandant_kz"] = "OF-XY 123"
        akte_daten["unfalldetails"]["mandant_ist_fahrer"] = True

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("§ 1006", xml)
        self.assertEqual(xml.count("ist Eigentümer des"), 1)

    def test_f_eigentum_mit_override_zeigt_override_text(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"]["anrede"] = "1"
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = "eigentum"
        akte_daten["unfalldetails"]["_wdm_mandant_kz"] = "OF-XY 123"
        akte_daten["unfalldetails"]["aktivlegitimation_text_override"] = (
            "Individueller Aktivlegitimations-Override-Text."
        )

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("Individueller Aktivlegitimations-Override-Text.", xml)

    def test_c_finanziert_maennlich_halter_und_besitzer_bank_block_vorhanden(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"]["anrede"] = "1"
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = "finanziert"
        akte_daten["unfalldetails"]["_wdm_mandant_kz"] = "OF-XY 123"

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("Halter und unmittelbarer Besitzer", xml)
        self.assertNotIn("ist Eigentümer des", xml)
        self.assertIn("finanzierenden Bank", xml)

    def test_d_geleast_weiblich_halterin_und_besitzerin(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"]["anrede"] = "2"
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = "geleast"
        akte_daten["unfalldetails"]["_wdm_mandant_kz"] = "OF-XY 123"

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("Halterin und unmittelbare Besitzerin", xml)
        self.assertNotIn("ist Eigentümerin des", xml)


class TestKW03HaftungsquoteFallAB(unittest.TestCase):
    def _akte_daten_hq(self, hq, hq_typ, mit_sg=False, sg_mind=0.0):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=7000.0, betrag_original=10000.0, checked=True),
        ]
        schaden = {"wertminderung": 10000.0}
        akte_daten = _akte_daten(
            positionen, schaden,
            mit_schmerzensgeld=mit_sg, schmerzensgeld_mindest=sg_mind,
        )
        akte_daten["klage_config"]["haftungsquote"] = hq
        akte_daten["klage_config"]["haftungsquote_typ"] = hq_typ
        return akte_daten

    def test_a_fall_b_eigene_quote_antrag1_4500_tabelle_bleibt_10000(self):
        xml = _document_xml(generiere_klageschrift(self._akte_daten_hq(75, "eigen")))

        self.assertIn("4.500,00 €", xml)
        self.assertIn("10.000,00", xml)
        self.assertIn(
            "Von dem Gesamtschaden in Höhe von 10.000,00 € sind unter Berücksichtigung "
            "der Mithaftungsquote von 25 % 75 %, mithin 7.500,00 €, ersatzfähig. "
            "Abzüglich der geleisteten Zahlungen in Höhe von 3.000,00 € "
            "verbleiben 4.500,00 €, die mit dem Klageantrag zu 1 geltend gemacht werden.",
            xml,
        )

    def test_b_fall_b_mit_sg_gegenstandswert_5500_sgmind_unquotiert(self):
        xml = _document_xml(generiere_klageschrift(
            self._akte_daten_hq(75, "eigen", mit_sg=True, sg_mind=1000.0)
        ))

        self.assertIn("5.500,00", xml)

    def test_c_fall_a_gegnerische_quote_antrag1_7000_kein_gekuerzt_bestreiten_satz(self):
        xml = _document_xml(generiere_klageschrift(self._akte_daten_hq(75, "gegnerisch")))

        self.assertIn("7.000,00 €", xml)
        self.assertNotIn("entsprechend gekürzt", xml)
        self.assertIn(
            "Die Beklagtenseite geht von einer Mithaftungsquote von 25 % auf Klägerseite aus. "
            "Dies wird bestritten; die Beklagtenseite haftet in vollem Umfang. "
            "Die Klageforderung ist ungekürzt geltend gemacht.",
            xml,
        )

    def test_d_fall_b_auto_rw_text_enthaelt_wahren_gekuerzt_satz(self):
        xml = _document_xml(generiere_klageschrift(self._akte_daten_hq(75, "eigen")))

        self.assertIn(
            "Der Kläger lässt sich eine Mithaftungsquote von 25 % anrechnen. "
            "Die Klageforderung ist entsprechend gekürzt.",
            xml,
        )

    def test_e_hq_100_keinerlei_quote_text(self):
        xml = _document_xml(generiere_klageschrift(self._akte_daten_hq(100, "eigen")))

        self.assertIn("10.000,00", xml)
        self.assertIn("7.000,00 €", xml)
        self.assertNotIn("entsprechend gekürzt", xml)
        self.assertNotIn("Mithaftungsquote", xml)
        self.assertNotIn("Von dem Gesamtschaden", xml)

    def test_f_prozent_dezimal_formatierung_ohne_int_truncation(self):
        akte_daten = self._akte_daten_hq(66.67, "eigen")
        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("33,33 % 66,67 %", xml)

    def test_g_klagebetrag_max_0_klammer_bei_uebersteigenden_zahlungen(self):
        # gesamt_voll=10000, betrag=100 -> zahlungen=9900; hq=20 -> ersatzfaehig=2000.
        # Ohne max(0, ...)-Klammer waere klagebetrag 2000-9900 = -7900.
        # KW-34: zahlungen (9900) > ersatzfaehig (2000) -> Klemm-Satz nennt die echte
        # Zahlungssumme (9.900,00) statt der schoengerechneten Differenz (2.000,00).
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=100.0, betrag_original=10000.0, checked=True),
        ]
        schaden = {"wertminderung": 10000.0}
        akte_daten = _akte_daten(positionen, schaden)
        akte_daten["klage_config"]["haftungsquote"] = 20
        akte_daten["klage_config"]["haftungsquote_typ"] = "eigen"

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn(
            "Von dem Gesamtschaden in Höhe von 10.000,00 € sind unter Berücksichtigung "
            "der Mithaftungsquote von 80 % 20 %, mithin 2.000,00 €, ersatzfähig. "
            "Hierauf wurden bereits Zahlungen in Höhe von 9.900,00 € geleistet; "
            "der ersatzfähige Betrag ist damit vollständig ausgeglichen.",
            xml,
        )

    def test_h_ersatzfaehig_basis_ist_schaden_gesamt_nicht_fallb_gesamt_voll(self):
        # sv_kosten: cfg-betragOriginal (595, "brutto" vom Wizard erfasst) weicht
        # von der Tabelle ab, die bei vorsteuerabzugsberechtigtem Mandanten nur
        # den Nettobetrag (sv_kosten_netto=500) zeigt (_netto_oder_brutto, KW-39).
        # schaden_gesamt (Tabelle) != fallb_gesamt_voll (cfg-Summe): 10.500 != 10.595.
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=7000.0, betrag_original=10000.0, checked=True),
            _position("sv_kosten", "Sachverständigenkosten", betrag=595.0, betrag_original=595.0, checked=True),
        ]
        schaden = {"wertminderung": 10000.0, "sv_kosten_netto": 500.0, "sv_kosten_ust": 0.0}
        akte_daten = _akte_daten(positionen, schaden, vorsteuer="J")
        akte_daten["klage_config"]["haftungsquote"] = 75
        akte_daten["klage_config"]["haftungsquote_typ"] = "eigen"

        xml = _document_xml(generiere_klageschrift(akte_daten))

        # schaden_gesamt (Tabelle) = 10.500,00; fallb_gesamt_voll (cfg) = 10.595,00
        self.assertIn("10.500,00", xml)
        self.assertIn(
            "Von dem Gesamtschaden in Höhe von 10.500,00 € sind unter Berücksichtigung "
            "der Mithaftungsquote von 25 % 75 %, mithin 7.875,00 €, ersatzfähig. "
            "Abzüglich der geleisteten Zahlungen in Höhe von 2.928,75 € "
            "verbleiben 4.946,25 €, die mit dem Klageantrag zu 1 geltend gemacht werden.",
            xml,
        )

    def test_i_hq_cfg_nicht_numerisch_faellt_auf_details_akte_zurueck(self):
        positionen = [
            _position("wertminderung", "Wertminderung", betrag=7000.0, betrag_original=10000.0, checked=True),
        ]
        schaden = {"wertminderung": 10000.0}
        akte_daten = _akte_daten(positionen, schaden)
        akte_daten["klage_config"]["haftungsquote"] = ""
        akte_daten["klage_config"]["haftungsquote_typ"] = "eigen"
        akte_daten["unfalldetails"]["haftungsquote"] = 100

        xml = _document_xml(generiere_klageschrift(akte_daten))

        self.assertIn("7.000,00 €", xml)
        self.assertNotIn("Mithaftungsquote", xml)


class TestKW15KW16RubrumGenus(unittest.TestCase):
    """KW-15: Rubrum-Rolle genus-korrekt; KW-16: Vertreter-Grammatik."""

    def _mit_beklagten(self, beklagte):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["klage_config"]["beklagte"] = beklagte
        return _document_xml(generiere_klageschrift(akte_daten))

    def test_kw15_maennlicher_beklagter_rubrum(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
            "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach",
        }])
        self.assertIn("– Beklagter –", xml)
        self.assertNotIn("– Beklagte –", xml)

    def test_kw15_versicherung_bleibt_beklagte(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
        }])
        self.assertIn("– Beklagte –", xml)

    def test_kw15_gemischt_nummeriert(self):
        xml = self._mit_beklagten([
            {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
             "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"},
            {"rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
             "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach"},
        ])
        self.assertIn("– Beklagte zu 1) –", xml)
        self.assertIn("– Beklagter zu 2) –", xml)

    def test_kw16_geschaeftsfuehrerin_artikel_und_anrede(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "firma": "Muster GmbH",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
            "vertreter_name": "Erika Musterfrau", "vertreter_funktion": "Geschäftsführerin",
        }])
        self.assertIn("vertreten durch die Geschäftsführerin Frau Erika Musterfrau", xml)
        self.assertNotIn("den Geschäftsführerin", xml)

    def test_kw16_leere_funktion_keine_geratene_anrede(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "firma": "Muster GmbH",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
            "vertreter_name": "Erika Musterfrau", "vertreter_funktion": "",
        }])
        self.assertIn("vertreten durch den Geschäftsführer Erika Musterfrau", xml)
        self.assertNotIn("Herrn Erika Musterfrau", xml)


class TestKW06Gesamtschuldner(unittest.TestCase):
    """KW-06: Mehrere Beklagte -> Gesamtschuldner-Anträge + Einleitung je Beklagtem."""

    VERS = {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"}
    MANN = {"rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
            "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach"}

    def _xml(self, beklagte, **kwargs):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)], **kwargs)
        akte_daten["klage_config"]["beklagte"] = beklagte
        akte_daten["klage_config"]["mit_feststellung_sach"] = True
        return _document_xml(generiere_klageschrift(akte_daten))

    def test_zwei_beklagte_gesamtschuldner_antrag1(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn(
            "Die Beklagten werden als Gesamtschuldner verurteilt, an den Kläger 400,00 € "
            "nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz "
            "seit Rechtshängigkeit zu zahlen.", xml)
        self.assertNotIn("Die Beklagte wird verurteilt", xml)

    def test_zwei_beklagte_feststellung_plural(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn("dass die Beklagten als Gesamtschuldner verpflichtet sind", xml)

    def test_zwei_beklagte_kosten_und_vk(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn("Die Beklagten tragen die Kosten des Rechtsstreits.", xml)
        self.assertIn("die Beklagten ebenfalls haften", xml)

    def test_zwei_beklagte_einleitung_je_beklagtem(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn("Die Beklagte zu 1) ist die Haftpflichtversicherung des "
                      "unfallverursachenden Fahrzeugs", xml)
        self.assertIn("Der Beklagte zu 2) war zum Unfallzeitpunkt der Fahrer des "
                      "unfallverursachenden Fahrzeugs.", xml)

    def test_ein_maennlicher_beklagter_singular_maskulin(self):
        xml = self._xml([self.MANN])
        self.assertIn("Der Beklagte wird verurteilt, an den Kläger 400,00 €", xml)
        self.assertIn("Der Beklagte trägt die Kosten des Rechtsstreits.", xml)

    def test_halter_beklagter_einleitung(self):
        halter = dict(self.MANN, ist_halter=1)
        xml = self._xml([self.VERS, halter])
        self.assertIn("Der Beklagte zu 2) ist der Halter des unfallverursachenden "
                      "Fahrzeugs.", xml)

    def test_regression_eine_versicherung_unveraendert(self):
        xml = self._xml([self.VERS])
        self.assertIn("Die Beklagte wird verurteilt, an den Kläger 400,00 €", xml)
        self.assertIn("Die Beklagte ist die Haftpflichtversicherung des "
                      "unfallverursachenden Fahrzeugs.", xml)

    def test_firmen_halter_wird_nicht_als_versicherung_bezeichnet(self):
        halter_gmbh = {"rolle_klage": "beklagter", "firma": "Spedition Krause GmbH",
                       "ist_halter": 1, "anschrift": "Weg 9", "plz": "63065", "ort": "Offenbach"}
        xml = self._xml([self.VERS, halter_gmbh])
        self.assertIn("Die Beklagte zu 2) ist die Halterin des unfallverursachenden "
                      "Fahrzeugs.", xml)
        self.assertNotIn("Die Beklagte zu 2) ist die Haftpflichtversicherung", xml)


class TestKW17MehrereKlaeger(unittest.TestCase):
    """KW-17: Numerus bei mehreren Klaegern + Vorsteuer."""

    K1 = {"id": 1, "rolle_klage": "klaeger", "vorname": "Max", "name": "Mustermann",
          "anrede": "1", "anschrift": "Musterstr. 1", "plz": "63067", "ort": "Offenbach"}
    K2 = {"id": 2, "rolle_klage": "klaeger", "vorname": "Eva", "name": "Mustermann",
          "anrede": "2", "anschrift": "Musterstr. 1", "plz": "63067", "ort": "Offenbach"}

    def _xml(self, vorsteuer="N", mit_sg=False, sg_mind=0.0):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)],
                                 vorsteuer=vorsteuer,
                                 mit_schmerzensgeld=mit_sg,
                                 schmerzensgeld_mindest=sg_mind)
        akte_daten["klage_config"]["beklagte"] = [
            self.K1, self.K2,
            {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
             "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"},
        ]
        return _document_xml(generiere_klageschrift(akte_daten))

    def test_einleitung_plural_verb(self):
        xml = self._xml()
        self.assertIn("Die Kläger machen als nicht vorsteuerabzugsberechtigte "
                      "Geschädigte Schadensersatzforderungen", xml)
        self.assertNotIn("Die Kläger macht", xml)

    def test_eigentuemer_plural(self):
        xml = self._xml()
        self.assertIn("Die Kläger sind Eigentümer", xml)
        self.assertNotIn("Die Kläger ist", xml)

    def test_vorsteuer_bei_mehreren_klaegern_beruecksichtigt(self):
        xml = self._xml(vorsteuer="J")
        self.assertIn("als vorsteuerabzugsberechtigte Geschädigte", xml)
        self.assertNotIn("als nicht vorsteuerabzugsberechtigte Geschädigte", xml)

    def test_sg_plural_verb(self):
        xml = self._xml(mit_sg=True, sg_mind=1000.0)
        self.assertIn("Die Kläger haben durch den Unfall Verletzungen erlitten", xml)

    def test_regression_intro_singular_ohne_unfalldatum_unveraendert(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Der Kläger macht Schadensersatzforderungen aus einem Verkehrsunfall", xml)
        self.assertNotIn("Der Kläger macht als", xml)

    def test_feststellung_dativ_plural(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["klage_config"]["beklagte"] = [
            self.K1, self.K2,
            {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
             "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"},
        ]
        akte_daten["klage_config"]["mit_feststellung_sach"] = True
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("den Klägern sämtliche", xml)


class TestKW18KlaegerFallback(unittest.TestCase):
    """KW-18: Rubrum ohne Klaeger -> Mandant-Fallback bzw. harte Sperre."""

    def test_fallback_auf_mandant(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["klage_config"]["beklagte"] = [{
            "rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
        }]
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Max Mustermann", xml)
        self.assertIn("– Kläger –", xml)

    def test_harte_sperre_ohne_mandant(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"] = {}
        akte_daten["klage_config"]["beklagte"] = [{
            "rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
        }]
        with self.assertRaises(ValueError):
            generiere_klageschrift(akte_daten)


class TestKW09VerzugsdatumFormat(unittest.TestCase):
    def _akte_mit_verzug(self, verzugsdatum):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        akte_daten["klage_config"]["verzugsdatum"] = verzugsdatum
        return akte_daten

    def test_iso_datum_erscheint_deutsch_in_antrag_und_verzugsabschnitt(self):
        # S4-M5: ohne verzug_schreiben_datum gibt es keinen BEWEIS-Satz mehr
        # (kein Fallback aufs Eintrittsdatum) - ISO-Formatierung des Schreibdatums
        # ist separat in TestKW10SchreibdatumGetrennt abgedeckt.
        xml = _document_xml(generiere_klageschrift(self._akte_mit_verzug("2026-05-04")))
        self.assertNotIn("2026-05-04", xml)
        self.assertIn("seit dem 04.05.2026 zu zahlen", xml)
        self.assertIn("am 04.05.2026 eingetreten", xml)
        self.assertNotIn("Schreiben vom", xml)

    def test_deutsches_datum_bleibt_unveraendert(self):
        xml = _document_xml(generiere_klageschrift(self._akte_mit_verzug("04.05.2026")))
        self.assertIn("seit dem 04.05.2026 zu zahlen", xml)

    def test_ohne_verzugsdatum_bleibt_rechtshaengigkeit(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("seit Rechtshängigkeit zu zahlen", xml)
        self.assertIn("Verzug ist mit Rechtshängigkeit eingetreten.", xml)


class TestKW10SchreibdatumGetrennt(unittest.TestCase):
    def test_beweis_nutzt_schreibdatum_eintritt_bleibt_verzugsdatum(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        akte_daten["klage_config"]["verzugsdatum"] = "2026-05-19"
        akte_daten["klage_config"]["verzug_schreiben_datum"] = "2026-05-04"
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("am 19.05.2026 eingetreten", xml)
        self.assertIn("Schreiben vom 04.05.2026", xml)
        self.assertNotIn("Schreiben vom 19.05.2026", xml)

    def test_ohne_schreiben_datum_kein_beweis_mehr(self):
        # S4-M5: Backend glich sich ans Frontend (buildVerzugAutoText) an - kein
        # BEWEIS-Satz mehr, wenn verzug_schreiben_datum nicht explizit gesetzt ist
        # (vorher Fallback aufs Eintrittsdatum, divergierte von der Wizard-Vorschau).
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["klage_config"]["zinsen_ab"] = "verzug"
        akte_daten["klage_config"]["verzugsdatum"] = "2026-05-19"
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("am 19.05.2026 eingetreten", xml)
        self.assertNotIn("Schreiben vom", xml)


class TestKW35RvgAnlagedatumFallback(unittest.TestCase):
    def test_fallback_nutzt_rvg_anlagedatum_statt_erstellt_am(self):
        # Akte 2024 angelegt (alter RVG-Tarif), aber erst 2026 in SQLite importiert.
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["akte"]["erstellt_am"] = "2026-01-01"
        akte_daten["akte"]["rvg_anlagedatum"] = "2024-06-01"
        # kein cfg["rvg"], kein cfg["rvg_ausserg"] -> berechne_rvg-Fallback greift
        xml = _document_xml(generiere_klageschrift(akte_daten))
        erwartet_alt  = berechne_rvg(700.0, erstellt_am="2024-06-01")["gesamt"]
        erwartet_neu  = berechne_rvg(700.0, erstellt_am="2026-01-01")["gesamt"]
        self.assertNotEqual(erwartet_alt, erwartet_neu,
                            "Testaufbau: Tarife 2021/2025 muessen sich beim gewaehlten Streitwert unterscheiden")
        alt_str = f"{erwartet_alt:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        neu_str = f"{erwartet_neu:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.assertIn(alt_str, xml)
        self.assertNotIn(neu_str, xml)


class TestKw34RvgNull(unittest.TestCase):
    def test_kein_rvg_antrag_bei_null(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["klage_config"]["rvg_ausserg"] = {"gesamt": 150.0, "faktor": 1.3, "streitwert": 1000.0}
        akte["klage_config"]["rvg_bereits_gezahlt"] = 500.0   # > gesamt → Betrag klemmt auf 0
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertNotIn("weitere 0,00", xml)
        self.assertNotIn("Vorgerichtliche Rechtsanwaltsgebühren", xml)

    def test_fall_b_zahlungen_ueber_quotiertem_anspruch(self):
        # "fahrzeugschaden" ist ein Aggregat-Key, der in schaden_raw NICHT direkt aus
        # betragOriginal gespeist wird (nur untergeordnete DB-Keys wie reparaturkosten) -
        # damit waere schaden_gesamt=0 und der Test träfe nichts real (Review-Fund).
        # "wertminderung" ist ein _EINFACHE_POS_KEYS-Key (klage_service.py ~:1600-1609):
        # schaden_raw["wertminderung"] wird direkt aus betragOriginal gesetzt, schaden_gesamt
        # damit real 1000,00 € -> ersatzfaehig real 500,00 €.
        pos = [_position("wertminderung", "Wertminderung", betrag=0.0, betrag_original=1000.0)]
        schaden = {"wertminderung": 1000.0}
        akte = _akte_daten(pos, schaden)
        akte["klage_config"]["haftungsquote"] = 50
        akte["klage_config"]["haftungsquote_typ"] = "eigen"
        # Zahlungen 1.000 € > quotierter Anspruch 500 € (1000 * 50 %) → klagebetrag klemmt auf 0
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("mithin 500,00", xml)                     # realer ersatzfähiger Betrag
        self.assertIn("Zahlungen in Höhe von 1.000,00", xml)     # echte Zahlungssumme genannt
        self.assertIn("vollständig ausgeglichen", xml)
        self.assertNotIn("Zahlungen in Höhe von 500,00", xml)    # nicht mehr die geschönte Differenz


class TestKW12AnlagenNummern(unittest.TestCase):
    def _mit_aktivleg(self, akte_daten, typ="finanziert", freigabe="freigabe"):
        akte_daten["unfalldetails"]["aktivlegitimation_typ"] = typ
        akte_daten["unfalldetails"]["aktivlegitimation_freigabe"] = freigabe
        akte_daten["unfalldetails"]["aktivlegitimation_datum"] = "01.03.2026"
        return akte_daten

    def test_eigentum_gutachten_k1_sg_k2(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)],
                                  mit_schmerzensgeld=True, schmerzensgeld_mindest=1000.0)
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Schadengutachten (Anlage K 1)", xml)
        self.assertIn("(Anlage K 2)", xml)          # Atteste
        self.assertNotIn("Anlage K 3", xml)

    def test_finanziert_freigabe_k1_gutachten_k2_sg_k3(self):
        akte_daten = self._mit_aktivleg(
            _akte_daten([_position("wertminderung", "Wertminderung", 700.0)],
                        mit_schmerzensgeld=True, schmerzensgeld_mindest=1000.0))
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Freigabeerklärung vom 01.03.2026, Anlage K 1", xml)
        self.assertIn("Schadengutachten (Anlage K 2)", xml)
        self.assertIn("(Anlage K 3)", xml)          # Atteste
        self.assertNotIn("Anlage K1", xml)          # alte Schreibweise weg

    def test_sachverhalt_override_mit_k1_verschiebt_gutachten_auf_k2(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["unfalldetails"]["sachverhalt_override"] = (
            "Das Fahrzeug ist finanziert.\n\nBEWEIS:\tFreigabeerklärung vom 01.03.2026, Anlage K 1\n")
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Schadengutachten (Anlage K 2)", xml)


class TestKW13RvgOverrideEntfernt(unittest.TestCase):
    def test_rvg_override_wird_ignoriert(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 700.0)])
        akte_daten["akte"]["rvg_anlagedatum"] = "2026-01-01"
        akte_daten["klage_config"]["rvg_override"] = 9999.99
        # Bewusst KEIN rvg_ausserg["gesamt"]: Tabelle und RVG-Antrag fallen auf
        # berechne_rvg zurueck - nur so wuerde ein wieder eingefuehrtes
        # rvg_override-Lesen (rvg["gesamt"] = float(rvg_override)) den Test rot machen.
        xml = _document_xml(generiere_klageschrift(akte_daten))
        erwartet = berechne_rvg(700.0, erstellt_am="2026-01-01")["gesamt"]
        erwartet_str = f"{erwartet:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.assertNotIn("9.999,99", xml)
        self.assertIn(erwartet_str, xml)


class TestKw33SgBeweis(unittest.TestCase):
    def test_sg_beweis_als_beweis_absatz_formatiert(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)],
                            mit_schmerzensgeld=True, schmerzensgeld_mindest=2000.0)
        xml = _document_xml(generiere_klageschrift(akte))
        # SG-Beweis muss ueber den _beweis()-Helper gerendert sein (fettes "BEWEIS:"
        # + <w:tab/> + Inhalt als eigener Run), nicht als einzelner _p()-Fliesstext-Run
        # mit "BEWEIS: " als Textpraefix.
        erwartet = _beweis("Ärztliche Atteste und Befundberichte (Anlage K 2)")
        self.assertIn(erwartet, xml)
        self.assertNotIn("BEWEIS: Ärztliche Atteste", xml)


class TestKw37FaktorKomma(unittest.TestCase):
    def test_rvg_faktor_mit_komma(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("Nr. 2300 VV RVG (1,3):", xml)
        self.assertNotIn("Nr. 2300 VV RVG (1.3):", xml)


class TestKw30LeereFelder(unittest.TestCase):
    """KW-30: Bedingte Ort-/Datum-Segmente statt fixer 'vom  '/'in  '-Fragmente."""

    def _akte_ohne_ort(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        # _akte_daten() setzt kein unfalldatum -> hier explizit setzen, damit dieser
        # Test wirklich nur den Ort-Fall (nicht zusaetzlich den Datum-Fall) prueft.
        akte["akte"]["unfalldatum"] = "2026-03-10"
        akte["akte"]["unfallort"] = ""
        return akte

    def test_einleitung_ohne_ort_kein_in_fragment(self):
        xml = _document_xml(generiere_klageschrift(self._akte_ohne_ort()))
        self.assertNotIn("in  geltend", xml)
        self.assertIn("Verkehrsunfall vom", xml)   # Datum-Segment bleibt

    def test_einleitung_ohne_ort_und_datum(self):
        akte = self._akte_ohne_ort()
        akte["akte"]["unfalldatum"] = ""
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("aus einem Verkehrsunfall geltend", xml)

    def test_feststellung_ohne_datum_kein_vom_fragment(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["akte"]["unfalldatum"] = ""
        akte["klage_config"]["mit_feststellung_sach"] = True
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertNotIn("Unfallereignis vom  noch", xml)
        self.assertIn("aus dem Unfallereignis noch entstehen", xml)

    def test_einleitung_mit_ort_und_datum_bytegleich(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["akte"]["unfalldatum"] = "2026-03-10"
        akte["akte"]["unfallort"] = "Offenbach"
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("aus einem Verkehrsunfall vom 10.03.2026 in Offenbach geltend.", xml)


class TestKw31OverrideAbsaetze(unittest.TestCase):
    def _xml_fuer(self, override):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["unfalldetails"]["sachverhalt_override"] = override
        return _document_xml(generiere_klageschrift(akte))

    def test_beweis_nach_einfachem_umbruch_wird_beweis_absatz(self):
        xml = self._xml_fuer("Der Kläger ist Eigentümer.\nBEWEIS: Zeugnis des Herrn Meier")
        self.assertIn('BEWEIS:</w:t>', xml)                      # _beweis()-Format
        self.assertNotIn("Eigentümer. BEWEIS:", xml)             # nicht als Fließtext verkettet

    def test_beweis_tab_variante_nach_einfachem_umbruch_wird_beweis_absatz(self):
        xml = self._xml_fuer("Der Kläger ist Eigentümer.\nBEWEIS:\tZeugnis des Herrn Meier")
        self.assertIn(_beweis("Zeugnis des Herrn Meier"), xml)
        self.assertNotIn("Eigentümer. BEWEIS:", xml)

    def test_bare_beweis_ohne_inhalt_wird_leerer_beweis_absatz(self):
        xml = self._xml_fuer("Vor dem Beweis.\nBEWEIS:\nNach dem Beweis.")
        self.assertIn(_beweis(""), xml)
        self.assertNotIn("Vor dem Beweis. BEWEIS:", xml)
        self.assertNotIn("BEWEIS: Nach dem Beweis.", xml)
        self.assertIn(">Nach dem Beweis.<", xml)

    def test_leerzeile_erzeugt_zwei_absaetze(self):
        xml = self._xml_fuer("Absatz eins.\n\nAbsatz zwei.")
        self.assertIn(">Absatz eins.<", xml)
        self.assertIn(">Absatz zwei.<", xml)
        self.assertNotIn("Absatz eins. Absatz zwei.", xml)

    def test_einfacher_umbruch_bleibt_ein_absatz(self):
        xml = self._xml_fuer("Zeile eins\nZeile zwei")
        self.assertIn("Zeile eins Zeile zwei", xml)


class TestKw32Abschnittszaehler(unittest.TestCase):
    def test_verzug_hat_nummer_und_ueberschrift_ohne_sg(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["klage_config"]["verzugsdatum"] = "2026-05-04"
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("5.) Verzug", xml)
        self.assertIn("6.) Vorgerichtliche Rechtsanwaltsgebühren", xml)

    def test_nummern_mit_sg(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)],
                           mit_schmerzensgeld=True, schmerzensgeld_mindest=2000.0)
        akte["klage_config"]["verzugsdatum"] = "2026-05-04"
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("5.) Schmerzensgeld", xml)
        self.assertIn("6.) Verzug", xml)
        self.assertIn("7.) Vorgerichtliche Rechtsanwaltsgebühren", xml)

    def test_verzug_ohne_verzugsdatum_bleibt_nummeriert(self):
        # Verzug-Block rendert auch ohne verzugsdatum/Override den Default-Satz
        # ("Verzug ist mit Rechtshaengigkeit eingetreten.") - der Block ist also
        # nie wirklich leer; die Ueberschrift darf hier nicht uebersprungen werden.
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("5.) Verzug", xml)
        self.assertIn("Verzug ist mit Rechtshängigkeit eingetreten.", xml)
        self.assertIn("6.) Vorgerichtliche Rechtsanwaltsgebühren", xml)

    def test_sachverhalt_bis_rechtliche_wuerdigung_unveraendert_nummeriert(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("1.) Sachverhalt", xml)
        self.assertIn("2.) Unfallhergang", xml)
        self.assertIn("3.) Unfallschaden", xml)
        self.assertIn("4.) Rechtliche Würdigung", xml)


if __name__ == "__main__":
    unittest.main()
