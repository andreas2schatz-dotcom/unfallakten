"""
import_textbausteine.py
========================
Liest 19 Word-Dateien aus ./textbausteine/ und schreibt den Text in
kuerzungsarten.textbaustein.

Verwendung:
    python import_textbausteine.py            # Dry-Run: zeigt Platzhalter + Mapping
    python import_textbausteine.py --write    # Schreibt in DB

Voraussetzung: pip install python-docx
DB-Pfad wird aus Umgebungsvariable DB_PATH gelesen oder Standard verwendet.
"""

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path

try:
    from docx import Document
except ImportError:
    sys.exit("python-docx nicht installiert. Bitte: pip install python-docx")

# -- Pfade ---------------------------------------------------------------------

SCRIPT_DIR  = Path(__file__).parent
DOCX_DIR    = SCRIPT_DIR / "textbausteine"
DEFAULT_DB  = SCRIPT_DIR.parent / "backend" / "data" / "unfallakten.db"
DB_PATH     = Path(os.environ.get("DB_PATH", DEFAULT_DB))

# -- Mapping: Dateiname (ohne .docx) -> kuerzungsarten.id ----------------------
# Wird nach dem ersten Dry-Run gemeinsam mit dem Anwalt ausgefuellt.
# Schluessel: Dateiname ohne Extension (Gross-/Kleinschreibung egal)
# Wert: id aus kuerzungsarten-Tabelle (1-19)

MAPPING: dict[str, int] = {
    # Beispiele - nach Dry-Run anpassen:
    # "stundenverrechnungssaetze": 1,
    # "nutzungsausfall":           2,
}


# -- Hilfsfunktionen -----------------------------------------------------------

def _lese_docx(pfad: Path) -> str:
    """Extrahiert den vollstaendigen Text aus einer Word-Datei."""
    doc = Document(str(pfad))
    absaetze = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            absaetze.append(text)
    return "\n\n".join(absaetze)


def _finde_platzhalter(text: str) -> list[str]:
    """Gibt alle <PLATZHALTER> im Text zurueck (ohne Duplikate, sortiert)."""
    gefunden = re.findall(r"<([A-Z_]+)>", text)
    return sorted(set(gefunden))


def _lade_kuerzungsarten(conn: sqlite3.Connection) -> dict[int, str]:
    """Gibt {id: bezeichnung} fuer alle Kuerzungsarten zurueck."""
    rows = conn.execute("SELECT id, bezeichnung FROM kuerzungsarten ORDER BY id").fetchall()
    return {r[0]: r[1] for r in rows}


# -- Haupt-Logik ---------------------------------------------------------------

def run(schreiben: bool) -> None:
    if not DOCX_DIR.exists():
        sys.exit(f"Ordner nicht gefunden: {DOCX_DIR}")

    dateien = sorted(DOCX_DIR.glob("*.docx"))
    if not dateien:
        sys.exit(f"Keine .docx-Dateien in {DOCX_DIR}")

    if not DB_PATH.exists():
        sys.exit(f"Datenbank nicht gefunden: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        kuerzungsarten = _lade_kuerzungsarten(conn)

        print(f"\n{'='*60}")
        print(f"Modus: {'SCHREIBEN' if schreiben else 'DRY-RUN (nur Analyse)'}")
        print(f"Datenbank: {DB_PATH}")
        print(f"Dateien gefunden: {len(dateien)}")
        print(f"{'='*60}\n")

        alle_platzhalter: set[str] = set()
        nicht_gemappt: list[str] = []

        for pfad in dateien:
            name_key = pfad.stem.lower()
            kuerzungsart_id = MAPPING.get(name_key) or MAPPING.get(pfad.stem)
            text = _lese_docx(pfad)
            platzhalter = _finde_platzhalter(text)
            alle_platzhalter.update(platzhalter)

            print(f"Datei: {pfad.name}")
            print(f"   Mapping -> ", end="")

            if kuerzungsart_id:
                bezeichnung = kuerzungsarten.get(kuerzungsart_id, "???")
                print(f"ID {kuerzungsart_id}: {bezeichnung}")
            else:
                print("KEIN MAPPING (-> in MAPPING-Dict eintragen)")
                nicht_gemappt.append(pfad.name)

            print(f"   Laenge: {len(text)} Zeichen")
            if platzhalter:
                print(f"   Platzhalter: {', '.join(f'<{p}>' for p in platzhalter)}")
            else:
                print("   Platzhalter: keine")

            if schreiben and kuerzungsart_id:
                conn.execute(
                    "UPDATE kuerzungsarten SET textbaustein = ? WHERE id = ?",
                    (text, kuerzungsart_id)
                )
                print("   OK Geschrieben.")
            print()

        if schreiben:
            conn.commit()

        print(f"{'='*60}")
        print(f"ALLE GEFUNDENEN PLATZHALTER:")
        for p in sorted(alle_platzhalter):
            print(f"  <{p}>")

        if nicht_gemappt:
            print(f"\n!!! NICHT GEMAPPT ({len(nicht_gemappt)} Dateien):")
            for f in nicht_gemappt:
                print(f"  {f}")
            print("-> Bitte MAPPING-Dict im Script ergaenzen und erneut ausfuehren.")

        print(f"{'='*60}\n")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Textbaustein-Import fuer Kuerzungsarten")
    parser.add_argument("--write", action="store_true",
                        help="Werte in DB schreiben (ohne Flag: nur Dry-Run)")
    args = parser.parse_args()
    run(schreiben=args.write)
