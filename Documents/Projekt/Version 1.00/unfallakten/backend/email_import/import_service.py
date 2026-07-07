"""
Modul 7 – Import-Service
=========================
Orchestriert einen vollständigen E-Mail-Import-Lauf.

FIXES v9:
  Bug 3 – hole_import_log(): JOIN auf unfallakte(az) statt unfallakte(id)
  Bug 6 – Status 'verarbeitet'/'kein_treffer' → 'zugeordnet'/'nicht_zugeordnet'
  Neu   – finde_akte() gibt jetzt (az, erkannt_az, match_methode) zurück,
          alle drei Werte werden in email_import_log gespeichert
  Neu   – von_name aus parsed['absender_name'] in Log schreiben
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..db.database import get_connection
from ..models.dokument import registriere_dokument
from ..pdf.upload_service import starte_pdf_parsing

from .imap_client import (
    imap_verbinden, hole_ungelesene, markiere_als_gelesen,
    ImapVerbindungsFehler, get_imap_config, ist_konfiguriert,
    verschiebe_in_ua, suche_und_verschiebe_ua,
)
from .email_parser import parse_email, finde_akte, speichere_anhang, ist_weiterleitung, extrahiere_original_absender
from .fragebogen_parser import parse_fragebogen_anhang

# RA-Micro Matching – optionaler Import (kein Fehler wenn Modul fehlt)
try:
    from ..ramicro.email_matching import suche_akte_in_ramicro
    _RAMICRO_VERFUEGBAR = True
except ImportError:
    _RAMICRO_VERFUEGBAR = False
    logger.info("RA-Micro email_matching nicht verfuegbar – nur SQLite-Matching.")

# E-Mail-Klassifizierer
try:
    from .klassifizierer import klassifiziere_email
    _KLASSIFIZIERER_VERFUEGBAR = True
except ImportError:
    _KLASSIFIZIERER_VERFUEGBAR = False

logger = logging.getLogger(__name__)


# ── Import-Fehler ─────────────────────────────────────────────────────────────

class ImportFehler(Exception):
    def __init__(self, nachricht: str, status_code: int = 500):
        self.nachricht = nachricht
        self.status_code = status_code
        super().__init__(nachricht)


# ── Upload-Verzeichnis ────────────────────────────────────────────────────────

def _upload_dir() -> Path:
    default = Path(__file__).parent.parent / "uploads"
    return Path(os.environ.get("UPLOAD_DIR", str(default)))


def _imap_cfg_fuer_konto(konto: str) -> dict | None:
    """Baut IMAP-Config für einen Account aus ENV-Vars (analog polling_service)."""
    host     = os.environ.get("EMAIL_HOST", "").strip()
    user     = os.environ.get(f"EMAIL_USER_{konto.upper()}", "").strip()
    password = os.environ.get(f"EMAIL_PASSWORD_{konto.upper()}", "").strip()
    if not host or not user or not password:
        return None
    return {
        "host":      host,
        "port":      int(os.environ.get("EMAIL_PORT", "993")),
        "user":      user,
        "password":  password,
        "folder":    "INBOX",
        "max_fetch": 50,
        "ssl":       os.environ.get("EMAIL_PORT", "993") != "143",
    }


# ── Hauptfunktion: Import-Lauf ────────────────────────────────────────────────

def fuehre_import_lauf_durch(
    bearbeiter_id: Optional[int] = None,
    max_nachrichten: int = None,
    imap_config: dict = None,
    imap_mock=None,
    konto: str = None,
) -> dict:
    """
    Führt einen vollständigen E-Mail-Import-Lauf durch.

    Returns:
        {
          "verarbeitet":  int,
          "kein_treffer": int,
          "fehler":       int,
          "ignoriert":    int,
          "anhaenge":     int,
          "laufzeit_s":   float,
          "details":      [...]
        }
    """
    if not ist_konfiguriert() and imap_mock is None:
        raise ImportFehler(
            "E-Mail-Import nicht konfiguriert. "
            "Bitte EMAIL_HOST, EMAIL_USER und EMAIL_PASSWORD setzen.",
            status_code=503,
        )

    start_zeit = datetime.now()
    bericht    = _leerer_bericht()

    if imap_config:
        cfg = imap_config
    elif konto and konto != "unfall":
        cfg = _imap_cfg_fuer_konto(konto)
        if not cfg:
            raise ImportFehler(
                f"IMAP-Konfiguration für '{konto}' fehlt. "
                f"Bitte EMAIL_USER_{konto.upper()} und EMAIL_PASSWORD_{konto.upper()} setzen.",
                status_code=503,
            )
    else:
        cfg = get_imap_config()
    max_n  = max_nachrichten or cfg.get("max_fetch", 50)
    up_dir = _upload_dir()

    try:
        if imap_mock is not None:
            nachrichten = hole_ungelesene(imap_mock, max_n)
            _verarbeite_alle(nachrichten, imap_mock, bericht, up_dir, bearbeiter_id, konto)
        else:
            with imap_verbinden(cfg) as imap:
                nachrichten = hole_ungelesene(imap, max_n)
                _verarbeite_alle(nachrichten, imap, bericht, up_dir, bearbeiter_id, konto)

    except ImapVerbindungsFehler as e:
        raise ImportFehler(f"IMAP-Verbindungsfehler: {e}", 503) from e

    bericht["laufzeit_s"] = round(
        (datetime.now() - start_zeit).total_seconds(), 2
    )
    logger.info(
        "Import-Lauf: %d zugeordnet, %d kein Treffer, %d Fehler, "
        "%d Anhänge in %.2fs",
        bericht["verarbeitet"], bericht["kein_treffer"],
        bericht["fehler"], bericht["anhaenge"], bericht["laufzeit_s"]
    )
    return bericht


# ── Alle Nachrichten verarbeiten ──────────────────────────────────────────────

def _verarbeite_alle(nachrichten, imap, bericht, up_dir, bearbeiter_id, konto=None):
    for uid, roh_bytes in nachrichten:
        try:
            _verarbeite_eine(uid, roh_bytes, imap, bericht, up_dir, bearbeiter_id, konto)
        except Exception as e:
            logger.error("Unerwarteter Fehler bei UID %s: %s", uid, e)
            bericht["fehler"] += 1
            bericht["details"].append({
                "uid":    uid.decode() if isinstance(uid, bytes) else str(uid),
                "status": "fehler",
                "fehler": str(e),
            })


def _verarbeite_eine(uid, roh_bytes, imap, bericht, up_dir, bearbeiter_id, konto=None):
    parsed = parse_email(roh_bytes)
    msg_id = parsed["message_id"]

    # ── Weiterleitung abfangen ────────────────────────────────────────────────
    # Strategie: Domain-basiert ist zuverlaessiger als Betreff-Erkennung.
    # Wenn Absender von der Kanzlei-Domain kommt (konfigurierbar per .env),
    # wurde die E-Mail intern weitergeleitet → echten Absender aus Body lesen.
    import os as _os
    kanzlei_domains_raw = _os.environ.get(
        'KANZLEI_DOMAINS',
        'anwalt-offenbach.de'
    )
    kanzlei_domains = [
        d.strip().lower()
        for d in kanzlei_domains_raw.split(',')
        if d.strip()
    ]
    weiterleitender = parsed.get('absender_email', '').lower()
    absender_domain = weiterleitender.split('@')[-1] if '@' in weiterleitender else ''
    ist_kanzlei_absender = absender_domain in kanzlei_domains

    if ist_kanzlei_absender:
        # Kanzlei-Domain → immer nach echtem Absender im Body suchen
        orig_name, orig_email = extrahiere_original_absender(parsed.get('text', ''))
        if (orig_email
                and orig_email.lower() != weiterleitender
                and '@' in orig_email):
            logger.info('Kanzlei-Weiterleitung: Original-Absender %s <%s>',
                        orig_name, orig_email)
            parsed = dict(parsed)
            parsed['absender_email_original'] = weiterleitender
            parsed['absender_email'] = orig_email
            if orig_name:
                parsed['absender_name'] = orig_name
                parsed['absender'] = f'{orig_name} <{orig_email}>'
            else:
                parsed['absender'] = orig_email
            parsed['ist_weiterleitung'] = True
        else:
            logger.debug('Kanzlei-Absender, kein Original gefunden: %s', weiterleitender)
    elif ist_weiterleitung(parsed.get('betreff', '')):
        # Fallback: Betreff-Erkennung fuer externe Weiterleitungen (WG:/FW:)
        orig_name, orig_email = extrahiere_original_absender(parsed.get('text', ''))
        if (orig_email
                and orig_email.lower() != weiterleitender
                and '@' in orig_email):
            logger.info('Betreff-Weiterleitung: Original-Absender %s <%s>',
                        orig_name, orig_email)
            parsed = dict(parsed)
            parsed['absender_email_original'] = weiterleitender
            parsed['absender_email'] = orig_email
            if orig_name:
                parsed['absender_name'] = orig_name
                parsed['absender'] = f'{orig_name} <{orig_email}>'
            else:
                parsed['absender'] = orig_email
            parsed['ist_weiterleitung'] = True

    # ── Duplikat-Prüfung ──────────────────────────────────────────────────────
    with get_connection() as conn:
        vorhandener = conn.execute(
            "SELECT id FROM email_import_log WHERE message_id = ?",
            (msg_id,)
        ).fetchone()

    if vorhandener:
        logger.debug("Duplikat ignoriert: %s", msg_id)
        bericht["ignoriert"] += 1
        markiere_als_gelesen(imap, uid)
        return

    # ── PRD-22c: Fragebogen-E-Mails separat verarbeiten ──────────────────────
    if _ist_fragebogen_email(parsed):
        als_fragebogen = _verarbeite_fragebogen(
            parsed, bericht, bearbeiter_id, up_dir
        )
        if als_fragebogen:
            markiere_als_gelesen(imap, uid)
            return
        # als_fragebogen == False → ungültiger Anhang, normal weitermachen

    # ── Akte finden ───────────────────────────────────────────────────────────
    # Stufe 1+2+3: RA-Micro zuerst (wenn aktiv), dann SQLite als Fallback
    akte_az, erkannt_az, match_methode = None, None, None

    if _RAMICRO_VERFUEGBAR:
        akte_az, erkannt_az, match_methode = suche_akte_in_ramicro(
            az_kandidaten  = parsed["az_kandidaten"],
            kfz_kandidaten = parsed["kfz_kandidaten"],
            absender_email = parsed["absender_email"],
        )
        if akte_az:
            # RA-Micro liefert az ohne Kürzel (z.B. "322/25")
            # SQLite-Akte on-demand anlegen falls noch nicht vorhanden
            _stelle_sqlite_akte_sicher(akte_az)

    # Fallback: SQLite-Matching
    if not akte_az:
        with get_connection() as conn:
            akte_az, erkannt_az, match_methode = finde_akte(parsed, conn)

    # KFZ aus erkannt_az vs. match_methode ableiten
    erkannt_kfz = None
    if match_methode == "kfz_kennzeichen":
        erkannt_kfz = erkannt_az
        erkannt_az  = None

    # FIX Bug 6: Status-Werte angepasst an neues Schema
    status  = "zugeordnet" if akte_az else "nicht_zugeordnet"
    dok_ids = []

    # ── Absender-Domain fuer Dispatcher extrahieren ───────────────────────
    _absender_email = parsed.get("absender_email", "")
    _absender_domain = _absender_email.split("@")[-1].lower() if "@" in _absender_email else None

    # ── Anhänge speichern (nur wenn Akte gefunden) ────────────────────────────
    anhaenge_anzahl = len(parsed["anhaenge"])
    if akte_az and parsed["anhaenge"]:
        for anhang in parsed["anhaenge"]:
            gespeichert = speichere_anhang(anhang, up_dir, akte_az)
            if not gespeichert:
                continue

            try:
                dok = registriere_dokument(
                    akte_id      = akte_az,
                    typ          = "sonstiges",
                    dateiname    = gespeichert["dateiname"],
                    dateipfad    = gespeichert["pfad"],
                    bearbeiter_id= bearbeiter_id,
                    dateityp     = gespeichert["dateityp"],
                    dateigroesse = gespeichert["groesse"],
                )
                dok_ids.append(dok.id)
                bericht["anhaenge"] += 1

                if gespeichert["dateityp"] == "pdf":
                    try:
                        starte_pdf_parsing(dok.id, akte_az,
                                           absender_domain=_absender_domain)
                    except Exception as e:
                        logger.warning(
                            "PDF-Parsing für Dokument %d fehlgeschlagen: %s",
                            dok.id, e
                        )

            except Exception as e:
                logger.error("Dokument-Registrierung fehlgeschlagen: %s", e)
                status = "fehler"

    # ── Domain-Matching gegen Absender-Vorlagen ──────────────────────────────
    absender_kategorie = None
    versicherer_name   = None
    von_name_final = parsed.get("absender_name", "") or None
    try:
        email_addr = parsed["absender_email"]
        domain = email_addr.split("@")[-1].lower() if "@" in email_addr else ""
        if domain:
            with get_connection() as conn:
                vorlage = conn.execute(
                    "SELECT name, kategorie, versicherer_name FROM email_absender_vorlagen "
                    "WHERE LOWER(domain) = ? AND aktiv = 1",
                    (domain,)
                ).fetchone()
            if vorlage:
                absender_kategorie = vorlage["kategorie"]
                versicherer_name   = vorlage["versicherer_name"] or vorlage["name"]
                if not von_name_final:
                    von_name_final = versicherer_name or vorlage["name"]
    except Exception as e:
        logger.debug("Domain-Matching Fehler: %s", e)

    # ── E-Mail klassifizieren ────────────────────────────────────────────────
    email_typ = 'sonstiges'
    if _KLASSIFIZIERER_VERFUEGBAR:
        try:
            email_typ = klassifiziere_email(
                parsed=parsed,
                absender_kategorie=absender_kategorie,
                akte_az=akte_az,
            )
            logger.info("E-Mail klassifiziert als '%s'", email_typ)
        except Exception as e:
            logger.debug("Klassifizierung fehlgeschlagen: %s", e)

    # ── Aktion-Badge auf Akte setzen ─────────────────────────────────────────
    if akte_az and email_typ == 'sachstandsanfrage':
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE unfallakte
                    SET aktion_erforderlich = 1,
                        aktion_typ          = 'sachstandsanfrage',
                        aktion_seit         = datetime('now','localtime')
                    WHERE az = ?
                    """,
                    (akte_az,)
                )
        except Exception as e:
            logger.debug("Aktion-Badge setzen fehlgeschlagen: %s", e)

    # ── .eml-Datei speichern ──────────────────────────────────────────────────
    eml_pfad = None
    try:
        import uuid as _uuid
        safe_id = msg_id[:40].replace('/', '_').replace('@', '_')
        eml_dateiname = f"{_uuid.uuid4().hex}_{safe_id}.eml"
        eml_ziel = up_dir / eml_dateiname
        up_dir.mkdir(parents=True, exist_ok=True)
        eml_ziel.write_bytes(roh_bytes)
        eml_pfad = str(eml_ziel)
    except Exception as e:
        logger.warning(".eml speichern fehlgeschlagen: %s", e)

    # ── Import-Log anlegen ────────────────────────────────────────────────────
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO email_import_log (
                message_id, betreff, absender, von_name, empfangen_am,
                akte_id, status,
                erkannt_az, erkannt_kfz, match_methode,
                absender_kategorie, eml_pfad, email_typ,
                anhaenge_anzahl, importierte_dok, notizen, konto
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg_id,
                parsed["betreff"][:500]  if parsed["betreff"]  else None,
                parsed["absender"][:200] if parsed["absender"] else None,
                von_name_final[:200] if von_name_final else None,
                parsed["empfangen_am"],
                akte_az,
                status,
                erkannt_az,
                erkannt_kfz,
                match_methode,
                absender_kategorie,
                eml_pfad,
                email_typ,
                anhaenge_anzahl,
                json.dumps(dok_ids) if dok_ids else None,
                None if akte_az else (
                    f"Keine Akte gefunden. Kandidaten: "
                    f"{parsed['az_kandidaten']} / KFZ: {parsed['kfz_kandidaten']}"
                )[:500],
                konto,
            )
        )

    # ── Als gelesen markieren ─────────────────────────────────────────────────
    markiere_als_gelesen(imap, uid)

    # ── IMAP: nach UA_Eingang verschieben (nur unfall@) ───────────────────────
    if konto == "unfall":
        verschiebe_in_ua(imap, uid, "eingang")

    # ── Bericht aktualisieren ─────────────────────────────────────────────────
    if status == "zugeordnet":
        bericht["verarbeitet"] += 1
    elif status == "nicht_zugeordnet":
        bericht["kein_treffer"] += 1
    else:
        bericht["fehler"] += 1

    bericht["details"].append({
        "message_id":        msg_id,
        "betreff":           (parsed["betreff"] or "")[:80],
        "absender":          parsed["absender_email"],
        "von_name":          von_name_final or "",
        "status":            status,
        "akte_id":           akte_az,
        "erkannt_az":        erkannt_az,
        "erkannt_kfz":       erkannt_kfz,
        "match_methode":     match_methode,
        "absender_kategorie":absender_kategorie,
        "versicherer_name":  versicherer_name,
        "email_typ":         email_typ,
        "anhaenge":          anhaenge_anzahl,
        "dok_ids":           dok_ids,
    })


