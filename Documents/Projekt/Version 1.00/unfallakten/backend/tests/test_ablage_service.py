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


def test_fragt_in_bloecken_an(monkeypatch):
    zeilen = [{"az": f"{i}/24", "iAblageNummer": 0, "dtAblage": None, "kurz": ""}
              for i in range(1, 5)]
    conn = _mit_zeilen(monkeypatch, zeilen)
    ablage_service.hole_ablage_status([f"{i}/24" for i in range(1, 5)])
    assert conn.cursor().params is not None
