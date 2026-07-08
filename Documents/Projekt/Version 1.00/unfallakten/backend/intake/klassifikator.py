"""
Klassifikator-Kaskade (S1.6b).

Stufe 1 -- Regeln ueber die VEREINIGUNG aller Signale (YAML-Marker im Text +
Zustellungs-Signale wie ``klasse_kandidat`` aus der Absender-Registry).
Vererbte Signale (Absender/Kategorie) erzeugen Kandidaten, sind aber nie
allein "eindeutig" (Konfidenz max. ``SIGNAL_KONFIDENZ``, siehe K-P3).

Stufe 2 -- Qwen (llm_service) mit geschlossener Labelliste. Kuerzung Seite 1
und letzte Seite auf ``F11_MAX_ZEICHEN`` (~3000, F-11 im Freigabe-Dokument).
Faellt das LLM aus (LLM_ENABLED=false, Timeout, ungueltige Antwort), greift
der beste Kandidat aus Stufe 1; ist auch der leer, ``sonstiges`` mit
Konfidenz 0.5.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from ..services import llm_service

F11_MAX_ZEICHEN = 3000

MARKER_BASIS_KONFIDENZ = 0.75
MARKER_BONUS_PRO_TREFFER = 0.05
MARKER_MAX_KONFIDENZ = 0.95

SIGNAL_KONFIDENZ = 0.55
SIGNAL_PLUS_MARKER_BONUS = 0.05

SONSTIGES_FALLBACK_KONFIDENZ = 0.5


@dataclass
class Kandidat:
    klasse: str
    konfidenz: float
    quelle: str  # 'marker' | 'signal' | 'marker+signal'


def _extrahiere_klasse_kandidaten(signale: Iterable[dict]) -> List[str]:
    """Sammelt die eindeutigen ``klasse_kandidat``-Werte aus allen Signalen.

    Freigabe K-P3: Signale werden VEREINIGT (nicht dedupliziert-nach-Wert
    verworfen). Ein Signal ohne ``klasse_kandidat`` liefert nichts.
    """
    ergebnis: List[str] = []
    for signal in signale or ():
        if not isinstance(signal, dict):
            continue
        klasse = signal.get("klasse_kandidat")
        if klasse and klasse not in ergebnis:
            ergebnis.append(str(klasse))
    return ergebnis


def klassifiziere_stufe1(text: str,
                         signale: Iterable[dict],
                         registry) -> Tuple[List[Kandidat], List[str]]:
    """Regel-basierte Klassifikation (Stufe 1).

    Args:
        text:     Volltext des Dokuments.
        signale:  Iterable von Zustellungs-Signal-Dicts (aus
                  ``zustellungen.signale_json``). Leer ist zulaessig.
        registry: Loader-Registry mit ``.klassen`` (Mapping klasse -> yaml).

    Returns:
        (kandidaten, hinweise). ``kandidaten`` ist eine absteigend nach
        Konfidenz sortierte Liste; ``hinweise`` sind lesbare Debug-Zeilen
        fuer parse_json (welcher Marker/welches Signal geloest hat).
    """
    text_norm = (text or "").lower()
    signal_klassen = _extrahiere_klasse_kandidaten(signale)

    treffer: dict = {}
    hinweise: List[str] = []

    for klasse_name, eintrag in registry.klassen.items():
        marker_liste = eintrag.get("marker") or []
        anzahl = 0
        gefundene = []
        for m in marker_liste:
            if m and m.lower() in text_norm:
                anzahl += 1
                gefundene.append(m)
        if anzahl > 0:
            konfidenz = min(
                MARKER_BASIS_KONFIDENZ
                + MARKER_BONUS_PRO_TREFFER * (anzahl - 1),
                MARKER_MAX_KONFIDENZ,
            )
            treffer[klasse_name] = {"konfidenz": konfidenz, "quelle": "marker"}
            hinweise.append(
                f"Marker fuer {klasse_name}: {gefundene}"
            )

    for klasse_name in signal_klassen:
        if klasse_name in treffer:
            # Marker + Signal: kleiner Bonus, weiter unter MARKER_MAX
            treffer[klasse_name]["konfidenz"] = min(
                treffer[klasse_name]["konfidenz"] + SIGNAL_PLUS_MARKER_BONUS,
                MARKER_MAX_KONFIDENZ,
            )
            treffer[klasse_name]["quelle"] = "marker+signal"
            hinweise.append(f"Signal + Marker fuer {klasse_name}")
        else:
            # Vererbtes Signal allein -- niemals eindeutig
            treffer[klasse_name] = {
                "konfidenz": SIGNAL_KONFIDENZ,
                "quelle": "signal",
            }
            hinweise.append(f"Signal fuer {klasse_name} (vererbt)")

    kandidaten = [
        Kandidat(klasse=k, konfidenz=v["konfidenz"], quelle=v["quelle"])
        for k, v in treffer.items()
    ]
    kandidaten.sort(key=lambda x: x.konfidenz, reverse=True)
    return kandidaten, hinweise


def _kuerze(text: str) -> str:
    if not text:
        return ""
    if len(text) <= F11_MAX_ZEICHEN:
        return text
    return text[:F11_MAX_ZEICHEN]


def klassifiziere_stufe2(text_seite1: str,
                         text_letzte_seite: str,
                         kandidaten: Sequence[Kandidat],
                         labels: Sequence[str]) -> Tuple[str, float]:
    """LLM-basierte Klassifikation mit geschlossener Labelliste (Stufe 2).

    Ruft ``llm_service.klassifiziere_geschlossen``. Faellt der LLM-Call aus,
    liefert der beste Kandidat aus Stufe 1 die Klasse; ist auch der leer,
    ``sonstiges`` (falls in labels) oder das erste Label -- Konfidenz 0.5.
    """
    text_fuer_llm = _kuerze(text_seite1) + "\n\n---\n\n" + _kuerze(text_letzte_seite)
    label, konf = llm_service.klassifiziere_geschlossen(list(labels),
                                                       text_fuer_llm)

    if label is not None:
        return (label, float(konf))

    if kandidaten:
        top = kandidaten[0]
        return (top.klasse, float(top.konfidenz))

    fallback = "sonstiges" if "sonstiges" in labels else next(iter(labels), "")
    return (fallback, SONSTIGES_FALLBACK_KONFIDENZ)
