# Kanzlei Unfallverwaltung – Backend

Python/FastAPI-Backend für die Verwaltung von Unfallakten.

## Voraussetzungen

- Python 3.11+
- pip

---

## Installation

```bash
# 1. In den Projektordner wechseln
cd kanzlei-backend

# 2. Virtuelle Umgebung erstellen
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. Konfiguration einrichten
copy .env.example .env       # Windows
# cp .env.example .env       # Mac/Linux
# → .env mit echten Werten befüllen

# 5. Word-Vorlage in templates/ legen
# → Forderungsschreiben_Vorlage.docx in den Ordner "templates/" kopieren

# 6. Server starten
uvicorn main:app --reload --port 8000
```

API-Dokumentation: **http://localhost:8000/docs**

---

## Projektstruktur

```
kanzlei-backend/
├── main.py              ← FastAPI-App, alle Endpunkte
├── database.py          ← SQLAlchemy-Modelle + DB-Setup
├── pdf_extractor.py     ← PDF lesen + KI-Extraktion
├── word_generator.py    ← Forderungsschreiben generieren
├── requirements.txt
├── .env.example         ← Vorlage für Konfiguration
├── templates/
│   └── Forderungsschreiben_Vorlage.docx   ← Word-Vorlage
├── uploads/             ← hochgeladene PDFs (auto-erstellt)
├── ausgabe/             ← generierte Word-Dateien (auto-erstellt)
└── kanzlei.db           ← SQLite-Datenbank (auto-erstellt)
```

---

## Wichtigste API-Endpunkte

| Methode | Pfad | Beschreibung |
|---------|------|-------------|
| GET | `/unfaelle` | Alle Unfälle abrufen |
| POST | `/unfaelle` | Neuen Unfall anlegen |
| GET | `/unfaelle/{id}` | Dashboard für einen Unfall |
| PATCH | `/unfaelle/{id}` | Unfall aktualisieren |
| POST | `/beteiligte` | Mandant / Gegner / Zeuge anlegen |
| POST | `/fahrzeuge` | Fahrzeug anlegen |
| POST | `/versicherungen` | Versicherung anlegen |
| POST | `/gutachten/upload` | PDF hochladen + KI-Extraktion |
| POST | `/forderungen` | Forderung erfassen |
| POST | `/regulierungen` | Zahlung erfassen |
| POST | `/unfaelle/{id}/forderungsschreiben` | Word-Datei generieren + Download |
| GET | `/unfaelle/{id}/taetigkeiten` | Aktivitätshistorie |
| POST | `/taetigkeiten` | Manuelle Tätigkeit erfassen |

---

## DSGVO-Hinweis: PDF-Extraktion

### Option A – Claude API (Cloud)
Standard-Einstellung. Gutachtentext wird an Anthropic-Server übermittelt.
→ **Data Processing Agreement (DPA) mit Anthropic abschließen!**
→ https://www.anthropic.com/legal/dpa

### Option B – Lokales LLM (empfohlen für Produktion)
Kein Cloud-Versand, vollständig lokal, DSGVO-konform ohne DPA.

```bash
# 1. Ollama installieren: https://ollama.com
# 2. Modell herunterladen
ollama pull llama3

# 3. Beim PDF-Upload use_local_llm=true setzen (im API-Aufruf)
```

---

## Typischer Workflow

```
1. POST /unfaelle          → Akte anlegen (AZ, Unfalldatum, Ort)
2. POST /beteiligte        → Mandant anlegen (rolle: "mandant")
3. POST /beteiligte        → Gegner anlegen (rolle: "gegner")
4. POST /fahrzeuge         → Fahrzeug des Mandanten
5. POST /versicherungen    → Haftpflicht des Gegners
6. POST /gutachten/upload  → PDF hochladen → KI extrahiert Werte
7. POST /forderungen       → Beträge erfassen
8. POST /unfaelle/{id}/forderungsschreiben  → Word-Datei downloaden
9. POST /regulierungen     → Zahlung der Versicherung erfassen
```
