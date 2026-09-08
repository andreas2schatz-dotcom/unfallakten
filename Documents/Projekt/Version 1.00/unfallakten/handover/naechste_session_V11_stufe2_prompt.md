# Prompt für nächste Session — V11 Stufe 2 (Standardtexte Kategorie C, vorflektierte Platzhalter)

Den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen V11 „Standardtexte pflegbar" Stufe 2 um: die ~24 grammatik-
abhängigen Bausteine (Kategorie C — alle Anträge, Sachverhalt-Kernsätze,
Aktivlegitimation, Einwände-Rahmensätze, SG-Kernsätze, Mithaftungssatz)
werden über vorflektierte Platzhalter pflegbar. Stufe 1 ist KOMPLETT:
in main gemergt (Stand 432b4fd4, 15 Commits ahead origin — Push-Status
prüfen), Playwright-E2E 24/24 bestanden.

Lies zuerst:
  * docs/TODO.md (Arbeitsliste; dort auch die 4 Stufe-2-Kickoff-Punkte
    aus dem Stufe-1-Abschluss-Review — die gehören mit in den Plan)
  * docs/superpowers/specs/2026-07-19-klage-wizard-standardtexte-design.md
    (verbindliche Spec, Abschnitt „Stufe 2"/vorflektierte Platzhalter —
    kein erneutes Brainstorming)
  * docs/superpowers/plans/2026-07-24-klage-wizard-standardtexte-v11-stufe1.md
    (eingecheckt; beschreibt die GESAMTE Infrastruktur, die Stufe 2 erbt)

Vorgehen: superpowers:writing-plans auf die Spec, Plan mir zur Freigabe
vorlegen. Erst nach Freigabe umsetzen (superpowers:subagent-driven-
development hat sich in Stufe 1 bewährt). Neuer Feature-Branch von main.

Infrastruktur aus Stufe 1 (NICHT neu bauen, nur erweitern):
  * backend/registry/klage_standardtexte.yaml — 44 Bausteine, Wurzel
    {platzhalter (23er-Katalog), bausteine}; Loader fail-loud:
    backend/services/standardtext_registry.py (lade_standardtexte,
    hole_texte_aufgeloest = Override vor Standard, ABSCHNITTE,
    Env-Override KLAGE_STANDARDTEXTE_PFAD).
  * DB: standardtext_override (Mig 65, baustein_key UNIQUE, kanzleiweit);
    Model backend/models/standardtext_override.py.
  * REST /klage-standardtexte (Liste/PUT 422+409/DELETE/vorschau/
    aufgeloest, routers/standardtexte_routes.py); Einstellungen-Tab
    „📄 Standardtexte" (views/StandardtexteTab.jsx, TextbausteinEditor).
  * klage_service.py: Helfer _st(key, kontext) in _baue_klage_dokument
    (ersetze_platzhalter aus stellungnahme_service, Syntax
    <GROSS_MIT_UNTERSTRICH>); 36 Stufe-1-Call-Sites als Muster.
    sg_text_builder.baue_sg_abschnitt(..., texte=None).
  * Wizard: KlageSection ist alleiniger Owner der standardtexte-Map
    (GET /aufgeloest), Prop-Drill an KlageWizard; Nach-Seed-Helfer
    berechneNachgezogeneStandardtexte; FE-Werteinsetzung via
    ersetzePlatzhalter (platzhalterLogik.js, wortgleich zum Backend —
    NICHT verändern).
  * Grammatik-Quellen für die vorflektierten Werte: _beklagten_grammatik
    (inkl. nom_gross/hat seit Stufe 1) + Kläger-Block kl_nom/kl_dat/
    kl_ist/kl_macht/kl_laesst… (klage_service.py ~955-975) — BE↔FE
    wortgleich mit beklagtenGrammatik/buildVorschauText (KlageWizard.jsx).
  * Golden-Parität: backend/tests/test_klage_standardtexte_golden.py,
    16 Fixtures, Neuaufnahme NUR via KLAGE_GOLDEN_UPDATE=1. Stufe 2 darf
    ohne Overrides NICHTS am Output ändern.

Verbliebene Kategorie-C-Stellen (Inventar-Anker):
  * klage_service.py: Anträge-Block ~1161-1283 (Kopfsatz, Antrag 1, SG-
    Anträge, Feststellungsanträge, RVG-Antrag; bek_gram/kl_dat/kl_dat3),
    Sachverhalt-Kernsätze ~1305-1408 (intro_satz, Beklagten-Sätze,
    Eigentümer-Satz), get_aktivlegitimation_text ~323-401,
    Mithaftung-eigen-Satz ~1673 (kl_nom/kl_laesst), Unfallhergang-BEWEIS
    „Parteivernahme…" (kl_art/kl_bez).
  * sg_text_builder.py: kl_nom-Kernsätze Zeilen ~61-74 und ~96-110.
  * KlageWizard.jsx: hq>=100-Alleinhaftungssatz (buildRwVorschau),
    buildVorschauText/buildSachverhaltText-Kernsätze,
    EINLEITUNGS_VARIANTEN (Einwände-Rahmensätze), baueAntraegeText.

Kickoff-Punkte aus dem Abschluss-Review (in den Plan aufnehmen):
  1. Verwaiste Overrides sichtbar machen (Warnung/„verwaist"-Anzeige +
     Lösch-Option) — vor etwaigen Key-Umbenennungen zwingend.
  2. Golden-Test: fehlende Golden-Datei muss FAILen statt still
     regenerieren.
  3. Sync-Test frontend/src/test/standardtexteFixture.js ↔ YAML
     (wortgleich, byte-genau).
  4. Standardtexte-Refresh in offener KlageSection nach Override-Änderung
     (aktuell fetch-once pro Mount).

Regeln:
  * RA-MICRO strikt read-only; nur SQLite als Schreibziel.
  * Git-Wurzel = Home — NIE git add -A, Dateien einzeln adden.
  * Testgetrieben (RED → GREEN); KlageWizard.einwaende*-Tests bleiben grün.
  * Test-Baseline lokal (Windows): Backend 204 bekannte Alt-Failures /
    1277 passed · Vitest 382/382 grün.
  * Migrationen: atomar, Container unfallakten-backend-dev vorher stoppen
    (Reloader-Falle, docs/STATE.md), kein executescript, Commits um DDL.
  * Neue Golden-/Fixture-Dateien: .gitattributes eol=lf im Verzeichnis
    (CRLF-Checkout-Falle, siehe backend/tests/golden/klage_standardtexte/).
  * Browser-E2E am Ende: Playwright liegt bereit (npm + pip); Muster-
    Skript livetest_v11.py im Scratchpad der Vorsession bzw. Vorgehen in
    docs/CHANGELOG.md (V11-Eintrag). Eigenheiten: Login-Maske ist im Dev
    vorbefüllt (einfach „Anmelden" klicken), Wizard-Stepper erlaubt kein
    Vorspringen (sequentiell „Weiter"), Gesamtvorschau erst nach Klick
    „Vorschau erzeugen"; Test-Overrides am Ende IMMER zurücksetzen.
  * Nach Abschluss: docs/TODO.md + docs/CHANGELOG.md nachführen,
    Commit-Protokoll wie bei Stufe 1 (Ledger ~/.superpowers/sdd/).
```
