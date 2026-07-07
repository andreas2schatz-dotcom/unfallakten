# Konzept: SV-Portal-Zugang via RA-MICRO Adressnummer

**Status:** Konzept — noch nicht implementiert  
**Betroffene Systeme:** Unfallaktensystem (unfallakten.db + sync_connector.py) + Stakeholder-Portal  
**Weiterzugeben an:** Session im Unfallaktensystem-Kontext (mit datamodel.md als Kontext laden)

---

## Ziel

Sachverständige sollen im Stakeholder-Portal ihre eigenen Akten sehen. Die Quelle der Wahrheit ist das Unfallaktensystem — das Portal spiegelt nur, was dort festgelegt wird. Kein doppeltes Pflegen von Zugriffen.

---

## Datenfluss (Gesamtbild)

```
RA-MICRO SQL Server
  └─ Adresstabelle (Adressnr, Name, Vorname, E-Mail, ...)
          │
          │ einmalig beim Anlegen eines SV-Portal-Zugangs
          ▼
  Unfallaktensystem (unfallakten.db)
  ├─ beteiligte (rolle='sachverstaendiger', ra_micro_adressnr, email)
  ├─ unfallakte.portal_aktiv = 1        ← Freigabe-Schalter pro Akte
  └─ sv_portal_accounts                 ← neue Tabelle: welche SVs Portal-Zugang haben
          │
          │ sync_connector.py (erweitert)
          ▼
  Stakeholder-Portal (portal.db)
  ├─ portal_users (SV-Account, ra_micro_adressnr gespeichert)
  └─ akte_zugriff (automatisch aus beteiligte + portal_aktiv)
```

---

## Was im Unfallaktensystem gebaut / geändert werden muss

### 1. Neue Tabelle `sv_portal_accounts`

Speichert, welche SVs (identifiziert per RA-MICRO Adressnummer) einen Portal-Account haben sollen.

```sql
CREATE TABLE sv_portal_accounts (
    adressnr        INTEGER PRIMARY KEY,   -- RA-MICRO Adressnummer
    name            TEXT NOT NULL,         -- aus RA-MICRO gecacht
    vorname         TEXT,
    email           TEXT NOT NULL UNIQUE,  -- Login-Adresse im Portal
    portal_aktiv    INTEGER NOT NULL DEFAULT 1,
    angelegt_am     TEXT NOT NULL DEFAULT (datetime('now')),
    letzter_sync    TEXT
);
```

### 2. Freigabe-Logik (kein neues Flag nötig)

Die Freigabe ergibt sich aus zwei bereits vorhandenen Signalen:
- `unfallakte.portal_aktiv = 1` — Akte ist für das Portal freigegeben
- `beteiligte.rolle = 'sachverstaendiger'` — SV ist dieser Akte zugeordnet

Ein SV sieht im Portal also genau die Akten, bei denen **beide Bedingungen** erfüllt sind und er in `sv_portal_accounts` eingetragen ist.

### 3. Neue Ansicht im Unfallaktensystem

- Liste aller SVs aus `sv_portal_accounts`
- Pro SV: alle zugeordneten Akten (`beteiligte` JOIN `unfallakte WHERE portal_aktiv = 1`)
- Schnellaktion: `portal_aktiv` für eine Akte an-/abschalten

### 4. Adressnummer-Lookup aus RA-MICRO

Beim Anlegen eines neuen SV-Portal-Accounts:
- Admin gibt RA-MICRO Adressnummer ein
- System holt Name, Vorname, E-Mail direkt aus RA-MICRO SQL
- Daten werden in `sv_portal_accounts` gespeichert
- E-Mail wird als Login-Adresse im Portal verwendet

---

## Was sync_connector.py zusätzlich tun muss

### Erweiterung des bestehenden Sync

Beim Sync einer Akte (bestehende Logik):
1. SV in `beteiligte` identifizieren (Adressnummer + E-Mail)
2. Prüfen: ist dieser SV in `sv_portal_accounts` eingetragen?
3. Falls ja → im Portal-Payload `akte_zugriff` automatisch anlegen/aktualisieren
4. Falls nein → überspringen

### Neuer Befehl `--sync-sv-accounts`

Legt Portal-Accounts für alle SVs aus `sv_portal_accounts` an oder aktualisiert sie:

```bash
python scripts/sync_connector.py --sync-sv-accounts
```

Was das Script dabei tut:
1. Alle Einträge aus `sv_portal_accounts WHERE portal_aktiv = 1` lesen
2. Für jeden SV: POST an `/api/admin/sync-sv` im Portal (neuer Endpunkt)
3. Portal legt `portal_users` Eintrag an (falls noch nicht vorhanden) mit `ra_micro_adressnr`
4. Portal schickt Magic-Link-E-Mail an den SV (erstmaliger Zugang)

---

## Was im Stakeholder-Portal gebaut wird (eigene Session)

Diese Punkte sind **nicht Teil der Unfallaktensystem-Session** — sie werden separat implementiert, sobald die Sync-Seite steht:

- `portal_users.ra_micro_adressnr TEXT` Spalte ergänzen
- Neuer API-Endpunkt `/api/admin/sync-sv` (nimmt SV-Profil entgegen, legt `portal_users` an)
- Sync-Handler (`src/lib/sync.ts`): `akte_zugriff` automatisch anlegen wenn SV-Account vorhanden
- Admin-Ansicht: SV-Liste mit ihren freigegebenen Akten (read-only)

---

## Offene Fragen — vor der Implementierung klären

1. **RA-MICRO Adresstabelle**: Wie heißt die Tabelle und welche Felder enthält sie?  
   (Vermutlich `_tblAdressen` o.ä. — Name, Vorname, E-Mail, Adressnummer)

2. **Adressnummer in `beteiligte`**: Ist die RA-MICRO Adressnummer bereits in der  
   `beteiligte`-Tabelle des Unfallaktensystems gespeichert, oder muss das ergänzt werden?

3. **Neues Script oder Erweiterung**: Soll `--sync-sv-accounts` ins bestehende  
   `sync_connector.py` oder ein eigenes `sv_account_sync.py`?

4. **Erstmaliger Login**: Soll der SV beim ersten Sync automatisch eine Einladungs-E-Mail  
   bekommen, oder wird der Zugang manuell freigeschaltet?
