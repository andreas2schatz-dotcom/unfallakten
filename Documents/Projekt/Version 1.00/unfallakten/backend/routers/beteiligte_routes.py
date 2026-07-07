"""
Modul 3 – Router: Beteiligte
==============================
REST-Endpunkte für Beteiligte einer Unfallakte.

Endpunkte:
  GET    /akten/<id>/beteiligte           Alle Beteiligten einer Akte
  POST   /akten/<id>/beteiligte           Beteiligten hinzufügen
  PATCH  /akten/<id>/beteiligte/<bid>     Beteiligten aktualisieren
  DELETE /akten/<id>/beteiligte/<bid>     Beteiligten entfernen
"""

import logging
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ._helpers import pruefe_akte as _pruefe_akte
from ..models.beteiligte import beteiligter_as_dict as _b_dict
from ..models.schaden import (
    erstelle_beteiligten, hole_beteiligte_by_akte,
    aktualisiere_beteiligten, loesche_beteiligten,
    GUELTIGE_ROLLEN
)
from ..models.dokument import logge_aktivitaet

logger = logging.getLogger(__name__)
beteiligte_bp = Blueprint("beteiligte", __name__,
                           url_prefix="/akten/<path:akte_id>/beteiligte")


def _j(daten, status=200):
    return jsonify(daten), status

def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status

def _body():
    return request.get_json(silent=True) or {}

@beteiligte_bp.route("", methods=["GET"])
@login_erforderlich
def liste(akte_id: str):
    """
    GET /akten/<id>/beteiligte
    Gibt alle Beteiligten einer Akte zurück.
    Wenn SQLite keine Beteiligte hat, wird RA-Micro als Fallback genutzt.

    Query-Parameter:
      rolle  Filter nach Rolle (mandant/gegner/zeuge/sachverstaendiger/sonstiger)
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    rolle = request.args.get("rolle")
    beteiligte = hole_beteiligte_by_akte(akte_id, rolle=rolle)

    def _ra_eintrag(ra_rolle: str, b: dict) -> dict:
        """Wandelt einen RA-Micro-Beteiligten-Dict in das API-Format um."""
        return {
            "id": None,  # nicht in SQLite → Adressat-Dropdown zeigt ihn an, Generator lädt Adresse selbst
            "akte_id": akte_id,
            "rolle": ra_rolle,
            "name":        b.get("name", ""),
            "vorname":     b.get("vorname", ""),
            "firma":       b.get("firma"),
            "anschrift":   b.get("anschrift"),
            "plz":         b.get("plz"),
            "ort":         b.get("ort"),
            "telefon":     b.get("telefon"),
            "email":       b.get("email"),
            "versicherung":b.get("versicherung"),
            "vers_nr":     None,
            "schaden_nr":  b.get("schaden_nr"),
            "iban":        None,
            "notizen":     None,
            "vollstaendiger_name": f"{b.get('vorname','')} {b.get('name','')}".strip(),
            "anrede":      b.get("anrede", ""),
            "vorsteuer":   b.get("vorsteuer", "N"),
            "kuerzel":     b.get("kuerzel", ""),
            "briefanrede": b.get("briefanrede", ""),
            "betreff1":    b.get("betreff1", ""),
            "betreff2":    b.get("betreff2", ""),
            "betreff3":    b.get("betreff3", ""),
        }

    # Single Source of Truth: RA-MICRO ist primär.
    # SQLite liefert nur eigene Ergänzungen (manuell angelegte Einträge / Anreicherungen).
    # RA-MICRO-Einträge werden immer hinzugefügt, sofern kein namensgleicher SQLite-Eintrag existiert.
    sqlite_liste = [_b_dict(b) for b in beteiligte]
    try:
        from ..word.word_service import _lade_beteiligte_aus_ramicro
        ra = _lade_beteiligte_aus_ramicro(akte_id)
        if ra:
            namen_sqlite = {
                n for b in sqlite_liste
                for n in filter(None, [
                    (b.get("name") or "").strip().lower(),
                    (b.get("firma") or "").strip().lower(),
                ])
            }
            hat_mandant = any(b.get("rolle") == "mandant" for b in sqlite_liste)

            def _merge(rb, ra_rolle):
                if not rb:
                    return
                rb_name = (rb.get("name") or rb.get("firma") or "").strip().lower()
                if rb_name and rb_name in namen_sqlite:
                    return
                sqlite_liste.append(_ra_eintrag(ra_rolle, rb))
                if rb_name:
                    namen_sqlite.add(rb_name)

            def _gegner_rolle(rb):
                kz = (rb.get("kuerzel") or "").strip().upper()
                if kz.startswith("SV"):
                    return "sachverstaendiger"
                if kz in ("SAB", "RSV", "SB"):
                    return "sonstiger"
                return "gegner"

            if not hat_mandant:
                _merge(ra.get("mandant"), "mandant")
            for rb in (ra.get("alle_gegner") or []):
                _merge(rb, _gegner_rolle(rb))
            for rb in (ra.get("sonstige") or []):
                _merge(rb, rb.get("rolle") or "sonstiger")
    except Exception as e:
        logger.debug("RA-Micro-Merge Beteiligte: %s", e)

    if rolle:
        sqlite_liste = [b for b in sqlite_liste if b.get("rolle") == rolle]
    return _j({"beteiligte": sqlite_liste})


@beteiligte_bp.route("", methods=["POST"])
@login_erforderlich
def erstelle(akte_id: str):
    """
    POST /akten/<id>/beteiligte
    Fügt einen Beteiligten zur Akte hinzu.

    Body:
      {
        "rolle":  "mandant",
        "name":   "Mustermann",
        "vorname": "Max",
        "kfz_kennzeichen": "OF-MM 1",
        "versicherung": "HUK Coburg",
        ...
      }

    Response 201: Angelegter Beteiligter
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = _body()
    rolle = daten.get("rolle", "").strip()
    name  = daten.get("name", "").strip()

    if not rolle:
        return _err("rolle ist erforderlich.", 422, feld="rolle")
    if not name:
        return _err("name ist erforderlich.", 422, feld="name")

    # Optionale Felder übergeben
    optionale = {
        k: daten[k] for k in [
            "vorname", "firma", "anschrift", "plz", "ort", "telefon",
            "email", "kfz_kennzeichen", "kfz_typ", "versicherung",
            "vers_nr", "schaden_nr", "iban", "notizen"
        ] if k in daten
    }

    try:
        b = erstelle_beteiligten(akte_id, rolle, name, **optionale)
    except ValueError as e:
        return _err(str(e), 422)

    logge_aktivitaet(
        aktion="beteiligter_hinzugefuegt",
        beschreibung=f"{rolle.capitalize()} '{name}' zur Akte hinzugefügt.",
        akte_id=akte_id,
        benutzer_id=g.benutzer_id,
    )

    return _j(_b_dict(b), 201)


