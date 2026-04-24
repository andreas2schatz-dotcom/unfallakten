# Übersicht-Redesign: Kollabierbare Beteiligten + Wiedervorlagen in To-Do Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alle Beteiligten-Kacheln im Übersicht-Tab ausklappbar machen und fällige Wiedervorlagen zur aktuellen Akte in der To-Do-Kachel anzeigen.

**Architecture:** Backend erhält einen `az`-Filter-Parameter in `hole_faellige_wiedervorlagen()`. Im Frontend werden `BeteiligterKachel` um Collapse-Logik erweitert (localStorage-Persistenz) und `TodoKachelKompakt` zu einer zweispaltigen Kachel mit Wiedervorlagen-Spalte umgebaut.

**Tech Stack:** Flask (Python 3.9), React 18, SQLite + SQL Server (RA-MICRO read-only via pymssql)

---

## Dateien-Übersicht

| Datei | Änderung |
|---|---|
| `backend/ramicro/wiedervorlage_service.py` | `hole_faellige_wiedervorlagen()` + `aktenzeichen`-Parameter + SQL-Filter |
| `backend/routers/wiedervorlage_routes.py` | `liste_wiedervorlagen()` liest neuen `az` Query-Parameter |
| `frontend/src/sections/UebersichtSection.jsx` | `BeteiligterKachel` Collapse-Props, `RaMicroAkteUebersicht` verkabelt, `TodoKachelKompakt` zweispaltig |

---

## Task 1: Backend – `hole_faellige_wiedervorlagen()` Aktenzeichen-Filter

**Files:**
- Modify: `backend/ramicro/wiedervorlage_service.py:93-223`

- [ ] **Step 1: Funktion-Signatur erweitern**

In `backend/ramicro/wiedervorlage_service.py` die Funktion `hole_faellige_wiedervorlagen` ab Zeile 93 wie folgt ändern — neuer Parameter `aktenzeichen=None` am Ende der Signatur:

```python
def hole_faellige_wiedervorlagen(
    nur_heute: bool = False,
    sachbearbeiter: Optional[str] = None,
    limit: int = 200,
    nur_stellungnahme: bool = True,
    grund_filter: Optional[str] = None,
    aktenzeichen: Optional[str] = None,
) -> list[dict]:
```

- [ ] **Step 2: SQL-Filter-Variable hinzufügen**

Direkt nach der Zeile `sb_filter = "AND w.sWiedervorlageSachbearbeiter = ..." if sachbearbeiter else ""` (Zeile ~118) einfügen:

```python
az_filter = "AND a.sAktenNummer = %(az)s" if aktenzeichen else ""
```

- [ ] **Step 3: SQL-Template um `AZ_FILTER` ergänzen**

In der SQL-String-Definition die `WHERE`-Klausel (Zeile ~198) wie folgt ändern:

```sql
        WHERE DATUM_FILTER
          GRUND_FILTER
          SB_FILTER
          AZ_FILTER
          AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
```

Und die `.replace()`-Kette am Ende der SQL-Definition (Zeile ~204) um den neuen Eintrag verlängern:

```python
    """.replace("DATUM_FILTER", datum_filter) \
       .replace("GRUND_FILTER", grund_sql) \
       .replace("SB_FILTER", sb_filter) \
       .replace("AZ_FILTER", az_filter)
```

- [ ] **Step 4: `az` in params-Dict eintragen**

Im `params`-Dict (Zeile ~208) nach dem `sachbearbeiter`-Block einfügen:

```python
    if aktenzeichen:
        params["az"] = aktenzeichen
```

- [ ] **Step 5: Manuell testen**

Im Backend-Container (oder lokal):
```bash
python -c "
from backend.ramicro.wiedervorlage_service import hole_faellige_wiedervorlagen
r = hole_faellige_wiedervorlagen(aktenzeichen='285/26TB', nur_stellungnahme=False)
print(len(r), 'WV gefunden')
for w in r: print(w.get('sAktenNummer'), w.get('sWiedervorlagegrund'))
"
```
Erwartetes Ergebnis: Liste (ggf. leer) ohne Exception. Nur Einträge mit `sAktenNummer = '285/26TB'`.