# ── Import-Log abrufen ────────────────────────────────────────────────────────

def hole_import_log(
    limit: int = 50,
    status: str = None,
    akte_id: str = None,
    konto: str = None,
) -> list[dict]:
    """Gibt den E-Mail-Import-Log zurück, optional gefiltert nach Account (konto)."""
    bedingungen = []
    parameter   = []

    if status:
        bedingungen.append("l.status = ?")
        parameter.append(status)
    if akte_id:
        bedingungen.append("l.akte_id = ?")
        parameter.append(akte_id)
    if konto:
        if konto == "unfall":
            bedingungen.append("(l.konto = ? OR l.konto IS NULL)")
        else:
            bedingungen.append("l.konto = ?")
        parameter.append(konto)

    where = f"WHERE {' AND '.join(bedingungen)}" if bedingungen else ""
    parameter.append(limit)

    with get_connection() as conn:
        # JOIN auf unfallakte(az) + absender_vorlagen für versicherer_name
        zeilen = conn.execute(
            f"""SELECT l.*, a.az AS aktenzeichen,
                       v.versicherer_name, v.kuerzel AS versicherer_kuerzel
                FROM email_import_log l
                LEFT JOIN unfallakte a ON l.akte_id = a.az
                LEFT JOIN email_absender_vorlagen v
                       ON LOWER(SUBSTR(l.absender, INSTR(l.absender,'@')+1)) = LOWER(v.domain)
                       AND v.aktiv = 1
                {where}
                ORDER BY l.importiert_am DESC
                LIMIT ?""",
            parameter
        ).fetchall()

    return [dict(z) for z in zeilen]


