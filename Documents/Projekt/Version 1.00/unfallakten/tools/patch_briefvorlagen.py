"""
Einmal-Werkzeug: Briefvorlagen nachziehen
=========================================
1. Legt ``abschlussbericht_vorlage.docx`` als Kopie des Kanzlei-Briefbogens an
   (Platzhalter ``{{ABRECHNUNGSINHALT}}`` → ``{{ABSCHLUSSINHALT}}``), ergänzt
   die von python-docx benötigte Formatvorlage "Table Grid" und die beiden
   Betreffzeilen ``{{BETREFF1}}`` / ``{{BETREFF2}}`` unter der
   Aktenkurzbezeichnung (Position wie im Forderungsschreiben).
2. Ersetzt in der Kopfzeile der Folgeseiten ("Seite N zum Schreiben vom …")
   das TIME-Feld durch den Platzhalter ``{{DATUM}}``. Das Feld lieferte das
   Tagesdatum des Öffnens, nicht das Briefdatum, und zeigte bis zur nächsten
   Feldaktualisierung den eingefrorenen Stand ("12. März 2026").

Aufruf auf dem Host:  py tools/patch_briefvorlagen.py
"""
import shutil
import sys
import zipfile
from pathlib import Path

WORD_DIR = Path(__file__).resolve().parent.parent / "backend" / "word"

_MARKER = " zum Schreiben vom </w:t></w:r>"
_DATUM_RUN = (
    '<w:r><w:rPr><w:rStyle w:val="Seitenzahl"/>'
    '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
    '<w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>'
    '<w:t>{{DATUM}}</w:t></w:r>'
)

# Betreffzeilen unter der Aktenkurzbezeichnung — Formatierung wortgleich zur
# Vorlage des Forderungsschreibens (Arial, fett), damit beide Briefe im
# Betreffblock identisch aussehen.
_BETREFF_RPR = ('<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
                '<w:b/><w:bCs/></w:rPr>')
_BETREFF_PPR = ('<w:pPr><w:widowControl w:val="0"/>'
                '<w:spacing w:line="200" w:lineRule="atLeast"/>'
                '<w:jc w:val="both"/>' + _BETREFF_RPR + '</w:pPr>')
_BETREFF_ZEILEN = "".join(
    f'<w:p>{_BETREFF_PPR}<w:r>{_BETREFF_RPR}<w:t>{{{{BETREFF{n}}}}}</w:t></w:r></w:p>'
    for n in (1, 2)
)

# Standard-Tabellenformat; die Vorlagen bringen nur "NormaleTabelle" mit,
# python-docx verlangt für tabelle.style = "Table Grid" diese Definition.
_TABLE_GRID = (
    '<w:style w:type="table" w:styleId="TableGrid">'
    '<w:name w:val="Table Grid"/><w:basedOn w:val="NormaleTabelle"/>'
    '<w:uiPriority w:val="39"/>'
    '<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
    '<w:tblPr><w:tblBorders>'
    '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
    '</w:tblBorders></w:tblPr></w:style>'
)


def _ersetze_datumsfeld(xml: str) -> tuple[str, bool]:
    """TIME-Feld hinter 'zum Schreiben vom' durch {{DATUM}} ersetzen."""
    if _MARKER not in xml or "{{DATUM}}" in xml:
        return xml, False
    kopf, rest = xml.split(_MARKER, 1)
    ende = rest.find("</w:p>")
    if ende < 0 or "TIME yyyy" not in rest[:ende]:
        return xml, False
    return kopf + _MARKER + _DATUM_RUN + rest[ende:], True


def _patche_datei(pfad: Path, umbenennungen: dict = None,
                  table_grid: bool = False,
                  betreffzeilen: bool = False) -> list[str]:
    umbenennungen = umbenennungen or {}
    quelle = pfad.read_bytes()
    protokoll = []
    puffer = pfad.with_suffix(".docx.tmp")

    with zipfile.ZipFile(pfad, "r") as zin, \
         zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("word/header") and item.filename.endswith(".xml"):
                text = data.decode("utf-8")
                neu, geaendert = _ersetze_datumsfeld(text)
                if geaendert:
                    protokoll.append(f"{item.filename}: TIME-Feld → {{{{DATUM}}}}")
                    data = neu.encode("utf-8")
            elif item.filename == "word/document.xml" and (umbenennungen or betreffzeilen):
                text = data.decode("utf-8")
                for alt, neu_ph in (umbenennungen or {}).items():
                    if alt in text:
                        text = text.replace(alt, neu_ph)
                        protokoll.append(f"document.xml: {alt} → {neu_ph}")
                if betreffzeilen and "{{BETREFF1}}" not in text:
                    marke = "{{Aktenkurzbezeichnung}}"
                    ende = text.find("</w:p>", text.find(marke)) + len("</w:p>")
                    text = text[:ende] + _BETREFF_ZEILEN + text[ende:]
                    protokoll.append(
                        "document.xml: Betreffzeilen unter der "
                        "Aktenkurzbezeichnung ergänzt")
                data = text.encode("utf-8")
            elif item.filename == "word/styles.xml" and table_grid:
                text = data.decode("utf-8")
                if 'w:styleId="TableGrid"' not in text:
                    text = text.replace("</w:styles>", _TABLE_GRID + "</w:styles>")
                    protokoll.append("styles.xml: Formatvorlage 'Table Grid' ergänzt")
                data = text.encode("utf-8")
            zout.writestr(item, data)

    if protokoll:
        puffer.replace(pfad)
    else:
        puffer.unlink()
        pfad.write_bytes(quelle)
    return protokoll


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ziel = WORD_DIR / "abschlussbericht_vorlage.docx"
    if not ziel.exists():
        shutil.copy(WORD_DIR / "abrechnungsuebersicht_vorlage.docx", ziel)
        print(f"angelegt: {ziel.name} (Kopie des Kanzlei-Briefbogens)")

    aufgaben = [
        (ziel, {"{{ABRECHNUNGSINHALT}}": "{{ABSCHLUSSINHALT}}"}, True, True),
        (WORD_DIR / "forderungsschreiben_vorlage.docx",   None, False, False),
        (WORD_DIR / "sachstandsanfrage_vorlage.docx",     None, False, False),
        (WORD_DIR / "abrechnungsuebersicht_vorlage.docx", None, False, False),
    ]
    for pfad, umbenennungen, table_grid, betreffzeilen in aufgaben:
        eintraege = _patche_datei(pfad, umbenennungen, table_grid, betreffzeilen)
        print(f"\n{pfad.name}")
        for e in eintraege or ["  (nichts zu tun)"]:
            print(f"  {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
