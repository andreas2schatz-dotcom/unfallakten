import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-dashboard-wv")

import datetime
import textwrap

import pytest

from backend.routers import dashboard_routes


class _Cursor:
    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.sqls = []

    def execute(self, sql, params=None):
        self.sqls.append(sql)

    def fetchall(self):
        return self._antworten.pop(0) if self._antworten else []


class _Conn:
    def __init__(self, antworten):
        self._cursor = _Cursor(antworten)

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mit(monkeypatch, antworten):
    conn = _Conn(antworten)
    monkeypatch.setattr(dashboard_routes, "get_ramicro_connection", lambda: conn)
    return conn


def test_fristen_beschriftung_kommt_aus_der_registry(monkeypatch):
    _mit(monkeypatch, [[{
        "az_roh": "158/25", "az_sb": "CO", "mandant": "Hammer",
        "kurzbezeichnung": "Hammer/Amt", "frist_datum": datetime.date(2026, 11, 25),
        "grund_code": 55, "grund_text": "", "bemerkung": "",
    }]])
    e = dashboard_routes._lade_ramicro_fristen_hart()[0]
    assert e["frist_art"] == "Beschwerde"
    assert e["az"] == "158/25CO"


def test_fristen_freitext_schlaegt_den_code(monkeypatch):
    _mit(monkeypatch, [[{
        "az_roh": "100/26", "az_sb": "AS", "mandant": "M",
        "kurzbezeichnung": "M/G", "frist_datum": datetime.date(2026, 9, 2),
        "grund_code": 55, "grund_text": "Berufungsbegruendung raus!",
        "bemerkung": "",
    }]])
    assert dashboard_routes._lade_ramicro_fristen_hart()[0]["frist_art"] == \
        "Berufungsbegruendung raus!"


def test_fristen_reichen_die_bemerkung_durch(monkeypatch):
    _mit(monkeypatch, [[{
        "az_roh": "100/26", "az_sb": "AS", "mandant": "M",
        "kurzbezeichnung": "M/G", "frist_datum": datetime.date(2026, 9, 2),
        "grund_code": 75, "grund_text": "",
        "bemerkung": "Wenn nix mehr gekommen ist, ablegen",
    }]])
    assert dashboard_routes._lade_ramicro_fristen_hart()[0]["bemerkung"] == \
        "Wenn nix mehr gekommen ist, ablegen"


def test_fristen_sql_nutzt_die_registry_codes(monkeypatch):
    conn = _mit(monkeypatch, [[]])
    dashboard_routes._lade_ramicro_fristen_hart()
    assert "IN (21, 22, 31, 46, 51, 55, 75)" in conn.cursor().sqls[0]


def test_wiedervorlage_bekommt_jetzt_eine_konkrete_beschriftung(monkeypatch):
    """Code 12 stand nicht in _RAMICRO_GRUENDE und zeigte bisher
    pauschal 'Wiedervorlage'. 169 Zeilen im Bestand."""
    _mit(monkeypatch, [[{
        "az_roh": "200/26", "az_sb": "SK", "mandant": "M",
        "kurzbezeichnung": "M/G", "datum": datetime.date(2026, 9, 1),
        "grund_code": 12, "grund_text": "", "bemerkung": "",
    }], []])
    e = dashboard_routes._lade_wiedervorlagen()["wv"][0]
    assert e["grund"] == "Zahlung Gegner"


def test_wiedervorlage_sql_schliesst_frist_und_termincodes_aus(monkeypatch):
    conn = _mit(monkeypatch, [[], []])
    dashboard_routes._lade_wiedervorlagen()
    assert "NOT IN (9, 21, 22, 31, 46, 51, 55, 58, 60, 75)" in conn.cursor().sqls[0]


def test_alte_konstanten_sind_verschwunden():
    for name in ("_RAMICRO_GRUENDE", "_FRIST_LABELS", "_TERMIN_LABELS",
                 "_FRIST_CODES", "_TERMIN_CODES", "_WV_AUSSCHLUSS",
                 "_lade_ramicro_fristen"):
        assert not hasattr(dashboard_routes, name), \
            f"{name} lebt noch -- die Registry ist nicht die einzige Quelle"


def _kaputte_registry(tmp_path):
    p = tmp_path / "kaputte_registry.yaml"
    p.write_text(textwrap.dedent("""
        freitext_ab: 1000
        codes:
          5: {bezeichnung: "X", art: quatsch, verifiziert: false}
        standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
    """), encoding="utf-8")
    return str(p)


class TestKaputteRegistryFaelltNichtLeiseAus:
    """Eine fehlerhafte Registry darf NICHT im generischen except der
    Loader landen -- sonst zeigt die Kachel faelschlich 'keine Fristen',
    obwohl RA-MICRO nie befragt wurde. Der Registry-Fehler muss durch."""

    def test_termine_heute_bricht_sichtbar_ab(self, monkeypatch, tmp_path):
        monkeypatch.setenv("WIEDERVORLAGE_CODES_REGISTRY_PFAD",
                           _kaputte_registry(tmp_path))
        with pytest.raises(RuntimeError, match="art"):
            dashboard_routes._lade_termine_heute()

    def test_fristen_hart_bricht_sichtbar_ab(self, monkeypatch, tmp_path):
        monkeypatch.setenv("WIEDERVORLAGE_CODES_REGISTRY_PFAD",
                           _kaputte_registry(tmp_path))
        with pytest.raises(RuntimeError, match="art"):
            dashboard_routes._lade_ramicro_fristen_hart()

    def test_wiedervorlagen_bricht_sichtbar_ab(self, monkeypatch, tmp_path):
        monkeypatch.setenv("WIEDERVORLAGE_CODES_REGISTRY_PFAD",
                           _kaputte_registry(tmp_path))
        with pytest.raises(RuntimeError, match="art"):
            dashboard_routes._lade_wiedervorlagen()
