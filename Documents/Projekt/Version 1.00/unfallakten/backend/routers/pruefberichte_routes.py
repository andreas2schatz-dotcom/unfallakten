"""
Modul 9b – Prüfberichte-Routen
================================
Persistenz-Endpunkte für gespeicherte Prüfberichte pro Akte.

Endpunkte:
  GET  /akten/<akte_id>/pruefberichte          Liste aller Prüfberichte
  POST /akten/<akte_id>/pruefberichte          Neuen Prüfbericht speichern
  DELETE /akten/<akte_id>/pruefberichte/<id>   Prüfbericht löschen
"""

import logging
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection

logger = logging.getLogger(__name__)

pruefberichte_bp = Blueprint(
    "pruefberichte",
    __name__,
    url_prefix="/akten/<path:akte_id>",
)


def _err(msg, status=400, **kw):
    return jsonify({"fehler": msg, "status": status, **kw}), status


def _ensure_columns():
    """
    Stellt sicher, dass alle benötigten Spalten in der pruefberichte-Tabelle
    vorhanden sind. Fügt fehlende Spalten via ALTER TABLE hinzu (idempotent).
    Wird beim ersten Request aufgerufen.
    """
    neue_spalten = [
        ("referenzwerkstatt_plz_ort", "TEXT"),
        ("abzug_nfa",                 "REAL"),
        ("auftraggeber",              "TEXT"),
        ("reparaturkosten_brutto",    "REAL"),
        ("reparaturkosten_netto_vor_pruefung", "REAL"),  # Alias-Feld
        ("fahrzeug_ez",               "TEXT"),
        ("schadennummer",             "TEXT"),
        ("abzuege_json",              "TEXT"),           # Detail-Abzüge als JSON
    ]
    with get_connection() as conn:
        # Erst prüfen ob Tabelle überhaupt existiert (Migration 4)
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='pruefberichte'"
        ).fetchone()
        if not exists:
            # Tabelle anlegen (Fallback wenn Migration 4 nicht gelaufen)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pruefberichte (
                    id                              INTEGER PRIMARY KEY,
                    akte_id                         TEXT    NOT NULL REFERENCES unfallakte(az),
                    pruefdienstleister              TEXT,
                    vorgangsnummer                  TEXT,
                    datum                           TEXT,
                    schadennummer                   TEXT,
                    auftraggeber                    TEXT,
                    reparaturkosten_brutto          REAL,
                    reparaturkosten_vor_pruefung    REAL,
                    reparaturkosten_netto_vor_pruefung REAL,
                    abzug_technisch                 REAL,
                    abzug_werkstattalternative      REAL,
                    abzug_nfa                       REAL,
                    abzug_gesamt                    REAL,
                    reparaturkosten_nach_pruefung   REAL,
                    referenzwerkstatt_name          TEXT,
                    referenzwerkstatt_adresse       TEXT,
                    referenzwerkstatt_plz_ort       TEXT,
                    referenzwerkstatt_entfernung    REAL,
                    ist_image_pdf                   INTEGER DEFAULT 0,
                    fahrzeug_hersteller             TEXT,
                    fahrzeug_typ                    TEXT,
                    fahrzeug_kennzeichen            TEXT,
                    fahrzeug_ez                     TEXT,
                    abzuege_json                    TEXT,
                    kuerzungen_json                 TEXT,
                    erfasst_am                      TEXT    DEFAULT (date('now')),
                    erfasst_von                     INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pruefberichte_akte ON pruefberichte(akte_id)")
        else:
            # Vorhandene Spalten ermitteln
            vorhandene = {
                row[1]
                for row in conn.execute("PRAGMA table_info(pruefberichte)").fetchall()
            }
            for spalte, typ in neue_spalten:
                if spalte not in vorhandene:
                    try:
                        conn.execute(f"ALTER TABLE pruefberichte ADD COLUMN {spalte} {typ}")
                        logger.info("pruefberichte: Spalte '%s' hinzugefügt", spalte)
                    except Exception as e:
                        logger.warning("ALTER TABLE pruefberichte ADD COLUMN %s: %s", spalte, e)


