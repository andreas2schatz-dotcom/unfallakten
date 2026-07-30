# Aktenanlage aus der ReviewQueue (PRD-NEW) — Design

Datum: 2026-07-30 · Status: freigegeben von RA Schatz (abschnittsweise, 2026-07-29/30)

## 1. Problem

Kommt ein Gutachten per E-Mail herein (Absender per Gutachter-Identifier bestätigt) und existieren Mandant und Unfall noch nicht im Bestand, gibt es heute keinen Weg weiter: Der Review-Eintrag zeigt „Keine Akten-Vorschläge", der Freigeben-Button bleibt gesperrt (Freigabe ohne `akte_az` → HTTP 422). Die Akte muss manuell in RA-MICRO angelegt werden, bevor das Dokument freigegeben werden kann. Das bestehende `NeueAkteModal` (Aktensuche) legt nur den SQLite-Schatten an und setzt voraus, dass die Akte in RA-MICRO schon existiert.

## 2. Lösungsidee (Kurzfassung)

Aktenanlage direkt aus der ReviewQueue: Ein Dialog sammelt die Mandats-/Unfalldaten (vorbefüllt aus dem geparsten Gutachten), erzeugt daraus eine **RA-MICRO-OMA-XML** (Onlinemandat, Muster: `beispieloma.xml` im Projekt-Root) und schreibt sie in einen **überwachten Ordner**. RA-MICRO liest die Datei selbstständig ein und legt die Akte vollautomatisch an. Das System erkennt die neue Akte anschließend per Read-Only-Abfrage der RA-MICRO-DB und schlägt das neue AZ am Review-Eintrag vor. Die Freigabe bleibt ein manueller Klick (INTAKE_REVIEW_PFLICHT: Review-Freigabe ist der einzige Schreibweg für Dokumente/Ereignisse).

Getroffene Grundentscheidungen:
- **XML-Weg:** überwachter Ordner, RA-MICRO importiert selbstständig; AZ-Rückweg über Read-Only-Erkennung in der RA-MICRO-DB.
- **Umfang:** ein gemeinsamer Dialog für beide Einstiege — aus der ReviewQueue (vorbefüllt) und „leer" aus der Aktensuche (ersetzt `NeueAkteModal`).
- **UI-Ansatz C:** alles inline in der ReviewQueue (Banner, Button, Status-Chip) plus schmale Status-Leiste oben in der Queue; **kein** eigener Navigationspunkt.
- **Dubletten-Check:** vor der Anlage Read-Only-Suche im RA-MICRO-Adressbestand (`tblAdressen`) über Name/Adressnummer.

## 3. Nutzerfluss

### 3.1 Vorschlag am Review-Eintrag
Erfüllt ein Eintrag alle drei Bedingungen —
1. Klasse = `gutachten`,
2. Absender per Gutachter-Identifier bestätigt (`absender_kategorie = "gutachter"` in `zustellungen.signale_json`),
3. keine Akten-Kandidaten aus dem Matching (`akten_kandidaten` leer)
— zeigt das Detail-Panel oben einen Hinweis-Banner: „🆕 Vermutlich neue Akte: Gutachten von <Absender>, kein Treffer im Bestand → Akte anlegen". Der Banner ist ein Vorschlag, keine Automatik.

### 3.2 Immer verfügbarer Button
Unabhängig vom Banner steht im Abschnitt „Akte zuordnen" (unter Kandidatenliste und Live-Suche) bei **jedem** Eintrag der Button „➕ Neue Akte anlegen" — für den Fall „ich bin mir sicher, das ist neu", auch wenn Kandidaten angezeigt werden.

### 3.3 Nach dem Anlegen
Der Dialog schreibt die XML in den überwachten Ordner und schließt sich. Der Review-Eintrag bleibt in der Queue und trägt den Status-Chip **„⏳ Aktenanlage läuft"**. Sobald das System die neue Akte in RA-MICRO erkennt, wechselt der Chip auf **„✅ Akte <AZ> angelegt"**, und das AZ ist im Zuordnen-Abschnitt vorausgewählt. Der Nutzer prüft und klickt „Freigeben" wie gewohnt.

