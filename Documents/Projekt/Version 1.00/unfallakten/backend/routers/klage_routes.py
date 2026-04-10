"""
backend/routers/klage_routes.py
=================================
REST-Endpunkte für das Klage-Modul.

  GET  /akten/<az>/klage/daten           Alle Daten für den Klage-Tab laden
  GET  /akten/<az>/unfalldetails         Unfalldetails laden
  PUT  /akten/<az>/unfalldetails         Unfalldetails speichern
  PUT  /akten/<az>/klage/gericht         Gewähltes Gericht in SQLite speichern
  POST /akten/<az>/klage/rvg-berechnen   RVG-Vorschau berechnen
  POST /akten/<az>/klage/generieren      Klageschrift generieren + speichern
"""

import io
import json
import logging
import os
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify, g, send_file
from ..auth.middleware import login_erforderlich
from ..models.akte import hole_akte_by_id
from ..db.database import get_connection
from ..models.schaden import hole_schadenpositionen, hole_regulierungen_by_akte
from ..models.dokument import registriere_dokument
from ..word.klage_service import berechne_rvg, generiere_klageschrift, berechne_fahrzeugschaden
from ..word.word_service import KANZLEI_INFO, _lade_beteiligte_aus_ramicro
from ..models.schaden import (
    hole_schadenpositionen, hole_beteiligte_by_akte
)

logger = logging.getLogger(__name__)

unfalldetails_bp = Blueprint("unfalldetails", __name__,
                            url_prefix="/akten/<path:akte_id>/unfalldetails")

klage_bp = Blueprint("klage", __name__,
                     url_prefix="/akten/<path:akte_id>/klage")


def _j(d, s=200): return jsonify(d), s
def _err(msg, s=400): return jsonify({"fehler": msg}), s


def _lade_wdm_klage_vars(az: str) -> dict:
    """
    Lädt Klage-spezifische WDM-Variablen aus RA-Micro:
      SCHILD        – Unfallschilderung
      Z1, Z2, Z3    – Zeugen
      M-FAHRER      – Fahrer Mandantenfahrzeug
      G-FAHRER      – Fahrer Unfallgegner
      G-SNR         – Schadennummer Gegner
      G-KZ          – Kennzeichen Gegner
      M-KZ          – Kennzeichen Mandant
      QUOTEG        – Haftungsquote Gegenseite
      VERZUGAB      – Verzugseintritt (Datum)
      EA-AZ         – AZ Ermittlungsakte
      EA-ADRESS.NVName – Behörde Ermittlungsakte
      EA-ADRESS.ORT    – Ort Ermittlungsakte
      varSSTF       – Vorsteuerabzug J/N

    Gibt leeres Dict zurück wenn RA-Micro nicht aktiv.
    """
    KLAGE_VARS = {
        "varSCHILD",
        "varZ1", "varZ2", "varZ3",
        "varADRZ1", "varADRZ2", "varADRZ3",   # Zeugen-Adressen
        "varM-FAHRER", "varG-FAHRER",
        "varG-KZ", "varM-KZ",
        "varG-HV",                              # HPV-Name
        "varG-VN",                              # Versicherungsnummer Gegner
        "varQUOTEG", "varVERZUGAB", "varSCHREIBENVERZUG",
        "varEA-AZ", "varEA-ADRESS", "varPOLIZEI",
        "varANSP1", "varANSP2", "varANSP3",    # Haftungsbegründung
        "varVORST",                              # Vorsteuer (statt varSSTF)
        "varU-TAG", "varU-ORT",                 # Unfalldaten
    }
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
        az_basis = az.strip()

        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            # AZ in RA-Micro finden
            cur.execute("""
                SELECT TOP 1 a.sAktenNummer AS az_roh
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return {}
            az_roh = row["az_roh"]

            placeholders = ",".join([f"%(v{i})s" for i in range(len(KLAGE_VARS))])
            params = {f"v{i}": v for i, v in enumerate(KLAGE_VARS)}
            params["az_roh"] = az_roh
            cur.execute(f"""
                SELECT sName, CAST(Value AS nvarchar(2000)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_roh)s
                  AND sName IN ({placeholders})
                  AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(500)) NOT IN ('', '??')
            """, params)
            return {r["sName"]: (r["wert"] or "").strip() for r in cur.fetchall()}

    except Exception as e:
        cls_name = type(e).__name__
        if "NichtAktiv" in cls_name or "VerbindungsFehler" in cls_name:
            logger.debug("_lade_wdm_klage_vars: RA-Micro nicht aktiv.")
        else:
            logger.warning("_lade_wdm_klage_vars: Fehler AZ=%s: %s", az, e)
        return {}


def _mandant_ist_fahrer(ud, mandant, wdm_fahrer_raw):
    # type: (any, dict, str) -> bool
    """
    Prüft ob der Mandant selbst gefahren ist.
    Quellen (Priorität):
      1. SQLite unfalldetails.fahrer_mandant == Mandantenname oder 'siehe oben'
      2. WDM varM-FAHRER == Mandantenname oder 'siehe oben'
    """
    fahrer_sqlite = ((ud["fahrer_mandant"] if ud else None) or "").strip().lower()
    fahrer_wdm    = (wdm_fahrer_raw or "").strip().lower()
    fahrer        = fahrer_sqlite or fahrer_wdm

    if not fahrer:
        return False
    if fahrer == "siehe oben":
        return True

    if mandant:
        mandant_name = " ".join(filter(None, [
            (mandant.get("vorname") or "").strip(),
            (mandant.get("name")    or "").strip(),
        ])).strip().lower()
        if mandant_name and fahrer == mandant_name:
            return True

    return False


# ── Unfalldetails GET/PUT ─────────────────────────────────────────────────────

@unfalldetails_bp.route("", methods=["GET"])
@login_erforderlich
def hole_unfalldetails(akte_id: str):
    """
    GET /akten/<az>/unfalldetails
    Gibt SQLite-Daten zurück, befüllt leere Felder mit WDM-Werten als Prefill.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.aktenzeichen

    # force_wdm=1: WDM-Werte überschreiben SQLite (expliziter Import-Button)
    force_wdm = request.args.get("force_wdm", "0") == "1"

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM unfalldetails WHERE akte_id = ?", (az,)
        ).fetchone()

    sqlite_daten = dict(row) if row else {}

    # WDM laden
    wdm = _lade_wdm_klage_vars(az)

    def _wdm(key, default=""):
        v = (wdm.get(key) or "").strip()
        return v if v and v != "??" else default

    # Mapping: bei force_wdm=1 → WDM hat Vorrang, bei normalem GET → nur Prefill für leere Felder
    def merge(feld, wdm_key):
        wdm_val = _wdm(wdm_key)
        if force_wdm and wdm_val:
            return wdm_val          # WDM überschreibt
        if not sqlite_daten.get(feld):
            return wdm_val          # Prefill für leere Felder
        return sqlite_daten.get(feld) or ""

    # Haftungsquote aus WDM (QUOTEG = "100,00" oder "75,00")
    def _quoteg():
        if sqlite_daten.get("haftungsquote") not in (None, 100.0, 0.0):
            return sqlite_daten.get("haftungsquote")
        raw = _wdm("varQUOTEG")
        if raw:
            try:
                # Strip " EUR", Leerzeichen, dann Komma → Punkt
                clean = raw.replace("EUR", "").replace(" ", "").replace(",", ".")
                return float(clean)
            except ValueError:
                pass
        return sqlite_daten.get("haftungsquote") or 100.0

    merged = {
        # Aus SQLite (eigene Werte haben Vorrang)
        **sqlite_daten,
        # WDM-Prefills für leere Felder
        "schilderung":            merge("schilderung", "varSCHILD"),
        "zeuge_1":                merge("zeuge_1", "varZ1"),
        "zeuge_1_anschrift":      merge("zeuge_1_anschrift", "varADRZ1"),
        "zeuge_2":                merge("zeuge_2", "varZ2"),
        "zeuge_2_anschrift":      merge("zeuge_2_anschrift", "varADRZ2"),
        "zeuge_3":                merge("zeuge_3", "varZ3"),
        "zeuge_3_anschrift":      merge("zeuge_3_anschrift", "varADRZ3"),
        "fahrer_mandant":         merge("fahrer_mandant", "varM-FAHRER"),
        "fahrer_gegner":          merge("fahrer_gegner", "varG-FAHRER"),
        "ermittlungsakte_az":     merge("ermittlungsakte_az", "varEA-AZ"),
        "ermittlungsakte_behoerde": merge("ermittlungsakte_behoerde", "varPOLIZEI"),
        "ermittlungsakte_ort":    merge("ermittlungsakte_ort", "varEA-ADRESS"),
        "haftungsquote":          _quoteg(),
        "haftungsbegruendung":    merge("haftungsbegruendung", "varANSP1"),
        "vorsteuerabzug":         sqlite_daten.get("vorsteuerabzug") or
                                  (1 if _wdm("varVORST").upper() in ("J", "JA", "Y") else 0),
        # WDM-Rohdaten für Anzeige im Frontend (readonly)
        "_wdm_vorhanden":         bool(wdm),
        "_wdm_ghv":               _wdm("varG-HV"),           # HPV-Name
        "_wdm_schreivenVerzug":   _wdm("varSCHREIBENVERZUG"),# Mahnschreiben-Datum
        "_wdm_ansp":              _wdm("varANSP1"),           # Haftungsbegründung kurz
        "_wdm_verzugab":          _wdm("varSCHREIBENVERZUG") or _wdm("varVERZUGAB"),
        "_wdm_u_tag":             _wdm("varU-TAG"),           # Unfalldatum aus WDM
        "_wdm_u_ort":             _wdm("varU-ORT"),           # Unfallort aus WDM
        "_wdm_gegner_kz":         _wdm("varG-KZ"),
        "_wdm_mandant_kz":        _wdm("varM-KZ"),
        "_wdm_schadennummer":     _wdm("varG-SNR"),
    }

    return _j({"unfalldetails": merged})


