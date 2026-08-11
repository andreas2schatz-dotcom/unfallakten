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


class TestErfasseForderung(ForderungModellBasis):
    """C-1: erfasse_forderung übernimmt die gerenderte Brief-Positionsliste
    statt das Schaden-Dict selbst zu interpretieren."""

    def test_positionen_liste_wird_uebernommen(self):
        pos = self.forderung.erfasse_forderung("901/25", positionen=[
            {"key": "rep_gutachten_netto",
             "label": "Reparaturkosten lt. Gutachten (netto)",
             "betrag": 5448.62},
            {"key": "unkostenpauschale", "label": "Unkostenpauschale",
             "betrag": 30.0},
        ])
        d = {p.position_key: p for p in pos}
        self.assertEqual(set(d), {"rep_gutachten_netto", "unkostenpauschale"})
        self.assertEqual(d["rep_gutachten_netto"].betrag_gefordert, 5448.62)
        self.assertEqual(d["rep_gutachten_netto"].position_label,
                         "Reparaturkosten lt. Gutachten (netto)")

    def test_restwert_negativ_gespeichert(self):
        pos = self.forderung.erfasse_forderung("901/25", positionen=[
            {"key": "wiederbeschaffung", "label": "Wiederbeschaffungswert",
             "betrag": 18500.0},
            {"key": "restwert", "label": "abzgl. Restwert", "betrag": -3200.0},
        ])
        d = {p.position_key: p.betrag_gefordert for p in pos}
        self.assertEqual(d["restwert"], -3200.0)
        z = self.forderung.forderungs_zusammenfassung("901/25")
        self.assertEqual(z["gesamt_gefordert"], 15300.0)

    def test_nullbetraege_uebersprungen(self):
        pos = self.forderung.erfasse_forderung("901/25", positionen=[
            {"key": "nutzungsausfall", "label": "NA", "betrag": 0.0},
            {"key": "sv_kosten", "label": "SV", "betrag": 890.0},
        ])
        self.assertEqual([p.position_key for p in pos], ["sv_kosten"])

    def test_vollregulierte_keys_uebersprungen(self):
        self._lege_position_an("901/25", key="sv_kosten", betrag=890.0,
                               schreiben_nr=1, status="vollreguliert")
        pos = self.forderung.erfasse_forderung("901/25", positionen=[
            {"key": "sv_kosten", "label": "SV", "betrag": 890.0},
            {"key": "nutzungsausfall", "label": "NA", "betrag": 500.0},
        ])
        self.assertEqual([p.position_key for p in pos], ["nutzungsausfall"])
        self.assertEqual(pos[0].forderungsschreiben_nr, 2)


class TestZusammenfassungDedup(ForderungModellBasis):
    """I-8: Aggregate zählen je position_key nur den Stand des letzten
    Schreibens — sonst verdoppeln sich Summen ab Schreiben Nr. 2."""

    def test_gesamt_gefordert_letztes_schreiben_je_key(self):
        self._lege_position_an("901/25", key="nutzungsausfall", betrag=500.0,
                               schreiben_nr=1, status="teilreguliert")
        self._lege_position_an("901/25", key="nutzungsausfall", betrag=300.0,
                               schreiben_nr=2)
        z = self.forderung.forderungs_zusammenfassung("901/25")
        self.assertEqual(z["gesamt_gefordert"], 300.0)
        self.assertEqual(z["anzahl_schreiben"], 2)

    def test_vollregulierte_position_bleibt_in_summe(self):
        self._lege_position_an("901/25", key="sv_kosten", betrag=890.0,
                               schreiben_nr=1, status="vollreguliert")
        self._lege_position_an("901/25", key="nutzungsausfall", betrag=500.0,
                               schreiben_nr=2)
        z = self.forderung.forderungs_zusammenfassung("901/25")
        self.assertEqual(z["gesamt_gefordert"], 1390.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
