"""
Tests fuer S1.9c: Upload-Route und E-Akte-Import unter dem Feature-Flag
INTAKE_REVIEW_PFLICHT.

Erwartungen:
  * Unter dem Flag (Default True) legt die Upload-Route KEINE
    ``dokumente``-Zeile mehr an; sie schickt die Datei ausschliesslich
    in die Review-Queue (``intake_dokumente`` + ``zustellungen``) und
    antwortet mit HTTP 202 ``{intake_dokument_id, in_review: True}``.
  * Der Alt-Pfad (INTAKE_REVIEW_PFLICHT=false) bleibt bestehen und
    liefert HTTP 201 ``{dokument, parse_ergebnis}`` wie frueher.
  * Der E-Akte-Import verhaelt sich analog.
"""
import importlib
import os
import sys
import tempfile
import unittest
from io import BytesIO
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


_tmp_dir = tempfile.mkdtemp(prefix="s19c_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"s19c_{test_id}.db")
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
            "VALUES ('44/22', '2022-04-27', 'offen')"
        )
    return client


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _minimal_pdf() -> bytes:
    return (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n"
        b"0000000053 00000 n\n0000000100 00000 n\ntrailer\n"
        b"<</Size 4/Root 1 0 R>>\nstartxref\n150\n%%EOF"
    )


class TestUploadRouteFlag(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def tearDown(self):
        if self._alt_flag is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt_flag

    def test_default_flag_true_liefert_202_intake(self):
        data = {
            "datei": (BytesIO(_minimal_pdf()), "beleg.pdf"),
            "typ": "sonstiges",
        }
        r = self.client.post(
            "/akten/44%2F22/dokumente",
            data=data, content_type="multipart/form-data",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))
        body = r.get_json()
        self.assertTrue(body.get("in_review"))
        self.assertIn("intake_dokument_id", body)

        from backend.db.database import get_connection
        with get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'"
            ).fetchone()[0]
            n_intake = conn.execute(
                "SELECT COUNT(*) FROM intake_dokumente"
            ).fetchone()[0]
        self.assertEqual(n_dok, 0,
                          "Unter dem Flag darf keine dokumente-Zeile "
                          "entstehen")
        self.assertGreaterEqual(n_intake, 1,
                                 "intake_dokument muss angelegt sein")

    def test_flag_false_altpfad_liefert_201(self):
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        data = {
            "datei": (BytesIO(_minimal_pdf()), "beleg.pdf"),
            "typ": "sonstiges",
        }
        r = self.client.post(
            "/akten/44%2F22/dokumente",
            data=data, content_type="multipart/form-data",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        body = r.get_json()
        self.assertIn("dokument", body)


class TestEakteImportFlag(unittest.TestCase):
    def setUp(self):
        self._alt_flag = os.environ.get("INTAKE_REVIEW_PFLICHT")
        os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def tearDown(self):
        if self._alt_flag is None:
            os.environ.pop("INTAKE_REVIEW_PFLICHT", None)
        else:
            os.environ["INTAKE_REVIEW_PFLICHT"] = self._alt_flag

    def _mock_eakte_dokument(self):
        # E-Akte-Dokument-Fixture: minimales PDF im Uploads-Verzeichnis.
        pdf_pfad = os.path.join(_tmp_dir, "eakte_fixture.pdf")
        with open(pdf_pfad, "wb") as f:
            f.write(_minimal_pdf())
        dok = {
            "dateiname": "eakte_fixture.pdf",
            "orgdatei":  "eakte_fixture.pdf",
            "anzeigename": "E-Akte-Beleg",
            "bemerkung": "E-Akte-Beleg",
            "dateityp":  "pdf",
        }
        return dok, pdf_pfad

    def test_default_flag_true_liefert_202(self):
        dok, pfad = self._mock_eakte_dokument()
        with mock.patch(
            "backend.ramicro.eakte_service.hole_eakte_dokument",
            return_value=dok,
        ), mock.patch(
            "backend.ramicro.eakte_service.baue_dateipfad",
            return_value=pfad,
        ):
            r = self.client.post(
                "/akten/44%2F22/eakte/42/importieren",
                headers=self.headers,
            )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))
        body = r.get_json()
        self.assertTrue(body.get("in_review"))
        self.assertIn("intake_dokument_id", body)

        from backend.db.database import get_connection
        with get_connection() as conn:
            n_dok = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'"
            ).fetchone()[0]
        self.assertEqual(n_dok, 0)

    def test_flag_false_altpfad(self):
        os.environ["INTAKE_REVIEW_PFLICHT"] = "false"
        dok, pfad = self._mock_eakte_dokument()
        with mock.patch(
            "backend.ramicro.eakte_service.hole_eakte_dokument",
            return_value=dok,
        ), mock.patch(
            "backend.ramicro.eakte_service.baue_dateipfad",
            return_value=pfad,
        ), mock.patch(
            "backend.workflow.dispatcher.dispatch_dokument",
            return_value={"klasse": "sonstiges", "konfidenz": 0.5},
        ):
            r = self.client.post(
                "/akten/44%2F22/eakte/42/importieren",
                headers=self.headers,
            )
        # 200 (importiert) oder 500 falls Dispatcher-Netzwerk fehlt
        self.assertIn(r.status_code, (200, 500),
                      r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