@unfalldetails_bp.route("", methods=["PUT"])
@login_erforderlich
def speichere_unfalldetails(akte_id: str):
    """PUT /akten/<az>/unfalldetails – Anlegen oder Aktualisieren."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.aktenzeichen

    d = request.get_json(silent=True) or {}

    TEXT_FELDER = [
        "schilderung",
        "zeuge_1", "zeuge_1_anschrift",
        "zeuge_2", "zeuge_2_anschrift",
        "zeuge_3", "zeuge_3_anschrift",
        "ermittlungsakte_az", "ermittlungsakte_behoerde", "ermittlungsakte_ort",
        "fahrer_mandant", "fahrer_gegner",
        "haftungsbegruendung",
        "aktivlegitimation_typ",
        "aktivlegitimation_freigabe",
        "aktivlegitimation_datum",
    ]

    felder = {f: (d.get(f) or "").strip() or None for f in TEXT_FELDER}
    felder["vorsteuerabzug"] = 1 if d.get("vorsteuerabzug") else 0
    try:
        felder["haftungsquote"] = float(d.get("haftungsquote") or 100)
    except (TypeError, ValueError):
        felder["haftungsquote"] = 100.0

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM unfalldetails WHERE akte_id = ?", (az,)
        ).fetchone()

        if existing:
            set_sql = ", ".join(f"{k} = ?" for k in felder)
            conn.execute(
                f"UPDATE unfalldetails SET {set_sql}, geaendert_am = datetime('now','localtime') "
                f"WHERE akte_id = ?",
                (*felder.values(), az)
            )
        else:
            cols = ["akte_id"] + list(felder.keys())
            vals = [az] + list(felder.values())
            conn.execute(
                f"INSERT INTO unfalldetails ({', '.join(cols)}) VALUES ({', '.join(['?']*len(vals))})",
                vals
            )

        row = conn.execute(
            "SELECT * FROM unfalldetails WHERE akte_id = ?", (az,)
        ).fetchone()

    return _j({"unfalldetails": dict(row) if row else None})


# ── Klage-Daten laden ─────────────────────────────────────────────────────────

def _suche_gericht_nach_ort(unfallort: str) -> list:
    """
    Sucht das wahrscheinlichste Gericht für einen Unfallort.

    Matching-Priorität:
      1. Gerichtsort = Unfallort (exakt, case-insensitiv)
      2. Gerichtsort ist Teilwort im Unfallort (z.B. "Frankfurt" in "Frankfurt am Main")
      3. Gerichtsname enthält Unfallort-Hauptwort
      4. Teilstring-Match als Fallback

    Vermeidet falsche Treffer wie "Frankfurt an der Oder" wenn Unfallort
    "Frankfurt am Main" ist, indem der vollständige Gerichtsort verglichen wird.
    """
    if not unfallort:
        return []

    ort_norm = unfallort.strip().lower()
    # Hauptwort: erstes Token (z.B. "Frankfurt" aus "Frankfurt am Main")
    ort_haupt = ort_norm.split()[0] if ort_norm else ""

    kandidaten = []

    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            # Alle Gerichte laden die das Hauptwort irgendwo enthalten
            # (bewusst weit – Scoring danach verfeinert)
            cur.execute("""
                SELECT TOP 50
                    iAdressnummer  AS adressnr,
                    sNachname      AS name,
                    [sStraße]      AS strasse,
                    sPLZ           AS plz,
                    sOrt           AS ort
                FROM tblAdressen
                WHERE iAdressnummer >= 90000
                  AND (sNachname LIKE '%Amtsgericht%' OR sNachname LIKE '%Landgericht%')
                  AND (sNachname LIKE %(haupt)s OR sOrt LIKE %(haupt)s)
                ORDER BY sNachname ASC
            """, {"haupt": f"%{ort_haupt}%"})
            rows = cur.fetchall()

        for r in rows:
            name      = (r["name"] or "").strip()
            gericht_ort = (r["ort"] or "").strip().lower()
            name_low  = name.lower()
            score     = 0

            # ── Scoring ──────────────────────────────────────────────────────
            # Gerichtsort exakt = Unfallort (beste Übereinstimmung)
            if gericht_ort == ort_norm:
                score += 100

            # Gerichtsort ist Teilstring von Unfallort (z.B. "Frankfurt" in "Frankfurt am Main")
            # NUR wenn Gerichtsort mindestens so lang wie das Hauptwort
            elif gericht_ort and ort_norm.startswith(gericht_ort):
                # Längerer Match = besser (Frankfurt am Main > Frankfurt)
                score += 50 + len(gericht_ort)

            elif gericht_ort and gericht_ort.startswith(ort_haupt):
                # Gerichtsort beginnt mit Hauptwort ("Frankfurt an der Oder" beginnt mit "frankfurt")
                # Aber: wenn Unfallort länger ist und Gerichtsort abweicht → Abzug
                # Abzug proportional zur Abweichung der restlichen Tokens
                ort_rest_tokens     = set(ort_norm.split()[1:])
                gericht_rest_tokens = set(gericht_ort.split()[1:])
                gemeinsam = ort_rest_tokens & gericht_rest_tokens
                abweichung = len(ort_rest_tokens ^ gericht_rest_tokens)
                score += 20 + len(gemeinsam) * 5 - abweichung * 8

            # Gerichtsname enthält vollständigen Unfallort
            if ort_norm in name_low:
                score += 30
            elif ort_haupt in name_low:
                score += 15

            # Amtsgericht bevorzugen
            if "amtsgericht" in name_low:
                score += 3

            if score > 0:
                kandidaten.append({
                    "adressnr": r["adressnr"],
                    "name":     name,
                    "strasse":  (r["strasse"] or "").strip(),
                    "plz":      (r["plz"]     or "").strip(),
                    "ort":      (r["ort"]     or "").strip(),
                    "quelle":   "unfallort_match",
                    "_score":   score,
                })

        kandidaten.sort(key=lambda x: -x["_score"])

    except Exception as e:
        cls = type(e).__name__
        if "NichtAktiv" not in cls and "VerbindungsFehler" not in cls:
            logger.debug("_suche_gericht_nach_ort: %s", e)

    return kandidaten


def _lade_gericht_aus_ramicro(az: str):
    """
    Sucht in RA-Micro das zur Akte gehörende Gericht aus tblAktenBeteiligte.
    Kennzeichen: GER, GERICHT, BEH, AG, LG oder iBeteiligtenArt = 5 (Behörde).
    Gibt dict mit name/strasse/plz/ort oder None zurück.
    """
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
        import re as _re
        az_basis = az.strip()

        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # GUIDAkte holen
            cur.execute("""
                SELECT TOP 1 a.GUIDAkte
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return None
            guid_akte = row["GUIDAkte"]

            # Gericht/Behörde in Beteiligten suchen
            cur.execute("""
                SELECT TOP 1
                    b.sBeteiligtenKennzeichen AS kz,
                    adr.sErsteAdresszeile     AS erste,
                    adr.sNachname             AS name,
                    adr.sVorname              AS vorname,
                    adr.[sStraße]             AS strasse,
                    adr.sPLZ                  AS plz,
                    adr.sOrt                  AS ort,
                    adr.iAdressnummer         AS adressnr
                FROM tblAktenBeteiligte b
                INNER JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.GUIDAkte = %(guid)s
                  AND b.bDeaktiviert = 0
                  AND (
                      b.iBeteiligtenArt = 5
                      OR UPPER(b.sBeteiligtenKennzeichen) IN (
                          'GER','GERICHT','BEH','BEHOERDE','AG','LG','OLG',
                          'AMTSGERICHT','LANDGERICHT'
                      )
                      OR adr.sNachname LIKE '%Amtsgericht%'
                      OR adr.sNachname LIKE '%Landgericht%'
                  )
                ORDER BY
                    CASE WHEN adr.sNachname LIKE '%Amtsgericht%' THEN 0
                         WHEN adr.sNachname LIKE '%Landgericht%' THEN 1
                         ELSE 2 END ASC
            """, {"guid": guid_akte})
            g = cur.fetchone()
            if not g:
                return None

            erste  = (g["erste"]  or "").strip()
            name   = erste if erste else (g["name"] or "").strip()
            if not name:
                return None

            return {
                "adressnr": g["adressnr"],
                "name":     name,
                "strasse":  (g["strasse"] or "").strip(),
                "plz":      (g["plz"]     or "").strip(),
                "ort":      (g["ort"]     or "").strip(),
                "quelle":   "akte",
            }

    except Exception as e:
        cls = type(e).__name__
        if "NichtAktiv" not in cls and "VerbindungsFehler" not in cls:
            logger.debug("_lade_gericht_aus_ramicro(%s): %s", az, e)
        return None


