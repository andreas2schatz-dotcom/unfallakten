"""
Modul 8 – Router: Wiedervorlage / Sachstandsanfragen
======================================================
Endpunkte:

    GET  /wiedervorlage/status
        Prüft ob RA-Micro Verbindung aktiv ist.

    GET  /wiedervorlage/
        Gibt alle fälligen Wiedervorlagen (Stellungnahme Gegner) zurück.
        Query-Parameter:
            ?nur_heute=true     nur exakt heute fällige
            ?sb=AS              nach Sachbearbeiter-Kürzel filtern

    POST /wiedervorlage/<guid>/sachstandsanfrage
        Generiert Word-Dokument für eine Wiedervorlage + Aktivitätseintrag.
        Download als .docx.

    GET  /wiedervorlage/statistik
        Übersicht aller offenen WV-Gründe (für Dashboard).
"""

import logging
from flask import Blueprint, jsonify, request, g, send_file
import io

from ..auth.middleware import login_erforderlich
from ..ramicro.connector import (
    verbindung_pruefen,
    RaMicroNichtAktiv,
    RaMicroVerbindungsFehler,
)
from ..ramicro.wiedervorlage_service import (
    hole_aktenbeteiligte,
    _loeseWvGrund,
    hole_faellige_wiedervorlagen,
    hole_wiedervorlage_details,
    hole_wiedervorlagen_statistik,
)
from ..word.sachstandsanfrage_wv import (
    generiere_sachstandsanfrage_wv,
    dateiname_generieren,
)
from ..models.dokument import logge_aktivitaet
from ..word.word_service import name_aus_ramicro_adresse

logger = logging.getLogger(__name__)


def _az_vollstaendig(az_raw: str, sb_kuerzel: str) -> str:
    """
    RA-Micro speichert Aktenzeichen ohne Sachbearbeiter-Kürzel ("1213/25").
    Für Anzeige wird das Kürzel wieder angehängt ("1213/25AS").
    """
    if sb_kuerzel and not az_raw.upper().endswith(sb_kuerzel.upper()):
        return az_raw + sb_kuerzel
    return az_raw


wiedervorlage_bp = Blueprint("wiedervorlage", __name__, url_prefix="/wiedervorlage")


def _j(daten, status=200):
    return jsonify(daten), status


def _err(msg, status=400, **extra):
    return jsonify({"fehler": msg, **extra}), status


def _ramicro_fehler_antwort(e: Exception):
    """Einheitliche Fehlerbehandlung für RA-Micro Fehler."""
    if isinstance(e, RaMicroNichtAktiv):
        return _err(
            "RA-Micro Verbindung ist nicht aktiviert. "
            "RAMICRO_AKTIV=true in .env setzen.",
            status=503,
            code="RAMICRO_NICHT_AKTIV",
        )
    if isinstance(e, RaMicroVerbindungsFehler):
        return _err(
            f"RA-Micro nicht erreichbar: {e}",
            status=503,
            code="RAMICRO_VERBINDUNG_FEHLER",
        )
    logger.exception("Unerwarteter Fehler bei RA-Micro Abfrage")
    return _err("Interner Fehler bei RA-Micro Abfrage.", status=500)


# ── GET /wiedervorlage/status ─────────────────────────────────────────────────

@wiedervorlage_bp.route("/status", methods=["GET"])
@login_erforderlich
def verbindung_status():
    """
    GET /wiedervorlage/status

    Prüft die RA-Micro Verbindung.

    Response 200:
        { "status": "ok",          "host": "192.168.1.x", "datenbank": "RAMICRO" }
        { "status": "deaktiviert", "meldung": "..." }
        { "status": "fehler",      "meldung": "..." }
    """
    status = verbindung_pruefen()
    http_code = 200 if status["status"] in ("ok", "deaktiviert") else 503
    return _j(status, http_code)


# ── GET /wiedervorlage/ ───────────────────────────────────────────────────────

