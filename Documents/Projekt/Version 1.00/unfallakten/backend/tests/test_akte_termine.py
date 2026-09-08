r"""GET /akten/<az>/termine -- Termine der Akte aus raKalender.dbo.Events.

Anders als die Dashboard-Kachel (heute + morgen, nur Anwaltskalender) zeigt die
Akte jeden Termin: auch vergangene und auch die aus nicht zugeordneten
Kalendern. Im Dashboard ist das Filtern richtig, in der Akte wuerde es Termine
verschlucken (Entscheidung RA Schatz, 2026-09-07).
"""
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-akte-termine")

import types
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from backend.ramicro.connector import RaMicroNichtAktiv
from backend.routers import termine_routes
from backend.services import termine_ramicro


HEUTE = date.today()


def tag(versatz, stunde=10, minute=0):
    return datetime.combine(HEUTE + timedelta(days=versatz),
                            datetime.min.time()).replace(hour=stunde, minute=minute)


def _event(**felder):
    """Eine Zeile aus raKalender.dbo.Events mit realistischen Vorgaben."""
    zeile = {
        "EventUid":             "00000000-0000-0000-0000-000000000001",
        "StartDateTime":        tag(3),
        "Subject":              None,
        "Summary":              "",
        "Location":             None,
        "Notes":                "",
        "Aktennummer":          "322/26",
        "Aktenkurzbezeichnung": "Karic/DA Deutsche Allg.",
        "IsGerichtstermin":     False,
        "GerichtName":          None,
        "CalendarName":         "RA.Schatz",
    }
    zeile.update(felder)
    return zeile


def _termin(**felder):
    """Ein bereits aufbereiteter Termin, wie ihn der Dienst liefert."""
    eintrag = {
        "az":              "322/26AS",
        "kurzbezeichnung": "Karic/DA Deutsche Allg.",
        "betreff":         "Karic/DA Deutsche Allg.",
        "termin_art":      "Mandantentermin",
        "termin_datum":    (HEUTE + timedelta(days=3)).isoformat(),
        "uhrzeit":         "10:00",
        "tage_bis":        3,
        "sb":              "AS",
        "ort":             "",
        "bemerkung":       "",
        "ist_gerichtstermin": False,
    }
    eintrag.update(felder)
    return eintrag


def _rufe_auf(monkeypatch, akte_az, termine=None, wirft=None):
    monkeypatch.setattr(termine_routes, "hole_akte_by_id",
                        lambda az: types.SimpleNamespace(aktenzeichen=akte_az)
                        if akte_az is not None else None)

    gefragt = {}

    def quelle(nummer):
        gefragt["nummer"] = nummer
        if wirft:
            raise wirft
        return list(termine or [])

    monkeypatch.setattr(termine_routes, "termine_der_akte", quelle)

    from backend.app import erstelle_app
    app = erstelle_app({"TESTING": True})
    with app.test_request_context("/akten/322-26/termine"):
        antwort = termine_routes.liste_termine.__wrapped__("322-26")
    rumpf, status = antwort if isinstance(antwort, tuple) else (antwort, 200)
    return status, rumpf.get_json(), gefragt


class TestAktenbezug:

    def test_fragt_die_nackte_aktennummer_ab(self, monkeypatch):
        """Der Kalendersatz fuehrt nur "322/26", das Aktenzeichen im System
        kann ein Sachbearbeiterkuerzel tragen."""
        _, _, gefragt = _rufe_auf(monkeypatch, "322/26AS", [_termin()])
        assert gefragt["nummer"] == "322/26"

    def test_akte_ohne_termine(self, monkeypatch):
        _, daten, _ = _rufe_auf(monkeypatch, "999/26", [])
        assert daten == {"termine": [], "anzahl": 0}

    def test_unbekannte_akte_gibt_404(self, monkeypatch):
        status, daten, _ = _rufe_auf(monkeypatch, None)
        assert status == 404
        assert "nicht gefunden" in daten["fehler"]

    def test_aktenzeichen_ohne_nummer_fragt_die_quelle_nicht(self, monkeypatch):
        _, daten, gefragt = _rufe_auf(monkeypatch, "Sammelakte",
                                      wirft=RaMicroNichtAktiv("aus"))
        assert daten == {"termine": [], "anzahl": 0}
        assert gefragt == {}


class TestReihenfolge:
    """Wie bei den Fristen: erst was noch ansteht, dann das Gewesene mit dem
    juengsten oben. Rein nach Datum stuende der naechste Termin ganz unten."""

    def test_kommendes_zuerst_dann_vergangenes_juengstes_oben(self, monkeypatch):
        _, daten, _ = _rufe_auf(monkeypatch, "70/24", [
            _termin(termin_art="Ortstermin alt", tage_bis=-400),
            _termin(termin_art="Verhandlung", tage_bis=21),
            _termin(termin_art="Guetetermin gewesen", tage_bis=-12),
            _termin(termin_art="Mandantengespraech", tage_bis=2),
        ])
        assert [t["termin_art"] for t in daten["termine"]] == [
            "Mandantengespraech",   # in 2 Tagen
            "Verhandlung",          # in 21 Tagen
            "Guetetermin gewesen",  # vor 12 Tagen
            "Ortstermin alt",       # vor 400 Tagen
        ]

    def test_heutige_termine_stehen_nach_uhrzeit(self, monkeypatch):
        _, daten, _ = _rufe_auf(monkeypatch, "70/24", [
            _termin(termin_art="nachmittags", tage_bis=0, uhrzeit="15:30"),
            _termin(termin_art="frueh",       tage_bis=0, uhrzeit="08:45"),
        ])
        assert [t["termin_art"] for t in daten["termine"]] == ["frueh", "nachmittags"]


