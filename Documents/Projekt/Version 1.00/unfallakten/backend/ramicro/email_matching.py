"""
backend/ramicro/email_matching.py
===================================
RA-Micro Akte-Matching für den E-Mail-Import.

Sucht in RA-Micro nach:
  1. Aktenzeichen (tblAkten.sAktenNummer)
  2. KFZ-Kennzeichen (tblAkten, soweit Spalte vorhanden)
  3. Absender-E-Mail (tblAdressen.sEMail → tblAktenBeteiligte → tblAkten)

Gibt das kanonische Aktenzeichen zurück (ohne SB-Kürzel, z.B. "322/25")
damit SQLite on-demand die Akte anlegen kann (ramicroListe.onDemand).

Alle Funktionen fangen Verbindungsfehler und geben None zurück –
kein Absturz wenn RA-Micro nicht erreichbar ist.
"""

import logging
import re
from typing import Optional

from .connector import get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler

logger = logging.getLogger(__name__)


def suche_akte_in_ramicro(
    az_kandidaten:   list[str],
    kfz_kandidaten:  list[str],
    absender_email:  str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Sucht die passende Akte in RA-Micro.

    Reihenfolge:
      1. Aktenzeichen gegen tblAkten.sAktenNummer
      2. KFZ-Kennzeichen via _tbl0WDMDaten (varM-KZ)
      3. Absender-E-Mail gegen tblAdressen → tblAktenBeteiligte → tblAkten

    Returns:
        (az, erkannt, match_methode) oder (None, None, None)
        az = kanonisches AZ ohne SB-Kürzel, z.B. "322/25"
    """
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # ── 1. Aktenzeichen ───────────────────────────────────────────────
            for kandidat in az_kandidaten:
                az_basis = _az_basis(kandidat)
                az = _suche_az(cur, az_basis)
                if az:
                    logger.info("RA-Micro Match via AZ '%s' → %s", kandidat, az)
                    return az, kandidat, "aktenzeichen"

            # ── 2. KFZ-Kennzeichen via WDM (varM-KZ) ─────────────────────────
            for kfz in kfz_kandidaten:
                az = _suche_kfz_wdm(cur, kfz)
                if az:
                    logger.info("RA-Micro Match via KFZ (WDM) '%s' -> %s", kfz, az)
                    return az, kfz, "kfz_kennzeichen"

            # ── 3. Absender-E-Mail ────────────────────────────────────────────
            if absender_email:
                az = _suche_email(cur, absender_email)
                if az:
                    logger.info("RA-Micro Match via E-Mail '%s' → %s", absender_email, az)
                    return az, absender_email, "absender_email"

    except RaMicroNichtAktiv:
        logger.debug("RA-Micro nicht aktiv – übersprungen.")
    except RaMicroVerbindungsFehler as e:
        logger.warning("RA-Micro nicht erreichbar: %s", e)
    except Exception as e:
        logger.warning("RA-Micro Matching Fehler: %s", e)

    return None, None, None


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _az_basis(az: str) -> str:
    """Entfernt SB-Kürzel: '322/25AS' → '322/25'."""
    az = az.strip().upper()
    if "/" in az:
        az = re.sub(r"[A-Z]{2,3}$", "", az).strip()
    return az


def _suche_az(cur, az_basis: str) -> Optional[str]:
    """
    Sucht sAktenNummer in tblAkten.
    sAktenNummer ist in RA-Micro bereits ohne Kürzel gespeichert.
    """
    try:
        cur.execute(
            """
            SELECT TOP 1 sAktenNummer
            FROM tblAkten
            WHERE sAktenNummer = %s
              AND (dtAblage IS NULL OR CAST(dtAblage AS DATE) = '1899-12-30')
            """,
            (az_basis,)
        )
        row = cur.fetchone()
        if row:
            return row["sAktenNummer"]

        # Fallback: LIKE-Suche falls Format leicht abweicht
        cur.execute(
            """
            SELECT TOP 1 sAktenNummer
            FROM tblAkten
            WHERE sAktenNummer LIKE %s
              AND (dtAblage IS NULL OR CAST(dtAblage AS DATE) = '1899-12-30')
            """,
            (az_basis + "%",)
        )
        row = cur.fetchone()
        return row["sAktenNummer"] if row else None

    except Exception as e:
        logger.debug("_suche_az Fehler: %s", e)
        return None


def _kfz_spalte_ermitteln(cur) -> Optional[str]:
    """
    Ermittelt ob tblAkten eine KFZ-Kennzeichen-Spalte hat.
    RA-Micro verwendet je nach Version unterschiedliche Spaltennamen.
    Gibt den Spaltennamen zurück oder None.
    """
    kandidaten = ["sKfzKennzeichen", "sKFZKennzeichen", "sKfz", "sKFZ"]
    try:
        cur.execute("""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'tblAkten'
        """)
        vorhandene = {r["COLUMN_NAME"] for r in cur.fetchall()}
        for kandidat in kandidaten:
            if kandidat in vorhandene:
                logger.debug("KFZ-Spalte gefunden: %s", kandidat)
                return kandidat
    except Exception as e:
        logger.debug("_kfz_spalte_ermitteln Fehler: %s", e)
    return None


def _suche_kfz(cur, kfz: str, spalte: str) -> Optional[str]:
    """Sucht KFZ-Kennzeichen in tblAkten."""
    try:
        # KFZ normieren: Leerzeichen und Bindestriche entfernen für Vergleich
        kfz_norm = kfz.upper().replace(" ", "").replace("-", "")
        cur.execute(
            f"""
            SELECT TOP 1 sAktenNummer
            FROM tblAkten
            WHERE UPPER(REPLACE(REPLACE({spalte}, ' ', ''), '-', '')) = %s
              AND (dtAblage IS NULL OR CAST(dtAblage AS DATE) = '1899-12-30')
            """,
            (kfz_norm,)
        )
        row = cur.fetchone()
        return row["sAktenNummer"] if row else None
    except Exception as e:
        logger.debug("_suche_kfz Fehler: %s", e)
        return None



def _suche_kfz_wdm(cur, kfz: str) -> Optional[str]:
    """
    Sucht KFZ-Kennzeichen in _tbl0WDMDaten (Variable varM-KZ).
    Gibt sAktenNummer zurueck oder None.
    """
    try:
        kfz_norm = kfz.upper().replace(' ', '').replace('-', '')
        cur.execute(
            """
            SELECT TOP 1 w.AktenNr
            FROM _tbl0WDMDaten w
            INNER JOIN tblAkten a
                ON a.sAktenNummer = w.AktenNr
            WHERE w.sName = 'varM-KZ'
              AND UPPER(REPLACE(REPLACE(CAST(w.Value AS NVARCHAR(50)), ' ', ''), '-', '')) = %s
              AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
            """,
            (kfz_norm,)
        )
        row = cur.fetchone()
        return row['AktenNr'] if row else None
    except Exception as e:
        logger.debug('_suche_kfz_wdm Fehler: %s', e)
        return None

def _suche_email(cur, email: str) -> Optional[str]:
    """
    Sucht E-Mail-Adresse in tblAdressen → tblAktenBeteiligte → tblAkten.
    """
    try:
        cur.execute(
            """
            SELECT TOP 1 a.sAktenNummer
            FROM tblAdressen adr
            INNER JOIN tblAktenBeteiligte b ON b.GUIDAdresse = adr.GUIDAdresse
            INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
            WHERE LOWER(adr.sEMail) = %s
              AND b.bDeaktiviert = 0
              AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
            ORDER BY a.sAktenNummer DESC
            """,
            (email.lower(),)
        )
        row = cur.fetchone()
        return row["sAktenNummer"] if row else None
    except Exception as e:
        logger.debug("_suche_email Fehler: %s", e)
        return None


# ── Fragebogen-Signale: mehrere Kandidaten statt eines Treffers ──────────────

def _kfz_norm(kfz: str) -> str:
    """Wie die SQL-Normalisierung in _WDM_KZ_SQL: Leerzeichen/Bindestriche
    raus, Grossbuchstaben -- sonst findet "OF-MU 1234" nichts."""
    return (kfz or "").strip().upper().replace(" ", "").replace("-", "")


_AKTIV_FILTER = ("(a.dtAblage IS NULL "
                 "OR CAST(a.dtAblage AS DATE) = '1899-12-30')")

# Umkehrung von _AKTIV_FILTER: genau die abgelegten Akten. Rueckfall fuer
# Boegen, zu denen keine laufende Akte existiert (siehe
# suche_abgelegte_in_ramicro).
_ABGELEGT_FILTER = ("(a.dtAblage IS NOT NULL "
                    "AND CAST(a.dtAblage AS DATE) <> '1899-12-30')")

# Rollenrichtig wie in SQLite: die Mandantenadresse und der Nachname des
# Mandanten duerfen nur Auftraggeber-Zeilen treffen. iBeteiligtenArt = 1 ist
# der Mandant (Konvention des Projekts, vgl. ramicro/akten_erkennung.py:36;
# = 2 waere der Gegner, vgl. ramicro/wiedervorlage_service.py:192). Ohne
# diesen Filter treffen Versicherer-, Gutachter- und Behoerdenadressen mit.
_ART_MANDANT = 1

_WDM_KZ_SQL = """
    SELECT DISTINCT TOP 100 a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung,
                    a.dtAblage AS abgelegt_am
    FROM _tbl0WDMDaten w
    INNER JOIN tblAkten a ON a.sAktenNummer = w.AktenNr
    WHERE w.sName = %s
      AND UPPER(REPLACE(REPLACE(CAST(w.Value AS nvarchar(50)),' ',''),'-','')) = %s
      AND {aktiv}
"""

_WDM_TAG_SQL = """
    SELECT DISTINCT TOP 100 a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung,
                    a.dtAblage AS abgelegt_am
    FROM _tbl0WDMDaten w
    INNER JOIN tblAkten a ON a.sAktenNummer = w.AktenNr
    WHERE w.sName = 'varU-TAG'
      AND CAST(w.Value AS nvarchar(50)) LIKE %s
      AND {aktiv}
"""

_MAIL_SQL = ("""
    SELECT DISTINCT TOP 100 a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung,
                    a.dtAblage AS abgelegt_am
    FROM tblAdressen adr
    INNER JOIN tblAktenBeteiligte b ON b.GUIDAdresse = adr.GUIDAdresse
    INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
    WHERE LOWER(adr.sEMail) = %s
      AND b.iBeteiligtenArt = """ + str(_ART_MANDANT) + """
      AND b.bDeaktiviert = 0
      AND {aktiv}
""")

_NAME_SQL = ("""
    SELECT DISTINCT TOP 100 a.sAktenNummer AS az,
                    a.sAktenKurzBezeichnung AS bezeichnung,
                    a.dtAblage AS abgelegt_am
    FROM tblAdressen adr
    INNER JOIN tblAktenBeteiligte b ON b.GUIDAdresse = adr.GUIDAdresse
    INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
    WHERE adr.sNachname = %s
      AND b.iBeteiligtenArt = """ + str(_ART_MANDANT) + """
      AND b.bDeaktiviert = 0
      AND {aktiv}
""")


def _suche_bogen_abfragen(
        merkmale: dict, ablage_filter: str
        ) -> list[tuple[str, str, str, Optional[str], Optional[str]]]:
    """Gemeinsamer Rumpf von ``suche_kandidaten_in_ramicro`` und
    ``suche_abgelegte_in_ramicro`` -- baut dieselben fuenf Abfragen und
    wendet nur den uebergebenen Ablage-Filter an, damit es keine zweite
    Kopie der Abfrageliste gibt.

    Returns:
        Liste von ``(akte_az, methode, treffer, kurzbezeichnung,
        abgelegt_am)``.
    """
    from ..utils.datum import iso_zu_ramicro

    abfragen = []
    mail = (merkmale.get("mandant_email") or "").strip().lower()
    if mail:
        abfragen.append((_MAIL_SQL, (mail,), "mandanten_mail", mail))
    kfz_m = _kfz_norm(merkmale.get("kfz_mandant") or "")
    if kfz_m:
        abfragen.append((_WDM_KZ_SQL, ("varM-KZ", kfz_m), "kfz_mandant", kfz_m))
    kfz_g = _kfz_norm(merkmale.get("kfz_gegner") or "")
    if kfz_g:
        abfragen.append((_WDM_KZ_SQL, ("varG-KZ", kfz_g), "kfz_gegner", kfz_g))
    tag = (merkmale.get("unfalltag") or "").strip()
    if tag:
        abfragen.append((_WDM_TAG_SQL, (f"{iso_zu_ramicro(tag)}%",),
                          "unfalltag", tag))
    name = (merkmale.get("nachname") or "").strip()
    if name:
        abfragen.append((_NAME_SQL, (name,), "nachname", name))

    if not abfragen:
        return []

    ergebnis: list[tuple[str, str, str, Optional[str], Optional[str]]] = []
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            for sql, params, methode, treffer in abfragen:
                try:
                    cur.execute(sql.format(aktiv=ablage_filter), params)
                    for row in cur.fetchall() or ():
                        az = row["az"] if row else None
                        if az:
                            ergebnis.append((_az_basis(az), methode, treffer,
                                              row.get("bezeichnung"),
                                              row.get("abgelegt_am")))
                except Exception as e:
                    logger.warning("RA-Micro-Teilabfrage %s fehlgeschlagen: %s",
                                    methode, e)
    except RaMicroNichtAktiv:
        logger.debug("RA-Micro nicht aktiv -- Bogen-Suche uebersprungen.")
    except RaMicroVerbindungsFehler as e:
        logger.warning("RA-Micro nicht erreichbar: %s", e)
    except Exception as e:
        logger.warning("RA-Micro Bogen-Suche Fehler: %s", e)

    return ergebnis


def suche_kandidaten_in_ramicro(
        merkmale: dict) -> list[tuple[str, str, str, Optional[str]]]:
    """Sucht Akten-Kandidaten zu den Signalen eines Unfallbogens.

    Anders als ``suche_akte_in_ramicro`` bricht diese Funktion nicht beim
    ersten Treffer ab -- die Bewertung geschieht im Aufrufer. Durchsucht nur
    laufende Akten (siehe ``suche_abgelegte_in_ramicro`` fuer den Rueckfall).

    Args:
        merkmale: Signal-Dict mit den optionalen Schluesseln
            ``mandant_email``, ``kfz_mandant``, ``kfz_gegner``,
            ``unfalltag`` (ISO), ``nachname``.

    Returns:
        Liste von ``(akte_az, methode, treffer, kurzbezeichnung)``. Leer bei
        fehlenden Merkmalen oder wenn RA-MICRO nicht erreichbar ist.

    Nur lesend.
    """
    return [(az, methode, treffer, bezeichnung)
            for az, methode, treffer, bezeichnung, _abgelegt_am in
            _suche_bogen_abfragen(merkmale, _AKTIV_FILTER)]


def suche_abgelegte_in_ramicro(
        merkmale: dict) -> list[tuple[str, str, str, Optional[str],
                                       Optional[str]]]:
    """Wie ``suche_kandidaten_in_ramicro``, aber ausschliesslich abgelegte
    Akten. Rueckfall fuer den Fall, dass zu einem Bogen keine laufende Akte
    existiert -- ohne diesen Weg wuerde ein abgeschlossener Fall als
    Neumandat erscheinen.

    Returns:
        Liste von ``(akte_az, methode, treffer, kurzbezeichnung,
        abgelegt_am)``.

    Nur lesend.
    """
    return _suche_bogen_abfragen(merkmale, _ABGELEGT_FILTER)