# ── Manuelle Akte-Zuordnung ───────────────────────────────────────────────────

def ordne_akte_manuell_zu(log_id: int, az: str) -> dict:
    """
    Ordnet eine ungematchte E-Mail manuell einer Akte zu.
    Wird vom Frontend aufgerufen wenn der Nutzer eine Akte aus dem Dropdown wählt.

    Args:
        log_id: ID des email_import_log Eintrags
        az:     Aktenzeichen (TEXT PK von unfallakte)

    Returns:
        {"ok": True, "az": az} oder {"ok": False, "fehler": str}
    """
    with get_connection() as conn:
        # Akte existiert?
        akte = conn.execute(
            "SELECT az FROM unfallakte WHERE az = ?", (az,)
        ).fetchone()
        if not akte:
            return {"ok": False, "fehler": f"Akte '{az}' nicht gefunden."}

        # Log-Eintrag aktualisieren
        conn.execute(
            """UPDATE email_import_log
               SET akte_id           = ?,
                   status            = 'zugeordnet',
                   manuell_zugeordnet = 1
               WHERE id = ?""",
            (az, log_id)
        )

    logger.info("Manuelle Zuordnung: Log-ID %d → Akte %s", log_id, az)
    return {"ok": True, "az": az}


# ── Import-Statistik ──────────────────────────────────────────────────────────

