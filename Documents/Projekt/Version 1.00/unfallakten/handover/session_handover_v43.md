# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v43 – 4. April 2026
> Erledigt diese Session: PRD-26 Teil 1 – Klage-Wizard Umbau (10 Steps, StepGericht, StepAntraege, StepGebuehren) + Kürzungstext-Generator
> Nächste Session: PRD-26 Teil 2 – klage_service.py + Restfixes P-3/P-4 + Deprecated-Markierung

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

3. **Stimme nicht einfach zu.** Verbesserungsvorschläge und kritische Fragen stellen.

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **33** |
| Frontend | **35 JSX-Dateien** + api.js |
| Backend | Flask/Python 3.9, SQLite PK `az TEXT` |
| RA-Micro | SQL Server (read-only), WDM + E-Akte aktiv |
| PRD-Dokument | `handover/PRD-26_Klage_Wizard_Umbau.md` |

---

## Diese Session erledigt

### Kürzungstext-Generator (EinwandePanel)

**`frontend/src/sections/KlageWizard.jsx`**

- Nummerierte Überschriften `**a) Bezeichnung**` (→ Fett im Word via klage_service)
- 5 rotierende Einleitungssätze (Varianten 0–4, index-basiert)
- Letzter Satz: „Schließlich kürzt die Beklagte…"
- Kürzungsbetrag je Position aus `abrechnungen.positionen` berechnet
- Schlusssatz mit Gesamtsumme + `(zu 1)` bei mehreren Beklagten
- `beklagte` prop jetzt bis EinwandePanel durchgereicht

**`backend/word/klage_service.py`**

- `**...**`-Zeilen in `rw_text_override` → `_p(fett=True)`, Marker entfernt

### PRD-26 Teil 1 – Klage-Wizard Umbau

**`frontend/src/sections/KlageSection.jsx`**
- 10 neue Wizard-States: `wizardHq`, `wizardHb`, `wizardMaxStep`, `wizardGerichtBest`,
  `wizardMitFestSg`, `wizardMitFestSach`, `wizardAntraegeText`,
  `wizardRvgAussergData`, `wizardRvgAussergOv`, `wizardGebuehrenText`
- `swAusserg` = Summe ALLER Schadenpositionen (außergerichtl. Streitwert)
- `oeffneWizard()` initialisiert alle neuen States
- `wizardGenerieren()` übergibt: `mit_feststellung_sg`, `mit_feststellung_sach`,
  `antraege_override`, `rvg_ausserg`, `rvg_ausserg_override`
- useEffect für Step-9-RVG: `rvgBerechnen(akteId, {streitwert: swAusserg})` bei Betreten Step 9
- Alle neuen Props an `KlageWizard` durchgereicht

**`frontend/src/sections/KlageWizard.jsx`**
- STEPS-Array: 10 Steps (Gericht, Rubrum, Aktiv., Unfall, Schaden, Anträge, Würdigung, Verzug, Gebühren, Generieren)
- **P-1 erledigt:** `Fortschrittsbalken` klickbar für Steps ≤ `wizardMaxStep`
- **P-2 erledigt:** `hq`/`hb` nicht mehr lokal in `StepRw`, kommen als Props `wizardHq`/`wizardHb`
- `kannWeiter()`: Step 1 gesperrt bis `gerichtBestaetigt`, Step 5 gesperrt ohne Positionen
- `weiter()` aktualisiert `wizardMaxStep`
- **Neu: `StepGericht`** – Suchfeld + Treffer-Dropdown + Bestätigen-Button + Vorschlag-Badge
- **Neu: `StepAntraege`** – Checkboxen, `baueAntraegeText()`, Feststellungsanträge,
  RVG-Platzhalter, DokumentCard
- **Neu: `StepGebuehren`** – RVG-Tabelle (auf `swAusserg`), Override, Platzhalter-Ersatz in antraegeText
- Step-Nummern neu: Rubrum=2, Aktivleg.=3, Unfall=4, Schaden=5, Würdigung=7, Verzug=8, Generieren=10

---

## Nächste Session: PRD-26 Teil 2

### ➡️ PROMPT FÜR NEUE SESSION:

```
Lies zuerst session_handover_v43.md, dann handover/PRD-26_Klage_Wizard_Umbau.md.

PRD-26 Teil 1 ist abgeschlossen (Wizard-Struktur, neue Steps, Frontend-State).
Wir machen weiter mit PRD-26 Teil 2:

1. P-3: StepAktLeg useEffect-Fix (überschreibt keine manuell editierten Texte)
2. P-4: Button „Parteien bearbeiten" in Step 2 (Rubrum), der Wizard schließt + scrollt zu Parteien
3. klage_service.py: antraege_override verarbeiten, Feststellungsanträge (mit_feststellung_sg/sach),
   rvg_ausserg für Gebühren-Antrag auf außergerichtlichem Streitwert
4. Deprecated-Markierung der Ein-Klick-Buttons in KlageSection.jsx
5. Danach: restliche offene Feature-Tasks (PRD-22c Session 5, PRD-25c, PRD-25d, Bußgeld-Deployment)
```

