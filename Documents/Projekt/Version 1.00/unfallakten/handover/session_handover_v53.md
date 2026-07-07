# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v53 – 25. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **37** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |
| LLM | Qwen via LM Studio lokal (Shadow-Mode für Regulierungsschreiben + Gutachten aktiv) |

---

## Erledigte Arbeiten v53

### PRD-31 – Akten Action Board (Übersicht-Umbau)

**Kernprinzip:** Übersicht-Tab von passivem Accordion-Stack in aktives Action Board umgebaut.

#### Neue Komponenten in `frontend/src/sections/UebersichtSection.jsx`

| Komponente | Funktion |
|---|---|
| `AkteActionBoardHeader` | Navy-Header mit AZ/Name, 4 Action-Buttons (Mandant anschreiben, Dokument hinzufügen, Termin, Stellungnahme), Vollmacht/IBAN/RSV-Status-Pills |
| `FinanzBand` | Gefordert / Reguliert / Offen / Kürzungen + Progress-Bar |
| `StatusBand` | Vollmacht-Pill, IBAN-Pill, RSV-Pill, §3a-Frist, Verjährung, Haftungsquote |
| `TodoWvSpalten` | 2-Spalten-Grid: offene To-Dos + fällige Wiedervorlagen |
| `TodoInlineForm` | Inline-Todo-Erfassung direkt im Board |
| `AkkordeonStrip` | 4 horizontale Tabs (To-Dos, Wiedervorlagen, Aktivitäten, RA-MICRO) als aufklappbarer Strip |
| `PwaNachrichtModal` | Modal zum Absenden von Nachrichten-Vorlagen ans Mandanten-Portal (Stub) |

#### Backend-Änderungen

| Datei | Änderung |
|---|---|
| `backend/routers/akten_routes.py` | `_akte_komplett()` liefert jetzt `kurzbezeichnung` + `hq`; neuer Endpoint `POST /<az>/pwa-nachricht` speichert als `aktivitaeten`-Eintrag (Stub, kein echtes Push) |
| `backend/routers/ramicro_akte_routes.py` | `mandant-checks` liefert `rechtsschutz_deckung` (RSV-Bool via RA-MICRO `tblAktenBeteiligte WHERE iBeteiligtenArt=3 AND bDeaktiviert=0`), `kurzbezeichnung` und `bezeichnung` aus `tblAkten` |
| `frontend/src/api.js` | `akten.pwaMessage(az, text, vorlageKey)` → `POST /akten/<az>/pwa-nachricht` |

#### Bug-Fixes während Implementierung

| Bug | Fix |
|---|---|
| RSV-Check nutzte SQLite `beteiligte WHERE rolle='rechtsschutz'` → CHECK-Constraint-Fehler | Auf RA-MICRO `tblAktenBeteiligte WHERE iBeteiligtenArt=3 AND bDeaktiviert=0` umgestellt |
| Keine-RSV-Pill zeigte rot statt neutral | `Pill`-Komponente um `neutral`-Prop erweitert |
| Badge-Timestamps für Dokumente/Regulierung nicht reaktiv | Von useMemo-Read auf React State (`besuchDok`, `besuchReg`) mit lazy localStorage-Init umgestellt |
| Header-Kurz/Lang-Bezeichnung leer | RA-MICRO-Query um `sAktenKurzBezeichnung`/`sAktenBezeichnung` erweitert + als Fallback via `ibanCheck`-Prop weitergereicht |

#### Navigation-Anbindung in `frontend/src/components/AkteDetailView.jsx`

- `UebersichtSection` erhält `onNavigate={setSec}` → Tab-Wechsel per Button aus dem Board möglich
- `"⚡ Übersicht"` als Tab-Label für ersten Tab
- Badges für Dokumente-Tab (`📄 Dokumente (N) 🔴M`) via React State, mit Timestamp-Update bei Tab-Klick

#### Commits dieser Session (älteste zuerst)

