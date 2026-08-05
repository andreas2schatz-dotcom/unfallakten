"""
Abschluss-/Sachstandsbericht – Übersichts-Objekt (kanal-unabhängig)
====================================================================
Baut aus akte_daten (word_service._lade_akte_daten) ein reines dict,
das DOCX-Renderer und Vorschau-Endpoint speist. KEIN DB-Zugriff hier —
alle Daten kommen über akte_daten (hermetisch testbar).

Spec: docs/superpowers/specs/2026-08-05-abschlussbericht-design.md §6-§11
"""
from datetime import datetime

from ..word.abrechnungsuebersicht_service import (
    _normalise_key, _schadenpositionen_rows,
)


def _parse_datum(d):
    d = (d or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(d[:10], fmt)
        except ValueError:
            continue
    return datetime.max


def _baue_pos_map_mit_verlauf(abrechnungen: list) -> tuple:
    """
    Wie _baue_pos_map (Option B: Summe der Zahlungs-Inkremente je Key),
    zusätzlich je Position: Einzelzahlungen (das "wann") + Kürzungsgrund.
    Roh-Key ra_gebuehren wird VOR der Normalisierung abgefangen (er ist
    kein Schadenersatz "für Sie") und separat summiert.

    Returns: (pos_map, ra_gebuehren_gezahlt)
      pos_map: key -> {reguliert, zahlungen: [{datum, betrag, versicherung}],
                       kuerzung_grund: str|None}
    """
    pos_map = {}
    ra_gebuehren = 0.0
    for ab in sorted(abrechnungen or [], key=lambda a: _parse_datum(a.get("datum"))):
        for p in (ab.get("positionen") or []):
            raw = p.get("position_key") or p.get("art") or "sonstiges"
            reg = p.get("betrag_reguliert")
            if reg is None:
                continue
            reg_f = round(float(reg), 2)
            if raw == "ra_gebuehren":
                ra_gebuehren = round(ra_gebuehren + reg_f, 2)
                continue
            key = _normalise_key(raw)
            eintrag = pos_map.setdefault(
                key, {"reguliert": 0.0, "zahlungen": [], "kuerzung_grund": None})
            eintrag["reguliert"] = round(eintrag["reguliert"] + reg_f, 2)
            eintrag["zahlungen"].append({
                "datum":        ab.get("datum") or "",
                "betrag":       reg_f,
                "versicherung": ab.get("versicherung") or "",
            })
            grund = (p.get("kuerzungsart_bezeichnung")
                     or p.get("kuerzung_freitext") or "").strip()
            if grund:
                eintrag["kuerzung_grund"] = grund
    return pos_map, ra_gebuehren
