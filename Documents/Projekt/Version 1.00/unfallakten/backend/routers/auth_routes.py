"""
Modul 2 – Auth-Routen (Flask Blueprint)
=========================================
REST-Endpunkte für Authentifizierung und Benutzerverwaltung.

Endpunkte:
  POST   /auth/register          Admin legt neuen Benutzer an
  POST   /auth/login             Login → gibt Token-Paar zurück
  POST   /auth/refresh           Erneuert Access Token per Refresh Token
  POST   /auth/logout            Logout (Client-seitig, Token wird invalidiert)
  GET    /auth/profil            Eigenes Profil abrufen
  POST   /auth/passwort-aendern  Passwort ändern
  GET    /auth/benutzer          Alle Benutzer listen (nur Admin)
  DELETE /auth/benutzer/<id>     Benutzer deaktivieren (nur Admin)
  GET    /auth/ping              Healthcheck (kein Auth nötig)
"""

import logging
from flask import Blueprint, request, jsonify, g
from ..auth.service import (
    registriere, login, refresh_token, aendere_passwort,
    liste_alle_benutzer, deaktiviere, hole_profil,
    AuthFehler
)
from ..auth.validierung import Validierungsfehler
from ..auth.middleware import login_erforderlich, nur_admin

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _erfolg(daten: dict, status: int = 200):
    return jsonify(daten), status

def _fehler(nachricht: str, status: int, feld: str = None):
    body = {"fehler": nachricht, "status": status}
    if feld:
        body["feld"] = feld
    return jsonify(body), status

def _json_body() -> dict:
    """Liest JSON-Body – gibt leeres Dict zurück wenn kein Body."""
    return request.get_json(silent=True) or {}


# ── Healthcheck ───────────────────────────────────────────────────────────────

@auth_bp.route("/ping", methods=["GET"])
def ping():
    """
    GET /auth/ping
    Healthcheck – kein Token erforderlich. Zeigt auch DB-Status.
    """
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            user_count = conn.execute("SELECT COUNT(*) AS n FROM benutzer WHERE aktiv=1").fetchone()["n"]
            users = conn.execute("SELECT email, rolle FROM benutzer WHERE aktiv=1").fetchall()
            schema_ver = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"]
            unfallakte_cols = [c[1] for c in conn.execute("PRAGMA table_info(unfallakte)").fetchall()]
        return _erfolg({
            "status": "ok",
            "modul": "auth",
            "db": {
                "schema_version": schema_ver,
                "benutzer_anzahl": user_count,
                "benutzer": [dict(u) for u in users],
                "unfallakte_pk": "az" if "az" in unfallakte_cols else "id (ALT!)",
            }
        })
    except Exception as e:
        return _erfolg({"status": "ok", "db_fehler": str(e)})


# ── Registrierung ─────────────────────────────────────────────────────────────

@auth_bp.route("/register", methods=["POST"])
@nur_admin
def register():
    """
    POST /auth/register
    Legt einen neuen Benutzer an. Nur für Admins.

    Body:
      { "name": "...", "email": "...", "passwort": "...", "rolle": "sachbearbeiter" }

    Response 201:
      { "id": 1, "name": "...", "email": "...", "rolle": "...", ... }
    """
    daten = _json_body()

    try:
        benutzer = registriere(daten, anfordernder_benutzer_id=g.benutzer_id)
        return _erfolg(benutzer, 201)
    except Validierungsfehler as e:
        return _fehler(e.nachricht, 422, e.feld)
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)


@auth_bp.route("/register/erster", methods=["POST"])
def register_erster():
    """
    POST /auth/register/erster
    Registriert den ERSTEN Benutzer (Bootstrap) ohne Auth.
    Nur erlaubt wenn noch kein Benutzer existiert.

    Body: { "name": "...", "email": "...", "passwort": "..." }
    Die Rolle wird automatisch auf 'admin' gesetzt.
    """
    from ..models.benutzer import liste_benutzer
    if liste_benutzer():
        return _fehler("Erster Benutzer bereits angelegt.", 409)

    daten = _json_body()
    daten["rolle"] = "admin"   # Erster Benutzer ist immer Admin

    try:
        benutzer = registriere(daten, anfordernder_benutzer_id=None)
        return _erfolg({"nachricht": "Admin-Account erstellt.", "benutzer": benutzer}, 201)
    except Validierungsfehler as e:
        return _fehler(e.nachricht, 422, e.feld)
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["POST"])
def login_route():
    """
    POST /auth/login
    Authentifiziert einen Benutzer.
    """
    daten = _json_body()

    try:
        ergebnis = login(daten)
        return _erfolg(ergebnis)
    except Validierungsfehler as e:
        return _fehler(e.nachricht, 422, e.feld)
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error("Login-Fehler (ungefangen): %s\n%s", e, tb)
        # Im Debug-Modus echte Fehlermeldung zurückgeben
        import os
        if os.environ.get("FLASK_DEBUG", "").lower() == "true" or \
           os.environ.get("LOG_LEVEL", "").upper() == "DEBUG":
            return jsonify({"fehler": f"Interner Fehler: {e}", "traceback": tb, "status": 500}), 500
        return jsonify({"fehler": f"Serverfehler beim Login: {type(e).__name__}: {e}", "status": 500}), 500


