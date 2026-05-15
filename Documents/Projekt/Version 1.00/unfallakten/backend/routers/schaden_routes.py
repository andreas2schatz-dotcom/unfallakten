"""
Modul 3 – Router: Schaden & Regulierung
=========================================
REST-Endpunkte für Schadenpositionen und Regulierungsvorgänge.

  GET    /akten/<id>/schaden               Schadenpositionen abrufen
  PUT    /akten/<id>/schaden               Schadenpositionen setzen/ersetzen
  GET    /akten/<id>/regulierungen         Alle Regulierungsvorgänge
  POST   /akten/<id>/regulierungen         Neuen Regulierungsvorgang anlegen
  GET    /akten/<id>/regulierungen/status  Aktueller Regulierungsstand
"""

import json
import logging
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ._helpers import pruefe_akte as _pruefe_akte
from ..models.schaden import (
    setze_schadenpositionen, hole_schadenpositionen,
    erstelle_regulierung, hole_regulierungen_by_akte,
    hole_regulierungsstatus, berechne_abrechnungsart,
    hole_beteiligte_by_akte,
)
from ..models.dokument import logge_aktivitaet

logger = logging.getLogger(__name__)

schaden_bp    = Blueprint("schaden",    __name__, url_prefix="/akten/<path:akte_id>/schaden")
regulierung_bp = Blueprint("regulierung", __name__, url_prefix="/akten/<path:akte_id>/regulierungen")


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _j(daten, status=200):
    return jsonify(daten), status

def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status

def _body():
    return request.get_json(silent=True) or {}

def _schaden_dict(s) -> dict:
    """Schadenposition → JSON-Dict für das Frontend."""
    if not s:
        return None
    _extras = []
    if s.wdm_extras_json:
        try:
            parsed = json.loads(s.wdm_extras_json)
            if isinstance(parsed, list):
                _extras = parsed
        except Exception:
            pass
    return {
        "id":                    s.id,
        "akte_id":               s.akte_id,
        "quelle":                s.quelle,
        "erfasst_am":            s.erfasst_am,
        "gesamt_brutto":         s.gesamt_brutto,
        # Fahrzeugschaden
        "reparaturkosten":       s.reparaturkosten,
        "rep_gutachten_netto":   s.rep_gutachten_netto,
        "rep_gutachten_mwst":    s.rep_gutachten_mwst,
        "rep_rechnung_netto":    s.rep_rechnung_netto,
        "rep_rechnung_brutto":   s.rep_rechnung_brutto,
        "wiederbeschaffung":     s.wiederbeschaffung,
        "restwert":              s.restwert,
        "wertminderung":         s.wertminderung,
        "abrechnungsart":        s.abrechnungsart,
        # Nebenkosten (brutto)
        "nutzungsausfall":       s.nutzungsausfall,
        "mietwagenkosten":       s.mietwagenkosten,
        "mietwagenkosten_netto": s.mietwagenkosten_netto,
        "mietwagenkosten_ust":   s.mietwagenkosten_ust,
        "sv_kosten":             s.sv_kosten,
        "sv_kosten_netto":       s.sv_kosten_netto,
        "sv_kosten_ust":         s.sv_kosten_ust,
        "kostennb":              s.kostennb,
        "kostennb_ust":          s.kostennb_ust,
        "abschleppkosten":       s.abschleppkosten,
        "abschleppkosten_netto": s.abschleppkosten_netto,
        "abschleppkosten_ust":   s.abschleppkosten_ust,
        "standkosten":           s.standkosten,
        "standkosten_netto":     s.standkosten_netto,
        "standkosten_ust":       s.standkosten_ust,
        "anabmeldekosten":       s.anabmeldekosten,
        "anabmeldekosten_netto": s.anabmeldekosten_netto,
        "anabmeldekosten_ust":   s.anabmeldekosten_ust,
        # Personenschaden
        "schmerzensgeld":        s.schmerzensgeld,
        "verdienstausfall":      s.verdienstausfall,
        "haushalt":              s.haushalt,
        # Sonstiges
        "unkostenpauschale":     s.unkostenpauschale,
        "sonstiges":             s.sonstiges,
        "sonstiges_beschr":      s.sonstiges_beschr,
        # WDM-Metadaten
        "wdm_extras_json":       s.wdm_extras_json,
        "wdm_info_json":         s.wdm_info_json,
        "_extras":               _extras,
    }


