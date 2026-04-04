"""
Modul 3 – Integrationstests
=============================
Vollständige API-Tests für alle Modul-3-Endpunkte:
  - GET/POST/PATCH/DELETE /akten
  - GET /akten/statistik
  - GET/POST/PATCH/DELETE /akten/<id>/beteiligte
  - GET/PUT /akten/<id>/schaden
  - GET/POST /akten/<id>/regulierungen
  - GET /akten/<id>/regulierungen/status
  - GET /akten/<id>/aktivitaeten

Jeder Test benutzt eine eigene, frische Datenbank + Auth-Kontext.
"""

import os
import sys
import unittest
import tempfile

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    """Erstellt frische DB + Flask-Client + eingeloggten Admin."""
    db_path = os.path.join(_tmp_dir, f"m3_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-chars!!"

    import importlib
    mods = [
        "backend.db.database", "backend.db.schema_manager",
        "backend.models.benutzer", "backend.models.akte",
        "backend.models.schaden", "backend.models.dokument",
        "backend.auth.jwt_handler", "backend.auth.middleware",
        "backend.auth.service", "backend.auth.validierung",
        "backend.routers.auth_routes", "backend.routers.akten_routes",
        "backend.routers.beteiligte_routes", "backend.routers.schaden_routes",
        "backend.app",
    ]
    import importlib
    loaded = {}
    for mod in mods:
        m = __import__(mod, fromlist=[""])
        importlib.reload(m)
        loaded[mod] = m

    app = loaded["backend.app"].erstelle_app()
    app.config["TESTING"] = True
    client = app.test_client()

    # Admin anlegen und einloggen
    client.post("/auth/register/erster", json={
        "name": "Admin", "email": "admin@test.de", "passwort": "Admin123!"
    })
    r = client.post("/auth/login", json={
        "email": "admin@test.de", "passwort": "Admin123!"
    })
    token = r.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Sachbearbeiter anlegen
    client.post("/auth/register", json={
        "name": "SB", "email": "sb@test.de",
        "passwort": "Sachb123!", "rolle": "sachbearbeiter"
    }, headers=headers)
    sb_r = client.post("/auth/login", json={
        "email": "sb@test.de", "passwort": "Sachb123!"
    })
    sb_token = sb_r.get_json()["access_token"]
    sb_headers = {"Authorization": f"Bearer {sb_token}"}

    return client, headers, sb_headers


def _neue_akte(client, headers, az="25-T-001", datum="2025-01-15",
               ort="Offenbach, Teststr. 1") -> dict:
    r = client.post("/akten", json={
        "aktenzeichen": az,
        "unfalldatum":  datum,
        "unfallort":    ort,
        "haftungsquote": 100.0,
    }, headers=headers)
    assert r.status_code == 201, f"Akte erstellen fehlgeschlagen: {r.get_json()}"
    return r.get_json()


# ══════════════════════════════════════════════════════════════════════════════
# AKTEN CRUD
# ══════════════════════════════════════════════════════════════════════════════

class TestAktenCRUD(unittest.TestCase):

    def setUp(self):
        self.client, self.h, self.sb_h = _setup(f"akte_{self._testMethodName}")

    # ── Liste ─────────────────────────────────────────────────────────────────

    def test_liste_leer(self):
        r = self.client.get("/akten", headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("akten", data)
        self.assertEqual(data["akten"], [])
        self.assertEqual(data["gesamt"], 0)

    def test_liste_ohne_token_401(self):
        r = self.client.get("/akten")
        self.assertEqual(r.status_code, 401)

    # ── Erstellen ─────────────────────────────────────────────────────────────

    def test_akte_erstellen(self):
        r = self.client.post("/akten", json={
            "aktenzeichen": "1/25",
            "unfalldatum":  "2025-01-15",
            "unfallort":    "Offenbach",
            "haftungsquote": 100.0,
        }, headers=self.h)
        self.assertEqual(r.status_code, 201)
        data = r.get_json()
        self.assertEqual(data["aktenzeichen"], "1/25")
        self.assertEqual(data["status"], "offen")
        # Vollständige Akte enthält Unterentitäten
        self.assertIn("beteiligte", data)
        self.assertIn("schaden", data)
        self.assertIn("regulierungen", data)
        self.assertIn("dokumente", data)

    def test_akte_ohne_aktenzeichen_422(self):
        r = self.client.post("/akten", json={
            "unfalldatum": "2025-01-15"
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["feld"], "aktenzeichen")

    def test_akte_ohne_datum_422(self):
        r = self.client.post("/akten", json={
            "aktenzeichen": "25-X"
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["feld"], "unfalldatum")

    def test_doppeltes_aktenzeichen_422(self):
        _neue_akte(self.client, self.h, "25-DUP")
        r = self.client.post("/akten", json={
            "aktenzeichen": "25-DUP", "unfalldatum": "2025-01-15"
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_akte_als_sachbearbeiter_erlaubt(self):
        r = self.client.post("/akten", json={
            "aktenzeichen": "25-SB-001", "unfalldatum": "2025-01-15"
        }, headers=self.sb_h)
        self.assertEqual(r.status_code, 201)

    # ── Detail ────────────────────────────────────────────────────────────────

    def test_detail_abruf(self):
        akte = _neue_akte(self.client, self.h, "25-DET")
        r = self.client.get(f"/akten/{akte['id']}", headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["aktenzeichen"], "25-DET")
        self.assertEqual(data["unfallort"], "Offenbach, Teststr. 1")

    def test_detail_nicht_vorhanden_404(self):
        r = self.client.get("/akten/99999", headers=self.h)
        self.assertEqual(r.status_code, 404)

    # ── Aktualisieren ─────────────────────────────────────────────────────────

    def test_status_aendern(self):
        akte = _neue_akte(self.client, self.h, "25-STAT")
        r = self.client.patch(f"/akten/{akte['id']}", json={
            "status": "in_regulierung"
        }, headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "in_regulierung")

    def test_notizen_setzen(self):
        akte = _neue_akte(self.client, self.h, "25-NOT")
        r = self.client.patch(f"/akten/{akte['id']}", json={
            "notizen": "Wichtige Notiz zur Akte."
        }, headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["notizen"], "Wichtige Notiz zur Akte.")

    def test_ungültiger_status_422(self):
        akte = _neue_akte(self.client, self.h, "25-INVSTAT")
        r = self.client.patch(f"/akten/{akte['id']}", json={
            "status": "ungueltig"
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_patch_ohne_felder_422(self):
        akte = _neue_akte(self.client, self.h, "25-NOFIELDS")
        r = self.client.patch(f"/akten/{akte['id']}", json={},
                               headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_nicht_vorhandene_akte_patch_404(self):
        r = self.client.patch("/akten/99999", json={"status": "offen"},
                               headers=self.h)
        self.assertEqual(r.status_code, 404)

    # ── Löschen ───────────────────────────────────────────────────────────────

    def test_akte_loeschen_als_admin(self):
        akte = _neue_akte(self.client, self.h, "25-DEL")
        r = self.client.delete(f"/akten/{akte['id']}", headers=self.h)
        self.assertEqual(r.status_code, 200)
        # Nach dem Löschen nicht mehr abrufbar
        r2 = self.client.get(f"/akten/{akte['id']}", headers=self.h)
        self.assertEqual(r2.status_code, 404)

    def test_akte_loeschen_als_sachbearbeiter_403(self):
        akte = _neue_akte(self.client, self.h, "25-NODEL")
        r = self.client.delete(f"/akten/{akte['id']}", headers=self.sb_h)
        self.assertEqual(r.status_code, 403)

    def test_nicht_vorhandene_akte_loeschen_404(self):
        r = self.client.delete("/akten/99999", headers=self.h)
        self.assertEqual(r.status_code, 404)

    # ── Filter & Suche ────────────────────────────────────────────────────────

    def test_filter_nach_status(self):
        _neue_akte(self.client, self.h, "25-F1")
        akte2 = _neue_akte(self.client, self.h, "25-F2")
        self.client.patch(f"/akten/{akte2['id']}", json={
            "status": "abgeschlossen"
        }, headers=self.h)

        r = self.client.get("/akten?status=offen", headers=self.h)
        az_liste = [a["aktenzeichen"] for a in r.get_json()["akten"]]
        self.assertIn("25-F1", az_liste)
        self.assertNotIn("25-F2", az_liste)

    def test_suche_nach_aktenzeichen(self):
        _neue_akte(self.client, self.h, "25-SUCH-001")
        _neue_akte(self.client, self.h, "25-ANDERS-001")
        r = self.client.get("/akten?suche=SUCH", headers=self.h)
        az_liste = [a["aktenzeichen"] for a in r.get_json()["akten"]]
        self.assertIn("25-SUCH-001", az_liste)
        self.assertNotIn("25-ANDERS-001", az_liste)

    def test_paginierung(self):
        for i in range(5):
            _neue_akte(self.client, self.h, f"25-PAG-{i:03d}")
        r = self.client.get("/akten?limit=2&offset=0", headers=self.h)
        data = r.get_json()
        self.assertEqual(len(data["akten"]), 2)
        self.assertEqual(data["gesamt"], 5)

    # ── Statistik ─────────────────────────────────────────────────────────────

    def test_statistik_leer(self):
        r = self.client.get("/akten/statistik", headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("gesamt", data)
        self.assertIn("akten_by_status", data)

    def test_statistik_mit_akten(self):
        _neue_akte(self.client, self.h, "25-ST1")
        akte2 = _neue_akte(self.client, self.h, "25-ST2")
        self.client.patch(f"/akten/{akte2['id']}", json={
            "status": "in_regulierung"
        }, headers=self.h)

        r = self.client.get("/akten/statistik", headers=self.h)
        stats = r.get_json()
        self.assertEqual(stats["gesamt"], 2)
        self.assertIn("offen", stats["akten_by_status"])

    # ── Aktivitätsfeed ────────────────────────────────────────────────────────

    def test_aktivitaeten_nach_erstellung(self):
        akte = _neue_akte(self.client, self.h, "25-ACT")
        r = self.client.get(f"/akten/{akte['id']}/aktivitaeten",
                             headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("aktivitaeten", data)
        aktionen = [a["aktion"] for a in data["aktivitaeten"]]
        self.assertIn("akte_erstellt", aktionen)

    def test_aktivitaeten_nach_status_aenderung(self):
        akte = _neue_akte(self.client, self.h, "25-ACT2")
        self.client.patch(f"/akten/{akte['id']}", json={
            "status": "in_regulierung"
        }, headers=self.h)
        r = self.client.get(f"/akten/{akte['id']}/aktivitaeten",
                             headers=self.h)
        aktionen = [a["aktion"] for a in r.get_json()["aktivitaeten"]]
        self.assertIn("status_geaendert", aktionen)

    def test_aktivitaeten_nicht_vorhandene_akte_404(self):
        r = self.client.get("/akten/99999/aktivitaeten", headers=self.h)
        self.assertEqual(r.status_code, 404)


# ══════════════════════════════════════════════════════════════════════════════
# BETEILIGTE
# ══════════════════════════════════════════════════════════════════════════════

class TestBeteiligte(unittest.TestCase):

    def setUp(self):
        self.client, self.h, self.sb_h = _setup(f"bet_{self._testMethodName}")
        self.akte = _neue_akte(self.client, self.h, "25-BET-001")
        self.aid = self.akte["id"]

    def _url(self, bid=None):
        base = f"/akten/{self.aid}/beteiligte"
        return f"{base}/{bid}" if bid else base

    def _add(self, rolle="mandant", name="Müller", **extra) -> dict:
        r = self.client.post(self._url(), json={
            "rolle": rolle, "name": name, **extra
        }, headers=self.h)
        assert r.status_code == 201, r.get_json()
        return r.get_json()

    # ── Liste ─────────────────────────────────────────────────────────────────

    def test_liste_leer(self):
        r = self.client.get(self._url(), headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["beteiligte"], [])

    def test_filter_nach_rolle(self):
        self._add("mandant", "Mandant1")
        self._add("gegner", "Gegner1")
        r = self.client.get(f"{self._url()}?rolle=mandant", headers=self.h)
        data = r.get_json()["beteiligte"]
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["rolle"], "mandant")

    # ── Erstellen ─────────────────────────────────────────────────────────────

    def test_mandant_hinzufuegen(self):
        r = self.client.post(self._url(), json={
            "rolle": "mandant",
            "name": "Mustermann",
            "vorname": "Max",
            "kfz_kennzeichen": "OF-MM 1",
            "kfz_typ": "VW Golf",
            "versicherung": "HUK",
            "vers_nr": "HUK-123",
            "telefon": "069-123456",
        }, headers=self.h)
        self.assertEqual(r.status_code, 201)
        data = r.get_json()
        self.assertEqual(data["name"], "Mustermann")
        self.assertEqual(data["vollstaendiger_name"], "Max Mustermann")

    def test_alle_rollen_erlaubt(self):
        for rolle in ["mandant", "gegner", "zeuge",
                       "sachverstaendiger", "sonstiger"]:
            r = self.client.post(self._url(), json={
                "rolle": rolle, "name": f"Person {rolle}"
            }, headers=self.h)
            self.assertEqual(r.status_code, 201,
                              f"Rolle {rolle!r} fehlgeschlagen")

    def test_ungueltige_rolle_422(self):
        r = self.client.post(self._url(), json={
            "rolle": "richter", "name": "X"
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_ohne_name_422(self):
        r = self.client.post(self._url(), json={"rolle": "mandant"},
                               headers=self.h)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["feld"], "name")

    def test_nicht_vorhandene_akte_404(self):
        r = self.client.post("/akten/99999/beteiligte", json={
            "rolle": "mandant", "name": "X"
        }, headers=self.h)
        self.assertEqual(r.status_code, 404)

    # ── Aktualisieren ─────────────────────────────────────────────────────────

    def test_beteiligten_aktualisieren(self):
        b = self._add("mandant", "Alt")
        r = self.client.patch(self._url(b["id"]), json={
            "name": "Neu", "telefon": "069-999"
        }, headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["name"], "Neu")
        self.assertEqual(data["telefon"], "069-999")

    def test_patch_ohne_felder_422(self):
        b = self._add()
        r = self.client.patch(self._url(b["id"]), json={},
                               headers=self.h)
        self.assertEqual(r.status_code, 422)

    # ── Löschen ───────────────────────────────────────────────────────────────

    def test_beteiligten_loeschen(self):
        b = self._add()
        r = self.client.delete(self._url(b["id"]), headers=self.h)
        self.assertEqual(r.status_code, 200)
        # Nicht mehr in Liste
        alle = self.client.get(self._url(), headers=self.h).get_json()["beteiligte"]
        ids = [x["id"] for x in alle]
        self.assertNotIn(b["id"], ids)

    def test_nicht_vorhandenen_beteiligten_loeschen_404(self):
        r = self.client.delete(self._url(99999), headers=self.h)
        self.assertEqual(r.status_code, 404)

    # ── Aktivitäts-Log ────────────────────────────────────────────────────────

    def test_hinzufuegen_erzeugt_aktivitaet(self):
        self._add("gegner", "Gegner")
        r = self.client.get(f"/akten/{self.aid}/aktivitaeten", headers=self.h)
        aktionen = [a["aktion"] for a in r.get_json()["aktivitaeten"]]
        self.assertIn("beteiligter_hinzugefuegt", aktionen)


# ══════════════════════════════════════════════════════════════════════════════
# SCHADENPOSITIONEN
# ══════════════════════════════════════════════════════════════════════════════

class TestSchadenpositionen(unittest.TestCase):

    def setUp(self):
        self.client, self.h, _ = _setup(f"scp_{self._testMethodName}")
        self.akte = _neue_akte(self.client, self.h, "25-SCP-001")
        self.aid = self.akte["id"]

    def _url(self):
        return f"/akten/{self.aid}/schaden"

    # ── GET (leer) ────────────────────────────────────────────────────────────

    def test_schaden_leer(self):
        r = self.client.get(self._url(), headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIsNone(data["schaden"])

    # ── PUT (setzen) ──────────────────────────────────────────────────────────

    def test_schaden_setzen(self):
        r = self.client.put(self._url(), json={
            "reparaturkosten": 6240.50,
            "sv_kosten":       890.00,
            "nutzungsausfall": 560.00,
            "wertminderung":   350.00,
            "abschleppkosten": 180.00,
        }, headers=self.h)
        self.assertEqual(r.status_code, 200)
        schaden = r.get_json()["schaden"]
        self.assertAlmostEqual(schaden["reparaturkosten"], 6240.50)
        self.assertAlmostEqual(schaden["gesamt_brutto"], 8220.50)

    def test_totalschaden(self):
        r = self.client.put(self._url(), json={
            "wiederbeschaffung": 18500.00,
            "restwert":           3200.00,
            "sv_kosten":          1150.00,
            "abschleppkosten":     220.00,
            "standkosten":         180.00,
            "mietwagenkosten":     680.00,
            "anabmeldekosten":      53.50,
        }, headers=self.h)
        schaden = r.get_json()["schaden"]
        # 18500 - 3200 + 1150 + 220 + 180 + 680 + 53.50 = 17583.50
        self.assertAlmostEqual(schaden["gesamt_brutto"], 17583.50)
        self.assertAlmostEqual(schaden["wiederbeschaffung"], 18500.00)
        self.assertAlmostEqual(schaden["restwert"], 3200.00)

    def test_negativer_wert_422(self):
        r = self.client.put(self._url(), json={
            "reparaturkosten": -100.0
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_kein_text_als_zahl_422(self):
        r = self.client.put(self._url(), json={
            "reparaturkosten": "nicht_eine_zahl"
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_update_ersetzt(self):
        self.client.put(self._url(), json={"reparaturkosten": 5000.0},
                         headers=self.h)
        self.client.put(self._url(), json={"reparaturkosten": 6000.0},
                         headers=self.h)
        r = self.client.get(self._url(), headers=self.h)
        self.assertAlmostEqual(r.get_json()["schaden"]["reparaturkosten"], 6000.0)

    def test_nicht_vorhandene_akte_404(self):
        r = self.client.get("/akten/99999/schaden", headers=self.h)
        self.assertEqual(r.status_code, 404)

    def test_schaden_erzeugt_aktivitaet(self):
        self.client.put(self._url(), json={"reparaturkosten": 5000.0},
                         headers=self.h)
        r = self.client.get(f"/akten/{self.aid}/aktivitaeten", headers=self.h)
        aktionen = [a["aktion"] for a in r.get_json()["aktivitaeten"]]
        self.assertIn("schaden_aktualisiert", aktionen)


# ══════════════════════════════════════════════════════════════════════════════
# REGULIERUNG
# ══════════════════════════════════════════════════════════════════════════════

class TestRegulierung(unittest.TestCase):

    def setUp(self):
        self.client, self.h, _ = _setup(f"reg_{self._testMethodName}")
        self.akte = _neue_akte(self.client, self.h, "25-REG-001")
        self.aid = self.akte["id"]
        # Schadenpositionen setzen
        self.client.put(f"/akten/{self.aid}/schaden", json={
            "reparaturkosten": 8000.0, "sv_kosten": 800.0
        }, headers=self.h)

    def _url(self, suffix=""):
        return f"/akten/{self.aid}/regulierungen{suffix}"

    def _reguliere(self, gefordert=8800.0, reguliert=6000.0, **extra) -> dict:
        r = self.client.post(self._url(), json={
            "datum": "2025-02-18",
            "betrag_gefordert": gefordert,
            "betrag_reguliert": reguliert,
            **extra
        }, headers=self.h)
        assert r.status_code == 201, r.get_json()
        return r.get_json()

    # ── Liste ─────────────────────────────────────────────────────────────────

    def test_liste_leer(self):
        r = self.client.get(self._url(), headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["regulierungen"], [])

    # ── Erstellen ─────────────────────────────────────────────────────────────

    def test_teilregulierung_anlegen(self):
        data = self._reguliere(8800.0, 6000.0,
                                vers_referenz="HUK-123",
                                kuerz_begruendung="SV-Kosten abgelehnt")
        reg = data["regulierung"]
        self.assertAlmostEqual(reg["betrag_gefordert"], 8800.0)
        self.assertAlmostEqual(reg["betrag_reguliert"], 6000.0)
        self.assertAlmostEqual(reg["differenz"], 2800.0)
        self.assertEqual(reg["status"], "teilreguliert")
        self.assertEqual(reg["vers_referenz"], "HUK-123")

    def test_vollregulierung(self):
        data = self._reguliere(8800.0, 8800.0)
        self.assertEqual(data["regulierung"]["status"], "vollreguliert")

    def test_vollregulierung_setzt_akte_abgeschlossen(self):
        self._reguliere(8800.0, 8800.0)
        akte = self.client.get(f"/akten/{self.aid}",
                                headers=self.h).get_json()
        self.assertEqual(akte["status"], "abgeschlossen")

    def test_teilregulierung_setzt_akte_in_regulierung(self):
        self._reguliere(8800.0, 4000.0)
        akte = self.client.get(f"/akten/{self.aid}",
                                headers=self.h).get_json()
        self.assertEqual(akte["status"], "in_regulierung")

    def test_ohne_datum_422(self):
        r = self.client.post(self._url(), json={
            "betrag_gefordert": 8000.0, "betrag_reguliert": 6000.0
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_negativer_regulierter_betrag_422(self):
        r = self.client.post(self._url(), json={
            "datum": "2025-02-01",
            "betrag_gefordert": 8000.0,
            "betrag_reguliert": -100.0
        }, headers=self.h)
        self.assertEqual(r.status_code, 422)

    def test_mehrere_regulierungen(self):
        self._reguliere(8800.0, 3000.0)
        self._reguliere(8800.0, 3000.0)
        r = self.client.get(self._url(), headers=self.h)
        self.assertEqual(len(r.get_json()["regulierungen"]), 2)

    # ── Status-View ───────────────────────────────────────────────────────────

    def test_status_leer(self):
        r = self.client.get(self._url("/status"), headers=self.h)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("betrag_gefordert", data)
        self.assertIn("betrag_reguliert", data)
        self.assertIn("differenz", data)

    def test_status_nach_regulierung(self):
        self._reguliere(8800.0, 5500.0)
        r = self.client.get(self._url("/status"), headers=self.h)
        data = r.get_json()
        self.assertAlmostEqual(data["betrag_reguliert"], 5500.0)

    def test_nicht_vorhandene_akte_404(self):
        r = self.client.get("/akten/99999/regulierungen", headers=self.h)
        self.assertEqual(r.status_code, 404)


# ══════════════════════════════════════════════════════════════════════════════
# VOLLSTÄNDIGER WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

class TestVollstaendigerWorkflow(unittest.TestCase):
    """
    Testet einen kompletten realistischen Workflow:
    Akte anlegen → Beteiligte → Schaden → Regulierung → Status prüfen
    """

    def setUp(self):
        self.client, self.h, _ = _setup(f"wf_{self._testMethodName}")

    def test_kompletter_workflow(self):
        # 1. Akte anlegen
        r = self.client.post("/akten", json={
            "aktenzeichen": "25-WORKFLOW-001",
            "unfalldatum":  "2025-03-01",
            "unfallort":    "Offenbach, Berliner Str. 12",
            "haftungsquote": 100.0,
        }, headers=self.h)
        self.assertEqual(r.status_code, 201)
        akte = r.get_json()
        akte_id = akte["id"]

        # 2. Mandant hinzufügen
        r = self.client.post(f"/akten/{akte_id}/beteiligte", json={
            "rolle": "mandant", "name": "Müller", "vorname": "Hans",
            "kfz_kennzeichen": "OF-HM 1", "kfz_typ": "VW Passat",
        }, headers=self.h)
        self.assertEqual(r.status_code, 201)

        # 3. Gegner hinzufügen
        r = self.client.post(f"/akten/{akte_id}/beteiligte", json={
            "rolle": "gegner", "name": "Bauer", "vorname": "Klaus",
            "versicherung": "HUK Coburg", "schaden_nr": "HUK-2025-001",
        }, headers=self.h)
        self.assertEqual(r.status_code, 201)

        # 4. Schadenpositionen setzen (aus Gutachten)
        r = self.client.put(f"/akten/{akte_id}/schaden", json={
            "reparaturkosten": 6240.50,
            "sv_kosten":        890.00,
            "nutzungsausfall":  560.00,
            "wertminderung":    350.00,
            "abschleppkosten":  180.00,
            "quelle": "gutachten_pdf",
        }, headers=self.h)
        self.assertEqual(r.status_code, 200)
        gesamt = r.get_json()["schaden"]["gesamt_brutto"]
        self.assertAlmostEqual(gesamt, 8220.50)

        # 5. Akte prüfen – Status noch offen
        r = self.client.get(f"/akten/{akte_id}", headers=self.h)
        akte_detail = r.get_json()
        self.assertEqual(akte_detail["status"], "offen")
        self.assertEqual(len(akte_detail["beteiligte"]), 2)
        self.assertAlmostEqual(
            akte_detail["schaden"]["gesamt_brutto"], 8220.50
        )

        # 6. Teilregulierung eingetragen
        r = self.client.post(f"/akten/{akte_id}/regulierungen", json={
            "datum": "2025-04-10",
            "betrag_gefordert": 8220.50,
            "betrag_reguliert": 6180.00,
            "vers_referenz": "HUK-2025-001-R",
            "kuerz_begruendung": "Wertminderung abgelehnt, SV-Kosten gekürzt",
        }, headers=self.h)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["regulierung"]["status"], "teilreguliert")

        # 7. Akte-Status prüfen → in_regulierung
        r = self.client.get(f"/akten/{akte_id}", headers=self.h)
        self.assertEqual(r.get_json()["status"], "in_regulierung")

        # 8. Regulierungsstatus prüfen
        r = self.client.get(f"/akten/{akte_id}/regulierungen/status",
                             headers=self.h)
        status = r.get_json()
        self.assertAlmostEqual(status["betrag_reguliert"], 6180.00)
        differenz = round(8220.50 - 6180.00, 2)
        self.assertAlmostEqual(status["differenz"], differenz, places=1)

        # 9. Aktivitätsfeed prüfen
        r = self.client.get(f"/akten/{akte_id}/aktivitaeten", headers=self.h)
        aktionen = [a["aktion"] for a in r.get_json()["aktivitaeten"]]
        for erwartet in ["akte_erstellt", "beteiligter_hinzugefuegt",
                          "schaden_aktualisiert"]:
            self.assertIn(erwartet, aktionen,
                          f"Aktion '{erwartet}' fehlt im Aktivitätsfeed")

        # 10. Statistik prüfen
        r = self.client.get("/akten/statistik", headers=self.h)
        stats = r.get_json()
        self.assertGreaterEqual(stats["gesamt"], 1)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestAktenCRUD, TestBeteiligte,
        TestSchadenpositionen, TestRegulierung,
        TestVollstaendigerWorkflow,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
