# N-03 — Retry-Differenzierung + Degradations-Hinweis (Design)

Stand: 2026-07-14 · Branch `intake-stufe1` · Quelle: `FREIGABE-NACHTRAG-1.md` Abschnitt A (N-03)

## Ausgangslage (Bestandsprüfung — „nur die Differenz bauen")

1. **Retry heute** (`backend/intake/queue.py::markiere_fehler`): behandelt *jeden*
   Fehler pauschal — Backoff `1/5/30` min (`BACKOFF_S`), nach `MAX_VERSUCHE=3`
   Fehlversuchen → `queue_status='pipeline_fehler'`. Keine Differenzierung.
2. **GLM-OCR** (`services/glm_ocr_service.py`) und **Text-LLM**
   (`services/llm_service.py`) **schlucken jeden Fehler → `None`**
   (Timeout / ConnectionError / generisch werden nur im *Log* unterschieden).
   Die Pipeline degradiert dann still auf Tesseract/Regex und erreicht trotzdem
   `bereit_zur_review`. Der Fall „reproduzierbarer Modellfehler → läuft im
   Tesseract-Primär-Modus weiter" ist damit heute faktisch schon der Normalfall.
3. **Der Retry-/Backoff-Pfad feuert deshalb nur bei harten Exceptions**, die in
   `pipeline.verarbeite_dokument` durchschlagen: fehlende Arbeitskopie, „keine
   Seiten extrahierbar", OCR-Rendering (poppler/tesseract weg), DB-Fehler.

**Entscheidung RA Schatz (2026-07-14):** Der Swallow bleibt (keine Umstellung auf
Zurückstellen/Retry bei degradierter KI). Stattdessen bekommt der Mensch beim
Review **sichtbar** die Meldung „nur Regex / kein Qwen" und prüft manuell.

## Ziel

Zwei kleine, unabhängig testbare Teile. Keine Architekturänderung.

### Teil 1 — Fehler-Klassifikation im Retry-Pfad (`backend/intake/queue.py`)

Neue **reine Funktion** `klassifiziere_fehler(meldung: str) -> str`, die die bereits
vorliegende Fehlermeldung case-insensitive in vier Kategorien einordnet:

| Kategorie | Erkennungsmuster (Beispiele, case-insensitive) |
|---|---|
| `timeout` | `timeout`, `timed out`, `read timed out`, `zeitüberschreitung` |
| `ressourcendruck` | `connection`, `verbindung`, `refused`, `reset by peer`, `broken pipe`, ` 503`, ` 502`, `overload`, `überlast`, `unavailable`, `too many requests`, `temporarily` |
| `reproduzierbar` | `keine seiten extrahierbar`, `ohne inhalt`, `cannot open`, `damaged`, `not a pdf`, `no /root`, `invalid`, `unsupported`, `arbeitskopie fehlt` |
| `unbekannt` (Default) | alles andere |

`markiere_fehler` ruft den Klassifikator und verzweigt:

- **`timeout` / `unbekannt`** → Verhalten **unverändert**: `versuch_zaehler += 1`,
  Backoff `1/5/30`, nach `MAX_VERSUCHE` → `pipeline_fehler`. (Sicherer Default:
  weiter retrien.)
- **`ressourcendruck`** → **Zurückstellen**: Status bleibt `neu`,
  `naechster_versuch = jetzt + RUECKSTELL_S` (`900` = 15 min, neue Konstante),
  **`versuch_zaehler` wird NICHT erhöht**. Ein vorübergehender LM-Studio-/
  Backend-Ausfall vergiftet das Dokument nicht. `fehler_detail` gesetzt.
  **Keine harte Obergrenze** (Entscheidung RA Schatz): ein permanent
  fehlkonfiguriertes Backend ist ein Ops-Problem und wird im Log wiederholt
  gewarnt — besser als ein `pipeline_fehler`, der die Ursache verdeckt. Der
  Worker ist nicht blockiert (nimmt andere Dokumente).
- **`reproduzierbar`** → **KEIN Retry**: sofort `queue_status='pipeline_fehler'`,
  `fehler_detail` mit klarem deutschem Hinweis. Der Mensch sieht das Dokument
  sofort im Fehler-Bereich der Review-Queue statt erst nach 36 min (3× Backoff).

Kein neuer `queue_status`-Wert (nutzt vorhandene `neu` / `pipeline_fehler`),
keine Migration für Teil 1.

### Teil 2 — Degradations-Hinweis „nur Regex / kein Qwen"

