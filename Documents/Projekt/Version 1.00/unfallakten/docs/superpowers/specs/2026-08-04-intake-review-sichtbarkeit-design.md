# Design-Spec: Ausstehende Intake-Dokumente in der Akte sichtbar machen

Datum: 2026-08-04
Status: freigegeben (Brainstorming), wartet auf Spec-Review

## 1. Problem

Seit `INTAKE_REVIEW_PFLICHT` läuft jeder Upload/Import über die Review-Queue:
Ein Dokument liegt zwischen Upload und Freigabe in `intake_dokumente`
(`queue_status`: `neu` → `laeuft` → `bereit_zur_review` → `freigegeben`,
Fehlerzweig `pipeline_fehler`). In dieser Phase ist es **nirgends in der Akte
sichtbar**:
- Die **ReviewQueue** zeigt nur `queue_status IN ('bereit_zur_review','pipeline_fehler')`
  (global, nicht je Akte) — ein `neu`/`laeuft`-Dokument fällt durch.
- Die **Dokumentenkachel** (`DokumenteSection`) liest ausschließlich die
  Tabelle `dokumente`, die erst bei Freigabe befüllt wird.

Folge: Ein frisch importiertes Dokument „verschwindet" aus Sicht der Akte, bis
es freigegeben ist. Das hat zudem einen wochenlangen, stillen Worker-Ausfall
verdeckt (16 Dokumente auf `neu` festhängend) — behoben durch
`SCHEDULER_LEASE_DISABLED=1` im Dev (Commit `4b0a99bc`).

## 2. Ziel

In der Dokumentenkachel einer Akte die **noch nicht freigegebenen**
Intake-Dokumente dieser Akte anzeigen — mit Status-Badge und einem Link, der die
ReviewQueue **auf genau dieses Dokument** öffnet. Das gibt Sichtbarkeit ab dem
Upload und wirkt als Frühwarnung, wenn Dokumente hängen bleiben.

## 3. Datenmodell-Kontext

- `intake_dokumente` hat **keine** Akte-Spalte. Die Akte-Zuordnung liegt je
  Quelle unterschiedlich vor:
  - **E-Akte-Import** (`quelle='eakte'`): AZ in `zustellungen.signale_json` (`$.az`).
  - **Manueller Upload** (`POST /akten/<id>/dokumente`): `ziel_akte=akte_id`,
    `zustellungen.roh_referenz='upload/akte:<akte_id>'`.
  - **E-Mail-Import**: kein sicherer AZ → nur Matching-Kandidaten
    (`intake_dokumente.parse_json.$.akten_kandidaten`, erst nach Verarbeitung).
- `zustellungen` verknüpft je Intake-Dokument die Herkunft
  (`intake_dokument_id`, `quelle`, `signale_json`, `roh_referenz`).
- Fest wird die Akte erst bei Freigabe (`freigaben.akte_az` + `dokumente`-Zeile).

## 4. Backend: neuer Endpoint

`GET /akten/<akte_az>/intake-pending`

Liefert die nicht-freigegebenen, nicht-verworfenen Intake-Dokumente **dieser
Akte**:

```json
[
  { "intake_id": 461, "bezeichnung": "…", "klasse": "abrechnungsschreiben",
    "queue_status": "bereit_zur_review", "erstellt_am": "2026-08-04 06:19:47" }
]
```

Filter: `queue_status NOT IN ('freigegeben')` UND `verworfen_am IS NULL`.

**Akte-Ableitung je Dokument (Union aller Quellen, umgesetzt in `921581f9`):**
Ein Dokument wird der angefragten Akte zugeordnet, wenn deren Basis-AZ mit
**irgendeiner** der folgenden Quellen übereinstimmt — über **alle** Zustellungen
des Dokuments hinweg (globale sha256-Dedup ⇒ ein `intake_dokumente` kann mehrere
`zustellungen` haben):
1. `zustellungen.signale_json` → `$.az` (E-Akte und Upload) je Zustellung.
2. `zustellungen.roh_referenz` `upload/akte:<akte_id>` → `akte_id` je Zustellung.
3. `intake_dokumente.parse_json` → `$.akten_kandidaten[0].akte_az` (Matching-Kandidat).

