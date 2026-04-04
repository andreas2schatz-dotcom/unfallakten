"""
Parser für Kfz-Prüfberichte (ControlExpert, DEKRA, etc.)

Erkennt:
- Prüfdienstleister und Auftraggeber
- Fahrzeugdaten (Hersteller, Typ, EZ, Kennzeichen)
- Abzüge (technische Prüfung, Werkstattalternative/fiktiv, NfA)
- Referenzwerkstatt
- Gesamtergebnis netto

Wichtig: DEKRA-Berichte werden oft als Bild-PDF angeliefert
         (Seiten haben has_image_pages=True) -> eingeschränkte Extraktion
"""
import re
from dataclasses import dataclass, field
from typing import Optional
from .pdf_utils import parse_betrag, normalize_text


@dataclass
class ParsedFahrzeug:
    hersteller: str = ""
    typ: str = ""
    erstzulassung: str = ""  # YYYY-MM-DD
    kennzeichen: str = ""


@dataclass
class ParsedAbzug:
    kategorie: str    # "technisch", "werkstattalternative", "nfa", "sonstig"
    bezeichnung: str  # Originaltext
    betrag: float = 0.0  # positiver Wert, ist immer ein Abzug
    konfidenz: float = 0.9


@dataclass
class ParsedReferenzwerkstatt:
    name: str = ""
    adresse: str = ""
    plz_ort: str = ""          # PLZ + Ort, z.B. "60599 Frankfurt am Main"
    entfernung_km: Optional[float] = None
    lohn_mechanik: Optional[float] = None
    lohn_elektrik: Optional[float] = None
    lohn_karosserie: Optional[float] = None
    lohn_lack: Optional[float] = None


@dataclass
class PruefberichtParseResult:
    pruefdienstleister: str = ""
    auftraggeber: str = ""
    vorgangsnummer: str = ""
    fahrzeug: ParsedFahrzeug = field(default_factory=ParsedFahrzeug)
    reparaturkosten_brutto: Optional[float] = None
    reparaturkosten_netto_vor_pruefung: Optional[float] = None
    abzug_technisch: Optional[float] = None
    abzug_werkstattalternative: Optional[float] = None
    abzug_nfa: Optional[float] = None
    abzug_gesamt: Optional[float] = None
    reparaturkosten_nach_pruefung: Optional[float] = None
    referenzwerkstatt: Optional[ParsedReferenzwerkstatt] = None
    abzuege_detail: list[ParsedAbzug] = field(default_factory=list)
    ist_image_pdf: bool = False  # True = DEKRA-Scan, keine Textextraktion möglich
    konfidenz: float = 0.0
    warnungen: list[str] = field(default_factory=list)


def _parse_erstzulassung(datum_str: str) -> str:
    """Konvertiert DD.MM.YYYY zu YYYY-MM-DD."""
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", datum_str.strip())
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return datum_str


