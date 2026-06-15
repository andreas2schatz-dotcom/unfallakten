# US-05 · E-Akte Hover-Vorschau — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hover über eine Akten-Zeile in `AktensucheView` zeigt einen Popover mit den letzten 5 E-Akte-Dokumenten; Klick öffnet die Akte direkt im Dokumente-Tab.

**Architecture:** Drei Dateien, kein Backend. `App.jsx` + `AkteDetailView.jsx` bekommen eine `initialTab`-Kette (exakt wie das bestehende `pendingEinstellungenTab`-Muster). `AktensucheView.jsx` bekommt eine neue Komponente `EakteHoverPopover` (position:fixed) und die zugehörige Hover-Logik mit 300 ms Delay und In-Memory-Cache.

**Tech Stack:** React 18, bestehende `eakte.liste(az)` API (`GET /akten/<az>/eakte`), kein neues Backend

---

## Dateien

| Datei | Änderung |
|---|---|
| `frontend/src/App.jsx` | `pendingAkteTab`-State, `openAkte` extrahiert `initialTab`, Props an `AkteDetailView` |
| `frontend/src/components/AkteDetailView.jsx` | Props `initialTab` + `onTabMounted`, `useEffect` zum Tab-Wechsel |
| `frontend/src/views/AktensucheView.jsx` | Import `eakte`, Hilfsfunktionen `typBadge`/`fmtDatum`, Komponente `EakteHoverPopover`, Hover-State + Refs + Handler in Hauptkomponente |

---

## Task 1: `initialTab`-Kette in `App.jsx` + `AkteDetailView.jsx`

**Files:**
- Modify: `frontend/src/App.jsx:98-103` (State), `App.jsx:118-134` (openAkte), `App.jsx:287` (JSX)
- Modify: `frontend/src/components/AkteDetailView.jsx:34-35` (Signatur + useEffect)

- [ ] **Schritt 1: `pendingAkteTab`-State in `App.jsx` hinzufügen**

  Direkt nach Zeile 102 (`pendingEinstellungenTab`):

  ```js
  const [pendingEinstellungenTab, setPendingEinstellungenTab] = useState(null);
  const [pendingAkteTab, setPendingAkteTab] = useState(null);
  ```

- [ ] **Schritt 2: `openAkte` in `App.jsx` erweitern**

  Zeile 118–134 komplett ersetzen:

  ```js
  const openAkte = useCallback((baseAkte) => {
    const { initialTab, ...akteData } = baseAkte;
    const azVoll  = akteData.az_roh || akteData.az || String(akteData.id);
    const azBasis = azVoll.replace(/[A-Z]{2,3}$/i, "").trim();
    const az      = azBasis.includes("/") ? azBasis : azVoll;
    const tabId   = `akte-${az}`;
    setTabs(prev => prev.find(t => t.id===tabId) ? prev : [
      ...prev,
      { id:tabId, label:azVoll, status:aktenState[az]?.status||akteData.status||"offen",
        akte:{ ...akteData, id:az, az:azVoll, az_roh:az } }
    ]);
    setActive(tabId);
    if (initialTab) setPendingAkteTab({ tabId, sec: initialTab });
    if (az.includes("/")) {
      ramicroListe.onDemand(az).catch(() => {});
    }
  }, [aktenState]);
  ```

- [ ] **Schritt 3: `AkteDetailView`-JSX in `App.jsx` erweitern**

  Zeile 287, `AkteDetailView`-Zeile ersetzen:

  ```jsx
  : activeTab?.akte ? <AkteDetailView
      akte={activeTab.akte}
      st={aktenState[activeTab.akte.id]||{}}
      dispatch={dispatch}
      initialTab={pendingAkteTab?.tabId === active ? pendingAkteTab.sec : null}
      onTabMounted={() => setPendingAkteTab(null)}
    />
  ```

- [ ] **Schritt 4: `AkteDetailView.jsx` — Signatur + useEffect**

  Zeile 34–35 anpassen:

  ```js
  function AkteDetailView({ akte, st, dispatch, initialTab, onTabMounted }) {
    const [sec, setSec] = useState("uebersicht");

    useEffect(() => {
      if (initialTab) {
        setSec(initialTab);
        onTabMounted?.();
      }
    }, [initialTab]);
  ```

- [ ] **Schritt 5: Manuell testen**

  Dev-Server starten (falls noch nicht läuft): `cd frontend && npm run dev`

  Ablauf:
  1. Aktensuche öffnen, nach einer Akte suchen
  2. Auf „Öffnen" klicken — Akte öffnet sich in Tab, Standard-Tab „Übersicht" erscheint ✓
  3. Zurück zur Aktensuche, zweite Akte öffnen — funktioniert weiterhin ✓
  4. (Popover-Klick wird in Task 3 getestet)