def hole_import_statistik() -> dict:
    """Gibt zusammenfassende Statistiken zum Import-Log zurück."""
    with get_connection() as conn:
        gesamt = conn.execute(
            "SELECT COUNT(*) as n FROM email_import_log"
        ).fetchone()["n"]

        nach_status = conn.execute(
            """SELECT status, COUNT(*) as anzahl
               FROM email_import_log
               GROUP BY status"""
        ).fetchall()

        letzte = conn.execute(
            """SELECT importiert_am FROM email_import_log
               ORDER BY importiert_am DESC LIMIT 1"""
        ).fetchone()

    status_dict = {r["status"]: r["anzahl"] for r in nach_status}
    return {
        "gesamt":           gesamt,
        "zugeordnet":       status_dict.get("zugeordnet", 0),
        "nicht_zugeordnet": status_dict.get("nicht_zugeordnet", 0),
        "fehler":           status_dict.get("fehler", 0),
        "ignoriert":        status_dict.get("ignoriert", 0),
        "letzter_import":   letzte["importiert_am"] if letzte else None,
    }




def setze_aktion_badge(az: str, aktion_typ: str) -> bool:
    """Setzt den Aktion-Badge auf einer Akte."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE unfallakte
                SET aktion_erforderlich = 1,
                    aktion_typ          = ?,
                    aktion_seit         = datetime('now','localtime')
                WHERE az = ?
                """,
                (aktion_typ, az)
            )
        return True
    except Exception as e:
        logger.warning("setze_aktion_badge Fehler: %s", e)
        return False


def loesche_aktion_badge(az: str) -> bool:
    """Loescht den Aktion-Badge von einer Akte (als erledigt markiert)."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE unfallakte
                SET aktion_erforderlich = 0,
                    aktion_typ          = NULL,
                    aktion_seit         = NULL
                WHERE az = ?
                """,
                (az,)
            )
        return True
    except Exception as e:
        logger.warning("loesche_aktion_badge Fehler: %s", e)
        return False


def importiere_in_akte(
    log_id: int,
    bearbeiter_id: Optional[int] = None,
    erzwingen: bool = False,
) -> dict:
    """
    Importiert Anhaenge + .eml einer E-Mail in den Dokumentenbereich der Akte.
    Wird aufgerufen wenn der Nutzer auf 'In Akte importieren' klickt.

    Speichert:
      - Vorhandene Anhaenge (die beim Import gespeichert wurden)
      - Die .eml-Datei der E-Mail selbst
      - Setzt in_akte_importiert = 1

    erzwingen=True: Auch bereits importierte E-Mails erneut importieren.
    """
    with get_connection() as conn:
        log = conn.execute(
            """
            SELECT id, akte_id, betreff, absender, eml_pfad,
                   importierte_dok, in_akte_importiert, anhaenge_anzahl,
                   message_id, konto
            FROM email_import_log WHERE id = ?
            """,
            (log_id,)
        ).fetchone()

    if not log:
        return {"ok": False, "fehler": "Log-Eintrag nicht gefunden."}
    if not log["akte_id"]:
        return {"ok": False, "fehler": "Keine Akte zugeordnet."}
    if log["in_akte_importiert"] and not erzwingen:
        return {"ok": True, "bereits_importiert": True}

    akte_id = log["akte_id"]
    dok_ids_neu = []
    fehler = []

    # Domain aus Absender extrahieren fuer Dispatcher
    _abs = log["absender"] or ""
    _import_domain = None
    if "<" in _abs and ">" in _abs:
        _import_domain = _abs.split("<")[-1].split(">")[0].split("@")[-1].lower()
    elif "@" in _abs:
        _import_domain = _abs.split("@")[-1].strip().lower()

    import json as _json
    from datetime import datetime as _dt
    from pathlib import Path as _Path
    import re as _re

    
    # 1. Vorhandene Anhänge registrieren (falls beim ersten Import gespeichert)
    bereits_dok_ids = []
    if log["importierte_dok"]:
        try:
            bereits_dok_ids = _json.loads(log["importierte_dok"])
        except (ValueError, TypeError):
            bereits_dok_ids = []

    if bereits_dok_ids:
        with get_connection() as conn:
            for dok_id in bereits_dok_ids:
                dok = conn.execute(
                    "SELECT id, dateityp, dateiname FROM dokumente WHERE id = ?",
                    (dok_id,)
                ).fetchone()
                if dok and dok["dateityp"] == "pdf":
                    try:
                        starte_pdf_parsing(dok["id"], akte_id,
                                           absender_domain=_import_domain)
                    except Exception as e:
                        logger.warning("PDF-Parsing fuer Dok %d: %s", dok["id"], e)
                dok_ids_neu.append(dok_id)

    # 2. Falls keine Anhänge gespeichert: EML nochmal parsen und PDFs extrahieren
    eml_pfad = log["eml_pfad"]
    if not bereits_dok_ids and eml_pfad and _Path(eml_pfad).exists():
        try:
            roh = _Path(eml_pfad).read_bytes()
            if roh[:2] in (b'\xff\xfe', b'\xfe\xff'):
                roh = roh.decode('utf-16').encode('utf-8')
            import email as _email
            import email.policy as _email_policy
            msg = _email.message_from_bytes(roh, policy=_email_policy.default)
            for part in msg.walk():
                cd = part.get_content_disposition() or ""
                fn = part.get_filename() or ""
                if not fn or cd not in ("attachment", "inline"):
                    continue
                ext = _Path(fn).suffix.lower()
                if ext not in (".pdf", ".docx", ".jpg", ".jpeg", ".png"):
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                dateityp = {".pdf":"pdf",".docx":"docx",".jpg":"jpg",
                            ".jpeg":"jpg",".png":"png"}.get(ext, "pdf")
                basis = _re.sub(r"[^\w\s-]", "", _Path(fn).stem).strip()
                sicherer_name = f"{basis}{ext}"
                ziel_pfad = _Path(eml_pfad).parent / sicherer_name
                ziel_pfad.write_bytes(payload)
                try:
                    dok = registriere_dokument(
                        akte_id      = akte_id,
                        typ          = "gutachten" if "gutachten" in fn.lower() else "sonstiges",
                        dateiname    = sicherer_name,
                        dateipfad    = str(ziel_pfad),
                        bearbeiter_id= bearbeiter_id,
                        dateityp     = dateityp,
                        dateigroesse = len(payload),
                    )
                    dok_ids_neu.append(dok.id)
                    if dateityp == "pdf":
                        try:
                            starte_pdf_parsing(dok.id, akte_id,
                                               absender_domain=_import_domain)
                        except Exception as e:
                            logger.warning("PDF-Parsing fuer Anhang %s: %s", fn, e)
                    logger.info("Anhang aus EML extrahiert: %s → %s", fn, sicherer_name)
                except Exception as e:
                    logger.error("Anhang-Registrierung fehlgeschlagen (%s): %s", fn, e)
                    fehler.append(str(e))
        except Exception as e:
            logger.error("EML-Anhang-Extraktion fehlgeschlagen: %s", e)
            fehler.append(str(e))

    # 3. EML-Datei selbst als Dokument registrieren (mit Zeitstempel)
    if eml_pfad and _Path(eml_pfad).exists():
        try:
            betreff_kurz = (log["betreff"] or "email")[:60]
            safe = _re.sub(r"[^\w\s-]", "", betreff_kurz).strip().replace(" ", "_")
            eml_dateiname = f"{safe}.eml"
            dok = registriere_dokument(
                akte_id      = akte_id,
                typ          = "sonstiges",
                dateiname    = eml_dateiname,
                dateipfad    = eml_pfad,
                bearbeiter_id= bearbeiter_id,
                dateityp     = "sonstiges",
                dateigroesse = _Path(eml_pfad).stat().st_size,
            )
            with get_connection() as _conn:
                _conn.execute(
                    "UPDATE dokumente SET dokumentenklasse = 'email' WHERE id = ?",
                    (dok.id,),
                )
            dok_ids_neu.append(dok.id)
        except Exception as e:
            logger.error(".eml Registrierung fehlgeschlagen: %s", e)
            fehler.append(str(e))
    elif eml_pfad:
        logger.warning(".eml Datei nicht mehr vorhanden: %s", eml_pfad)

    # 4. in_akte_importiert setzen
    importiert_am_str = _dt.now().strftime("%H:%M")
    with get_connection() as conn:
        conn.execute(
            "UPDATE email_import_log SET in_akte_importiert = 1, "
            "in_akte_importiert_am = ? WHERE id = ?",
            (importiert_am_str, log_id),
        )

    # 5. IMAP: UA_Eingang → UA_Verarbeitet (nur unfall@, best effort)
    if log["konto"] == "unfall" and log["message_id"]:
        cfg = _imap_cfg_fuer_konto("unfall")
        if cfg:
            suche_und_verschiebe_ua(cfg, log["message_id"], "eingang", "verarbeitet")

    logger.info("In-Akte-Import: Log %d -> Akte %s, %d Dok(e)",
                log_id, akte_id, len(dok_ids_neu))
    return {
        "ok":          True,
        "dok_ids":     dok_ids_neu,
        "fehler":      fehler,
        "importiert_am": importiert_am_str,
    }


