"""
RA-Micro Akte-Details (lesend)
================================
GET /ramicro/akte/<az>

Lädt alle verfügbaren Daten einer Akte direkt aus der RA-Micro SQL-Datenbank:
  - Stammdaten (tblAkten)
  - WDM-Variablen (_tbl0WDMDaten)
  - Alle Beteiligten mit vollständigen Adressdaten, klassifiziert in 5 Gruppen

Betreffzeilen werden serverseitig aufgelöst (RA-Micro-Variablen ersetzt).
"""

import re
import logging
import os
from flask import Blueprint, jsonify, request, make_response
from ..auth.middleware import login_erforderlich
from ..ramicro.connector import (
    get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
)

logger = logging.getLogger(__name__)
ramicro_akte_bp = Blueprint("ramicro_akte", __name__, url_prefix="/ramicro/akte")


def _j(d, s=200): return jsonify(d), s
def _err(m, s=400, **kw): return jsonify({"fehler": m, **kw}), s


# ── Beteiligten-Klassifizierung ───────────────────────────────────────────────

def _kz_beginnt_mit_m(kz: str) -> bool:
    """M, M1, M2, M3 … – Mandanten-Kennzeichen."""
    if not kz:
        return False
    return bool(re.match(r'^M\d*$', kz.strip(), re.IGNORECASE))


EIGENE_VERS_KZ   = {'HP', 'HPV', 'KASK'}
GHPV_KZ          = {'GHPV', 'GH'}
GBEV_KZ          = {'GBEV', 'GHV'}
BEHOERDEN_KZ_A4  = {'AA'}       # Art 4, trotzdem Behörde


def _klassifiziere(art: int, kz: str) -> str:
    """
    Gibt eine von 6 Gruppen zurück:
      mandant | eigene_versicherung | gegner | rechtsschutz | behoerde | weitere
    """
    kz_up = (kz or "").strip().upper()

    if art == 1:
        # M, M1, M2 … = explizit Mandant
        # Leeres Kennzeichen bei Art 1 = ebenfalls Mandant (RA-Micro-Standard)
        # Nur Ausnahmen explizit raus: SB (Sachbearbeiter), SO (Sonstiges)
        if kz_up in ("SB", "SO", "G"):
            return "weitere"
        return "mandant"

    if art == 2:
        if kz_up in EIGENE_VERS_KZ:
            return "eigene_versicherung"
        return "gegner"

    if art == 3:
        return "rechtsschutz"

    if art == 4:
        if kz_up in GHPV_KZ:
            return "gegner"
        if kz_up in GBEV_KZ:
            return "gegner"
        if kz_up in EIGENE_VERS_KZ:
            return "eigene_versicherung"
        if kz_up in BEHOERDEN_KZ_A4:
            return "behoerde"
        return "weitere"

    if art == 6:
        return "behoerde"

    if art == 9:
        return "gegner"

    return "weitere"


# ── RA-Micro Variablen-Ersetzung (analog sachstandsanfrage_wv.py) ─────────────

def _ersetze_vars(text: str, wdm: dict) -> str:
    """Ersetzt <VARIABLENNAME> durch Werte aus WDM-Dict."""
    if not text:
        return ""
    def _sub(m):
        name = m.group(1)
        if name.startswith("$"):
            return ""
        return wdm.get(f"var{name}") or wdm.get(f"var{name.upper()}") or ""
    return re.sub(r"<([^>]+)>", _sub, text).strip()


# ── Beteiligten-Dict aufbauen ─────────────────────────────────────────────────

def _beteiligte_dict(row: dict, wdm: dict) -> dict:
    vorname  = (row.get("sVorname")  or "").strip()
    nachname = (row.get("sNachname") or "").strip()
    name     = f"{vorname} {nachname}".strip() if vorname else nachname

    betreff1 = _ersetze_vars(row.get("sBetreffZeile1") or "", wdm)
    betreff2 = _ersetze_vars(row.get("sBetreffZeile2") or "", wdm)
    betreff3 = _ersetze_vars(row.get("sBetreffZeile3") or "", wdm)

    return {
        "name":         name,
        "vorname":      vorname,
        "nachname":     nachname,
        "anrede":       (row.get("sAnrede")      or "").strip(),
        "briefanrede":  (row.get("sBriefanrede") or "").strip(),
        "strasse":      (row.get("sStrasse")     or "").strip(),
        "plz":          (row.get("sPLZ")         or "").strip(),
        "ort":          (row.get("sOrt")         or "").strip(),
        "telefon":      (row.get("sTelefon")        or "").strip(),
        "telefon2":     (row.get("sTelefon2")       or "").strip(),
        "mobil":        (row.get("sMobiltelefon")   or row.get("sMobil") or row.get("sHandy") or "").strip(),
        "fax":          (row.get("sTelefax")     or "").strip(),
        "email":        (row.get("sEMail")       or "").strip(),
        "betreff1":     betreff1,
        "betreff2":     betreff2,
        "betreff3":     betreff3,
        "kennzeichen":  (row.get("kennzeichen")  or "").strip(),
        "art":          row.get("art", 0),
        "adress_nr":    row.get("iAdressNummer"),
    }


