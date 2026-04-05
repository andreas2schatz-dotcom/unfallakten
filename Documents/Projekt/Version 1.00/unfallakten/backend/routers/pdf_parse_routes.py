"""
Modul 9 – PDF-Parser-Route
============================
Endpunkt für den Upload und das Parsen von Versicherungs-PDFs
(Abrechnungsschreiben + Prüfberichte) im Kontext des Regulierungsverlaufs.

Endpunkte:
  POST /akten/<id>/parse-pdf      PDF hochladen + sofort parsen
  GET  /akten/<id>/parse-pdf/test Verbindungstest (ohne Datei)
"""

import io
import logging
import tempfile
import os
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich

logger = logging.getLogger(__name__)

pdf_parse_bp = Blueprint("pdf_parse", __name__,
                         url_prefix="/akten/<path:akte_id>")


def _err(msg, status=400, **kw):
    return jsonify({"fehler": msg, "status": status, **kw}), status


def _bestimme_routing(domain, rubrik):
    # type: (str, str) -> dict
    """
    Bestimmt Routing-Entscheidung anhand von Domain und Rubrik.

    Gibt dict zurück:
      basis:   "domain_versicherer" | "rubrik" | "fallback_kein_signal" | "fallback_domain_unbekannt"
      typ:     "versicherung" | "mandant" | "aussergerichtlich" | "unbekannt"
      skip:    False (Fallback noch nicht aktiv – erst nach Testphase aktivierbar)

    Fallback-Logging:
      "fallback_kein_signal"      → kein Domain-Match, keine Rubrik → Classifier läuft
      "fallback_domain_unbekannt" → Domain vorhanden, aber nicht in Whitelist → Classifier läuft
      (Beide werden im Log sichtbar – nach Testphase kann "fallback_domain_unbekannt" auf skip=True gestellt werden)
    """
    import re as _re
    from ..parsers.document_classifier import VERSICHERER_PATTERNS

    RELEVANTE_RUBRIKEN = {"von mandant", "außergerichtlich"}

    # Domain bekannt als Versicherer?
    if domain:
        for pattern, _kuerzel, _name, _prio in VERSICHERER_PATTERNS:
            if _re.search(pattern, domain):
                return {"basis": "domain_versicherer", "typ": "versicherung", "skip": False}

    # Rubrik relevant?
    if rubrik in RELEVANTE_RUBRIKEN:
        return {"basis": "rubrik", "typ": rubrik, "skip": False}

    # Kein Signal überhaupt
    if not domain and not rubrik:
        return {"basis": "fallback_kein_signal", "typ": "unbekannt", "skip": False}

    # Domain vorhanden aber nicht in Whitelist
    return {"basis": "fallback_domain_unbekannt", "typ": "unbekannt", "skip": False}


