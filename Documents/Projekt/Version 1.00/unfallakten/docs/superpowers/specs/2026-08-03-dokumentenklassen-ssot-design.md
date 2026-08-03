# Design-Spec: Dokumentenklassen-SSOT + 7 neue Klassen

Datum: 2026-08-03
Status: freigegeben (Brainstorming), wartet auf Spec-Review

## 1. Problem

„Dokumentenklasse" ist heute an **fünf** Stellen definiert, die sich nicht decken.
Eine Klasse hinzuzufügen bedeutet, bis zu fünf Dateien konsistent zu pflegen —
und ein Fehler bleibt still: Eine Klasse, die nur im Frontend-Dropdown steht,
ist wählbar, aber das Backend kennt sie nicht (kein Parser, kein Ereignis, keine
Positionszuordnung) → stiller Datenverlust.

Die fünf Quellen:

1. `backend/registry/klassen/*.yaml` — Intake-Registry (fail-loud Loader,
   trägt schon `label`, `fristrelevanz`, `loeschfrist_jahre`, `bezeichnung_felder`).
   Heute 8 Klassen: abrechnungsschreiben, abschlepprechnung, gutachten,
   pruefbericht, rechnung, sonstiges, standkostenrechnung, sv_rechnung.
2. `backend/workflow/dispatcher.py` → `_PARSER_MAP` — Klasse → Parser-Funktion.
3. `frontend/src/config/constants.js` → `DOK_TYPEN` — Dropdown, 19 hartkodierte
   Einträge (viele ohne Backend-Entsprechung).
4. `frontend/src/config/constants.js` → `KLASSE_TO_POS` **und**
   `backend/registry/rechnungstyp_mapping.yaml` — Klasse → Schadenposition
   (zwei Kopien, die bereits driften: `reparaturrechnung` → `rep_rechnung_brutto`
   im FE vs. `rep_rechnung_netto` im Backend). Dazu
   `backend/registry/klasse_ereignistyp.yaml` — Klasse → eingehender Ereignistyp.
5. `backend/word/word_service.py` → `GUELTIGE_DOK_TYPEN` — erlaubte Typen für
   **selbst erzeugte** Schreiben (Word-Generator).

## 2. Ziel

- **Eine** handgepflegte Quelle für Dokumentenklassen: die YAML-Dateien in
  `backend/registry/klassen/`. Alle anderen Listen werden daraus abgeleitet oder
  generiert und per Test gegen Drift abgesichert.
- Frontend und Backend führen garantiert dieselbe Klassenliste — oder der
  App-Start / die Testsuite bricht.
- 7 neue Klassen anlegen: `reparaturrechnung`, `mietwagenrechnung`, `arztbericht`,
  `krankenhausbericht`, `attest`, `mahnschreiben`, `klagedrohung`.
- Fristsetzungs-/Verzugs-Automatik für `klagedrohung`/`mahnschreiben`.

## 3. Gewählter Ansatz (B)

Die Intake-Registry (`klassen/*.yaml`) ist die alleinige Wahrheit. Das Backend
liest sie direkt; das Frontend erhält eine **generierte** Kopie mit
CI-Guard-Test. Kein Runtime-Endpoint, kein async-Umbau im Frontend — die
Sections importieren weiterhin eine Konstante.

Verworfen:
- **A (Live-Endpoint):** Dropdown hinge an einem Ladezustand; mehrere Formulare
  müssten die Liste asynchron beziehen. Größerer FE-Umbau, neue Fehlerzustände.
- **C (nur ergänzen):** Ließe die 5-fach-Spaltung bestehen — genau das Problem.

## 4. YAML-Schema-Erweiterung

Jede Klasse bleibt eine Datei `<klasse>.yaml` (Dateiname == `klasse:`-Feld,
Fail-Loud). Neue **optionale** Felder:

| Feld | ersetzt heute | Bedeutung |
|---|---|---|
| `parser` | `_PARSER_MAP` | Parser-Schlüssel (`rechnung`, `gutachten`, `abrechnungsschreiben`, `pruefbericht`) oder fehlt = kein Auto-Parsing |
| `richtung` | implizit | `eingehend` (Default), `ausgehend`, `beides` |
| `ereignistyp` | `klasse_ereignistyp.yaml` | eingehender Ereignistyp beim Import (muss in `ereignistypen.yaml` existieren und `richtung: eingehend` haben) |
| `schadenposition` | `KLASSE_TO_POS` + `rechnungstyp_mapping.yaml` | Ziel-position_key (aus `positionsarten.yaml`) oder Sondermarker `__sv_kosten_vorsteuer__` |

`label`, `fristrelevanz`, `loeschfrist_jahre`, `bezeichnung_felder` bestehen
bereits und bleiben.

**Rückwärtskompatibilität:** Alle neuen Felder sind optional. Die 8
Bestandsklassen funktionieren unverändert; ihre heutigen Parser-/Ereignistyp-/
Positions-Werte werden in die YAMLs gezogen, damit die Alt-Listen leer werden
können. Reine Ablage-Etiketten sind eine YAML mit leeren Markern (wie
`sonstiges.yaml` heute).