- [ ] **Schritt 6: Commit**

  ```bash
  git add frontend/src/App.jsx frontend/src/components/AkteDetailView.jsx
  git commit -m "feat(us05): initialTab-Kette App.jsx + AkteDetailView"
  ```

---

## Task 2: Hilfsfunktionen + `EakteHoverPopover`-Komponente in `AktensucheView.jsx`

**Files:**
- Modify: `frontend/src/views/AktensucheView.jsx:1-11` (Import), vor `AutocompleteInput` (Hilfsfunktionen + Komponente)

- [ ] **Schritt 1: `eakte`-Import ergänzen**

  Zeile 8–10 in `AktensucheView.jsx`:

  ```js
  import {
    aktensuche as apiAktensuche,
    emailImport,
    akten as apiAkten,
    eakte as apiEakte,
  } from "../api.js";
  ```

- [ ] **Schritt 2: Hilfsfunktionen einfügen**

  Direkt nach den Importen, vor `// ── Autocomplete-Input`, einfügen:

  ```js
  // ── E-Akte Hover-Vorschau: Hilfsfunktionen ──────────────────────────────────

  function typBadge(dok) {
    const text = ((dok.bemerkung || "") + " " + (dok.anzeigename || "")).toLowerCase();
    if (/regulier|schreiben|zahlung|deckung/.test(text))
      return { label: "Regulierung", bg: "#dbeafe", color: "#1e40af" };
    if (/gutachten|sachverst/.test(text))
      return { label: "Gutachten",   bg: "#d1fae5", color: "#065f46" };
    if (/polizei|bericht|anzeige/.test(text))
      return { label: "Polizei",     bg: "#fef3c7", color: "#92400e" };
    if (/rechnung|kosten|invoice/.test(text))
      return { label: "Rechnung",    bg: "#fce7f3", color: "#9d174d" };
    return { label: "Dokument", bg: "#f3f4f6", color: "#6b7280" };
  }

  function fmtDatum(isoStr) {
    if (!isoStr) return "–";
    const d = new Date(isoStr);
    return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  }
  ```

- [ ] **Schritt 3: `EakteHoverPopover`-Komponente einfügen**

  Direkt nach den Hilfsfunktionen, vor `// ── Autocomplete-Input`:

  ```jsx
  // ── EakteHoverPopover ────────────────────────────────────────────────────────

  function EakteHoverPopover({ az, anchor, daten, akteObj, onOpenAkte, onMouseEnter, onMouseLeave }) {
    const BREITE = 320;
    const HOEHE_GESCHAETZT = 260;
    const ueberZeile = anchor.top > HOEHE_GESCHAETZT + 20;
    const top   = ueberZeile ? anchor.top - HOEHE_GESCHAETZT : anchor.bottom + 4;
    const right = Math.max(8, window.innerWidth - anchor.right);

    const oeffnen = () => onOpenAkte({ ...akteObj, initialTab: "dokumente" });

    return (
      <div
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        style={{
          position: "fixed", top, right,
          width: BREITE, background: T.white,
          border: `1px solid ${T.border}`, borderRadius: 10,
          boxShadow: "0 6px 24px rgba(0,0,0,0.16)", zIndex: 500, overflow: "hidden",
        }}
      >
        {/* Header */}
        <div style={{
          padding: "8px 14px", background: T.navy,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "white",
            letterSpacing: "0.06em", textTransform: "uppercase",
            fontFamily: "'Figtree',sans-serif" }}>
            E-Akte Vorschau
          </span>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.5)",
            fontFamily: "ui-monospace,monospace" }}>
            {az}
          </span>
        </div>

        {/* Body */}
        {daten.loading ? (
          <div style={{ padding: "14px", textAlign: "center",
            color: T.textFaint, fontFamily: "'Figtree',sans-serif", fontSize: 13 }}>
            Lädt …
          </div>
        ) : daten.error ? (
          <div style={{ padding: "12px 14px",
            color: T.textMuted, fontFamily: "'Figtree',sans-serif", fontSize: 13 }}>
            {daten.error}
          </div>
        ) : daten.docs.length === 0 ? (
          <div style={{ padding: "12px 14px",
            color: T.textMuted, fontFamily: "'Figtree',sans-serif", fontSize: 13 }}>
            Keine E-Akte-Dokumente vorhanden.
          </div>
        ) : (
          <div style={{ padding: "6px 8px", display: "flex", flexDirection: "column", gap: 4 }}>
            {daten.docs.map(dok => {
              const badge = typBadge(dok);
              const datum = fmtDatum(dok.version || dok.einf_datum);
              return (
                <div key={dok.nr} onClick={oeffnen}
                  style={{
                    padding: "7px 9px", border: `1px solid ${T.borderSoft}`,
                    borderRadius: 6, display: "flex", alignItems: "flex-start",
                    gap: 8, cursor: "pointer", background: T.white,
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = T.accentPale}
                  onMouseLeave={e => e.currentTarget.style.background = T.white}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
                      <span style={{
                        fontSize: 10, fontWeight: 700,
                        background: badge.bg, color: badge.color,
                        borderRadius: 3, padding: "1px 5px",
                        textTransform: "uppercase", letterSpacing: "0.04em",
                        whiteSpace: "nowrap", fontFamily: "'Figtree',sans-serif",
                      }}>
                        {badge.label}
                      </span>
                      <span style={{ fontSize: 10, color: T.textFaint,
                        fontFamily: "'Figtree',sans-serif" }}>
                        {datum}
                      </span>
                    </div>
                    <div style={{
                      fontSize: 12, color: T.textMid, fontWeight: 500,
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                      fontFamily: "'Figtree',sans-serif",
                    }}>
                      {dok.anzeigename || dok.dateiname}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Footer */}
        {!daten.loading && !daten.error && (
          <div style={{
            padding: "7px 14px", background: "#fafaf8",
            borderTop: `1px solid ${T.borderSoft}`, textAlign: "center",
          }}>
            <button onClick={oeffnen}
              style={{
                background: "none", border: "none", cursor: "pointer",
                fontSize: 11, color: T.accent, fontWeight: 600,
                fontFamily: "'Figtree',sans-serif",
              }}>
              Alle Dokumente anzeigen →
            </button>
          </div>
        )}
      </div>
    );
  }
  ```

