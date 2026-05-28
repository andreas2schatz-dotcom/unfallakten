# Akten Action Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** UebersichtSection zu einem Action Board umbauen: Navy-Header mit AZ/Bezeichnung/Schnellaktionen, kompakte Status-Checks (Vollmacht/IBAN/RSV), Finanz-Band (Beträge statt Prozent), 2-Spalten-Body (Todos + WV), plus PWA-Nachricht-Stub und Navigation-Redesign.

**Architecture:** Alle neuen Komponenten entstehen als lokale Funktionen innerhalb `UebersichtSection.jsx` (bestehende Konvention). Die vorhandene KlappAbschnitt/KlappSektion-Struktur bleibt darunter erhalten. Das Backend bekommt einen neuen Stub-Endpunkt und eine Erweiterung des mandant-checks-Endpunkts.

**Tech Stack:** React 18, Figtree + Bricolage Grotesque (Google Fonts, bereits geladen), Flask 2, SQLite (get_connection), RA-MICRO SQL Server (get_ramicro_connection), theme.js für alle Farb-/Schrift-Tokens.

---

## Dateiübersicht

| Datei | Änderung |
|---|---|
| `backend/routers/ramicro_akte_routes.py` | `mandant_checks()` um `rechtsschutz_deckung` erweitern |
| `backend/routers/akten_routes.py` | Neuer Endpunkt `POST /<az>/pwa-nachricht` |
| `frontend/src/api.js` | Neue Funktion `pwaMessage(az, text, vorlageKey)` |
| `frontend/src/sections/UebersichtSection.jsx` | Hauptumbau: neue Komponenten + Zusammenbau |
| `frontend/src/components/AkteDetailView.jsx` | Tab-Reihenfolge + Badge-Logik |

---

## Task 1: Backend – RSV-Check in mandant-checks

**Files:**
- Modify: `backend/routers/ramicro_akte_routes.py:883-902`

Fügt `rechtsschutz_deckung` (bool | None) zum Response hinzu, indem die SQLite-`beteiligte`-Tabelle nach `rolle='rechtsschutz'` durchsucht wird.

- [ ] **Step 1: Imports prüfen**

`get_connection` ist in `ramicro_akte_routes.py` bereits importiert? Prüfen:

```bash
grep -n "get_connection\|from.*db" backend/routers/ramicro_akte_routes.py | head -5
```

Falls nicht vorhanden, am Dateianfang ergänzen:
```python
from ..db.database import get_connection
```

- [ ] **Step 2: mandant_checks erweitern**

In `backend/routers/ramicro_akte_routes.py`, den bestehenden `return jsonify({...})` Block am Ende von `mandant_checks()` (Zeile ~893) ersetzen:

```python
    # RSV-Check: SQLite beteiligte mit rolle='rechtsschutz'
    rsv_vorhanden = False
    try:
        with get_connection() as _sq:
            _rsv = _sq.execute(
                "SELECT COUNT(*) AS n FROM beteiligte WHERE akte_id = ? AND rolle = 'rechtsschutz'",
                (az_basis,)
            ).fetchone()
            rsv_vorhanden = bool(_rsv and _rsv["n"] > 0)
    except Exception as _re:
        logger.debug("rsv_check(%s): %s", az_basis, _re)

    if not m:
        return jsonify({
            "iban_vorhanden":        False,
            "vollmacht_vorhanden":   False,
            "rechtsschutz_deckung":  rsv_vorhanden,
            "mandant_name":          "",
            "mandant_email":         "",
        })

    firma   = (m.get("firma")   or "").strip()
    vorname = (m.get("vorname") or "").strip()
    nachname= (m.get("nachname")or "").strip()
    name    = firma if firma else f"{vorname} {nachname}".strip()
    iban    = (m.get("iban") or "").strip()

    return jsonify({
        "iban_vorhanden":        bool(iban),
        "iban":                  iban if iban else None,
        "bic":                   (m.get("bic") or "").strip() or None,
        "geldinstitut":          (m.get("geldinstitut") or "").strip() or None,
        "mandant_name":          name,
        "mandant_email":         (m.get("email") or "").strip() or None,
        "vollmacht_vorhanden":   vollmacht_wdm,
        "rechtsschutz_deckung":  rsv_vorhanden,
        "az_roh":                az_basis,
    })
```

- [ ] **Step 3: Manuell testen**

```bash
# Im Browser oder curl (Token aus Dev-Login holen):
curl -s "http://localhost:5000/ramicro/akte/mandant-checks?az=322/25" \
  -H "Authorization: Bearer <token>" | python -m json.tool
```

Erwartetes Ergebnis: Response enthält jetzt `"rechtsschutz_deckung": true` oder `false`.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/ramicro_akte_routes.py
git commit -m "feat(mandant-checks): rechtsschutz_deckung aus SQLite beteiligte"
```

---

## Task 2: Backend – PWA-Nachricht Stub-Endpunkt

**Files:**
- Modify: `backend/routers/akten_routes.py`

Neuer Endpunkt schreibt die Nachricht als Aktivitätseintrag. Keine Push-Zustellung (Stub).

- [ ] **Step 1: Endpunkt einfügen**

In `backend/routers/akten_routes.py` direkt nach dem bestehenden `aktivitaet_loeschen`-Endpunkt (Zeile ~470) einfügen:

```python
@akten_bp.route("/<path:akte_id>/pwa-nachricht", methods=["POST"])
@login_erforderlich
def pwa_nachricht_senden(akte_id: str):
    """
    POST /akten/<az>/pwa-nachricht
    Body: { "text": str, "vorlage_key": str (optional) }
    Stub: speichert Nachricht als Aktivitätseintrag, sendet keine Push-Notification.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return jsonify({"fehler": "Akte nicht gefunden"}), 404
    az = akte.aktenzeichen

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    vorlage_key = (data.get("vorlage_key") or "freitext").strip()
    if not text:
        return jsonify({"fehler": "text erforderlich"}), 422

    benutzer_id = getattr(g, "benutzer_id", None)
    beschreibung = f"[PWA:{vorlage_key}] {text[:500]}"

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO aktivitaeten
                (akte_id, benutzer_id, aktion, beschreibung, tabelle)
            VALUES (?, ?, 'pwa_nachricht', ?, 'pwa')
            """,
            (az, benutzer_id, beschreibung)
        )
        akt_id = cursor.lastrowid

    return jsonify({"ok": True, "aktivitaet_id": akt_id})
