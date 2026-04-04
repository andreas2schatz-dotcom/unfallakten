"""
Modul 4 – PDF-Extraktion
==========================
Roher Text und Strukturdaten aus PDFs lesen.
Verwendet pdfplumber (kein Netzwerk nötig, kein GPT-Fallback in Phase 1).

Architektur:
  extrahiere_pdf()     → Roher Text + Metadaten aus allen Seiten
  extrahiere_tabellen()→ Tabellendaten (für Gutachten mit Positionstabellen)
  validiere_pdf()      → Prüft ob Datei ein gültiges PDF ist

Hinweis zu OCR:
  Für gescannte PDFs (kein Textlayer) könnte OCR integriert werden.
  Erkennung: Text leer nach pdfplumber → PDF ist gescannt.
  In Phase 2 kann pytesseract oder GPT-4o Vision ergänzt werden.
"""

import io
import logging
import hashlib
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)

# ── Datenstrukturen ───────────────────────────────────────────────────────────

@dataclass
class SeitenExtraktion:
    """Text und Tabellen einer einzelnen PDF-Seite."""
    seite:      int
    text:       str
    woerter:    int
    tabellen:   list[list[list[str]]]  # tabellen[i][zeile][spalte]
    hat_text:   bool

@dataclass
class PDFExtraktion:
    """Vollständige Extraktion eines PDFs."""
    seiten_anzahl: int
    seiten:        list[SeitenExtraktion]
    gesamt_text:   str
    gesamt_woerter: int
    metadaten:     dict
    sha256:        str
    ist_gescannt:  bool   # True wenn kein Textlayer gefunden
    fehler:        Optional[str] = None


# ── Validierung ───────────────────────────────────────────────────────────────

def validiere_pdf(datei_bytes: bytes) -> tuple[bool, str]:
    """
    Prüft ob die Bytes ein gültiges PDF-Dokument darstellen.

    Returns:
        (True, "") bei Erfolg
        (False, Fehlermeldung) bei ungültigem PDF
    """
    if not datei_bytes:
        return False, "Leere Datei."

    # PDF-Signatur prüfen: erste 4 Bytes müssen %PDF sein
    if not datei_bytes[:4].startswith(b"%PDF"):
        return False, "Keine PDF-Signatur (%PDF...) gefunden."

    # Tatsächlich öffnen und Seiten zählen
    try:
        with pdfplumber.open(io.BytesIO(datei_bytes)) as pdf:
            n = len(pdf.pages)
            if n == 0:
                return False, "PDF hat keine Seiten."
    except Exception as e:
        return False, f"PDF kann nicht geöffnet werden: {e}"

    return True, ""


# ── Text-Extraktion ────────────────────────────────────────────────────────────

def extrahiere_pdf(datei_bytes: bytes,
                   max_seiten: int = 30) -> PDFExtraktion:
    """
    Extrahiert Text und Tabellen aus einem PDF.

    Args:
        datei_bytes: Rohes PDF als Bytes
        max_seiten:  Maximale Anzahl Seiten (verhindert Timeouts bei großen PDFs)

    Returns:
        PDFExtraktion mit vollständigem Text aller Seiten
    """
    sha = hashlib.sha256(datei_bytes).hexdigest()

    try:
        with pdfplumber.open(io.BytesIO(datei_bytes)) as pdf:
            meta = {}
            try:
                meta = dict(pdf.metadata or {})
            except Exception:
                pass

            seiten_list: list[SeitenExtraktion] = []
            texte: list[str] = []

            n_seiten = min(len(pdf.pages), max_seiten)
            for i, page in enumerate(pdf.pages[:n_seiten]):
                # Text extrahieren
                try:
                    text = page.extract_text(
                        x_tolerance=3,
                        y_tolerance=3,
                        layout=False,
                    ) or ""
                except Exception as e:
                    logger.warning("Seite %d: Textextraktion fehlgeschlagen: %s", i+1, e)
                    text = ""

                # Tabellen extrahieren (optional, für strukturierte Gutachten)
                tabellen = []
                try:
                    roh_tabellen = page.extract_tables()
                    for tab in (roh_tabellen or []):
                        # Leere Zellen normalisieren
                        saubere_tab = [
                            [str(zelle or "").strip() for zelle in zeile]
                            for zeile in tab
                            if any(z for z in zeile)
                        ]
                        if saubere_tab:
                            tabellen.append(saubere_tab)
                except Exception as e:
                    logger.debug("Seite %d: Tabellenextraktion übersprungen: %s", i+1, e)

                woerter = len(text.split()) if text else 0
                seite = SeitenExtraktion(
                    seite=i + 1,
                    text=text,
                    woerter=woerter,
                    tabellen=tabellen,
                    hat_text=woerter > 5,
                )
                seiten_list.append(seite)
                if text:
                    texte.append(text)

            gesamt_text   = "\n\n".join(texte)
            gesamt_woerter = sum(s.woerter for s in seiten_list)
            ist_gescannt   = gesamt_woerter < 20 and n_seiten > 0

            if ist_gescannt:
                logger.info("PDF scheint gescannt (nur %d Wörter auf %d Seiten).",
                            gesamt_woerter, n_seiten)

            return PDFExtraktion(
                seiten_anzahl=n_seiten,
                seiten=seiten_list,
                gesamt_text=gesamt_text,
                gesamt_woerter=gesamt_woerter,
                metadaten=meta,
                sha256=sha,
                ist_gescannt=ist_gescannt,
            )

    except Exception as e:
        logger.error("Kritischer Fehler bei PDF-Extraktion: %s", e)
        return PDFExtraktion(
            seiten_anzahl=0,
            seiten=[],
            gesamt_text="",
            gesamt_woerter=0,
            metadaten={},
            sha256=sha,
            ist_gescannt=False,
            fehler=str(e),
        )


def extrahiere_tabellen_als_dicts(extraktion: PDFExtraktion) -> list[dict]:
    """
    Wandelt rohe Tabellendaten in Dicts um.
    Erste Zeile jeder Tabelle wird als Spaltenkopf verwendet.

    Returns:
        Liste von Tabellen, jede Tabelle = Liste von Zeilen-Dicts
    """
    ergebnis = []
    for seite in extraktion.seiten:
        for tab in seite.tabellen:
            if len(tab) < 2:
                continue
            kopfzeile = tab[0]
            zeilen = []
            for zeile in tab[1:]:
                zeilen.append({
                    kopfzeile[j]: zeile[j] if j < len(zeile) else ""
                    for j in range(len(kopfzeile))
                })
            if zeilen:
                ergebnis.append({
                    "seite":  seite.seite,
                    "zeilen": zeilen,
                })
    return ergebnis
