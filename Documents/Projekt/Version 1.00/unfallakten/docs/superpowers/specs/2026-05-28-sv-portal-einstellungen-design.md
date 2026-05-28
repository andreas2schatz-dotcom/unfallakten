# Design: SV-Portal-Zugang in Einstellungen

**Datum:** 2026-05-28  
**Status:** Approved  
**Projekt:** Unfallakten-Verwaltungssystem · Koch, Schatz & Kollegen

---

## Ziel

Im Einstellungs-Tab „SV-Portal" kann der Admin verwalten, welche Sachverständigen Zugang zum Stakeholder-Portal (portal.anwalt-offenbach.de) erhalten, und pro Akte steuern, welche Akten im Portal sichtbar sind.

---

## Layout

Zwei-Spalten-Ansicht innerhalb des neuen Einstellungs-Tabs:

- **Linke Spalte (240 px):** Liste aller angelegten SV-Portal-Accounts + Button „SV-Portal-Zugang anlegen"
- **Rechte Spalte (flex):** Detail des ausgewählten SV — Name, E-Mail, Status, Aktionen, Liste der zugeordneten Akten mit portal_aktiv-Toggle

Statusanzeige per farbigem Punkt in der SV-Liste:
- Grün = aktiv im Portal
- Amber = Einladung noch nicht gesendet
- Grau = deaktiviert

---

## Datenbank — Migration 41

Neue Tabelle `sv_portal_accounts`:

```sql
CREATE TABLE sv_portal_accounts (
    adressnr        INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    vorname         TEXT,
    email           TEXT    NOT NULL UNIQUE,
    portal_aktiv    INTEGER NOT NULL DEFAULT 1 CHECK(portal_aktiv IN (0,1)),
    einladung_gesendet_am TEXT,
    angelegt_am     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
```

`adressnr` ist die RA-MICRO `iAdressnummer` aus `tblAdressen` — gleichzeitig PK und Verknüpfung zu RA-MICRO.

---

## RA-MICRO-Adress-Lookup

Neue Funktion `hole_adresse_by_nr(adressnr)` in `backend/ramicro/adress_service.py`:

```sql
SELECT TOP 1
    iAdressnummer AS adressnr,
    sNachname     AS name,
    sVorname      AS vorname,
    sEMail        AS email
FROM tblAdressen
WHERE iAdressnummer = %(adressnr)s
```

Gibt `None` zurück wenn keine Verbindung oder kein Treffer. Frontend zeigt dann Fehlermeldung.

---

## Backend-Router

Neue Datei `backend/routers/sv_portal_routes.py`, Blueprint-Prefix `/einstellungen/sv-portal`.

| Methode | Pfad | Funktion |
|---|---|---|
| `GET` | `/` | Alle SV-Accounts + Akten-Anzahl pro SV |
| `GET` | `/vorschau/<adressnr>` | RA-MICRO-Lookup ohne Speichern (für Formular-Preview) |
| `POST` | `/` | Neuen Account anlegen (Body: `{adressnr}`) |
| `DELETE` | `/<adressnr>` | Account löschen |
| `PATCH` | `/<adressnr>` | Account-Status togglen (`portal_aktiv`) |
| `POST` | `/<adressnr>/einladung` | Einladungs-Zeitstempel setzen (`einladung_gesendet_am = now()`) |
| `GET` | `/<adressnr>/akten` | Akten des SV (JOIN über email-Matching) |
| `PATCH` | `/akten/<akte_az>/portal_aktiv` | `unfallakte.portal_aktiv` togglen |

**Akten-Matching:** Akten werden über `beteiligte.email = sv_portal_accounts.email` gefunden, wobei `beteiligte.rolle = 'sachverstaendiger'`. Einschränkung: nur Akten, wo die E-Mail des SV in `beteiligte` gespeichert ist.