**Loader-Erweiterung** (`backend/intake/registry_loader.py`), gleicher
Fail-Loud-Stil:
- `parser`, falls gesetzt, muss ein bekannter Parser-Schlüssel sein.
- `richtung`, falls gesetzt, ∈ {eingehend, ausgehend, beides}.
- `ereignistyp` / `schadenposition` werden **beim App-Start** gegen die
  Positionsmodell-Registry (`positionsmodell_registry.py`) validiert — siehe
  §6, Reihenfolge der beiden Loader.

## 5. Die 7 neuen Klassen

| Klasse | Label | Richtung | Parser | Ereignistyp (Eingang) | Schadenposition | Fristrelevant |
|---|---|---|---|---|---|---|
| `reparaturrechnung` | Reparaturrechnung | eingehend | `rechnung` | `rechnung_eingegangen` | `rep_rechnung_netto` | – |
| `mietwagenrechnung` | Mietwagenrechnung | eingehend | `rechnung` | `rechnung_eingegangen` | `mietwagenkosten` | – |
| `arztbericht` | Arztbericht | eingehend | — | — | — | – |
| `krankenhausbericht` | Krankenhausbericht | eingehend | — | — | — | – |
| `attest` | Attest (AU / Haushalt) | eingehend | — | — | — | – |
| `mahnschreiben` | Mahnschreiben | beides | — | — | — | ja |
| `klagedrohung` | Klagedrohung / Fristsetzung | beides | — | — | — | ja |

