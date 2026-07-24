"""
V11 Standardtexte: REST-Routen fuer die pflegbaren Klageschrift-Bausteine.
Muster: kuerzungsarten_routes.py (Platzhalter-Katalog + Vorschau).
"""
import re

from flask import Blueprint, jsonify, request

from ..auth.middleware import login_erforderlich
from ..services.standardtext_registry import (
    ABSCHNITTE, hole_texte_aufgeloest, lade_standardtexte)
from ..models.standardtext_override import (
    hole_alle_overrides_mit_meta, loesche_override, setze_override)

standardtexte_bp = Blueprint(
    "standardtexte", __name__, url_prefix="/klage-standardtexte")

_PLATZHALTER_RE = re.compile(r"<([A-Z_]+)>")


def _j(d, s=200):
    return jsonify(d), s


def _body():
    return request.get_json(silent=True) or {}


@standardtexte_bp.route("", methods=["GET"])
@login_erforderlich
def liste():
    registry = lade_standardtexte()
    overrides = hole_alle_overrides_mit_meta()
    bausteine = []
    for key, e in registry.items():
        ov = overrides.get(key)
        bausteine.append({
            "key": key,
            "abschnitt": e["abschnitt"],
            "abschnitt_label": ABSCHNITTE[e["abschnitt"]],
            "beschreibung": e["beschreibung"],
            "standard_text": e["text"],
            "override_text": ov["text"] if ov else None,
            "geaendert_am": ov["geaendert_am"] if ov else None,
            "platzhalter": e["platzhalter"],
        })
    return _j({"bausteine": bausteine})


@standardtexte_bp.route("/aufgeloest", methods=["GET"])
@login_erforderlich
def aufgeloest():
    return _j({"texte": hole_texte_aufgeloest()})


@standardtexte_bp.route("/vorschau", methods=["POST"])
@login_erforderlich
def vorschau():
    from ..word.stellungnahme_service import ersetze_platzhalter
    body = _body()
    e = lade_standardtexte().get(str(body.get("key") or ""))
    if not e:
        return _j({"fehler": "Unbekannter Baustein."}, 404)
    kontext = {p["key"]: p["beispiel"] for p in e["platzhalter"]}
    return _j({"vorschau": ersetze_platzhalter(body.get("text") or "", kontext)})


@standardtexte_bp.route("/<key>", methods=["PUT"])
@login_erforderlich
def speichern(key):
    e = lade_standardtexte().get(key)
    if not e:
        return _j({"fehler": f"Unbekannter Baustein: {key}"}, 404)
    body = _body()
    text = str(body.get("text") or "").strip()
    if not text:
        return _j({"fehler": "Text darf nicht leer sein."}, 422)
    erlaubt = {p["key"] for p in e["platzhalter"]}
    benutzt = set(_PLATZHALTER_RE.findall(text))
    unbekannt = sorted(benutzt - erlaubt)
    if unbekannt:
        return _j({"fehler": "Unbekannte Platzhalter.", "unbekannt": unbekannt}, 422)
    pflicht = {p["key"] for p in e["platzhalter"] if p["pflicht"]}
    fehlend = sorted(pflicht - benutzt)
    if fehlend and not body.get("bestaetigt"):
        return _j({"warnung": "Pflicht-Platzhalter fehlen.", "fehlend": fehlend}, 409)
    setze_override(key, text)
    return _j({"ok": True})


@standardtexte_bp.route("/<key>", methods=["DELETE"])
@login_erforderlich
def zuruecksetzen(key):
    if key not in lade_standardtexte():
        return _j({"fehler": f"Unbekannter Baustein: {key}"}, 404)
    return _j({"ok": True, "geloescht": loesche_override(key)})
