# Nächste Session — Fragebogen-Feld-Übernahme bei Freigabe

Stand: 2026-07-14 · Branch `intake-stufe1` · **frische Session, als Nächstes**

## Aufgabe (in Klartext)

Wenn ein **Unfallbogen/Fragebogen** in der Review-Queue **freigegeben** wird,
sollen die bereits geparsten Felder (Mandant, Gegner, Unfalldetails,
Personenschaden) tatsächlich **in die Akte übernommen** werden. Heute landet
der Unfallbogen zwar als Text-Dokument in der Review-Queue (BUG-01), aber die
Freigabe schreibt die Fragebogen-Felder **nicht** in die Akten-Tabellen — der
Sachbearbeiter muss sie manuell nacherfassen. Das ist der direkte
Alltagsnutzen.

## Warum das offen ist (Kontext)

- **BUG-01** hat den Unfallbogen verlustfrei in die Review-Queue gebracht
  (`_fragebogen_in_intake_queue()` in `backend/email_import/import_service.py`),
  als Text-`intake_dokument` + `zustellung` (Signal `az`).
  **Entscheidung RA Schatz:** „erst in Review-Queue zur Freigabe", NICHT
  Auto-Übernahme.
- Die **Feld-Übernahme beim Freigeben** wurde bewusst als eigenes Feature
  ausgeklammert — das ist genau diese Aufgabe.
- Unter S1.9d wurde das frühere Auto-Enrichment stillgelegt: die vier
  Funktionen `_ergaenze_mandant` / `_ergaenze_gegner` / `_ergaenze_unfalldetails`
  / `_ergaenze_personenschaden` (in `import_service.py`) schreiben unter
  `INTAKE_REVIEW_PFLICHT=True` **nichts** mehr. Ihre Feld→Tabelle-Logik ist aber
  vorhanden und ist der natürliche Kandidat, jetzt **beim Freigeben** (statt
  automatisch) ausgelöst zu werden.

## Verbindliche Leitplanken (nicht verhandeln)

- **Menschliche Freigabe ist die EINZIGE Schreiboperation Richtung Akte.**
  Diese Aufgabe fügt genau dort einen Schreibweg hinzu — passt zum Prinzip.
- **RA-MICRO read-only** — nur SQLite schreiben.
- Alt-Pfade unter `INTAKE_REVIEW_PFLICHT=false` unangetastet lassen.
- TDD, keine unnötigen Abstraktionen, Deutsch.

## Grounded Andockpunkte (2026-07-14 verifiziert)

- **Freigabe-Endpoint:** `post_freigabe` in `backend/routers/intake_routes.py`
  (schreibt heute via `output_adapter` + Ereignisse; hier müsste die
  Fragebogen-Übernahme andocken, wenn `klasse`/Signal = Unfallbogen).
- **Feld→Tabelle-Logik (wiederverwenden):** `_ergaenze_*` +
  `_speichere_fragebogen_json` in `backend/email_import/import_service.py`.
- **Parser + Datenquelle:** `backend/email_import/fragebogen_parser.py`,
  DB-Tabelle `fragebogen_erstkontakt` (PRD-22c). Prüfen, ob die geparsten
  Felder am `intake_dokument` (`parse_json`/`structured_payload`) oder in
  `fragebogen_erstkontakt` liegen und welche Quelle beim Freigeben gilt.
- **Guard:** `test_s19_intake_write_guard.py` (AST-Whitelist der erlaubten
  Direkt-Schreiber) — bei neuem legitimen Schreibweg mitpflegen.
- **E2E-Referenz:** `test_s19d_e2e_no_intake_writes.py` (dokumentiert, dass
  heute NICHTS geschrieben wird — dieser Test bzw. eine Variante muss die neue
  gewollte Schreibung sauber abgrenzen).

## Zu klärende Fragen (im Brainstorming)

- Woran wird ein Fragebogen-Dokument im Freigabe-Dialog erkannt (Klasse?
  Signal? payload_typ='text' + Herkunft)?
- Übernahme vollautomatisch bei Freigabe, oder editierbare Vorschau im
  Freigabe-Dialog (der Anwalt bestätigt/korrigiert die Felder vor dem
  Schreiben)? — voraussichtlich die entscheidende UX-Frage.
- Verhalten bei bereits befüllter Akte (Überschreiben vs. nur Leerfelder
  füllen)?
- Neue Akte vs. bestehende Akte (Onboarding-Berührung mit PRD-NEW?).

## Vorgehen

**Mit `superpowers:brainstorming` starten** (Design + offene Fragen klären),
dann Spec → Plan → TDD-Umsetzung (Subagent-Driven bewährt). NICHT direkt in
Code springen.

## SDD-Lehren aus N-04 (beachten)

- Implementer-Subagenten explizit anweisen: **Tests im Vordergrund laufen,
  erst committen, dann melden** (ein Agent hing sonst in einer
  Hintergrund-Test-Warteschleife).
- Nach **Signaturänderungen** an gemeinsam genutzten Funktionen die **volle**
  Testsuite laufen lassen, nicht nur den Golden-Teil (ein Alt-Test mit
  veraltetem Mock war sonst latent gebrochen und vom Teil-Lauf verdeckt).
