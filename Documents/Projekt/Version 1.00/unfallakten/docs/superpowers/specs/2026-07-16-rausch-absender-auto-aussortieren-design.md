# Rausch-Absender automatisch aussortieren + Papierkorb

> Design-Spec · 2026-07-16 · Branch-Ziel: Feature-Branch von `main`
> Status: freigegeben im Brainstorming (RA Schatz)

## Ziel

Auf `info@` laufen E-Mails auf, die für die Review-Queue garantiert wertlos sind und sie
zumüllen. Zwei Kategorien sind bekannt:

1. **Placetel** (`no-reply@placetel.de`, Telefonanlage):
   - **ohne Anhang** = „verpasster Anruf"-Benachrichtigung → wertlos.
   - **mit Anhang** = eingegangenes **Fax** (PDF) → muss erfasst werden. Der E-Mail-Body ist
     nur ein Deckblatt-Text und ebenfalls wertlos.
2. **beA** (`bea-brak.de`): Benachrichtigungen, dass eine beA-Nachricht eingegangen ist.
   Nie ein Aktenbezug enthalten; die eigentliche Nachricht wird über den RA-MICRO-Posteingang
   entschlüsselt. **Immer** wertlos — Body **und** etwaige Anhänge.

Das System soll solche Mails **beim Eingang automatisch aussortieren**, sodass sie gar nicht
erst in der Review-Queue auftauchen — über denselben Soft-Delete wie der manuelle
Verwerfen-Button (nichts wird hart gelöscht). Ein **Papierkorb** macht die Auto-Aussortierung
kontrollierbar: verworfene Dokumente bleiben einsehbar und wiederherstellbar.

## Leitentscheidungen (aus dem Brainstorming)

1. **Auto-aussortieren beim Eingang** (nicht bloß ein Anzeige-Filter). Nutzt den bestehenden
   Verwerfen-Mechanismus (`verworfen_grund`/`verworfen_am`/`verworfen_von`, Migration 53) —
   Row + Datei bleiben in der DB, auditierbar via `korrektur_log`.
2. **Per-Dokument-Policy statt „hat Anhang?"-Abfrage.** Die Regel entscheidet **pro erzeugtem
   Intake-Dokument**; das gewünschte Verhalten fällt ohne Sonderfall-Logik heraus:

   | Absender-Domain | Policy | Body | Anhänge |
   |---|---|---|---|
   | `placetel.de` | `nur_body` | verwerfen | **behalten** (Fax) |
   | `bea-brak.de` | `komplett` | verwerfen | verwerfen |

   - Placetel **ohne** Anhang → nur ein Body-Dok existiert → verworfen → Mail komplett weg.
   - Placetel **mit** Fax → Body verworfen, Fax-PDF bleibt in der Queue.
   - beA → Body + evtl. Anhänge verworfen → immer weg.
   - Unbekannter Absender → nichts wird angefasst.
3. **Erkennung an der Absender-Domain** (aus dem `From:`-Header), nicht an der vollen Adresse.
   Robust gegen `no-reply@` vs. `fax@` etc. Nutzt den bestehenden `_domain_aus_from_header`.
4. **Konfig als YAML-Registry** (`backend/registry/rausch_absender.yaml`), fail-loud geladen —
   wie die anderen Registries. Neuen Absender ergänzen = eine Zeile + Redeploy.
5. **Betreff-Muster „Fax von '…' auf '069999993317'" wird NICHT verwendet.** Die
   Anhang-Präsenz unterscheidet Fax von Anruf-Info bereits zuverlässig; die feste Faxnummer zu
   hardcoden wäre fragil, und ein echtes Placetel-PDF, das kein Fax ist, soll ohnehin in die
   Queue. (Optional später für die Dokumentbezeichnung nutzbar — PRD-37-Gebiet, nicht hier.)
