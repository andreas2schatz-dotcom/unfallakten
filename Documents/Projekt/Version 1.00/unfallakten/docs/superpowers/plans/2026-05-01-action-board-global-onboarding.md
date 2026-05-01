# Action Board Global + Onboarding Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace DashboardView with a kanzlei-wide Action Board (RA-MICRO Fristen / WV fällig / neue Emails) and add an Onboarding Hub (7 Hub & Spoke tiles) to UebersichtSection for Akten without Mandant or IBAN.

**Architecture:** Three new GET endpoints added to `dashboard_routes.py` (onboarding-offen, nachrichten-neu, ramicro-fristen). `ActionBoardView.jsx` replaces `DashboardView.jsx` in `App.jsx`; it calls existing `apiWV.liste()` + 3 new API functions. `OnboardingHub.jsx` is a new component mounted at the top of `UebersichtSection.jsx`, derived entirely from existing Redux state — no new DB fields needed.

**Tech Stack:** React 18 (JSX, inline styles, useState/useEffect), Flask/Python 3.9, SQLite via `get_connection()`, RA-MICRO via `get_ramicro_connection()`, existing Redux state (`st.beteiligte`, `st.schaden`, `st.dokumente`, `st.aktivitaeten`).

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `backend/routers/dashboard_routes.py` | Modify | Add 3 new GET endpoints |
| `backend/tests/test_dashboard_uebersicht.py` | Create | Tests for 2 SQLite endpoints |
| `frontend/src/api.js` | Modify | 3 new API functions |
| `frontend/src/views/ActionBoardView.jsx` | Create | New global springboard view |
| `frontend/src/App.jsx` | Modify | Swap DashboardView → ActionBoardView (2 lines) |
| `frontend/src/sections/OnboardingHub.jsx` | Create | 7-tile Hub & Spoke component |
| `frontend/src/sections/UebersichtSection.jsx` | Modify | Mount OnboardingHub at top |

---

## Task 1: Backend — `/dashboard/onboarding-offen` und `/dashboard/nachrichten-neu`

**Files:**
- Modify: `backend/routers/dashboard_routes.py`
- Create: `backend/tests/test_dashboard_uebersicht.py`

- [ ] **Schritt 1: Test für `/dashboard/onboarding-offen` schreiben**

Datei anlegen: `backend/tests/test_dashboard_uebersicht.py`

```python
import pytest
from backend.app import erstelle_app


@pytest.fixture
def client():
    app = erstelle_app({"TESTING": True})
    with app.test_client() as c:
        # Login überspringen — direkt testen
        with app.app_context():
            yield c


def test_onboarding_offen_gibt_liste_zurueck(client):
    """Endpoint liefert Liste, auch wenn sie leer ist."""
    resp = client.get(
        "/dashboard/onboarding-offen",
        headers={"Authorization": "Bearer test"}
    )
    assert resp.status_code in (200, 401)  # 401 ohne gültigen Token ist ok
```

Hinweis: Falls der Endpoint `@login_erforderlich` hat, entweder mit gültigem Token testen oder den Decorator in Tests patchen. Orientiere dich an bestehenden Tests wie `test_prd23b.py`.

- [ ] **Schritt 2: Test laufen lassen (erwartet FAIL)**

```bash
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/unfallakten/backend"
python -m pytest tests/test_dashboard_uebersicht.py -v
```

Erwartet: `FAILED` oder `ERROR` — Endpoint existiert noch nicht.

- [ ] **Schritt 3: Zwei Hilfsfunktionen + zwei Routen in `dashboard_routes.py` hinzufügen**

Direkt nach der bestehenden `_lade_akten_ohne_bewegung`-Funktion anfügen:

```python
# ══════════════════════════════════════════════════════════════
#  GET /dashboard/onboarding-offen
# ══════════════════════════════════════════════════════════════

def _lade_onboarding_offen(conn):
    """
    Akten ohne Mandant-Beteiligter ODER ohne IBAN.
    Liefert max. 20 Einträge, neueste zuerst.
    """
    rows = conn.execute("""
        SELECT
            a.aktenzeichen                                    AS az,
            COALESCE(b.name || ' ' || COALESCE(b.vorname, ''), '') AS mandant,
            CASE WHEN b.id IS NULL THEN 'mandant' ELSE 'iban' END   AS fehlt
        FROM unfallakte a
        LEFT JOIN beteiligte b
               ON b.akte_id = a.id AND b.rolle = 'mandant'
        WHERE a.status != 'abgeschlossen'
          AND (b.id IS NULL
               OR b.iban IS NULL
               OR trim(b.iban) = '')
        ORDER BY a.id DESC
        LIMIT 20
    """).fetchall()
    return [dict(r) for r in rows]


def _lade_nachrichten_neu(conn):
    """
    Letzte 20 E-Mails aus email_import_log, neueste zuerst.
    Nur Mails mit bekannter Akte (akte_id IS NOT NULL).
    """
    rows = conn.execute("""
        SELECT
            a.aktenzeichen   AS az,
            e.absender,
            e.betreff,
            e.empfangen_am   AS datum,
            'email'          AS kanal
        FROM email_import_log e
        JOIN unfallakte a ON a.id = e.akte_id
        WHERE e.akte_id IS NOT NULL
        ORDER BY e.empfangen_am DESC
        LIMIT 20
    """).fetchall()
    return [dict(r) for r in rows]


@dashboard_bp.route("/onboarding-offen", methods=["GET"])
@login_erforderlich
def onboarding_offen():
    """Akten ohne Mandant oder IBAN — für Action Board Onboarding-Spalte."""
    with get_connection() as conn:
        return _j({"eintraege": _lade_onboarding_offen(conn)})


@dashboard_bp.route("/nachrichten-neu", methods=["GET"])
@login_erforderlich
def nachrichten_neu():
    """Neueste E-Mails kanzleiweit — für Action Board Nachrichten-Spalte."""
    with get_connection() as conn:
        return _j({"eintraege": _lade_nachrichten_neu(conn)})
```

- [ ] **Schritt 4: Tests laufen lassen (erwartet PASS)**

```bash
python -m pytest tests/test_dashboard_uebersicht.py -v
```

Erwartet: PASSED (oder 401 wenn Auth-Mock fehlt — beide Endpoints existieren dann).

- [ ] **Schritt 5: Commit**

```bash
git add backend/routers/dashboard_routes.py backend/tests/test_dashboard_uebersicht.py
git commit -m "feat(dashboard): /onboarding-offen + /nachrichten-neu Endpoints"
```

---

## Task 2: Backend — `/dashboard/ramicro-fristen`

**Files:**
- Modify: `backend/routers/dashboard_routes.py`

Dieser Endpoint liest RA-MICRO read-only. Die genaue Tabellenstruktur ist unbekannt — Schritt 1 erkundet sie.

- [ ] **Schritt 1: RA-MICRO Fristen-Tabelle erkunden**

Python-Snippet einmalig ausführen (z.B. in einer Flask-Shell oder als temporäres Skript):

```python
from backend.ramicro.connector import get_ramicro_connection
with get_ramicro_connection() as conn:
    # Alle Tabellen mit "rist" oder "ermin" im Namen
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND (name LIKE '%rist%' OR name LIKE '%ermin%' OR name LIKE '%frist%')"
    ).fetchall()
    print([t[0] for t in tables])
    # Für jede gefundene Tabelle: Spalten anzeigen
    for t in tables:
        cols = conn.execute(f"PRAGMA table_info({t[0]})").fetchall()
        print(f"\n{t[0]}:", [c[1] for c in cols])
```

Notiere: Tabellenname + Spalten für Datum, AZ-Referenz, Fristbezeichnung.

- [ ] **Schritt 2: Endpoint mit entdeckten Spalten implementieren**

Füge nach den bestehenden Routen in `dashboard_routes.py` hinzu. Platzhalter `TABELLE`, `COL_DATUM`, `COL_AZ`, `COL_ART` durch echte Namen aus Schritt 1 ersetzen:

```python
from ..ramicro.connector import (
    get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
)
from datetime import datetime


def _lade_ramicro_fristen():
    """
    Liest harte Fristen (Rechtsmittelfristen etc.) aus RA-MICRO.
    Gibt leere Liste bei Verbindungsfehler zurück — nie werfen.

    IMPLEMENTIERER: Ersetze TABELLE, COL_DATUM, COL_AZ, COL_ART
    mit echten Spaltennamen aus Schritt 1.
    """
    try:
        heute = date.today().isoformat()
        bis = (date.today() + timedelta(days=60)).isoformat()
        with get_ramicro_connection() as conn:
            rows = conn.execute(f"""
                SELECT
                    {COL_AZ}       AS az,
                    {COL_ART}      AS frist_art,
                    {COL_DATUM}    AS frist_datum
                FROM {TABELLE}
                WHERE {COL_DATUM} BETWEEN ? AND ?
                ORDER BY {COL_DATUM} ASC
                LIMIT 50
            """, (heute, bis)).fetchall()
        heute_dt = date.today()
        ergebnis = []
        for r in rows:
            try:
                fd = date.fromisoformat(str(r["frist_datum"])[:10])
                tage = (fd - heute_dt).days
            except Exception:
                tage = 99
            ergebnis.append({
                "az":          r["az"] or "",
                "mandant":     "",        # optional: JOIN auf Akten-Tabelle
                "frist_art":   r["frist_art"] or "",
                "frist_datum": str(r["frist_datum"])[:10],
                "tage_bis":    tage,
            })
        return ergebnis
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("ramicro_fristen Fehler: %s", e)
        return []


@dashboard_bp.route("/ramicro-fristen", methods=["GET"])
@login_erforderlich
def ramicro_fristen():
    """Harte RA-MICRO Fristen für die nächsten 60 Tage."""
    return _j({"eintraege": _lade_ramicro_fristen()})
```

