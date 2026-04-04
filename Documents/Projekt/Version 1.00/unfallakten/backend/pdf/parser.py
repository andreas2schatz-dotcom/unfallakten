"""
Modul 4 – PDF-Parser: Schadenpositionen
=========================================
Extrahiert strukturierte Schadendaten aus deutschen Kfz-Gutachten,
Abrechnungsschreiben und Versicherungskorrespondenz.

Unterstützte Dokumenttypen:
  - Kfz-Sachverständigengutachten (Reparaturkosten, Wiederbeschaffung, SV-Kosten)
  - Versicherungsabrechnungen (regulierte Beträge, Kürzungen)
  - Forderungsschreiben (Gesamtforderung)

Strategie:
  1. Regex-Muster für bekannte Felder
  2. Konfidenz-Score je Feld (0.0–1.0)
  3. Plausibilitätsprüfung (Summe ≈ Gesamt)
  4. Ergebnis als JSON gespeichert → in Modul 5 für Word-Generierung nutzbar
"""

import re
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── Datenstruktur ─────────────────────────────────────────────────────────────

@dataclass
class ParseErgebnis:
    """
    Geparste Schadendaten aus einem PDF.
    None bedeutet: nicht gefunden. 0.0 bedeutet: explizit als 0 angegeben.
    """
    # Schadenpositionen
    reparaturkosten:    Optional[float] = None
    wiederbeschaffung:  Optional[float] = None
    restwert:           Optional[float] = None
    wertminderung:      Optional[float] = None
    nutzungsausfall:    Optional[float] = None
    mietwagenkosten:    Optional[float] = None
    sv_kosten:          Optional[float] = None
    abschleppkosten:    Optional[float] = None
    standkosten:        Optional[float] = None
    anabmeldekosten:    Optional[float] = None
    schmerzensgeld:     Optional[float] = None
    sonstiges:          Optional[float] = None

    # Metadaten
    gesamtschaden:      Optional[float] = None   # Aus PDF extrahiert
    vers_referenz:      Optional[str]   = None
    betrag_reguliert:   Optional[float] = None
    kfz_kennzeichen:    Optional[str]   = None
    unfalldatum:        Optional[str]   = None

    # Qualitätsbewertung
    konfidenz:          float = 0.0        # 0.0 – 1.0
    felder_gefunden:    list  = field(default_factory=list)
    warnungen:          list  = field(default_factory=list)
    dokumenttyp:        str   = "unbekannt"

    def als_dict(self) -> dict:
        return asdict(self)

    def als_json(self) -> str:
        return json.dumps(self.als_dict(), ensure_ascii=False, default=str)

    @property
    def berechneter_gesamt(self) -> float:
        """Berechnet Gesamtschaden aus geparsten Einzelpositionen."""
        felder = [
            self.reparaturkosten, self.nutzungsausfall,
            self.mietwagenkosten, self.sv_kosten, self.abschleppkosten,
            self.standkosten, self.anabmeldekosten, self.schmerzensgeld,
            self.sonstiges, self.wertminderung,
        ]
        summe = sum(f for f in felder if f is not None)
        # Totalschaden: Wiederbeschaffung minus Restwert
        if self.wiederbeschaffung is not None:
            summe += self.wiederbeschaffung - (self.restwert or 0.0)
        return round(summe, 2)


# ── Zahl-Parser ───────────────────────────────────────────────────────────────

def _parse_euro(text: str) -> Optional[float]:
    """
    Wandelt deutsche Eurobeträge in float um.
    Unterstützt: "1.234,56", "1234,56", "1.234,56 €", "EUR 1.234,56"

    Returns:
        float oder None wenn nicht parsebar
    """
    if not text:
        return None
    # Eurozeichen und Währungskürzel entfernen
    bereinigt = re.sub(r"[€EUReur\s]", "", text.strip())
    # Deutsches Format: Tausenderpunkt entfernen, Komma → Punkt
    bereinigt = bereinigt.replace(".", "").replace(",", ".")
    try:
        wert = float(bereinigt)
        if wert < 0 or wert > 2_000_000:
            return None
        return round(wert, 2)
    except ValueError:
        return None


