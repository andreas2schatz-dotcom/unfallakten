"""
Einstellungen-Routen
====================
GET  /einstellungen/sta-fristen   → Fristenzeiten + Texttemplates
PUT  /einstellungen/sta-fristen   → Fristen + Texte aktualisieren
GET  /einstellungen/ki            → KI-Modell + Prompts
PUT  /einstellungen/ki            → KI-Modell + Prompts aktualisieren
"""

import logging
from flask import Blueprint, jsonify, request
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..services.sta_service import _TEXT_DEFAULTS, _FRIST_DEFAULTS

logger = logging.getLogger(__name__)

einstellungen_bp = Blueprint("einstellungen", __name__, url_prefix="/einstellungen")

_TAGE_SCHLUESSEL = {
    "stufe1_tage": "sta_stufe1_tage",
    "stufe2_tage": "sta_stufe2_tage",
    "stufe3_tage": "sta_stufe3_tage",
}
_TEXT_SCHLUESSEL = {
    "stufe1_text": "sta_stufe1_text",
    "stufe2_text": "sta_stufe2_text",
    "stufe3_text": "sta_stufe3_text",
}


def _lese_int(conn, schluessel):
    row = conn.execute(
        "SELECT wert FROM konfiguration WHERE schluessel = ?", (schluessel,)
    ).fetchone()
    if row:
        try:
            return int(row["wert"])
        except (ValueError, TypeError):
            pass
    return _FRIST_DEFAULTS.get(schluessel)


def _lese_text(conn, schluessel):
    row = conn.execute(
        "SELECT wert FROM konfiguration WHERE schluessel = ?", (schluessel,)
    ).fetchone()
    if row and row["wert"].strip():
        return row["wert"]
    return _TEXT_DEFAULTS.get(schluessel, "")


KI_MODELLE  = ["claude-sonnet-4-6", "gemini-3.1-pro-preview"]
KI_DEFAULTS = {
    "ki_modell":        "claude-sonnet-4-6",
    "ki_system_prompt": (
        "Du bist ein erfahrener Rechtsanwalt für Verkehrsrecht in Deutschland mit "
        "Spezialisierung auf grenzüberschreitende Unfälle.\n\n"
        "Prüfungsreihenfolge:\n"
        "1. Unfallort: Inland oder Ausland?\n"
        "   - Ausland: Anwendbares Recht nach Rom II-VO (Art. 4) bestimmen.\n"
        "     Grundregel: Recht des Unfallortes. Ausnahme: gemeinsamer gewöhnlicher "
        "Aufenthalt (Art. 4 Abs. 2 Rom II-VO).\n"
        "     Leite das Haftungsregime aus dem Landesrecht ab.\n"
        "     Verweise auf EuGH 13.12.2007 – C-463/06 (Tatortprinzip) und "
        "BGH VI ZR 200/05 (Anerkennungsgrundsatz) wo relevant.\n"
        "   - Inland: StVG, StVO, BGB anwenden.\n"
        "2. Verschuldensform: Welche Sorgfaltspflicht wurde verletzt?\n"
        "3. Kausalität: Wie hat die Handlung den Schaden verursacht?\n"
        "4. Haftungsquote: Ist die übergebene Quote plausibel begründbar?\n\n"
        "Stil: Juristisch, sachlich, klageschrifttauglich.\n"
        "Länge: Kurz, prägnant, auf das Wesentliche reduziert.\n"
        "Kein Titel, keine Einleitung, kein Schlusssatz. Nur der reine Haftungstext."
    ),
    "ki_user_prompt": (
        "{haftung_ctx}\n\n"
        "Unfallschilderung (anonymisiert – Mandant wird als Kläger bezeichnet):\n"
        "{schilderung}\n\n"
        "Erstelle den Abschnitt »Rechtliche Würdigung« für eine Klageschrift. "
        "Begründe konkret und fallbezogen, warum der Unfallgegner haftet. "
        "Beziehe dich auf die Schilderung. Juristischer, sachlicher Stil."
    ),
}


def _lese_wert(conn, schluessel, default=""):
    row = conn.execute(
        "SELECT wert FROM konfiguration WHERE schluessel = ?", (schluessel,)
    ).fetchone()
    return row["wert"] if (row and row["wert"].strip()) else default


def _upsert(conn, schluessel, wert):
    conn.execute(
        """
        INSERT INTO konfiguration (schluessel, wert, geaendert_am)
        VALUES (?, ?, datetime('now','localtime'))
        ON CONFLICT(schluessel) DO UPDATE SET
            wert         = excluded.wert,
            geaendert_am = excluded.geaendert_am
        """,
        (schluessel, wert),
    )


