"""
Modul 8 – Word-Generator: Sachstandsanfrage (Wiedervorlage)
=============================================================
Verwendet sachstandsanfrage_vorlage.docx als Basis (Briefkopf + Grafiken).
Dynamische Felder per Platzhalter-Ersetzung, RA-Micro-Variablen werden
aus _tbl0WDMDaten aufgelöst, Unterschriftsbild je Sachbearbeiter.

Platzhalter in der Vorlage:
    {{EMPF_NAME}}            Empfänger Name
    {{EMPF_STRASSE}}         Empfänger Straße
    {{EMPF_ORT}}             Empfänger PLZ Ort
    {{EMPF_EMAIL}}           "Nur per E-Mail an ..."
    {{AKTENZEICHEN}}         Aktenzeichen mit SB-Kürzel
    {{Aktenkurzbezeichnung}} Aktenkurzbezeichnung
    {{DATUM}}                Datum auf Deutsch
    {{BETREFF1}}             Betreffzeile 1 (RA-Micro-Vars aufgelöst)
    {{BETREFF2}}             Betreffzeile 2
    {{BETREFF3}}             Betreffzeile 3
    {{SB_NAME}}              Sachbearbeiter Name
    {{SB_TITEL}}             Sachbearbeiter Titel
    image1.png               Unterschriftsbild (wird je SB ausgetauscht)
"""

import io
import logging
import os
import re
import zipfile
from datetime import date
from typing import Optional

from ..ramicro.sachbearbeiter import hole_sachbearbeiter

logger = logging.getLogger(__name__)

_VORLAGE_PFAD      = os.path.join(os.path.dirname(__file__), "sachstandsanfrage_vorlage.docx")
_UNTERSCHRIFTEN_DIR = os.path.join(os.path.dirname(__file__), "unterschriften")
_FALLBACK_SB       = "AS"   # Unterschrift wenn kein Bild für SB vorhanden


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _datum_deutsch(d: date) -> str:
    monate = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
              "Juli", "August", "September", "Oktober", "November", "Dezember"]
    return f"{d.day}. {monate[d.month]} {d.year}"


