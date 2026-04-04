"""
STA-Service – PRD-25d
=====================
Analysiert die Regulierungschronologie einer Akte und generiert
stufenangepassten Sachstandsanfrage-Text.

Stufenlogik:
  1 – Erinnerung       (14–21 Tage, erste STA)      Frist: konfigurierbar (Default 14 Tage)
  2 – Mahnung          (>21 Tage oder ≥1 STA)        Frist: konfigurierbar (Default  7 Tage)
  3 – Klage-Ankündigung (≥2 STAs + >42 Tage)         Frist: konfigurierbar (Default  5 Tage)

Texte und Fristen sind über die konfiguration-Tabelle anpassbar.
Platzhalter in den Templates: {Schreiben}, {Mandant}, {Frist}
"""

import logging
from datetime import date, timedelta

from ..db.database import get_connection

logger = logging.getLogger(__name__)

# ── Defaults ──────────────────────────────────────────────────────────────────

_FRIST_DEFAULTS = {
    "sta_stufe1_tage": 14,
    "sta_stufe2_tage":  7,
    "sta_stufe3_tage":  5,
}

_TEXT_DEFAULTS = {
    "sta_stufe1_text": (
        "in vorbezeichneter Angelegenheit erlauben wir uns, auf {Schreiben} hinzuweisen, "
        "mit dem wir die Schadensersatzansprüche für {Mandant} geltend gemacht haben.\n\n"
        "Eine Rückmeldung Ihrerseits ist bislang ausgeblieben. Wir bitten Sie, "
        "die Angelegenheit zu bearbeiten und uns bis zum {Frist} eine Stellungnahme "
        "zukommen zu lassen.\n\n"
        "Für Rückfragen stehen wir Ihnen gerne zur Verfügung."
    ),
    "sta_stufe2_text": (
        "in vorbezeichneter Angelegenheit haben wir Ihnen mit {Schreiben} "
        "die Schadensersatzansprüche für {Mandant} angezeigt. "
        "Trotz Ablauf der gesetzten Frist ist eine Reaktion Ihrerseits bisher ausgeblieben.\n\n"
        "Wir fordern Sie auf, bis spätestens {Frist} eine verbindliche Stellungnahme abzugeben "
        "bzw. die ausstehenden Leistungen zu erbringen.\n\n"
        "Für den Fall, dass eine Reaktion bis zu diesem Datum ausbleibt, behalten wir uns "
        "vor, ohne weitere Ankündigung gerichtliche Schritte einzuleiten. Die anfallenden "
        "Verfahrenskosten gehen in diesem Fall zu Ihren Lasten."
    ),
    "sta_stufe3_text": (
        "in vorbezeichneter Angelegenheit haben wir uns mehrfach schriftlich an Sie gewandt, "
        "zuletzt mit {Schreiben}. Eine Reaktion Ihrerseits ist in keinem Fall erfolgt.\n\n"
        "Wir kündigen hiermit an, ohne weiteres Zuwarten gerichtliche Schritte einzuleiten. "
        "Sollten wir bis zum {Frist} keine verbindliche Regulierungszusage erhalten, "
        "werden wir Klage erheben.\n\n"
        "Die anfallenden Verfahrenskosten – Gerichtskosten sowie weitere anwaltliche Gebühren "
        "– werden wir vollumfänglich geltend machen."
    ),
}

TYP_LABEL = {
    "forderungsschreiben": "Forderungsschreiben",
    "sachstandsanfrage":   "Sachstandsanfrage",
    "stellungnahme":       "Stellungnahme",
}


# ── Öffentliche API ────────────────────────────────────────────────────────────

