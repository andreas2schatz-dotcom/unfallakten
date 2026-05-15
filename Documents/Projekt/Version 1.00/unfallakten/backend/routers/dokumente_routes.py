"""
Modul 4 – Router: Dokumente
=============================
REST-Endpunkte für Dokumenten-Upload und -Verwaltung.

Endpunkte:
  GET    /akten/<id>/dokumente               Dokumente einer Akte listen
  POST   /akten/<id>/dokumente               PDF/Bild hochladen + parsen
  GET    /akten/<id>/dokumente/<did>         Dokument-Metadaten abrufen
  GET    /akten/<id>/dokumente/<did>/datei   Datei herunterladen
  GET    /akten/<id>/dokumente/<did>/parse   Parse-Ergebnis abrufen
  POST   /akten/<id>/dokumente/<did>/korrektur  Parse-Ergebnis manuell korrigieren
  DELETE /akten/<id>/dokumente/<did>         Dokument löschen
"""

import json
import logging
from flask import Blueprint, request, jsonify, g, send_file
from ..auth.middleware import login_erforderlich
from ._helpers import pruefe_akte as _pruefe_akte
from ..models.dokument import (
    hole_dokumente_by_akte, GUELTIGE_TYPEN,
    aktualisiere_parse_status
)
from ..pdf.upload_service import (
    verarbeite_upload, hole_dokument_datei,
    loesche_dokument_mit_datei, korrigiere_parse_ergebnis,
    UploadFehler, _dok_dict
)
from ..db.database import get_connection
from ..services.portal_sync import _portal_flag
import io

logger = logging.getLogger(__name__)
dokumente_bp = Blueprint("dokumente", __name__,
                          url_prefix="/akten/<path:akte_id>/dokumente")


def _j(daten, status=200):
    return jsonify(daten), status

def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status

def _hole_dok_row(dokument_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM dokumente WHERE id = ?", (dokument_id,)
        ).fetchone()


def _schreibe_gutachten_nr(conn, akte_id, dispatch_ergebnis):
    """PORTAL-A2: Schreibt auftragsnummer aus Gutachten-Parse in beteiligte.gutachten_nr.

    Nur wenn: Dokumenttyp=gutachten, auftragsnummer vorhanden, genau ein SV in beteiligte.
    Stiller Fehler – darf Upload nie blockieren.
    """
    try:
        if not dispatch_ergebnis:
            return
        pe = dispatch_ergebnis.get("parse_ergebnis") or {}
        auftragsnummer = pe.get("auftragsnummer") or ""
        if not auftragsnummer:
            return
        if dispatch_ergebnis.get("klasse") != "gutachten":
            return
        svs = conn.execute(
            "SELECT id FROM beteiligte WHERE akte_id = ? AND rolle = 'sachverstaendiger'",
            (akte_id,)
        ).fetchall()
        if len(svs) == 1:
            conn.execute(
                "UPDATE beteiligte SET gutachten_nr = ? WHERE id = ?",
                (auftragsnummer, svs[0]["id"])
            )
            logger.info("PORTAL-A2: gutachten_nr=%r → beteiligte.id=%s", auftragsnummer, svs[0]["id"])
    except Exception as exc:
        logger.warning("_schreibe_gutachten_nr fehlgeschlagen (Akte %s): %s", akte_id, exc)


# ── Liste ──────────────────────────────────────────────────────────────────────

