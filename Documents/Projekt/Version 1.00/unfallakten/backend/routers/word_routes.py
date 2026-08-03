"""
Modul 5 – Router: Word-Dokumente
==================================
REST-Endpunkte für die Generierung von Word-Dokumenten.

Endpunkte:
  POST /akten/<id>/dokumente/word                Dokument generieren
  GET  /akten/<id>/dokumente/word/<typ>/vorschau Sofort-Download ohne DB-Speicherung
"""

import io
import logging
from flask import Blueprint, request, jsonify, g, send_file
from ..auth.middleware import login_erforderlich
from ._helpers import pruefe_akte as _pruefe_akte
from ..word.word_service import (
    generiere_und_speichere, WordFehler, gueltige_dok_typen
)

logger = logging.getLogger(__name__)
word_bp = Blueprint("word", __name__,
                     url_prefix="/akten/<path:akte_id>/dokumente/word")


def _j(daten, status=200):
    return jsonify(daten), status

def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status

@word_bp.route("", methods=["POST"])
@login_erforderlich
def generiere(akte_id: str):
    """
    POST /akten/<id>/dokumente/word
    Generiert ein Word-Dokument und speichert es in DB + Dateisystem.

    Body:
      {
        "typ": "forderungsschreiben"
                | "sachstandsanfrage"
                | "abrechnungsuebersicht"
      }

    Response 201:
      {
        "dateiname":  "42-25_forderungsschreiben.docx",
        "groesse":    38720,
        "dokument":   { id, dateiname, dateityp, dateigroesse, hochgeladen_am },
        "download_url": "/akten/1/dokumente/word/forderungsschreiben/vorschau"
      }
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = request.get_json(silent=True) or {}
    dok_typ = daten.get("typ", "").strip()
    variante = daten.get("variante", "auto").strip()  # "auto" | "hoehe" | "grunde"
    adressat_id = daten.get("adressat_id")  # Optional: expliziter Adressat (Beteiligter-ID)

    if not dok_typ:
        return _err(
            "Feld 'typ' fehlt. "
            f"Erlaubte Werte: {', '.join(sorted(gueltige_dok_typen()))}",
            422, feld="typ"
        )

    try:
        ergebnis = generiere_und_speichere(
            akte_id=akte_id,
            dok_typ=dok_typ,
            bearbeiter_id=g.benutzer_id,
            in_db=True,
            variante=variante,
            adressat_id=int(adressat_id) if adressat_id else None,
        )
    except WordFehler as e:
        return _err(e.nachricht, e.status_code)
    except Exception as e:
        logger.error("Word-Fehler: %s", e)
        return _err(f"Interner Fehler: {e}", 500)

    return _j({
        "dateiname":    ergebnis["dateiname"],
        "groesse":      len(ergebnis["bytes"]),
        "dokument":     ergebnis["dokument"],
        "variante":     ergebnis.get("variante"),          # "hoehe" | "grunde" | None
        "download_url": f"/akten/{akte_id}/dokumente/word/{dok_typ}/vorschau",
    }, 201)


@word_bp.route("/<dok_typ>/vorschau", methods=["GET"])
@login_erforderlich
def vorschau(akte_id: str, dok_typ: str):
    """
    GET /akten/<id>/dokumente/word/<typ>/vorschau
    Generiert das Dokument on-the-fly und liefert es als Download zurück.
    Kein DB-Eintrag – nützlich für schnelle Vorschauen.

    Response: application/vnd.openxmlformats-officedocument.wordprocessingml.document
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    try:
        ergebnis = generiere_und_speichere(
            akte_id=akte_id,
            dok_typ=dok_typ,
            bearbeiter_id=g.benutzer_id,
            in_db=False,
        )
    except WordFehler as e:
        return _err(e.nachricht, e.status_code)

    return send_file(
        io.BytesIO(ergebnis["bytes"]),
        mimetype=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        as_attachment=True,
        download_name=ergebnis["dateiname"],
    )
