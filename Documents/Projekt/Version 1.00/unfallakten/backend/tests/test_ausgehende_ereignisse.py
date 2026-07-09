"""
Tests fuer backend/services/ausgehende_ereignisse.py (P1.4).

Der Helper ``erzeuge`` wrapt ``ereignis_service.schreibe_ereignis`` fuer
ausgehende Dokumente (word_service / klage_routes / stellungnahme /
sta / gebuehren_word). Wichtige Eigenschaften:

  * quelle wird auf 'dokument' gesetzt.
  * Best-Effort: Fehler beim Ereignis-Schreiben duerfen die eigentliche
    Dokument-Generierung NIE brechen. Rueckgabe = None bei Fehler.
  * Positionen-Liste akzeptiert dict-Format {position_key: betrag}
    (Convenience fuer Alt-Kontexte) oder Liste von Positions-Dicts.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestErzeuge(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p14h_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def test_erzeuge_schreibt_ereignis_mit_positionen_dict(self):
        from backend.services.ausgehende_ereignisse import erzeuge
        from backend.db.database import get_connection

        eid = erzeuge(
            akte_az="44/22",
            ereignistyp="forderung_generiert",
            dokument_id=1,
            positionen={"reparaturkosten": 5000.0,
                         "wertminderung":   500.0},
            datum="2022-05-10",
            benutzer_id=None,
            herkunft="word_service",
        )
        self.assertIsInstance(eid, int)

        with get_connection() as conn:
            pos = conn.execute(
                "SELECT position_key, wirkung, betrag "
                "FROM ereignis_positionen WHERE ereignis_id=?", (eid,)
            ).fetchall()
        d = {r["position_key"]: r["betrag"] for r in pos}
        self.assertEqual(d, {"reparaturkosten": 5000.0,
                              "wertminderung": 500.0})
        for r in pos:
            self.assertEqual(r["wirkung"], "gefordert")

    def test_erzeuge_akten_scope_ohne_positionen(self):
        from backend.services.ausgehende_ereignisse import erzeuge
        from backend.db.database import get_connection

        eid = erzeuge(
            akte_az="44/22",
            ereignistyp="sachstandsanfrage_generiert",
            dokument_id=1,
            positionen=None,
            datum="2022-05-10",
        )
        self.assertIsInstance(eid, int)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignis_positionen "
                "WHERE ereignis_id=?", (eid,)
            ).fetchone()[0]
        self.assertEqual(n, 0)

    def test_erzeuge_ist_best_effort_bei_fehler(self):
        """Ein Schreib-Fehler darf die aufrufende Generierung NIE brechen.
        Rueckgabe None."""
        from backend.services import ausgehende_ereignisse as ae
        with mock.patch(
            "backend.services.ausgehende_ereignisse.schreibe_ereignis",
            side_effect=RuntimeError("kaboom"),
        ):
            eid = ae.erzeuge(
                akte_az="44/22", ereignistyp="klage_generiert",
                dokument_id=1, positionen={"reparaturkosten": 100.0},
            )
        self.assertIsNone(eid)

    def test_erzeuge_ignoriert_unbekannte_position_keys(self):
        """Positionen mit unbekannten Keys werden weggeloggt, aber nicht
        durchgereicht (Alt-Kontexte koennen Fantasie-Keys enthalten).
        Ohne verbleibende Positionen entsteht ein Akten-Scope-Ereignis."""
        from backend.services.ausgehende_ereignisse import erzeuge
        from backend.db.database import get_connection

        eid = erzeuge(
            akte_az="44/22", ereignistyp="klage_generiert",
            dokument_id=1,
            positionen={"reparaturkosten": 100.0,
                         "diese_position_gibt_es_nicht": 50.0},
            datum="2022-05-10",
        )
        self.assertIsInstance(eid, int)
        with get_connection() as conn:
            zeilen = conn.execute(
                "SELECT position_key FROM ereignis_positionen "
                "WHERE ereignis_id=?", (eid,)
            ).fetchall()
        keys = {r["position_key"] for r in zeilen}
        self.assertEqual(keys, {"reparaturkosten"})


if __name__ == "__main__":
    unittest.main()