### 3.4 Geschwister-Dokumente
Kommen mehrere Dokumente in einer E-Mail (Gutachten + Rechnung + Auftrag), gilt der AZ-Vorschlag nach Erkennung für **alle Einträge derselben E-Mail-Gruppe** (`zustellung_id` / `parent_zustellung_id`) — sie werden nacheinander auf dieselbe neue Akte freigegeben, ohne das AZ zu tippen.

### 3.5 Status-Leiste
Oben in der ReviewQueue erscheint — nur wenn Vorgänge existieren — eine schmale Leiste: „⏳ 1 Aktenanlage läuft · ✅ 1 Akte erkannt". Klick springt zum betroffenen Eintrag. Vorgänge ohne Intake-Dokument (leerer Einstieg) erscheinen ebenfalls hier („✅ Akte <AZ> angelegt — öffnen").

### 3.6 Leerer Einstieg
Der Button „+ Neue Akte" in der Aktensuche öffnet denselben Dialog ohne Vorbefüllung. Da kein Dokument freizugeben ist, legt das Backend bei Erkennung die Schattenakte direkt an (inkl. Unfalldaten) und setzt den Vorgang auf `akte_erkannt`; die Leiste bietet „öffnen" an. Erst der Klick auf „öffnen" (oder Abbrechen) setzt den Vorgang auf `abgeschlossen` — so verschwindet er nicht aus der Leiste, bevor der Nutzer ihn gesehen hat.

## 4. Aktenanlage-Dialog

Neue Komponente `AktenanlageDialog.jsx` (in `frontend/src/components/`), genutzt von ReviewQueueView und AktensucheView; ersetzt das bisherige `NeueAkteModal`.

Feldgruppen, angelehnt an die OMA-Struktur, vorbefüllt soweit das Gutachten-Parsing es hergibt:

| Gruppe | Felder | Pflicht | Vorbefüllung |
|---|---|---|---|
| **Mandant** | Anrede, Titel, Vorname, **Nachname**, Straße, PLZ, Ort, Telefon, E-Mail; einklappbar: Geburtsdatum, IBAN/Bank, Rechtsschutzversicherung + Versicherungsnummer | Nachname | Auftraggeber/Anspruchsteller aus dem Gutachten-Parse |
| **Unfall** | **Unfalldatum**, Unfallort, amtl. Kennzeichen | Unfalldatum | Gutachten-Parse |
| **Gegner** (optional) | Name, Adresse, Kennzeichen | — | Gutachten-Parse, falls vorhanden |
| **Gegnerische Versicherung** (optional) | Name, Schadennummer | — | Gutachten-Parse, falls vorhanden |
| **Gutachter** | Bezeichnung, Adresse, Gutachten-Nummer | — | Identifier-Treffer; Adresse via `ramicro_adressnr` aus `tblAdressen`, sonst Firmen-Stammdaten |

Buttons: **„Akte anlegen"** (erzeugt die XML) und „Abbrechen". Nach Erfolg kurze Bestätigung „XML geschrieben — RA-MICRO legt die Akte an", dann schließt der Dialog.

Hinweis Unfalldaten: Die OMA-XML hat kein eigenes Feld für Unfalldatum/-ort/Kennzeichen — diese gehen in das Freitext-Feld „Zusatzangaben" der XML. Unfalldatum und Unfallort werden zusätzlich beim Abschluss in die SQLite-Schattenakte übernommen (dort ist das Unfalldatum Pflicht). Das Kennzeichen wird in dieser Runde nur in die XML-Zusatzangaben geschrieben, sonst nirgends weiterverwendet.

