# Design-Spec: Abschluss-/Sachstandsbericht an den Mandanten

Datum: 2026-08-05
Status: freigegeben (Brainstorming); Spec-Review mit Codebasis-Abgleich eingearbeitet (2026-08-05)

## 1. Ausgangslage

Am Ende (oder mitten in) eines Mandats soll der Mandant ein Schreiben erhalten,
das **gegenüberstellt, was gefordert und was gezahlt wurde — und wann**. Dasselbe
Gerüst soll auf Knopfdruck auch als **Sachstandsbericht** (Mandat läuft noch) und
als **Abschlussseite im Mandantenportal** dienen.

Der Kern existiert bereits: Der aktive Dokumenttyp `"abrechnungsuebersicht"`
(`backend/word/abrechnungsuebersicht_service.py`, verdrahtet in
`word_service.py:139`) erzeugt schon heute eine Mandanten-Übersicht mit den
Spalten *Schadenposition | Forderung | Regulierung | Offen*. Das ist faktisch
v1 dieser Idee. Es fehlen: die mandantengerechte Aufbereitung („was kommt bei
mir an"), die Anwaltskosten, ein kuratierter Abschluss-/Ausblick-Teil, der
Umschalter Abschluss↔Sachstand, der Bewertungs-Baustein und die Portal-Ausgabe.

Dies ist daher **kein Neubau, sondern die nächste Ausbaustufe** — mit maximaler
Wiederverwendung der bestehenden Rechen- und Stil-Bausteine.

**Vorgänger, der ersetzt wird (Codebasis-Abgleich 2026-08-05):**
`backend/word/abschluss_summary.py` („Das haben wir für Sie erreicht") wird heute
**automatisch** bei Statuswechsel auf `abgeschlossen` erzeugt
(`akten_routes.py:409`, `_erzeuge_abschluss_summary`) und als
`dokumente.typ='sonstiges'` mit `portal_sichtbar=1` abgelegt — ohne Hausstil,
ohne Netto/Brutto-Logik, ohne Key-Normalisierung. Entscheidung: **Auto-Trigger
entfernen, Modul löschen.** Der neue kuratierte Bericht ist der einzige
Abschluss fürs Mandantenauge; ein automatisch erzeugtes, unkuratiertes
Konkurrenzdokument darf nicht mehr entstehen.

## 2. Ziel

Ein **kanal-unabhängiges Übersichts-Objekt** je Akte, das zwei Renderer speist:
1. einen **DOCX-Brief** (Post, anwaltlich geprüft, Hausstil wie Forderungsschreiben),
2. eine **HTML-Abschlussseite im Mandantenportal** (später; siehe unten).

**Portal-Realität (Codebasis-Abgleich):** Das Portal wird per **Push-Sync**
beliefert (`services/portal_sync.py`: `_build_payload` → HMAC-signierter POST an
`PORTAL_API_URL`), nicht per Pull. Ein GET-Endpoint auf dem Kanzlei-Backend ist
für das Portal nicht erreichbar. Entscheidung: **In dieser Ausbaustufe wird nur
der kanzlei-interne GET-Endpoint gebaut** (für die Vorschau im Kurationsdialog);
die Portal-Auslieferung (Übersichts-Objekt ins Sync-Payload + Portal-UI) ist
Teil des Stakeholder-Portal-Teilprojekts (§15).

Das Objekt schaltet über **ein einziges anwaltlich kuratiertes Schlussfeld**
zwischen **Abschluss** und **Sachstand** um.

## 3. Nicht-Ziele (YAGNI)

- **Keine neue Erfassung von Zahlungsdaten.** Alles wird aus vorhandenen
  Strukturen abgeleitet (Positionsmodell, Abrechnungen, Gebührenassistent).
- **Kein automatischer Versand.** „Knopfdruck" erzeugt eine *Rohfassung* zum
  anwaltlichen Prüfen (wie Forderungsschreiben/Stellungnahme), kein PDF-Direktversand.
- **Kein hartes Abgleich-Gate.** Das System erfasst Zahlungen je Position bereits
  sauber; eine stille Plausi-Anzeige genügt (§11), kein blockierendes Subsystem.
- **Der schlichte Typ `"abrechnungsuebersicht"` bleibt bestehen** (schnelles
  Zwischen-Dokument). Der neue Bericht kommt additiv daneben (Entscheidung §4-①).

## 4. Entwurfsentscheidungen (im Brainstorming festgelegt)

| # | Frage | Entscheidung |
|---|---|---|
| Struktur | Endstand vs. Verlauf | **C — Hybrid:** Schlussbilanz oben, aufklappbarer Verlauf-Block darunter |
| „Für Sie" | volle Zahl vs. Mandantensicht | **A — zwei Blöcke:** „gesamt reguliert" *und* „davon direkt an Sie" |
| Anwaltskosten | zeigen? | **Ja**, mit RVG-Betrag beziffert („getragen von der Gegenseite, für Sie kostenfrei") |
| Schlussteil | Kuration | **A — Pflicht-Kurationsfeld** mit Bausteinen; zugleich der Abschluss↔Sachstand-Umschalter |
| Sachstand | Abweichung | **B — eigener Schwerpunkt-Block** „Woran wir arbeiten / worauf wir warten" mit Mini-Timeline |
| Ausgabe | Knopfdruck | **A — DOCX-Entwurf** wie andere Schreiben, anwaltlicher Prüfblick |
| Bewertung | Google-Link | **Bedingter Baustein** (nur bei voller Durchsetzung + „endgültig erledigt"), Portal-primär |
| Integration | andocken | **B — neuer Typ `abschlussbericht`**, geteilte Engine + Hausstil |
| Empfänger-Split | an Sie / an Dritte | **Konvention aus `abrechnungsart`** (§8), anwaltlich überschreibbar |

## 5. Bestehende Bausteine (Wiederverwendung — nichts neu bauen)

**Backend — Rechen-Engine (SSOT):** `backend/word/abrechnungsuebersicht_service.py`
- `_baue_pos_map(abrechnungen)` — summiert Zahlungs-Inkremente je `position_key`
  (Option B), inkl. Key-Normalisierung (`_normalise_key`, `sonstiges_wdm_N →
  extra_wdm_ssN`).
- `_schadenpositionen_rows(schaden, pos_map, vorsteuer)` — baut die Zeilen
  (`key, label, forderung, reguliert, ist_abzug`) inkl. Fahrzeugschaden-Logik.
- `_ermittle_abrechnungsart` → `models/schaden.py:berechne_abrechnungsart`
  (PRD-14-SSOT für fiktiv/konkret/totalschaden).

**Backend — Hausstil (SSOT):** `backend/word/styling.py`
- `fuege_briefkopf_ein`, `fuege_adressblock_ein` (rechtsbündig `Az.:`),
  `fuege_fusszeile_ein` (Az.), Farben `NAVY`/`GOLD`, Schrift `SCHRIFT_TEXT`
  (Calibri). Grußformel-Logik: „Mit freundlichen Grüßen" + Kanzleiname fett Navy.
- Einordnung (Abgleich): Es gibt zwei Stil-Welten. Die *aktive*
  Abrechnungsübersicht (`abrechnungsuebersicht_service.py`) rendert per
  Vorlagen-DOCX + OOXML-Injection; `styling.py` (python-docx) wird aktiv von
  `sachstandsanfrage.py` genutzt. Der neue Bericht geht den
  **python-docx/styling.py-Weg** (wie Sachstandsanfrage) — kein Vorlagen-DOCX.

**Backend — Gebühren (Abgleich präzisiert):** Der RVG-Betrag der
Geschäftsgebühr (Nr. 2300 VV RVG) kommt aus `berechne_rvg(streitwert, faktor)`
in `word/klage_service.py` (so nutzt es `gebuehren_routes.py:85-87`); der Faktor
ist `gebuehren_berechnung.faktor_final` (falls gespeichert), sonst
`berechne_faktor_vorschlag()` aus `services/gebuehren_service.py`. Streitwert
wie in `gebuehren_routes.py`: Summe `forderung_positionen`, Fallback
Hauptpositionen aus `schadenpositionen`.

**Backend — Ideenvorlage (schlummernd, nicht verdrahtet):**
`backend/word/abrechnungsuebersicht.py` enthält bereits Status-Badge
(`offen`/`abgeschlossen`/`klage`), Regulierungsverlauf-Tabelle (Datum +
Versicherung) und „Weiteres Vorgehen"-Absatz — als Muster nutzbar, nicht als Code.

**Frontend — Anzeige-Logik:** `frontend/src/sections/UebersichtSection.jsx`
- `RegulierungsTabelle` — Forderung × Reguliert × Kürzung je Position, inkl.
  `eintraege` je Zahlung (`{betrag, datum, versicherung, quelle}` = das „wann")
  und Fahrzeugschaden-Abrechnungsart. **Das ist die Verlaufs-/Bilanz-Anzeige.**
- `ForderungshistorieKarte` — je Forderungsschreiben (`apiForderungen.nachSchreiben`).
- `PositionsDashboard.jsx` — Ereignis-Modell (`GET /akten/<az>/positionen/status`,
  gefordert/anerkannt/offen). Sekundär; die Bilanz kommt aus der Regulierungsseite.

## 6. Architektur: ein Objekt, zwei Renderer

```
                ┌─────────────────────────────────────────┐
                │  services/abschluss_uebersicht.py        │
                │  baue_abschluss_uebersicht(akte_daten)   │  ← kanal-unabhängig
                │  → nutzt _baue_pos_map / _schadenpos_rows │
                │    / berechne_abrechnungsart / berechne_rvg│
                └───────────────┬─────────────────────────┘
                                │  Übersichts-Objekt (dict, §7)
                 ┌──────────────┴───────────────┐
                 ▼                               ▼
   word/abschlussbericht.py            GET /akten/<az>/abschluss-uebersicht
   (DOCX, styling.py-Hausstil)         (kanzlei-intern, login_erforderlich →
   Typ "abschlussbericht"               Vorschau im Kurationsdialog; später
                                        auch Quelle fürs portal_sync-Payload)
```

Die **Aufbereitung** lebt genau einmal in `services/abschluss_uebersicht.py`.
Beide Renderer sind „dumm": sie formatieren nur das fertige Objekt.

## 7. Das Übersichts-Objekt (Datenstruktur + Herkunft je Feld)

`baue_abschluss_uebersicht(akte_daten) -> dict`:

```
{
  "akte":    { az, unfalltag, unfallort, kz_mandant, kz_gegner,
               gegner_versicherung },              # aus akte + wdm_roh (wie _service.py)
  "mandant": { name, anschrift, plz_ort, anrede },  # aus mandant-Beteiligtem
  "modus":   "abschluss" | "sachstand",             # abgeleitet aus schluss.typ (§10)

  "positionen": [ {
      key, label, kategorie,                        # aus _schadenpositionen_rows
      gefordert,                                     # forderung
      gezahlt,                                        # reguliert (None = offen)
      differenz,                                      # gefordert − gezahlt
      kuerzung_grund,                                 # kuerzungsarten-Matching (falls vorhanden)
      empfaenger: "mandant" | "dritte",              # Konvention §8
      status: "voll" | "gekuerzt" | "offen" | "abzug",
      zahlungen: [ { datum, betrag, versicherung } ] # aus abrechnungen-eintraegen (das „wann")
  } ],

  "summen": { gefordert, gezahlt, differenz,
              an_mandant, an_dritte },               # an_* nach empfaenger aggregiert

  "anwaltskosten": { rvg_betrag,                     # berechne_rvg (klage_service, §5)
                     gezahlt_von_gegner,             # Σ ra_gebuehren-Zahlungen (s.u.)
                     getragen_von: "gegner"|"mandant"|"rsv" },

  "schluss": { typ, text, verjaehrung_datum?, naechste_schritte_text?,
               kuratiert_am, kuratiert_von },        # aus Tabelle abschluss_status (§10)

  "bewertung_cta": bool,                             # Bedingung §11.2
  "plausi": { zeilensumme, reguliert_gesamt, differenz_ok }  # stille Kontrolle §11.1
}
```

Erweiterung gegenüber `_baue_pos_map`: Die heutige pos_map summiert nur
`reguliert`. Für `zahlungen[]` (das „wann") wird — analog zu
`RegulierungsTabelle.posMap.eintraege` im Frontend — je Position die Liste der
Einzelzahlungen (`datum`, `betrag`, `versicherung`) mitgeführt. Das ist eine
additive Ergänzung in einer neuen Funktion (`_baue_pos_map_mit_verlauf`), die
`_baue_pos_map` nicht verändert.

**Feld-Herkunft (Abgleich verifiziert):** Alle nötigen Daten existieren bereits.
Je `Abrechnungsschreiben`: `datum`, `versicherung`, `haftungsquote`,
`gesamt_reguliert`. Je `RegulierungPosition`: `kuerzungsart_bezeichnung` /
`kuerzungsart_kategorie` (Kürzungstaxonomie-Join) + `kuerzung_freitext` →
speisen `kuerzung_grund` (Bezeichnung bevorzugt, sonst Freitext).
`word_service._lade_akte_daten` reicht das bereits als `abrechnungen`-Liste
durch — die Ladebedingung `if dok_typ == "abrechnungsuebersicht"`
(`word_service.py:274`) wird um den neuen Typ erweitert.

**Sonderregel RA-Gebühren (Entscheidung 2026-08-05):** Zahlungen mit Roh-Key
`ra_gebuehren` (heute via `_KEY_NORMALISE` → `sonstiges`) werden **vor** der
Key-Normalisierung abgefangen und **nicht** in `positionen[]` aufgenommen —
sie sind kein Schadenersatz „für Sie". Stattdessen fließen sie als
`anwaltskosten.gezahlt_von_gegner` in den Anwaltskosten-Block: angezeigt wird
bevorzugt der tatsächlich gezahlte Betrag, sonst der berechnete RVG-Betrag.

## 8. Empfänger-Split „an Sie / an Dritte" (Konvention, ohne neue Daten)

Ableitbar aus der bereits berechneten `abrechnungsart` — keine Erfassung nötig:

- **Fahrzeugschaden:**
  - `fiktiv` (rep_gutachten_netto) → **an Sie** (Mandant erhält die Gutachtensumme)
  - `konkret` (rep_rechnung) → **an Werkstatt** (Zahlung folgt der Rechnung)
  - `totalschaden` (WBW − Restwert) → **an Sie**
- **an Dritte:** `sv_kosten`, `mietwagenkosten`, `abschleppkosten`, `standkosten`
- **an Sie:** `wertminderung`, `nutzungsausfall`, `schmerzensgeld`,
  `unkostenpauschale`, `verdienstausfall`, `haushalt`, `anabmeldekosten`,
  `sonstiges`, `extra_*`

Umsetzung als Mapping `EMPFAENGER_KONVENTION` + Sonderfall Fahrzeugschaden nach
`abrechnungsart`. **Anwaltlich überschreibbar** (optionales Feld je Position im
Kurationsschritt; Default = Konvention). `an_mandant`/`an_dritte` sind reine
Summen dieser Zuordnung; „davon direkt an Sie" = `an_mandant`.

## 9. Dokument-Anatomie (mandantengerechte Reihenfolge)

Ein Gerüst, per `modus` umgeschaltet. Reihenfolge = absteigende Relevanz *für den
Mandanten*:

1. **Briefkopf + Az. + Betreff** (styling.py). Betreff schaltet um:
   „Abschluss Ihrer Schadenersatzangelegenheit …" ↔ „Sachstandsbericht zu …",
   Zusatz „Unser Zeichen: {az}".
2. **Ergebnis / Arbeitsstand** (Gold-Kachel).
   - *Abschluss:* „Für Sie durchgesetzt: {gezahlt} €" (vs. {gefordert} €).
   - *Sachstand:* Block „Woran wir arbeiten / worauf wir warten" (§4-B) mit
     Mini-Timeline (erledigt / offen / nächster Schritt aus `schluss.naechste_schritte_text`).
3. **Was davon bei Ihnen ankommt** (nur Abschluss): „gesamt reguliert {gezahlt}
   — davon direkt an Sie {an_mandant}"; Rest ging an Werkstatt/SV/Mietwagen (§8).
4. **Gegenüberstellung** *Position | gefordert | gezahlt | Differenz (+ Grund)*;
   offene Positionen im Sachstand als „noch offen". Darunter aufklappbarer
   **Verlauf** aus `positionen[].zahlungen` (Datum je Zahlung).
5. **Ihre Anwaltskosten:** „RVG {rvg_betrag} € — getragen von der Gegenseite,
   für Sie kostenfrei" (bzw. `getragen_von`).
6. **Schluss / Ausblick** (kuratiert, §10). Bei voller Durchsetzung + „endgültig":
   **Bewertungs-Baustein** (§11.2).
7. **Grußformel** (MfG + Kanzleiname Navy) + **Fußzeile mit Az.**

## 10. Kuriertes Schlussfeld + Umschalt-Logik

Neue SQLite-Tabelle `abschluss_status` (RA-MICRO bleibt read-only; **Migration
Nr. 67** — Stand nach Migration 66/Aktenanlage):

| Spalte | Typ | Bedeutung |
|---|---|---|
| `akte_az` | TEXT PK | Akte |
| `schluss_typ` | TEXT | `NULL`/`offen` · `endgueltig` · `vorbehalt_spaetfolgen` · `restposten` |
| `schluss_text` | TEXT | anwaltlicher Freitext / gewählter Baustein |
| `verjaehrung_datum` | TEXT | bei `vorbehalt_spaetfolgen` |
| `naechste_schritte_text` | TEXT | Sachstand-Block (§9-2) |
| `kuratiert_am` / `kuratiert_von` | TEXT | Audit |

**Umschalt-Regel:** `modus = "sachstand"` wenn `schluss_typ IS NULL OR
schluss_typ = 'offen'`, sonst `"abschluss"`. Damit ist *ein* Feld sowohl der
Haftungs-relevante Wertungspunkt als auch der Kanal-Umschalter.

Ohne bewusst gesetztes `schluss_typ ≠ offen` kann **kein** Dokument als
„Abschluss" generiert werden (nur Sachstand). Migration atomar in **einem** Edit
(Reloader-Falle, siehe `docs/STATE.md` / Memory `migration_reloader_trap`),
`ALTER`/`CREATE` mit explizitem `conn.commit()` (Memory `migration_executescript`).

## 11. Plausi-Kontrolle & Bedingungen

**11.1 Stille Bilanz-Kontrolle (nur Anzeige):** Vergleicht die
**positionsweise Zeilensumme** (`zeilensumme = Σ positionen.gezahlt`) gegen die
**Kopfsummen der Abrechnungen** (`reguliert_gesamt = Σ abrechnungen[].gesamt_reguliert`).
`plausi.differenz_ok = |zeilensumme − reguliert_gesamt| ≤ 0,01 €`. Weichen sie ab
(eine Zahlung wurde keiner Position zugeordnet), zeigt die erzeugende UI eine
weiche Warnung („Zeilensumme weicht vom regulierten Gesamtbetrag ab — bitte
prüfen"). **Kein** Block der Generierung.

**11.2 Bewertungs-Baustein `bewertung_cta`** ist `true` **nur** wenn *alle*
zutreffen:
- `modus == "abschluss"` und `schluss_typ == "endgueltig"`,
- `summen.differenz ≤ 0,01 €` (keine relevante Kürzung),
- Haftungsquote = 100 % — Quelle: **keine Abrechnung mit
  `haftungsquote < 100`** (je-Abrechnung-Feld ist aktueller als
  `unfallakte.haftungsquote`, das nur als Fallback dient, wenn keine
  Abrechnung erfasst ist),
- keine Position mit `status == "offen"`.

Rendering: Portal = klickbarer Button; DOCX = dezente Zeile + QR-Code.

## 12. Backend: neuer Typ `abschlussbericht`

- `services/abschluss_uebersicht.py` — `baue_abschluss_uebersicht(akte_daten)` (§7).
- `word/abschlussbericht.py` — `generiere_abschlussbericht(akte_daten) -> bytes`,
  nutzt `styling.py` + das Übersichts-Objekt.
- `word_service.py`: Typ in `_REINE_WORD_TYPEN` (`:55`, **zwingend** — sonst
  lehnt `gueltige_dok_typen()` ihn ab; er hat keine Registry-Klasse), Generator
  ins Dispatch-Dict (`:139`), Abrechnungs-Ladebedingung (`:274`) auf den neuen
  Typ erweitern; kein Ereignis-/Forderungs-Seiteneffekt (wie
  `abrechnungsuebersicht`, vgl. `:389`).
- `word_routes.py`: Docstring-Typenliste (`:42`) ergänzen (die Validierung
  selbst läuft über `gueltige_dok_typen()`).
- `GET /akten/<az>/abschluss-uebersicht` → Übersichts-Objekt als JSON,
  **kanzlei-intern** (`login_erforderlich`), read-only — speist die Vorschau im
  Kurationsdialog. Blueprint: `akten_routes.py` (dort liegen die übrigen
  Akten-GET-Routen; `portal_routes.py` ist Admin-/Sync-Verwaltung).
- `PUT /akten/<az>/abschluss-status` — Kurationsfeld speichern (Tabelle §10).
- **Rückbau:** `_erzeuge_abschluss_summary` + Aufruf (`akten_routes.py:409,521`)
  und `word/abschluss_summary.py` entfernen (§1).
- Empfänger = **Mandant** (`_empfaenger_mandant`-Muster aus `abrechnungsuebersicht.py`).

## 13. Frontend

- **Akte:** Button „Abschluss-/Sachstandsbericht" (bei den übrigen
  Schreiben-Buttons) → Kurationsdialog für `schluss_typ`/`text`/`verjaehrung`/
  `naechste_schritte` → DOCX-Download (bestehender Word-Flow).
- **Anzeige/Vorschau:** wiederverwendet `RegulierungsTabelle`; neue leichte
  `AbschlussVorschau` konsumiert das Übersichts-Objekt (Ergebnis-Kachel, Split,
  Anwaltskosten, Schlussblock). Kein Neubau der Tabelle.
- **Portal (separates Projekt Stakeholder-Portal):** Abschlussseite rendert das
  JSON-Objekt; Bewertungs-Button bei `bewertung_cta`.

## 14. Tests

- **Unit `baue_abschluss_uebersicht`:** fiktiv → Fahrzeug „an Sie"; konkret → „an
  Werkstatt"; totalschaden → „an Sie"; Kürzung erzeugt `differenz`+`grund`;
  mehrere Abrechnungen → `zahlungen[]` chronologisch; `modus` aus `schluss_typ`.
- **Bewertungs-CTA:** volle Durchsetzung + `endgueltig` → `true`; Kürzung/
  Teilhaftung/offene Position/Vorbehalt → jeweils `false`.
- **Plausi:** künstliche Zeilensummen-Abweichung → `differenz_ok = false`.
- **DOCX-Smoke:** `generiere_abschlussbericht` rendert fehlerfrei, enthält Az.,
  Grußformel-Kanzleizeile, Ergebnisbetrag; Sachstand-Variante ohne Ergebnis-Zahl.
- **RA-Gebühren-Filter:** `ra_gebuehren`-Zahlung erscheint nicht in
  `positionen[]`, sondern als `anwaltskosten.gezahlt_von_gegner`.
- **Migration-Guard:** `abschluss_status` existiert nach Migration (Spalten da).
- **Rückbau-Guard:** Statuswechsel auf `abgeschlossen` erzeugt **kein**
  Dokument mehr automatisch (alte Auto-Summary entfernt).

## 15. Offene Punkte / später

- **Portal-Anbindung** ist ein eigenes Teilprojekt (Stakeholder-Portal, Next.js).
  Konkreter Weg (Entscheidung 2026-08-05): Übersichts-Objekt in das
  **portal_sync-Payload** (`_build_payload()`) aufnehmen und im Portal rendern —
  das Portal pullt nicht (§2). In dieser Ausbaustufe wird dafür nichts gebaut.
- **`getragen_von` bei Teilhaftung/RSV:** v1 Default „gegner" bei Vollhaftung,
  sonst anwaltlich setzbar; feinere Kostenverteilung später.
- **Google-Bewertungs-Ziel-URL / QR** als Kanzlei-Einstellung hinterlegen.
- **Chronik-Ereignis** „Abschlussbericht versandt" optional ergänzen, wenn der
  Bericht als Meilenstein in der Aktenchronik erscheinen soll.
