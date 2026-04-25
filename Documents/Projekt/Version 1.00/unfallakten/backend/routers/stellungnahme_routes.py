"""
backend/routers/stellungnahme_routes.py
=========================================
Blueprint: Stellungnahme zum Abrechnungsschreiben

Route:
    POST /akten/<az>/stellungnahme/generieren
        → Generiert Stellungnahme.docx und gibt sie zurück.
        → Body (optional): { "abrechnungsschreiben_id": 123 }
          Wenn angegeben: nur dieses Abrechnungsschreiben berücksichtigen.
          Wenn nicht angegeben: alle Abrechnungsschreiben mit Kürzungen.
"""

import logging
from flask import Blueprint, jsonify, request, Response

from ..models.akte import hole_akte_by_id
from ..models.schaden import hole_beteiligte_by_akte
from ..models.abrechnungsschreiben import hole_abrechnungsschreiben_by_akte
from ..word.stellungnahme_service import generiere_stellungnahme, dateiname_generieren

logger = logging.getLogger(__name__)

# Fester url_prefix – <path:akte_id> pro Route (nicht im Prefix!).
# Lerneffekt v14d: url_prefix mit <path:> am Ende + variable Suffixe = greedy Bug.
stellungnahme_bp = Blueprint("stellungnahme", __name__, url_prefix="/akten")


def _err(msg: str, status: int = 400):
    return jsonify({"fehler": msg}), status


@stellungnahme_bp.route("/<path:akte_id>/stellungnahme/generieren", methods=["POST"])
def generiere(akte_id: str):
    """
    Generiert die Stellungnahme zum Abrechnungsschreiben als DOCX-Download.
    """
    # ── Akte laden (Lerneffekt v14c: nie akte_id direkt in Queries verwenden) ─
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)

    az = akte.aktenzeichen   # ← immer az = akte.aktenzeichen setzen

    # ── Beteiligte laden (Lerneffekt v14e: immer hole_beteiligte_by_akte) ─────
    beteiligte = hole_beteiligte_by_akte(az)

    # ── Abrechnungsschreiben laden ────────────────────────────────────────────
    body = {}
    try:
        body = request.get_json(silent=True) or {}
    except Exception:
        pass

    ab_id_filter = body.get("abrechnungsschreiben_id")

    alle_abrechnungen = hole_abrechnungsschreiben_by_akte(az)
    if not alle_abrechnungen:
        return _err("Keine Abrechnungsschreiben für diese Akte vorhanden.", 404)

    # Optional: nur ein bestimmtes Abrechnungsschreiben berücksichtigen
    if ab_id_filter:
        abrechnungen = [
            ab for ab in alle_abrechnungen
            if (getattr(ab, "id", None) or (ab.get("id") if isinstance(ab, dict) else None)) == ab_id_filter
        ]
        if not abrechnungen:
            return _err(f"Abrechnungsschreiben {ab_id_filter} nicht gefunden.", 404)
    else:
        abrechnungen = alle_abrechnungen

    # ── Prüfe ob Kürzungen vorhanden ─────────────────────────────────────────
    hat_kuerzungen = False
    for ab in abrechnungen:
        positionen = getattr(ab, "positionen", None) or (ab.get("positionen") if isinstance(ab, dict) else None) or []
        for pos in positionen:
            pos_dict = pos if isinstance(pos, dict) else vars(pos) if hasattr(pos, "__dict__") else {}
            gef = float(pos_dict.get("betrag_gefordert") or 0)
            reg = float(pos_dict.get("betrag_reguliert") or 0)
            if round(gef - reg, 2) > 0.005:
                hat_kuerzungen = True
                break
        if hat_kuerzungen:
            break

    if not hat_kuerzungen:
        return _err("Keine Kürzungen in den Abrechnungsschreiben gefunden.", 422)

    # ── custom_texte aus Request-Body ────────────────────────────────────────
    custom_texte = body.get("custom_texte") or {}

    # ── Dokument generieren ───────────────────────────────────────────────────
    try:
        docx_bytes = generiere_stellungnahme(
            az=az,
            akte_daten=akte,
            beteiligte=beteiligte,
            abrechnungen=abrechnungen,
            custom_texte=custom_texte,
        )
    except FileNotFoundError as e:
        logger.error("Stellungnahme-Vorlage fehlt: %s", e)
        return _err(f"Vorlage fehlt: {e}", 500)
    except Exception as e:
        logger.exception("Fehler bei Stellungnahme-Generierung AZ=%s", az)
        return _err(f"Fehler bei der Generierung: {e}", 500)

    dateiname = dateiname_generieren(az)

    return Response(
        docx_bytes,
        status=200,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{dateiname}"',
            "Content-Length":      str(len(docx_bytes)),
        },
    )