### 4.1 Dubletten-Check (RA-MICRO-Adressbestand)
- Beim Öffnen (mit vorbefülltem Namen) und beim Tippen im Nachnamen-Feld (debounced) fragt der Dialog die Read-Only-Adresssuche ab (`ramicro/adress_service.suche_adressen`, `tblAdressen`) und zeigt Treffer: „⚠ Im Adressbestand gefunden: AdrNr <n> — <Name>, <Adresse>".
- Klick auf einen Treffer:
  1. **Akten-Check:** Der Dialog zeigt (via `tblAktenBeteiligte`), in welchen Akten die Person bereits Beteiligte ist. Gehört der Unfall zu einer davon → Anlage abbrechen, das AZ wird direkt in den Zuordnen-Abschnitt übernommen.
  2. **Gleiche Person, neuer Unfall:** Anlage läuft weiter; Adressfelder werden aus `tblAdressen` übernommen, die Adressnummer wird am Vorgang gespeichert.
- Ist die RA-MICRO-DB offline, meldet der Dialog „Adresssuche nicht verfügbar"; die Anlage bleibt möglich.

## 5. Technik

### 5.1 Neue Tabelle `aktenanlage_vorgaenge` (SQLite, nächste freie Migrationsnummer)
Spalten: `id` (PK), `intake_dokument_id` (nullable, FK `intake_dokumente`), `zustellung_id` (nullable, für die E-Mail-Gruppe), `status` CHECK(`laeuft` | `akte_erkannt` | `abgeschlossen` | `abgebrochen`), `formular_json` (die eingegebenen Daten), `xml_pfad`, `mandant_nachname`, `mandant_vorname`, `mandant_adressnr` (nullable), `erkanntes_az` (nullable), `angelegt_am`, `angelegt_von`, `erkannt_am` (nullable).

Migrations-Regeln beachten: kein `executescript()`, explizites `conn.commit()`, Migration atomar in einem Edit (siehe Feedback-Memories Migration-Bugs).

### 5.2 Neues Blueprint `aktenanlage_bp` (`/aktenanlage`)
- **`POST /aktenanlage`** — validiert das Formular (Pflicht: Mandant-Nachname, Unfalldatum), erzeugt die XML nach dem `beispieloma.xml`-Muster und schreibt sie **atomar** (Temp-Datei + Rename, damit RA-MICRO nie eine halb geschriebene Datei einliest) in den überwachten Ordner. Legt den Vorgang mit Status `laeuft` an. Guard: pro `intake_dokument_id` nur ein laufender Vorgang (sonst 409). Ist der Ordner nicht beschreibbar → Fehler, kein Vorgang, keine Datei.
- **`GET /aktenanlage/offen`** — liefert offene Vorgänge (für Leiste und Chips) und erledigt dabei die **Erkennung** (lazy, kein eigener Worker — die ReviewQueue pollt ohnehin alle 30 s): Für jeden laufenden Vorgang Read-Only-Abfrage, ob in RA-MICRO seit Vorgangsstart eine Akte angelegt wurde, deren Mandant passt (bevorzugt über `mandant_adressnr`, sonst Nachname; Join `tblAkten` ↔ `tblAktenBeteiligte` ↔ `tblAdressen`). Genau ein Treffer → `akte_erkannt` + `erkanntes_az`. Mehrere Treffer → keine Auto-Wahl, Status bleibt `laeuft`, die Treffer werden in der Antwort als Kandidaten mitgeliefert und im Zuordnen-Abschnitt angezeigt.
- **`POST /aktenanlage/<id>/abbrechen`** — Vorgang auf `abgebrochen`; die XML wird, falls noch vorhanden, aus dem Ordner gelöscht.
- **`GET /aktenanlage/adressen?q=`** — schlanke Route auf `suche_adressen()` für den Dubletten-Check (eigene Route statt Mitnutzung der SV-Portal-Route, um Kopplung zu vermeiden).

