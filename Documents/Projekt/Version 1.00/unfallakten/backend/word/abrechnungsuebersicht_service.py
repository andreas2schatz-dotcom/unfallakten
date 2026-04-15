"""
Abrechnungsübersicht Generator
================================
Vorlage: abrechnungsuebersicht_vorlage.docx

4-spaltige Haupttabelle:
  Schadenposition | Geforderter Betrag | Zahlung Gegenseite | Offen

Regulierungsdaten kommen aus akte_daten["abrechnungen"] –
identisch zur Datenstruktur die RegulierungSection / apiAbrechnungen liefert.
Aggregationslogik: Option B – Summe aller Zahlungsinkremente je position_key.

Dateneingabe (akte_daten dict):
  akte:
    az, sachbearbeiter, kurzbezeichnung, aktenbezeichnung
  mandant:
    vorname, name, firma, anschrift/strasse, plz, ort, anrede
    vorsteuer (Y/J/1 = vorsteuerabzugsberechtigt)
  schaden:
    (alle Schadenpositionen – identisch zu forderungsschreiben_wv.py)
    abrechnungsart  ('fiktiv'|'konkret'|'totalschaden')
  abrechnungen:  ← aus DB/API (apiAbrechnungen.liste)
    [
      {
        "datum": "15.01.2026",
        "positionen": [
          {
            "position_key": "sv_kosten",
            "betrag_gefordert": 600.00,
            "betrag_reguliert": 450.00,
          },
          ...
        ]
      }
    ]
    Wenn leer oder nicht übergeben → Spalten 3+4 bleiben leer.
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

# PRD-14: Single Source of Truth
from ..models.schaden import berechne_abrechnungsart as _berechne_abrechnungsart

logger = logging.getLogger(__name__)

_MODUL_DIR = os.path.dirname(__file__)
_VORLAGE   = Path(_MODUL_DIR) / "abrechnungsuebersicht_vorlage.docx"

# ── Farben (identisch zum Briefkopf) ────────────────────────────────────────
_BLAU      = "5488D4"
_ROT       = "C0392B"
_GRAU_HELL = "F5F6F8"
_GRAU_MID  = "EAEDF2"
_KOPF_BG   = "2C3E50"
_SUMME_BG  = "EBF2FB"
_REST_BG   = "D6E8FF"

# ── position_key → Labelmapping (identisch zu SCHADEN_POS_MAP in App.jsx) ───
_POSITION_LABELS = {
    "rep_gutachten_netto":  "Reparaturkosten lt. Gutachten (netto)",
    "rep_rechnung_netto":   "Reparaturkosten lt. Rechnung (netto)",
    "rep_rechnung_brutto":  "Reparaturkosten lt. Rechnung (brutto)",
    "reparaturkosten":      "Reparaturkosten",
    "wiederbeschaffung":    "Wiederbeschaffungswert",
    "restwert":             "Restwert (−)",
    "wertminderung":        "Merkantile Wertminderung",
    "nutzungsausfall":      "Nutzungsausfallschaden",
    "mietwagenkosten":      "Mietwagenkosten",
    "sv_kosten":            "Sachverständigenkosten",
    "abschleppkosten":      "Abschleppkosten",
    "standkosten":          "Standkosten",
    "anabmeldekosten":      "An-/Abmeldekosten",
    "schmerzensgeld":       "Schmerzensgeld",
    "verdienstausfall":     "Verdienstausfall",
    "haushalt":             "Haushaltsführungsschaden",
    "unkostenpauschale":    "Unkostenpauschale",
    "kostenpauschale":      "Unkostenpauschale",
    "sonstiges":            "Sonstiges",
}

# position_keys die Abzugsposten sind (Restwert: höherer Wert = schlechter für Mandant)
_ABZUG_KEYS = {"restwert"}


# ══════════════════════════════════════════════════════════════════════════════
# ÖFFENTLICHE SCHNITTSTELLE
# ══════════════════════════════════════════════════════════════════════════════

def generiere_abrechnungsuebersicht(akte_daten: dict) -> bytes:
    if not _VORLAGE.exists():
        raise FileNotFoundError(f"Vorlage fehlt: {_VORLAGE}")
    return _generiere(akte_daten)


def dateiendung() -> str:
    return "docx"


# ══════════════════════════════════════════════════════════════════════════════
# GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def _generiere(akte_daten: dict) -> bytes:
    akte        = akte_daten.get("akte")        or {}
    mandant     = akte_daten.get("mandant")     or {}
    schaden     = akte_daten.get("schaden")     or {}
    abrechnungen = akte_daten.get("abrechnungen") or []

    sb_kuerzel = akte.get("sachbearbeiter") or ""
    sb = _hole_sb_info(sb_kuerzel)

    # ── Mandant → Fensterbereich ──────────────────────────────────────────
    m_vorname    = (mandant.get("vorname")   or "").strip()
    m_nachname   = (mandant.get("name")      or "").strip()
    m_firma      = (mandant.get("firma")     or "").strip()
    m_anschrift  = (mandant.get("anschrift") or mandant.get("strasse") or "").strip()
    m_plz_ort    = " ".join(filter(None, [mandant.get("plz"), mandant.get("ort")])).strip()
    m_anrede_str = (mandant.get("anrede")    or "").strip()
    _ist_firma   = m_anrede_str in ("4", "firma") or (not m_vorname and m_firma)
    empf_name    = (m_firma or m_nachname or "MANDANT UNBEKANNT") if _ist_firma else \
                   " ".join(filter(None, [_anrede_text(m_anrede_str), m_vorname, m_nachname])) or "MANDANT UNBEKANNT"

    # ── Metadaten ─────────────────────────────────────────────────────────
    az       = akte.get("aktenzeichen") or akte.get("az") or "—"
    kurzb    = akte.get("kurzbezeichnung") or akte.get("aktenbezeichnung") or az
    heute    = date.today()
    vorsteuer = str(mandant.get("vorsteuer") or "N").strip().upper() in ("Y", "J", "JA", "1", "TRUE")

    # ── Regulierungsstand aus Abrechnungen aggregieren ────────────────────
    # Option B: Summe aller Zahlungsinkremente je position_key
    pos_map = _baue_pos_map(abrechnungen)

    # ── Letztes Abrechnungsdatum ──────────────────────────────────────────
    letztes_datum = ""
    if abrechnungen:
        # Datum aus dem neuesten Eintrag (nach Datum sortiert)
        def _parse_ab_datum(ab):
            d = ab.get("datum") or ""
            # ISO (YYYY-MM-DD) oder DD.MM.YYYY
            try:
                from datetime import datetime as _dt
                if len(d) == 10 and d[4] == "-":
                    return _dt.strptime(d, "%Y-%m-%d")
                elif len(d) == 10 and d[2] == ".":
                    return _dt.strptime(d, "%d.%m.%Y")
            except Exception:
                pass
            return None
        datierte = [(ab, _parse_ab_datum(ab)) for ab in abrechnungen]
        datierte = [(ab, dt) for ab, dt in datierte if dt is not None]
        if datierte:
            neuestes_ab, neuestes_dt = max(datierte, key=lambda x: x[1])
            letztes_datum = _datum_deutsch(neuestes_dt.date())
        elif abrechnungen[0].get("datum"):
            letztes_datum = abrechnungen[0]["datum"]

    # ── Unfalldaten: wdm_roh primär, SQLite als Fallback ─────────────────
    gegner  = akte_daten.get("gegner")  or {}
    wdm_roh = akte_daten.get("wdm_roh") or {}

    def _wdm(key): return (wdm_roh.get(key) or "").strip()

    unfallort_raw = _wdm("varU-ORT") or _wdm("varU-ORTSTEIL") or \
                    (akte.get("unfallort") or "").strip()
    unfallort = unfallort_raw or "—"

    unfalltag_raw = _wdm("varU-TAG") or (akte.get("unfalldatum") or "").strip()
    if unfalltag_raw and len(unfalltag_raw) == 10:
        try:
            from datetime import datetime as _dt2
            if unfalltag_raw[4] == "-":
                unfalltag = _datum_deutsch(_dt2.strptime(unfalltag_raw, "%Y-%m-%d").date())
            else:
                unfalltag = _datum_deutsch(_dt2.strptime(unfalltag_raw, "%d.%m.%Y").date())
        except Exception:
            unfalltag = unfalltag_raw
    else:
        unfalltag = unfalltag_raw or "—"

    kz_mandant = _wdm("varM-KZ") or (mandant.get("kfz_kennzeichen") or "").strip() or "—"
    kz_gegner  = _wdm("varG-KZ") or (gegner.get("kfz_kennzeichen")  or "").strip() or "—"

    unfalldaten = {
        "unfallort":  unfallort,
        "unfalltag":  unfalltag,
        "kz_mandant": kz_mandant,
        "kz_gegner":  kz_gegner,
    }

    # ── Body-Inhalt ───────────────────────────────────────────────────────
    bw = _lese_textbreite(_VORLAGE)
    inhalt_xml = _baue_inhalt(kurzb, schaden, pos_map, sb, bw, vorsteuer,
                               letztes_datum, unfalldaten)

    replacements = {
        "{{EMPF_NAME}}":            _esc(empf_name),
        "{{EMPF_STRASSE}}":         _esc(m_anschrift or "KEINE ANSCHRIFT"),
        "{{EMPF_ORT}}":             _esc(m_plz_ort),
        "{{EMPF_EMAIL}}":           "",
        "{{AKTENZEICHEN}}":         _esc(az),
        "{{Aktenkurzbezeichnung}}": _esc(kurzb),
        "{{DATUM}}":                _esc(_datum_deutsch(heute)),
    }
    return _render_docx(_VORLAGE, replacements, {"{{ABRECHNUNGSINHALT}}": inhalt_xml})


# ══════════════════════════════════════════════════════════════════════════════
# POS-MAP: Regulierungsstand je position_key (Option B: Summierung)
# ══════════════════════════════════════════════════════════════════════════════

# Parser-art → kanonischer position_key (spiegelt _ART_TO_POS_KEY in constants.js).
# Notwendig weil der Live-PDF-Import (RegulierungSection) Parser-art-Werte
# direkt als position_key in die DB schreibt, _schadenpositionen_rows() aber
# kanonische Keys erwartet.
_KEY_NORMALISE = {
    "wbw":               "wiederbeschaffung",
    "wbw_netto":         "wiederbeschaffung",
    "wbw_brutto":        "wiederbeschaffung",
    "wba":               "wiederbeschaffung",
    "reparatur_netto":   "rep_gutachten_netto",
    "reparatur_brutto":  "rep_gutachten_netto",
    "reparatur_fiktiv":  "rep_gutachten_netto",
    "kostenpauschale":   "unkostenpauschale",
    "ra_gebuehren":      "sonstiges",
    # fahrzeugschaden bleibt roh – Ziel-Key (rep_gutachten_netto vs.
    # rep_rechnung_netto vs. wiederbeschaffung) hängt von Abrechnungsart ab
    # und kann hier ohne Kontext nicht aufgelöst werden.
}
_WDM_RE = re.compile(r"^sonstiges_wdm_(\d+)$")


def _normalise_key(raw_key: str) -> str:
    m = _WDM_RE.match(raw_key)
    if m:
        return f"extra_wdm_ss{m.group(1)}"
    return _KEY_NORMALISE.get(raw_key, raw_key)


def _baue_pos_map(abrechnungen: list) -> dict:
    """
    Gibt dict: position_key → { "reguliert": float }

    Option B: Jedes Abrechnungsschreiben speichert nur seinen eigenen
    Zahlungsbetrag (Inkrement). Gesamtregulierung je Position = Summe
    aller betrag_reguliert über alle Abrechnungen.
    """
    pos_map = {}
    for ab in abrechnungen:
        for p in (ab.get("positionen") or []):
            raw = p.get("position_key") or p.get("art") or "sonstiges"
            key = _normalise_key(raw)
            reg = p.get("betrag_reguliert")
            if reg is not None:
                reg_f = round(float(reg), 2)
                if key in pos_map:
                    pos_map[key]["reguliert"] = round(pos_map[key]["reguliert"] + reg_f, 2)
                else:
                    pos_map[key] = {"reguliert": reg_f}
    return pos_map


# ══════════════════════════════════════════════════════════════════════════════
# INHALT
# ══════════════════════════════════════════════════════════════════════════════

def _baue_inhalt(kurzb, schaden, pos_map, sb, bw, vorsteuer,
                 letztes_datum="", unfalldaten=None):
    rows = _schadenpositionen_rows(schaden, pos_map, vorsteuer)
    ud = unfalldaten or {}

    teile = []
    teile.append(_titel_block("Abrechnungsübersicht"))
    # Standzeile mit letztem Abrechnungsdatum (kein "in Sachen" mehr)
    stand_text = f"Stand per letztem Abrechnungsschreiben vom: {letztes_datum}" \
                 if letztes_datum else "Stand: noch kein Abrechnungsschreiben erfasst"
    teile.append(_stand_zeile(stand_text))
    # Kein Abstand – direkt Unfalldaten-Tabelle
    teile.append(_unfalldaten_tabelle(
        unfallort  = ud.get("unfallort",  "—"),
        unfalltag  = ud.get("unfalltag",  "—"),
        kz_mandant = ud.get("kz_mandant", "—"),
        kz_gegner  = ud.get("kz_gegner",  "—"),
        bw         = bw,
    ))
    teile.append(_leerzeile(120))
    teile.append(_haupttabelle(rows, bw, hat_regulierung=bool(pos_map)))
    teile.append(_leerzeile(160))
    teile.append(_abschluss(sb))
    return "".join(teile)


# ══════════════════════════════════════════════════════════════════════════════
# SCHADENPOSITIONEN MIT REGULIERUNG
# Jede Zeile enthält:
#   position_key, label, forderung, reguliert (None wenn noch offen), ist_abzug
# ══════════════════════════════════════════════════════════════════════════════

def _schadenpositionen_rows(schaden: dict, pos_map: dict, vorsteuer: bool) -> list:
    """
    Gibt Liste von Dicts zurück:
      key, label, forderung, reguliert (float|None), ist_abzug
    """
    def _f(k): return float(schaden.get(k) or 0)

    art = _ermittle_abrechnungsart(schaden, vorsteuer)

    rep_gut_netto   = _f("rep_gutachten_netto") or _f("reparaturkosten")
    rep_rech_netto  = _f("rep_rechnung_netto")
    rep_rech_brutto = _f("rep_rechnung_brutto")
    wbw = _f("wiederbeschaffung")
    rst = abs(_f("restwert"))

    suf = " (netto)" if vorsteuer else " (brutto)"

    def _nb(kn, ku, kb):
        n = _f(kn); u = _f(ku); b = _f(kb)
        if vorsteuer:
            return n if n > 0 else (round(b / 1.19, 2) if b else 0.0)
        # vorsteuer=False → brutto benötigt
        if n > 0:
            if u > 0:
                return n + u
            # ust fehlt: brutto_fallback wenn > netto, sonst 19% aufschlagen
            return b if b > n else round(n * 1.19, 2)
        return b

    # Fahrzeugschadenpositionen je Abrechnungsart
    if art == "totalschaden":
        fahrzeug = [
            ("wiederbeschaffung", "Wiederbeschaffungswert",            wbw,  False),
            ("restwert",          "abzgl. Restwert",                  -rst,  True),
        ] if wbw > 0 else []
    elif art == "konkret":
        if rep_rech_netto > 0:
            if vorsteuer:
                fahrzeug = [("rep_rechnung_netto", "Reparaturkosten lt. Rechnung (netto)", rep_rech_netto, False)]
            else:
                betrag = rep_rech_brutto if rep_rech_brutto > 0 else rep_rech_netto * 1.19
                fahrzeug = [("rep_rechnung_netto", "Reparaturkosten lt. Rechnung (brutto)", betrag, False)]
        else:
            fahrzeug = []
    else:  # fiktiv
        fahrzeug = [("rep_gutachten_netto", "Reparaturkosten lt. Gutachten (netto)", rep_gut_netto, False)] \
                   if rep_gut_netto > 0 else []

    # Nebenpositionen
    neben = [
        ("wertminderung",   "Merkantile Wertminderung",             _f("wertminderung"),                                    False),
        ("nutzungsausfall", "Nutzungsausfallschaden",                _f("nutzungsausfall"),                                  False),
        ("mietwagenkosten", "Mietwagenkosten" + suf,                 _nb("mietwagenkosten_netto","mietwagenkosten_ust","mietwagenkosten"), False),
        ("sv_kosten",       "Sachverständigenkosten" + suf,          _nb("sv_kosten_netto","sv_kosten_ust","sv_kosten"),     False),
        ("kostennb",        "Nachbesichtigungskosten" + suf,         _nb("kostennb","kostennb_ust","kostennb"),              False),
        ("abschleppkosten", "Abschleppkosten" + suf,                 _nb("abschleppkosten_netto","abschleppkosten_ust","abschleppkosten"), False),
        ("standkosten",     "Standkosten" + suf,                     _nb("standkosten_netto","standkosten_ust","standkosten"), False),
        ("anabmeldekosten", "An-/Abmeldekosten" + suf,               _nb("anabmeldekosten_netto","anabmeldekosten_ust","anabmeldekosten"), False),
        ("schmerzensgeld",  "Schmerzensgeld",                        _f("schmerzensgeld"),                                  False),
        ("verdienstausfall","Verdienstausfall",                       _f("verdienstausfall"),                                False),
        ("haushalt",        "Haushaltsführungsschaden",              _f("haushalt"),                                        False),
        ("unkostenpauschale","Unkostenpauschale",                    _f("unkostenpauschale") or 30.0,                       False),
    ]
    if art == "totalschaden":
        neben = [(k, l, v, a) for k, l, v, a in neben if k != "wertminderung"]

    # Sonstiges
    sonstiges_val   = _f("sonstiges")
    sonstiges_beschr = (schaden.get("sonstiges_beschr") or "Sonstiges").strip() or "Sonstiges"
    extras = []
    if sonstiges_val > 0:
        extras.append(("sonstiges", sonstiges_beschr, sonstiges_val, False))

    raw = schaden.get("wdm_extras_json") or "[]"
    try:
        ex_list = json.loads(raw) if isinstance(raw, str) else (raw or [])
        for ex in (ex_list if isinstance(ex_list, list) else []):
            extras.append((f"extra_{ex.get('id','')}", ex.get("label","Sonstiges"),
                           float(ex.get("betrag") or ex.get("netto") or 0), False))
    except Exception:
        pass

    alle = fahrzeug + [(k, l, v, a) for k, l, v, a in neben if v != 0] + extras

    result = []
    for key, label, forderung, ist_abzug in alle:
        if forderung == 0 and key not in ("wiederbeschaffung", "restwert"):
            continue
        reg_data = pos_map.get(key)
        reguliert = reg_data["reguliert"] if reg_data is not None else None
        result.append({
            "key":       key,
            "label":     label,
            "forderung": forderung,
            "reguliert": reguliert,   # None = noch kein Eintrag
            "ist_abzug": ist_abzug,
        })
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 4-SPALTIGE HAUPTTABELLE
# ══════════════════════════════════════════════════════════════════════════════

def _haupttabelle(rows: list, bw: int, hat_regulierung: bool) -> str:
    c1 = int(bw * 0.44)
    c2 = int(bw * 0.18)
    c3 = int(bw * 0.18)
    c4 = bw - c1 - c2 - c3
    cols = (c1, c2, c3, c4)

    tbl_grid = (
        f'<w:tblGrid>'
        f'<w:gridCol w:w="{c1}"/><w:gridCol w:w="{c2}"/>'
        f'<w:gridCol w:w="{c3}"/><w:gridCol w:w="{c4}"/>'
        f'</w:tblGrid>'
    )

    tr_list = []

    # ── Kopfzeile ──────────────────────────────────────────────────────────
    tr_list.append(_kopfzeile(
        ["Schadenposition", "Forderung", "Regulierung", "Offen"],
        cols
    ))

    # ── Datenzeilen ────────────────────────────────────────────────────────
    gesamtforderung = 0.0
    gesamtreguliert = 0.0
    gesamt_offen    = 0.0

    for i, r in enumerate(rows):
        bg = _GRAU_HELL if i % 2 == 0 else _GRAU_MID
        forderung  = r["forderung"]
        reguliert  = r["reguliert"]   # None oder float
        ist_abzug  = r["ist_abzug"]

        # Offen = gefordert − reguliert (nur wenn reguliert vorhanden)
        if reguliert is not None:
            offen = abs(forderung) - reguliert if ist_abzug else forderung - reguliert
        else:
            offen = None

        # Summen kumulieren (Abzüge negativ)
        netto_forderung = -abs(forderung) if ist_abzug else forderung
        gesamtforderung += netto_forderung
        if reguliert is not None:
            gesamtreguliert += (-reguliert if ist_abzug else reguliert)
        if offen is not None:
            gesamt_offen += offen

        # Zellinhalte
        col1 = r["label"]
        col2 = _euro_fmt(abs(forderung), prefix="- " if ist_abzug else "")
        col3 = _euro_fmt(reguliert) if reguliert is not None else ""
        col4 = _euro_fmt(offen)     if offen     is not None else ""

        rot_forderung   = ist_abzug
        # Regulierung rot wenn Betrag < Forderung, grün wenn vollständig
        gruen_reguliert = (reguliert is not None and reguliert > 0 and not ist_abzug and
                           offen is not None and offen <= 0.005)
        rot_reguliert   = (reguliert is not None and not ist_abzug and not gruen_reguliert
                           and reguliert < abs(forderung) - 0.005)

        tr_list.append(_datenzeile(
            [col1, col2, col3, col4], cols, bg=bg,
            rot={1: rot_forderung, 2: rot_reguliert},
            gruen={2: gruen_reguliert},
        ))

    # ── Summenzeile: Gesamtschaden – offener Betrag fett+rot ─────────────────
    hat_reguliert = any(r["reguliert"] is not None for r in rows)
    offen_gesamt = gesamt_offen if hat_reguliert else abs(gesamtforderung)
    tr_list.append(_summenzeile_gesamt(
        label="Gesamtschaden",
        gefordert=_euro_force(abs(gesamtforderung)),
        reguliert=_euro_force(gesamtreguliert) if hat_reguliert else "",
        offen=_euro_force(offen_gesamt),
        offen_rot=(hat_reguliert and gesamt_offen > 0.005),
        cols=cols, bg=_SUMME_BG
    ))

    if not hat_regulierung:
        tr_list.append(_trenn(cols))
        tr_list.append(_hinweis_zeile(
            "Noch kein Regulierungseingang erfasst.", cols
        ))

    return (
        f'<w:tbl>'
        f'<w:tblPr><w:tblW w:w="{bw}" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="none"/><w:left w:val="none"/>'
        '<w:bottom w:val="none"/><w:right w:val="none"/>'
        '<w:insideH w:val="none"/><w:insideV w:val="none"/>'
        '</w:tblBorders></w:tblPr>'
        + tbl_grid
        + "".join(tr_list)
        + '</w:tbl>'
    )


# ── Zeilentypen ───────────────────────────────────────────────────────────────

def _rpr(sz=22, bold=False, farbe="", caps=False):
    r = f'<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
    if bold:  r += '<w:b/>'
    if farbe: r += f'<w:color w:val="{farbe}"/>'
    if caps:  r += '<w:caps/>'
    r += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    return r


def _kopfzeile(labels, cols):
    rpr = _rpr(sz=20, bold=True, farbe="FFFFFF")
    cells = "".join(
        _tc(l, w, rpr, jc="right" if i > 0 else "left", bg=_KOPF_BG, pad=(80,120,80,120))
        for i, (l, w) in enumerate(zip(labels, cols))
    )
    return f'<w:tr>{cells}</w:tr>'


def _datenzeile(vals, cols, bg="", rot=None, gruen=None):
    rot   = rot   or {}
    gruen = gruen or {}
    cells = ""
    for i, (val, w) in enumerate(zip(vals, cols)):
        jc = "right" if i > 0 else "left"
        if rot.get(i):
            rpr = _rpr(farbe=_ROT)
        elif gruen.get(i):
            rpr = _rpr(farbe="27AE60", bold=True)
        else:
            rpr = _rpr()
        cells += _tc(val, w, rpr, jc=jc, bg=bg, pad=(60,100,60,100))
    return f'<w:tr>{cells}</w:tr>'


def _summenzeile(label, gefordert, reguliert, offen, cols, bg):
    bdr = '<w:tcBorders><w:top w:val="single" w:sz="4" w:color="000000"/></w:tcBorders>'
    rpr = _rpr(bold=True, farbe="000000")
    vals = [label, gefordert, reguliert, offen]
    cells = "".join(
        _tc(v, w, rpr, jc="right" if i > 0 else "left", bg=bg, border=bdr, pad=(80,100,80,100))
        for i, (v, w) in enumerate(zip(vals, cols))
    )
    return f'<w:tr>{cells}</w:tr>'


def _summenzeile_gesamt(label, gefordert, reguliert, offen, offen_rot, cols, bg):
    """Summenzeile mit optionalem Rot für die Offen-Spalte."""
    bdr = '<w:tcBorders><w:top w:val="single" w:sz="6" w:color="000000"/></w:tcBorders>'
    rpr_std  = _rpr(bold=True, farbe="000000")
    rpr_offen = _rpr(bold=True, farbe=_ROT) if offen_rot else rpr_std
    vals = [label, gefordert, reguliert, offen]
    cells = ""
    for i, (v, w) in enumerate(zip(vals, cols)):
        rpr = rpr_offen if i == 3 else rpr_std
        cells += _tc(v, w, rpr, jc="right" if i > 0 else "left",
                     bg=bg, border=bdr, pad=(80,100,80,100))
    return f'<w:tr>{cells}</w:tr>'


def _restbetrag_zeile(label, gefordert, reguliert, offen, cols):
    bdr = (
        f'<w:tcBorders>'
        f'<w:top w:val="single" w:sz="8" w:color="{_BLAU}"/>'
        f'<w:bottom w:val="double" w:sz="8" w:color="{_BLAU}"/>'
        f'</w:tcBorders>'
    )
    rpr = _rpr(sz=24, bold=True, farbe=_BLAU) + f'<w:u w:val="double" w:color="{_BLAU}"/>'
    vals = [label, gefordert, reguliert, offen]
    cells = "".join(
        _tc(v, w, rpr, jc="right" if i > 0 else "left", bg=_REST_BG, border=bdr, pad=(100,100,100,100))
        for i, (v, w) in enumerate(zip(vals, cols))
    )
    return f'<w:tr>{cells}</w:tr>'


def _hinweis_zeile(text, cols):
    """Einspaltige Hinweiszeile (colspan-Simulation: Text in Col1, Rest leer)."""
    rpr = _rpr(farbe="999999")
    vals = [text, "", "", ""]
    cells = "".join(
        _tc(v, w, rpr, jc="left" if i == 0 else "right", pad=(60,100,60,100))
        for i, (v, w) in enumerate(zip(vals, cols))
    )
    return f'<w:tr>{cells}</w:tr>'


def _trenn(cols):
    cells = "".join(
        f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="90" w:lineRule="exact"/></w:pPr></w:p>'
        f'</w:tc>'
        for w in cols
    )
    return f'<w:tr>{cells}</w:tr>'


def _tc(text, width, rpr, jc="left", bg="", border="", pad=(60,100,60,100)):
    shd  = f'<w:shd w:val="clear" w:color="auto" w:fill="{bg}"/>' if bg else ""
    pt, pr_m, pb, pl = pad
    mar  = (
        f'<w:tcMar>'
        f'<w:top w:w="{pt}" w:type="dxa"/>'
        f'<w:start w:w="{pl}" w:type="dxa"/>'
        f'<w:bottom w:w="{pb}" w:type="dxa"/>'
        f'<w:end w:w="{pr_m}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    # Leeres Feld in Zahlen-Spalten (rechts) → zentriertes "–" in Grau
    if not text and jc == "right":
        rpr_leer = _rpr(farbe="AAAAAA")
        return (
            f'<w:tc>'
            f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{border}{shd}{mar}</w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>'
            f'<w:jc w:val="center"/></w:pPr>'
            f'<w:r><w:rPr>{rpr_leer}</w:rPr><w:t>–</w:t></w:r>'
            f'</w:p></w:tc>'
        )
    jcx  = f'<w:jc w:val="{jc}"/>' if jc != "left" else ""
    t_attr = ' xml:space="preserve"' if (" " in text or not text) else ""
    return (
        f'<w:tc>'
        f'<w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{border}{shd}{mar}</w:tcPr>'
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/>{jcx}</w:pPr>'
        f'<w:r><w:rPr>{rpr}</w:rPr><w:t{t_attr}>{_esc(text)}</w:t></w:r>'
        f'</w:p></w:tc>'
    )


# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT-HELFER
# ══════════════════════════════════════════════════════════════════════════════

def _titel_block(text):
    rpr = _rpr(sz=40, bold=True, farbe=_BLAU)
    # 2 Leerzeilen Abstand vor dem Titel (damit kein Datumsfeld-Konflikt)
    lz = '<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:p>'
    titel = (
        f'<w:p>'
        f'<w:pPr>'
        f'<w:jc w:val="center"/>'
        f'<w:pBdr><w:bottom w:val="single" w:sz="12" w:space="1" w:color="{_BLAU}"/></w:pBdr>'
        f'<w:spacing w:before="200" w:after="80"/>'
        f'</w:pPr>'
        f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{_esc(text)}</w:t></w:r>'
        f'</w:p>'
    )
    return lz + lz + titel


def _untertitel(text):
    rpr = _rpr(sz=22, farbe="555555")
    return (
        f'<w:p><w:pPr><w:spacing w:after="120"/></w:pPr>'
        f'<w:r><w:rPr>{rpr}</w:rPr>'
        f'<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'
    )


def _unfalldaten_tabelle(unfallort, unfalltag, kz_mandant, kz_gegner, bw):
    """
    Zweizeilige Tabelle:
      Zeile 1: Unfallort:   | <wert> | Unfalltag:  | <wert>
      Zeile 2: KZ Mandant:  | <wert> | KZ Gegner:  | <wert>
    """
    c_lbl = int(bw * 0.22)
    c_val = int(bw * 0.28)
    c_lbl2 = int(bw * 0.22)
    c_val2 = bw - c_lbl - c_val - c_lbl2

    tbl_grid = (
        f'<w:tblGrid>'
        f'<w:gridCol w:w="{c_lbl}"/><w:gridCol w:w="{c_val}"/>'
        f'<w:gridCol w:w="{c_lbl2}"/><w:gridCol w:w="{c_val2}"/>'
        f'</w:tblGrid>'
    )

    rpr_lbl = _rpr(sz=20, bold=True,  farbe="2C3E50")
    rpr_val = _rpr(sz=20, bold=False, farbe="000000")
    PAD_LBL = (60, 60, 60, 80)
    PAD_VAL = (60, 80, 60, 60)

    def _zl(text, w):
        pt, pr, pb, pl = PAD_LBL
        mar = (f'<w:tcMar><w:top w:w="{pt}" w:type="dxa"/><w:start w:w="{pl}" w:type="dxa"/>'
               f'<w:bottom w:w="{pb}" w:type="dxa"/><w:end w:w="{pr}" w:type="dxa"/></w:tcMar>')
        return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{mar}</w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
                f'<w:r><w:rPr>{rpr_lbl}</w:rPr>'
                f'<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p></w:tc>')

    def _zv(text, w):
        pt, pr, pb, pl = PAD_VAL
        mar = (f'<w:tcMar><w:top w:w="{pt}" w:type="dxa"/><w:start w:w="{pl}" w:type="dxa"/>'
               f'<w:bottom w:w="{pb}" w:type="dxa"/><w:end w:w="{pr}" w:type="dxa"/></w:tcMar>')
        return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{mar}</w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
                f'<w:r><w:rPr>{rpr_val}</w:rPr>'
                f'<w:t xml:space="preserve">{_esc(text or "—")}</w:t></w:r></w:p></w:tc>')

    zeile1 = (f'<w:tr>'
              + _zl("Unfallort:",          c_lbl)  + _zv(unfallort,  c_val)
              + _zl("Unfalltag:",          c_lbl2) + _zv(unfalltag,  c_val2)
              + f'</w:tr>')
    zeile2 = (f'<w:tr>'
              + _zl("Kennzeichen Mandant:", c_lbl)  + _zv(kz_mandant, c_val)
              + _zl("Kennzeichen Gegner:",  c_lbl2) + _zv(kz_gegner,  c_val2)
              + f'</w:tr>')

    return (
        f'<w:tbl>'
        f'<w:tblPr><w:tblW w:w="{bw}" w:type="dxa"/>'
        f'<w:tblBorders>'
        f'<w:top    w:val="single" w:sz="4" w:color="AAAAAA"/>'
        f'<w:left   w:val="single" w:sz="4" w:color="AAAAAA"/>'
        f'<w:bottom w:val="single" w:sz="4" w:color="AAAAAA"/>'
        f'<w:right  w:val="single" w:sz="4" w:color="AAAAAA"/>'
        f'<w:insideH w:val="none"/><w:insideV w:val="none"/>'
        f'</w:tblBorders>'
        f'<w:tblShd w:val="clear" w:color="auto" w:fill="F0F4FB"/>'
        f'</w:tblPr>'
        + tbl_grid + zeile1 + zeile2
        + f'</w:tbl>'
    )


def _stand_zeile(text):
    rpr = _rpr(sz=19, farbe="666666")
    return (
        f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="40" w:after="160"/></w:pPr>'
        f'<w:r><w:rPr>{rpr}</w:rPr>'
        f'<w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'
    )


def _leerzeile(after=0):
    return f'<w:p><w:pPr><w:spacing w:after="{after}" w:line="240" w:lineRule="auto"/></w:pPr></w:p>'


def _abschluss(sb):
    rpr_hint    = _rpr(sz=20, farbe="777777")
    rpr_gruss   = _rpr(sz=22, farbe="000000")
    rpr_kanzlei = _rpr(sz=22, bold=True, farbe=_BLAU)
    teile = [
        f'<w:p><w:pPr><w:spacing w:after="40"/></w:pPr>'
        f'<w:r><w:rPr>{rpr_hint}</w:rPr>'
        f'<w:t>Für Rückfragen stehen wir Ihnen gerne zur Verfügung.</w:t></w:r></w:p>',
        # Leerzeile
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:p>',
        # Mit freundlichen Grüßen
        f'<w:p><w:pPr><w:spacing w:after="40"/></w:pPr>'
        f'<w:r><w:rPr>{rpr_gruss}</w:rPr>'
        f'<w:t>Mit freundlichen Grüßen</w:t></w:r></w:p>',
        # Leerzeile
        f'<w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:p>',
        f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
        f'<w:r><w:rPr>{rpr_kanzlei}</w:rPr>'
        f'<w:t xml:space="preserve">Rechtsanwälte Koch, Schatz &amp; Kollegen</w:t></w:r></w:p>',
    ]
    if sb.get("name"):
        titel = f' ({_esc(sb["titel"])})' if sb.get("titel") else ""
        teile.append(
            f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>'
            f'<w:r><w:rPr>{rpr_hint}</w:rPr>'
            f'<w:t xml:space="preserve">Sachbearbeitung: {_esc(sb["name"])}{titel}</w:t></w:r></w:p>'
        )
    return "".join(teile)


# ══════════════════════════════════════════════════════════════════════════════
# RENDERING
# ══════════════════════════════════════════════════════════════════════════════

def _render_docx(vorlage, replacements, ooxml_blocks):
    with open(vorlage, "rb") as f:
        vb = f.read()
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(vb), "r") as zin, \
         zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                xml = _merge_split_placeholders(xml, list(replacements.keys()))
                for k, v in replacements.items():
                    xml = xml.replace(k, v)
                for ph, block in ooxml_blocks.items():
                    xml = _inject_block(xml, ph, block)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    return output.getvalue()


def _inject_block(xml, ph, block):
    return re.sub(
        r'<w:p[ >](?:(?!</w:p>).)*' + re.escape(ph) + r'(?:(?!</w:p>).)*</w:p>',
        block, xml, flags=re.DOTALL,
    )


def _merge_split_placeholders(xml, phs):
    for ph in phs:
        if ph in xml:
            continue
        def _fix(m, _ph=ph):
            para = m.group(0)
            if '<w:drawing>' in para or '<w:pict>' in para:
                return para
            texte = re.findall(r'<w:t[^>]*>([^<]*)</w:t>', para)
            gesamt = "".join(texte)
            if _ph not in gesamt:
                return para
            count = [0]
            def _t(tm):
                count[0] += 1
                return f'<w:t xml:space="preserve">{gesamt}</w:t>' if count[0] == 1 else '<w:t></w:t>'
            return re.sub(r'<w:t[^>]*>[^<]*</w:t>', _t, para)
        xml = re.sub(r'<w:p[ >](?:(?!</w:p>).)*</w:p>', _fix, xml, flags=re.DOTALL)
    return xml


# ══════════════════════════════════════════════════════════════════════════════
# ABRECHNUNGSART
# ══════════════════════════════════════════════════════════════════════════════

def _ermittle_abrechnungsart(schaden, vorsteuer=False):
    """
    PRD-14: Delegiert an berechne_abrechnungsart() in schaden.py.
    Single Source of Truth – lokale Implementierung entfernt.
    """
    return _berechne_abrechnungsart(schaden, vorsteuer=vorsteuer)["abrechnungsart"]


# ══════════════════════════════════════════════════════════════════════════════
# HILFSFUNKTIONEN
# ══════════════════════════════════════════════════════════════════════════════

def _anrede_text(s):
    m = {"1":"Herrn","2":"Frau","3":"Notar","5":"Rechtsanwalt",
         "6":"Rechtsanwälte","7":"Rechtsanwältin","8":"Eheleute","10":"Notarin"}
    r = m.get((s or "").strip())
    if r: return r
    return {"herr":"Herrn","herrn":"Herrn","frau":"Frau"}.get(
        (s or "").strip().lower().rstrip("."), "")


def _lese_textbreite(vorlage):
    try:
        with zipfile.ZipFile(str(vorlage)) as z:
            doc = z.read('word/document.xml').decode('utf-8')
        pgSz  = re.search(r'<w:pgSz[^/]*/>', doc)
        pgMar = re.search(r'<w:pgMar[^/]*/>', doc)
        if pgSz and pgMar:
            w = int(re.search(r'w:w="(\d+)"',    pgSz.group(0)).group(1))
            l = int(re.search(r'w:left="(\d+)"',  pgMar.group(0)).group(1))
            r = int(re.search(r'w:right="(\d+)"', pgMar.group(0)).group(1))
            return w - l - r
    except Exception: pass
    return 9070


def _esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")


def _euro_fmt(wert, prefix=""):
    if wert is None: return ""
    v = float(wert)
    if v == 0 and not prefix: return ""
    s = f"{abs(v):,.2f}".replace(",","X").replace(".",",").replace("X",".") + "\u00a0\u20ac"
    return prefix + s


def _euro_force(wert):
    v = float(wert or 0)
    return f"{v:,.2f}".replace(",","X").replace(".",",").replace("X",".") + "\u00a0\u20ac"


def _datum_deutsch(d):
    m = ["","Januar","Februar","März","April","Mai","Juni",
         "Juli","August","September","Oktober","November","Dezember"]
    return f"{d.day}. {m[d.month]} {d.year}"


def _hole_sb_info(kuerzel):
    try:
        from ..ramicro.sachbearbeiter import hole_sachbearbeiter
        return hole_sachbearbeiter(kuerzel)
    except Exception:
        return {"name": "", "titel": "Rechtsanwälte"}
