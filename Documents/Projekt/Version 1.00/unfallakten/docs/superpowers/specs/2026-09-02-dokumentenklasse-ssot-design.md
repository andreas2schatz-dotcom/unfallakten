# Dokumentenklasse als alleinige Wahrheit — `dokumente.typ` entfällt

**Datum:** 2026-09-02
**Auslöser:** Bugmeldung RA Schatz — „Die Klassenzuordnung in der ReviewQueue überlebt den Übertrag zur DokumenteSection nicht. Da taucht fast alles als *Sonstiges* auf."
**Status:** Design abgestimmt, Umsetzung offen

---

## 1. Befund

### 1.1 Die Ursache

`dokumente` führt **zwei Spalten für dieselbe Tatsache**:

| Spalte | Herkunft | Wertebereich |
|---|---|---|
| `typ` | Ursprungsschema | 6 Werte, `CHECK`-Constraint in `backend/db/schema.py:213-216` |
| `dokumentenklasse` | Migration 24 (PRD-04) | 23 Registry-Klassen, kein Constraint |

Die Review-Freigabe schreibt ausschließlich `typ`. `backend/ramicro/output_adapter.py:28-32`:

```python
def _map_klasse(klasse):
    if klasse and klasse in GUELTIGE_TYPEN:
        return klasse
    return "sonstiges"
```

**17 der 23 Registry-Klassen fallen hier auf `sonstiges`.** Nur `gutachten`,
`abrechnungsschreiben`, `forderungsschreiben`, `sachstandsanfrage`, `klage` und
`sonstiges` überleben. `dokumentenklasse` wird dabei überhaupt nicht geschrieben
und bleibt `NULL`.

Die Anzeige liest (`frontend/src/sections/DokumenteSection.jsx:798`):

```jsx
value={d.dokumentenklasse || d.typ || "sonstiges"}
```

`NULL` → Rückfall auf `typ` → `"sonstiges"` → Label **„Sonstiges"**.

### 1.2 Belegt an der Produktivdatenbank

756 von 793 Dokumenten tragen `typ='sonstiges'`. Bei den Freigaben ab
2026-08 ist `dokumentenklasse` durchgehend `NULL` — außer bei den vier
Dokumenten, die nachträglich von Hand in der DokumenteSection umklassifiziert
wurden (das schreibt die Spalte).

Die Juli-Zeilen tragen eine Klasse, weil sie aus dem **E-Akte-Importweg**
stammen: `eakte_routes.py` ruft `dispatch_dokument()`, und der Dispatcher
schreibt `dokumentenklasse` korrekt. Daher der Eindruck, es habe einmal
funktioniert — es sind zwei verschiedene Wege.

### 1.3 Zweiter Datenverlust an derselben Stelle

`output_adapter.schreibe_dokument()` überträgt auch `parse_json`,
`parse_konfidenz` und `parse_status` nicht. Diese Felder liest:

- `backend/routers/belege_routes.py:574, 622, 822` — Beträge der Belegkandidaten
- `backend/routers/distanz_routes.py:328-336` — Volltext für die Entfernungsprüfung

Für freigegebene Dokumente laufen beide ins Leere.

### 1.4 Folgeschäden der leeren `dokumentenklasse`

`dokumentenklasse` ist kein Anzeigefeld, sondern Filterkriterium:

- `belege_routes.py:510-514`, `:970-974` — Belegkandidaten
- `klage_routes.py:688` — Verzugsdokumente für die Klage
- `DokumenteSection.jsx:99, 252, 761` — Gutachten-Sonderfunktionen,
  Rechnungserkennung, „offene Positionen" über `KLASSE_TO_POS`

---

## 2. Entscheidungen

