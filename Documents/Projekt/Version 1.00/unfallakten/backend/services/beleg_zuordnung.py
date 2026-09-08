"""Einziger Schreibweg fuer ``schadenposition_belege`` (R2).

Beleg und Ereignis sind zwei Wahrheiten: die Beleg-Tabelle sagt, WOMIT eine
Position bewiesen wird (ein Zustand), das Ereignis sagt, WANN etwas hereinkam
(ein Vorgang). Freigabe und manuelle Zuordnung schreiben beide hierher.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..db.database import get_connection
from .positionsmodell_registry import lade_positionsmodell

logger = logging.getLogger(__name__)


def ordne_beleg_zu(*, akte_az: str, position_key: str, dokument_id: int,
                   betrag: Optional[float] = None,
                   notiz: Optional[str] = None) -> None:
    """Legt die Zuordnung an oder aktualisiert sie (Upsert)."""
    reg = lade_positionsmodell()
    if position_key not in reg.positionsarten:
        raise ValueError(
            f"Unbekannter position_key {position_key!r}. Erlaubt: "
            f"{sorted(reg.positionsarten)}"
        )

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO schadenposition_belege "
            "(akte_az, position_key, dokument_id, betrag_aus_beleg, notiz) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(akte_az, position_key, dokument_id) "
            "DO UPDATE SET betrag_aus_beleg = excluded.betrag_aus_beleg, "
            "              notiz = excluded.notiz",
            (akte_az, position_key, dokument_id, betrag, notiz),
        )
        conn.commit()


def belege_aus_freigabe(*, akte_az: str, dokument_id: int, klasse: str,
                        felder: Optional[Dict[str, Any]] = None,
                        vorsteuer: bool = False) -> List[str]:
    """Traegt die Belege einer Review-Freigabe ein.

    Gutachten belegen mehrere Positionen, Rechnungen genau eine. Klassen ohne
    Positionsbezug -- und die Auffangklasse 'rechnung' ohne Mapping-Eintrag --
    schreiben nichts. Best-Effort: Fehler brechen die Freigabe nie ab.
    """
    felder = felder or {}
    geschrieben: List[str] = []

    try:
        from .eingehende_ereignisse import (
            _feld_zu_zahl, _gutachten_positionen, rechnungstyp_zu_position,
        )

        if klasse == "gutachten":
            paare = _gutachten_positionen(felder, vorsteuer, akte_az=akte_az)
            for key, betrag in paare.items():
                ordne_beleg_zu(akte_az=akte_az, position_key=key,
                               dokument_id=dokument_id,
                               betrag=round(betrag, 2))
                geschrieben.append(key)
            return sorted(geschrieben)

        pk = rechnungstyp_zu_position(klasse, vorsteuer=vorsteuer)
        if pk:
            betrag = (_feld_zu_zahl(felder.get("bruttobetrag"))
                      or _feld_zu_zahl(felder.get("nettobetrag")))
            ordne_beleg_zu(akte_az=akte_az, position_key=pk,
                           dokument_id=dokument_id,
                           betrag=round(betrag, 2) if betrag is not None
                           else None)
            geschrieben.append(pk)
    except Exception as exc:  # pragma: no cover -- Best-Effort
        logger.warning(
            "Beleg aus Freigabe fehlgeschlagen (akte %s, dok %s, klasse %s): %s",
            akte_az, dokument_id, klasse, exc,
        )

    return geschrieben
