import logging

from flask import Blueprint, g, jsonify, request

from ..auth.middleware import login_erforderlich
from ..services.aktenanlage_service import (
    VorgangExistiertFehler, brich_vorgang_ab, hole_offene_vorgaenge,
    lege_vorgang_an, schliesse_vorgang_ab)

logger = logging.getLogger(__name__)

aktenanlage_bp = Blueprint("aktenanlage", __name__,
                           url_prefix="/aktenanlage")


def _j(daten, status=200):
    return jsonify(daten), status


def _err(msg, status=400, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status


@aktenanlage_bp.route("", methods=["POST"])
@login_erforderlich
def post_anlegen():
    payload = request.get_json(silent=True) or {}
    try:
        vorgang = lege_vorgang_an(
            payload.get("formular") or {},
            intake_dokument_id=payload.get("intake_dokument_id"),
            zustellung_id=payload.get("zustellung_id"),
            benutzer_id=getattr(g, "benutzer_id", None),
        )
    except VorgangExistiertFehler as e:
        return _err(str(e), 409)
    except ValueError as e:
        return _err(str(e), 422)
    except OSError as e:
        return _err(f"OMA-Export-Ordner nicht beschreibbar: {e}", 500)
    return _j({"vorgang": vorgang}, 201)


@aktenanlage_bp.route("/offen", methods=["GET"])
@login_erforderlich
def get_offen():
    return _j(hole_offene_vorgaenge())


@aktenanlage_bp.route("/<int:vorgang_id>/abbrechen", methods=["POST"])
@login_erforderlich
def post_abbrechen(vorgang_id: int):
    if not brich_vorgang_ab(vorgang_id):
        return _err("Vorgang nicht gefunden oder nicht offen.", 409)
    return _j({"ok": True})


@aktenanlage_bp.route("/<int:vorgang_id>/abschliessen", methods=["POST"])
@login_erforderlich
def post_abschliessen(vorgang_id: int):
    if not schliesse_vorgang_ab(vorgang_id):
        return _err("Vorgang nicht im Status 'akte_erkannt'.", 409)
    return _j({"ok": True})
