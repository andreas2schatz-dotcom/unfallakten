# PRD-23b – Rechnungs-Parser + Auto-Zuordnung
> Erstellt: Session v40 – 2. April 2026
> Status: Bereit zur Implementierung
> Abhängigkeiten: PRD-23a (schadenposition_belege) ✅ live

---

## Ziel

Rechnungen (Werkstatt, SV, Mietwagen, Abschlepp) automatisch erkennen und
den richtigen Schadenpositionen vorschlagen. Der Sachbearbeiter bestätigt
per Klick – kein manuelles Eintippen von Beträgen.

---

## Architektur: Zwei Quellen, drei Stufen

### Quelle 0 – Lokal importierte Dokumente (Priorität 1)

Wenn ein Sachbearbeiter eine E-Mail mit Rechnungsanhang importiert,
liegt das Dokument bereits in der lokalen `dokumente`-Tabelle.
Der Dispatcher weist `dokumentenklasse = "rechnung"` zu (nach
Registry-Erweiterung, siehe unten).

```
dokumente WHERE akte_id = ? AND dokumentenklasse LIKE 'rechnung%'
  → parse_json enthält bereits geparste Beträge
  → Datei liegt auf /uploads/ (kein Mount nötig)
  → Treffer sofort verfügbar, kein HTTP-Request
```

### Quelle 1 – E-Akte (noch nicht lokal importiert, Priorität 2)

Wenn kein lokales Dokument gefunden → E-Akte Metadaten-Abfrage.
Nur Metadaten (kein Dateilesen), Klassifikation via Beteiligten-Abgleich.

```
tblElo_AktenArchiv WHERE eakte_nr NOT IN (lokale dokumente.eakte_nr)
  → absender_domain vs. beteiligte.email-Domain
  → Firmenname-Keywords wenn kein Domain-Match
  → Dateiname-Keywords als letzter Fallback
```

---

## Schritt 1: Registry-Erweiterung (erster Implementierungsschritt)

**Datei:** `backend/config/registry.json`

Neue generische Marker für die Klasse `"rechnung"`:

```json
"Rechnungsnummer":          { "klasse": "rechnung", "marker_typ": "text" },
"Re.-Nr.":                  { "klasse": "rechnung", "marker_typ": "text" },
"Rg.-Nr.":                  { "klasse": "rechnung", "marker_typ": "text" },
"Zahlungsziel":             { "klasse": "rechnung", "marker_typ": "text" },
"Bitte überweisen Sie":     { "klasse": "rechnung", "marker_typ": "text" },
"Unsere Bankverbindung":    { "klasse": "rechnung", "marker_typ": "text" },
"zzgl. 19% MwSt":           { "klasse": "rechnung", "marker_typ": "text" },
"zzgl. 19 % MwSt":          { "klasse": "rechnung", "marker_typ": "text" },
"Nettobetrag":              { "klasse": "rechnung", "marker_typ": "text" },
"Gesamtbetrag inkl":        { "klasse": "rechnung", "marker_typ": "text" },
"Zu zahlen bis":            { "klasse": "rechnung", "marker_typ": "text" },
"Fällig bis":               { "klasse": "rechnung", "marker_typ": "text" }
```

**Konflikt-Schutz:** Wenn ein Gutachten auch "Nettobetrag" enthält → Konflikt
im Dispatcher → `classify_document()` entscheidet (gutachten-Score höher).
Das ist bestehende Logik, kein Sonderbedarf.

---

## Schritt 2: Neuer Endpunkt `GET /akten/<az>/belege/kandidaten`

**Datei:** `backend/routers/belege_routes.py`

Gibt alle Rechnungs-Kandidaten für eine Akte zurück. Zweistufig:

```python
# Stufe 0: Lokale Dokumente
SELECT id, dateiname, dokumentenklasse, parse_json, quelle, hochgeladen_am
FROM dokumente
WHERE akte_id = ? AND dokumentenklasse LIKE 'rechnung%'

# Stufe 1 (nur wenn RAMICRO_AKTIV): E-Akte Metadaten
hole_eakte_dokumente(az, nur_pdf=True)
→ filtern: eakte_nr NOT IN lokale eakte_nrs
→ klassifizieren via Beteiligten-Abgleich (s.u.)
```

**Response-Format:**
```json
{
  "kandidaten": [
    {
      "position_key":    "rep_rechnung_netto",
      "konfidenz":       0.90,
      "grund":           "domain_match",
      "quelle":          "lokal",
      "dok_id":          42,
      "eakte_nr":        null,
      "dateiname":       "Rechnung_Werkstatt_Mueller.pdf",
      "betrag_vorschlag": 3850.00,
      "betrag_ist_netto": true,
      "lieferant":       "Kfz-Müller GmbH"
    }
  ]
}
```