@klage_bp.route("/daten", methods=["GET"])
@login_erforderlich
def hole_klage_daten(akte_id: str):
    """
    GET /akten/<az>/klage/daten
    Lädt alle Daten die der Klage-Tab benötigt:
    - Beteiligte (vorgeschlagen: GHPV)
    - Schadenpositionen (vorausgewählt wenn fuer_klage_vorgemerkt)
    - Letztes Verzugsdatum aus Forderungshistorie
    - RVG-Vorberechnung
    - Unfalldetails
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    # Migration 5: beteiligte.akte_id ist TEXT = Aktenzeichen
    # hole_beteiligte_by_akte() nutzen wie word_service – liefert Model-Objekte mit .kuerzel
    az = akte.aktenzeichen

    with get_connection() as conn:

        # Regulierungspositionen mit fuer_klage_vorgemerkt
        klage_pos = conn.execute(
            """SELECT rp.*, ab.versicherung, ab.datum AS ab_datum,
                      ka.bezeichnung AS kuerzung_bezeichnung
               FROM regulierung_positionen rp
               LEFT JOIN abrechnungsschreiben ab ON rp.abrechnungsschreiben_id = ab.id
               LEFT JOIN kuerzungsarten ka ON rp.kuerzungsart_id = ka.id
               WHERE ab.akte_id = ?
               ORDER BY ab.datum DESC, rp.id""",
            (az,)
        ).fetchall()

        # Abrechnungsschreiben (für Regulierungsstand)
        abrechnungen = conn.execute(
            "SELECT * FROM abrechnungsschreiben WHERE akte_id = ? ORDER BY datum DESC",
            (az,)
        ).fetchall()

        # Positionen je Abrechnung – inkl. Kürzungsart-Bezeichnung für Wizard
        ab_positionen = {}
        try:
            if abrechnungen:
                ab_ids = tuple(a["id"] for a in abrechnungen)
                placeholders = ",".join(["?"] * len(ab_ids))
                pos_rows = conn.execute(
                    f"""SELECT rp.*, ka.bezeichnung AS kuerzung_bezeichnung,
                               ka.standard_gegenargument
                        FROM regulierung_positionen rp
                        LEFT JOIN kuerzungsarten ka ON rp.kuerzungsart_id = ka.id
                        WHERE rp.abrechnungsschreiben_id IN ({placeholders})""",
                    ab_ids
                ).fetchall()
                for p in pos_rows:
                    ab_positionen.setdefault(p["abrechnungsschreiben_id"], []).append(dict(p))
        except Exception:
            pass

        # Kürzungsarten-Katalog für Wizard-Einwände-Panel
        kuerzungsarten_katalog = []
        try:
            ka_rows = conn.execute(
                """SELECT id, bezeichnung, kategorie, standard_gegenargument, hinweis_intern
                   FROM kuerzungsarten WHERE aktiv = 1 ORDER BY sortierung"""
            ).fetchall()
            kuerzungsarten_katalog = [dict(r) for r in ka_rows]
        except Exception:
            pass

        # Letztes Verzugsdatum: aus forderung_positionen (letztes Forderungsschreiben-Datum)
        # Tabelle existiert ab Migration 9 – safe fallback falls noch nicht vorhanden
        letztes_forderung = None
        try:
            letztes_forderung = conn.execute(
                "SELECT MAX(datum) AS datum FROM forderung_positionen WHERE akte_id = ?",
                (az,)
            ).fetchone()
        except Exception:
            pass

        # Unfalldetails – existiert ab Migration 22
        ud = None
        try:
            ud = conn.execute(
                "SELECT * FROM unfalldetails WHERE akte_id = ?", (az,)
            ).fetchone()
        except Exception:
            pass

    schaden = hole_schadenpositionen(az)
    # Beteiligte via Model-Funktion (liefert Objekte mit .kuerzel, .schaden_nr etc.)
    beteiligte_objs = hole_beteiligte_by_akte(az)

    # RA-Micro Fallback: wenn SQLite keinen Mandanten/Gegner enthält.
    # Wichtig: 'gericht'-Einträge (von speichere_gericht) dürfen den Fallback
    # nicht unterdrücken – daher Prüfung auf Parteien, nicht auf leere Liste.
    ra_beteiligte = {}
    _hat_parteien = any(
        getattr(b, "rolle", "") in ("mandant", "gegner")
        for b in beteiligte_objs
    )
    if not _hat_parteien:
        try:
            ra_beteiligte = _lade_beteiligte_aus_ramicro(az) or {}
        except Exception as e:
            logger.debug("RA-Micro Beteiligte Fallback: %s", e)

    # WDM-Daten für Klage laden (Verzug, Kennzeichen, Schadennummer)
    wdm = _lade_wdm_klage_vars(akte.aktenzeichen)
    def _wdm(key):
        v = (wdm.get(key) or "").strip()
        return v if v and v != "??" else ""

    # ── Schadenpositionen für Klage aufbereiten ──────────────────────────────
    def s(key): return float(getattr(schaden, key, None) or 0) if schaden else 0.0
    def sv(key): return getattr(schaden, key, None) if schaden else None

    schaden_dict = {
        "rep_gutachten_netto": s("rep_gutachten_netto"),
        "rep_rechnung_netto":  s("rep_rechnung_netto"),
        "rep_rechnung_brutto": s("rep_rechnung_brutto"),
        "reparaturkosten":     s("reparaturkosten"),
        "wiederbeschaffung":   s("wiederbeschaffung"),
        "restwert":            s("restwert"),
        "wertminderung":       s("wertminderung"),
        "sv_kosten":           s("sv_kosten"),
        "sv_kosten_netto":     s("sv_kosten_netto"),
        "sv_kosten_ust":       s("sv_kosten_ust"),
        "nutzungsausfall":     s("nutzungsausfall"),
        "mietwagenkosten":     s("mietwagenkosten"),
        "mietwagenkosten_netto": s("mietwagenkosten_netto"),
        "mietwagenkosten_ust": s("mietwagenkosten_ust"),
        "abschleppkosten":     s("abschleppkosten"),
        "abschleppkosten_netto": s("abschleppkosten_netto"),
        "abschleppkosten_ust": s("abschleppkosten_ust"),
        "standkosten":         s("standkosten"),
        "standkosten_netto":   s("standkosten_netto"),
        "standkosten_ust":     s("standkosten_ust"),
        "anabmeldekosten":     s("anabmeldekosten"),
        "kostennb":            s("kostennb"),
        "anabmeldekosten_netto": s("anabmeldekosten_netto"),
        "anabmeldekosten_ust": s("anabmeldekosten_ust"),
        "kostennb_ust":        s("kostennb_ust"),
        "schmerzensgeld":      s("schmerzensgeld"),
        "verdienstausfall":    s("verdienstausfall"),
        "haushalt":            s("haushalt"),
        "sonstiges":           s("sonstiges"),
        "sonstiges_beschr":    sv("sonstiges_beschr") or "",
        # None → _baue_tabelle setzt 30€-Default; 0.0 → kein Default
        "unkostenpauschale":   sv("unkostenpauschale"),
        "abrechnungsart":      sv("abrechnungsart") or "",
        "wdm_extras_json":     sv("wdm_extras_json") or "[]",
        "gesamt_brutto":       s("gesamt_brutto"),
    }
    # PRD-14: vorsteuer aus Mandanten-Beteiligtem übergeben
    _mandant_vst = next(
        (b for b in beteiligte_objs if getattr(b, "rolle", "") == "mandant"), None
    )
    _vorsteuer = str(getattr(_mandant_vst, "vorsteuer", "N") or "N").upper() in ("J", "Y", "JA", "1")
    fzg = berechne_fahrzeugschaden(schaden_dict, vorsteuer=_vorsteuer)

    # Alle möglichen Positionen
    pos_definitionen = [
        {"key": "fahrzeugschaden",  "label": fzg["label"] or "Fahrzeugschaden",
         "betrag": fzg["betrag"],   "vorschlag": fzg["betrag"] > 0},
        {"key": "wertminderung",    "label": "Wertminderung",
         "betrag": s("wertminderung"), "vorschlag": s("wertminderung") > 0},
        {"key": "sv_kosten",        "label": "Kosten des Sachverständigen (brutto)",
         "betrag": s("sv_kosten"),  "vorschlag": s("sv_kosten") > 0},
        {"key": "nutzungsausfall",  "label": "Nutzungsausfallschaden",
         "betrag": s("nutzungsausfall"), "vorschlag": s("nutzungsausfall") > 0},
        {"key": "mietwagenkosten",  "label": "Mietwagenkosten",
         "betrag": s("mietwagenkosten"), "vorschlag": s("mietwagenkosten") > 0},
        {"key": "abschleppkosten",  "label": "Abschleppkosten",
         "betrag": s("abschleppkosten"), "vorschlag": s("abschleppkosten") > 0},
        {"key": "standkosten",      "label": "Standkosten",
         "betrag": s("standkosten"), "vorschlag": s("standkosten") > 0},
        {"key": "anabmeldekosten",  "label": "An- und Abmeldekosten",
         "betrag": s("anabmeldekosten"), "vorschlag": s("anabmeldekosten") > 0},
        {"key": "unkostenpauschale","label": "Unkostenpauschale",
         "betrag": s("unkostenpauschale") or 30.0,
         "vorschlag": True},  # immer 30 €, immer vorschlagen
        {"key": "verdienstausfall", "label": "Verdienstausfall",
         "betrag": s("verdienstausfall"), "vorschlag": s("verdienstausfall") > 0},
        {"key": "haushalt",         "label": "Haushaltsführungsschaden",
         "betrag": s("haushalt"),   "vorschlag": s("haushalt") > 0},
        {"key": "schmerzensgeld",   "label": "Schmerzensgeld",
         "betrag": s("schmerzensgeld"), "vorschlag": s("schmerzensgeld") > 0},
        {"key": "kostennb",         "label": "Nachbesichtigungskosten",
         "betrag": s("kostennb") + s("kostennb_ust") if not _vorsteuer else s("kostennb"),
         "vorschlag": s("kostennb") > 0},
    ]

    # Sonstiges (Freitext-Position aus Schaden-Reiter)
    _sonstiges_val = s("sonstiges")
    _sonstiges_beschr = (sv("sonstiges_beschr") or "Sonstiges").strip() or "Sonstiges"
    if _sonstiges_val > 0:
        pos_definitionen.append({
            "key": "sonstiges", "label": _sonstiges_beschr,
            "betrag": _sonstiges_val, "vorschlag": True,
        })

    # WDM-Extras (sonstige Schäden aus WDM)
    if schaden and schaden.wdm_extras_json:
        try:
            extras = json.loads(schaden.wdm_extras_json)
            for e in (extras or []):
                betrag = float(e.get("betrag_g") or e.get("betrag") or e.get("netto") or 0)
                if betrag > 0:
                    pos_definitionen.append({
                        "key":      f"extra_{e.get('key', e.get('label', '?'))}",
                        "label":    e.get("bezeichnung") or e.get("label") or "Sonstiger Schaden",
                        "betrag":   betrag,
                        "vorschlag": True,
                    })
        except Exception:
            pass

    # Vorauswahl: vorgeschlagen ODER fuer_klage_vorgemerkt in regulierung_positionen
    klage_keys = set()
    for kp in klage_pos:
        if kp["fuer_klage_vorgemerkt"]:
            klage_keys.add(kp["position_key"])

    for p in pos_definitionen:
        p["checked"] = p["vorschlag"] or (p["key"] in klage_keys)

    # ── Beteiligte aufbereiten ────────────────────────────────────────────────
    def b_dict(b):
        def _get(key, default=""):
            try:
                return getattr(b, key, None) or default
            except Exception:
                return default
        return {
            "id":                _get("id", 0),
            "rolle":             _get("rolle"),
            "name":              _get("name"),
            "vorname":           _get("vorname"),
            "firma":             _get("firma"),
            "anschrift":         _get("anschrift"),
            "plz":               _get("plz"),
            "ort":               _get("ort"),
            "anrede":            _get("anrede"),
            "versicherung":      _get("versicherung"),
            "schaden_nr":        _get("schaden_nr"),
            "kfz_kennzeichen":   _get("kfz_kennzeichen"),
            "kuerzel":           _get("kuerzel"),
            "vertreter_name":    _get("vertreter_name"),
            "vertreter_funktion":_get("vertreter_funktion"),
            "ist_halter":        int(_get("ist_halter", 0)),
        }

    alle_bet = [b_dict(b) for b in beteiligte_objs]

    # RA-Micro Fallback: Parteien aus RA-Micro ergänzen wenn keine in SQLite
    if not _hat_parteien and ra_beteiligte:
        for rolle_key in ("mandant", "gegner"):
            rb = ra_beteiligte.get(rolle_key)
            if rb and isinstance(rb, dict):
                alle_bet.append({
                    "id":            rb.get("id", 0),
                    "rolle":         rolle_key,
                    "name":          rb.get("name") or "",
                    "vorname":       rb.get("vorname") or "",
                    "firma":         rb.get("firma") or "",
                    "anschrift":     rb.get("anschrift") or "",
                    "plz":           rb.get("plz") or "",
                    "ort":           rb.get("ort") or "",
                    "anrede":        rb.get("anrede") or "",
                    "versicherung":  rb.get("versicherung") or "",
                    "schaden_nr":    rb.get("schaden_nr") or "",
                    "kfz_kennzeichen": rb.get("kfz_kennzeichen") or "",
                    "kuerzel":       rb.get("kuerzel") or "",
                })
    # Rollen und Vorschläge setzen
    for b in alle_bet:
        rolle   = (b.get("rolle") or "").lower()
        kz      = (b.get("kuerzel") or "").upper()
        ist_mandant = rolle == "mandant"
        ist_ghpv    = kz in ("GHPV", "GH", "GHV", "GBEV", "HPV") or rolle == "gegner"

        # Klage-Rolle: Mandant → Kläger, alle anderen Gegner/GHPV → Beklagte
        b["rolle_klage"]        = "klaeger" if ist_mandant else "beklagter"
        b["vorschlag_beklagter"] = ist_ghpv and not ist_mandant

        # WDM-Anreicherung: Schadennummer + Kennzeichen wenn in SQLite leer
        if not b.get("schaden_nr") and _wdm("varG-SNR") and b["vorschlag_beklagter"]:
            b["schaden_nr"] = _wdm("varG-SNR")
        if not b.get("versicherung") and _wdm("varG-HV") and b["vorschlag_beklagter"]:
            b["versicherung"] = _wdm("varG-HV")
        if not b.get("kfz_kennzeichen") and rolle == "gegner" and _wdm("varG-KZ"):
            b["kfz_kennzeichen"] = _wdm("varG-KZ")

    # ── Verzugsdatum bestimmen ────────────────────────────────────────────────
    verzug_datum = None
    if letztes_forderung and letztes_forderung["datum"]:
        verzug_datum = letztes_forderung["datum"]
    # WDM-Fallback: VERZUGAB
    if not verzug_datum:
        verzug_datum = _wdm("varSCHREIBENVERZUG") or _wdm("varVERZUGAB") or None

    # ── Gericht-Vorschlag ────────────────────────────────────────────────────
    # Prio 1a: Beteiligte mit rolle=gericht in SQLite
    # Prio 1b: Gericht direkt aus RA-Micro tblAktenBeteiligte
    # Prio 2:  Unfallort → Gericht in RA-Micro suchen
    gericht_vorschlag = None
    gericht_quelle    = None

    # 1a – SQLite
    for b in alle_bet:
        if (b.get("rolle") or "").lower() == "gericht":
            gericht_vorschlag = {
                "adressnr": b.get("id"),
                "name":     b.get("firma") or b.get("versicherung") or b.get("name") or "Gericht",
                "strasse":  b.get("anschrift") or "",
                "plz":      b.get("plz") or "",
                "ort":      b.get("ort") or "",
                "quelle":   "akte",
            }
            gericht_quelle = "akte"
            break

    # 1b – RA-Micro tblAktenBeteiligte (auch wenn SQLite leer)
    if not gericht_vorschlag:
        try:
            ra_gericht = _lade_gericht_aus_ramicro(az)
            if ra_gericht:
                gericht_vorschlag = ra_gericht
                gericht_quelle    = "akte"
        except Exception as e:
            logger.debug("RA-Micro Gericht: %s", e)

    # 2 – Unfallort-Matching als letzter Fallback
    if not gericht_vorschlag:
        unfallort = (akte.unfallort or "").strip() or (_wdm("varU-ORT") or "").strip()
        if unfallort:
            try:
                kandidaten = _suche_gericht_nach_ort(unfallort)
                if kandidaten:
                    gericht_vorschlag = kandidaten[0]
                    gericht_quelle    = kandidaten[0].get("quelle", "unfallort")
            except Exception as e:
                logger.debug("Gericht-Vorschlag: %s", e)

    # Gericht aus Parteien-Liste entfernen (wird separat via gericht_vorschlag behandelt)
    alle_bet = [b for b in alle_bet if (b.get("rolle") or "").lower() != "gericht"]

    # ── RVG-Vorberechnung ─────────────────────────────────────────────────────
    klagebetrag = sum(p["betrag"] for p in pos_definitionen if p["checked"])
    rvg = berechne_rvg(klagebetrag, erstellt_am=akte.erstellt_am)
    rvg["streitwert"] = klagebetrag

    # ── Aktivlegitimation aus unfalldetails + Fahrer-Ermittlung ──────────────
    _ud_dict = dict(ud) if ud else {}
    # WDM-Fallback: schilderung aus varSCHILD wenn SQLite leer
    if not _ud_dict.get("schilderung"):
        _wdm_schild = _wdm("varSCHILD")
        if _wdm_schild:
            _ud_dict["schilderung"] = _wdm_schild

    # Mandant ist Fahrer wenn varM-FAHRER == Mandantenname oder "siehe oben"
    _fahrer_wdm   = (_wdm("varM-FAHRER") or "").strip().lower()
    _mandant_name = ""
    _mandant_obj  = next(
        (b for b in beteiligte_objs if getattr(b, "rolle", "") == "mandant"), None
    )
    if _mandant_obj:
        _mandant_name = " ".join(filter(None, [
            getattr(_mandant_obj, "vorname", "") or "",
            getattr(_mandant_obj, "name", "")    or "",
        ])).strip().lower()

    mandant_ist_fahrer = bool(
        _fahrer_wdm and (
            _fahrer_wdm == "siehe oben"
            or (_mandant_name and _fahrer_wdm == _mandant_name)
        )
    ) or bool(_ud_dict.get("fahrer_mandant", ""))  # SQLite-Fallback

    aktivlegitimation = {
        "typ":              _ud_dict.get("aktivlegitimation_typ")      or "eigentum",
        "freigabe_status":  _ud_dict.get("aktivlegitimation_freigabe") or "freigabe",
        "datum_freigabe":   _ud_dict.get("aktivlegitimation_datum")    or None,
        "mandant_ist_fahrer": mandant_ist_fahrer,
    }

    with get_connection() as conn2:
        row = conn2.execute("SELECT wert FROM konfiguration WHERE schluessel='lg_grenzwert'").fetchone()
        lg_grenzwert = int(row["wert"]) if row else 10000

    return _j({
        "beteiligte":         alle_bet,
        "positionen":         [p for p in pos_definitionen if p["betrag"] > 0],
        "unfalldetails":      _ud_dict,
        "verzug_datum":       verzug_datum,
        "rvg":                rvg,
        "abrechnungen":       [
            {**dict(a), "positionen": ab_positionen.get(a["id"], [])}
            for a in abrechnungen
        ],
        "schaden":            schaden_dict,
        "gericht_vorschlag":  gericht_vorschlag,
        "gericht_quelle":     gericht_quelle,
        "unfallort":          akte.unfallort or (_wdm("varU-ORT") if wdm else "") or "",
        "aktivlegitimation":  aktivlegitimation,
        "kuerzungsarten":     kuerzungsarten_katalog,
        "lg_grenzwert":       lg_grenzwert,
    })


# ── RVG neu berechnen ─────────────────────────────────────────────────────────

@klage_bp.route("/rvg-berechnen", methods=["POST"])
@login_erforderlich
def rvg_berechnen(akte_id: str):
    """POST /akten/<az>/klage/rvg-berechnen – RVG für gegebenen Streitwert."""
    d = request.get_json(silent=True) or {}
    try:
        streitwert = float(d.get("streitwert") or 0)
        faktor     = float(d.get("faktor") or 1.3)
    except (TypeError, ValueError):
        return _err("streitwert und faktor müssen Zahlen sein.", 422)
    akte = hole_akte_by_id(akte_id)
    rvg = berechne_rvg(streitwert, faktor,
                       erstellt_am=akte.erstellt_am if akte else None)
    rvg["streitwert"] = streitwert
    return _j({"rvg": rvg})


# ── Klageschrift generieren ───────────────────────────────────────────────────

@klage_bp.route("/generieren", methods=["POST"])
@login_erforderlich
def generiere_klage(akte_id: str):
    """
    POST /akten/<az>/klage/generieren
    Body: { klage_config: { beklagte, positionen, mit_schmerzensgeld,
                             schmerzensgeld_mindest, verzugsdatum, zinsen_ab,
                             rvg_override } }
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    body = request.get_json(silent=True) or {}
    klage_cfg = body.get("klage_config") or {}

    # PRD-24: Wizard-Overrides auslesen (explizit, keine Mehrdeutigkeit)
    # None = kein Override → Backend nutzt DB-Wert
    # Wert = Override → Wizard-Wert hat Vorrang
    overrides = body.get("overrides") or {}

    def _override(key, db_val):
        """Override vorhanden und nicht None → nehmen. Sonst DB-Wert."""
        v = overrides.get(key)
        return v if v is not None else db_val

    # Daten zusammenstellen (analog word_service._lade_akte_daten)
    # Migration 5: immer akte.aktenzeichen statt rohem URL-Parameter verwenden
    az = akte.aktenzeichen

    # Schadendaten für _baue_tabelle in klage_service
    schaden = hole_schadenpositionen(az)
    def s(key): return float(getattr(schaden, key, None) or 0) if schaden else 0.0
    def sv(key): return getattr(schaden, key, None) if schaden else None
    schaden_dict = {
        # Fahrzeugschaden
        "rep_gutachten_netto": s("rep_gutachten_netto"),
        "rep_rechnung_netto":  s("rep_rechnung_netto"),
        "rep_rechnung_brutto": s("rep_rechnung_brutto"),
        "reparaturkosten":     s("reparaturkosten"),
        "wiederbeschaffung":   s("wiederbeschaffung"),
        "restwert":            s("restwert"),
        "wertminderung":       s("wertminderung"),
        # Nebenkosten (netto+ust Felder für _netto_oder_brutto)
        "sv_kosten":           s("sv_kosten"),
        "sv_kosten_netto":     s("sv_kosten_netto"),
        "sv_kosten_ust":       s("sv_kosten_ust"),
        "nutzungsausfall":     s("nutzungsausfall"),
        "mietwagenkosten":     s("mietwagenkosten"),
        "mietwagenkosten_netto": s("mietwagenkosten_netto"),
        "mietwagenkosten_ust": s("mietwagenkosten_ust"),
        "abschleppkosten":     s("abschleppkosten"),
        "abschleppkosten_netto": s("abschleppkosten_netto"),
        "abschleppkosten_ust": s("abschleppkosten_ust"),
        "standkosten":         s("standkosten"),
        "anabmeldekosten":     s("anabmeldekosten"),
        "standkosten_netto":   s("standkosten_netto"),
        "anabmeldekosten_netto": s("anabmeldekosten_netto"),
        "anabmeldekosten_ust": s("anabmeldekosten_ust"),
        "standkosten_ust":     s("standkosten_ust"),
        "kostennb":            s("kostennb"),
        "kostennb_ust":        s("kostennb_ust"),
        "schmerzensgeld":      s("schmerzensgeld"),
        "verdienstausfall":    s("verdienstausfall"),
        "haushalt":            s("haushalt"),
        "sonstiges":           s("sonstiges"),
        "sonstiges_beschr":    sv("sonstiges_beschr") or "",
        # Unkostenpauschale: 0 wenn nicht gesetzt → _baue_tabelle fügt keinen 30€-Default ein
        "unkostenpauschale":   s("unkostenpauschale") if s("unkostenpauschale") > 0
                               else (30.0 if s("unkostenpauschale") is None else 0.0),
        # Wichtig für korrekte Abrechnungsart
        "abrechnungsart":      sv("abrechnungsart") or "",
        # WDM-Extras
        "wdm_extras_json":     sv("wdm_extras_json") or "[]",
        "gesamt_brutto":       s("gesamt_brutto"),
    }

    with get_connection() as conn:
        ud = conn.execute(
            "SELECT * FROM unfalldetails WHERE akte_id = ?", (az,)
        ).fetchone()
        abrechnungen = conn.execute(
            """SELECT id, datum, versicherung, gesamt_gefordert, gesamt_reguliert
               FROM abrechnungsschreiben WHERE akte_id = ? ORDER BY datum""",
            (az,)
        ).fetchall()

    # Mandant via Model-Funktion
    beteiligte_objs = hole_beteiligte_by_akte(az)
    mandant = None
    for b in beteiligte_objs:
        try:
            if getattr(b, "rolle", "") == "mandant":
                mandant = {
                    "id": b.id, "rolle": b.rolle,
                    "name": b.name or "", "vorname": b.vorname or "",
                    "firma": b.firma or "", "anschrift": b.anschrift or "",
                    "plz": b.plz or "", "ort": b.ort or "",
                    "anrede": getattr(b, "anrede", "") or "",
                    "vorsteuer": getattr(b, "vorsteuer", "N") or "N",
                }
                break
        except Exception:
            continue

    # WDM-Variablen laden (Fallback für leere SQLite-Felder)
    wdm = _lade_wdm_klage_vars(az)
    def _wdm(key, default=""):
        return (wdm.get(key) or default)

    akte_daten = {
        "akte": {
            "aktenzeichen": akte.aktenzeichen,
            "unfalldatum":  akte.unfalldatum or _wdm("varU-TAG") or "",
            "unfallort":    (akte.unfallort or "").strip() or _wdm("varU-ORT") or "",
            "haftungsquote": akte.haftungsquote,
            "erstellt_am":  akte.erstellt_am,
        },
        "mandant":      mandant,
        "kanzlei":      KANZLEI_INFO,
        "unfalldetails": {
            # SQLite hat Vorrang – WDM füllt nur leere Felder auf
            "schilderung":              _override("schilderung",
                (ud["schilderung"] if ud and ud["schilderung"] else _wdm("varSCHILD"))),
            "zeuge_1":                  (ud["zeuge_1"] if ud and ud["zeuge_1"] else _wdm("varZ1")),
            "zeuge_1_anschrift":        (ud["zeuge_1_anschrift"] if ud and ud["zeuge_1_anschrift"] else _wdm("varADRZ1")),
            "zeuge_2":                  (ud["zeuge_2"] if ud and ud["zeuge_2"] else _wdm("varZ2")),
            "zeuge_2_anschrift":        (ud["zeuge_2_anschrift"] if ud and ud["zeuge_2_anschrift"] else _wdm("varADRZ2")),
            "zeuge_3":                  (ud["zeuge_3"] if ud and ud["zeuge_3"] else _wdm("varZ3")),
            "zeuge_3_anschrift":        (ud["zeuge_3_anschrift"] if ud and ud["zeuge_3_anschrift"] else _wdm("varADRZ3")),
            "fahrer_mandant":           (ud["fahrer_mandant"] if ud and ud["fahrer_mandant"] else _wdm("varM-FAHRER")),
            "fahrer_gegner":            (ud["fahrer_gegner"] if ud and ud["fahrer_gegner"] else _wdm("varG-FAHRER")),
            "ermittlungsakte_az":       (ud["ermittlungsakte_az"] if ud and ud["ermittlungsakte_az"] else _wdm("varEA-AZ")),
            "ermittlungsakte_behoerde": (ud["ermittlungsakte_behoerde"] if ud and ud["ermittlungsakte_behoerde"] else _wdm("varPOLIZEI")),
            "ermittlungsakte_ort":      (ud["ermittlungsakte_ort"] if ud and ud["ermittlungsakte_ort"] else _wdm("varEA-ADRESS")),
            "haftungsbegruendung":      (ud["haftungsbegruendung"] if ud and ud["haftungsbegruendung"] else _wdm("varANSP1")),
            "haftungsquote":            (ud["haftungsquote"] if ud and ud["haftungsquote"] else None),
            # WDM-Metadaten (immer mitgeben)
            "_wdm_u_tag":               _wdm("varU-TAG"),
            "_wdm_u_ort":               _wdm("varU-ORT"),
            "_wdm_ghv":                 _wdm("varG-HV"),
            "_wdm_gegner_kz":           _wdm("varG-KZ"),
            "_wdm_schadennummer":       _wdm("varG-SNR"),
            "_wdm_verzugab":            _wdm("varSCHREIBENVERZUG") or _wdm("varVERZUGAB"),
            "_wdm_mandant_kz":          _wdm("varM-KZ"),
            # PRD-24: Aktivlegitimation – Wizard-Override hat Vorrang vor DB
            "aktivlegitimation_typ":      _override(
                "aktivlegitimation_typ",
                (ud["aktivlegitimation_typ"] if ud and ud["aktivlegitimation_typ"] else "eigentum")
            ),
            "aktivlegitimation_freigabe": _override(
                "aktivlegitimation_freigabe",
                (ud["aktivlegitimation_freigabe"] if ud and ud["aktivlegitimation_freigabe"] else "freigabe")
            ),
            "aktivlegitimation_datum":    _override(
                "aktivlegitimation_datum",
                (ud["aktivlegitimation_datum"] if ud else None)
            ),
            "aktivlegitimation_text_override": _override(
                "aktivlegitimation_text_override",
                None
            ),
            "sachverhalt_override": _override("sachverhalt_override", None),
            # PRD-24b: Wizard-Overrides für Textblöcke
            "rw_text_override":     _override("rw_text_override",  None),
            "verzug_text_override": _override("verzug_text_override", None),
            # Fahrer-Ermittlung: varM-FAHRER vs. Mandantenname
            "mandant_ist_fahrer": _override(
                "mandant_ist_fahrer",
                _mandant_ist_fahrer(ud, mandant, _wdm("varM-FAHRER"))
            ),
        },
        "abrechnungen":  [dict(a) for a in abrechnungen],
        "klage_config":  klage_cfg,
        "schaden":      schaden_dict,  # für _baue_tabelle in klage_service
    }

    # PRD-29: personenschaden für Schmerzensgeld-Textbaustein laden
    with get_connection() as conn:
        ps_row = conn.execute(
            "SELECT * FROM personenschaden WHERE akte_id = ?", (az,)
        ).fetchone()
    akte_daten["personenschaden"] = dict(ps_row) if ps_row else {}

    try:
        doc_bytes = generiere_klageschrift(akte_daten)
    except FileNotFoundError as e:
        return _err(str(e), 501)
    except Exception as e:
        logger.error("Klage-Generierung fehlgeschlagen: %s", e, exc_info=True)
        return _err(f"Fehler beim Erstellen der Klageschrift: {e}", 500)

    # Als Download zurückgeben (+ optional in DB speichern)
    az_clean  = akte.aktenzeichen.replace("/", "-").replace(" ", "_")
    dateiname = f"{az_clean}_klageschrift.docx"

    in_db = body.get("in_db", True)
    dok_eintrag = None
    if in_db:
        upload_dir = Path(os.environ.get("UPLOAD_DIR",
                          str(Path(__file__).parent.parent / "uploads")))
        upload_dir.mkdir(parents=True, exist_ok=True)
        pfad = upload_dir / f"{uuid.uuid4().hex}_{dateiname}"
        pfad.write_bytes(doc_bytes)
        try:
            dok = registriere_dokument(
                akte_id=az, typ="klage",
                dateiname=dateiname, dateipfad=str(pfad),
                bearbeiter_id=g.benutzer_id,
                dateityp="docx", dateigroesse=len(doc_bytes),
            )
            dok_eintrag = {"id": dok.id, "dateiname": dok.dateiname}
        except Exception as e:
            logger.warning("Klage DB-Registrierung: %s", e)

    return send_file(
        io.BytesIO(doc_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=dateiname,
    )


# ── Gericht in Akte speichern ─────────────────────────────────────────────────

@klage_bp.route("/gericht", methods=["PUT"])
@login_erforderlich
def speichere_gericht(akte_id: str):
    """
    PUT /akten/<az>/klage/gericht
    Speichert das vom Nutzer bestätigte Gericht als Beteiligter (rolle='gericht')
    in der lokalen SQLite. Überschreibt einen ggf. vorhandenen Eintrag.
    Body: { name, strasse, plz, ort, adressnr }
    """
    if not hole_akte_by_id(akte_id):
        return jsonify({"fehler": f"Akte {akte_id} nicht gefunden."}), 404

    daten = request.get_json(silent=True) or {}
    name = (daten.get("name") or "").strip()
    if not name:
        return jsonify({"fehler": "name ist erforderlich."}), 422

    strasse  = (daten.get("strasse")  or "").strip()
    plz      = (daten.get("plz")      or "").strip()
    ort      = (daten.get("ort")      or "").strip()

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM beteiligte WHERE akte_id = ? AND rolle = 'gericht'",
            (akte_id,)
        )
        conn.execute(
            """INSERT INTO beteiligte (akte_id, rolle, name, anschrift, plz, ort)
               VALUES (?, 'gericht', ?, ?, ?, ?)""",
            (akte_id, name, strasse, plz, ort)
        )

    return jsonify({"ok": True}), 200


