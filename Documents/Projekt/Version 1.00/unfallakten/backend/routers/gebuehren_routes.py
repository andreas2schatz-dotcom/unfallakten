"""
Gebührenassistent-Router – PRD-28
===================================
Endpunkte für den RVG-Gebührenassistenten (Nr. 2300 VV RVG).

Endpunkte:
  GET  /akten/<az>/gebuehren              Lade Kriterien + Vorschlag + gespeicherte Berechnung
  POST /akten/<az>/gebuehren/analysieren  Frische Analyse (ohne Speichern)
  PUT  /akten/<az>/gebuehren              Kriterien + Ergebnis speichern
  POST /akten/<az>/gebuehren/word         Word-Kostennote generieren
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, g
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..models.akte import hole_akte_by_id
from ..services.gebuehren_service import analysiere_akte, berechne_faktor_vorschlag
from ..word.klage_service import berechne_rvg

logger = logging.getLogger(__name__)

gebuehren_bp = Blueprint("gebuehren", __name__, url_prefix="/akten/<path:akte_id>")


def _j(data, status=200):
    return jsonify(data), status


def _err(msg, status=400):
    return jsonify({"fehler": msg}), status


# ── GET /akten/<az>/gebuehren ─────────────────────────────────────────────────

@gebuehren_bp.route("/gebuehren", methods=["GET"])
@login_erforderlich
def lade_gebuehren(akte_id):
    """
    Lädt auto-analysierte Kriterien aus der Akte + gespeicherte Berechnung (falls vorhanden).
    Berechnet immer einen Vorschlag basierend auf den aktuellen Daten.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.aktenzeichen

    with get_connection() as conn:
        kriterien = analysiere_akte(az, conn)
        if kriterien is None:
            return _err("Akte konnte nicht analysiert werden.", 404)

        vorschlag = berechne_faktor_vorschlag(kriterien)

        # Gespeicherte Berechnung laden (falls vorhanden)
        gespeichert = conn.execute(
            "SELECT * FROM gebuehren_berechnung WHERE akte_id = ?", (az,)
        ).fetchone()

        # Streitwert aus forderung_positionen
        fw = conn.execute(
            "SELECT SUM(betrag_gefordert) as s FROM forderung_positionen WHERE akte_id = ?",
            (az,)
        ).fetchone()
        streitwert = float(fw["s"] or 0) if fw else 0.0

        # Fallback: Summe der Hauptpositionen aus schadenpositionen
        if streitwert == 0.0:
            sp = conn.execute(
                """SELECT CASE WHEN COALESCE(rep_rechnung_brutto, 0) > 0
                               THEN rep_rechnung_brutto
                               ELSE COALESCE(rep_gutachten_netto, 0) END
                          + COALESCE(wiederbeschaffung, 0) - COALESCE(restwert, 0)
                          + COALESCE(wertminderung, 0) + COALESCE(nutzungsausfall, 0)
                          + COALESCE(mietwagenkosten, 0) + COALESCE(sv_kosten, 0)
                          + COALESCE(schmerzensgeld, 0) + COALESCE(verdienstausfall, 0)
                          + COALESCE(unkostenpauschale, 0) as summe
                   FROM schadenpositionen WHERE akte_id = ?""",
                (az,)
            ).fetchone()
            if sp:
                streitwert = float(sp["summe"] or 0)

    faktor = float(gespeichert["faktor_final"]) if gespeichert and gespeichert["faktor_final"] else vorschlag["faktor"]
    rvg = berechne_rvg(streitwert, faktor)
    rvg["streitwert"] = streitwert

    return _j({
        "kriterien":     kriterien,
        "vorschlag":     vorschlag,
        "gespeichert":   dict(gespeichert) if gespeichert else None,
        "rvg":           rvg,
    })


# ── POST /akten/<az>/gebuehren/analysieren ────────────────────────────────────

