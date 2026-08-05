"""Tests für services/abschluss_uebersicht.py (Übersichts-Objekt)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.abschluss_uebersicht import (
    _baue_pos_map_mit_verlauf,
    baue_abschluss_uebersicht,
)


def _ab(datum, versicherung, positionen, gesamt_reguliert=None, haftungsquote=100.0):
    if gesamt_reguliert is None:
        gesamt_reguliert = sum(p.get("betrag_reguliert") or 0 for p in positionen)
    return {
        "datum": datum, "versicherung": versicherung,
        "gesamt_reguliert": gesamt_reguliert, "haftungsquote": haftungsquote,
        "positionen": positionen,
    }


class TestPosMapMitVerlauf(unittest.TestCase):

    def test_summiert_und_sammelt_zahlungen_chronologisch(self):
        abrechnungen = [
            _ab("2026-03-10", "HUK", [
                {"position_key": "sv_kosten", "betrag_gefordert": 600.0,
                 "betrag_reguliert": 450.0}]),
            _ab("2026-01-15", "HUK", [
                {"position_key": "sv_kosten", "betrag_gefordert": 600.0,
                 "betrag_reguliert": 100.0}]),
        ]
        pos_map, ra = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertEqual(pos_map["sv_kosten"]["reguliert"], 550.0)
        daten = [z["datum"] for z in pos_map["sv_kosten"]["zahlungen"]]
        self.assertEqual(daten, ["2026-01-15", "2026-03-10"])
        self.assertEqual(pos_map["sv_kosten"]["zahlungen"][0]["betrag"], 100.0)
        self.assertEqual(pos_map["sv_kosten"]["zahlungen"][0]["versicherung"], "HUK")
        self.assertEqual(ra, 0.0)

    def test_key_normalisierung_wdm(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "sonstiges_wdm_3", "betrag_gefordert": 50.0,
             "betrag_reguliert": 50.0}])]
        pos_map, _ = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertIn("extra_wdm_ss3", pos_map)

    def test_ra_gebuehren_werden_gefiltert_und_summiert(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "ra_gebuehren", "betrag_gefordert": 627.13,
             "betrag_reguliert": 627.13},
            {"position_key": "nutzungsausfall", "betrag_gefordert": 300.0,
             "betrag_reguliert": 300.0}])]
        pos_map, ra = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertNotIn("sonstiges", pos_map)
        self.assertNotIn("ra_gebuehren", pos_map)
        self.assertIn("nutzungsausfall", pos_map)
        self.assertEqual(ra, 627.13)

    def test_kuerzung_grund_bezeichnung_vor_freitext(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "mietwagenkosten", "betrag_gefordert": 500.0,
             "betrag_reguliert": 350.0,
             "kuerzungsart_bezeichnung": "Überhöhter Tagessatz",
             "kuerzung_freitext": "wird ignoriert"},
            {"position_key": "standkosten", "betrag_gefordert": 200.0,
             "betrag_reguliert": 120.0,
             "kuerzung_freitext": "nur Freitext"}])]
        pos_map, _ = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertEqual(pos_map["mietwagenkosten"]["kuerzung_grund"],
                         "Überhöhter Tagessatz")
        self.assertEqual(pos_map["standkosten"]["kuerzung_grund"], "nur Freitext")

    def test_none_reguliert_wird_uebersprungen(self):
        abrechnungen = [_ab("2026-02-01", "VHV", [
            {"position_key": "sv_kosten", "betrag_gefordert": 600.0,
             "betrag_reguliert": None}], gesamt_reguliert=0.0)]
        pos_map, _ = _baue_pos_map_mit_verlauf(abrechnungen)
        self.assertNotIn("sv_kosten", pos_map)


def _akte_daten(schaden=None, abrechnungen=None, abschluss_status=None,
                gebuehren_kontext=None, mandant_vorsteuer="N"):
    return {
        "akte": {"aktenzeichen": "42/26", "unfalldatum": "2026-01-10",
                 "unfallort": "Offenbach", "haftungsquote": 100.0},
        "mandant": {"name": "Muster", "vorname": "Max", "anrede": "1",
                    "anschrift": "Weg 1", "plz": "63065", "ort": "Offenbach",
                    "vorsteuer": mandant_vorsteuer},
        "gegner": {"versicherung": "HUK-COBURG"},
        "schaden": schaden or {},
        "abrechnungen": abrechnungen or [],
        "wdm_roh": {},
        "abschluss_status": abschluss_status,
        "gebuehren_kontext": gebuehren_kontext,
    }


class TestBaueAbschlussUebersicht(unittest.TestCase):

    def test_fiktiv_fahrzeug_an_mandant(self):
        daten = _akte_daten(
            schaden={"rep_gutachten_netto": 4000.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "rep_gutachten_netto",
                 "betrag_gefordert": 4000.0, "betrag_reguliert": 4000.0}])])
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "rep_gutachten_netto")
        self.assertEqual(pos["empfaenger"], "mandant")
        self.assertEqual(pos["kategorie"], "fahrzeug")
        self.assertEqual(pos["status"], "voll")
        self.assertEqual(ueb["summen"]["an_mandant"], 4000.0)

    def test_konkret_fahrzeug_an_dritte(self):
        daten = _akte_daten(
            schaden={"rep_rechnung_netto": 3000.0, "rep_rechnung_brutto": 3570.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "rep_rechnung_netto",
                 "betrag_gefordert": 3570.0, "betrag_reguliert": 3570.0}])])
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "rep_rechnung_netto")
        self.assertEqual(pos["empfaenger"], "dritte")
        self.assertEqual(ueb["summen"]["an_dritte"], 3570.0)

    def test_totalschaden_an_mandant_mit_abzug(self):
        daten = _akte_daten(
            schaden={"wiederbeschaffung": 10000.0, "restwert": 2000.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "wiederbeschaffung",
                 "betrag_gefordert": 8000.0, "betrag_reguliert": 8000.0}])])
        ueb = baue_abschluss_uebersicht(daten)
        wbw = next(p for p in ueb["positionen"] if p["key"] == "wiederbeschaffung")
        rst = next(p for p in ueb["positionen"] if p["key"] == "restwert")
        self.assertEqual(wbw["empfaenger"], "mandant")
        self.assertEqual(rst["status"], "abzug")

    def test_kuerzung_liefert_differenz_und_grund(self):
        daten = _akte_daten(
            schaden={"mietwagenkosten": 500.0},
            abrechnungen=[_ab("2026-02-01", "HUK", [
                {"position_key": "mietwagenkosten",
                 "betrag_gefordert": 500.0, "betrag_reguliert": 350.0,
                 "kuerzungsart_bezeichnung": "Überhöhter Tagessatz"}])])
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "mietwagenkosten")
        self.assertEqual(pos["status"], "gekuerzt")
        self.assertEqual(pos["differenz"], 150.0)
        self.assertEqual(pos["kuerzung_grund"], "Überhöhter Tagessatz")
        self.assertEqual(pos["empfaenger"], "dritte")

    def test_offene_position_ohne_zahlung(self):
        daten = _akte_daten(schaden={"nutzungsausfall": 300.0})
        ueb = baue_abschluss_uebersicht(daten)
        pos = next(p for p in ueb["positionen"] if p["key"] == "nutzungsausfall")
        self.assertEqual(pos["status"], "offen")
        self.assertIsNone(pos["gezahlt"])
        self.assertEqual(pos["empfaenger"], "mandant")

    def test_modus_aus_schluss_typ(self):
        daten = _akte_daten()
        self.assertEqual(baue_abschluss_uebersicht(daten)["modus"], "sachstand")
        daten["abschluss_status"] = {"schluss_typ": "offen"}
        self.assertEqual(baue_abschluss_uebersicht(daten)["modus"], "sachstand")
        daten["abschluss_status"] = {"schluss_typ": "endgueltig",
                                     "schluss_text": "Alles erledigt."}
        ueb = baue_abschluss_uebersicht(daten)
        self.assertEqual(ueb["modus"], "abschluss")
        self.assertEqual(ueb["schluss"]["text"], "Alles erledigt.")


if __name__ == "__main__":
    unittest.main()
