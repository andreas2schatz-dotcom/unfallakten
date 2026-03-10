"""
pdf_extractor.py – PDF-Text extrahieren und per Claude-API strukturieren

Ablauf:
  1. pdfplumber liest den Text aus der PDF
  2. Der Text wird an die Claude-API geschickt
  3. Claude gibt ein strukturiertes JSON zurück
  4. Das JSON wird validiert und zurückgegeben
"""

import json
import re
import os
from datetime import date
from pathlib import Path
from typing import Optional

import pdfplumber
import anthropic

# ──────────────────────────────────────────────────────────────
#  DATENSTRUKTUR  –  was wir aus dem Gutachten holen wollen
# ──────────────────────────────────────────────────────────────
GUTACHTEN_SCHEMA = {
    "gutachter_name":          None,   # str
    "gutachter_buero":         None,   # str
    "gutachtennummer":         None,   # str
    "gutachtendatum":          None,   # "YYYY-MM-DD"

    # Fahrzeugdaten
    "fahrzeug_marke":          None,   # str
    "fahrzeug_modell":         None,   # str
    "kennzeichen":             None,   # str
    "fahrgestellnummer":       None,   # str
    "erstzulassung":           None,   # "YYYY-MM-DD"
    "km_stand":                None,   # int

    # Schadenwerte
    "wiederbeschaffungswert":  None,   # float (EUR)
    "restwert":                None,   # float (EUR)
    "reparaturkosten_netto":   None,   # float (EUR)
    "reparaturkosten_brutto":  None,   # float (EUR)
    "wertminderung":           None,   # float (EUR)
    "mietwagenklasse":         None,   # str  z.B. "Klasse 4"
    "totalschaden":            False,  # bool

    # Unfallbeteiligte (soweit im Gutachten)
    "auftraggeber_name":       None,   # str (= Mandant)
    "auftraggeber_strasse":    None,
    "auftraggeber_plz":        None,
    "auftraggeber_ort":        None,

    # Versicherung des Gegners (falls angegeben)
    "versicherung_name":       None,
    "schadennummer":           None,
}


SYSTEM_PROMPT = """Du bist ein Datenextraktions-Assistent für eine Rechtsanwaltskanzlei.
Du bekommst den Textinhalt eines KFZ-Schadengutachtens und extrahierst daraus strukturierte Daten.

REGELN:
- Antworte AUSSCHLIESSLICH mit einem JSON-Objekt, kein Text davor oder danach.
- Nutze exakt die vorgegebenen Schlüssel.
- Beträge immer als Zahl (Float), ohne Währungszeichen, ohne Tausenderpunkte.
  Beispiel: "6.200,50 €" → 6200.50
- Datumsangaben immer als "YYYY-MM-DD".
  Beispiel: "15. März 2024" → "2024-03-15"
- Wenn ein Wert nicht gefunden werden kann, setze null.
- totalschaden: true wenn Totalschaden oder wirtschaftlicher Totalschaden, sonst false.
"""

USER_PROMPT_TEMPLATE = """Extrahiere aus folgendem Gutachtentext alle verfügbaren Daten.

Verwende dieses JSON-Schema (alle Schlüssel müssen enthalten sein):
{schema}

Gutachtentext:
---
{text}
---

Antworte nur mit dem ausgefüllten JSON."""


def extract_text_from_pdf(pdf_path: str) -> str:
    """Liest den gesamten Text einer PDF-Datei mit pdfplumber."""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def extract_data_with_claude(pdf_text: str, api_key: Optional[str] = None) -> dict:
    """
    Schickt den PDF-Text an Claude und bekommt strukturiertes JSON zurück.

    DSGVO-Hinweis: Nutze entweder
      a) Anthropic Cloud + Data Processing Agreement (DPA)
      b) Lokales LLM (Ollama) – dafür extract_data_with_ollama() verwenden
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("Kein ANTHROPIC_API_KEY gesetzt. Bitte in .env eintragen.")

    client = anthropic.Anthropic(api_key=key)

    # Text auf max. 8.000 Zeichen kürzen (Gutachten sind meist kürzer)
    truncated_text = pdf_text[:8000]

    user_prompt = USER_PROMPT_TEMPLATE.format(
        schema=json.dumps(GUTACHTEN_SCHEMA, ensure_ascii=False, indent=2),
        text=truncated_text
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw_response = message.content[0].text
    return _parse_json_response(raw_response)


def extract_data_with_ollama(pdf_text: str, model: str = "llama3") -> dict:
    """
    Alternative: Lokales LLM via Ollama (DSGVO-konform, kein Cloud-Versand).
    Voraussetzung: `ollama serve` läuft lokal, Modell ist geladen.
    pip install ollama
    """
    try:
        import ollama
    except ImportError:
        raise ImportError("pip install ollama")

    truncated_text = pdf_text[:6000]
    user_prompt = USER_PROMPT_TEMPLATE.format(
        schema=json.dumps(GUTACHTEN_SCHEMA, ensure_ascii=False, indent=2),
        text=truncated_text
    )

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt}
        ]
    )

    raw_response = response["message"]["content"]
    return _parse_json_response(raw_response)


def _parse_json_response(raw: str) -> dict:
    """Bereinigt die KI-Antwort und parsed das JSON."""
    # Markdown-Fences entfernen falls vorhanden
    clean = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as e:
        raise ValueError(f"KI-Antwort ist kein gültiges JSON: {e}\nAntwort: {raw[:300]}")

    # Fehlende Schlüssel mit None auffüllen
    for key in GUTACHTEN_SCHEMA:
        if key not in data:
            data[key] = None

    return data


# ──────────────────────────────────────────────────────────────
#  HAUPTFUNKTION  –  wird vom FastAPI-Router aufgerufen
# ──────────────────────────────────────────────────────────────
def process_gutachten_pdf(
    pdf_path: str,
    use_local_llm: bool = False,
    ollama_model: str = "llama3"
) -> dict:
    """
    Vollständiger Pipeline-Schritt:
      PDF → Text → KI-Extraktion → strukturiertes Dict

    Args:
        pdf_path:       Pfad zur PDF-Datei
        use_local_llm:  True = Ollama (lokal, DSGVO-konform)
                        False = Claude API (Cloud, DPA erforderlich)
        ollama_model:   Modellname für Ollama

    Returns:
        Dict mit extrahierten Gutachtendaten + Rohtext
    """
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF nicht gefunden: {pdf_path}")

    print(f"📄  Lese PDF: {pdf_path}")
    pdf_text = extract_text_from_pdf(pdf_path)

    if not pdf_text.strip():
        raise ValueError("PDF konnte nicht gelesen werden (möglicherweise gescannt/bildbasiert).")

    print(f"📝  {len(pdf_text)} Zeichen extrahiert. Starte KI-Analyse...")

    if use_local_llm:
        extracted = extract_data_with_ollama(pdf_text, model=ollama_model)
        print("🤖  Daten via lokales LLM extrahiert.")
    else:
        extracted = extract_data_with_claude(pdf_text)
        print("🤖  Daten via Claude API extrahiert.")

    extracted["_pdf_rohtext"] = pdf_text   # für Debugging / manuelle Prüfung

    return extracted