---

## Schritt 3: Beteiligten-Klassifikations-Logik (Backend)

**Datei:** `backend/routers/belege_routes.py` (Hilfsfunktionen)

### `ist_firma(b)` – Port aus KlageSection.jsx:209

```python
def ist_firma(b):
    # type: (Beteiligter) -> bool
    return bool(
        (getattr(b, "anrede", "") or "").lower() == "firma"
        or (not b.vorname and b.rolle != "mandant")
    )
```

### `position_aus_firmenname(name)` – Port aus handelsregister_service._erkenne_rechtsform

```python
FIRMA_POSITION_MAP = [
    (["ABSCHLEPP", "BERGUNG", "PANNENDIENST", "PANNENHILFE"],
     "abschleppkosten"),
    (["MIETWAGEN", "AUTOVERMIET", "LEIHWAGEN",
      "HERTZ", "SIXT", "EUROPCAR", "BUCHBINDER", "AVIS"],
     "mietwagenkosten_netto"),
    (["WERKSTATT", "KAROSSERIE", "LACKIER",
      "REPARATUR", "UNFALLINSTAND", "KFZ-MEISTER"],
     "rep_rechnung_netto"),
    (["STANDPLATZ", "DEPOT", "ABSTELLPLATZ", "LAGERPLATZ"],
     "standkosten_netto"),
]
# sachverstaendiger-Rolle braucht kein Keyword-Lookup (direkt → sv_kosten)

def position_aus_firmenname(name):
    # type: (str) -> Optional[str]
    n = (name or "").upper()
    for keywords, pos_key in FIRMA_POSITION_MAP:
        if any(k in n for k in keywords):
            return pos_key
    return None
```

### SV-Kosten: netto vs. brutto

```python
# Wie in schaden_routes._abrechnungsberechnung:
mandant = next((b for b in beteiligte if b.rolle == "mandant"), None)
vorsteuer = str(getattr(mandant, "vorsteuer", "N") or "N").upper() in ("J", "Y", "1")
sv_position_key = "sv_kosten_netto" if vorsteuer else "sv_kosten"
```

### Domain-Matching

```python
def _domain_aus_email(email):
    # type: (str) -> Optional[str]
    if not email or "@" not in email:
        return None
    return email.split("@")[-1].lower().strip()

def klassifiziere_eakte_dok(dok, beteiligte, vorsteuer):
    # type: (dict, list, bool) -> Optional[dict]
    domain = dok.get("absender_domain", "")

    # sachverstaendiger-Rolle direkt
    for b in beteiligte:
        if b.rolle == "sachverstaendiger":
            if domain and domain == _domain_aus_email(b.email or ""):
                return {"position_key": "sv_kosten_netto" if vorsteuer else "sv_kosten",
                        "konfidenz": 0.90, "grund": "domain_match_sv", "lieferant": b.name}

    # sonstige Firmen
    for b in beteiligte:
        if b.rolle == "sonstiger" and ist_firma(b):
            if domain and domain == _domain_aus_email(b.email or ""):
                pos = position_aus_firmenname(b.name)
                return {"position_key": pos, "konfidenz": 0.90,
                        "grund": "domain_match", "lieferant": b.name}
            # Kein Domain-Match: Firmenname-Heuristik
            pos = position_aus_firmenname(b.name)
            if pos:
                return {"position_key": pos, "konfidenz": 0.60,
                        "grund": "firmenname_keyword", "lieferant": b.name}

    # Dateiname-Fallback
    name_lower = (dok.get("anzeigename") or "").lower()
    if any(k in name_lower for k in ["rg", "re", "rechnung", "invoice", "honorar", "beleg"]):
        return {"position_key": None, "konfidenz": 0.40,
                "grund": "dateiname_keyword", "lieferant": None}

    return None
```

---

## Schritt 4: `rechnung_parser.py` (neues Modul)

**Datei:** `backend/parsers/rechnung_parser.py`

Extrahiert aus Rechnungs-PDFs: Nettobetrag, MwSt, Bruttobetrag, Datum.
Kein Aufbrechen in Einzelpositionen – nur Gesamtbeträge.

