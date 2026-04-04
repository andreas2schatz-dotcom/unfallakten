"""
Modul 7 – Router: E-Mail-Import
=================================
REST-Endpunkte für den E-Mail-Import.

Endpunkte:
  POST /email/import                        Import-Lauf starten
  GET  /email/import/status                 Verbindungsstatus
  GET  /email/import/log                    Import-Log
  GET  /email/import/log/statistik          Zusammenfassung
  POST /email/import/log/<id>/zuordnen      Manuelle Akte-Zuordnung  ← NEU v9
  GET  /email/import/aktensuche            Akten-Suche für Dropdown  ← NEU v9

FIXES v9:
  - Status-Validierung: zugeordnet/nicht_zugeordnet statt verarbeitet/kein_treffer
  - akte_id: bleibt TEXT (az), kein int-Cast mehr
  - ordne_akte_manuell_zu() importiert und eingebunden
"""

import logging
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ..email_import.import_service import (
    fuehre_import_lauf_durch, hole_import_log,
    hole_import_statistik, ordne_akte_manuell_zu,
    importiere_in_akte, loesche_aktion_badge, ImportFehler
)
from ..email_import.imap_client import (
    ist_konfiguriert, teste_verbindung, get_imap_config
)
from ..db.database import get_connection

logger = logging.getLogger(__name__)
email_bp = Blueprint("email", __name__, url_prefix="/email")

ERLAUBTE_STATUS = ("zugeordnet", "nicht_zugeordnet", "fehler", "ignoriert")


def _j(daten, status=200):
    return jsonify(daten), status

def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status


# ── POST /email/import ────────────────────────────────────────────────────────

@email_bp.route("/import", methods=["POST"])
@login_erforderlich
def starte_import():
    """
    POST /email/import
    Startet einen manuellen E-Mail-Import-Lauf.

    Body (optional):
      { "max_nachrichten": 20 }

    Response 200:
      { "verarbeitet", "kein_treffer", "fehler", "ignoriert",
        "anhaenge", "laufzeit_s", "details" }
    """
    daten = request.get_json(silent=True) or {}
    max_n = daten.get("max_nachrichten")
    if max_n is not None:
        try:
            max_n = int(max_n)
            if max_n < 1 or max_n > 200:
                return _err("max_nachrichten muss zwischen 1 und 200 liegen.", 422)
        except (TypeError, ValueError):
            return _err("max_nachrichten muss eine Zahl sein.", 422)

    try:
        bericht = fuehre_import_lauf_durch(
            bearbeiter_id=g.benutzer_id,
            max_nachrichten=max_n,
        )
        return _j(bericht)
    except ImportFehler as e:
        return _err(e.nachricht, e.status_code)
    except Exception as e:
        logger.error("Unerwarteter Import-Fehler: %s", e)
        return _err(f"Interner Fehler: {e}", 500)


# ── GET /email/import/status ──────────────────────────────────────────────────

@email_bp.route("/import/status", methods=["GET"])
@login_erforderlich
def import_status():
    """
    GET /email/import/status

    Response 200:
      { "konfiguriert", "verbindung_ok", "nachricht", "ungelesen",
        "konfiguration": { "host", "port", "user", "folder" } }
    """
    konfiguriert = ist_konfiguriert()

    if not konfiguriert:
        return _j({
            "konfiguriert":  False,
            "verbindung_ok": False,
            "nachricht": (
                "E-Mail-Import nicht konfiguriert. "
                "Bitte EMAIL_HOST, EMAIL_USER und EMAIL_PASSWORD setzen."
            ),
            "ungelesen":     0,
            "konfiguration": None,
        })

    verbindungstest = teste_verbindung()
    cfg = get_imap_config()

    return _j({
        "konfiguriert":  True,
        "verbindung_ok": verbindungstest["ok"],
        "nachricht":     verbindungstest["nachricht"],
        "ungelesen":     verbindungstest.get("ungelesen", 0),
        "konfiguration": {
            "host":   cfg["host"],
            "port":   cfg["port"],
            "user":   cfg["user"],
            "folder": cfg["folder"],
        },
    })


