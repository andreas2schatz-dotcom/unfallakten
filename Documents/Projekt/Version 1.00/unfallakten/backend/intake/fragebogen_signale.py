"""Ableitung von Such-Signalen aus einem Website-Unfallbogen.

Reine Lesefunktionen ohne Datenbankzugriff. Der Bogen ist ein schema-
validierter JSON-Datensatz -- seine Felder werden direkt verwendet, statt
Kennzeichen und Datum per Regex aus dem Volltext zu raten.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 1-3 Unterscheidungsbuchstaben, 1-2 Erkennungsbuchstaben, 1-4 Ziffern --
# nach dem Entfernen aller Trennzeichen. Faengt Freitext wie "siehe Akte"
# oder "k.A. Fussgaenger" ab.
_KFZ_GUELTIG = re.compile(r"^[A-ZÄÖÜ]{1,3}[A-Z]{1,2}\d{1,4}$")
_KFZ_MUELL = re.compile(r"[^A-ZÄÖÜ0-9]")


def erkenne_fragebogen(payload_typ: Optional[str],
                       text_gesamt: Optional[str]) -> Optional[Dict[str, Any]]:
    """Gibt den geparsten Bogen zurueck, sonst None.

    Ein Fragebogen ist ein Text-Payload, dessen JSON gegen
    ``meta.formular == "unfallbogen"`` und das Bogen-Schema validiert.
    """
    if payload_typ != "text" or not text_gesamt or not text_gesamt.strip():
        return None
    from ..email_import.fragebogen_parser import parse_fragebogen_anhang
    try:
        return parse_fragebogen_anhang(text_gesamt.encode("utf-8"))
    except Exception as exc:
        logger.warning("Fragebogen-Payload nicht lesbar: %s", exc)
        return None


def normiere_kennzeichen(roh: Optional[str]) -> Optional[str]:
    """Freie Eingabe -> Suchschluessel, oder None wenn unbrauchbar."""
    if not roh:
        return None
    norm = _KFZ_MUELL.sub("", str(roh).upper())
    return norm if _KFZ_GUELTIG.match(norm) else None


def baue_signale(bogen: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Suchmerkmale fuer Klassifikator und Akten-Matching."""
    if not bogen:
        return {}
    mandant = bogen.get("mandant") or {}
    gegner = bogen.get("gegner") or {}
    unfall = bogen.get("unfall") or {}
    eigenes = (bogen.get("sachschaden") or {}).get("eigenes_fahrzeug") or {}
    gegner_kfz = gegner.get("fahrzeug") or {}

    signal: Dict[str, Any] = {"dokument_art": "fragebogen"}

    if bogen.get("aktenzeichen"):
        signal["az"] = bogen["aktenzeichen"]

    mail = (mandant.get("email") or "").strip().lower()
    if mail:
        signal["mandant_email"] = mail

    kfz_m = normiere_kennzeichen(eigenes.get("kennzeichen"))
    if kfz_m:
        signal["kfz_mandant"] = kfz_m

    kfz_g = normiere_kennzeichen(gegner_kfz.get("kennzeichen"))
    if kfz_g:
        signal["kfz_gegner"] = kfz_g

    nachname = (mandant.get("name") or "").strip()
    if nachname:
        signal["nachname"] = nachname

    tag = (unfall.get("datum") or "").strip()
    if tag:
        signal["unfalltag"] = tag

    return signal


def baue_kopf(bogen: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Anzeigewerte fuer die Zeile in der Review-Queue.

    Zeigt das Kennzeichen bewusst so, wie der Mandant es eingetippt hat --
    auch wenn es als Suchschluessel unbrauchbar ist.
    """
    if not bogen:
        return {"mandant_name": None, "kennzeichen": None, "unfalltag": None}
    mandant = bogen.get("mandant") or {}
    eigenes = (bogen.get("sachschaden") or {}).get("eigenes_fahrzeug") or {}
    teile = [(mandant.get("vorname") or "").strip(),
             (mandant.get("name") or "").strip()]
    return {
        "mandant_name": " ".join(t for t in teile if t) or None,
        "kennzeichen": (eigenes.get("kennzeichen") or "").strip() or None,
        "unfalltag": ((bogen.get("unfall") or {}).get("datum") or "").strip()
                      or None,
    }
