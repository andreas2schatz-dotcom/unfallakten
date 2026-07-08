"""
End-to-End-Assertion S1.9d (Testkriterium aus dem Pipeline-Plan):

    Kein Codepfad schreibt mehr ohne freigegeben_von in Akten-Tabellen.
    Alle Schreibwege Richtung dokumente / schadenpositionen (K-P1: und
    beteiligte / unfalldetails / personenschaden) aus dem Intake laufen
    ueber den output_adapter.

Test-Strategie: End-to-end den kompletten Intake-Weg durchfahren
(Upload, E-Akte-Import, In-Akte-Klick, Fragebogen-Ergaenzung) und
danach pruefen, dass NIRGENDWO Akten-Tabellen-Zeilen entstanden sind.
Unter dem Flag ist die einzige zulaessige Schreib-Op der output_adapter,
und der laeuft nur ueber ``POST /intake/dokument/<id>/freigabe`` (S1.8).
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from io import BytesIO
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


_tmp_dir = tempfile.mkdtemp(prefix="s19d_e2e_")


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"e2e_{test_id}.db")
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


def _zaehle_akten_tabellen(conn):
    """Zaehlt die Zeilen in allen Akten-Tabellen, die durch Intake-Auto-
    Pfade befuellt werden koennten (K-P1: erweitert)."""
    daten = {}
    for tabelle, wo in (
        ("dokumente",       "akte_id='44/22'"),
        ("schadenpositionen","akte_id='44/22'"),
        ("beteiligte",      "akte_id='44/22'"),
        ("unfalldetails",   "akte_id='44/22'"),
        ("personenschaden", "akte_id='44/22'"),
        ("fragebogen_erstkontakt", "1=1"),
    ):
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {tabelle} WHERE {wo}"
                             ).fetchone()[0]
        except Exception:
            n = 0
        daten[tabelle] = n
    return daten


class TestS19dNoIntakeWrites(unittest.TestCase):
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

    def test_upload_schreibt_nicht_in_akten_tabellen(self):
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

        from backend.db.database import get_connection
        with get_connection() as conn:
            zaehl = _zaehle_akten_tabellen(conn)
        self.assertEqual(zaehl["dokumente"], 0,
                          f"Upload hat dokumente geschrieben: {zaehl}")
        self.assertEqual(zaehl["schadenpositionen"], 0)

    def test_eakte_import_schreibt_nicht_in_akten_tabellen(self):
        pdf_pfad = os.path.join(_tmp_dir, "eakte.pdf")
        with open(pdf_pfad, "wb") as f:
            f.write(_minimal_pdf())
        dok = {
            "dateiname": "eakte.pdf", "orgdatei": "eakte.pdf",
            "anzeigename": "E-Akte", "bemerkung": "E-Akte",
            "dateityp": "pdf",
        }
        with mock.patch(
            "backend.ramicro.eakte_service.hole_eakte_dokument",
            return_value=dok,
        ), mock.patch(
            "backend.ramicro.eakte_service.baue_dateipfad",
            return_value=pdf_pfad,
        ):
            r = self.client.post(
                "/akten/44%2F22/eakte/42/importieren",
                headers=self.headers,
            )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))

        from backend.db.database import get_connection
        with get_connection() as conn:
            zaehl = _zaehle_akten_tabellen(conn)
        self.assertEqual(zaehl["dokumente"], 0,
                          f"E-Akte-Import hat dokumente geschrieben: {zaehl}")

    def test_in_akte_klick_schreibt_nicht_in_akten_tabellen(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO email_import_log "
                "(id, message_id, betreff, absender, empfangen_am, konto, "
                " akte_id, status) "
                "VALUES (1, '<mid1>', 'x', 'test@x', '2026-01-01', 'unfall', "
                "'44/22', 'zugeordnet')"
            )
        r = self.client.post(
            "/email/import/log/1/in-akte",
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))

        with get_connection() as conn:
            zaehl = _zaehle_akten_tabellen(conn)
        self.assertEqual(zaehl["dokumente"], 0)

    def test_fragebogen_verarbeitung_schreibt_nicht_in_akten_tabellen(self):
        """Fragebogen-JSON: _ergaenze_mandant/_gegner/_unfalldetails/
        _personenschaden schreiben unter dem Flag nichts, und
        _speichere_fragebogen_json legt keine dokumente-Zeile an."""
        from backend.email_import.import_service import (
            _ergaenze_mandant, _ergaenze_gegner,
            _ergaenze_unfalldetails, _ergaenze_personenschaden,
            _speichere_fragebogen_json,
        )
        from pathlib import Path

        _ergaenze_mandant("44/22", {"name": "Max", "email": "a@b.de"})
        _ergaenze_gegner("44/22", {"fahrer": "G",
                                    "fahrzeug": {"kennzeichen": "OF-1"}})
        _ergaenze_unfalldetails("44/22", {"datum": "2022-04-27",
                                           "ort": "OF"})
        _ergaenze_personenschaden("44/22", {"verletzungen": "x"})
        _speichere_fragebogen_json("44/22", {"foo": "bar"},
                                     Path(_tmp_dir), bearbeiter_id=1)

        from backend.db.database import get_connection
        with get_connection() as conn:
            zaehl = _zaehle_akten_tabellen(conn)
        self.assertEqual(zaehl["dokumente"], 0,
                          f"Fragebogen-Auto hat dokumente geschrieben: {zaehl}")
        self.assertEqual(zaehl["beteiligte"], 0)
        self.assertEqual(zaehl["unfalldetails"], 0)
        self.assertEqual(zaehl["personenschaden"], 0)


if __name__ == "__main__":
    unittest.main()
