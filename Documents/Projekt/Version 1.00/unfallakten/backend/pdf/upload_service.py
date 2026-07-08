"""
Modul 4 – Upload-Service
==========================
Orchestriert den kompletten Upload-Workflow:

  1. Datei empfangen & validieren (Typ, Größe)
  2. Sicher auf Disk speichern (zufälliger Dateiname)
  3. In Datenbank registrieren (parse_status = 'ausstehend')
  4. PDF-Extraktion + Parsing durchführen
  5. Parse-Ergebnis in DB speichern
  6. Optional: Schadenpositionen automatisch übernehmen

Sicherheit:
  - Dateigröße begrenzt (Standard: 20 MB)
  - Nur PDF/DOCX/JPG/PNG erlaubt (MIME-Typ + Erweiterung)
  - Dateinamen werden durch UUID ersetzt (keine Path-Traversal)
  - Upload-Verzeichnis konfigurierbar per Umgebungsvariable
"""

import os
import io
import uuid
import logging
import hashlib
import mimetypes
from pathlib import Path
from typing import Optional

from ..models.dokument import (
    registriere_dokument, aktualisiere_parse_status,
    hole_dokumente_by_akte, loesche_dokument, Dokument, GUELTIGE_TYPEN
)
from ..models.schaden import setze_schadenpositionen
from ..models.akte import hole_akte_by_id
from .extraktor import extrahiere_pdf, validiere_pdf
from .parser import extrahiere_schadenpositionen

logger = logging.getLogger(__name__)

# ── Konfiguration ─────────────────────────────────────────────────────────────

