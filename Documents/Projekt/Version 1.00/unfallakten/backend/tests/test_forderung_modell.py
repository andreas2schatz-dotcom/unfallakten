"""
Tests für backend/models/forderung.py (Forderungshistorie).

Entstanden aus dem Code-Review 2026-08-10 (Befunde C-1, I-7, I-8) —
das Modell hatte zuvor keine direkten Tests.
"""

import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class ForderungModellBasis(unittest.TestCase):
    """Frische SQLite-DB je Test, zwei Akten (901/25, 902/25)."""

    def setUp(self):
        db_path = os.path.join(_tmp_dir, f"fm_{self._testMethodName}.db")
        if os.path.exists(db_path):
            os.remove(db_path)
        os.environ["DB_PATH"] = db_path
        os.environ["JWT_SECRET_KEY"] = "test-key-32chars-minimum!!!!!"

        import importlib
        for mod in [
            "backend.db.database", "backend.db.schema_manager",
            "backend.models.benutzer", "backend.models.akte",
            "backend.models.forderung",
        ]:
            importlib.reload(__import__(mod, fromlist=[""]))

        from backend.db.schema_manager import init_db
        init_db()
        from backend.models.benutzer import erstelle_benutzer
        from backend.models.akte import erstelle_akte

        self.user = erstelle_benutzer("Admin", "a@b.de", "Admin1234!", "admin")
        erstelle_akte("901/25", "2025-03-15", self.user.id, unfallort="Offenbach")
        erstelle_akte("902/25", "2025-04-01", self.user.id, unfallort="Frankfurt")

        import backend.models.forderung as forderung
        self.forderung = forderung

    def _lege_position_an(self, az: str, key: str = "nutzungsausfall",
                          betrag: float = 500.0, schreiben_nr: int = 1,
                          status: str = "gefordert") -> int:
        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO forderung_positionen
                    (akte_id, forderungsschreiben_nr, datum, position_key,
                     position_label, betrag_gefordert, status)
                VALUES (?, ?, date('now'), ?, ?, ?, ?)
                """,
                (az, schreiben_nr, key, key, betrag, status),
            )
            return cur.lastrowid


class TestAktualisierePositionScoping(ForderungModellBasis):
    """I-7: PATCH darf nur Positionen der eigenen Akte ändern."""

    def test_fremde_akte_wird_abgelehnt(self):
        pid_b = self._lege_position_an("902/25")
        pos = self.forderung.aktualisiere_position(
            pid_b, akte_id="901/25", status="gekuerzt")
        self.assertIsNone(pos)
        rows = self.forderung.hole_forderung_positionen("902/25")
        self.assertEqual(rows[0].status, "gefordert")

    def test_eigene_akte_wird_geaendert(self):
        pid = self._lege_position_an("901/25")
        pos = self.forderung.aktualisiere_position(
            pid, akte_id="901/25", status="gekuerzt", betrag_reguliert=100.0)
        self.assertIsNotNone(pos)
        self.assertEqual(pos.status, "gekuerzt")
        self.assertEqual(pos.betrag_reguliert, 100.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