6. **Kein SPF/DKIM-Gate.** Die Regel greift rein domainbasiert. Der Papierkorb ist das
   Sicherheitsnetz gegen einen (sehr unwahrscheinlichen) Spoofing-Fall; ein Gate riskierte, dass
   echtes Rauschen mit fehlendem `auth_status` doch durchrutscht.
7. **Papierkorb-UI im Scope.** Auto-Aussortierung ohne Einsicht wäre unheimlich — der
   Papierkorb zeigt, was die Regel entfernt hat, und erlaubt Wiederherstellung.

## Architektur

### 1. Konfig — `backend/registry/rausch_absender.yaml`

```yaml
- domain: placetel.de
  policy: nur_body      # Body verwerfen, Anhänge (Faxe) behalten
- domain: bea-brak.de
  policy: komplett      # Body + Anhänge verwerfen
```

Erlaubte `policy`-Werte: `nur_body`, `komplett`. `domain` ist die kleingeschriebene Domain.

### 2. Regel-Modul — `backend/intake/rausch_regel.py`

Reine, DB-freie Logik + fail-loud Loader (Muster aus `registry_loader.py`, aber für eine
**einzelne** YAML-Datei mit Listen-Wurzel):

- `lade_regeln(pfad=None, *, reload=False) -> dict[str, str]` — lädt die YAML, validiert
  fail-loud (Wurzel = Liste; jeder Eintrag Mapping mit `domain` (nichtleerer String) +
  `policy` ∈ {`nur_body`, `komplett`}; keine doppelte Domain), liefert `{domain: policy}`.
  Cache-Singleton je Pfad. Pfad überschreibbar via Env `INTAKE_RAUSCH_REGISTRY_PFAD` (Tests).
- `bewerte_absender(from_header: str | None) -> str | None` — Domain aus dem Header ziehen
  (via `_domain_aus_from_header` aus `adapter_imap`), in den geladenen Regeln nachschlagen.
  Liefert die Policy (`nur_body`/`komplett`) oder `None` (kein Rausch-Absender).

Fail-loud beim Laden: defektes/fehlendes YAML → `RuntimeError` beim App-Start (die Datei ist
Teil des Deployments, kein Laufzeit-Input).

### 3. Auto-Verwerfen-Helfer

Der manuelle `post_verwerfen` (in `intake_routes.py`) und der Adapter sollen **denselben**
Soft-Delete schreiben. Dazu die Kern-Schreiblogik in einen Helfer ziehen:

`auto_verwerfen(intake_id, *, grund, kommentar=None, benutzer_id=None) -> bool`

- **Öffnet die DB-Connection selbst** (`with get_connection()`), damit Adapter und Route sie
  ohne durchgereichtes `conn` aufrufen können. Klasse/registry_version für die `korrektur_log`
  liest der Helfer selbst aus der Zeile.
- Setzt `verworfen_grund`, `verworfen_am` (UTC-ISO, wie die Route), `verworfen_von`
  (= `benutzer_id`; **`NULL` = System** bei der Auto-Regel).
- Schreibt eine `korrektur_log`-Zeile (`feld='verworfen'`, `wert_neu={grund, kommentar}`).
- **Guard:** überspringt (liefert `False`), wenn das Dokument bereits verworfen ist
  (`verworfen_am IS NOT NULL`) oder bereits freigegeben (`queue_status='freigegeben'`). Nur
  `neu`/`bereit_zur_review`/`pipeline_fehler` werden verworfen — analog zum Route-Guard.

Ort: eine kleine Funktion, die sowohl die Route als auch der Adapter importieren. Vorschlag
`backend/intake/verwerfen.py` (oder als Funktion in `rausch_regel.py`, wenn schlanker). Die
Route `post_verwerfen` ruft sie künftig auf (Verhalten unverändert: benutzer_id gesetzt,
Status-Guard bleibt, die 400/404/409-Antworten bleiben in der Route).

### 4. Integration — `adapter_imap.verarbeite_email`

