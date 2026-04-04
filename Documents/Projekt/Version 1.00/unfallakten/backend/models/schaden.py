"""
Modul 1 – Models: Beteiligte, Schadenpositionen, Regulierung
=============================================================
Datenzugriffsschicht für die Kerndaten einer Unfallakte.
"""

import sqlite3
import logging
import dataclasses
from dataclasses import dataclass
from typing import Optional
from ..db.database import get_connection

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BETEILIGTE
# ══════════════════════════════════════════════════════════════════════════════

GUELTIGE_ROLLEN = ("mandant", "gegner", "zeuge", "sachverstaendiger", "sonstiger")


@dataclass
class Beteiligter:
    id: Optional[int]
    akte_id: int
    rolle: str
    name: str
    vorname: Optional[str] = None
    firma: Optional[str] = None
    anschrift: Optional[str] = None
    plz: Optional[str] = None
    ort: Optional[str] = None
    telefon: Optional[str] = None
    email: Optional[str] = None
    kfz_kennzeichen: Optional[str] = None
    kfz_typ: Optional[str] = None
    versicherung: Optional[str] = None
    vers_nr: Optional[str] = None
    schaden_nr: Optional[str] = None
    iban: Optional[str] = None
    notizen: Optional[str] = None
    anrede: Optional[str] = None
    vorsteuer: Optional[str] = "N"
    vertreter_name: Optional[str] = None
    vertreter_funktion: Optional[str] = None

    @property
    def vollstaendiger_name(self) -> str:
        if self.vorname:
            return f"{self.vorname} {self.name}"
        return self.name

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Beteiligter":
        known = {f.name for f in __import__('dataclasses').fields(cls)}
        return cls(**{k: row[k] for k in row.keys() if k in known})


def erstelle_beteiligten(akte_id: int, rolle: str, name: str,
                          **felder) -> Beteiligter:
    if rolle not in GUELTIGE_ROLLEN:
        raise ValueError(f"Ungültige Rolle: {rolle!r}. Erlaubt: {GUELTIGE_ROLLEN}")

    erlaubte = {"vorname", "firma", "anschrift", "plz", "ort", "telefon",
                "email", "kfz_kennzeichen", "kfz_typ", "versicherung",
                "vers_nr", "schaden_nr", "iban", "notizen"}
    daten = {k: v for k, v in felder.items() if k in erlaubte}

    spalten = ["akte_id", "rolle", "name"] + list(daten.keys())
    werte = [akte_id, rolle, name] + list(daten.values())
    platzhalter = ", ".join("?" * len(werte))

    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO beteiligte ({', '.join(spalten)}) VALUES ({platzhalter})",
            werte
        )
        row = conn.execute(
            "SELECT * FROM beteiligte WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return Beteiligter.from_row(row)


def hole_beteiligte_by_akte(akte_id: int,
                              rolle: Optional[str] = None) -> list[Beteiligter]:
    sql = "SELECT * FROM beteiligte WHERE akte_id = ?"
    params: list = [akte_id]
    if rolle:
        sql += " AND rolle = ?"
        params.append(rolle)
    sql += " ORDER BY rolle, name"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [Beteiligter.from_row(r) for r in rows]


def aktualisiere_beteiligten(beteiligter_id: int, **felder) -> Optional[Beteiligter]:
    erlaubte = {"name", "vorname", "firma", "anschrift", "plz", "ort",
                "telefon", "email", "kfz_kennzeichen", "kfz_typ",
                "versicherung", "vers_nr", "schaden_nr", "iban", "notizen"}
    updates = {k: v for k, v in felder.items() if k in erlaubte}
    if not updates:
        return None

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE beteiligte SET {set_clause} WHERE id = ?",
            list(updates.values()) + [beteiligter_id]
        )
        row = conn.execute(
            "SELECT * FROM beteiligte WHERE id = ?", (beteiligter_id,)
        ).fetchone()
        return Beteiligter.from_row(row) if row else None


