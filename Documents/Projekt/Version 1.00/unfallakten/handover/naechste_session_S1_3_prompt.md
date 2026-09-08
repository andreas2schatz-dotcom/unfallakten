# Prompt für nächste Session — S1.3 (Intake-Adapter)

Vorher: `/model` → Opus 4.7 (falls nicht schon Standard).

Danach den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen ein geplantes, freigegebenes Refactoring um. Branch: intake-stufe1
(bitte prüfen, dass er aktiv ist).

Lies zuerst vollständig: freigabe.md (verbindlich, übersteuert die Pläne),
PIPELINE-REFACTORING-PLAN.md, POSITIONSMODELL-PLAN.md (alle im Projekt-Root).
Die Planung ist abgeschlossen und freigegeben — kein erneutes Brainstorming,
keine Alternativvorschläge zur Architektur.

Nutze die Skills superpowers:executing-plans,
superpowers:test-driven-development und
superpowers:verification-before-completion.

Implementiere AUSSCHLIESSLICH Schritt S1.3 aus dem Pipeline-Plan
(Adapter-Schicht IMAP/Upload/E-Akte). S1.3 hat keinen K-Punkt-Zusatz
in freigabe.md — direkt nach Plan umsetzen.

Vorwissen aus S1.1 (bereits umgesetzt): Die Zustellungs-FK heißt
`zustellungen.intake_dokument_id` (nicht `dokument_id`), um Verwechslung
mit der Alt-Tabelle `dokumente` zu vermeiden. Details im Docstring von
`_run_migration_46` in `backend/db/schema_manager.py`.
Das Archiv-Modul `backend/intake/archiv.py` liefert die Funktionen
`lege_original_ab(bytes, ext)` und `erzeuge_arbeitskopie(pfad, quell_ext)`
für die neuen Adapter.

Regeln:
- Charakter des Schritts: S1.3 fasst bestehenden Code an (Doppelschreiben:
  Adapter-Aufrufe zusätzlich zum Alt-Pfad; UTF-16-BOM-Logik aus
  email_parser.py in den IMAP-Adapter umziehen).
- Der Alt-Pfad muss verhaltensgleich bleiben. Prüfstein: die 7 bestehenden
  E-Mail-Regressionstests bleiben grün.
- RA-MICRO strikt read-only. Docker/CIFS nicht anfassen.
- Testgetrieben arbeiten: Testkriterien aus dem Plan als pytest umsetzen
  (Test-E-Mail mit 2 Anhängen → 3 Zustellungen mit gemeinsamer parent_id
  + 3 Dokumente; identischer Anhang aus zweiter E-Mail → keine neue
  Dokument-Zeile, aber neue Zustellung).
- Regressionscheck am Ende: aktuelle Baseline auf intake-stufe1 ist
  327 passed / 274 failed / 22 errors / 2 skipped (Stand nach S1.1+S1.2).
  Bekannte Alt-Failures (P-01 aus docs/STATE.md) zählen nicht als
  Regression.
- Danach: Commit, docs/TODO.md-Eintrag „Aktueller Schritt" aktualisieren,
  dann STOPP — nächster Schritt (S1.4) erst nach meiner Abnahme.
```

---

## Für weitere Sessions

Denselben Prompt kannst du für S1.4 ff. wiederverwenden — anzupassen sind jeweils nur:
- **Schrittnummer** (S1.4 / S1.5 / P1.1 / …)
- **K-Punkt-Zusatz** aus freigabe.md Abschnitt 4 (z. B. bei P1.2: K-M1; bei S1.6a/b: K-P3; bei S1.8: K-2 + K-M2b; bei S1.9: K-P1)
- **Baseline-Zahlen** — nach jedem Schritt steigt der passed-Zähler; die aktuelle Zahl steht im letzten Session-Commit oder im TODO-Block