class TestQuelleNichtErreichbar:
    """Ein RA-MICRO-Ausfall darf nicht wie "keine Termine" aussehen -- dieselbe
    Regel wie beim fehlenden E-Akte-Mount in der Fristenliste."""

    def test_antwortet_mit_503_statt_leerer_liste(self, monkeypatch):
        status, daten, _ = _rufe_auf(monkeypatch, "322/26",
                                     wirft=RaMicroNichtAktiv("Dienst aus"))
        assert status == 503
        assert daten["termine"] == []
        assert "RA-MICRO" in daten["fehler"]


# ══════════════════════════════════════════════════════════════
#  Der Dienst: eine Events-Zeile wird zu einem Termin
# ══════════════════════════════════════════════════════════════

def _mock_verbindung(zeilen):
    cur = MagicMock()
    cur.fetchall.return_value = list(zeilen)
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = None
    return conn, cur


def _lade(zeilen, nummer="322/26"):
    conn, cur = _mock_verbindung(zeilen)
    with patch.object(termine_ramicro, "get_ramicro_connection", return_value=conn):
        return termine_ramicro.termine_der_akte(nummer), cur


class TestDienstAkte:

    def test_fragt_nur_diese_akte_ab(self):
        _, cur = _lade([_event()])
        sql, parameter = cur.execute.call_args[0]
        assert "Aktennummer" in sql
        assert parameter["nummer"] == "322/26"

    def test_geloeschte_termine_bleiben_draussen(self):
        _, cur = _lade([_event()])
        sql = cur.execute.call_args[0][0]
        assert "IsDeleted = 0" in sql

    def test_ohne_datumsfenster(self):
        """In der Akte zaehlt Vollstaendigkeit -- der vergangene Gerichtstermin
        gehoert zur Geschichte des Falls."""
        sql = _lade([_event()])[1].execute.call_args[0][0]
        assert "BETWEEN" not in sql.upper()

    def test_nicht_zugeordneter_kalender_liefert_den_termin_trotzdem(self):
        """Im Dashboard richtig gefiltert -- in der Akte wuerde es Termine
        verschlucken."""
        termine, _ = _lade([_event(CalendarName="ReferendarIn",
                                   Summary="Akteneinsicht")])
        assert len(termine) == 1
        assert termine[0]["sb"] == ""

    def test_zugeordneter_kalender_liefert_das_kuerzel(self):
        termine, _ = _lade([_event(CalendarName="RA.Schatz")])
        assert termine[0]["sb"] == "AS"

    def test_datum_uhrzeit_und_tage_bis(self):
        termine, _ = _lade([_event(StartDateTime=tag(5, 9, 30))])
        (t,) = termine
        assert t["termin_datum"] == (HEUTE + timedelta(days=5)).isoformat()
        assert t["uhrzeit"] == "09:30"
        assert t["tage_bis"] == 5

    def test_vergangener_termin_hat_negative_tage(self):
        termine, _ = _lade([_event(StartDateTime=tag(-30))])
        assert termine[0]["tage_bis"] == -30

    def test_ort_notiz_und_terminart_wie_im_dashboard(self):
        termine, _ = _lade([_event(
            IsGerichtstermin=True,
            Subject="HV",
            Location="AG Offenbach, Raum 218",
            Notes="Mdt. laedt selbst\r\nTel. 069 123456",
        )])
        (t,) = termine
        assert t["termin_art"] == "HV"
        assert t["ist_gerichtstermin"] is True
        assert t["ort"] == "AG Offenbach, Raum 218"
        assert t["bemerkung"] == "Mdt. laedt selbst · Tel. 069 123456"

    def test_betreff_kommt_aus_summary_ohne_vorangestellte_aktennummer(self):
        termine, _ = _lade([_event(Aktenkurzbezeichnung="",
                                   Summary="322/26 Karic/DA Deutsche Allg.")])
        assert termine[0]["betreff"] == "Karic/DA Deutsche Allg."

    def test_dieselbe_eventuid_erscheint_nur_einmal(self):
        zeile = _event()
        termine, _ = _lade([zeile, dict(zeile)])
        assert len(termine) == 1


class TestRegistrierung:
    """Ohne Blueprint-Registrierung laeuft die Route nur im Test."""

    def test_route_haengt_in_der_app(self):
        from backend.app import erstelle_app
        app = erstelle_app({"TESTING": True})
        regeln = {str(r) for r in app.url_map.iter_rules()}
        assert "/akten/<path:akte_id>/termine" in regeln


class TestAktennummerMitAuffuellung:
    """RA-MICRO-Textfelder tragen haeufig Leerzeichen -- ein Vergleich auf
    Gleichheit wuerde die Akte dann stillschweigend leer zeigen."""

    def test_vergleich_trimmt_die_aktennummer(self):
        sql = _lade([_event()])[1].execute.call_args[0][0]
        assert "LTRIM(RTRIM(e.Aktennummer))" in sql