Anders als eine strikte „erste-nicht-leere"-Präzedenz wird der Matching-Kandidat
(3) **immer** mitgeprüft, nicht nur bei fehlendem Signal-AZ. Ein Dokument mit
sicherem Signal-AZ `A`, das zusätzlich einen abweichenden Kandidaten `B` trägt,
erscheint dadurch als ausstehend **sowohl** unter `A` als auch unter `B`. Das ist
gewollte Über-Inklusion im Sinne der bekannten Grenze unten (kann eine korrekte
Akte nie verbergen); die Review löst es auf. AZ-Normalisierung analog zum
bestehenden `_az_basis` (siehe `akten_matching`/`intake_routes.py:68`), auf beiden
Seiten des Vergleichs.

Motivation der Union (statt nur der frühesten Zustellung): Traf ein Dokument
zuerst ohne AZ ein (z. B. `quelle='imap'`) und später mit AZ (Upload mit
`ziel_akte`), wurde es unter der frühesten-Zustellung-Logik aus seiner Akte
**verborgen** — der eigentliche Bug, den dieses Feature sichtbar machen soll.

**Bekannte Grenze:** Für E-Mail-Importe ohne sicheren AZ beruht die Zuordnung
nur auf dem obersten Matching-Kandidaten — ein Dokument kann dann unter der
wahrscheinlichen statt der endgültigen Akte erscheinen. Das löst die Review
ohnehin auf. Bewusst akzeptiert (kein Over-Engineering).

## 5. Frontend: Dokumentenkachel

Neuer Bereich **oben** in `DokumenteSection`, über den freigegebenen Dokumenten.
Lädt `GET /akten/<az>/intake-pending` beim Öffnen der Akte (und nach Freigabe).
Je Eintrag eine Zeile: Bezeichnung/Klasse · Eingangsdatum · **Status-Badge** ·
Link **„Zur Review →"**.

Status-Badges (Farbtokens aus `theme.js`, keine Roh-Hexwerte):
| queue_status | Badge-Text | Farbe |
|---|---|---|
| `neu`, `laeuft` | „Wird verarbeitet" | neutral/grau |
| `bereit_zur_review` | „Review ausstehend" | amber |
| `pipeline_fehler` | „Fehler – prüfen" | rot |

Bei `neu`/`laeuft` ist noch kein Review möglich → der Link führt zur Queue, das
Dokument ist dort aber noch nicht reviewbar (Badge kommuniziert das).

Ist die Liste leer, wird der Bereich **nicht** gerendert (kein leerer Kasten).

## 6. Frontend: Navigation zum Dokument

Nach bestehendem `initial…`-Muster (`pendingEinstellungenTab`,
`initialEmailId`):
- Neuer App-State `pendingReviewIntakeId`.
- Klick auf „Zur Review →" ruft einen Callback `onOpenReview(intakeId)` (von
  `App` an die Akten-Ansicht/`DokumenteSection` durchgereicht), der
  `setActive("review-queue")` + `setPendingReviewIntakeId(intakeId)` setzt.
- `ReviewQueueView` bekommt `initialIntakeId` und öffnet beim Mount das Detail
  dieses Dokuments (nutzt den bestehenden Detail-/Auswahl-Mechanismus; setzt
  danach den Pending-State zurück, analog `onTabMounted`).

## 7. Scope

- **Kein** Live-Polling/Auto-Refresh der Badges im MVP. Liste lädt beim Öffnen
  der Akte und nach einer Freigabe neu.
- Keine Änderung an der Queue-Statusmaschine, am Upload-Gate oder an der
  Freigabe-Logik.

## 8. Teststrategie

- **Backend:** Unit/Router-Test für `/akten/<az>/intake-pending`: (a) E-Akte-Dok
  mit AZ im Signal wird der Akte zugeordnet; (b) manueller Upload über
  `ziel_akte`; (c) freigegebene/verworfene Dokumente erscheinen NICHT; (d)
  fremde Akte erscheint nicht. Fixtures in `intake_dokumente`+`zustellungen`.
- **Frontend:** Komponententest, dass die drei Badges je `queue_status`
  gerendert werden und der Link `onOpenReview(intakeId)` mit korrekter ID
  auslöst; leere Liste → kein Bereich.
- Browser-Nachtest: Import in eine Testakte → Zeile „Review ausstehend" in der
  Kachel → Link öffnet das Dokument in der ReviewQueue.

## 9. Bekannte Fallen

- RA-MICRO read-only — nur SQLite lesen.
- AZ-Normalisierung muss dieselbe Basis-Logik nutzen wie das bestehende
  Matching, sonst greift der Akte-Vergleich nicht (führende Nullen, Suffixe).
- `intake_dokumente.bezeichnung` kann leer sein (vor Verarbeitung) → Fallback
  auf Dateiname/Klasse/`„(unbenannt)"`.