def _reg_dict(r) -> dict:
    return {
        "id":                r.id,
        "akte_id":           r.akte_id,
        "datum":             r.datum,
        "betrag_gefordert":  r.betrag_gefordert,
        "betrag_reguliert":  r.betrag_reguliert,
        "differenz":         r.differenz,
        "status":            r.status,
        "vers_referenz":     r.vers_referenz,
        "kuerz_begruendung": r.kuerz_begruendung,
        "erfasst_am":        r.erfasst_am,
    }


# ── Numerische Felder (aktuelles Schema v15, keine Legacy-Namen) ──────────────

NUMERISCHE_FELDER = [
    # Fahrzeugschaden
    "reparaturkosten",
    "rep_gutachten_netto",   "rep_gutachten_mwst",
    "rep_rechnung_netto",    "rep_rechnung_brutto",
    "wiederbeschaffung",     "restwert",
    "wertminderung",
    # Nebenkosten
    "nutzungsausfall",
    "mietwagenkosten",       "mietwagenkosten_netto",  "mietwagenkosten_ust",
    "sv_kosten",             "sv_kosten_netto",         "sv_kosten_ust",
    "kostennb",              "kostennb_ust",
    "abschleppkosten",       "abschleppkosten_netto",   "abschleppkosten_ust",
    "standkosten",           "standkosten_netto",       "standkosten_ust",
    "anabmeldekosten",       "anabmeldekosten_netto",   "anabmeldekosten_ust",
    # Personenschaden
    "schmerzensgeld",
    "verdienstausfall",
    "haushalt",
    # Sonstiges
    "unkostenpauschale",
    "sonstiges",
]

TEXT_FELDER = [
    "sonstiges_beschr", "quelle", "wdm_extras_json",
    "wdm_info_json", "abrechnungsart",
]


# ══════════════════════════════════════════════════════════════════════════════
# ENDPUNKTE
# ══════════════════════════════════════════════════════════════════════════════

def _abrechnungsberechnung(schaden, akte_id: str) -> dict:
    """
    PRD-14: Single Source of Truth.
    Lädt Vorsteuer-Flag des Mandanten und berechnet Abrechnungsart + Fahrzeugschaden.
    Wird in GET und PUT Response mitgeliefert – Frontend rechnet nie selbst.
    """
    try:
        beteiligte = hole_beteiligte_by_akte(akte_id)
        mandant    = next((b for b in beteiligte if b.rolle == "mandant"), None)
        vorsteuer  = str(getattr(mandant, "vorsteuer", "N") or "N").upper() in ("J", "Y", "JA", "1")
    except Exception:
        vorsteuer  = False
    return berechne_abrechnungsart(schaden, vorsteuer=vorsteuer)


