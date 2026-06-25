"""
Dashboard-Router – PRD-25b
===========================
Endpunkte für das Action-Dashboard.

Endpunkte:
  GET  /dashboard/action-items    Priorisierte Arbeitsliste für den Tag
  GET  /dashboard/termine-heute   Heutige + morgige Gerichtstermine aus RA-MICRO
  GET  /dashboard/fristen         Harte Fristen aus RA-MICRO (Codes 21,22,31,46,75), überfällig bis +14 Tage
  GET  /dashboard/wiedervorlagen  WV überfällig+heute aus RA-MICRO + lokale Akten ohne aktive WV

Python 3.9 kompatibel.
"""

import re
import logging
from datetime import date, timedelta
from flask import Blueprint, jsonify, g

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..ramicro.connector import (
    get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
)

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _j(daten, status=200):
    r = jsonify(daten)
    r.status_code = status
    return r


# ══════════════════════════════════════════════════════════════
#  GET /dashboard/action-items
# ══════════════════════════════════════════════════════════════

@dashboard_bp.route("/action-items", methods=["GET"])
@login_erforderlich
def action_items():
    """
    Gibt alle priorisierten Arbeitsaufgaben für das Action-Dashboard zurück.

    Response:
    {
      "fristen":             [...],   # offene system-Todos ≤ 30 Tage
      "eingaenge":           {...},   # nicht zugeordnete E-Mails + Fragebogen
      "regulierung_offen":   [...],   # ausstehende Regulierungen
      "akten_ohne_bewegung": [...],   # inaktive Akten mit Vorschlag
      "generiert_am":        "..."
    }
    """
    with get_connection() as conn:
        return _j({
            "fristen":             _lade_fristen(conn),
            "eingaenge":           _lade_eingaenge(conn),
            "regulierung_offen":   _lade_regulierung_offen(conn),
            "akten_ohne_bewegung": _lade_akten_ohne_bewegung(conn),
            "generiert_am":        date.today().isoformat(),
        })


# ── Block 1: Fristen ──────────────────────────────────────────────────────────

def _lade_fristen(conn):
    """
    Alle offenen system-Todos die in den nächsten 30 Tagen fällig sind,
    sortiert nach faellig_am aufsteigend.
    """
    horizont = (date.today() + timedelta(days=30)).isoformat()
    heute    = date.today().isoformat()

    rows = conn.execute(
        """
        SELECT
            t.id,
            t.akte_az,
            t.text,
            t.faellig_am,
            t.frist_typ,
            t.regel_key,
            CAST(julianday(t.faellig_am) - julianday('now') AS INTEGER)
                AS tage_bis_faellig,
            (SELECT name FROM beteiligte
             WHERE akte_id = t.akte_az AND rolle = 'mandant'
             LIMIT 1) AS mandant_name
        FROM todos t
        WHERE t.erledigt   = 0
          AND t.quelle     = 'system'
          AND t.faellig_am <= ?
        ORDER BY t.faellig_am ASC
        LIMIT 25
        """,
        (horizont,),
    ).fetchall()

    result = []
    for r in rows:
        result.append({
            "id":               r["id"],
            "akte_az":          r["akte_az"],
            "text":             r["text"],
            "faellig_am":       r["faellig_am"],
            "frist_typ":        r["frist_typ"],
            "regel_key":        r["regel_key"],
            "tage_bis_faellig": r["tage_bis_faellig"],
            "mandant_name":     r["mandant_name"],
            "ueberfaellig":     r["faellig_am"] < heute,
        })
    return result


# ── Block 2: Neue Eingänge ────────────────────────────────────────────────────

def _lade_eingaenge(conn):
    """
    Zählt nicht zugeordnete E-Mails und neue Fragebogen-Erstkontakte.
    """
    emails = conn.execute(
        """
        SELECT COUNT(*) AS n FROM email_import_log
        WHERE status = 'nicht_zugeordnet'
          AND (email_typ IS NULL OR email_typ != 'fragebogen')
        """
    ).fetchone()["n"]

    fragebogen = 0
    try:
        fragebogen = conn.execute(
            "SELECT COUNT(*) AS n FROM fragebogen_erstkontakt WHERE status = 'neu'"
        ).fetchone()["n"]
    except Exception:
        pass  # Tabelle existiert erst ab Migration 30

    return {
        "emails_nicht_zugeordnet": emails,
        "fragebogen_neu":          fragebogen,
        "gesamt":                  emails + fragebogen,
    }


