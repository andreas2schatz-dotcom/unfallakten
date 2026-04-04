"""
Modul 1 – Datenbankverbindung & Schema-Management
==================================================
Verwaltet SQLite-Verbindungen, aktiviert WAL-Modus und
stellt eine zentrale get_connection()-Factory bereit.

Spätere Migration zu PostgreSQL:
  Nur diese Datei + database_pg.py austauschen.
  Alle Models bleiben identisch.
"""

import sqlite3
import os
import logging
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# Datenbankpfad aus Umgebungsvariable oder Standard
DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "data" / "unfallakten.db"))


def _ensure_data_dir() -> None:
    """Stellt sicher, dass das Datenbankverzeichnis existiert."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def get_raw_connection() -> sqlite3.Connection:
    """
    Erstellt eine neue SQLite-Verbindung mit optimierten Einstellungen.

    Konfiguration:
      - WAL-Modus: Mehrere gleichzeitige Lesezugriffe, ein Schreiber
      - Foreign Keys: MÜSSEN explizit aktiviert werden in SQLite
      - Row Factory: Zeilen als dict-ähnliche Objekte (sqlite3.Row)
      - Timeout: 30s Wartezeit bei gesperrter Datenbank
    """
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    # Kritische PRAGMA-Einstellungen
    conn.execute("PRAGMA journal_mode=WAL;")        # Write-Ahead Logging
    conn.execute("PRAGMA foreign_keys=ON;")         # FK-Constraints erzwingen
    conn.execute("PRAGMA synchronous=NORMAL;")      # Balance: Sicherheit vs. Speed
    conn.execute("PRAGMA cache_size=-64000;")       # 64 MB Cache
    conn.execute("PRAGMA temp_store=MEMORY;")       # Temp-Tabellen im RAM
    return conn


@contextmanager
def get_connection():
    """
    Context-Manager für sichere Datenbankverbindungen.

    Verwendung:
        with get_connection() as conn:
            conn.execute("SELECT ...")

    Führt automatisch COMMIT bei Erfolg und ROLLBACK bei Fehler durch.
    """
    conn = get_raw_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db_path() -> str:
    return DB_PATH
