"""
Gebührenassistent Word-Generator – PRD-28
==========================================
Erstellt eine Kostennote als DOCX auf Basis von forderungsschreiben_vorlage.docx.
Briefkopf, Schrift und Layout sind dadurch identisch mit dem Forderungsschreiben.

Platzhalter die befüllt werden:
  {{EMPF_NAME}}, {{EMPF_STRASSE}}, {{EMPF_ORT}}, {{EMPF_EMAIL}}
  {{AKTENZEICHEN}}, {{Aktenkurzbezeichnung}}, {{DATUM}}
  {{BETREFF1}}, {{BETREFF2}}, {{BETREFF3}}
  {{ANREDE}}, {{VERTRETUNG}}, {{AUFTRAG}}
  {{SCHADENTABELLE}}   → RVG-Gebührentabelle (OOXML)
  {{VERLETZUNGSBLOCK}} → Begründung + Leitentscheidung (OOXML)
  {{GRUSSFORMEL}}      → Abschluss mit Unterschriftsbild (OOXML)
"""

import logging
import os
import uuid
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_MODUL_DIR  = os.path.dirname(__file__)
_VORLAGE    = Path(_MODUL_DIR) / "forderungsschreiben_vorlage.docx"
_UPLOAD_DIR = os.environ.get("UPLOAD_DIR", str(Path(_MODUL_DIR).parent / "uploads"))

# Signatur-Drawing-XML (identisch mit forderungsschreiben_wv.py → rId18)
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


