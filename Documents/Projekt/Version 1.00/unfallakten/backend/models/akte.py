"""
Modul 1 – Model: Unfallakte
============================
Datenzugriffsschicht für die Tabelle `unfallakte`.
Primary Key: az (TEXT) = Aktenzeichen aus RA-Micro (z.B. "211/26")
"""

import sqlite3
import logging
from dataclasses import dataclass
from typing import Optional
from ..db.database import get_connection

logger = logging.getLogger(__name__)

GUELTIGE_STATUS = ("offen", "in_regulierung", "klage", "abgeschlossen")


@dataclass
class Unfallakte:
    """Repräsentiert eine Unfallakte. PK = az (Aktenzeichen)."""
    az:              str             # Primary Key = RA-Micro Aktenzeichen
    unfalldatum:     str             # YYYY-MM-DD (leer = unbekannt)
    status:          str
    erstellt_am:     str
    geaendert_am:    str
    unfallort:       Optional[str]  = None
    bearbeiter_id:   Optional[int]  = None
    notizen:         Optional[str]  = None
    haftungsquote:   float          = 100.0
    regulierung_status: str         = "offen"
    kurzbezeichnung: Optional[str]  = None
    sachbearbeiter:  Optional[str]  = None

    # Alias für Rückwärtskompatibilität (Code referenziert akte.id überall)
    @property
    def id(self) -> str:
        return self.az

    # Alias für alten Code der akte.aktenzeichen nutzt
    @property
    def aktenzeichen(self) -> str:
        return self.az

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Unfallakte":
        keys = row.keys()
        return cls(
            az=             row["az"],
            unfalldatum=    row["unfalldatum"]    or "",
            status=         row["status"],
            erstellt_am=    row["erstellt_am"],
            geaendert_am=   row["geaendert_am"],
            unfallort=      row["unfallort"],
            bearbeiter_id=  row["bearbeiter_id"],
            notizen=        row["notizen"],
            haftungsquote=  row["haftungsquote"],
            regulierung_status= row["regulierung_status"] if "regulierung_status" in keys else "offen",
            kurzbezeichnung=row["kurzbezeichnung"] if "kurzbezeichnung" in keys else None,
            sachbearbeiter= row["sachbearbeiter"]  if "sachbearbeiter"  in keys else None,
        )


# ── CRUD ──────────────────────────────────────────────────────────────────────

def erstelle_oder_hole_akte(az: str,
                             bearbeiter_id: Optional[int] = None,
                             kurzbezeichnung: Optional[str] = None,
                             sachbearbeiter:  Optional[str] = None,
                             unfalldatum:     str = "",
                             unfallort:       Optional[str] = None,
                             haftungsquote:   float = 100.0) -> "Unfallakte":
    """
    Gibt die Akte zurück wenn sie existiert, legt sie sonst neu an.
    Wird beim ersten Öffnen einer RA-Micro-Akte aufgerufen (on demand).
    """
    az = az.strip()
    if not az:
        raise ValueError("Aktenzeichen darf nicht leer sein.")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM unfallakte WHERE az = ?", (az,)
        ).fetchone()
        if row:
            return Unfallakte.from_row(row)

        # Neu anlegen
        conn.execute(
            """
            INSERT INTO unfallakte
                (az, unfalldatum, unfallort, bearbeiter_id, haftungsquote,
                 kurzbezeichnung, sachbearbeiter)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (az, unfalldatum, unfallort, bearbeiter_id, haftungsquote,
             kurzbezeichnung, sachbearbeiter)
        )
        conn.execute(
            """
            INSERT INTO aktivitaeten
                (akte_id, benutzer_id, aktion, beschreibung, tabelle, datensatz_id)
            VALUES (?, ?, 'akte_erstellt', ?, 'unfallakte', ?)
            """,
            (az, bearbeiter_id, f"Akte {az} angelegt (aus RA-Micro).", az)
        )
        row = conn.execute(
            "SELECT * FROM unfallakte WHERE az = ?", (az,)
        ).fetchone()
        logger.info("Akte on-demand angelegt: %s", az)
        return Unfallakte.from_row(row)


def erstelle_akte(aktenzeichen: str, unfalldatum: str = "",
                   bearbeiter_id: Optional[int] = None,
                   unfallort: Optional[str] = None,
                   haftungsquote: float = 100.0) -> "Unfallakte":
    """Legt eine neue Akte an. Alias für Rückwärtskompatibilität."""
    return erstelle_oder_hole_akte(
        az=aktenzeichen, unfalldatum=unfalldatum,
        bearbeiter_id=bearbeiter_id, unfallort=unfallort,
        haftungsquote=haftungsquote
    )


def hole_akte_by_id(akte_id: str) -> Optional["Unfallakte"]:
    """Gibt eine Akte anhand des AZ zurück. akte_id = az (TEXT)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM unfallakte WHERE az = ?", (str(akte_id),)
        ).fetchone()
        return Unfallakte.from_row(row) if row else None


def hole_akte_by_aktenzeichen(aktenzeichen: str) -> Optional["Unfallakte"]:
    return hole_akte_by_id(aktenzeichen)


def liste_akten(status: Optional[str] = None,
                bearbeiter_id: Optional[int] = None,
                suchbegriff: Optional[str] = None,
                limit: int = 50,
                offset: int = 0) -> list["Unfallakte"]:
    sql = "SELECT * FROM unfallakte WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if bearbeiter_id:
        sql += " AND bearbeiter_id = ?"
        params.append(bearbeiter_id)
    if suchbegriff:
        sql += " AND (az LIKE ? OR unfallort LIKE ?)"
        term = f"%{suchbegriff}%"
        params.extend([term, term])
    sql += " ORDER BY erstellt_am DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [Unfallakte.from_row(r) for r in rows]


def aktualisiere_akte(akte_id: str, bearbeiter_id: Optional[int] = None,
                       **felder) -> Optional["Unfallakte"]:
    erlaubte = {"status", "notizen", "unfallort", "bearbeiter_id",
                "haftungsquote", "unfalldatum", "kurzbezeichnung",
                "sachbearbeiter", "regulierung_status"}
    updates = {k: v for k, v in felder.items() if k in erlaubte}
    if not updates:
        return hole_akte_by_id(akte_id)
    if "status" in updates and updates["status"] not in GUELTIGE_STATUS:
        raise ValueError(f"Ungültiger Status: {updates['status']!r}")
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    params = list(updates.values()) + [str(akte_id)]
    with get_connection() as conn:
        conn.execute(
            f"UPDATE unfallakte SET {set_clause} WHERE az = ?", params
        )
        row = conn.execute(
            "SELECT * FROM unfallakte WHERE az = ?", (str(akte_id),)
        ).fetchone()
        return Unfallakte.from_row(row) if row else None


def loesche_akte(akte_id: str) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM unfallakte WHERE az = ?", (str(akte_id),)
        )
        return cursor.rowcount > 0


def zaehle_akten_by_status() -> dict[str, int]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as anzahl FROM unfallakte GROUP BY status"
        ).fetchall()
        return {r["status"]: r["anzahl"] for r in rows}
