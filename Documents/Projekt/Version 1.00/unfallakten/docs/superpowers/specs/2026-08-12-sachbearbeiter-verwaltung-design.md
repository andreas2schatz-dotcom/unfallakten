# Sachbearbeiter-Verwaltung in den Einstellungen — Design

**Datum:** 2026-08-12 · **Status:** vom Nutzer freigegeben (RA Schatz) · **Auslöser:** Feinschliff Dashboard-Hell, Punkt „SB-Klarnamen-Tooltips"

## 1. Ausgangslage

Sachbearbeiter-Kürzel und -Namen stehen heute an vier Stellen hartcodiert im Code und laufen auseinander:

| Ort | Inhalt | Stand |
|---|---|---|
| `frontend/src/views/ActionBoardView.jsx` | `ALLE_SB` (8 Kürzel), `DEFAULT_SB` (5) | ohne CS, SN, JH |
| `backend/ramicro/sachbearbeiter.py` | `SACHBEARBEITER` (10 Kürzel → Name + Titel) | Quelle der Unterschriftszeile in allen DOCX |
| `backend/routers/dashboard_routes.py` | `_KALENDER_ZU_SB` (5 Kalendernamen → Kürzel) | Termine der übrigen SB werden nicht zugeordnet |
| `backend/word/unterschriften/` | Bilddateien je Kürzel | bleibt unverändert (nicht Teil dieses Vorhabens) |

Bestandsaufnahme in RA-MICRO (`tblAkten`, read-only, 2026-08-12) — Akten je Kürzel:

```
PK 7608 · AH 4255 · AS 3201 · MM 3120 · JH 2182 · CO 205 · ME 20 · EM 5 · EY 2 · EI 1
```

Daraus folgt:

- **JH (Jochen Hofmann)** führt 2.182 Altakten, war Partner bis 2011, ist im System aber unbekannt — kein Filter-Chip, in Schreiben `[JH]` statt des Namens.
- **TB, SK, SN, CS** haben null Akten. Das ist korrekt: das Kürzel eines Aktensachbearbeiters gehört in der Regel einem Anwalt bzw. einer Anwältin; ReFa-Kürzel sind trotzdem relevant (Kalender, Wiedervorlagen).
- **ME, EM, EY** (20/5/2 Akten) sind laut RA Schatz Fehlanlagen oder Privatakten.

## 2. Ziel und Nicht-Ziele

**Ziel:** Eine gepflegte Quelle für Sachbearbeiter, im Browser durch RA Schatz änderbar — anlegen, ausscheiden lassen, Name/Titel/Anrede/Rolle ändern, Vorauswahl der Tagesübersicht setzen, RA-MICRO-Kalendernamen hinterlegen. Backend und Frontend lesen ausschließlich daraus.

**Nicht-Ziele:** Upload von Unterschriftsbildern; Benutzerkonten/Rechte (die Anmeldung bleibt davon unberührt); Schreibzugriffe auf RA-MICRO (bleibt read-only).

## 3. Datenmodell — Migration 68

```sql
CREATE TABLE IF NOT EXISTS sachbearbeiter (
    kuerzel              TEXT PRIMARY KEY,                 -- exakt 2 Großbuchstaben
    name                 TEXT    NOT NULL,
    titel                TEXT    NOT NULL DEFAULT '',      -- "Rechtsanwältin", …
    anrede               TEXT    NOT NULL DEFAULT '',      -- 'herr' | 'frau' | ''
    rolle                TEXT    NOT NULL DEFAULT 'anwalt',-- 'anwalt' | 'refa'
    aktiv                INTEGER NOT NULL DEFAULT 1,
    ignoriert            INTEGER NOT NULL DEFAULT 0,       -- aus dem RA-MICRO-Abgleich ausgeblendet
    dashboard_vorauswahl INTEGER NOT NULL DEFAULT 0,
    kalender_name        TEXT,                             -- raKalender.dbo.Calendars.Name
    sortierung           INTEGER NOT NULL DEFAULT 100,
    erstellt_am          TEXT    NOT NULL DEFAULT (datetime('now')),
    geaendert_am         TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sachbearbeiter_kalender
    ON sachbearbeiter(kalender_name)
    WHERE kalender_name IS NOT NULL AND kalender_name <> '';
```

**Startbefüllung (11 Zeilen)** — Zustand danach entspricht dem heutigen Verhalten, ergänzt um CS und JH:

| Kürzel | Name | Titel | Anrede | Rolle | aktiv | Vorauswahl | Kalendername | Sort. |
|---|---|---|---|---|---|---|---|---|
| AS | Andreas Schatz | Rechtsanwalt | herr | anwalt | ja | ja | `RA.Schatz` | 10 |
| PK | Peter Koch | Rechtsanwalt | herr | anwalt | ja | ja | `Peter Koch` | 20 |
| CO | Claudia Ostarek | Rechtsanwältin | frau | anwalt | ja | ja | `C. Ostarek` | 30 |
| MM | Monika Mieth | Rechtsanwältin | frau | anwalt | ja | ja | `Monika Mieth` | 40 |
| AH | Alexander Herbert | Rechtsanwalt | herr | anwalt | ja | ja | `Alexander.Herbert` | 50 |
| CS | Carina Salvagnin | Rechtsanwältin | frau | anwalt | ja | nein | — | 60 |
| TB | Tanja Brunner | Rechtsanwalts- und Notarfachangestellte | frau | refa | ja | nein | — | 70 |
| SK | Sophie Koch | Rechtsanwaltsfachangestellte | frau | refa | ja | nein | — | 80 |
| EI | Elsa Ihl | Rechtsanwaltsfachangestellte | frau | refa | ja | nein | — | 90 |
| SN | Susanne Neumann | Rechtsanwaltsfachangestellte | frau | refa | ja | nein | — | 100 |
| JH | Jochen Hofmann | Rechtsanwalt | herr | anwalt | **nein** | nein | — | 110 |

Die Migration ist additiv und idempotent (`INSERT OR IGNORE` je Zeile), folgt also der bestehenden Regel „Migration vor App-Code" (`docs/STATE.md`).

## 4. Backend

### 4.1 Modul `backend/ramicro/sachbearbeiter.py`

Bleibt Heimat und Importpfad — die fünf aufrufenden Generatoren (`forderungsschreiben_wv`, `sachstandsanfrage_wv`, `stellungnahme_service`, `gebuehren_word`, `abrechnungsuebersicht_service`) werden **nicht** angefasst.

- `hole_sachbearbeiter(kuerzel) -> dict` — Signatur und Fallback-Verhalten unverändert (leeres Kürzel → Kanzleiname; unbekannt → `[XY]`), liest aber aus der Tabelle.
- `alle_sachbearbeiter(nur_aktive=False) -> list[dict]` — sortiert nach `sortierung`, `kuerzel`.
- Zeilen mit `ignoriert=1` gelten als „nicht gepflegt": `hole_sachbearbeiter` liefert für sie `[XY]` wie für ein unbekanntes Kürzel, und sie erscheinen weder in `alle_sachbearbeiter(nur_aktive=True)` noch als Chip.
- `kalender_zu_kuerzel() -> dict[str, str]` — ersetzt `_KALENDER_ZU_SB` in `dashboard_routes.py`.
- `_FALLBACK` — das heutige Dict bleibt als Notnagel, falls die Tabelle fehlt (Bestands-DB ohne Migration 68). Nur Lesen; Schreibzugriffe melden dann einen Fehler.

**Kein Zwischenspeicher.** Die Tabelle hat ~11 Zeilen; jeder Zugriff liest frisch. Damit wirkt eine Änderung sofort in allen Gunicorn-Workern (ein Prozess-Cache würde genau hier zu veralteten Namen führen).

### 4.2 Endpunkte (`backend/routers/einstellungen_routes.py`, `@login_erforderlich`)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/einstellungen/sachbearbeiter` | Liste aller Zeilen (inkl. inaktiv/ignoriert, mit Kennzeichen) |
| POST | `/einstellungen/sachbearbeiter` | anlegen |
| PUT | `/einstellungen/sachbearbeiter/<kuerzel>` | ändern (Kürzel selbst unveränderlich) |
| DELETE | `/einstellungen/sachbearbeiter/<kuerzel>` | löschen |
| GET | `/einstellungen/sachbearbeiter/ramicro-abgleich` | Kürzel + Aktenzahl aus RA-MICRO |

**Validierung** (400, bei Duplikat 409):

- `kuerzel`: `^[A-Z]{2}$` — exakt zwei Großbuchstaben, deckungsgleich mit RA-MICRO; eindeutig.
- `name`: nicht leer. `rolle` ∈ {`anwalt`, `refa`}. `anrede` ∈ {`herr`, `frau`, `''`}.
- `kalender_name`: falls gesetzt, systemweit eindeutig (sonst landen dieselben Termine bei zwei Personen).

**RA-MICRO-Abgleich** (read-only, `tblAkten` gruppiert nach `sAktenSachbearbeiter`):

```json
{"verfuegbar": true,
 "kuerzel": {"PK": 7608, "AS": 3201, "…": 0},
 "unbekannt": [{"kuerzel": "ME", "akten": 20}]}
```

`unbekannt` = in RA-MICRO vorhanden, hier weder gepflegt noch ignoriert. Ist RA-MICRO nicht erreichbar, liefert der Endpunkt `{"verfuegbar": false}` — nichts wird blockiert.

## 5. Frontend

### 5.1 Neuer Reiter „Sachbearbeiter" (`views/einstellungen/SachbearbeiterTab.jsx`)

