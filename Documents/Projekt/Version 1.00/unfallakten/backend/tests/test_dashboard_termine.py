"""
Tests für die Termine-Kachel der Tagesübersicht (_lade_termine_heute).

Hintergrund: RA-MICRO füllt in raKalender.dbo.Events fast nie ``Subject``.
Der lesbare Termintext steht in ``Summary``, Gericht/Saal in ``Location``,
Telefonnummern und Zusätze in ``Notes``.
"""

import importlib
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

_tmp_dir = tempfile.mkdtemp()


def _setup(test_id: str):
    """Frische DB + Flask-App (Muster: test_sachbearbeiter._setup)."""
    db_path = os.path.join(_tmp_dir, f"term_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters!!"
    os.environ["FLASK_SECRET_KEY"] = "test-flask-secret-key-minimum-32-characters!!"

    import backend.db.database as db_mod
    import backend.db.schema_manager as schema_mod
    import backend.ramicro.sachbearbeiter as sb_mod
    import backend.routers.dashboard_routes as dash_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as auth_routes_mod
    import backend.app as app_mod

    for m in (db_mod, schema_mod, sb_mod, dash_mod, jwt_mod, mw_mod,
              svc_mod, auth_routes_mod, app_mod):
        importlib.reload(m)

    app_mod.erstelle_app({"TESTING": True})
    return dash_mod


def _event(**felder):
    """Eine Zeile aus raKalender.dbo.Events mit realistischen Vorgaben."""
    zeile = {
        "EventUid":             "00000000-0000-0000-0000-000000000001",
        "StartDateTime":        datetime.now().replace(hour=10, minute=0, second=0, microsecond=0),
        "Subject":              None,
        "Summary":              "",
        "Location":             None,
        "Notes":                "",
        "Aktennummer":          "",
        "Aktenkurzbezeichnung": "",
        "IsGerichtstermin":     False,
        "GerichtName":          None,
        "CalendarName":         "RA.Schatz",
    }
    zeile.update(felder)
    return zeile


def _mock_verbindung(kalender_zeilen, wv_zeilen=()):
    """RA-MICRO-Verbindung, die je Abfrage eine eigene Ergebnismenge liefert."""
    cur = MagicMock()
    cur.fetchall.side_effect = [list(kalender_zeilen), list(wv_zeilen)]
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = None
    return conn


class TestTerminText(unittest.TestCase):
    """Der Termintext muss aus Summary kommen, nicht aus dem leeren Subject."""

    def setUp(self):
        self.dash = _setup(self._testMethodName)

    def _laden(self, zeilen, wv_zeilen=()):
        conn = _mock_verbindung(zeilen, wv_zeilen)
        with patch.object(self.dash, "get_ramicro_connection", return_value=conn):
            return self.dash._lade_termine_heute()

    def test_betreff_kommt_aus_summary_wenn_subject_leer_ist(self):
        eintraege = self._laden([_event(Subject="", Summary="Herr Kirto Pektas")])

        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["betreff"], "Herr Kirto Pektas")

    def test_terminart_bleibt_leer_ohne_akte_und_ohne_subject(self):
        """Ohne Akte ist "Mandantentermin" geraten - z.B. bei einem Lehrgang."""
        eintraege = self._laden([_event(Summary="Fachanwaltslehrgang")])

        self.assertEqual(eintraege[0]["termin_art"], "")

    def test_betreff_ist_die_aktenkurzbezeichnung_bei_aktentermin(self):
        eintraege = self._laden([_event(
            Aktennummer="696/26",
            Aktenkurzbezeichnung="Kokott/Ahmad",
            Summary="696/26 Kokott/Ahmad",
        )])

        self.assertEqual(eintraege[0]["betreff"], "Kokott/Ahmad")
        self.assertEqual(eintraege[0]["termin_art"], "Mandantentermin")

    def test_aktennummer_wird_dem_summary_betreff_nicht_vorangestellt(self):
        """Summary trägt oft das AZ als Präfix - das steht schon in der Meta-Zeile."""
        eintraege = self._laden([_event(
            Aktennummer="1218/25",
            Aktenkurzbezeichnung="",
            Summary="1218/25 Plajer/Unbekannt",
        )])

        self.assertEqual(eintraege[0]["betreff"], "Plajer/Unbekannt")

    def test_gerichtstermin_nutzt_subject_als_terminart(self):
        eintraege = self._laden([_event(
            IsGerichtstermin=True,
            Subject="HV",
            Aktennummer="618/26",
            Aktenkurzbezeichnung="Keita/Ermittlungsverfahren",
            Summary="618/26 Keita/Ermittlungsverfahren HV",
        )])

        self.assertEqual(eintraege[0]["termin_art"], "HV")
        self.assertEqual(eintraege[0]["betreff"], "Keita/Ermittlungsverfahren")

    def test_gerichtstermin_ohne_subject_heisst_verhandlungstermin(self):
        eintraege = self._laden([_event(
            IsGerichtstermin=True,
            Aktennummer="153/22",
            Aktenkurzbezeichnung="Lossen/Unbekannt",
        )])

        self.assertEqual(eintraege[0]["termin_art"], "Verhandlungstermin")


