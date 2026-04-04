"""
Rechnungs-Parser (PRD-23b)
===========================
Extrahiert aus Rechnungs-PDFs: Nettobetrag, MwSt, Bruttobetrag, Datum, Rechnungsnummer.
Kein Aufbrechen in Einzelpositionen – nur Gesamtbetraege.

Python 3.9 kompatibel.
"""
import re
from typing import Optional
from dataclasses import dataclass, field

from .pdf_utils import parse_betrag


@dataclass
class RechnungParseResult:
    nettobetrag: Optional[float] = None
    mwst_betrag: Optional[float] = None
    bruttobetrag: Optional[float] = None
    rechnungsdatum: str = ""
    rechnungsnummer: str = ""
    konfidenz: float = 0.0
    warnungen: list = field(default_factory=list)


# Betragsmuster (deutsches Format: 1.234,56 oder 1234,56)
GESAMTBETRAG_PATTERNS = [
    r"Gesamtbetrag\s+inkl\.?\s+(?:MwSt|Mehrwertsteuer)[.\s:]*?([\d.]+,\d{2})\s*(?:EUR|€)?",
    r"Rechnungsbetrag\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Zu\s+zahlen\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Endbetrag\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Zahlungsbetrag\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Gesamtsumme\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Gesamthonorar\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Gesamtbetrag\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
]

NETTO_PATTERNS = [
    r"Nettobetrag\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)?",
    r"Summe\s+netto\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)?",
    r"Betrag\s+ohne\s+(?:MwSt|Mehrwertsteuer)\.?\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)?",
    r"Nettosumme\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)?",
    r"Netto\s+([\d.]+,\d{2})\s*(?:EUR|€)",
]

MWST_PATTERNS = [
    r"(?:zzgl\.|zuzüglich|inkl\.)\s+19\s*%\s+(?:MwSt|Mehrwertsteuer)[.\s:]*?([\d.]+,\d{2})",
    r"Mehrwertsteuer\s+19\s*%\s*[:\s]+([\d.]+,\d{2})",
    r"19\s*%\s+(?:MwSt|Mehrwertsteuer)\s*[:\s]+([\d.]+,\d{2})",
    r"USt\.\s+19\s*%\s*[:\s]+([\d.]+,\d{2})",
    r"MwSt\.\s+19\s*%\s*[:\s]+([\d.]+,\d{2})",
]


def _find_first_betrag(text, patterns):
    # type: (str, list) -> Optional[float]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            v = parse_betrag(m.group(1))
            if v is not None and v > 0:
                return v
    return None


def parse_rechnung(text):
    # type: (str) -> RechnungParseResult
    """
    Extrahiert Gesamtbetraege aus einem Rechnungs-Text.

    Fallback-Kette:
    1. Alle drei (brutto + netto + mwst) → Cross-Check (Toleranz 2 EUR)
    2. Brutto + netto → mwst = brutto - netto
    3. Brutto + mwst → netto = brutto - mwst
    4. Nur brutto → netto = brutto / 1.19
    5. Nur netto → brutto = netto * 1.19
    6. Kein Treffer → konfidenz 0.0
    """
    result = RechnungParseResult()

    brutto = _find_first_betrag(text, GESAMTBETRAG_PATTERNS)
    netto = _find_first_betrag(text, NETTO_PATTERNS)
    mwst = _find_first_betrag(text, MWST_PATTERNS)

    if brutto and netto and mwst:
        if abs((netto + mwst) - brutto) <= 2.0:
            result.nettobetrag = netto
            result.mwst_betrag = mwst
            result.bruttobetrag = brutto
            result.konfidenz = 0.95
        else:
            # Cross-Check fehlgeschlagen – trotzdem setzen, aber niedrigere Konfidenz
            result.bruttobetrag = brutto
            result.nettobetrag = netto
            result.mwst_betrag = mwst
            result.konfidenz = 0.60
            result.warnungen.append(
                "Plausibilitaetspruefung: Netto+MwSt (%.2f) weicht von Brutto (%.2f) ab." % (
                    netto + mwst, brutto)
            )
    elif brutto and netto:
        result.bruttobetrag = brutto
        result.nettobetrag = netto
        result.mwst_betrag = round(brutto - netto, 2)
        result.konfidenz = 0.90
    elif brutto and mwst:
        result.bruttobetrag = brutto
        result.mwst_betrag = mwst
        result.nettobetrag = round(brutto - mwst, 2)
        result.konfidenz = 0.85
    elif brutto:
        result.bruttobetrag = brutto
        result.nettobetrag = round(brutto / 1.19, 2)
        result.mwst_betrag = round(brutto - result.nettobetrag, 2)
        result.konfidenz = 0.65
        result.warnungen.append(
            "Nur Bruttobetrag gefunden – Netto aus Brutto/1.19 abgeleitet (19% MwSt angenommen)."
        )
    elif netto:
        result.nettobetrag = netto
        result.mwst_betrag = round(netto * 0.19, 2)
        result.bruttobetrag = round(netto * 1.19, 2)
        result.konfidenz = 0.65
        result.warnungen.append(
            "Nur Nettobetrag gefunden – Brutto aus Netto*1.19 abgeleitet (19% MwSt angenommen)."
        )
    else:
        result.konfidenz = 0.0
        result.warnungen.append("Kein Betrag erkannt – bitte manuell pruefen.")
        return result

    # Rechnungsdatum
    datum_patterns = [
        r"(?:Rechnungsdatum|Datum der Rechnung|Ausgestellt am|Datum)[:\s]+(\d{1,2}\.\d{2}\.\d{4})",
        r"\b(\d{1,2}\.\d{2}\.\d{4})\b",
    ]
    for dp in datum_patterns:
        dm = re.search(dp, text, re.IGNORECASE)
        if dm:
            raw = dm.group(1)
            mm = re.match(r"(\d{1,2})\.(\d{2})\.(\d{4})", raw)
            if mm:
                result.rechnungsdatum = "%s-%s-%s" % (
                    mm.group(3), mm.group(2), mm.group(1).zfill(2)
                )
                break

    # Rechnungsnummer
    nr_m = re.search(
        r"(?:Rechnungsnummer|Rechnungs-Nr\.?|Re\.?-Nr\.?|Rg\.?-Nr\.?)[:\s]+([A-Z0-9][A-Z0-9/\-\.]{2,25})",
        text, re.IGNORECASE
    )
    if nr_m:
        result.rechnungsnummer = nr_m.group(1).strip()

    return result