- [ ] **Step 6: Commit**

```bash
git add backend/ramicro/wiedervorlage_service.py
git commit -m "feat(wv): hole_faellige_wiedervorlagen – aktenzeichen-Filter"
```

---

## Task 2: Backend – Route `az` Query-Parameter

**Files:**
- Modify: `backend/routers/wiedervorlage_routes.py:149-167`

- [ ] **Step 1: Query-Parameter auslesen**

In `liste_wiedervorlagen()` (nach den bestehenden `request.args.get()`-Aufrufen, ca. Zeile 155) einfügen:

```python
    az = request.args.get("az") or None
```

- [ ] **Step 2: Parameter an Service weitergeben**

Den `hole_faellige_wiedervorlagen()`-Aufruf (Zeile ~159) um `aktenzeichen=az` ergänzen:

```python
        rows = hole_faellige_wiedervorlagen(
            nur_heute=nur_heute,
            sachbearbeiter=sb,
            limit=limit,
            nur_stellungnahme=not alle_gruende,
            grund_filter=grund_filter,
            aktenzeichen=az,
        )
```

- [ ] **Step 3: Manuell testen**

```bash
curl -s -H "Authorization: Bearer <token>" \
  "http://localhost:5000/wiedervorlage/?az=285/26TB&alle_gruende=true" \
  | python -m json.tool | head -40
```
Erwartetes Ergebnis: JSON mit `"anzahl": N` und `"wiedervorlagen": [...]`, alle Einträge haben `"aktenzeichen": "285/26TB"`.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/wiedervorlage_routes.py
git commit -m "feat(wv): /wiedervorlage/ Route – az Query-Parameter"
```

---

## Task 3: Frontend – `BeteiligterKachel` Collapse-Support

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx:80-309`

- [ ] **Step 1: Props erweitern und Collapse-State anlegen**

Die Funktionssignatur von `BeteiligterKachel` (Zeile 80) und den State-Bereich darunter ersetzen:

```jsx
function BeteiligterKachel({ titel, farbe, beteiligte, zeigeFirma=false, zeigeBetreff=false, zeigeAktenzeichen=false, nurEiner=false, akteId=null, ausklappbar=false, standardOffen=true, localStorageKey=null }) {
  const liste = nurEiner ? beteiligte.slice(0,1) : beteiligte;
  if (!liste.length) return null;

  const [offen, setOffen] = useState(() => {
    if (!ausklappbar) return true;
    if (localStorageKey) {
      const saved = localStorage.getItem(localStorageKey);
      if (saved !== null) return saved === "true";
    }
    return standardOffen;
  });

  const toggle = () => {
    const neu = !offen;
    setOffen(neu);
    if (localStorageKey) localStorage.setItem(localStorageKey, String(neu));
  };

  // IBAN-Check: nur für Mandantenkachel
  const [ibanCheck, setIbanCheck] = useState(null);
  // ... (restlicher bestehender Code bleibt unverändert)
```

**Wichtig:** Die bestehenden Zeilen für `ibanCheck`, `toast` und alle `useEffect`-Blöcke bleiben genau wie bisher — nur die ersten Zeilen der Funktion werden ersetzt.

- [ ] **Step 2: Header zu klickbarem Button machen (wenn `ausklappbar`)**

Den Header-Block (Zeile ~136, der `{titel && <div ...>}` Block) ersetzen:

```jsx
      {titel && (
        ausklappbar ? (
          <button
            onClick={toggle}
            style={{
              width:"100%", display:"flex", alignItems:"center", justifyContent:"space-between",
              background: farbe + "18", borderBottom: offen ? `1px solid ${farbe}33` : "none",
              padding:"8px 14px", cursor:"pointer", border:"none", textAlign:"left",
            }}>
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <div style={{ width:8, height:8, borderRadius:"50%", background:farbe, flexShrink:0 }} />
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", fontWeight:600, color:farbe, textTransform:"uppercase", letterSpacing:"0.08em" }}>{titel}</span>
              {liste.length > 1 && <span style={{ marginLeft:"auto", fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", color:T.textFaint }}>{liste.length} Einträge</span>}
            </div>
            <span style={{ fontSize:"0.9rem", color:farbe, transform: offen ? "rotate(180deg)" : "none", transition:"transform 0.2s", lineHeight:1 }}>⌄</span>
          </button>
        ) : (
          <div style={{ background: farbe + "18", borderBottom:`1px solid ${farbe}33`, padding:"8px 14px", display:"flex", alignItems:"center", gap:8 }}>
            <div style={{ width:8, height:8, borderRadius:"50%", background:farbe, flexShrink:0 }} />
            <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", fontWeight:600, color:farbe, textTransform:"uppercase", letterSpacing:"0.08em" }}>{titel}</span>
            {liste.length > 1 && <span style={{ marginLeft:"auto", fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", color:T.textFaint }}>{liste.length} Einträge</span>}
          </div>
        )
      )}
```

