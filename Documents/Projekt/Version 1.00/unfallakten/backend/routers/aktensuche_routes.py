"""
Modul: RA-Micro Aktensuche
===========================
Lesende Suche in der RA-Micro SQL-Datenbank.

WDM-Variablen (ermittelt aus echten Daten):
  U-Tag   Unfalltag  Format: TT.MM.JJ  (zweistelliges Jahr!)
  M-KZ    Mandant-KFZ-Kennzeichen

Endpunkte:
  GET /aktensuche?az=42/25     Aktenzeichen (mit /) oder Namenssuche (ohne /)
  GET /aktensuche?kz=OFNM444   KFZ-Kennzeichen via WDM M-KZ
  GET /aktensuche?tag=2026-02-23  Schadentag via WDM U-Tag
"""

import logging
from flask import Blueprint, request, jsonify
from ..auth.middleware import login_erforderlich
from ..ramicro.connector import (
    get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
)
from ..utils.datum import iso_zu_ramicro as _iso_zu_ttmmjj

logger = logging.getLogger(__name__)
aktensuche_bp = Blueprint("aktensuche", __name__, url_prefix="/aktensuche")


def _j(d, s=200):  return jsonify(d), s
def _err(m, s=400, **kw): return jsonify({"fehler": m, **kw}), s


def _fmt_az(az_raw: str, sb: str) -> str:
    if sb and not az_raw.upper().endswith(sb.upper()):
        return az_raw + sb
    return az_raw


def _row(r: dict) -> dict:
    return {
        "az":              _fmt_az(r.get("az_roh",""), r.get("sachbearbeiter","")),
        "az_roh":          r.get("az_roh", ""),
        "kurzbezeichnung": r.get("kurzbezeichnung") or "",
        "bezeichnung":     r.get("bezeichnung")     or "",
        "sachbearbeiter":  r.get("sachbearbeiter")  or "",
        "mandant":         r.get("mandant")          or "",
        "kennzeichen":     r.get("kennzeichen")      or "",
    }


# Aktiv-Filter: nicht archivierte Akten
_AKTIV = "(a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')"

# LEFT JOIN um Kennzeichen (WDM varM-KZ) mitzuladen
# sName-Varianten: 'varM-KZ' ist der primäre Name; IN-Liste fängt Schreibvarianten ab
_KZ_JOIN = """
    LEFT JOIN (
        SELECT AktenNr, CAST(Value AS nvarchar(50)) AS kz_wert
        FROM _tbl0WDMDaten d1
        WHERE sName IN ('varM-KZ','var_M-KZ','M-KZ')
          AND Value IS NOT NULL
          AND CAST(Value AS nvarchar(50)) != ''
    ) kz_wdm ON kz_wdm.AktenNr = a.sAktenNummer
"""

# Standard-Spalten für alle Suchmodi
_COLS = """
    a.sAktenNummer          AS az_roh,
    a.sAktenSachbearbeiter  AS sachbearbeiter,
    a.sAktenKurzBezeichnung AS kurzbezeichnung,
    a.sAktenBezeichnung     AS bezeichnung,
    a.sMandant              AS mandant,
    kz_wdm.kz_wert          AS kennzeichen
"""


