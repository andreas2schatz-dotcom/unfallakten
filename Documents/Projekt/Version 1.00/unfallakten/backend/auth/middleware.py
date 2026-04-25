"""
Modul 2 – Authentifizierungs-Middleware & Dekoratoren
=======================================================
Flask-Dekoratoren und Hilfsfunktionen für:
  - Token-Extraktion aus Authorization-Header
  - Zugriffskontrolle (Login erforderlich)
  - Rollenkontrolle (nur Admin)
  - Aktuellen Benutzer in Flask `g` speichern

Verwendung in Routen:
    @app.route("/geschuetzt")
    @login_erforderlich
    def meine_route():
        benutzer = g.benutzer   # Aktuell eingeloggter Benutzer
        ...

    @app.route("/nur-admin")
    @nur_admin
    def admin_route():
        ...
"""

import logging
import functools
from flask import request, jsonify, g, current_app
from .jwt_handler import (
    validiere_access_token, TokenFehler, TokenAbgelaufen,
    TokenUngueltig, TokenTypFehler
)

logger = logging.getLogger(__name__)


# ── Token-Extraktion ──────────────────────────────────────────────────────────

def _extrahiere_token() -> str | None:
    """
    Liest den Bearer Token aus dem Authorization-Header.
    Format: 'Authorization: Bearer <token>'

    Fallback für SSE (EventSource unterstützt keine Custom-Header):
    Query-Parameter 'token=<token>' wird ebenfalls akzeptiert.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    # SSE-Fallback: ?token=<jwt>
    qs_token = request.args.get("token", "").strip()
    if qs_token:
        return qs_token
    return None


def _lade_benutzer(benutzer_id: int):
    """
    Lädt den Benutzer aus der Datenbank.
    Importiert lazy um Zirkelimporte zu vermeiden.
    """
    from ..models.benutzer import hole_benutzer_by_id
    return hole_benutzer_by_id(benutzer_id)


# ── Fehleantworten ────────────────────────────────────────────────────────────

def _fehler_antwort(nachricht: str, status: int) -> tuple:
    return jsonify({"fehler": nachricht, "status": status}), status


# ── Gemeinsame Auth-Logik ─────────────────────────────────────────────────────

def _authentifiziere():
    """
    Extrahiert Token, validiert ihn und lädt den Benutzer.

    Rückgabe bei Erfolg:  (None, payload, benutzer, benutzer_id)
    Rückgabe bei Fehler:  (fehler_response, None, None, None)
    """
    token = _extrahiere_token()
    if not token:
        return (
            _fehler_antwort(
                "Kein Authentifizierungs-Token angegeben. "
                "Bitte 'Authorization: Bearer <token>' setzen.",
                401
            ),
            None, None, None,
        )

    try:
        payload = validiere_access_token(token)
    except TokenAbgelaufen:
        return _fehler_antwort("Token abgelaufen. Bitte mit dem Refresh Token erneuern.", 401), None, None, None
    except (TokenUngueltig, TokenTypFehler) as e:
        return _fehler_antwort(str(e), 401), None, None, None
    except TokenFehler as e:
        return _fehler_antwort(str(e), 401), None, None, None

    benutzer_id = int(payload["sub"])
    benutzer = _lade_benutzer(benutzer_id)
    if not benutzer:
        return _fehler_antwort("Benutzer nicht gefunden oder deaktiviert.", 403), None, None, None

    return None, payload, benutzer, benutzer_id


# ── Dekoratoren ───────────────────────────────────────────────────────────────

def login_erforderlich(f):
    """
    Dekorator: Stellt sicher, dass ein gültiger Access Token vorhanden ist.
    Speichert den Benutzer in flask.g.benutzer.

    Bei Fehler:
      401 – Kein Token, Token abgelaufen oder ungültig
      403 – Benutzer inaktiv
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        fehler, payload, benutzer, benutzer_id = _authentifiziere()
        if fehler:
            return fehler
        g.benutzer    = benutzer
        g.benutzer_id = benutzer_id
        g.rolle        = payload.get("rolle", "sachbearbeiter")
        return f(*args, **kwargs)
    return wrapper


def nur_admin(f):
    """
    Dekorator: Stellt sicher dass der Benutzer Admin-Rolle hat.

    Verwendung:
        @app.route("/admin-bereich")
        @nur_admin
        def admin_bereich():
            ...
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        fehler, payload, benutzer, benutzer_id = _authentifiziere()
        if fehler:
            return fehler
        if payload.get("rolle") != "admin":
            return _fehler_antwort(
                "Zugriff verweigert. Diese Aktion erfordert Admin-Rechte.",
                403
            )
        g.benutzer    = benutzer
        g.benutzer_id = benutzer_id
        g.rolle        = "admin"
        return f(*args, **kwargs)
    return wrapper


def optionale_auth(f):
    """
    Dekorator: Authentifizierung ist optional.
    Falls ein gültiger Token vorhanden ist, wird g.benutzer gesetzt.
    Falls nicht, läuft die Route als anonymer Zugriff weiter.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        g.benutzer    = None
        g.benutzer_id = None
        g.rolle        = None

        token = _extrahiere_token()
        if token:
            try:
                payload = validiere_access_token(token)
                benutzer_id = int(payload["sub"])
                benutzer = _lade_benutzer(benutzer_id)
                if benutzer:
                    g.benutzer    = benutzer
                    g.benutzer_id = benutzer_id
                    g.rolle        = payload.get("rolle")
            except TokenFehler:
                pass  # Stiller Fehler bei optionaler Auth

        return f(*args, **kwargs)
    return wrapper
