# PRD-37 — Dokumentenbezeichnung vorschlagen + Feld

> Design-Spec · 2026-07-15 · Branch-Ziel: Feature-Branch von `main`
> Status: freigegeben im Brainstorming (RA Schatz)

## Ziel

Dokumente tragen heute nur ihren **physischen Dateinamen** (z. B. `scan_0042.pdf`) plus
Klasse/Typ. Das ist im Review und in der E-Akte schlecht lesbar. PRD-37 führt eine
**sprechende Dokumentenbezeichnung** ein: Das System schlägt sie **regelbasiert** aus den
inhaltlichen Dokumentdaten vor, der Anwalt kann sie überschreiben, und sie wird bei der
Review-Freigabe in die Akte übernommen und ist dort nachträglich editierbar.

PRD-38 (LLM-Vorschlag) baut später auf demselben Feld und derselben Baseline auf — deshalb
lebt die Vorschlags-Regel als **eine** wiederverwendbare Backend-Funktion.

## Leitentscheidungen (aus dem Brainstorming)

1. **Zuschnitt B:** Vorschlag im Review, Übernahme bei Freigabe, und die Bezeichnung bleibt
   in der E-Akte nachträglich editierbar.
2. **Einheitliches Schema** (kein per-Klasse-Template):
   `«Klassen-Label» «Aussteller» vom «Datum» («Betrag»)` — leere Teile fallen sauber weg.
3. **Nur inhaltliche Dokumentdaten** speisen die Bezeichnung. Kein Vermengen mit dem
   Transportweg: **kein Eingangsdatum**, **kein E-Mail-Absender** — mit **einer** bewussten
   Ausnahme (Sonderfall `sonstiges`, siehe unten).
4. **Datum = nur das Schriftdatum** (Dokumentdatum aus `parse_json.felder`). Fehlt es, fällt
   der Datumsteil weg (Ausnahme `sonstiges`).
5. **Aussteller = nur der geparste Dokument-Aussteller** (Rechnungssteller/Versicherung/
   Sachverständiger aus `parse_json.felder`). Kein Rückfall auf den E-Mail-Absender.
6. **Lebendiger Vorschlag:** Solange das Feld nicht manuell editiert wurde, rechnet es sich
   bei Korrekturen (Klasse/Aussteller/Datum/Betrag) neu. Ab der ersten manuellen Eingabe gilt
   der Nutzer-Text und wird nicht mehr überschrieben (`…Manuell`-Muster wie beim Verzugsdatum).

## Sonderfall `sonstiges`

Für die Klasse `sonstiges` ist „Sonstiges" als Titel unbrauchbar. Stattdessen:

```
«Schreiben|E-Mail» vom «Schriftdatum ODER Eingangsdatum»
```

