"""
Fristablauf-Service - P1.6 (POSITIONSMODELL-PLAN Abschnitt 4.5 / 5.1).

Uebersetzt faellige todos (quelle='system', erledigt=0) aus dem
Alt-Modell in Ereignisse ``fristablauf`` (richtung=intern, quelle=system).

Die Alt-Tabelle ``todos`` bleibt bewusst bestehen (freigabe.md,
Vorwissen-Block P1.6): der Job liest sie nur, schreibt zusaetzlich das
Ereignis und markiert den Idempotenz-Anker ``fristablauf_ereignis_id``
(Migration 52).

Positions-Regel (Handover P1.6):
  * ``antwort_2w_{dok_id}``: das auslösende ausgehende Ereignis
    (forderung_generiert / stellungnahme_generiert /
    sachstandsanfrage_generiert / fristsetzung_generiert /
    klage_generiert) zum selben ``dokument_id`` liefert die
    Positionsliste. Wirkung im Fristablauf-Ereignis: ``keine``
    (fristablauf dokumentiert Eskalation, keinen Betragsanspruch).
  * Verjährung / PflVG: Akten-Scope, keine Positionen,
    ``dokument_id=NULL``.

Idempotenz: Der Job selektiert ``fristablauf_ereignis_id IS NULL`` und
setzt die Spalte nach erfolgreichem Ereignis-Schreiben. Ein zweiter Lauf
findet dieselbe todo-Zeile nicht mehr.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from ..db.database import get_connection
from .ereignis_service import schreibe_ereignis

logger = logging.getLogger(__name__)


# Ereignistypen, die einen Fristablauf ausloesen koennen (ausgehende
# Dokumente, die eine Antwortfrist starten). Klage ist bewusst dabei --
# eine Klage-Erwiderung nach Zustellung ist ebenfalls fristbewehrt.
_AUSLOESENDE_TYPEN = (
    "forderung_generiert",
    "stellungnahme_generiert",
    "sachstandsanfrage_generiert",
    "fristsetzung_generiert",
    "klage_generiert",
)


def _lade_faellige_todos(conn) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT id, akte_az, text, frist_typ, regel_key, dok_id "
        "FROM todos "
        "WHERE quelle='system' AND erledigt=0 "
        "  AND faellig_am IS NOT NULL "
        "  AND faellig_am <= date('now') "
        "  AND fristablauf_ereignis_id IS NULL "
        "ORDER BY faellig_am ASC, id ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def _positionen_aus_ausloesendem_ereignis(
    conn, *, akte_az: str, dokument_id: int,
) -> List[Dict[str, Any]]:
    """Sucht das juengste aktuelle ausgehende Ereignis zum Dokument und
    liefert dessen aktuelle Positionen als Liste fuer schreibe_ereignis.
    Wirkung wird auf 'keine' gesetzt (Fristablauf = Eskalations-Marker,
    kein Betragsanspruch)."""
    placeholders = ",".join("?" for _ in _AUSLOESENDE_TYPEN)
    ausl_row = conn.execute(
        "SELECT id FROM ereignisse "
        "WHERE akte_az=? AND dokument_id=? "
        "  AND richtung='ausgehend' "
        "  AND ersetzt_durch IS NULL "
        f"  AND ereignistyp IN ({placeholders}) "
        "ORDER BY id DESC LIMIT 1",
        (akte_az, dokument_id, *_AUSLOESENDE_TYPEN),
    ).fetchone()
    if ausl_row is None:
        return []

    pos_rows = conn.execute(
        "SELECT position_key FROM ereignis_positionen "
        "WHERE ereignis_id=? AND ersetzt_durch IS NULL",
        (ausl_row["id"],),
    ).fetchall()
    return [{"position_key": r["position_key"], "wirkung": "keine"}
             for r in pos_rows]


def _erzeuge_fristablauf_fuer_todo(todo: Dict[str, Any]) -> Optional[int]:
    dok_id = todo.get("dok_id")
    if dok_id is not None:
        # BUG-09: Positions-Lesen in einer EIGENEN, kurzlebigen Verbindung,
        # die vor dem schreibe_ereignis-Aufruf wieder freigegeben wird --
        # sonst haelt sie einen Lock, den schreibe_ereignis (neue Verbindung)
        # nicht bekommt ("database is locked").
        with get_connection() as conn:
            positionen = _positionen_aus_ausloesendem_ereignis(
                conn, akte_az=todo["akte_az"], dokument_id=int(dok_id),
            )
    else:
        positionen = []

    try:
        ev_id = schreibe_ereignis(
            akte_az=todo["akte_az"],
            ereignistyp="fristablauf",
            quelle="system",
            datum=date.today().isoformat(),
            dokument_id=int(dok_id) if dok_id is not None else None,
            herkunft="scheduler",
            notiz=todo.get("text"),
            positionen=positionen,
        )
    except Exception as exc:  # pragma: no cover - defensiv, s. Log
        logger.warning(
            "Fristablauf-Ereignis fuer todo #%s fehlgeschlagen: %s",
            todo.get("id"), exc,
        )
        return None
    return ev_id


def verarbeite_faellige_todos() -> int:
    """Erzeugt fristablauf-Ereignisse fuer alle faelligen system-todos,
    die noch keinen Idempotenz-Anker haben.

    Rueckgabe: Anzahl neu erzeugter Ereignisse.
    """
    with get_connection() as conn:
        offene = _lade_faellige_todos(conn)
    if not offene:
        return 0

    # BUG-09: pro Todo mit KURZLEBIGEN Verbindungen arbeiten. schreibe_ereignis
    # oeffnet intern eine eigene Verbindung; wuerde die aeussere Schleife eine
    # unkommittierte Schreib-Transaktion halten (UPDATE todos), liefe die
    # zweite Frist in den SQLite-Write-Lock ("database is locked").
    erzeugt = 0
    for todo in offene:
        ev_id = _erzeuge_fristablauf_fuer_todo(todo)
        if ev_id is None:
            continue
        with get_connection() as conn:
            conn.execute(
                "UPDATE todos SET fristablauf_ereignis_id=? WHERE id=?",
                (ev_id, todo["id"]),
            )
        erzeugt += 1

    if erzeugt:
        logger.info(
            "fristablauf_service: %d neue fristablauf-Ereignisse angelegt.",
            erzeugt,
        )
    return erzeugt
