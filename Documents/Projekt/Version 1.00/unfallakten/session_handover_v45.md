# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v45 – 4. April 2026
> Erledigt diese Session: Klage-Wizard Steps 1–3 optimiert (Layout, Gericht-Persistenz, Sachverhalt-Block)
> Nächste Session: Step 4 (Unfallhergang) und folgende, dann PRD-22c/25c/25d/Bußgeld

---

## ⚠️ ERINNERUNG: WSL-Mount vor jedem Docker-Start!

```powershell
wsl --user root
mount -t cifs //192.168.10.100/ServerSQL/ra /mnt/eakte -o username=admin,password=passwort,ro
exit
docker compose up -d
```

---

## ⛔ ABSOLUTE REGELN

1. **Kein Schreibzugriff auf raEloakte** – NUR SELECT. Alle eigenen Daten in lokaler SQLite.

2. **Vor jedem Deploy: Code-Review gegen Learnings und bekannte Fehler:**
   - Routen-URLs: api.js ↔ Flask-Blueprint (`loesche` nicht `loeschen`!)
   - `_dok_dict()`: Beide Funktionen (upload_service + akten_routes) bei neuen Spalten
   - `d.typ` Fallback: `d.dokumentenklasse === "x" || d.typ === "x"`
   - React-Hook-Imports, Kommentar-Balance, **Python 3.9** (keine Union-Types `X | Y`, kein Walrus `:=`)
   - Reducer-Actions existieren? `confirm()` vor Löschaktionen
   - **B-08:** Bei durchgereichten Dicts IMMER prüfen ob alle Felder in JEDEM Zwischenschritt weitergegeben werden
   - **B-09:** Wenn Schadentabelle und Gegenstandswert unterschiedliche Quellen → beide prüfen
   - **PRD-24:** Override-Dict vollständig durchreichen: Wizard → API → klage_service
   - **WDM Key-Mismatch:** `sonstiges_wdm_X` ≠ `extra_wdm_ssX` → immer remap prüfen bei posMap-Aufbau
   - **Neue Reducer-Actions** immer in `reducer.js` eintragen – sonst silenter Datenverlust (→ CR-F02)
   - **Neue fetch()-Aufrufe** immer mit `Authorization: Bearer` Header, nie `credentials:'include'` (→ CR-F03)
   - **JSX Root-Knoten:** Toast/Modal nach `</div>` braucht Fragment `<>...</>` – sonst Babel-Fehler beim Restart
   - **React Race Condition:** `setState` ist async → setState + navigate NIEMALS sequenziell. Stattdessen combined callback in Parent (siehe gerichtBestaetigenUndWeiter)

3. **Stimme nicht einfach zu.** Verbesserungsvorschläge und kritische Fragen stellen.

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **34** (`ist_halter` auf beteiligte) |
| Frontend | **35 JSX-Dateien** + api.js |
| Backend | Flask/Python 3.9, SQLite PK `az TEXT` |
| RA-Micro | SQL Server (read-only), WDM + E-Akte aktiv |
| Wizard-Map | `handover/klage_wizard_map.md` |
| PRD-Dokument | `handover/PRD-26_Klage_Wizard_Umbau.md` |

---

## Diese Session erledigt

### Step 1 (Gericht) – vollständig optimiert

| Was | Details | Commit |
|---|---|---|
| Gericht-Persistenz | PUT `/akten/<az>/klage/gericht` → speichert als `rolle='gericht'` in beteiligte; wird beim nächsten Wizard-Öffnen auto-bestätigt | a2aef7c |
| Bestätigen→Weiter | `gerichtBestaetigenUndWeiter` in KlageSection (race-condition-sicher: API + setState + navigate in einem Callback) | a2aef7c |
| Layout | Modal `height: 92vh` (fixed, alle Steps gleich hoch), Fortschrittsbalken 32px Bubbles, Header 1.25rem | a2aef7c |

### Step 2 (Rubrum) – optimiert

| Was | Details |
|---|---|
| Vertreter-Warnung klickbar | Button → `onClose()` + `scrollTo('#karte-parteien')` |
| Schadennummer im Word | `schaden_suffix` im HPV-Block von klage_service.py |

### Step 3 (AktLeg → Sachverhalt) – komplett umgebaut

**Kernidee:** Step 3 zeigt jetzt einen kombinierten, editierbaren Sachverhalt-Block aus Kläger + Beklagte + Aktivlegitimation. Dieser geht als `sachverhalt_override` ans Backend und ersetzt **beide** Platzhalter `{{EINLEITUNG}}` und `{{AKTIVLEGITIMATION}}` im Word-Dokument.

