"""
Hilfsfunktionen für PDF-Textextraktion und -vorverarbeitung.
"""
import re
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
    Bereinigt PDF-Extraktionsartefakte:
    - Entfernt 'new_line' Artefakte (Allianz Direct)
    - Normalisiert Whitespace
    - Entfernt Seitenköpfe/-füße
    """
    # Allianz Direct: literal "new_line" im Text
    text = text.replace("new_line", "\n")

    # Mehrfache Leerzeichen normalisieren
    text = re.sub(r" {2,}", " ", text)

    # Seitenumbruch-Artefakte
    text = re.sub(r"\f", "\n", text)

    return text


def parse_betrag(betrag_str: str) -> Optional[float]:
    """
    Parst einen deutschen Geldbetragsstring zu float.
    Unterstützt: '1.234,56', '1234,56', '1,234.56', '1234.56'
    Ignoriert negative Vorzeichen (Abzüge werden separat behandelt).
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
    Sucht einen Geldbetrag in der Nähe eines Labels.
    Gibt den ersten gefundenen Betrag nach dem Label zurück.
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
    Findet alle Geldbeträge im Text mit ihrer Position.
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
