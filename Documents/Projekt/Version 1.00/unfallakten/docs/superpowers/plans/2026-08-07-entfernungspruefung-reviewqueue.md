# Entfernungsprüfung in der ReviewQueue (Paket 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Im Review-Detail der Intake-Queue gibt es für Dokumente der Klasse `pruefbericht` einen manuellen Button „Entfernung prüfen", der die echte Fahrstrecke Mandant → Referenzwerkstatt via OpenRouteService prüft, das Ergebnis als Popup zeigt UND in `felder.referenzwerkstatt` speichert.

**Architecture:** Neuer schlanker Endpoint `POST /intake/dokument/<id>/entfernung` in `backend/routers/intake_routes.py` (der Alt-Endpoint `/distanz/prüfen-aus-dokument` arbeitet mit Alt-Tabellen und bleibt unangetastet). Er liest die Werkstatt aus `parse_json.felder.referenzwerkstatt` (Paket 1), die Mandanten-Adresse via vorhandenem `_mandant_adresse(akte_az)` aus `distanz_routes.py`, ruft `pruefe_entfernung` aus `werkstatt_service.py` und persistiert das Ergebnis nach dem Muster von `patch_felder`. Frontend: Button + Modal-Dialog in `ReviewQueueView.jsx` nach den dortigen Bestandsmustern (`erneutParsen`-Button, `VerwerfenDialog`-Modal). ENTSCHIEDEN (RA Schatz 2026-08-07): KEINE Auto-Prüfung — Mandanten-Adresse geht nur auf Klick an den externen Dienst; Mandanten-Adresse kommt aus dem im Review AUSGEWÄHLTEN Akten-Kandidaten (`gewaehlteAkte`), ohne Auswahl ist der Button deaktiviert mit Hinweis.

**Tech Stack:** Python 3/Flask (Docker-Container `unfallakten-backend-dev`), React/Vite + Vitest (Host), OpenRouteService (`ORS_APIKEY` im Dev-Container gesetzt, geprüft).

## Global Constraints

