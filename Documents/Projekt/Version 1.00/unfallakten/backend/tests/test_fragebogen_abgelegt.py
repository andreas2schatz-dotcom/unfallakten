"""Rueckfall auf abgelegte Akten.

Findet die regulaere Suche gar nichts, wird einmal ohne Ablage-Filter
nachgesehen -- sonst bekaeme ein Bogen zu einem abgeschlossenen Fall den
Vorschlag "neue Akte anlegen" und erzeugte eine Dublette.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

MERKMALE = {"dokument_art": "fragebogen",
            "mandant_email": "bernd.ruegner@t-online.de",
            "kfz_mandant": "OFBR1612",
            "nachname": "Rügner",
            "unfalltag": "2026-08-06"}


class TestAbgelegtSuche(unittest.TestCase):
    def test_filter_sucht_nur_abgelegte(self):
        from backend.ramicro import email_matching as em
        aufrufe = []

        class _Cur:
            def execute(self, sql, params=None):
                aufrufe.append(" ".join(sql.split()))
            def fetchall(self):
                return [{"az": "749/26", "bezeichnung": "Rügner/Unbekannt",
                          "abgelegt_am": "2026-08-26"}]

        conn = mock.MagicMock()
        conn.cursor.return_value = _Cur()
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = conn
        ctx.__exit__.return_value = False
        with mock.patch.object(em, "get_ramicro_connection", return_value=ctx):
            treffer = em.suche_abgelegte_in_ramicro(MERKMALE)

        self.assertTrue(treffer)
        az, methode, _tr, bez, abgelegt_am = treffer[0]
        self.assertEqual(az, "749/26")
        self.assertEqual(bez, "Rügner/Unbekannt")
        self.assertEqual(abgelegt_am, "2026-08-26")
        self.assertIn("dtAblage IS NOT NULL", aufrufe[0])
        self.assertNotIn("dtAblage IS NULL", aufrufe[0])

    def test_ohne_merkmale_keine_abfrage(self):
        from backend.ramicro import email_matching as em
        with mock.patch.object(em, "get_ramicro_connection") as verbindung:
            self.assertEqual(em.suche_abgelegte_in_ramicro({}), [])
            verbindung.assert_not_called()


class TestRueckfallInFindeKandidaten(unittest.TestCase):
    def _finde(self, regulaer, abgelegt):
        from backend.intake import akten_matching as am
        with mock.patch.object(am, "_suche_in_ramicro", return_value=regulaer), \
             mock.patch("backend.ramicro.email_matching."
                         "suche_abgelegte_in_ramicro", return_value=abgelegt):
            return am.finde_kandidaten("", [MERKMALE])

    def test_rueckfall_nur_wenn_nichts_gefunden(self):
        k = self._finde([], [("749/26", "mandanten_mail",
                               "bernd.ruegner@t-online.de",
                               "Rügner/Unbekannt", "2026-08-26")])
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0].akte_az, "749/26")
        self.assertTrue(k[0].abgelegt)
        self.assertEqual(k[0].abgelegt_am, "2026-08-26")
        self.assertEqual(k[0].bezeichnung, "Rügner/Unbekannt")

    def test_laufende_akte_verdraengt_den_rueckfall(self):
        from backend.intake import akten_matching as am
        from backend.intake.akten_matching import AktenKandidat
        laufend = [AktenKandidat(akte_az="742/26", score=0.8,
                                  quelle="mandanten_mail", treffer="x",
                                  bezeichnung="Golovin/Brochner")]
        with mock.patch.object(am, "_suche_in_ramicro", return_value=laufend), \
             mock.patch("backend.ramicro.email_matching."
                         "suche_abgelegte_in_ramicro") as abgelegt:
            k = am.finde_kandidaten("", [MERKMALE])
            abgelegt.assert_not_called()
        self.assertEqual([x.akte_az for x in k], ["742/26"])
        self.assertFalse(k[0].abgelegt)

    def test_kein_rueckfall_ohne_bogen(self):
        from backend.intake import akten_matching as am
        with mock.patch.object(am, "_suche_in_ramicro", return_value=[]), \
             mock.patch("backend.ramicro.email_matching."
                         "suche_abgelegte_in_ramicro") as abgelegt:
            am.finde_kandidaten("Sehr geehrte Damen und Herren", [])
            abgelegt.assert_not_called()

    def test_dedupliziert_rueckfall_nach_bestem_score_nicht_nach_reihenfolge(self):
        """Punkt 1: bei 749/26 treffen tatsaechlich zwei Wege (Mandanten-
        adresse und Nachname). Die Reihenfolge der Treffer aus RA-MICRO ist
        nicht garantiert score-absteigend -- hier bewusst umgekehrt
        (schwaches Signal zuerst), um 'wer zuerst kommt gewinnt' von
        'bester Score gewinnt' zu unterscheiden."""
        k = self._finde([], [
            ("749/26", "nachname", "Rügner", "Rügner/Unbekannt",
             "2026-08-26"),
            ("749/26", "mandanten_mail", "bernd.ruegner@t-online.de",
             "Rügner/Unbekannt", "2026-08-26"),
        ])
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0].akte_az, "749/26")
        self.assertEqual(k[0].quelle, "mandanten_mail")
        self.assertAlmostEqual(k[0].score, 0.8, places=2)

    def test_schwacher_laufender_kandidat_blockiert_rueckfall_nicht(self):
        """Punkt 3: ein zufaelliger Nachnamens-Treffer (Score 0.4) auf eine
        laufende Akte darf die Erkennung einer abgelegten Akte, die per
        Mandantenadresse perfekt passt, nicht stillschweigend unterdruecken
        -- der Rueckfall muss laufen, solange kein STARKER Kandidat
        vorliegt."""
        from backend.intake import akten_matching as am
        from backend.intake.akten_matching import AktenKandidat
        schwach = [AktenKandidat(akte_az="900/26", score=0.4,
                                  quelle="mandantenname", treffer="Rügner")]
        k = self._finde(schwach, [("749/26", "mandanten_mail",
                                    "bernd.ruegner@t-online.de",
                                    "Rügner/Unbekannt", "2026-08-26")])
        azse = {x.akte_az: x for x in k}
        self.assertIn("900/26", azse)
        self.assertIn("749/26", azse)
        self.assertTrue(azse["749/26"].abgelegt)
        self.assertFalse(azse["900/26"].abgelegt)

    def test_starker_laufender_kandidat_blockiert_rueckfall_weiterhin(self):
        """Gegenprobe zu Punkt 3: ein STARKER laufender Kandidat (Score
        >= STARK_AB) muss den Rueckfall weiterhin unterdruecken."""
        from backend.intake import akten_matching as am
        from backend.intake.akten_matching import AktenKandidat
        stark = [AktenKandidat(akte_az="742/26", score=0.8,
                                quelle="mandanten_mail",
                                treffer="paulgolovin@web.de")]
        with mock.patch.object(am, "_suche_in_ramicro", return_value=stark), \
             mock.patch("backend.ramicro.email_matching."
                         "suche_abgelegte_in_ramicro") as abgelegt:
            k = am.finde_kandidaten("", [MERKMALE])
            abgelegt.assert_not_called()
        self.assertEqual([x.akte_az for x in k], ["742/26"])


class TestAblageDatumWirdZuString(unittest.TestCase):
    """K-1-Regression: RA-MICRO liefert dtAblage als ``datetime.datetime``,
    nicht als String. Ungewandelt bricht ``json.dumps(parse_dict)`` in
    pipeline.py (kein ``default=``) mit TypeError ab -- das Dokument faellt
    in den Fehlerzustand, die Ampel "abgelegt" erscheint nie. Genau das war
    der reale Fall Bogen 672 / Akte 749/26, der Anlass fuer den vierten
    Zustand. Kein bisheriger Mock deckte das ab, weil alle mit fertigen
    ISO-Strings arbeiteten."""

    def test_echtes_datetime_wird_beim_lesen_normalisiert(self):
        import datetime
        from backend.ramicro import email_matching as em

        class _Cur:
            def execute(self, sql, params=None):
                pass
            def fetchall(self):
                return [{"az": "749/26", "bezeichnung": "Rügner/Unbekannt",
                          "abgelegt_am": datetime.datetime(2026, 8, 26, 0, 0)}]

        conn = mock.MagicMock()
        conn.cursor.return_value = _Cur()
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = conn
        ctx.__exit__.return_value = False
        with mock.patch.object(em, "get_ramicro_connection", return_value=ctx):
            treffer = em.suche_abgelegte_in_ramicro(MERKMALE)

        self.assertTrue(treffer)
        abgelegt_am = treffer[0][4]
        self.assertIsInstance(abgelegt_am, str)
        self.assertEqual(abgelegt_am, "2026-08-26")

    def test_nullwert_1899_wird_zu_none(self):
        """RA-MICRO traegt fuer 'nicht abgelegt' den Nullwert 1899-12-30
        ein -- auch als echtes datetime, nicht als String."""
        import datetime
        from backend.ramicro import email_matching as em

        class _Cur:
            def execute(self, sql, params=None):
                pass
            def fetchall(self):
                return [{"az": "742/26", "bezeichnung": "Golovin/Brochner",
                          "abgelegt_am": datetime.datetime(1899, 12, 30, 0, 0)}]

        conn = mock.MagicMock()
        conn.cursor.return_value = _Cur()
        ctx = mock.MagicMock()
        ctx.__enter__.return_value = conn
        ctx.__exit__.return_value = False
        with mock.patch.object(em, "get_ramicro_connection", return_value=ctx):
            treffer = em.suche_abgelegte_in_ramicro(MERKMALE)

        self.assertIsNone(treffer[0][4])

    def test_datetime_durch_die_ganze_kette_bis_ins_json(self):
        """Schickt ein echtes datetime -- so wie RA-MICRO es fuer dtAblage
        liefert -- als (gemockte) SQL-Zeile durch die komplette Kette:
        _suche_bogen_abfragen -> suche_abgelegte_in_ramicro ->
        finde_kandidaten-Rueckfall -> pipeline.verarbeite_dokument ->
        json.dumps(parse_dict). Nur die RA-MICRO-Verbindung ist gemockt
        (Zeile mit echtem datetime), alles darueber laeuft echt. Belegt,
        dass am Ende ein serialisierbarer String im parse_json steht und
        die Pipeline nicht in den Fehlerzustand faellt."""
        import datetime
        import json
        import tempfile

        fd, pfad = tempfile.mkstemp(prefix="fbabgelegt_kette_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        _db.DB_PATH = pfad
        os.environ["DB_PATH"] = pfad
        from backend.db.schema_manager import init_db
        init_db()

        from backend.db.database import get_connection
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status) "
                "VALUES (?, 'text', ?, 'neu')",
                ("sha-kette-abgelegt",
                 '{"meta": {"formular": "unfallbogen", "version": "2.1"}, '
                 '"mandant": {"name": "Rügner", "vorname": "Bernd", '
                 '"email": "bernd.ruegner@t-online.de"}, '
                 '"unfall": {"datum": "2026-08-06"}, '
                 '"sachschaden": {"eigenes_fahrzeug": '
                 '{"kennzeichen": "OF-BR 1612"}}}'))
            intake_id = cur.lastrowid

        from backend.ramicro import email_matching as em

        class _Cur:
            def execute(self, sql, params=None):
                pass
            def fetchall(self):
                return [{"az": "749/26", "bezeichnung": "Rügner/Unbekannt",
                          "abgelegt_am": datetime.datetime(2026, 8, 26, 0, 0)}]

        ramicro_conn = mock.MagicMock()
        ramicro_conn.cursor.return_value = _Cur()
        ramicro_ctx = mock.MagicMock()
        ramicro_ctx.__enter__.return_value = ramicro_conn
        ramicro_ctx.__exit__.return_value = False

        from backend.intake import pipeline
        with mock.patch.object(pipeline, "klassifiziere_stufe2",
                                return_value=("sonstiges", 0.5)), \
             mock.patch.object(pipeline, "extrahiere_felder",
                                return_value={"felder": {}}), \
             mock.patch("backend.intake.akten_matching._suche_in_ramicro",
                         return_value=[]), \
             mock.patch.object(em, "get_ramicro_connection",
                                return_value=ramicro_ctx):
            self.assertTrue(pipeline.verarbeite_dokument(intake_id))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, parse_json FROM intake_dokumente "
                "WHERE id=?", (intake_id,)).fetchone()

        self.assertEqual(row["queue_status"], "bereit_zur_review")
        parse = json.loads(row["parse_json"])
        kandidat = parse["akten_kandidaten"][0]
        self.assertEqual(kandidat["akte_az"], "749/26")
        self.assertTrue(kandidat["abgelegt"])
        self.assertIsInstance(kandidat["abgelegt_am"], str)
        self.assertEqual(kandidat["abgelegt_am"], "2026-08-26")


if __name__ == "__main__":
    unittest.main()
