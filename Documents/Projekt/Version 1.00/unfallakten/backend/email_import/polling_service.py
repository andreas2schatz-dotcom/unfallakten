"""
US-02 – IMAP Auto-Polling Service
===================================
Verwaltet das automatische Polling für 4 IMAP-Accounts.
Job-Funktion fuehre_polling_durch() wird von APScheduler jede Minute aufgerufen.
"""

import logging
from datetime import datetime

from ..db.database import get_connection
from .import_service import (
    fuehre_import_lauf_durch,
    _imap_cfg_fuer_konto as _imap_config_fuer_account,
)

logger = logging.getLogger(__name__)


def hole_accounts() -> list[dict]:
    """Liest alle Account-Rows aus DB und ergänzt ENV-Credential-Status."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT account, aktiv, intervall_min, letzter_lauf, "
            "       letzter_status, letzter_fehler "
            "FROM imap_polling_config ORDER BY account"
        ).fetchall()
    result = []
    for row in rows:
        account = row["account"]
        cfg = _imap_config_fuer_account(account)
        result.append({
            "account":            account,
            "aktiv":              bool(row["aktiv"]),
            "intervall_min":      row["intervall_min"],
            "passwort_vorhanden": cfg is not None,
            "letzter_lauf":       row["letzter_lauf"],
            "letzter_status":     row["letzter_status"],
            "letzter_fehler":     row["letzter_fehler"],
        })
    return result


def _ist_faellig(letzter_lauf: str | None, intervall_min: int) -> bool:
    """True wenn Account noch nie lief (None) oder Intervall abgelaufen."""
    if letzter_lauf is None:
        return True
    try:
        letzter = datetime.fromisoformat(letzter_lauf)
        return (datetime.now() - letzter).total_seconds() >= intervall_min * 60
    except (ValueError, TypeError):
        return True


def _schreibe_status(account: str, status: str, fehler: str | None) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE imap_polling_config "
            "SET letzter_lauf=?, letzter_status=?, letzter_fehler=? "
            "WHERE account=?",
            (datetime.now().isoformat(timespec="seconds"), status, fehler, account),
        )


def fuehre_polling_durch() -> None:
    """APScheduler-Job: importiert für jeden fälligen aktiven Account."""
    try:
        accounts = hole_accounts()
    except Exception as e:
        logger.error("IMAP-Polling: DB-Fehler beim Laden der Accounts: %s", e)
        return

    for acc in accounts:
        account = acc["account"]
        if not acc["aktiv"]:
            continue
        if not acc["passwort_vorhanden"]:
            _schreibe_status(
                account, "fehler",
                f"EMAIL_PASSWORD_{account.upper()} nicht in .env gesetzt",
            )
            continue
        if not _ist_faellig(acc["letzter_lauf"], acc["intervall_min"]):
            continue

        logger.info("IMAP-Polling: Starte Import für %s", account)
        try:
            cfg = _imap_config_fuer_account(account)
            fuehre_import_lauf_durch(imap_config=cfg, konto=account)
            _schreibe_status(account, "ok", None)
            logger.info("IMAP-Polling: %s erfolgreich.", account)
        except Exception as e:
            logger.error("IMAP-Polling: Fehler bei %s: %s", account, e)
            _schreibe_status(account, "fehler", str(e)[:500])
