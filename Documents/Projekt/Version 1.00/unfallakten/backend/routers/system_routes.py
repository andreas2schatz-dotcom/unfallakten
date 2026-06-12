import logging
from flask import Blueprint, jsonify
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
