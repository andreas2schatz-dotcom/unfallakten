"""
Tests fuer die P1-Bugfixes aus docs/BUGFIX_INTAKE_V7.md (Code-Review 2026-07-12).

Abgedeckt:
  * BUG-05 -- Betraege werden nicht mehr verhundertfacht (Dezimalpunkt-Notation
              aus dem LLM-JSON). ``_feld_zu_zahl`` nutzt den format-sicheren
              Helper ``parsers.pdf_utils.parse_betrag``.
  * BUG-06 -- Verworfene / bereits freigegebene Dokumente sind nicht mehr
              freigebbar (HTTP 409 statt stiller Doppel-Wirkung).
  * BUG-07 -- ``_anker_dokument_id`` bezieht sich auf die Freigabe DERSELBEN
              Ziel-Akte, nicht auf die erste Freigabe einer fremden Akte.

Muster wie test_p15e_freigabe_ereignisse.py: eigene DB je Test, Import der
Produktivmodule INNERHALB der Testmethode (nach DB-Reload).
"""
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ─── BUG-05: Betraege werden verhundertfacht ─────────────────────────────────


class TestBug05FeldZuZahl(unittest.TestCase):
    """``_feld_zu_zahl`` ist eine reine Funktion -- keine DB noetig."""

    def setUp(self):
        from backend.services.eingehende_ereignisse import _feld_zu_zahl
        self.f = _feld_zu_zahl

    def test_dezimalpunkt_wird_nicht_verhundertfacht(self):
        # Kern-Bug: LLM liefert '850.00' -> darf NICHT 85000.0 werden.
        self.assertEqual(self.f("850.00"), 850.0)

    def test_deutsche_tausender_notation(self):
        # Format 1: 1.234,56 (Punkt=Tausender, Komma=Dezimal).
        self.assertEqual(self.f("1.234,56"), 1234.56)

    def test_dezimalpunkt_ohne_tausender(self):
        # Format 2: 1234.56 (Punkt=Dezimal).
        self.assertEqual(self.f("1234.56"), 1234.56)

    def test_komma_dezimal_ohne_tausender(self):
        # Format 3: 1011,50 (Komma=Dezimal).
        self.assertEqual(self.f("1011,50"), 1011.5)

    def test_us_tausender_wird_nicht_verhundertfacht(self):
        # 1,234.56 (US-Tausender) ist mit parse_betrag nicht darstellbar ->
        # None (kein Betrag) ist korrekt: lieber keine Zahl als eine falsche
        # (Projekt-Prinzip "nur echte Betraege buchen").
        self.assertIsNone(self.f("1,234.56"))

    def test_reine_ganzzahl(self):
        self.assertEqual(self.f("850"), 850.0)

    def test_int_und_float_passthrough(self):
        self.assertEqual(self.f(850), 850.0)
        self.assertEqual(self.f(850.5), 850.5)

    def test_leer_und_none(self):
        self.assertIsNone(self.f(None))
        self.assertIsNone(self.f(""))
        self.assertIsNone(self.f("   "))


# ─── Basis-Klassen ───────────────────────────────────────────────────────────


class _DBBasis(unittest.TestCase):
    """Frische SQLite-DB je Test (ohne Flask-App)."""

    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p1bug_", suffix=".sqlite")
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
    """Flask-App + Test-Client mit Auth (wie test_p15e_freigabe_ereignisse)."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="p1bug_route_")
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


# ─── BUG-06: Freigabe-Guards ─────────────────────────────────────────────────


class TestBug06FreigabeGuards(_RouteBasis):
    def test_verworfenes_dokument_nicht_freigebbar(self):
        did = self._intake("abrechnungsschreiben", {}, "verw")
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET verworfen_am=?, "
                "verworfen_grund='spam' WHERE id=?",
                ("2026-07-13T10:00:00+00:00", did),
            )
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
                             json={"akte_az": "44/22"})
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'"
            ).fetchone()[0]
        self.assertEqual(n, 0, "Verworfenes Dokument darf keine Akten-Wirkung "
                               "erzeugen")

    def test_bereits_freigegeben_nicht_erneut_freigebbar(self):
        did = self._intake("abrechnungsschreiben", {}, "frei")
        h = self._login()
        body = {"akte_az": "44/22",
                "kandidaten_ereignisse": [{"typ": "abrechnung_eingegangen"}]}
        r1 = self.client.post(f"/intake/dokument/{did}/freigabe",
                              headers=h, json=body)
        self.assertEqual(r1.status_code, 200, r1.get_data(as_text=True))
        r2 = self.client.post(f"/intake/dokument/{did}/freigabe",
                              headers=h, json=body)
        self.assertEqual(r2.status_code, 409, r2.get_data(as_text=True))
        from backend.db.database import get_connection
        with get_connection() as conn:
            nd = conn.execute(
                "SELECT COUNT(*) FROM dokumente WHERE akte_id='44/22'"
            ).fetchone()[0]
            nf = conn.execute(
                "SELECT COUNT(*) FROM freigaben WHERE intake_dokument_id=?",
                (did,),
            ).fetchone()[0]
        self.assertEqual(nd, 1, "Doppel-Submit darf keine zweite dokumente-Zeile "
                               "erzeugen")
        self.assertEqual(nf, 1, "Doppel-Submit darf keine zweite freigaben-Zeile "
                               "erzeugen")

    def test_normale_freigabe_bleibt_moeglich(self):
        did = self._intake("abrechnungsschreiben", {}, "ok")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
                             json={"akte_az": "44/22"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))


# ─── BUG-07: Ereignis-Anker der Ziel-Akte ────────────────────────────────────


class TestBug07AnkerZielakte(_DBBasis):
    def test_anker_nimmt_freigabe_der_zielakte(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, status) VALUES ('100/26','offen')")
            conn.execute(
                "INSERT INTO unfallakte (az, status) VALUES ('200/26','offen')")
            cur = conn.execute(
                "INSERT INTO intake_dokumente (sha256, queue_status) "
                "VALUES (?, 'freigegeben')", ("07" * 32,),
            )
            iid = cur.lastrowid
            # Erst in 100/26 (dokument_id 5), nach Korrektur in 200/26 (dok 9).
            conn.execute(
                "INSERT INTO freigaben (intake_dokument_id, akte_az, dokument_id) "
                "VALUES (?, '100/26', 5)", (iid,))
            conn.execute(
                "INSERT INTO freigaben (intake_dokument_id, akte_az, dokument_id) "
                "VALUES (?, '200/26', 9)", (iid,))

        from backend.routers.intake_routes import _anker_dokument_id
        anker = _anker_dokument_id(iid, 9, akte_az="200/26")
        self.assertEqual(anker, 9,
                         "Anker muss die Freigabe DERSELBEN Ziel-Akte nehmen, "
                         "nicht die erste Freigabe einer fremden Akte")

    def test_anker_faellt_ohne_intake_id_auf_dokument_id_zurueck(self):
        from backend.routers.intake_routes import _anker_dokument_id
        self.assertEqual(_anker_dokument_id(None, 42, akte_az="200/26"), 42)


if __name__ == "__main__":
    unittest.main()