def _az_basis(az: str) -> str:
    """
    Schneidet das SB-Kürzel vom Aktenzeichen ab.
    "1213/25AS" → "1213/25"   "211/26TB" → "211/26"   "42/25" → "42/25"
    RA-Micro speichert sAktenNummer ohne Kürzel (z.B. "1213/25"),
    das Kürzel steht separat in sAktenSachbearbeiter ("AS").
    """
    import re as _re
    basis = _re.sub(r'[A-Z]{2,3}$', '', az.strip().upper()).strip()
    return basis if basis and "/" in basis else az


# ── Endpunkt ──────────────────────────────────────────────────────────────────

@ramicro_akte_bp.route("/debug-beteiligte", methods=["GET"])
@login_erforderlich
def debug_beteiligte():
    """GET /ramicro/akte/debug-beteiligte?az=1018/24 — zeigt rohe Art+Kennzeichen."""
    az = (request.args.get("az") or "").strip()
    if not az:
        return _err("az erforderlich", 422)
    az_like = _az_basis(az) + "%"
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 1 a.GUIDAkte FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer
            """, {"like": az_like})
            row = cur.fetchone()
            if not row:
                return _err("Akte nicht gefunden", 404)
            guid = row["GUIDAkte"]
            cur.execute("""
                SELECT b.iBeteiligtenArt AS art,
                       b.sBeteiligtenKennzeichen AS kz,
                       adr.sNachname, adr.sVorname
                FROM tblAktenBeteiligte b
                LEFT JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.GUIDAkte = %(guid)s AND b.bDeaktiviert = 0
                ORDER BY b.iBeteiligtenArt, b.sBeteiligtenKennzeichen
            """, {"guid": guid})
            rows = cur.fetchall()
        return _j([{"art": r["art"], "kz": r["kz"], "name": f"{r['sVorname'] or ''} {r['sNachname'] or ''}".strip(),
                    "gruppe": _klassifiziere(r["art"], r["kz"])} for r in rows])
    except Exception as e:
        return _err(str(e), 500)


@ramicro_akte_bp.route("/wdm-schaden", methods=["GET"])
@login_erforderlich
def wdm_schaden():
    """
    GET /ramicro/akte/wdm-schaden?az=211/26

    Liest Schadenpositionen aus WDM-Variablen mit dem präzisen Kanzlei-Mapping.
    Netto + MwSt-Variablen werden zu Brutto summiert.
    Sonstige Schäden 1-6 landen in wdm_extras.
    """
    az = (request.args.get("az") or "").strip()
    if not az:
        return _err("az erforderlich", 422)
    az_basis = _az_basis(az)

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            # 1. Echte AktenNr aus tblAkten holen (exakter Match für WDM-Abfrage)
            cur.execute("""
                SELECT TOP 1 a.sAktenNummer AS az_roh
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return _j({"az": az, "schaden": {}, "extras": [], "info": {},
                           "quellen": {}, "felder_gefunden": 0, "extras_gefunden": 0,
                           "mapping_konfiguriert": True, "wdm_variablen_gesamt": 0,
                           "hinweis": f"Akte {az} nicht in RA-Micro gefunden."})
            az_roh = row["az_roh"]  # exakter Wert aus DB z.B. "1/16GK"
            # WDM speichert AktenNr OHNE SB-Kürzel → Kürzel abschneiden
            az_wdm = _az_basis(az_roh)

            # 2. WDM-Variablen mit AktenNr ohne SB-Kürzel laden
            cur.execute("""
                SELECT sName, CAST(Value AS nvarchar(500)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_wdm)s
                  AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(500)) != ''
            """, {"az_wdm": az_wdm})
            raw = {}
            for r in cur.fetchall():
                wert = (r["wert"] or "").strip()
                raw[r["sName"]] = wert

    except RaMicroNichtAktiv:
        return _err("RA-Micro nicht aktiv", 503)
    except RaMicroVerbindungsFehler as e:
        return _err(f"RA-Micro nicht erreichbar: {e}", 503)
    except Exception as e:
        return _err(str(e), 500)

    # raw-Dict case-insensitiv machen (RA-Micro schreibt Variablen manchmal anders)
    raw_ci = {k.lower(): v for k, v in raw.items()}

    def _zahl(name: str) -> float:
        """Liest eine WDM-Variable als float — case-insensitiv, EUR-Suffix tolerant."""
        v = raw.get(name) or raw_ci.get(name.lower()) or ""
        v = v.strip().upper().replace(" EUR", "").replace("EUR", "").strip()
        if not v:
            return 0.0
        try:
            return float(v.replace(".", "").replace(",", "."))
        except ValueError:
            return 0.0

    def _text(name: str) -> str:
        return (raw.get(name) or raw_ci.get(name.lower()) or "").strip()

    def _brutto(netto_var: str, ust_var: str) -> float:
        return _zahl(netto_var) + _zahl(ust_var)

    # ── Reparaturkosten: beide Varianten separat speichern ────────────────
    rep_gutachten_netto = _zahl("varREPKOSTENSV")     # lt. Gutachten, netto
    rep_gutachten_mwst  = _zahl("varUST-REPKOSTENSV")
    rep_konkret_netto = _zahl("varREPKOSTEN")          # lt. Rechnung, netto
    rep_konkret_mwst  = _zahl("varUST-REPKOSTEN")
    rep_konkret_brutto = rep_konkret_netto + rep_konkret_mwst


    rep_quelle = []
    if rep_gutachten_netto > 0:  rep_quelle.append("varREPKOSTENSV")
    if rep_konkret_netto > 0: rep_quelle.append("varREPKOSTEN+UST (konkret/Rechnung)")

    # ── SV-Kosten: Honorar + Nachbesichtigung (netto + ust getrennt) ────────
    sv_kosten_netto = _zahl("varKOSTENSV") + _zahl("varKOSTENNB")
    sv_kosten_ust   = _zahl("varUST-KOSTENSV") + _zahl("varUST-KOSTENNB")
    sv_kosten       = sv_kosten_netto + sv_kosten_ust  # Brutto als Fallback

    # ── Sonstige Schäden 1-6 → extras ────────────────────────────────────
    extras = []
    for i in range(1, 7):
        betrag_var = f"varSSBETRAG{i}" if i != 5 else "varSSBETRAG5A"
        bezeichnung = _text(f"varSSCHADEN{i}")
        betrag = _brutto(betrag_var, f"varUST-SS{i}")
        if bezeichnung or betrag > 0:
            extras.append({
                "id":        f"wdm_ss{i}",
                "label":     bezeichnung or f"Sonstiger Schaden {i}",
                "betrag":    betrag,
                "netto":     _zahl(betrag_var),
                "mwst":      _zahl(f"varUST-SS{i}"),
                "wdm_var":   betrag_var,
            })

    # ── Info-Felder (nicht monetär) ───────────────────────────────────────
    info = {}
    if _text("varFKLASSE"):   info["fahrzeugklasse_na"] = _text("varFKLASSE")
    if _zahl("varNABETRAG"):  info["na_tagessatz"]      = _zahl("varNABETRAG")
    if _zahl("varREPDAUER"):  info["reparaturdauer"]    = _zahl("varREPDAUER")

    schaden = {
        "rep_gutachten_netto":  rep_gutachten_netto,
        "rep_gutachten_mwst":   rep_gutachten_mwst,
        "rep_rechnung_netto":   rep_konkret_netto,       # lt. Werkstattrechnung netto
        "rep_rechnung_brutto":  rep_konkret_brutto,
        "wiederbeschaffung":    _zahl("varWIEDERBESCHAFF"),
        "restwert":             _zahl("varRESTWERT"),
        "wertminderung":        _zahl("varWERTMIND"),
        "nutzungsausfall":      _zahl("varNUTZUNGSA"),
        "mietwagenkosten":      _brutto("varMIETWAGEN",    "varUST-MIETWAGEN"),
        "mietwagenkosten_netto": _zahl("varMIETWAGEN"),
        "mietwagenkosten_ust":   _zahl("varUST-MIETWAGEN"),
        "sv_kosten":            sv_kosten,
        "sv_kosten_netto":      sv_kosten_netto,
        "sv_kosten_ust":        sv_kosten_ust,
        "abschleppkosten":      _brutto("varABSCHLEPP",   "varUST-ABSCHLEPP"),
        "abschleppkosten_netto": _zahl("varABSCHLEPP"),
        "abschleppkosten_ust":   _zahl("varUST-ABSCHLEPP"),
        "standkosten":          _brutto("varSTANDKOSTEN",  "varUST-STANDKOSTEN"),
        "standkosten_netto":     _zahl("varSTANDKOSTEN"),
        "standkosten_ust":       _zahl("varUST-STANDKOSTEN"),
        "anabmeldekosten":      _brutto("varANABKOSTEN",   "varUST-ANABKOSTEN"),
        "anabmeldekosten_netto": _zahl("varANABKOSTEN"),
        "anabmeldekosten_ust":   _zahl("varUST-ANABKOSTEN"),
        "schmerzensgeld":       _zahl("varSCHMGELD"),
        "verdienstausfall":     _zahl("varVERDIENST"),
        "haushalt":             _zahl("varHAUSHALT"),
        "unkostenpauschale":    _zahl("varUNKOSTEN"),
    }

    quellen = {
        "rep_gutachten_netto":  "varREPKOSTENSV",
        "rep_gutachten_mwst":   "varUST-REPKOSTENSV",
        "rep_rechnung_netto":   "varREPKOSTEN",
        "rep_rechnung_brutto":  "varREPKOSTEN + varUST-REPKOSTEN",
        "wiederbeschaffung":    "varWIEDERBESCHAFF",
        "restwert":             "varRESTWERT",
        "wertminderung":        "varWERTMIND",
        "nutzungsausfall":      "varNUTZUNGSA",
        "mietwagenkosten":      "varMIETWAGEN + varUST-MIETWAGEN",
        "mietwagenkosten_netto": "varMIETWAGEN",
        "mietwagenkosten_ust":   "varUST-MIETWAGEN",
        "sv_kosten":            "varKOSTENSV + varUST-KOSTENSV + varKOSTENNB + varUST-KOSTENNB",
        "sv_kosten_netto":      "varKOSTENSV + varKOSTENNB",
        "sv_kosten_ust":        "varUST-KOSTENSV + varUST-KOSTENNB",
        "abschleppkosten":      "varABSCHLEPP + varUST-ABSCHLEPP",
        "abschleppkosten_netto": "varABSCHLEPP",
        "abschleppkosten_ust":   "varUST-ABSCHLEPP",
        "standkosten":          "varSTANDKOSTEN + varUST-STANDKOSTEN",
        "standkosten_netto":    "varSTANDKOSTEN",
        "standkosten_ust":      "varUST-STANDKOSTEN",
        "anabmeldekosten":      "varANABKOSTEN + varUST-ANABKOSTEN",
        "anabmeldekosten_netto": "varANABKOSTEN",
        "anabmeldekosten_ust":   "varUST-ANABKOSTEN",
        "schmerzensgeld":       "varSCHMGELD",
        "verdienstausfall":     "varVERDIENST",
        "haushalt":             "varHAUSHALT",
        "unkostenpauschale":    "varUNKOSTEN (30 €)",
    }

    felder_gefunden = sum(1 for v in schaden.values() if v and v > 0)

    return _j({
        "az":               az,
        "schaden":          schaden,
        "extras":           extras,
        "info":             info,
        "quellen":          quellen,
        "felder_gefunden":  felder_gefunden,
        "extras_gefunden":  len(extras),
        "mapping_konfiguriert": True,
        "wdm_variablen_gesamt": len(raw),
    })


