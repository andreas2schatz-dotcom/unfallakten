# E-Mail-Workflow Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Einen durchgehenden E-Mail-Workflow bauen: Action Dashboard → E-Mail-Detail-Seite → PDF-Vorschau → In-Akte-Import, plus E-Mail-Gruppe in DokumenteSection.

**Architecture:** `UnfallEmailView` verwaltet einen neuen `geöffneteEmail`-State; bei gesetztem Wert rendert er statt des Streams die neue `EmailDetailView`. App.jsx leitet Klicks aus dem ActionBoard über einen `pendingEmailId`-State als `initialEmailId`-Prop durch die Komponenten-Kette. Die DokumenteSection bekommt eine eigenständige E-Mail-Gruppe, die `emailImport.log` für die aktuelle Akte abfragt.

**Tech Stack:** React (JSX, Inline-Styles), Flask (Python), SQLite

---

## File Map

| Datei | Aktion | Zweck |
|---|---|---|
| `frontend/src/views/email_import/EmailDetailView.jsx` | **Neu** | 2-spaltige Detail-Seite |
| `frontend/src/views/email_import/UnfallEmailView.jsx` | Modify | `geöffneteEmail` State, `initialEmailId` Prop |
| `frontend/src/views/email_import/components/EmailKarte.jsx` | Modify | „▶ E-Mail öffnen"-Button |
| `frontend/src/views/EmailImportView.jsx` | Modify | `initialEmailId` Prop durchreichen |
| `frontend/src/App.jsx` | Modify | `openEmail` Handler, `pendingEmailId` State |
| `frontend/src/views/ActionBoardView.jsx` | Modify | `NachrichtenSpalte` nutzt `onOpenEmail` |
| `frontend/src/sections/DokumenteSection.jsx` | Modify | E-Mail-Gruppe mit Inline-Expand |
| `frontend/src/api.js` | Modify | `emailImport.inAkte(logId, erzwingen)` |
| `frontend/src/views/email_import/components/InAkteButton.jsx` | Modify | nutzt `emailImport.inAkte` statt direktem `request()` |
| `backend/routers/dashboard_routes.py` | Modify | `log_id` Feld in `nachrichten-neu` |
| `backend/db/schema_manager.py` | Modify | Migration 42: `.eml`-Zeilen korrigieren |
| `backend/email_import/import_service.py` | Modify | `.eml`-Import mit `dateityp='sonstiges'`, `dokumentenklasse='email'` |

---

## Task 1: Backend – `nachrichten-neu` liefert `log_id`

**Files:**
- Modify: `backend/routers/dashboard_routes.py:334-351`
- Test: `backend/tests/test_dashboard_uebersicht.py`

### Warum: Das Frontend braucht die `id` des `email_import_log`-Eintrags um direkt zur E-Mail-Detail-Seite zu navigieren.

- [ ] **Step 1.1: Failing test schreiben**

In `backend/tests/test_dashboard_uebersicht.py` — neuen Test am Ende der Klasse `TestDashboardUebersicht` hinzufügen:

```python
def test_nachrichten_neu_entries_haben_log_id(self):
    """Jeder Eintrag in nachrichten-neu muss ein log_id-Feld haben."""
    import backend.db.database as db_mod
    from backend.db.database import get_connection
    # Testdaten anlegen: Akte + email_import_log-Eintrag
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, status) VALUES (?, ?)",
            ("99/99", "offen")
        )
        conn.execute(
            """INSERT OR IGNORE INTO email_import_log
               (betreff, absender, empfangen_am, akte_id, status, email_typ)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("Testbetreff", "test@rv.de", "2026-06-12 10:00:00", "99/99", "zugeordnet", "sonstiges")
        )
        conn.commit()

    headers = self._auth_header()
    resp = self.client.get("/dashboard/nachrichten-neu", headers=headers)
    self.assertEqual(resp.status_code, 200)
    data = resp.get_json()
    eintraege = data["eintraege"]
    self.assertTrue(len(eintraege) > 0, "Mindestens ein Eintrag erwartet")
    for e in eintraege:
        self.assertIn("log_id", e, f"log_id fehlt in Eintrag: {e}")
        self.assertIsNotNone(e["log_id"])
```

- [ ] **Step 1.2: Test ausführen – muss FAIL sein**

```
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten"
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_nachrichten_neu_entries_haben_log_id -v
```

Erwartetes Ergebnis: `FAILED` – `AssertionError: log_id fehlt in Eintrag`

- [ ] **Step 1.3: `_lade_nachrichten_neu` anpassen**

In `backend/routers/dashboard_routes.py`, Funktion `_lade_nachrichten_neu` (Zeile 334):

```python
def _lade_nachrichten_neu(conn):
    """
    Letzte 20 E-Mails aus email_import_log, neueste zuerst.
    Nur Mails mit bekannter Akte.
    """
    rows = conn.execute("""
        SELECT
            e.id          AS log_id,
            a.az          AS az,
            e.absender,
            e.betreff,
            e.empfangen_am AS datum,
            'email'        AS kanal
        FROM email_import_log e
        JOIN unfallakte a ON a.az = e.akte_id
        ORDER BY e.empfangen_am DESC
        LIMIT 20
    """).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 1.4: Test ausführen – muss PASS sein**

```
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_nachrichten_neu_entries_haben_log_id -v
```

Erwartetes Ergebnis: `PASSED`

- [ ] **Step 1.5: Alle Dashboard-Tests grün**

```
python -m pytest backend/tests/test_dashboard_uebersicht.py -v
```

Erwartetes Ergebnis: Alle Tests `PASSED`

- [ ] **Step 1.6: Commit**

```bash
git add backend/routers/dashboard_routes.py backend/tests/test_dashboard_uebersicht.py
git commit -m "feat(api): nachrichten-neu liefert log_id fuer E-Mail-Detail-Navigation"
```

---

## Task 2: Backend – Migration 42 + `.eml`-Dateityp-Fix

**Files:**
- Modify: `backend/db/schema_manager.py`
- Modify: `backend/email_import/import_service.py:702-716`

### Warum: `.eml`-Dateien werden aktuell mit `dateityp='docx'` gespeichert – ein Workaround. DokumenteSection soll sie über `dokumentenklasse='email'` identifizieren.

- [ ] **Step 2.1: Migration 42 in MIGRATIONS-Dict eintragen**

In `backend/db/schema_manager.py`, im `MIGRATIONS`-Dict nach Zeile 295 (`41: ...`) eintragen:

```python
    42: "-- migration_42_eml_dateityp",  # Handled by _run_migration_42
