# PRD-32 – Rechnungstypen-Parser: Subklassifizierung & Beleg-Mapping
> Erstellt: 2026-04-12 · Status: Planung

---

## Problem

Der aktuelle `rechnung_parser.py` (PRD-23b) extrahiert Brutto/Netto/MwSt aus beliebigen Rechnungen – erkennt aber **nicht welche Art** von Rechnung vorliegt. Das führt dazu, dass z. B. eine Standkostenrechnung zwar als `"rechnung"` klassifiziert wird, aber nicht automatisch der richtigen Schadenposition (`standkosten`) zugeordnet werden kann.

**Konkrete Lücken:**

| Rechnungstyp | Dokumentenklasse (Ist) | Position-Key (Soll) | Status |
|---|---|---|---|
| Abschlepprechnung | `rechnung` | `abschleppkosten` | ⚠️ nur via Firmenname-Heuristik |
| Standkostenrechnung | `rechnung` | `standkosten` | ❌ fehlt in `_KLASSE_POSITION_MAP` |
| Mietwagenrechnung | `mietwagenrechnung` | `mietwagenkosten_netto` | ✓ teilweise |
| Reparaturrechnung | `reparaturrechnung` | `rep_rechnung_netto` | ✓ teilweise |
| SV-Honorarrechnung | `sv_rechnung` | `sv_kosten` | ✓ funktioniert |

---

## Ziel

1. **Subklassifizierung** in `document_classifier.py`:
   Aus dem generischen `"rechnung"` werden spezifische Klassen:
   - `standkostenrechnung`
   - `abschlepprechnung`
   - `mietwagenrechnung`
   - `reparaturrechnung`
   - `unkostenpauschale_rechnung` (Pauschalen-Nachweis)

2. **`_KLASSE_POSITION_MAP` in `belege_routes.py` ergänzen**:
   `standkostenrechnung` → `standkosten_netto` eintragen.

3. **Optionale Parser-Erweiterung** für Standkosten:
   Tage × Tagessatz extrahieren wenn im Text vorhanden
   (z. B. „5 Tage à 12,00 € = 60,00 €").

---

## Erkennungssignale (Entwurf)

### `standkostenrechnung`
```
"standgeld", "standkosten", "standgebühr",
"bereitstellungsgebühr", "abstellgebühr",
"fahrzeug steht", "einstellgebühr",
"tage à", "tag à", "/tag"
```

### `abschlepprechnung`
```
"abschleppen", "abschleppkosten", "abschleppfahrzeug",
"bergung", "bergekosten", "pannenhilfe",
"anfahrt pannendienst", "rückschlepp", "umsetzkosten",
"inkasso abschlepp"
```

### `mietwagenrechnung`
```
"mietwagen", "leihfahrzeug", "leihwagen",
"mietfahrzeug", "fahrzeugmiete",
"mietzeitraum", "mietdauer"
```

### `reparaturrechnung`
```
"reparaturrechnung", "werkstattrechnung",
"instandsetzung", "karosseriearbeiten",
"lackierarbeiten", "materialkosten"
```

---

## Architektur-Änderungen

### 1. `backend/parsers/document_classifier.py`
- Neue Signallisten: `standkosten_signals`, `abschlepp_signals`, `mietwagen_signals`, `reparatur_signals`
- Nach `rg_score >= 2` → zweite Ebene: Subtyp-Bestimmung
- Gibt spezifische `dokumenttyp`-Strings zurück statt generisch `"rechnung"`

### 2. `backend/routers/belege_routes.py`
- `_KLASSE_POSITION_MAP` ergänzen:
  ```python
  "standkostenrechnung":   "standkosten",
  "abschlepprechnung":     "abschleppkosten",
  ```

### 3. `backend/parsers/rechnung_parser.py` (optional, Phase 2)
- `parse_standkosten(text)`: Tage + Tagessatz aus Muster extrahieren
- Gibt zusätzlich `tage: int` und `tagessatz: float` zurück

### 4. Registry-Erweiterung (`backend/config/registry.json`)
- Marker für `standkostenrechnung` und `abschlepprechnung` ergänzen

---

## Implementierungsreihenfolge

1. Echte Belege sammeln (Ist-Zustand prüfen): Welche Schlüsselwörter kommen in vorhandenen Rechnungen vor?
2. Signallisten definieren (Classifier)
3. `document_classifier.py` anpassen + testen
4. `_KLASSE_POSITION_MAP` ergänzen
5. `rechnung_parser.py` Phase 2 (Tage × Tagessatz) – nur wenn Bedarf besteht

---

## Kritische Dateien

| Datei | Änderung |
|---|---|
| `backend/parsers/document_classifier.py` | Subklassen-Signale + Entscheidungslogik |
| `backend/routers/belege_routes.py` | `_KLASSE_POSITION_MAP` ergänzen |
| `backend/parsers/rechnung_parser.py` | Optional: Tage/Tagessatz bei Standkosten |
| `backend/config/registry.json` | Marker für neue Klassen |

---

## Verifikation

- Standkostenrechnung (z. B. Abstellgebühr Abschleppunternehmen) → `standkostenrechnung` → `standkosten`-Position
- Abschlepprechnung → `abschlepprechnung` → `abschleppkosten`-Position
- Bestehende SV-Rechnungen weiterhin korrekt als `sv_rechnung` erkannt
- Kein Rückschritt bei Abrechnungsschreiben/Prüfberichten
