"""
Model: Forderungshistorie (forderung_positionen)
=================================================
Trackt welche Schadenposition mit welchem Forderungsschreiben
zu welchem Datum gefordert wurde und ihren aktuellen Regulierungsstatus.

Kernlogik:
  - Beim Generieren eines Forderungsschreibens werden automatisch
    Zeilen für alle Positionen mit Betrag > 0 angelegt.
  - Jedes folgende Forderungsschreiben bekommt nur noch Positionen
    die NICHT den Status 'vollreguliert' haben.
  - Für die Klage: WHERE status IN ('gekuerzt', 'abgelehnt', 'teilreguliert')
                   OR fuer_klage = 1

Statusübergänge:
  gefordert → teilreguliert | vollreguliert | gekuerzt | abgelehnt
  (wird manuell oder durch den Abrechnungsschreiben-Parser aktualisiert)
"""

import sqlite3
import logging
from dataclasses import dataclass
from typing import Optional
from ..db.database import get_connection

logger = logging.getLogger(__name__)

# Alle gültigen Statuswerte
GUELTIGE_STATUS = ("gefordert", "teilreguliert", "vollreguliert", "gekuerzt", "abgelehnt")

# Feste Bezeichnungen für Standard-Schadenpositionen (für Dokumente)
POSITION_LABELS: dict[str, str] = {
    "reparaturkosten":     "Reparaturkosten",
    "rep_fiktiv_netto":    "Reparaturkosten lt. Gutachten (netto)",
    "rep_rechnung_netto":  "Reparaturkosten lt. Rechnung (netto)",
    "rep_rechnung_brutto": "Reparaturkosten lt. Rechnung (brutto)",
    "wiederbeschaffung":   "Wiederbeschaffungswert",
    "restwert":            "abzgl. Restwert",
    "wertminderung":       "Merkantile Wertminderung",
    "nutzungsausfall":     "Nutzungsausfallschaden",
    "mietwagenkosten":     "Mietwagenkosten",
    "sv_kosten":           "Sachverständigenkosten",
    "kostennb":            "Kosten der Nachbesichtigung",
    "abschleppkosten":     "Abschleppkosten",
    "standkosten":         "Standkosten",
    "anabmeldekosten":     "An-/Abmeldekosten",
    "schmerzensgeld":      "Schmerzensgeld",
    "verdienstausfall":    "Verdienstausfall",
    "haushalt":            "Haushaltsführungsschaden",
    "unkostenpauschale":   "Unkostenpauschale",
    "sonstiges":           "Sonstiges",
}


@dataclass
class ForderungPosition:
    id: Optional[int]
    akte_id: str
    position_key: str
    position_label: str
    betrag_gefordert: float
    betrag_reguliert: float = 0.0
    status: str = "gefordert"
    fuer_klage: bool = False
    forderungsschreiben_nr: int = 1
    datum: Optional[str] = None
    dokument_id: Optional[int] = None
    kuerzungsart_id: Optional[int] = None
    kuerzung_begruendung: Optional[str] = None
    erfasst_am: Optional[str] = None
    erfasst_von: Optional[int] = None

    @property
    def differenz(self) -> float:
        return round(self.betrag_gefordert - self.betrag_reguliert, 2)

    @property
    def ist_vollreguliert(self) -> bool:
        return self.status == "vollreguliert"

    @property
    def ist_offen(self) -> bool:
        return self.status == "gefordert"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ForderungPosition":
        d = dict(row)
        d["fuer_klage"] = bool(d.get("fuer_klage", 0))
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


# ══════════════════════════════════════════════════════════════════════════════
# SCHREIBEN-NUMMER ERMITTELN
# ══════════════════════════════════════════════════════════════════════════════