@aktensuche_bp.route("", methods=["GET"])
@login_erforderlich
def suche():
    az  = (request.args.get("az")  or "").strip()
    kz  = (request.args.get("kz")  or "").strip()
    tag = (request.args.get("tag") or "").strip()

    if not az and not kz and not tag:
        return _err("Mindestens 'az', 'kz' oder 'tag' angeben.", 422)

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # ── KFZ-Kennzeichen via WDM M-KZ ──────────────────────────────
            if kz:
                kz_norm = kz.replace(" ", "").replace("-", "").upper()
                cur.execute(f"""
                    SELECT TOP 100
                        w.AktenNr               AS az_roh,
                        a.sAktenSachbearbeiter  AS sachbearbeiter,
                        a.sAktenKurzBezeichnung AS kurzbezeichnung,
                        a.sAktenBezeichnung     AS bezeichnung,
                        a.sMandant              AS mandant,
                        CAST(w.Value AS nvarchar(50)) AS kennzeichen
                    FROM _tbl0WDMDaten w
                    INNER JOIN tblAkten a ON a.sAktenNummer = w.AktenNr
                    WHERE w.sName IN ('varM-KZ','var_M-KZ','M-KZ')
                      AND REPLACE(REPLACE(
                            UPPER(CAST(w.Value AS nvarchar(max))),
                          ' ',''),'-','') LIKE %(kz_like)s
                      AND {_AKTIV}
                    ORDER BY w.AktenNr ASC
                """, {"kz_like": f"%{kz_norm}%"})
                rows = cur.fetchall()
                return _j({"treffer": [_row(r) for r in rows],
                            "anzahl": len(rows), "suchmodus": "kennzeichen",
                            "ramicro_aktiv": True})

            # ── Schadentag via WDM U-Tag (Format TT.MM.JJ) ───────────────
            if tag:
                tag_fmt = _iso_zu_ttmmjj(tag)
                logger.info("Schadentag-Suche: Eingabe=%s → varU-TAG-Format=%s%%", tag, tag_fmt)
                cur.execute(f"""
                    SELECT TOP 100
                        w.AktenNr               AS az_roh,
                        a.sAktenSachbearbeiter  AS sachbearbeiter,
                        a.sAktenKurzBezeichnung AS kurzbezeichnung,
                        a.sAktenBezeichnung     AS bezeichnung,
                        a.sMandant              AS mandant,
                        kz_wdm.kz_wert          AS kennzeichen
                    FROM _tbl0WDMDaten w
                    INNER JOIN tblAkten a ON a.sAktenNummer = w.AktenNr
                    {_KZ_JOIN}
                    WHERE w.sName = 'varU-TAG'
                      AND CAST(w.Value AS nvarchar(50)) LIKE %(tag_like)s
                      AND {_AKTIV}
                    ORDER BY w.AktenNr ASC
                """, {"tag_like": f"{tag_fmt}%"})
                rows = cur.fetchall()
                return _j({"treffer": [_row(r) for r in rows],
                            "anzahl": len(rows), "suchmodus": "schadentag",
                            "ramicro_aktiv": True})

            # ── Aktenzeichen (enthält "/") ────────────────────────────────
            if "/" in az:
                cur.execute(f"""
                    SELECT TOP 100 {_COLS}
                    FROM tblAkten a
                    {_KZ_JOIN}
                    WHERE {_AKTIV}
                      AND a.sAktenNummer LIKE %(like)s
                    ORDER BY a.sAktenNummer ASC
                """, {"like": f"{az}%"})
                rows = cur.fetchall()
                return _j({"treffer": [_row(r) for r in rows],
                            "anzahl": len(rows), "suchmodus": "aktenzeichen",
                            "ramicro_aktiv": True})

            # ── Namenssuche: Mandant + Gegner ─────────────────────────────
            like = f"%{az}%"
            cur.execute(f"""
                SELECT TOP 100 {_COLS}
                FROM tblAkten a
                {_KZ_JOIN}
                WHERE {_AKTIV}
                  AND (
                        a.sMandant LIKE %(like)s
                     OR EXISTS (
                            SELECT 1
                            FROM tblAktenBeteiligte b
                            INNER JOIN tblAdressen adr
                                ON adr.GUIDAdresse = b.GUIDAdresse
                            WHERE b.GUIDAkte = a.GUIDAkte
                              AND b.bDeaktiviert = 0
                              AND (   adr.sNachname LIKE %(like)s
                                   OR adr.sVorname  LIKE %(like)s
                                   OR (adr.sNachname + ' ' + ISNULL(adr.sVorname,'')) LIKE %(like)s
                                   OR (ISNULL(adr.sVorname,'') + ' ' + adr.sNachname) LIKE %(like)s
                                  )
                        )
                  )
                ORDER BY a.sAktenNummer ASC
            """, {"like": like})
            rows = cur.fetchall()
            return _j({"treffer": [_row(r) for r in rows],
                        "anzahl": len(rows), "suchmodus": "name",
                        "ramicro_aktiv": True})

    except RaMicroNichtAktiv:
        return _j({"treffer": [], "anzahl": 0, "suchmodus": "",
                   "ramicro_aktiv": False,
                   "hinweis": "RA-Micro Verbindung deaktiviert (RAMICRO_AKTIV=false)."})
    except RaMicroVerbindungsFehler as e:
        logger.error("Aktensuche Verbindungsfehler: %s", e)
        return _err(f"RA-Micro nicht erreichbar: {e}", 503)
    except Exception as e:
        logger.error("Aktensuche Fehler: %s", e, exc_info=True)
        return _err(f"Interner Fehler: {e}", 500)