@ramicro_akte_bp.route("/liste", methods=["GET"])
@login_erforderlich
def aktenliste():
    """
    GET /ramicro/akte/liste?seite=1&limit=50&sb=AS&status=offen

    Paginierte Aktenliste direkt aus RA-Micro.
    Optional: sb=Sachbearbeiter-Kürzel, status=lokaler Status-Filter
    """
    from flask import g
    seite  = max(1, request.args.get("seite", 1, type=int))
    limit  = min(50, max(1, request.args.get("limit", 50, type=int)))
    offset = (seite - 1) * limit
    sb_filter = (request.args.get("sb") or "").strip().upper() or None

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            sb_sql = "AND a.sAktenSachbearbeiter = %(sb)s" if sb_filter else ""

            # Gesamtanzahl
            cur.execute(f"""
                SELECT COUNT(*) AS n
                FROM tblAkten a
                WHERE (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                  {sb_sql}
            """, {"sb": sb_filter} if sb_filter else {})
            gesamt = cur.fetchone()["n"]

            # Seite laden + KFZ per LEFT JOIN
            cur.execute(f"""
                SELECT
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS sachbearbeiter,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    a.sAktenBezeichnung     AS bezeichnung,
                    a.sMandant              AS mandant,
                    kz.kz_wert              AS kennzeichen
                FROM tblAkten a
                LEFT JOIN (
                    SELECT AktenNr, CAST(Value AS nvarchar(50)) AS kz_wert
                    FROM _tbl0WDMDaten
                    WHERE sName IN ('varM-KZ','var_M-KZ','M-KZ')
                      AND Value IS NOT NULL AND CAST(Value AS nvarchar(50)) != ''
                ) kz ON kz.AktenNr = a.sAktenNummer
                WHERE (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                  {sb_sql}
                ORDER BY a.sAktenNummer ASC
                OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY
            """, {"sb": sb_filter} if sb_filter else {})
            rows = cur.fetchall()

        def _fmt(r):
            az_roh = r["az_roh"] or ""
            sb     = r["sachbearbeiter"] or ""
            az     = az_roh + sb if sb and not az_roh.upper().endswith(sb.upper()) else az_roh
            return {
                "az":              az,
                "az_roh":          az_roh,
                "sachbearbeiter":  sb,
                "kurzbezeichnung": r["kurzbezeichnung"] or "",
                "bezeichnung":     r["bezeichnung"]     or "",
                "mandant":         r["mandant"]          or "",
                "kennzeichen":     r["kennzeichen"]      or "",
            }

        return _j({
            "akten":        [_fmt(r) for r in rows],
            "gesamt":       gesamt,
            "seite":        seite,
            "limit":        limit,
            "seiten":       max(1, (gesamt + limit - 1) // limit),
            "ramicro_aktiv": True,
        })

    except RaMicroNichtAktiv:
        return _j({"akten": [], "gesamt": 0, "seite": 1, "seiten": 1,
                   "ramicro_aktiv": False,
                   "hinweis": "RA-Micro nicht aktiv (RAMICRO_AKTIV=false)."})
    except RaMicroVerbindungsFehler as e:
        return _err(f"RA-Micro nicht erreichbar: {e}", 503)
    except Exception as e:
        logger.error("aktenliste Fehler: %s", e, exc_info=True)
        return _err(f"Interner Fehler: {e}", 500)


@ramicro_akte_bp.route("/on-demand", methods=["POST"])
@login_erforderlich
def on_demand_anlegen():
    """
    POST /ramicro/akte/on-demand
    Body: { "az": "211/26" }

    Legt die Akte in der lokalen SQLite an (falls noch nicht vorhanden)
    und gibt die lokale Akte zurück. Wird beim ersten Öffnen aufgerufen.
    """
    from flask import g
    from ..models.akte import erstelle_oder_hole_akte
    daten = request.get_json(silent=True) or {}
    az = (daten.get("az") or "").strip()
    if not az or "/" not in az:
        return _err("az erforderlich (Format: ZAHL/JJ).", 422)

    # RA-Micro Stammdaten holen für den Cache
    az_like = _az_basis(az) + "%"
    kurzbezeichnung = sachbearbeiter = None
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 1
                    a.sAktenKurzBezeichnung AS kb,
                    a.sAktenSachbearbeiter  AS sb
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE)='1899-12-30')
            """, {"like": az_like})
            row = cur.fetchone()
            if row:
                kurzbezeichnung = row["kb"]
                sachbearbeiter  = row["sb"]
    except Exception:
        pass  # RA-Micro nicht erreichbar → trotzdem lokal anlegen

    akte = erstelle_oder_hole_akte(
        az=az,
        bearbeiter_id=getattr(g, "benutzer_id", None),
        kurzbezeichnung=kurzbezeichnung,
        sachbearbeiter=sachbearbeiter,
    )
    return _j({"az": akte.az, "neu": akte.erstellt_am == akte.geaendert_am})


@ramicro_akte_bp.route("", methods=["GET"])
@login_erforderlich
def akte_details():
    """
    GET /ramicro/akte/211/26

    Lädt alle Stamm- und Beteiligten-Daten einer Akte aus RA-Micro.
    az wird als Pfad übergeben (Schrägstrich erlaubt via <path:az>).

    Response 200:
    {
      "stammdaten": { az, kurzbezeichnung, bezeichnung, sachbearbeiter, ... },
      "wdm":        { "varU-TAG": "23.02.26", "varM-KZ": "OF-NM 444", ... },
      "beteiligte": {
        "mandant":           [...],   // max. 1 Eintrag (erster M-Beteiligter)
        "eigene_versicherung": [...],
        "gegner":            [...],
        "rechtsschutz":      [...],
        "behoerde":          [...],
        "weitere":           [...]
      }
    }
    """
    az = (request.args.get("az") or "").strip()
    if not az or "/" not in az:
        return _err("Aktenzeichen muss Format ZAHL/JJ haben (z.B. 211/26).", 422)

    # SB-Kürzel abschneiden: "1213/25AS" → "1213/25"
    az_basis = _az_basis(az)

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # ── 1. Stammdaten ──────────────────────────────────────────────
            cur.execute("""
                SELECT TOP 1
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS sachbearbeiter,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    a.sAktenBezeichnung     AS bezeichnung,
                    a.sMandant              AS mandant,
                    a.sGegner               AS gegner,
                    a.iReferat              AS referat,
                    a.GUIDAkte              AS guid_akte
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(az_like)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"az_like": f"{az_basis}%"})
            stamm_row = cur.fetchone()

            if not stamm_row:
                return _err(f"Akte {az} nicht gefunden oder archiviert.", 404)

            guid_akte = stamm_row["guid_akte"]
            az_roh    = stamm_row["az_roh"]
            sb        = stamm_row["sachbearbeiter"] or ""
            az_voll   = az_roh + sb if sb and not az_roh.upper().endswith(sb.upper()) else az_roh
            # WDM speichert AktenNr OHNE SB-Kürzel
            az_wdm    = _az_basis(az_roh)

            stammdaten = {
                "az":              az_voll,
                "az_roh":          az_roh,
                "sachbearbeiter":  sb,
                "kurzbezeichnung": stamm_row["kurzbezeichnung"] or "",
                "bezeichnung":     stamm_row["bezeichnung"]     or "",
                "mandant":         stamm_row["mandant"]         or "",
                "gegner":          stamm_row["gegner"]          or "",
                "referat":         stamm_row["referat"],
            }

            # ── 2. WDM-Variablen ───────────────────────────────────────────
            cur.execute("""
                SELECT sName, CAST(Value AS nvarchar(500)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_wdm)s
                  AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(max)) != ''
            """, {"az_wdm": az_wdm})
            wdm = {r["sName"]: r["wert"] for r in cur.fetchall()}

            # Komfort-Felder direkt aus WDM
            stammdaten["unfalltag"]     = wdm.get("varU-TAG", "")
            stammdaten["kfz_mandant"]   = wdm.get("varM-KZ", "")
            stammdaten["kfz_gegner"]    = wdm.get("varG-KZ", "")

            # ── 3. Beteiligte (mit Fallback für unbekannte Mobilspalten) ──
            def _beteiligte_query(mit_mobil: bool) -> str:
                mobil_cols = ",\n                    adr.sTelefon2       AS sTelefon2,\n                    adr.sMobiltelefon   AS sMobiltelefon" if mit_mobil else ""
                return f"""
                SELECT
                    b.iBeteiligtenArt                   AS art,
                    b.sBeteiligtenKennzeichen            AS kennzeichen,
                    b.iAdressNummer,
                    b.sBetreffZeile1,
                    b.sBetreffZeile2,
                    b.sBetreffZeile3,
                    adr.sNachname,
                    adr.sVorname,
                    adr.sAnrede,
                    adr.sBriefanrede,
                    adr.[sStraße]   AS sStrasse,
                    adr.sPLZ,
                    adr.sOrt,
                    adr.sTelefon{mobil_cols},
                    adr.sTelefax,
                    adr.sEMail
                FROM tblAktenBeteiligte b
                INNER JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.GUIDAkte = %(guid)s
                  AND b.bDeaktiviert = 0
                  AND b.GUIDAdresse IS NOT NULL
                ORDER BY b.iBeteiligtenArt ASC, b.sBeteiligtenKennzeichen ASC
                """
            try:
                cur.execute(_beteiligte_query(mit_mobil=True), {"guid": guid_akte})
            except Exception:
                # Mobilspalte nicht vorhanden → ohne abfragen
                cur.execute(_beteiligte_query(mit_mobil=False), {"guid": guid_akte})
            alle_rows = cur.fetchall()

        # ── Klassifizieren ─────────────────────────────────────────────────
        gruppen = {
            "mandant":            [],
            "eigene_versicherung":[],
            "gegner":             [],
            "rechtsschutz":       [],
            "behoerde":           [],
            "weitere":            [],
        }
        seen_adr = set()

        for row in alle_rows:
            adr_nr = row.get("iAdressNummer")
            if adr_nr and adr_nr in seen_adr:
                continue
            if adr_nr:
                seen_adr.add(adr_nr)

            gruppe = _klassifiziere(row.get("art", 0), row.get("kennzeichen", ""))

            eintrag = _beteiligte_dict(dict(row), wdm)
            if gruppe == "mandant" and gruppen["mandant"]:
                continue  # nur erster Mandant
            gruppen[gruppe].append(eintrag)

        return _j({
            "stammdaten": stammdaten,
            "wdm":        wdm,
            "beteiligte": gruppen,
        })

    except RaMicroNichtAktiv:
        return _j({
            "fehler": "RA-Micro Verbindung deaktiviert (RAMICRO_AKTIV=false).",
            "ramicro_aktiv": False,
        }, 503)
    except RaMicroVerbindungsFehler as e:
        logger.error("ramicro_akte: Verbindungsfehler: %s", e)
        return _err(f"RA-Micro nicht erreichbar: {e}", 503)
    except Exception as e:
        logger.error("ramicro_akte: Fehler: %s", e, exc_info=True)
        return _err(f"Interner Fehler: {e}", 500)


