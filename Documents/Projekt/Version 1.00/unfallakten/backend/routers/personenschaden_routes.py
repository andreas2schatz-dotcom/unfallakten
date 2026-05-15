"""
Personenschaden-Router
=======================
Endpunkte für Personenschaden-Daten und Beteiligte der Heilbehandlung.

Endpunkte:
  GET  /akten/<az>/personenschaden              Textfelder aus SQLite
  PUT  /akten/<az>/personenschaden              Textfelder speichern
  GET  /akten/<az>/personenschaden/beteiligte   Beteiligte (SQLite + WDM-Fallback)
  POST /akten/<az>/personenschaden/beteiligte   Beteiligten hinzufügen/speichern
  DELETE /akten/<az>/personenschaden/beteiligte/<id>  Beteiligten entfernen

Datenquellen-Hierarchie für Beteiligte:
  1. SQLite (quelle='manuell' oder quelle='wdm') – hat immer Vorrang
  2. WDM (varV-KHADR, varV-ARZT1-3, varV-ADRAG, varV-KRKASSE) – Fallback
  In beiden Fällen wird die Adresse live aus tblAdressen geladen.
"""

import logging
import json
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ._helpers import pruefe_akte as _pruefe_akte
from ..db.database import get_connection

logger = logging.getLogger(__name__)

ps_bp = Blueprint("personenschaden", __name__,
                  url_prefix="/akten/<path:akte_id>")

GUELTIGE_ROLLEN = {
    "arzt", "krankenhaus", "physiotherapeut",
    "arbeitgeber", "krankenkasse", "bg"
}

ROLLEN_LABEL = {
    "arzt":            "Behandelnder Arzt",
    "krankenhaus":     "Krankenhaus",
    "physiotherapeut": "Physiotherapeut",
    "arbeitgeber":     "Arbeitgeber",
    "krankenkasse":    "Krankenkasse",
    "bg":              "Berufsgenossenschaft",
}


def _j(d, s=200): return jsonify(d), s
def _err(msg, s=400): return jsonify({"fehler": msg, "status": s}), s


# ── Adresse aus RA-Micro laden ─────────────────────────────────────────────

def _lade_adresse_aus_ramicro(adressnr: int) -> dict | None:
    """Lädt vollständige Adresse aus tblAdressen per iAdressnummer."""
    if not adressnr:
        return None
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    iAdressnummer       AS adressnr,
                    sErsteAdresszeile   AS firma,
                    sNachname           AS nachname,
                    sVorname            AS vorname,
                    sAnrede             AS anrede,
                    sBriefanrede        AS briefanrede,
                    [sStraße]           AS strasse,
                    sPLZ                AS plz,
                    sOrt                AS ort,
                    sTelefon            AS telefon,
                    sTelefax            AS telefax,
                    sEMail              AS email
                FROM tblAdressen
                WHERE iAdressNummer = %(nr)s
            """, {"nr": adressnr})
            row = cur.fetchone()
        if not row:
            return None
        r = dict(row)
        # Vollständiger Name: Firma hat Vorrang, sonst Vor- + Nachname
        firma   = (r.get("firma")    or "").strip()
        vorname = (r.get("vorname")  or "").strip()
        nachname= (r.get("nachname") or "").strip()
        r["name"] = firma if firma else f"{vorname} {nachname}".strip()
        return r
    except Exception as e:
        logger.warning("_lade_adresse_aus_ramicro(%s): %s", adressnr, e)
        return None


def _beteiligter_mit_adresse(b: dict) -> dict:
    """Reichert einen Beteiligten-Datensatz mit Adresse aus RA-Micro an."""
    adressnr = b.get("adressnr")
    adresse = _lade_adresse_aus_ramicro(adressnr) if adressnr else None
    return {
        "id":        b.get("id"),
        "akte_id":   b.get("akte_id"),
        "adressnr":  adressnr,
        "rolle":     b.get("rolle"),
        "sortierung":b.get("sortierung", 0),
        "quelle":    b.get("quelle", "manuell"),
        "notizen":   b.get("notizen"),
        "erfasst_am":b.get("erfasst_am"),
        # Adressfelder live aus RA-Micro
        "name":      adresse["name"]     if adresse else b.get("name_cache", ""),
        "firma":     adresse.get("firma","") if adresse else "",
        "vorname":   adresse.get("vorname","") if adresse else "",
        "nachname":  adresse.get("nachname","") if adresse else "",
        "strasse":   adresse.get("strasse","") if adresse else "",
        "plz":       adresse.get("plz","") if adresse else "",
        "ort":       adresse.get("ort","") if adresse else "",
        "telefon":   adresse.get("telefon","") if adresse else "",
        "email":     adresse.get("email","") if adresse else "",
        "adresse_geladen": adresse is not None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEXTFELDER (Verletzungen, Daten, Flags)
# ══════════════════════════════════════════════════════════════════════════════

@ps_bp.route("/personenschaden", methods=["GET"])
@login_erforderlich
def hole_personenschaden(akte_id: str):
    """GET /akten/<az>/personenschaden — Textfelder aus SQLite."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM personenschaden WHERE akte_id = ?", (akte_id,)
        ).fetchone()
    if not row:
        return _j({"personenschaden": None})
    return _j({"personenschaden": dict(row)})