```python
GESAMTBETRAG_PATTERNS = [
    r"Gesamtbetrag\s+(?:inkl\.?\s+(?:MwSt|Mehrwertsteuer))?\s+([\d.]+,\d{2})\s*€?",
    r"Rechnungsbetrag\s+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Zu\s+zahlen\s*[:\s]+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Endbetrag\s+([\d.]+,\d{2})\s*(?:EUR|€)",
    r"Zahlungsbetrag\s+([\d.]+,\d{2})\s*(?:EUR|€)",
]
NETTO_PATTERNS = [
    r"Nettobetrag\s+([\d.]+,\d{2})\s*€?",
    r"Summe\s+netto\s+([\d.]+,\d{2})\s*€?",
    r"Betrag\s+ohne\s+MwSt\.?\s+([\d.]+,\d{2})\s*€?",
]
MWST_PATTERNS = [
    r"(?:zzgl\.|zuzüglich|inkl\.)\s+19\s*%\s+(?:MwSt|Mehrwertsteuer)[\s.:]*?([\d.]+,\d{2})",
    r"Mehrwertsteuer\s+19\s*%\s+([\d.]+,\d{2})",
    r"19\s*%\s+MwSt\.\s+([\d.]+,\d{2})",
]
```

Fallback-Kette:
1. Alle drei Muster gefunden → cross-check (brutto ≈ netto × 1.19, Toleranz 1 €)
2. Nur brutto → netto = brutto / 1.19
3. Kein Treffer → Konfidenz 0.0, kein Vorschlag (aber PDF-Preview trotzdem)

---

## Schritt 5: Neuer Endpunkt `POST /akten/<az>/parse-pdf/eakte/<nr>`

**Datei:** `backend/routers/pdf_parse_routes.py`

Analog zu `parse-pdf/dokument/<dok_id>` – aber Quelle ist E-Akte:

```python
@pdf_parse_bp.route("/parse-pdf/eakte/<int:eakte_nr>", methods=["POST"])
def parse_eakte_dokument(akte_id, eakte_nr):
    dok = hole_eakte_dokument(az=akte_id, nr=eakte_nr)
    if not dok:
        return _err("E-Akte-Dokument nicht gefunden.", 404)
    pfad = baue_dateipfad(dok["dateiname"])
    if not pfad:
        return _err("EAKTE_BASE_PATH nicht konfiguriert.", 503)
    try:
        datei_bytes = Path(pfad).read_bytes()
    except OSError:
        return _err("Datei nicht erreichbar – WSL-Mount prüfen.", 503)
    ergebnis = _parse_versicherungs_pdf(datei_bytes)
    return jsonify({"akte_id": akte_id, "eakte_nr": eakte_nr,
                    "dateiname": dok["anzeigename"], "ergebnis": ergebnis})
```

---

## Schritt 6: Frontend – SchadenSection.jsx

### Neue API-Calls

```javascript
// api.js: Kandidaten laden
GET /akten/<az>/belege/kandidaten
→ { kandidaten: [...] }

// on-demand parse (nur E-Akte-Quelle)
POST /akten/<az>/parse-pdf/eakte/<nr>
→ { ergebnis: { schadenpositionen: {...}, parse_konfidenz: 0.87 } }

// PDF-Preview
lokal:  GET /akten/<az>/dokumente/<dok_id>/datei  (existiert)
eakte:  GET /akten/<az>/eakte/<nr>/datei          (existiert)
```

### Inline-Symbol im Formular

```
Rep.-Rechnung netto  [____3.850,00____] [📎]   ← grün: Konfidenz ≥ 0.70
SV-Kosten            [________0,00____] [📎]   ← grau: Konfidenz < 0.70
Mietwagenkosten      [________0,00____]         ← kein Symbol: kein Kandidat
```

### Split-View bei Klick

```
Links:                          Rechts:
position_key-Feld               PDF-Vorschau (iframe, Blob-URL)
Vorschlag: 3.850,00 €           [natives Browser-PDF]
Konfidenz: 90%
Lieferant: Kfz-Müller GmbH

[✓ Übernehmen] [✗ Schließen]
```

Bei `position_key = null` (grau): Dropdown zur manuellen Auswahl statt Vorschlag.

### "Übernehmen" schreibt NUR in form-State

```javascript
// Kein Autocommit. User klickt danach normal "Speichern".
setForm(prev => ({ ...prev, [position_key]: betrag_vorschlag }));
// + schadenposition_belege anlegen:
await apiBelege.zuordnen(akteId, { position_key, dokument_id: dok_id, betrag_aus_beleg: betrag });
```

---

## Schritt 7: handleBatchParser (Dokumenten-Kachel)

**Datei:** `frontend/src/sections/DokumenteSection.jsx:78`

Stub ersetzen durch echten Aufruf:

```javascript
const handleBatchParser = async () => {
  setBatchParserLaden(true);
  try {
    const res = await apiBelege.kandidaten(akteId);
    // Kandidaten in globalem State/Dispatch speichern
    dispatch({ type: "SET_BELEGE_KANDIDATEN", akteId, kandidaten: res.kandidaten });
    setToast(`${res.kandidaten.length} Rechnungskandidat(en) gefunden.`);
  } catch(e) {
    setToast("Batch-Parser fehlgeschlagen: " + (e?.message || ""));
  } finally {
    setBatchParserLaden(false);
  }
};
```

---

## Caching-Strategie

### Lokale Dokumente – `parse_status` + `parse_json` (bereits im Schema)

Die `dokumente`-Tabelle hat bereits:
```sql
parse_status    TEXT  -- 'ausstehend' | 'erfolgreich' | 'fehler' | 'manuell_korrigiert'
parse_konfidenz REAL
parse_json      TEXT  -- Rohes Parse-Ergebnis als JSON
```

`parse_status = 'erfolgreich'` AND `parse_json IS NOT NULL` = geparstes Dokument.
**Kein neues Feld nötig.**

Der `/belege/kandidaten`-Endpunkt prüft zuerst `parse_status`:
- `erfolgreich` → `parse_json` direkt verwenden, kein Re-Parse
- `ausstehend` oder `fehler` → parsen, Ergebnis zurückschreiben:

```python
UPDATE dokumente
SET parse_status = 'erfolgreich', parse_konfidenz = ?, parse_json = ?
WHERE id = ? AND parse_status IN ('ausstehend', 'fehler')
```

### E-Akte-Dokumente – `rechnung_parse_cache` (Schema-Migration 29)

Für noch nicht lokal importierte E-Akte-Dokumente:

```sql
CREATE TABLE IF NOT EXISTS rechnung_parse_cache (
    eakte_nr        INTEGER PRIMARY KEY,
    datei_groesse   INTEGER NOT NULL,
    geparst_am      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    ergebnis_json   TEXT    NOT NULL
);
```

Cache-Key: `(eakte_nr, datei_groesse)`. Gleiche Dateigröße = kein Re-Parse.

### Force Re-Parse (Fallback)

Query-Parameter `?force=true` auf beiden Endpunkten:

```
GET /akten/<az>/belege/kandidaten?force=true
POST /akten/<az>/parse-pdf/eakte/<nr>?force=true
```

Verhalten:
- Lokal: setzt `parse_status = 'ausstehend'` vor dem Parse → schreibt neu
- E-Akte: löscht `rechnung_parse_cache`-Eintrag → parsed neu

Im Frontend: kleines „↺"-Icon neben dem Klage-Symbol für manuellen Re-Parse.

### Übersicht

| Quelle | Cache-Mechanismus | Force Re-Parse |
|---|---|---|
| Lokal importiert | `parse_status` + `parse_json` (bereits vorhanden) | `?force=true` → reset auf 'ausstehend' |
| E-Akte (nicht importiert) | `rechnung_parse_cache(eakte_nr, datei_groesse)` | `?force=true` → Cache löschen |

---

## Session-Planung

| Session | Inhalt | Status |
|---|---|---|
| 1 | Registry-Erweiterung (rechnung-Marker) + `GET /belege/kandidaten` + Beteiligten-Logik | ✅ erledigt 2026-04-02 |
| 2 | `rechnung_parser.py` + `POST parse-pdf/eakte/<nr>` + Schema-Migration 29 | ✅ erledigt 2026-04-02 |
| 3 | Frontend: Inline-Symbol + Split-View + handleBatchParser + Fortschritts-Zähler | ✅ erledigt 2026-04-03 |
| 4 | Tests: `rechnung_parser.py` + `belege_routes.py` Hilfsfunktionen | ✅ erledigt 2026-04-03 |

### Session-1-Ergebnis (2026-04-02)

**`backend/config/registry.json`** – 12 neue Text-Marker mit `"klasse": "rechnung"`:
`Rechnungsnummer`, `Re.-Nr.`, `Rg.-Nr.`, `Zahlungsziel`, `Bitte überweisen Sie`,
`Unsere Bankverbindung`, `zzgl. 19% MwSt`, `zzgl. 19 % MwSt`, `Nettobetrag`,
`Gesamtbetrag inkl`, `Zu zahlen bis`, `Fällig bis`

**`backend/routers/belege_routes.py`** – neuer Endpunkt + Hilfsfunktionen:
- `GET /akten/<az>/belege/kandidaten` – Zweistufige Kandidaten-Abfrage
- `_ist_firma()`, `_position_aus_firmenname()`, `_domain_aus_email()`, `_klassifiziere_eakte_dok()`
- `_KLASSE_POSITION_MAP`: abschlepprechnung/reparaturrechnung/mietwagenrechnung → position_key
- Graceful Degradation: E-Akte-Fehler → leere Liste, kein 500

