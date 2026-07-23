"""
backend/word/stellungnahme_service.py
=======================================
Generiert eine Stellungnahme zum Abrechnungsschreiben als .docx.

Aufbau:
  1. Briefkopf (forderungsschreiben_vorlage.docx als Stil-Träger)
  2. Empfänger: gegnerische Haftpflichtversicherung (GHPV)
  3. Betreff: Stellungnahme zu den Kürzungen vom [Datum]
  4. Tabelle: Position | Gekürzt um | Gegenargument
  5. Abschlussformel: Zahlungsaufforderung Restbetrag

Wird aufgerufen von stellungnahme_routes.py.

Platzhalter in forderungsschreiben_vorlage.docx:
    {{EMPF_NAME}}             Empfänger-Name (GHPV)
    {{EMPF_STRASSE}}          Empfänger-Straße
    {{EMPF_ORT}}              Empfänger PLZ Ort
    {{EMPF_EMAIL}}            Nur per E-Mail (wenn vorhanden)
    {{AKTENZEICHEN}}          Aktenzeichen mit SB-Kürzel
    {{Aktenkurzbezeichnung}}  Kurzbezeichnung der Akte
    {{DATUM}}                 Datum auf Deutsch
    {{BETREFF1}}              Betreffzeile 1
    {{BETREFF2}}              Betreffzeile 2
    {{BETREFF3}}              Betreffzeile 3 (leer)
    {{ANREDE}}                Briefanrede
    {{VERTRETUNG}}            (leer – kein Auftrag-Block nötig)
    {{AUFTRAG}}               (leer)
    {{SCHADENTABELLE}}        OOXML-Block: Kürzungstabelle
    {{VERLETZUNGSBLOCK}}      (leer)
    {{GRUSSFORMEL}}           OOXML-Block: Abschluss + Zahlungsaufforderung
"""

import io
import logging
import os
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MODUL_DIR = os.path.dirname(__file__)
_VORLAGE   = Path(_MODUL_DIR) / "forderungsschreiben_vorlage.docx"

_SIG_RID   = "rId18"
_SIG_MEDIA = "word/media/image2.png"


# ── Hilfsfunktionen (identisch zu forderungsschreiben_wv.py) ─────────────────

def _escape_xml(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
                  .replace(">", "&gt;").replace('"', "&quot;"))


def _datum_deutsch(d: date) -> str:
    m = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
         "Juli", "August", "September", "Oktober", "November", "Dezember"]
    return f"{d.day}. {m[d.month]} {d.year}"


# ── Textbaustein-Replacement ──────────────────────────────────────────────────

def ersetze_platzhalter(text, kontext: dict):
    """
    Ersetzt <PLATZHALTER> im Text mit Werten aus kontext.
    Unbekannte Platzhalter werden als [FEHLT: <XYZ>] markiert.
    """
    if not text:
        return text
    for key, value in kontext.items():
        text = text.replace(f"<{key}>", str(value) if value else "")
    text = re.sub(r"<([A-Z_]+)>", r"[FEHLT: <\1>]", text)
    return text


def _baue_kontext(az: str, akte_daten, beteiligte: list) -> dict:
    """Baut das Platzhalter-Kontext-Dict aus Aktendaten."""
    mandant = next(
        (b for b in (beteiligte or []) if getattr(b, "rolle", "") == "mandant"),
        None,
    )
    versicherung = next(
        (b for b in (beteiligte or [])
         if getattr(b, "rolle", "") in ("ghpv", "versicherung", "haftpflicht")),
        None,
    )

    def _name(b) -> str:
        if not b:
            return ""
        vn = getattr(b, "vorname", "") or ""
        nn = getattr(b, "name", "") or getattr(b, "nachname", "") or ""
        return f"{vn} {nn}".strip() or nn

    schaden = getattr(akte_daten, "schaden", None) or {}
    if isinstance(schaden, dict):
        _s = lambda k: str(schaden.get(k) or "")
    else:
        _s = lambda k: str(getattr(schaden, k, "") or "")

    return {
        "MANDANT":      _name(mandant),
        "AZ":           az,
        "VERSICHERER":  _name(versicherung),
        "DATUM":        date.today().strftime("%d.%m.%Y"),
        "KFZ":          getattr(akte_daten, "kfz_kennzeichen", "") or "",
        # RA-MICRO Platzhalter aus den importierten Textbausteinen
        "RGGDAT":       "",   # Datum Regulierungsschreiben – wird aus abrechnungsschreiben befüllt
        "GUTACHTER":    "",   # Name SV – aus beteiligte (rolle=gutachter)
        "FKLASSE":      _s("fklasse"),
        "NUTZUNGSA":    _s("nutzungsausfall_betrag"),
        "NABETRAG":     _s("nutzungsausfall_tagessatz"),
        "REPDAUER":     _s("reparaturdauer"),
        "KOSTENNB":     _s("kostennb"),
        "SCHMGELD":     _s("schmerzensgeld"),
        "SGVORSCHUSS":  _s("schmerzensgeld_vorschuss"),
    }


