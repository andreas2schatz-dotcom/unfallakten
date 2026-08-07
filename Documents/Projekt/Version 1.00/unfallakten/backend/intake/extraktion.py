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


def _erkenne_referenzwerkstatt(text: str):
    """Fallback fuer Pruefberichte, deren Werkstatt-Block ausserhalb des
    N-06-LLM-Seitenfensters liegt (Befund 1280/25: VHV-Blockformat auf
    Seite 4/5). Deterministisch statt LLM-Fenster-Erweiterung
    (Entscheidung RA Schatz 2026-08-07)."""
    from ..services.werkstatt_service import extrahiere_verweisbetrieb
    treffer = extrahiere_verweisbetrieb(text)
    if not treffer.get("gefunden"):
        return None
    return {
        "name":       treffer.get("name", ""),
        "adresse":    treffer.get("adresse", ""),
        "plz_ort":    treffer.get("plz_ort", ""),
        "telefon":    treffer.get("telefon", ""),
        "km_genannt": treffer.get("km_genannt"),
        "quelle":     treffer.get("quelle", ""),
    }


_BETRAG_TOLERANZ = 0.011  # 1 Cent + Float-Spielraum (wie intake/validierung.py)


def _positions_betrag(eintrag):
    if not isinstance(eintrag, dict):
        return None
    for schluessel in ("betrag", "betrag_brutto", "betrag_netto"):
        wert = eintrag.get(schluessel)
        if isinstance(wert, (int, float)) and not isinstance(wert, bool):
            return float(wert)
    return None


def _ergaenze_abrechnungspositionen(text: str, felder: Dict[str, Any]) -> None:
    """Sicherungsnetz fuer Abrechnungsschreiben (Befund 1280/25): Die
    LLM-Extraktion laesst einzelne Abrechnungszeilen aus (VHV liest
    "Abrechnung nach Prüfbericht 5.448,62 EUR" als abrechnungsart). Der
    Regex-Parser liefert deterministische Kandidaten; ergaenzt wird nur, was
    die Differenz zum Gesamtbetrag exakt erklaert -- lieber die bestehende
    Validierungswarnung stehen lassen als eine geratene Position anhaengen."""
    from ..parsers.abrechnungsschreiben_parser import parse_abrechnungsschreiben

    kuerzel = felder.get("versicherer_kuerzel") or ""
    ergebnis = parse_abrechnungsschreiben(text, str(kuerzel))
    kandidaten = []
    for p in ergebnis.positionen:
        # Abzuege und Gegenwerte sind keine Auszahlungspositionen
        if p.art in ("mwst_abzug", "pruefbericht_abzug", "restwert"):
            continue
        wert = p.betrag_netto if p.betrag_netto is not None else p.betrag_brutto
        if not wert or wert <= 0:
            continue
        kandidaten.append({"bezeichnung": p.bezeichnung, "betrag": round(wert, 2)})

    vorhandene = felder.get("positionen")
    if not isinstance(vorhandene, list) or not vorhandene:
        if kandidaten:
            felder["positionen"] = kandidaten
        return

    bekannte = [b for b in (_positions_betrag(p) for p in vorhandene)
                if b is not None]
    fehlende = [
        k for k in kandidaten
        if not any(abs(k["betrag"] - b) <= _BETRAG_TOLERANZ for b in bekannte)
    ]
    if not fehlende:
        return

    gesamt = felder.get("gesamtbetrag")
    if isinstance(gesamt, bool) or not isinstance(gesamt, (int, float)):
        return
    differenz = round(float(gesamt) - sum(bekannte), 2)
    if abs(differenz) <= _BETRAG_TOLERANZ:
        return

    for k in fehlende:
        if abs(k["betrag"] - differenz) <= _BETRAG_TOLERANZ:
            felder["positionen"] = vorhandene + [k]
            return
    if abs(sum(k["betrag"] for k in fehlende) - differenz) <= _BETRAG_TOLERANZ:
        felder["positionen"] = vorhandene + fehlende


_DATUM_DE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
_DATUM_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _datum_iso(wert: str):
    """DD.MM.YYYY / YYYY-MM-DD -> 'YYYY-MM-DD'; None wenn kein Datum."""
    m = _DATUM_DE.match(wert)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if _DATUM_ISO.match(wert):
        return wert
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

    if klasse == "pruefbericht" and not felder.get("referenzwerkstatt"):
        werkstatt = _erkenne_referenzwerkstatt(text)
        if werkstatt:
            felder["referenzwerkstatt"] = werkstatt

    # LLM liefert referenzwerkstatt ungeprueft mit beliebigen Keys (z.B.
    # "entfernung" statt "km_genannt") -- auf kanonische Keys angleichen,
    # damit Folgeverbraucher (Entfernungspruefung) nicht ins Leere greifen.
    if klasse == "pruefbericht" and isinstance(felder.get("referenzwerkstatt"), dict):
        werkstatt = felder["referenzwerkstatt"]
        for feld in ("name", "adresse", "plz_ort", "telefon"):
            werkstatt.setdefault(feld, "")
        werkstatt.setdefault("km_genannt", None)
        werkstatt.setdefault("quelle", "llm")

    if klasse == "abrechnungsschreiben":
        _ergaenze_abrechnungspositionen(text, felder)

    ergebnis: Dict[str, Any] = {"felder": felder, "llm_status": llm_status}

    konflikte: Dict[str, Dict[str, Any]] = {}
    for feld, regex_wert in regex_werte.items():
        llm_wert = llm_werte.get(feld)
        if llm_wert is None:
            continue
        llm_s = str(llm_wert).strip()
        regex_s = str(regex_wert).strip()
        iso_llm, iso_regex = _datum_iso(llm_s), _datum_iso(regex_s)
        if iso_llm and iso_regex and iso_llm == iso_regex:
            continue
        if llm_s != regex_s:
            konflikte[feld] = {"llm": llm_wert, "regex": regex_wert}
    if konflikte:
        ergebnis["llm_konflikt"] = konflikte

    return ergebnis
