# PRD-25d – Intelligente Sachstandsanfrage
> Erstellt: 2026-04-03  
> Status: Bereit zur Implementierung  
> Abhängigkeiten: aktivitaeten ✅, todos ✅, dokumente ✅, word_service.py ✅  

---

## Ziel

Die bestehende Sachstandsanfrage-Generierung ist zu generisch. Sie nimmt keinen Bezug
auf den konkreten Stand der Akte. Die neue Version:

1. **Analysiert die Aktenchronik** (letzte Schreiben, ausstehende Antworten, Fristlage)
2. **Wählt automatisch die richtige Eskalationsstufe** (Erstanfrage / Zweite Anfrage / Drohung)
3. **Bezieht sich konkret** auf das letzte Forderungsschreiben oder die letzte STA
4. **Macht einen Vorschlag** ob überhaupt STA sinnvoll ist oder ob Klage besser wäre

---

## Eskalations-Stufen

### Stufe 1 – Erstanfrage (freundlich)

**Voraussetzung:** Forderungsschreiben versandt, noch keine Antwort, 14-28 Tage vergangen  
**Ton:** höflich nachfragend

```
Betreff: Unfallsache {mandant_name} – Aktenzeichen {az} – Sachstandsanfrage

wir erlauben uns, Sie an unsere mit Schreiben vom {fs_datum} übermittelte
Schadensersatzforderung in Höhe von {betrag_gesamt} € zu erinnern.
Bis heute liegt uns Ihre Stellungnahme hierzu nicht vor.
Wir bitten Sie, uns bis zum {frist_datum = heute + 14 Tage} mitzuteilen,
ob und in welcher Höhe Sie die geltend gemachten Ansprüche anerkennen.
```

---

### Stufe 2 – Zweite Anfrage (bestimmt)

**Voraussetzung:** Bereits eine STA versandt, noch keine Antwort, weitere 14 Tage vergangen  
**Ton:** bestimmt, mit §3a PflVG-Verweis falls relevant

```
Betreff: 2. Sachstandsanfrage – {az} – LETZTE AUFFORDERUNG

wir haben Sie mit Schreiben vom {fs_datum} zur Regulierung aufgefordert.
Mit weiterer Sachstandsanfrage vom {sta1_datum} haben wir Sie erinnert.
Bis heute ist weder eine Zahlung noch eine begründete Ablehnung erfolgt.
Wir fordern Sie letztmals auf, bis zum {frist_datum = heute + 10 Tage}
Stellung zu nehmen. Anderenfalls behalten wir uns vor, unsere Mandantschaft
gerichtlich gegen Sie vorzugehen.
```

---

### Stufe 3 – Letzte Mahnung / Klage-Ankündigung

**Voraussetzung:** 2 STAs versandt, >42 Tage seit erstem FS, §3a PflVG-Frist abgelaufen  
**Vorschlag:** System empfiehlt Klage statt weiterer STA  

```
⚠ Empfehlung: Klage einleiten
Begründung: 2 Sachstandsanfragen ohne Reaktion. §3a PflVG-Frist abgelaufen.
Weitere Sachstandsanfrage ist nicht sinnvoll.
→ Klage-Wizard öffnen?
```

---

## Kontext-Analyse (Backend)

### Neue Datei: `backend/services/aktenchronik_service.py`

```python
def analysiere_akte(akte_az: str) -> dict:
    """
    Gibt strukturierten Kontext für Sachstandsanfrage zurück.
    
    Returns: {
        "letztes_forderungsschreiben": {"datum": "...", "betrag": ..., "dok_id": ...},
        "letzte_sta": {"datum": "...", "dok_id": ...} | None,
        "sta_anzahl": 2,
        "tage_seit_letztem_fs": 28,
        "pflvg_frist_abgelaufen": False,
        "empfohlene_stufe": 1,  # 1, 2, 3
        "vorschlag": "sta_stufe_2",  # "sta_stufe_1"|"sta_stufe_2"|"klage"
        "offene_positionen": [...],  # Schadenpositionen noch nicht reguliert
        "letzte_antwort_versicherer": {"datum": "...", "typ": "teilregulierung"} | None
    }
    """
```

**Datenquellen:**
- `dokumente` WHERE `dokumentenklasse IN ('forderungsschreiben', 'sachstandsanfrage')` AND `akte_az`
- `todos` WHERE `frist_typ = 'pflvg_3a'`
- `regulierung` + `regulierung_positionen` für offene Positionen
- `email_import_log` WHERE `email_typ IN ('regulierungsschreiben', 'sonstiges')` für letzte Versichererantwort

---

## Neuer Endpunkt

```
GET /akten/<az>/sachstandsanfrage/kontext
```

Response: Kontext-Objekt aus `analysiere_akte(az)` + vorausgefüllter Textbaustein.

```
POST /akten/<az>/sachstandsanfrage/generieren
Body: { stufe: 1|2|3, text_override: "..." }
```

Generiert Word-Dokument (bestehende `sachstandsanfrage.py`) mit dem kontextbezogenen Text,
legt 2-Wochen-Todo an (PRD-25a Regel 3) und Mandanten-Email-Vorschlag (PRD-25c).

---

## Frontend: SachstandsanfrageDialog.jsx

### Aufbau

```
┌─ Sachstandsanfrage ─────────────────────────────────────────┐
│                                                             │
│  Letztes Forderungsschreiben: 10.03.2026  (18.400 €)        │
│  Keine Antwort seit: 24 Tagen                               │
│                                                             │
│  [●] Stufe 1 – Erstanfrage    [ ] Stufe 2    [ ] Stufe 3   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ wir erlauben uns, Sie an unsere mit Schreiben vom   │   │
│  │ 10.03.2026 übermittelte Forderung i.H.v. 18.400 €  │   │
│  │ zu erinnern. Bitte nehmen Sie bis zum 17.04.2026   │   │
│  │ Stellung.                                          │   │
│  │ [editierbar]                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [ Generieren + Word öffnen ]  [ Abbrechen ]               │
└─────────────────────────────────────────────────────────────┘
```

### Integration

Der Dialog wird geöffnet aus:
1. **Action-Dashboard** → Vorschlag-Chip „→ Sachstandsanfrage?" (PRD-25b)
2. **WiedervorlageView** → bestehender Button bleibt, öffnet neuen Dialog
3. **WordSection** → neuer Eintrag in der Dokument-Liste

---

## Session-Plan

| Session | Inhalt |
|---|---|
| 1 | `aktenchronik_service.py` + `analysiere_akte()` + Endpunkt `/kontext` |
| 2 | Stufen-Logik + Textbausteine + Endpunkt `/generieren` |
| 3 | `SachstandsanfrageDialog.jsx` mit Kontext-Anzeige + Stufen-Selector |
| 4 | Integration in Dashboard + WiedervorlageView + WordSection |
| 5 | Test mit realen Akten + Abnahme |

---

## Abgrenzung

- Kein ML/KI — nur regelbasierte Logik auf Basis von Datum, Anzahl Dokumente, Fristlage
- Texte werden vorgeschlagen, nicht zwingend automatisch generiert
- Kein E-Mail-Direktversand aus diesem Dialog (→ geht über PRD-25c MandantenEmailDialog)
