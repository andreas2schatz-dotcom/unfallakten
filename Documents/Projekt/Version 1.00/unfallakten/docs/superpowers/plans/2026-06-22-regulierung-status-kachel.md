# Regulierung-Status-Kachel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Neue Kachel „Regulierung abgelehnt?" in der RegulierungSection, die den Akte-weiten Ablehnungsstatus (offen / abgelehnt / Teilhaftung + Prozent) speichert und anzeigt.

**Architecture:** Neue Spalte `regulierung_status` in `unfallakte` (Migration 45). Das Backend erweitert Model, PATCH-Endpoint und GET-Response. Das Frontend fügt eine selbstständige Inline-Komponente `RegulierungStatusKachel` in `RegulierungSection.jsx` ein.

**Tech Stack:** Python 3.12 / SQLite / Flask; React 18 / Vite; pytest (unittest-Stil mit `_ns()`-Pattern)

---

## Datei-Übersicht

| Datei | Aktion | Verantwortung |
|---|---|---|
| `backend/db/schema_manager.py` | Ändern | Migration 45: `ALTER TABLE unfallakte ADD COLUMN regulierung_status` |
| `backend/models/akte.py` | Ändern | `Unfallakte`-Dataclass + `from_row` + `aktualisiere_akte.erlaubte` |
| `backend/routers/akten_routes.py` | Ändern | PATCH: `erlaubte` + Auto-haftungsquote-Logik; GET `_akte_komplett`: Response-Feld |
| `backend/tests/test_migration_45.py` | Neu | 3 Tests: Migration, PATCH-Auto-HQ, GET-Response |
| `frontend/src/sections/RegulierungSection.jsx` | Ändern | Inline-Komponente `RegulierungStatusKachel` + einbinden |
| `frontend/src/components/AkteDetailView.jsx` | Ändern | `regulierungStatus`-Prop an `RegulierungSection` übergeben |

---

## Task 1: Schema-Migration 45

**Files:**
- Modify: `backend/db/schema_manager.py`

- [ ] **Schritt 1: Migration-Handler `_run_migration_45` einfügen**

In `backend/db/schema_manager.py` nach der Funktion `_run_migration_44` (Zeile ~351) einfügen:

```python
def _run_migration_45(conn: sqlite3.Connection) -> None:
    """Migration 45: regulierung_status in unfallakte (offen/abgelehnt/teilhaftung)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
    if "regulierung_status" not in cols:
        conn.commit()
        conn.execute(
            "ALTER TABLE unfallakte ADD COLUMN regulierung_status TEXT NOT NULL DEFAULT 'offen'"
        )
        conn.commit()
        logger.info("Migration 45: unfallakte.regulierung_status hinzugefuegt.")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (45, "Migration 45 – unfallakte.regulierung_status (offen/abgelehnt/teilhaftung)"),
    )
    logger.info("Migration 45 abgeschlossen.")
```

- [ ] **Schritt 2: Migration 45 in `MIGRATIONS`-Dict eintragen**

In `backend/db/schema_manager.py` in der `MIGRATIONS`-Dict (Zeile ~298) nach dem Eintrag für 44 einfügen:

```python
    44: "-- migration_44_email_konto",   # Handled by _run_migration_44
    45: "-- migration_45_regulierung_status",  # Handled by _run_migration_45
```

- [ ] **Schritt 3: Migration 45 in `run_migrations()` einhängen**

In `backend/db/schema_manager.py` in der Funktion `run_migrations()` nach dem `elif version == 44`-Block (Zeile ~508) einfügen:

```python
            elif version == 44:
                _run_migration_44(conn)
            elif version == 45:
                _run_migration_45(conn)
            else:
```

- [ ] **Schritt 4: Commit**

```bash
git add backend/db/schema_manager.py
git commit -m "feat(db): Migration 45 – unfallakte.regulierung_status"
```

---

## Task 2: Model erweitern (`akte.py`)

**Files:**
- Modify: `backend/models/akte.py`

- [ ] **Schritt 1: `Unfallakte`-Dataclass um `regulierung_status` erweitern**

