"""
Dokumentenklassifikation: Erkennt Versicherer, Dokumenttyp und Grundmetadaten.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DokumentMetadata:
    """Grundlegende erkannte Metadaten eines Versicherungsdokuments."""
    dokumenttyp: str = "unbekannt"        # "abrechnungsschreiben" | "pruefbericht" | "unbekannt"
    versicherer: str = "Unbekannt"
    versicherer_kuerzel: str = ""          # "HDI", "VHV", "HUK", "ALLIANZ", "ALLIANZ_DIRECT"
    pruefdienstleister: str = ""           # "ControlExpert", "DEKRA", etc. (nur Prüfberichte)
    schadennummer: str = ""
    aktenzeichen_kanzlei: str = ""
    schreibdatum: str = ""                 # YYYY-MM-DD
    schadendatum: str = ""                 # YYYY-MM-DD
    hat_bildseiten: bool = False           # True = mind. eine Seite ist ein Bild (kein OCR)
    konfidenz: float = 0.0                 # 0.0 - 1.0
    rg_score: int = 0                      # Anzahl erkannter Rechnungs-Signale (für Dispatcher)
    sv_rg_score: int = 0                   # Anzahl erkannter SV-Honorar-Signale (für Dispatcher)


# ──────────────────────────────────────────────────────────
# Versicherer-Fingerprints: (schlüsselwort, kürzel, vollname, priorität)
# ──────────────────────────────────────────────────────────
VERSICHERER_PATTERNS = [
    # Spezifischere zuerst
    (r"allianz\s+direct",              "ALLIANZ_DIRECT", "Allianz Direct Versicherungs-AG", 10),
    (r"allianzdirect\.de",             "ALLIANZ_DIRECT", "Allianz Direct Versicherungs-AG", 10),
    (r"allianz\s+versicherungs-aktiengesellschaft", "ALLIANZ", "Allianz Versicherungs-AG", 9),
    (r"sachschaden@allianz\.de",       "ALLIANZ",        "Allianz Versicherungs-AG",        9),
    (r"huk[-\s]coburg",                "HUK",            "HUK-COBURG",                      9),
    (r"huk\.de",                       "HUK",            "HUK-COBURG",                      8),
    (r"hdi\s+global",                  "HDI",            "HDI Global SE",                   9),
    (r"hdi\.global",                   "HDI",            "HDI Global SE",                   8),
    (r"kfz-schadenservice@hdi",        "HDI",            "HDI Global SE",                   8),
    (r"vhv\s+allgemeine\s+versicherung","VHV",           "VHV Allgemeine Versicherung AG",  9),
    (r"schaden@vhv\.de",               "VHV",            "VHV Allgemeine Versicherung AG",  8),
    (r"vhv\.de",                       "VHV",            "VHV Allgemeine Versicherung AG",  7),
    (r"zurich",                        "ZURICH",         "Zurich Insurance",                7),
    (r"axа",                           "AXA",            "AXA Versicherung",                7),
    (r"generali",                      "GENERALI",       "Generali Versicherung",           7),
    (r"ergo",                          "ERGO",           "ERGO Versicherung",               7),
    (r"gothaer",                       "GOTHAER",        "Gothaer Versicherung",            7),
    (r"württembergische",              "WUERTTEMBERGISCHE","Württembergische Versicherung", 7),
    (r"adac\s+versicherungs?[-\s]?ag|adac\s+versicherung\b", "ADAC", "ADAC Versicherungs-AG", 8),
    (r"adac\.de",                      "ADAC",           "ADAC Versicherungs-AG",           7),
]

# ──────────────────────────────────────────────────────────
# Schadennummer-Patterns je Versicherer
# ──────────────────────────────────────────────────────────
SCHADENNUMMER_PATTERNS = {
    "HDI":            r"\b(\d{2}-\d{3}-\d{5}-\d{3})\b",
    "VHV":            r"\b(SD\d+\s+\d+\s+\d+\s+\d+\s+\w+)\b",
    "HUK":            r"\b(\d{2}-\d{2}-\d{3}/\d{6}-[A-Z])\b",
    "ALLIANZ":        r"\b(AS\d{4}-\d{8}-[A-Z]\d{3})\b",
    "ALLIANZ_DIRECT": r"\b(DG\d{4}-\d{8})\b",
    "GOTHAER":        r"\b(\d{2}\.\d{2}\.\d{7})\b",   # z.B. 54.26.0146692
}

# Fallback: generische Schadennummer
SCHADENNUMMER_GENERIC = [
    r"Schaden(?:nummer|[-\s]Nr\.?|[-\s]Nummer)\s*[:\s]+([A-Z0-9][\w\s/-]{5,30}?)(?:\s*[\n(]|$)",
    r"Schaden-Nummer:\s*([A-Z0-9][\w/-]{5,25})\b",
]

# ──────────────────────────────────────────────────────────
# Prüfdienstleister-Fingerprints
# ──────────────────────────────────────────────────────────
PRUEFDIENSTLEISTER_PATTERNS = [
    (r"control.?expert",  "ControlExpert"),
    (r"dekra\s+automobil", "DEKRA"),
    (r"dekra",            "DEKRA"),
    (r"audatex",          "Audatex"),
    (r"da\s+direkt",      "DA Direkt"),
    (r"gtue",             "GTÜ"),
]

# ──────────────────────────────────────────────────────────
# Aktenzeichen der Kanzlei
# ──────────────────────────────────────────────────────────
AKTENZEICHEN_PATTERN = re.compile(
    r"\b(\d{1,6}/\d{2}(?:\s?[A-Z]{2,3})?)\b"
)

# ──────────────────────────────────────────────────────────
# Datums-Patterns
# ──────────────────────────────────────────────────────────
DATUM_PATTERNS = [
    # DD.MM.YYYY
    r"\b(\d{2})\.(\d{2})\.(\d{4})\b",
    # D. Monatsname YYYY
    r"\b(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b",
]

MONATE = {
    "januar": "01", "februar": "02", "märz": "03", "april": "04",
    "mai": "05", "juni": "06", "juli": "07", "august": "08",
    "september": "09", "oktober": "10", "november": "11", "dezember": "12",
}


def _parse_datum(match_groups, pattern_type: int) -> str:
    """Konvertiert Regex-Gruppen zu YYYY-MM-DD."""
    if pattern_type == 0:
        d, m, y = match_groups
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    elif pattern_type == 1:
        d, mon, y = match_groups
        m = MONATE.get(mon.lower(), "00")
        return f"{y}-{m}-{d.zfill(2)}"
    return ""


def classify_document(text: str, has_image_pages: bool = False) -> DokumentMetadata:
    """
    Klassifiziert ein Dokument und extrahiert Grundmetadaten.
    """
    meta = DokumentMetadata(hat_bildseiten=has_image_pages)
    text_lower = text.lower()
    konfidenz_punkte = 0

    # ── Dokumenttyp ──────────────────────────────────────
    pruefbericht_signals = [
        "prüfbericht", "prüfung gutachten", "prüfergebnis",
        "abzug technische prüfung", "abzug werkstattalternative",
        "reparaturkosten nach prüfung", "fiktive prüfung",
        "fiktive abrechnung", "kfz-technische prüfung",
    ]
    abrechnung_signals = [
        "den schaden regulieren wir", "schaden regulieren wir wie folgt",
        "den schadenfall rechnen wir", "abrechnung.*nehmen wir.*vor",
        r"zahlung\s+per\s*überweisung", "zahlungsbetrag", "entschädigungsbetrag",
        r"haben wir.*(?:angewiesen|veranlasst)", "rechnen wir wie folgt ab",
        "wir rechnen wie folgt ab",       # Gothaer-Wortstellung
        r"letztgenannter betrag",          # Gothaer-Zahlungshinweis
        r"schadenregulierung",             # ADAC: "Haftpflichtschadenregulierung"
        r"regulierungsbetrag",             # ADAC + Generali: Gesamtzahlungsbetrag-Label
        r"auszahlungsbetrag",             # einige Versicherer
        r"wir (?:regulieren|haben.*reguliert|konnten.*regulier)", # generisch
    ]
    gutachten_signals = [
        "schadensgutachten", "kfz-gutachten", "kraftfahrzeuggutachten",
        "haftpflichtschaden.*gutachten", "gutachten.*haftpflichtschaden",
        "sachverständigengutachten", "fahrzeugbewertung",
        "wiederbeschaffungswert", "reparaturwürdig",
        "wirtschaftlicher totalschaden", "schadenumfang",
        "merkantile wertminderung", "nutzungsausfall.*tagessatz",
        "besichtigungsdatum", "beauftragter sachverständiger",
        "lichtbilddokumentation", "schadenskalkulation",
    ]

    # Rechnungs-Signale (PRD-23b): spezifische Marker die nur in Rechnungen vorkommen
    rechnung_signals = [
        "rechnungsnummer", "re.-nr.", "rg.-nr.", "zahlungsziel",
        "bitte überweisen sie", "unsere bankverbindung", "bankverbindung",
        "zzgl. 19% mwst", "zzgl. 19 % mwst",
        "zu zahlen bis", "fällig bis", "zahlbar bis", "zahlbar innerhalb",
        r"\biban\b",                 # IBAN auf fast jeder modernen Rechnung
        "nettobetrag",               # klare Rechnungsstruktur
    ]

    # SV-Rechnungs-Signale: NUR echte Honorar-Invoice-Keywords
    # "sachverständigenkosten" und "gutachtenkosten" BEWUSST NICHT hier –
    # sie erscheinen in Gutachten als Schadenspositions-Label und würden
    # das Gutachten fälschlicherweise als sv_rechnung klassifizieren.
    sv_rechnung_signals = [
        "sachverständigenhonorar",   # typisch für SV-Rechnungen
        "gutachterhonorar",          # typisch für SV-Rechnungen
        "honorarrechnung",           # direkter Hinweis auf Honorar-Rechnung
        "sv-honorar",                # Kurzform in manchen SV-Büros
        "honorarnote",               # österreichische/schweizer Variante
        "gutachtergebühr",           # alternative Bezeichnung
        "sachverständigengebühr",    # alternative Bezeichnung
        r"honorar",                  # matcht auch Komposita: Grundhonorar, Fahrthonorar etc.
    ]

    pb_score    = sum(1 for s in pruefbericht_signals  if s in text_lower)
    ab_score    = sum(1 for s in abrechnung_signals     if re.search(s, text_lower))
    gt_score    = sum(1 for s in gutachten_signals      if s in text_lower)
    rg_score    = sum(1 for s in rechnung_signals       if re.search(s, text_lower))
    sv_rg_score = sum(1 for s in sv_rechnung_signals    if re.search(s, text_lower))
    meta.rg_score    = rg_score
    meta.sv_rg_score = sv_rg_score

    # sv_rechnung: SV-Honorar-Keyword + mind. 1 Rechnungs-Signal
    # Kein Fallback auf gt_score+rg_score – zu viele Gutachten haben beides
    if sv_rg_score >= 1 and rg_score >= 1:
        meta.dokumenttyp = "sv_rechnung"
        konfidenz_punkte += min(sv_rg_score + rg_score, 5)
    # Rechnung gewinnt nur wenn mind. 2 spezifische Signale UND klarer Vorsprung
    elif rg_score >= 2 and rg_score > gt_score and rg_score > pb_score and rg_score > ab_score:
        # ── Subtyp-Bestimmung ────────────────────────────────────────────
        abschlepp_sub_signals = [
            r"abschleppdienst",
            r"abschlepp(?:en|kosten|fahrzeug)",
            r"\blfbk\b",                        # LKW mit Fahrzeugkran
            r"fahrzeugbeförderung",
            r"berg(?:ung|ekosten)",
            r"pannenhilfe|pannendienst",
            r"rückschlepp|umsetzkosten",
        ]
        standkosten_sub_signals = [
            r"\bstandkosten\b",
            r"\bstandgeld\b",
            r"\bstandgebühr\b",
            r"bereitstellungsgebühr",
            r"abstellgebühr",
            r"einstellgebühr",
            r"\d+\s*tage?\s+[àa@]\s",           # "22 Tage à 16,81 €"
            r"\d+[,.]?\d*\s*€\s*/\s*tag\b",     # "16,81 €/Tag"
        ]
        ab_sub  = sum(1 for s in abschlepp_sub_signals  if re.search(s, text_lower))
        sk_sub  = sum(1 for s in standkosten_sub_signals if re.search(s, text_lower))
        if ab_sub >= 1:
            meta.dokumenttyp = "abschlepprechnung"
        elif sk_sub >= 1:
            meta.dokumenttyp = "standkostenrechnung"
        else:
            meta.dokumenttyp = "rechnung"
        konfidenz_punkte += min(rg_score, 4)
    elif pb_score > ab_score and pb_score >= gt_score:
        meta.dokumenttyp = "pruefbericht"
        konfidenz_punkte += min(pb_score, 4)
    elif gt_score > ab_score and gt_score >= pb_score:
        meta.dokumenttyp = "gutachten"
        konfidenz_punkte += min(gt_score, 4)
    elif ab_score > 0:
        meta.dokumenttyp = "abrechnungsschreiben"
        konfidenz_punkte += min(ab_score, 4)

    # ── Versicherer ──────────────────────────────────────
    best_versicherer = None
    best_prio = 0
    for pattern, kuerzel, vollname, prio in VERSICHERER_PATTERNS:
        if re.search(pattern, text_lower) and prio > best_prio:
            best_versicherer = (kuerzel, vollname)
            best_prio = prio

    if best_versicherer:
        meta.versicherer_kuerzel, meta.versicherer = best_versicherer
        konfidenz_punkte += 2

    # ── Fallback: Versicherer aus Aktenzeichen-Format ────────
    # z.B. "AS2026-70072807-G002" -> ALLIANZ, "DG2025-..." -> ALLIANZ_DIRECT
    if not meta.versicherer_kuerzel:
        az_m = re.search(r"\bAktenzeichen[:\s]+([A-Z]{2}\d{4}-)", text, re.IGNORECASE)
        if not az_m:
            az_m = re.search(r"\b(AS\d{4}-\d{8}-[A-Z]\d{3})\b", text)
        if az_m:
            prefix = az_m.group(0 if az_m.lastindex == 0 else 1)[:2].upper()
            if prefix == "AS":
                meta.versicherer_kuerzel = "ALLIANZ"
                meta.versicherer = "Allianz Versicherungs-AG"
                konfidenz_punkte += 1
            elif prefix == "DG":
                meta.versicherer_kuerzel = "ALLIANZ_DIRECT"
                meta.versicherer = "Allianz Direct Versicherungs-AG"
                konfidenz_punkte += 1

    # ── Prüfdienstleister (nur bei Prüfberichten relevant) ──
    for pattern, name in PRUEFDIENSTLEISTER_PATTERNS:
        if re.search(pattern, text_lower):
            meta.pruefdienstleister = name
            konfidenz_punkte += 1
            break

    # Bug-7-Fix: DEKRA-Prüfberichte liegen oft als Bild-Seiten in HUK-Dokumenten vor.
    # Wenn has_image_pages=True + Abrechnungsschreiben + HUK → DEKRA-Anhang signalisieren.
    if (not meta.pruefdienstleister and has_image_pages
            and meta.dokumenttyp == "abrechnungsschreiben"
            and meta.versicherer_kuerzel == "HUK"):
        meta.pruefdienstleister = "DEKRA"
        meta.hat_bildseiten = True

    # ── Schadennummer ──────────────────────────────────────
    if meta.versicherer_kuerzel in SCHADENNUMMER_PATTERNS:
        m = re.search(SCHADENNUMMER_PATTERNS[meta.versicherer_kuerzel], text, re.IGNORECASE)
        if m:
            meta.schadennummer = m.group(1).strip()
            konfidenz_punkte += 2

    # Fallback: generische Muster
    if not meta.schadennummer:
        for pattern in SCHADENNUMMER_GENERIC:
            m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if m:
                meta.schadennummer = m.group(1).strip()
                konfidenz_punkte += 1
                break

    # ── Aktenzeichen Kanzlei ──────────────────────────────
    # Suche nach "Ihr Zeichen" Label zuerst
    iz_match = re.search(
        r"(?:Ihr\s+Zeichen|Ihr\s+Az\.|Az\.)[\s,:\n]+(\d{1,6}/\d{2}(?:\s?[A-Z]{2,3})?)",
        text, re.IGNORECASE
    )
    if iz_match:
        meta.aktenzeichen_kanzlei = iz_match.group(1).strip()
        konfidenz_punkte += 1
    else:
        m = AKTENZEICHEN_PATTERN.search(text)
        if m:
            meta.aktenzeichen_kanzlei = m.group(1).strip()

    # ── Schreibdatum ──────────────────────────────────────
    # Priorität 1: Ort + Datum (z.B. "Köln, 12.03.2026")
    ort_datum = re.search(
        r"[A-ZÄÖÜ][a-zäöüß]+(?:\s[A-ZÄÖÜ][a-zäöüß]+)?,?\s+"
        r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})",
        text
    )
    if ort_datum:
        d, m_val, y = ort_datum.group(1), ort_datum.group(2), ort_datum.group(3)
        meta.schreibdatum = f"{y}-{m_val.zfill(2)}-{d.zfill(2)}"
        konfidenz_punkte += 1
    else:
        # Priorität 2: explizites Label "Datum DD.MM.YYYY"
        datum_m = re.search(r"Datum\s+(\d{2})\.(\d{2})\.(\d{4})", text)
        if datum_m:
            meta.schreibdatum = f"{datum_m.group(3)}-{datum_m.group(2)}-{datum_m.group(1)}"
            konfidenz_punkte += 1
        else:
            # Priorität 3: ausgeschriebener Monat ("10. Februar 2026")
            datum_m2 = re.search(
                r"\b(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|"
                r"September|Oktober|November|Dezember)\s+(\d{4})\b",
                text, re.IGNORECASE
            )
            if datum_m2:
                d = datum_m2.group(1)
                mon = MONATE.get(datum_m2.group(2).lower(), "00")
                y = datum_m2.group(3)
                meta.schreibdatum = f"{y}-{mon}-{d.zfill(2)}"
                konfidenz_punkte += 1
            else:
                # Priorität 4: erstes DD.MM.YYYY im Briefkopf (erste 800 Zeichen)
                kopf = text[:800]
                datum_m3 = re.search(r"\b(\d{1,2})\.(\d{2})\.(\d{4})\b", kopf)
                if datum_m3:
                    d, m_val, y = datum_m3.group(1), datum_m3.group(2), datum_m3.group(3)
                    # Plausibilitätsprüfung: Monat 1–12, Jahr ab 2000
                    if 1 <= int(m_val) <= 12 and int(y) >= 2000:
                        meta.schreibdatum = f"{y}-{m_val.zfill(2)}-{d.zfill(2)}"
                        konfidenz_punkte += 1

    # ── Schadendatum ──────────────────────────────────────
    # "Kfz-Haftpflichtschaden vom DD.MM.YYYY" / "Schaden vom DD.MM.YYYY"
    schaden_datum_m = re.search(
        r"(?:Haftpflichtschaden|Schaden)\s+vom\s+(\d{1,2})\.(\d{1,2})\.(\d{4})",
        text, re.IGNORECASE
    )
    if schaden_datum_m:
        d, m_val, y = schaden_datum_m.group(1), schaden_datum_m.group(2), schaden_datum_m.group(3)
        meta.schadendatum = f"{y}-{m_val.zfill(2)}-{d.zfill(2)}"
        konfidenz_punkte += 1

    # ── Konfidenz ──────────────────────────────────────────
    meta.konfidenz = min(konfidenz_punkte / 12.0, 1.0)

    return meta