def _suche_betrag(pattern: str, text: str,
                  flags: int = re.IGNORECASE) -> Optional[float]:
    """
    Sucht einen Eurobetrag nach einem Label-Muster.
    Pattern muss eine Gruppe enthalten die den Betrag matched.
    """
    match = re.search(pattern, text, flags)
    if not match:
        return None
    return _parse_euro(match.group(1))


def _alle_betraege(pattern: str, text: str) -> list[float]:
    """Findet alle Eurobeträge zu einem Muster."""
    matches = re.findall(pattern, text, re.IGNORECASE)
    result = []
    for m in matches:
        val = _parse_euro(m)
        if val is not None and val > 0:
            result.append(val)
    return result


# ── Dokumenttyp-Erkennung ─────────────────────────────────────────────────────

def erkenne_dokumenttyp(text: str) -> str:
    """Klassifiziert den Dokumenttyp anhand von Schlüsselwörtern."""
    text_lower = text.lower()

    # Priorität: spezifischste Erkennung zuerst
    if any(w in text_lower for w in [
        "sachverständigengutachten", "kfz-gutachten", "schadengutachten",
        "schadensgutachten", "reparaturkalkulation", "bewertungsgutachten"
    ]):
        return "gutachten"

    if any(w in text_lower for w in [
        "abrechnung", "schadensabrechnung", "regulierung",
        "wir erstatten", "wir zahlen", "zahlung"
    ]):
        return "abrechnung"

    if any(w in text_lower for w in [
        "forderung", "geltend", "schadensersatz", "wir fordern",
        "in höhe von", "rechtsanwalt", "kanzlei"
    ]):
        return "forderungsschreiben"

    if any(w in text_lower for w in [
        "anfrage", "sachstand", "aktenzeichen", "bearbeitung"
    ]):
        return "sachstandsanfrage"

    return "sonstiges"


# ── Kern-Extraktion ───────────────────────────────────────────────────────────

# Betrag-Muster: 1-7 Ziffern, optionaler Tausenderpunkt, Komma, 2 Nachkommastellen
_BETRAG = r"([\d]{1,3}(?:\.?\d{3})*[,\.]\d{2})\s*(?:EUR|€)?"

