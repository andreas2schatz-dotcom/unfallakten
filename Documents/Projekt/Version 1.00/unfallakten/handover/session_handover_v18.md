# Session-Übergabe – Kanzlei Koch, Schatz & Kollegen
# Unfallakten-Verwaltungssystem
> Stand: Session v46 – 6. April 2026

---

## Aktueller Systemstand

| Komponente | Details |
|---|---|
| DB-Schema-Version | **34** |
| Frontend | React + Vite, aufgeteilt in Section-Dateien (kein Monolith mehr) |
| Backend | Flask/Python 3.9, SQLite PK az TEXT |
| RA-Micro | Optional (RAMICRO_AKTIV=true) |
| E-Akte | EAKTE_BASE_PATH konfiguriert → Auto-Import aktiv |

---

## Erledigte Features v46

| Feature | Commit | Status |
|---|---|---|
| Auto-Parser Routing-Whitelist + Debug-Dialog | `648cf3b` | ✅ |
| `domain`, `rubrik`, `einf_datum`, `routing_basis` in Kandidaten-Response | `648cf3b` | ✅ |
| `KandidatenDebugDialog`: Stats-Header + Metadaten-Zeile pro Kandidat | `648cf3b` | ✅ |
| Dokument-Kacheln nach Auto-Parser sofort aktualisieren (`auto_importiert` + `ladeDokumenteListe`) | `d7bc02c` | ✅ |
| Vorschau-Button (👁) für lokale PDF-Kacheln | `d37ab75` | ✅ |
| SHA-256 Hash-Duplikat-Check vor `registriere_dokument` | `c8c3eed` | ✅ |
| Konfidenz-Schwelle >= 0.85 für E-Akte Auto-Import | `c8c3eed` | ✅ |
| `eakte_service.py`: Limit 200→500 | `c8c3eed` | ✅ |
| Gutachten-Parser: Wertminderung 3-Pass-Fix (false positive 0.0 → korrekt 150.0) | `5a274e4` | ✅ |
| SV-Rechnung Auto-Import via `hat_sv_rechnung_pos` + `eakte_cache[nr]` | `5a274e4` | ✅ |

---

## Offene Bugs / Bekannte Probleme

| # | Problem | Priorität |
|---|---|---|
| – | Klagegenerator noch nicht vollständig getestet (13 Blöcke) | 🔴 |
| – | PRD-22c Session 4–5 (Fragebogen-Backend-Tests) ausstehend | 🟡 |
| – | PRD-25c Mandantenkommunikation nicht implementiert | 🟡 |
| – | PRD-25d STA End-to-End-Test ausstehend | 🟡 |
| – | Bußgeld-Deployment ausstehend | 🟡 |

---

## To-Do – Nächste Session

### 🔴 Priorität 1: Klagegenerator – Abschlusstest (je Block)

| Block | Was prüfen | Status |
|---|---|---|
| **Rubrum** | Kläger (Name, Anrede, Anschrift), alle Beklagten (GHPV + ggf. Halter/Fahrer), Vertreter mit Funktion, Gericht | ⬜ |
| **Einleitung** | AZ, Unfalldatum, Unfallort (SQLite > WDM), Kennzeichen Gegner, Schadennummer | ⬜ |
| **Tatbestand** | Unfallschilderung (SQLite > varSCHILD), Zeugen (varZ1-3 + Adressen), Fahrer Mandant/Gegner, KFZ-Daten aus Gutachten | ⬜ |
| **Ermittlungsakte** | AZ Ermittlungsakte (varEA-AZ), Behörde (varPOLIZEI), Ort (varEA-ADRESS) | ⬜ |
| **Schadentabelle** | Korrekte Positionen je Abrechnungsart (fiktiv/konkret/Totalschaden), Beträge, Unkostenpauschale-Default 30€, WDM-Extras | ⬜ |
| **Haftungsquote** | Quoten-Block erscheint bei HQ < 100%, korrekte Berechnung | ⬜ |
| **Haftungsbegründung** | varANSP1 oder SQLite `haftungsbegruendung` | ⬜ |
| **Schmerzensgeld** | Block erscheint wenn angehakt (auch ohne Mindestbetrag), Mindestbetrag optional | ⬜ |
| **Zinsen** | Verzugsdatum (varSCHREIBENVERZUG), Zinsbeginn-Wahl, korrekter Zinssatz 5PP | ⬜ |
| **Klageanträge** | Hauptantrag korrekt je Abrechnungsart, Leerzeilen, Versäumnisurteil-Antrag | ⬜ |
| **Rechtliche Würdigung** | Platzhalter-Text vorhanden; D4: Kürzungsargumente auto aus kuerzungsarten | ⬜ |
| **RVG** | Streitwert = Summe gemerkter Positionen, §13-Tabelle korrekt, Mehrwertsteuer, Override | ⬜ |
| **Verweisbetrieb** | Textbaustein erscheint wenn verweisFlag gesetzt, Entfernungsangabe korrekt | ⬜ |

### 🟡 Priorität 2: PRD-27 ReguWizard
Geführter Wizard: Stellungnahme auf Abrechnungsschreiben. PRD: `handover/PRD-27_ReguWizard.md`.

