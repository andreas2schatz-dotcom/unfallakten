"""
E-Akte Routes – API-Endpoints fuer RA-Micro DMS
=================================================
⛔ Alle Endpoints sind READ-ONLY gegenueber raEloakte.
   Eigene Daten werden nur in lokaler SQLite gespeichert.

Endpoints:
  GET  /akten/<az>/eakte              E-Akte-Dokumente auflisten
  GET  /akten/<az>/eakte/<nr>/datei   PDF herunterladen (Phase 2)
  POST /akten/<az>/eakte/<nr>/importieren  In Pipeline importieren (Phase 3a)

Python 3.9 kompatibel.
"""

import logging
import io
import os
from flask import Blueprint, request, jsonify, g, send_file
from ..auth.middleware import login_erforderlich

logger = logging.getLogger(__name__)

eakte_bp = Blueprint("eakte", __name__, url_prefix="/akten/<path:akte_id>/eakte")


def _j(daten, status=200):
    return jsonify(daten), status


def _err(msg, status):
    return jsonify({"fehler": msg, "status": status}), status


# ── Liste ──────────────────────────────────────────────────────────────────────

@eakte_bp.route("", methods=["GET"])
@login_erforderlich
def liste(akte_id):
    """
    GET /akten/<az>/eakte
    Listet E-Akte-Dokumente aus RA-Micro auf.

    Query-Parameter:
      emails   "true" → auch E-Mails anzeigen (Standard: nur PDFs)
      limit    Max. Anzahl (Standard: 200)
    """
    try:
        from ..ramicro.eakte_service import hole_eakte_dokumente
    except ImportError as e:
        return _err("E-Akte-Modul nicht verfuegbar: %s" % e, 503)

    emails = request.args.get("emails", "false").lower() == "true"
    limit = min(int(request.args.get("limit", "200")), 500)

    try:
        dokumente = hole_eakte_dokumente(
            az=akte_id,
            nur_pdf=not emails,
            limit=limit,
        )
    except ValueError as e:
        return _err(str(e), 422)
    except RuntimeError as e:
        return _err(str(e), 503)
    except Exception as e:
        logger.error("E-Akte Fehler fuer %s: %s", akte_id, e)
        return _err("E-Akte Abfrage fehlgeschlagen: %s" % e, 500)

    # Bereits importierte E-Akte-Nummern aus lokaler SQLite
    importierte_nrs = []
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT eakte_nr FROM dokumente WHERE akte_id = ? AND eakte_nr IS NOT NULL",
                (akte_id,),
            ).fetchall()
            importierte_nrs = [r["eakte_nr"] for r in rows]
    except Exception:
        pass

    return _j({
        "akte_id": akte_id,
        "anzahl": len(dokumente),
        "nur_pdf": not emails,
        "dokumente": dokumente,
        "importierte_nrs": importierte_nrs,
    })


# ── Datei-Download (Phase 2) ──────────────────────────────────────────────────

@eakte_bp.route("/<int:nr>/datei", methods=["GET"])
@login_erforderlich
def datei_download(akte_id, nr):
    """
    GET /akten/<az>/eakte/<nr>/datei
    Streamt ein E-Akte-Dokument vom Netzlaufwerk.
    ⛔ Read-only – Datei wird nur gelesen, nicht kopiert.

    Voraussetzung: EAKTE_BASE_PATH muss konfiguriert sein (Volume-Mount).
    """
    try:
        from ..ramicro.eakte_service import hole_eakte_dokument, baue_dateipfad
    except ImportError as e:
        return _err("E-Akte-Modul nicht verfuegbar: %s" % e, 503)

    base_path = os.environ.get("EAKTE_BASE_PATH", "")
    if not base_path:
        return _err(
            "E-Akte Dateizugriff nicht konfiguriert. "
            "EAKTE_BASE_PATH in .env setzen und Volume-Mount einrichten.",
            503,
        )

    try:
        dok = hole_eakte_dokument(akte_id, nr)
    except (ValueError, RuntimeError) as e:
        return _err(str(e), 422)

    if not dok:
        return _err("E-Akte-Dokument %d nicht gefunden." % nr, 404)

    pfad = baue_dateipfad(dok["dateiname"])
    if not pfad or not os.path.exists(pfad):
        return _err(
            "Datei nicht gefunden: %s. Volume-Mount pruefen." % (dok["dateiname"]),
            404,
        )

    # MIME-Typ bestimmen
    mime_map = {
        "pdf": "application/pdf",
        "msg": "application/vnd.ms-outlook",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "jpg": "image/jpeg",
        "png": "image/png",
    }
    mime = mime_map.get(dok["dateityp"], "application/octet-stream")

    # Anzeigename fuer Download
    download_name = dok["anzeigename"] or ("dokument_%d.%s" % (nr, dok["dateityp"]))

    try:
        datei_bytes = open(pfad, "rb").read()
        return send_file(
            io.BytesIO(datei_bytes),
            mimetype=mime,
            as_attachment=True,
            download_name=download_name,
        )
    except OSError as e:
        logger.error("E-Akte Datei lesen fehlgeschlagen: %s", e)
        return _err("Datei konnte nicht gelesen werden: %s" % e, 500)


