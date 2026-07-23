"""
Modul 9 – Model: Abrechnungsschreiben, Regulierungspositionen, Prüfberichte
=============================================================================
Regulierungsverlauf: Mehrere Abrechnungsschreiben pro Akte mit
positionsgenauer Aufschlüsselung und Kürzungszuordnung.
"""

import json
import sqlite3
import logging
from dataclasses import dataclass, field
from typing import Optional
from ..db.database import get_connection

logger = logging.getLogger(__name__)

GUELTIGE_HAFTUNGSARTEN = ("vollhaftung", "mithaftung", "quote", "ablehnung")
GUELTIGE_PARSE_STATUS  = ("ausstehend", "erfolgreich", "teilweise", "manuell", "fehlgeschlagen")

POSITION_KEYS = (
    "reparaturkosten", "wiederbeschaffung", "restwert",
    "wertminderung", "nutzungsausfall", "mietwagenkosten",
    "sv_kosten", "abschleppkosten", "restkraftstoff", "standkosten",
    "anabmeldekosten", "schmerzensgeld", "sonstiges",
    # PDF-Parser Arten
    "reparatur_brutto", "reparatur_netto",
    "wbw", "wbw_netto", "wbw_brutto", "wba",
    "fahrzeugschaden", "kostenpauschale",
    "ra_gebuehren", "mwst_abzug", "pruefbericht_abzug",
    # Neue Keys (Migration 14+)
    "rep_gutachten_netto", "rep_rechnung_netto", "rep_rechnung_brutto",
    "verdienstausfall", "haushalt", "unkostenpauschale", "kostennb",
    "vorschuss",
    "sonstiges_wdm_1", "sonstiges_wdm_2", "sonstiges_wdm_3",
    "sonstiges_wdm_4", "sonstiges_wdm_5", "sonstiges_wdm_6",
)

POSITION_LABELS = {
    "reparaturkosten":  "Reparaturkosten",
    "wiederbeschaffung":"Wiederbeschaffung",
    "restwert":         "Restwert",
    "wertminderung":    "Wertminderung",
    "nutzungsausfall":  "Nutzungsausfall",
    "mietwagenkosten":  "Mietwagenkosten",
    "sv_kosten":        "SV-Kosten",
    "abschleppkosten":  "Abschleppkosten",
    "restkraftstoff":   "Restkraftstoff",
    "standkosten":      "Standkosten",
    "anabmeldekosten":  "An-/Abmeldekosten",
    "schmerzensgeld":   "Schmerzensgeld",
    "sonstiges":        "Sonstiges",
    "reparatur_brutto": "Reparaturkosten (brutto)",
    "reparatur_netto":  "Reparaturkosten (netto)",
    "wbw":              "Wiederbeschaffungswert",
    "wbw_netto":        "WBW (netto)",
    "wbw_brutto":       "WBW (brutto)",
    "wba":              "Wiederbeschaffungsaufwand",
    "fahrzeugschaden":  "Fahrzeugschaden",
    "kostenpauschale":  "Kostenpauschale",
    "ra_gebuehren":     "RA-Gebühren",
    "mwst_abzug":       "Abzug MwSt.",
    "pruefbericht_abzug": "Abzug Prüfbericht",
}


