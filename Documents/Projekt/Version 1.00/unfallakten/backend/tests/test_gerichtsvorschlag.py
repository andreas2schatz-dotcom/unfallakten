"""
Gerichtsvorschlag aus dem Unfallort.

Der alte Abgleich nahm das ERSTE WORT des Unfallorts als Suchbegriff und
verglich es als Teilstring. varU-ORT ist aber Freitext: "Auf der Rosenhoehe
68, Offenbach" ergab das Hauptwort "auf", das als Teilstring in
"K-auf-beuren" steckt -- Akte 612/26 bekam das Amtsgericht Kaufbeuren
vorgeschlagen, waehrend das Amtsgericht Offenbach am Main nicht einmal
abgefragt wurde ("Offenbach" enthaelt kein "auf").

Messung ueber 400 echte Unfallorte aus RA-MICRO: 206 plausibel,
20 falsch, 174 ohne Vorschlag.

Getestet wird die reine Bewertungsfunktion -- ohne RA-MICRO, die
Gerichtsadressen werden als Liste hereingereicht.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.services.gerichtsvorschlag import waehle_gericht          # noqa: E402
from backend.services.gerichtsort_registry import (                    # noqa: E402
    lade_gerichtsorte, GerichtsortFehler,
)


def _g(name, ort, nr=90000):
    return {"adressnr": nr, "name": name, "strasse": "", "plz": "", "ort": ort}


# Ausschnitt aus tblAdressen, mit den Faellen, die real danebengingen.
GERICHTE = [
    _g("Amtsgericht Offenbach am Main", "Offenbach am Main", 96052),
    _g("Amtsgericht Offenbach am Main", "Offenbach am Main", 96050),   # Dublette
    _g("Amtsgericht Kaufbeuren",        "Kaufbeuren",        91001),
    _g("Amtsgericht Laufen i. OB.",     "Laufen i. OB.",     91002),
    _g("Amtsgericht Staufen i. Breisgau", "Staufen i. Breisgau", 91003),
    _g("Amtsgericht Baden-Baden",       "Baden-Baden",       91004),
    _g("Amtsgericht Bad Saulgau",       "Bad Saulgau",       91005),
    _g("Amtsgericht Frankfurt am Main", "Frankfurt am Main", 92001),
    _g("Amtsgericht Frankfurt (Oder)",  "Frankfurt (Oder)",  92002),
    _g("Amtsgericht Frankfurt am Main ASt Höchst", "Frankfurt am Main", 92003),
    _g("Landgericht Darmstadt",         "Offenbach am Main", 92919),
    _g("Amtsgericht Alsfeld",           "",                  93001),   # ohne sOrt
    _g("Amtsgericht Amberg",            "Amberg",            93002),
    _g("Amtsgericht Königstein im Taunus", "Königstein im Taunus", 93003),
]


def _registry(inhalt: str):
    fh = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    fh.write(inhalt)
    fh.close()
    return lade_gerichtsorte(fh.name, reload=True)


# Stufe 2 muss ohne Ortsliste geprueft werden, sonst faengt die gepflegte
# Liste die Faelle ab und der Namensabgleich bliebe ungetestet.
LEERE_LISTE = _registry("gerichtsorte: {}")


def _bester(unfallort, gerichte=None, registry=LEERE_LISTE):
    treffer = waehle_gericht(unfallort, gerichte if gerichte is not None else GERICHTE,
                             registry=registry)
    return treffer[0] if treffer else None


class TestNamensabgleich(unittest.TestCase):
    """Stufe 2: Abgleich gegen die Gerichtsadressen, wortgenau."""

    def test_strassenadresse_findet_das_gericht_am_ortsende(self):
        t = _bester("Auf der Rosenhöhe 68, Offenbach")
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_erstes_wort_wird_nicht_als_teilstring_gesucht(self):
        """"auf" darf nicht in "Kaufbeuren" treffen -- der Befund aus 612/26."""
        namen = [k["name"] for k in waehle_gericht("Auf der Rosenhöhe 68, Offenbach", GERICHTE, LEERE_LISTE)]
        self.assertNotIn("Amtsgericht Kaufbeuren", namen)
        self.assertNotIn("Amtsgericht Laufen i. OB.", namen)
        self.assertNotIn("Amtsgericht Staufen i. Breisgau", namen)

    def test_ort_mit_postleitzahl_wird_erkannt(self):
        t = _bester("Im Eschig, 63075 Offenbach")
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_bad_nauheim_trifft_nicht_baden_baden(self):
        """"bad" ist ein Namensbestandteil vieler Staedte, kein Ortskennzeichen."""
        t = _bester("Bad Nauheim")
        self.assertIsNone(t)

    def test_autobahnangabe_liefert_keinen_vorschlag(self):
        self.assertIsNone(_bester("A 661"))
        self.assertIsNone(_bester("A 66 Abfahrt zur A 5"))

    def test_vollstaendiger_stadtname_schlaegt_gleichnamige_stadt(self):
        t = _bester("Frankfurt am Main, Carl Benz Straße")
        self.assertEqual(t["name"], "Amtsgericht Frankfurt am Main")

    def test_hauptgericht_vor_zweigstelle(self):
        t = _bester("Frankfurt am Main, Carl Benz Straße")
        self.assertNotIn("ASt", t["name"])

    def test_gericht_ohne_ortsangabe_wird_nicht_bevorzugt(self):
        """Ein leeres sOrt uebersprang frueher den Abwertungszweig."""
        namen = [k["name"] for k in waehle_gericht("Alsfelder Straße, Offenbach", GERICHTE, LEERE_LISTE)]
        self.assertNotIn("Amtsgericht Alsfeld", namen)

    def test_amtsgericht_vor_landgericht_am_selben_ort(self):
        t = _bester("Offenbach")
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_dubletten_erscheinen_nur_einmal(self):
        treffer = waehle_gericht("Offenbach", GERICHTE, LEERE_LISTE)
        namen = [k["name"] for k in treffer]
        self.assertEqual(len(namen), len(set(namen)))

    def test_quelle_ist_der_namensabgleich(self):
        self.assertEqual(_bester("Offenbach")["quelle"], "unfallort_match")

    def test_leerer_unfallort_liefert_nichts(self):
        self.assertEqual(waehle_gericht("", GERICHTE, LEERE_LISTE), [])
        self.assertEqual(waehle_gericht(None, GERICHTE, LEERE_LISTE), [])


class TestOrtsliste(unittest.TestCase):
    """Stufe 1: gepflegte Zuordnung Ort -> Gericht (Bezirke Frankfurt/Darmstadt)."""

    LISTE = """
