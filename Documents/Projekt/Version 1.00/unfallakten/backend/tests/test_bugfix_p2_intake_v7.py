"""
Tests fuer die P2-Bugfixes aus docs/BUGFIX_INTAKE_V7.md (Code-Review 2026-07-12).

Abgedeckt:
  * BUG-08 -- Freigabe auf RA-MICRO-only-Akten legt die Akte on-demand in
              SQLite an (statt 404). RA-MICRO bleibt read-only.
  * BUG-09 -- Fristablauf-Job blockiert sich nicht mehr selbst: mehrere
              faellige todos bekommen jeweils ihr Ereignis (kein Write-Lock
              ueber schreibe_ereignis gehalten).
  * BUG-10 -- Scheduler-Lease: nur genau ein Prozess erhaelt den Lease.
  * BUG-11 -- Upload unter Review-Pflicht validiert Datei (Typ/Groesse/
              PDF-Signatur) -> 422 statt 202.
  * BUG-12 -- OCR rendert pro Seite nur DIESE Seite (first_page/last_page),
              nicht das ganze PDF (O(n) statt O(n^2)).
  * BUG-13 -- Migration 50 nutzt kein executescript() und committet explizit.

Muster wie test_bugfix_p1_intake_v7.py: eigene DB je Test, Import der
Produktivmodule INNERHALB der Testmethode (nach DB-Reload).
"""
import ast
import importlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ─── Basis-Klassen (aus test_bugfix_p1_intake_v7.py) ─────────────────────────


class _DBBasis(unittest.TestCase):
    """Frische SQLite-DB je Test (ohne Flask-App)."""

    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p2bug_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass


class _RouteBasis(unittest.TestCase):
    """Flask-App + Test-Client mit Auth (wie test_bugfix_p1_intake_v7)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="p2bug_route_")
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
        for var in ("DB_PATH", "UPLOAD_DIR", "INTAKE_ARTEFAKTE_ROOT"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def _pdf(self):
        import fitz
        doc = fitz.open()
        doc.new_page(width=595, height=842).insert_text(
            (72, 72), "T", fontsize=10)
        return doc.write()

    def _intake(self, klasse, felder, suffix):
        from backend.db.database import get_connection
        pfad = os.path.join(self._uploads, f"a_{suffix}.pdf")
        with open(pfad, "wb") as f:
            f.write(self._pdf())
        sha = (suffix * 64)[:64]
        parse = json.dumps({"felder": felder})
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente (sha256, arbeitskopie_pfad, "
                "queue_status, klasse, parse_json) "
                "VALUES (?, ?, 'bereit_zur_review', ?, ?)",
                (sha, pfad, klasse, parse),
            )
            return cur.lastrowid


# ─── BUG-08: Freigabe auf RA-MICRO-only-Akte ─────────────────────────────────


class TestBug08RamicroOnlyAkte(_RouteBasis):
    def test_freigabe_legt_ramicro_akte_in_sqlite_an(self):
        # '162/26' existiert NICHT in unfallakte (nur '44/22' aus setUp) --
        # simuliert einen Kandidaten, der nur in RA-MICRO (tblAkten) liegt.
        did = self._intake("abrechnungsschreiben", {}, "ramo")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
                             json={"akte_az": "162/26"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT az FROM unfallakte WHERE az='162/26'"
            ).fetchone()
        self.assertIsNotNone(
            row, "RA-MICRO-only-Akte muss beim Freigeben in SQLite angelegt "
                 "werden (RA-MICRO bleibt read-only)")

    def test_verworfenes_dokument_bleibt_gesperrt(self):
        # BUG-08-Fix darf den BUG-06-Guard nicht aufweichen: ein verworfenes
        # Dokument darf auch bei RA-MICRO-only-Akte KEINE Akte anlegen.
        did = self._intake("abrechnungsschreiben", {}, "vsp2")
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET verworfen_am=? WHERE id=?",
                ("2026-07-13T10:00:00+00:00", did))
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
                             json={"akte_az": "999/26"})
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        with get_connection() as conn:
            row = conn.execute(
                "SELECT az FROM unfallakte WHERE az='999/26'").fetchone()
        self.assertIsNone(row, "Verworfenes Dokument darf keine Akte anlegen")


# ─── BUG-09: Fristablauf-Selbstblockade ──────────────────────────────────────


class TestBug09FristablaufKeinLock(_DBBasis):
    def test_zwei_faellige_todos_bekommen_beide_ihr_ereignis(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, status) VALUES ('44/22','offen')")
            for i in range(2):
                conn.execute(
                    "INSERT INTO todos (akte_az, text, faellig_am, quelle, "
                    "erledigt) VALUES ('44/22', ?, date('now','-1 day'), "
                    "'system', 0)",
                    (f"Verjaehrung {i}",))

        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )
        n = verarbeite_faellige_todos()
        self.assertEqual(n, 2, "Beide faelligen todos muessen ihr "
                              "fristablauf-Ereignis bekommen (kein Lock)")

        with get_connection() as conn:
            offene = conn.execute(
                "SELECT COUNT(*) FROM todos WHERE quelle='system' "
                "AND fristablauf_ereignis_id IS NULL").fetchone()[0]
            ev = conn.execute(
                "SELECT COUNT(*) FROM ereignisse WHERE ereignistyp='fristablauf'"
            ).fetchone()[0]
        self.assertEqual(offene, 0, "Kein todo darf ohne Anker zurueckbleiben")
        self.assertEqual(ev, 2, "Es muessen 2 fristablauf-Ereignisse existieren")


# ─── BUG-10: Scheduler-Lease (Single-Process) ────────────────────────────────


class TestBug10SchedulerLease(unittest.TestCase):
    @staticmethod
    def _freier_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        return port

    def test_nur_ein_prozess_erhaelt_den_lease(self):
        os.environ.pop("SCHEDULER_LEASE_DISABLED", None)
        import backend.services.scheduler_lease as lease_mod
        importlib.reload(lease_mod)
        port = self._freier_port()
        try:
            erster = lease_mod.erwirb_scheduler_lease(port=port)
            zweiter = lease_mod.erwirb_scheduler_lease(port=port)
            self.assertTrue(erster, "Erster Aufruf muss den Lease erhalten")
            self.assertFalse(
                zweiter, "Zweiter Aufruf (anderer Worker) darf den Lease NICHT "
                         "erhalten -> Scheduler laeuft nur einmal")
        finally:
            lease_mod.gib_scheduler_lease_frei()


# ─── BUG-11: Upload-Validierung unter Review-Pflicht ─────────────────────────


class TestBug11UploadValidierung(_RouteBasis):
    def _post(self, daten: bytes, name: str):
        h = self._login()
        return self.client.post(
            "/akten/44/22/dokumente", headers=h,
            data={"datei": (io.BytesIO(daten), name), "typ": "sonstiges"},
            content_type="multipart/form-data")

    def test_gefaelschtes_pdf_wird_abgelehnt(self):
        r = self._post(b"KEIN ECHTES PDF", "brief.pdf")
        self.assertEqual(r.status_code, 422, r.get_data(as_text=True))

    def test_leere_datei_wird_abgelehnt(self):
        r = self._post(b"", "leer.pdf")
        self.assertEqual(r.status_code, 422, r.get_data(as_text=True))

    def test_verbotene_endung_wird_abgelehnt(self):
        r = self._post(b"MZ\x90\x00irgendwas", "schadprogramm.exe")
        self.assertEqual(r.status_code, 422, r.get_data(as_text=True))

    def test_zu_grosse_datei_wird_abgelehnt(self):
        import backend.pdf.upload_service as us
        alt = us.MAX_DATEIGROESSE
        us.MAX_DATEIGROESSE = 10
        try:
            r = self._post(self._pdf(), "gross.pdf")
        finally:
            us.MAX_DATEIGROESSE = alt
        self.assertEqual(r.status_code, 422, r.get_data(as_text=True))

    def test_gueltiges_pdf_geht_in_review_queue(self):
        r = self._post(self._pdf(), "ok.pdf")
        self.assertEqual(r.status_code, 202, r.get_data(as_text=True))


# ─── BUG-12: OCR rendert nur die benoetigte Seite ────────────────────────────


class TestBug12OcrLinear(unittest.TestCase):
    def test_ocr_seite_rendert_nur_diese_seite(self):
        import backend.intake.pipeline as pipeline

        class _Bild:
            size = (1000, 1000)

        with mock.patch.object(
            pipeline.ocr_service, "pdf_zu_bildern",
            return_value=[_Bild()],
        ) as m_conv, mock.patch.object(
            pipeline.glm_ocr_service, "glm_ocr_seite", return_value="",
        ), mock.patch.object(
            pipeline.ocr_service, "ocr_seite_daten", return_value=("TEXT", []),
        ):
            text, _ist_bild = pipeline._ocr_seite(b"%PDF-fake", 3, "abc123")

        self.assertEqual(text, "TEXT")
        # Kern-Bug: pro Seite darf nur DIESE Seite gerendert werden, nicht das
        # ganze PDF (sonst O(n^2)). first_page/last_page muessen die Seite
        # eingrenzen.
        _, kwargs = m_conv.call_args
        self.assertEqual(kwargs.get("first_page"), 3,
                         "pdf_zu_bildern muss first_page=Seitennummer setzen")
        self.assertEqual(kwargs.get("last_page"), 3,
                         "pdf_zu_bildern muss last_page=Seitennummer setzen")


# ─── BUG-13: Migration 50 haelt executescript()-Verbotsregel ein ─────────────


class TestBug13Migration50KeinExecutescript(unittest.TestCase):
    def _migration_50_quelltext(self):
        import backend.db.schema_manager as sm
        quelle = os.path.abspath(sm.__file__)
        if quelle.endswith(".pyc"):
            quelle = quelle[:-1]
        with open(quelle, "r", encoding="utf-8") as f:
            baum = ast.parse(f.read(), filename=quelle)
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.FunctionDef)
                    and knoten.name == "_run_migration_50"):
                return knoten
        self.fail("_run_migration_50 nicht gefunden")

    def test_kein_executescript(self):
        fn = self._migration_50_quelltext()
        aufrufe = [
            k for k in ast.walk(fn)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Attribute)
            and k.func.attr == "executescript"
        ]
        self.assertEqual(
            aufrufe, [],
            "Migration 50 darf kein conn.executescript() verwenden "
            "(feedback_migration_executescript).")

    def test_hat_explizite_commits(self):
        fn = self._migration_50_quelltext()
        commits = [
            k for k in ast.walk(fn)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Attribute)
            and k.func.attr == "commit"
        ]
        self.assertTrue(
            commits, "Migration 50 muss explizite conn.commit()-Aufrufe haben.")

    def test_migration_50_legt_unfalldetails_weiterhin_an(self):
        # Verhaltens-Absicherung: der Regelkonformitaets-Umbau darf die
        # Funktion (frische DB: Tabelle + Aktivlegit-Spalten) nicht kaputt
        # machen.
        fd, pfad = tempfile.mkstemp(prefix="mig50_", suffix=".sqlite")
        os.close(fd)
        import sqlite3
        try:
            conn = sqlite3.connect(pfad)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS unfallakte (az TEXT PRIMARY KEY)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                "version INTEGER PRIMARY KEY, beschreibung TEXT)")
            conn.commit()
            import backend.db.schema_manager as sm
            sm._run_migration_50(conn)
            spalten = {r[1] for r in conn.execute(
                "PRAGMA table_info(unfalldetails)").fetchall()}
            self.assertIn("aktivlegitimation_typ", spalten)
            self.assertIn("aktivlegitimation_freigabe", spalten)
            self.assertIn("aktivlegitimation_datum", spalten)
            conn.close()
        finally:
            try:
                os.unlink(pfad)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
