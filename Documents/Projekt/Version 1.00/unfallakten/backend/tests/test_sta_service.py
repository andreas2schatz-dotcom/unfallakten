"""
Tests fuer backend/services/sta_service.py + sta_routes (PRD-25d).

Abdeckung (STA-Review 2026-08-11):
  * _empfohlene_stufe: Grenzwerte der Eskalationslogik (bisher ungetestet, G-7)
  * generiere_sta_text: Genus-korrekte Schreiben-Referenz (M-2) —
    {Schreiben} = Nominativ/Akkusativ, {SchreibenDativ} = Dativ ("mit ...")
  * analysiere_regulierung: Todo-Vorrang, Fallback, Zaehlung
  * GET /sta/kontext liefert frist_tage der gewaehlten Stufe (G-2)
"""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

_tmp_dir = tempfile.mkdtemp(prefix="sta_tests_")


class _DbFixture(unittest.TestCase):
    """Temporaere SQLite-DB mit vollem Schema (Muster test_fristablauf_service)."""

    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="sta_", suffix=".sqlite")
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

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass


# ── Stufenlogik ────────────────────────────────────────────────────────────────

class TestEmpfohleneStufe(unittest.TestCase):
    def _stufe(self, tage, sta_anzahl):
        from backend.services.sta_service import _empfohlene_stufe
        return _empfohlene_stufe(tage, sta_anzahl)

    def test_erste_sta_kurz_nach_schreiben_ist_stufe_1(self):
        self.assertEqual(self._stufe(tage=14, sta_anzahl=0), 1)

    def test_grenzwert_21_tage_bleibt_stufe_1(self):
        self.assertEqual(self._stufe(tage=21, sta_anzahl=0), 1)

    def test_ueber_21_tage_ohne_sta_ist_stufe_2(self):
        self.assertEqual(self._stufe(tage=22, sta_anzahl=0), 2)

    def test_eine_sta_erzwingt_stufe_2_unabhaengig_von_tagen(self):
        self.assertEqual(self._stufe(tage=0, sta_anzahl=1), 2)

    def test_zwei_stas_und_ueber_42_tage_ist_stufe_3(self):
        self.assertEqual(self._stufe(tage=43, sta_anzahl=2), 3)

    def test_zwei_stas_aber_grenzwert_42_tage_bleibt_stufe_2(self):
        self.assertEqual(self._stufe(tage=42, sta_anzahl=2), 2)

    def test_eine_sta_und_lange_wartezeit_bleibt_stufe_2(self):
        self.assertEqual(self._stufe(tage=100, sta_anzahl=1), 2)


# ── Textgenerierung (Genus M-2) ────────────────────────────────────────────────

def _ls(typ, typ_label, datum_fmt="01.06.2026"):
    return {"typ": typ, "typ_label": typ_label,
            "datum": "2026-06-01", "datum_fmt": datum_fmt, "dok_id": 1}


class TestGeneriereStaText(_DbFixture):
    def _text(self, stufe, kontext):
        from backend.services.sta_service import generiere_sta_text
        return generiere_sta_text(stufe, kontext)

    # Stufe 1: {Schreiben} im Akkusativ ("auf ... hinzuweisen")

    def test_stufe1_forderungsschreiben_neutrum(self):
        text = self._text(1, {"letztes_schreiben":
                              _ls("forderungsschreiben", "Forderungsschreiben")})
        self.assertIn("auf unser Forderungsschreiben vom 01.06.2026", text)

    def test_stufe1_sachstandsanfrage_feminin(self):
        text = self._text(1, {"letztes_schreiben":
                              _ls("sachstandsanfrage", "Sachstandsanfrage")})
        self.assertIn("auf unsere Sachstandsanfrage vom 01.06.2026", text)
        self.assertNotIn("unser Sachstandsanfrage", text)
        self.assertNotIn("mit dem wir", text)
        self.assertIn("womit wir", text)

    # Stufe 2/3: Referenz nach "mit" im Dativ

    def test_stufe2_forderungsschreiben_dativ(self):
        text = self._text(2, {"letztes_schreiben":
                              _ls("forderungsschreiben", "Forderungsschreiben")})
        self.assertIn("mit unserem Forderungsschreiben vom 01.06.2026", text)
        self.assertNotIn("mit unser Forderungsschreiben", text)

    def test_stufe3_sachstandsanfrage_dativ(self):
        text = self._text(3, {"letztes_schreiben":
                              _ls("sachstandsanfrage", "Sachstandsanfrage")})
        self.assertIn("zuletzt mit unserer Sachstandsanfrage vom 01.06.2026", text)

    def test_stufe2_stellungnahme_dativ(self):
        text = self._text(2, {"letztes_schreiben":
                              _ls("stellungnahme", "Stellungnahme")})
        self.assertIn("mit unserer Stellungnahme vom 01.06.2026", text)

    # Fallbacks

    def test_ohne_letztes_schreiben_neutraler_fallback(self):
        self.assertIn("auf unser Schreiben", self._text(1, {}))
        self.assertIn("mit unserem Schreiben", self._text(2, {}))

    def test_mandant_und_frist_werden_ersetzt(self):
        frist = (date.today() + timedelta(days=14)).strftime("%d.%m.%Y")
        text = self._text(1, {"letztes_schreiben":
                              _ls("forderungsschreiben", "Forderungsschreiben"),
                              "mandant_name": "Max Muster"})
        self.assertIn("Max Muster", text)
        self.assertIn(frist, text)
        self.assertNotIn("{", text)


