"""
Abschluss-/Sachstandsbericht – DOCX-Renderer
=============================================
Rendert das Übersichts-Objekt (services/abschluss_uebersicht.py) auf dem
echten Kanzlei-Briefbogen. Der Renderer ist "dumm": keine eigene Rechenlogik.

Vorlage ``abschlussbericht_vorlage.docx`` — dieselbe Briefbogen-Datei wie beim
Forderungsschreiben und der Abrechnungsübersicht. Sie liefert Sozietätsleiste,
Empfängerfeld, Az-/Datumsfeld sowie Kopf- und Fußzeilen; dieser Renderer füllt
die Platzhalter und hängt den Brieftext an die Stelle der Inhaltsmarke.

Anatomie (Spec §9): Betreff → Ergebnis bzw. Arbeitsstand → "Was bei Ihnen
ankommt" (nur Abschluss) → Gegenüberstellung + Zahlungsverlauf →
Anwaltskosten → Schluss (+ Bewertungszeile) → Grußformel.
"""
import io
import logging
import re
from datetime import date
from pathlib import Path

from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Pt, Cm, Emu, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from ..services.abschluss_uebersicht import baue_abschluss_uebersicht
from .forderungsschreiben_wv import (
    _datum_deutsch, _hole_sb_info, _mandant_anrede_nominativ,
    _unterschrift_bytes,
)
from .styling import (
    entferne_tabellen_raender, setze_zellen_farbe, fmt_euro,
)

logger = logging.getLogger(__name__)

_VORLAGE = Path(__file__).resolve().parent / "abschlussbericht_vorlage.docx"

# Einheitlicher Brieftext: Arial 12 pt, wie im Forderungsschreiben
# (RA Schatz, 2026-08-26). Die Vorlage selbst setzt dieselbe Schrift.
SCHRIFT    = "Arial"
SCHRIFT_PT = 12

# Kanzleifarben, deckungsgleich mit abrechnungsuebersicht_service.py
BLAU       = RGBColor(0x54, 0x88, 0xD4)
WEISS      = RGBColor(0xFF, 0xFF, 0xFF)
_KOPF_BG   = "2C3E50"     # Tabellenkopf
_ZEBRA_BG  = "F5F6F8"     # jede zweite Datenzeile
_SUMME_BG  = "EBF2FB"     # Summenzeile
_KACHEL_BG = "D6E8FF"     # Ergebnis-Kachel

_BEWERTUNG_URL = "https://g.page/r/CaCarkH1DYGQEBM/review"

# Maße des Unterschriftsbildes, gleich zum Forderungsschreiben
_SIG_BREITE = Emu(981075)
_SIG_HOEHE  = Emu(485775)

_INHALTSMARKE = "{{ABSCHLUSSINHALT}}"

_STATUS_LABEL = {
    "voll":     "vollständig gezahlt",
    "gekuerzt": "gekürzt",
    "offen":    "noch offen",
    "abzug":    "Abzugsposten",
}

# RA-Micro speichert sAnrede numerisch; der Connector liefert je nach Weg den
# Code oder den Klartext ("Herr"). Beides muss hier ankommen.
_ANREDE_CODE_NOMINATIV = {
    "1": "Herr", "2": "Frau", "3": "Herr", "5": "Herr",
    "6": "Rechtsanwälte", "7": "Frau", "8": "Eheleute", "10": "Frau",
}


def dateiendung() -> str:
    return "docx"


def _jahr_vierstellig(text: str) -> str:
    """
    Zweistellige Jahre in einem Freitext auf vier Stellen bringen. RA-Micros
    Aktenlangbezeichnung lautet z.B. "Unfall vom 11.06.26"; im Brief soll
    überall TT.MM.JJJJ stehen (RA Schatz, 2026-08-26).
    """
    return re.sub(r"(?<!\d)(\d{1,2}\.\d{1,2}\.)(\d{2})(?!\d)",
                  lambda m: f"{m.group(1)}20{m.group(2)}", text or "")


def _datum(wert) -> str:
    """
    Datum als TT.MM.JJJJ. Die Quellen sind uneinheitlich: SQLite liefert ISO
    (2026-06-11), RA-Micros varU-TAG deutsch und oft zweistellig (11.06.26).
    """
    text = (wert or "").strip()
    if not text:
        return "–"
    if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", text):
        j, m, t = text.split("-")
        return f"{int(t):02d}.{int(m):02d}.{j}"
    treffer = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})", text)
    if treffer:
        t, m, j = treffer.groups()
        if len(j) == 2:
            j = f"20{j}"
        return f"{int(t):02d}.{int(m):02d}.{j}"
    return text


