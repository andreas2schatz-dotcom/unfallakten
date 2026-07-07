# Unfallbogen — JSON-Schema-Dokumentation

**Version:** 2.0
**Stand:** 2026-03-30
**Quelle:** Website-Formular unter `/terminvorbereitung`
**API-Endpunkt:** `POST /api/unfall`
**Zustellung:** Als E-Mail-Anhang (`unfallbogen_[Name]_[Datum].json`)

---

## Übersicht

Das Unfallformular auf der Kanzlei-Website generiert bei jeder Einreichung eine strukturierte JSON-Datei. Diese Datei wird als Anhang an info@anwalt-offenbach.de gesendet und kann von Aktenverwaltungssystemen automatisch importiert werden.

---

## JSON-Struktur (Top-Level)

```json
{
  "meta": { ... },
  "mandant": { ... },
  "gegner": { ... },
  "unfall": { ... },
  "sachschaden": { ... },
  "personenschaden": { ... } | null
}
```

---

## Feldtypen-Legende

| Typ | Beschreibung |
|-----|--------------|
| `string` | Textfeld, UTF-8 |
| `string\|null` | Optionales Textfeld, `null` wenn nicht ausgefüllt |
| `"ja"\|"nein"\|null` | Ja/Nein-Auswahl, `null` wenn nicht beantwortet |
| `date-string` | Datumsformat `YYYY-MM-DD` (ISO 8601) |
| `iso-datetime` | Vollständiger Zeitstempel `YYYY-MM-DDTHH:mm:ss.sssZ` |

---

## 1. `meta` — Formular-Metadaten

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `meta.formular` | `string` | — | Immer `"unfallbogen"` — identifiziert den Formulartyp |
| `meta.version` | `string` | — | Schema-Version, aktuell `"2.0"` |
| `meta.eingegangen` | `iso-datetime` | — | Zeitstempel der Server-Verarbeitung (UTC) |
| `meta.aktenzeichen` | `string\|null` | 50 | Vom Mandanten eingegebenes Aktenzeichen zur Zuordnung an bestehende Akte. `null` = neue Akte anlegen |

**Beispiel:**
```json
{
  "formular": "unfallbogen",
  "version": "2.0",
  "eingegangen": "2026-03-30T14:22:31.000Z",
  "aktenzeichen": "123/26"
}
```

### Import-Logik für Aktenzeichen

```
WENN meta.aktenzeichen != null:
    → Suche bestehende Akte mit diesem Aktenzeichen
    → Falls gefunden: Daten der Akte zuordnen
    → Falls nicht gefunden: Warnung ausgeben, neue Akte anlegen
SONST:
    → Neue Akte anlegen
```

---

## 2. `mandant` — Mandantendaten

| Feld | Typ | Max. Länge | Pflicht | Beschreibung |
|------|-----|------------|---------|--------------|
| `mandant.name` | `string` | 200 | Ja | Nachname |
| `mandant.vorname` | `string` | 200 | Ja | Vorname |
| `mandant.strasse` | `string\|null` | 300 | Nein | Straße + Hausnummer |
| `mandant.plz` | `string\|null` | 5 | Nein | Postleitzahl (nur Ziffern) |
| `mandant.ort` | `string\|null` | 200 | Nein | Stadt/Ort |
| `mandant.email` | `string\|null` | 254 | Nein | E-Mail-Adresse (validiert) |
| `mandant.telefon` | `string` | 30 | Ja | Telefonnummer |
| `mandant.iban` | `string\|null` | 34 | Nein | IBAN (Format: `DE` + 2 Prüfziffern + 18 Stellen) |
| `mandant.vorsteuerabzug` | `"ja"\|"nein"\|null` | — | Nein | Vorsteuerabzugsberechtigt? |

**Beispiel:**
```json
{
  "name": "Müller",
  "vorname": "Thomas",
  "strasse": "Berliner Str. 15",
  "plz": "63067",
  "ort": "Offenbach",
  "email": "t.mueller@example.de",
  "telefon": "069 12345678",
  "iban": "DE89370400440532013000",
  "vorsteuerabzug": "nein"
}
```

---