def analysiere_regulierung(az):
    # type: (str) -> dict
    """
    Analysiert die Regulierungschronologie einer Akte.

    Returns dict:
      az, letztes_schreiben, tage_ohne_antwort, sta_anzahl,
      empfohlene_stufe, versicherer_name, schaden_nr, mandant_name
    """
    with get_connection() as conn:
        # Letztes unbeantwortetes Schreiben: offenes antwort_2w-Todo → dok
        unbeantwortet = conn.execute(
            """
            SELECT t.dok_id, d.typ, d.hochgeladen_am
            FROM todos t
            JOIN dokumente d ON d.id = t.dok_id
            WHERE t.akte_az      = ?
              AND t.frist_typ    = 'antwort_2w'
              AND t.erledigt     = 0
              AND t.dok_id IS NOT NULL
            ORDER BY d.hochgeladen_am DESC
            LIMIT 1
            """,
            (az,)
        ).fetchone()

        # Fallback: neuestes ausgehendes Dokument ohne offenes Todo
        if not unbeantwortet:
            unbeantwortet = conn.execute(
                """
                SELECT id AS dok_id, typ, hochgeladen_am
                FROM dokumente
                WHERE akte_id = ?
                  AND typ IN ('forderungsschreiben', 'sachstandsanfrage', 'stellungnahme')
                ORDER BY hochgeladen_am DESC
                LIMIT 1
                """,
                (az,)
            ).fetchone()

        sta_anzahl = conn.execute(
            "SELECT COUNT(*) FROM dokumente WHERE akte_id = ? AND typ = 'sachstandsanfrage'",
            (az,)
        ).fetchone()[0]

        gegner = conn.execute(
            "SELECT versicherung, schaden_nr FROM beteiligte WHERE akte_id = ? AND rolle = 'gegner' LIMIT 1",
            (az,)
        ).fetchone()

        mandant = conn.execute(
            "SELECT name, vorname FROM beteiligte WHERE akte_id = ? AND rolle = 'mandant' LIMIT 1",
            (az,)
        ).fetchone()

    letztes_schreiben = None
    tage_ohne_antwort = 0

    if unbeantwortet:
        datum_str = (unbeantwortet["hochgeladen_am"] or "")[:10]
        try:
            datum = date.fromisoformat(datum_str)
            tage_ohne_antwort = (date.today() - datum).days
            datum_fmt = datum.strftime("%d.%m.%Y")
        except (ValueError, TypeError):
            datum_fmt = datum_str
            tage_ohne_antwort = 0

        typ = unbeantwortet["typ"]
        letztes_schreiben = {
            "typ":       typ,
            "typ_label": TYP_LABEL.get(typ, typ),
            "datum":     datum_str,
            "datum_fmt": datum_fmt,
            "dok_id":    unbeantwortet["dok_id"],
        }

    mandant_name = None
    if mandant:
        teile = [mandant["vorname"] or "", mandant["name"] or ""]
        mandant_name = " ".join(t for t in teile if t).strip() or None

    return {
        "az":                az,
        "letztes_schreiben": letztes_schreiben,
        "tage_ohne_antwort": tage_ohne_antwort,
        "sta_anzahl":        sta_anzahl,
        "empfohlene_stufe":  _empfohlene_stufe(tage_ohne_antwort, sta_anzahl),
        "versicherer_name":  (gegner["versicherung"] if gegner else None),
        "schaden_nr":        (gegner["schaden_nr"]   if gegner else None),
        "mandant_name":      mandant_name,
    }


def generiere_sta_text(stufe, kontext):
    # type: (int, dict) -> str
    """
    Generiert den Brieftext in der angegebenen Eskalationsstufe (1–3).

    Lädt das Template aus der konfiguration-Tabelle (falls vorhanden),
    fällt sonst auf die eingebauten Defaults zurück.
    Ersetzt Platzhalter: {Schreiben}, {Mandant}, {Frist}.
    """
    stufe = max(1, min(3, int(stufe)))

    ls      = kontext.get("letztes_schreiben")
    mandant = kontext.get("mandant_name") or "unsere Mandantschaft"
    frist   = (date.today() + timedelta(days=_frist_tage(stufe))).strftime("%d.%m.%Y")

    schreiben_ref = (
        "unser {} vom {}".format(ls["typ_label"], ls["datum_fmt"])
        if ls else "unser Schreiben"
    )

    template = _lese_text_template(stufe)
    return (
        template
        .replace("{Schreiben}", schreiben_ref)
        .replace("{Mandant}",   mandant)
        .replace("{Frist}",     frist)
    )


# ── Interne Hilfsfunktionen ───────────────────────────────────────────────────

def _frist_tage(stufe):
    # type: (int) -> int
    """Liest die konfigurierte Fristdauer für eine STA-Stufe aus der DB."""
    schluessel = "sta_stufe{}_tage".format(stufe)
    default    = _FRIST_DEFAULTS.get(schluessel, 7)
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT wert FROM konfiguration WHERE schluessel = ?", (schluessel,)
            ).fetchone()
        if row:
            return max(1, int(row["wert"]))
    except Exception:
        pass
    return default


def _lese_text_template(stufe):
    # type: (int) -> str
    """Liest das konfigurierte Texttemplate für eine STA-Stufe aus der DB."""
    schluessel = "sta_stufe{}_text".format(stufe)
    default    = _TEXT_DEFAULTS.get(schluessel, "")
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT wert FROM konfiguration WHERE schluessel = ?", (schluessel,)
            ).fetchone()
        if row and row["wert"].strip():
            return row["wert"]
    except Exception:
        pass
    return default


def _empfohlene_stufe(tage, sta_anzahl):
    # type: (int, int) -> int
    if sta_anzahl >= 2 and tage > 42:
        return 3
    if tage > 21 or sta_anzahl >= 1:
        return 2
    return 1
