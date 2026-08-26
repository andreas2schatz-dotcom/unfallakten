"""
Zahlungen auf den Fahrzeugschaden erreichen den Abschlussbericht.

Befund RA Schatz (2026-08-26): Eine in der Regulierung erfasste oder
geaenderte Zahlung taucht im Abschluss-/Sachstandsbericht nicht auf.

Ursache: ``_normalise_key`` liess ``fahrzeugschaden`` bewusst roh stehen
("Ziel-Key haengt von der Abrechnungsart ab und kann hier ohne Kontext
nicht aufgeloest werden") und kannte ``reparaturkosten`` gar nicht --
``_schadenpositionen_rows`` baut die Fahrzeugzeile aber unter
``rep_gutachten_netto`` / ``rep_rechnung_netto`` / ``wiederbeschaffung``.
Der Nachschlag ging ins Leere, die Zahlung verschwand lautlos.

Die Regulierungs-Tabelle fuehrt alle Fahrzeug-Keys dagegen auf eine Zeile
zusammen -- daher zeigte sie die Zahlung, der Bericht nicht.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Akte 589/26: fiktive Abrechnung, Reparatur 4.882,48 unter WBW 13.500
_SCHADEN_FIKTIV = {
    "abrechnungsart":      "fiktiv",
    "rep_gutachten_netto": 4882.48,
    "wiederbeschaffung":   13500.0,
    "wertminderung":       150.0,
    "nutzungsausfall":     172.0,
    "sv_kosten":           992.34,
    "unkostenpauschale":   30.0,
}

_SCHADEN_TOTAL = {
    "abrechnungsart":      "totalschaden",
    "rep_gutachten_netto": 14000.0,
    "wiederbeschaffung":   13500.0,
    "restwert":            3000.0,
    "unkostenpauschale":   30.0,
}

_SCHADEN_KONKRET = {
    "abrechnungsart":      "konkret",
    "rep_rechnung_netto":  4200.0,
    "rep_rechnung_brutto": 4998.0,
    "unkostenpauschale":   30.0,
}


def _abrechnung(position_key, betrag, gefordert=4882.48):
    return [{
        "datum": "2026-06-30", "versicherung": "AXA", "quelle": "pdf",
        "gesamt_gefordert": gefordert, "gesamt_reguliert": betrag,
        "gesamt_kuerzung": round(gefordert - betrag, 2),
        "positionen": [{"position_key": position_key,
                        "betrag_gefordert": gefordert,
                        "betrag_reguliert": betrag}],
    }]


def _gezahlt_je_key(schaden, abrechnungen, vorsteuer=False):
    from backend.services.abschluss_uebersicht import baue_abschluss_uebersicht
    ueb = baue_abschluss_uebersicht({
        "akte": {"az": "589/26"}, "mandant": {}, "gegner": {},
        "schaden": schaden, "abrechnungen": abrechnungen,
    })
    return ({p["key"]: p["gezahlt"] for p in ueb["positionen"]},
            ueb["summen"])


class TestFahrzeugschadenKeys(unittest.TestCase):

    def test_fiktiv_nimmt_zahlung_von_jedem_fahrzeug_key_an(self):
        # So bucht der Abrechnungs-Vorschlag ("fiktive Abrechnung"), so das
        # Gutachten-Ereignis ("reparaturkosten"), so der PDF-Parser
        # ("reparatur_netto") und so der Schaden-Tab selbst.
        for key in ("fahrzeugschaden", "reparaturkosten", "reparatur_netto",
                    "rep_gutachten_netto"):
            with self.subTest(position_key=key):
                gezahlt, summen = _gezahlt_je_key(
                    _SCHADEN_FIKTIV, _abrechnung(key, 2697.19))
                self.assertEqual(gezahlt["rep_gutachten_netto"], 2697.19)
                self.assertEqual(summen["gezahlt"], 2697.19)

    def test_totalschaden_fuehrt_auf_die_wiederbeschaffungszeile(self):
        for key in ("fahrzeugschaden", "reparaturkosten", "wbw",
                    "wiederbeschaffung"):
            with self.subTest(position_key=key):
                gezahlt, _ = _gezahlt_je_key(
                    _SCHADEN_TOTAL, _abrechnung(key, 9000.0, gefordert=10500.0))
                self.assertEqual(gezahlt["wiederbeschaffung"], 9000.0)

    def test_restwert_bleibt_eine_eigene_abzugszeile(self):
        gezahlt, _ = _gezahlt_je_key(
            _SCHADEN_TOTAL, _abrechnung("wiederbeschaffung", 9000.0,
                                        gefordert=10500.0))
        self.assertIn("restwert", gezahlt)
        self.assertIsNone(gezahlt["restwert"])

    def test_konkret_fuehrt_auf_die_rechnungszeile(self):
        for key in ("fahrzeugschaden", "reparaturkosten", "rep_rechnung_netto"):
            with self.subTest(position_key=key):
                gezahlt, _ = _gezahlt_je_key(
                    _SCHADEN_KONKRET,
                    _abrechnung(key, 4000.0, gefordert=4998.0))
                self.assertEqual(gezahlt["rep_rechnung_netto"], 4000.0)

    def test_nebenpositionen_bleiben_unveraendert(self):
        gezahlt, _ = _gezahlt_je_key(
            _SCHADEN_FIKTIV, _abrechnung("kostenpauschale", 25.0, gefordert=30.0))
        self.assertEqual(gezahlt["unkostenpauschale"], 25.0)

    def test_manuelle_korrektur_schlaegt_im_bericht_durch(self):
        """Der Kern des Befunds: geaenderter Betrag = Betrag im Bericht."""
        gezahlt, summen = _gezahlt_je_key(
            _SCHADEN_FIKTIV, _abrechnung("fahrzeugschaden", 2697.19))
        self.assertEqual(gezahlt["rep_gutachten_netto"], 2697.19)
        korrigiert, summen2 = _gezahlt_je_key(
            _SCHADEN_FIKTIV, _abrechnung("fahrzeugschaden", 3100.0))
        self.assertEqual(korrigiert["rep_gutachten_netto"], 3100.0)
        self.assertEqual(summen2["gezahlt"], 3100.0)


class TestZahlungOhneForderung(unittest.TestCase):
    """Eine Zahlung darf nie unterschlagen werden.

    Akte 589/26: die Reparaturbestaetigung ist im Schaden-Tab unter
    ``sonstiges`` gefordert, die Zahlung wurde aber auf ``kostennb``
    gebucht. Ohne eigene Zeile fiel der Betrag aus der Berichtssumme --
    die Uebersicht zeigte ihn, der Bericht nicht.
    """

    def test_position_ohne_forderung_erscheint_mit_zahlung(self):
        gezahlt, summen = _gezahlt_je_key(
            _SCHADEN_FIKTIV, _abrechnung("kostennb", 29.75, gefordert=0.0))
        self.assertEqual(gezahlt["kostennb"], 29.75)
        self.assertEqual(summen["gezahlt"], 29.75)

    def test_position_ohne_forderung_und_ohne_zahlung_bleibt_weg(self):
        gezahlt, _ = _gezahlt_je_key(_SCHADEN_FIKTIV, [])
        self.assertNotIn("kostennb", gezahlt)


class TestAbrechnungsuebersichtGleichzieht(unittest.TestCase):
    """Die Word-Abrechnungsuebersicht nutzt dieselbe Normalisierung."""

    def test_pos_map_loest_fahrzeugschaden_auf(self):
        from backend.word.abrechnungsuebersicht_service import (
            _baue_pos_map, _fahrzeug_zielkey)
        zielkey = _fahrzeug_zielkey(_SCHADEN_FIKTIV, vorsteuer=False)
        self.assertEqual(zielkey, "rep_gutachten_netto")
        pos_map = _baue_pos_map(_abrechnung("fahrzeugschaden", 2697.19),
                                fahrzeug_zielkey=zielkey)
        self.assertEqual(pos_map["rep_gutachten_netto"]["reguliert"], 2697.19)


if __name__ == "__main__":
    unittest.main()