def _row_to_dict(row) -> dict:
    """Konvertiert eine SQLite-Row in ein sauberes Dict für die API-Response."""
    return {
        "id":                              row["id"],
        "akte_id":                         row["akte_id"],
        "pruefdienstleister":              row["pruefdienstleister"] or "",
        "vorgangsnummer":                  row["vorgangsnummer"] or "",
        "datum":                           row["datum"] or "",
        "schadennummer":                   row["schadennummer"] if "schadennummer" in row.keys() else "",
        "auftraggeber":                    row["auftraggeber"] if "auftraggeber" in row.keys() else "",
        "reparaturkosten_brutto":          row["reparaturkosten_brutto"] if "reparaturkosten_brutto" in row.keys() else None,
        "reparaturkosten_vor_pruefung":    row["reparaturkosten_vor_pruefung"],
        "reparaturkosten_netto_vor_pruefung": (
            row["reparaturkosten_netto_vor_pruefung"]
            if "reparaturkosten_netto_vor_pruefung" in row.keys()
            else row["reparaturkosten_vor_pruefung"]
        ),
        "abzug_technisch":                 row["abzug_technisch"],
        "abzug_werkstattalternative":      row["abzug_werkstattalternative"],
        "abzug_nfa":                       row["abzug_nfa"] if "abzug_nfa" in row.keys() else None,
        "abzug_gesamt":                    row["abzug_gesamt"],
        "reparaturkosten_nach_pruefung":   row["reparaturkosten_nach_pruefung"],
        "referenzwerkstatt_name":          row["referenzwerkstatt_name"] or "",
        "referenzwerkstatt_adresse":       row["referenzwerkstatt_adresse"] or "",
        "referenzwerkstatt_plz_ort":       row["referenzwerkstatt_plz_ort"] if "referenzwerkstatt_plz_ort" in row.keys() else "",
        "referenzwerkstatt_entfernung":    row["referenzwerkstatt_entfernung"],
        "ist_image_pdf":                   bool(row["ist_image_pdf"]),
        "fahrzeug_hersteller":             row["fahrzeug_hersteller"] or "",
        "fahrzeug_typ":                    row["fahrzeug_typ"] or "",
        "fahrzeug_kennzeichen":            row["fahrzeug_kennzeichen"] or "",
        "fahrzeug_ez":                     row["fahrzeug_ez"] if "fahrzeug_ez" in row.keys() else "",
        "abzuege_json":                    row["abzuege_json"] if "abzuege_json" in row.keys() else None,
        "erfasst_am":                      row["erfasst_am"] or "",
    }


# ── GET /akten/<akte_id>/pruefberichte ─────────────────────────────────────────

@pruefberichte_bp.route("/pruefberichte", methods=["GET"])
@login_erforderlich
def liste_pruefberichte(akte_id: str):
    """Alle Prüfberichte einer Akte laden."""
    _ensure_columns()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM pruefberichte WHERE akte_id = ? ORDER BY id DESC",
            (akte_id,)
        ).fetchall()
    return jsonify({"pruefberichte": [_row_to_dict(r) for r in rows]}), 200


# ── POST /akten/<akte_id>/pruefberichte ────────────────────────────────────────

