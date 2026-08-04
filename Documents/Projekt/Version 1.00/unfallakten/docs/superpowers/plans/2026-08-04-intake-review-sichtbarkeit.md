# Intake-Review-Sichtbarkeit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In der Dokumentenkachel einer Akte die noch nicht freigegebenen Intake-Dokumente dieser Akte mit Status-Badge und Link zur ReviewQueue anzeigen.

**Architecture:** Neuer read-only Endpoint `GET /akten/<akte_az>/intake-pending` am `akten_bp` liest `intake_dokumente` + erste `zustellung` und ordnet je Dokument über eine AZ-Präzedenz (Signal-AZ → Upload-Referenz → Matching-Kandidat) der angefragten Akte zu. Das Frontend lädt die Liste beim Öffnen der Akte, rendert je Eintrag ein Status-Badge und einen „Zur Review →"-Link. Ein Callback `onOpenReview(intakeId)` reicht die ID über `AkteDetailView` an `App` durch, das per bestehendem `pending…`-Muster in die `ReviewQueueView` navigiert und dort das Dokument öffnet.

**Tech Stack:** Flask (Blueprint, SQLite via `get_connection`), React (Vitest/Testing-Library), bestehende `theme.js`-Farbtokens.

## Global Constraints

- **RA-MICRO ist read-only** — niemals in die RA-MICRO SQL Server DB schreiben, nur SQLite lesen.
- **Zielsprache Deutsch** — UI-Texte und Kommunikation auf Deutsch.
- **Keine unnötigen Abstraktionen** — nur umsetzen, was die Spec verlangt.
- **Keine Kommentare** im Code außer bei nicht-offensichtlichem Verhalten.
- **Keine Roh-Hexwerte** im Frontend — Farben ausschließlich über `theme.js`-Tokens (`T.amberBg`, `T.redBg`, `T.textMuted`, `T.surface` …).
- **AZ-Normalisierung** muss dieselbe Basis-Logik nutzen wie das bestehende Matching (`intake_routes._basis_az`: streift ein 2–3-stelliges SB-Kürzel am Ende ab, nur bei AZ mit `/`).
- **Backend-Tests im Container, im Vordergrund:** `docker exec unfallakten-backend-dev python -m pytest <pfad> -v` (kein Background).
- **Frontend-Tests auf dem Host:** `cd frontend && npm test` (Vitest). Frontend ist NICHT im Backend-Container gemountet.
- **Git-Wurzel = Home** (`C:\Users\HAL9000`) → NIE `git add -A`, immer nur konkrete Pfade.
- **Kein Live-Polling** der Badges (Spec §7). Liste lädt beim Öffnen der Akte.
- Filter des Endpoints: `queue_status != 'freigegeben' AND verworfen_am IS NULL`.
- Antwort-Felder je Eintrag: `intake_id`, `bezeichnung`, `klasse`, `queue_status`, `erstellt_am`.
- START_HEAD für den SDD-Ledger: `4c711265`.

---

## File Structure

- `backend/routers/akten_routes.py` — **modifizieren**: neuer Endpoint `intake_pending()` + Helfer `_basis_az()` / `_abgeleiteter_az()`. (Das `akten_bp` hat bereits `url_prefix="/akten"` — perfekter Sitz; `dokumente_bp` scheidet aus, dessen Prefix ist `/akten/<path:akte_id>/dokumente`.)
- `backend/tests/test_akten_intake_pending.py` — **neu**: Router-Test (4 Fälle der Spec §8).
- `frontend/src/api.js` — **modifizieren**: `dokumente.intakePending(az)`.
- `frontend/src/sections/IntakePendingListe.jsx` — **neu**: präsentationale, testbare Komponente + Pure-Funktion `intakeBadge(status)`.
- `frontend/src/sections/IntakePendingListe.test.jsx` — **neu**: Vitest-Komponententest (Badges + Link-Callback + leere Liste).
- `frontend/src/sections/DokumenteSection.jsx` — **modifizieren**: Liste laden, oben rendern, Prop `onOpenReview` durchreichen.
- `frontend/src/components/AkteDetailView.jsx` — **modifizieren**: Prop `onOpenReview` annehmen + an `DokumenteSection` durchreichen.
- `frontend/src/views/ReviewQueueView.jsx` — **modifizieren**: Prop `initialIntakeId` → `setAktivId` beim Mount.
- `frontend/src/App.jsx` — **modifizieren**: State `pendingReviewIntakeId`, Callback `onOpenReview`, Props an `AkteDetailView` + `ReviewQueueView`.

