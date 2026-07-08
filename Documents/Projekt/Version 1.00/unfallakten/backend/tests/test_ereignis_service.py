"""
Tests fuer backend/services/ereignis_service.py (P1.2).

Verhalten:
  * schreibe_ereignis() erzeugt Ebene-1-Kopf + n:m-Zeilen + Ebene-2-Cache
    in einer Transaktion.
  * rebuild_cache() rekonstruiert den kompletten Cache aus Ebene 1 --
    nach beliebiger Ereignisfolge muss gilt: Cache == Rebuild.
  * ersetzt_durch fuehrt dazu, dass die alte Cache-Zeile auf 'ersetzt'
    wechselt (Ableitungs-Invariante).
  * Registry-Validierung: unbekannter Ereignistyp / unbekannte
    Wirkung / unbekannter position_key wirft.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestEreignisService(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="es_", suffix=".sqlite")
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

    def test_schreibe_ereignis_legt_kopf_positionen_cache_an(self):
        from backend.services.ereignis_service import schreibe_ereignis
        from backend.db.database import get_connection

        eid = schreibe_ereignis(
            akte_az="44/22",
            ereignistyp="abrechnung_eingegangen",
            quelle="dokument",
            datum="2022-05-10",
            positionen=[
                {"position_key": "reparaturkosten",
                 "wirkung": "anerkannt", "betrag": 4100.0},
                {"position_key": "reparaturkosten",
                 "wirkung": "gekuerzt",  "betrag": 100.0,
                 "kuerzungsart_id": 1},
            ],
        )
        self.assertIsInstance(eid, int)

        with get_connection() as conn:
            kopf = conn.execute(
                "SELECT ereignistyp, richtung, quelle FROM ereignisse "
                "WHERE id=?", (eid,)
            ).fetchone()
            pos = conn.execute(
                "SELECT position_key, wirkung, betrag "
                "FROM ereignis_positionen WHERE ereignis_id=?", (eid,)
            ).fetchall()
            cache = conn.execute(
                "SELECT position_key, wirkung, status FROM position_ereignis_cache "
                "WHERE akte_az='44/22' ORDER BY wirkung"
            ).fetchall()

        self.assertEqual(kopf["ereignistyp"], "abrechnung_eingegangen")
        self.assertEqual(kopf["richtung"], "eingehend")
        self.assertEqual(len(pos), 2)
        self.assertEqual(len(cache), 2)
        for row in cache:
            self.assertEqual(row["status"], "aktuell")

    def test_unbekannter_ereignistyp_wirft(self):
        from backend.services.ereignis_service import schreibe_ereignis
        with self.assertRaisesRegex(ValueError, "Unbekannter Ereignistyp"):
            schreibe_ereignis(
                akte_az="44/22",
                ereignistyp="quatschtyp",
                quelle="dokument",
                datum="2022-05-10",
            )

    def test_unbekannte_wirkung_wirft(self):
        from backend.services.ereignis_service import schreibe_ereignis
        with self.assertRaisesRegex(ValueError, "Unbekannte Wirkung"):
            schreibe_ereignis(
                akte_az="44/22", ereignistyp="abrechnung_eingegangen",
                quelle="dokument", datum="2022-05-10",
                positionen=[{"position_key": "reparaturkosten",
                             "wirkung": "phantasiewirkung"}],
            )

    def test_unbekannter_position_key_wirft(self):
        from backend.services.ereignis_service import schreibe_ereignis
        with self.assertRaisesRegex(ValueError, "Unbekannter position_key"):
            schreibe_ereignis(
                akte_az="44/22", ereignistyp="abrechnung_eingegangen",
                quelle="dokument", datum="2022-05-10",
                positionen=[{"position_key": "keine_position",
                             "wirkung": "anerkannt"}],
            )

    def test_quelle_gegen_ereignistyp_validiert(self):
        """abrechnung_eingegangen darf nur mit quelle in
        {dokument, manuell} kommen -- 'system' ist nicht erlaubt."""
        from backend.services.ereignis_service import schreibe_ereignis
        with self.assertRaisesRegex(ValueError, "Quelle"):
            schreibe_ereignis(
                akte_az="44/22", ereignistyp="abrechnung_eingegangen",
                quelle="system", datum="2022-05-10",
            )

    def test_rebuild_cache_ist_konsistent(self):
        """Nach beliebiger Ereignisfolge muss Cache == Rebuild sein."""
        from backend.services.ereignis_service import (
            schreibe_ereignis, rebuild_cache,
        )
        from backend.db.database import get_connection

        schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-04-30",
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "gefordert", "betrag": 5000.0}],
        )
        schreibe_ereignis(
            akte_az="44/22", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2022-05-10",
            positionen=[
                {"position_key": "reparaturkosten",
                 "wirkung": "anerkannt", "betrag": 4100.0},
                {"position_key": "reparaturkosten",
                 "wirkung": "gekuerzt", "betrag": 900.0,
                 "kuerzungsart_id": 1},
            ],
        )

        with get_connection() as conn:
            cache_vorher = conn.execute(
                "SELECT akte_az, position_key, ereignis_id, ereignistyp, "
                "       wirkung, betrag, COALESCE(kuerzungsart_id, 0) AS k, "
                "       status "
                "FROM position_ereignis_cache ORDER BY id"
            ).fetchall()
            cache_vorher = [dict(r) for r in cache_vorher]

        rebuild_cache()

        with get_connection() as conn:
            cache_nachher = conn.execute(
                "SELECT akte_az, position_key, ereignis_id, ereignistyp, "
                "       wirkung, betrag, COALESCE(kuerzungsart_id, 0) AS k, "
                "       status "
                "FROM position_ereignis_cache ORDER BY id"
            ).fetchall()
            cache_nachher = [dict(r) for r in cache_nachher]

        # Vergleich ohne id-Reihenfolge
        def _key(row):
            return (row["akte_az"], row["position_key"], row["ereignis_id"],
                    row["wirkung"], row["k"])
        self.assertEqual(
            sorted((_key(r), r["betrag"], r["status"]) for r in cache_vorher),
            sorted((_key(r), r["betrag"], r["status"]) for r in cache_nachher),
            "Cache-Zustand nach schreibe_ereignis() weicht von "
            "rebuild_cache() ab -- schreibe_ereignis ist nicht mehr "
            "Single-Source-of-Truth-Kompatibel",
        )

    def test_ersetzt_durch_markiert_alten_cache_als_ersetzt(self):
        """Ergaenzungsgutachten: neues Ereignis ersetzt altes per
        ersetzt_durch am Kopf. Cache der alten Zeile -> 'ersetzt'."""
        from backend.services.ereignis_service import schreibe_ereignis
        from backend.db.database import get_connection

        alt_id = schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-04-30",
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "gefordert", "betrag": 5000.0}],
        )
        neu_id = schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-05-15",
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "gefordert", "betrag": 5500.0}],
            ersetzt_kopf_id=alt_id,
        )

        with get_connection() as conn:
            alt_kopf = conn.execute(
                "SELECT ersetzt_durch FROM ereignisse WHERE id=?", (alt_id,)
            ).fetchone()
            cache = conn.execute(
                "SELECT ereignis_id, status FROM position_ereignis_cache "
                "WHERE akte_az='44/22' ORDER BY id"
            ).fetchall()
        self.assertEqual(alt_kopf["ersetzt_durch"], neu_id)
        cache_map = {r["ereignis_id"]: r["status"] for r in cache}
        self.assertEqual(cache_map[alt_id], "ersetzt")
        self.assertEqual(cache_map[neu_id], "aktuell")

    def test_akten_scope_ereignis_ohne_positionen(self):
        """POSITIONSMODELL 4.2: null Positionszeilen = Akten-Scope-Ereignis."""
        from backend.services.ereignis_service import schreibe_ereignis
        from backend.db.database import get_connection

        eid = schreibe_ereignis(
            akte_az="44/22", ereignistyp="vollmacht_eingegangen",
            quelle="dokument", datum="2022-04-27",
        )
        with get_connection() as conn:
            n_pos = conn.execute(
                "SELECT COUNT(*) FROM ereignis_positionen WHERE ereignis_id=?",
                (eid,)
            ).fetchone()[0]
            n_cache = conn.execute(
                "SELECT COUNT(*) FROM position_ereignis_cache "
                "WHERE ereignis_id=?", (eid,)
            ).fetchone()[0]
        self.assertEqual(n_pos, 0)
        self.assertEqual(n_cache, 0)


if __name__ == "__main__":
    unittest.main()