# ── Aktenanalyse ───────────────────────────────────────────────────────────────

def _insert_dok(conn, *, typ, tage_alt, akte_az="44/22"):
    datum = (date.today() - timedelta(days=tage_alt)).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO dokumente (akte_id, typ, dateiname, dateipfad, dateityp, "
        "hochgeladen_am) VALUES (?, ?, 'x.docx', 'x/x.docx', 'docx', ?)",
        (akte_az, typ, datum),
    )
    return int(cur.lastrowid)


class TestAnalysiereRegulierung(_DbFixture):
    def _analyse(self, az="44/22"):
        from backend.services.sta_service import analysiere_regulierung
        return analysiere_regulierung(az)

    def test_fallback_neuestes_ausgehendes_dokument(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            _insert_dok(conn, typ="forderungsschreiben", tage_alt=30)
            conn.execute(
                "INSERT INTO beteiligte (akte_id, rolle, name, vorname, "
                "versicherung, schaden_nr) "
                "VALUES ('44/22', 'gegner', 'Unfallgegner', '', 'HUK', 'S-1'), "
                "       ('44/22', 'mandant', 'Muster', 'Max', NULL, NULL)"
            )

        k = self._analyse()
        self.assertEqual(k["letztes_schreiben"]["typ"], "forderungsschreiben")
        self.assertEqual(k["tage_ohne_antwort"], 30)
        self.assertEqual(k["sta_anzahl"], 0)
        self.assertEqual(k["empfohlene_stufe"], 2)
        self.assertEqual(k["versicherer_name"], "HUK")
        self.assertEqual(k["mandant_name"], "Max Muster")

    def test_offenes_antwort_todo_hat_vorrang_vor_fallback(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            fs_id = _insert_dok(conn, typ="forderungsschreiben", tage_alt=40)
            _insert_dok(conn, typ="sachstandsanfrage", tage_alt=5)
            conn.execute(
                "INSERT INTO todos (akte_az, text, faellig_am, frist_typ, "
                "erledigt, quelle, dok_id, regel_key) "
                "VALUES ('44/22', 'Antwort ausstehend', ?, 'antwort_2w', 0, "
                "'system', ?, ?)",
                ((date.today() - timedelta(days=26)).isoformat(), fs_id,
                 "antwort_2w_{}".format(fs_id)),
            )

        k = self._analyse()
        self.assertEqual(k["letztes_schreiben"]["dok_id"], fs_id)
        self.assertEqual(k["tage_ohne_antwort"], 40)
        self.assertEqual(k["sta_anzahl"], 1)

    def test_leere_akte_liefert_stufe_1_ohne_schreiben(self):
        k = self._analyse()
        self.assertIsNone(k["letztes_schreiben"])
        self.assertEqual(k["sta_anzahl"], 0)
        self.assertEqual(k["empfohlene_stufe"], 1)


# ── Route: frist_tage im Kontext (G-2) ─────────────────────────────────────────

def _setup_client(test_id):
    db_path = os.path.join(_tmp_dir, "sta_routes_{}.db".format(test_id))
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, "uploads_{}".format(test_id))

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
    return app.test_client()


class TestStaKontextRoute(unittest.TestCase):
    def setUp(self):
        self.client = _setup_client(self._testMethodName)
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        assert r.status_code == 200, "Login failed: {}".format(r.get_json())
        self.headers = {"Authorization":
                        "Bearer {}".format(r.get_json()["access_token"])}
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

    def test_kontext_liefert_frist_tage_der_stufe(self):
        r = self.client.get("/akten/44/22/sta/kontext", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["stufe"], 1)
        self.assertEqual(body["frist_tage"], 14)

    def test_kontext_frist_tage_folgt_stufen_parameter(self):
        r = self.client.get("/akten/44/22/sta/kontext?stufe=3",
                            headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["frist_tage"], 5)


if __name__ == "__main__":
    unittest.main()
