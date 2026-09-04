"""
Eine Geld-Wahrheit: Schadenpositionen + Abrechnungsart (DECISIONS 2026-08-26).

Entscheidung RA Schatz: Die erfassten Schadenpositionen und die
Abrechnungsart sind aktenwahr und gelten immer und ueberall. Der
Positionsstatus -- und damit Kopfzahl, PositionsDashboard und
Phasenberechnung der Uebersicht -- darf keine eigene Forderungssumme
mehr aus Ereignissen bilden.

  * gefordert  <- _schadenpositionen_rows() (Schaden-Tab + Abrechnungsart)
  * anerkannt  <- _baue_pos_map()           (Regulierung)

Damit zeigen Uebersicht, Abschlussbericht und Word-Abrechnungsuebersicht
zwingend dieselbe Zahl.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Basis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="pos_ssot_", suffix=".sqlite")
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
                "VALUES ('589/26', '2026-06-11', 'offen')")
            conn.execute(
                "INSERT INTO beteiligte (akte_id, rolle, name, vorsteuer) "
                "VALUES ('589/26', 'mandant', 'Pantea', 'N')")
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, dokumentenklasse) "
                "VALUES ('589/26', 'g.pdf', 'x', 'pdf', 'gutachten')")
            conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _schaden_589(self):
        """Echte Zahlen der Akte 589/26 (fiktive Abrechnung)."""
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO schadenpositionen "
                "(akte_id, abrechnungsart, rep_gutachten_netto, "
                " rep_gutachten_mwst, wiederbeschaffung, wertminderung, "
                " nutzungsausfall, sv_kosten, sv_kosten_netto, sv_kosten_ust, "
                " unkostenpauschale, sonstiges, sonstiges_beschr) "
                "VALUES ('589/26', 'fiktiv', 4882.48, 927.67, 13500.0, 150.0, "
                " 172.0, 992.34, 833.9, 158.44, 30.0, 29.75, "
                " 'Kosten der Nachbesichtigung')")
            conn.commit()

    def _dok_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='g.pdf'"
            ).fetchone()["id"]

    def _status(self):
        from backend.services.positionsstatus_service import (
            leite_positionsstatus_ab)
        return leite_positionsstatus_ab("589/26")

    def _summe(self, feld):
        return round(sum(p[feld] for p in self._status().values()), 2)


class TestForderungKommtAusDenSchadenpositionen(_Basis):

    def test_kopfzahl_entspricht_dem_schaden_tab(self):
        self._schaden_589()
        # berechne_abrechnungsart(): gesamt_brutto = 6.256,57
        self.assertAlmostEqual(self._summe("gefordert"), 6256.57, places=2)

    def test_gutachten_ereignis_aendert_die_forderung_nicht(self):
        """Das Ereignis dokumentiert, es rechnet nicht."""
        self._schaden_589()
        vorher = self._summe("gefordert")
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        erzeuge_aus_freigabe(
            akte_az="589/26", dokument_id=self._dok_id(),
            ereignistyp="gutachten_eingegangen", klasse="gutachten",
            felder={"reparaturkosten_netto": 4882.48,
                    "wiederbeschaffungswert": 13500.0,
                    "wertminderung": 150.0},
            datum="2026-08-26")
        self.assertAlmostEqual(self._summe("gefordert"), vorher, places=2)
        self.assertAlmostEqual(self._summe("gefordert"), 6256.57, places=2)

    def test_ohne_schadenpositionen_keine_forderung(self):
        self.assertEqual(self._summe("gefordert"), 0.0)

    def test_nebenpositionen_erscheinen_einzeln(self):
        self._schaden_589()
        st = self._status()
        self.assertAlmostEqual(st["rep_gutachten_netto"]["gefordert"], 4882.48, 2)
        self.assertAlmostEqual(st["sv_kosten"]["gefordert"], 992.34, 2)
        self.assertAlmostEqual(st["nutzungsausfall"]["gefordert"], 172.0, 2)
        self.assertAlmostEqual(st["unkostenpauschale"]["gefordert"], 30.0, 2)
        self.assertNotIn("wiederbeschaffung", st)


class TestZahlungKommtAusDerRegulierung(_Basis):

    def _abrechnung(self, position_key, betrag, gefordert=4882.48):
        from backend.models.abrechnungsschreiben import (
            erstelle_abrechnungsschreiben)
        return erstelle_abrechnungsschreiben(
            akte_id="589/26", datum="2026-06-30", haftungsart="vollhaftung",
            haftungsquote=100.0, bearbeiter_id=None, versicherung="AXA",
            positionen=[{"position_key": position_key,
                         "betrag_gefordert": gefordert,
                         "betrag_reguliert": betrag}])

    def test_zahlung_landet_auf_der_fahrzeugzeile(self):
        self._schaden_589()
        self._abrechnung("fahrzeugschaden", 2697.19)
        st = self._status()
        self.assertAlmostEqual(st["rep_gutachten_netto"]["anerkannt"], 2697.19, 2)
        self.assertAlmostEqual(st["rep_gutachten_netto"]["offen"], 2185.29, 2)

    def test_manuelle_korrektur_schlaegt_sofort_durch(self):
        """PATCH auf die Position -- ohne Ereignis-Nachzug."""
        self._schaden_589()
        ab = self._abrechnung("fahrzeugschaden", 2697.19)
        from backend.models.abrechnungsschreiben import aktualisiere_position
        pos_id = ab.as_dict()["positionen"][0]["id"]
        aktualisiere_position(pos_id, betrag_reguliert=3100.0)
        st = self._status()
        self.assertAlmostEqual(st["rep_gutachten_netto"]["anerkannt"], 3100.0, 2)
        self.assertAlmostEqual(self._summe("anerkannt"), 3100.0, 2)

    def test_zustand_folgt_den_aktenwahren_betraegen(self):
        self._schaden_589()
        self._abrechnung("sv_kosten", 992.34, gefordert=992.34)
        st = self._status()
        self.assertEqual(st["sv_kosten"]["zustand"], "anerkannt")
        self.assertEqual(st["rep_gutachten_netto"]["zustand"], "gefordert")


class TestGleichstandMitDemAbschlussbericht(_Basis):

    def test_summen_stimmen_mit_dem_bericht_ueberein(self):
        self._schaden_589()
        from backend.models.abrechnungsschreiben import (
            erstelle_abrechnungsschreiben)
        erstelle_abrechnungsschreiben(
            akte_id="589/26", datum="2026-06-30", haftungsart="vollhaftung",
            haftungsquote=100.0, bearbeiter_id=None, versicherung="AXA",
            positionen=[{"position_key": "fahrzeugschaden",
                         "betrag_gefordert": 4882.48,
                         "betrag_reguliert": 2697.19}])

        from backend.word.word_service import _lade_akte_daten
        from backend.models.akte import hole_akte_by_id
        from backend.services.abschluss_uebersicht import (
            baue_abschluss_uebersicht)
        daten = _lade_akte_daten("589/26", hole_akte_by_id("589/26"),
                                 dok_typ="abschlussbericht")
        bericht = baue_abschluss_uebersicht(daten)["summen"]

        self.assertAlmostEqual(self._summe("gefordert"),
                               bericht["gefordert"], places=2)
        self.assertAlmostEqual(self._summe("anerkannt"),
                               bericht["gezahlt"], places=2)


if __name__ == "__main__":
    unittest.main()
