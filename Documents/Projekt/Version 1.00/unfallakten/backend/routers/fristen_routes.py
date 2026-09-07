r"""
backend/routers/fristen_routes.py
=================================
Fristen einer Akte aus dem RA-MICRO-Kalenderbaum Z:\RA\Kalender\GT.

  GET /akten/<az>/fristen    Alle unerledigten Fristen der Akte

Bewusst getrennt von todos_routes.py: To-Dos liegen in SQLite und sind
schreibbar, Fristen kommen aus einem read-only-Dateibaum und werden in
RA-MICRO abgehakt.

Anders als die Dashboard-Kachel (drei Werktage Vorschau) zeigt die Akte jede
unerledigte Frist, auch jahrealte. In der Akte zaehlt Vollstaendigkeit mehr als
Ruhe: eine seit Jahren offene Frist ist entweder laengst erledigt und nur nie
abgehakt worden -- dann soll man das sehen -- oder sie ist echt.
"""

import logging
import re
from datetime import date

from flask import Blueprint, jsonify

from ..auth.middleware import login_erforderlich
from ..models.akte import hole_akte_by_id
from ..services.fristen_gt import FristenQuelleNichtErreichbar, alle_offenen_fristen

logger = logging.getLogger(__name__)

# Fester url_prefix – <path:akte_id> pro Route (Lerneffekt v14d)
fristen_bp = Blueprint("fristen", __name__, url_prefix="/akten")

# Der Kalendersatz fuehrt nur die nackte Nummer ("322/26"), das Aktenzeichen im
# System kann ein Sachbearbeiterkuerzel tragen.
_NUMMER = re.compile(r"\d+/\d{2}")


def _aktennummer(az: str):
    m = _NUMMER.search(az or "")
    return m.group(0) if m else None


@fristen_bp.route("/<path:akte_id>/fristen", methods=["GET"])
@login_erforderlich
def liste_fristen(akte_id: str):
    """GET /akten/<az>/fristen – unerledigte Fristen der Akte.

    503, wenn der Kalenderbaum nicht lesbar ist (in der Regel ein weggefallener
    E-Akte-Mount). Eine leere Liste waere hier die gefaehrlichste Antwort.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return jsonify({"fehler": f"Akte '{akte_id}' nicht gefunden.",
                        "status": 404}), 404

    nummer = _aktennummer(akte.aktenzeichen)
    if not nummer:
        return jsonify({"fristen": [], "anzahl": 0})

    try:
        alle = alle_offenen_fristen()
    except FristenQuelleNichtErreichbar as e:
        logger.warning("Fristenkalender nicht lesbar: %s", e)
        return jsonify({
            "fristen": [],
            "anzahl": 0,
            "fehler": "Fristenkalender nicht erreichbar (E-Akte-Mount)",
        }), 503

    heute = date.today()
    fristen = [
        {
            "frist_datum":  e["frist_datum"],
            "frist_beginn": e["frist_beginn"],
            "frist_art":    e["frist_art"],
            "bemerkung":    e["bemerkung"],
            "sb":           e["sb"],
            "gerichts_az":  e["gerichts_az"],
            "ist_vorfrist": e["ist_vorfrist"],
            "tage_bis":     (date.fromisoformat(e["frist_datum"]) - heute).days,
        }
        for e in alle if e["aktennummer"] == nummer
    ]

    # Erst was noch laeuft (naechste zuerst), dann das Abgelaufene mit dem
    # Juengsten oben. Rein nach Datum sortiert stuenden bei Akten mit langer
    # Historie Fristen von vor anderthalb Jahren ganz oben.
    fristen.sort(key=lambda f: (0, f["tage_bis"]) if f["tage_bis"] >= 0
                 else (1, -f["tage_bis"]))
    return jsonify({"fristen": fristen, "anzahl": len(fristen)})
