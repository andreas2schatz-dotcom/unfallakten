import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-wv-codes")

import textwrap

import pytest

from backend.services.wiedervorlage_code_registry import (
    codes_fuer_art,
    lade_wv_codes,
    loese_wv_grund,
    sql_codeliste,
    stellungnahme_codes,
)


class TestAufloesung:
    """Der Freitext ist die massgebliche Quelle, die Nummer nur der Notnagel."""

    def test_freitext_schlaegt_den_katalog(self):
        g = loese_wv_grund("Gegner gemeldet / gezahlt?", 63915)
        assert g.text == "Gegner gemeldet / gezahlt?"
        assert g.aus_freitext is True
        assert g.unbekannt is False

    def test_freitext_wird_nicht_gedeutet(self):
        g = loese_wv_grund("  Klage fertigen!  ", 63944)
        assert g.text == "Klage fertigen!"
        assert g.art == "wiedervorlage"

    def test_leerer_text_faellt_auf_den_katalog_zurueck(self):
        g = loese_wv_grund("", 55)
        assert g.text == "Beschwerde"
        assert g.aus_freitext is False
        assert g.art == "frist"

    def test_none_text_faellt_auf_den_katalog_zurueck(self):
        assert loese_wv_grund(None, 12).text == "Zahlung Gegner"

    def test_freitextcode_ohne_text_gibt_ohne_angabe(self):
        g = loese_wv_grund("", 63974)
        assert g.text == "ohne Angabe"
        assert g.art == "wiedervorlage"

    def test_unbekannter_katalogcode_nennt_die_nummer(self):
        g = loese_wv_grund("", 47)
        assert g.text == "Unbekannter Grund (47)"
        assert g.unbekannt is True
        assert g.art == "wiedervorlage"

    def test_offener_code_gilt_als_unbekannt(self):
        g = loese_wv_grund("", 61)
        assert g.text == "Unbekannter Grund (61)"
        assert g.unbekannt is True

    def test_kein_code_und_kein_text(self):
        g = loese_wv_grund(None, None)
        assert g.text == "ohne Angabe"
        assert g.code is None

    def test_code_als_string_wird_akzeptiert(self):
        assert loese_wv_grund("", "55").text == "Beschwerde"

    def test_unbrauchbarer_code_wird_wie_kein_code_behandelt(self):
        assert loese_wv_grund("", "abc").text == "ohne Angabe"


class TestKachelzuordnung:
    """Ersetzt _TERMIN_CODES / _FRIST_CODES / _WV_AUSSCHLUSS und die
    drei gleichlautenden SQL-Literale in dashboard_routes.py."""

    def test_fristcodes_unveraendert(self):
        assert codes_fuer_art("frist") == (21, 22, 31, 46, 51, 55, 75)

    def test_termincodes_unveraendert(self):
        assert codes_fuer_art("termin") == (9, 58, 60)

    def test_ausschluss_ist_die_vereinigung(self):
        assert codes_fuer_art("frist", "termin") == (
            9, 21, 22, 31, 46, 51, 55, 58, 60, 75)

    def test_sql_codeliste_ist_eine_kommaliste(self):
        assert sql_codeliste("termin") == "9, 58, 60"

    def test_unbekannte_art_wird_abgelehnt(self):
        with pytest.raises(ValueError):
            codes_fuer_art("quatsch")

    def test_stellungnahme_codes_unveraendert(self):
        assert stellungnahme_codes() == (5, 6, 11, 16)


class TestFailLoud:
    """Registries brechen bei fehlerhaften Eintraegen hart ab."""

    def _schreibe(self, tmp_path, inhalt):
        p = tmp_path / "wv.yaml"
        p.write_text(textwrap.dedent(inhalt), encoding="utf-8")
        return str(p)

    def test_unbekannte_art(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              5: {bezeichnung: "X", art: quatsch, verifiziert: false}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="art"):
            lade_wv_codes(p, reload=True)

    def test_leere_bezeichnung_ohne_offen(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              5: {bezeichnung: "", art: wiedervorlage, verifiziert: false}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="bezeichnung"):
            lade_wv_codes(p, reload=True)

    def test_fehlendes_verifiziert(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              5: {bezeichnung: "X", art: wiedervorlage}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="verifiziert"):
            lade_wv_codes(p, reload=True)

    def test_code_im_freitextbereich(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              63912: {bezeichnung: "X", art: wiedervorlage, verifiziert: false}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="freitext_ab"):
            lade_wv_codes(p, reload=True)

    def test_leere_registry(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes: {}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="leer"):
            lade_wv_codes(p, reload=True)

    def test_datei_fehlt(self, tmp_path):
        with pytest.raises(RuntimeError, match="nicht lesbar"):
            lade_wv_codes(str(tmp_path / "gibtsnicht.yaml"), reload=True)


class TestPruefstand:
    """Dokumentiert den offenen Verifikationsstand, ohne ihn zu erzwingen."""

    def test_jeder_eintrag_traegt_ein_verifiziert_flag(self):
        r = lade_wv_codes()
        fehlend = [c for c, e in r.codes.items() if "verifiziert" not in e]
        assert fehlend == []

    def test_verifizierte_eintraege_haben_eine_bezeichnung(self):
        r = lade_wv_codes()
        leer = [c for c, e in r.codes.items()
                if e.get("verifiziert") and not e.get("bezeichnung")]
        assert leer == []
