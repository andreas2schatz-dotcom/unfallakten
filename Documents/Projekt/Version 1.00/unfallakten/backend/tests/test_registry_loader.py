"""
Tests fuer intake/registry_loader.py (S1.5).

Anforderungen aus PIPELINE-REFACTORING-PLAN.md S1.5 + freigabe.md:
  * Verzeichnis backend/registry/klassen/*.yaml, ein File je Klasse.
  * Pflichtfelder je YAML: marker, regex_felder, schema, pflichtfelder,
    kritische_felder, validierungsregeln, fristrelevanz, loeschfrist_jahre.
  * Loader berechnet registry_version = kurzer Hash ueber alle YAMLs
    (deterministisch, reproduzierbar, aendert sich bei jeder YAML-Aenderung).
  * Ladefehler = raise (Fail-Loud) + ERROR-Log. Kein stiller Fallback auf
    leere Registry.
  * Loader singleton-Cache, aber lade_registry(pfad, reload=True) erneut moeglich
    (fuer Tests).
"""
import os
import sys
import shutil
import tempfile
import textwrap
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.intake import registry_loader


def _schreibe_yaml(pfad: str, inhalt: str) -> None:
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "w", encoding="utf-8") as f:
        f.write(inhalt)


_MINIMAL_YAML = """\
klasse: gutachten
marker:
  - Sachverstaendigengutachten
  - SV-Buero
regex_felder:
  schadennummer:
    - "SD-\\\\d+"
schema:
  schadennummer: string
  wiederbeschaffungswert: number
pflichtfelder:
  - schadennummer
kritische_felder:
  - wiederbeschaffungswert
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
"""


class _BaseLoaderTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="registry_test_")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestBasisLaden(_BaseLoaderTest):
    def test_leeres_verzeichnis_ergibt_fail_loud(self):
        """Kein YAML-File = Fail-Loud statt leerer Registry (behebt heutigen Bug)."""
        from backend.intake.registry_loader import lade_registry
        with self.assertRaises(RuntimeError):
            lade_registry(self._tmp, reload=True)

    def test_einzelne_klasse_wird_geladen(self):
        from backend.intake.registry_loader import lade_registry
        _schreibe_yaml(os.path.join(self._tmp, "gutachten.yaml"), _MINIMAL_YAML)
        reg = lade_registry(self._tmp, reload=True)
        self.assertIn("gutachten", reg.klassen)
        eintrag = reg.klassen["gutachten"]
        self.assertEqual(eintrag["loeschfrist_jahre"], 6)
        self.assertIn("Sachverstaendigengutachten", eintrag["marker"])

    def test_version_ist_deterministisch(self):
        from backend.intake.registry_loader import lade_registry
        _schreibe_yaml(os.path.join(self._tmp, "gutachten.yaml"), _MINIMAL_YAML)
        v1 = lade_registry(self._tmp, reload=True).version
        v2 = lade_registry(self._tmp, reload=True).version
        self.assertEqual(v1, v2)
        self.assertTrue(v1)  # nicht leer

    def test_version_aendert_sich_bei_yaml_aenderung(self):
        from backend.intake.registry_loader import lade_registry
        pfad = os.path.join(self._tmp, "gutachten.yaml")
        _schreibe_yaml(pfad, _MINIMAL_YAML)
        v1 = lade_registry(self._tmp, reload=True).version
        # Loeschfrist geaendert -> andere Version
        _schreibe_yaml(pfad,
                       _MINIMAL_YAML.replace("loeschfrist_jahre: 6",
                                             "loeschfrist_jahre: 10"))
        v2 = lade_registry(self._tmp, reload=True).version
        self.assertNotEqual(v1, v2)


