"""
Parser für Kfz-Sachverständigen-Gutachten

Erkennt typische Layouts von:
- DEKRA Automobil GmbH
- GTÜ Gesellschaft für Technische Überwachung
- TÜV-Stationen
- Freie SV-Büros (AUTOexpert, Kraftfahrzeugsachverständige etc.)

Extrahiert:
- Fahrzeugdaten (Hersteller, Typ, EZ, KM, Kennzeichen)
- Schadenpositionen: WBW, Restwert, Reparaturkosten (netto/brutto),
  Wertminderung, Nutzungsausfall, SV-Kosten
- Schadenart (Reparaturschaden / Totalschaden / Totalschadengrenze)
- SV-Büro und Gutachter
- Auftragsdatum / Besichtigungsdatum
"""
import re
from dataclasses import dataclass, field
from typing import Optional
from .pdf_utils import parse_betrag, find_betrag_near_label, normalize_text


# ══════════════════════════════════════════════════════════════════════════════
# DATENKLASSEN
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class GutachtenFahrzeug:
    hersteller: str = ""
    typ: str = ""
    kennzeichen: str = ""
    erstzulassung: str = ""        # YYYY-MM-DD
    kilometerstand: Optional[int] = None
    farbe: str = ""
    vin: str = ""                  # Fahrzeug-Ident-Nummer


@dataclass
class GutachtenParseResult:
    # Metadaten
    sv_buero: str = ""
    gutachter: str = ""
    auftragsnummer: str = ""
    auftragsdatum: str = ""        # YYYY-MM-DD
    besichtigungsdatum: str = ""   # YYYY-MM-DD
    schadendatum: str = ""         # YYYY-MM-DD
    schadennummer_versicherung: str = ""
    versicherung_name: str = ""
    versicherungsschein_nummer: str = ""

    # Fahrzeug
    fahrzeug: GutachtenFahrzeug = field(default_factory=GutachtenFahrzeug)

    # Schadenart
    schadenart: str = "reparaturschaden"   # "reparaturschaden" | "totalschaden" | "grenzfall"
    abrechnungsart: str = "fiktiv"         # "fiktiv" | "konkret"

    # Kernbeträge (alle NETTO sofern nicht anders angegeben)
    reparaturkosten_netto: Optional[float] = None
    reparaturkosten_brutto: Optional[float] = None
    wiederbeschaffungswert: Optional[float] = None
    restwert: Optional[float] = None
    wertminderung: Optional[float] = None
    wertverbesserung: Optional[float] = None   # Abzug vom Reparaturbetrag (steuerneutral)
    nutzungsausfall_tagessatz: Optional[float] = None
    nutzungsausfall_tage: Optional[int] = None
    nutzungsausfall_gesamt: Optional[float] = None
    sv_kosten_netto: Optional[float] = None
    sv_kosten_brutto: Optional[float] = None

    # Abgeleitete Werte
    wirtschaftlicher_totalschaden: bool = False   # Rep > 130% WBW
    totalschadengrenze: Optional[float] = None    # 130% des WBW

    konfidenz: float = 0.0
    warnungen: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# HILFSFUNKTIONEN
# ══════════════════════════════════════════════════════════════════════════════

def _find_first(text: str, patterns: list[str], flags=re.IGNORECASE) -> Optional[str]:
    """Gibt den ersten Match zurück."""
    for pattern in patterns:
        m = re.search(pattern, text, flags)
        if m:
            return m.group(1).strip()
    return None


