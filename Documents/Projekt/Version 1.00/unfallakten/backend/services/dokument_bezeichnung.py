"""
PRD-37: Regelbasierte Dokumentenbezeichnung.

Einheitliches Schema  «Label» «Aussteller» vom «Datum» («Betrag»)  —
leere Teile fallen weg. Nur inhaltliche Dokumentdaten (kein Eingangsdatum,
kein E-Mail-Absender), Ausnahme: Klasse 'sonstiges' faellt fuers Datum auf
das Eingangsdatum zurueck und traegt ein typ-abhaengiges Label
(Schreiben/E-Mail).

Feld-Rollen (aussteller/datum/betrag) und Klassen-Label kommen aus der
Intake-Registry (klassen/*.yaml, Felder 'label' + 'bezeichnung_felder').
Reine Funktion, kein DB-/IO-Zugriff -> voll testbar.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..parsers.pdf_utils import parse_betrag
from ..utils.datum import parse_datum
from ..word.styling import fmt_euro


def _fmt_datum(roh: Any) -> Optional[str]:
    if roh is None:
        return None
    s = str(roh).strip()
    if not s:
        return None
    d = parse_datum(s[:10]) or parse_datum(s)
    return d.strftime("%d.%m.%Y") if d else None


def _fmt_betrag(roh: Any) -> Optional[str]:
    if roh is None:
        return None
    if isinstance(roh, (int, float)):
        wert = float(roh)
    else:
        wert = parse_betrag(str(roh))
        if wert is None:
            return None
    return fmt_euro(wert)


def _text(roh: Any) -> Optional[str]:
    if roh is None:
        return None
    s = str(roh).strip()
    return s or None


def _zusammen(label: str, aussteller: Optional[str],
              datum: Optional[str], betrag: Optional[str]) -> str:
    teile = [label]
    if aussteller:
        teile.append(aussteller)
    if datum:
        teile.append(f"vom {datum}")
    s = " ".join(t for t in teile if t).strip()
    if betrag:
        s = f"{s} ({betrag})"
    return s.strip()


def baue_bezeichnung(klasse: Optional[str], felder: Optional[Dict[str, Any]],
                     kontext: Optional[Dict[str, Any]], registry) -> str:
    felder = felder or {}
    kontext = kontext or {}
    spec: Dict[str, Any] = {}
    if registry is not None and klasse:
        spec = (registry.klassen.get(klasse) or {})
    rollen = spec.get("bezeichnung_felder") or {}

    if klasse == "sonstiges":
        label = "E-Mail" if kontext.get("ist_email") else "Schreiben"
        datum = None
        datum_key = rollen.get("datum")
        if datum_key:
            datum = _fmt_datum(felder.get(datum_key))
        if not datum:
            datum = _fmt_datum(kontext.get("eingangsdatum"))
        return _zusammen(label, None, datum, None)

    label = (spec.get("bezeichnung_label") or spec.get("label")
             or klasse or "Dokument")
    aussteller = _text(felder.get(rollen["aussteller"])) if rollen.get("aussteller") else None
    datum = _fmt_datum(felder.get(rollen["datum"])) if rollen.get("datum") else None
    betrag = _fmt_betrag(felder.get(rollen["betrag"])) if rollen.get("betrag") else None
    return _zusammen(label, aussteller, datum, betrag)


# Klassen, deren 'datum'-Rolle nachweislich NICHT das Datum des Schreibens
# traegt: beim Unfallfragebogen ist es der Unfalltag, der Jahre vor der
# Aufnahme des Bogens liegen kann.
KLASSEN_OHNE_DOKUMENTDATUM = ("fragebogen",)


def dokument_datum_aus_feldern(klasse: Optional[str],
                               felder: Optional[Dict[str, Any]],
                               registry,
                               eingangsdatum: Optional[str] = None) -> Optional[str]:
    """Datum des Schreibens als ISO-String, oder None.

    Liest dieselbe ``bezeichnung_felder.datum``-Rolle wie baue_bezeichnung.
    Liefert kein Feldtreffer, faellt die Funktion auf ``eingangsdatum``
    zurueck, sofern der Aufrufer eines uebergibt -- sie kennt selbst keine
    Klasse, die einen Rueckfall verdient. Bei gescannter Post liegt zwischen
    Schreiben und Scan oft eine Luecke, deshalb geben nur Aufrufer, die
    wissen dass es sich um eine E-Mail handelt (Zustellung = Versand), ein
    ``eingangsdatum`` mit -- fuer Post bleibt es None und das Feld bleibt
    leer, damit der Anwalt es vom Papier abliest.

    ``KLASSEN_OHNE_DOKUMENTDATUM`` schaltet nur die Feld-Auswertung ab
    (z. B. der Unfalltag im Fragebogen ist kein Schreibdatum) -- der
    Rueckfall auf ``eingangsdatum`` gilt trotzdem, falls uebergeben.
    """
    felder = felder or {}
    d = None

    if klasse not in KLASSEN_OHNE_DOKUMENTDATUM:
        spec: Dict[str, Any] = {}
        if registry is not None and klasse:
            spec = (registry.klassen.get(klasse) or {})
        rollen = spec.get("bezeichnung_felder") or {}

        datum_key = rollen.get("datum")
        roh = felder.get(datum_key) if datum_key else None
        if roh is not None:
            s = str(roh).strip()
            d = parse_datum(s[:10]) or parse_datum(s)

    if d is None and eingangsdatum is not None:
        s = str(eingangsdatum).strip()
        if s:
            d = parse_datum(s[:10]) or parse_datum(s)

    return d.isoformat() if d else None