### 5.3 XML-Erzeugung
- Vorlage: Struktur aus `beispieloma.xml` (`<Onlinemandat>`, Rechtsangelegenheit `VERKEHRSUNFALL`, Mandantenliste, Gegnerliste, Beteiligtenliste mit Versicherung/Gutachter, Zusatzangaben-Freitext). Leere Elemente sind zulässig (das Beispiel enthält viele) — es wird das volle Gerüst geschrieben und nur Bekanntes befüllt; die `name`-Attribute sind Anzeigetexte und werden unverändert aus der Vorlage übernommen, ebenso das leere `<tvm/>`.
- Options-Werte spiegelbildlich zu den RA-MICRO-Adress-Konventionen (Entscheidung RA Schatz 2026-07-30): Anrede-Codes `1=Herr, 2=Frau, 4=Firma` (Mapping existiert in `word/abrechnungsuebersicht_service.py:_anrede_text`), in der XML als Großbuchstaben-Label `HERR`/`FRAU`/`FIRMA`. Datumsangaben im ISO-Format `JJJJ-MM-TT` (wie das Zustellungsdatum im Beispiel).
- Encoding UTF-8, korrektes XML-Escaping (Umlaute, `&`); Erzeugung über Stdlib (`xml.etree` bzw. Template) — Details im Implementierungsplan.
- Dateiname eindeutig: `onlinemandat_<JJJJMMTT-HHMMSS>_<nachname>.xml`.
- Zielordner aus `.env` (`OMA_EXPORT_PFAD`), als Volume in `docker-compose.yml` und `docker-compose.prod.yml` gemountet (Windows-Share, den RA-MICRO überwacht).

### 5.4 Abschluss und Schattenakte
- **Mit Intake-Dokument:** Der Vorgang gilt als abgeschlossen, sobald das erste Dokument seiner E-Mail-Gruppe freigegeben wird. Bei Freigabe auf das erkannte AZ greift der bestehende Mechanismus (`erstelle_oder_hole_akte`, BUG-08); zusätzlich werden Unfalldatum/Unfallort aus `formular_json` in die Schattenakte übernommen. Wird auf ein **anderes** AZ freigegeben, wird der Vorgang ebenfalls geschlossen und die UI weist darauf hin, dass die in RA-MICRO angelegte Akte bestehen bleibt (dort ggf. manuell stornieren).
- **Ohne Intake-Dokument (leerer Einstieg):** Bei Erkennung legt das Backend die Schattenakte direkt an (inkl. Unfalldaten), der Vorgang steht auf `akte_erkannt`; „öffnen" in der Leiste (oder Abbrechen) setzt ihn auf `abgeschlossen` (siehe 3.6).
- RA-MICRO bleibt strikt **read-only** — geschrieben wird ausschließlich die XML-Datei in den Ordner; das Anlegen macht RA-MICRO selbst.

### 5.5 Frontend-Änderungen (ReviewQueueView)
- Banner-Komponente (Heuristik aus 3.1), Button im Zuordnen-Abschnitt, Status-Chip am Queue-Eintrag, Status-Leiste über der Queue-Liste.
- Datenquelle: `GET /aktenanlage/offen`, abgefragt im bestehenden 30-s-Poll-Rhythmus der Queue.
- AktensucheView: „+ Neue Akte" öffnet den neuen Dialog; `NeueAkteModal` entfällt.

## 6. Fehlerbehandlung

