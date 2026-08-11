# Bugfixes Forderungsschreiben-Modul

Quelle: Code-Review 2026-08-10, Vollbericht → `handover/2026-08-10-forderungsschreiben-review-befunde.md`.
Branch: `abschlussbericht`. Vorgehen: TDD (Test zuerst, rot sehen, dann fixen).

## Reihenfolge & Status

### Phase 0 — Aufräumarbeiten (Verbesserungsvorschläge) ✅ (2026-08-11, `a4cf92ca`)
- [x] **V-1** Toter Alt-Generator `backend/word/forderungsschreiben.py` gelöscht; Tests auf `_wv` portiert
- [x] **V-2** 8 tote Vorlagen entfernt — nur `forderungsschreiben_vorlage.docx` wird geladen
- [x] **V-1b** Toter Code `_KANZLEI_IBAN`/`_KANZLEI_BIC` (Fantasie-IBAN) entfernt
- [x] **Bonus:** 15 verrottete `TestWordRouten`-Tests repariert (Setup-AZ `25-W5-001` scheiterte seit Juli an der AZ-Format-Validierung `####/YY`)

### Phase 1 — Quick-Wins / Abstürze ✅ (2026-08-11, `ed797f17`)
- [x] **I-3** Ungeschütztes `float(varSCHMGELD)` — Freitext crasht nicht mehr
- [x] **I-1** Registry-Typen ohne Generator → sauberer 422 statt KeyError-500
- [x] **I-6** `varSSTF`-Override hinter das WDM-Laden verschoben — greift jetzt
- [x] **I-7** `aktualisiere_position()` verlangt `akte_id` (Scoping in UPDATE+SELECT)

### Phase 2 — Kernbefund Historie/Beträge ✅ (2026-08-11, `9e787541`)
- [x] **C-1** `berechne_positionen()` neu als SSOT (Brief-Tabelle UND Historie); `erfasse_forderung(akte_id, positionen)` übernimmt exakt die Brief-Positionen; Restwert negativ gespeichert; kanonisches AZ statt roher `akte_id`
- [x] **I-8** `forderungs_zusammenfassung` + Gebühren-Streitwert-Fallback: je `position_key` zählt nur der Stand des letzten Schreibens
- [x] **I-11** (Kern) `test_forderung_modell.py` neu + `TestBerechnePositionen` + Historie==Brief-Integrationstest; FE-Tests siehe Phase 4

### Phase 3 — Juristische Textfehler ✅ (2026-08-11, `9d93a951`)
- [x] **I-4** „Der Kläger" → „Unser(e) Mandant(in)/Mandanten" aus Genus-Vars; Bonus: `wurde/wurden verletzt`, `war/waren krankgeschrieben` numerus-korrekt
- [x] **I-5** Pseudo-„grunde" → `WordFehler` 422 „Keine Schadenpositionen erfasst" (FE kannte die Variante nie). **Vermerk:** Falls ein echtes Schreiben „dem Grunde nach" gewünscht ist, braucht es eine Formulierung von RA Schatz — dann als eigenes Feature.

### Phase 4 — Frontend ✅ (2026-08-11, `1b8d2402`)
- [x] **I-2** `adressat_id` durchgereicht (BE) + Vorbelegung zieht nach Beteiligten-Laden nach (FE); RA-MICRO-Fallback überschreibt explizite Auswahl nicht mehr
- [x] **I-9** Ignore-Guard, Ladezustand-Reset beim Aktenwechsel, sichtbarer Fehlerzustand in `ForderungshistorieKarte`

### Zurückgestellt — Entscheidung RA Schatz nötig
- [ ] **I-10** Haftungsquote: Produktiv-Generator behauptet immer Alleinschuld, FE-Banner quotiert, HQ=0-Semantik uneinheitlich. Der korrekte Textbaustein bei Teilhaftung ist eine juristische Formulierungsentscheidung → Vorschlag vorlegen, nicht eigenmächtig texten.

### Minors (opportunistisch, bei Anfassen der Datei)
- `naechste_schreiben_nr`-Race (eigene Connection) · `kuerzungsart_id` ohne Validierung · leerer PATCH → 404 statt 422 · `_pruefe_akte`-Rückgabewert verworfen in `word_routes.py:54,76` + `int(adressat_id)` ohne try · `vorschau` fängt nur `WordFehler` · Sofort-Download regeneriert statt E-Akte-Datei · `_merge_split_placeholders` verliert Misch-Formatierung · MwSt 19 % dreifach hartkodiert · `/zusammenfassung` FE-ungenutzt + zwei „Klagepotential"-Definitionen

### Vermerke ohne Fix-Zwang (aus Review)
- **V-3** Positionsliste berechnen / XML rendern trennen (wird mit C-1 miterledigt)
- **V-4** Status `vollreguliert` → `betrag_reguliert` automatisch nachziehen (oder warnen)
- **V-5** Frontend-Tests `ForderungshistorieKarte` nachziehen

## Protokoll

**2026-08-11 — alle Phasen 0–4 umgesetzt** (Branch `abschlussbericht`, Commits `520e75af..1b8d2402`):
- `520e75af` docs: Befundbericht + diese Arbeitsliste
- `a4cf92ca` chore: Phase 0 Aufräumen (Alt-Generator, 8 Vorlagen, IBAN-Totcode, TestWordRouten-Reparatur)
- `ed797f17` fix: Phase 1 (I-3, I-1, I-6, I-7)
- `9e787541` fix: Phase 2 (C-1 SSOT-Positionsliste, I-8 Dedup, I-11 Testfundament)
- `9d93a951` fix: Phase 3 (I-4 Mandanten-Formulierung + Numerus, I-5 grunde→422)
- `1b8d2402` fix: Phase 4 (I-2 Adressat, I-9 FE-Race)

Testbilanz: Backend `test_modul5` 84/84 + `test_forderung_modell` 8/8 (23 neue Tests, alle vorher rot verifiziert); angrenzende Suiten (Klage KW39/S2/KW28, P1.4, Abschlussbericht, Registry-Typen, Genus) 69/69; Frontend-Vollsuite 498/498 (4 neue).

Besonderheiten / bewusste Entscheidungen:
- **Restwert wird jetzt negativ gespeichert** (`forderung_positionen.betrag_gefordert`) — Summen ergeben den echten Forderungsbetrag. Bestandszeilen mit positivem Restwert bleiben unverändert (kein Backfill; betrifft nur Alt-Akten mit Totalschaden-Historie).
- **Aggregat-Semantik:** `gesamt_gefordert`/`offen`/`klagepotential`/Streitwert-Fallback = Stand des jeweils letzten Schreibens je `position_key` (vollregulierte Positionen behalten ihren letzten Stand automatisch).
- `test_modul6`/`test_modul7` haben 95 vorbestehende Failures (gleiche Zahl vor/nach allen Änderungen, gleiche Ursachen-Klasse wie die reparierte AZ-Verrottung) — separates Sanierungsthema, nicht Forderungsmodul.
- I-10 (Haftungsquote/Alleinschuld-Baustein) bewusst offen: juristische Formulierung gehört RA Schatz vorgelegt.