# ── KI-gestützte Haftungsbegründung ───────────────────────────────────────────

@klage_bp.route("/ki-haftung", methods=["POST"])
@login_erforderlich
def ki_haftung(akte_id: str):
    """
    POST /akten/<az>/klage/ki-haftung
    Sendet die Unfallschilderung an GPT-4o und gibt einen individuellen
    Haftungsbegründungstext zurück (2-3 Sätze, juristischer Stil).
    Body: { schilderung: str, hq: float }
    """
    import os
    from ..db.database import get_connection
    from .einstellungen_routes import KI_DEFAULTS

    daten       = request.get_json(silent=True) or {}
    schilderung = (daten.get("schilderung") or "").strip()
    hq          = float(daten.get("hq") or 100)

    if not schilderung:
        return jsonify({"fehler": "Keine Unfallschilderung vorhanden."}), 400

    # ── Einstellungen aus DB lesen ────────────────────────────────────────
    def _lese(conn, key):
        row = conn.execute("SELECT wert FROM konfiguration WHERE schluessel=?", (key,)).fetchone()
        return row["wert"] if (row and row["wert"].strip()) else KI_DEFAULTS[key]

    with get_connection() as conn:
        modell        = _lese(conn, "ki_modell")
        system_prompt = _lese(conn, "ki_system_prompt")
        user_template = _lese(conn, "ki_user_prompt")

    # ── Platzhalter befüllen ──────────────────────────────────────────────
    if hq >= 100:
        haftung_ctx = "Die alleinige Haftung des Unfallgegners steht fest (100 %)."
    elif hq >= 50:
        haftung_ctx = f"Der Unfallgegner haftet überwiegend zu {hq:.0f} %."
    else:
        haftung_ctx = f"Der Unfallgegner haftet zu {hq:.0f} % (Mithaftung)."

    user_prompt = user_template.replace("{haftung_ctx}", haftung_ctx)\
                               .replace("{schilderung}", schilderung)

    # ── API-Aufruf je nach Modell ─────────────────────────────────────────
    try:
        if modell.startswith("claude"):
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                return jsonify({"fehler": "ANTHROPIC_API_KEY nicht in .env konfiguriert."}), 503
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg  = client.messages.create(
                model=modell, max_tokens=800,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = msg.content[0].text.strip()

        elif modell.startswith("gemini"):
            api_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
            if not api_key:
                return jsonify({"fehler": "GEMINI_API_KEY nicht in .env konfiguriert."}), 503
            from google import genai
            from google.genai import types as gtypes
            client   = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=modell,
                config=gtypes.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=800,
                    thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
                ),
                contents=user_prompt,
            )
            text = response.text.strip()

        else:
            return jsonify({"fehler": f"Unbekanntes Modell: {modell}"}), 400

        return jsonify({"text": text, "modell": modell}), 200

    except Exception as e:
        logger.error("KI-Haftung Fehler (%s): %s", modell, e)
        return jsonify({"fehler": f"KI-Aufruf fehlgeschlagen: {str(e)}"}), 500