class TestTerminZusatzinfos(unittest.TestCase):
    """Ort und Notiz gingen bisher komplett verloren."""

    def setUp(self):
        self.dash = _setup(self._testMethodName)

    def _laden(self, zeilen, wv_zeilen=()):
        conn = _mock_verbindung(zeilen, wv_zeilen)
        with patch.object(self.dash, "get_ramicro_connection", return_value=conn):
            return self.dash._lade_termine_heute()

    def test_ort_kommt_aus_location(self):
        eintraege = self._laden([_event(
            IsGerichtstermin=True,
            Location="AG Dieburg, Bei der Erlesmühle 1, 64807 Dieburg, Raum 110",
            GerichtName="AG Dieburg",
        )])

        self.assertEqual(eintraege[0]["ort"],
                         "AG Dieburg, Bei der Erlesmühle 1, 64807 Dieburg, Raum 110")

    def test_gerichtname_ist_der_ort_fallback(self):
        eintraege = self._laden([_event(
            IsGerichtstermin=True, Location="", GerichtName="AG Offenbach am Main")])

        self.assertEqual(eintraege[0]["ort"], "AG Offenbach am Main")

    def test_notes_werden_zur_bemerkung(self):
        eintraege = self._laden([_event(Summary="Herr Ranjbar", Notes="0151/56355142")])

        self.assertEqual(eintraege[0]["bemerkung"], "0151/56355142")

    def test_mehrzeilige_notes_werden_einzeilig(self):
        eintraege = self._laden([_event(
            Summary="Frau Rotter",
            Notes="01726867604\r\nAkte von Frau Heidenreich",
        )])

        self.assertEqual(eintraege[0]["bemerkung"],
                         "01726867604 · Akte von Frau Heidenreich")


class TestKalenderAuswahl(unittest.TestCase):
    """Nur Kalender, die einem Sachbearbeiter zugeordnet sind (die Anwälte)."""

    def setUp(self):
        self.dash = _setup(self._testMethodName)

    def _laden(self, zeilen, wv_zeilen=()):
        conn = _mock_verbindung(zeilen, wv_zeilen)
        with patch.object(self.dash, "get_ramicro_connection", return_value=conn):
            return self.dash._lade_termine_heute()

    def test_nicht_zugeordneter_kalender_liefert_keinen_termin(self):
        eintraege = self._laden([_event(
            CalendarName="ReferendarIn", Summary="Bibliothek", Aktennummer="1/26")])

        self.assertEqual(eintraege, [])

    def test_zugeordneter_kalender_liefert_das_kuerzel(self):
        eintraege = self._laden([_event(CalendarName="RA.Schatz", Aktennummer="288/26")])

        self.assertEqual(eintraege[0]["sb"], "AS")
        self.assertEqual(eintraege[0]["az"], "288/26AS")


class TestTerminDedup(unittest.TestCase):
    """Zwei echte Termine dürfen nicht auf einen zusammenfallen."""

    def setUp(self):
        self.dash = _setup(self._testMethodName)

    def _laden(self, zeilen, wv_zeilen=()):
        conn = _mock_verbindung(zeilen, wv_zeilen)
        with patch.object(self.dash, "get_ramicro_connection", return_value=conn):
            return self.dash._lade_termine_heute()

    def test_zwei_aktenlose_termine_zur_gleichen_zeit_bleiben_erhalten(self):
        gleich = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        eintraege = self._laden([
            _event(EventUid="aaaaaaaa-0000-0000-0000-000000000001",
                   StartDateTime=gleich, Summary="Herr Adbahi"),
            _event(EventUid="bbbbbbbb-0000-0000-0000-000000000002",
                   StartDateTime=gleich, Summary="Frau Nouri"),
        ])

        self.assertEqual([e["betreff"] for e in eintraege], ["Herr Adbahi", "Frau Nouri"])

    def test_dieselbe_eventuid_erscheint_nur_einmal(self):
        zeile = _event(Summary="Herr Pektas")
        eintraege = self._laden([zeile, dict(zeile)])

        self.assertEqual(len(eintraege), 1)


if __name__ == "__main__":
    unittest.main()
