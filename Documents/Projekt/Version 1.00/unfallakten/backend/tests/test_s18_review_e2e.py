"""
End-to-End Test S1.8: Review-Queue -> Klasse korrigieren -> Re-Parse ->
Akte zuordnen -> Freigabe -> dokumente-Zeile in Akte + freigaben-Eintrag +
korrektur_log-Eintrag + intake_dokumente.queue_status='freigegeben'.

Testkriterium aus PIPELINE-REFACTORING-PLAN.md S1.8 und aus dem
Session-Prompt naechste_session_S1_8_prompt.md.

Der LLM-Klassifikator und die LLM-Extraktion sind gemockt, damit der Test
ohne LM-Studio laeuft.
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def _pdf_aus_text(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    seite = doc.new_page(width=595, height=842)
    seite.insert_text((72, 72), text, fontsize=10)
    return doc.write()


class TestS18ReviewE2E(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="s18_")
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

    def _lege_intake_pdf_an(self, text: str, sha_suffix="e2e"):
        from backend.db.database import get_connection
        pfad = os.path.join(self._uploads, f"arbeit_{sha_suffix}.pdf")
        with open(pfad, "wb") as f:
            f.write(_pdf_aus_text(text))
        sha = (sha_suffix * 64)[:64]
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, queue_status) "
                "VALUES (?, ?, 'neu')",
                (sha, pfad),
            )
            return cur.lastrowid

    def test_e2e_review_bis_freigabe(self):
        """Golden-Path: Abrechnungsschreiben durchlaeuft Queue, Bearbeiter
        korrigiert Klasse+Felder, ordnet Akte zu, gibt frei."""
        from backend.intake.pipeline import verarbeite_dokument
        from backend.db.database import get_connection

        # 1) Golden-File in die Queue setzen und Pipeline durchlaufen lassen.
        fixture = os.path.join(GOLDEN_DIR, "abrechnungsschreiben",
                                "fixture.txt")
        with open(fixture, "r", encoding="utf-8") as f:
            text = f.read()
        # Wir haengen ein Aktenzeichen an, damit akten_matching Score 1.0 liefert.
        text = text + "\nUnser Aktenzeichen: 44/22\n"
        did = self._lege_intake_pdf_an(text, sha_suffix="e2e")

        with mock.patch(
            "backend.services.llm_service.klassifiziere_geschlossen",
            return_value=("sonstiges", 0.3),  # falsch klassifiziert
        ), mock.patch(
            "backend.services.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            self.assertTrue(verarbeite_dokument(did))

        headers = self._login()

        # 2) Queue-Endpoint zeigt das Dokument.
        r = self.client.get("/intake/queue", headers=headers)
        self.assertEqual(r.status_code, 200)
        eintraege = r.get_json()["eintraege"]
        self.assertEqual(len(eintraege), 1)
        self.assertEqual(eintraege[0]["id"], did)
        self.assertEqual(eintraege[0]["klasse"], "sonstiges")

        # 3) Detail zeigt Akten-Kandidat 44/22 (Score 1.0).
        r = self.client.get(f"/intake/dokument/{did}", headers=headers)
        self.assertEqual(r.status_code, 200)
        detail = r.get_json()
        kandidaten = detail["parse"]["akten_kandidaten"]
        self.assertTrue(kandidaten, "Erwarte >=1 Kandidat")
        self.assertEqual(kandidaten[0]["akte_az"], "44/22")

        # 4) Bearbeiter korrigiert Klasse -> Re-Enqueue.
        r = self.client.patch(
            f"/intake/dokument/{did}/klasse",
            json={"klasse": "abrechnungsschreiben"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["queue_status"], "neu")

        # 5) Re-Parse mit neuer (korrekter) Klasse.
        with mock.patch(
            "backend.services.llm_service.klassifiziere_geschlossen",
            return_value=("abrechnungsschreiben", 0.9),
        ), mock.patch(
            "backend.services.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            verarbeite_dokument(did)

        r = self.client.get(f"/intake/dokument/{did}", headers=headers)
        self.assertEqual(r.get_json()["klasse"], "abrechnungsschreiben")

        # 6) Feld-Korrektur -> korrektur_log.
        r = self.client.patch(
            f"/intake/dokument/{did}/felder",
            json={"felder": {
                "gesamtbetrag": {"alt": None, "neu": "4200,00"}
            }},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200)

        # 7) Freigabe an die Akte.
        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"},
            headers=headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        freigabe = r.get_json()
        self.assertIn("dokument_id", freigabe)
        self.assertIn("freigabe_id", freigabe)

        # 8) Assertion: dokumente-Zeile in Akte + freigaben-Eintrag +
        #    intake_dokumente.queue_status='freigegeben' + korrektur_log
        #    enthaelt die Feldaenderung.
        with get_connection() as conn:
            dok = conn.execute(
                "SELECT akte_id, typ, dateiname FROM dokumente WHERE id=?",
                (freigabe["dokument_id"],)
            ).fetchone()
            frg = conn.execute(
                "SELECT intake_dokument_id, akte_az, dokument_id "
                "FROM freigaben WHERE id=?", (freigabe["freigabe_id"],)
            ).fetchone()
            intake = conn.execute(
                "SELECT queue_status FROM intake_dokumente WHERE id=?",
                (did,)
            ).fetchone()
            logs = conn.execute(
                "SELECT feld, wert_neu FROM korrektur_log "
                "WHERE intake_dokument_id=?", (did,)
            ).fetchall()

        self.assertIsNotNone(dok)
        self.assertEqual(dok["akte_id"], "44/22")
        self.assertEqual(dok["typ"], "abrechnungsschreiben")
        self.assertEqual(frg["intake_dokument_id"], did)
        self.assertEqual(frg["akte_az"], "44/22")
        self.assertEqual(frg["dokument_id"], freigabe["dokument_id"])
        self.assertEqual(intake["queue_status"], "freigegeben")

        felder = {r["feld"] for r in logs}
        self.assertIn("klasse", felder)
        self.assertIn("gesamtbetrag", felder)

    def test_freigabe_ohne_akte_422(self):
        did = self._lege_intake_pdf_an("Testtext", sha_suffix="noak")
        # Erst mal bereit_zur_review setzen (manuell, ohne Pipeline).
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET queue_status='bereit_zur_review', "
                "klasse='sonstiges', parse_json='{}' WHERE id=?", (did,)
            )
        headers = self._login()
        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={}, headers=headers,
        )
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