def _parse_controlexpert(text: str) -> PruefberichtParseResult:
    """Parser speziell für ControlExpert-Berichte."""
    result = PruefberichtParseResult(pruefdienstleister="ControlExpert")

    # Auftraggeber
    auftr_m = re.search(r"Auftraggeber\s+(\w+)", text, re.IGNORECASE)
    if auftr_m:
        result.auftraggeber = auftr_m.group(1).strip()

    # Vorgangsnummer
    vorg_m = re.search(r"Vorgangs[-.]?Nr\.?\s+(\d+)", text, re.IGNORECASE)
    if vorg_m:
        result.vorgangsnummer = vorg_m.group(1).strip()

    # Fahrzeugdaten
    herst_m = re.search(r"Hersteller\s+([A-ZÄÖÜ][A-ZÄÖÜa-zäöü\s]+?)(?:\n|Typ)", text)
    if herst_m:
        result.fahrzeug.hersteller = herst_m.group(1).strip()

    typ_m = re.search(r"Typ\s+([A-Z0-9][\w\s-]+?)(?:\n|Erstzulassung)", text, re.IGNORECASE)
    if typ_m:
        result.fahrzeug.typ = typ_m.group(1).strip()

    ez_m = re.search(r"Erstzulassung\s+(\d{2}\.\d{2}\.\d{4})", text)
    if ez_m:
        result.fahrzeug.erstzulassung = _parse_erstzulassung(ez_m.group(1))

    kz_m = re.search(r"Kennzeichen\s+([A-ZÄÖÜ]{1,3}-[A-Z]{1,2}\s*\d{1,4}[A-Z]?|[A-ZÄÖÜ0-9 -]{4,12})",
                      text, re.IGNORECASE)
    if kz_m:
        result.fahrzeug.kennzeichen = kz_m.group(1).strip()

    # Zusammenfassung Prüfergebnis (Seite 1)
    # "Reparaturkosten gemäß Gutachten o. Kostenvoranschlag (brutto): 3.574,95 €"
    brutto_m = re.search(
        r"Reparaturkosten\s+gemäß\s+Gutachten.*?\(brutto\)\s*:\s*([\d.]+,\d{2})\s*€",
        text, re.IGNORECASE
    )
    if brutto_m:
        result.reparaturkosten_brutto = parse_betrag(brutto_m.group(1))

    # "(netto): 3.004,16 €"
    netto_vor_m = re.search(
        r"Reparaturkosten\s+gemäß\s+Gutachten.*?\(netto\)\s*:\s*([\d.]+,\d{2})\s*€",
        text, re.IGNORECASE
    )
    if netto_vor_m:
        result.reparaturkosten_netto_vor_pruefung = parse_betrag(netto_vor_m.group(1))

    # "Abzug technische Prüfung (netto): 0,00 €" / "-444,85 €"
    tech_m = re.search(
        r"Abzug\s+technische\s+Prüfung\s*\(netto\)\s*:\s*(-?[\d.]+,\d{2})\s*€",
        text, re.IGNORECASE
    )
    if tech_m:
        val = parse_betrag(tech_m.group(1))
        result.abzug_technisch = abs(val) if val else 0.0

    # "Abzug Werkstattalternative / weitere Prüfung (netto): -444,85 €"
    wa_m = re.search(
        r"Abzug\s+Werkstattalternative[^:]*\(netto\)\s*:\s*(-?[\d.]+,\d{2})\s*€",
        text, re.IGNORECASE
    )
    if wa_m:
        val = parse_betrag(wa_m.group(1))
        result.abzug_werkstattalternative = abs(val) if val else 0.0

    # "Abzug gesamt (netto): -444,85 €"
    gesamt_m = re.search(
        r"Abzug\s+gesamt\s*\(netto\)\s*:\s*(-?[\d.]+,\d{2})\s*€",
        text, re.IGNORECASE
    )
    if gesamt_m:
        val = parse_betrag(gesamt_m.group(1))
        result.abzug_gesamt = abs(val) if val else 0.0

    # "Reparaturkosten nach Prüfung (netto): 2.559,31 €"
    nach_m = re.search(
        r"Reparaturkosten\s+nach\s+Prüfung\s*\(netto\)\s*:\s*([\d.]+,\d{2})\s*€",
        text, re.IGNORECASE
    )
    if nach_m:
        result.reparaturkosten_nach_pruefung = parse_betrag(nach_m.group(1))

    # "Abzug NfA / Wertverbesserung: 0,00 €"
    nfa_m = re.search(
        r"Abzug\s+NfA\s*/\s*Wertverbesserung\s*:\s*(-?[\d.]+,\d{2})\s*€",
        text, re.IGNORECASE
    )
    if nfa_m:
        val = parse_betrag(nfa_m.group(1))
        result.abzug_nfa = abs(val) if val else 0.0

    # "Bei fiktiver Abrechnung betragen ... Reparaturkosten ohne Mehrwertsteuer: 2.018,37 EUR"
    fiktiv_m = re.search(
        r"fiktiver\s+Abrechnung\s+betragen.*?Reparaturkosten\s+ohne\s+Mehrwertsteuer\s*:\s*([\d.]+,\d{2})\s*(?:EUR|€)",
        text, re.IGNORECASE | re.DOTALL
    )
    if fiktiv_m and not result.reparaturkosten_nach_pruefung:
        result.reparaturkosten_nach_pruefung = parse_betrag(fiktiv_m.group(1))

    # Tabellen-Format: "Gesamtbetrag X,XX € -Y,XX € -Z,XX € N,XX €"
    # (Allianz-Prüfbericht / allgemeines Format mit 4 Spalten)
    if not result.abzug_gesamt:
        tab_m = re.search(
            r"Gesamtbetrag\s+([\d.]+,\d{2})\s*€?\s+"
            r"(-?[\d.]+,\d{2})\s*€?\s+"
            r"(-?[\d.]+,\d{2})\s*€?\s+"
            r"([\d.]+,\d{2})\s*€?",
            text, re.IGNORECASE
        )
        if tab_m:
            result.reparaturkosten_netto_vor_pruefung = parse_betrag(tab_m.group(1))
            result.abzug_technisch = abs(parse_betrag(tab_m.group(2)) or 0.0)
            result.abzug_werkstattalternative = abs(parse_betrag(tab_m.group(3)) or 0.0)
            result.reparaturkosten_nach_pruefung = parse_betrag(tab_m.group(4))
            result.abzug_gesamt = round((result.abzug_technisch or 0) + (result.abzug_werkstattalternative or 0), 2)

    # Detail-Abzüge aus Prüftext (Seite 3)
    # Pattern: "BEZEICHNUNG (Arbeitslohn): -N Std. / -XXX,XX EUR"
    einzelabzug_re = re.compile(
        r"([A-ZÄÖÜ][A-ZÄÖÜ0-9\s*/-]+?)\s*\(Arbeitslohn\)\s*:\s*"
        r"-?[\d.,]+\s*Std\.\s*/\s*(-[\d.]+,\d{2})\s*(?:EUR)?",
        re.IGNORECASE
    )
    for m in einzelabzug_re.finditer(text):
        bezeichnung = m.group(1).strip()
        val = parse_betrag(m.group(2))
        if val is not None:
            result.abzuege_detail.append(ParsedAbzug(
                kategorie="technisch",
                bezeichnung=bezeichnung,
                betrag=abs(val),
                konfidenz=0.85,
            ))

    # Referenzwerkstatt
    ref_ws = ParsedReferenzwerkstatt()

    # ControlExpert-Block: "Verwendeter Referenzbetrieb\nNAME\nSTRASSE\nPLZ ORT\nTEL\nEntfernung"
    ce_block_m = re.search(
        r"Verwendeter?\s+Referenz(?:betrieb|firma)\s*\n"
        r"([^\n]+)\n"           # Name
        r"([^\n]+)\n"           # Straße
        r"(\d{5}[^\n]+)\n",    # PLZ + Ort
        text, re.IGNORECASE
    )
    if ce_block_m:
        ref_ws.name    = ce_block_m.group(1).strip()
        ref_ws.adresse = ce_block_m.group(2).strip()
        ref_ws.plz_ort = ce_block_m.group(3).strip()
    else:
        # Fallback: nur Name
        ws_name_m = re.search(
            r"(?:Verwendeter?\s+Referenz(?:betrieb|firma)|Referenz-Firma)\s*\n\s*([^\n]+)",
            text, re.IGNORECASE
        )
        if ws_name_m:
            ref_ws.name = ws_name_m.group(1).strip()
        else:
            ws_direct_m = re.search(
                r"(Karosserie-Fachbetrieb\s+\w+|[A-ZÄÖÜ][\w\s&.-]+(?:GmbH|KG|Meisterbetrieb))",
                text
            )
            if ws_direct_m:
                ref_ws.name = ws_direct_m.group(1).strip()

        # Adresse ohne Block: nächste Zeile nach Name suchen
        if ref_ws.name and not ref_ws.adresse:
            adr_m = re.search(
                re.escape(ref_ws.name) + r"\n([^\n]{5,60})\n(\d{5}[^\n]+)",
                text, re.IGNORECASE
            )
            if adr_m:
                ref_ws.adresse = adr_m.group(1).strip()
                ref_ws.plz_ort = adr_m.group(2).strip()

    # Entfernung
    entf_m = re.search(r"Entfernung\s+zum\s+Anspruchsteller\s*:\s*([\d.,]+)\s*km", text, re.IGNORECASE)
    if entf_m:
        ref_ws.entfernung_km = parse_betrag(entf_m.group(1).replace(",", "."))

    # Lohnfaktoren
    for label, attr in [
        (r"Mechanik", "lohn_mechanik"),
        (r"Elektrik", "lohn_elektrik"),
        (r"Karosserie", "lohn_karosserie"),
        (r"Lack\s+inkl\.?\s+Lackmaterial", "lohn_lack"),
    ]:
        m = re.search(label + r"\s+([\d.]+,\d{2})\s*€", text, re.IGNORECASE)
        if m:
            setattr(ref_ws, attr, parse_betrag(m.group(1)))

    if ref_ws.name:
        result.referenzwerkstatt = ref_ws

    return result