**`POST /` — Ablauf:**
1. RA-MICRO-Lookup mit `adressnr` → holt `name`, `vorname`, `email`
2. Falls kein Treffer oder RA-MICRO inaktiv → 400/503
3. INSERT in `sv_portal_accounts`
4. Gibt neuen Eintrag zurück

**`POST /<adressnr>/einladung` — Scope:**  
Setzt nur `einladung_gesendet_am = datetime('now','localtime')` in SQLite.  
Die eigentliche Einladungs-E-Mail wird **nicht** von diesem Endpoint gesendet — das ist Aufgabe des separaten `sync_connector.py`-Scripts (Portal-Session). Damit bleibt der Endpoint idempotent und nicht von externen Diensten abhängig.

---

## Frontend

### EinstellungenView.jsx

Neuer Tab `"sv_portal"` mit Label `"🔗 SV-Portal"` in der Tab-Leiste (nach „Gutachter", vor „IMAP").

Neuer State-Block für SV-Portal:
```
svListe          []      - Liste der SV-Accounts
svAusgewaehlt    null    - Ausgewählter SV (adressnr)
svAkten          []      - Akten des ausgewählten SV
svLaedt          false
svForm           { adressnr: "", vorschau: null }  - Neu-anlegen-Formular
svFormLaedt      false
svFormSpeichert  false
```

### Neue-SV-Formular-Flow (in linker Spalte, oberhalb der Liste)

1. Input-Feld: RA-MICRO-Adressnummer (Zahl)
2. Button „Laden" → `GET`-Request an RA-MICRO-Lookup-Endpoint → zeigt Vorschau (Name, E-Mail)
3. Button „Speichern" → `POST /einstellungen/sv-portal`
4. Fehlerfall (kein RA-MICRO, Adressnummer unbekannt, E-Mail schon vergeben) → Toast

### Rechte Spalte — Detail

- Name, E-Mail, RA-MICRO-Adressnr
- Status-Badge (Aktiv / Einladung ausstehend / Inaktiv)
- Aktionen: „✉ Einladung senden" (manuell, immer), „Deaktivieren / Aktivieren", „Löschen"
- Akten-Liste: AZ + Kurzbezeichnung + Unfalldatum + Toggle (portal_aktiv)
- Info-Zeile: „SV sieht X von Y Akten im Portal"

### api.js

Neues Objekt `apiSvPortal` mit Methoden:
- `liste()` → `GET /einstellungen/sv-portal`
- `vorschau(adressnr)` → `GET /einstellungen/sv-portal/vorschau/<adressnr>` (RA-MICRO-Lookup)
- `anlegen(adressnr)` → `POST /einstellungen/sv-portal`
- `loeschen(adressnr)` → `DELETE /einstellungen/sv-portal/<adressnr>`
- `toggleAktiv(adressnr, aktiv)` → `PATCH /einstellungen/sv-portal/<adressnr>`
- `einladungSenden(adressnr)` → `POST /einstellungen/sv-portal/<adressnr>/einladung`
- `akten(adressnr)` → `GET /einstellungen/sv-portal/<adressnr>/akten`
- `togglePortalAktiv(akte_az, aktiv)` → `PATCH /einstellungen/sv-portal/akten/<akte_az>/portal_aktiv`

---

## Offene Fragen / Einschränkungen

- **Email-Matching:** SVs in `beteiligte` ohne gespeicherte E-Mail werden nicht als zugehörige Akten erkannt. Kann in einem späteren Schritt durch Ergänzung von `ra_micro_adressnr` in der `beteiligte`-Tabelle verbessert werden.
- **Einladungs-E-Mail:** Wird in dieser Session nicht implementiert. Der Endpoint setzt nur den Zeitstempel. Die eigentliche E-Mail ist Teil der Portal-Session (PORTAL-A1/B1).
- **`portal_aktiv`-Toggle gilt global:** Wenn eine Akte auf `portal_aktiv = 0` gesetzt wird, ist sie für alle Portal-Nutzer dieser Akte unsichtbar — nicht nur für den gerade angezeigten SV.
