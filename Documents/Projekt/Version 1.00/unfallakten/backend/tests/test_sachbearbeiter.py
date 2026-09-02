"""
Tests für die Sachbearbeiter-Verwaltung (Migration 68, Modul, Endpunkte).
"""

import importlib
import os
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp()


def _setup(test_id: str):
    """Frische DB + Flask-App (Muster: test_dashboard_uebersicht._setup)."""
    db_path = os.path.join(_tmp_dir, f"sb_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters!!"
    os.environ["FLASK_SECRET_KEY"] = "test-flask-secret-key-minimum-32-characters!!"

    import backend.db.database as db_mod
    import backend.db.schema_manager as schema_mod
    import backend.ramicro.sachbearbeiter as sb_mod
    import backend.routers.einstellungen_routes as eins_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as auth_routes_mod
    import backend.app as app_mod

    for m in (db_mod, schema_mod, sb_mod, eins_mod, jwt_mod, mw_mod, svc_mod, auth_routes_mod, app_mod):
        importlib.reload(m)

    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


class TestMigration68(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def test_tabelle_und_elf_startzeilen(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT kuerzel, name, titel, rolle, aktiv, dashboard_vorauswahl, "
                "kalender_name FROM sachbearbeiter ORDER BY sortierung"
            ).fetchall()]

        self.assertEqual(len(rows), 11)
        self.assertEqual([r["kuerzel"] for r in rows][:5], ["AS", "PK", "CO", "MM", "AH"])

        nach_kuerzel = {r["kuerzel"]: r for r in rows}
        self.assertEqual(nach_kuerzel["CS"]["name"], "Carina Salvagnin")
        self.assertEqual(nach_kuerzel["JH"]["name"], "Jochen Hofmann")
        self.assertEqual(nach_kuerzel["JH"]["aktiv"], 0)
        self.assertEqual(nach_kuerzel["TB"]["rolle"], "refa")
        self.assertEqual(nach_kuerzel["AS"]["kalender_name"], "RA.Schatz")
        vorausgewaehlt = {r["kuerzel"] for r in rows if r["dashboard_vorauswahl"]}
        self.assertEqual(vorausgewaehlt, {"AS", "PK", "CO", "MM", "AH"})

    def test_zweiter_lauf_aendert_nichts(self):
        from backend.db.database import get_connection
        from backend.db.schema_manager import _run_migration_68
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET name = 'Geändert' WHERE kuerzel = 'AS'")
            conn.commit()
            _run_migration_68(conn)
            name = conn.execute(
                "SELECT name FROM sachbearbeiter WHERE kuerzel = 'AS'"
            ).fetchone()["name"]
            anzahl = conn.execute("SELECT COUNT(*) AS n FROM sachbearbeiter").fetchone()["n"]
            versionen = conn.execute(
                "SELECT COUNT(*) AS n FROM schema_version WHERE version = 68"
            ).fetchone()["n"]
        self.assertEqual(name, "Geändert")
        self.assertEqual(anzahl, 11)
        self.assertEqual(versionen, 1)

    def test_kalender_name_ist_eindeutig(self):
        import sqlite3
        from backend.db.database import get_connection
        with get_connection() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO sachbearbeiter (kuerzel, name, kalender_name) "
                    "VALUES ('ZZ', 'Doppelkalender', 'RA.Schatz')"
                )


