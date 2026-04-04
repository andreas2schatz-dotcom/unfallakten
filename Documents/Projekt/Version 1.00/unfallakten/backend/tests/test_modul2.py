"""
Modul 2 – Unit-Tests
=====================
Vollständige Testabdeckung für:
  - JWT-Token-Erstellung und Validierung
  - Eingabe-Validierung
  - Auth-Service (Login, Register, Refresh, Passwortänderung)
  - Flask-Routen (Integration)
  - Middleware (Dekoratoren)

Jeder Test benutzt eine frische Datenbank.
"""

import os
import sys
import unittest
import json
import tempfile
import time

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    """Richtet eine frische DB + Flask-App für einen Test ein."""
    db_path = os.path.join(_tmp_dir, f"m2_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-characters!!"

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.schaden as schaden_mod
    import backend.models.dokument as dok_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as routes_mod
    import backend.app as app_mod

    for m in (db_mod, sm_mod, ben_mod, akte_mod, schaden_mod,
              dok_mod, jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
        importlib.reload(m)

    app = app_mod.erstelle_app()
    app.config["TESTING"] = True
    client = app.test_client()

    return client, jwt_mod, svc_mod


# ══════════════════════════════════════════════════════════════════════════════
# JWT TOKEN TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestJWTTokens(unittest.TestCase):

    def setUp(self):
        _, self.jwt, _ = _setup(f"jwt_{self._testMethodName}")

    def test_access_token_erstellen(self):
        token = self.jwt.erstelle_access_token(1, "admin")
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) > 50)

    def test_refresh_token_erstellen(self):
        token = self.jwt.erstelle_refresh_token(1)
        self.assertIsInstance(token, str)

    def test_token_paar_enthält_beide_tokens(self):
        paar = self.jwt.erstelle_token_paar(1, "sachbearbeiter")
        self.assertIn("access_token", paar)
        self.assertIn("refresh_token", paar)
        self.assertEqual(paar["token_type"], "Bearer")
        self.assertIn("expires_in", paar)

    def test_access_token_validierung(self):
        token = self.jwt.erstelle_access_token(42, "admin")
        payload = self.jwt.validiere_access_token(token)
        self.assertEqual(payload["sub"], "42")
        self.assertEqual(payload["rolle"], "admin")
        self.assertEqual(payload["typ"], "access")

    def test_refresh_token_validierung(self):
        token = self.jwt.erstelle_refresh_token(7)
        payload = self.jwt.validiere_refresh_token(token)
        self.assertEqual(payload["sub"], "7")
        self.assertEqual(payload["typ"], "refresh")

    def test_access_token_mit_falschem_secret_ungueltig(self):
        import jwt as pyjwt
        token = pyjwt.encode(
            {"sub": "1", "typ": "access", "rolle": "admin",
             "iat": 0, "exp": 9999999999},
            "falsches-secret", algorithm="HS256"
        )
        with self.assertRaises(self.jwt.TokenUngueltig):
            self.jwt.validiere_access_token(token)

    def test_refresh_token_als_access_abgelehnt(self):
        """Refresh Token darf nicht als Access Token akzeptiert werden."""
        token = self.jwt.erstelle_refresh_token(1)
        with self.assertRaises(self.jwt.TokenTypFehler):
            self.jwt.validiere_access_token(token)

    def test_access_token_als_refresh_abgelehnt(self):
        token = self.jwt.erstelle_access_token(1, "admin")
        with self.assertRaises(self.jwt.TokenTypFehler):
            self.jwt.validiere_refresh_token(token)

    def test_abgelaufener_token(self):
        import jwt as pyjwt
        from datetime import datetime, timezone, timedelta
        token = pyjwt.encode(
            {"sub": "1", "typ": "access", "rolle": "admin",
             "iat": datetime.now(timezone.utc) - timedelta(hours=2),
             "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            os.environ["JWT_SECRET_KEY"], algorithm="HS256"
        )
        with self.assertRaises(self.jwt.TokenAbgelaufen):
            self.jwt.validiere_access_token(token)

    def test_benutzer_id_extraktion(self):
        token = self.jwt.erstelle_access_token(99, "sachbearbeiter")
        bid = self.jwt.hole_benutzer_id_aus_token(token)
        self.assertEqual(bid, 99)

    def test_benutzer_id_ungültiger_token_none(self):
        bid = self.jwt.hole_benutzer_id_aus_token("komplett.ungueltig.token")
        self.assertIsNone(bid)


# ══════════════════════════════════════════════════════════════════════════════
# VALIDIERUNGS-TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestValidierung(unittest.TestCase):

    def setUp(self):
        from backend.auth.validierung import (
            validiere_email, validiere_passwort, validiere_name,
            validiere_rolle, validiere_registrierung, validiere_login,
            Validierungsfehler
        )
        self.ve = validiere_email
        self.vp = validiere_passwort
        self.vn = validiere_name
        self.vr = validiere_rolle
        self.vreg = validiere_registrierung
        self.vlog = validiere_login
        self.VF = Validierungsfehler

    def test_gueltige_email(self):
        self.assertEqual(self.ve("Test@Example.COM"), "test@example.com")

    def test_ungueltige_email(self):
        for email in ["", "kein-at", "@domain.de", "x@", "x@x"]:
            with self.assertRaises(self.VF, msg=f"Sollte fehlschlagen: {email!r}"):
                self.ve(email)

    def test_gültiges_passwort(self):
        self.assertEqual(self.vp("Sicher1!"), "Sicher1!")

    def test_passwort_zu_kurz(self):
        with self.assertRaises(self.VF):
            self.vp("Ab1")

    def test_passwort_ohne_grossbuchstabe(self):
        with self.assertRaises(self.VF):
            self.vp("klein123")

    def test_passwort_ohne_zahl(self):
        with self.assertRaises(self.VF):
            self.vp("KeinZahl!")

    def test_gueltiger_name(self):
        self.assertEqual(self.vn("  Hans  "), "Hans")

    def test_name_zu_kurz(self):
        with self.assertRaises(self.VF):
            self.vn("X")

    def test_gueltuge_rollen(self):
        self.assertEqual(self.vr("admin"), "admin")
        self.assertEqual(self.vr("sachbearbeiter"), "sachbearbeiter")

    def test_ungueltige_rolle(self):
        with self.assertRaises(self.VF):
            self.vr("superuser")

    def test_registrierung_komplett(self):
        result = self.vreg({
            "name": "Max Müller", "email": "max@k.de",
            "passwort": "Sicher1!", "rolle": "sachbearbeiter"
        })
        self.assertEqual(result["email"], "max@k.de")

    def test_login_valide(self):
        result = self.vlog({"email": "a@b.de", "passwort": "pw"})
        self.assertEqual(result["email"], "a@b.de")

    def test_login_ohne_email_fehler(self):
        with self.assertRaises(self.VF):
            self.vlog({"passwort": "pw"})


# ══════════════════════════════════════════════════════════════════════════════
# FLASK-ROUTEN-TESTS (Integration)
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthRouten(unittest.TestCase):
    """Integration-Tests für alle Auth-Endpunkte."""

    def setUp(self):
        self.client, self.jwt, _ = _setup(f"routes_{self._testMethodName}")
        # Ersten Admin anlegen
        self.client.post("/auth/register/erster", json={
            "name": "Admin Koch", "email": "admin@k.de", "passwort": "Admin123!"
        })

    def _login(self, email="admin@k.de", passwort="Admin123!") -> dict:
        r = self.client.post("/auth/login", json={
            "email": email, "passwort": passwort
        })
        return r.get_json()

    def _auth_header(self, email="admin@k.de", passwort="Admin123!") -> dict:
        data = self._login(email, passwort)
        return {"Authorization": f"Bearer {data['access_token']}"}

    # ── Ping ──────────────────────────────────────────────────────────────────

    def test_ping_ohne_token(self):
        r = self.client.get("/auth/ping")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    # ── Erster Benutzer ───────────────────────────────────────────────────────

    def test_erster_benutzer_nur_einmal(self):
        r = self.client.post("/auth/register/erster", json={
            "name": "Zweiter", "email": "zweiter@k.de", "passwort": "Admin123!"
        })
        self.assertEqual(r.status_code, 409)

    # ── Login ─────────────────────────────────────────────────────────────────

    def test_login_erfolgreich(self):
        r = self.client.post("/auth/login", json={
            "email": "admin@k.de", "passwort": "Admin123!"
        })
        data = r.get_json()
        self.assertEqual(r.status_code, 200)
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertIn("benutzer", data)
        self.assertEqual(data["benutzer"]["rolle"], "admin")

    def test_login_falsches_passwort(self):
        r = self.client.post("/auth/login", json={
            "email": "admin@k.de", "passwort": "FalschesPasswort1!"
        })
        self.assertEqual(r.status_code, 401)

    def test_login_unbekannte_email(self):
        r = self.client.post("/auth/login", json={
            "email": "niemand@k.de", "passwort": "Admin123!"
        })
        self.assertEqual(r.status_code, 401)

    def test_login_kein_body(self):
        r = self.client.post("/auth/login", json={})
        self.assertEqual(r.status_code, 422)

    # ── Registrierung ─────────────────────────────────────────────────────────

    def test_register_als_admin(self):
        headers = self._auth_header()
        r = self.client.post("/auth/register", json={
            "name": "Neuer SB", "email": "sb@k.de",
            "passwort": "Sachb123!", "rolle": "sachbearbeiter"
        }, headers=headers)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["rolle"], "sachbearbeiter")

    def test_register_ohne_token_verboten(self):
        r = self.client.post("/auth/register", json={
            "name": "X", "email": "x@k.de", "passwort": "Xtest1234!"
        })
        self.assertEqual(r.status_code, 401)

    def test_register_doppelte_email(self):
        headers = self._auth_header()
        self.client.post("/auth/register", json={
            "name": "SB", "email": "dup@k.de", "passwort": "Sachb123!"
        }, headers=headers)
        r = self.client.post("/auth/register", json={
            "name": "SB2", "email": "dup@k.de", "passwort": "Sachb123!"
        }, headers=headers)
        self.assertEqual(r.status_code, 422)

    def test_register_ungueltige_email(self):
        headers = self._auth_header()
        r = self.client.post("/auth/register", json={
            "name": "X", "email": "kein-email", "passwort": "Sachb123!"
        }, headers=headers)
        self.assertEqual(r.status_code, 422)

    # ── Profil ────────────────────────────────────────────────────────────────

    def test_profil_eingeloggt(self):
        headers = self._auth_header()
        r = self.client.get("/auth/profil", headers=headers)
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertEqual(data["email"], "admin@k.de")
        self.assertNotIn("passwort_hash", data)

    def test_profil_ohne_token(self):
        r = self.client.get("/auth/profil")
        self.assertEqual(r.status_code, 401)

    def test_profil_mit_ungueltigem_token(self):
        r = self.client.get("/auth/profil", headers={
            "Authorization": "Bearer komplett.falsch.token"
        })
        self.assertEqual(r.status_code, 401)

    def test_refresh_mit_access_token_schlaegt_fehl(self):
        login_data = self._login()
        r = self.client.post("/auth/refresh", json={
            "refresh_token": login_data["access_token"]  # Falscher Token-Typ
        })
        self.assertEqual(r.status_code, 401)

    def test_refresh_ohne_token(self):
        r = self.client.post("/auth/refresh", json={})
        self.assertEqual(r.status_code, 400)

    # ── Logout ────────────────────────────────────────────────────────────────

    def test_logout_erfolgreich(self):
        headers = self._auth_header()
        r = self.client.post("/auth/logout", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIn("nachricht", r.get_json())

    # ── Passwortänderung ──────────────────────────────────────────────────────

    def test_passwort_aendern(self):
        headers = self._auth_header()
        r = self.client.post("/auth/passwort-aendern", json={
            "altes_passwort": "Admin123!",
            "neues_passwort": "NeuesAdmin456!"
        }, headers=headers)
        self.assertEqual(r.status_code, 200)
        # Mit neuem Passwort einloggen
        r2 = self.client.post("/auth/login", json={
            "email": "admin@k.de", "passwort": "NeuesAdmin456!"
        })
        self.assertEqual(r2.status_code, 200)

    def test_passwort_aendern_falsches_altes_pw(self):
        headers = self._auth_header()
        r = self.client.post("/auth/passwort-aendern", json={
            "altes_passwort": "FalschesPasswort1!",
            "neues_passwort": "NeuesAdmin456!"
        }, headers=headers)
        self.assertEqual(r.status_code, 401)

    def test_passwort_aendern_neues_zu_schwach(self):
        headers = self._auth_header()
        r = self.client.post("/auth/passwort-aendern", json={
            "altes_passwort": "Admin123!",
            "neues_passwort": "kurz"
        }, headers=headers)
        self.assertEqual(r.status_code, 422)

    # ── Benutzerverwaltung ────────────────────────────────────────────────────

    def test_benutzer_liste_als_admin(self):
        headers = self._auth_header()
        r = self.client.get("/auth/benutzer", headers=headers)
        self.assertEqual(r.status_code, 200)
        self.assertIsInstance(r.get_json(), list)

    def test_benutzer_liste_als_sachbearbeiter_verboten(self):
        # Sachbearbeiter anlegen
        headers = self._auth_header()
        self.client.post("/auth/register", json={
            "name": "SB", "email": "sb@k.de", "passwort": "Sachb123!"
        }, headers=headers)
        sb_headers = self._auth_header("sb@k.de", "Sachb123!")
        r = self.client.get("/auth/benutzer", headers=sb_headers)
        self.assertEqual(r.status_code, 403)

    def test_benutzer_deaktivieren(self):
        headers = self._auth_header()
        # SB anlegen
        self.client.post("/auth/register", json={
            "name": "SB Del", "email": "del@k.de", "passwort": "Sachb123!"
        }, headers=headers)
        sb_data = self.client.get("/auth/benutzer", headers=headers).get_json()
        sb_id = next(b["id"] for b in sb_data if b["email"] == "del@k.de")

        r = self.client.delete(f"/auth/benutzer/{sb_id}", headers=headers)
        self.assertEqual(r.status_code, 200)
        # Login nach Deaktivierung schlägt fehl (401 = Benutzer nicht gefunden)
        r2 = self.client.post("/auth/login", json={
            "email": "del@k.de", "passwort": "Sachb123!"
        })
        self.assertIn(r2.status_code, (401, 403))  # Beide sind korrekt

    def test_admin_kann_sich_nicht_selbst_deaktivieren(self):
        headers = self._auth_header()
        admin_data = self.client.get("/auth/profil", headers=headers).get_json()
        r = self.client.delete(f"/auth/benutzer/{admin_data['id']}", headers=headers)
        self.assertEqual(r.status_code, 400)

    # ── 404 / Fehlerbehandlung ────────────────────────────────────────────────

    def test_nicht_existierender_endpunkt(self):
        # GET auf unbekannte Route → 404 oder 405 (je nach OPTIONS-Catch-all)
        # Wichtig: Antwort ist JSON und enthält "fehler"-Feld
        r = self.client.get("/komplett/unbekannte/route/xyz")
        self.assertIn(r.status_code, (404, 405))
        data = r.get_json()
        self.assertIsNotNone(data)
        self.assertIn("fehler", data)

    def test_kein_bearer_prefix(self):
        """Token ohne 'Bearer ' prefix wird abgelehnt."""
        login_data = self._login()
        r = self.client.get("/auth/profil", headers={
            "Authorization": login_data["access_token"]  # Kein 'Bearer ' prefix
        })
        self.assertEqual(r.status_code, 401)

    # ── Token-Refresh ─────────────────────────────────────────────────────────

    def test_refresh_erneuert_access_token(self):
        login_data = self._login()
        import time; time.sleep(1)   # Sicherstellen dass iat sich unterscheidet
        r = self.client.post("/auth/refresh", json={
            "refresh_token": login_data["refresh_token"]
        })
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("access_token", data)
        self.assertIn("benutzer", data)


# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [TestJWTTokens, TestValidierung, TestAuthRouten]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