def _parse_versicherungs_pdf(datei_bytes: bytes) -> dict:
    """
    Führt den vollständigen Parser-Workflow durch:
      1. Text extrahieren
      2. Dokument klassifizieren
      3. Je nach Typ: Abrechnungsschreiben oder Prüfbericht parsen

    Returns: strukturiertes Ergebnis-Dict
    """
    import json
    from ..parsers.pdf_utils import extract_text_from_pdf, normalize_text
    from ..parsers.document_classifier import classify_document
    from ..parsers.abrechnungsschreiben_parser import parse_abrechnungsschreiben
    from ..parsers.pruefbericht_parser import parse_pruefbericht
    from ..parsers.gutachten_parser import parse_gutachten

    # In temporäre Datei schreiben (pdfplumber benötigt Dateipfad oder Stream)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(datei_bytes)
        tmp_pfad = tmp.name

    try:
        full_text, page_texts, has_image_pages = extract_text_from_pdf(tmp_pfad)
    finally:
        try:
            os.unlink(tmp_pfad)
        except OSError:
            pass

    norm_text = normalize_text(full_text)

    # Klassifizieren
    meta = classify_document(norm_text, has_image_pages)

    basis = {
        "dokumenttyp":          meta.dokumenttyp,
        "versicherer":          meta.versicherer,
        "versicherer_kuerzel":  meta.versicherer_kuerzel,
        "pruefdienstleister":   meta.pruefdienstleister,
        "schadennummer":        meta.schadennummer,
        "aktenzeichen_kanzlei": meta.aktenzeichen_kanzlei,
        "schreibdatum":         meta.schreibdatum,
        "schadendatum":         meta.schadendatum,
        "hat_bildseiten":       meta.hat_bildseiten,
        "klassifizier_konfidenz": round(meta.konfidenz, 3),
        "seiten_anzahl":        len(page_texts),
    }

    if meta.dokumenttyp == "abrechnungsschreiben":
        r = parse_abrechnungsschreiben(norm_text, meta.versicherer_kuerzel)
        positionen = []
        for p in r.positionen:
            positionen.append({
                "art":           p.art,
                "bezeichnung":   p.bezeichnung,
                "betrag_brutto": p.betrag_brutto,
                "betrag_netto":  p.betrag_netto,
                "mwst_betrag":   p.mwst_betrag,
                "pruefbericht_abzug": p.pruefbericht_abzug,
                "hinweis":       p.hinweis,
                "konfidenz":     round(p.konfidenz, 3),
            })
        zahlungen = []
        for z in r.zahlungen:
            zahlungen.append({
                "empfaenger":     z.empfaenger,
                "betrag":         z.betrag,
                "datum":          z.datum,
                "konto_hinweis":  z.konto_hinweis,
            })
        ergebnis = {
            **basis,
            "abrechnungsart":   r.abrechnungsart,
            "gesamtbetrag":     r.gesamtbetrag,
            "mwst_hinweis":     r.mwst_hinweis,
            "positionen":       positionen,
            "zahlungen":        zahlungen,
            "parse_konfidenz":  round(r.konfidenz, 3),
            "warnungen":        r.warnungen,
        }

    elif meta.dokumenttyp == "pruefbericht":
        r = parse_pruefbericht(norm_text, meta.pruefdienstleister, has_image_pages)
        fahrzeug = {
            "hersteller":     r.fahrzeug.hersteller,
            "typ":            r.fahrzeug.typ,
            "erstzulassung":  r.fahrzeug.erstzulassung,
            "kennzeichen":    r.fahrzeug.kennzeichen,
        }
        ref_ws = None
        if r.referenzwerkstatt:
            w = r.referenzwerkstatt
            ref_ws = {
                "name":             w.name,
                "adresse":          w.adresse,
                "plz_ort":          w.plz_ort,
                "entfernung_km":    w.entfernung_km,
                "lohn_mechanik":    w.lohn_mechanik,
                "lohn_elektrik":    w.lohn_elektrik,
                "lohn_karosserie":  w.lohn_karosserie,
                "lohn_lack":        w.lohn_lack,
            }
        abzuege = [
            {
                "kategorie":   a.kategorie,
                "bezeichnung": a.bezeichnung,
                "betrag":      a.betrag,
            }
            for a in r.abzuege_detail
        ]
        ergebnis = {
            **basis,
            "pruefdienstleister":   r.pruefdienstleister,
            "auftraggeber":         r.auftraggeber,
            "vorgangsnummer":       r.vorgangsnummer,
            "fahrzeug":             fahrzeug,
            "reparaturkosten_brutto":           r.reparaturkosten_brutto,
            "reparaturkosten_netto_vor_pruefung": r.reparaturkosten_netto_vor_pruefung,
            "abzug_technisch":          r.abzug_technisch,
            "abzug_werkstattalternative": r.abzug_werkstattalternative,
            "abzug_nfa":                r.abzug_nfa,
            "abzug_gesamt":             r.abzug_gesamt,
            "reparaturkosten_nach_pruefung": r.reparaturkosten_nach_pruefung,
            "referenzwerkstatt":        ref_ws,
            "abzuege_detail":           abzuege,
            "ist_image_pdf":            r.ist_image_pdf,
            "parse_konfidenz":          round(r.konfidenz, 3),
            "warnungen":                r.warnungen,
        }

    elif meta.dokumenttyp == "rechnung":
        from ..parsers.rechnung_parser import parse_rechnung
        r = parse_rechnung(norm_text)
        ergebnis = {
            **basis,
            "nettobetrag":    r.nettobetrag,
            "mwst_betrag":    r.mwst_betrag,
            "bruttobetrag":   r.bruttobetrag,
            "rechnungsdatum": r.rechnungsdatum,
            "rechnungsnummer": r.rechnungsnummer,
            "parse_konfidenz": round(r.konfidenz, 3),
            "warnungen":      r.warnungen,
        }

    elif meta.dokumenttyp == "gutachten":
        r = parse_gutachten(norm_text, meta.pruefdienstleister)
        fz = r.fahrzeug
        ergebnis = {
            **basis,
            # SV-Büro & Metadaten
            "sv_buero":             r.sv_buero,
            "gutachter":            r.gutachter,
            "auftragsnummer":       r.auftragsnummer,
            "auftragsdatum":        r.auftragsdatum,
            "besichtigungsdatum":   r.besichtigungsdatum,
            # Versicherung
            "versicherung_name":            r.versicherung_name,
            "versicherungsschein_nummer":   r.versicherungsschein_nummer,
            "schadennummer_versicherung":   r.schadennummer_versicherung,
            # Fahrzeug
            "fahrzeug": {
                "hersteller":      fz.hersteller,
                "typ":             fz.typ,
                "kennzeichen":     fz.kennzeichen,
                "erstzulassung":   fz.erstzulassung,
                "kilometerstand":  fz.kilometerstand,
                "farbe":           fz.farbe,
                "vin":             fz.vin,
            },
            # Schadenart
            "schadenart":                    r.schadenart,
            "abrechnungsart":                r.abrechnungsart,
            "wirtschaftlicher_totalschaden": r.wirtschaftlicher_totalschaden,
            "totalschadengrenze":            r.totalschadengrenze,
            # Kernbeträge → direkt als Schadenpositionen nutzbar
            # Netto und Brutto getrennt für korrekte Vorsteuer-Behandlung
            "schadenpositionen": {
                "reparaturkosten":      r.reparaturkosten_netto or r.reparaturkosten_brutto,
                "rep_gutachten_netto":  r.reparaturkosten_netto,
                "rep_gutachten_mwst":   (r.reparaturkosten_brutto or 0) - (r.reparaturkosten_netto or 0)
                                        if r.reparaturkosten_brutto and r.reparaturkosten_netto else 0,
                "wiederbeschaffung":    r.wiederbeschaffungswert,
                "restwert":             r.restwert,
                "wertminderung":        r.wertminderung,
                "nutzungsausfall":      r.nutzungsausfall_gesamt,
                # SV-Kosten: netto + ust getrennt (Migration 14)
                "sv_kosten":            r.sv_kosten_netto or r.sv_kosten_brutto,
                "sv_kosten_netto":      r.sv_kosten_netto,
                "sv_kosten_ust":        (r.sv_kosten_brutto or 0) - (r.sv_kosten_netto or 0)
                                        if r.sv_kosten_brutto and r.sv_kosten_netto else 0,
            },
            # Rohe Beträge für Detailanzeige
            "reparaturkosten_netto":      r.reparaturkosten_netto,
            "reparaturkosten_brutto":     r.reparaturkosten_brutto,
            "wiederbeschaffungswert":     r.wiederbeschaffungswert,
            "restwert":                   r.restwert,
            "wertminderung":              r.wertminderung,
            "wertverbesserung":           r.wertverbesserung,
            "nutzungsausfall_tagessatz":  r.nutzungsausfall_tagessatz,
            "nutzungsausfall_tage":       r.nutzungsausfall_tage,
            "nutzungsausfall_gesamt":     r.nutzungsausfall_gesamt,
            "sv_kosten_netto":            r.sv_kosten_netto,
            "sv_kosten_brutto":           r.sv_kosten_brutto,
            "parse_konfidenz":            r.konfidenz,
            "warnungen":                  r.warnungen,
        }

    else:
        ergebnis = {
            **basis,
            "parse_konfidenz": 0.0,
            "warnungen": [
                "Dokumenttyp konnte nicht erkannt werden. "
                "Bitte manuell als Abrechnungsschreiben oder Prüfbericht klassifizieren."
            ],
        }

    return ergebnis