| Was | Details |
|---|---|
| `buildSachverhaltText()` | Neue JS-Funktion: Kläger-Satz (mit Vorsteuer-Variante) + Beklagte-Block (Versicherungen/Fahrer/Halter, Klammern nur bei mehreren) + AktLeg-Satz + optionaler Auslandsunfall-Text |
| Flektierung | Halter/Halterin (aus `beteiligte.anrede`), Fahrer/Fahrerin (aus `beteiligte.anrede`), Kläger/Klägerin (aus Mandant-Anrede) |
| `ist_halter` | DB-Migration v34, PATCH beteiligte (erlaubte-Set), Halter-Checkbox im Klage-Tab UI |
| `sachverhalt_override` | Neuer Backend-Parameter: ersetzt `{{EINLEITUNG}}` + setzt `aktivleg_xml = ""`; Fallback auf altes Verhalten wenn nicht gesetzt |
| `_sachverhalt_override_xml()` | Neue Funktion in klage_service.py: wandelt Freitext (Absätze per `\n\n`) in OOXML-Absätze |
| Article-Fix | `get_aktivlegitimation_text`: `kl_nom = "Der Kläger"` statt `kl_einf = "Kläger"` → kein "Kläger ist Eigentümer" mehr |
| Auslandsunfall-Stub | Checkbox + EuGH-Standardtext: "Wir machen auf die Entscheidung des EuGH vom 13.12.2007 – Az. C 463/06 – und die Vorlage des BGH im Verfahren vom 26.9.2006 zu VI ZR 200/05 aufmerksam..." |
| prevAutoRef | Manuell bearbeiteter Text wird nicht überschrieben wenn Radio-Buttons geändert werden |

**Commits:** a2aef7c (Hauptimplementierung), 9eb79d4 (Auslandsunfall-Standardtext)

---

## State-Übersicht (in KlageSection.jsx) – aktuell

```
Wizard-States (PRD-24b + PRD-26 + Session v45):
  wizardOffen, wizardStep, wizardMaxStep
  gericht, gerichtSuche, gerichtTreffer, gerichtLaedt, gerichtBestaetigt
  aktLegTyp, aktLegFreigabe, aktLegDatum
  wizardSachverhaltText       ← NEU v45 (ersetzt wizardAktLegText)
  auslandsunfall              ← NEU v45 (bool)
  wizardUnfallText
  wizardPos (=positionen), wizardMitSG, wizardSGMind
  wizardHq, wizardHb, wizardRwText
  wizardVerzugText
  wizardMitFestSg, wizardMitFestSach
  wizardAntraegeText
  wizardRvgAussergData, wizardRvgAussergOv, wizardGebuehrenText
```

**KlageWizard-Props (neu in v45):**
```
sachverhaltText, onSachverhaltText
auslandsunfall, onAuslandsunfall
fahrGegnerName           ← WDM varG-FAHRER aus unfalldetails
mandantVorsteuer         ← vorsteuerabzugsberechtigt (bool)
unfallort                ← aus daten.unfallort
```

---

## Backend – neue/geänderte Endpunkte

```
PUT /akten/<az>/klage/gericht
  Body: { name, strasse, plz, ort, rolle:"gericht" }
  Löscht vorhandenen gericht-Eintrag, fügt neuen ein

Parameter generiere_klage (neu):
  sachverhalt_override  → str, ersetzt {{EINLEITUNG}} + {{AKTIVLEGITIMATION}}
  (alt: aktivlegitimation_text_override → weiterhin unterstützt als Fallback)
```

---

## ➡️ PROMPT FÜR NEUE SESSION

```
Lies zuerst session_handover_v45.md und handover/klage_wizard_map.md.

Wir haben in Session v45 die Wizard-Steps 1–3 optimiert (Gericht-Persistenz,
Sachverhalt-Einleitungssatz mit Beklagten-Block, Article-Fix, Auslandsunfall).

Jetzt weiter mit Step 4 (Unfallhergang) – was können wir dort verbessern?
Danach Step 5–10, dann PRD-22c/25c/25d/Bußgeld.
```

---

## Nächste offene Schritte (Reihenfolge)

| Priorität | Was |
|---|---|
| **Jetzt** | Wizard Step 4–10 optimieren (Unfallhergang, Schaden, Anträge, RW, Verzug, Gebühren, Zusammenfassung) |
| Danach | **PRD-22c Sess. 5** – Tests Fragebogen-Backend |
| Danach | **PRD-25c** – Mandantenkommunikation |
| Danach | **PRD-25d** – Intelligente STA End-to-End-Test |
| Danach | **Bußgeld** – Deployment (bussgeld@ Strato + .env) |
| Später | **ReguWizard** – Analog-Wizard für Antwort auf Abrechnungsschreiben |
| Später | **Auto-Parser-Optimierung** |

---

## Docker-Befehle

```powershell
# ⚠️ WSL-Mount (JEDES MAL vor Docker-Start!)
wsl --user root
mount -t cifs //192.168.10.100/ServerSQL/ra /mnt/eakte -o username=admin,password=passwort,ro
exit

docker compose up -d

# Schema prüfen (soll 34 zeigen)
docker exec unfallakten-backend-dev python3 -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print('Schema:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])"

# Deploy Frontend
docker cp frontend/src/sections/KlageWizard.jsx   unfallakten-frontend-dev:/app/src/sections/KlageWizard.jsx
docker cp frontend/src/sections/KlageSection.jsx  unfallakten-frontend-dev:/app/src/sections/KlageSection.jsx
docker cp frontend/src/api.js                     unfallakten-frontend-dev:/app/src/api.js

# Deploy Backend
docker cp backend/word/klage_service.py           unfallakten-backend-dev:/app/backend/word/klage_service.py
docker cp backend/routers/klage_routes.py         unfallakten-backend-dev:/app/backend/routers/klage_routes.py
docker cp backend/routers/beteiligte_routes.py    unfallakten-backend-dev:/app/backend/routers/beteiligte_routes.py
docker cp backend/db/schema_manager.py            unfallakten-backend-dev:/app/backend/db/schema_manager.py
docker restart unfallakten-backend-dev
```
