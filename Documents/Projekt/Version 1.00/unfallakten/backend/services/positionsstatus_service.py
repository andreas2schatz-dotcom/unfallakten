"""
Positionsstatus-Ableitung (P1.3).

Reine Ableitungs-Funktionen ueber ``position_ereignis_cache``. Kein Schema,
kein Schreiben -- POSITIONSMODELL-PLAN Abschnitt 4.3.

Kernfunktion:
    leite_positionsstatus_ab(akte_az, mit_registry=False) -> dict je
    position_key mit den Feldern:
        * zustand            (offen / gefordert / anerkannt / teilanerkannt /
                              bestritten / erledigt)
        * gefordert          Summe aktueller 'gefordert'-Wirkungen (PF-02)
        * anerkannt          Summe aktueller 'anerkannt'-Wirkungen
        * gekuerzt           Summe aktueller 'gekuerzt'-Wirkungen
        * abgelehnt          Summe aktueller 'abgelehnt'-Wirkungen
        * offen              gefordert x Quote - anerkannt (Quote lt. PF-03,
                              Default 1.0)
        * eskalationsstufe   Ausgabe von _empfohlene_stufe (analog
                              sta_service, verallgemeinert auf Positionsebene)
        * stand              Datum des juengsten aktuellen Ereignisses
                              (POSITIONSMODELL-PLAN: Pflichtfeld fuer die
                              Wissensgrenze)
        * checkliste         { erledigt: [...], offen: [...] } aus der
                              positionsarten.yaml (Abschnitt 4.6)

Ableitungs-Invariante: **nur ``position_ereignis_cache.status='aktuell'``
Zeilen** werden beruecksichtigt. ersetzte Ereignisse (Kopf oder Zeile)
sind bereits durch ``ereignis_service`` in ``status='ersetzt'`` gehoben.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

from ..db.database import get_connection
from .positionsmodell_registry import lade_positionsmodell

logger = logging.getLogger(__name__)

DEFAULT_QUOTE = 1.0  # PF-03: Standard-Haftungsquote 100%


def _empfohlene_stufe(tage: int, sta_anzahl: int) -> int:
    """Analog backend/services/sta_service._empfohlene_stufe."""
    if sta_anzahl >= 2 and tage > 42:
        return 3
    if tage > 21 or sta_anzahl >= 1:
        return 2
    return 1


def _tage_seit(iso_datum: Optional[str]) -> int:
    if not iso_datum:
        return 0
    try:
        d = datetime.strptime(iso_datum[:10], "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max(0, (date.today() - d).days)


def _zustand(gefordert: float, anerkannt: float, gekuerzt: float,
              abgelehnt: float, hat_erledigt: bool,
              hat_bestritten_only: bool) -> str:
    if hat_erledigt:
        return "erledigt"
    if gefordert <= 0 and anerkannt <= 0 and gekuerzt <= 0 and abgelehnt <= 0:
        return "offen"
    if gefordert > 0 and anerkannt <= 0 and gekuerzt <= 0 and abgelehnt <= 0:
        return "gefordert"
    if gefordert > 0 and abgelehnt >= gefordert and anerkannt <= 0:
        return "bestritten"
    if gefordert > 0 and anerkannt >= gefordert - 0.005:
        return "anerkannt"
    return "teilanerkannt"


def leite_positionsstatus_ab(
    akte_az: str,
    *,
    quote: float = DEFAULT_QUOTE,
    mit_registry: bool = False,
) -> Dict[str, Any]:
    """Baut den Statusbaum je position_key fuer eine Akte.

    Nur ``position_ereignis_cache.status='aktuell'`` fliesst ein.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT position_key, ereignistyp, richtung, wirkung, betrag, "
            "       datum, dokument_id "
            "FROM position_ereignis_cache "
            "WHERE akte_az=? AND status='aktuell' "
            "ORDER BY datum ASC, ereignis_id ASC",
            (akte_az,),
        ).fetchall()
        ausgehende_akten_ereignisse = conn.execute(
            "SELECT ereignistyp, datum FROM ereignisse "
            "WHERE akte_az=? AND richtung='ausgehend' "
            "  AND ersetzt_durch IS NULL",
            (akte_az,),
        ).fetchall()

    per_key: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        key = r["position_key"]
        st = per_key.setdefault(key, {
            "gefordert": 0.0, "anerkannt": 0.0,
            "gekuerzt": 0.0,  "abgelehnt": 0.0,
            "erledigt_flag": False,
            "letztes_datum": None,
            "aktuelle_typen": set(),
            "aktuelle_typen_mit_dok": set(),
        })
        betrag = float(r["betrag"] or 0.0)
        w = r["wirkung"]
        if w == "gefordert":
            st["gefordert"] += betrag
        elif w == "anerkannt":
            st["anerkannt"] += betrag
        elif w == "gekuerzt":
            st["gekuerzt"] += betrag
        elif w == "abgelehnt":
            st["abgelehnt"] += betrag
        elif w == "erledigt":
            st["erledigt_flag"] = True
        st["aktuelle_typen"].add(r["ereignistyp"])
        if r["dokument_id"] is not None:
            st["aktuelle_typen_mit_dok"].add(r["ereignistyp"])
        if st["letztes_datum"] is None or r["datum"] > st["letztes_datum"]:
            st["letztes_datum"] = r["datum"]

    reg = lade_positionsmodell()

    # Ausgehende Ereignisse fuer die Akte -> Basis fuer Eskalationsstufe
    sta_anzahl = sum(
        1 for e in ausgehende_akten_ereignisse
        if e["ereignistyp"] == "sachstandsanfrage_generiert"
    )
    letzte_ausgehende = None
    for e in ausgehende_akten_ereignisse:
        if letzte_ausgehende is None or e["datum"] > letzte_ausgehende:
            letzte_ausgehende = e["datum"]
    tage_seit_letzter_aktion = _tage_seit(letzte_ausgehende)

    ergebnis: Dict[str, Any] = {}
    for key, st in per_key.items():
        zustand = _zustand(
            st["gefordert"], st["anerkannt"],
            st["gekuerzt"],  st["abgelehnt"],
            st["erledigt_flag"], False,
        )
        offen = max(0.0, st["gefordert"] * quote - st["anerkannt"])

        # Checkliste (POSITIONSMODELL 4.6): benoetigte Typen aus
        # positionsarten.yaml gegen aktuelle Ereignisse mit dokument_id!=NULL.
        checkliste_soll = reg.positionsarten.get(key, {}).get("checkliste", [])
        checkliste = {
            "erledigt": [t for t in checkliste_soll
                          if t in st["aktuelle_typen_mit_dok"]],
            "offen":    [t for t in checkliste_soll
                          if t not in st["aktuelle_typen_mit_dok"]],
        }

        ergebnis[key] = {
            "zustand":          zustand,
            "gefordert":        round(st["gefordert"], 2),
            "anerkannt":        round(st["anerkannt"], 2),
            "gekuerzt":         round(st["gekuerzt"], 2),
            "abgelehnt":        round(st["abgelehnt"], 2),
            "offen":            round(offen, 2),
            "quote":            quote,
            "stand":            st["letztes_datum"],
            "eskalationsstufe": _empfohlene_stufe(
                tage_seit_letzter_aktion, sta_anzahl,
            ),
            "checkliste":       checkliste,
        }

    if mit_registry:
        ergebnis["_registry_version"] = reg.version

    return ergebnis