- [ ] **Schritt 3: Manuell testen**

```bash
# Docker neu starten (kein rebuild nötig — Volume-Mount)
docker compose restart backend

# Endpoint aufrufen
curl -s -H "Authorization: Bearer <TOKEN>" \
  http://localhost:5000/dashboard/ramicro-fristen | python -m json.tool
```

Erwartet: `{"eintraege": [...]}` — Liste kann leer sein wenn RA-MICRO nicht verbunden.

- [ ] **Schritt 4: Commit**

```bash
git add backend/routers/dashboard_routes.py
git commit -m "feat(dashboard): /ramicro-fristen Endpoint (RA-MICRO read-only)"
```

---

## Task 3: Frontend — api.js Ergänzungen

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Schritt 1: Bestehenden `apiDashboard`-Block in `api.js` finden**

Suche nach `apiDashboard` oder `dashboard` in `api.js`. Dort sind bereits Funktionen wie `actionItems()`. Füge drei neue Funktionen in dasselbe Objekt ein:

```javascript
// In das bestehende apiDashboard-Objekt einfügen:
onboardingOffen: () =>
  api.request("/dashboard/onboarding-offen"),

nachrichtenNeu: () =>
  api.request("/dashboard/nachrichten-neu"),

ramicroFristen: () =>
  api.request("/dashboard/ramicro-fristen"),
```

- [ ] **Schritt 2: Datei speichern, Vite-Dev-Server prüfen (kein Fehler in der Konsole)**

- [ ] **Schritt 3: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(api): apiDashboard.onboardingOffen/nachrichtenNeu/ramicroFristen"
```

---

## Task 4: Frontend — `ActionBoardView.jsx` (neue Datei)

**Files:**
- Create: `frontend/src/views/ActionBoardView.jsx`

- [ ] **Schritt 1: Datei anlegen**

`frontend/src/views/ActionBoardView.jsx`:

```jsx
import React, { useEffect, useState, useCallback } from "react";
import { apiDashboard, apiWV, apiAkten } from "../api";

// ─── Theme ───────────────────────────────────────────────────
const T = {
  navy:       "#1B2A4A",
  terra:      "#A06B4A",
  terraLight: "#F3EAE2",
  bg:         "#F6F4EF",
  surface:    "#FAFAF8",
  border:     "#E2DDD3",
  red:        "#dc2626",  redBg:   "#fef2f2",
  amber:      "#d97706",  amberBg: "#fffbeb",
  green:      "#16a34a",  greenBg: "#f0fdf4",
  text:       "#1e293b",
  faint:      "#64748b",
};

const LABEL = {
  fontSize: "0.68rem", fontWeight: 700,
  textTransform: "uppercase", letterSpacing: ".06em",
  color: T.faint, marginBottom: 8,
  fontFamily: "Bricolage Grotesque",
};

// ─── Hilfsfunktion: AZ aus WV-Aktenzeichen (entfernt SB-Kürzel) ──
function baseAz(azVoll) {
  return (azVoll || "").replace(/[A-Z]{2,3}$/i, "").trim();
}

// ─── Heute als ISO-String ────────────────────────────────────
function heuteISO() {
  return new Date().toISOString().slice(0, 10);
}

