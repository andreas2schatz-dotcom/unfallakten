"""
Gemeinsamer Soft-Delete-Helfer fuer Intake-Dokumente.

Setzt verworfen_grund/am/von und schreibt eine korrektur_log-Zeile. Wird
sowohl von der manuellen Route (post_verwerfen) als auch von der
automatischen Rausch-Absender-Regel (adapter_imap) genutzt.

verworfen_von = None kennzeichnet die automatische Aussortierung (System).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ..db.database import get_connection

logger = logging.getLogger(__name__)

_VERWERFBARE_STATUS = ("neu", "bereit_zur_review", "pipeline_fehler", "laeuft")


def auto_verwerfen(
    intake_id: int,
    *,
    grund: str,
    kommentar: Optional[str] = None,
    benutzer_id: Optional[int] = None,
) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT queue_status, verworfen_am, klasse, registry_version "
            "FROM intake_dokumente WHERE id=?", (intake_id,),
        ).fetchone()
        if row is None:
            logger.error("auto_verwerfen: ID %s nicht gefunden", intake_id)
            return None
        if row["verworfen_am"] is not None:
            return None
        if row["queue_status"] not in _VERWERFBARE_STATUS:
            logger.warning(
                "auto_verwerfen: Intake %s im Status %r nicht verwerfbar",
                intake_id, row["queue_status"],
            )
            return None

        jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE intake_dokumente "
            "SET verworfen_grund=?, verworfen_am=?, verworfen_von=? WHERE id=?",
            (grund, jetzt, benutzer_id, intake_id),
        )
        wert_neu = json.dumps({"grund": grund, "kommentar": kommentar},
                              ensure_ascii=False)
        conn.execute(
            "INSERT INTO korrektur_log "
            "(intake_dokument_id, feld, wert_alt, wert_neu, klasse, "
            " registry_version, benutzer_id) "
            "VALUES (?, 'verworfen', ?, ?, ?, ?, ?)",
            (intake_id, row["queue_status"], wert_neu, row["klasse"],
             row["registry_version"], benutzer_id),
        )
    logger.info("auto_verwerfen: Intake %s grund=%s benutzer=%s",
                intake_id, grund, benutzer_id)
    return jetzt
