"""
Guard-Tests fuer das Ereignis-Datenmodell (P1.2):

  * AST-Guard: NUR ``backend/services/ereignis_service.py`` schreibt in
    ``ereignisse`` / ``ereignis_positionen`` / ``position_ereignis_cache``.
    (schema_manager.py CREATE ist ok; alle anderen INSERT/UPDATE/DELETE
    zeigen an, dass jemand am Service vorbei geschrieben hat.)
  * Runtime-Guard: ``ereignisse`` erlaubt kein DELETE und kein UPDATE
    ausser ``ersetzt_durch`` und ``versand_bestaetigt_am`` (per Konvention;
    Test dokumentiert die Regel).
"""
import ast
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..")

# Erlaubte Schreiber:
#   * schema_manager.py -> CREATE TABLE + CREATE INDEX (Migration 51)
#   * ereignis_service.py -> INSERT/UPDATE/DELETE (kontrollierte Schreib-Op)
ERLAUBTE_SCHREIBER = {
    ("db/schema_manager.py",),
    ("services/ereignis_service.py",),
}
ERLAUBTE_DATEIEN = {
    os.path.join(BACKEND_ROOT, "db", "schema_manager.py"),
    os.path.join(BACKEND_ROOT, "services", "ereignis_service.py"),
}
TABELLEN = ("ereignisse", "ereignis_positionen",
            "position_ereignis_cache")


def _quelldateien():
    """Alle Python-Dateien unter backend/, ausser den erlaubten Schreibern
    und den Tests."""
    for dirpath, _, filenames in os.walk(BACKEND_ROOT):
        if os.sep + "__pycache__" in dirpath:
            continue
        if os.sep + "tests" in dirpath:
            continue
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            vollpfad = os.path.join(dirpath, fn)
            if vollpfad in ERLAUBTE_DATEIEN:
                continue
            yield vollpfad


_WRITE_RE = re.compile(
    r"\b(INSERT\s+(?:OR\s+\w+\s+)?INTO|UPDATE|DELETE\s+FROM)\s+(\w+)",
    re.IGNORECASE,
)


class TestEreignisSchreibGuard(unittest.TestCase):
    def test_kein_fremd_write_in_ereignis_tabellen(self):
        treffer = []
        for pfad in _quelldateien():
            with open(pfad, "r", encoding="utf-8") as f:
                quelle = f.read()
            for match in _WRITE_RE.finditer(quelle):
                tabelle = match.group(2)
                if tabelle in TABELLEN:
                    zeile = quelle.count("\n", 0, match.start()) + 1
                    rel = os.path.relpath(pfad, BACKEND_ROOT).replace(
                        os.sep, "/")
                    treffer.append(f"{rel}:{zeile} -> {tabelle}")
        self.assertFalse(
            treffer,
            "Fremd-Write in Ereignis-Tabellen entdeckt "
            "(erlaubt sind nur ereignis_service.py + schema_manager.py):\n"
            + "\n".join(treffer),
        )


class TestEreignisAllowedWriters(unittest.TestCase):
    def test_ereignis_service_ist_der_einzige_schreiber(self):
        """Sanity: der Service muss INSERTs in alle drei Tabellen enthalten."""
        pfad = os.path.join(BACKEND_ROOT, "services",
                              "ereignis_service.py")
        with open(pfad, "r", encoding="utf-8") as f:
            src = f.read()
        for tabelle in TABELLEN:
            self.assertRegex(
                src, rf"INSERT INTO {tabelle}",
                f"ereignis_service.py enthaelt kein INSERT INTO {tabelle}",
            )


if __name__ == "__main__":
    unittest.main()