# ── Anrede ───────────────────────────────────────────────────────────────────

def _anrede_zeile(mandant: dict) -> str:
    """Briefanrede des Mandanten — RA-Micro-Briefanrede hat Vorrang."""
    briefanrede = (mandant.get("briefanrede") or "").strip()
    if briefanrede:
        return briefanrede if briefanrede.endswith(",") else f"{briefanrede},"

    name = (mandant.get("name") or "").strip()
    nachname = name.split()[-1] if name else ""
    code = (mandant.get("anrede") or "").strip()
    nominativ = (_ANREDE_CODE_NOMINATIV.get(code)
                 or _mandant_anrede_nominativ(mandant))

    if nachname and nominativ == "Herr":
        return f"Sehr geehrter Herr {nachname},"
    if nachname and nominativ == "Frau":
        return f"Sehr geehrte Frau {nachname},"
    if nachname and nominativ == "Eheleute":
        return f"Sehr geehrte Eheleute {nachname},"
    return "Sehr geehrte Damen und Herren,"


# ── Bausteine ────────────────────────────────────────────────────────────────

def _run(absatz, text: str, bold: bool = False, farbe: RGBColor = None):
    run = absatz.add_run(text)
    run.font.name = SCHRIFT
    run.font.size = Pt(SCHRIFT_PT)
    run.font.bold = bold
    if farbe is not None:
        run.font.color.rgb = farbe
    return run


def _absatz(doc, text: str, bold: bool = False, farbe: RGBColor = None):
    p = doc.add_paragraph()
    _run(p, text, bold=bold, farbe=farbe)
    return p


def _hyperlink(absatz, text: str, url: str):
    """Klickbarer Verweis — python-docx bringt dafür nichts Fertiges mit."""
    r_id = absatz.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)

    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    schrift = OxmlElement("w:rFonts")
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        schrift.set(qn(attr), SCHRIFT)
    rPr.append(schrift)
    groesse = OxmlElement("w:sz")
    groesse.set(qn("w:val"), str(SCHRIFT_PT * 2))
    rPr.append(groesse)
    farbe = OxmlElement("w:color")
    farbe.set(qn("w:val"), "5488D4")
    rPr.append(farbe)
    unterstrichen = OxmlElement("w:u")
    unterstrichen.set(qn("w:val"), "single")
    rPr.append(unterstrichen)
    run.append(rPr)

    knoten = OxmlElement("w:t")
    knoten.text = text
    run.append(knoten)
    link.append(run)
    absatz._p.append(link)
    return link


def _titel(doc, text: str):
    p = doc.add_paragraph()
    _run(p, text, bold=True, farbe=BLAU)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after  = Pt(4)
    p.paragraph_format.keep_with_next = True
    return p


def _kachel(doc, zeilen):
    """Ergebnis-Kachel: hellblau hinterlegter Kasten über die Textbreite."""
    tab = doc.add_table(rows=1, cols=1)
    zelle = tab.rows[0].cells[0]
    setze_zellen_farbe(zelle, _KACHEL_BG)
    for i, (text, hervorgehoben) in enumerate(zeilen):
        p = zelle.paragraphs[0] if i == 0 else zelle.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _run(p, text, bold=hervorgehoben, farbe=BLAU)
    doc.add_paragraph()
    return tab


def _textbreite(doc) -> Emu:
    """Nutzbare Textbreite des Briefbogens (Seitenbreite minus Ränder)."""
    s = doc.sections[0]
    # Length-Arithmetik liefert ein blankes int — wieder als Länge fassen
    return Emu(s.page_width - s.left_margin - s.right_margin)


def _feste_breiten(tab, breiten):
    """
    Word/LibreOffice ignorieren Zellbreiten, solange die Tabelle auf
    Automatik steht — daher tblLayout=fixed und tblGrid mitziehen.
    """
    tab.autofit = False
    gesamt = sum(int(b.twips) for b in breiten)
    tblPr = tab._tbl.tblPr

    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa")
    tblW.set(qn("w:w"), str(gesamt))

    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)

    # Schmale Zellinnenränder — bei Arial 12 pt zählt jeder Millimeter
    raender = OxmlElement("w:tblCellMar")
    for seite in ("left", "right"):
        el = OxmlElement(f"w:{seite}")
        el.set(qn("w:w"), "57")          # 0,1 cm
        el.set(qn("w:type"), "dxa")
        raender.append(el)
    tblPr.append(raender)

    for gridCol, breite in zip(tab._tbl.find(qn("w:tblGrid")), breiten):
        gridCol.set(qn("w:w"), str(int(breite.twips)))
    for zeile in tab.rows:
        for zelle, breite in zip(zeile.cells, breiten):
            zelle.width = breite


