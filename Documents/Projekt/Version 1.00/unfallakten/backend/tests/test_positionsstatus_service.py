"""
Tests fuer backend/services/positionsstatus_service.py (P1.3).

Tabellenbasierte Unit-Tests je Zustandsuebergang aus POSITIONSMODELL-PLAN
Abschnitt 4.3:
  * offen: kein Ereignis vorhanden fuer die Position
  * gefordert: nur gefordert (kein anerkannt/gekuerzt/abgelehnt)
  * anerkannt: gefordert + anerkannt gedeckt (Summe anerkannt >= gefordert)
  * teilanerkannt: gefordert + anerkannt teilweise + Kuerzungen
  * bestritten: gefordert + abgelehnt (voll)
  * erledigt: Wirkung 'erledigt' vorhanden

Beruhigung: die Ableitung liest ausschliesslich aus
``position_ereignis_cache`` mit ``status='aktuell'``.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestLeitePositionsstatusAb(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="pss_", suffix=".sqlite")
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

    def _lade(self):
        from backend.services.positionsstatus_service import leite_positionsstatus_ab
        return leite_positionsstatus_ab("44/22")

    def _schr(self, typ, positionen, datum="2022-05-10",
               ersetzt_kopf_id=None, dokument_id=42):
        from backend.services.ereignis_service import schreibe_ereignis
        # Alle in der Tests genutzten Ereignistypen (gutachten_eingegangen,
        # abrechnung_eingegangen, forderung_generiert) sind quelle=dokument
        # -- also braucht die Checkliste (POSITIONSMODELL 4.6) einen
        # dokument_id fuer die 'erledigt'-Auswertung.
        return schreibe_ereignis(
            akte_az="44/22", ereignistyp=typ, quelle="dokument",
            datum=datum, positionen=positionen,
            dokument_id=dokument_id,
            ersetzt_kopf_id=ersetzt_kopf_id,
        )

    def test_leere_akte_hat_keinen_position_status(self):
        ergebnis = self._lade()
        self.assertEqual(ergebnis, {},
                          "Ohne Ereignisse leerer Statusbaum")

    def test_zustand_gefordert_nach_gutachten(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ])
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["zustand"], "gefordert")
        self.assertEqual(e["reparaturkosten"]["gefordert"], 5000.0)
        self.assertEqual(e["reparaturkosten"]["anerkannt"], 0.0)
        self.assertEqual(e["reparaturkosten"]["offen"], 5000.0)

    def test_zustand_anerkannt_bei_voller_deckung(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        self._schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "anerkannt", "betrag": 5000.0},
        ])
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["zustand"], "anerkannt")
        self.assertEqual(e["reparaturkosten"]["anerkannt"], 5000.0)
        self.assertEqual(e["reparaturkosten"]["offen"], 0.0)

    def test_zustand_teilanerkannt_bei_teilweiser_deckung(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        self._schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "anerkannt", "betrag": 4100.0},
            {"position_key": "reparaturkosten",
             "wirkung": "gekuerzt", "betrag": 900.0,
             "kuerzungsart_id": 1},
        ])
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["zustand"], "teilanerkannt")
        self.assertEqual(e["reparaturkosten"]["anerkannt"], 4100.0)
        self.assertEqual(e["reparaturkosten"]["offen"], 900.0)

    def test_zustand_bestritten_bei_voller_ablehnung(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        self._schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "abgelehnt", "betrag": 5000.0,
             "kuerzungsart_id": 1},
        ])
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["zustand"], "bestritten")
        self.assertEqual(e["reparaturkosten"]["anerkannt"], 0.0)
        self.assertEqual(e["reparaturkosten"]["offen"], 5000.0)

    def test_zustand_erledigt_ueberschreibt_andere(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        self._schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "erledigt", "betrag": 5000.0},
        ])
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["zustand"], "erledigt")

    def test_stand_ist_datum_des_juengsten_aktuellen_ereignisses(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        self._schr("abrechnung_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "anerkannt", "betrag": 5000.0},
        ], datum="2022-05-20")
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["stand"], "2022-05-20")

    def test_ersetztes_ereignis_fliesst_nicht_ein(self):
        """POSITIONSMODELL 2.2c: ein durch ersetzt_durch abgeloestes
        Ereignis darf keine Wirkung mehr in der Ableitung entfalten."""
        alt = self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        # Ergaenzungsgutachten mit hoeherem Wert ersetzt Original
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 6500.0},
        ], datum="2022-05-15", ersetzt_kopf_id=alt)

        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["gefordert"], 6500.0,
                          "Erst-Gutachten (5000) darf nicht mehr zaehlen")

    def test_registry_version_im_ergebnis(self):
        """Wissensgrenze: die Ableitung nennt ihre Registry-Version."""
        from backend.services.positionsstatus_service import leite_positionsstatus_ab
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ])
        e = leite_positionsstatus_ab("44/22", mit_registry=True)
        self.assertIn("_registry_version", e)
        self.assertIsInstance(e["_registry_version"], str)

    def test_has_unbestaetigt_flag_true_bei_wdm_herkunft(self):
        """PF-08: WDM-Import erzeugt Ereignis mit herkunft='wdm'; die
        Ableitung muss das als has_unbestaetigt=True je Position melden,
        damit das Dashboard den Vorschlag als unbestaetigt markieren kann."""
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az="44/22", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2022-05-14",
            dokument_id=None, herkunft="wdm",
            positionen=[
                {"position_key": "sonstiges", "wirkung": "anerkannt",
                 "betrag": 65.0},
            ],
        )
        e = self._lade()
        self.assertTrue(e["sonstiges"].get("has_unbestaetigt"),
                          "WDM-Ereignis muss has_unbestaetigt=True setzen")

    def test_has_unbestaetigt_flag_false_ohne_wdm(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ])
        e = self._lade()
        self.assertFalse(e["reparaturkosten"].get("has_unbestaetigt", False),
                          "Ohne WDM-Herkunft muss Flag False sein")

    def test_aggregation_aus_registry_je_position(self):
        """POSITIONSMODELL 6.1: Dashboard-Toggle bündelt nach
        aggregation-Gruppe aus positionsarten.yaml — daher muss die
        Ableitung die aggregation je Position mitliefern."""
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ])
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["aggregation"], "fahrzeugschaden")

    def test_kategorie_und_label_aus_registry(self):
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ])
        e = self._lade()
        self.assertEqual(e["reparaturkosten"]["kategorie"], "fahrzeugschaden")
        self.assertEqual(e["reparaturkosten"]["label"], "Reparaturkosten")

    def test_checkliste_wird_ausgewertet(self):
        """POSITIONSMODELL 4.6: pro Position werden benoetigte Ereignis-
        typen aus positionsarten.yaml gegen aktuelle Ereignisse gepueft.
        reparaturkosten braucht laut Registry gutachten_eingegangen +
        forderung_generiert."""
        self._schr("gutachten_eingegangen", [
            {"position_key": "reparaturkosten",
             "wirkung": "gefordert", "betrag": 5000.0},
        ], datum="2022-04-30")
        e = self._lade()
        cl = e["reparaturkosten"]["checkliste"]
        self.assertIn("gutachten_eingegangen", cl["erledigt"])
        self.assertIn("forderung_generiert", cl["offen"])


if __name__ == "__main__":
    unittest.main()
