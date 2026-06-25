# Action Board Redesign — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Das 3-Spalten-Action-Board durch ein 2×2-Kachel-Layout ersetzen mit vier spezialisierten Bereichen: Termine, Fristen, Wiedervorlagen, Posteingang.

**Architecture:** Drei neue Backend-Endpoints filtern `tblAktenWiedervorlagen` nach Grundcode-Kategorie. Im Frontend ersetzt `ActionBoardView.jsx` das bisherige Spalten-Layout durch vier eigenständige Kachel-Komponenten in `frontend/src/views/action_board/`.

**Tech Stack:** Python 3.9, Flask, pymssql (RA-MICRO read-only), SQLite, React 18, CSS-in-JS (inline styles, bestehendes Navy-Farbschema)

---

## Dateiübersicht

**Neu erstellen:**
- `frontend/src/views/action_board/tagesBadge.js` — Badge-Helper (Label + Farbe nach tage_bis)
- `frontend/src/views/action_board/TermineKachel.jsx` — Kachel oben links
- `frontend/src/views/action_board/FristenKachel.jsx` — Kachel oben rechts
- `frontend/src/views/action_board/WiedervorlagenKachel.jsx` — Kachel unten links
- `frontend/src/views/action_board/PosteingangKachel.jsx` — Kachel unten rechts

**Ändern:**
- `backend/routers/dashboard_routes.py` — 3 neue Hilfsfunktionen + 3 neue Routen
- `backend/tests/test_dashboard_uebersicht.py` — Tests für neue Endpoints
- `frontend/src/api.js` — 3 neue Einträge in `apiDashboard`
- `frontend/src/views/ActionBoardView.jsx` — Komplett-Umbau auf 2×2-Grid

---

## Grundcode-Kategorien (RA-MICRO)

```python
# Aus _RAMICRO_GRUENDE in dashboard_routes.py
TERMIN_CODES  = {9, 58, 60}          # Verhandlungstermin, Anhörungstermin, Entscheidung/Gericht
FRIST_CODES   = {21, 22, 31, 46, 75} # Klage, Urteil, Mahnbescheid, Berufung, Fristablauf
# Wiedervorlage = alles andere (5, 6, 11, 16, 23, 51, 54, 55, ...)
WV_AUSSCHLUSS = TERMIN_CODES | FRIST_CODES
```

---

## Task 1: Backend — `/dashboard/termine-heute`

**Files:**
- Modify: `backend/routers/dashboard_routes.py`
- Test: `backend/tests/test_dashboard_uebersicht.py`

- [ ] **Schritt 1: Failing Test schreiben**

Ans Ende von `TestDashboardUebersicht` in `test_dashboard_uebersicht.py` anfügen:

```python
def test_termine_heute_gibt_liste_zurueck(self):
    """GET /dashboard/termine-heute liefert eintraege-Liste (leer wenn RA-MICRO nicht verbunden)."""
    headers = self._auth_header()
    resp = self.client.get("/dashboard/termine-heute", headers=headers)
    self.assertEqual(resp.status_code, 200)
    data = resp.get_json()
    self.assertIn("eintraege", data)
    self.assertIsInstance(data["eintraege"], list)

def test_termine_heute_ohne_token_401(self):
    """Ohne Token sollte 401 zurückgegeben werden."""
    resp = self.client.get("/dashboard/termine-heute")
    self.assertEqual(resp.status_code, 401)

def test_termine_heute_felder(self):
    """Wenn Einträge vorhanden, müssen az, termin_art, termin_datum, tage_bis vorhanden sein."""
    # Dieser Test prüft nur die Struktur — RA-MICRO ist in Tests nicht verbunden,
    # daher bleibt die Liste leer. Der Test dokumentiert das erwartete Schema.
    headers = self._auth_header()
    resp = self.client.get("/dashboard/termine-heute", headers=headers)
    data = resp.get_json()
    for e in data["eintraege"]:
        for feld in ("az", "mandant", "termin_art", "termin_datum", "tage_bis"):
            self.assertIn(feld, e, f"Feld '{feld}' fehlt in Eintrag: {e}")
```

- [ ] **Schritt 2: Test ausführen — muss fehlschlagen**

```bash
cd "C:/Users/HAL9000/Documents/Projekt/Version 1.00/unfallakten"
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_termine_heute_gibt_liste_zurueck -v
```

Erwartetes Ergebnis: `FAILED` mit `404 != 200` (Endpoint existiert noch nicht).

- [ ] **Schritt 3: Hilfsfunktion + Route in `dashboard_routes.py` ergänzen**

Nach der `_RAMICRO_GRUENDE`-Definition (Zeile ~398) einfügen:

```python
_TERMIN_CODES  = {9, 58, 60}
_FRIST_CODES   = {21, 22, 31, 46, 75}
_WV_AUSSCHLUSS = _TERMIN_CODES | _FRIST_CODES

_TERMIN_LABELS = {
    9:  "Entscheidung/Gericht",
    58: "Verhandlungstermin",
    60: "Anhörungstermin",
}


def _bilde_az(row):
    # type: (dict) -> str
    az_roh = (row.get("az_roh") or "").strip()
    az_sb  = (row.get("az_sb")  or "").strip()
    if az_sb and not az_roh.upper().endswith(az_sb.upper()):
        return az_roh + az_sb
    return az_roh


def _parse_datum(raw, heute_dt):
    # type: (object, date) -> tuple
    """Gibt (iso_str, tage_bis) zurück."""
    try:
        if hasattr(raw, "date"):
            d = raw.date()
        elif isinstance(raw, str):
            d = date.fromisoformat(str(raw)[:10])
        else:
            d = raw
        return d.isoformat(), (d - heute_dt).days
    except Exception:
        return str(raw)[:10] if raw else "", 99


def _lade_termine_heute():
    # type: () -> list
    heute_dt   = date.today()
    morgen_dt  = heute_dt + timedelta(days=1)
    heute_s    = heute_dt.isoformat()
    morgen_s   = morgen_dt.isoformat()

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 30
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS termin_datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sBemerkung            AS bemerkung
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund IN (9, 58, 60)
                  AND CAST(w.dtWiedervorlage AS DATE)
                      BETWEEN %(heute)s AND %(morgen)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"heute": heute_s, "morgen": morgen_s})
            rows = cur.fetchall()

        import re as _re
        ergebnis = []
        for r in rows:
            az = _bilde_az(r)
            datum_iso, tage = _parse_datum(r.get("termin_datum"), heute_dt)
            code = r.get("grund_code")
            termin_art = _TERMIN_LABELS.get(int(code), "Termin") if code else "Termin"

            # Uhrzeit aus sBemerkung extrahieren (z.B. "10:00 Uhr" oder "14:30")
            bemerkung = (r.get("bemerkung") or "").strip()
            m = _re.search(r"(\d{1,2}:\d{2})", bemerkung)
            uhrzeit = m.group(1) if m else None

            ergebnis.append({
                "az":           az,
                "mandant":      (r.get("mandant") or "").strip(),
                "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                "termin_art":   termin_art,
                "termin_datum": datum_iso,
                "uhrzeit":      uhrzeit,
                "tage_bis":     tage,
            })
        return ergebnis

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("termine_heute Fehler: %s", e)
        return []
```

Dann die Route ergänzen (nach der `ramicro_fristen`-Route):

```python
@dashboard_bp.route("/termine-heute", methods=["GET"])
@login_erforderlich
def termine_heute():
    """Heutige + morgige Gerichtstermine und Anhörungen aus RA-MICRO."""
    return _j({"eintraege": _lade_termine_heute()})
```

- [ ] **Schritt 4: Test ausführen — muss grün sein**

```bash
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_termine_heute_gibt_liste_zurueck backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_termine_heute_ohne_token_401 -v
```

Erwartetes Ergebnis: beide `PASSED`.

- [ ] **Schritt 5: Commit**

```bash
git add backend/routers/dashboard_routes.py backend/tests/test_dashboard_uebersicht.py
git commit -m "feat(dashboard): GET /dashboard/termine-heute (Codes 9,58,60, heute+morgen)"
```

---

## Task 2: Backend — `/dashboard/fristen`

**Files:**
- Modify: `backend/routers/dashboard_routes.py`
- Test: `backend/tests/test_dashboard_uebersicht.py`

- [ ] **Schritt 1: Failing Test schreiben**

In `test_dashboard_uebersicht.py` anfügen:

```python
def test_fristen_gibt_liste_zurueck(self):
    """GET /dashboard/fristen liefert eintraege-Liste."""
    headers = self._auth_header()
    resp = self.client.get("/dashboard/fristen", headers=headers)
    self.assertEqual(resp.status_code, 200)
    data = resp.get_json()
    self.assertIn("eintraege", data)
    self.assertIsInstance(data["eintraege"], list)

def test_fristen_ohne_token_401(self):
    resp = self.client.get("/dashboard/fristen")
    self.assertEqual(resp.status_code, 401)
```

- [ ] **Schritt 2: Test ausführen — muss fehlschlagen**

```bash
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_fristen_gibt_liste_zurueck -v
```

Erwartetes Ergebnis: `FAILED` mit `404 != 200`.

- [ ] **Schritt 3: `_lade_fristen()` + Route in `dashboard_routes.py` ergänzen**

Nach `_lade_termine_heute()` einfügen:

```python
_FRIST_LABELS = {
    21: "Klage",
    22: "Urteil",
    31: "Mahnbescheid",
    46: "Berufung",
    75: "Fristablauf",
}


def _lade_fristen():
    # type: () -> list
    heute_dt   = date.today()
    plus14_dt  = heute_dt + timedelta(days=14)
    # überfällig: kein unteres Limit (alle), bis heute+14T
    heute_s   = heute_dt.isoformat()
    plus14_s  = plus14_dt.isoformat()

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 50
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS frist_datum,
                    w.iWiedervorlageGrund   AS grund_code
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund IN (21, 22, 31, 46, 75)
                  AND CAST(w.dtWiedervorlage AS DATE) <= %(plus14)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"plus14": plus14_s})
            rows = cur.fetchall()

        ergebnis = []
        for r in rows:
            az = _bilde_az(r)
            datum_iso, tage = _parse_datum(r.get("frist_datum"), heute_dt)
            code = r.get("grund_code")
            frist_art = _FRIST_LABELS.get(int(code), f"Grund {code}") if code else "Frist"

            ergebnis.append({
                "az":              az,
                "mandant":         (r.get("mandant") or "").strip(),
                "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                "frist_art":       frist_art,
                "frist_datum":     datum_iso,
                "tage_bis":        tage,
            })
        return ergebnis

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("fristen Fehler: %s", e)
        return []
```

Route ergänzen:

```python
@dashboard_bp.route("/fristen", methods=["GET"])
@login_erforderlich
def fristen():
    """Fristen aus RA-MICRO: Codes 21,22,31,46,75 — überfällig bis +14 Tage."""
    return _j({"eintraege": _lade_fristen()})
```

- [ ] **Schritt 4: Test ausführen — muss grün sein**

```bash
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_fristen_gibt_liste_zurueck backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_fristen_ohne_token_401 -v
```

Erwartetes Ergebnis: beide `PASSED`.

- [ ] **Schritt 5: Commit**

```bash
git add backend/routers/dashboard_routes.py backend/tests/test_dashboard_uebersicht.py
git commit -m "feat(dashboard): GET /dashboard/fristen (Codes 21,22,31,46,75, bis +14T)"
```

---

## Task 3: Backend — `/dashboard/wiedervorlagen`

**Files:**
- Modify: `backend/routers/dashboard_routes.py`
- Test: `backend/tests/test_dashboard_uebersicht.py`

- [ ] **Schritt 1: Failing Test schreiben**

```python
def test_wiedervorlagen_gibt_dict_zurueck(self):
    """GET /dashboard/wiedervorlagen liefert wv + ohne_wv Listen."""
    headers = self._auth_header()
    resp = self.client.get("/dashboard/wiedervorlagen", headers=headers)
    self.assertEqual(resp.status_code, 200)
    data = resp.get_json()
    self.assertIn("wv", data)
    self.assertIn("ohne_wv", data)
    self.assertIsInstance(data["wv"], list)
    self.assertIsInstance(data["ohne_wv"], list)

def test_wiedervorlagen_ohne_token_401(self):
    resp = self.client.get("/dashboard/wiedervorlagen")
    self.assertEqual(resp.status_code, 401)

def test_wiedervorlagen_ohne_wv_enthaelt_lokale_akte(self):
    """Eine Akte ohne RA-MICRO WV erscheint in ohne_wv (wenn RA-MICRO nicht verbunden)."""
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, status) VALUES (?, ?)",
            ("WV-TEST/26AS", "offen")
        )
        conn.commit()

    headers = self._auth_header()
    resp = self.client.get("/dashboard/wiedervorlagen", headers=headers)
    self.assertEqual(resp.status_code, 200)
    data = resp.get_json()
    az_liste = [e["az"] for e in data["ohne_wv"]]
    self.assertIn("WV-TEST/26AS", az_liste)
```

- [ ] **Schritt 2: Test ausführen — muss fehlschlagen**

```bash
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_wiedervorlagen_gibt_dict_zurueck -v
```

Erwartetes Ergebnis: `FAILED` mit `404 != 200`.

- [ ] **Schritt 3: `_lade_wiedervorlagen()` + Route ergänzen**

```python
def _lade_wiedervorlagen():
    # type: () -> dict
    heute_dt = date.today()
    heute_s  = heute_dt.isoformat()

    wv_eintraege     = []
    az_mit_aktiver_wv = set()  # AZ mit WV >= heute → nicht als "ohne WV" zeigen
    ramicro_erreichbar = True

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # Überfällige + heutige WV (alle Codes außer Termine + Fristen)
            cur.execute("""
                SELECT TOP 50
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sWiedervorlagegrund   AS grund_text
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund NOT IN (9, 21, 22, 31, 46, 58, 60, 75)
                  AND CAST(w.dtWiedervorlage AS DATE) <= %(heute)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"heute": heute_s})
            for r in cur.fetchall():
                az = _bilde_az(r)
                datum_iso, tage = _parse_datum(r.get("datum"), heute_dt)
                grund = (r.get("grund_text") or "").strip()
                if not grund and r.get("grund_code"):
                    grund = _RAMICRO_GRUENDE.get(int(r["grund_code"]), "Wiedervorlage")
                wv_eintraege.append({
                    "az":              az,
                    "mandant":         (r.get("mandant") or "").strip(),
                    "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                    "grund":           grund,
                    "datum":           datum_iso,
                    "tage_bis":        tage,
                    "hat_wv":          True,
                })

            # Alle AZ mit aktiver (heutiger oder zukünftiger) WV → für "ohne WV"-Filter
            cur.execute("""
                SELECT DISTINCT
                    a.sAktenNummer + a.sAktenSachbearbeiter AS az_full
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE CAST(w.dtWiedervorlage AS DATE) >= %(heute)s
            """, {"heute": heute_s})
            az_mit_aktiver_wv = {
                (r.get("az_full") or "").strip()
                for r in cur.fetchall()
            }

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        ramicro_erreichbar = False
    except Exception as e:
        logger.warning("wiedervorlagen Fehler: %s", e)
        ramicro_erreichbar = False

    # Lokale Akten ohne aktive WV in RA-MICRO
    ohne_wv = []
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT az, kurzbezeichnung
                FROM unfallakte
                WHERE status NOT IN ('abgeschlossen')
                ORDER BY geaendert_am DESC
                LIMIT 100
            """).fetchall()
        for r in rows:
            az = r["az"]
            # Wenn RA-MICRO nicht erreichbar: alle lokalen Akten als "ohne WV" zeigen
            if not ramicro_erreichbar or az not in az_mit_aktiver_wv:
                ohne_wv.append({
                    "az":              az,
                    "mandant":         "",
                    "kurzbezeichnung": r["kurzbezeichnung"] or "",
                    "grund":           None,
                    "datum":           None,
                    "tage_bis":        None,
                    "hat_wv":          False,
                })
    except Exception as e:
        logger.warning("ohne_wv Fehler: %s", e)

    return {"wv": wv_eintraege, "ohne_wv": ohne_wv[:10]}
```