# ── Schmerzensgeld-Ermittlungstool (PRD-29) ───────────────────────────────────

@klage_bp.route("/sg-analyse", methods=["GET"])
@login_erforderlich
def sg_analyse(akte_id: str):
    """
    GET /akten/<az>/klage/sg-analyse
    Liest personenschaden-Daten und gibt strukturiertes Verletzungsprofil zurück.
    """
    az = akte_id
    with get_connection() as conn:
        ps = conn.execute(
            "SELECT * FROM personenschaden WHERE akte_id=?", (az,)
        ).fetchone()

    if not ps:
        return _j({
            "profil": None,
            "fehlende_felder": ["verletzungen_text"],
            "gespeichert": {},
        })

    ps = dict(ps)

    from ..word.sg_text_builder import _parse_datum as _pd

    # Krankenhaustage berechnen (unterstützt ISO und deutsches Datumsformat)
    krankenhaustage = 0
    kh_von_d = _pd(ps.get("krankenhaus_von") or "")
    kh_bis_d = _pd(ps.get("krankenhaus_bis") or "")
    if kh_von_d and kh_bis_d:
        krankenhaustage = max(0, (kh_bis_d - kh_von_d).days)

    # AU-Tage berechnen
    au_tage = 0
    au_von_d = _pd(ps.get("krank_von") or "")
    au_bis_d = _pd(ps.get("krank_bis") or "")
    if au_von_d and au_bis_d:
        au_tage = max(0, (au_bis_d - au_von_d).days)

    fehlende = []
    if not ps.get("verletzungen_text"):
        fehlende.append("verletzungen_text")
    if not ps.get("verletzungsgrad"):
        fehlende.append("verletzungsgrad")

    return _j({
        "profil": {
            "verletzungen_text":   ps.get("verletzungen_text") or "",
            "verletzungsgrad":     ps.get("verletzungsgrad") or "",
            "krankenhaustage":     krankenhaustage,
            "krankenhaus_von":     ps.get("krankenhaus_von") or "",
            "krankenhaus_bis":     ps.get("krankenhaus_bis") or "",
            "krankenhaus_name":    ps.get("krankenhaus_name") or "",
            "au_tage":             au_tage,
            "krank_von":           ps.get("krank_von") or "",
            "krank_bis":           ps.get("krank_bis") or "",
            "dauerfolgen":         bool(ps.get("dauerfolgen")),
            "dauerfolgen_text":    ps.get("dauerfolgen_text") or "",
            "physiotherapie_anzahl": ps.get("physiotherapie_anzahl") or 0,
        },
        "fehlende_felder": fehlende,
        "gespeichert": {
            "sg_mindest":        ps.get("sg_mindest"),
            "sg_text":           ps.get("sg_text") or "",
            "sg_urteil_gericht": ps.get("sg_urteil_gericht") or "",
            "sg_urteil_az":      ps.get("sg_urteil_az") or "",
            "sg_urteil_betrag":  ps.get("sg_urteil_betrag"),
        },
    })