# ── Token-Refresh ─────────────────────────────────────────────────────────────

@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """
    POST /auth/refresh
    Erneuert den Access Token.

    Body:
      { "refresh_token": "eyJ..." }

    Response 200:
      { "access_token": "eyJ...", "refresh_token": "eyJ...", ... }
    """
    daten = _json_body()
    tok = daten.get("refresh_token", "")

    if not tok:
        return _fehler("Kein refresh_token im Body angegeben.", 400)

    try:
        ergebnis = refresh_token(tok)
        return _erfolg(ergebnis)
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route("/logout", methods=["POST"])
@login_erforderlich
def logout():
    """
    POST /auth/logout
    Logout. JWT ist stateless – der Client löscht die Tokens.
    Server-seitig wird nur ein Aktivitäts-Log geschrieben.

    Response 200:
      { "nachricht": "Erfolgreich abgemeldet." }
    """
    from ..models.dokument import logge_aktivitaet
    logge_aktivitaet(
        aktion="logout",
        beschreibung=f"Benutzer {g.benutzer.email} hat sich abgemeldet.",
        benutzer_id=g.benutzer_id,
    )
    return _erfolg({"nachricht": "Erfolgreich abgemeldet."})


# ── Profil ────────────────────────────────────────────────────────────────────

@auth_bp.route("/profil", methods=["GET"])
@login_erforderlich
def profil():
    """
    GET /auth/profil
    Gibt das Profil des eingeloggten Benutzers zurück.

    Response 200:
      { "id": 1, "name": "...", "email": "...", "rolle": "...", ... }
    """
    try:
        return _erfolg(hole_profil(g.benutzer_id))
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)


# ── Passwortänderung ──────────────────────────────────────────────────────────

@auth_bp.route("/passwort-aendern", methods=["POST"])
@login_erforderlich
def passwort_aendern():
    """
    POST /auth/passwort-aendern
    Ändert das eigene Passwort.

    Body:
      { "altes_passwort": "...", "neues_passwort": "..." }

    Response 200:
      { "nachricht": "Passwort erfolgreich geändert." }
    """
    daten = _json_body()
    altes  = daten.get("altes_passwort", "")
    neues  = daten.get("neues_passwort", "")

    if not altes:
        return _fehler("altes_passwort ist erforderlich.", 422, "altes_passwort")
    if not neues:
        return _fehler("neues_passwort ist erforderlich.", 422, "neues_passwort")

    try:
        ergebnis = aendere_passwort(g.benutzer_id, altes, neues)
        return _erfolg(ergebnis)
    except Validierungsfehler as e:
        return _fehler(e.nachricht, 422, e.feld)
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)


# ── Benutzerverwaltung (Admin) ────────────────────────────────────────────────

@auth_bp.route("/benutzer", methods=["GET"])
@nur_admin
def alle_benutzer():
    """
    GET /auth/benutzer
    Gibt alle aktiven Benutzer zurück. Nur für Admins.

    Response 200:
      [ { "id": 1, "name": "...", "rolle": "..." }, ... ]
    """
    try:
        return _erfolg(liste_alle_benutzer(g.benutzer_id))
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)


@auth_bp.route("/benutzer/<int:benutzer_id>", methods=["DELETE"])
@nur_admin
def benutzer_deaktivieren(benutzer_id: int):
    """
    DELETE /auth/benutzer/<id>
    Deaktiviert einen Benutzer (Soft-Delete). Nur für Admins.

    Response 200:
      { "nachricht": "Benutzer 2 wurde deaktiviert." }
    """
    try:
        ergebnis = deaktiviere(benutzer_id, g.benutzer_id)
        return _erfolg(ergebnis)
    except AuthFehler as e:
        return _fehler(e.nachricht, e.status_code)
