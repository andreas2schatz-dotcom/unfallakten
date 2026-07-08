"""
S1.3 - IMAP-Adapter.

Zerlegt eine rohe RFC-822-E-Mail in normierte Zustellungs-Datensaetze:
  * Body als eigene ``payload_typ='text'``-Zustellung (Parent).
  * Anhaenge einzeln als ``payload_typ='datei'``-Zustellungen mit
    ``parent_id`` = id der Body-Zustellung.

Encoding-Handling (UTF-16-BOM inkl. Fallback auf Header-Charset) lebt
AUSSCHLIESSLICH hier — der Alt-Pfad in ``email_import/email_parser.py``
importiert die Helferfunktion ``dekodiere_email_payload`` und dupliziert
sie nicht.

SPF/DKIM: der IMAP-Adapter liest den ``Authentication-Results``-Header und
haelt das Ergebnis als ``auth_status`` an der Body-Zustellung fest (F-02).

Der Adapter beruehrt den Alt-Pfad nicht. Er wird zusaetzlich zum
bestehenden Import-Service aufgerufen (Doppelschreiben).
"""
from __future__ import annotations

import email
import email.header
import email.policy
import logging
import re
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from ..db.database import get_connection
from ._persistenz import (
    erzeuge_zustellung,
    oder_intake_dokument_fuer_datei,
    oder_intake_dokument_fuer_text,
)

logger = logging.getLogger(__name__)


# ── Absender-Registry-Lookup (S1.4) ─────────────────────────────────────────


def _absender_signale_fuer_domain(domain: str | None) -> dict:
    """
    Sucht die Domain in ``email_absender_vorlagen`` und liefert die Signale
    fuer ``zustellungen.signale_json`` zurueck. Unbekannte Domain oder Fehler
    (z.B. Tabelle noch nicht auf S1.4-Stand) → leeres Dict.

    Der Lookup ist reines Signal, kein Routing (v7-Regel: vererbte Signale
    nur Kandidaten).
    """
    if not domain:
        return {}
    domain = domain.strip().lower()
    if not domain:
        return {}
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT kategorie, versicherer_name, klasse_kandidat, "
                "       vertrauensstufe "
                "FROM email_absender_vorlagen "
                "WHERE LOWER(domain) = ? AND aktiv = 1",
                (domain,),
            ).fetchone()
    except Exception as e:
        logger.debug("Absender-Registry-Lookup fehlgeschlagen: %s", e)
        return {}
    if row is None:
        return {}
    signale: dict[str, Any] = {}
    if row["kategorie"]:
        signale["absender_kategorie"] = row["kategorie"]
    if row["versicherer_name"]:
        signale["versicherer_name"] = row["versicherer_name"]
    if row["klasse_kandidat"]:
        signale["klasse_kandidat"] = row["klasse_kandidat"]
    if row["vertrauensstufe"] is not None:
        signale["vertrauensstufe"] = row["vertrauensstufe"]
    return signale


def _domain_aus_from_header(from_header: str) -> str | None:
    """From: Max <a@b.de> oder From: a@b.de → 'b.de'."""
    if not from_header:
        return None
    m = re.search(r"<([^>]+)>", from_header)
    email_addr = m.group(1) if m else from_header
    if "@" not in email_addr:
        return None
    return email_addr.split("@")[-1].strip().lower() or None


# ── Encoding-Helfer (eigene Wahrheitsquelle, aus email_parser hierher umgezogen)


