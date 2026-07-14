"""
LLM-Service – lokales KI-Parsing via LM Studio
================================================
Verbindet sich mit einem lokalen LM Studio Server (OpenAI-kompatible API).

Konfiguration via Umgebungsvariablen:
  LLM_BASE_URL   – LM Studio API-Endpunkt  (Standard: http://localhost:1234/v1)
  LLM_MODEL      – Standard-Modell-ID      (Standard: qwen3.5-9b)
  LLM_MODELS     – Komma-getrennte Liste verfügbarer Modelle (Standard: LLM_MODEL)
  LLM_ENABLED    – "true" / "false"         (Standard: false)
  LLM_TIMEOUT    – Sekunden                 (Standard: 60)

Öffentliche API:
  is_available()                            → bool
  get_active_model()                        → str
  set_active_model(model)                   → None
  get_available_models()                    → list[str]
  parse_abrechnung_raw(text, versicherer)   → dict | None  (Shadow-Mode)
  parse_abrechnung(text, versicherer)       → dict | None
  chat(prompt, system)                      → str | None   (Verbindungstest)
"""

import json
import logging
import os
import re
from typing import Optional

import requests as _requests

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Konfiguration
# ──────────────────────────────────────────────────────────────────────────────

_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1").rstrip("/")
_ENABLED  = os.environ.get("LLM_ENABLED",  "false").strip().lower() == "true"
_TIMEOUT  = int(os.environ.get("LLM_TIMEOUT", "60"))

_HEADERS  = {"Content-Type": "application/json"}

# ── Modell-Verwaltung (zur Laufzeit umschaltbar) ───────────────────────────────
_DEFAULT_MODEL       = os.environ.get("LLM_MODEL", "qwen3.5-9b").strip()
_aktives_modell: str = _DEFAULT_MODEL

# Verfügbare Modelle aus LLM_MODELS-Env (Komma-getrennt); Fallback: nur Default
_VERFUEGBARE_MODELLE: list = [
    m.strip()
    for m in os.environ.get("LLM_MODELS", _DEFAULT_MODEL).split(",")
    if m.strip()
]
if _aktives_modell not in _VERFUEGBARE_MODELLE:
    _VERFUEGBARE_MODELLE.insert(0, _aktives_modell)


def get_active_model() -> str:
    """Gibt das aktuell aktive Modell zurück."""
    return _aktives_modell


def ist_aktiviert() -> bool:
    """True, wenn LLM_ENABLED gesetzt ist (N-03 Degradations-Erkennung)."""
    return _ENABLED


def set_active_model(model: str) -> None:
    """Setzt das aktive Modell zur Laufzeit (kein Container-Neustart nötig)."""
    global _aktives_modell
    _aktives_modell = model
    logger.info("LLM-Modell gewechselt zu: %s", model)


def get_available_models() -> list:
    """Gibt die Liste aller konfigurierten Modelle zurück."""
    return list(_VERFUEGBARE_MODELLE)


def init_from_db() -> None:
    """
    Lädt das gespeicherte Modell aus der DB und setzt es als aktives Modell.
    Wird beim App-Start aufgerufen (app.py), damit das Modell sofort korrekt ist
    und nicht erst nach dem ersten Öffnen der Einstellungen-Seite.
    """
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT wert FROM konfiguration WHERE schluessel='llm_aktives_modell'"
            ).fetchone()
            if row and row["wert"]:
                set_active_model(row["wert"])
                logger.info("LLM-Modell aus DB geladen: %s", row["wert"])
            else:
                logger.info("Kein LLM-Modell in DB – behalte Standard: %s", _aktives_modell)
    except Exception as e:
        logger.warning("LLM-Modell-Init aus DB fehlgeschlagen (nicht kritisch): %s", e)


# ──────────────────────────────────────────────────────────────────────────────
# System-Prompt – kompakt, für Qwen3.5 optimiert
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Du extrahierst Abrechnungsdaten aus deutschen Kfz-Versicherungsschreiben.
Antworte NUR mit dem JSON-Objekt, kein erklärender Text davor oder danach.

Ausgabe-Schema:
{
  "positionen": [
    {"art": "wbw", "bezeichnung": "...", "betrag_netto": 0.00, "betrag_brutto": null},
    ...
  ],
  "gesamtbetrag": 0.00,
  "zahlungen": [{"empfaenger": "kanzlei", "betrag": 0.00}],
  "abrechnungsart": "totalschaden"
}