Auf dem **Erfolgs-Pfad**: War die KI-Extraktion eingeschaltet, lieferte aber
nichts (weggeschluckt → `None`), wird das erkannt und sichtbar gemacht.

- `extrahiere_felder` (`backend/intake/extraktion.py`) liefert zusätzlich
  `llm_status ∈ {"ok","aus","ausgefallen"}`:
  - `aus` → LLM bewusst deaktiviert (`LLM_ENABLED=false`) → **kein** Hinweis
    (konfigurierter Modus, keine Störung).
  - `ausgefallen` → LLM eingeschaltet, aber `extrahiere_nach_schema` gab
    `None`/leer → **Degradation**.
  - `ok` → LLM lieferte Werte.
  Grundlage: neuer öffentlicher `llm_service.ist_aktiviert()` (liest das
  vorhandene `_ENABLED`) + die bereits im Aufruf vorliegende `None`-Rückgabe.
  Dokumente ohne Schema (Klasse ohne `schema`) → `aus`.
- `pipeline.verarbeite_dokument` stempelt bei `ausgefallen`:
  - `parse_json["degradation"] = {"llm_extraktion": "ausgefallen"}` (für den
    Detail-Hinweis, migrationsfrei), und
  - **Migration 57** (additiv, nullable, idempotent, kein `executescript`,
    explizite Commits — Klon von Mig 55/56): `intake_dokumente.llm_degradiert
    INTEGER` (0/1/NULL). Wird im bestehenden UPDATE mitgesetzt.
- `hole_queue` liefert `llm_degradiert` je Eintrag (analog `ocr_ratio_salat` aus
  N-02, via `json_extract`/Spalte). `hole_detail` liefert `degradation` aus
  `parse_json`.
- **Frontend** (`ReviewQueueView.jsx`):
  - **Queue-Badge** neben `OcrBadge`/`KonfidenzChip`: gelbes „KI ⚠"/„nur Regex"
    (reine Funktion analog `ocrQualitaet(item)`).
  - **Detail-Panel**: gelbe Hinweis-Box „Extraktion ohne KI (nur Regex) — Felder
    bitte manuell prüfen." (nur wenn `degradation.llm_extraktion === 'ausgefallen'`).

## Verworfene Alternativen

- **Typisierte Exceptions aus den Services** statt Muster-Matching auf der
  Meldung: sauberer, ändert aber den load-bearing „schluck-und-gib-`None`"-
  Vertrag → Regressionsrisiko bei der Degradation. Verworfen.
- **Neue `queue_status`-Werte** (`zurueckgestellt`/`degradiert`): bräuchte
  CHECK-Migration + Anpassung aller Status-Filter. Verworfen — vorhandene
  Zustände reichen.
- **Ressourcendruck-Retry aus dem Swallow melden** (Variante 2 der
  Scope-Frage): vom Nutzer verworfen — Swallow bleibt, Mensch prüft manuell.

## Tests (TDD)

- `test`: `klassifiziere_fehler` — Tabellen-Test je Kategorie inkl. Default.
- `markiere_fehler`-Verhalten je Kategorie: `ressourcendruck` (Status `neu`,
  `naechster_versuch` gesetzt, `versuch_zaehler` **unverändert**),
  `reproduzierbar` (sofort `pipeline_fehler`, kein Backoff), `timeout`/`unbekannt`
  (unveränderter Backoff, poison-pill nach 3).
- Migration 57: Spalte existiert, nullable, idempotenter Zweitlauf.
- `extrahiere_felder`: `llm_status` in allen drei Ausprägungen (Monkeypatch von
  `extrahiere_nach_schema` → Werte / `None`; `ist_aktiviert` True/False).
- Pipeline-E2E: „KI eingeschaltet aber tot" → `llm_degradiert=1` +
  `parse_json.degradation`; „KI aus" → kein Marker.
- `hole_queue` liefert `llm_degradiert`; `hole_detail` liefert `degradation`.
- Frontend-Vitest: Queue-Badge bei `llm_degradiert`, Detail-Hinweis bei
  `degradation`, keiner ohne.
- **Golden-Files** (`test_registry_golden.py`, `test_s16a_golden_e2e.py`,
  `test_s18_review_e2e.py`) bleiben grün.

## Abgrenzung

- Kein Anfassen von N-04 (Seiten-Triage), N-05 (Yielding/Teilergebnisse).
- Alt-Pfade / `INTAKE_REVIEW_PFLICHT` unberührt. RA-MICRO read-only.
- Vor Migration 57: Sicherungskopie der aktiven Volume-DB (`/app/data`).