def extrahiere_schadenpositionen(text: str) -> ParseErgebnis:
    """
    Extrahiert Schadenpositionen aus dem Rohtext eines PDFs.

    Returns:
        ParseErgebnis mit allen gefundenen Werten und Konfidenz-Score
    """
    ergebnis = ParseErgebnis()
    ergebnis.dokumenttyp = erkenne_dokumenttyp(text)

    # ── Reparaturkosten ──────────────────────────────────────────────────────
    rep_muster = [
        rf"reparaturkosten?\s*(?:\([^)]*\)\s*)?:?\s*(?:netto\s*:?\s*)?(?:brutto\s*:?\s*)?(?:EUR\s*|€\s*)?{_BETRAG}",
        rf"kosten\s+(?:der\s+)?reparatur\s*:?\s*{_BETRAG}",
        rf"reparatur(?:aufwand|summe|betrag)\s*:?\s*{_BETRAG}",
        rf"nettoreparaturkosten\s*:?\s*{_BETRAG}",
        rf"bruttoreparaturkosten?\s*:?\s*{_BETRAG}",
        # Tabellenformat: "Reparaturkosten  6.240,50"
        rf"reparatur[^\n]{{0,60}}{_BETRAG}",
    ]
    for m in rep_muster:
        val = _suche_betrag(m, text)
        if val and val > 100:
            ergebnis.reparaturkosten = val
            ergebnis.felder_gefunden.append("reparaturkosten")
            break

    # ── Wiederbeschaffungswert ────────────────────────────────────────────────
    wbw_muster = [
        rf"wiederbeschaffungswert\s*:?\s*(?:EUR\s*|€\s*)?{_BETRAG}",
        rf"wbw\s*:?\s*{_BETRAG}",
        rf"wiederbeschaffung(?:swert|spreis)?\s*:?\s*{_BETRAG}",
        rf"zeitwert\s*:?\s*{_BETRAG}",
    ]
    for m in wbw_muster:
        val = _suche_betrag(m, text)
        if val and val > 500:
            ergebnis.wiederbeschaffung = val
            ergebnis.felder_gefunden.append("wiederbeschaffung")
            break

    # ── Restwert ─────────────────────────────────────────────────────────────
    rw_muster = [
        rf"restwert\s*:?\s*(?:EUR\s*|€\s*)?{_BETRAG}",
        rf"restwert\s+(?:gem\.\s*angebot\s*)?:?\s*{_BETRAG}",
        rf"veräußerungswert\s*:?\s*{_BETRAG}",
    ]
    for m in rw_muster:
        val = _suche_betrag(m, text)
        if val is not None:
            ergebnis.restwert = val
            ergebnis.felder_gefunden.append("restwert")
            break

    # ── SV-Kosten ─────────────────────────────────────────────────────────────
    sv_muster = [
        rf"(?:sv|sachverständigen?)-?kosten\s*:?\s*{_BETRAG}",
        rf"gutachterkosten?\s*:?\s*{_BETRAG}",
        rf"gutachtenkosten?\s*:?\s*{_BETRAG}",
        rf"sachverständigenhonorar\s*:?\s*{_BETRAG}",
        rf"honorar\s*(?:brutto\s*)?:?\s*{_BETRAG}",
    ]
    for m in sv_muster:
        val = _suche_betrag(m, text)
        if val and val > 50:
            ergebnis.sv_kosten = val
            ergebnis.felder_gefunden.append("sv_kosten")
            break

    # ── Nutzungsausfall ───────────────────────────────────────────────────────
    naf_muster = [
        rf"nutzungsausfall(?:entschädigung|schaden)?\s*:?\s*{_BETRAG}",
        rf"nutzungsausfallentschädigung\s*:?\s*{_BETRAG}",
        rf"ausfalltage?[^\n]{{0,60}}{_BETRAG}",
    ]
    for m in naf_muster:
        val = _suche_betrag(m, text)
        if val and val > 0:
            ergebnis.nutzungsausfall = val
            ergebnis.felder_gefunden.append("nutzungsausfall")
            break

    # ── Mietwagenkosten ───────────────────────────────────────────────────────
    mw_muster = [
        rf"mietwagenkosten?\s*:?\s*{_BETRAG}",
        rf"mietwagen(?:kosten?|rechnung)?\s*:?\s*{_BETRAG}",
        rf"ersatzfahrzeug(?:kosten)?\s*:?\s*{_BETRAG}",
    ]
    for m in mw_muster:
        val = _suche_betrag(m, text)
        if val and val > 0:
            ergebnis.mietwagenkosten = val
            ergebnis.felder_gefunden.append("mietwagenkosten")
            break

    # ── Wertminderung ─────────────────────────────────────────────────────────
    wm_muster = [
        rf"merkantile\s+wertminderung\s*:?\s*{_BETRAG}",
        rf"wertminderung\s*:?\s*{_BETRAG}",
        rf"minderwert\s*:?\s*{_BETRAG}",
    ]
    for m in wm_muster:
        val = _suche_betrag(m, text)
        if val and val > 0:
            ergebnis.wertminderung = val
            ergebnis.felder_gefunden.append("wertminderung")
            break

    # ── Abschleppkosten ───────────────────────────────────────────────────────
    abschleppkosten = _suche_betrag(
        rf"abschleppkosten?\s*:?\s*{_BETRAG}", text)
    if abschleppkosten and abschleppkosten > 0:
        ergebnis.abschleppkosten = abschleppkosten
        ergebnis.felder_gefunden.append("abschleppkosten")

    # ── Standkosten ───────────────────────────────────────────────────────────
    standkosten = _suche_betrag(
        rf"standkosten?\s*:?\s*{_BETRAG}", text)
    if standkosten and standkosten > 0:
        ergebnis.standkosten = standkosten
        ergebnis.felder_gefunden.append("standkosten")

    # ── An-/Abmeldekosten ─────────────────────────────────────────────────────
    anabm = _suche_betrag(
        rf"(?:an-?\s*/?\s*ab-?|an-?|zulassungs-)meldekosten?\s*:?\s*{_BETRAG}", text)
    if anabm and anabm > 0:
        ergebnis.anabmeldekosten = anabm
        ergebnis.felder_gefunden.append("anabmeldekosten")

    # ── Schmerzensgeld ────────────────────────────────────────────────────────
    sg = _suche_betrag(
        rf"schmerzensgeld\s*:?\s*{_BETRAG}", text)
    if sg and sg > 0:
        ergebnis.schmerzensgeld = sg
        ergebnis.felder_gefunden.append("schmerzensgeld")

    # ── Gesamtschaden (für Plausibilitätsprüfung) ─────────────────────────────
    gesamt_muster = [
        rf"gesamtschaden\s*:?\s*{_BETRAG}",
        rf"gesamtbetrag\s*:?\s*{_BETRAG}",
        rf"gesamt(?:summe|forderung)?\s*:?\s*{_BETRAG}",
        rf"summe\s*(?:gesamt\s*)?:?\s*{_BETRAG}",
        rf"schadenssumme\s*:?\s*{_BETRAG}",
    ]
    for m in gesamt_muster:
        val = _suche_betrag(m, text)
        if val and val > 100:
            ergebnis.gesamtschaden = val
            ergebnis.felder_gefunden.append("gesamtschaden")
            break

    # ── Regulierter Betrag (aus Abrechnungsschreiben) ─────────────────────────
    reg_muster = [
        rf"wir\s+(?:erstatten|zahlen|überweisen|regulieren)[^\n]{{0,40}}{_BETRAG}",
        rf"regulierungsbetrag\s*:?\s*{_BETRAG}",
        rf"anerkannte?r?\s+(?:betrag|schaden)\s*:?\s*{_BETRAG}",
        rf"ausgezahlt(?:er?\s+betrag)?\s*:?\s*{_BETRAG}",
    ]
    for m in reg_muster:
        val = _suche_betrag(m, text)
        if val and val > 0:
            ergebnis.betrag_reguliert = val
            ergebnis.felder_gefunden.append("betrag_reguliert")
            break

    # ── Versicherungsnummer ───────────────────────────────────────────────────
    vers_ref = re.search(
        r"(?:schaden(?:s)?-?nr|schadennummer|aktenzeichen|schadenfall|referenz)\s*[:\.]?\s*([A-Z0-9\-\/]{5,30})",
        text, re.IGNORECASE
    )
    if vers_ref:
        ergebnis.vers_referenz = vers_ref.group(1).strip()
        ergebnis.felder_gefunden.append("vers_referenz")

    # ── KFZ-Kennzeichen ───────────────────────────────────────────────────────
    kfz = re.search(
        r"\b([A-ZÄÖÜ]{1,3}[-\s][A-Z]{1,2}[-\s]\d{1,4}[EHeh]?)\b",
        text
    )
    if kfz:
        ergebnis.kfz_kennzeichen = kfz.group(1).replace(" ", "-")
        ergebnis.felder_gefunden.append("kfz_kennzeichen")

    # ── Unfalldatum ───────────────────────────────────────────────────────────
    datum = re.search(
        r"(?:unfalldatum|ereignisdatum|schadensdatum|datum\s+des\s+unfalls?)\s*[:\.]?\s*"
        r"(\d{1,2}[.\/]\d{1,2}[.\/]\d{2,4})",
        text, re.IGNORECASE
    )
    if datum:
        ergebnis.unfalldatum = datum.group(1)
        ergebnis.felder_gefunden.append("unfalldatum")

    # ── Konfidenz berechnen ───────────────────────────────────────────────────
    ergebnis.konfidenz = _berechne_konfidenz(ergebnis)

    # ── Plausibilitätsprüfung ─────────────────────────────────────────────────
    _pruefe_plausibilitaet(ergebnis)

    return ergebnis