def loesche_beteiligten(beteiligter_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM beteiligte WHERE id = ?", (beteiligter_id,)
        )
        return cursor.rowcount > 0


# ══════════════════════════════════════════════════════════════════════════════
# SCHADENPOSITIONEN
# ══════════════════════════════════════════════════════════════════════════════

_SCHADEN_SPALTEN_CACHE: set = set()


def _hole_schaden_spalten(conn) -> set:
    """Spalten von schadenpositionen — einmal pro Prozess gecacht.
    Schema ändert sich nur beim App-Start (Migrationen), nie im laufenden Betrieb."""
    global _SCHADEN_SPALTEN_CACHE
    if not _SCHADEN_SPALTEN_CACHE:
        _SCHADEN_SPALTEN_CACHE = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(schadenpositionen)").fetchall()
        }
    return _SCHADEN_SPALTEN_CACHE


SCHADEN_FELDER = [
    "reparaturkosten", "wiederbeschaffung", "restwert", "wertminderung",
    "nutzungsausfall", "mietwagenkosten", "sv_kosten", "abschleppkosten",
    "standkosten", "anabmeldekosten", "schmerzensgeld", "sonstiges",
    "sonstiges_beschr", "quelle", "erfasst_von",
    "verdienstausfall", "haushalt",
    "rep_gutachten_netto", "rep_gutachten_mwst",
    "unkostenpauschale", "wdm_extras_json", "wdm_info_json",
    "kostennb", "kostennb_ust",
    "rep_rechnung_netto", "rep_rechnung_brutto",
    "abrechnungsart",
    "sv_kosten_netto",       "sv_kosten_ust",
    "abschleppkosten_netto", "abschleppkosten_ust",
    "standkosten_netto",     "standkosten_ust",
    "anabmeldekosten_netto", "anabmeldekosten_ust",
    "mietwagenkosten_netto", "mietwagenkosten_ust",
]


