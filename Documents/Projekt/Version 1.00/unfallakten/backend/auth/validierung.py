"""
Modul 2 – Eingabe-Validierung
==============================
Validierungsfunktionen für Registrierung, Login und Passwortänderung.
Keine externen Abhängigkeiten – nur Python-Stdlib.
"""

import re
from typing import Optional


class Validierungsfehler(Exception):
    """Wird geworfen wenn Eingaben die Validierung nicht bestehen."""
    def __init__(self, feld: str, nachricht: str):
        self.feld = feld
        self.nachricht = nachricht
        super().__init__(f"{feld}: {nachricht}")

    def als_dict(self) -> dict:
        return {"feld": self.feld, "nachricht": self.nachricht}


# ── E-Mail ────────────────────────────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

def validiere_email(email: str) -> str:
    """Gibt bereinigte E-Mail zurück oder wirft Validierungsfehler."""
    email = email.strip().lower()
    if not email:
        raise Validierungsfehler("email", "E-Mail darf nicht leer sein.")
    if len(email) > 254:
        raise Validierungsfehler("email", "E-Mail ist zu lang (max. 254 Zeichen).")
    if not _EMAIL_REGEX.match(email):
        raise Validierungsfehler("email", "Ungültiges E-Mail-Format.")
    return email


# ── Passwort ──────────────────────────────────────────────────────────────────

def validiere_passwort(passwort: str, feld: str = "passwort") -> str:
    """
    Prüft Passwort-Komplexität.
    Mindestanforderungen:
      - 8 Zeichen Mindestlänge
      - 1 Großbuchstabe
      - 1 Kleinbuchstabe
      - 1 Zahl
    """
    if not passwort:
        raise Validierungsfehler(feld, "Passwort darf nicht leer sein.")
    if len(passwort) < 8:
        raise Validierungsfehler(feld, "Passwort muss mindestens 8 Zeichen lang sein.")
    if len(passwort) > 128:
        raise Validierungsfehler(feld, "Passwort ist zu lang (max. 128 Zeichen).")
    if not re.search(r"[A-Z]", passwort):
        raise Validierungsfehler(feld, "Passwort muss mindestens einen Großbuchstaben enthalten.")
    if not re.search(r"[a-z]", passwort):
        raise Validierungsfehler(feld, "Passwort muss mindestens einen Kleinbuchstaben enthalten.")
    if not re.search(r"\d", passwort):
        raise Validierungsfehler(feld, "Passwort muss mindestens eine Zahl enthalten.")
    return passwort


# ── Name ──────────────────────────────────────────────────────────────────────

def validiere_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise Validierungsfehler("name", "Name darf nicht leer sein.")
    if len(name) < 2:
        raise Validierungsfehler("name", "Name muss mindestens 2 Zeichen lang sein.")
    if len(name) > 100:
        raise Validierungsfehler("name", "Name ist zu lang (max. 100 Zeichen).")
    return name


# ── Rolle ─────────────────────────────────────────────────────────────────────

def validiere_rolle(rolle: str) -> str:
    if rolle not in ("admin", "sachbearbeiter"):
        raise Validierungsfehler(
            "rolle",
            f"Ungültige Rolle '{rolle}'. Erlaubt: 'admin', 'sachbearbeiter'."
        )
    return rolle


# ── Registrierungs-Payload ────────────────────────────────────────────────────

def validiere_registrierung(daten: dict) -> dict:
    """
    Validiert alle Felder einer Registrierungsanfrage.
    Returns: Bereinigtes Dict mit validierten Werten.
    Raises:  Validierungsfehler beim ersten Problem.
    """
    return {
        "name":   validiere_name(daten.get("name", "")),
        "email":  validiere_email(daten.get("email", "")),
        "passwort": validiere_passwort(daten.get("passwort", "")),
        "rolle":  validiere_rolle(daten.get("rolle", "sachbearbeiter")),
    }


# ── Login-Payload ─────────────────────────────────────────────────────────────

def validiere_login(daten: dict) -> dict:
    """Validiert Login-Felder."""
    email    = daten.get("email", "")
    passwort = daten.get("passwort", "")
    if not email:
        raise Validierungsfehler("email", "E-Mail ist erforderlich.")
    if not passwort:
        raise Validierungsfehler("passwort", "Passwort ist erforderlich.")
    return {
        "email":    email.strip().lower(),
        "passwort": passwort,
    }
