"""
Guard: dokumente.typ ist entfallen (Migration 74) und darf nicht
zurueckkehren. Fachlich massgeblich ist allein dokumentenklasse.

Vorbild: test_gen_dokumentenklassen_guard.py.
"""
import os
import re

PROJEKT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Gleichnamige, aber voellig andere Felder -- diese Treffer sind erlaubt.
ERLAUBTE_NACHBARN = (
    "dateityp", "ereignistyp", "payload_typ", "rechnungstyp", "kuerzungstyp",
    "fahrzeug_typ", "frist_typ", "schluss_typ", "kfz_typ", "email_typ",
    "aktion_typ", "typ_code", "typ_quelle", "aktivlegitimation_typ",
)

# Prosa-Muster: schlaegt auch in Fliesstext an, der die Spalte nur benennt.
PROSA_MUSTER = re.compile(r"\bdokumente\.typ\b")

# Zugriffsmuster: nur echter Code sieht so aus.
ZUGRIFF_MUSTER = (
    re.compile(r"\bd\.typ\b"),
    re.compile(r"registriere_dokument\([^)]*\btyp\s*="),
    re.compile(r"GUELTIGE_TYPEN"),
)

# Die Migration, die die Spalte entfernt, muss sie benennen -- in Docstring,
# Logmeldung und schema_version-Beschreibung. Nur dort greift das Prosa-Muster
# nicht; die drei Zugriffsmuster bleiben auch in dieser Datei scharf.
PROSA_ERLAUBT_IN = ("schema_manager.py",)

KOMMENTARZEILE = re.compile(r"^\s*(#|//|--|\*)")

# Bare `typ` innerhalb einer SQL-Anweisung ueber dokumente -- ohne
# Tabellen-Praefix, daher von den zeilenweisen Mustern nicht erfasst.
# Genau so war _zaehle_schriftsaetze() in gebuehren_service.py durchgerutscht.
SQL_BARE_TYP = re.compile(
    r"(?is)(?:FROM|INTO|UPDATE|JOIN)\s+dokumente\b"
    r".{0,400}?"
    r"(?<![\w.])typ\s*(?:=|\bIN\b|,)"
)

DURCHSUCHEN = ("backend", "frontend/src", "tools")
UEBERSPRINGEN = ("node_modules", "dist", "__pycache__", ".git",
                 "test_dokumente_typ_guard.py", "test_migration_73_74.py")


def _quelldateien():
    for wurzel in DURCHSUCHEN:
        for pfad, ordner, dateien in os.walk(os.path.join(PROJEKT, wurzel)):
            ordner[:] = [o for o in ordner if o not in UEBERSPRINGEN]
            for d in dateien:
                if d in UEBERSPRINGEN:
                    continue
                if d.endswith((".py", ".js", ".jsx", ".sql")):
                    yield os.path.join(pfad, d)


def test_keine_bare_typ_spalte_in_dokumente_abfragen():
    treffer = []
    for datei in _quelldateien():
        if os.path.basename(datei) in PROSA_ERLAUBT_IN:
            continue
        with open(datei, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        for m in SQL_BARE_TYP.finditer(text):
            nr = text.count(chr(10), 0, m.start()) + 1
            treffer.append("%s:%d: %s" % (
                os.path.relpath(datei, PROJEKT), nr,
                " ".join(m.group(0).split())[:140]))
    assert not treffer, (
        "SQL-Abfrage auf dokumente nutzt noch die entfallene Spalte typ:"
        + chr(10) + chr(10).join(treffer))


def test_keine_dokumente_typ_zugriffe_mehr():
    treffer = []
    for datei in _quelldateien():
        muster = list(ZUGRIFF_MUSTER)
        if os.path.basename(datei) not in PROSA_ERLAUBT_IN:
            muster.append(PROSA_MUSTER)
        with open(datei, "r", encoding="utf-8", errors="replace") as f:
            for nr, zeile in enumerate(f, 1):
                if any(n in zeile for n in ERLAUBTE_NACHBARN):
                    continue
                if KOMMENTARZEILE.match(zeile):
                    continue
                for m in muster:
                    if m.search(zeile):
                        treffer.append(
                            "%s:%d: %s" % (os.path.relpath(datei, PROJEKT),
                                           nr, zeile.strip()))
    assert not treffer, (
        "dokumente.typ ist mit Migration 74 entfallen. Massgeblich ist "
        "dokumentenklasse. Gefunden:" + chr(10) + chr(10).join(treffer))