@klage_bp.route("/sg-recherche", methods=["POST"])
@login_erforderlich
def sg_recherche(akte_id: str):
    """
    POST /akten/<az>/klage/sg-recherche
    Claude mit web_search sucht auf dejure.org, lexetius.com, verkehrslexikon.de
    nach passenden Schmerzensgeldurteilen.
    Body: { profil: { verletzungen_text, krankenhaustage, au_tage, dauerfolgen, ... } }
    """
    import os
    daten  = request.get_json(silent=True) or {}
    profil = daten.get("profil") or {}

    verletzungen    = (profil.get("verletzungen_text") or "").strip()
    kh_tage         = int(profil.get("krankenhaustage") or 0)
    au_tage         = int(profil.get("au_tage") or 0)
    dauerfolgen     = bool(profil.get("dauerfolgen"))
    dauerfolgen_txt = (profil.get("dauerfolgen_text") or "").strip()

    if not verletzungen:
        return jsonify({"fehler": "Keine Verletzungsbeschreibung vorhanden. "
                                  "Bitte im Personenschaden-Tab ergänzen."}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"fehler": "ANTHROPIC_API_KEY nicht konfiguriert."}), 503

    # Verletzungsprofil als Text
    profil_zeilen = [f"Verletzungen: {verletzungen}"]
    if kh_tage:
        profil_zeilen.append(f"Stationärer Krankenhausaufenthalt: {kh_tage} Tage")
    if au_tage:
        profil_zeilen.append(f"Arbeitsunfähigkeit: {au_tage} Tage")
    if dauerfolgen:
        df_txt = f" ({dauerfolgen_txt})" if dauerfolgen_txt else ""
        profil_zeilen.append(f"Dauerfolgen: ja{df_txt}")
    profil_text = "\n".join(profil_zeilen)

    # vorbereiteter schmerzensgeld.online-Link
    import urllib.parse
    sg_link = "https://schmerzensgeld.online/suche?" + urllib.parse.urlencode({
        "q": verletzungen[:100]
    })

    user_prompt = (
        f"Suche nach deutschen Gerichtsurteilen zu Schmerzensgeld bei Verkehrsunfällen "
        f"mit ähnlichen Verletzungen (exakte Übereinstimmung nicht erforderlich):\n"
        f"{profil_text}\n\n"
        f"Gib bis zu 5 real existierende Urteile mit vollständigem Aktenzeichen zurück. "
        f"Ähnliche oder teilweise übereinstimmende Verletzungsbilder sind ausdrücklich erwünscht. "
        f"Antworte mit einem JSON-Array:\n"
        f'[{{"gericht":"OLG Frankfurt","az":"22 U 60/17","datum":"22.03.2018",'
        f'"betrag":5000,"kurzfassung":"HWS Grad II, 4 Wochen AU"}}]'
    )

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=api_key)

        # max_uses=2 begrenzt interne Suchanfragen → reduziert Input-Tokens
        web_search_tool = {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 2,
        }

        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            system="Antworte ausschließlich mit dem angeforderten JSON-Array. Kein Fließtext, keine Erklärungen, keine Hinweise.",
            tool_choice={"type": "any"},
            tools=[web_search_tool],
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Antwort-Text aus allen text-Blöcken zusammensetzen
        # (Claude kann mehrere text-Blöcke zwischen web_search-Aufrufen ausgeben)
        text_parts = []
        for block in msg.content:
            t = getattr(block, "text", None)
            if t:
                text_parts.append(t.strip())
        antwort_text = " ".join(text_parts)

        # JSON aus der Antwort extrahieren
        import re as _re
        treffer = []
        json_match = _re.search(r"\[[\s\S]*\]", antwort_text)
        if json_match:
            try:
                treffer = json.loads(json_match.group(0))
            except Exception:
                treffer = []

        return _j({"treffer": treffer[:10], "sg_link": sg_link})

    except Exception as e:
        logger.error("SG-Recherche Fehler: %s", e)
        # Fallback: leere Liste + Link
        return _j({
            "treffer": [],
            "sg_link": sg_link,
            "fehler": f"Automatische Recherche nicht verfügbar: {str(e)}. "
                      f"Bitte manuell auf schmerzensgeld.online suchen.",
        })


