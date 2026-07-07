# Unfallakten-System – Architektur

Koch, Schatz & Kollegen · Rechtsanwaltskanzlei Offenbach  
Stand: 2026-05-02 · Schema v37+

---

## 1. Stack

| Schicht | Technologie | Version |
|---|---|---|
| **Sprache Backend** | Python | 3.12 |
| **Webframework** | Flask (Application Factory) | via requirements.txt |
| **WSGI (Produktion)** | Gunicorn | via requirements.txt |
| **Datenbank** | SQLite (Datei `unfallakten.db`) | stdlib |
| **ORM / Migrations** | SQLAlchemy 2.0.30 · Alembic 1.13.1 (vorbereitet für PostgreSQL) | — |
| **Auth** | JWT via `python-jose` 3.3.0 · Passwort-Hash via `passlib[bcrypt]` 1.7.4 | — |
| **PDF-Verarbeitung** | pdfplumber 0.11.1 · PyMuPDF 1.24.3 | — |
| **OCR** | Tesseract (tesseract-ocr-deu) + pdf2image + pytesseract | System-Paket |
| **Word-Generierung** | python-docx 1.1.2 · docxtpl 0.16.8 (Jinja2-Vorlagen) | — |
| **DOCX → PDF** | LibreOffice Writer (headless, System-Paket) | — |
| **KI / LLM-Parsing** | Lokales LM Studio (OpenAI-kompatible API) · Claude Sonnet via `anthropic` 0.49.0 · Gemini via `google-genai` 1.10.0 | — |
| **RA-MICRO Connector** | pymssql 2.3.1 → MS SQL Server 2014 TDS 7.0 | — |
| **E-Mail-Import** | imaplib (stdlib) IMAP4_SSL Port 993 | — |
| **Distanz-Prüfung** | OpenRouteService REST-API (Verweisbetrieb-Check) | extern |
| **Validierung** | Pydantic 2.7.1 | — |
| **Tests** | pytest 8.2.0 · pytest-cov 5.0.0 · httpx 0.27.0 | — |
| **Sprache Frontend** | JavaScript (JSX) | — |
| **Frontend-Framework** | React 18.3.1 | — |
| **Build-Tool** | Vite 5.4.2 | — |
| **Charts** | Recharts 2.12.7 | — |
| **Node** | 20+ / npm 10+ | — |
| **Reverse Proxy** | nginx 1.27-alpine | — |
| **Container** | Docker / Docker Compose | — |

---

## 2. Dienste (Docker)

### Entwicklung (`docker-compose.yml`)

| Container | Image | Port | Zweck | Abhängigkeit |
|---|---|---|---|---|
| `unfallakten-backend-dev` | `unfallakten-backend:dev` (python:3.12-slim) | 5000 | Flask Dev-Server mit Hot-Reload | — |
| `unfallakten-frontend-dev` | `node:20-alpine` | 5173 | Vite Dev-Server | backend healthy |

Volume `dev-data` → SQLite-DB, `dev-uploads` → hochgeladene PDFs, `/mnt/eakte` → E-Akte Read-Only (CIFS-Mount aus WSL)

### Produktion (`docker-compose.prod.yml`)

| Container | Image | Port (intern) | Zweck | Abhängigkeit |
|---|---|---|---|---|
| `unfallakten-backend` | `unfallakten-backend:prod` (python:3.12-slim, non-root) | 5000 | Gunicorn 4 Worker · 60 s Timeout | — |
| `unfallakten-frontend` | `unfallakten-frontend:prod` (Vite-Build → nginx:alpine) | 8080 | Statisches SPA via nginx | — |
| `unfallakten-nginx` | `nginx:1.27-alpine` | **80, 443** | TLS-Termination · HTTP→HTTPS · Routing API/SPA | backend + frontend healthy |
| `unfallakten-backup` | `alpine:3.20` | — | Nightly Cron (02:00) → SQLite + Uploads sichern, 30 Tage Retention | — |

nginx-Routing:
- `GET /health` → backend:5000 (kein Rate-Limit)
- `POST /auth/anmelden` → backend:5000 (Rate-Limit 10 req/min, Burst 5)
- `^/(auth|akten|email)` → backend:5000 (Rate-Limit 60 req/min, Burst 20)
- `/*.{js,css,woff2,...}` → frontend:8080 (Cache 1 Jahr, immutable)
- `/*` → frontend:8080 (SPA, kein Cache auf index.html)