# ── Pipeline-Import (Phase 3a) ────────────────────────────────────────────────

@eakte_bp.route("/<int:nr>/importieren", methods=["POST"])
@login_erforderlich
def importieren(akte_id, nr):
    """
    POST /akten/<az>/eakte/<nr>/importieren
    Importiert ein E-Akte-PDF in die Pipeline (Dispatcher).
    ⛔ Read-only gegenueber raEloakte – nur lokale SQLite wird geschrieben.

    1. E-Akte-Dokument aus raEloakte lesen (Metadaten)
    2. Duplikat-Check: eakte_nr schon in dokumente?
    3. PDF vom Netzlaufwerk lesen
    4. In dokumente registrieren (quelle='eakte')
    5. Dispatcher aufrufen (Klassifikation + Parsing)
    """
    try:
        from ..ramicro.eakte_service import hole_eakte_dokument, baue_dateipfad
        from ..db.database import get_connection
        from ..models.dokument import registriere_dokument
    except ImportError as e:
        return _err("Modul nicht verfuegbar: %s" % e, 503)

    # 1. E-Akte-Dokument holen (read-only SQL auf raEloakte)
    try:
        dok = hole_eakte_dokument(akte_id, nr)
    except (ValueError, RuntimeError) as e:
        return _err(str(e), 422)

    if not dok:
        return _err("E-Akte-Dokument %d nicht gefunden." % nr, 404)

    if dok["dateityp"] != "pdf":
        return _err("Nur PDFs koennen importiert werden.", 422)

    # 2. Duplikat-Check: eakte_nr schon importiert?
    try:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id, dateiname, dokumentenklasse FROM dokumente "
                "WHERE eakte_nr = ? AND akte_id = ?",
                (nr, akte_id),
            ).fetchone()
        if existing:
            return _j({
                "status": "duplikat",
                "meldung": "Dokument bereits importiert.",
                "dokument_id": existing["id"],
                "dokumentenklasse": existing["dokumentenklasse"],
            })
    except Exception as e:
        logger.warning("Duplikat-Check fehlgeschlagen: %s", e)

    # 3. PDF-Pfad pruefen
    pfad = baue_dateipfad(dok["dateiname"])
    if not pfad or not os.path.exists(pfad):
        return _err(
            "Datei nicht gefunden: %s. Volume-Mount pruefen." % dok["dateiname"],
            404,
        )

    # 4. Dateigroesse ermitteln
    try:
        dateigroesse = os.path.getsize(pfad)
    except OSError:
        dateigroesse = 0

    # 5. In dokumente registrieren (lokale SQLite)
    try:
        db_dok = registriere_dokument(
            akte_id=akte_id,
            typ="sonstiges",  # Wird vom Dispatcher ueberschrieben
            dateiname=dok["bemerkung"] or dok["anzeigename"] or ("eakte_%d.pdf" % nr),
            dateipfad=pfad,
            bearbeiter_id=getattr(g, "benutzer_id", None),
            dateityp="pdf",
            dateigroesse=dateigroesse,
        )
        dok_id = db_dok.id

        # eakte_nr, eakte_pfad, quelle setzen
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET eakte_nr = ?, eakte_pfad = ?, quelle = ? "
                "WHERE id = ?",
                (nr, dok["dateiname"], "eakte", dok_id),
            )
            conn.commit()
    except Exception as e:
        logger.error("E-Akte Registrierung fehlgeschlagen: %s", e)
        return _err("Registrierung fehlgeschlagen: %s" % e, 500)

    # 6. Dispatcher aufrufen (Klassifikation + Parsing)
    dispatch_ergebnis = None
    try:
        from ..workflow.dispatcher import dispatch_dokument
        dispatch_ergebnis = dispatch_dokument(
            dok_id=dok_id,
            akte_az=akte_id,
            dateipfad=pfad,
            benutzer_id=getattr(g, "benutzer_id", None),
            absender_domain=dok.get("absender_domain"),
        )
    except Exception as e:
        logger.error("Dispatcher fehlgeschlagen fuer E-Akte %d: %s", nr, e)
        # Nicht abbrechen – Dokument ist registriert, Parsing kann spaeter nachgeholt werden

    # Dokumentenklasse aus Dispatcher-Ergebnis
    klasse = None
    if dispatch_ergebnis:
        klasse = dispatch_ergebnis.get("klasse")

    return _j({
        "status": "importiert",
        "dokument_id": dok_id,
        "eakte_nr": nr,
        "dokumentenklasse": klasse,
        "dispatch": dispatch_ergebnis,
        "meldung": "E-Akte-Dokument importiert%s." % (
            " als %s" % klasse if klasse else ""
        ),
    })