# ── GET /email/import/log ─────────────────────────────────────────────────────

@email_bp.route("/import/log", methods=["GET"])
@login_erforderlich
def import_log():
    """
    GET /email/import/log

    Query-Parameter:
      limit   = 50   (max 200)
      status  = zugeordnet|nicht_zugeordnet|fehler|ignoriert
      akte_id = <az TEXT>

    Response 200:
      { "log": [...], "gesamt": int }
    """
    limit   = min(int(request.args.get("limit", 200)), 500)
    status  = request.args.get("status")
    # FIX: akte_id ist TEXT (az), kein int-Cast
    akte_id = request.args.get("akte_id")

    if status and status not in ERLAUBTE_STATUS:
        return _err(
            f"Ungültiger Status. Erlaubt: {', '.join(ERLAUBTE_STATUS)}", 422
        )

    eintraege = hole_import_log(limit=limit, status=status, akte_id=akte_id)
    # Frontend erwartet key "log"
    return _j({"log": eintraege, "gesamt": len(eintraege)})


# ── GET /email/import/log/statistik ──────────────────────────────────────────

@email_bp.route("/import/log/statistik", methods=["GET"])
@login_erforderlich
def import_statistik():
    """
    GET /email/import/log/statistik

    Response 200:
      { "gesamt", "zugeordnet", "nicht_zugeordnet",
        "fehler", "ignoriert", "letzter_import" }
    """
    return _j(hole_import_statistik())


# ── POST /email/import/log/<id>/zuordnen ─────────────────────────────────────

@email_bp.route("/import/log/<int:log_id>/zuordnen", methods=["POST"])
@login_erforderlich
def log_eintrag_zuordnen(log_id: int):
    """
    POST /email/import/log/<id>/zuordnen
    Ordnet eine ungematchte E-Mail manuell einer Akte zu.

    Body:
      { "az": "31/21" }

    Response 200:
      { "ok": true, "az": "31/21" }

    Response 404:
      { "fehler": "Akte '99/99' nicht gefunden." }

    Response 422:
      { "fehler": "az fehlt im Request-Body." }
    """
    daten = request.get_json(silent=True) or {}
    az = (daten.get("az") or "").strip()

    if not az:
        return _err("az fehlt im Request-Body.", 422)

    ergebnis = ordne_akte_manuell_zu(log_id, az)

    if not ergebnis["ok"]:
        return _err(ergebnis["fehler"], 404)

    return _j(ergebnis)


# ── GET /email/import/aktensuche ──────────────────────────────────────────────