@dokumente_bp.route("", methods=["GET"])
@login_erforderlich
def liste(akte_id: str):
    """
    GET /akten/<id>/dokumente
    Listet alle Dokumente einer Akte auf.

    Query-Parameter:
      typ   Filter nach Dokumenttyp
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    typ = request.args.get("typ")
    dokumente = hole_dokumente_by_akte(akte_id, typ=typ)
    return _j({"dokumente": [_dok_dict(d) for d in dokumente]})


# ── Upload ─────────────────────────────────────────────────────────────────────

@dokumente_bp.route("", methods=["POST"])
@login_erforderlich
def upload(akte_id: str):
    """
    POST /akten/<id>/dokumente
    Lädt ein Dokument hoch und startet die PDF-Verarbeitung.

    Request: multipart/form-data
      - datei: Datei-Feld
      - typ:   Dokumenttyp (gutachten/abrechnungsschreiben/...)
      - auto_schaden: "true" → Schadenpositionen automatisch übernehmen

    Response 201:
      {
        "dokument":       { Dokument-Metadaten },
        "parse_ergebnis": { Extrahierte Felder, Konfidenz, Warnungen }
      }
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    # Datei aus multipart holen
    if "datei" not in request.files:
        return _err(
            "Kein 'datei'-Feld im Request. "
            "Bitte als multipart/form-data senden.", 422
        )

    datei = request.files["datei"]
    if not datei.filename:
        return _err("Kein Dateiname.", 422)

    typ = request.form.get("typ", "sonstiges").strip()
    auto_schaden = request.form.get("auto_schaden", "false").lower() == "true"

    datei_bytes = datei.read()
    ist_pdf = datei.filename.lower().endswith('.pdf')

    try:
        ergebnis = verarbeite_upload(
            akte_id=akte_id,
            dateiname=datei.filename,
            datei_bytes=datei_bytes,
            typ=typ,
            bearbeiter_id=g.benutzer_id,
            auto_schaden=auto_schaden,
            skip_parse=ist_pdf,  # Dispatcher übernimmt für PDFs
        )
    except UploadFehler as e:
        return _err(e.nachricht, e.status_code)
    except Exception as e:
        logger.error("Upload-Fehler: %s", e)
        return _err(f"Interner Fehler beim Upload: {e}", 500)

    # ── Dispatcher: PDF klassifizieren + parsen (Pipeline Phase 2) ─────────
    if ist_pdf:
        try:
            from ..workflow.dispatcher import dispatch_dokument
            dok_info = ergebnis.get("dokument") or {}
            dok_id = dok_info.get("id")
            if dok_id:
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT dateipfad FROM dokumente WHERE id = ?",
                        (dok_id,),
                    ).fetchone()
                dateipfad = row["dateipfad"] if row else None
                if dateipfad:
                    dispatch_ergebnis = dispatch_dokument(
                        dok_id=dok_id,
                        akte_az=akte_id,
                        dateipfad=dateipfad,
                        benutzer_id=g.benutzer_id,
                    )
                    logger.info(
                        "Dispatcher Dok %s: klasse=%s, konfidenz=%.2f, stufe=%s",
                        dok_id,
                        dispatch_ergebnis.get('klasse'),
                        dispatch_ergebnis.get('konfidenz', 0),
                        dispatch_ergebnis.get('stufe'),
                    )
                    ergebnis["dispatch"] = dispatch_ergebnis
                    ergebnis["parse_ergebnis"] = dispatch_ergebnis.get("parse_ergebnis")
                    # PORTAL-A2: auftragsnummer → beteiligte.gutachten_nr
                    _schreibe_gutachten_nr(conn, akte_id, dispatch_ergebnis)
        except Exception as e:
            # Dispatcher darf Upload NIE blockieren!
            logger.warning('Dispatcher fehlgeschlagen: %s', e)

    # Portal-Sync Flagge setzen
    try:
        with get_connection() as conn:
            _portal_flag(conn, akte_id)
    except Exception as exc:
        logger.warning("portal_flag fehlgeschlagen (Akte %s): %s", akte_id, exc)

    return _j(ergebnis, 201)


# ── Metadaten ─────────────────────────────────────────────────────────────────

