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
        assert g.text == "Akte schließen"
        assert g.aus_freitext is False
        assert g.art == "wiedervorlage"

    def test_none_text_faellt_auf_den_katalog_zurueck(self):
        assert loese_wv_grund(None, 12).text == "Mandant gemeldet?"

    def test_freitextcode_ohne_text_gibt_ohne_angabe(self):
        g = loese_wv_grund("", 63974)
        assert g.text == "ohne Angabe"
        assert g.art == "wiedervorlage"

    def test_unbekannter_katalogcode_nennt_die_nummer(self):
        """Die Maske fuellt 1..99 vollstaendig; 0 kann RA-MICRO nicht liefern
        und steht hier fuer jeden kuenftigen Ausreisser unterhalb 100."""
        g = loese_wv_grund("", 0)
        assert g.text == "Unbekannter Grund (0)"
        assert g.unbekannt is True
        assert g.art == "wiedervorlage"

    def test_kein_code_und_kein_text(self):
        g = loese_wv_grund(None, None)
        assert g.text == "ohne Angabe"
        assert g.code is None

    def test_code_als_string_wird_akzeptiert(self):
        assert loese_wv_grund("", "55").text == "Akte schließen"

    def test_unbrauchbarer_code_wird_wie_kein_code_behandelt(self):
        assert loese_wv_grund("", "abc").text == "ohne Angabe"


class TestKachelzuordnung:
    """Ersetzt _TERMIN_CODES / _FRIST_CODES / _WV_AUSSCHLUSS und die
    drei gleichlautenden SQL-Literale in dashboard_routes.py."""

    def test_keine_fristcodes(self):
        """Alle 99 Gruende der Maske sind Wiedervorlagen. Echte Fristen fuehrt
        RA-MICRO getrennt (Mas\\FRIV.MSK) und speichert sie in keiner der acht
        SQL-Datenbanken -- belegt am 07.09.2026 durch eine Testfrist zum
        31.12.2029, die in 119 Datumsspalten nicht auftauchte."""
        assert codes_fuer_art("frist") == ()

    def test_keine_termincodes(self):
        """Termine kommen aus raKalender.dbo.Events, nicht aus Wiedervorlagen."""
        assert codes_fuer_art("termin") == ()

    def test_ausschluss_ist_leer(self):
        assert codes_fuer_art("frist", "termin") == ()

    def test_sql_codeliste_ist_eine_kommaliste(self):
        assert sql_codeliste("wiedervorlage").startswith("1, 2, 3, 4, 5,")

    def test_unbekannte_art_wird_abgelehnt(self):
        with pytest.raises(ValueError):
            codes_fuer_art("quatsch")

    def test_sql_codeliste_ohne_arten_bricht_ab(self):
        """Ohne Treffer waere das Ergebnis eine leere IN () -- ein SQL-Fehler
        statt eines klaren Registry-Fehlers. Muss fail-loud sein."""
        with pytest.raises(RuntimeError, match="keine Codes"):
            sql_codeliste()

    def test_sql_codeliste_fuer_leere_art_bricht_ab(self):
        """Solange keine Frist-Codes bekannt sind, darf niemand daraus ein
        SQL-Fragment bauen -- die Aufrufer muessen vorher codes_fuer_art()
        pruefen und die Abfrage ganz weglassen."""
        with pytest.raises(RuntimeError, match="keine Codes"):
            sql_codeliste("frist")

    def test_stellungnahme_codes_folgen_der_bezeichnung(self):
        """Dieselbe Regel wie das LIKE '%nahme%' auf den Freitext."""
        assert stellungnahme_codes() == (11, 16, 99)


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


