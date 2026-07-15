import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="split_routes_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import fitz


def _pdf(n):
    doc = fitz.open()
    for i in range(n):
        doc.new_page().insert_text((72, 72), f"S{i+1}")
    out = doc.tobytes()
    doc.close()
    return out


def _setup(test_id):
    db_path = os.path.join(_tmp, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp, f"up_{test_id}")
    os.environ["INTAKE_ARCHIV_ROOT"] = os.path.join(_tmp, f"arch_{test_id}")

    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    import backend.auth.middleware as mw_mod
    import backend.routers.intake_routes as ir_mod
    import backend.app as app_mod
    for m in (db_mod, sm, mw_mod, ir_mod, app_mod):
        importlib.reload(m)
    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _original(pdf_bytes, queue_status="bereit_zur_review", payload_typ="datei"):
    from backend.intake._persistenz import oder_intake_dokument_fuer_datei
    from backend.db.database import get_connection
    iid, _ = oder_intake_dokument_fuer_datei(pdf_bytes, "pdf")
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET queue_status=?, payload_typ=? WHERE id=?",
            (queue_status, payload_typ, iid))
    return iid


class TestSplitRoutes(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self.id().split(".")[-1])
        self.headers = _auth(self.client)

    def test_split_200_und_teile(self):
        oid = _original(_pdf(5))
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2, 3], [4, 5]]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(r.get_json()["teile"]), 2)

    def test_split_422_ungueltige_gruppen(self):
        oid = _original(_pdf(5))
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2, 3, 4, 5]]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 422)

    def test_split_422_text(self):
        oid = _original(_pdf(3), payload_typ="text")
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2], [3]]},
                             headers=self.headers)
        self.assertEqual(r.status_code, 422)

    def test_split_409_doppelt(self):
        oid = _original(_pdf(4))
        self.client.post(f"/intake/dokument/{oid}/split",
                         json={"gruppen": [[1, 2], [3, 4]]}, headers=self.headers)
        r = self.client.post(f"/intake/dokument/{oid}/split",
                             json={"gruppen": [[1, 2], [3, 4]]}, headers=self.headers)
        self.assertEqual(r.status_code, 409)

    def test_seiten_endpoint(self):
        oid = _original(_pdf(7))
        r = self.client.get(f"/intake/dokument/{oid}/seiten", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["seiten"], 7)

    def test_thumbnail_png(self):
        oid = _original(_pdf(3))
        r = self.client.get(f"/intake/dokument/{oid}/seite/1/thumbnail",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "image/png")

    def test_thumbnail_404_ausserhalb(self):
        oid = _original(_pdf(3))
        r = self.client.get(f"/intake/dokument/{oid}/seite/9/thumbnail",
                            headers=self.headers)
        self.assertEqual(r.status_code, 404)

    def test_thumbnail_422_text(self):
        oid = _original(_pdf(3), payload_typ="text")
        r = self.client.get(f"/intake/dokument/{oid}/seite/1/thumbnail",
                            headers=self.headers)
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
