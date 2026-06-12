# Health-Monitoring (US-01 + US-06) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RA-Micro Heartbeat mit automatischem Reconnect-Banner im Header (US-01) und System-Status-Tab in den Einstellungen (US-06).

**Architecture:** Flask-APScheduler prüft die RA-Micro-Verbindung alle 60s und schreibt das Ergebnis in einen In-Memory-Cache in `health_service.py`. Ein neuer Blueprint `system_routes.py` stellt `/system/status` und `/system/ramicro/retry` bereit. Das Frontend pollt `/system/status` alle 30s; bei `ramicro.ok === false` erscheint ein roter Banner unterhalb des Headers mit einem Link zum neuen System-Status-Tab in den Einstellungen.

**Tech Stack:** Python `flask-apscheduler==1.13.1`, Flask Blueprint, React `useState`/`useEffect`, bestehendes api.js Muster.

---

## Dateiübersicht

| Aktion | Datei | Zweck |
|--------|-------|-------|
| CREATE | `backend/system/__init__.py` | Paket-Marker |
| CREATE | `backend/system/health_service.py` | In-Memory-Cache + check_ramicro() + get_status() |
| CREATE | `backend/routers/system_routes.py` | Blueprint: GET /system/status, POST /system/ramicro/retry |
| MODIFY | `backend/app.py` | APScheduler init + Blueprint registrieren |
| MODIFY | `requirements.txt` | flask-apscheduler hinzufügen |
| CREATE | `backend/tests/test_health_service.py` | Unit-Tests für health_service |
| MODIFY | `frontend/src/api.js` | apiSystem Export hinzufügen |
| MODIFY | `frontend/src/App.jsx` | systemStatus Polling + Banner + pendingEinstellungenTab |
| MODIFY | `frontend/src/views/EinstellungenView.jsx` | System-Status Tab |

---

## Task 1: health_service.py (TDD)

**Files:**
- Create: `backend/system/__init__.py`
- Create: `backend/system/health_service.py`
- Create: `backend/tests/test_health_service.py`

- [ ] **Schritt 1: Test-Datei anlegen**

```python
# backend/tests/test_health_service.py
import os, sys, unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _reload():
    import importlib
    import backend.system.health_service as hs
    importlib.reload(hs)
    return hs


class TestCheckRamicro(unittest.TestCase):

    def setUp(self):
        hs = _reload()
        hs._cache["ramicro"] = {"ok": None, "letzter_sync_ts": None, "fehler": None}

    def test_ok_setzt_cache_ok_true(self):
        hs = _reload()
        with patch.object(hs, "verbindung_pruefen", return_value={"status": "ok", "host": "x", "datenbank": "RAMICRO"}):
            hs.check_ramicro()
        self.assertTrue(hs._cache["ramicro"]["ok"])
        self.assertIsNone(hs._cache["ramicro"]["fehler"])
        self.assertIsNotNone(hs._cache["ramicro"]["letzter_sync_ts"])

    def test_fehler_setzt_cache_ok_false(self):
        hs = _reload()
        with patch.object(hs, "verbindung_pruefen", return_value={"status": "fehler", "meldung": "Connection refused"}):
            hs.check_ramicro()
        self.assertFalse(hs._cache["ramicro"]["ok"])
        self.assertEqual(hs._cache["ramicro"]["fehler"], "Connection refused")

    def test_deaktiviert_setzt_cache_ok_false(self):
        hs = _reload()
        with patch.object(hs, "verbindung_pruefen", return_value={"status": "deaktiviert", "meldung": "RAMICRO_AKTIV ist nicht 'true'"}):
            hs.check_ramicro()
        self.assertFalse(hs._cache["ramicro"]["ok"])


class TestGetStatus(unittest.TestCase):

    def setUp(self):
        hs = _reload()
        hs._cache["ramicro"] = {"ok": None, "letzter_sync_ts": None, "fehler": None}

    def test_letzter_sync_vor_s_ist_none_wenn_nie_gecheckt(self):
        hs = _reload()
        status = hs.get_status()
        self.assertIsNone(status["ramicro"]["letzter_sync_vor_s"])

    def test_letzter_sync_vor_s_wird_aus_timestamp_berechnet(self):
        hs = _reload()
        hs._cache["ramicro"] = {
            "ok": True,
            "letzter_sync_ts": datetime.now() - timedelta(seconds=120),
            "fehler": None,
        }
        status = hs.get_status()
        self.assertAlmostEqual(status["ramicro"]["letzter_sync_vor_s"], 120, delta=3)

    def test_response_enthaelt_imap_und_sv_portal_keys(self):
        hs = _reload()
        status = hs.get_status()
        self.assertIn("imap", status)
        self.assertIn("sv_portal", status)
        self.assertFalse(status["sv_portal"]["konfiguriert"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 2: Tests laufen lassen — müssen FAIL sein**

```
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten"
pytest backend/tests/test_health_service.py -v
```

Erwartet: `ERROR` (Modul nicht gefunden).

- [ ] **Schritt 3: `backend/system/__init__.py` anlegen**

```python
# backend/system/__init__.py
```

(Leere Datei.)

- [ ] **Schritt 4: `backend/system/health_service.py` anlegen**

```python
# backend/system/health_service.py
import logging
from datetime import datetime