## 3. `gegner` — Unfallgegnerdaten

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `gegner.fahrer` | `string\|null` | 300 | Name des gegnerischen Fahrers |
| `gegner.halter` | `string\|null` | 300 | Fahrzeughalter (falls abweichend) |
| `gegner.fahrzeug.art` | `string\|null` | 100 | z.B. PKW, LKW, Motorrad |
| `gegner.fahrzeug.fabrikat` | `string\|null` | 100 | z.B. VW Golf, BMW 3er |
| `gegner.fahrzeug.kennzeichen` | `string\|null` | 20 | Amtliches Kennzeichen |
| `gegner.versicherung.name` | `string\|null` | 200 | Name der Haftpflichtversicherung |
| `gegner.versicherung.nummer` | `string\|null` | 50 | Versicherungsnummer |
| `gegner.versicherung.schadennummer` | `string\|null` | 50 | Schadennummer der Versicherung |

**Beispiel:**
```json
{
  "fahrer": "Max Mustermann",
  "halter": "Max Mustermann",
  "fahrzeug": {
    "art": "PKW",
    "fabrikat": "VW Golf",
    "kennzeichen": "OF-AB 123"
  },
  "versicherung": {
    "name": "HUK-Coburg",
    "nummer": "VN-123456789",
    "schadennummer": "S-2026-00123"
  }
}
```

---

## 4. `unfall` — Unfalldaten

| Feld | Typ | Max. Länge | Pflicht | Beschreibung |
|------|-----|------------|---------|--------------|
| `unfall.selbst_fahrer` | `"ja"\|"nein"\|null` | — | Nein | War der Mandant selbst Fahrer? |
| `unfall.eigener_fahrer_name` | `string\|null` | 200 | Nein | Name des Fahrers (nur wenn selbst_fahrer = nein) |
| `unfall.datum` | `date-string` | 10 | Ja | Unfalltag (YYYY-MM-DD) |
| `unfall.zeit` | `string\|null` | 5 | Nein | Unfallzeit (HH:MM) |
| `unfall.ort` | `string` | 500 | Ja | Unfallort (Straße, Kreuzung, Ort) |
| `unfall.schilderung` | `string` | 5000 | Ja | Freitext-Unfallschilderung |
| `unfall.polizei.aufgenommen` | `"ja"\|"nein"\|null` | — | Nein | Polizeiliche Aufnahme? |
| `unfall.polizei.dienststelle` | `string\|null` | 200 | Nein | Polizeidienststelle |
| `unfall.polizei.aktenzeichen` | `string\|null` | 50 | Nein | Polizeiliches Aktenzeichen |
| `unfall.zeugen` | `string\|null` | 2000 | Nein | Freitext: Name/Anschrift der Zeugen |
| `unfall.andere_beteiligte` | `string\|null` | 2000 | Nein | Weitere Beteiligte |

---

## 5. `sachschaden` — Sachschadendaten

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `sachschaden.sonstige_schaeden` | `string\|null` | 2000 | Brille, Handy, Kleidung etc. |
| `sachschaden.betriebsvermoegen` | `"ja"\|"nein"\|null` | — | Fahrzeug = Betriebsvermögen? |
| `sachschaden.vorschaeden` | `"ja"\|"nein"\|null` | — | Vorschäden vorhanden? |
| `sachschaden.vorschaeden_art` | `string\|null` | 2000 | Beschreibung der Vorschäden |

### `sachschaden.eigenes_fahrzeug`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.art` | `string\|null` | 100 | Fahrzeugart |
| `.fabrikat` | `string\|null` | 100 | Fabrikat/Modell |
| `.baujahr` | `string\|null` | 4 | Baujahr (4 Ziffern) |
| `.km_stand` | `string\|null` | 10 | Kilometerstand |
| `.kennzeichen` | `string\|null` | 20 | Amtliches Kennzeichen |

### `sachschaden.vollkasko` / `sachschaden.teilkasko`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.vorhanden` | `"ja"\|"nein"\|null` | — | Versicherung vorhanden? |
| `.nummer` | `string\|null` | 50 | Versicherungsnummer |
| `.selbstbeteiligung` | `string\|null` | 20 | Betrag in EUR |

### `sachschaden.rechtsschutz`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.vorhanden` | `"ja"\|"nein"\|null` | — | RSV vorhanden? |
| `.name` | `string\|null` | 200 | Name der RSV |
| `.nummer` | `string\|null` | 50 | Versicherungsnummer |
| `.selbstbeteiligung` | `string\|null` | 20 | Selbstbeteiligung in EUR |

