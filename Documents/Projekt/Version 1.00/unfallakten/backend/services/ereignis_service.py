"""
Ereignis-Service (P1.2) — der EINZIGE Schreibpunkt fuer
``ereignisse`` / ``ereignis_positionen`` / ``position_ereignis_cache``.

Verantwortlichkeiten:
  * ``schreibe_ereignis()`` — legt Kopf + n:m-Zeilen an und synchronisiert
    den Ebene-2-Cache in derselben Transaktion.
  * ``rebuild_cache()`` — verwirft den Cache und rekonstruiert ihn aus
    Ebene 1 (Ereignis-Kopf + ereignis_positionen). Muss identisch zu
    ``schreibe_ereignis()`` sein (Drift-Guard-Test).
  * ``ersetzt_kopf_id`` fuehrt zu ``ersetzt_durch`` am Alt-Ereignis und
    zu ``status='ersetzt'`` in dessen Cache-Zeilen (K-M2 aus freigabe.md).

Regeln (POSITIONSMODELL-PLAN 4.1):
  * kein UPDATE ausser ``ersetzt_durch`` und ``versand_bestaetigt_am``.
  * kein DELETE. Ereignisse sind Fakten.
  * Registry-Validierung: ereignistyp, quelle, wirkung, position_key.

Konfliktbehandlung: Der Aufrufer erwartet eine ValueError-Exception bei
Registry-Konflikten (nicht IntegrityError -- damit der Freigabe-Dialog
lesbare Meldungen produziert).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..db.database import get_connection
from .positionsmodell_registry import lade_positionsmodell

logger = logging.getLogger(__name__)


_WIRKUNGEN = {"gefordert", "anerkannt", "gekuerzt", "abgelehnt",
              "erledigt", "beleg", "keine"}


def _validiere(akte_az: str, ereignistyp: str, quelle: str,
                positionen: List[Dict[str, Any]]) -> None:
    reg = lade_positionsmodell()
    if ereignistyp not in reg.ereignistypen:
        raise ValueError(
            f"Unbekannter Ereignistyp {ereignistyp!r}. Erlaubt: "
            f"{sorted(reg.ereignistypen)}"
        )
    spec = reg.ereignistypen[ereignistyp]
    if quelle not in spec["zulaessige_quellen"]:
        raise ValueError(
            f"Quelle {quelle!r} nicht zulaessig fuer Ereignistyp "
            f"{ereignistyp!r}. Erlaubt: {spec['zulaessige_quellen']}"
        )
    for pos in positionen:
        pk = pos.get("position_key")
        if pk not in reg.positionsarten:
            raise ValueError(
                f"Unbekannter position_key {pk!r}. Erlaubt: "
                f"{sorted(reg.positionsarten)}"
            )
        w = pos.get("wirkung")
        if w not in _WIRKUNGEN:
            raise ValueError(
                f"Unbekannte Wirkung {w!r}. Erlaubt: {sorted(_WIRKUNGEN)}"
            )
    if not akte_az:
        raise ValueError("akte_az fehlt")


def schreibe_ereignis(
    *,
    akte_az: str,
    ereignistyp: str,
    quelle: str,
    datum: str,
    dokument_id: Optional[int] = None,
    herkunft: Optional[str] = None,
    betragswirkung_gesamt: Optional[float] = None,
    notiz: Optional[str] = None,
    erfasst_von: Optional[int] = None,
    positionen: Optional[List[Dict[str, Any]]] = None,
    ersetzt_kopf_id: Optional[int] = None,
    ersetzt_positions_ids: Optional[List[int]] = None,
) -> int:
    """Erzeugt ein Ereignis (Kopf + Positionen + Cache) atomar.

    ``positionen`` ist eine Liste von Dicts mit den Feldern
    ``position_key``, ``wirkung``, optional ``betrag``, ``kuerzungsart_id``.
    Leere Liste -> Akten-Scope-Ereignis (POSITIONSMODELL 4.2).

    ``ersetzt_kopf_id`` (K-M2b): setzt ``ereignisse.ersetzt_durch = neue_id``
    am Alt-Ereignis und markiert alle dessen Cache-Zeilen als
    ``status='ersetzt'`` (Kopf-Ersetzung, ganzes Alt-Ereignis storniert).

    ``ersetzt_positions_ids`` (K-M2a): Liste von ereignis_positionen.id
    aus dem Alt-Ereignis, die von der neuen n:m-Zeile positionsscharf
    abgeloest werden. Match ueber position_key. Konvention:
    ``alt_position.ersetzt_durch = neue_position.id`` (nicht umgekehrt),
    Cache-Zeile der Alt-Position wechselt auf ``status='ersetzt'``.
    Kopf-Level bleibt aktuell -- unveraenderte Positionen des Alt-
    Ereignisses fliessen weiter in die Ableitung ein (Ergaenzungsgutachten).

    ``ersetzt_kopf_id`` und ``ersetzt_positions_ids`` schliessen sich aus.

    Liefert die neue ereignisse.id.
    """
    if ersetzt_kopf_id is not None and ersetzt_positions_ids:
        raise TypeError(
            "ersetzt_kopf_id und ersetzt_positions_ids sind widerspruechlich "
            "-- entweder Kopf- oder positionsscharfe Ersetzung, nicht beides."
        )
    positionen = positionen or []
    _validiere(akte_az, ereignistyp, quelle, positionen)

    reg = lade_positionsmodell()
    richtung = reg.ereignistypen[ereignistyp]["richtung"]

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO ereignisse "
            "(akte_az, ereignistyp, richtung, quelle, datum, dokument_id, "
            " herkunft, betragswirkung_gesamt, notiz, erfasst_von) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (akte_az, ereignistyp, richtung, quelle, datum, dokument_id,
             herkunft, betragswirkung_gesamt, notiz, erfasst_von),
        )
        neue_id = int(cur.lastrowid)

        neue_pos_ids_je_key: Dict[str, int] = {}
        for pos in positionen:
            pk = pos["position_key"]
            wk = pos["wirkung"]
            pcur = conn.execute(
                "INSERT INTO ereignis_positionen "
                "(ereignis_id, position_key, wirkung, betrag, kuerzungsart_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (neue_id, pk, wk,
                 pos.get("betrag"), pos.get("kuerzungsart_id")),
            )
            neue_pos_ids_je_key[pk] = int(pcur.lastrowid)
            conn.execute(
                "INSERT INTO position_ereignis_cache "
                "(akte_az, position_key, ereignis_id, ereignistyp, richtung, "
                " datum, dokument_id, wirkung, betrag, kuerzungsart_id, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'aktuell')",
                (akte_az, pk, neue_id, ereignistyp,
                 richtung, datum, dokument_id, wk,
                 pos.get("betrag"), pos.get("kuerzungsart_id")),
            )

        if ersetzt_kopf_id is not None:
            conn.execute(
                "UPDATE ereignisse SET ersetzt_durch=? WHERE id=?",
                (neue_id, ersetzt_kopf_id),
            )
            conn.execute(
                "UPDATE position_ereignis_cache SET status='ersetzt' "
                "WHERE ereignis_id=?",
                (ersetzt_kopf_id,),
            )

        if ersetzt_positions_ids:
            for alt_pos_id in ersetzt_positions_ids:
                alt_row = conn.execute(
                    "SELECT ereignis_id, position_key, wirkung, kuerzungsart_id "
                    "FROM ereignis_positionen WHERE id=?",
                    (alt_pos_id,),
                ).fetchone()
                if alt_row is None:
                    logger.warning(
                        "ersetzt_positions_ids: Alt-Position %d nicht "
                        "gefunden, ueberspringe", alt_pos_id,
                    )
                    continue
                neu_pos_id = neue_pos_ids_je_key.get(alt_row["position_key"])
                if neu_pos_id is None:
                    logger.warning(
                        "ersetzt_positions_ids: keine passende neue Position "
                        "fuer position_key=%r (alt_id=%d) -- ueberspringe",
                        alt_row["position_key"], alt_pos_id,
                    )
                    continue
                conn.execute(
                    "UPDATE ereignis_positionen SET ersetzt_durch=? "
                    "WHERE id=?",
                    (neu_pos_id, alt_pos_id),
                )
                conn.execute(
                    "UPDATE position_ereignis_cache SET status='ersetzt' "
                    "WHERE ereignis_id=? AND position_key=? AND wirkung=? "
                    "AND COALESCE(kuerzungsart_id, 0) "
                    "  = COALESCE(?, 0)",
                    (alt_row["ereignis_id"], alt_row["position_key"],
                     alt_row["wirkung"], alt_row["kuerzungsart_id"]),
                )

    logger.info(
        "Ereignis %d angelegt: akte=%s typ=%s quelle=%s positionen=%d",
        neue_id, akte_az, ereignistyp, quelle, len(positionen),
    )
    return neue_id


def pruefe_doppelerfassung(
    *,
    akte_az: str,
    dokument_id: Optional[int],
    ereignistyp: str,
) -> Optional[int]:
    """Prueft, ob fuer (akte_az, dokument_id, ereignistyp) bereits ein
    NICHT ersetztes Ereignis vorliegt.

    Liefert die ereignis.id des juengsten aktuellen Ereignisses zurueck,
    sonst None.

    Fuer ``dokument_id is None`` (z. B. WDM-Vorschlaege ohne Dokument)
    liefert der Guard IMMER ``None`` -- NULL waere kein sinnvoller
    Duplikat-Schluessel (mehrere WDM-Importe je Akte sind auf Alt-Tabellen-
    Ebene bereits verhindert).

    Fuer nicht existierende Akten oder Ereignisse liefert der Guard
    ``None``.
    """
    if dokument_id is None:
        return None
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM ereignisse "
            "WHERE akte_az=? AND dokument_id=? AND ereignistyp=? "
            "  AND ersetzt_durch IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (akte_az, dokument_id, ereignistyp),
        ).fetchone()
    return int(row["id"]) if row else None


def rebuild_cache(akte_az: Optional[str] = None) -> None:
    """Rekonstruiert ``position_ereignis_cache`` aus Ebene 1.

    ``akte_az=None`` -> alle Akten. Andernfalls nur die genannte Akte.
    """
    with get_connection() as conn:
        if akte_az is None:
            conn.execute("DELETE FROM position_ereignis_cache")
            rows = conn.execute(
                "SELECT ep.ereignis_id, ep.position_key, ep.wirkung, "
                "       ep.betrag, ep.kuerzungsart_id, ep.ersetzt_durch "
                "         AS pos_ersetzt, "
                "       e.akte_az, e.ereignistyp, e.richtung, e.datum, "
                "       e.dokument_id, e.ersetzt_durch AS kopf_ersetzt "
                "FROM ereignis_positionen ep "
                "JOIN ereignisse e ON e.id = ep.ereignis_id"
            ).fetchall()
        else:
            conn.execute(
                "DELETE FROM position_ereignis_cache WHERE akte_az=?",
                (akte_az,),
            )
            rows = conn.execute(
                "SELECT ep.ereignis_id, ep.position_key, ep.wirkung, "
                "       ep.betrag, ep.kuerzungsart_id, ep.ersetzt_durch "
                "         AS pos_ersetzt, "
                "       e.akte_az, e.ereignistyp, e.richtung, e.datum, "
                "       e.dokument_id, e.ersetzt_durch AS kopf_ersetzt "
                "FROM ereignis_positionen ep "
                "JOIN ereignisse e ON e.id = ep.ereignis_id "
                "WHERE e.akte_az = ?",
                (akte_az,),
            ).fetchall()

        for r in rows:
            status = "ersetzt" if (r["pos_ersetzt"] is not None
                                    or r["kopf_ersetzt"] is not None) \
                                  else "aktuell"
            conn.execute(
                "INSERT INTO position_ereignis_cache "
                "(akte_az, position_key, ereignis_id, ereignistyp, richtung, "
                " datum, dokument_id, wirkung, betrag, kuerzungsart_id, "
                " status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (r["akte_az"], r["position_key"], r["ereignis_id"],
                 r["ereignistyp"], r["richtung"], r["datum"],
                 r["dokument_id"], r["wirkung"], r["betrag"],
                 r["kuerzungsart_id"], status),
            )

    logger.info("rebuild_cache abgeschlossen (akte_az=%s, %d Zeilen)",
                akte_az, len(rows))
