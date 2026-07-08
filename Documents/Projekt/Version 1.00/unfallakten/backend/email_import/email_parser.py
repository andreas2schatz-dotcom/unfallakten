"""
Modul 7 – E-Mail-Parser
========================
Parst rohe RFC-822-Bytes zu strukturierten Metadaten und
extrahiert Anhänge (PDF, DOCX, JPG, PNG).

Akte-Matching-Strategie (Priorität absteigend):
  1. Aktenzeichen im Betreff (z.B. "Az. 42/25" oder "42/25AS")
  2. Aktenzeichen im E-Mail-Text (Body)
  3. KFZ-Kennzeichen im Betreff/Body gegen beteiligte.kfz_kennzeichen
  4. Absender-E-Mail gegen beteiligte.email

FIXES v9:
  Bug 1 – SELECT id FROM unfallakte → SELECT az FROM unfallakte (PK ist jetzt TEXT)
  Bug 2 – Rückgabe ist jetzt Optional[str] (az TEXT), nicht Optional[int]
  Bug 5 – _normiere_az_basis() strippt SB-Kürzel (31/21AS → 31/21) vor DB-Lookup
"""

import re
import uuid
import logging
import email
import email.header
import email.policy
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Erlaubte Anhang-Dateitypen ────────────────────────────────────────────────

ERLAUBTE_ENDUNGEN = {
    "pdf":  "pdf",
    "docx": "docx",
    "doc":  "docx",
    "jpg":  "jpg",
    "jpeg": "jpg",
    "png":  "png",
}

# ── Regex-Muster für Aktenzeichen ─────────────────────────────────────────────

AZ_MUSTER = [
    re.compile(r"[Aa]z\.?\s*:?\s*(\d{1,6}/\d{2}(?:[A-Z]{2,3})?)", re.IGNORECASE),
    re.compile(r"\bUnser\s+Zeichen\s*:?\s*(\d{1,6}/\d{2}(?:[A-Z]{2,3})?)", re.IGNORECASE),
    re.compile(r"\b(\d{1,6}/\d{2}(?:[A-Z]{2,3})?)\b"),
]

# KFZ-Kennzeichen: z.B. OF-HM 123, B-AB 1234
KFZ_MUSTER = re.compile(
    r"\b([A-ZÄÖÜ]{1,3})-([A-Z]{1,2})\s*(\d{1,4})\b", re.IGNORECASE
)


# ── Hauptfunktion: E-Mail parsen ──────────────────────────────────────────────

def parse_email(roh_bytes: bytes) -> dict:
    """
    Parst rohe E-Mail-Bytes zu einem strukturierten Dict.

    Returns:
        {
          "message_id":    str,
          "betreff":       str,
          "absender":      str,       # vollständiger From-Header
          "absender_email": str,      # extrahierte E-Mail-Adresse
          "absender_name": str,       # extrahierter Name
          "empfangen_am":  str (ISO),
          "text":          str (Body, plain text),
          "anhaenge":      [{"dateiname": str, "endung": str, "daten": bytes}],
          "anhaenge_json": [{"dateiname": str, "inhalt": bytes}],  # JSON-Anhänge (PRD-22c)
          "az_kandidaten":  [str],
          "kfz_kandidaten": [str],
        }
    """
    try:
        msg = email.message_from_bytes(roh_bytes, policy=email.policy.default)
    except Exception as e:
        logger.warning("E-Mail konnte nicht geparst werden: %s", e)
        return _leeres_ergebnis()

    message_id   = _header(msg, "Message-ID") or f"<generated-{uuid.uuid4().hex}>"
    betreff_raw  = _header(msg, "Subject") or ""
    betreff      = _decode_header(betreff_raw)
    absender     = _header(msg, "From") or ""
    datum        = _header(msg, "Date") or ""
    empfangen_am = _parse_datum(datum)
    absender_email = _extrahiere_email(absender)
    absender_name  = _extrahiere_name(absender)

    text          = _extrahiere_text(msg)
    anhaenge      = _extrahiere_anhaenge(msg)
    anhaenge_json = extrahiere_json_anhaenge(msg)

    # WG:/FW: Prefix abschneiden vor AZ-Suche
    betreff_clean = re.sub(
        r'^(WG|FW|FWD|AW|RE)\s*:\s*', '', betreff,
        flags=re.IGNORECASE
    ).strip()
    suchtext = f"{betreff_clean} {text[:2000]}"
    az_kandidaten  = _suche_aktenzeichen(suchtext)
    kfz_kandidaten = _suche_kfz(suchtext)

    return {
        "message_id":     message_id.strip("<>").strip(),
        "betreff":        betreff,
        "absender":       absender,
        "absender_email": absender_email,
        "absender_name":  absender_name,
        "empfangen_am":   empfangen_am,
        "text":           text,
        "anhaenge":       anhaenge,
        "anhaenge_json":  anhaenge_json,
        "az_kandidaten":  az_kandidaten,
        "kfz_kandidaten": kfz_kandidaten,
    }