@klage_bp.route("/sg-text", methods=["POST"])
@login_erforderlich
def sg_text_generieren(akte_id: str):
    """
    POST /akten/<az>/klage/sg-text
    Claude generiert einen juristisch formulierten Schmerzensgeld-Abschnitt
    für die Klageschrift auf Basis der Verletzungsdaten.
    Body: { profil: {...}, kl_nom: str, sg_mind: float,
            urteil_gericht: str, urteil_az: str, urteil_betrag: float }
    """
    import os
    daten      = request.get_json(silent=True) or {}
    profil     = daten.get("profil") or {}
    kl_nom     = (daten.get("kl_nom") or "Die Klägerin/Der Kläger").strip()
    sg_mind    = float(daten.get("sg_mind") or 0)
    urteil_g   = (daten.get("urteil_gericht") or "").strip()
    urteil_az  = (daten.get("urteil_az") or "").strip()
    urteil_b   = float(daten.get("urteil_betrag") or 0)

    verletzungen = (profil.get("verletzungen_text") or "").strip()
    if not verletzungen:
        return jsonify({"fehler": "Keine Verletzungsbeschreibung vorhanden."}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"fehler": "ANTHROPIC_API_KEY nicht konfiguriert."}), 503

    kh_von   = profil.get("krankenhaus_von") or ""
    kh_bis   = profil.get("krankenhaus_bis") or ""
    kh_name  = profil.get("krankenhaus_name") or ""
    kh_tage  = int(profil.get("krankenhaustage") or 0)
    au_von   = profil.get("krank_von") or ""
    au_bis   = profil.get("krank_bis") or ""
    au_tage  = int(profil.get("au_tage") or 0)
    df_bool  = bool(profil.get("dauerfolgen"))
    df_text  = (profil.get("dauerfolgen_text") or "").strip()

    # Kontext für Claude aufbauen
    kontext_zeilen = [f"Kläger/in: {kl_nom}", f"Verletzungen: {verletzungen}"]
    if kh_tage and kh_von and kh_bis:
        kh_zeile = f"Krankenhausaufenthalt: {kh_tage} Tage ({kh_von} – {kh_bis})"
        if kh_name:
            kh_zeile += f" im {kh_name}"
        kontext_zeilen.append(kh_zeile)
    if au_tage and au_von and au_bis:
        kontext_zeilen.append(f"Arbeitsunfähigkeit: {au_tage} Tage ({au_von} – {au_bis})")
    if df_bool:
        kontext_zeilen.append(f"Dauerfolgen: {df_text}" if df_text else "Dauerfolgen: ja")
    if sg_mind > 0:
        kontext_zeilen.append(f"Mindest-Schmerzensgeld: {sg_mind:,.0f} €".replace(",", "."))
    if urteil_az:
        kontext_zeilen.append(f"Orientierungsurteil: {urteil_g} {urteil_az} → {urteil_b:,.0f} €".replace(",", "."))

    kontext = "\n".join(kontext_zeilen)

    user_prompt = f"""Schreibe den Schmerzensgeld-Abschnitt für eine deutsche Klageschrift (Verkehrsunfallsache).

Sachverhalt:
{kontext}

Anforderungen:
- Sachlicher, juristischer Stil (kein Pathos)
- 2–3 kurze Absätze
- Schildere konkret die Verletzungen und Beeinträchtigungen
- Begründe die Höhe des Schmerzensgeldes knapp
- Falls ein Orientierungsurteil angegeben: als Vergleich erwähnen
- Kein Beweisantritt (wird separat ergänzt)
- Kein Überschrift-Text (kommt separat)
- Nur Fließtext, keine Listen"""

    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system="Du bist ein erfahrener Rechtsanwalt und formulierst Klageschriften in Deutschland. "
                   "Schreibe präzise, sachlich und juristisch korrekt.",
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = msg.content[0].text.strip()
        return _j({"text": text})

    except Exception as e:
        logger.error("SG-Text Fehler: %s", e)
        return jsonify({"fehler": f"KI-Aufruf fehlgeschlagen: {str(e)}"}), 500