Route ergänzen:

```python
@dashboard_bp.route("/wiedervorlagen", methods=["GET"])
@login_erforderlich
def wiedervorlagen():
    """WV überfällig+heute aus RA-MICRO + lokale Akten ohne aktive WV."""
    return _j(_lade_wiedervorlagen())
```

- [ ] **Schritt 4: Tests ausführen — müssen grün sein**

```bash
python -m pytest backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_wiedervorlagen_gibt_dict_zurueck backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_wiedervorlagen_ohne_token_401 backend/tests/test_dashboard_uebersicht.py::TestDashboardUebersicht::test_wiedervorlagen_ohne_wv_enthaelt_lokale_akte -v
```

Erwartetes Ergebnis: alle drei `PASSED`.

- [ ] **Schritt 5: Commit**

```bash
git add backend/routers/dashboard_routes.py backend/tests/test_dashboard_uebersicht.py
git commit -m "feat(dashboard): GET /dashboard/wiedervorlagen (WV überfällig+heute + ohne-WV)"
```

---

## Task 4: Frontend — `api.js` aktualisieren

**Files:**
- Modify: `frontend/src/api.js` (Zeilen ~880–891)

- [ ] **Schritt 1: `apiDashboard` erweitern**

Den bestehenden Block:

```javascript
export const apiDashboard = {
  actionItems: () => request('/dashboard/action-items'),
  onboardingOffen: () => request("/dashboard/onboarding-offen"),
  nachrichtenNeu: () => request("/dashboard/nachrichten-neu"),
  ramicroFristen: () => request("/dashboard/ramicro-fristen"),
};
```

ersetzen durch:

```javascript
export const apiDashboard = {
  actionItems:    () => request('/dashboard/action-items'),
  onboardingOffen: () => request("/dashboard/onboarding-offen"),
  nachrichtenNeu: () => request("/dashboard/nachrichten-neu"),
  ramicroFristen: () => request("/dashboard/ramicro-fristen"),
  termineHeute:   () => request("/dashboard/termine-heute"),
  fristen:        () => request("/dashboard/fristen"),
  wiedervorlagen: () => request("/dashboard/wiedervorlagen"),
};
```

- [ ] **Schritt 2: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(api): apiDashboard um termine-heute, fristen, wiedervorlagen ergänzt"
```

---

## Task 5: Frontend — `tagesBadge.js` + `TermineKachel.jsx`

**Files:**
- Create: `frontend/src/views/action_board/tagesBadge.js`
- Create: `frontend/src/views/action_board/TermineKachel.jsx`

- [ ] **Schritt 1: Verzeichnis anlegen**

```bash
mkdir "frontend/src/views/action_board"
```

- [ ] **Schritt 2: `tagesBadge.js` erstellen**

```javascript
// Gibt { label, color, bg } für ein tage_bis-Zahl zurück
export function tagesBadge(tage) {
  if (tage === null || tage === undefined) return null;
  if (tage <= 0) {
    const label = tage === 0 ? "HEUTE" : `${tage}T`;
    return { label, color: "#ffffff", bg: "#dc2626" };
  }
  return { label: `+${tage}T`, color: "#9ca3af", bg: "#374151" };
}
```

- [ ] **Schritt 3: `TermineKachel.jsx` erstellen**

```jsx
import React from "react";

