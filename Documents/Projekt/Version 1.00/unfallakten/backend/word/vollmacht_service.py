"""
Vollmacht-Generator
====================
Generiert eine aktenbezogene Vollmacht als PDF aus der Vorlage vollmacht.docx.

Ablauf:
  1. vollmacht_vorlage.docx → Platzhalter ersetzen → temp DOCX
  2. LibreOffice (headless) → temp DOCX → PDF
  3. PDF-Bytes zurückgeben

Platzhalter in der Vorlage:
  {{AKTENZEICHEN}}        → z.B. "242/26"
  {{AKTENKURZBEZEICHNUNG}}→ z.B. "Müller ./. R+V"
  {{AKTENLANGBEZEICHNUNG}}→ z.B. "Schadensersatz nach Verkehrsunfall vom 01.01.2026"
  {{DATUM}}               → z.B. "Offenbach, 18.03.2026"

Alle Platzhalter werden in fett + Arial ersetzt. Leere Werte → leerer String.
"""

import io
import os
import re
import logging
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime

logger = logging.getLogger(__name__)

# Pfad zur Vorlage – liegt im selben Verzeichnis wie dieses Modul
VORLAGE_PFAD = os.path.join(os.path.dirname(__file__), "vollmacht_vorlage.docx")

# LibreOffice-Pfade (Reihenfolge: Linux-Server, macOS, Windows)
SOFFICE_KANDIDATEN = [
    "soffice",
    "libreoffice",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/usr/local/bin/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


def _finde_soffice() -> str:
    """Gibt den ersten verfügbaren LibreOffice-Pfad zurück."""
    for kandidat in SOFFICE_KANDIDATEN:
        if shutil.which(kandidat) or os.path.exists(kandidat):
            return kandidat
    raise RuntimeError(
        "LibreOffice nicht gefunden. Bitte installieren: sudo apt install libreoffice"
    )


def _ersetze_platzhalter_in_xml(xml: str, werte: dict) -> str:
    """
    Ersetzt {{PLATZHALTER}} im document.xml mit fetter Arial-Formatierung.

    Strategie: XML in <w:r>-Runs aufteilen, jeden Run einzeln prüfen.
    Verhindert dass der Regex über Run-Grenzen hinweg matched.
    """
    def _verarbeite_run(run: str, platzhalter: str, wert: str) -> str:
        """Ersetzt Platzhalter in einem einzelnen <w:r>-Block."""
        ph = '{{' + platzhalter + '}}'
        if ph not in run:
            return run

        # rPr extrahieren und Bold ergänzen
        rpr_match = re.search(r'<w:rPr>(.*?)</w:rPr>', run, re.DOTALL)
        if rpr_match:
            rpr_inhalt = rpr_match.group(1)
            if '<w:b/>' not in rpr_inhalt and '<w:b ' not in rpr_inhalt:
                neues_rpr = f'<w:rPr>{rpr_inhalt}<w:b/><w:bCs/></w:rPr>'
                run = run.replace(rpr_match.group(0), neues_rpr, 1)
        else:
            # Kein rPr vorhanden – nach <w:r...> einfügen
            run = re.sub(
                r'(<w:r\b[^>]*>)',
                r'\1<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
                r'<w:b/><w:bCs/></w:rPr>',
                run, count=1
            )

        # xml:space="preserve" wenn Wert Leerzeichen enthält
        if wert and (' ' in wert or '\t' in wert):
            run = re.sub(r'<w:t>', '<w:t xml:space="preserve">', run)

        # Platzhalter ersetzen
        run = run.replace(ph, wert)
        return run

    # XML in Runs aufteilen, jeden verarbeiten, wieder zusammensetzen
    # Splitt-Muster: <w:r...>...</w:r> — jeder Run einzeln
    teile = re.split(r'(<w:r\b[^>]*>.*?</w:r>)', xml, flags=re.DOTALL)
    ergebnis = []
    for teil in teile:
        if teil.startswith('<w:r'):
            for platzhalter, wert in werte.items():
                teil = _verarbeite_run(teil, platzhalter, wert)
        ergebnis.append(teil)
    return ''.join(ergebnis)


def _repariere_wingdings_checkboxen(xml: str) -> str:
    """
    Wingdings 2 + £ (0xA3) = Checkbox-Symbol.
    LibreOffice kennt Wingdings 2 nicht → zeigt £.
    Fix: ersetze durch Unicode-Checkbox ☐ (U+2610) in Arial.
    """
    # Muster: <w:r> mit Wingdings 2 Schrift und £ als Text
    def _ersetze_run(m: re.Match) -> str:
        run = m.group(0)
        if '\xa3' not in run and '£' not in run:
            return run
        # Schrift auf Arial umstellen
        run = re.sub(
            r'w:ascii="Wingdings 2" w:hAnsi="Wingdings 2"(\s+w:cs="Wingdings 2")?',
            'w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"',
            run
        )
        # £ → ☐ (leere Checkbox U+2610)
        run = run.replace('\xa3', '\u2610').replace('£', '\u2610')
        # xml:space="preserve" für das <w:t>-Element
        run = re.sub(r'<w:t>', '<w:t xml:space="preserve">', run)
        return run

    return re.sub(r'<w:r\b[^>]*>.*?</w:r>', _ersetze_run, xml, flags=re.DOTALL)


def _docx_zu_pdf(docx_bytes: bytes) -> bytes:
    """
    Konvertiert DOCX-Bytes zu PDF-Bytes via LibreOffice.
    Nutzt ein temporäres Verzeichnis das nach der Konvertierung bereinigt wird.
    """
    soffice = _finde_soffice()
    tmpdir = tempfile.mkdtemp(prefix="vollmacht_")
    try:
        # DOCX in temp-Verzeichnis schreiben
        docx_pfad = os.path.join(tmpdir, "vollmacht.docx")
        with open(docx_pfad, "wb") as f:
            f.write(docx_bytes)

        # LibreOffice Konvertierung (headless, kein Display nötig)
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf",
             "--outdir", tmpdir, docx_pfad],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode != 0:
            logger.error("LibreOffice Fehler: %s", result.stderr)
            raise RuntimeError(f"LibreOffice Konvertierung fehlgeschlagen: {result.stderr}")

        pdf_pfad = os.path.join(tmpdir, "vollmacht.pdf")
        if not os.path.exists(pdf_pfad):
            raise RuntimeError(f"PDF wurde nicht erzeugt. LibreOffice stdout: {result.stdout}")

        with open(pdf_pfad, "rb") as f:
            return f.read()

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def generiere_vollmacht(
    aktenzeichen: str = "",
    kurz: str = "",
    lang: str = "",
    datum: str = "",
    vorlage_pfad: str = None,
    als_pdf: bool = True,
) -> bytes:
    """
    Generiert eine vollständige Vollmacht als PDF- oder DOCX-Bytes.

    Args:
        aktenzeichen: z.B. "242/26"
        kurz:         Aktenkurzbezeichnung
        lang:         Aktenlangbezeichnung
        datum:        z.B. "Offenbach, 18.03.2026" (wenn leer → heutiges Datum)
        vorlage_pfad: Pfad zur DOCX-Vorlage (default: vollmacht_vorlage.docx)
        als_pdf:      True = PDF zurückgeben (default), False = DOCX

    Returns:
        PDF- oder DOCX-Bytes, direkt als HTTP-Response sendbar
    """
    pfad = vorlage_pfad or VORLAGE_PFAD

    if not os.path.exists(pfad):
        raise FileNotFoundError(f"Vollmacht-Vorlage nicht gefunden: {pfad}")

    if not datum:
        heute = datetime.now()
        datum = heute.strftime('%d.%m.%Y')

    werte = {
        "AKTENZEICHEN":         aktenzeichen or "",
        "AKTENKURZBEZEICHNUNG": kurz         or "",
        "AKTENLANGBEZEICHNUNG": lang         or "",
        "DATUM":                datum,
    }

    # DOCX befüllen
    output = io.BytesIO()
    with zipfile.ZipFile(pfad, "r") as zin:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                daten = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    xml = daten.decode("utf-8")
                    xml = _repariere_wingdings_checkboxen(xml)
                    xml = _ersetze_platzhalter_in_xml(xml, werte)
                    daten = xml.encode("utf-8")
                zout.writestr(item, daten)

    docx_bytes = output.getvalue()

    if not als_pdf:
        return docx_bytes

    # DOCX → PDF
    return _docx_zu_pdf(docx_bytes)
