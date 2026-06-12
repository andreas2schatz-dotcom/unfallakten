# US-02 – IMAP Auto-Polling: Design-Spec
**Datum:** 2026-06-12  
**Status:** Genehmigt  
**Scope:** Unfallakten-Backend + Health-Dashboard Frontend

---

## Ziel

Automatisches IMAP-Polling für vier Kanzlei-E-Mail-Accounts ohne manuellen Klick.  
Intervall und pro-Account-Aktivierung sind im Health-Dashboard konfigurierbar.

---

## Accounts

| Name      | Adresse                        |
|-----------|-------------------------------|
| unfall    | unfall@anwalt-offenbach.de    |
| termin    | termin@anwalt-offenbach.de    |
| bussgeld  | bussgeld@anwalt-offenbach.de  |
| info      | info@anwalt-offenbach.de      |

Alle vier Accounts teilen denselben IMAP-Server (imap.strato.de, Port 993 SSL).

---

## Architektur-Entscheidung

**Ansatz A (gewählt):** Ein APScheduler-Job tickt fix jede Minute. Er liest aus der DB welche Accounts aktiv sind und welches Intervall gilt. Pro Account prüft er `jetzt − letzter_lauf >= intervall_min`. Läuft nur wenn fällig. Kein Neustart des Schedulers bei Intervall-Änderung nötig.

---

## 1. Konfiguration (ENV-Variablen)

Passwörter bleiben in `.env`, nie in der DB.

```
# Gemeinsam für alle Accounts (bestehende Vars, unverändert)
EMAIL_HOST=imap.strato.de
EMAIL_PORT=993
EMAIL_FOLDER=INBOX

# Pro Account: eigener User + eigenes Passwort
EMAIL_USER_UNFALL=unfall@anwalt-offenbach.de
EMAIL_PASSWORD_UNFALL=...
EMAIL_USER_TERMIN=termin@anwalt-offenbach.de
EMAIL_PASSWORD_TERMIN=...
EMAIL_USER_BUSSGELD=bussgeld@anwalt-offenbach.de
EMAIL_PASSWORD_BUSSGELD=...
EMAIL_USER_INFO=info@anwalt-offenbach.de
EMAIL_PASSWORD_INFO=...
```

Der bestehende `EMAIL_USER` / `EMAIL_PASSWORD` bleibt für den manuellen Import (`POST /email/import`) rückwärtskompatibel erhalten.

---

## 2. Datenmodell

**Schema-Migration 43** — neue Tabelle `imap_polling_config`:

```sql
CREATE TABLE IF NOT EXISTS imap_polling_config (
    account       TEXT PRIMARY KEY,
    aktiv         INTEGER NOT NULL DEFAULT 1,
    intervall_min INTEGER NOT NULL DEFAULT 5,
    letzter_lauf  TEXT,       -- ISO-8601 Timestamp
    letzter_status TEXT,      -- 'ok' | 'fehler' | NULL
    letzter_fehler TEXT
);
```

**Seed** (wird beim ersten Start automatisch angelegt, falls Tabelle leer):
```sql
INSERT OR IGNORE INTO imap_polling_config (account, aktiv, intervall_min)
VALUES
    ('unfall',   1, 5),
    ('termin',   1, 5),
    ('bussgeld', 1, 5),
    ('info',     1, 5);
```

`intervall_min` ist in allen 4 Rows identisch — UI schreibt beim Speichern alle Rows gleichzeitig.

---

## 3. Backend

### 3.1 Neues Modul `backend/email_import/polling_service.py`

**`hole_accounts() -> list[dict]`**
- Liest alle 4 Rows aus `imap_polling_config`
- Ergänzt pro Row: User + Passwort aus ENV (`EMAIL_USER_UNFALL`, `EMAIL_PASSWORD_UNFALL` etc.)
- Gibt zurück: `[{ account, aktiv, intervall_min, user, passwort_vorhanden, letzter_lauf, letzter_status, letzter_fehler }]`

