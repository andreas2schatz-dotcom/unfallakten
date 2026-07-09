"""
End-to-End-Assertion P1.4 (Testkriterium aus dem POSITIONSMODELL-PLAN):

    Jede Generierung erzeugt genau 1 Ereignis mit korrekten Positionen.

Test-Strategie: der Helper ``ausgehende_ereignisse.erzeuge`` ist der
zentrale Weg -- statt jede Route mit ihren echten Word-Vorlagen zu
initialisieren, patchen wir den Helper und pruefen, dass er von den
Generierungs-Stellen wirklich aufgerufen wird.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestGenerierungRuftHelper(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p14e2e_",
                                              suffix=".sqlite")
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

    def test_word_service_forderung_ruft_helper(self):
        """word_service.generiere_und_speichere ruft den Helper mit
        ereignistyp=forderung_generiert. Wir patchen alle Datenpfade auf
        Minimalwerte, damit der Aufrufweg bis zum Helper durchlaeuft."""
        from backend.word import word_service as ws

        with mock.patch.object(ws, "hole_akte_by_id",
                                return_value=mock.MagicMock(aktenzeichen="44/22")), \
             mock.patch.object(ws, "_lade_akte_daten",
                                return_value={"variante": "hoehe",
                                              "schaden": {"reparaturkosten": 5000.0}}), \
             mock.patch.object(ws, "generiere_forderungsschreiben_wv",
                                return_value=b"PK\x03\x04dummy"), \
             mock.patch.object(ws, "registriere_dokument",
                                return_value=mock.MagicMock(
                                    id=1, dateiname="x.docx",
                                    dateityp="docx", dateigroesse=1,
                                    hochgeladen_am="now")), \
             mock.patch.object(ws, "erfasse_forderung"), \
             mock.patch.object(ws, "setze_pflvg_frist"), \
             mock.patch.object(ws, "setze_antwort_frist"), \
             mock.patch(
                 "backend.services.ausgehende_ereignisse.erzeuge"
             ) as mck:
            ws.generiere_und_speichere(
                akte_id="44/22", dok_typ="forderungsschreiben",
                bearbeiter_id=None, in_db=True, variante="hoehe",
            )
            mck.assert_called_once()
            kwargs = mck.call_args.kwargs
            self.assertEqual(kwargs["ereignistyp"], "forderung_generiert")
            self.assertEqual(kwargs["dokument_id"], 1)
            self.assertEqual(kwargs["positionen"],
                              {"reparaturkosten": 5000.0})

    def test_word_service_klage_ruft_helper(self):
        from backend.word import word_service as ws

        with mock.patch.object(ws, "hole_akte_by_id",
                                return_value=mock.MagicMock(aktenzeichen="44/22")), \
             mock.patch.object(ws, "_lade_akte_daten",
                                return_value={"variante": None,
                                              "schaden": {"reparaturkosten": 5000.0}}), \
             mock.patch.object(ws, "generiere_klageschrift",
                                return_value=b"PK\x03\x04dummy"), \
             mock.patch.object(ws, "registriere_dokument",
                                return_value=mock.MagicMock(
                                    id=2, dateiname="k.docx",
                                    dateityp="docx", dateigroesse=1,
                                    hochgeladen_am="now")), \
             mock.patch.object(ws, "setze_antwort_frist"), \
             mock.patch(
                 "backend.services.ausgehende_ereignisse.erzeuge"
             ) as mck:
            ws.generiere_und_speichere(
                akte_id="44/22", dok_typ="klage",
                bearbeiter_id=None, in_db=True,
            )
            mck.assert_called_once()
            self.assertEqual(mck.call_args.kwargs["ereignistyp"],
                              "klage_generiert")

    def test_word_service_sta_ruft_helper(self):
        from backend.word import word_service as ws

        with mock.patch.object(ws, "hole_akte_by_id",
                                return_value=mock.MagicMock(aktenzeichen="44/22")), \
             mock.patch.object(ws, "_lade_akte_daten",
                                return_value={"variante": None}), \
             mock.patch.object(ws, "generiere_sachstandsanfrage",
                                return_value=b"PK\x03\x04"), \
             mock.patch.object(ws, "registriere_dokument",
                                return_value=mock.MagicMock(
                                    id=3, dateiname="s.docx",
                                    dateityp="docx", dateigroesse=1,
                                    hochgeladen_am="now")), \
             mock.patch.object(ws, "setze_antwort_frist"), \
             mock.patch(
                 "backend.services.ausgehende_ereignisse.erzeuge"
             ) as mck:
            ws.generiere_und_speichere(
                akte_id="44/22", dok_typ="sachstandsanfrage",
                bearbeiter_id=None, in_db=True,
            )
            mck.assert_called_once()
            kwargs = mck.call_args.kwargs
            self.assertEqual(kwargs["ereignistyp"],
                              "sachstandsanfrage_generiert")
            self.assertIsNone(kwargs["positionen"])   # Akten-Scope


if __name__ == "__main__":
    unittest.main()