def _find_betrag(text: str, labels: list[str], window: int = 80) -> Optional[float]:
    """
    Sucht nach einem Betrag in der Nähe eines der Labels.

    Primär: Betrag mit Währungszeichen (€ / EUR) – verhindert, dass Prozent-
    oder MwSt-Zahlen (z. B. "19") fälschlich als Schadensbetrag erkannt werden.

    Fallback: Betrag ohne Währungszeichen, aber nur wenn das gefundene Label
    mindestens 10 Zeichen lang ist (spezifisch genug, um Fehlzuordnungen
    auszuschließen). Erforderlich für Audatex-Zusammenfassungen wie
    "Voraussichtliche Reparaturkosten netto :  20535,10" ohne EUR-Angabe.
    """
    BETRAG_MIT_WAEHRUNG = re.compile(
        r"(?:€|EUR)\s*(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})"   # € 1.234,56
        r"|"
        r"(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})\s*(?:EUR|€)",   # 1.234,56 EUR
        re.IGNORECASE
    )

    for label in labels:
        # finditer statt search: alle Vorkommen durchprobieren.
        # Nötig wenn das erste Vorkommen im Inhaltsverzeichnis steht (nur Punkte,
        # kein Betrag) und der echte Betrag erst später im Text erscheint.
        for m in re.finditer(re.escape(label), text, re.IGNORECASE):
            # Suche NUR im Text NACH dem Label (ab m.end()), nicht ab m.start().
            # Sonst würde ein folgendes "EUR X" auf der nächsten Zeile vor dem
            # eigentlichen Betrag ohne Währungszeichen gefunden werden.
            snippet = text[m.end(): m.end() + window]
            betrag_m = BETRAG_MIT_WAEHRUNG.search(snippet)
            if betrag_m:
                raw = betrag_m.group(1) or betrag_m.group(2)
                v = parse_betrag(raw)
                if v is not None and v > 0:
                    return v
            # Fallback ohne Währung nur für spezifische Labels (≥10 Zeichen)
            if len(label) >= 10:
                betrag_m2 = re.search(
                    r"[\s:]\s*(\d+(?:\.\d{3})*,\d{2})\s*(?:\n|$)",
                    snippet
                )
                if betrag_m2:
                    v = parse_betrag(betrag_m2.group(1))
                    if v is not None and v > 0:
                        return v
    return None


def _parse_datum_de(s: str) -> str:
    """DD.MM.YYYY → YYYY-MM-DD"""
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s.strip())
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return ""


