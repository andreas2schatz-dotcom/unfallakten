# Design: Review-Queue entrümpeln (Baustelle 1a „Volumen zähmen")

**Datum:** 2026-07-31 · **Status:** Design **+ Mockup von RA Schatz freigegeben** (2026-07-31). Umsetzung wartet hinter Merge-Gate, s. u.
**Herkunft:** UX-Review 2026-07-31 (`handover/2026-07-31_UX-Review_Roadmap.md`), Punkte B6 + Bündel-Aktionen.
**Mockup (freigegeben):** https://claude.ai/code/artifact/9f2b41c8-1658-4ad3-a572-1a833c4f69f1 — Review-Queue im hellen Hausstil, zeigt Mehrfachauswahl + Bündelleiste, eingeklappten Spamverdacht-Korb mit Grund-Etiketten (Massen-E-Mail / gelernter Absender / von Hand) + Zurückholen, und den Lern-Rückfrage-Dialog (exakte Adresse, `schaden@…` bleibt unberührt). **Standard hell**, Dunkel nur per Umschalter. Quelle: Session-Scratchpad `mock.template.html` + Build-Snippet (Hausschrift inline).
**Nächster Schritt:** `superpowers:writing-plans` — erst **nach** Merge von `aktenanlage` → `main` → `dashboard-hell`.

---

## 1. Ziel

Die Review-Queue enthält ~89 „bereite" Einträge, viele davon offensichtlicher Nicht-Fall-Kram (DHL/Amazon-Paketmeldungen, Facebook, Newsletter, Versicherer-Rundmails, verpasste Anrufe). Heute muss RA Schatz jeden einzeln „Verwerfen". Ziel: **Rausch automatisch und sicher aus dem Blick nehmen** und **manuelles Aufräumen im Schwung** ermöglichen — ohne dass je ein echtes Schreiben verloren geht.

## 2. Ist-Zustand (verifiziert)

- **Rausch-Filter heute:** `backend/intake/rausch_regel.py` + `backend/registry/rausch_absender.yaml` — eine **manuelle Domain-Blockliste mit 2 Einträgen** (`placetel.de` = nur_body, `bea-brak.de` = komplett), Exakt-Domain-Treffer beim Eingang (`adapter_imap`). Der lange Schwanz rutscht durch.
- **Klassifikator** (`backend/intake/klassifikator.py`): Unerkanntes fällt auf Klasse **`sonstiges` (Konfidenz 0,5)** und landet als `bereit_zur_review` / „Keine Akten-Vorschläge" in der Queue.
- **Soft-Delete/Papierkorb existiert:** `backend/intake/verwerfen.py::auto_verwerfen(intake_id, grund, kommentar, benutzer_id)` setzt `verworfen_grund/am/von` + `korrektur_log`. `benutzer_id=None` = System. Routen in `backend/routers/intake_routes.py`: `POST /intake/dokument/<id>/verwerfen`, `GET /intake/papierkorb`, `POST /intake/dokument/<id>/wiederherstellen`.
- **Import liest Roh-Mail-Header** bereits aus (`adapter_imap.py`: `Subject`, `From`, `Authentication-Results`/SPF-DKIM, …) — `List-Unsubscribe` mitzulesen ist additiv.
- **Frontend** `frontend/src/views/ReviewQueueView.jsx`: Tabs „Queue"/„Papierkorb", Sortier-Toggle (Eingangsdatum, localStorage). Keine Mehrfachauswahl.

## 3. Nicht-Ziele

- Keine LLM-Rausch-Erkennung in v1 (Ansatz C verworfen — mehr Unschärfe, wenig Zusatznutzen; später nachrüstbar).
- Kein Anfassen der bestehenden 2-Domain-Hartregel (`rausch_absender.yaml`) — bleibt wie sie ist.
- Keine Fristen-Triage (Baustelle 1b, eigene Spec).

## 4. Zustandsmodell — die drei Körbe

Ein Queue-Eintrag ist in genau einem sichtbaren Zustand:

| Korb | Bedeutung | Speicherung |
|---|---|---|
| **Hauptliste** | echte Arbeit | `queue_status='bereit_zur_review'`, `rausch_verdacht_grund IS NULL` |
| **Spamverdacht** | vermutlich Rausch, eingeklappt, wiederherstellbar | `queue_status='bereit_zur_review'`, `rausch_verdacht_grund` gesetzt |
| **Papierkorb** | verworfen, endgültig aber wiederherstellbar | `verworfen_am` gesetzt (bestehend) |

**Neue Spalte** `intake_dokumente.rausch_verdacht_grund TEXT NULL` mit Werten `'massenmail'` | `'gelernter_absender'` | `'manuell'`. Spamverdacht ist bewusst **kein** eigener `queue_status`, sondern ein Flag auf `bereit_zur_review` — so bleibt der Eintrag ein normaler, jederzeit zurückholbarer Queue-Eintrag und alle bestehenden Queue-Invarianten gelten weiter.

Übergänge:
- Auto (A/B) beim Eingang: `NULL → 'massenmail'` bzw. `'gelernter_absender'`.
- Manuell „→ Spamverdacht": `NULL → 'manuell'`.
- „Zurück in Queue": `→ NULL`.
- „→ Papierkorb": setzt `verworfen_am` (aus jedem Korb heraus).

## 5. Ansatz A — Massen-E-Mail-Erkennung (deterministisch)

**Signal (Massenmail):** beim Eingang wahr, wenn einer dieser Header vorliegt:
- `List-Unsubscribe` vorhanden, **oder**
- `Precedence:` ∈ {`bulk`, `list`, `junk`}, **oder**
- `List-Id` vorhanden.

**Schutzregel (Kern-Invariante):** Ein Eingang wird **nur dann** auf `rausch_verdacht_grund='massenmail'` gesetzt, wenn **alle** gelten:
1. Massenmail-Signal vorhanden, **und**
2. Klasse `= 'sonstiges'` (keine Fall-Klasse erkannt), **und**
3. **kein** Aktenzeichen-Treffer / keine Akten-Zuordnung.

Sobald ein Dokument nach echter Schadenspost aussieht (Fall-Klasse) oder einer Akte zuordenbar ist, wird es **nie** automatisch aussortiert — selbst mit Abmeldelink. Da nichts gelöscht, nur eingeklappt wird, ist der Worst Case „einmal aufklappen".

**Ort:** Auswertung in der Intake-Pipeline nach der Klassifikation (Signal in `adapter_imap` erfassen, Entscheidung dort, wo Klasse + AZ-Treffer vorliegen — Dispatcher/Queue-Schreibpunkt). Fail-loud-Prinzip der Registries bleibt unberührt.

## 6. Ansatz B — Lernende Absenderliste (opt-in nach Rückfrage)

- **Neue Tabelle** `rausch_absender_gelernt(absender_email TEXT UNIQUE, angelegt_von INTEGER, angelegt_am TEXT, treffer_zahl INTEGER DEFAULT 0)`. Getrennt von der kuratierten YAML-Hartliste.
- **Exakte Absender-Adresse, nicht Domain** (Kern-Invariante): Versicherer senden über dieselbe Domain Newsletter *und* Schadensregulierung. `newsletter@axa.de` lernen, `schaden@axa.de` bleibt unangetastet. Kein Domain-Wildcard in v1.
- **Opt-in nach Rückfrage:** Nach einer manuellen „→ Spamverdacht"-Aktion fragt das Frontend **einmal pro betroffener, noch nicht gelernter Absender-Adresse**: „Absender X künftig automatisch aussortieren?" (bei Bündel-Aktion Liste der distinct Absender mit Häkchen). Bestätigte Adressen → Tabelle.
- **Wirkung beim Eingang:** exakter Treffer in `rausch_absender_gelernt` → `rausch_verdacht_grund='gelernter_absender'` (dieselbe eingeklappte Behandlung; **nicht** hart verworfen, damit ein Fehler beim Lernen folgenlos bleibt).
- Verwaltung/Rücknahme gelernter Absender: minimal (Liste + Löschen) — Detailort offen (s. §10).

## 7. Frontend (`ReviewQueueView.jsx`)

