"""
Modul 9 – Model: Kürzungsarten
================================
Stammdaten-Tabelle für Kürzungskategorien mit Gegenargumentation.
"""

import sqlite3
import logging
from dataclasses import dataclass
from typing import Optional
from ..db.database import get_connection

logger = logging.getLogger(__name__)

GUELTIGE_KATEGORIEN = (
    "fahrzeugschaden",
    "ersatzbeschaffung",
    "sonstiger_schaden",
    "technisch_gutachten",
)

KATEGORIE_LABEL = {
    "fahrzeugschaden":   "Fahrzeugschaden",
    "ersatzbeschaffung": "Ersatzbeschaffung",
    "sonstiger_schaden": "Sonstiger Schaden",
    "technisch_gutachten": "Technisch / Gutachten",
}


@dataclass
class Kuerzungsart:
    id: Optional[int]
    bezeichnung: str
    kategorie: str
    standard_gegenargument: Optional[str] = None
    rechtsgrundlagen: Optional[str] = None
    hinweis_intern: Optional[str] = None
    sv_stellungnahme_erforderlich: bool = False
    aktiv: bool = True
    sortierung: int = 0
    erstellt_am: Optional[str] = None

    @property
    def kategorie_label(self) -> str:
        return KATEGORIE_LABEL.get(self.kategorie, self.kategorie)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Kuerzungsart":
        d = dict(row)
        d["sv_stellungnahme_erforderlich"] = bool(d.get("sv_stellungnahme_erforderlich", 0))
        d["aktiv"] = bool(d.get("aktiv", 1))
        return cls(**{k: d[k] for k in d if k in cls.__dataclass_fields__})

    def as_dict(self) -> dict:
        return {
            "id":                               self.id,
            "bezeichnung":                      self.bezeichnung,
            "kategorie":                        self.kategorie,
            "kategorie_label":                  self.kategorie_label,
            "standard_gegenargument":           self.standard_gegenargument,
            "rechtsgrundlagen":                 self.rechtsgrundlagen,
            "hinweis_intern":                   self.hinweis_intern,
            "sv_stellungnahme_erforderlich":    self.sv_stellungnahme_erforderlich,
            "aktiv":                            self.aktiv,
            "sortierung":                       self.sortierung,
            "erstellt_am":                      self.erstellt_am,
        }


# ──────────────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────────────

def hole_alle_kuerzungsarten(nur_aktive: bool = False) -> list[Kuerzungsart]:
    sql = "SELECT * FROM kuerzungsarten"
    if nur_aktive:
        sql += " WHERE aktiv = 1"
    sql += " ORDER BY sortierung, bezeichnung"
    with get_connection() as conn:
        return [Kuerzungsart.from_row(r) for r in conn.execute(sql).fetchall()]


def hole_kuerzungsart_by_id(kid: int) -> Optional[Kuerzungsart]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM kuerzungsarten WHERE id = ?", (kid,)
        ).fetchone()
        return Kuerzungsart.from_row(row) if row else None


def erstelle_kuerzungsart(
    bezeichnung: str,
    kategorie: str,
    **felder,
) -> Kuerzungsart:
    if kategorie not in GUELTIGE_KATEGORIEN:
        raise ValueError(f"Ungültige Kategorie: {kategorie!r}")

    erlaubt = {
        "standard_gegenargument", "rechtsgrundlagen", "hinweis_intern",
        "sv_stellungnahme_erforderlich", "sortierung",
    }
    daten = {k: v for k, v in felder.items() if k in erlaubt}
    daten["bezeichnung"] = bezeichnung
    daten["kategorie"] = kategorie

    spalten = list(daten.keys())
    werte = list(daten.values())
    with get_connection() as conn:
        cur = conn.execute(
            f"INSERT INTO kuerzungsarten ({', '.join(spalten)}) "
            f"VALUES ({', '.join('?' * len(werte))})",
            werte,
        )
        row = conn.execute(
            "SELECT * FROM kuerzungsarten WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
        return Kuerzungsart.from_row(row)


def aktualisiere_kuerzungsart(kid: int, **felder) -> Optional[Kuerzungsart]:
    erlaubt = {
        "bezeichnung", "kategorie", "standard_gegenargument",
        "rechtsgrundlagen", "hinweis_intern",
        "sv_stellungnahme_erforderlich", "aktiv", "sortierung",
    }
    updates = {k: v for k, v in felder.items() if k in erlaubt}
    if not updates:
        return hole_kuerzungsart_by_id(kid)

    if "kategorie" in updates and updates["kategorie"] not in GUELTIGE_KATEGORIEN:
        raise ValueError(f"Ungültige Kategorie: {updates['kategorie']!r}")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE kuerzungsarten SET {set_clause} WHERE id = ?",
            list(updates.values()) + [kid],
        )
        row = conn.execute(
            "SELECT * FROM kuerzungsarten WHERE id = ?", (kid,)
        ).fetchone()
        return Kuerzungsart.from_row(row) if row else None