@pruefberichte_bp.route("/pruefberichte", methods=["POST"])
@login_erforderlich
def erstelle_pruefbericht(akte_id: str):
    """Neuen Prüfbericht speichern."""
    _ensure_columns()

    daten = request.get_json(force=True, silent=True) or {}

    # Adresse: Wenn `referenzwerkstatt_plz_ort` separat übergeben wird, nutzen;
    # sonst versuchen aus `referenzwerkstatt_adresse` zu splitten (Legacy-Format:
    # "Musterstraße 1, 60599 Frankfurt" → letztes Segment wenn es mit Zahl beginnt)
    plz_ort  = daten.get("referenzwerkstatt_plz_ort", "") or ""
    adresse  = daten.get("referenzwerkstatt_adresse", "") or ""

    if not plz_ort and adresse:
        parts = adresse.split(", ")
        if len(parts) >= 2 and parts[-1] and parts[-1][0].isdigit():
            plz_ort = parts[-1]
            adresse = ", ".join(parts[:-1])

    import json as _json

    with get_connection() as conn:
        # Prüfen ob Akte existiert (on-demand anlegen via ramicro-Liste ist Sache des Aufrufers)
        akte = conn.execute(
            "SELECT az FROM unfallakte WHERE az = ?", (akte_id,)
        ).fetchone()
        if not akte:
            return _err(f"Akte {akte_id!r} nicht gefunden.", 404)

        cur = conn.execute("""
            INSERT INTO pruefberichte (
                akte_id,
                pruefdienstleister,
                vorgangsnummer,
                datum,
                schadennummer,
                auftraggeber,
                reparaturkosten_brutto,
                reparaturkosten_vor_pruefung,
                reparaturkosten_netto_vor_pruefung,
                abzug_technisch,
                abzug_werkstattalternative,
                abzug_nfa,
                abzug_gesamt,
                reparaturkosten_nach_pruefung,
                referenzwerkstatt_name,
                referenzwerkstatt_adresse,
                referenzwerkstatt_plz_ort,
                referenzwerkstatt_entfernung,
                ist_image_pdf,
                fahrzeug_hersteller,
                fahrzeug_typ,
                fahrzeug_kennzeichen,
                fahrzeug_ez,
                abzuege_json,
                erfasst_am,
                erfasst_von
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, date('now'), ?
            )
        """, (
            akte_id,
            daten.get("pruefdienstleister") or "",
            daten.get("vorgangsnummer") or "",
            daten.get("datum") or "",
            daten.get("schadennummer") or "",
            daten.get("auftraggeber") or "",
            daten.get("reparaturkosten_brutto"),
            daten.get("reparaturkosten_vor_pruefung"),
            daten.get("reparaturkosten_netto_vor_pruefung")
                or daten.get("reparaturkosten_vor_pruefung"),
            daten.get("abzug_technisch"),
            daten.get("abzug_werkstattalternative"),
            daten.get("abzug_nfa"),
            daten.get("abzug_gesamt"),
            daten.get("reparaturkosten_nach_pruefung"),
            daten.get("referenzwerkstatt_name") or "",
            adresse,
            plz_ort,
            daten.get("referenzwerkstatt_entfernung"),
            1 if daten.get("ist_image_pdf") else 0,
            daten.get("fahrzeug_hersteller") or "",
            daten.get("fahrzeug_typ") or "",
            daten.get("fahrzeug_kennzeichen") or "",
            daten.get("fahrzeug_ez") or "",
            _json.dumps(daten.get("abzuege_detail") or [], ensure_ascii=False),
            getattr(g, "benutzer_id", None),
        ))
        new_id = cur.lastrowid

        # Chronik-Eintrag
        try:
            from ..models.dokument import logge_aktivitaet
            abzug = daten.get("abzug_gesamt")
            dienstleister = daten.get("pruefdienstleister") or "Prüfbericht"
            beschreibung = f"Prüfbericht gespeichert: {dienstleister}"
            if abzug:
                beschreibung += f" · Abzug: {abzug:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
            logge_aktivitaet(
                aktion="pdf_import_pruefbericht",
                beschreibung=beschreibung,
                akte_id=akte_id,
                benutzer_id=getattr(g, "benutzer_id", None),
                tabelle="pruefberichte",
            )
        except Exception as log_err:
            logger.warning("Chronik-Eintrag für Prüfbericht fehlgeschlagen: %s", log_err)

        # Neu gespeicherten Datensatz zurückgeben
        row = conn.execute(
            "SELECT * FROM pruefberichte WHERE id = ?", (new_id,)
        ).fetchone()

    return jsonify({"pruefbericht": _row_to_dict(row)}), 201


# ── DELETE /akten/<akte_id>/pruefberichte/<pb_id> ──────────────────────────────

@pruefberichte_bp.route("/pruefberichte/<int:pb_id>", methods=["DELETE"])
@login_erforderlich
def loesche_pruefbericht(akte_id: str, pb_id: int):
    """Einzelnen Prüfbericht löschen."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM pruefberichte WHERE id = ? AND akte_id = ?",
            (pb_id, akte_id)
        ).fetchone()
        if not row:
            return _err(f"Prüfbericht {pb_id} nicht gefunden.", 404)
        conn.execute("DELETE FROM pruefberichte WHERE id = ?", (pb_id,))
    return jsonify({"geloescht": True, "id": pb_id}), 200