class TestValidierung(_BaseLoaderTest):
    """Ladefehler = raise, nie stiller Fallback."""

    def test_defektes_yaml_wirft(self):
        from backend.intake.registry_loader import lade_registry
        _schreibe_yaml(os.path.join(self._tmp, "kaputt.yaml"),
                       "klasse: gutachten\n  invalid: [nicht: geschlossen")
        with self.assertRaises(RuntimeError) as ctx:
            lade_registry(self._tmp, reload=True)
        # Fehlermeldung soll den Dateinamen enthalten
        self.assertIn("kaputt.yaml", str(ctx.exception))

    def test_fehlende_pflichtfelder_wirft(self):
        from backend.intake.registry_loader import lade_registry
        # 'schema' fehlt
        yaml_ohne_schema = """\
klasse: gutachten
marker: []
regex_felder: {}
pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
"""
        _schreibe_yaml(os.path.join(self._tmp, "gutachten.yaml"), yaml_ohne_schema)
        with self.assertRaises(RuntimeError) as ctx:
            lade_registry(self._tmp, reload=True)
        self.assertIn("schema", str(ctx.exception).lower())

    def test_klasse_muss_zum_dateinamen_passen(self):
        from backend.intake.registry_loader import lade_registry
        # Datei 'rechnung.yaml' enthaelt 'klasse: gutachten' -> Fail
        _schreibe_yaml(os.path.join(self._tmp, "rechnung.yaml"), _MINIMAL_YAML)
        with self.assertRaises(RuntimeError) as ctx:
            lade_registry(self._tmp, reload=True)
        msg = str(ctx.exception).lower()
        self.assertTrue("klasse" in msg or "dateiname" in msg)

    def test_loeschfrist_muss_zahl_sein(self):
        from backend.intake.registry_loader import lade_registry
        yaml_falsch = _MINIMAL_YAML.replace("loeschfrist_jahre: 6",
                                           "loeschfrist_jahre: sechs")
        _schreibe_yaml(os.path.join(self._tmp, "gutachten.yaml"), yaml_falsch)
        with self.assertRaises(RuntimeError):
            lade_registry(self._tmp, reload=True)


class TestMehrereKlassen(_BaseLoaderTest):
    def test_zwei_klassen_werden_geladen(self):
        from backend.intake.registry_loader import lade_registry
        _schreibe_yaml(os.path.join(self._tmp, "gutachten.yaml"), _MINIMAL_YAML)
        rechnung_yaml = _MINIMAL_YAML.replace("klasse: gutachten",
                                              "klasse: rechnung")
        _schreibe_yaml(os.path.join(self._tmp, "rechnung.yaml"), rechnung_yaml)
        reg = lade_registry(self._tmp, reload=True)
        self.assertEqual(set(reg.klassen.keys()), {"gutachten", "rechnung"})

    def test_duplikate_klassen_werden_erkannt(self):
        """Zwei YAMLs mit derselben 'klasse' → Fail-Loud."""
        from backend.intake.registry_loader import lade_registry
        _schreibe_yaml(os.path.join(self._tmp, "gutachten.yaml"), _MINIMAL_YAML)
        _schreibe_yaml(os.path.join(self._tmp, "gutachten_2.yaml"), _MINIMAL_YAML)
        with self.assertRaises(RuntimeError):
            lade_registry(self._tmp, reload=True)


class TestSingleton(_BaseLoaderTest):
    def test_wiederholtes_laden_ohne_reload_nutzt_cache(self):
        """Ohne reload=True liefert lade_registry() dieselbe Instanz."""
        from backend.intake.registry_loader import lade_registry
        _schreibe_yaml(os.path.join(self._tmp, "gutachten.yaml"), _MINIMAL_YAML)
        r1 = lade_registry(self._tmp, reload=True)
        r2 = lade_registry(self._tmp)  # kein reload
        self.assertIs(r1, r2)


def _schreibe_klasse(dir_pfad, name, extra=""):
    inhalt = textwrap.dedent(f"""\
        klasse: {name}
        marker: []
        regex_felder: {{}}
        schema: {{}}
        pflichtfelder: []
        kritische_felder: []
        validierungsregeln: []
        fristrelevanz: false
        loeschfrist_jahre: 6
        label: {name.capitalize()}
    """) + extra
    with open(os.path.join(dir_pfad, f"{name}.yaml"), "w", encoding="utf-8") as f:
        f.write(inhalt)