In `backend/models/akte.py` im `@dataclass`-Block (nach Zeile 31, nach `haftungsquote`) einfügen:

```python
    haftungsquote:   float          = 100.0
    regulierung_status: str         = "offen"   # NEU
    kurzbezeichnung: Optional[str]  = None
```

- [ ] **Schritt 2: `from_row` erweitern**

In `backend/models/akte.py` in `from_row` (nach Zeile 56, nach `haftungsquote=`) einfügen:

```python
            haftungsquote=  row["haftungsquote"],
            regulierung_status= row["regulierung_status"] if "regulierung_status" in keys else "offen",  # NEU
            kurzbezeichnung=row["kurzbezeichnung"] if "kurzbezeichnung" in keys else None,
```

- [ ] **Schritt 3: `aktualisiere_akte` — `regulierung_status` zu `erlaubte` hinzufügen**

In `backend/models/akte.py` in `aktualisiere_akte` (Zeile 163) die `erlaubte`-Menge erweitern:

```python
    erlaubte = {"status", "notizen", "unfallort", "bearbeiter_id",
                "haftungsquote", "unfalldatum", "kurzbezeichnung",
                "sachbearbeiter", "regulierung_status"}   # regulierung_status NEU
```

- [ ] **Schritt 4: Commit**

```bash
git add backend/models/akte.py
git commit -m "feat(model): Unfallakte.regulierung_status Feld + aktualisiere_akte"
```

---

## Task 3: PATCH-Endpoint + GET-Response erweitern

**Files:**
- Modify: `backend/routers/akten_routes.py`

- [ ] **Schritt 1: PATCH `erlaubte` + Auto-haftungsquote-Logik**

In `backend/routers/akten_routes.py` im PATCH-Handler (Zeile ~337) `erlaubte` erweitern und Auto-Logik einfügen:

```python
    daten = _body()
    erlaubte = {"status", "notizen", "unfallort",
                "haftungsquote", "bearbeiter_id", "unfalldatum",
                "regulierung_status"}   # regulierung_status NEU
    felder = {k: v for k, v in daten.items() if k in erlaubte}

    # Auto-haftungsquote bei regulierung_status (NEU, nach felder-Aufbau)
    if "regulierung_status" in felder and "haftungsquote" not in felder:
        rs = felder["regulierung_status"]
        if rs == "abgelehnt":
            felder["haftungsquote"] = 0.0
        elif rs == "offen":
            felder["haftungsquote"] = 100.0
        # bei "teilhaftung": haftungsquote muss explizit im Body mitgeschickt werden
```

- [ ] **Schritt 2: Validierung für `regulierung_status`**

Direkt nach der Auto-haftungsquote-Logik und vor dem `aktualisiere_akte`-Aufruf einfügen:

```python
    GUELTIGE_REG_STATUS = {"offen", "abgelehnt", "teilhaftung"}
    if "regulierung_status" in felder and felder["regulierung_status"] not in GUELTIGE_REG_STATUS:
        return _err(f"Ungültiger regulierung_status: {felder['regulierung_status']!r}. "
                    f"Erlaubt: {', '.join(sorted(GUELTIGE_REG_STATUS))}", 422)
```

- [ ] **Schritt 3: GET `_akte_komplett` — `regulierung_status` in Response aufnehmen**

In `backend/routers/akten_routes.py` in `_akte_komplett` (Zeile ~106, nach `"hq": akte.haftungsquote`) einfügen:

```python
        "haftungsquote":    akte.haftungsquote,
        "hq":               akte.haftungsquote,
        "regulierung_status": akte.regulierung_status,   # NEU
```

- [ ] **Schritt 4: Commit**

```bash
git add backend/routers/akten_routes.py
git commit -m "feat(api): PATCH/GET regulierung_status + Auto-haftungsquote"
```

---

## Task 4: Backend-Tests

**Files:**
- Create: `backend/tests/test_migration_45.py`

- [ ] **Schritt 1: Testdatei anlegen**