@dataclass
class Schadenposition:
    id: Optional[int]
    akte_id: int
    reparaturkosten: float = 0.0
    wiederbeschaffung: float = 0.0
    restwert: float = 0.0
    wertminderung: float = 0.0
    nutzungsausfall: float = 0.0
    mietwagenkosten: float = 0.0
    sv_kosten: float = 0.0
    abschleppkosten: float = 0.0
    standkosten: float = 0.0
    anabmeldekosten: float = 0.0
    schmerzensgeld: float = 0.0
    sonstiges: float = 0.0
    sonstiges_beschr: Optional[str] = None
    quelle: str = "manuell"
    erfasst_am: Optional[str] = None
    erfasst_von: Optional[int] = None
    verdienstausfall: float = 0.0
    haushalt: float = 0.0
    rep_gutachten_netto: float = 0.0
    rep_gutachten_mwst: float = 0.0
    unkostenpauschale: float = 0.0
    wdm_extras_json: Optional[str] = None
    wdm_info_json: Optional[str] = None
    kostennb: float = 0.0
    kostennb_ust: float = 0.0
    rep_rechnung_netto: float = 0.0
    rep_rechnung_brutto: float = 0.0
    abrechnungsart: Optional[str] = None
    sv_kosten_netto: float = 0.0
    sv_kosten_ust: float = 0.0
    abschleppkosten_netto: float = 0.0
    abschleppkosten_ust: float = 0.0
    standkosten_netto: float = 0.0
    standkosten_ust: float = 0.0
    anabmeldekosten_netto: float = 0.0
    anabmeldekosten_ust: float = 0.0
    mietwagenkosten_netto: float = 0.0
    mietwagenkosten_ust: float = 0.0

    @property
    def gesamt_brutto(self) -> float:
        """
        Einheitliche Fahrzeugschaden-Logik:
          1. Effektiver Reparaturwert = max(rep_gutachten_netto, rep_rechnung_netto)
          2. Wenn WBW > 0: prüfe ob eff_rep > WBW-Restwert → Totalschaden
          3. Reparaturfall: eff_rep; Totalschaden: WBW-Restwert
        """
        rep_n  = self.rep_gutachten_netto or self.reparaturkosten or 0.0
        rep_rn = self.rep_rechnung_netto  or 0.0
        wbw    = self.wiederbeschaffung   or 0.0
        rst    = self.restwert            or 0.0

        # Effektiver Reparaturwert (netto): Rechnung hat Vorrang wenn höher
        eff_rep = rep_rn if (rep_rn > 0 and rep_rn > rep_n) else rep_n

        # Fahrzeugschaden:
        # WBW > 0 → prüfe ob Reparatur günstiger als WBW-Restwert
        #   Reparatur günstiger → eff_rep; sonst → WBW-Restwert (Totalschaden)
        # WBW = 0 → Reparaturschaden mit eff_rep
        if wbw > 0:
            netto_fahrzeug = wbw - rst
            if eff_rep > 0 and eff_rep <= netto_fahrzeug:
                fahrzeug = eff_rep       # Reparatur, WBW ausreichend
            else:
                fahrzeug = netto_fahrzeug  # Totalschaden (auch wenn eff_rep=0)
        else:
            fahrzeug = eff_rep           # kein WBW → Reparatur (oder 0)

        return (
            fahrzeug
            + (self.wertminderung    or 0.0)
            + (self.nutzungsausfall  or 0.0)
            + (self.mietwagenkosten  or 0.0)
            + (self.sv_kosten        or 0.0)
            + (self.abschleppkosten  or 0.0)
            + (self.standkosten      or 0.0)
            + (self.anabmeldekosten  or 0.0)
            + (self.schmerzensgeld   or 0.0)
            + (self.sonstiges        or 0.0)
            + (self.verdienstausfall or 0.0)
            + (self.haushalt         or 0.0)
            + (self.unkostenpauschale or 0.0)
            + (self.kostennb         or 0.0)
            + (self.kostennb_ust     or 0.0)
        )

    @property
    def als_dict(self) -> dict:
        """Gibt alle Positionen als dict zurück (für Word-Generierung)."""
        return {
            "reparaturkosten":   self.reparaturkosten,
            "wiederbeschaffung": self.wiederbeschaffung,
            "restwert":          self.restwert,
            "wertminderung":     self.wertminderung,
            "nutzungsausfall":   self.nutzungsausfall,
            "mietwagenkosten":   self.mietwagenkosten,
            "sv_kosten":         self.sv_kosten,
            "abschleppkosten":   self.abschleppkosten,
            "standkosten":       self.standkosten,
            "anabmeldekosten":   self.anabmeldekosten,
            "schmerzensgeld":    self.schmerzensgeld,
            "sonstiges":         self.sonstiges,
            "gesamt_brutto":     self.gesamt_brutto,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Schadenposition":
        keys = row.keys()
        d = {k: row[k] for k in keys if k in cls.__dataclass_fields__}
        # None-Werte für float-Felder auf 0.0 setzen —
        # SQLite liefert NULL wenn ein Feld nie beschrieben wurde.
        float_felder = {
            f.name for f in dataclasses.fields(cls)
            if f.type in ("float", float) or str(f.type) == "float"
        }
        for k in float_felder:
            if k in d and d[k] is None:
                d[k] = 0.0
        return cls(**d)


def setze_schadenpositionen(akte_id: int, bearbeiter_id: Optional[int] = None,
                             **positionen) -> Schadenposition:
    """
    Erstellt oder ersetzt die Schadenpositionen einer Akte.
    Schreibt nur Spalten die tatsächlich in der DB existieren (migrationsrobust).
    """
    erlaubte = {f for f in SCHADEN_FELDER if f not in ("erfasst_von",)}
    daten = {k: v for k, v in positionen.items() if k in erlaubte}
    daten["erfasst_von"] = bearbeiter_id

    with get_connection() as conn:
        # Tatsächlich vorhandene Spalten ermitteln (einmal pro Prozess gecacht)
        vorhandene = _hole_schaden_spalten(conn)
        daten = {k: v for k, v in daten.items() if k in vorhandene}

        existing = conn.execute(
            "SELECT id FROM schadenpositionen WHERE akte_id = ?", (akte_id,)
        ).fetchone()

        if existing:
            set_clause = ", ".join(f"{k} = ?" for k in daten)
            conn.execute(
                f"UPDATE schadenpositionen SET {set_clause} WHERE akte_id = ?",
                list(daten.values()) + [akte_id]
            )
        else:
            daten["akte_id"] = akte_id
            spalten = list(daten.keys())
            werte   = list(daten.values())
            conn.execute(
                f"INSERT INTO schadenpositionen ({', '.join(spalten)}) "
                f"VALUES ({', '.join('?' * len(werte))})",
                werte
            )

        conn.execute(
            "INSERT INTO aktivitaeten (akte_id, benutzer_id, aktion, beschreibung) "
            "VALUES (?, ?, 'schaden_aktualisiert', 'Schadenpositionen wurden aktualisiert.')",
            (akte_id, bearbeiter_id)
        )
        row = conn.execute(
            "SELECT * FROM schadenpositionen WHERE akte_id = ?", (akte_id,)
        ).fetchone()
        return Schadenposition.from_row(row)


def hole_schadenpositionen(akte_id: int) -> Optional[Schadenposition]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM schadenpositionen WHERE akte_id = ?", (akte_id,)
        ).fetchone()
        return Schadenposition.from_row(row) if row else None