def test_schema_wert_mit_typ_und_beschreibung_laedt(tmp_path):
    yaml_inhalt = _MINIMAL_YAML.replace(
        "  wiederbeschaffungswert: number",
        "  wiederbeschaffungswert:\n"
        "    typ: number\n"
        "    beschreibung: nur uebernehmen wenn ausgewiesen",
    ).replace("klasse: gutachten", "klasse: rechnung")
    _schreibe_yaml(os.path.join(str(tmp_path), "rechnung.yaml"), yaml_inhalt)
    reg = registry_loader.lade_registry(str(tmp_path), reload=True)
    schema = reg.klassen["rechnung"]["schema"]
    assert schema["wiederbeschaffungswert"]["typ"] == "number"


def test_schema_wert_mapping_ohne_typ_wirft(tmp_path):
    yaml_inhalt = _MINIMAL_YAML.replace(
        "  wiederbeschaffungswert: number",
        "  wiederbeschaffungswert:\n"
        "    beschreibung: ohne typ",
    ).replace("klasse: gutachten", "klasse: rechnung")
    _schreibe_yaml(os.path.join(str(tmp_path), "rechnung.yaml"), yaml_inhalt)
    with pytest.raises(RuntimeError, match="schema"):
        registry_loader.lade_registry(str(tmp_path), reload=True)


def test_schema_wert_falscher_typ_wirft(tmp_path):
    yaml_inhalt = _MINIMAL_YAML.replace(
        "  wiederbeschaffungswert: number",
        "  wiederbeschaffungswert: 42",
    ).replace("klasse: gutachten", "klasse: rechnung")
    _schreibe_yaml(os.path.join(str(tmp_path), "rechnung.yaml"), yaml_inhalt)
    with pytest.raises(RuntimeError, match="schema"):
        registry_loader.lade_registry(str(tmp_path), reload=True)


def test_gueltiges_parser_feld_laedt(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "parser: rechnung\n")
    reg = registry_loader.lade_registry(str(tmp_path), reload=True)
    assert reg.klassen["rechnung"]["parser"] == "rechnung"


def test_unbekannter_parser_wirft(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "parser: quatsch\n")
    with pytest.raises(RuntimeError, match="parser"):
        registry_loader.lade_registry(str(tmp_path), reload=True)


def test_ungueltige_richtung_wirft(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "richtung: seitwaerts\n")
    with pytest.raises(RuntimeError, match="richtung"):
        registry_loader.lade_registry(str(tmp_path), reload=True)


def test_ereignistyp_muss_string_sein(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "ereignistyp: 42\n")
    with pytest.raises(RuntimeError, match="ereignistyp"):
        registry_loader.lade_registry(str(tmp_path), reload=True)


from types import SimpleNamespace
from backend.intake.registry_loader import validiere_gegen_positionsmodell


def _pos_reg_stub():
    return SimpleNamespace(
        ereignistypen={"rechnung_eingegangen": {"richtung": "eingehend"},
                       "forderung_generiert": {"richtung": "ausgehend"}},
        positionsarten={"mietwagenkosten": {}, "rep_rechnung_netto": {}},
    )


def test_ereignistyp_nicht_eingehend_wirft():
    klassen_reg = SimpleNamespace(klassen={
        "x": {"klasse": "x", "ereignistyp": "forderung_generiert"}})
    with pytest.raises(RuntimeError, match="eingehend"):
        validiere_gegen_positionsmodell(klassen_reg, _pos_reg_stub())


def test_unbekannte_schadenposition_wirft():
    klassen_reg = SimpleNamespace(klassen={
        "x": {"klasse": "x", "schadenposition": "gibtsnicht"}})
    with pytest.raises(RuntimeError, match="schadenposition"):
        validiere_gegen_positionsmodell(klassen_reg, _pos_reg_stub())


def test_sv_vorsteuer_marker_erlaubt():
    klassen_reg = SimpleNamespace(klassen={
        "sv_rechnung": {"klasse": "sv_rechnung",
                        "schadenposition": "__sv_kosten_vorsteuer__"}})
    validiere_gegen_positionsmodell(klassen_reg, _pos_reg_stub())  # kein Fehler


if __name__ == "__main__":
    unittest.main()
