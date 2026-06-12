import logging
from flask import Blueprint, jsonify, request
from ..auth.middleware import login_erforderlich
from ..system.health_service import check_ramicro, get_status

system_bp = Blueprint("system", __name__)
logger = logging.getLogger(__name__)


@system_bp.route("/system/status", methods=["GET"])
@login_erforderlich
def system_status():
    return jsonify(get_status())


@system_bp.route("/system/ramicro/retry", methods=["POST"])
@login_erforderlich
def ramicro_retry():
    check_ramicro()
    status = get_status()
    return jsonify(status["ramicro"])


@system_bp.route("/system/imap-polling", methods=["GET"])
@login_erforderlich
def imap_polling_status():
    from ..email_import.polling_service import hole_accounts
    return jsonify({"accounts": hole_accounts()})


@system_bp.route("/system/imap-polling", methods=["PATCH"])
@login_erforderlich
def imap_polling_speichern():
    from ..email_import.polling_service import hole_accounts
    from ..db.database import get_connection
    daten = request.get_json(silent=True) or {}
    intervall_min = daten.get("intervall_min")
    accounts_map  = daten.get("accounts", {})
    ERLAUBTE = {"unfall", "termin", "bussgeld", "info"}

    if intervall_min is not None:
        try:
            intervall_min = int(intervall_min)
            if not (1 <= intervall_min <= 1440):
                return jsonify({"fehler": "intervall_min muss zwischen 1 und 1440 liegen."}), 422
        except (TypeError, ValueError):
            return jsonify({"fehler": "intervall_min muss eine Zahl sein."}), 422

    with get_connection() as conn:
        for account, aktiv in accounts_map.items():
            if account not in ERLAUBTE:
                continue
            conn.execute(
                "UPDATE imap_polling_config SET aktiv=? WHERE account=?",
                (1 if aktiv else 0, account),
            )
        if intervall_min is not None:
            conn.execute(
                "UPDATE imap_polling_config SET intervall_min=?",
                (intervall_min,),
            )
    return jsonify({"accounts": hole_accounts()})
