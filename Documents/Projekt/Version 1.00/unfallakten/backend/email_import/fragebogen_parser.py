"""
PRD-22c – Fragebogen-Parser
============================
Parst den JSON-Anhang eines Website-Unfallbogens zu einem strukturierten Dict.

Erwartet JSON-Schema v2.x (unfallbogen-json-schema.md).
Gibt None zurück wenn der Anhang kein gültiger Unfallbogen ist.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)

# Bekannte Schema-Versionen – bei unbekannter Version warnen, trotzdem importieren
_BEKANNTE_VERSIONEN = {"2.0", "2.1"}


def parse_fragebogen_anhang(json_bytes):
    """
    Parst JSON-Anhang-Bytes zu strukturiertem Dict.

    Prüft meta.formular == "unfallbogen" und meta.version.
    Gibt None zurück wenn kein gültiger Unfallbogen.

    Returns:
        {
            "meta":            dict,
            "hat_aktenzeichen": bool,
            "aktenzeichen":    str|None,   # normiert via _normiere_az_basis()
            "mandant":         dict,
            "gegner":          dict,
            "unfall":          dict,
            "sachschaden":     dict,
            "personenschaden": dict|None,
            "_roh":            dict,       # Original-JSON
        }
        oder None wenn ungültig.
    """
    if not json_bytes:
        return None

    try:
        roh = json.loads(json_bytes.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as e:
        logger.warning("Fragebogen-JSON konnte nicht geparst werden: %s", e)
        return None

    if not isinstance(roh, dict):
        logger.warning("Fragebogen-JSON ist kein Objekt.")
        return None

    # Pflicht-Check: meta.formular
    meta = roh.get("meta", {})
    if not isinstance(meta, dict):
        logger.warning("Fragebogen: meta fehlt oder kein Objekt.")
        return None

    if meta.get("formular") != "unfallbogen":
        logger.debug(
            "Fragebogen ignoriert: meta.formular = %r", meta.get("formular")
        )
        return None

    # Version prüfen (Warnung bei unbekannt, aber trotzdem importieren)
    version = str(meta.get("version", ""))
    if version not in _BEKANNTE_VERSIONEN:
        logger.warning(
            "Fragebogen: unbekannte Schema-Version %r – Import wird trotzdem versucht.",
            version,
        )

    # Aktenzeichen normieren
    az_roh = meta.get("aktenzeichen") or None
    az_norm = _normiere_az_basis(az_roh) if az_roh else None

    return {
        "meta":             meta,
        "hat_aktenzeichen": az_norm is not None,
        "aktenzeichen":     az_norm,
        "mandant":          roh.get("mandant") or {},
        "gegner":           roh.get("gegner") or {},
        "unfall":           roh.get("unfall") or {},
        "sachschaden":      roh.get("sachschaden") or {},
        "personenschaden":  roh.get("personenschaden") or None,
        "_roh":             roh,
    }


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _normiere_az_basis(az):
    """
    Normiert ein Aktenzeichen für den DB-Lookup.
    Entfernt SB-Kürzel: "31/21AS" → "31/21"
    Gibt None zurück bei leerem Input.
    """
    if not az:
        return None
    az = str(az).strip().upper()
    if "/" in az:
        az = re.sub(r"[A-Z]{2,3}$", "", az).strip()
    return az if az else None
