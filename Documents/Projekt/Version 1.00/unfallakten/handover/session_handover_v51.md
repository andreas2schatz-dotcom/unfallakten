# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v51 – 15. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **36** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode für Regulierungsschreiben + Gutachten aktiv) |

---

## Erledigte Arbeiten v51

### 1 – RegulierungSection: per-Position KI-Toggle (Abschluss aus v50)

**Problem:** Die KI-Konfliktauflösung in `RegulierungSection.jsx` nutzte einen globalen Toggle
(`llmGewaehlt` boolean: entweder alle Regex oder alle KI). Der Nutzer wollte per-Position-Buttons
wie in `SchadenSection.jsx`.

**Geänderte Dateien:**

| Datei | Änderung |
|---|---|
| `frontend/src/sections/RegulierungSection.jsx` | `llmGewaehlt` → `llmWahl = {}` (Map), `handleUebernehmen` neu, Header-IIFE durch Badge ersetzt, `AbrechnungVorschau` um `llmWahl`/`setLlmWahl`-Props + "Wählen"-Spalte erweitert |

**Verhalten:**
- Header: `⚠ KI-Konflikt – wähle pro Position` (Badge, kein globaler Button mehr)
- Tabellen-Spalte „Wählen": `[Regex]` + `[KI]`-Buttons je abweichender Zeile
- „Vorschlag"-Spalte zeigt lila KI-Wert wenn `llmWahl[i] === 'ki'` gesetzt
- `handleUebernehmen` wendet `llmWahl` per Position an

---

### 2 – PRD-34: Inbox-Pattern für Dokumente-Kachel

**Problem:** Nutzer musste für jedes importierte Dokument zwei Interaktionen durchführen:
(1) Klasse in Dokumente-Kachel bestätigen, (2) Kandidat in Schadenbelege-Kachel annehmen.

**Lösung:** „Enhanced Hybrid": Dokumente-Kachel wird zur Inbox, zugeordnete Dokumente
verschwinden automatisch. Beim Klassifizieren erscheint ein Inline-Prompt zur sofortigen
Schadenposition-Zuordnung.

**Geänderte Dateien:**

| Datei | Änderung |
|---|---|
| `frontend/src/config/constants.js` | `KLASSE_TO_POS` Konstante (6 Einträge) + Export |
| `frontend/src/sections/DokumenteSection.jsx` | Inbox-Filter, Inline-Prompt, Beleg-Entfernen, Highlight-Animation |

**Neue Funktionen in DokumenteSection.jsx:**

- **Inbox-Filter:** `sichtbareDokumente` filtert belegte + `gutachten`-Dokumente aus
- **CardHead:** `"3 offen / 8 gesamt"` + Toggle-Button `"Alle (8)"` / `"Nur offene"`
- **Leerzustand:** `"Alle Dokumente zugeordnet. [Alle anzeigen]"`
- **Inline-Prompt:** Erscheint unterhalb der Dokument-Zeile wenn:
  - `parse_konfidenz >= 0.85` UND Klasse in `KLASSE_TO_POS` UND Position noch offen, **oder**
  - Nutzer ändert Klasse manuell im Dropdown → `promptForced`
  - Zeigt Position-Label + Betrag (aus Kandidaten) oder Betrag-Eingabefeld
  - `← Annehmen` → `apiBelege.zuordnen()` + `apiSchaden.speichern()` → Dok verschwindet
  - `✕` → Prompt wird geschlossen (Ablehnung gemerkert)
- **Beleg-Entfernen:** `✕`-Button (hover-sichtbar) neben ✓-Checkmark in Schadenbelege-Kachel
- **Highlight:** Grüner Flash (2 s) auf der zugeordneten Schadenbelege-Zeile
- **zeigeAlle-Modus:** `zugeordnet`-Badge (grün) + `→ Schaden-Reiter`-Badge (lila) für Gutachten

**`KLASSE_TO_POS`:**
```js
abschlepprechnung   → abschleppkosten
standkostenrechnung → standkosten
mietwagenrechnung   → mietwagenkosten
sv_rechnung         → sv_kosten
reparaturrechnung   → rep_rechnung_brutto
werkstattrechnung   → rep_rechnung_netto
```

**Nicht im Inbox-Filter (bleiben sichtbar):**
- `abrechnungsschreiben` → eigener Workflow in RegulierungSection
- `gutachten` → eigener Workflow in SchadenSection (wird ausgeblendet, nicht zugeordnet)
- Alle nicht in KLASSE_TO_POS (arztbericht, klage, etc.)

---

## Nächste Session: PRD-33 – Feintuning Klage-Wizard

### Kontext

Der 10-Step-Wizard ist funktional vollständig (PRD-26, Session v45). PRD-33 ist ein
**Qualitäts-/Debugging-Pass** am generierten Word-Dokument: Formatierung, Zeilenumbrüche,
Absätze, Textqualität einzelner Abschnitte.

### Ziel der nächsten Session

1. **Ist-Analyse:** Klage für eine Testakte generieren, das DOCX öffnen, alle Abschnitte
   systematisch durchgehen und Mängel dokumentieren
2. **Bugfixing** an `backend/word/klage_service.py` (Hauptdatei für Word-Generierung)
3. Optional: Textbausteine in `KlageWizard.jsx` (Step 3/6/7/8/9) überarbeiten

### Relevante Dateien

| Datei | Rolle |
|---|---|
| `backend/word/klage_service.py` | Word-Generierung: python-docx, alle Abschnitte, Formatierung |
| `frontend/src/sections/KlageWizard.jsx` | Wizard-UI (10 Steps), Textbausteine in `buildSachverhaltText()`, `baueAntraegeText()`, `baueGebuehrenAntrag()` |
| `frontend/src/sections/KlageSection.jsx` | Wizard-Orchestrierung, `wizardGenerieren()` baut `cfg`-Objekt |
| `handover/klage_wizard_map.md` | Vollständige Step-Map, State-Übersicht, bekannte Mängel |

### Bekannte Qualitätsmängel (aus klage_wizard_map.md)

| Step | Problem |
|---|---|
| Step 4 | Kein Diff-View, kein Zurücksetzen-Button |
| Step 5 | Kein Regulierungsstand neben Position |
| Step 8 | Zeigt gerichtl. RVG – könnte Nutzer verwirren |
| Step 10 | Zeigt nur gerichtl. RVG, nicht außergerichtl. |
| Backend | Formatierung (Absätze, Leerzeilen, Zeilenumbrüche) lt. Nutzer-Feedback |

### Debugging-Vorbereitung

Für die nächste Session: Klage für eine reale Testakte (z.B. mit allen 10 Steps durchlaufen)
generieren, DOCX herunterladen, und folgende Punkte prüfen:

1. **Absätze und Leerzeilen** zwischen Abschnitten (Sachverhalt / Rechtliche Würdigung / Anträge)
2. **Schriftbild** – Überschriften, Fließtext, Einrückungen in python-docx
3. **Platzhalter** – sind alle `{{...}}` korrekt ersetzt?
4. **Antragstexte** – RVG-Betrag korrekt eingesetzt? Außergerichtl. vs. gerichtl. Trennung?
5. **Rubrum** – Beklagte korrekt formatiert (mehrere Beklagte)?

---

## Offene PRDs (Gesamt-Übersicht)

| PRD | Titel | Status |
|---|---|---|
| PRD-33 | Feintuning Klage-Wizard | Debugging-Pass nächste Session |
| PRD-27 | ReguWizard – Stellungnahme | Planung offen |
