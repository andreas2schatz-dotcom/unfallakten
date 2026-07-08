"""
S1.3 - Persistenz-Helfer fuer die Intake-Adapter.

Alle drei Adapter (adapter_imap, adapter_upload, adapter_eakte) legen ein
``intake_dokumente`` an (idempotent per sha256) und schreiben je Zustellung
eine ``zustellungen``-Zeile. Damit die Adapter selbst schlank bleiben, ist
die gemeinsame Insert-Logik hier gebuendelt.

Konvention aus S1.1 (Migration 46) + K-P2:
  * ``intake_dokumente.sha256`` ist UNIQUE (global, akte-unabhaengig).
  * ``zustellungen.intake_dokument_id`` FK auf intake_dokumente.
  * ``zustellungen`` wird nie geloescht; jede Zustellung erzeugt eine Zeile,
    auch bei sha256-Duplikat des Dokuments.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from ..db.database import get_connection
from .archiv import erzeuge_arbeitskopie, lege_original_ab

logger = logging.getLogger(__name__)

# Erweiterungen, fuer die eine PDF-Arbeitskopie erzeugt werden kann.
# HEIC ist im Archiv-Modul explizit vertagt und darf hier keinen Abbruch
# aus loesen — Arbeitskopie bleibt bei unbekannten Typen leer.
_ARBEITSKOPIE_UNTERSTUETZT = {"pdf", "docx", "doc", "jpg", "jpeg", "png"}


def _sha256_bytes(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def oder_intake_dokument_fuer_datei(daten: bytes, ext: str) -> tuple[int, str]:
    """
    Legt eine Datei ins Archiv (Original + Arbeitskopie) und stellt sicher,
    dass fuer ihren sha256 GENAU EINE Zeile in ``intake_dokumente`` existiert.

    Rueckgabe: ``(intake_dokument_id, sha256)``.
    """
    ext_norm = (ext or "").lstrip(".").lower()
    sha = _sha256_bytes(daten)

    original_pfad = lege_original_ab(daten, ext_norm)

    arbeitskopie_pfad: str | None = None
    if ext_norm in _ARBEITSKOPIE_UNTERSTUETZT:
        try:
            arbeitskopie_pfad = erzeuge_arbeitskopie(original_pfad, ext_norm)
        except Exception as e:
            # Arbeitskopie ist Best-Effort — Adapter soll trotzdem laufen,
            # damit der Alt-Pfad nicht gefaehrdet wird. Fehler landet im Log.
            logger.warning(
                "Arbeitskopie fuer %s (ext=%s) fehlgeschlagen: %s", sha, ext_norm, e
            )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO intake_dokumente
                (sha256, original_pfad, arbeitskopie_pfad, payload_typ, queue_status)
            VALUES (?, ?, ?, 'datei', 'neu')
            """,
            (sha, original_pfad, arbeitskopie_pfad),
        )
        row = conn.execute(
            "SELECT id, arbeitskopie_pfad FROM intake_dokumente WHERE sha256 = ?",
            (sha,),
        ).fetchone()
        intake_id = row["id"]

        # Nachtragen falls die frueher angelegte Zeile noch keine Arbeitskopie
        # trug (idempotenter Aufholmechanismus).
        if arbeitskopie_pfad and not row["arbeitskopie_pfad"]:
            conn.execute(
                "UPDATE intake_dokumente SET arbeitskopie_pfad = ? WHERE id = ?",
                (arbeitskopie_pfad, intake_id),
            )

    return intake_id, sha


def oder_intake_dokument_fuer_text(text: str) -> tuple[int, str]:
    """
    Text-Payload (z.B. E-Mail-Body). Speichert den Text in
    ``structured_payload`` und dedupliziert ueber sha256(text-utf8).
    Kein Archiv-Original, keine Arbeitskopie.

    Rueckgabe: ``(intake_dokument_id, sha256)``.
    """
    sha = _sha256_text(text or "")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO intake_dokumente
                (sha256, payload_typ, structured_payload, queue_status)
            VALUES (?, 'text', ?, 'neu')
            """,
            (sha, text),
        )
        row = conn.execute(
            "SELECT id FROM intake_dokumente WHERE sha256 = ?", (sha,)
        ).fetchone()
    return row["id"], sha


def erzeuge_zustellung(
    intake_dokument_id: int,
    quelle: str,
    *,
    parent_id: int | None = None,
    absender: str | None = None,
    auth_status: str | None = None,
    betreff: str | None = None,
    empfangen_am: str | None = None,
    signale: dict[str, Any] | None = None,
    konto: str | None = None,
    roh_referenz: str | None = None,
) -> int:
    """
    Legt eine ``zustellungen``-Zeile an und gibt deren id zurueck.
    Wird nie gedupliziert — jede Zustellung ist ein eigener Datensatz.
    """
    signale_json = json.dumps(signale, ensure_ascii=False) if signale else None
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO zustellungen
                (intake_dokument_id, quelle, absender, auth_status,
                 betreff, empfangen_am, parent_id, signale_json,
                 konto, roh_referenz)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                intake_dokument_id, quelle, absender, auth_status,
                betreff, empfangen_am, parent_id, signale_json,
                konto, roh_referenz,
            ),
        )
        return cursor.lastrowid