---

## Task 1: Backend-Endpoint `GET /akten/<akte_az>/intake-pending`

**Files:**
- Modify: `backend/routers/akten_routes.py` (Imports oben; neue Funktionen ans Ende der Datei)
- Test: `backend/tests/test_akten_intake_pending.py` (neu)

**Interfaces:**
- Produces: `GET /akten/<path:akte_az>/intake-pending` → JSON-Array `[{ "intake_id": int, "bezeichnung": str, "klasse": str|null, "queue_status": str, "erstellt_am": str }]`. Auth via `@login_erforderlich`.
- Consumes: bestehende `intake_dokumente`-Spalten (`id, klasse, queue_status, erstellt_am, bezeichnung, parse_json, verworfen_am`) und `zustellungen` (`intake_dokument_id, signale_json, roh_referenz`).

**Kontext (aus der Recherche, verbatim):**
- `akten_bp = Blueprint("akten", __name__, url_prefix="/akten")` (Zeile 37). Vorhandene Imports: `from flask import Blueprint, request, jsonify, g`, `from ..auth.middleware import login_erforderlich, nur_admin`, `from ..db.database import get_connection`. Helfer `_j(daten, status=200)` und `_err(msg, status, **extra)` existieren bereits (Z. 42-46). `import re` fehlt noch.
- Referenz-Normalisierung (`intake_routes.py:65-75`):
  ```python
  def _basis_az(az: str) -> str:
      az = (az or "").strip()
      if "/" in az:
          az = re.sub(r"[A-Za-z]{2,3}$", "", az).strip()
      return az
  ```
- Upload schreibt `signale["az"] = ziel_akte` (roher akte_id) **und** `roh_referenz = f"upload/akte:{akte_id}"`; E-Akte schreibt `signale["az"] = akte_az`. E-Mail hat keinen Signal-AZ, nur `parse_json.$.akten_kandidaten[0].akte_az`.
- `queue_status` CHECK: `('neu','laeuft','bereit_zur_review','pipeline_fehler','freigegeben')`. `verworfen_am` existiert (Migration 53). `bezeichnung` existiert (Migration 59).

- [ ] **Step 1: Testdatei anlegen mit Setup + Fixtures (kopiert das etablierte Muster aus `test_intake_routes.py`)**

Create `backend/tests/test_akten_intake_pending.py`:

```python
import importlib
import json
import os
import sys
import tempfile
import unittest

_tmp_dir = tempfile.mkdtemp(prefix="akten_intake_pending_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ip_{test_id}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["UPLOAD_DIR"] = os.path.join(_tmp_dir, f"uploads_{test_id}")

    import backend.db.database as db_mod
    import backend.models.benutzer as ben_mod
    import backend.models.akte as akte_mod
    import backend.models.dokument as dok_mod
    import backend.auth.jwt_handler as jwt_mod
    import backend.auth.middleware as mw_mod
    import backend.auth.service as svc_mod
    import backend.routers.auth_routes as routes_mod
    import backend.app as app_mod
    for m in (db_mod, ben_mod, akte_mod, dok_mod,
              jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
        importlib.reload(m)
    app = app_mod.erstelle_app({"TESTING": True})
    return app.test_client()


def _auth_header(client):
    r = client.post("/auth/login", json={
        "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
        "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
    })
    assert r.status_code == 200, f"Login failed: {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['access_token']}"}


def _seed_akte(az="44/22"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2022-04-27', 'offen')", (az,),
        )


def _lege_intake_an(sha_suffix, klasse="abrechnungsschreiben",
                    queue_status="bereit_zur_review", parse_json=None,
                    bezeichnung=None, verworfen_am=None):
    from backend.db.database import get_connection
    sha = (sha_suffix * 64)[:64]
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO intake_dokumente "
            "(sha256, arbeitskopie_pfad, klasse, klasse_quelle, konfidenz, "
            " queue_status, parse_json, registry_version, bezeichnung, "
            " verworfen_am) "
            "VALUES (?, '/tmp/x.pdf', ?, 'auto', 0.9, ?, ?, 'v1', ?, ?)",
            (sha, klasse, queue_status, parse_json, bezeichnung, verworfen_am),
        )
        return cur.lastrowid


def _lege_zustellung_an(intake_id, quelle, signale=None, roh_referenz=None):
    from backend.db.database import get_connection
    signale_json = json.dumps(signale, ensure_ascii=False) if signale else None
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO zustellungen "
            "(intake_dokument_id, quelle, signale_json, roh_referenz) "
            "VALUES (?, ?, ?, ?)",
            (intake_id, quelle, signale_json, roh_referenz),
        )


class TestIntakePending(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.headers = _auth_header(self.client)
        _seed_akte("44/22")

    def test_eakte_signal_az_wird_zugeordnet(self):
        did = _lege_intake_an("a")
        _lege_zustellung_an(did, "eakte", signale={"az": "44/22"})
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertIn(did, ids)

    def test_manueller_upload_ziel_akte(self):
        did = _lege_intake_an("b")
        _lege_zustellung_an(did, "upload", signale={"az": "44/22"},
                            roh_referenz="upload/akte:44/22")
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertIn(did, ids)

    def test_freigegeben_und_verworfen_erscheinen_nicht(self):
        frei = _lege_intake_an("c", queue_status="freigegeben")
        _lege_zustellung_an(frei, "eakte", signale={"az": "44/22"})
        verw = _lege_intake_an("d", verworfen_am="2026-08-01 10:00:00")
        _lege_zustellung_an(verw, "eakte", signale={"az": "44/22"})
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertNotIn(frei, ids)
        self.assertNotIn(verw, ids)

    def test_fremde_akte_erscheint_nicht(self):
        did = _lege_intake_an("e")
        _lege_zustellung_an(did, "eakte", signale={"az": "99/22"})
        r = self.client.get("/akten/44/22/intake-pending", headers=self.headers)
        ids = [e["intake_id"] for e in r.get_json()]
        self.assertNotIn(did, ids)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen (Endpoint fehlt → 404)**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_akten_intake_pending.py -v`
Expected: FAIL — die vier Tests scheitern (Status 404 statt 200 bzw. `r.get_json()` ist kein Array).

- [ ] **Step 3: `import re` ergänzen**

In `backend/routers/akten_routes.py`, die Import-Zeile `import logging` (Z. 19) erweitern:

```python
import logging
import re
```

- [ ] **Step 4: Helfer + Endpoint implementieren (ans Ende von `akten_routes.py` anfügen)**

```python
def _basis_az(az: str) -> str:
    """Streift ein optionales SB-Kuerzel ab ('670/26AS' -> '670/26').

    Gleiche Basis-Logik wie intake_routes._basis_az / akten_matching._az_basis,
    damit der Akte-Vergleich ueber Suffixe/fuehrende Nullen hinweg greift.
    """
    az = (az or "").strip()
    if "/" in az:
        az = re.sub(r"[A-Za-z]{2,3}$", "", az).strip()
    return az


def _abgeleiteter_az(row) -> str | None:
    """Erste nicht-leere AZ-Quelle je Intake-Dokument (Spec Praezedenz):
    1. Signal-AZ (E-Akte + Upload), 2. Upload-Referenz, 3. Matching-Kandidat.
    """
    if row["signal_az"]:
        return row["signal_az"]
    roh = row["roh_referenz"] or ""
    if roh.startswith("upload/akte:"):
        return roh[len("upload/akte:"):]
    return row["kandidat_az"]


@akten_bp.route("/<path:akte_az>/intake-pending", methods=["GET"])
@login_erforderlich
def intake_pending(akte_az: str):
    ziel = _basis_az(akte_az)
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT i.id, i.klasse, i.queue_status, i.erstellt_am, "
            "       i.bezeichnung, "
            "       json_extract(i.parse_json, '$.akten_kandidaten[0].akte_az') "
            "         AS kandidat_az, "
            "       json_extract(z.signale_json, '$.az') AS signal_az, "
            "       json_extract(z.signale_json, '$.dateiname') "
            "         AS signal_dateiname, "
            "       z.roh_referenz AS roh_referenz "
            "FROM intake_dokumente i "
            "LEFT JOIN (SELECT intake_dokument_id, MIN(id) AS min_id "
            "           FROM zustellungen GROUP BY intake_dokument_id) ze "
            "  ON ze.intake_dokument_id = i.id "
            "LEFT JOIN zustellungen z ON z.id = ze.min_id "
            "WHERE i.queue_status != 'freigegeben' "
            "  AND i.verworfen_am IS NULL "
            "ORDER BY i.erstellt_am ASC, i.id ASC"
        ).fetchall()

    eintraege = []
    for r in rows:
        az = _abgeleiteter_az(r)
        if not az or _basis_az(az) != ziel:
            continue
        bez = (r["bezeichnung"] or r["signal_dateiname"]
               or r["klasse"] or "(unbenannt)")
        eintraege.append({
            "intake_id": r["id"],
            "bezeichnung": bez,
            "klasse": r["klasse"],
            "queue_status": r["queue_status"],
            "erstellt_am": r["erstellt_am"],
        })
    return _j(eintraege)
```

