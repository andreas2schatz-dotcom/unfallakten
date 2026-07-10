"""
N-08 (FREIGABE-NACHTRAG-1): Baseline "Sekunden pro Freigabe".

Zeitstempel Queue-Oeffnung (erstes GET /intake/dokument/<id>) -> Freigabe
wird als korrektur_log-Zeile (feld='sekunden_bis_freigabe') erfasst. Zweck:
Vorher-Baseline fuer die Stufe-2-Entscheidung (Bounding-Boxes/PDF.js).

Testkriterien:
  1) Erstes Detail-Oeffnen setzt intake_dokumente.review_geoeffnet_am.
  2) Erneutes Oeffnen aendert den Zeitstempel NICHT (erstes Anschauen gewinnt).
  3) Freigabe schreibt genau eine korrektur_log-Zeile
     feld='sekunden_bis_freigabe' mit nicht-negativer Zahl.
  4) Freigabe ohne vorheriges Oeffnen (Altbestand) schreibt KEINE
     sekunden_bis_freigabe-Zeile (Best-Effort).
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestN08BaselineFreigabe(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="n08_")
        self._db_pfad = os.path.join(self._tmp, "unfallakten.db")
        self._uploads = os.path.join(self._tmp, "uploads")
        self._artefakte = os.path.join(self._tmp, "artefakte")
        os.makedirs(self._uploads, exist_ok=True)
        os.makedirs(self._artefakte, exist_ok=True)

        os.environ["DB_PATH"] = self._db_pfad
        os.environ["UPLOAD_DIR"] = self._uploads
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._artefakte

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

        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

    def tearDown(self):
        import shutil
        for var in ("DB_PATH", "UPLOAD_DIR", "INTAKE_ARTEFAKTE_ROOT"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        self.assertEqual(r.status_code, 200,
                         f"Login-Fehler: {r.get_data(as_text=True)}")
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def _pdf_aus_text(self, text: str) -> bytes:
        import fitz
        doc = fitz.open()
        seite = doc.new_page(width=595, height=842)
        seite.insert_text((72, 72), text, fontsize=10)
        return doc.write()

    def _lege_intake_pdf_an(self, sha_suffix="n08"):
        from backend.db.database import get_connection
        pfad = os.path.join(self._uploads, f"arbeit_{sha_suffix}.pdf")
        with open(pfad, "wb") as f:
            f.write(self._pdf_aus_text("Testtext"))
        sha = (sha_suffix * 64)[:64]
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, queue_status, klasse, parse_json) "
                "VALUES (?, ?, 'bereit_zur_review', 'sonstiges', '{}')",
                (sha, pfad),
            )
            return cur.lastrowid

    def _review_geoeffnet_am(self, did):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT review_geoeffnet_am FROM intake_dokumente WHERE id=?",
                (did,),
            ).fetchone()
        return row["review_geoeffnet_am"]

    def _sekunden_logs(self, did):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT wert_neu FROM korrektur_log "
                "WHERE intake_dokument_id=? AND feld='sekunden_bis_freigabe'",
                (did,),
            ).fetchall()

    def test_migration_55_spalte_existiert(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            cols = {r[1] for r in conn.execute(
                "PRAGMA table_info(intake_dokumente)").fetchall()}
        self.assertIn("review_geoeffnet_am", cols)

    def test_erstes_oeffnen_setzt_zeitstempel_und_ist_stabil(self):
        did = self._lege_intake_pdf_an("open")
        headers = self._login()

        self.assertIsNone(self._review_geoeffnet_am(did))

        r = self.client.get(f"/intake/dokument/{did}", headers=headers)
        self.assertEqual(r.status_code, 200)
        erst = self._review_geoeffnet_am(did)
        self.assertIsNotNone(erst)

        # Zweites Oeffnen darf den Zeitstempel nicht ueberschreiben.
        r = self.client.get(f"/intake/dokument/{did}", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._review_geoeffnet_am(did), erst)

    def test_freigabe_loggt_sekunden(self):
        did = self._lege_intake_pdf_an("frg")
        headers = self._login()

        # Oeffnen -> Zeitstempel setzen, dann kuenstlich 65s in die
        # Vergangenheit ziehen, damit die Differenz deterministisch > 0 ist.
        self.client.get(f"/intake/dokument/{did}", headers=headers)
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente "
                "SET review_geoeffnet_am=datetime('now','localtime','-65 seconds') "
                "WHERE id=?", (did,),
            )

        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"}, headers=headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        logs = self._sekunden_logs(did)
        self.assertEqual(len(logs), 1, "genau eine sekunden_bis_freigabe-Zeile")
        wert = json.loads(logs[0]["wert_neu"])
        self.assertIsInstance(wert, int)
        self.assertGreaterEqual(wert, 60)

    def test_freigabe_ohne_oeffnen_loggt_nichts(self):
        did = self._lege_intake_pdf_an("noopen")
        headers = self._login()

        # KEIN GET /dokument/<id> -> review_geoeffnet_am bleibt NULL.
        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"}, headers=headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._sekunden_logs(did)), 0)


if __name__ == "__main__":
    unittest.main()