# ══════════════════════════════════════════════════════════════════════════════
# REGULIERUNG POSITIONEN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RegulierungPosition:
    id: Optional[int]
    abrechnungsschreiben_id: int
    position_key: str
    betrag_gefordert: float = 0.0
    betrag_reguliert: float = 0.0
    kuerzungsart_id: Optional[int] = None
    kuerzung_freitext: Optional[str] = None
    parser_erkannt: bool = False
    parser_konfidenz: Optional[float] = None
    fuer_klage_vorgemerkt: bool = False
    sv_stellungnahme_ausstehend: bool = False
    # Joined fields (not stored)
    kuerzungsart_bezeichnung: Optional[str] = None
    kuerzungsart_kategorie: Optional[str] = None
    standard_gegenargument: Optional[str] = None

    @property
    def kuerzung_betrag(self) -> float:
        return round(self.betrag_gefordert - self.betrag_reguliert, 2)

    @property
    def position_label(self) -> str:
        return POSITION_LABELS.get(self.position_key, self.position_key)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "RegulierungPosition":
        d = dict(row)
        d["parser_erkannt"]              = bool(d.get("parser_erkannt", 0))
        d["fuer_klage_vorgemerkt"]       = bool(d.get("fuer_klage_vorgemerkt", 0))
        d["sv_stellungnahme_ausstehend"] = bool(d.get("sv_stellungnahme_ausstehend", 0))
        known = cls.__dataclass_fields__
        return cls(**{k: d[k] for k in d if k in known})

    def as_dict(self) -> dict:
        return {
            "id":                           self.id,
            "abrechnungsschreiben_id":      self.abrechnungsschreiben_id,
            "position_key":                 self.position_key,
            "position_label":               self.position_label,
            "betrag_gefordert":             self.betrag_gefordert,
            "betrag_reguliert":             self.betrag_reguliert,
            "kuerzung_betrag":              self.kuerzung_betrag,
            "kuerzungsart_id":              self.kuerzungsart_id,
            "kuerzungsart_bezeichnung":     self.kuerzungsart_bezeichnung,
            "kuerzungsart_kategorie":       self.kuerzungsart_kategorie,
            "standard_gegenargument":       self.standard_gegenargument,
            "kuerzung_freitext":            self.kuerzung_freitext,
            "parser_erkannt":               self.parser_erkannt,
            "parser_konfidenz":             self.parser_konfidenz,
            "fuer_klage_vorgemerkt":        self.fuer_klage_vorgemerkt,
            "sv_stellungnahme_ausstehend":  self.sv_stellungnahme_ausstehend,
        }


# ══════════════════════════════════════════════════════════════════════════════
# ABRECHNUNGSSCHREIBEN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Abrechnungsschreiben:
    id: Optional[int]
    akte_id: int
    datum: str
    haftungsquote: float = 100.0
    haftungsart: str = "vollhaftung"
    versicherung: Optional[str] = None
    referenz_nr: Optional[str] = None
    haftungsbegruendung: Optional[str] = None
    gesamt_gefordert: float = 0.0
    gesamt_reguliert: float = 0.0
    dokument_id: Optional[int] = None
    parse_status: str = "manuell"
    notizen: Optional[str] = None
    erfasst_am: Optional[str] = None
    erfasst_von: Optional[int] = None
    positionen: list = field(default_factory=list)

    @property
    def gesamt_kuerzung(self) -> float:
        return round(self.gesamt_gefordert - self.gesamt_reguliert, 2)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Abrechnungsschreiben":
        d = dict(row)
        known = cls.__dataclass_fields__
        return cls(**{k: d[k] for k in d if k in known})

    def as_dict(self, mit_positionen: bool = True) -> dict:
        d = {
            "id":                   self.id,
            "akte_id":              self.akte_id,
            "datum":                self.datum,
            "versicherung":         self.versicherung,
            "referenz_nr":          self.referenz_nr,
            "haftungsquote":        self.haftungsquote,
            "haftungsart":          self.haftungsart,
            "haftungsbegruendung":  self.haftungsbegruendung,
            "gesamt_gefordert":     self.gesamt_gefordert,
            "gesamt_reguliert":     self.gesamt_reguliert,
            "gesamt_kuerzung":      self.gesamt_kuerzung,
            "dokument_id":          self.dokument_id,
            "parse_status":         self.parse_status,
            "notizen":              self.notizen,
            "erfasst_am":           self.erfasst_am,
        }
        if mit_positionen:
            d["positionen"] = [p.as_dict() for p in self.positionen]
        return d