def _aggregiere_kuerzungen(abrechnungen: list) -> tuple[list, float]:
    """
    Aggregiert Kürzungspositionen über alle Abrechnungen.
    Gibt (kuerzungen_liste, restbetrag) zurück.
    """
    kuerzung_by_art: dict = {}
    restbetrag = 0.0

    for ab in (abrechnungen or []):
        positionen = (getattr(ab, "positionen", None)
                      or (ab.get("positionen") if isinstance(ab, dict) else None)
                      or [])
        for pos in positionen:
            pos_dict = (pos if isinstance(pos, dict)
                        else vars(pos) if hasattr(pos, "__dict__") else {})
            betrag_gef = float(pos_dict.get("betrag_gefordert") or 0)
            betrag_reg = float(pos_dict.get("betrag_reguliert") or 0)
            kuerzung   = round(betrag_gef - betrag_reg, 2)
            if kuerzung <= 0.005:
                continue

            restbetrag += kuerzung

            ka_id  = pos_dict.get("kuerzungsart_id")
            ka_bez = pos_dict.get("kuerzungsart_bezeichnung") or ""
            ka_arg = (
                pos_dict.get("textbaustein")
                or pos_dict.get("kuerzungsart_textbaustein")
                or pos_dict.get("standard_gegenargument")
                or pos_dict.get("kuerzungsart_standard_gegenargument")
                or ""
            )
            pos_key   = pos_dict.get("position_key") or "sonstiges"
            pos_label = pos_dict.get("position_label") or pos_key.replace("_", " ").title()
            gruppe_key = f"ka_{ka_id}" if ka_id else f"pos_{pos_key}"

            if gruppe_key not in kuerzung_by_art:
                kuerzung_by_art[gruppe_key] = {
                    "_gruppe_key":            gruppe_key,
                    "kuerzungsart_id":        ka_id,
                    "bezeichnung":            ka_bez or pos_label,
                    "label":                  ka_bez or pos_label,
                    "standard_gegenargument": ka_arg,
                    "kuerzung_gesamt":        0.0,
                    "positionen":             [],
                    "_zitate":                [],
                }
            kuerzung_by_art[gruppe_key]["kuerzung_gesamt"] += kuerzung
            kuerzung_by_art[gruppe_key]["positionen"].append(pos_label)
            zitat = (pos_dict.get("kuerzung_freitext") or "").strip()
            if zitat:
                kuerzung_by_art[gruppe_key]["_zitate"].append(zitat)

    kuerzungen = list(kuerzung_by_art.values())
    for k in kuerzungen:
        posis = list(dict.fromkeys(k["positionen"]))
        if len(posis) > 1:
            k["label"] = k["bezeichnung"] + f" ({', '.join(posis)})"
        k["begruendung_roh"] = " / ".join(dict.fromkeys(k.pop("_zitate")))

    return kuerzungen, restbetrag


def _euro(wert) -> str:
    v = float(wert or 0)
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "\u00a0\u20ac"


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


# ── XML-Bausteine ─────────────────────────────────────────────────────────────

def _p(text: str, fett: bool = False, center: bool = False,
       einzug: bool = False, size: int = 24) -> str:
    """Einfacher Absatz in Arial."""
    jc  = '<w:jc w:val="center"/>' if center else '<w:jc w:val="both"/>'
    ind = '<w:ind w:left="720"/>' if einzug else ""
    ppr = f'<w:pPr>{jc}{ind}</w:pPr>'
    b   = "<w:b/><w:bCs/>" if fett else ""
    sz  = f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>'
    rpr = f'<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>{b}{sz}</w:rPr>'
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{_escape_xml(text)}</w:t></w:r></w:p>'


def _lz() -> str:
    return '<w:p><w:pPr><w:jc w:val="both"/></w:pPr></w:p>'


