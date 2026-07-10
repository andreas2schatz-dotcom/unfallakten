# P1.5e — Review-Freigabe schreibt Ereignisse für alle Dokumentenklassen

> Design-Spec · 2026-07-11 · Branch `intake-stufe1`
> Kontext: Intake-Refactoring (Pipeline v7 + Positionsmodell), Fortsetzung nach P1.1–P1.7.
> Maßgebliche Vorwissen: `docs/TODO.md` Abschnitt P1.5e, `freigabe.md`, `POSITIONSMODELL-PLAN.md`.

## Problem

Bei der Review-Freigabe (`POST /intake/dokument/<id>/freigabe`) wählt der
Sachbearbeiter im Dialog „Ereignis-Vorschläge" pro Dokument den passenden
Ereignistyp aus einem Dropdown (Feld `kandidaten_ereignisse`, je Eintrag
`{typ}`). Diese Auswahl wird heute **nur als Kontext ins `korrektur_log`**
geschrieben — sie entfaltet keine Wirkung im Positionsmodell.

Einzige Ausnahme: Dokumente der Klasse `gutachten`. Für sie schreibt
`post_freigabe` — **klassen-getrieben, unabhängig vom Dropdown** — ein echtes
`gutachten_eingegangen`-Ereignis mit Positionen aus den geparsten Feldern
(Option A, `_schreibe_gutachten_ereignis`, `herkunft='ki_dialog'`).

Damit ist das gesamte Positionsmodell (P1.1–P1.7) für den Haupt-Eingangsweg
blind: es „sieht" nur Gutachten. Für Abrechnungen, Rechnungen, Prüfberichte
usw. bleibt das Dashboard leer.

## Ziel

Die im Freigabe-Dialog **bestätigten** Ereignistypen werden tatsächlich ins
Positionsmodell gebucht — für **alle** Klassen, nicht nur Gutachten. Der neue
Ereignistyp-Dropdown entfaltet damit endlich Wirkung.

## Zwei getroffene Grundsatzentscheidungen (RA Schatz, 2026-07-11)

1. **Auslöser:** Die **Dropdown-Auswahl** steuert, welches Ereignis gebucht
   wird. Eine Registry-YAML liefert je Klasse nur die **Vorbelegung** (Default),
   die der Sachbearbeiter bestätigen, ändern oder ergänzen kann. (Nicht:
   rein klassen-getrieben ohne Korrekturmöglichkeit.)
2. **Positionen/Beträge:** Es werden **nur echte Beträge** gebucht, die
   eindeutig im Dokument stehen. Fehlen sie, wird das Ereignis als **reiner
   Fakt** gebucht (erfüllt die Checkliste, erfindet aber keine Zahlen). Passt
   zur Ehrlichkeits-Linie des Projekts (AbleitungBadge, K-M3, N-07).

