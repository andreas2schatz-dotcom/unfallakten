"""
Verarbeitungs-Pipeline fuer intake_dokumente (S1.6a).

Der Textgewinnungs-Schritt:
  1. Laedt Arbeitskopie-PDF (arbeitskopie_pfad) vom Dokument.
  2. Ruft text_extraktion.extrahiere_seiten() -> pro Seite Text oder braucht_ocr.
  3. Fuer OCR-Seiten: pdf_zu_bildern + ocr_seite_mit_tsv (TSV je Seite unter
     ``uploads/artefakte/<sha256>/seite_<N>.tsv``). GLM-OCR-Aufruf hinter
     Feature-Flag ``GLM_OCR_ENABLED`` (F-01, Stufe-1-Uebergangszeit: default
     False -> Tesseract ist Primaerquelle).
  4. Stempelt textquelle, registry_version, llm_stack am Dokument.
  5. markiere_bereit() bei Erfolg, markiere_fehler() bei Exception.

Klassifikation/Extraktion sind bewusst NICHT hier -- das ist S1.6b.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import sys
from typing import Any, Dict

from ..db.database import get_connection
from ..intake.queue import markiere_bereit, markiere_fehler, reserviere_naechsten
from ..intake.registry_loader import lade_registry, standard_pfad
from ..intake.text_extraktion import (
    extrahiere_seiten, aggregierte_textquelle, SeitenText,
)
from ..services import ocr_service, glm_ocr_service

logger = logging.getLogger(__name__)


def _artefakte_root() -> str:
    """Verzeichnis fuer TSVs, Seitenbilder etc. Ueberschreibbar per Env."""
    return os.environ.get(
        "INTAKE_ARTEFAKTE_ROOT",
        os.path.join(os.path.dirname(__file__), "..", "..",
                     "uploads", "artefakte"),
    )


def _llm_stack_json() -> str:
    return json.dumps({
        "python": sys.version.split()[0],
        "os": platform.system(),
        "tesseract": bool(ocr_service.ocr_verfuegbar()),
        "glm_ocr_enabled": glm_ocr_service.ist_aktiviert(),
        "glm_ocr_model": os.environ.get("OCR_LLM_MODEL", ""),
        "text_llm_model": os.environ.get("LLM_MODEL", ""),
    }, ensure_ascii=False)


def _lade_dokument(intake_id: int) -> Dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, sha256, arbeitskopie_pfad, original_pfad "
            "FROM intake_dokumente WHERE id=?", (intake_id,)
        ).fetchone()
    if not row:
        raise RuntimeError(f"intake_dokument {intake_id} nicht gefunden")
    return dict(row)


def _ocr_seite(pdf_bytes: bytes, seite_nr: int, sha256: str) -> str:
    """OCR fuer eine einzelne Seite via Tesseract mit TSV-Persistierung.

    Optional: GLM-OCR wenn Feature-Flag gesetzt (dort dann kein TSV,
    weil die LLM-Antwort direkt Text ist).
    """
    tsv_verzeichnis = os.path.join(_artefakte_root(), sha256)
    tsv_pfad = os.path.join(tsv_verzeichnis, f"seite_{seite_nr}.tsv")

    bilder = ocr_service.pdf_zu_bildern(pdf_bytes)
    if not bilder or seite_nr - 1 >= len(bilder):
        return ""
    bild = bilder[seite_nr - 1]

    # GLM-OCR (Feature-Flag, F-01) — Stufe-1-Default False, Tesseract primaer.
    text_glm = glm_ocr_service.glm_ocr_seite(bild)
    if text_glm:
        return text_glm

    return ocr_service.ocr_seite_mit_tsv(bild, tsv_pfad, lang="deu")


def verarbeite_dokument(intake_id: int) -> bool:
    """Fuehrt den Textgewinnungs-Schritt aus. Liefert True bei Erfolg.

    Bei Exception: markiere_fehler() -> Backoff/Retry ueber die Queue.
    """
    try:
        dok = _lade_dokument(intake_id)
        arbeit = dok.get("arbeitskopie_pfad")
        if not arbeit or not os.path.isfile(arbeit):
            raise RuntimeError(
                f"Arbeitskopie fehlt: {arbeit}"
            )
        with open(arbeit, "rb") as f:
            pdf_bytes = f.read()

        seiten = extrahiere_seiten(pdf_bytes)
        if not seiten:
            raise RuntimeError("Keine Seiten extrahierbar")

        for s in seiten:
            if s.braucht_ocr:
                s.text = _ocr_seite(pdf_bytes, s.nr, dok["sha256"])
                s.textquelle = "ocr"
            # sonst: s.textquelle wurde bereits von extrahiere_seiten auf
            # 'textebene' gesetzt.

        text_gesamt = "\n\n".join(s.text for s in seiten if s.text)
        textquelle = aggregierte_textquelle(seiten)
        registry = lade_registry(standard_pfad())

        parse_json = json.dumps({
            "text_gesamt": text_gesamt,
            "seiten": [
                {"nr": s.nr, "textquelle": s.textquelle,
                 "ratio_salat": round(s.ratio_salat, 3),
                 "zeichen": len(s.text)}
                for s in seiten
            ],
        }, ensure_ascii=False)

        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET "
                "textquelle=?, registry_version=?, llm_stack=?, parse_json=? "
                "WHERE id=?",
                (textquelle, registry.version, _llm_stack_json(),
                 parse_json, intake_id),
            )
        markiere_bereit(intake_id)
        logger.info(
            "Dokument %s: Textgewinnung ok (%d Seiten, %s, %d Zeichen)",
            intake_id, len(seiten), textquelle, len(text_gesamt),
        )
        return True

    except Exception as exc:
        logger.error("verarbeite_dokument(%s) fehlgeschlagen: %s",
                     intake_id, exc, exc_info=True)
        markiere_fehler(intake_id, str(exc))
        return False


def _worker_id() -> str:
    """Eindeutige Worker-Kennung fuer das Lease (Hostname + PID)."""
    return f"{platform.node()}-{os.getpid()}"


def tick(lease_dauer_s: int = 300) -> bool:
    """Ein Verarbeitungs-Tick fuer den APScheduler-Job.

    Reserviert genau EIN Dokument (Single-Instance ueber das Lease, F-10) und
    verarbeitet es. Liefert True wenn ein Dokument verarbeitet wurde, False
    wenn die Queue leer war. Ausnahmen werden intern abgefangen -- der Job
    darf den Scheduler nicht abwuergen.
    """
    try:
        job = reserviere_naechsten(worker_id=_worker_id(),
                                   lease_dauer_s=lease_dauer_s)
        if not job:
            return False
        verarbeite_dokument(job["id"])
        return True
    except Exception as exc:
        logger.error("Pipeline-Tick fehlgeschlagen: %s", exc, exc_info=True)
        return False