@wiedervorlage_bp.route("/", methods=["GET"])
@login_erforderlich
def liste_wiedervorlagen():
    """
    GET /wiedervorlage/

    Alle fälligen Wiedervorlagen mit Grund 'Stellungnahme Gegner'.

    Query-Parameter:
        nur_heute   (bool, default false)  Nur exakt heute fällige
        sb          (string)               Sachbearbeiter-Kürzel filtern (z.B. AS)
        limit       (int, default 200)     Max. Ergebnisse

    Response 200:
        {
          "anzahl": 12,
          "wiedervorlagen": [
            {
              "guid":             "55F4DD24-...",
              "datum":            "2026-03-18",
              "grund":            "Stellungnahme Gegner?schieben!",
              "bemerkung":        "...",
              "sachbearbeiter":   "TB",
              "aktenzeichen":     "62260/25TB",
              "kurzbezeichnung":  "Müller ./. KRAVAG",
              "mandant":          "Müller, Hans",
              "anrede":           r.get("adr_anrede") or "",
            "gegner_hv_name":   "KRAVAG Versicherung",
              "gegner_hv_email":  "schaden@kravag.de",
              "gegner_hv_ort":    "Hamburg",
              "betreff1":         "Schadennummer KH-123456",
              "betreff2":         "KH-Schaden vom 15.01.2026",
              "bereits_generiert": false
            },
            ...
          ]
        }
    """
    nur_heute      = request.args.get("nur_heute", "false").lower() == "true"
    alle_gruende   = request.args.get("alle_gruende", "false").lower() == "true"
    alle_daten     = request.args.get("alle_daten", "false").lower() == "true"
    sb             = request.args.get("sb") or None
    grund_filter   = request.args.get("grund") or None
    az             = request.args.get("az") or None
    try:
        limit = min(int(request.args.get("limit", "200")), 500)
    except ValueError:
        return _err("Parameter 'limit' muss eine ganze Zahl sein.", 400)

    try:
        rows = hole_faellige_wiedervorlagen(
            nur_heute=nur_heute,
            sachbearbeiter=sb,
            limit=limit,
            nur_stellungnahme=not alle_gruende,
            grund_filter=grund_filter,
            aktenzeichen=az,
            alle_daten=alle_daten,
        )
    except Exception as e:
        return _ramicro_fehler_antwort(e)

    # Aufbereiten für Frontend
    ergebnis = []
    for r in rows:
        ergebnis.append({
            "guid":             r.get("GUIDWiedervorlage"),
            "datum":            r["dtWiedervorlage"].strftime("%Y-%m-%d")
                                if r.get("dtWiedervorlage") else None,
            "grund":            _loeseWvGrund(r.get("sWiedervorlagegrund", ""), r.get("iWiedervorlageGrund")),
            "bemerkung":        r.get("wv_bemerkung", ""),
            "sachbearbeiter":   r.get("wv_sachbearbeiter_kuerzel", ""),
            "aktenzeichen":     _az_vollstaendig(r.get("sAktenNummer", ""),
                                                     r.get("akte_sachbearbeiter_kuerzel", "")),
            "kurzbezeichnung":  r.get("sAktenKurzBezeichnung", ""),
            "bezeichnung":      r.get("sAktenBezeichnung", ""),
            "referat":          r.get("iReferat") or 0,
            "mandant":          r.get("sMandant", ""),
            "anrede":           r.get("adr_anrede") or "",
            "gegner_hv_name":   ((r.get("adr_vorname") or "") + " " + (r.get("adr_name") or "")).strip() or r.get("adr_name") or r.get("sGegner", ""),
            "gegner_hv_strasse":r.get("adr_strasse", ""),
            "gegner_hv_plz":    r.get("adr_plz", ""),
            "gegner_hv_ort":    r.get("adr_ort", ""),
            "gegner_hv_email":  r.get("adr_email", ""),
            "betreff1":         r.get("sBetreffZeile1", ""),
            "betreff2":         r.get("sBetreffZeile2", ""),
            "betreff3":         r.get("sBetreffZeile3", ""),
        })

    return _j({"anzahl": len(ergebnis), "wiedervorlagen": ergebnis})


# ── POST /wiedervorlage/<guid>/sachstandsanfrage ──────────────────────────────

