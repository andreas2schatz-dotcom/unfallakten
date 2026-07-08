"""
Golden-File-Tests fuer die Dokumentklassen-Registry (S1.5).

Fuer jede Klasse gibt es unter backend/tests/golden/<klasse>/:
  * fixture.txt      -- synthetischer Text (KEINE echten Kanzlei-Dokumente, DSGVO)
  * erwartung.json   -- {"klasse": "...", "felder": {feldname: wert, ...}}

Der Test verifiziert:
  1. Klasse ist in der Registry geladen.
  2. Mindestens ein Marker aus der YAML kommt im Fixture-Text vor
     (fuer Klassen mit Markern; 'sonstiges' hat bewusst keine Marker).
  3. Fuer jedes Feld in erwartung['felder']: mindestens ein regex_felder-
     Pattern der Klasse liefert den erwarteten Wert.
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

ERWARTETE_KLASSEN = [
    "gutachten",
    "abrechnungsschreiben",
    "pruefbericht",
    "rechnung",
    "sv_rechnung",
    "abschlepprechnung",
    "standkostenrechnung",
    "sonstiges",
]


class TestGoldenFilesExistieren(unittest.TestCase):
    def test_jede_klasse_hat_golden_verzeichnis(self):
        for k in ERWARTETE_KLASSEN:
            pfad = os.path.join(GOLDEN_DIR, k)
            self.assertTrue(os.path.isdir(pfad),
                            f"Golden-Verzeichnis fehlt: {pfad}")
            self.assertTrue(os.path.isfile(os.path.join(pfad, "fixture.txt")),
                            f"fixture.txt fehlt in {pfad}")
            self.assertTrue(os.path.isfile(os.path.join(pfad, "erwartung.json")),
                            f"erwartung.json fehlt in {pfad}")


class TestGoldenKlassifikation(unittest.TestCase):
    """Marker aus der YAML kommen im Fixture-Text vor -> Klasse erkennbar."""

    def setUp(self):
        from backend.intake.registry_loader import lade_registry, standard_pfad
        self.registry = lade_registry(standard_pfad(), reload=True)

    def test_marker_matchen_pro_klasse(self):
        for k in ERWARTETE_KLASSEN:
            eintrag = self.registry.klassen[k]
            fixture_pfad = os.path.join(GOLDEN_DIR, k, "fixture.txt")
            with open(fixture_pfad, "r", encoding="utf-8") as f:
                text = f.read()

            marker = eintrag["marker"]
            if not marker:
                # 'sonstiges' hat bewusst keine Marker -> Auffangklasse
                self.assertEqual(k, "sonstiges",
                                 f"Nur 'sonstiges' darf marker-frei sein, nicht {k}")
                continue

            treffer = [m for m in marker if m.lower() in text.lower()]
            self.assertTrue(
                treffer,
                f"Klasse {k}: kein Marker im Fixture-Text gefunden. Marker: {marker!r}",
            )


class TestGoldenExtraktion(unittest.TestCase):
    """regex_felder aus der YAML matchen die erwarteten Werte im Fixture."""

    def setUp(self):
        from backend.intake.registry_loader import lade_registry, standard_pfad
        self.registry = lade_registry(standard_pfad(), reload=True)

    def _extrahiere_feld(self, text: str, patterns: list) -> str:
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1) if m.groups() else m.group(0)
        return ""

    def test_regex_felder_treffen_erwartete_werte(self):
        for k in ERWARTETE_KLASSEN:
            eintrag = self.registry.klassen[k]
            fixture_pfad = os.path.join(GOLDEN_DIR, k, "fixture.txt")
            erwart_pfad  = os.path.join(GOLDEN_DIR, k, "erwartung.json")

            with open(fixture_pfad, "r", encoding="utf-8") as f:
                text = f.read()
            with open(erwart_pfad, "r", encoding="utf-8") as f:
                erwartung = json.load(f)

            # Klasse muss passen
            self.assertEqual(erwartung["klasse"], k,
                             f"erwartung.json['klasse']={erwartung['klasse']} ≠ {k}")

            felder = erwartung.get("felder", {}) or {}
            for feld_name, erwartet in felder.items():
                patterns = eintrag["regex_felder"].get(feld_name, [])
                self.assertTrue(
                    patterns,
                    f"Klasse {k}: regex_felder hat kein Muster fuer {feld_name!r}",
                )
                gefunden = self._extrahiere_feld(text, patterns)
                self.assertEqual(
                    gefunden, erwartet,
                    f"Klasse {k} Feld {feld_name}: erwartet {erwartet!r}, gefunden {gefunden!r}",
                )


if __name__ == "__main__":
    unittest.main()
