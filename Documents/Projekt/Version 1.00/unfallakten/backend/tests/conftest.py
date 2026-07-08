"""
Gemeinsame pytest-Konfiguration fuer backend/tests.

Setzt Test-Umgebungsvariablen VOR dem Sammeln der Testmodule.

FLASK_SECRET_KEY:
    Ohne diesen Wert crasht jeder Test, der ``backend.app.erstelle_app()``
    importiert, mit ``RuntimeError: FLASK_SECRET_KEY ist nicht gesetzt``
    (app.py:117).

JWT_SECRET_KEY:
    Wird von backend/auth/jwt_handler.py verlangt (Mindestlaenge 32 Zeichen).

ADMIN_EMAIL / ADMIN_PASSWORT / ADMIN_NAME:
    Ueberschreiben die Kanzlei-Default-Bootstrap-Credentials aus
    app.py:_ensure_admin_exists(). Ohne diesen Fix legt jeder erstelle_app()-
    Aufruf einen "koch@anwalt-offenbach.de"-Admin an; die alten Tests
    versuchten daraufhin ``/auth/register/erster`` mit Test-Credentials,
    bekamen 409 und fielen im anschliessenden Login auf ``KeyError:
    'access_token'`` (~150 Failures in test_modul3/4/7).

Alle Werte sind bewusst Fix-Testkonstanten -- der produktive Betrieb
verwendet echte .env-Konfiguration. Nur pytest laedt conftest.py
automatisch, ausserhalb von pytest greifen diese Defaults NICHT.
"""
import os

os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-minimum-32-chars!!")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.de")
os.environ.setdefault("ADMIN_PASSWORT", "Admin123!")
os.environ.setdefault("ADMIN_NAME", "Admin")
