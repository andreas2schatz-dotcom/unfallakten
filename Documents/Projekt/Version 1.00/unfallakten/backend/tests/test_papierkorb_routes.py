"""Tests fuer GET /intake/papierkorb + POST /intake/dokument/<id>/wiederherstellen."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Fixture-Aufbau (App-Client + Auth-Header + _lege_intake_pdf_an + frische DB)
# aus test_intake_routes.py uebernommen -- dort gibt es keine gemeinsame
# Testbasis-Klasse, jede TestCase baut ueber setUp() mit _setup()/_auth_header()
# ihre eigene frische DB + Client auf (siehe z.B. TestVerwerfen).
from backend.tests.test_intake_routes import (  # type: ignore
    _setup, _auth_header, _lege_intake_pdf_an,
)
from backend.db.database import get_connection


class TestPapierkorb(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_verworfenes_erscheint_im_papierkorb_nicht_in_queue(self):
        did = _lege_intake_pdf_an("p1", queue_status="bereit_zur_review")
        self.client.post(f"/intake/dokument/{did}/verwerfen",
                         json={"grund": "rauschen"}, headers=self.headers)

        q = self.client.get("/intake/queue", headers=self.headers).get_json()
        self.assertNotIn(did, [e["id"] for e in q["eintraege"]])

        p = self.client.get("/intake/papierkorb", headers=self.headers).get_json()
        eintrag = next(e for e in p["eintraege"] if e["id"] == did)
        self.assertEqual(eintrag["verworfen_grund"], "rauschen")
        self.assertIsNotNone(eintrag["verworfen_am"])

    def test_wiederherstellen_holt_zurueck_in_queue(self):
        did = _lege_intake_pdf_an("p2", queue_status="bereit_zur_review")
        self.client.post(f"/intake/dokument/{did}/verwerfen",
                         json={"grund": "rauschen"}, headers=self.headers)

        r = self.client.post(f"/intake/dokument/{did}/wiederherstellen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(r.get_json()["wiederhergestellt"])

        with get_connection() as conn:
            row = conn.execute(
                "SELECT verworfen_am, verworfen_grund FROM intake_dokumente "
                "WHERE id=?", (did,),
            ).fetchone()
        self.assertIsNone(row["verworfen_am"])
        self.assertIsNone(row["verworfen_grund"])

        q = self.client.get("/intake/queue", headers=self.headers).get_json()
        self.assertIn(did, [e["id"] for e in q["eintraege"]])

    def test_wiederherstellen_nicht_verworfenes_409(self):
        did = _lege_intake_pdf_an("p3", queue_status="bereit_zur_review")
        r = self.client.post(f"/intake/dokument/{did}/wiederherstellen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 409)

    def test_wiederherstellen_unbekannt_404(self):
        r = self.client.post("/intake/dokument/999999/wiederherstellen",
                             headers=self.headers)
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