# ══════════════════════════════════════════════════════════════════════════════
# ADRESSSUCHE (für Personenschaden-Tab)
# ══════════════════════════════════════════════════════════════════════════════

@ramicro_akte_bp.route("/adressen/suche", methods=["GET"])
@login_erforderlich
def adressen_suche():
    """
    GET /ramicro/akte/adressen/suche?q=<name_oder_nr>&limit=10

    Sucht in tblAdressen nach Name oder Adressnummer.
    Wird für das Adress-Suchfeld im Personenschaden-Tab verwendet.

    q kann sein:
      - Zahl  → direkte Suche nach iAdressnummer
      - Text  → LIKE-Suche auf sNachname + sErsteAdresszeile + sOrt
    """
    q     = (request.args.get("q") or "").strip()
    limit = min(int(request.args.get("limit", 10)), 50)

    if not q or len(q) < 2:
        return jsonify({"ergebnisse": [], "hinweis": "Mindestens 2 Zeichen eingeben."})

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # TOP N als Integer direkt in SQL einsetzen (pymssql unterstützt
            # keine Parameter im TOP-Clause)
            top_n = int(limit)  # bereits als int validiert (max 50)

            # Numerische Eingabe → direkte Adressnummer-Suche
            if q.isdigit():
                cur.execute(f"""
                    SELECT TOP {top_n}
                        iAdressNummer     AS adressnr,
                        sErsteAdresszeile AS firma,
                        sNachname         AS nachname,
                        sVorname          AS vorname,
                        [sStraße]          AS strasse,
                        sPLZ              AS plz,
                        sOrt              AS ort,
                        sTelefon          AS telefon,
                        sEMail            AS email
                    FROM tblAdressen
                    WHERE iAdressNummer = %(nr)s
                """, {"nr": int(q)})
            else:
                # Textsuche: Nachname, Vorname, Firmenname oder Ort
                like   = f"%{q}%"
                starts = f"{q}%"
                cur.execute(f"""
                    SELECT TOP {top_n}
                        iAdressNummer     AS adressnr,
                        sErsteAdresszeile AS firma,
                        sNachname         AS nachname,
                        sVorname          AS vorname,
                        [sStraße]          AS strasse,
                        sPLZ              AS plz,
                        sOrt              AS ort,
                        sTelefon          AS telefon,
                        sEMail            AS email
                    FROM tblAdressen
                    WHERE (
                        sNachname         LIKE %(like)s OR
                        sVorname          LIKE %(like)s OR
                        sErsteAdresszeile LIKE %(like)s OR
                        sOrt              LIKE %(like)s
                    )
                    ORDER BY
                        CASE
                            WHEN sNachname         LIKE %(starts)s THEN 0
                            WHEN sErsteAdresszeile LIKE %(starts)s THEN 1
                            ELSE 2
                        END,
                        sNachname ASC,
                        sErsteAdresszeile ASC
                """, {"like": like, "starts": starts})

            rows = cur.fetchall()

    except RaMicroNichtAktiv:
        return jsonify({"ergebnisse": [], "fehler": "RA-Micro nicht aktiv."}), 503
    except RaMicroVerbindungsFehler as e:
        return jsonify({"ergebnisse": [], "fehler": str(e)}), 503
    except Exception as e:
        logger.error("adressen_suche: %s", e)
        return jsonify({"ergebnisse": [], "fehler": str(e)}), 500

    ergebnisse = []
    for r in rows:
        firma   = (r.get("firma")   or "").strip()
        vorname = (r.get("vorname") or "").strip()
        nachname= (r.get("nachname")or "").strip()
        name = firma if firma else f"{vorname} {nachname}".strip()
        ergebnisse.append({
            "adressnr": r.get("adressnr"),
            "name":     name,
            "firma":    firma,
            "vorname":  vorname,
            "nachname": nachname,
            "strasse":  (r.get("strasse") or "").strip(),
            "plz":      (r.get("plz")     or "").strip(),
            "ort":      (r.get("ort")     or "").strip(),
            "telefon":  (r.get("telefon") or "").strip(),
            "email":    (r.get("email")   or "").strip(),
        })

    return jsonify({"ergebnisse": ergebnisse, "anzahl": len(ergebnisse)})


