# Design: US-05 · E-Akte Hover-Vorschau im Dashboard

**Datum:** 2026-06-13  
**Status:** Genehmigt  
**Aufwand:** S  
**Priorität:** P1

---

## Ziel

In `AktensucheView` zeigt ein Hover über eine Akten-Zeile einen Popover mit den letzten 3–5 E-Akte-Dokumenten der Akte. Klick auf ein Dokument öffnet die Akte direkt im Dokumente-Tab.

---

## Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `frontend/src/views/AktensucheView.jsx` | Hauptänderung: Hover-Logik + Popover-Komponente |
| `frontend/src/App.jsx` | Minimale Erweiterung: `pendingAkteTab`-State, `openAkte` + `initialTab` |
| `frontend/src/components/AkteDetailView.jsx` | Minimale Erweiterung: Props `initialTab` + `onTabMounted` |

Kein neues Backend — bestehender Endpoint `GET /akten/<az>/eakte` reicht.

---

## Architektur

### AktensucheView.jsx

#### Neuer State

```js
const [hoverAz, setHoverAz]       = useState(null);      // az der gehover­ten Zeile
const [hoverAnchor, setHoverAnchor] = useState(null);    // DOMRect der Zeile
const [popoverDaten, setPopover]  = useState({ docs: [], loading: false, error: null });
```

#### Neue Refs

```js
const timerRef = useRef(null);   // 300 ms Delay-Timer
const hideTimerRef = useRef(null); // 150 ms Hide-Timer (Mouse-Transfer)
const cacheRef = useRef(new Map()); // Map<az, doc[]>
```

#### Hover-Logik pro Tabellenzeile

**`onMouseEnter(e, treffer)`:**
1. `hoverAnchor` = `e.currentTarget.getBoundingClientRect()`
2. `hoverAz` = `treffer.az_roh`
3. Laufenden Hide-Timer abbrechen
4. Wenn Cache-Hit: `popoverDaten` direkt setzen, kein Fetch
5. Sonst: 300 ms Timer → `eakte.liste(az)` → ersten 5 Einträge → Cache setzen → `popoverDaten` setzen

**`onMouseLeave`:**
1. Laufenden Fetch-Timer abbrechen
2. 150 ms Hide-Timer starten → dann `hoverAz = null`

#### Popover: Mouse-Transfer

- `onMouseEnter` des Popovers: laufenden Hide-Timer abbrechen (Maus ist jetzt auf dem Popover)
- `onMouseLeave` des Popovers: `hoverAz = null` sofort

---

### EakteHoverPopover-Komponente (in AktensucheView.jsx)

**Props:** `az`, `anchor`, `daten`, `onOpenAkte`, `onMouseEnter`, `onMouseLeave`

**Positionierung:** `position: fixed`, rechtsbündig zur Tabelle  
- Standard: `bottom = window.innerHeight - anchor.top` (Popover über der Zeile)  
- Falls Popover oben abgeschnitten würde (`anchor.top < popoverHeight + 20`): `top = anchor.bottom` (darunter)  
- `right = window.innerWidth - anchor.right`

**Inhalt:**

| Zustand | Anzeige |
|---|---|
| `loading: true` | Spinner-Zeile |
| `docs.length === 0` | „Keine E-Akte-Dokumente vorhanden" (grau) |
| `error` | Fehlermeldung (grau, kein Toast) |
| Normal | 3–5 Dokument-Karten + Footer-Link |

**Dokument-Karte:** farbiges Typ-Badge + Datum + Dateiname (ellipsis)  
**Footer:** „Alle Dokumente anzeigen →"  
**Klick auf Karte oder Footer:** `onOpenAkte({ ...akteObj, initialTab: "dokumente" })`

#### Typ-Badge-Zuordnung (aus `bemerkung`-Feld / Dateiname)

| Schlüsselwort | Label | Farbe |
|---|---|---|
| `regulier` / `schreiben` | Regulierung | Blau (#dbeafe / #1e40af) |
| `gutachten` | Gutachten | Grün (#d1fae5 / #065f46) |
| `polizei` / `bericht` | Polizei | Gelb (#fef3c7 / #92400e) |
| sonst | Dokument | Grau (#f3f4f6 / #6b7280) |

---

### App.jsx

```js
const [pendingAkteTab, setPendingAkteTab] = useState(null); // { tabId, sec } | null
```

`openAkte` extrahiert `initialTab` aus dem Akte-Objekt (keine Signatur-Änderung nötig):

```js
const openAkte = useCallback((baseAkte) => {
  const { initialTab, ...akteData } = baseAkte;
  // ... bestehende Logik mit akteData statt baseAkte ...
  if (initialTab) setPendingAkteTab({ tabId, sec: initialTab });
}, [aktenState]);
```

`AkteDetailView` erhält neue Props:

```jsx
<AkteDetailView
  akte={activeTab.akte}
  st={...}
  dispatch={dispatch}
  initialTab={pendingAkteTab?.tabId === active ? pendingAkteTab.sec : null}
  onTabMounted={() => setPendingAkteTab(null)}
/>
```

---

### AkteDetailView.jsx

```js
function AkteDetailView({ akte, st, dispatch, initialTab, onTabMounted }) {
  const [sec, setSec] = useState("uebersicht");

  useEffect(() => {
    if (initialTab) {
      setSec(initialTab);
      onTabMounted?.();
    }
  }, [initialTab]);
  // ...
}
```

---

## Fehlerbehandlung

- API-Fehler beim E-Akte-Fetch: `error`-State im Popover, grau dargestellt, kein Toast
- Timeout: kein explizites Timeout — bei langsamer Verbindung bleibt Spinner (Popover ist informell)
- Akte ohne E-Akte-Dokumente: Leer-Zustand im Popover

---

## Was nicht gebaut wird

- Keine Vorschau des PDF-Inhalts (nur Metadaten der Dokumente)
- Kein Keyboard-Trigger (nur Hover)
- Kein Prefetch beim Laden der Suchergebnisse
