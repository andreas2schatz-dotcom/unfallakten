"""
Tests: textbaustein REST-fähig + Platzhalter-Katalog + Vorschau-Endpoint
=========================================================================
Kürzungstaxonomie Phase 1, Task 4.
"""

import importlib
import os
import shutil
import tempfile
import unittest


class _RouteBasis(unittest.TestCase):
    """Flask-App + Test-Client mit Auth (wie test_bugfix_p1_intake_v7.py)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="kuerzung_textbaustein_route_")
        self._db_pfad = os.path.join(self._tmp, "unfallakten.db")
        os.environ["DB_PATH"] = self._db_pfad

        import backend.db.database as db_mod
        import backend.models.benutzer as ben_mod
        import backend.models.kuerzungsart as kart_mod
        import backend.auth.jwt_handler as jwt_mod
        import backend.auth.middleware as mw_mod
        import backend.auth.service as svc_mod
        import backend.routers.auth_routes as auth_routes_mod
        import backend.routers.kuerzungsarten_routes as kuerzung_routes_mod
        import backend.app as app_mod
        for m in (db_mod, ben_mod, kart_mod, jwt_mod, mw_mod, svc_mod,
                  auth_routes_mod, kuerzung_routes_mod, app_mod):
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


class TestTextbausteinRest(_RouteBasis):
    def _liste(self):
        r = self.client.get("/kuerzungsarten", headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()["kuerzungsarten"]

    def test_put_und_get_textbaustein_roundtrip(self):
        r = self.client.put(
            "/kuerzungsarten/1",
            json={"textbaustein": "Die Kürzung der <GUTACHTER>-Sätze ist unbegründet."},
            headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        liste = self._liste()
        eintrag = next(k for k in liste if k["id"] == 1)
        self.assertIn("GUTACHTER", eintrag["textbaustein"])
        self.assertEqual(eintrag["typ_code"], "A04")

    def test_typ_code_nicht_schreibbar(self):
        self.client.put("/kuerzungsarten/1", json={"typ_code": "Z99"},
                         headers=self._auth())
        liste = self._liste()
        eintrag = next(k for k in liste if k["id"] == 1)
        self.assertEqual(eintrag["typ_code"], "A04")

    def test_platzhalter_katalog(self):
        r = self.client.get("/kuerzungsarten/platzhalter", headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        daten = r.get_json()
        keys = {p["key"] for p in daten}
        self.assertTrue({"MANDANT", "GUTACHTER", "VERSICHERER", "AZ"} <= keys)
        for p in daten:
            self.assertTrue(p["beschreibung"])
            self.assertTrue(p["beispiel"])

    def test_vorschau_ersetzt_und_markiert_fehlende(self):
        r = self.client.post(
            "/kuerzungsarten/vorschau",
            json={"text": "Sehr geehrte Damen, <MANDANT> und <UNBEKANNT>."},
            headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        v = r.get_json()["vorschau"]
        self.assertNotIn("<MANDANT>", v)
        self.assertIn("[FEHLT: <UNBEKANNT>]", v)

    def test_post_neue_kuerzungsart_mit_textbaustein(self):
        r = self.client.post(
            "/kuerzungsarten",
            json={"bezeichnung": "Testtyp POST-Baustein",
                  "kategorie": "fahrzeugschaden",
                  "textbaustein": "Neuer Baustein mit <MANDANT>."},
            headers=self._auth())
        self.assertIn(r.status_code, (200, 201))
        eintrag = next(k for k in self._liste()
                       if k["bezeichnung"] == "Testtyp POST-Baustein")
        self.assertEqual(eintrag["textbaustein"], "Neuer Baustein mit <MANDANT>.")


class TestStellungnahmeVorschau(_RouteBasis):
    """Task 11: Baustein-Fallback-Kette + begruendung_roh in der Vorschau."""

    def setUp(self):
        super().setUp()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("INSERT INTO unfallakte (az) VALUES ('971/25')")
            cur = conn.execute(
                "INSERT INTO abrechnungsschreiben "
                "(akte_id, datum, versicherung, gesamt_gefordert, gesamt_reguliert) "
                "VALUES ('971/25', '2026-07-01', 'Allianz', 100.0, 40.0)")
            ab_id = cur.lastrowid
            conn.execute(
                "INSERT INTO regulierung_positionen "
                "(abrechnungsschreiben_id, position_key, betrag_gefordert, "
                " betrag_reguliert, kuerzungsart_id, kuerzung_freitext) "
                "VALUES (?, 'wertminderung', 100.0, 40.0, 2, "
                "'Wertminderung nicht nachvollziehbar.')", (ab_id,))
            conn.execute(
                "UPDATE kuerzungsarten "
                "SET standard_gegenargument='STANDARD-ARGUMENT abweichend.' "
                "WHERE id=2")

    def _setze_textbaustein(self, kid, text):
        r = self.client.put(f"/kuerzungsarten/{kid}",
                            json={"textbaustein": text}, headers=self._auth())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_vorschau_nutzt_textbaustein_vor_standard_gegenargument(self):
        self._setze_textbaustein(2, "BAUSTEIN-TEXT zur Wertminderung")
        r = self.client.get("/akten/971/25/stellungnahme/vorschau",
                            headers=self._auth())
        pos = next(p for p in r.get_json()["positionen"]
                   if p.get("kuerzungsart_id") == 2)
        self.assertIn("BAUSTEIN-TEXT", pos["textbaustein_vorschlag"])

    def test_vorschau_faellt_auf_standard_gegenargument_zurueck(self):
        self._setze_textbaustein(2, "")
        r = self.client.get("/akten/971/25/stellungnahme/vorschau",
                            headers=self._auth())
        pos = next(p for p in r.get_json()["positionen"]
                   if p.get("kuerzungsart_id") == 2)
        self.assertIn("STANDARD-ARGUMENT", pos["textbaustein_vorschlag"])

    def test_vorschau_liefert_begruendung_roh(self):
        r = self.client.get("/akten/971/25/stellungnahme/vorschau",
                            headers=self._auth())
        pos = next(p for p in r.get_json()["positionen"]
                   if p.get("kuerzungsart_id") == 2)
        self.assertEqual(pos["begruendung_roh"],
                         "Wertminderung nicht nachvollziehbar.")

    def test_zitat_platzhalter_wird_ersetzt(self):
        self._setze_textbaustein(
            2, "Die Versicherung meint: <ZITAT> Dem widersprechen wir.")
        r = self.client.get("/akten/971/25/stellungnahme/vorschau",
                            headers=self._auth())
        pos = next(p for p in r.get_json()["positionen"]
                   if p.get("kuerzungsart_id") == 2)
        self.assertIn("Wertminderung nicht nachvollziehbar.",
                      pos["textbaustein_vorschlag"])
        self.assertNotIn("<ZITAT>", pos["textbaustein_vorschlag"])

    def test_zitat_im_platzhalter_katalog(self):
        r = self.client.get("/kuerzungsarten/platzhalter", headers=self._auth())
        keys = {p["key"] for p in r.get_json()}
        self.assertIn("ZITAT", keys)


if __name__ == "__main__":
    unittest.main()
