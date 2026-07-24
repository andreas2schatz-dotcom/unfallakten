# Prompt für nächste Session — V11 Standardtexte (Klage-Wizard Paket 4)

Den folgenden Block kopieren und als Prompt einfügen:

---

```
Wir setzen V11 „Standardtexte pflegbar" um — das letzte Paket der
Klage-Wizard-Verbesserungsrunde. Das Design ist freigegeben (2026-07-19),
die Umsetzung hat bewusst auf Phase 1 der Kürzungstaxonomie gewartet und
kann jetzt starten.

Lies zuerst:
  * docs/TODO.md (Arbeitsliste)
  * docs/superpowers/specs/2026-07-19-klage-wizard-standardtexte-design.md
    (verbindliche Spec — kein erneutes Brainstorming, keine
    Architektur-Alternativen)

Vorgehen: Nutze superpowers:writing-plans, um aus der Spec einen
Implementierungsplan zu erstellen, und lege ihn mir zur Freigabe vor.
Erst nach Freigabe umsetzen (superpowers:executing-plans +
superpowers:test-driven-development). Neuer Feature-Branch von main.

Vorwissen aus Phase 1 Kürzungstaxonomie (in main, Stand a5a8c6a8 —
NICHT neu bauen, sondern wiederverwenden):
  * frontend/src/components/TextbausteinEditor.jsx — fertige
    Editor-Komponente (Platzhalter-Chips mit Cursor-Insert, 400-ms-
    Debounce-Vorschau, pruefePlatzhalter blockiert Speichern).
    Props-getrieben, frei von Kürzungs-Spezifika — V11 erbt sie
    unverändert. Integrations-Muster: views/KuerzungskatalogView.jsx.
  * Platzhalter-Infrastruktur Backend: PLATZHALTER_KATALOG +
    GET /kuerzungsarten/platzhalter + POST /kuerzungsarten/vorschau
    (routers/kuerzungsarten_routes.py); ersetze_platzhalter +
    genus_platzhalter/_GENUS_FORMEN (18 Genus-Formen) in
    word/stellungnahme_service.py. Falls V11 eigene Endpoints braucht:
    gleiche Semantik, Platzhalter-Syntax <GROSSBUCHSTABEN_MIT_UNTERSTRICH>.
  * FE-Spiegel frontend/src/sections/platzhalterLogik.js
    (ersetzePlatzhalter mit [FEHLT: <X>]-Marker, genusKontext via
    weiblich-Flag) — MUSS wortgleich zum Backend bleiben, Kommentar
    im Dateikopf beachten.
  * Klage-Einwände lösen Platzhalter bereits bei der Übernahme auf
    (EinwaendeAuswahl, Prop platzhalterKontext, KlageWizard reicht
    genusKontext(weiblich) durch).

Regeln:
  * RA-MICRO strikt read-only; nur SQLite als Schreibziel.
  * Git-Wurzel liegt im Home-Verzeichnis — NIE `git add -A`, immer
    Dateien einzeln adden.
  * Testgetrieben (RED → GREEN); die bestehenden
    KlageWizard.einwaende*-Tests müssen grün bleiben.
  * Test-Baseline lokal (Windows): Backend 204 bekannte Alt-Failures /
    1241 passed (ModuleNotFound-Cluster, KEINE Regression, Vergleichs-
    basis in docs/CHANGELOG.md) · Vitest 362/362 grün.
  * Migrationen: atomar in EINEM Edit schreiben, Container vorher
    stoppen (Reloader-Falle, docs/STATE.md).
  * Nach Abschluss: docs/TODO.md + docs/CHANGELOG.md nachführen,
    Commit-Protokoll wie bei Phase 1.
```
