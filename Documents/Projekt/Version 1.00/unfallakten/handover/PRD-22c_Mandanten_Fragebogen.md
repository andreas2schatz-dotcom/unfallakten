# PRD-22c – Mandanten-Fragebogen (Website → E-Mail-Import → Akte)
> Erstellt: 2026-04-03  
> Status: Bereit zur Implementierung (Session 1)  
> Abhängigkeiten: E-Mail-Import (Modul 7) ✅ live  
> Schema-Version: JSON 2.0 (unfallbogen-json-schema.md)

---

## Ziel

Mandanten füllen auf der Kanzlei-Website einen Unfall-Fragebogen aus (HTML-Formular
oder geführter Chat). Die Daten kommen als **JSON-Datei-Anhang** an `unfall@anwalt-offenbach.de`.
Der E-Mail-Import erkennt diese E-Mails, parst den Anhang und:

- **bestehende Akte**: reichert die Akte mit Fragebogen-Daten an (nur fehlende Felder füllen)
- **neuer Mandant**: legt Stub-Eintrag in `fragebogen_erstkontakt` an (Akte-Anlage = PRD-22d)

---

## Zwei Haupt-Flows

```
Website-Fragebogen
       │
       ├─ meta.aktenzeichen != null?
       │
       ├── JA  → Bestehende-Akte-Flow
       │          Akte in DB suchen → Daten ergänzen
       │
       └── NEIN → Neuer-Mandant-Flow (STUB)
                   Eintrag in fragebogen_erstkontakt anlegen
                   Vollständige Akte-Anlage: PRD-22d (späteres Modul)
```

---

## Erkennungslogik

**Drei Erkennungsmerkmale (alle drei werden geprüft):**

| Merkmal | Wert | Regex |
|---|---|---|
| Betreff | `Unfallbogen: [Name] – YYYY-MM-DD` | `^Unfallbogen:\s+.+\s+–\s+\d{4}-\d{2}-\d{2}` |
| Anhang-Dateiname | `unfallbogen_[Name]_[Datum].json` | `^unfallbogen_.*\.json$` |
| JSON-Inhalt | `meta.formular == "unfallbogen"` | finale Prüfung nach Parse |

**Implementierung in `import_service.py`:**

```python
def _ist_fragebogen_email(parsed: dict) -> bool:
    """Schnell-Check: Betreff oder JSON-Anhang erkennbar?"""
    betreff = parsed.get("betreff", "")
    if re.match(r"^Unfallbogen:\s+.+\s+[-–]\s+\d{4}-\d{2}-\d{2}", betreff):
        return True
    for anh in parsed.get("anhaenge_roh", []):  # neue Liste, s.u.
        if re.match(r"^unfallbogen_.*\.json$", anh.get("dateiname", ""), re.IGNORECASE):
            return True
    return False
```

---

## Änderungen am bestehenden E-Mail-Parser

### `email_parser.py` – JSON-Anhänge extrahieren

Die aktuelle `ERLAUBTE_ENDUNGEN`-Liste enthält kein JSON. Es braucht eine
**separate** Extraktion für `.json`-Anhänge (nicht über den normalen Anhang-Pfad):

```python
# Neue Hilfsfunktion in email_parser.py
def extrahiere_json_anhaenge(msg: EmailMessage) -> list:
    """
    Gibt Liste von dicts zurück:
    [{"dateiname": "unfallbogen_...json", "inhalt": bytes}, ...]
    Nur .json-Dateien, keine anderen Typen.
    """
```

`parse_email()` wird um `anhaenge_json` im Rückgabe-Dict erweitert.
Die normalen PDF/DOCX-Anhänge bleiben unverändert.

---

## Neues Modul `fragebogen_parser.py`

**Datei:** `backend/email_import/fragebogen_parser.py`

```python
def parse_fragebogen_anhang(json_bytes: bytes) -> dict:
    """
    Parst JSON-Anhang-Bytes zu strukturiertem Dict.
    Prüft meta.formular == "unfallbogen" und meta.version.
    Gibt None zurück wenn kein gültiger Unfallbogen.
    
    Rückgabe:
    {
        "meta":           dict,
        "hat_aktenzeichen": bool,
        "aktenzeichen":   str|None,   # normiert via _normiere_az_basis()
        "mandant":        dict,
        "gegner":         dict,
        "unfall":         dict,
        "sachschaden":    dict,
        "personenschaden": dict|None,
        "_roh":           dict,       # Original-JSON
    }
    """
```