**`fuehre_polling_durch() -> None`**
- Wird vom APScheduler jede Minute aufgerufen
- Für jeden Account:
  - Überspringe wenn `aktiv = 0`
  - Überspringe wenn Passwort fehlt in ENV → `letzter_fehler = "EMAIL_PASSWORD_X nicht gesetzt"`
  - Prüfe: `letzter_lauf IS NOT NULL AND jetzt − letzter_lauf < intervall_min * 60s` → überspringe; bei `letzter_lauf = NULL` (noch nie gelaufen) gilt Account sofort als fällig
  - Rufe `fuehre_import_lauf_durch(imap_config=...)` auf
  - Schreibe `letzter_lauf`, `letzter_status='ok'` oder `letzter_status='fehler'` + `letzter_fehler` in DB
- Fehler eines einzelnen Accounts brechen das Polling der anderen Accounts nicht ab

### 3.2 Neue Endpoints in `system_routes.py`

**`GET /system/imap-polling`**
```json
{
  "accounts": [
    {
      "account": "unfall",
      "aktiv": true,
      "intervall_min": 5,
      "passwort_vorhanden": true,
      "letzter_lauf": "2026-06-12T14:23:00",
      "letzter_status": "ok",
      "letzter_fehler": null
    },
    ...
  ]
}
```

**`PATCH /system/imap-polling`**
```json
{
  "intervall_min": 10,
  "accounts": {
    "unfall":   true,
    "termin":   false,
    "bussgeld": true,
    "info":     true
  }
}
```
Schreibt alle Felder in DB. Gibt den aktualisierten Status zurück (gleiche Struktur wie GET).

### 3.3 Änderungen in `app.py`

Zweiter APScheduler-Job, analog zum bestehenden `health_ramicro`:

```python
from .email_import.polling_service import fuehre_polling_durch

scheduler.add_job(
    id="imap_polling",
    func=fuehre_polling_durch,
    trigger="interval",
    seconds=60,
    replace_existing=True,
)
```

### 3.4 Änderungen in `health_service.py`

`get_status()` ersetzt den bisherigen IMAP-Placeholder durch den echten Polling-Status:
- Importiert `hole_accounts()` aus `polling_service`
- Gibt `imap` als Array der 4 Account-Objekte zurück

---

## 4. Frontend

### 4.1 Änderungen in `EinstellungenView.jsx`

**Neuer State:**
```js
const [imapPolling, setImapPolling] = useState(null);  // null = lädt
const [imapIntervall, setImapIntervall] = useState(5);
const [imapSpeichert, setImapSpeichert] = useState(false);
```

**Polling alle 30s** wenn Tab `system_status` aktiv:
```js
useEffect(() => {
  if (tab !== "system_status") return;
  const id = setInterval(() => ladeSysStatus(), 30_000);
  return () => clearInterval(id);
}, [tab]);
```

**Neuer IMAP-Block** (ersetzt bisherigen Placeholder im `system_status`-Tab):

```
┌─────────────────────────────────────────────────────┐
│ E-Mail Polling          Intervall: [5 min ▼] [Speichern] │
├──────────┬───────┬─────────────┬────────────────────┤
│ unfall@  │ ● AN  │ vor 2 Min   │ ✓ OK               │
│ termin@  │ ● AN  │ vor 2 Min   │ ✓ OK               │
│ bussgeld@│ ○ AUS │ —           │ —                  │
│ info@    │ ● AN  │ vor 7 Min   │ ✗ Passwort fehlt   │
└──────────┴───────┴─────────────┴────────────────────┘
```

- Toggle pro Account → sofortiger `PATCH /system/imap-polling`
- Status-Dot: grün (ok), rot (fehler), grau (nie gelaufen / kein Passwort)
- Intervall-Dropdown: 5 / 10 / 15 / 30 Minuten

### 4.2 Änderungen in `api.js`

Neue Funktionen unter `apiSystem`:
- `apiSystem.getImapPolling()` → `GET /system/imap-polling`
- `apiSystem.patchImapPolling(data)` → `PATCH /system/imap-polling`

---

## 5. Nicht im Scope

- Erstmalige Konfiguration der IMAP-Passwörter aus dem UI (bleibt `.env`)
- Per-Account unterschiedliche Intervalle
- Retry-Logik bei IMAP-Verbindungsfehlern (ein Fehlschlag → nächster regulärer Lauf)
- Benachrichtigung bei dauerhaftem IMAP-Fehler

---

## 6. Migrations-Nummer

Schema-Migration 43 (nächste freie nach Migration 42 aus E-Mail-Workflow-Redesign).
