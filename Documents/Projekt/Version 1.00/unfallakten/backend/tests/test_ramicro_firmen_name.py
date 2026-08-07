"""
Firmen-Namen aus RA-MICRO-Adressen (Befund Akte 1280/25).

RA-MICRO speichert den Namen (auch Firmennamen) IMMER in sNachname.
sErsteAdresszeile ist nur die Anredeform des Adressfelds
("Herrn", "Frau", "Firma", "Anwaltskanzlei", "c/o ...", "Inhaber ...")
und darf nie den echten Namen verdrängen.
"""

import uuid
from unittest import mock

import pytest

from backend.word.word_service import (
    name_aus_ramicro_adresse,
    _lade_beteiligte_aus_ramicro,
)


class TestNameAusRamicroAdresse:
    def test_firma_name_aus_nachname(self):
        assert name_aus_ramicro_adresse("RCR GmbH", "Firma") == "RCR GmbH"

    def test_person_name_aus_nachname(self):
        assert name_aus_ramicro_adresse("Petrovic", "Frau") == "Petrovic"

    def test_fallback_erste_zeile_wenn_nachname_leer(self):
        assert name_aus_ramicro_adresse("", "HUK-COBURG Versicherungsgruppe") \
            == "HUK-COBURG Versicherungsgruppe"

    def test_leere_eingaben(self):
        assert name_aus_ramicro_adresse(None, None) == ""
        assert name_aus_ramicro_adresse("  ", " Firma ") == "Firma"


class _FakeCursor:
    """Liefert pro execute() das nächste vorbereitete Ergebnis."""

    def __init__(self, ergebnisse):
        self._ergebnisse = list(ergebnisse)
        self._aktuell = None

    def execute(self, sql, params=None):
        self._aktuell = self._ergebnisse.pop(0)

    def fetchone(self):
        return self._aktuell[0] if self._aktuell else None

    def fetchall(self):
        return self._aktuell or []


def _fake_connection(ergebnisse):
    cur = _FakeCursor(ergebnisse)
    conn = mock.MagicMock()
    conn.cursor.return_value = cur
    ctx = mock.MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = False
    return ctx


AKTE_1280 = {"az_roh": "1280/25", "GUIDAkte": uuid.uuid4()}

MANDANTIN = {
    "art": 1, "kz": "", "iAdressnummer": 33412,
    "sErsteAdresszeile": "Frau", "sNachname": "Petrovic",
    "sVorname": "Anita", "sAnrede": "2",
    "sBriefanrede": "Sehr geehrte Frau Petrovic,",
    "sStrasse": "", "sPLZ": "63165", "sOrt": "Mühlheim",
    "sTelefon": "", "sTelefax": "", "sEMail": "",
    "sBetreffZeile1": "", "sBetreffZeile2": "", "sBetreffZeile3": "",
    "bVorsteuerabzugsberechtigt": 0,
}

GEGNERIN_FIRMA = {
    "art": 2, "kz": "", "iAdressnummer": 33413,
    "sErsteAdresszeile": "Firma", "sNachname": "RCR GmbH",
    "sVorname": "", "sAnrede": "4",
    "sBriefanrede": "Sehr geehrte Damen und Herren,",
    "sStrasse": "", "sPLZ": "", "sOrt": "Offenbach",
    "sTelefon": "", "sTelefax": "", "sEMail": "",
    "sBetreffZeile1": "", "sBetreffZeile2": "", "sBetreffZeile3": "",
    "bVorsteuerabzugsberechtigt": 0,
}


class TestLadeBeteiligteFirma:
    def test_firma_gegner_bekommt_nachnamen_nicht_anredeform(self):
        ctx = _fake_connection([
            [AKTE_1280],                    # tblAkten
            [MANDANTIN, GEGNERIN_FIRMA],    # tblAktenBeteiligte
            [],                             # WDM
        ])
        with mock.patch("backend.ramicro.connector.get_ramicro_connection",
                        return_value=ctx):
            result = _lade_beteiligte_aus_ramicro("1280/25")

        assert result["mandant"]["name"] == "Petrovic"
        assert result["mandant"]["anrede"] == "Frau"
        assert result["gegner"] is not None
        assert result["gegner"]["name"] == "RCR GmbH"
        assert result["gegner"]["anrede"] == "Firma"
