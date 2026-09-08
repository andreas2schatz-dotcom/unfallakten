# Prompt für die nächste Session — Referenzwerkstatt + Entfernungsprüfung in der ReviewQueue (+ Intake-Restbefunde a/c)

> Zum Einfügen als Start-Prompt. Stand: 2026-08-07 nach Prüfbericht-Runde 2 (Commit `37673529` auf Branch `abschlussbericht`).

---

Wir setzen die Intake-Arbeit aus dem Befund Akte 1280/25 fort. Zuerst lesen:
`docs/TODO.md` (Backlog-Eintrag „Intake-Klassifikation/Extraktion — Restpunkte aus
Befund 1280/25") und `docs/CHANGELOG.md` Abschnitt „2026-08-06 — Prüfbericht-Extraktion
Akte 1280/25, Runde 2". Runde 2 ist fertig committet (`37673529`): Schema-Feld-
beschreibungen `{typ, beschreibung}` in der Klassen-Registry, 2 neue Validierungsregeln,
Prüfdienstleister-Fallback (nur Dokumentkopf 1500 Zeichen), Schadennummer-Regex mit
Leerzeichen-Tokens. Dok 516 (VHV-Prüfbericht) + 517 (VHV-Abrechnungsschreiben) liegen
reparsed und konsistent in `bereit_zur_review`.

Heutige Session hat 3 Arbeitspakete. Für Paket 1+2 sind die Design-Entscheidungen
mit RA Schatz bereits getroffen (2026-08-07) — direkt mit superpowers:writing-plans
bzw. Umsetzung starten, KEIN neues Brainstorming der Grundsatzfragen nötig:

## Paket 1 — Referenzwerkstatt-Extraktion (VHV-Blockformat)

Ziel: `felder.referenzwerkstatt` (Name + Straße + PLZ/Ort + genannte km) wird beim
Prüfbericht-Intake zuverlässig gefüllt. Ist-Zustand: Feld bleibt leer, weil der
Werkstatt-Block auf Seite 4/5 außerhalb des N-06-LLM-Seitenfensters liegt
(`waehle_extraktions_text`, backend/intake/pipeline.py).

ENTSCHIEDENER Weg: NICHT das LLM-Seitenfenster erweitern, sondern deterministisch —
den vorhandenen Regex-Parser `extrahiere_verweisbetrieb` in
`backend/services/werkstatt_service.py` um das VHV-Blockformat erweitern und in der
Intake-Extraktion (`backend/intake/extraktion.py`, analog zum
Prüfdienstleister-Fallback: nur Klasse `pruefbericht`, nur wenn LLM nichts liefert)
als Füller für `felder.referenzwerkstatt` aufrufen.

VHV-Blockformat im echten Text (Dok 516, `parse_json.text_gesamt` in
`intake_dokumente`, DB `/app/data/unfallakten.db` im Container `unfallakten-backend-dev`):

```
Für die Korrekturberechnung haben wir den Reparaturbetrieb

Möser Arno - Karosseriefachbetrieb
Philipp-Reis-Straße 9
63128 Dietzenbach
Telefon: 06074-25936
Web: www.kbmoeser.de
Reparaturkosten (Netto): 5448,62 EUR
Lohn Mechanik: 130,00 EUR/Stunde
...
Entfernungskilometer: 16,00 km
Garantieleistung: 5-5 Jahre
berücksichtigt.
```

BEKANNTER BUG dabei mitfixen: `extrahiere_verweisbetrieb` feuert auf dem VHV-Text
aktuell auf den Floskel-Satz „Wird eine Referenzwerkstatt benannt, berücksichtigen
wir …" und liefert diesen Satz als `name` zurück (quelle `triggerkontext`, Adresse
leer) — verifiziert am 2026-08-07. Der Trigger-Kontext-Fallback braucht eine
Plausibilitätsbremse (z. B. kein Treffer ohne PLZ-Zeile).

