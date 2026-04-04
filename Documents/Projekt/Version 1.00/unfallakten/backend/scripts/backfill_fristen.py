"""
Backfill-Skript – PRD-25a Automatische Fristen
================================================
Legt Verjährungs- und §3a PflVG-Fristen für alle bestehenden Akten nach.

Einmalig ausführen nach Deployment von PRD-25a:
  docker-compose exec backend python -m scripts.backfill_fristen

Idempotent: Bereits vorhandene Todos werden nicht doppelt angelegt.
"""

import sys
import os
import logging

from backend.db.database import get_connection
from backend.services.fristen_service import setze_verjaerungs_fristen, setze_pflvg_frist

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("backfill_fristen")


def backfill_verjährung():
    """Setzt Verjährungsfristen für alle Akten mit bekanntem Unfalldatum."""
    with get_connection() as conn:
        akten = conn.execute(
            "SELECT az, unfalldatum FROM unfallakte WHERE unfalldatum IS NOT NULL AND unfalldatum != ''"
        ).fetchall()

    logger.info("Starte Verjährungs-Backfill für %d Akten …", len(akten))
    ok = 0
    skip = 0
    for az, unfalldatum in akten:
        try:
            setze_verjaerungs_fristen(az, unfalldatum)
            ok += 1
        except Exception as e:
            logger.warning("Fehler bei Akte %s: %s", az, e)
            skip += 1

    logger.info("Verjährungs-Backfill abgeschlossen: %d OK, %d Fehler.", ok, skip)


def backfill_pflvg():
    """Setzt §3a PflVG-Frist für alle Akten mit generiertem Forderungsschreiben."""
    with get_connection() as conn:
        docs = conn.execute(
            """
            SELECT DISTINCT akte_id
            FROM dokumente
            WHERE typ = 'forderungsschreiben'
              AND akte_id IS NOT NULL
            """
        ).fetchall()

    logger.info("Starte §3a PflVG-Backfill für %d Akten …", len(docs))
    ok = 0
    skip = 0
    for (az,) in docs:
        try:
            setze_pflvg_frist(az)
            ok += 1
        except Exception as e:
            logger.warning("Fehler bei Akte %s: %s", az, e)
            skip += 1

    logger.info("§3a PflVG-Backfill abgeschlossen: %d OK, %d Fehler.", ok, skip)


if __name__ == "__main__":
    backfill_verjährung()
    backfill_pflvg()
    logger.info("Backfill komplett.")
