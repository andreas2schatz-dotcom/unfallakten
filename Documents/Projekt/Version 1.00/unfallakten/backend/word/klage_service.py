"""
backend/word/klage_service.py
==============================
Generiert die Klageschrift als .docx

Aufbau:
  1. Briefkopf (identisch mit Forderungsschreiben-Vorlage)
  2. Adressat: gegnerische Haftpflichtversicherung
  3. Anträge (dynamisch: Sachschaden, ggf. Schmerzensgeld, RVG-Kosten, Kosten)
  4. Begründung:
     - Einleitung
     - Unfallhergang (aus unfalldetails)
     - Unfallschaden (Tabelle aus ausgewählten Positionen)
     - Rechtliche Würdigung (statischer Baustein, später dynamisch)
     - Vorgerichtliche Kosten (RVG-Tabelle)

Wird aufgerufen von word_service.py mit akte_daten + klage_config.
"""

import io
import json
import logging
import os
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Optional

# PRD-14: Single Source of Truth – Abrechnungsart-Berechnung aus schaden.py
from ..models.schaden import berechne_abrechnungsart

logger = logging.getLogger(__name__)

_MODUL_DIR = os.path.dirname(__file__)
# Klageschrift nutzt dieselbe Vorlage wie Forderungsschreiben
_VORLAGE_FS = Path(_MODUL_DIR) / "forderungsschreiben_vorlage.docx"  # Forderungsschreiben

# ── RVG Tabelle § 13 RVG – Anlage 2 (KostRÄG 2021, gültig ab 01.01.2021) ─────
_RVG_TABELLE = [
    (500,    49.00),
    (1000,   88.50),
    (1500,   127.50),
    (2000,   166.50),
    (3000,   222.00),
    (4000,   277.50),
    (5000,   338.00),   # KostRÄG 2021: war 333,00
    (6000,   390.00),   # KostRÄG 2021: war 388,50  → 390 × 1,3 = 507,00 ✓
    (7000,   442.00),   # KostRÄG 2021: war 444,00
    (8000,   494.00),   # KostRÄG 2021: war 499,50
    (9000,   546.00),   # KostRÄG 2021: war 555,00
    (10000,  598.00),   # KostRÄG 2021: war 610,50
    (13000,  668.00),   # KostRÄG 2021: war 679,50
    (16000,  738.00),   # KostRÄG 2021: war 748,50
    (19000,  808.00),   # KostRÄG 2021: war 817,50
    (22000,  878.00),   # KostRÄG 2021: war 886,50
    (25000,  948.00),   # KostRÄG 2021: war 955,50
    (30000,  1053.00),  # KostRÄG 2021: war 1059,00
    (35000,  1158.00),  # KostRÄG 2021: war 1162,50
    (40000,  1263.00),  # KostRÄG 2021: war 1266,00
    (45000,  1368.00),  # KostRÄG 2021: war 1369,50
    (50000,  1473.00),  # unverändert
]