```
45273f7  feat(mandant-checks): rechtsschutz_deckung aus SQLite beteiligte
70394b3  fix(mandant-checks): RSV-Check via RA-MICRO tblAktenBeteiligte
3ddb8fe  fix(mandant-checks): RSV-Query bDeaktiviert=0 Filter ergänzt
3280d34  feat(akten): POST pwa-nachricht Stub-Endpunkt
0cde998  fix(akten): pwa-nachricht Fehler-Responses via _err()
e9186b6  feat(api): akten.pwaMessage()
ffecb2d  feat(uebersicht): PwaNachrichtModal mit Vorlagen
21b19c8  feat(uebersicht): AkteActionBoardHeader + TodoInlineForm
b40982b  feat(uebersicht): StatusBand + FinanzBand Komponenten
47e8e73  feat(uebersicht): TodoWvSpalten 2-Spalten-Body
b569f23  feat(uebersicht): AkkordeonStrip horizontale Buttonleiste
116d7af  feat(uebersicht): Action Board Zusammenbau
9a2be40  fix(uebersicht): azKlappKey via azRoh deduplizieren
a1331d6  fix(uebersicht): onNavigate Prop verdrahten für Word-Tab-Button
1299000  feat(navigation): Übersicht-Label + Badges + onNavigate
8a16f92  fix(navigation): Badge-State als React-State + Dokumente-Count
9dbe827  fix(action-board): IMP-01 Kurz/Lang + IMP-03 Keine-RSV-Pill neutral
4ebe6ed  feat: KI-Parsing, OCR-Override, LLM-UI, Dokumente-Inbox, Suche-Autocomplete
```

---

## Nächste Session: PRD-31 Bugfixes (Deferred IMP Issues)

Die folgende Liste wurde vom Code-Review nach der Implementierung erstellt und für die nächste Session zurückgestellt.

### IMP-02 — RSV "anfrage"-Zustand nicht erreichbar

**Problem:** `AkteActionBoardHeader` rendert `<Pill warn={rsv === "anfrage"} ...>`, aber `mandant-checks` liefert nur `true` / `false` für `rechtsschutz_deckung`. Der `"anfrage"`-Zweig ist toter Code.

**Fix-Optionen:**
- Option A (einfach): `warn`-Prop aus der RSV-Pill entfernen; nur `ok={bool}` + `neutral={!bool}` verwenden.
- Option B (vollständig): Neuen Status `"anfrage"` in `mandant-checks` einführen: SQLite-`aktivitaeten`-Eintrag `aktion='rsv_anfrage'` prüfen; wenn vorhanden und `rechtsschutz_deckung=false`, dann `"anfrage"` zurückgeben.

**Empfehlung:** Option A als Sofort-Fix. Option B als eigenes Feature wenn RSV-Workflow umgebaut wird.

**Dateien:** `backend/routers/ramicro_akte_routes.py` (mandant-checks Endpoint) + `frontend/src/sections/UebersichtSection.jsx` (RSV-Pill in `AkteActionBoardHeader`)

---

### IMP-04 — Doppelter `apiTodos.liste()`-Fetch

**Problem:** `StatusBand` und `TodoWvSpalten` rufen beide unabhängig `apiTodos.liste(azRoh)` auf. Bei Akte-Laden → 2 parallele Requests.

**Fix:** Todos-Fetch in `UebersichtSection` hochziehen, Ergebnis als Prop weitergeben:

```jsx
// In UebersichtSection
const [todos, setTodos] = useState([]);
useEffect(() => {
  if (!azRoh) return;
  apiTodos.liste(azRoh).then(r => setTodos(r.todos || []));
}, [azRoh]);

// StatusBand und TodoWvSpalten erhalten: todos={todos}
// Beide entfernen ihren eigenen fetch-useEffect
```

**Dateien:** `frontend/src/sections/UebersichtSection.jsx` (Zeilen ~1800–1900 für StatusBand-Fetch; ~2050–2100 für TodoWvSpalten-Fetch)

---

### IMP-05 — `pwa_nachricht_senden` nutzt kein `logge_aktivitaet()`-Helper

**Problem:** Der Endpoint macht ein rohes `conn.execute(INSERT INTO aktivitaeten ...)` statt den Projekt-Standard `logge_aktivitaet()` zu verwenden.

**Fix:**
```python
# Ersetze in backend/routers/akten_routes.py, Funktion pwa_nachricht_senden:
# Alt:
with get_connection() as conn:
    cursor = conn.execute(
        "INSERT INTO aktivitaeten (akte_id, benutzer_id, aktion, beschreibung, tabelle) VALUES (?, ?, 'pwa_nachricht', ?, 'pwa')",
        (az, benutzer_id, beschreibung)
    )
    akt_id = cursor.lastrowid

# Neu:
akt_id = logge_aktivitaet(az, benutzer_id, "pwa_nachricht", beschreibung, "pwa")
```