@email_bp.route("/import/aktensuche", methods=["GET"])
@login_erforderlich
def aktensuche_fuer_zuordnung():
    """
    GET /email/import/aktensuche?q=<suchbegriff>
    Sucht Akten fuer das Zuordnungs-Dropdown.
    Reihenfolge: zuerst RA-Micro, dann SQLite als Fallback.

    Query-Parameter:
      q = Suchbegriff (min. 2 Zeichen)

    Response 200:
      { "akten": [{ "az", "label" }, ...] }
    """
    q = (request.args.get("q") or "").strip()

    if len(q) < 2:
        return _j({"akten": []})

    akten = []
    gefundene_az = set()

    # ── 1. RA-Micro suchen ────────────────────────────────────────────────────
    try:
        from ..ramicro.connector import get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        such_muster_sql = f"%{q}%"
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT TOP 20
                    a.sAktenNummer AS az,
                    a.sAktenNummer + COALESCE(' - ' + a.sMandant, '') AS label
                FROM tblAkten a
                WHERE (
                    a.sAktenNummer LIKE %s
                    OR UPPER(a.sMandant) LIKE UPPER(%s)
                    OR UPPER(a.sGegner)  LIKE UPPER(%s)
                    OR UPPER(a.sAktenKurzBezeichnung) LIKE UPPER(%s)
                )
                AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer
                """,
                (such_muster_sql, such_muster_sql, such_muster_sql, such_muster_sql)
            )
            rows = cur.fetchall()
            for r in rows:
                az = r["az"]
                if az and az not in gefundene_az:
                    akten.append({"az": az, "label": r["label"] or az})
                    gefundene_az.add(az)
        logger.debug("Aktensuche RA-Micro: %d Treffer fuer '%s'", len(akten), q)
    except Exception as e:
        logger.debug("Aktensuche RA-Micro nicht verfuegbar: %s", e)

    # ── 2. SQLite als Fallback / Ergaenzung ───────────────────────────────────
    such_muster = f"%{q.upper()}%"
    with get_connection() as conn:
        zeilen = conn.execute(
            """
            SELECT DISTINCT
                a.az,
                a.az || COALESCE(' - ' || b.name, '') AS label
            FROM unfallakte a
            LEFT JOIN beteiligte b
                ON b.akte_id = a.az
                AND b.rolle  = 'mandant'
            WHERE UPPER(a.az) LIKE ?
               OR UPPER(COALESCE(b.name, '')) LIKE ?
               OR UPPER(COALESCE(b.kfz_kennzeichen, '')) LIKE ?
            ORDER BY a.az
            LIMIT 20
            """,
            (such_muster, such_muster, such_muster)
        ).fetchall()

    for z in zeilen:
        if z["az"] not in gefundene_az:
            akten.append({"az": z["az"], "label": z["label"] or z["az"]})
            gefundene_az.add(z["az"])

    # Gesamt max 20 Treffer
    return _j({"akten": akten[:20]})

# ── GET /email/import/log/<id>/dokumente ─────────────────────────────────────

@email_bp.route("/import/log/<int:log_id>/dokumente", methods=["GET"])
@login_erforderlich
def log_eintrag_dokumente(log_id: int):
    """
    GET /email/import/log/<id>/dokumente
    Gibt die gespeicherten Dokumente fuer einen Import-Log-Eintrag zurueck.
    Liest importierte_dok (JSON-Array von dok_ids) und joint mit dokumente.

    Response 200:
      { "dokumente": [{ "id", "dateiname", "dateityp", "dateigroesse", "akte_id" }] }
    """
    import json as _json

    with get_connection() as conn:
        log = conn.execute(
            "SELECT akte_id, importierte_dok FROM email_import_log WHERE id = ?",
            (log_id,)
        ).fetchone()

    if not log:
        return _err("Log-Eintrag nicht gefunden.", 404)

    importierte_dok = log["importierte_dok"]
    if not importierte_dok:
        return _j({"dokumente": []})

    try:
        dok_ids = _json.loads(importierte_dok)
    except (ValueError, TypeError):
        return _j({"dokumente": []})

    if not dok_ids:
        return _j({"dokumente": []})

    platzhalter = ",".join("?" * len(dok_ids))
    with get_connection() as conn:
        zeilen = conn.execute(
            f"""
            SELECT id, dateiname, dateityp, dateigroesse, akte_id
            FROM dokumente
            WHERE id IN ({platzhalter})
            ORDER BY id
            """,
            dok_ids
        ).fetchall()

    return _j({"dokumente": [dict(z) for z in zeilen]})

# ── POST /email/import/log/<id>/in-akte ──────────────────────────────────────

@email_bp.route("/import/log/<int:log_id>/in-akte", methods=["POST"])
@login_erforderlich
def log_in_akte_importieren(log_id: int):
    """
    POST /email/import/log/<id>/in-akte
    Importiert Anhaenge + .eml einer E-Mail in den Dokumentenbereich der Akte.

    Response 200:
      { "ok": true, "dok_ids": [...], "importiert_am": "14:23" }
    Response 400:
      { "fehler": "Keine Akte zugeordnet." }
    """
    try:
        ergebnis = importiere_in_akte(log_id, bearbeiter_id=g.benutzer_id)
        if not ergebnis["ok"]:
            return _err(ergebnis["fehler"], 400)
        return _j(ergebnis)
    except Exception as e:
        logger.error("in-akte Import Fehler: %s", e)
        return _err(f"Interner Fehler: {e}", 500)


# ── Absender-Vorlagen CRUD ────────────────────────────────────────────────────

@email_bp.route("/import/absender-vorlagen", methods=["GET"])
@login_erforderlich
def absender_vorlagen_liste():
    """GET /email/import/absender-vorlagen – Alle Vorlagen."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM email_absender_vorlagen ORDER BY kategorie, name"
        ).fetchall()
    return _j({"vorlagen": [dict(r) for r in rows]})