# ── Akte-Matching ─────────────────────────────────────────────────────────────

def finde_akte(parsed: dict, db_conn) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Versucht die passende Akte für eine E-Mail zu finden.

    Returns:
        (az, erkannt_az, match_methode)
        az = Aktenzeichen (TEXT, PK von unfallakte) oder None
        erkannt_az  = der gefundene Kandidat aus E-Mail (für Log)
        match_methode = 'aktenzeichen' | 'kfz_kennzeichen' | 'absender_email' | None

    FIX Bug 1: Tabelle unfallakte hat kein `id` mehr – PK ist `az` (TEXT).
    FIX Bug 2: Rückgabe ist Optional[str], nicht Optional[int].
    FIX Bug 5: SB-Kürzel (z.B. 31/21AS → 31/21) wird vor DB-Lookup entfernt.
    """
    # 1. Aktenzeichen-Treffer
    for kandidat in parsed["az_kandidaten"]:
        az_basis = _az_basis(kandidat)          # "31/21AS" → "31/21"
        az_norm  = az_basis.upper().replace("/", "")   # "3121"
        # LIKE mit % am Ende, damit "3121" auch "3121AS" matched falls Kürzel in DB steht
        row = db_conn.execute(
            "SELECT az FROM unfallakte WHERE UPPER(REPLACE(az, '/', '')) LIKE ?",
            (az_norm + "%",)
        ).fetchone()
        if row:
            logger.info("Akte-Match via AZ '%s' (Basis '%s') → az %s",
                        kandidat, az_basis, row["az"])
            return row["az"], kandidat, "aktenzeichen"

    # 2. KFZ-Kennzeichen-Treffer
    for kfz in parsed["kfz_kandidaten"]:
        row = db_conn.execute(
            """SELECT DISTINCT akte_id
               FROM beteiligte
               WHERE UPPER(REPLACE(kfz_kennzeichen,' ','')) =
                     UPPER(REPLACE(?, ' ',''))""",
            (kfz,)
        ).fetchone()
        if row:
            logger.info("Akte-Match via KFZ '%s' → akte_id %s", kfz, row["akte_id"])
            return row["akte_id"], kfz, "kfz_kennzeichen"

    # 3. Absender-E-Mail gegen Beteiligte
    absender_mail = parsed["absender_email"].lower()
    if absender_mail:
        row = db_conn.execute(
            "SELECT DISTINCT akte_id FROM beteiligte WHERE LOWER(email) = ?",
            (absender_mail,)
        ).fetchone()
        if row:
            logger.info("Akte-Match via E-Mail '%s' → akte_id %s",
                        absender_mail, row["akte_id"])
            return row["akte_id"], absender_mail, "absender_email"

    # Candidates für Log (erstes AZ bzw. KFZ)
    erkannt = (
        parsed["az_kandidaten"][0] if parsed["az_kandidaten"]
        else (parsed["kfz_kandidaten"][0] if parsed["kfz_kandidaten"] else None)
    )
    logger.info("Kein Akte-Match für Betreff: %r", parsed["betreff"][:80])
    return None, erkannt, None


# ── Anhang-Speicherung ────────────────────────────────────────────────────────

def speichere_anhang(anhang: dict, upload_dir: Path,
                     akte_id: str) -> Optional[dict]:
    """
    Speichert einen Anhang auf Disk.
    akte_id ist jetzt TEXT (az), nicht INTEGER.
    """
    endung   = anhang.get("endung", "")
    dateityp = ERLAUBTE_ENDUNGEN.get(endung)
    if not dateityp:
        return None

    original  = anhang.get("dateiname", "anhang")
    safe_name = re.sub(r"[^\w.\-]", "_", original)
    uuid_name = f"{uuid.uuid4().hex}_{safe_name}"
    pfad      = upload_dir / uuid_name

    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        pfad.write_bytes(anhang["daten"])
        return {
            "dateiname": safe_name,
            "pfad":      str(pfad),
            "groesse":   len(anhang["daten"]),
            "dateityp":  dateityp,
        }
    except OSError as e:
        logger.error("Anhang konnte nicht gespeichert werden: %s", e)
        return None


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


# ── Weiterleitungs-Erkennung ─────────────────

_WEITERLEITUNG_RE = re.compile(
    r'^(WG|FW|FWD|AW|RE|Fwd|Aw|Wg|fw|wg)\s*:\s*',
    re.IGNORECASE
)

_TRENN_RE = re.compile(
    r'-{3,}.{0,40}(urspr|original|weitergeleit|forwarded)',
    re.IGNORECASE
)

_VON_MIT_RE = re.compile(
    r'(?:Von|From)\s*:\s*([^<\[\n]{0,80}?)\s*<([\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,})>',
    re.IGNORECASE | re.MULTILINE
)
# Outlook-Format: Von: Max Mustermann [mailto:max@example.de]
_VON_MAILTO_RE = re.compile(
    r'(?:Von|From)\s*:\s*([^\[\n]{0,80}?)\s*\[mailto:([\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,})\]',
    re.IGNORECASE | re.MULTILINE
)
_VON_OHNE_RE = re.compile(
    r'(?:Von|From)\s*:\s*([\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,})',
    re.IGNORECASE | re.MULTILINE
)


def ist_weiterleitung(betreff: str) -> bool:
    '''Prueft ob Betreff WG:/FW:/AW: enthaelt (Weiterleitung).'''
    return bool(_WEITERLEITUNG_RE.match(betreff.strip()))


def extrahiere_original_absender(text: str) -> tuple:
    '''
    Extrahiert Original-Absender aus Body einer weitergeleiteten E-Mail.

    Behandelt drei Faelle:
    1. Trennlinie vorhanden (Outlook: -----Urspruengliche Nachricht-----):
       Sucht NUR nach der Trennlinie
    2. Kein Trennlinie, Von: steht direkt am Anfang (haeufigstes Format):
       Sucht im gesamten Body
    3. Mailto-Format: <email <mailto:email>> wird bereinigt
    '''
    if not text:
        return '', ''

    suchbereich = text[:6000]  # erweitert von 4000 – lange Outlook-Mails haben Kopf weiter hinten

    # Trennlinie suchen – nur danach weitersuchen wenn gefunden
    trenn = _TRENN_RE.search(suchbereich)
    if trenn:
        suchbereich = suchbereich[trenn.start():]

    # Mailto-Links bereinigen: <email <mailto:email> > oder <email <mailto:email>> → <email>
    suchbereich = re.sub(
        r'<([\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,})\s+<mailto:[^>]+>\s*>',
        r'<\1>',
        suchbereich
    )

    # Format 1: Von: Max Mustermann <max@example.de>
    m = _VON_MIT_RE.search(suchbereich)
    if m:
        name  = m.group(1).strip().strip('"').strip("'")
        email = m.group(2).strip()
        if '@' in email:
            logger.debug('Weiterleitung Original (spitze Klammern): %s <%s>', name, email)
            return name, email

    # Format 2: Outlook: Von: Max Mustermann [mailto:max@example.de]
    m = _VON_MAILTO_RE.search(suchbereich)
    if m:
        name  = m.group(1).strip().strip('"').strip("'")
        email = m.group(2).strip()
        if '@' in email:
            logger.debug('Weiterleitung Original (mailto-Klammern): %s <%s>', name, email)
            return name, email

    # Format 3: Ohne Name: Von: max@example.de
    m = _VON_OHNE_RE.search(suchbereich)
    if m:
        email = m.group(1).strip()
        if '@' in email:
            return '', email

    return '', ''

def _leeres_ergebnis() -> dict:
    return {
        "message_id": f"<generated-{uuid.uuid4().hex}>",
        "betreff": "", "absender": "", "absender_email": "", "absender_name": "",
        "empfangen_am": None, "text": "",
        "anhaenge": [], "anhaenge_json": [], "az_kandidaten": [], "kfz_kandidaten": [],
    }


def _header(msg, name: str) -> str:
    val = msg.get(name, "")
    return str(val) if val else ""


def _decode_header(raw: str) -> str:
    try:
        teile = email.header.decode_header(raw)
        decoded = []
        for teil, charset in teile:
            if isinstance(teil, bytes):
                decoded.append(teil.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(teil)
        return "".join(decoded)
    except Exception:
        return raw


def _extrahiere_email(from_header: str) -> str:
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip()
    match = re.search(r"[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}", from_header)
    return match.group(0).strip() if match else ""


def _extrahiere_name(from_header: str) -> str:
    """Extrahiert den Anzeigenamen aus 'Max Mustermann <max@example.de>'."""
    match = re.match(r'^"?([^"<]+)"?\s*<', from_header)
    if match:
        return match.group(1).strip().strip('"')
    # Wenn keine spitzen Klammern: die ganze Adresse ist der Name
    if "@" not in from_header:
        return from_header.strip()
    return ""


def _extrahiere_text(msg: EmailMessage) -> str:
    '''
    Extrahiert Plain-Text aus einer E-Mail.
    Fallback auf text/html wenn kein text/plain vorhanden (eingebettete Bilder etc.).

    Die UTF-16-BOM-Behandlung liegt seit S1.3 im IMAP-Adapter
    (``backend/intake/adapter_imap.py: dekodiere_email_payload``) — hier
    wird sie ueber Import benutzt, nicht dupliziert.
    '''
    # Lokal importieren, damit Modul-Zyklen ausgeschlossen sind
    # (adapter_imap importiert nichts aus diesem Modul).
    from ..intake.adapter_imap import dekodiere_email_payload

    text_teile = []
    html_teile = []
    try:
        for part in msg.walk():
            ct  = part.get_content_type()
            cd  = str(part.get('Content-Disposition', ''))
            if 'attachment' in cd:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or 'utf-8'
            decoded = dekodiere_email_payload(payload, charset)
            if ct == 'text/plain':
                # Pruefen ob Text lesbar ist (nicht binaerer Muell)
                lesbar = sum(1 for c in decoded[:200] if c.isprintable() or c in '\n\r\t')
                if lesbar > len(decoded[:200]) * 0.5:
                    text_teile.append(decoded)
            elif ct == 'text/html':
                html_teile.append(decoded)
    except Exception as e:
        logger.debug('Text-Extraktion: %s', e)

    if text_teile:
        return '\n'.join(text_teile).strip()

    # Fallback: HTML → Plain Text
    if html_teile:
        return _html_zu_text('\n'.join(html_teile))

    return ''


def _html_zu_text(html: str) -> str:
    '''Entfernt HTML-Tags und gibt lesbaren Text zurueck.'''
    # Script/Style-Bloecke entfernen
    text = re.sub(r'<(script|style)[^>]*>.*?</(script|style)>', '', html,
                  flags=re.IGNORECASE | re.DOTALL)
    # Zeilenumbrueche bei Block-Elementen
    text = re.sub(r'<(br|p|div|tr)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Alle verbleibenden Tags entfernen
    text = re.sub(r'<[^>]+>', ' ', text)
    # HTML-Entities
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace(
        '&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    # Mehrfache Leerzeichen/Zeilenumbrueche
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extrahiere_json_anhaenge(msg: EmailMessage) -> list:
    """
    Extrahiert ausschließlich .json-Anhänge aus einer E-Mail.
    Separater Pfad von _extrahiere_anhaenge() – ERLAUBTE_ENDUNGEN bleibt unverändert.

    Returns:
        [{"dateiname": str, "inhalt": bytes}, ...]
    """
    ergebnisse = []
    try:
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            fn = part.get_filename()
            if not fn:
                continue
            dateiname = _decode_header(fn)
            if not dateiname.lower().endswith(".json"):
                continue
            daten = part.get_payload(decode=True)
            if not daten:
                continue
            ergebnisse.append({
                "dateiname": dateiname,
                "inhalt":    daten,
            })
            logger.debug("JSON-Anhang extrahiert: %s (%d Bytes)", dateiname, len(daten))
    except Exception as e:
        logger.warning("JSON-Anhang-Extraktion fehlgeschlagen: %s", e)
    return ergebnisse


def _extrahiere_anhaenge(msg: EmailMessage) -> list[dict]:
    ergebnisse = []
    try:
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            fn = part.get_filename()
            if not fn or "attachment" not in cd:
                continue
            dateiname = _decode_header(fn)
            endung = Path(dateiname).suffix.lstrip(".").lower()
            if endung not in ERLAUBTE_ENDUNGEN:
                logger.debug("Anhang ignoriert (Typ nicht erlaubt): %s", dateiname)
                continue
            daten = part.get_payload(decode=True)
            if not daten:
                continue
            ergebnisse.append({
                "dateiname": dateiname,
                "endung":    endung,
                "daten":     daten,
                "groesse":   len(daten),
            })
    except Exception as e:
        logger.warning("Anhang-Extraktion fehlgeschlagen: %s", e)
    return ergebnisse


def _suche_aktenzeichen(text: str) -> list[str]:
    treffer = []
    for muster in AZ_MUSTER:
        for match in muster.finditer(text):
            az = match.group(1)
            if len(az) >= 4 and az not in treffer:
                treffer.append(az)
    return treffer


def _suche_kfz(text: str) -> list[str]:
    treffer = []
    for match in KFZ_MUSTER.finditer(text):
        kfz = f"{match.group(1).upper()}-{match.group(2).upper()} {match.group(3)}"
        if kfz not in treffer:
            treffer.append(kfz)
    return treffer


def _az_basis(az: str) -> str:
    """
    FIX Bug 5: Entfernt SB-Kürzel vom Ende eines Aktenzeichens.
    "31/21AS" → "31/21"
    "1087/24AB" → "1087/24"
    "42/25" → "42/25" (unverändert)
    """
    az = az.strip().upper()
    if "/" in az:
        az = re.sub(r"[A-Z]{2,3}$", "", az).strip()
    return az


def _parse_datum(datum_str: str) -> Optional[str]:
    """Parst ein E-Mail-Datum-Header zu ISO-Format."""
    if not datum_str:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(datum_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datum_str[:19] if len(datum_str) >= 19 else datum_str


def _normiere_az(az: str) -> str:
    """Normiert auf Großschreibung (Legacy-Kompatibilität)."""
    return az.strip().upper()
