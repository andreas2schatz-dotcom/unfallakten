"""
V11 Golden-Paritaet (Stufe 1): pinnt die Klage-Vorschautexte vor dem
Registry-Umbau. Der Umbau ohne Overrides muss byte-identische Texte liefern.
Bewusste Neuaufnahme (nur nach dokumentierter Textaenderung):
  KLAGE_GOLDEN_UPDATE=1 python -m pytest backend/tests/test_klage_standardtexte_golden.py
Abschnitt "datum" wird ausgeklammert (enthaelt das Tagesdatum).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from backend.word.klage_service import baue_klage_vorschau
from backend.tests.test_klage_service_docx import _akte_daten, _position

GOLDEN_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "golden", "klage_standardtexte")

VERS = {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
        "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"}
MANN = {"rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
        "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach"}


def _basis_cfg(mit_sg=False, n_bek=1, akt_typ="eigentum"):
    pos = [_position("fahrzeugschaden", "Fahrzeugschaden", 3000.0)]
    akte = _akte_daten(pos, mit_schmerzensgeld=mit_sg,
                       schmerzensgeld_mindest=2000.0 if mit_sg else 0.0)
    akte["unfalldetails"]["aktivlegitimation_typ"] = akt_typ
    akte["klage_config"]["beklagte"] = [VERS] if n_bek == 1 else [VERS, MANN]
    akte["klage_config"]["verzugsdatum"] = "2026-05-04"
    return akte


def _szenarien():
    sz = {}
    for mit_sg in (False, True):
        for n_bek in (1, 2):
            for akt_typ in ("eigentum", "finanziert", "geleast"):
                sz["matrix_sg%d_bek%d_%s" % (int(mit_sg), n_bek, akt_typ)] = \
                    _basis_cfg(mit_sg, n_bek, akt_typ)
    fallb = _basis_cfg(n_bek=2)
    fallb["klage_config"]["haftungsquote"] = 70
    fallb["klage_config"]["haftungsquote_typ"] = "eigen"
    sz["fallb_eigene_quote"] = fallb
    gegnerisch = _basis_cfg(n_bek=2)
    gegnerisch["klage_config"]["haftungsquote"] = 70
    gegnerisch["klage_config"]["haftungsquote_typ"] = "gegnerisch"
    sz["quote_gegnerisch_bestritten"] = gegnerisch
    mann_solo = _basis_cfg()
    mann_solo["klage_config"]["beklagte"] = [MANN]
    sz["beklagter_maennlich"] = mann_solo
    teilreg = _basis_cfg()
    teilreg["abrechnungen"] = [{"gesamt_reguliert": 500.0}]
    sz["teilregulierung"] = teilreg
    return sz


def _snapshot(akte_daten):
    res = baue_klage_vorschau(akte_daten)
    teile = []
    for a in res["abschnitte"]:
        if a["key"] == "datum":
            continue
        teile.append("== %s ==\n%s" % (a["key"], a["text"]))
    return "\n\n".join(teile) + "\n"


class TestKlageGolden(unittest.TestCase):

    def test_golden_paritaet(self):
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        update = os.environ.get("KLAGE_GOLDEN_UPDATE") == "1"
        for name, akte in _szenarien().items():
            with self.subTest(szenario=name):
                ist = _snapshot(akte)
                pfad = os.path.join(GOLDEN_DIR, name + ".txt")
                if update or not os.path.exists(pfad):
                    with open(pfad, "w", encoding="utf-8", newline="\n") as f:
                        f.write(ist)
                with open(pfad, "r", encoding="utf-8", newline="\n") as f:
                    soll = f.read()
                self.assertEqual(soll, ist)

    def test_szenarien_treffen_die_zielpfade(self):
        snaps = {n: _snapshot(a) for n, a in _szenarien().items()}
        self.assertIn("Mithaftungsquote", snaps["fallb_eigene_quote"])
        # Der Backend-Teilregulierungssatz (klage_service.py:1647) ist strukturell
        # unerreichbar: "not reg_tbl_xml" und gesamt_reguliert > 0 schliessen sich
        # aus (beide stammen aus denselben abrechnungen-Summen, KW-04-Altlast).
        # Das Szenario pinnt stattdessen, dass die Abrechnung den
        # "keine Regulierung"-Satz unterdrueckt. Teilregulierungs-Text kommt real
        # nur ueber den Wizard-Override-Pfad (Frontend) ins Dokument.
        self.assertNotIn("keine Regulierung", snaps["teilregulierung"])
        self.assertIn("Dies wird bestritten", snaps["quote_gegnerisch_bestritten"])
        self.assertIn("keine Regulierung", snaps["matrix_sg0_bek1_eigentum"])