Am Ende von `verarbeite_email`, nachdem Body- und Anhang-Dokumente angelegt sind:

```
policy = bewerte_absender(absender)   # 'absender' = From-Header, liegt schon vor
if policy:                            # nur_body oder komplett
    auto_verwerfen(body_intake_id, grund="rauschen",
                   kommentar=f"Auto: Rausch-Absender ({policy})")
    if policy == "komplett":
        for a in anhang_ergebnisse:
            auto_verwerfen(a["intake_dokument_id"], grund="rauschen",
                           kommentar=f"Auto: Rausch-Absender ({policy})")
```

- Die Regel ist **absenderbasiert** und damit **kontounabhängig** — sie greift für jede
  eingehende Mail dieser Domains, egal über welches IMAP-Konto sie kommt.
- Auto-verworfene Body-/beA-Dokumente behalten `queue_status='neu'`; der Worker verarbeitet sie
  ggf. noch (Textpfad, günstig — LLM in Stufe 1 aus), was **harmlos** ist: sie erscheinen wegen
  `verworfen_am IS NOT NULL` nie in der Queue. Bewusst kein Eingriff in den Worker (der
  `queue_status`-CHECK kennt kein `'verworfen'`; ein Table-Rebuild wäre unverhältnismäßig —
  dieselbe Begründung wie beim manuellen Verwerfen).

### 5. `_VERWERFEN_GRUENDE`

Um `"rauschen"` erweitern. **Keine Migration** — `verworfen_grund` ist eine freie Spalte, die
Whitelist ist App-Ebene.

### 6. Papierkorb — Backend

Zwei neue Endpunkte in `intake_routes.py`:

- `GET /intake/papierkorb` — verworfene Dokumente (`verworfen_am IS NOT NULL`), neueste zuerst
  (`ORDER BY verworfen_am DESC`). Liefert je Eintrag dieselbe Kernform wie `hole_queue`
  (id, klasse, konfidenz, payload_typ, absender, betreff, erstellt_am …) **plus**
  `verworfen_grund`, `verworfen_am`. Sinnvolles Limit (z. B. 200) gegen unbegrenztes Wachstum.
- `POST /intake/dokument/<id>/wiederherstellen` — macht den Soft-Delete rückgängig:
  `verworfen_grund/am/von = NULL`, `korrektur_log`-Zeile (`feld='wiederhergestellt'`).
  **Guard:** 404 wenn nicht vorhanden, 409 wenn nicht verworfen. Nach dem Zurücksetzen erscheint
  das Dokument wieder in der Queue, sofern sein `queue_status` ein Review-Zustand ist (bei
  `neu` verarbeitet es der Worker regulär zu `bereit_zur_review`).

### 7. Papierkorb — Frontend (`ReviewQueueView.jsx`)

- **Umschalter im Queue-Header:** „Queue ⇄ Papierkorb" (lokaler View-State). Standard: Queue.
- **Papierkorb-Liste:** lädt `GET /intake/papierkorb`, rendert mit der bestehenden
  `QueueEintrag`-Darstellung, ergänzt um ein **Grund-Label** (z. B. „Rauschen", „Spam") und das
  Verwerf-Datum. Je Eintrag ein **„Wiederherstellen"**-Knopf →
  `POST …/wiederherstellen` → Liste neu laden.
- `api.js`: `papierkorb()` + `wiederherstellen(id)`.
- Kein Auto-Polling im Papierkorb nötig (statische Sicht; Reload nach Aktion genügt).

## Datenfluss

```
IMAP-Poll → adapter_imap.verarbeite_email
   ├─ Body-Dok + Anhang-Doks anlegen (unverändert)
   └─ bewerte_absender(From) ─ policy?
        ├─ nur_body   → auto_verwerfen(Body)
        └─ komplett   → auto_verwerfen(Body) + auto_verwerfen(jeder Anhang)

hole_queue   : WHERE verworfen_am IS NULL           (unverändert → Rauschen unsichtbar)
papierkorb   : WHERE verworfen_am IS NOT NULL       (neu)
wiederherstellen : verworfen_* = NULL               (neu)
```