# ── Block 3: Regulierung offen ────────────────────────────────────────────────

def _lade_regulierung_offen(conn):
    """
    Regulierungen mit Status 'ausstehend' oder 'teilreguliert',
    sowie §3a PflVG-Fristen die in ≤ 14 Tagen ablaufen.
    """
    pflvg_horizont = (date.today() + timedelta(days=14)).isoformat()
    heute          = date.today().isoformat()

    # Offene Regulierungen (Option B: aus v_regulierungsstatus + abrechnungsschreiben)
    reg_rows = conn.execute(
        """
        SELECT
            v.akte_id                               AS akte_az,
            v.betrag_gefordert,
            v.betrag_reguliert,
            v.differenz                             AS betrag_differenz,
            CASE
                WHEN v.betrag_reguliert > 0 THEN 'teilreguliert'
                ELSE 'ausstehend'
            END                                     AS status,
            CAST(julianday('now') - julianday(
                COALESCE(ab_last.datum, date('now'))
            ) AS INTEGER)                           AS tage_seit_eingang,
            (SELECT b.name FROM beteiligte b
             WHERE b.akte_id = v.akte_id AND b.rolle = 'mandant'
             LIMIT 1)                               AS mandant_name
        FROM v_regulierungsstatus v
        LEFT JOIN abrechnungsschreiben ab_last
               ON ab_last.id = (
                   SELECT id FROM abrechnungsschreiben
                   WHERE akte_id = v.akte_id
                   ORDER BY datum DESC LIMIT 1
               )
        WHERE v.differenz > 0.0
          AND COALESCE(ab_last.haftungsart, '') != 'ablehnung'
        ORDER BY tage_seit_eingang DESC
        LIMIT 15
        """,
    ).fetchall()

    # §3a PflVG kurz vor Ablauf (separater Eintrag, nicht doppeln)
    pflvg_rows = conn.execute(
        """
        SELECT
            t.akte_az,
            t.faellig_am,
            CAST(julianday(t.faellig_am) - julianday('now') AS INTEGER)
                AS tage_bis_faellig,
            (SELECT name FROM beteiligte
             WHERE akte_id = t.akte_az AND rolle = 'mandant'
             LIMIT 1) AS mandant_name
        FROM todos t
        WHERE t.frist_typ = 'pflvg_3a'
          AND t.erledigt  = 0
          AND t.faellig_am <= ?
        ORDER BY t.faellig_am ASC
        LIMIT 10
        """,
        (pflvg_horizont,),
    ).fetchall()

    # Bereits vorhandene AZ aus Regulierungen sammeln um Doppel zu vermeiden
    reg_az_set = set()
    result = []

    for r in reg_rows:
        az = r["akte_az"]
        reg_az_set.add(az)
        result.append({
            "typ":              "regulierung",
            "akte_az":          az,
            "status":           r["status"],
            "betrag_gefordert": r["betrag_gefordert"],
            "betrag_differenz": r["betrag_differenz"],
            "tage_seit_eingang": r["tage_seit_eingang"],
            "mandant_name":     r["mandant_name"],
        })

    for r in pflvg_rows:
        az = r["akte_az"]
        if az in reg_az_set:
            # Füge §3a-Hinweis zum bestehenden Eintrag hinzu
            for item in result:
                if item["akte_az"] == az:
                    item["pflvg_tage"] = r["tage_bis_faellig"]
                    item["pflvg_faellig"] = r["faellig_am"]
            continue
        result.append({
            "typ":              "pflvg",
            "akte_az":          az,
            "status":           "pflvg_frist",
            "pflvg_tage":       r["tage_bis_faellig"],
            "pflvg_faellig":    r["faellig_am"],
            "mandant_name":     r["mandant_name"],
        })

    # Sortierung: überfälligste zuerst
    result.sort(key=lambda x: x.get("pflvg_tage", x.get("tage_seit_eingang", 0) * -1))
    return result