class TestKatalogStimmtMitRaMicro:
    r"""Die Bezeichnungen stammen aus Z:\RA\Mas\TextWV.msk und sind gegen
    die gedruckten Wiedervorlagenlisten (Z:\RA\Text\*wvsik.rtf) geprueft.

    Bis 2026-09-07 stand hier eine geratene Liste ("RA-Micro Handbuch /
    empirisch ermittelt"): von 41 tatsaechlich verwendeten Codes war genau
    einer richtig. Die Fristen-Kachel zeigte deshalb "Beschwerde" fuer
    "Akte schliessen" und "Klage" fuer "Akte RA vorlegen".
    """

    # Aus 81 Ausdruckzeilen ueber (Aktennummer, Datum) gegen
    # tblAktenWiedervorlagen gejoint -- 12 von 12 stimmen mit der Maske.
    BELEGT = {
        10: "Mandant gezahlt?",
        11: "Stellungnahme Mandant?",
        12: "Mandant gemeldet?",
        16: "Stellungnahme Gegner?",
        17: "Gegner gezahlt?",
        20: "ZV-Sachstand",
        23: "MB erlassen?",
        28: "Rate gezahlt?",
        32: "Ermittlungsakte da?",
        34: "Erneute EV möglich!",
        63: "Polizei gemeldet?",
        93: "Unterlagen da?",
    }

    def test_maske_fuehrt_99_plaetze(self):
        r = lade_wv_codes()
        assert sorted(r.codes) == list(range(1, 100))

    def test_empirisch_belegte_codes(self):
        for code, text in self.BELEGT.items():
            assert loese_wv_grund("", code).text == text, f"Code {code}"

    def test_frueher_falsch_angezeigte_fristen(self):
        """Die vier Codes, die in der Fristen-Kachel standen."""
        assert loese_wv_grund("", 21).text == "Akte RA vorlegen"
        assert loese_wv_grund("", 51).text == "Klage entwerfen"
        assert loese_wv_grund("", 55).text == "Akte schließen"
        assert loese_wv_grund("", 75).text == "Reaktion GVZ?"

    def test_freitextgrenze_liegt_bei_100(self):
        r"""Katalog 1..99, darueber laufende IDs aus Z:\RA\Pr\wvgrund
        (Satznummer + 100), fuer die RA-MICRO den Text mitliefert."""
        assert lade_wv_codes().freitext_ab == 100

    def test_alles_verifiziert(self):
        r = lade_wv_codes()
        assert [c for c, e in r.codes.items() if not e.get("verifiziert")] == []


class TestOffenerPlatz:
    """Leere Plaetze in der Maske bleiben moeglich (AllowEmptyRows=1) und
    duerfen keine erfundene Bezeichnung bekommen."""

    def test_offener_code_gilt_als_unbekannt(self, tmp_path, monkeypatch):
        p = tmp_path / "wv.yaml"
        p.write_text(textwrap.dedent("""
            freitext_ab: 100
            codes:
              61: {bezeichnung: "", art: wiedervorlage, verifiziert: true, offen: true}
            standard: {text_und_code_leer: "ohne Angabe", code_unbekannt: "Unbekannter Grund", art: wiedervorlage}
        """), encoding="utf-8")
        monkeypatch.setenv("WIEDERVORLAGE_CODES_REGISTRY_PFAD", str(p))
        lade_wv_codes(reload=True)

        g = loese_wv_grund("", 61)
        assert g.text == "Unbekannter Grund (61)"
        assert g.unbekannt is True


class TestGeneratorGuard:
    """Die YAML ist erzeugt, nicht gepflegt: sie muss zur Maske passen."""

    def test_yaml_passt_zur_maske(self):
        import os as _os
        import subprocess
        import sys as _sys

        maske = _os.path.join(_os.environ.get("EAKTE_BASE_PATH", ""),
                              "Mas", "TextWV.msk")
        if not _os.path.exists(maske):
            pytest.skip("RA-MICRO-Maske nicht erreichbar (E-Akte-Mount fehlt)")

        wurzel = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", ".."))
        erg = subprocess.run(
            [_sys.executable, _os.path.join(wurzel, "tools", "gen_wiedervorlage_codes.py"),
             "--pruefen"],
            capture_output=True, text=True)
        assert erg.returncode == 0, (
            "wiedervorlage_codes.yaml passt nicht mehr zu TextWV.msk -- "
            "py tools/gen_wiedervorlage_codes.py ausfuehren.\n" + erg.stderr)