def _parse_dekra(text: str, is_image: bool) -> PruefberichtParseResult:
    """Parser für DEKRA-Prüfberichte."""
    result = PruefberichtParseResult(
        pruefdienstleister="DEKRA",
        ist_image_pdf=is_image,
    )

    if is_image:
        result.warnungen.append(
            "DEKRA-Prüfbericht liegt als Bilddatei vor. "
            "Automatische Textextraktion nicht möglich. "
            "Bitte Daten manuell erfassen."
        )
        result.konfidenz = 0.0
        return result

    # DEKRA-spezifische Extraktion (wenn Text vorhanden)
    # Schaden-Nr.
    schaden_m = re.search(r"Schaden[-.]?Nr\.?\s+([\w\s-]+?)(?:\n|Vorgangs)", text)
    if schaden_m:
        result.auftraggeber = "HUK"  # Typischerweise

    # Tabelle: Eingangswert / Techn. Prüfung / Weitere Prüfung / Ausgangswert
    # "Ergebnis (netto v. NfA) 8.052,84 € -306,60 € -548,88 € 7.197,36 €"
    ergebnis_m = re.search(
        r"Ergebnis\s*\(netto\s+v\.\s+NfA\)\s+"
        r"([\d.]+,\d{2})\s*€?\s+"
        r"(-?[\d.]+,\d{2})\s*€?\s+"
        r"(-?[\d.]+,\d{2})\s*€?\s+"
        r"([\d.]+,\d{2})\s*€?",
        text, re.IGNORECASE
    )
    if ergebnis_m:
        result.reparaturkosten_netto_vor_pruefung = parse_betrag(ergebnis_m.group(1))
        result.abzug_technisch = abs(parse_betrag(ergebnis_m.group(2)) or 0)
        result.abzug_werkstattalternative = abs(parse_betrag(ergebnis_m.group(3)) or 0)
        result.reparaturkosten_nach_pruefung = parse_betrag(ergebnis_m.group(4))
        result.abzug_gesamt = (result.abzug_technisch or 0) + (result.abzug_werkstattalternative or 0)

    # Einzelabzüge aus DEKRA "Ergebnis der Prüfung"
    # "AUFNAHMEBLECH H.L. AUSBEULEN  Arbeitslohn  -1 Std.  -160,00 €"
    dekra_abzug_re = re.compile(
        r"([A-ZÄÖÜ*][A-ZÄÖÜ\s*/-]{3,}?)\s+"
        r"(Arbeitslohn|Lackierung|Ersatzteil)\s+"
        r"(-?[\d.]+(?:,\d+)?\s*Std\.)?\s*"
        r"(-[\d.]+,\d{2})\s*€",
        re.IGNORECASE
    )
    for m in dekra_abzug_re.finditer(text):
        bezeichnung = m.group(1).strip()
        art_raw = m.group(2).lower()
        val = parse_betrag(m.group(4))
        if val is not None:
            kategorie = "technisch" if "arbeitslohn" in art_raw else "werkstattalternative"
            result.abzuege_detail.append(ParsedAbzug(
                kategorie=kategorie,
                bezeichnung=bezeichnung,
                betrag=abs(val),
            ))

    # UPE-Abzüge
    upe_m = re.search(r"Summe\s+UPE\s+bedingter?\s+Abzüge\s+Ersatzteil\s+(-[\d.]+,\d{2})\s*€", text, re.IGNORECASE)
    if upe_m:
        val = parse_betrag(upe_m.group(1))
        if val:
            result.abzuege_detail.append(ParsedAbzug(
                kategorie="werkstattalternative",
                bezeichnung="UPE-Abzüge",
                betrag=abs(val),
            ))

    return result