@dokumente_bp.route("/<int:dokument_id>", methods=["GET"])
@login_erforderlich
def metadaten(akte_id: str, dokument_id: int):
    """
    GET /akten/<id>/dokumente/<did>
    Gibt Metadaten eines Dokuments zurück.
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    from ..models.dokument import Dokument
    dok = Dokument.from_row(row)
    return _j(_dok_dict(dok))


# ── Datei-Download ────────────────────────────────────────────────────────────

@dokumente_bp.route("/<int:dokument_id>/datei", methods=["GET"])
@login_erforderlich
def download(akte_id: str, dokument_id: int):
    """
    GET /akten/<id>/dokumente/<did>/datei
    Gibt die Rohdatei zum Download zurück.

    Response: application/pdf oder entsprechender MIME-Typ
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    ergebnis = hole_dokument_datei(dokument_id)
    if not ergebnis:
        return _err("Datei nicht auf dem Server gefunden.", 404)

    datei_bytes, dateiname, dateityp = ergebnis

    mime_map = {
        "pdf":  "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "jpg":  "image/jpeg",
        "png":  "image/png",
    }
    mime = mime_map.get(dateityp, "application/octet-stream")

    return send_file(
        io.BytesIO(datei_bytes),
        mimetype=mime,
        as_attachment=True,
        download_name=dateiname,
    )


# ── Parse-Ergebnis ────────────────────────────────────────────────────────────

@dokumente_bp.route("/<int:dokument_id>/parse", methods=["GET"])
@login_erforderlich
def parse_ergebnis(akte_id: str, dokument_id: int):
    """
    GET /akten/<id>/dokumente/<did>/parse
    Gibt das gespeicherte Parse-Ergebnis zurück.

    Response 200:
      {
        "parse_status":    "erfolgreich",
        "parse_konfidenz": 0.72,
        "parse_ergebnis":  { ... extrahierte Felder ... },
        "warnungen":       [ ... ]
      }
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    parse_json = row["parse_json"]
    ergebnis = None
    if parse_json:
        try:
            ergebnis = json.loads(parse_json)
        except json.JSONDecodeError:
            ergebnis = {"fehler": "Parse-JSON konnte nicht gelesen werden."}

    return _j({
        "parse_status":    row["parse_status"],
        "parse_konfidenz": row["parse_konfidenz"],
        "parse_fehler":    row["parse_fehler"],
        "parse_ergebnis":  ergebnis,
    })


# ── Manuelle Korrektur ────────────────────────────────────────────────────────

@dokumente_bp.route("/<int:dokument_id>/korrektur", methods=["POST"])
@login_erforderlich
def manuelle_korrektur(akte_id: str, dokument_id: int):
    """
    POST /akten/<id>/dokumente/<did>/korrektur
    Speichert ein manuell korrigiertes Parse-Ergebnis.

    Body:
      {
        "reparaturkosten": 6240.50,
        "sv_kosten":        890.00,
        ...
      }

    Response 200: Aktualisierter Parse-Status
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    korrigiert = request.get_json(silent=True) or {}
    if not korrigiert:
        return _err("Kein korrigierter Body angegeben.", 422)

    dok = korrigiere_parse_ergebnis(dokument_id, korrigiert)
    if not dok:
        return _err("Dokument konnte nicht aktualisiert werden.", 500)

    from ..models.dokument import logge_aktivitaet
    logge_aktivitaet(
        aktion="parse_manuell_korrigiert",
        beschreibung=f"Parse-Ergebnis von Dokument {dokument_id} manuell korrigiert.",
        akte_id=akte_id,
        benutzer_id=g.benutzer_id,
    )

    return _j({
        "nachricht":       "Parse-Ergebnis manuell korrigiert.",
        "parse_status":    dok.parse_status,
        "parse_konfidenz": dok.parse_konfidenz,
    })


# ── Klassifikation korrigieren ──────────────────────────────────────────────────

