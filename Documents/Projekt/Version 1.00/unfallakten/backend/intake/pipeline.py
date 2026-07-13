"""
Verarbeitungs-Pipeline fuer intake_dokumente (S1.6a + S1.6b + S1.7).

Ablauf pro Dokument:
  1. Laedt Arbeitskopie-PDF (arbeitskopie_pfad) vom Dokument.
  2. Ruft text_extraktion.extrahiere_seiten() -> pro Seite Text oder braucht_ocr.
  3. Fuer OCR-Seiten: pdf_zu_bildern + ocr_seite_mit_tsv (TSV je Seite unter
     ``uploads/artefakte/<sha256>/seite_<N>.tsv``). GLM-OCR-Aufruf hinter
     Feature-Flag ``GLM_OCR_ENABLED`` (F-01, Stufe-1-Uebergangszeit: default
     False -> Tesseract ist Primaerquelle).
  4. Klassifikation (S1.6b):
     - Stufe 1 (Regeln): YAML-Marker + VEREINIGTE Zustellungs-Signale.
     - Stufe 2 (LLM):    Qwen closed-label (Seite 1 + letzte Seite gekuerzt).
  5. Feld-Extraktion (S1.6b): Regex-Anker + LLM-Schema-Extraktion.
  6. Akten-Matching (S1.7): Kandidatenliste mit Score gegen SQLite +
     RA-Micro (read-only). KEIN Auto-Zuordnen von ``akte_az`` -- die
     Kandidaten landen in ``parse_json.akten_kandidaten``, die Review-
     Freigabe (S1.8) waehlt eine aus.
  7. Stempelt klasse, klasse_quelle='auto', konfidenz, textquelle,
     registry_version, llm_stack, parse_json am Dokument.
  8. markiere_bereit() bei Erfolg, markiere_fehler() bei Exception.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import sys
from typing import Any, Dict

from ..db.database import get_connection
from ..intake.akten_matching import finde_kandidaten
from ..intake.extraktion import extrahiere_felder
from ..intake.klassifikator import (
    Kandidat, klassifiziere_stufe1, klassifiziere_stufe2,
)
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
            "SELECT id, sha256, arbeitskopie_pfad, original_pfad, "
            "       payload_typ, structured_payload, "
            "       klasse, klasse_quelle, konfidenz "
            "FROM intake_dokumente WHERE id=?", (intake_id,)
        ).fetchone()
    if not row:
        raise RuntimeError(f"intake_dokument {intake_id} nicht gefunden")
    return dict(row)


def _lade_zustellungs_signale(intake_id: int) -> list:
    """Sammelt VEREINIGTE Zustellungs-Signale (K-P3).

    Jede Zustellung kann ein ``signale_json``-Dict tragen (aus dem
    Adapter-Layer bzw. der Absender-Registry S1.4). Diese Signale liefern
    Stufe 1 Klassen-KANDIDATEN -- nie eindeutige Zuordnungen.
    """
    signale: list = []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT signale_json FROM zustellungen "
            "WHERE intake_dokument_id=?", (intake_id,)
        ).fetchall()
    for row in rows:
        rohtext = row["signale_json"] if row else None
        if not rohtext:
            continue
        try:
            data = json.loads(rohtext)
        except (TypeError, ValueError):
            continue
        if isinstance(data, dict):
            signale.append(data)
        elif isinstance(data, list):
            signale.extend(x for x in data if isinstance(x, dict))
    return signale


def _ocr_seite(pdf_bytes: bytes, seite_nr: int, sha256: str) -> str:
    """OCR fuer eine einzelne Seite via Tesseract mit TSV-Persistierung.

    Optional: GLM-OCR wenn Feature-Flag gesetzt (dort dann kein TSV,
    weil die LLM-Antwort direkt Text ist).
    """
    tsv_verzeichnis = os.path.join(_artefakte_root(), sha256)
    tsv_pfad = os.path.join(tsv_verzeichnis, f"seite_{seite_nr}.tsv")

    # BUG-12: nur DIESE Seite rendern (first_page/last_page), nicht das ganze
    # PDF pro Seite -- sonst O(n^2) Renderings (30 Seiten -> 900 statt 30).
    bilder = ocr_service.pdf_zu_bildern(
        pdf_bytes, first_page=seite_nr, last_page=seite_nr)
    if not bilder:
        return ""
    bild = bilder[0]

    # GLM-OCR (Feature-Flag, F-01) — Stufe-1-Default False, Tesseract primaer.
    text_glm = glm_ocr_service.glm_ocr_seite(bild)
    if text_glm:
        return text_glm

    return ocr_service.ocr_seite_mit_tsv(bild, tsv_pfad, lang="deu")


def _synth_seite(text: str) -> SeitenText:
    """E-Mail-Text als synthetische Ein-Seiten-Struktur (kein PDF/OCR)."""
    return SeitenText(nr=1, text=text, braucht_ocr=False,
                      ratio_salat=0.0, textquelle="email_text")


def verarbeite_dokument(intake_id: int) -> bool:
    """Fuehrt den Textgewinnungs-Schritt aus. Liefert True bei Erfolg.

    Bei Exception: markiere_fehler() -> Backoff/Retry ueber die Queue.
    """
    try:
        dok = _lade_dokument(intake_id)

        if dok.get("payload_typ") == "text":
            text_roh = (dok.get("structured_payload") or "")
            if not text_roh.strip():
                raise RuntimeError("Text-Payload ohne Inhalt")
            seiten = [_synth_seite(text_roh)]
            text_gesamt = text_roh
            textquelle = "email_text"
        else:
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

        # ── Klassifikation (S1.6b Stufe 1 + Stufe 2) ─────────────────────
        # Auto-Vorschlag wird IMMER berechnet (fuer Transparenz und Konflikt-
        # Anzeige), auch bei manueller Klasse. Aber:
        #   * klasse_quelle='manuell' -> die manuelle Wahl bleibt bindend,
        #     die Felder werden mit dem manuellen Klassen-Schema extrahiert.
        #   * sonst: Auto-Ergebnis ist verbindlich.
        signale = _lade_zustellungs_signale(intake_id)
        kandidaten, hinweise = klassifiziere_stufe1(text_gesamt, signale,
                                                     registry)
        labels = sorted(registry.klassen.keys())
        seite1 = seiten[0].text if seiten else ""
        letzte = seiten[-1].text if seiten else ""
        klasse_auto, konfidenz_auto = klassifiziere_stufe2(
            seite1, letzte, kandidaten, labels,
        )

        ist_manuell = dok.get("klasse_quelle") == "manuell"
        if ist_manuell and dok.get("klasse"):
            klasse = dok["klasse"]
            # Konfidenz der manuellen Wahl: hoch, aber wir behalten den
            # alten Wert falls vorhanden (kann vom letzten Auto-Run stammen).
            konfidenz = dok.get("konfidenz") if dok.get("konfidenz") is not None else 1.0
            neue_klasse_quelle = "manuell"
        else:
            klasse = klasse_auto
            konfidenz = konfidenz_auto
            neue_klasse_quelle = "auto"

        # ── Feld-Extraktion (S1.6b) ──────────────────────────────────────
        # WICHTIG: gegen die effektive Klasse (manuell hat Vorrang), nicht
        # gegen den Auto-Vorschlag.
        extraktion = extrahiere_felder(text_gesamt, klasse, registry)
        felder = extraktion.get("felder", {})
        llm_konflikt = extraktion.get("llm_konflikt")

        # ── Akten-Matching (S1.7) ────────────────────────────────────────
        # Kandidatenliste mit Score. KEIN Auto-Zuordnen -- akte_az wird
        # erst durch die Review-Freigabe (S1.8) verbindlich gesetzt.
        akten_kandidaten = finde_kandidaten(text_gesamt, signale)
        akten_kandidaten_json = [
            {"akte_az": k.akte_az,
             "score": round(k.score, 3),
             "quelle": k.quelle,
             "treffer": k.treffer}
            for k in akten_kandidaten
        ]

        parse_dict: Dict[str, Any] = {
            "text_gesamt": text_gesamt,
            "seiten": [
                {"nr": s.nr, "textquelle": s.textquelle,
                 "ratio_salat": round(s.ratio_salat, 3),
                 "zeichen": len(s.text)}
                for s in seiten
            ],
            "klassifikation": {
                "kandidaten": [
                    {"klasse": k.klasse,
                     "konfidenz": round(k.konfidenz, 3),
                     "quelle": k.quelle}
                    for k in kandidaten
                ],
                "hinweise": hinweise,
                "auto_vorschlag": {
                    "klasse": klasse_auto,
                    "konfidenz": round(konfidenz_auto, 3),
                    "abgewaehlt_zugunsten_manuell": (
                        ist_manuell and klasse_auto != klasse
                    ),
                },
            },
            "felder": felder,
            "akten_kandidaten": akten_kandidaten_json,
        }
        if llm_konflikt:
            parse_dict["llm_konflikt"] = llm_konflikt
        parse_json = json.dumps(parse_dict, ensure_ascii=False)

        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET "
                "klasse=?, klasse_quelle=?, konfidenz=?, "
                "textquelle=?, registry_version=?, llm_stack=?, parse_json=? "
                "WHERE id=?",
                (klasse, neue_klasse_quelle, konfidenz, textquelle,
                 registry.version, _llm_stack_json(), parse_json, intake_id),
            )
        markiere_bereit(intake_id)
        logger.info(
            "Dokument %s: %d Seiten, %s, %d Zeichen -> %s (%.2f) [%s]"
            "%s",
            intake_id, len(seiten), textquelle, len(text_gesamt),
            klasse, konfidenz, neue_klasse_quelle,
            f" (Auto haette {klasse_auto} vorgeschlagen)" if
            ist_manuell and klasse_auto != klasse else "",
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
