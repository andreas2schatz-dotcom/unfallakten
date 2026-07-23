"""
Tests: Dokument-Verkettung Abrechnungsschreiben <-> Pruefbericht
==================================================================
Kuerzungstaxonomie Phase 1, Task 7.
"""

import importlib
import os
import shutil
import tempfile
import unittest


class _RouteBasis(unittest.TestCase):
    """Flask-App + Test-Client mit Auth (wie test_kuerzungsarten_textbaustein_rest.py)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="pruefbericht_verkettung_")
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

    def _fixtures(self, pb_pruefdienstleister=None):
        """1 Akte, 2 Abrechnungsschreiben (Datum +-10/+-90 Tage vom
        Pruefbericht-Datum), 1 Pruefbericht. akte_id-Spalten halten das AZ
        direkt (Text) -- FK auf unfallakte(id) existiert nicht wirklich
        (unfallakte hat keine id-Spalte, az ist PK), daher FK aus."""
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("INSERT INTO unfallakte (az) VALUES ('971/25')")
            conn.execute("INSERT INTO unfallakte (az) VALUES ('555/25')")
            cur = conn.execute(
                "INSERT INTO abrechnungsschreiben "
                "(akte_id, datum, versicherung, referenz_nr, gesamt_reguliert) "
                "VALUES ('971/25', '2026-07-11', 'Allianz', 'REF 30.278.811.1', 1000.0)")
            self.ab1_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO abrechnungsschreiben "
                "(akte_id, datum, versicherung, referenz_nr, gesamt_reguliert) "
                "VALUES ('971/25', '2026-04-02', 'Allianz', 'REF 99.999.999.9', 500.0)")
            self.ab2_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO abrechnungsschreiben "
                "(akte_id, datum, versicherung, referenz_nr, gesamt_reguliert) "
                "VALUES ('555/25', '2026-07-05', 'HUK', 'ANDERE AKTE', 200.0)")
            self.ab_fremd_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO pruefberichte (akte_id, datum, schadennummer, pruefdienstleister_id) "
                "VALUES ('971/25', '2026-07-01', '30.278.811.1', ?)",
                (self._dienstleister_id(conn, pb_pruefdienstleister),))
            self.pb_id = cur.lastrowid

    def _dienstleister_id(self, conn, name):
        if not name:
            return None
        row = conn.execute(
            "SELECT id FROM pruefdienstleister WHERE name = ?", (name,)).fetchone()
        return row["id"] if row else None


class TestFindeAbrechnungsKandidaten(_RouteBasis):
    def setUp(self):
        super().setUp()
        self._fixtures()

    def test_eindeutiger_kandidat_ueber_schadennummer(self):
        from backend.services.kuerzungstyp_matching import finde_abrechnungs_kandidaten
        k = finde_abrechnungs_kandidaten("971/25", datum="2026-07-01",
                                         schadennummer="30.278.811.1")
        self.assertEqual(k[0]["abrechnungsschreiben_id"], self.ab1_id)
        self.assertGreater(k[0]["score"], k[1]["score"])

    def test_datumsnaehe_zaehlt(self):
        from backend.services.kuerzungstyp_matching import finde_abrechnungs_kandidaten
        k = finde_abrechnungs_kandidaten("971/25", datum="2026-07-01")
        self.assertEqual(k[0]["abrechnungsschreiben_id"], self.ab1_id)

    def test_andere_akte_nicht_enthalten(self):
        from backend.services.kuerzungstyp_matching import finde_abrechnungs_kandidaten
        k = finde_abrechnungs_kandidaten("971/25", datum="2026-07-01")
        ids = {c["abrechnungsschreiben_id"] for c in k}
        self.assertNotIn(self.ab_fremd_id, ids)

    def test_sortierung_absteigend(self):
        from backend.services.kuerzungstyp_matching import finde_abrechnungs_kandidaten
        k = finde_abrechnungs_kandidaten("971/25", datum="2026-07-01",
                                         schadennummer="30.278.811.1")
        scores = [c["score"] for c in k]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestPruefdienstleisterId(_RouteBasis):
    def test_bekannter_name_liefert_id(self):
        from backend.db.database import get_connection
        from backend.services.kuerzungstyp_matching import _pruefdienstleister_id
        with get_connection() as conn:
            pid = _pruefdienstleister_id(conn, "ControlExpert")
        self.assertIsNotNone(pid)

    def test_unbekannter_name_liefert_none_und_legt_nichts_an(self):
        from backend.db.database import get_connection
        from backend.services.kuerzungstyp_matching import _pruefdienstleister_id
        with get_connection() as conn:
            vorher = conn.execute("SELECT COUNT(*) AS n FROM pruefdienstleister").fetchone()["n"]
            pid = _pruefdienstleister_id(conn, "Voellig Unbekannter Dienstleister GmbH")
            nachher = conn.execute("SELECT COUNT(*) AS n FROM pruefdienstleister").fetchone()["n"]
        self.assertIsNone(pid)
        self.assertEqual(vorher, nachher)

    def test_leerer_name_liefert_none(self):
        from backend.db.database import get_connection
        from backend.services.kuerzungstyp_matching import _pruefdienstleister_id
        with get_connection() as conn:
            self.assertIsNone(_pruefdienstleister_id(conn, None))
            self.assertIsNone(_pruefdienstleister_id(conn, "Unbekannt"))


class TestAutoVerkettungBeimPost(_RouteBasis):
    def setUp(self):
        super().setUp()
        self._fixtures()

    def test_post_verkettet_automatisch_bei_eindeutigem_kandidat(self):
        r = self.client.post(
            "/akten/971/25/pruefberichte",
            json={"datum": "2026-07-01", "schadennummer": "30.278.811.1",
                  "pruefdienstleister": "ControlExpert"},
            headers=self._auth())
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        pb = r.get_json()["pruefbericht"]
        self.assertEqual(pb["abrechnungsschreiben_id"], self.ab1_id)

    def test_post_laesst_null_wenn_mehrdeutig(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT INTO abrechnungsschreiben "
                "(akte_id, datum, versicherung, referenz_nr, gesamt_reguliert) "
                "VALUES ('971/25', '2026-07-11', 'Allianz', 'REF 30.278.811.1', 1000.0)")
        r = self.client.post(
            "/akten/971/25/pruefberichte",
            json={"datum": "2026-07-01", "schadennummer": "30.278.811.1"},
            headers=self._auth())
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        pb = r.get_json()["pruefbericht"]
        self.assertIsNone(pb["abrechnungsschreiben_id"])

    def test_post_setzt_pruefdienstleister_id_bei_bekanntem_namen(self):
        r = self.client.post(
            "/akten/971/25/pruefberichte",
            json={"datum": "2026-07-01", "pruefdienstleister": "DEKRA"},
            headers=self._auth())
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        pb = r.get_json()["pruefbericht"]
        self.assertIsNotNone(pb["pruefdienstleister_id"])

    def test_post_pruefdienstleister_id_none_bei_unbekanntem_namen(self):
        r = self.client.post(
            "/akten/971/25/pruefberichte",
            json={"datum": "2026-07-01", "pruefdienstleister": "Nirgendwo GmbH"},
            headers=self._auth())
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        pb = r.get_json()["pruefbericht"]
        self.assertIsNone(pb["pruefdienstleister_id"])

    def test_post_propagiert_dienstleister_auf_verkettetes_abrechnungsschreiben(self):
        r = self.client.post(
            "/akten/971/25/pruefberichte",
            json={"datum": "2026-07-01", "schadennummer": "30.278.811.1",
                  "pruefdienstleister": "ControlExpert"},
            headers=self._auth())
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        r2 = self.client.get("/akten/971/25/abrechnungen", headers=self._auth())
        ab1 = next(a for a in r2.get_json()["abrechnungen"] if a["id"] == self.ab1_id)
        self.assertIn("pruefdienstleister_id", pb_json := r.get_json()["pruefbericht"])
        self.assertIsNotNone(pb_json["pruefdienstleister_id"])


class TestKandidatenEndpoint(_RouteBasis):
    def setUp(self):
        super().setUp()
        self._fixtures()

    def test_kandidaten_endpoint_liefert_sortierte_liste(self):
        r = self.client.get(
            f"/akten/971/25/pruefberichte/{self.pb_id}/abrechnungs-kandidaten",
            headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        k = r.get_json()["kandidaten"]
        self.assertGreaterEqual(len(k), 2)
        self.assertEqual(k[0]["abrechnungsschreiben_id"], self.ab1_id)

    def test_kandidaten_endpoint_404_bei_unbekanntem_pruefbericht(self):
        r = self.client.get(
            "/akten/971/25/pruefberichte/999999/abrechnungs-kandidaten",
            headers=self._auth())
        self.assertEqual(r.status_code, 404)


class TestPatchVerkettung(_RouteBasis):
    def setUp(self):
        super().setUp()
        self._fixtures(pb_pruefdienstleister="ControlExpert")

    def test_patch_verkettung(self):
        r = self.client.patch(
            f"/akten/971/25/pruefberichte/{self.pb_id}",
            json={"abrechnungsschreiben_id": self.ab1_id}, headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["pruefbericht"]["abrechnungsschreiben_id"], self.ab1_id)

    def test_patch_verkettung_propagiert_pruefdienstleister(self):
        self.client.patch(
            f"/akten/971/25/pruefberichte/{self.pb_id}",
            json={"abrechnungsschreiben_id": self.ab1_id}, headers=self._auth())
        r = self.client.get("/akten/971/25/abrechnungen", headers=self._auth())
        ab1 = next(a for a in r.get_json()["abrechnungen"] if a["id"] == self.ab1_id)
        # Abrechnungsschreiben.as_dict() bietet das Feld aktuell nicht an,
        # daher direkte DB-Pruefung.
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT pruefdienstleister_id FROM abrechnungsschreiben WHERE id = ?",
                (self.ab1_id,)).fetchone()
        self.assertIsNotNone(row["pruefdienstleister_id"])

    def test_patch_unlink(self):
        self.client.patch(
            f"/akten/971/25/pruefberichte/{self.pb_id}",
            json={"abrechnungsschreiben_id": self.ab1_id}, headers=self._auth())
        r = self.client.patch(
            f"/akten/971/25/pruefberichte/{self.pb_id}",
            json={"abrechnungsschreiben_id": None}, headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertIsNone(r.get_json()["pruefbericht"]["abrechnungsschreiben_id"])

    def test_patch_cross_akte_wird_abgelehnt(self):
        r = self.client.patch(
            f"/akten/971/25/pruefberichte/{self.pb_id}",
            json={"abrechnungsschreiben_id": self.ab_fremd_id}, headers=self._auth())
        self.assertIn(r.status_code, (400, 404))

    def test_patch_fehlendes_feld_ist_400(self):
        r = self.client.patch(
            f"/akten/971/25/pruefberichte/{self.pb_id}",
            json={}, headers=self._auth())
        self.assertEqual(r.status_code, 400)

    def test_patch_unbekannter_pruefbericht_404(self):
        r = self.client.patch(
            "/akten/971/25/pruefberichte/999999",
            json={"abrechnungsschreiben_id": self.ab1_id}, headers=self._auth())
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
