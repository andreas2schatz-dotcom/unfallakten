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
# PRD-29: Gemeinsamer Schmerzensgeld-Textbaustein
from .sg_text_builder import baue_sg_abschnitt

logger = logging.getLogger(__name__)

_MODUL_DIR = os.path.dirname(__file__)
# Klageschrift nutzt dieselbe Vorlage wie Forderungsschreiben
_VORLAGE_FS = Path(_MODUL_DIR) / "forderungsschreiben_vorlage.docx"  # Forderungsschreiben

# ── RVG Tabelle § 13 RVG – Anlage 2 ──────────────────────────────────────────
# Stichtag: Akten angelegt bis 31.05.2025 → KostRÄG 2021
#           Akten angelegt ab 01.06.2025  → 2. KostRMoG 2025
# !! Werte gegen Anlage 2 zu § 13 RVG (BGBl.) prüfen !!

_RVG_STICHTAG_2025 = date(2025, 6, 1)

# KostRÄG 2021 – gültig bis 31.05.2025
# Quelle: Anlage 2 zu § 13 RVG (Stand bis 31.05.2025)
_RVG_TABELLE_2021 = [
    (500,     49.00),
    (1000,    88.00),
    (1500,   127.00),
    (2000,   166.00),
    (3000,   222.00),
    (4000,   278.00),
    (5000,   334.00),
    (6000,   390.00),
    (7000,   446.00),
    (8000,   502.00),
    (9000,   558.00),
    (10000,  614.00),
    (13000,  666.00),
    (16000,  718.00),
    (19000,  770.00),
    (22000,  822.00),
    (25000,  874.00),
    (30000,  955.00),
    (35000,  1036.00),
    (40000,  1117.00),
    (45000,  1198.00),
    (50000,  1279.00),
    (65000,  1373.00),
    (80000,  1467.00),
    (95000,  1561.00),
    (110000, 1655.00),
    (125000, 1749.00),
    (140000, 1843.00),
    (155000, 1937.00),
    (170000, 2031.00),
    (185000, 2125.00),
    (200000, 2219.00),
    (230000, 2351.00),
    (260000, 2483.00),
    (290000, 2615.00),
    (320000, 2747.00),
    (350000, 2879.00),
    (380000, 3011.00),
    (410000, 3143.00),
    (440000, 3275.00),
    (470000, 3407.00),
    (500000, 3539.00),
]

# 2. KostRMoG – gültig ab 01.06.2025
# Quelle: Anlage 2 zu § 13 RVG, BGBl. 2025 I Nr. 109
_RVG_TABELLE_2025 = [
    (500,     51.50),
    (1000,    93.00),
    (1500,   134.50),
    (2000,   176.00),
    (3000,   235.50),
    (4000,   295.00),
    (5000,   354.50),
    (6000,   414.00),
    (7000,   473.50),
    (8000,   533.00),
    (9000,   592.50),
    (10000,  652.00),
    (13000,  707.00),
    (16000,  762.00),
    (19000,  817.00),
    (22000,  872.00),
    (25000,  927.00),
    (30000,  1013.00),
    (35000,  1099.00),
    (40000,  1185.00),
    (45000,  1271.00),
    (50000,  1357.00),
    (65000,  1456.50),
    (80000,  1556.00),
    (95000,  1655.50),
    (110000, 1755.00),
    (125000, 1854.50),
    (140000, 1954.00),
    (155000, 2053.50),
    (170000, 2153.00),
    (185000, 2252.50),
    (200000, 2352.00),
    (230000, 2492.00),
    (260000, 2632.00),
    (290000, 2772.00),
    (320000, 2912.00),
    (350000, 3052.00),
    (380000, 3192.00),
    (410000, 3332.00),
    (440000, 3472.00),
    (470000, 3612.00),
    (500000, 3752.00),
]


