# PRD-29: Schmerzensgeld-Ermittlungstool
> Erstellt: 2026-04-09
> Status: **In Implementierung**
> Schema-Version nach Abschluss: 36

## Ziel

Der Schmerzensgeld-Block in Klageschrift und Forderungsschreiben wird mit echten Verletzungsdaten befüllt. Ein geführtes Modal-Tool hilft dem Anwalt dabei:
1. Vergleichsurteile recherchieren (Claude + web_search auf dejure.org, lexetius.com, verkehrslexikon.de)
2. Schmerzensgeld-Mindestbetrag festlegen
3. Juristisch formulierten Klagetext generieren (KI)

## Architektur

```
KlageSection Kachel 4  +  KlageWizard Step 5
        ↓
SchmerzensgelDialog.jsx  (Modal, analog StaDialog.jsx)
        ↓
GET  /akten/{az}/klage/sg-analyse      Verletzungsprofil
POST /akten/{az}/klage/sg-recherche    Claude web_search → 10 Urteile
POST /akten/{az}/klage/sg-text         Claude → Klagetext
PUT  /akten/{az}/personenschaden       speichert sg_text + sg_mindest
```

## DB-Änderungen (Migration 36)

Neue Spalten in `personenschaden`:
- `sg_mindest REAL`
- `sg_text TEXT`
- `sg_urteil_gericht TEXT`
- `sg_urteil_az TEXT`
- `sg_urteil_betrag REAL`

## Phasen

| # | Was | Dateien |
|---|---|---|
| 1 | Schema-Migration 36 | `schema_manager.py` |
| 2a | GET sg-analyse | `klage_routes.py` |
| 2b | POST sg-recherche (Claude web_search) | `klage_routes.py` |
| 2c | POST sg-text (Claude Textgenerierung) | `klage_routes.py` |
| 2d | personenschaden allowed_fields erweitern | `personenschaden_routes.py` |
| 3 | Gemeinsamer Textbaustein | `backend/word/sg_text_builder.py` (NEU) |
| 3a | klage_service.py: verbesserter Block | `klage_service.py` |
| 3b | forderungsschreiben_wv.py: Zweizeiler ersetzen | `forderungsschreiben_wv.py` |
| 4 | SchmerzensgelDialog.jsx | `frontend/src/components/` (NEU) |
| 5 | KlageSection + KlageWizard Integration | `KlageSection.jsx`, `KlageWizard.jsx` |
| 6 | api.js neue Endpunkte | `api.js` |

## Recherche-Quellen

- **Automatisch** (Claude web_search): dejure.org, lexetius.com, verkehrslexikon.de
- **Manuell per Link**: schmerzensgeld.online (Abo vorhanden, kein API; Link mit vorbereiteten Suchbegriffen)
- **Zukunft**: schmerzensgeld.online anfragen ob API-Zugang möglich

## Kosten

~7 Cent pro Recherche-Aufruf (claude-sonnet-4-6 + web_search, ~11.000 Input + 2.000 Output Token)

## Dialog-Aufbau (3 Bereiche)

1. **Verletzungsprofil** (readonly): Diagnosen, Krankenhaustage, AU-Tage, Dauerfolgen + Warnung bei leeren Feldern
2. **Recherche**: [Urteile recherchieren]-Button → Ladeindikator → Trefferliste mit [Auswählen]; Link zu schmerzensgeld.online
3. **Text + Übernahme**: Mindestbetrag-Eingabe, [KI-Text generieren], editierbare Textarea, [Übernehmen]