MAX_DATEIGROESSE = int(os.environ.get("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))  # 20 MB
ERLAUBTE_ERWEITERUNGEN = {".pdf", ".docx", ".jpg", ".jpeg", ".png"}
ERLAUBTE_MIME_TYPEN = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/jpeg",
    "image/png",
}
ERWEITERUNG_ZU_DATEITYP = {
    ".pdf":  "pdf",
    ".docx": "docx",
    ".jpg":  "jpg",
    ".jpeg": "jpg",
    ".png":  "png",
}

def _upload_verzeichnis() -> Path:
    """Gibt das Upload-Verzeichnis zurück (aus Env oder Default)."""
    default = Path(__file__).parent.parent / "uploads"
    pfad = Path(os.environ.get("UPLOAD_DIR", str(default)))
    pfad.mkdir(parents=True, exist_ok=True)
    return pfad


# ── Validierung ───────────────────────────────────────────────────────────────

class UploadFehler(Exception):
    """Wird bei ungültigen Uploads geworfen."""
    def __init__(self, nachricht: str, status_code: int = 422):
        self.nachricht = nachricht
        self.status_code = status_code
        super().__init__(nachricht)


def _validiere_datei(dateiname: str, datei_bytes: bytes):
    """
    Prüft Dateiname, Größe und Typ.
    Raises UploadFehler bei Problemen.
    """
    if not dateiname:
        raise UploadFehler("Kein Dateiname angegeben.")

    ext = Path(dateiname).suffix.lower()
    if ext not in ERLAUBTE_ERWEITERUNGEN:
        raise UploadFehler(
            f"Dateityp '{ext}' nicht erlaubt. "
            f"Erlaubt: {', '.join(sorted(ERLAUBTE_ERWEITERUNGEN))}"
        )

    if len(datei_bytes) == 0:
        raise UploadFehler("Leere Datei.")

    if len(datei_bytes) > MAX_DATEIGROESSE:
        mb = MAX_DATEIGROESSE // (1024 * 1024)
        raise UploadFehler(
            f"Datei zu groß ({len(datei_bytes) // (1024*1024)} MB). "
            f"Maximum: {mb} MB."
        )

    # PDF-Signatur prüfen
    if ext == ".pdf":
        gueltig, fehler = validiere_pdf(datei_bytes)
        if not gueltig:
            raise UploadFehler(f"Ungültiges PDF: {fehler}")


def _sicherer_dateiname(original: str) -> str:
    """Erstellt einen sicheren Dateinamen (UUID + Erweiterung)."""
    ext = Path(original).suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    return f"{uuid.uuid4().hex}{ext}"


# ── Haupt-Upload-Funktion ─────────────────────────────────────────────────────

def verarbeite_upload(
    akte_id:     int,
    dateiname:   str,
    datei_bytes: bytes,
    typ:         str,
    bearbeiter_id: Optional[int] = None,
    auto_schaden: bool = False,
    skip_parse: bool = False,
) -> dict:
    """
    Kompletter Upload-Workflow.

    Args:
        akte_id:      Ziel-Akte
        dateiname:    Originaler Dateiname (für Anzeige)
        datei_bytes:  Dateiinhalt
        typ:          Dokumenttyp (gutachten/abrechnungsschreiben/...)
        bearbeiter_id: Hochladender Benutzer
        auto_schaden: True → Schadenpositionen automatisch in Akte übernehmen
        skip_parse:   True → Internes Parsing überspringen (Dispatcher übernimmt)

    Returns:
        Dict mit Dokument-Info + Parse-Ergebnis

    Raises:
        UploadFehler bei Validierungsfehlern
    """
    # 1. Akte prüfen
    akte = hole_akte_by_id(akte_id)
    if not akte:
        raise UploadFehler(f"Akte {akte_id} nicht gefunden.", 404)

    # 2. Dokumenttyp prüfen
    if typ not in GUELTIGE_TYPEN:
        raise UploadFehler(
            f"Ungültiger Dokumenttyp '{typ}'. "
            f"Erlaubt: {', '.join(GUELTIGE_TYPEN)}"
        )

    # 3. Datei validieren
    _validiere_datei(dateiname, datei_bytes)

    # 4. Sicher speichern
    sicherer_name = _sicherer_dateiname(dateiname)
    ext = Path(dateiname).suffix.lower()
    dateityp = ERWEITERUNG_ZU_DATEITYP.get(ext, "pdf")

    upload_dir = _upload_verzeichnis()
    ziel_pfad = upload_dir / sicherer_name
    ziel_pfad.write_bytes(datei_bytes)
    logger.info("Datei gespeichert: %s (%d Bytes)", ziel_pfad, len(datei_bytes))

    # 5. In Datenbank registrieren
    dok = registriere_dokument(
        akte_id=akte_id,
        typ=typ,
        dateiname=dateiname,
        dateipfad=str(ziel_pfad),
        bearbeiter_id=bearbeiter_id,
        dateityp=dateityp,
        dateigroesse=len(datei_bytes),
    )

    # 6. PDF parsen (nur für PDF-Dateien, nur wenn Dispatcher nicht übernimmt)
    parse_ergebnis = None
    if dateityp == "pdf" and not skip_parse:
        parse_ergebnis = _parse_pdf(dok.id, datei_bytes)

        # 7. Auto-Übernahme der Schadenpositionen
        if auto_schaden and parse_ergebnis and parse_ergebnis.get("konfidenz", 0) >= 0.3:
            _uebernehme_schaden(akte_id, parse_ergebnis, bearbeiter_id, dateiname)

    return {
        "dokument":       _dok_dict(dok),
        "parse_ergebnis": parse_ergebnis,
    }


def _parse_pdf(dokument_id: int, datei_bytes: bytes) -> Optional[dict]:
    """Extrahiert und parst ein PDF, speichert Ergebnis in DB."""
    import json

    try:
        extraktion = extrahiere_pdf(datei_bytes)

        if extraktion.fehler:
            aktualisiere_parse_status(
                dokument_id,
                parse_status="fehler",
                parse_fehler=extraktion.fehler,
            )
            return None

        if extraktion.ist_gescannt:
            ergebnis_dict = {
                "ist_gescannt": True,
                "hinweis": "PDF hat keinen Textlayer (gescannt). "
                           "OCR erforderlich für automatische Extraktion.",
                "seiten_anzahl": extraktion.seiten_anzahl,
            }
            aktualisiere_parse_status(
                dokument_id,
                parse_status="fehler",
                parse_json=json.dumps(ergebnis_dict, ensure_ascii=False),
                parse_fehler="Gescanntes PDF – kein Textlayer.",
            )
            return ergebnis_dict

        # Schadenpositionen extrahieren
        parse_erg = extrahiere_schadenpositionen(extraktion.gesamt_text)
        erg_dict = parse_erg.als_dict()
        erg_dict["gesamt_text_laenge"] = len(extraktion.gesamt_text)
        erg_dict["seiten_anzahl"] = extraktion.seiten_anzahl
        erg_dict["sha256"] = extraktion.sha256

        status = "erfolgreich" if parse_erg.konfidenz >= 0.2 else "fehler"

        aktualisiere_parse_status(
            dokument_id,
            parse_status=status,
            parse_json=json.dumps(erg_dict, ensure_ascii=False, default=str),
            parse_konfidenz=parse_erg.konfidenz,
            parse_fehler=None if status == "erfolgreich" else
                         f"Zu wenige Felder gefunden (Konfidenz: {parse_erg.konfidenz})",
        )

        logger.info(
            "PDF geparst: Dokument %d, Konfidenz %.2f, "
            "Felder: %s, Typ: %s",
            dokument_id, parse_erg.konfidenz,
            parse_erg.felder_gefunden, parse_erg.dokumenttyp
        )
        return erg_dict

    except Exception as e:
        logger.error("PDF-Parsing Fehler für Dokument %d: %s", dokument_id, e)
        aktualisiere_parse_status(
            dokument_id,
            parse_status="fehler",
            parse_fehler=str(e),
        )
        return None


def _uebernehme_schaden(akte_id: int, parse_erg: dict,
                         bearbeiter_id: Optional[int], dateiname: str):
    """Übernimmt geparste Schadenpositionen in die Akte.

    S1.9c (BREAKING #2): Unter INTAKE_REVIEW_PFLICHT (Default True) laeuft
    die Auto-Uebernahme NICHT MEHR -- Schadenpositionen entstehen erst mit
    der Review-Freigabe (S1.8) und ihrer Ereignis-Bestaetigung (P1.5).
    Alt-Pfad bleibt bei INTAKE_REVIEW_PFLICHT=false aktiv.
    """
    from ..intake.feature_flags import review_pflicht_aktiv
    if review_pflicht_aktiv():
        logger.debug(
            "Auto-Uebernahme Schadenpositionen uebersprungen "
            "(INTAKE_REVIEW_PFLICHT aktiv, Akte %s)", akte_id,
        )
        return

    felder = {
        "reparaturkosten", "wiederbeschaffung", "restwert",
        "wertminderung", "nutzungsausfall", "mietwagenkosten",
        "sv_kosten", "abschleppkosten", "standkosten",
        "anabmeldekosten", "schmerzensgeld", "sonstiges"
    }
    positionen = {
        k: v for k, v in parse_erg.items()
        if k in felder and v is not None
    }
    if positionen:
        positionen["quelle"] = "gutachten_pdf"
        positionen["bearbeiter_id"] = bearbeiter_id
        try:
            setze_schadenpositionen(akte_id=akte_id, **positionen)
            logger.info("Schadenpositionen automatisch übernommen für Akte %d", akte_id)
        except Exception as e:
            logger.warning("Auto-Übernahme fehlgeschlagen: %s", e)


# ── Dokument-Verwaltung ───────────────────────────────────────────────────────

def hole_dokument_datei(dokument_id: int) -> Optional[tuple[bytes, str, str]]:
    """
    Liest eine Datei vom Disk.

    Returns:
        (bytes, dateiname, dateityp) oder None wenn nicht gefunden
    """
    from ..db.database import get_connection
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dokumente WHERE id = ?", (dokument_id,)
        ).fetchone()

    if not row:
        return None

    pfad = Path(row["dateipfad"])
    if not pfad.exists():
        logger.warning("Datei nicht gefunden: %s", pfad)
        return None

    return pfad.read_bytes(), row["dateiname"], row["dateityp"]


