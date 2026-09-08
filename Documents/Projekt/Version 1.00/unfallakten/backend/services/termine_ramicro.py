r"""
backend/services/termine_ramicro.py
===================================
Termine aus raKalender.dbo.Events -- die eine Stelle, die das Kalenderschema
kennt.

Dashboard-Kachel und Aktenansicht lesen dieselben Saetze, nur mit anderem
Zuschnitt: das Dashboard heute + morgen und ausschliesslich die gepflegten
Anwaltskalender, die Akte alles zu einer Aktennummer. Bis 2026-09-07 stand die
Satzaufbereitung allein in dashboard_routes; eine zweite Kopie fuer die Akte
haette zwei Termin-Wahrheiten ergeben, die auseinanderlaufen.

RA-MICRO fuellt ``Subject`` fast nie. Der lesbare Termintext steht in
``Summary``, Gericht/Saal in ``Location``, Telefonnummern in ``Notes``.

Python 3.9 kompatibel.
"""

from datetime import date

from ..ramicro.connector import get_ramicro_connection
from ..ramicro.sachbearbeiter import kalender_zu_kuerzel

# Beide Abfragen brauchen genau diese Felder -- getrennt gepflegt waere das die
# naechste Fehlerquelle.
SPALTEN = """
                    e.EventUid,
                    e.StartDateTime,
                    e.Subject,
                    e.Summary,
                    e.Location,
                    e.Notes,
                    e.Aktennummer,
                    e.Aktenkurzbezeichnung,
                    e.IsGerichtstermin,
                    e.GerichtName,
                    c.CalendarName
"""

VON_UND_JOIN = """
                FROM raKalender.dbo.Events e
                LEFT JOIN raKalender.dbo.Calendars c
                    ON c.CalendarId = e.CalendarId AND c.Deleted = 0
"""


def parse_datum(raw, heute_dt):
    # type: (object, date) -> tuple
    """Gibt (iso_str, tage_bis) zurueck."""
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


def satz_zu_termin(zeile, kalender_map, heute_dt, kalender_pflicht=True):
    # type: (dict, dict, date, bool) -> dict
    """Eine Events-Zeile wird ein Termin -- oder None.

    ``kalender_pflicht`` verwirft Termine aus Kalendern ohne Sachbearbeiter.
    Im Dashboard ist das richtig: gepflegt sind nur die Anwaltskalender, die
    Angestellten arbeiten mit Wiedervorlagen. In der Akte wuerde dieselbe Regel
    Termine verschlucken, deshalb dort False.
    """
    cal_name = (zeile.get("CalendarName") or "").strip()
    sb = kalender_map.get(cal_name)
    if not sb:
        if kalender_pflicht:
            return None
        sb = ""

    datum_raw = zeile.get("StartDateTime")
    datum_iso, tage = parse_datum(datum_raw, heute_dt)

    uhrzeit = None
    if datum_raw is not None and hasattr(datum_raw, "strftime"):
        uhrzeit = datum_raw.strftime("%H:%M")

    ak_nr = (zeile.get("Aktennummer") or "").strip()
    az = ak_nr + sb if ak_nr else ""

    kurz    = (zeile.get("Aktenkurzbezeichnung") or "").strip()
    summary = (zeile.get("Summary") or "").strip()
    if ak_nr and summary.startswith(ak_nr):
        summary = summary[len(ak_nr):].strip()

    is_gt   = bool(zeile.get("IsGerichtstermin"))
    subject = (zeile.get("Subject") or "").strip()
    if is_gt:
        termin_art = subject or "Verhandlungstermin"
    elif ak_nr or kurz:
        termin_art = subject or "Mandantentermin"
    else:
        # Ohne Aktenbezug waere "Mandantentermin" geraten
        # (Lehrgang, Urlaub, Behoerdengang).
        termin_art = subject

    notiz = (zeile.get("Notes") or "").strip()

    return {
        "az":                 az,
        "mandant":            "",
        "kurzbezeichnung":    kurz,
        "betreff":            kurz or summary,
        "termin_art":         termin_art,
        "termin_datum":       datum_iso,
        "uhrzeit":            uhrzeit,
        "tage_bis":           tage,
        "sb":                 sb,
        "ist_gerichtstermin": is_gt,
        "ort":                ((zeile.get("Location") or "").strip()
                               or (zeile.get("GerichtName") or "").strip()),
        "bemerkung":          " · ".join(
            z.strip() for z in notiz.splitlines() if z.strip()),
    }


def termine_der_akte(nummer):
    # type: (str) -> list
    """Alle Termine einer Aktennummer ("322/26"), unsortiert.

    Ohne Datumsfenster: in der Akte zaehlt Vollstaendigkeit: der vergangene
    Gerichtstermin gehoert zur Geschichte des Falls. Ein RA-MICRO-Ausfall wird
    hier nicht abgefangen -- eine leere Liste waere die gefaehrlichste Antwort.
    """
    heute_dt     = date.today()
    kalender_map = kalender_zu_kuerzel()

    ergebnis = []
    gesehen  = set()

    with get_ramicro_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
                SELECT TOP 200
""" + SPALTEN + VON_UND_JOIN + """
                WHERE LTRIM(RTRIM(e.Aktennummer)) = %(nummer)s
                  AND e.IsDeleted = 0
                ORDER BY e.StartDateTime ASC
        """, {"nummer": nummer})

        for r in cur.fetchall():
            uid = r.get("EventUid")
            if uid in gesehen:
                continue
            gesehen.add(uid)
            termin = satz_zu_termin(r, kalender_map, heute_dt,
                                    kalender_pflicht=False)
            if termin:
                ergebnis.append(termin)

    return ergebnis
