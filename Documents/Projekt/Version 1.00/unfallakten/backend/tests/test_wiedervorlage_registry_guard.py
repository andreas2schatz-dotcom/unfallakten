"""
Statischer Guard: das Feld iWiedervorlageGrund darf nur noch in der
Registry ausgelegt werden.

Bis 2026-09-01 taten das vier Konstanten und drei SQL-Literale. Der Test
prueft die Quelltexte, nicht das Laufzeitverhalten -- eine neue Liste faellt
so sofort auf, auch wenn sie noch von keinem Test beruehrt wird.
"""

import os
import re

WURZEL = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

ERLAUBT = {
    os.path.join("services", "wiedervorlage_code_registry.py"),
}

MUSTER_SQL = re.compile(r"iWiedervorlageGrund\s+(?:NOT\s+)?IN\s*\(\s*\d")


def _quelldateien():
    for ordner, _, dateien in os.walk(WURZEL):
        rel = os.path.relpath(ordner, WURZEL)
        segmente = rel.split(os.sep) if rel != "." else []
        if "tests" in segmente or "__pycache__" in segmente:
            continue
        for d in dateien:
            if d.endswith(".py"):
                yield os.path.join(ordner, d)


def test_keine_hartcodierte_codeliste_im_sql():
    treffer = []
    for pfad in _quelldateien():
        rel = os.path.relpath(pfad, WURZEL)
        if rel in ERLAUBT:
            continue
        with open(pfad, encoding="utf-8") as fh:
            for nr, zeile in enumerate(fh, 1):
                if MUSTER_SQL.search(zeile):
                    treffer.append(f"{rel}:{nr}")
    assert treffer == [], (
        "Codeliste direkt im SQL statt aus sql_codeliste(): "
        + ", ".join(treffer))


def test_offener_pruefstand_ist_sichtbar():
    """Kein Fehlschlag, nur ein Zaehler: solange Bezeichnungen unverifiziert
    sind, soll das im Testlauf sichtbar bleiben."""
    from backend.services.wiedervorlage_code_registry import lade_wv_codes
    r = lade_wv_codes()
    offen = [c for c, e in r.codes.items() if not e.get("verifiziert")]
    if offen:
        print(f"\nHINWEIS: {len(offen)} von {len(r.codes)} Wiedervorlagecodes "
              f"sind noch nicht gegen RA-MICRO verifiziert: {sorted(offen)}")
