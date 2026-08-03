# Nächste Session — Aktenanlage-Abnahme fortsetzen + Prefill-Bug fixen

**Stand:** 2026-08-03 · **Branch:** `dashboard-hell` (Dev-Container laufen darauf)

---

## 0. Eigentliches Ziel (NICHT vergessen)

**Merge-Gate abschließen:** `aktenanlage` → `main`, dann `dashboard-hell` → `main`.
Beide Branches sind fertig implementiert und liegen **linear** vor `main` (Topologie `main → aktenanlage (27) → dashboard-hell (12)`, Fast-Forward-fähig, geprüft 2026-08-03). Der Merge ist bewusst **gated** auf die **manuelle Abnahme der Aktenanlage am echten RA-MICRO** (das Feature erzeugt **reale Akten** via OMA-XML-Export). Diese Abnahme läuft gerade — sie ist der *Weg* zum Merge, nicht das Endziel. Nach bestandener Abnahme: mergen (FF), dann uncommittete Planungsarbeit sichern (§4).

## 1. ✅ ERLEDIGT: Blocker-Bug Prefill (gefixt 2026-08-03, Commit 2cc29de0)

**Root Cause war KEIN Frontend-Bug.** Der Mandant wird per `baueVorbefuellung` nur aus `felder.auftraggeber_*` (Gutachten-Parse) gefüllt. Diese Felder haben (a) keine Regex-Regel — nur der LLM extrahiert sie (funktioniert zuverlässig, Seite 1 ist immer im N-06-Auszug), und (b) kamen erst am 2026-07-30 ins Schema (Commit 2cc98de4). **Alle Bestands-Queue-Dokumente wurden davor geparst → parse_json ohne Auftraggeber → leerer Mandant** = was RA Schatz sah (stale data). Frische Importe funktionieren ohne Reparse; Bestandsdocs brauchen einen „neu parsen"-Lauf.

Zusätzlich echter Code-Fix: `normalisiereAnrede()` in `AktenanlageDialog.jsx` — LLM liefert „Herrn"/„Frau", altes `.toLowerCase()` ergab „herrn" (kein Match zu Select-Optionen/`oma_xml.py`-Keys `herr`/`frau`/`firma`) → leere Anrede in der OMA-XML (abnahmerelevant Punkt 3). Jetzt gemappt.

