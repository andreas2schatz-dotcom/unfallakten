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
    """Ein Test hat versucht, eine ECHTE RA-MICRO-Verbindung aufzubauen,
    statt den RA-MICRO-Zugriff zu mocken.

    Erbt bewusst von ``BaseException`` statt ``Exception``: RA-MICRO-
    Zugriffscode faengt Verbindungsfehler in der Produktion absichtlich
    grosszuegig mit ``except Exception`` ab (Resilienz bei echtem
    RA-MICRO-Ausfall) -- genau das wuerde einen vergessenen Mock in einem
    Test lautlos zu einem leeren Ergebnis machen, statt den Test hart
    scheitern zu lassen. ``BaseException`` rutscht durch diese
    Except-Bloecke hindurch. Verifiziert (2026-08-28): kein
    ``except BaseException``/nacktes ``except:`` im Produktionscode
    ausserhalb der Tests, ``finally``-Bloecke (Verbindungsaufraeumung)
    laufen unbeeinflusst, weil der Sperrhahn schon vor dem eigentlichen
    Verbindungsaufbau wirft.
    """


def _ramicro_sperrhahn(*_args, **_kwargs):
    raise EchteRamicroVerbindungVersucht(
        "pymssql.connect() haette eine ECHTE Verbindung zur "
        "Kanzlei-RA-MICRO-Datenbank aufgebaut. Der Container hat "
        "RAMICRO_AKTIV=true UND echte Netzwerksicht auf den Kanzleiserver "
        "(2026-08-28 verifiziert) -- ein fehlender Mock in diesem Test "
        "wuerde also lesend gegen die Produktivdatenbank laufen. Fehlt "
        "ein mock.patch fuer "
        "get_ramicro_connection / suche_akte_in_ramicro / "
        "suche_kandidaten_in_ramicro / suche_abgelegte_in_ramicro / "
        "_suche_in_ramicro -- oder braucht dieser Test bewusst eine echte "
        "Verbindung? Dann @pytest.mark.erlaubt_echte_ramicro_verbindung "
        "setzen und begruenden."
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "erlaubt_echte_ramicro_verbindung: Opt-out aus der globalen "
        "RA-MICRO-Verbindungssperre (siehe _ramicro_verbindungssperre in "
        "conftest.py) -- nur mit Begruendung im Test-Docstring verwenden.",
    )


@pytest.fixture(autouse=True)
def _ramicro_verbindungssperre(request):
    """Harte Sperre gegen unbemerkte echte RA-MICRO-Verbindungen -- gilt
    standardmaessig fuer die GESAMTE Suite, nicht nur fuer einzelne
    Dateien.

    Befund 2026-08-28: RAMICRO_AKTIV=true im Dev-Container plus echte
    Netzwerksicht auf den Kanzleiserver fuehrten dazu, dass mehrere Tests
    (u.a. in test_fragebogen_matching.py) ohne Mock lesend gegen die
    Produktivdatenbank der Kanzlei liefen, unbemerkt, weil RA-MICRO-
    Zugriffscode Verbindungsfehler bewusst grosszuegig abfaengt. Eine
    Datei-Liste, die jemand pflegen muss, ist dagegen kein verlaesslicher
    Schutz -- mehrere Bestandsdateien und mehrere RA-MICRO-Module
    (adress_service, ablage_service, wiedervorlage_service,
    akten_erkennung, output_adapter, email_matching) holen sich
    ``get_ramicro_connection`` jeweils selbst, eine Sperre auf einer
    einzelnen Modulbindung deckt das nicht ab.

    Der Haken sitzt deshalb an der niedrigsten gemeinsamen Stelle:
    ``pymssql.connect`` -- der einzige Ort, an dem ``connector.py``
    tatsaechlich eine Socket-Verbindung oeffnet (sowohl
    ``get_ramicro_connection()`` als auch ``verbindung_pruefen()``
    importieren ``pymssql`` erst innerhalb der Funktion und rufen
    ``pymssql.connect`` auf; das Patchen des Attributs auf dem bereits
    importierten ``pymssql``-Modul wirkt deshalb fuer jeden Aufrufer,
    unabhaengig davon, ueber welches Zwischenmodul er kommt).

    Opt-out: ``@pytest.mark.erlaubt_echte_ramicro_verbindung`` auf einem
    Test, der bewusst real gegen RA-MICRO laufen soll. Tests, die selbst
    gezielt ``get_ramicro_connection``, ``pymssql.connect`` oder eine der
    oeffentlichen Suchfunktionen mocken, ueberschreiben diese Sperre fuer
    ihre Dauer ohnehin -- ``mock.patch`` stapelt korrekt.
    """
    if request.node.get_closest_marker("erlaubt_echte_ramicro_verbindung"):
        yield
        return
    with mock.patch("pymssql.connect", side_effect=_ramicro_sperrhahn):
        yield
