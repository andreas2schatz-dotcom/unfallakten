import os
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.ramicro import adress_service, akten_erkennung
from backend.ramicro.connector import RaMicroVerbindungsFehler


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self.cur = _FakeCursor(rows)

    def cursor(self):
        return self.cur


def _fake_connection(rows):
    @contextmanager
    def _cm():
        yield _cm.conn
    _cm.conn = _FakeConn(rows)
    return _cm


def _offline():
    @contextmanager
    def _cm():
        raise RaMicroVerbindungsFehler("offline")
        yield
    return _cm


ADRESSE = {"adressnr": 12345, "anrede": "1", "name": "Achkour Zejli",
           "vorname": "Abdessamad", "firmenzeile": "",
           "strasse": "Wiener Straße 61", "plz": "60599",
           "ort": "Frankfurt am Main", "telefon": "069/1234",
           "email": "a@b.de"}


class TestHoleAdresseDetails(unittest.TestCase):
    def test_liefert_alle_felder(self):
        cm = _fake_connection([ADRESSE])
        with patch.object(adress_service, "get_ramicro_connection", cm):
            d = adress_service.hole_adresse_details(12345)
        self.assertEqual(d["strasse"], "Wiener Straße 61")
        self.assertEqual(d["plz"], "60599")
        self.assertEqual(d["anrede"], "1")
        self.assertIn("[sStraße]", cm.conn.cur.sql)
        self.assertIn("iAdressnummer", cm.conn.cur.sql)

    def test_offline_liefert_none(self):
        with patch.object(adress_service, "get_ramicro_connection",
                          _offline()):
            self.assertIsNone(adress_service.hole_adresse_details(1))


class TestAktenZuAdresse(unittest.TestCase):
    def test_liefert_akten(self):
        rows = [{"az": "285/26", "kurzbezeichnung": "Zejli ./. KRAVAG"}]
        cm = _fake_connection(rows)
        with patch.object(adress_service, "get_ramicro_connection", cm):
            akten = adress_service.akten_zu_adresse(12345)
        self.assertEqual(akten, [{"az": "285/26",
                                  "kurzbezeichnung": "Zejli ./. KRAVAG"}])
        self.assertIn("bDeaktiviert = 0", cm.conn.cur.sql)
        self.assertIn("1899-12-30", cm.conn.cur.sql)

    def test_offline_liefert_leer(self):
        with patch.object(adress_service, "get_ramicro_connection",
                          _offline()):
            self.assertEqual(adress_service.akten_zu_adresse(1), [])


class TestFindeNeueAkten(unittest.TestCase):
    def test_ohne_kriterium_leer_aber_verfuegbar(self):
        erg = akten_erkennung.finde_neue_akten("2026-07-30 10:00:00")
        self.assertEqual(erg, {"verfuegbar": True, "treffer": []})

    def test_treffer_nach_nachname(self):
        rows = [{"az": "301/26", "kurzbezeichnung": "Zejli ./. KRAVAG"}]
        cm = _fake_connection(rows)
        with patch.object(akten_erkennung, "get_ramicro_connection", cm):
            erg = akten_erkennung.finde_neue_akten(
                "2026-07-30 10:00:00", nachname="Achkour Zejli")
        self.assertTrue(erg["verfuegbar"])
        self.assertEqual(erg["treffer"][0]["az"], "301/26")
        self.assertIn("adr.sNachname LIKE %(nachname)s", cm.conn.cur.sql)
        self.assertEqual(cm.conn.cur.params["nachname"], "%Achkour Zejli%")

    def test_adressnr_hat_vorrang(self):
        rows = [{"az": "302/26", "kurzbezeichnung": ""}]
        cm = _fake_connection(rows)
        with patch.object(akten_erkennung, "get_ramicro_connection", cm):
            erg = akten_erkennung.finde_neue_akten(
                "2026-07-30 10:00:00", nachname="X", adressnr="12345")
        self.assertEqual(erg["treffer"][0]["az"], "302/26")
        self.assertIn("b.iAdressnummer = %(adressnr)s", cm.conn.cur.sql)
        self.assertNotIn("sNachname LIKE", cm.conn.cur.sql)
        self.assertEqual(cm.conn.cur.params["adressnr"], "12345")

    def test_offline(self):
        with patch.object(akten_erkennung, "get_ramicro_connection",
                          _offline()):
            erg = akten_erkennung.finde_neue_akten(
                "2026-07-30 10:00:00", nachname="X")
        self.assertEqual(erg, {"verfuegbar": False, "treffer": []})


if __name__ == "__main__":
    unittest.main()
