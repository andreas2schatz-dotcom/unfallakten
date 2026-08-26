"""
Nachbesichtigungskosten als vollwertige Schadenposition.

RA Schatz 2026-08-26: "Wir haben in der Schadentabelle keine Position fuer
die Kosten der Nachbesichtigung. Diese Position kommt immer wieder."

Die DB-Spalte ``kostennb`` gab es laengst, aber ohne Eingabefeld -- und sie
war die einzige Nebenposition ohne ``_netto``-Geschwister: ``kostennb``
galt als NETTO und ``kostennb_ust`` wurde separat aufaddiert, waehrend
sv_kosten, mietwagenkosten & Co. den Bruttobetrag im Hauptfeld fuehren.
Wer den Rechnungsbetrag ins Feld tippt, haette so eine 19-%-Hochrechnung
ausgeloest.

Migration 70 zieht ``kostennb`` auf die Hausregel: ``kostennb`` = brutto,
``kostennb_netto`` + ``kostennb_ust`` = Aufteilung.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Basis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="kostennb_", suffix=".sqlite")
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
            conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass


class TestMigration70(_Basis):

    def test_spalte_kostennb_netto_existiert(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r["name"] for r in
                       conn.execute("PRAGMA table_info(schadenpositionen)")}
        for spalte in ("kostennb", "kostennb_netto", "kostennb_ust"):
            self.assertIn(spalte, spalten)


class TestBruttoKonvention(_Basis):
    """kostennb ist das Bruttofeld -- wie bei allen Nebenpositionen."""

    def _schaden(self, **felder):
        basis = {"abrechnungsart": "fiktiv", "rep_gutachten_netto": 1000.0}
        basis.update(felder)
        return basis

    def test_gesamtsumme_zaehlt_den_bruttobetrag_einmal(self):
        from backend.models.schaden import berechne_abrechnungsart
        erg = berechne_abrechnungsart(self._schaden(
            kostennb=29.75, kostennb_netto=25.0, kostennb_ust=4.75))
        # 1000 Reparatur + 29,75 Nachbesichtigung + 30 Unkostenpauschale? nein:
        # unkostenpauschale ist hier nicht gesetzt -> 1029,75
        self.assertAlmostEqual(erg["gesamt_brutto"], 1029.75, places=2)

    def test_ust_wird_nicht_zusaetzlich_addiert(self):
        from backend.models.schaden import berechne_abrechnungsart
        ohne = berechne_abrechnungsart(self._schaden(kostennb=29.75))
        mit = berechne_abrechnungsart(self._schaden(
            kostennb=29.75, kostennb_netto=25.0, kostennb_ust=4.75))
        self.assertAlmostEqual(ohne["gesamt_brutto"], mit["gesamt_brutto"], 2)

    def test_bericht_zeigt_den_rechnungsbetrag(self):
        from backend.word.abrechnungsuebersicht_service import (
            _schadenpositionen_rows)
        zeilen = {z["key"]: z["forderung"] for z in _schadenpositionen_rows(
            self._schaden(kostennb=29.75, kostennb_netto=25.0,
                          kostennb_ust=4.75), {}, False)}
        self.assertAlmostEqual(zeilen["kostennb"], 29.75, places=2)

    def test_bericht_ohne_aufteilung_rechnet_nicht_hoch(self):
        """Der Fallstrick: 29,75 im Feld darf nicht zu 35,40 werden."""
        from backend.word.abrechnungsuebersicht_service import (
            _schadenpositionen_rows)
        zeilen = {z["key"]: z["forderung"] for z in _schadenpositionen_rows(
            self._schaden(kostennb=29.75), {}, False)}
        self.assertAlmostEqual(zeilen["kostennb"], 29.75, places=2)

    def test_vorsteuermandant_bekommt_den_nettobetrag(self):
        from backend.word.abrechnungsuebersicht_service import (
            _schadenpositionen_rows)
        zeilen = {z["key"]: z["forderung"] for z in _schadenpositionen_rows(
            self._schaden(kostennb=29.75, kostennb_netto=25.0,
                          kostennb_ust=4.75), {}, True)}
        self.assertAlmostEqual(zeilen["kostennb"], 25.0, places=2)


class TestSpeicherwegAkte(_Basis):
    """Der Schaden-Endpunkt nimmt die neuen Felder an."""

    def test_kostennb_netto_wird_gespeichert(self):
        from backend.models.schaden import (
            setze_schadenpositionen, hole_schadenpositionen)
        setze_schadenpositionen("589/26", **{
            "abrechnungsart": "fiktiv", "rep_gutachten_netto": 1000.0,
            "kostennb": 29.75, "kostennb_netto": 25.0, "kostennb_ust": 4.75,
        })
        s = hole_schadenpositionen("589/26")
        self.assertAlmostEqual(s.kostennb, 29.75, places=2)
        self.assertAlmostEqual(s.kostennb_netto, 25.0, places=2)
        self.assertAlmostEqual(s.kostennb_ust, 4.75, places=2)
        self.assertAlmostEqual(s.gesamt_brutto, 1029.75, places=2)


class TestUebersichtUndBerichtGleich(_Basis):
    """Ein Modell (DECISIONS 2026-08-26) gilt auch fuer die neue Position."""

    def test_position_erscheint_in_der_ableitung(self):
        from backend.models.schaden import setze_schadenpositionen
        from backend.services.positionsstatus_service import (
            leite_positionsstatus_ab)
        setze_schadenpositionen("589/26", **{
            "abrechnungsart": "fiktiv", "rep_gutachten_netto": 1000.0,
            "kostennb": 29.75, "kostennb_netto": 25.0, "kostennb_ust": 4.75,
        })
        status = leite_positionsstatus_ab("589/26")
        self.assertIn("kostennb", status)
        self.assertAlmostEqual(status["kostennb"]["gefordert"], 29.75, places=2)
        self.assertEqual(status["kostennb"]["label"], "Nachbesichtigungskosten")


if __name__ == "__main__":
    unittest.main()
