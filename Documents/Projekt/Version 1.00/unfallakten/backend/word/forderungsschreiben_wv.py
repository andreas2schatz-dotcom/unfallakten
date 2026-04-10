"""
Forderungsschreiben Generator
==============================
Vorlage: forderungsschreiben_vorlage.docx
Alle 16 Platzhalter werden per str.replace() befüllt.
OOXML-Blöcke (SCHADENTABELLE, VERLETZUNGSBLOCK, GRUSSFORMEL) ersetzen
den kompletten <w:p>-Absatz der den Platzhalter enthält.
"""

import io
import json
import logging
import os
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# PRD-14: Single Source of Truth
from ..models.schaden import berechne_abrechnungsart as _berechne_abrechnungsart
# PRD-29: Gemeinsamer Schmerzensgeld-Textbaustein
from .sg_text_builder import baue_sg_abschnitt as _baue_sg_abschnitt

logger = logging.getLogger(__name__)

_MODUL_DIR = os.path.dirname(__file__)
_VORLAGE   = Path(_MODUL_DIR) / "forderungsschreiben_vorlage.docx"

_KANZLEI_IBAN = os.environ.get("KANZLEI_IBAN", "DE12 3456 7890 1234 5678 90")
_KANZLEI_BIC  = os.environ.get("KANZLEI_BIC",  "COBADEFFXXX")

# Bewährtes SA-Drawing (rId10, byte-identisch mit SA-Vorlage)
_SIG_RID       = "rId18"        # Eigene rId für Unterschrift in document.xml.rels
_SIG_MEDIA     = "word/media/image2.png"   # Unterschrift-Platzhalter in der Vorlage

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


# ══════════════════════════════════════════════════════════════════════════════
# GRAMMATIK
# ══════════════════════════════════════════════════════════════════════════════

_GRAMMATIK: dict = {
    "m": {
        "@pp2A":  "seiner",   # Possessiv Genitiv
        "@a2A":   "unseres",  # Artikel Genitiv
        "@a3P":   "unserem",  # Artikel Dativ
        "@S1A":   "",         # Mandant-Suffix Nominativ → "Mandant"
        "@S2A":   "en",       # Mandant-Suffix Akkusativ/Genitiv → "Mandanten"
        "@S3A":   "en",       # Mandant-Suffix Genitiv attrib.
        "@S3P":   "",         # Fahrer-Suffix Dativ
        "@P1A":   "",         # unser/unsere
        "@P2A":   "es",
        "@PP1A":  "Er",
        "@pp1A":  "er",
        "@pp3A":  "er",
        "@pp3P":  "er",
        "@pp4A":  "ihn",
    },
    "f": {
        "@pp2A":  "ihrer",
        "@a2A":   "unserer",
        "@a3P":   "unserer",
        "@S1A":   "in",       # → "Mandantin"
        "@S2A":   "in",
        "@S3A":   "in",
        "@S3P":   "in",
        "@P1A":   "e",
        "@P2A":   "er",
        "@PP1A":  "Sie",
        "@pp1A":  "sie",
        "@pp3A":  "sie",
        "@pp3P":  "sie",
        "@pp4A":  "sie",
    },
    "p": {
        # Plural: Eheleute, Rechtsanwälte
        # "unserer Mandanten" (Genitiv Plural)
        "@pp2A":  "ihrer",
        "@a2A":   "unserer",
        "@a3P":   "unseren",
        "@S1A":   "en",       # → "Mandanten"
        "@S2A":   "en",
        "@S3A":   "en",
        "@S3P":   "en",
        "@P1A":   "e",        # → "unsere Mandanten"
        "@P2A":   "er",
        "@PP1A":  "Sie",
        "@pp1A":  "sie",
        "@pp3A":  "sie",
        "@pp3P":  "sie",
        "@pp4A":  "sie",
    },
}


# RA-Micro speichert sAnrede als Zahl (String):
#   0=Selbstdefiniert  1=Herr   2=Frau    3=Notar   4=Firma
#   5=Rechtsanwalt     6=RA'e   7=RA'in   8=Eheleute 9=Sonstige  10=Notarin
_ANREDE_GESCHLECHT = {
    "0": None,   # selbstdefiniert → briefanrede auswerten
    "1": "m",    # Herr
    "2": "f",    # Frau
    "3": "m",    # Notar
    "4": None,   # Firma → name prüfen (e.V. → m, sonst f)
    "5": "m",    # Rechtsanwalt
    "6": "p",    # Rechtsanwälte (Plural)
    "7": "f",    # Rechtsanwältin
    "8": "p",    # Eheleute (Plural)
    "9": "f",    # Sonstige → Fallback f
    "10": "f",   # Notarin
}


def _ev_check(name: str) -> bool:
    """True wenn Name einen eingetragenen Verein (e.V./eV) enthält → männlich."""
    return bool(re.search(r'(?<![a-zA-Z])e\.?\s*[Vv]\.?(?![a-zA-Z])', name or ""))


