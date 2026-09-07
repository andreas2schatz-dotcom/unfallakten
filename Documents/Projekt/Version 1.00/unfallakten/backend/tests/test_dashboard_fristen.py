r"""GET /dashboard/fristen -- echte Fristen aus Z:\RA\Kalender\GT.

Bis 2026-09-07 lieferte der Endpunkt ausgewaehlte Wiedervorlagen, die
faelschlich als Fristen gefuehrt wurden. Jetzt kommt er aus dem
RA-MICRO-Kalenderbaum; RA-MICRO wird nur noch fuer den Akten-Sachbearbeiter
befragt, und dessen Ausfall darf die Kachel nicht leeren.
"""
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-dashboard-fristen")

import datetime

import pytest

from backend.routers import dashboard_routes
from backend.services.fristen_gt import FristenQuelleNichtErreichbar


def _frist(**abweichend):
    satz = {
        "aktennummer":     "322/26",
        "frist_datum":     (datetime.date.today() + datetime.timedelta(days=1)).isoformat(),
        "frist_beginn":    "2026-09-03",
        "frist_art":       "Klageerwiderung",
        "bemerkung":       "",
        "sb":              "PK",
        "kurzbezeichnung": "Karic/DA Deutsche Allg.",
        "gerichts_az":     "AZ: 2-15 S 68/25",
        "ist_vorfrist":    False,
    }
    satz.update(abweichend)
    return satz


def _quelle(monkeypatch, fristen, akten=None):
    monkeypatch.setattr(dashboard_routes, "lade_fristen",
                        lambda von, bis: list(fristen))
    monkeypatch.setattr(dashboard_routes, "_akten_sachbearbeiter",
                        lambda nummern: dict(akten or {}))


class TestAufbereitung:

    def test_aktenzeichen_nutzt_den_akten_sachbearbeiter(self, monkeypatch):
        """Der SB im Fristsatz ist der, dem die Frist gehoert -- bei 5 von 178
        Fristen der letzten zwei Jahre ein anderer als der Akten-SB. Mit dem
        falschen Kuerzel liesse sich die Akte nicht oeffnen."""
        _quelle(monkeypatch, [_frist(sb="AS")],
                {"322/26": {"sb": "PK", "mandant": "Karic"}})
        (e,) = dashboard_routes._lade_fristen_aus_dem_kalender()
        assert e["az"] == "322/26PK"
        assert e["sb"] == "PK"
        assert e["mandant"] == "Karic"

    def test_ohne_ramicro_springt_der_frist_sb_ein(self, monkeypatch):
        """Die Fristen selbst stehen nicht in RA-MICRO. Faellt der SQL-Server
        aus, bleibt die Kachel benutzbar."""
        _quelle(monkeypatch, [_frist(sb="AS")], {})
        (e,) = dashboard_routes._lade_fristen_aus_dem_kalender()
        assert e["az"] == "322/26AS"
        assert e["mandant"] == ""

    def test_tage_bis_wird_berechnet(self, monkeypatch):
        heute = datetime.date.today()
        _quelle(monkeypatch, [
            _frist(frist_datum=heute.isoformat()),
            _frist(frist_datum=(heute - datetime.timedelta(days=3)).isoformat()),
            _frist(frist_datum=(heute + datetime.timedelta(days=2)).isoformat()),
        ])
        assert [e["tage_bis"] for e in
                dashboard_routes._lade_fristen_aus_dem_kalender()] == [0, -3, 2]

    def test_vorfrist_wird_durchgereicht(self, monkeypatch):
        _quelle(monkeypatch, [_frist(ist_vorfrist=True,
                                     frist_art="Vorfrist Replik")])
        (e,) = dashboard_routes._lade_fristen_aus_dem_kalender()
        assert e["ist_vorfrist"] is True
        assert e["frist_art"] == "Vorfrist Replik"

    def test_fenster_ist_14_tage_zurueck_und_3_werktage_voraus(self, monkeypatch):
        gefragt = {}

        def merken(von, bis):
            gefragt["von"], gefragt["bis"] = von, bis
            return []

        monkeypatch.setattr(dashboard_routes, "lade_fristen", merken)
        monkeypatch.setattr(dashboard_routes, "_akten_sachbearbeiter", lambda n: {})
        dashboard_routes._lade_fristen_aus_dem_kalender()

        heute = datetime.date.today()
        assert gefragt["von"] == heute - datetime.timedelta(days=14)
        assert gefragt["bis"] > heute


class TestQuelleNichtErreichbar:
    """Ausdrueckliche Anforderung RA Schatz: ein fehlender E-Akte-Mount muss
    immer sichtbar sein. Der Fehler darf NICHT zu einer leeren Liste werden."""

    def test_fehler_schlaegt_bis_zum_aufrufer_durch(self, monkeypatch):
        def wirft(von, bis):
            raise FristenQuelleNichtErreichbar("Fristenkalender nicht erreichbar: /mnt/eakte")

        monkeypatch.setattr(dashboard_routes, "lade_fristen", wirft)
        with pytest.raises(FristenQuelleNichtErreichbar):
            dashboard_routes._lade_fristen_aus_dem_kalender()

    def test_endpunkt_antwortet_mit_503(self, monkeypatch):
        def wirft():
            raise FristenQuelleNichtErreichbar("Fristenkalender nicht erreichbar: /mnt/eakte")

        monkeypatch.setattr(dashboard_routes, "_lade_fristen_aus_dem_kalender", wirft)

        from backend.app import erstelle_app
        app = erstelle_app({"TESTING": True})
        with app.test_request_context("/dashboard/fristen"):
            antwort = dashboard_routes.fristen.__wrapped__()
        rumpf = antwort[0] if isinstance(antwort, tuple) else antwort
        assert rumpf.status_code == 503
        daten = rumpf.get_json()
        assert daten["eintraege"] == []
        assert "E-Akte-Mount" in daten["fehler"]
