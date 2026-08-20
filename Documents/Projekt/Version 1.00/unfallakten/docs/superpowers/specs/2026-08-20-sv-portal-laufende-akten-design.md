# Design: SV-Portal für Sachverständige nutzbar machen

**Datum:** 2026-08-20
**Status:** Approved
**Projekt:** Unfallakten-Verwaltungssystem · Koch, Schatz & Kollegen
**Anlass:** Erster echter SV-Portal-Zugang (KFZ-Sachverständigenbüro Ninnivaggi, RA-MICRO-Adressnr. 25982)

---

## 1. Ausgangslage

Der erste Portal-Zugang für einen Sachverständigen soll in Betrieb gehen. Die Bestandsaufnahme am 2026-08-20 ergab, dass die Kette von der Freigabe in den Einstellungen bis zur Anzeige beim Sachverständigen an fünf Stellen unterbrochen ist (D-1 bis D-5). Ein sechster Befund (D-6) betrifft das Portal nicht, fiel aber bei der Vorarbeit an.

**Mengengerüst Ninnivaggi** (RA-MICRO, `iAdressnummer = 25982`, Beteiligtenkennzeichen `SV%`, nicht deaktiviert):

| | Akten |
|---|---|
| gesamt | 578 |
| abgelegt (`iAblageNummer > 0`) | 467 |
| **laufend** | **111** |

Nach Jahrgang: 2026: 49 (40 laufend) · 2025: 210 (45) · 2024: 163 (17) · 2023: 91 (6) · 2022: 52 (2) · 2021: 13 (1).

**Was bereits vorhanden ist und bleibt:**

- Einstellungen-Reiter „SV-Portal" mit SV-Liste, Aktenliste je SV und Freigabeschalter je Akte (`unfallakte.portal_aktiv`).
- Im Portal (`stakeholder-portal`, Next.js) das SV-Cockpit: ab zehn Akten Cockpitmodus, Aktenliste mit Suchfeld und den Filter-Chips **Laufend | Abgeschlossen | Alle**, Voreinstellung „Laufend" (`src/lib/sv-akten-filter.ts`, `src/components/sv/AktenFilter.tsx`).

Der gewünschte Anzeigemodus ist also gebaut. Er greift nur ins Leere, weil die Daten fehlen, auf die er sich stützt.

**Kernbefund 1:** Der Filter unterscheidet über `akten.status = 'abgeschlossen'`. Im Kanzlei-System stehen 844 von 861 Akten auf `offen`; abgelegte RA-MICRO-Akten werden nirgends als abgeschlossen erkannt. Alle freigegebenen Akten landeten damit unter „Laufend".

**Kernbefund 2:** Die Zuordnung „Akte gehört diesem Sachverständigen" existiert im Kanzlei-System nicht. Die Tabelle `beteiligte` enthält genau einen Eintrag mit `rolle = 'sachverstaendiger'` (DEKRA); keine der 111 laufenden Akten hat einen SV-Beteiligten. Die Zuordnung steht ausschließlich in RA-MICRO. Deshalb zeigt die SV-Liste in den Einstellungen auch „0 Akten" — sie zählt über `beteiligte.email`.

**Vorarbeit** (bereits ausgeführt, 2026-08-20): Der Knopf „alle aktivieren" hatte 545 leere Akten-Hüllen angelegt. Davon wurden 537 gelöscht, 8 mit anhängenden Dokumenten behalten und stillgelegt; alle 578 Ninnivaggi-Akten stehen wieder auf `portal_aktiv = 0`. Backup: `/app/data/unfallakten.db.bak_pre_svportal_cleanup_20260820`.

---

## 2. Entscheidungen (RA Schatz, 2026-08-20)