---

## Feldmapping: JSON → DB

### `mandant` → `beteiligte` (rolle = "mandant")

| JSON | DB-Feld | Konvertierung |
|---|---|---|
| `mandant.name` | `name` | direkt |
| `mandant.vorname` | `vorname` | direkt |
| `mandant.strasse` | `strasse` | direkt |
| `mandant.plz` | `plz` | direkt |
| `mandant.ort` | `ort` | direkt |
| `mandant.email` | `email` | direkt |
| `mandant.telefon` | `telefon` | direkt |
| `mandant.iban` | `iban` | direkt |
| `mandant.vorsteuerabzug` | `vorsteuer` | `"ja"` → `"Y"`, `"nein"` → `"N"` |

### `gegner.fahrer/halter` → `beteiligte` (rolle = "unfallgegner")

| JSON | DB-Feld |
|---|---|
| `gegner.fahrer` | `name` |
| `gegner.fahrzeug.kennzeichen` | `kfz_kennzeichen` |
| `gegner.fahrzeug.fabrikat` | notiz (Freitext) |

### `gegner.versicherung` → `beteiligte` (rolle = "versicherung")

| JSON | DB-Feld |
|---|---|
| `gegner.versicherung.name` | `name` |
| `gegner.versicherung.nummer` | `telefon` (Hilfsspalte bis eigenes Feld vorhanden) |
| `gegner.versicherung.schadennummer` | `notiz` |

### `unfall` → `unfalldetails`-Tabelle

| JSON | DB-Feld |
|---|---|
| `unfall.datum` | `schadentag` |
| `unfall.zeit` | `unfallzeit` (falls Spalte vorhanden, sonst in `schilderung` prefixen) |
| `unfall.ort` | `unfallort` (falls Spalte vorhanden) |
| `unfall.schilderung` | `schilderung` |
| `unfall.polizei.aktenzeichen` | `polizei_az` (falls Spalte vorhanden) |

> **Hinweis:** Vor Implementierung `unfalldetails`-Schema prüfen – nur vorhandene Spalten befüllen.
> Fehlende Spalten werden als JSON in einer `fragebogen_extras_json`-Spalte gespeichert.

### `sachschaden` → kein direktes Mapping

Sachschadenpositionen (Fahrzeugdaten, Versicherungen) haben keine direkte
Entsprechung in der `schaden`-Tabelle → werden als JSON in
`fragebogen_erstkontakt.json_roh` gespeichert und stehen dem Sachbearbeiter
zur Verfügung.

### `personenschaden` → `personenschaden`-Tabelle (nur wenn != null)

| JSON | DB-Feld |
|---|---|
| `personenschaden.verletzter.geburtsdatum` | `geburtsdatum` (falls Spalte vorhanden) |
| `personenschaden.verletzungen` | `verletzungsbeschreibung` (falls Spalte vorhanden) |
| `personenschaden.krankenhaus.*` | Freitext-Felder |
| `personenschaden.hauskrank.*` | Freitext-Felder |

> Gleiche Regel: nur vorhandene Spalten befüllen, Rest in `fragebogen_extras_json`.

---

## Bestehende-Akte-Flow (Detail)

```python
def _fragebogen_bestehende_akte(fragebogen, parsed, bericht, bearbeiter_id):
    az = fragebogen["aktenzeichen"]
    
    # 1. Akte suchen
    akte_az = _stelle_sqlite_akte_sicher(az)  # legt ggf. on-demand an
    if not akte_az:
        # AZ nicht erkannt → als nicht_zugeordnet loggen mit Flagge
        _log_fragebogen_fehler(fragebogen, parsed, "az_nicht_gefunden")
        return
    
    # 2. Mandant prüfen/ergänzen (NUR wenn noch kein Mandant vorhanden)
    _ergaenze_mandant(akte_az, fragebogen["mandant"])
    
    # 3. Unfallgegner prüfen/ergänzen
    _ergaenze_gegner(akte_az, fragebogen["gegner"])
    
    # 4. Unfalldetails einspielen (nur leere Felder)
    _ergaenze_unfalldetails(akte_az, fragebogen["unfall"])
    
    # 5. Personenschaden (falls vorhanden)
    if fragebogen["personenschaden"]:
        _ergaenze_personenschaden(akte_az, fragebogen["personenschaden"])
    
    # 6. JSON als Dokument ablegen (Audit-Trail)
    _speichere_fragebogen_json(akte_az, fragebogen["_roh"], up_dir)
    
    # 7. Log
    bericht["verarbeitet"] += 1
    _log_import(akte_az, "fragebogen_zugeordnet", parsed, fragebogen)
```