def _stelle_sqlite_akte_sicher(az: str) -> None:
    """Stellt sicher dass die Akte in SQLite existiert. On-demand Anlage via RA-Micro."""
    try:
        with get_connection() as conn:
            exists = conn.execute(
                'SELECT 1 FROM unfallakte WHERE az = ?', (az,)
            ).fetchone()
        if not exists:
            logger.info('Akte %s nicht in SQLite - on-demand Anlage.', az)
            try:
                from ..ramicro.ramicro_liste import on_demand_anlegen
                on_demand_anlegen(az)
            except Exception as e:
                logger.warning('on-demand Anlage fuer %s fehlgeschlagen: %s', az, e)
    except Exception as e:
        logger.warning('_stelle_sqlite_akte_sicher Fehler fuer %s: %s', az, e)

def _leerer_bericht() -> dict:
    return {
        "verarbeitet": 0, "kein_treffer": 0,
        "fehler": 0, "ignoriert": 0,
        "anhaenge": 0, "laufzeit_s": 0.0,
        "details": [],
    }


# ── PRD-22c: Fragebogen-Erkennung und -Verarbeitung ──────────────────────────

def _ist_fragebogen_email(parsed: dict) -> bool:
    """
    Schnell-Check: Ist diese E-Mail ein Website-Unfallbogen?

    Zwei Erkennungswege (OR):
    1. Betreff beginnt mit "Unfallbogen: Name – YYYY-MM-DD"
    2. JSON-Anhang mit Dateiname unfallbogen_*.json vorhanden
    """
    import re as _re
    betreff = parsed.get("betreff", "")
    if _re.match(r"^Unfallbogen:\s+.+\s+[-\u2013]\s+\d{4}-\d{2}-\d{2}", betreff):
        return True
    for anh in parsed.get("anhaenge_json", []):
        if _re.match(r"^unfallbogen_.*\.json$", anh.get("dateiname", ""),
                     _re.IGNORECASE):
            return True
    return False


def _verarbeite_fragebogen(parsed: dict, bericht: dict,
                           bearbeiter_id: Optional[int], up_dir: Path) -> bool:
    """
    Verarbeitet eine Fragebogen-E-Mail (PRD-22c).

    Sucht den ersten gültigen unfallbogen_*.json-Anhang, parst ihn und leitet
    in den passenden Flow weiter.

    Returns True wenn als Fragebogen verarbeitet (E-Mail aus normalem Flow entfernen).
    Returns False wenn kein gültiger Fragebogen-Anhang gefunden (normal weitermachen).
    """
    fragebogen = None
    for anh in parsed.get("anhaenge_json", []):
        import re as _re
        if not _re.match(r"^unfallbogen_.*\.json$", anh.get("dateiname", ""),
                         _re.IGNORECASE):
            continue
        fragebogen = parse_fragebogen_anhang(anh["inhalt"])
        if fragebogen is not None:
            break

    if fragebogen is None:
        # Betreff passte, aber kein gültiger JSON-Anhang → normal weiterverarbeiten
        logger.warning(
            "Fragebogen-E-Mail ohne gültigen JSON-Anhang: %r",
            parsed.get("betreff", "")[:80],
        )
        return False

    try:
        if fragebogen["hat_aktenzeichen"]:
            _fragebogen_bestehende_akte(fragebogen, parsed, bericht,
                                        bearbeiter_id, up_dir)
        else:
            _fragebogen_neuer_mandant_stub(fragebogen, parsed, bericht)
    except Exception as e:
        logger.error("Fragebogen-Verarbeitung fehlgeschlagen: %s", e)
        _log_fragebogen_fehler(parsed, fragebogen, str(e))
        bericht["fehler"] += 1

    return True