Sicherstellen, dass `logge_aktivitaet` in `akten_routes.py` importiert ist (vermutlich aus `..services.aktivitaet_service` oder ähnlich).

**Dateien:** `backend/routers/akten_routes.py`

---

### IMP-06 — Badge-Timestamp bei Erst-Besuch nicht gesetzt

**Problem:** Beim ersten Öffnen einer Akte (mit Tab "Dokumente" bereits aktiv) wird kein Timestamp gesetzt. Erst beim nächsten manuellen Tab-Klick lernt das System den Besuchszeitpunkt. Neue Dokumente, die nach dem Erst-Besuch hochgeladen werden, würden trotzdem als "neu" markiert.

**Fix:** In `AkteDetailView.jsx` einen `useEffect` ergänzen, der bei Mount den Timestamp setzt wenn der aktive Tab bereits "dokumente" oder "regulierung" ist:

```jsx
useEffect(() => {
  if (!akte?.az) return;
  const now = new Date().toISOString();
  if (sektion === "dokumente" && !besuchDok) {
    localStorage.setItem(lsKeyDok, now);
    setBesuchDok(now);
  }
  if (sektion === "regulierung" && !besuchReg) {
    localStorage.setItem(lsKeyReg, now);
    setBesuchReg(now);
  }
}, [akte?.az]); // Nur beim Laden einer neuen Akte
```

**Dateien:** `frontend/src/components/AkteDetailView.jsx`

---

## Offene Suggestions (niedrige Priorität)

| # | Problem | Fix |
|---|---|---|
| SUG-01 | `neueDokumente`-Pluralisierung ist no-op | `neueDokumente === 1 ? "Dokument" : "Dokumente"` im Badge-Label |
| SUG-02 | `TodoKachelKompakt` hat toten `timeout`/cleanup-Code | Entfernen |
| SUG-03 | `BTN`-Objekt in `AkteActionBoardHeader` wird bei jedem Render neu erstellt | `const BTN = { ... }` vor die Komponente verschieben |
| SUG-04 | `mandant-checks` wird zweimal beim Mount aufgerufen (IBAN + RSV) | Einzelner Fetch, beide Ergebnisse zusammen zurückgeben |
| SUG-06 | `T.amber + "80"` Hex-Alpha-Concat funktioniert nicht wenn `T.amber` jemals zu `oklch(...)` wechselt | `T.amber + "cc"` auf `color-mix(in oklch, ${T.amber} 50%, transparent)` umstellen |

---

## Offene PRDs (Gesamt-Übersicht)

| PRD | Titel | Status |
|---|---|---|
| PRD-31 IMP | Action Board Bugfixes (IMP-02/04/05/06) | **Nächste Session** |
| PRD-33 | Feintuning Klage-Wizard | Debugging-Pass ausstehend |
| PRD-32 Phase 2 | Rechnungstypen-Beleg-Mapping | Phase 1 ✅, Phase 2 offen |
| PRD-27 | ReguWizard – Stellungnahme | Planung offen |
| PRD-25c | Mandantenkommunikation | Planung offen |

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

### RSV-Check (RA-MICRO, nicht SQLite!)

```python
# SQLite beteiligte hat kein 'rechtsschutz'-Rolle (CHECK constraint verletzt)
# Immer RA-MICRO abfragen:
cursor.execute(
    "SELECT COUNT(*) FROM tblAktenBeteiligte WHERE GUIDAkte = %s AND iBeteiligtenArt = 3 AND bDeaktiviert = 0",
    (guid,)
)
```

### Option B – Regulierungslogik

- `regulierung`-Tabelle **deprecated** (Endpunkte erhalten, kein neuer Code schreibt dort)
- **Neue Datenquelle:** `abrechnungsschreiben` + `regulierung_positionen` + `v_regulierungsstatus`
- **Summierung:** Immer über alle `regulierung_positionen` je `akte_id` aggregieren

### Pre-existing Testfehler

`test_prd23b.py` (7 Failures) und `test_modul8.py` (16 Errors) schlagen seit vor PRD-31 fehl – nicht durch Action Board verursacht. Sind keine Blocker.
