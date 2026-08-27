"""Unit-Tests fuer backend/intake/fragebogen_signale.py.

Die Kennzeichen-Schreibweisen stammen aus echten Unfallboegen im
Produktivsystem (Stand 2026-08-27) -- Mandanten tippen frei ein.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake.fragebogen_signale import (
    baue_kopf, baue_signale, erkenne_fragebogen, normiere_kennzeichen,
)


def _bogen_json(**ueberschreibungen):
    basis = {
        "meta": {"formular": "unfallbogen", "version": "2.1"},
        "mandant": {"name": "Golovin", "vorname": "Paul",
                     "email": "PaulGolovin@web.de", "telefon": "01785799951"},
        "gegner": {"fahrer": "Brochner",
                    "fahrzeug": {"kennzeichen": "MTK-DB801"}},
        "unfall": {"datum": "2026-08-03", "ort": "Mainhausen"},
        "sachschaden": {"eigenes_fahrzeug": {"kennzeichen": "WÜ PG 777"}},
    }
    basis.update(ueberschreibungen)
    return json.dumps(basis, ensure_ascii=False)


class TestNormiereKennzeichen(unittest.TestCase):
    def test_echte_schreibweisen_werden_zum_schluessel(self):
        faelle = [
            ("WÜ PG 777",  "WÜPG777"),
            ("OF A-418",   "OFA418"),
            ("OFGM891",    "OFGM891"),
            ("OF CJ 828",  "OFCJ828"),
            ("OF-BR 1612", "OFBR1612"),
            ("of-br 1612", "OFBR1612"),
        ]
        for roh, erwartet in faelle:
            with self.subTest(roh=roh):
                self.assertEqual(normiere_kennzeichen(roh), erwartet)

    def test_freitext_wird_verworfen(self):
        for roh in ("k.A. Fußgänger", "siehe Akte", "unbekannt", "", None,
                    "12345", "ABCDEFG"):
            with self.subTest(roh=roh):
                self.assertIsNone(normiere_kennzeichen(roh))


class TestErkenneFragebogen(unittest.TestCase):
    def test_gueltiger_bogen_wird_erkannt(self):
        bogen = erkenne_fragebogen("text", _bogen_json())
        self.assertIsNotNone(bogen)
        self.assertEqual(bogen["mandant"]["name"], "Golovin")

    def test_pdf_payload_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("pdf", _bogen_json()))

    def test_fremdes_json_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("text", '{"meta": {}}'))

    def test_kein_json_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("text", "Sehr geehrte Damen"))

    def test_leerer_text_ist_kein_bogen(self):
        self.assertIsNone(erkenne_fragebogen("text", ""))
        self.assertIsNone(erkenne_fragebogen("text", None))


class TestBaueSignale(unittest.TestCase):
    def test_vollstaendiger_bogen(self):
        s = baue_signale(erkenne_fragebogen("text", _bogen_json()))
        self.assertEqual(s["dokument_art"], "fragebogen")
        self.assertEqual(s["mandant_email"], "paulgolovin@web.de")
        self.assertEqual(s["kfz_mandant"], "WÜPG777")
        self.assertEqual(s["kfz_gegner"], "MTKDB801")
        self.assertEqual(s["nachname"], "Golovin")
        self.assertEqual(s["unfalltag"], "2026-08-03")
        self.assertNotIn("az", s)

    def test_aktenzeichen_wird_normiert_uebernommen(self):
        roh = json.loads(_bogen_json())
        roh["meta"]["aktenzeichen"] = "641/26AS"
        s = baue_signale(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(s["az"], "641/26")

    def test_fussgaenger_ohne_kennzeichen(self):
        roh = json.loads(_bogen_json())
        roh["sachschaden"]["eigenes_fahrzeug"]["kennzeichen"] = "k.A. Fußgänger"
        roh["gegner"]["fahrzeug"]["kennzeichen"] = "siehe Akte"
        s = baue_signale(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertNotIn("kfz_mandant", s)
        self.assertNotIn("kfz_gegner", s)
        self.assertEqual(s["mandant_email"], "paulgolovin@web.de")

    def test_leere_felder_erzeugen_keine_signale(self):
        roh = json.loads(_bogen_json())
        roh["mandant"] = {"name": "", "email": "  "}
        roh["unfall"] = {}
        roh["sachschaden"] = {}
        roh["gegner"] = {}
        s = baue_signale(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(s, {"dokument_art": "fragebogen"})


class TestBaueKopf(unittest.TestCase):
    def test_kopf_fuer_die_listenanzeige(self):
        k = baue_kopf(erkenne_fragebogen("text", _bogen_json()))
        self.assertEqual(k["mandant_name"], "Paul Golovin")
        self.assertEqual(k["kennzeichen"], "WÜ PG 777")
        self.assertEqual(k["unfalltag"], "2026-08-03")

    def test_kopf_zeigt_rohes_kennzeichen_auch_wenn_unbrauchbar(self):
        roh = json.loads(_bogen_json())
        roh["sachschaden"]["eigenes_fahrzeug"]["kennzeichen"] = "k.A. Fußgänger"
        k = baue_kopf(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(k["kennzeichen"], "k.A. Fußgänger")

    def test_kopf_ohne_vorname(self):
        roh = json.loads(_bogen_json())
        roh["mandant"]["vorname"] = None
        k = baue_kopf(erkenne_fragebogen("text", json.dumps(roh)))
        self.assertEqual(k["mandant_name"], "Golovin")


if __name__ == "__main__":
    unittest.main()
