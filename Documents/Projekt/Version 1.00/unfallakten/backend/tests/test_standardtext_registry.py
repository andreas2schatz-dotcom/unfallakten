"""Fail-loud-Guards fuer die Klage-Standardtext-Registry (Muster: test_rausch_regel.py)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

from backend.services.standardtext_registry import lade_standardtexte, ABSCHNITTE

ERWARTETE_KEYS = {
    "antraege_versaeumnis_einleitung", "antraege_versaeumnis_titel",
    "antraege_versaeumnis_schluss",
    "sachverhalt_auslandsunfall",
    "unfallhergang_schilderung_fehlt", "unfallhergang_beweis_rekonstruktion",
    "unfallhergang_beweis_ermittlungsakte", "unfallhergang_beweis_ermittlungsakte_kurz",
    "schaden_einleitung", "schaden_beweis_gutachten", "schaden_beweis_gerichtsgutachten",
    "schaden_zahlungen_vorspann", "schaden_fallb_geklemmt", "schaden_fallb_offen",
    "schaden_fallb_voll", "schaden_differenz", "schaden_gesamtbetrag",
    "wuerdigung_grundhaftung", "wuerdigung_teilregulierung",
    "wuerdigung_keine_regulierung", "wuerdigung_alleinhaftung_bestritten",
    "sg_beweis_atteste", "sg_krankenhaus_mit_klinik", "sg_krankenhaus",
    "sg_arbeitsunfaehigkeit", "sg_dauerfolgen_mit_text", "sg_dauerfolgen",
    "sg_begruendung_mindestbetrag", "sg_begruendung_angemessen",
    "verzug_mit_datum", "verzug_beweis_schreiben", "verzug_rechtshaengigkeit",
    "gebuehren_begruendung_anspruch", "gebuehren_begruendung_kontakt",
    "gebuehren_begruendung_berechnung",
    "gebuehren_zeile_gegenstandswert", "gebuehren_zeile_geschaeftsgebuehr",
    "gebuehren_zeile_post", "gebuehren_zeile_zwischensumme", "gebuehren_zeile_ust",
    "gebuehren_zeile_gesamt", "gebuehren_zeile_gezahlt", "gebuehren_zeile_offen",
    "schluss_hinweis",
}

MINIMAL_GUELTIG = """
platzhalter:
  BETRAG: {beschreibung: "Betrag", beispiel: "1,00 €"}
bausteine:
  - key: schluss_hinweis
    abschnitt: schluss
    beschreibung: "Test"
    text: |-
      Satz mit <BETRAG>.
    platzhalter: [BETRAG]
    pflicht: [BETRAG]
"""


class TestEchteRegistry(unittest.TestCase):
    def test_vollstaendig_gegen_inventar(self):
        reg = lade_standardtexte(reload=True)
        self.assertEqual(ERWARTETE_KEYS, set(reg.keys()))

    def test_struktur_jedes_bausteins(self):
        reg = lade_standardtexte(reload=True)
        for key, e in reg.items():
            with self.subTest(key=key):
                self.assertIn(e["abschnitt"], ABSCHNITTE)
                self.assertTrue(e["beschreibung"].strip())
                self.assertTrue(e["text"].strip())
                for p in e["platzhalter"]:
                    self.assertTrue(p["beschreibung"])
                    self.assertTrue(p["beispiel"])
                    self.assertIn(p["pflicht"], (True, False))


class TestFailLoud(unittest.TestCase):
    def _lade(self, yaml_text):
        tmp = tempfile.mkdtemp(prefix="st_reg_")
        pfad = os.path.join(tmp, "klage_standardtexte.yaml")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write(yaml_text)
        return lade_standardtexte(pfad, reload=True)

    def test_minimal_gueltig(self):
        reg = self._lade(MINIMAL_GUELTIG)
        self.assertEqual(list(reg), ["schluss_hinweis"])
        self.assertEqual(reg["schluss_hinweis"]["platzhalter"][0]["pflicht"], True)

    def test_datei_fehlt(self):
        with self.assertRaises(RuntimeError):
            lade_standardtexte(os.path.join(tempfile.mkdtemp(), "nix.yaml"), reload=True)

    def test_doppelter_key(self):
        kaputt = MINIMAL_GUELTIG + MINIMAL_GUELTIG.split("bausteine:")[1]
        with self.assertRaises(RuntimeError):
            self._lade(kaputt)

    def test_unbekannter_platzhalter_im_text(self):
        with self.assertRaises(RuntimeError):
            self._lade(MINIMAL_GUELTIG.replace("<BETRAG>", "<UNBEKANNT>"))

    def test_platzhalter_ohne_katalogeintrag(self):
        with self.assertRaises(RuntimeError):
            self._lade(MINIMAL_GUELTIG.replace("[BETRAG]\n    pflicht", "[BETRAG, FREMD]\n    pflicht"))

    def test_pflicht_fehlt_im_standardtext(self):
        kaputt = MINIMAL_GUELTIG.replace("Satz mit <BETRAG>.", "Satz ohne Platzhalter.")
        with self.assertRaises(RuntimeError):
            self._lade(kaputt)

    def test_unbekannter_abschnitt(self):
        with self.assertRaises(RuntimeError):
            self._lade(MINIMAL_GUELTIG.replace("abschnitt: schluss", "abschnitt: kapitel_x"))


class TestAppStartGuard(unittest.TestCase):
    def test_kaputte_registry_stoppt_app_start(self):
        tmp = tempfile.mkdtemp(prefix="st_reg_broken_")
        pfad = os.path.join(tmp, "klage_standardtexte.yaml")
        with open(pfad, "w", encoding="utf-8") as f:
            f.write("bausteine: [")
        alt = os.environ.get("KLAGE_STANDARDTEXTE_PFAD")
        os.environ["KLAGE_STANDARDTEXTE_PFAD"] = pfad
        try:
            from backend.app import erstelle_app
            with self.assertRaises(RuntimeError):
                erstelle_app({"TESTING": True})
        finally:
            if alt is None:
                os.environ.pop("KLAGE_STANDARDTEXTE_PFAD", None)
            else:
                os.environ["KLAGE_STANDARDTEXTE_PFAD"] = alt


if __name__ == "__main__":
    unittest.main()