def _extract_km(text: str) -> Optional[int]:
    """Kilométerstand extrahieren."""
    patterns = [
        r"(?:Kilometerstand|km-Stand|Laufleistung)[:\s]+(\d[\d\.\s]{1,8})\s*km",
        r"(\d[\d\.]{3,8})\s*km\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1).replace(".", "").replace(" ", ""))
            except ValueError:
                pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# SV-BÜRO ERKENNUNG
# ══════════════════════════════════════════════════════════════════════════════

SV_BUERO_PATTERNS = [
    (r"dekra\s+automobil",          "DEKRA Automobil GmbH"),
    (r"\bdekra\b",                  "DEKRA"),
    (r"gt[üu]e?\s+gesellschaft",    "GTÜ"),
    (r"\bgtüe?\b",                  "GTÜ"),
    (r"t[üu]v\s+s[üu]d",           "TÜV SÜD"),
    (r"t[üu]v\s+nord",              "TÜV Nord"),
    (r"t[üu]v\s+rheinland",         "TÜV Rheinland"),
    (r"\bt[üu]v\b",                 "TÜV"),
    (r"autoexpert",                 "AUTOexpert"),
    (r"kfz[-\s]sachverst[äa]ndige", "KFZ-Sachverständige"),
    (r"huk[-\s]coburg\s+.*gutacht", "HUK-COBURG SV-Büro"),
]

def _detect_sv_buero(text_lower: str, text_orig: str = "") -> str:
    # Schritt 1: Firmennamen in den ersten 5 Zeilen (Briefkopf) haben Vorrang
    for line in text_orig.splitlines()[:5]:
        line = line.strip()
        if len(line) > 5 and re.search(
            r"(?:GmbH|GbR|\bAG\b|e\.K\.|Sachverst[äa]ndige.*(?:GmbH|Büro))",
            line, re.IGNORECASE
        ):
            return line[:60]

    # Schritt 2: Bekannte SV-Organisationen im Volltext suchen
    for pattern, name in SV_BUERO_PATTERNS:
        if re.search(pattern, text_lower):
            return name
    return ""


# ══════════════════════════════════════════════════════════════════════════════
# FAHRZEUGDATEN
# ══════════════════════════════════════════════════════════════════════════════

def _extract_fahrzeug(text: str) -> GutachtenFahrzeug:
    fz = GutachtenFahrzeug()
    tl = text.lower()

    # Kennzeichen: Standard mit Bindestrich (OF-AB 123) UND ohne (F MH 5362)
    # Suche explizit nach "Amtliches Kennzeichen" Label zuerst
    kz_label_m = re.search(
        r"(?:Amtliches\s+Kennzeichen|Kennzeichen)[:\s]+([A-ZÄÖÜ]{1,3}[\s\-][A-Z]{1,2}\s?\d{1,4}[HE]?)\b",
        text, re.IGNORECASE
    )
    if kz_label_m:
        fz.kennzeichen = kz_label_m.group(1).strip()
    else:
        # Fallback: freies Muster mit Bindestrich
        kz_m = re.search(r"\b([A-ZÄÖÜ]{1,3}-[A-Z]{1,2}\s?\d{1,4}[HE]?)\b", text)
        if kz_m:
            fz.kennzeichen = kz_m.group(1).strip()

    # Hersteller + Typ
    hersteller_patterns = [
        # "Fabrikat: Mercedes-Benz" (Neubauer-Format)
        r"(?:Fabrikat)[:\s]+([A-Za-zÄÖÜäöüß\-]+(?:\s+[A-Za-zÄÖÜäöüß\-]+)?)",
        # "Hersteller: Volkswagen" (Cassese-Format, DAT-Kalkulation)
        r"(?:^|\n)Hersteller[:\s]+([A-Za-zÄÖÜäöüß\-]+(?:\s+[A-Za-zÄÖÜäöüß\-]+)?)(?:\n|\*|$)",
        r"(?:Fahrzeug|Fahrzeugtyp|Fahrzeugbezeichnung|Marke)[:\s]+([A-Za-zÄÖÜäöüß\-]+)\s+([A-Za-z0-9\.\-\s]{2,30}?)(?:\n|,|Erstzulassung)",
        r"(?:Marke|Make)[:\s]+([A-Za-zÄÖÜäöüß\-]+)",
    ]
    for p in hersteller_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            fz.hersteller = m.group(1).strip()
            if m.lastindex and m.lastindex >= 2:
                fz.typ = m.group(2).strip()
            break

    # Erstzulassung
    ez_patterns = [
        r"Erstzulassung[:\s]+(\d{1,2}\.\d{1,2}\.\d{4})",
        r"EZ[:\s]+(\d{1,2}\.\d{1,2}\.\d{4})",
        r"(?:zugelassen|Zulassung)\s+(?:am|seit)\s+(\d{1,2}\.\d{1,2}\.\d{4})",
    ]
    for p in ez_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            fz.erstzulassung = _parse_datum_de(m.group(1))
            break

    # Kilometerstand
    fz.kilometerstand = _extract_km(text)

    # VIN / FIN – auch "Fahrzeug-Ident-Nummer" und "Fahrzeugidentifikationsnummer (VIN)"
    vin_m = re.search(
        r"(?:FIN|VIN|Fahrzeug-Ident(?:-Nummer)?|Fahrzeugidentifikationsnummer(?:\s*\(VIN\))?|Fahrgestellnummer)[:\s]+([A-HJ-NPR-Z0-9]{17})",
        text, re.IGNORECASE
    )
    if vin_m:
        fz.vin = vin_m.group(1).strip()

    # Farbe
    farbe_m = re.search(r"(?:Farbe|Lackierung)[:\s]+([A-Za-zÄÖÜäöüß\s\-]{3,25})(?:\n|,)", text, re.IGNORECASE)
    if farbe_m:
        fz.farbe = farbe_m.group(1).strip()

    return fz


# ══════════════════════════════════════════════════════════════════════════════
# KERNBETRÄGE
# ══════════════════════════════════════════════════════════════════════════════

# Label-Listen je Position (in Reihenfolge der Spezifität)
LABELS_WBW = [
    "Wiederbeschaffungswert", "Wiederbeschaffungspreis",
    "WBW", "W.B.W.", "Neupreis bei Totalschaden",
    "Fahrzeugwert", "Handelswert",
]
LABELS_RESTWERT = [
    "Restwert:", "Restwertangebot",
    "Mindestrestwert", "Verwertungserlös",
    "Restwert mit",          # z. B. "Restwert mit 19,00 % MwSt."
    # HINWEIS: "Restwert" allein (ohne Doppelpunkt) entfernt – matcht auf
    # "Restwertermittlung (keine)" und greift dann den nächsten Betrag.
]
LABELS_REP_NETTO = [
    "Nettoreparaturkosten", "Reparaturkosten netto",
    "Reparaturkosten (netto)", "Rep.-Kosten netto",
    "Reparaturaufwand netto",
    "Voraussichtliche Reparaturkosten netto",  # Audatex-Zusammenfassung
    "Reparaturkosten ohne MwSt.",              # Neubauer/Kaeswurm-Format
    "Reparaturkosten:", "Instandsetzungskosten netto",
]
# HINWEIS: "netto:" allein absichtlich entfernt – zu generisch
LABELS_REP_BRUTTO = [
    "Bruttoreparaturkosten", "Reparaturkosten brutto",
    "Reparaturkosten (brutto)", "Rep.-Kosten brutto",
    "Reparaturaufwand brutto",
    "Voraussichtliche Reparaturkosten brutto",
    "Reparaturkosten mit",          # z. B. "Reparaturkosten mit 19,00 % MwSt."
    "Reparaturkosten inkl.", "Instandsetzungskosten brutto",
]
# HINWEIS: "inkl. MwSt." entfernt – zu generisch (kann WBW-Zeile treffen)
LABELS_WERTMINDERUNG = [
    "Merkantile Wertminderung", "Wertminderung (merkantil)",
    "Minderwert", "§ 251 BGB",
    # "Wertminderung" allein BEWUSST entfernt:
    # "Wertminderung keine" / "Wertminderung entfällt" steht in vielen Gutachten
    # direkt vor dem WBW-Betrag → Parser griff den WBW als Wertminderung.
]
LABELS_NA_GESAMT = [
    "Nutzungsausfall gesamt", "Nutzungsausfallentschädigung",
    "Nutzungsausfall:", "Ausfallentschädigung",
]
LABELS_NA_TAGESSATZ = [
    "Nutzungsausfalltagessatz", "Tagessatz",
    "Ausfallentschädigung je Tag", "Tagessatz:",
    "Nutzungsausfall pro Tag",          # Neubauer/Kaeswurm-Format
    "Entschädigung pro Ausfalltag",     # Cassese-Format
    "Entschädigung pro Tag",            # Kurzform
    "Nutzungsausfallsatz",
]
LABELS_SV_NETTO = [
    "Sachverständigenkosten netto", "Gutachterkosten netto",
    "Sachverständigengebühr netto", "SV-Kosten netto",
    "Gutachterhonorar netto",
]
LABELS_SV_BRUTTO = [
    "Sachverständigenkosten brutto", "Gutachterkosten brutto",
    "Gutachterhonorar brutto", "SV-Kosten brutto",
    "Sachverständigenkosten inkl.", "Honorar brutto",
    "Gesamthonorar", "Gutachterhonorar inkl.",
    "Sachverständigenhonorar inkl.",
]
# HINWEIS: "Rechnungsbetrag" und "Gesamtbetrag:" absichtlich entfernt –
# zu generisch, können Gesamtschadenbetrag oder Reparaturrechnungstotal ziehen.


def _extract_betraege(text: str, result: GutachtenParseResult) -> None:
    """Extrahiert alle Geldbeträge aus dem Gutachtentext."""

    # ── Reparaturkosten ─────────────────────────────────────────────────
    result.reparaturkosten_netto  = _find_betrag(text, LABELS_REP_NETTO)
    result.reparaturkosten_brutto = _find_betrag(text, LABELS_REP_BRUTTO)

    # Fallback: häufiges Muster "Reparaturkosten ... X.XXX,XX €" oder "€ X.XXX,XX"
    if not result.reparaturkosten_netto and not result.reparaturkosten_brutto:
        m = re.search(
            r"Reparatur(?:kosten|aufwand)[^\n]{0,80}?"
            r"(?:(?:€|EUR)\s*(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})"
            r"|(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})\s*(?:EUR|€))",
            text, re.IGNORECASE
        )
        if m:
            raw = m.group(1) or m.group(2)
            result.reparaturkosten_netto = parse_betrag(raw)

    # ── WBW ─────────────────────────────────────────────────────────────
    # Einzel-Regex mit großem Fenster (150 Zeichen) auf derselben Zeile:
    # Label + Text-Wert wie "ausreichend" → Sentinel 1.000.000 (kein Totalschaden).
    # Zweiter Pfad: nur spezifische Mehrwort-Labels (NICHT "WBW", "Fahrzeugwert",
    # "Handelswert" – zu generisch, tauchen auch in der NA-Tabelle auf).
    _wbw_ausreichend_m = re.search(
        r"(?:Wiederbeschaffungswert|Wiederbeschaffungspreis|WBW|W\.B\.W\.)"
        r"[^\n]{0,150}"
        r"(?:ausreichend|nicht\s+ermittelt|entfällt|keine?\s+Angabe|k\.A\.)",
        text, re.IGNORECASE
    )
    if _wbw_ausreichend_m:
        # "ausreichend" = Reparatur wirtschaftlich sinnvoll, kein Totalschaden.
        # Sentinel 1.000.000 damit Totalschaden-Check (Rep > 130% WBW) nie auslöst.
        result.wiederbeschaffungswert = 1_000_000.0
    else:
        result.wiederbeschaffungswert = _find_betrag(text, [
            "Wiederbeschaffungswert", "Wiederbeschaffungspreis",
            "Neupreis bei Totalschaden",
        ])

    # ── Restwert ─────────────────────────────────────────────────────────
    # Textwerte wie "kein", "keiner", "nicht ermittelt" → explizit 0
    _rv_kein = re.search(
        r"\bRestwert\b[^\n]{0,40}"
        r"(?:kein(?:er)?|nicht\s+ermittelt|entfällt|0[,.]00|–|keine?\s+Angabe)",
        text, re.IGNORECASE
    )
    if _rv_kein:
        result.restwert = 0.0
    else:
        # Spezifische Labels (mit Doppelpunkt oder Zusatz):
        result.restwert = _find_betrag(text, LABELS_RESTWERT)
        # Fallback: "Restwert EUR 110,00" – aber NICHT wenn "Restwertermittlung" folgt
        if result.restwert is None:
            rv_m = re.search(
                r"\bRestwert\b(?!\s*ermittlung)(?!\s*\(keine\))[^\n]{0,40}"
                r"(?:(?:€|EUR)\s*(\b\d{1,3}(?:[.\s]\d{3})*,\d{2}|\b\d+,\d{2})"
                r"|(\b\d{1,3}(?:[.\s]\d{3})*,\d{2}|\b\d+,\d{2})\s*(?:EUR|€))",
                text, re.IGNORECASE
            )
            if rv_m:
                raw = rv_m.group(1) or rv_m.group(2)
                v = parse_betrag(raw)
                if v is not None and v > 0:
                    result.restwert = v

    # ── Wertminderung ────────────────────────────────────────────────────
    # Reihenfolge: erst konkreten Betrag suchen, dann explizit 0/keine prüfen.
    #
    # 1) Spezifische Labels (Merkantile Wertminderung, Minderwert, §251 BGB)
    result.wertminderung = _find_betrag(text, LABELS_WERTMINDERUNG)
    #
    # 2) Fallback: "Wertminderung 150,00 €" ohne "merkantil"-Zusatz (häufig in SV-Gutachten).
    #    Nur gleiche Zeile, kein "keine/entfällt" davor.
    #    "Wertminderung" allein bleibt aus LABELS_WERTMINDERUNG ausgeschlossen
    #    (würde sonst WBW-Betrag in der Folgezeile greifen).
    if result.wertminderung is None:
        _wm_fb = re.search(
            r"\bWertminderung\b"
            r"(?![^\n]{0,40}(?:keine?|entfällt|nicht\s+ermittelt))"
            r"[^\n]{0,60}"
            r"(?:(?:€|EUR)\s*(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})"
            r"|(?<!\d)(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})\s*(?:€|EUR))",
            text, re.IGNORECASE
        )
        if _wm_fb:
            raw = _wm_fb.group(1) or _wm_fb.group(2)
            v = parse_betrag(raw)
            if v is not None and v > 0:
                result.wertminderung = v
    #
    # 3) Kein positiver Betrag gefunden → prüfen ob explizit 0/keine angegeben.
    #    FIX: (?<!\d)0[,.]00 verhindert Backtracking-Fehlmatch bei "150,00 €"
    #    (alte Regex sah "150,0" als "[^\n]{0,80}" + "0,00 €" → false positive).
    if result.wertminderung is None:
        _wm_kein = re.search(
            r"(?:Merkantile\s+Wertminderung|Wertminderung(?:\s*\(merkantil\))?|Minderwert)"
            r"[^\n]{0,80}"
            r"(?:keine?|entfällt|nicht\s+ermittelt|(?<!\d)0[,.]00\s*€?|\b0\s*€)",
            text, re.IGNORECASE
        )
        if _wm_kein:
            result.wertminderung = 0.0

    # ── Wertverbesserung (Abzug bei Vorschäden) ──────────────────────────
    wv_m = re.search(
        r"Wertverbesserung[^\n]{0,60}?"           # non-greedy: so wenig wie nötig
        r"(?:(?:€|EUR)\s*(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})"
        r"|(?<!\d)(\d{1,3}(?:[.\s]\d{3})*,\d{2}|\d+,\d{2})\s*(?:EUR|€))",
        text, re.IGNORECASE
    )
    if wv_m:
        raw = wv_m.group(1) or wv_m.group(2)
        v = parse_betrag(raw)
        if v is not None and v > 0:
            result.wertverbesserung = v

    # ── Nutzungsausfall ──────────────────────────────────────────────────
    # WICHTIG: Im Gutachten wird der Nutzungsausfallschaden NICHT berechnet –
    # das Fahrzeug ist zum Zeitpunkt der Begutachtung noch nicht repariert.
    # nutzungsausfall_gesamt bleibt daher immer None.
    # nutzungsausfall_tagessatz = Nutzungsausfallklasse (z.B. "Klasse G: 59 €/Tag") → Info
    # nutzungsausfall_tage = geschätzte Reparaturdauer → wird später für NA-Berechnung gebraucht
    result.nutzungsausfall_tagessatz = _find_betrag(text, LABELS_NA_TAGESSATZ)
    result.nutzungsausfall_gesamt    = None   # nie aus Gutachten übernehmen

    # Tage – NUR im Kontext einer Nutzungsausfall-Zeile suchen
    for na_kontext_m in re.finditer(
        r"(?:Nutzungsausfall|Ausfalltag|Ausfallentschäd)[^\n]{0,300}",
        text, re.IGNORECASE
    ):
        na_snippet = na_kontext_m.group(0)
        tage_m = re.search(
            r"(\d{1,2})\s*(?:Tage?|Ausfalltage?|Reparaturtage?)\b",
            na_snippet, re.IGNORECASE
        )
        if tage_m:
            try:
                result.nutzungsausfall_tage = int(tage_m.group(1))
            except ValueError:
                pass
            break

    # ── SV-Kosten ────────────────────────────────────────────────────────
    result.sv_kosten_netto  = _find_betrag(text, LABELS_SV_NETTO)
    result.sv_kosten_brutto = _find_betrag(text, LABELS_SV_BRUTTO)

    # Brutto aus Netto ableiten (19% MwSt) wenn Brutto fehlt
    if result.sv_kosten_netto and not result.sv_kosten_brutto:
        result.sv_kosten_brutto = round(result.sv_kosten_netto * 1.19, 2)


# ══════════════════════════════════════════════════════════════════════════════
# SCHADENART
# ══════════════════════════════════════════════════════════════════════════════

def _detect_schadenart(text: str, result: GutachtenParseResult) -> None:
    """Erkennt Totalschaden, Reparaturschaden oder Grenzfall."""
    tl = text.lower()

    total_signals = [
        # Eindeutige Totalschaden-Deklarationen
        "wirtschaftlicher totalschaden",
        "technischer totalschaden",
        "totalschaden liegt vor",
        "einwandfreier totalschaden",   # Neubauer/Kaeswurm-Format
        "übersteigen den wiederbeschaffungswert",
        "unzumutbar",
    ]
    rep_signals = [
        "reparaturwürdig", "fachgerecht repariert",
        "reparatur wirtschaftlich", "reparaturschaden",
        "instandsetzung wirtschaftlich", "fiktive abrechnung",
    ]

    total_score = sum(1 for s in total_signals if s in tl)
    rep_score   = sum(1 for s in rep_signals   if s in tl)

    if total_score > 0:
        result.schadenart = "totalschaden"
        result.wirtschaftlicher_totalschaden = True

        # Totalschadengrenze = 130% WBW
        if result.wiederbeschaffungswert:
            result.totalschadengrenze = round(result.wiederbeschaffungswert * 1.3, 2)
    elif rep_score > 0:
        result.schadenart = "reparaturschaden"

    # Abrechnungsart: Im Gutachten grundsätzlich fiktiv.
    # Die Unterscheidung fiktiv/konkret ist erst beim Forderungsschreiben relevant
    # und wird dort separat erfasst – nicht durch den Gutachten-Parser.
    result.abrechnungsart = "fiktiv"


# ══════════════════════════════════════════════════════════════════════════════
# METADATEN (Gutachter, Nummer, Datum)
# ══════════════════════════════════════════════════════════════════════════════

def _extract_meta(text: str, result: GutachtenParseResult) -> None:
    """Auftragsnummer, Gutachter, Datum etc."""

    # Auftragsnummer / Gutachtennummer
    # HINWEIS: "Schadennummer" bewusst entfernt – wird separat als schadennummer_versicherung extrahiert
    nr_m = re.search(
        r"(?:Auftrag(?:snummer|s-Nr\.?)|Gutachten(?:nummer|-Nr\.?)|Vorgangs-Nr\.?)"
        r"[:\s]+([A-Z0-9][A-Z0-9/\-\.]{3,25})",
        text, re.IGNORECASE
    )
    if nr_m:
        result.auftragsnummer = nr_m.group(1).strip()
    else:
        # Fallback: "Gutachten B25/1844" – auch mit gesperrtem Text ("G u t a c h t e n")
        nr_m2 = re.search(
            r"G\s*u\s*t\s*a\s*c\s*h\s*t\s*e\s*n\s+([A-Z]\d{1,4}/\d{3,6})\b",
            text, re.IGNORECASE
        )
        if nr_m2:
            result.auftragsnummer = nr_m2.group(1).strip()

    # Gutachter / Besichtigt durch
    gutachter_m = re.search(
        r"(?:Sachverst[äa]ndiger?|Gutachter|Erstellt von|Bearbeiter|Besichtigt durch)[:\s]+([A-Za-zÄÖÜäöüß\-\s\.]{5,40})(?:\n|,|\d)",
        text, re.IGNORECASE
    )
    if gutachter_m:
        result.gutachter = gutachter_m.group(1).strip()

    # Besichtigungsdatum – auch "Besichtigungsdatum / -ort DD.MM.YYYY / Ort"
    bes_m = re.search(
        r"Besichtigung(?:sdatum)?[^0-9]{0,20}(\d{1,2}\.\d{1,2}\.\d{4})",
        text, re.IGNORECASE
    )
    if bes_m:
        result.besichtigungsdatum = _parse_datum_de(bes_m.group(1))

    # Auftragsdatum
    auf_m = re.search(
        r"(?:Auftragsdatum|Beauftragt am|Datum des Auftrags)[:\s]+"
        r"(\d{1,2}\.\d{1,2}\.\d{4})",
        text, re.IGNORECASE
    )
    if auf_m:
        result.auftragsdatum = _parse_datum_de(auf_m.group(1))
    elif not result.auftragsdatum:
        # Briefdatum als Fallback
        datum_m = re.search(
            r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text
        )
        if datum_m:
            result.auftragsdatum = _parse_datum_de(datum_m.group(0))

    # Schadennummer der Versicherung
    sn_m = re.search(
        r"(?:Schaden(?:nummer|-Nr\.?)|Ihre Schaden-Nr\.?)[:\s]+([A-Z0-9][A-Z0-9/\-\.\ ]{4,30}?)(?:\n|,|\s{2})",
        text, re.IGNORECASE
    )
    if sn_m:
        result.schadennummer_versicherung = sn_m.group(1).strip()

    # Versicherungsname
    # Muster 1: "Versicherung VHV" / "Versicherung Name Allianz Direct München" (Cassese-Format)
    vn_m = re.search(
        r"(?:^|\n)Versicherung(?:\s+Name)?\s+(.+?)(?:\n|$)",
        text, re.IGNORECASE
    )
    if vn_m:
        name_cand = vn_m.group(1).strip()
        # Nicht nehmen wenn es eine Adresszeile ist (enthält Straße, PLZ etc.)
        if not re.search(r"\d{5}|Straße|Platz|straße|platz|\bstr\b", name_cand, re.IGNORECASE):
            result.versicherung_name = name_cand

    # Versicherungsscheinnummer / Policennummer
    vs_m = re.search(
        r"(?:Versicherungsschein(?:nummer)?|Policen(?:nummer|-Nr\.?)|VS-Nr\.?|Police)[:\s]+([A-Z0-9][A-Z0-9/\-\.]{4,30})",
        text, re.IGNORECASE
    )
    if vs_m:
        result.versicherungsschein_nummer = vs_m.group(1).strip()


# ══════════════════════════════════════════════════════════════════════════════
# KONFIDENZ-BERECHNUNG
# ══════════════════════════════════════════════════════════════════════════════

def _calc_konfidenz(result: GutachtenParseResult) -> float:
    punkte = 0
    if result.sv_buero:                  punkte += 2
    if result.fahrzeug.kennzeichen:      punkte += 2
    if result.fahrzeug.hersteller:       punkte += 1
    if result.reparaturkosten_netto or result.reparaturkosten_brutto: punkte += 3
    if result.wiederbeschaffungswert:    punkte += 2
    if result.schadenart != "reparaturschaden" or result.reparaturkosten_netto: punkte += 1
    if result.sv_kosten_netto or result.sv_kosten_brutto: punkte += 1
    return round(min(punkte / 12.0, 1.0), 3)


# ══════════════════════════════════════════════════════════════════════════════
# HAUPT-PARSER
# ══════════════════════════════════════════════════════════════════════════════

def parse_gutachten(text: str, sv_buero_hint: str = "") -> GutachtenParseResult:
    """
    Haupt-Einstieg für den Gutachten-Parser.

    Args:
        text:          Normalisierter PDF-Text
        sv_buero_hint: Optional bereits erkanntes SV-Büro aus Classifier

    Returns:
        GutachtenParseResult
    """
    result = GutachtenParseResult()
    text_lower = text.lower()

    # SV-Büro
    result.sv_buero = sv_buero_hint or _detect_sv_buero(text_lower, text)

    # Metadaten
    _extract_meta(text, result)

    # Fahrzeug
    result.fahrzeug = _extract_fahrzeug(text)

    # Beträge
    _extract_betraege(text, result)

    # Schadenart
    _detect_schadenart(text, result)

    # Warnungen
    if not result.reparaturkosten_netto and not result.reparaturkosten_brutto:
        if result.schadenart == "reparaturschaden":
            result.warnungen.append(
                "Reparaturkosten konnten nicht extrahiert werden – bitte manuell prüfen."
            )
    if not result.wiederbeschaffungswert and result.schadenart == "totalschaden":
        result.warnungen.append(
            "Wiederbeschaffungswert konnte nicht extrahiert werden."
        )
    if not result.fahrzeug.kennzeichen:
        result.warnungen.append("KFZ-Kennzeichen nicht erkannt.")

    # Konfidenz
    result.konfidenz = _calc_konfidenz(result)

    return result
