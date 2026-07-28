# Review-Queue Sortier-Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ein Auf/Ab-Sortier-Toggle für das Eingangsdatum in der Review-Queue, damit manuell importierte (also neu eingegangene) Dokumente schnell auffindbar sind.

**Architecture:** Rein clientseitig in `frontend/src/views/ReviewQueueView.jsx`. Die vom Server gelieferte Reihenfolge (`erstellt_am ASC, konfidenz DESC` aus `backend/routers/intake_routes.py:163`) bleibt unverändert die Datenquelle. Ein neuer boolescher State `sortAbsteigend` steuert, ob die bereits gruppierte Liste (`gruppiereQueue()`) in Original-Reihenfolge oder umgekehrt gerendert wird. Kein Backend-Eingriff.

**Tech Stack:** React (Hooks: `useState`, `useMemo`, `useCallback`), Vitest für Unit-Tests, `localStorage` für Persistenz (Browser-API, kein zusätzliches Package).

## Global Constraints

- Keine Backend-Änderung (Spec Entscheidung 2): Server-Query/Reihenfolge bleibt exakt wie in `intake_routes.py:163`.
- Sortierung wirkt auf Gruppen-Ebene, nicht auf einzelne Kind-Dokumente (Spec Entscheidung 3).
- Toggle nur sichtbar in der Queue-Ansicht (`ansicht === "queue"`), nicht im Papierkorb-Tab (Spec Entscheidung 5).
- Persistenz über `localStorage` (Spec Entscheidung 4), Schlüssel `"reviewQueueSortAbsteigend"`, Wert `"true"`/`"false"` als String (Konvention siehe `frontend/src/components/AkteDetailView.jsx:192-204`, gleiches Muster ohne try/catch).
- Deutsch als Zielsprache: alle sichtbaren Labels und Kommentare auf Deutsch (Projektkonvention laut `CLAUDE.md`).
- Keine Kommentare im Code außer bei nicht-offensichtlichem Verhalten (`CLAUDE.md`).

---

### Task 1: Pure Sortier-Helper `sortiereGruppen`

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (neue Export-Funktion direkt nach `gruppiereQueue`, aktuell Zeile 49–70)
- Test: `frontend/src/views/ReviewQueueView.sortierung.test.jsx` (neu)

**Interfaces:**
- Produces: `export function sortiereGruppen(gruppen: Array<{eintrag: object, kinder: object[]}>, absteigend: boolean): Array<{eintrag: object, kinder: object[]}>` — gibt bei `absteigend=false` die Eingabe-Referenz-Reihenfolge unverändert (neues Array, keine Mutation) zurück, bei `absteigend=true` die umgekehrte Reihenfolge. Wird von Task 2 im Rendering verwendet.

- [ ] **Step 1: Schreibe den fehlschlagenden Test**

Erstelle `frontend/src/views/ReviewQueueView.sortierung.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { sortiereGruppen } from "./ReviewQueueView.jsx";

describe("sortiereGruppen", () => {
  const gruppen = [
    { eintrag: { id: 1 }, kinder: [] },
    { eintrag: { id: 2 }, kinder: [] },
    { eintrag: { id: 3 }, kinder: [] },
  ];

  it("gibt die Liste unveraendert zurueck wenn absteigend=false", () => {
    const res = sortiereGruppen(gruppen, false);
    expect(res.map(g => g.eintrag.id)).toEqual([1, 2, 3]);
  });

  it("kehrt die Reihenfolge um wenn absteigend=true", () => {
    const res = sortiereGruppen(gruppen, true);
    expect(res.map(g => g.eintrag.id)).toEqual([3, 2, 1]);
  });

  it("veraendert das Eingabe-Array nicht (keine Mutation)", () => {
    const original = [...gruppen];
    sortiereGruppen(gruppen, true);
    expect(gruppen).toEqual(original);
  });
});
```

- [ ] **Step 2: Test ausführen, Fehlschlag bestätigen**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.sortierung.test.jsx`
Expected: FAIL — `sortiereGruppen is not exported by "./ReviewQueueView.jsx"` (oder `undefined is not a function`).

- [ ] **Step 3: Implementiere die minimale Funktion**

In `frontend/src/views/ReviewQueueView.jsx`, direkt nach dem Ende von `gruppiereQueue` (nach der schließenden `}` in Zeile 70, vor `export function TextVorschau` in Zeile 72), einfügen:

```jsx
export function sortiereGruppen(gruppen, absteigend) {
  return absteigend ? [...gruppen].reverse() : gruppen;
}
```

- [ ] **Step 4: Test ausführen, Erfolg bestätigen**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.sortierung.test.jsx`
Expected: PASS (3/3 Tests grün).