| # | Entscheidung | Begründung |
|---|---|---|
| E-1 | **`dokumente.typ` wird ersatzlos entfernt.** `dokumentenklasse` ist die alleinige Wahrheit. | Zwei Spalten für eine Tatsache laufen zwangsläufig auseinander; das ist genau passiert. Entspricht dem Vorgehen bei der Dokumentenklassen-Registry (5 Quellen → 1). |
| E-2 | **Kein `CHECK`-Constraint auf `dokumentenklasse`.** Geprüft wird gegen die Registry beim Schreiben. | Ein Constraint erzwänge für jede neue Klasse eine Migration und bräche die Regel „neue Klasse = 1 YAML + Generator". |
| E-3 | **`parse_json` / `parse_konfidenz` / `parse_status` werden mit übertragen.** | Gleiche Funktion, gleicher Testaufbau — getrennt doppelte Arbeit. |
| E-4 | **ReviewQueue zeigt Labels statt technischer Schlüssel.** | Beide Ansichten sollen dieselbe Sprache sprechen. Die Labels stehen bereits in den Registry-YAMLs. |
| E-5 | **Keine Rücksicht auf das Stakeholder-Portal.** Die Vertragsänderung wird dokumentiert (Abschnitt 6), das Portal zieht RA Schatz separat nach. | Das Portal ist nicht live (RA Schatz, 2026-09-02). |

---

## 3. Betroffene Stellen — vollständige Erhebung

### 3.1 Schreiber (12)