### 🟡 Priorität 3: PRD-25c Mandantenkommunikation
### 🟡 Priorität 4: PRD-25d STA End-to-End-Test
### 🟡 Priorität 5: Bußgeld-Deployment

---

## Kritische Architektur-Notizen

- `unfallakte` PK = `az TEXT` (kein Integer seit Migration 5) → `WHERE az=?` überall
- Nach `hole_akte_by_id(akte_id)` IMMER `az = akte.aktenzeichen` setzen – nie rohen URL-Parameter für DB nutzen
- Beteiligte: IMMER `hole_beteiligte_by_akte(az)` nutzen, nie `SELECT * FROM beteiligte`
- `Beteiligter.from_row()` filtert mit `dataclasses.fields()` → neue Felder MÜSSEN in Dataclass eingetragen werden
- `POSITION_KEYS` in `abrechnungsschreiben.py` UND `_POSITION_KEYS_ERWEITERT` in Route – neue Keys immer an BEIDEN Stellen
- `PRAGMA foreign_keys = OFF` vor INSERT in `abrechnungsschreiben` (FK-Mismatch auf `dokumente`)
- WDM-Variablen: `varSCHREIBENVERZUG` bevorzugen vor `varVERZUGAB`; `varQUOTEG` hat `" EUR"` Suffix → strippen
- RA-MICRO: NIEMALS schreiben. Nur SELECT auf `ra` und `raEloakte`. Eigene Daten → SQLite.
- `pdf_hash` in `dokumente` (seit Migration 24): SHA-256, vor `registriere_dokument` auf Duplikat prüfen

---

## E-Akte Auto-Import – Architektur (v46)

```
E-Akte Kandidaten-Aufruf (GET /belege/kandidaten)
  └─ hole_eakte_dokumente() → Metadaten (max. 500)
       └─ _klassifiziere_eakte_dok() → treffer_liste + konfidenz
            ├─ hat_gutachten_pos (konfidenz >= 0.85): rep_gutachten_netto / wbw / rw / wm
            ├─ hat_sv_rechnung_pos (konfidenz >= 0.85): sv_kosten / sv_kosten_netto
            └─ wenn EAKTE_BASE_PATH konfiguriert:
                 ├─ SHA-256 Hash → Duplikat? → skip
                 ├─ registriere_dokument()
                 ├─ dispatch_dokument()
                 ├─ wenn hat_gutachten_pos:
                 │    klasse != "gutachten" → korrigiere_klassifikation()
                 │    gut_betraege befüllen
                 └─ wenn hat_sv_rechnung_pos + klasse in (rechnung/sv_rechnung):
                      eakte_cache[nr] aktualisieren (in-memory für selben Aufruf)
```

**Konfidenz-Schwellen:**
- `domain_match_versicherer`: ~0.92 → Auto-Import ✅
- `domain_match_sv_buero`: ~0.88 → Auto-Import ✅
- `domain_match_sv_unklar`: ~0.72 → Auto-Import ❌ (unter Schwelle 0.85)
- E-Mails/Korrespondenz bleiben unter 0.85 → kein Auto-Import

---

## Wichtige Tabellen / Felder

```sql
-- dokumente (Migration 24)
pdf_hash TEXT   -- SHA-256 hex, für Duplikat-Check

-- abrechnungsschreiben
quelle TEXT  -- 'pdf' | 'manuell' | 'wdm'
gesamt_kuerzung REAL
wdm_importiert INTEGER
referenz_nr TEXT

-- beteiligte
vertreter_name TEXT    -- MUSS in Beteiligter-Dataclass stehen!
vertreter_funktion TEXT
```

---

## Geänderte Dateien v46

| Datei | Änderung |
|---|---|
| `backend/parsers/gutachten_parser.py` | Wertminderung 3-Pass-Fix (Reihenfolge: Betrag → Fallback → kein/0) |
| `backend/routers/belege_routes.py` | hat_sv_rechnung_pos, SHA-256 Duplikat-Check, Konfidenz-Schwelle 0.85, routing_basis in Kandidaten |
| `backend/routers/pdf_parse_routes.py` | routing_info in parse-Response, Fallback-Logging |
| `backend/ramicro/eakte_service.py` | Limit 200→500 |
| `frontend/src/sections/DokumenteSection.jsx` | ladeDokumenteListe(), auto_importiert-Refresh, 👁-Button für lokale PDFs, KandidatenDebugDialog Stats |

---

## Docker-Befehle

```bash
# Volume-gemountete Dateien: kein docker cp nötig für belege_routes.py, gutachten_parser.py etc.
# Nur nach Python-Änderungen: docker restart unfallakten-backend-dev

# Frontend (JSX): live via Vite-HMR, kein cp nötig wenn gemountet
# Falls nicht gemountet:
docker cp frontend/src/sections/DokumenteSection.jsx unfallakten-frontend-dev:/app/src/sections/DokumenteSection.jsx

# Backend-Restart
docker restart unfallakten-backend-dev

# Logs
docker logs unfallakten-backend-dev --tail 50

# DB direkt
docker exec unfallakten-backend-dev sqlite3 /app/data/unfallakten.db "SELECT schema_version FROM schema_version;"
```
