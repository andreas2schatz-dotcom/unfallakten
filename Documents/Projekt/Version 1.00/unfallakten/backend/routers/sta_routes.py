"""
STA-Routen – PRD-25d
====================
GET  /akten/<az>/sta/kontext?stufe=N  → Analyse + Brieftext
POST /akten/<az>/sta/generieren       → Word generieren + Todo anlegen
"""

import io
import logging
import os
import uuid
from datetime import date
from pathlib import Path

from flask import Blueprint, g, jsonify, request, send_file

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..models.dokument import registriere_dokument
from ..services.fristen_service import setze_antwort_frist
from ..services.sta_service import analysiere_regulierung, generiere_sta_text
from ..word.sachstandsanfrage import generiere_sachstandsanfrage

logger = logging.getLogger(__name__)

sta_bp = Blueprint("sta", __name__, url_prefix="/akten")


def _err(msg, status=400):
    return jsonify({"fehler": msg}), status


@sta_bp.route("/<path:az>/sta/kontext", methods=["GET"])
@login_erforderlich
def sta_kontext(az: str):
    """
    GET /akten/<az>/sta/kontext?stufe=N

    Gibt Analyse-Kontext und vorberechneten Brieftext zurück.
    stufe-Parameter optional (Default: empfohlene Stufe).
    """
    try:
        kontext = analysiere_regulierung(az)
    except Exception as e:
        logger.exception("sta_kontext: Fehler für Akte %s", az)
        return _err("Analyse fehlgeschlagen: {}".format(e), 500)

    try:
        stufe = int(request.args.get("stufe", kontext["empfohlene_stufe"]))
        stufe = max(1, min(3, stufe))
    except (ValueError, TypeError):
        stufe = kontext["empfohlene_stufe"]

    brieftext = generiere_sta_text(stufe, kontext)

    return jsonify({
        **kontext,
        "stufe":     stufe,
        "brieftext": brieftext,
    })


@sta_bp.route("/<path:az>/sta/generieren", methods=["POST"])
@login_erforderlich
def sta_generieren(az: str):
    """
    POST /akten/<az>/sta/generieren

    Body: { "stufe": 2, "brieftext": "..." }

    Generiert Word-Dokument, speichert in dokumente, legt 2-Wochen-Todo an.
    """
    body = request.get_json(silent=True) or {}

    try:
        stufe = max(1, min(3, int(body.get("stufe", 1))))
    except (ValueError, TypeError):
        stufe = 1

    brieftext = (body.get("brieftext") or "").strip()
    if not brieftext:
        return _err("Feld 'brieftext' fehlt.", 400)

    with get_connection() as conn:
        akte = conn.execute(
            "SELECT az, unfalldatum, unfallort FROM unfallakte WHERE az = ?",
            (az,)
        ).fetchone()
        if not akte:
            return _err("Akte '{}' nicht gefunden.".format(az), 404)

        mandant = conn.execute(
            "SELECT name, vorname, anschrift, plz, ort FROM beteiligte "
            "WHERE akte_id = ? AND rolle = 'mandant' LIMIT 1",
            (az,)
        ).fetchone()

        gegner = conn.execute(
            "SELECT name, vorname, firma, versicherung, anschrift, plz, ort, schaden_nr "
            "FROM beteiligte WHERE akte_id = ? AND rolle = 'gegner' LIMIT 1",
            (az,)
        ).fetchone()

    akte_daten = {
        "akte": {
            "aktenzeichen": az,
            "unfalldatum":  akte["unfalldatum"] or "",
            "unfallort":    akte["unfallort"] or "",
        },
        "mandant":      dict(mandant) if mandant else None,
        "gegner":       dict(gegner)  if gegner  else None,
        "schaden":      None,
        "regulierungen": [],
        "kanzlei":      None,
        "brieftext":    brieftext,
    }

    try:
        doc_bytes = generiere_sachstandsanfrage(akte_daten)
    except Exception as e:
        logger.exception("sta_generieren: Word-Generierung fehlgeschlagen für %s", az)
        return _err("Dokument konnte nicht generiert werden: {}".format(e), 500)

    az_safe   = az.replace("/", "-")
    dateiname = "{}_sachstandsanfrage_stufe{}_{}.docx".format(
        az_safe, stufe, date.today().isoformat()
    )

    upload_dir = Path(os.environ.get(
        "UPLOAD_DIR", str(Path(__file__).parent.parent / "uploads")
    ))
    upload_dir.mkdir(parents=True, exist_ok=True)
    pfad = upload_dir / "{}_{}".format(uuid.uuid4().hex, dateiname)
    pfad.write_bytes(doc_bytes)

    benutzer_id = getattr(g, "benutzer_id", None)
    dok = None
    try:
        dok = registriere_dokument(
            akte_id=az,
            typ="sachstandsanfrage",
            dateiname=dateiname,
            dateipfad=str(pfad),
            bearbeiter_id=benutzer_id,
            dateityp="docx",
            dateigroesse=len(doc_bytes),
        )
        setze_antwort_frist(az, dok.id, "sachstandsanfrage")
    except Exception as e:
        logger.warning("sta_generieren: DB-Registrierung fehlgeschlagen für %s: %s", az, e)

    # ── Positionsmodell: sachstandsanfrage_generiert (P1.4) ─────────────────
    if dok is not None:
        try:
            from ..services.ausgehende_ereignisse import erzeuge as _p14_erzeuge
            _p14_erzeuge(
                akte_az=az, ereignistyp="sachstandsanfrage_generiert",
                dokument_id=dok.id, positionen=None,   # Akten-Scope
                benutzer_id=benutzer_id, herkunft="sta_routes",
            )
        except Exception as _e:
            logger.debug("P1.4 Ereignis-Erzeugung STA: %s", _e)

    return send_file(
        io.BytesIO(doc_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=dateiname,
    )
