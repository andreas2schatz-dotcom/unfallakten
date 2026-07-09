"""
Tests fuer P1.5a — ReguWizard-Speichern erzeugt Ereignis
``abrechnung_eingegangen``.

Testkriterien (aus P1.5-Prompt):
  (a) Nach ReguWizard-Erfassung liefert /positionen/status dieselben
      Betraege wie die RegulierungSection (Abgleichstest).
  (b) Doppelerfassung erzeugt keine Doppel-Ereignisse.
  (K-M2)  Erneutes Speichern zu bereits erfasstem Abrechnungsschreiben
          erzeugt NEUES Ereignis mit ersetzt_kopf_id (Kopf-Ersetzung).

Test-Modus: Model-Ebene (kein Flask-App), damit die Tests dokumentieren,
was der Bestaetigungsweg unabhaengig vom HTTP-Layer garantieren muss.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _RegulierungTestBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15a_", suffix=".sqlite")
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
            # Vollhaftungspflichtige Kuerzungsart fuer gekuerzt/abgelehnt.
            # Es gibt Seed-Daten aus init_db(); id per INSERT OR IGNORE
            # feste 1 -- entweder Seed-Datensatz oder unser Insert.
            conn.execute(
                "INSERT OR IGNORE INTO kuerzungsarten "
                "(id, bezeichnung, kategorie, sv_stellungnahme_erforderlich) "
                "VALUES (1, 'UPE-Aufschlag', 'fahrzeugschaden', 0)"
            )
            # Beispiel-Dokumentzeile (die vom Freigabe-Adapter erzeugt worden
            # waere -- fuer den Test genuegt ein Direktinsert).
            conn.execute(
                "INSERT INTO dokumente "
                "(akte_id, dateiname, dateipfad, dateityp, typ) "
                "VALUES ('44/22', 'abrechnung.pdf', 'x', 'pdf', "
                " 'abrechnungsschreiben')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass


class TestErzeugeAusRegulierung(_RegulierungTestBasis):
    """Helper backend/services/eingehende_ereignisse.erzeuge_aus_regulierung."""

    def _hole_dok_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM dokumente WHERE akte_id='44/22' "
                "AND typ='abrechnungsschreiben'"
            ).fetchone()["id"]

    def test_erzeugt_ereignis_mit_positionen_und_wirkungen(self):
        from backend.services.eingehende_ereignisse import (
            erzeuge_aus_regulierung,
        )
        from backend.db.database import get_connection

        dok_id = self._hole_dok_id()
        positionen = [
            # reparaturkosten: 4000 gefordert, 3500 reguliert, Rest gekuerzt
            {"position_key": "reparaturkosten",
             "betrag_gefordert": 4000.0, "betrag_reguliert": 3500.0,
             "kuerzungsart_id": 1},
            # sv_kosten: 500 gefordert, 500 reguliert -> nur anerkannt
            {"position_key": "sv_kosten",
             "betrag_gefordert": 500.0, "betrag_reguliert": 500.0,
             "kuerzungsart_id": None},
            # wertminderung: 700 gefordert, 0 reguliert, Kuerzungsart -> abgelehnt
            {"position_key": "wertminderung",
             "betrag_gefordert": 700.0, "betrag_reguliert": 0.0,
             "kuerzungsart_id": 1},
        ]
        eid = erzeuge_aus_regulierung(
            akte_az="44/22",
            dokument_id=dok_id,
            datum="2022-05-10",
            positionen=positionen,
            benutzer_id=None,
        )
        self.assertIsInstance(eid, int)

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT position_key, wirkung, betrag, kuerzungsart_id "
                "FROM ereignis_positionen WHERE ereignis_id=? "
                "ORDER BY position_key, wirkung", (eid,)
            ).fetchall()
        by_key = {(r["position_key"], r["wirkung"]): dict(r) for r in rows}

        # reparaturkosten: anerkannt 3500 + gekuerzt 500
        self.assertIn(("reparaturkosten", "anerkannt"), by_key)
        self.assertEqual(by_key[("reparaturkosten", "anerkannt")]["betrag"],
                         3500.0)
        self.assertIn(("reparaturkosten", "gekuerzt"), by_key)
        self.assertEqual(by_key[("reparaturkosten", "gekuerzt")]["betrag"],
                         500.0)
        self.assertEqual(
            by_key[("reparaturkosten", "gekuerzt")]["kuerzungsart_id"], 1,
        )
        # sv_kosten: nur anerkannt 500
        self.assertIn(("sv_kosten", "anerkannt"), by_key)
        self.assertNotIn(("sv_kosten", "gekuerzt"), by_key)
        # wertminderung: abgelehnt 700
        self.assertIn(("wertminderung", "abgelehnt"), by_key)
        self.assertEqual(by_key[("wertminderung", "abgelehnt")]["betrag"],
                         700.0)

    def test_doppelaufruf_liefert_gleiche_ereignis_id(self):
        """Guard-Effekt: bei bereits erfasster (akte, dokument, typ) wird
        KEIN neues Ereignis geschrieben, sondern die alte ID geliefert."""
        from backend.services.eingehende_ereignisse import (
            erzeuge_aus_regulierung,
        )
        from backend.db.database import get_connection

        dok_id = self._hole_dok_id()
        positionen = [
            {"position_key": "reparaturkosten",
             "betrag_gefordert": 4000.0, "betrag_reguliert": 4000.0,
             "kuerzungsart_id": None},
        ]
        first = erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=dok_id,
            datum="2022-05-10", positionen=positionen,
        )
        second = erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=dok_id,
            datum="2022-05-10", positionen=positionen,
        )
        self.assertEqual(first, second)

        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse "
                "WHERE akte_az='44/22' AND ereignistyp='abrechnung_eingegangen'"
            ).fetchone()[0]
        self.assertEqual(n, 1)

    def test_erneutes_speichern_mit_ersetzt_erzeugt_neues_ereignis(self):
        """K-M2 aus freigabe.md 3: erneutes Speichern des ReguWizards zu
        bereits ereignis-erfasstem Abrechnungsschreiben erzeugt ein NEUES
        Ereignis mit ersetzt_kopf_id des vorherigen -- nie Update, nie
        Doppelereignis."""
        from backend.services.eingehende_ereignisse import (
            erzeuge_aus_regulierung,
        )
        from backend.db.database import get_connection

        dok_id = self._hole_dok_id()
        alt_id = erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=dok_id, datum="2022-05-10",
            positionen=[{"position_key": "reparaturkosten",
                          "betrag_gefordert": 4000.0,
                          "betrag_reguliert": 3500.0,
                          "kuerzungsart_id": 1}],
        )
        # Neuaufruf mit ``ersetzt=True`` -> Kopf-Ersetzung.
        neu_id = erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=dok_id, datum="2022-05-11",
            positionen=[{"position_key": "reparaturkosten",
                          "betrag_gefordert": 4000.0,
                          "betrag_reguliert": 3800.0,
                          "kuerzungsart_id": 1}],
            ersetzt=True,
        )
        self.assertNotEqual(neu_id, alt_id)

        with get_connection() as conn:
            alt_kopf = conn.execute(
                "SELECT ersetzt_durch FROM ereignisse WHERE id=?", (alt_id,)
            ).fetchone()
            cache_alt = conn.execute(
                "SELECT status FROM position_ereignis_cache WHERE ereignis_id=?",
                (alt_id,)
            ).fetchall()
            cache_neu = conn.execute(
                "SELECT status FROM position_ereignis_cache WHERE ereignis_id=?",
                (neu_id,)
            ).fetchall()
        self.assertEqual(alt_kopf["ersetzt_durch"], neu_id)
        for r in cache_alt:
            self.assertEqual(r["status"], "ersetzt")
        for r in cache_neu:
            self.assertEqual(r["status"], "aktuell")

    def test_haftungsart_ablehnung_setzt_alle_positionen_abgelehnt(self):
        """Wenn ``haftungsart='ablehnung'`` gesetzt ist, sind ALLE
        Positionen abgelehnt -- auch ohne Kuerzungsart pro Position."""
        from backend.services.eingehende_ereignisse import (
            erzeuge_aus_regulierung,
        )
        from backend.db.database import get_connection

        dok_id = self._hole_dok_id()
        eid = erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=dok_id, datum="2022-05-10",
            haftungsart="ablehnung",
            positionen=[
                {"position_key": "reparaturkosten",
                 "betrag_gefordert": 4000.0, "betrag_reguliert": 0.0,
                 "kuerzungsart_id": None},
                {"position_key": "wertminderung",
                 "betrag_gefordert": 500.0, "betrag_reguliert": 0.0,
                 "kuerzungsart_id": None},
            ],
        )
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT position_key, wirkung "
                "FROM ereignis_positionen WHERE ereignis_id=?", (eid,)
            ).fetchall()
        for r in rows:
            self.assertEqual(r["wirkung"], "abgelehnt")

    def test_leere_positionen_liefert_akten_scope_ereignis(self):
        from backend.services.eingehende_ereignisse import (
            erzeuge_aus_regulierung,
        )
        from backend.db.database import get_connection

        dok_id = self._hole_dok_id()
        eid = erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=dok_id, datum="2022-05-10",
            positionen=[],
        )
        self.assertIsNotNone(eid)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignis_positionen WHERE ereignis_id=?",
                (eid,)
            ).fetchone()[0]
        self.assertEqual(n, 0)

    def test_kein_dokument_id_erlaubt(self):
        """Bei manueller ReguWizard-Erfassung ohne Dokument-Zuordnung
        entsteht trotzdem ein Ereignis -- Guard greift dann nicht
        (dokument_id=NULL)."""
        from backend.services.eingehende_ereignisse import (
            erzeuge_aus_regulierung,
        )
        eid = erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=None, datum="2022-05-10",
            positionen=[{"position_key": "reparaturkosten",
                          "betrag_gefordert": 4000.0,
                          "betrag_reguliert": 3500.0,
                          "kuerzungsart_id": 1}],
        )
        self.assertIsNotNone(eid)


class TestPositionsstatusAbgleich(_RegulierungTestBasis):
    """Testkriterium (a): /positionen/status liefert dieselben Betraege
    wie die Alt-Tabelle regulierung_positionen (Abgleich)."""

    def test_ableitung_summe_matcht_alt_tabelle(self):
        from backend.services.eingehende_ereignisse import (
            erzeuge_aus_regulierung,
        )
        from backend.services.positionsstatus_service import (
            leite_positionsstatus_ab,
        )
        from backend.db.database import get_connection

        with get_connection() as conn:
            dok_id = conn.execute(
                "SELECT id FROM dokumente LIMIT 1"
            ).fetchone()["id"]

        erzeuge_aus_regulierung(
            akte_az="44/22", dokument_id=dok_id, datum="2022-05-10",
            positionen=[
                {"position_key": "reparaturkosten",
                 "betrag_gefordert": 4000.0, "betrag_reguliert": 3500.0,
                 "kuerzungsart_id": 1},
                {"position_key": "sv_kosten",
                 "betrag_gefordert": 500.0, "betrag_reguliert": 500.0,
                 "kuerzungsart_id": None},
            ],
        )

        status = leite_positionsstatus_ab("44/22")
        # anerkannt = summe der aktuellen anerkannt-Wirkungen
        self.assertEqual(status["reparaturkosten"]["anerkannt"], 3500.0)
        self.assertEqual(status["reparaturkosten"]["gekuerzt"], 500.0)
        self.assertEqual(status["sv_kosten"]["anerkannt"], 500.0)


if __name__ == "__main__":
    unittest.main()