```

- [ ] **Step 2: Import `g` prüfen**

```bash
grep -n "^from flask import\|^import flask" backend/routers/akten_routes.py | head -3
```

Falls `g` nicht im Import, ergänzen:
```python
from flask import request, jsonify, g
```

- [ ] **Step 3: Manuell testen**

```bash
curl -s -X POST "http://localhost:5000/akten/322%2F25/pwa-nachricht" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text": "Bitte IBAN mitteilen.", "vorlage_key": "iban_anfrage"}' \
  | python -m json.tool
```

Erwartetes Ergebnis: `{"ok": true, "aktivitaet_id": <int>}`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/akten_routes.py
git commit -m "feat(akten): POST pwa-nachricht Stub-Endpunkt"
```

---

## Task 3: Frontend – api.js: pwaMessage()

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Step 1: Funktion hinzufügen**

In `frontend/src/api.js` direkt bei den anderen `akten`-Exports (suche `export const akten`) folgende Methode dem `akten`-Objekt hinzufügen:

```js
pwaMessage: (az, text, vorlageKey = "freitext") =>
  request(`/akten/${encodeURIComponent(az)}/pwa-nachricht`, {
    method: "POST",
    body: JSON.stringify({ text, vorlage_key: vorlageKey }),
  }),
```

- [ ] **Step 2: Im Browser Console testen**

Nach Container-Neustart in der Browser-Konsole:
```js
import("/src/api.js").then(m => m.akten.pwaMessage("322/25", "Test", "freitext").then(console.log))
```
Erwartetes Ergebnis: `{ok: true, aktivitaet_id: <n>}`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(api): akten.pwaMessage() für PWA-Stub"
```

---

## Task 4: Frontend – PwaNachrichtModal

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx` (neues Top-Level-Funktionskomponent einfügen)

Neue Funktion **vor** `UebersichtSection` einfügen. Imports die bereits vorhanden sind: `Card`, `Btn`, `Toast` aus `../components/common.jsx`, `akten as apiAkten` aus `../api.js`, `T` aus `../config/theme.js`.

- [ ] **Step 1: PWA_VORLAGEN Konstante + PwaNachrichtModal einfügen**

Direkt oberhalb von `function UebersichtSection` einfügen:

```jsx
const PWA_VORLAGEN = [
  {
    key: "iban_anfrage",
    label: "Bitte IBAN mitteilen",
    text: "für die Weiterleitung eingegangener Zahlungen benötigen wir noch Ihre Bankverbindung (IBAN). Bitte teilen Sie uns diese baldmöglichst mit.",
  },
  {
    key: "regulierung_eingegangen",
    label: "Regulierungszahlung eingegangen",
    text: "wir möchten Sie informieren, dass eine Zahlung der Gegenseite bei uns eingegangen ist. Wir werden diese nach Prüfung an Sie weiterleiten.",
  },
  {
    key: "sachstand",
    label: "Sachstandsmitteilung",
    text: "wir möchten Sie über den aktuellen Stand Ihrer Akte informieren.",
  },
  { key: "freitext", label: "Freitext", text: "" },
];

function PwaNachrichtModal({ az, mandantName, onClose }) {
  const [vorlageKey, setVorlageKey] = React.useState("iban_anfrage");
  const [text, setText]             = React.useState(PWA_VORLAGEN[0].text);
  const [senden, setSenden]         = React.useState(false);
  const [toast, setToast]           = React.useState("");

  const waehleVorlage = (key) => {
    setVorlageKey(key);
    const v = PWA_VORLAGEN.find(v => v.key === key);
    if (v) setText(v.text);
  };

  const absenden = async () => {
    if (!text.trim()) { setToast("Bitte einen Text eingeben."); return; }
    setSenden(true);
    try {
      await apiAkten.pwaMessage(az, text.trim(), vorlageKey);
      setToast("Nachricht gespeichert.");
      setTimeout(onClose, 1200);
    } catch (e) {
      setToast("Fehler: " + (e?.message || String(e)));
    } finally {
      setSenden(false);
    }
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{
        position:"fixed", inset:0, background:"rgba(0,0,0,.45)",
        zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center",
      }} onClick={onClose}>
        <div style={{
          background:T.offWhite, borderRadius:12, padding:"1.5rem",
          width:"min(520px,96vw)", boxShadow:"0 8px 32px rgba(0,0,0,.18)",
          fontFamily:T.fontBody,
        }} onClick={e => e.stopPropagation()}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:"1rem" }}>
            <span style={{ fontFamily:T.fontDisplay, fontWeight:700, fontSize:"1rem", color:T.navy }}>
              💬 Nachricht an Mandant
            </span>
            {mandantName && (
              <span style={{ fontSize:"0.78rem", color:T.textMuted }}>{mandantName}</span>
            )}
          </div>

          {/* Vorlage-Auswahl */}
          <label style={{ fontSize:"0.75rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:4 }}>
            Vorlage
          </label>
          <select value={vorlageKey} onChange={e => waehleVorlage(e.target.value)}
            style={{ width:"100%", padding:"7px 10px", borderRadius:7, border:`1.5px solid ${T.border}`,
              fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text, background:T.surface,
              marginBottom:"0.75rem", outline:"none" }}>
            {PWA_VORLAGEN.map(v => (
              <option key={v.key} value={v.key}>{v.label}</option>
            ))}
          </select>

          {/* Text */}
          <label style={{ fontSize:"0.75rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:".06em", display:"block", marginBottom:4 }}>
            Nachrichtentext
          </label>
          <textarea value={text} onChange={e => setText(e.target.value)} rows={5}
            style={{ width:"100%", padding:"8px 10px", borderRadius:7, border:`1.5px solid ${T.border}`,
              fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text, background:T.surface,
              resize:"vertical", outline:"none", boxSizing:"border-box", marginBottom:"1rem" }}
            onFocus={e => e.target.style.borderColor = T.accent}
            onBlur={e => e.target.style.borderColor = T.border}
          />

          <div style={{ display:"flex", gap:8, justifyContent:"flex-end" }}>
            <Btn variant="secondary" onClick={onClose}>Abbrechen</Btn>
            <Btn variant="primary" onClick={absenden} disabled={senden}>
              {senden ? "…" : "📤 Senden"}
            </Btn>
          </div>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Im Browser testen**

Dummy-Test: Modal manuell mit `<PwaNachrichtModal az="322/25" onClose={() => {}} />` in der App rendern, Vorlage wechseln, Senden-Button klicken → Toast erscheint.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(uebersicht): PwaNachrichtModal mit Vorlagen"
```