**Kritische Regel:** `_ergaenze_*`-Funktionen **nur** wenn Zielfeld leer/null ist.
Keine bestehenden Daten überschreiben.

---

## Neuer-Mandant-Flow (STUB)

```python
def _fragebogen_neuer_mandant_stub(fragebogen, parsed, bericht, bearbeiter_id):
    """
    Stub: Nur Datensicherung. Keine echte Akte-Anlage.
    Akte-Anlage wird in PRD-22d implementiert.
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO fragebogen_erstkontakt
                (absender_email, absender_name, message_id, json_roh,
                 mandant_name, mandant_email, kfz_kennzeichen, schadentag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            parsed.get("absender_email"),
            parsed.get("absender_name"),
            parsed.get("message_id"),
            json.dumps(fragebogen["_roh"], ensure_ascii=False),
            fragebogen["mandant"].get("name"),
            fragebogen["mandant"].get("email"),
            fragebogen["gegner"].get("fahrzeug", {}).get("kennzeichen"),
            fragebogen["unfall"].get("datum"),
        ))
        conn.commit()
    bericht["verarbeitet"] += 1
```

---

## Schema-Migration 30: `fragebogen_erstkontakt`

```sql
CREATE TABLE IF NOT EXISTS fragebogen_erstkontakt (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    empfangen_am    TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    absender_email  TEXT,
    absender_name   TEXT,
    message_id      TEXT UNIQUE,
    json_roh        TEXT NOT NULL,
    mandant_name    TEXT,
    mandant_email   TEXT,
    kfz_kennzeichen TEXT,
    schadentag      TEXT,
    status          TEXT NOT NULL DEFAULT 'neu',
    akte_az         TEXT
);
```

---

## IMAP-Konfiguration

Der bestehende Import-Service nutzt `EMAIL_HOST`, `EMAIL_USER`, `EMAIL_PASSWORD`.
Die Website-Doku nennt `SMTP_USER_UNFALL` / `SMTP_PASS_UNFALL`.

→ **In Session 1 prüfen:** welche `.env`-Variablen der laufende Import-Service
  für `unfall@` tatsächlich nutzt. Ggf. muss die IMAP-Konfiguration um ein
  zweites Konto erweitert werden oder die Variablen werden gemappt.

---

## Session-Planung

| Session | Inhalt | Status |
|---|---|---|
| 1 | `email_parser.py` JSON-Extraktion + `fragebogen_parser.py` + Erkennungslogik + Schema-Migration 30 | ⬜ |
| 2 | Bestehende-Akte-Flow: `_ergaenze_*`-Funktionen + unfalldetails-Schema prüfen | ⬜ |
| 3 | Neuer-Mandant-Stub + `_fragebogen_neuer_mandant_stub` | ⬜ |
| 4 | Frontend: `fragebogen_erstkontakt`-Liste in EmailImportView | ⬜ |
| 5 | Tests + Abnahme | ⬜ |

---

## Kritische Regeln

- ⛔ Bestehende Akte-Daten **niemals überschreiben** – nur ergänzen wenn Zielfeld leer
- ⛔ Kein Schreibzugriff auf RA-MICRO
- ⛔ JSON-Anhang-Fehler graceful → `fragebogen_fehler`-Log, E-Mail nicht verlieren
- ⛔ JSON-Anhänge über **separaten Pfad** extrahieren – normaler Anhang-Pfad (PDF/DOCX) bleibt unverändert
- `meta.formular == "unfallbogen"` ist **Pflicht-Check** vor jeder Verarbeitung
- Schema-Version prüfen: `meta.version` – bei unbekannter Version warnen, trotzdem importieren
- Akte-Anlage (PRD-22d) ist bewusst ausgelagert
