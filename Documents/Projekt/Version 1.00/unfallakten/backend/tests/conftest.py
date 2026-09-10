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

RAMICRO_INTEGRATION / @pytest.mark.ramicro_integration:
    Tests, die absichtlich ECHT gegen die RA-MICRO-Datenbank der
    Kanzlei laufen sollen (statt gegen Mocks), tragen die Markierung
    ``@pytest.mark.ramicro_integration``. Ohne die Umgebungsvariable
    ``RAMICRO_INTEGRATION=1`` werden sie uebersprungen (mit Klartext-
    Grund), damit die normale Suite nicht vom laufenden Kanzleiserver
    abhaengt -- ``RAMICRO_INTEGRATION=1 pytest ...`` fuehrt sie echt
    aus. Der Grund fuer die Trennung: die Suite soll beantworten "habe
    ich etwas kaputtgemacht" (nur der Code darf sich aendern), die
    Integrationstests beantworten "stimmt unsere Annahme ueber
    RA-MICRO noch" -- beide sind wertvoll, duerfen aber nicht dasselbe
    rote Kreuz erzeugen.
"""
import os

os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-minimum-32-chars!!")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.de")
os.environ.setdefault("ADMIN_PASSWORT", "Admin123!")
os.environ.setdefault("ADMIN_NAME", "Admin")

# RA-MICRO ist in der normalen Testsuite grundsaetzlich AUS -- zentral, nicht
# je Datei. Kein setdefault: der Dev-Container setzt RAMICRO_AKTIV=true, das
# muss hier ueberschrieben werden.
#
# Befund 2026-09-10: Bis dahin schaltete test_fragebogen_queue_endpunkt.py
# RA-MICRO in seinem _setup() prozessweit ab und nahm es nie zurueck. Weil die
# Datei alphabetisch vor test_klage_*, test_modul3 und test_modul5 laeuft, lief
# die halbe Suite danach mit abgeschaltetem RA-MICRO -- die Vollsuite war
# gruen, jede Teilmenge rot (58 Fehler in 22 Dateien, alle mit derselben
# Ursache). Ein zufaelliger Nebeneffekt der Dateireihenfolge darf nicht
# darueber entscheiden, ob ein Test besteht.
#
# Das entschaerft den Sperrhahn unten NICHT: get_ramicro_connection bricht bei
# ausgeschaltetem RA-MICRO ab, BEVOR pymssql importiert oder ein Socket
# geoeffnet wird -- es kann also weiterhin kein Test unbemerkt gegen die
# Produktivdatenbank lesen. Der Sperrhahn bewacht ab jetzt genau den Fall, fuer
# den er gebaut wurde: ein Test, der RA-MICRO absichtlich einschaltet und dabei
# einen Mock vergisst.
#
# Wer RA-MICRO braucht, schaltet es fuer seine Dauer selbst ein
# (monkeypatch.setenv("RAMICRO_AKTIV", "true") -- Muster: test_modul8.py) und
# mockt dann den Zugriff.
if os.environ.get("RAMICRO_INTEGRATION") != "1":
    os.environ["RAMICRO_AKTIV"] = "false"

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
        "_suche_in_ramicro -- oder ist das absichtlich ein "
        "Integrationstest? Dann @pytest.mark.ramicro_integration setzen "
        "(siehe Modul-Docstring)."
    )


_RAMICRO_INTEGRATION_GRUND = (
    "Integrationstest gegen die echte RA-MICRO-Datenbank der Kanzlei -- "
    "standardmaessig uebersprungen, damit die normale Testsuite nicht vom "
    "laufenden Kanzleiserver abhaengt. Mit der Umgebungsvariable "
    "RAMICRO_INTEGRATION=1 vor dem pytest-Aufruf ausfuehren, um ihn "
    "echt gegen RA-MICRO laufen zu lassen."
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "ramicro_integration: Integrationstest, der ECHT gegen die "
        "RA-MICRO-Datenbank der Kanzlei laeuft (keine Mocks). "
        "Standardmaessig uebersprungen; mit RAMICRO_INTEGRATION=1 als "
        "Umgebungsvariable ausgefuehrt. Siehe Modul-Docstring in "
        "conftest.py.",
    )


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RAMICRO_INTEGRATION") == "1":
        return
    ueberspringen = pytest.mark.skip(reason=_RAMICRO_INTEGRATION_GRUND)
    for item in items:
        if item.get_closest_marker("ramicro_integration"):
            item.add_marker(ueberspringen)


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
    akten_erkennung, eakte_service, email_matching) holen sich
    ``get_ramicro_connection`` jeweils selbst oder rufen (eakte_service)
    sogar ``pymssql.connect`` direkt auf, eine Sperre auf einer einzelnen
    Modulbindung deckt das nicht ab.

    Der Haken sitzt deshalb an der niedrigsten gemeinsamen Stelle:
    ``pymssql.connect`` -- der einzige Ort, an dem tatsaechlich eine
    Socket-Verbindung geoeffnet wird (das Patchen des Attributs auf dem
    bereits importierten ``pymssql``-Modul wirkt fuer jeden Aufrufer,
    unabhaengig davon, ueber welches Zwischenmodul er kommt).

    Ausnahme: bei mit ``@pytest.mark.ramicro_integration`` markierten
    Tests und gesetztem ``RAMICRO_INTEGRATION=1`` bleibt die Sperre aus --
    genau diese Tests SOLLEN dann echt verbinden (siehe Modul-Docstring).
    Tests, die selbst gezielt ``get_ramicro_connection``,
    ``pymssql.connect`` oder eine der oeffentlichen Suchfunktionen mocken,
    ueberschreiben diese Sperre fuer ihre Dauer ohnehin -- ``mock.patch``
    stapelt korrekt.
    """
    if (request.node.get_closest_marker("ramicro_integration")
            and os.environ.get("RAMICRO_INTEGRATION") == "1"):
        yield
        return
    with mock.patch("pymssql.connect", side_effect=_ramicro_sperrhahn):
        yield