---

## Task 5: Frontend – AkteActionBoardHeader Komponente

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx`

Navy-Header mit AZ, Kurz- und Langbezeichnung sowie Aktionsleiste. Bestehende Komponenten `StaDialog` (bereits importiert in UebersichtSection?) und `TodoSection` werden aus ihren Tabs per Callback aufgerufen.

- [ ] **Step 1: StaDialog-Import prüfen**

```bash
grep -n "StaDialog\|staDialog\|import.*Sta" frontend/src/sections/UebersichtSection.jsx | head -5
```

Falls nicht vorhanden, am Dateianfang ergänzen:
```js
import StaDialog from "../components/StaDialog.jsx";
```

- [ ] **Step 2: AkteActionBoardHeader einfügen**

Direkt nach `PwaNachrichtModal` und vor `UebersichtSection` einfügen:

```jsx
function AkteActionBoardHeader({ akte, azRoh, mandantName, onNavigate }) {
  const [zeigePwModal, setZeigePwModal] = React.useState(false);
  const [zeigeStaDialog, setZeigeStaDialog] = React.useState(false);
  const [zeigeTodoForm, setZeigeTodoForm] = React.useState(false);

  // Bezeichnungen aus Akte-Objekt
  const az       = akte.az_roh || akte.az || "";
  const kurz     = akte.kurzbezeichnung || akte.kurzbez || "";
  const lang     = akte.bezeichnung || akte.langbezeichnung || "";

  const BTN = ({ children, onClick, stil = "ghost" }) => {
    const styles = {
      ghost:    { background:"rgba(255,255,255,.12)", color:"white",  border:"1px solid rgba(255,255,255,.22)" },
      primary:  { background:T.accent,               color:"white",  border:"none" },
      warn:     { background:T.amber,                color:"#1a1a00",border:"none" },
      dimmed:   { background:"rgba(255,255,255,.07)", color:T.textFaint, border:"1px solid rgba(255,255,255,.1)" },
    };
    return (
      <button onClick={onClick} style={{
        ...styles[stil],
        fontFamily:T.fontBody, fontSize:"0.72rem", fontWeight:600,
        padding:"5px 12px", borderRadius:6, cursor:"pointer",
        display:"flex", alignItems:"center", gap:4, whiteSpace:"nowrap",
      }}>{children}</button>
    );
  };

  return (
    <>
      {zeigePwModal && (
        <PwaNachrichtModal
          az={azRoh || az}
          mandantName={mandantName}
          onClose={() => setZeigePwModal(false)}
        />
      )}
      {zeigeStaDialog && (
        <StaDialog
          az={azRoh || az}
          onClose={() => setZeigeStaDialog(false)}
        />
      )}

      <div style={{ background:T.navy, borderRadius:"10px 10px 0 0", padding:"12px 18px 10px" }}>
        {/* AZ + Kurzbezeichnung */}
        <div style={{ display:"flex", alignItems:"baseline", gap:14, flexWrap:"wrap", marginBottom:3 }}>
          <span style={{
            fontFamily:"'Bricolage Grotesque',system-ui,sans-serif",
            fontSize:"1.5rem", fontWeight:800, color:"white", letterSpacing:".03em", lineHeight:1,
          }}>{az}</span>
          {kurz && (
            <span style={{
              fontFamily:"'Bricolage Grotesque',system-ui,sans-serif",
              fontSize:"1.1rem", fontWeight:600, color:T.accentLight, lineHeight:1,
            }}>{kurz}</span>
          )}
        </div>
        {/* Langbezeichnung */}
        {lang && (
          <div style={{
            fontFamily:T.fontBody, fontSize:"0.88rem", color:T.textFaint, marginTop:2,
          }}>{lang}</div>
        )}

        {/* Aktionsleiste */}
        <div style={{
          display:"flex", gap:6, flexWrap:"wrap",
          marginTop:10, paddingTop:10,
          borderTop:"1px solid rgba(255,255,255,.1)",
        }}>
          <BTN stil="primary" onClick={() => setZeigePwModal(true)}>💬 Nachricht → Mandant</BTN>
          <BTN stil="warn"    onClick={() => setZeigeStaDialog(true)}>📤 STA senden</BTN>
          <BTN stil="ghost"   onClick={() => setZeigeTodoForm(true)}>+ Todo</BTN>
          <BTN stil="ghost"   onClick={() => onNavigate && onNavigate("word")}>📄 Forderungsschr.</BTN>
          <BTN stil="dimmed"  onClick={() => onNavigate && onNavigate("word")}>⬇ Word</BTN>
        </div>
      </div>

      {/* Todo-Formular-Overlay (inline, kein eigenes Modal) */}
      {zeigeTodoForm && (
        <div style={{
          background:T.surface, border:`1px solid ${T.border}`,
          borderTop:"none", padding:"12px 18px",
        }}>
          <TodoInlineForm az={azRoh || az} onDone={() => setZeigeTodoForm(false)} />
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 3: TodoInlineForm einfügen**

Direkt vor `AkteActionBoardHeader` einfügen (minimale Version des Todo-Formulars):

```jsx
function TodoInlineForm({ az, onDone }) {
  const [text, setText]       = React.useState("");
  const [faellig, setFaellig] = React.useState("");
  const [busy, setBusy]       = React.useState(false);
  const [toast, setToast]     = React.useState("");

  const speichern = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      await apiTodos.erstellen(az, { text: text.trim(), faellig_am: faellig || null, frist_typ: "" });
      onDone();
    } catch (e) {
      setToast("Fehler: " + (e?.message || String(e)));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}
      <div style={{ display:"flex", gap:8, alignItems:"center", flexWrap:"wrap" }}>
        <input
          type="text" value={text} onChange={e => setText(e.target.value)}
          placeholder="To-Do Text …"
          style={{
            flex:1, minWidth:200, padding:"6px 10px",
            border:`1.5px solid ${T.border}`, borderRadius:6,
            fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text,
            background:T.white, outline:"none",
          }}
          onFocus={e => e.target.style.borderColor = T.accent}
          onBlur={e => e.target.style.borderColor = T.border}
          onKeyDown={e => { if (e.key === "Enter") speichern(); if (e.key === "Escape") onDone(); }}
          autoFocus
        />
        <input
          type="date" value={faellig} onChange={e => setFaellig(e.target.value)}
          style={{
            padding:"6px 10px", border:`1.5px solid ${T.border}`, borderRadius:6,
            fontFamily:T.fontBody, fontSize:"0.875rem", color:T.text,
            background:T.white, outline:"none",
          }}
        />
        <Btn variant="gold" size="sm" onClick={speichern} disabled={busy || !text.trim()}>
          {busy ? "…" : "✓ Anlegen"}
        </Btn>
        <Btn variant="secondary" size="sm" onClick={onDone}>Abbrechen</Btn>
      </div>
    </>
  );
}
```

- [ ] **Step 4: apiTodos.erstellen prüfen**

```bash
grep -n "erstellen\|erstelle\|create" frontend/src/api.js | grep -i todo | head -5
```

Falls `apiTodos.erstellen` nicht existiert, stattdessen `apiTodos.anlegen` oder ähnliches verwenden (Namen aus dem tatsächlichen api.js übernehmen).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(uebersicht): AkteActionBoardHeader + TodoInlineForm"
```

---

## Task 6: Frontend – StatusBand + FinanzBand

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx`

- [ ] **Step 1: StatusBand einfügen**

Direkt vor `UebersichtSection` einfügen:

```jsx
function StatusBand({ ibanCheck, todos }) {
  // Check-Pills aus mandant-checks Response
  const vollmacht = ibanCheck?.vollmacht_vorhanden;
  const iban      = ibanCheck?.iban_vorhanden;
  const rsv       = ibanCheck?.rechtsschutz_deckung;

  const Pill = ({ ok, warn, label }) => {
    let bg, color, border;
    if (ok === true)  { bg = T.greenBg;  color = T.greenText;  border = T.greenLight; }
    else if (ok === false && !warn) { bg = T.redBg; color = T.redText; border = T.redLight; }
    else if (warn)    { bg = T.amberMid; color = T.amberText;  border = T.amber + "80"; }
    else              { bg = T.surface;  color = T.textFaint;  border = T.border; }
    return (
      <span style={{
        display:"inline-flex", alignItems:"center", gap:4,
        fontSize:"0.7rem", fontWeight:600, padding:"3px 9px",
        borderRadius:20, border:`1px solid ${border}`,
        background:bg, color, whiteSpace:"nowrap",
      }}>{label}</span>
    );
  };

  // §3a-Frist und Verjährung aus Todos
  const heute = new Date(); heute.setHours(0,0,0,0);
  const fristTodo = (todos || []).find(t => !t.erledigt && (t.frist_typ === "gerichtlich" || t.frist_typ === "verjaehrung" && false));
  const verjTodo  = (todos || []).find(t => !t.erledigt && t.frist_typ === "verjaehrung");

  const tageBis = (iso) => {
    if (!iso) return null;
    const d = new Date(iso); d.setHours(0,0,0,0);
    return Math.round((d - heute) / 86400000);
  };

  const fristTage = fristTodo ? tageBis(fristTodo.faellig_am) : null;
  const verjTage  = verjTodo  ? tageBis(verjTodo.faellig_am)  : null;

  const fmtDatum = (iso) => {
    if (!iso) return "";
    try { const [y,m,d] = iso.split("-"); return `${d}.${m}.${y}`; } catch { return iso; }
  };

  return (
    <div style={{
      background:T.surface, borderTop:`1px solid ${T.border}`,
      padding:"7px 18px", display:"flex", alignItems:"center",
      gap:0, flexWrap:"wrap",
    }}>
      {/* Checks */}
      <div style={{ display:"flex", gap:7, alignItems:"center", paddingRight:14, marginRight:14, borderRight:`1px solid ${T.border}`, flexWrap:"wrap" }}>
        <span style={{ fontSize:".62rem", fontWeight:700, color:T.textFaint, textTransform:"uppercase", letterSpacing:".07em" }}>Checks</span>
        <Pill ok={vollmacht}
          label={vollmacht === true ? "✓ Vollmacht" : vollmacht === false ? "✗ Vollmacht fehlt" : "○ Vollmacht"} />
        <Pill ok={iban}
          label={iban === true ? "✓ IBAN" : iban === false ? "✗ IBAN fehlt" : "○ IBAN"} />
        <Pill ok={rsv === true} warn={rsv === "anfrage"}
          label={rsv === true ? "✓ RSV" : rsv === false ? "○ Keine RSV" : "⚠ RSV: Anfrage"} />
      </div>

      {/* Meta-Pills */}
      <div style={{ display:"flex", gap:7, alignItems:"center", flexWrap:"wrap" }}>
        {fristTage !== null && (
          <span style={{
            display:"inline-flex", alignItems:"center", gap:4,
            fontSize:"0.7rem", fontWeight: fristTage <= 7 ? 700 : 400,
            padding:"3px 9px", borderRadius:20, whiteSpace:"nowrap",
            border:`1px solid ${fristTage <= 7 ? T.redLight : T.border}`,
            background: fristTage <= 7 ? T.redBg : T.surface,
            color: fristTage <= 7 ? T.redText : T.textMuted,
          }}>§3a-Frist: {fristTage < 0 ? "überschritten" : `${fristTage} Tage`}</span>
        )}
        {verjTage !== null && (
          <span style={{
            display:"inline-flex", alignItems:"center", gap:4,
            fontSize:"0.7rem", fontWeight: verjTage <= 14 ? 700 : 400,
            padding:"3px 9px", borderRadius:20, whiteSpace:"nowrap",
            border:`1px solid ${verjTage <= 60 ? T.amber + "80" : T.border}`,
            background: verjTage <= 14 ? T.redBg : verjTage <= 60 ? T.amberMid : T.surface,
            color: verjTage <= 14 ? T.redText : verjTage <= 60 ? T.amberText : T.textMuted,
          }}>Verjährung: {fmtDatum(verjTodo.faellig_am)}</span>
        )}
        {akte => akte?.hq !== undefined && akte.hq !== null && akte.hq < 100 && (
          <span style={{
            display:"inline-flex", alignItems:"center", gap:4,
            fontSize:"0.7rem", padding:"3px 9px", borderRadius:20,
            border:`1px solid ${T.amber}80`, background:T.amberMid, color:T.amberText,
            whiteSpace:"nowrap",
          }}>HQ {akte.hq} %</span>
        )}
      </div>
    </div>
  );
}
```

**Hinweis:** `akte` ist im `StatusBand` nicht direkt verfügbar — der HQ-Pill wird im Elternelement `UebersichtSection` separat gerendert oder als Prop übergeben. Einfacher: HQ als eigene Prop:

```jsx
// Signatur anpassen:
function StatusBand({ ibanCheck, todos, hq }) {
  // ...
  // HQ-Pill mit hq-Prop statt akte.hq:
  {hq !== null && hq !== undefined && hq < 100 && (
    <span style={{...}}>HQ {hq} %</span>
  )}
}
```

- [ ] **Step 2: FinanzBand einfügen**

Direkt nach `StatusBand`:

```jsx
function FinanzBand({ gesamtForderung, gesamtReguliert, gesamtKuerzung, anzahlSchreiben }) {
  const offen   = Math.max(0, gesamtForderung - gesamtReguliert);
  const regGrad = gesamtForderung > 0 ? Math.min(100, Math.round(gesamtReguliert / gesamtForderung * 100)) : 0;
  const hatReg  = anzahlSchreiben > 0;

  const Item = ({ label, value, farbe }) => (
    <div style={{ display:"flex", flexDirection:"column", paddingRight:20, marginRight:20, borderRight:`1px solid ${T.border}` }}>
      <span style={{ fontSize:".62rem", fontWeight:600, color:T.accent, textTransform:"uppercase", letterSpacing:".06em" }}>{label}</span>
      <span style={{ fontFamily:T.fontMono, fontSize:"1rem", fontWeight:700, color:farbe || T.navy, marginTop:1 }}>
        {fmtEuro(value)}
      </span>
    </div>
  );

  if (!hatReg && gesamtForderung === 0) return null;

  return (
    <div style={{
      background:T.accentPale, borderTop:`1px solid ${T.accentTrim}`,
      padding:"8px 18px", display:"flex", alignItems:"center", flexWrap:"wrap", gap:0,
    }}>
      <Item label="Gefordert"   value={gesamtForderung} />
      {hatReg && <Item label="Reguliert"  value={gesamtReguliert} farbe={T.green} />}
      {hatReg && <Item label="Noch offen" value={offen}           farbe={offen > 0 ? T.red : T.green} />}
      {hatReg && gesamtKuerzung > 0 && <Item label="Kürzungen" value={gesamtKuerzung} farbe={T.amber} />}

      {hatReg && (
        <div style={{ flex:1, minWidth:140, display:"flex", flexDirection:"column", justifyContent:"center" }}>
          <span style={{ fontSize:".62rem", fontWeight:600, color:T.accentDark, textTransform:"uppercase", letterSpacing:".06em" }}>
            Regulierungsfortschritt
          </span>
          <div style={{ height:6, background:T.border, borderRadius:3, overflow:"hidden", marginTop:4 }}>
            <div style={{ height:"100%", width:`${regGrad}%`, background:T.accent, borderRadius:3, transition:"width .8s" }} />
          </div>
          <span style={{ fontSize:".65rem", color:T.accentDark, fontWeight:600, marginTop:2 }}>
            {regGrad} % · {anzahlSchreiben} {anzahlSchreiben === 1 ? "Schreiben" : "Schreiben"}
          </span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(uebersicht): StatusBand + FinanzBand Komponenten"
```

---

## Task 7: Frontend – TodoWvSpalten (2-Spalten Body)

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx`

Refactoring: `TodoKachelKompakt` wird zu `TodoWvSpalten` umgebaut — gleiches API, neue Darstellung ohne Card-Wrapper (der kommt vom Elternelement).

- [ ] **Step 1: TodoWvSpalten einfügen**

`TodoKachelKompakt` bleibt unverändert (wird noch in anderen Kontexten genutzt?). Neues separates Komponent:

```jsx
function TodoWvSpalten({ az, azRoh, onTodoChange }) {
  const [todos,   setTodos]   = React.useState([]);
  const [wvListe, setWvListe] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    const todoCall = Promise.race([
      apiTodos.liste(az),
      new Promise((_, r) => setTimeout(() => r(new Error("timeout")), 8000)),
    ]).catch(() => ({ todos: [] }));

    const wvCall = azRoh && azRoh.includes("/")
      ? request(`/wiedervorlage/?az=${encodeURIComponent(azRoh)}&alle_gruende=true&alle_daten=true&limit=10`)
          .then(r => r?.wiedervorlagen || [])
          .catch(() => [])
      : Promise.resolve([]);

    Promise.all([todoCall, wvCall])
      .then(([tRes, wRes]) => {
        setTodos(tRes?.todos || []);
        setWvListe(wRes);
      })
      .finally(() => setLoading(false));
  }, [az, azRoh]);

  const offen = todos.filter(t => !t.erledigt);

  const dringlichkeit = (todo) => {
    const heute = new Date(); heute.setHours(0,0,0,0);
    if (todo.faellig_am) {
      const f = new Date(todo.faellig_am); f.setHours(0,0,0,0);
      const tage = Math.round((f - heute) / 86400000);
      const s = tage < 0 ? "rot" : tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
      return todo.frist_typ === "verjaehrung" ? ({rot:"rot",orange:"rot",gelb:"orange",grau:"gelb"}[s]||s) : s;
    }
    const alter = Math.round((heute - new Date(todo.erstellt_am)) / 86400000);
    return alter >= 15 ? "rot" : alter >= 8 ? "orange" : alter >= 4 ? "gelb" : "grau";
  };

  const DOT = { rot:"#ef4444", orange:"#f97316", gelb:"#eab308", grau:T.textFaint };

  const fmtD = (iso) => {
    if (!iso) return "";
    try { const [,m,d] = iso.split("-"); return `${d}.${m}.`; } catch { return ""; }
  };

  if (loading) return null;

  const hatWv = wvListe.length > 0;

  return (
    <div style={{
      display:"grid",
      gridTemplateColumns: hatWv ? "1fr 1px 1fr" : "1fr",
      padding:"12px 18px 14px", gap:0,
    }}>
      {/* Todos */}
      <div style={{ paddingRight: hatWv ? 16 : 0 }}>
        <div style={{ fontSize:".65rem", fontWeight:700, color:T.textFaint, textTransform:"uppercase", letterSpacing:".08em", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
          📋 To-Dos
          {offen.length > 0 && (
            <span style={{ background:T.redBg, color:T.red, borderRadius:10, padding:"1px 7px", fontSize:".62rem", fontWeight:700 }}>
              {offen.length} offen
            </span>
          )}
        </div>
        {offen.length === 0 ? (
          <div style={{ fontSize:".875rem", color:T.textFaint, fontFamily:T.fontBody }}>✅ Alle erledigt</div>
        ) : (
          offen.slice(0, 5).map(todo => {
            const d = dringlichkeit(todo);
            return (
              <div key={todo.id} style={{ display:"flex", alignItems:"flex-start", gap:7, padding:"5px 0", borderBottom:`1px solid ${T.borderSoft}` }}>
                <span style={{ width:8, height:8, borderRadius:"50%", background:DOT[d], flexShrink:0, marginTop:5 }} />
                <span style={{ fontFamily:T.fontBody, fontSize:".875rem", color:T.text, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                  {todo.text}
                </span>
                {todo.faellig_am && (
                  <span style={{ fontFamily:T.fontMono, fontSize:".68rem", color:T.textFaint, flexShrink:0 }}>
                    {fmtD(todo.faellig_am)}
                  </span>
                )}
              </div>
            );
          })
        )}
        {offen.length > 5 && (
          <div style={{ fontSize:".78rem", color:T.textFaint, marginTop:5, fontFamily:T.fontBody }}>
            + {offen.length - 5} weitere …
          </div>
        )}
      </div>

      {/* Trennlinie */}
      {hatWv && <div style={{ background:T.border, width:1 }} />}

      {/* Wiedervorlagen */}
      {hatWv && (
        <div style={{ paddingLeft:16 }}>
          <div style={{ fontSize:".65rem", fontWeight:700, color:T.textFaint, textTransform:"uppercase", letterSpacing:".08em", marginBottom:8, display:"flex", alignItems:"center", gap:6 }}>
            📅 Wiedervorlagen
            <span style={{ background:T.amberMid, color:T.amberText, borderRadius:10, padding:"1px 7px", fontSize:".62rem", fontWeight:700 }}>
              {wvListe.length} fällig
            </span>
          </div>
          {wvListe.slice(0, 4).map((wv, i) => (
            <div key={wv.guid || i} style={{
              background:T.amberMid, border:`1px solid ${T.amber}50`,
              borderRadius:6, padding:"6px 10px", marginBottom:5,
            }}>
              <div style={{ fontFamily:T.fontBody, fontSize:".78rem", fontWeight:700, color:T.amberText, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                {wv.grund || "Wiedervorlage"}
              </div>
              <div style={{ fontFamily:T.fontMono, fontSize:".68rem", color:T.amberText, marginTop:2 }}>
                fällig {fmtD(wv.datum)}{new Date(wv.datum).getFullYear()}
              </div>
            </div>
          ))}
          {wvListe.length > 4 && (
            <div style={{ fontSize:".72rem", color:T.textFaint }}>+ {wvListe.length - 4} weitere</div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(uebersicht): TodoWvSpalten 2-Spalten-Body"
```

---

## Task 8: Frontend – AkkordeonStrip

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx`

Horizontale Button-Leiste die die bestehenden Klapp-Abschnitte steuert.

- [ ] **Step 1: AkkordeonStrip einfügen**

```jsx
const STRIP_TABS = [
  { id:"ramicro",     label:"🏛 RA-Micro Stammdaten" },
  { id:"historie",    label:"📜 Forderungshistorie" },
  { id:"regulierung", label:"⚖️ Regulierungsdetails" },
  { id:"chronik",     label:"🕒 Akten-Chronik" },
  { id:"notizen",     label:"📝 Notizen" },
];

function AkkordeonStrip({ offene, onToggle }) {
  return (
    <div style={{
      borderTop:`2px solid ${T.border}`,
      display:"flex", flexWrap:"wrap",
    }}>
      {STRIP_TABS.map((tab, i) => (
        <button key={tab.id} onClick={() => onToggle(tab.id)}
          style={{
            flex:1, minWidth:130,
            padding:"9px 14px",
            fontFamily:T.fontBody, fontSize:".72rem",
            color: offene.includes(tab.id) ? T.accentDark : T.textMuted,
            background: offene.includes(tab.id) ? T.accentPale : T.surface,
            border:"none",
            borderRight: i < STRIP_TABS.length - 1 ? `1px solid ${T.border}` : "none",
            cursor:"pointer", textAlign:"left",
            display:"flex", alignItems:"center", gap:5,
            transition:"background .15s, color .15s",
          }}>
          {tab.label}
          <span style={{ marginLeft:"auto", fontSize:".75rem" }}>
            {offene.includes(tab.id) ? "▲" : "▾"}
          </span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(uebersicht): AkkordeonStrip horizontale Buttonleiste"
```

---

## Task 9: Frontend – UebersichtSection Zusammenbau

**Files:**
- Modify: `frontend/src/sections/UebersichtSection.jsx` — Hauptfunktion umbauen

- [ ] **Step 1: ibanCheck State + useEffect ergänzen**

Am Anfang von `UebersichtSection` (nach bestehenden States) ergänzen:

```jsx
const [ibanCheck, setIbanCheck] = useState(null);
const [stripOffene, setStripOffene] = useState([]);

const azRoh = akte.az_roh || akte.az || "";

React.useEffect(() => {
  if (!azRoh.includes("/")) return;
  request(`/ramicro/akte/mandant-checks?az=${encodeURIComponent(azRoh)}`)
    .then(d => setIbanCheck(d))
    .catch(() => setIbanCheck({ iban_vorhanden: null }));
}, [azRoh]);

const toggleStrip = (id) => {
  setStripOffene(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
  );
};
```

- [ ] **Step 2: Rendering ersetzen**

Den bisherigen `return`-Block von `UebersichtSection` ersetzen:

```jsx
  const azKlappKey = azRoh.replace(/\//g, "-");
  const mandantName = ibanCheck?.mandant_name || mandant?.name || "";

  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")} />}

      {/* ── Action Board ── */}
      <div style={{ border:`1px solid ${T.border}`, borderRadius:10, overflow:"hidden", marginBottom:"1.25rem", boxShadow:"0 1px 4px rgba(0,0,0,.05)" }}>

        <AkteActionBoardHeader
          akte={akte}
          azRoh={azRoh}
          mandantName={mandantName}
          onNavigate={null}
        />

        <StatusBand
          ibanCheck={ibanCheck}
          todos={st.todos || []}
          hq={akte.hq}
        />

        <FinanzBand
          gesamtForderung={gesamtForderung}
          gesamtReguliert={gesamtReguliert}
          gesamtKuerzung={gesamtKuerzung}
          anzahlSchreiben={abrechnungen.length}
        />

        <TodoWvSpalten az={akte.az} azRoh={azRoh} />

        <AkkordeonStrip offene={stripOffene} onToggle={toggleStrip} />

      </div>

      {/* ── Ausklappbare Abschnitte ── */}
      {stripOffene.includes("ramicro") && azRoh.includes("/") && (
        <div style={{ marginBottom:"1rem" }}>
          <RaMicroAkteUebersicht azRoh={azRoh} />
        </div>
      )}

      {stripOffene.includes("historie") && (
        <KlappAbschnitt titel="Forderungshistorie" lsKey={`uebersicht-historie-${azKlappKey}`}>
          <ForderungshistorieKarte akteId={akte.id} />
        </KlappAbschnitt>
      )}

      {stripOffene.includes("regulierung") && (
        <div style={{ marginBottom:"1rem" }}>
          <Card style={{ background:"rgba(84,136,212,0.06)", border:"1px solid rgba(84,136,212,0.25)" }}>
            <CardHead title="Forderung vs. Regulierung – Positionsübersicht" />
            <RegulierungsTabelle
              schaden={schaden}
              abrechnungen={abrechnungen}
              showCheckboxes={false}
              showKlageBadge={true}
            />
          </Card>
        </div>
      )}

      {stripOffene.includes("chronik") && (
        <KlappAbschnitt titel="Akten-Chronik" lsKey={`uebersicht-chronik-${azKlappKey}`}>
          <AktenTimeline
            abrechnungen={abrechnungen}
            aktivitaeten={st.aktivitaeten || []}
            akteId={akte.id}
            onAktivitaetenChange={async () => {
              const data = await apiAkten.aktivitaeten(akte.id);
              if (data?.aktivitaeten)
                dispatch({ type:"SET_AKTIVITAETEN", akteId:akte.id, aktivitaeten:data.aktivitaeten });
            }}
          />
        </KlappAbschnitt>
      )}

      {stripOffene.includes("notizen") && (
        <Card style={{ padding:"0.6rem 1rem", display:"flex", flexDirection:"column", gap:5 }}>
          <textarea value={notizen} onChange={e => { setNotizen(e.target.value); setNC(true); }} rows={3}
            placeholder="Interne Notizen …"
            style={{ padding:"5px 8px", border:`1.5px solid ${T.border}`, borderRadius:6,
              fontSize:"0.875rem", color:T.text, background:T.surface, outline:"none", resize:"none",
              fontFamily:T.fontBody }}
            onFocus={e => e.target.style.borderColor = T.accent}
            onBlur={e => e.target.style.borderColor = T.border} />
          {nChanged && (
            <Btn variant="gold" size="sm" onClick={async () => {
              dispatch({ type:"SET_NOTIZEN", akteId:akte.id, notizen });
              setNC(false); setToast("Notizen gespeichert.");
              try { await apiAkten.aktualisieren(akte.id, { notizen }); } catch {}
            }}>{Ic.check} Speichern</Btn>
          )}
        </Card>
      )}
    </>
  );
```

**Wichtig:** Der bisherige `ibanCheck`-Aufruf in `BeteiligterKachel` (für die Mandanten-Kachel in `RaMicroAkteUebersicht`) bleibt erhalten — der ist unabhängig vom neuen `StatusBand`.

- [ ] **Step 3: st.todos Verfügbarkeit prüfen**

```bash
grep -n "SET_TODOS\|todos.*state\|initialState.*todos" frontend/src/components/AkteDetailView.jsx | head -10
```

Falls `st.todos` nicht im State: Im `StatusBand`-Aufruf statt `st.todos` die `todos`-Variable aus dem neu hinzugefügten State in UebersichtSection verwenden (die `TodoWvSpalten` lädt sie separat — für den `StatusBand` die todos aus dem internen State von `TodoWvSpalten` hochheben oder separat laden).

Einfachste Lösung — separaten Todos-Load am Anfang von `UebersichtSection`:
```jsx
const [todosState, setTodosState] = useState([]);
React.useEffect(() => {
  if (!akte.az) return;
  apiTodos.liste(akte.az).then(r => setTodosState(r?.todos || [])).catch(() => {});
}, [akte.az]);
```
Dann `todos={todosState}` an `StatusBand` übergeben.

- [ ] **Step 4: Im Browser testen**

1. Akte öffnen → Übersicht-Tab → Action Board erscheint mit Navy-Header
2. „💬 Nachricht → Mandant"-Button → Modal öffnet sich
3. Vorlage wechseln → Text ändert sich
4. Senden → Toast erscheint, Modal schließt sich nach 1.2s
5. Strip-Button „🏛 RA-Micro Stammdaten" → klappt auf
6. Status-Band zeigt Pills korrekt (IBAN rot wenn leer, grün wenn vorhanden)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(uebersicht): Action Board Zusammenbau"
```

---

## Task 10: Frontend – Navigation Redesign

**Files:**
- Modify: `frontend/src/components/AkteDetailView.jsx`

Übersicht an erste Stelle, localStorage-Badges für Dokumente und Regulierung.

- [ ] **Step 1: Tab-Reihenfolge ändern**

In `AkteDetailView.jsx`, im `useMemo`-Block (Zeile ~191), `uebersicht` an erste Stelle verschieben:

```jsx
return [
  { id:"uebersicht",    label:"⚡ Übersicht" },            // ← neu: erste Stelle
  { id:"beteiligte",    label:`👥 Beteiligte`, ...sp(beteiligteOk, !beteiligteOk && st.beteiligte !== undefined) },
  { id:"unfalldetails", label:"🔍 Unfalldetails" },
  { id:"schaden",       label:`🚗 Schaden`, ...sp(schadenOk, !schadenOk && st.schaden !== undefined) },
  { id:"dokumente",     label:`📄 Dokumente (${dokumenteAnz})` },
  { id:"regulierung",   label:`💶 Regulierung`, ...sp(regulierungOk, false) },
  { id:"gebuehren",     label:"⚖️ Gebühren" },
  { id:"klage",         label:`⚖ Klage`, ...sp(klageStatus, false) },
  { id:"word",          label:"📝 Word" },
  { id:"todos",         label:`📋 To-Dos` },
];
```

- [ ] **Step 2: Standard-Tab auf "uebersicht" setzen**

In `AkteDetailView.jsx`, Zeile ~35:
```jsx
const [sec, setSec] = useState("uebersicht");
```
Bereits auf `"uebersicht"` gesetzt → keine Änderung nötig. Prüfen:
```bash
grep -n 'useState("uebersicht")\|useState("beteiligte")' frontend/src/components/AkteDetailView.jsx
```

- [ ] **Step 3: Badge-Logik ergänzen**

In `AkteDetailView.jsx`, innerhalb des `useMemo`-Blocks, vor dem `return`, Badge-Berechnung ergänzen:

```jsx
// Badges: localStorage-Timestamps
const lsKeyDok = `tab-letztbesucht-${akte?.az?.replace(/\//g,"-")}-dokumente`;
const lsKeyReg = `tab-letztbesucht-${akte?.az?.replace(/\//g,"-")}-regulierung`;

const letzterBesuchDok = localStorage.getItem(lsKeyDok);
const letzterBesuchReg = localStorage.getItem(lsKeyReg);

const neueDokumente = letzterBesuchDok
  ? (st.dokumente || []).filter(d => d.erstellt_am && d.erstellt_am > letzterBesuchDok).length
  : 0;
const neueAbrechnung = letzterBesuchReg && (st.abrechnungen || []).length > 0
  ? (st.abrechnungen[0]?.erstellt_am || "") > letzterBesuchReg
  : false;
```

Dann `dokumente`- und `regulierung`-Tab-Labels anpassen:

```jsx
{ id:"dokumente",   label: neueDokumente > 0 ? `📄 Dokumente (${dokumenteAnz}) 🔴${neueDokumente}` : `📄 Dokumente (${dokumenteAnz})` },
{ id:"regulierung", label: neueAbrechnung ? `💶 Regulierung 🔴` : `💶 Regulierung`, ...sp(regulierungOk, false) },
```

- [ ] **Step 4: Timestamp beim Tab-Besuch setzen**

Im `setSec`-Aufruf (wo Tab-Wechsel stattfindet), Timestamp schreiben. Suchen:
```bash
grep -n "setSec\|onClick.*setSec\|setzeTab" frontend/src/components/AkteDetailView.jsx | head -10
```

An der Stelle wo `setSec(t.id)` aufgerufen wird ergänzen:
```jsx
setSec(t.id);
const lsKey = `tab-letztbesucht-${akte?.az?.replace(/\//g,"-")}-${t.id}`;
localStorage.setItem(lsKey, new Date().toISOString());
```

- [ ] **Step 5: Im Browser testen**

1. Akte öffnen → erster Tab ist „⚡ Übersicht"
2. Neues Dokument importieren → Dokumente-Tab zeigt rote Zahl
3. Dokumente-Tab besuchen → Badge verschwindet beim nächsten Öffnen der Akte

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AkteDetailView.jsx
git commit -m "feat(navigation): Übersicht erster Tab + Dokumente/Regulierung Badges"
```

---

## Self-Review

### Spec-Coverage

| Spec-Anforderung | Task |
|---|---|
| Akte-Header: AZ + Kurz + Lang | Task 5 |
| Aktionsleiste: PWA, STA, Todo, Forderungsschr., Word | Task 5 |
| Check-Pills: Vollmacht, IBAN, RSV | Task 1 + Task 6 |
| Meta-Pills: HQ, §3a-Frist, Verjährung | Task 6 |
| Finanz-Band: Gefordert/Reguliert/Offen/Kürzungen | Task 6 |
| 2-Spalten-Body: Todos + WV | Task 7 |
| Akkordeon-Strip horizontal | Task 8 |
| Zusammenbau UebersichtSection | Task 9 |
| PWA-Nachricht Modal (Frontend) | Task 4 |
| PWA api.js | Task 3 |
| PWA Backend Stub | Task 2 |
| Navigation: Übersicht erster Tab | Task 10 |
| Navigation: Badges | Task 10 |
| RSV in mandant-checks | Task 1 |

Alle Spec-Anforderungen sind abgedeckt.

### Offene Fragen (aus Spec) – Entscheidungen

1. **RSV-Quelle** → SQLite `beteiligte` WHERE `rolle='rechtsschutz'` (Task 1)
2. **Langbezeichnung** → `akte.bezeichnung` oder `akte.langbezeichnung` (Task 5 — Fallback-Chain)  
3. **Badge-Persistenz** → localStorage (Task 10)

### Risikohinweise

- `apiTodos.erstellen` vs. `apiTodos.anlegen`: Task 5 Step 4 weist explizit darauf hin
- `st.todos` nicht im State: Task 9 Step 3 zeigt Workaround mit separatem Load
- `StaDialog`-Props: Vor Task 5 prüfen ob `StaDialog` Props `az` + `onClose` unterstützt