---

## Offene Punkte PRD-26

| ID | Problem | Datei | Status |
|---|---|---|---|
| P-3 | `useEffect` StepAktLeg überschreibt manuellen Text | `KlageWizard.jsx` | Offen |
| P-4 | Rubrum-Korrekturen erfordern Wizard-Neustart | `KlageWizard.jsx` + `KlageSection.jsx` | Offen |
| BE-1 | `klage_service.py`: `antraege_override` statt auto-Anträge | `klage_service.py` | Offen |
| BE-2 | `klage_service.py`: `mit_feststellung_sg/sach` → Feststellungsanträge | `klage_service.py` | Offen |
| BE-3 | `klage_service.py`: `rvg_ausserg` für Gebühren-Antrag | `klage_service.py` | Offen |
| DEP | Ein-Klick-Buttons visuell als deprecated markieren | `KlageSection.jsx` | Offen |

---

## Technische Details PRD-26 für Backend

### klage_service.py – neue cfg-Felder

```python
# In generiere_klageschrift(cfg):
antraege_override     = cfg.get("antraege_override")       # str, kompletter Antrags-Block
mit_feststellung_sg   = cfg.get("mit_feststellung_sg", False)
mit_feststellung_sach = cfg.get("mit_feststellung_sach", False)
rvg_ausserg           = cfg.get("rvg_ausserg")             # dict aus berechne_rvg(swAusserg)
rvg_ausserg_override  = cfg.get("rvg_ausserg_override")    # float, optional

# Logik:
# 1. Wenn antraege_override vorhanden → direkt als Antrags-Block verwenden
#    (inkl. RVG-Antrag und Kostentragung, exakt wie im Wizard editiert)
# 2. Wenn nicht → bestehende Auto-Generierung (Fallback, rückwärtskompatibel)
#    + mit_feststellung_sg/sach → Feststellungsanträge einbauen
#    + rvg_ausserg → RVG-Antrag auf außergerichtl. Streitwert statt klagebetrag
```

### Feststellungsantrag-Formulierungen

**Personenschaden** (`mit_feststellung_sg=True`):
> Es wird festgestellt, dass die Beklagte verpflichtet ist, dem Kläger / der Klägerin
> sämtliche künftigen materiellen und immateriellen Schäden zu ersetzen, die aus dem
> Unfallereignis vom [Unfalldatum] noch entstehen werden, soweit Ansprüche nicht auf
> Sozialversicherungsträger oder sonstige Dritte übergegangen sind oder noch übergehen werden.

**Sachschaden** (`mit_feststellung_sach=True`):
> Es wird festgestellt, dass die Beklagte verpflichtet ist, dem Kläger / der Klägerin
> sämtliche weiteren materiellen Schäden zu ersetzen, die aus dem Unfallereignis vom
> [Unfalldatum] noch entstehen werden.

### Antrags-Reihenfolge (Fallback ohne antraege_override)

1. Hauptantrag Sachschaden + Zinsen
2. Schmerzensgeld (wenn `mit_sg`)
3. Feststellungsantrag Personenschaden (wenn `mit_feststellung_sg`)
4. Feststellungsantrag Sachschaden (wenn `mit_feststellung_sach`)
5. RVG-Antrag (auf `rvg_ausserg.gesamt` wenn vorhanden, sonst `rvg.gesamt`)
6. Kostentragung

---

## Weitere offene Feature-Tasks (nach PRD-26)

| Priorität | PRD | Beschreibung |
|---|---|---|
| Danach | **PRD-22c Sess. 5** | Tests Fragebogen-Backend |
| Danach | **PRD-25c** | Mandantenkommunikation |
| Danach | **PRD-25d** | Intelligente STA – End-to-End-Test |
| Danach | **Bußgeld** | Deployment (bussgeld@ Strato + .env) |
| Später | **ReguWizard** | Analog-Wizard für Antwort auf Abrechnungsschreiben |

---

## Docker-Befehle

```powershell
# ⚠️ WSL-Mount (JEDES MAL vor Docker-Start!)
wsl --user root
mount -t cifs //192.168.10.100/ServerSQL/ra /mnt/eakte -o username=admin,password=passwort,ro
exit

docker compose up -d

# Schema prüfen (soll 33 zeigen)
docker exec unfallakten-backend-dev python3 -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print('Schema:', c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0])"

# Deploy Frontend
docker cp frontend/src/sections/KlageWizard.jsx   unfallakten-frontend-dev:/app/src/sections/KlageWizard.jsx
docker cp frontend/src/sections/KlageSection.jsx  unfallakten-frontend-dev:/app/src/sections/KlageSection.jsx

# Deploy Backend
docker cp backend/word/klage_service.py  unfallakten-backend-dev:/app/backend/word/klage_service.py
docker restart unfallakten-backend-dev
```