---

## 3. Verzeichnisstruktur

```
unfallakten/
├── backend/                   Python-Backend (Flask Application)
│   ├── app.py                 Application Factory, Blueprint-Registrierung, Health-Check
│   ├── auth/                  JWT-Handler, Login-Middleware, Validierung
│   ├── config/
│   │   └── registry.json      Parser-Registry (Versicherer → Parser-Klasse)
│   ├── data/                  SQLite-Datenbankdatei (unfallakten.db)
│   ├── db/
│   │   ├── database.py        get_connection() Context-Manager
│   │   ├── schema.py          CREATE TABLE DDL (Basisschema: 7 Tabellen)
│   │   └── schema_manager.py  init_db(), Migrations-Registry (bis Migration 39+)
│   ├── email_import/          IMAP-Client, E-Mail-Parser, Klassifizierer, Import-Service
│   ├── models/                Pydantic/Datenmodelle (Akte, Beteiligter, Dokument, …)
│   ├── parsers/               PDF-Parser: Gutachten, Abrechnungsschreiben, Rechnungen, Prüfberichte
│   ├── pdf/                   Upload-Service, Text-Extraktor, Parser-Wrapper
│   ├── ramicro/               RA-MICRO SQL-Connector, E-Akte-Service, WDM-Service, Wiedervorlagen
│   ├── routers/               Flask-Blueprints (ein Blueprint pro Fachdomäne, s. u.)
│   ├── scripts/               Einmal-Skripte: backfill_fristen.py, seed_db.py
│   ├── services/              Domänen-Services: Fristen, Gebühren, OCR, LLM, Portal-Sync, STA
│   └── tests/                 pytest-Testsuiten (test_modul1–8, test_prd23b, test_prd27, …)
├── frontend/
│   ├── src/
│   │   ├── App.jsx            Router, Auth-Guard, Layout-Shell
│   │   ├── api.js             Zentraler Fetch-Wrapper (JWT-Header, Error-Handling)
│   │   ├── views/             Seiten-Komponenten (ActionBoardView, AkteDetailView, LoginPage, …)
│   │   ├── sections/          Akte-Detail-Tabs: Übersicht, Schaden, Regulierung, Dokumente, Gebühren, Klage, …
│   │   ├── components/        Wiederverwendbare UI-Bausteine
│   │   ├── state/             Lokaler React-State (kein Redux)
│   │   └── config/            Konfigurationskonstanten
│   └── package.json           Abhängigkeiten: React 18, Recharts, Vite
├── nginx/
│   ├── nginx.conf             Reverse Proxy: TLS, Rate-Limit, Routing, Security-Header
│   └── proxy_params.conf      Gemeinsame Proxy-Parameter
├── Dockerfile                 Multi-Stage: `builder` (Dev) + `production` (Gunicorn, non-root)
├── docker-compose.yml         Entwicklungs-Stack
├── docker-compose.prod.yml    Produktions-Stack (+ nginx + backup)
├── gunicorn.conf.py           Gunicorn: 4 Worker, Timeout 60 s
├── .env.example               Alle Konfigurationsvariablen dokumentiert
├── backups/                   Nightly-Backups (SQLite + Uploads)
├── docs/                      API-Dokumentation (openapi.yaml, ARCHITECTURE.md)
└── handover/                  Session-Übergabe-Dokumente, PRD-Mappen, Architecture-Map
```

---

## 4. Flask-Blueprints (API-Endpunkte)