# ── Block 4: Akten ohne Bewegung ──────────────────────────────────────────────

def _lade_akten_ohne_bewegung(conn):
    """
    Akten ohne Aktivität seit mehr als 14 Tagen (offen/in_regulierung/klage).
    Gibt Vorschlag zurück: sachstandsanfrage | sachstandsanfrage_dringend | klage_pruefen
    """
    rows = conn.execute(
        """
        SELECT
            a.az AS akte_az,
            MAX(ak.zeitstempel) AS letzte_aktivitaet,
            CAST(julianday('now') - julianday(
                COALESCE(MAX(ak.zeitstempel), a.erstellt_am)
            ) AS INTEGER) AS tage_ohne_bewegung,
            (SELECT name FROM beteiligte
             WHERE akte_id = a.az AND rolle = 'mandant'
             LIMIT 1) AS mandant_name,
            (
                SELECT COUNT(*) FROM dokumente d
                WHERE d.akte_id = a.az
                  AND d.dateiname LIKE '%sachstandsanfrage%'
            ) AS sta_anzahl
        FROM unfallakte a
        LEFT JOIN aktivitaeten ak ON ak.akte_id = a.az
        WHERE a.status NOT IN ('abgeschlossen')
        GROUP BY a.az
        HAVING tage_ohne_bewegung > 14
        ORDER BY tage_ohne_bewegung DESC
        LIMIT 10
        """,
    ).fetchall()

    result = []
    for r in rows:
        tage       = r["tage_ohne_bewegung"] or 0
        sta_anzahl = r["sta_anzahl"] or 0
        vorschlag  = _berechne_vorschlag(tage, sta_anzahl)

        result.append({
            "akte_az":           r["akte_az"],
            "mandant_name":      r["mandant_name"],
            "letzte_aktivitaet": r["letzte_aktivitaet"],
            "tage_ohne_bewegung": tage,
            "sta_anzahl":        sta_anzahl,
            "vorschlag":         vorschlag,
        })
    return result


def _berechne_vorschlag(tage, sta_anzahl):
    # type: (int, int) -> str
    """
    Gibt einen Aktions-Vorschlag für eine inaktive Akte zurück.
    """
    if tage < 14:
        return "keine"
    if sta_anzahl >= 2 and tage > 42:
        return "klage_pruefen"
    if tage > 21:
        return "sachstandsanfrage_dringend"
    return "sachstandsanfrage"


# ══════════════════════════════════════════════════════════════
#  GET /dashboard/onboarding-offen
# ══════════════════════════════════════════════════════════════

def _lade_onboarding_offen(conn):
    """
    Akten ohne Mandant-Beteiligter ODER ohne IBAN.
    Liefert max. 20 Einträge, neueste zuerst.
    """
    rows = conn.execute("""
        SELECT
            a.az                                        AS az,
            COALESCE(b.name || ' ' || COALESCE(b.vorname, ''), '') AS mandant,
            CASE WHEN b.id IS NULL THEN 'mandant' ELSE 'iban' END   AS fehlt
        FROM unfallakte a
        LEFT JOIN beteiligte b
               ON b.akte_id = a.az AND b.rolle = 'mandant'
        WHERE a.status != 'abgeschlossen'
          AND (b.id IS NULL
               OR b.iban IS NULL
               OR trim(b.iban) = '')
        ORDER BY a.erstellt_am DESC
        LIMIT 20
    """).fetchall()
    return [dict(r) for r in rows]


def _lade_nachrichten_neu(conn):
    """
    Letzte 20 E-Mails aus email_import_log, neueste zuerst.
    Nur Mails mit bekannter Akte.
    """
    rows = conn.execute("""
        SELECT
            e.id          AS log_id,
            a.az          AS az,
            e.absender,
            e.betreff,
            e.empfangen_am AS datum,
            e.konto        AS konto,
            'email'        AS kanal
        FROM email_import_log e
        JOIN unfallakte a ON a.az = e.akte_id
        ORDER BY e.empfangen_am DESC
        LIMIT 20
    """).fetchall()
    return [
        {**dict(r), "konto": r["konto"] or "unfall"}
        for r in rows
    ]


