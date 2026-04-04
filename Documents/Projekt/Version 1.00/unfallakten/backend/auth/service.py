"""
Modul 2 – Auth-Service
=======================
Business-Logik für Authentifizierung und Benutzerverwaltung.
Verbindet Modul-1-Models mit JWT-Handler.

Alle Funktionen hier sind framework-unabhängig und direkt testbar.
"""

import logging
from typing import Optional
from ..models.benutzer import (
    erstelle_benutzer as db_erstelle_benutzer,
    hole_benutzer_by_id,
    hole_benutzer_by_email,
    verify_passwort,
    liste_benutzer as db_liste_benutzer,
    deaktiviere_benutzer as db_deaktiviere_benutzer,
    aktualisiere_letzten_login,
    _hash_passwort,
)
from ..models.dokument import logge_aktivitaet
from .jwt_handler import erstelle_token_paar, validiere_refresh_token, TokenFehler
from .validierung import (
    validiere_registrierung, validiere_login,
    validiere_passwort, Validierungsfehler
)
from ..db.database import get_connection

logger = logging.getLogger(__name__)


class AuthFehler(Exception):
    """Allgemeiner Authentifizierungsfehler."""
    def __init__(self, nachricht: str, status_code: int = 401):
        self.nachricht = nachricht
        self.status_code = status_code
        super().__init__(nachricht)


# ── Registrierung ─────────────────────────────────────────────────────────────

def registriere(daten: dict, anfordernder_benutzer_id: Optional[int] = None) -> dict:
    """
    Registriert einen neuen Benutzer.

    Nur Admins dürfen neue Benutzer anlegen.
    Der allererste Benutzer (leere DB) kann ohne Auth registriert werden.

    Args:
        daten: Dict mit name, email, passwort, rolle
        anfordernder_benutzer_id: ID des anfragenden Admins (None = erster Benutzer)

    Returns:
        Dict mit Benutzer-Info (ohne Passwort)

    Raises:
        AuthFehler bei Zugriffsproblemen
        Validierungsfehler bei ungültigen Eingaben
    """
    # Ersten Benutzer ohne Auth-Prüfung erlauben
    if anfordernder_benutzer_id is not None:
        admin = hole_benutzer_by_id(anfordernder_benutzer_id)
        if not admin or admin.rolle != "admin":
            raise AuthFehler(
                "Nur Admins dürfen neue Benutzer anlegen.", 403
            )

    validiert = validiere_registrierung(daten)

    try:
        benutzer = db_erstelle_benutzer(
            name=validiert["name"],
            email=validiert["email"],
            passwort=validiert["passwort"],
            rolle=validiert["rolle"],
        )
    except ValueError as e:
        raise Validierungsfehler("email", str(e))

    logge_aktivitaet(
        aktion="benutzer_registriert",
        beschreibung=f"Neuer Benutzer angelegt: {benutzer.email} ({benutzer.rolle})",
        benutzer_id=anfordernder_benutzer_id,
    )

    logger.info("Benutzer registriert: %s", benutzer.email)
    return _benutzer_als_dict(benutzer)


# ── Login ─────────────────────────────────────────────────────────────────────

def login(daten: dict) -> dict:
    """
    Authentifiziert einen Benutzer und gibt Token-Paar zurück.

    Args:
        daten: Dict mit email und passwort

    Returns:
        Dict mit access_token, refresh_token, token_type, expires_in, benutzer

    Raises:
        AuthFehler:         Ungültige Anmeldedaten oder inaktiver Benutzer
        Validierungsfehler: Fehlende Pflichtfelder
    """
    validiert = validiere_login(daten)

    # Benutzer suchen
    ergebnis = hole_benutzer_by_email(validiert["email"])
    if not ergebnis:
        # Timing-sicherer Vergleich: Auch bei nicht-existentem Benutzer
        # einen Hash-Vergleich durchführen um Timing-Angriffe zu vermeiden
        _dummy_hash_check()
        raise AuthFehler("E-Mail oder Passwort falsch.")

    benutzer, pw_hash = ergebnis

    if not verify_passwort(validiert["passwort"], pw_hash):
        raise AuthFehler("E-Mail oder Passwort falsch.")

    if not benutzer.aktiv:
        raise AuthFehler("Dieses Konto wurde deaktiviert. Bitte Admin kontaktieren.", 403)

    # Letzten Login aktualisieren (nicht-fatal)
    try:
        aktualisiere_letzten_login(benutzer.id)
    except Exception as e:
        logger.warning("aktualisiere_letzten_login fehlgeschlagen: %s", e)

    # Aktivität loggen (nicht-fatal – darf Login nicht blockieren)
    try:
        logge_aktivitaet(
            aktion="login",
            beschreibung=f"Benutzer {benutzer.email} hat sich angemeldet.",
            benutzer_id=benutzer.id,
        )
    except Exception as log_err:
        logger.warning("Login-Aktivität konnte nicht geloggt werden: %s", log_err)

    token_paar = erstelle_token_paar(benutzer.id, benutzer.rolle)
    token_paar["benutzer"] = _benutzer_als_dict(benutzer)

    logger.info("Login: %s", benutzer.email)
    return token_paar


def _dummy_hash_check():
    """Führt einen nutzlosen Hash-Vergleich durch um Timing-Angriffe zu erschweren."""
    import hashlib
    hashlib.pbkdf2_hmac("sha256", b"dummy", b"salt", 1000)


