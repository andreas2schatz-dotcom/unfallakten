import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="klgv_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _fresh_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return db_mod


class TestGlobalerVertreterPass(unittest.TestCase):
    def test_synthetischer_ghpv_bekommt_globalen_vertreter(self):
        db_mod = _fresh_db("ghpv")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(
                conn, "ADAC Autoversicherung AG", "Stefan Daehne", "Vorstand")
            alle_bet = [{
                "id": -1, "vorname": "", "name": "ADAC Autoversicherung AG",
                "firma": "ADAC Autoversicherung AG", "versicherung": "",
                "vertreter_name": "", "vertreter_funktion": "",
                "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "Stefan Daehne")
        self.assertEqual(alle_bet[0]["vertreter_funktion"], "Vorstand")

    def test_direkter_vertreter_hat_vorrang(self):
        db_mod = _fresh_db("vorrang")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "Muster AG", "Global Name", "Vorstand")
            alle_bet = [{
                "id": 5, "vorname": "", "name": "Muster AG", "firma": "Muster AG",
                "versicherung": "", "vertreter_name": "Direkt Name",
                "vertreter_funktion": "Vorstand", "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "Direkt Name")

    def test_natuerliche_person_mit_versicherung_bleibt_ohne_vertreter(self):
        db_mod = _fresh_db("person")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "HUK", "Falsch Fuellen", "Vorstand")
            alle_bet = [{
                "id": 9, "vorname": "Max", "name": "Mustermann", "firma": "",
                "versicherung": "HUK", "vertreter_name": "",
                "vertreter_funktion": "", "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "")

    def test_ra_micro_eintrag_ohne_vertreter_key(self):
        db_mod = _fresh_db("ramicro")
        from backend.models.firmen_vertreter import upsert_firmen_vertreter
        from backend.routers.klage_routes import _wende_globalen_vertreter_an
        with db_mod.get_connection() as conn:
            upsert_firmen_vertreter(conn, "Baloise AG", "B Vorstand", "Vorstand")
            alle_bet = [{
                "id": 0, "vorname": "", "name": "Baloise AG", "firma": "Baloise AG",
                "rolle_klage": "beklagter",
            }]
            _wende_globalen_vertreter_an(conn, alle_bet)
        self.assertEqual(alle_bet[0]["vertreter_name"], "B Vorstand")


if __name__ == "__main__":
    unittest.main()