- [ ] **Step 5: Test laufen lassen — muss grün sein**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_akten_intake_pending.py -v`
Expected: PASS — alle vier Tests grün.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/akten_routes.py backend/tests/test_akten_intake_pending.py
git commit -m "feat(intake): Endpoint GET /akten/<az>/intake-pending fuer ausstehende Dokumente"
```

---

## Task 2: Frontend-Bereich in der Dokumentenkachel

**Files:**
- Modify: `frontend/src/api.js` (`dokumente`-Objekt, Z. 187-251)
- Create: `frontend/src/sections/IntakePendingListe.jsx`
- Create: `frontend/src/sections/IntakePendingListe.test.jsx`
- Modify: `frontend/src/sections/DokumenteSection.jsx` (Signatur Z. 18; Render-Anfang Z. 727)

**Interfaces:**
- Consumes: `GET /akten/<az>/intake-pending` (Task 1) via neue API-Methode.
- Produces: `dokumente.intakePending(az): Promise<Array<{intake_id,bezeichnung,klasse,queue_status,erstellt_am}>>`; Komponente `<IntakePendingListe eintraege onOpenReview />`; exportierte Pure-Funktion `intakeBadge(status): {text, color, bg}`.
- DokumenteSection nimmt neue Prop `onOpenReview: (intakeId:number) => void` (wird in Task 3 verdrahtet).

- [ ] **Step 1: API-Methode ergänzen**

In `frontend/src/api.js`, im `dokumente`-Objekt (nach `liste`, Z. ~188) eine Zeile ergänzen:

```javascript
export const dokumente = {
  liste:    (aId)        => request(`/akten/${aId}/dokumente`),
  intakePending: (aId)   => request(`/akten/${encodeURIComponent(aId)}/intake-pending`),
```

- [ ] **Step 2: Komponententest schreiben (definiert Verhalten)**

Create `frontend/src/sections/IntakePendingListe.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import IntakePendingListe, { intakeBadge } from "./IntakePendingListe.jsx";

describe("intakeBadge", () => {
  it("mappt queue_status auf Badge-Texte", () => {
    expect(intakeBadge("neu").text).toBe("Wird verarbeitet");
    expect(intakeBadge("laeuft").text).toBe("Wird verarbeitet");
    expect(intakeBadge("bereit_zur_review").text).toBe("Review ausstehend");
    expect(intakeBadge("pipeline_fehler").text).toBe("Fehler – prüfen");
  });
});

describe("IntakePendingListe", () => {
  const EINTRAEGE = [
    { intake_id: 1, bezeichnung: "Abrechnung", klasse: "abrechnungsschreiben",
      queue_status: "bereit_zur_review", erstellt_am: "2026-08-04 06:19:47" },
    { intake_id: 2, bezeichnung: "Foto", klasse: "sonstiges",
      queue_status: "pipeline_fehler", erstellt_am: "2026-08-04 07:00:00" },
  ];

  it("rendert die drei Badge-Texte je Status", () => {
    render(<IntakePendingListe eintraege={EINTRAEGE} onOpenReview={() => {}} />);
    expect(screen.getByText("Review ausstehend")).toBeInTheDocument();
    expect(screen.getByText("Fehler – prüfen")).toBeInTheDocument();
  });

  it("löst onOpenReview mit der intake_id aus", () => {
    const onOpen = vi.fn();
    render(<IntakePendingListe eintraege={EINTRAEGE} onOpenReview={onOpen} />);
    fireEvent.click(screen.getAllByText("Zur Review →")[0]);
    expect(onOpen).toHaveBeenCalledWith(1);
  });

  it("rendert nichts bei leerer Liste", () => {
    const { container } = render(
      <IntakePendingListe eintraege={[]} onOpenReview={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 3: Test laufen lassen — muss fehlschlagen (Komponente fehlt)**

Run: `cd frontend && npx vitest run src/sections/IntakePendingListe.test.jsx`
Expected: FAIL — Import von `./IntakePendingListe.jsx` schlägt fehl (Datei existiert nicht).

- [ ] **Step 4: Komponente implementieren**

Create `frontend/src/sections/IntakePendingListe.jsx`:

```jsx
import React from "react";
import T from "../config/theme.js";
import { Card, CardHead } from "../components/common.jsx";