def generiere_kostennote(akte_id, gb_row):
    # type: (str, dict) -> dict
    """
    Generiert die Kostennote als DOCX auf Basis der Forderungsschreiben-Vorlage.

    gb_row: Zeile aus gebuehren_berechnung
    Returns: { "dateiname": "...", "dok_id": ... }
    """
    from ..db.database import get_connection
    from ..models.dokument import registriere_dokument
    from ..word.klage_service import berechne_rvg
    from ..services.gebuehren_service import VU_REGELN
    from ..ramicro.sachbearbeiter import hole_sachbearbeiter
    from ..word.forderungsschreiben_wv import _render_docx, _unterschrift_bytes, _mandant_anrede_nominativ

    # ── Akte-Daten laden ──────────────────────────────────────────────────────
    with get_connection() as conn:
        akte_row = conn.execute(
            "SELECT az, unfalldatum, kurzbezeichnung, sachbearbeiter "
            "FROM unfallakte WHERE az = ?",
            (akte_id,)
        ).fetchone()

        mandant = conn.execute(
            "SELECT vorname, name, firma, anrede, anschrift, plz, ort FROM beteiligte "
            "WHERE akte_id = ? AND rolle = 'mandant' LIMIT 1",
            (akte_id,)
        ).fetchone()

        # Streitwert: bevorzugt forderung_positionen, Fallback schadenpositionen
        fw = conn.execute(
            "SELECT SUM(betrag_gefordert) as s FROM forderung_positionen WHERE akte_id = ?",
            (akte_id,)
        ).fetchone()
        streitwert = float(fw["s"] or 0) if fw else 0.0

        if streitwert == 0.0:
            sp = conn.execute(
                """SELECT COALESCE(rep_rechnung_brutto, rep_gutachten_netto, 0)
                          + COALESCE(wiederbeschaffung, 0) - COALESCE(restwert, 0)
                          + COALESCE(wertminderung, 0) + COALESCE(nutzungsausfall, 0)
                          + COALESCE(mietwagenkosten, 0) + COALESCE(sv_kosten, 0)
                          + COALESCE(schmerzensgeld, 0) + COALESCE(verdienstausfall, 0)
                          + COALESCE(unkostenpauschale, 0) as summe
                   FROM schadenpositionen WHERE akte_id = ?""",
                (akte_id,)
            ).fetchone()
            if sp:
                streitwert = float(sp["summe"] or 0)

    az          = akte_row["az"] if akte_row else akte_id
    kurzb       = (akte_row["kurzbezeichnung"] if akte_row else "") or az
    unfalldatum = (akte_row["unfalldatum"] if akte_row else "") or ""
    sb_kuerzel  = (akte_row["sachbearbeiter"] if akte_row else "") or ""

    # Sachbearbeiter-Infos + Unterschriftsbild
    try:
        sb = hole_sachbearbeiter(sb_kuerzel)
    except Exception:
        sb = {"name": "Koch, Schatz & Kollegen", "titel": "Rechtsanwälte"}
    unterschrift = _unterschrift_bytes(sb_kuerzel)

    mandant_name = ""
    empf_name    = ""
    empf_str     = ""
    empf_plz_ort = ""
    anrede       = "Sehr geehrte Damen und Herren,"
    if mandant:
        m_anrede_str = (mandant["anrede"] or "").strip()
        m_vorname    = (mandant["vorname"] or "").strip()
        m_nachname   = (mandant["name"]    or "").strip()
        m_firma      = (mandant["firma"]   or "").strip()
        _ist_firma   = m_anrede_str in ("4", "firma") or (not m_vorname and m_firma)

        if _ist_firma:
            empf_name    = m_firma or m_nachname
            anrede       = "Sehr geehrte Damen und Herren,"
        else:
            anrede_nom   = _mandant_anrede_nominativ(dict(mandant))
            empf_name    = " ".join(filter(None, [anrede_nom, m_vorname, m_nachname]))
            if anrede_nom == "Herr":
                anrede = f"Sehr geehrter Herr {m_nachname},"
            elif anrede_nom == "Frau":
                anrede = f"Sehr geehrte Frau {m_nachname},"
            elif empf_name:
                anrede = f"Sehr geehrte/r {empf_name},"

        mandant_name = " ".join(filter(None, [m_vorname, m_nachname])) or m_firma
        empf_str     = (mandant["anschrift"] or "").strip()
        empf_plz_ort = " ".join(filter(None, [mandant["plz"], mandant["ort"]]))

    vuregel_id       = gb_row.get("vuregel_id") or "VU-01"
    faktor_final     = float(gb_row.get("faktor_final") or gb_row.get("faktor_vorschlag") or 1.3)
    begruendung_text = gb_row.get("begruendung") or ""

    # Leitentscheidung aus VU_REGELN nachschlagen
    leitentscheidung = next(
        (r["leitentscheidung"] for r in VU_REGELN if r["id"] == vuregel_id),
        "BGH VI ZR 273/11"
    )

    rvg = berechne_rvg(streitwert, faktor_final)
    rvg["streitwert"] = streitwert

    heute    = date.today()
    betreff1 = f"Kostennote \u2013 {mandant_name}" if mandant_name else "Kostennote"
    betreff2 = f"Unfall vom {unfalldatum}" if unfalldatum else ""

    # ── Platzhalter-Map ───────────────────────────────────────────────────────
    replacements = {
        "{{EMPF_NAME}}":            _esc(empf_name),
        "{{EMPF_STRASSE}}":         _esc(empf_str),
        "{{EMPF_ORT}}":             _esc(empf_plz_ort),
        "{{EMPF_EMAIL}}":           "",
        "{{AKTENZEICHEN}}":         _esc(az),
        "{{Aktenkurzbezeichnung}}": _esc(kurzb),
        "{{DATUM}}":                _esc(_datum_deutsch(heute)),
        "{{BETREFF1}}":             _esc(betreff1),
        "{{BETREFF2}}":             _esc(betreff2),
        "{{BETREFF3}}":             "",
        "{{ANREDE}}":               _esc(anrede),
        "{{VERTRETUNG}}":           _esc(
            "wir bringen die Angelegenheit zum Abschluss und erlauben uns, "
            "unsere Geb\u00fchren wie folgt abzurechnen:"
        ),
        "{{AUFTRAG}}":              "",
    }

    ooxml_blocks = {
        "{{SCHADENTABELLE}}":   _xml_rvg_tabelle(rvg, faktor_final),
        "{{VERLETZUNGSBLOCK}}": _xml_begruendung(begruendung_text, leitentscheidung,
                                                  vuregel_id, faktor_final),
        "{{GRUSSFORMEL}}":      _xml_grussformel(az, sb["name"], sb["titel"]),
    }

    # _render_docx aus forderungsschreiben_wv.py — verwaltet Signatur-Injection (rId18)
    doc_bytes = _render_docx(_VORLAGE, replacements, ooxml_blocks, unterschrift)

    # ── Speichern ─────────────────────────────────────────────────────────────
    dateiname  = f"Kostennote_{az.replace('/', '-')}_{heute.isoformat()}.docx"
    upload_dir = Path(_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    pfad = upload_dir / f"{uuid.uuid4().hex}_{dateiname}"
    pfad.write_bytes(doc_bytes)

    dok_id = None
    try:
        dok = registriere_dokument(
            akte_id=akte_id, typ="sonstiges",
            dateiname=dateiname, dateipfad=str(pfad),
            bearbeiter_id=None,
            dateityp="docx", dateigroesse=len(doc_bytes),
        )
        dok_id = dok.id
    except Exception as e:
        logger.warning("Kostennote DB-Registrierung: %s", e)

    return {"dateiname": dateiname, "dok_id": dok_id,
            "pfad": str(pfad), "groesse": len(doc_bytes)}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _datum_deutsch(d):
    monate = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
              "Juli", "August", "September", "Oktober", "November", "Dezember"]
    return f"{d.day}. {monate[d.month]} {d.year}"


def _esc(text):
    return str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _eur(betrag):
    return f"{float(betrag or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + "\u00a0\u20ac"


_PPR  = '<w:pPr><w:jc w:val="both"/></w:pPr>'
_RPR  = ('<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
         '<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>')
_RPRB = ('<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
         '<w:sz w:val="24"/><w:szCs w:val="24"/><w:b/><w:bCs/></w:rPr>')
_RPRI = ('<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
         '<w:sz w:val="22"/><w:szCs w:val="22"/><w:i/><w:iCs/></w:rPr>')
