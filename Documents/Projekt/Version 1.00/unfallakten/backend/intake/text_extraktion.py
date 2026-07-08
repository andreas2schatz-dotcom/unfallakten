"""
Seitenweise Textgewinnung mit Zeichensalat-Check (S1.6a).

Fuer jede Seite eines PDF:
  * Textebene mit pdfplumber ziehen.
  * Zeichensalat-Ratio pruefen (Anteil "unerwarteter" Zeichen).
  * Wenn Ratio zu hoch ODER Wortzahl zu niedrig -> ``braucht_ocr=True``.

Der eigentliche OCR-Aufruf lebt im Pipeline-Schritt (S1.6a-6). Diese Modul
sagt nur: "diese Seite braucht OCR" bzw. "Textebene ist brauchbar".
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Schwellenwerte
MIN_WOERTER_TEXTEBENE = 5      # < 5 Woerter -> braucht OCR
MAX_ZEICHENSALAT_RATIO = 0.30  # > 30% "Rausch"-Zeichen -> braucht OCR

# Erlaubte Zeichen (DE-Texte, uebliche Interpunktion und Zahlen).
# Mehrzeilig, damit auch Whitespace/Zeilenumbrueche zaehlen.
_ERLAUBT_REGEX = re.compile(
    r"[A-Za-z0-9ÄÖÜäöüß"
    r" \t\r\n"
    r".,;:!?\-()\[\]{}\"'`´/#§€%&+*=<>@_"
    r"]"
)


@dataclass
class SeitenText:
    nr: int
    text: str
    braucht_ocr: bool
    ratio_salat: float
    textquelle: Optional[str] = None  # "textebene" | "ocr" - wird spaeter gesetzt


def zeichensalat_ratio(text: str) -> float:
    """Anteil der Zeichen, die NICHT ins erwartete deutsche Schrift-/Zahl-Alphabet fallen.

    Leerer Text -> 1.0 (maximaler Salat, weil unbrauchbar).
    """
    if not text:
        return 1.0
    gesamt = len(text)
    ok = len(_ERLAUBT_REGEX.findall(text))
    return 1.0 - (ok / gesamt)


def extrahiere_seiten(pdf_bytes: bytes, max_seiten: int = 30) -> List[SeitenText]:
    """Extrahiert die Textebene je Seite und entscheidet, ob OCR noetig ist.

    Bei fehlender/kaputter Textebene wird die Seite als ``braucht_ocr`` markiert;
    ``text`` bleibt leer. Der OCR-Aufruf passiert im Pipeline-Schritt.
    """
    import pdfplumber

    ergebnis: List[SeitenText] = []
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as exc:
        logger.error("PDF-Oeffnen fehlgeschlagen: %s", exc)
        return ergebnis

    try:
        n = min(len(pdf.pages), max_seiten)
        for i, page in enumerate(pdf.pages[:n]):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                logger.warning("Seite %d: Textextraktion Fehler: %s", i + 1, exc)
                text = ""

            woerter = len(text.split())
            ratio = zeichensalat_ratio(text)

            braucht_ocr = (woerter < MIN_WOERTER_TEXTEBENE or
                           ratio > MAX_ZEICHENSALAT_RATIO)

            ergebnis.append(SeitenText(
                nr=i + 1,
                text="" if braucht_ocr else text,
                braucht_ocr=braucht_ocr,
                ratio_salat=ratio,
                textquelle=None if braucht_ocr else "textebene",
            ))
    finally:
        pdf.close()
    return ergebnis


def aggregierte_textquelle(seiten: List[SeitenText]) -> str:
    """Aggregiert die Seiten-textquelle zu einem Dokument-Level-Stempel.

    * Alle 'textebene' -> 'textebene'
    * Alle 'ocr'       -> 'ocr'
    * Gemischt         -> 'gemischt'
    """
    if not seiten:
        return "textebene"
    quellen = {s.textquelle for s in seiten if s.textquelle}
    if len(quellen) == 1:
        return quellen.pop()
    return "gemischt"