def _grammatik_vars(s_anrede: str, name: str = "", briefanrede: str = "") -> dict:
    """
    Bestimmt das grammatikalische Geschlecht anhand von sAnrede.

    RA-Micro speichert sAnrede numerisch als String ("1"=Herr, "2"=Frau etc.).
    Fallback auf Text-Erkennung für SQLite-Daten ohne RA-Micro-Kodierung.
    """
    a = (s_anrede or "").strip()

    # ── Numerische RA-Micro Kodierung (primär) ────────────────────────────
    if a in _ANREDE_GESCHLECHT:
        g = _ANREDE_GESCHLECHT[a]
        if g is not None:
            return dict(_GRAMMATIK[g])
        # g == None: 0=Selbstdefiniert oder 4=Firma
        if a == "4":
            # Firma: e.V. → m, sonst f
            return dict(_GRAMMATIK["m" if _ev_check(name) else "f"])
        # a == "0": selbstdefiniert → direkt zu Briefanrede-Auswertung
        ba = (briefanrede or "").strip().lower()
        if re.search(r'geehrter\b|lieber\s+herr\b', ba):
            return dict(_GRAMMATIK["m"])
        if re.search(r'geehrte\s+frau\b|liebe\s+frau\b', ba):
            return dict(_GRAMMATIK["f"])
        if _ev_check(name):
            return dict(_GRAMMATIK["m"])
        return dict(_GRAMMATIK["f"])

    # ── Text-Fallback (SQLite-Daten, manuell erfasst) ─────────────────────
    al = a.lower().rstrip(".")
    if al in ("herr", "herrn", "hr", "mr", "mister", "notar", "rechtsanwalt"):
        return dict(_GRAMMATIK["m"])
    if al in ("frau", "fr", "mrs", "ms", "notarin",
              "rechtsanwältin", "rechtsanwaeltin", "sonstige"):
        return dict(_GRAMMATIK["f"])
    if al in ("eheleute", "rechtsanwälte", "rechtsanwaelte"):
        return dict(_GRAMMATIK["p"])
    if al in ("firma",):
        return dict(_GRAMMATIK["m" if _ev_check(name) else "f"])
    if al:
        return dict(_GRAMMATIK["m" if _ev_check(name) else "f"])

    # ── Briefanrede auswerten (leer oder 0=Selbstdefiniert) ───────────────
    ba = (briefanrede or "").strip().lower()
    if re.search(r'geehrter\b|lieber\s+herr\b', ba):
        return dict(_GRAMMATIK["m"])
    if re.search(r'geehrte\s+frau\b|liebe\s+frau\b', ba):
        return dict(_GRAMMATIK["f"])
    if _ev_check(name):
        return dict(_GRAMMATIK["m"])
    return dict(_GRAMMATIK["f"])



def _fahrer_dativ(gegner: dict) -> str:
    """'dem Fahrer' (m/Fallback) oder 'der Fahrerin' (f)."""
    if not gegner.get("vorname"):
        return "dem Fahrer"
    a = (gegner.get("anrede") or "").strip().lower()
    if a in ("frau", "fr.", "mrs", "ms"):
        return "der Fahrerin"
    return "dem Fahrer"


def _mandant_anrede_nominativ(mandant: dict) -> str:
    """Nominativ-Anrede: 'Herr' / 'Frau' / 'Eheleute' / ''."""
    a = (mandant.get("anrede") or "").strip().lower().rstrip(".")
    if a in ("herr", "herrn", "hr", "mr", "mister", "notar", "rechtsanwalt"):
        return "Herr"
    if a in ("frau", "fr", "mrs", "ms", "notarin", "rechtsanwältin", "rechtsanwaeltin"):
        return "Frau"
    if a in ("eheleute",):
        return "Eheleute"
    if a in ("rechtsanwälte", "rechtsanwaelte"):
        return "Rechtsanwälte"
    ba = (mandant.get("briefanrede") or "").strip().lower()
    if re.search(r'geehrter\b|lieber\s+herr\b', ba):
        return "Herr"
    if re.search(r'geehrte\s+frau\b|liebe\s+frau\b', ba):
        return "Frau"
    return ""


def _mandant_genitiv(s_anrede: str, name: str = "", briefanrede: str = "") -> str:
    """Genitiv: 'unseres Mandanten' / 'unserer Mandantin' / 'unserer Mandanten' (Plural)."""
    gram = _grammatik_vars(s_anrede, name, briefanrede)
    s1a = gram.get("@S1A", "")
    a2a = gram.get("@a2A", "unseres")
    if s1a == "":    return "unseres Mandanten"   # männlich
    if s1a == "in":  return "unserer Mandantin"   # weiblich
    return "unserer Mandanten"                    # plural


# ══════════════════════════════════════════════════════════════════════════════
# ÖFFENTLICHE SCHNITTSTELLE
# ══════════════════════════════════════════════════════════════════════════════

def generiere_forderungsschreiben_wv(akte_daten: dict, variante: str = "auto") -> bytes:
    return _generiere(akte_daten)


def hat_schadensdaten(schaden: Optional[dict]) -> bool:
    if not schaden:
        return False
    return any(float(schaden.get(f) or 0) > 0 for f in [
        "rep_gutachten_netto", "rep_rechnung_netto", "rep_rechnung_brutto",
        "reparaturkosten",     "wiederbeschaffung",  "wertminderung",
        "nutzungsausfall",     "sv_kosten",
    ])


def dateiendung(variante: str) -> str:
    return "docx"


