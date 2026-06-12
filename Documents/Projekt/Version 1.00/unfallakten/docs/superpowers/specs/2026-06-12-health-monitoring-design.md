# Design: Health-Monitoring (US-01 + US-06)
> Erstellt: 2026-06-12

## Scope

**US-01** — RA-Micro Heartbeat & Verbindungs-Banner  
**US-06** — Health-Dashboard UI (System-Status-Tab in Einstellungen)

Gemeinsame Grundlage: APScheduler im Flask-Prozess. Dieselbe Infrastruktur wird später für US-02 (IMAP Auto-Polling) wiederverwendet.

---

## Backend

### Neues Modul `backend/system/health_service.py`

In-Memory-Cache `_cache: dict` hält den Status aller Services. Wird beim App-Start initialisiert und durch den Scheduler aktuell gehalten.

**Funktionen:**
- `check_ramicro()` — ruft `verbindung_pruefen()` auf, schreibt `ok`, `letzter_sync_ts` (datetime) und ggf. `fehler` in `_cache["ramicro"]`. Loggt Zustandswechsel (ok→fehler, fehler→ok).
- `get_status() -> dict` — berechnet `letzter_sync_vor_s` zur Laufzeit aus `letzter_sync_ts` und gibt den vollständigen Status zurück. `letzter_sync_vor_s` wird **nicht** im Cache gespeichert, damit der Wert bei jedem Abruf aktuell ist.

**Interner Cache (nur im Speicher):**
```python
_cache = {
    "ramicro": { "ok": None, "letzter_sync_ts": None, "fehler": None }
}
```

**Response-Struktur von `GET /system/status`:**
```json
{
  "ramicro": {
    "ok": false,
    "letzter_sync_vor_s": 240,
    "fehler": "Connection refused"
  },
  "imap": {
    "ok": true,
    "konfiguriert": true,
    "ungelesen": 3,
    "letzter_sync_vor_s": 60
  },
  "sv_portal": {
    "ok": null,
    "konfiguriert": false
  }
}
```

*Hinweis: `imap` wird in US-02 auf drei separate Accounts (`unfall`, `termin`, `bussgeld`) aufgespalten. Die Cache-Struktur ist darauf vorbereitet.*

### APScheduler-Setup in `backend/app.py`

- Dependency: `flask-apscheduler`
- Initialisierung in `erstelle_app()` nach Blueprint-Registrierung
- Job `health_ramicro`: ruft `check_ramicro()` alle 60s auf, `id="health_ramicro"`, `replace_existing=True`
- Beim App-Start: `check_ramicro()` einmalig direkt aufrufen (verhindert 60s-Lücke ohne Status)
- Scheduler startet nur wenn `not app.testing`

### Neuer Blueprint `backend/routers/system_routes.py`

**`GET /system/status`**  
Gibt `_cache` zurück. Der `imap`-Block wird aus dem bestehenden `/email/import/status`-Endpoint proxied; `sv_portal` ist statisch `{ok: null, konfiguriert: false}` bis US-03 gebaut ist.

**`POST /system/ramicro/retry`**  
Ruft `check_ramicro()` sofort auf und gibt den aktualisierten `_cache["ramicro"]`-Block zurück. Kein Background-Job — synchroner Call, Response kommt nach dem Check (typisch <3s).

### Registrierung

`system_routes.py` wird in `erstelle_app()` als Blueprint registriert (analog zu allen anderen Blueprints).

---

## Frontend

### `src/api.js` — zwei neue Funktionen

```js
getSystemStatus()   // GET /system/status
retryRamicro()      // POST /system/ramicro/retry
```

### `src/App.jsx` — zentrales Polling

- Neuer State `systemStatus` (initial `null`)
- `useEffect` on mount: ruft `getSystemStatus()` einmal auf
- `setInterval` alle 30s: ruft `getSystemStatus()` auf, aktualisiert `systemStatus`
- Cleanup: `clearInterval` on unmount
- `systemStatus` wird als Prop an Header und (via bestehende Props-Kette) an `EinstellungenView` weitergegeben

### Header — Verbindungs-Banner

Neue bedingte Zeile direkt unterhalb der Header-Navigationsleiste.

- **Erscheint wenn:** `systemStatus?.ramicro?.ok === false`
- **Verschwindet automatisch** wenn `ok` wieder `true`
- **Inhalt:** roter Balken über volle Breite
  - Links: „⚠ RA-Micro nicht erreichbar — letzter Sync vor X Minuten"
  - Rechts: Button „→ System-Status öffnen"
- **Klick auf Button:** navigiert zu `/einstellungen?tab=system_status` — `EinstellungenView` liest beim Mount den `tab`-Query-Parameter aus und setzt den aktiven Tab entsprechend

### `src/views/EinstellungenView.jsx` — Tab „System-Status"

Neuer Tab `system_status` wird der bestehenden Tab-Leiste hinzugefügt.

**Inhalt (Layout A — gruppierte Liste):**

**Gruppe „RA-Micro"** (prominent, volle Breite)
- Statuspunkt (grün/rot) + Name + letzter Sync vor X Minuten
- Button „↺ Neu versuchen": ruft `retryRamicro()` auf, aktualisiert lokalen State sofort

**Gruppe „E-Mail (IMAP)"**
- Eine Zeile für den aktuell konfigurierten IMAP-Account
- Status: grün (ok), rot (fehler), gelb (konfiguriert, noch nicht geprüft), grau (nicht konfiguriert)
- Wird in US-02 auf drei Zeilen (unfall@, termin@, bussgeld@) erweitert

**Gruppe „Externe Dienste"**
- SV-Portal: grau, „Noch nicht eingerichtet" — bis US-03

**Farb-Semantik:**
| Farbe | Bedeutung |
|---|---|
| Grün | `ok: true` |
| Rot | `ok: false` |
| Gelb | Konfiguriert, Status unbekannt (`ok: null`, `konfiguriert: true`) |
| Grau | Nicht konfiguriert (`konfiguriert: false`) |

---

## Datenfluss

```
APScheduler (alle 60s)
    → check_ramicro() → _cache["ramicro"] aktualisieren

App.jsx (alle 30s)
    → GET /system/status
    → systemStatus State aktualisieren
    → Header: Banner wenn ramicro.ok === false
    → EinstellungenView: System-Status Tab zeigt aktuelle Werte

Retry-Button
    → POST /system/ramicro/retry
    → sofortiger Check (<3s)
    → _cache["ramicro"] aktualisieren
    → Response → lokaler State im Tab sofort aktualisiert
```

---

## Out of Scope (explizit ausgeschlossen)

- IMAP-Polling / Multi-Account → US-02
- SV-Portal Live-Status → US-03
- Fehlerhistorie / Logging-UI
- Push-Notifications / Alarmierung