def loesche_dokument_mit_datei(dokument_id: int) -> bool:
    """Löscht Datei vom Disk UND Datenbankeintra."""
    from ..db.database import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT dateipfad FROM dokumente WHERE id = ?", (dokument_id,)
        ).fetchone()

    if not row:
        return False

    # Datei löschen
    pfad = Path(row["dateipfad"])
    if pfad.exists():
        try:
            pfad.unlink()
            logger.info("Datei gelöscht: %s", pfad)
        except OSError as e:
            logger.warning("Datei konnte nicht gelöscht werden: %s", e)

    return loesche_dokument(dokument_id)


def korrigiere_parse_ergebnis(dokument_id: int, korrigiert: dict) -> Optional[Dokument]:
    """
    Speichert ein manuell korrigiertes Parse-Ergebnis.
    Setzt parse_status auf 'manuell_korrigiert'.
    """
    import json
    return aktualisiere_parse_status(
        dokument_id,
        parse_status="manuell_korrigiert",
        parse_json=json.dumps(korrigiert, ensure_ascii=False, default=str),
        parse_konfidenz=1.0,  # Manuelle Korrektur = 100% Vertrauen
    )


def _dok_dict(dok: Dokument) -> dict:
    return {
        "id":               dok.id,
        "akte_id":          dok.akte_id,
        "typ":              dok.typ,
        "dokumentenklasse": getattr(dok, "dokumentenklasse", None),
        "dateiname":        dok.dateiname,
        "dateityp":         dok.dateityp,
        "dateigroesse":     dok.dateigroesse,
        "hochgeladen_am":   dok.hochgeladen_am,
        "parse_status":     dok.parse_status,
        "parse_konfidenz":  dok.parse_konfidenz,
        "notizen":          dok.notizen,
        "eakte_nr":         getattr(dok, "eakte_nr", None),
        "eakte_pfad":       getattr(dok, "eakte_pfad", None),
        "quelle":           getattr(dok, "quelle", "upload"),
    }