# ══════════════════════════════════════════════════════════════════════════════
# GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def _generiere(akte_daten: dict) -> bytes:
    if not _VORLAGE.exists():
        raise FileNotFoundError(f"Vorlage fehlt: {_VORLAGE}")

    akte    = akte_daten.get("akte")    or {}
    mandant = akte_daten.get("mandant") or {}
    gegner  = akte_daten.get("gegner")  or {}
    schaden = akte_daten.get("schaden") or {}
    wdm     = akte_daten.get("wdm_roh") or {}

    sb_kuerzel   = akte.get("sachbearbeiter") or ""
    sb           = _hole_sb_info(sb_kuerzel)
    unterschrift = _unterschrift_bytes(sb_kuerzel)

    gram = _grammatik_vars(
        mandant.get("anrede") or "",
        mandant.get("name") or mandant.get("firma") or "",
        mandant.get("briefanrede") or "",
    )

    def wv(key: str, default: str = "") -> str:
        v = (wdm.get(f"var{key}") or wdm.get(key) or "").strip()
        return default if (not v or v == "??") else v

    # ── Empfänger ─────────────────────────────────────────────────────────
    KEIN_WERT = "KEINE ADRESSE ERFASST"
    empf_name    = gegner.get("versicherung") or \
                   " ".join(filter(None, [gegner.get("vorname"), gegner.get("name")])) or \
                   KEIN_WERT
    empf_strasse = gegner.get("anschrift") or KEIN_WERT
    empf_plz_ort = " ".join(filter(None, [gegner.get("plz"), gegner.get("ort")])) or KEIN_WERT
    empf_email   = f"Nur per E-Mail: {gegner['email']}" if gegner.get("email") else ""


    # ── Aktenzeichen & Datum ───────────────────────────────────────────────
    az      = akte.get("aktenzeichen") or akte.get("az") or KEIN_WERT
    kurzb   = akte.get("kurzbezeichnung") or az
    heute   = date.today()

    # ── Betreff ───────────────────────────────────────────────────────────
    betreff1 = gegner.get("betreff1") or ""
    betreff2 = gegner.get("betreff2") or ""
    betreff3 = gegner.get("betreff3") or ""
    # Fallback: Aktenlangbezeichnung wenn alle Betreffzeilen leer
    if not any([betreff1, betreff2, betreff3]):
        betreff1 = akte.get("aktenbezeichnung") or kurzb

    # ── Anrede (sBriefanrede des Gegners) ──────────────────────────────────
    gegner_briefanrede = (gegner.get("briefanrede") or "").strip()
    # Prüfe ob es eine generische Floskeln ohne konkreten Namen ist
    _ba_clean = gegner_briefanrede.lower().replace("sehr geehrte", "").replace("sehr geehrter", "").strip()
    if not gegner_briefanrede or not _ba_clean or _ba_clean in ("damen und herren,", "damen und herren", "r*,", "r*"):
        anrede = "Sehr geehrte Damen und Herren,"
    else:
        anrede = gegner_briefanrede if gegner_briefanrede.endswith(",") else gegner_briefanrede + ","

    # ── Mandant ───────────────────────────────────────────────────────────
    m_anrede_str = (mandant.get("anrede") or "").strip()
    m_vorname    = (mandant.get("vorname") or "").strip()
    m_nachname   = (mandant.get("name")    or "").strip()
    m_firma      = (mandant.get("firma")   or "").strip()
    m_anschrift  = mandant.get("anschrift") or mandant.get("strasse") or ""
    m_plz_ort    = " ".join(filter(None, [mandant.get("plz"), mandant.get("ort")]))

    # Ist es eine Firma? sAnrede = "4" oder sAnrede-Text = "Firma"
    _ist_firma = m_anrede_str in ("4", "firma") or (not m_vorname and m_firma)

    if _ist_firma:
        # Firma: nur Firmenname, Anrede = "die Firma XY"
        firmenname  = m_firma or m_nachname
        m_anrede_nom = "die"
        name_vollst  = f"die Firma {firmenname}"
    else:
        # Person: Anrede + Vorname + Nachname direkt aus den Feldern
        m_anrede_nom = _mandant_anrede_nominativ(mandant)
        name_vollst  = " ".join(p for p in [m_anrede_nom, m_vorname, m_nachname] if p)

    adresse = ", ".join(filter(None, [m_anschrift, m_plz_ort]))

    # ── {{VERTRETUNG}} ────────────────────────────────────────────────────
    mandanten_count = int(akte.get("mandanten_anzahl") or 1)
    verb_beauftragt = "haben" if mandanten_count > 1 else "hat"
    vollmacht_text  = "liegt bei." if wv("VOLLMACHTERKL", "Nein").lower() == "ja" \
                      else "werden wir in Kürze nachreichen."

    vertretung = (
        f"in vorbezeichneter Angelegenheit zeigen wir an, dass uns "
        f"{name_vollst}"
        + (f", {adresse}" if adresse else "")
        + f", mit der Wahrnehmung {gram['@pp2A']} Interessen beauftragt {verb_beauftragt}. "
        f"Eine auf uns lautende Vollmacht {vollmacht_text}"
    )

    # ── {{AUFTRAG}} ───────────────────────────────────────────────────────
    anspr_sg = wv("ANSPR-SG", "Nein").lower() == "ja"
    if anspr_sg:
        anspruch_str = "Schmerzensgeld- und Schadenersatzansprüche"
    else:
        anspruch_str = "Schadenersatzansprüche"

    fahrer_dat = _fahrer_dativ(gegner)
    m_gen      = _mandant_genitiv(mandant.get("anrede") or "",
                                   mandant.get("name") or mandant.get("firma") or "",
                                   mandant.get("briefanrede") or "")

    auftrag = (
        f"Wir sind mit der Durchsetzung der {anspruch_str} {m_gen} beauftragt. "
        f"Die näheren Unfalldaten und eine Unfallschilderung bitten wir dem "
        f"beigefügten Fragebogen für Anspruchsteller zu entnehmen. "
        f"Der Unfall wurde allein schuldhaft von {fahrer_dat} "
        f"des bei Ihnen versicherten Fahrzeugs verursacht."
    )

    # ── OOXML-Blöcke ──────────────────────────────────────────────────────
    bw   = _lese_textbreite(_VORLAGE)
    # Einleitungssatz vor Tabelle: Gutachten oder Kostenvoranschlag
    gutachter    = wv("GUTACHTER")
    kostenvor    = wv("KOSTENVOR", "Nein").lower() == "ja"
    if gutachter:
        if kostenvor:
            einleitung_dok = f"den Kostenvoranschlag der Firma {gutachter}"
        else:
            einleitung_dok = f"das Gutachten des Sachverständigen {gutachter}"
        einleitung_tabelle = (
            f"Wir überreichen {einleitung_dok} und beziffern den Schaden "
            f"vorläufig wie folgt:"
        )
    else:
        einleitung_tabelle = "Wir beziffern den Schaden vorläufig wie folgt:"
    vorsteuer = str(mandant.get("vorsteuer") or "N").strip().upper() in ("Y", "J", "JA", "1", "TRUE")
    tabelle_xml, _ = _baue_tabelle(schaden, bw, einleitung_tabelle, vorsteuer=vorsteuer)
    ps_data = akte_daten.get("personenschaden") or {}
    verletzung_xml = _baue_verletzungsblock(wdm, gram, ps_data)
    grussformel_xml = _baue_grussformel_xml(sb["name"], sb["titel"])

    # ── Einfache Platzhalter ───────────────────────────────────────────────
    replacements = {
        "{{EMPF_NAME}}":            _escape_xml(empf_name),
        "{{EMPF_STRASSE}}":         _escape_xml(empf_strasse),
        "{{EMPF_ORT}}":             _escape_xml(empf_plz_ort),
        "{{EMPF_EMAIL}}":           _escape_xml(empf_email),
        "{{AKTENZEICHEN}}":         _escape_xml(az),
        "{{Aktenkurzbezeichnung}}": _escape_xml(kurzb),
        "{{DATUM}}":                _escape_xml(_datum_deutsch(heute)),
        "{{BETREFF1}}":             _escape_xml(betreff1),
        "{{BETREFF2}}":             _escape_xml(betreff2),
        "{{BETREFF3}}":             _escape_xml(betreff3),
        "{{ANREDE}}":               _escape_xml(anrede),
        "{{VERTRETUNG}}":           _escape_xml(vertretung),
        "{{AUFTRAG}}":              _escape_xml(auftrag),
    }

    # OOXML-Blöcke (ersetzen ganzen <w:p>-Absatz)
    ooxml_blocks = {
        "{{SCHADENTABELLE}}":    tabelle_xml,
        "{{VERLETZUNGSBLOCK}}":  verletzung_xml,
        "{{GRUSSFORMEL}}":       grussformel_xml,
    }

    return _render_docx(_VORLAGE, replacements, ooxml_blocks, unterschrift)