@email_bp.route("/import/absender-vorlagen", methods=["POST"])
@login_erforderlich
def absender_vorlage_erstellen():
    """POST /email/import/absender-vorlagen – Neue Vorlage anlegen."""
    d = request.get_json(silent=True) or {}
    name             = (d.get("name") or "").strip()
    domain           = (d.get("domain") or "").strip().lower().lstrip("@")
    kategorie        = (d.get("kategorie") or "sonstiges").strip()
    notizen          = (d.get("notizen") or "").strip() or None
    versicherer_name = (d.get("versicherer_name") or "").strip() or None
    kuerzel          = (d.get("kuerzel") or "").strip().upper() or None

    if not name:
        return _err("name ist erforderlich.", 422)
    if not domain or "." not in domain:
        return _err("domain ist erforderlich (z.B. gutachter-xyz.de).", 422)
    if kategorie not in ("gutachter", "versicherung", "gericht", "sonstiges"):
        return _err("Ungueltige Kategorie.", 422)

    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO email_absender_vorlagen "
                "(name, domain, kategorie, notizen, versicherer_name, kuerzel) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, domain, kategorie, notizen, versicherer_name, kuerzel)
            )
            neu = conn.execute(
                "SELECT * FROM email_absender_vorlagen WHERE domain = ?", (domain,)
            ).fetchone()
        return _j(dict(neu)), 201
    except Exception as e:
        if "UNIQUE" in str(e):
            return _err(f"Domain '{domain}' ist bereits vorhanden.", 409)
        return _err(str(e), 500)


@email_bp.route("/import/absender-vorlagen/<int:vid>", methods=["PATCH"])
@login_erforderlich
def absender_vorlage_aktualisieren(vid: int):
    """PATCH /email/import/absender-vorlagen/<id> – Vorlage aktualisieren."""
    d = request.get_json(silent=True) or {}
    felder = {}
    if "name"             in d: felder["name"]             = d["name"].strip()
    if "domain"           in d: felder["domain"]            = d["domain"].strip().lower().lstrip("@")
    if "kategorie"        in d: felder["kategorie"]         = d["kategorie"].strip()
    if "notizen"          in d: felder["notizen"]           = d["notizen"].strip() or None
    if "aktiv"            in d: felder["aktiv"]             = 1 if d["aktiv"] else 0
    if "versicherer_name" in d: felder["versicherer_name"]  = d["versicherer_name"].strip() or None
    if "kuerzel"          in d: felder["kuerzel"]           = d["kuerzel"].strip().upper() or None

    if not felder:
        return _err("Keine Felder angegeben.", 422)

    set_sql = ", ".join(f"{k} = ?" for k in felder)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE email_absender_vorlagen SET {set_sql} WHERE id = ?",
            (*felder.values(), vid)
        )
        aktu = conn.execute(
            "SELECT * FROM email_absender_vorlagen WHERE id = ?", (vid,)
        ).fetchone()

    if not aktu:
        return _err("Vorlage nicht gefunden.", 404)
    return _j(dict(aktu))


