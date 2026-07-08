"""
Gemeinsame pytest-Konfiguration fuer backend/tests.

Setzt Test-Umgebungsvariablen VOR dem Sammeln der Testmodule. Ohne dieses
Modul crasht jeder Test, der ``backend.app.erstelle_app()`` importiert,
mit ``RuntimeError: FLASK_SECRET_KEY ist nicht gesetzt`` (app.py:117).

Der Wert ist bewusst ein Fixzeichen und **darf nur im Testkontext** stehen
-- ein produktiver Lauf ohne echte Secret Key wuerde durch die Assertion
in app.py verhindert. Nur pytest laedt conftest.py automatisch.
"""
import os

os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-production")
