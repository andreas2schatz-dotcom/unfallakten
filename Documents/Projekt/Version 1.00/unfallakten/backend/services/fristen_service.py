"""
Fristen-Service – PRD-25a
==========================
Legt automatisch system-generierte Todos für gesetzliche Fristen an.

Drei Frist-Typen:
  verjährung  – §195/199 BGB: 3 Jahre, Jahresende, Vorfristen -2M / -1M
  pflvg_3a    – §3a PflVG: 3 Monate ab Forderungsschreiben-Versand
  antwort_2w  – 2-Wochen-Antwortfrist nach eigenem Schreiben

Alle Funktionen sind idempotent (kein Doppel-Anlegen).

Keine externen Abhängigkeiten außer stdlib. Python 3.9 kompatibel.
"""

import calendar
import logging
from datetime import date, datetime, timedelta

from ..db.database import get_connection
from ..utils.datum import parse_datum as _parse_datum

logger = logging.getLogger(__name__)

# ── Konstanten ─────────────────────────────────────────────────────────────────

GEGENSEITEN_TYPEN = frozenset({"forderungsschreiben", "sachstandsanfrage", "stellungnahme"})


# ── Öffentliche API ────────────────────────────────────────────────────────────

def setze_verjaerungs_fristen(akte_az, unfalldatum_str):
    # type: (str, str) -> None
    """
    Legt 3 Verjährungs-Todos für eine Akte an.

    Verjährungsbeginn nach §199 Abs. 1 BGB: Ende des Jahres, in dem der
    Anspruch entstanden ist. Fristende: 3 Jahre danach → 31.12.

    Beispiel: Unfall 15.03.2023 → Verjährung 31.12.2026
    Vorfristen: 01.11.2026 (-2M) und 01.12.2026 (-1M)
    """
    if not akte_az or not unfalldatum_str:
        return

    unfalldatum = _parse_datum(unfalldatum_str)
    if unfalldatum is None:
        logger.warning(
            "fristen_service: Unfalldatum '%s' nicht parsbar – übersprungen.", unfalldatum_str
        )
        return

    # §199 BGB: Verjährung läuft ab Ende des Unfalljahres + 3 Jahre
    verjahrungs_datum = date(unfalldatum.year + 3, 12, 31)
    vj_str = verjahrungs_datum.strftime("%d.%m.%Y")

    todos = [
        {
            "regel_key": "verjährung_2m",
            "faellig_am": _subtrahiere_monate(verjahrungs_datum, 2),
            "frist_typ":  "verjährung",
            "text":       "⚠ Verjährung in 2 Monaten (fällig {}) — Hemmung prüfen (§204 BGB)".format(vj_str),
        },
        {
            "regel_key": "verjährung_1m",
            "faellig_am": _subtrahiere_monate(verjahrungs_datum, 1),
            "frist_typ":  "verjährung",
            "text":       "⚠ Verjährung in 1 Monat (fällig {}) — letzte Chance zur Hemmung!".format(vj_str),
        },
        {
            "regel_key": "verjährung",
            "faellig_am": verjahrungs_datum,
            "frist_typ":  "verjährung",
            "text":       "⚠ Verjährung heute! Akte sofort prüfen.",
        },
    ]

    for t in todos:
        if not _todo_existiert(akte_az, t["regel_key"]):
            _erstelle_todo(
                akte_az=akte_az,
                text=t["text"],
                faellig_am=t["faellig_am"].isoformat(),
                frist_typ=t["frist_typ"],
                regel_key=t["regel_key"],
            )
            logger.info(
                "fristen_service: Todo '%s' für Akte %s angelegt (fällig %s).",
                t["regel_key"], akte_az, t["faellig_am"],
            )


def setze_pflvg_frist(akte_az):
    # type: (str) -> None
    """
    Legt §3a PflVG-Todo an: 3 Monate ab heute.
    Auslöser: Forderungsschreiben wurde generiert.
    """
    if not akte_az:
        return

    if _todo_existiert(akte_az, "pflvg_3a"):
        logger.debug(
            "fristen_service: pflvg_3a für %s bereits vorhanden – übersprungen.", akte_az
        )
        return

    faellig = _addiere_monate(date.today(), 3).isoformat()
    _erstelle_todo(
        akte_az=akte_az,
        text="§3a PflVG-Frist: Versicherer muss bis heute reguliert oder begründet abgelehnt haben",
        faellig_am=faellig,
        frist_typ="pflvg_3a",
        regel_key="pflvg_3a",
    )
    logger.info(
        "fristen_service: §3a PflVG-Frist für Akte %s angelegt (fällig %s).", akte_az, faellig
    )


def setze_antwort_frist(akte_az, dok_id, dok_typ):
    # type: (str, int, str) -> None
    """
    Legt 2-Wochen-Antwortfrist-Todo für ein versandtes Dokument an.
    Auslöser: forderungsschreiben, sachstandsanfrage oder stellungnahme generiert.
    """
    if not akte_az or dok_typ not in GEGENSEITEN_TYPEN:
        return

    regel_key = "antwort_2w_{}".format(dok_id)
    if _todo_existiert(akte_az, regel_key):
        return

    typ_label = {
        "forderungsschreiben": "Forderungsschreiben",
        "sachstandsanfrage":   "Sachstandsanfrage",
        "stellungnahme":       "Stellungnahme",
    }.get(dok_typ, dok_typ)

    heute_str   = date.today().strftime("%d.%m.%Y")
    faellig_str = (date.today() + timedelta(days=14)).isoformat()

    _erstelle_todo(
        akte_az=akte_az,
        text="Antwort ausstehend: {} vom {} — nachhaken?".format(typ_label, heute_str),
        faellig_am=faellig_str,
        frist_typ="antwort_2w",
        regel_key=regel_key,
        dok_id=dok_id,
    )
    logger.info(
        "fristen_service: 2-Wochen-Antwortfrist für Akte %s (dok %d) angelegt.",
        akte_az, dok_id,
    )


# ── Interne Hilfsfunktionen ────────────────────────────────────────────────────

def _todo_existiert(akte_az, regel_key):
    # type: (str, str) -> bool
    """True wenn offenes (erledigt=0) Todo mit diesem regel_key existiert."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM todos WHERE akte_az = ? AND regel_key = ? AND erledigt = 0 LIMIT 1",
            (akte_az, regel_key),
        ).fetchone()
    return row is not None


def _erstelle_todo(akte_az, text, faellig_am, frist_typ, regel_key, dok_id=None):
    # type: (str, str, str, str, str, int) -> int
    """Legt ein system-generiertes Todo an und gibt die neue id zurück."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO todos
                (akte_az, text, faellig_am, frist_typ, erledigt, quelle, dok_id, regel_key)
            VALUES (?, ?, ?, ?, 0, 'system', ?, ?)
            """,
            (akte_az, text, faellig_am, frist_typ, dok_id, regel_key),
        )
        return cursor.lastrowid


def _addiere_monate(d, monate):
    # type: (date, int) -> date
    """
    Addiert eine Anzahl Monate zu einem Datum.
    Klemmt auf den letzten Tag des Zielmonats wenn nötig
    (z.B. 31.01. + 1M = 28.02.).
    """
    monat = d.month + monate
    jahr  = d.year + (monat - 1) // 12
    monat = (monat - 1) % 12 + 1
    max_tag = calendar.monthrange(jahr, monat)[1]
    return date(jahr, monat, min(d.day, max_tag))


def _subtrahiere_monate(d, monate):
    # type: (date, int) -> date
    """Subtrahiert eine Anzahl Monate von einem Datum."""
    return _addiere_monate(d, -monate)
