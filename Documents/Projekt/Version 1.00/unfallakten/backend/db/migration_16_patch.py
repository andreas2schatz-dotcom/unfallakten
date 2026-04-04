"""
PATCH: schema_manager.py – Migration 16
========================================
Einfügen in die migrate()-Funktion nach Migration 15.
"""

# ── In der MIGRATIONS-Liste ergänzen ─────────────────────────────────────────
# (nach dem letzten bestehenden Eintrag, typisch: „if version < 15: migration_15(conn)")

MIGRATION_16_CODE = """
    if version < 16:
        migration_16(conn)
        set_version(conn, 16)
"""

# ── Neue Funktion einfügen (vor migrate()) ────────────────────────────────────

def migration_16(conn):
    """
    Manuelle Regulierungserfassung + WDM-Fallback.

    abrechnungen:
      - quelle TEXT DEFAULT 'pdf'   →  'pdf' | 'manuell' | 'wdm'
      - wdm_importiert INTEGER DEFAULT 0  →  Flag verhindert Doppel-Import

    abrechnungen_positionen:
      - position_label TEXT   →  Freitext-Label für Sonstiges-Positionen
    """
    # SQLite: ALTER TABLE kann nur Spalten hinzufügen, kein CHECK-Constraint
    conn.execute(
        "ALTER TABLE abrechnungen ADD COLUMN quelle TEXT NOT NULL DEFAULT 'pdf'"
    )
    conn.execute(
        "ALTER TABLE abrechnungen ADD COLUMN wdm_importiert INTEGER NOT NULL DEFAULT 0"
    )
    conn.execute(
        "ALTER TABLE abrechnungen_positionen ADD COLUMN position_label TEXT"
    )