gerichtsorte:
  Heusenstamm:
    gericht: Amtsgericht Offenbach am Main
  Mühlheim am Main:
    gericht: Amtsgericht Offenbach am Main
"""

    def test_ort_ohne_eigenes_gericht_wird_zugeordnet(self):
        t = _bester("Heusenstamm", registry=_registry(self.LISTE))
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_quelle_weist_die_ortsliste_aus(self):
        t = _bester("Heusenstamm", registry=_registry(self.LISTE))
        self.assertEqual(t["quelle"], "ortsliste")

    def test_ortsliste_schlaegt_den_namensabgleich(self):
        """Auch wenn ein gleichnamiges Gericht existiert, gilt die Liste."""
        liste = _registry("""
gerichtsorte:
  Offenbach:
    gericht: Landgericht Darmstadt
""")
        t = _bester("Offenbach", registry=liste)
        self.assertEqual(t["name"], "Landgericht Darmstadt")
        self.assertEqual(t["quelle"], "ortsliste")

    def test_ortsliste_greift_mitten_in_einer_adresse(self):
        t = _bester("Bahnhofstraße 4, Heusenstamm", registry=_registry(self.LISTE))
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_mehrwortiger_ort_wird_als_phrase_gesucht(self):
        t = _bester("Unfall in Mühlheim am Main", registry=_registry(self.LISTE))
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_ortsliste_trifft_nicht_als_teilstring(self):
        liste = _registry("""
gerichtsorte:
  Bad:
    gericht: Amtsgericht Irgendwo