from ..ramicro.connector import verbindung_pruefen
from ..email_import.imap_client import ist_konfiguriert

logger = logging.getLogger(__name__)

_cache: dict = {
    "ramicro": {"ok": None, "letzter_sync_ts": None, "fehler": None}
}


def check_ramicro() -> None:
    result = verbindung_pruefen()
    war_ok = _cache["ramicro"]["ok"]
    jetzt_ok = result["status"] == "ok"
    if war_ok is not None and war_ok != jetzt_ok:
        if jetzt_ok:
            logger.info("RA-Micro: Verbindung wiederhergestellt")
        else:
            logger.warning("RA-Micro: Verbindung unterbrochen – %s", result.get("meldung", ""))
    _cache["ramicro"] = {
        "ok": jetzt_ok,
        "letzter_sync_ts": datetime.now(),
        "fehler": result.get("meldung") if not jetzt_ok else None,
    }


def get_status() -> dict:
    rm = _cache["ramicro"]
    letzter_sync_vor_s = None
    if rm["letzter_sync_ts"] is not None:
        letzter_sync_vor_s = int((datetime.now() - rm["letzter_sync_ts"]).total_seconds())
    try:
        imap_konfig = ist_konfiguriert()
    except Exception:
        imap_konfig = False
    return {
        "ramicro": {
            "ok": rm["ok"],
            "letzter_sync_vor_s": letzter_sync_vor_s,
            "fehler": rm["fehler"],
        },
        "imap": {"ok": None, "konfiguriert": imap_konfig},
        "sv_portal": {"ok": None, "konfiguriert": False},
    }
```

- [ ] **Schritt 5: Tests laufen lassen — müssen alle PASS sein**

```
pytest backend/tests/test_health_service.py -v
```

Erwartet: 7 passed.

- [ ] **Schritt 6: Commit**

```
git add backend/system/__init__.py backend/system/health_service.py backend/tests/test_health_service.py
git commit -m "feat(health): health_service Modul mit check_ramicro und get_status"
```

---

## Task 2: system_routes.py Blueprint

**Files:**
- Create: `backend/routers/system_routes.py`

- [ ] **Schritt 1: Blueprint anlegen**

```python
# backend/routers/system_routes.py
import logging
from flask import Blueprint, jsonify
from ..auth.middleware import login_erforderlich
from ..system.health_service import check_ramicro, get_status

system_bp = Blueprint("system", __name__)
logger = logging.getLogger(__name__)


@system_bp.route("/system/status", methods=["GET"])
@login_erforderlich
def system_status():
    return jsonify(get_status())


@system_bp.route("/system/ramicro/retry", methods=["POST"])
@login_erforderlich
def ramicro_retry():
    check_ramicro()
    status = get_status()
    return jsonify(status["ramicro"])
```

- [ ] **Schritt 2: Commit**

```
git add backend/routers/system_routes.py
git commit -m "feat(health): system_routes Blueprint GET /system/status + POST /system/ramicro/retry"
```

---

## Task 3: APScheduler + Blueprint in app.py

**Files:**
- Modify: `requirements.txt`
- Modify: `backend/app.py`

- [ ] **Schritt 1: flask-apscheduler in requirements.txt eintragen**

In `requirements.txt` nach der Zeile `Flask==3.1.2` folgende Zeile hinzufügen:

```
flask-apscheduler==1.13.1   # Hintergrund-Jobs (Health-Checks, später IMAP-Polling)
```

- [ ] **Schritt 2: Paket installieren**

```
pip install flask-apscheduler==1.13.1
```

- [ ] **Schritt 3: app.py anpassen**

**Import-Block** — nach Zeile 17 (`from flask import Flask, jsonify`) folgende Zeile einfügen:

```python
from flask_apscheduler import APScheduler
```

**Blueprint-Import** — nach Zeile 47 (`from .routers.portal_routes import portal_bp`) einfügen:

```python
from .routers.system_routes import system_bp
```

**Blueprint-Registrierung** — nach Zeile 175 (`app.register_blueprint(portal_bp)`) einfügen:

```python
    app.register_blueprint(system_bp)
