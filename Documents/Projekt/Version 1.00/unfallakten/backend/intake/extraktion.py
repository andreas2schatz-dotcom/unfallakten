"""
Feldextraktion nach Klassenschema (S1.6b).

extrahiere_felder(text, klasse, registry) laeuft zweispurig:
  1. Regex-Felder aus dem YAML-Eintrag der Klasse liefern Anker-Werte.
  2. llm_service.extrahiere_nach_schema liefert die Primaerwerte anhand des
     YAML-``schema``. Faellt der LLM-Call aus (LLM_ENABLED=false, Timeout,
     ungueltige Antwort), gelten die Regex-Werte.

Der LLM-Wert ueberschreibt den Regex-Wert; bei Divergenz wird das Feld unter
``llm_konflikt`` festgehalten (llm-Wert + regex-Wert). Damit bleibt der
Regex ein sichtbarer Konsistenz-Anker.

Nur der Neu-Pfad ruft diese Funktion auf. Der Alt-Pfad (llm_service.py
Shadow-Mode -- parse_abrechnung_raw etc.) bleibt unangetastet.
"""
from __future__ import annotations

import re
from typing import Any, Dict

from ..services import llm_service


def _regex_extraktion(text: str,
                      regex_felder: Dict[str, list]) -> Dict[str, Any]:
    """Wendet die YAML-regex_felder-Muster in Reihenfolge an.

    Erster Treffer je Feld gewinnt. Kein Match -> Feld faellt weg.
    Dieselbe Logik wie in test_registry_golden.py (bewusst dupliziert
    gehalten, weil der Golden-Test explizit nur die Registry prueft).
    """
    ergebnis: Dict[str, Any] = {}
    for feld, muster_liste in (regex_felder or {}).items():
        for muster in muster_liste or ():
            treffer = re.search(muster, text)
            if not treffer:
                continue
            wert = treffer.group(1) if treffer.groups() else treffer.group(0)
            ergebnis[feld] = wert
            break
    return ergebnis


def _erkenne_pruefdienstleister(text: str):
    """Fallback fuer Pruefberichte ohne LLM-Wert (Befund 1280/25: der
    Versicherer prueft selbst, ohne ControlExpert/DEKRA im Text).

    Nur der Dokumentkopf zaehlt -- spaetere Erwaehnungen wie
    "Dekra-Zertifizierung" in Werkstatt-Qualitaetsmerkmalen sind kein
    Beleg fuer den Absender."""
    kopf = text[:1500].lower()
    if re.search(r"control.?e?xpert", kopf):
        return "ControlExpert"
    if "dekra" in kopf:
        return "DEKRA"
    from ..parsers.document_classifier import VERSICHERER_PATTERNS
    for muster, _kuerzel, vollname, _prio in VERSICHERER_PATTERNS:
        if re.search(muster, kopf):
            return vollname
    return None


def extrahiere_felder(text: str, klasse: str, registry,
                      llm_text: str = None) -> Dict[str, Any]:
    """Extrahiere Felder gemaess YAML-Registry-Eintrag der ``klasse``.

    Args:
        text:     Volltext des Dokuments (Basis fuer die Regex-Anker).
        llm_text: N-06 -- Seitenauszug (Seite 1 + letzte + Regex-/Tabellen-
                  Seiten) fuer die LLM-Extraktion. Ohne Angabe nutzt der LLM
                  den Volltext (Alt-Verhalten).

    Returns:
        ``{"felder": {...}, "llm_status": "ok"|"aus"|"ausgefallen"}`` oder bei
        Divergenz zusaetzlich
        ``{"felder": {...}, "llm_status": ..., "llm_konflikt": {feld: {"llm": ..., "regex": ...}}}``.

        ``felder`` ist LLM-primaer, faellt aber auf Regex zurueck.
        ``llm_status``: "aus" ohne Schema oder bei deaktiviertem LLM,
        "ausgefallen" bei aktiviertem LLM ohne Werte, sonst "ok".
    """
    eintrag = registry.klassen.get(klasse) if getattr(registry, "klassen", None) else None
    if not eintrag:
        return {"felder": {}, "llm_status": "aus"}

    regex_werte = _regex_extraktion(text, eintrag.get("regex_felder") or {})

    schema = eintrag.get("schema") or {}
    llm_aktiv = llm_service.ist_aktiviert()
    llm_roh = llm_service.extrahiere_nach_schema(
        schema, llm_text if llm_text is not None else text)
    llm_werte = llm_roh if isinstance(llm_roh, dict) else {}

    if not schema or not llm_aktiv:
        llm_status = "aus"
    elif not llm_werte:
        llm_status = "ausgefallen"
    else:
        llm_status = "ok"

    # LLM ist Primaerquelle, Regex-Werte fuellen fehlende Schluessel.
    felder: Dict[str, Any] = {}
    for schema_feld in schema.keys():
        if schema_feld in llm_werte and llm_werte[schema_feld] is not None:
            felder[schema_feld] = llm_werte[schema_feld]
        elif schema_feld in regex_werte:
            felder[schema_feld] = regex_werte[schema_feld]

    # Regex-Felder ausserhalb des Schemas trotzdem erhalten (Anker)
    for feld, wert in regex_werte.items():
        felder.setdefault(feld, wert)

    if klasse == "pruefbericht" and not felder.get("pruefdienstleister"):
        dienstleister = _erkenne_pruefdienstleister(text)
        if dienstleister:
            felder["pruefdienstleister"] = dienstleister

    ergebnis: Dict[str, Any] = {"felder": felder, "llm_status": llm_status}

    konflikte: Dict[str, Dict[str, Any]] = {}
    for feld, regex_wert in regex_werte.items():
        llm_wert = llm_werte.get(feld)
        if llm_wert is None:
            continue
        if str(llm_wert).strip() != str(regex_wert).strip():
            konflikte[feld] = {"llm": llm_wert, "regex": regex_wert}
    if konflikte:
        ergebnis["llm_konflikt"] = konflikte

    return ergebnis