- [ ] **Step 3: Einträge-Body nur rendern wenn `offen`**

Die `{liste.map(...)}` Block-Zeile (~Zeile 143) mit einer Bedingung wrappen:

```jsx
      {(!ausklappbar || offen) && liste.map((b, i) => (
        // ... bestehender Eintrag-Code unverändert
      ))}
```

Das schließende `</div>` der äußeren Kachel-Box bleibt wo es ist.

- [ ] **Step 4: Im Browser prüfen**

Dev-Server starten, eine Akte öffnen, Tab "Übersicht". Die Beteiligten-Kacheln sehen noch genauso aus wie vorher (da `ausklappbar` default `false`). Kein visueller Unterschied erwartet.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(ui): BeteiligterKachel – ausklappbar prop + localStorage"
```

---

## Task 4: Frontend – Alle Beteiligten-Kacheln verkabeln

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx:400-445` (innerhalb `RaMicroAkteUebersicht`)

- [ ] **Step 1: Mandant-Kachel ausklappbar machen**

Den `BeteiligterKachel`-Aufruf für Mandant (ca. Zeile 407) erweitern:

```jsx
<BeteiligterKachel
  titel="Mandant" farbe={T.navy}
  beteiligte={b.mandant} nurEiner
  zeigeBetreff zeigeAktenzeichen={false}
  akteId={azRoh}
  ausklappbar={true}
  localStorageKey={`uebersicht-kachel-mandant-${azRoh}`}
/>
```

- [ ] **Step 2: Gegner-Kachel ausklappbar machen**

Den `BeteiligterKachel`-Aufruf für Gegner (ca. Zeile 432) erweitern:

```jsx
<BeteiligterKachel
  titel="Gegner" farbe={T.red}
  beteiligte={b.gegner}
  zeigeBetreff zeigeAktenzeichen={false}
  ausklappbar={true}
  localStorageKey={`uebersicht-kachel-gegner-${azRoh}`}
/>
```

- [ ] **Step 3: Behörden-Kachel ausklappbar machen**

Den `BeteiligterKachel`-Aufruf für Behörden (ca. Zeile 439) erweitern:

```jsx
<BeteiligterKachel
  titel="Behörden / Gerichte" farbe={T.amber}
  beteiligte={b.behoerde}
  zeigeAktenzeichen zeigeBetreff={false}
  ausklappbar={true}
  localStorageKey={`uebersicht-kachel-behoerde-${azRoh}`}
/>
```

- [ ] **Step 4: Weitere Beteiligte ausklappbar machen**

Den `BeteiligterKachel`-Aufruf für Weitere (ca. Zeile 418) erweitern:

```jsx
<BeteiligterKachel
  titel="Weitere Beteiligte" farbe={T.textMuted}
  beteiligte={b.weitere}
  zeigeFirma zeigeBetreff
  ausklappbar={true}
  localStorageKey={`uebersicht-kachel-weitere-${azRoh}`}
/>
```

- [ ] **Step 5: Im Browser testen**

Eine Akte öffnen → Übersicht-Tab. Alle vier Beteiligten-Kacheln zeigen jetzt einen `⌄`-Pfeil im Header. Klick klappt zu. Seite neu laden → Zustand bleibt (localStorage). Pfeil dreht sich beim Auf-/Zuklappen.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(ui): RaMicroAkteUebersicht – alle Beteiligten ausklappbar (localStorage)"
```

---

## Task 5: Frontend – `TodoKachelKompakt` zweispaltig mit Wiedervorlagen

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx:1399-1493` (`TodoKachelKompakt`)
- Modify: `frontend/src/sections/UebersichtSection.jsx:1737-1739` (Aufruf in `UebersichtSection`)