def naechste_schreiben_nr(akte_id: str) -> int:
    """Gibt die nächste Forderungsschreiben-Nummer für diese Akte zurück."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(forderungsschreiben_nr), 0) AS n "
            "FROM forderung_positionen WHERE akte_id = ?",
            (akte_id,)
        ).fetchone()
        return (row["n"] if row else 0) + 1


# ══════════════════════════════════════════════════════════════════════════════
# POSITIONEN ANLEGEN (beim Generieren eines Forderungsschreibens)
# ══════════════════════════════════════════════════════════════════════════════

def erfasse_forderung(
    akte_id: str,
    schaden: dict,
    dokument_id: Optional[int] = None,
    bearbeiter_id: Optional[int] = None,
    datum: Optional[str] = None,
) -> list[ForderungPosition]:
    """
    Legt Forderungsposition-Zeilen für ein neues Forderungsschreiben an.

    Nur Positionen mit Betrag > 0 werden erfasst.
    Positionen die bereits 'vollreguliert' sind werden übersprungen.
    Extras aus wdm_extras_json werden als 'extra_1'..'extra_6' gespeichert.

    Args:
        akte_id:      Aktenzeichen
        schaden:      Schaden-Dict aus word_service (SQLite-Werte)
        dokument_id:  ID des generierten Dokuments in der dokumente-Tabelle
        bearbeiter_id: Wer das Schreiben erstellt hat
        datum:        Datum des Schreibens (ISO, Standard: heute)

    Returns:
        Liste der angelegten ForderungPosition-Objekte
    """
    schreiben_nr = naechste_schreiben_nr(akte_id)

    # Bereits vollregulierte Positionen dieser Akte holen
    vollreguliert = _hole_vollregulierte_keys(akte_id)

    positionen: list[tuple] = []

    # Standard-Schadenpositionen
    for key, label in POSITION_LABELS.items():
        if key in vollreguliert:
            continue
        betrag = float(schaden.get(key) or 0)
        if betrag <= 0:
            continue
        # Restwert: wird im Schreiben als Abzug geführt — trotzdem positiv speichern
        positionen.append((key, label, betrag))

    # Extras (sonstige Schäden 1-6 aus wdm_extras_json)
    import json
    extras_raw = schaden.get("wdm_extras_json") or "[]"
    try:
        extras = json.loads(extras_raw) if isinstance(extras_raw, str) else (extras_raw or [])
        if not isinstance(extras, list):
            extras = []
    except Exception:
        extras = []

    for i, ex in enumerate(extras[:6], 1):
        betrag = float(ex.get("betrag") or ex.get("netto") or 0)
        label  = ex.get("label") or f"Sonstiger Schaden {i}"
        key    = f"extra_{i}"
        if betrag <= 0 or key in vollreguliert:
            continue
        positionen.append((key, label, betrag))

    if not positionen:
        logger.info("Keine offenen Positionen für Forderungsschreiben %s/%d.",
                    akte_id, schreiben_nr)
        return []

    with get_connection() as conn:
        ids = []
        for key, label, betrag in positionen:
            cur = conn.execute(
                """
                INSERT INTO forderung_positionen
                    (akte_id, dokument_id, forderungsschreiben_nr, datum,
                     position_key, position_label, betrag_gefordert,
                     status, erfasst_von)
                VALUES (?, ?, ?, COALESCE(?, date('now','localtime')),
                        ?, ?, ?, 'gefordert', ?)
                """,
                (akte_id, dokument_id, schreiben_nr, datum,
                 key, label, betrag, bearbeiter_id)
            )
            ids.append(cur.lastrowid)

        rows = conn.execute(
            f"SELECT * FROM forderung_positionen WHERE id IN "
            f"({','.join('?' * len(ids))})",
            ids
        ).fetchall()

    result = [ForderungPosition.from_row(r) for r in rows]
    logger.info(
        "Forderung %s Nr.%d erfasst: %d Positionen, Gesamt %.2f €",
        akte_id, schreiben_nr,
        len(result),
        sum(p.betrag_gefordert for p in result),
    )
    return result


def _hole_vollregulierte_keys(akte_id: str) -> set[str]:
    """Gibt position_keys zurück die für diese Akte bereits vollreguliert sind."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT position_key FROM forderung_positionen "
            "WHERE akte_id = ? AND status = 'vollreguliert'",
            (akte_id,)
        ).fetchall()
    return {r["position_key"] for r in rows}


# ══════════════════════════════════════════════════════════════════════════════
# LESEN
# ══════════════════════════════════════════════════════════════════════════════

def hole_forderung_positionen(
    akte_id: str,
    nur_offen: bool = False,
    fuer_klage: Optional[bool] = None,
) -> list[ForderungPosition]:
    """
    Gibt alle Forderungspositionen einer Akte zurück.

    Args:
        akte_id:    Aktenzeichen
        nur_offen:  Nur status != 'vollreguliert'
        fuer_klage: True → nur Klage-markierte, False → ohne, None → alle
    """
    sql = "SELECT * FROM forderung_positionen WHERE akte_id = ?"
    params: list = [akte_id]

    if nur_offen:
        sql += " AND status != 'vollreguliert'"
    if fuer_klage is True:
        sql += " AND fuer_klage = 1"
    elif fuer_klage is False:
        sql += " AND fuer_klage = 0"

    sql += " ORDER BY forderungsschreiben_nr, id"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [ForderungPosition.from_row(r) for r in rows]


