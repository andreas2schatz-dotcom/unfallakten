r"""GET /akten/<az>/fristen -- Fristen der Akte aus Z:\RA\Kalender\GT.

Anders als die Dashboard-Kachel zeigt die Akte jede unerledigte Frist, auch
jahrealte: dort zaehlt Vollstaendigkeit mehr als Ruhe (Entscheidung RA Schatz,
2026-09-07).
"""
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-akte-fristen")

import types

import pytest

from backend.routers import fristen_routes
from backend.services.fristen_gt import FristenQuelleNichtErreichbar


def _frist(aktennummer, frist_datum, **abweichend):
    satz = {
        "aktennummer":     aktennummer,
        "frist_datum":     frist_datum,
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


def _rufe_auf(monkeypatch, akte_az, fristen=None, wirft=False):
    monkeypatch.setattr(fristen_routes, "hole_akte_by_id",
                        lambda az: types.SimpleNamespace(aktenzeichen=akte_az)
                        if akte_az is not None else None)

    def quelle():
        if wirft:
            raise FristenQuelleNichtErreichbar("Fristenkalender nicht erreichbar: /mnt/eakte")
        return list(fristen or [])

    monkeypatch.setattr(fristen_routes, "alle_offenen_fristen", quelle)

    from backend.app import erstelle_app
    app = erstelle_app({"TESTING": True})
    with app.test_request_context("/akten/322-26/fristen"):
        antwort = fristen_routes.liste_fristen.__wrapped__("322-26")
    rumpf, status = antwort if isinstance(antwort, tuple) else (antwort, 200)
    return status, rumpf.get_json()


class TestFilterAufDieAkte:

    def test_nur_die_fristen_dieser_akte(self, monkeypatch):
        status, daten = _rufe_auf(monkeypatch, "322/26", [
            _frist("322/26", "2026-09-07"),
            _frist("489/25", "2026-09-07"),
            _frist("322/26", "2026-09-20"),
        ])
        assert status == 200
        assert daten["anzahl"] == 2
        assert [f["frist_datum"] for f in daten["fristen"]] == \
            ["2026-09-07", "2026-09-20"]

    def test_sachbearbeiterkuerzel_im_aktenzeichen_stoert_nicht(self, monkeypatch):
        """Der Kalendersatz fuehrt nur die nackte Nummer."""
        _, daten = _rufe_auf(monkeypatch, "322/26PK", [_frist("322/26", "2026-09-07")])
        assert daten["anzahl"] == 1

    def test_alte_fristen_bleiben_sichtbar(self, monkeypatch):
        """In der Akte wird nicht nach Datum gefiltert -- eine seit 2019 offene
        Frist ist entweder nie abgehakt worden oder echt. Beides will man sehen."""
        _, daten = _rufe_auf(monkeypatch, "620/19", [_frist("620/19", "2019-11-04")])
        assert daten["anzahl"] == 1
        assert daten["fristen"][0]["tage_bis"] < 0

    def test_akte_ohne_fristen(self, monkeypatch):
        _, daten = _rufe_auf(monkeypatch, "999/26", [_frist("322/26", "2026-09-07")])
        assert daten == {"fristen": [], "anzahl": 0}

    def test_unbekannte_akte_gibt_404(self, monkeypatch):
        status, daten = _rufe_auf(monkeypatch, None)
        assert status == 404
        assert "nicht gefunden" in daten["fehler"]

    def test_aktenzeichen_ohne_nummer_fragt_die_quelle_nicht(self, monkeypatch):
        _, daten = _rufe_auf(monkeypatch, "Sammelakte", wirft=True)
        assert daten == {"fristen": [], "anzahl": 0}


class TestAufbereitung:

    def test_tage_bis_und_vorfrist(self, monkeypatch):
        import datetime
        heute = datetime.date.today()
        _, daten = _rufe_auf(monkeypatch, "322/26", [
            _frist("322/26", (heute + datetime.timedelta(days=4)).isoformat(),
                   ist_vorfrist=True, frist_art="Vorfrist Replik"),
        ])
        (f,) = daten["fristen"]
        assert f["tage_bis"] == 4
        assert f["ist_vorfrist"] is True
        assert f["frist_art"] == "Vorfrist Replik"

    def test_aktennummer_wird_nicht_mit_ausgeliefert(self, monkeypatch):
        """Sie steht schon im Aufrufpfad."""
        _, daten = _rufe_auf(monkeypatch, "322/26", [_frist("322/26", "2026-09-07")])
        assert "aktennummer" not in daten["fristen"][0]


class TestQuelleNichtErreichbar:
    """Ausdrueckliche Anforderung RA Schatz: ein fehlender E-Akte-Mount muss
    immer sichtbar sein -- auch in der Akte, nicht nur im Dashboard."""

    def test_antwortet_mit_503_statt_leerer_liste(self, monkeypatch):
        status, daten = _rufe_auf(monkeypatch, "322/26", wirft=True)
        assert status == 503
        assert daten["fristen"] == []
        assert "E-Akte-Mount" in daten["fehler"]


class TestReihenfolge:
    """Akten mit langer Historie fuehren bis zu 14 offene Fristen, die aelteste
    von 2019. Rein nach Datum sortiert stuende das Aktuelle ganz unten."""

    def test_laufendes_zuerst_dann_abgelaufenes_juengstes_oben(self, monkeypatch):
        import datetime
        heute = datetime.date.today()

        def tag(versatz):
            return (heute + datetime.timedelta(days=versatz)).isoformat()

        _, daten = _rufe_auf(monkeypatch, "70/24", [
            _frist("70/24", tag(-572), frist_art="Schriftsatzschluss alt"),
            _frist("70/24", tag(21), frist_art="Berufung"),
            _frist("70/24", tag(-17), frist_art="Vorfrist Berufungsbegruendung"),
            _frist("70/24", tag(2), frist_art="Berufung VF"),
        ])
        assert [f["frist_art"] for f in daten["fristen"]] == [
            "Berufung VF",                  # in 2 Tagen
            "Berufung",                     # in 21 Tagen
            "Vorfrist Berufungsbegruendung",  # vor 17 Tagen
            "Schriftsatzschluss alt",       # vor 572 Tagen
        ]

    def test_heute_faellige_stehen_ganz_oben(self, monkeypatch):
        import datetime
        heute = datetime.date.today()
        _, daten = _rufe_auf(monkeypatch, "70/24", [
            _frist("70/24", (heute + datetime.timedelta(days=5)).isoformat(), frist_art="spaeter"),
            _frist("70/24", heute.isoformat(), frist_art="heute"),
        ])
        assert [f["frist_art"] for f in daten["fristen"]] == ["heute", "spaeter"]
