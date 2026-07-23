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


PLATZHALTER_KATALOG = [
    {"key": "MANDANT", "beschreibung": "Name der Mandantschaft", "beispiel": "Herr Max Beispiel"},
    {"key": "AZ", "beschreibung": "Aktenzeichen der Kanzlei", "beispiel": "971/25"},
    {"key": "VERSICHERER", "beschreibung": "Gegnerische Versicherung", "beispiel": "HUK-COBURG"},
    {"key": "DATUM", "beschreibung": "Heutiges Datum", "beispiel": "23.07.2026"},
    {"key": "KFZ", "beschreibung": "Fahrzeug (Hersteller/Typ/Kennzeichen)", "beispiel": "VW Golf, OF-XY 123"},
    {"key": "RGGDAT", "beschreibung": "Datum des Regulierungsschreibens", "beispiel": "10.07.2026"},
    {"key": "GUTACHTER", "beschreibung": "Name des Sachverständigen", "beispiel": "Dipl.-Ing. Muster"},
    {"key": "FKLASSE", "beschreibung": "Fahrzeug-/Mietwagenklasse", "beispiel": "Gruppe F"},
    {"key": "NUTZUNGSA", "beschreibung": "Nutzungsausfall-Tagessatz", "beispiel": "50,00 €"},
    {"key": "NABETRAG", "beschreibung": "Nutzungsausfall-Gesamtbetrag", "beispiel": "350,00 €"},
    {"key": "REPDAUER", "beschreibung": "Reparaturdauer laut Gutachten", "beispiel": "5 Arbeitstage"},
    {"key": "KOSTENNB", "beschreibung": "Kostennote/Gebührenbetrag", "beispiel": "413,64 €"},
    {"key": "SCHMGELD", "beschreibung": "Schmerzensgeld-Forderung", "beispiel": "1.500,00 €"},
    {"key": "SGVORSCHUSS", "beschreibung": "Schmerzensgeld-Vorschuss", "beispiel": "500,00 €"},
]

_BEISPIEL_KONTEXT = {p["key"]: p["beispiel"] for p in PLATZHALTER_KATALOG}


@kuerzungsarten_bp.route("/platzhalter", methods=["GET"])
@login_erforderlich
def platzhalter_katalog():
    return jsonify(PLATZHALTER_KATALOG)


@kuerzungsarten_bp.route("/vorschau", methods=["POST"])
@login_erforderlich
def textbaustein_vorschau():
    from ..word.stellungnahme_service import ersetze_platzhalter
    text = _body().get("text", "")
    return _j({"vorschau": ersetze_platzhalter(text, _BEISPIEL_KONTEXT)})


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
            hinweis_intern?, sv_stellungnahme_erforderlich?, sortierung?, textbaustein? }
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
            textbaustein=daten.get("textbaustein"),
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
               "rechtsgrundlagen", "hinweis_intern", "sortierung",
               "textbaustein"):
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