# ══════════════════════════════════════════════════════════════════════════════
# REGULIERUNG
# ══════════════════════════════════════════════════════════════════════════════

GUELTIGE_REG_STATUS = ("offen", "teilreguliert", "vollreguliert", "abgelehnt")


@dataclass
class Regulierung:
    id: Optional[int]
    akte_id: int
    datum: str
    betrag_gefordert: float
    betrag_reguliert: float
    status: str
    vers_referenz: Optional[str] = None
    kuerz_begruendung: Optional[str] = None
    reguliert_positionen: Optional[str] = None
    erfasst_am: Optional[str] = None
    erfasst_von: Optional[int] = None

    @property
    def differenz(self) -> float:
        return round(self.betrag_gefordert - self.betrag_reguliert, 2)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Regulierung":
        return cls(**{k: row[k] for k in row.keys()
                      if k in cls.__dataclass_fields__})


def erstelle_regulierung(akte_id: int, datum: str, betrag_gefordert: float,
                          betrag_reguliert: float, bearbeiter_id: Optional[int] = None,
                          **felder) -> Regulierung:
    if betrag_reguliert < 0:
        raise ValueError("Regulierter Betrag kann nicht negativ sein.")

    status = felder.pop("status", "offen")
    if status not in GUELTIGE_REG_STATUS:
        raise ValueError(f"Ungültiger Status: {status!r}")

    # Automatischen Status ableiten
    if betrag_reguliert >= betrag_gefordert:
        status = "vollreguliert"
    elif betrag_reguliert > 0:
        status = "teilreguliert"

    erlaubte = {"vers_referenz", "kuerz_begruendung", "reguliert_positionen"}
    daten = {k: v for k, v in felder.items() if k in erlaubte}

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO regulierung
                (akte_id, datum, betrag_gefordert, betrag_reguliert,
                 status, erfasst_von, vers_referenz, kuerz_begruendung,
                 reguliert_positionen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (akte_id, datum, betrag_gefordert, betrag_reguliert,
             status, bearbeiter_id,
             daten.get("vers_referenz"),
             daten.get("kuerz_begruendung"),
             daten.get("reguliert_positionen"))
        )
        reg_id = cursor.lastrowid

        # Akte-Status ggf. aktualisieren
        if status == "vollreguliert":
            conn.execute(
                "UPDATE unfallakte SET status = 'abgeschlossen' WHERE az = ?",
                (akte_id,)
            )
        elif status in ("teilreguliert", "offen"):
            conn.execute(
                "UPDATE unfallakte SET status = 'in_regulierung' WHERE az = ?",
                (akte_id,)
            )

        # Aktivität loggen
        conn.execute(
            """
            INSERT INTO aktivitaeten (akte_id, benutzer_id, aktion, beschreibung)
            VALUES (?, ?, 'regulierung_eingetragen',
                    'Regulierung eingetragen: ' || ? || ' € (' || ? || ')')
            """,
            (akte_id, bearbeiter_id,
             str(betrag_reguliert), status)
        )

        row = conn.execute(
            "SELECT * FROM regulierung WHERE id = ?", (reg_id,)
        ).fetchone()
        return Regulierung.from_row(row)