def _xml_kuerzungstabelle(
    kuerzungen: list,
    kontext: dict | None = None,
    custom_texte: dict | None = None,
) -> str:
    """
    Baut die Kürzungstabelle mit 3 Spalten:
    Schadenposition | Kürzung | Gegenargument
    """
    W_POS  = 3000
    W_BETR = 1400
    W_ARG  = 4763   # Summe: 9163 Twips Gesamtbreite

    def zelle(w: int, text: str, fett: bool = False, align: str = "left") -> str:
        b  = "<w:b/><w:bCs/>" if fett else ""
        al = f'<w:jc w:val="{align}"/>' if align != "left" else ""
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr>{al}</w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
            f'<w:sz w:val="22"/><w:szCs w:val="22"/>{b}</w:rPr>'
            f'<w:t xml:space="preserve">{_escape_xml(text)}</w:t></w:r></w:p></w:tc>'
        )

    def zeile(pos: str, betrag: str, argument: str, fett: bool = False) -> str:
        return (
            f'<w:tr>'
            f'{zelle(W_POS,  pos,      fett)}'
            f'{zelle(W_BETR, betrag,   fett, "right")}'
            f'{zelle(W_ARG,  argument, fett)}'
            f'</w:tr>'
        )

    tbl_props = (
        '<w:tbl>'
        '<w:tblPr>'
        '<w:tblStyle w:val="Tabellenraster"/>'
        '<w:tblW w:w="9163" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:left w:val="none"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:right w:val="none"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="AAAAAA"/>'
        '<w:insideV w:val="none"/>'
        '</w:tblBorders>'
        '</w:tblPr>'
    )

    reihen = [zeile("Schadenposition", "Kürzung", "Rechtliche Erwiderung", fett=True)]
    gesamt_kuerzung = 0.0

    for k in kuerzungen:
        betrag = float(k.get("kuerzung_gesamt") or 0)
        gesamt_kuerzung += betrag
        gruppe_key = k.get("_gruppe_key", "")
        raw_text = (
            (custom_texte or {}).get(gruppe_key)
            or k.get("standard_gegenargument")
            or "Die Kürzung ist nicht gerechtfertigt."
        )
        argument = ersetze_platzhalter(
            raw_text,
            {**(kontext or {}), "ZITAT": k.get("begruendung_roh") or ""})
        reihen.append(zeile(
            k.get("label") or k.get("bezeichnung") or "Position",
            f"−{_euro(betrag)}",
            argument,
        ))

    reihen.append(zeile("Gesamte Kürzung", f"−{_euro(gesamt_kuerzung)}", "", fett=True))

    return tbl_props + "".join(reihen) + '</w:tbl>'


def _xml_grussformel(restbetrag: float, versicherung: str, az_versicherung: str) -> str:
    """
    Abschluss: Zahlungsaufforderung + Grußformel.
    """
    blocks = []
    blocks.append(_lz())
    blocks.append(_p(
        "Wir weisen die vorgenommenen Kürzungen aus den vorstehend dargelegten Gründen "
        "vollumfänglich zurück und fordern Sie auf, den noch ausstehenden Restbetrag in Höhe von",
    ))
    blocks.append(_lz())
    blocks.append(_p(_euro(restbetrag), fett=True, center=True))
    blocks.append(_lz())
    # Referenznummer wenn vorhanden
    if az_versicherung:
        blocks.append(_p(
            f"unter Angabe Ihres Aktenzeichens {az_versicherung} innerhalb von 14 Tagen "
            "auf unser Kanzleikonto zu überweisen."
        ))
    else:
        blocks.append(_p(
            "innerhalb von 14 Tagen auf unser Kanzleikonto zu überweisen."
        ))
    blocks.append(_lz())
    blocks.append(_p(
        "Wir bitten Sie, die Zahlung fristgerecht vorzunehmen. "
        "Andernfalls behalten wir uns vor, unsere Mandantschaft gerichtlich zu vertreten."
    ))
    blocks.append(_lz())
    blocks.append(_p("Mit freundlichen Grüßen"))
    blocks.append(_lz())
    blocks.append(_lz())
    return "".join(blocks)


# ── Platzhalter-Helpers (1:1 aus forderungsschreiben_wv.py) ──────────────────