- [ ] **Step 5: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/ReviewQueueView.jsx" "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/ReviewQueueView.sortierung.test.jsx"
git commit -m "feat(review-queue): sortiereGruppen-Helper fuer Auf/Ab-Sortierung"
```

---

### Task 2: State, Toggle-Button und Persistenz verdrahten

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (State-Deklarationen ~Zeile 1260–1268, Handler-Block ~Zeile 1331–1341, Header-JSX ~Zeile 1357–1381, Render-Zeile 1396)

**Interfaces:**
- Consumes: `sortiereGruppen(gruppen, absteigend)` aus Task 1, `gruppiereQueue(queue)` (bestehend, Zeile 49).
- Produces: keine neuen Exporte — reine Komponenten-internes Wiring. Sichtbares Verhalten: Button-Label `"🕓 Älteste zuerst"` / `"🕓 Neueste zuerst"`, `localStorage`-Key `"reviewQueueSortAbsteigend"`.

- [ ] **Step 1: State für Sortierrichtung ergänzen**

In `frontend/src/views/ReviewQueueView.jsx`, Zeile 1268 (`const [papierkorb, setPapierkorb] = useState([]);`) wird gefolgt von:

```jsx
  const [papierkorb, setPapierkorb] = useState([]);
  const [sortAbsteigend, setSortAbsteigend] = useState(
    () => localStorage.getItem("reviewQueueSortAbsteigend") === "true"
  );
```

- [ ] **Step 2: Toggle-Handler ergänzen**

Nach dem Ende von `doVerwerfen` (schließt mit `}, [verwerfenDok, aktivId, laden]);` in Zeile 1331), vor der `bereit`-Definition (Zeile 1333), einfügen:

```jsx
  const toggleSortRichtung = useCallback(() => {
    setSortAbsteigend(v => {
      const next = !v;
      localStorage.setItem("reviewQueueSortAbsteigend", String(next));
      return next;
    });
  }, []);
```

- [ ] **Step 3: Gruppierte + sortierte Liste als `useMemo` ableiten**

Nach der `fehler`-Definition (schließt mit `}, [queue]);` in Zeile 1340), vor `onFreigegeben` (Zeile 1342), einfügen:

```jsx
  const gruppen = useMemo(
    () => sortiereGruppen(gruppiereQueue(queue), sortAbsteigend),
    [queue, sortAbsteigend],
  );