# ── Endpunkte ──────────────────────────────────────────────────────────────────

@pdf_parse_bp.route("/parse-pdf", methods=["POST"])
@login_erforderlich
def parse_pdf(akte_id: str):
    """
    POST /akten/<id>/parse-pdf

    Multipart-Form mit Feld "datei" (PDF).
    Returns strukturiertes Parse-Ergebnis ohne DB-Abhängigkeit.
    Schreibt nach erfolgreichem Parse einen Eintrag in die Akten-Chronik.
    """
    if "datei" not in request.files:
        return _err("Kein Datei-Feld 'datei' im Request.")

    datei = request.files["datei"]
    if not datei.filename:
        return _err("Keine Datei ausgewählt.")

    if not datei.filename.lower().endswith(".pdf"):
        return _err("Nur PDF-Dateien werden unterstützt.")

    datei_bytes = datei.read()
    if len(datei_bytes) == 0:
        return _err("Leere Datei.")
    if len(datei_bytes) > 20 * 1024 * 1024:
        return _err("Datei zu groß (max. 20 MB).")

    try:
        ergebnis = _parse_versicherungs_pdf(datei_bytes)
    except Exception as e:
        logger.error("PDF-Parse-Fehler für Akte %d: %s", akte_id, e, exc_info=True)
        return _err(f"PDF konnte nicht verarbeitet werden: {str(e)}", 500)

    # ── Akten-Chronik-Eintrag ──────────────────────────────────────────────
    try:
        from ..models.dokument import logge_aktivitaet

        dokumenttyp = ergebnis.get("dokumenttyp", "unbekannt")
        konfidenz   = ergebnis.get("parse_konfidenz") or ergebnis.get("klassifizier_konfidenz", 0)
        benutzer_id = getattr(g, "benutzer_id", None)

        # Lesbare Bezeichnung je Dokumenttyp
        typ_labels = {
            "gutachten":            "Gutachten",
            "abrechnungsschreiben": "Abrechnungsschreiben",
            "pruefbericht":         "Prüfbericht",
        }
        typ_label = typ_labels.get(dokumenttyp, "PDF-Dokument")

        # Konfidenz als Prozent für die Beschreibung
        konfidenz_pct = f"{round(konfidenz * 100)} %" if konfidenz else "–"

        beschreibung = (
            f"{typ_label} hochgeladen: {datei.filename}"
            f" · Konfidenz {konfidenz_pct}"
        )

        # Ergänze nützliche Parse-Details je Typ
        if dokumenttyp == "gutachten":
            sv = ergebnis.get("sv_buero", "")
            schadenart = ergebnis.get("schadenart", "")
            if sv:
                beschreibung += f" · SV-Büro: {sv}"
            if schadenart:
                beschreibung += f" · {schadenart.capitalize()}"
        elif dokumenttyp == "abrechnungsschreiben":
            versicherer = ergebnis.get("versicherer", "")
            betrag = ergebnis.get("gesamtbetrag")
            if versicherer:
                beschreibung += f" · {versicherer}"
            if betrag:
                beschreibung += f" · {betrag:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
        elif dokumenttyp == "pruefbericht":
            dienstleister = ergebnis.get("pruefdienstleister", "")
            abzug = ergebnis.get("abzug_gesamt")
            if dienstleister:
                beschreibung += f" · {dienstleister}"
            if abzug:
                beschreibung += f" · Abzug: {abzug:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

        logge_aktivitaet(
            aktion=f"pdf_import_{dokumenttyp}",
            beschreibung=beschreibung,
            akte_id=akte_id,
            benutzer_id=benutzer_id,
            tabelle="pdf_parse",
        )
    except Exception as log_err:
        # Logging-Fehler dürfen das Parse-Ergebnis nicht blockieren
        logger.warning("Chronik-Eintrag fehlgeschlagen für Akte %d: %s", akte_id, log_err)

    return jsonify({
        "akte_id": akte_id,
        "dateiname": datei.filename,
        "ergebnis": ergebnis,
    }), 200