- [ ] **Schritt 4: Commit**

  ```bash
  git add frontend/src/views/AktensucheView.jsx
  git commit -m "feat(us05): EakteHoverPopover-Komponente + typBadge/fmtDatum"
  ```

---

## Task 3: Hover-State + Logik in `AktensucheView` + Tabellenzeilen verbinden

**Files:**
- Modify: `frontend/src/views/AktensucheView.jsx` (Hauptkomponente `AktensucheView`)

- [ ] **Schritt 1: State + Refs hinzufügen**

  In `AktensucheView` direkt nach den bestehenden `useState`-Deklarationen (nach Zeile 272 `const [toast, setToast] = useState("")`):

  ```js
  const [hoverAz,      setHoverAz]      = useState(null);
  const [hoverAnchor,  setHoverAnchor]  = useState(null);
  const [hoverAkteObj, setHoverAkteObj] = useState(null);
  const [popoverDaten, setPopover]      = useState({ docs: [], loading: false, error: null });
  const timerRef    = useRef(null);
  const hideTimerRef = useRef(null);
  const cacheRef    = useRef(new Map());
  ```

  Außerdem sicherstellen, dass `useRef` im React-Import oben steht:
  ```js
  import React, { useState, useRef, useEffect } from "react";
  ```
  (bereits vorhanden, kein Änderungsbedarf)

- [ ] **Schritt 2: Handler-Funktionen hinzufügen**

  Direkt nach den Ref-Deklarationen, vor `const suchen = async ...`:

  ```js
  const handleRowEnter = (e, t) => {
    clearTimeout(hideTimerRef.current);
    const anchor = e.currentTarget.getBoundingClientRect();
    setHoverAnchor(anchor);
    setHoverAkteObj({
      id: t.az_roh, az: t.az, az_roh: t.az_roh,
      status: t.status || "offen", unfalldatum: t.unfalldatum || "",
      unfallort: t.unfallort || "", hq: t.haftungsquote || 100, brutto: 0,
    });
    if (hoverAz === t.az_roh) return;
    setHoverAz(t.az_roh);
    if (cacheRef.current.has(t.az_roh)) {
      setPopover({ docs: cacheRef.current.get(t.az_roh), loading: false, error: null });
      return;
    }
    setPopover({ docs: [], loading: true, error: null });
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      try {
        const res = await apiEakte.liste(t.az_roh);
        const docs = (res.dokumente || []).slice(0, 5);
        cacheRef.current.set(t.az_roh, docs);
        setPopover({ docs, loading: false, error: null });
      } catch {
        setPopover({ docs: [], loading: false, error: "Dokumente konnten nicht geladen werden." });
      }
    }, 300);
  };

  const handleRowLeave = () => {
    clearTimeout(timerRef.current);
    hideTimerRef.current = setTimeout(() => setHoverAz(null), 150);
  };
  ```