# ── Gerichte aus RA-Micro suchen ──────────────────────────────────────────────

@klage_bp.route("/gerichte", methods=["GET"])
@login_erforderlich
def suche_gerichte(akte_id: str):
    """
    GET /akten/<az>/klage/gerichte?q=Frankfurt&typ=amts
    Sucht Gerichte in RA-Micro (tblAdressen, iAdressnummer >= 95000).
    Fallback: Beteiligte mit rolle='gericht' aus SQLite.
    """
    q   = (request.args.get("q")   or "").strip()
    typ = (request.args.get("typ") or "").strip().lower()  # "amts" | "land" | ""

    gerichte = []

    # ── Versuch 1: RA-Micro ──────────────────────────────────────────────────
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )

        if typ == "amts":
            typ_filter = "AND sNachname LIKE '%Amtsgericht%'"
        elif typ == "land":
            typ_filter = "AND sNachname LIKE '%Landgericht%'"
        else:
            typ_filter = "AND (sNachname LIKE '%Amtsgericht%' OR sNachname LIKE '%Landgericht%')"

        q_filter = "AND (sNachname LIKE %(q)s OR sOrt LIKE %(q)s)" if q else ""
        q_param  = f"%{q}%"

        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(f"""
                SELECT TOP 30
                    iAdressnummer  AS adressnr,
                    sNachname      AS name,
                    [sStraße]      AS strasse,
                    sPLZ           AS plz,
                    sOrt           AS ort,
                    sTelefon       AS telefon,
                    sEMail         AS email
                FROM tblAdressen
                WHERE iAdressnummer >= 90000
                  {typ_filter}
                  {q_filter}
                ORDER BY sNachname ASC
            """, {"q": q_param} if q else {})

            for r in cur.fetchall():
                gerichte.append({
                    "quelle":    "ramicro",
                    "adressnr":  r["adressnr"],
                    "name":      (r["name"]    or "").strip(),
                    "strasse":   (r["strasse"] or "").strip(),
                    "plz":       (r["plz"]     or "").strip(),
                    "ort":       (r["ort"]     or "").strip(),
                    "telefon":   (r["telefon"] or "").strip(),
                    "email":     (r["email"]   or "").strip(),
                })
    except Exception as e:
        cls = type(e).__name__
        if "NichtAktiv" not in cls and "VerbindungsFehler" not in cls:
            logger.warning("Gerichte RA-Micro: %s", e)

    # ── Versuch 2: SQLite-Fallback (Beteiligte mit rolle=gericht) ───────────
    if not gerichte:
        try:
            akte = hole_akte_by_id(akte_id)
            if akte:
                az = akte.aktenzeichen
                with get_connection() as conn:
                    rows = conn.execute(
                        "SELECT * FROM beteiligte WHERE akte_id = ? AND rolle = 'gericht'",
                        (az,)
                    ).fetchall()
                for r in rows:
                    name = (r["firma"] or
                            f"{r['vorname'] or ''} {r['name'] or ''}".strip() or
                            "Gericht")
                    if not q or q.lower() in name.lower() or q.lower() in (r["ort"] or "").lower():
                        gerichte.append({
                            "quelle":  "sqlite",
                            "adressnr": r["id"],
                            "name":    name,
                            "strasse": r["anschrift"] or "",
                            "plz":     r["plz"]       or "",
                            "ort":     r["ort"]       or "",
                            "telefon": r["telefon"]   or "",
                            "email":   r["email"]     or "",
                        })
        except Exception as e:
            logger.warning("Gerichte SQLite-Fallback: %s", e)

    return _j({"gerichte": gerichte})
