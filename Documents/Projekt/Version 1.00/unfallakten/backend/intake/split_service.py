"""
Aufteilen mehrseitiger Intake-PDFs entlang von Seitengrenzen (PDF-Splitting).

Reine PDF-Primitive (PyMuPDF) + Gruppen-Validierung; die Orchestrierung
(teile_dokument) folgt in Task 3. Schreibt ausschliesslich Intake-Tabellen,
nie Akten-Tabellen (INTAKE_REVIEW_PFLICHT bleibt gewahrt).
"""
from __future__ import annotations

import logging

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class SplitFehler(Exception):
    """Fachlicher Split-Fehler mit HTTP-Status (422 = ungueltig, 409 = Zustand)."""

    def __init__(self, meldung: str, status: int):
        super().__init__(meldung)
        self.status = status


def pdf_seiten_zahl(pdf_bytes: bytes) -> int:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.page_count


def extrahiere_seiten_pdf(pdf_bytes: bytes, von: int, bis: int) -> bytes:
    """Neues PDF mit den Seiten von..bis (1-basiert, inklusive)."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as src:
        neu = fitz.open()
        neu.insert_pdf(src, from_page=von - 1, to_page=bis - 1)
        out = neu.tobytes()
        neu.close()
    return out


def rendere_thumbnail(pdf_bytes: bytes, seite_nr: int, breite: int = 150) -> bytes:
    """PNG-Miniatur der Seite (1-basiert), skaliert auf ``breite`` px."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc.load_page(seite_nr - 1)
        zoom = breite / page.rect.width if page.rect.width else 1.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return pix.tobytes("png")


def validiere_gruppen(gruppen: list[list[int]], seiten_gesamt: int) -> None:
    """Gruppen muessen zusammenhaengend die Seiten 1..N lueckenlos, in
    Reihenfolge und ohne Ueberlappung abdecken; mindestens 2 Gruppen."""
    if not isinstance(gruppen, list) or len(gruppen) < 2:
        raise SplitFehler("Mindestens 2 Teile erforderlich.", 422)
    erwartet = 1
    for gruppe in gruppen:
        if not gruppe:
            raise SplitFehler("Leere Gruppe nicht erlaubt.", 422)
        for p in gruppe:
            if p != erwartet:
                raise SplitFehler(
                    "Teile muessen die Seiten 1..N lueckenlos und "
                    "zusammenhaengend abdecken.", 422)
            erwartet += 1
    if erwartet - 1 != seiten_gesamt:
        raise SplitFehler(
            f"Teile decken {erwartet - 1} Seiten ab, das PDF hat "
            f"{seiten_gesamt}.", 422)