- [ ] **Schritt 3: Tabellenzeilen-Handler verdrahten**

  In der `<tbody>` — bestehende `<tr>`-Zeile (ca. Zeile 444–448) anpassen. **Achtung:** Die bestehenden `onMouseEnter`/`onMouseLeave` für das Zeilen-Highlighting bleiben erhalten — sie werden erweitert:

  ```jsx
  <tr key={t.az + i}
    style={{ borderBottom: `1px solid ${T.borderSoft}`, background: i % 2 === 0 ? T.white : "#fafaf8", transition: "background 0.12s", cursor: "default" }}
    onMouseEnter={e => { e.currentTarget.style.background = "#f6f4ef"; handleRowEnter(e, t); }}
    onMouseLeave={e => { e.currentTarget.style.background = i % 2 === 0 ? T.white : "#fafaf8"; handleRowLeave(); }}>
  ```

- [ ] **Schritt 4: Popover im JSX rendern**

  Am Ende des Fragment-Returns, direkt vor `{neueAkteOffen && <NeueAkteModal ...}` (ca. Zeile 504), einfügen:

  ```jsx
  {hoverAz && hoverAnchor && (
    <EakteHoverPopover
      az={hoverAz}
      anchor={hoverAnchor}
      daten={popoverDaten}
      akteObj={hoverAkteObj}
      onOpenAkte={onOpenAkte}
      onMouseEnter={() => clearTimeout(hideTimerRef.current)}
      onMouseLeave={() => setHoverAz(null)}
    />
  )}
  ```

- [ ] **Schritt 5: Manuell testen — Vollständiger End-to-End-Test**

  Dev-Server läuft unter `http://localhost:5173` (Vite-Default).

  **Szenario 1 — Popover erscheint:**
  1. Aktensuche öffnen, Suchergebnis laden (mind. 1 Treffer)
  2. Maus langsam über eine Trefferzeile bewegen und 300 ms halten
  3. Popover erscheint rechts oben/unten neben der Zeile ✓
  4. Header zeigt „E-AKTE VORSCHAU" + AZ ✓
  5. Dokument-Karten erscheinen mit farbigen Typ-Badges ✓

  **Szenario 2 — Kein Flackern:**
  1. Maus schnell über mehrere Zeilen bewegen (< 300 ms pro Zeile)
  2. Kein Popover erscheint während der schnellen Bewegung ✓

  **Szenario 3 — Mouse-Transfer:**
  1. Über Zeile hovern bis Popover erscheint
  2. Maus vom Tabellenzeile in den Popover bewegen
  3. Popover bleibt offen ✓
  4. Maus vom Popover weg → Popover verschwindet ✓

  **Szenario 4 — Klick öffnet Dokumente-Tab:**
  1. Popover öffnen
  2. Auf Dokument-Karte oder „Alle Dokumente anzeigen →" klicken
  3. Akte öffnet sich direkt im Tab „Dokumente" ✓
  4. Nochmal: Akte bereits geöffnet (anderer Tab), erneuter Klick im Popover → navigiert zur Akte UND wechselt zu Dokumente-Tab ✓

  **Szenario 5 — Akte ohne E-Akte:**
  1. Akte ohne E-Akte-Dokumente hovern
  2. Popover zeigt „Keine E-Akte-Dokumente vorhanden." ✓

  **Szenario 6 — Cache:**
  1. Dieselbe Zeile ein zweites Mal hovern
  2. Popover erscheint sofort (kein Spinner) ✓

- [ ] **Schritt 6: Commit**

  ```bash
  git add frontend/src/views/AktensucheView.jsx
  git commit -m "feat(us05): Hover-State + EakteHoverPopover in AktensucheView"
  ```

---

## Task 4: TODO.md aktualisieren

**Files:**
- Modify: `docs/TODO.md`

- [ ] **Schritt 1: US-05 als erledigt markieren**

  In `docs/TODO.md` — Zeile mit `**PRD-US05 — E-Akte Hover-Vorschau im Dashboard**` anpassen:

  ```markdown
  **~~PRD-US05 — E-Akte Hover-Vorschau im Dashboard~~** ✅ *(Session 2026-06-15)*
  ```

- [ ] **Schritt 2: Commit**

  ```bash
  git add docs/TODO.md
  git commit -m "docs: US-05 in TODO als erledigt markiert"
  ```
