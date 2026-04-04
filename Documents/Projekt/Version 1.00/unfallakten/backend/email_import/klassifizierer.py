"""
backend/email_import/klassifizierer.py
========================================
Klassifiziert eingehende E-Mails in einen von 5 Typen:

  gutachten              – Gutachten vom Sachverstaendiger
  regulierungsschreiben  – Regulierungs-/Abrechnungsschreiben der Versicherung
  sachstandsanfrage      – Sachstandsanfrage des Mandanten
  neues_mandat           – Kein AZ bekannt, Anhang vorhanden → neues Mandat
  sonstiges              – Alles andere

Strategie (Prioritaet absteigend):
  1. PDF-Anhang vorhanden → erkenne_dokumenttyp() aus pdf/parser.py
  2. Absender-Kategorie aus email_absender_vorlagen (bereits geprueft)
  3. Betreff-Regex
  4. Fallback: sonstiges
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Betreff-Muster ────────────────────────────────────────────────────────────

_GUTACHTEN_MUSTER = re.compile(
    r"gutachten|schadensgutachten|kfz.gutachten|sv.gutachten|"
    r"\bGA-\d|reparaturkalkulation|bewertungsgutachten|sachverst",
    re.IGNORECASE
)

_REGULIERUNG_MUSTER = re.compile(
    r"regulier|abrechnung|schadensabrechnung|zahlung|wir erstatten|"
    r"wir zahlen|wir ueberweisen|regulierungsbetrag|schadenregulier|"
    r"anerkennung|erstattung|schadenbearbeitung",
    re.IGNORECASE
)

_SACHSTAND_MUSTER = re.compile(
    r"sachstand|anfrage|nachfrage|stand der|wie ist der stand|"
    r"bitte um|rueckmeldung|haben sie|wann koennen|wann kommen",
    re.IGNORECASE
)

# ── Mapping PDF-Dokumenttyp → E-Mail-Typ ─────────────────────────────────────

_PDF_TYP_MAP = {
    "gutachten":          "gutachten",
    "abrechnung":         "regulierungsschreiben",
    "forderungsschreiben": "sonstiges",
    "sachstandsanfrage":  "sachstandsanfrage",
    "sonstiges":          None,   # kein Signal
    "unbekannt":          None,
}

# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def klassifiziere_email(
    parsed:             dict,
    absender_kategorie: Optional[str] = None,
    akte_az:            Optional[str] = None,
) -> str:
    """
    Klassifiziert eine E-Mail.

    Args:
        parsed:             Ergebnis von parse_email()
        absender_kategorie: Aus email_absender_vorlagen (gutachter/versicherung/...)
        akte_az:            Gematchtes Aktenzeichen (None = unbekannt)

    Returns:
        email_typ: gutachten | regulierungsschreiben | sachstandsanfrage |
                   neues_mandat | sonstiges
    """
    # Weiterleitungs-Prefix abschneiden fuer sauberes Matching
    betreff_raw = (parsed.get('betreff') or '').strip()
    betreff = re.sub(
        r'^(WG|FW|FWD|AW|RE|Fwd|Aw|Wg|fw|wg)\s*:\s*',
        '', betreff_raw, flags=re.IGNORECASE
    ).strip()
    # Bei Weiterleitung den Original-Absender verwenden (wurde in import_service gesetzt)
    ist_wl = parsed.get('ist_weiterleitung', False)
    anhaenge = parsed.get('anhaenge') or []
    hat_pdf_anhang = any(
        a.get("endung", "").lower() in ("pdf",) for a in anhaenge
    )

    # ── Stufe 0: Betreff-Prioritaet fuer eindeutige Keywords ────────────────
    # Wenn Betreff eindeutig 'Gutachten' enthaelt, direkt klassifizieren
    # (verhindert dass PDF-Inhalt die klare Betreff-Info ueberschreibt)
    if _GUTACHTEN_MUSTER.search(betreff):
        logger.debug("Klassifizierung via Betreff-Prioritaet: gutachten")
        return "gutachten"

    # ── Stufe 1: PDF-Inhalt auswerten (wenn Anhang vorhanden) ────────────────
    if hat_pdf_anhang:
        pdf_typ = _erkenne_pdf_typ(anhaenge)
        if pdf_typ:
            logger.debug("Klassifizierung via PDF-Typ '%s'", pdf_typ)
            return pdf_typ

    # ── Stufe 2: Absender-Kategorie ──────────────────────────────────────────
    if absender_kategorie == "gutachter":
        logger.debug("Klassifizierung via Absender-Kategorie 'gutachter'")
        return "gutachten"

    if absender_kategorie == "versicherung":
        logger.debug("Klassifizierung via Absender-Kategorie 'versicherung'")
        return "regulierungsschreiben"

    if absender_kategorie == "gericht":
        logger.debug("Klassifizierung via Absender-Kategorie 'gericht'")
        return "sonstiges"

    # ── Stufe 3: Betreff-Regex ────────────────────────────────────────────────
    if _GUTACHTEN_MUSTER.search(betreff):
        logger.debug("Klassifizierung via Betreff-Muster: gutachten")
        return "gutachten"

    if _REGULIERUNG_MUSTER.search(betreff):
        logger.debug("Klassifizierung via Betreff-Muster: regulierungsschreiben")
        return "regulierungsschreiben"

    if _SACHSTAND_MUSTER.search(betreff):
        logger.debug("Klassifizierung via Betreff-Muster: sachstandsanfrage")
        return "sachstandsanfrage"

    # Sachstandsanfrage via Body-Text erkennen (Mandant fragt nach Sachstand)
    body = (parsed.get('text') or '')[:500]
    if _SACHSTAND_MUSTER.search(body) and akte_az:
        logger.debug("Klassifizierung via Body-Muster: sachstandsanfrage")
        return "sachstandsanfrage"

    # ── Stufe 4: Neues Mandat? ────────────────────────────────────────────────
    # Kein AZ erkannt + PDF-Anhang + unbekannter Absender → neues Mandat
    if not akte_az and hat_pdf_anhang and not absender_kategorie:
        az_kandidaten = parsed.get("az_kandidaten") or []
        if not az_kandidaten:
            logger.debug("Klassifizierung: neues_mandat (kein AZ, PDF vorhanden)")
            return "neues_mandat"

    return "sonstiges"


def _erkenne_pdf_typ(anhaenge: list) -> Optional[str]:
    """
    Versucht den ersten PDF-Anhang zu lesen und zu klassifizieren.
    Gibt den E-Mail-Typ zurueck oder None wenn nicht erkennbar.
    """
    try:
        from ..pdf.extraktor import extrahiere_pdf
        from ..pdf.parser import erkenne_dokumenttyp

        for anhang in anhaenge:
            if anhang.get("endung", "").lower() != "pdf":
                continue
            daten = anhang.get("daten")
            if not daten:
                continue

            extraktion = extrahiere_pdf(daten)
            if extraktion.fehler or extraktion.ist_gescannt or not extraktion.gesamt_text:
                continue

            pdf_dokumenttyp = erkenne_dokumenttyp(extraktion.gesamt_text)
            email_typ = _PDF_TYP_MAP.get(pdf_dokumenttyp)
            if email_typ:
                logger.info("PDF-Typ erkannt: %s → E-Mail-Typ: %s",
                            pdf_dokumenttyp, email_typ)
                return email_typ

    except Exception as e:
        logger.debug("PDF-Typ-Erkennung fehlgeschlagen: %s", e)

    return None