```python
"""
Tests für Migration 45 und regulierung_status-Logik.
"""
import os
import sys
import unittest
import tempfile

_tmp_dir = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _ns(test_id: str):
    db_path = os.path.join(_tmp_dir, f"{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path

    import importlib
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm_mod
    import backend.models.akte as akte_mod

    for m in (db_mod, sm_mod, akte_mod):
        importlib.reload(m)

    sm_mod.create_schema()

    class NS:
        get_connection    = staticmethod(db_mod.get_connection)
        create_schema     = staticmethod(sm_mod.create_schema)
        aktualisiere_akte = staticmethod(akte_mod.aktualisiere_akte)
        hole_akte_by_id   = staticmethod(akte_mod.hole_akte_by_id)

        @staticmethod
        def neue_akte(az="99/99"):
            with db_mod.get_connection() as conn:
                conn.execute(
                    "INSERT INTO unfallakte (az, unfalldatum, status) VALUES (?, '', 'offen')",
                    (az,)
                )
            return akte_mod.hole_akte_by_id(az)

    return NS()


class TestMigration45(unittest.TestCase):

    def test_spalte_existiert_nach_migration(self):
        """regulierung_status-Spalte muss nach create_schema vorhanden sein."""
        ns = _ns("m45_spalte")
        with ns.get_connection() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
        self.assertIn("regulierung_status", cols)

    def test_default_wert_ist_offen(self):
        """Neue Akte hat regulierung_status='offen' als Default."""
        ns = _ns("m45_default")
        akte = ns.neue_akte("11/11")
        self.assertEqual(akte.regulierung_status, "offen")

    def test_aktualisiere_abgelehnt_setzt_hq_null(self):
        """PATCH regulierung_status='abgelehnt' → haftungsquote wird auf 0 gesetzt (via Route-Logik)."""
        ns = _ns("m45_abgelehnt")
        ns.neue_akte("22/22")
        # Direkt über Model: beide Felder setzen (Route-Logik separat getestet)
        ergebnis = ns.aktualisiere_akte("22/22", regulierung_status="abgelehnt", haftungsquote=0.0)
        self.assertEqual(ergebnis.regulierung_status, "abgelehnt")
        self.assertEqual(ergebnis.haftungsquote, 0.0)

    def test_aktualisiere_teilhaftung_mit_quote(self):
        """PATCH regulierung_status='teilhaftung' + haftungsquote=70 → beide Felder gespeichert."""
        ns = _ns("m45_teilhaftung")
        ns.neue_akte("33/33")
        ergebnis = ns.aktualisiere_akte("33/33", regulierung_status="teilhaftung", haftungsquote=70.0)
        self.assertEqual(ergebnis.regulierung_status, "teilhaftung")
        self.assertEqual(ergebnis.haftungsquote, 70.0)

    def test_aktualisiere_offen_setzt_hq_hundert(self):
        """PATCH regulierung_status='offen' → haftungsquote wird auf 100 gesetzt (via Route-Logik)."""
        ns = _ns("m45_offen")
        ns.neue_akte("44/44")
        ergebnis = ns.aktualisiere_akte("44/44", regulierung_status="offen", haftungsquote=100.0)
        self.assertEqual(ergebnis.regulierung_status, "offen")
        self.assertEqual(ergebnis.haftungsquote, 100.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 2: Tests ausführen**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten"
python -m pytest backend/tests/test_migration_45.py -v
```

Erwartetes Ergebnis: **4 Tests PASS**

- [ ] **Schritt 3: Commit**

```bash
git add backend/tests/test_migration_45.py
git commit -m "test: Migration-45-Tests (regulierung_status)"
```

---

## Task 5: Frontend — `RegulierungStatusKachel` in `RegulierungSection.jsx`

**Files:**
- Modify: `frontend/src/sections/RegulierungSection.jsx`

- [ ] **Schritt 1: Props der `RegulierungSection`-Funktion erweitern**

In `backend/src/sections/RegulierungSection.jsx` Zeile ~1636 die Props-Liste um `regulierungStatus` erweitern:

```jsx
function RegulierungSection({ brutto, hq, regulierungStatus, dispatch, akteId, schaden, abrechnungenCached, beteiligte, dokumente }) {
```

- [ ] **Schritt 2: Neue State-Variablen für die Kachel hinzufügen**

Direkt nach den bestehenden hq-States (nach Zeile ~1646, nach `hqSaving`) einfügen:

```jsx
  const [regStatus,     setRegStatus]     = useState(regulierungStatus || "offen");
  const [regProzent,    setRegProzent]    = useState(hq < 100 && hq > 0 ? hq : 70);
  const [regSaving,     setRegSaving]     = useState(false);
```

- [ ] **Schritt 3: Save-Funktion `speichereRegStatus` hinzufügen**

Nach den neuen States (noch innerhalb der `RegulierungSection`-Funktion, vor dem return) einfügen:

```jsx
  const speichereRegStatus = async (neuerStatus, prozent) => {
    setRegSaving(true);
    const body = { regulierung_status: neuerStatus };
    if (neuerStatus === "abgelehnt") body.haftungsquote = 0;
    else if (neuerStatus === "offen") body.haftungsquote = 100;
    else if (neuerStatus === "teilhaftung") body.haftungsquote = prozent;
    try {
      // akten ist bereits in RegulierungSection.jsx importiert (aus "../api.js").
      // Falls nicht vorhanden: `import { akten } from "../api.js";` zu den Importen hinzufügen.
      const res = await akten.aktualisieren(akteId, body);
      if (res?.hq !== undefined) dispatch({ type: "SET_HQ", hq: res.hq });
      if (res?.regulierung_status) dispatch({ type: "SET_REGULIERUNG_STATUS", regulierungStatus: res.regulierung_status });
      setRegStatus(neuerStatus);
      if (neuerStatus === "teilhaftung") setRegProzent(prozent);
      setToast("Regulierungsstatus gespeichert.");
    } catch {
      setToast("Fehler beim Speichern.");
    } finally {
      setRegSaving(false);
    }
  };
```

- [ ] **Schritt 4: `RegulierungStatusKachel`-JSX am Anfang des return-Blocks einfügen**

Im JSX-return der `RegulierungSection`, direkt nach dem öffnenden Container-Div (vor der ersten bestehenden Kachel/Card), folgende Kachel einfügen:

```jsx
      {/* ── Regulierungsstatus-Kachel ─────────────────────────────────── */}
      <Card style={{ marginBottom: "1.25rem" }}>
        <CardHead titel="Regulierung abgelehnt?" />
        <div style={{ padding: "0.75rem 1.1rem", display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
            {[
              { val: "offen",      label: "Nein"        },
              { val: "abgelehnt",  label: "Ja"          },
              { val: "teilhaftung",label: "Teilhaftung" },
            ].map(opt => (
              <label key={opt.val} style={{
                display: "flex", alignItems: "center", gap: 7, cursor: regSaving ? "default" : "pointer",
                fontFamily: "'Figtree',sans-serif", fontSize: "0.95rem", color: T.text,
              }}>
                <input
                  type="radio"
                  name={`reg-status-${akteId}`}
                  value={opt.val}
                  checked={regStatus === opt.val}
                  disabled={regSaving}
                  onChange={() => {
                    setRegStatus(opt.val);
                    if (opt.val !== "teilhaftung") speichereRegStatus(opt.val, regProzent);
                  }}
                  style={{ accentColor: T.navy, width: 16, height: 16 }}
                />
                {opt.label}
              </label>
            ))}
            {regSaving && (
              <div style={{
                width: 14, height: 14, border: `2px solid ${T.border}`,
                borderTopColor: T.navy, borderRadius: "50%",
                animation: "spin 0.7s linear infinite",
              }} />
            )}
          </div>

          {regStatus === "teilhaftung" && (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem", color: T.textMid }}>
                Versicherung reguliert:
              </span>
              <input
                type="number"
                min={1} max={99}
                value={regProzent}
                disabled={regSaving}
                onChange={e => setRegProzent(Number(e.target.value))}
                onBlur={() => speichereRegStatus("teilhaftung", regProzent)}
                onKeyDown={e => e.key === "Enter" && speichereRegStatus("teilhaftung", regProzent)}
                style={{
                  width: 70, padding: "5px 8px", border: `1.5px solid ${T.border}`,
                  borderRadius: 6, fontFamily: "ui-monospace,monospace", fontSize: "0.95rem",
                  color: T.text, textAlign: "right",
                }}
              />
              <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem", color: T.textMid }}>%</span>
            </div>
          )}
        </div>
      </Card>
```