## Fehlerbehandlung

- **Regel-Lookup schlägt fehl** ist keine Laufzeitoption: Die YAML ist Deploy-Artefakt und wird
  fail-loud beim Start geladen. `bewerte_absender` auf einer geladenen Registry wirft nicht.
- **Auto-Verwerfen** läuft **best-effort** relativ zum Mail-Import: schlägt ein einzelnes
  `auto_verwerfen` fehl (z. B. DB-Sperre), wird es geloggt, aber der Import der übrigen
  Dokumente nicht abgebrochen. Schlimmster Fall: ein Rausch-Dokument landet doch in der Queue
  und wird manuell verworfen — kein Datenverlust.
- **Wiederherstellen** eines nicht-verworfenen oder unbekannten Dokuments → 409/404, keine
  stille Mutation.

## Abgrenzung (bewusst NICHT im Scope)

- Kein SPF/DKIM-Gate (Leitentscheidung 6).
- Kein Betreff-Muster-Matching (Leitentscheidung 5).
- Keine Admin-UI zum Pflegen der Rausch-Absender (YAML + Redeploy genügt bei 2 Absendern).
  Falls das später oft geändert wird → DB-Tabelle + UI als eigenes Mini-Feature.
- Kein Eingriff in den Worker/`queue_status`-CHECK (auto-verworfene `neu`-Dokumente dürfen
  harmlos durch den Worker laufen).
- Keine generischen Queue-Filter-Chips (Klasse/Konfidenz/Badges) — das war die ursprüngliche
  TODO-Idee, ist aber nicht das reale Bedürfnis. Bei Bedarf später eigenes Feature.

## Tests (TDD)

**Backend:**
- `rausch_regel`: Domain-Treffer `nur_body`/`komplett`; Nicht-Treffer → `None`;
  Groß-/Kleinschreibung; `From: Name <no-reply@placetel.de>` vs. bare address; leerer/kaputter
  Header → `None`. Loader: gültige YAML lädt; defekte YAML (Wurzel kein List, unbekannte
  Policy, doppelte Domain, fehlende Felder) → `RuntimeError`.
- Adapter-Integration (`verarbeite_email`): (a) Placetel ohne Anhang → Body verworfen,
  Grund `rauschen`, `verworfen_von IS NULL`; (b) Placetel mit PDF → Body verworfen, Anhang
  **nicht** verworfen; (c) beA mit Anhang → Body + Anhang verworfen; (d) beA ohne Anhang →
  Body verworfen; (e) unbekannter Versicherer-Absender → nichts verworfen, bleibt in der Queue.
- `auto_verwerfen`-Helfer: Guard überspringt bereits verworfene/freigegebene Dokumente.
- Routen: `GET /intake/papierkorb` listet nur Verworfene, neueste zuerst, mit Grund/Datum;
  `POST …/wiederherstellen` setzt `verworfen_*` zurück (200) bzw. 409/404 in den Guard-Fällen;
  `hole_queue` blendet Verworfene weiter aus (Regression).
- `post_verwerfen` nutzt den Helfer und verhält sich unverändert (Regression).

**Frontend (Vitest):**
- Queue/Papierkorb-Umschalter rendert die richtige Liste.
- Papierkorb zeigt Grund-Label + „Wiederherstellen"-Knopf; Klick ruft die API und lädt neu.

## Deployment

- **Keine Migration.** Nur neue Konfig-Datei + Code. Die YAML muss mit ausgeliefert werden
  (Teil des Images/Deployments), sonst startet die App fail-loud nicht.
- Feature ist sofort aktiv, sobald der Code läuft — es gibt kein Flag. (Rollback = alter Code.)
