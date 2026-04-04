"""
Router: Forderungshistorie
===========================
REST-Endpunkte für die Forderungsposition-Tabelle.

Endpunkte:
  GET  /akten/<az>/forderungen            Alle Positionen (mit Filteroptionen)
  GET  /akten/<az>/forderungen/zusammenfassung  Aggregierte Kennzahlen
  GET  /akten/<az>/forderungen/schreiben  Positionen gruppiert nach Schreiben-Nr.
  PATCH /akten/<az>/forderungen/<id>      Status / Klage-Flag aktualisieren
  POST  /akten/<az>/forderungen/klage     Klage-Flag für mehrere IDs setzen

Hinweis: Das Anlegen (POST) erfolgt automatisch beim Generieren eines
Forderungsschreibens in word_service.generiere_und_speichere() —
kein manueller POST-Endpunkt nötig.
"""

import logging
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ..models.akte import hole_akte_by_id
from ..models.forderung import (
    hole_forderung_positionen,
    hole_forderung_nach_schreiben,
    forderungs_zusammenfassung,
    aktualisiere_position,
    setze_klage_flag,
    GUELTIGE_STATUS,
)

logger = logging.getLogger(__name__)

forderung_bp = Blueprint(
    "forderung", __name__,
    url_prefix="/akten/<path:akte_id>/forderungen"
)


def _j(d, s=200): return jsonify(d), s
def _err(m, s=400, **kw): return jsonify({"fehler": m, **kw}), s


def _pos_dict(p) -> dict:
    return {
        "id":                    p.id,
        "akte_id":               p.akte_id,
        "dokument_id":           p.dokument_id,
        "forderungsschreiben_nr": p.forderungsschreiben_nr,
        "datum":                 p.datum,
        "position_key":          p.position_key,
        "position_label":        p.position_label,
        "betrag_gefordert":      p.betrag_gefordert,
        "betrag_reguliert":      p.betrag_reguliert,
        "differenz":             p.differenz,
        "status":                p.status,
        "fuer_klage":            p.fuer_klage,
        "kuerzungsart_id":       p.kuerzungsart_id,
        "kuerzung_begruendung":  p.kuerzung_begruendung,
        "erfasst_am":            p.erfasst_am,
    }


# ── GET /akten/<az>/forderungen ───────────────────────────────────────────────

@forderung_bp.route("", methods=["GET"])
@login_erforderlich
def liste(akte_id: str):
    """
    Alle Forderungspositionen einer Akte.

    Query-Parameter:
      nur_offen=1      → status != 'vollreguliert'
      fuer_klage=1/0   → nur Klage-markierte / ohne Klage-Flag
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    nur_offen  = request.args.get("nur_offen", "0") == "1"
    fk_param   = request.args.get("fuer_klage")
    fuer_klage = True if fk_param == "1" else (False if fk_param == "0" else None)

    positionen = hole_forderung_positionen(akte_id, nur_offen=nur_offen, fuer_klage=fuer_klage)
    return _j({
        "positionen": [_pos_dict(p) for p in positionen],
        "anzahl":     len(positionen),
    })


# ── GET /akten/<az>/forderungen/zusammenfassung ───────────────────────────────

@forderung_bp.route("/zusammenfassung", methods=["GET"])
@login_erforderlich
def zusammenfassung(akte_id: str):
    """Aggregierte Kennzahlen: Summen, offene Beträge, Klagepotential."""
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    return _j(forderungs_zusammenfassung(akte_id))


# ── GET /akten/<az>/forderungen/schreiben ────────────────────────────────────

@forderung_bp.route("/schreiben", methods=["GET"])
@login_erforderlich
def nach_schreiben(akte_id: str):
    """
    Positionen gruppiert nach Forderungsschreiben-Nummer.
    Nützlich für die Verlaufsansicht im Frontend.
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    grouped = hole_forderung_nach_schreiben(akte_id)
    result = []
    for nr in sorted(grouped):
        positionen = grouped[nr]
        result.append({
            "schreiben_nr":      nr,
            "datum":             positionen[0].datum if positionen else None,
            "dokument_id":       positionen[0].dokument_id if positionen else None,
            "gesamt_gefordert":  round(sum(p.betrag_gefordert for p in positionen), 2),
            "gesamt_reguliert":  round(sum(p.betrag_reguliert for p in positionen), 2),
            "positionen_offen":  sum(1 for p in positionen if p.status == "gefordert"),
            "positionen":        [_pos_dict(p) for p in positionen],
        })

    return _j({"schreiben": result, "anzahl": len(result)})


# ── PATCH /akten/<az>/forderungen/<id> ───────────────────────────────────────

@forderung_bp.route("/<int:position_id>", methods=["PATCH"])
@login_erforderlich
def aktualisiere(akte_id: str, position_id: int):
    """
    Aktualisiert Status, Regulierungsbetrag oder Klage-Flag einer Position.

    Body (alle Felder optional):
      {
        "status":              "gekuerzt",
        "betrag_reguliert":    1200.00,
        "fuer_klage":          true,
        "kuerzungsart_id":     3,
        "kuerzung_begruendung": "Stundenverrechnungssatz nicht anerkannt"
      }
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = request.get_json(silent=True) or {}

    status            = daten.get("status")
    betrag_reguliert  = daten.get("betrag_reguliert")
    fuer_klage        = daten.get("fuer_klage")
    kuerzungsart_id   = daten.get("kuerzungsart_id")
    kuerzung_begruendung = daten.get("kuerzung_begruendung")

    if status is not None and status not in GUELTIGE_STATUS:
        return _err(
            f"Ungültiger Status '{status}'. "
            f"Erlaubt: {', '.join(GUELTIGE_STATUS)}", 422
        )

    if betrag_reguliert is not None:
        try:
            betrag_reguliert = float(betrag_reguliert)
        except (TypeError, ValueError):
            return _err("betrag_reguliert muss eine Zahl sein.", 422)

    if fuer_klage is not None:
        fuer_klage = bool(fuer_klage)

    try:
        pos = aktualisiere_position(
            position_id,
            status=status,
            betrag_reguliert=betrag_reguliert,
            fuer_klage=fuer_klage,
            kuerzungsart_id=kuerzungsart_id,
            kuerzung_begruendung=kuerzung_begruendung,
        )
    except ValueError as e:
        return _err(str(e), 422)

    if not pos:
        return _err(f"Position {position_id} nicht gefunden oder keine Änderung.", 404)

    return _j({"position": _pos_dict(pos)})


# ── POST /akten/<az>/forderungen/klage ───────────────────────────────────────

@forderung_bp.route("/klage", methods=["POST"])
@login_erforderlich
def klage_flag(akte_id: str):
    """
    Setzt oder entfernt das Klage-Flag für mehrere Positionen gleichzeitig.

    Body:
      {
        "position_ids": [1, 2, 5, 7],
        "fuer_klage":   true
      }
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = request.get_json(silent=True) or {}
    ids       = daten.get("position_ids", [])
    flag      = bool(daten.get("fuer_klage", True))

    if not isinstance(ids, list) or not ids:
        return _err("position_ids muss eine nicht-leere Liste sein.", 422)

    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return _err("position_ids muss eine Liste von Ganzzahlen sein.", 422)

    anzahl = setze_klage_flag(akte_id, ids, flag)
    return _j({
        "aktualisiert": anzahl,
        "fuer_klage":   flag,
    })