def _escape_xml(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _unterschrift_bytes(sb_kuerzel: str) -> Optional[bytes]:
    """Lädt das Unterschriftsbild für einen Sachbearbeiter.
    Fallback: AS.png wenn kein eigenes Bild vorhanden."""
    for kuerzel in [sb_kuerzel.upper(), _FALLBACK_SB]:
        pfad = os.path.join(_UNTERSCHRIFTEN_DIR, f"{kuerzel}.png")
        if os.path.exists(pfad):
            with open(pfad, "rb") as f:
                return f.read()
    return None


def ersetze_ramicro_vars(text: str, wdm_werte: dict) -> str:
    """
    Ersetzt RA-Micro-Platzhalter in einem Text.

    RA-Micro-Syntax: <VARIABLENNAME> → Wert aus _tbl0WDMDaten (sName = 'varVARIABLENNAME')
    Sonderfall <$N>: Adressfeld-Referenz – wird unverändert entfernt (leer ersetzt).

    Beispiele:
        <U-TAG>  → wdm_werte.get('varU-TAG', '')
        <G-KZ>   → wdm_werte.get('varG-KZ', '')
        <$33>    → '' (RA-Micro interne Adressreferenz)
    """
    def replace_match(m):
        name = m.group(1)
        if name.startswith("$"):
            return ""   # Adressfeld-Referenz – nicht auflösbar
        # Case-insensitive Suche: versuche exakt, dann UPPER
        key_exact = f"var{name}"
        key_upper = f"var{name.upper()}"
        return wdm_werte.get(key_exact) or wdm_werte.get(key_upper) or ""

    return re.sub(r"<([^>]+)>", replace_match, text)


# ── Haupt-Funktion ────────────────────────────────────────────────────────────

def generiere_sachstandsanfrage_wv(wv_daten: dict) -> bytes:
    """
    Generiert eine Sachstandsanfrage als Word-Dokument (.docx).

    Args:
        wv_daten: Dict aus wiedervorlage_service.hole_wiedervorlage_details()
                  Enthält alle Felder inkl. wdm_werte (Dict der WDM-Variablen).
    """
    heute     = date.today()
    datum_str = _datum_deutsch(heute)

    # ── Daten aufbereiten ─────────────────────────────────────────────────────

    az_raw      = wv_daten.get("sAktenNummer", "")
    sb_kuerzel  = wv_daten.get("akte_sachbearbeiter_kuerzel") or ""
    sb          = hole_sachbearbeiter(sb_kuerzel)
    kurzbezeich = wv_daten.get("sAktenKurzBezeichnung", "") or az_raw

    az = (az_raw + sb_kuerzel
          if sb_kuerzel and not az_raw.upper().endswith(sb_kuerzel.upper())
          else az_raw)

    adr_vorname  = wv_daten.get("adr_vorname") or ""
    adr_nachname = wv_daten.get("adr_name") or ""
    # Firma: sVorname leer → nur Nachname; Person: Vorname + Nachname
    adr_name     = (f"{adr_vorname} {adr_nachname}".strip() if adr_vorname else adr_nachname)                    or wv_daten.get("sGegner") or ""
    adr_strasse  = wv_daten.get("adr_strasse") or ""
    adr_plz      = wv_daten.get("adr_plz") or ""
    adr_ort      = wv_daten.get("adr_ort") or ""
    adr_email    = wv_daten.get("adr_email") or ""
    plz_ort      = f"{adr_plz} {adr_ort}".strip()
    empf_email   = f"Nur per E-Mail an {adr_email}" if adr_email else ""

    # Anrede: aus RA-Micro sAnrede, Fallback: generisch
    anrede_raw   = wv_daten.get("anrede") or wv_daten.get("adr_briefanrede") or ""
    if anrede_raw.strip():
        # RA-Micro liefert z.B. "Sehr geehrte Frau Müller," – direkt übernehmen
        anrede = anrede_raw.strip()
    else:
        anrede = "Sehr geehrte Damen und Herren,"

    # ── RA-Micro Variablen auflösen ───────────────────────────────────────────
    wdm = wv_daten.get("wdm_werte") or {}

    def betreff_aufloesen(text: str) -> str:
        if not text:
            return ""
        return ersetze_ramicro_vars(text, wdm)

    betreff1 = betreff_aufloesen(wv_daten.get("sBetreffZeile1") or "")
    betreff2 = betreff_aufloesen(wv_daten.get("sBetreffZeile2") or "")
    betreff3 = betreff_aufloesen(wv_daten.get("sBetreffZeile3") or "")

    # ── Platzhalter-Map ───────────────────────────────────────────────────────
    replacements = {
        "{{ANREDE}}":               _escape_xml(anrede),
        "{{EMPF_NAME}}":            _escape_xml(adr_name),
        "{{EMPF_STRASSE}}":         _escape_xml(adr_strasse),
        "{{EMPF_ORT}}":             _escape_xml(plz_ort),
        "{{EMPF_EMAIL}}":           _escape_xml(empf_email),
        "{{AKTENZEICHEN}}":         _escape_xml(az),
        "{{Aktenkurzbezeichnung}}": _escape_xml(kurzbezeich),
        "{{DATUM}}":                _escape_xml(datum_str),
        "{{BETREFF1}}":             _escape_xml(betreff1),
        "{{BETREFF2}}":             _escape_xml(betreff2),
        "{{BETREFF3}}":             _escape_xml(betreff3),
        "{{SB_NAME}}":              _escape_xml(sb["name"]),
        "{{SB_TITEL}}":             _escape_xml(sb["titel"]),
    }

    # ── Unterschriftsbild laden ───────────────────────────────────────────────
    unterschrift = _unterschrift_bytes(sb_kuerzel)

    # ── Vorlage laden und Platzhalter + Bild ersetzen ─────────────────────────
    with open(_VORLAGE_PFAD, "rb") as f:
        vorlage_bytes = f.read()

    output_buf = io.BytesIO()

    with zipfile.ZipFile(io.BytesIO(vorlage_bytes), "r") as zin, \
         zipfile.ZipFile(output_buf, "w", zipfile.ZIP_DEFLATED) as zout:

        for item in zin.infolist():
            data = zin.read(item.filename)

            if item.filename == "word/document.xml":
                text = data.decode("utf-8")
                for placeholder, value in replacements.items():
                    text = text.replace(placeholder, value)
                data = text.encode("utf-8")

            elif item.filename == "word/media/image1.png" and unterschrift:
                data = unterschrift

            zout.writestr(item, data)

    logger.info("Sachstandsanfrage generiert: AZ=%s SB=%s Empfänger=%s",
                az, sb_kuerzel, adr_name)
    return output_buf.getvalue()


def dateiname_generieren(az: str, datum: Optional[date] = None) -> str:
    d = datum or date.today()
    sicheres_az = az.replace("/", "-").replace("\\", "-").strip()
    return f"{sicheres_az}_sachstandsanfrage_{d.isoformat()}.docx"
