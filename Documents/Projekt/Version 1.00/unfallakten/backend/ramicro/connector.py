"""
Modul 8 – RA-Micro Datenbankverbindung
========================================
Stellt eine Nur-Lese-Verbindung zum RA-Micro SQL Server 2014 bereit.
Verbindungsparameter kommen ausschließlich aus Umgebungsvariablen.

Umgebungsvariablen (alle in .env eintragen):
    RAMICRO_HOST        IP-Adresse des Kanzlei-Servers (z.B. 192.168.1.x)
    RAMICRO_PORT        Port des SQL Servers (Standard: 1433)
    RAMICRO_DATABASE    Datenbankname (Standard: RAMICRO)
    RAMICRO_USER        SQL-Benutzername (Read-Only-Konto)
    RAMICRO_PASSWORD    Passwort des SQL-Benutzers
    RAMICRO_TIMEOUT     Verbindungstimeout in Sekunden (Standard: 10)
    RAMICRO_AKTIV       Auf "true" setzen um Verbindung zu aktivieren
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional

logger = logging.getLogger(__name__)

# ── Konfiguration aus Umgebungsvariablen ──────────────────────────────────────

def _cfg() -> dict:
    return {
        "host":     os.environ.get("RAMICRO_HOST", ""),
        "port":     int(os.environ.get("RAMICRO_PORT", "1433")),
        "database": os.environ.get("RAMICRO_DATABASE", "RAMICRO"),
        "user":     os.environ.get("RAMICRO_USER", ""),
        "password": os.environ.get("RAMICRO_PASSWORD", ""),
        "timeout":  int(os.environ.get("RAMICRO_TIMEOUT", "10")),
        "aktiv":    os.environ.get("RAMICRO_AKTIV", "false").lower() == "true",
    }


class RaMicroNichtAktiv(Exception):
    """RA-Micro Verbindung ist in .env deaktiviert (RAMICRO_AKTIV != true)."""


class RaMicroVerbindungsFehler(Exception):
    """Verbindung zum SQL Server fehlgeschlagen."""


def verbindung_pruefen() -> dict:
    """
    Prüft Verbindung und gibt Statusinfo zurück.
    Sicher aufrufbar – wirft keine Exceptions.
    """
    cfg = _cfg()

    if not cfg["aktiv"]:
        return {"status": "deaktiviert", "meldung": "RAMICRO_AKTIV ist nicht 'true'"}

    if not cfg["host"] or not cfg["user"]:
        return {"status": "fehler", "meldung": "RAMICRO_HOST oder RAMICRO_USER nicht konfiguriert"}

    try:
        import pymssql
        # FreeTDS/pymssql: Port muss im server-String stehen ("host:port"),
        # der separate port-Parameter wird in manchen Versionen ignoriert.
        server_str = f"{cfg['host']}:{cfg['port']}"
        with pymssql.connect(
            server=server_str,
            database=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            login_timeout=cfg["timeout"],
            as_dict=True,
            tds_version="7.0",   # Dieser Server antwortet nur auf TDS 7.0
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
        return {"status": "ok", "host": cfg["host"], "datenbank": cfg["database"]}
    except ImportError:
        return {"status": "fehler", "meldung": "pymssql nicht installiert (pip install pymssql)"}
    except Exception as e:
        logger.error("RA-Micro Verbindungstest fehlgeschlagen: %s", e)
        return {"status": "fehler", "meldung": str(e)}


@contextmanager
def get_ramicro_connection():
    """
    Context-Manager für RA-Micro Datenbankverbindungen.

    Nur-Lese – kein COMMIT, kein INSERT/UPDATE/DELETE.

    Verwendung:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT ...")
            rows = cur.fetchall()

    Wirft:
        RaMicroNichtAktiv   – wenn RAMICRO_AKTIV != 'true'
        RaMicroVerbindungsFehler – bei Verbindungsproblemen
    """
    cfg = _cfg()

    if not cfg["aktiv"]:
        raise RaMicroNichtAktiv(
            "RA-Micro Verbindung ist deaktiviert. "
            "RAMICRO_AKTIV=true in .env setzen."
        )

    if not cfg["host"] or not cfg["user"]:
        raise RaMicroVerbindungsFehler(
            "RA-Micro nicht vollständig konfiguriert. "
            "RAMICRO_HOST, RAMICRO_USER und RAMICRO_PASSWORD in .env prüfen."
        )

    try:
        import pymssql
    except ImportError:
        raise RaMicroVerbindungsFehler(
            "pymssql nicht installiert. "
            "pip install pymssql==2.3.1 ausführen und Docker neu bauen."
        )

    try:
        # FreeTDS/pymssql: Port muss im server-String stehen ("host:port"),
        # der separate port-Parameter wird in manchen Versionen ignoriert.
        server_str = f"{cfg['host']}:{cfg['port']}"
        conn = pymssql.connect(
            server=server_str,
            database=cfg["database"],
            user=cfg["user"],
            password=cfg["password"],
            login_timeout=cfg["timeout"],
            as_dict=True,
            charset="UTF-8",
            tds_version="7.0",   # Dieser Server antwortet nur auf TDS 7.0
        )
        logger.debug("RA-Micro Verbindung hergestellt: %s/%s", cfg["host"], cfg["database"])
        try:
            yield conn
        finally:
            conn.close()
    except Exception as e:
        logger.error("RA-Micro Verbindung fehlgeschlagen: %s", e)
        raise RaMicroVerbindungsFehler(f"Verbindung zu {cfg['host']} fehlgeschlagen: {e}") from e