@schaden_bp.route("", methods=["GET"])
@login_erforderlich
def hole_schaden(akte_id: str):
    """GET /akten/<id>/schaden — Schadenpositionen abrufen."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    schaden = hole_schadenpositionen(akte_id)
    if not schaden:
        return _j({"schaden": None, "hinweis": "Noch keine Schadenpositionen erfasst."})
    schaden_dict = _schaden_dict(schaden)
    schaden_dict["abrechnungsberechnung"] = _abrechnungsberechnung(schaden, akte_id)
    return _j({"schaden": schaden_dict})


@schaden_bp.route("", methods=["PUT"])
@login_erforderlich
def setze_schaden(akte_id: str):
    """PUT /akten/<id>/schaden — Schadenpositionen setzen/ersetzen."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = _body()
    positionen = {}

    for feld in NUMERISCHE_FELDER:
        try:
            raw = daten.get(feld, 0)
            val = float(raw) if raw not in (None, "") else 0.0
            if feld == "restwert":
                val = abs(val)
            elif val < 0:
                return _err(f"'{feld}' darf nicht negativ sein.", 422, feld=feld)
            positionen[feld] = val
        except (TypeError, ValueError):
            return _err(f"'{feld}' muss eine Zahl sein.", 422, feld=feld)

    for feld in TEXT_FELDER:
        if feld in daten:
            positionen[feld] = daten[feld]

    # _extras (Frontend-Array) → wdm_extras_json (JSON-String)
    if "_extras" in daten and isinstance(daten["_extras"], list):
        positionen["wdm_extras_json"] = json.dumps(daten["_extras"], ensure_ascii=False)

    schaden = setze_schadenpositionen(
        akte_id=akte_id,
        bearbeiter_id=g.benutzer_id,
        **positionen,
    )

    logge_aktivitaet(
        aktion="schaden_aktualisiert",
        beschreibung=f"Schadenpositionen gesetzt. Gesamt: {schaden.gesamt_brutto:.2f} €",
        akte_id=akte_id,
        benutzer_id=g.benutzer_id,
    )

    schaden_dict = _schaden_dict(schaden)
    schaden_dict["abrechnungsberechnung"] = _abrechnungsberechnung(schaden, akte_id)
    return _j({"schaden": schaden_dict})


# ══════════════════════════════════════════════════════════════════════════════
# REGULIERUNG (DEPRECATED)
# Diese Endpunkte schreiben in die Legacy-Tabelle `regulierung`.
# Das System nutzt jetzt `abrechnungsschreiben + regulierung_positionen` (Option B).
# Endpunkte bleiben erhalten bis alle Clients migriert sind — NICHT löschen.
# ══════════════════════════════════════════════════════════════════════════════

@regulierung_bp.route("", methods=["GET"])
@login_erforderlich
def liste_regulierungen(akte_id: str):
    """GET /akten/<id>/regulierungen — Alle Regulierungsvorgänge. (DEPRECATED)"""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    return _j({"regulierungen": [_reg_dict(r) for r in hole_regulierungen_by_akte(akte_id)]})


@regulierung_bp.route("", methods=["POST"])
@login_erforderlich
def erstelle_reg(akte_id: str):
    """POST /akten/<id>/regulierungen — Regulierungsvorgang anlegen. (DEPRECATED)"""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = _body()
    datum = daten.get("datum", "").strip()
    if not datum:
        return _err("datum ist erforderlich.", 422, feld="datum")

    try:
        gefordert = float(daten.get("betrag_gefordert", 0))
        reguliert = float(daten.get("betrag_reguliert", 0))
    except (TypeError, ValueError):
        return _err("betrag_gefordert und betrag_reguliert müssen Zahlen sein.", 422)

    if gefordert < 0:
        return _err("betrag_gefordert darf nicht negativ sein.", 422)

    try:
        reg = erstelle_regulierung(
            akte_id=akte_id,
            datum=datum,
            betrag_gefordert=gefordert,
            betrag_reguliert=reguliert,
            bearbeiter_id=g.benutzer_id,
            vers_referenz=daten.get("vers_referenz"),
            kuerz_begruendung=daten.get("kuerz_begruendung"),
        )
    except ValueError as e:
        return _err(str(e), 422)

    return _j({"regulierung": _reg_dict(reg)}, 201)


@regulierung_bp.route("/status", methods=["GET"])
@login_erforderlich
def regulierungsstatus(akte_id: str):
    """GET /akten/<id>/regulierungen/status — Aktueller Regulierungsstand. (DEPRECATED: nutze v_regulierungsstatus)"""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    return _j(hole_regulierungsstatus(akte_id))
