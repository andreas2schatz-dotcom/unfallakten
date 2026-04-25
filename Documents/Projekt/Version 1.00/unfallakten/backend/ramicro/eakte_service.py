"""
E-Akte Service – Read-Only Zugriff auf RA-Micro DMS
=====================================================
⛔ ABSOLUTE REGEL: Kein Schreibzugriff auf raEloakte!
   Nur SELECT-Statements. Alle eigenen Daten in lokaler SQLite.

Liest Dokument-Metadaten aus tblElo_AktenArchiv.
Physischer Dateizugriff erst in Phase 2 (Volume-Mount).

Python 3.9 kompatibel.
"""

import os
import re
import logging
from typing import Optional, List, Dict, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ── Konfiguration ─────────────────────────────────────────────────────────────

EAKTE_DATABASE = os.environ.get("EAKTE_DATABASE", "raEloakte")
EAKTE_BASE_PATH = os.environ.get("EAKTE_BASE_PATH", "")  # Phase 2: Volume-Mount


# ── Verbindung (nutzt bestehenden RA-Micro Connector, andere DB) ──────────────

@contextmanager
def _get_eakte_connection():
    """
    Verbindung zur raEloakte-Datenbank.
    ⛔ NUR SELECT – kein INSERT/UPDATE/DELETE.
    Nutzt dieselben Credentials wie RA-Micro, aber andere Datenbank.
    """
    cfg_host = os.environ.get("RAMICRO_HOST", "")
    cfg_port = int(os.environ.get("RAMICRO_PORT", "1433"))
    cfg_user = os.environ.get("RAMICRO_USER", "")
    cfg_pass = os.environ.get("RAMICRO_PASSWORD", "")
    cfg_timeout = int(os.environ.get("RAMICRO_TIMEOUT", "10"))
    cfg_aktiv = os.environ.get("RAMICRO_AKTIV", "false").lower() == "true"

    if not cfg_aktiv:
        raise RuntimeError("RA-Micro nicht aktiv (RAMICRO_AKTIV != true)")

    if not cfg_host or not cfg_user:
        raise RuntimeError("RA-Micro nicht konfiguriert (RAMICRO_HOST/USER)")

    try:
        import pymssql
    except ImportError:
        raise RuntimeError("pymssql nicht installiert")

    server_str = "%s:%d" % (cfg_host, cfg_port)
    try:
        conn = pymssql.connect(
            server=server_str,
            database=EAKTE_DATABASE,
            user=cfg_user,
            password=cfg_pass,
            login_timeout=cfg_timeout,
            as_dict=True,
            charset="UTF-8",
            tds_version="7.0",
        )
        logger.debug("E-Akte Verbindung: %s/%s", cfg_host, EAKTE_DATABASE)
        try:
            yield conn
        finally:
            conn.close()
    except Exception as e:
        logger.error("E-Akte Verbindung fehlgeschlagen: %s", e)
        raise RuntimeError("E-Akte Verbindung fehlgeschlagen: %s" % e)


# ── AZ-Parsing ────────────────────────────────────────────────────────────────

def parse_az(az):
    # type: (str) -> Tuple[int, int]
    """
    '1/16' → (1, 16)
    '276/26' → (276, 26)
    """
    parts = az.strip().split("/")
    if len(parts) != 2:
        raise ValueError("Ungültiges Aktenzeichen: %s" % az)
    return int(parts[0]), int(parts[1])


# ── E-Akte Dokumente abfragen ────────────────────────────────────────────────

def hole_eakte_dokumente(az, nur_pdf=True, limit=0):
    # type: (str, bool, int) -> List[Dict]
    """
    Holt Dokument-Metadaten aus tblElo_AktenArchiv.
    ⛔ Nur SELECT – kein Schreibzugriff!

    Args:
        az:       Aktenzeichen (z.B. "1/16")
        nur_pdf:  True = nur PDFs, False = auch E-Mails/andere
        limit:    Maximale Anzahl Ergebnisse (0 = kein Limit, Standard)

    Returns:
        Liste von Dicts mit Dokument-Metadaten
    """
    akten_nr, jahrgang = parse_az(az)

    top_klausel = ("TOP %d " % limit) if limit > 0 else ""
    sql = """
        SELECT %s
            Nr, AktenNr, Jahrgang,
            Dateiname, OrgDatei,
            Empfaenger, Bemerkung,
            Sachbearb, Rubrik, Schlagwort,
            Version, EinfDatum
        FROM tblElo_AktenArchiv
        WHERE AktenNr = %%s
          AND Jahrgang = %%s
          AND (UAkte = 0 OR UAkte IS NULL)
    """ % top_klausel

    if nur_pdf:
        sql += " AND (Dateiname LIKE '%.pdf')"
    else:
        # PDFs + E-Mails (MSG-Konvertierungen)
        sql += " AND (Dateiname LIKE '%.pdf' OR Dateiname LIKE '%.msg')"

    sql += " ORDER BY Version DESC"

    try:
        with _get_eakte_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (akten_nr, jahrgang))
            rows = cur.fetchall()
    except Exception as e:
        logger.error("E-Akte Abfrage fehlgeschlagen fuer %s: %s", az, e)
        return []

    ergebnis = []
    for row in rows:
        dateiname_raw = row.get("Dateiname") or ""
        # Kurzen Anzeigenamen extrahieren (letzter Teil des Pfads)
        anzeigename = dateiname_raw.split("\\")[-1] if dateiname_raw else ""
        # Dateityp bestimmen
        ext = anzeigename.rsplit(".", 1)[-1].lower() if "." in anzeigename else ""

        # Absender-Domain extrahieren (fuer spaetere Klassifikation)
        empfaenger = row.get("Empfaenger") or ""
        domain = _extrahiere_domain(empfaenger)

        ergebnis.append({
            "nr": row["Nr"],
            "dateiname": dateiname_raw,
            "anzeigename": anzeigename,
            "orgdatei": row.get("OrgDatei") or "",
            "dateityp": ext,
            "empfaenger": empfaenger,
            "absender_domain": domain,
            "bemerkung": row.get("Bemerkung") or "",
            "sachbearbeiter": row.get("Sachbearb") or "",
            "rubrik": row.get("Rubrik") or "",
            "schlagwort": row.get("Schlagwort") or "",
            "version": row["Version"].isoformat() if row.get("Version") else None,
            "einf_datum": row["EinfDatum"].isoformat() if row.get("EinfDatum") else None,
        })

    logger.info("E-Akte %s: %d Dokumente gefunden (nur_pdf=%s)", az, len(ergebnis), nur_pdf)
    return ergebnis