def _berechne_konfidenz(ergebnis: ParseErgebnis) -> float:
    """
    Berechnet einen Konfidenz-Score basierend auf:
      - Anzahl gefundener Felder
      - Plausibilität der Gesamtsumme
      - Dokumenttyp-Erkennung
    """
    score = 0.0

    # Basis: Felder gefunden
    gewichte = {
        "reparaturkosten":   0.25,
        "wiederbeschaffung": 0.20,
        "sv_kosten":         0.15,
        "nutzungsausfall":   0.10,
        "wertminderung":     0.10,
        "gesamtschaden":     0.10,
        "kfz_kennzeichen":   0.05,
        "betrag_reguliert":  0.05,
    }
    for feld, gewicht in gewichte.items():
        if feld in ergebnis.felder_gefunden:
            score += gewicht

    # Bonus: Dokumenttyp erkannt
    if ergebnis.dokumenttyp != "unbekannt":
        score += 0.05

    # Bonus: Gesamtsumme stimmt (innerhalb 5% Toleranz)
    if ergebnis.gesamtschaden and ergebnis.berechneter_gesamt > 0:
        abweichung = abs(ergebnis.gesamtschaden - ergebnis.berechneter_gesamt)
        if abweichung / max(ergebnis.gesamtschaden, 1) < 0.05:
            score += 0.15

    return round(min(score, 1.0), 3)


