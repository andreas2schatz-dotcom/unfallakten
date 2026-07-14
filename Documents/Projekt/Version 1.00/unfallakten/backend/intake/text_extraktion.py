"""
Seitenweise Textgewinnung mit Zeichensalat-Check (S1.6a).

Fuer jede Seite eines PDF:
  * Textebene mit pdfplumber ziehen.
  * Zeichensalat-Ratio pruefen (Anteil "unerwarteter" Zeichen).
  * Wenn Ratio zu hoch ODER Wortzahl zu niedrig -> ``braucht_ocr=True``.

Der eigentliche OCR-Aufruf lebt im Pipeline-Schritt (S1.6a-6). Diese Modul
sagt nur: "diese Seite braucht OCR" bzw. "Textebene ist brauchbar".
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

# Schwellenwerte
MIN_WOERTER_TEXTEBENE = 5      # < 5 Woerter -> braucht OCR
MAX_ZEICHENSALAT_RATIO = 0.30  # > 30% "Rausch"-Zeichen -> braucht OCR
MIN_KONFIDENZ_WORT = 30              # Tesseract-Konfidenz-Schwelle (N-04)
MAX_TEXT_ABDECKUNG_BILDSEITE = 0.12  # < 12% Textflaeche -> Bildseite (N-04)
# N-01: Woerterbuch-Abgleich. Eine dichte Seite (viele Woerter), deren Text
# aber kaum echte deutsche Woerter/Rechtsbegriffe enthaelt, stammt aus einer
# korrupten Font-Kodierung (CID-Mapping-Bruch): niedrige Zeichensalat-Ratio,
# hohe Wortzahl, trotzdem Kauderwelsch -> harter Fallback auf Bild-Rendering.
MIN_WOERTER_FUER_WB_CHECK = 20  # erst ab dieser Dichte greift der WB-Check
MIN_WOERTERBUCH_QUOTE = 0.10    # < 10% Woerterbuch-Treffer bei Dichte -> OCR

# Haeufige deutsche Funktionswoerter + Kanzlei-/Rechts-/Rechnungsbegriffe.
# ASCII-transliteriert (ae/oe/ue/ss), damit sowohl "ueber" als auch "über"
# nach der Normalisierung in woerterbuch_quote treffen.
_WOERTERBUCH = frozenset("""
der die das den dem des ein eine einen einem eines und oder aber auch noch nur
schon sehr mehr wir uns unser unsere unserem unseren ihnen ihre ihrer ihrem sie
er es ich man wird werden wurde worden ist sind war waren sein haben hat hatte
kann koennen muss muessen soll sollen bitte bitten wollen in im an auf aus bei
mit nach von vor zu zum zur ueber unter fuer durch gegen ohne um bis ab als am
dass wenn weil dann hier dort oben unten nicht kein keine dieser diese dieses
diesem diesen welche welcher jede jeder alle allen beim vom hiermit daher somit
sowie bereits jedoch dabei damit gemaess wegen sowohl geehrte geehrter sehr
damen herren angelegenheit schreiben mitteilung antwort frage betreff bezug
rechnung betrag summe gesamt gesamtbetrag netto brutto mehrwertsteuer mwst
umsatzsteuer ust steuer datum tag monat jahr euro eur nummer nr kunde konto
zahlung zahlen ueberweisung faellig frist termin position menge preis anzahl
schaden schadennummer schadenfall versicherung versicherer versicherten
gutachten gutachter sachverstaendiger sachverstaendigen honorar fahrzeug kfz
kennzeichen reparatur reparaturkosten werkstatt wiederbeschaffungswert restwert
wertminderung nutzungsausfall unfall unfalltag haftung haftpflicht anspruch
ansprueche forderung forderungen mandant mandanten mandantschaft auftraggeber
kanzlei rechtsanwalt rechtsanwaelte anwalt gericht amtsgericht landgericht
klage urteil beschluss verfahren akte aktenzeichen vollmacht partei beklagte
klaeger geschaedigte unfallgegner name vorname strasse ort plz adresse
""".split())


def _transliteriere(text: str) -> str:
    return (text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                .replace("ß", "ss"))

# Erlaubte Zeichen (DE-Texte, uebliche Interpunktion und Zahlen).
# Mehrzeilig, damit auch Whitespace/Zeilenumbrueche zaehlen.
_ERLAUBT_REGEX = re.compile(
    r"[A-Za-z0-9ÄÖÜäöüß"
    r" \t\r\n"
    r".,;:!?\-()\[\]{}\"'`´/#§€%&+*=<>@_"
    r"]"
)


@dataclass
class SeitenText:
    nr: int
    text: str
    braucht_ocr: bool
    ratio_salat: float
    textquelle: Optional[str] = None  # "textebene" | "ocr" - wird spaeter gesetzt
    quote_woerter: float = 1.0        # N-01: Woerterbuch-Trefferquote
    hat_tabelle: bool = False         # N-06: Seite traegt eine Tabelle
    ist_bildseite: bool = False       # N-04: Foto-/Bildseite, kein GLM


def zeichensalat_ratio(text: str) -> float:
    """Anteil der Zeichen, die NICHT ins erwartete deutsche Schrift-/Zahl-Alphabet fallen.

    Leerer Text -> 1.0 (maximaler Salat, weil unbrauchbar).
    """
    if not text:
        return 1.0
    gesamt = len(text)
    ok = len(_ERLAUBT_REGEX.findall(text))
    return 1.0 - (ok / gesamt)


def woerterbuch_quote(text: str) -> float:
    """Anteil der Wort-Token, die im DE-/Rechts-Woerterbuch stehen (N-01).

    Umlaute werden vor dem Abgleich transliteriert, damit "ueber" und "über"
    gleich behandelt werden. Token < 2 Buchstaben zaehlen nicht mit.
    Leerer/wortloser Text -> 0.0 (kein Treffer moeglich).
    """
    tokens = [t for t in re.findall(r"[a-z]+", _transliteriere(text.lower()))
              if len(t) >= 2]
    if not tokens:
        return 0.0
    treffer = sum(1 for t in tokens if t in _WOERTERBUCH)
    return treffer / len(tokens)


def text_abdeckung(wort_boxen: List[dict], seiten_flaeche: float) -> float:
    """Anteil der Seitenflaeche, der von sicherem Text bedeckt ist (N-04).

    Summe der Flaechen der Wort-Boxen mit conf >= MIN_KONFIDENZ_WORT und
    nichtleerem Text, geteilt durch seiten_flaeche. Ueberlappungen werden nicht
    abgezogen (Woerter ueberlappen praktisch nie). Auf [0, 1] geklemmt.
    """
    if not wort_boxen or seiten_flaeche <= 0:
        return 0.0
    summe = 0.0
    for b in wort_boxen:
        try:
            conf = float(b.get("conf", -1))
        except (TypeError, ValueError):
            continue
        if conf < MIN_KONFIDENZ_WORT:
            continue
        if not (b.get("text") or "").strip():
            continue
        summe += float(b.get("breite", 0)) * float(b.get("hoehe", 0))
    return min(1.0, summe / seiten_flaeche)


def ist_bildseite(abdeckung: float) -> bool:
    """True, wenn die Textabdeckung unter der Bildseiten-Schwelle liegt (N-04)."""
    return abdeckung < MAX_TEXT_ABDECKUNG_BILDSEITE


def extrahiere_seiten(pdf_bytes: bytes, max_seiten: int = 30) -> List[SeitenText]:
    """Extrahiert die Textebene je Seite und entscheidet, ob OCR noetig ist.

    Bei fehlender/kaputter Textebene wird die Seite als ``braucht_ocr`` markiert;
    ``text`` bleibt leer. Der OCR-Aufruf passiert im Pipeline-Schritt.
    """
    import pdfplumber

    ergebnis: List[SeitenText] = []
    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as exc:
        logger.error("PDF-Oeffnen fehlgeschlagen: %s", exc)
        return ergebnis

    try:
        n = min(len(pdf.pages), max_seiten)
        for i, page in enumerate(pdf.pages[:n]):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                logger.warning("Seite %d: Textextraktion Fehler: %s", i + 1, exc)
                text = ""

            try:
                hat_tabelle = bool(page.find_tables())
            except Exception as exc:
                logger.warning("Seite %d: Tabellensuche Fehler: %s", i + 1, exc)
                hat_tabelle = False

            woerter = len(text.split())
            ratio = zeichensalat_ratio(text)
            quote = woerterbuch_quote(text)

            # N-01: dichte Seite ohne Woerterbuch-Treffer = korrupte Font-
            # Kodierung -> OCR erzwingen, obwohl der Zeichensalat-Check "sauber"
            # meldet.
            korrupte_font = (woerter >= MIN_WOERTER_FUER_WB_CHECK and
                             quote < MIN_WOERTERBUCH_QUOTE)
            braucht_ocr = (woerter < MIN_WOERTER_TEXTEBENE or
                           ratio > MAX_ZEICHENSALAT_RATIO or
                           korrupte_font)

            ergebnis.append(SeitenText(
                nr=i + 1,
                text="" if braucht_ocr else text,
                braucht_ocr=braucht_ocr,
                ratio_salat=ratio,
                quote_woerter=round(quote, 3),
                hat_tabelle=hat_tabelle,
                textquelle=None if braucht_ocr else "textebene",
            ))
    finally:
        pdf.close()
    return ergebnis


def waehle_extraktions_text(seiten: List[SeitenText],
                            regex_muster: List[str]) -> str:
    """Waehlt die fuer die Feld-Extraktion relevanten Seiten (N-06).

    Statt der ersten 10.000 Zeichen erhaelt die LLM-Extraktion gezielt:
    Seite 1 + letzte Seite + Seiten mit Regex-Treffer + Seiten mit Tabelle.
    Liefert den konkatenierten Text der ausgewaehlten Seiten in Seitenreihen-
    folge. Ein- oder Null-Seiten-Faelle liefern den Gesamttext unveraendert.

    Die Klassifikation bleibt hiervon unberuehrt (F-11) -- sie nutzt weiterhin
    Seite 1 + letzte Seite direkt im Pipeline-Schritt.
    """
    if not seiten:
        return ""

    muster_kompiliert = []
    for m in regex_muster or ():
        try:
            muster_kompiliert.append(re.compile(m))
        except re.error:
            continue

    n = len(seiten)
    ausgewaehlt = {0, n - 1}
    for i, s in enumerate(seiten):
        if s.hat_tabelle:
            ausgewaehlt.add(i)
            continue
        if s.text and any(p.search(s.text) for p in muster_kompiliert):
            ausgewaehlt.add(i)

    return "\n\n".join(seiten[i].text for i in sorted(ausgewaehlt)
                       if seiten[i].text)


def dokument_ocr_qualitaet(seiten: List[SeitenText]):
    """Dokument-Level OCR-Qualitaet als Schlechteste-Seite-Aggregat (N-02).

    Liefert ``(ratio_salat, quote_woerter)`` -- den groessten (schlechtesten)
    Zeichensalat-Anteil und die kleinste (schlechteste) Woerterbuch-Quote
    ueber alle texttragenden Seiten. Gerechnet auf dem FINALEN Seitentext
    (nach OCR), nicht auf den ggf. veralteten Vor-OCR-Stempeln -- ein sauber
    OCR'tes Scan-Dokument soll nicht als schlecht gelten. Seiten ohne Text
    (leerer OCR-Ausfall) bleiben unberuecksichtigt. Ohne texttragende Seite:
    ``(None, None)``.
    """
    texte = [s.text for s in seiten if s.text and s.text.strip()]
    if not texte:
        return (None, None)
    ratio = max(zeichensalat_ratio(t) for t in texte)
    quote = min(woerterbuch_quote(t) for t in texte)
    return (round(ratio, 3), round(quote, 3))


def aggregierte_textquelle(seiten: List[SeitenText]) -> str:
    """Aggregiert die Seiten-textquelle zu einem Dokument-Level-Stempel.

    Bildseiten (N-04) bleiben unberuecksichtigt. Ein Dokument, das nur aus
    Bildseiten besteht, gilt als 'ocr' (bleibt im gueltigen Spalten-CHECK).
    """
    if not seiten:
        return "textebene"
    nicht_bild = [s for s in seiten if not s.ist_bildseite]
    if not nicht_bild:
        return "ocr"
    quellen = {s.textquelle for s in nicht_bild if s.textquelle}
    if len(quellen) == 1:
        return quellen.pop()
    return "gemischt"