def _merge_split_placeholders(xml: str, placeholders: list) -> str:
    """
    Word zersplittert Platzhalter manchmal über mehrere <w:r>-Runs.
    Diese Funktion fügt den Textinhalt benachbarter Runs zusammen,
    wenn ein Platzhalter dadurch vollständig wird.

    Strategie: Alle <w:t>-Texte innerhalb eines <w:p> zusammensuchen;
    wenn der zusammengesetzte Text einen Platzhalter enthält aber der
    einzelne Run nicht, den Absatz-XML so umschreiben dass der Platzhalter
    in einem einzigen Run landet.
    """
    for ph in placeholders:
        # Prüfen ob Platzhalter bereits als ganzes vorkommt
        if ph in xml:
            continue  # Kein Problem

        # Suche Absätze die Teile des Platzhalters enthalten
        # Einfache Strategie: alle w:t-Inhalte im Absatz zusammensetzen
        # Wenn der Platzhalter im Gesamt-Text vorkommt, Runs zusammenführen
        def _fix_para(m):
            para = m.group(0)
            # Absätze mit Bildern/Drawings nie anfassen
            if '<w:drawing>' in para or '<w:pict>' in para:
                return para
            # Alle w:t-Texte extrahieren
            texte = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para)
            gesamt = "".join(texte)
            if ph not in gesamt:
                return para  # Platzhalter nicht in diesem Absatz
            # Platzhalter ist gesplittet - ersten Run mit vollständigem Text ersetzen
            # Ersetze alle w:t-Inhalte: ersten mit Gesamttext, rest leer
            count = [0]
            def _ersetze_t(tm):
                count[0] += 1
                if count[0] == 1:
                    return f'<w:t xml:space="preserve">{gesamt}</w:t>'
                return '<w:t></w:t>'
            return re.sub(r'<w:t[^>]*>[^<]*</w:t>', _ersetze_t, para)

        xml = re.sub(r'<w:p[ >](?:(?!</w:p>).)*</w:p>', _fix_para, xml, flags=re.DOTALL)
    return xml


# ══════════════════════════════════════════════════════════════════════════════
# RENDERING
# ══════════════════════════════════════════════════════════════════════════════

def _render_docx(
    vorlage: Path,
    replacements: dict,
    ooxml_blocks: dict,
    unterschrift: Optional[bytes],
) -> bytes:
    with open(vorlage, "rb") as f:
        vb = f.read()

    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(vb), "r") as zin, \
         zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/_rels/document.xml.rels" and unterschrift:
                # rId18 für Unterschrift-Bild eintragen wenn noch nicht vorhanden
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
                # 0. Gesplittete Platzhalter zusammenführen
                xml = _merge_split_placeholders(xml, list(replacements.keys()))
                # 1. Einfache Platzhalter ersetzen
                for key, value in replacements.items():
                    xml = xml.replace(key, value)
                # 2. Leere Betreffzeilen: einfach leere Strings lassen (kein Regex)
                # xml = _entferne_leere_betreff(xml)  # deaktiviert - zu aggressiv
                # 3. OOXML-Blöcke: ganzen <w:p>-Absatz ersetzen
                for placeholder, block_xml in ooxml_blocks.items():
                    xml = _inject_block(xml, placeholder, block_xml)
                data = xml.encode("utf-8")
            elif item.filename == _SIG_MEDIA and unterschrift:
                data = unterschrift
            zout.writestr(item, data)
    return output.getvalue()


