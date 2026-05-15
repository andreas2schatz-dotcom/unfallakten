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
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None  # optional

try:
    from striprtf.striprtf import rtf_to_text
except ImportError:
    rtf_to_text = None

if DocxDocument is None and rtf_to_text is None:
    sys.exit("Weder python-docx noch striprtf installiert.\n"
             "Bitte: pip install striprtf")

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
    "verweis":                            1,   # Stundenverrechnungssätze
    "wertminderung":                      2,   # Wertminderung
    "ghpfupe":                            3,   # Ersatzteilaufschläge / UPE
    "verbringungskosten rechtsprechung":  4,   # Verbringungskosten
    "beilackierung":                      5,   # Beilackierung
    "werkstattrisiko":                    6,   # Kürzung Reparaturrechnung
    "tank":                               7,   # Tankrest
    "ghpfbatterie":                       8,   # Batteriestützbetrieb
    "ghpffehlerspeicher":                 9,   # Fehlerspeicher auslesen
    "ghpfkleinteile":                    10,   # Kleinteilpauschale
    # 11 Technische Kürzungen: kein Textbaustein (SV-Stellungnahme)
    "ghpfzulassungsdienst":              12,   # Zulassungsdienst
    "ghpvkz":                            13,   # Kennzeichen / Schilderkosten
    # 14 Wunschkennzeichen: kein Textbaustein
    "ghpfup":                            15,   # Unkostenpauschale
    "ghpfup.doc":                        15,   # Unkostenpauschale (ghpfup.DOC.rtf)
    "ghpfnagewerbe":                     16,   # Nutzungsausfall
    "ghpfsvkosten":                      17,   # Kürzung Sachverständigenrechnung
    # 18 Mietwagenrechnung: kein Textbaustein
    # 19 Verdienstausfall: kein Textbaustein
}


# -- Hilfsfunktionen -----------------------------------------------------------

def _lese_datei(pfad: Path) -> tuple[str, list[str]]:
    """Extrahiert Text und Feldfunktions-Instruktionen aus DOCX oder RTF."""
    ext = pfad.suffix.lower()

    if ext == ".rtf":
        if rtf_to_text is None:
            sys.exit("striprtf nicht installiert. Bitte: pip install striprtf")
        raw = pfad.read_bytes().decode("latin-1", errors="replace")
        text = rtf_to_text(raw).strip()
        # RTF hat keine strukturierten Feldinstruktionen wie DOCX
        return text, []

    # DOCX
    if DocxDocument is None:
        sys.exit("python-docx nicht installiert. Bitte: pip install python-docx")
    doc = DocxDocument(str(pfad))
    absaetze = []
    felder: list[str] = []
    gesehen: set[str] = set()

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            absaetze.append(text)
        for elem in para._element.iter():
            if elem.tag.endswith('}instrText') and elem.text:
                instr = elem.text.strip()
                if instr and instr not in gesehen:
                    gesehen.add(instr)
                    felder.append(instr)

    return "\n\n".join(absaetze), felder


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

    dateien = sorted(
        [p for p in DOCX_DIR.iterdir() if p.suffix.lower() in (".docx", ".rtf")],
        key=lambda p: p.name.lower(),
    )
    if not dateien:
        sys.exit(f"Keine .docx- oder .rtf-Dateien in {DOCX_DIR}")

    if not DB_PATH.exists():
        sys.exit(f"Datenbank nicht gefunden: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        # textbaustein-Spalte anlegen falls noch nicht vorhanden
        cols = [r[1] for r in conn.execute("PRAGMA table_info(kuerzungsarten)").fetchall()]
        if "textbaustein" not in cols:
            conn.execute("ALTER TABLE kuerzungsarten ADD COLUMN textbaustein TEXT")
            conn.commit()

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
            text, felder_im_dok = _lese_datei(pfad)
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

            if felder_im_dok:
                print(f"   Feldfunktionen ({len(felder_im_dok)}):")
                for f in felder_im_dok:
                    kurztext = f if len(f) <= 80 else f[:77] + "..."
                    print(f"     {{ {kurztext} }}")

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
