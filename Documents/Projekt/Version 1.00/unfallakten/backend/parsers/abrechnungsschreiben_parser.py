"""
Parser für Abrechnungsschreiben der Versicherungen.

Unterstützte Versicherer:
- HDI Global SE
- VHV Allgemeine Versicherung AG
- HUK-COBURG
- Allianz Versicherungs-AG
- Allianz Direct Versicherungs-AG
- (erweiterbar)

Rückgabe-Datenstruktur orientiert sich am Modul-9-Schema:
- positionen: Liste von regulierungs_positionen
- gesamtbetrag: Gesamtgezahlter Betrag
- zahlungen: Einzelzahlungen mit Empfänger
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from .pdf_utils import parse_betrag, find_betrag_near_label, normalize_text

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Datenklassen für das Ergebnis
# ──────────────────────────────────────────────────────────

@dataclass
class ParsedPosition:
    """Eine erkannte Regulierungsposition."""
    art: str           # z.B. "reparatur_netto", "sv_kosten", "kostenpauschale", etc.
    bezeichnung: str   # Originalbezeichnung aus dem Dokument
    betrag_brutto: Optional[float] = None
    betrag_netto: Optional[float] = None
    mwst_betrag: Optional[float] = None
    pruefbericht_abzug: Optional[float] = None
    konfidenz: float = 1.0
    hinweis: str = ""  # z.B. "Abzug laut Prüfbericht"


@dataclass
class ParsedZahlung:
    """Eine erkannte Zahlung."""
    empfaenger: str       # "kanzlei", "sv_buero", "sonstige", oder Name
    betrag: float = 0.0
    datum: str = ""       # YYYY-MM-DD
    konto_hinweis: str = ""  # letzte 4 Stellen o.ä.


@dataclass
class AbrechnungParseResult:
    """Gesamtergebnis des Abrechnungsschreiben-Parsers."""
    positionen: list[ParsedPosition] = field(default_factory=list)
    gesamtbetrag: Optional[float] = None
    zahlungen: list[ParsedZahlung] = field(default_factory=list)
    abrechnungsart: str = "unbekannt"  # "reparatur_fiktiv", "reparatur_konkret", "totalschaden"
    mwst_hinweis: bool = False          # Nettobetrag, MwSt auf Anfrage
    konfidenz: float = 0.0
    warnungen: list[str] = field(default_factory=list)
    # LLM Shadow-Mode
    llm_verwendet: bool = False
    llm_konflikt: bool = False
    llm_gesamtbetrag: Optional[float] = None   # Qwen's Gesamtbetrag zum Vergleich
    llm_positionen: list = field(default_factory=list)  # Qwen's Positionen [{art, betrag_netto, betrag_brutto}]


# ──────────────────────────────────────────────────────────
# Positions-Erkennungs-Patterns
# Jeder Eintrag: (art, bezeichnung_pattern, suchfenster)
# ──────────────────────────────────────────────────────────
POSITIONS_PATTERNS = [
    # Reparaturkosten – spezifische Varianten zuerst
    ("reparatur_brutto", r"Reparaturkosten\s+(?:gemäß|nach|laut)\s+Gutachten", 200),
    ("reparatur_brutto", r"Reparaturkosten\s+(?:gemäß|nach|laut)\s+Kostenvoranschlag", 200),
    ("reparatur_netto",  r"kalkulierte\s+Reparaturkosten\s+ohne\s+Mehrwertsteuer", 150),
    ("reparatur_netto",  r"Reparaturkosten\s+ohne\s+Mehrwertsteuer", 150),
    # Standalone "Reparaturkosten N.NNN,NN" (HUK-COBURG Reparatur-Format)
    ("reparatur_netto",  r"^Reparaturkosten\s+[\d]", 80),
    # VHV: regulierte Reparaturkosten stehen als "Abrechnung nach Prüfbericht N,NN EUR"
    ("reparatur_netto",  r"Abrechnung\s+nach\s+Prüfbericht", 80),

    # Sachverständigen – großes Fenster wegen Netto→USt→Brutto-Aufbau
    # (Brutto steht als letzter Betrag; Extraktion nimmt daher den letzten Betrag im Fenster)
    ("sv_kosten",        r"SV[-\s]Kosten",                               500),  # Gothaer: "SV-Kosten"
    ("sv_kosten",        r"Sachverständigen(?:kosten|gebühren|honorar)", 500),

    # Nutzungsausfall / Sonstiges
    ("nutzungsausfall",  r"Nutzungsausfall",                            150),
    ("abschleppkosten",  r"Abschleppkosten",                             80),
    ("restkraftstoff",   r"Restkraftstoff",                              80),

    # WBA – Wiederbeschaffungsaufwand (WBW minus Restwert; trumpft wbw bei Totalschaden)
    # Muss VOR wbw stehen damit found_arts-Prüfung greift
    ("wba",              r"Wiederbeschaffungsaufwand", 120),
    ("wba",              r"\bWBA\b", 80),

    # Wiederbeschaffung / Restwert – Reihenfolge wichtig (spezifischer zuerst)
    ("wbw_netto",        r"Wiederbeschaffungswert(?:e)?\s+netto", 120),
    ("wbw_brutto",       r"Wiederbeschaffungswert(?:e)?\s+brutto", 120),
    # Nicht-netto/brutto WBW – aber wbw_netto und wbw_brutto werden zuerst gefunden
    ("wbw",              r"Wiederbeschaffungswert(?:e)?(?!\s*(?:netto|brutto|ohne|mit))", 120),
    # Restwert: "Restwerte lt. unserem Angebot", "Restwert lt. Angebot", "- Restwert N EUR"
    # \s* statt \s+ wegen VHV-Leerzeichenproblem (z.B. "Restwertelt.")
    ("restwert",         r"Restwert(?:e)?\s*lt\.?\s*(?:unserem\s*)?Angebot", 100),
    ("restwert",         r"abzüglich\s+Restwert\s+", 30),   # AllianzDirect Inline-Format
    ("restwert",         r"-\s*Restwert\s+[\d]", 50),
    ("restwert",         r"Restwert(?:e)?\s+[\d-]", 40),    # enger Fenster – kein Überlauf auf nächste Zeile
    ("fahrzeugschaden",  r"Fahrzeugschaden", 120),

    # Sonstiges
    ("kostenpauschale",  r"Kostenpauschale", 100),
    ("wertminderung",    r"Wertminderung", 100),
    ("ra_gebuehren",     r"Rechtsanwalts(?:gebühren|kosten)", 120),
    ("mwst_abzug",       r"(?:Mehrwertsteuer|MwSt\.?)\s*\(\s*19\s*%\s*\)", 100),
    ("mwst_abzug",       r"(?:Mehrwertsteuer|MwSt\.?)\s*\(\s*\d+\s*%\s*\)", 100),
    ("pruefbericht_abzug", r"laut\s+Prüfbericht", 100),
    ("pruefbericht_abzug", r"lt\.?\s+Prüfbericht", 100),
]

# Gesamtbetrag-Patterns (suchen nach dem letzten/größten erkannten Betrag)
GESAMTBETRAG_PATTERNS = [
    r"(?:Entschädigungsbetrag|Gesamtentschädigung)\s+([\d.]+,\d{2})\s*€?",
    r"Regulierungsbetrag\s+([\d.]+,\d{2})\s*(?:EUR|€)?",      # Generali
    r"Auszahlungsbetrag\s+([\d.]+,\d{2})\s*(?:EUR|€)?",
    r"Zahlungsbetrag\s+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Betrag\s+in\s+Höhe\s+von\s+([\d.]+,\d{2})\s+EUR",
    r"Summe:\s+([\d.]+,\d{2})\s*(?:EUR|€)?",
    r"Gesamtbetrag\s*:\s*([\d.]+,\d{2})\s*(?:EUR|€)",          # Gothaer
    # HUK: "===============" nach dem Betrag
    r"([\d.]+,\d{2})\s*€?\s*\n\s*[=]+",
]

# Zahlungs-Patterns
ZAHLUNG_PATTERNS = [
    # "Am DD.MM.YYYY an [Empfänger] Betrag"
    r"Am\s+(\d{2}\.\d{2}\.\d{4})\s+an\s+(.*?)\s+([\d.]+,\d{2})\s*€?",
    # "Zahlung per Überweisung Betrag"
    r"Zahlung\s+per\s+Überweisung\s+([\d.]+,\d{2})\s*(?:EUR|€)",
    # "an Sie: gezahlt Betrag"
    r"an\s+Sie\s*:\s*gezahlt\s+([\d.]+,\d{2})\s*(?:EUR|€)",
    # "abgetreten an [Name]: gezahlt Betrag"
    r"abgetreten\s+an\s+(.*?):\s*\n?\s*gezahlt\s+([\d.]+,\d{2})\s*(?:EUR|€)",
    # "Den Betrag in Höhe von X EUR haben wir auf Ihr Konto ... angewiesen"
    r"Den\s+Betrag\s+in\s+Höhe\s+von\s+([\d.]+,\d{2})\s+EUR\s+haben\s+wir\s+auf\s+(?:Ihr\s+)?Konto[^.]*angewiesen",
]


def _detect_abrechnungsart(text: str) -> str:
    """Erkennt ob Reparatur (fiktiv/konkret) oder Totalschaden."""
    text_lower = text.lower()
    # Totalschaden: NUR wenn tatsächliche WBW/Restwert-Beträge im Text
    # "Totalschadenfall" in Boilerplate-Sätzen zählt NICHT
    has_wbw_betrag = bool(re.search(
        r"Wiederbeschaffungswert(?:e)?(?:\s+netto|\s+brutto)?\s+[\d]",
        text, re.IGNORECASE
    ))
    has_restwert_betrag = bool(re.search(
        r"Restwert(?:e)?(?:\s+lt\.?|\s+laut|\s+nach|\s+gem|\s+:)?\s+[\d-]",
        text, re.IGNORECASE
    ))
    if has_wbw_betrag or has_restwert_betrag:
        return "totalschaden"
    if "ohne mehrwertsteuer" in text_lower or "nettobetrag" in text_lower:
        return "reparatur_fiktiv"
    if "reparaturrechnung" in text_lower and "liegt vor" in text_lower:
        return "reparatur_konkret"
    if "reparaturkosten" in text_lower:
        return "reparatur_fiktiv"
    return "unbekannt"


def _extract_reparatur_mit_abzuegen(text: str) -> list[ParsedPosition]:
    """
    Spezialfall HDI-Layout: Reparaturkosten mit eingebetteten Abzügen.
    
    Muster:
      Reparaturkosten gemäß Gutachten    3.574,95
       ./. Mehrwertsteuer (19%)           570,79
       ./. laut Prüfbericht               444,85
       ergibt einen Gesamtabzug von     1.015,64    2.559,31 EUR
    """
    positionen = []

    # Suche den Reparaturkosten-Block
    block_m = re.search(
        r"(Reparaturkosten\s+gemäß\s+(?:Gutachten|Kostenvoranschlag))\s+([\d.]+,\d{2})(.*?)"
        r"(\d[\d.,]+)\s*(?:EUR|€)",
        text, re.DOTALL | re.IGNORECASE
    )
    if not block_m:
        return positionen

    brutto_str = block_m.group(2)
    block_text = block_m.group(3)

    brutto = parse_betrag(brutto_str)
    if brutto:
        pos = ParsedPosition(
            art="reparatur_brutto",
            bezeichnung="Reparaturkosten gemäß Gutachten",
            betrag_brutto=brutto,
            konfidenz=0.95,
        )

        # MwSt-Abzug
        mwst_m = re.search(r"\.\/?\..*?Mehrwertsteuer[^0-9]+([\d.]+,\d{2})", block_text, re.IGNORECASE)
        if mwst_m:
            pos.mwst_betrag = parse_betrag(mwst_m.group(1))

        # Prüfbericht-Abzug
        pb_m = re.search(r"\.\/?\..*?(?:laut|lt\.?)\s+Prüfbericht[^0-9]+([\d.]+,\d{2})", block_text, re.IGNORECASE)
        if pb_m:
            pos.pruefbericht_abzug = parse_betrag(pb_m.group(1))

        # Nettobetrag nach allen Abzügen
        netto_candidates = re.findall(r"([\d.]+,\d{2})\s*(?:EUR|€)", block_text)
        if netto_candidates:
            # Letzter Betrag im Block = regulierter Nettobetrag
            pos.betrag_netto = parse_betrag(netto_candidates[-1])

        if pos.betrag_netto and pos.pruefbericht_abzug:
            pos.hinweis = f"Prüfbericht-Kürzung: -{pos.pruefbericht_abzug:.2f} EUR"

        positionen.append(pos)

    return positionen


_GOTHAER_ART_MAP = {
    "wiederbeschaffungswert": "wbw",
    "sv-kosten":              "sv_kosten",
    "sachverständig":         "sv_kosten",
    "kostenpauschale":        "kostenpauschale",
    "restkraftstoff":         "restkraftstoff",
    "nutzungsausfall":        "nutzungsausfall",
    "abschleppkosten":        "abschleppkosten",
    "wertminderung":          "wertminderung",
    "reparaturkosten":        "reparatur_netto",
    "wertverbesserung":       "wertminderung",
    "unkostenpauschale":      "kostenpauschale",
}


def _extract_gothaer_positionen(text: str) -> list[ParsedPosition]:
    """
    Gothaer-Layout: Strichliste mit Doppelpunkt-Trenner.

    Muster: "- LABEL : BETRAG EUR"

    Der Betrag steht immer NACH dem Doppelpunkt – dadurch wird z.B.
    "Nutzungsausfall 14 x 43 EUR : 602,00 EUR" korrekt mit 602,00 EUR
    ausgewertet und nicht mit dem Tagessatz 43 EUR.
    """
    positionen = []

    # Doppelpunkt (:) ist NICHT in der Label-Zeichenklasse → Greedy-Matching
    # stoppt automatisch am ersten ":" → Betrag nach ":" ist der Gesamtbetrag.
    line_re = re.compile(
        r"-\s+([\w][\w\s\-,./()]+)\s*:\s*([\d.]+,\d{2})\s*EUR",
        re.IGNORECASE,
    )

    for m in line_re.finditer(text):
        label = m.group(1).strip()
        betrag = parse_betrag(m.group(2))
        if not betrag:
            continue

        label_lower = label.lower()
        art = "sonstiges"
        for key, mapped_art in _GOTHAER_ART_MAP.items():
            if key in label_lower:
                art = mapped_art
                break

        positionen.append(ParsedPosition(
            art=art,
            bezeichnung=label,
            betrag_netto=betrag,
            konfidenz=0.92,
        ))

    return positionen


# Gesamt-/Zahlungszeilen begrenzen das sv_kosten-Suchfenster: dessen
# Maximum-Heuristik darf nicht den Auszahlungsbetrag der Folgezeilen greifen
# (VHV: "Sachverständigengebühren ... Zahlung per Überweisung 7.751,54 EUR").
_SUMMENZEILEN_RE = re.compile(
    r"Zahlung(?:sbetrag)?\b|Gesamtbetrag|Entschädigungsbetrag|"
    r"Gesamtentschädigung|Auszahlungsbetrag|Regulierungsbetrag|Summe\s*:",
    re.IGNORECASE,
)


def _extract_standard_positionen(text: str) -> list[ParsedPosition]:
    """Extrahiert Standardpositionen via Label + nachfolgendem Betrag."""
    positionen = []
    found_arts = set()

    # Erkennt sowohl "1.234,56 EUR" als auch Ganzzahlen "300 EUR" / "30 EUR"
    betrag_re = re.compile(
        r"([\d]{1,3}(?:[.,]\d{3})*,\d{2}|\b\d{2,6})\s*(?:EUR|€)"
    )

    for art, label_pattern, window in POSITIONS_PATTERNS:
        # Mehrfache Treffer vermeiden
        if art in found_arts:
            continue
        # WBW-Familie: wenn spezifischere Variante gefunden, generisches wbw überspringen
        if art == "wbw" and ("wbw_netto" in found_arts or "wbw_brutto" in found_arts):
            continue

        for m in re.finditer(label_pattern, text, re.IGNORECASE | re.MULTILINE):
            snippet = text[m.start(): m.start() + window]

            # sv_kosten: Brutto ist immer der GRÖSSTE Betrag im Block
            # (Teilposten < Netto < Brutto; Reihenfolge im Dokument variiert)
            # → alle Beträge im Fenster sammeln, Maximum nehmen
            if art == "sv_kosten":
                summen_m = _SUMMENZEILEN_RE.search(snippet)
                if summen_m:
                    snippet = snippet[:summen_m.start()]
                alle_vals = [parse_betrag(x) for x in betrag_re.findall(snippet)]
                alle_vals = [v for v in alle_vals if v is not None and v > 0]
                val = max(alle_vals) if alle_vals else None
            else:
                betrag_m = betrag_re.search(snippet)
                val = parse_betrag(betrag_m.group(1)) if betrag_m else None

            if val is not None:
                bezeichnung = m.group(0).strip()
                pos = ParsedPosition(
                    art=art,
                    bezeichnung=bezeichnung,
                    konfidenz=0.85,
                )
                # Je nach Art als brutto oder netto speichern
                if art in ("reparatur_netto", "wbw_netto", "fahrzeugschaden",
                            "wba",
                            "kostenpauschale", "wertminderung",
                            "ra_gebuehren", "restwert",
                            "nutzungsausfall", "abschleppkosten", "restkraftstoff"):
                    pos.betrag_netto = val
                elif art == "sv_kosten":
                    # Brutto-Betrag – enthält bereits MwSt
                    pos.betrag_brutto = val
                elif art in ("reparatur_brutto", "wbw_brutto", "wbw"):
                    pos.betrag_brutto = val
                elif art in ("mwst_abzug", "pruefbericht_abzug"):
                    pos.betrag_netto = val
                    pos.hinweis = "Abzug"
                else:
                    pos.betrag_brutto = val

                positionen.append(pos)
                found_arts.add(art)
                break

    return positionen


def _extract_gesamtbetrag(text: str) -> Optional[float]:
    """Extrahiert den Gesamtentschädigungsbetrag."""
    betrag_re = re.compile(r"([\d.]+,\d{2})")

    for pattern in GESAMTBETRAG_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            # Erster capture group könnte der Betrag sein
            val = parse_betrag(m.group(1))
            if val and val > 0:
                return val

    return None


def _extract_zahlungen(text: str, versicherer_kuerzel: str = "") -> list[ParsedZahlung]:
    """Extrahiert Zahlungsdetails."""
    zahlungen = []

    # ── "Am DD.MM.YYYY an [Empfänger] Betrag" ──────────
    am_pattern = re.compile(
        r"Am\s+(\d{2}\.\d{2}\.\d{4})\s+an\s+(.*?)\s+(?:auf\s+(?:das\s+)?Konto\s*:\s*\S+\s+)?"
        r"([\d.]+,\d{2})\s*€?",
        re.IGNORECASE
    )
    for m in am_pattern.finditer(text):
        datum_raw = m.group(1)
        parts = datum_raw.split(".")
        datum = f"{parts[2]}-{parts[1]}-{parts[0]}"
        empfaenger_raw = m.group(2).strip().rstrip(".,:")

        # Klassifizierung des Empfängers
        empf_lower = empfaenger_raw.lower()
        if "sie" == empf_lower or "ihre" in empf_lower:
            empfaenger = "kanzlei"
        elif any(s in empf_lower for s in ["sachverständig", "sv-", "gutachter"]):
            empfaenger = "sv_buero"
        elif empfaenger_raw:
            empfaenger = empfaenger_raw
        else:
            empfaenger = "kanzlei"

        betrag = parse_betrag(m.group(3))
        if betrag:
            zahlungen.append(ParsedZahlung(
                empfaenger=empfaenger,
                betrag=betrag,
                datum=datum,
            ))

    # ── "an Sie: gezahlt Betrag" (HDI-Stil) ────────────
    if not zahlungen:
        an_sie = re.findall(
            r"an\s+Sie\s*:\s*\n?\s*gezahlt\s+([\d.]+,\d{2})\s*(?:EUR|€)",
            text, re.IGNORECASE
        )
        for b_str in an_sie:
            b = parse_betrag(b_str)
            if b:
                zahlungen.append(ParsedZahlung(empfaenger="kanzlei", betrag=b))

        # abgetreten an [Name]: gezahlt Betrag
        abgetreten = re.findall(
            r"abgetreten\s+an\s+(.*?):\s*\n?\s*gezahlt\s+([\d.]+,\d{2})\s*(?:EUR|€)",
            text, re.IGNORECASE
        )
        for name, b_str in abgetreten:
            b = parse_betrag(b_str)
            if b:
                zahlungen.append(ParsedZahlung(empfaenger=name.strip(), betrag=b))

    # ── "Zahlung per Überweisung Betrag" (VHV-Stil, auch ohne Leerzeichen) ────
    if not zahlungen:
        zpue = re.findall(
            r"Zahlung\s+per\s*Überweisung\s+([\d.]+,\d{2})\s*(?:EUR|€)",
            text, re.IGNORECASE
        )
        for b_str in zpue:
            b = parse_betrag(b_str)
            if b:
                zahlungen.append(ParsedZahlung(empfaenger="kanzlei", betrag=b))

    # ── "Betrag in Höhe von X EUR ... angewiesen" (Allianz Direct) ──
    if not zahlungen:
        m = re.search(
            r"Betrag\s+in\s+Höhe\s+von\s+([\d.]+,\d{2})\s+EUR\s+haben\s+wir.*?angewiesen",
            text, re.IGNORECASE | re.DOTALL
        )
        if m:
            b = parse_betrag(m.group(1))
            if b:
                zahlungen.append(ParsedZahlung(empfaenger="kanzlei", betrag=b))

    # ── "haben wir ... veranlasst" (Allianz-Stil) ──────────
    # Allianz schreibt "haben wir ... veranlasst" ohne Betrag im Satz.
    # Betrag steht als "Zahlungsbetrag X EUR" separat.
    if not zahlungen:
        if re.search(r"haben\s+wir\s+.*?veranlasst", text, re.IGNORECASE | re.DOTALL):
            zb_m = re.search(r"Zahlungsbetrag\s+([\d.]+,\d{2})\s*(?:EUR|€)", text, re.IGNORECASE)
            if zb_m:
                b = parse_betrag(zb_m.group(1))
                if b:
                    zahlungen.append(ParsedZahlung(empfaenger="kanzlei", betrag=b))

    # ── "Letztgenannter Betrag wird auf Ihr Konto überwiesen" (Gothaer) ──
    # Kein eigener Betrag im Satz – Gesamtbetrag steht weiter oben.
    if not zahlungen:
        if re.search(r"letztgenannter\s+betrag\s+wird", text, re.IGNORECASE):
            gb_m = re.search(
                r"Gesamtbetrag\s*:\s*([\d.]+,\d{2})\s*EUR",
                text, re.IGNORECASE,
            )
            if gb_m:
                b = parse_betrag(gb_m.group(1))
                if b:
                    zahlungen.append(ParsedZahlung(empfaenger="kanzlei", betrag=b))

    return zahlungen


def parse_abrechnungsschreiben(text: str, versicherer_kuerzel: str = "", llm_aktiv: bool = False) -> AbrechnungParseResult:
    """
    Hauptfunktion: Parst ein Abrechnungsschreiben.
    
    Args:
        text: Normalisierter Volltext des Dokuments
        versicherer_kuerzel: Optionaler Hinweis auf den Versicherer
    
    Returns:
        AbrechnungParseResult mit allen erkannten Daten
    """
    result = AbrechnungParseResult()

    # Abrechnungsart
    result.abrechnungsart = _detect_abrechnungsart(text)

    # MwSt-Hinweis
    result.mwst_hinweis = bool(re.search(
        r"(?:nettobetrag|ohne\s+(?:die\s+)?(?:gesetzliche\s+)?mehrwertsteuer|"
        r"tatsächlich\s+angefallen)",
        text, re.IGNORECASE
    ))

    # Positionen extrahieren
    # Versicherer-Spezialformate haben Vorrang vor dem generischen Parser.

    if versicherer_kuerzel == "GOTHAER":
        # Gothaer: Strichliste "- LABEL : BETRAG EUR"
        gothaer_positionen = _extract_gothaer_positionen(text)
        if gothaer_positionen:
            result.positionen = gothaer_positionen
        else:
            # Fallback auf Standardpositionen wenn Gothaer-Parser nichts findet
            result.positionen = _extract_standard_positionen(text)
    else:
        # HDI: Reparatur mit eingebetteten Abzügen
        hdi_positionen = _extract_reparatur_mit_abzuegen(text)
        standard_positionen = _extract_standard_positionen(text)

        if hdi_positionen:
            result.positionen = hdi_positionen
            for p in standard_positionen:
                if p.art not in ("reparatur_brutto", "reparatur_netto", "mwst_abzug", "pruefbericht_abzug"):
                    result.positionen.append(p)
        else:
            result.positionen = standard_positionen

    # Gesamtbetrag
    result.gesamtbetrag = _extract_gesamtbetrag(text)

    # Zahlungen
    result.zahlungen = _extract_zahlungen(text, versicherer_kuerzel)

    # Gesamtbetrag-Fallback: Summe aller Zahlungen wenn kein expliziter Gesamtbetrag erkannt
    if not result.gesamtbetrag and result.zahlungen:
        result.gesamtbetrag = round(sum(z.betrag for z in result.zahlungen), 2)

    # Konfidenz berechnen
    punkte = 0
    if result.positionen:
        punkte += min(len(result.positionen), 5)
    if result.gesamtbetrag:
        punkte += 2
    if result.zahlungen:
        punkte += 2
    if result.abrechnungsart != "unbekannt":
        punkte += 1

    result.konfidenz = min(punkte / 10.0, 1.0)

    # Plausibilitätsprüfung
    if result.gesamtbetrag and result.zahlungen:
        total_zahlungen = sum(z.betrag for z in result.zahlungen)
        if abs(total_zahlungen - result.gesamtbetrag) > 1.0:  # > 1 EUR Differenz
            result.warnungen.append(
                f"Gesamtbetrag ({result.gesamtbetrag:.2f} EUR) "
                f"weicht von Summe der Zahlungen ({total_zahlungen:.2f} EUR) ab"
            )

    # ── LLM Shadow-Mode ───────────────────────────────────────────────────────
    # Gemma läuft parallel zum Regex-Parser (wenn aktiviert).
    # Primäres Ergebnis bleibt immer das Regex-Ergebnis.
    # Abweichungen werden als Konflikt-Flag zurückgemeldet.
    if llm_aktiv:
        _llm_shadow(text, versicherer_kuerzel, result)

    return result


def _llm_shadow(
    text: str,
    versicherer: str,
    regex_result: "AbrechnungParseResult",
) -> None:
    """
    Führt Gemma parallel zum Regex-Parser aus (Shadow-Mode).
    Modifiziert regex_result in-place:
      llm_verwendet     = True wenn Gemma geantwortet hat
      llm_konflikt      = True wenn Gesamtbeträge um > 1 EUR abweichen
      llm_gesamtbetrag  = Gemma's Gesamtbetrag (zum Anzeigen im Frontend)
    Das Regex-Ergebnis wird NICHT ersetzt.
    """
    try:
        from ..services.llm_service import parse_abrechnung_raw as llm_parse
    except ImportError:
        return

    llm_dict = llm_parse(text, versicherer)
    if llm_dict is None:
        return  # Gemma nicht erreichbar oder JSON nicht parsierbar

    # Qwen hat geantwortet – Badge zeigen, auch wenn JSON unvollständig
    regex_result.llm_verwendet    = True
    regex_result.llm_gesamtbetrag = llm_dict.get("gesamtbetrag")
    regex_result.llm_positionen   = [
        {
            "art":           p.get("art", "sonstiges"),
            "bezeichnung":   p.get("bezeichnung", ""),
            "betrag_netto":  p.get("betrag_netto"),
            "betrag_brutto": p.get("betrag_brutto"),
        }
        for p in (llm_dict.get("positionen") or [])
        if isinstance(p, dict)
    ]

    # Konflikt-Prüfung: Gesamtbetrag weicht > 1 EUR ab
    r_total   = regex_result.gesamtbetrag or 0.0
    llm_total = regex_result.llm_gesamtbetrag or 0.0
    if r_total > 0 and llm_total > 0:
        regex_result.llm_konflikt = abs(r_total - llm_total) > 1.0
    elif r_total == 0 and llm_total > 0:
        # Regex hat keinen Gesamtbetrag erkannt, LLM schon → Konflikt,
        # damit Nutzer zwischen den Ergebnissen wählen kann
        regex_result.llm_konflikt = True

    # Positions-Konflikt: Auch wenn Gesamtbeträge übereinstimmen,
    # kann eine einzelne Position (z.B. sv_kosten) unterschiedlich sein
    if not regex_result.llm_konflikt and regex_result.llm_positionen:
        regex_pos_map = {
            p.art: (p.betrag_brutto or p.betrag_netto or 0.0)
            for p in regex_result.positionen
        }
        for llm_p in regex_result.llm_positionen:
            llm_val   = llm_p.get("betrag_brutto") or llm_p.get("betrag_netto") or 0.0
            regex_val = regex_pos_map.get(llm_p.get("art"), 0.0)
            if regex_val > 0 and llm_val > 0 and abs(regex_val - llm_val) > 1.0:
                regex_result.llm_konflikt = True
                logger.info(
                    "LLM Shadow: Positions-Konflikt bei art='%s': Regex=%.2f LLM=%.2f",
                    llm_p.get("art"), regex_val, llm_val,
                )
                break

    logger.info(
        "LLM Shadow: Regex=%.2f LLM=%.2f Konflikt=%s",
        r_total, llm_total, regex_result.llm_konflikt,
    )
