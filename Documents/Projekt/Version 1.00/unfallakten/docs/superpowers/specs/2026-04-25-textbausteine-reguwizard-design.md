# Design: Textbaustein-Import + ReguWizard (PRD-02 + PRD-27)
> Erstellt: 2026-04-25

---

## Scope

Diese Session deckt ab:

| PRD | Titel | Aufwand |
|---|---|---|
| PRD-14 | Frontend-Cleanup Abrechnungsart (Single Source of Truth) | 0,5 h |
| PRD-02 | Textbaustein-Import + Replacement-Engine | 1 Session |
| PRD-27 | ReguWizard – Geführte Stellungnahme | 1–2 Sessions |

PRD-14 wird vorab als Quick-Fix erledigt (Voraussetzung: Betrag-Anzeige konsistent).

---

## Teil 1: Import-Script (PRD-02a)

### Zweck

Einmaliges Python-Script, das 19 Word-Dateien (je eine pro Kürzungsart) in die
`textbaustein`-Spalte der `kuerzungsarten`-Tabelle importiert.

### Dateistruktur

```
tools/
  import_textbausteine.py
  textbausteine/
    stundenverrechnungssaetze.docx
    nutzungsausfall.docx
    ...   (19 Dateien)
```

### Ablauf

1. Script liest alle `.docx`-Dateien im Unterordner `textbausteine/`
2. Dateiname wird per Mapping-Tabelle einer `kuerzungsarten.id` zugeordnet
3. Text wird mit `python-docx` extrahiert (alle Paragraphen, Zeilenumbrüche erhalten)
4. **Platzhalter-Inventar:** Vor dem Schreiben werden alle `<...>`-Vorkommen gesammelt und ausgegeben — Mapping wird gemeinsam mit dem Anwalt erstellt
5. SQL-Update: `UPDATE kuerzungsarten SET textbaustein = ? WHERE id = ?`
6. Ausgabe: Erfolg/Fehler je Datei, unbekannte Kürzungsarten

### Eigenschaften

- Idempotent (wiederholbar, überschreibt vorherigen Wert)
- Kein laufendes Backend nötig — direkter SQLite-Zugriff
- Läuft auf dem Host (außerhalb Docker), Python 3.9+, Abhängigkeit: `python-docx`

---

## Teil 2: Placeholder-Replacement-Engine (PRD-02b)

### Mechanismus

```python
def ersetze_platzhalter(text: str, kontext: dict) -> str:
    for key, value in kontext.items():
        text = text.replace(f"<{key}>", str(value) if value else "")
    return text
```

Wird in `stellungnahme_service.py` aufgerufen, bevor Text ins Word-Dokument fließt.

### Kontext-Dict (initiales Mapping — wird gemeinsam vervollständigt)

| Platzhalter | Quelle |
|---|---|
| `<MANDANT>` | Beteiligte → Mandant → vollständiger Name |
| `<AZ>` | Akte → Aktenzeichen |
| `<VERSICHERER>` | Beteiligte → Versicherung → Name |
| `<DATUM>` | `datetime.now()` formatiert als `DD.MM.YYYY` |
| `<BETRAG>` | Kürzungsbetrag der aktuellen Position (EUR) |
| `<KFZ>` | Fahrzeugkennzeichen aus Akte |

**Unbekannte Platzhalter** werden als `[FEHLT: <XYZ>]` markiert, damit sie im
Wizard sichtbar sind und nachgebessert werden können.

### Kritische Randbedingung

Das endgültige Mapping wird **erst nach Sichtung der Word-Dateien** festgelegt.
Das Import-Script listet alle gefundenen `<...>`-Token auf — dieser Output ist
Grundlage für das gemeinsame Mapping-Review vor der Implementierung der Engine.

---

## Teil 3: ReguWizard (PRD-27)

### Einstiegspunkt

Button „Stellungnahme erstellen" in `RegulierungSection.jsx`,
sichtbar wenn mindestens ein Abrechnungsschreiben mit Kürzungen vorhanden.

### Wizard-Steps

| # | Label | Inhalt |
|---|---|---|
| 1 | Parteien | Mandant + Versicherer aus Akte (read-only, bestätigen) |
| 2 | Abrechnungsschreiben | Datum, AZ Versicherer, Gesamtbetrag (vorausgefüllt aus Parser) |
| 3 … N | Kürzungsposition | Je eine Seite pro gekürzter Position: Bezeichnung + Betrag + vorgeschlagener Textbaustein (Platzhalter bereits ersetzt). Anwalt: akzeptieren / Text anpassen / überspringen |
| N+1 | Frist | Zahlungsfrist (Standard 14 Tage ab heute) |
| N+2 | Generieren | Zusammenfassung aller übernommenen Positionen + Word-Export |

### Technische Komponenten

| Komponente | Datei | Bemerkung |
|---|---|---|
| Wizard-UI | `RegulierungSection.jsx` (neuer `<ReguWizard>`-Block) | Analog `KlageWizard.jsx` |
| API-Endpoint | `POST /akten/<az>/regulierung/stellungnahme/generieren` | neu in `regulierung_routes.py` |
| Word-Generierung | `stellungnahme_service.py` | vorhanden, wird um Wizard-Input erweitert |
| Aktivitäten-Log | `logge_aktivitaet()` | Stellungnahme als Aktivität erfassen |

### Abhängigkeiten

- PRD-02 (textbaustein-Spalte befüllt + Replacement-Engine) → muss vorher fertig sein
- PRD-26 (KlageWizard) → Architektur-Vorlage für Step-Logik
- PRD-23b (Kürzungsparser) → Kürzungsbeträge automatisch vorausgefüllt

### Abnahmekriterium

Nach Durchlauf des Wizards liegt ein Word-Dokument vor, das:
- Alle akzeptierten Kürzungspositionen mit ihrem Gegenargument enthält
- Keine ungefüllten `<PLATZHALTER>` enthält
- Als Aktivität in der Akte protokolliert ist

---

## Reihenfolge der Implementierung

```
1. PRD-14  Frontend-Cleanup (UebersichtSection + RegulierungSection)        [0,5 h]
2. PRD-02a Import-Script + Platzhalter-Inventar                             [1 h]
3. Mapping-Review mit Anwalt (gemeinsam)                                    [0,5 h]
4. PRD-02b Replacement-Engine in stellungnahme_service.py                   [0,5 h]
5. PRD-27  ReguWizard UI + Backend-Endpoint + Word-Export                   [2–3 h]
```