def _inject_block(xml: str, placeholder: str, block_xml: str) -> str:
    """Ersetzt den gesamten <w:p>-Absatz der den Platzhalter enthält."""
    ph_esc = re.escape(placeholder)
    return re.sub(
        r'<w:p[ >](?:(?!</w:p>).)*' + ph_esc + r'(?:(?!</w:p>).)*</w:p>',
        block_xml,
        xml,
        flags=re.DOTALL,
    )


def _entferne_leere_betreff(xml: str) -> str:
    """Entfernt Betreff-Absätze deren {{BETREFF}}-Platzhalter leer ist."""
    # Nach Ersetzung von {{BETREFF2/3}} kann ein leerer Absatz entstehen:
    # <w:p ...><w:pPr.../><w:r...><w:t></w:t></w:r></w:p>
    # Solche leeren Absätze zwischen BETREFF1 und ANREDE entfernen wir.
    xml = re.sub(r'<w:t></w:t>', '', xml)
    # Absätze die nur whitespace-w:t haben
    xml = re.sub(
        r'<w:p\b[^>]*><w:pPr>.*?</w:pPr>\s*(?:<w:r\b[^>]*>\s*<w:rPr>.*?</w:rPr>\s*<w:t/>\s*</w:r>\s*)*</w:p>',
        '', xml, flags=re.DOTALL
    )
    return xml


# ══════════════════════════════════════════════════════════════════════════════
# GRUßFORMEL
# ══════════════════════════════════════════════════════════════════════════════