**Marker-Strategie:**
- `reparaturrechnung` / `mietwagenrechnung`: trennscharfe Marker
  („Reparaturrechnung", „Mietwagen", „Ersatzfahrzeug" …). Parser =
  bestehender Rechnungs-Parser.
- `arztbericht` / `krankenhausbericht` / `attest`: **bewusst wenige,
  trennscharfe** Marker. Keine erzwungene Marker-Konkurrenz — im Zweifel landet
  ein medizinisches Dokument in `sonstiges` und wird per Dropdown zugeordnet.
  Verhindert Dauer-Konflikt-Eskalationen zwischen den drei.
- `klagedrohung` / `mahnschreiben`: eingehende Marker vorsichtig
  („letztmalige Frist", „gerichtliche Geltendmachung", „Mahnung") — geringe
  Fallzahl, Kollision mit ausgehender `klage` unkritisch.

**Sonderfall `klagedrohung` / `mahnschreiben` (`richtung: beides`):**
- **Selbst erzeugt** (Word) → stempeln das `frist_datum` exakt und buchen
  `fristsetzung_generiert` (existiert in `ereignistypen.yaml`).
- **Importiert** → landen als eingehendes Dokument in der Akte; bewegen keine
  Schadenposition, buchen daher beim Import kein Positions-Ereignis. Frist wird
  vom Import-Parser extrahiert (Plan 2).

## 6. Ableitung der Alt-Listen

**Handgepflegt wird nur die YAML.** Ableitung:

**Backend (liest direkt aus der Klassen-Registry):**
- `_PARSER_MAP` (dispatcher.py) → ersetzt durch Lookup des `parser`-Feldes.
- `GUELTIGE_DOK_TYPEN` (word_service.py) → abgeleitet: Klassen mit
  `richtung` ∈ {ausgehend, beides}.
- `klasse_ereignistyp.yaml` + `rechnungstyp_mapping.yaml` → **generiert** aus den
  `ereignistyp`/`schadenposition`-Feldern (bleiben als Datei bestehen, damit
  `positionsmodell_registry.py` unverändert liest — aber nicht mehr von Hand
  gepflegt). Header-Kommentar markiert sie als generiert.

**Frontend (eine generierte Datei):**
- Skript `tools/gen_dokumentenklassen.py` erzeugt
  `frontend/src/config/dokumentenklassen.generated.js`.
- Ersetzt `DOK_TYPEN` (value+label, sortiert) **und** `KLASSE_TO_POS`
  (Klasse → [position_key], aus `schadenposition` als Liste).
- Reconciliation: `KLASSE_TO_POS.reparaturrechnung` wechselt von
  `rep_rechnung_brutto` (FE, falsch) auf `rep_rechnung_netto` (validierte
  Backend-Wahrheit). Das ist eine bewusste Verhaltensänderung im FE.

**Zwei-Loader-Reihenfolge:** Der Klassen-Loader validiert `ereignistyp`/
`schadenposition` gegen die Positionsmodell-Registry. Da beide Loader
Cache-Singletons sind, ruft der Klassen-Loader den Positionsmodell-Loader zur
Kreuzvalidierung auf (Lazy-Import, analog zu `_validiere_position_keys_katalog`).

**Wächter (gegen erneute Drift):**
- **Guard-Test:** erzeugt Generate (FE-Datei + die zwei generierten YAMLs) neu
  und vergleicht byte-genau mit den eingecheckten Dateien → schlägt fehl, wenn
  jemand eine Klasse ändert, ohne das Skript laufen zu lassen. (Muster wie
  V11-Fixture-Sync.)
- Fail-Loud-Loader validiert alle Felder beim App-Start.

**Ergebnis:** Neue Klasse = **eine YAML schreiben + `gen_dokumentenklassen.py`
laufen lassen.** FE und BE danach garantiert identisch.

## 7. Umsetzung — zwei Pläne in Reihenfolge

### Plan 1 — Dokumentenklassen-SSOT (Fundament)

1. Loader (`registry_loader.py`) um optionale Felder + Fail-Loud-Validierung
   erweitern (`parser`, `richtung`, `ereignistyp`, `schadenposition`) inkl.
   Kreuzvalidierung gegen Positionsmodell-Registry.
2. Die 8 Bestandsklassen um ihre heutigen Werte ergänzen (Parser/Ereignistyp/
   Position aus `_PARSER_MAP`, `klasse_ereignistyp.yaml`, `rechnungstyp_mapping.yaml`
   hineinziehen).
3. Die 7 neuen YAMLs anlegen (ohne Frist-Sonderlogik — die kommt in Plan 2;
   `klagedrohung`/`mahnschreiben` zunächst ohne `frist_datum`-Schema).
4. Backend-Ableitungen umstellen: `_PARSER_MAP` → Registry-Lookup;
   `GUELTIGE_DOK_TYPEN` → abgeleitet; `klasse_ereignistyp.yaml` /
   `rechnungstyp_mapping.yaml` → generiert.
5. Codegen-Skript `tools/gen_dokumentenklassen.py`; generierte FE-Datei;
   `DOK_TYPEN`/`KLASSE_TO_POS` durch Import der generierten Datei ersetzen;
   alle Konsumenten (`DokumenteSection.jsx` u. a.) umstellen.
6. Guard-Tests + bestehende Testsuite grün. **→ Alle 5 Listen sind jetzt eine.**

### Plan 2 — Fristsetzungs-/Verzugs-Automatik (Feature)

7. `frist_datum`-Schemafeld für `klagedrohung`/`mahnschreiben`;
   `verzug_dokumente` um `frist_datum` erweitern (Migration, **atomar in einem
   Edit** wegen Reloader-Falle).
8. Word-Generator für `klagedrohung`/`mahnschreiben`: Frist exakt stempeln +
   `fristsetzung_generiert` buchen; Aufnahme in `GUELTIGE_DOK_TYPEN` folgt
   automatisch aus `richtung: beides`.
9. Import-Frist-Parser: Regex für „bis zum <Datum>" / „Frist zum <Datum>" /
   „innerhalb von … bis <Datum>", belegt `frist_datum` bei importierten
   Klagedrohungen/Mahnschreiben vor.
10. Klage-Wizard: Verzugseintritt = Tag nach Fristablauf vorbelegen (FE
    `KlageSection.jsx` + `klage_service.py`), gespeist aus `frist_datum`.

## 8. Teststrategie

- **TDD** durchgehend: erst Test, dann Code.
- Loader-Tests: neue Felder validieren, Fehlerfälle (unbekannter Parser,
  nicht-eingehender Ereignistyp, unbekannter position_key) müssen RuntimeError
  werfen.
- Guard-Test: generierte Artefakte == eingecheckte (byte-genau).
- Regressions: bestehende Intake-/Dispatcher-/Registry-Golden-Tests grün.
- Plan 2: Migrations-Guard, Frist-Parser-Unit-Tests (Datumsvarianten),
  Verzugs-Vorbelegung im Klage-Wizard.
- Je Plan ein Browser-Nachtest am Ende.

## 9. Bekannte Fallen / Offene Punkte

- **Positions-Namensraum-Drift** (TODO „zwei Positions-Modelle"): Das FE
  `KLASSE_TO_POS` nutzt teils `_brutto`/`_netto`-Varianten abweichend vom
  Backend. Diese Spec reconcilet auf die validierten `positionsarten.yaml`-Keys;
  bei der Umstellung ist je Klasse zu prüfen, ob abhängiger FE-Code (Regulierung/
  Inbox-Zuordnung) den geänderten Key verträgt.
- **Reloader-Falle** (Migrationen): Migration in Plan 2 atomar in *einem* Edit
  schreiben; aktive DB ist das Docker-Volume dev-data.
- **RA-MICRO read-only**: unberührt — alle Änderungen betreffen nur SQLite/Registry.
- **`sv_rechnung`-Sondermarker** `__sv_kosten_vorsteuer__` bleibt als
  `schadenposition`-Wert erhalten; Loader lässt ihn wie bisher durch.
- Weitere Kandidatenklassen (werkstattrechnung, gutachterrechnung,
  forderungsschreiben, sachstandsanfrage, kaufvertrag, nachbesichtigung,
  verdienstausfall_nachweis) sind bewusst **nicht** in diesem Satz — sie lassen
  sich später mit je einer YAML in dieselbe Struktur einhängen.
