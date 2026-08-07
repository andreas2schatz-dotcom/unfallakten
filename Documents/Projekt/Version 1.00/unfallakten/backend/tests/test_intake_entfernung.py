"""
Tests fuer POST /intake/dokument/<id>/entfernung (Paket 2, Befund 1280/25).

Entfernungspruefung Referenzwerkstatt aus der ReviewQueue: Werkstatt aus
parse_json.felder.referenzwerkstatt, Mandanten-Adresse aus dem uebergebenen
Akten-Kandidaten (akte_az), pruefe_entfernung ist gemockt (kein echter
ORS-Call). Setup-Muster wie test_intake_routes.py (bewusst dupliziert).
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

_tmp_dir = tempfile.mkdtemp(prefix="intake_entfernung_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ie_{test_id}.db")
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
    return app.test_client()


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


REFERENZWERKSTATT = {
    "name": "Möser Arno - Karosseriefachbetrieb",
    "adresse": "Philipp-Reis-Straße 9",
    "plz_ort": "63128 Dietzenbach",
    "telefon": "06074-25936",
    "km_genannt": 16.0,
    "quelle": "vhv_block",
}


def _lege_pruefbericht_an(referenzwerkstatt=REFERENZWERKSTATT):
    from backend.db.database import get_connection
    felder = {"vorgangsnummer": "SD1"}
    if referenzwerkstatt is not None:
        felder["referenzwerkstatt"] = dict(referenzwerkstatt)
    parse_json = json.dumps({"text_gesamt": "Prüfbericht ...",
                             "felder": felder,
                             "akten_kandidaten": []}, ensure_ascii=False)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO intake_dokumente "
            "(sha256, klasse, klasse_quelle, konfidenz, queue_status, "
            " parse_json, registry_version) "
            "VALUES (?, 'pruefbericht', 'auto', 0.9, 'bereit_zur_review', ?, 'v1')",
            (("e" * 64), parse_json),
        )
        return cur.lastrowid


def _seed_akte_mit_mandant(az="1280/25"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2025-11-01', 'offen')", (az,))
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, anschrift, plz, ort) "
            "VALUES (?, 'mandant', 'Mustermann', 'Andréstr. 10', '63067', 'Offenbach')",
            (az,))


ORS_OK = {
    "ok": True,
    "mandant_adresse": "Andréstr. 10, 63067 Offenbach",
    "werkstatt_adresse": "Philipp-Reis-Straße 9, 63128 Dietzenbach",
    "werkstatt_name": "Möser Arno - Karosseriefachbetrieb",
    "km_genannt": 16.0,
    "km_echt": 24.3,
    "minuten": 31,
    "abweichung_km": 8.3,
    "unzumutbar": True,
    "textbaustein": "Den dortigen Verweis ...",
    "fehler": None,
}


class TestEntfernung(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.h = _auth_header(self.client)

    def _post(self, intake_id, body):
        return self.client.post(
            f"/intake/dokument/{intake_id}/entfernung",
            json=body, headers=self.h)

    def _felder_aus_db(self, intake_id):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json FROM intake_dokumente WHERE id=?",
                (intake_id,)).fetchone()
        return json.loads(row["parse_json"])["felder"]

    def test_ohne_akte_az_400(self):
        dok_id = _lege_pruefbericht_an()
        r = self._post(dok_id, {})
        self.assertEqual(r.status_code, 400)

    def test_unbekanntes_dokument_404(self):
        r = self._post(99999, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 404)

    def test_ohne_referenzwerkstatt_422(self):
        dok_id = _lege_pruefbericht_an(referenzwerkstatt=None)
        _seed_akte_mit_mandant()
        r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 422)

    def test_werkstatt_adresse_unvollstaendig_422(self):
        dok_id = _lege_pruefbericht_an(
            referenzwerkstatt={"name": "Nur Name", "adresse": "",
                               "plz_ort": "", "telefon": "",
                               "km_genannt": None, "quelle": "triggerkontext"})
        _seed_akte_mit_mandant()
        r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 422)

    def test_mandant_nicht_gefunden_404(self):
        dok_id = _lege_pruefbericht_an()
        with mock.patch(
            "backend.routers.distanz_routes._mandant_adresse",
            return_value=None,
        ):
            r = self._post(dok_id, {"akte_az": "777/77"})
        self.assertEqual(r.status_code, 404)

    def test_erfolg_persistiert_ergebnis(self):
        dok_id = _lege_pruefbericht_an()
        _seed_akte_mit_mandant()
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=dict(ORS_OK),
        ) as m:
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        daten = r.get_json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["km_echt"], 24.3)
        self.assertEqual(daten["referenzwerkstatt"]["bewertung"], "unzumutbar")
        kwargs = m.call_args.kwargs
        self.assertEqual(kwargs["mandant_adresse"],
                         "Andréstr. 10, 63067 Offenbach")
        self.assertEqual(kwargs["werkstatt_adresse"],
                         "Philipp-Reis-Straße 9, 63128 Dietzenbach")
        self.assertEqual(kwargs["km_genannt"], 16.0)
        ws = self._felder_aus_db(dok_id)["referenzwerkstatt"]
        self.assertEqual(ws["km_echt"], 24.3)
        self.assertEqual(ws["minuten"], 31)
        self.assertEqual(ws["abweichung_km"], 8.3)
        self.assertEqual(ws["bewertung"], "unzumutbar")
        self.assertEqual(ws["textbaustein"], "Den dortigen Verweis ...")
        self.assertEqual(ws["geprueft_gegen_akte"], "1280/25")
        self.assertTrue(ws.get("geprueft_am"))
        self.assertEqual(ws["name"], REFERENZWERKSTATT["name"])
        self.assertEqual(ws["quelle"], "vhv_block")

    def test_zumutbar_speichert_keinen_textbaustein(self):
        dok_id = _lege_pruefbericht_an()
        _seed_akte_mit_mandant()
        zumutbar = dict(ORS_OK, km_echt=9.8, unzumutbar=False,
                        abweichung_km=-6.2)
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=zumutbar,
        ):
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        ws = self._felder_aus_db(dok_id)["referenzwerkstatt"]
        self.assertEqual(ws["bewertung"], "zumutbar")
        self.assertEqual(ws["textbaustein"], "")

    def test_ors_fehler_persistiert_nicht(self):
        dok_id = _lege_pruefbericht_an()
        _seed_akte_mit_mandant()
        fehl = dict(ORS_OK, ok=False, km_echt=None,
                    fehler="Werkstatt-Adresse konnte nicht geocodiert werden")
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=fehl,
        ):
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["ok"])
        ws = self._felder_aus_db(dok_id)["referenzwerkstatt"]
        self.assertNotIn("km_echt", ws)
        self.assertNotIn("bewertung", ws)

    def test_km_genannt_als_string_wird_konvertiert(self):
        dok_id = _lege_pruefbericht_an(
            referenzwerkstatt=dict(REFERENZWERKSTATT, km_genannt="16,00 km"))
        _seed_akte_mit_mandant()
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=dict(ORS_OK),
        ) as m:
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(m.call_args.kwargs["km_genannt"], 16.0)


if __name__ == "__main__":
    unittest.main()
