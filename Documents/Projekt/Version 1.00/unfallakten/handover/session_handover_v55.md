# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v55 – 29. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **37** (unverändert) |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true), read-only |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode) |

---

## Erledigte Arbeiten v55

### Schwerpunkt: Klagewizard-Fixes + Streitwert-Korrektheit

Diese Session hat keine DB-Migrationen eingeführt. Alle Fixes betreffen Frontend und Backend-Logik.

#### Commits dieser Session

(Änderungen noch nicht committed — alle Dateien sind live via Volume-Mount)

Geänderte Dateien:
- `backend/routers/klage_routes.py`
- `backend/word/word_service.py`
- `frontend/src/sections/KlageSection.jsx`

---

### Fix 1: Klagewizard Gegner-Fallback aus RA-MICRO (Bug: Deutsches Büro Grüne Karte fehlte)

**Problem:** `_lade_beteiligte_aus_ramicro()` gibt nur den **ersten** Gegner zurück. Da GHPV (z.B. HUK-Coburg) Sort-Rang 0 hat, verdrängte die Versicherung den echten Gegner (z.B. Deutsches Büro Grüne Karte, Rang 2–3). Zusätzlich blockierte `_hat_parteien` den RA-MICRO-Fallback komplett wenn GHPV als `rolle="gegner"` in SQLite gespeichert war.

**Fix in `word_service.py` (`_lade_beteiligte_aus_ramicro`):**
- `result` enthält jetzt `"alle_gegner": []` zusätzlich zu `"gegner"` (erster/höchst-priorisierter)
- In der Schleife: alle Gegner-Einträge werden in `alle_gegner` gesammelt; `gegner` bleibt für Rückwärts-Kompatibilität (Word-Briefe, beteiligte_routes)
- `d["id"] = adr_nr` setzt die echte RA-MICRO-Adressnummer je Eintrag

**Fix in `klage_routes.py`:**
- `_hat_parteien` ersetzt durch `_hat_mandant`
- RA-MICRO wird **immer** geladen (nicht nur als Fallback)
- Mandant: nur ergänzt wenn `_hat_mandant = False`
- Gegner: **alle** aus `alle_gegner` werden per Namens-Dedup in `alle_bet` gemergt
- `_namen_bet` wird nach jedem Merge-Eintrag aktualisiert (verhindert Duplikate zwischen Einträgen)

**Fix: Checkbox-Bug (alle Beklagte gleichzeitig togglen):**
- Ursache: alle RA-MICRO-Einträge hatten `id = 0` (kein `id`-Feld in `_beteiligter_dict`)
- Fix: `d["id"] = adr_nr` liefert eindeutige RA-MICRO-Adressnummern → `toggleBek(id)` matched korrekt

---

### Fix 2: Tab-Reihenfolge PRD-16 (committed d2748df)

Tabs umgeordnet: Übersicht → Beteiligte → Unfalldetails → Schaden → Dokumente → Regulierung → **Klage → Word → Gebühren** (To-Dos-Tab entfernt, Button → Übersicht).

---

### Fix 3: Phasen-Strip PRD-18 (committed 3f34ed5)

