import logging
import re

from flask import Blueprint, g, jsonify, request

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..ramicro.adress_service import (akten_zu_adresse, hole_adresse_details,
                                      suche_adressen)
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


@aktenanlage_bp.route("/adressen", methods=["GET"])
@login_erforderlich
def get_adressen():
    q = (request.args.get("q") or "").strip()
    return _j({"treffer": suche_adressen(q)})


@aktenanlage_bp.route("/adresse/<int:adressnr>", methods=["GET"])
@login_erforderlich
def get_adresse(adressnr: int):
    return _j({"adresse": hole_adresse_details(adressnr),
               "akten": akten_zu_adresse(adressnr)})


def _domain_aus_absender(absender: str) -> str:
    m = re.search(r"@([A-Za-z0-9.-]+)", absender or "")
    return m.group(1).lower() if m else ""


@aktenanlage_bp.route("/gutachter-vorlage", methods=["GET"])
@login_erforderlich
def get_gutachter_vorlage():
    zustellung_id = request.args.get("zustellung_id", type=int)
    if zustellung_id is None:
        return _err("zustellung_id fehlt", 422)
    with get_connection() as conn:
        zust = conn.execute(
            "SELECT absender FROM zustellungen WHERE id=?",
            (zustellung_id,)).fetchone()
        domain = _domain_aus_absender(zust["absender"] if zust else "")
        vorlage = None
        if domain:
            vorlage = conn.execute(
                "SELECT name, ramicro_adressnr FROM email_absender_vorlagen "
                "WHERE LOWER(domain)=? AND kategorie='gutachter' AND aktiv=1",
                (domain,)).fetchone()
    if not vorlage:
        return _j({"vorlage": None})
    adressnr = None
    if vorlage["ramicro_adressnr"]:
        try:
            adressnr = int(vorlage["ramicro_adressnr"])
        except (TypeError, ValueError):
            adressnr = None
    adresse = hole_adresse_details(adressnr) if adressnr is not None else None
    return _j({"vorlage": {"name": vorlage["name"],
                           "adressnr": adressnr,
                           "adresse": adresse}})