def _alle_werte(conn):
    return {
        "stufe1_tage": _lese_int(conn,  "sta_stufe1_tage"),
        "stufe2_tage": _lese_int(conn,  "sta_stufe2_tage"),
        "stufe3_tage": _lese_int(conn,  "sta_stufe3_tage"),
        "stufe1_text": _lese_text(conn, "sta_stufe1_text"),
        "stufe2_text": _lese_text(conn, "sta_stufe2_text"),
        "stufe3_text": _lese_text(conn, "sta_stufe3_text"),
    }


@einstellungen_bp.route("/klassifikation-training", methods=["GET"])
@login_erforderlich
def get_klassifikation_training():
    """Gibt Statistiken über gesammelte Klassifikations-Trainingsdaten zurück."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS gesamt FROM klassifikation_training"
        ).fetchone()
        gesamt = row["gesamt"] if row else 0

        klassen = conn.execute(
            "SELECT klasse_korrigiert AS klasse, COUNT(*) AS n "
            "FROM klassifikation_training "
            "GROUP BY klasse_korrigiert ORDER BY n DESC"
        ).fetchall()

    return jsonify({
        "gesamt":        gesamt,
        "ziel":          50,
        "bereit":        gesamt >= 50,
        "klassen":       [{"klasse": r["klasse"], "n": r["n"]} for r in klassen],
    })


@einstellungen_bp.route("/sta-fristen", methods=["GET"])
@login_erforderlich
def get_sta_fristen():
    """Gibt Fristen und Texttemplates für alle drei STA-Stufen zurück."""
    with get_connection() as conn:
        return jsonify(_alle_werte(conn))


@einstellungen_bp.route("/sta-fristen", methods=["PUT"])
@login_erforderlich
def put_sta_fristen():
    """Aktualisiert Fristen und/oder Texttemplates."""
    body   = request.get_json(silent=True) or {}
    fehler = []

    with get_connection() as conn:
        # Fristtage
        for feld, schluessel in _TAGE_SCHLUESSEL.items():
            if feld not in body:
                continue
            try:
                wert = int(body[feld])
                if not (1 <= wert <= 365):
                    fehler.append("{}: Wert muss zwischen 1 und 365 liegen.".format(feld))
                    continue
                _upsert(conn, schluessel, str(wert))
            except (ValueError, TypeError):
                fehler.append("{}: Kein gültiger ganzzahliger Wert.".format(feld))

        # Texttemplates
        for feld, schluessel in _TEXT_SCHLUESSEL.items():
            if feld not in body:
                continue
            text = str(body[feld]).strip()
            if len(text) > 4000:
                fehler.append("{}: Text zu lang (max. 4000 Zeichen).".format(feld))
                continue
            _upsert(conn, schluessel, text)

        if fehler:
            return jsonify({"fehler": "; ".join(fehler)}), 400

        return jsonify({"ok": True, **_alle_werte(conn)})


def _ki_werte(conn):
    return {
        "modell":        _lese_wert(conn, "ki_modell",        KI_DEFAULTS["ki_modell"]),
        "system_prompt": _lese_wert(conn, "ki_system_prompt", KI_DEFAULTS["ki_system_prompt"]),
        "user_prompt":   _lese_wert(conn, "ki_user_prompt",   KI_DEFAULTS["ki_user_prompt"]),
        "modelle":       KI_MODELLE,
    }


@einstellungen_bp.route("/ki", methods=["GET"])
@login_erforderlich
def get_ki_einstellungen():
    """GET /einstellungen/ki – Gibt KI-Modell und Prompts zurück."""
    with get_connection() as conn:
        return jsonify(_ki_werte(conn))


@einstellungen_bp.route("/ki", methods=["PUT"])
@login_erforderlich
def put_ki_einstellungen():
    """PUT /einstellungen/ki – Aktualisiert KI-Modell und/oder Prompts."""
    body = request.get_json(silent=True) or {}
    with get_connection() as conn:
        if "modell" in body:
            modell = str(body["modell"]).strip()
            if modell not in KI_MODELLE:
                return jsonify({"fehler": f"Unbekanntes Modell: {modell}"}), 400
            _upsert(conn, "ki_modell", modell)
        if "system_prompt" in body:
            _upsert(conn, "ki_system_prompt", str(body["system_prompt"]).strip())
        if "user_prompt" in body:
            _upsert(conn, "ki_user_prompt", str(body["user_prompt"]).strip())
        return jsonify({"ok": True, **_ki_werte(conn)})
