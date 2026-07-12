"""P1.5e — Review-Freigabe erzeugt Ereignisse fuer alle Klassen."""
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _HelperBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15e_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, typ) VALUES ('44/22', 'd.pdf', 'x', 'pdf', 'gutachten')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _dok_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='d.pdf'"
            ).fetchone()["id"]

    def _positionen(self, eid):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT position_key, wirkung, betrag FROM ereignis_positionen "
                "WHERE ereignis_id=? ORDER BY position_key", (eid,)
            ).fetchall()

    def _kopf(self, eid):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT ereignistyp, herkunft FROM ereignisse WHERE id=?",
                (eid,)
            ).fetchone()


class TestErzeugeAusFreigabe(_HelperBasis):
    def test_gutachten_positionen_gefordert(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="gutachten_eingegangen", klasse="gutachten",
            felder={"reparaturkosten_netto": "6.200,00",
                    "wertminderung": "500,00"},
            datum="2022-04-30",
        )
        self.assertIsInstance(eid, int)
        rows = self._positionen(eid)
        keys = {r["position_key"] for r in rows}
        self.assertEqual(keys, {"reparaturkosten", "wertminderung"})
        for r in rows:
            self.assertEqual(r["wirkung"], "gefordert")
        betraege = {r["position_key"]: r["betrag"] for r in rows}
        self.assertEqual(betraege["reparaturkosten"], 6200.0)
        self.assertEqual(betraege["wertminderung"], 500.0)
        self.assertEqual(self._kopf(eid)["herkunft"], "freigabe")

    def test_rechnung_beleg_position_aus_mapping(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="rechnung_eingegangen", klasse="abschlepprechnung",
            felder={"bruttobetrag": "350,00"}, datum="2022-05-01",
        )
        rows = self._positionen(eid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["position_key"], "abschleppkosten")
        self.assertEqual(rows[0]["wirkung"], "beleg")
        self.assertEqual(rows[0]["betrag"], 350.0)

    def test_abrechnung_ist_fakt_ohne_positionen(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={"bruttobetrag": "1.000,00"}, datum="2022-05-01",
        )
        self.assertIsInstance(eid, int)
        self.assertEqual(len(self._positionen(eid)), 0)

    def test_rechnung_ohne_mapping_ist_fakt(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="rechnung_eingegangen", klasse="rechnung",
            felder={"bruttobetrag": "80,00"}, datum="2022-05-01",
        )
        self.assertIsInstance(eid, int)
        self.assertEqual(len(self._positionen(eid)), 0)

    def test_doppelerfassungs_guard(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        from backend.db.database import get_connection
        did = self._dok_id()
        e1 = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=did,
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={}, datum="2022-05-01",
        )
        e2 = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=did,
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={}, datum="2022-05-02",
        )
        self.assertEqual(e1, e2)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse WHERE dokument_id=? "
                "AND ereignistyp='abrechnung_eingegangen'", (did,)
            ).fetchone()[0]
        self.assertEqual(n, 1)


# ─── Teil B: HTTP-E2E ueber POST /intake/dokument/<id>/freigabe ──────────────

class _RouteBasis(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="p15e_route_")
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
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def _pdf(self):
        import fitz
        doc = fitz.open()
        doc.new_page(width=595, height=842).insert_text((72, 72), "T", fontsize=10)
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

    def _ereignisse(self, ereignistyp):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id, herkunft, quelle FROM ereignisse WHERE ereignistyp=?",
                (ereignistyp,),
            ).fetchall()


class TestFreigabeRouteE2E(_RouteBasis):
    def test_gutachten_schreibt_ereignis_mit_positionen(self):
        did = self._intake("gutachten",
                            {"reparaturkosten_netto": "6.200,00"}, "gut")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "gutachten_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        evs = self._ereignisse("gutachten_eingegangen")
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["herkunft"], "freigabe")
        self.assertEqual(evs[0]["quelle"], "dokument")
        from backend.db.database import get_connection
        with get_connection() as conn:
            pos = conn.execute(
                "SELECT position_key FROM ereignis_positionen WHERE ereignis_id=?",
                (evs[0]["id"],),
            ).fetchall()
        keys = {r["position_key"] for r in pos}
        self.assertIn("reparaturkosten", keys)

    def test_abschlepprechnung_schreibt_beleg(self):
        did = self._intake("abschlepprechnung", {"bruttobetrag": "350,00"}, "abs")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "rechnung_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("rechnung_eingegangen")), 1)

    def test_abrechnung_fakt_ohne_positionen(self):
        did = self._intake("abrechnungsschreiben", {}, "abr")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "abrechnung_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("abrechnung_eingegangen")), 1)

    def test_pruefbericht_fakt(self):
        did = self._intake("pruefbericht", {}, "prf")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "pruefbericht_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("pruefbericht_eingegangen")), 1)

    def test_fallback_ohne_kandidaten_nutzt_registry_default(self):
        did = self._intake("gutachten", {"reparaturkosten_netto": "6.200,00"}, "fb")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("gutachten_eingegangen")), 1)

    def test_detail_liefert_default_ereignistyp(self):
        did = self._intake("abschlepprechnung", {}, "det")
        h = self._login()
        r = self.client.get(f"/intake/dokument/{did}", headers=h)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["default_ereignistyp"],
                         "rechnung_eingegangen")

    def test_re_freigabe_kein_duplikat(self):
        did = self._intake("abrechnungsschreiben", {}, "dup")
        h = self._login()
        body = {"akte_az": "44/22",
                "kandidaten_ereignisse": [{"typ": "abrechnung_eingegangen"}]}
        self.client.post(f"/intake/dokument/{did}/freigabe", headers=h, json=body)
        self.client.post(f"/intake/dokument/{did}/freigabe", headers=h, json=body)
        self.assertEqual(len(self._ereignisse("abrechnung_eingegangen")), 1)