def dekodiere_email_payload(payload: bytes, charset: str | None = None) -> str:
    """
    Dekodiert einen E-Mail-Payload zu str. UTF-16-BOM (LE/BE) hat Vorrang
    vor dem MIME-Charset-Header, weil Outlook/Exchange oft UTF-16 sendet und
    dabei einen falschen Charset angibt.

    Ist der Payload leer, wird der leere String zurueckgegeben.
    """
    if not payload:
        return ""
    if payload[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return payload.decode("utf-16", errors="replace")
        except Exception:
            pass
    if not charset:
        charset = "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        # Unbekanntes charset -> UTF-8 als Fallback.
        return payload.decode("utf-8", errors="replace")


# ── Anhang- und Body-Extraktion (adapter-lokal, KEIN Import aus email_parser)


_ERLAUBTE_ANHANG_ENDUNGEN = ("pdf", "docx", "doc", "jpg", "jpeg", "png")


def _decode_header(raw: str) -> str:
    try:
        teile = email.header.decode_header(raw)
        out = []
        for teil, charset in teile:
            if isinstance(teil, bytes):
                out.append(teil.decode(charset or "utf-8", errors="replace"))
            else:
                out.append(teil)
        return "".join(out)
    except Exception:
        return raw or ""


def _extrahiere_body_text(msg: EmailMessage) -> str:
    """
    Body-Text priorisiert text/plain; wenn nur HTML vorliegt, wird HTML
    minimal in Text konvertiert.

    Nutzt ``dekodiere_email_payload`` — die UTF-16-BOM-Erkennung ist damit
    nur hier implementiert.
    """
    text_teile: list[str] = []
    html_teile: list[str] = []
    try:
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = dekodiere_email_payload(payload, charset)
            if ct == "text/plain":
                text_teile.append(decoded)
            elif ct == "text/html":
                html_teile.append(decoded)
    except Exception as e:
        logger.debug("Body-Extraktion (IMAP-Adapter): %s", e)

    if text_teile:
        return "\n".join(text_teile).strip()
    if html_teile:
        return _html_zu_text("\n".join(html_teile))
    return ""


def _html_zu_text(html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", "", html,
                  flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<(br|p|div|tr)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&lt;", "<")
            .replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"'))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extrahiere_anhaenge(msg: EmailMessage) -> list[dict]:
    """
    Liefert eine Liste von Dicts mit den Keys ``dateiname``, ``endung``,
    ``daten`` fuer alle Anhaenge mit erlaubter Endung.
    """
    ergebnisse: list[dict] = []
    try:
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            fn = part.get_filename()
            if not fn or "attachment" not in cd:
                continue
            dateiname = _decode_header(fn)
            endung = Path(dateiname).suffix.lstrip(".").lower()
            if endung not in _ERLAUBTE_ANHANG_ENDUNGEN:
                continue
            daten = part.get_payload(decode=True)
            if not daten:
                continue
            ergebnisse.append({
                "dateiname": dateiname,
                "endung": endung,
                "daten": daten,
            })
    except Exception as e:
        logger.warning("Anhang-Extraktion (IMAP-Adapter): %s", e)
    return ergebnisse


# ── Signale-Parser


_SPF_RE = re.compile(r"\bspf\s*=\s*([A-Za-z]+)")
_DKIM_RE = re.compile(r"\bdkim\s*=\s*([A-Za-z]+)")


def _auth_status_aus_header(header: str | None) -> str | None:
    """
    Extrahiert SPF/DKIM aus dem ``Authentication-Results``-Header als
    kompaktes Kuerzel ``spf=pass;dkim=fail`` (F-02).
    """
    if not header:
        return None
    spf = _SPF_RE.search(header)
    dkim = _DKIM_RE.search(header)
    teile = []
    if spf:
        teile.append(f"spf={spf.group(1).lower()}")
    if dkim:
        teile.append(f"dkim={dkim.group(1).lower()}")
    return ";".join(teile) if teile else None


def _empfangen_am_iso(header: str | None) -> str | None:
    if not header:
        return None
    try:
        return parsedate_to_datetime(header).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


# ── Haupt-Einstieg


def verarbeite_email(
    roh_bytes: bytes,
    *,
    konto: str | None = None,
    roh_referenz: str | None = None,
) -> dict[str, Any]:
    """
    Zerlegt eine RFC-822-E-Mail in eine Body-Zustellung + n Anhang-Zustellungen
    und schreibt sie in ``intake_dokumente`` + ``zustellungen``.

    Rueckgabe::

        {
          "body":     {"intake_dokument_id": int, "zustellung_id": int,
                       "sha256": str},
          "anhaenge": [{"dateiname": str, "intake_dokument_id": int,
                        "zustellung_id": int, "sha256": str}, ...],
        }

    Idempotenz: identische E-Mail-Bytes fuehren pro Aufruf zu einer NEUEN
    Zustellung (Zustellungen sind der Log), aber zu KEINEN neuen Dokumenten,
    wenn sha256 bereits bekannt ist. Doppelaufruf ist damit fachlich
    inkorrekt (haette zwei Zustellungen statt einer), aber technisch stabil;
    die Duplikat-Pruefung auf message_id liegt weiter im Alt-Pfad.
    """
    try:
        msg = email.message_from_bytes(roh_bytes, policy=email.policy.default)
    except Exception as e:
        logger.warning("IMAP-Adapter: E-Mail nicht parsebar: %s", e)
        return {"body": None, "anhaenge": []}

    betreff = _decode_header(msg.get("Subject", "") or "")
    absender = msg.get("From", "") or ""
    empfangen_am = _empfangen_am_iso(msg.get("Date"))
    auth_status = _auth_status_aus_header(msg.get("Authentication-Results"))

    body_text = _extrahiere_body_text(msg)
    anhaenge = _extrahiere_anhaenge(msg)

    body_signale: dict[str, Any] = {
        "message_id": (msg.get("Message-ID") or "").strip("<>").strip() or None,
    }
    # S1.4: Absender-Registry-Signale in die Body-Zustellung anreichern.
    absender_signale = _absender_signale_fuer_domain(
        _domain_aus_from_header(absender)
    )
    body_signale.update(absender_signale)

    body_intake_id, body_sha = oder_intake_dokument_fuer_text(body_text)
    body_zust_id = erzeuge_zustellung(
        body_intake_id,
        quelle="imap",
        absender=absender[:200] if absender else None,
        auth_status=auth_status,
        betreff=betreff[:500] if betreff else None,
        empfangen_am=empfangen_am,
        signale=body_signale,
        konto=konto,
        roh_referenz=roh_referenz,
    )

    anhang_ergebnisse: list[dict] = []
    for anh in anhaenge:
        intake_id, sha = oder_intake_dokument_fuer_datei(anh["daten"], anh["endung"])
        zust_id = erzeuge_zustellung(
            intake_id,
            quelle="imap",
            parent_id=body_zust_id,
            absender=absender[:200] if absender else None,
            auth_status=auth_status,
            betreff=betreff[:500] if betreff else None,
            empfangen_am=empfangen_am,
            signale={"dateiname": anh["dateiname"]},
            konto=konto,
            roh_referenz=roh_referenz,
        )
        anhang_ergebnisse.append({
            "dateiname": anh["dateiname"],
            "intake_dokument_id": intake_id,
            "zustellung_id": zust_id,
            "sha256": sha,
        })

    return {
        "body": {
            "intake_dokument_id": body_intake_id,
            "zustellung_id": body_zust_id,
            "sha256": body_sha,
        },
        "anhaenge": anhang_ergebnisse,
    }