def hole_eakte_dokument(az, nr):
    # type: (str, int) -> Optional[Dict]
    """
    Holt ein einzelnes E-Akte-Dokument anhand der Nr.
    ⛔ Nur SELECT!
    """
    akten_nr, jahrgang = parse_az(az)

    sql = """
        SELECT Nr, AktenNr, Jahrgang,
               Dateiname, OrgDatei,
               Empfaenger, Bemerkung,
               Sachbearb, Rubrik, Schlagwort,
               Version, EinfDatum
        FROM tblElo_AktenArchiv
        WHERE Nr = %s
          AND AktenNr = %s
          AND Jahrgang = %s
    """

    try:
        with _get_eakte_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (nr, akten_nr, jahrgang))
            row = cur.fetchone()
    except Exception as e:
        logger.error("E-Akte Einzeldokument %d fehlgeschlagen: %s", nr, e)
        return None

    if not row:
        return None

    dateiname_raw = row.get("Dateiname") or ""
    anzeigename = dateiname_raw.split("\\")[-1] if dateiname_raw else ""
    ext = anzeigename.rsplit(".", 1)[-1].lower() if "." in anzeigename else ""

    return {
        "nr": row["Nr"],
        "dateiname": dateiname_raw,
        "anzeigename": anzeigename,
        "orgdatei": row.get("OrgDatei") or "",
        "dateityp": ext,
        "empfaenger": row.get("Empfaenger") or "",
        "absender_domain": _extrahiere_domain(row.get("Empfaenger") or ""),
        "bemerkung": row.get("Bemerkung") or "",
        "sachbearbeiter": row.get("Sachbearb") or "",
        "rubrik": row.get("Rubrik") or "",
        "schlagwort": row.get("Schlagwort") or "",
        "version": row["Version"].isoformat() if row.get("Version") else None,
        "einf_datum": row["EinfDatum"].isoformat() if row.get("EinfDatum") else None,
    }


def eakte_anzahl(az):
    # type: (str) -> int
    """Gibt die Anzahl der E-Akte-Dokumente einer Akte zurück."""
    akten_nr, jahrgang = parse_az(az)
    try:
        with _get_eakte_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) AS n FROM tblElo_AktenArchiv "
                "WHERE AktenNr = %s AND Jahrgang = %s AND (UAkte = 0 OR UAkte IS NULL)",
                (akten_nr, jahrgang),
            )
            row = cur.fetchone()
            return row["n"] if row else 0
    except Exception:
        return 0


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _extrahiere_domain(empfaenger):
    # type: (str) -> Optional[str]
    """
    Extrahiert die E-Mail-Domain aus dem Empfaenger-Feld.
    'Peter Koch <peter.koch@anwalt-offenbach.de>' → 'anwalt-offenbach.de'
    '"HUK-COBURG" <schaden@huk.de>' → 'huk.de'
    """
    if not empfaenger:
        return None
    # E-Mail in spitzen Klammern
    m = re.search(r"<([^>]+@([^>]+))>", empfaenger)
    if m:
        return m.group(2).lower().strip()
    # Nackte E-Mail-Adresse
    m = re.search(r"[\w.+-]+@([\w.-]+)", empfaenger)
    if m:
        return m.group(1).lower().strip()
    return None


def baue_dateipfad(dateiname):
    # type: (str) -> Optional[str]
    """
    Baut den physischen Dateipfad aus EAKTE_BASE_PATH + relativem Pfad.
    Phase 2: Erst nutzbar wenn Volume-Mount eingerichtet ist.

    'ar\\26\\03\\11\\111174400001-00-16~~PK~04.pdf'
    → '/mnt/eakte/ar/26/03/11/111174400001-00-16~~PK~04.pdf'
    """
    if not EAKTE_BASE_PATH:
        return None
    if not dateiname:
        return None
    # Backslashes zu Forward-Slashes (Windows → Linux)
    pfad_teil = dateiname.replace("\\", "/")
    return os.path.join(EAKTE_BASE_PATH, pfad_teil)
