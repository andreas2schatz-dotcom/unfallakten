# PRD-25c – Automatische Mandantenkommunikation
> Erstellt: 2026-04-03  
> Status: Bereit zur Implementierung  
> Abhängigkeiten: word_service.py ✅, beteiligte (E-Mail-Adresse) ✅, SMTP ✅  

---

## Ziel

Nach definierten Ereignissen erscheint ein **E-Mail-Entwurf-Dialog** mit vorausgefülltem
Text und 3 wählbaren Textbausteinen. Der Sachbearbeiter kann den Text bearbeiten und
mit einem Klick an den Mandanten versenden. Grundsatz: **kein vollautomatischer Versand**
— der Sachbearbeiter bestätigt immer.

---

## Auslöser und Textbausteine

### Trigger 1 – Forderungsschreiben generiert

**E-Mail-Betreff:** `Ihre Unfallsache – Forderungsschreiben versandt [AZ {az}]`

**3 Varianten:**
```
A (Standard):
Sehr geehrte/r {mandant_anrede},
wir haben heute in Ihrer Unfallsache das Forderungsschreiben an die
Haftpflichtversicherung {versicherer_name} versandt.
Wir erwarten eine Antwort innerhalb von 4 Wochen und halten Sie informiert.
Mit freundlichen Grüßen

B (Kurz):
in Ihrer Sache haben wir heute die Schadensersatzforderung i.H.v. {betrag_gesamt} €
an {versicherer_name} übermittelt. Sobald eine Antwort vorliegt, melden wir uns.

C (Ausführlich mit Fristhinweis):
wir haben heute das Forderungsschreiben versandt. Gemäß §3a PflVG hat der Versicherer
nun 3 Monate Zeit zur Regulierung (Frist: {pflvg_datum}). Sollte bis dahin keine
zufriedenstellende Antwort vorliegen, werden wir weitere Schritte einleiten.
```

---

### Trigger 2 – Regulierungsschreiben eingegangen (E-Mail-Import)

**Auslöser:** `email_import_log.email_typ = 'regulierungsschreiben'` AND `status = 'zugeordnet'`  
**Betreff:** `Ihre Unfallsache – Schreiben des Versicherers eingegangen [AZ {az}]`

**3 Varianten:**
```
A (Standard):
wir haben heute ein Schreiben von {versicherer_name} erhalten und werden es prüfen.
Wir melden uns mit einer Einschätzung in Kürze.

B (mit Regulierungsbetrag, falls erkannt):
wir haben ein Regulierungsangebot über {regulierungs_betrag} € erhalten.
Wir prüfen dieses und informieren Sie über das weitere Vorgehen.

C (bei Ablehnung):
wir haben eine Ablehnung / Teilregulierung des Versicherers erhalten.
Wir prüfen das Schreiben und melden uns mit unserem Vorschlag zum weiteren Vorgehen.
```

---

### Trigger 3 – Dokument generiert (Abrechnungsübersicht)

**Betreff:** `Ihre Unfallsache – Abrechnungsübersicht [AZ {az}]`

**3 Varianten:**
```
A: Anbei erhalten Sie die aktuelle Übersicht über den Stand Ihrer Schadensregulierung.

B: anbei finden Sie die Aufstellung aller geltend gemachten Positionen und
den aktuellen Regulierungsstand.

C (bei Abschluss): Wir freuen uns Ihnen mitteilen zu können, dass Ihre Unfallsache
abgeschlossen werden konnte. Anbei die abschließende Abrechnungsübersicht.
```

---

## Dialog-Komponente: `MandantenEmailDialog.jsx`

### Verhalten

1. Erscheint **automatisch** nach Generierung eines auslösenden Dokuments
   (als Modal über dem bestehenden WordSection-Bereich)
2. Vorausgefüllt mit: Mandant-Name, Versicherer-Name, Beträge aus dem generierten Dokument
3. **Textbaustein-Selector**: 3 Buttons (A / B / C) wechseln den Fließtext
4. **Freitext-Editor**: Textarea, vollständig editierbar
5. **Anhang**: generiertes PDF automatisch angehängt (Checkbox, default: an)
6. **Absender**: `unfall@anwalt-offenbach.de` (nicht änderbar)
7. **Empfänger**: Mandant E-Mail aus Beteiligte — editierbar für Korrekturen
8. **Buttons**: `Senden` / `Entwurf speichern` / `Überspringen`
9. **Entwurf speichern**: Speichert in neue Tabelle `mandanten_emails` mit `status='entwurf'`

### Props

```jsx
<MandantenEmailDialog
  akteAz={az}
  trigger="forderungsschreiben"   // 'forderungsschreiben'|'regulierungsschreiben'|'abrechnungsuebersicht'
  dokId={dokId}                   // generiertes Dokument
  mandant={mandant}               // {id, name, email, anrede}
  versicherer={versicherer}       // {name}
  betrag={betragGesamt}           // optional
  onClose={() => setDialog(null)}
/>
```

---

## Backend

### Neuer Endpunkt

```
POST /akten/<az>/mandanten-email
Body: { betreff, text, empfaenger, dok_id, anhang_mitsenden }
```

Sendet E-Mail via SMTP (`unfall@anwalt-offenbach.de`) und legt Aktivität an:
`"✉ E-Mail an Mandant gesendet: {betreff}"`.

### Neue Tabelle: `mandanten_emails`

```sql
CREATE TABLE mandanten_emails (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_az      TEXT NOT NULL REFERENCES unfallakte(az),
    betreff      TEXT NOT NULL,
    text         TEXT NOT NULL,
    empfaenger   TEXT NOT NULL,
    dok_id       INTEGER REFERENCES dokumente(id),
    trigger_typ  TEXT,   -- 'forderungsschreiben'|'regulierungsschreiben'|'abrechnungsuebersicht'|'manuell'
    status       TEXT NOT NULL DEFAULT 'gesendet'  -- 'gesendet'|'entwurf'
    gesendet_am  TEXT,
    erstellt_am  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
```

Diese Tabelle bildet die **Kommunikationschronik** mit dem Mandanten —
wichtig für PRD-25d (Aktenchronik).

---

## Session-Plan

| Session | Inhalt |
|---|---|
| 1 | Schema-Migration `mandanten_emails` + POST-Endpunkt + SMTP-Integration |
| 2 | `MandantenEmailDialog.jsx` mit Varianten-Selector + Textarea |
| 3 | Integration in WordSection.jsx (nach Generierung öffnen) + Regulierungsschreiben-Trigger in email_import |
| 4 | Test + Abnahme |

---

## Abgrenzung

- Kein automatischer Versand ohne Bestätigung
- Kein E-Mail-Eingang (IMAP) — nur ausgehend
- Textbausteine sind hardcoded in Phase 1; Konfiguration via UI in einem späteren PRD