# ══════════════════════════════════════════════════════════════════════════════
# PRÜFBERICHTE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Pruefbericht:
    id: Optional[int]
    akte_id: int
    datum: str
    abrechnungsschreiben_id: Optional[int] = None
    gutachter: Optional[str] = None
    dokument_id: Optional[int] = None
    parse_status: str = "manuell"
    kuerzungen_json: Optional[str] = None
    notizen: Optional[str] = None
    erfasst_am: Optional[str] = None
    erfasst_von: Optional[int] = None
    # PDF-Parser Felder
    pruefdienstleister: Optional[str] = None
    vorgangsnummer: Optional[str] = None
    schadennummer: Optional[str] = None
    reparaturkosten_vor_pruefung: Optional[float] = None
    abzug_technisch: Optional[float] = None
    abzug_werkstattalternative: Optional[float] = None
    abzug_gesamt: Optional[float] = None
    reparaturkosten_nach_pruefung: Optional[float] = None
    referenzwerkstatt_name: Optional[str] = None
    referenzwerkstatt_adresse: Optional[str] = None
    referenzwerkstatt_entfernung: Optional[float] = None
    ist_image_pdf: int = 0
    fahrzeug_hersteller: Optional[str] = None
    fahrzeug_typ: Optional[str] = None
    fahrzeug_kennzeichen: Optional[str] = None
    pruefdienstleister_id: Optional[int] = None

    @property
    def kuerzungen(self) -> list:
        if not self.kuerzungen_json:
            return []
        try:
            return json.loads(self.kuerzungen_json)
        except Exception:
            return []

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Pruefbericht":
        d = dict(row)
        known = cls.__dataclass_fields__
        return cls(**{k: d[k] for k in d if k in known})

    def as_dict(self) -> dict:
        return {
            "id":                               self.id,
            "akte_id":                          self.akte_id,
            "datum":                            self.datum,
            "abrechnungsschreiben_id":          self.abrechnungsschreiben_id,
            "gutachter":                        self.gutachter,
            "dokument_id":                      self.dokument_id,
            "parse_status":                     self.parse_status,
            "kuerzungen":                       self.kuerzungen,
            "notizen":                          self.notizen,
            "erfasst_am":                       self.erfasst_am,
            # PDF-Parser Felder
            "pruefdienstleister":               self.pruefdienstleister,
            "vorgangsnummer":                   self.vorgangsnummer,
            "schadennummer":                    self.schadennummer,
            "reparaturkosten_vor_pruefung":     self.reparaturkosten_vor_pruefung,
            "abzug_technisch":                  self.abzug_technisch,
            "abzug_werkstattalternative":       self.abzug_werkstattalternative,
            "abzug_gesamt":                     self.abzug_gesamt,
            "reparaturkosten_nach_pruefung":    self.reparaturkosten_nach_pruefung,
            "referenzwerkstatt_name":           self.referenzwerkstatt_name,
            "referenzwerkstatt_adresse":        self.referenzwerkstatt_adresse,
            "referenzwerkstatt_entfernung":     self.referenzwerkstatt_entfernung,
            "ist_image_pdf":                    bool(self.ist_image_pdf),
            "fahrzeug_hersteller":              self.fahrzeug_hersteller,
            "fahrzeug_typ":                     self.fahrzeug_typ,
            "fahrzeug_kennzeichen":             self.fahrzeug_kennzeichen,
            "pruefdienstleister_id":            self.pruefdienstleister_id,
        }


# ══════════════════════════════════════════════════════════════════════════════
# DB-FUNKTIONEN: ABRECHNUNGSSCHREIBEN
# ══════════════════════════════════════════════════════════════════════════════

def _lade_positionen(conn: sqlite3.Connection, abrechnung_id: int) -> list[RegulierungPosition]:
    rows = conn.execute(
        """
        SELECT rp.*,
               ka.bezeichnung  AS kuerzungsart_bezeichnung,
               ka.kategorie    AS kuerzungsart_kategorie,
               ka.standard_gegenargument
        FROM regulierung_positionen rp
        LEFT JOIN kuerzungsarten ka ON ka.id = rp.kuerzungsart_id
        WHERE rp.abrechnungsschreiben_id = ?
        ORDER BY rp.id
        """,
        (abrechnung_id,),
    ).fetchall()
    return [RegulierungPosition.from_row(r) for r in rows]


def hole_abrechnungsschreiben_by_akte(akte_id: int) -> list[Abrechnungsschreiben]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM abrechnungsschreiben WHERE akte_id = ? ORDER BY datum DESC, id DESC",
            (akte_id,),
        ).fetchall()
        result = []
        for row in rows:
            ab = Abrechnungsschreiben.from_row(row)
            ab.positionen = _lade_positionen(conn, ab.id)
            result.append(ab)
        return result


def hole_abrechnungsschreiben_by_id(abid: int) -> Optional[Abrechnungsschreiben]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM abrechnungsschreiben WHERE id = ?", (abid,)
        ).fetchone()
        if not row:
            return None
        ab = Abrechnungsschreiben.from_row(row)
        ab.positionen = _lade_positionen(conn, ab.id)
        return ab


