r"""
Dashboard-Router – PRD-25b
===========================
Endpunkte für das Action-Dashboard.

Endpunkte:
  GET  /dashboard/action-items    Priorisierte Arbeitsliste für den Tag
  GET  /dashboard/termine-heute   Heutige + morgige Gerichtstermine aus RA-MICRO
  GET  /dashboard/fristen         Echte Fristen aus dem RA-MICRO-Kalenderbaum (Z:\RA\Kalender\GT), 14 Tage zurück bis 3 Werktage voraus
  GET  /dashboard/wiedervorlagen  WV überfällig+heute aus RA-MICRO + lokale Akten ohne aktive WV

Python 3.9 kompatibel.
"""

import logging
from datetime import date, timedelta
from flask import Blueprint, jsonify, g

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..ramicro.connector import (
    get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
)
from ..ramicro.sachbearbeiter import kalender_zu_kuerzel
from ..services.wiedervorlage_code_registry import (
    codes_fuer_art, loese_wv_grund, sql_codeliste
)
from ..services.fristen_gt import (
    FristenQuelleNichtErreichbar, lade_fristen, standard_fenster
)
from ..services.termine_ramicro import (
    SPALTEN as _TERMIN_SPALTEN, VON_UND_JOIN as _TERMIN_VON,
    parse_datum as _parse_datum, satz_zu_termin
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
    Zählt nicht zugeordnete E-Mails.
    """
    emails = conn.execute(
        """
        SELECT COUNT(*) AS n FROM email_import_log
        WHERE status = 'nicht_zugeordnet'
          AND (email_typ IS NULL OR email_typ != 'fragebogen')
        """
    ).fetchone()["n"]

    return {
        "emails_nicht_zugeordnet": emails,
        "gesamt":                  emails,
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


@dashboard_bp.route("/onboarding-offen", methods=["GET"])
@login_erforderlich
def onboarding_offen():
    """Akten ohne Mandant oder IBAN — für Action Board Onboarding-Spalte."""
    with get_connection() as conn:
        return _j({"eintraege": _lade_onboarding_offen(conn)})


def _bilde_az(row):
    # type: (dict) -> str
    az_roh = (row.get("az_roh") or "").strip()
    az_sb  = (row.get("az_sb")  or "").strip()
    if az_sb and not az_roh.upper().endswith(az_sb.upper()):
        return az_roh + az_sb
    return az_roh


def _lade_termine_heute():
    # type: () -> list
    heute_dt  = date.today()
    morgen_dt = heute_dt + timedelta(days=1)
    heute_s   = heute_dt.isoformat()
    morgen_s  = morgen_dt.isoformat()

    ergebnis  = []
    seen_keys = set()  # Dedup: (az, datum_iso)

    try:
        kalender_map = kalender_zu_kuerzel()

        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # Primärquelle: raKalender.dbo.Events (alle Kalendertermine).
            # Subject ist in den echten Daten fast immer leer -- der lesbare
            # Termintext steht in Summary, Gericht/Saal in Location, Telefon-
            # nummern und Zusätze in Notes.
            cur.execute("""
                SELECT TOP 100
""" + _TERMIN_SPALTEN + _TERMIN_VON + """
                WHERE CAST(e.StartDateTime AS DATE) BETWEEN %(heute)s AND %(morgen)s
                  AND e.IsDeleted = 0
                ORDER BY e.StartDateTime ASC
            """, {"heute": heute_s, "morgen": morgen_s})
            for r in cur.fetchall():
                # Ohne zugeordneten Kalender kein Termin: gepflegt sind nur die
                # Anwaltskalender, die Angestellten arbeiten mit Wiedervorlagen.
                termin = satz_zu_termin(r, kalender_map, heute_dt)
                if not termin:
                    continue

                key = ("kalender", r.get("EventUid"))
                if key not in seen_keys:
                    seen_keys.add(key)
                    ergebnis.append(termin)

            # Bis 2026-09-07 wurden hier zusaetzlich Wiedervorlagen mit
            # art: termin als Gerichtstermine ausgegeben. Die drei Codes (9,
            # 58, 60) heissen laut RA-MICRO-Maske Mas\TextWV.msk in Wahrheit
            # "SV-Gutachten?", "Unterlagen von Mdt. da?" und "Entscheidung
            # Gericht!?" -- keiner davon ist ein Termin. Termine stehen
            # vollstaendig in raKalender.dbo.Events.

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("termine_heute Fehler: %s", e)
        return []

    ergebnis.sort(key=lambda x: (x["tage_bis"], x["uhrzeit"] or "99:99"))
    return ergebnis


@dashboard_bp.route("/termine-heute", methods=["GET"])
@login_erforderlich
def termine_heute():
    """Heutige + morgige Gerichtstermine und Anhörungen aus RA-MICRO."""
    return _j({"eintraege": _lade_termine_heute()})


def _akten_sachbearbeiter(nummern):
    # type: (list) -> dict
    """Akten-SB je Aktennummer aus RA-MICRO.

    Der Sachbearbeiter im Fristsatz ist der, dem die Frist gehoert -- bei 5 von
    178 Fristen der letzten zwei Jahre ist das ein anderer als der Akten-SB.
    Fuer ein oeffnbares Aktenzeichen und den SB-Filter zaehlt der Akten-SB.

    Ist RA-MICRO nicht erreichbar, kommt ein leeres Verzeichnis zurueck und der
    Aufrufer faellt auf den Frist-SB zurueck. Die Fristen selbst stehen nicht in
    RA-MICRO, die Kachel bleibt also auch ohne SQL-Server benutzbar.
    """
    if not nummern:
        return {}
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            platzhalter = ", ".join("%%(a%d)s" % i for i in range(len(nummern)))
            cur.execute(
                "SELECT sAktenNummer AS nr, sAktenSachbearbeiter AS sb, "
                "       sMandant AS mandant "
                "FROM tblAkten WHERE sAktenNummer IN (%s)" % platzhalter,
                {("a%d" % i): n for i, n in enumerate(nummern)})
            return {
                (r.get("nr") or "").strip(): {
                    "sb":      (r.get("sb") or "").strip(),
                    "mandant": (r.get("mandant") or "").strip(),
                }
                for r in cur.fetchall()
            }
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return {}
    except Exception as e:
        logger.warning("Akten-SB fuer Fristen nicht ermittelbar: %s", e)
        return {}


def _lade_fristen_aus_dem_kalender():
    # type: () -> list
    """Unerledigte Fristen aus Z:\\RA\\Kalender\\GT.

    Wirft FristenQuelleNichtErreichbar, wenn der Kalenderbaum nicht lesbar ist.
    Das MUSS durchschlagen: eine leere Liste saehe aus wie "keine Fristen".
    """
    heute_dt = date.today()
    von, bis = standard_fenster(heute_dt)
    roh = lade_fristen(von, bis)

    akten = _akten_sachbearbeiter(sorted({e["aktennummer"] for e in roh}))

    ergebnis = []
    for e in roh:
        akte = akten.get(e["aktennummer"], {})
        sb = akte.get("sb") or e["sb"]
        ergebnis.append({
            "az":              e["aktennummer"] + sb,
            "mandant":         akte.get("mandant", ""),
            "kurzbezeichnung": e["kurzbezeichnung"],
            "frist_art":       e["frist_art"],
            "frist_datum":     e["frist_datum"],
            "tage_bis":        (date.fromisoformat(e["frist_datum"]) - heute_dt).days,
            "bemerkung":       e["bemerkung"],
            "sb":              sb,
            "ist_vorfrist":    e["ist_vorfrist"],
        })
    return ergebnis


@dashboard_bp.route("/fristen", methods=["GET"])
@login_erforderlich
def fristen():
    """Echte RA-MICRO-Fristen aus dem Kalenderbaum Z:\\RA\\Kalender\\GT.

    Zeitraum: 14 Tage Rueckschau auf Unerledigtes plus drei Werktage Vorschau
    (Wochenenden werden uebersprungen, liegen aber im Zeitraum).

    Bis 2026-09-07 kamen hier ausgewaehlte Wiedervorlagen heraus, die faelsch-
    lich als Fristen gefuehrt wurden. Ist die Quelle nicht lesbar -- in der
    Regel ein weggefallener E-Akte-Mount -- antwortet der Endpunkt mit 503,
    damit die Kachel den Ausfall zeigt statt "keine Fristen".
    """
    try:
        return _j({"eintraege": _lade_fristen_aus_dem_kalender()})
    except FristenQuelleNichtErreichbar as e:
        logger.warning("Fristenkalender nicht lesbar: %s", e)
        return _j({
            "eintraege": [],
            "fehler": "Fristenkalender nicht erreichbar (E-Akte-Mount)",
        }, 503)


def _lade_wiedervorlagen():
    # type: () -> dict
    heute_dt   = date.today()
    heute_s    = heute_dt.isoformat()
    minus90_s  = (heute_dt - timedelta(days=90)).isoformat()

    wv_eintraege       = []
    az_mit_aktiver_wv  = set()
    ramicro_erreichbar = True

    # Solange Frist- und Termin-Kachel keine eigenen Codes haben, gehoert jede
    # Wiedervorlage hierher -- der Ausschluss entfaellt dann ganz.
    ausgeschlossen = codes_fuer_art("frist", "termin")
    wo_ausschluss = (
        f"w.iWiedervorlageGrund NOT IN ({sql_codeliste('frist', 'termin')})"
        if ausgeschlossen else "1 = 1")

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            cur.execute(f"""
                SELECT TOP 500
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sWiedervorlagegrund   AS grund_text,
                    w.sBemerkung            AS bemerkung
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE {wo_ausschluss}
                  AND CAST(w.dtWiedervorlage AS DATE) BETWEEN %(minus90)s AND %(heute)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage DESC
            """, {"heute": heute_s, "minus90": minus90_s})
            for r in cur.fetchall():
                az = _bilde_az(r)
                datum_iso, tage = _parse_datum(r.get("datum"), heute_dt)
                wv_eintraege.append({
                    "az":              az,
                    "mandant":         (r.get("mandant") or "").strip(),
                    "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                    "grund":           loese_wv_grund(r.get("grund_text"),
                                                      r.get("grund_code")).text,
                    "datum":           datum_iso,
                    "tage_bis":        tage,
                    "bemerkung":       (r.get("bemerkung") or "").strip(),
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
                    "bemerkung":       "",
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