def starte_pdf_parsing(dokument_id: int, akte_id: int,
                       absender_domain: Optional[str] = None) -> Optional[dict]:
    """
    Startet das PDF-Parsing für ein bereits registriertes Dokument.
    Wird vom E-Mail-Import-Service aufgerufen.
    Nutzt den Dispatcher (Pipeline Phase 2) statt den alten _parse_pdf().

    Args:
        dokument_id: ID des Dokuments in der DB
        akte_id:     Zugehörige Akte (az TEXT)
        absender_domain: E-Mail-Domain des Absenders (optional, verbessert Klassifikation)

    Returns:
        Dispatch-Ergebnis als Dict oder None bei Fehler
    """
    from ..db.database import get_connection

    with get_connection() as conn:
        row = conn.execute(
            "SELECT dateipfad, dateityp FROM dokumente WHERE id = ?",
            (dokument_id,)
        ).fetchone()

    if not row:
        logger.warning("Dokument %d nicht gefunden.", dokument_id)
        return None

    if row["dateityp"] != "pdf":
        return None

    dateipfad = row["dateipfad"]
    if not Path(dateipfad).exists():
        logger.warning("Datei %s nicht lesbar.", dateipfad)
        return None

    try:
        from ..workflow.dispatcher import dispatch_dokument
        return dispatch_dokument(
            dok_id=dokument_id,
            akte_az=str(akte_id),
            dateipfad=dateipfad,
            absender_domain=absender_domain,
        )
    except Exception as e:
        logger.error("Dispatcher-Fehler fuer Dokument %d: %s", dokument_id, e)
        # Fallback auf alten Parser falls Dispatcher nicht verfuegbar
        try:
            datei_bytes = Path(dateipfad).read_bytes()
            return _parse_pdf(dokument_id, datei_bytes)
        except Exception as e2:
            logger.error("Auch Fallback-Parser fehlgeschlagen: %s", e2)
            return None