def parse_pruefbericht(text: str, pruefdienstleister: str = "",
                        has_image_pages: bool = False) -> PruefberichtParseResult:
    """
    Hauptfunktion: Parst einen Prüfbericht.
    
    Args:
        text: Normalisierter Volltext
        pruefdienstleister: Vorab erkannter Prüfdienstleister
        has_image_pages: True wenn Seiten als Bilder vorliegen
    
    Returns:
        PruefberichtParseResult
    """
    text_lower = text.lower()

    # Prüfdienstleister bestimmen
    if not pruefdienstleister:
        if re.search(r"control.?expert", text_lower):
            pruefdienstleister = "ControlExpert"
        elif "dekra" in text_lower:
            pruefdienstleister = "DEKRA"

    # DEKRA-Berichte kommen oft als Image-PDF an
    if pruefdienstleister == "DEKRA" and has_image_pages:
        result = _parse_dekra("", is_image=True)
    elif pruefdienstleister == "DEKRA":
        result = _parse_dekra(text, is_image=False)
    elif pruefdienstleister == "ControlExpert":
        result = _parse_controlexpert(text)
    else:
        # Generischer Versuch mit ControlExpert-Logik als Fallback
        result = _parse_controlexpert(text)
        result.pruefdienstleister = pruefdienstleister or "Unbekannt"

    # Konfidenz berechnen
    punkte = 0
    if result.reparaturkosten_nach_pruefung:
        punkte += 3
    if result.abzug_gesamt is not None:
        punkte += 2
    if result.fahrzeug.kennzeichen:
        punkte += 1
    if result.referenzwerkstatt:
        punkte += 1
    if result.abzuege_detail:
        punkte += min(len(result.abzuege_detail), 2)

    result.konfidenz = min(punkte / 9.0, 1.0) if not result.ist_image_pdf else 0.0

    # Plausibilitätsprüfung
    if (result.reparaturkosten_netto_vor_pruefung and
            result.abzug_gesamt and
            result.reparaturkosten_nach_pruefung):
        expected = result.reparaturkosten_netto_vor_pruefung - result.abzug_gesamt
        actual = result.reparaturkosten_nach_pruefung
        if abs(expected - actual) > 1.0:
            result.warnungen.append(
                f"Plausibilitätsfehler: {result.reparaturkosten_netto_vor_pruefung:.2f} "
                f"- {result.abzug_gesamt:.2f} ≠ {actual:.2f} "
                f"(Differenz: {abs(expected - actual):.2f})"
            )

    return result