def _baue_grussformel_xml(sb_name: str, sb_titel: str) -> str:
    """
    Abschlussabsatz + Leerzeile + 'Mit freundlichen Grüßen' (keine Leerzeile danach)
    + Unterschrift + SB-Name + SB-Titel (Blau 5488D4).
    """
    PPR = '<w:pPr><w:jc w:val="both"/></w:pPr>'

    def _p(text: str = "", farbe: str = "", sz: int = 24) -> str:
        farbe_xml = f'<w:color w:val="{farbe}"/>' if farbe else ""
        rpr = (f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
               f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>{farbe_xml}</w:rPr>')
        t_xml = f'<w:t xml:space="preserve">{_escape_xml(text)}</w:t>' if text else "<w:t/>"
        return f'<w:p>{PPR}<w:r>{rpr}{t_xml}</w:r></w:p>'

    leere = f'<w:p>{PPR}</w:p>'
    return (
        # Abschlussabsatz
        _p("Wir bitten um Prüfung und Aufnahme der Regulierung. "
           "Künftiger Schriftverkehr ist nur noch über unser Büro zu führen.")
        + leere
        # Grußformel (keine Leerzeile nach "Mit freundlichen Grüßen")
        + _p("Mit freundlichen Grüßen")
        + f'<w:p>{PPR}<w:r><w:rPr><w:noProof/></w:rPr>{_SA_DRAWING_XML}</w:r></w:p>'
        + _p(sb_name)
        + _p(sb_titel)
    )


# ══════════════════════════════════════════════════════════════════════════════
# VERLETZUNGSBLOCK
# ══════════════════════════════════════════════════════════════════════════════

def _baue_verletzungsblock(wdm: dict, gram: dict, ps_data: dict = None) -> str:
    """Verletzungsblock. Leer wenn ANSPR-SG != Ja."""
    def wv(key: str) -> str:
        v = (wdm.get(f"var{key}") or wdm.get(key) or "").strip()
        return "" if (not v or v == "??") else v

    if wv("ANSPR-SG").lower() != "ja":
        return ""

    PP1A = gram.get("@PP1A", "Er")
    P1A  = gram.get("@P1A",  "")
    S1A  = gram.get("@S1A",  "")

    PPR = '<w:pPr><w:jc w:val="both"/></w:pPr>'
    RPR = '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
    LEER = f'<w:p>{PPR}</w:p>'

    def _p(text: str = "") -> str:
        """Absatz mit anschließender Leerzeile."""
        if not text.strip():
            return LEER
        return (f'<w:p>{PPR}<w:r>{RPR}<w:t xml:space="preserve">{_escape_xml(text)}</w:t></w:r></w:p>'
                + LEER)

    def _p_last(text: str = "") -> str:
        """Letzter Absatz im Block — ohne nachfolgende Leerzeile."""
        if not text.strip():
            return ""
        return f'<w:p>{PPR}<w:r>{RPR}<w:t xml:space="preserve">{_escape_xml(text)}</w:t></w:r></w:p>'

    absaetze = []

    # Einleitung
    absaetze.append(_p(f"Bei dem Unfall wurde unser{P1A} Mandant{S1A} verletzt."))

    # Krankenhaus
    kh_name = wv("V-KHADR.NName")
    kh_von  = wv("V-KHVON")
    kh_bis  = wv("V-KHBIS")
    if kh_name:
        stationaer = f"vom {kh_von} bis zum {kh_bis} stationär " if kh_von and kh_bis else ""
        absaetze.append(_p(
            f"{PP1A} wurde dabei zunächst im {kh_name} aufgenommen "
            f"und {stationaer}behandelt."
        ))

    # Verletzungsdiagnosen
    v1 = wv("VERLETZUNG1")
    v2 = wv("VERLETZUNG2")
    if v1:
        if v2:
            absaetze.append(_p(
                f"Dabei wurden ausweislich des beiliegenden Berichts folgende "
                f"Verletzungen diagnostiziert: {v1}, {v2}."
            ))
        else:
            absaetze.append(_p(
                f"Dabei wurde ausweislich des beiliegenden Berichts folgende "
                f"Verletzung diagnostiziert: {v1}."
            ))

    # Ärzte
    for i in range(1, 4):
        arzt_name    = wv(f"V-ARZT{i}.VNName")
        arzt_strasse = wv(f"V-ARZT{i}.Strasse")
        arzt_ort     = wv(f"V-ARZT{i}.Ort")
        if arzt_name:
            ort_str = ""
            if arzt_strasse and arzt_ort:
                ort_str = f", {arzt_strasse} in {arzt_ort}"
            elif arzt_strasse:
                ort_str = f", {arzt_strasse}"
            absaetze.append(_p(
                f"Die weitere Heilbehandlung findet statt bei {arzt_name}{ort_str}."
            ))

    # Krankschreibung
    if wv("V-HKRANK").lower() == "ja":
        kr_von = wv("V-KRVON")
        kr_bis = wv("V-KRBIS")
        verb   = "war" if kr_bis else "ist"
        if kr_von and kr_bis:
            zeitraum = f" für die Zeit vom {kr_von} bis zum {kr_bis}"
        elif kr_von:
            zeitraum = f" seit dem {kr_von}"
        else:
            zeitraum = ""
        absaetze.append(_p(f"Unser{P1A} Mandant{S1A} {verb}{zeitraum} krankgeschrieben."))

    # Schweigepflichtentbindung
    if wv("ENTBINDUNG").lower() == "ja":
        absaetze.append(_p(
            "Wir verweisen an dieser Stelle auf die beiliegende "
            "Schweigepflichtentbindungserklärung."
        ))
    else:
        absaetze.append(_p(
            "Wir bitten Sie, uns ein Formular zur Schweigepflichtentbindung "
            "zu übersenden, damit wir die ärztlichen Befundberichte einholen können."
        ))

    # Schmerzensgeld (PRD-29: echte Verletzungsdaten wenn vorhanden)
    schmgeld = wv("SCHMGELD")
    sg_mind  = float(schmgeld.replace(".", "").replace(",", ".").replace(" €", "").replace("€", "").strip()) \
               if schmgeld else 0.0
    try:
        sg_mind = float(schmgeld.replace(".", "").replace(",", ".").strip().rstrip("€").strip()) \
                  if schmgeld else 0.0
    except Exception:
        sg_mind = 0.0

    sg_absaetze, _, sg_vgl = _baue_sg_abschnitt(ps_data or {}, gram.get("kl_nom") or "Der Kläger", sg_mind)
    sg_text = " ".join(sg_absaetze)
    if sg_vgl:
        sg_text += f" ({sg_vgl})"
    absaetze.append(_p_last(sg_text))

    return "".join(absaetze)


# ══════════════════════════════════════════════════════════════════════════════
# SCHADENTABELLE
# ══════════════════════════════════════════════════════════════════════════════

def _netto_oder_brutto(schaden: dict, key_netto: str, key_ust: str, key_brutto_fallback: str, vorsteuer: bool) -> float:
    """
    Gibt den korrekten Betrag zurück je nach Vorsteuer-Berechtigung.
    - vorsteuer=True  → netto (key_netto)
    - vorsteuer=False → brutto (key_netto + key_ust, oder key_brutto_fallback)
    Fallback: wenn ust=0 aber netto>0 → brutto_fallback wenn vorhanden, sonst netto * 1.19.
    """
    netto = float(schaden.get(key_netto) or 0)
    ust   = float(schaden.get(key_ust)   or 0)
    brutto_fallback = float(schaden.get(key_brutto_fallback) or 0)

    if vorsteuer:
        # Netto zurückgeben; falls kein Netto: Brutto-Fallback / 1.19 als Näherung
        return netto if netto > 0 else (round(brutto_fallback / 1.19, 2) if brutto_fallback else 0.0)
    else:
        if netto > 0:
            if ust > 0:
                return netto + ust
            # ust fehlt: brutto_fallback nutzen wenn > netto, sonst 19% aufschlagen
            if brutto_fallback > netto:
                return brutto_fallback
            return round(netto * 1.19, 2)
        return brutto_fallback


def _ermittle_abrechnungsart(schaden: dict, vorsteuer: bool = False) -> str:
    """
    PRD-14: Delegiert an berechne_abrechnungsart() in schaden.py.
    Single Source of Truth – lokale Implementierung entfernt.
    Returns: 'fiktiv' | 'konkret' | 'totalschaden'
    """
    return _berechne_abrechnungsart(schaden, vorsteuer=vorsteuer)["abrechnungsart"]


def _baue_tabelle(schaden: dict, body_width: int = 9163, einleitung: str = "", vorsteuer: bool = False) -> tuple:
    def _f(key): return float(schaden.get(key) or 0)

    rep_gut_netto   = _f("rep_gutachten_netto") or _f("reparaturkosten")
    rep_rech_netto  = _f("rep_rechnung_netto")
    rep_rech_brutto = _f("rep_rechnung_brutto")
    wbw = _f("wiederbeschaffung")
    rst = abs(_f("restwert"))
    n_fzg = wbw - rst

    # ── Abrechnungsart ermitteln (explizit gesetzt oder automatisch) ──────────
    art = _ermittle_abrechnungsart(schaden, vorsteuer)

    # ── Fahrzeugschaden-Positionen je Abrechnungsart ──────────────────────────
    if art == "totalschaden":
        fahrzeug = [
            ("Wiederbeschaffungswert", wbw, ""),
            ("abzgl. Restwert", -rst, "rot"),
        ] if wbw > 0 else []

    elif art == "konkret":
        ist_130 = rep_rech_netto > 0 and wbw > 0 and rep_rech_netto > n_fzg and rep_rech_netto <= 1.3 * wbw
        if rep_rech_netto > 0:
            if vorsteuer:
                # Vorsteuerabzugsberechtigt → Nettobetrag maßgeblich
                fahrzeug = [("Reparaturkosten lt. Rechnung (netto)", rep_rech_netto, "")]
            else:
                # Kein Vorsteuerabzug → Bruttobetrag maßgeblich
                betrag_konkret = rep_rech_brutto if rep_rech_brutto > 0 else rep_rech_netto * 1.19
                fahrzeug = [("Reparaturkosten lt. Rechnung (brutto)", betrag_konkret, "")]
        else:
            fahrzeug = []

    else:  # fiktiv
        fahrzeug = [("Reparaturkosten lt. Gutachten (netto)", rep_gut_netto, "")] if rep_gut_netto > 0 else []

    def _nb(key_n, key_u, key_b):
        """Nebenkosten: netto oder brutto je Vorsteuer."""
        return _netto_oder_brutto(schaden, key_n, key_u, key_b, vorsteuer)

    suf = " (netto)" if vorsteuer else " (brutto)"

    # Wertminderung nur bei Reparaturschäden (fiktiv/konkret) – nicht bei Totalschaden
    wertminderung_pos = [] if art == "totalschaden" else [
        ("Merkantile Wertminderung", _f("wertminderung"), ""),
    ]

    positionen = fahrzeug + wertminderung_pos + [
        ("Nutzungsausfallschaden",            _f("nutzungsausfall"),                            ""),
        ("Mietwagenkosten" + suf,            _nb("mietwagenkosten_netto","mietwagenkosten_ust","mietwagenkosten"), ""),
        ("Sachverständigenkosten" + suf,     _nb("sv_kosten_netto",      "sv_kosten_ust",      "sv_kosten"),       ""),
        ("Nachbesichtigungskosten" + suf,    _nb("kostennb",             "kostennb_ust",       "kostennb"),        ""),
        ("Abschleppkosten" + suf,            _nb("abschleppkosten_netto","abschleppkosten_ust","abschleppkosten"), ""),
        ("Standkosten" + suf,                _nb("standkosten_netto",    "standkosten_ust",    "standkosten"),     ""),
        ("An-/Abmeldekosten" + suf,          _nb("anabmeldekosten_netto","anabmeldekosten_ust","anabmeldekosten"), ""),
        ("Schmerzensgeld",              _f("schmerzensgeld"),             ""),
        ("Verdienstausfall",            _f("verdienstausfall"),           ""),
        ("Haushaltsführungsschaden",    _f("haushalt"),                   ""),
        ("Unkostenpauschale",           _f("unkostenpauschale") or 30.0,  ""),  # Default 30,00 €
    ]

    # SQLite-Feld "sonstiges" → als Position wenn > 0
    sonstiges_val  = float(schaden.get("sonstiges") or 0)
    sonstiges_beschr = (schaden.get("sonstiges_beschr") or "Sonstiges").strip() or "Sonstiges"
    if sonstiges_val > 0:
        positionen.append((sonstiges_beschr, sonstiges_val, ""))

    # WDM-Extras (JSON-Array mit zusätzlichen Schadenpositionen aus WDM)
    extras_raw = schaden.get("wdm_extras_json") or "[]"
    try:
        extras = json.loads(extras_raw) if isinstance(extras_raw, str) else (extras_raw or [])
        if not isinstance(extras, list): extras = []
        for ex in extras:
            positionen.append((ex.get("label", "Sonstiges"),
                               float(ex.get("betrag") or ex.get("netto") or 0), ""))
    except Exception:
        pass

    # Zeilen mit 0-Wert filtern, AUSSER explizit gesetzten (z.B. Restwert=0 bei Totalschaden)
    positionen = [(l, v, c) for l, v, c in positionen if v != 0 or c == "rot"]
    gesamt = sum(v for _, v, _ in positionen)

    col_l = int(body_width * 0.75)
    col_r = body_width - col_l

    RPR_NORMAL = (
        '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
        '<w:sz w:val="24"/><w:szCs w:val="24"/>'
    )
    RPR_BOLD        = RPR_NORMAL + '<w:b/><w:color w:val="000000"/>'
    RPR_BOLD_DOUBLE = RPR_NORMAL + '<w:b/><w:color w:val="000000"/>'
    RPR_WHITE       = RPR_BOLD + '<w:color w:val="FFFFFF"/>'

    def _zeile(label: str, wert: float, col_farbe: str = "", rpr: str = RPR_NORMAL, bg: str = "", border: str = "") -> str:
        shd     = f'<w:shd w:val="clear" w:color="auto" w:fill="{bg}"/>' if bg else ""
        tcbdr   = border if border else ""
        ws      = ("- " if wert < 0 else "") + _euro(abs(wert)) if wert != 0 else "0,00\xa0\u20ac"
        rot_tag = '<w:color w:val="C0392B"/>' if col_farbe == "rot" else ""
        rot_rpr = rpr + rot_tag
        return (
            f'<w:tr>'
            f'<w:tc><w:tcPr><w:tcW w:w="{col_l}" w:type="dxa"/>{tcbdr}{shd}</w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            f'<w:r><w:rPr>{rot_rpr}</w:rPr><w:t xml:space="preserve">{_escape_xml(label)}</w:t></w:r></w:p></w:tc>'
            f'<w:tc><w:tcPr><w:tcW w:w="{col_r}" w:type="dxa"/>{tcbdr}{shd}</w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:jc w:val="right"/></w:pPr>'
            f'<w:r><w:rPr>{rot_rpr}</w:rPr><w:t>{_escape_xml(ws)}</w:t></w:r></w:p></w:tc>'
            f'</w:tr>'
        )

    # Header-Zeile: fett schwarz, kein Hintergrund, Unterstreichung
    header = (
        f'<w:tr>'
        f'<w:tc><w:tcPr><w:tcW w:w="{col_l}" w:type="dxa"/></w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
        f'<w:r><w:rPr>{RPR_BOLD}</w:rPr><w:t>Schadenposition</w:t></w:r></w:p></w:tc>'
        f'<w:tc><w:tcPr><w:tcW w:w="{col_r}" w:type="dxa"/></w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
        '<w:jc w:val="right"/></w:pPr>'
        f'<w:r><w:rPr>{RPR_BOLD}</w:rPr><w:t>Betrag</w:t></w:r></w:p></w:tc>'
        f'</w:tr>'
    )

    # Doppelter Rahmen oben + doppelte Unterstreichung für Gesamtschaden-Zeile
    # Gesamtschaden: doppelter Rahmen oben + doppelte Unterstreichung + Trennlinie unten
    border_dbl = (
        '<w:tcBorders>'
        '<w:top    w:val="single" w:sz="4" w:color="000000"/>'
        '<w:bottom w:val="double" w:sz="6" w:color="000000"/>'
        '</w:tcBorders>'
    )
    gesamt_zeile = (
        f'<w:tr>'
        f'<w:tc><w:tcPr><w:tcW w:w="{col_l}" w:type="dxa"/>{border_dbl}</w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
        f'<w:r><w:rPr>{RPR_BOLD_DOUBLE}</w:rPr><w:t>Gesamtschaden</w:t></w:r></w:p></w:tc>'
        f'<w:tc><w:tcPr><w:tcW w:w="{col_r}" w:type="dxa"/>{border_dbl}</w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
        f'<w:jc w:val="right"/></w:pPr>'
        f'<w:r><w:rPr>{RPR_BOLD_DOUBLE}</w:rPr>'
        f'<w:t>{_escape_xml(_euro_force(gesamt))}</w:t></w:r></w:p></w:tc>'
        f'</w:tr>'
    )

    PPR = '<w:pPr><w:jc w:val="both"/></w:pPr>'
    RPR_EINL = '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
    LEER_P = f'<w:p>{PPR}</w:p>'
    einleitung_xml = ""
    if einleitung:
        einleitung_xml = (
            f'<w:p>{PPR}<w:r>{RPR_EINL}'
            f'<w:t xml:space="preserve">{_escape_xml(einleitung)}</w:t>'
            f'</w:r></w:p>'
            + LEER_P
        )

    xml = (
        einleitung_xml
        + f'<w:tbl><w:tblPr><w:tblW w:w="{body_width}" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="none"/><w:left w:val="none"/>'
        '<w:bottom w:val="none"/><w:right w:val="none"/>'
        '<w:insideH w:val="none"/><w:insideV w:val="none"/>'
        '</w:tblBorders></w:tblPr>'
        + header
        + "".join(_zeile(l, v, c) for l, v, c in positionen)
        + gesamt_zeile
        + '</w:tbl>'
        # Leerzeile nach Tabelle
        + f'<w:p><w:pPr><w:jc w:val="both"/></w:pPr></w:p>'
        # Vorbehalt
        + f'<w:p><w:pPr><w:jc w:val="both"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr><w:t xml:space="preserve">Die Geltendmachung weiterer Schadenpositionen bleibt vorbehalten.</w:t></w:r></w:p>'
    )
    return xml, gesamt


# ══════════════════════════════════════════════════════════════════════════════
# HILFSFUNKTIONEN
# ══════════════════════════════════════════════════════════════════════════════

def _lese_textbreite(vorlage: Path) -> int:
    try:
        with zipfile.ZipFile(str(vorlage)) as z:
            doc = z.read('word/document.xml').decode('utf-8')
        pgSz  = re.search(r'<w:pgSz[^/]*/>', doc)
        pgMar = re.search(r'<w:pgMar[^/]*/>', doc)
        if pgSz and pgMar:
            w = int(re.search(r'w:w="(\d+)"', pgSz.group(0)).group(1))
            l = int(re.search(r'w:left="(\d+)"', pgMar.group(0)).group(1))
            r = int(re.search(r'w:right="(\d+)"', pgMar.group(0)).group(1))
            return w - l - r
    except Exception:
        pass
    return 9163


def _escape_xml(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                  .replace(">", "&gt;").replace('"', "&quot;"))


def _euro(wert) -> str:
    v = float(wert or 0)
    if v == 0: return ""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "\u00a0\u20ac"


def _euro_force(wert) -> str:
    v = float(wert or 0)
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "\u00a0\u20ac"


def _datum_deutsch(d: date) -> str:
    m = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
         "Juli", "August", "September", "Oktober", "November", "Dezember"]
    return f"{d.day}. {m[d.month]} {d.year}"


def _unterschrift_bytes(kuerzel: str) -> Optional[bytes]:
    d = Path(_MODUL_DIR) / "unterschriften"
    for k in ([kuerzel.upper()] if kuerzel else []) + ["AS"]:
        for ext in (".png", ".PNG", ".jpg", ".JPG"):
            p = d / f"{k}{ext}"
            if p.exists():
                data = p.read_bytes()
                return _jpeg_zu_png(data) if ext.lower() in (".jpg", ".jpeg") else data
    return None


def _jpeg_zu_png(jpeg: bytes) -> Optional[bytes]:
    try:
        from PIL import Image
        buf = io.BytesIO()
        Image.open(io.BytesIO(jpeg)).save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        logger.warning("JPEG→PNG fehlgeschlagen: %s", e)
        return None


def _hole_sb_info(kuerzel: str) -> dict:
    try:
        from ..ramicro.sachbearbeiter import hole_sachbearbeiter
        return hole_sachbearbeiter(kuerzel)
    except Exception:
        return {"name": "Koch, Schatz & Kollegen", "titel": "Rechtsanwälte"}
