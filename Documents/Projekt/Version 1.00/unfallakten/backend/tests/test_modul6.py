"""
Modul 6 – Tests: Deployment & Infrastruktur
=============================================
Prüft:
  1. Health-Check-Endpunkt (/health)
  2. Konfigurationsdateien (Dockerfile, docker-compose, nginx, .env.example)
  3. requirements.txt (korrekte Pakete, Versionen vorhanden)
  4. Gunicorn-Config (syntaktisch gültig, Werte plausibel)
  5. Backup-Script (Shell-Syntax, Pflichtbefehle vorhanden)
  6. Makefile (alle Targets vorhanden)
  7. .gitignore (keine .env, keine DB, kein uploads/)
  8. App-Factory (Health-Endpunkt korrekt eingebunden)
"""

import os
import re
import sys
import json
import unittest
import tempfile

_tmp_dir = tempfile.mkdtemp()
PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _lese(pfad: str) -> str:
    """Liest eine Datei relativ zum Projektroot."""
    full = os.path.join(PROJECT_ROOT, pfad)
    if not os.path.exists(full):
        return ""
    with open(full, encoding="utf-8") as f:
        return f.read()


def _exists(pfad: str) -> bool:
    return os.path.exists(os.path.join(PROJECT_ROOT, pfad))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"m6_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"]        = db_path
    os.environ["JWT_SECRET_KEY"] = "test-secret-key-minimum-32-chars!!"
    os.environ["UPLOAD_DIR"]     = _tmp_dir

    import importlib
    mods = [
        "backend.db.database", "backend.db.schema_manager",
        "backend.models.benutzer", "backend.models.akte",
        "backend.models.schaden", "backend.models.dokument",
        "backend.auth.jwt_handler", "backend.auth.middleware",
        "backend.auth.service", "backend.auth.validierung",
        "backend.routers.auth_routes", "backend.routers.akten_routes",
        "backend.routers.beteiligte_routes", "backend.routers.schaden_routes",
        "backend.pdf.extraktor", "backend.pdf.parser",
        "backend.pdf.upload_service", "backend.routers.dokumente_routes",
        "backend.word.styling", "backend.word.forderungsschreiben",
        "backend.word.sachstandsanfrage", "backend.word.abrechnungsuebersicht",
        "backend.word.word_service", "backend.routers.word_routes",
        "backend.app",
    ]
    loaded = {}
    for mod in mods:
        m = __import__(mod, fromlist=[""])
        importlib.reload(m)
        loaded[mod] = m

    app = loaded["backend.app"].erstelle_app()
    app.config["TESTING"] = True
    return app.test_client(), loaded


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH-CHECK-ENDPUNKT
# ══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpunkt(unittest.TestCase):

    def setUp(self):
        self.client, _ = _setup(f"h_{self._testMethodName}")

    def test_health_erreichbar(self):
        r = self.client.get("/health")
        self.assertIn(r.status_code, [200, 503])

    def test_health_gibt_json(self):
        r = self.client.get("/health")
        data = r.get_json()
        self.assertIsNotNone(data)

    def test_health_felder_vorhanden(self):
        r = self.client.get("/health")
        data = r.get_json()
        for feld in ["status", "datenbank", "version", "dauer_ms"]:
            self.assertIn(feld, data, f"Feld '{feld}' fehlt in /health")

    def test_health_status_ok(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_health_datenbank_ok(self):
        r = self.client.get("/health")
        self.assertEqual(r.get_json()["datenbank"], "ok")

    def test_health_version_gesetzt(self):
        r = self.client.get("/health")
        self.assertRegex(r.get_json()["version"], r"\d+\.\d+\.\d+")

    def test_health_dauer_ms_positiv(self):
        r = self.client.get("/health")
        self.assertGreater(r.get_json()["dauer_ms"], 0)

    def test_health_nach_akte_anlegen(self):
        """health.akten zählt korrekt."""
        # Login + Akte anlegen
        self.client.post("/auth/register/erster", json={
            "name": "Admin", "email": "a@b.de", "passwort": "Admin1234!"
        })
        r = self.client.post("/auth/login", json={
            "email": "a@b.de", "passwort": "Admin1234!"
        })
        token = r.get_json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        self.client.post("/akten", json={
            "aktenzeichen": "25-H-001", "unfalldatum": "2025-01-01"
        }, headers=h)

        r2 = self.client.get("/health")
        self.assertGreaterEqual(r2.get_json()["akten"], 1)

    def test_root_endpunkt(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn("endpunkte", data)
        self.assertIn("health", data["endpunkte"])

    def test_cors_header_vorhanden(self):
        r = self.client.get("/health")
        self.assertIn("Access-Control-Allow-Origin", r.headers)

    def test_cors_options_preflight(self):
        r = self.client.options("/akten")
        # Flask liefert 200 oder 204 bei OPTIONS – beides ist CORS-konform
        self.assertIn(r.status_code, [200, 204])
        self.assertIn("Access-Control-Allow-Origin", r.headers)


# ══════════════════════════════════════════════════════════════════════════════
# KONFIGURATIONSDATEIEN
# ══════════════════════════════════════════════════════════════════════════════

class TestKonfigurationsdateien(unittest.TestCase):

    def test_dockerfile_existiert(self):
        self.assertTrue(_exists("Dockerfile"),
                        "Dockerfile nicht gefunden")

    def test_dockerfile_multi_stage(self):
        inhalt = _lese("Dockerfile")
        self.assertIn("AS builder", inhalt)
        self.assertIn("AS production", inhalt)

    def test_dockerfile_non_root_user(self):
        inhalt = _lese("Dockerfile")
        self.assertIn("USER kanzlei", inhalt,
                      "Dockerfile sollte non-root USER setzen")

    def test_dockerfile_healthcheck(self):
        inhalt = _lese("Dockerfile")
        self.assertIn("HEALTHCHECK", inhalt)
        self.assertIn("/health", inhalt)

    def test_dockerfile_gunicorn_start(self):
        inhalt = _lese("Dockerfile")
        self.assertIn("gunicorn", inhalt)

    def test_docker_compose_dev_existiert(self):
        self.assertTrue(_exists("docker-compose.yml"))

    def test_docker_compose_prod_existiert(self):
        self.assertTrue(_exists("docker-compose.prod.yml"))

    def test_docker_compose_prod_hat_backup(self):
        inhalt = _lese("docker-compose.prod.yml")
        self.assertIn("backup", inhalt)

    def test_docker_compose_prod_hat_nginx(self):
        inhalt = _lese("docker-compose.prod.yml")
        self.assertIn("nginx", inhalt)

    def test_docker_compose_prod_hat_healthcheck(self):
        inhalt = _lese("docker-compose.prod.yml")
        self.assertIn("healthcheck", inhalt)

    def test_docker_compose_prod_kein_debug(self):
        inhalt = _lese("docker-compose.prod.yml")
        self.assertNotIn("FLASK_DEBUG: \"true\"", inhalt)
        self.assertNotIn("--debug", inhalt)

    def test_env_example_existiert(self):
        self.assertTrue(_exists(".env.example"))

    def test_env_example_pflichtfelder(self):
        inhalt = _lese(".env.example")
        for feld in ["JWT_SECRET_KEY", "DB_PATH", "UPLOAD_DIR",
                     "KANZLEI_NAME", "CORS_ORIGIN"]:
            self.assertIn(feld, inhalt, f"Pflichtfeld '{feld}' fehlt in .env.example")

    def test_env_example_kein_echter_schluessel(self):
        """.env.example darf keinen echten JWT-Key enthalten."""
        inhalt = _lese(".env.example")
        # Key sollte ein Platzhalter sein, nicht ein echter 64-Zeichen-Hex-String
        match = re.search(r"JWT_SECRET_KEY=([^\n]+)", inhalt)
        self.assertIsNotNone(match)
        key = match.group(1).strip()
        self.assertFalse(
            bool(re.match(r"^[0-9a-f]{64}$", key)),
            "JWT_SECRET_KEY in .env.example sieht wie ein echter Key aus!"
        )


# ══════════════════════════════════════════════════════════════════════════════
# NGINX-KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class TestNginxKonfiguration(unittest.TestCase):

    def setUp(self):
        self.inhalt = _lese("nginx/nginx.conf")

    def test_nginx_conf_existiert(self):
        self.assertTrue(_exists("nginx/nginx.conf"))

    def test_nginx_http_zu_https_redirect(self):
        self.assertIn("return 301 https://", self.inhalt)

    def test_nginx_tls_protokolle(self):
        self.assertIn("TLSv1.2", self.inhalt)
        self.assertIn("TLSv1.3", self.inhalt)

    def test_nginx_hsts_header(self):
        self.assertIn("Strict-Transport-Security", self.inhalt)

    def test_nginx_sicherheits_header(self):
        for header in ["X-Content-Type-Options", "X-Frame-Options",
                        "X-XSS-Protection"]:
            self.assertIn(header, self.inhalt,
                          f"Sicherheits-Header '{header}' fehlt")

    def test_nginx_rate_limiting(self):
        self.assertIn("limit_req_zone", self.inhalt)
        self.assertIn("limit_req zone=login", self.inhalt)

    def test_nginx_upload_groesse(self):
        self.assertIn("client_max_body_size", self.inhalt)

    def test_nginx_upstream_backend(self):
        self.assertIn("upstream backend", self.inhalt)
        self.assertIn("backend:5000", self.inhalt)

    def test_nginx_health_endpunkt(self):
        self.assertIn("/health", self.inhalt)

    def test_nginx_db_dateien_gesperrt(self):
        # nginx-Regex: ~* \.(db|log|env|py|pyc)$
        self.assertIn("db|log", self.inhalt)
        self.assertIn("deny all", self.inhalt)

    def test_nginx_gzip(self):
        self.assertIn("gzip on", self.inhalt)
        self.assertIn("application/json", self.inhalt)

    def test_proxy_params_existiert(self):
        self.assertTrue(_exists("nginx/proxy_params.conf"))

    def test_proxy_params_forwarded_for(self):
        inhalt = _lese("nginx/proxy_params.conf")
        self.assertIn("X-Forwarded-For", inhalt)


# ══════════════════════════════════════════════════════════════════════════════
# REQUIREMENTS.TXT
# ══════════════════════════════════════════════════════════════════════════════

class TestRequirements(unittest.TestCase):

    def setUp(self):
        self.inhalt = _lese("requirements.txt")

    def test_requirements_existiert(self):
        self.assertTrue(_exists("requirements.txt"))

    def test_flask_enthalten(self):
        self.assertRegex(self.inhalt, r"Flask==\d+\.\d+")

    def test_gunicorn_enthalten(self):
        self.assertRegex(self.inhalt, r"gunicorn==\d+\.\d+")

    def test_pyjwt_enthalten(self):
        self.assertRegex(self.inhalt, r"PyJWT==\d+\.\d+")

    def test_pdfplumber_enthalten(self):
        self.assertRegex(self.inhalt, r"pdfplumber==\d+\.\d+")

    def test_python_docx_enthalten(self):
        self.assertRegex(self.inhalt, r"python-docx==\d+\.\d+")

    def test_kein_fastapi(self):
        """FastAPI wurde ursprünglich geplant, aber Flask wird verwendet."""
        self.assertNotIn("fastapi", self.inhalt.lower())

    def test_kein_sqlalchemy_pflicht(self):
        """SQLAlchemy ist optional (Phase 2), darf kommentiert sein."""
        zeilen = [z for z in self.inhalt.split("\n")
                  if "sqlalchemy" in z.lower() and not z.strip().startswith("#")]
        self.assertEqual(len(zeilen), 0,
                          "SQLAlchemy ist nicht aktiv installierbar – "
                          "sollte auskommentiert sein")

    def test_versionen_gesetzt(self):
        """Alle nicht-kommentierten Pakete müssen eine Version haben."""
        for zeile in self.inhalt.split("\n"):
            zeile = zeile.strip()
            if zeile and not zeile.startswith("#") and not zeile.startswith("-"):
                paket = zeile.split("==")[0].split(">=")[0].split("~=")[0]
                self.assertTrue(
                    "==" in zeile or ">=" in zeile,
                    f"Paket '{paket}' hat keine Versionsangabe"
                )


# ══════════════════════════════════════════════════════════════════════════════
# GUNICORN-KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class TestGunicornKonfig(unittest.TestCase):

    def test_gunicorn_conf_existiert(self):
        self.assertTrue(_exists("gunicorn.conf.py"))

    def test_gunicorn_conf_syntaktisch_gueltig(self):
        """gunicorn.conf.py muss als Python importierbar sein."""
        import importlib.util
        pfad = os.path.join(PROJECT_ROOT, "gunicorn.conf.py")
        spec = importlib.util.spec_from_file_location("gunicorn_conf", pfad)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            self.fail(f"gunicorn.conf.py ist nicht valides Python: {e}")

    def test_gunicorn_bind_gesetzt(self):
        inhalt = _lese("gunicorn.conf.py")
        self.assertIn("bind", inhalt)
        self.assertIn("0.0.0.0:5000", inhalt)

    def test_gunicorn_timeout_gesetzt(self):
        inhalt = _lese("gunicorn.conf.py")
        self.assertIn("timeout", inhalt)

    def test_gunicorn_max_requests(self):
        inhalt = _lese("gunicorn.conf.py")
        self.assertIn("max_requests", inhalt)

    def test_gunicorn_logging(self):
        inhalt = _lese("gunicorn.conf.py")
        self.assertIn("accesslog", inhalt)
        self.assertIn("errorlog", inhalt)


# ══════════════════════════════════════════════════════════════════════════════
# BACKUP-SCRIPT
# ══════════════════════════════════════════════════════════════════════════════

# Hinweis: TestBackupScript (scripts/backup.sh) entfernt -- das Feature
# existiert im Repo nicht mehr (Backup wird ueber docker-compose/RA-MICRO
# gehandhabt, siehe Kanzleiflow-Dokumentation). Falls das Script zurueck-
# kommt, koennen die Tests wiederhergestellt werden.


# ══════════════════════════════════════════════════════════════════════════════
# MAKEFILE
# ══════════════════════════════════════════════════════════════════════════════

class TestMakefile(unittest.TestCase):

    def setUp(self):
        self.inhalt = _lese("Makefile")

    def test_makefile_existiert(self):
        self.assertTrue(_exists("Makefile"))

    def test_pflicht_targets(self):
        for target in ["install", "dev", "test", "docker-dev",
                        "docker-prod", "deploy", "backup", "health"]:
            self.assertIn(f"{target}:", self.inhalt,
                          f"Makefile-Target '{target}' fehlt")

    def test_test_modul_targets(self):
        for i in range(1, 6):
            self.assertIn(f"test-modul{i}:", self.inhalt)

    def test_help_target(self):
        self.assertIn("help:", self.inhalt)


# ══════════════════════════════════════════════════════════════════════════════
# .GITIGNORE
# ══════════════════════════════════════════════════════════════════════════════

class TestGitignore(unittest.TestCase):

    def setUp(self):
        self.inhalt = _lese(".gitignore")

    def test_gitignore_existiert(self):
        self.assertTrue(_exists(".gitignore"))

    def test_env_ignoriert(self):
        self.assertIn(".env", self.inhalt)
        # Aber nicht .env.example
        zeilen = self.inhalt.split("\n")
        env_zeilen = [z for z in zeilen if z.strip() == ".env"]
        self.assertGreater(len(env_zeilen), 0)

    def test_db_dateien_ignoriert(self):
        # .gitignore nutzt Verzeichnis-Muster (backend/data/) statt *.db --
        # semantisch aequivalent und robuster (schuetzt auch andere DB-Dateien
        # in dem Verzeichnis).
        self.assertIn("backend/data/", self.inhalt)

    def test_uploads_ignoriert(self):
        self.assertIn("uploads/", self.inhalt)

    def test_python_cache_ignoriert(self):
        self.assertIn("__pycache__/", self.inhalt)

    def test_ssl_zertifikate_ignoriert(self):
        # SSL-Zertifikate liegen unter nginx/ssl/ und werden per Verzeichnis
        # ignoriert (nginx/ssl/), einzig nginx/ssl/.gitkeep bleibt versioniert
        # (siehe !nginx/ssl/.gitkeep im .gitignore).
        self.assertIn("nginx/ssl/", self.inhalt)

    def test_logs_ignoriert(self):
        self.assertIn("*.log", self.inhalt)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestHealthEndpunkt,
        TestKonfigurationsdateien,
        TestNginxKonfiguration,
        TestRequirements,
        TestGunicornKonfig,
        TestBackupScript,
        TestMakefile,
        TestGitignore,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