def _fragebogen_bestehende_akte(fragebogen: dict, parsed: dict,
                                 bericht: dict, bearbeiter_id: Optional[int],
                                 up_dir: Path) -> None:
    """
    Bestehende-Akte-Flow: Akte suchen und Fragebogen-Daten ergänzen (nur leere Felder).
    """
    az = fragebogen["aktenzeichen"]
    _stelle_sqlite_akte_sicher(az)

    with get_connection() as conn:
        akte = conn.execute(
            "SELECT az FROM unfallakte WHERE UPPER(REPLACE(az, '/', '')) LIKE ?",
            (az.upper().replace("/", "") + "%",),
        ).fetchone()

    if not akte:
        logger.warning("Fragebogen: Aktenzeichen %r nicht in DB gefunden.", az)
        _log_fragebogen_fehler(parsed, fragebogen, "az_nicht_gefunden")
        bericht["kein_treffer"] += 1
        return

    akte_az = akte["az"]
    logger.info("Fragebogen: zugeordnet zu Akte %s", akte_az)

    # Fragebogen-Daten ergänzen (nur leere Felder, nie überschreiben)
    _ergaenze_mandant(akte_az, fragebogen["mandant"])
    _ergaenze_gegner(akte_az, fragebogen["gegner"])
    _ergaenze_unfalldetails(akte_az, fragebogen["unfall"])
    if fragebogen["personenschaden"]:
        _ergaenze_personenschaden(akte_az, fragebogen["personenschaden"])

    # JSON-Anhang als Dokument archivieren (Audit-Trail)
    _speichere_fragebogen_json(akte_az, fragebogen["_roh"], up_dir, bearbeiter_id)

    # Import-Log anlegen
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO email_import_log (
                message_id, betreff, absender, von_name, empfangen_am,
                akte_id, status, match_methode, email_typ, anhaenge_anzahl
            ) VALUES (?, ?, ?, ?, ?, ?, 'zugeordnet', 'fragebogen', 'fragebogen', 0)
            """,
            (
                parsed.get("message_id"),
                (parsed.get("betreff") or "")[:500],
                (parsed.get("absender") or "")[:200],
                (parsed.get("absender_name") or "")[:200],
                parsed.get("empfangen_am"),
                akte_az,
            ),
        )

    bericht["verarbeitet"] += 1
    bericht["details"].append({
        "message_id":    parsed.get("message_id"),
        "betreff":       (parsed.get("betreff") or "")[:80],
        "absender":      parsed.get("absender_email"),
        "status":        "zugeordnet",
        "akte_id":       akte_az,
        "email_typ":     "fragebogen",
        "match_methode": "fragebogen",
    })


def _fragebogen_neuer_mandant_stub(fragebogen: dict, parsed: dict,
                                    bericht: dict) -> None:
    """
    Stub: Speichert Fragebogen-Daten in fragebogen_erstkontakt.
    Keine Akte-Anlage – das ist PRD-22d.
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO fragebogen_erstkontakt
                (absender_email, absender_name, message_id, json_roh,
                 mandant_name, mandant_email, kfz_kennzeichen, schadentag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parsed.get("absender_email"),
                parsed.get("absender_name"),
                parsed.get("message_id"),
                json.dumps(fragebogen["_roh"], ensure_ascii=False),
                fragebogen["mandant"].get("name"),
                fragebogen["mandant"].get("email"),
                fragebogen["gegner"].get("fahrzeug", {}).get("kennzeichen"),
                fragebogen["unfall"].get("datum"),
            ),
        )

    # Import-Log anlegen
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO email_import_log (
                message_id, betreff, absender, von_name, empfangen_am,
                akte_id, status, email_typ, anhaenge_anzahl,
                notizen
            ) VALUES (?, ?, ?, ?, ?, NULL, 'nicht_zugeordnet', 'fragebogen', 0, ?)
            """,
            (
                parsed.get("message_id"),
                (parsed.get("betreff") or "")[:500],
                (parsed.get("absender") or "")[:200],
                (parsed.get("absender_name") or "")[:200],
                parsed.get("empfangen_am"),
                "Neuer Mandant – fragebogen_erstkontakt angelegt (PRD-22d ausstehend)",
            ),
        )

    logger.info(
        "Fragebogen Erstkontakt angelegt: %s <%s>",
        fragebogen["mandant"].get("name"),
        fragebogen["mandant"].get("email"),
    )
    bericht["verarbeitet"] += 1
    bericht["details"].append({
        "message_id": parsed.get("message_id"),
        "betreff":    (parsed.get("betreff") or "")[:80],
        "absender":   parsed.get("absender_email"),
        "status":     "fragebogen_erstkontakt",
        "akte_id":    None,
        "email_typ":  "fragebogen",
    })


def _speichere_fragebogen_json(akte_az: str, roh_dict: dict,
                                up_dir: Path, bearbeiter_id: Optional[int]) -> None:
    """Speichert den Original-JSON als Dokument in der Akte (Audit-Trail)."""
    try:
        import uuid as _uuid
        up_dir.mkdir(parents=True, exist_ok=True)
        dateiname = f"fragebogen_{_uuid.uuid4().hex}.json"
        pfad = up_dir / dateiname
        pfad.write_text(
            json.dumps(roh_dict, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        registriere_dokument(
            akte_id       = akte_az,
            typ           = "sonstiges",
            dateiname     = dateiname,
            dateipfad     = str(pfad),
            bearbeiter_id = bearbeiter_id,
            dateityp      = "docx",   # JSON hat kein eigenes dateityp – "docx" als Freitext-Platzhalter
            dateigroesse  = pfad.stat().st_size,
        )
        logger.debug("Fragebogen-JSON archiviert: %s", dateiname)
    except Exception as e:
        logger.warning("Fragebogen-JSON konnte nicht archiviert werden: %s", e)


def _log_fragebogen_fehler(parsed: dict, fragebogen, grund: str) -> None:
    """Schreibt einen Fehler-Eintrag in den Import-Log (graceful degradation)."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO email_import_log (
                    message_id, betreff, absender, empfangen_am,
                    akte_id, status, email_typ, notizen
                ) VALUES (?, ?, ?, ?, NULL, 'fehler', 'fragebogen', ?)
                """,
                (
                    parsed.get("message_id"),
                    (parsed.get("betreff") or "")[:500],
                    (parsed.get("absender") or "")[:200],
                    parsed.get("empfangen_am"),
                    f"Fragebogen-Fehler: {grund}"[:500],
                ),
            )
    except Exception as e:
        logger.error("_log_fragebogen_fehler selbst fehlgeschlagen: %s", e)


# ── PRD-22c Session 2: _ergaenze_*-Funktionen ────────────────────────────────

def _ergaenze_mandant(akte_az: str, mandant_dict: dict) -> None:
    """
    Ergänzt Mandant-Daten in beteiligte (rolle='mandant').
    Nur leere Felder werden befüllt – bestehende Daten werden NIE überschrieben.

    JSON-Mapping:
      mandant.name           → name
      mandant.vorname        → vorname
      mandant.strasse        → anschrift
      mandant.plz            → plz
      mandant.ort            → ort
      mandant.email          → email
      mandant.telefon        → telefon
      mandant.iban           → iban
      mandant.vorsteuerabzug → vorsteuer  ("ja" → "Y"; default bleibt "N")
    """
    if not mandant_dict:
        return
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, vorname, anschrift, plz, ort, email, telefon, iban, vorsteuer "
                "FROM beteiligte WHERE akte_id = ? AND rolle = 'mandant'",
                (akte_az,)
            ).fetchone()

            if row is None:
                name = mandant_dict.get("name")
                if not name:
                    logger.debug("Fragebogen Mandant: kein Name, kein Insert für Akte %s.", akte_az)
                    return
                conn.execute(
                    """INSERT INTO beteiligte
                       (akte_id, rolle, name, vorname, anschrift, plz, ort,
                        email, telefon, iban, vorsteuer)
                       VALUES (?, 'mandant', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        akte_az,
                        name,
                        mandant_dict.get("vorname"),
                        mandant_dict.get("strasse"),
                        mandant_dict.get("plz"),
                        mandant_dict.get("ort"),
                        mandant_dict.get("email"),
                        mandant_dict.get("telefon"),
                        mandant_dict.get("iban"),
                        "Y" if mandant_dict.get("vorsteuerabzug") == "ja" else "N",
                    )
                )
                logger.info("Fragebogen: Mandant neu angelegt für Akte %s", akte_az)
            else:
                updates = {}
                if not row["name"] and mandant_dict.get("name"):
                    updates["name"] = mandant_dict["name"]
                if not row["vorname"] and mandant_dict.get("vorname"):
                    updates["vorname"] = mandant_dict["vorname"]
                if not row["anschrift"] and mandant_dict.get("strasse"):
                    updates["anschrift"] = mandant_dict["strasse"]
                if not row["plz"] and mandant_dict.get("plz"):
                    updates["plz"] = mandant_dict["plz"]
                if not row["ort"] and mandant_dict.get("ort"):
                    updates["ort"] = mandant_dict["ort"]
                if not row["email"] and mandant_dict.get("email"):
                    updates["email"] = mandant_dict["email"]
                if not row["telefon"] and mandant_dict.get("telefon"):
                    updates["telefon"] = mandant_dict["telefon"]
                if not row["iban"] and mandant_dict.get("iban"):
                    updates["iban"] = mandant_dict["iban"]
                # Vorsteuer: nur auf "Y" upgraden, nie auf "N" downgraden
                if row["vorsteuer"] != "Y" and mandant_dict.get("vorsteuerabzug") == "ja":
                    updates["vorsteuer"] = "Y"
                if updates:
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    conn.execute(
                        f"UPDATE beteiligte SET {set_clause} WHERE id = ?",
                        list(updates.values()) + [row["id"]]
                    )
                    logger.info("Fragebogen: Mandant ergänzt für Akte %s (%d Felder)", akte_az, len(updates))
    except Exception as e:
        logger.warning("_ergaenze_mandant für Akte %s fehlgeschlagen: %s", akte_az, e)