@gebuehren_bp.route("/gebuehren/analysieren", methods=["POST"])
@login_erforderlich
def analysiere(akte_id):
    """
    Führt eine frische Analyse durch (optional mit manuell übermittelten Kriterien).
    Speichert NICHT in der DB.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.aktenzeichen

    daten = request.get_json(silent=True) or {}

    with get_connection() as conn:
        kriterien = analysiere_akte(az, conn)
        if kriterien is None:
            return _err("Akte konnte nicht analysiert werden.", 404)

    # Manuelle Überschreibungen aus dem Request-Body einspielen
    for feld in ["auslandsbezug", "todesfall", "verletzungsgrad",
                 "pflegebedarf", "haftung_streitig"]:
        if feld in daten:
            kriterien[feld] = daten[feld]

    # fehlende_felder neu berechnen
    fehlende = []
    if kriterien.get("hat_personenschaden") and kriterien.get("verletzungsgrad") == "keine":
        if "verletzungsgrad" not in daten:
            fehlende.append("verletzungsgrad")
    kriterien["fehlende_felder"] = fehlende

    vorschlag = berechne_faktor_vorschlag(kriterien)

    streitwert = float(daten.get("streitwert", 0))
    faktor = float(daten.get("faktor", vorschlag["faktor"]))
    rvg = berechne_rvg(streitwert, faktor)
    rvg["streitwert"] = streitwert

    return _j({
        "kriterien": kriterien,
        "vorschlag":  vorschlag,
        "rvg":        rvg,
    })


# ── PUT /akten/<az>/gebuehren ─────────────────────────────────────────────────

@gebuehren_bp.route("/gebuehren", methods=["PUT"])
@login_erforderlich
def speichere_gebuehren(akte_id):
    """
    Speichert Kriterien + Berechnung:
      - unfallakte: auslandsbezug, todesfall, haftung_streitig
      - personenschaden: verletzungsgrad, pflegebedarf
      - gebuehren_berechnung: UPSERT
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.aktenzeichen

    daten = request.get_json(silent=True) or {}
    kriterien  = daten.get("kriterien", {})
    vuregel_id = daten.get("vuregel_id")
    faktor_vorschlag = daten.get("faktor_vorschlag")
    faktor_final     = daten.get("faktor_final")
    begruendung      = daten.get("begruendung", "")
    benutzer_id      = getattr(g, "benutzer_id", None)

    with get_connection() as conn:
        # ── unfallakte aktualisieren ──────────────────────────────────────
        akte_felder = {}
        for f in ["auslandsbezug", "todesfall", "haftung_streitig"]:
            if f in kriterien:
                akte_felder[f] = 1 if kriterien[f] else 0
        if akte_felder:
            set_clause = ", ".join(f"{k} = ?" for k in akte_felder)
            conn.execute(
                f"UPDATE unfallakte SET {set_clause} WHERE az = ?",
                list(akte_felder.values()) + [az]
            )

        # ── personenschaden aktualisieren ─────────────────────────────────
        ps_felder = {}
        if "verletzungsgrad" in kriterien:
            ps_felder["verletzungsgrad"] = kriterien["verletzungsgrad"]
        if "pflegebedarf" in kriterien:
            ps_felder["pflegebedarf"] = 1 if kriterien["pflegebedarf"] else 0

        if ps_felder:
            existing = conn.execute(
                "SELECT id FROM personenschaden WHERE akte_id = ?", (az,)
            ).fetchone()
            if existing:
                set_clause = ", ".join(f"{k} = ?" for k in ps_felder)
                conn.execute(
                    f"UPDATE personenschaden SET {set_clause} WHERE akte_id = ?",
                    list(ps_felder.values()) + [az]
                )
            else:
                # Personenschaden-Zeile anlegen mit Minimal-Daten
                cols = ["akte_id"] + list(ps_felder.keys())
                vals = [az] + list(ps_felder.values())
                placeholders = ", ".join("?" for _ in vals)
                conn.execute(
                    f"INSERT INTO personenschaden ({', '.join(cols)}) VALUES ({placeholders})",
                    vals
                )

        # ── gebuehren_berechnung UPSERT ───────────────────────────────────
        kriterien_json = json.dumps(kriterien, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO gebuehren_berechnung
                (akte_id, vuregel_id, faktor_vorschlag, faktor_final,
                 begruendung, kriterien_json, erfasst_am, erfasst_von)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(akte_id) DO UPDATE SET
                vuregel_id       = excluded.vuregel_id,
                faktor_vorschlag = excluded.faktor_vorschlag,
                faktor_final     = excluded.faktor_final,
                begruendung      = excluded.begruendung,
                kriterien_json   = excluded.kriterien_json,
                erfasst_am       = excluded.erfasst_am,
                erfasst_von      = excluded.erfasst_von
            """,
            (az, vuregel_id, faktor_vorschlag, faktor_final,
             begruendung, kriterien_json,
             datetime.now().isoformat(timespec="seconds"), benutzer_id)
        )

    return _j({"ok": True})


# ── POST /akten/<az>/gebuehren/word ───────────────────────────────────────────

@gebuehren_bp.route("/gebuehren/word", methods=["POST"])
@login_erforderlich
def generiere_word(akte_id):
    """Generiert die Word-Kostennote und speichert sie in dokumente."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.aktenzeichen

    with get_connection() as conn:
        gb_row = conn.execute(
            "SELECT * FROM gebuehren_berechnung WHERE akte_id = ?", (az,)
        ).fetchone()

    if not gb_row:
        return _err("Bitte zuerst die Gebührenberechnung speichern.", 400)

    try:
        from ..word.gebuehren_word import generiere_kostennote
        result = generiere_kostennote(az, dict(gb_row))
        return _j(result)
    except Exception as e:
        logger.exception("Fehler beim Generieren der Kostennote: %s", e)
        return _err(f"Generierung fehlgeschlagen: {e}", 500)