def hole_regulierungen_by_akte(akte_id: int) -> list[Regulierung]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM regulierung WHERE akte_id = ? ORDER BY datum DESC",
            (akte_id,)
        ).fetchall()
        return [Regulierung.from_row(r) for r in rows]


def hole_regulierungsstatus(akte_id: int) -> dict:
    """Gibt den aktuellen Regulierungsstand einer Akte zurück."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM v_regulierungsstatus WHERE akte_id = ?",
            (akte_id,)
        ).fetchone()
        if not row:
            return {"betrag_gefordert": 0.0, "betrag_reguliert": 0.0,
                    "differenz": 0.0, "akte_status": "offen"}
        return dict(row)


# ══════════════════════════════════════════════════════════════════════════════
# PRD-14: Single Source of Truth – Abrechnungsart-Berechnung
# Einzige Stelle im gesamten System wo Abrechnungsart + Fahrzeugschaden
# berechnet wird. Frontend zeigt nur noch diesen Wert an.
# ══════════════════════════════════════════════════════════════════════════════

def berechne_abrechnungsart(s, vorsteuer: bool = False) -> dict:
    """
    Berechnet Abrechnungsart und Fahrzeugschaden aus einer Schadenposition.
    Spiegelt exakt ermittleAbrechnungsart() + calcBrutto() aus App.jsx.

    Args:
        s:          Schadenposition-Objekt oder dict
        vorsteuer:  True wenn Mandant vorsteuerabzugsberechtigt

    Returns:
        {
          "abrechnungsart":      "fiktiv" | "konkret" | "totalschaden",
          "fahrzeugschaden":     1234.56,
          "fahrzeugschaden_key": "rep_gutachten_netto" | "rep_rechnung_netto" | "wiederbeschaffung",
          "gesamt_brutto":       2345.67,
          "begruendung":         "...",
          "ist_130_fall":        False,
        }
    """
    import json as _json

    def g(k):
        if isinstance(s, dict):
            return float(s.get(k) or 0)
        return float(getattr(s, k, None) or 0)

    def attr(k):
        if isinstance(s, dict):
            return s.get(k)
        return getattr(s, k, None)

    rep_gut   = g("rep_gutachten_netto") or g("reparaturkosten")
    rep_rn    = g("rep_rechnung_netto")
    rep_rb    = g("rep_rechnung_brutto")
    wbw       = g("wiederbeschaffung")
    rst       = g("restwert")
    netto_fzg = wbw - rst

    hat_gutachten = rep_gut > 0
    hat_rechnung  = rep_rn  > 0
    hat_wbw       = wbw     > 0

    ist_130_fall = (
        hat_rechnung and hat_wbw
        and rep_rn > netto_fzg
        and rep_rn <= 1.3 * wbw
    )

    # Explizit gesetzte Abrechnungsart hat immer Vorrang
    explizit = (attr("abrechnungsart") or "").strip()
    if explizit in ("fiktiv", "konkret", "totalschaden"):
        art         = explizit
        begruendung = f"Manuell gesetzt: {art}"
    else:
        if hat_rechnung and hat_gutachten:
            vergleich = rep_rn if vorsteuer else (rep_rb or rep_rn * 1.19)
            if rep_gut > vergleich:
                art         = "fiktiv"
                begruendung = f"Gutachten ({rep_gut:.2f}\u00a0\u20ac) > Rechnung \u2192 fiktive Abrechnung"
            else:
                art         = "konkret"
                begruendung = "Rechnung g\u00fcnstiger als Gutachten \u2192 konkrete Abrechnung"
        elif hat_rechnung and not hat_gutachten:
            if not hat_wbw:
                art         = "konkret"
                begruendung = "Reparaturrechnung vorhanden, kein WBW \u2192 konkrete Abrechnung"
            elif rep_rn > 1.3 * wbw:
                art         = "totalschaden"
                begruendung = f"Rechnung ({rep_rn:.2f}\u00a0\u20ac) > 130\u00a0% WBW \u2192 wirtschaftlicher Totalschaden"
            elif rep_rn > netto_fzg:
                art         = "konkret"
                begruendung = "Rechnung > WBW\u2212Restwert, aber \u2264 130\u00a0% \u2192 130\u00a0%-Fall (konkret)"
            else:
                art         = "konkret"
                begruendung = "Reparaturrechnung \u2264 WBW\u2212Restwert \u2192 konkrete Abrechnung"
        elif hat_gutachten and not hat_rechnung:
            if not hat_wbw:
                art         = "fiktiv"
                begruendung = "Nur Gutachten, kein WBW \u2192 fiktive Abrechnung"
            elif rep_gut > netto_fzg:
                art         = "totalschaden"
                begruendung = f"Gutachten ({rep_gut:.2f}\u00a0\u20ac) > WBW\u2212Restwert \u2192 Totalschaden"
            else:
                art         = "fiktiv"
                begruendung = "Gutachten \u2264 WBW\u2212Restwert \u2192 fiktive Abrechnung"
        elif hat_wbw:
            art         = "totalschaden"
            begruendung = "Nur WBW ohne Reparaturkosten \u2192 Totalschaden"
        else:
            art         = "fiktiv"
            begruendung = "Keine Schadensdaten \u2192 fiktive Abrechnung (Fallback)"

    # Fahrzeugschaden-Betrag und zugehöriger DB-Key
    if art == "totalschaden":
        fahrzeug = netto_fzg if hat_wbw else 0.0
        fzg_key  = "wiederbeschaffung"
    elif art == "fiktiv":
        fahrzeug = rep_gut
        fzg_key  = "rep_gutachten_netto"
    else:  # konkret
        fahrzeug = rep_rn if rep_rn > 0 else rep_gut
        fzg_key  = "rep_rechnung_netto"

    # WDM-Extras einrechnen
    extras_summe = 0.0
    wdm_json = attr("wdm_extras_json")
    if wdm_json:
        try:
            extras = _json.loads(wdm_json)
            if isinstance(extras, list):
                extras_summe = sum(float(e.get("betrag") or 0) for e in extras)
        except Exception:
            pass

    gesamt = (
        fahrzeug
        + g("wertminderung")    + g("nutzungsausfall")  + g("mietwagenkosten")
        + g("sv_kosten")        + g("abschleppkosten")  + g("standkosten")
        + g("anabmeldekosten")  + g("schmerzensgeld")   + g("sonstiges")
        + g("verdienstausfall") + g("haushalt")         + (g("unkostenpauschale") or 0)
        + g("kostennb")         + g("kostennb_ust")
        + extras_summe
    )

    return {
        "abrechnungsart":      art,
        "fahrzeugschaden":     round(fahrzeug, 2),
        "fahrzeugschaden_key": fzg_key,
        "gesamt_brutto":       round(gesamt, 2),
        "begruendung":         begruendung,
        "ist_130_fall":        ist_130_fall,
    }
