"""
Abrechnungs-Vorschlaege aus freigegebenen Abrechnungsschreiben.

Die Review-Freigabe schreibt fuer ``abrechnung_eingegangen`` bewusst kein
Positions-Ereignis (erzeuge_aus_freigabe kennt nur Gutachten + Rechnung).
Die geparsten Betraege werden daher als *Vorschlag* angeboten, den der
Sachbearbeiter in der Regulierung bestaetigt.
"""
import importlib
import json
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="abr_vorschlag_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"av_{test_id}.db")
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


# Echte AXA-Felder aus Akte 589/26 (Schreiben vom 30.06.2026)
_FELDER_AXA = {
    "versicherer": "AXA Versicherung AG",
    "versicherer_kuerzel": "AXA",
    "schadennummer": "90000810441",
    "schreibdatum": "2026-06-30",
    "abrechnungsart": "fiktive Abrechnung",
    "gesamtbetrag": 3719.53,
    "positionen": [
        {"text": "fiktive Abrechnung", "betrag": 2697.19},
        {"text": "Sachverständigenkosten", "betrag": 992.34},
        {"text": "Auslagenpauschale", "betrag": 30.0},
    ],
    "zahlungen": [],
}

# Schreiben vom 28.07.2026 - LLM liefert hier "beschreibung" statt "text"
_FELDER_AXA_2 = {
    "versicherer": "AXA Versicherung AG",
    "schadennummer": "90000810441",
    "schreibdatum": "2026-07-28",
    "gesamtbetrag": 201.758,
    "positionen": [
        {"beschreibung": "Nutzungsausfallentschädigung", "betrag": 43},
        {"beschreibung": "Kosten für die Erstellung der "
                         "Reparaturbestätigung", "betrag": 29.75},
    ],
    "zahlungen": [{"betrag": 201.758}],
}

_UNBEKANNTES_LABEL = ("Kosten für die Erstellung der "
                      "Reparaturbestätigung")


def _seed_akte(az="589/26"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2026-06-24', 'offen')", (az,),
        )
        conn.commit()


def _seed_abrechnungsdokument(az, sha, felder, bezeichnung,
                              warnungen=None, in_intake=True):
    """Legt ein freigegebenes Abrechnungsschreiben an.

    in_intake=True bildet den Regelfall ab: das Parse-Ergebnis liegt in
    intake_dokumente, dokumente.parse_json ist leer.
    """
    from backend.db.database import get_connection
    parse = {"felder": felder}
    if warnungen:
        parse["validierung_warnungen"] = warnungen
    parse_json = json.dumps(parse, ensure_ascii=False)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO dokumente "
            "(akte_id, dateiname, dateipfad, dateityp, typ, dokumentenklasse, "
            " bezeichnung, parse_json) "
            "VALUES (?, ?, 'x', 'pdf', 'abrechnungsschreiben', "
            "'abrechnungsschreiben', ?, ?)",
            (az, sha + ".pdf", bezeichnung,
             None if in_intake else parse_json),
        )
        dok_id = cur.lastrowid
        if in_intake:
            cur2 = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, arbeitskopie_pfad, klasse, klasse_quelle, konfidenz,"
                " queue_status, parse_json, registry_version, bezeichnung) "
                "VALUES (?, '/tmp/x.pdf', 'abrechnungsschreiben', 'manuell', "
                "0.95, 'freigegeben', ?, 'v1', ?)",
                (sha, parse_json, bezeichnung),
            )
            conn.execute(
                "INSERT INTO freigaben "
                "(intake_dokument_id, akte_az, dokument_id, freigegeben_von) "
                "VALUES (?, ?, ?, 1)",
                (cur2.lastrowid, az, dok_id),
            )
        conn.commit()
        return dok_id


class TestSynonymFiktiveAbrechnung(unittest.TestCase):

    def test_fiktive_abrechnung_auf_fahrzeugschaden(self):
        _setup("synonym")
        from backend.services.kuerzungstyp_matching import (
            normalisiere_positionslabel)
        self.assertEqual(
            normalisiere_positionslabel("fiktive Abrechnung"),
            "fahrzeugschaden")


