"""
PDF-Pipeline – Eskalation
===========================
Erzeugt System-Todos fuer nicht klassifizierte Dokumente.
Nutzt die bestehende todos-Tabelle (Migration 23).

Python 3.9 kompatibel.
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


def eskaliere_dokument(akte_az, dok_id, meta=None, registry_treffer=None):
    # type: (str, int, Optional[Any], Optional[dict]) -> None
    """
    Erzeugt ein System-Todo fuer manuelle Klassifikation.

    Das Todo erscheint im To-Do-Reiter der Akte (PRD-01)
    und spaeter im Tagesstart-Dashboard (PRD-17).

    Args:
        akte_az: Aktenzeichen (PK der unfallakte)
        dok_id: ID des Dokuments in der dokumente-Tabelle
        meta: Ergebnis von classify_document() (optional)
        registry_treffer: Bester Registry-Treffer (optional)
    """
    # Vorschlag zusammenbauen
    vorschlaege = []
    if meta and hasattr(meta, "dokumenttyp") and meta.dokumenttyp != "unbekannt":
        konf = getattr(meta, "konfidenz", 0)
        vorschlaege.append("%s (%.0f%%)" % (meta.dokumenttyp, konf * 100))

    if registry_treffer:
        vorschlaege.append(
            "%s via Registry" % registry_treffer.get("klasse", "?")
        )

    if vorschlaege:
        vorschlag_text = "Vorschlaege: " + ", ".join(vorschlaege)
    else:
        vorschlag_text = "Kein Vorschlag – Dokument manuell pruefen"

    todo_text = "Dokument klassifizieren – %s" % vorschlag_text

    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            # Pruefen ob bereits ein offenes Klassifikations-Todo existiert
            bestehend = conn.execute(
                "SELECT id FROM todos "
                "WHERE dok_id = ? AND regel_key = 'klassifikation_offen' "
                "AND erledigt = 0",
                (dok_id,),
            ).fetchone()

            if bestehend:
                logger.info(
                    "Klassifikations-Todo existiert bereits fuer Dok %d (Todo %d).",
                    dok_id, bestehend["id"],
                )
                return

            # PRAGMA wegen dok_id FK
            conn.execute("PRAGMA foreign_keys = OFF")
            try:
                conn.execute(
                    "INSERT INTO todos "
                    "(akte_az, text, quelle, dok_id, regel_key) "
                    "VALUES (?, ?, 'system', ?, 'klassifikation_offen')",
                    (akte_az, todo_text, dok_id),
                )
            finally:
                conn.execute("PRAGMA foreign_keys = ON")

            logger.info(
                "Klassifikations-Todo erstellt fuer Dok %d in Akte %s.",
                dok_id, akte_az,
            )
    except Exception as e:
        logger.error(
            "Eskalation fehlgeschlagen fuer Dok %d: %s", dok_id, e, exc_info=True,
        )
