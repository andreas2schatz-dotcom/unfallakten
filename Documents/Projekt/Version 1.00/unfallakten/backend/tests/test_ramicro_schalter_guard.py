"""
Guard: kein Test darf den RA-MICRO-Schalter prozessweit umlegen.

Befund 2026-09-10: test_fragebogen_queue_endpunkt.py setzte in seinem
_setup() ``os.environ["RAMICRO_AKTIV"] = "false"`` und nahm es nie zurueck.
os.environ gilt fuer den ganzen pytest-Prozess, und weil die Datei
alphabetisch vor test_klage_*, test_modul3 und test_modul5 laeuft, lief die
halbe Suite danach mit abgeschaltetem RA-MICRO.

Folge: die Vollsuite meldete 2374 gruen, waehrend dieselben Tests einzeln
aufgerufen reihenweise durchfielen -- 58 Fehler in 22 Dateien, alle mit
derselben Ursache. Ein Testergebnis, das von der Dateireihenfolge abhaengt,
ist wertlos: es sagt nichts ueber den Code aus.

Der Schalter gehoert deshalb genau an eine Stelle: conftest.py schaltet
RA-MICRO fuer die gesamte Suite ab. Wer ihn braucht, legt ihn NUR fuer die
Dauer seines Tests um -- ``monkeypatch.setenv`` oder ``mock.patch.dict``
stellen den alten Wert danach wieder her (Muster: test_modul8.py:56).

Vorbild fuer die Bauart dieses Wechters: test_dokumente_typ_guard.py.
"""
import os
import re

TESTS = os.path.dirname(os.path.abspath(__file__))
PROJEKT = os.path.dirname(os.path.dirname(TESTS))

# Direkte, bleibende Zuweisung: os.environ["RAMICRO_AKTIV"] = ... bzw.
# os.environ.setdefault("RAMICRO_AKTIV", ...). Beides ueberlebt den Test.
BLEIBENDE_ZUWEISUNG = re.compile(
    r"os\.environ\s*\[\s*[\"']RAMICRO_AKTIV[\"']\s*\]\s*="
    r"|os\.environ\.setdefault\s*\(\s*[\"']RAMICRO_AKTIV[\"']"
)

# conftest.py IST die eine erlaubte Stelle -- dort steht die Begruendung.
ERLAUBT_IN = ("conftest.py", "test_ramicro_schalter_guard.py")

KOMMENTARZEILE = re.compile(r"^\s*(#|\*)")


def _testdateien():
    for name in sorted(os.listdir(TESTS)):
        if name.endswith(".py"):
            yield name, os.path.join(TESTS, name)


def test_kein_test_legt_den_ramicro_schalter_dauerhaft_um():
    treffer = []
    for name, pfad in _testdateien():
        if name in ERLAUBT_IN:
            continue
        with open(pfad, encoding="utf-8") as fh:
            for nr, zeile in enumerate(fh, 1):
                if KOMMENTARZEILE.match(zeile):
                    continue
                if BLEIBENDE_ZUWEISUNG.search(zeile):
                    treffer.append(f"{name}:{nr}: {zeile.strip()}")

    assert treffer == [], (
        "RAMICRO_AKTIV wird prozessweit gesetzt und nicht zurueckgenommen -- "
        "das faelscht jeden spaeter laufenden Test.\n"
        + "\n".join(treffer)
        + "\n\nStattdessen fuer die Dauer des Tests umlegen: "
        "monkeypatch.setenv('RAMICRO_AKTIV', 'true') oder "
        "mock.patch.dict(os.environ, {...}). Suiteweit ist RA-MICRO in "
        "conftest.py bereits abgeschaltet."
    )


def test_conftest_schaltet_ramicro_suiteweit_ab():
    """Die zentrale Abschaltung muss vorhanden und an RAMICRO_INTEGRATION
    gekoppelt bleiben -- sonst koennen die Integrationstests nicht mehr
    echt verbinden."""
    with open(os.path.join(TESTS, "conftest.py"), encoding="utf-8") as fh:
        quelle = fh.read()
    assert 'os.environ["RAMICRO_AKTIV"] = "false"' in quelle
    assert 'os.environ.get("RAMICRO_INTEGRATION") != "1"' in quelle


def test_schalter_ist_im_test_tatsaechlich_aus():
    """Gegenprobe zur Laufzeit: was conftest verspricht, muss hier ankommen."""
    if os.environ.get("RAMICRO_INTEGRATION") == "1":
        return
    assert os.environ.get("RAMICRO_AKTIV") == "false"