```

- [ ] **Step 2.2: `_run_migration_42` Funktion hinzufügen**

In `backend/db/schema_manager.py`, nach der `_run_migration_4`-Funktion (vor `create_schema`):

```python
def _run_migration_42(conn: sqlite3.Connection) -> None:
    """Korrigiert dateityp für .eml-Dateien: 'docx' → 'sonstiges', dokumentenklasse → 'email'."""
    conn.execute("""
        UPDATE dokumente
        SET dateityp = 'sonstiges',
            dokumentenklasse = 'email'
        WHERE dateiname LIKE '%.eml'
          AND dateityp = 'docx'
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (42, "Migration 42 – .eml dateityp sonstiges + dokumentenklasse email"),
    )
    logger.info("Migration 42: .eml-Zeilen korrigiert.")
```

- [ ] **Step 2.3: Migration 42 in `run_migrations` einbinden**

In `backend/db/schema_manager.py`, in der `run_migrations`-Funktion, nach dem letzten `elif version == 41:` Block die neue Verzweigung hinzufügen:

```python
            elif version == 42:
                _run_migration_42(conn)
```

- [ ] **Step 2.4: `CHECK`-Constraint in `schema.py` prüfen und `.eml`-Handling absichern**

In `backend/db/schema.py`, Zeile 217-218:
```sql
dateityp        TEXT    NOT NULL DEFAULT 'pdf'
                CHECK(dateityp IN ('pdf', 'docx', 'jpg', 'png')),
```

`'sonstiges'` fehlt in der CHECK-Constraint. Das betrifft nur neue Tabellen (bestehende DB wird durch Migration 42 aktualisiert, aber der CHECK gilt erst bei neuen Inserts). Die Constraint muss erweitert werden:

```python
# In backend/db/schema.py, Zeile 217-218 ändern:
    dateityp        TEXT    NOT NULL DEFAULT 'pdf'
                    CHECK(dateityp IN ('pdf', 'docx', 'jpg', 'png', 'sonstiges')),
```

- [ ] **Step 2.5: `import_service.py` – `.eml`-Registrierung korrigieren**

In `backend/email_import/import_service.py`, Zeile ~707-713 (die EML-Selbstregistrierung):

**Alt:**
```python
            dok = registriere_dokument(
                akte_id      = akte_id,
                typ          = "sonstiges",
                dateiname    = eml_dateiname,
                dateipfad    = eml_pfad,
                bearbeiter_id= bearbeiter_id,
                dateityp     = "docx",
                dateigroesse = _Path(eml_pfad).stat().st_size,
            )
```

**Neu:**
```python
            dok = registriere_dokument(
                akte_id         = akte_id,
                typ             = "sonstiges",
                dateiname       = eml_dateiname,
                dateipfad       = eml_pfad,
                bearbeiter_id   = bearbeiter_id,
                dateityp        = "sonstiges",
                dateigroesse    = _Path(eml_pfad).stat().st_size,
                dokumentenklasse= "email",
            )
```

Prüfen ob `registriere_dokument` einen `dokumentenklasse`-Parameter akzeptiert. Falls nicht, direkt nach dem `registriere_dokument`-Aufruf ein UPDATE ausführen:

```python
            # Falls registriere_dokument kein dokumentenklasse-Param kennt:
            from ..db.database import get_connection as _get_conn
            with _get_conn() as _c:
                _c.execute(
                    "UPDATE dokumente SET dokumentenklasse = 'email' WHERE id = ?",
                    (dok.id,)
                )
```

- [ ] **Step 2.6: `registriere_dokument` Signatur prüfen**

```
grep -n "def registriere_dokument" backend/models/dokument.py
```

Falls `dokumentenklasse` kein Parameter ist: den direkten UPDATE-Ansatz aus Step 2.5 verwenden. Falls doch vorhanden: direkt als Parameter übergeben.

- [ ] **Step 2.7: Manuell testen – Migration läuft durch**

```
python -c "
import os; os.environ['DB_PATH'] = 'test_mig42.db'
from backend.db.schema_manager import create_schema, run_migrations
create_schema(); run_migrations()
from backend.db.database import get_connection
with get_connection() as c:
    v = c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0]
    print('Schema-Version:', v)
os.remove('test_mig42.db')
"
```

Erwartetes Ergebnis: `Schema-Version: 42`

- [ ] **Step 2.8: Commit**

```bash
git add backend/db/schema_manager.py backend/db/schema.py backend/email_import/import_service.py
git commit -m "feat(db): Migration 42 – .eml dateityp sonstiges + dokumentenklasse email"
```

---

## Task 3: Frontend api.js – `emailImport.inAkte` mit `erzwingen`

**Files:**
- Modify: `frontend/src/api.js:393`

### Warum: Der bestehende `inAkte`-Aufruf sendet kein JSON-Body. InAkteButton.jsx verwendet direktes `request()`. Beides soll konsolidiert werden.

- [ ] **Step 3.1: `emailImport.inAkte` in api.js anpassen**

In `frontend/src/api.js`, Zeile 393 (aktuell: `inAkte: (logId) => request(...)`):

**Alt:**
```javascript
  inAkte:     (logId) => request(`/email/import/log/${logId}/in-akte`, { method: 'POST' }),
```

**Neu:**
```javascript
  inAkte: (logId, erzwingen = false) =>
    request(`/email/import/log/${logId}/in-akte`, {
      method: 'POST',
      body: JSON.stringify({ erzwingen }),
    }),
```

- [ ] **Step 3.2: Manuell verifizieren – kein Syntax-Fehler**

```
node -e "import('./frontend/src/api.js').then(() => console.log('OK')).catch(e => console.error(e))"
```

Oder einfach: Frontend starten und schauen ob keine Konsolen-Fehler auftreten.

- [ ] **Step 3.3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(api): emailImport.inAkte unterstuetzt erzwingen-Parameter"
```

---

## Task 4: Frontend InAkteButton.jsx – nutzt `emailImport.inAkte`

**Files:**
- Modify: `frontend/src/views/email_import/components/InAkteButton.jsx`

### Warum: InAkteButton baut aktuell seinen Request manuell. Es soll die zentrale API-Funktion nutzen.

- [ ] **Step 4.1: Import und doImport umschreiben**

Komplette neue Version von `InAkteButton.jsx`:

```jsx
import React, { useState } from "react";
import T from "../../../config/theme.js";
import Ic from "../../../config/icons.jsx";
import { emailImport as apiEmail } from "../../../api.js";

function InAkteButton({ entry: e, onImportiert, onOpenAkte }) {
  const [laedt, setLaedt]             = useState(false);
  const [fehler, setFehler]           = useState(null);
  const [bestaetigen, setBestaetigen] = useState(false);

  if (!e.akte_az) return null;

  const doImport = async (erzwingen = false) => {
    setLaedt(true); setFehler(null); setBestaetigen(false);
    try {
      const res = await apiEmail.inAkte(e.id, erzwingen);
      if (res?.ok) {
        onImportiert(res);
        if (onOpenAkte) onOpenAkte(e);
      } else {
        setFehler(res?.fehler || "Unbekannter Fehler");
      }
    } catch (err) {
      setFehler(err?.message || "Fehler beim Import");
    } finally {
      setLaedt(false);
    }
  };

  if (e.in_akte_importiert) {
    return (
      <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
        <div style={{ display:"flex", alignItems:"center", gap:7,
          background:T.greenBg, border:`1px solid ${T.green}33`,
          borderRadius:7, padding:"6px 12px", fontFamily:"'Figtree',sans-serif",
          fontSize:"0.875rem", color:T.green }}>
          {Ic.check}
          <span style={{ flex:1 }}>In Akte importiert{e.in_akte_importiert_am ? ` · ${e.in_akte_importiert_am}` : ""}</span>
          <button onClick={() => setBestaetigen(true)} disabled={laedt}
            style={{ background:"none", border:`1px solid ${T.green}55`, borderRadius:5,
              padding:"2px 9px", fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
              color:T.green, cursor:"pointer", flexShrink:0 }}>
            ↺ Erneut
          </button>
        </div>
        {bestaetigen && (
          <div style={{ background:T.amberBg, border:`1px solid ${T.amber}44`,
            borderRadius:7, padding:"10px 12px", fontFamily:"'Figtree',sans-serif",
            fontSize:"0.855rem", color:T.textMid }}>
            <div style={{ fontWeight:600, marginBottom:6, color:T.amber }}>
              ⚠ Bereits importiert – erneut importieren?
            </div>
            <div style={{ marginBottom:10, fontSize:"0.835rem", color:T.textMuted }}>
              Anhänge und E-Mail-Datei werden erneut in den Dokumenten-Reiter der Akte gespeichert.
            </div>
            <div style={{ display:"flex", gap:8 }}>
              <button onClick={() => doImport(true)} disabled={laedt}
                style={{ padding:"5px 14px", background:T.amber, color:T.white,
                  border:"none", borderRadius:6, fontFamily:"'Figtree',sans-serif",
                  fontSize:"0.855rem", fontWeight:600, cursor:"pointer" }}>
                {laedt ? "Wird importiert …" : "Ja, erneut importieren"}
              </button>
              <button onClick={() => setBestaetigen(false)}
                style={{ padding:"5px 12px", background:"none", color:T.textMuted,
                  border:`1px solid ${T.border}`, borderRadius:6,
                  fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem", cursor:"pointer" }}>
                Abbrechen
              </button>
            </div>
          </div>
        )}
        {fehler && (
          <div style={{ fontSize:"0.845rem", color:T.red, fontFamily:"'Figtree',sans-serif" }}>{fehler}</div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
      <button onClick={() => doImport(false)} disabled={laedt}
        style={{ display:"flex", alignItems:"center", gap:7, padding:"6px 14px",
          background: laedt ? T.navyMid : T.navy, color:T.white,
          border:"none", borderRadius:7, fontFamily:"'Figtree',sans-serif",
          fontSize:"0.875rem", fontWeight:600,
          cursor: laedt ? "default" : "pointer", transition:"background 0.15s" }}>
        {laedt
          ? <><div style={{ width:12, height:12, border:"2px solid rgba(255,255,255,0.3)",
              borderTopColor:"white", borderRadius:"50%",
              animation:"spin 0.7s linear infinite" }}/> Wird importiert …</>
          : <>{Ic.attach} In Akte importieren</>}
      </button>
      {fehler && (
        <div style={{ fontSize:"0.845rem", color:T.red, fontFamily:"'Figtree',sans-serif" }}>{fehler}</div>
      )}
    </div>
  );
}

export default InAkteButton;
```

- [ ] **Step 4.2: Commit**

```bash
git add frontend/src/views/email_import/components/InAkteButton.jsx
git commit -m "refactor(email): InAkteButton nutzt emailImport.inAkte aus api.js"
```

---

## Task 5: Frontend – `EmailDetailView.jsx` (neue Komponente)

**Files:**
- Create: `frontend/src/views/email_import/EmailDetailView.jsx`

### Warum: Kernstück des Redesigns – zeigt eine E-Mail mit 2-spaltiger Layout (Metadaten + PDF-Vorschau).

- [ ] **Step 5.1: Datei anlegen**

`frontend/src/views/email_import/EmailDetailView.jsx`:

```jsx
import React, { useState, useEffect, useRef } from "react";
import T from "../../config/theme.js";
import Ic from "../../config/icons.jsx";
import { EMAIL_TYP_LABELS } from "../../config/constants.js";
import { emailImport as apiEmail, tokenStore, API_BASE } from "../../api.js";
import InAkteButton from "./components/InAkteButton.jsx";

function EmailDetailView({ entry: e, onBack, onOpenAkte, onInAkteImportiert }) {
  const [meta, setMeta]               = useState(null);
  const [metaLaedt, setMetaLaedt]     = useState(true);
  const [aktiverIdx, setAktiverIdx]   = useState(null);
  const [vorschauUrl, setVorschauUrl] = useState(null);
  const [vorschauLaedt, setVorschauLaedt] = useState(false);
  const [lokalerEintrag, setLokalerEintrag] = useState(e);
  const prevUrlRef = useRef(null);

  useEffect(() => {
    setLokalerEintrag(e);
    setMeta(null); setMetaLaedt(true);
    setAktiverIdx(null); setVorschauUrl(null);
  }, [e.id]);

  useEffect(() => {
    apiEmail.meta(lokalerEintrag.id)
      .then(m => setMeta(m))
      .catch(() => setMeta({ anhaenge: [], body_text: "" }))
      .finally(() => setMetaLaedt(false));
  }, [lokalerEintrag.id]);

  useEffect(() => () => { if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current); }, []);

  const oeffneAnhangVorschau = async (anhang) => {
    if (aktiverIdx === anhang.index) {
      setAktiverIdx(null);
      if (vorschauUrl) { URL.revokeObjectURL(vorschauUrl); prevUrlRef.current = null; }
      setVorschauUrl(null);
      return;
    }
    setAktiverIdx(anhang.index);
    setVorschauLaedt(true);
    try {
      const token = tokenStore.getAccess();
      const res = await fetch(
        `${API_BASE}/email/import/log/${lokalerEintrag.id}/anhang/${anhang.index}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (!res.ok) throw new Error("Anhang nicht verfügbar");
      const blob = await res.blob();
      if (prevUrlRef.current) URL.revokeObjectURL(prevUrlRef.current);
      const url = URL.createObjectURL(blob);
      prevUrlRef.current = url;
      setVorschauUrl(url);
    } catch {
      setVorschauUrl(null);
    } finally {
      setVorschauLaedt(false);
    }
  };

  const handleInAkteImportiert = (res) => {
    setLokalerEintrag(prev => ({
      ...prev,
      in_akte_importiert: 1,
      in_akte_importiert_am: res?.importiert_am,
    }));
    if (onInAkteImportiert) onInAkteImportiert(lokalerEintrag.id, res);
  };

  const et = lokalerEintrag.email_typ && lokalerEintrag.email_typ !== "sonstiges"
    ? EMAIL_TYP_LABELS[lokalerEintrag.email_typ] : null;

  return (
    <div style={{ display:"flex", height:"100%", overflow:"hidden" }}>

      {/* ── Linke Spalte (fix 380px) ──────────────────────────── */}
      <div style={{ width:380, flexShrink:0, borderRight:`1px solid ${T.border}`,
        overflowY:"auto", display:"flex", flexDirection:"column" }}>

        {/* Navigation */}
        <div style={{ padding:"0.85rem 1.25rem", borderBottom:`1px solid ${T.border}`,
          display:"flex", alignItems:"center", gap:10, flexWrap:"wrap", flexShrink:0 }}>
          <button onClick={onBack}
            style={{ display:"flex", alignItems:"center", gap:5, background:"none",
              border:"none", cursor:"pointer", fontFamily:"'Figtree',sans-serif",
              fontSize:"0.895rem", color:T.textMid, padding:"4px 0" }}>
            ← Zurück zum Stream
          </button>
          {lokalerEintrag.akte_az && (
            <button onClick={() => onOpenAkte(lokalerEintrag)}
              style={{ display:"flex", alignItems:"center", gap:5, background:"none",
                border:`1px solid ${T.navy}`, borderRadius:6, cursor:"pointer",
                fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem",
                color:T.navy, padding:"4px 10px", marginLeft:"auto" }}>
              {Ic.akte} Akte {lokalerEintrag.akte_az} öffnen
            </button>
          )}
        </div>

        {/* Betreff */}
        <div style={{ padding:"1.25rem 1.25rem 0.75rem",
          fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"1.1rem",
          fontWeight:700, color:T.navy, lineHeight:1.3 }}>
          {lokalerEintrag.betreff || <span style={{ color:T.textMuted, fontStyle:"italic" }}>(kein Betreff)</span>}
        </div>

        {/* Metadaten */}
        <div style={{ padding:"0 1.25rem 1rem", display:"flex", flexDirection:"column", gap:6 }}>
          {[
            ["Von",   `${lokalerEintrag.von_name || ""} ${lokalerEintrag.absender ? `<${lokalerEintrag.absender}>` : ""}`.trim() || lokalerEintrag.absender || "–"],
            ["Akte",  lokalerEintrag.akte_az ? `${lokalerEintrag.akte_az} ✓ Zugeordnet` : "Nicht zugeordnet"],
            ["Datum", lokalerEintrag.empfangen_am ? String(lokalerEintrag.empfangen_am).slice(0, 16) : "–"],
            ["Typ",   et ? et.label : "Sonstiges"],
          ].map(([l, v]) => (
            <div key={l} style={{ display:"flex", gap:10, alignItems:"baseline" }}>
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem",
                color:T.textMuted, width:44, flexShrink:0 }}>{l}</span>
              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
                color: l === "Akte" && lokalerEintrag.akte_az ? T.green : T.text,
                fontWeight: l === "Akte" && lokalerEintrag.akte_az ? 600 : 400 }}>{v}</span>
            </div>
          ))}
        </div>

        <div style={{ margin:"0 1.25rem", borderTop:`1px solid ${T.border}` }} />

        {/* Anhänge */}
        {(lokalerEintrag.anhaenge_anzahl || 0) > 0 && (
          <div style={{ padding:"0.85rem 1.25rem" }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", fontWeight:700,
              color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:8 }}>
              Anhänge ({lokalerEintrag.anhaenge_anzahl})
            </div>
            {metaLaedt ? (
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.textMuted }}>Lade …</div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
                {(meta?.anhaenge || []).map(anh => {
                  const isPdf = (anh.ext === "pdf") || (anh.name || "").toLowerCase().endsWith(".pdf");
                  const istAktiv = aktiverIdx === anh.index;
                  return (
                    <div key={anh.index}
                      style={{ display:"flex", alignItems:"center", gap:8,
                        background: istAktiv ? T.accentPale : T.surface,
                        border: `1.5px solid ${istAktiv ? T.accent : T.border}`,
                        borderRadius:7, padding:"6px 10px", cursor:"pointer" }}
                      onClick={() => oeffneAnhangVorschau(anh)}>
                      <span style={{ color: isPdf ? T.red : T.blue, display:"flex", flexShrink:0 }}>{isPdf ? Ic.pdf : Ic.attach}</span>
                      <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                        color:T.text, flex:1, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {anh.name || `Anhang ${anh.index + 1}`}
                      </span>
                      <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.8rem",
                        color: istAktiv ? T.accent : T.textMuted, flexShrink:0 }}>
                        {istAktiv ? "▼ Vorschau" : "▶ Vorschau"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        <div style={{ margin:"0 1.25rem", borderTop:`1px solid ${T.border}` }} />

        {/* Import-Vorschlag */}
        <div style={{ padding:"0.85rem 1.25rem", flex:1 }}>
          {lokalerEintrag.akte_az && !lokalerEintrag.in_akte_importiert ? (
            <div style={{ background:T.greenBg, border:`1.5px solid ${T.green}44`,
              borderRadius:9, padding:"0.85rem 1rem" }}>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                fontWeight:700, color:T.green, marginBottom:4 }}>
                📥 In Akte {lokalerEintrag.akte_az} importieren?
              </div>
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.835rem",
                color:T.textMid, marginBottom:10 }}>
                {(lokalerEintrag.anhaenge_anzahl || 0) > 0
                  ? `${lokalerEintrag.anhaenge_anzahl} Anhang${lokalerEintrag.anhaenge_anzahl > 1 ? "hänge" : ""} + E-Mail-Text`
                  : "E-Mail-Text"}
              </div>
              <InAkteButton
                entry={lokalerEintrag}
                onImportiert={handleInAkteImportiert}
                onOpenAkte={null}
              />
            </div>
          ) : lokalerEintrag.in_akte_importiert ? (
            <div style={{ display:"flex", alignItems:"center", gap:7,
              background:T.greenBg, border:`1px solid ${T.green}33`,
              borderRadius:7, padding:"8px 12px",
              fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem", color:T.green }}>
              {Ic.check}
              <span>In Akte importiert{lokalerEintrag.in_akte_importiert_am ? ` · ${lokalerEintrag.in_akte_importiert_am}` : ""}</span>
            </div>
          ) : (
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
              color:T.textMuted, fontStyle:"italic" }}>
              E-Mail noch keiner Akte zugeordnet
            </div>
          )}
        </div>
      </div>

      {/* ── Rechtes Vorschau-Panel ────────────────────────────── */}
      <div style={{ flex:1, overflow:"hidden", display:"flex", flexDirection:"column" }}>
        {aktiverIdx !== null ? (
          vorschauLaedt ? (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center",
              fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.textMuted }}>
              <div style={{ width:20, height:20, border:`2px solid ${T.border}`,
                borderTopColor:T.navy, borderRadius:"50%", animation:"spin 0.7s linear infinite",
                marginRight:10 }} />
              Lade Vorschau …
            </div>
          ) : vorschauUrl ? (
            <>
              <div style={{ padding:"8px 14px", borderBottom:`1px solid ${T.border}`,
                display:"flex", alignItems:"center", gap:10, flexShrink:0,
                background:T.white, fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}>
                <span style={{ color:T.textMid }}>
                  {(meta?.anhaenge || []).find(a => a.index === aktiverIdx)?.name || `Anhang ${aktiverIdx + 1}`}
                </span>
                <button onClick={() => apiEmail.anhangOeffnen(lokalerEintrag.id, aktiverIdx,
                    (meta?.anhaenge || []).find(a => a.index === aktiverIdx)?.name || "anhang")}
                  style={{ marginLeft:"auto", background:"none", border:`1px solid ${T.border}`,
                    borderRadius:5, padding:"3px 10px", cursor:"pointer",
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.835rem", color:T.textMid }}>
                  ↗ Vollbild
                </button>
              </div>
              <iframe src={vorschauUrl} title="PDF-Vorschau"
                style={{ flex:1, border:"none", width:"100%", height:"100%" }} />
            </>
          ) : (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center",
              fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.red }}>
              Anhang konnte nicht geladen werden.
            </div>
          )
        ) : (
          <div style={{ flex:1, overflowY:"auto", padding:"1.5rem" }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.78rem", fontWeight:700,
              color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:10 }}>
              E-Mail-Text
            </div>
            {metaLaedt ? (
              <div style={{ color:T.textMuted, fontSize:"0.895rem", fontFamily:"'Figtree',sans-serif" }}>Lade …</div>
            ) : (
              <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.895rem",
                color:T.textMid, whiteSpace:"pre-wrap", lineHeight:1.6 }}>
                {meta?.body_text || <span style={{ color:T.textMuted, fontStyle:"italic" }}>(kein Text)</span>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default EmailDetailView;
```

- [ ] **Step 5.2: Commit**

```bash
git add frontend/src/views/email_import/EmailDetailView.jsx
git commit -m "feat(ui): EmailDetailView – 2-spaltige E-Mail-Detail-Seite mit PDF-Vorschau"
```

---

## Task 6: Frontend – EmailKarte.jsx – „▶ E-Mail öffnen"-Button

**Files:**
- Modify: `frontend/src/views/email_import/components/EmailKarte.jsx`

### Warum: Im Stream soll jede E-Mail-Karte einen Button haben, der direkt zur Detail-Seite führt.

- [ ] **Step 6.1: `onOpenEmail` Prop hinzufügen**

In `frontend/src/views/email_import/components/EmailKarte.jsx`, Zeile 10:

**Alt:**
```jsx
function EmailKarte({ entry: e, seite, onOpenAkte, zuordnungState: zs,
                      onOeffneZuordnung, onSchliessZuordnung, onSucheAkten, onZuordnen,
                      onInAkteImportiert, letzter }) {
```

**Neu:**
```jsx
function EmailKarte({ entry: e, seite, onOpenAkte, onOpenEmail, zuordnungState: zs,
                      onOeffneZuordnung, onSchliessZuordnung, onSucheAkten, onZuordnen,
                      onInAkteImportiert, letzter }) {
```

- [ ] **Step 6.2: „▶ E-Mail öffnen"-Button in den Card-Header einfügen**

Im Header-Bereich der Karte (die `<div style={{ display:"flex", alignItems:"flex-start", gap:10 }}>` Zeile, ca. Zeile 62), nach dem Datums-Span und vor dem Chevron-SVG den Button hinzufügen. Das Ende der Header-Zeile sieht aktuell so aus:

```jsx
              <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.825rem",
                color:T.textMuted, marginLeft:"auto", flexShrink:0, whiteSpace:"nowrap" }}>
                {e.empfangen_am ? String(e.empfangen_am).slice(0,16) : ""}
              </span>
            </div>
```

**Neu – nach dem Datums-Span und vor dem schließenden `</div>` einfügen:**

```jsx
              <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.825rem",
                color:T.textMuted, marginLeft:"auto", flexShrink:0, whiteSpace:"nowrap" }}>
                {e.empfangen_am ? String(e.empfangen_am).slice(0,16) : ""}
              </span>
              {onOpenEmail && (
                <button
                  onClick={ev => { ev.stopPropagation(); onOpenEmail(e); }}
                  style={{ display:"flex", alignItems:"center", gap:4, padding:"3px 9px",
                    background:T.navy, color:T.white, border:"none", borderRadius:5,
                    fontFamily:"'Figtree',sans-serif", fontSize:"0.795rem",
                    fontWeight:600, cursor:"pointer", flexShrink:0 }}>
                  ▶ öffnen
                </button>
              )}
```

- [ ] **Step 6.3: Commit**

```bash
git add frontend/src/views/email_import/components/EmailKarte.jsx
git commit -m "feat(ui): EmailKarte bekommt ▶ E-Mail-öffnen-Button"
```

---

## Task 7: Frontend – UnfallEmailView.jsx – `geöffneteEmail` State

**Files:**
- Modify: `frontend/src/views/email_import/UnfallEmailView.jsx`

### Warum: UnfallEmailView steuert, ob der Stream oder die Detail-Seite gezeigt wird. Außerdem muss es auf `initialEmailId` reagieren.

- [ ] **Step 7.1: Import für EmailDetailView hinzufügen**

In `frontend/src/views/email_import/UnfallEmailView.jsx`, Zeile 9 (nach dem letzten Import):

```jsx
import EmailDetailView from "./EmailDetailView.jsx";
```

Außerdem `useRef` zu den React-Imports hinzufügen:

```jsx
import React, { useState, useEffect, useCallback, useRef } from "react";
```

- [ ] **Step 7.2: Props und State erweitern**

Zeile 48 – Signatur ändern:

**Alt:**
```jsx
function UnfallEmailView({ onOpenAkte, dispatch }) {
```

**Neu:**
```jsx
function UnfallEmailView({ onOpenAkte, dispatch, initialEmailId }) {
```

Nach den bestehenden State-Deklarationen (ca. Zeile 63, nach `laedt`) zwei neue States und ein Ref hinzufügen:

```jsx
  const [geoeffneteEmail, setGeoeffneteEmail] = useState(null);
  const letzteInitialId = useRef(null);
```

- [ ] **Step 7.3: `useEffect` für `initialEmailId` hinzufügen**

Nach dem bestehenden `useEffect` (der Log + Status lädt, ca. Zeile 84-95) einen neuen Effect hinzufügen:

```jsx
  useEffect(() => {
    if (!initialEmailId || initialEmailId === letzteInitialId.current) return;
    if (log.length === 0) return;
    const entry = log.find(e => e.id === initialEmailId);
    if (entry) {
      setGeoeffneteEmail(entry);
      letzteInitialId.current = initialEmailId;
    }
  }, [initialEmailId, log]);
```

- [ ] **Step 7.4: `onOpenEmail`-Handler definieren**

Nach dem `handleOpenAkte`-Handler (ca. Zeile 196):

```jsx
  const handleOpenEmail = useCallback((entry) => {
    setGeoeffneteEmail(entry);
  }, []);

  const handleEmailZurueck = useCallback(() => {
    setGeoeffneteEmail(null);
  }, []);
```

- [ ] **Step 7.5: `onInAkteImportiert` im Detail aktualisieren**

Die bestehende `onInAkteImportiert`-Funktion (Zeile 65) aktualisiert den Log-Eintrag. Wenn eine E-Mail gerade in `geoeffneteEmail` gezeigt wird, muss auch dieser Eintrag aktualisiert werden:

```jsx
  const onInAkteImportiert = useCallback((logId, res) => {
    setLog(prev => prev.map(e => e.id === logId
      ? { ...e, in_akte_importiert: 1, in_akte_importiert_am: res?.importiert_am }
      : e
    ));
    setGeoeffneteEmail(prev => prev?.id === logId
      ? { ...prev, in_akte_importiert: 1, in_akte_importiert_am: res?.importiert_am }
      : prev
    );
    const eintrag = log.find(e => e.id === logId);
    const akteRaw = eintrag?.akte_az || eintrag?.akte_id;
    const akteId  = akteRaw ? akteRaw.replace(/[A-Z]{2,3}$/i, "").trim() : null;
    if (akteId && dispatch) {
      request(`/akten/${akteId}`)
        .then(data => {
          if (data?.dokumente) {
            dispatch({ type: "SET_DOKUMENTE", akteId, dokumente: data.dokumente });
          }
        })
        .catch(() => {});
    }
  }, [log, dispatch]);
```

- [ ] **Step 7.6: `onOpenEmail` an alle `EmailKarte`-Instanzen übergeben**

Im Return der Komponente, alle `<EmailKarte ... />` Aufrufe um `onOpenEmail={handleOpenEmail}` ergänzen. Es gibt zwei Stellen:

Zeile ~338 (in der Aktionspflichtig-Sektion):
```jsx
                    <EmailKarte
                      key={e.id ?? i}
                      entry={e}
                      seite="nicht_zugeordnet"
                      onOpenAkte={handleOpenAkte}
                      onOpenEmail={handleOpenEmail}
                      zuordnungState={zuordnungState[e.id]}
                      ...
```

Zeile ~605 (im Stream):
```jsx
                  <EmailKarte
                    key={e.id ?? i}
                    entry={e}
                    seite={e.status === "zugeordnet" ? "zugeordnet" : "nicht_zugeordnet"}
                    onOpenAkte={handleOpenAkte}
                    onOpenEmail={handleOpenEmail}
                    zuordnungState={zuordnungState[e.id]}
                    ...
```

- [ ] **Step 7.7: `EmailDetailView` rendern wenn `geoeffneteEmail` gesetzt**

Am Anfang des `return`-Statements (direkt nach `<>` und dem `Toast`), vor dem Aktionszeilen-Block:

```jsx
  return (
    <>
      {toast && <Toast msg={toast} onDone={() => setToast("")}/>}

      {geoeffneteEmail ? (
        <EmailDetailView
          entry={geoeffneteEmail}
          onBack={handleEmailZurueck}
          onOpenAkte={handleOpenAkte}
          onInAkteImportiert={onInAkteImportiert}
        />
      ) : (
        <>
          {/* Aktionszeile: Verbindungsstatus + Import-Button */}
          ...rest of the original return...
        </>
      )}
    </>
  );
```

Der gesamte bisherige Inhalt des `return` (von der Aktionszeile bis zum IMAP-Dialog) wird in den `else`-Zweig (das zweite `<>...</>`) eingeschlossen.

- [ ] **Step 7.8: Commit**

```bash
git add frontend/src/views/email_import/UnfallEmailView.jsx
git commit -m "feat(ui): UnfallEmailView – geöffneteEmail State, EmailDetailView Integration"
```

---

## Task 8: Frontend – EmailImportView.jsx – `initialEmailId` durchreichen

**Files:**
- Modify: `frontend/src/views/EmailImportView.jsx`

- [ ] **Step 8.1: Prop hinzufügen und weiterreichen**

In `frontend/src/views/EmailImportView.jsx`, Zeile 13:

**Alt:**
```jsx
function EmailImportView({ onOpenAkte, dispatch }) {
```

**Neu:**
```jsx
function EmailImportView({ onOpenAkte, dispatch, initialEmailId }) {
```

Zeile 61:

**Alt:**
```jsx
        {tab === "unfall"   && <UnfallEmailView  onOpenAkte={onOpenAkte} dispatch={dispatch} />}
```

**Neu:**
```jsx
        {tab === "unfall"   && <UnfallEmailView  onOpenAkte={onOpenAkte} dispatch={dispatch} initialEmailId={initialEmailId} />}
```

- [ ] **Step 8.2: Commit**

```bash
git add frontend/src/views/EmailImportView.jsx
git commit -m "feat(ui): EmailImportView reicht initialEmailId an UnfallEmailView weiter"
```

---

## Task 9: Frontend – App.jsx – `openEmail` Handler

**Files:**
- Modify: `frontend/src/App.jsx`

### Warum: Das Action Board muss eine E-Mail öffnen können, ohne selbst den Navigation-State zu kennen.

- [ ] **Step 9.1: `pendingEmailId`-State hinzufügen**

In `frontend/src/App.jsx`, in `AppShell` nach den bestehenden States (ca. Zeile 97):

```jsx
  const [pendingEmailId, setPendingEmailId] = useState(null);
```

- [ ] **Step 9.2: `openEmail` Handler definieren**

Nach dem `openAkte`-Handler (ca. Zeile 121):

```jsx
  const openEmail = useCallback(({ logId }) => {
    setActive("email-import");
    setPendingEmailId(logId);
  }, []);
```

- [ ] **Step 9.3: `initialEmailId` und `onOpenEmail` an die Views übergeben**

Zeile 238-241 (das View-Rendering), `ActionBoardView` und `EmailImportView` anpassen:

```jsx
            {active==="dashboard"        ? <ActionBoardView onOpenAkte={openAkte} onOpenEmail={openEmail} />
            : active==="statistiken"     ? <StatistikenView />
            : active==="aktensuche"      ? <AktensucheView onOpenAkte={openAkte} />
            : active==="email-import"    ? <EmailImportView onOpenAkte={openAkte} dispatch={dispatch} initialEmailId={pendingEmailId} />
```

- [ ] **Step 9.4: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(ui): App.jsx – openEmail Handler navigiert zum E-Mail-Import mit Ziel-ID"
```

---

## Task 10: Frontend – ActionBoardView.jsx – `NachrichtenSpalte` nutzt `onOpenEmail`

**Files:**
- Modify: `frontend/src/views/ActionBoardView.jsx`

- [ ] **Step 10.1: `onOpenEmail` Prop in `ActionBoardView` akzeptieren**

Zeile 301:

**Alt:**
```jsx
export default function ActionBoardView({ onOpenAkte }) {
```

**Neu:**
```jsx
export default function ActionBoardView({ onOpenAkte, onOpenEmail }) {
```

- [ ] **Step 10.2: `onOpenEmail` an `NachrichtenSpalte` übergeben**

Zeile 367:

**Alt:**
```jsx
          <NachrichtenSpalte nachrichten={nachrichten}                             onOpenAkte={oeffneAkte} />
```

**Neu:**
```jsx
          <NachrichtenSpalte nachrichten={nachrichten} onOpenAkte={oeffneAkte} onOpenEmail={onOpenEmail} />
```

- [ ] **Step 10.3: `NachrichtenSpalte` Signatur und Klick-Handler anpassen**

Zeile 142:

**Alt:**
```jsx
function NachrichtenSpalte({ nachrichten, onOpenAkte }) {
```

**Neu:**
```jsx
function NachrichtenSpalte({ nachrichten, onOpenAkte, onOpenEmail }) {
```

Zeile 177 (der onClick):

**Alt:**
```jsx
              onClick={() => onOpenAkte(m.az)}
```

**Neu:**
```jsx
              onClick={() => {
                if (onOpenEmail && m.log_id) {
                  onOpenEmail({ az: m.az, logId: m.log_id });
                } else {
                  onOpenAkte(m.az);
                }
              }}
```

- [ ] **Step 10.4: Commit**

```bash
git add frontend/src/views/ActionBoardView.jsx
git commit -m "feat(ui): ActionBoard NachrichtenSpalte öffnet E-Mail-Detail statt Akte"
```

---

## Task 11: Frontend – DokumenteSection.jsx – E-Mail-Gruppe

**Files:**
- Modify: `frontend/src/sections/DokumenteSection.jsx`

### Warum: E-Mails zur Akte sollen direkt in der DokumenteSection klappbar sichtbar sein, ohne in den E-Mail-Import-Bereich wechseln zu müssen.

- [ ] **Step 11.1: Import für `emailImport` hinzufügen**

In `frontend/src/sections/DokumenteSection.jsx`, Zeile 8-13 (Imports), `emailImport` aus api.js hinzufügen:

```jsx
import {
  dokumente as apiDokumente,
  eakte as apiEakte,
  belege as apiBelege,
  schaden as apiSchaden,
  emailImport as apiEmail,
  tokenStore,
  API_BASE,
} from "../api.js";
```

- [ ] **Step 11.2: State für E-Mail-Gruppe hinzufügen**

In `DokumenteSection` nach den bestehenden State-Deklarationen (ca. Zeile 50):

```jsx
  const [emailDoks, setEmailDoks]         = useState([]);
  const [emailGruppeGeladen, setEmailGruppeGeladen] = useState(false);
  const [emailExpanded, setEmailExpanded] = useState({});
  const [emailMeta, setEmailMeta]         = useState({});
```

- [ ] **Step 11.3: E-Mails beim Laden der DokumenteSection abrufen**

In DokumenteSection wird `akteId` als Prop übergeben. Nach dem letzten `useEffect` (oder in einem neuen) die E-Mails laden:

```jsx
  useEffect(() => {
    if (!akteId) return;
    apiEmail.log({ akte_id: akteId, limit: 50 })
      .then(d => { if (d?.log) setEmailDoks(d.log); })
      .catch(() => {})
      .finally(() => setEmailGruppeGeladen(true));
  }, [akteId]);
```

- [ ] **Step 11.4: E-Mail aufklappen + Meta laden**

Handler-Funktionen (als normale `const`-Funktionen im Komponenten-Body):

```jsx
  const toggleEmailExpand = async (id) => {
    const neuOffen = !emailExpanded[id];
    setEmailExpanded(prev => ({ ...prev, [id]: neuOffen }));
    if (neuOffen && !emailMeta[id]) {
      try {
        const meta = await apiEmail.meta(id);
        setEmailMeta(prev => ({ ...prev, [id]: meta }));
      } catch {
        setEmailMeta(prev => ({ ...prev, [id]: { anhaenge: [], body_text: "" } }));
      }
    }
  };

  const oeffneEmailAnhang = async (logId, index, name) => {
    try {
      await apiEmail.anhangOeffnen(logId, index, name);
    } catch {
      alert("Anhang konnte nicht geöffnet werden.");
    }
  };
```

- [ ] **Step 11.5: E-Mail-Gruppe ans Ende der DokumenteSection rendern**

In der `return`-Anweisung der DokumenteSection, nach der letzten bestehenden `<Card>` (dem Dokumente-Block), den folgenden Block hinzufügen – kurz vor dem abschließenden `</>` oder `</div>`:

```jsx
      {/* ── E-Mail-Gruppe ──────────────────────────────────────── */}
      {emailGruppeGeladen && emailDoks.length > 0 && (
        <Card style={{ marginTop:"1.25rem" }}>
          <CardHead title={`📧 E-Mails (${emailDoks.length})`} />
          {emailDoks.map((em, i) => {
            const istOffen = !!emailExpanded[em.id];
            const meta     = emailMeta[em.id];
            return (
              <div key={em.id} style={{ borderBottom: i < emailDoks.length - 1 ? `1px solid ${T.borderSoft}` : "none" }}>
                <div
                  onClick={() => toggleEmailExpand(em.id)}
                  style={{ display:"flex", alignItems:"center", gap:10,
                    padding:"10px 1.25rem", cursor:"pointer",
                    background: istOffen ? T.accentPale : "transparent",
                    transition:"background 0.1s" }}
                  onMouseEnter={ev => { if (!istOffen) ev.currentTarget.style.background = T.surface; }}
                  onMouseLeave={ev => { if (!istOffen) ev.currentTarget.style.background = "transparent"; }}>
                  <span style={{ color:T.blue, display:"flex", flexShrink:0 }}>📧</span>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.925rem",
                      fontWeight:500, color:T.text,
                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                      {em.von_name || em.absender || "Unbekannt"}
                      {em.betreff ? ` · ${em.betreff}` : ""}
                    </div>
                  </div>
                  <span style={{ fontFamily:"ui-monospace,monospace", fontSize:"0.8rem",
                    color:T.textMuted, flexShrink:0 }}>
                    {em.empfangen_am ? String(em.empfangen_am).slice(0, 10) : ""}
                    {(em.anhaenge_anzahl || 0) > 0 ? ` · ${em.anhaenge_anzahl} Anhang${em.anhaenge_anzahl > 1 ? "hänge" : ""}` : ""}
                  </span>
                  <svg viewBox="0 0 24 24" fill={T.textFaint}
                    style={{ width:13, height:13, flexShrink:0,
                      transform: istOffen ? "rotate(180deg)" : "none", transition:"transform 0.2s" }}>
                    <path d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/>
                  </svg>
                </div>
                {istOffen && (
                  <div style={{ padding:"0 1.25rem 12px 2.75rem",
                    background:T.accentPale, borderTop:`1px solid ${T.border}` }}>
                    {meta?.body_text ? (
                      <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem",
                        color:T.textMid, marginTop:10, marginBottom:10,
                        whiteSpace:"pre-wrap", maxHeight:120, overflowY:"auto",
                        background:T.white, border:`1px solid ${T.border}`,
                        borderRadius:6, padding:"8px 10px", lineHeight:1.5 }}>
                        {meta.body_text.slice(0, 400)}{meta.body_text.length > 400 ? " …" : ""}
                      </div>
                    ) : !meta ? (
                      <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.855rem",
                        color:T.textMuted, marginTop:10 }}>Lade …</div>
                    ) : null}
                    {(meta?.anhaenge || []).length > 0 && (
                      <div style={{ display:"flex", flexDirection:"column", gap:4, marginTop: meta?.body_text ? 0 : 10 }}>
                        {meta.anhaenge.map(anh => {
                          const isPdf = (anh.ext === "pdf") || (anh.name || "").toLowerCase().endsWith(".pdf");
                          return (
                            <div key={anh.index}
                              style={{ display:"flex", alignItems:"center", gap:8 }}>
                              <span style={{ color: isPdf ? T.red : T.blue, display:"flex", fontSize:"0.9rem", flexShrink:0 }}>
                                {isPdf ? Ic.pdf : Ic.attach}
                              </span>
                              <span style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem",
                                color:T.text, flex:1 }}>
                                {anh.name || `Anhang ${anh.index + 1}`}
                              </span>
                              <button
                                onClick={() => oeffneEmailAnhang(em.id, anh.index, anh.name || "anhang")}
                                style={{ background:"none", border:`1px solid ${T.border}`,
                                  borderRadius:5, padding:"2px 10px", cursor:"pointer",
                                  fontFamily:"'Figtree',sans-serif", fontSize:"0.815rem",
                                  color:T.textMid }}>
                                Öffnen
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </Card>
      )}
```

- [ ] **Step 11.6: Commit**

```bash
git add frontend/src/sections/DokumenteSection.jsx
git commit -m "feat(ui): DokumenteSection zeigt E-Mails zur Akte klappbar an"
```

---

## Verifikation (nach allen Tasks)

- [ ] **V1: Action Dashboard → E-Mail-Detail**
  1. App starten (`npm run dev` + Backend)
  2. Im Action Board auf eine E-Mail in der Nachrichten-Spalte klicken
  3. Erwartung: E-Mail-Import-View öffnet sich, EmailDetailView wird sofort angezeigt (nicht der Stream)

- [ ] **V2: Detail-Seite – Anhang-Vorschau**
  1. In der EmailDetailView auf einen PDF-Anhang klicken
  2. Erwartung: Rechtes Panel zeigt PDF-Vorschau inline; aktiver Anhang hat blauen Rahmen
  3. Erneut klicken → zurück zum E-Mail-Text

- [ ] **V3: In-Akte-Import aus Detail-Seite**
  1. In der EmailDetailView (E-Mail noch nicht importiert) auf „Jetzt importieren" klicken
  2. Erwartung: Grünes Badge „✓ In Akte importiert" erscheint; Vorschlag-Box verschwindet

- [ ] **V4: DokumenteSection – E-Mail-Gruppe**
  1. Eine Akte öffnen, die bereits importierte E-Mails hat
  2. In der DokumenteSection nach unten scrollen
  3. Erwartung: Gruppe „📧 E-Mails (N)" ist sichtbar; Klick klappt E-Mail auf; Anhänge öffnen im Tab

- [ ] **V5: Stream-Navigation**
  1. Im E-Mail-Stream auf „▶ öffnen" bei einer Karte klicken
  2. Erwartung: EmailDetailView öffnet sich; „← Zurück zum Stream" bringt zur Stream-Position zurück (kein Re-Fetch)

- [ ] **V6: Backend-Tests grün**
  ```
  python -m pytest backend/tests/test_dashboard_uebersicht.py -v
  ```

---

## Erfolgs-Kriterien (aus Spec)

1. ✅ Klick auf E-Mail im Action Dashboard → E-Mail-Detail-Seite, nicht Akte-Übersicht
2. ✅ Detail-Seite zeigt Text links, PDF-Vorschau rechts bei Anhang-Klick
3. ✅ „In Akte importieren" als prominenter grüner Vorschlag-Block
4. ✅ DokumenteSection zeigt E-Mails klappbar; Anhänge können geöffnet werden
5. ✅ Alle Navigationspfade haben funktionierenden Zurück-Button
6. ✅ Kein Seitenwechsel beim Aufklappen in DokumenteSection
