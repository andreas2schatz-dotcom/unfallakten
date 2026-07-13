"""
Tests fuer backend/routers/intake_routes.py (S1.8).

Deckt Blueprint intake_bp mit:
  - GET  /intake/queue
  - GET  /intake/dokument/<id>
  - PATCH /intake/dokument/<id>/klasse
  - PATCH /intake/dokument/<id>/felder
  - POST  /intake/dokument/<id>/freigabe
  - POST  /intake/dokument/<id>/verwerfen (Verwerfen-Workflow, Migration 53)
  - GET  /intake/ereignistypen (Registry-Katalog fuer Freigabe-Dropdown)
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="intake_routes_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"iq_{test_id}.db")
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
    client = app.test_client()
    return client


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _lege_intake_pdf_an(sha_suffix="a", klasse="abrechnungsschreiben",
                         konfidenz=0.9, queue_status="bereit_zur_review",
                         parse_json=None):
    from backend.db.database import get_connection
    uploads = os.environ["UPLOAD_DIR"]
    os.makedirs(uploads, exist_ok=True)
    pfad = os.path.join(uploads, f"arbeit_{sha_suffix}.pdf")
    with open(pfad, "wb") as f:
        f.write(b"%PDF-1.4\n%dummy\n")
    sha = (sha_suffix * 64)[:64]
    if parse_json is None:
        parse_json = json.dumps({
            "text_gesamt": "Aktenzeichen 44/22 ...",
            "seiten": [{"nr": 1, "textquelle": "textebene",
                        "ratio_salat": 0.0, "zeichen": 200}],
            "klassifikation": {
                "kandidaten": [{"klasse": klasse, "konfidenz": konfidenz,
                                "quelle": "llm_stufe2"}],
                "hinweise": [],
            },
            "felder": {"betrag": "1000,00"},
            "akten_kandidaten": [
                {"akte_az": "44/22", "score": 1.0,
                 "quelle": "az_exakt", "treffer": "44/22"}
            ],
        }, ensure_ascii=False)

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO intake_dokumente "
            "(sha256, arbeitskopie_pfad, klasse, klasse_quelle, "
            " konfidenz, queue_status, parse_json, registry_version) "
            "VALUES (?, ?, ?, 'auto', ?, ?, ?, 'v1')",
            (sha, pfad, klasse, konfidenz, queue_status, parse_json),
        )
        return cur.lastrowid


def _seed_akte(az="44/22"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2022-04-27', 'offen')",
            (az,),
        )


class TestIntakeQueue(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_queue_ohne_token_401(self):
        r = self.client.get("/intake/queue")
        self.assertEqual(r.status_code, 401)

    def test_queue_leere_liste_wenn_nichts_vorhanden(self):
        r = self.client.get("/intake/queue", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"eintraege": []})

    def test_queue_liefert_bereit_und_pipeline_fehler(self):
        _lege_intake_pdf_an("a", queue_status="bereit_zur_review",
                            konfidenz=0.9)
        _lege_intake_pdf_an("b", queue_status="pipeline_fehler",
                            konfidenz=0.1)
        _lege_intake_pdf_an("c", queue_status="neu",
                            konfidenz=0.7)  # nicht sichtbar
        _lege_intake_pdf_an("d", queue_status="freigegeben",
                            konfidenz=0.7)  # nicht sichtbar

        r = self.client.get("/intake/queue", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        eintraege = r.get_json()["eintraege"]
        stati = sorted({e["queue_status"] for e in eintraege})
        self.assertEqual(stati, ["bereit_zur_review", "pipeline_fehler"])
        self.assertEqual(len(eintraege), 2)

    def test_queue_sortierung_alter_dann_konfidenz(self):
        # b (aelter) bekommt niedrigere ID (sqlite AUTOINCREMENT -> aelter)
        id_a = _lege_intake_pdf_an("a", konfidenz=0.9)
        id_b = _lege_intake_pdf_an("b", konfidenz=0.1)
        r = self.client.get("/intake/queue", headers=self.headers)
        ids = [e["id"] for e in r.get_json()["eintraege"]]
        self.assertEqual(ids, [id_a, id_b],
                         "Erwartet: Aeltestes zuerst (id_a vor id_b)")

    def test_bug20_queue_deserialisiert_nicht_ganzes_parse_json(self):
        # BUG-20: Top-Kandidat kommt per json_extract; das ganze parse_json
        # (inkl. text_gesamt) wird nicht mehr pro Queue-Zeile deserialisiert.
        import backend.routers.intake_routes as ir
        _lege_intake_pdf_an("a")  # parse_json enthaelt text_gesamt + akten_kandidaten
        gesehen = []
        orig = ir._parse

        def _spy(text):
            gesehen.append(text)
            return orig(text)

        ir._parse = _spy
        try:
            r = self.client.get("/intake/queue", headers=self.headers)
        finally:
            ir._parse = orig
        self.assertEqual(r.status_code, 200)
        self.assertFalse(
            any("text_gesamt" in (t or "") for t in gesehen),
            "hole_queue deserialisiert weiterhin das ganze parse_json pro Zeile",
        )
        top = r.get_json()["eintraege"][0]["akte_kandidat_top"]
        self.assertEqual(top["akte_az"], "44/22")

    def test_bug21_queue_nutzt_erste_zustellung(self):
        # BUG-21: eine LEFT-JOIN-Zustellung (MIN(id)) statt 4 korrelierter
        # Subselects — dieselbe "erste Zustellung"-Semantik.
        from backend.db.database import get_connection
        did = _lege_intake_pdf_an("a")
        with get_connection() as conn:
            erste_id = conn.execute(
                "INSERT INTO zustellungen "
                "(intake_dokument_id, quelle, absender, betreff, empfangen_am, "
                " parent_id) VALUES (?, 'imap', 'erst@x.de', 'Erste', "
                "'2022-05-01', NULL)",
                (did,),
            ).lastrowid
            conn.execute(
                "INSERT INTO zustellungen "
                "(intake_dokument_id, quelle, absender, betreff, empfangen_am, "
                " parent_id) VALUES (?, 'imap', 'zweit@x.de', 'Zweite', "
                "'2022-05-02', ?)",
                (did, erste_id),
            )
        r = self.client.get("/intake/queue", headers=self.headers)
        e = [x for x in r.get_json()["eintraege"] if x["id"] == did][0]
        self.assertEqual(e["absender"], "erst@x.de")
        self.assertEqual(e["betreff"], "Erste")
        self.assertIsNone(e["parent_zustellung_id"])


class TestIntakeKlassen(unittest.TestCase):
    """BUG-26: Klassen-Katalog-Endpoint fuer das Reklassifikations-Dropdown."""

    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_klassen_ohne_token_401(self):
        r = self.client.get("/intake/klassen")
        self.assertEqual(r.status_code, 401)

    def test_klassen_liefert_registry_klassen(self):
        r = self.client.get("/intake/klassen", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        klassen = r.get_json()["klassen"]
        self.assertIn("gutachten", klassen)
        self.assertIn("abrechnungsschreiben", klassen)
        self.assertIn("sonstiges", klassen)


class TestIntakeDetail(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_detail_liefert_parse_json_und_kandidaten(self):
        did = _lege_intake_pdf_an("a")
        r = self.client.get(f"/intake/dokument/{did}", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        daten = r.get_json()
        self.assertEqual(daten["id"], did)
        self.assertEqual(daten["klasse"], "abrechnungsschreiben")
        self.assertIn("parse", daten)
        self.assertIn("akten_kandidaten", daten["parse"])
        self.assertIn("felder", daten["parse"])
        self.assertIn("zustellungen", daten)
        self.assertIn("freigaben", daten)

    def test_detail_404_bei_unbekannter_id(self):
        r = self.client.get("/intake/dokument/99999", headers=self.headers)
        self.assertEqual(r.status_code, 404)


class TestPatchKlasse(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_setzt_klasse_manuell_und_reenqueued(self):
        from backend.db.database import get_connection
        did = _lege_intake_pdf_an("a", klasse="sonstiges", konfidenz=0.3)

        r = self.client.patch(
            f"/intake/dokument/{did}/klasse",
            json={"klasse": "gutachten"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT klasse, klasse_quelle, queue_status "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
            log = conn.execute(
                "SELECT feld, wert_alt, wert_neu FROM korrektur_log "
                "WHERE intake_dokument_id=?", (did,)
            ).fetchone()
        self.assertEqual(row["klasse"], "gutachten")
        self.assertEqual(row["klasse_quelle"], "manuell")
        self.assertEqual(row["queue_status"], "neu")
        self.assertIsNotNone(log)
        self.assertEqual(log["feld"], "klasse")
        self.assertEqual(log["wert_alt"], "sonstiges")
        self.assertEqual(log["wert_neu"], "gutachten")

    def test_ohne_klasse_400(self):
        did = _lege_intake_pdf_an("a")
        r = self.client.patch(
            f"/intake/dokument/{did}/klasse", json={},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 400)


class TestPatchFelder(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_felder_werden_gespeichert_und_geloggt(self):
        from backend.db.database import get_connection
        did = _lege_intake_pdf_an("a")

        r = self.client.patch(
            f"/intake/dokument/{did}/felder",
            json={"felder": {
                "betrag": {"alt": "1000,00", "neu": "1500,00"},
                "datum": {"alt": None, "neu": "2026-04-01"},
            }},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, queue_status FROM intake_dokumente "
                "WHERE id=?", (did,)
            ).fetchone()
            logs = conn.execute(
                "SELECT feld, wert_alt, wert_neu FROM korrektur_log "
                "WHERE intake_dokument_id=? ORDER BY feld", (did,)
            ).fetchall()

        self.assertEqual(row["queue_status"], "bereit_zur_review")
        parse = json.loads(row["parse_json"])
        self.assertEqual(parse["felder"]["betrag"], "1500,00")
        self.assertEqual(parse["felder"]["datum"], "2026-04-01")
        felder = {r["feld"]: (r["wert_alt"], r["wert_neu"]) for r in logs}
        self.assertEqual(felder["betrag"], ("1000,00", "1500,00"))
        self.assertEqual(felder["datum"], (None, "2026-04-01"))


class TestFreigabe(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_ohne_akte_az_422(self):
        did = _lege_intake_pdf_an("a")
        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 422)

    def test_freigabe_erzeugt_dokument_und_freigabe_zeile(self):
        from backend.db.database import get_connection
        _seed_akte("44/22")
        did = _lege_intake_pdf_an("a")

        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        data = r.get_json()
        self.assertIn("dokument_id", data)
        self.assertIn("freigabe_id", data)

        with get_connection() as conn:
            dok = conn.execute(
                "SELECT akte_id, typ FROM dokumente WHERE id=?",
                (data["dokument_id"],)
            ).fetchone()
            frg = conn.execute(
                "SELECT intake_dokument_id, akte_az, dokument_id "
                "FROM freigaben WHERE id=?", (data["freigabe_id"],)
            ).fetchone()
            intake = conn.execute(
                "SELECT queue_status FROM intake_dokumente WHERE id=?",
                (did,)
            ).fetchone()

        self.assertIsNotNone(dok)
        self.assertEqual(dok["akte_id"], "44/22")
        self.assertEqual(dok["typ"], "abrechnungsschreiben")
        self.assertEqual(frg["intake_dokument_id"], did)
        self.assertEqual(frg["akte_az"], "44/22")
        self.assertEqual(frg["dokument_id"], data["dokument_id"])
        self.assertEqual(intake["queue_status"], "freigegeben")

    def test_freigabe_akzeptiert_kandidaten_ereignisse_und_ersetzt_ids(self):
        """K-2 (Ereignis-Vorschlaege) + K-M2b (ersetzt_ids): S1.8 nimmt die
        Payload entgegen und legt sie fuer P1.5 als Kontext ab -- Struktur,
        nicht Persistenz im Positionsmodell."""
        from backend.db.database import get_connection
        _seed_akte("44/22")
        did = _lege_intake_pdf_an("a")

        payload = {
            "akte_az": "44/22",
            "kandidaten_ereignisse": [
                {"typ": "abrechnung_eingegangen",
                 "positionen": [
                     {"key": "reparaturkosten",
                      "wirkung": "anerkannt", "betrag": 4100.0}
                 ]}
            ],
            "ersetzt_ids": [],
        }
        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json=payload, headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        with get_connection() as conn:
            log = conn.execute(
                "SELECT feld, wert_neu FROM korrektur_log "
                "WHERE intake_dokument_id=? "
                "  AND feld IN ('kandidaten_ereignisse', 'ersetzt_ids') "
                "ORDER BY feld",
                (did,)
            ).fetchall()
        felder = {r["feld"] for r in log}
        self.assertIn("kandidaten_ereignisse", felder)


class TestFreigabeGutachtenErzeugtEreignis(unittest.TestCase):
    """Option A: Wird ein Gutachten freigegeben und enthaelt das parse_json
    Positions-Felder (reparaturkosten, wiederbeschaffung, restwert,
    wertminderung) und optional SV-Kosten (sv_kosten_netto / sv_kosten_brutto),
    schreibt die Freigabe automatisch ein gutachten_eingegangen-Ereignis
    mit allen Positionen -- inklusive sv_kosten je nach Vorsteuer-Flag
    des Mandanten. Kein Alt-Pfad-Zwang.
    """

    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def _seed_akte_mit_mandant(self, az, vorsteuer):
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
                "VALUES (?, '2026-04-27', 'offen')", (az,),
            )
            conn.execute(
                "INSERT INTO beteiligte (akte_id, rolle, name, vorsteuer) "
                "VALUES (?, 'mandant', 'Riccio', ?)",
                (az, "J" if vorsteuer else "N"),
            )

    def _lege_gutachten_an(self, felder):
        return _lege_intake_pdf_an(
            "g", klasse="gutachten", konfidenz=0.95,
            parse_json=json.dumps({
                "text_gesamt": "DEKRA Gutachten 44/22",
                "seiten": [{"nr": 1, "textquelle": "textebene",
                            "ratio_salat": 0.0, "zeichen": 500}],
                "klassifikation": {
                    "kandidaten": [{"klasse": "gutachten",
                                     "konfidenz": 0.95,
                                     "quelle": "llm_stufe2"}],
                    "hinweise": [],
                },
                "felder": felder,
                "akten_kandidaten": [
                    {"akte_az": "44/22", "score": 1.0,
                     "quelle": "az_exakt", "treffer": "44/22"}
                ],
            }, ensure_ascii=False),
        )

    def test_gutachten_freigabe_erzeugt_gutachten_ereignis_mit_positionen(self):
        from backend.db.database import get_connection
        self._seed_akte_mit_mandant("44/22", vorsteuer=False)
        did = self._lege_gutachten_an({
            "reparaturkosten_netto": "3500,00",
            "wiederbeschaffungswert": "12000,00",
            "restwert_brutto": "5000,00",
            "wertminderung": "500,00",
        })

        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        with get_connection() as conn:
            ereignisse = conn.execute(
                "SELECT id, ereignistyp FROM ereignisse "
                "WHERE akte_az='44/22' AND ersetzt_durch IS NULL"
            ).fetchall()
            self.assertEqual(len(ereignisse), 1)
            self.assertEqual(ereignisse[0]["ereignistyp"],
                              "gutachten_eingegangen")

            positionen = conn.execute(
                "SELECT position_key, betrag FROM ereignis_positionen "
                "WHERE ereignis_id=?", (ereignisse[0]["id"],)
            ).fetchall()
            keys = {p["position_key"] for p in positionen}
        self.assertIn("reparaturkosten", keys)
        self.assertIn("wiederbeschaffung", keys)
        self.assertIn("restwert", keys)
        self.assertIn("wertminderung", keys)

    def test_gutachten_mit_sv_kosten_privat_nutzt_brutto(self):
        """Privatmandant (vorsteuer=False): sv_kosten mit BRUTTO-Betrag."""
        from backend.db.database import get_connection
        self._seed_akte_mit_mandant("44/22", vorsteuer=False)
        did = self._lege_gutachten_an({
            "reparaturkosten_netto": "3500,00",
            "sv_kosten_netto": "850,00",
            "sv_kosten_brutto": "1011,50",
        })

        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT ep.position_key, ep.betrag FROM ereignis_positionen ep "
                "JOIN ereignisse e ON e.id = ep.ereignis_id "
                "WHERE e.akte_az='44/22' AND ep.position_key='sv_kosten'"
            ).fetchone()
        self.assertIsNotNone(row, "sv_kosten-Position fehlt")
        self.assertAlmostEqual(row["betrag"], 1011.50, places=2)

    def test_gutachten_mit_sv_kosten_vorsteuerberechtigt_nutzt_netto(self):
        from backend.db.database import get_connection
        self._seed_akte_mit_mandant("44/22", vorsteuer=True)
        did = self._lege_gutachten_an({
            "reparaturkosten_netto": "3500,00",
            "sv_kosten_netto": "850,00",
            "sv_kosten_brutto": "1011,50",
        })

        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        with get_connection() as conn:
            row = conn.execute(
                "SELECT ep.position_key, ep.betrag FROM ereignis_positionen ep "
                "JOIN ereignisse e ON e.id = ep.ereignis_id "
                "WHERE e.akte_az='44/22' AND ep.position_key='sv_kosten'"
            ).fetchone()
        self.assertIsNotNone(row, "sv_kosten-Position fehlt")
        # Vorsteuer-Berechtigt -> Netto-Betrag
        self.assertAlmostEqual(row["betrag"], 850.00, places=2)

    def test_freigabe_ohne_gutachten_klasse_erzeugt_registry_default_event(self):
        """P1.5e: auch Nicht-Gutachten-Klassen (abrechnungsschreiben etc.)
        schreiben bei der Freigabe ein Ereignis -- ohne bestaetigte
        kandidaten_ereignisse greift der Registry-Default
        (abrechnungsschreiben -> abrechnung_eingegangen, ohne Positionen)."""
        from backend.db.database import get_connection
        _seed_akte("44/22")
        did = _lege_intake_pdf_an("a")  # klasse=abrechnungsschreiben

        r = self.client.post(
            f"/intake/dokument/{did}/freigabe",
            json={"akte_az": "44/22"}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)

        with get_connection() as conn:
            ereignisse = conn.execute(
                "SELECT ereignistyp FROM ereignisse WHERE akte_az='44/22'"
            ).fetchall()
        self.assertEqual(len(ereignisse), 1)
        self.assertEqual(ereignisse[0]["ereignistyp"], "abrechnung_eingegangen")


class TestVerwerfen(unittest.TestCase):
    """POST /intake/dokument/<id>/verwerfen (Soft-Delete, Migration 53)."""

    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_ohne_grund_400(self):
        did = _lege_intake_pdf_an("a")
        r = self.client.post(
            f"/intake/dokument/{did}/verwerfen",
            json={}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 400)

    def test_ungueltiger_grund_400(self):
        did = _lege_intake_pdf_an("a")
        r = self.client.post(
            f"/intake/dokument/{did}/verwerfen",
            json={"grund": "quatsch"}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 400)

    def test_bereits_freigegeben_409(self):
        did = _lege_intake_pdf_an("a", queue_status="freigegeben")
        r = self.client.post(
            f"/intake/dokument/{did}/verwerfen",
            json={"grund": "spam"}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 409)

    def test_soft_delete_setzt_felder_und_status(self):
        from backend.db.database import get_connection
        did = _lege_intake_pdf_an("a", queue_status="bereit_zur_review")

        r = self.client.post(
            f"/intake/dokument/{did}/verwerfen",
            json={"grund": "duplikat", "kommentar": "kam gestern schon"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        data = r.get_json()
        self.assertTrue(data["verworfen"])
        self.assertEqual(data["verworfen_grund"], "duplikat")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, verworfen_grund, verworfen_am, "
                "       verworfen_von FROM intake_dokumente WHERE id=?",
                (did,),
            ).fetchone()
            log = conn.execute(
                "SELECT feld, wert_alt, wert_neu FROM korrektur_log "
                "WHERE intake_dokument_id=? AND feld='verworfen'",
                (did,),
            ).fetchone()
        # queue_status bleibt unangetastet -- Ausblendung ueber verworfen_am
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        self.assertEqual(row["verworfen_grund"], "duplikat")
        self.assertIsNotNone(row["verworfen_am"])
        # Kommentar landet im korrektur_log als JSON
        self.assertIsNotNone(log)
        self.assertEqual(log["wert_alt"], "bereit_zur_review")
        payload = json.loads(log["wert_neu"])
        self.assertEqual(payload["grund"], "duplikat")
        self.assertEqual(payload["kommentar"], "kam gestern schon")

    def test_verworfene_verschwinden_aus_queue(self):
        did_a = _lege_intake_pdf_an("a", queue_status="bereit_zur_review")
        _lege_intake_pdf_an("b", queue_status="bereit_zur_review")

        r = self.client.post(
            f"/intake/dokument/{did_a}/verwerfen",
            json={"grund": "spam"}, headers=self.headers,
        )
        self.assertEqual(r.status_code, 200)

        r = self.client.get("/intake/queue", headers=self.headers)
        ids = [e["id"] for e in r.get_json()["eintraege"]]
        self.assertNotIn(did_a, ids)
        self.assertEqual(len(ids), 1)


class TestEreignistypen(unittest.TestCase):
    """GET /intake/ereignistypen -- Registry-Katalog fuer Freigabe-Dropdown."""

    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)

    def test_ohne_token_401(self):
        r = self.client.get("/intake/ereignistypen")
        self.assertEqual(r.status_code, 401)

    def test_liefert_alle_typen_und_wirkungen(self):
        r = self.client.get("/intake/ereignistypen", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        typen = data["ereignistypen"]
        self.assertGreaterEqual(len(typen), 5)
        # Struktur je Eintrag
        eintrag = typen[0]
        for feld in ("typ", "label", "richtung", "default_wirkung"):
            self.assertIn(feld, eintrag)
        # Kern-Eintraege vorhanden
        typ_namen = {t["typ"] for t in typen}
        for pflicht in ("gutachten_eingegangen", "abrechnung_eingegangen",
                         "rechnung_eingegangen", "pruefbericht_eingegangen",
                         "vollmacht_eingegangen"):
            self.assertIn(pflicht, typ_namen)
        # Wirkungen aus _WIRKUNGEN
        wirkungen = set(data["wirkungen"])
        self.assertIn("gefordert", wirkungen)
        self.assertIn("anerkannt", wirkungen)
        self.assertIn("beleg", wirkungen)

    def test_eingehende_typen_haben_richtung_eingehend(self):
        r = self.client.get("/intake/ereignistypen", headers=self.headers)
        typen = r.get_json()["ereignistypen"]
        eingehend = [t for t in typen if t["richtung"] == "eingehend"]
        # Registry hat 5 eingehende Typen
        self.assertEqual(len(eingehend), 5)


if __name__ == "__main__":
    unittest.main()
