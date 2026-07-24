"""
Tests: REST-Routen /klage-standardtexte (Liste, Override, Reset, Vorschau, aufgeloest)
=======================================================================================
V11 Standardtexte Stufe 1, Task 7.
"""

import importlib
import os
import shutil
import tempfile
import unittest


class _RouteBasis(unittest.TestCase):
    """Flask-App + Test-Client mit Auth (wie test_kuerzungsarten_textbaustein_rest.py)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="standardtexte_route_")
        self._db_pfad = os.path.join(self._tmp, "unfallakten.db")
        os.environ["DB_PATH"] = self._db_pfad

        import backend.db.database as db_mod
        import backend.models.benutzer as ben_mod
        import backend.models.standardtext_override as override_mod
        import backend.auth.jwt_handler as jwt_mod
        import backend.auth.middleware as mw_mod
        import backend.auth.service as svc_mod
        import backend.routers.auth_routes as auth_routes_mod
        import backend.routers.standardtexte_routes as standardtexte_routes_mod
        import backend.app as app_mod
        for m in (db_mod, ben_mod, override_mod, jwt_mod, mw_mod, svc_mod,
                  auth_routes_mod, standardtexte_routes_mod, app_mod):
            importlib.reload(m)

        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()
        self.h = self._login()

    def tearDown(self):
        os.environ.pop("DB_PATH", None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "koch@anwalt-offenbach.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Kanzlei2024!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        token = r.get_json()["access_token"]
        return {"Authorization": f"Bearer {token}"}


class TestStandardtexteRest(_RouteBasis):
    def test_liste_liefert_alle_bausteine(self):
        r = self.client.get("/klage-standardtexte", headers=self.h)
        self.assertEqual(200, r.status_code)
        bausteine = r.get_json()["bausteine"]
        self.assertEqual(44, len(bausteine))
        b = next(x for x in bausteine if x["key"] == "schaden_differenz")
        self.assertEqual("Unfallschaden", b["abschnitt_label"])
        self.assertIsNone(b["override_text"])
        self.assertTrue(any(p["key"] == "KLAGEBETRAG" and p["pflicht"]
                            for p in b["platzhalter"]))

    def test_put_unbekannter_baustein_404(self):
        r = self.client.put("/klage-standardtexte/gibt_es_nicht",
                            json={"text": "X"}, headers=self.h)
        self.assertEqual(404, r.status_code)

    def test_put_unbekannter_platzhalter_422(self):
        r = self.client.put("/klage-standardtexte/schluss_hinweis",
                            json={"text": "Hinweis <FANTASIE>."}, headers=self.h)
        self.assertEqual(422, r.status_code)
        self.assertEqual(["FANTASIE"], r.get_json()["unbekannt"])

    def test_put_pflicht_fehlt_409_dann_bestaetigt_200(self):
        r = self.client.put("/klage-standardtexte/schaden_gesamtbetrag",
                            json={"text": "Ohne Betrag."}, headers=self.h)
        self.assertEqual(409, r.status_code)
        self.assertEqual(["GESAMTSCHADEN"], r.get_json()["fehlend"])
        r = self.client.put("/klage-standardtexte/schaden_gesamtbetrag",
                            json={"text": "Ohne Betrag.", "bestaetigt": True},
                            headers=self.h)
        self.assertEqual(200, r.status_code)

    def test_override_roundtrip_und_aufgeloest(self):
        neu = "Um richterlichen Hinweis wird gebeten."
        r = self.client.put("/klage-standardtexte/schluss_hinweis",
                            json={"text": neu}, headers=self.h)
        self.assertEqual(200, r.status_code)
        liste = self.client.get("/klage-standardtexte", headers=self.h).get_json()
        b = next(x for x in liste["bausteine"] if x["key"] == "schluss_hinweis")
        self.assertEqual(neu, b["override_text"])
        self.assertTrue(b["geaendert_am"])
        texte = self.client.get("/klage-standardtexte/aufgeloest",
                                headers=self.h).get_json()["texte"]
        self.assertEqual(neu, texte["schluss_hinweis"])
        r = self.client.delete("/klage-standardtexte/schluss_hinweis", headers=self.h)
        self.assertEqual(200, r.status_code)
        texte = self.client.get("/klage-standardtexte/aufgeloest",
                                headers=self.h).get_json()["texte"]
        self.assertIn("richterlichen Hinweis gebeten", texte["schluss_hinweis"])

    def test_vorschau_mit_beispielwerten(self):
        r = self.client.post("/klage-standardtexte/vorschau",
                             json={"key": "schaden_gesamtbetrag",
                                   "text": "Betrag: <GESAMTSCHADEN> Ende <TIPPFEHLER>"},
                             headers=self.h)
        self.assertEqual(200, r.status_code)
        v = r.get_json()["vorschau"]
        self.assertIn("5.000,00 €", v)
        self.assertIn("[FEHLT: <TIPPFEHLER>]", v)

    def test_override_wirkt_im_dokument(self):
        neu = "Um richterlichen Hinweis wird ausdruecklich gebeten."
        self.client.put("/klage-standardtexte/schluss_hinweis",
                        json={"text": neu}, headers=self.h)
        from backend.tests.test_klage_service_docx import _akte_daten, _position
        from backend.word.klage_service import baue_klage_vorschau
        res = baue_klage_vorschau(_akte_daten(
            [_position("fahrzeugschaden", "Fahrzeugschaden", 3000.0)]))
        gesamt = "\n".join(a["text"] for a in res["abschnitte"])
        self.assertIn(neu, gesamt)


if __name__ == "__main__":
    unittest.main()
