"""
Modul 2 – JWT Token-Verwaltung
================================
Erstellt, validiert und erneuert JWT Access- und Refresh-Tokens.

Token-Architektur:
  - Access Token:  Kurzlebig (60 Min), enthält Benutzer-ID und Rolle
  - Refresh Token: Langlebig (7 Tage), enthält nur Benutzer-ID
  - Secret Key:    Aus Umgebungsvariable JWT_SECRET_KEY (PFLICHT in Produktion)

Payload-Struktur:
  {
    "sub":   <benutzer_id>,       # Subject
    "rolle": "admin",             # Nur in Access Token
    "typ":   "access" | "refresh",
    "iat":   <issued_at>,         # Ausgestellt am
    "exp":   <expires_at>         # Ablauf
  }
"""

import os
import jwt
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Konfiguration ─────────────────────────────────────────────────────────────

# In Produktion ZWINGEND als Umgebungsvariable setzen!
# z.B.: export JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
JWT_SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY",
    "DEV_ONLY_INSECURE_KEY_change_in_production_32chars_min"
)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS   = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS",   "7"))

if JWT_SECRET_KEY.startswith("DEV_ONLY"):
    logger.warning(
        "⚠️  JWT_SECRET_KEY ist der unsichere Standard-Entwicklungsschlüssel! "
        "Bitte in Produktion durch eine sichere Umgebungsvariable ersetzen."
    )


# ── Token-Erstellung ───────────────────────────────────────────────────────────

def erstelle_access_token(benutzer_id: int, rolle: str) -> str:
    """
    Erstellt einen signierten JWT Access Token.

    Args:
        benutzer_id: Primärschlüssel des Benutzers
        rolle:       'admin' oder 'sachbearbeiter'

    Returns:
        Signierter JWT-String
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub":   str(benutzer_id),
        "rolle": rolle,
        "typ":   "access",
        "iat":   now,
        "exp":   now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def erstelle_refresh_token(benutzer_id: int) -> str:
    """
    Erstellt einen signierten JWT Refresh Token (keine Rolle enthalten).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub":  str(benutzer_id),
        "typ":  "refresh",
        "iat":  now,
        "exp":  now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "jti":  secrets.token_hex(16),   # JWT ID – eindeutig je Token
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def erstelle_token_paar(benutzer_id: int, rolle: str) -> dict:
    """
    Erstellt Access + Refresh Token in einem Schritt.
    Wird beim Login zurückgegeben.
    """
    access  = erstelle_access_token(benutzer_id, rolle)
    refresh = erstelle_refresh_token(benutzer_id)
    return {
        "access_token":  access,
        "refresh_token": refresh,
        "token_type":    "Bearer",
        "expires_in":    ACCESS_TOKEN_EXPIRE_MINUTES * 60,   # Sekunden
    }


# ── Token-Validierung ──────────────────────────────────────────────────────────

class TokenFehler(Exception):
    """Basisklasse für Token-Fehler."""
    pass

class TokenAbgelaufen(TokenFehler):
    """Token ist abgelaufen."""
    pass

class TokenUngueltig(TokenFehler):
    """Token ist ungültig (falsche Signatur, fehlerhaftes Format etc.)."""
    pass

class TokenTypFehler(TokenFehler):
    """Falscher Token-Typ (z.B. Refresh statt Access)."""
    pass


def validiere_access_token(token: str) -> dict:
    """
    Validiert und dekodiert einen Access Token.

    Returns:
        Payload-Dict mit 'sub' (benutzer_id als str) und 'rolle'

    Raises:
        TokenAbgelaufen:  Token ist abgelaufen
        TokenUngueltig:   Signatur ungültig oder Format fehlerhaft
        TokenTypFehler:   Kein Access Token
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "typ"]}
        )
    except jwt.ExpiredSignatureError:
        raise TokenAbgelaufen("Access Token ist abgelaufen.")
    except jwt.InvalidTokenError as e:
        raise TokenUngueltig(f"Ungültiger Token: {e}")

    if payload.get("typ") != "access":
        raise TokenTypFehler("Kein Access Token übergeben.")

    return payload


def validiere_refresh_token(token: str) -> dict:
    """
    Validiert und dekodiert einen Refresh Token.

    Returns:
        Payload-Dict mit 'sub' (benutzer_id als str)

    Raises:
        TokenAbgelaufen, TokenUngueltig, TokenTypFehler
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat", "typ"]}
        )
    except jwt.ExpiredSignatureError:
        raise TokenAbgelaufen("Refresh Token ist abgelaufen. Bitte neu anmelden.")
    except jwt.InvalidTokenError as e:
        raise TokenUngueltig(f"Ungültiger Refresh Token: {e}")

    if payload.get("typ") != "refresh":
        raise TokenTypFehler("Kein Refresh Token übergeben.")

    return payload


def hole_benutzer_id_aus_token(token: str) -> Optional[int]:
    """
    Extrahiert die Benutzer-ID aus einem Token ohne Fehler zu werfen.
    Gibt None zurück wenn der Token ungültig ist.
    Nützlich für optionale Authentifizierung.
    """
    try:
        payload = validiere_access_token(token)
        return int(payload["sub"])
    except (TokenFehler, ValueError, KeyError):
        return None
