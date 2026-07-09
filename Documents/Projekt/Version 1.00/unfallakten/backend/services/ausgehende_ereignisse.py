"""
Helper fuer ausgehende Ereignisse (P1.4).

Wird von den Generierungs-Stellen aufgerufen (word_service, klage_routes,
stellungnahme_routes, sta_routes, gebuehren_word) und wrapt
``ereignis_service.schreibe_ereignis`` so, dass:

  * quelle = 'dokument' (ausgehende Dokumente sind quelle=dokument).
  * Wirkung wird aus der Registry-Vorbelegung des Ereignistyps
    (``default_wirkung``) uebernommen, wenn der Aufrufer keine explizite
    Wirkung angibt.
  * Positionen koennen als dict ``{position_key: betrag}`` oder als Liste
    von Positions-Dicts uebergeben werden (bequemer fuer Alt-Kontexte).
  * Unbekannte position_keys werden weggeloggt und uebersprungen (Alt-
    Kontexte enthalten manchmal Fantasie-Keys, z. B. "kostenpauschale").
    Wenn dadurch keine Positionen mehr uebrigbleiben, entsteht ein
    Akten-Scope-Ereignis (leere Positionsliste).
  * Best-Effort: Fehler beim Schreiben werden geloggt, aber nicht durch-
    gereicht (Rueckgabe None). Ausgehende Generierung darf durch ein
    Ereignis-Problem NIE brechen.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Union

from .ereignis_service import schreibe_ereignis
from .positionsmodell_registry import lade_positionsmodell

logger = logging.getLogger(__name__)


PositionenInput = Union[
    None,
    Dict[str, Optional[float]],
    Iterable[Dict[str, Any]],
]


def _normalisiere_positionen(positionen: PositionenInput,
                              wirkung: str) -> List[Dict[str, Any]]:
    """Bringt {key: betrag} oder Liste in die kanonische Form fuer
    schreibe_ereignis."""
    if positionen is None:
        return []

    if isinstance(positionen, dict):
        eintraege: List[Dict[str, Any]] = []
        for k, v in positionen.items():
            if v is None:
                continue
            try:
                betrag = float(v)
            except (TypeError, ValueError):
                logger.debug("Positionsbetrag %r nicht numerisch, ueberspringe",
                             v)
                continue
            eintraege.append({"position_key": k,
                              "wirkung": wirkung,
                              "betrag": betrag})
        return eintraege

    # Iterable von Dicts
    liste: List[Dict[str, Any]] = []
    for eintrag in positionen:
        if not isinstance(eintrag, dict):
            continue
        pk = eintrag.get("position_key")
        if not pk:
            continue
        pos = {
            "position_key": pk,
            "wirkung": eintrag.get("wirkung", wirkung),
        }
        if "betrag" in eintrag:
            pos["betrag"] = eintrag["betrag"]
        if "kuerzungsart_id" in eintrag:
            pos["kuerzungsart_id"] = eintrag["kuerzungsart_id"]
        liste.append(pos)
    return liste


def erzeuge(
    *,
    akte_az: str,
    ereignistyp: str,
    dokument_id: Optional[int],
    positionen: PositionenInput = None,
    datum: Optional[str] = None,
    benutzer_id: Optional[int] = None,
    herkunft: Optional[str] = None,
    notiz: Optional[str] = None,
    wirkung_override: Optional[str] = None,
) -> Optional[int]:
    """Schreibt ein ausgehendes Ereignis. Liefert die ereignis_id oder
    None bei Fehler (Best-Effort).
    """
    try:
        reg = lade_positionsmodell()
        spec = reg.ereignistypen.get(ereignistyp)
        if spec is None:
            logger.warning(
                "Ausgehendes Ereignis abgebrochen: unbekannter Typ %r",
                ereignistyp,
            )
            return None

        wirkung = wirkung_override or spec.get("default_wirkung") or "gefordert"
        pos_liste = _normalisiere_positionen(positionen, wirkung)

        # Unbekannte position_keys herausfiltern
        gefilterte = []
        for p in pos_liste:
            if p["position_key"] in reg.positionsarten:
                gefilterte.append(p)
            else:
                logger.debug(
                    "Ausgehendes Ereignis: position_key %r nicht in Registry, "
                    "ueberspringe (typ=%s)",
                    p["position_key"], ereignistyp,
                )

        if datum is None:
            datum = date.today().isoformat()

        return schreibe_ereignis(
            akte_az=akte_az,
            ereignistyp=ereignistyp,
            quelle="dokument",
            datum=datum,
            dokument_id=dokument_id,
            herkunft=herkunft,
            notiz=notiz,
            erfasst_von=benutzer_id,
            positionen=gefilterte,
        )
    except Exception as exc:
        logger.warning(
            "Ausgehendes Ereignis fehlgeschlagen (Akte %s Typ %s): %s",
            akte_az, ereignistyp, exc,
        )
        return None