@dokumente_bp.route("/<int:dokument_id>/klassifikation", methods=["POST"])
@login_erforderlich
def klassifikation_korrigieren(akte_id: str, dokument_id: int):
    """
    POST /akten/<id>/dokumente/<did>/klassifikation
    Korrigiert die Dokumentenklasse und löst den richtigen Parser aus.
    Speichert ein Trainingspaar für den TF-IDF-Classifier.

    Body: { "dokumentenklasse": "abrechnungsschreiben" }

    Response 200:
      {
        "klasse":         "abrechnungsschreiben",
        "alte_klasse":    "gutachten",
        "parse_status":   "erfolgreich",
        "parse_ergebnis": { ... }
      }
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    body = request.get_json(silent=True) or {}
    neue_klasse = (body.get("dokumentenklasse") or "").strip()
    if not neue_klasse:
        return _err("'dokumentenklasse' ist erforderlich.", 422)

    try:
        from ..workflow.dispatcher import korrigiere_klassifikation
        ergebnis = korrigiere_klassifikation(
            dok_id=dokument_id,
            akte_az=akte_id,
            neue_klasse=neue_klasse,
            benutzer_id=g.benutzer_id,
        )
    except Exception as e:
        logger.error("Klassifikation-Korrektur fehlgeschlagen: %s", e)
        return _err(f"Korrektur fehlgeschlagen: {e}", 500)

    return _j(ergebnis)


# ── Vorhandenes PDF parsen (PRD-22) ──────────────────────────────────────────

@dokumente_bp.route("/<int:dokument_id>/parsen", methods=["POST"])
@login_erforderlich
def vorhandenes_parsen(akte_id, dokument_id):
    """
    POST /akten/<az>/dokumente/<did>/parsen
    Parst ein bereits registriertes PDF (aus Upload oder E-Akte-Import).
    Kein erneuter Upload noetig – liest direkt vom bestehenden Pfad.

    Query-Parameter:
      typ   Optional: Erwarteter Dokumenttyp (gutachten/abrechnungsschreiben/pruefbericht)
            Wenn angegeben, wird geprueft ob das Ergebnis passt.

    Response 200:
      {
        "ergebnis": { dokumenttyp, schadenpositionen, ... },
        "dokument_id": 123,
        "dateiname": "...",
        "klasse": "gutachten"
      }
    """
    import os
    from pathlib import Path

    if not _pruefe_akte(akte_id):
        return _err("Akte %s nicht gefunden." % akte_id, 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err("Dokument %d nicht gefunden." % dokument_id, 404)

    if row["dateityp"] != "pdf":
        return _err("Nur PDFs koennen geparst werden.", 422)

    dateipfad = row["dateipfad"]
    if not dateipfad or not os.path.exists(dateipfad):
        return _err("Datei nicht gefunden: %s" % (dateipfad or "kein Pfad"), 404)

    erwarteter_typ = request.args.get("typ", "").strip()

    # Dispatcher aufrufen (Klassifikation + Parsing)
    try:
        from ..workflow.dispatcher import dispatch_dokument
        dispatch_erg = dispatch_dokument(
            dok_id=dokument_id,
            akte_az=akte_id,
            dateipfad=dateipfad,
            benutzer_id=getattr(g, "benutzer_id", None),
            absender_domain=None,
        )
    except Exception as e:
        logger.error("Parsen fehlgeschlagen fuer Dok %d: %s", dokument_id, e)
        return _err("Parsen fehlgeschlagen: %s" % e, 500)

    klasse = dispatch_erg.get("klasse", "")
    parse_ergebnis = dispatch_erg.get("parse_ergebnis")

    # PORTAL-A2: auftragsnummer → beteiligte.gutachten_nr
    with get_connection() as conn:
        _schreibe_gutachten_nr(conn, akte_id, dispatch_erg)

    # Typenpruefung wenn gewuenscht
    if erwarteter_typ and klasse != erwarteter_typ:
        return _j({
            "ergebnis": parse_ergebnis,
            "dokument_id": dokument_id,
            "dateiname": row["dateiname"],
            "klasse": klasse,
            "warnung": "Dokument als '%s' erkannt, erwartet war '%s'." % (klasse, erwarteter_typ),
        })

    return _j({
        "ergebnis": parse_ergebnis,
        "dokument_id": dokument_id,
        "dateiname": row["dateiname"],
        "klasse": klasse,
    })


# ── Streaming-Parser mit OCR-Fortschritt (PRD-30) ─────────────────────────────

@dokumente_bp.route("/<int:dokument_id>/parsen-stream", methods=["GET"])
@login_erforderlich
def vorhandenes_parsen_stream(akte_id: str, dokument_id: int):
    """
    GET /akten/<az>/dokumente/<did>/parsen-stream

    Server-Sent Events (SSE) – liefert Live-Fortschritt während des Parsens.
    Besonders nützlich für Bild-PDFs (Generali etc.) wo OCR mehrere Sekunden dauert.

    Event-Format:
      data: {"schritt": "ocr",    "status": "laeuft"}
      data: {"schritt": "ocr",    "status": "fertig", "zeichen": 2840}
      data: {"schritt": "parsen", "status": "laeuft"}
      data: {"schritt": "parsen", "status": "fertig", "klasse": "abrechnungsschreiben"}
      data: {"schritt": "fertig", "ergebnis": {...}, "dokument_id": 123, "dateiname": "..."}
      data: {"schritt": "fehler", "meldung": "..."}

    Kein POST-Body nötig – Dokument wird anhand dok_id aus DB geladen.
    """
    import json as _json
    import os as _os
    import tempfile as _tempfile
    from flask import Response, stream_with_context

    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    if row["dateityp"] != "pdf":
        return _err("Nur PDFs koennen geparst werden.", 422)

    dateipfad = row["dateipfad"]
    if not dateipfad or not _os.path.exists(dateipfad):
        return _err(f"Datei nicht gefunden: {dateipfad or 'kein Pfad'}", 404)

    dateiname = row["dateiname"]
    benutzer_id = getattr(g, "benutzer_id", None)

    def _sse(data: dict) -> str:
        return "data: " + _json.dumps(data, ensure_ascii=False) + "\n\n"

    def generate():
        from ..parsers.pdf_utils import extract_text_from_pdf, normalize_text
        from ..services.ocr_service import ist_bild_pdf, ocr_text as _ocr_text, ocr_verfuegbar
        from ..workflow.dispatcher import dispatch_dokument

        # PDF-Bytes laden
        try:
            with open(dateipfad, "rb") as f:
                datei_bytes = f.read()
        except OSError as e:
            yield _sse({"schritt": "fehler", "meldung": f"Datei nicht lesbar: {e}"})
            return

        # Text extrahieren
        ocr_text_override = None
        try:
            with _tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(datei_bytes)
                tmp_pfad = tmp.name
            try:
                full_text, _pages, has_image_pages = extract_text_from_pdf(tmp_pfad)
            finally:
                try:
                    _os.unlink(tmp_pfad)
                except OSError:
                    pass

            norm_text = normalize_text(full_text)
        except Exception as e:
            yield _sse({"schritt": "fehler", "meldung": f"Textextraktion fehlgeschlagen: {e}"})
            return

        # OCR wenn Bild-PDF
        if ist_bild_pdf(has_image_pages, len(norm_text.strip())):
            if ocr_verfuegbar():
                yield _sse({"schritt": "ocr", "status": "laeuft"})
                try:
                    ocr_roh = _ocr_text(datei_bytes)
                    ocr_text_override = ocr_roh
                    zeichen = len(normalize_text(ocr_roh).strip())
                    yield _sse({"schritt": "ocr", "status": "fertig", "zeichen": zeichen})
                    logger.info(
                        "SSE-OCR Dok %d: %d Zeichen erkannt.", dokument_id, zeichen
                    )
                except Exception as e:
                    logger.warning("SSE-OCR Dok %d: %s", dokument_id, e)
                    yield _sse({"schritt": "ocr", "status": "fehler", "meldung": str(e)})
                    # Weiter ohne OCR-Text – Dispatcher versucht OCR-Fallback selbst
            else:
                yield _sse({
                    "schritt": "ocr",
                    "status": "nicht_verfuegbar",
                    "meldung": "Tesseract nicht installiert.",
                })

        # Dispatcher
        yield _sse({"schritt": "parsen", "status": "laeuft"})
        try:
            dispatch_erg = dispatch_dokument(
                dok_id=dokument_id,
                akte_az=akte_id,
                dateipfad=dateipfad,
                benutzer_id=benutzer_id,
                absender_domain=None,
                ocr_text_override=ocr_text_override,
            )
            klasse = dispatch_erg.get("klasse") or "unbekannt"
            yield _sse({"schritt": "parsen", "status": "fertig", "klasse": klasse})
            yield _sse({
                "schritt": "fertig",
                "ergebnis": dispatch_erg.get("parse_ergebnis"),
                "klasse": klasse,
                "dokument_id": dokument_id,
                "dateiname": dateiname,
            })
        except Exception as e:
            logger.error("SSE-Dispatcher Dok %d: %s", dokument_id, e, exc_info=True)
            yield _sse({"schritt": "fehler", "meldung": f"Parsen fehlgeschlagen: {e}"})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx Buffering deaktivieren
        },
    )


# ── Löschen ───────────────────────────────────────────────────────────────────

@dokumente_bp.route("/<int:dokument_id>", methods=["DELETE"])
@login_erforderlich
def loesche(akte_id: str, dokument_id: int):
    """
    DELETE /akten/<id>/dokumente/<did>
    Löscht ein Dokument aus DB und Dateisystem.

    Response 200: { "nachricht": "Dokument gelöscht." }
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    row = _hole_dok_row(dokument_id)
    if not row or row["akte_id"] != akte_id:
        return _err(f"Dokument {dokument_id} nicht gefunden.", 404)

    dateiname = row["dateiname"]
    erfolg = loesche_dokument_mit_datei(dokument_id)
    if not erfolg:
        return _err("Löschen fehlgeschlagen.", 500)

    from ..models.dokument import logge_aktivitaet
    logge_aktivitaet(
        aktion="dokument_geloescht",
        beschreibung=f"Dokument gelöscht: {dateiname}",
        akte_id=akte_id,
        benutzer_id=g.benutzer_id,
    )

    return _j({"nachricht": f"Dokument {dokument_id} ({dateiname}) gelöscht."})