@stellungnahme_bp.route("/<path:akte_id>/stellungnahme/vorschau", methods=["GET"])
def vorschau(akte_id: str):
    """
    Gibt aggregierte Kürzungspositionen mit Textbaustein-Vorschlägen zurück.
    Gespeicherte Gegenargumente (stellungnahme_texte) überschreiben den Standard-Vorschlag.
    """
    from ..word.stellungnahme_service import (
        _aggregiere_kuerzungen, _baue_kontext, ersetze_platzhalter
    )
    from ..db.database import get_connection

    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen if hasattr(akte, "aktenzeichen") else akte_id

    beteiligte = hole_beteiligte_by_akte(az)
    alle_abrechnungen = hole_abrechnungsschreiben_by_akte(az)
    if not alle_abrechnungen:
        return jsonify({"positionen": []})

    kuerzungen, _ = _aggregiere_kuerzungen(alle_abrechnungen)
    kontext = _baue_kontext(az, akte, beteiligte)

    saved_texte = {}
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT gruppe_key, gegenargument FROM stellungnahme_texte WHERE az = ?",
                (az,)
            ).fetchall()
            saved_texte = {r["gruppe_key"]: r["gegenargument"] for r in rows}
    except Exception:
        pass

    positionen_out = []
    for k in kuerzungen:
        key = k.get("_gruppe_key", "")
        raw = k.get("standard_gegenargument") or "Die Kürzung ist nicht gerechtfertigt."
        vorschlag = saved_texte.get(key) or ersetze_platzhalter(raw, kontext)
        positionen_out.append({
            "_gruppe_key":            key,
            "bezeichnung":            k.get("bezeichnung", ""),
            "label":                  k.get("label", ""),
            "kuerzung_gesamt":        k.get("kuerzung_gesamt", 0.0),
            "textbaustein_vorschlag": vorschlag,
        })

    return jsonify({"positionen": positionen_out})


@stellungnahme_bp.route("/<path:akte_id>/stellungnahme/texte", methods=["GET"])
def texte_holen(akte_id: str):
    """Gibt gespeicherte Gegenargument-Texte für diese Akte zurück."""
    from ..db.database import get_connection

    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen if hasattr(akte, "aktenzeichen") else akte_id

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT gruppe_key, gegenargument FROM stellungnahme_texte WHERE az = ?",
            (az,)
        ).fetchall()
    return jsonify({r["gruppe_key"]: r["gegenargument"] for r in rows})


@stellungnahme_bp.route("/<path:akte_id>/stellungnahme/texte", methods=["PUT"])
def texte_speichern(akte_id: str):
    """Speichert Gegenargument-Texte aus dem ReguWizard."""
    from ..db.database import get_connection

    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen if hasattr(akte, "aktenzeichen") else akte_id

    body = request.get_json(silent=True) or {}
    texte = body.get("texte", {})
    if not isinstance(texte, dict):
        return _err("'texte' muss ein Objekt {gruppe_key: text} sein.", 400)

    with get_connection() as conn:
        for key, text in texte.items():
            conn.execute(
                "INSERT OR REPLACE INTO stellungnahme_texte "
                "(az, gruppe_key, gegenargument, geaendert_am) "
                "VALUES (?, ?, ?, datetime('now', 'localtime'))",
                (az, key, text or "")
            )

    return jsonify({"ok": True, "gespeichert": len(texte)})