# ── Token-Refresh ─────────────────────────────────────────────────────────────

def refresh_token(refresh_tok: str) -> dict:
    """
    Erneuert den Access Token anhand eines gültigen Refresh Tokens.

    Args:
        refresh_tok: Gültiger Refresh Token

    Returns:
        Neues Token-Paar

    Raises:
        AuthFehler bei ungültigem oder abgelaufenem Refresh Token
    """
    try:
        payload = validiere_refresh_token(refresh_tok)
    except TokenFehler as e:
        raise AuthFehler(str(e))

    benutzer_id = int(payload["sub"])
    benutzer = hole_benutzer_by_id(benutzer_id)

    if not benutzer:
        raise AuthFehler("Benutzer nicht gefunden.", 404)
    if not benutzer.aktiv:
        raise AuthFehler("Benutzer ist deaktiviert.", 403)

    token_paar = erstelle_token_paar(benutzer.id, benutzer.rolle)
    token_paar["benutzer"] = _benutzer_als_dict(benutzer)

    logger.debug("Token erneuert für Benutzer-ID: %d", benutzer_id)
    return token_paar


# ── Passwortänderung ──────────────────────────────────────────────────────────

def aendere_passwort(benutzer_id: int, altes_passwort: str,
                      neues_passwort: str) -> dict:
    """
    Ändert das Passwort eines Benutzers.

    Args:
        benutzer_id:     ID des Benutzers
        altes_passwort:  Aktuelles Passwort (zur Verifikation)
        neues_passwort:  Neues Passwort

    Returns:
        Erfolgsmeldung als Dict

    Raises:
        AuthFehler:         Falsches altes Passwort
        Validierungsfehler: Neues Passwort erfüllt Anforderungen nicht
    """
    ergebnis = hole_benutzer_by_id(benutzer_id)
    if not ergebnis:
        raise AuthFehler("Benutzer nicht gefunden.", 404)

    # Altes Passwort prüfen
    from ..models.benutzer import hole_benutzer_by_email
    ergebnis_mit_hash = hole_benutzer_by_email(ergebnis.email)
    if not ergebnis_mit_hash:
        raise AuthFehler("Benutzer nicht gefunden.", 404)

    _, pw_hash = ergebnis_mit_hash
    if not verify_passwort(altes_passwort, pw_hash):
        raise AuthFehler("Aktuelles Passwort ist falsch.")

    # Neues Passwort validieren
    validiere_passwort(neues_passwort, feld="neues_passwort")

    # Hash erstellen und speichern
    neuer_hash = _hash_passwort(neues_passwort)
    with get_connection() as conn:
        conn.execute(
            "UPDATE benutzer SET passwort_hash = ? WHERE id = ?",
            (neuer_hash, benutzer_id)
        )

    logge_aktivitaet(
        aktion="passwort_geaendert",
        beschreibung="Benutzer hat sein Passwort geändert.",
        benutzer_id=benutzer_id,
    )

    return {"nachricht": "Passwort erfolgreich geändert."}


# ── Benutzer-Verwaltung (Admin) ───────────────────────────────────────────────

def liste_alle_benutzer(anfordernder_benutzer_id: int) -> list:
    """Gibt alle aktiven Benutzer zurück. Nur für Admins."""
    admin = hole_benutzer_by_id(anfordernder_benutzer_id)
    if not admin or admin.rolle != "admin":
        raise AuthFehler("Nur Admins können Benutzerlisten abrufen.", 403)

    return [_benutzer_als_dict(b) for b in db_liste_benutzer()]


def deaktiviere(benutzer_id: int, anfordernder_benutzer_id: int) -> dict:
    """Deaktiviert einen Benutzer. Nur für Admins."""
    admin = hole_benutzer_by_id(anfordernder_benutzer_id)
    if not admin or admin.rolle != "admin":
        raise AuthFehler("Nur Admins können Benutzer deaktivieren.", 403)

    if benutzer_id == anfordernder_benutzer_id:
        raise AuthFehler("Sie können Ihren eigenen Account nicht deaktivieren.", 400)

    erfolg = db_deaktiviere_benutzer(benutzer_id)
    if not erfolg:
        raise AuthFehler("Benutzer nicht gefunden.", 404)

    logge_aktivitaet(
        aktion="benutzer_deaktiviert",
        beschreibung=f"Benutzer-ID {benutzer_id} wurde deaktiviert.",
        benutzer_id=anfordernder_benutzer_id,
    )
    return {"nachricht": f"Benutzer {benutzer_id} wurde deaktiviert."}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _benutzer_als_dict(benutzer) -> dict:
    """Serialisiert einen Benutzer – ohne sensible Felder."""
    return {
        "id":            benutzer.id,
        "name":          benutzer.name,
        "email":         benutzer.email,
        "rolle":         benutzer.rolle,
        "aktiv":         benutzer.aktiv,
        "erstellt_am":   benutzer.erstellt_am,
        "zuletzt_login": benutzer.zuletzt_login,
    }


def hole_profil(benutzer_id: int) -> dict:
    """Gibt das Profil des eingeloggten Benutzers zurück."""
    benutzer = hole_benutzer_by_id(benutzer_id)
    if not benutzer:
        raise AuthFehler("Benutzer nicht gefunden.", 404)
    return _benutzer_als_dict(benutzer)
