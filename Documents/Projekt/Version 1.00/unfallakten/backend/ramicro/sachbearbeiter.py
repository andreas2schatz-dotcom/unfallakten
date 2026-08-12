"""
Modul 8 – Sachbearbeiter
========================
Quelle ist die Tabelle ``sachbearbeiter`` (Migration 68), gepflegt im
Einstellungen-Reiter. Das Dict ``_FALLBACK`` greift nur, wenn die Tabelle
fehlt (Bestands-DB ohne Migration 68).

RA-Micro speichert nur Kürzel (z.B. "AS") in tblAkten.sAktenSachbearbeiter.
Eine Stammdatentabelle mit Vollnamen existiert dort nicht.
"""

import logging
import sqlite3

from ..db.database import get_connection

logger = logging.getLogger(__name__)

KANZLEI = {"name": "Kanzlei Koch, Schatz & Kollegen", "titel": "Rechtsanwälte"}

_FALLBACK: dict[str, dict] = {
    "AS": {"name": "Andreas Schatz",    "titel": "Rechtsanwalt"},
    "CO": {"name": "Claudia Ostarek",   "titel": "Rechtsanwältin"},
    "EI": {"name": "Elsa Ihl",          "titel": "Rechtsanwaltsfachangestellte"},
    "SK": {"name": "Sophie Koch",       "titel": "Rechtsanwaltsfachangestellte"},
    "SN": {"name": "Susanne Neumann",   "titel": "Rechtsanwaltsfachangestellte"},
    "TB": {"name": "Tanja Brunner",     "titel": "Rechtsanwalts- und Notarfachangestellte"},
    "PK": {"name": "Peter Koch",        "titel": "Rechtsanwalt"},
    "CS": {"name": "Carina Salvagnin",  "titel": "Rechtsanwältin"},
    "MM": {"name": "Monika Mieth",      "titel": "Rechtsanwältin"},
    "AH": {"name": "Alexander Herbert", "titel": "Rechtsanwalt"},
}

_SPALTEN = ("kuerzel, name, titel, anrede, rolle, aktiv, ignoriert, "
            "dashboard_vorauswahl, kalender_name, sortierung, geaendert_am")


def _fallback_zeilen() -> list[dict]:
    return [
        {"kuerzel": k, "name": v["name"], "titel": v["titel"], "anrede": "",
         "rolle": "anwalt", "aktiv": 1, "ignoriert": 0, "dashboard_vorauswahl": 0,
         "kalender_name": None, "sortierung": 100, "geaendert_am": None}
        for k, v in _FALLBACK.items()
    ]


def _zeilen(nur_aktive: bool = False) -> list[dict]:
    sql = f"SELECT {_SPALTEN} FROM sachbearbeiter"
    if nur_aktive:
        sql += " WHERE aktiv = 1 AND ignoriert = 0"
    sql += " ORDER BY sortierung, kuerzel"
    try:
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]
    except sqlite3.OperationalError:
        logger.warning("Tabelle sachbearbeiter fehlt – Fallback auf die eingebaute Liste.")
        zeilen = _fallback_zeilen()
        return [z for z in zeilen if z["aktiv"]] if nur_aktive else zeilen


def alle_sachbearbeiter(nur_aktive: bool = False) -> list[dict]:
    """Alle Sachbearbeiter, sortiert nach Sortierung und Kürzel."""
    return _zeilen(nur_aktive)


def kalender_zu_kuerzel() -> dict[str, str]:
    """RA-MICRO-Kalendername → Kürzel (nur gepflegte Einträge)."""
    return {
        z["kalender_name"]: z["kuerzel"]
        for z in _zeilen()
        if (z.get("kalender_name") or "").strip()
    }


def hole_sachbearbeiter(kuerzel: str) -> dict:
    """
    Gibt Name und Titel für ein Sachbearbeiter-Kürzel zurück.
    Fallback: Kürzel in eckigen Klammern, Titel "Rechtsanwalt".
    """
    if not kuerzel:
        return dict(KANZLEI)
    gesucht = kuerzel.strip().upper()
    for z in _zeilen():
        if z["kuerzel"] == gesucht and not z["ignoriert"] and (z["name"] or "").strip():
            return {"name": z["name"], "titel": z["titel"]}
    return {"name": f"[{kuerzel}]", "titel": "Rechtsanwalt"}


# Kennzeichen der gegnerischen Haftpflichtversicherung in tblAktenBeteiligte
# RA-Micro verwendet üblicherweise "HV" – bitte prüfen und ggf. anpassen
# Kennzeichen der GHPV in tblAktenBeteiligte (aus echten Daten ermittelt)
HV_KENNZEICHEN = ("GHPV", "G1", "G2", "G3")   # Priorität: GHPV > G1 > G2 > G3
