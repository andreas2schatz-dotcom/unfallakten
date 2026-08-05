"""Tests für services/abschluss_uebersicht.py (Übersichts-Objekt)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.abschluss_uebersicht import _baue_pos_map_mit_verlauf


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


if __name__ == "__main__":
    unittest.main()