@beteiligte_bp.route("/<int:beteiligter_id>", methods=["PATCH"])
@login_erforderlich
def aktualisiere(akte_id: str, beteiligter_id: int):
    """
    PATCH /akten/<id>/beteiligte/<bid>
    Aktualisiert einen Beteiligten.
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = _body()
    erlaubte = {
        "name", "vorname", "firma", "anschrift", "plz", "ort",
        "telefon", "email", "kfz_kennzeichen", "kfz_typ",
        "versicherung", "vers_nr", "schaden_nr", "iban", "notizen",
        "ist_halter"
    }
    felder = {k: v for k, v in daten.items() if k in erlaubte}

    if not felder:
        return _err("Keine aktualisierbaren Felder im Body.", 422)

    upd = aktualisiere_beteiligten(beteiligter_id, **felder)
    if not upd:
        return _err(f"Beteiligter {beteiligter_id} nicht gefunden.", 404)

    return _j(_b_dict(upd))


@beteiligte_bp.route("/<int:beteiligter_id>", methods=["DELETE"])
@login_erforderlich
def loesche(akte_id: str, beteiligter_id: int):
    """
    DELETE /akten/<id>/beteiligte/<bid>
    Entfernt einen Beteiligten aus der Akte.
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    from ..models.schaden import loesche_beteiligten as db_loesche
    erfolg = db_loesche(beteiligter_id)
    if not erfolg:
        return _err(f"Beteiligter {beteiligter_id} nicht gefunden.", 404)

    logge_aktivitaet(
        aktion="beteiligter_entfernt",
        beschreibung=f"Beteiligter {beteiligter_id} aus Akte entfernt.",
        akte_id=akte_id,
        benutzer_id=g.benutzer_id,
    )
    return _j({"nachricht": f"Beteiligter {beteiligter_id} gelöscht."})
