import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-ablage")
import datetime
import pytest
from backend.ramicro import ablage_service
from backend.ramicro.connector import RaMicroNichtAktiv


class _Cursor:
    def __init__(self, zeilen):
        self._zeilen = zeilen
        self.sql = None
        self.params = None

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._zeilen


class _Conn:
    def __init__(self, zeilen):
        self._cursor = _Cursor(zeilen)

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mit_zeilen(monkeypatch, zeilen):
    conn = _Conn(zeilen)
    monkeypatch.setattr(ablage_service, "get_ramicro_connection", lambda: conn)
    return conn


def test_abgelegt_wird_an_der_ablagenummer_erkannt(monkeypatch):
    _mit_zeilen(monkeypatch, [{
        "az": "100/24", "iAblageNummer": 4711,
        "dtAblage": datetime.datetime(2025, 3, 4),
        "kurz": "Meier/Schulz",
    }])
    ergebnis = ablage_service.hole_ablage_status(["100/24"])
    assert ergebnis["100/24"]["abgelegt"] is True
    assert ergebnis["100/24"]["ablage_datum"] == "2025-03-04"
    assert ergebnis["100/24"]["kurzbezeichnung"] == "Meier/Schulz"


def test_nullwert_1899_gilt_nicht_als_ablage(monkeypatch):
    _mit_zeilen(monkeypatch, [{
        "az": "101/24", "iAblageNummer": 0,
        "dtAblage": datetime.datetime(1899, 12, 30),
        "kurz": "Nticha/Meyer",
    }])
    ergebnis = ablage_service.hole_ablage_status(["101/24"])
    assert ergebnis["101/24"]["abgelegt"] is False
    assert ergebnis["101/24"]["ablage_datum"] is None


def test_ablagenummer_positiv_aber_1899_datum(monkeypatch):
    _mit_zeilen(monkeypatch, [{
        "az": "103/24", "iAblageNummer": 4711,
        "dtAblage": datetime.datetime(1899, 12, 30),
        "kurz": "Meyer/Schmidt",
    }])
    ergebnis = ablage_service.hole_ablage_status(["103/24"])
    assert ergebnis["103/24"]["abgelegt"] is True
    assert ergebnis["103/24"]["ablage_datum"] is None
    assert ergebnis["103/24"]["kurzbezeichnung"] == "Meyer/Schmidt"


def test_ablagenummer_null_gilt_nicht_als_ablage(monkeypatch):
    _mit_zeilen(monkeypatch, [{
        "az": "102/24", "iAblageNummer": None,
        "dtAblage": None, "kurz": "",
    }])
    ergebnis = ablage_service.hole_ablage_status(["102/24"])
    assert ergebnis["102/24"]["abgelegt"] is False


def test_ramicro_nicht_erreichbar_gibt_none(monkeypatch):
    def _kaputt():
        raise RaMicroNichtAktiv("kein RA-MICRO")
    monkeypatch.setattr(ablage_service, "get_ramicro_connection", _kaputt)
    assert ablage_service.hole_ablage_status(["100/24"]) is None


def test_leere_eingabe_fragt_ra_micro_nicht(monkeypatch):
    def _darf_nicht_aufgerufen_werden():
        raise AssertionError("RA-MICRO wurde trotz leerer Liste befragt")
    monkeypatch.setattr(
        ablage_service, "get_ramicro_connection", _darf_nicht_aufgerufen_werden
    )
    assert ablage_service.hole_ablage_status([]) == {}


def test_verbindung_ok_aber_keine_akten_gefunden(monkeypatch):
    _mit_zeilen(monkeypatch, [])
    ergebnis = ablage_service.hole_ablage_status(["999/99"])
    assert ergebnis == {}


def test_fragt_in_bloecken_an(monkeypatch):
    az_liste = [f"{i:03d}/24" for i in range(1, 502)]

    class _MultiBlockCursor:
        def __init__(self):
            self.aufrufe = []

        def execute(self, sql, params=None):
            self.aufrufe.append((sql, params))

        def fetchall(self):
            aufruf_nr = len(self.aufrufe) - 1
            if aufruf_nr == 0:
                return [{"az": f"{i:03d}/24", "iAblageNummer": i,
                         "dtAblage": datetime.datetime(2025, 1, 1), "kurz": f"Fall{i}"}
                        for i in range(1, 501)]
            elif aufruf_nr == 1:
                return [{"az": "501/24", "iAblageNummer": 501,
                         "dtAblage": datetime.datetime(2025, 1, 2), "kurz": "Fall501"}]
            return []

    class _MultiBlockConn:
        def __init__(self):
            self._cursor = _MultiBlockCursor()

        def cursor(self):
            return self._cursor

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    conn = _MultiBlockConn()
    monkeypatch.setattr(ablage_service, "get_ramicro_connection", lambda: conn)

    ergebnis = ablage_service.hole_ablage_status(az_liste)

    assert len(conn._cursor.aufrufe) == 2
    assert len(conn._cursor.aufrufe[0][1]) == 500
    assert len(conn._cursor.aufrufe[1][1]) == 1
    assert len(ergebnis) == 501
    assert ergebnis["001/24"]["abgelegt"] is True
    assert ergebnis["501/24"]["abgelegt"] is True
