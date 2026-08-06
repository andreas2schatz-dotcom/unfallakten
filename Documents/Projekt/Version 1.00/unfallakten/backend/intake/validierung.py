"""
Ausfuehrung der YAML-Validierungsregeln aus der Klassen-Registry.

Die Registry deklariert je Klasse ``validierungsregeln`` (Name +
Beschreibung). Bis 2026-08-06 waren das reine Dokumentationseintraege --
hier werden sie tatsaechlich gegen die extrahierten ``felder`` geprueft.

pruefe_validierungsregeln(felder, regeln) liefert eine Liste deutscher
Warnungstexte fuer die Review-Queue. Nicht pruefbare Regeln (fehlende
Felder, unbekannter Regelname, kaputte Werte) werden still uebersprungen --
eine Validierung darf die Pipeline nie zum Absturz bringen.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TOLERANZ = 0.011  # 1 Cent + Float-Spielraum


def _als_betrag(wert: Any) -> Optional[float]:
    if isinstance(wert, bool):
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    return None


def _positions_betrag(pos: Any) -> Optional[float]:
    if not isinstance(pos, dict):
        return None
    for schluessel in ("betrag", "betrag_brutto", "betrag_netto"):
        wert = _als_betrag(pos.get(schluessel))
        if wert is not None:
            return wert
    return None


def _eur(wert: float) -> str:
    return f"{wert:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pruefe_summe_positionen_gleich_gesamt(felder: Dict[str, Any]) -> List[str]:
    gesamt = _als_betrag(felder.get("gesamtbetrag"))
    positionen = felder.get("positionen")
    if gesamt is None or not isinstance(positionen, list) or not positionen:
        return []
    betraege = [_positions_betrag(p) for p in positionen]
    betraege = [b for b in betraege if b is not None]
    if not betraege:
        return []
    summe = round(sum(betraege), 2)
    differenz = round(gesamt - summe, 2)
    if abs(differenz) <= _TOLERANZ:
        return []
    return [
        f"Summe der Positionen ({_eur(summe)} EUR) weicht vom Gesamtbetrag "
        f"({_eur(gesamt)} EUR) um {_eur(abs(differenz))} EUR ab — "
        "vermutlich fehlt eine Position oder ein Betrag wurde falsch erkannt."
    ]


def _pruefe_abzug_gesamt_summe(felder: Dict[str, Any]) -> List[str]:
    gesamt = _als_betrag(felder.get("abzug_gesamt"))
    if gesamt is None:
        return []
    teile = [
        _als_betrag(felder.get(k))
        for k in ("abzug_technisch", "abzug_werkstattalternative", "abzug_nfa")
    ]
    teile = [t for t in teile if t is not None]
    if not teile:
        return []
    summe = round(sum(teile), 2)
    differenz = round(gesamt - summe, 2)
    if abs(differenz) <= _TOLERANZ:
        return []
    return [
        f"Abzug gesamt ({_eur(gesamt)} EUR) entspricht nicht der Summe der "
        f"Einzelabzüge ({_eur(summe)} EUR, Differenz {_eur(abs(differenz))} EUR)."
    ]


_REGEL_FUNKTIONEN = {
    "summe_positionen_gleich_gesamt": _pruefe_summe_positionen_gleich_gesamt,
    "abzug_gesamt_summe": _pruefe_abzug_gesamt_summe,
}


def pruefe_validierungsregeln(felder: Dict[str, Any],
                              regeln) -> List[str]:
    """Prueft die deklarierten Regeln gegen die extrahierten Felder.

    Liefert deutsche Warnungstexte; leere Liste wenn nichts zu beanstanden
    oder nichts pruefbar ist.
    """
    if not isinstance(felder, dict) or not regeln:
        return []
    warnungen: List[str] = []
    for regel in regeln:
        name = regel.get("name") if isinstance(regel, dict) else None
        funktion = _REGEL_FUNKTIONEN.get(name or "")
        if funktion is None:
            continue
        try:
            warnungen.extend(funktion(felder))
        except Exception as e:
            logger.warning("Validierungsregel %s fehlgeschlagen: %s", name, e)
    return warnungen