def _ergaenze_gegner(akte_az: str, gegner_dict: dict) -> None:
    """
    Ergänzt Gegner-Daten in beteiligte (rolle='gegner').
    Versicherungs-Daten werden auf dieselbe Zeile geschrieben (Spalten versicherung, vers_nr, schaden_nr).
    Nur leere Felder werden befüllt.

    JSON-Mapping:
      gegner.fahrer                  → name
      gegner.fahrzeug.kennzeichen    → kfz_kennzeichen
      gegner.fahrzeug.fabrikat       → notizen
      gegner.versicherung.name       → versicherung
      gegner.versicherung.nummer     → vers_nr
      gegner.versicherung.schadennummer → schaden_nr
    """
    if not gegner_dict:
        return
    try:
        fahrzeug = gegner_dict.get("fahrzeug") or {}
        versicherung = gegner_dict.get("versicherung") or {}

        fahrer = gegner_dict.get("fahrer")
        kennzeichen = fahrzeug.get("kennzeichen")
        fabrikat = fahrzeug.get("fabrikat")
        vers_name = versicherung.get("name")
        vers_nr = versicherung.get("nummer")
        schaden_nr = versicherung.get("schadennummer")

        hat_daten = any([fahrer, kennzeichen, fabrikat, vers_name, vers_nr, schaden_nr])
        if not hat_daten:
            return

        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, name, kfz_kennzeichen, notizen, versicherung, vers_nr, schaden_nr "
                "FROM beteiligte WHERE akte_id = ? AND rolle = 'gegner'",
                (akte_az,)
            ).fetchone()

            if row is None:
                conn.execute(
                    """INSERT INTO beteiligte
                       (akte_id, rolle, name, kfz_kennzeichen, notizen,
                        versicherung, vers_nr, schaden_nr)
                       VALUES (?, 'gegner', ?, ?, ?, ?, ?, ?)""",
                    (akte_az, fahrer, kennzeichen, fabrikat, vers_name, vers_nr, schaden_nr)
                )
                logger.info("Fragebogen: Gegner neu angelegt für Akte %s", akte_az)
            else:
                updates = {}
                if not row["name"] and fahrer:
                    updates["name"] = fahrer
                if not row["kfz_kennzeichen"] and kennzeichen:
                    updates["kfz_kennzeichen"] = kennzeichen
                if not row["notizen"] and fabrikat:
                    updates["notizen"] = fabrikat
                if not row["versicherung"] and vers_name:
                    updates["versicherung"] = vers_name
                if not row["vers_nr"] and vers_nr:
                    updates["vers_nr"] = vers_nr
                if not row["schaden_nr"] and schaden_nr:
                    updates["schaden_nr"] = schaden_nr
                if updates:
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    conn.execute(
                        f"UPDATE beteiligte SET {set_clause} WHERE id = ?",
                        list(updates.values()) + [row["id"]]
                    )
                    logger.info("Fragebogen: Gegner ergänzt für Akte %s (%d Felder)", akte_az, len(updates))
    except Exception as e:
        logger.warning("_ergaenze_gegner für Akte %s fehlgeschlagen: %s", akte_az, e)


