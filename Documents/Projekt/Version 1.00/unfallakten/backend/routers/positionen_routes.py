"""
Router: Positionsstatus + Aktionen (P1.3).

Endpoints:
  * GET /akten/<az>/positionen/status
       Ableitungsergebnis pro position_key + Wissensgrenzen-Payload
       (registry_version, stand pro Position).

  * GET /akten/<az>/positionen/<position_key>/ereignisse
       Ebene-2-Liste: alle Ereignisse dieser Position, chronologisch,
       inkl. ersetzter (K-M2a). Datum, Typ, Richtung, Dokument-Link,
       Herkunft, Status (aktuell/ersetzt).

  * GET /akten/<az>/aktionen[?dokument_id=...]
       Type-Action-Matrix-Auswertung aus aktionen.yaml.
       Ohne dokument_id: alle aktuellen Ereignisse der Akte.
       Mit dokument_id: nur Ereignisse dieses Dokuments.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..services.positionsmodell_registry import lade_positionsmodell
from ..services.positionsstatus_service import leite_positionsstatus_ab

logger = logging.getLogger(__name__)

positionen_bp = Blueprint(
    "positionen", __name__, url_prefix="/akten/<path:akte_az>"
)


def _err(msg: str, status: int, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status


def _pruefe_akte(az: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM unfallakte WHERE az = ?", (az,)
        ).fetchone()
    return row is not None


@positionen_bp.route("/positionen/status", methods=["GET"])
@login_erforderlich
def positionen_status(akte_az: str):
    if not _pruefe_akte(akte_az):
        return _err(f"Akte {akte_az!r} nicht gefunden.", 404)

    ergebnis = leite_positionsstatus_ab(akte_az, mit_registry=True)
    registry_version = ergebnis.pop("_registry_version", None)
    return jsonify({
        "akte_az": akte_az,
        "positionen": ergebnis,
        "registry_version": registry_version,
    })


@positionen_bp.route(
    "/positionen/<path:position_key>/ereignisse", methods=["GET"],
)
@login_erforderlich
def position_ereignisse(akte_az: str, position_key: str):
    """Ebene-2-Ereignisliste einer Position (P1.7).

    Liefert aktuelle *und* ersetzte Ereignisse dieser Position
    chronologisch (Datum aufsteigend). Ersetzte bleiben sichtbar,
    damit die UI die Historie zeigen kann; die Ableitung selbst
    ignoriert sie ohnehin (positionsstatus_service).
    """
    if not _pruefe_akte(akte_az):
        return _err(f"Akte {akte_az!r} nicht gefunden.", 404)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT pec.ereignis_id, pec.ereignistyp, pec.richtung, "
            "       pec.datum, pec.dokument_id, pec.wirkung, pec.betrag, "
            "       pec.kuerzungsart_id, pec.status, e.herkunft, e.notiz "
            "FROM position_ereignis_cache pec "
            "LEFT JOIN ereignisse e ON e.id = pec.ereignis_id "
            "WHERE pec.akte_az=? AND pec.position_key=? "
            "ORDER BY pec.datum ASC, pec.ereignis_id ASC",
            (akte_az, position_key),
        ).fetchall()

    ereignisse: List[Dict[str, Any]] = [{
        "ereignis_id":    r["ereignis_id"],
        "ereignistyp":    r["ereignistyp"],
        "richtung":       r["richtung"],
        "datum":          r["datum"],
        "dokument_id":    r["dokument_id"],
        "wirkung":        r["wirkung"],
        "betrag":         r["betrag"],
        "kuerzungsart_id": r["kuerzungsart_id"],
        "status":         r["status"],
        "herkunft":       r["herkunft"],
        "notiz":          r["notiz"],
    } for r in rows]

    return jsonify({
        "akte_az":      akte_az,
        "position_key": position_key,
        "ereignisse":   ereignisse,
    })


@positionen_bp.route("/aktionen", methods=["GET"])
@login_erforderlich
def aktionen_matrix(akte_az: str):
    """Aktions-Vorschlaege basierend auf aktuellen Ereignissen.

    Ohne dokument_id: aggregiert ueber alle aktuellen Ereignisse der Akte.
    Mit dokument_id: nur Ereignisse dieses Dokuments.
    """
    if not _pruefe_akte(akte_az):
        return _err(f"Akte {akte_az!r} nicht gefunden.", 404)

    dok_id_raw = request.args.get("dokument_id")
    try:
        dok_id = int(dok_id_raw) if dok_id_raw else None
    except ValueError:
        return _err("dokument_id muss eine Ganzzahl sein.", 400)

    reg = lade_positionsmodell()
    with get_connection() as conn:
        if dok_id is None:
            rows = conn.execute(
                "SELECT DISTINCT ereignistyp FROM ereignisse "
                "WHERE akte_az=? AND ersetzt_durch IS NULL",
                (akte_az,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT DISTINCT ereignistyp FROM ereignisse "
                "WHERE akte_az=? AND dokument_id=? "
                "  AND ersetzt_durch IS NULL",
                (akte_az, dok_id),
            ).fetchall()

    vorgeschlagen: List[Dict[str, Any]] = []
    gesehen: set[str] = set()  # Deduplikation: gleiche aktion nur einmal
    for r in rows:
        typ = r["ereignistyp"]
        eintrag = reg.aktionen.get(typ)
        if not eintrag:
            continue
        for fa in eintrag.get("folgeaktionen", []):
            aid = fa.get("aktion")
            if aid in gesehen:
                continue
            gesehen.add(aid)
            vorgeschlagen.append({
                "aktion":          aid,
                "label":           fa.get("label"),
                "positions_scope": fa.get("positions_scope", False),
                "vorbedingung":    fa.get("vorbedingung"),
                "trigger_typ":     typ,
            })

    return jsonify({
        "akte_az":         akte_az,
        "dokument_id":     dok_id,
        "aktionen":        vorgeschlagen,
        "registry_version": reg.version,
    })
