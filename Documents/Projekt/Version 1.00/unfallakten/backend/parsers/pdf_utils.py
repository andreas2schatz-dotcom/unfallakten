"""
Hilfsfunktionen fuer PDF-Textextraktion und -vorverarbeitung.
"""
import re
import unicodedata
import pdfplumber
from typing import Optional


def extract_text_from_pdf(pdf_path: str) -> tuple[str, list[str], bool]:
    """
    Extrahiert Text aus einer PDF-Datei.

    Returns:
        (full_text, page_texts, has_image_pages)
        - full_text: Gesamter Text aller Seiten
        - page_texts: Text je Seite
        - has_image_pages: True wenn mind. eine Seite nur als Bild vorliegt
    """
    page_texts = []
    has_image_pages = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            words = page.extract_words()
            images = page.images

            # Seite ist ein Bild wenn: kaum Text aber Bilder vorhanden
            if len(words) <= 2 and len(images) >= 1:
                has_image_pages = True
                page_texts.append("")  # Keine Textdaten
            else:
                page_texts.append(text)

    full_text = "\n".join(page_texts)
    return full_text, page_texts, has_image_pages


def normalize_text(text: str) -> str:
    """
    Bereinigt PDF-Extraktionsartefakte fuer Registry-Lookup, Classifier und Parser.

    Reihenfolge ist bewusst gewaehlt:
    1. Zeilenenden zuerst, damit nachfolgende Newline-Regeln konsistent greifen
    2. Allianz-Direct-Artefakt vor Unicode-Normalisierung
    3. NFKC loest Ligaturen auf (fi, fl, ff, ffi) - verbessert Registry-Trefferrate
    4. Unsichtbare Zeichen nach NFKC, da NFKC diese nicht entfernt
    5. Whitespace und Leerzeilen am Ende
    """
    # 1. Zeilenenden vereinheitlichen (\r\n und \r -> \n)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Allianz Direct: literal "new_line" im Text statt echtem Zeilenumbruch
    text = text.replace("new_line", "\n")

    # 3. Form-Feed-Zeichen (Seitenumbruch-Artefakt mancher PDF-Bibliotheken)
    text = text.replace("\f", "\n")

    # 4. Unicode-Normalisierung: Ligaturen aufloesen (fi, fl, ff, ffi)
    text = unicodedata.normalize("NFKC", text)

    # 5. Unsichtbare Zeichen - NFKC laesst diese unveraendert
    text = text.replace("\xad", "")           # Soft Hyphen
    text = text.replace(" ", " ")        # Non-breaking Space
    text = text.replace("\t", " ")            # Tab (Spalten-Layout)
    text = re.sub(r"[​‌‍﻿]", "", text)  # Zero-Width-Zeichen

    # 6. Mehrfache Leerzeichen -> ein Leerzeichen
    text = re.sub(r" {2,}", " ", text)

    # 7. Mehrfache Leerzeilen -> maximal zwei (Absatzstruktur fuer LLM erhalten)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def parse_betrag(betrag_str: str) -> Optional[float]:
    """
    Parst einen deutschen Geldbetragsstring zu float.
    Unterstuetzt: '1.234,56', '1234,56', '1,234.56', '1234.56'
    Ignoriert negative Vorzeichen (Abzuege werden separat behandelt).
    """
    if not betrag_str:
        return None

    s = betrag_str.strip().replace(" ", "").replace("EUR", "").replace("€", "").strip()

    # Minus-Vorzeichen merken
    negative = s.startswith("-")
    s = s.lstrip("-").strip()

    # Deutsches Format: 1.234,56
    if re.match(r"^\d{1,3}(\.\d{3})*,\d{2}$", s):
        s = s.replace(".", "").replace(",", ".")
    # Nur Komma: 1234,56
    elif re.match(r"^\d+,\d{2}$", s):
        s = s.replace(",", ".")
    # Punkt als Dezimaltrennzeichen: 1234.56
    elif re.match(r"^\d+\.\d{2}$", s):
        pass  # Bereits im richtigen Format
    # Ganzzahl ohne Dezimalen: 300, 30, 25 (Allianz Direct Kurzformat)
    elif re.match(r"^\d+$", s):
        s = s + ".0"
    else:
        return None

    try:
        value = float(s)
        return -value if negative else value
    except ValueError:
        return None


def find_betrag_near_label(text: str, label_pattern: str,
                            search_window: int = 150) -> Optional[float]:
    """
    Sucht einen Geldbetrag in der Naehe eines Labels.
    Gibt den ersten gefundenen Betrag nach dem Label zurueck.
    """
    betrag_re = re.compile(
        r"(-?\s*[\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*(?:EUR|€)?",
        re.IGNORECASE
    )
    label_match = re.search(label_pattern, text, re.IGNORECASE)
    if not label_match:
        return None

    window = text[label_match.start(): label_match.start() + search_window]
    betrag_match = betrag_re.search(window)
    if betrag_match:
        return parse_betrag(betrag_match.group(1))
    return None


def find_all_betraege(text: str) -> list[tuple[int, float]]:
    """
    Findet alle Geldbetraege im Text mit ihrer Position.
    Returns: Liste von (position, wert)
    """
    pattern = re.compile(
        r"(-?[\d]{1,3}(?:\.\d{3})*,\d{2})\s*(?:EUR|€)",
        re.IGNORECASE
    )
    results = []
    for m in pattern.finditer(text):
        val = parse_betrag(m.group(1))
        if val is not None:
            results.append((m.start(), val))
    return results
