"""
Bereinigt alle Abrechnungsschreiben für eine Akte aus der SQLite-DB.

Ausführen im Docker-Container:
    docker exec -it unfallakten-backend-dev python3 /app/backend/cleanup_abrechnungen.py

Oder lokal (Pfad anpassen):
    python3 cleanup_abrechnungen.py
"""

import sqlite3
import os
from pathlib import Path

# DB-Pfad -- konsistent zum Pattern aus backend/db/database.py:
# Diese Datei liegt in backend/, also
# Path(__file__).parent / "data" / "unfallakten.db"
# = backend/data/unfallakten.db (die Live-DB).
# Der historische Default "/app/backend/db/unfallakten.db" zeigte auf
# die Karteileiche (Schema-Version 16) und wurde in Praxis nur durch
# Dockerfile-/Compose-ENV DB_PATH ueberdeckt -- lokale Laeufe ausserhalb
# Docker liefen ins Leere.
DB_PATH = os.environ.get(
    "DB_PATH",
    str(Path(__file__).parent / "data" / "unfallakten.db"),
)

AKTE_ID = "31/21"   # Akte die bereinigt werden soll

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

print(f"DB: {DB_PATH}")
print(f"Akte: {AKTE_ID}\n")

# Aktuellen Stand zeigen
rows = conn.execute(
    "SELECT id, datum, parse_status, gesamt_reguliert, notizen "
    "FROM abrechnungsschreiben WHERE akte_id=? ORDER BY id",
    (AKTE_ID,)
).fetchall()
print(f"Vorher: {len(rows)} Einträge")
for r in rows:
    print(f"  ID {r['id']}: {r['datum']} | {r['parse_status']} | {r['gesamt_reguliert']} €")

if not rows:
    print("Nichts zu löschen.")
    conn.close()
    exit(0)

# Löschen
ids = [r['id'] for r in rows]
conn.execute("PRAGMA foreign_keys = OFF")
for abid in ids:
    conn.execute("DELETE FROM regulierung_positionen WHERE abrechnungsschreiben_id=?", (abid,))
    conn.execute("DELETE FROM abrechnungsschreiben WHERE id=?", (abid,))
conn.commit()
conn.execute("PRAGMA foreign_keys = ON")

# Migration 16 prüfen und ggf. ausführen
cols = {r[1] for r in conn.execute("PRAGMA table_info(abrechnungsschreiben)").fetchall()}
if "quelle" not in cols:
    print("\nFühre Migration 16 aus...")
    conn.execute("ALTER TABLE abrechnungsschreiben ADD COLUMN quelle TEXT NOT NULL DEFAULT 'pdf'")
    conn.execute("ALTER TABLE abrechnungsschreiben ADD COLUMN gesamt_kuerzung REAL NOT NULL DEFAULT 0.0")
    conn.execute("ALTER TABLE abrechnungsschreiben ADD COLUMN wdm_importiert INTEGER NOT NULL DEFAULT 0")
    rp_cols = {r[1] for r in conn.execute("PRAGMA table_info(regulierung_positionen)").fetchall()}
    if "position_label" not in rp_cols:
        conn.execute("ALTER TABLE regulierung_positionen ADD COLUMN position_label TEXT")
    conn.execute("INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (16, 'Migration 16')")
    conn.commit()
    print("  quelle, gesamt_kuerzung, wdm_importiert, position_label hinzugefügt")

# CHECK-Constraint auf regulierung_positionen entfernen
ddl = conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='regulierung_positionen'"
).fetchone()
if ddl and "CHECK(position_key IN" in (ddl['sql'] or ''):
    print("Entferne CHECK-Constraint auf regulierung_positionen...")
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS regulierung_positionen_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            abrechnungsschreiben_id INTEGER NOT NULL,
            position_key TEXT NOT NULL,
            position_label TEXT,
            betrag_gefordert REAL NOT NULL DEFAULT 0.0,
            betrag_reguliert REAL NOT NULL DEFAULT 0.0,
            kuerzungsart_id INTEGER,
            kuerzung_freitext TEXT,
            parser_erkannt INTEGER NOT NULL DEFAULT 0 CHECK(parser_erkannt IN (0,1)),
            parser_konfidenz REAL,
            fuer_klage_vorgemerkt INTEGER NOT NULL DEFAULT 0 CHECK(fuer_klage_vorgemerkt IN (0,1)),
            sv_stellungnahme_ausstehend INTEGER NOT NULL DEFAULT 0 CHECK(sv_stellungnahme_ausstehend IN (0,1))
        );
        INSERT INTO regulierung_positionen_new SELECT
            id, abrechnungsschreiben_id, position_key, NULL,
            betrag_gefordert, betrag_reguliert, kuerzungsart_id, kuerzung_freitext,
            parser_erkannt, parser_konfidenz, fuer_klage_vorgemerkt, sv_stellungnahme_ausstehend
        FROM regulierung_positionen;
        DROP TABLE regulierung_positionen;
        ALTER TABLE regulierung_positionen_new RENAME TO regulierung_positionen;
        CREATE INDEX IF NOT EXISTS idx_regpos_abrechnung_id ON regulierung_positionen(abrechnungsschreiben_id);
        CREATE INDEX IF NOT EXISTS idx_regpos_klage ON regulierung_positionen(fuer_klage_vorgemerkt);
    """)
    conn.execute("PRAGMA foreign_keys = ON")
    print("  CHECK-Constraint entfernt")

conn.close()

# Nachher zeigen
conn2 = sqlite3.connect(DB_PATH)
conn2.row_factory = sqlite3.Row
rows2 = conn2.execute(
    "SELECT COUNT(*) as n FROM abrechnungsschreiben WHERE akte_id=?", (AKTE_ID,)
).fetchone()
v = conn2.execute("SELECT MAX(version) as v FROM schema_version").fetchone()
conn2.close()

print(f"\nNachher: {rows2['n']} Einträge für {AKTE_ID}")
print(f"Schema-Version: {v['v']}")
print("\n✅ Bereinigung abgeschlossen. Container neu starten nicht nötig.")