```

**Scheduler-Setup** — nach dem Blueprint-Register-Block (nach `logger.info("Alle Blueprints registriert.")`, Zeile 176) einfügen:

```python
    # ── APScheduler: Hintergrund-Health-Checks ────────────────────────────────
    if not app.testing:
        from .system.health_service import check_ramicro as _check_ramicro
        scheduler = APScheduler()
        app.config["SCHEDULER_API_ENABLED"] = False
        scheduler.init_app(app)
        scheduler.add_job(
            id="health_ramicro",
            func=_check_ramicro,
            trigger="interval",
            seconds=60,
            replace_existing=True,
        )
        scheduler.start()
        _check_ramicro()
        logger.info("APScheduler gestartet: RA-Micro Health-Check alle 60s")
```

- [ ] **Schritt 4: Manuelle Smoke-Test — Server starten und Endpoint prüfen**

```
python -m backend.app
```

In einem zweiten Terminal (mit gültigem Token):
```
curl -H "Authorization: Bearer <token>" http://localhost:5000/system/status
```

Erwartet: JSON mit Keys `ramicro`, `imap`, `sv_portal`. `ramicro.ok` ist `true` oder `false` (nicht `null`) weil der initiale Check bereits lief.

- [ ] **Schritt 5: Commit**

```
git add requirements.txt backend/app.py
git commit -m "feat(health): APScheduler + system_bp in erstelle_app() eingebunden"
```

---

## Task 4: Frontend api.js — apiSystem

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Schritt 1: apiSystem Export am Ende von api.js hinzufügen**

Am Ende der Datei `frontend/src/api.js` (nach dem letzten `export const`-Block) einfügen:

```js
export const apiSystem = {
  getStatus: () => request("/system/status"),
  retryRamicro: () => request("/system/ramicro/retry", { method: "POST" }),
};
```

- [ ] **Schritt 2: Commit**

```
git add frontend/src/api.js
git commit -m "feat(health): apiSystem.getStatus + retryRamicro in api.js"
```

---

## Task 5: App.jsx — Polling + Banner + pendingEinstellungenTab

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Schritt 1: apiSystem importieren**

In Zeile 2 von `App.jsx` den bestehenden Import erweitern:

```js
import { auth as apiAuth, ramicroListe, emailImport, apiSystem } from "./api.js";
```

- [ ] **Schritt 2: systemStatus State + pendingEinstellungenTab State in AppShell hinzufügen**

In der `AppShell`-Funktion nach Zeile 98 (`const { online } = useBackend();`) einfügen:

```js
  const [systemStatus,           setSystemStatus]           = useState(null);
  const [pendingEinstellungenTab, setPendingEinstellungenTab] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try { setSystemStatus(await apiSystem.getStatus()); } catch {}
    };
    poll();
    const id = setInterval(poll, 30000);
    return () => clearInterval(id);
  }, []);
```

- [ ] **Schritt 3: Banner JSX einfügen**

In der `AppShell` return-Anweisung, direkt nach `<TopNav ... />` (Zeile 164) und vor dem Haupt-Layout-`<div>` einfügen:

```jsx
      {systemStatus?.ramicro?.ok === false && (
        <div style={{ background:"#c0392b", color:"white", padding:"7px 16px", display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0, fontFamily:"'Figtree',sans-serif", fontSize:"0.875rem" }}>
          <span>
            ⚠ <strong>RA-Micro nicht erreichbar</strong>
            {systemStatus.ramicro.letzter_sync_vor_s != null && (
              <span style={{ fontWeight:400 }}>
                {" — letzter Sync vor "}
                {systemStatus.ramicro.letzter_sync_vor_s < 60
                  ? "wenigen Sekunden"
                  : `${Math.round(systemStatus.ramicro.letzter_sync_vor_s / 60)} Minuten`}
              </span>
            )}
          </span>
          <button
            onClick={() => { setActive("einstellungen"); setPendingEinstellungenTab("system_status"); }}
            style={{ background:"rgba(255,255,255,0.25)", color:"white", border:"none", borderRadius:4, padding:"4px 12px", cursor:"pointer", fontSize:"0.825rem", fontFamily:"'Figtree',sans-serif" }}>
            → System-Status öffnen
          </button>
        </div>
      )}
