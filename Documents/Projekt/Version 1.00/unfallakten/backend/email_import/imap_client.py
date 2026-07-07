"""
Modul 7 – IMAP-Client
======================
Stellt eine Verbindung zu einem IMAP-Postfach her und ruft
ungelesene Nachrichten ab.

Konfiguration per Umgebungsvariablen:
  EMAIL_HOST      IMAP-Server (z.B. mail.anwalt-offenbach.de)
  EMAIL_PORT      IMAP-Port (Standard: 993 für SSL)
  EMAIL_USER      IMAP-Benutzer (z.B. akten@anwalt-offenbach.de)
  EMAIL_PASSWORD  IMAP-Passwort
  EMAIL_FOLDER    Zielordner (Standard: INBOX)
  EMAIL_MAX_FETCH Maximale Nachrichten pro Lauf (Standard: 50)

Unterstützte Protokolle:
  - IMAP4_SSL (Port 993) – Standard
  - IMAP4    (Port 143 + STARTTLS) – Fallback

Verwendung:
  with imap_verbinden() as client:
      nachrichten = hole_ungelesene(client)
      for msg_id, roh_bytes in nachrichten:
          verarbeite(msg_id, roh_bytes)
          markiere_als_gelesen(client, msg_id)
"""

import os
import ssl
import imaplib
import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)

# ── Konfiguration aus Umgebungsvariablen ──────────────────────────────────────

def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def get_imap_config() -> dict:
    """Liest IMAP-Konfiguration aus Umgebungsvariablen."""
    return {
        "host":      _cfg("EMAIL_HOST"),
        "port":      int(_cfg("EMAIL_PORT", "993")),
        "user":      _cfg("EMAIL_USER"),
        "password":  _cfg("EMAIL_PASSWORD"),
        "folder":    _cfg("EMAIL_FOLDER", "INBOX"),
        "max_fetch": int(_cfg("EMAIL_MAX_FETCH", "50")),
        "ssl":       _cfg("EMAIL_PORT", "993") != "143",
    }


def ist_konfiguriert() -> bool:
    """Prüft ob alle Pflichtfelder gesetzt sind."""
    cfg = get_imap_config()
    return bool(cfg["host"] and cfg["user"] and cfg["password"])


# ── Verbindung aufbauen ───────────────────────────────────────────────────────

class ImapVerbindungsFehler(Exception):
    pass


@contextmanager
def imap_verbinden(config: dict = None) -> Iterator[imaplib.IMAP4]:
    """
    Context-Manager: Baut eine IMAP-Verbindung auf und schließt sie sauber.

    Usage:
        with imap_verbinden() as imap:
            nachrichten = hole_ungelesene(imap)

    Raises:
        ImapVerbindungsFehler bei Verbindungs- oder Login-Fehlern
    """
    if config is None:
        config = get_imap_config()

    if not config["host"]:
        raise ImapVerbindungsFehler("EMAIL_HOST nicht konfiguriert.")
    if not config["user"] or not config["password"]:
        raise ImapVerbindungsFehler(
            "EMAIL_USER oder EMAIL_PASSWORD nicht konfiguriert."
        )

    imap = None
    try:
        logger.info("IMAP-Verbindung zu %s:%d ...", config["host"], config["port"])

        if config["ssl"]:
            ctx = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(
                host=config["host"],
                port=config["port"],
                ssl_context=ctx,
            )
        else:
            imap = imaplib.IMAP4(host=config["host"], port=config["port"])
            imap.starttls()

        imap.login(config["user"], config["password"])
        logger.info("IMAP-Login erfolgreich als %s.", config["user"])

        # Ordner auswählen
        status, _ = imap.select(config["folder"])
        if status != "OK":
            raise ImapVerbindungsFehler(
                f"Ordner '{config['folder']}' nicht gefunden."
            )

        yield imap

    except imaplib.IMAP4.error as e:
        raise ImapVerbindungsFehler(f"IMAP-Fehler: {e}") from e
    except OSError as e:
        raise ImapVerbindungsFehler(
            f"Netzwerkfehler bei Verbindung zu {config['host']}: {e}"
        ) from e
    finally:
        if imap is not None:
            try:
                imap.close()
                imap.logout()
                logger.debug("IMAP-Verbindung geschlossen.")
            except Exception:
                pass  # Beste-Mühe beim Schließen


# ── Nachrichten abrufen ───────────────────────────────────────────────────────

def hole_ungelesene(imap: imaplib.IMAP4,
                    max_fetch: int = 50) -> list[tuple[bytes, bytes]]:
    """
    Gibt eine Liste von (message_uid, roh_bytes) für ungelesene Nachrichten zurück.
    Verwendet UIDs statt Sequenznummern (stabil über Sitzungen hinweg).

    Args:
        imap:      Aktive IMAP-Verbindung (nach select())
        max_fetch: Maximale Anzahl abzurufender Nachrichten

    Returns:
        Liste von (uid_bytes, roh_email_bytes)
    """
    # Ungelesene UIDs suchen
    typ, daten = imap.uid("SEARCH", None, "UNSEEN")
    if typ != "OK" or not daten[0]:
        logger.debug("Keine ungelesenen Nachrichten gefunden.")
        return []

    uid_liste = daten[0].split()
    # Neueste zuerst (letzte UIDs = neueste Nachrichten)
    uid_liste = uid_liste[-max_fetch:]
    logger.info("%d ungelesene Nachricht(en) gefunden.", len(uid_liste))

    ergebnisse = []
    for uid in uid_liste:
        try:
            typ, msg_daten = imap.uid("FETCH", uid, "(RFC822)")
            if typ != "OK" or not msg_daten or not msg_daten[0]:
                logger.warning("UID %s: Abruf fehlgeschlagen.", uid)
                continue
            roh = msg_daten[0][1]
            ergebnisse.append((uid, roh))
        except Exception as e:
            logger.warning("UID %s: Fehler beim Abruf: %s", uid, e)
            continue

    return ergebnisse


