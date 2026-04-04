"""
Modul 9 – Router: Kürzungsarten (Stammdaten)
=============================================
GET    /kuerzungsarten               Alle Kürzungsarten
POST   /kuerzungsarten               Neue Kürzungsart anlegen
PUT    /kuerzungsarten/<id>          Kürzungsart aktualisieren
PATCH  /kuerzungsarten/<id>/aktiv    Aktiv/Inaktiv schalten
"""

import logging
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ..models.kuerzungsart import (
    hole_alle_kuerzungsarten, hole_kuerzungsart_by_id,
    erstelle_kuerzungsart, aktualisiere_kuerzungsart,
    GUELTIGE_KATEGORIEN,
)

logger = logging.getLogger(__name__)

kuerzungsarten_bp = Blueprint("kuerzungsarten", __name__,
                               url_prefix="/kuerzungsarten")


def _j(d, s=200):  return jsonify(d), s
def _err(m, s, **kw): return jsonify({"fehler": m, "status": s, **kw}), s
def _body():        return request.get_json(silent=True) or {}


@kuerzungsarten_bp.route("", methods=["GET"])
@login_erforderlich
def liste_kuerzungsarten():
    """
    GET /kuerzungsarten?nur_aktive=1
    Gibt alle Kürzungsarten zurück, gruppiert nach Kategorie.
    """
    nur_aktive = request.args.get("nur_aktive", "0") == "1"
    arten = hole_alle_kuerzungsarten(nur_aktive=nur_aktive)
    return _j({
        "kuerzungsarten": [a.as_dict() for a in arten],
        "anzahl": len(arten),
    })


@kuerzungsarten_bp.route("/<int:kid>", methods=["GET"])
@login_erforderlich
def hole_kuerzungsart(kid: int):
    art = hole_kuerzungsart_by_id(kid)
    if not art:
        return _err(f"Kürzungsart {kid} nicht gefunden.", 404)
    return _j({"kuerzungsart": art.as_dict()})


@kuerzungsarten_bp.route("", methods=["POST"])
@login_erforderlich
def neue_kuerzungsart():
    """
    POST /kuerzungsarten
    Body: { bezeichnung, kategorie, standard_gegenargument?, rechtsgrundlagen?,
            hinweis_intern?, sv_stellungnahme_erforderlich?, sortierung? }
    """
    daten = _body()
    bezeichnung = (daten.get("bezeichnung") or "").strip()
    kategorie   = (daten.get("kategorie")   or "").strip()

    if not bezeichnung:
        return _err("bezeichnung ist erforderlich.", 422, feld="bezeichnung")
    if kategorie not in GUELTIGE_KATEGORIEN:
        return _err(
            f"Ungültige Kategorie. Erlaubt: {', '.join(GUELTIGE_KATEGORIEN)}",
            422, feld="kategorie",
        )

    try:
        art = erstelle_kuerzungsart(
            bezeichnung=bezeichnung,
            kategorie=kategorie,
            standard_gegenargument=daten.get("standard_gegenargument"),
            rechtsgrundlagen=daten.get("rechtsgrundlagen"),
            hinweis_intern=daten.get("hinweis_intern"),
            sv_stellungnahme_erforderlich=int(
                bool(daten.get("sv_stellungnahme_erforderlich", False))
            ),
            sortierung=int(daten.get("sortierung", 999)),
        )
    except ValueError as e:
        return _err(str(e), 422)

    return _j({"kuerzungsart": art.as_dict()}, 201)


@kuerzungsarten_bp.route("/<int:kid>", methods=["PUT"])
@login_erforderlich
def update_kuerzungsart(kid: int):
    """
    PUT /kuerzungsarten/<id>
    Aktualisiert eine Kürzungsart (alle Felder optional).
    """
    if not hole_kuerzungsart_by_id(kid):
        return _err(f"Kürzungsart {kid} nicht gefunden.", 404)

    daten = _body()
    felder = {}
    for f in ("bezeichnung", "kategorie", "standard_gegenargument",
               "rechtsgrundlagen", "hinweis_intern", "sortierung"):
        if f in daten:
            felder[f] = daten[f]
    if "sv_stellungnahme_erforderlich" in daten:
        felder["sv_stellungnahme_erforderlich"] = int(
            bool(daten["sv_stellungnahme_erforderlich"])
        )
    if "aktiv" in daten:
        felder["aktiv"] = int(bool(daten["aktiv"]))

    try:
        art = aktualisiere_kuerzungsart(kid, **felder)
    except ValueError as e:
        return _err(str(e), 422)

    return _j({"kuerzungsart": art.as_dict()})


@kuerzungsarten_bp.route("/<int:kid>/aktiv", methods=["PATCH"])
@login_erforderlich
def toggle_aktiv(kid: int):
    """
    PATCH /kuerzungsarten/<id>/aktiv
    Body: { "aktiv": true/false }
    """
    art = hole_kuerzungsart_by_id(kid)
    if not art:
        return _err(f"Kürzungsart {kid} nicht gefunden.", 404)

    daten = _body()
    aktiv = bool(daten.get("aktiv", not art.aktiv))
    art = aktualisiere_kuerzungsart(kid, aktiv=int(aktiv))
    return _j({"kuerzungsart": art.as_dict()})