---

## 6. `personenschaden` — Personenschadendaten

**Dieses Objekt ist `null`, wenn `verletzt = "nein"` oder nicht beantwortet wurde.**

### `personenschaden.verletzter`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.name` | `string\|null` | 200 | Name der verletzten Person |
| `.geburtsdatum` | `date-string\|null` | 10 | Geburtsdatum |
| `.anschrift` | `string\|null` | 300 | Anschrift |
| `.telefon` | `string\|null` | 30 | Telefon |
| `.familienstand` | `string\|null` | 50 | Familienstand |
| `.kinder` | `string\|null` | 200 | Anzahl und Alter der Kinder |
| `.selbststaendig` | `"ja"\|"nein"\|null` | — | Selbstständig? |
| `.beruf` | `string\|null` | 200 | Ausgeübter Beruf |
| `.nettoeinkommen` | `string\|null` | 20 | Monatliches Netto in EUR |
| `.einkommen_von` | `string\|null` | 200 | Von wem? (Arbeitgeber etc.) |

### `personenschaden.arbeitgeber`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.name` | `string\|null` | 200 | Name des Arbeitgebers |
| `.anschrift` | `string\|null` | 300 | Anschrift |
| `.telefon` | `string\|null` | 30 | Telefon |

### `personenschaden.rente`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.bezieht_rente` | `"ja"\|"nein"\|null` | — | Bezieht unabhängig Rente? |
| `.betrag` | `string\|null` | 20 | Monatlich EUR |
| `.von` | `string\|null` | 200 | Rentenversicherungsträger |

### `personenschaden.krankenhaus`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.aufenthalt` | `"ja"\|"nein"\|null` | — | Krankenhausaufenthalt? |
| `.von` | `date-string\|null` | 10 | Beginn |
| `.bis` | `date-string\|null` | 10 | Ende (voraussichtlich) |
| `.name` | `string\|null` | 300 | Name + Anschrift |

### `personenschaden.hauskrank`

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `.geschrieben` | `"ja"\|"nein"\|null` | — | Hauskrank geschrieben? |
| `.von` | `date-string\|null` | 10 | Beginn |
| `.bis` | `date-string\|null` | 10 | Ende (voraussichtlich) |

### Weitere Felder

| Feld | Typ | Max. Länge | Beschreibung |
|------|-----|------------|--------------|
| `personenschaden.verletzungen` | `string\|null` | 3000 | Art und Umfang der Verletzungen |
| `personenschaden.ambulant_aerzte` | `string\|null` | 2000 | Ambulant behandelnde Ärzte |
| `personenschaden.krankenkasse` | `string\|null` | 200 | Name der Krankenkasse |
| `personenschaden.berufsunfall.liegt_vor` | `"ja"\|"nein"\|null` | — | Berufsunfall/Wegeunfall? |
| `personenschaden.berufsunfall.berufsgenossenschaft` | `string\|null` | 200 | Zuständige BG |
| `personenschaden.rentenversichert.gesetzlich` | `"ja"\|"nein"\|null` | — | Gesetzlich rentenversichert? |
| `personenschaden.rentenversichert.anstalt` | `string\|null` | 200 | Rentenversicherungsanstalt |
| `personenschaden.schweigepflicht_entbindung` | `"ja"\|"nein"\|null` | — | Ärzte von Schweigepflicht entbunden? |

---

## Vollständiges Beispiel