export function intakeBadge(status) {
  switch (status) {
    case "bereit_zur_review":
      return { text: "Review ausstehend", color: T.amberText, bg: T.amberBg };
    case "pipeline_fehler":
      return { text: "Fehler – prüfen", color: T.redText, bg: T.redBg };
    default:
      return { text: "Wird verarbeitet", color: T.textMuted, bg: T.surface };
  }
}

function fmtDatum(iso) {
  if (!iso) return "";
  try {
    const dt = new Date(String(iso).replace(" ", "T"));
    if (isNaN(dt.getTime())) return "";
    return dt.toLocaleString("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return "";
  }
}

export default function IntakePendingListe({ eintraege = [], onOpenReview }) {
  if (!eintraege.length) return null;
  return (
    <Card>
      <CardHead title={`In Verarbeitung (${eintraege.length})`} />
      {eintraege.map((e, i) => {
        const b = intakeBadge(e.queue_status);
        return (
          <div key={e.intake_id}
            style={{ display: "flex", alignItems: "center", gap: 13,
              padding: "11px 1.4rem",
              borderBottom: i < eintraege.length - 1
                ? `1px solid ${T.borderSoft}` : "none" }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontFamily: T.fontBody, fontSize: "0.975rem",
                fontWeight: 600, color: T.text, overflow: "hidden",
                textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {e.bezeichnung}
              </div>
              <div style={{ fontFamily: T.fontBody, fontSize: "0.815rem",
                color: T.textFaint, marginTop: 3 }}>
                {e.klasse || "—"} · {fmtDatum(e.erstellt_am)}
              </div>
            </div>
            <span style={{ background: b.bg, color: b.color,
              borderRadius: 10, padding: "2px 8px", fontSize: "0.825rem",
              fontWeight: 600, flexShrink: 0 }}>
              {b.text}
            </span>
            <button
              onClick={() => onOpenReview?.(e.intake_id)}
              style={{ background: "none", border: "none", color: T.accent,
                cursor: "pointer", fontFamily: T.fontBody,
                fontSize: "0.875rem", fontWeight: 600, flexShrink: 0 }}>
              Zur Review →
            </button>
          </div>
        );
      })}
    </Card>
  );
}
```

- [ ] **Step 5: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/sections/IntakePendingListe.test.jsx`
Expected: PASS — alle Tests grün.

- [ ] **Step 6: `DokumenteSection` einbinden — Signatur + Import + State + Laden + Render**

In `frontend/src/sections/DokumenteSection.jsx`:

(a) Import ergänzen (nach Z. 7, `import DokumentAktionsmenue …`):

```jsx
import IntakePendingListe from "./IntakePendingListe.jsx";
```

(b) Signatur (Z. 18) um `onOpenReview` erweitern:

```jsx
function DokumenteSection({ dokumente, dispatch, akteId, akte, belegeKandidaten = [], schaden = {}, vorsteuer = false, onOpenReview }) {
```

(c) State-Deklaration (bei den übrigen `useState`, z.B. nach Z. 31):

```jsx
  const [intakePending, setIntakePending] = useState([]);
```

(d) Laden beim Öffnen der Akte — neuen `useEffect` neben den bestehenden akteId-Effekten (z.B. nach dem Block Z. 225-228) einfügen:

```jsx
  useEffect(() => {
    if (!akteId) return;
    apiDokumente.intakePending(akteId)
      .then(res => setIntakePending(Array.isArray(res) ? res : []))
      .catch(() => setIntakePending([]));
  }, [akteId]);
```

(e) Rendern — als erstes Kind des äußeren Flex-Containers (direkt nach `<div style={{ display:"flex", flexDirection:"column", gap:"1.25rem" }}>`, Z. 727):

```jsx
        <IntakePendingListe eintraege={intakePending} onOpenReview={onOpenReview} />

```

- [ ] **Step 7: Frontend-Build prüfen (kein Kompilierfehler)**

Run: `cd frontend && npm run build`
Expected: Build läuft ohne Fehler durch.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api.js frontend/src/sections/IntakePendingListe.jsx frontend/src/sections/IntakePendingListe.test.jsx frontend/src/sections/DokumenteSection.jsx
git commit -m "feat(intake): Ausstehende Intake-Dokumente in der Dokumentenkachel anzeigen"
```

---

## Task 3: Navigation zur ReviewQueue auf das Dokument

**Files:**
- Modify: `frontend/src/views/ReviewQueueView.jsx` (Signatur Z. 1424; State `aktivId` Z. 1426)
- Modify: `frontend/src/components/AkteDetailView.jsx` (Signatur Z. 34; Render `DokumenteSection` Z. 414)
- Modify: `frontend/src/App.jsx` (State Z. 95-104; Render-Switch Z. 288-303)
- Test: `frontend/src/views/ReviewQueueView.initial.test.jsx` (neu)

**Interfaces:**
- Consumes: `onOpenReview(intakeId)` aus Task 2 (Prop von `DokumenteSection`).
- Produces: `ReviewQueueView`-Prop `initialIntakeId: number|null` + `onDokumentGeoffnet: () => void`; `AkteDetailView`-Prop `onOpenReview`; `App`-State `pendingReviewIntakeId`.

**Kontext (verbatim):**
- App-Muster für `pendingEinstellungenTab` (Z. 199-200): `onClick={() => { setActive("einstellungen"); setPendingEinstellungenTab("system_status"); }}`.
- `EinstellungenView`-Render (Z. 295): `initialTab={pendingEinstellungenTab} onTabMounted={() => setPendingEinstellungenTab(null)}`.
- `ReviewQueueView`-Render (Z. 293): `active==="review-queue" ? <ReviewQueueView onOpenAkte={openAkte} />`.
- `AkteDetailView`-Render (Z. 296-302): bekommt `akte, st, dispatch, initialTab, onTabMounted`.
- In `ReviewQueueView`: `setAktivId(id)` ist der einzige nötige Hebel; der programmatische Sprung existiert schon (`onSpringe={id => setAktivId(id)}`, Z. 1591). `DetailPanel` (Z. 1676) lädt sein Detail selbst per `id`, unabhängig vom Queue-Fetch.

- [ ] **Step 1: Test für ReviewQueue-Initialöffnung schreiben**

Create `frontend/src/views/ReviewQueueView.initial.test.jsx`:

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const api = vi.hoisted(() => ({
  apiIntake: {
    queue: vi.fn(() => Promise.resolve({ eintraege: [
      { id: 461, klasse: "abrechnungsschreiben",
        queue_status: "bereit_zur_review", konfidenz: 0.9, erstellt_am: "2026-08-04 06:19:47" },
    ] })),
    detail: vi.fn(() => Promise.resolve({ id: 461, klasse: "abrechnungsschreiben",
      queue_status: "bereit_zur_review", felder: {}, parse: {},
      akten_kandidaten: [], zustellungen: [] })),
    ereignistypen: vi.fn(() => Promise.resolve({ typen: [] })),
    klassen: vi.fn(() => Promise.resolve({ klassen: [] })),
  },
  apiAktenanlage: { offen: vi.fn(() => Promise.resolve({ vorgaenge: [], ramicro_verfuegbar: true })) },
}));
vi.mock("../api", () => api);

import ReviewQueueView from "./ReviewQueueView.jsx";

describe("ReviewQueueView initialIntakeId", () => {
  it("öffnet das Detail des per initialIntakeId übergebenen Dokuments", async () => {
    const onGeoffnet = vi.fn();
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={461}
             onDokumentGeoffnet={onGeoffnet} />);
    await waitFor(() => expect(api.apiIntake.detail).toHaveBeenCalledWith(461));
    expect(onGeoffnet).toHaveBeenCalled();
  });
});
```

Hinweis für die Umsetzung: Die im Mock unter `apiIntake`/`apiAktenanlage` gelisteten Methoden müssen die real von `ReviewQueueView` aufgerufenen sein. Falls beim Testlauf eine weitere Methode fehlt (Fehler „is not a function"), diese Methode dem `vi.hoisted`-Mock als weiteres `vi.fn()` ergänzen — kein Produktionscode-Änderungsgrund.

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.initial.test.jsx`
Expected: FAIL — `apiIntake.detail` wird nicht mit `461` aufgerufen (Prop noch nicht ausgewertet).

- [ ] **Step 3: `ReviewQueueView` — Prop `initialIntakeId` auswerten**

In `frontend/src/views/ReviewQueueView.jsx` die Signatur (Z. 1424) ändern:

```jsx
export default function ReviewQueueView({ onOpenAkte, initialIntakeId = null, onDokumentGeoffnet }) {
```

Direkt nach dem bestehenden `useEffect(() => { laden(); }, [laden]);` (Z. ~1471) ergänzen:

```jsx
  useEffect(() => {
    if (initialIntakeId != null) {
      setAktivId(initialIntakeId);
      onDokumentGeoffnet?.();
    }
  }, [initialIntakeId]); // eslint-disable-line react-hooks/exhaustive-deps
```

- [ ] **Step 4: Test laufen lassen — muss grün sein**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.initial.test.jsx`
Expected: PASS.

- [ ] **Step 5: `AkteDetailView` — Prop `onOpenReview` durchreichen**

In `frontend/src/components/AkteDetailView.jsx` die Signatur (Z. 34) ändern:

```jsx
function AkteDetailView({ akte, st, dispatch, initialTab, onTabMounted, onOpenReview }) {
```

Und den `DokumenteSection`-Render (Z. 414) um die Prop erweitern:

```jsx
            {sec==="dokumente"     && <DokumenteSection dokumente={st.dokumente||[]} dispatch={dispatch} akteId={akte.id} akte={akte} belegeKandidaten={st.belegeKandidaten||[]} schaden={st.schaden||{}} vorsteuer={(st.beteiligte||[]).find(b=>b.rolle==="mandant")?.vorsteuer==="Y"} onOpenReview={onOpenReview} />}
```

- [ ] **Step 6: `App.jsx` — State, Callback und Props verdrahten**

(a) State-Deklaration bei den übrigen `pending…`-States (nach Z. 99, `pendingEmailId`):

```jsx
  const [pendingReviewIntakeId, setPendingReviewIntakeId] = useState(null);
```

(b) `ReviewQueueView`-Render (Z. 293) erweitern:

```jsx
: active==="review-queue"    ? <ReviewQueueView onOpenAkte={openAkte} initialIntakeId={pendingReviewIntakeId} onDokumentGeoffnet={() => setPendingReviewIntakeId(null)} />
```

(c) `AkteDetailView`-Render (Z. 296-302) um den Callback erweitern:

```jsx
: activeTab?.akte ? <AkteDetailView
    akte={activeTab.akte}
    st={aktenState[activeTab.akte.id]||{}}
    dispatch={dispatch}
    initialTab={pendingAkteTab?.tabId === active ? pendingAkteTab : null}
    onTabMounted={() => setPendingAkteTab(null)}
    onOpenReview={(intakeId) => { setActive("review-queue"); setPendingReviewIntakeId(intakeId); }}
  />
```

- [ ] **Step 7: Build + gezielte Tests grün**

Run: `cd frontend && npm run build && npx vitest run src/views/ReviewQueueView.initial.test.jsx src/sections/IntakePendingListe.test.jsx`
Expected: Build ok; beide Testdateien grün.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.initial.test.jsx frontend/src/components/AkteDetailView.jsx frontend/src/App.jsx
git commit -m "feat(intake): Navigation aus der Akte zur ReviewQueue auf das Dokument"
```

---

## Abschluss-Gate (nach allen Tasks)

Nicht Teil eines Task-Commits — manueller Browser-Nachtest durch RA Schatz (Spec §8, Handover Gate 1):

1. Dokument in eine Testakte importieren → Zeile mit Badge „Review ausstehend" erscheint oben in der Dokumentenkachel.
2. Klick auf „Zur Review →" → ReviewQueue öffnet sich und zeigt das Detail genau dieses Dokuments.
3. Nach Freigabe und erneutem Öffnen der Akte verschwindet die Zeile aus der Kachel (erscheint dann unter den freigegebenen Dokumenten).

Danach: Whole-Branch-Review (subagent-driven-development), dann Merge-Strategie mit dem Nutzer klären (SSOT + Scheduler-Fix + dieses Feature liegen zusammen auf dem Branch — Handover Gate 3).