def erstelle_abrechnungsschreiben(
    akte_id: int,
    datum: str,
    haftungsart: str,
    haftungsquote: float,
    bearbeiter_id: Optional[int] = None,
    **felder,
) -> Abrechnungsschreiben:
    if haftungsart not in GUELTIGE_HAFTUNGSARTEN:
        raise ValueError(f"Ungültige Haftungsart: {haftungsart!r}")

    erlaubt = {
        "versicherung", "referenz_nr", "haftungsbegruendung",
        "gesamt_gefordert", "gesamt_reguliert",
        "dokument_id", "parse_status", "notizen",
    }
    daten = {k: v for k, v in felder.items() if k in erlaubt}
    daten.update({
        "akte_id": akte_id, "datum": datum,
        "haftungsart": haftungsart, "haftungsquote": haftungsquote,
        "erfasst_von": bearbeiter_id,
    })

    positionen_daten = felder.get("positionen", [])

    spalten = list(daten.keys())
    werte   = list(daten.values())

    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        cur = conn.execute(
            f"INSERT INTO abrechnungsschreiben ({', '.join(spalten)}) "
            f"VALUES ({', '.join('?' * len(werte))})",
            werte,
        )
        abid = cur.lastrowid

        # Positionen anlegen
        gesamt_gefordert = 0.0
        gesamt_reguliert = 0.0
        for pos in positionen_daten:
            pkey = pos.get("position_key")
            if pkey not in POSITION_KEYS:
                continue
            bgefordert = float(pos.get("betrag_gefordert", 0.0))
            breguliert = float(pos.get("betrag_reguliert", 0.0))
            if bgefordert == 0.0 and breguliert == 0.0:
                continue

            kuerzungsart_id = pos.get("kuerzungsart_id")
            sv_flag = 0
            if kuerzungsart_id:
                row = conn.execute(
                    "SELECT sv_stellungnahme_erforderlich FROM kuerzungsarten WHERE id = ?",
                    (kuerzungsart_id,),
                ).fetchone()
                if row:
                    sv_flag = row["sv_stellungnahme_erforderlich"]

            conn.execute(
                """
                INSERT INTO regulierung_positionen
                    (abrechnungsschreiben_id, position_key,
                     betrag_gefordert, betrag_reguliert,
                     kuerzungsart_id, kuerzung_freitext,
                     fuer_klage_vorgemerkt, sv_stellungnahme_ausstehend)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    abid, pkey, bgefordert, breguliert,
                    kuerzungsart_id,
                    pos.get("kuerzung_freitext"),
                    int(pos.get("fuer_klage_vorgemerkt", False)),
                    sv_flag,
                ),
            )
            gesamt_gefordert += bgefordert
            gesamt_reguliert += breguliert

        # Gesamtsummen aktualisieren
        conn.execute(
            "UPDATE abrechnungsschreiben SET gesamt_gefordert=?, gesamt_reguliert=? WHERE id=?",
            (gesamt_gefordert, gesamt_reguliert, abid),
        )

        # Akte-Status anpassen
        if haftungsart == "ablehnung":
            pass  # Status bleibt
        elif gesamt_reguliert >= gesamt_gefordert and gesamt_gefordert > 0:
            conn.execute(
                "UPDATE unfallakte SET status='abgeschlossen' WHERE az=?", (akte_id,)
            )
        else:
            conn.execute(
                "UPDATE unfallakte SET status='in_regulierung' WHERE az=?", (akte_id,)
            )

        # Aktivität loggen
        conn.execute(
            """
            INSERT INTO aktivitaeten (akte_id, benutzer_id, aktion, beschreibung)
            VALUES (?, ?, 'abrechnung_erfasst', ?)
            """,
            (
                akte_id, bearbeiter_id,
                f"Abrechnungsschreiben erfasst: {gesamt_reguliert:.2f} € reguliert "
                f"({haftungsart}, {haftungsquote}%)",
            ),
        )

        row = conn.execute(
            "SELECT * FROM abrechnungsschreiben WHERE id=?", (abid,)
        ).fetchone()
        ab = Abrechnungsschreiben.from_row(row)
        ab.positionen = _lade_positionen(conn, abid)
        return ab


class PositionNichtGefunden(Exception):
    """Position existiert nicht oder gehört nicht zur erwarteten Akte/Abrechnung."""


def pruefe_position_ownership(
    conn: sqlite3.Connection,
    pos_id: int,
    abid: int,
    akte_id: int,
) -> None:
    """
    Bug 4: Stellt sicher, dass pos_id zu abid und abid zu akte_id gehört.
    Wirft PositionNichtGefunden wenn die Ownership nicht stimmt.
    """
    row = conn.execute(
        """
        SELECT rp.id
        FROM regulierung_positionen rp
        JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
        WHERE rp.id = ? AND rp.abrechnungsschreiben_id = ? AND ab.akte_id = ?
        """,
        (pos_id, abid, akte_id),
    ).fetchone()
    if not row:
        raise PositionNichtGefunden(
            f"Position {pos_id} gehört nicht zu Abrechnung {abid} / Akte {akte_id}."
        )


def aktualisiere_position(
    pos_id: int,
    abid: Optional[int] = None,
    akte_id: Optional[int] = None,
    **felder,
) -> Optional[RegulierungPosition]:
    """
    Aktualisiert eine Regulierungsposition.

    Bug 6: Gibt None zurück wenn keine bekannten Felder übergeben wurden
           (Unterschied zu „Position nicht gefunden" → None vom fetchone).
           Der Aufrufer muss leere Updates vor dem Aufruf abfangen.
    Bug 4: Wenn abid und akte_id übergeben werden, wird Ownership geprüft.
    """
    erlaubt = {
        "betrag_gefordert", "betrag_reguliert", "kuerzungsart_id",
        "kuerzung_freitext", "fuer_klage_vorgemerkt", "sv_stellungnahme_ausstehend",
        "typ_quelle",
    }
    updates = {k: v for k, v in felder.items() if k in erlaubt}
    if not updates:
        # Keine gültigen Felder → None mit explizitem Marker
        return None

    with get_connection() as conn:
        # Bug 4: Ownership-Prüfung
        if abid is not None and akte_id is not None:
            pruefe_position_ownership(conn, pos_id, abid, akte_id)

        # Automatisch sv_flag setzen wenn kuerzungsart_id gesetzt
        if "kuerzungsart_id" in updates and updates["kuerzungsart_id"]:
            row = conn.execute(
                "SELECT sv_stellungnahme_erforderlich FROM kuerzungsarten WHERE id=?",
                (updates["kuerzungsart_id"],),
            ).fetchone()
            if row and "sv_stellungnahme_ausstehend" not in updates:
                updates["sv_stellungnahme_ausstehend"] = row["sv_stellungnahme_erforderlich"]

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        cur = conn.execute(
            f"UPDATE regulierung_positionen SET {set_clause} WHERE id=?",
            list(updates.values()) + [pos_id],
        )
        if cur.rowcount == 0:
            return None  # Position existiert nicht

        # Gesamtsummen im Abrechnungsschreiben aktualisieren
        row2 = conn.execute(
            "SELECT abrechnungsschreiben_id FROM regulierung_positionen WHERE id=?",
            (pos_id,),
        ).fetchone()
        if row2:
            abrechnung_id = row2["abrechnungsschreiben_id"]
            conn.execute(
                """
                UPDATE abrechnungsschreiben
                SET gesamt_gefordert = (
                        SELECT COALESCE(SUM(betrag_gefordert),0)
                        FROM regulierung_positionen
                        WHERE abrechnungsschreiben_id = ?
                    ),
                    gesamt_reguliert = (
                        SELECT COALESCE(SUM(betrag_reguliert),0)
                        FROM regulierung_positionen
                        WHERE abrechnungsschreiben_id = ?
                    )
                WHERE id = ?
                """,
                (abrechnung_id, abrechnung_id, abrechnung_id),
            )

        row3 = conn.execute(
            """
            SELECT rp.*, ka.bezeichnung AS kuerzungsart_bezeichnung,
                   ka.kategorie AS kuerzungsart_kategorie,
                   ka.standard_gegenargument
            FROM regulierung_positionen rp
            LEFT JOIN kuerzungsarten ka ON ka.id = rp.kuerzungsart_id
            WHERE rp.id = ?
            """,
            (pos_id,),
        ).fetchone()
        return RegulierungPosition.from_row(row3) if row3 else None


def loesche_abrechnungsschreiben(abid: int) -> bool:
    """
    Bug 3: Setzt Akte-Status zurück auf 'offen' wenn keine weiteren
    Abrechnungsschreiben mehr existieren.
    """
    with get_connection() as conn:
        # Akte-ID vor dem Löschen merken
        ab_row = conn.execute(
            "SELECT akte_id FROM abrechnungsschreiben WHERE id=?", (abid,)
        ).fetchone()
        if not ab_row:
            return False

        akte_id = ab_row["akte_id"]
        cur = conn.execute(
            "DELETE FROM abrechnungsschreiben WHERE id=?", (abid,)
        )
        if cur.rowcount == 0:
            return False

        # Prüfen ob noch weitere Abrechnungen existieren
        verbleibend = conn.execute(
            "SELECT COUNT(*) AS n FROM abrechnungsschreiben WHERE akte_id=?",
            (akte_id,),
        ).fetchone()["n"]

        if verbleibend == 0:
            # Keine Regulierung mehr → Status zurücksetzen
            conn.execute(
                "UPDATE unfallakte SET status='offen' WHERE az=? AND status='in_regulierung'",
                (akte_id,),
            )

        return True


# ══════════════════════════════════════════════════════════════════════════════
# DB-FUNKTIONEN: PRÜFBERICHTE
# ══════════════════════════════════════════════════════════════════════════════

def hole_pruefberichte_by_akte(akte_id: int) -> list[Pruefbericht]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pruefberichte WHERE akte_id=? ORDER BY datum DESC",
            (akte_id,),
        ).fetchall()
        return [Pruefbericht.from_row(r) for r in rows]


def erstelle_pruefbericht(
    akte_id: int,
    datum: str,
    bearbeiter_id: Optional[int] = None,
    **felder,
) -> Pruefbericht:
    erlaubt = {
        "abrechnungsschreiben_id", "gutachter", "dokument_id",
        "parse_status", "kuerzungen_json", "notizen",
        # PDF-Parser Felder
        "pruefdienstleister", "vorgangsnummer", "schadennummer",
        "reparaturkosten_vor_pruefung", "abzug_technisch",
        "abzug_werkstattalternative", "abzug_gesamt",
        "reparaturkosten_nach_pruefung", "referenzwerkstatt_name",
        "referenzwerkstatt_adresse", "referenzwerkstatt_entfernung",
        "ist_image_pdf", "fahrzeug_hersteller", "fahrzeug_typ",
        "fahrzeug_kennzeichen", "pruefdienstleister_id",
    }
    daten = {k: v for k, v in felder.items() if k in erlaubt and v is not None}
    daten.update({"akte_id": akte_id, "datum": datum, "erfasst_von": bearbeiter_id})

    spalten = list(daten.keys())
    werte   = list(daten.values())
    with get_connection() as conn:
        # akte_id haelt in diesem Datenmodell das Aktenzeichen (Text), nicht
        # die (in unfallakte gar nicht existierende) numerische ID — die
        # deklarierte FK auf unfallakte(id) ist daher grundsaetzlich
        # inkompatibel; siehe erstelle_abrechnungsschreiben() fuer dasselbe
        # etablierte Muster.
        conn.execute("PRAGMA foreign_keys = OFF")
        cur = conn.execute(
            f"INSERT INTO pruefberichte ({', '.join(spalten)}) "
            f"VALUES ({', '.join('?' * len(werte))})",
            werte,
        )
        row = conn.execute(
            "SELECT * FROM pruefberichte WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return Pruefbericht.from_row(row)


# ══════════════════════════════════════════════════════════════════════════════
# AGGREGATION: KLAGEBETRAG
# ══════════════════════════════════════════════════════════════════════════════

def hole_klagebetrag(akte_id: int) -> dict:
    """
    Aggregiert alle für Klage vorgemerkten Positionen über alle
    Abrechnungsschreiben einer Akte.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT rp.position_key,
                   SUM(rp.betrag_gefordert)   AS gesamt_gefordert,
                   SUM(rp.betrag_reguliert)   AS gesamt_reguliert,
                   SUM(rp.betrag_gefordert - rp.betrag_reguliert) AS gesamt_kuerzung,
                   ka.bezeichnung             AS kuerzungsart,
                   ka.standard_gegenargument,
                   ka.rechtsgrundlagen
            FROM regulierung_positionen rp
            JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
            LEFT JOIN kuerzungsarten ka ON ka.id = rp.kuerzungsart_id
            WHERE ab.akte_id = ? AND rp.fuer_klage_vorgemerkt = 1
            GROUP BY rp.position_key, rp.kuerzungsart_id
            ORDER BY gesamt_kuerzung DESC
            """,
            (akte_id,),
        ).fetchall()

        positionen = []
        gesamt_kuerzung = 0.0
        for r in rows:
            d = dict(r)
            positionen.append(d)
            gesamt_kuerzung += d.get("gesamt_kuerzung", 0.0)

        return {
            "akte_id":          akte_id,
            "positionen":       positionen,
            "gesamt_kuerzung":  round(gesamt_kuerzung, 2),
        }
