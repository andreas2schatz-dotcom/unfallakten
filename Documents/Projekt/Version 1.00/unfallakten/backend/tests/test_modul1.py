"""
Modul 1 – Unit-Tests (finale Version)
=======================================
Jede Testmethode benutzt eine eigene, frische SQLite-Datenbank.
"""

import os
import sys
import unittest
import tempfile

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _ns(test_id: str):
    """Gibt einen frischen Namespace mit neu geladenen Modulen zurück."""
    db_path = os.path.join(_tmp_dir, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.schaden as schaden_mod
    import backend.models.dokument as dok_mod

    for m in (db_mod, sm_mod, ben_mod, akte_mod, schaden_mod, dok_mod):
        importlib.reload(m)

    # Schema sofort erstellen
    sm_mod.create_schema()

    class NS:
        check_schema        = staticmethod(sm_mod.check_schema)
        get_connection      = staticmethod(db_mod.get_connection)
        erstelle_benutzer   = staticmethod(ben_mod.erstelle_benutzer)
        hole_benutzer_by_id = staticmethod(ben_mod.hole_benutzer_by_id)
        hole_benutzer_by_email = staticmethod(ben_mod.hole_benutzer_by_email)
        verify_passwort     = staticmethod(ben_mod.verify_passwort)
        deaktiviere_benutzer= staticmethod(ben_mod.deaktiviere_benutzer)
        erstelle_akte       = staticmethod(akte_mod.erstelle_akte)
        hole_akte_by_id     = staticmethod(akte_mod.hole_akte_by_id)
        hole_akte_by_aktenzeichen = staticmethod(akte_mod.hole_akte_by_aktenzeichen)
        liste_akten         = staticmethod(akte_mod.liste_akten)
        aktualisiere_akte   = staticmethod(akte_mod.aktualisiere_akte)
        loesche_akte        = staticmethod(akte_mod.loesche_akte)
        zaehle_akten_by_status = staticmethod(akte_mod.zaehle_akten_by_status)
        erstelle_beteiligten= staticmethod(schaden_mod.erstelle_beteiligten)
        hole_beteiligte_by_akte = staticmethod(schaden_mod.hole_beteiligte_by_akte)
        aktualisiere_beteiligten = staticmethod(schaden_mod.aktualisiere_beteiligten)
        setze_schadenpositionen = staticmethod(schaden_mod.setze_schadenpositionen)
        hole_schadenpositionen = staticmethod(schaden_mod.hole_schadenpositionen)
        erstelle_regulierung= staticmethod(schaden_mod.erstelle_regulierung)
        hole_regulierungen_by_akte = staticmethod(schaden_mod.hole_regulierungen_by_akte)
        hole_regulierungsstatus = staticmethod(schaden_mod.hole_regulierungsstatus)
        registriere_dokument= staticmethod(dok_mod.registriere_dokument)
        hole_dokumente_by_akte = staticmethod(dok_mod.hole_dokumente_by_akte)
        aktualisiere_parse_status = staticmethod(dok_mod.aktualisiere_parse_status)
        logge_aktivitaet    = staticmethod(dok_mod.logge_aktivitaet)
        hole_aktivitaeten   = staticmethod(dok_mod.hole_aktivitaeten)

    return NS()


class TestDatenbankSetup(unittest.TestCase):

    def test_schema_ok(self):
        f = _ns("db_setup_ok")
        status = f.check_schema()
        self.assertTrue(status["ok"])

    def test_alle_tabellen(self):
        f = _ns("db_setup_tbl")
        for tbl, ok in f.check_schema()["tabellen"].items():
            self.assertTrue(ok, f"Tabelle fehlt: {tbl}")

    def test_alle_views(self):
        f = _ns("db_setup_views")
        for v, ok in f.check_schema()["views"].items():
            self.assertTrue(ok, f"View fehlt: {v}")

    def test_foreign_keys_aktiv(self):
        f = _ns("db_fk")
        with f.get_connection() as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_wal_modus(self):
        f = _ns("db_wal")
        with f.get_connection() as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")

    def test_schema_idempotent(self):
        f = _ns("db_idem")
        import importlib
        import backend.db.schema_manager as sm
        importlib.reload(sm)
        sm.create_schema()  # zweiter Aufruf
        self.assertTrue(f.check_schema()["ok"])


class TestBenutzer(unittest.TestCase):

    def test_erstellen(self):
        f = _ns("ben_erstell")
        b = f.erstelle_benutzer("Hans", "hans@k.de", "pw!", "sachbearbeiter")
        self.assertIsNotNone(b.id)
        self.assertTrue(b.aktiv)

    def test_admin_rolle(self):
        f = _ns("ben_admin")
        b = f.erstelle_benutzer("Admin", "a@k.de", "pw!", "admin")
        self.assertEqual(b.rolle, "admin")

    def test_ungueltige_rolle(self):
        f = _ns("ben_rolle")
        with self.assertRaises(ValueError):
            f.erstelle_benutzer("X", "x@x.de", "pw", rolle="god")

    def test_doppelte_email(self):
        f = _ns("ben_dup")
        f.erstelle_benutzer("A", "dup@k.de", "pw!")
        with self.assertRaises(ValueError):
            f.erstelle_benutzer("B", "dup@k.de", "pw!")

    def test_passwort_korrekt(self):
        f = _ns("ben_pw1")
        f.erstelle_benutzer("X", "x@k.de", "Sicher123!")
        _, pw_hash = f.hole_benutzer_by_email("x@k.de")
        self.assertTrue(f.verify_passwort("Sicher123!", pw_hash))

    def test_passwort_falsch(self):
        f = _ns("ben_pw2")
        f.erstelle_benutzer("X", "x@k.de", "Sicher123!")
        _, pw_hash = f.hole_benutzer_by_email("x@k.de")
        self.assertFalse(f.verify_passwort("FalschesPasswort", pw_hash))

    def test_by_id(self):
        f = _ns("ben_byid")
        b = f.erstelle_benutzer("Test", "t@k.de", "pw!")
        self.assertEqual(f.hole_benutzer_by_id(b.id).email, "t@k.de")

    def test_nicht_vorhanden_none(self):
        f = _ns("ben_none")
        self.assertIsNone(f.hole_benutzer_by_id(99999))

    def test_deaktivierung(self):
        f = _ns("ben_deak")
        b = f.erstelle_benutzer("D", "d@k.de", "pw!")
        f.deaktiviere_benutzer(b.id)
        self.assertIsNone(f.hole_benutzer_by_id(b.id))

    def test_email_case_insensitive(self):
        f = _ns("ben_case")
        f.erstelle_benutzer("C", "case@k.de", "pw!")
        self.assertIsNotNone(f.hole_benutzer_by_email("CASE@K.DE"))


class TestUnfallakte(unittest.TestCase):

    def test_erstellen(self):
        f = _ns("akte_erstell")
        a = f.erstelle_akte("1/25", "2025-01-01", unfallort="Offenbach")
        self.assertIsNotNone(a.id)
        self.assertEqual(a.status, "offen")
        self.assertEqual(a.haftungsquote, 100.0)

    def test_doppeltes_aktenzeichen(self):
        f = _ns("akte_dup")
        f.erstelle_akte("25-DUP", "2025-01-01")
        with self.assertRaises(ValueError):
            f.erstelle_akte("25-DUP", "2025-01-01")

    def test_leeres_aktenzeichen(self):
        f = _ns("akte_leer")
        with self.assertRaises(ValueError):
            f.erstelle_akte("", "2025-01-01")

    def test_ungueltige_haftungsquote(self):
        f = _ns("akte_hq")
        with self.assertRaises(ValueError):
            f.erstelle_akte("AZ-X", "2025-01-01", haftungsquote=150.0)

    def test_by_aktenzeichen(self):
        f = _ns("akte_byaz")
        f.erstelle_akte("25-SUCH", "2025-01-01")
        a = f.hole_akte_by_aktenzeichen("25-SUCH")
        self.assertIsNotNone(a)

    def test_status_update(self):
        f = _ns("akte_stat")
        a = f.erstelle_akte("25-S", "2025-01-01")
        upd = f.aktualisiere_akte(a.id, status="in_regulierung")
        self.assertEqual(upd.status, "in_regulierung")

    def test_ungueltiger_status(self):
        f = _ns("akte_bstat")
        a = f.erstelle_akte("25-BS", "2025-01-01")
        with self.assertRaises(ValueError):
            f.aktualisiere_akte(a.id, status="ungueltig")

    def test_loeschen_cascade(self):
        f = _ns("akte_del")
        a = f.erstelle_akte("25-DEL", "2025-01-01")
        f.erstelle_beteiligten(a.id, "mandant", "Testperson")
        f.loesche_akte(a.id)
        self.assertEqual(len(f.hole_beteiligte_by_akte(a.id)), 0)

    def test_filter_status(self):
        f = _ns("akte_filt")
        a1 = f.erstelle_akte("25-F1", "2025-01-01")
        a2 = f.erstelle_akte("25-F2", "2025-01-01")
        f.aktualisiere_akte(a2.id, status="abgeschlossen")
        offene = [a.aktenzeichen for a in f.liste_akten(status="offen")]
        self.assertIn("25-F1", offene)
        self.assertNotIn("25-F2", offene)

    def test_statistik(self):
        f = _ns("akte_stats")
        f.erstelle_akte("25-ST1", "2025-01-01")
        f.erstelle_akte("25-ST2", "2025-01-01")
        stats = f.zaehle_akten_by_status()
        self.assertGreaterEqual(stats.get("offen", 0), 2)

    def test_aktivitaet_bei_erstellung(self):
        f = _ns("akte_act")
        a = f.erstelle_akte("25-ACT", "2025-01-01")
        aktionen = [x.aktion for x in f.hole_aktivitaeten(a.id)]
        self.assertIn("akte_erstellt", aktionen)


class TestBeteiligte(unittest.TestCase):

    def test_erstellen(self):
        f = _ns("bet_erstell")
        a = f.erstelle_akte("AZ", "2025-01-01")
        b = f.erstelle_beteiligten(a.id, "mandant", "Müller", vorname="Max")
        self.assertEqual(b.vollstaendiger_name, "Max Müller")

    def test_alle_rollen_erlaubt(self):
        f = _ns("bet_rollen")
        a = f.erstelle_akte("AZ", "2025-01-01")
        for r in ["mandant", "gegner", "zeuge", "sachverstaendiger", "sonstiger"]:
            f.erstelle_beteiligten(a.id, r, f"Person_{r}")
        alle = f.hole_beteiligte_by_akte(a.id)
        self.assertEqual(len(alle), 5)

    def test_ungueltige_rolle(self):
        f = _ns("bet_inv")
        a = f.erstelle_akte("AZ", "2025-01-01")
        with self.assertRaises(ValueError):
            f.erstelle_beteiligten(a.id, "richter", "X")

    def test_filter_rolle(self):
        f = _ns("bet_filt")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.erstelle_beteiligten(a.id, "mandant", "A")
        f.erstelle_beteiligten(a.id, "gegner", "B")
        m = f.hole_beteiligte_by_akte(a.id, rolle="mandant")
        self.assertEqual(len(m), 1)

    def test_aktualisieren(self):
        f = _ns("bet_upd")
        a = f.erstelle_akte("AZ", "2025-01-01")
        b = f.erstelle_beteiligten(a.id, "zeuge", "Alt")
        upd = f.aktualisiere_beteiligten(b.id, name="Neu")
        self.assertEqual(upd.name, "Neu")


class TestSchadenpositionen(unittest.TestCase):

    def test_setzen(self):
        f = _ns("scp_set")
        a = f.erstelle_akte("AZ", "2025-01-01")
        sp = f.setze_schadenpositionen(a.id, reparaturkosten=5000.0)
        self.assertEqual(sp.reparaturkosten, 5000.0)

    def test_gesamt_summe(self):
        f = _ns("scp_sum")
        a = f.erstelle_akte("AZ", "2025-01-01")
        sp = f.setze_schadenpositionen(
            a.id, reparaturkosten=5000, sv_kosten=800,
            nutzungsausfall=400, wertminderung=200
        )
        self.assertAlmostEqual(sp.gesamt_brutto, 6400.0)

    def test_restwert_abgezogen(self):
        f = _ns("scp_rest")
        a = f.erstelle_akte("AZ", "2025-01-01")
        sp = f.setze_schadenpositionen(a.id, wiederbeschaffung=15000, restwert=3000)
        self.assertAlmostEqual(sp.gesamt_brutto, 12000.0)

    def test_update_ueberschreibt(self):
        f = _ns("scp_upd")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.setze_schadenpositionen(a.id, reparaturkosten=5000)
        f.setze_schadenpositionen(a.id, reparaturkosten=6000)
        self.assertEqual(f.hole_schadenpositionen(a.id).reparaturkosten, 6000)

    def test_alle_felder(self):
        f = _ns("scp_all")
        a = f.erstelle_akte("AZ", "2025-01-01")
        sp = f.setze_schadenpositionen(
            a.id, reparaturkosten=1000, wertminderung=100,
            nutzungsausfall=200, mietwagenkosten=150,
            sv_kosten=300, abschleppkosten=80, standkosten=50,
            anabmeldekosten=53.50, sonstiges=66.50
        )
        self.assertAlmostEqual(sp.gesamt_brutto, 2000.0)


class TestRegulierung(unittest.TestCase):

    def test_teilregulierung(self):
        f = _ns("reg_teil")
        a = f.erstelle_akte("AZ", "2025-01-01")
        r = f.erstelle_regulierung(a.id, "2025-02-01", 8000, 6000)
        self.assertEqual(r.status, "teilreguliert")
        self.assertAlmostEqual(r.differenz, 2000.0)

    def test_vollregulierung(self):
        f = _ns("reg_voll")
        a = f.erstelle_akte("AZ", "2025-01-01")
        r = f.erstelle_regulierung(a.id, "2025-02-01", 8000, 8000)
        self.assertEqual(r.status, "vollreguliert")

    def test_vollreg_schliesst_akte(self):
        f = _ns("reg_close")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.erstelle_regulierung(a.id, "2025-02-01", 8000, 8000)
        self.assertEqual(f.hole_akte_by_id(a.id).status, "abgeschlossen")

    def test_teilreg_setzt_in_regulierung(self):
        f = _ns("reg_inreg")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.erstelle_regulierung(a.id, "2025-02-01", 8000, 4000)
        self.assertEqual(f.hole_akte_by_id(a.id).status, "in_regulierung")

    def test_negativer_betrag_fehler(self):
        f = _ns("reg_neg")
        a = f.erstelle_akte("AZ", "2025-01-01")
        with self.assertRaises(ValueError):
            f.erstelle_regulierung(a.id, "2025-02-01", 8000, -100)

    def test_status_view(self):
        f = _ns("reg_view")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.erstelle_regulierung(a.id, "2025-02-01", 8000, 5000)
        s = f.hole_regulierungsstatus(a.id)
        self.assertAlmostEqual(s["betrag_reguliert"], 5000.0)

    def test_vers_referenz(self):
        f = _ns("reg_ref")
        a = f.erstelle_akte("AZ", "2025-01-01")
        r = f.erstelle_regulierung(a.id, "2025-02-01", 8000, 7000,
                                    vers_referenz="HUK-123")
        self.assertEqual(r.vers_referenz, "HUK-123")


class TestDokumenteUndAktivitaeten(unittest.TestCase):

    def test_dokument_registrieren(self):
        f = _ns("dok_reg")
        a = f.erstelle_akte("AZ", "2025-01-01")
        d = f.registriere_dokument(a.id, "gutachten", "G.pdf", "uploads/G.pdf")
        self.assertEqual(d.parse_status, "ausstehend")

    def test_parse_status_update(self):
        f = _ns("dok_parse")
        a = f.erstelle_akte("AZ", "2025-01-01")
        d = f.registriere_dokument(a.id, "gutachten", "G.pdf", "uploads/G.pdf")
        upd = f.aktualisiere_parse_status(
            d.id, "erfolgreich",
            parse_json='{"rep": 5000}', parse_konfidenz=0.92
        )
        self.assertEqual(upd.parse_status, "erfolgreich")
        self.assertAlmostEqual(upd.parse_konfidenz, 0.92)

    def test_ungueltiger_typ_fehler(self):
        f = _ns("dok_invtyp")
        a = f.erstelle_akte("AZ", "2025-01-01")
        with self.assertRaises(ValueError):
            f.registriere_dokument(a.id, "rechnung", "X.pdf", "X.pdf")

    def test_filter_nach_typ(self):
        f = _ns("dok_filt")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.registriere_dokument(a.id, "gutachten", "G.pdf", "g.pdf")
        f.registriere_dokument(a.id, "klage", "K.docx", "k.docx", dateityp="docx")
        self.assertEqual(len(f.hole_dokumente_by_akte(a.id, typ="gutachten")), 1)

    def test_aktivitaet_loggen(self):
        f = _ns("dok_akt")
        a = f.erstelle_akte("AZ", "2025-01-01")
        akt = f.logge_aktivitaet("test", "Testbeschreibung", akte_id=a.id)
        self.assertIsNotNone(akt.id)

    def test_aktivitaeten_feed(self):
        f = _ns("dok_feed")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.logge_aktivitaet("aktion_1", "Erster Eintrag", a.id)
        f.logge_aktivitaet("aktion_2", "Zweiter Eintrag", a.id)
        alle = f.hole_aktivitaeten(a.id)
        self.assertGreaterEqual(len(alle), 2)

    def test_upload_erzeugt_aktivitaet(self):
        f = _ns("dok_upact")
        a = f.erstelle_akte("AZ", "2025-01-01")
        f.registriere_dokument(a.id, "abrechnungsschreiben", "A.pdf", "a.pdf")
        aktionen = [x.aktion for x in f.hole_aktivitaeten(a.id)]
        self.assertIn("dokument_hochgeladen", aktionen)

    def test_alle_dokumenttypen(self):
        f = _ns("dok_alltyp")
        a = f.erstelle_akte("AZ", "2025-01-01")
        typen = ["gutachten", "abrechnungsschreiben", "forderungsschreiben",
                 "sachstandsanfrage", "klage", "sonstiges"]
        for typ in typen:
            ext = "docx" if typ not in ("gutachten", "abrechnungsschreiben", "sonstiges") else "pdf"
            f.registriere_dokument(a.id, typ, f"x.{ext}", f"x.{ext}", dateityp=ext)
        self.assertEqual(len(f.hole_dokumente_by_akte(a.id)), len(typen))


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestDatenbankSetup, TestBenutzer, TestUnfallakte,
        TestBeteiligte, TestSchadenpositionen,
        TestRegulierung, TestDokumenteUndAktivitaeten,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
