"""
Modul 1 – Models: Aktivitäten & Dokumente
==========================================
"""

import sqlite3
import logging
from dataclasses import dataclass
from typing import Optional
from ..db.database import get_connection

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# AKTIVITAETEN (Audit-Log)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Aktivitaet:
    id: Optional[int]
    akte_id: Optional[int]
    benutzer_id: Optional[int]
    zeitstempel: str
    aktion: str
    beschreibung: str
    tabelle: Optional[str] = None
    datensatz_id: Optional[int] = None
    aenderung_json: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Aktivitaet":
        return cls(**{k: row[k] for k in row.keys()})


def logge_aktivitaet(aktion: str, beschreibung: str,
                      akte_id: Optional[int] = None,
                      benutzer_id: Optional[int] = None,
                      tabelle: Optional[str] = None,
                      datensatz_id: Optional[int] = None,
                      aenderung_json: Optional[str] = None) -> Aktivitaet:
    """Schreibt einen Aktivitätseintrag."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO aktivitaeten
                (akte_id, benutzer_id, aktion, beschreibung,
                 tabelle, datensatz_id, aenderung_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (akte_id, benutzer_id, aktion, beschreibung,
             tabelle, datensatz_id, aenderung_json)
        )
        row = conn.execute(
            "SELECT * FROM aktivitaeten WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return Aktivitaet.from_row(row)


def hole_aktivitaeten(akte_id: Optional[int] = None,
                       limit: int = 50) -> list[Aktivitaet]:
    """Gibt Aktivitäten zurück, optional gefiltert nach Akte."""
    if akte_id:
        sql = ("SELECT * FROM aktivitaeten WHERE akte_id = ? "
               "ORDER BY zeitstempel DESC LIMIT ?")
        params = [akte_id, limit]
    else:
        sql = "SELECT * FROM aktivitaeten ORDER BY zeitstempel DESC LIMIT ?"
        params = [limit]

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [Aktivitaet.from_row(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# DOKUMENTE
# ══════════════════════════════════════════════════════════════════════════════

GUELTIGE_TYPEN = (
    "gutachten", "abrechnungsschreiben", "forderungsschreiben",
    "sachstandsanfrage", "klage", "sonstiges"
)
GUELTIGE_DATEITYPEN = ("pdf", "docx", "jpg", "png", "sonstiges")
GUELTIGE_PARSE_STATUS = ("ausstehend", "erfolgreich", "fehler", "manuell_korrigiert")


@dataclass
class Dokument:
    id: Optional[int]
    akte_id: int
    typ: str
    dateiname: str
    dateipfad: str
    dateityp: str = "pdf"
    dateigroesse: Optional[int] = None
    hochgeladen_am: Optional[str] = None
    hochgeladen_von: Optional[int] = None
    parse_status: str = "ausstehend"
    parse_konfidenz: Optional[float] = None
    parse_json: Optional[str] = None
    parse_fehler: Optional[str] = None
    notizen: Optional[str] = None
    dokumentenklasse: Optional[str] = None
    pdf_hash: Optional[str] = None
    bezeichnung: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Dokument":
        return cls(**{k: row[k] for k in row.keys()
                      if k in cls.__dataclass_fields__})


def registriere_dokument(akte_id: int, typ: str, dateiname: str,
                          dateipfad: str, bearbeiter_id: Optional[int] = None,
                          dateityp: str = "pdf",
                          dateigroesse: Optional[int] = None) -> Dokument:
    """Registriert ein hochgeladenes Dokument in der Datenbank."""
    if typ not in GUELTIGE_TYPEN:
        raise ValueError(f"Ungültiger Dokumenttyp: {typ!r}")
    if dateityp not in GUELTIGE_DATEITYPEN:
        raise ValueError(f"Ungültiger Dateityp: {dateityp!r}")

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO dokumente
                (akte_id, typ, dateiname, dateipfad, dateityp,
                 dateigroesse, hochgeladen_von)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (akte_id, typ, dateiname, dateipfad, dateityp,
             dateigroesse, bearbeiter_id)
        )
        doc_id = cursor.lastrowid

        # Aktivität loggen – in try/except da akte_id TEXT ist
        try:
            conn.execute(
                """
                INSERT INTO aktivitaeten (akte_id, benutzer_id, aktion, beschreibung,
                                           tabelle, datensatz_id)
                VALUES (?, ?, 'dokument_hochgeladen', ?, 'dokumente', ?)
                """,
                (akte_id, bearbeiter_id,
                 f"Dokument hochgeladen: {dateiname} ({typ})", doc_id)
            )
        except Exception as log_err:
            logger.warning("Aktivitäts-Log für Dokument %d fehlgeschlagen: %s",
                           doc_id, log_err)

    from datetime import datetime
    # Dokument aus bekannten Inputs bauen – kein SELECT nötig
    # (SELECT nach INSERT in neuem get_connection() würde uncommitted INSERT nicht sehen)
    return Dokument(
        id=doc_id,
        akte_id=akte_id,
        typ=typ,
        dateiname=dateiname,
        dateipfad=dateipfad,
        dateityp=dateityp,
        dateigroesse=dateigroesse,
        hochgeladen_von=bearbeiter_id,
        hochgeladen_am=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        parse_status="ausstehend",
    )


def aktualisiere_parse_status(dokument_id: int, parse_status: str,
                               parse_json: Optional[str] = None,
                               parse_konfidenz: Optional[float] = None,
                               parse_fehler: Optional[str] = None) -> Optional[Dokument]:
    """Wird von Modul 4 (PDF-Parser) aufgerufen."""
    if parse_status not in GUELTIGE_PARSE_STATUS:
        raise ValueError(f"Ungültiger Parse-Status: {parse_status!r}")

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE dokumente
            SET parse_status = ?, parse_json = ?,
                parse_konfidenz = ?, parse_fehler = ?
            WHERE id = ?
            """,
            (parse_status, parse_json, parse_konfidenz, parse_fehler, dokument_id)
        )
        row = conn.execute(
            "SELECT * FROM dokumente WHERE id = ?", (dokument_id,)
        ).fetchone()
        return Dokument.from_row(row) if row else None