const S = {
  kachel: {
    background: "#1e1b4b",
    border: "1px solid #4c1d95",
    borderRadius: 6,
    padding: 12,
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  titel: {
    color: "#a78bfa",
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
  },
  badge: {
    background: "#7c3aed",
    color: "white",
    borderRadius: 10,
    padding: "2px 8px",
    fontSize: 10,
    fontWeight: 600,
  },
  sectionLabel: {
    color: "#6b7280",
    fontSize: 9,
    fontWeight: 700,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    marginBottom: 4,
    marginTop: 8,
    paddingLeft: 2,
  },
  eintrag: (gedimmt) => ({
    background: gedimmt ? "#201d3a" : "#2d2463",
    borderRadius: 4,
    padding: "8px 10px",
    marginBottom: 6,
    cursor: "pointer",
    borderLeft: `3px solid ${gedimmt ? "#4c1d95" : "#7c3aed"}`,
    opacity: gedimmt ? 0.85 : 1,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
  }),
  art: { color: "#c4b5fd", fontSize: 10, fontWeight: 600, marginBottom: 2 },
  bezeichnung: { color: "#e2e8f0", fontSize: 12, fontWeight: 500 },
  az: { color: "#94a3b8", fontSize: 11 },
  uhrzeit: { color: "#a78bfa", fontSize: 14, fontWeight: 700, whiteSpace: "nowrap" },
  leer: { color: "#4ade80", fontSize: 12, padding: "12px 0", textAlign: "center" },
};

export default function TermineKachel({ eintraege, onOpenAkte }) {
  const heute = eintraege.filter((e) => e.tage_bis === 0);
  const morgen = eintraege.filter((e) => e.tage_bis === 1);
  const anzahl = eintraege.length;

  function handleClick(e) {
    if (onOpenAkte) onOpenAkte(e.az);
  }

  if (anzahl === 0) {
    return (
      <div style={S.kachel}>
        <div style={S.header}>
          <span style={S.titel}>📅 Termine</span>
        </div>
        <div style={S.leer}>Heute keine Termine</div>
      </div>
    );
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>📅 Termine</span>
        <span style={S.badge}>{anzahl}</span>
      </div>

      {heute.length > 0 && (
        <>
          <div style={S.sectionLabel}>Heute</div>
          {heute.map((e) => (
            <div key={e.az + e.termin_datum} style={S.eintrag(false)} onClick={() => handleClick(e)}>
              <div>
                <div style={S.art}>{e.termin_art.toUpperCase()}</div>
                <div style={S.bezeichnung}>{e.kurzbezeichnung || e.mandant}</div>
                <div style={S.az}>{e.az}</div>
              </div>
              <div style={S.uhrzeit}>{e.uhrzeit || e.termin_datum?.slice(5) || ""}</div>
            </div>
          ))}
        </>
      )}

      {morgen.length > 0 && (
        <>
          <div style={{ ...S.sectionLabel, marginTop: heute.length > 0 ? 8 : 0 }}>Morgen</div>
          {morgen.map((e) => (
            <div key={e.az + e.termin_datum} style={S.eintrag(true)} onClick={() => handleClick(e)}>
              <div>
                <div style={{ ...S.art, color: "#9ca3af" }}>{e.termin_art.toUpperCase()}</div>
                <div style={{ ...S.bezeichnung, color: "#cbd5e1" }}>{e.kurzbezeichnung || e.mandant}</div>
                <div style={{ ...S.az, color: "#6b7280" }}>{e.az}</div>
              </div>
              <div style={{ ...S.uhrzeit, color: "#9ca3af" }}>{e.uhrzeit || ""}</div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
```

- [ ] **Schritt 4: Commit**

```bash
git add frontend/src/views/action_board/
git commit -m "feat(ui): TermineKachel + tagesBadge helper"
```

---

## Task 6: Frontend — `FristenKachel.jsx`

**Files:**
- Create: `frontend/src/views/action_board/FristenKachel.jsx`

- [ ] **Schritt 1: `FristenKachel.jsx` erstellen**

```jsx
import React from "react";

const ROT_BG     = "#3b1c0c";
const ROT_BORDER = "#dc2626";
const GRAU_BG    = "#231f1d";
const GRAU_BORDER = "#475569";

function Badge({ tage }) {
  const istKritisch = tage <= 0;
  return (
    <span style={{
      background: istKritisch ? ROT_BORDER : "#374151",
      color: "white",
      borderRadius: 4,
      padding: "2px 6px",
      fontSize: 10,
      fontWeight: 700,
      whiteSpace: "nowrap",
    }}>
      {tage === 0 ? "HEUTE" : tage < 0 ? `${tage}T` : `+${tage}T`}
    </span>
  );
}

function FristEintrag({ e, onOpenAkte }) {
  const kritisch = e.tage_bis <= 0;
  return (
    <div
      onClick={() => onOpenAkte && onOpenAkte(e.az)}
      style={{
        background: kritisch ? ROT_BG : GRAU_BG,
        borderRadius: 4,
        padding: "8px 10px",
        marginBottom: 5,
        cursor: "pointer",
        borderLeft: `3px solid ${kritisch ? ROT_BORDER : GRAU_BORDER}`,
        opacity: kritisch ? 1 : 0.75,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
      }}
    >
      <div>
        <div style={{ color: kritisch ? "#fca5a5" : "#9ca3af", fontSize: 10, fontWeight: 600, marginBottom: 2 }}>
          {e.frist_art.toUpperCase()}
          {e.tage_bis < 0 ? ` · ${Math.abs(e.tage_bis)} TAG${Math.abs(e.tage_bis) === 1 ? "" : "E"} ÜBERFÄLLIG` : e.tage_bis === 0 ? " · HEUTE FÄLLIG" : ""}
        </div>
        <div style={{ color: "#e2e8f0", fontSize: 12, fontWeight: 500 }}>{e.kurzbezeichnung || e.mandant}</div>
        <div style={{ color: "#94a3b8", fontSize: 11 }}>{e.az}</div>
      </div>
      <Badge tage={e.tage_bis} />
    </div>
  );
}

export default function FristenKachel({ eintraege, onOpenAkte }) {
  const kritisch   = eintraege.filter((e) => e.tage_bis <= 0);
  const demnächst  = eintraege.filter((e) => e.tage_bis > 0);

  const S = {
    kachel: { background: "#1c1917", border: "1px solid #7c2d12", borderRadius: 6, padding: 12 },
    header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
    titel:  { color: "#fb923c", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" },
    badge:  { background: "#dc2626", color: "white", borderRadius: 10, padding: "2px 8px", fontSize: 10, fontWeight: 600 },
    label:  { color: "#6b7280", fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4, paddingLeft: 2 },
    leer:   { color: "#4ade80", fontSize: 12, padding: "12px 0", textAlign: "center" },
  };

  if (eintraege.length === 0) {
    return (
      <div style={S.kachel}>
        <div style={S.header}><span style={S.titel}>⏰ Fristen</span></div>
        <div style={S.leer}>Keine Fristen in den nächsten 14 Tagen</div>
      </div>
    );
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>⏰ Fristen</span>
        {kritisch.length > 0 && (
          <span style={S.badge}>{kritisch.length} {kritisch.length === 1 ? "kritisch" : "kritisch"}</span>
        )}
      </div>

      {kritisch.length > 0 && (
        <>
          <div style={{ ...S.label, color: "#fca5a5" }}>⚠ Handlungsbedarf</div>
          {kritisch.map((e) => <FristEintrag key={e.az + e.frist_datum} e={e} onOpenAkte={onOpenAkte} />)}
        </>
      )}

      {demnächst.length > 0 && (
        <>
          <div style={{ ...S.label, marginTop: kritisch.length > 0 ? 10 : 0 }}>Demnächst</div>
          {demnächst.map((e) => <FristEintrag key={e.az + e.frist_datum} e={e} onOpenAkte={onOpenAkte} />)}
        </>
      )}
    </div>
  );
}
```

- [ ] **Schritt 2: Commit**

```bash
git add frontend/src/views/action_board/FristenKachel.jsx
git commit -m "feat(ui): FristenKachel (heute+überfällig=rot, demnächst=grau)"
```

---

## Task 7: Frontend — `WiedervorlagenKachel.jsx`

**Files:**
- Create: `frontend/src/views/action_board/WiedervorlagenKachel.jsx`

- [ ] **Schritt 1: `WiedervorlagenKachel.jsx` erstellen**

```jsx
import React from "react";

function WvEintrag({ e, onOpenAkte }) {
  const istUeberfaellig = e.hat_wv && e.tage_bis < 0;
  const istHeute        = e.hat_wv && e.tage_bis === 0;
  const ohneWv          = !e.hat_wv;

  let borderColor = "#f59e0b"; // heute
  if (istUeberfaellig) borderColor = "#dc2626";
  if (ohneWv)          borderColor = "#6366f1";

  let badgeContent = null;
  if (istUeberfaellig) badgeContent = (
    <span style={{ background: "#dc2626", color: "white", borderRadius: 4, padding: "1px 5px", fontSize: 10, fontWeight: 600 }}>
      {e.tage_bis}T
    </span>
  );
  if (istHeute) badgeContent = (
    <span style={{ background: "#f59e0b", color: "#1c1917", borderRadius: 4, padding: "1px 5px", fontSize: 10, fontWeight: 600 }}>
      HEUTE
    </span>
  );
  if (ohneWv) badgeContent = (
    <span style={{ color: "#818cf8", fontSize: 10, fontWeight: 600 }}>⚠ keine WV</span>
  );

  return (
    <div
      onClick={() => onOpenAkte && onOpenAkte(e.az)}
      style={{
        background: "#132237",
        borderRadius: 4,
        padding: "7px 10px",
        marginBottom: 5,
        cursor: "pointer",
        borderLeft: `3px solid ${borderColor}`,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}
    >
      <div>
        <div style={{ color: "#e2e8f0", fontSize: 12, fontWeight: 500 }}>{e.kurzbezeichnung || e.mandant || e.az}</div>
        <div style={{ color: "#94a3b8", fontSize: 10 }}>
          {e.grund ? `${e.grund} · ` : ""}{e.az}
        </div>
      </div>
      {badgeContent}
    </div>
  );
}

export default function WiedervorlagenKachel({ wv, ohne_wv, onOpenAkte }) {
  const ueberfaellig = (wv || []).filter((e) => e.tage_bis < 0);
  const heute        = (wv || []).filter((e) => e.tage_bis === 0);
  const gesamt       = (wv || []).length;

  const S = {
    kachel: { background: "#0c1929", border: "1px solid #1e3a5f", borderRadius: 6, padding: 12 },
    header: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
    titel:  { color: "#60a5fa", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" },
    badge:  { background: "#1d4ed8", color: "white", borderRadius: 10, padding: "2px 8px", fontSize: 10, fontWeight: 600 },
    label:  { color: "#6b7280", fontSize: 9, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 4, paddingLeft: 2 },
    leer:   { color: "#4ade80", fontSize: 12, padding: "12px 0", textAlign: "center" },
  };

  const alleOhneWv = ohne_wv || [];
  const hatInhalt  = gesamt > 0 || alleOhneWv.length > 0;

  if (!hatInhalt) {
    return (
      <div style={S.kachel}>
        <div style={S.header}><span style={S.titel}>🔁 Wiedervorlagen</span></div>
        <div style={S.leer}>Alle Wiedervorlagen erledigt</div>
      </div>
    );
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>🔁 Wiedervorlagen</span>
        {gesamt > 0 && <span style={S.badge}>{gesamt} offen</span>}
      </div>

      {ueberfaellig.length > 0 && (
        <>
          <div style={S.label}>Überfällig</div>
          {ueberfaellig.map((e) => <WvEintrag key={e.az + e.datum} e={e} onOpenAkte={onOpenAkte} />)}
        </>
      )}

      {heute.length > 0 && (
        <>
          <div style={{ ...S.label, marginTop: ueberfaellig.length > 0 ? 8 : 0 }}>Heute fällig</div>
          {heute.map((e) => <WvEintrag key={e.az + e.datum} e={e} onOpenAkte={onOpenAkte} />)}
        </>
      )}

      {alleOhneWv.length > 0 && (
        <>
          <div style={{ ...S.label, marginTop: (gesamt > 0) ? 8 : 0 }}>Keine Wiedervorlage gesetzt</div>
          {alleOhneWv.map((e) => <WvEintrag key={e.az} e={e} onOpenAkte={onOpenAkte} />)}
        </>
      )}
    </div>
  );
}
```

- [ ] **Schritt 2: Commit**

```bash
git add frontend/src/views/action_board/WiedervorlagenKachel.jsx
git commit -m "feat(ui): WiedervorlagenKachel (überfällig+heute+ohne-WV)"
```

---

## Task 8: Frontend — `PosteingangKachel.jsx`

**Files:**
- Create: `frontend/src/views/action_board/PosteingangKachel.jsx`

- [ ] **Schritt 1: `PosteingangKachel.jsx` erstellen**

```jsx
import React, { useState } from "react";

const KONTO_FARBE = {
  "unfall":    "#60a5fa",
  "termin":    "#a78bfa",
  "bussgeld":  "#fb923c",
};

function kontoKuerzel(absender) {
  if (!absender) return "unfall";
  if (absender.includes("termin@"))   return "termin";
  if (absender.includes("bussgeld@")) return "bussgeld";
  return "unfall";
}

export default function PosteingangKachel({ eintraege, onOpenEmail, onAlleOeffnen }) {
  const [aktivesKonto, setAktivesKonto] = useState("unfall");

  const konten = ["unfall", "termin", "bussgeld"];
  const zaehler = {};
  konten.forEach((k) => {
    zaehler[k] = (eintraege || []).filter((e) => kontoKuerzel(e.absender) === k).length;
  });

  const gefiltert = (eintraege || []).filter(
    (e) => kontoKuerzel(e.absender) === aktivesKonto
  );
  const gesamt = (eintraege || []).length;

  const S = {
    kachel:  { background: "#0a1f1a", border: "1px solid #14532d", borderRadius: 6, padding: 12 },
    header:  { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 },
    titel:   { color: "#4ade80", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" },
    badge:   { background: "#15803d", color: "white", borderRadius: 10, padding: "2px 8px", fontSize: 10, fontWeight: 600 },
    tabs:    { display: "flex", gap: 6, marginBottom: 8 },
    allLink: { textAlign: "center", paddingTop: 6, color: "#22c55e", fontSize: 11, cursor: "pointer", opacity: 0.7 },
    leer:    { color: "#6b7280", fontSize: 12, padding: "12px 0", textAlign: "center" },
  };

  function tabStyle(konto) {
    const aktiv = konto === aktivesKonto;
    return {
      background: aktiv ? "#14532d" : "#1a2e1a",
      color: aktiv ? "#4ade80" : "#6b7280",
      borderRadius: 3,
      padding: "3px 8px",
      fontSize: 10,
      fontWeight: aktiv ? 600 : 400,
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      gap: 4,
    };
  }

  return (
    <div style={S.kachel}>
      <div style={S.header}>
        <span style={S.titel}>✉ Posteingang</span>
        {gesamt > 0 && <span style={S.badge}>{gesamt} neu</span>}
      </div>

      <div style={S.tabs}>
        {konten.map((k) => (
          <div key={k} style={tabStyle(k)} onClick={() => setAktivesKonto(k)}>
            {k}@
            {zaehler[k] > 0 && (
              <span style={{ background: k === aktivesKonto ? "#dc2626" : "#374151", color: "white", borderRadius: 8, padding: "0 4px", fontSize: 9 }}>
                {zaehler[k]}
              </span>
            )}
          </div>
        ))}
      </div>

      {gefiltert.length === 0 ? (
        <div style={S.leer}>Keine neuen E-Mails</div>
      ) : (
        gefiltert.slice(0, 5).map((e) => (
          <div
            key={e.log_id}
            onClick={() => onOpenEmail && onOpenEmail({ az: e.az, logId: e.log_id })}
            style={{
              background: "#0d2b1f",
              borderRadius: 4,
              padding: "8px 10px",
              marginBottom: 5,
              cursor: "pointer",
              borderLeft: "3px solid #16a34a",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ color: "#e2e8f0", fontSize: 12, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {e.betreff || "(kein Betreff)"}
              </div>
              <div style={{ color: "#6b7280", fontSize: 10 }}>
                {e.absender} {e.az ? `· ${e.az}` : ""}
              </div>
            </div>
            <div style={{ color: "#4b5563", fontSize: 10, whiteSpace: "nowrap", marginLeft: 8 }}>
              {e.datum ? new Date(e.datum).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : ""}
            </div>
          </div>
        ))
      )}

      <div style={S.allLink} onClick={onAlleOeffnen}>→ Alle E-Mails öffnen</div>
    </div>
  );
}
```

- [ ] **Schritt 2: Commit**

```bash
git add frontend/src/views/action_board/PosteingangKachel.jsx
git commit -m "feat(ui): PosteingangKachel mit Tab-Leiste je Postfach"
```

---

## Task 9: Frontend — `ActionBoardView.jsx` umbauen

**Files:**
- Modify: `frontend/src/views/ActionBoardView.jsx`

- [ ] **Schritt 1: `ActionBoardView.jsx` komplett ersetzen**

Die gesamte Datei durch folgendes ersetzen:

```jsx
import React, { useEffect, useState } from "react";
import { apiDashboard } from "../api";
import TermineKachel        from "./action_board/TermineKachel";
import FristenKachel        from "./action_board/FristenKachel";
import WiedervorlagenKachel from "./action_board/WiedervorlagenKachel";
import PosteingangKachel    from "./action_board/PosteingangKachel";

export default function ActionBoardView({ onOpenAkte, onOpenEmail, onAlleEmailsOeffnen }) {
  const [termine,       setTermine]       = useState([]);
  const [fristen,       setFristen]       = useState([]);
  const [wvDaten,       setWvDaten]       = useState({ wv: [], ohne_wv: [] });
  const [nachrichten,   setNachrichten]   = useState([]);
  const [ladeZeit,      setLadeZeit]      = useState(null);
  const [laedtGerade,   setLaedtGerade]   = useState(false);

  async function laden() {
    setLaedtGerade(true);
    const [r1, r2, r3, r4] = await Promise.allSettled([
      apiDashboard.termineHeute(),
      apiDashboard.fristen(),
      apiDashboard.wiedervorlagen(),
      apiDashboard.nachrichtenNeu(),
    ]);

    if (r1.status === "fulfilled") setTermine(r1.value?.eintraege ?? []);
    if (r2.status === "fulfilled") setFristen(r2.value?.eintraege ?? []);
    if (r3.status === "fulfilled") setWvDaten(r3.value ?? { wv: [], ohne_wv: [] });
    if (r4.status === "fulfilled") setNachrichten(r4.value?.eintraege ?? []);

    setLadeZeit(new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    setLaedtGerade(false);
  }

  useEffect(() => { laden(); }, []);

  const heute = new Date().toLocaleDateString("de-DE", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });

  return (
    <div style={{ background: "#1B2A4A", borderRadius: 8, padding: 16, fontFamily: "'Segoe UI', sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ color: "#e2e8f0", fontSize: 15, fontWeight: 600 }}>
          Tagesübersicht — {heute}
        </div>
        <button
          onClick={laden}
          disabled={laedtGerade}
          style={{ background: "none", border: "none", color: "#60a5fa", fontSize: 12, cursor: "pointer", opacity: laedtGerade ? 0.4 : 0.7 }}
        >
          {laedtGerade ? "Lädt..." : `↻ Aktualisieren${ladeZeit ? ` (${ladeZeit})` : ""}`}
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <TermineKachel
          eintraege={termine}
          onOpenAkte={onOpenAkte}
        />
        <FristenKachel
          eintraege={fristen}
          onOpenAkte={onOpenAkte}
        />
        <WiedervorlagenKachel
          wv={wvDaten.wv}
          ohne_wv={wvDaten.ohne_wv}
          onOpenAkte={onOpenAkte}
        />
        <PosteingangKachel
          eintraege={nachrichten}
          onOpenEmail={onOpenEmail}
          onAlleOeffnen={onAlleEmailsOeffnen}
        />
      </div>
    </div>
  );
}
```

- [ ] **Schritt 2: In `App.jsx` prüfen, ob Props-Namen stimmen**

In `App.jsx` nach dem `<ActionBoardView`-Tag suchen. Die bisherigen Props waren `onOpenEmail` und ähnliches. Sicherstellen dass folgende Props übergeben werden:

```jsx
<ActionBoardView
  onOpenAkte={(az) => oeffneAkte(az)}
  onOpenEmail={({ az, logId }) => oeffneEmail(az, logId)}
  onAlleEmailsOeffnen={() => navigiereZuEmailImport()}
/>
```

Die genauen Handler-Namen in `App.jsx` anpassen — die Funktion `oeffneAkte`, `oeffneEmail`, `navigiereZuEmailImport` entsprechen den tatsächlichen Funktionsnamen in `App.jsx`. Nicht umbenennen, nur die Props-Übergabe sicherstellen.

- [ ] **Schritt 3: Im Browser testen**

```bash
# Docker-Container neu starten (bei Windows HMR kaputt — immer restart nötig)
docker compose restart frontend
```

Dann `http://localhost:5173` (oder konfigurierten Port) öffnen und prüfen:
- Alle 4 Kacheln erscheinen im 2×2-Grid
- Kacheln laden ohne Fehlermeldung (leere Zustände zeigen grüne Texte)
- Klick auf Eintrag öffnet Akten-Detailansicht
- E-Mail-Kachel zeigt Tab-Leiste mit je Postfach-Badge

- [ ] **Schritt 4: Commit**

```bash
git add frontend/src/views/ActionBoardView.jsx
git commit -m "feat(ui): ActionBoardView Umbau auf 2x2-Kacheln (Termine/Fristen/WV/Posteingang)"
```

---

## Selbstprüfung

**Spec-Abdeckung:**
- ✅ Termine heute + morgen — `TermineKachel` + `/dashboard/termine-heute`
- ✅ Fristen (keine Wiedervorlagen) bis +14T, heute/überfällig = rot — `FristenKachel` + `/dashboard/fristen`
- ✅ Wiedervorlagen nur überfällig+heute+ohne-WV — `WiedervorlagenKachel` + `/dashboard/wiedervorlagen`
- ✅ E-Mail Schnellzugriff mit Tab-Leiste — `PosteingangKachel`
- ✅ Klick → Akten-Detailansicht

**Offene Punkte:**
- Uhrzeit bei Terminen: kommt aus `sBemerkung` per Regex — wenn RA-MICRO dort keine Uhrzeit trägt, wird nur das Datum angezeigt (akzeptables Fallback)
- `ohne_wv`-Mandant-Name: fehlt (unfallakte hat kein `mandant_name`-Feld), es wird `kurzbezeichnung` aus RA-MICRO-Cache gezeigt — ausreichend zur Identifikation