@dashboard_bp.route("/onboarding-offen", methods=["GET"])
@login_erforderlich
def onboarding_offen():
    """Akten ohne Mandant oder IBAN — für Action Board Onboarding-Spalte."""
    with get_connection() as conn:
        return _j({"eintraege": _lade_onboarding_offen(conn)})


@dashboard_bp.route("/nachrichten-neu", methods=["GET"])
@login_erforderlich
def nachrichten_neu():
    """Neueste E-Mails kanzleiweit — für Action Board Nachrichten-Spalte."""
    with get_connection() as conn:
        return _j({"eintraege": _lade_nachrichten_neu(conn)})


# ══════════════════════════════════════════════════════════════
#  GET /dashboard/ramicro-fristen
# ══════════════════════════════════════════════════════════════
#
#  RA-MICRO Tabellen (MS SQL Server, pymssql, read-only):
#    tblAktenWiedervorlagen  — Wiedervorlagen / harte Fristen
#      dtWiedervorlage        DATE    — Fälligkeitsdatum
#      sWiedervorlagegrund    NVARCHAR — Fristen-Art als Text
#      iWiedervorlageGrund    INT     — Fristen-Art als Code
#      GUIDAkte               GUID    — Join → tblAkten
#    tblAkten
#      sAktenNummer           NVARCHAR — Aktenzeichen (ohne SB-Kürzel)
#      sAktenSachbearbeiter   NVARCHAR — SB-Kürzel
#      sMandant               NVARCHAR — Mandanten-Kurzname
#      dtAblage               DATE    — NULL / '1899-12-30' = aktiv
#
#  Fristen-Codes (empirisch, s. wiedervorlage_service.py):
#    75 = Fristablauf, 5/6/11/16 = Stellungnahme, 58 = Verhandlungstermin
#    21 = Klage, 46 = Berufung, 31 = Mahnbescheid, 22 = Urteil

_RAMICRO_GRUENDE = {
    5: "Stellungnahme Gegner", 6: "Stellungnahme Mandant",
    9: "Entscheidung/Gericht", 11: "Stellungnahme Mandant",
    16: "Stellungnahme Gegner?", 21: "Klage", 22: "Urteil",
    23: "Vergleich", 31: "Mahnbescheid", 46: "Berufung",
    51: "Einspruch", 54: "Widerspruch", 55: "Beschwerde",
    58: "Verhandlungstermin", 60: "Anhörungstermin", 75: "Fristablauf",
}


