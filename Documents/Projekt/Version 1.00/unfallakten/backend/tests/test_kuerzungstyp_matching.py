import importlib
import os
import shutil
import tempfile
import unittest
import unittest.mock


class _DBBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        os.unlink(self._db_pfad)


class TestRegelMatching(_DBBasis):
    def _vorschlaege(self, text, klasse="pruefbericht"):
        from backend.services.kuerzungstyp_matching import schlage_typen_vor
        return schlage_typen_vor(text, dokumentklasse=klasse, llm_fallback=False)

    def test_wortgrenze_kleinteilepauschale_ist_A06_nicht_E06(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kleinteilekostenpauschale in Höhe von 30,00 € wurde gekürzt.")}
        self.assertIn("A06", codes)
        self.assertNotIn("E06", codes)

    def test_kostenpauschale_allein_ist_E06(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kostenpauschale erstatten wir mit 25,00 €.",
            klasse="abrechnungsschreiben")}
        self.assertIn("E06", codes)

    def test_kennzeichen_im_briefkopf_matcht_nicht(self):
        text = "Amtl. Kennzeichen: OF-AB 123\nSchaden-Nr. 4711\n" + "x" * 200
        self.assertEqual(self._vorschlaege(text), [])

    def test_kennzeichen_mit_schilder_kontext_matcht(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kosten für die Erneuerung der Kennzeichen (Schilderkosten) "
            "kürzen wir auf 20,00 €.")}
        self.assertIn("E05b", codes)

    def test_neu_fuer_alt(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Wir nehmen einen Abzug neu für alt in Höhe von 200,00 € vor.")}
        self.assertIn("A07", codes)

    def test_snippet_liefert_begruendung_roh(self):
        v = self._vorschlaege("Vorlauf. " * 30 +
                              "Die Verbringungskosten sind nicht erforderlich. " +
                              "Nachlauf. " * 30)
        treffer = next(x for x in v if x.typ_code == "A02")
        self.assertIn("Verbringungskosten", treffer.snippet)
        self.assertLessEqual(len(treffer.snippet), 260)

    def test_zahlmitteilung_ohne_begruendung_liefert_nichts(self):
        self.assertEqual(
            self._vorschlaege("Verbringungskosten 50,00 €", klasse="gutachten"), [])

    def test_dedup_pro_typ(self):
        v = self._vorschlaege("Verbringung hier. Verbringungskosten dort.")
        self.assertEqual(len([x for x in v if x.typ_code == "A02"]), 1)

    def test_briefkopf_ohne_signal_wird_unterdrueckt(self):
        text = ("Wertminderung\nSchaden-Nr. 4711\nAmtl. Kennzeichen OF-AB 123\n"
                "Sachverhalt: " + "Fahrzeug am Werktag besichtigt. " * 30)
        self.assertGreater(len(text), 600)
        self.assertEqual(self._vorschlaege(text), [])


class TestLlmFallback(_DBBasis):
    def test_fallback_nur_wenn_regeln_leer(self):
        from backend.services import kuerzungstyp_matching as m
        aufrufe = []

        def fake_klassifiziere(labels, text):
            aufrufe.append(labels)
            return ("A02", 0.8)

        with unittest.mock.patch.object(
                m, "_klassifiziere_via_llm", side_effect=fake_klassifiziere):
            v = m.schlage_typen_vor(
                "Die Position wird nicht anerkannt, unklarer Grund.",
                dokumentklasse="pruefbericht", llm_fallback=True)
        self.assertEqual([x.typ_code for x in v], ["A02"])
        self.assertEqual(v[0].quelle, "llm")
        self.assertEqual(len(aufrufe), 1)


class _RouteBasis(unittest.TestCase):
    """Flask-App + Test-Client mit Auth (wie test_pruefbericht_verkettung.py)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="kuerzungstyp_routen_")
        self._db_pfad = os.path.join(self._tmp, "unfallakten.db")
        os.environ["DB_PATH"] = self._db_pfad

        import backend.db.database as db_mod
        import backend.models.benutzer as ben_mod
        import backend.models.abrechnungsschreiben as abr_mod
        import backend.services.kuerzungstyp_matching as match_mod
        import backend.auth.jwt_handler as jwt_mod
        import backend.auth.middleware as mw_mod
        import backend.auth.service as svc_mod
        import backend.routers.auth_routes as auth_routes_mod
        import backend.routers.abrechnungsschreiben_routes as ab_routes_mod
        import backend.app as app_mod
        for m in (db_mod, ben_mod, abr_mod, match_mod, jwt_mod, mw_mod, svc_mod,
                  auth_routes_mod, ab_routes_mod, app_mod):
            importlib.reload(m)
        self._ab_routes_mod = ab_routes_mod

        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()
        self._headers = None

    def tearDown(self):
        os.environ.pop("DB_PATH", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "koch@anwalt-offenbach.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Kanzlei2024!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def _auth(self):
        if self._headers is None:
            self._headers = self._login()
        return self._headers

    def _fixtures(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("INSERT INTO unfallakte (az) VALUES ('971/25')")
            cur = conn.execute(
                "INSERT INTO abrechnungsschreiben "
                "(akte_id, datum, versicherung, gesamt_gefordert, gesamt_reguliert) "
                "VALUES ('971/25', '2026-07-01', 'Allianz', 1000.0, 900.0)")
            self.ab_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO regulierung_positionen "
                "(abrechnungsschreiben_id, position_key, betrag_gefordert, betrag_reguliert) "
                "VALUES (?, 'wertminderung', 100.0, 40.0)", (self.ab_id,))
            self.pos_id = cur.lastrowid

    def _pos_url(self):
        return f"/akten/971/25/abrechnungen/{self.ab_id}/positionen/{self.pos_id}"


class TestPflichtBegruendung(_RouteBasis):
    def setUp(self):
        super().setUp()
        self._fixtures()

    def test_patch_kuerzungsart_ohne_begruendung_400(self):
        r = self.client.patch(self._pos_url(), json={"kuerzungsart_id": 4},
                              headers=self._auth())
        self.assertEqual(r.status_code, 400)

    def test_patch_mit_begruendung_ok_und_typ_quelle(self):
        r = self.client.patch(self._pos_url(), json={
            "kuerzungsart_id": 4,
            "kuerzung_freitext": "Verbringungskosten fallen regional nicht an.",
            "typ_quelle": "regel"}, headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT typ_quelle FROM regulierung_positionen WHERE id = ?",
                (self.pos_id,)).fetchone()
        self.assertEqual(row["typ_quelle"], "regel")

    def test_patch_ohne_typ_quelle_default_manuell(self):
        r = self.client.patch(self._pos_url(), json={
            "kuerzungsart_id": 4,
            "kuerzung_freitext": "Fällt nicht an."}, headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT typ_quelle FROM regulierung_positionen WHERE id = ?",
                (self.pos_id,)).fetchone()
        self.assertEqual(row["typ_quelle"], "manuell")

    def test_patch_mit_vorhandener_begruendung_in_zeile_ok(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE regulierung_positionen SET kuerzung_freitext = 'Bestand.' "
                "WHERE id = ?", (self.pos_id,))
        r = self.client.patch(self._pos_url(), json={"kuerzungsart_id": 4},
                              headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_patch_kuerzungsart_loeschen_ohne_begruendung_ok(self):
        r = self.client.patch(self._pos_url(), json={"kuerzungsart_id": None},
                              headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_patch_leere_begruendung_400(self):
        r = self.client.patch(self._pos_url(), json={
            "kuerzungsart_id": 4, "kuerzung_freitext": "   "},
            headers=self._auth())
        self.assertEqual(r.status_code, 400)


class TestTypVorschlaegeEndpoint(_RouteBasis):
    def setUp(self):
        super().setUp()
        self._fixtures()

    def _lege_pruefbericht_mit_dokument(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            cur = conn.execute(
                "INSERT INTO dokumente (typ, dateiname, dateipfad, akte_id) "
                "VALUES ('sonstiges', 'pb.pdf', '/nicht/vorhanden/pb.pdf', '971/25')")
            self.dok_id = cur.lastrowid
            conn.execute(
                "INSERT INTO pruefberichte (akte_id, datum, abrechnungsschreiben_id, dokument_id) "
                "VALUES ('971/25', '2026-06-25', ?, ?)", (self.ab_id, self.dok_id))

    def test_vorschlaege_aus_verkettetem_pruefbericht(self):
        self._lege_pruefbericht_mit_dokument()
        with unittest.mock.patch.object(
                self._ab_routes_mod, "_dokument_volltext",
                return_value="Die Verbringungskosten werden gekürzt, da nicht erforderlich."):
            r = self.client.get(
                f"/akten/971/25/abrechnungen/{self.ab_id}/typ-vorschlaege",
                headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        daten = r.get_json()
        self.assertEqual(daten["quelle_dokument_id"], self.dok_id)
        codes = {v["typ_code"] for v in daten["vorschlaege"]}
        self.assertIn("A02", codes)
        self.assertEqual(daten["vorschlaege"][0]["quelle"], "regel")

    def test_ohne_dokument_leere_vorschlaege(self):
        r = self.client.get(
            f"/akten/971/25/abrechnungen/{self.ab_id}/typ-vorschlaege",
            headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        daten = r.get_json()
        self.assertEqual(daten["vorschlaege"], [])
        self.assertIsNone(daten["quelle_dokument_id"])

    def test_unbekanntes_abrechnungsschreiben_404(self):
        r = self.client.get(
            "/akten/971/25/abrechnungen/999999/typ-vorschlaege",
            headers=self._auth())
        self.assertEqual(r.status_code, 404)


class TestEreignisBegruendungRoh(_DBBasis):
    def test_ereignis_traegt_begruendung_roh(self):
        from backend.services.eingehende_ereignisse import _regulierungs_wirkungen
        zeilen = _regulierungs_wirkungen([{
            "position_key": "wertminderung", "betrag_gefordert": 100.0,
            "betrag_reguliert": 40.0, "kuerzungsart_id": 2,
            "kuerzung_freitext": "Fällt regional nicht an."}])
        gekuerzt = next(z for z in zeilen if z["wirkung"] == "gekuerzt")
        self.assertEqual(gekuerzt["begruendung_roh"], "Fällt regional nicht an.")
        self.assertEqual(gekuerzt["betrag"], 60.0)

    def test_ablehnung_traegt_begruendung_roh(self):
        from backend.services.eingehende_ereignisse import _regulierungs_wirkungen
        zeilen = _regulierungs_wirkungen([{
            "position_key": "wertminderung", "betrag_gefordert": 100.0,
            "betrag_reguliert": 0.0, "kuerzungsart_id": 2,
            "kuerzung_freitext": "Nicht ersatzfähig."}])
        abgelehnt = next(z for z in zeilen if z["wirkung"] == "abgelehnt")
        self.assertEqual(abgelehnt["begruendung_roh"], "Nicht ersatzfähig.")

    def test_schreibe_ereignis_persistiert_begruendung_roh(self):
        import sqlite3
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("INSERT INTO unfallakte (az) VALUES ('971/25')")
        from backend.services.ereignis_service import schreibe_ereignis
        eid = schreibe_ereignis(
            akte_az="971/25", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2026-07-01",
            positionen=[{"position_key": "wertminderung", "wirkung": "gekuerzt",
                         "betrag": 60.0, "kuerzungsart_id": 2,
                         "begruendung_roh": "Fällt regional nicht an."}])
        conn = sqlite3.connect(self._db_pfad)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT begruendung_roh FROM ereignis_positionen WHERE ereignis_id = ?",
            (eid,)).fetchone()
        conn.close()
        self.assertEqual(row["begruendung_roh"], "Fällt regional nicht an.")


class TestPositionsSynonymik(unittest.TestCase):
    def test_versicherer_synonyme(self):
        from backend.services.kuerzungstyp_matching import normalisiere_positionslabel
        self.assertEqual(normalisiere_positionslabel("Differenzbetrag"), "fahrzeugschaden")
        self.assertEqual(normalisiere_positionslabel("Kostenpauschale"), "kostenpauschale")
        self.assertEqual(normalisiere_positionslabel("Sachverständigenkosten"), "sv_kosten")
        self.assertIsNone(normalisiere_positionslabel("Völlig Unbekanntes"))


if __name__ == "__main__":
    unittest.main()