Regeln:
- Nur Werte übernehmen, die explizit im Text stehen – niemals erfinden
- Dezimaltrennzeichen: Punkt, kein Tausend-Punkt  (5.035,00 EUR → 5035.00)
- OCR-Rauschen: Leerzeichen in Zahlen ignorieren ("8 500,00" → 8500.00, "1 . 200 , 00" → 1200.00)
- Nicht erkennbare Werte: null
- Jede Schadensposition als eigenes Objekt in "positionen"
- Bei Nutzungsausfall mit Tagesrate (z. B. "14 x 43 EUR : 602,00 EUR" oder \
"14 Tage x 43,00 EUR") immer den Gesamtbetrag nehmen (602.00), nicht die Tagesrate (43.00)
- Wenn "überwiesen", "letztgenannter Betrag" oder "auf das Konto" steht → empfaenger: "kanzlei"
- "Regulierungsbetrag", "Entschädigungsbetrag", "Auszahlungsbetrag" → das ist der gesamtbetrag
- "abzüglich Restwert" → Restwert als eigene Position mit dem abgezogenen Betrag (positiver Wert)
- WBW (Wiederbeschaffungswert) immer als Bruttowert vor Abzügen erfassen
- Wenn nur Nettobetrag ohne MwSt-Angabe → betrag_netto setzen, betrag_brutto: null

Erlaubte Werte für "art":
  wbw | wba | restwert | reparatur_netto | reparatur_brutto | sv_kosten |
  nutzungsausfall | abschleppkosten | restkraftstoff | kostenpauschale |
  wertminderung | sonstiges

Synonyme für "art" (intern mappen):
  Wiederbeschaffungswert → wbw
  Wiederbeschaffungsaufwand, WBA → wba  (= WBW minus Restwert; der tatsächliche Fahrzeugschadenbetrag)
  Sachverständigenkosten, Gutachterkosten, SV-Honorar → sv_kosten
  Nutzungsausfallentschädigung, Nutzungsausfallschaden → nutzungsausfall
  Wertminderung, Merkantile Wertminderung → wertminderung
  Unkostenpauschale, Kostenpauschale, Auslagenpauschale → kostenpauschale
  Abschleppkosten, Bergungskosten → abschleppkosten

WBA-Regel (Totalschaden):
  Wenn WBA (Wiederbeschaffungsaufwand) im Text steht: WBW, Restwert UND WBA alle als eigene Positionen erfassen.
  WBA = betrag_netto setzen (das ist der Nettofahrzeugschadenbetrag).
  Als Zahlung (zahlungen[].betrag) den WBA-Betrag + alle weiteren Positionen nehmen → ergibt den gesamtbetrag.

SV-Kosten-Regel:
  Bei Sachverständigenkosten gibt es oft eine Aufschlüsselung: Teilposten → Netto → USt → Brutto.
  Immer den BRUTTOBETRAG (nach USt) nehmen → betrag_brutto setzen (nicht betrag_netto).
  Wenn nur ein Betrag ohne Netto/Brutto-Unterscheidung: betrag_netto setzen.

Erlaubte Werte für "abrechnungsart": totalschaden | reparatur_fiktiv | reparatur_konkret | unbekannt
Erlaubte Werte für "empfaenger": kanzlei | sv_buero | sonstige

--- Beispiel 1 (Standard) ---
Eingabe:
  Nutzungsausfall 10 x 38 EUR : 380,00 EUR
  Abschleppkosten : 210,50 EUR
  Gesamtbetrag : 590,50 EUR
  Letztgenannter Betrag wird auf Ihr Konto überwiesen.

Ausgabe:
{
  "positionen": [
    {"art": "nutzungsausfall", "bezeichnung": "Nutzungsausfall", "betrag_netto": 380.00, "betrag_brutto": null},
    {"art": "abschleppkosten", "bezeichnung": "Abschleppkosten", "betrag_netto": 210.50, "betrag_brutto": null}
  ],
  "gesamtbetrag": 590.50,
  "zahlungen": [{"empfaenger": "kanzlei", "betrag": 590.50}],
  "abrechnungsart": "totalschaden"
}