def _rvg_grundgebuehr(streitwert: float, tabelle: list) -> float:
    """Ermittelt die Grundgebühr nach § 13 RVG aus dem Streitwert."""
    for grenze, gebuehr in tabelle:
        if streitwert <= grenze:
            return gebuehr
    # Über Tabellen-Maximum: lineare Näherung je angefangene 50.000 €
    if tabelle is _RVG_TABELLE_2025:
        # Über 500.000 €: je angefangene 30.000 € = 140,00 € (Progression aus Tabelle)
        basis    = 3752.00
        mehrwert = streitwert - 500000
        basis   += (mehrwert // 30000) * 140.00
    else:
        # Über 500.000 €: je angefangene 30.000 € = 132,00 € (KostRÄG 2021)
        basis    = 3539.00
        mehrwert = streitwert - 500000
        basis   += (mehrwert // 30000) * 132.00
    return round(basis, 2)


def berechne_rvg(streitwert: float, faktor: float = 1.3,
                 erstellt_am: str = None) -> dict:
    """
    Berechnet die vorgerichtlichen RVG-Kosten.

    erstellt_am: ISO-Datum der Akte (z.B. "2025-06-15 14:30:00").
                 Ab 01.06.2025 gilt die 2. KostRMoG-Tabelle.

    Returns:
        {
          "grundgebuehr":   507.00,
          "faktor":         1.3,
          "gebuehr_netto":  507.00,  # Grundgebühr × Faktor (wenn Faktor=1.3 → direkt)
          "post_pauschale": 20.00,
          "zwischen_netto": 527.00,
          "ust":            100.13,
          "gesamt":         627.13,
          "rvg_version":    "2025",   # "2021" oder "2025"
        }
    """
    tabelle = _RVG_TABELLE_2021
    rvg_version = "2021"
    if erstellt_am:
        try:
            akte_datum = date.fromisoformat(str(erstellt_am)[:10])
            if akte_datum >= _RVG_STICHTAG_2025:
                tabelle = _RVG_TABELLE_2025
                rvg_version = "2025"
        except (ValueError, TypeError):
            pass
    grundgebuehr   = _rvg_grundgebuehr(streitwert, tabelle)
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
        "rvg_version":    rvg_version,
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


def _pct_str(wert: float) -> str:
    """Prozentanzeige ohne int-Truncation: 66.67 -> '66,67', 50.0 -> '50'."""
    gerundet = round(wert, 2)
    if gerundet == int(gerundet):
        return str(int(gerundet))
    return f"{gerundet:.2f}".rstrip("0").rstrip(".").replace(".", ",")


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
        kl_einf_klein = kl_einf[0].lower() + kl_einf[1:]
        text = f"{kl_einf} ist {kl_eigen} des Fahrzeugs{mkz_satz}."
        if ist_fahrer:
            text += (
                f"\nFür {kl_pron_akk} streitet bereits § 1006 BGB, "
                f"da {kl_einf_klein} zum Zeitpunkt des Unfalls das Fahrzeug selbst fuhr."
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

# ── Unterschrift (identisch mit forderungsschreiben_wv.py) ────────────────────
_SIG_RID   = "rId18"
_SIG_MEDIA = "word/media/image2.png"

_SA_DRAWING_XML = (
    '<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"'
    ' wp14:anchorId="14E4ED95" wp14:editId="029D3954">'
    '<wp:extent cx="981075" cy="485775"/>'
    '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
    '<wp:docPr id="742740175" name="Bild 1"/>'
    '<wp:cNvGraphicFramePr>'
    '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
    '</wp:cNvGraphicFramePr>'
    '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
    '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
    '<pic:nvPicPr>'
    '<pic:cNvPr id="0" name="Picture 1"/>'
    '<pic:cNvPicPr><a:picLocks noChangeAspect="1" noChangeArrowheads="1"/></pic:cNvPicPr>'
    '</pic:nvPicPr>'
    '<pic:blipFill>'
    '<a:blip r:embed="rId18">'
    '<a:extLst><a:ext uri="{28A0092B-C50C-407E-A947-70E740481C1C}">'
    '<a14:useLocalDpi xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main" val="0"/>'
    '</a:ext></a:extLst>'
    '</a:blip>'
    '<a:srcRect/><a:stretch><a:fillRect/></a:stretch>'
    '</pic:blipFill>'
    '<pic:spPr bwMode="auto">'
    '<a:xfrm><a:off x="0" y="0"/><a:ext cx="981075" cy="485775"/></a:xfrm>'
    '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
    '<a:noFill/><a:ln><a:noFill/></a:ln>'
    '</pic:spPr>'
    '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>'
)


def _render_docx(vorlage: Path, replacements: dict, ooxml_blocks: dict,
                 unterschrift: Optional[bytes] = None) -> bytes:
    """
    Öffnet DOCX-Vorlage, ersetzt einfache Platzhalter (String) und
    OOXML-Blöcke (ganzen <w:p>-Absatz), gibt DOCX-Bytes zurück.
    Identisch zum Forderungsschreiben-System inkl. Unterschrift-Einbettung.
    """
    import zipfile as _zf, re as _re, io as _io
    with open(vorlage, "rb") as f:
        vb = f.read()

    output = _io.BytesIO()
    sig_written = False
    with _zf.ZipFile(_io.BytesIO(vb), "r") as zin, \
         _zf.ZipFile(output, "w", _zf.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/_rels/document.xml.rels" and unterschrift:
                rels_xml = data.decode("utf-8")
                if _SIG_RID not in rels_xml:
                    rel_entry = (
                        f'<Relationship Id="{_SIG_RID}" '
                        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                        f'Target="media/image2.png"/>'
                    )
                    rels_xml = rels_xml.replace("</Relationships>", rel_entry + "</Relationships>")
                    data = rels_xml.encode("utf-8")
            elif item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                xml = _merge_split_placeholders(xml, list(replacements.keys()))
                for key, value in replacements.items():
                    xml = xml.replace(key, value)
                for ph, block in ooxml_blocks.items():
                    xml = _inject_block(xml, ph, block)
                data = xml.encode("utf-8")
            elif item.filename == _SIG_MEDIA and unterschrift:
                data = unterschrift
                sig_written = True
            zout.writestr(item, data)
        # Vorlage hat kein image2.png-Placeholder → neu hinzufügen
        if unterschrift and not sig_written:
            zout.writestr(_SIG_MEDIA, unterschrift)
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


def _anrede_norm(anrede) -> str:
    a = str(anrede or "").strip().lower()
    if a in ("1", "herr", "herrn"):
        return "herr"
    if a in ("2", "frau"):
        return "frau"
    return ""


def _ist_maennliche_privatperson(bek: dict) -> bool:
    ist_firma = bool(bek.get("firma") or bek.get("versicherung"))
    return (not ist_firma) and _anrede_norm(bek.get("anrede")) == "herr"


def _rechtsform_klasse(firmenname: str) -> str:
    """Wortgrenzen-Klassifikation statt Substring ("UG" in "FAHRZEUGBAU", KW-21)."""
    roh = (firmenname or "").upper()
    if re.search(r"\bE\.\s?V\b", roh):
        return "vorstand"
    tokens = set(re.split(r"[^A-ZÄÖÜ0-9]+", roh))
    if tokens & {"GMBH", "UG", "GBR", "OHG", "KG"}:
        return "gf"
    if tokens & {"AG", "SE", "KGAA", "EV"}:
        return "vorstand"
    return "sonstige"


def _beklagten_grammatik(beklagte_gef: list) -> dict:
    if len(beklagte_gef) > 1:
        return {
            "verurteilt":   "Die Beklagten werden als Gesamtschuldner verurteilt",
            "verpflichtet": "die Beklagten als Gesamtschuldner verpflichtet sind",
            "kosten":       "Die Beklagten tragen die Kosten des Rechtsstreits.",
            "nom_klein":    "die Beklagten",
            "haftet":       "haften",
        }
    if beklagte_gef and _ist_maennliche_privatperson(beklagte_gef[0]):
        return {
            "verurteilt":   "Der Beklagte wird verurteilt",
            "verpflichtet": "der Beklagte verpflichtet ist",
            "kosten":       "Der Beklagte trägt die Kosten des Rechtsstreits.",
            "nom_klein":    "der Beklagte",
            "haftet":       "haftet",
        }
    return {
        "verurteilt":   "Die Beklagte wird verurteilt",
        "verpflichtet": "die Beklagte verpflichtet ist",
        "kosten":       "Die Beklagte trägt die Kosten des Rechtsstreits.",
        "nom_klein":    "die Beklagte",
        "haftet":       "haftet",
    }


def _beklagten_rolle(bek: dict) -> str:
    return "Beklagter" if _ist_maennliche_privatperson(bek) else "Beklagte"


def _vertreter_suffix(funktion: str, name: str, firmenname: str) -> str:
    """KW-16: Artikel/Anrede aus dem Genus der Funktion; ohne Funktion keine Anrede raten."""
    funktion = (funktion or "").strip()
    name = (name or "").strip()
    if funktion:
        weiblich = funktion.endswith("in") or funktion.endswith("ende")
        artikel = "die" if weiblich else "den"
        anrede = "Frau" if weiblich else "Herrn"
        if name:
            return f", vertreten durch {artikel} {funktion} {anrede} {name}"
        return f", vertreten durch {artikel} {funktion}"
    funk_label = _funktion_aus_rechtsform_str(firmenname)
    if name:
        return f", vertreten durch den {funk_label} {name}"
    return f", vertreten durch den {funk_label}"


def _funktion_aus_rechtsform_str(firmenname: str) -> str:
    """Gibt die korrekte Funktion (Geschäftsführer/Vorstand) für eine Rechtsform zurück."""
    k = _rechtsform_klasse(firmenname)
    if k == "gf":
        return "Geschäftsführer"
    if k == "vorstand":
        return "Vorstand"
    return "gesetzlichen Vertreter"


def _vertretungs_hinweis(firmenname: str) -> str:
    """Vertretungshinweis je Rechtsform (Kläger-Rubrum bei Firmen)."""
    k = _rechtsform_klasse(firmenname)
    if k == "gf":
        return "– vertreten durch den/die Geschäftsführer –"
    if k == "vorstand":
        return "– vertreten durch den Vorstand –"
    return "– vertreten durch den gesetzlichen Vertreter –"

def _sachverhalt_override_xml(text):
    # type: (str) -> str
    """
    Wandelt einen sachverhalt_override-Freitext in OOXML um.
    BEWEIS:\\t-Zeilen werden mit Tab-Stop-Formatierung gerendert.
    Aller andere Text wird als ein einzelner Fließtext-Absatz (Blocksatz) zusammengeführt.
    """
    xml = ""
    fliess_teile = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.startswith("BEWEIS:\t") or block.upper().startswith("BEWEIS: "):
            if fliess_teile:
                xml += _p(" ".join(fliess_teile))
                fliess_teile = []
            xml += _beweis(block[block.index("\t") + 1:].strip()
                           if "\t" in block else block[len("BEWEIS:"):].strip())
        else:
            for zeile in block.split("\n"):
                z = zeile.strip()
                if z:
                    fliess_teile.append(z)
    if fliess_teile:
        xml += _p(" ".join(fliess_teile))
    return xml


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


from .forderungsschreiben_wv import (
    _unterschrift_bytes,
    _hole_sb_info,
)

_REGULIERUNG_LABEL_MAP = {
    "fahrzeugschaden":       "Fahrzeugschaden",
    "reparaturkosten":       "Reparaturkosten lt. Gutachten (netto)",
    "rep_gutachten_netto":   "Reparaturkosten lt. Gutachten (netto)",
    "rep_rechnung_netto":    "Reparaturkosten lt. Rechnung (netto)",
    "rep_rechnung_brutto":   "Reparaturkosten lt. Rechnung (brutto)",
    "reparatur_netto":       "Reparaturkosten (netto)",
    "reparatur_brutto":      "Reparaturkosten (brutto)",
    "wiederbeschaffung":     "Wiederbeschaffungswert",
    "wbw":                   "Wiederbeschaffungswert",
    "wbw_netto":             "Wiederbeschaffungswert (netto)",
    "wbw_brutto":            "Wiederbeschaffungswert (brutto)",
    "wba":                   "Wiederbeschaffungsaufwand",
    "restwert":              "abzgl. Restwert",
    "wertminderung":         "Merkantile Wertminderung",
    "nutzungsausfall":       "Nutzungsausfallschaden",
    "mietwagenkosten":       "Mietwagenkosten",
    "mietwagenkosten_netto": "Mietwagenkosten (netto)",
    "sv_kosten":             "Sachverständigenkosten",
    "kostennb":              "Nachbesichtigungskosten",
    "abschleppkosten":       "Abschleppkosten",
    "standkosten":           "Standkosten",
    "standkosten_netto":     "Standkosten (netto)",
    "anabmeldekosten":       "An-/Abmeldekosten",
    "restkraftstoff":        "Restkraftstoff",
    "schmerzensgeld":        "Schmerzensgeld",
    "verdienstausfall":      "Verdienstausfall",
    "haushalt":              "Haushaltsführungsschaden",
    "unkostenpauschale":     "Unkostenpauschale",
    "kostenpauschale":       "Unkostenpauschale",
    "ra_gebuehren":          "Rechtsanwaltsgebühren (vorgerichtlich)",
    "vorschuss":             "Vorschuss",
    "mwst_abzug":            "MwSt.-Abzug",
    "pruefbericht_abzug":    "Prüfbericht-Abzug",
    "sonstiges":             "Sonstige Schäden",
}


def _baue_regulierungs_tbl_xml(reg_agg: dict, ungebunden: float = 0.0, body_width: int = 9163) -> tuple:
    """
    Baut eine Zahlungs-Tabelle aus reg_agg (position_key → {gesamt_reguliert}).
    Gibt (xml, gesamt_reguliert) zurück. xml ist leer wenn keine Zahlungen vorliegen.
    KW-04: `ungebunden` (Zahlungen ohne Positionszuordnung, z.B. Vorschüsse)
    fließt als eigene Zeile ein, damit die Tabelle alle geleisteten Zahlungen abbildet.
    """
    positionen = []
    for key, daten in reg_agg.items():
        betrag = float(daten.get("gesamt_reguliert") or 0)
        if betrag == 0:
            continue
        if key.startswith("sonstiges_wdm_"):
            label = "Sonstige Schäden"
        else:
            label = _REGULIERUNG_LABEL_MAP.get(key, key.replace("_", " ").title())
        positionen.append((label, betrag))

    if ungebunden > 0:
        positionen.append(("Zahlung ohne Positionszuordnung", round(ungebunden, 2)))

    if not positionen:
        return "", 0.0

    gesamt = round(sum(b for _, b in positionen), 2)
    col_l  = int(body_width * 0.75)
    col_r  = body_width - col_l

    RPR = ('<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
           '<w:sz w:val="24"/><w:szCs w:val="24"/>')
    RPR_B = RPR + '<w:b/><w:bCs/>'

    def _zeile(label, betrag, fett=False):
        rpr = RPR_B if fett else RPR
        ws  = _eur_str(betrag)
        return (
            f'<w:tr>'
            f'<w:tc><w:tcPr><w:tcW w:w="{col_l}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{_esc(label)}</w:t></w:r></w:p></w:tc>'
            f'<w:tc><w:tcPr><w:tcW w:w="{col_r}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:jc w:val="right"/></w:pPr>'
            f'<w:r><w:rPr>{rpr}</w:rPr><w:t>{_esc(ws)}</w:t></w:r></w:p></w:tc>'
            f'</w:tr>'
        )

    header = (
        f'<w:tr>'
        f'<w:tc><w:tcPr><w:tcW w:w="{col_l}" w:type="dxa"/></w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
        f'<w:r><w:rPr>{RPR_B}</w:rPr><w:t>Geleistete Zahlung</w:t></w:r></w:p></w:tc>'
        f'<w:tc><w:tcPr><w:tcW w:w="{col_r}" w:type="dxa"/></w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
        f'<w:jc w:val="right"/></w:pPr>'
        f'<w:r><w:rPr>{RPR_B}</w:rPr><w:t>Betrag</w:t></w:r></w:p></w:tc>'
        f'</w:tr>'
    )

    xml = (
        f'<w:tbl><w:tblPr><w:tblW w:w="{body_width}" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="none"/><w:left w:val="none"/>'
        '<w:bottom w:val="none"/><w:right w:val="none"/>'
        '<w:insideH w:val="none"/><w:insideV w:val="none"/>'
        '</w:tblBorders></w:tblPr>'
        + header
        + "".join(_zeile(l, b) for l, b in positionen)
        + _zeile("Gesamtzahlung", gesamt, fett=True)
        + '</w:tbl>'
    )
    return xml, gesamt


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

    akte            = akte_daten.get("akte") or {}
    mandant         = akte_daten.get("mandant") or {}
    kanzlei         = akte_daten.get("kanzlei") or {}
    details         = akte_daten.get("unfalldetails") or {}
    cfg             = akte_daten.get("klage_config") or {}
    abrechnungen    = akte_daten.get("abrechnungen") or []
    reg_agg         = akte_daten.get("reg_agg") or {}
    ps_data         = akte_daten.get("personenschaden") or {}  # PRD-29

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
    _anrede_raw = (mandant.get("anrede") or "").strip()
    # Normalisierung: RA-MICRO liefert sAnrede numerisch ("1"=Herr, "2"=Frau)
    if _anrede_raw == "1":   _anrede_raw = "Herr"
    elif _anrede_raw == "2": _anrede_raw = "Frau"
    anrede_m = _anrede_raw.lower()
    vorsteuer       = (mandant.get("vorsteuer") or "N").upper() in ("J", "JA", "Y", "1")

    # Deduplizierung nach ID: doppelte Mandanten-Einträge (SQLite-Bug) dürfen
    # mehrere_klaeger nicht fälschlicherweise auf True setzen.
    _kl_seen = set()
    klaeger_liste = []
    for b in beklagte_liste:
        if b.get("rolle_klage") == "klaeger":
            bid = b.get("id") or id(b)
            if bid not in _kl_seen:
                _kl_seen.add(bid)
                klaeger_liste.append(b)

    # KW-18: kein Klaeger-Beteiligter im Rubrum -> auf Mandantendaten
    # zurueckfallen; ist auch das leer, harte Sperre statt leerem Rubrum.
    if not klaeger_liste:
        _fb = {
            "rolle_klage": "klaeger",
            "name":      mandant.get("name") or "",
            "vorname":   mandant.get("vorname") or "",
            "firma":     mandant.get("firma") or "",
            "anschrift": mandant.get("anschrift") or "",
            "plz":       mandant.get("plz") or "",
            "ort":       mandant.get("ort") or "",
            "anrede":    mandant.get("anrede") or "",
        }
        if not (_fb["name"] or _fb["firma"]):
            raise ValueError("Kein Kläger ermittelbar – bitte Mandanten-/Parteidaten prüfen.")
        klaeger_liste = [_fb]

    mehrere_klaeger  = len(klaeger_liste) > 1

    if mehrere_klaeger:
        kl_art  = "der"; kl_bez = "Kläger"; kl_nom = "Die Kläger"; kl_dat = "die Kläger"
        kl_einf = "Kläger"; kl_gesch = "Geschädigte"
        nicht_vst = "vorsteuerabzugsberechtigte" if vorsteuer else "nicht vorsteuerabzugsberechtigte"
        kl_macht = "machen"; kl_ist = "sind"; kl_laesst = "lassen"
    elif anrede_m in ("herr", "herrn"):
        kl_art  = "des"; kl_bez = "Klägers"; kl_nom = "Der Kläger"; kl_dat = "den Kläger"
        kl_einf = "Kläger"; kl_gesch = "Geschädigter"
        nicht_vst = "nicht vorsteuerabzugsberechtigter" if not vorsteuer else "vorsteuerabzugsberechtigter"
        kl_macht = "macht"; kl_ist = "ist"; kl_laesst = "lässt"
    elif anrede_m == "frau":
        kl_art  = "der"; kl_bez = "Klägerin"; kl_nom = "Die Klägerin"; kl_dat = "die Klägerin"
        kl_einf = "Klägerin"; kl_gesch = "Geschädigte"
        nicht_vst = "nicht vorsteuerabzugsberechtigte" if not vorsteuer else "vorsteuerabzugsberechtigte"
        kl_macht = "macht"; kl_ist = "ist"; kl_laesst = "lässt"
    else:
        kl_art  = "des"; kl_bez = "Klägers"; kl_nom = "Der Kläger"; kl_dat = "den Kläger"
        kl_einf = "Kläger"; kl_gesch = "Geschädigter"
        nicht_vst = "nicht vorsteuerabzugsberechtigter" if not vorsteuer else "vorsteuerabzugsberechtigter"
        kl_macht = "macht"; kl_ist = "ist"; kl_laesst = "lässt"

    # ── Schmerzensgeld ───────────────────────────────────────────────────────
    mit_sg  = bool(cfg.get("mit_schmerzensgeld"))
    sg_mind = float(cfg.get("schmerzensgeld_mindest") or 0)

    # ── Haftungsquote (KW-03) ────────────────────────────────────────────────
    hq_cfg = cfg.get("haftungsquote")
    try:
        hq = float(hq_cfg) if hq_cfg is not None else float(
            details.get("haftungsquote") or akte.get("haftungsquote") or 100
        )
    except (ValueError, TypeError):
        hq = float(details.get("haftungsquote") or akte.get("haftungsquote") or 100)
    hq_typ = cfg.get("haftungsquote_typ") or "gegnerisch"

    # ── Positionen / Gegenstandswert ─────────────────────────────────────────
    # KW-07: bei aktivem unbezifferten SG-Antrag (mit_sg) die bezifferte
    # SG-Position ausschliessen, sonst wird Schmerzensgeld doppelt geltend
    # gemacht (beziffert in Antrag 1/Tabelle/Gegenstandswert UND unbeziffert).
    positionen = [p for p in (cfg.get("positionen") or [])
                  if isinstance(p, dict) and p.get("checked")
                  and not (mit_sg and p.get("key") == "schmerzensgeld")]

    # KW-03 Fall B: eigene Mithaftungsquote - erst quotieren, dann die bereits
    # geleisteten Zahlungen abziehen. gesamt_voll/fallb_zahlungen werden auch
    # fuer den Differenz-Satz an der Schadentabelle benoetigt (Fall-B-Variante).
    fallb_aktiv = hq_typ == "eigen" and 0 < hq < 100
    if fallb_aktiv:
        fallb_gesamt_voll = sum(
            float(p.get("betragOriginal") if p.get("betragOriginal") is not None else p.get("betrag") or 0)
            for p in positionen
        )
        fallb_zahlungen = round(
            fallb_gesamt_voll - sum(float(p.get("betrag") or 0) for p in positionen), 2
        )
        klagebetrag = max(0.0, round(fallb_gesamt_voll * hq / 100 - fallb_zahlungen, 2))
    else:
        klagebetrag = sum(float(p.get("betrag") or 0) for p in positionen)

    # ── RVG ──────────────────────────────────────────────────────────────────
    rvg_override     = cfg.get("rvg_override")
    akte_erstellt_am = akte.get("rvg_anlagedatum") or akte.get("erstellt_am")
    rvg              = cfg.get("rvg") or berechne_rvg(klagebetrag,
                                                       erstellt_am=akte_erstellt_am)
    if rvg_override is not None:
        rvg["gesamt"] = float(rvg_override)

    # ── Zinsen ───────────────────────────────────────────────────────────────
    zinsen_ab     = cfg.get("zinsen_ab") or "verzug"
    verzugsdatum  = _fmt_datum(cfg.get("verzugsdatum") or "")
    zins_sachsch  = f"dem {verzugsdatum}" if zinsen_ab == "verzug" and verzugsdatum else "Rechtshängigkeit"
    zins_rvg      = "Rechtshängigkeit"

    # ── PRD-26: Antrags-Override + Feststellungsanträge + RVG außergerichtlich ─
    antraege_override     = (cfg.get("antraege_override") or "").strip()
    mit_feststellung_sg   = bool(cfg.get("mit_feststellung_sg"))
    mit_feststellung_sach = bool(cfg.get("mit_feststellung_sach"))
    rvg_ausserg           = cfg.get("rvg_ausserg") or {}
    rvg_ausserg_override  = cfg.get("rvg_ausserg_override")
    rvg_bereits_gezahlt   = round(float(cfg.get("rvg_bereits_gezahlt") or 0), 2)
    # BE-3: Welcher Betrag kommt in den RVG-Antrag?
    if rvg_ausserg_override is not None:
        rvg_antrag_betrag = float(rvg_ausserg_override)
    elif rvg_ausserg.get("gesamt") is not None:
        rvg_antrag_betrag = float(rvg_ausserg["gesamt"])
    else:
        rvg_antrag_betrag = float(rvg["gesamt"])
    # Bereits gezahlten Anteil abziehen → nur offener Rest wird eingeklagt
    if rvg_bereits_gezahlt > 0:
        rvg_antrag_betrag = round(max(0.0, rvg_antrag_betrag - rvg_bereits_gezahlt), 2)

    # ── Gegner-Kennzeichen ───────────────────────────────────────────────────
    gegner_kz = (
        next((b["kfz_kennzeichen"] for b in beklagte_liste if b.get("kfz_kennzeichen")), "")
        or details.get("_wdm_gegner_kz") or ""
    )

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
    # klaeger_liste wurde oben bereits dedupliziert – direkt verwenden
    klaeger_objs = klaeger_liste
    for i, kl in enumerate(klaeger_objs):
        kl_name    = " ".join(filter(None, [kl.get("vorname"), kl.get("name")])) or kl.get("firma") or "KLÄGER"
        kl_anschr  = kl.get("anschrift") or ""
        kl_plz_ort = " ".join(filter(None, [kl.get("plz"), kl.get("ort")])) or ""
        # Rollenbezeichnung mit Nummer wenn mehrere Kläger
        _kl_anrede_raw = (kl.get("anrede") or "").strip()
        if _kl_anrede_raw == "1":   _kl_anrede_raw = "Herr"
        elif _kl_anrede_raw == "2": _kl_anrede_raw = "Frau"
        kl_anrede  = _kl_anrede_raw.lower()
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
    # klaeger_xml += _lz()

    # ── {{HPV_BLOCK}} ─────────────────────────────────────────────────────
    hpv_xml = ""
    beklagte_gef = [b for b in beklagte_liste
                    if (b.get("rolle_klage") or b.get("rolle") or "") not in ("klaeger", "mandant")
                    and b.get("checked", True)]
    bek_gram = _beklagten_grammatik(beklagte_gef)
    for i, bek in enumerate(beklagte_gef):
        # Personen haben Vorrang: vorname+name zuerst, dann Firmen-/Versicherungsname
        _bek_person = " ".join(filter(None, [bek.get("vorname"), bek.get("name")])).strip()
        bek_name    = _bek_person or bek.get("firma") or bek.get("versicherung") or "BEKLAGTE"
        bek_anschr  = bek.get("anschrift") or ""
        bek_plz_ort = " ".join(filter(None, [bek.get("plz"), bek.get("ort")])) or ""
        # ist_firma: firma oder versicherung gesetzt → Vertretungshinweis einblenden
        # (kein _bek_person-Check: Organisationen wie "DBGK e. V." haben name, kein vorname)
        ist_firma   = bool(bek.get("firma") or bek.get("versicherung"))
        nr_suffix   = f" zu {i+1})" if len(beklagte_gef) > 1 else ""
        vertreter_name = (bek.get("vertreter_name") or "").strip()
        vertreter_funk = (bek.get("vertreter_funktion") or "").strip()
        if ist_firma:
            vertreter_suffix = _vertreter_suffix(vertreter_funk, vertreter_name, bek_name)
        else:
            vertreter_suffix = ""

        # Adresszeile + Vertreter + Schadennummer in einer Zeile
        import re as _re
        schaden_nr_raw = (bek.get("schaden_nr") or "").strip()
        schaden_nr_val = _re.sub(r"^Schadennummer:\s*", "", schaden_nr_raw, flags=_re.IGNORECASE)
        schaden_suffix = f", zur Schadennummer {schaden_nr_val}" if schaden_nr_val else ""
        adress_teile = [t for t in [bek_name, bek_anschr, bek_plz_ort] if t]
        full_line = ", ".join(adress_teile) + vertreter_suffix + schaden_suffix
        hpv_xml += _p(full_line)
        hpv_xml += _rolle_rechts(f"– {_beklagten_rolle(bek)}{nr_suffix} –")
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
    # Dativ für Feststellungsanträge
    if mehrere_klaeger:
        kl_dat3 = "den Klägern"
    elif kl_bez == "Klägerin":
        kl_dat3 = "der Klägerin"
    else:
        kl_dat3 = "dem Kläger"

    _versaeumnis_block = (
        _lz()
        + _p("Für den Fall der Anordnung des schriftlichen Vorverfahrens bitten wir, "
             "für den Fall der Nichteinlassung der Beklagten:")
        + _lz()
        + _p("Versäumnisurteil", fett=True, center=True)
        + _lz()
        + _p("ohne mündliche Verhandlung zu erlassen.")
    )

    if antraege_override:
        # BE-1: Wizard-Override direkt rendern
        # RVG-Antragsnummer: vorletzter nummerierter Antrag (letzter = Kostentragung)
        _nummern = re.findall(r'^\d+(?=\.[\t ])', antraege_override, re.MULTILINE)
        rvg_antrag_nr = int(_nummern[-2]) if len(_nummern) >= 2 else len(_nummern)

        antraege_xml  = _p(f"Namens und in Vollmacht {vollmacht_text} erheben wir Klage, "
                           "bitten um Anordnung des schriftlichen Vorverfahrens "
                           "und werden beantragen:")
        antraege_xml += _lz()
        for _line in antraege_override.split("\n"):
            _line = _line.strip()
            if not _line:
                antraege_xml += _lz()
            elif re.match(r'^\d+\.[\t ]', _line):
                # Nummerierter Antrag → hängender Einzug + fett
                antraege_xml += (
                    f'<w:p><w:pPr><w:jc w:val="both"/>'
                    f'<w:ind w:left="720" w:hanging="360"/></w:pPr>'
                    f'<w:r><w:rPr>'
                    f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
                    f'<w:b/><w:bCs/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
                    f'<w:t xml:space="preserve">{_esc(_line)}</w:t></w:r></w:p>'
                )
            else:
                antraege_xml += _p(_line)
        antraege_xml += _versaeumnis_block
    else:
        # Fallback: Auto-Generierung (rückwärtskompatibel)
        antraege_xml  = _p(f"Namens und in Vollmacht {vollmacht_text} erheben wir Klage, "
                           "bitten um Anordnung des schriftlichen Vorverfahrens "
                           "und werden beantragen:")
        antraege_xml += _lz()
        antraege_xml += antrag(
            f"{bek_gram['verurteilt']}, an {kl_dat} {_eur_str(klagebetrag)} "
            f"nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz "
            f"seit {zins_sachsch} zu zahlen."
        )
        antraege_xml += _lz()
        if mit_sg:
            if sg_mind > 0:
                antraege_xml += antrag(
                    f"{bek_gram['verurteilt']}, an {kl_dat} ein angemessenes, "
                    f"vom Gericht festzulegendes Schmerzensgeld zu zahlen, "
                    f"wobei die Höhe nicht weniger als {_eur_str(sg_mind)} betragen sollte, "
                    f"nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz seit Rechtshängigkeit."
                )
            else:
                antraege_xml += antrag(
                    f"{bek_gram['verurteilt']}, an {kl_dat} ein angemessenes, "
                    f"vom Gericht nach billigem Ermessen festzulegendes Schmerzensgeld zu zahlen, "
                    f"nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz seit Rechtshängigkeit."
                )
            antraege_xml += _lz()
        # BE-2: Feststellungsanträge (Personenschaden)
        if mit_feststellung_sg:
            antraege_xml += antrag(
                f"Es wird festgestellt, dass {bek_gram['verpflichtet']}, {kl_dat3} "
                f"sämtliche künftigen materiellen und immateriellen Schäden zu ersetzen, "
                f"die aus dem Unfallereignis vom {unfalltag} noch entstehen werden, "
                f"soweit Ansprüche nicht auf Sozialversicherungsträger oder sonstige Dritte "
                f"übergegangen sind oder noch übergehen werden."
            )
            antraege_xml += _lz()
        # BE-2: Feststellungsantrag (Sachschaden)
        if mit_feststellung_sach:
            antraege_xml += antrag(
                f"Es wird festgestellt, dass {bek_gram['verpflichtet']}, {kl_dat3} "
                f"sämtliche weiteren materiellen Schäden zu ersetzen, die aus dem "
                f"Unfallereignis vom {unfalltag} noch entstehen werden."
            )
            antraege_xml += _lz()
        # BE-3: RVG-Antrag auf außergerichtlichem Streitwert (wenn rvg_ausserg vorhanden)
        rvg_antrag_nr = antrag_nr[0]   # Nummer vor dem Aufruf merken
        antraege_xml += antrag(
            f"{bek_gram['verurteilt']}, an {kl_dat} weitere {_eur_str(rvg_antrag_betrag)} "
            f"nebst Zinsen von 5 Prozentpunkten über dem Basiszinssatz "
            f"seit {zins_rvg} zu zahlen."
        )
        antraege_xml += _lz()
        antraege_xml += antrag(bek_gram["kosten"], fett=False)
        antraege_xml += _versaeumnis_block

    # ── {{EINLEITUNG}} ────────────────────────────────────────────────────
    if details.get("sachverhalt_override"):
        # Wizard hat einen kombinierten Sachverhalt-Text übergeben (Einleitung +
        # Beklagten-Block + AktLeg in einem). Überschreibt die Auto-Generierung.
        einleitung_xml = _lz() + _p("1.) Sachverhalt", fett=True)
        einleitung_xml += _sachverhalt_override_xml(details["sachverhalt_override"])
        aktivleg_xml   = ""
    else:
        einleitung_xml  = _lz() + _p("1.) Sachverhalt", fett=True)

        # Alle Einleitungssätze zu einem Fließtext-Absatz zusammenführen
        if unfalltag:
            intro_satz = (
                f"{kl_nom} {kl_macht} als {nicht_vst} {kl_gesch} Schadensersatzforderungen "
                f"aus einem Verkehrsunfall vom {unfalltag} in {unfallort} geltend."
            )
        elif mehrere_klaeger:
            intro_satz = (
                f"{kl_nom} {kl_macht} als {nicht_vst} {kl_gesch} Schadensersatzforderungen "
                f"aus einem Verkehrsunfall in {unfallort} geltend."
            )
        else:
            intro_satz = (
                f"{kl_nom} macht Schadensersatzforderungen aus einem Verkehrsunfall "
                f"in {unfallort} geltend."
            )
        bek_saetze = []
        mehrere_bek = len(beklagte_gef) > 1
        schadennr_gesetzt = False
        for i, bek in enumerate(beklagte_gef):
            nr_str = f" zu {i+1})" if mehrere_bek else ""
            if bek.get("versicherung") or (bek.get("firma") and not bek.get("ist_halter")):
                satz = (
                    f"Die Beklagte{nr_str} ist die Haftpflichtversicherung des "
                    f"unfallverursachenden Fahrzeugs mit dem amtlichen Kennzeichen {gegner_kz}."
                    if gegner_kz else
                    f"Die Beklagte{nr_str} ist die Haftpflichtversicherung des "
                    f"unfallverursachenden Fahrzeugs."
                )
                if schadennummer and not schadennr_gesetzt:
                    satz += f" Sie führt den Vorgang unter der Schadennummer {schadennummer}."
                    schadennr_gesetzt = True
            else:
                ist_firma_b = bool(bek.get("firma") or bek.get("versicherung"))
                weiblich_b = ist_firma_b or _anrede_norm(bek.get("anrede")) == "frau"
                art = "Die" if weiblich_b else "Der"
                if bek.get("ist_halter"):
                    bez = "die Halterin" if weiblich_b else "der Halter"
                    satz = f"{art} Beklagte{nr_str} ist {bez} des unfallverursachenden Fahrzeugs."
                else:
                    bez = "die Fahrerin" if weiblich_b else "der Fahrer"
                    satz = (f"{art} Beklagte{nr_str} war zum Unfallzeitpunkt {bez} "
                            f"des unfallverursachenden Fahrzeugs.")
            bek_saetze.append(satz)
        beklagte_satz = " ".join(bek_saetze)

        mandant_kz = (details.get("_wdm_mandant_kz") or
                      mandant.get("kfz_kennzeichen") or "").strip()
        aktivlegitimation_typ = (details.get("aktivlegitimation_typ") or "eigentum").strip()
        weiblich = anrede_m == "frau"
        if aktivlegitimation_typ in ("finanziert", "geleast"):
            if mehrere_klaeger:
                halter_besitzer = "Halter und unmittelbare Besitzer"
            elif weiblich:
                halter_besitzer = "Halterin und unmittelbare Besitzerin"
            else:
                halter_besitzer = "Halter und unmittelbarer Besitzer"
            eigentuemer_satz = (
                f"{kl_nom} {kl_ist} {halter_besitzer} des bei dem Unfall beschädigten "
                f"Fahrzeugs mit dem amtlichen Kennzeichen {mandant_kz}."
                if mandant_kz else
                f"{kl_nom} {kl_ist} {halter_besitzer} des bei dem Unfall beschädigten Fahrzeugs."
            )
        else:
            eigentuemer = "Eigentümer" if mehrere_klaeger else ("Eigentümerin" if weiblich else "Eigentümer")
            eigentuemer_satz = (
                f"{kl_nom} {kl_ist} {eigentuemer} des bei dem Unfall beschädigten "
                f"Fahrzeugs mit dem amtlichen Kennzeichen {mandant_kz}."
                if mandant_kz else
                f"{kl_nom} {kl_ist} {eigentuemer} des bei dem Unfall beschädigten Fahrzeugs."
            )
        hat_override = bool(details.get("aktivlegitimation_text_override"))
        # § 1006-Argument hängt am AktLeg-Block: bei Eigentum+Fahrer wandert die
        # Eigentumsbehauptung dorthin, damit sie nicht doppelt im Dokument steht.
        if aktivlegitimation_typ == "eigentum" and not hat_override and bool(details.get("mandant_ist_fahrer")):
            einleitung_xml += _p(f"{intro_satz} {beklagte_satz}")
            aktivleg_xml = _build_aktivlegitimation_xml(details, kl_nom, anrede_m)
        else:
            einleitung_xml += _p(f"{intro_satz} {beklagte_satz} {eigentuemer_satz}")
            if aktivlegitimation_typ == "eigentum" and not hat_override:
                aktivleg_xml = ""
            else:
                aktivleg_xml = _build_aktivlegitimation_xml(details, kl_nom, anrede_m)

    # ── {{UNFALLHERGANG}} ─────────────────────────────────────────────────
    schilderung = details.get("schilderung") or ""
    zeugen = [
        f"{details.get(f'zeuge_{i}')}, {details.get(f'zeuge_{i}_anschrift') or 'n.n.'}"
        for i in (1, 2, 3) if details.get(f"zeuge_{i}")
    ]
    ea_az  = details.get("ermittlungsakte_az") or ""
    ea_beh = details.get("ermittlungsakte_behoerde") or ""

    unfall_xml  = _lz() + _p("2.) Unfallhergang", fett=True)
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
    # KW-04: eine Rechenquelle - Tabelle wird auf die checked cfg-Positionen
    # gefiltert (100 %-Werte aus betragOriginal), damit Antrag 1, Tabelle und
    # Differenz-Satz nicht mehr auseinanderlaufen können.
    schaden_raw = dict(akte_daten.get("schaden") or {})
    checked_keys = {p.get("key") for p in positionen}

    _FAHRZEUG_DB_KEYS = (
        "rep_gutachten_netto", "reparaturkosten", "rep_rechnung_netto",
        "rep_rechnung_brutto", "wiederbeschaffung", "restwert",
    )
    if "fahrzeugschaden" not in checked_keys:
        for _k in _FAHRZEUG_DB_KEYS:
            schaden_raw.pop(_k, None)

    # Nebenkosten mit Netto/USt/Brutto-Varianten: nur Filterung (keine
    # 100%-Überschreibung, da _netto_oder_brutto() die Werte je nach
    # Vorsteuerstatus unterschiedlich zusammensetzt).
    _NEBENKOSTEN_GRUPPEN = {
        "mietwagenkosten": ("mietwagenkosten", "mietwagenkosten_netto", "mietwagenkosten_ust"),
        "sv_kosten":       ("sv_kosten", "sv_kosten_netto", "sv_kosten_ust"),
        "kostennb":        ("kostennb", "kostennb_ust"),
        "abschleppkosten": ("abschleppkosten", "abschleppkosten_netto", "abschleppkosten_ust"),
        "standkosten":     ("standkosten", "standkosten_netto", "standkosten_ust"),
        "anabmeldekosten": ("anabmeldekosten", "anabmeldekosten_netto", "anabmeldekosten_ust"),
    }
    for _pos_key, _db_keys in _NEBENKOSTEN_GRUPPEN.items():
        if _pos_key not in checked_keys:
            for _k in _db_keys:
                schaden_raw.pop(_k, None)

    # Einfache 1:1-Keys: nicht checked → raus; checked → betragOriginal
    # (Fallback: vorhandener DB-Wert, dann betrag) statt des rohen DB-Werts.
    _EINFACHE_POS_KEYS = (
        "wertminderung", "nutzungsausfall", "haushalt",
        "verdienstausfall", "schmerzensgeld", "sonstiges",
    )
    for _pos_key in _EINFACHE_POS_KEYS:
        if _pos_key not in checked_keys:
            schaden_raw.pop(_pos_key, None)
    if "unkostenpauschale" not in checked_keys:
        # explizit 0.0 (nicht entfernen!) - sonst greift der 30-€-Default (KW-11)
        schaden_raw["unkostenpauschale"] = 0.0

    for p in positionen:
        _key = p.get("key")
        if _key not in _EINFACHE_POS_KEYS and _key != "unkostenpauschale":
            continue
        _wert = p.get("betragOriginal")
        if _wert is None:
            _wert = schaden_raw.get(_key)
        if _wert is None:
            _wert = p.get("betrag")
        schaden_raw[_key] = float(_wert or 0)

    # WDM-Extras (wdm_extras_json) ebenfalls auf checked cfg-Positionen filtern -
    # der Wizard erzeugt dafür Keys "extra_<key-oder-label>" (gleiche Ableitung
    # wie in klage_routes.py bei pos_definitionen), sonst umgehen Extras den
    # Checked-Filter und verfälschen Tabelle/Differenz-Satz (Finding 1, KW-04).
    _extras_raw = schaden_raw.get("wdm_extras_json") or "[]"
    try:
        _extras = json.loads(_extras_raw) if isinstance(_extras_raw, str) else (_extras_raw or [])
        if not isinstance(_extras, list):
            _extras = []
    except Exception:
        _extras = []

    _extras_gefiltert = []
    for _ex in _extras:
        _ex_key = f"extra_{_ex.get('key', _ex.get('label', '?'))}"
        if _ex_key not in checked_keys:
            continue
        _ex_pos = next((p for p in positionen if p.get("key") == _ex_key), None)
        _ex_wert = (_ex_pos or {}).get("betragOriginal")
        if _ex_wert is None:
            _ex_wert = _ex.get("betrag") or _ex.get("netto")
        _ex_neu = dict(_ex)
        _ex_neu["betrag"] = float(_ex_wert or 0)
        _extras_gefiltert.append(_ex_neu)
    schaden_raw["wdm_extras_json"] = json.dumps(_extras_gefiltert, ensure_ascii=False)

    schaden_gesamt = klagebetrag
    try:
        from .forderungsschreiben_wv import _baue_tabelle as _bt
        tabelle_xml, schaden_gesamt = _bt(
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

    # KW-04: Regulierungstabelle inkl. ungebundener Vorschüsse - der Betrag,
    # den die Abrechnungen insgesamt ausweisen (gesamt_reguliert), abzüglich
    # dessen, was bereits positionsgebunden erfasst ist (reg_agg).
    gesamt_reguliert_abrechnungen = round(
        sum(float(a.get("gesamt_reguliert") or 0) for a in abrechnungen), 2
    )
    gesamt_reguliert_positionsgebunden = round(
        sum(float(d.get("gesamt_reguliert") or 0) for d in reg_agg.values()), 2
    )
    ungebundener_vorschuss = round(
        max(0.0, gesamt_reguliert_abrechnungen - gesamt_reguliert_positionsgebunden), 2
    )
    reg_tbl_xml, _ = _baue_regulierungs_tbl_xml(
        reg_agg, ungebunden=ungebundener_vorschuss
    )

    schaden_xml  = _lz() + _p("3.) Unfallschaden", fett=True)
    schaden_xml += _p("Durch den Unfall ist ein Schaden entstanden, der sich wie folgt zusammensetzt:")
    schaden_xml += tabelle_xml
    schaden_xml += _lz()
    schaden_xml += _beweis("Schadengutachten (Anlage K 1)")
    schaden_xml += _lz()
    schaden_xml += _p("Einholung eines gerichtlichen Sachverständigengutachtens.", fett=True)

    if fallb_aktiv:
        # KW-03 Fall B: eigene Quote - der Satz zeigt schaden_gesamt (Tabelle) als
        # Basis, daher muss auch die Quote auf schaden_gesamt gerechnet werden.
        # fallb_gesamt_voll (cfg-betragOriginal-Summe) kann bei Nebenkosten
        # (netto/brutto via _netto_oder_brutto) von schaden_gesamt abweichen -
        # nur klagebetrag (Antrag 1) darf auf fallb_gesamt_voll basieren.
        _ersatzfaehig = round(schaden_gesamt * hq / 100, 2)
        _zahlungen_anzeige = round(_ersatzfaehig - klagebetrag, 2)
        schaden_xml += _lz()
        if _zahlungen_anzeige > 0:
            schaden_xml += _p("Die Beklagte hat folgende Zahlungen auf den Schaden geleistet:")
            if reg_tbl_xml:
                schaden_xml += reg_tbl_xml
            schaden_xml += _lz()
            schaden_xml += _p(
                f"Von dem Gesamtschaden in Höhe von {_eur_str(schaden_gesamt)} sind unter "
                f"Berücksichtigung der Mithaftungsquote von {_pct_str(100 - hq)} % {_pct_str(hq)} %, "
                f"mithin {_eur_str(_ersatzfaehig)}, ersatzfähig. Abzüglich der geleisteten Zahlungen "
                f"in Höhe von {_eur_str(_zahlungen_anzeige)} verbleiben {_eur_str(klagebetrag)}, "
                f"die mit dem Klageantrag zu 1 geltend gemacht werden."
            )
        else:
            schaden_xml += _p(
                f"Von dem Gesamtschaden in Höhe von {_eur_str(schaden_gesamt)} sind unter "
                f"Berücksichtigung der Mithaftungsquote von {_pct_str(100 - hq)} % {_pct_str(hq)} %, "
                f"mithin {_eur_str(_ersatzfaehig)}, ersatzfähig. Dieser Betrag wird mit dem "
                f"Klageantrag zu 1 geltend gemacht."
            )
    else:
        # KW-04: Differenz-Satz aus einer Quelle - Zahlungen ergeben sich aus
        # schaden_gesamt (Tabelle, 100 %) und klagebetrag (Antrag 1), nicht mehr
        # unabhängig aus gesamt_reguliert_tbl. Der Satz endet damit immer exakt
        # beim Antrag-1-Betrag.
        _zahlungen = round(schaden_gesamt - klagebetrag, 2)
        if _zahlungen > 0:
            schaden_xml += _lz()
            schaden_xml += _p("Die Beklagte hat folgende Zahlungen auf den Schaden geleistet:")
            if reg_tbl_xml:
                schaden_xml += reg_tbl_xml
            schaden_xml += _lz()
            schaden_xml += _p(
                f"Die Differenz des geforderten Gesamtbetrages in Höhe von {_eur_str(schaden_gesamt)} "
                f"abzgl. der oben gezeigten geleisteten Zahlungen in Höhe von {_eur_str(_zahlungen)} "
                f"beträgt {_eur_str(klagebetrag)} und wird mit dem Klageantrag zu 1 geltend gemacht."
            )
        else:
            schaden_xml += _lz()
            schaden_xml += _p(
                f"Der Gesamtbetrag in Höhe von {_eur_str(schaden_gesamt)} wird mit dem "
                f"Klageantrag zu 1 geltend gemacht."
            )

    # ── {{RECHTLICHE_WUERDIGUNG}} ─────────────────────────────────────────
    rw_text_override = (details.get("rw_text_override") or "").strip()
    if rw_text_override:
        rw_xml = _lz() + _p("4.) Rechtliche Würdigung", fett=True)
        for _line in rw_text_override.split("\n"):
            _line = _line.strip()
            if not _line:
                rw_xml += _lz()
            elif _line.startswith("**") and _line.endswith("**"):
                rw_xml += _p(_line[2:-2], fett=True)
            else:
                rw_xml += _p(_line)
    else:
        haftungsbegruendung = details.get("haftungsbegruendung") or ""

        rw_xml  = _lz() + _p("4.) Rechtliche Würdigung", fett=True)
        rw_xml += _p(f"Der bei der Beklagten versicherte Unfallgegner verursachte den Unfall "
                     f"durch {haftungsbegruendung or 'sein schuldhaftes Verhalten'}. "
                     f"Die Haftungsquote beträgt {_pct_str(hq)} %.")
        # Regulierungshinweis nur wenn keine positions-genaue Tabelle vorhanden
        if not reg_tbl_xml:
            gesamt_reguliert = sum(float(a.get("gesamt_reguliert") or 0) for a in abrechnungen)
            if gesamt_reguliert > 0:
                rw_xml += _p(
                    f"Die Beklagte hat eine Teilregulierung in Höhe von {_eur_str(gesamt_reguliert)} "
                    f"vorgenommen. Die verbleibenden Kürzungen sind nicht gerechtfertigt, "
                    f"sodass die Klage in Höhe des offenen Restbetrages erhoben wird."
                )
            else:
                rw_xml += _p(
                    "Die Beklagte hat bislang keine Regulierung vorgenommen. "
                    "Da trotz mehrfacher Fristsetzung keine Zahlung erfolgte, war die Klage notwendig."
                )
        # KW-03: "entsprechend gekürzt" nur im Fall B (eigene Quote) wahr -
        # im Fall gegnerisch wird die Mithaftungsquote bestritten.
        if hq < 100:
            if hq_typ == "eigen":
                rw_xml += _p(
                    f"{kl_nom} {kl_laesst} sich eine Mithaftungsquote von {_pct_str(100 - hq)} % anrechnen. "
                    f"Die Klageforderung ist entsprechend gekürzt."
                )
            else:
                rw_xml += _p(
                    f"Die Beklagtenseite geht von einer Mithaftungsquote von "
                    f"{_pct_str(100 - hq)} % auf Klägerseite aus. Dies wird bestritten; die "
                    f"Beklagtenseite haftet in vollem Umfang. Die Klageforderung ist ungekürzt "
                    f"geltend gemacht."
                )

    # ── {{SCHMERZENSGELD}} ────────────────────────────────────────────────
    if mit_sg:
        sg_xml = _lz() + _p("5.) Schmerzensgeld", fett=True)
        sg_absaetze, sg_beweis, sg_vgl = baue_sg_abschnitt(
            ps_data, kl_nom, sg_mind,
            verb_hat="haben" if mehrere_klaeger else "hat")
        for absatz in sg_absaetze:
            sg_xml += _p(absatz)
        if sg_vgl:
            sg_xml += _p(sg_vgl, einzug=True)
        sg_xml += _p(sg_beweis, einzug=True)
    else:
        sg_xml = ""   # leer → Platzhalter verschwindet

    # ── {{VERZUG}} ────────────────────────────────────────────────────────
    verzug_text_override = (details.get("verzug_text_override") or "").strip()
    if verzug_text_override:
        verzug_xml = ""
        for _line in verzug_text_override.split("\n"):
            _line = _line.strip()
            if not _line:
                verzug_xml += _lz()
            elif _line.upper().startswith("BEWEIS:"):
                verzug_xml += _beweis(_line[len("BEWEIS:"):].strip())
            else:
                verzug_xml += _p(_line)
        verzug_xml += _lz()
    else:
        if verzugsdatum:
            verzug_xml = _p(
                f"Der Verzug ist nach Ablauf der Zahlungsfrist bzw. dem ernsthaften "
                f"und endgültigen Verweigern der Leistung am {verzugsdatum} eingetreten."
            )
            verzug_xml += _beweis(f"Schreiben vom {verzugsdatum}")
        else:
            verzug_xml = _p("Verzug ist mit Rechtshängigkeit eingetreten.")
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

    # Außergerichtlicher Streitwert: aus rvg_ausserg (hat .streitwert wenn vom rvg-berechnen-Endpoint),
    # Fallback auf klagebetrag damit die Tabelle nie leer bleibt.
    sw_ausserg = round(float(rvg_ausserg.get("streitwert") or 0), 2) or klagebetrag
    rvg_fuer_tab = rvg_ausserg if rvg_ausserg.get("gesamt") else rvg
    rvg_brutto = round(float(rvg_ausserg_override or rvg_fuer_tab.get("gesamt") or 0), 2)
    rvg_tabelle = (
        '<w:tbl><w:tblPr><w:tblW w:w="9163" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="2" w:space="0" w:color="CCCCCC"/>'
        '</w:tblBorders></w:tblPr>'
        + _rvg_tbl_zeile(f"Gegenstandswert:", _eur_str(sw_ausserg), fett=True)
        + _rvg_tbl_zeile(f"Geschäftsgebühr §§ 13, 14, Nr. 2300 VV RVG ({rvg_fuer_tab.get('faktor', 1.3)}):",
                         _eur_str(rvg_fuer_tab.get("gebuehr_netto", 0)))
        + _rvg_tbl_zeile("Post u. Telekommunikation Nr. 7002 VV RVG:",
                         _eur_str(rvg_fuer_tab.get("post_pauschale", 0)))
        + _rvg_tbl_zeile("Zwischensumme netto:", _eur_str(rvg_fuer_tab.get("zwischen_netto", 0)), fett=True)
        + _rvg_tbl_zeile("19 % Umsatzsteuer:", _eur_str(rvg_fuer_tab.get("ust", 0)))
        + _rvg_tbl_zeile("Gesamtbetrag:", _eur_str(rvg_brutto), fett=True)
        + (
            _rvg_tbl_zeile("abzüglich bereits gezahlter Kosten:", f"- {_eur_str(rvg_bereits_gezahlt)}")
            + _rvg_tbl_zeile("Klageanteil (offen):", _eur_str(rvg_antrag_betrag), fett=True)
            if rvg_bereits_gezahlt > 0 else ""
          )
        + '</w:tbl>'
    )

    bek_haften = bek_gram["haftet"]
    bek_nom    = bek_gram["nom_klein"]

    vk_nr   = 5 + int(mit_sg)  # 5 ohne SG, 6 mit SG
    vk_xml  = _lz() + _p(f"{vk_nr}.) Vorgerichtliche Rechtsanwaltsgebühren", fett=True)
    vk_xml += _p(
        f"Der Klageantrag zu {rvg_antrag_nr}. ergibt sich aus den vorgerichtlich entstandenen "
        f"Gebühren, für die {bek_nom} ebenfalls {bek_haften}. "
        f"Der Anspruch auf Zahlung vorgerichtlicher Rechtsverfolgungskosten folgt aus § 249 ff. BGB "
        f"unabhängig von einem etwaigen Verzugseintritt. Der Geschädigte sieht sich im Regelfall "
        f"einem in der Regulierung von Unfallschäden versierten Sachbearbeiter des "
        f"Haftpflichtversicherers gegenüber. Unter dem Aspekt der Waffengleichheit wird deshalb "
        f"eine Erstattungsfähigkeit der Rechtsanwaltskosten im Rahmen der Rechtsverfolgungskosten "
        f"grundsätzlich bejaht (Berz/Buhrmann Straßenverkehrsrecht \u2013 Hdb/Ziegenhardt, "
        f"48. EL August 2023 5. C. Rn. 82, Beck-online)."
    )
    vk_xml += _lz()
    vk_xml += _p(
        "Der Prozessbevollmächtigte war bereits vorgerichtlich mit der Gegenseite in Kontakt "
        "getreten. Letztmalig, als man die Gegenseite unter Fristsetzung zur Zahlung aufforderte."
    )
    vk_xml += _lz()
    vk_xml += _p(
        "Die hieraus vorgerichtlich entstandenen Rechtsanwaltsgebühren sind zu ersetzen. "
        "Die Gebühren berechnen sich wie folgt:"
    )
    vk_xml += rvg_tabelle

    # ── {{SCHLUSSFORMEL}} ─────────────────────────────────────────────────
    # K-15: Sachbearbeiter aus RA-MICRO (identisch mit Forderungsschreiben)
    sb_kuerzel  = akte.get("sachbearbeiter") or ""
    sb          = _hole_sb_info(sb_kuerzel)
    unterschrift = _unterschrift_bytes(sb_kuerzel)
    sb_name     = sb.get("name") or "Koch, Schatz & Kollegen"
    sb_titel    = sb.get("titel") or "Rechtsanwälte"

    PPR_SL = '<w:pPr><w:jc w:val="both"/></w:pPr>'
    RPR_SL = ('<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
              '<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>')

    def _psl(text: str = "") -> str:
        t = f'<w:t xml:space="preserve">{_esc(text)}</w:t>' if text else "<w:t/>"
        return f'<w:p>{PPR_SL}<w:r>{RPR_SL}{t}</w:r></w:p>'

    sl_xml  = _p("Sollte das Gericht noch weiteren Vortrag für notwendig erachten, "
                 "so wird um einen richterlichen Hinweis gebeten.")
    sl_xml += f'<w:p>{PPR_SL}</w:p>'
    if unterschrift:
        sl_xml += (f'<w:p>{PPR_SL}<w:r><w:rPr><w:noProof/></w:rPr>'
                   f'{_SA_DRAWING_XML}</w:r></w:p>')
    sl_xml += _psl(sb_name)
    sl_xml += _psl(sb_titel)

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
        "{{AKTIVLEGITIMATION}}":      aktivleg_xml,
        "{{UNFALLHERGANG}}":          unfall_xml,
        "{{SCHADEN}}":                schaden_xml,
        "{{RECHTLICHE_WUERDIGUNG}}":  rw_xml,
        "{{SCHMERZENSGELD}}":         sg_xml,
        "{{VERZUG}}":                 verzug_xml,
        "{{VORGERICHTLICHE_KOSTEN}}": vk_xml,
        "{{SCHLUSSFORMEL}}":          sl_xml,
    }

    return _render_docx(_VORLAGE, replacements, ooxml_blocks, unterschrift)

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