| Stelle | heutiger Wert |
|---|---|
| `backend/email_import/import_service.py:326` | `"sonstiges"` |
| `backend/email_import/import_service.py:786` | `"gutachten" if "gutachten" in fn.lower() else "sonstiges"` (Dateinamen-Heuristik) |
| `backend/email_import/import_service.py:816` | `"sonstiges"` (.eml) |
| `backend/email_import/import_service.py:1193` | `"sonstiges"` (JSON) |
| `backend/pdf/upload_service.py:173` | Durchreichung vom Aufrufer, gegen `GUELTIGE_TYPEN` geprüft |
| `backend/ramicro/output_adapter.py:64, 85` | `_map_klasse()` — der Fehler |
| `backend/routers/belege_routes.py:755` | `"sonstiges"` |
| `backend/routers/eakte_routes.py:256` | `"sonstiges"` (Kommentar „Wird vom Dispatcher ueberschrieben" ist falsch — der Dispatcher schreibt nur `dokumentenklasse`) |
| `backend/routers/klage_routes.py:1453` | `"klage"` |
| `backend/routers/sta_routes.py:144` | `"sachstandsanfrage"` |
| `backend/routers/stellungnahme_routes.py:128` | `"sonstiges"` |
| `backend/scripts/seed_db.py:97` | `"gutachten"` |

### 3.2 Leser Backend

- `backend/services/sta_service.py:93, 121` — `typ='sachstandsanfrage'`
- `backend/services/abrechnung_vorschlag.py:121` — `d.typ='abrechnungsschreiben'`
- `backend/routers/dokumente_routes.py:396` — `typ=='gutachten'`
- `backend/routers/dokumente_routes.py:96-97` — API-Filter `?typ=`
- `backend/routers/akten_routes.py:163` — `_dokument_dict`, API-Ausgabe
- `backend/pdf/upload_service.py:367` — `_dok_dict`, API-Ausgabe
- `backend/models/dokument.py:193` — `hole_dokumente_by_akte(typ=…)`

### 3.3 Leser Frontend

- `frontend/src/config/utils.js:65`
- `frontend/src/sections/DokumenteSection.jsx:798`
- `frontend/src/sections/SchadenSection.jsx:265`
- `frontend/src/sections/RegulierungSection.jsx:303, 304, 306, 307, 1988, 1992`
  — Muster `d.dokumentenklasse === "x" || d.typ === "x"`. Der `typ`-Zweig für
  `"pruefbericht"` ist bereits tot (`pruefbericht` war nie in `GUELTIGE_TYPEN`).

### 3.4 Konstante

`GUELTIGE_TYPEN` in `backend/models/dokument.py:80`, importiert von
`upload_service.py:31`, `output_adapter.py:25`, `dokumente_routes.py:22`.

### 3.5 Tests

21 Backend-Testdateien und `frontend/src/config/utils.dokumentAnzeige.test.js`.
`backend/tests/test_output_adapter.py:98, 118, 136` zementiert das heutige
Mapping ausdrücklich, inklusive `test_unbekannte_klasse_mappt_auf_sonstiges` —
dieser Test beschreibt den Fehler als Sollverhalten und muss umgeschrieben werden.

### 3.6 Dokumentation

`docs/DATAMODEL.md:168` beschreibt Spalte und CHECK-Constraint.

---

## 4. Entwurf

### 4.1 Teil A — Kosmetik: eine Liste, eine Sprache

`GET /intake/klassen` (`backend/routers/intake_routes.py:600-611`) liefert
künftig Wert **und** Label aus der Registry:

```json
{"klassen": [{"wert": "sv_rechnung", "label": "SV-/Gutachterrechnung"}, ...]}
```

Das Label steht bereits in jeder `backend/registry/klassen/*.yaml` als
`label:` und ist dasselbe, das die DokumenteSection über
`dokumentenklassen.generated.js` anzeigt.

Die ReviewQueue zeigt es im Dropdown (`ReviewQueueView.jsx:1665-1666`), in der
Trefferliste (Z. 512, 2178) und im Freigabe-Dialog (Z. 1184).

`KLASSEN_FALLBACK` (`ReviewQueueView.jsx:24-33`) entfällt. Fällt der Endpoint
aus, ist ein leeres Dropdown mit Fehlerhinweis richtiger als eine stille
Achtel-Liste — dieselbe fail-loud-Regel wie bei den übrigen Registries.

Der Endpoint hat genau einen Konsumenten; die Formatänderung ist folgenlos.

### 4.2 Teil B — `typ` entfällt

**`backend/models/dokument.py`**

- `GUELTIGE_TYPEN` entfällt.
- `registriere_dokument()` nimmt `dokumentenklasse` statt `typ` und prüft
  gegen die Registry — unbekannte Klasse → `ValueError` (fail-loud).
- `Dokument.typ` entfällt aus der Dataclass.
- `hole_dokumente_by_akte(typ=…)` → `hole_dokumente_by_akte(klasse=…)`.

**`backend/ramicro/output_adapter.py`**

- `_map_klasse()` ersatzlos entfernt; die Intake-Klasse geht 1:1 durch.
- Zusätzlich werden `parse_json`, `parse_konfidenz` und `parse_status` aus
  `intake_dokumente` in die `dokumente`-Zeile übernommen (E-3).
  `intake_dokumente` führt `parse_json` und `konfidenz`; `parse_status` wird
  auf `'erfolgreich'` gesetzt, wenn `parse_json` vorliegt, sonst `'ausstehend'`.
- Der irreführende Modul-Docstring (Z. 12-16) wird berichtigt.

**Die zwölf Schreiber** übergeben ihre Registry-Klasse statt eines Typs.
Zuordnung im Einzelnen:

| Stelle | neue Klasse |
|---|---|
| `import_service.py:326, 816, 1193` | `"sonstiges"` |
| `import_service.py:786` | `"sonstiges"` — die Dateinamen-Heuristik entfällt (siehe 7.1) |
| `upload_service.py:173` | Durchreichung, Prüfung gegen Registry |
| `output_adapter.py:85` | `intake_dok["klasse"]` |
| `belege_routes.py:755`, `eakte_routes.py:256` | `"sonstiges"` (Dispatcher überschreibt danach) |
| `klage_routes.py:1453` | `"klage"` |
| `sta_routes.py:144` | `"sachstandsanfrage"` |
| `stellungnahme_routes.py:128` | `"sonstiges"` (siehe 7.2) |
| `seed_db.py:97` | `"gutachten"` |

**Die Leser** werden auf `dokumentenklasse` umgestellt; der API-Filter
`?typ=` heißt künftig `?klasse=`. `typ` verschwindet aus `_dokument_dict`
(`akten_routes.py:163`) und `_dok_dict` (`upload_service.py:367`).

**Frontend:** `d.dokumentenklasse || d.typ || "sonstiges"` → `d.dokumentenklasse`
an allen neun Stellen. Das tote „Dokumenttyp"-Dropdown im Upload-Dialog
(`DokumenteSection.jsx:1386`) entfällt: unter `INTAKE_REVIEW_PFLICHT` — aktiv,
geprüft — verwirft `dokumente_routes.py:143-175` den Wert ohnehin, die Klasse
wird in der Queue vergeben.

### 4.3 Migrationen 73 und 74

Bewusst **zwei** Migrationen statt einer: 73 füllt nach und ist nicht
destruktiv, 74 entfernt die Spalte. So bleibt jeder Zwischenstand des Umbaus
lauffähig — die Leser (4.2) arbeiten bereits auf einer gefüllten Spalte,
bevor die alte verschwindet. Wäre beides eine Migration, gäbe es einen
Zwischenstand, in dem die umgestellten Leser auf leere Werte greifen.

Am Datenbestand erprobt (SQLite 3.46.1, Kopie der Produktivdatenbank):
`ALTER TABLE … DROP COLUMN` genügt, **kein Tabellen-Rebuild**. Der Index muss
zuerst weg, sonst bricht die Anweisung ab:

```
error in index idx_dokumente_typ after drop column: no such column: typ
```

**Migration 73 — nachfüllen (nicht destruktiv):**

1. **Nachfüllen**, solange `typ` noch existiert:
   ```sql
   UPDATE dokumente SET dokumentenklasse = COALESCE(
       dokumentenklasse,
       (SELECT i.klasse FROM freigaben f
          JOIN intake_dokumente i ON i.id = f.intake_dokument_id
         WHERE f.dokument_id = dokumente.id
         ORDER BY f.id ASC LIMIT 1),
       typ)
   WHERE dokumentenklasse IS NULL;
   ```
   Wirkung im Bestand: 15 freigegebene Dokumente erhalten ihre echte Klasse,
   162 übernehmen ihren bisherigen Grobwert.

2. **Altwerte bereinigen**, die es in der Registry nicht gibt:
   - `gutachterrechnung` → `sv_rechnung` (1 Zeile; derselbe Sachverhalt,
     das Registry-Label lautet „SV-/Gutachterrechnung")
   - `versicherung` → `sonstiges` (2 Zeilen; ein BGH-Beschluss und ein
     Anschreiben, für die es keine Klasse gibt)

3. `CREATE INDEX IF NOT EXISTS idx_dok_klasse ON dokumente(dokumentenklasse)`
   — **notwendig, nicht optional.** `schema_manager.py:3721` legt diesen Index
   in Migration 24 an, in der aktiven Datenbank existiert er jedoch nicht
   (geprüft 2026-09-02, `schema_version` = 72; vorhanden sind nur
   `idx_dokumente_akte_id`, `idx_dokumente_typ`, `idx_dokumente_eakte_nr`) —
   mutmaßlich die bekannte Reloader-Falle. Mit dem Wegfall von
   `idx_dokumente_typ` stünde die Spalte sonst ganz ohne Index da, obwohl
   `belege_routes.py:510-514` und `:970-974` darauf filtern.

**Migration 74 — Spalte entfernen (destruktiv):**

4. `DROP INDEX IF EXISTS idx_dokumente_typ`
5. `ALTER TABLE dokumente DROP COLUMN typ`
6. `PRAGMA foreign_key_check` als Nachkontrolle

Beide Migrationen prüfen mit `PRAGMA table_info(dokumente)`, ob `typ` noch
existiert, und arbeiten sonst ohne diese Spalte. Das ist zwingend: `init_db()`
ist `create_schema()` + `run_migrations()`, auf einer **frischen** Datenbank
laufen also alle Migrationen der Reihe nach — und `schema.py` führt die Spalte
nach dem Umbau nicht mehr. Ohne die Prüfung liefe Migration 73 dort auf
`no such column: typ`.

Der `CHECK`-Constraint verschwindet mit der Spalte.

**Bekannter Vorbefund:** Die Datenbank trägt bereits zwei FK-Verletzungen
(`klassifikation_training` → `dokumente`, `aktivitaeten` → `unfallakte`).
Sie bestehen vor der Migration und sind nicht deren Folge. Die Nachkontrolle
in Schritt 6 muss auf **genau diese zwei** prüfen, nicht auf null, sonst
schlägt sie fälschlich an.

**Fallen bei der Migration** (aus früheren Sitzungen):

- Migration atomar in **einem** Edit schreiben — der Flask-Reloader greift
  sonst einen Zwischenstand ab und stempelt die Version, ohne die Spalte zu ändern.
- Niemals `executescript()`; `ALTER TABLE` braucht explizites `conn.commit()`
  davor und danach.
- Die aktive Datenbank liegt im Docker-Volume, nicht unter `backend/data/`.

---

## 5. Prüfweg

Testgetrieben, in dieser Reihenfolge:

1. **Roter Test zuerst** — Freigabe eines Intake-Dokuments mit
   `klasse='sv_rechnung'` führt zu `dokumente.dokumentenklasse == 'sv_rechnung'`
   und gefülltem `parse_json`. Schlägt heute fehl.
2. **Statischer Guard** — keine Codestelle liest oder schreibt noch
   `dokumente.typ`. Muster: `backend/tests/test_gen_dokumentenklassen_guard.py`.
   Muss die Fehltreffer `dateityp`, `ereignistyp`, `payload_typ`,
   `rechnungstyp`, `kuerzungstyp`, `fahrzeug_typ`, `frist_typ`, `schluss_typ`
   sowie den Gerichtstyp in `klage_routes.py:1920` (`"amts"`/`"land"`)
   ausschließen.
3. **Migrationstest** auf Frisch-Datenbank mit Altbestand: `NULL`-Klasse,
   Altwerte `gutachterrechnung`/`versicherung`, Freigabe mit Intake-Klasse.
4. **`test_output_adapter.py` umschreiben** — Z. 98/118/136 beschreiben heute
   den Fehler als Sollverhalten. `test_unbekannte_klasse_mappt_auf_sonstiges`
   wird ersetzt durch „unbekannte Klasse → `ValueError`".
5. **Vollsuite** als Netz: 2207 Tests, Stand 2026-09-02 grün. Die drei
   `typ`-Leser und das Model sind dort abgedeckt.

---

## 6. Vertragsänderung fürs Stakeholder-Portal

*Dieser Abschnitt ist die Übergabe an das Portal-Projekt
(`Projekt/Version 1.00/stakeholder-portal`). Das Portal ist nicht live; die
Änderung wird dort separat nachgezogen.*

### 6.1 Was sich am Sync-Payload ändert

`backend/services/portal_sync.py:136-139` liest heute:

```sql
SELECT id, typ, dateiname, hochgeladen_am
FROM dokumente WHERE akte_id = ? AND portal_sichtbar = 1
```

und liefert (Z. 163-166):

```json
"dokumente": [{"id": …, "typ": "sonstiges", "dateiname": …, "erstellt_am": …}]
```

**Neu:**

```json
"dokumente": [{
  "id": …,
  "klasse": "sv_rechnung",
  "klasse_label": "SV-/Gutachterrechnung",
  "dateiname": …,
  "erstellt_am": …
}]
```

Das Feld `typ` **entfällt ersatzlos**. `klasse` trägt den technischen
Registry-Schlüssel, `klasse_label` den Anzeigetext aus der Registry.

### 6.2 Wertebereich

Statt der bisherigen sechs Werte künftig die 23 Registry-Klassen:

```
abrechnungsschreiben · abschlepprechnung · arbeitsunfaehigkeitsbescheinigung
arztbericht · attest · forderungsschreiben · fragebogen · gutachten
kaufvertrag · klage · klagedrohung · krankenhausbericht · mahnschreiben
mietwagenrechnung · nachbesichtigung · pruefbericht · rechnung
reparaturrechnung · sachstandsanfrage · sonstiges · standkostenrechnung
sv_rechnung · verdienstausfall_nachweis
```

Die Liste kann wachsen — sie stammt aus `backend/registry/klassen/*.yaml`.
Das Portal darf sie **nicht** hart kodieren oder per `CHECK` einschränken,
sonst bricht der Sync bei jeder neuen Klasse. `klasse_label` mitliefern heißt
gerade, dass das Portal keine eigene Übersetzungstabelle pflegen muss.

### 6.3 Anzupassende Stellen im Portal

| Datei | Änderung |
|---|---|
| `src/lib/sync.ts:189-193` | `INSERT INTO dokumente (…, typ, …)` → `klasse`, `klasse_label`; `d.typ` → `d.klasse` |
| `src/lib/db.ts:106` | Spalte `typ TEXT NOT NULL` → `klasse TEXT NOT NULL` plus `klasse_label TEXT`; Migration für Bestandsdaten |
| `src/types/index.ts:111, 154` | `typ: string` → `klasse: string; klasse_label: string` |
| `src/app/(authed)/mandant/[az]/dokumente/page.tsx:20, 21` | Filter `d.typ !== "mandant_eingang"` → `d.klasse !== "mandant_eingang"` |
| `src/app/(authed)/mandant/[az]/dokumente/page.tsx:48` | Anzeige `{doc.typ}` → `{doc.klasse_label}` |
| `src/components/sv/DokumenteSection.tsx:18, 159` | dito |
| `src/app/api/dokumente/[id]/route.ts:18` | `SELECT … d.typ` → `d.klasse` |
| `src/app/api/upload/route.ts:117, 141, 162`, `src/app/api/sv/upload/[az]/route.ts:83` | portaleigene Uploads schreiben `'mandant_eingang'` in die neue Spalte |

### 6.4 Zwei Punkte, die dabei auffallen sollten

1. **Die Spalte ist ein Mischtopf.** Sie führt Kanzlei-Klassen aus dem Sync
   *und* den portaleigenen Wert `mandant_eingang`, der in keiner Registry steht.
   Das funktioniert, solange kein Registry-Schlüssel je `mandant_eingang`
   heißt. Sauberer wäre eine eigene Spalte `herkunft` (`kanzlei` /
   `mandant_eingang`) — Entscheidung liegt beim Portal-Projekt.
2. **Der Wert ist mandantensichtbar.** `page.tsx:48` und
   `sv/DokumenteSection.tsx:159` zeigen ihn Mandanten und Sachverständigen im
   Klartext. Deshalb `klasse_label` anzeigen, nie `klasse` — sonst steht dort
   „sv_rechnung" statt „SV-/Gutachterrechnung".

---

## 7. Nicht im Umfang

### 7.1 Dateinamen-Heuristik im E-Mail-Import

`import_service.py:786` rät die Klasse aus dem Dateinamen
(`"gutachten" if "gutachten" in fn.lower()`). Diese Heuristik entfällt mit der
Umstellung ersatzlos — klassifiziert wird im Intake. Eine echte
Nachklassifikation dieses Pfades ist eine eigene Aufgabe.

### 7.2 `stellungnahme_routes` ohne passende Klasse

`stellungnahme_routes.py:128` legt ein erzeugtes Dokument ab, für das es keine
Registry-Klasse gibt; es bekommt `sonstiges`. In
`POSITIONSMODELL-PLAN.md:159-160` bereits vermerkt. Eine Klasse
`stellungnahme` anzulegen ist eine eigene Entscheidung.

### 7.3 Unberührt

- Die Klassifikation selbst (Dispatcher, Parser, Registry-Inhalte)
- Ereignis- und Positionsmodell — bekommt seine Beträge bereits korrekt
- Der E-Akte-Importweg — schreibt `dokumentenklasse` schon richtig

---

## 8. Nach dem Ausrollen zu prüfen

Die Belege-Ansicht wird bei freigegebenen Dokumenten Kandidaten und Beträge
zeigen, die vorher unsichtbar waren. Das ist der Zweck der Änderung, verändert
aber sichtbar das Bild bei bekannten Akten. Nach dem Deploy an einer Akte
gemeinsam gegenprüfen.
