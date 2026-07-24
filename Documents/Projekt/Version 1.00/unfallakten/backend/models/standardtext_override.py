"""V11 Standardtexte: DB-Overrides (nur Abweichungen vom YAML-Standard)."""
import sqlite3
import logging
from ..db.database import get_connection

logger = logging.getLogger(__name__)


def hole_alle_overrides() -> dict:
    return {k: v["text"] for k, v in hole_alle_overrides_mit_meta().items()}


def hole_alle_overrides_mit_meta() -> dict:
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT baustein_key, text, geaendert_am FROM standardtext_override"
            ).fetchall()
    except sqlite3.OperationalError:
        # Tabelle existiert erst ab Migration 65 - reine Unit-Tests des
        # Klage-Services laufen ohne Migrationslauf.
        return {}
    return {r["baustein_key"]: {"text": r["text"], "geaendert_am": r["geaendert_am"]}
            for r in rows}


def setze_override(baustein_key: str, text: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO standardtext_override (baustein_key, text, geaendert_am)"
            " VALUES (?, ?, datetime('now', 'localtime'))"
            " ON CONFLICT(baustein_key) DO UPDATE SET"
            " text = excluded.text, geaendert_am = excluded.geaendert_am",
            (baustein_key, text),
        )


def loesche_override(baustein_key: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM standardtext_override WHERE baustein_key = ?",
            (baustein_key,),
        )
        return cur.rowcount > 0