_LEER = f'<w:p>{_PPR}</w:p>'


def _xml_rvg_tabelle(rvg, faktor_final):
    """OOXML-Gebührentabelle für Nr. 2300 VV RVG."""
    def _zelle(breite, text, align="left", fett=False, trennlinie=False):
        al  = f'<w:jc w:val="{align}"/>' if align != "left" else ""
        rpr = _RPRB if fett else _RPR
        # Optionale untere Trennlinie auf Zellebene (für Zwischensumme)
        tcbdr = (
            '<w:tcBdr>'
            '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>'
            '</w:tcBdr>'
        ) if trennlinie else ""
        return (f'<w:tc><w:tcPr><w:tcW w:w="{breite}" w:type="dxa"/>{tcbdr}</w:tcPr>'
                f'<w:p><w:pPr>{al}</w:pPr>'
                f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'
                f'</w:p></w:tc>')

    def _zeile(links, rechts, fett=False, trennlinie=False):
        return (f'<w:tr>'
                f'{_zelle(7000, links, fett=fett, trennlinie=trennlinie)}'
                f'{_zelle(2163, rechts, align="right", fett=fett, trennlinie=trennlinie)}'
                f'</w:tr>')

    faktor_str = str(faktor_final).replace(".", ",")
    streitwert = rvg.get("streitwert", 0)

    return (
        '<w:tbl>'
        '<w:tblPr>'
        '<w:tblStyle w:val="Tabellenraster"/>'
        '<w:tblW w:w="9163" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top    w:val="none"/>'
        '<w:left   w:val="none"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/>'
        '<w:right  w:val="none"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="AAAAAA"/>'
        '<w:insideV w:val="none"/>'
        '</w:tblBorders>'
        '</w:tblPr>'
        + _zeile(f"Gegenstandswert: {_eur(streitwert)}", "", fett=True)
        + _zeile(f"Gesch\u00e4ftsgeb\u00fchr \u00a7\u00a7 13, 14, Nr. 2300 VV RVG  \u00d7  {faktor_str}",
                 _eur(rvg.get("gebuehr_netto", 0)))
        + _zeile("Pauschale Post und Telekommunikation Nr. 7002 VV RVG",
                 _eur(rvg.get("post_pauschale", 0)))
        + _zeile("Zwischensumme netto", _eur(rvg.get("zwischen_netto", 0)),
                 trennlinie=True)
        + _zeile("19\u00a0% Umsatzsteuer", _eur(rvg.get("ust", 0)))
        + _zeile("Gesamtbetrag", _eur(rvg.get("gesamt", 0)), fett=True)
        + '</w:tbl>'
    )


def _xml_begruendung(begruendung, leitentscheidung, vuregel_id, faktor_final):
    """OOXML-Block: Begründung des Faktors + Leitentscheidung."""
    faktor_str = str(faktor_final).replace(".", ",")

    def _p(text, rpr=None):
        rpr = rpr or _RPR
        return (f'<w:p>{_PPR}'
                f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'
                f'</w:p>')

    einleitung = (f"Der Geb\u00fchrenfaktor von {faktor_str} ergibt sich aus folgenden "
                  f"Umst\u00e4nden des Mandats gem\u00e4\u00df \u00a7 14 Abs. 1 RVG ({vuregel_id}):")

    result = _p(einleitung) + _LEER
    if begruendung:
        result += _p(begruendung) + _LEER
    if leitentscheidung:
        result += _p(f"Leitentscheidung: {leitentscheidung}", rpr=_RPRI)

    return result


def _xml_grussformel(az="", sb_name="Koch, Schatz & Kollegen", sb_titel="Rechtsanw\u00e4lte"):
    """
    Grußformel der Kostennote:
    Zahlungsbitte → Leerzeile → Mit freundlichen Grüßen → Unterschrift → Name → Titel.
    Das Unterschriftsbild referenziert rId18 (wird von _render_docx aus
    forderungsschreiben_wv.py in die ZIP-Datei injiziert).
    """
    def _p(text=""):
        t = f'<w:t xml:space="preserve">{_esc(text)}</w:t>' if text else "<w:t/>"
        return f'<w:p>{_PPR}<w:r>{_RPR}{t}</w:r></w:p>'

    schluss = (
        f"Wir bitten um kurzfristige Zahlung auf unser unten angegebenes Konto "
        f"unter Angabe unseres Aktenzeichens {_esc(az)} im Verwendungszweck."
        if az else
        "Wir bitten um kurzfristige Zahlung auf unser unten angegebenes Konto "
        "unter Angabe unseres Aktenzeichens im Verwendungszweck."
    )

    return (
        _p(schluss)
        + _LEER
        + _p("Mit freundlichen Gr\u00fc\u00dfen")
        + f'<w:p>{_PPR}<w:r><w:rPr><w:noProof/></w:rPr>{_SA_DRAWING_XML}</w:r></w:p>'
        + _p(sb_name)
        + _p(sb_titel)
    )