Die Zuordnung Klasse→Ereignistyp liegt als **Registry-YAML** vor (nicht
hartkodiert, nicht in den App-Einstellungen — „Variante 2"). Grund: Es ist
Fachlogik, die selten wechselt; eine editierbare UI wäre unnötige Abstraktion
und könnte die Fail-Loud-Konsistenz des Positionsmodells unterlaufen.

## Nicht-Ziele (YAGNI)

- **Keine** Heuristik zur Ableitung von Abrechnungs-/Prüfbericht-Beträgen aus
  generischem Parse — dafür existiert der ReguWizard (P1.5a).
- **Keine** Einstellungs-Oberfläche zur Laufzeit-Konfiguration des Mappings.
- **Keine** Änderung an den Alt-Tabellen (`regulierung_positionen` etc.) —
  P1.5e ist additiv, Doppelführung bleibt bestehen.
- **Keine** Migration/Schema-Änderung — die `ereignisse`-Tabellen existieren
  seit P1.2.

## Architektur

### Komponente 1 — Registry `backend/registry/klasse_ereignistyp.yaml` (neu)

Analog zur bestehenden `rechnungstyp_mapping.yaml`. Mappt jede
Dokumentenklasse (aus `backend/registry/klassen/*.yaml`) auf den vorbelegten
eingehenden Ereignistyp:

```yaml
klasse_ereignistyp:
  gutachten:            gutachten_eingegangen
  rechnung:             rechnung_eingegangen
  abschlepprechnung:    rechnung_eingegangen
  standkostenrechnung:  rechnung_eingegangen
  sv_rechnung:          rechnung_eingegangen
  abrechnungsschreiben: abrechnung_eingegangen
  pruefbericht:         pruefbericht_eingegangen
  # sonstiges: bewusst KEINE Vorbelegung
```

**Loader** (`positionsmodell_registry.py`): neues Feld
`klasse_ereignistyp` auf `PositionsmodellRegistry`, fail-loud geladen.
Konsistenzcheck: jeder Wert muss ein in `ereignistypen.yaml` existierender
Ereignistyp mit `richtung == eingehend` sein. Unbekannter oder nicht-
eingehender Typ → App-Start bricht ab (analog bestehende Registry-Checks).

### Komponente 2 — Helper `eingehende_ereignisse.erzeuge_aus_freigabe(...)` (neu)

Zentraler, einheitlicher Bestätigungsweg für die Review-Freigabe. Signatur:

```
erzeuge_aus_freigabe(*, akte_az, dokument_id, ereignistyp, klasse,
                     felder, vorsteuer, benutzer_id=None, datum=None)
    -> Optional[int]
```

Ablauf (Best-Effort, Ausnahmen werden geloggt, nie durchgereicht):

1. **Doppelerfassungs-Guard:** `pruefe_doppelerfassung(akte_az, dokument_id,
   ereignistyp)`. Vorhandenes aktuelles Ereignis → INFO-Log, Rückgabe der
   Alt-ID, **kein** neues Ereignis.
2. **Positions-Ableitung je Ereignistyp:**

   | Ereignistyp | Positionen | Quelle |
   |---|---|---|
   | `gutachten_eingegangen` | reparaturkosten / wiederbeschaffung / restwert / wertminderung / sv_kosten, Wirkung `gefordert` | geparste `felder` (bestehende Ableitung inkl. sv_kosten-Vorsteuer-Weiche) |
   | `rechnung_eingegangen` | **eine** Position, Wirkung `beleg` | `position_key` aus `rechnungstyp_mapping[klasse]`; Betrag aus `felder['bruttobetrag']` bzw. `['nettobetrag']` |
   | alle übrigen (`abrechnung_eingegangen`, `pruefbericht_eingegangen`, …) | **keine** (Fakt-Ereignis) | — |

   Fehlt bei `rechnung_eingegangen` ein `position_key` (z. B. generische
   `rechnung` ohne Subtyp in `rechnungstyp_mapping`) → ebenfalls Fakt-Ereignis
   ohne Position. Kein erfundener Betrag.
3. **`schreibe_ereignis(...)`** mit `quelle='dokument'`, `herkunft='freigabe'`,
   `dokument_id=<neue dokumente.id>`, `erfasst_von=benutzer_id` und den
   abgeleiteten (ggf. leeren) Positionen. `schreibe_ereignis` bleibt der
   EINZIGE Schreibpunkt der drei Ereignis-Tabellen.

Die felder→Positionen-Ableitung für Gutachten (`_feld_zu_zahl`,
sv_kosten-Vorsteuer-Weiche) wird aus `intake_routes.py::_schreibe_gutachten_ereignis`
in `eingehende_ereignisse.py` verschoben bzw. dort als Helper geteilt, damit
`erzeuge_aus_freigabe` sie wiederverwendet (keine Kopie).

### Komponente 3 — Route `post_freigabe` (Umbau in `intake_routes.py`)

Der Sonderblock `if (dok.get("klasse") or "").lower() == "gutachten": …`
entfällt und wird durch einen einheitlichen Weg ersetzt:

1. **Ereignisliste auflösen:**
   - `bestaetigt = payload.get("kandidaten_ereignisse")` (Liste `{typ}`).
   - Ist sie leer/fehlt: Fallback auf den Registry-Default der Klasse
     (`klasse_ereignistyp[klasse]`), falls vorhanden — sonst leere Liste.
     Damit bleibt das heutige Gutachten-Auto-Verhalten für API-Aufrufer ohne
     Dialog erhalten.
2. **Pro Ereignistyp** ein Aufruf von `erzeuge_aus_freigabe(...)`, jeweils in
   try/except gekapselt (eine Panne bricht die Freigabe nie ab).
3. Das bestehende `_log_korrektur`-Schreiben von `kandidaten_ereignisse`,
   `ersetzt_ids`, `sekunden_bis_freigabe` bleibt **unverändert** bestehen
   (Audit-Trail).
4. `vorsteuer` wird wie bisher über `_mandanten_vorsteuer(akte_az)` bestimmt
   und an `erzeuge_aus_freigabe` durchgereicht (für die sv_kosten-Weiche).

Der `korrektur`-Endpoint für den echten KI-Dialog
(`dokumente/<did>/korrektur` → `erzeuge_aus_gutachten`, `herkunft='ki_dialog'`)
bleibt **unangetastet**.

### Komponente 4 — Detail-Endpoint + Frontend-Vorbelegung

- `GET /intake/dokument/<id>` liefert zusätzlich **`default_ereignistyp`**
  (aus `klasse_ereignistyp[klasse]`, oder `null`).
- `ReviewQueueView.jsx` (`DetailPanel`): Beim Laden eines Dokuments wird die
  Ereignis-Liste des Dialogs mit `[{typ: default_ereignistyp}]` **vorbelegt**,
  sofern vorhanden (statt leerer Liste). Der Sachbearbeiter kann bestätigen,
  ändern oder weitere hinzufügen.
- Der Hinweistext im `FreigabeDialog` („Persistierung ins Positionsmodell folgt
  mit P1.5e — heute nur korrektur_log") wird auf den neuen Stand aktualisiert.

## Datenfluss (Beispiel: abschlepprechnung)

1. Sachbearbeiter öffnet Dokument #42 (Klasse `abschlepprechnung`) in der Queue.
2. Detail-Endpoint liefert `default_ereignistyp='rechnung_eingegangen'`.
3. Dialog zeigt „Rechnung eingegangen" vorgewählt. Sachbearbeiter bestätigt,
   klickt Freigeben.
4. `post_freigabe`: `schreibe_dokument` → neue `dokumente.id=777`.
5. `erzeuge_aus_freigabe(ereignistyp='rechnung_eingegangen',
   klasse='abschlepprechnung', felder={bruttobetrag: '350,00'}, …)`:
   - Guard: kein Vor-Ereignis.
   - `rechnungstyp_mapping['abschlepprechnung'] = 'abschleppkosten'`.
   - Betrag 350,00 aus `bruttobetrag`.
   - `schreibe_ereignis(ereignistyp='rechnung_eingegangen', herkunft='freigabe',
     dokument_id=777, positionen=[{position_key:'abschleppkosten',
     wirkung:'beleg', betrag:350.0}])`.
6. Dashboard zeigt die Position `abschleppkosten` als belegt.

## Fehlerbehandlung

- Alle Ereignis-Erzeugungen sind Best-Effort: try/except pro Ereignistyp in
  der Route **und** im Helper. Eine Ausnahme wird geloggt (WARNING), die
  Freigabe (Dokument-Schreiben + `freigaben`-Zeile + `queue_status`) läuft
  regulär durch.
- Registry-Load-Fehler beim App-Start ist fail-loud (gewollt — Config-Fehler
  soll früh auffallen, nicht zur Laufzeit einzelne Freigaben stillschweigend
  entwerten).

## Tests

Keine Migration → kein DB-Backup nötig (Schema unverändert).

**Backend — `backend/tests/test_p15e_freigabe_ereignisse.py` (neu):**
- E2E je Klasse „Freigabe → passendes Ereignis":
  - `gutachten` → `gutachten_eingegangen` **mit** Positions-Cache-Zeilen
    (Wirkung `gefordert`), `herkunft='freigabe'`.
  - `abschlepprechnung` → `rechnung_eingegangen` mit **einer** beleg-Position
    (`abschleppkosten`).
  - `abrechnungsschreiben` → `abrechnung_eingegangen` **ohne** Positionen.
  - `pruefbericht` → `pruefbericht_eingegangen` **ohne** Positionen.
- Doppelerfassungs-Guard: zweite Freigabe desselben Dokuments (gleicher Typ)
  → **kein** zweites Ereignis.
- Fallback: Freigabe **ohne** `kandidaten_ereignisse` → Registry-Default greift
  (Gutachten-Beispiel schreibt weiterhin).
- Mehrere bestätigte Typen auf einem Dokument → je ein Ereignis, Guard je
  `(akte, dokument_id, ereignistyp)`.

**Registry — `backend/tests/test_positionsmodell_registry.py` (erweitern):**
- `klasse_ereignistyp` wird geladen; alle Werte sind gültige **eingehende**
  Ereignistypen (fail-loud bei Verstoß).

**Frontend — Vitest (`ReviewQueueView` oder fokussierter Dialog-Test):**
- Dialog belegt das Ereignis-Dropdown mit `default_ereignistyp` vor.

**Verifikation:** volle Backend-Suite vor/nach. Baseline 208f/712p/18s. Erwartung:
nur neue grüne Tests, keine echten Non-Alt-Regressionen (bekanntes
Test-Order-Rauschen in Auth-401/haftungsquote/sv_portal darf wandern).

## Offene Detailpunkte für den Implementierungsplan

- `herkunft`-Angleichung: Die bestehende Gutachten-Option-A im Freigabe-Pfad
  nutzte `herkunft='ki_dialog'`. P1.5e vereinheitlicht auf `herkunft='freigabe'`.
  Falls ein bestehender Test die `herkunft` der Gutachten-Freigabe prüft, wird
  er entsprechend aktualisiert (Option-A war eine junge Erweiterung).
- Exakte Feldnamen für die Betrags-Extraktion je Klasse aus den
  `klassen/*.yaml`-Schemata (`bruttobetrag`, `nettobetrag`, Gutachten-Felder)
  im Plan verankern.