- **Label typ-abhängig:** „**E-Mail**", wenn das Dokument **selbst** eine E-Mail ist
  (E-Mail-Body — `payload_typ='text'` bzw. `textquelle='email_text'`), sonst „**Schreiben**".
  Ein **Anhang** einer E-Mail (eigenständiges Dokument mit `eltern_email`) ist bewusst ein
  „Schreiben", keine „E-Mail" — nur der Body selbst zählt als E-Mail (entspricht der
  Nutzerentscheidung: „E-Mail, wenn das Dokument eine E-Mail ist").
- **Datum mit Rückfall — nur hier:** Schriftdatum, wenn geparst; sonst **ausnahmsweise das
  Eingangsdatum** (`zustellungen.empfangen_am`). Diese Eingangsdatum-Ausnahme gilt **nur** für
  `sonstiges`; bei allen anderen Klassen bleibt Regel 4 (kein Eingangsdatum).
- Aussteller/Betrag: wie üblich nur wenn geparst; fehlen sie, fallen sie weg.

Beispiele:
- E-Mail ohne Schriftdatum, eingegangen 12.03.2026 → *„E-Mail vom 12.03.2026"*
- Gescanntes Schreiben mit Briefdatum 05.03.2026 → *„Schreiben vom 05.03.2026"*

## Beispiele (Regelfall)

| Klasse | Aussteller | Datum | Betrag | Vorschlag |
|---|---|---|---|---|
| rechnung | Autohaus Müller | 12.03.2026 | 1.234,56 € | Rechnung Autohaus Müller vom 12.03.2026 (1.234,56 €) |
| gutachten | — | 12.03.2026 | — | Gutachten vom 12.03.2026 |
| abrechnungsschreiben | Allianz | — | 8.500,00 € | Abrechnungsschreiben Allianz (8.500,00 €) |
| sonstiges (E-Mail) | — | — (Eingang 12.03.2026) | — | E-Mail vom 12.03.2026 |

## Datenfluss

**Review-Dialog (`ReviewQueueView.DetailPanel`):**
1. `hole_detail` liefert `bezeichnung_vorschlag` (berechnet) **und** `bezeichnung`
   (gespeichert, ggf. `null`).
2. Feld wird mit `bezeichnung` befüllt, falls gesetzt; sonst mit `bezeichnung_vorschlag`
   (lebendig).
3. Korrektur von Klasse/Feldern lädt das Detail neu → frischer Vorschlag, solange nicht
   manuell editiert. Erste manuelle Eingabe setzt ein `…Manuell`-Flag → kein Überschreiben.
4. Manuell editierte Bezeichnung wird über einen neuen Review-Endpoint nach
   `intake_dokumente.bezeichnung` persistiert (überlebt Verlassen/Zurückkehren).

**Freigabe (`post_freigabe` → `output_adapter.schreibe_dokument`):**
- Effektive Bezeichnung = `intake_dokumente.bezeichnung`, falls gesetzt; sonst der zum
  Freigabe-Zeitpunkt frisch berechnete Vorschlag.
- Wird nach `dokumente.bezeichnung` geschrieben.

**E-Akte (`DokumenteSection`):**
- Dokument wird mit `dokumente.bezeichnung` angezeigt (statt/neben dem Dateinamen).
- Nachträglich editierbar über einen Akten-Dokument-Editier-Endpoint.

## Datenmodell (Migration 59)

Nächste freie Migrationsnummer: **59** (aktuell höchste = 58).

- `intake_dokumente.bezeichnung TEXT NULL` — im Review bestätigter/editierter Text.
  **`NULL` = nie manuell angefasst** ⇒ es gilt der lebendige Vorschlag. Die Spalte ist damit
  zugleich das „manuell"-Flag serverseitig.
- `dokumente.bezeichnung TEXT NULL` — bei Freigabe geschrieben, in der E-Akte editierbar.

Migration additiv, nullable, idempotent, **explizite Commits**, **kein `executescript`**
(Klon-Muster der Migrationen 55–58). **Atomar in einem Edit** schreiben (bekannte
Flask-Reloader-Migrations-Falle — siehe Memory `feedback_migration_reloader_trap`).

## Registry-Ergänzungen

Zwei **optionale** Felder je Klassen-YAML (`backend/registry/klassen/*.yaml`), von
`registry_loader.py` akzeptiert; die bestehenden Pflichtfelder bleiben fail-loud:

1. **`label`** — sprechendes deutsches Klassen-Label (z. B. `sv_rechnung` → „SV-Rechnung",
   `pruefbericht` → „Prüfbericht"). Fehlt es, wird die rohe Klasse verwendet (kein Bruch).
2. **`bezeichnung_felder`** — Rollen-Mapping, welches geparste Feld die Rolle
   *aussteller* / *datum* / *betrag* spielt (z. B. rechnung:
   `{aussteller: rechnungssteller, datum: rechnungsdatum, betrag: gesamtbetrag}`).
   Nur diese drei Rollen. Fehlende Rolle oder leeres Feld ⇒ Teil fällt weg.

## Komponenten

**Backend:**
- **Neu** `backend/services/dokument_bezeichnung.py` — reine Funktion
  `baue_bezeichnung(klasse, felder, kontext, registry) -> str`.
  - `kontext`: was die Regel außerhalb der geparsten Felder braucht — `ist_email: bool` und
    `eingangsdatum` (nur für den `sonstiges`-Rückfall).
  - Kein DB-Zugriff. Datum → `TT.MM.JJJJ`; Betrag → bestehende `fmtEur`-Logik.
  - Whitespace-/Wörtchen-Bereinigung, sodass fehlende Teile keine „Löcher" hinterlassen
    (kein doppeltes „vom", keine leeren Klammern).
- `registry_loader.py` — optionale Felder `label`, `bezeichnung_felder` einlesen.
- `intake_routes.hole_detail` — `bezeichnung_vorschlag` + `bezeichnung` ausliefern.
- **Neuer Review-Endpoint** — speichert `intake_dokumente.bezeichnung`. Fällt unter die
  bestehende `INTAKE_REVIEW_PFLICHT`-Guard-Logik (schreibt nur in `intake_dokumente`, kein
  Akten-Write vor Freigabe → Guard `test_s19_intake_write_guard.py` bleibt grün).
- `post_freigabe` / `output_adapter.schreibe_dokument` — effektive Bezeichnung nach
  `dokumente.bezeichnung`.
- **E-Akte-Editier-Endpoint** — `dokumente.bezeichnung` nachträglich ändern.

**Frontend:**
- `ReviewQueueView.jsx` — Bezeichnungsfeld im `DetailPanel` (lebendiger Vorschlag bis
  manuelle Eingabe via `…Manuell`-Flag), Übergabe bei Freigabe; reine Helfer-Funktion für die
  Prefill-/Manuell-Logik (unit-testbar).
- `DokumenteSection.jsx` — Bezeichnung an der Dokument-Zeile anzeigen + inline editierbar.

## Tests (TDD)

- **Reine Funktion `baue_bezeichnung`** (Tabellenfälle): alle Teile vorhanden; einzelne Teile
  fehlen; unbekannte Klasse ohne Label (Fallback auf rohe Klasse); `sonstiges` als E-Mail vs.
  Schreiben; `sonstiges` Schriftdatum vs. Eingangsdatum-Rückfall; korrekte Wörtchen-/
  Klammer-Bereinigung.
- **Migration 59** — Guard/Idempotenz, beide Spalten vorhanden.
- **`hole_detail`** liefert `bezeichnung_vorschlag` + `bezeichnung`.
- **Freigabe** schreibt effektive Bezeichnung nach `dokumente.bezeichnung` (manuell gesetzt
  vs. Vorschlag-Fallback).
- **Review-Write-Guard** (`test_s19_intake_write_guard.py` / `test_s19d_e2e_no_intake_writes.py`)
  bleibt grün — neuer Review-Endpoint schreibt nur `intake_dokumente`.
- **Vitest** — Vorschlag-Prefill; manuelle Eingabe wird bei Reload nicht überschrieben;
  E-Akte-Inline-Edit.

## Bewusst außerhalb des Scopes (YAGNI)

- **LLM-Vorschlag** → PRD-38 (baut auf diesem Feld auf).
- **Per-Klasse-Templates** (Frage 2 = A: ein einheitliches Schema genügt; klassenspezifische
  Muster nur nachrüsten, falls sich einzelne Klassen als unpassend zeigen).
- **Längenbegrenzung/Kürzung** der Bezeichnung.
- **Rückfall auf E-Mail-Absender** als Aussteller (bewusst verworfen).