```json
{
  "meta": {
    "formular": "unfallbogen",
    "version": "2.0",
    "eingegangen": "2026-03-30T14:22:31.000Z",
    "aktenzeichen": null
  },
  "mandant": {
    "name": "Müller",
    "vorname": "Thomas",
    "strasse": "Berliner Str. 15",
    "plz": "63067",
    "ort": "Offenbach",
    "email": "t.mueller@example.de",
    "telefon": "069 12345678",
    "iban": "DE89370400440532013000",
    "vorsteuerabzug": "nein"
  },
  "gegner": {
    "fahrer": "Max Mustermann",
    "halter": "Max Mustermann",
    "fahrzeug": {
      "art": "PKW",
      "fabrikat": "VW Golf",
      "kennzeichen": "OF-AB 123"
    },
    "versicherung": {
      "name": "HUK-Coburg",
      "nummer": "VN-123456789",
      "schadennummer": null
    }
  },
  "unfall": {
    "selbst_fahrer": "ja",
    "eigener_fahrer_name": null,
    "datum": "2026-03-28",
    "zeit": "14:30",
    "ort": "Kaiserstraße / Ecke Berliner Str., 63067 Offenbach",
    "schilderung": "Der Unfallgegner fuhr bei Rot über die Ampel und kollidierte mit meiner Beifahrerseite.",
    "polizei": {
      "aufgenommen": "ja",
      "dienststelle": "Polizeirevier Offenbach",
      "aktenzeichen": "TAB-2026-03-1234"
    },
    "zeugen": "Maria Schmidt, Frankfurter Str. 10, 63065 Offenbach",
    "andere_beteiligte": null
  },
  "sachschaden": {
    "sonstige_schaeden": "Brille beschädigt",
    "betriebsvermoegen": "nein",
    "vorschaeden": "nein",
    "vorschaeden_art": null,
    "eigenes_fahrzeug": {
      "art": "PKW",
      "fabrikat": "Opel Astra",
      "baujahr": "2021",
      "km_stand": "45000",
      "kennzeichen": "OF-TM 456"
    },
    "vollkasko": {
      "vorhanden": "ja",
      "nummer": "VK-987654",
      "selbstbeteiligung": "300"
    },
    "teilkasko": {
      "vorhanden": "nein",
      "nummer": null,
      "selbstbeteiligung": null
    },
    "rechtsschutz": {
      "vorhanden": "ja",
      "name": "ADAC Rechtsschutz",
      "nummer": "RS-112233",
      "selbstbeteiligung": "250"
    }
  },
  "personenschaden": {
    "verletzter": {
      "name": "Thomas Müller",
      "geburtsdatum": "1985-06-15",
      "anschrift": "Berliner Str. 15, 63067 Offenbach",
      "telefon": "069 12345678",
      "familienstand": "verheiratet",
      "kinder": "2 Kinder (4 und 7 Jahre)",
      "selbststaendig": "nein",
      "beruf": "Softwareentwickler",
      "nettoeinkommen": "3500",
      "einkommen_von": "ABC GmbH"
    },
    "arbeitgeber": {
      "name": "ABC GmbH",
      "anschrift": "Mainzer Landstr. 50, 60329 Frankfurt",
      "telefon": "069 98765432"
    },
    "rente": {
      "bezieht_rente": "nein",
      "betrag": null,
      "von": null
    },
    "verletzungen": "HWS-Distorsion (Schleudertrauma), Prellungen linker Oberarm",
    "krankenhaus": {
      "aufenthalt": "nein",
      "von": null,
      "bis": null,
      "name": null
    },
    "ambulant_aerzte": "Dr. med. Petra Weber, Kaiserstr. 22, 63067 Offenbach",
    "hauskrank": {
      "geschrieben": "ja",
      "von": "2026-03-28",
      "bis": "2026-04-11"
    },
    "krankenkasse": "Techniker Krankenkasse",
    "berufsunfall": {
      "liegt_vor": "nein",
      "berufsgenossenschaft": null
    },
    "rentenversichert": {
      "gesetzlich": "ja",
      "anstalt": "Deutsche Rentenversicherung Hessen"
    },
    "schweigepflicht_entbindung": "ja"
  }
}
```

---

## Hinweise für den Import

1. **Encoding:** UTF-8 — deutsche Umlaute (ä, ö, ü, ß) sind korrekt kodiert
2. **Null-Werte:** `null` bedeutet "nicht ausgefüllt" — nicht mit leerem String verwechseln
3. **Datumsformat:** Immer ISO 8601 (`YYYY-MM-DD`)
4. **Beträge:** Als String gespeichert (z.B. `"300"`, `"3500"`) — beim Import in numerischen Typ konvertieren
5. **Personenschaden:** Das gesamte Objekt ist `null` wenn keine Verletzung vorliegt
6. **Versionierung:** Prüfen Sie `meta.version` beim Import — bei Schema-Änderungen wird die Version erhöht
   