**Verifiziert:** `AktenanlageDialog.test.jsx` 11/11 + `ReviewQueueView.aktenanlage.test.jsx` 13/13 grün; Playwright-E2E am Dev-System 6/6 (Mandant komplett vorbefüllt inkl. Anrede=Herr, an reparstem id=196 „Tatalovic"). Frontend-Container 2026-08-03 neu gestartet (Windows-HMR-Trap). Bestands-Gutachten der Queue wurden reparst (Entscheidung RA Schatz), damit der Live-Test auf jedem greift.

<details><summary>Historische Beschreibung des Bugs</summary>

Beim Anlegen einer neuen Akte über den **AktenanlageDialog** (aus der Review-Queue) werden die **Mandanten-Daten NICHT vorausgefüllt** (von RA Schatz beobachtet). Muss vor dem Live-Test behoben sein — sonst enthält die exportierte OMA-XML keinen/leeren Mandanten.

- **Erwartung:** Der Dialog soll Mandant (Name, Anschrift, ggf. Kontakt/IBAN) aus dem erkannten Dokument bzw. den geparsten Beteiligten vorbefüllen.
- **Startpunkte:**
  - `frontend/src/components/AktenanlageDialog.jsx` (ersetzt NeueAkteModal) + `AktenanlageDialog.test.jsx`
  - Trigger/Banner: `frontend/src/views/ReviewQueueView.jsx` + `ReviewQueueView.aktenanlage.test.jsx`
  - Backend: `backend/routers/aktenanlage_routes.py`, `backend/services/aktenanlage_service.py`
  - Tests: `backend/tests/test_aktenanlage_routes.py`, `test_ramicro_aktenanlage.py`
- **Vorgehen:** `superpowers:systematic-debugging` — erst am echten Dev-System **reproduzieren** (Login unten), dann Ursache (woher SOLLTEN die Mandantendaten kommen? welcher Feld-Mapping-/Übergabe-Schritt liefert leer?), dann fixen + verifizieren (Playwright am Dev-System + betroffene Tests).

</details>

## 2. Abnahme-Checkliste (Stand)

| # | Schritt | Status |
|---|---|---|
| 1 | OMA-Ordner-Mount | ✅ **fertig** (s. u.) |
| 2 | Echter Export → RA-MICRO importiert → reale Akte | ⬜ **entblockt (§1 gefixt) — braucht Live-Lauf RA Schatz** |
| 3 | `FRAU`/`FIRMA`-Anrede + ISO-Datum + `dtAnlage` beim Import korrekt | ⬜ |
| 4 | Adressnummer-Referenz: „Bekannt = Ja" + Adressnummer → **keine Dublette** | ⬜ |
| 5 | Geschwister-Szenario: Gutachten auf erkanntes AZ freigeben, dann Rechnung/Body öffnen — AZ bleibt vorausgewählt | ⬜ |

**Schritt 1 erledigt (2026-08-03):** OMA-Ordner als **CIFS-Volume `oma-share`** in `docker-compose.yml` angelegt: `//192.168.10.100/ServerSQL/OMA` → `/app/oma_export`, **rw**, Zugangsdaten aus `.env` (`EAKTE_SMB_USER`/`EAKTE_SMB_PASSWORD`, gleicher ServerSQL-Share wie E-Akte). Persistent (Docker mountet bei jedem Start automatisch, `restart: unless-stopped`), **Schreibrechte bestätigt**, Backend healthy. Der Ordner ist echt (enthielt bereits `HUKKOPIE - HUK-Fragebogen.xml` von 2021).
- **PROD offen:** gleiche Volume-Definition in `docker-compose.prod.yml` nachziehen (nur ein Kommentar-Vermerk gesetzt).
- **Offene Frage an RA Schatz (Schritt 2):** Zieht RA-MICRO die OMA-XML **automatisch** ein (Überwachung) oder muss der Import in RA-MICRO **manuell** angestoßen werden? (Die 2021er-Datei liegt noch im Ordner → evtl. kein Auto-Cleanup/Auto-Import.)

**Ablauf Schritt 2 (nach Bugfix):** RA Schatz legt in der Dev-App (Review-Queue → „Akte anlegen") einen klar erkennbaren Testfall an und klickt Freigeben → OMA-XML landet im Ordner. Dann: XML im Ordner prüfen (Anrede/Datum), und **read-only** in RA-MICRO verifizieren, ob die Akte angelegt wurde (Spec Abschnitt 9). Verifikationspunkte 3–5 dabei mit abhaken.

## 3. Operatives (wichtig)

- **Login Dev-App** (`http://localhost:5173`, Playwright-Pattern): `schatz@anwalt-offenbach.de` / `Sachbearbeiter1!`. Playwright liegt unter einem älteren Session-Scratchpad (`.../1a418a8b-.../scratchpad/node_modules/playwright`, v1.62.1).
- **Dev-Container laufen auf dem Arbeitsverzeichnis** (Branch `dashboard-hell` inkl. aktenanlage), `restart: unless-stopped`. **NICHT** Branch wechseln, während die Container laufen (STATE.md).
- **Git-Wurzel = `C:\Users\HAL9000` (Home)**, NICHT das Projekt. NIE `git add -A` aus Home.
- **RA-MICRO read-only:** SQL-Introspektion ok (im Container via `from backend.ramicro.connector import get_ramicro_connection`, `os.chdir('/app')`), **NIE schreiben**. Server 192.168.10.100. Wichtig: RA-MICROs echte **Fristen** sind nicht SQL-lesbar (s. Memory `feedback_ramicro_fristen_quelle`) — für diese Aufgabe irrelevant, nur zur Einordnung.
- **Kontext-Doku:** `docs/superpowers/specs/2026-07-30-aktenanlage-design.md` (**Abschnitt 9** = Abnahme-/Verifikationspunkte), Plan `docs/superpowers/plans/2026-07-30-aktenanlage.md`, `docs/STATE.md` Abschnitt 0. Pflichtlektüre `docs/TODO.md` (Aktenanlage-Block unter „In Arbeit").

## 4. Nach den Merges — uncommittete Arbeit sichern

Diese Session hat Artefakte erzeugt, die **uncommittet** auf `dashboard-hell` liegen (RA Schatz hat den Commit-Ort noch nicht entschieden — Vorschlag `main` oder ein `docs`-Branch, **NICHT** dieser Feature-Branch):
- `docker-compose.yml` (OMA-CIFS-Volume — betriebsrelevant, gehört committet)
- 3 Design-Specs: `docs/superpowers/specs/2026-07-31-{review-queue-entruempeln,jetzt-dran-echte-signale,belege-zu-positionen}-design.md`
- `handover/2026-07-31_UX-Review_Roadmap.md`
- `docs/TODO.md` (Ergänzung „Zwei Positions-Modelle abgleichen" unter Unklar)
- dieser Handover

Die 3 Specs sind Baustellen 1a/1b/3 aus dem UX-Review 2026-07-31 (je Spec + Mockup, von RA Schatz freigegeben) — **Umsetzung erst NACH dem Merge-Gate.** Mockup-Links stehen in den jeweiligen Specs.

## 5. Reihenfolge

1. **Prefill-Bug fixen** (§1) + am Dev-System verifizieren.
2. **Live-Abnahme Schritt 2–5** mit RA Schatz (er klickt, du prüfst OMA-Ordner + RA-MICRO read-only).
3. **Merges** `aktenanlage → main`, dann `dashboard-hell → main` (FF; Dev-Betrieb möglichst nicht umschalten).
4. **Uncommittete Planungsdokumente** committen (Ort mit RA Schatz klären).