| # | Frage | Entscheidung | Begründung |
|---|---|---|---|
| E-1 | Umfang der Freischaltung | Alle 578 Akten gehen ins Portal, mit korrektem Ablage-Status | Der Sachverständige klappt Abgeschlossenes selbst über den Chip auf und findet Altakten ohne Rückfrage in der Kanzlei |
| E-2 | Reichweite des Ablage-Status | Setzt auch den Aktenstatus im Kanzlei-System | Räumt die 844 falschen „offen"-Einträge auf; Wirkung auf eigene Ansichten wird über einen Vorschaulauf abgesichert |
| E-3 | Zuschnitt | Datenseite; Abnahme lokal per Impersonate | Das Portal ist noch nicht veröffentlicht (`portal.anwalt-offenbach.de` löst nicht auf, läuft nur auf `localhost:3002`). Veröffentlichung ist ein eigenes Vorhaben |
| E-4 | Beschriftung der Akten | RA-MICRO-Kurzbezeichnung („Türe/Taskoparan") | Für alle 578 Akten vorhanden, sofort wiedererkennbar; ein Kennzeichen führt RA-MICRO bei keiner dieser Akten |
| E-5 | Rolle des Freigabeschalters | Ausnahme-Sperre: grundsätzlich frei, gezielt sperrbar | Kein Nachpflegen bei neuen Akten; die Sperre bleibt für Streitfälle (etwa über sein eigenes Honorar) |
| E-6 | Takt des Abgleichs | Nächtlich, 03:30 Uhr | Reaktivierungen sind am nächsten Morgen sichtbar; das genügt für Vorgänge, die ohnehin Tage brauchen |

**Nachgeschärft während der Klärung:** In RA-MICRO können abgelegte Akten reaktiviert werden (etwa bei einer Nachzahlung). Der Abgleich muss deshalb in **beide** Richtungen folgen — eine einmal gesetzte Ablage darf nicht einbetoniert werden.

---

## 3. Sichtbarkeitsregel

> Ein Sachverständiger sieht eine Akte genau dann, wenn RA-MICRO ihn dort als Sachverständigen führt **und** die Akte nicht ausdrücklich gesperrt ist.

RA-MICRO ist alleinige Quelle der Zuordnung; sie wird nicht in SQLite gedoppelt. Ob die Akte unter „Laufend" oder „Abgeschlossen" erscheint, entscheidet allein der Ablage-Status aus RA-MICRO — nicht die Freigabe.

### 3.1 Freigabe wird zur Sperre (Folge aus E-5)

Heute bedeutet `unfallakte.portal_aktiv = 1` „freigegeben"; Voreinstellung ist 0. Damit lässt sich „noch nie angefasst" nicht von „bewusst gesperrt" unterscheiden — E-5 verlangt aber genau diese Unterscheidung, weil neue Akten ohne Zutun frei sein sollen.

Deshalb wird die Entscheidung in einer eigenen Spalte geführt:

- **`portal_gesperrt`** (neu, Voreinstellung 0) trägt die ausdrückliche Entscheidung von RA Schatz. Nur dieses Feld schreibt der Schalter in den Einstellungen.
- **`portal_aktiv`** bleibt das technische Merkmal, an dem `_portal_flag()` und `process_queue()` hängen — es gilt unverändert auch für das Mandantenportal. Der Zugriffs-Abgleich setzt es für alle nicht gesperrten Akten eines aktiven SV-Zugangs auf 1 und für gesperrte auf 0.

Der Schalter in der Aktenliste behält seine Bedienung, wird aber als **freigegeben / gesperrt** beschriftet. Der Knopf „alle aktivieren" **entfällt**: Die Freigabe ergibt sich künftig von selbst, und genau dieser Knopf hat am 2026-08-20 die 545 leeren Akten-Hüllen erzeugt.

---

## 4. Baustein 1 — Ablage-Abgleich

### 4.1 Migration 69

```sql
ALTER TABLE unfallakte ADD COLUMN ramicro_abgelegt INTEGER NOT NULL DEFAULT 0;
ALTER TABLE unfallakte ADD COLUMN ramicro_ablage_datum TEXT;
ALTER TABLE unfallakte ADD COLUMN status_vor_ablage TEXT;
ALTER TABLE unfallakte ADD COLUMN portal_gesperrt INTEGER NOT NULL DEFAULT 0;
```

`status_vor_ablage` merkt sich den Aktenstatus, den der Abgleich beim Ablegen überschrieben hat, damit die Reaktivierung ihn wiederherstellen kann. `portal_gesperrt` trägt die ausdrückliche Sperrentscheidung (siehe 3.1).

Die acht bei der Vorarbeit stillgelegten Akten (`1152/24`, `169/26`, `375/26`, `48/26`, `482/26`, `628/26`, `972/24`, `999/24`) waren nie bewusst gesperrt — sie bleiben auf `portal_gesperrt = 0` und werden damit regulär freigegeben.

Migration 69 legt außerdem die aus Migration 38 fehlenden Portal-Tabellen an (siehe D-1) und repariert die Fremdschlüssel aus D-6.

**Regel aus `feedback_migration_reloader_trap`:** Die Migration in **einem** Schreibvorgang schreiben, `conn.commit()` vor und nach jedem `ALTER TABLE`, kein `executescript()`. Danach Spalten und `schema_version` in der Live-Datenbank nachprüfen.

### 4.2 Neuer Dienst `backend/ramicro/ablage_service.py`

Liest für eine Liste von Aktenzeichen den Ablage-Status aus RA-MICRO — ausschließlich lesend:

```sql
SELECT sAktenNummer, iAblageNummer, dtAblage, sAktenKurzBezeichnung
FROM tblAkten
WHERE sAktenNummer IN (...)
```

Abgelegt ist eine Akte, wenn `ISNULL(iAblageNummer, 0) > 0`. **Nicht** über `dtAblage IS NOT NULL` prüfen: RA-MICRO trägt dort für nicht abgelegte Akten den Nullwert `1899-12-30` ein — dieser Fallstrick hat bei der Bestandsaufnahme zunächst „578 von 578 abgelegt" ergeben.

Ist RA-MICRO nicht erreichbar (`RaMicroNichtAktiv`, `RaMicroVerbindungsFehler`), bricht der Abgleich ohne Änderung ab und schreibt eine Protokollzeile. Ein unerreichbares RA-MICRO darf niemals dazu führen, dass Akten als nicht abgelegt gelten.

### 4.3 Abgleichlauf `backend/services/ablage_abgleich.py`

Eine Funktion `abgleichen(az_liste=None, vorschau=False)` mit zwei Aufrufern:

- **ohne Liste** (nächtlicher Lauf): alle Akten, die in `unfallakte` stehen.
- **mit Liste** (aus dem Zugriffs-Abgleich, 6.1): genau diese Aktenzeichen. Fehlt eine Zeile in `unfallakte`, wird sie angelegt — mit Kurzbezeichnung und Ablage-Status aus RA-MICRO.

Der zweite Fall ist die Erstbefüllung für Ninnivaggis 578 Akten. Anders als beim gelöschten Wildwuchs vom 2026-08-20 entstehen dabei **keine leeren Hüllen**: Jede angelegte Zeile trägt Kurzbezeichnung und Ablage-Status. Ein Unfalldatum führt RA-MICRO für diese Akten nicht; es bleibt leer.

Je Akte:

| Übergang | Wirkung |
|---|---|
| nicht abgelegt → abgelegt | `ramicro_abgelegt = 1`, `ramicro_ablage_datum` setzen; wenn `status <> 'abgeschlossen'`: alten Wert nach `status_vor_ablage` sichern und `status = 'abgeschlossen'` setzen; Sync anstoßen |
| abgelegt → nicht abgelegt (Reaktivierung) | `ramicro_abgelegt = 0`, `ramicro_ablage_datum = NULL`; wenn `status_vor_ablage` gesetzt ist: diesen Wert wiederherstellen und `status_vor_ablage` leeren; Sync anstoßen |
| unverändert | nur `kurzbezeichnung` auffrischen, falls abweichend |

Ein selbst gesetztes `status = 'abgeschlossen'` (aus `models/abrechnungsschreiben.py:404` oder `models/schaden.py:415`) hat kein `status_vor_ablage` und bleibt bei einer Reaktivierung unangetastet.

„Sync anstoßen" heißt `portal_sync_pending = 1` über `queue_sync()`, damit das Portal den Seitenwechsel mitbekommt.

### 4.4 Zweistufige Erstanwendung

Wegen E-2 wirkt der Lauf in Ansichten hinein, die nach Status filtern (Tagesübersicht, `dashboard_routes.py:329`). Deshalb:

```
flask ablage-abgleich --vorschau    # schreibt nichts, meldet je Übergang die Anzahl + Beispiel-AZ
flask ablage-abgleich               # schreibt
```

Der Vorschaulauf ist Teil der Abnahme: RA Schatz sieht die Zahl, bevor irgendetwas geschrieben wird.

### 4.5 Nächtlicher Lauf

Neuer APScheduler-Job in `backend/app.py`, `trigger="cron"` um 03:30 Uhr, neben der bestehenden Fristablauf-Prüfung (03:15). Er ruft denselben Abgleich ohne Vorschau auf.

---

## 5. Baustein 2 — Beschriftung

Der Abgleich aus 4.3 schreibt `sAktenKurzBezeichnung` nach `unfallakte.kurzbezeichnung`, sofern dort nichts Abweichendes gepflegt ist. Für alle 578 Akten liegt eine Kurzbezeichnung vor.

`_build_payload()` in `backend/services/portal_sync.py` sendet `kurzbezeichnung` bislang nicht, obwohl der Portal-Empfänger (`src/lib/sync.ts`) das Feld bereits verarbeitet und `AkteCard` es anzeigt. Ergänzen.

Ergebnis auf der Karte: `AZ 1000/25 · Türe/Taskoparan`.

---

## 6. Baustein 3 — Zugriffs-Abgleich

Die Berechtigung wird getrennt vom Akteninhalt übertragen. Sie ändert sich, wenn RA-MICRO die Zuordnung ändert oder ein Schalter umgelegt wird — nicht, wenn sich Akteninhalte ändern.

### 6.1 Kanzlei-Seite

Neuer Dienst `backend/services/sv_zugriff_sync.py`:

1. RA-MICRO nach den Akten des SV fragen (die vorhandene `_hole_akten_fuer_sv()` aus `sv_portal_routes.py` dorthin verschieben — sie gehört nicht in eine Routendatei).
2. `ablage_abgleich.abgleichen(az_liste)` für diese Aktenzeichen aufrufen: fehlende Zeilen anlegen, Kurzbezeichnung und Ablage-Status auffrischen.
3. `portal_aktiv` setzen: 1 für nicht gesperrte, 0 für gesperrte Akten (siehe 3.1); anschließend die gesperrten aus der Liste nehmen.
4. Als Sendung ans Portal übertragen, signiert wie der Aktensync (HMAC über `PORTAL_HMAC_SECRET`):

```json
{
  "adressnr": 25982,
  "name": "Ninnivaggi",
  "vorname": "KFZ-Sachverständigenbüro",
  "email": "info@gn-gutachter.de",
  "akten": ["1000/25", "1008/25", "..."]
}
```

Auslöser: Knopf „Zugriffe abgleichen" im SV-Reiter, dazu ein CLI-Befehl `flask sync-sv-zugriffe`.

### 6.2 Portal-Seite

Neuer Endpunkt `POST /api/sync/sv-zugriffe` in `stakeholder-portal`, HMAC-geprüft wie `/api/sync/push`:

- `portal_users` anlegen, falls zur E-Mail noch kein Zugang besteht (`rolle = 'sachverstaendiger'`).
- `akte_zugriff` auf **genau** die übergebene Liste setzen: fehlende anlegen, entzogene löschen. Damit wirkt eine Sperre in den Einstellungen auch rückwirkend.
- Keine Einladungs-E-Mail. Der Zugang wird im Rahmen der Veröffentlichung vergeben (eigenes Vorhaben, E-3).

Wichtig: Ein Zugriffseintrag ohne zugehörige Zeile in `akten` bleibt unsichtbar, weil `getSvAkten()` beide verbindet. Der Zugriffs-Abgleich ersetzt den Aktensync also nicht — beide müssen laufen.

### 6.3 Aktenzahl in der SV-Liste

`GET /einstellungen/sv-portal` zählt heute über `beteiligte.email` und liefert deshalb immer 0. Umstellen auf die RA-MICRO-Zahl, getrennt ausgewiesen als **laufend / gesamt** (für Ninnivaggi: „111 laufend, 578 gesamt").

Die Aktenliste je SV (`GET /<adressnr>/akten`) zeigt zusätzlich den Ablage-Status je Zeile, damit erkennbar ist, was beim Sachverständigen unter „Laufend" landet. `PATCH /akten/<az>/portal_aktiv` schreibt künftig `portal_gesperrt` statt `portal_aktiv`; `PATCH /<adressnr>/akten/alle` entfällt (siehe 3.1).

---

## 7. Behobene Defekte

| # | Befund | Fundstelle | Behebung |
|---|---|---|---|
| D-1 | `portal_sync_queue` und `portal_einladungen` fehlen in der Datenbank, obwohl Migration 38 als ausgeführt vermerkt ist | Live-DB; bekannte Falle aus `feedback_migration38_portal_spalten` | Migration 69 legt sie an, falls nicht vorhanden |
| D-2 | Der Payload liest `beteiligte.gutachten_nr` — diese Spalte existiert nicht. Jeder Aufbau bricht mit `no such column` ab | `portal_sync.py:_build_payload`, `stakeholder-portal/scripts/sync_connector.py` | Feld aus beiden Abfragen entfernen. Das Portal führt `akte_zugriff.gutachten_nr` ohnehin als „bleibt leer bis Portal-A2" (PORTAL-B2, Anhang A) |
| D-3 | `PORTAL_API_URL`, `PORTAL_API_KEY`, `PORTAL_HMAC_SECRET` sind nicht gesetzt; der Versand steigt sofort aus | Backend-Container | Für den Testbetrieb auf das lokale Portal setzen (`http://host.docker.internal:3002`), Schlüssel aus `.env.local` des Portals |
| D-4 | Eine Akte ohne erfasste Beträge zeigt „bezahlt ✓" | `AkteCard.tsx`, `RechnungBlock.tsx` | Bei `sv_kosten_gefordert = 0` „—" anzeigen statt einer Aussage über die Zahlung |
| D-5 | Abgelaufene Sitzung führt zu einer leeren SV-Liste statt einer Meldung (`catch { setSvListe([]) }`) | `EinstellungenView.jsx:113` und die Akten-Ladefunktion daneben | Fehler unterscheiden: bei 401 „Sitzung abgelaufen — bitte neu anmelden", sonst Fehlermeldung; nie stumm leeren |
| D-6 | Akten lassen sich nicht löschen: `forderung_positionen` und `abrechnungsschreiben` verweisen per Fremdschlüssel auf die nicht mehr existierende Tabelle `dokumente_alt`. Da `database.py:46` `PRAGMA foreign_keys=ON` setzt, scheitert jedes `DELETE FROM unfallakte` mit `no such table: main.dokumente_alt` | Live-DB | Beide Tabellen mit korrektem Verweis auf `dokumente` neu aufbauen (Teil von Migration 69) |

D-4 ist der gefährlichste Punkt: Er würde dem Sachverständigen offene Honorare als beglichen anzeigen.

D-6 gehört sachlich nicht zum Portal, fiel aber bei der Bereinigung an und ist eng umgrenzt. Er kann bei Bedarf abgetrennt werden.

---

## 8. Datenfluss

```
RA-MICRO (read-only)
  |
  |-- tblAkten.iAblageNummer / dtAblage / sAktenKurzBezeichnung
  |        | nächtlich 03:30
  |        v
  |   unfallakte.ramicro_abgelegt · status · kurzbezeichnung
  |        | portal_sync_pending = 1
  |        v
  |   portal_sync.process_queue()  --POST /api/sync/push-->  Portal: akten
  |
  '-- tblAktenBeteiligte (iAdressnummer, SV-Kennzeichen)
           | auf Knopfdruck, gekürzt um portal_aktiv = 0
           v
     sv_zugriff_sync  --POST /api/sync/sv-zugriffe-->  Portal: portal_users · akte_zugriff
                                                              |
                                                              v
                                                     SV sieht Akte, wenn beides vorliegt
```

---

## 9. Fehlerfälle

| Fall | Verhalten |
|---|---|
| RA-MICRO nicht erreichbar | Abgleich bricht ohne Änderung ab, Protokolleintrag. Keine Akte wechselt die Seite |
| Portal nicht erreichbar | Bestehendes Verhalten: `portal_sync_queue`-Eintrag auf `failed`, Wiederholung; nach fünf Fehlversuchen wird `portal_sync_pending` zurückgesetzt und die Akte protokolliert |
| Akte in RA-MICRO, aber nicht in SQLite | Der Zugriffs-Abgleich legt die Zeile über Schritt 2 (6.1) mit Kurzbezeichnung und Ablage-Status an. Im Portal sichtbar wird sie, sobald der Aktensync sie übertragen hat — beide Schritte sind nötig |
| SV in RA-MICRO von einer Akte entfernt | Nächster Zugriffs-Abgleich löscht den Zugriffseintrag; die Akte verschwindet aus seiner Liste |
| Akte gesperrt (`portal_gesperrt = 1`) | Fällt aus der Zugriffsliste, `portal_aktiv` wird auf 0 gesetzt; im Portal beim nächsten Abgleich entzogen |
| Falsche HMAC-Signatur am neuen Endpunkt | 401, keine Änderung |

---

## 10. Tests

**Backend (pytest, mit RA-MICRO-Mock — Pflicht laut `project_unfallakten_vollsuite_sanierung`):**

- `ablage_service`: abgelegt erkannt (`iAblageNummer > 0`), **nicht** abgelegt bei `dtAblage = 1899-12-30`, RA-MICRO nicht erreichbar → keine Änderung.
- Abgleichlauf: Ablegen setzt Status und sichert den vorherigen; Reaktivierung stellt ihn wieder her; ein selbst gesetzter Abschluss (ohne `status_vor_ablage`) bleibt bei Reaktivierung unangetastet; jeder Übergang setzt `portal_sync_pending = 1`.
- Vorschaulauf schreibt nichts.
- Migrations-Wächter: `portal_sync_queue` und `portal_einladungen` existieren nach der Migration; `DELETE FROM unfallakte` gelingt bei eingeschalteter Fremdschlüsselprüfung (D-6).
- Payload: enthält `kurzbezeichnung`, enthält **kein** `gutachten_nr`, Status abgelegter Akten ist `abgeschlossen`.
- Zugriffs-Abgleich: legt fehlende Akten-Zeilen mit Kurzbezeichnung an; kürzt um gesperrte Akten und setzt deren `portal_aktiv` auf 0; leere Liste bei unbekanntem SV.
- Sperre: eine nie angefasste Akte gilt als frei, eine gesperrte nicht; das Aufheben der Sperre gibt sie wieder frei.

**Portal (vitest):**

- `POST /api/sync/sv-zugriffe`: legt Nutzer an, legt Zugriffe an, entzieht entfallene, lehnt falsche Signatur ab, ist wiederholbar ohne Doppelanlage.
- `AkteCard`: zeigt bei `sv_kosten_gefordert = 0` „—" statt „bezahlt ✓".
- `filterAkten`: Voreinstellung „Laufend" blendet abgeschlossene aus (bestehender Test, als Regressionsschutz bestätigen).

**Frontend (vitest):**

- SV-Liste zeigt bei 401 „Sitzung abgelaufen", nicht die Leermeldung.

---

## 11. Abnahme

Über die Impersonate-Funktion im Portal-Admin, mit echten Daten, auf `localhost:3002`:

1. Vorschaulauf `flask ablage-abgleich --vorschau` — Zahlen von RA Schatz bestätigen lassen, **dann** erst schreiben.
2. Zugriffs-Abgleich für Adressnr. 25982 auslösen.
3. Als Ninnivaggi anmelden:
   - Startseite meldet „Meine Akten — 578 Fälle" (Cockpitmodus, nicht Kompaktmodus).
   - Aktenliste zeigt beim Öffnen **111** Akten, nicht 578.
   - Chip „Abgeschlossen" klappt **467** auf.
   - Suche nach einem Mandantennamen findet die Akte.
   - Keine Akte behauptet „bezahlt ✓", wo nichts erfasst ist.
4. Eine Akte in RA-MICRO reaktivieren, Abgleich laufen lassen: Sie wandert zurück zu „Laufend", ihr vorheriger Aktenstatus ist wiederhergestellt.
5. Eine Akte sperren, Zugriffs-Abgleich laufen lassen: Sie verschwindet aus seiner Liste.

---

## 12. Nicht Teil dieses Vorhabens

- **Veröffentlichung des Portals** (Domain, SSL, E-Mail-Versand der Zugangslinks, Auftragsverarbeitung und Datenschutzerklärung für den SV-Zugang) — eigenes Vorhaben, E-3.
- **Einladungs-E-Mail.** Der bestehende Endpunkt setzt weiterhin nur den Zeitstempel.
- **Gutachtennummer.** Wird im Kanzlei-System nirgends geführt; das Portal zeigt das Feld leer an. Nachrüsten wäre Portal-A2 und ist hier nicht enthalten.
- **Mandantenportal.** Unberührt.
- **Zweiter Sachverständiger (Cassese).** Der Mechanismus trägt ihn, die Freischaltung ist aber nicht Gegenstand dieser Abnahme. Seine neun bereits freigegebenen Akten bleiben unangetastet.

---

## 13. Risiken

| Risiko | Umgang |
|---|---|
| E-2 verändert Ansichten außerhalb des Portals: Akten mit Status `abgeschlossen` fallen aus der Tagesübersicht (`dashboard_routes.py:329`) | Vorschaulauf vor dem Schreiben; Backup vor dem ersten schreibenden Lauf. Die Zahl der betroffenen Akten liegt bei rund 850 |
| Zwei Sync-Wege nebeneinander: `backend/services/portal_sync.py` (in der Anwendung) und `stakeholder-portal/scripts/sync_connector.py` (Skript). Die Payloads unterscheiden sich | In diesem Vorhaben gilt der Weg in der Anwendung. Der Skript-Weg wird nur um D-2 bereinigt, damit er nicht mit veraltetem Aufbau danebenläuft |
| Die 578 Akten sind bei uns inhaltlich dünn (von 111 laufenden haben 26 eine Kurzbezeichnung bei uns, keine ein Unfalldatum, 22 Dokumente) | Baustein 2 füllt die Kurzbezeichnung aus RA-MICRO. Mehr Inhalt entsteht erst im laufenden Betrieb; die Karten bleiben zunächst schlicht. Bewusst in Kauf genommen |
| Migration 69 könnte der Reloader-Falle zum Opfer fallen | In einem Schreibvorgang schreiben, danach `schema_version` und Spalten in der Live-Datenbank prüfen |
