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


def extrahiere_felder(text: str, klasse: str, registry) -> Dict[str, Any]:
    """Extrahiere Felder gemaess YAML-Registry-Eintrag der ``klasse``.

    Returns:
        ``{"felder": {...}}`` oder bei Divergenz zusaetzlich
        ``{"felder": {...}, "llm_konflikt": {feld: {"llm": ..., "regex": ...}}}``.

        ``felder`` ist LLM-primaer, faellt aber auf Regex zurueck.
    """
    eintrag = registry.klassen.get(klasse) if getattr(registry, "klassen", None) else None
    if not eintrag:
        return {"felder": {}}

    regex_werte = _regex_extraktion(text, eintrag.get("regex_felder") or {})

    schema = eintrag.get("schema") or {}
    llm_werte = llm_service.extrahiere_nach_schema(schema, text) or {}
    if not isinstance(llm_werte, dict):
        llm_werte = {}

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

    ergebnis: Dict[str, Any] = {"felder": felder}

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
