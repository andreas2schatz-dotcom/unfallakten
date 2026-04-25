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


@einstellungen_bp.route("/llm-status", methods=["GET"])
@login_erforderlich
def get_llm_status():
    """
    GET /einstellungen/llm-status
    Gibt zurück ob LLM-Parsing aktiviert, LM Studio erreichbar ist
    und welche Modelle konfiguriert sind.
    """
    import os as _os
    from ..services.llm_service import (
        is_available, get_active_model, get_available_models,
        set_active_model, _BASE_URL,
    )
    env_enabled = _os.environ.get("LLM_ENABLED", "false").strip().lower() == "true"
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO konfiguration (schluessel, wert, beschreibung) VALUES (?, ?, ?)",
            ("llm_parsing_enabled", "false", "LLM-Parsing aktiviert"),
        )
        row_aktiv = conn.execute(
            "SELECT wert FROM konfiguration WHERE schluessel='llm_parsing_enabled'"
        ).fetchone()
        row_modell = conn.execute(
            "SELECT wert FROM konfiguration WHERE schluessel='llm_aktives_modell'"
        ).fetchone()
        db_enabled = (row_aktiv["wert"] == "true") if row_aktiv else False
        # Gespeichertes Modell aus DB in Service übernehmen
        if row_modell and row_modell["wert"]:
            set_active_model(row_modell["wert"])
    verfuegbar = is_available() if env_enabled else False
    return jsonify({
        "env_konfiguriert": env_enabled,
        "aktiviert":        db_enabled,
        "verfuegbar":       verfuegbar,
        "aktives_modell":   get_active_model(),
        "modelle":          get_available_models(),
        "base_url":         _BASE_URL,
    })


@einstellungen_bp.route("/llm-modell", methods=["PUT"])
@login_erforderlich
def put_llm_modell():
    """PUT /einstellungen/llm-modell  Body: { "modell": "qwen3.5-9b" }"""
    from ..services.llm_service import set_active_model, get_available_models
    body   = request.get_json(silent=True) or {}
    modell = (body.get("modell") or "").strip()
    if not modell:
        return jsonify({"fehler": "Kein Modell angegeben."}), 400
    if modell not in get_available_models():
        return jsonify({"fehler": f"Unbekanntes Modell: {modell}. In LLM_MODELS eintragen."}), 400
    set_active_model(modell)
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO konfiguration (schluessel, wert, geaendert_am)
               VALUES ('llm_aktives_modell', ?, datetime('now','localtime'))
               ON CONFLICT(schluessel) DO UPDATE SET
                   wert=excluded.wert, geaendert_am=excluded.geaendert_am""",
            (modell,)
        )
    return jsonify({"ok": True, "aktives_modell": modell})


@einstellungen_bp.route("/llm-aktivieren", methods=["PUT"])
@login_erforderlich
def put_llm_aktivieren():
    """PUT /einstellungen/llm-aktivieren  Body: { "aktiviert": true|false }"""
    body = request.get_json(silent=True) or {}
    wert = "true" if body.get("aktiviert") else "false"
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO konfiguration (schluessel, wert, geaendert_am)
               VALUES ('llm_parsing_enabled', ?, datetime('now','localtime'))
               ON CONFLICT(schluessel) DO UPDATE SET
                   wert=excluded.wert, geaendert_am=excluded.geaendert_am""",
            (wert,)
        )
    return jsonify({"ok": True, "aktiviert": wert == "true"})


@einstellungen_bp.route("/llm-test", methods=["POST"])
@login_erforderlich
def post_llm_test():
    """
    POST /einstellungen/llm-test
    Body: { "prompt": "..." }   (optional, Default: einfacher Ping)
    Schickt einen Testprompt an Gemma und gibt die Antwort zurück.
    """
    import os as _os
    body   = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "Antworte mit genau einem Satz: Verbindung zu Gemma erfolgreich.").strip()

    if not _os.environ.get("LLM_ENABLED", "false").strip().lower() == "true":
        return jsonify({"fehler": "LLM_ENABLED ist in .env nicht auf true gesetzt."}), 503

    from ..services.llm_service import chat as llm_chat, get_active_model
    antwort = llm_chat(prompt)
    if antwort is None:
        return jsonify({"fehler": "Keine Antwort von LM Studio – läuft der Server?"}), 503
    return jsonify({"antwort": antwort, "modell": get_active_model()})


@einstellungen_bp.route("/lg-grenzwert", methods=["GET"])
@login_erforderlich
def get_lg_grenzwert():
    """GET /einstellungen/lg-grenzwert – LG-Zuständigkeitsschwelle."""
    with get_connection() as conn:
        row = conn.execute("SELECT wert FROM konfiguration WHERE schluessel='lg_grenzwert'").fetchone()
        wert = int(row["wert"]) if row else 10000
    return jsonify({"lg_grenzwert": wert})


@einstellungen_bp.route("/lg-grenzwert", methods=["PUT"])
@login_erforderlich
def put_lg_grenzwert():
    """PUT /einstellungen/lg-grenzwert – LG-Zuständigkeitsschwelle aktualisieren."""
    body = request.get_json(silent=True) or {}
    try:
        wert = int(body.get("lg_grenzwert", 10000))
        if not (1 <= wert <= 10_000_000):
            return jsonify({"fehler": "Wert muss zwischen 1 und 10.000.000 liegen."}), 400
    except (ValueError, TypeError):
        return jsonify({"fehler": "Kein gültiger ganzzahliger Wert."}), 400
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO konfiguration (schluessel, wert, geaendert_am)
               VALUES ('lg_grenzwert', ?, datetime('now','localtime'))
               ON CONFLICT(schluessel) DO UPDATE SET
                   wert=excluded.wert, geaendert_am=excluded.geaendert_am""",
            (str(wert),)
        )
    return jsonify({"ok": True, "lg_grenzwert": wert})