def markiere_als_gelesen(imap: imaplib.IMAP4, uid: bytes) -> bool:
    """
    Markiert eine Nachricht als gelesen (\\Seen-Flag setzen).

    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        typ, _ = imap.uid("STORE", uid, "+FLAGS", "(\\Seen)")
        return typ == "OK"
    except Exception as e:
        logger.warning("Konnte UID %s nicht als gelesen markieren: %s", uid, e)
        return False


def verschiebe_in_ordner(imap: imaplib.IMAP4, uid: bytes,
                          zielordner: str) -> bool:
    """
    Verschiebt eine Nachricht in einen anderen IMAP-Ordner (z.B. 'Verarbeitet').
    Erstellt den Ordner wenn er nicht existiert.

    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        # Ordner anlegen wenn nötig
        imap.create(zielordner)
    except imaplib.IMAP4.error:
        pass  # Ordner existiert bereits

    try:
        typ, _ = imap.uid("COPY", uid, zielordner)
        if typ != "OK":
            return False
        imap.uid("STORE", uid, "+FLAGS", "(\\Deleted)")
        imap.expunge()
        return True
    except Exception as e:
        logger.warning("Verschieben von UID %s nach '%s' fehlgeschlagen: %s",
                        uid, zielordner, e)
        return False


# ── UA-Ordner-Verwaltung (unfall@ Workflow) ───────────────────────────────────

_UA_ORDNER = {
    "eingang":     "UA_Eingang",
    "verarbeitet": "UA_Verarbeitet",
    "geloescht":   "UA_DELETED",
}


def _hole_trennzeichen(imap: imaplib.IMAP4) -> str:
    """Liest den IMAP-Hierarchietrenner aus der Server-Antwort ('/' oder '.')."""
    import re as _re
    try:
        typ, daten = imap.list("", "INBOX")
        if typ == "OK" and daten and daten[0]:
            raw = daten[0].decode() if isinstance(daten[0], bytes) else str(daten[0])
            m = _re.search(r'"([./\\])"', raw)
            if m:
                return m.group(1)
    except Exception:
        pass
    return "/"


def verschiebe_in_ua(imap: imaplib.IMAP4, uid: bytes, ziel_key: str) -> bool:
    """
    Verschiebt eine E-Mail aus dem aktuell selektierten Ordner (INBOX)
    nach INBOX/{sep}UA_xxx. Erstellt den Zielordner bei Bedarf.

    ziel_key: 'eingang' | 'verarbeitet' | 'geloescht'
    """
    name = _UA_ORDNER.get(ziel_key, ziel_key)
    sep  = _hole_trennzeichen(imap)
    ziel = f"INBOX{sep}{name}"
    try:
        imap.create(ziel)
    except imaplib.IMAP4.error:
        pass
    return verschiebe_in_ordner(imap, uid, ziel)


def suche_und_verschiebe_ua(
    cfg: dict,
    message_id: str,
    quell_key: str,
    ziel_key: str,
) -> bool:
    """
    Öffnet eine neue IMAP-Verbindung, sucht eine E-Mail anhand der Message-ID
    in INBOX/{UA_quell} und verschiebt sie nach INBOX/{UA_ziel}.
    Gibt True zurück wenn eine E-Mail bewegt wurde (best effort, kein Fehler bei Misserfolg).
    """
    if not message_id or not cfg:
        return False
    quell_name = _UA_ORDNER.get(quell_key, quell_key)
    ziel_name  = _UA_ORDNER.get(ziel_key,  ziel_key)
    try:
        with imap_verbinden(cfg) as imap:
            sep        = _hole_trennzeichen(imap)
            quell_pfad = f"INBOX{sep}{quell_name}"
            ziel_pfad  = f"INBOX{sep}{ziel_name}"

            try:
                imap.create(ziel_pfad)
            except imaplib.IMAP4.error:
                pass

            typ, _ = imap.select(quell_pfad)
            if typ != "OK":
                logger.warning("UA-Quellordner '%s' nicht vorhanden.", quell_pfad)
                return False

            typ, daten = imap.uid("SEARCH", "HEADER", "Message-ID", message_id)
            if typ != "OK" or not daten[0]:
                logger.debug("Message-ID '%s' nicht in '%s' gefunden.", message_id, quell_pfad)
                return False

            bewegt = False
            for uid in daten[0].split():
                if verschiebe_in_ordner(imap, uid, ziel_pfad):
                    bewegt = True
            return bewegt
    except Exception as e:
        logger.warning("suche_und_verschiebe_ua (%s→%s): %s", quell_name, ziel_name, e)
        return False


# ── Verbindungstest ───────────────────────────────────────────────────────────

def teste_verbindung(config: dict = None) -> dict:
    """
    Testet die IMAP-Verbindung und gibt einen Status zurück.

    Returns:
        {"ok": True/False, "nachricht": str, "ungelesen": int}
    """
    try:
        with imap_verbinden(config) as imap:
            typ, daten = imap.uid("SEARCH", None, "UNSEEN")
            anzahl = len(daten[0].split()) if typ == "OK" and daten[0] else 0
            return {
                "ok": True,
                "nachricht": "Verbindung erfolgreich.",
                "ungelesen": anzahl,
            }
    except ImapVerbindungsFehler as e:
        return {"ok": False, "nachricht": str(e), "ungelesen": 0}
