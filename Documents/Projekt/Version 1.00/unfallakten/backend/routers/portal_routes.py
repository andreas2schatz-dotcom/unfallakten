"""Portal-Admin-Routen: Akte aktivieren, Stakeholder einladen, Sync-Status."""
import logging
from flask import Blueprint, g, jsonify, request
from ..auth.middleware import nur_admin
from ..db.database import get_connection
from ..services.portal_sync import queue_sync

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")
logger = logging.getLogger(__name__)


def _err(msg, code=400):
    return jsonify({"fehler": msg}), code


@portal_bp.route("/akten/<path:az>/aktivieren", methods=["POST"])
@nur_admin
def aktiviere_portal_fuer_akte(az):
    data = request.get_json(silent=True) or {}
    aktiv = 1 if data.get("aktiv", True) else 0
    with get_connection() as conn:
        row = conn.execute("SELECT az FROM unfallakte WHERE az = ?", (az,)).fetchone()
        if not row:
            return _err("Akte nicht gefunden", 404)
        conn.execute("UPDATE unfallakte SET portal_aktiv = ? WHERE az = ?", (aktiv, az))
        if aktiv:
            queue_sync(conn, az)
    return jsonify({"status": "ok", "portal_aktiv": bool(aktiv)})


@portal_bp.route("/akten/<path:az>/einladen", methods=["POST"])
@nur_admin
def einladen(az):
    data = request.get_json(silent=True) or {}
    beteiligter_id = data.get("beteiligter_id")
    email = (data.get("email") or "").strip()
    rolle = data.get("rolle", "")
    if not beteiligter_id or not email or rolle not in ("sachverstaendiger", "privatmandant"):
        return _err("beteiligter_id, email und rolle (sachverstaendiger|privatmandant) erforderlich")
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM beteiligte WHERE id = ? AND akte_id = ?", (beteiligter_id, az)
        ).fetchone()
        if not row:
            return _err("Beteiligter gehoert nicht zu dieser Akte", 404)
        conn.execute("""
            INSERT INTO portal_einladungen (akte_id, beteiligter_id, email, rolle, status, eingeladen_von)
            VALUES (?, ?, ?, ?, 'ausstehend', ?)
        """, (az, beteiligter_id, email, rolle, g.benutzer_id))
    return jsonify({"status": "einladung_gespeichert"})


@portal_bp.route("/status", methods=["GET"])
@nur_admin
def sync_status():
    with get_connection() as conn:
        stats = conn.execute(
            "SELECT status, COUNT(*) AS n FROM portal_sync_queue GROUP BY status"
        ).fetchall()
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM unfallakte WHERE portal_sync_pending = 1"
        ).fetchone()["n"]
        aktiv = conn.execute(
            "SELECT COUNT(*) AS n FROM unfallakte WHERE portal_aktiv = 1"
        ).fetchone()["n"]
        letzte = conn.execute("""
            SELECT MAX(sent_at) AS letzte FROM portal_sync_queue WHERE status = 'confirmed'
        """).fetchone()["letzte"]
    return jsonify({
        "queue": {r["status"]: r["n"] for r in stats},
        "pending_akten": pending,
        "aktiv_akten": aktiv,
        "letzter_sync": letzte,
    })