| Blueprint | Prefix | Fachdomäne |
|---|---|---|
| `auth_bp` | `/auth` | Anmeldung, JWT-Refresh, Benutzer |
| `akten_bp` | `/akten` | CRUD Unfallakten, Akten-Status |
| `aktensuche_bp` | `/aktensuche` | Volltext-/Filter-Suche |
| `beteiligte_bp` | `/akten/<az>/beteiligte` | Mandant, Gegner, Zeuge, SV |
| `schaden_bp` | `/akten/<az>/schaden` | Schadenpositionen |
| `regulierung_bp` | `/akten/<az>/regulierungen` | Abrechnungsschreiben, Regulierungspositionen |
| `belege_bp` | `/akten/<az>/belege` | Beleg-Zuordnung zu Regulierungen |
| `dokumente_bp` | `/akten/<az>/dokumente` | Dokument-Upload, Verwaltung |
| `word_bp` | `/akten/<az>/dokumente/word` | Word-Generierung (docxtpl) |
| `pdf_parse_bp` | `/akten/<az>/pdf-parse` | PDF-Text-Extraktion + Parser-Dispatch |
| `eakte_bp` | `/eakte` | E-Akte Dokumente aus RA-MICRO DMS |
| `email_bp` | `/email` | IMAP-Import, E-Mail-Log |
| `dashboard_bp` | `/dashboard` | Übersichts-Kacheln, Fristen, Wiedervorlagen |
| `wiedervorlage_bp` | `/wiedervorlagen` | WV aus RA-MICRO + lokal |
| `klage_bp` | `/akten/<az>/klage` | Klage-Wizard (10 Schritte) |
| `unfalldetails_bp` | `/akten/<az>/unfalldetails` | Unfallhergang, Haftungsquote |
| `gebuehren_bp` | `/akten/<az>/gebuehren` | RVG-Gebührenberechnung (Nr. 2300 VV) |
| `forderung_bp` | `/akten/<az>/forderung` | Forderungsübersicht |
| `distanz_bp` | `/distanz` | OpenRouteService-Distanzprüfung |
| `sta_bp` | `/akten/<az>/sta` | Sachstandsanfragen |
| `stellungnahme_bp` | `/akten/<az>/stellungnahme` | SV-Stellungnahmen |
| `pruefberichte_bp` | `/akten/<az>/pruefberichte` | Prüfberichte |
| `abrechnungsschreiben_bp` | `/akten/<az>/abrechnungsschreiben` | Abrechnungsschreiben-Parser |
| `ps_bp` | `/akten/<az>/personenschaden` | Personenschaden |
| `firmen_bp` | `/firmen` | Werkstätten, Versicherer, SV (Stammdaten) |
| `kuerzungsarten_bp` | `/kuerzungsarten` | Kürzungsarten-Katalog |
| `ramicro_akte_bp` | `/ramicro` | RA-MICRO Akte-Stammdaten |
| `einstellungen_bp` | `/einstellungen` | LLM-Modell, System-Einstellungen |
| `todos_bp` | `/todos` | Aufgaben / To-dos |
| `portal_bp` | `/portal` | Stakeholder-Portal Webhook + Sync |

---

## 5. Datenbankschema (SQLite)

**Basistabellen** (schema.py, Migration 1):

| Tabelle | Inhalt |
|---|---|
| `benutzer` | Kanzleimitarbeiter, Rollen (admin / sachbearbeiter), bcrypt-Hash |
| `unfallakte` | Kernakte: PK = Aktenzeichen (az), Status, Haftungsquote, RA-MICRO-Cache |
| `beteiligte` | Mandant, Gegner, Zeuge, SV, sonstiger – je Akte |
| `schadenpositionen` | Alle Schadenposten (Reparatur, WBW, Nutzungsausfall, SV, Mietw., …) |
| `regulierung` | Regulierungsvorgänge der Versicherung (deprecated, s. u.) |
| `dokumente` | PDF/DOCX-Metadaten: Typ, DKz, SHA-256, Pfad, Klassifizierung |
| `aktivitaeten` | Audit-Log aller Aktionen |

**Migrations-Tabellen** (schema_manager.py, Migration 2–39+):

| Migration | Tabellen / Änderungen |
|---|---|
| 2 | `email_import_log` |
| 3 | `kuerzungsarten` (19 Seed-Einträge), `abrechnungsschreiben`, `regulierung_positionen` |
| 4+ | `forderungen`, `pruefberichte`, `todos`, `fristen`, `stellungnahmen`, `portal_sync_queue`, `klage_*`, `gebuehren_*`, `sta_*`, u. v. m. |

---

## 6. Datenpfad

```
RA-MICRO SQL Server (RAMICRO-DB, read-only)
  → ramicro/connector.py          pymssql TDS 7.0, Port 1433
  → ramicro/eakte_service.py      tblElo_AktenArchiv (raEloakte-DB, read-only)
  → ramicro/wiedervorlage_service.py / wdm_regulierung_service.py
        ↓
  Backend (Flask/Gunicorn, Port 5000)
  → akten_routes.py               Akte in unfallakten.db cachen / anlegen
  → schaden_routes.py             Schadenpositionen speichern
  → abrechnungsschreiben_routes.py Abrechnungsschreiben parsen + speichern
        ↓
  SQLite (unfallakten.db, /app/data/)
        ↓
  Frontend (React, Port 5173/8080)
  → api.js                        Fetch + JWT-Auth-Header
  → views/ + sections/            Darstellung, Formulare, Wizard
```

