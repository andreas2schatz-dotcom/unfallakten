# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v54 – 25. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **37** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true), read-only |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode: Regulierungsschreiben + Gutachten) |

---

## Erledigte Arbeiten v54

### Schwerpunkt: Code-Konsolidierung & Dokumentation

Session v54 hat keine neuen Features eingeführt, sondern bestehenden Code stabilisiert und die Planungsdokumente grundlegend überarbeitet.

#### Commits dieser Session

```
e3ea0f3  chore(v54): Code-Konsolidierung, Neue-Akte-Stub, Architecture-Docs v54
1fb361a  fix(header): SB+KFZ-Daten im Header, Kurzbez-Größe, Portal-Checkbox, ladeHeaderTodos
6f3c46e  fix(prd31): IMP-02/04/05/06 + Option-C Header + Button-Umbenennung
6a7066f  fix(action-board): Buttons Word + Klage umbenennen
fae4cf9  fix(action-board): IMP-02/04/05/06 deferred bugs aus PRD-31
```

#### Frontend-Änderungen

| Datei | Änderung |
|---|---|
| `AkteDetailView.jsx` | Header-Textfarbe/-größe für bessere Lesbarkeit (Kurzbezeichnung: rgba 0.55→0.78, Meta-Zeile: 0.72rem→0.87rem) |
| `UebersichtSection.jsx` | `stripOffene` Default auf `["regulierung"]` → Regulierungs-Tab im AkkordeonStrip standardmäßig aufgeklappt |
| `AktensucheView.jsx` | `NeueAkteModal`-Komponente eingebaut (Stub für PRD-NEW Onboarding-Wizard): AZ, Unfalldatum, Unfallort, Notizen |

#### PRD-31 Bugfixes (aus v53 zurückgestellt)

| IMP | Problem | Fix |
|---|---|---|
| IMP-02 | RSV `"anfrage"`-Zustand nicht erreichbar | `warn`-Prop entfernt, nur `ok`/`neutral` |
| IMP-04 | Doppelter `apiTodos.liste()`-Fetch | Todos-Fetch in `UebersichtSection` hochgezogen, als Prop weitergereicht |
| IMP-05 | `pwa_nachricht_senden` nutzte rohes INSERT | `logge_aktivitaet()` verwendet |
| IMP-06 | Badge-Timestamp bei Erst-Besuch nicht gesetzt | `useEffect` in `AkteDetailView` bei Akte-Mount ergänzt |

#### Dokumentation überarbeitet

| Datei | Änderung |
|---|---|
| `handover/architecture.md` | Aktualisiert auf v54: Tab-Reihenfolge mit PRD-16-Ausblick, LM-Studio-Eintrag, Neue-Akte-Stub |
| `handover/dokumenten_workflow_konzept.md` | Komplett auf **Version 4** umgeschrieben: Workflow-Phasen (Onboarding + Regulierung), Gap-Analyse, neue PRD-Priorisierungsliste |

---

## Nächste Session: PRD-14 Frontend-Cleanup

### PRD-14 – Single Source of Truth: Abrechnungsart

**Status:** Backend ✅, Frontend-Cleanup ⬜  
**Schätzung:** 0,5 Sessions

**Problem:** Die Betrag-Berechnung (fiktiv / konkret / Totalschaden) ist an 3 Frontend-Stellen gespiegelt. Das Backend liefert bereits `abrechnungsberechnung.gesamt_brutto` korrekt — das Frontend muss nur darauf umstellen.

#### Was fehlt

```javascript
// 1. UebersichtSection.jsx – _fzg()-Funktion entfernen (~Zeile 1789)
//    Stattdessen: st.schaden?.abrechnungsberechnung?.gesamt_brutto lesen

// 2. RegulierungSection.jsx – lokale Betrag-Berechnung entfernen (~Zeile 1776)
//    Stattdessen: st.schaden?.abrechnungsberechnung verwenden
```

#### Checkliste
- [ ] `UebersichtSection.jsx`: `_fzg()` entfernen, `st.schaden.abrechnungsberechnung` lesen
- [ ] `RegulierungSection.jsx`: lokale Betrag-Berechnung auf Backend-Wert umstellen
- [ ] Regressionstest: gleiche Beträge in Übersicht, Regulierung und Header

**Abnahmekriterium:** Betrag in Übersicht, Regulierung und Header sind identisch.

---

## Offene PRDs (Gesamt-Übersicht)

```
── KRITISCH (sofort) ────────────────────────────────────────────
PRD-14   Single Source of Truth: Abrechnungsart (Frontend-Cleanup)   ← Nächste Session
PRD-02   Textbaustein-Feld Kürzungsarten (Voraussetzung für PRD-27)
PRD-27   ReguWizard – Stellungnahme-Wizard (größter Effizienz-Hebel)

── BALD (nächste 3 Sessions) ────────────────────────────────────
PRD-16   Tab-Reihenfolge als Workflow-Ablauf
PRD-18   Statusmodell + Phasen-Strip (hängt an PRD-14)
PRD-NEW  Onboarding-Wizard (Stub in v54 vorhanden)
PRD-17   Tagesstart-Dashboard

── MITTEL ───────────────────────────────────────────────────────
PRD-03   Klagegenerator Abschlusstest
PRD-33   Klage-Wizard Feintuning (Formatierung + Textbausteine)
PRD-04   Erweiterte Dokumentenklassen (Klasse A/B/C)
PRD-32   Rechnungstypen-Parser Phase 2 (Beleg-Mapping)
PRD-05   Betrag-Abgleich nach Upload
PRD-25c  Mandantenkommunikation

── SPÄTER ───────────────────────────────────────────────────────
PRD-01   To-Do-System Vollausbau (Action Board deckt 70 % ab)
PRD-06   Parser Reparaturrechnung LLM
PRD-07   Workflow-Regeln + automatische To-Dos
PRD-19   RA-Micro DMS Integration (Read-Only)
```

---

## Wichtige Architektur-Hinweise

### v14c-Muster (kritisch!)

```python
akte_obj = _pruefe_akte(akte_id)
if not akte_obj:
    return _err(...)
az = akte_obj.aktenzeichen if hasattr(akte_obj, "aktenzeichen") else akte_id
# Alle DB-Queries mit az, nie mit akte_id
```

### Option B – Regulierungslogik

- `regulierung`-Tabelle **deprecated** (Endpunkte erhalten, kein neuer Code schreibt dort)
- **Neue Datenquelle:** `abrechnungsschreiben` + `regulierung_positionen` + `v_regulierungsstatus`
- **Summierung:** Immer über alle `regulierung_positionen` je `akte_id` aggregieren

### RSV-Check (RA-MICRO, nicht SQLite!)

```python
# SQLite beteiligte hat kein 'rechtsschutz'-Rolle (CHECK-Constraint)
# Immer RA-MICRO abfragen:
cursor.execute(
    "SELECT COUNT(*) FROM tblAktenBeteiligte WHERE GUIDAkte = %s AND iBeteiligtenArt = 3 AND bDeaktiviert = 0",
    (guid,)
)
```

### Pre-existing Testfehler

`test_prd23b.py` (7 Failures) und `test_modul8.py` (16 Errors) schlagen seit vor PRD-31 fehl — kein Blocker, nicht durch v54 verursacht.