--- Beispiel 2 (Generali / Totalschaden mit WBA und SV-Kosten-Aufschlüsselung) ---
Eingabe:
  Entschädigungsberechnung
  Wiederbeschaffungswert                              8.500,00 EUR
  abzüglich Restwert                                  1.200,00 EUR
  Wiederbeschaffungsaufwand                           7.300,00 EUR
  Nutzungsausfallentschädigung  14 Tage x 43,00 EUR    602,00 EUR
  Sachverständigenkosten
    Grundhonorar                                      1.620,50 EUR
    Fahrtkosten                                         150,00 EUR
    Netto                                             1.770,50 EUR
    zzgl. 19% USt.                                      336,40 EUR
    Brutto                                            2.106,90 EUR
  Kostenpauschale                                        25,00 EUR
  Regulierungsbetrag                                 10.033,90 EUR
  Wir überweisen diesen Betrag auf das Konto Ihrer Rechtsanwältin.

Ausgabe:
{
  "positionen": [
    {"art": "wbw",            "bezeichnung": "Wiederbeschaffungswert",       "betrag_netto": 8500.00, "betrag_brutto": null},
    {"art": "restwert",       "bezeichnung": "Restwert",                     "betrag_netto": 1200.00, "betrag_brutto": null},
    {"art": "wba",            "bezeichnung": "Wiederbeschaffungsaufwand",    "betrag_netto": 7300.00, "betrag_brutto": null},
    {"art": "nutzungsausfall","bezeichnung": "Nutzungsausfallentschädigung", "betrag_netto": 602.00,  "betrag_brutto": null},
    {"art": "sv_kosten",      "bezeichnung": "Sachverständigenkosten",       "betrag_netto": null,    "betrag_brutto": 2106.90},
    {"art": "kostenpauschale","bezeichnung": "Kostenpauschale",              "betrag_netto": 25.00,   "betrag_brutto": null}
  ],
  "gesamtbetrag": 10033.90,
  "zahlungen": [{"empfaenger": "kanzlei", "betrag": 10033.90}],
  "abrechnungsart": "totalschaden"
}
--- Ende Beispiele ---\
"""

# ──────────────────────────────────────────────────────────────────────────────
# System-Prompt – Kfz-Sachverständigen-Gutachten
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_GUTACHTEN = """\
Du extrahierst Schadenpositionen aus deutschen Kfz-Sachverständigen-Gutachten.
Antworte NUR mit dem JSON-Objekt, kein erklärender Text davor oder danach.

Ausgabe-Schema:
{
  "reparaturkosten_netto":        0.00,
  "wiederbeschaffungswert":       0.00,
  "restwert":                     0.00,
  "wertminderung":                0.00,
  "nutzungsausfall_tagessatz":    0.00,
  "nutzungsausfall_tage":         0,
  "sv_kosten_netto":              0.00,
  "schadenart":                   "reparaturschaden"
}

Regeln:
- Nur Werte übernehmen, die explizit im Text stehen – niemals erfinden
- Dezimaltrennzeichen: Punkt, kein Tausend-Punkt  (5.035,00 EUR → 5035.00)
- OCR-Rauschen: Leerzeichen in Zahlen ignorieren ("8 500,00" → 8500.00)
- Nicht erkennbare Werte: null
- reparaturkosten_netto: Netto-Reparaturkosten (ohne MwSt.) – NICHT der Bruttobetrag
- wiederbeschaffungswert: WBW (Fahrzeugwert, vor Abzügen); null wenn "ausreichend" oder kein Totalschaden
- restwert: Restwert des beschädigten Fahrzeugs; null wenn kein Totalschaden
- wertminderung: Merkantile Wertminderung; null wenn keine angegeben
- nutzungsausfall_tagessatz: Tagessatz lt. NA-Tabelle (z.B. 43,00 für Klasse G)
- nutzungsausfall_tage: Geschätzte Reparatur- / Ausfalltage (Integer)
- sv_kosten_netto: SV-Honorar netto (ohne MwSt.); NICHT der Bruttobetrag
- schadenart: "reparaturschaden" | "totalschaden" | "grenzfall"

Erlaubte Werte für "schadenart":
  reparaturschaden – Reparatur wirtschaftlich sinnvoll
  totalschaden     – Wirtschaftlicher oder technischer Totalschaden
  grenzfall        – Reparaturkosten nahe der 130%-Grenze