class TestSachbearbeiterModul(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def test_name_kommt_aus_der_tabelle(self):
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        self.assertEqual(hole_sachbearbeiter("AS")["name"], "Andreas Schatz")
        self.assertEqual(hole_sachbearbeiter("as")["titel"], "Rechtsanwalt")

    def test_ausgeschiedener_sachbearbeiter_behaelt_namen_schutzplanke(self):
        """Schutzplanke gegen ein künftiges 'AND aktiv = 1' in der Abfrage.

        JH (Jochen Hofmann) trägt aktiv=0, ignoriert=0 -- 'ausgeschieden',
        nicht 'ignoriert'. hole_sachbearbeiter() MUSS trotzdem den Namen und
        Titel liefern, sonst fallen 2.182 Altakten wieder auf den Platzhalter
        [JH] zurueck (RA-MICRO-Bestandsaufnahme 2026-08-12). Ein naheliegendes
        Aufraeumen der Abfrage in _zeilen() ('AND aktiv = 1' statt nur
        'ignoriert = 0') wuerde diesen Test rot machen, ohne dass die Vollsuite
        sonst etwas merkt.
        """
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        ergebnis = hole_sachbearbeiter("JH")
        self.assertEqual(ergebnis["name"], "Jochen Hofmann")
        self.assertEqual(ergebnis["titel"], "Rechtsanwalt")

    def test_aenderung_wirkt_sofort(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET titel = 'Fachanwalt für Verkehrsrecht' "
                         "WHERE kuerzel = 'AS'")
            conn.commit()
        self.assertEqual(hole_sachbearbeiter("AS")["titel"], "Fachanwalt für Verkehrsrecht")

    def test_unbekanntes_kuerzel_bleibt_platzhalter(self):
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        self.assertEqual(hole_sachbearbeiter("XY")["name"], "[XY]")

    def test_ignoriertes_kuerzel_liefert_platzhalter(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        with get_connection() as conn:
            conn.execute("INSERT INTO sachbearbeiter (kuerzel, name, aktiv, ignoriert) "
                         "VALUES ('ME', 'ME', 0, 1)")
            conn.commit()
        self.assertEqual(hole_sachbearbeiter("ME")["name"], "[ME]")

    def test_leeres_kuerzel_liefert_kanzlei(self):
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        self.assertIn("Koch, Schatz", hole_sachbearbeiter("")["name"])

    def test_nur_aktive_ohne_ausgeschiedene_und_ignorierte(self):
        from backend.ramicro.sachbearbeiter import alle_sachbearbeiter
        kuerzel = [e["kuerzel"] for e in alle_sachbearbeiter(nur_aktive=True)]
        self.assertIn("AS", kuerzel)
        self.assertNotIn("JH", kuerzel)
        self.assertEqual(kuerzel, sorted(kuerzel, key=lambda k: kuerzel.index(k)))

    def test_kalender_mapping_aus_der_tabelle(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import kalender_zu_kuerzel
        self.assertEqual(kalender_zu_kuerzel()["RA.Schatz"], "AS")
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET kalender_name = 'T. Brunner' "
                         "WHERE kuerzel = 'TB'")
            conn.commit()
        self.assertEqual(kalender_zu_kuerzel()["T. Brunner"], "TB")

    def test_kalender_mapping_ausgeschiedener_sachbearbeiter_bleibt_erhalten(self):
        """Schutzplanke für die DECISIONS.md-Entscheidung zu kalender_zu_kuerzel().

        Termine aus dem RA-MICRO-Kalender eines ausgeschiedenen Kollegen
        (aktiv=0, ignoriert=0) sollen weiterhin der richtigen Akte zugeordnet
        werden -- kalender_zu_kuerzel() darf also NICHT nach aktiv filtern.
        JH (Jochen Hofmann) ist im Seed aktiv=0; hier bekommt er testweise
        einen Kalendernamen, den die Zuordnung trotzdem liefern muss.
        """
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import kalender_zu_kuerzel
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET kalender_name = 'J. Hofmann' "
                         "WHERE kuerzel = 'JH'")
            conn.commit()
        self.assertEqual(kalender_zu_kuerzel()["J. Hofmann"], "JH")

    def test_fallback_wenn_tabelle_fehlt(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        with get_connection() as conn:
            conn.execute("DROP TABLE sachbearbeiter")
            conn.commit()
        self.assertEqual(hole_sachbearbeiter("AS")["name"], "Andreas Schatz")

    def test_fallback_vorauswahl_deckt_sich_mit_dem_seed(self):
        """Fallback-Liste (Bestands-DB ohne Migration 68) muss dieselbe
        Dashboard-Vorauswahl tragen wie die Startzeilen der Tabelle, sonst
        waehlt die Tagesuebersicht ohne gespeicherte Auswahl entweder gar
        niemanden (Frist-Verlust) oder -- seit dem Frontend-Fix -- alle zehn
        statt der fuenf kuratierten Anwaelte.
        """
        from backend.ramicro.sachbearbeiter import alle_sachbearbeiter
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("DROP TABLE sachbearbeiter")
            conn.commit()
        vorausgewaehlt = {e["kuerzel"] for e in alle_sachbearbeiter() if e["dashboard_vorauswahl"]}
        self.assertEqual(vorausgewaehlt, {"AS", "PK", "CO", "MM", "AH"})


class TestKalenderMapping(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def _auth_header(self):
        """Gibt Authorization-Header mit gültigem Token zurück."""
        r = self.client.post("/auth/login", json={
            "email": "admin@test.de", "passwort": "Admin123!"
        })
        if r.status_code != 200:
            raise RuntimeError(f"Login failed: {r.status_code} - {r.get_json()}")
        data = r.get_json()
        return {"Authorization": f"Bearer {data['access_token']}"}

    def test_dashboard_hat_keine_hartcodierte_kalenderliste_mehr(self):
        import backend.routers.dashboard_routes as dash
        self.assertFalse(hasattr(dash, "_KALENDER_ZU_SB"))

    def test_termine_nutzen_das_mapping_aus_der_tabelle(self):
        from backend.db.database import get_connection
        from backend.ramicro.sachbearbeiter import kalender_zu_kuerzel
        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET kalender_name = 'S. Koch' "
                         "WHERE kuerzel = 'SK'")
            conn.commit()
        self.assertEqual(kalender_zu_kuerzel().get("S. Koch"), "SK")

    def test_endpoint_termine_heute_nutzt_kalender_mapping_bekannt(self):
        """Integration: GET /dashboard/termine-heute mit bekanntem Kalendernamen."""
        from datetime import datetime
        from unittest.mock import patch, MagicMock
        from backend.db.database import get_connection

        with get_connection() as conn:
            conn.execute("UPDATE sachbearbeiter SET kalender_name = 'S. Koch' "
                         "WHERE kuerzel = 'SK'")
            conn.commit()

        headers = self._auth_header()
        heute = datetime.now()

        mock_cursor = MagicMock()
        mock_row = {
            "StartDateTime": heute,
            "Subject": "Termin",
            "Aktennummer": "123/26",
            "Aktenkurzbezeichnung": "Test-Akte",
            "IsGerichtstermin": False,
            "GerichtName": None,
            "CalendarName": "S. Koch",
        }
        mock_cursor.fetchall.return_value = [mock_row]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None

        with patch("backend.routers.dashboard_routes.get_ramicro_connection", return_value=mock_conn):
            resp = self.client.get("/dashboard/termine-heute", headers=headers)
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertGreater(len(data["eintraege"]), 0)
            eintrag = data["eintraege"][0]
            self.assertEqual(eintrag["az"], "123/26SK",
                           f"Erwartet '123/26SK', erhalten '{eintrag['az']}'")
            self.assertEqual(eintrag["sb"], "SK")

    def test_endpoint_termine_heute_uebergeht_unbekannten_kalender(self):
        """Ein Kalender ohne Sachbearbeiter-Zuordnung liefert keinen Termin.

        Gepflegt sind nur die Anwaltskalender; die Angestellten arbeiten
        ausschließlich mit Wiedervorlagen. Termine aus fremden Kalendern
        (ReferendarIn, Verwalter, Poolkalender) würden sonst jeden
        SB-Filter der Tagesübersicht ungefiltert passieren.
        """
        from datetime import datetime
        from unittest.mock import patch, MagicMock

        headers = self._auth_header()
        heute = datetime.now()

        mock_cursor = MagicMock()
        mock_row = {
            "EventUid": "11111111-2222-3333-4444-555555555555",
            "StartDateTime": heute,
            "Subject": "Termin",
            "Summary": "456/26 Andere-Akte",
            "Location": None,
            "Notes": "",
            "Aktennummer": "456/26",
            "Aktenkurzbezeichnung": "Andere-Akte",
            "IsGerichtstermin": False,
            "GerichtName": None,
            "CalendarName": "Unbekannter Kalendername",
        }
        # Erste Abfrage: raKalender.dbo.Events, zweite: tblAktenWiedervorlagen
        mock_cursor.fetchall.side_effect = [[mock_row], []]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None

        with patch("backend.routers.dashboard_routes.get_ramicro_connection", return_value=mock_conn):
            resp = self.client.get("/dashboard/termine-heute", headers=headers)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()["eintraege"], [])


class TestSachbearbeiterEndpunkte(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def _header(self):
        r = self.client.post("/auth/login", json={
            "email": "admin@test.de", "passwort": "Admin123!"})
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def test_liste_liefert_alle_inklusive_inaktiver(self):
        r = self.client.get("/einstellungen/sachbearbeiter", headers=self._header())
        self.assertEqual(r.status_code, 200)
        eintraege = r.get_json()["eintraege"]
        self.assertEqual(len(eintraege), 11)
        jh = next(e for e in eintraege if e["kuerzel"] == "JH")
        self.assertFalse(jh["aktiv"])
        self.assertEqual(eintraege[0]["kuerzel"], "AS")

    def test_ohne_token_401(self):
        self.assertEqual(self.client.get("/einstellungen/sachbearbeiter").status_code, 401)

    def test_liste_faellt_auf_eingebaute_liste_zurueck_wenn_tabelle_fehlt(self):
        """GET muss über alle_sachbearbeiter() laufen, nicht über eine eigene Abfrage.

        Bestands-Datenbanken ohne Migration 68 haben die Tabelle 'sachbearbeiter'
        noch nicht -- der Reiter UND die Chips der Tagesübersicht sollen dann die
        eingebaute Fallback-Liste zeigen statt eines Serverfehlers.
        """
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute("DROP TABLE sachbearbeiter")
            conn.commit()
        r = self.client.get("/einstellungen/sachbearbeiter", headers=self._header())
        self.assertEqual(r.status_code, 200)
        eintraege = r.get_json()["eintraege"]
        self.assertGreater(len(eintraege), 0)
        self.assertIn("AS", [e["kuerzel"] for e in eintraege])
        self.assertIn("geaendert_am", eintraege[0])

    def test_anlegen_und_wieder_lesen(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(), json={
            "kuerzel": "XX", "name": "Neue Kollegin", "titel": "Rechtsanwältin",
            "anrede": "frau", "rolle": "anwalt", "aktiv": True,
            "dashboard_vorauswahl": True, "sortierung": 55})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["eintrag"]["name"], "Neue Kollegin")
        liste = self.client.get("/einstellungen/sachbearbeiter",
                                headers=self._header()).get_json()["eintraege"]
        self.assertIn("XX", [e["kuerzel"] for e in liste])

    def test_kuerzel_muss_genau_zwei_grossbuchstaben_sein(self):
        for falsch in ("A", "ABC", "a1", "12"):
            r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                                 json={"kuerzel": falsch, "name": "Test"})
            self.assertEqual(r.status_code, 400, falsch)
            self.assertIn("Kürzel", r.get_json()["fehler"])

    def test_doppeltes_kuerzel_409(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "AS", "name": "Doppelt"})
        self.assertEqual(r.status_code, 409)

    def test_leerer_name_400(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "XX", "name": "   "})
        self.assertEqual(r.status_code, 400)

    def test_unbekannte_rolle_oder_anrede_400(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "XX", "name": "Test", "rolle": "chef"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(),
                             json={"kuerzel": "XY", "name": "Test", "anrede": "divers"})
        self.assertEqual(r.status_code, 400)

    def test_doppelter_kalendername_400(self):
        r = self.client.put("/einstellungen/sachbearbeiter/TB", headers=self._header(),
                            json={"kalender_name": "RA.Schatz"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Kalender", r.get_json()["fehler"])

    def test_aendern_setzt_geaendert_am(self):
        r = self.client.put("/einstellungen/sachbearbeiter/AS", headers=self._header(),
                            json={"titel": "Fachanwalt für Verkehrsrecht", "aktiv": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["eintrag"]["titel"], "Fachanwalt für Verkehrsrecht")
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute("SELECT geaendert_am FROM sachbearbeiter "
                               "WHERE kuerzel = 'AS'").fetchone()
        self.assertIsNotNone(row["geaendert_am"])

    def test_aendern_unbekannt_404(self):
        r = self.client.put("/einstellungen/sachbearbeiter/ZZ", headers=self._header(),
                            json={"name": "Niemand"})
        self.assertEqual(r.status_code, 404)

    def test_loeschen(self):
        self.assertEqual(
            self.client.delete("/einstellungen/sachbearbeiter/SN",
                               headers=self._header()).status_code, 200)
        liste = self.client.get("/einstellungen/sachbearbeiter",
                                headers=self._header()).get_json()["eintraege"]
        self.assertNotIn("SN", [e["kuerzel"] for e in liste])
        self.assertEqual(
            self.client.delete("/einstellungen/sachbearbeiter/SN",
                               headers=self._header()).status_code, 404)

    def test_kalender_name_null_entfernt_zuordnung(self):
        r = self.client.put("/einstellungen/sachbearbeiter/AS", headers=self._header(),
                            json={"kalender_name": None})
        self.assertEqual(r.status_code, 200)
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute("SELECT kalender_name FROM sachbearbeiter "
                               "WHERE kuerzel = 'AS'").fetchone()
        self.assertIsNone(row["kalender_name"])

    def test_freigewordener_kalendername_kann_neu_vergeben_werden(self):
        r = self.client.put("/einstellungen/sachbearbeiter/AS", headers=self._header(),
                            json={"kalender_name": None})
        self.assertEqual(r.status_code, 200)

        r = self.client.put("/einstellungen/sachbearbeiter/TB", headers=self._header(),
                            json={"kalender_name": "RA.Schatz"})
        self.assertEqual(r.status_code, 200)

        r = self.client.put("/einstellungen/sachbearbeiter/AS", headers=self._header(),
                            json={"kalender_name": "Schatz.Neu"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["eintrag"]["kalender_name"], "Schatz.Neu")

    def test_mehrere_zeilen_koennen_kalender_name_gleichzeitig_entfernen(self):
        """Kein Geisterkonflikt: zwei mit null geleerte Zeilen dürfen nicht
        über den Text 'None' aneinander kollidieren."""
        r = self.client.put("/einstellungen/sachbearbeiter/AS", headers=self._header(),
                            json={"kalender_name": None})
        self.assertEqual(r.status_code, 200)
        r = self.client.put("/einstellungen/sachbearbeiter/PK", headers=self._header(),
                            json={"kalender_name": None})
        self.assertEqual(r.status_code, 200)

    def test_name_null_400(self):
        r = self.client.put("/einstellungen/sachbearbeiter/AS", headers=self._header(),
                            json={"name": None})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Name", r.get_json()["fehler"])

    def test_anlegen_ignorierte_zeile(self):
        r = self.client.post("/einstellungen/sachbearbeiter", headers=self._header(), json={
            "kuerzel": "ME", "name": "ME", "aktiv": False, "ignoriert": True})
        self.assertEqual(r.status_code, 201)
        liste = self.client.get("/einstellungen/sachbearbeiter",
                                headers=self._header()).get_json()["eintraege"]
        me = next(e for e in liste if e["kuerzel"] == "ME")
        self.assertFalse(me["aktiv"])
        self.assertTrue(me["ignoriert"])

        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        ergebnis = hole_sachbearbeiter("ME")
        self.assertEqual(ergebnis["name"], "[ME]")

    def test_aktiv_setzen_hebt_ignoriert_wieder_auf(self):
        """PUT auf aktiv=true muss eine ignorierte Zeile wieder verwendbar machen.

        Sonst sieht die Zeile im Reiter vollwertig aus (aktiv, mit Namen),
        bleibt aber ueberall wirkungslos: hole_sachbearbeiter() liefert
        weiter [ME], weil ignoriert=1 stehen bleibt -- eine Sackgasse ohne
        direkten Datenbankeingriff.
        """
        self.client.post("/einstellungen/sachbearbeiter", headers=self._header(), json={
            "kuerzel": "ME", "name": "ME", "aktiv": False, "ignoriert": True})

        r = self.client.put("/einstellungen/sachbearbeiter/ME", headers=self._header(), json={
            "name": "Maria Ehlert", "aktiv": True})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["eintrag"]["ignoriert"])

        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT ignoriert FROM sachbearbeiter WHERE kuerzel = 'ME'").fetchone()
        self.assertEqual(row["ignoriert"], 0)

        from backend.ramicro.sachbearbeiter import hole_sachbearbeiter
        self.assertEqual(hole_sachbearbeiter("ME")["name"], "Maria Ehlert")


class TestRamicroAbgleich(unittest.TestCase):

    def setUp(self):
        self.client = _setup(self._testMethodName)

    def _header(self):
        r = self.client.post("/auth/login", json={
            "email": "admin@test.de", "passwort": "Admin123!"})
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def test_ohne_ramicro_verfuegbar_false(self):
        from unittest.mock import patch
        from backend.ramicro.connector import RaMicroVerbindungsFehler
        with patch("backend.ramicro.connector.get_ramicro_connection",
                   side_effect=RaMicroVerbindungsFehler("offline")):
            r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                headers=self._header())
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["verfuegbar"])
        self.assertEqual(r.get_json()["unbekannt"], [])

    def test_unbekannte_kuerzel_werden_gemeldet(self):
        from contextlib import contextmanager
        from unittest.mock import patch

        class _Cursor:
            def execute(self, *a, **k): pass
            def fetchall(self):
                return [{"k": "AS", "n": 3201}, {"k": "ME", "n": 20}, {"k": "JH", "n": 2182}]

        class _Conn:
            def cursor(self): return _Cursor()

        @contextmanager
        def _fake():
            yield _Conn()

        with patch("backend.ramicro.connector.get_ramicro_connection", _fake):
            r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                headers=self._header())
        daten = r.get_json()
        self.assertTrue(daten["verfuegbar"])
        self.assertEqual(daten["kuerzel"]["AS"], 3201)
        self.assertEqual(daten["unbekannt"], [{"kuerzel": "ME", "akten": 20}])

    def test_ignoriertes_kuerzel_gilt_als_bekannt(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        from backend.db.database import get_connection

        with get_connection() as conn:
            conn.execute("INSERT INTO sachbearbeiter (kuerzel, name, aktiv, ignoriert) "
                         "VALUES ('ME', 'ME', 0, 1)")
            conn.commit()

        class _Cursor:
            def execute(self, *a, **k): pass
            def fetchall(self): return [{"k": "ME", "n": 20}]

        class _Conn:
            def cursor(self): return _Cursor()

        @contextmanager
        def _fake():
            yield _Conn()

        with patch("backend.ramicro.connector.get_ramicro_connection", _fake):
            r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                headers=self._header())
        self.assertEqual(r.get_json()["unbekannt"], [])

    def test_unerwarteter_fehler_wird_als_error_geloggt(self):
        from contextlib import contextmanager
        from unittest.mock import patch

        class _Cursor:
            def execute(self, *a, **k): pass
            def fetchall(self): return [{"falscher_schluessel": "AS", "n": 3201}]

        class _Conn:
            def cursor(self): return _Cursor()

        @contextmanager
        def _fake():
            yield _Conn()

        with patch("backend.ramicro.connector.get_ramicro_connection", _fake):
            with self.assertLogs("backend.routers.einstellungen_routes", level="ERROR") as protokoll:
                r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                    headers=self._header())
        self.assertEqual(r.status_code, 200)
        daten = r.get_json()
        self.assertFalse(daten["verfuegbar"])
        self.assertEqual(daten["kuerzel"], {})
        self.assertEqual(daten["unbekannt"], [])
        self.assertTrue(any(satz.levelname == "ERROR" for satz in protokoll.records))

    def test_verbindungsfehler_wird_nicht_als_error_geloggt(self):
        from unittest.mock import patch
        from backend.ramicro.connector import RaMicroVerbindungsFehler

        with patch("backend.ramicro.connector.get_ramicro_connection",
                   side_effect=RaMicroVerbindungsFehler("offline")):
            with self.assertLogs("backend.routers.einstellungen_routes", level="WARNING") as protokoll:
                r = self.client.get("/einstellungen/sachbearbeiter/ramicro-abgleich",
                                    headers=self._header())
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["verfuegbar"])
        self.assertTrue(all(satz.levelname != "ERROR" for satz in protokoll.records))


if __name__ == "__main__":
    unittest.main()
