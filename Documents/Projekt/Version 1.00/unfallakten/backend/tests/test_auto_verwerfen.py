"""Tests fuer backend/intake/verwerfen.py::auto_verwerfen."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(test_id, tmp_dir):
    db_path = os.path.join(tmp_dir, f"av_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    for m in (db_mod, sm_mod):
        importlib.reload(m)
    sm_mod.create_schema()
    sm_mod.run_migrations()
    return db_mod


class TestAutoVerwerfen(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="av_test_")
        self.db = _fresh_db(self._testMethodName, self._tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _lege_dok_an(self, sha, status="bereit_zur_review"):
        with self.db.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente (sha256, payload_typ, queue_status) "
                "VALUES (?, 'text', ?)", (sha, status),
            )
            return cur.lastrowid

    def test_setzt_soft_delete_und_log_als_system(self):
        from backend.intake.verwerfen import auto_verwerfen
        did = self._lege_dok_an("s1")
        ts = auto_verwerfen(did, grund="rauschen", kommentar="Auto: Test")
        self.assertIsNotNone(ts)
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_grund, verworfen_am, verworfen_von "
                "FROM intake_dokumente WHERE id=?", (did,),
            ).fetchone()
            log = conn.execute(
                "SELECT feld, wert_alt, wert_neu, benutzer_id FROM korrektur_log "
                "WHERE intake_dokument_id=? AND feld='verworfen'", (did,),
            ).fetchone()
        self.assertEqual(row["verworfen_grund"], "rauschen")
        self.assertIsNotNone(row["verworfen_am"])
        self.assertIsNone(row["verworfen_von"])
        self.assertEqual(log["wert_alt"], "bereit_zur_review")
        self.assertIsNone(log["benutzer_id"])
        self.assertEqual(json.loads(log["wert_neu"])["kommentar"], "Auto: Test")

    def test_bereits_verworfenes_wird_uebersprungen(self):
        from backend.intake.verwerfen import auto_verwerfen
        did = self._lege_dok_an("s2")
        self.assertIsNotNone(auto_verwerfen(did, grund="rauschen"))
        self.assertIsNone(auto_verwerfen(did, grund="rauschen"))

    def test_freigegebenes_wird_uebersprungen(self):
        from backend.intake.verwerfen import auto_verwerfen
        did = self._lege_dok_an("s3", status="freigegeben")
        self.assertIsNone(auto_verwerfen(did, grund="rauschen"))
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_am FROM intake_dokumente WHERE id=?", (did,),
            ).fetchone()
        self.assertIsNone(row["verworfen_am"])

    def test_unbekannte_id_none(self):
        from backend.intake.verwerfen import auto_verwerfen
        self.assertIsNone(auto_verwerfen(999999, grund="rauschen"))

    def test_laufendes_dokument_ist_verwerfbar(self):
        # Race: Worker least den Body-Doc auf 'laeuft', waehrend
        # auto_verwerfen fuer denselben Intake laeuft (Fix 1).
        from backend.intake.verwerfen import auto_verwerfen
        did = self._lege_dok_an("s4", status="laeuft")
        ts = auto_verwerfen(did, grund="rauschen")
        self.assertIsNotNone(ts)
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_am FROM intake_dokumente WHERE id=?", (did,),
            ).fetchone()
        self.assertIsNotNone(row["verworfen_am"])


if __name__ == "__main__":
    unittest.main()
