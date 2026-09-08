"""R2 — die Review-Freigabe traegt ihre Belege in die Belegliste ein."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Basis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="belzu_", suffix=".sqlite")
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
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) "
                "VALUES ('44/22', 'r.pdf', 'x', 'pdf', 'mietwagenrechnung')"
            )
            conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _dok_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='r.pdf'"
            ).fetchone()["id"]

    def _belege(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT position_key, dokument_id, betrag_aus_beleg "
                "FROM schadenposition_belege WHERE akte_az='44/22' "
                "ORDER BY position_key"
            ).fetchall()]


class TestOrdneBelegZu(_Basis):
    def test_legt_zuordnung_an(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=812.50)
        belege = self._belege()
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["position_key"], "mietwagenkosten")
        self.assertEqual(belege[0]["betrag_aus_beleg"], 812.50)

    def test_zweiter_aufruf_aktualisiert_statt_zu_doppeln(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=812.50)
        ordne_beleg_zu(akte_az="44/22", position_key="mietwagenkosten",
                       dokument_id=self._dok_id(), betrag=900.00)
        belege = self._belege()
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["betrag_aus_beleg"], 900.00)

    def test_unbekannte_position_wird_abgelehnt(self):
        from backend.services.beleg_zuordnung import ordne_beleg_zu
        with self.assertRaises(ValueError):
            ordne_beleg_zu(akte_az="44/22", position_key="fantasieposten",
                           dokument_id=self._dok_id())


class TestBelegeAusFreigabe(_Basis):
    def test_rechnung_erzeugt_einen_beleg(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            klasse="mietwagenrechnung",
            felder={"bruttobetrag": "812,50"},
        )
        self.assertEqual(keys, ["mietwagenkosten"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 812.50)

    def test_gutachten_alle_vier_positionen(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"wiederbeschaffungswert": "12000,00",
                    "restwert_brutto": "3000,00",
                    "wertminderung": "800,00",
                    "reparaturkosten_netto": "4500,00"},
        )
        self.assertEqual(keys, ["rep_gutachten_netto", "restwert",
                                "wertminderung", "wiederbeschaffung"])
        belege = {r["position_key"]: r["betrag_aus_beleg"]
                  for r in self._belege()}
        self.assertEqual(belege, {"wertminderung": 800.0,
                                  "restwert": 3000.0,
                                  "rep_gutachten_netto": 4500.0,
                                  "wiederbeschaffung": 12000.0})

    def test_gutachten_null_betraege_werden_nicht_weggelassen(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"wertminderung": "0,00", "restwert_brutto": "0,00"},
        )
        self.assertEqual(keys, ["restwert", "wertminderung"])
        belege = {r["position_key"]: r["betrag_aus_beleg"]
                  for r in self._belege()}
        self.assertEqual(belege, {"wertminderung": 0.0, "restwert": 0.0})

    def test_gutachten_sv_kosten_erzeugt_keine_belegzeile(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"sv_kosten_brutto": "1190,00",
                    "sv_kosten_netto": "1000,00"},
        )
        self.assertEqual(keys, [])
        self.assertEqual(self._belege(), [])

    def test_gutachten_restwert_vorsteuerabzug_nimmt_netto(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"restwert_netto": "2500,00",
                    "restwert_brutto": "3000,00"},
            vorsteuer=True,
        )
        self.assertEqual(keys, ["restwert"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 2500.0)

    def test_gutachten_restwert_ohne_vorsteuerabzug_nimmt_brutto(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"restwert_netto": "2500,00",
                    "restwert_brutto": "3000,00"},
            vorsteuer=False,
        )
        self.assertEqual(keys, ["restwert"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 3000.0)

    def test_gutachten_restwert_faellt_auf_anderen_wert_zurueck(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="gutachten",
            felder={"restwert_brutto": "3000,00"}, vorsteuer=True,
        )
        self.assertEqual(keys, ["restwert"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 3000.0)

    def test_fehler_in_ordne_beleg_zu_wird_abgefangen(self):
        from unittest.mock import patch
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        with patch("backend.services.beleg_zuordnung.ordne_beleg_zu",
                   side_effect=ValueError("boom")):
            keys = belege_aus_freigabe(
                akte_az="44/22", dokument_id=self._dok_id(),
                klasse="mietwagenrechnung",
                felder={"bruttobetrag": "812,50"},
            )
        self.assertEqual(keys, [])
        self.assertEqual(self._belege(), [])

    def test_klasse_ohne_positionsbezug_schreibt_nichts(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="arztbericht",
            felder={"datum": "01.02.2024"},
        )
        self.assertEqual(keys, [])
        self.assertEqual(self._belege(), [])

    def test_auffangklasse_rechnung_schreibt_nichts(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(), klasse="rechnung",
            felder={"bruttobetrag": "100,00"},
        )
        self.assertEqual(keys, [])

    def test_rechnung_faellt_auf_nettobetrag_zurueck(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            klasse="mietwagenrechnung",
            felder={"nettobetrag": "100,00"},
        )
        self.assertEqual(keys, ["mietwagenkosten"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 100.0)

    def test_rechnung_bruttobetrag_null_faellt_nicht_auf_netto_zurueck(self):
        from backend.services.beleg_zuordnung import belege_aus_freigabe
        keys = belege_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            klasse="mietwagenrechnung",
            felder={"bruttobetrag": "0,00", "nettobetrag": "500,00"},
        )
        self.assertEqual(keys, ["mietwagenkosten"])
        self.assertEqual(self._belege()[0]["betrag_aus_beleg"], 0.0)


class TestSchreibeFreigabeBelege(_Basis):
    def test_freigabe_erzeugt_belegzeile(self):
        import json
        from backend.routers.intake_routes import _schreibe_freigabe_belege
        dok = {"id": None, "klasse": "mietwagenrechnung",
               "parse_json": json.dumps(
                   {"felder": {"bruttobetrag": "812,50"}})}
        _schreibe_freigabe_belege(dok=dok, akte_az="44/22",
                                  dokument_id=self._dok_id())
        belege = self._belege()
        self.assertEqual(len(belege), 1)
        self.assertEqual(belege[0]["position_key"], "mietwagenkosten")
        self.assertEqual(belege[0]["betrag_aus_beleg"], 812.50)

    def test_fehler_im_freigabe_belegpfad_wird_abgefangen(self):
        from unittest.mock import patch
        from backend.routers.intake_routes import _schreibe_freigabe_belege
        dok = {"id": None, "klasse": "mietwagenrechnung", "parse_json": "{}"}
        with patch("backend.routers.intake_routes._mandanten_vorsteuer",
                   side_effect=RuntimeError("boom")):
            _schreibe_freigabe_belege(dok=dok, akte_az="44/22",
                                      dokument_id=self._dok_id())
        self.assertEqual(self._belege(), [])


if __name__ == "__main__":
    unittest.main()
