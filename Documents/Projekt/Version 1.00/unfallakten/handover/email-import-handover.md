# E-Mail-Import: Session-Übergabe

**Stand:** 2026-04-03
**Ziel:** Python-Script, das JSON-Anhänge aus dem `unfall@`-Postfach abruft und Daten für die Aktenverwaltung aufbereitet.

---

## Kontext

Die Kanzlei-Website schickt bei jedem ausgefüllten Unfallbogen automatisch eine E-Mail an `unfall@anwalt-offenbach.de` mit:
- **HTML-Body:** Lesbare Zusammenfassung aller Felder
- **JSON-Anhang:** Strukturierte Daten für den automatischen Import (`unfallbogen_[Name]_[Datum].json`)

Das Import-Script soll diese E-Mails per IMAP abholen, die JSON-Dateien auslesen und die Daten weiterverarbeiten.

---

## Erkennungsmerkmale einer Unfallbogen-E-Mail

| Merkmal | Wert | Zuverlässigkeit |
|---------|------|-----------------|
| **Zieladresse** | `unfall@anwalt-offenbach.de` | ★★★ (primärer Filter) |
| **Betreff** | `Unfallbogen: [Vorname] [Nachname] – [YYYY-MM-DD]` | ★★★ |
| **Betreff mit Az.** | `Unfallbogen: Thomas Müller – 2026-03-28 (Az. 123/26)` | ★★★ |
| **Anhang-Dateiname** | `unfallbogen_[Name]_[Datum].json` | ★★★ |
| **JSON-Inhalt** | `meta.formular === "unfallbogen"` | ★★★ (finale Prüfung) |

**Betreff-Regex:** `^Unfallbogen: .+ – \d{4}-\d{2}-\d{2}`
**Dateiname-Regex:** `^unfallbogen_.*\.json$`

---

## JSON-Struktur des Anhangs

Schema-Version: `2.1`
Vollständige Dokumentation: [`docs/unfallbogen-json-schema.md`](./unfallbogen-json-schema.md)

```
{
  "meta": {
    "formular": "unfallbogen",       ← immer dieser Wert
    "version": "2.1",
    "eingegangen": "2026-03-30T14:22:31.000Z",
    "aktenzeichen": "123/26" | null, ← null = neue Akte anlegen
    "gutachter_name": "...",
    "gutachter_aktenzeichen": "..."
  },
  "mandant": { name, vorname, strasse, plz, ort, email, telefon, iban, vorsteuerabzug },
  "gegner":  { fahrer, halter, fahrzeug{art,fabrikat,kennzeichen}, versicherung{name,nummer,schadennummer} },
  "unfall":  { selbst_fahrer, datum, zeit, ort, schilderung, polizei{...}, zeugen, andere_beteiligte },
  "sachschaden": { eigenes_fahrzeug{...}, vollkasko{...}, teilkasko{...}, rechtsschutz{...}, ... },
  "personenschaden": { ... } | null   ← null wenn verletzt = "nein"
}
```

### Import-Logik für Aktenzeichen

```
WENN meta.aktenzeichen != null:
    → Bestehende Akte mit diesem Zeichen suchen
    → Gefunden: Daten zuordnen
    → Nicht gefunden: Warnung + neue Akte anlegen
SONST:
    → Neue Akte anlegen
```

---

## Gewünschtes Verhalten des Import-Scripts

1. IMAP-Verbindung zu `unfall@anwalt-offenbach.de` (Strato-Server)
2. Ungelesene E-Mails filtern: Betreff beginnt mit `Unfallbogen:`
3. JSON-Anhang herunterladen und parsen
4. `meta.formular` prüfen → nur `"unfallbogen"` verarbeiten
5. Aktenzeichen prüfen → Zuordnung oder neue Akte
6. E-Mail nach Verarbeitung als gelesen markieren / in Unterordner `Verarbeitet` verschieben
7. Fehlerhafte E-Mails in Ordner `Fehler` verschieben + Logfile-Eintrag

---

## E-Mail-Zugangsdaten (Strato IMAP)

Die IMAP-Zugangsdaten stehen in `.env.local` im Projekt-Root:

```
SMTP_USER_UNFALL=unfall@anwalt-offenbach.de
SMTP_PASS_UNFALL=...
```

Strato IMAP-Server:
- Host: `imap.strato.de`
- Port: `993` (SSL)

---

## Technische Rahmenbedingungen

- **Sprache:** Python (wie `tools/ramicro_sync.py`)
- **Zielort:** `tools/email_import.py`
- **Ausführung:** Manuell oder per Windows Task Scheduler (z.B. alle 30 Min)
- **Encoding:** UTF-8 (deutsche Umlaute in JSON)
- **Datumsformat:** ISO 8601 (`YYYY-MM-DD`)
- **Beträge:** Als String gespeichert → beim Import in Zahl konvertieren
- **Personenschaden:** Gesamtes Objekt ist `null` wenn keine Verletzung

---

## Offene Fragen für die nächste Session

1. **Ausgabeformat:** Wohin sollen die Daten nach dem Import? Optionen:
   - CSV-Datei (für manuellen RA-MICRO-Import)
   - SQLite-Datenbank (wie bei Unfallakten-System)
   - Direkt in RA-MICRO? (NICHT empfohlen — RA-MICRO nur READ-ONLY!)
   - Nur Logfile + JSON-Archiv (Dateisystem)

2. **Duplikat-Erkennung:** Was passiert wenn die gleiche E-Mail zweimal verarbeitet wird?

3. **Bußgeld-Import:** Soll ein gleichartiges Script für `bussgeld@anwalt-offenbach.de` gebaut werden? (JSON-Schema noch nicht dokumentiert)

---

## Verwandte Dateien

| Datei | Beschreibung |
|-------|-------------|
| `app/api/unfall/route.ts` | Generiert die JSON-Anhänge (Quelldefinition) |
| `docs/unfallbogen-json-schema.md` | Vollständige Feld-Dokumentation mit Beispiel |
| `tools/ramicro_sync.py` | Vorlage für Python-Script-Stil |
| `lib/mail.ts` | SMTP-Konfiguration (Strato-Zugangsdaten-Referenz) |