def hole_forderung_nach_schreiben(akte_id: str) -> dict[int, list[ForderungPosition]]:
    """
    Gibt Forderungspositionen gruppiert nach Schreiben-Nummer zurück.

    Returns:
        { 1: [pos, pos, ...], 2: [...], ... }
    """
    alle = hole_forderung_positionen(akte_id)
    result: dict[int, list] = {}
    for pos in alle:
        result.setdefault(pos.forderungsschreiben_nr, []).append(pos)
    return result


def forderungs_zusammenfassung(akte_id: str) -> dict:
    """
    Gibt eine Zusammenfassung der Forderungshistorie zurück.
    Nützlich für das Frontend-Dashboard.
    """
    positionen = hole_forderung_positionen(akte_id)
    if not positionen:
        return {
            "anzahl_schreiben": 0,
            "gesamt_gefordert": 0.0,
            "gesamt_reguliert": 0.0,
            "offen":            0.0,
            "klagepotential":   0.0,
            "positionen_offen": 0,
            "positionen_gesamt": 0,
        }

    gesamt_gefordert = sum(p.betrag_gefordert for p in positionen)
    gesamt_reguliert = sum(p.betrag_reguliert for p in positionen)
    klagepotential   = sum(
        p.differenz for p in positionen
        if p.status in ("gekuerzt", "abgelehnt", "teilreguliert")
    )

    return {
        "anzahl_schreiben":  max((p.forderungsschreiben_nr for p in positionen), default=0),
        "gesamt_gefordert":  round(gesamt_gefordert, 2),
        "gesamt_reguliert":  round(gesamt_reguliert, 2),
        "offen":             round(gesamt_gefordert - gesamt_reguliert, 2),
        "klagepotential":    round(klagepotential, 2),
        "positionen_offen":  sum(1 for p in positionen if not p.ist_vollreguliert),
        "positionen_gesamt": len(positionen),
    }


# ══════════════════════════════════════════════════════════════════════════════
# AKTUALISIEREN (manuell oder via Abrechnungsschreiben-Parser)
# ══════════════════════════════════════════════════════════════════════════════

def aktualisiere_position(
    position_id: int,
    *,
    akte_id: str,
    status: Optional[str] = None,
    betrag_reguliert: Optional[float] = None,
    fuer_klage: Optional[bool] = None,
    kuerzungsart_id: Optional[int] = None,
    kuerzung_begruendung: Optional[str] = None,
) -> Optional[ForderungPosition]:
    """
    Aktualisiert Status und Regulierungsdaten einer Forderungsposition.
    Alle Feld-Parameter sind optional — nur übergebene Felder werden geändert.
    akte_id ist Pflicht: Positionen fremder Akten werden nie geändert
    (Rückgabe None).
    """
    updates: dict = {}

    if status is not None:
        if status not in GUELTIGE_STATUS:
            raise ValueError(f"Ungültiger Status: {status!r}. Erlaubt: {GUELTIGE_STATUS}")
        updates["status"] = status

    if betrag_reguliert is not None:
        if betrag_reguliert < 0:
            raise ValueError("betrag_reguliert darf nicht negativ sein.")
        updates["betrag_reguliert"] = betrag_reguliert

    if fuer_klage is not None:
        updates["fuer_klage"] = 1 if fuer_klage else 0

    if kuerzungsart_id is not None:
        updates["kuerzungsart_id"] = kuerzungsart_id

    if kuerzung_begruendung is not None:
        updates["kuerzung_begruendung"] = kuerzung_begruendung

    if not updates:
        return None

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE forderung_positionen SET {set_clause} "
            f"WHERE id = ? AND akte_id = ?",
            list(updates.values()) + [position_id, akte_id]
        )
        row = conn.execute(
            "SELECT * FROM forderung_positionen WHERE id = ? AND akte_id = ?",
            (position_id, akte_id)
        ).fetchone()
    return ForderungPosition.from_row(row) if row else None


def setze_klage_flag(akte_id: str, position_ids: list[int], fuer_klage: bool) -> int:
    """
    Setzt das Klage-Flag für mehrere Positionen gleichzeitig.
    Returns: Anzahl aktualisierter Zeilen.
    """
    if not position_ids:
        return 0
    placeholders = ",".join("?" * len(position_ids))
    with get_connection() as conn:
        cur = conn.execute(
            f"UPDATE forderung_positionen SET fuer_klage = ? "
            f"WHERE akte_id = ? AND id IN ({placeholders})",
            [1 if fuer_klage else 0, akte_id] + position_ids
        )
    return cur.rowcount