def _merge_split_placeholders(xml: str, placeholders: list) -> str:
    for ph in placeholders:
        if ph in xml:
            continue

        def _fix_para(m):
            para = m.group(0)
            if '<w:drawing>' in para or '<w:pict>' in para:
                return para
            texte  = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para)
            gesamt = "".join(texte)
            if ph not in gesamt:
                return para
            count = [0]

            def _ersetze_t(tm):
                count[0] += 1
                if count[0] == 1:
                    return f'<w:t xml:space="preserve">{gesamt}</w:t>'
                return '<w:t></w:t>'

            return re.sub(r'<w:t[^>]*>[^<]*</w:t>', _ersetze_t, para)

        xml = re.sub(r'<w:p[ >](?:(?!</w:p>).)*</w:p>', _fix_para, xml, flags=re.DOTALL)
    return xml


def _inject_block(xml: str, placeholder: str, block_xml: str) -> str:
    ph_esc = re.escape(placeholder)
    return re.sub(
        r'<w:p[ >](?:(?!</w:p>).)*' + ph_esc + r'(?:(?!</w:p>).)*</w:p>',
        block_xml,
        xml,
        flags=re.DOTALL,
    )


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
                for placeholder, block_xml in ooxml_blocks.items():
                    xml = _inject_block(xml, placeholder, block_xml)
                data = xml.encode("utf-8")

            elif item.filename == _SIG_MEDIA and unterschrift:
                data = unterschrift

            zout.writestr(item, data)

    return output.getvalue()


# ── Haupt-Funktion ────────────────────────────────────────────────────────────

