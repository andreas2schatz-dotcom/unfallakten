"""
S1.2 - Original-Archiv (unveraenderlich) + Normalisierung auf Arbeitskopie.

Entwurfsregeln aus PIPELINE-REFACTORING-PLAN.md und v7-Zielarchitektur:

* Original hash-adressiert unter ``<root>/originale/<sha[:2]>/<sha>.<ext>``.
  Konvention: **write-once** — existiert die Datei, wird sie nie geschrieben.
* Arbeitskopie ist immer ein PDF unter ``<root>/arbeitskopien/<sha[:2]>/<sha>.pdf``:
    - PDF-Eingang  -> reine Kopie
    - DOCX-Eingang -> LibreOffice-headless (identisch zum word_service-Muster)
    - JPG/PNG      -> PyMuPDF baut single-page PDF um das Bild
    - HEIC         -> ``NotImplementedError`` (bewusst vertagt bis Bedarf belegt)
* Kein bestehender Aufrufer wird umgestellt (S1.2 legt nur das Modul an; die
  Adapter aus S1.3 werden es dann verwenden).

Der Wurzelpfad wird ueber ``INTAKE_ARCHIV_ROOT`` (Env-Var) oder als
Default ``uploads/`` unterhalb des Projekt-Roots ermittelt.
"""
from __future__ import annotations

import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# LibreOffice-Pfade in derselben Reihenfolge wie in ``word/vollmacht_service.py``.
_SOFFICE_KANDIDATEN = (
    "soffice",
    "libreoffice",
    "/usr/bin/soffice",
    "/usr/bin/libreoffice",
    "/usr/local/bin/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
)


def _archiv_root() -> Path:
    """
    Wurzel fuer originale/ und arbeitskopien/. Konfigurierbar per
    ``INTAKE_ARCHIV_ROOT`` (fuer Tests), sonst ``uploads/`` (relativ zum
    backend/).
    """
    aus_env = os.environ.get("INTAKE_ARCHIV_ROOT")
    if aus_env:
        return Path(aus_env)
    # Default: <repo>/backend/uploads/ (analog zum bestehenden UPLOAD_DIR-Muster
    # in email_import/import_service.py).
    return Path(__file__).parent.parent / "uploads"


def _ziel_original(sha: str, ext: str) -> Path:
    ext = (ext or "").lstrip(".").lower()
    return _archiv_root() / "originale" / sha[:2] / f"{sha}.{ext}"


def _ziel_arbeitskopie(sha: str) -> Path:
    return _archiv_root() / "arbeitskopien" / sha[:2] / f"{sha}.pdf"


def _finde_soffice() -> str:
    for kandidat in _SOFFICE_KANDIDATEN:
        if shutil.which(kandidat) or os.path.exists(kandidat):
            return kandidat
    raise RuntimeError(
        "LibreOffice nicht gefunden. Bitte 'libreoffice-writer' installieren "
        "(im Docker-Image bereits vorhanden)."
    )


def lege_original_ab(daten: bytes, ext: str) -> str:
    """
    Legt ``daten`` hash-adressiert ab und gibt den absoluten Pfad zurueck.

    Write-once: existiert die Zieldatei (weil Hash bereits einmal geschrieben),
    wird sie NICHT ueberschrieben. Der Aufrufer erhaelt in beiden Faellen den
    gleichen Pfad. Rueckgabe ist der absolute Pfad als String.
    """
    if not isinstance(daten, (bytes, bytearray)):
        raise TypeError("lege_original_ab erwartet bytes")
    sha = hashlib.sha256(daten).hexdigest()
    ziel = _ziel_original(sha, ext)

    if ziel.exists():
        # Write-once — kein Ueberschreiben. Wir liefern lediglich den Pfad zurueck.
        logger.debug("Original %s existiert bereits, no-op.", sha)
        return str(ziel)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    # Atomar schreiben: temp im gleichen Verzeichnis, dann rename. Verhindert
    # halbfertige Dateien bei Absturz.
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=f".{ext.lstrip('.').lower()}",
                               dir=str(ziel.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(daten)
        os.replace(tmp, ziel)
    except Exception:
        # Aufraeumen, falls Rename scheiterte.
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise

    return str(ziel)


def _erzeuge_pdf_kopie(original_pfad: Path, ziel: Path) -> None:
    """PDF-Eingang: reine Byte-Kopie in die Arbeitskopie."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(original_pfad), str(ziel))


def _erzeuge_pdf_aus_bild(original_pfad: Path, ziel: Path) -> None:
    """JPG/PNG -> single-page PDF via PyMuPDF."""
    import fitz  # PyMuPDF
    ziel.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(str(original_pfad)) as bild_doc:
        pdf_bytes = bild_doc.convert_to_pdf()
    # In temp+rename schreiben.
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".pdf", dir=str(ziel.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pdf_bytes)
        os.replace(tmp, ziel)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _erzeuge_pdf_aus_docx(original_pfad: Path, ziel: Path) -> None:
    """DOCX -> PDF via LibreOffice-headless (Muster aus word/vollmacht_service.py)."""
    soffice = _finde_soffice()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="intake_docx_")
    try:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf",
             "--outdir", tmpdir, str(original_pfad)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice DOCX->PDF fehlgeschlagen: {result.stderr}"
            )
        # LibreOffice benennt die Ausgabe wie den Input, mit .pdf-Endung.
        base = original_pfad.stem
        erzeugt = Path(tmpdir) / f"{base}.pdf"
        if not erzeugt.exists():
            raise RuntimeError(
                f"LibreOffice hat keine PDF-Ausgabe erzeugt. stdout: {result.stdout}"
            )
        shutil.copy2(str(erzeugt), str(ziel))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# Ordnet Quell-Extensions den passenden Konvertern zu. Alles was im Intake
# real vorkommen kann muss hier gelistet sein.
_KONVERTER = {
    "pdf": _erzeuge_pdf_kopie,
    "jpg": _erzeuge_pdf_aus_bild,
    "jpeg": _erzeuge_pdf_aus_bild,
    "png": _erzeuge_pdf_aus_bild,
    "docx": _erzeuge_pdf_aus_docx,
    "doc": _erzeuge_pdf_aus_docx,  # LibreOffice liest auch alte .doc-Dateien
}


def erzeuge_arbeitskopie(original_pfad: str, quell_ext: str) -> str:
    """
    Erzeugt aus dem Original eine PDF-Arbeitskopie und gibt deren Pfad zurueck.

    Idempotent: existiert die Arbeitskopie bereits (gleicher Hash), wird sie
    NICHT neu erzeugt.
    Verletzt niemals das Original — der Aufrufer garantiert nur den Pfad,
    die Bytes des Originals bleiben unveraendert (Konvention).
    """
    quell_ext = (quell_ext or "").lstrip(".").lower()
    pfad = Path(original_pfad)
    if not pfad.is_file():
        raise FileNotFoundError(f"Originaldatei nicht gefunden: {original_pfad}")

    # Der sha256 ist der Dateiname des Originals: <root>/originale/<xx>/<sha>.<ext>
    sha = pfad.stem
    ziel = _ziel_arbeitskopie(sha)

    if ziel.exists():
        return str(ziel)

    if quell_ext == "heic":
        raise NotImplementedError(
            "HEIC-Normalisierung ist vertagt (S1.2 v7). Aktivieren, sobald Bedarf belegt."
        )

    konverter = _KONVERTER.get(quell_ext)
    if konverter is None:
        raise ValueError(f"Kein Konverter fuer Extension '{quell_ext}' bekannt")

    konverter(pfad, ziel)
    return str(ziel)
