"""
Abrechnungs-Vorschlaege aus freigegebenen Abrechnungsschreiben.

Die Review-Freigabe legt fuer ein Abrechnungsschreiben nur das Ereignis
``abrechnung_eingegangen`` ohne Positionen an (siehe
``eingehende_ereignisse.erzeuge_aus_freigabe``) -- die geparsten Betraege
stehen als Freitext-Zeilen im ``parse_json`` und kaemen sonst nirgends an.

Dieses Modul uebersetzt diese Zeilen ueber ``positions_synonyme.yaml`` auf
position_keys und bietet sie als Vorschlag an. Gebucht wird erst, wenn der
Sachbearbeiter den Vorschlag in der Regulierung bestaetigt -- OCR-Fehler in
Betraegen sollen nicht ungeprueft in die Akte laufen.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from ..db.database import get_connection
from .kuerzungstyp_matching import normalisiere_positionslabel

logger = logging.getLogger(__name__)

# Reihenfolge = Vorrang. Der Intake-LLM benennt das Freitext-Label je nach
# Dokument unterschiedlich, der Regex-Parser liefert stattdessen 'art'.
_LABEL_FELDER = ("text", "beschreibung", "label", "bezeichnung", "position")
_BETRAG_FELDER = ("betrag", "betrag_brutto", "betrag_netto", "wert")


def _zu_zahl(wert: Any) -> Optional[float]:
    if wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    from ..parsers.pdf_utils import parse_betrag
    return parse_betrag(str(wert).strip())


def _felder_aus_parse(parse_json: Optional[str]) -> Dict[str, Any]:
    if not parse_json:
        return {}
    try:
        daten = json.loads(parse_json)
    except (ValueError, TypeError):
        return {}
    if not isinstance(daten, dict):
        return {}
    felder = daten.get("felder")
    ergebnis = dict(felder) if isinstance(felder, dict) else dict(daten)
    warnungen = daten.get("validierung_warnungen")
    if isinstance(warnungen, list):
        ergebnis["_warnungen"] = [str(w) for w in warnungen]
    return ergebnis


def _position_key(eintrag: Dict[str, Any], bekannte: set) -> Optional[str]:
    art = (eintrag.get("art") or "").strip()
    if art and art in bekannte:
        return art
    for feld in _LABEL_FELDER:
        label = eintrag.get(feld)
        if isinstance(label, str) and label.strip():
            return normalisiere_positionslabel(label)
    return None


def _roh_label(eintrag: Dict[str, Any]) -> str:
    for feld in _LABEL_FELDER:
        label = eintrag.get(feld)
        if isinstance(label, str) and label.strip():
            return label.strip()
    return (eintrag.get("art") or "").strip()


def _positionen(felder: Dict[str, Any], bekannte: set) -> List[Dict[str, Any]]:
    roh = felder.get("positionen")
    if not isinstance(roh, list):
        return []
    ergebnis = []
    for eintrag in roh:
        if not isinstance(eintrag, dict):
            continue
        betrag = None
        for feld in _BETRAG_FELDER:
            betrag = _zu_zahl(eintrag.get(feld))
            if betrag is not None:
                break
        label = _roh_label(eintrag)
        if betrag is None and not label:
            continue
        ergebnis.append({
            "position_key":     _position_key(eintrag, bekannte),
            "roh_label":        label,
            "betrag_reguliert": round(betrag, 2) if betrag is not None else 0.0,
        })
    return ergebnis


def baue_vorschlaege(akte_az: str) -> List[Dict[str, Any]]:
    """Liefert je noch nicht erfasstem Abrechnungsschreiben einen Vorschlag.

    Ausgelassen werden Dokumente, zu denen bereits ein
    ``abrechnungsschreiben``-Eintrag existiert, sowie solche ohne
    verwertbare Positionszeilen.
    """
    from .positionsmodell_registry import lade_positionsmodell
    try:
        bekannte = set(lade_positionsmodell().positionsarten.keys())
    except Exception as exc:  # pragma: no cover -- Registry faellt laut aus
        logger.warning("Positionsmodell nicht ladbar: %s", exc)
        bekannte = set()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT d.id, d.bezeichnung, d.dateiname, d.parse_json, "
            "       i.parse_json AS intake_parse_json "
            "FROM dokumente d "
            "LEFT JOIN freigaben f "
            "       ON f.dokument_id = d.id AND f.akte_az = d.akte_id "
            "LEFT JOIN intake_dokumente i ON i.id = f.intake_dokument_id "
            "WHERE d.akte_id = ? "
            "  AND (d.typ = 'abrechnungsschreiben' "
            "       OR d.dokumentenklasse = 'abrechnungsschreiben') "
            "  AND d.id NOT IN ("
            "       SELECT dokument_id FROM abrechnungsschreiben "
            "       WHERE akte_id = ? AND dokument_id IS NOT NULL) "
            "ORDER BY d.id ASC",
            (akte_az, akte_az),
        ).fetchall()

    vorschlaege = []
    for r in rows:
        felder = (_felder_aus_parse(r["parse_json"])
                  or _felder_aus_parse(r["intake_parse_json"]))
        positionen = _positionen(felder, bekannte)
        if not positionen:
            continue
        vorschlaege.append({
            "dokument_id":  r["id"],
            "bezeichnung":  r["bezeichnung"] or r["dateiname"],
            "datum":        felder.get("schreibdatum") or None,
            "versicherung": felder.get("versicherer") or None,
            "referenz_nr":  felder.get("schadennummer") or None,
            "abrechnungsart": felder.get("abrechnungsart") or None,
            "gesamtbetrag": _zu_zahl(felder.get("gesamtbetrag")),
            "positionen":   positionen,
            "warnungen":    felder.get("_warnungen") or [],
        })
    return vorschlaege
