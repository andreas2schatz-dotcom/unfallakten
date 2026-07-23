"""
Tests fuer backend/services/positionsmodell_registry.py (P1.1).

Loader-Verhalten:
  * Erfolgreich laden: dataclass mit positionsarten / ereignistypen /
    aktionen / version.
  * Fail-Loud bei fehlender YAML, YAML-Syntaxfehler, unbekannter
    checkliste-Referenz, unbekanntem aktionen-Ereignistyp.
  * POSITION_KEYS-Katalog aus abrechnungsschreiben.py ist vollstaendig in
    positionsarten abgedeckt (jeder Key hat einen Eintrag).
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestPositionsmodellRegistryLaden(unittest.TestCase):
    def test_default_registry_laesst_sich_laden(self):
        from backend.services.positionsmodell_registry import lade_positionsmodell
        reg = lade_positionsmodell(reload=True)
        self.assertGreater(len(reg.positionsarten), 20)
        self.assertGreater(len(reg.ereignistypen), 5)
        self.assertGreater(len(reg.aktionen), 5)
        self.assertRegex(reg.version, r"^[0-9a-f]{8,}$")

    def test_alle_position_keys_abgedeckt(self):
        from backend.services.positionsmodell_registry import lade_positionsmodell
        from backend.models.abrechnungsschreiben import POSITION_KEYS
        reg = lade_positionsmodell(reload=True)
        fehlend = sorted(k for k in POSITION_KEYS
                          if k not in reg.positionsarten)
        self.assertFalse(
            fehlend,
            f"POSITION_KEYS ohne Registry-Eintrag: {fehlend}",
        )

    def test_alle_checkliste_referenzen_gueltig(self):
        from backend.services.positionsmodell_registry import lade_positionsmodell
        reg = lade_positionsmodell(reload=True)
        for key, art in reg.positionsarten.items():
            for typ in art.get("checkliste", []):
                self.assertIn(
                    typ, reg.ereignistypen,
                    f"positionsart {key!r}.checkliste -> {typ!r} ist "
                    "kein gueltiger Ereignistyp",
                )

    def test_alle_aktionen_zeigen_auf_gueltige_typen(self):
        from backend.services.positionsmodell_registry import lade_positionsmodell
        reg = lade_positionsmodell(reload=True)
        for typ in reg.aktionen.keys():
            self.assertIn(
                typ, reg.ereignistypen,
                f"aktionen.yaml: Ereignistyp {typ!r} nicht in "
                "ereignistypen.yaml",
            )

    def test_positions_synonyme_zeigen_auf_gueltige_position_keys(self):
        from backend.services.positionsmodell_registry import lade_positionsmodell
        reg = lade_positionsmodell(reload=True)
        self.assertGreater(len(reg.positions_synonyme), 5)
        for synonym, ziel in reg.positions_synonyme.items():
            self.assertIn(
                ziel, reg.positionsarten,
                f"positions_synonyme[{synonym!r}] -> {ziel!r} ist kein "
                "gueltiger position_key",
            )


class TestPositionsmodellRegistryFailLoud(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="pmreg_")
        self._alt_env = os.environ.get("POSITIONSMODELL_REGISTRY_PFAD")
        os.environ["POSITIONSMODELL_REGISTRY_PFAD"] = self._tmp

    def tearDown(self):
        if self._alt_env is None:
            os.environ.pop("POSITIONSMODELL_REGISTRY_PFAD", None)
        else:
            os.environ["POSITIONSMODELL_REGISTRY_PFAD"] = self._alt_env
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_fehlendes_verzeichnis_wirft(self):
        os.environ["POSITIONSMODELL_REGISTRY_PFAD"] = os.path.join(
            self._tmp, "nichtvorhanden",
        )
        from backend.services.positionsmodell_registry import lade_positionsmodell
        with self.assertRaises(RuntimeError):
            lade_positionsmodell(reload=True)

    def test_defektes_yaml_wirft(self):
        for name in ("positionsarten.yaml", "ereignistypen.yaml",
                     "aktionen.yaml", "rechnungstyp_mapping.yaml",
                     "klasse_ereignistyp.yaml", "positions_synonyme.yaml"):
            with open(os.path.join(self._tmp, name), "w",
                      encoding="utf-8") as f:
                f.write("nicht: gueltiges: yaml: [")
        from backend.services.positionsmodell_registry import lade_positionsmodell
        with self.assertRaises(RuntimeError):
            lade_positionsmodell(reload=True)

    def test_checkliste_zeigt_auf_unbekannten_typ_wirft(self):
        with open(os.path.join(self._tmp, "positionsarten.yaml"), "w",
                   encoding="utf-8") as f:
            f.write(
                "positionsarten:\n"
                "  reparaturkosten:\n"
                "    label: Reparaturkosten\n"
                "    kategorie: fahrzeugschaden\n"
                "    aggregation: fahrzeugschaden\n"
                "    checkliste: [ungueltiger_typ_xyz]\n"
            )
        with open(os.path.join(self._tmp, "ereignistypen.yaml"), "w",
                   encoding="utf-8") as f:
            f.write(
                "ereignistypen:\n"
                "  gutachten_eingegangen:\n"
                "    label: Gutachten\n"
                "    richtung: eingehend\n"
                "    zulaessige_quellen: [dokument]\n"
                "    default_wirkung: gefordert\n"
                "    checklisten_relevanz: []\n"
            )
        with open(os.path.join(self._tmp, "aktionen.yaml"), "w",
                   encoding="utf-8") as f:
            f.write("aktionen: {}\n")
        with open(os.path.join(self._tmp, "rechnungstyp_mapping.yaml"), "w",
                   encoding="utf-8") as f:
            f.write("rechnungstyp_mapping: {}\n")
        with open(os.path.join(self._tmp, "klasse_ereignistyp.yaml"), "w",
                   encoding="utf-8") as f:
            f.write("klasse_ereignistyp: {}\n")
        with open(os.path.join(self._tmp, "positions_synonyme.yaml"), "w",
                   encoding="utf-8") as f:
            f.write("positions_synonyme: {}\n")

        from backend.services.positionsmodell_registry import lade_positionsmodell
        with self.assertRaisesRegex(RuntimeError, "ungueltiger_typ_xyz"):
            lade_positionsmodell(reload=True)


class TestKlasseEreignistyp(unittest.TestCase):
    def test_mapping_geladen_und_nur_eingehende_typen(self):
        from backend.services.positionsmodell_registry import lade_positionsmodell
        reg = lade_positionsmodell(reload=True)
        self.assertIsInstance(reg.klasse_ereignistyp, dict)
        self.assertEqual(reg.klasse_ereignistyp["gutachten"], "gutachten_eingegangen")
        self.assertEqual(reg.klasse_ereignistyp["abschlepprechnung"], "rechnung_eingegangen")
        self.assertEqual(reg.klasse_ereignistyp["abrechnungsschreiben"], "abrechnung_eingegangen")
        for klasse, typ in reg.klasse_ereignistyp.items():
            self.assertIn(typ, reg.ereignistypen, f"{klasse}->{typ} kein Ereignistyp")
            self.assertEqual(
                reg.ereignistypen[typ]["richtung"], "eingehend",
                f"{klasse}->{typ} ist nicht eingehend",
            )

    def test_ungueltiger_typ_wirft(self):
        quelle = None
        from backend.services.positionsmodell_registry import standard_pfad
        quelle = standard_pfad()
        tmp = tempfile.mkdtemp(prefix="reg_")
        try:
            for name in os.listdir(quelle):
                if name.endswith(".yaml"):
                    shutil.copy(os.path.join(quelle, name), os.path.join(tmp, name))
            with open(os.path.join(tmp, "klasse_ereignistyp.yaml"), "w",
                      encoding="utf-8") as f:
                f.write("klasse_ereignistyp:\n  gutachten: forderung_generiert\n")
            from backend.services.positionsmodell_registry import lade_positionsmodell
            with self.assertRaises(RuntimeError):
                lade_positionsmodell(tmp, reload=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