@email_bp.route("/import/absender-vorlagen/<int:vid>", methods=["DELETE"])
@login_erforderlich
def absender_vorlage_loeschen(vid: int):
    """DELETE /email/import/absender-vorlagen/<id> – Vorlage loeschen."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM email_absender_vorlagen WHERE id = ?", (vid,)
        )
    return _j({"ok": True})

# ── POST /email/import/log/<id>/regulierung-bestaetigen ──────────────────────

@email_bp.route("/import/log/<int:log_id>/regulierung-bestaetigen", methods=["POST"])
@login_erforderlich
def regulierung_bestaetigen(log_id: int):
    """
    POST /email/import/log/<id>/regulierung-bestaetigen
    Importiert einen Regulierungsschreiben-Anhang als Abrechnungsschreiben.
    Wird nach manueller Bestaetigung im Frontend aufgerufen.

    Response 200:
      { "ok": true, "abrechnung_id": int, "parse_konfidenz": float }
    Response 400:
      { "fehler": "..." }
    """
    import json as _json

    with get_connection() as conn:
        log = conn.execute(
            """
            SELECT id, akte_id, eml_pfad, importierte_dok, email_typ,
                   anhaenge_anzahl
            FROM email_import_log WHERE id = ?
            """,
            (log_id,)
        ).fetchone()

    if not log:
        return _err("Log-Eintrag nicht gefunden.", 404)
    if not log["akte_id"]:
        return _err("Keine Akte zugeordnet. Bitte zuerst Akte zuordnen.", 400)

    akte_id = log["akte_id"]

    # Dokument-IDs aus Log lesen
    dok_ids = []
    if log["importierte_dok"]:
        try:
            dok_ids = _json.loads(log["importierte_dok"])
        except (ValueError, TypeError):
            dok_ids = []

    if not dok_ids:
        return _err(
            "Keine gespeicherten Anhaenge gefunden. "
            "Bitte zuerst 'In Akte importieren' klicken.", 400
        )

    # PDF-Anhang finden und parsen
    with get_connection() as conn:
        pdf_dok = conn.execute(
            f"""
            SELECT id, dateipfad, dateiname, parse_json, parse_konfidenz
            FROM dokumente
            WHERE id IN ({','.join('?' * len(dok_ids))})
              AND dateityp = 'pdf'
            ORDER BY id LIMIT 1
            """,
            dok_ids
        ).fetchone()

    if not pdf_dok:
        return _err("Kein PDF-Anhang gefunden.", 400)

    # Parse-Ergebnis lesen
    parse_data = {}
    if pdf_dok["parse_json"]:
        try:
            parse_data = _json.loads(pdf_dok["parse_json"])
        except (ValueError, TypeError):
            pass

    if not parse_data:
        # PDF nochmal parsen
        from ..pdf.upload_service import starte_pdf_parsing
        parse_result = starte_pdf_parsing(pdf_dok["id"], akte_id)
        if parse_result:
            parse_data = parse_result

    # Abrechnungsschreiben erstellen
    try:
        from ..models.abrechnungsschreiben import erstelle_abrechnungsschreiben
        from datetime import datetime as _dt

        # Positionen aus Parse-Ergebnis aufbauen
        positionen = _parse_zu_positionen(parse_data)

        # Datum aus Parse-Ergebnis oder heute
        datum_raw = parse_data.get("unfalldatum") or _dt.now().strftime("%Y-%m-%d")
        try:
            _dt.strptime(datum_raw, "%Y-%m-%d")
            datum = datum_raw
        except ValueError:
            datum = _dt.now().strftime("%Y-%m-%d")

        ab = erstelle_abrechnungsschreiben(
            akte_id=akte_id,
            datum=datum,
            haftungsart="vollhaftung",
            haftungsquote=100.0,
            bearbeiter_id=g.benutzer_id,
            versicherung=None,
            referenz_nr=parse_data.get("vers_referenz"),
            notizen=f"Automatisch importiert aus E-Mail (Log-ID {log_id})",
            dokument_id=pdf_dok["id"],
            positionen=positionen,
        )

        # Log-Eintrag: regulierung_bestaetigt setzen
        with get_connection() as conn:
            conn.execute(
                "UPDATE email_import_log SET in_akte_importiert = 1 WHERE id = ?",
                (log_id,)
            )

        logger.info(
            "Regulierungsschreiben bestaetigt: Log %d -> Akte %s, Abrechnung %d",
            log_id, akte_id, ab.id
        )

        return _j({
            "ok":             True,
            "abrechnung_id":  ab.id,
            "parse_konfidenz": pdf_dok["parse_konfidenz"] or 0.0,
            "positionen":     len(positionen),
        })

    except Exception as e:
        logger.error("Regulierung-Bestaetigung Fehler: %s", e)
        return _err(f"Fehler beim Erstellen des Abrechnungsschreibens: {e}", 500)


def _parse_zu_positionen(parse_data: dict) -> list:
    """Konvertiert PDF-Parse-Ergebnis in Abrechnungsschreiben-Positionen."""
    from ..models.abrechnungsschreiben import POSITION_KEYS

    FELD_MAP = {
        "reparaturkosten":   "rep_gutachten_netto",
        "wiederbeschaffung": "rep_gutachten_netto",
        "sv_kosten":         "sv_kosten",
        "nutzungsausfall":   "nutzungsausfall",
        "mietwagenkosten":   "mietwagenkosten",
        "wertminderung":     "wertminderung",
        "abschleppkosten":   "abschleppkosten",
        "standkosten":       "standkosten",
        "anabmeldekosten":   "anabmeldekosten",
        "schmerzensgeld":    "schmerzensgeld",
        "betrag_reguliert":  None,  # Sonderbehandlung unten
    }

    positionen = []
    gesamt_reguliert = parse_data.get("betrag_reguliert")

    for pdf_feld, pos_key in FELD_MAP.items():
        if pdf_feld == "betrag_reguliert":
            continue
        if pos_key not in POSITION_KEYS:
            continue
        wert = parse_data.get(pdf_feld)
        if not wert or float(wert) <= 0:
            continue
        positionen.append({
            "position_key":      pos_key,
            "betrag_gefordert":  float(wert),
            "betrag_reguliert":  float(wert) if gesamt_reguliert else 0.0,
        })

    return positionen


# ── POST /akten/<az>/aktion-erledigt ─────────────────────────────────────────

@email_bp.route("/akten/<path:az>/aktion-erledigt", methods=["POST"])
@login_erforderlich
def aktion_erledigt(az: str):
    """
    POST /akten/<az>/aktion-erledigt
    Loescht den Aktion-Badge von einer Akte.

    Response 200: { "ok": true }
    """
    loesche_aktion_badge(az)
    return _j({"ok": True})

# ── GET /email/import/log/<id>/anhang/<index> ─────────────────────────────────

@email_bp.route("/import/log/<int:log_id>/anhang/<int:index>", methods=["GET"])
@login_erforderlich
def log_anhang_streamen(log_id: int, index: int):
    """
    GET /email/import/log/<id>/anhang/<index>
    Streamt einen Anhang direkt aus der .eml-Datei.
    Funktioniert auch ohne gespeichertes Dokument in der Akte.

    Response: Datei-Bytes mit korrektem MIME-Type
    """
    import io, email as _email, email.policy as _policy

    with get_connection() as conn:
        log = conn.execute(
            "SELECT eml_pfad, importierte_dok FROM email_import_log WHERE id = ?",
            (log_id,)
        ).fetchone()

    if not log:
        return _err("Log-Eintrag nicht gefunden.", 404)

    # Erst: gespeichertes Dokument verwenden wenn vorhanden
    import json as _json
    from pathlib import Path as _Path
    from flask import send_file as _send_file

    if log["importierte_dok"]:
        try:
            dok_ids = _json.loads(log["importierte_dok"])
            if index < len(dok_ids):
                with get_connection() as conn:
                    dok = conn.execute(
                        "SELECT * FROM dokumente WHERE id = ?",
                        (dok_ids[index],)
                    ).fetchone()
                if dok and _Path(dok["dateipfad"]).exists():
                    from ..pdf.upload_service import hole_dokument_datei
                    result = hole_dokument_datei(dok["id"])
                    if result:
                        datei_bytes, dateiname, dateityp = result
                        mime_map = {
                            "pdf": "application/pdf",
                            "jpg": "image/jpeg",
                            "png": "image/png",
                            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        }
                        mime = mime_map.get(dateityp, "application/octet-stream")
                        return _send_file(
                            io.BytesIO(datei_bytes),
                            mimetype=mime,
                            as_attachment=False,
                            download_name=dateiname,
                        )
        except Exception as e:
            logger.debug("Gespeichertes Dokument nicht nutzbar: %s", e)

    # Fallback: Direkt aus .eml extrahieren
    eml_pfad = log["eml_pfad"]
    if not eml_pfad or not _Path(eml_pfad).exists():
        return _err("Anhang nicht verfuegbar.", 404)

    try:
        raw = _Path(eml_pfad).read_bytes()
        msg = _email.message_from_bytes(raw, policy=_policy.default)

        ERLAUBTE = {"pdf", "jpg", "jpeg", "png", "docx"}
        anhaenge = []
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            fn = part.get_filename()
            if not fn or "attachment" not in cd:
                continue
            ext = _Path(fn).suffix.lstrip(".").lower()
            if ext not in ERLAUBTE:
                continue
            daten = part.get_payload(decode=True)
            if daten:
                anhaenge.append((fn, ext, daten))

        if index >= len(anhaenge):
            return _err(f"Anhang {index} nicht gefunden (nur {len(anhaenge)} vorhanden).", 404)

        dateiname, ext, daten = anhaenge[index]
        mime_map = {
            "pdf":  "application/pdf",
            "jpg":  "image/jpeg",
            "jpeg": "image/jpeg",
            "png":  "image/png",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        return _send_file(
            io.BytesIO(daten),
            mimetype=mime,
            as_attachment=False,
            download_name=dateiname,
        )

    except Exception as e:
        logger.error("Anhang-Stream Fehler: %s", e)
        return _err(f"Fehler beim Lesen des Anhangs: {e}", 500)

# ── GET /email/import/log/<id>/meta ──────────────────────────────────────────

@email_bp.route("/import/log/<int:log_id>/meta", methods=["GET"])
@login_erforderlich
def log_eintrag_meta(log_id: int):
    """
    GET /email/import/log/<id>/meta
    Gibt Anhang-Metadaten und Body-Text direkt aus der .eml-Datei zurueck.

    Response 200:
      {
        "anhaenge": [{ "index": 0, "name": "...", "ext": "pdf", "groesse": 12345, "oeffenbar": true }],
        "body_text": "..." (erste 1000 Zeichen des lesbaren Textes)
      }
    """
    import email as _email, email.policy as _pol, email.header as _hdr
    from pathlib import Path as _P
    import re as _re

    with get_connection() as conn:
        log = conn.execute(
            "SELECT eml_pfad FROM email_import_log WHERE id = ?",
            (log_id,)
        ).fetchone()

    if not log or not log["eml_pfad"] or not _P(log["eml_pfad"]).exists():
        return _j({"anhaenge": [], "body_text": ""})

    ERLAUBTE = {"pdf", "jpg", "jpeg", "png", "docx"}

    try:
        raw = _P(log["eml_pfad"]).read_bytes()
        msg = _email.message_from_bytes(raw, policy=_pol.default)

        # Anhang-Metadaten
        anhaenge = []
        anh_index = 0
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            fn = part.get_filename()
            if not fn or "attachment" not in cd:
                continue
            # Dateiname dekodieren
            decoded = ""
            for teil, charset in _hdr.decode_header(fn):
                if isinstance(teil, bytes):
                    decoded += teil.decode(charset or "utf-8", errors="replace")
                else:
                    decoded += str(teil)
            ext = _P(decoded).suffix.lstrip(".").lower()
            payload = part.get_payload(decode=True) or b""
            oeffenbar = ext in ERLAUBTE
            if oeffenbar:  # nur erlaubte Typen anzeigen
                anhaenge.append({
                    "index":    anh_index,
                    "name":     decoded,
                    "ext":      ext,
                    "groesse":  len(payload),
                    "oeffenbar": True,
                })
            anh_index += 1

        # Body-Text extrahieren
        body_text = ""
        for part in msg.walk():
            ct  = part.get_content_type()
            cd2 = str(part.get("Content-Disposition", ""))
            if "attachment" in cd2:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            if ct == "text/plain":
                if payload[:2] in (b"\xff\xfe", b"\xfe\xff"):
                    try: decoded_body = payload.decode("utf-16", errors="replace")
                    except: decoded_body = payload.decode(charset, errors="replace")
                else:
                    decoded_body = payload.decode(charset, errors="replace")
                # Lesbarkeit pruefen
                lesbar = sum(1 for c in decoded_body[:200] if c.isprintable() or c in "\n\r\t")
                if lesbar > len(decoded_body[:200]) * 0.5:
                    body_text = decoded_body[:1500]
                    break
            elif ct == "text/html" and not body_text:
                decoded_body = payload.decode(charset, errors="replace")
                # HTML-Tags entfernen
                text = _re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "",
                               decoded_body, flags=_re.IGNORECASE | _re.DOTALL)
                text = _re.sub(r"<(br|p|div|tr)[^>]*>", "\n", text, flags=_re.IGNORECASE)
                text = _re.sub(r"<[^>]+>", " ", text)
                text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace(
                    "&gt;", ">").replace("&amp;", "&")
                text = _re.sub(r"[ \t]+", " ", text)
                text = _re.sub(r"\n{3,}", "\n\n", text)
                body_text = text.strip()[:1500]

        return _j({"anhaenge": anhaenge, "body_text": body_text.strip()})

    except Exception as e:
        logger.error("log_eintrag_meta Fehler: %s", e)
        return _j({"anhaenge": [], "body_text": ""})


# ── GET /email/fragebogen-erstkontakt ─────────────────────────────────────────

@email_bp.route("/fragebogen-erstkontakt", methods=["GET"])
@login_erforderlich
def fragebogen_erstkontakt_liste():
    """
    GET /email/fragebogen-erstkontakt
    Gibt Fragebogen-Erstkontakte zurueck (Standard: status='neu').

    Query-Parameter:
      status = neu|bearbeitet|akte_angelegt  (default: neu)

    Response 200:
      { "eintraege": [...], "gesamt": int }
    """
    status = request.args.get("status", "neu")
    erlaubt = ("neu", "bearbeitet", "akte_angelegt")
    if status not in erlaubt:
        return _err(f"Ungueltiger Status. Erlaubt: {', '.join(erlaubt)}", 422)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM fragebogen_erstkontakt WHERE status = ? ORDER BY empfangen_am DESC",
            (status,)
        ).fetchall()
    return _j({"eintraege": [dict(r) for r in rows], "gesamt": len(rows)})


# ── PATCH /email/fragebogen-erstkontakt/<id>/status ───────────────────────────

@email_bp.route("/fragebogen-erstkontakt/<int:ek_id>/status", methods=["PATCH"])
@login_erforderlich
def fragebogen_erstkontakt_status_setzen(ek_id: int):
    """
    PATCH /email/fragebogen-erstkontakt/<id>/status
    Setzt den Status eines Fragebogen-Erstkontakts.

    Body:
      { "status": "bearbeitet" }

    Response 200: aktualisierter Eintrag als JSON
    Response 422: Ungueltiger Status
    Response 404: Eintrag nicht gefunden
    """
    daten = request.get_json(silent=True) or {}
    neuer_status = (daten.get("status") or "").strip()
    erlaubt = ("neu", "bearbeitet", "akte_angelegt")
    if neuer_status not in erlaubt:
        return _err(f"Ungueltiger Status. Erlaubt: {', '.join(erlaubt)}", 422)

    with get_connection() as conn:
        conn.execute(
            "UPDATE fragebogen_erstkontakt SET status = ? WHERE id = ?",
            (neuer_status, ek_id)
        )
        eintrag = conn.execute(
            "SELECT * FROM fragebogen_erstkontakt WHERE id = ?", (ek_id,)
        ).fetchone()

    if not eintrag:
        return _err("Eintrag nicht gefunden.", 404)
    return _j(dict(eintrag))
