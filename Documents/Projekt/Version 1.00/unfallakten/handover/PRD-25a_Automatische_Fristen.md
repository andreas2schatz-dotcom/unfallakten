# PRD-25a – Automatische Fristerfassung
> Erstellt: 2026-04-03  
> Status: Bereit zur Implementierung  
> Abhängigkeiten: todos-Tabelle ✅, aktivitaeten-Tabelle ✅, word_service.py ✅  

---

## Ziel

Bei definierten Ereignissen legt das System automatisch Fristen als Todos an
(`quelle = 'system'`). Kein manuelles Eintragen mehr für:
- Verjährungsfristen nach §195 BGB (mit Vorfristen)
- §3a PflVG-Frist (3 Monate ab Forderungsschreiben-Versand)
- 2-Wochen-Antwortfrist nach eigenem Schreiben

Die `todos`-Tabelle ist bereits vorhanden und hat alle nötigen Felder
(`frist_typ`, `quelle`, `regel_key`, `faellig_am`).

---

## Frist-Regeln

### Regel 1 – Verjährung (§195 BGB)

**Auslöser:** Akte wird angelegt oder `unfalldatum` wird gesetzt/geändert  
**Logik:** `verjährungs_datum = unfalldatum + 3 Jahre (letzter Tag des Jahres, §199 BGB)`  

> Genau: §199 Abs. 1 BGB — Verjährung beginnt am Ende des Jahres, in dem der Anspruch
> entstanden ist. Beispiel: Unfall am 15.03.2023 → Verjährung am 31.12.2026.

**Erzeugte Todos (3 Stück):**

| regel_key | faellig_am | text |
|---|---|---|
| `verjährung_2m` | verjährungs_datum − 2 Monate | ⚠ Verjährung in 2 Monaten — Hemmung prüfen (§204 BGB) |
| `verjährung_1m` | verjährungs_datum − 1 Monat | ⚠ Verjährung in 1 Monat — letzte Chance zur Hemmung |
| `verjährung` | verjährungs_datum | ⚠ Verjährung heute — Akte prüfen |

**Doppelanlagen verhindern:** Vor Anlage prüfen ob ein Todo mit gleichem
`akte_az` + `regel_key` bereits existiert und `erledigt = 0`. Wenn ja → nicht neu anlegen.

---

### Regel 2 – §3a PflVG (3-Monats-Frist Versicherer)

**Auslöser:** Forderungsschreiben wird generiert (Hook in `word_service.py`)  
**Logik:** `pflvg_datum = heute + 3 Monate`  

**Erzeugte Todos (1 Stück):**

| regel_key | faellig_am | text |
|---|---|---|
| `pflvg_3a` | pflvg_datum | §3a PflVG-Frist — Versicherer muss bis heute reguliert oder begründet abgelehnt haben |

---

### Regel 3 – 2-Wochen-Antwortfrist

**Auslöser:** Jedes durch das System generierte Word-Dokument das an die Gegenseite geht  
Betrifft: `forderungsschreiben`, `sachstandsanfrage`, `stellungnahme`  
**Nicht für:** `abrechnungsuebersicht` (geht an Mandant), `vollmacht`  

**Erzeugte Todos (1 Stück):**

| regel_key | faellig_am | text |
|---|---|---|
| `antwort_2w_{dok_id}` | heute + 14 Tage | Antwort ausstehend: {dokument_typ} vom {datum} — nachhaken? |

---

## Backend-Implementierung

### Neue Datei: `backend/services/fristen_service.py`

```python
# Kernfunktionen:

def setze_verjaerungs_fristen(akte_az: str, unfalldatum: str) -> None:
    """Legt 3 Verjährungs-Todos an. Idempotent (prüft ob bereits vorhanden)."""

def setze_pflvg_frist(akte_az: str) -> None:
    """Legt §3a PflVG-Todo an."""

def setze_antwort_frist(akte_az: str, dok_id: int, dok_typ: str) -> None:
    """Legt 2-Wochen-Antwort-Todo für ein versandtes Dokument an."""

def _todo_existiert(akte_az: str, regel_key: str) -> bool:
    """Prüft ob offenes Todo mit diesem regel_key bereits existiert."""

def _erstelle_todo(akte_az: str, text: str, faellig_am: str,
                   frist_typ: str, regel_key: str, dok_id: int = None) -> int:
    """Legt Todo an. Gibt id zurück."""
```

### Hooks (wo wird fristen_service aufgerufen)

**1. `akten_routes.py` – POST /akten und PATCH /akten/<az>:**
```python
# Nach erfolgreichem Speichern wenn unfalldatum vorhanden:
from services.fristen_service import setze_verjaerungs_fristen
if daten.get("unfalldatum"):
    setze_verjaerungs_fristen(az, daten["unfalldatum"])
```

**2. `word_service.py` – `generiere_und_speichere()` nach Speichern:**
```python
from services.fristen_service import setze_pflvg_frist, setze_antwort_frist
GEGENSEITEN_TYPEN = {"forderungsschreiben", "sachstandsanfrage", "stellungnahme"}
if dok_typ == "forderungsschreiben":
    setze_pflvg_frist(akte_az)
if dok_typ in GEGENSEITEN_TYPEN:
    setze_antwort_frist(akte_az, dok_id, dok_typ)
```

### Migration

Keine neue Tabelle nötig. Neue `frist_typ`-Werte:
`verjährung`, `pflvg_3a`, `antwort_2w`

Neuer Index für schnellen Dashboard-Abruf:
```sql
CREATE INDEX IF NOT EXISTS idx_todos_faellig
    ON todos (erledigt, faellig_am);
```

---

## Neuer API-Endpunkt

```
GET /akten/<az>/todos/fristen
```
Gibt alle offenen Frist-Todos (quelle='system') für eine Akte zurück,
sortiert nach `faellig_am`. Wird vom Action-Dashboard (PRD-25b) genutzt.

Bestehender Endpunkt `GET /akten/<az>/todos` bleibt unverändert.

---

## Frontend

**In PRD-25b (Action-Dashboard) integriert** — kein separates Frontend nötig.

Optional: In `AkteDetailView.jsx` im Todos-Tab Frist-Todos visuell hervorheben
(rote Badge wenn `faellig_am` < heute + 14 Tage und `frist_typ` in Verjährungs-Typen).

---

## Session-Plan

| Session | Inhalt |
|---|---|
| 1 | `fristen_service.py` + `_todo_existiert` + `setze_verjaerungs_fristen` + Migration Index |
| 2 | Hooks in `akten_routes.py` + `word_service.py` + `setze_pflvg_frist` + `setze_antwort_frist` |
| 3 | Backfill-Skript für bestehende Akten + Tests |

---

## Backfill

Für bestehende Akten einmalig ausführen:
```python
# scripts/backfill_fristen.py
# Iteriert alle Akten mit unfalldatum → setze_verjaerungs_fristen()
# Iteriert alle forderungsschreiben-Dokumente → setze_pflvg_frist()
```