@pdf_parse_bp.route("/parse-pdf/eakte/<int:eakte_nr>", methods=["POST"])
@login_erforderlich
def parse_eakte_dokument(akte_id: str, eakte_nr: int):
    """
    POST /akten/<id>/parse-pdf/eakte/<nr>

    Parst ein E-Akte-Dokument (noch nicht lokal importiert).
    Ergebnis wird in rechnung_parse_cache gecacht (Cache-Key: eakte_nr + Dateigroesse).

    Query-Parameter:
      force  "true" → Cache ignorieren und neu parsen
    """
    import json as _json
    from pathlib import Path as _Path
    from ..db.database import get_connection

    force = request.args.get("force", "").lower() == "true"

    try:
        from ..ramicro.eakte_service import hole_eakte_dokument, baue_dateipfad
    except ImportError as e:
        return _err("E-Akte-Modul nicht verfuegbar: %s" % e, 503)

    dok = hole_eakte_dokument(az=akte_id, nr=eakte_nr)
    if not dok:
        return _err("E-Akte-Dokument %d nicht gefunden." % eakte_nr, 404)

    # Routing-Signal bestimmen (Domain-Whitelist → Rubrik → Fallback)
    _domain = (dok.get("absender_domain") or "").lower()
    _rubrik = (dok.get("rubrik") or "").lower()
    routing = _bestimme_routing(_domain, _rubrik)
    if routing["basis"].startswith("fallback"):
        logger.info(
            "E-Akte-Dok %d: routing_basis=%s domain=%r rubrik=%r",
            eakte_nr, routing["basis"], _domain or "(leer)", _rubrik or "(leer)",
        )

    pfad = baue_dateipfad(dok["dateiname"])
    if not pfad:
        return _err(
            "E-Akte Dateizugriff nicht konfiguriert. "
            "EAKTE_BASE_PATH in .env setzen und Volume-Mount einrichten.",
            503,
        )

    try:
        datei_bytes = _Path(pfad).read_bytes()
    except OSError as exc:
        return _err("Datei nicht erreichbar – WSL-Mount pruefen: %s" % exc, 503)

    datei_groesse = len(datei_bytes)
    if datei_groesse == 0:
        return _err("Datei ist leer.", 422)

    # Cache pruefen (ausser force=true)
    if not force:
        try:
            with get_connection() as conn:
                cached = conn.execute(
                    "SELECT ergebnis_json, datei_groesse "
                    "FROM rechnung_parse_cache WHERE eakte_nr = ?",
                    (eakte_nr,),
                ).fetchone()
            if cached and cached["datei_groesse"] == datei_groesse:
                return jsonify({
                    "akte_id":     akte_id,
                    "eakte_nr":    eakte_nr,
                    "dateiname":   dok.get("anzeigename", ""),
                    "aus_cache":   True,
                    "routing_info": routing,
                    "ergebnis":    _json.loads(cached["ergebnis_json"]),
                }), 200
        except Exception as cache_err:
            logger.warning("Cache-Lesen fehlgeschlagen (nicht kritisch): %s", cache_err)

    # Parsen
    try:
        ergebnis = _parse_versicherungs_pdf(datei_bytes)
    except Exception as e:
        logger.error("PDF-Parse-Fehler fuer E-Akte-Dok %d: %s", eakte_nr, e, exc_info=True)
        return _err("PDF konnte nicht verarbeitet werden: %s" % e, 500)

    # In rechnung_parse_cache schreiben
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO rechnung_parse_cache (eakte_nr, datei_groesse, ergebnis_json)
                VALUES (?, ?, ?)
                ON CONFLICT(eakte_nr) DO UPDATE
                SET datei_groesse = excluded.datei_groesse,
                    ergebnis_json = excluded.ergebnis_json,
                    geparst_am    = datetime('now', 'localtime')
                """,
                (eakte_nr, datei_groesse, _json.dumps(ergebnis, ensure_ascii=False)),
            )
            conn.commit()
    except Exception as write_err:
        logger.warning("Cache-Schreiben fehlgeschlagen (nicht kritisch): %s", write_err)

    return jsonify({
        "akte_id":     akte_id,
        "eakte_nr":    eakte_nr,
        "dateiname":   dok.get("anzeigename", ""),
        "aus_cache":   False,
        "routing_info": routing,
        "ergebnis":    ergebnis,
    }), 200


@pdf_parse_bp.route("/parse-pdf/test", methods=["GET"])
@login_erforderlich
def parse_pdf_test(akte_id: str):
    """Einfacher Verbindungstest."""
    return jsonify({"status": "ok", "akte_id": akte_id}), 200


@pdf_parse_bp.route("/parse-pdf/dokument/<int:dok_id>", methods=["POST"])
@login_erforderlich
def parse_pdf_vorhandenes(akte_id: str, dok_id: int):
    """
    POST /akten/<id>/parse-pdf/dokument/<dok_id>

    Parst ein bereits im Dokumenten-Tab vorhandenes PDF.
    Kein Upload nötig – Datei wird vom Disk gelesen.

    Response: identisch mit POST /parse-pdf
    """
    from ..db.database import get_connection
    from pathlib import Path as _Path

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dokumente WHERE id = ? AND akte_id = ?",
            (dok_id, akte_id)
        ).fetchone()

    if not row:
        return _err(f"Dokument {dok_id} nicht gefunden oder gehört nicht zu Akte {akte_id}.", 404)

    if row["dateityp"] != "pdf":
        return _err(f"Dokument {dok_id} ist kein PDF ({row['dateityp']}).", 422)

    pfad = _Path(row["dateipfad"])
    if not pfad.exists():
        return _err(f"Datei nicht auf dem Server gefunden: {pfad}", 404)

    datei_bytes = pfad.read_bytes()
    if len(datei_bytes) == 0:
        return _err("Datei ist leer.", 422)

    try:
        ergebnis = _parse_versicherungs_pdf(datei_bytes)
    except Exception as e:
        logger.error("PDF-Parse-Fehler für Dokument %d: %s", dok_id, e, exc_info=True)
        return _err(f"PDF konnte nicht verarbeitet werden: {str(e)}", 500)

    # Chronik-Eintrag
    try:
        from ..models.dokument import logge_aktivitaet
        dokumenttyp = ergebnis.get("dokumenttyp", "unbekannt")
        konfidenz   = ergebnis.get("parse_konfidenz") or ergebnis.get("klassifizier_konfidenz", 0)
        typ_labels  = {
            "gutachten": "Gutachten",
            "abrechnungsschreiben": "Abrechnungsschreiben",
            "pruefbericht": "Prüfbericht",
        }
        logge_aktivitaet(
            aktion=f"pdf_import_{dokumenttyp}",
            beschreibung=(
                f"{typ_labels.get(dokumenttyp, 'PDF')} aus Dokumenten-Tab importiert:"
                f" {row['dateiname']} · Konfidenz {round(konfidenz * 100)} %"
            ),
            akte_id=akte_id,
            benutzer_id=getattr(g, "benutzer_id", None),
            tabelle="pdf_parse",
        )
    except Exception as log_err:
        logger.warning("Chronik-Eintrag fehlgeschlagen: %s", log_err)

    return jsonify({
        "akte_id":   akte_id,
        "dateiname": row["dateiname"],
        "dok_id":    dok_id,
        "ergebnis":  ergebnis,
    }), 200
