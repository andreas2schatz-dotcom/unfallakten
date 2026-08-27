"""RA-MICRO-Suche fuer Bogen-Signale. Die Datenbankschicht ist gemockt --
geprueft wird, WELCHE Abfragen mit WELCHEN Werten gestellt werden und wie
die Treffer zurueckkommen. Es wird ausschliesslich gelesen.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Cursor:
    """Minimaler Cursor: liefert je Aufruf die naechste vorbereitete Antwort
    und merkt sich die abgesetzten SQL-Texte samt Parametern."""

    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.aufrufe = []

    def execute(self, sql, params=None):
        self.aufrufe.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.antworten.pop(0) if self.antworten else None

    def fetchall(self):
        return self.antworten.pop(0) if self.antworten else []


def _mock_verbindung(cursor):
    conn = mock.MagicMock()
    conn.cursor.return_value = cursor
    ctx = mock.MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = False
    return ctx


class TestSucheKandidatenInRamicro(unittest.TestCase):
    def _suche(self, merkmale, antworten):
        from backend.ramicro import email_matching
        cur = _Cursor(antworten)
        with mock.patch.object(email_matching, "get_ramicro_connection",
                                return_value=_mock_verbindung(cur)):
            treffer = email_matching.suche_kandidaten_in_ramicro(merkmale)
        return treffer, cur

    def test_mandanten_mail_liefert_treffer(self):
        treffer, cur = self._suche(
            {"mandant_email": "paulgolovin@web.de"},
            [[{"az": "742/26", "bezeichnung": "Golovin/Brochner"}]],
        )
        self.assertEqual(treffer, [("742/26", "mandanten_mail",
                                     "paulgolovin@web.de",
                                     "Golovin/Brochner")])
        sql, params = cur.aufrufe[0]
        self.assertIn("tblAdressen", sql)
        self.assertIn("sAktenKurzBezeichnung", sql)
        self.assertIn("dtAblage", sql)
        self.assertIn("iBeteiligtenArt = 1", sql)
        self.assertEqual(params, ("paulgolovin@web.de",))

    def test_eigenes_kennzeichen_fragt_varM_KZ(self):
        treffer, cur = self._suche(
            {"kfz_mandant": "WÜPG777"},
            [[{"az": "742/26", "bezeichnung": "Golovin/Brochner"}]],
        )
        self.assertEqual(treffer[0][1], "kfz_mandant")
        sql, params = cur.aufrufe[0]
        self.assertIn("_tbl0WDMDaten", sql)
        self.assertEqual(params, ("varM-KZ", "WÜPG777"))

    def test_gegnerkennzeichen_fragt_varG_KZ(self):
        _, cur = self._suche({"kfz_gegner": "MTKDB801"}, [[]])
        sql, params = cur.aufrufe[0]
        self.assertIn("_tbl0WDMDaten", sql)
        self.assertEqual(params, ("varG-KZ", "MTKDB801"))

    def test_unfalltag_wird_ins_ramicro_format_uebersetzt(self):
        _, cur = self._suche({"unfalltag": "2026-08-03"}, [[]])
        sql, params = cur.aufrufe[0]
        self.assertIn("varU-TAG", sql)
        self.assertEqual(params, ("03.08.26%",))

    def test_nachname_wird_gesucht(self):
        treffer, cur = self._suche(
            {"nachname": "Golovin"},
            [[{"az": "742/26", "bezeichnung": "Golovin/Brochner"}]],
        )
        self.assertEqual(treffer[0][1], "nachname")
        sql, params = cur.aufrufe[0]
        self.assertIn("sNachname", sql)
        self.assertIn("iBeteiligtenArt = 1", sql)
        self.assertEqual(params, ("Golovin",))

    def test_mehrere_merkmale_ergeben_mehrere_treffer(self):
        treffer, _ = self._suche(
            {"mandant_email": "harti.clan@freenet.de", "nachname": "Hartmann"},
            [[{"az": "751/26", "bezeichnung": "Hartmann/Guthier"}],
             [{"az": "751/26", "bezeichnung": "Hartmann/Guthier"},
              {"az": "990/26", "bezeichnung": "Hartmann/Weber"}]],
        )
        self.assertIn(("751/26", "mandanten_mail", "harti.clan@freenet.de",
                        "Hartmann/Guthier"), treffer)
        self.assertIn(("990/26", "nachname", "Hartmann", "Hartmann/Weber"),
                       treffer)

    def test_leere_merkmale_fragen_nichts(self):
        treffer, cur = self._suche({}, [])
        self.assertEqual(treffer, [])
        self.assertEqual(cur.aufrufe, [])

    def test_verbindungsfehler_liefert_leere_liste(self):
        from backend.ramicro import email_matching
        from backend.ramicro.connector import RaMicroVerbindungsFehler
        with mock.patch.object(email_matching, "get_ramicro_connection",
                                side_effect=RaMicroVerbindungsFehler("weg")):
            self.assertEqual(
                email_matching.suche_kandidaten_in_ramicro(
                    {"nachname": "Golovin"}),
                [])


class TestFindeKandidatenProduktiveSignalKonstellation(unittest.TestCase):
    """K-1-Regression: in der Produktion legt import_service beim Einliefern
    zuerst ein DUENNES Signal ohne Merkmale an ({"dokument_art":
    "fragebogen"} + optional "az"), die Pipeline haengt das REICHE
    baue_signale()-Dict erst DANACH an (siehe pipeline.py:212). Ein
    finde_kandidaten, das nur das erste 'fragebogen'-Signal auswertet,
    findet in genau dieser -- der einzigen produktiv vorkommenden --
    Reihenfolge nichts. Dieser Test bildet sie nach."""

    def setUp(self):
        import tempfile
        fd, pfad = tempfile.mkstemp(prefix="fbramicro_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        _db.DB_PATH = pfad
        os.environ["DB_PATH"] = pfad
        from backend.db.schema_manager import init_db
        init_db()

        from backend.ramicro import email_matching
        self.akte_patcher = mock.patch.object(
            email_matching, "suche_akte_in_ramicro",
            return_value=(None, None, None))
        self.akte_patcher.start()
        self.addCleanup(self.akte_patcher.stop)

    def test_duennes_signal_zuerst_reiches_danach_liefert_kandidaten(self):
        from backend.intake.akten_matching import finde_kandidaten
        from backend.ramicro import email_matching

        duennes_signal = {"dateiname": "unfallbogen_x.json",
                           "dokument_art": "fragebogen"}
        reiches_signal = {
            "dokument_art": "fragebogen",
            "mandant_email": "paulgolovin@web.de",
            "kfz_mandant": "WUEPG777",
            "unfalltag": "2026-08-03",
        }

        with mock.patch.object(
                email_matching, "suche_kandidaten_in_ramicro",
                return_value=[("742/26", "mandanten_mail",
                                "paulgolovin@web.de", "Golovin/Brochner")],
        ) as mock_suche:
            kandidaten = finde_kandidaten(
                "", [duennes_signal, reiches_signal])

        mock_suche.assert_called_once()
        merkmale = mock_suche.call_args[0][0]
        self.assertEqual(merkmale["mandant_email"], "paulgolovin@web.de")
        self.assertEqual(merkmale["kfz_mandant"], "WUEPG777")
        self.assertEqual(merkmale["unfalltag"], "2026-08-03")

        self.assertEqual(len(kandidaten), 1)
        k = kandidaten[0]
        self.assertEqual(k.akte_az, "742/26")
        self.assertEqual(k.score, 0.8)
        self.assertEqual(k.quelle, "mandanten_mail")
        self.assertEqual(k.treffer, "paulgolovin@web.de")
        self.assertEqual(k.bezeichnung, "Golovin/Brochner")

    def test_nur_duennes_signal_ruft_ramicro_bogensuche_nicht_umsonst_auf(self):
        """Ohne reiches Signal sind alle Merkmale leer -- kein Crash, kein
        Kandidat, aber der Bogen-Modus wird trotzdem erkannt (dokument_art
        gesetzt) und die Suche mit leeren Merkmalen aufgerufen."""
        from backend.intake.akten_matching import finde_kandidaten
        from backend.ramicro import email_matching

        with mock.patch.object(
                email_matching, "suche_kandidaten_in_ramicro",
                return_value=[]) as mock_suche:
            kandidaten = finde_kandidaten(
                "", [{"dateiname": "unfallbogen_x.json",
                      "dokument_art": "fragebogen"}])

        mock_suche.assert_called_once()
        self.assertEqual(kandidaten, [])


if __name__ == "__main__":
    unittest.main()