Tabelle mit inline bearbeitbaren Zeilen: Kürzel (nur beim Anlegen), Name, Titel, Anrede, Rolle, Häkchen „aktiv" und „in Tagesübersicht vorausgewählt", Kalendername. Darunter „+ Sachbearbeiter"; je Zeile Löschen mit Rückfrage samt Hinweis, dass Altakten dann `[XY]` zeigen. Inaktive und ignorierte Zeilen stehen grau am Ende.

Je Zeile eine Statusangabe aus dem Abgleich: „RA-MICRO: 3.201 Akten" bzw. „keine Akten in RA-MICRO". Diese Warnung erscheint **nur bei Rolle `anwalt`** — bei ReFa ist null der Normalfall.

Über der Tabelle der umgekehrte Abgleich: „In RA-MICRO gibt es Kürzel ohne Eintrag: JH (2.182), ME (20) …" mit je zwei Knöpfen **anlegen** (öffnet das Formular vorbelegt) und **ignorieren** (legt per POST eine Zeile mit `aktiv=false`, `ignoriert=true` und dem Kürzel als Name an; das Kürzel wird nicht mehr gemeldet und löst weiterhin zu `[XY]` auf).

Beim Speichern eines Anwalt-Kürzels ohne Akten in RA-MICRO: Rückfrage „Kürzel in RA-MICRO nicht vergeben — trotzdem speichern?" — kein Blocker.

### 5.2 Tagesübersicht (`ActionBoardView.jsx`)

`ALLE_SB`/`DEFAULT_SB` entfallen. Die Liste wird beim Laden zusammen mit Terminen/Fristen/Wiedervorlagen geholt:

- Chips = aktive Sachbearbeiter in gepflegter Reihenfolge, `title` = „Name · Titel" (erledigt den offenen Feinschliff-Punkt).
- Erstauswahl = Personen mit `dashboard_vorauswahl`; danach gilt weiterhin die in `localStorage` gespeicherte Auswahl, gefiltert gegen die geladenen Kürzel.
- Beibehalten: Akten mit unbekanntem oder fehlendem Kürzel werden **nie** versteckt; solange die Liste nicht geladen ist, wird **nicht** gefiltert.

## 6. Randfälle

| Fall | Verhalten |
|---|---|
| Tabelle fehlt (Bestands-DB ohne Migration) | Lesen über eingebautes Fallback-Dict; Schreiben meldet Fehler |
| RA-MICRO nicht erreichbar | Abgleich `verfuegbar: false`, Statusangaben entfallen, nichts blockiert |
| Kürzel gelöscht, das RA-MICRO noch führt | Schreiben zeigen `[XY]`; Dialog weist vorher darauf hin, „inaktiv" ist der empfohlene Weg |
| Kalendername doppelt vergeben | 400 mit Klartextmeldung, Speichern abgelehnt |
| Liste leer (alle inaktiv) | Tagesübersicht zeigt keine Chips und filtert nicht |

Nicht angefasst wird die AZ-Normalisierung (`/[A-Z]{2,3}$/`) in `App.jsx` und `ActionBoardView.jsx`: sie ist bewusst tolerant und hat mit der Kürzel-Pflege nichts zu tun.

## 7. Tests (TDD, Test zuerst)

**Backend**

1. Migration 68 legt Tabelle und 11 Startzeilen an; erneuter Lauf ändert nichts (idempotent).
2. `hole_sachbearbeiter` liest aus der Tabelle; geänderter Name wirkt sofort; unbekanntes Kürzel → `[XY]`; ignoriertes Kürzel ebenfalls `[XY]`; leeres Kürzel → Kanzleiname.
3. CRUD: anlegen/ändern/löschen; Kürzel-Regel `^[A-Z]{2}$`; Duplikat → 409; doppelter Kalendername → 400; `rolle`/`anrede` außerhalb der erlaubten Werte → 400.
4. Abgleich: liefert Kürzel + Aktenzahlen und die Liste `unbekannt`; ignorierte Kürzel fehlen darin; RA-MICRO gemockt (`_RAMICRO_VERFUEGBAR=False` → `verfuegbar: false`).
5. Termin-Zuordnung nutzt `kalender_zu_kuerzel()` statt der Konstante.
6. Generator-Test: geänderter Titel erscheint im erzeugten DOCX unter der Unterschrift.

**Frontend**

7. Reiter lädt Liste, legt an, meldet Validierungsfehler, fragt vor dem Löschen nach.
8. Abgleich-Hinweis zeigt unbekannte Kürzel; „ignorieren" entfernt sie aus dem Hinweis.
9. Tagesübersicht baut Chips samt Tooltips aus der API, respektiert Vorauswahl und gespeicherte Auswahl.
10. Unbekannte Kürzel in Akten werden nicht versteckt; ohne geladene Liste wird nicht gefiltert.

## 8. Bewusst außerhalb

Unterschriftsbilder bleiben Dateien in `backend/word/unterschriften/`. Eine Kopplung der Sachbearbeiter an Benutzerkonten (Login) ist nicht Teil dieses Vorhabens.