# ══════════════════════════════════════════════════════════════════════════════
# MANDANT-CHECKS (IBAN, später Vollmacht)
# ══════════════════════════════════════════════════════════════════════════════

@ramicro_akte_bp.route("/mandant-checks", methods=["GET"])
@login_erforderlich
def mandant_checks():
    """GET /ramicro/akte/mandant-checks?az=
    Prüft: IBAN (tblAdressenBankverbindungen), Vollmacht (WDM),
    RSV-Beteiligter (tblAktenBeteiligte iBeteiligtenArt=3).
    Returns: {iban_vorhanden, vollmacht_vorhanden, rechtsschutz_deckung, mandant_name, ...}
    """
    az = (request.args.get("az") or "").strip()
    if not az:
        return jsonify({"fehler": "az erforderlich"}), 422

    import re as _re
    az_basis = _re.sub(r'[A-Z]{2,3}$', '', az.strip().upper()).strip()
    if not az_basis or "/" not in az_basis:
        az_basis = az

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # Akte + GUIDAkte holen
            cur.execute("""
                SELECT TOP 1
                    a.GUIDAkte,
                    a.sAktenNummer          AS az_roh,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    a.sAktenBezeichnung     AS bezeichnung
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return jsonify({"iban_vorhanden": False, "fehler": "Akte nicht gefunden"})
            guid_akte = row["GUIDAkte"]

            # Mandant + seine GUIDAdresse + IBAN
            cur.execute("""
                SELECT TOP 1
                    adr.GUIDAdresse,
                    adr.sNachname       AS nachname,
                    adr.sVorname        AS vorname,
                    adr.sErsteAdresszeile AS firma,
                    adr.sEMail          AS email,
                    bv.sIBAN            AS iban,
                    bv.sBIC             AS bic,
                    bv.sGeldinstitut    AS geldinstitut
                FROM tblAktenBeteiligte b
                INNER JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                LEFT JOIN tblAdressenBankverbindungen bv
                    ON bv.GUIDAdresse = b.GUIDAdresse
                    AND (bv.bStandardBankverbindung = 1 OR bv.iIDBankverbindung = (
                        SELECT MIN(iIDBankverbindung)
                        FROM tblAdressenBankverbindungen
                        WHERE GUIDAdresse = b.GUIDAdresse
                    ))
                WHERE b.GUIDAkte = %(guid)s
                  AND b.iBeteiligtenArt = 1
                  AND b.bDeaktiviert = 0
                ORDER BY b.iBeteiligtenArt ASC
            """, {"guid": guid_akte})
            m = cur.fetchone()

            # WDM: varVOLLMACHTERKL prüfen – innerhalb derselben Verbindung
            vollmacht_wdm = False
            if m:
                try:
                    cur.execute("""
                        SELECT TOP 1 CAST(Value AS nvarchar(20)) AS wert
                        FROM _tbl0WDMDaten
                        WHERE AktenNr = %(az)s
                          AND sName = 'varVOLLMACHTERKL'
                          AND Value IS NOT NULL
                    """, {"az": row["az_roh"]})
                    wv = cur.fetchone()
                    if wv and (wv.get("wert") or "").strip().lower() in ("ja", "j", "yes", "1", "true"):
                        vollmacht_wdm = True
                except Exception as ve:
                    logger.debug("vollmacht_wdm check: %s", ve)

            # RSV-Check: Beteiligter mit iBeteiligtenArt = 3 in tblAktenBeteiligte
            rsv_vorhanden = False
            try:
                cur.execute("""
                    SELECT COUNT(*) AS n
                    FROM tblAktenBeteiligte
                    WHERE GUIDAkte = %(guid)s AND iBeteiligtenArt = 3 AND bDeaktiviert = 0
                """, {"guid": guid_akte})
                rsv_row = cur.fetchone()
                rsv_vorhanden = bool(rsv_row and rsv_row["n"] > 0)
            except Exception as re_:
                logger.debug("rsv_check(%s): %s", az_basis, re_)

    except RaMicroNichtAktiv:
        return jsonify({"iban_vorhanden": None, "fehler": "RA-Micro nicht aktiv"}), 503
    except RaMicroVerbindungsFehler as e:
        return jsonify({"iban_vorhanden": None, "fehler": str(e)}), 503
    except Exception as e:
        logger.warning("mandant_checks(%s): %s", az, e)
        return jsonify({"iban_vorhanden": None, "fehler": str(e)}), 500

    kurzbez   = (row.get("kurzbezeichnung") or "").strip() if row else ""
    langbez   = (row.get("bezeichnung")    or "").strip() if row else ""

    if not m:
        return jsonify({
            "iban_vorhanden":        False,
            "vollmacht_vorhanden":   False,
            "rechtsschutz_deckung":  rsv_vorhanden,
            "mandant_name":          "",
            "mandant_email":         "",
            "kurzbezeichnung":       kurzbez,
            "bezeichnung":           langbez,
        })

    firma   = (m.get("firma")   or "").strip()
    vorname = (m.get("vorname") or "").strip()
    nachname= (m.get("nachname")or "").strip()
    name    = firma if firma else f"{vorname} {nachname}".strip()
    iban    = (m.get("iban") or "").strip()

    return jsonify({
        "iban_vorhanden":        bool(iban),
        "iban":                  iban if iban else None,
        "bic":                   (m.get("bic") or "").strip() or None,
        "geldinstitut":          (m.get("geldinstitut") or "").strip() or None,
        "mandant_name":          name,
        "mandant_email":         (m.get("email") or "").strip() or None,
        "vollmacht_vorhanden":   vollmacht_wdm,
        "rechtsschutz_deckung":  rsv_vorhanden,
        "az_roh":                az_basis,
        "kurzbezeichnung":       kurzbez,
        "bezeichnung":           langbez,
    })


# ══════════════════════════════════════════════════════════════════════════════
# VOLLMACHT-DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════════

@ramicro_akte_bp.route("/vollmacht", methods=["GET"])
@login_erforderlich
def vollmacht_generieren():
    """
    GET /ramicro/akte/vollmacht?az=242/26

    Generiert eine aktenbezogene Vollmacht als DOCX-Download.
    Befüllt {{AKTENZEICHEN}}, {{AKTENKURZBEZEICHNUNG}}, {{AKTENLANGBEZEICHNUNG}}, {{DATUM}}
    automatisch aus RA-Micro Stammdaten.
    """
    import re as _re
    from flask import current_app, make_response

    az = (request.args.get("az") or "").strip()
    if not az:
        return jsonify({"fehler": "az erforderlich"}), 422

    az_basis = _re.sub(r'[A-Z]{2,3}$', '', az.strip().upper()).strip()
    if not az_basis or "/" not in az_basis:
        az_basis = az

    kurz = lang = ""
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 1
                    a.sAktenKurzBezeichnung AS kurz,
                    a.sAktenBezeichnung AS lang
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if row:
                kurz = (row.get("kurz") or "").strip()
                lang = (row.get("lang") or "").strip()
    except Exception as e:
        logger.debug("vollmacht stammdaten %s: %s", az, e)

    try:
        vorlage_pfad = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "word", "vollmacht_vorlage.docx"
        ))
        logger.info("Vollmacht Vorlage Pfad: %s (exists=%s)", vorlage_pfad, os.path.exists(vorlage_pfad))

        from ..word.vollmacht_service import generiere_vollmacht
        pdf_bytes = generiere_vollmacht(
            aktenzeichen=az_basis,
            kurz=kurz,
            lang=lang,
            vorlage_pfad=vorlage_pfad,
            als_pdf=True,
        )
    except FileNotFoundError as e:
        logger.error("Vollmacht Vorlage nicht gefunden: %s", e)
        return jsonify({"fehler": f"Vollmacht-Vorlage fehlt: {e}", "pfad": vorlage_pfad if 'vorlage_pfad' in dir() else "unbekannt"}), 500
    except Exception as e:
        logger.error("vollmacht_generieren(%s): %s", az, e, exc_info=True)
        return jsonify({"fehler": str(e), "typ": type(e).__name__}), 500

    dateiname = f"Vollmacht_{az_basis.replace('/', '_')}.pdf"
    response = make_response(pdf_bytes)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{dateiname}"'
    return response
