"""Erzeugt backend/registry/wiedervorlage_codes.yaml aus der RA-MICRO-Maske.

Quelle ist die Auswahlmaske "Wiedervorlagegruende":

    Z:\\RA\\Mas\\TextWV.msk

Ihre Kopfzeile traegt NotMove=1;NotDel=1;NotInsert=1 -- die Zeilennummer ist
damit dauerhaft der Code, den RA-MICRO in tblAktenWiedervorlagen ablegt. Der
Text selbst steht in keiner der acht SQL-Datenbanken.

Aufruf (Host, Projektwurzel):  py tools/gen_wiedervorlage_codes.py
Im Container:                  python tools/gen_wiedervorlage_codes.py

Ohne --quelle wird EAKTE_BASE_PATH/Mas/TextWV.msk gesucht, sonst Z:\\RA.
Der Guard-Test test_wiedervorlage_codes.py schlaegt fehl, wenn die YAML nicht
mehr zur Maske passt.
"""
import argparse
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)

ZIEL = os.path.join(WURZEL, "backend", "registry", "wiedervorlage_codes.yaml")

# Die Maske fuehrt genau 99 Plaetze. Weicht das ab, hat RA-MICRO die Datei
# umgebaut -- dann darf nicht stillschweigend eine halbe Liste entstehen.
ERWARTETE_PLAETZE = 99

# Ab hier ist die Zahl eine laufende ID aus Z:\RA\Pr\wvgrund (Satznummer + 100)
# und RA-MICRO schreibt den Text zusaetzlich nach sWiedervorlagegrund.
FREITEXT_AB = 100

KOPF_ERWARTET = "Name=Wiedervorlagegründe"


def quellpfad(explizit=None):
    if explizit:
        return explizit
    basis = os.environ.get("EAKTE_BASE_PATH")
    if basis:
        return os.path.join(basis, "Mas", "TextWV.msk")
    return r"Z:\RA\Mas\TextWV.msk"


def lies_maske(pfad):
    """Gibt {code: bezeichnung} zurueck; leere Plaetze bleiben leerer Text."""
    try:
        with open(pfad, "rb") as fh:
            roh = fh.read()
    except OSError as e:
        raise SystemExit(f"Maske nicht lesbar: {pfad}: {e}")

    zeilen = roh.decode("cp1252").splitlines()
    if not zeilen or KOPF_ERWARTET not in zeilen[0]:
        raise SystemExit(
            f"{pfad} ist nicht die Wiedervorlagegruende-Maske "
            f"(Kopfzeile: {zeilen[0][:60] if zeilen else '<leer>'!r})")

    eintraege = [z.rstrip() for z in zeilen[1:]]
    while eintraege and eintraege[-1] == "":
        eintraege.pop()
    if len(eintraege) != ERWARTETE_PLAETZE:
        raise SystemExit(
            f"{pfad}: {len(eintraege)} Plaetze statt {ERWARTETE_PLAETZE} -- "
            f"die Codezuordnung waere nicht mehr sicher")
    return {i: t for i, t in enumerate(eintraege, start=1)}


def _yaml_text(wert):
    return '"' + wert.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render(katalog):
    breite = max(len(_yaml_text(t)) for t in katalog.values() if t) if katalog else 2
    zeilen = [
        "# GENERIERT von tools/gen_wiedervorlage_codes.py — NICHT von Hand editieren.",
        "# ============================================================================",
        "#",
        "# Quelle: RA-MICRO-Auswahlmaske Z:\\RA\\Mas\\TextWV.msk",
        "#   Kopfzeile: Name=Wiedervorlagegründe;MaxRows=99;NotMove=1;NotDel=1;NotInsert=1",
        "#   NotMove/NotDel/NotInsert heisst: die Zeilennummer ist der Code und darf",
        "#   sich nie verschieben. Genau deshalb steht der Text in keiner SQL-Tabelle.",
        "#",
        "# Verifikation (2026-09-07): Aus den gedruckten Wiedervorlagenlisten",
        "# Z:\\RA\\Text\\*wvsik.rtf wurden 81 Eintraege ueber (Aktennummer, Datum) gegen",
        "# tblAktenWiedervorlagen gejoint. Alle 12 daraus ableitbaren Codes stimmen mit",
        "# dieser Maske ueberein (10, 11, 12, 16, 17, 20, 23, 28, 32, 34, 63, 93).",
        "#",
        "# art: Alle 99 Gruende sind Wiedervorlagen. Echte Fristen fuehrt RA-MICRO in",
        "# einer eigenen Verwaltung (Maske Mas\\FRIV.MSK, 'Fristengrund') und legt sie",
        "# in KEINER der acht SQL-Datenbanken ab -- eine Frist-Kachel aus diesen Codes",
        "# zu speisen war der Fehler, den diese Datei ersetzt.",
        "#",
        "# stellungnahme: true dort, wo die Bezeichnung 'nahme' enthaelt -- dieselbe",
        "# Regel, die _stellungnahme_sql() per LIKE '%nahme%' auf den Freitext anwendet.",
        "",
        'version: "2.0-textwv"',
        "",
        "# Darunter Katalogcodes aus der Maske, darueber laufende IDs aus",
        "# Z:\\RA\\Pr\\wvgrund (Satznummer + 100). Fuer die schreibt RA-MICRO den Text",
        "# zusaetzlich nach sWiedervorlagegrund -- sie werden unveraendert uebernommen.",
        f"freitext_ab: {FREITEXT_AB}",
        "",
        "codes:",
    ]
    for code in sorted(katalog):
        text = katalog[code]
        # Der Schluessel steht bei allen Codes in Spalte 2 -- eine Einrueckung
        # nach Ziffernbreite waere kein gueltiges YAML mehr.
        schluessel = f"  {code}:"
        if not text:
            zeilen.append(
                f"{schluessel:<6}{{bezeichnung: \"\", art: wiedervorlage, "
                f"verifiziert: true, offen: true}}")
            continue
        felder = f"bezeichnung: {_yaml_text(text):<{breite}}, art: wiedervorlage, verifiziert: true"
        if "nahme" in text.lower():
            felder += ", stellungnahme: true"
        zeilen.append(f"{schluessel:<6}{{{felder}}}")

    zeilen += [
        "",
        "standard:",
        '  text_und_code_leer: "ohne Angabe"',
        '  code_unbekannt:     "Unbekannter Grund"',
        "  art:                wiedervorlage",
        "",
    ]
    return "\n".join(zeilen)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--quelle", help="Pfad zu TextWV.msk")
    p.add_argument("--pruefen", action="store_true",
                   help="nur vergleichen, nichts schreiben (Exit 1 bei Abweichung)")
    args = p.parse_args()

    pfad = quellpfad(args.quelle)
    inhalt = render(lies_maske(pfad))

    if args.pruefen:
        with open(ZIEL, encoding="utf-8") as fh:
            if fh.read() == inhalt:
                print(f"{ZIEL} ist aktuell.")
                return 0
        print(f"{ZIEL} weicht von {pfad} ab.", file=sys.stderr)
        return 1

    with open(ZIEL, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(inhalt)
    print(f"{ZIEL} aus {pfad} erzeugt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