def generiere_stellungnahme(
    az: str,
    akte_daten,
    beteiligte: list,
    abrechnungen: list,
    custom_texte: dict | None = None,
) -> bytes:
    """
    Generiert die Stellungnahme zum Abrechnungsschreiben als DOCX-Bytes.

    Args:
        az:           Aktenzeichen (az TEXT aus unfallakte)
        akte_daten:   Objekt oder dict mit Feldern az, aktenzeichen, sachbearbeiter etc.
        beteiligte:   Liste der Beteiligten (aus hole_beteiligte_by_akte)
        abrechnungen: Liste der Abrechnungsschreiben (aus hole_abrechnungsschreiben_by_akte)
    """
    if not _VORLAGE.exists():
        raise FileNotFoundError(f"Vorlage fehlt: {_VORLAGE}")

    heute = date.today()

    # ── Aktenzeichen + SB ────────────────────────────────────────────────────
    sb_kuerzel   = getattr(akte_daten, "sachbearbeiter", None) or (akte_daten.get("sachbearbeiter") if isinstance(akte_daten, dict) else None) or ""
    kurzb        = getattr(akte_daten, "kurzbezeichnung", None) or (akte_daten.get("kurzbezeichnung") if isinstance(akte_daten, dict) else None) or az
    sb           = _hole_sb_info(sb_kuerzel)
    unterschrift = _unterschrift_bytes(sb_kuerzel)

    az_mit_sb = (
        az + sb_kuerzel
        if sb_kuerzel and not az.upper().endswith(sb_kuerzel.upper())
        else az
    )

    # ── GHPV-Daten (Empfänger) ────────────────────────────────────────────────
    # Reihenfolge: GHPV → GHV → GBEV → Beteiligter mit rolle=gegner
    ghpv = None
    for b in (beteiligte or []):
        kuerzel = (getattr(b, "kuerzel", None) or "").upper()
        if kuerzel in ("GHPV", "GHV", "GBEV"):
            ghpv = b
            break
    if not ghpv:
        for b in (beteiligte or []):
            if getattr(b, "rolle", "") == "gegner":
                ghpv = b
                break

    def _bget(obj, *felder):
        for f in felder:
            v = getattr(obj, f, None) if obj else None
            if v:
                return v
        return ""

    empf_name    = _bget(ghpv, "versicherung", "firma", "name") or "Gegnerische Haftpflichtversicherung"
    empf_strasse = _bget(ghpv, "strasse", "anschrift") or ""
    empf_plz     = _bget(ghpv, "plz") or ""
    empf_ort     = _bget(ghpv, "ort") or ""
    empf_plz_ort = f"{empf_plz} {empf_ort}".strip()
    empf_email   = _bget(ghpv, "email") or ""
    empf_email_str = f"Nur per E-Mail an {empf_email}" if empf_email else ""

    # Anrede
    anrede = "Sehr geehrte Damen und Herren,"

    # ── Kürzungsdaten aufbereiten ─────────────────────────────────────────────
    # Versicherungs-AZ aus letzter Abrechnung
    az_versicherung = ""
    datum_letzte_ab = ""
    if abrechnungen:
        letzte = abrechnungen[0]
        az_versicherung = getattr(letzte, "referenz_nr", None) or (letzte.get("referenz_nr") if isinstance(letzte, dict) else "") or ""
        datum_letzte_ab = getattr(letzte, "datum", None) or (letzte.get("datum") if isinstance(letzte, dict) else "") or ""

    # Formatierung Datum Abrechnungsschreiben für Betreff
    datum_betreff = ""
    if datum_letzte_ab:
        try:
            teile = datum_letzte_ab.split("-")
            if len(teile) == 3:
                datum_betreff = f"{teile[2]}.{teile[1]}.{teile[0]}"
            else:
                datum_betreff = datum_letzte_ab
        except Exception:
            datum_betreff = datum_letzte_ab

    # Alle Positionen mit Kürzung über alle Abrechnungen aggregieren
    kuerzungen, restbetrag = _aggregiere_kuerzungen(abrechnungen)
    kontext = _baue_kontext(az, akte_daten, beteiligte)

    # ── Betreff ───────────────────────────────────────────────────────────────
    mandant_name = ""
    for b in (beteiligte or []):
        if getattr(b, "rolle", "") == "mandant":
            vn = getattr(b, "vorname", "") or ""
            nn = getattr(b, "name", "") or getattr(b, "nachname", "") or ""
            mandant_name = f"{vn} {nn}".strip() or nn
            break

    betreff1 = f"Unfall – {mandant_name}" if mandant_name else f"Aktenzeichen: {az}"
    betreff2 = f"Ihre Ref.: {az_versicherung}" if az_versicherung else ""
    betreff3_txt = f"Stellungnahme zu Ihren Kürzungen"
    if datum_betreff:
        betreff3_txt += f" vom {datum_betreff}"

    # Wenn nur 2 Betreffzeilen: Stellungnahme auf Zeile 2
    if not betreff2:
        betreff2 = betreff3_txt
        betreff3_txt = ""

    # ── OOXML-Blöcke ─────────────────────────────────────────────────────────
    if kuerzungen:
        tabelle_xml = _xml_kuerzungstabelle(kuerzungen, kontext, custom_texte)
    else:
        tabelle_xml = _p("Keine Kürzungen erfasst.")

    grussformel_xml = _xml_grussformel(restbetrag, empf_name, az_versicherung)

    # ── Platzhalter-Map ───────────────────────────────────────────────────────
    replacements = {
        "{{EMPF_NAME}}":            _escape_xml(empf_name),
        "{{EMPF_STRASSE}}":         _escape_xml(empf_strasse),
        "{{EMPF_ORT}}":             _escape_xml(empf_plz_ort),
        "{{EMPF_EMAIL}}":           _escape_xml(empf_email_str),
        "{{AKTENZEICHEN}}":         _escape_xml(az_mit_sb),
        "{{Aktenkurzbezeichnung}}": _escape_xml(kurzb),
        "{{DATUM}}":                _escape_xml(_datum_deutsch(heute)),
        "{{BETREFF1}}":             _escape_xml(betreff1),
        "{{BETREFF2}}":             _escape_xml(betreff2),
        "{{BETREFF3}}":             _escape_xml(betreff3_txt),
        "{{ANREDE}}":               _escape_xml(anrede),
        "{{VERTRETUNG}}":           "",
        "{{AUFTRAG}}":              "",
        "{{SB_NAME}}":              _escape_xml(sb.get("name", "")),
        "{{SB_TITEL}}":             _escape_xml(sb.get("titel", "")),
    }

    ooxml_blocks = {
        "{{SCHADENTABELLE}}":   tabelle_xml,
        "{{VERLETZUNGSBLOCK}}": "",
        "{{GRUSSFORMEL}}":      grussformel_xml,
    }

    logger.info(
        "Stellungnahme generiert: AZ=%s SB=%s GHPV=%s Kürzungen=%d Restbetrag=%.2f",
        az, sb_kuerzel, empf_name, len(kuerzungen), restbetrag,
    )

    return _render_docx(_VORLAGE, replacements, ooxml_blocks, unterschrift)


def dateiname_generieren(az: str) -> str:
    sicheres_az = az.replace("/", "-").replace("\\", "-").strip()
    return f"{sicheres_az}_stellungnahme_{date.today().isoformat()}.docx"
