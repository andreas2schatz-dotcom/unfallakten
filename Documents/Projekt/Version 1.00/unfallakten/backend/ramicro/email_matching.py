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
