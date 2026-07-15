"""PRD-37: E-Akte-Dokument traegt bezeichnung + ist nachtraeglich editierbar."""
import importlib
import os
import sys
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="dok_bez_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _client(test_id):
    db = os.path.join(_tmp, f"{test_id}.db")
    if os.path.exists(db):
        os.remove(db)
    os.environ["DB_PATH"] = db
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp, f"up_{test_id}")
    import backend.db.database as db_mod
    import backend.app as app_mod
    for m in (db_mod, app_mod):
        importlib.reload(m)
    return app_mod.erstelle_app({"TESTING": True}).test_client()


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!")})
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestDokumentBezeichnungAkte(unittest.TestCase):
    def test_patch_und_liste(self):
        client = _client("akte")
        h = _auth(client)
        from backend.models.akte import erstelle_oder_hole_akte
        from backend.models.dokument import registriere_dokument
        erstelle_oder_hole_akte("90/26", bearbeiter_id=None)
        dok = registriere_dokument(akte_id="90/26", typ="sonstiges",
                                   dateiname="scan_1.pdf", dateipfad="90_26/scan_1.pdf")
        r = client.patch(f"/akten/90/26/dokumente/{dok.id}/bezeichnung",
                         headers=h, json={"bezeichnung": "Anwaltsschreiben"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["bezeichnung"], "Anwaltsschreiben")
        liste = client.get("/akten/90/26/dokumente", headers=h).get_json()
        treffer = [d for d in liste["dokumente"] if d["id"] == dok.id]
        self.assertEqual(treffer[0]["bezeichnung"], "Anwaltsschreiben")


if __name__ == "__main__":
    unittest.main()