```

- [ ] **Step 4: Render-Stelle auf `gruppen` umstellen**

In Zeile 1396 ersetzen:

Vorher:
```jsx
              {gruppiereQueue(queue).map(gruppe => (
```

Nachher:
```jsx
              {gruppen.map(gruppe => (
```

- [ ] **Step 5: Toggle-Button im Queue-Header ergänzen**

Der bestehende Header-Block (Zeile 1357–1381) sieht so aus:

```jsx
        <div style={{
          padding: "12px 14px", borderBottom: `1px solid ${T.border}`,
          background: T.navy, color: T.white,
        }}>
          <div style={{ fontSize: T.textXs, opacity: 0.7, letterSpacing: "0.1em" }}>
            REVIEW-QUEUE
          </div>
          <div style={{ fontSize: T.textLg, fontFamily: T.fontDisplay }}>
            {bereit.length} bereit · {fehler.length} fehlerhaft
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            {["queue", "papierkorb"].map(a => (
              <button key={a} onClick={() => setAnsicht(a)}
                style={{
                  flex: 1, padding: "4px 8px", fontSize: T.textXs,
                  fontWeight: 600, cursor: "pointer", borderRadius: 4,
                  border: `1px solid ${T.white}40`,
                  background: ansicht === a ? T.white : "transparent",
                  color: ansicht === a ? T.navy : T.white,
                }}>
                {a === "queue" ? "Queue" : "Papierkorb"}
              </button>
            ))}
          </div>
        </div>
```

Ersetze den Block durch (neuer Button nach der `queue`/`papierkorb`-Zeile, vor dem schließenden `</div>` des Headers):

```jsx
        <div style={{
          padding: "12px 14px", borderBottom: `1px solid ${T.border}`,
          background: T.navy, color: T.white,
        }}>
          <div style={{ fontSize: T.textXs, opacity: 0.7, letterSpacing: "0.1em" }}>
            REVIEW-QUEUE
          </div>
          <div style={{ fontSize: T.textLg, fontFamily: T.fontDisplay }}>
            {bereit.length} bereit · {fehler.length} fehlerhaft
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            {["queue", "papierkorb"].map(a => (
              <button key={a} onClick={() => setAnsicht(a)}
                style={{
                  flex: 1, padding: "4px 8px", fontSize: T.textXs,
                  fontWeight: 600, cursor: "pointer", borderRadius: 4,
                  border: `1px solid ${T.white}40`,
                  background: ansicht === a ? T.white : "transparent",
                  color: ansicht === a ? T.navy : T.white,
                }}>
                {a === "queue" ? "Queue" : "Papierkorb"}
              </button>
            ))}
          </div>
          {ansicht === "queue" && (
            <button onClick={toggleSortRichtung}
              style={{
                width: "100%", marginTop: 6, padding: "4px 8px", fontSize: T.textXs,
                fontWeight: 600, cursor: "pointer", borderRadius: 4,
                border: `1px solid ${T.white}40`, background: "transparent", color: T.white,
              }}>
              {sortAbsteigend ? "🕓 Neueste zuerst" : "🕓 Älteste zuerst"}
            </button>
          )}
        </div>
```

- [ ] **Step 6: Bestehende Frontend-Suite ausführen**

Run: `cd frontend && npx vitest run`
Expected: alle Tests grün, insbesondere `ReviewQueueView.*.test.jsx` und `__tests__/QueueGruppen.test.jsx` weiterhin PASS (keine Regression durch die Umbenennung von `gruppiereQueue(queue).map` auf `gruppen.map`).

- [ ] **Step 7: Manueller Browser-Nachtest**

Dev-Server starten (falls nicht bereits über Docker laufend, siehe `docs/STATE.md` für den lokalen Docker-Weg) und im Browser:

1. Review-Queue öffnen, Button „🕓 Älteste zuerst" muss sichtbar sein (Standard-Zustand).
2. Klick auf den Button → Label wechselt zu „🕓 Neueste zuerst", Liste dreht sich um (neuestes Dokument/Gruppe zuerst).
3. Seite neu laden (F5) → Zustand „Neueste zuerst" bleibt erhalten (aus `localStorage`).
4. Erneuter Klick → zurück zu „Älteste zuerst", Liste wieder in Original-Reihenfolge.
5. Zum Papierkorb-Tab wechseln → Sortier-Button ist nicht sichtbar.
6. Ein Dokument mit E-Mail-Anhang (Gruppe mit `kinder`) in beiden Sortierrichtungen prüfen: Kind-Dokument bleibt unter seinem Eltern-Eintrag eingerückt, wandert nicht einzeln.

- [ ] **Step 8: Commit**

```bash
git add "Documents/Projekt/Version 1.00/unfallakten/frontend/src/views/ReviewQueueView.jsx"
git commit -m "feat(review-queue): Sortier-Toggle Eingangsdatum auf/ab mit localStorage-Persistenz"
```

---

## Self-Review

**Spec-Abdeckung:**
- Entscheidung 1 (nur Sortier-Toggle, keine weiteren Filter) → Task 2 fügt ausschließlich den einen Toggle hinzu, kein Filter-UI. ✓
- Entscheidung 2 (clientseitig, kein Backend-Eingriff) → keine Task berührt `intake_routes.py` oder andere Backend-Dateien. ✓
- Entscheidung 3 (Gruppen-Ebene sortieren) → `sortiereGruppen` arbeitet auf dem Ergebnis von `gruppiereQueue()`, sortiert also Gruppen, nicht einzelne Kind-Einträge; Step 7.6 verifiziert das manuell. ✓
- Entscheidung 4 (Persistenz via localStorage) → Task 2 Step 1 (Lesen) + Step 2 (Schreiben), Step 7.3 verifiziert. ✓
- Entscheidung 5 (Toggle nur in Queue-Ansicht) → Task 2 Step 5 rendert den Button in `{ansicht === "queue" && (...)}`, Step 7.5 verifiziert. ✓
- UI-Label-Vorgabe („🕓 Älteste zuerst" / „🕓 Neueste zuerst") → Task 2 Step 5 exakt übernommen. ✓
- Tests (Spec-Abschnitt „Tests") → Unit-Test Task 1, manueller Browser-Nachtest Task 2 Step 7. ✓

**Platzhalter-Scan:** Keine TBD/TODO, kein „ähnlich wie", jeder Code-Block vollständig ausgeschrieben.

**Typ-Konsistenz:** `sortiereGruppen(gruppen, absteigend)` wird in Task 1 definiert und in Task 2 Step 3 exakt mit diesen Parameternamen/dieser Reihenfolge aufgerufen (`sortiereGruppen(gruppiereQueue(queue), sortAbsteigend)`). Kein Namens-Drift.