""")
        self.assertIsNone(_bester("Badenweiler", [], registry=liste))

    def test_adresse_aus_der_liste_uebernimmt_die_gerichtsanschrift(self):
        """Steht das Gericht auch in tblAdressen, wird dessen Anschrift benutzt."""
        t = _bester("Heusenstamm", registry=_registry(self.LISTE))
        self.assertEqual(t["adressnr"], 96052)
        self.assertEqual(t["ort"], "Offenbach am Main")


class TestOrtslisteFehler(unittest.TestCase):
    """Die Registry meldet Pflegefehler laut, statt still das Falsche zu tun."""

    def test_leere_liste_ist_zulaessig(self):
        r = _registry("gerichtsorte: {}\n")
        self.assertEqual(r.gerichtsorte, {})

    def test_eintrag_ohne_gericht_wird_abgelehnt(self):
        with self.assertRaises(GerichtsortFehler):
            _registry("gerichtsorte:\n  Heusenstamm:\n    gericht: ''\n")

    def test_unbekannter_schluessel_wird_abgelehnt(self):
        with self.assertRaises(GerichtsortFehler):
            _registry("gerichtsorte:\n  Heusenstamm:\n    gercht: AG Offenbach\n")

    def test_kaputtes_yaml_wird_abgelehnt(self):
        with self.assertRaises(GerichtsortFehler):
            _registry("gerichtsorte:\n  - [unausgeglichen\n")


class TestGepflegteListe(unittest.TestCase):
    """Die ausgelieferte Datei muss ladbar und in sich stimmig sein."""

    def test_registry_des_projekts_laedt(self):
        r = lade_gerichtsorte(reload=True)
        self.assertIsInstance(r.gerichtsorte, dict)

    def test_jeder_eintrag_nennt_ein_gericht(self):
        r = lade_gerichtsorte(reload=True)
        for ort, eintrag in r.gerichtsorte.items():
            self.assertTrue(eintrag["gericht"].strip(), f"{ort} ohne Gericht")


class TestKreisOffenbach(unittest.TestCase):
    """Der Landkreis Offenbach verteilt sich auf DREI Amtsgerichte.

    Quelle: ordentliche-gerichtsbarkeit.hessen.de, abgerufen 2026-09-02.
    Der Test haelt das fest, weil die Annahme "der ganze Kreis gehoert zum
    Amtsgericht Offenbach" naheliegt und fuer 8 der 13 Kommunen falsch ist
    -- eine Klage landete dann beim unzustaendigen Gericht.
    """

    ZUORDNUNG = {
        # Amtsgericht Offenbach am Main
        "Dietzenbach":       "Amtsgericht Offenbach am Main",
        "Heusenstamm":       "Amtsgericht Offenbach am Main",
        "Mühlheim am Main":  "Amtsgericht Offenbach am Main",
        "Neu-Isenburg":      "Amtsgericht Offenbach am Main",
        "Obertshausen":      "Amtsgericht Offenbach am Main",
        # Amtsgericht Langen (Hessen)
        "Dreieich":          "Amtsgericht Langen (Hessen)",
        "Egelsbach":         "Amtsgericht Langen (Hessen)",
        "Langen":            "Amtsgericht Langen (Hessen)",
        "Rödermark":         "Amtsgericht Langen (Hessen)",
        # Amtsgericht Seligenstadt
        "Hainburg":          "Amtsgericht Seligenstadt",
        "Mainhausen":        "Amtsgericht Seligenstadt",
        "Rodgau":            "Amtsgericht Seligenstadt",
        "Seligenstadt":      "Amtsgericht Seligenstadt",
    }

    def setUp(self):
        self.registry = lade_gerichtsorte(reload=True)

    def test_alle_dreizehn_kommunen_sind_gepflegt(self):
        fehlend = [o for o in self.ZUORDNUNG
                   if _bester(o, GERICHTE, self.registry) is None]
        self.assertEqual(fehlend, [], f"nicht in der Ortsliste: {fehlend}")

    def test_jede_kommune_zeigt_auf_ihr_amtsgericht(self):
        for ort, gericht in self.ZUORDNUNG.items():
            with self.subTest(ort=ort):
                t = _bester(ort, GERICHTE, self.registry)
                self.assertEqual(t["name"], gericht)
                self.assertEqual(t["quelle"], "ortsliste")

    def test_dreieich_gehoert_nicht_zum_amtsgericht_offenbach(self):
        """Der naheliegende Irrtum, ausdruecklich festgehalten."""
        t = _bester("Dreieich-Sprendlingen", GERICHTE, self.registry)
        self.assertEqual(t["name"], "Amtsgericht Langen (Hessen)")

    def test_muehlheim_ohne_zusatz_wird_ebenfalls_zugeordnet(self):
        """In den Akten steht 39x "Muehlheim" und 6x "Muehlheim am Main"."""
        t = _bester("Mühlheim", GERICHTE, self.registry)
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_niederroden_gehoert_zu_rodgau(self):
        t = _bester("Niederroden", GERICHTE, self.registry)
        self.assertEqual(t["name"], "Amtsgericht Seligenstadt")

    def test_frankfurt_ist_eindeutig_das_am_main(self):
        t = _bester("Frankfurt", GERICHTE, self.registry)
        self.assertEqual(t["name"], "Amtsgericht Frankfurt am Main")

    def test_ortsteil_mit_bindestrich_wird_der_stadt_zugeordnet(self):
        """In den Akten steht "Muehlheim-Laemmerspiel"."""
        t = _bester("Mühlheim-Lämmerspiel", GERICHTE, self.registry)
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")

    def test_bindestrich_stadtteil_auch_im_namensabgleich(self):
        """"Frankfurt-Riederwald" muss das Frankfurter Gericht finden."""
        t = _bester("Frankfurt-Riederwald", GERICHTE, self.registry)
        self.assertEqual(t["name"], "Amtsgericht Frankfurt am Main")

    def test_neu_isenburg_bleibt_trotz_bindestrichzerlegung_eindeutig(self):
        t = _bester("Neu-Isenburg", GERICHTE, self.registry)
        self.assertEqual(t["name"], "Amtsgericht Offenbach am Main")


if __name__ == "__main__":
    unittest.main()