| Fall | Verhalten |
|---|---|
| RA-MICRO legt nichts an (Ordner nicht überwacht, Import klemmt) | Vorgang bleibt `laeuft`; nach 15 Minuten Warn-Chip „⚠ Aktenanlage läuft ungewöhnlich lange — bitte in RA-MICRO prüfen". Auswege jederzeit: AZ manuell per Live-Suche zuordnen oder Vorgang abbrechen. Kein blockierender Zustand. |
| Erkennung mehrdeutig (mehrere passende neue Akten) | Keine Auto-Wahl; alle Treffer als Kandidaten im Zuordnen-Abschnitt, Nutzer entscheidet. Vorausgewähltes AZ ist nie erzwungen. |
| Ordner nicht beschreibbar / Share nicht gemountet | Sofortige klare Fehlermeldung im Dialog; kein Vorgang, keine halbe XML (atomares Schreiben). |
| RA-MICRO-DB offline | Dubletten-Check und Erkennung melden „nicht verfügbar"; Anlage funktioniert trotzdem (XML braucht keine DB), Erkennung holt nach. |
| Doppel-Anlage | Pro Review-Eintrag nur ein laufender Vorgang (Button wird zum Chip; Backend-Guard 409). Leerer Einstieg: Warnung bei laufendem Vorgang mit gleichem Nachnamen. |
| Review-Eintrag wird verworfen, während Vorgang läuft | Vorgang lebt unabhängig weiter und bleibt über die Status-Leiste erreichbar, bis erkannt oder abgebrochen. |
| Freigabe auf anderes AZ als das erkannte | Vorgang wird geschlossen; Hinweis, dass die RA-MICRO-Akte bestehen bleibt. |

## 7. Tests

- **Backend (pytest):**
  - XML-Generator: Golden-Datei gegen die `beispieloma.xml`-Struktur, Escaping (Umlaute, `&`), Pflichtfeld-Validierung.
  - Endpoints: Anlage legt Vorgang + Datei an; 409 bei Doppel-Vorgang; Abbrechen löscht die XML; Ordner-Fehlerfall.
  - Erkennungslogik mit gemockter RA-MICRO-Abfrage: eindeutig / mehrdeutig / kein Treffer / offline.
  - Freigabe-Integration: Unfalldatum/-ort landen in der Schattenakte, Vorgang wird abgeschlossen; Geschwister-Gruppe erhält AZ-Vorschlag.
- **Frontend (Vitest):** `ReviewQueueView.aktenanlage.test.jsx` im bestehenden Muster — Banner-Heuristik (nur Gutachten + Identifier + keine Kandidaten), Chip-Zustände, Status-Leiste, Dialog-Pflichtfelder, Dubletten-Trefferliste.
- **Manueller Abnahmetest am echten System:** erster XML-Import in RA-MICRO, inklusive Klärung der offenen Verifikationspunkte (Abschnitt 9).

## 8. Nicht-Ziele

- Kein Schreiben in die RA-MICRO-DB (read-only bleibt unangetastet).
- Keine automatische Freigabe von Dokumenten — die Review-Freigabe bleibt der einzige Schreibweg und ein manueller Klick.
- Kein eigener Navigationspunkt „Aktenanlage".
- Keine Übernahme des Kennzeichens über die XML-Zusatzangaben hinaus.
- Kein Batch-/Massenanlage-Modus.

## 9. Beim ersten echten Import zu verifizieren

1. **Adressnummer-Referenz:** Kann die OMA-XML über „Bekannt = Ja" (plus Mandanten-/Adressnummer) eine bestehende Adresse referenzieren, sodass RA-MICRO keine Adress-Dublette anlegt? Test beim Abnahmetest; falls nein, verhindert der Dubletten-Check nur die falsche Akten-Anlage, die Adress-Zusammenführung bleibt ein RA-MICRO-Handgriff.
2. **Konkreter Ordnerpfad:** `OMA_EXPORT_PFAD` (Windows-Share, den RA-MICRO überwacht) muss vor dem Rollout von RA Schatz benannt und in `.env` + Compose-Mounts eingetragen werden.
3. **Options-Labels und Datumsformat:** Bestätigen, dass `FRAU`/`FIRMA` als Anrede-Werte und das ISO-Datumsformat beim Import korrekt ankommen (das Beispiel zeigt nur `HERR` und mischt Datumsformate).