def _rvg_grundgebuehr(streitwert: float) -> float:
    """Ermittelt die Grundgebühr nach § 13 RVG aus dem Streitwert."""
    for grenze, gebuehr in _RVG_TABELLE:
        if streitwert <= grenze:
            return gebuehr
    # Über 50.000 €: lineare Näherung
    basis = 1473.00
    mehrwert = streitwert - 50000
    basis += (mehrwert // 50000) * 466.50
    return round(basis, 2)


def berechne_rvg(streitwert: float, faktor: float = 1.3) -> dict:
    """
    Berechnet die vorgerichtlichen RVG-Kosten.

    Returns:
        {
          "grundgebuehr":   507.00,
          "faktor":         1.3,
          "gebuehr_netto":  507.00,  # Grundgebühr × Faktor (wenn Faktor=1.3 → direkt)
          "post_pauschale": 20.00,
          "zwischen_netto": 527.00,
          "ust":            100.13,
          "gesamt":         627.13,
        }
    """
    grundgebuehr   = _rvg_grundgebuehr(streitwert)
    gebuehr_netto  = round(grundgebuehr * faktor, 2)
    post_pauschale = min(20.00, round(gebuehr_netto * 0.20, 2))
    zwischen_netto = round(gebuehr_netto + post_pauschale, 2)
    ust            = round(zwischen_netto * 0.19, 2)
    gesamt         = round(zwischen_netto + ust, 2)
    return {
        "grundgebuehr":   grundgebuehr,
        "faktor":         faktor,
        "gebuehr_netto":  gebuehr_netto,
        "post_pauschale": post_pauschale,
        "zwischen_netto": zwischen_netto,
        "ust":            ust,
        "gesamt":         gesamt,
    }


# ── Fahrzeugschaden-Logik (gespiegelt aus Frontend) ──────────────────────────

def berechne_fahrzeugschaden(schaden: dict, vorsteuer: bool = False) -> dict:
    """
    Bestimmt die optimale Abrechnungsart und den Fahrzeugschaden-Betrag.
    PRD-14: Delegiert an berechne_abrechnungsart() in schaden.py –
    Single Source of Truth für die gesamte Anwendung.
    Das Rückgabe-Interface bleibt kompatibel (typ, betrag, label, text).
    """
    b = berechne_abrechnungsart(schaden, vorsteuer=vorsteuer)
    art    = b["abrechnungsart"]
    betrag = b["fahrzeugschaden"]

    def f(key): return float(schaden.get(key) or 0)
    wbw     = f("wiederbeschaffung")
    restwert = f("restwert")
    rep_sv  = f("rep_gutachten_netto") or f("reparaturkosten")
    rep_rn  = f("rep_rechnung_netto")

    if art == "totalschaden":
        return {
            "typ":    "totalschaden",
            "betrag": betrag,
            "label":  f"Wiederbeschaffungswert ({_eur(wbw)} €) abzgl. Restwert ({_eur(restwert)} €)",
            "text":   "Totalschadenabrechnung (Wiederbeschaffungswert abzüglich Restwert)",
        }
    if art == "fiktiv":
        return {
            "typ":    "fiktiv",
            "betrag": betrag,
            "label":  "Schaden nach Gutachten (netto)",
            "text":   "fiktive Abrechnung auf Gutachtenbasis (netto)",
        }
    if art == "konkret":
        ist_130 = b.get("ist_130_fall", False)
        return {
            "typ":    "130" if ist_130 else "konkret",
            "betrag": betrag,
            "label":  "Reparaturkosten laut Rechnung (netto)",
            "text":   ("Reparaturkostenabrechnung im Rahmen der 130%-Grenze"
                       if ist_130
                       else "Abrechnung auf Basis der tatsächlich angefallenen Reparaturkosten"),
        }
    return {"typ": "keine", "betrag": 0, "label": "", "text": ""}


def _eur(betrag: float) -> str:
    """Formatiert als deutsche Währung ohne €-Zeichen: 1.234,56"""
    return f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _eur_str(betrag: float) -> str:
    return f"{_eur(betrag)} €"


# ── OOXML-Bausteine ──────────────────────────────────────────────────────────

def _xml_absatz(text: str, fett: bool = False, einzug: bool = False,
                abstand_nach: int = 0, abstand_vor: int = 0,
                schriftgroesse: int = 24) -> str:
    """Einfacher Absatz in Arial 12pt."""
    b_start = "<w:b/><w:bCs/>" if fett else ""
    ppr = ""
    spacing = ""
    if abstand_nach or abstand_vor:
        spacing = f'<w:spacing w:before="{abstand_vor}" w:after="{abstand_nach}"/>'
    if einzug:
        ppr = f'<w:pPr><w:ind w:left="720"/>{spacing}</w:pPr>'
    elif spacing:
        ppr = f'<w:pPr>{spacing}</w:pPr>'

    return (
        f'<w:p><w:pPr><w:pStyle w:val="Fliesstext"/></w:pPr>'
        f'<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
        f'<w:sz w:val="{schriftgroesse}"/><w:szCs w:val="{schriftgroesse}"/>'
        f'{b_start}</w:rPr><w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'
    )


def _xml_leerzeile() -> str:
    return '<w:p><w:pPr><w:pStyle w:val="Fliesstext"/></w:pPr></w:p>'


def _esc(text: str) -> str:
    """XML-Escaping."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _xml_tabelle_schaden(positionen: list) -> str:
    """
    Baut eine 2-spaltige Schadentabelle:
    Position | Betrag
    """
    # Tabellenbreite: 9163 Twips (wie im Forderungsschreiben)
    W_POS   = 7000
    W_BETR  = 2163

    def zeile(links: str, rechts: str, fett: bool = False) -> str:
        b = "<w:b/><w:bCs/>" if fett else ""
        return (
            f'<w:tr>'
            f'<w:tc><w:tcPr><w:tcW w:w="{W_POS}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
            f'<w:sz w:val="24"/><w:szCs w:val="24"/>{b}</w:rPr>'
            f'<w:t xml:space="preserve">{_esc(links)}</w:t></w:r></w:p></w:tc>'
            f'<w:tc><w:tcPr><w:tcW w:w="{W_BETR}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:jc w:val="right"/></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
            f'<w:sz w:val="24"/><w:szCs w:val="24"/>{b}</w:rPr>'
            f'<w:t xml:space="preserve">{_esc(rechts)}</w:t></w:r></w:p></w:tc>'
            f'</w:tr>'
        )

    reihen = [zeile("Schadenposition", "Betrag", fett=True)]
    gesamt = 0.0
    for pos in positionen:
        betrag = float(pos.get("betrag") or 0)
        gesamt += betrag
        reihen.append(zeile(pos["label"], _eur_str(betrag)))
    reihen.append(zeile("Gesamtschaden", _eur_str(gesamt), fett=True))

    return (
        f'<w:tbl>'
        f'<w:tblPr>'
        f'<w:tblStyle w:val="Tabellenraster"/>'
        f'<w:tblW w:w="9163" w:type="dxa"/>'
        f'<w:tblBorders>'
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        f'<w:left w:val="none"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="AAAAAA"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
        f'</w:tblPr>'
        f'{"".join(reihen)}'
        f'</w:tbl>'
    )


def _xml_tabelle_rvg(rvg: dict) -> str:
    """Baut die RVG-Gebührentabelle."""
    W_POS  = 6500
    W_BETR = 2663

    def zeile(links: str, mitte: str, rechts: str, fett: bool = False) -> str:
        b = "<w:b/><w:bCs/>" if fett else ""
        def zelle(w, text, align="left"):
            al = f'<w:jc w:val="{align}"/>' if align != "left" else ""
            return (
                f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>'
                f'<w:p><w:pPr>{al}</w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
                f'<w:sz w:val="24"/><w:szCs w:val="24"/>{b}</w:rPr>'
                f'<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p></w:tc>'
            )
        return f'<w:tr>{zelle(4000, links)}{zelle(1500, mitte, "center")}{zelle(W_BETR, rechts, "right")}</w:tr>'

    streitwert = rvg.get("streitwert", 0)
    return (
        f'<w:tbl>'
        f'<w:tblPr>'
        f'<w:tblStyle w:val="Tabellenraster"/>'
        f'<w:tblW w:w="9163" w:type="dxa"/>'
        f'<w:tblBorders>'
        f'<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        f'<w:left w:val="none"/>'
        f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="AAAAAA"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
        f'</w:tblPr>'
        + zeile(f"Gegenstandswert: {_eur_str(streitwert)}", "", "", fett=True)
        + zeile("Geschäftsgebühr §§ 13, 14, Nr. 2300 VV RVG",
                str(rvg["faktor"]).replace(".", ","),
                _eur_str(rvg["gebuehr_netto"]))
        + zeile("Zwischensumme der Gebührenpositionen", "",
                _eur_str(rvg["gebuehr_netto"]))
        + zeile("Pauschale für Post und Telekommunikation Nr. 7002 VV RVG", "",
                _eur_str(rvg["post_pauschale"]))
        + zeile("Zwischensumme netto", "", _eur_str(rvg["zwischen_netto"]))
        + zeile("19% Umsatzsteuer", "", _eur_str(rvg["ust"]))
        + zeile("Gesamtbetrag", "", _eur_str(rvg["gesamt"]), fett=True)
        + '</w:tbl>'
    )


# ── Hauptfunktion ─────────────────────────────────────────────────────────────


# ── Aktivlegitimation ─────────────────────────────────────────────────────────

def _get_kl_genus_vars(anrede: str) -> dict:
    """Genus-Variablen aus Anrede ableiten (Python 3.9 kompatibel)."""
    weiblich = (anrede or "").lower() == "frau"
    return {
        "kl_eigen":    "Eigentümerin" if weiblich else "Eigentümer",
        "kl_pron_akk": "sie" if weiblich else "ihn",
    }


def get_aktivlegitimation_text(details: dict, kl_einf: str, anrede: str) -> str:
    """
    Baut den Aktivlegitimations-Absatz für die Klageschrift.
    Gibt leeren String zurück wenn kein Text generiert werden soll (Fall G).

    details: unfalldetails-Dict aus akte_daten
    kl_einf: "Der Kläger" | "Die Klägerin" (bereits gebildet)
    anrede:  Anrede des Mandanten (für Genus-Variablen)

    Fälle:
      A: Eigentum + selbst gefahren
      B: Eigentum + nicht selbst gefahren
      C: Finanziert + Freigabe liegt vor
      D: Finanziert + aus Finanzierungsbedingungen
      E: Geleast + Freigabe liegt vor
      F: Geleast + aus Leasingbedingungen
      G: Ungeklärt → leerer String (Warnung nur im UI)
    """
    typ      = (details.get("aktivlegitimation_typ")      or "eigentum").strip()
    freigabe = (details.get("aktivlegitimation_freigabe") or "freigabe").strip()
    datum    = (details.get("aktivlegitimation_datum")    or "TT.MM.JJJJ").strip()
    mkz      = (details.get("_wdm_mandant_kz")            or "").strip()
    ist_fahrer = bool(details.get("mandant_ist_fahrer"))

    gv = _get_kl_genus_vars(anrede)
    kl_eigen    = gv["kl_eigen"]
    kl_pron_akk = gv["kl_pron_akk"]

    mkz_satz = f" mit dem amtlichen Kennzeichen {mkz}" if mkz else ""

    # ── Fall A + B: Eigentum ──────────────────────────────────────────────────
    if typ == "eigentum":
        text = f"{kl_einf} ist {kl_eigen} des Fahrzeugs{mkz_satz}."
        if ist_fahrer:
            text += (
                f"\nFür {kl_pron_akk} streitet bereits § 1006 BGB, "
                f"da {kl_einf} zum Zeitpunkt des Unfalls das Fahrzeug selbst fuhr."
            )
        return text

    # ── Fall G: Ungeklärt ─────────────────────────────────────────────────────
    if freigabe == "ungeklaert":
        return ""

    # ── Fälle C–F: Finanziert / Geleast ──────────────────────────────────────
    if typ == "finanziert":
        eigentuemer   = "finanzierenden Bank"
        fin_typ       = "Bank"
        bedingungstyp = "Finanzierungsbedingungen"
    else:  # geleast
        eigentuemer   = "Leasinggeberin"
        fin_typ       = "Leasinggeberin"
        bedingungstyp = "Leasingbedingungen"

    basis = (
        f"Das Fahrzeug{mkz_satz} befindet sich im Eigentum der {eigentuemer}. "
        f"{kl_einf} ist jedoch aufgrund "
    )

    if freigabe == "freigabe":
        # Fall C / E
        text = (
            basis
            + f"der vorliegenden Freigabeerklärung der {fin_typ} aktivlegitimiert, "
            + "den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen."
            + f"\n\nBEWEIS:\tFreigabeerklärung vom {datum}, Anlage K1\n"
        )
    else:
        # Fall D / F (bedingungen)
        text = (
            basis
            + f"der {bedingungstyp} aktivlegitimiert, "
            + "den Schaden im eigenen Namen und auf eigene Rechnung geltend zu machen."
            + f"\n\nBEWEIS:\t{bedingungstyp} in Kopie, Anlage K1\n"
        )

    return text


# ── Vorlage ───────────────────────────────────────────────────────────────────
_VORLAGE = Path(__file__).parent / "klagevorlage.docx"


def _render_docx(vorlage: Path, replacements: dict, ooxml_blocks: dict) -> bytes:
    """
    Öffnet DOCX-Vorlage, ersetzt einfache Platzhalter (String) und
    OOXML-Blöcke (ganzen <w:p>-Absatz), gibt DOCX-Bytes zurück.
    Identisch zum Forderungsschreiben-System.
    """
    import zipfile as _zf, re as _re, io as _io
    with open(vorlage, "rb") as f:
        vb = f.read()

    output = _io.BytesIO()
    with _zf.ZipFile(_io.BytesIO(vb), "r") as zin,          _zf.ZipFile(output, "w", _zf.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                # Gesplittete Platzhalter zusammenführen
                xml = _merge_split_placeholders(xml, list(replacements.keys()))
                # Einfache String-Ersetzung
                for key, value in replacements.items():
                    xml = xml.replace(key, value)
                # OOXML-Blöcke: ganzer Absatz wird ersetzt
                for ph, block in ooxml_blocks.items():
                    xml = _inject_block(xml, ph, block)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    return output.getvalue()


def _inject_block(xml: str, placeholder: str, block_xml: str) -> str:
    """Ersetzt den gesamten <w:p>-Absatz der den Platzhalter enthält."""
    import re as _re
    ph_esc = _re.escape(placeholder)
    return _re.sub(
        r'<w:p[ >](?:(?!</w:p>).)*' + ph_esc + r'(?:(?!</w:p>).)*</w:p>',
        block_xml,
        xml,
        flags=_re.DOTALL,
    )


def _merge_split_placeholders(xml: str, placeholders: list) -> str:
    """
    Word zersplittert Platzhalter manchmal über mehrere <w:r>-Runs.
    Fügt Textinhalt benachbarter Runs zusammen wenn ein Platzhalter
    dadurch vollständig wird.
    """
    import re as _re
    for ph in placeholders:
        if ph in xml:
            continue
        def _fix_para(m):
            para = m.group(0)
            if '<w:drawing>' in para or '<w:pict>' in para:
                return para
            texte  = _re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para)
            gesamt = "".join(texte)
            if ph not in gesamt:
                return para
            count = [0]
            def _ersetze_t(tm):
                count[0] += 1
                if count[0] == 1:
                    return f'<w:t xml:space="preserve">{gesamt}</w:t>'
                return '<w:t></w:t>'
            return _re.sub(r'<w:t[^>]*>[^<]*</w:t>', _ersetze_t, para)
        xml = _re.sub(r'<w:p[ >](?:(?!</w:p>).)*</w:p>', _fix_para, xml, flags=_re.DOTALL)
    return xml


def _p(text: str, fett: bool = False, center: bool = False,
       einzug: bool = False, size: int = 24) -> str:
    """Einfacher Absatz in Arial."""
    jc  = '<w:jc w:val="center"/>' if center else '<w:jc w:val="both"/>' 
    ind = '<w:ind w:left="720"/>' if einzug else ""
    ppr = f'<w:pPr>{jc}{ind}</w:pPr>'
    b   = '<w:b/><w:bCs/>' if fett else ""
    sz  = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' 
    rpr = f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>{b}{sz}</w:rPr>'
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'


def _lz() -> str:
    return '<w:p><w:pPr><w:jc w:val="both"/></w:pPr></w:p>'


def _p_rechts(text: str, fett: bool = True) -> str:
    """Rechtsbündiger Absatz – passend zum Template-Format von {{DATUM}} und {{AKTENZEICHEN}}."""
    b   = '<w:b/><w:bCs/>' if fett else ''
    rf  = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
    sz  = '<w:sz w:val="24"/><w:szCs w:val="24"/>'
    rpr = f'<w:rPr>{rf}{b}{sz}</w:rPr>'
    return (
        f'<w:p>'
        f'<w:pPr><w:jc w:val="right"/><w:rPr>{rf}{b}</w:rPr></w:pPr>'
        f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'
        f'</w:p>'
    )


def _beweis(inhalt):
    # type: (str) -> str
    """BEWEIS: (fett) + Tab + Inhalt (normal) in einer Zeile."""
    sz = '<w:sz w:val="24"/><w:szCs w:val="24"/>'
    rf = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
    return (
        '<w:p><w:pPr><w:tabs><w:tab w:val="left" w:pos="1701"/></w:tabs></w:pPr>'
        f'<w:r><w:rPr>{rf}<w:b/><w:bCs/>{sz}</w:rPr>'
        '<w:t xml:space="preserve">BEWEIS:</w:t></w:r>'
        f'<w:r><w:rPr>{rf}{sz}</w:rPr><w:tab/></w:r>'
        f'<w:r><w:rPr>{rf}{sz}</w:rPr>'
        f'<w:t xml:space="preserve">{_esc(inhalt)}</w:t></w:r></w:p>'
    )



def _funktion_aus_rechtsform_str(firmenname: str) -> str:
    """Gibt die korrekte Funktion (Geschäftsführer/Vorstand) für eine Rechtsform zurück."""
    n = (firmenname or "").upper()
    if any(x in n for x in ("GMBH", " KG", "OHG", "GBR", "UG")):
        return "Geschäftsführer"
    if any(x in n for x in (" AG", " SE", "KGAA")):
        return "Vorstand"
    return "gesetzlichen Vertreter"


def _vertretungs_hinweis(firmenname: str) -> str:
    """
    Bestimmt den Vertretungshinweis je nach Rechtsform.
    GmbH / GbR / KG / OHG → Geschäftsführer
    AG / SE / KGaA         → Vorstand
    Sonstige Firma         → gesetzlichen Vertreter
    """
    n = (firmenname or "").upper()
    if any(x in n for x in ("GMBH", "GBR", " KG", "OHG", "GMBH & CO")):
        return "– vertreten durch den/die Geschäftsführer –"
    if any(x in n for x in (" AG", "SE ", " SE,", " KGA", "KGAA")):
        return "– vertreten durch den Vorstand –"
    return "– vertreten durch den gesetzlichen Vertreter –"

def _build_aktivlegitimation_xml(details: dict, kl_einf: str, anrede: str) -> str:
    """
    Wandelt get_aktivlegitimation_text() in OOXML um.
    Behandelt den BEWEIS-Block separat mit _beweis()-Helper.
    Gibt leeren String zurück wenn kein Text (Fall G).
    """
    text_override = details.get("aktivlegitimation_text_override")
    raw = text_override if text_override else get_aktivlegitimation_text(details, kl_einf, anrede)
    if not raw:
        return ""

    # BEWEIS-Block aufteilen: Text vor "\n\nBEWEIS:\t..." und der BEWEIS-Teil
    if "\n\nBEWEIS:\t" in raw:
        teile        = raw.split("\n\nBEWEIS:\t", 1)
        haupt_text   = teile[0].strip()
        beweis_inhalt = teile[1].rstrip("\n")
    else:
        haupt_text   = raw.strip()
        beweis_inhalt = None

    xml = ""
    # Haupttext: kann mehrzeilig sein (z.B. § 1006 BGB als zweiter Satz)
    for zeile in haupt_text.split("\n"):
        z = zeile.strip()
        if z:
            xml += _p(z)

    if beweis_inhalt:
        xml += _lz()
        xml += _beweis(beweis_inhalt)
        xml += _lz()

    return xml


def generiere_klageschrift(akte_daten: dict) -> bytes:
    """
    Generiert die Klageschrift als DOCX-Bytes.
    Nutzt klagevorlage.docx mit sauberen Platzhaltern –
    identisches System wie forderungsschreiben_wv.py.
    """
    if not _VORLAGE.exists():
        raise FileNotFoundError(
            f"Klagevorlage fehlt: {_VORLAGE}. "
            "Bitte klagevorlage.docx in backend/word/ ablegen."
        )

    akte         = akte_daten.get("akte") or {}
    mandant      = akte_daten.get("mandant") or {}
    kanzlei      = akte_daten.get("kanzlei") or {}
    details      = akte_daten.get("unfalldetails") or {}
    cfg          = akte_daten.get("klage_config") or {}
    abrechnungen = akte_daten.get("abrechnungen") or []

    # ── Beklagte / GHPV ──────────────────────────────────────────────────────
    beklagte_liste = cfg.get("beklagte") or []
    # Erste beklagte = GHPV
    ghpv          = next((b for b in beklagte_liste
                          if (b.get("rolle_klage","") or b.get("rolle","")) != "klaeger"), {})
    ghpv_name     = ghpv.get("versicherung") or ghpv.get("firma") or ghpv.get("name") or "KEINE HPV ERFASST"
    ghpv_anschrift= ghpv.get("anschrift") or ""
    ghpv_plz_ort  = " ".join(filter(None, [ghpv.get("plz"), ghpv.get("ort")])) or ""
    schadennummer = ghpv.get("schaden_nr") or details.get("_wdm_schadennummer") or ""

    # ── Gericht ──────────────────────────────────────────────────────────────
    gericht       = cfg.get("gericht") or {}
    gericht_name  = gericht.get("name")    or "AN DAS ZUSTÄNDIGE GERICHT"
    gericht_str   = gericht.get("strasse") or ""
    gericht_plzort= " ".join(filter(None, [gericht.get("plz"), gericht.get("ort")])) or ""

    # ── Aktenzeichen / Datum / Unfall ─────────────────────────────────────────
    az        = akte.get("aktenzeichen") or akte.get("az") or ""
    heute     = date.today().strftime("%d.%m.%Y")
    _ud       = akte_daten.get("unfalldetails") or {}
    # Unfalldatum: akte (ISO) → WDM varU-TAG (DD.MM.YY oder DD.MM.YYYY)
    unfalltag = (
        _fmt_datum(akte.get("unfalldatum") or "")
        or _fmt_datum(_ud.get("_wdm_u_tag") or "")
    )
    # Unfallort: akte → WDM varU-ORT
    unfallort = (
        (akte.get("unfallort") or "").strip()
        or (_ud.get("_wdm_u_ort") or "").strip()
    )

    # ── Mandant / Grammatik ───────────────────────────────────────────────────
    mandant_name    = " ".join(filter(None, [mandant.get("vorname"), mandant.get("name")]))                       or mandant.get("firma") or "KLÄGER"
    mandant_anschr  = mandant.get("anschrift") or ""
    mandant_plz_ort = " ".join(filter(None, [mandant.get("plz"), mandant.get("ort")])) or ""
    anrede_m        = (mandant.get("anrede") or "").lower()
    vorsteuer       = (mandant.get("vorsteuer") or "N").upper() in ("J", "JA", "Y", "1")

    klaeger_liste    = [b for b in beklagte_liste
                        if (b.get("rolle_klage") or b.get("rolle") or "") in ("klaeger", "mandant")]
    mehrere_klaeger  = len(klaeger_liste) > 1

    if mehrere_klaeger:
        kl_art  = "der"; kl_bez = "Kläger"; kl_nom = "Die Kläger"; kl_dat = "die Kläger"
        kl_einf = "Kläger"
        nicht_vst = "nicht vorsteuerabzugsberechtigten"
    elif anrede_m in ("herr", "herrn"):
        kl_art  = "des"; kl_bez = "Klägers"; kl_nom = "Der Kläger"; kl_dat = "den Kläger"
        kl_einf = "Kläger"
        nicht_vst = "nicht vorsteuerabzugsberechtigter" if not vorsteuer else "vorsteuerabzugsberechtigter"
    elif anrede_m == "frau":
        kl_art  = "der"; kl_bez = "Klägerin"; kl_nom = "Die Klägerin"; kl_dat = "die Klägerin"
        kl_einf = "Klägerin"
        nicht_vst = "nicht vorsteuerabzugsberechtigte" if not vorsteuer else "vorsteuerabzugsberechtigte"
    else:
        kl_art  = "des"; kl_bez = "Klägers"; kl_nom = "Der Kläger"; kl_dat = "den Kläger"
        kl_einf = "Kläger"
        nicht_vst = "nicht vorsteuerabzugsberechtigter" if not vorsteuer else "vorsteuerabzugsberechtigter"

    # ── Positionen / Gegenstandswert ─────────────────────────────────────────
    positionen = [p for p in (cfg.get("positionen") or [])
                  if isinstance(p, dict) and p.get("checked")]
    klagebetrag = sum(float(p.get("betrag") or 0) for p in positionen)

    # ── RVG ──────────────────────────────────────────────────────────────────
    rvg_override = cfg.get("rvg_override")
    rvg          = cfg.get("rvg") or berechne_rvg(klagebetrag)
    if rvg_override is not None:
        rvg["gesamt"] = float(rvg_override)

    # ── Zinsen ───────────────────────────────────────────────────────────────
    zinsen_ab     = cfg.get("zinsen_ab") or "verzug"
    verzugsdatum  = cfg.get("verzugsdatum") or ""
    zins_sachsch  = f"dem {verzugsdatum}" if zinsen_ab == "verzug" and verzugsdatum else "Rechtshängigkeit"
    zins_rvg      = "Rechtshängigkeit"

    # ── Schmerzensgeld ───────────────────────────────────────────────────────
    mit_sg  = bool(cfg.get("mit_schmerzensgeld"))
    sg_mind = float(cfg.get("schmerzensgeld_mindest") or 0)

    # ── Gegner-Kennzeichen ───────────────────────────────────────────────────
    gegner_kz = (
        next((b["kfz_kennzeichen"] for b in beklagte_liste if b.get("kfz_kennzeichen")), "")
        or details.get("_wdm_gegner_kz") or ""
    )

    # ── Haftungsquote ────────────────────────────────────────────────────────
    hq = float(details.get("haftungsquote") or akte.get("haftungsquote") or 100)

    # ════════════════════════════════════════════════════════════════════════
    # EINFACHE PLATZHALTER
    # ════════════════════════════════════════════════════════════════════════
    kanzlei_str = kanzlei.get("name") or "Koch, Schatz & Kollegen"
    
    def _tab_rechts(text: str, fett: bool = True) -> str:
        """Absatz mit Tab-Stop bei 8364 (rechts unter Sidebar, wie im Original)."""
        b = "<w:b/><w:bCs/>" if fett else ""
        rpr = f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>{b}</w:rPr>'
        return (
            f'<w:p><w:pPr>'
            f'<w:tabs><w:tab w:val="center" w:pos="8364"/></w:tabs>'
            f'<w:ind w:right="-1136"/>'
            f'{rpr}</w:pPr>'
            f'<w:r>{rpr}<w:tab/></w:r>'
            f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'
            f'</w:p>'
        )

    replacements = {
        "{{GEGENSTANDSWERT}}": _esc(_eur_str(klagebetrag + (sg_mind if mit_sg else 0))),
    }
    # AZ und Datum als OOXML-Block (K-01: einfach rechtsbündig, passend zum Template)
    az_xml    = _p_rechts(az)
    datum_xml = _p_rechts(heute)

    # ════════════════════════════════════════════════════════════════════════
    # OOXML-BLÖCKE
    # ════════════════════════════════════════════════════════════════════════

    # ── {{GERICHT_ADRESSE}} ───────────────────────────────────────────────
    gericht_adresse_xml = "".join(
        _p(z) for z in [gericht_name, gericht_str, gericht_plzort] if z
    )

    # ── Hilfsfunktion: Rubrum-Zeile (Name+Anschrift in einer Zeile) ──────
    def _rubrum_zeile(name: str, anschr: str, plz_ort: str) -> str:
        """Name und Anschrift in einer Zeile, kommagetrennt."""
        teile = [t for t in [name, anschr, plz_ort] if t]
        return _p(", ".join(teile))

    def _rolle_rechts(text: str) -> str:
        """Rollenbezeichnung rechtsbündig via Tab-Stop (wie in Word-Vorlage)."""
        rpr = ('<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
               '<w:i/><w:iCs/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>')
        return (
            f'<w:p><w:pPr>'
            f'<w:tabs><w:tab w:val="right" w:pos="9163"/></w:tabs>'
            f'<w:jc w:val="both"/></w:pPr>'
            f'<w:r>{rpr}<w:tab/></w:r>'
            f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'
            f'</w:p>'
        )

    # ── {{KLAEGER_BLOCK}} ─────────────────────────────────────────────────
    klaeger_xml = ""
    klaeger_objs = [b for b in beklagte_liste
                    if (b.get("rolle_klage") or b.get("rolle") or "") in ("klaeger", "mandant")]
    for i, kl in enumerate(klaeger_objs):
        kl_name    = " ".join(filter(None, [kl.get("vorname"), kl.get("name")])) or kl.get("firma") or "KLÄGER"
        kl_anschr  = kl.get("anschrift") or ""
        kl_plz_ort = " ".join(filter(None, [kl.get("plz"), kl.get("ort")])) or ""
        # Rollenbezeichnung mit Nummer wenn mehrere Kläger
        kl_anrede  = (kl.get("anrede") or "").lower()
        if mehrere_klaeger:
            nr = i + 1
            if kl_anrede in ("frau",):
                rolle_bez = f"Klägerin zu {nr})"
            else:
                rolle_bez = f"Kläger zu {nr})"
        else:
            rolle_bez = "Klägerin" if kl_anrede in ("frau",) else "Kläger"
        # Firma? Vertretung ergänzen
        ist_firma = bool(kl.get("firma")) and not kl.get("vorname")
        klaeger_xml += _rubrum_zeile(kl_name, kl_anschr, kl_plz_ort)
        if ist_firma:
            klaeger_xml += _p(_vertretungs_hinweis(kl_name), einzug=True)
        klaeger_xml += _rolle_rechts(f"– {rolle_bez} –")
        if i < len(klaeger_objs) - 1:
            klaeger_xml += _lz()

    # Prozessbevollmächtigte-Block unter Kläger
    kanzlei_name   = kanzlei.get("name")    or "Koch, Schatz & Kollegen"
    kanzlei_str_rb = kanzlei.get("strasse") or "Tulpenhofstr. 1"
    kanzlei_ort_rb = kanzlei.get("ort")     or "63067 Offenbach"
    klaeger_xml += _lz()
    klaeger_xml += _p(f"Prozessbevollmächtigte: {kanzlei_name}, {kanzlei_str_rb}, {kanzlei_ort_rb}")
    klaeger_xml += _lz()

    # ── {{HPV_BLOCK}} ─────────────────────────────────────────────────────
    hpv_xml = ""
    beklagte_gef = [b for b in beklagte_liste
                    if (b.get("rolle_klage") or b.get("rolle") or "") not in ("klaeger", "mandant")
                    and b.get("checked", True)]
    for i, bek in enumerate(beklagte_gef):
        bek_name    = bek.get("versicherung") or bek.get("firma") or \
                      " ".join(filter(None, [bek.get("vorname"), bek.get("name")])) or "BEKLAGTE"
        bek_anschr  = bek.get("anschrift") or ""
        bek_plz_ort = " ".join(filter(None, [bek.get("plz"), bek.get("ort")])) or ""
        ist_firma   = bool(bek.get("firma") or bek.get("versicherung"))
        nr_suffix   = f" zu {i+1})" if len(beklagte_gef) > 1 else ""
        # Vertreter aus DB (gespeichert via Klage-Tab Lookup)
        vertreter_name = (bek.get("vertreter_name") or "").strip()
        vertreter_funk = (bek.get("vertreter_funktion") or "").strip()

        # Vertreter-Suffix: ", vertreten durch Geschäftsführer Herrn Max Mustermann"
        if ist_firma and vertreter_name:
            funk_label = vertreter_funk or _funktion_aus_rechtsform_str(bek_name)
            # Anrede bestimmen (Herr/Frau aus Funktion-Label oder Vornamen heuristisch)
            anrede_v = "Frau" if any(x in vertreter_funk.lower() for x in ("in ", "rin", "frau")) else "Herrn"
            vertreter_suffix = f", vertreten durch den {funk_label} {anrede_v} {vertreter_name}"
        elif ist_firma:
            # Generischer Hinweis ohne konkreten Namen
            funk_label = _funktion_aus_rechtsform_str(bek_name)
            vertreter_suffix = f", vertreten durch den {funk_label}"
        else:
            vertreter_suffix = ""

        # Adresszeile + Vertreter in einer Zeile
        adress_teile = [t for t in [bek_name, bek_anschr, bek_plz_ort] if t]
        full_line = ", ".join(adress_teile) + vertreter_suffix
        hpv_xml += _p(full_line)
        hpv_xml += _rolle_rechts(f"– Beklagte{nr_suffix} –")
        if i < len(beklagte_gef) - 1:
            hpv_xml += _lz()

    # ── {{ANTRAEGE}} ──────────────────────────────────────────────────────
    antrag_nr = [1]
    def antrag(text, fett=True):
        nr = antrag_nr[0]; antrag_nr[0] += 1
        return (
            f'<w:p><w:pPr><w:jc w:val="both"/><w:ind w:left="720" w:hanging="360"/></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
            f'{"<w:b/><w:bCs/>" if fett else ""}'
            f'<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
            f'<w:t xml:space="preserve">{nr}.\t{_esc(text)}</w:t></w:r></w:p>'
        )

    vollmacht_text = ("der Kläger" if mehrere_klaeger
                      else ("des Klägers" if kl_bez == "Klägers" else "der Klägerin"))
    antraege_xml  = _p(f"Namens und in Vollmacht {vollmacht_text} erheben wir Klage, "
                       "bitten um Anordnung des schriftlichen Vorverfahrens "
                       "und werden beantragen:")
    antraege_xml += _lz()
    antraege_xml += antrag(
        f"Die Beklagte wird verurteilt, an {kl_dat} {_eur_str(klagebetrag)} "
        f"nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz "
        f"seit {zins_sachsch} zu zahlen."
    )
    antraege_xml += _lz()
    if mit_sg:
        if sg_mind > 0:
            antraege_xml += antrag(
                f"Die Beklagte wird verurteilt, an {kl_dat} ein angemessenes, "
                f"vom Gericht festzulegendes Schmerzensgeld zu zahlen, "
                f"wobei die Höhe nicht weniger als {_eur_str(sg_mind)} betragen sollte, "
                f"nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz seit Rechtshängigkeit."
            )
        else:
            antraege_xml += antrag(
                f"Die Beklagte wird verurteilt, an {kl_dat} ein angemessenes, "
                f"vom Gericht nach billigem Ermessen festzulegendes Schmerzensgeld zu zahlen, "
                f"nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz seit Rechtshängigkeit."
            )
        antraege_xml += _lz()
    antraege_xml += antrag(
        f"Die Beklagte wird verurteilt, an {kl_dat} weitere {_eur_str(rvg['gesamt'])} "
        f"nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz "
        f"seit {zins_rvg} zu zahlen."
    )
    antraege_xml += _lz()
    antraege_xml += antrag("Die Beklagte trägt die Kosten des Rechtsstreits.", fett=False)
    antraege_xml += _lz()
    antraege_xml += _p("Für den Fall der Anordnung des schriftlichen Vorverfahrens bitten wir, "
                       "für den Fall der Nichteinlassung der Beklagten:")
    antraege_xml += _lz()
    antraege_xml += _p("Versäumnisurteil", fett=True, center=True)
    antraege_xml += _lz()
    antraege_xml += _p("ohne mündliche Verhandlung zu erlassen.")

    # ── {{EINLEITUNG}} ────────────────────────────────────────────────────
    einleitung_xml  = _lz() + _p("1.) Sachverhalt", fett=True)
    einleitung_xml += _lz()
    einleitung_xml += _p(
        f"{kl_nom} macht als {nicht_vst} {kl_einf} Schadensersatzforderungen "
        f"aus einem Verkehrsunfall vom {unfalltag} in {unfallort} geltend."
        if unfalltag else
        f"{kl_nom} macht Schadensersatzforderungen aus einem Verkehrsunfall "
        f"in {unfallort} geltend."
    )
    beklagte_satz = (
        f"Die Beklagte ist die Haftpflichtversicherung des unfallverursachenden "
        f"Fahrzeugs mit dem amtlichen Kennzeichen {gegner_kz}."
        if gegner_kz else
        "Die Beklagte ist die Haftpflichtversicherung des unfallverursachenden Fahrzeugs."
    )
    if schadennummer:
        beklagte_satz += f" Sie führt den Vorgang unter der Schadennummer {schadennummer}."
    einleitung_xml += _p(beklagte_satz)

    # K-04: Aktivlegitimation + Mandant-Kennzeichen
    mandant_kz = (details.get("_wdm_mandant_kz") or
                  mandant.get("kfz_kennzeichen") or "").strip()
    eigentuemer = "Eigentümerin" if anrede_m == "frau" else "Eigentümer"
    if mandant_kz:
        einleitung_xml += _p(
            f"{kl_nom} ist {eigentuemer} des bei dem Unfall beschädigten "
            f"Fahrzeugs mit dem amtlichen Kennzeichen {mandant_kz}."
        )
    else:
        einleitung_xml += _p(
            f"{kl_nom} ist {eigentuemer} des bei dem Unfall beschädigten Fahrzeugs."
        )

    # ── {{UNFALLHERGANG}} ─────────────────────────────────────────────────
    schilderung = details.get("schilderung") or ""
    zeugen = [
        f"{details.get(f'zeuge_{i}')}, {details.get(f'zeuge_{i}_anschrift') or 'n.n.'}"
        for i in (1, 2, 3) if details.get(f"zeuge_{i}")
    ]
    ea_az  = details.get("ermittlungsakte_az") or ""
    ea_beh = details.get("ermittlungsakte_behoerde") or ""

    unfall_xml  = _lz() + _p("2.) Unfallhergang", fett=True)
    unfall_xml += _lz()
    if schilderung:
        unfall_xml += _p(schilderung)
    else:
        unfall_xml += _p("[Unfallschilderung – bitte aus RA-Micro WDM laden]")
    unfall_xml += _lz()
    unfall_xml += _beweis(f"Parteivernahme, hilfsweise informatorische Anhörung "
                          f"{kl_art} {kl_bez}.")
    for z in zeugen:
        unfall_xml += _p(f"Zeugnis: {z}", einzug=True)
    unfall_xml += _p("Unfallrekonstruktionsgutachten", einzug=True)
    if ea_az and ea_beh:
        unfall_xml += _p(f"Beiziehung der Ermittlungsakte {ea_az} bei der {ea_beh}", einzug=True)
    elif ea_az:
        unfall_xml += _p(f"Beiziehung der Ermittlungsakte {ea_az}", einzug=True)

    # ── {{SCHADEN}} ───────────────────────────────────────────────────────
    # Schadentabelle: exakt dieselbe Funktion wie Forderungsschreiben
    schaden_raw = dict(akte_daten.get("schaden") or {})
    # Nebenkosten aus positionen ergänzen falls nicht in schaden_raw
    _pos_key_map = {
        "sv_kosten": "sv_kosten", "wertminderung": "wertminderung",
        "nutzungsausfall": "nutzungsausfall", "mietwagenkosten": "mietwagenkosten",
        "abschleppkosten": "abschleppkosten", "standkosten": "standkosten",
        "anabmeldekosten": "anabmeldekosten", "unkostenpauschale": "unkostenpauschale",
    }
    for p in positionen:
        k = _pos_key_map.get(p.get("key",""))
        if k and p.get("betrag"):
            schaden_raw.setdefault(k, p["betrag"])
    try:
        from .forderungsschreiben_wv import _baue_tabelle as _bt
        tabelle_xml, _ = _bt(
            schaden_raw,
            einleitung="Der entstandene Schaden berechnet sich wie folgt:",
            vorsteuer=vorsteuer
        )
    except Exception as _e:
        logger.warning("_baue_tabelle Fehler: %s", _e)
        tabelle_xml = "".join(
            _p(f"{p.get('label','')}: {_eur_str(p.get('betrag',0))}", einzug=True)
            for p in positionen if p.get("betrag")
        )
        tabelle_xml += _p(f"Gesamt: {_eur_str(klagebetrag)}", fett=True)


    schaden_xml  = _lz() + _p("2.) Unfallschaden", fett=True)
    schaden_xml += _lz()
    schaden_xml += _p("Durch den Unfall ist ein Schaden entstanden, der sich wie folgt zusammensetzt:")
    schaden_xml += tabelle_xml
    schaden_xml += _lz()
    schaden_xml += _beweis("Schadengutachten (Anlage K 1)")
    schaden_xml += _lz()
    schaden_xml += _p("Einholung eines gerichtlichen Sachverständigengutachtens.", fett=True)

    # ── {{RECHTLICHE_WUERDIGUNG}} ─────────────────────────────────────────
    rw_text_override = (details.get("rw_text_override") or "").strip()
    if rw_text_override:
        rw_xml = _lz() + _p("3.) Rechtliche Würdigung", fett=True)
        rw_xml += _lz()
        for _line in rw_text_override.split("\n"):
            _line = _line.strip()
            if _line:
                rw_xml += _p(_line)
    else:
        haftungsbegruendung = details.get("haftungsbegruendung") or ""
        gesamt_reguliert    = sum(float(a.get("gesamt_reguliert") or 0) for a in abrechnungen)

        if gesamt_reguliert > 0:
            regulierung_satz = (
                f"Die Beklagte hat eine Teilregulierung in Höhe von {_eur_str(gesamt_reguliert)} "
                f"vorgenommen. Die verbleibenden Kürzungen sind nicht gerechtfertigt, "
                f"sodass die Klage in Höhe des offenen Restbetrages erhoben wird."
            )
        else:
            regulierung_satz = (
                "Die Beklagte hat bislang keine Regulierung vorgenommen. "
                "Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig."
            )

        rw_xml  = _lz() + _p("3.) Rechtliche Würdigung", fett=True)
        rw_xml += _lz()
        rw_xml += _p(f"Der bei der Beklagten versicherte Unfallgegner verursachte den Unfall "
                     f"durch {haftungsbegruendung or 'sein schuldhaftes Verhalten'}. "
                     f"Die Haftungsquote beträgt {int(hq)} %.")
        rw_xml += _p(regulierung_satz)
        if hq < 100:
            rw_xml += _p(f"Die Mithaftungsquote des {kl_dat} beträgt {int(100-hq)} %. "
                         f"Die Klageforderung wurde entsprechend gekürzt.")

    # ── {{SCHMERZENSGELD}} ────────────────────────────────────────────────
    if mit_sg:
        sg_xml  = _p("4.) Schmerzensgeld", fett=True)
        sg_xml += _lz()
        if sg_mind > 0:
            sg_xml += _p(f"{kl_nom} hat durch den Unfall Verletzungen erlitten, "
                         f"die ein Schmerzensgeld von mindestens {_eur_str(sg_mind)} rechtfertigen.")
        else:
            sg_xml += _p(f"{kl_nom} hat durch den Unfall Verletzungen erlitten, "
                         f"die ein angemessenes Schmerzensgeld rechtfertigen.")
        sg_xml += _p("BEWEIS: Ärztliche Atteste und Befundberichte (Anlage K 2)", einzug=True)
    else:
        sg_xml = ""   # leer → Platzhalter verschwindet

    # ── {{VERZUG}} ────────────────────────────────────────────────────────
    verzug_text_override = (details.get("verzug_text_override") or "").strip()
    if verzug_text_override:
        verzug_xml = ""
        for _line in verzug_text_override.split("\n"):
            _line = _line.strip()
            if _line:
                verzug_xml += _p(_line)
        verzug_xml += _lz()
    else:
        verzug_xml = _p(f"Verzug ist spätestens am {verzugsdatum} eingetreten."
                        if verzugsdatum else
                        "Verzug ist mit Rechtshängigkeit eingetreten.")
        if verzugsdatum:
            verzug_xml += _beweis(f"Schreiben vom {verzugsdatum} in Kopie, Anlage K 3")
        verzug_xml += _lz()

    # ── {{VORGERICHTLICHE_KOSTEN}} ────────────────────────────────────────
    # K-14: RVG als saubere 2-Spalten-Tabelle (wie Schadentabelle)
    def _rvg_tbl_zeile(label, betrag_str, fett=False):
        b = "<w:b/><w:bCs/>" if fett else ""
        rpr = f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>{b}<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
        return (
            f'<w:tr>'
            f'<w:tc><w:tcPr><w:tcW w:w="7000" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(label)}</w:t></w:r></w:p></w:tc>'
            f'<w:tc><w:tcPr><w:tcW w:w="2163" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="right"/></w:pPr>'
            f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(betrag_str)}</w:t></w:r></w:p></w:tc>'
            f'</w:tr>'
        )

    rvg_tabelle = (
        '<w:tbl><w:tblPr><w:tblW w:w="9163" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="2" w:space="0" w:color="CCCCCC"/>'
        '</w:tblBorders></w:tblPr>'
        + _rvg_tbl_zeile(f"Gegenstandswert:", _eur_str(klagebetrag), fett=True)
        + _rvg_tbl_zeile(f"Geschäftsgebühr §§ 13, 14, Nr. 2300 VV RVG ({rvg.get('faktor',1.3)}):",
                         _eur_str(rvg.get("gebuehr_netto", 0)))
        + _rvg_tbl_zeile("Post u. Telekommunikation Nr. 7002 VV RVG:",
                         _eur_str(rvg.get("post_pauschale", 0)))
        + _rvg_tbl_zeile("Zwischensumme netto:", _eur_str(rvg.get("zwischen_netto", 0)), fett=True)
        + _rvg_tbl_zeile("19 % Umsatzsteuer:", _eur_str(rvg.get("ust", 0)))
        + _rvg_tbl_zeile("Gesamtbetrag:", _eur_str(rvg.get("gesamt", 0)), fett=True)
        + '</w:tbl>'
    )

    vk_xml  = _lz() + _p("4.) Vorgerichtliche Rechtsanwaltsgebühren", fett=True)
    vk_xml += _lz()
    vk_xml += _p(f"Der Klageantrag ergibt sich aus den vorgerichtlich entstandenen "
                 f"Rechtsanwaltskosten. Aus einem Gegenstandswert von "
                 f"{_eur_str(klagebetrag)} ergibt sich:")
    vk_xml += rvg_tabelle

    # ── {{SCHLUSSFORMEL}} ─────────────────────────────────────────────────
    # K-15: Sachbearbeiter-Name wie im Forderungsschreiben
    bearbeiter_name = ""
    if mandant:
        # Versuche Sachbearbeiter aus Kanzleidaten
        bearbeiter_name = akte_daten.get("kanzlei", {}).get("sachbearbeiter", "")
    sl_xml  = _p("Sollte das Gericht noch weiteren Vortrag für notwendig erachten, "
                 "so wird um einen richterlichen Hinweis gebeten.")
    sl_xml += _lz()
    sl_xml += _p(kanzlei_str)
    sl_xml += _lz()
    if bearbeiter_name:
        sl_xml += _p(f"Rechtsanwalt {bearbeiter_name}")
    else:
        sl_xml += _p("Rechtsanwalt")

    # ════════════════════════════════════════════════════════════════════════
    # ZUSAMMENFÜHREN UND RENDERN
    # ════════════════════════════════════════════════════════════════════════
    ooxml_blocks = {
        "{{AKTENZEICHEN}}":           az_xml,
        "{{DATUM}}":                  datum_xml,
        "{{GERICHT_ADRESSE}}":        gericht_adresse_xml,
        "{{KLAEGER_BLOCK}}":          klaeger_xml,
        "{{HPV_BLOCK}}":              hpv_xml,
        "{{ANTRAEGE}}":               antraege_xml,
        "{{EINLEITUNG}}":             einleitung_xml,
        "{{AKTIVLEGITIMATION}}":      _build_aktivlegitimation_xml(
            details, kl_einf, anrede_m
        ),
        "{{UNFALLHERGANG}}":          unfall_xml,
        "{{SCHADEN}}":                schaden_xml,
        "{{RECHTLICHE_WUERDIGUNG}}":  rw_xml,
        "{{SCHMERZENSGELD}}":         sg_xml,
        "{{VERZUG}}":                 verzug_xml,
        "{{VORGERICHTLICHE_KOSTEN}}": vk_xml,
        "{{SCHLUSSFORMEL}}":          sl_xml,
    }

    return _render_docx(_VORLAGE, replacements, ooxml_blocks)

def _xml_antrag(nr: int, text: str) -> str:
    """Nummerierten Klageantrag als OOXML-Absatz."""
    return (
        f'<w:p>'
        f'<w:pPr><w:ind w:left="720" w:hanging="720"/></w:pPr>'
        f'<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
        f'<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
        f'<w:t xml:space="preserve">{nr}.\t{_esc(text)}</w:t></w:r>'
        f'</w:p>'
    )


def _fmt_datum(iso: str) -> str:
    """
    Wandelt Datum in deutsches Format DD.MM.YYYY.
    Unterstützt: YYYY-MM-DD (ISO), DD.MM.YYYY, DD.MM.YY (WDM-Kurzformat).
    """
    if not iso:
        return ""
    s = iso.strip()
    try:
        # ISO: 2025-03-01
        if "-" in s and s[4] == "-":
            teile = s[:10].split("-")
            return f"{teile[2]}.{teile[1]}.{teile[0]}"
        # Bereits deutsch: 01.03.2025 oder 01.03.25
        if "." in s:
            teile = s.split(".")
            if len(teile) == 3:
                j = teile[2].strip()
                if len(j) == 2:
                    j = f"20{j}"  # WDM: 25 → 2025
                return f"{teile[0].zfill(2)}.{teile[1].zfill(2)}.{j}"
    except Exception:
        pass
    return s


