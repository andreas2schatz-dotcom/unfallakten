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

import pytest
from unittest import mock


class EchteRamicroVerbindungVersucht(BaseException):
    """Ein Fragebogen-Matching-Test hat versucht, eine ECHTE RA-MICRO-
    Verbindung aufzubauen, statt ``suche_akte_in_ramicro`` /
    ``suche_kandidaten_in_ramicro`` / ``suche_abgelegte_in_ramicro`` (oder
    ``_suche_in_ramicro``) zu mocken.

    Erbt bewusst von ``BaseException`` statt ``Exception``: die
    Matching-Logik faengt RA-MICRO-Fehler in der Produktion absichtlich
    grosszuegig mit ``except Exception`` ab (Resilienz bei echtem
    RA-MICRO-Ausfall) -- genau das wuerde einen vergessenen Mock in einem
    Test lautlos zu einer leeren Kandidatenliste machen, statt den Test
    hart scheitern zu lassen. ``BaseException`` rutscht durch diese
    Except-Bloecke hindurch.
    """


def _ramicro_sperrhahn(*_args, **_kwargs):
    raise EchteRamicroVerbindungVersucht(
        "get_ramicro_connection() haette eine ECHTE Verbindung zur "
        "Kanzlei-RA-MICRO-Datenbank aufgebaut. Der Container hat "
        "RAMICRO_AKTIV=true UND echte Netzwerksicht auf den Kanzleiserver "
        "(2026-08-28 verifiziert) -- ein fehlender Mock in diesem Test "
        "wuerde also lesend gegen die Produktivdatenbank laufen. Fehlt "
        "hier ein mock.patch fuer suche_akte_in_ramicro / "
        "suche_kandidaten_in_ramicro / suche_abgelegte_in_ramicro / "
        "_suche_in_ramicro?"
    )


# Dateien, in denen Fragebogen-/Akten-Matching-Code (finde_kandidaten und
# alles, was darunter RA-MICRO beruehrt) ohne echte Verbindung laufen muss.
# Tests, die selbst gezielt get_ramicro_connection oder eine der oeffentlichen
# Suchfunktionen mocken, ueberschreiben diese Sperre fuer ihre Dauer --
# mock.patch stapelt korrekt.
_RAMICRO_TESTSPERRE_DATEIEN = {
    "test_fragebogen_abgelegt.py",
    "test_fragebogen_matching.py",
    "test_fragebogen_pipeline_klasse.py",
    "test_fragebogen_queue_endpunkt.py",
    "test_fragebogen_ramicro.py",
    "test_fragebogen_zuordnung.py",
    "test_intake_akten_matching.py",
    "test_s17_akten_matching_e2e.py",
}


@pytest.fixture(autouse=True)
def _keine_echte_ramicro_verbindung(request):
    """Harte Sperre gegen unbemerkte echte RA-MICRO-Verbindungen in den
    Fragebogen-/Akten-Matching-Tests (siehe
    handover/feedback_unfallakten_geld_ssot.md-Nachbarn -- Befund
    2026-08-28: RAMICRO_AKTIV=true im Dev-Container plus echte
    Netzwerksicht auf 192.168.10.100 fuehrten dazu, dass ein vergessener
    Mock in ``test_fragebogen_matching.py`` lesend gegen die
    Produktivdatenbank der Kanzlei lief, unbemerkt, weil die
    Matching-Logik Verbindungsfehler bewusst grosszuegig abfaengt).

    Wirkt nur in den Dateien aus ``_RAMICRO_TESTSPERRE_DATEIEN``. Ein
    kuenftiger neuer RA-MICRO-Suchweg, der dort ungemockt durchlaeuft,
    bricht den Test sofort mit ``EchteRamicroVerbindungVersucht`` ab,
    statt still leere Ergebnisse zu liefern.
    """
    dateiname = os.path.basename(str(request.fspath))
    if dateiname not in _RAMICRO_TESTSPERRE_DATEIEN:
        yield
        return
    from backend.ramicro import email_matching as _em
    with mock.patch.object(_em, "get_ramicro_connection",
                            side_effect=_ramicro_sperrhahn):
        yield