`PhasenStrip`-Komponente in `UebersichtSection.jsx` hinzugefügt. Automatische Phasenderivation aus bestehendem State (kein DB-Migration). 5 Phasen: Onboarding → Erstforderung → Regulierung → Stellungnahme → Abschluss (bei Klage: „⚖ Klage").

---

### Fix 4: Abrechnungsart-Bug – KPI/Übersicht nicht aktualisiert (committed 0caaa4a)

`SAVE_SCHADEN`-Dispatch in `SchadenSection.jsx` schrieb `abrechnungsberechnung` aus der Server-Antwort nicht in den Redux-State. KPI und Übersicht lasen aber `st.schaden.abrechnungsberechnung?.gesamt_brutto`. Fix: beide `SAVE_SCHADEN`-Dispatches ergänzt um `abrechnungsberechnung: serverSchaden.abrechnungsberechnung`.

---

### Fix 5: Gerichtlicher Streitwert falsch (zu hoch)

**Problem:** `klagebetrag` in `KlageSection.jsx` summierte alle angehakten Positionen ohne Abzug der Regulierungen. Ein ungebundener Vorschuss (z.B. €10.000) wurde gar nicht berücksichtigt. RA-MICRO-Fallback und positions-gebundene Zahlungen wurden getrennt behandelt.

**Fix in `KlageSection.jsx`:**

```javascript
// Gesamte regulierte Zahlung (inkl. Vorschüsse ohne Positionszuordnung)
const gesamtReguliert = (daten?.abrechnungen || []).reduce(
  (s, a) => s + (parseFloat(a.gesamt_reguliert) || 0), 0
);
// Gerichtlicher Streitwert = angehakte Positionen minus bereits gezahlte Beträge
const klagebetrag = Math.max(0,
  positionen.filter(p => p.checked).reduce((s, p) => s + (p.betrag || 0), 0)
  - gesamtReguliert
);
```

**Fix in `oeffneWizard` (für Wizard Step 5):**
1. Schritt 1: positions-gebundene Regulierungen per `_regMap` abziehen (wie bisher)
2. Schritt 2: verbleibender ungebundener Betrag (`gesamtReguliert - _posLevelPaid`) wird gierig auf die größten Positionen verteilt → `sum(wizardPos.betrag)` = korrekter `klagebetrag`
3. Alle Klagebetrag-Berechnungen im Wizard (Step 5, Step 10, Anträge-Text) werden automatisch korrekt, da sie aus `wizardPos` rechnen.

---

## Noch zu committen (diese Session)

```bash
git add backend/routers/klage_routes.py \
        backend/word/word_service.py \
        frontend/src/sections/KlageSection.jsx
git commit -m "fix(klage): Alle-Gegner aus RA-MICRO + gerichtlicher Streitwert korrekt"
```

---

## Offene PRDs (aktualisiert)

```
── ERLEDIGT in v55 ──────────────────────────────────────────────
PRD-16   Tab-Reihenfolge ✅ (d2748df)
PRD-18   Phasen-Strip ✅ (3f34ed5)
PRD-14   Abrechnungsart SSoT ✅ (0341e54 + 0caaa4a)

── KRITISCH (sofort) ────────────────────────────────────────────
PRD-02   Textbaustein-Feld Kürzungsarten ✅ (2e1e0fb)
PRD-27   ReguWizard ✅ (2e1e0fb)

── BALD (nächste 2–3 Sessions) ──────────────────────────────────
PRD-NEW  Onboarding-Wizard (Stub in v54 vorhanden)
PRD-33   Klage-Wizard Feintuning (Formatierung + Textbausteine)
PRD-25c  Mandantenkommunikation
PRD-29   DKz-Filter E-Akte (Plan noch ausstehend)

── MITTEL ───────────────────────────────────────────────────────
PRD-32   Rechnungstypen-Parser Phase 2 (Beleg-Mapping)
PRD-04   Erweiterte Dokumentenklassen (Klasse A/B/C)
PRD-05   Betrag-Abgleich nach Upload
PRD-22c  Mandanten-Fragebogen Session 4–5

── SPÄTER ───────────────────────────────────────────────────────
PRD-01   To-Do-System Vollausbau
PRD-06   Parser Reparaturrechnung LLM
PRD-07   Workflow-Regeln + automatische To-Dos
PRD-17   Tagesstart-Dashboard
PRD-19   RA-Micro DMS Integration (Read-Only)
```

---

## Wichtige Architektur-Hinweise (für nächste Session)

### RA-MICRO Beteiligte im Klagewizard (NEU v55)

```python
# _lade_beteiligte_aus_ramicro() gibt jetzt zurück:
# { "mandant": dict|None, "gegner": dict|None, "alle_gegner": list }
# "gegner" = erster (GHPV-Priorität), für Briefe/Word
# "alle_gegner" = ALLE Gegner, für Klagewizard

# In klage_routes.py:
# - RA-MICRO immer laden (kein _hat_parteien-Guard mehr)
# - Mandant: nur wenn _hat_mandant=False
# - Gegner: alle aus alle_gegner, per Namens-Dedup
```

### Streitwert-Logik (NEU v55)

```javascript
// KlageSection.jsx
// gesamtReguliert = sum(a.gesamt_reguliert) über alle Abrechnungen
// → inkl. Vorschüsse ohne Positionszuordnung
// klagebetrag (gerichtlich) = checked_positionen_sum - gesamtReguliert
// swAusserg (außergerichtlich) = alle_positionen_sum (unverändert)
```

### v14c-Muster (kritisch!)

```python
akte_obj = _pruefe_akte(akte_id)
if not akte_obj:
    return _err(...)
az = akte_obj.aktenzeichen if hasattr(akte_obj, "aktenzeichen") else akte_id
```

### Option B – Regulierungslogik

- `regulierung`-Tabelle **deprecated** (Endpunkte erhalten, kein neuer Code schreibt dort)
- **Neue Datenquelle:** `abrechnungsschreiben` + `regulierung_positionen`
- **Summierung:** Immer über alle `regulierung_positionen` je `akte_id` aggregieren

### Pre-existing Testfehler

`test_prd23b.py` (7 Failures) und `test_modul8.py` (16 Errors) schlagen seit vor PRD-31 fehl — kein Blocker.