def hole_dokumente_by_akte(akte_id: int,
                            typ: Optional[str] = None) -> list[Dokument]:
    sql = "SELECT * FROM dokumente WHERE akte_id = ?"
    params: list = [akte_id]
    if typ:
        sql += " AND typ = ?"
        params.append(typ)
    sql += " ORDER BY hochgeladen_am DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [Dokument.from_row(r) for r in rows]


def hole_dokument_by_id(dokument_id: int) -> Optional[Dokument]:
    """Gibt ein einzelnes Dokument anhand seiner ID zurück."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM dokumente WHERE id = ?", (dokument_id,)
        ).fetchone()
        return Dokument.from_row(row) if row else None


def loesche_dokument(dokument_id: int) -> bool:
    with get_connection() as conn:
        # Abhängige Tabellen bereinigen die kein ON DELETE CASCADE/SET NULL haben
        conn.execute(
            "UPDATE klassifikation_training SET dok_id = NULL WHERE dok_id = ?",
            (dokument_id,)
        )
        conn.execute(
            "DELETE FROM schadenposition_belege WHERE dokument_id = ?",
            (dokument_id,)
        )
        # fristen/todos mit dok_id-Referenz (falls vorhanden)
        for tbl in ("fristen", "todos"):
            try:
                conn.execute(
                    f"UPDATE {tbl} SET dok_id = NULL WHERE dok_id = ?",
                    (dokument_id,)
                )
            except Exception:
                pass  # Tabelle existiert nicht oder hat kein dok_id-Feld
        cursor = conn.execute(
            "DELETE FROM dokumente WHERE id = ?", (dokument_id,)
        )
        return cursor.rowcount > 0