def _lade_ramicro_fristen():
    # type: () -> list
    """
    Liest harte Fristen aus RA-MICRO (tblAktenWiedervorlagen) für die
    letzten 7 Tage bis heute. Gibt leere Liste zurück wenn RA-MICRO nicht erreichbar.
    """
    try:
        heute_dt = date.today()
        von_dt   = heute_dt - timedelta(days=7)
        # MS SQL Server erwartet Datumsstring im Format YYYY-MM-DD
        von_s    = von_dt.isoformat()
        heute_s  = heute_dt.isoformat()

        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 50
                    a.sAktenNummer              AS az_roh,
                    a.sAktenSachbearbeiter      AS az_sb,
                    a.sMandant                  AS mandant,
                    w.dtWiedervorlage           AS frist_datum,
                    w.sWiedervorlagegrund       AS frist_art_text,
                    w.iWiedervorlageGrund       AS frist_art_code
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE CAST(w.dtWiedervorlage AS DATE) BETWEEN %(von)s AND %(bis)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage DESC
            """, {"von": von_s, "bis": heute_s})
            rows = cur.fetchall()

        ergebnis = []
        for r in rows:
            az = _bilde_az(r)

            frist_art_text = (r.get("frist_art_text") or "").strip()
            frist_art_code = r.get("frist_art_code")
            if not frist_art_text and frist_art_code:
                try:
                    frist_art_text = _RAMICRO_GRUENDE.get(int(frist_art_code), f"Grund {frist_art_code}")
                except (ValueError, TypeError):
                    frist_art_text = ""

            frist_iso, tage = _parse_datum(r.get("frist_datum"), heute_dt)

            ergebnis.append({
                "az":         az,
                "mandant":    (r.get("mandant") or "").strip(),
                "frist_art":  frist_art_text,
                "frist_datum": frist_iso,
                "tage_bis":   tage,
            })
        return ergebnis

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("ramicro_fristen Fehler: %s", e)
        return []


@dashboard_bp.route("/ramicro-fristen", methods=["GET"])
@login_erforderlich
def ramicro_fristen():
    """Harte RA-MICRO Wiedervorlagen/Fristen für die nächsten 60 Tage."""
    return _j({"eintraege": _lade_ramicro_fristen()})


_TERMIN_CODES  = {9, 58, 60}
_FRIST_CODES   = {21, 22, 31, 46, 75}
_WV_AUSSCHLUSS = _TERMIN_CODES | _FRIST_CODES

# Nur für Termine-Kachel: spezifischere Labels als in _RAMICRO_GRUENDE für Codes 9, 58, 60
_TERMIN_LABELS = {
    9:  "Entscheidung/Gericht",
    58: "Verhandlungstermin",
    60: "Anhörungstermin",
}

_FRIST_LABELS = {
    21: "Klage",
    22: "Urteil",
    31: "Mahnbescheid",
    46: "Berufung",
    75: "Fristablauf",
}


def _bilde_az(row):
    # type: (dict) -> str
    az_roh = (row.get("az_roh") or "").strip()
    az_sb  = (row.get("az_sb")  or "").strip()
    if az_sb and not az_roh.upper().endswith(az_sb.upper()):
        return az_roh + az_sb
    return az_roh


def _parse_datum(raw, heute_dt):
    # type: (object, date) -> tuple
    """Gibt (iso_str, tage_bis) zurück."""
    try:
        if hasattr(raw, "date"):
            d = raw.date()
        elif isinstance(raw, str):
            d = date.fromisoformat(str(raw)[:10])
        else:
            d = raw
        return d.isoformat(), (d - heute_dt).days
    except Exception:
        return str(raw)[:10] if raw else "", 99


def _lade_termine_heute():
    # type: () -> list
    heute_dt   = date.today()
    morgen_dt  = heute_dt + timedelta(days=1)
    heute_s    = heute_dt.isoformat()
    morgen_s   = morgen_dt.isoformat()

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 30
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS termin_datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sBemerkung            AS bemerkung
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund IN (9, 58, 60)
                  AND CAST(w.dtWiedervorlage AS DATE)
                      BETWEEN %(heute)s AND %(morgen)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"heute": heute_s, "morgen": morgen_s})
            rows = cur.fetchall()

        ergebnis = []
        for r in rows:
            az = _bilde_az(r)
            datum_iso, tage = _parse_datum(r.get("termin_datum"), heute_dt)
            code = r.get("grund_code")
            termin_art = _TERMIN_LABELS.get(int(code), "Termin") if code else "Termin"

            bemerkung = (r.get("bemerkung") or "").strip()
            m = re.search(r"(\d{1,2}:\d{2})", bemerkung)
            uhrzeit = m.group(1) if m else None

            ergebnis.append({
                "az":              az,
                "mandant":         (r.get("mandant") or "").strip(),
                "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                "termin_art":      termin_art,
                "termin_datum":    datum_iso,
                "uhrzeit":         uhrzeit,
                "tage_bis":        tage,
            })
        return ergebnis

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("termine_heute Fehler: %s", e)
        return []


@dashboard_bp.route("/termine-heute", methods=["GET"])
@login_erforderlich
def termine_heute():
    """Heutige + morgige Gerichtstermine und Anhörungen aus RA-MICRO."""
    return _j({"eintraege": _lade_termine_heute()})


def _lade_ramicro_fristen_hart():
    # type: () -> list
    heute_dt    = date.today()
    plus14_dt   = heute_dt + timedelta(days=14)
    plus14_s    = plus14_dt.isoformat()
    minus365_dt = heute_dt - timedelta(days=365)
    minus365_s  = minus365_dt.isoformat()

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 50
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS frist_datum,
                    w.iWiedervorlageGrund   AS grund_code
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund IN (21, 22, 31, 46, 75)
                  AND CAST(w.dtWiedervorlage AS DATE) BETWEEN %(minus365)s AND %(plus14)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"plus14": plus14_s, "minus365": minus365_s})
            rows = cur.fetchall()

        ergebnis = []
        for r in rows:
            az = _bilde_az(r)
            frist_iso, tage = _parse_datum(r.get("frist_datum"), heute_dt)
            code = r.get("grund_code")
            frist_art = _FRIST_LABELS.get(int(code), f"Grund {code}") if code else "Frist"

            ergebnis.append({
                "az":              az,
                "mandant":         (r.get("mandant") or "").strip(),
                "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                "frist_art":       frist_art,
                "frist_datum":     frist_iso,
                "tage_bis":        tage,
            })
        return ergebnis

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("fristen Fehler: %s", e)
        return []


@dashboard_bp.route("/fristen", methods=["GET"])
@login_erforderlich
def fristen():
    """Fristen aus RA-MICRO: Codes 21,22,31,46,75 — überfällig bis +14 Tage."""
    return _j({"eintraege": _lade_ramicro_fristen_hart()})


def _lade_wiedervorlagen():
    # type: () -> dict
    heute_dt = date.today()
    heute_s  = heute_dt.isoformat()

    wv_eintraege       = []
    az_mit_aktiver_wv  = set()
    ramicro_erreichbar = True

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT TOP 50
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sWiedervorlagegrund   AS grund_text
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund NOT IN (9, 21, 22, 31, 46, 58, 60, 75)
                  AND CAST(w.dtWiedervorlage AS DATE) <= %(heute)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"heute": heute_s})
            for r in cur.fetchall():
                az = _bilde_az(r)
                datum_iso, tage = _parse_datum(r.get("datum"), heute_dt)
                grund = (r.get("grund_text") or "").strip()
                if not grund and r.get("grund_code"):
                    try:
                        grund = _RAMICRO_GRUENDE.get(int(r["grund_code"]), "Wiedervorlage")
                    except (ValueError, TypeError):
                        grund = "Wiedervorlage"
                wv_eintraege.append({
                    "az":              az,
                    "mandant":         (r.get("mandant") or "").strip(),
                    "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                    "grund":           grund,
                    "datum":           datum_iso,
                    "tage_bis":        tage,
                    "hat_wv":          True,
                })

            cur.execute("""
                SELECT DISTINCT
                    a.sAktenNummer + a.sAktenSachbearbeiter AS az_full
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE CAST(w.dtWiedervorlage AS DATE) >= %(heute)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
            """, {"heute": heute_s})
            az_mit_aktiver_wv = {
                (r.get("az_full") or "").strip()
                for r in cur.fetchall()
            }

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        ramicro_erreichbar = False
    except Exception as e:
        logger.warning("wiedervorlagen Fehler: %s", e)
        ramicro_erreichbar = False

    ohne_wv = []
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT az, kurzbezeichnung
                FROM unfallakte
                WHERE status NOT IN ('abgeschlossen')
                ORDER BY geaendert_am DESC
                LIMIT 100
            """).fetchall()
        for r in rows:
            az = r["az"]
            if not ramicro_erreichbar or az not in az_mit_aktiver_wv:
                ohne_wv.append({
                    "az":              az,
                    "mandant":         "",
                    "kurzbezeichnung": r["kurzbezeichnung"] or "",
                    "grund":           None,
                    "datum":           None,
                    "tage_bis":        None,
                    "hat_wv":          False,
                })
    except Exception as e:
        logger.warning("ohne_wv Fehler: %s", e)

    return {"wv": wv_eintraege, "ohne_wv": ohne_wv[:10]}


@dashboard_bp.route("/wiedervorlagen", methods=["GET"])
@login_erforderlich
def wiedervorlagen():
    """WV überfällig+heute aus RA-MICRO + lokale Akten ohne aktive WV."""
    return _j(_lade_wiedervorlagen())