# ── Portal-Sichtbarkeit ───────────────────────────────────────────────────────

@dokumente_bp.route("/<int:dok_id>/portal-sichtbar", methods=["PATCH"])
@login_erforderlich
def setze_portal_sichtbar(akte_id: str, dok_id: int):
    """
    PATCH /akten/<az>/dokumente/<did>/portal-sichtbar
    Setzt portal_sichtbar-Flag eines Dokuments und flaggt die Akte für Portal-Sync.

    Body: { "portal_sichtbar": true|false }

    Response 200: { "status": "ok", "portal_sichtbar": true|false }
    """
    akte_obj = _pruefe_akte(akte_id)
    if not akte_obj:
        return _err("Akte nicht gefunden", 404)
    az = akte_obj.aktenzeichen if hasattr(akte_obj, "aktenzeichen") else akte_id
    data = request.get_json(silent=True) or {}
    sichtbar = 1 if data.get("portal_sichtbar", False) else 0
    with get_connection() as conn:
        result = conn.execute(
            "UPDATE dokumente SET portal_sichtbar = ? WHERE id = ? AND akte_id = ?",
            (sichtbar, dok_id, az)
        )
        if result.rowcount == 0:
            return _err("Dokument nicht gefunden.", 404)
        _portal_flag(conn, az)
    return jsonify({"status": "ok", "portal_sichtbar": bool(sichtbar)})