def _kopfzeile_wiederholen(tab):
    """Kopfzeile auf Folgeseiten wiederholen, Zeilen nicht aufbrechen."""
    for index, zeile in enumerate(tab.rows):
        trPr = zeile._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if index == 0:
            trPr.append(OxmlElement("w:tblHeader"))


def _tabelle(doc, spalten: list, zeilen: list, anteile: list,
             summenzeile: bool = False):
    """
    Erste Spalte linksbündig, alle weiteren rechtsbündig — Kopfzeile
    eingeschlossen (RA Schatz, 2026-08-26).

    anteile:     Spaltenbreiten als Anteil der Textbreite (Summe 1,0).
    summenzeile: letzte Zeile fett und hinterlegt absetzen.
    """
    tab = doc.add_table(rows=1 + len(zeilen), cols=len(spalten))
    entferne_tabellen_raender(tab)

    textbreite = _textbreite(doc)
    _feste_breiten(tab, [Cm(textbreite.cm * a) for a in anteile])

    def _zelle(zelle, wert, s_idx, bold, farbe, hintergrund):
        setze_zellen_farbe(zelle, hintergrund)
        p = zelle.paragraphs[0]
        p.alignment = (WD_ALIGN_PARAGRAPH.LEFT if s_idx == 0
                       else WD_ALIGN_PARAGRAPH.RIGHT)
        _run(p, str(wert), bold=bold, farbe=farbe)

    for i, kopf in enumerate(spalten):
        _zelle(tab.rows[0].cells[i], kopf, i, True, WEISS, _KOPF_BG)

    for z_idx, zeile_daten in enumerate(zeilen):
        ist_summe = summenzeile and z_idx == len(zeilen) - 1
        hintergrund = (_SUMME_BG if ist_summe
                       else _ZEBRA_BG if z_idx % 2 == 0 else "FFFFFF")
        for s_idx, wert in enumerate(zeile_daten):
            _zelle(tab.rows[z_idx + 1].cells[s_idx], wert, s_idx,
                   ist_summe, None, hintergrund)

    _kopfzeile_wiederholen(tab)
    return tab


def _fuege_grussformel_ein(doc, sb_kuerzel: str):
    """
    Grußformel wie im Forderungsschreiben: 'Mit freundlichen Grüßen',
    direkt darunter Unterschriftsbild, Name und Titel des Aktensachbearbeiters.
    """
    sb = _hole_sb_info(sb_kuerzel)
    _absatz(doc, "Mit freundlichen Grüßen")

    unterschrift = _unterschrift_bytes(sb_kuerzel)
    if unterschrift:
        try:
            p = doc.add_paragraph()
            p.add_run().add_picture(io.BytesIO(unterschrift),
                                    width=_SIG_BREITE, height=_SIG_HOEHE)
        except Exception as e:
            logger.warning("Unterschrift (%s) nicht einbettbar: %s",
                           sb_kuerzel or "-", e)
            doc.add_paragraph()
    else:
        doc.add_paragraph()

    _absatz(doc, sb["name"])
    _absatz(doc, sb["titel"])


# ── Vorlage ──────────────────────────────────────────────────────────────────

def _ersetze_platzhalter(element, werte: dict):
    """Ersetzt {{…}} in allen Textknoten — auch in Textrahmen und Kopfzeilen."""
    for knoten in element.iter(qn("w:t")):
        if not knoten.text or "{{" not in knoten.text:
            continue
        for schluessel, wert in werte.items():
            if schluessel in knoten.text:
                knoten.text = knoten.text.replace(schluessel, wert)


def _oeffne_vorlage(werte: dict) -> Document:
    """Briefbogen laden, Platzhalter füllen, Inhaltsmarke entfernen."""
    if not _VORLAGE.exists():
        raise FileNotFoundError(f"Vorlage fehlt: {_VORLAGE}")
    doc = Document(str(_VORLAGE))

    _ersetze_platzhalter(doc.element.body, werte)
    for abschnitt in doc.sections:
        for kopf in (abschnitt.header, abschnitt.first_page_header,
                     abschnitt.even_page_header):
            _ersetze_platzhalter(kopf._element, werte)

    for p in doc.paragraphs:
        if _INHALTSMARKE in p.text:
            p._element.getparent().remove(p._element)
            break
    else:
        logger.warning("Inhaltsmarke %s in der Vorlage nicht gefunden",
                       _INHALTSMARKE)
    return doc


