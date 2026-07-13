"""
OCR-Service (PRD-30)
=====================
Lokale Texterkennung für gescannte PDFs via Tesseract + pdf2image.

- Kein Cloud-Dienst, vollständig lokal → DSGVO-konform
- Deutsch als Standardsprache (tesseract-ocr-deu)
- DPI 300 für A4-Briefe (Regelfall bei Versicherungspost)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# OCR-Bibliotheken sind optional – bei fehlendem Tesseract graceful degradieren
_ocr_verfuegbar: Optional[bool] = None  # None = noch nicht geprüft


def _pruefeVerfuegbarkeit() -> bool:
    global _ocr_verfuegbar
    if _ocr_verfuegbar is not None:
        return _ocr_verfuegbar
    try:
        import pytesseract
        import pdf2image  # noqa: F401
        pytesseract.get_tesseract_version()
        _ocr_verfuegbar = True
        logger.info("Tesseract OCR verfügbar: %s", pytesseract.get_tesseract_version())
    except Exception as e:
        _ocr_verfuegbar = False
        logger.warning("Tesseract OCR nicht verfügbar (%s) – OCR deaktiviert.", e)
    return _ocr_verfuegbar


def ist_bild_pdf(has_image_pages: bool, text_laenge: int) -> bool:
    """
    True wenn das PDF OCR benötigt.

    Kriterien:
    - pdfplumber hat Bildseiten erkannt (has_image_pages), ODER
    - weniger als 50 Zeichen extrahiert (quasi leer)
    """
    return has_image_pages or text_laenge < 50


def ocr_text(pdf_bytes: bytes, lang: str = "deu", dpi: int = 300) -> str:
    """
    Konvertiert Bild-PDF-Seiten zu Text via Tesseract.

    Args:
        pdf_bytes: Rohbytes der PDF-Datei
        lang:      Tesseract-Sprachkürzel (Standard: 'deu')
        dpi:       Auflösung für Bildkonvertierung (Standard: 300)

    Returns:
        Erkannter Text aller Seiten, Seiten durch Doppelnewline getrennt.
        Leerer String wenn OCR nicht verfügbar oder Fehler.
    """
    if not _pruefeVerfuegbarkeit():
        logger.error("OCR-Anfrage, aber Tesseract nicht verfügbar.")
        return ""

    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as e:
        logger.error("OCR-Import fehlgeschlagen: %s", e)
        return ""

    try:
        images = convert_from_bytes(pdf_bytes, dpi=dpi)
    except Exception as e:
        logger.error("PDF→Bild-Konvertierung fehlgeschlagen: %s", e)
        return ""

    seiten = []
    for i, img in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(img, lang=lang)
            seiten.append(text)
            logger.debug("OCR Seite %d/%d: %d Zeichen erkannt.", i, len(images), len(text))
        except Exception as e:
            logger.warning("OCR Seite %d fehlgeschlagen: %s", i, e)
            seiten.append("")

    ergebnis = "\n\n".join(seiten)
    logger.info(
        "OCR abgeschlossen: %d Seiten, %d Zeichen gesamt.",
        len(images), len(ergebnis),
    )
    return ergebnis


def ocr_verfuegbar() -> bool:
    """Gibt True zurück wenn Tesseract einsatzbereit ist."""
    return _pruefeVerfuegbarkeit()


# ══════════════════════════════════════════════════════════════════════════════
# S1.6a: image_to_data + TSV-Persistierung
# ══════════════════════════════════════════════════════════════════════════════

def pdf_zu_bildern(pdf_bytes: bytes, dpi: int = 300,
                   first_page: int | None = None,
                   last_page: int | None = None) -> list:
    """PDF-Seiten -> PIL-Images (fuer die per-Seite-OCR-Pipeline S1.6a).

    ``first_page``/``last_page`` grenzen die zu rendernden Seiten ein
    (BUG-12): die per-Seite-OCR ruft die Funktion mit
    ``first_page=last_page=N`` auf, damit nur DIESE Seite gerendert wird
    statt des ganzen PDFs pro Seite (O(n) statt O(n^2)).

    Rueckgabe: leere Liste bei Fehler oder nicht verfuegbarem pdf2image.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        logger.warning("pdf2image nicht verfuegbar - keine Bild-Konvertierung.")
        return []
    try:
        return convert_from_bytes(pdf_bytes, dpi=dpi,
                                  first_page=first_page, last_page=last_page)
    except Exception as e:
        logger.error("PDF->Bild-Konvertierung fehlgeschlagen: %s", e)
        return []


def ocr_seite_mit_tsv(bild, tsv_ziel_pfad: str, lang: str = "deu") -> str:
    """OCR einer einzelnen Seite mit TSV-Persistierung.

    Ruft ``pytesseract.image_to_data(output_type=TSV)`` auf, schreibt das TSV
    unter ``tsv_ziel_pfad`` und liefert den erkannten Text (Konkatenation der
    'text'-Spalte, ohne Confidence-Filter).

    Ohne Tesseract-Verfuegbarkeit: leerer String, kein TSV.
    """
    if not _pruefeVerfuegbarkeit():
        return ""
    try:
        import pytesseract
    except ImportError:
        return ""

    try:
        tsv = pytesseract.image_to_data(
            bild, lang=lang, output_type=pytesseract.Output.STRING
        )
    except AttributeError:
        # Fallback fuer aeltere pytesseract-Versionen: Output.STRING kann fehlen
        tsv = pytesseract.image_to_data(bild, lang=lang)
    except Exception as e:
        logger.error("image_to_data fehlgeschlagen: %s", e)
        return ""

    # TSV persistieren
    os.makedirs(os.path.dirname(tsv_ziel_pfad), exist_ok=True)
    with open(tsv_ziel_pfad, "w", encoding="utf-8") as f:
        f.write(tsv)

    # Text aus TSV extrahieren: letzte Spalte 'text' der data-Zeilen
    zeilen = tsv.strip().splitlines()
    if not zeilen:
        return ""
    kopf = zeilen[0].split("\t")
    try:
        text_idx = kopf.index("text")
    except ValueError:
        return ""
    woerter = []
    for z in zeilen[1:]:
        spalten = z.split("\t")
        if len(spalten) > text_idx:
            w = spalten[text_idx].strip()
            if w:
                woerter.append(w)
    return " ".join(woerter)