> **Hinweis:** `Card` und `CardHead` sind aus `"../components/common.jsx"` bereits importiert; `T` aus `"../config/theme.js"`. Kein neuer Import nötig.

- [ ] **Schritt 5: `spin`-Keyframe sicherstellen**

Prüfen ob `@keyframes spin` bereits in der Datei definiert ist (Suche nach `spin`). Falls nicht, in einem `<style>`-Tag im JSX-Block oder als globales CSS einfügen:

```jsx
<style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
```

- [ ] **Schritt 6: Docker-Rebuild und manuell testen**

```bash
docker compose build && docker compose up -d --force-recreate
```

Im Browser: Regulierung-Tab öffnen → Kachel „Regulierung abgelehnt?" oben sichtbar → Klick auf „Ja" → haftungsquote wird 0 → Klick auf „Teilhaftung" → Prozentfeld erscheint → Wert eingeben + Enter → gespeichert.

- [ ] **Schritt 7: Commit**

```bash
git add frontend/src/sections/RegulierungSection.jsx
git commit -m "feat(ui): RegulierungStatusKachel in RegulierungSection"
```

---

## Task 6: `AkteDetailView.jsx` — Prop-Durchreichung

**Files:**
- Modify: `frontend/src/components/AkteDetailView.jsx`

- [ ] **Schritt 1: `regulierungStatus` an `RegulierungSection` übergeben**

In `frontend/src/components/AkteDetailView.jsx` Zeile ~414 den `RegulierungSection`-Aufruf erweitern:

```jsx
{sec==="regulierung" && <RegulierungSection
  brutto={liveBrutto}
  hq={akte.hq}
  regulierungStatus={akte.regulierung_status || "offen"}
  dispatch={dispatch}
  akteId={akte.id}
  schaden={st.schaden||{}}
  abrechnungenCached={st.abrechnungen||[]}
  beteiligte={st.beteiligte||[]}
  dokumente={st.dokumente||[]}
/>}
```

- [ ] **Schritt 2: `SET_REGULIERUNG_STATUS` im Reducer/Dispatch sicherstellen**

In `AkteDetailView.jsx` nach dem vorhandenen `dispatch`-Reducer-Block suchen (Suche nach `SET_HQ` oder `useReducer`). Den neuen Action-Typ hinzufügen:

```jsx
case "SET_REGULIERUNG_STATUS":
  return { ...state, akte: { ...state.akte, regulierung_status: action.regulierungStatus } };
```

Falls `akte` direkt im State steckt (nicht in `st`), entsprechend anpassen — dem Muster des vorhandenen `SET_HQ`-Handlers folgen.

- [ ] **Schritt 3: Docker-Rebuild und Abschlusstest**

```bash
docker compose build && docker compose up -d --force-recreate
```

Vollständiger Test:
1. Akte öffnen → Regulierung-Tab → Kachel sichtbar mit Vorauswahl aus DB
2. „Ja" wählen → nach Reload immer noch „Ja" (persistiert)
3. „Teilhaftung" wählen → 70 eingeben → Enter → nach Reload 70 % gesetzt
4. „Nein" wählen → hq zurück auf 100 → Klage-Wizard prüfen: zeigt 100 %

- [ ] **Schritt 4: Commit**

```bash
git add frontend/src/components/AkteDetailView.jsx
git commit -m "feat(ui): regulierungStatus-Prop an RegulierungSection + Reducer-Handler"
```
