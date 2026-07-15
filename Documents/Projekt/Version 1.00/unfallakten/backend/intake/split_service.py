"""
Aufteilen mehrseitiger Intake-PDFs entlang von Seitengrenzen (PDF-Splitting).

PDF-Primitive (PyMuPDF) + Gruppen-Validierung + Orchestrierung
(teile_dokument). Schreibt ausschliesslich Intake-Tabellen,
nie Akten-Tabellen (INTAKE_REVIEW_PFLICHT bleibt gewahrt).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import fitz  # PyMuPDF

from ..db.database import get_connection
from ._persistenz import oder_intake_dokument_fuer_datei, erzeuge_zustellung

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


def teile_dokument(intake_id: int, gruppen: list[list[int]],
                    benutzer_id: int | None) -> list[int]:
    """Zerlegt das Arbeitskopie-PDF in die angegebenen Seitengruppen.

    Legt je Gruppe ein neues Intake-Dokument (queue_status='neu', der Worker
    klassifiziert automatisch) mit vererbter Zustellung an und markiert das
    Original zuletzt als 'aufgeteilt'. Bricht ein Schritt vorher ab, bleibt das
    Original reviewbar; Teile sind per sha256 idempotent.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM intake_dokumente WHERE id=?", (intake_id,)).fetchone()
    if not row:
        raise SplitFehler("Intake-Dokument nicht gefunden.", 404)
    dok = dict(row)

    if dok.get("payload_typ") != "datei":
        raise SplitFehler("Nur Datei-Dokumente koennen aufgeteilt werden.", 422)
    if dok.get("verworfen_am"):
        raise SplitFehler(
            "Dokument ist verworfen/aufgeteilt und kann nicht aufgeteilt "
            "werden.", 409)
    if dok.get("queue_status") not in ("bereit_zur_review", "pipeline_fehler", "neu"):
        raise SplitFehler(
            f"Dokument im Status {dok.get('queue_status')!r} kann nicht "
            f"aufgeteilt werden.", 409)

    pfad = dok.get("arbeitskopie_pfad")
    if not pfad or not os.path.isfile(pfad):
        raise SplitFehler("Arbeitskopie fehlt.", 422)
    with open(pfad, "rb") as f:
        pdf_bytes = f.read()

    seiten_gesamt = pdf_seiten_zahl(pdf_bytes)
    if seiten_gesamt < 2:
        raise SplitFehler("Dokument hat weniger als 2 Seiten.", 422)
    validiere_gruppen(gruppen, seiten_gesamt)

    with get_connection() as conn:
        zust = conn.execute(
            "SELECT quelle, absender, betreff, empfangen_am, signale_json, konto "
            "FROM zustellungen WHERE intake_dokument_id=? ORDER BY id ASC LIMIT 1",
            (intake_id,)).fetchone()
    quelle = (zust["quelle"] if zust else None) or "upload"
    absender = zust["absender"] if zust else None
    betreff = zust["betreff"] if zust else None
    empfangen_am = zust["empfangen_am"] if zust else None
    konto = zust["konto"] if zust else None
    signale = json.loads(zust["signale_json"]) if (zust and zust["signale_json"]) else None

    kinder: list[int] = []
    for gruppe in gruppen:
        teil_bytes = extrahiere_seiten_pdf(pdf_bytes, gruppe[0], gruppe[-1])
        kind_id, _sha = oder_intake_dokument_fuer_datei(teil_bytes, "pdf")
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET aufgeteilt_aus_id=? WHERE id=?",
                (intake_id, kind_id))
        erzeuge_zustellung(
            kind_id, quelle, absender=absender, betreff=betreff,
            empfangen_am=empfangen_am, signale=signale, konto=konto,
            roh_referenz=f"split:{intake_id}")
        kinder.append(kind_id)

    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente "
            "SET verworfen_grund='aufgeteilt', verworfen_am=?, verworfen_von=? "
            "WHERE id=?",
            (jetzt, benutzer_id, intake_id))
    return kinder
