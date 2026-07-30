import importlib
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

_tmp_dir = tempfile.mkdtemp(prefix="aktenanlage_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"aa_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")
    export_dir = os.path.join(_tmp_dir, f"oma_{test_id}")
    shutil.rmtree(export_dir, ignore_errors=True)
    os.makedirs(export_dir, exist_ok=True)
    os.environ["OMA_EXPORT_PFAD"] = export_dir

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


FORMULAR = {
    "mandant": {"anrede": "herr", "titel": "", "vorname": "Abdessamad",
                "nachname": "Achkour Zejli", "strasse": "Wiener Straße 61",
                "plz": "60599", "ort": "Frankfurt am Main", "telefon": "",
                "email": "", "geburtstag": "", "iban": "", "bank": "",
                "rsv_name": "", "rsv_nummer": "", "bekannt_adressnr": ""},
    "unfall": {"unfalldatum": "2026-04-10", "unfallort": "Offenbach",
               "kennzeichen": "F-RX 4243"},
    "gegner": {"anrede": "", "vorname": "", "nachname": "", "strasse": "",
               "plz": "", "ort": "", "kennzeichen": ""},
    "versicherung": {"name": "KRAVAG-LOGISTIC Versicherungs-AG",
                     "schadennummer": "45-11-22"},
    "gutachter": {"bezeichnung": "KFZ-Sachverständigenbüro Cassese",
                  "strasse": "Frankfurter Straße 97", "plz": "63067",
                  "ort": "Offenbach am Main", "telefon": "", "email": "",
                  "gutachten_nr": "GA-202604-1189"},
}


class TestMigration66(unittest.TestCase):
    def setUp(self):
        self.client = _setup("mig66")

    def test_tabelle_und_spalten_vorhanden(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            spalten = {r["name"] for r in
                       conn.execute("PRAGMA table_info(aktenanlage_vorgaenge)")}
        for spalte in ("id", "intake_dokument_id", "zustellung_id", "status",
                       "formular_json", "xml_pfad", "mandant_nachname",
                       "mandant_vorname", "mandant_adressnr", "erkanntes_az",
                       "angelegt_am", "angelegt_von", "erkannt_am"):
            self.assertIn(spalte, spalten)

    def test_schema_version_66_gestempelt(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS v FROM schema_version").fetchone()
        self.assertGreaterEqual(row["v"], 66)


def _lege_intake_an(sha_suffix="a", klasse="gutachten"):
    from backend.db.database import get_connection
    uploads = os.environ["UPLOAD_DIR"]
    os.makedirs(uploads, exist_ok=True)
    pfad = os.path.join(uploads, f"arbeit_{sha_suffix}.pdf")
    with open(pfad, "wb") as f:
        f.write(b"%PDF-1.4\n%dummy\n")
    sha = (sha_suffix * 64)[:64]
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO intake_dokumente "
            "(sha256, arbeitskopie_pfad, klasse, klasse_quelle, konfidenz, "
            " queue_status, parse_json, registry_version) "
            "VALUES (?, ?, ?, 'auto', 0.9, 'bereit_zur_review', '{}', 'v1')",
            (sha, pfad, klasse),
        )
        return cur.lastrowid


def _lege_zustellung_an(intake_id, parent_id=None, absender="x@svb-cassese.de",
                        signale=None):
    from backend.db.database import get_connection
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO zustellungen "
            "(intake_dokument_id, quelle, absender, parent_id, signale_json) "
            "VALUES (?, 'imap', ?, ?, ?)",
            (intake_id, absender, parent_id,
             json.dumps(signale or {})),
        )
        return cur.lastrowid


class TestAktenanlageEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = _setup("endpoints")
        self.headers = _auth_header(self.client)

    def _anlegen(self, intake_id=None, zustellung_id=None, formular=None):
        return self.client.post("/aktenanlage", headers=self.headers, json={
            "intake_dokument_id": intake_id,
            "zustellung_id": zustellung_id,
            "formular": formular or FORMULAR,
        })

    def test_anlegen_erzeugt_vorgang_und_xml(self):
        r = self._anlegen()
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        v = r.get_json()["vorgang"]
        self.assertEqual(v["status"], "laeuft")
        self.assertEqual(v["mandant_name"], "Abdessamad Achkour Zejli")
        xmls = [f for f in os.listdir(os.environ["OMA_EXPORT_PFAD"])
                if f.endswith(".xml")]
        self.assertEqual(len(xmls), 1)

    def test_anlegen_ohne_nachname_422(self):
        f = {**FORMULAR, "mandant": {**FORMULAR["mandant"], "nachname": ""}}
        r = self._anlegen(formular=f)
        self.assertEqual(r.status_code, 422)

    def test_anlegen_ohne_unfalldatum_422(self):
        f = {**FORMULAR, "unfall": {**FORMULAR["unfall"], "unfalldatum": ""}}
        r = self._anlegen(formular=f)
        self.assertEqual(r.status_code, 422)

    def test_doppelter_vorgang_pro_intake_409(self):
        did = _lege_intake_an("d")
        zid = _lege_zustellung_an(did)
        self.assertEqual(self._anlegen(did, zid).status_code, 201)
        self.assertEqual(self._anlegen(did, zid).status_code, 409)

    def test_offen_erkennung_eindeutig(self):
        did = _lege_intake_an("e")
        zid = _lege_zustellung_an(did)
        self._anlegen(did, zid)
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True,
                                 "treffer": [{"az": "301/26",
                                              "kurzbezeichnung": "Zejli"}]}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertTrue(d["ramicro_verfuegbar"])
        v = d["vorgaenge"][0]
        self.assertEqual(v["status"], "akte_erkannt")
        self.assertEqual(v["erkanntes_az"], "301/26")

    def test_offen_erkennung_mehrdeutig_bleibt_laeuft(self):
        did = _lege_intake_an("f")
        self._anlegen(did, _lege_zustellung_an(did))
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True,
                                 "treffer": [{"az": "301/26",
                                              "kurzbezeichnung": ""},
                                             {"az": "302/26",
                                              "kurzbezeichnung": ""}]}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        v = r.get_json()["vorgaenge"][0]
        self.assertEqual(v["status"], "laeuft")
        self.assertEqual([k["az"] for k in v["kandidaten"]],
                         ["301/26", "302/26"])

    def test_offen_ramicro_offline(self):
        did = _lege_intake_an("g")
        self._anlegen(did, _lege_zustellung_an(did))
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": False, "treffer": []}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        d = r.get_json()
        self.assertFalse(d["ramicro_verfuegbar"])
        self.assertEqual(d["vorgaenge"][0]["status"], "laeuft")

    def test_leerer_vorgang_erkannt_legt_schattenakte_an(self):
        self._anlegen()
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True,
                                 "treffer": [{"az": "305/26",
                                              "kurzbezeichnung": ""}]}):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        v = r.get_json()["vorgaenge"][0]
        self.assertEqual(v["status"], "akte_erkannt")
        from backend.db.database import get_connection
        with get_connection() as conn:
            akte = conn.execute(
                "SELECT unfalldatum, unfallort FROM unfallakte WHERE az=?",
                ("305/26",)).fetchone()
        self.assertIsNotNone(akte)
        self.assertEqual(akte["unfalldatum"], "2026-04-10")
        self.assertEqual(akte["unfallort"], "Offenbach")

    def test_abbrechen_loescht_xml(self):
        r = self._anlegen()
        vid = r.get_json()["vorgang"]["id"]
        xmls_vor = [f for f in os.listdir(os.environ["OMA_EXPORT_PFAD"])
                    if f.endswith(".xml")]
        self.assertEqual(len(xmls_vor), 1)
        r2 = self.client.post(f"/aktenanlage/{vid}/abbrechen",
                              headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        xmls_nach = [f for f in os.listdir(os.environ["OMA_EXPORT_PFAD"])
                     if f.endswith(".xml")]
        self.assertEqual(xmls_nach, [])
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value={"verfuegbar": True, "treffer": []}):
            offen = self.client.get("/aktenanlage/offen",
                                    headers=self.headers).get_json()
        self.assertEqual(offen["vorgaenge"], [])

    def test_abschliessen_nur_aus_akte_erkannt(self):
        r = self._anlegen()
        vid = r.get_json()["vorgang"]["id"]
        r2 = self.client.post(f"/aktenanlage/{vid}/abschliessen",
                              headers=self.headers)
        self.assertEqual(r2.status_code, 409)

    def test_erkennung_ueberschreibt_abgebrochenen_vorgang_nicht(self):
        did = _lege_intake_an("r1")
        zid = _lege_zustellung_an(did)
        r = self._anlegen(did, zid)
        vid = r.get_json()["vorgang"]["id"]
        from backend.db.database import get_connection

        def _bricht_waehrend_erkennung_ab(*args, **kwargs):
            with get_connection() as conn:
                conn.execute(
                    "UPDATE aktenanlage_vorgaenge SET status='abgebrochen' "
                    "WHERE id=?", (vid,))
            return {"verfuegbar": True,
                    "treffer": [{"az": "399/26", "kurzbezeichnung": ""}]}

        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   side_effect=_bricht_waehrend_erkennung_ab):
            self.client.get("/aktenanlage/offen", headers=self.headers)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, erkanntes_az FROM aktenanlage_vorgaenge "
                "WHERE id=?", (vid,)).fetchone()
        self.assertEqual(row["status"], "abgebrochen")
        self.assertIsNone(row["erkanntes_az"])

    def test_schattenakte_fehler_vorgang_bleibt_laufend(self):
        self._anlegen()
        treffer = {"verfuegbar": True,
                   "treffer": [{"az": "398/26", "kurzbezeichnung": ""}]}
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value=treffer), \
             patch("backend.models.akte.erstelle_oder_hole_akte",
                   side_effect=RuntimeError("DB kaputt")):
            r = self.client.get("/aktenanlage/offen", headers=self.headers)
        self.assertEqual(r.get_json()["vorgaenge"][0]["status"], "laeuft")
        with patch("backend.services.aktenanlage_service.finde_neue_akten",
                   return_value=treffer):
            r2 = self.client.get("/aktenanlage/offen", headers=self.headers)
        self.assertEqual(r2.get_json()["vorgaenge"][0]["status"],
                         "akte_erkannt")

    def test_doppel_409_hinterlaesst_keine_zweite_xml(self):
        did = _lege_intake_an("r2")
        zid = _lege_zustellung_an(did)
        self.assertEqual(self._anlegen(did, zid).status_code, 201)
        self.assertEqual(self._anlegen(did, zid).status_code, 409)
        xmls = [f for f in os.listdir(os.environ["OMA_EXPORT_PFAD"])
                if f.endswith(".xml")]
        self.assertEqual(len(xmls), 1)


if __name__ == "__main__":
    unittest.main()
