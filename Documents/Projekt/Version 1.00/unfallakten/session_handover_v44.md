# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v44 – 4. April 2026
> Erledigt diese Session: PRD-26 Teil 2 komplett + Fragment-Bugfixes (6 Stellen)
> Nächste Session: Klage-Wizard Step-für-Step optimieren + ggf. PRD-22c/25c/25d/Bußgeld

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

3. **Stimme nicht einfach zu.** Verbesserungsvorschläge und kritische Fragen stellen.

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **33** |
| Frontend | **35 JSX-Dateien** + api.js |
| Backend | Flask/Python 3.9, SQLite PK `az TEXT` |
| RA-Micro | SQL Server (read-only), WDM + E-Akte aktiv |
| Wizard-Map | `handover/klage_wizard_map.md` |
| PRD-Dokument | `handover/PRD-26_Klage_Wizard_Umbau.md` |

---

## Diese Session erledigt

### PRD-26 Teil 2 – alle offenen Punkte geschlossen

| ID | Was | Commit |
|---|---|---|
| P-3 | StepAktLeg useEffect überschreibt manuellen Text nicht mehr (prevAutoRef) | 7edc055 |
| P-4 | Button „Parteien bearbeiten →" in Step 2 + Scroll-Anker `#karte-parteien` | 7edc055 |
| DEP | Ein-Klick-Buttons grau + opacity + Tooltip „Veraltet – bitte Wizard verwenden" | 7edc055 |
| BE-1 | `antraege_override` → direkt in DOCX (nummerierte Zeilen, hängender Einzug) | 7edc055 |
| BE-2 | `mit_feststellung_sg/sach` → Feststellungsanträge im Fallback-Pfad | 7edc055 |
| BE-3 | `rvg_ausserg/rvg_ausserg_override` → RVG-Antrag auf außergerichtl. SW | 7edc055 |

### Fragment-Bugfixes (pre-existing, sichtbar nach Restart)

| Datei | Funktion | Commit |
|---|---|---|
| `AkteDetailView.jsx` | `AkteDetailView` | 40789b5 |
| `RegulierungSection.jsx` | `AbrechnungFormular`, `ManuelleAbrechnungFormular` | 5f61e92 |
| `UebersichtSection.jsx` | `GegnerVersicherungMini`(?), `ChronikKachel` | 5f61e92 |

**Ursache:** `{toast && <Toast/>}` stand nach `</div>` außerhalb des JSX-Root ohne Fragment-Wrapper. Babel-Fehler trat erst beim sauberen Neustart des Vite-Compilers auf.

---

## Nächste Session: Wizard Step-für-Step optimieren

### ➡️ PROMPT FÜR NEUE SESSION:

```
Lies zuerst session_handover_v44.md und handover/klage_wizard_map.md.

PRD-26 ist vollständig abgeschlossen (Grundgerüst steht).
Wir optimieren jetzt Step für Step den Klage-Wizard.

Starte mit Step 1 (Gericht) und zeige mir was konkret verbessert werden kann.
Dann gemeinsam durcharbeiten: Benutzerführung, Fehlerbehandlung, Texte, Layout.

Danach: PRD-22c Session 5, PRD-25c, PRD-25d, Bußgeld-Deployment.
```

---

## Wizard-Optimierung – Übersicht offener Punkte

> Detaillierte Map: `handover/klage_wizard_map.md`

| Step | Label | Optimierungspotenzial | Priorität |
|---|---|---|---|
| 1 | Gericht | Gericht zurück in Akte speichern (derzeit nur Session-State) | Mittel |
| 2 | Rubrum | Vertreter-Warnung klickbar machen (direkt zu Vertreter-Formular) | Niedrig |
| 3 | Aktiv. | Tooltip zu § 1006 BGB, „Datum unbekannt"-Option | Niedrig |
| 4 | Unfall | Diff-Hervorhebung (welche Wörter ersetzt), Zurücksetzen-Button | Niedrig |
| 5 | Schaden | Regulierungsstand neben jeder Position (gezahlt / gefordert) | Mittel |
| 6 | Anträge | Platzhalter-Zeile visuell abheben; Feststellungsantrag-Hinweis | Niedrig |
| 7 | Würdigung | UX EinwandePanel verfeinern; HQ als Schieberegler | Mittel |
| 8 | Verzug | Klarstellen: dieser RVG = gerichtl. SW (nicht außergerichtl.) | Niedrig |
| 9 | Gebühren | Vorher/Nachher des Platzhalter-Ersatzes zeigen | Niedrig |
| 10 | Generieren | Beide RVG zeigen (gerichtl. + außergerichtl.); Text-Preview | Niedrig |
| Datei | – | Header-Kommentar aktualisieren: „7-Step" → „10-Step" | Trivial |

---

## Weitere offene Feature-Tasks (nach Wizard-Optimierung)

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
