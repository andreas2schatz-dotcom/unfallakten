"""PRD-36d – Unit-Tests für beteiligter_as_dict in backend/models/beteiligte.py"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.models.beteiligte import beteiligter_as_dict


class _FakeBeteiligter:
    def __init__(self):
        self.id = 1
        self.akte_id = 10
        self.rolle = "mandant"
        self.name = "Mustermann"
        self.vorname = "Max"
        self.firma = None
        self.anschrift = "Musterstraße 1"
        self.plz = "12345"
        self.ort = "Musterstadt"
        self.telefon = None
        self.email = None
        self.kfz_kennzeichen = "OF-XX 1"
        self.kfz_typ = None
        self.versicherung = None
        self.vers_nr = None
        self.schaden_nr = None
        self.iban = None
        self.notizen = None
        self.anrede = "1"
        self.vorsteuer = "N"
        self.vertreter_name = None
        self.vertreter_funktion = None

    @property
    def vollstaendiger_name(self):
        if self.vorname:
            return f"{self.vorname} {self.name}"
        return self.name


class TestBeteiligterAsDict(unittest.TestCase):

    def test_basisfelder(self):
        d = beteiligter_as_dict(_FakeBeteiligter())
        self.assertEqual(d["id"], 1)
        self.assertEqual(d["akte_id"], 10)
        self.assertEqual(d["rolle"], "mandant")
        self.assertEqual(d["name"], "Mustermann")
        self.assertEqual(d["kfz_kennzeichen"], "OF-XX 1")

    def test_vollstaendiger_name(self):
        d = beteiligter_as_dict(_FakeBeteiligter())
        self.assertEqual(d["vollstaendiger_name"], "Max Mustermann")

    def test_anrede_und_vorsteuer(self):
        d = beteiligter_as_dict(_FakeBeteiligter())
        self.assertEqual(d["anrede"], "1")
        self.assertEqual(d["vorsteuer"], "N")

    def test_getattr_felder_mit_default(self):
        b = _FakeBeteiligter()
        d = beteiligter_as_dict(b)
        self.assertEqual(d["kuerzel"], "")
        self.assertEqual(d["briefanrede"], "")
        self.assertEqual(d["betreff1"], "")
        self.assertEqual(d["betreff2"], "")
        self.assertEqual(d["betreff3"], "")
        self.assertEqual(d["ist_halter"], 0)
        self.assertIsInstance(d["ist_halter"], int)

    def test_ist_halter_string_wird_int(self):
        b = _FakeBeteiligter()
        b.ist_halter = "1"
        d = beteiligter_as_dict(b)
        self.assertIsInstance(d["ist_halter"], int)
        self.assertEqual(d["ist_halter"], 1)

    def test_vertreter_felder(self):
        b = _FakeBeteiligter()
        b.vertreter_name = "Dr. Klaus"
        b.vertreter_funktion = "GF"
        d = beteiligter_as_dict(b)
        self.assertEqual(d["vertreter_name"], "Dr. Klaus")
        self.assertEqual(d["vertreter_funktion"], "GF")

    def test_vorsteuer_none_wird_N(self):
        b = _FakeBeteiligter()
        b.vorsteuer = None
        d = beteiligter_as_dict(b)
        self.assertEqual(d["vorsteuer"], "N")


if __name__ == "__main__":
    unittest.main()