@wiedervorlage_bp.route("/<guid>/sachstandsanfrage", methods=["POST"])
@login_erforderlich
def generiere_sachstandsanfrage(guid: str):
    """
    POST /wiedervorlage/<guid>/sachstandsanfrage

    Generiert eine Sachstandsanfrage als Word-Dokument.

    Aktionen:
      1. Wiedervorlage-Details aus RA-Micro abrufen
      2. Word-Dokument generieren (exaktes Kanzlei-Format)
      3. Aktivitätseintrag in lokale Unfallakten-DB schreiben
      4. Direkt-Download der .docx-Datei

    Response 200:
        Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
        Content-Disposition: attachment; filename="1213-25AS_sachstandsanfrage_2026-03-12.docx"

    Response 404: Wiedervorlage nicht gefunden
    Response 503: RA-Micro nicht erreichbar
    """
    adress_nr = None
    if request.is_json and request.json:
        adress_nr = request.json.get("adress_nr")
        if adress_nr is not None:
            try:
                adress_nr = int(adress_nr)
            except (ValueError, TypeError):
                adress_nr = None

    try:
        wv = hole_wiedervorlage_details(guid, adress_nr=adress_nr)
    except Exception as e:
        return _ramicro_fehler_antwort(e)

    if not wv:
        return _err(f"Wiedervorlage mit GUID '{guid}' nicht gefunden.", 404)

    # Word generieren
    try:
        docx_bytes = generiere_sachstandsanfrage_wv(wv)
    except Exception as e:
        logger.exception("Word-Generierung fehlgeschlagen für WV %s", guid)
        return _err(f"Dokument konnte nicht generiert werden: {e}", 500)

    # Aktivitätseintrag (in lokale SQLite-DB – kein Schreibzugriff auf RA-Micro)
    sb_kuerzel = wv.get("akte_sachbearbeiter_kuerzel") or ""
    az        = _az_vollstaendig(wv.get("sAktenNummer", ""), sb_kuerzel)
    empfaenger = (name_aus_ramicro_adresse(wv.get("adr_name"),
                                           wv.get("sErsteAdresszeile")) or
                  wv.get("sGegner") or "")
    try:
        benutzer_id = getattr(g, "benutzer", {}).get("id") if hasattr(g, "benutzer") else None
        logge_aktivitaet(
            aktion="sachstandsanfrage_wv",
            beschreibung=(
                f"Sachstandsanfrage generiert für AZ {az} "
                f"an {empfaenger} (WV-Grund: {wv.get('sWiedervorlagegrund', '')})"
            ),
            akte_id=None,          # Akte nur in RA-Micro → keine lokale akte_id
            benutzer_id=benutzer_id,
            tabelle="ramicro_wiedervorlage",
            datensatz_id=None,
            aenderung_json=None,
        )
    except Exception as e:
        # Aktivitätslog-Fehler ist nicht kritisch – Download trotzdem senden
        logger.warning("Aktivitätslog fehlgeschlagen: %s", e)

    # Download senden
    dateiname = dateiname_generieren(az)
    return send_file(
        io.BytesIO(docx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=dateiname,
    )


# ── GET /wiedervorlage/statistik ──────────────────────────────────────────────

@wiedervorlage_bp.route("/statistik", methods=["GET"])
@login_erforderlich
def statistik():
    """
    GET /wiedervorlage/statistik

    Übersicht aller offenen WV-Gründe nach Häufigkeit.
    Nützlich für das Dashboard.

    Response 200:
        {
          "gruppen": [
            { "sWiedervorlagegrund": "Stellungnahme Gegner?schieben!", "anzahl": 8, ... },
            ...
          ]
        }
    """
    try:
        return _j(hole_wiedervorlagen_statistik())
    except Exception as e:
        return _ramicro_fehler_antwort(e)


# ── GET /wiedervorlage/bereits-erstellt ───────────────────────────────────────

@wiedervorlage_bp.route("/bereits-erstellt", methods=["GET"])
@login_erforderlich
def bereits_erstellt():
    """
    GET /wiedervorlage/bereits-erstellt

    Gibt alle Aktenzeichen zurück, für die im Aktivitätslog bereits
    eine Sachstandsanfrage (aktion='sachstandsanfrage_wv') eingetragen ist.
    Wird vom Frontend verwendet um den ✓/✗-Marker in der WV-Liste zu setzen.

    Response 200:
        { "aktenzeichen": ["1213/25AS", "62260/25TB", ...] }
    """
    from ..db.database import get_connection
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT DISTINCT beschreibung
                FROM aktivitaeten
                WHERE aktion = 'sachstandsanfrage_wv'
            """).fetchall()
    except Exception as e:
        logger.exception("Fehler beim Laden des Aktivitätslogs")
        return _err("Interner Fehler beim Laden des Aktivitätslogs.", 500)

    # Aktenzeichen aus der Beschreibung extrahieren
    # Format: "Sachstandsanfrage generiert für AZ 1213/25AS an ..."
    import re
    az_set = set()
    for row in rows:
        beschreibung = row[0] or ""
        m = re.search(r"für AZ ([^\s]+)", beschreibung)
        if m:
            az_set.add(m.group(1))

    return _j({"aktenzeichen": sorted(az_set)})


# ── Vorauswahl-Logik ──────────────────────────────────────────────────────────

REFERAT_VERKEHRSUNFALL = {4}   # RA-Micro Referat 04 = Verkehrsunfallsachen


def _berechne_vorauswahl(grund: str, bezeichnung: str, beteiligte: list, referat: int = 0) -> int | None:
    """
    Berechnet die optimale Adressaten-Vorauswahl anhand WV-Grund + Referat.

    Regeln:
      - "Stellungnahme Gegner" + Referat 14  → GHPV > G1 > G2 > G3 (iBeteiligtenArt=2)
      - "Stellungnahme Gegner" (sonstige)    → G1 > G2 > G3 > GHPV  (iBeteiligtenArt=2)
      - "Stellungnahme Mandant"              → M > M1 > M2           (iBeteiligtenArt=1)
      - "Stellungnahme SV" / "Gutachten"     → SV > SVR              (alle Arten)
      - Sonstige                             → erster Beteiligter
    """
    if not beteiligte:
        return None

    g = (grund or "").lower()
    ist_unfall = int(referat) in REFERAT_VERKEHRSUNFALL

    def _find(kennzeichen_prio: list, art_filter: int | None = None) -> int | None:
        for kz in kennzeichen_prio:
            for b in beteiligte:
                if art_filter and b.get("art") != art_filter:
                    continue
                if (b.get("kennzeichen") or "").upper() == kz.upper():
                    return b.get("adress_nr")
        return None

    if "gegner" in g or "schieben" in g:
        if ist_unfall:
            prio = ["GHPV", "G1", "G2", "G3"]
        else:
            prio = ["G1", "G2", "G3", "GHPV"]
        result = _find(prio, art_filter=2)
        if result:
            return result
        # Fallback: irgendein Beteiligter mit art=2
        for b in beteiligte:
            if b.get("art") == 2:
                return b.get("adress_nr")

    elif "mandant" in g:
        prio = ["M", "M1", "M2", "M3"]
        result = _find(prio, art_filter=1)
        if result:
            return result
        for b in beteiligte:
            if b.get("art") == 1:
                return b.get("adress_nr")

    elif "sv" in g or "sachverständig" in g or "sachverstaendig" in g or "gutachten" in g:
        prio = ["SV", "SVR", "SV1", "SV2"]
        result = _find(prio)
        if result:
            return result

    # Allgemeiner Fallback: erster Eintrag
    return beteiligte[0].get("adress_nr") if beteiligte else None


# ── GET /wiedervorlage/<guid>/beteiligte ──────────────────────────────────────

@wiedervorlage_bp.route("/<guid>/beteiligte", methods=["GET"])
@login_erforderlich
def get_aktenbeteiligte(guid: str):
    """
    GET /wiedervorlage/<guid>/beteiligte

    Gibt alle aktiven Beteiligten der Akte zurück (für Adressaten-Dropdown).
    """
    # WV-Daten für Vorauswahl ermitteln (Grund + Referat)
    grund       = request.args.get("grund", "")
    bezeichnung = request.args.get("bezeichnung", "")
    try:
        referat = int(request.args.get("referat", "0"))
    except ValueError:
        referat = 0

    try:
        beteiligte = hole_aktenbeteiligte(guid)
    except Exception as e:
        return _ramicro_fehler_antwort(e)

    vorauswahl_nr = _berechne_vorauswahl(grund, bezeichnung, beteiligte, referat=referat)
    return _j({"beteiligte": beteiligte, "vorauswahl_adress_nr": vorauswahl_nr})



# ── POST /wiedervorlage/batch-sachstandsanfrage ───────────────────────────────

@wiedervorlage_bp.route("/batch-sachstandsanfrage", methods=["POST"])
@login_erforderlich
def batch_sachstandsanfrage():
    """
    POST /wiedervorlage/batch-sachstandsanfrage

    Generiert mehrere Sachstandsanfragen auf einmal und gibt sie als ZIP zurück.

    Body: { "guids": ["guid1", "guid2", ...] }

    Response 200:
        Content-Type: application/zip
        Content-Disposition: attachment; filename="sachstandsanfragen_2026-03-12.zip"

    Response 400: guids fehlt oder leer
    Response 207: Teilerfolg (manche Dokumente konnten nicht generiert werden)
    """
    import zipfile
    import io as _io
    from datetime import date as _date

    body = request.get_json(silent=True) or {}
    guids = body.get("guids", [])

    if not guids:
        return _err("Feld 'guids' fehlt oder ist leer.", 400)
    if len(guids) > 100:
        return _err("Maximal 100 Dokumente pro Batch.", 400)

    zip_buf   = _io.BytesIO()
    fehler    = []
    generiert = 0

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for guid in guids:
            try:
                wv = hole_wiedervorlage_details(guid)
                if not wv:
                    fehler.append({"guid": guid, "fehler": "Nicht gefunden"})
                    continue

                docx_bytes = generiere_sachstandsanfrage_wv(wv)

                sb_kuerzel = wv.get("akte_sachbearbeiter_kuerzel") or ""
                az         = _az_vollstaendig(wv.get("sAktenNummer", ""), sb_kuerzel)
                dateiname  = dateiname_generieren(az)
                zf.writestr(dateiname, docx_bytes)
                generiert += 1

                # Aktivitätslog
                try:
                    empfaenger = (name_aus_ramicro_adresse(wv.get("adr_name"),
                                                           wv.get("sErsteAdresszeile")) or
                                  wv.get("sGegner") or "")
                    benutzer_id = getattr(g, "benutzer", {}).get("id") if hasattr(g, "benutzer") else None
                    logge_aktivitaet(
                        aktion="sachstandsanfrage_wv",
                        beschreibung=(
                            f"Sachstandsanfrage generiert für AZ {az} "
                            f"an {empfaenger} (WV-Grund: {wv.get('sWiedervorlagegrund', '')}) [Batch]"
                        ),
                        akte_id=None,
                        benutzer_id=benutzer_id,
                        tabelle="ramicro_wiedervorlage",
                        datensatz_id=None,
                        aenderung_json=None,
                    )
                except Exception as log_err:
                    logger.warning("Aktivitätslog (Batch) fehlgeschlagen: %s", log_err)

            except Exception as e:
                logger.exception("Batch: Fehler bei GUID %s", guid)
                fehler.append({"guid": guid, "fehler": str(e)})

    if generiert == 0:
        return _err(
            f"Kein Dokument konnte generiert werden. Fehler: {fehler}",
            status=500,
        )

    zip_buf.seek(0)
    datum_str  = _date.today().isoformat()
    dateiname  = f"sachstandsanfragen_{datum_str}.zip"

    response = send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=dateiname,
    )

    # Bei Teilerfolg: Warnungsheader hinzufügen
    if fehler:
        response.headers["X-Batch-Fehler"] = str(len(fehler))
        logger.warning("Batch: %d Fehler, %d generiert", len(fehler), generiert)

    return response