**E-Mail-Import-Pfad:**
```
IMAP-Server (EMAIL_HOST:993, SSL)
  → email_import/imap_client.py   ungelesene E-Mails abrufen
  → email_import/email_parser.py  Anhänge extrahieren (PDF, DOCX)
  → email_import/klassifizierer.py  Akte-Zuordnung (az-Extraktion)
  → parsers/ (gutachten_parser, rechnung_parser, …)  Dokument-KI-Parsing
  → db (unfallakten.db)           dokumente + email_import_log eintragen
```

**PDF-Upload-Pfad:**
```
Browser → POST /akten/<az>/pdf-parse (multipart/form-data, max 25 MB)
  → pdf/upload_service.py         SHA-256 Dedup, /app/uploads/ ablegen
  → parsers/document_classifier.py  Klassifizierung (Gutachten / Abrechnung / Rechnung / …)
  → Parser (Regex + ggf. LLM)    Positionen, Beträge, Kürzungen extrahieren
  → SQLite                        abrechnungsschreiben + regulierung_positionen
  → SSE-Stream (PRD-30)           Echtzeit-Fortschritt an Frontend
```

**LLM-Parsing-Pfad (Shadow-Mode):**
```
Backend → services/llm_service.py
  → LM Studio lokal (http://host.docker.internal:1234/v1, OpenAI-API)
  → Modell: qwen3.5-9b (umschaltbar per UI)
  Alternativ: anthropic SDK → Claude Sonnet (ANTHROPIC_API_KEY)
             google-genai → Gemini (GEMINI_API_KEY)
```

**Portal-Sync-Pfad:**
```
SQLite (portal_sync_queue)
  → services/portal_sync.py       Ampel-Status berechnen
  → HTTPS POST portal.anwalt-offenbach.de (PORTAL_API_URL, HMAC-signiert)
  ← Stakeholder-Portal (Next.js)  Bestätigung
```

---

## 7. Externe Abhängigkeiten

| Dienst | Verbindungsart | Konfiguration |
|---|---|---|
| **RA-MICRO SQL Server 2014** | pymssql · TCP 1433 · TDS 7.0 · Read-Only-User | `.env`: `RAMICRO_HOST`, `RAMICRO_PORT`, `RAMICRO_USER`, `RAMICRO_PASSWORD`, `RAMICRO_AKTIV` |
| **RA-MICRO E-Akte DMS (raEloakte)** | pymssql · gleiche Credentials wie RA-MICRO, andere DB | `.env`: wie RA-MICRO; `EAKTE_BASE_PATH` für Dateipfade |
| **E-Akte Dateifreigabe** | CIFS-Mount (WSL: `//192.168.10.100/ServerSQL/ra`) → Docker Volume `/mnt/eakte:ro` | `docker-compose.yml`: Volume-Mount, Read-Only |
| **IMAP (Strato)** | IMAP4_SSL · Port 993 · SSL | `.env`: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`, `EMAIL_FOLDER` |
| **OpenRouteService** | HTTPS REST-API (Geocoding + Routing) | `backend/routers/distanz_routes.py` (API-Key im Code oder `.env`) |
| **LM Studio (lokal)** | HTTP · `host.docker.internal:1234` · OpenAI-kompatible API | `.env`: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_ENABLED` |
| **Anthropic (Claude)** | HTTPS · `api.anthropic.com` | `.env`: `ANTHROPIC_API_KEY` |
| **Google Gemini** | HTTPS · `generativelanguage.googleapis.com` | `.env`: `GEMINI_API_KEY` |
| **Stakeholder-Portal** | HTTPS · `portal.anwalt-offenbach.de` · Bearer + HMAC | `.env`: `PORTAL_API_URL`, `PORTAL_API_KEY`, `PORTAL_HMAC_SECRET` |
| **Let's Encrypt** | certbot (ACME) · nginx ACME-Challenge unter `/var/www/certbot` | `nginx/ssl/fullchain.pem` + `privkey.pem` |
