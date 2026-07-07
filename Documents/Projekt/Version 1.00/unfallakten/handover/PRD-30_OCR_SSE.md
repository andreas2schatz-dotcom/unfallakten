# PRD-30 – OCR + Streaming-Parser für Bild-PDFs
> Erstellt: 2026-04-12 · Status: Planung abgeschlossen

---

## Problem

Gescannte PDFs (z. B. Generali 335/22) liefern 0–2 Zeichen extrahierten Text.
Weder Regex-Parser noch LLM können ohne Text arbeiten.

Log-Beweis:
```
Dok 159: Zu wenig Text extrahiert (2 Zeichen).
Dok 161: Zu wenig Text extrahiert (0 Zeichen).
LLM Shadow: Regex=0.00 LLM=0.00 Konflikt=False
```

---

## Lösung

### Stufe 1 – OCR (lokal, DSGVO-konform)
- **Bibliotheken:** `pytesseract` + `pdf2image` (wrappt Tesseract + Poppler)
- **Kein Cloud-Dienst** – alles läuft im Docker-Container
- **Ausgabe:** reiner Python-String (kein Text-PDF)
- **Sprache:** `deu` (deutsches Tesseract-Sprachpaket)
- **DPI:** 300 für gute Erkennungsqualität bei A4-Briefen

### Stufe 2 – SSE-Streaming (Fortschrittsanzeige)
Statt des bisherigen synchronen Endpoints ein **Server-Sent Events**-Stream:
```
POST /akten/{az}/dokumente/{id}/parsen-stream
Content-Type: text/event-stream

data: {"schritt": "ocr",   "status": "laeuft"}
data: {"schritt": "ocr",   "status": "fertig", "zeichen": 2840}
data: {"schritt": "regex", "status": "laeuft"}
data: {"schritt": "regex", "status": "fertig", "positionen": 4}
data: {"schritt": "llm",   "status": "laeuft"}
data: {"schritt": "llm",   "status": "fertig", "gesamtbetrag": 7971.51}
data: {"schritt": "fertig","ergebnis": { ... vollständiges Parse-Ergebnis ... }}
```

---

## Architektur-Änderungen

### Neue Datei: `backend/services/ocr_service.py`
```python
def ist_bild_pdf(has_image_pages: bool, text_laenge: int) -> bool:
    """True wenn OCR benötigt wird."""
    return has_image_pages or text_laenge < 50

def ocr_text(pdf_bytes: bytes, lang: str = "deu") -> str:
    """Konvertiert Bild-PDF-Seiten zu Text via Tesseract."""
    from pdf2image import convert_from_bytes
    import pytesseract
    images = convert_from_bytes(pdf_bytes, dpi=300)
    return "\n\n".join(
        pytesseract.image_to_string(img, lang=lang)
        for img in images
    )
```

### Neue Route: `backend/routers/pdf_parse_routes.py`
```python
@bp.route("/<az>/dokumente/<int:dok_id>/parsen-stream", methods=["POST"])
@login_erforderlich
def parsen_stream(az, dok_id):
    def generate():
        # 1. PDF laden
        pdf_bytes = _lade_pdf_bytes(dok_id)
        full_text, has_image_pages = _extrahiere_text(pdf_bytes)

        # 2. OCR wenn nötig
        if ocr_service.ist_bild_pdf(has_image_pages, len(full_text)):
            yield sse("ocr", "laeuft")
            full_text = ocr_service.ocr_text(pdf_bytes)
            yield sse("ocr", "fertig", zeichen=len(full_text))

        # 3. Regex
        yield sse("regex", "laeuft")
        result = _fuehre_regex_aus(full_text, ...)
        yield sse("regex", "fertig", positionen=len(result.positionen))

        # 4. LLM
        if llm_aktiv:
            yield sse("llm", "laeuft")
            _llm_shadow(full_text, versicherer, result)
            yield sse("llm", "fertig", gesamtbetrag=result.llm_gesamtbetrag)

        yield sse("fertig", ergebnis=_result_zu_dict(result))

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
```

### Geänderte Datei: `dispatcher.py`
- `_fuehre_parser_aus()`: OCR-Text als optionaler Parameter (überschreibt PDF-Text)
- `_llm_shadow` wird aus dem Streaming-Endpoint aufgerufen (nicht mehr intern im Parser)

### Geänderte Datei: `frontend/src/sections/RegulierungSection.jsx`
- Bisheriger `fetch('/parsen')` → `EventSource('/parsen-stream')`
- Neue State-Variable `parseSchritte: []`
- Progress-Box während Import:
  ```
  ⟳ OCR läuft …          (nur wenn Bild-PDF)
  ✓ OCR abgeschlossen    (2.840 Zeichen erkannt)
  ⟳ Regex-Parser läuft …
  ✓ Regex: 4 Positionen
  ⟳ KI-Parsing läuft …
  ✓ KI: 7.971,51 €
  ```

---

## Docker / Dependencies

### `Dockerfile` (backend):
```dockerfile
# Tesseract + deutsches Sprachpaket + Poppler (für pdf2image)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-deu \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

### `requirements.txt`:
```
pytesseract>=0.3.10
pdf2image>=1.17.0
```

---

## Reihenfolge der Implementierung

1. `Dockerfile` + `requirements.txt` → `docker compose up --build`
2. `ocr_service.py` anlegen + testen mit Generali-Dok
3. Synchronen `/parsen`-Endpoint zunächst belassen, OCR dort einbauen (Schritt 3 → Grundfunktion)
4. SSE-Endpoint `/parsen-stream` als neuen Endpoint hinzufügen
5. Frontend auf SSE umstellen
6. Alten sync-Endpoint als Fallback behalten (für API-Nutzung ohne SSE)

---

## Kritische Dateien

| Datei | Änderung |
|---|---|
| `backend/services/ocr_service.py` | NEU |
| `backend/routers/pdf_parse_routes.py` | Neuer SSE-Endpoint |
| `backend/workflow/dispatcher.py` | OCR-Text-Parameter |
| `backend/Dockerfile` | tesseract + poppler |
| `backend/requirements.txt` | pytesseract + pdf2image |
| `frontend/src/sections/RegulierungSection.jsx` | EventSource + Progress-UI |

---

## Verifikation

- Generali 335/22: OCR erkennt Text → Positionen werden extrahiert
- Text-PDF (Gothaer): OCR wird übersprungen (`ist_bild_pdf=False`)
- Frontend zeigt Schritte live während des Parsens
- Kein Netzwerkaufruf außerhalb des Containers (DSGVO ✓)
