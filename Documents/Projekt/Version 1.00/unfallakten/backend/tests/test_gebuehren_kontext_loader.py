"""Regression-Test: _lade_gebuehren_kontext Streitwert-Fallback (toter COALESCE).

Vor dem Fix ignoriert die Streitwert-Fallback-Query rep_gutachten_netto,
weil rep_rechnung_brutto NOT NULL DEFAULT 0.0 ist (COALESCE fällt nie zurück).
Für fiktiv abgerechnete Fälle (keine Werkstattrechnung, nur Gutachten) wird
der Fahrzeugschaden-Anteil dadurch stillschweigend als 0 berechnet.
"""
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="gebkontext_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _ns(test_id: str):
    db_path = os.path.join(_tmp_dir, f"{test_id}.db")
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

    import backend.word.word_service as ws_mod
    importlib.reload(ws_mod)

    class NS:
        get_connection = staticmethod(db_mod.get_connection)
        lade_gebuehren_kontext = staticmethod(ws_mod._lade_gebuehren_kontext)
    return NS()


class TestGebuehrenKontextLoader(unittest.TestCase):

    def test_fiktiv_abgerechnet_gutachten_netto_fliesst_ein(self):
        ns = _ns("gk_fiktiv")
        with ns.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('77/26', '', 'offen')")
            conn.execute(
                "INSERT INTO schadenpositionen (akte_id, rep_gutachten_netto) "
                "VALUES ('77/26', 4000.0)")

        kontext = ns.lade_gebuehren_kontext("77/26")

        self.assertIsNotNone(kontext)
        self.assertGreaterEqual(kontext["streitwert"], 4000.0)
        self.assertIsNone(kontext["faktor"])

    def test_werkstattrechnung_hat_vorrang_vor_gutachten(self):
        ns = _ns("gk_rechnung_vorrang")
        with ns.get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('78/26', '', 'offen')")
            conn.execute(
                "INSERT INTO schadenpositionen "
                "(akte_id, rep_rechnung_brutto, rep_gutachten_netto) "
                "VALUES ('78/26', 3570.0, 3000.0)")

        kontext = ns.lade_gebuehren_kontext("78/26")

        self.assertIsNotNone(kontext)
        self.assertGreaterEqual(kontext["streitwert"], 3570.0)
        self.assertLess(kontext["streitwert"], 3570.0 + 3000.0)


if __name__ == "__main__":
    unittest.main()