- **Mehrfachauswahl:** Checkbox je Eintrag + „Alle auswählen". Bei ≥1 Auswahl erscheint eine **Aktionsleiste**: „→ Papierkorb (N)", „→ Spamverdacht (N)", „Auswahl aufheben".
- **Eingeklappter Block „Vermutlich Rausch (N)"** am Ende der Queue-Liste: standardmäßig zu, aufklappbar. Je Eintrag ein **Etikett** mit Grund („Massen-E-Mail" / „gelernter Absender" / „von Hand") und **Rückhol-Knopf** („zurück in Queue"). Mehrfachauswahl auch hier → „→ Papierkorb (N)" / „→ zurück in Queue (N)".
- **Rückfrage-Dialog** nach manueller „→ Spamverdacht" (Ansatz B, §6).
- Papierkorb-Tab unverändert; profitiert aber von Mehrfachauswahl (Wiederherstellen im Schwung — optional).
- A11y: Checkboxen mit Label, Aktionsleiste als `role="region"`/aria-live, Buttons `type="button"`.

## 8. Backend-Routen (neu)

- `POST /intake/bulk/verwerfen` — Body `{ids: [int]}`, Schleife über bestehendes `auto_verwerfen`; liefert Ergebnis je ID (verworfen / übersprungen).
- `POST /intake/bulk/spamverdacht` — Body `{ids: [int]}`, setzt `rausch_verdacht_grund='manuell'`; Antwort enthält die **distinct Absender** der betroffenen, noch nicht gelernten IDs (für den Rückfrage-Dialog).
- `POST /intake/bulk/zurueck-in-queue` — Body `{ids: [int]}`, setzt `rausch_verdacht_grund=NULL`.
- `POST /intake/rausch-absender/lernen` — Body `{absender: [email]}`, schreibt bestätigte Adressen in `rausch_absender_gelernt`.
- `GET /intake/queue` erweitern: liefert `rausch_verdacht_grund` je Eintrag mit; optional getrennte Zählung Hauptliste vs. Spamverdacht.

## 9. Migration & Sicherheit

- **Migration** (nächste freie Nummer, atomar in EINEM Edit — Reloader-Trap beachten): `ALTER TABLE intake_dokumente ADD COLUMN rausch_verdacht_grund TEXT` + `CREATE TABLE rausch_absender_gelernt(...)`. Additiv, forward-only. `conn.commit()` vor+nach ALTER. Basis-`schema.py` mitziehen. Regel „Migration vor App-Code".
- **Kern-Invarianten (Testpflicht):**
  - I1: Dokument mit AZ-Treffer **oder** Fall-Klasse ≠ `sonstiges` wird **nie** automatisch auf Spamverdacht gesetzt.
  - I2: Lernen speichert die **exakte Absender-Adresse**, nie eine Domain.
  - I3: Nichts wird hart gelöscht — Spamverdacht und Papierkorb sind vollständig wiederherstellbar.
  - I4: Auto-Spamverdacht wird **nur nach Rückfrage** zu „gelernter Absender"; ohne Bestätigung kein Lerneintrag.

## 10. Tests

- Header-Erkennung (List-Unsubscribe / Precedence / List-Id) → Signal.
- Schutzregel I1 (mit/ohne AZ-Treffer, Fall-Klasse vs. sonstiges).
- Bündel-Endpunkte (verwerfen/spamverdacht/zurück) inkl. gemischter Status.
- Lernen I2/I4 (exakte Adresse, opt-in).
- Wiederherstellbarkeit I3.
- Migration idempotent auf Bestands-DB.

## 11. Offene Punkte (in writing-plans zu klären)

- Genauer Einbau-Ort der A-Entscheidung im Dispatcher/Queue-Schreibpunkt (wo Klasse **und** AZ-Treffer sicher vorliegen).
- Verwaltungsort für gelernte Absender (eigener kleiner Bereich in Einstellungen vs. Inline in der Queue).
- Sollen die bestehenden 2 Hart-Domains optisch auch als „Massen-E-Mail" auftauchen oder unverändert bleiben (Vorschlag: unverändert).

## 12. Abgrenzung / Reihenfolge

Teil von Baustelle 1 „Volumen zähmen". 1b (Fristen-Triage) ist eine eigene Spec. Umsetzung erst nach dem Merge-Gate (`aktenanlage` → `main`, dann `dashboard-hell`), da die Dev-Container auf `aktenanlage` laufen.