- Backend-Tests IM CONTAINER: `docker exec unfallakten-backend-dev python -m pytest backend/tests/<datei> -q`. Frontend-Tests/Build auf dem HOST: `cd frontend` + `npx vitest run <datei>` bzw. `npm test` / `npm run build`.
- In Unit-Tests NIE echte ORS-Aufrufe: `pruefe_entfernung` und `_mandant_adresse` werden gemockt.
- Git-Wurzel ist das Home-Verzeichnis `C:\Users\HAL9000` — NIE `git add -A`, immer Dateien einzeln stagen; git-Befehle aus dem Projektordner `C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten`.
- Branch: `abschlussbericht` (dort weiterarbeiten, NICHT mergen).
- Vorbestehende Failures NICHT fixen: 2× `test_intake_routes` (Label „Rechnung (Auffang)"), `test_modul7`.
- Keine Code-Kommentare außer bei nicht-offensichtlichem Verhalten.
- Commit-Messages enden mit `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Interface-Kontrakt aus Paket 1 (bindend): `felder.referenzwerkstatt` hat garantiert die Keys `{name, adresse, plz_ort, telefon, km_genannt, quelle}`; `km_genannt` kann `None` sein („keine Angabe") oder — vom LLM — auch als String kommen. Dieses Paket ERGÄNZT die Keys `{km_echt, minuten, abweichung_km, bewertung, textbaustein, geprueft_am, geprueft_gegen_akte}`.
- Der gespeicherte `textbaustein` wird nur bei `unzumutbar` gefüllt (der Service generiert ihn immer, aber er behauptet „> 15 km nicht zumutbar" — bei zumutbarer Entfernung wäre das inhaltlich falsch und dürfte nicht in den späteren Stellungnahme-Workflow wandern).

---

### Task 1: Backend-Endpoint `POST /intake/dokument/<id>/entfernung`

**Files:**
- Modify: `backend/routers/intake_routes.py` (Modul-Docstring-Endpunktliste Zeile 9–17 ergänzen; neuer Endpoint + Helfer nach `patch_felder`, d. h. nach Zeile 630)
- Test: `backend/tests/test_intake_entfernung.py` (neu)

**Interfaces:**
- Consumes: `_lade_intake`, `_parse`, `_basis_az`, `_j`, `_err`, `get_connection` (alle bereits in `intake_routes.py`); `_mandant_adresse(akte_az)` aus `backend/routers/distanz_routes.py:356` (liest Mandant aus `beteiligte`, `akte_id` = az-String); `pruefe_entfernung(mandant_adresse, werkstatt_adresse, werkstatt_name, km_genannt)` aus `backend/services/werkstatt_service.py:278` (Rückgabe-Keys: `ok, mandant_adresse, werkstatt_adresse, werkstatt_name, km_genannt, km_echt, minuten, abweichung_km, unzumutbar, textbaustein, fehler`).
- Produces: `POST /intake/dokument/<int:intake_id>/entfernung`, Body `{"akte_az": str}`. Antwort 200 = das `pruefe_entfernung`-Result plus Key `referenzwerkstatt` (der ggf. aktualisierte Feld-Stand). Fehler: 400 (akte_az fehlt), 404 (Dokument bzw. Mandanten-Adresse), 422 (keine/unvollständige Referenzwerkstatt). Bei `ok: false` (ORS-/Geocoding-Fehler) wird NICHT persistiert. Task 2 ruft diesen Endpoint via `apiIntake.entfernungPruefen(id, akteAz)`.

- [ ] **Step 1: Write the failing tests**

Neue Datei `backend/tests/test_intake_entfernung.py`:

```python
"""
Tests fuer POST /intake/dokument/<id>/entfernung (Paket 2, Befund 1280/25).

Entfernungspruefung Referenzwerkstatt aus der ReviewQueue: Werkstatt aus
parse_json.felder.referenzwerkstatt, Mandanten-Adresse aus dem uebergebenen
Akten-Kandidaten (akte_az), pruefe_entfernung ist gemockt (kein echter
ORS-Call). Setup-Muster wie test_intake_routes.py (bewusst dupliziert).
"""
import importlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

_tmp_dir = tempfile.mkdtemp(prefix="intake_entfernung_")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _setup(test_id: str):
    db_path = os.path.join(_tmp_dir, f"ie_{test_id}.db")
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


REFERENZWERKSTATT = {
    "name": "Möser Arno - Karosseriefachbetrieb",
    "adresse": "Philipp-Reis-Straße 9",
    "plz_ort": "63128 Dietzenbach",
    "telefon": "06074-25936",
    "km_genannt": 16.0,
    "quelle": "vhv_block",
}


def _lege_pruefbericht_an(referenzwerkstatt=REFERENZWERKSTATT):
    from backend.db.database import get_connection
    felder = {"vorgangsnummer": "SD1"}
    if referenzwerkstatt is not None:
        felder["referenzwerkstatt"] = dict(referenzwerkstatt)
    parse_json = json.dumps({"text_gesamt": "Prüfbericht ...",
                             "felder": felder,
                             "akten_kandidaten": []}, ensure_ascii=False)
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO intake_dokumente "
            "(sha256, klasse, klasse_quelle, konfidenz, queue_status, "
            " parse_json, registry_version) "
            "VALUES (?, 'pruefbericht', 'auto', 0.9, 'bereit_zur_review', ?, 'v1')",
            (("e" * 64), parse_json),
        )
        return cur.lastrowid


def _seed_akte_mit_mandant(az="1280/25"):
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO unfallakte (az, unfalldatum, status) "
            "VALUES (?, '2025-11-01', 'offen')", (az,))
        conn.execute(
            "INSERT INTO beteiligte (akte_id, rolle, name, anschrift, plz, ort) "
            "VALUES (?, 'mandant', 'Mustermann', 'Andréstr. 10', '63067', 'Offenbach')",
            (az,))


ORS_OK = {
    "ok": True,
    "mandant_adresse": "Andréstr. 10, 63067 Offenbach",
    "werkstatt_adresse": "Philipp-Reis-Straße 9, 63128 Dietzenbach",
    "werkstatt_name": "Möser Arno - Karosseriefachbetrieb",
    "km_genannt": 16.0,
    "km_echt": 24.3,
    "minuten": 31,
    "abweichung_km": 8.3,
    "unzumutbar": True,
    "textbaustein": "Den dortigen Verweis ...",
    "fehler": None,
}


