"""
backend/word/klage_bloecke.py
=============================
Abschnitts-Schicht ueber der Klage-OOXML-Erzeugung.

`Abschnitt` beschreibt einen Dokument-Abschnitt mit Metadaten; `ooxml_zu_text`
projiziert einen OOXML-Block in lesbaren Klartext fuer die Gesamtvorschau.
Der Text entsteht aus DEMSELBEN OOXML, das ins DOCX geht -> kein Drift.
"""
import html
import re
from dataclasses import dataclass


@dataclass
class Abschnitt:
    key: str
    titel: str
    platzhalter: str
    xml: str
    editierbar: bool
    override_feld: str | None


def ooxml_zu_text(xml: str) -> str:
    if not xml:
        return ""
    s = xml.replace("<w:tab/>", "\t")
    s = s.replace("</w:p>", "\n").replace("</w:tr>", "\n").replace("</w:tc>", "\t")
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    zeilen = [z.rstrip() for z in s.split("\n")]
    out = []
    for z in zeilen:
        if z.strip() or (out and out[-1] != ""):
            out.append(z.strip())
    return "\n".join(out).strip()