def _ergaenze_unfalldetails(akte_az: str, unfall_dict: dict) -> None:
    """
    Ergänzt Unfalldaten in unfallakte (unfalldatum, unfallort) und unfalldetails
    (schilderung, ermittlungsakte_az). Nur leere Felder werden befüllt.

    JSON-Mapping:
      unfall.datum                   → unfallakte.unfalldatum
      unfall.ort                     → unfallakte.unfallort
      unfall.zeit                    → Präfix in unfalldetails.schilderung (kein eigenes Feld)
      unfall.schilderung             → unfalldetails.schilderung
      unfall.polizei.aktenzeichen    → unfalldetails.ermittlungsakte_az
    """
    if not unfall_dict:
        return
    try:
        datum = unfall_dict.get("datum")
        ort = unfall_dict.get("ort")
        zeit = unfall_dict.get("zeit")
        schilderung = unfall_dict.get("schilderung")
        polizei = unfall_dict.get("polizei") or {}
        polizei_az = polizei.get("aktenzeichen")

        with get_connection() as conn:
            # 1. unfallakte: unfalldatum + unfallort nur wenn leer/Leerstring
            akte_row = conn.execute(
                "SELECT unfalldatum, unfallort FROM unfallakte WHERE az = ?",
                (akte_az,)
            ).fetchone()
            if akte_row:
                akte_updates = {}
                if not akte_row["unfalldatum"] and datum:
                    akte_updates["unfalldatum"] = datum
                if not akte_row["unfallort"] and ort:
                    akte_updates["unfallort"] = ort
                if akte_updates:
                    set_clause = ", ".join(f"{k} = ?" for k in akte_updates)
                    conn.execute(
                        f"UPDATE unfallakte SET {set_clause} WHERE az = ?",
                        list(akte_updates.values()) + [akte_az]
                    )

            # 2. Schilderung: Zeit als Präfix einfügen falls vorhanden
            schilderung_final = schilderung
            if zeit:
                prefix = f"[Uhrzeit: {zeit}]"
                schilderung_final = f"{prefix} {schilderung}" if schilderung else prefix

            # 3. unfalldetails: INSERT oder UPDATE
            ud_row = conn.execute(
                "SELECT id, schilderung, ermittlungsakte_az "
                "FROM unfalldetails WHERE akte_id = ?",
                (akte_az,)
            ).fetchone()

            if ud_row is None:
                if any([schilderung_final, polizei_az]):
                    conn.execute(
                        "INSERT INTO unfalldetails (akte_id, schilderung, ermittlungsakte_az) "
                        "VALUES (?, ?, ?)",
                        (akte_az, schilderung_final, polizei_az)
                    )
                    logger.info("Fragebogen: unfalldetails neu angelegt für Akte %s", akte_az)
            else:
                updates = {}
                if not ud_row["schilderung"] and schilderung_final:
                    updates["schilderung"] = schilderung_final
                if not ud_row["ermittlungsakte_az"] and polizei_az:
                    updates["ermittlungsakte_az"] = polizei_az
                if updates:
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    conn.execute(
                        f"UPDATE unfalldetails SET {set_clause} WHERE id = ?",
                        list(updates.values()) + [ud_row["id"]]
                    )
                    logger.info("Fragebogen: unfalldetails ergänzt für Akte %s (%d Felder)", akte_az, len(updates))
    except Exception as e:
        logger.warning("_ergaenze_unfalldetails für Akte %s fehlgeschlagen: %s", akte_az, e)


def _ergaenze_personenschaden(akte_az: str, ps_dict: dict) -> None:
    """
    Ergänzt Personenschaden-Daten in personenschaden. Nur leere Felder werden befüllt.
    ps_dict muss != None sein (Caller prüft das).

    JSON-Mapping:
      personenschaden.verletzter.geburtsdatum → geburtsdatum
      personenschaden.verletzungen            → verletzungen_text
      personenschaden.krankenhaus.name        → krankenhaus_name  (+ krankenhaus_aufenthalt=1)
      personenschaden.krankenhaus.von/bis     → krankenhaus_von/bis
      personenschaden.hauskrank.von/bis       → krank_von/bis  (+ krankgeschrieben=1)
    """
    if not ps_dict:
        return
    try:
        verletzter = ps_dict.get("verletzter") or {}
        krankenhaus = ps_dict.get("krankenhaus") or {}
        hauskrank = ps_dict.get("hauskrank") or {}

        geburtsdatum = verletzter.get("geburtsdatum")
        verletzungen = ps_dict.get("verletzungen")
        kh_name = krankenhaus.get("name")
        kh_von = krankenhaus.get("von")
        kh_bis = krankenhaus.get("bis")
        krank_von = hauskrank.get("von")
        krank_bis = hauskrank.get("bis")

        hat_daten = any([geburtsdatum, verletzungen, kh_name, krank_von])
        if not hat_daten:
            return

        with get_connection() as conn:
            ps_row = conn.execute(
                """SELECT id, geburtsdatum, verletzungen_text,
                          krankenhaus_name, krankenhaus_aufenthalt,
                          krankenhaus_von, krankenhaus_bis,
                          krankgeschrieben, krank_von, krank_bis
                   FROM personenschaden WHERE akte_id = ?""",
                (akte_az,)
            ).fetchone()

            if ps_row is None:
                conn.execute(
                    """INSERT INTO personenschaden
                       (akte_id, geburtsdatum, verletzungen_text,
                        krankenhaus_name, krankenhaus_aufenthalt,
                        krankenhaus_von, krankenhaus_bis,
                        krankgeschrieben, krank_von, krank_bis)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        akte_az,
                        geburtsdatum, verletzungen,
                        kh_name,
                        1 if kh_name else 0,
                        kh_von, kh_bis,
                        1 if krank_von else 0,
                        krank_von, krank_bis,
                    )
                )
                logger.info("Fragebogen: personenschaden neu angelegt für Akte %s", akte_az)
            else:
                updates = {}
                if not ps_row["geburtsdatum"] and geburtsdatum:
                    updates["geburtsdatum"] = geburtsdatum
                if not ps_row["verletzungen_text"] and verletzungen:
                    updates["verletzungen_text"] = verletzungen
                if not ps_row["krankenhaus_name"] and kh_name:
                    updates["krankenhaus_name"] = kh_name
                    if not ps_row["krankenhaus_aufenthalt"]:
                        updates["krankenhaus_aufenthalt"] = 1
                if not ps_row["krankenhaus_von"] and kh_von:
                    updates["krankenhaus_von"] = kh_von
                if not ps_row["krankenhaus_bis"] and kh_bis:
                    updates["krankenhaus_bis"] = kh_bis
                if not ps_row["krank_von"] and krank_von:
                    updates["krank_von"] = krank_von
                    if not ps_row["krankgeschrieben"]:
                        updates["krankgeschrieben"] = 1
                if not ps_row["krank_bis"] and krank_bis:
                    updates["krank_bis"] = krank_bis
                if updates:
                    set_clause = ", ".join(f"{k} = ?" for k in updates)
                    conn.execute(
                        f"UPDATE personenschaden SET {set_clause} WHERE id = ?",
                        list(updates.values()) + [ps_row["id"]]
                    )
                    logger.info("Fragebogen: personenschaden ergänzt für Akte %s (%d Felder)", akte_az, len(updates))
    except Exception as e:
        logger.warning("_ergaenze_personenschaden für Akte %s fehlgeschlagen: %s", akte_az, e)