class TestEntfernung(unittest.TestCase):
    def setUp(self):
        self.client = _setup(self._testMethodName)
        self.h = _auth_header(self.client)

    def _post(self, intake_id, body):
        return self.client.post(
            f"/intake/dokument/{intake_id}/entfernung",
            json=body, headers=self.h)

    def _felder_aus_db(self, intake_id):
        from backend.db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json FROM intake_dokumente WHERE id=?",
                (intake_id,)).fetchone()
        return json.loads(row["parse_json"])["felder"]

    def test_ohne_akte_az_400(self):
        dok_id = _lege_pruefbericht_an()
        r = self._post(dok_id, {})
        self.assertEqual(r.status_code, 400)

    def test_unbekanntes_dokument_404(self):
        r = self._post(99999, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 404)

    def test_ohne_referenzwerkstatt_422(self):
        dok_id = _lege_pruefbericht_an(referenzwerkstatt=None)
        _seed_akte_mit_mandant()
        r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 422)

    def test_werkstatt_adresse_unvollstaendig_422(self):
        dok_id = _lege_pruefbericht_an(
            referenzwerkstatt={"name": "Nur Name", "adresse": "",
                               "plz_ort": "", "telefon": "",
                               "km_genannt": None, "quelle": "triggerkontext"})
        _seed_akte_mit_mandant()
        r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 422)

    def test_mandant_nicht_gefunden_404(self):
        dok_id = _lege_pruefbericht_an()
        with mock.patch(
            "backend.routers.distanz_routes._mandant_adresse",
            return_value=None,
        ):
            r = self._post(dok_id, {"akte_az": "777/77"})
        self.assertEqual(r.status_code, 404)

    def test_erfolg_persistiert_ergebnis(self):
        dok_id = _lege_pruefbericht_an()
        _seed_akte_mit_mandant()
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=dict(ORS_OK),
        ) as m:
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        daten = r.get_json()
        self.assertTrue(daten["ok"])
        self.assertEqual(daten["km_echt"], 24.3)
        self.assertEqual(daten["referenzwerkstatt"]["bewertung"], "unzumutbar")
        kwargs = m.call_args.kwargs
        self.assertEqual(kwargs["mandant_adresse"],
                         "Andréstr. 10, 63067 Offenbach")
        self.assertEqual(kwargs["werkstatt_adresse"],
                         "Philipp-Reis-Straße 9, 63128 Dietzenbach")
        self.assertEqual(kwargs["km_genannt"], 16.0)
        ws = self._felder_aus_db(dok_id)["referenzwerkstatt"]
        self.assertEqual(ws["km_echt"], 24.3)
        self.assertEqual(ws["minuten"], 31)
        self.assertEqual(ws["abweichung_km"], 8.3)
        self.assertEqual(ws["bewertung"], "unzumutbar")
        self.assertEqual(ws["textbaustein"], "Den dortigen Verweis ...")
        self.assertEqual(ws["geprueft_gegen_akte"], "1280/25")
        self.assertTrue(ws.get("geprueft_am"))
        self.assertEqual(ws["name"], REFERENZWERKSTATT["name"])
        self.assertEqual(ws["quelle"], "vhv_block")

    def test_zumutbar_speichert_keinen_textbaustein(self):
        dok_id = _lege_pruefbericht_an()
        _seed_akte_mit_mandant()
        zumutbar = dict(ORS_OK, km_echt=9.8, unzumutbar=False,
                        abweichung_km=-6.2)
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=zumutbar,
        ):
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        ws = self._felder_aus_db(dok_id)["referenzwerkstatt"]
        self.assertEqual(ws["bewertung"], "zumutbar")
        self.assertEqual(ws["textbaustein"], "")

    def test_ors_fehler_persistiert_nicht(self):
        dok_id = _lege_pruefbericht_an()
        _seed_akte_mit_mandant()
        fehl = dict(ORS_OK, ok=False, km_echt=None,
                    fehler="Werkstatt-Adresse konnte nicht geocodiert werden")
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=fehl,
        ):
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["ok"])
        ws = self._felder_aus_db(dok_id)["referenzwerkstatt"]
        self.assertNotIn("km_echt", ws)
        self.assertNotIn("bewertung", ws)

    def test_km_genannt_als_string_wird_konvertiert(self):
        dok_id = _lege_pruefbericht_an(
            referenzwerkstatt=dict(REFERENZWERKSTATT, km_genannt="16,00 km"))
        _seed_akte_mit_mandant()
        with mock.patch(
            "backend.services.werkstatt_service.pruefe_entfernung",
            return_value=dict(ORS_OK),
        ) as m:
            r = self._post(dok_id, {"akte_az": "1280/25"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(m.call_args.kwargs["km_genannt"], 16.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_entfernung.py -q`
Expected: alle Tests FAIL mit 404 (Route existiert nicht — Flask liefert für unbekannte Pfade 404, daher schlagen auch die Status-Assertions auf 400/422/200 fehl; `test_unbekanntes_dokument_404` kann als False-Positive grün sein, das ist ok solange die übrigen rot sind).

- [ ] **Step 3: Implement**

In `backend/routers/intake_routes.py`:

(a) Modul-Docstring-Endpunktliste (nach Zeile 16 `POST /intake/dokument/<id>/verwerfen …`) ergänzen um:

```
  POST  /intake/dokument/<id>/entfernung    Entfernungspruefung Referenzwerkstatt
```

(b) Nach `patch_felder` (nach Zeile 630, vor dem Abschnitt `PATCH /intake/dokument/<id>/bezeichnung`) einfügen:

```python
# ─── POST /intake/dokument/<id>/entfernung ────────────────────────────────────

def _km_zahl(wert):
    """'16,00 km' / '16.0' / 16 -> float; None wenn nicht parsbar."""
    if wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(wert))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


@intake_bp.route("/dokument/<int:intake_id>/entfernung", methods=["POST"])
@login_erforderlich
def post_entfernung(intake_id: int):
    """Entfernungspruefung Referenzwerkstatt (Befund 1280/25, Paket 2).

    Body: {"akte_az": str}. Nur manuell ausgeloest -- die Mandanten-Adresse
    geht an den externen Dienst OpenRouteService (Entscheidung RA Schatz
    2026-08-07). Das Ergebnis wird in parse_json.felder.referenzwerkstatt
    ergaenzt, damit es bei der Freigabe dauerhaft in die Akte wandert.
    Kein korrektur_log-Eintrag: keine manuelle Feldkorrektur, sondern
    System-Anreicherung.
    """
    payload = request.get_json(silent=True) or {}
    akte_az = _basis_az(payload.get("akte_az") or "")
    if not akte_az:
        return _err("akte_az erforderlich", 400)

    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    parse = _parse(dok.get("parse_json"))
    ws = (parse.get("felder") or {}).get("referenzwerkstatt")
    if not isinstance(ws, dict):
        return _err("Keine Referenzwerkstatt im Dokument extrahiert", 422)

    werkstatt_adresse = ", ".join(
        t for t in (ws.get("adresse") or "", ws.get("plz_ort") or "") if t)
    if not werkstatt_adresse:
        return _err("Werkstatt-Adresse unvollständig – Entfernung manuell prüfen", 422)

    from .distanz_routes import _mandant_adresse
    mandant_adresse = _mandant_adresse(akte_az)
    if not mandant_adresse:
        return _err(f"Mandanten-Adresse für Akte {akte_az} nicht gefunden", 404)

    from ..services.werkstatt_service import pruefe_entfernung
    result = pruefe_entfernung(
        mandant_adresse=mandant_adresse,
        werkstatt_adresse=werkstatt_adresse,
        werkstatt_name=ws.get("name") or "",
        km_genannt=_km_zahl(ws.get("km_genannt")),
    )

    if result.get("ok"):
        # Textbaustein nur bei unzumutbar speichern -- er formuliert die
        # ">15 km"-Ruege und waere bei zumutbarer Entfernung inhaltlich falsch
        ws.update({
            "km_echt":             result.get("km_echt"),
            "minuten":             result.get("minuten"),
            "abweichung_km":       result.get("abweichung_km"),
            "bewertung":           "unzumutbar" if result.get("unzumutbar") else "zumutbar",
            "textbaustein":        (result.get("textbaustein") or "")
                                   if result.get("unzumutbar") else "",
            "geprueft_am":         datetime.now().strftime("%Y-%m-%d"),
            "geprueft_gegen_akte": akte_az,
        })
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET parse_json=? WHERE id=?",
                (json.dumps(parse, ensure_ascii=False), intake_id),
            )

    result["referenzwerkstatt"] = ws
    return _j(result)
```

Hinweis: `re`, `datetime`, `json`, `get_connection` sind in `intake_routes.py` bereits importiert (Zeilen 31–42) — keine neuen Top-Level-Imports nötig. Die Funktions-Imports (`_mandant_adresse`, `pruefe_entfernung`) bleiben bewusst lokal (Muster der Datei, und testbar via `mock.patch` am Quellmodul).

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_entfernung.py -q`
Expected: 9 passed.

- [ ] **Step 5: Regression der Nachbar-Suiten**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_intake_routes.py -q`
Expected: nur die 2 vorbestehenden Failures (Label „Rechnung (Auffang)"), keine neuen.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_intake_entfernung.py
git commit -m "feat(intake): Endpoint Entfernungspruefung Referenzwerkstatt (Befund 1280/25)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Frontend — Button „Entfernung prüfen" + Ergebnis-Popup

**Files:**
- Modify: `frontend/src/api.js` (neuer Helper in `apiIntake`, Objekt bei Zeile 1104–1137)
- Modify: `frontend/src/views/ReviewQueueView.jsx` (neue Komponente `EntfernungDialog` nach `VerwerfenDialog` Zeile 477; State + Handler + Button + Dialog-Render im `DetailPanel`)
- Test: `frontend/src/views/ReviewQueueView.entfernung.test.jsx` (neu)

**Interfaces:**
- Consumes: `POST /intake/dokument/<id>/entfernung` aus Task 1 (Antwort: `pruefe_entfernung`-Result + `referenzwerkstatt`); Bestands-State im `DetailPanel`: `gewaehlteAkte` (az-String, Zeile 867), `aktion`, `pollAktiv`, `laden({skipFormReset:true})`, Theme-Objekt `T`.
- Produces: `apiIntake.entfernungPruefen(id, akteAz)`; Button nur bei `detail.klasse === "pruefbericht"`, deaktiviert ohne `gewaehlteAkte`; Modal `EntfernungDialog`.

- [ ] **Step 1: Write the failing tests**

Neue Datei `frontend/src/views/ReviewQueueView.entfernung.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";

const api = vi.hoisted(() => ({
  apiIntake: {
    queue: vi.fn(() => Promise.resolve({ eintraege: [
      { id: 516, klasse: "pruefbericht", queue_status: "bereit_zur_review",
        konfidenz: 0.9, erstellt_am: "2026-08-07 09:00:00" },
    ] })),
    detail: vi.fn(),
    entfernungPruefen: vi.fn(() => Promise.resolve({
      ok: true,
      werkstatt_name: "Möser Arno - Karosseriefachbetrieb",
      werkstatt_adresse: "Philipp-Reis-Straße 9, 63128 Dietzenbach",
      km_genannt: 16.0, km_echt: 24.3, minuten: 31, abweichung_km: 8.3,
      unzumutbar: true, textbaustein: "Den dortigen Verweis ...",
      referenzwerkstatt: {},
    })),
    ereignistypen: vi.fn(() => Promise.resolve({ typen: [] })),
    klassen: vi.fn(() => Promise.resolve({ klassen: [] })),
  },
  apiAktenanlage: { offen: vi.fn(() => Promise.resolve({ vorgaenge: [], ramicro_verfuegbar: true })) },
  tokenStore: { getAccess: vi.fn(() => "test-token") },
  API_BASE: "http://localhost:5000",
}));
vi.mock("../api", () => api);

import ReviewQueueView from "./ReviewQueueView.jsx";

const PRUEF_DETAIL = {
  id: 516, klasse: "pruefbericht", queue_status: "bereit_zur_review",
  payload_typ: "pdf",
  parse: {
    felder: { referenzwerkstatt: {
      name: "Möser Arno - Karosseriefachbetrieb",
      adresse: "Philipp-Reis-Straße 9", plz_ort: "63128 Dietzenbach",
      telefon: "", km_genannt: 16.0, quelle: "vhv_block",
    } },
    akten_kandidaten: [{ akte_az: "1280/25", score: 1.0, quelle: "az_exakt" }],
  },
  zustellungen: [],
};

function setDetail(fixture) {
  api.apiIntake.detail.mockImplementation(() => Promise.resolve(fixture));
}

beforeEach(() => {
  api.apiIntake.detail.mockReset();
  api.apiIntake.entfernungPruefen.mockClear();
  setDetail(PRUEF_DETAIL);
});

describe("ReviewQueueView Entfernungsprüfung", () => {
  it("prüft die Entfernung und zeigt das Ergebnis-Popup", async () => {
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={516} />);
    const btn = await screen.findByRole("button", { name: /Entfernung prüfen/ });
    await waitFor(() => expect(btn.disabled).toBe(false));
    fireEvent.click(btn);
    await waitFor(() => expect(api.apiIntake.entfernungPruefen)
      .toHaveBeenCalledWith(516, "1280/25"));
    await screen.findByText(/Entfernungsprüfung Referenzwerkstatt/);
    expect(screen.getByText(/24,3 km/)).toBeTruthy();
    expect(screen.getByText(/Nicht zumutbar/)).toBeTruthy();
  });

  it("zeigt den Button nur bei Klasse pruefbericht", async () => {
    setDetail({ ...PRUEF_DETAIL, id: 517, klasse: "abrechnungsschreiben" });
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={517} />);
    await waitFor(() => expect(api.apiIntake.detail).toHaveBeenCalled());
    await screen.findByText(/Extrahierte Felder/);
    expect(screen.queryByRole("button", { name: /Entfernung prüfen/ })).toBeNull();
  });

  it("deaktiviert den Button ohne gewählte Akte und zeigt einen Hinweis", async () => {
    setDetail({ ...PRUEF_DETAIL, id: 518,
      parse: { ...PRUEF_DETAIL.parse, akten_kandidaten: [] } });
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={518} />);
    const btn = await screen.findByRole("button", { name: /Entfernung prüfen/ });
    expect(btn.disabled).toBe(true);
    expect(screen.getByText(/Erst Akte auswählen/)).toBeTruthy();
  });

  it("zeigt den Fehler im Popup, wenn der Endpoint einen Fehler liefert", async () => {
    api.apiIntake.entfernungPruefen.mockRejectedValueOnce(
      new Error("Mandanten-Adresse für Akte 1280/25 nicht gefunden"));
    render(<ReviewQueueView onOpenAkte={() => {}} initialIntakeId={516} />);
    const btn = await screen.findByRole("button", { name: /Entfernung prüfen/ });
    await waitFor(() => expect(btn.disabled).toBe(false));
    fireEvent.click(btn);
    await screen.findByText(/Mandanten-Adresse für Akte 1280\/25 nicht gefunden/);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend; npx vitest run src/views/ReviewQueueView.entfernung.test.jsx`
Expected: 4 failed (Button existiert nicht → `findByRole` Timeout bzw. `queryByRole`-Test kann als False-Positive grün sein; mindestens Tests 1, 3, 4 MÜSSEN rot sein).

- [ ] **Step 3: Implement**

(a) `frontend/src/api.js` — im `apiIntake`-Objekt (bei den anderen Dokument-Aktionen, z. B. direkt nach `reparse`) ergänzen:

```js
  entfernungPruefen: (id, akteAz) =>
    request(`/intake/dokument/${id}/entfernung`, {
      method: 'POST',
      body: JSON.stringify({ akte_az: akteAz }),
    }),
```

(b) `frontend/src/views/ReviewQueueView.jsx` — nach `VerwerfenDialog` (Zeile 477) neue Komponente:

```jsx
function EntfernungDialog({ ergebnis, onClose }) {
  const r = ergebnis || {};
  const fmtKm = (v) => (v == null ? "—" : String(v).replace(".", ",") + " km");
  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 900,
    }}>
      <div style={{
        background: T.cardBg, width: 520,
        borderRadius: 10, padding: 24,
        boxShadow: "0 12px 40px rgba(0,0,0,0.25)",
      }}>
        <h3 style={{ margin: "0 0 10px", fontFamily: T.fontDisplay, color: T.navy }}>
          Entfernungsprüfung Referenzwerkstatt
        </h3>
        {!r.ok ? (
          <div style={{ padding: "8px 12px", marginBottom: 16,
            background: T.amberBg, color: T.amberText,
            border: `1px solid ${T.amber}`, borderRadius: 4, fontSize: T.textSm }}>
            ⚠ {r.fehler || "Prüfung fehlgeschlagen."}
          </div>
        ) : (
          <>
            <div style={{ color: T.textMuted, marginBottom: 12, fontSize: T.textSm }}>
              {r.werkstatt_name || "Werkstatt"}
              {r.werkstatt_adresse && <> · {r.werkstatt_adresse}</>}
            </div>
            <table style={{ borderCollapse: "collapse", fontSize: T.textSm, marginBottom: 12 }}>
              <tbody>
                <tr>
                  <td style={{ padding: "2px 12px 2px 0", color: T.textMid }}>Genannte Entfernung</td>
                  <td><strong>{fmtKm(r.km_genannt)}</strong></td>
                </tr>
                <tr>
                  <td style={{ padding: "2px 12px 2px 0", color: T.textMid }}>Echte Fahrstrecke</td>
                  <td><strong>{fmtKm(r.km_echt)}</strong>
                    {r.minuten != null && <> (ca. {r.minuten} Min.)</>}</td>
                </tr>
                {r.abweichung_km != null && (
                  <tr>
                    <td style={{ padding: "2px 12px 2px 0", color: T.textMid }}>Abweichung</td>
                    <td>{fmtKm(r.abweichung_km)}</td>
                  </tr>
                )}
              </tbody>
            </table>
            <div style={{
              padding: "8px 12px", marginBottom: 12, borderRadius: 4,
              fontSize: T.textSm, fontWeight: 600,
              background: r.unzumutbar ? T.greenBg : T.amberBg,
              color: r.unzumutbar ? T.greenText : T.amberText,
              border: `1px solid ${r.unzumutbar ? T.greenLight : T.amber}`,
            }}>
              {r.unzumutbar
                ? "Nicht zumutbar: über 15 km — Verweis angreifbar, Textbaustein gespeichert."
                : "Zumutbar: 15 km oder weniger — Verweis vermutlich haltbar."}
            </div>
            {r.unzumutbar && r.textbaustein && (
              <>
                <label style={{ display: "block", fontSize: T.textSm, fontWeight: 600, marginBottom: 4 }}>
                  Textbaustein
                </label>
                <textarea readOnly value={r.textbaustein} rows={6}
                  style={{ width: "100%", boxSizing: "border-box",
                    padding: "6px 10px", marginBottom: 12,
                    border: `1px solid ${T.border}`, borderRadius: 4,
                    fontFamily: T.fontBody, fontSize: T.textSm }} />
              </>
            )}
          </>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          {r.ok && r.unzumutbar && r.textbaustein && (
            <button onClick={() => navigator.clipboard?.writeText(r.textbaustein)}
              style={{ padding: "8px 16px", background: T.offWhite,
                border: `1px solid ${T.border}`, borderRadius: 4, cursor: "pointer" }}>
              Textbaustein kopieren
            </button>
          )}
          <button onClick={onClose}
            style={{ padding: "8px 16px", background: T.navy, color: T.white,
              border: "none", borderRadius: 4, cursor: "pointer", fontWeight: 600 }}>
            Schließen
          </button>
        </div>
      </div>
    </div>
  );
}
```

(c) Im `DetailPanel`: State-Zeile ergänzen (bei den anderen useState-Zeilen, nach Zeile 876):

```jsx
  const [entfernung, setEntfernung] = useState(null);
```

Handler ergänzen (nach `speichereFelder`, Zeile 1022):

```jsx
  const pruefeEntfernung = async () => {
    setAktion(true);
    try {
      const r = await apiIntake.entfernungPruefen(id, gewaehlteAkte);
      setEntfernung(r);
      if (r.ok) await laden({ skipFormReset: true });
    } catch (e) {
      setEntfernung({ ok: false, fehler: e.message });
    } finally { setAktion(false); }
  };
```

(Fehler landen bewusst im Dialog statt in `setError` — `error` ersetzt das ganze Panel, ein 404/422 der Prüfung soll aber nur das Popup betreffen.)

Button in der Sektion „Extrahierte Felder" direkt nach `<FelderEditor felder={felderMerged} onChange={feldChange} />` (Zeile 1292) einfügen:

```jsx
          {detail.klasse === "pruefbericht" && (
            <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 8 }}>
              <button onClick={pruefeEntfernung}
                disabled={aktion || pollAktiv || !gewaehlteAkte}
                title={gewaehlteAkte
                  ? "Echte Fahrstrecke Mandant → Referenzwerkstatt via OpenRouteService prüfen"
                  : "Erst Akte auswählen — die Mandanten-Adresse kommt aus der gewählten Akte"}
                style={{
                  padding: "6px 12px", background: T.navy, color: T.white,
                  border: "none", borderRadius: 4,
                  fontSize: T.textXs, fontWeight: 600, whiteSpace: "nowrap",
                  cursor: (aktion || pollAktiv || !gewaehlteAkte) ? "not-allowed" : "pointer",
                  opacity: gewaehlteAkte ? 1 : 0.5,
                }}>
                📍 Entfernung prüfen
              </button>
              {!gewaehlteAkte && (
                <span style={{ fontSize: T.textXs, color: T.textMuted }}>
                  Erst Akte auswählen (Mandanten-Adresse).
                </span>
              )}
            </div>
          )}