@ps_bp.route("/personenschaden", methods=["PUT"])
@login_erforderlich
def speichere_personenschaden(akte_id: str):
    """PUT /akten/<az>/personenschaden — Textfelder speichern (UPSERT)."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = request.get_json(silent=True) or {}

    # Erlaubte Felder (nur Textfelder – keine Adressfelder)
    FELDER = [
        "verletzungen_text",
        "krankenhaus_von", "krankenhaus_bis",
        "krankenhaus_aufenthalt", "krankgeschrieben", "krank_von", "krank_bis",
        "berufsunfall", "bg_name",
        "rentenversichert", "rentenversicherung_name",
        "heilbehandlung_abgeschlossen", "heilbehandlung_ende",
        "dauerfolgen", "dauerfolgen_text",
        "schweigepflicht_entbindung",
        "familienstand", "kinder_anzahl", "kinder_alter_text",
        "geburtsdatum", "beruf", "selbststaendig",
        "nettoeinkommen_monatlich",
        "physiotherapie", "physiotherapie_anzahl",
        "notizen",
        # PRD-29: Schmerzensgeld-Ermittlungstool
        "sg_mindest", "sg_text",
        "sg_urteil_gericht", "sg_urteil_az", "sg_urteil_betrag",
    ]

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM personenschaden WHERE akte_id = ?", (akte_id,)
        ).fetchone()

        felder_werte = {k: daten[k] for k in FELDER if k in daten}

        if existing:
            if felder_werte:
                set_clause = ", ".join(f"{k} = ?" for k in felder_werte)
                set_clause += ", geaendert_am = datetime('now','localtime')"
                conn.execute(
                    f"UPDATE personenschaden SET {set_clause} WHERE akte_id = ?",
                    [*felder_werte.values(), akte_id]
                )
        else:
            felder_werte["akte_id"] = akte_id
            cols = ", ".join(felder_werte.keys())
            placeholders = ", ".join("?" * len(felder_werte))
            conn.execute(
                f"INSERT INTO personenschaden ({cols}) VALUES ({placeholders})",
                list(felder_werte.values())
            )

        row = conn.execute(
            "SELECT * FROM personenschaden WHERE akte_id = ?", (akte_id,)
        ).fetchone()

    return _j({"personenschaden": dict(row) if row else felder_werte})


# ══════════════════════════════════════════════════════════════════════════════
# BETEILIGTE DER HEILBEHANDLUNG
# ══════════════════════════════════════════════════════════════════════════════

@ps_bp.route("/personenschaden/beteiligte", methods=["GET"])
@login_erforderlich
def liste_ps_beteiligte(akte_id: str):
    """
    GET /akten/<az>/personenschaden/beteiligte

    Lädt Beteiligte aus SQLite. Falls leer → WDM-Fallback.
    Adressdaten kommen immer live aus tblAdressen.
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM personenschaden_beteiligte
               WHERE akte_id = ?
               ORDER BY sortierung ASC, id ASC""",
            (akte_id,)
        ).fetchall()

    if rows:
        ergebnis = [_beteiligter_mit_adresse(dict(r)) for r in rows]
        return _j({"beteiligte": ergebnis, "quelle": "sqlite"})

    # ── WDM-Fallback ──────────────────────────────────────────────────────
    try:
        wdm_beteiligte = _lade_ps_beteiligte_aus_wdm(akte_id)
        if wdm_beteiligte:
            return _j({"beteiligte": wdm_beteiligte, "quelle": "wdm"})
    except Exception as e:
        logger.debug("WDM-Fallback Personenschaden-Beteiligte: %s", e)

    return _j({"beteiligte": [], "quelle": "leer"})


def _lade_ps_beteiligte_aus_wdm(akte_id: str) -> list:
    """
    Lädt Personenschaden-Beteiligte aus WDM-Adressnummern.
    Gibt Liste im Frontend-Format zurück (noch nicht in SQLite gespeichert).
    """
    from ..word.word_service import _lade_wdm_kontrollvars

    # Erweiterte WDM-Variablen für Adressnummern laden
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
        import re as _re

        az_basis = _re.sub(r'[A-Z]{2,3}$', '', akte_id.strip().upper()).strip()
        if not az_basis or "/" not in az_basis:
            az_basis = akte_id

        PS_ADR_VARS = {
            "varV-KHADR":   "krankenhaus",
            "varV-ARZT1":   "arzt",
            "varV-ARZT2":   "arzt",
            "varV-ARZT3":   "arzt",
            "varV-ADRAG":   "arbeitgeber",
            "varV-KRKASSE": "krankenkasse",
        }

        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 1 a.sAktenNummer AS az_roh
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return []
            az_roh = row["az_roh"]

            placeholders = ",".join([f"%(v{i})s" for i in range(len(PS_ADR_VARS))])
            params = {f"v{i}": k for i, k in enumerate(PS_ADR_VARS.keys())}
            params["az_roh"] = az_roh

            cur.execute(f"""
                SELECT sName, CAST(Value AS nvarchar(100)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_roh)s
                  AND sName IN ({placeholders})
                  AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(100)) != ''
            """, params)
            wdm_raw = {r["sName"]: (r["wert"] or "").strip() for r in cur.fetchall()}

    except Exception as e:
        logger.warning("_lade_ps_beteiligte_aus_wdm WDM-Abfrage fehlgeschlagen: %s", e, exc_info=True)
        return []

    ergebnis = []
    sortierung = 0
    arzt_zaehler = 0

    for var, rolle in PS_ADR_VARS.items():
        wert = wdm_raw.get(var, "")
        if not wert:
            continue
        # WDM liefert Adressnummern als Strings
        try:
            adressnr = int(float(wert))  # float() für "123.0"-Format tolerant
        except (ValueError, TypeError):
            logger.debug("_lade_ps_beteiligte_aus_wdm: kein int-Wert für %s: %r", var, wert)
            continue

        if rolle == "arzt":
            arzt_zaehler += 1
            notizen_default = f"Arzt {arzt_zaehler}"
        else:
            notizen_default = ""

        adresse = _lade_adresse_aus_ramicro(adressnr)
        if not adresse and rolle != "bg":
            continue

        eintrag = {
            "id":        None,  # noch nicht in SQLite
            "akte_id":   akte_id,
            "adressnr":  adressnr,
            "rolle":     rolle,
            "sortierung":sortierung,
            "quelle":    "wdm",
            "notizen":   notizen_default,
            "erfasst_am":None,
            "name":      adresse["name"]       if adresse else "",
            "firma":     adresse.get("firma","")  if adresse else "",
            "vorname":   adresse.get("vorname","") if adresse else "",
            "nachname":  adresse.get("nachname","") if adresse else "",
            "strasse":   adresse.get("strasse","") if adresse else "",
            "plz":       adresse.get("plz","")   if adresse else "",
            "ort":       adresse.get("ort","")   if adresse else "",
            "telefon":   adresse.get("telefon","") if adresse else "",
            "email":     adresse.get("email","")  if adresse else "",
            "adresse_geladen": adresse is not None,
        }
        ergebnis.append(eintrag)
        sortierung += 1

    return ergebnis


@ps_bp.route("/personenschaden/beteiligte", methods=["POST"])
@login_erforderlich
def speichere_ps_beteiligten(akte_id: str):
    """
    POST /akten/<az>/personenschaden/beteiligte

    Speichert einen Beteiligten in SQLite.
    Body: { adressnr, rolle, quelle, notizen, sortierung }
    Wenn quelle="wdm" und mehrere WDM-Einträge auf einmal gespeichert werden,
    können auch Arrays übergeben werden.
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = request.get_json(silent=True) or {}

    # Einzelner Eintrag oder Array
    if isinstance(daten, list):
        eintraege = daten
    elif daten.get("batch"):
        eintraege = daten["batch"]
    else:
        eintraege = [daten]

    gespeichert = []
    with get_connection() as conn:
        for d in eintraege:
            adressnr = d.get("adressnr")
            rolle    = (d.get("rolle") or "").strip().lower()

            if not adressnr:
                continue
            if rolle not in GUELTIGE_ROLLEN:
                continue

            # Prüfen ob bereits vorhanden (gleiche adressnr + rolle)
            exists = conn.execute(
                "SELECT id FROM personenschaden_beteiligte WHERE akte_id=? AND adressnr=? AND rolle=?",
                (akte_id, adressnr, rolle)
            ).fetchone()

            if exists:
                # Update: quelle + notizen aktualisieren
                conn.execute(
                    """UPDATE personenschaden_beteiligte
                       SET quelle=?, notizen=?, sortierung=?
                       WHERE id=?""",
                    (d.get("quelle","manuell"), d.get("notizen",""),
                     d.get("sortierung",0), exists["id"])
                )
                new_id = exists["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO personenschaden_beteiligte
                       (akte_id, adressnr, rolle, sortierung, quelle, notizen)
                       VALUES (?,?,?,?,?,?)""",
                    (akte_id, adressnr, rolle,
                     d.get("sortierung", 0),
                     d.get("quelle", "manuell"),
                     d.get("notizen", ""))
                )
                new_id = cur.lastrowid

            row = conn.execute(
                "SELECT * FROM personenschaden_beteiligte WHERE id=?", (new_id,)
            ).fetchone()
            if row:
                gespeichert.append(_beteiligter_mit_adresse(dict(row)))

    return _j({"beteiligte": gespeichert}, 201)


@ps_bp.route("/personenschaden/beteiligte/<int:beteiligter_id>", methods=["PATCH"])
@login_erforderlich
def aktualisiere_ps_beteiligten(akte_id: str, beteiligter_id: int):
    """PATCH — Notizen oder Sortierung eines Beteiligten ändern."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = request.get_json(silent=True) or {}
    erlaubt = {"notizen", "sortierung", "quelle", "rolle"}
    felder = {k: v for k, v in daten.items() if k in erlaubt}
    if not felder:
        return _err("Keine aktualisierbaren Felder.", 422)

    with get_connection() as conn:
        set_clause = ", ".join(f"{k}=?" for k in felder)
        conn.execute(
            f"UPDATE personenschaden_beteiligte SET {set_clause} WHERE id=? AND akte_id=?",
            [*felder.values(), beteiligter_id, akte_id]
        )
        row = conn.execute(
            "SELECT * FROM personenschaden_beteiligte WHERE id=?", (beteiligter_id,)
        ).fetchone()

    if not row:
        return _err(f"Beteiligter {beteiligter_id} nicht gefunden.", 404)
    return _j({"beteiligter": _beteiligter_mit_adresse(dict(row))})


@ps_bp.route("/personenschaden/beteiligte/<int:beteiligter_id>", methods=["DELETE"])
@login_erforderlich
def loesche_ps_beteiligten(akte_id: str, beteiligter_id: int):
    """DELETE — Beteiligten aus SQLite entfernen."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM personenschaden_beteiligte WHERE id=? AND akte_id=?",
            (beteiligter_id, akte_id)
        )
    return _j({"nachricht": f"Beteiligter {beteiligter_id} entfernt."})


# ══════════════════════════════════════════════════════════════════════════════
# WDM-PERSONENSCHADEN (alle PS-Felder aus WDM laden)
# ══════════════════════════════════════════════════════════════════════════════

@ps_bp.route("/personenschaden/wdm", methods=["GET"])
@login_erforderlich
def hole_ps_wdm(akte_id: str):
    """
    GET /akten/<az>/personenschaden/wdm

    Lädt alle Personenschaden-relevanten WDM-Variablen aus RA-Micro.
    Gibt zwei Blöcke zurück:
      - textfelder: dict mit psForm-Keys (direkt übertragbar)
      - adressen:   Liste mit {var, adressnr, rolle, adresse} (Beteiligte)
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    # WDM-Variablen: Textfelder + Flags
    WDM_TEXT = {
        # Flags (Ja/Nein → 1/0)
        "varV-BU":       ("berufsunfall",              "bool"),
        "varV-SELB":     ("selbststaendig",             "bool"),
        "varV-HKRANK":   ("krankgeschrieben",           "bool"),
        "varV-RENT":     ("rente_vor_unfall",           "bool"),
        # Datumsfelder (TT.MM.JJJJ)
        "varV-KRVON":    ("krank_von",                  "datum"),
        "varV-KRBIS":    ("krank_bis",                  "datum"),
        "varV-KHVON":    ("krankenhaus_von",             "datum"),
        "varV-KHBIS":    ("krankenhaus_bis",             "datum"),
        # Textfelder
        "varV-BERUF-G":  ("bg_name",                    "text"),
        "varV-BERUF":    ("beruf",                      "text"),
        "varV-FAM":      ("familienstand",              "text"),
        "varV-KINDER":   ("kinder_alter_text",          "text"),
        "varVERLETZUNG1":("verletzung1",                "text"),
        "varVERLETZUNG2":("verletzung2",                "text"),
    }

    # WDM-Variablen: Adressnummern → Beteiligte
    WDM_ADR = {
        "varV-KHADR":   "krankenhaus",
        "varV-ARZT1":   "arzt",
        "varV-ARZT2":   "arzt",
        "varV-ARZT3":   "arzt",
        "varV-ADRAG":   "arbeitgeber",
        "varV-KRKASSE": "krankenkasse",
    }

    alle_vars = list(WDM_TEXT.keys()) + list(WDM_ADR.keys())

    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
        import re as _re

        az_basis = _re.sub(r'[A-Z]{2,3}$', '', akte_id.strip().upper()).strip()
        if not az_basis or "/" not in az_basis:
            az_basis = akte_id

        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT TOP 1 a.sAktenNummer AS az_roh
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return _j({"textfelder": {}, "adressen": [],
                           "hinweis": f"Akte {akte_id} nicht in RA-Micro gefunden."})
            az_roh = row["az_roh"]

            # Alle relevanten WDM-Vars auf einmal laden
            placeholders = ",".join([f"%(v{i})s" for i in range(len(alle_vars))])
            params = {f"v{i}": v for i, v in enumerate(alle_vars)}
            params["az_roh"] = az_roh

            top_n = len(alle_vars) + 5
            cur.execute(f"""
                SELECT TOP {top_n} sName, CAST(Value AS nvarchar(500)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_roh)s
                  AND sName IN ({placeholders})
                  AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(500)) != ''
            """, params)
            wdm_raw = {r["sName"]: (r["wert"] or "").strip() for r in cur.fetchall()}

    except RaMicroNichtAktiv:
        return _j({"textfelder": {}, "adressen": [], "fehler": "RA-Micro nicht aktiv."}), 503
    except RaMicroVerbindungsFehler as e:
        return _j({"textfelder": {}, "adressen": [], "fehler": str(e)}), 503
    except Exception as e:
        logger.warning("hole_ps_wdm(%s): %s", akte_id, e, exc_info=True)
        return _j({"textfelder": {}, "adressen": [], "fehler": str(e)}), 500

    # ── Textfelder aufbereiten ────────────────────────────────────────────
    textfelder = {}
    for var, (feld, typ) in WDM_TEXT.items():
        wert = wdm_raw.get(var, "")
        if not wert:
            continue
        if typ == "bool":
            textfelder[feld] = 1 if wert.strip().lower() in ("ja", "j", "yes", "1", "true") else 0
        elif typ == "datum":
            textfelder[feld] = wert  # TT.MM.JJJJ direkt übernehmen
        else:
            textfelder[feld] = wert

    # Verletzungen zusammenführen
    v1 = wdm_raw.get("varVERLETZUNG1", "")
    v2 = wdm_raw.get("varVERLETZUNG2", "")
    if v1 or v2:
        textfelder["verletzungen_text"] = ", ".join(filter(None, [v1, v2]))
    # Einzelfelder wieder entfernen (nur kombiniert verwenden)
    textfelder.pop("verletzung1", None)
    textfelder.pop("verletzung2", None)

    # ── Adressnummern → Beteiligte-Liste ─────────────────────────────────
    adressen = []
    arzt_nr = 0
    for var, rolle in WDM_ADR.items():
        wert = wdm_raw.get(var, "")
        if not wert:
            continue
        try:
            adressnr = int(float(wert))
        except (ValueError, TypeError):
            continue

        if rolle == "arzt":
            arzt_nr += 1

        adresse = _lade_adresse_aus_ramicro(adressnr)
        adressen.append({
            "wdm_var":   var,
            "adressnr":  adressnr,
            "rolle":     rolle,
            "quelle":    "wdm",
            "notizen":   f"Arzt {arzt_nr}" if rolle == "arzt" else "",
            "adresse":   adresse,
            "name":      adresse["name"] if adresse else "",
        })

    return _j({
        "textfelder":        textfelder,
        "adressen":          adressen,
        "felder_gefunden":   len(textfelder),
        "adressen_gefunden": len(adressen),
        "az_roh":            az_roh if 'az_roh' in dir() else akte_id,
    })