Hinweis: Das Dokument nennt 3 Betriebe (Möser=verwendet für Korrekturberechnung,
Rauch, Wießner & Schroth als Alternativen). Maßgeblich ist der VERWENDETE Betrieb
(steht nach „Für die Korrekturberechnung haben wir den Reparaturbetrieb").

## Paket 2 — Entfernungsprüfung in der ReviewQueue (Button + Popup)

ENTSCHIEDEN (RA Schatz, 2026-08-07):
- Auslöser: manueller Button „Entfernung prüfen" im Review-Detail bei Klasse
  `pruefbericht` (KEINE Auto-Prüfung — Mandanten-Adresse geht an externen Dienst
  OpenRouteService, nur auf Klick; `ORS_APIKEY` ist im Dev-Container gesetzt, geprüft).
- Ergebnis: Popup (genannte km vs. echte km + Bewertung/Textbaustein) UND speichern —
  Ergebnis in `felder.referenzwerkstatt` ablegen (z. B. `km_echt`, `bewertung`),
  damit es bei der Freigabe dauerhaft in parse_json/Akte wandert. Spätere Nutzung im
  Stellungnahme-/Kürzungs-Workflow ausdrücklich gewünscht, aber NICHT Teil dieser Runde.

Vorhandene Infrastruktur (heute nur von der praktisch ungenutzten alten
RegulierungSection aufgerufen):
- `backend/routers/distanz_routes.py`: `POST /distanz/prüfen`
  (mandant_adresse, werkstatt_adresse, werkstatt_name, km_genannt),
  `/distanz/prüfen-aus-dokument` (arbeitet mit Alt-Tabellen `dokumente`/
  `pruefberichte`, NICHT mit `intake_dokumente` — vermutlich neuer schlanker
  Endpoint oder Erweiterung nötig, z. B. `POST /intake/dokument/<id>/entfernung`).
- `backend/services/werkstatt_service.py`: `pruefe_entfernung()` (Geocoding +
  Routing via ORS, liefert km_echt, Bewertung, Textbaustein), `_mandant_adresse()`
  -Muster in distanz_routes (liest Mandant aus Beteiligten der Akte).
- Frontend-Nutzungsbeispiele: `frontend/src/sections/RegulierungSection.jsx`
  (apiDistanz in `frontend/src/api.js`).

Zu klärender Punkt in der Umsetzung: In der ReviewQueue ist die Akte noch nicht
verbindlich zugeordnet (akten_kandidaten, `akte_az` erst bei Freigabe) — die
Mandanten-Adresse muss aus dem im Review AUSGEWÄHLTEN Akten-Kandidaten kommen;
ohne Auswahl Button deaktivieren + Hinweis.

## Paket 3 — Intake-Restbefunde (a) + (c)

- (a) Marker-Wortgrenze: Klassifikations-Marker „Rechnung" trifft als Teilwort
  „**Ab**rechnung" → Auto-Vorschlag stufte Dok 517 als `rechnung` ein. Fix:
  Wortgrenzen-Matching im Marker-Vergleich (`backend/intake/klassifikator.py`),
  vgl. Gutachten-Parser-Lektion (\b, Memory `feedback_gutachten_parser_debugging`).
  Achtung Nebenwirkungen: Marker wie „HDI Global"/„VHV Allgemeine" (Mehrwort) und
  „Control€xpert" (Sonderzeichen) dürfen nicht kaputtgehen — Golden-Tests
  `test_registry_golden.py` + `test_s16b_klassifikation_e2e.py` laufen lassen.
- (c) Datums-Scheinkonflikt: `llm_konflikt` meldet schreibdatum „2026-04-28" (LLM)
  vs. „28.04.2026" (Regex) als Konflikt, obwohl derselbe Tag. Fix: im
  Konflikt-Vergleich von `backend/intake/extraktion.py` (extrahiere_felder,
  Konflikt-Schleife) beide Werte vor Vergleich auf ISO normalisieren (nur für
  Datums-Muster DD.MM.YYYY ↔ YYYY-MM-DD). Sichtbar an Dok 517.

## Arbeitsregeln

TDD strikt (superpowers:test-driven-development — RED vor GREEN, echte Suiten im
Container: `docker exec unfallakten-backend-dev python -m pytest backend/tests/... -q`).
Registry-YAMLs werden NUR beim Backend-Start geladen → nach YAML-Änderung
`docker restart unfallakten-backend-dev`. Reparse zum Verifizieren am echten Dokument:

```
docker exec unfallakten-backend-dev python -c "
import sys; sys.path.insert(0, '/app')
from backend.intake.queue import enqueue
from backend.intake.pipeline import verarbeite_dokument
enqueue(516); print(verarbeite_dokument(516))"
```

Vorbestehende Failures (NICHT von uns, nicht fixen ohne Auftrag): 2×
`test_intake_routes` Bezeichnungs-Label „Rechnung (Auffang)"; `test_modul7`
(gelöschtes Modul email_import.parser). Git-Wurzel ist das Home-Verzeichnis —
NIE `git add -A`, immer Dateien einzeln stagen. Branch-Lage: Arbeit bisher auf
`abschlussbericht` (stapelt auf `intake-review-sichtbarkeit`, beide NICHT gemergt);
neue Arbeit dort fortsetzen, Merge-Strategie siehe TODO „In Arbeit".
RA-MICRO read-only. Zielsprache Deutsch, RA Schatz ist nicht-technisch.

Reihenfolge-Empfehlung: Paket 1 → 2 (baut aufeinander), Paket 3 unabhängig
(bei Zeitknappheit vorziehen, ist klein). Am Ende: CHANGELOG/TODO nachführen,
Browser-Abnahme des Popups durch RA Schatz einplanen.
