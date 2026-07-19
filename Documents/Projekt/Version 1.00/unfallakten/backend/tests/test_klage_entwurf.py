"""
Klage-Wizard Entwurf speichern (Paket 1): GET/PUT/DELETE /akten/<az>/klage/entwurf.
"""
import importlib
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp(prefix="klage_entwurf_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"entwurf_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")

    import backend.db.database as db_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.dokument as dok_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as routes_mod
    import backend.app as app_mod

    for m in (db_mod, ben_mod, akte_mod, dok_mod,
              jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
        importlib.reload(m)

    app = app_mod.erstelle_app({"TESTING": True})
    client = app.test_client()

    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO unfallakte (az, unfalldatum, status) "
            "VALUES ('61/26', '2026-02-01', 'offen')"
        )

    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestKlageEntwurfEndpoints(unittest.TestCase):
    az = "61/26"

    def setUp(self):
        self._alte_db = os.environ.get("DB_PATH")
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def tearDown(self):
        if self._alte_db:
            os.environ["DB_PATH"] = self._alte_db

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_tmp_dir, ignore_errors=True)

    def _put(self, az=None, body=None):
        return self.client.put(
            f"/akten/{az or self.az}/klage/entwurf",
            json=body if body is not None else {
                "entwurf": {"wizardStep": 7, "wizardSachverhaltText": "Text ä ö ü"},
                "format_version": 1,
            },
            headers=self.headers,
        )

    def test_get_ohne_entwurf_404(self):
        r = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r.status_code, 404)

    def test_put_dann_get(self):
        r = self._put()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(r.get_json()["ok"])
        self.assertTrue(r.get_json()["gespeichert_am"])

        r2 = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        d = r2.get_json()
        self.assertEqual(d["format_version"], 1)
        self.assertIn('"wizardStep": 7', d["entwurf_json"])
        self.assertIn("ä ö ü", d["entwurf_json"])
        self.assertTrue(d["gespeichert_am"])

    def test_put_ist_upsert_eine_zeile(self):
        self._put()
        self._put(body={"entwurf": {"wizardStep": 9}, "format_version": 2})
        from backend.db.database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT format_version FROM klage_entwurf WHERE akte_id = ?",
                (self.az,)).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["format_version"], 2)

    def test_put_validierung_422(self):
        self.assertEqual(self._put(body={"format_version": 1}).status_code, 422)
        self.assertEqual(
            self._put(body={"entwurf": "kein-objekt", "format_version": 1}).status_code, 422)
        self.assertEqual(
            self._put(body={"entwurf": {}, "format_version": "1"}).status_code, 422)
        self.assertEqual(
            self._put(body={"entwurf": {}}).status_code, 422)

    def test_az_normalisierung(self):
        r = self._put(az="6126")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        r2 = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r2.status_code, 200)

    def test_unbekannte_akte_404(self):
        r = self._put(az="999/99")
        self.assertEqual(r.status_code, 404)

    def test_delete_idempotent(self):
        self._put()
        r = self.client.delete(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        r2 = self.client.get(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r2.status_code, 404)
        r3 = self.client.delete(f"/akten/{self.az}/klage/entwurf", headers=self.headers)
        self.assertEqual(r3.status_code, 200)


if __name__ == "__main__":
    unittest.main()