--- Beispiel 1 (Reparaturschaden) ---
Eingabe:
  Reparaturkosten netto: 5.235,00 EUR
  Bruttoreparaturkosten: 6.229,65 EUR
  Merkantile Wertminderung: 300,00 EUR
  Nutzungsausfall: Klasse G, 43,00 EUR/Tag, ca. 8 Tage
  Sachverständigengebühr netto: 780,00 EUR

Ausgabe:
{
  "reparaturkosten_netto":     5235.00,
  "wiederbeschaffungswert":    null,
  "restwert":                  null,
  "wertminderung":             300.00,
  "nutzungsausfall_tagessatz": 43.00,
  "nutzungsausfall_tage":      8,
  "sv_kosten_netto":           780.00,
  "schadenart":                "reparaturschaden"
}

--- Beispiel 2 (Totalschaden) ---
Eingabe:
  Wiederbeschaffungswert: 8.500,00 EUR
  Restwert: 1.200,00 EUR
  Gutachterhonorar netto: 820,50 EUR
  Wirtschaftlicher Totalschaden liegt vor.

Ausgabe:
{
  "reparaturkosten_netto":     null,
  "wiederbeschaffungswert":    8500.00,
  "restwert":                  1200.00,
  "wertminderung":             null,
  "nutzungsausfall_tagessatz": null,
  "nutzungsausfall_tage":      null,
  "sv_kosten_netto":           820.50,
  "schadenart":                "totalschaden"
}
--- Ende Gutachten-Beispiele ---\
"""

# ──────────────────────────────────────────────────────────────────────────────
# response_format – erzwingt valides JSON (LM Studio structured output)
# ──────────────────────────────────────────────────────────────────────────────

_RESPONSE_FORMAT = None  # LM Studio unterstützt response_format nicht – Prompt-Engineering reicht


# ──────────────────────────────────────────────────────────────────────────────
# Interne Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────

def _post_chat(
    messages: list,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    response_format: Optional[dict] = None,
) -> Optional[str]:
    """
    Ruft POST /v1/chat/completions auf und gibt den Antwort-Text zurück.
    Gibt None zurück bei Verbindungsfehlern, leerem Content oder ungültiger Antwort.
    """
    url     = f"{_BASE_URL}/chat/completions"
    payload = {
        "model":       get_active_model(),
        "messages":    messages,
        "temperature": temperature,
        "max_tokens":  max_tokens,
        "stream":      False,
    }
    if response_format:
        payload["response_format"] = response_format

    try:
        resp = _requests.post(url, json=payload, headers=_HEADERS, timeout=_TIMEOUT)
        if not resp.ok:
            logger.warning("LM Studio %d: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
        data    = resp.json()
        choice  = data["choices"][0]
        content = choice["message"].get("content") or ""
        finish  = choice.get("finish_reason", "?")
        usage   = data.get("usage", {})
        logger.info(
            "LM Studio: finish=%s tokens(prompt=%s completion=%s) content_len=%d",
            finish,
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
            len(content),
        )
        return content if content else None
    except _requests.exceptions.Timeout:
        logger.warning("LLM Timeout nach %ds (%s)", _TIMEOUT, url)
    except _requests.exceptions.ConnectionError as exc:
        logger.warning("LLM Verbindungsfehler: %s", exc)
    except Exception as exc:
        logger.warning("LLM Fehler (%s): %s", type(exc).__name__, exc)
    return None


def _parse_json_response(raw: str) -> Optional[dict]:
    """
    Extrahiert JSON aus LLM-Antwort.
    Fallback für Modelle die kein response_format unterstützen.
    """
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    text  = match.group(1) if match else raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r"\{[\s\S]+\}", text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
    logger.debug("LLM JSON-Parse fehlgeschlagen: %s", raw[:300])
    return None


def _validiere_abrechnung_dict(d: dict) -> bool:
    """Minimale Plausibilitätsprüfung – Schutz gegen Halluzinationen."""
    if not isinstance(d, dict):
        return False
    positionen = d.get("positionen")
    if positionen is not None and not isinstance(positionen, list):
        return False
    for p in (positionen or []):
        if not isinstance(p, dict) or "art" not in p:
            return False
        for b in (p.get("betrag_netto"), p.get("betrag_brutto")):
            if b is not None and not (0 < b < 500_000):
                return False
    return True


def _baue_messages(user_content: str) -> list:
    """
    /no_think deaktiviert den Qwen3/3.5-Reasoning-Modus.
    Direkte Ausgabe ohne <think>-Blöcke → kein Token-Budget für Reasoning verschwendet.
    """
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": f"/no_think\n\n{user_content}"},
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Öffentliche API
# ──────────────────────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Gibt True zurück wenn LM Studio erreichbar ist (GET /v1/models, Timeout 3s)."""
    if not _ENABLED:
        return False
    try:
        resp = _requests.get(f"{_BASE_URL}/models", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def chat(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """
    Sendet einen einzelnen Prompt und gibt die Antwort zurück.
    Wird für den Verbindungstest in den Einstellungen genutzt.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": f"/no_think\n\n{prompt}"})
    return _post_chat(messages, max_tokens=1024, temperature=0.3)


def parse_abrechnung_raw(text: str, versicherer: str = "") -> Optional[dict]:
    """
    Shadow-Mode: JSON-Extraktion ohne Plausibilitätsprüfung.
    response_format erzwingt valides JSON – _parse_json_response als Fallback.
    """
    versicherer_hinweis = f"Versicherer: {versicherer}\n\n" if versicherer else ""
    user_content = f"{versicherer_hinweis}Abrechnungsschreiben:\n{text[:10_000]}"

    raw = _post_chat(
        _baue_messages(user_content),
        max_tokens=1536,
        temperature=0.0,
        response_format=_RESPONSE_FORMAT,
    )
    if raw is None:
        return None

    # response_format garantiert valides JSON – Fallback-Parser nur zur Sicherheit
    result = _parse_json_response(raw)
    if result is None:
        logger.warning("LLM-Antwort konnte nicht als JSON geparst werden (Shadow-Mode)")
    return result


def parse_gutachten_raw(text: str) -> Optional[dict]:
    """
    Shadow-Mode: Extrahiert Gutachten-Schadenpositionen per LLM.
    Analoges Vorgehen zu parse_abrechnung_raw(), aber mit Gutachten-Prompt.
    """
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT_GUTACHTEN},
        {"role": "user",   "content": f"/no_think\n\nGutachten:\n{text[:10_000]}"},
    ]
    raw = _post_chat(messages, max_tokens=512, temperature=0.0)
    if raw is None:
        return None
    result = _parse_json_response(raw)
    if result is None:
        logger.warning("LLM-Antwort (Gutachten) konnte nicht als JSON geparst werden")
    return result


# ──────────────────────────────────────────────────────────────────────────────
# S1.6b — Klassifikator- und Extraktions-Bausteine fuer die neue Pipeline
# ──────────────────────────────────────────────────────────────────────────────
#
# Diese beiden Funktionen sind bewusst schlank gehalten. Sie sind der einzige
# LLM-Aufruf in backend/intake/klassifikator.py bzw. extraktion.py; damit
# bleibt der Shadow-Mode (parse_abrechnung_raw etc.) fuer den Alt-Pfad
# unangetastet.

_KLASSIFIKATOR_SYSTEM = """\
Du klassifizierst deutsche Kanzlei-Dokumente in eine EINZIGE geschlossene
Klasse aus einer vorgegebenen Liste. Halluziniere niemals ein Label, das
nicht in der Liste steht. Antworte NUR mit einem JSON-Objekt in genau der
Form: {"label": "<klasse>", "konfidenz": <0.0-1.0>}. Kein Fliesstext.
"""


def klassifiziere_geschlossen(labels, text: str):
    """Closed-label-Klassifikation (S1.6b Stufe 2, F-11).

    Args:
        labels: Iterable geschlossener Klassennamen. Nur diese sind zulaessig.
        text:   Der zu klassifizierende Text (in der Regel Seite 1 + letzte
                Seite, je auf ~3000 Zeichen gekuerzt, siehe F-11 im
                Freigabe-Dokument).

    Returns:
        (label, konfidenz). ``(None, 0.0)`` wenn das LLM nichts oder etwas
        Muell liefert, oder ein Label ausserhalb der geschlossenen Liste
        halluziniert.
    """
    label_liste = [str(x) for x in labels]
    if not label_liste:
        return (None, 0.0)

    user_content = (
        "Geschlossene Labelliste (waehle GENAU eines):\n"
        + "\n".join(f"- {lbl}" for lbl in label_liste)
        + "\n\nDokumenttext (Seite 1 + letzte Seite, gekuerzt):\n"
        + text
    )
    messages = [
        {"role": "system", "content": _KLASSIFIKATOR_SYSTEM},
        {"role": "user",   "content": f"/no_think\n\n{user_content}"},
    ]
    raw = _post_chat(messages, max_tokens=64, temperature=0.0)
    if not raw:
        return (None, 0.0)

    ergebnis = _parse_json_response(raw)
    if not isinstance(ergebnis, dict):
        return (None, 0.0)

    label = ergebnis.get("label")
    konfidenz = ergebnis.get("konfidenz")
    if label not in label_liste:
        return (None, 0.0)
    try:
        konfidenz_f = float(konfidenz) if konfidenz is not None else 0.0
    except (TypeError, ValueError):
        konfidenz_f = 0.0
    return (label, konfidenz_f)


_EXTRAKTOR_SYSTEM = """\
Du extrahierst strukturierte Felder aus einem deutschen Kanzlei-Dokument.
Antworte NUR mit einem JSON-Objekt, dessen Schluessel den vorgegebenen
Feldnamen entsprechen. Fehlt ein Wert im Text, setze den Feldwert auf null.
Erfinde niemals Werte, die nicht im Text stehen. Kein Fliesstext, nur JSON.
"""


def extrahiere_nach_schema(schema, text: str):
    """Extraktion nach vorgegebenem Feld-Schema (S1.6b).

    Args:
        schema: Mapping ``{feldname: typ}`` — die Schluessel werden im Prompt
                als geforderte Felder gelistet; die Typangaben helfen dem
                Modell, aber sie sind kein Response-Format-Constraint (LM
                Studio unterstuetzt kein response_format).
        text:   Volltext des Dokuments.

    Returns:
        dict der extrahierten Felder oder ``None`` bei Fehler (LLM nicht
        erreichbar, ungueltiges JSON, unerwarteter Typ).
    """
    if not isinstance(schema, dict) or not schema:
        return None

    felderbeschreibung = "\n".join(
        f"- {name} ({typ})" for name, typ in schema.items()
    )
    user_content = (
        "Extrahiere die folgenden Felder:\n"
        + felderbeschreibung
        + "\n\nDokumenttext:\n"
        + text[:10_000]
    )
    messages = [
        {"role": "system", "content": _EXTRAKTOR_SYSTEM},
        {"role": "user",   "content": f"/no_think\n\n{user_content}"},
    ]
    raw = _post_chat(messages, max_tokens=1024, temperature=0.0)
    if not raw:
        return None
    ergebnis = _parse_json_response(raw)
    if not isinstance(ergebnis, dict):
        return None
    return ergebnis


def parse_abrechnung(text: str, versicherer: str = "") -> Optional[dict]:
    """
    Parst ein Abrechnungsschreiben per LLM.

    Returns:
        Dict mit Schlüsseln 'positionen', 'gesamtbetrag', 'zahlungen', 'abrechnungsart'.
        None bei Fehler oder wenn LLM nicht verfügbar.
    """
    versicherer_hinweis = f"Versicherer: {versicherer}\n\n" if versicherer else ""
    user_content = f"{versicherer_hinweis}Abrechnungsschreiben:\n{text[:10_000]}"

    raw = _post_chat(
        _baue_messages(user_content),
        max_tokens=1536,
        temperature=0.0,
        response_format=_RESPONSE_FORMAT,
    )
    if raw is None:
        return None

    result = _parse_json_response(raw)
    if result is None:
        logger.warning("LLM-Antwort konnte nicht als JSON geparst werden")
        return None

    if not _validiere_abrechnung_dict(result):
        logger.warning("LLM-Ergebnis failed Plausibilitätsprüfung: %s", result)
        return None

    logger.info(
        "LLM-Parse erfolgreich: %d Positionen, Gesamtbetrag=%s",
        len(result.get("positionen", [])),
        result.get("gesamtbetrag"),
    )
    return result