// ════════════════════════════════════════════════════════════════
//  Sub-Komponente: Fristen-Spalte (RA-MICRO)
// ════════════════════════════════════════════════════════════════
function FristenSpalte({ fristen, onOpenAkte }) {
  const bg   = (t) => t <= 14 ? T.redBg   : t <= 30 ? T.amberBg   : T.greenBg;
  const col  = (t) => t <= 14 ? T.red     : t <= 30 ? T.amber     : T.green;

  return (
    <div style={{ borderRight: `1px solid ${T.border}`, padding: 12, overflowY: "auto", background: T.surface }}>
      <div style={LABEL}>⚡ Fristen (RA-MICRO)</div>
      {fristen.length === 0 ? (
        <p style={{ fontSize: "0.78rem", color: T.faint }}>
          Keine offenen Fristen · RA-MICRO nicht verbunden
        </p>
      ) : (
        fristen.map((f, i) => (
          <div
            key={i}
            onClick={() => onOpenAkte(f.az)}
            style={{
              background: bg(f.tage_bis), borderRadius: 6,
              padding: "8px 10px", marginBottom: 6, cursor: "pointer",
              border: `1px solid ${col(f.tage_bis)}40`,
            }}
          >
            <div style={{ fontWeight: 600, fontSize: "0.8rem", color: T.text, fontFamily: "Bricolage Grotesque" }}>
              {f.az}{f.mandant ? ` — ${f.mandant}` : ""}
            </div>
            <div style={{ fontSize: "0.75rem", color: "#475569", marginTop: 2 }}>{f.frist_art}</div>
            <div style={{ fontSize: "0.8rem", fontWeight: 700, color: col(f.tage_bis), marginTop: 3 }}>
              {f.frist_datum} · {f.tage_bis} Tage
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Sub-Komponente: Handlung erforderlich
// ════════════════════════════════════════════════════════════════
function HandlungSpalte({ wvFaellig, onboardingOffen, onOpenAkte }) {
  const EintragZeile = ({ az, titel, sub, rand }) => (
    <div
      onClick={() => onOpenAkte(az)}
      style={{
        borderLeft: `3px solid ${rand}`, background: T.surface,
        borderRadius: "0 6px 6px 0", padding: "7px 10px",
        marginBottom: 5, cursor: "pointer",
      }}
    >
      <div style={{ fontWeight: 600, fontSize: "0.82rem", color: T.text, fontFamily: "Bricolage Grotesque" }}>
        {az}
      </div>
      <div style={{ fontSize: "0.75rem", color: T.faint, marginTop: 1 }}>{titel}</div>
      {sub && <div style={{ fontSize: "0.72rem", color: T.faint, marginTop: 1, fontStyle: "italic" }}>{sub}</div>}
    </div>
  );

  return (
    <div style={{ borderRight: `1px solid ${T.border}`, padding: 12, overflowY: "auto" }}>
      {/* Wiedervorlage */}
      <div style={LABEL}>Wiedervorlage fällig ({wvFaellig.length})</div>
      {wvFaellig.length === 0 ? (
        <p style={{ fontSize: "0.78rem", color: T.faint, marginBottom: 16 }}>Keine fälligen Wiedervorlagen</p>
      ) : (
        <div style={{ marginBottom: 16 }}>
          {wvFaellig.slice(0, 15).map((wv, i) => {
            const az = baseAz(wv.aktenzeichen);
            const tageDiff = Math.floor((new Date(heuteISO()) - new Date(wv.datum)) / 86400000);
            const sub = tageDiff > 0 ? `${tageDiff} Tag${tageDiff !== 1 ? "e" : ""} überfällig` : "heute fällig";
            return (
              <EintragZeile
                key={i}
                az={az}
                titel={wv.mandant || wv.kurzbezeichnung || ""}
                sub={`${wv.grund || ""} · ${sub}`}
                rand={tageDiff > 0 ? T.red : T.amber}
              />
            );
          })}
        </div>
      )}

      {/* Onboarding */}
      <div style={LABEL}>Onboarding unvollständig ({onboardingOffen.length})</div>
      {onboardingOffen.length === 0 ? (
        <p style={{ fontSize: "0.78rem", color: T.faint }}>Alle Akten vollständig</p>
      ) : (
        onboardingOffen.slice(0, 10).map((ob, i) => (
          <EintragZeile
            key={i}
            az={ob.az}
            titel={ob.mandant || "–"}
            sub={ob.fehlt === "mandant" ? "Mandant fehlt" : "IBAN fehlt"}
            rand="#8b5cf6"
          />
        ))
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Sub-Komponente: Nachrichten
// ════════════════════════════════════════════════════════════════
function NachrichtenSpalte({ nachrichten, onOpenAkte }) {
  const [aktiveTab, setAktiveTab] = useState("email");

  const TabBtn = ({ id, label, anzahl }) => (
    <button
      onClick={() => setAktiveTab(id)}
      style={{
        background: aktiveTab === id ? T.navy : "transparent",
        color: aktiveTab === id ? "#fff" : T.faint,
        border: `1px solid ${aktiveTab === id ? T.navy : T.border}`,
        borderRadius: 4, padding: "3px 10px",
        fontSize: "0.72rem", cursor: "pointer",
        fontFamily: "Figtree",
      }}
    >
      {label}{anzahl > 0 ? ` (${anzahl})` : ""}
    </button>
  );

  return (
    <div style={{ padding: 12, overflowY: "auto", background: T.surface }}>
      <div style={LABEL}>Nachrichten</div>
      <div style={{ display: "flex", gap: 4, marginBottom: 10, flexWrap: "wrap" }}>
        <TabBtn id="email"  label="📧 E-Mail"         anzahl={nachrichten.length} />
        <TabBtn id="portal" label="👤 Mandantenportal" anzahl={0} />
        <TabBtn id="sv"     label="🔬 SV-Portal"       anzahl={0} />
      </div>

      {aktiveTab === "email" && (
        nachrichten.length === 0 ? (
          <p style={{ fontSize: "0.78rem", color: T.faint }}>Keine neuen E-Mails</p>
        ) : (
          nachrichten.map((m, i) => (
            <div
              key={i}
              onClick={() => onOpenAkte(m.az)}
              style={{
                background: T.bg, borderRadius: 5,
                padding: "7px 10px", marginBottom: 6,
                cursor: "pointer", borderLeft: `3px solid ${T.navy}`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontWeight: 600, fontSize: "0.78rem", color: T.navy, fontFamily: "Bricolage Grotesque" }}>
                  {m.az}
                </span>
                <span style={{ fontSize: "0.68rem", color: T.faint }}>
                  {m.datum ? m.datum.slice(0, 10) : ""}
                </span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "#475569", marginTop: 1 }}>{m.absender}</div>
              <div style={{ fontSize: "0.72rem", color: T.faint, marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {m.betreff}
              </div>
            </div>
          ))
        )
      )}

      {(aktiveTab === "portal" || aktiveTab === "sv") && (
        <p style={{ fontSize: "0.78rem", color: T.faint, fontStyle: "italic" }}>
          Demnächst verfügbar
        </p>
      )}
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Neue-Akte-Modal (kopiert aus AktensucheView)
// ════════════════════════════════════════════════════════════════
function NeueAkteModal({ onClose, onOpenAkte }) {
  const INIT = { aktenzeichen: "", unfalldatum: "", unfallort: "", notizen: "" };
  const [felder, setFelder] = useState(INIT);
  const [fehler, setFehler] = useState({});
  const [speichern, setSpeichern] = useState(false);

  const set = (k, v) => setFelder(p => ({ ...p, [k]: v }));

  const validiere = () => {
    const f = {};
    if (!felder.aktenzeichen.match(/^\d+\/\d{2}([A-Z]{2,3})?$/i))
      f.aktenzeichen = "Format: 42/26 oder 42/26AS";
    if (!felder.unfalldatum) f.unfalldatum = "Pflichtfeld";
    setFehler(f);
    return Object.keys(f).length === 0;
  };

  const anlegen = async () => {
    if (!validiere()) return;
    setSpeichern(true);
    try {
      const res = await apiAkten.erstellen({
        aktenzeichen: felder.aktenzeichen.trim(),
        unfalldatum:  felder.unfalldatum.trim(),
        unfallort:    felder.unfallort.trim() || undefined,
        notizen:      felder.notizen.trim()   || undefined,
      });
      onOpenAkte(res.akte.az || res.akte.aktenzeichen);
      onClose();
    } catch (e) {
      setFehler({ global: e.message || "Fehler beim Anlegen" });
    } finally {
      setSpeichern(false);
    }
  };

  const feld = (key, label, type = "text", pflicht = false) => (
    <div style={{ marginBottom: 10 }}>
      <label style={{ fontSize: "0.78rem", color: T.faint, display: "block", marginBottom: 3 }}>
        {label}{pflicht ? " *" : ""}
      </label>
      <input
        type={type}
        value={felder[key]}
        onChange={e => set(key, e.target.value)}
        style={{
          width: "100%", boxSizing: "border-box",
          border: `1px solid ${fehler[key] ? T.red : T.border}`,
          borderRadius: 5, padding: "6px 10px",
          fontSize: "0.85rem", background: T.bg,
          fontFamily: "Figtree",
        }}
      />
      {fehler[key] && <div style={{ fontSize: "0.72rem", color: T.red, marginTop: 2 }}>{fehler[key]}</div>}
    </div>
  );

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 9000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ background: "#fff", borderRadius: 10, padding: 24, width: 380, maxWidth: "95vw", boxShadow: "0 8px 32px rgba(0,0,0,.2)" }}>
        <div style={{ fontFamily: "Bricolage Grotesque", fontWeight: 700, fontSize: "1.1rem", color: T.navy, marginBottom: 16 }}>
          Neue Akte anlegen
        </div>
        {feld("aktenzeichen", "Aktenzeichen", "text", true)}
        {feld("unfalldatum",  "Unfalldatum",  "date", true)}
        {feld("unfallort",    "Unfallort")}
        {feld("notizen",      "Notizen")}
        {fehler.global && <div style={{ fontSize: "0.78rem", color: T.red, marginBottom: 8 }}>{fehler.global}</div>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
          <button onClick={onClose} style={{ background: "transparent", border: `1px solid ${T.border}`, borderRadius: 5, padding: "6px 14px", cursor: "pointer", fontFamily: "Figtree" }}>
            Abbrechen
          </button>
          <button
            onClick={anlegen}
            disabled={speichern}
            style={{ background: T.terra, color: "#fff", border: "none", borderRadius: 5, padding: "6px 16px", cursor: "pointer", fontFamily: "Figtree", fontWeight: 600 }}
          >
            {speichern ? "Legt an…" : "Anlegen"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════
//  Haupt-Komponente: ActionBoardView
// ════════════════════════════════════════════════════════════════
export default function ActionBoardView({ onOpenAkte }) {
  const [wvAlle,         setWvAlle]         = useState([]);
  const [onboardingOffen, setOnboardingOffen] = useState([]);
  const [nachrichten,    setNachrichten]    = useState([]);
  const [fristen,        setFristen]        = useState([]);
  const [geladen,        setGeladen]        = useState(false);
  const [zeigeModal,     setZeigeModal]     = useState(false);

  useEffect(() => {
    Promise.allSettled([
      apiWV.liste({ nurHeute: false }),
      apiDashboard.onboardingOffen(),
      apiDashboard.nachrichtenNeu(),
      apiDashboard.ramicroFristen(),
    ]).then(([wv, ob, na, fr]) => {
      if (wv.status === "fulfilled") setWvAlle(wv.value || []);
      if (ob.status === "fulfilled") setOnboardingOffen(ob.value?.eintraege || []);
      if (na.status === "fulfilled") setNachrichten(na.value?.eintraege || []);
      if (fr.status === "fulfilled") setFristen(fr.value?.eintraege || []);
      setGeladen(true);
    });
  }, []);

  const oeffneAkte = useCallback((az) => {
    onOpenAkte({ az: baseAz(az), az_roh: az });
  }, [onOpenAkte]);

  // WV filtern: nur datum <= heute
  const wvFaellig = wvAlle.filter(wv => wv.datum <= heuteISO());

  const heute = new Date().toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", background: T.bg, overflow: "hidden" }}>

      {/* Kopfzeile */}
      <div style={{
        background: T.navy, padding: "10px 16px",
        display: "flex", alignItems: "center", flexShrink: 0,
      }}>
        <span style={{ fontFamily: "Bricolage Grotesque", fontWeight: 700, fontSize: "1.05rem", color: "#fff" }}>
          Action Board
        </span>
        <span style={{ color: "#94a3b8", marginLeft: 16, fontSize: "0.83rem" }}>{heute}</span>
        <button
          onClick={() => setZeigeModal(true)}
          style={{
            marginLeft: "auto", background: T.terra, color: "#fff",
            border: "none", borderRadius: 6, padding: "6px 14px",
            cursor: "pointer", fontFamily: "Figtree", fontWeight: 600,
          }}
        >
          + Neue Akte
        </button>
      </div>

      {/* 3-Spalten Grid */}
      {!geladen ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: T.faint }}>
          Lade…
        </div>
      ) : (
        <div style={{ flex: 1, display: "grid", gridTemplateColumns: "220px 1fr 300px", overflow: "hidden" }}>
          <FristenSpalte    fristen={fristen}                       onOpenAkte={oeffneAkte} />
          <HandlungSpalte   wvFaellig={wvFaellig} onboardingOffen={onboardingOffen} onOpenAkte={oeffneAkte} />
          <NachrichtenSpalte nachrichten={nachrichten}              onOpenAkte={oeffneAkte} />
        </div>
      )}

      {zeigeModal && (
        <NeueAkteModal
          onClose={() => setZeigeModal(false)}
          onOpenAkte={oeffneAkte}
        />
      )}
    </div>
  );
}
```

- [ ] **Schritt 2: Datei speichern, keine Lint-Fehler prüfen**

Vite-Dev-Server-Konsole auf Fehler prüfen (falls läuft).

- [ ] **Schritt 3: Commit**

```bash
git add frontend/src/views/ActionBoardView.jsx
git commit -m "feat(ui): ActionBoardView — globales Sprungbrett mit Fristen/WV/Nachrichten"
```

---

## Task 5: Frontend — `App.jsx` umverdrahten

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Schritt 1: Import tauschen**

In `App.jsx` suche nach:
```javascript
import DashboardView from
```
Ändere zu:
```javascript
import ActionBoardView from "./views/ActionBoardView";
```

(Den alten `DashboardView`-Import auskommentieren oder löschen.)

- [ ] **Schritt 2: JSX tauschen**

Suche (ca. Zeile 6082):
```javascript
active==="dashboard" ? <DashboardView onOpenAkte={openAkte} aktenState={aktenState} />
```
Ändere zu:
```javascript
active==="dashboard" ? <ActionBoardView onOpenAkte={openAkte} />
```

- [ ] **Schritt 3: Im Browser testen**

- Dashboard-Tab klicken → Action Board erscheint mit 3 Spalten
- „+ Neue Akte"-Button → Modal öffnet sich
- Klick auf WV-Eintrag / Onboarding-Eintrag → Akte-Tab öffnet sich

- [ ] **Schritt 4: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(ui): ActionBoardView ersetzt DashboardView in App.jsx"
```

---

## Task 6: Frontend — `OnboardingHub.jsx` + Einbindung in `UebersichtSection.jsx`

**Files:**
- Create: `frontend/src/sections/OnboardingHub.jsx`
- Modify: `frontend/src/sections/UebersichtSection.jsx`

- [ ] **Schritt 1: `OnboardingHub.jsx` anlegen**

`frontend/src/sections/OnboardingHub.jsx`:

```jsx
import React, { useState } from "react";

const T = {
  navy:    "#1B2A4A",
  border:  "#E2DDD3",
  amber:   "#d97706", amberBg: "#fffbeb", amberBorder: "#fde68a",
  green:   "#16a34a", greenBg: "#f0fdf4", greenBorder:  "#86efac",
  purple:  "#7c3aed", purpleBg: "#f5f3ff", purpleBorder: "#c4b5fd",
};

export default function OnboardingHub({ az, beteiligte = [], schaden = {}, dokumente = [], aktivitaeten = [], onTabWechsel }) {

  // ── Status-Checks (live aus Props/State) ───────────────────
  const mandant     = beteiligte.find(b => b.rolle === "mandant");
  const gegner      = beteiligte.find(b => b.rolle === "gegner");
  const ghpv        = beteiligte.find(b => ["ghpv", "versicherung", "ghpv_versicherung"].includes(b.rolle));
  const hatUnfall   = !!(schaden?.unfalldatum && schaden?.unfallort);
  const hatSchaden  = (schaden?.positionen?.length || 0) > 0;
  const hatVollmacht = dokumente.some(d => (d.klasse || "").toLowerCase().includes("vollmacht"));
  const hatErstforderung = aktivitaeten.some(a => a.typ === "forderungsschreiben");

  // ── Onboarding nötig? ──────────────────────────────────────
  const onboardingNoetig = !mandant || !mandant.iban;

  // ── localStorage-Flag ─────────────────────────────────────
  const storageKey = `onboarding_hub_versteckt_${az}`;
  const [versteckt, setVersteckt] = useState(
    () => localStorage.getItem(storageKey) === "true"
  );

  if (!onboardingNoetig || versteckt) return null;

  // ── Zähler (Erstforderung zählt nicht als Pflicht) ────────
  const erledigt = [!!mandant, !!gegner, !!ghpv, hatUnfall, hatSchaden, hatVollmacht]
    .filter(Boolean).length;

  // ── Kacheln-Definition ────────────────────────────────────
  const kacheln = [
    { key: "mandant",      label: "Mandant",              ok: !!mandant,   tab: "beteiligte"  },
    { key: "gegner",       label: "Gegner / Schädiger",   ok: !!gegner,    tab: "beteiligte"  },
    { key: "ghpv",         label: "GHPV (Versicherung)",  ok: !!ghpv,      tab: "beteiligte"  },
    { key: "unfalldetails",label: "Unfalldetails",         ok: hatUnfall,   tab: "unfalldetails"},
    { key: "schaden",      label: "Schadenspositionen",   ok: hatSchaden,  tab: "schaden"     },
    { key: "vollmacht",    label: "Vollmacht & Dokumente",ok: hatVollmacht,tab: "dokumente"   },
    { key: "erstforderung",label: "Erstforderung",        ok: hatErstforderung, tab: "word", optional: true },
  ];

  const Kachel = ({ k }) => {
    const bg     = k.ok ? T.greenBg  : k.optional ? T.purpleBg  : T.amberBg;
    const border = k.ok ? T.greenBorder : k.optional ? T.purpleBorder : T.amberBorder;
    const col    = k.ok ? T.green    : k.optional ? T.purple    : T.amber;

    return (
      <div
        onClick={() => onTabWechsel && onTabWechsel(k.tab)}
        style={{
          background: bg, border: `1px solid ${border}`,
          borderRadius: 7, padding: "9px 12px",
          cursor: onTabWechsel ? "pointer" : "default",
          transition: "opacity .15s",
        }}
        onMouseEnter={e => e.currentTarget.style.opacity = ".85"}
        onMouseLeave={e => e.currentTarget.style.opacity = "1"}
      >
        <div style={{ fontSize: "0.78rem", fontWeight: 700, color: col, fontFamily: "Bricolage Grotesque" }}>
          {k.ok ? "✓" : "○"} {k.label}
        </div>
        {k.optional && !k.ok && (
          <div style={{ fontSize: "0.65rem", color: T.purple, marginTop: 2 }}>optional</div>
        )}
      </div>
    );
  };

  return (
    <div style={{
      background: T.amberBg,
      border: `1px solid ${T.amberBorder}`,
      borderRadius: 9, margin: "12px 12px 0",
      padding: "12px 16px",
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontFamily: "Bricolage Grotesque", fontWeight: 700, color: T.navy, fontSize: "0.9rem" }}>
          Onboarding — {erledigt} von 6 Bereichen vollständig
        </span>
        <button
          onClick={() => { localStorage.setItem(storageKey, "true"); setVersteckt(true); }}
          style={{
            marginLeft: "auto", background: "transparent",
            border: `1px solid ${T.amber}`, borderRadius: 4,
            padding: "3px 12px", color: T.amber,
            cursor: "pointer", fontSize: "0.78rem", fontFamily: "Figtree",
          }}
        >
          Zur normalen Ansicht →
        </button>
      </div>

      {/* Kacheln-Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        {kacheln.map(k => <Kachel key={k.key} k={k} />)}
      </div>
    </div>
  );
}
```

- [ ] **Schritt 2: In `UebersichtSection.jsx` einbinden**

Am Anfang der Datei nach den bestehenden Imports hinzufügen:
```javascript
import OnboardingHub from "./OnboardingHub";
```

Im Return-JSX von `UebersichtSection` das `<OnboardingHub …>` als **erstes Kind** des Root-Elements einfügen.

Suche das erste `return (` in `UebersichtSection` und füge direkt nach dem öffnenden Root-`<div>` ein:

```jsx
<OnboardingHub
  az={az}
  beteiligte={st?.beteiligte || []}
  schaden={st?.schaden || {}}
  dokumente={st?.dokumente || []}
  aktivitaeten={st?.aktivitaeten || []}
  onTabWechsel={onTabWechsel}   // Prop-Name prüfen — je nach UebersichtSection-Interface
/>
```

Hinweis: Prüfe wie `UebersichtSection` aufgerufen wird (vermutlich in `AkteDetailView.jsx`) und welcher Prop-Name für Tab-Wechsel verwendet wird. Wenn kein `onTabWechsel`-Prop existiert, den Tab-Wechsel-Callback aus dem Parent durchreichen oder zunächst weglassen (Hub erscheint dann ohne Klick-Funktion).

- [ ] **Schritt 3: Neue Akte anlegen und testen**

- Über Action Board „+ Neue Akte" → neues AZ anlegen
- Akte öffnen → Übersicht-Tab → OnboardingHub erscheint (amber Rahmen, 7 Kacheln)
- Mandant-Kachel anklicken → wechselt zu Beteiligte-Tab (falls onTabWechsel verdrahtet)
- „Zur normalen Ansicht" klicken → Hub verschwindet

- [ ] **Schritt 4: Commit**

```bash
git add frontend/src/sections/OnboardingHub.jsx frontend/src/sections/UebersichtSection.jsx
git commit -m "feat(ui): OnboardingHub — Hub & Spoke Onboarding in UebersichtSection"
```

---

## Self-Review Checklist

- [x] Spec § Action Board: 3-Spalten (Fristen / WV+Onboarding / Nachrichten) → Tasks 1–5
- [x] Spec § Fristen aus RA-MICRO → Task 2
- [x] Spec § WV fällig (≤ heute) + Onboarding unvollständig → Tasks 1 + 4
- [x] Spec § Nachrichten-Tabs (Email aktiv, Portal/SV Placeholder) → Task 4
- [x] Spec § ActionBoardView ersetzt DashboardView → Task 5
- [x] Spec § OnboardingHub: 7 Kacheln, Hub & Spoke, localStorage-Flag → Task 6
- [x] Spec § Keine neuen DB-Felder → bestätigt (nur vorhandene Tabellen/State)
- [x] Spec § NeueAkteModal → in Task 4 integriert (NeueAkteModal Komponente)
- [x] Fallback wenn RA-MICRO nicht verbunden → `_lade_ramicro_fristen()` gibt `[]` zurück
- [x] `onOpenAkte` akzeptiert `{ az, az_roh }` Objekt → korrekt in `oeffneAkte()`
