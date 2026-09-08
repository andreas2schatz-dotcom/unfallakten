r"""
backend/routers/termine_routes.py
=================================
Termine einer Akte aus raKalender.dbo.Events.

  GET /akten/<az>/termine    Alle Termine der Akte

Bewusst getrennt von todos_routes.py, aus demselben Grund wie die Fristen:
To-Dos liegen in SQLite und sind schreibbar, Termine kommen read-only aus
RA-MICRO und werden dort gepflegt.
"""

import logging
import re

from flask import Blueprint, jsonify

from ..auth.middleware import login_erforderlich
from ..models.akte import hole_akte_by_id
from ..ramicro.connector import RaMicroNichtAktiv, RaMicroVerbindungsFehler
from ..services.termine_ramicro import termine_der_akte

logger = logging.getLogger(__name__)

# Fester url_prefix – <path:akte_id> pro Route (Lerneffekt v14d)
termine_bp = Blueprint("termine", __name__, url_prefix="/akten")

# Der Kalendersatz fuehrt nur die nackte Nummer ("322/26"), das Aktenzeichen im
# System kann ein Sachbearbeiterkuerzel tragen.
_NUMMER = re.compile(r"\d+/\d{2}")


def _aktennummer(az):
    m = _NUMMER.search(az or "")
    return m.group(0) if m else None


@termine_bp.route("/<path:akte_id>/termine", methods=["GET"])
@login_erforderlich
def liste_termine(akte_id):
    """GET /akten/<az>/termine – Termine der Akte, kommende zuerst.

    503, wenn RA-MICRO nicht erreichbar ist: ein Ausfall darf nicht wie "keine
    Termine" aussehen.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return jsonify({"fehler": "Akte '%s' nicht gefunden." % akte_id,
                        "status": 404}), 404

    nummer = _aktennummer(akte.aktenzeichen)
    if not nummer:
        return jsonify({"termine": [], "anzahl": 0})

    try:
        termine = termine_der_akte(nummer)
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Termine nicht lesbar: %s", e)
        return jsonify({
            "termine": [],
            "anzahl": 0,
            "fehler": "RA-MICRO nicht erreichbar",
        }), 503
    except Exception as e:
        logger.warning("Termine der Akte %s: %s", nummer, e)
        return jsonify({
            "termine": [],
            "anzahl": 0,
            "fehler": "RA-MICRO nicht erreichbar",
        }), 503

    # Wie bei den Fristen: erst was noch ansteht (der naechste oben), dann das
    # Gewesene mit dem juengsten zuerst. Rein nach Datum sortiert stuende bei
    # einer Akte mit Historie der naechste Termin ganz unten.
    termine.sort(key=lambda t: (0, t["tage_bis"], t["uhrzeit"] or "99:99")
                 if t["tage_bis"] >= 0
                 else (1, -t["tage_bis"], t["uhrzeit"] or "99:99"))
    return jsonify({"termine": termine, "anzahl": len(termine)})
