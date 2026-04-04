"""
Modul 1 – Model: Benutzer
==========================
Datenzugriffsschicht für die Tabelle `benutzer`.
Alle Datenbankoperationen für Benutzer sind hier gebündelt.
"""

import hashlib
import os
import sqlite3
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from ..db.database import get_connection

logger = logging.getLogger(__name__)


@dataclass
class Benutzer:
    """Repräsentiert einen Kanzleimitarbeiter."""
    id: Optional[int]
    name: str
    email: str
    rolle: str                  # 'admin' | 'sachbearbeiter'
    aktiv: bool
    erstellt_am: str
    zuletzt_login: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Benutzer":
        return cls(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            rolle=row["rolle"],
            aktiv=bool(row["aktiv"]),
            erstellt_am=row["erstellt_am"],
            zuletzt_login=row["zuletzt_login"],
        )


def _hash_passwort(passwort: str, salt: Optional[str] = None) -> str:
    """
    Sicheres Passwort-Hashing mit PBKDF2-HMAC-SHA256.
    Format: salt$hash (beide hex-kodiert)
    Hinweis: In Produktion mit bcrypt ersetzen (sobald Paket verfügbar).
    """
    if salt is None:
        salt = os.urandom(32).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        passwort.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=260_000      # OWASP-Empfehlung 2024
    )
    return f"{salt}${key.hex()}"


def verify_passwort(passwort: str, passwort_hash: str) -> bool:
    """Prüft ein Passwort gegen einen gespeicherten Hash."""
    try:
        salt, _ = passwort_hash.split("$", 1)
        expected = _hash_passwort(passwort, salt)
        return expected == passwort_hash
    except ValueError:
        return False


# ── CRUD ──────────────────────────────────────────────────────────────────────

def erstelle_benutzer(name: str, email: str, passwort: str,
                       rolle: str = "sachbearbeiter") -> Benutzer:
    """
    Legt einen neuen Benutzer an.
    Raises: ValueError bei ungültiger Rolle oder doppelter E-Mail.
    """
    if rolle not in ("admin", "sachbearbeiter"):
        raise ValueError(f"Ungültige Rolle: {rolle!r}")

    passwort_hash = _hash_passwort(passwort)

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO benutzer (name, email, passwort_hash, rolle)
                VALUES (?, ?, ?, ?)
                """,
                (name, email.lower().strip(), passwort_hash, rolle)
            )
            row = conn.execute(
                "SELECT * FROM benutzer WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            logger.info("Benutzer erstellt: %s (%s)", email, rolle)
            return Benutzer.from_row(row)
        except sqlite3.IntegrityError:
            raise ValueError(f"E-Mail bereits registriert: {email}")


def hole_benutzer_by_id(benutzer_id: int) -> Optional[Benutzer]:
    """Gibt einen Benutzer anhand der ID zurück."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM benutzer WHERE id = ? AND aktiv = 1", (benutzer_id,)
        ).fetchone()
        return Benutzer.from_row(row) if row else None


def hole_benutzer_by_email(email: str) -> Optional[tuple[Benutzer, str]]:
    """
    Gibt (Benutzer, passwort_hash) zurück – für Login-Prozess.
    Gibt None zurück wenn nicht gefunden oder inaktiv.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM benutzer WHERE email = ? AND aktiv = 1",
            (email.lower().strip(),)
        ).fetchone()
        if not row:
            return None
        return Benutzer.from_row(row), row["passwort_hash"]


def liste_benutzer() -> list[Benutzer]:
    """Gibt alle aktiven Benutzer zurück."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM benutzer WHERE aktiv = 1 ORDER BY name"
        ).fetchall()
        return [Benutzer.from_row(r) for r in rows]


def aktualisiere_letzten_login(benutzer_id: int) -> None:
    """Aktualisiert den Timestamp des letzten Logins."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE benutzer SET zuletzt_login = datetime('now', 'localtime') WHERE id = ?",
            (benutzer_id,)
        )


def deaktiviere_benutzer(benutzer_id: int) -> bool:
    """Soft-Delete: Benutzer wird deaktiviert, nicht gelöscht."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE benutzer SET aktiv = 0 WHERE id = ?", (benutzer_id,)
        )
        return cursor.rowcount > 0