```

- [ ] **Schritt 4: pendingEinstellungenTab an EinstellungenView übergeben**

Die bestehende Zeile (ca. Zeile 254):
```jsx
: active==="einstellungen"   ? <EinstellungenView />
```
ersetzen durch:
```jsx
: active==="einstellungen"   ? <EinstellungenView initialTab={pendingEinstellungenTab} onTabMounted={() => setPendingEinstellungenTab(null)} />
```

- [ ] **Schritt 5: Commit**

```
git add frontend/src/App.jsx
git commit -m "feat(health): systemStatus Polling, RA-Micro Banner, pendingEinstellungenTab in App.jsx"
```

---

## Task 6: EinstellungenView — System-Status Tab

**Files:**
- Modify: `frontend/src/views/EinstellungenView.jsx`

- [ ] **Schritt 1: Props + initialTab State-Init + useEffect in EinstellungenView**

Die Funktionssignatur von `EinstellungenView` ändern:

```jsx
function EinstellungenView({ initialTab = null, onTabMounted } = {}) {
```

Den bestehenden `useState("versicherer")` für `tab` ersetzen durch:

```jsx
  const [tab, setTab] = useState(initialTab || "versicherer");
```

Direkt danach einen neuen `useEffect` einfügen:

```jsx
  useEffect(() => {
    if (initialTab) {
      setTab(initialTab);
      onTabMounted?.();
    }
  }, [initialTab]);
```

- [ ] **Schritt 2: apiSystem importieren**

In den bestehenden Import in EinstellungenView (Zeile 10):
```js
import {
  emailImport as apiEmail,
  apiEinstellungen,
  apiSvPortal,
} from "../api.js";
```
`apiSystem` hinzufügen:
```js
import {
  emailImport as apiEmail,
  apiEinstellungen,
  apiSvPortal,
  apiSystem,
} from "../api.js";
```

- [ ] **Schritt 3: systemStatus State für den Tab anlegen**

In den State-Deklarationen von EinstellungenView (nach den bestehenden `useState`-Aufrufen) einfügen:

```jsx
  const [sysStatus,      setSysStatus]      = useState(null);
  const [sysLaedt,       setSysLaedt]       = useState(false);
  const [sysRetryLaedt,  setSysRetryLaedt]  = useState(false);
```

- [ ] **Schritt 4: Tab-Lade-Effekt für system_status**

Im bestehenden `useEffect([tab])` (der bereits `if (tab === "sv_portal") ladeSvListe();` enthält) eine weitere Bedingung hinzufügen:

```js
    if (tab === "system_status") {
      setSysLaedt(true);
      apiSystem.getStatus()
        .then(setSysStatus)
        .catch(() => {})
        .finally(() => setSysLaedt(false));
    }
```

- [ ] **Schritt 5: Tab-Button in der Tab-Leiste einfügen**

In `EinstellungenView.jsx` das Inline-Array der Tab-Definitionen suchen (ca. Zeile 225). Es sieht so aus:

```jsx
{[
  ["versicherer",    "🏦 Versicherer"],
  ["gutachter",      "🔍 Gutachter"],
  ...
  ["zustaendigkeit", "⚖ Zuständigkeit"],
].map(([id, label]) => (
```

Dort am Ende, nach `["zustaendigkeit","⚖ Zuständigkeit"]`, folgende Zeile einfügen:

```jsx
  ["system_status",  "⚙ System-Status"],
```

- [ ] **Schritt 6: System-Status Tab-Inhalt rendern**

Nach dem letzten `{tab === "sv_portal" && (...)}` Block (ca. Zeile 1113) einfügen:

```jsx
        {tab === "system_status" && (
          <div style={{ maxWidth: 680 }}>
            <Card>
              <CardHead title="System-Status" />
              {sysLaedt && <p style={{ color: T.textSub, padding: "1rem" }}>Wird geladen…</p>}
              {!sysLaedt && sysStatus && (
                <div style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>

                  {/* RA-Micro */}
                  <div style={{ background: T.cardBg, borderRadius: 8, padding: "0.75rem 1rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <span style={{ width: 12, height: 12, borderRadius: "50%", display: "inline-block", flexShrink: 0,
                        background: sysStatus.ramicro.ok === true ? "#2ecc71" : sysStatus.ramicro.ok === false ? "#e74c3c" : "#f39c12" }} />
                      <div>
                        <div style={{ color: T.text, fontWeight: 600 }}>RA-Micro Datenbank</div>
                        <div style={{ color: T.textSub, fontSize: "0.8rem" }}>
                          {sysStatus.ramicro.ok === true && "Verbunden"}
                          {sysStatus.ramicro.ok === false && `Nicht erreichbar${sysStatus.ramicro.fehler ? ` – ${sysStatus.ramicro.fehler}` : ""}`}
                          {sysStatus.ramicro.ok === null && "Noch nicht geprüft"}
                          {sysStatus.ramicro.letzter_sync_vor_s != null && (
                            <span> · vor {sysStatus.ramicro.letzter_sync_vor_s < 60 ? "wenigen Sekunden" : `${Math.round(sysStatus.ramicro.letzter_sync_vor_s / 60)} Min`}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <Btn
                      label={sysRetryLaedt ? "…" : "↺ Neu versuchen"}
                      disabled={sysRetryLaedt}
                      onClick={async () => {
                        setSysRetryLaedt(true);
                        try {
                          const updated = await apiSystem.retryRamicro();
                          setSysStatus(prev => ({ ...prev, ramicro: updated }));
                        } catch {}
                        finally { setSysRetryLaedt(false); }
                      }}
                    />
                  </div>

                  {/* IMAP */}
                  <div style={{ color: T.textSub, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", padding: "0.5rem 0 0.25rem" }}>E-Mail (IMAP)</div>
                  <div style={{ background: T.cardBg, borderRadius: 8, padding: "0.75rem 1rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <span style={{ width: 10, height: 10, borderRadius: "50%", display: "inline-block", flexShrink: 0,
                        background: sysStatus.imap?.konfiguriert ? (sysStatus.imap.ok === true ? "#2ecc71" : sysStatus.imap.ok === false ? "#e74c3c" : "#f39c12") : "#888" }} />
                      <div>
                        <div style={{ color: T.text, fontWeight: 600 }}>{sysStatus.imap?.konfiguriert ? "IMAP konfiguriert" : "IMAP nicht konfiguriert"}</div>
                        <div style={{ color: T.textSub, fontSize: "0.8rem" }}>
                          {sysStatus.imap?.konfiguriert ? "Wird in US-02 um Polling erweitert" : "EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD in .env setzen"}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* SV-Portal */}
                  <div style={{ color: T.textSub, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", padding: "0.5rem 0 0.25rem" }}>Externe Dienste</div>
                  <div style={{ background: T.cardBg, borderRadius: 8, padding: "0.75rem 1rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", display: "inline-block", flexShrink: 0, background: "#888" }} />
                    <div>
                      <div style={{ color: T.text, fontWeight: 600 }}>SV-Portal</div>
                      <div style={{ color: T.textSub, fontSize: "0.8rem" }}>Noch nicht eingerichtet (US-03)</div>
                    </div>
                  </div>

                </div>
              )}
            </Card>
          </div>
        )}
```

- [ ] **Schritt 7: Commit**

```
git add frontend/src/views/EinstellungenView.jsx
git commit -m "feat(health): System-Status Tab in EinstellungenView (US-06)"
```

---

## Abschluss-Check

- [ ] Backend starten: `python -m backend.app` — kein Fehler beim Start, APScheduler-Meldung im Log
- [ ] `pytest backend/tests/test_health_service.py -v` — 7 passed
- [ ] Frontend starten: `npm run dev` (im `frontend/`-Ordner)
- [ ] In der App: Einstellungen → System-Status Tab öffnet sich
- [ ] RA-Micro in `.env` vorübergehend deaktivieren (`RAMICRO_AKTIV=false`), 35s warten → roter Banner erscheint
- [ ] Banner-Button klicken → springt direkt zum System-Status Tab
- [ ] „↺ Neu versuchen" klicken → Status aktualisiert sich
- [ ] RA-Micro wieder aktivieren → Banner verschwindet beim nächsten Poll (max. 30s)
