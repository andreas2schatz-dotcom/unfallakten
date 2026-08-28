"""GET /intake/queue liefert Fragebogen-Kennzeichnung, Kopfdaten und Ampel."""
import importlib
import json
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="fbqueue_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BOGEN = {
    "meta": {"formular": "unfallbogen", "version": "2.1"},
    "mandant": {"name": "Golovin", "vorname": "Paul",
                 "email": "paulgolovin@web.de"},
    "gegner": {"fahrzeug": {"kennzeichen": "MTK-DB801"}},
    "unfall": {"datum": "2026-08-03"},
    "sachschaden": {"eigenes_fahrzeug": {"kennzeichen": "WÜ PG 777"}},
}


def _setup(test_id: str):
    """Muster aus backend/tests/test_abschluss_routes.py:12 -- eigener
    DB_PATH je Test, danach die Module neu laden, damit sie ihn sehen."""
    db_path = os.path.join(_tmp_dir, f"fbq_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")
    os.environ["RAMICRO_AKTIV"] = "false"

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


def _auth(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login fehlgeschlagen: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


class TestQueueEndpunkt(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth(self.client)

    def _lege_eintrag(self, payload, klasse, kandidaten):
        from backend.db.database import get_connection
        parse = {"text_gesamt": payload, "felder": {},
                  "akten_kandidaten": kandidaten}
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status, "
                " klasse, klasse_quelle, konfidenz, parse_json) "
                "VALUES (?, 'text', ?, 'bereit_zur_review', ?, ?, 1.0, ?)",
                (f"sha-{klasse}-{len(payload)}", payload, klasse,
                 "fragebogen" if klasse == "fragebogen" else "auto",
                 json.dumps(parse, ensure_ascii=False)))
            return cur.lastrowid

    def _queue(self):
        r = self.client.get("/intake/queue", headers=self.headers)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()["eintraege"]

    def test_fragebogen_traegt_kopf_und_ampel(self):
        self._lege_eintrag(
            json.dumps(BOGEN, ensure_ascii=False), "fragebogen",
            [{"akte_az": "742/26", "score": 0.8, "quelle": "mandanten_mail",
              "treffer": "paulgolovin@web.de",
              "bezeichnung": "Golovin/Brochner"}])
        e = self._queue()[0]
        self.assertTrue(e["ist_fragebogen"])
        self.assertEqual(e["bogen_kopf"]["mandant_name"], "Paul Golovin")
        self.assertEqual(e["bogen_kopf"]["kennzeichen"], "WÜ PG 777")
        self.assertEqual(e["bogen_kopf"]["unfalltag"], "2026-08-03")
        self.assertEqual(e["zuordnung"]["ampel"], "gruen")
        self.assertEqual(e["zuordnung"]["akte_az"], "742/26")
        self.assertEqual(e["zuordnung"]["kurzbezeichnung"], "Golovin/Brochner")
        self.assertEqual(e["zuordnung"]["begruendung"], "Mandanten-E-Mail")

    def test_fragebogen_ohne_kandidat_ist_neu(self):
        self._lege_eintrag(json.dumps(BOGEN, ensure_ascii=False),
                            "fragebogen", [])
        e = self._queue()[0]
        self.assertEqual(e["zuordnung"]["ampel"], "neu")

    def test_bogen_mit_klasse_sonstiges_wird_trotzdem_erkannt(self):
        """W-2-Regression: alle acht echten Boegen tragen in der DB noch
        klasse='sonstiges' (kein Reparse gelaufen). Ein Guard auf
        klasse=='fragebogen' liefert fuer sie ist_fragebogen=False, obwohl
        der Detail-Endpunkt (parse_fragebogen_payload ohne Klassen-Guard)
        fuer dieselbe Zeile True sagt. Die Liste muss payload_typ=='text'
        pruefen und erkenne_fragebogen entscheiden lassen -- unabhaengig
        von der (noch nicht aktualisierten) Klasse."""
        self._lege_eintrag(
            json.dumps(BOGEN, ensure_ascii=False), "sonstiges",
            [{"akte_az": "742/26", "score": 0.8, "quelle": "mandanten_mail",
              "treffer": "paulgolovin@web.de",
              "bezeichnung": "Golovin/Brochner"}])
        e = self._queue()[0]
        self.assertTrue(e["ist_fragebogen"])
        self.assertIsNotNone(e["bogen_kopf"])
        self.assertEqual(e["bogen_kopf"]["mandant_name"], "Paul Golovin")
        self.assertIsNotNone(e["zuordnung"])
        self.assertEqual(e["zuordnung"]["ampel"], "gruen")

    def test_normales_dokument_ohne_bogenfelder(self):
        self._lege_eintrag("Sehr geehrte Damen und Herren", "sonstiges", [])
        e = self._queue()[0]
        self.assertFalse(e["ist_fragebogen"])
        self.assertIsNone(e["bogen_kopf"])
        self.assertIsNone(e["zuordnung"])

    def test_bestehende_felder_bleiben_erhalten(self):
        self._lege_eintrag("Sehr geehrte Damen und Herren", "sonstiges", [])
        e = self._queue()[0]
        for feld in ("id", "klasse", "konfidenz", "queue_status",
                      "erstellt_am", "akte_kandidat_top", "payload_typ"):
            self.assertIn(feld, e)


if __name__ == "__main__":
    unittest.main()