class TestBaueVorschlaege(unittest.TestCase):

    def test_labels_werden_auf_position_keys_abgebildet(self):
        _setup("mapping")
        _seed_akte()
        dok_id = _seed_abrechnungsdokument(
            "589/26", "a" * 64, _FELDER_AXA,
            "Abrechnungsschreiben AXA vom 30.06.2026")

        from backend.services.abrechnung_vorschlag import baue_vorschlaege
        vs = baue_vorschlaege("589/26")

        self.assertEqual(len(vs), 1)
        v = vs[0]
        self.assertEqual(v["dokument_id"], dok_id)
        self.assertEqual(v["datum"], "2026-06-30")
        self.assertEqual(v["versicherung"], "AXA Versicherung AG")
        self.assertEqual(v["referenz_nr"], "90000810441")
        self.assertAlmostEqual(v["gesamtbetrag"], 3719.53, places=2)
        self.assertEqual(
            [(p["position_key"], p["roh_label"], p["betrag_reguliert"])
             for p in v["positionen"]],
            [("fahrzeugschaden", "fiktive Abrechnung", 2697.19),
             ("sv_kosten", "Sachverständigenkosten", 992.34),
             ("kostenpauschale", "Auslagenpauschale", 30.0)],
        )

    def test_unbekanntes_label_bleibt_ohne_position_key(self):
        _setup("unbekannt")
        _seed_akte()
        _seed_abrechnungsdokument(
            "589/26", "b" * 64, _FELDER_AXA_2,
            "Abrechnungsschreiben AXA vom 28.07.2026",
            warnungen=["Summe der Positionen weicht ab"])

        from backend.services.abrechnung_vorschlag import baue_vorschlaege
        v = baue_vorschlaege("589/26")[0]

        keys = {p["roh_label"]: p["position_key"] for p in v["positionen"]}
        self.assertEqual(keys["Nutzungsausfallentschädigung"],
                         "nutzungsausfall")
        self.assertIsNone(keys[_UNBEKANNTES_LABEL])
        self.assertEqual(v["warnungen"], ["Summe der Positionen weicht ab"])

    def test_parse_json_am_dokument_wird_genutzt(self):
        """Per PDF-Import geparste Dokumente tragen das Ergebnis selbst."""
        _setup("direkt")
        _seed_akte()
        _seed_abrechnungsdokument(
            "589/26", "c" * 64, _FELDER_AXA,
            "Abrechnungsschreiben AXA vom 30.06.2026", in_intake=False)

        from backend.services.abrechnung_vorschlag import baue_vorschlaege
        v = baue_vorschlaege("589/26")[0]
        self.assertEqual(len(v["positionen"]), 3)

    def test_bereits_erfasstes_schreiben_wird_nicht_vorgeschlagen(self):
        _setup("erfasst")
        _seed_akte()
        dok_id = _seed_abrechnungsdokument(
            "589/26", "d" * 64, _FELDER_AXA,
            "Abrechnungsschreiben AXA vom 30.06.2026")

        from backend.models.abrechnungsschreiben import (
            erstelle_abrechnungsschreiben)
        erstelle_abrechnungsschreiben(
            akte_id="589/26", datum="2026-06-30", haftungsart="vollhaftung",
            haftungsquote=100.0, bearbeiter_id=1, dokument_id=dok_id,
            positionen=[{"position_key": "sv_kosten",
                         "betrag_gefordert": 992.34,
                         "betrag_reguliert": 992.34}],
        )

        from backend.services.abrechnung_vorschlag import baue_vorschlaege
        self.assertEqual(baue_vorschlaege("589/26"), [])

    def test_dokument_ohne_positionen_liefert_keinen_vorschlag(self):
        _setup("leer")
        _seed_akte()
        _seed_abrechnungsdokument(
            "589/26", "e" * 64,
            {"versicherer": "AXA", "schreibdatum": "2026-06-30",
             "positionen": []},
            "Abrechnungsschreiben AXA vom 30.06.2026")

        from backend.services.abrechnung_vorschlag import baue_vorschlaege
        self.assertEqual(baue_vorschlaege("589/26"), [])


class TestVorschlagRoute(unittest.TestCase):

    def test_route_liefert_vorschlaege(self):
        client = _setup("route")
        kopf = _auth_header(client)
        _seed_akte()
        _seed_abrechnungsdokument(
            "589/26", "f" * 64, _FELDER_AXA,
            "Abrechnungsschreiben AXA vom 30.06.2026")

        r = client.get("/akten/589/26/abrechnungen/vorschlaege", headers=kopf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        daten = r.get_json()
        self.assertEqual(len(daten["vorschlaege"]), 1)
        self.assertEqual(daten["vorschlaege"][0]["bezeichnung"],
                         "Abrechnungsschreiben AXA vom 30.06.2026")

    def test_akte_ohne_abrechnungsschreiben_liefert_leere_liste(self):
        # pruefe_akte laesst Akten durch, die nur in RA-MICRO existieren
        # (_helpers.pruefe_akte) -- erwartet wird daher 200 mit leerer Liste.
        client = _setup("routeleer")
        kopf = _auth_header(client)
        r = client.get("/akten/999/99/abrechnungen/vorschlaege", headers=kopf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["vorschlaege"], [])


if __name__ == "__main__":
    unittest.main()