# ── Generator ────────────────────────────────────────────────────────────────

def generiere_abschlussbericht(akte_daten: dict) -> bytes:
    ueb = baue_abschluss_uebersicht(akte_daten)
    modus = ueb["modus"]
    az = ueb["akte"]["az"]
    summen = ueb["summen"]
    mandant = ueb["mandant"]
    heute = date.today()

    akte = akte_daten.get("akte") or {}
    kurzbezeichnung = akte.get("kurzbezeichnung") or ""
    # Betreffblock unter der Kurzbezeichnung: Aktenlangbezeichnung, darunter
    # die Art des Schreibens (RA Schatz, 2026-08-26).
    langbezeichnung = _jahr_vierstellig((akte.get("aktenbezeichnung") or "").strip())
    berichtsart = ("Abschlussbericht" if modus == "abschluss"
                   else "Sachstandsbericht")

    doc = _oeffne_vorlage({
        "{{EMPF_NAME}}":            mandant["name"],
        "{{EMPF_STRASSE}}":         mandant["anschrift"],
        "{{EMPF_ORT}}":             mandant["plz_ort"],
        "{{EMPF_EMAIL}}":           "",
        "{{AKTENZEICHEN}}":         az,
        "{{Aktenkurzbezeichnung}}": kurzbezeichnung,
        "{{BETREFF1}}":             langbezeichnung,
        "{{BETREFF2}}":             berichtsart,
        "{{DATUM}}":                _datum_deutsch(heute),
    })

    doc.add_paragraph()
    _absatz(doc, _anrede_zeile(mandant))
    doc.add_paragraph()

    if modus == "abschluss":
        _absatz(doc, "Ihre Unfallsache ist abgeschlossen. Nachfolgend "
                     "erhalten Sie eine Übersicht über den "
                     "Regulierungsverlauf:")
        doc.add_paragraph()
        _kachel(doc, [
            (f"Für Sie durchgesetzt: {fmt_euro(summen['gezahlt'])}", True),
            (f"von {fmt_euro(summen['gefordert'])} geforderten "
             f"Schadenersatzansprüchen", False),
        ])
        _titel(doc, "Was davon bei Ihnen ankommt")
        _absatz(doc, f"Insgesamt reguliert wurden "
                     f"{fmt_euro(summen['gezahlt'])} — davon gingen "
                     f"{fmt_euro(summen['an_mandant'])} direkt an Sie.")
        if summen["an_dritte"] > 0.005:
            _absatz(doc, f"Die übrigen {fmt_euro(summen['an_dritte'])} wurden "
                         f"unmittelbar an Dritte gezahlt (z. B. Werkstatt, "
                         f"Sachverständiger, Mietwagenunternehmen).")
    else:
        _titel(doc, "Woran wir arbeiten / worauf wir warten")
        offene = [p for p in ueb["positionen"] if p["status"] == "offen"]
        erledigte = [p for p in ueb["positionen"] if p["status"] == "voll"]
        for pos in erledigte:
            _absatz(doc, f"✓ {pos['label']} — erledigt")
        for pos in offene:
            _absatz(doc, f"○ {pos['label']} — noch offen "
                         f"({fmt_euro(pos['gefordert'])})")
        if ueb["schluss"]["naechste_schritte_text"]:
            _absatz(doc, f"Nächster Schritt: "
                         f"{ueb['schluss']['naechste_schritte_text']}", bold=True)

    _titel(doc, "Gegenüberstellung Ihrer Ansprüche")
    zeilen = []
    for p in ueb["positionen"]:
        grund = p["kuerzung_grund"] or _STATUS_LABEL[p["status"]]
        zeilen.append([
            p["label"],
            fmt_euro(p["gefordert"]),
            fmt_euro(p["gezahlt"]) if p["gezahlt"] is not None else "–",
            fmt_euro(p["differenz"]) if p["differenz"] > 0.005 else "–",
            grund,
        ])
    zeilen.append(["Gesamt", fmt_euro(summen["gefordert"]),
                   fmt_euro(summen["gezahlt"]),
                   fmt_euro(summen["differenz"]) if summen["differenz"] > 0.005 else "–",
                   ""])
    _tabelle(doc, ["Position", "gefordert", "gezahlt", "Differenz", "Anmerkung"],
             zeilen, [0.35, 0.15, 0.15, 0.15, 0.20], summenzeile=True)

    verlauf = [(z["datum"], p["label"], z["betrag"], z["versicherung"])
               for p in ueb["positionen"] for z in p["zahlungen"]]
    if verlauf:
        doc.add_paragraph()
        _titel(doc, "Regulierungsverlauf")
        _tabelle(doc, ["Abrechnung", "Position", "Betrag", "Versicherung"],
                 [[_datum(d), lbl, fmt_euro(b), v]
                  for d, lbl, b, v in sorted(verlauf)],
                 [0.22, 0.35, 0.15, 0.28])

    doc.add_paragraph()
    _titel(doc, "Ihre Anwaltskosten")
    ak = ueb["anwaltskosten"]
    # Bei vorsteuerabzugsberechtigten Mandanten erstattet die Gegenseite nur
    # den Nettobetrag; die Umsatzsteuer holt sich der Mandant als Vorsteuer
    # vom Finanzamt. "Für Sie kostenfrei" wäre dort falsch (RA Schatz,
    # 2026-08-27).
    if ak.get("vorsteuer"):
        if ak.get("gezahlt_von_gegner"):
            betrag = f"in Höhe von {fmt_euro(ak['gezahlt_von_gegner'])} netto "
        elif ak.get("rvg_betrag"):
            betrag = (f"nach dem RVG (berechnet aus dem regulierten Betrag) "
                      f"in Höhe von {fmt_euro(ak['rvg_betrag'])} netto ")
        else:
            betrag = ""
        _absatz(doc, f"Unsere Gebühren {betrag}werden von der Gegenseite "
                     f"getragen. Die Umsatzsteuer erstattet die Gegenseite "
                     f"nicht, da Sie zum Vorsteuerabzug berechtigt sind; wir "
                     f"stellen sie Ihnen gesondert in Rechnung.")
    elif ak.get("gezahlt_von_gegner"):
        _absatz(doc, f"Unsere Gebühren in Höhe von "
                     f"{fmt_euro(ak['gezahlt_von_gegner'])} wurden von der "
                     f"Gegenseite getragen — für Sie kostenfrei.")
    elif ak.get("rvg_betrag"):
        _absatz(doc, f"Unsere Gebühren nach dem RVG (berechnet aus dem "
                     f"regulierten Betrag) in Höhe von "
                     f"{fmt_euro(ak['rvg_betrag'])} werden von der Gegenseite "
                     f"getragen — für Sie kostenfrei.")
    else:
        _absatz(doc, "Unsere Gebühren werden von der Gegenseite getragen — "
                     "für Sie kostenfrei.")

    schluss = ueb["schluss"]
    zeige_verjaehrung = (schluss["typ"] == "vorbehalt_spaetfolgen"
                         and schluss["verjaehrung_datum"])
    if schluss["text"] or zeige_verjaehrung:
        doc.add_paragraph()
        _titel(doc, "Abschluss" if modus == "abschluss" else "Ausblick")
        if schluss["text"]:
            _absatz(doc, schluss["text"])
        if zeige_verjaehrung:
            _absatz(doc, f"Bitte beachten Sie: Ansprüche wegen etwaiger "
                         f"Spätfolgen verjähren am "
                         f"{_datum(schluss['verjaehrung_datum'])}.",
                    bold=True)

    if ueb["bewertung_cta"]:
        doc.add_paragraph()
        p = _absatz(doc, "Waren Sie mit unserer Leistung zufrieden? Teilen "
                         "Sie Ihre Erfahrung und bewerten Sie unsere Kanzlei "
                         "auf Google: ")
        _hyperlink(p, _BEWERTUNG_URL, _BEWERTUNG_URL)

    doc.add_paragraph()
    if modus == "abschluss":
        _absatz(doc, "Wir freuen uns, ein für Sie positives Ergebnis erlangt "
                     "haben zu können und hoffen, Sie auch in Zukunft "
                     "anwaltlich beraten zu dürfen. Sollten Sie noch "
                     "Rückfragen haben, stehen wir Ihnen gerne zur Verfügung.")
    else:
        _absatz(doc, "Sollten Sie noch Rückfragen haben, stehen wir Ihnen "
                     "gerne zur Verfügung.")
    doc.add_paragraph()
    _fuege_grussformel_ein(
        doc, (akte_daten.get("akte") or {}).get("sachbearbeiter") or "")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