- [ ] **Step 1: Prop `azRoh` zum Aufruf hinzufügen**

In `UebersichtSection` (ca. Zeile 1738) den `TodoKachelKompakt`-Aufruf erweitern:

```jsx
<TodoKachelKompakt az={akte.az} akteId={akte.id} azRoh={akte.az_roh || akte.az} />
```

- [ ] **Step 2: Komponente komplett ersetzen**

Die gesamte `TodoKachelKompakt`-Funktion (Zeilen 1399–1493) durch die folgende neue Version ersetzen:

```jsx
function TodoKachelKompakt({ az, akteId, azRoh }) {
  const [todos, setTodos]   = useState([]);
  const [wvListe, setWvListe] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const todoCall = apiTodos.liste(az).catch(() => ({ todos: [] }));
    const wvCall = azRoh && azRoh.includes("/")
      ? request(`/wiedervorlage/?az=${encodeURIComponent(azRoh)}&alle_gruende=true&limit=10`)
          .then(r => r?.wiedervorlagen || [])
          .catch(() => [])
      : Promise.resolve([]);

    Promise.all([todoCall, wvCall])
      .then(([todoRes, wvRes]) => {
        setTodos(todoRes?.todos || []);
        setWvListe(wvRes);
      })
      .finally(() => setLoading(false));
  }, [az, azRoh]);

  const offen = todos.filter(t => !t.erledigt);

  const FARBEN = {
    rot:    { dot: T.red },
    orange: { dot: "#f97316" },
    gelb:   { dot: "#eab308" },
    grau:   { dot: T.textFaint },
  };

  const dringlichkeit = (todo) => {
    const heute = new Date(); heute.setHours(0,0,0,0);
    if (todo.faellig_am) {
      const frist = new Date(todo.faellig_am); frist.setHours(0,0,0,0);
      const tage = Math.round((frist - heute) / 86400000);
      const s = tage < 0 ? "rot" : tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
      return todo.frist_typ === "verjaehrung"
        ? ({rot:"rot",orange:"rot",gelb:"orange",grau:"gelb"}[s] || s) : s;
    }
    const alter = Math.round((heute - new Date(todo.erstellt_am)) / 86400000);
    return alter >= 15 ? "rot" : alter >= 8 ? "orange" : alter >= 4 ? "gelb" : "grau";
  };

  const fmtWvDatum = (iso) => {
    if (!iso) return "";
    try { const [y,m,d] = iso.split("-"); return `${d}.${m}.${y}`; } catch { return iso; }
  };

  if (loading) return null;

  const hatWv = wvListe.length > 0;

  return (
    <Card style={ offen.length > 0 ? { border:`1.5px solid ${T.accentTrim}`, background:T.accentPale } : {} }>
      {/* Header */}
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"0.85rem 1.4rem 0.5rem", flexWrap:"wrap", gap:8 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMid, textTransform:"uppercase", letterSpacing:"0.08em" }}>
            📋 To-Dos
          </span>
          {offen.length > 0 && (
            <span style={{ background:T.redBg, color:T.red, borderRadius:10, padding:"1px 7px", fontSize:"0.78rem", fontWeight:600 }}>
              {offen.length} offen
            </span>
          )}
        </div>
        {hatWv && (
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMid, textTransform:"uppercase", letterSpacing:"0.08em" }}>
              📅 Wiedervorlagen
            </span>
            <span style={{ background:"#fef9c3", color:"#92400e", borderRadius:10, padding:"1px 7px", fontSize:"0.78rem", fontWeight:600 }}>
              {wvListe.length} fällig
            </span>
          </div>
        )}
      </div>

      {/* Body */}
      <div style={{ display:"grid", gridTemplateColumns: hatWv ? "1fr 1px 1fr" : "1fr", padding:"0 1.4rem 0.85rem", gap:0 }}>

        {/* To-Do-Spalte */}
        <div style={{ paddingRight: hatWv ? 12 : 0 }}>
          {offen.length === 0 ? (
            <div style={{ fontSize:"0.875rem", color:T.textFaint, fontFamily:"'Figtree',sans-serif" }}>
              ✅ Alle To-Dos erledigt
            </div>
          ) : (
            offen.slice(0, 4).map(todo => {
              const d = dringlichkeit(todo);
              const f = FARBEN[d];
              return (
                <div key={todo.id} style={{ display:"flex", alignItems:"center", gap:8, padding:"5px 0", borderBottom:`1px solid ${T.borderSoft}` }}>
                  <span style={{ width:8, height:8, borderRadius:"50%", background:f.dot, flexShrink:0, display:"inline-block" }} />
                  <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.text, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                    {todo.text}
                  </span>
                  {todo.faellig_am && (
                    <span style={{ fontSize:"0.75rem", color:T.textFaint, fontFamily:"ui-monospace,monospace", flexShrink:0 }}>
                      {(() => { try { const [y,m,d]=todo.faellig_am.split("-"); return `${d}.${m}.`; } catch{return "";} })()}
                    </span>
                  )}
                </div>
              );
            })
          )}
          {offen.length > 4 && (
            <div style={{ fontSize:"0.8rem", color:T.textFaint, marginTop:5, fontFamily:"'Figtree',sans-serif" }}>
              + {offen.length - 4} weitere …
            </div>
          )}
        </div>

        {/* Trennlinie */}
        {hatWv && <div style={{ background:T.border, margin:"0 0" }} />}

        {/* Wiedervorlage-Spalte */}
        {hatWv && (
          <div style={{ paddingLeft:12, display:"flex", flexDirection:"column", gap:6 }}>
            {wvListe.slice(0, 3).map((wv, i) => (
              <div key={i} style={{ background:"#fef9c3", border:"1px solid #fde047", borderRadius:6, padding:"6px 10px" }}>
                <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem", fontWeight:700, color:"#78350f", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                  {wv.grund || "Wiedervorlage"}
                </div>
                <div style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.75rem", color:"#92400e", marginTop:2 }}>
                  fällig: {fmtWvDatum(wv.datum)}
                </div>
              </div>
            ))}
            {wvListe.length > 3 && (
              <div style={{ fontSize:"0.78rem", color:T.textFaint, fontFamily:"'Figtree',sans-serif" }}>
                + {wvListe.length - 3} weitere → WVL-Tab
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Im Browser testen – ohne RA-Micro-Verbindung**

Eine Akte öffnen → Übersicht-Tab. Wenn kein `az_roh` mit `/` vorhanden oder RA-Micro nicht erreichbar: Kachel zeigt nur die To-Do-Spalte (einspaltig), kein Fehler, kein Ladeindikator. Todos erscheinen wie bisher.

- [ ] **Step 4: Im Browser testen – mit RA-Micro-Verbindung**

Eine Akte mit gültigem Aktenzeichen (z. B. `285/26`) öffnen. Wenn Wiedervorlagen vorhanden: rechte Spalte erscheint mit gelben WV-Kacheln, Header zeigt `📅 Wiedervorlagen [N fällig]`. Wenn keine WV: nur linke Spalte (einspaltig), kein WV-Header.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(ui): TodoKachelKompakt – zweispaltig mit Wiedervorlagen je Akte"
```

---

## Selbst-Review Checkliste

- **Kollabierbare Beteiligten:** Task 3 + Task 4 ✅
- **localStorage-Persistenz:** Task 3, Step 1 (`standardOffen` + `localStorageKey`) ✅
- **WV-Backend-Filter:** Task 1 + Task 2 ✅
- **WV im Frontend:** Task 5 ✅
- **Silent fail bei fehlender RA-Micro-Verbindung:** Task 5, Step 2 (`.catch(() => [])`) ✅
- **Max. 3 WV angezeigt, Link zum WVL-Tab:** Task 5, Step 2 (`wvListe.slice(0,3)` + "+ N weitere → WVL-Tab") ✅
- **Nicht im Scope (globaler WVL-Tab, TodoSection, RechtsschutzKlappkachel):** nicht angefasst ✅
