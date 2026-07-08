"""
Zielbild-Assertion-Guard (S1.9): kein direkter Schreibweg aus dem Intake
in Akten-Tabellen (dokumente, schadenpositionen, beteiligte, unfalldetails,
personenschaden, mandant) darf ohne den output_adapter laufen.

Test-Strategie: **Fixierte Whitelist der aktuell noch bestehenden
Alt-Aufrufer.** S1.9a friert den Status Quo ein; jeder NEUE direkte
Aufruf schlaegt an. In S1.9b/c/d wird die Whitelist Zeile fuer Zeile
geleert, bis nur noch der output_adapter uebrig bleibt.

Die Whitelist ist eine explizite Datei-Zeilen-Auflistung — damit sie
wirklich schmerzt und nicht verrutscht.
"""
import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BACKEND_ROOT = os.path.join(os.path.dirname(__file__), "..")
INTAKE_PFADE = (
    os.path.join(BACKEND_ROOT, "email_import", "import_service.py"),
    os.path.join(BACKEND_ROOT, "email_import", "fragebogen_parser.py"),
    os.path.join(BACKEND_ROOT, "pdf", "upload_service.py"),
    os.path.join(BACKEND_ROOT, "routers", "dokumente_routes.py"),
    os.path.join(BACKEND_ROOT, "routers", "eakte_routes.py"),
)

# Whitelist der aktuell BEKANNTEN Alt-Aufrufer. Format: (rel_pfad, funktion,
# kommentar). S1.9b/c/d entfernt die Eintraege der Reihe nach.
#
# Nach S1.9b + S1.9c:
#   * import_service.py Zeile 306 — Alt-Pfad Anhang-Registrierung, hinter
#     INTAKE_REVIEW_PFLICHT (S1.9b). Wird erst in S1.9d entfernt.
#   * import_service.py Zeilen 737 + 767 — manuelle "In Akte importieren"-
#     Aktion und .eml-Registrierung. Werden in S1.9d auf output_adapter
#     umgestellt.
#   * import_service.py Zeile 1041 — Fragebogen-JSON-Archivierung (K-P1,
#     S1.9d).
#   * upload_service.py Zeile 171 — Upload-Route Alt-Pfad, ab S1.9c hinter
#     dem Flag (dokumente_routes.upload schaltet unter Flag um).
#   * upload_service.py Zeile 293 — Auto-setze_schadenpositionen, ab S1.9c
#     explizit hinter dem Flag in ``_uebernehme_schaden``.
#   * eakte_routes.py Zeile 226 — E-Akte-Import Alt-Pfad, ab S1.9c hinter
#     dem Flag.
BEKANNTE_ALT_AUFRUFER = {
    ("email_import/import_service.py", "registriere_dokument"): {306, 737, 767, 1041},
    ("pdf/upload_service.py",         "registriere_dokument"):    {171},
    ("pdf/upload_service.py",         "setze_schadenpositionen"): {293},
    ("routers/eakte_routes.py",       "registriere_dokument"):    {254},
}

VERBOTEN = {"registriere_dokument", "setze_schadenpositionen"}


def _sammle_calls(pfad: str, funktion: str) -> set[int]:
    """Alle Zeilennummern in ``pfad``, in denen ``funktion`` aufgerufen wird
    (unabhaengig davon, ob als Name oder Attribut). Import-Statements werden
    ignoriert -- wir suchen echte Calls."""
    with open(pfad, "r", encoding="utf-8") as f:
        quelle = f.read()
    baum = ast.parse(quelle, filename=pfad)
    treffer: set[int] = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Call):
            aufruf = knoten.func
            name = None
            if isinstance(aufruf, ast.Name):
                name = aufruf.id
            elif isinstance(aufruf, ast.Attribute):
                name = aufruf.attr
            if name == funktion:
                treffer.add(knoten.lineno)
    return treffer


class TestIntakeWriteGuard(unittest.TestCase):
    """Kein NEUER direkter Schreibpfad aus dem Intake ohne output_adapter."""

    def test_keine_neuen_direkten_aufrufer(self):
        aktuelle: dict[tuple[str, str], set[int]] = {}
        for pfad in INTAKE_PFADE:
            if not os.path.isfile(pfad):
                continue
            rel = os.path.relpath(pfad, BACKEND_ROOT).replace(os.sep, "/")
            for funktion in VERBOTEN:
                zeilen = _sammle_calls(pfad, funktion)
                if zeilen:
                    aktuelle[(rel, funktion)] = zeilen

        # 1) Kein neuer Schluessel darf auftauchen, den die Whitelist nicht kennt.
        neue_dateien_funktionen = set(aktuelle) - set(BEKANNTE_ALT_AUFRUFER)
        self.assertFalse(
            neue_dateien_funktionen,
            "Neue direkte Intake-Schreibpfade entdeckt (S1.9-Regel verletzt): "
            f"{neue_dateien_funktionen}. Bitte ueber backend/ramicro/"
            "output_adapter.schreibe_dokument() gehen.",
        )

        # 2) Bekannte Alt-Aufrufer duerfen keine ZUSAETZLICHEN Aufruf-Zeilen
        #    haben (jeder neue Aufruf in bekannten Dateien schlaegt an).
        for key, whitelisted_lines in BEKANNTE_ALT_AUFRUFER.items():
            gefunden = aktuelle.get(key, set())
            # Sensitive Testsemantik: Wir erwarten die exakte Whitelist. Wenn
            # zwischenzeitlich ein Alt-Aufrufer entfernt wurde (S1.9b/c/d
            # macht Fortschritt), reduziert sich die Whitelist. Neue
            # Aufrufer -> Test failt.
            zusaetzlich = gefunden - whitelisted_lines
            self.assertFalse(
                zusaetzlich,
                f"{key[0]}: neuer Aufruf von {key[1]}() an Zeile(n) "
                f"{zusaetzlich} -- S1.9-Regel verletzt.",
            )

    def test_output_adapter_ist_der_erlaubte_pfad(self):
        """Der output_adapter muss existieren und den einen Aufruf enthalten,
        der ab S1.9d als einziger Schreibweg gilt."""
        adapter = os.path.join(BACKEND_ROOT, "ramicro", "output_adapter.py")
        self.assertTrue(os.path.isfile(adapter),
                        "output_adapter.py fehlt")
        aufrufe = _sammle_calls(adapter, "registriere_dokument")
        self.assertTrue(aufrufe,
                        "output_adapter muss registriere_dokument aufrufen")


if __name__ == "__main__":
    unittest.main()