### Session-2-Ergebnis (2026-04-02)

**`backend/parsers/rechnung_parser.py`** – neues Modul `parse_rechnung(text) → RechnungParseResult`:
- `GESAMTBETRAG_PATTERNS` (8), `NETTO_PATTERNS` (5), `MWST_PATTERNS` (5)
- Fallback-Kette: alle 3 cross-check (Toleranz 2 €) → brutto+netto → brutto+mwst → nur brutto (÷1.19) → nur netto (×1.19) → konfidenz 0.0
- Felder: `nettobetrag`, `mwst_betrag`, `bruttobetrag`, `rechnungsdatum`, `rechnungsnummer`, `konfidenz`, `warnungen`

**`backend/parsers/document_classifier.py`** – rechnung-Typ ergänzt:
- `rechnung_signals` (10 Marker): rechnungsnummer, re.-nr., rg.-nr., zahlungsziel, bitte überweisen sie, unsere bankverbindung, zzgl. 19% mwst, zzgl. 19 % mwst, zu zahlen bis, fällig bis
- `rg_score >= 2 AND rg_score > alle anderen` → `dokumenttyp = "rechnung"`
- Gutachten schlägt Rechnung wenn gt_score höher (bewusste Priorisierung)

**`backend/routers/pdf_parse_routes.py`** – zwei Änderungen:
- `elif meta.dokumenttyp == "rechnung":` Branch in `_parse_versicherungs_pdf()` – ruft `parse_rechnung()`, Response enthält nettobetrag/bruttobetrag/mwst_betrag/rechnungsnummer/rechnungsdatum
- Neuer Endpunkt `POST /akten/<az>/parse-pdf/eakte/<nr>`:
  - Cache-Check via `rechnung_parse_cache` (Cache-Key: eakte_nr + datei_groesse)
  - File-Read via `baue_dateipfad()` (WSL-Mount)
  - Parse → Cache-Write (`ON CONFLICT DO UPDATE`)
  - Query-Param `?force=true` → Cache überspringen
  - Response: `{akte_id, eakte_nr, dateiname, aus_cache, ergebnis}`

**`backend/db/schema_manager.py`** – Migration 29:
- `rechnung_parse_cache(eakte_nr PK, datei_groesse, geparst_am, ergebnis_json)`
- In MIGRATIONS-Dict als Stub + `_run_migration_29()` Funktion + Dispatcher-Branch

**`backend/routers/belege_routes.py`** – `/belege/kandidaten` erweitert:
- Lädt `rechnung_parse_cache` vorab (graceful wenn Tabelle noch nicht existiert)
- E-Akte-Kandidaten erhalten `betrag_vorschlag` + `betrag_ist_netto` aus Cache

### Session-3-Anforderung: Fortschritts-Zähler (neu)

Beim Ausführen des Batch-Parsers (`handleBatchParser`) soll ein Zähler sichtbar sein,
der hochzählt während Dokumente verarbeitet werden.

**Umsetzungsplan (Frontend):**
1. `handleBatchParser` ruft zuerst `GET /akten/<az>/dokumente?klasse=rechnung%25` → erhält Gesamtzahl N
2. Zeigt sofort: `"0 / N Dokumente analysiert..."`
3. Parallel ruft er `GET /belege/kandidaten` auf
4. Während des Ladens: Counter animiert (Intervall ~200ms bis Response kommt)
5. Bei Response: Counter springt auf tatsächliche Zahl, Toast zeigt Ergebnis

**Alternativ (Server-Sent Events, nur wenn Zähler nicht ausreicht):**
`GET /belege/kandidaten/stream` – SSE-Endpoint sendet Progress-Events je Dokument

**Empfehlung:** Animierter Counter reicht für die Kanzlei (Antwort < 2s typisch).

---

## Kritische Regeln für dieses PRD

- ⛔ Kein Schreibzugriff auf raEloakte (nur SELECT in eakte_service.py)
- ⛔ Python 3.9: keine Union-Types, kein Walrus `:=`
- ⛔ Kein Autocommit – User bestätigt Übernahme immer
- ⛔ `ist_firma()` exakt wie KlageSection.jsx:209 portieren (bewährt, kein Abweichen)
- ⛔ Mount-Fehler graceful degradieren: kein Symbol statt Fehler im UI
- SV-Kosten: position_key abhängig von `mandant.vorsteuer` (J → netto, N → brutto)
- `schadenposition_belege` immer mitschreiben beim "Übernehmen" (PRD-23a-Konformität)
