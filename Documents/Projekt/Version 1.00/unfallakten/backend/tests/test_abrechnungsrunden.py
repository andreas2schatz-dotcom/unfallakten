import os
import tempfile
import unittest


class _DBBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        os.unlink(self._db_pfad)


class TestRundenVergleich(_DBBasis):
    def setUp(self):
        super().setUp()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("INSERT INTO unfallakte (az) VALUES ('971/25')")
            conn.execute("PRAGMA foreign_keys = OFF")
            for dok_id in (101, 102):
                conn.execute(
                    "INSERT INTO dokumente (id, typ, dateiname, dateipfad, akte_id) "
                    "VALUES (?, 'sonstiges', 'ab.pdf', '/nicht/vorhanden/ab.pdf', "
                    "'971/25')", (dok_id,))

    def _runde(self, datum, dok_id, kuerzung_betrag):
        from backend.services.ereignis_service import schreibe_ereignis
        return schreibe_ereignis(
            akte_az="971/25", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum=datum, dokument_id=dok_id,
            positionen=[
                {"position_key": "kostenpauschale", "wirkung": "anerkannt",
                 "betrag": 30.0 - kuerzung_betrag},
                {"position_key": "kostenpauschale", "wirkung": "gekuerzt",
                 "betrag": kuerzung_betrag, "kuerzungsart_id": 15},
            ])

    def test_nachzahlung_erkannt(self):
        self._runde("2026-06-01", 101, 5.0)
        self._runde("2026-07-01", 102, 0.0)
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        erg = leite_runden_ab("971/25")
        self.assertEqual(len(erg["runden"]), 2)
        v = next(x for x in erg["vergleich"]
                 if x["position_key"] == "kostenpauschale")
        self.assertEqual(v["status"], "nachzahlung")
        self.assertEqual(v["delta"], -5.0)

    def test_ersetzung_ist_keine_runde(self):
        e1 = self._runde("2026-06-01", 101, 5.0)
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az="971/25", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2026-06-01", dokument_id=101,
            positionen=[{"position_key": "kostenpauschale",
                         "wirkung": "gekuerzt", "betrag": 5.0,
                         "kuerzungsart_id": 15}],
            ersetzt_kopf_id=e1)
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        self.assertEqual(len(leite_runden_ab("971/25")["runden"]), 1)

    def test_aufrechterhalten_und_neu(self):
        self._runde("2026-06-01", 101, 5.0)
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az="971/25", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2026-07-01", dokument_id=102,
            positionen=[
                {"position_key": "kostenpauschale", "wirkung": "gekuerzt",
                 "betrag": 5.0, "kuerzungsart_id": 15},
                {"position_key": "wertminderung", "wirkung": "gekuerzt",
                 "betrag": 800.0, "kuerzungsart_id": 2},
            ])
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        stati = {(v["position_key"], v["status"])
                 for v in leite_runden_ab("971/25")["vergleich"]}
        self.assertIn(("kostenpauschale", "aufrechterhalten"), stati)
        self.assertIn(("wertminderung", "neu"), stati)

    def test_erhoehung_erkannt(self):
        self._runde("2026-06-01", 101, 5.0)
        self._runde("2026-07-01", 102, 12.5)
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        v = next(x for x in leite_runden_ab("971/25")["vergleich"]
                 if x["position_key"] == "kostenpauschale")
        self.assertEqual(v["status"], "erhoeht")
        self.assertEqual(v["delta"], 7.5)

    def test_eine_runde_ohne_vergleich(self):
        self._runde("2026-06-01", 101, 5.0)
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        erg = leite_runden_ab("971/25")
        self.assertEqual(len(erg["runden"]), 1)
        self.assertEqual(erg["vergleich"], [])

    def test_typloser_abzug_wird_gefuehrt(self):
        from backend.services.ereignis_service import schreibe_ereignis
        for datum, dok_id in (("2026-06-01", 101), ("2026-07-01", 102)):
            schreibe_ereignis(
                akte_az="971/25", ereignistyp="abrechnung_eingegangen",
                quelle="dokument", datum=datum, dokument_id=dok_id,
                positionen=[{"position_key": "mietwagenkosten",
                             "wirkung": "gekuerzt", "betrag": 100.0}])
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        v = next(x for x in leite_runden_ab("971/25")["vergleich"]
                 if x["position_key"] == "mietwagenkosten")
        self.assertIsNone(v["kuerzungsart_id"])
        self.assertIsNone(v["typ_code"])
        self.assertEqual(v["status"], "aufrechterhalten")


from backend.tests.test_kuerzungstyp_matching import _RouteBasis


class TestRundenEndpoint(_RouteBasis):
    def test_runden_endpoint_liefert_vergleich(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("INSERT INTO unfallakte (az) VALUES ('971/25')")
            for dok_id in (101, 102):
                conn.execute(
                    "INSERT INTO dokumente (id, typ, dateiname, dateipfad, akte_id) "
                    "VALUES (?, 'sonstiges', 'ab.pdf', '/nicht/vorhanden/ab.pdf', "
                    "'971/25')", (dok_id,))
        from backend.services.ereignis_service import schreibe_ereignis
        for datum, dok_id, betrag in (("2026-06-01", 101, 5.0),
                                      ("2026-07-01", 102, 0.0)):
            schreibe_ereignis(
                akte_az="971/25", ereignistyp="abrechnung_eingegangen",
                quelle="dokument", datum=datum, dokument_id=dok_id,
                positionen=[{"position_key": "kostenpauschale",
                             "wirkung": "gekuerzt", "betrag": betrag,
                             "kuerzungsart_id": 15}])
        r = self.client.get("/akten/971/25/abrechnungen/runden",
                            headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        daten = r.get_json()
        self.assertEqual(len(daten["runden"]), 2)
        self.assertEqual(daten["vergleich"][0]["status"], "nachzahlung")

    def test_runden_unbekannte_akte_leer(self):
        r = self.client.get("/akten/999/99/abrechnungen/runden",
                            headers=self._auth())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"runden": [], "vergleich": []})

    def test_runden_ungueltiges_az_404(self):
        r = self.client.get("/akten/xx/abrechnungen/runden",
                            headers=self._auth())
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