```

Dialog-Render ergänzen: an der Stelle, wo die anderen bedingten Dialoge des `DetailPanel` gerendert werden (suche `{zeigeFreigabe &&` bzw. `<FreigabeDialog` am Ende des Formular-Panels), daneben:

```jsx
      {entfernung && (
        <EntfernungDialog ergebnis={entfernung} onClose={() => setEntfernung(null)} />
      )}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend; npx vitest run src/views/ReviewQueueView.entfernung.test.jsx`
Expected: 4 passed.

- [ ] **Step 5: Volle Frontend-Suite + Build**

Run: `cd frontend; npm test` — Expected: alle Tests grün (Stand vorher: 446).
Run: `cd frontend; npm run build` — Expected: Build ohne Fehler.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.entfernung.test.jsx
git commit -m "feat(intake): Button + Popup Entfernungspruefung in der ReviewQueue

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: E2E-Smoke mit echtem ORS am Dok 516 (Controller-Task)

**Files:**
- Keine Code-Änderungen erwartet; reine Verifikation im Dev-Container.

**Interfaces:**
- Consumes: komplette Kette `_mandant_adresse("1280/25")` + `pruefe_entfernung` mit den echten Werkstatt-Daten aus Dok 516; `ORS_APIKEY` im Container.
- Produces: Nachweis, dass Geocoding+Routing für die echten Adressen funktioniert (die HTTP-Schicht ist durch Task 1 abgedeckt, die UI durch Task 2; die Browser-Abnahme des Popups macht RA Schatz).

- [ ] **Step 1: Mandanten-Adresse der echten Akte prüfen**

```bash
docker exec unfallakten-backend-dev python -c "
import sys; sys.path.insert(0, '/app')
from backend.routers.distanz_routes import _mandant_adresse
print(repr(_mandant_adresse('1280/25')))"
```

Expected: eine echte Adresse (nicht `None`). Falls `None`: Akte hat lokal keinen Mandanten mit Adresse — dann Befund an den User melden (Button liefe ins 404), NICHT raten.

- [ ] **Step 2: Echte Entfernungsprüfung (ein ORS-Call)**

```bash
docker exec unfallakten-backend-dev python -c "
import sys, json; sys.path.insert(0, '/app')
from backend.routers.distanz_routes import _mandant_adresse
from backend.services.werkstatt_service import pruefe_entfernung
r = pruefe_entfernung(
    mandant_adresse=_mandant_adresse('1280/25'),
    werkstatt_adresse='Philipp-Reis-Straße 9, 63128 Dietzenbach',
    werkstatt_name='Möser Arno - Karosseriefachbetrieb',
    km_genannt=16.0)
print(json.dumps({k: r[k] for k in ('ok','km_echt','minuten','abweichung_km','unzumutbar','fehler')}, ensure_ascii=False))"
```

Expected: `ok: true`, plausibler `km_echt`-Wert (zweistellig einstellig km-Bereich Offenbach↔Dietzenbach), `fehler: null`. Ergebnis für den User-Bericht notieren (insbesondere ob die 16,00 km der VHV realistisch sind).

- [ ] **Step 3: Kein Commit**

Nur Verifikation. Browser-Abnahme des Popups durch RA Schatz ist das verbleibende Human-Gate.