def _pruefe_plausibilitaet(ergebnis: ParseErgebnis):
    """Fügt Warnungen bei unplausiblen Werten hinzu."""

    # Reparatur + Totalschaden gleichzeitig
    if ergebnis.reparaturkosten and ergebnis.wiederbeschaffung:
        if ergebnis.reparaturkosten > ergebnis.wiederbeschaffung * 1.3:
            ergebnis.warnungen.append(
                "Reparaturkosten übersteigen Wiederbeschaffungswert deutlich "
                "(evtl. Totalschaden)."
            )

    # Restwert ohne Wiederbeschaffung
    if ergebnis.restwert and not ergebnis.wiederbeschaffung:
        ergebnis.warnungen.append(
            "Restwert ohne Wiederbeschaffungswert – evtl. Totalschaden-Daten unvollständig."
        )

    # Gesamtabweichung > 20%
    if ergebnis.gesamtschaden and ergebnis.berechneter_gesamt > 0:
        abw = abs(ergebnis.gesamtschaden - ergebnis.berechneter_gesamt)
        if abw / max(ergebnis.gesamtschaden, 1) > 0.20:
            ergebnis.warnungen.append(
                f"Berechneter Gesamtschaden ({ergebnis.berechneter_gesamt:.2f} €) "
                f"weicht vom extrahierten Wert ({ergebnis.gesamtschaden:.2f} €) "
                f"um mehr als 20% ab."
            )

    # Extrem hohe Einzelwerte
    for feld, wert, grenze in [
        ("sv_kosten",       ergebnis.sv_kosten,       15_000),
        ("nutzungsausfall", ergebnis.nutzungsausfall,  10_000),
        ("abschleppkosten", ergebnis.abschleppkosten,  5_000),
    ]:
        if wert and wert > grenze:
            ergebnis.warnungen.append(
                f"{feld}: {wert:.2f} € erscheint ungewöhnlich hoch "
                f"(> {grenze:,} €). Bitte manuell prüfen."
            )
