"""
Dashboard-Router – PRD-25b
===========================
Endpunkte für das Action-Dashboard.

Endpunkte:
  GET  /dashboard/action-items   Priorisierte Arbeitsliste für den Tag

Python 3.9 kompatibel.
"""

import logging
from datetime import date, timedelta
from flask import Blueprint, jsonify, g

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection

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
            a.az          AS az,
            e.absender,
            e.betreff,
            e.empfangen_am AS datum,
            'email'        AS kanal
        FROM email_import_log e
        JOIN unfallakte a ON a.az = e.akte_id
        ORDER BY e.empfangen_am DESC
        LIMIT 20
    """).fetchall()
    return [dict(r) for r in rows]


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
