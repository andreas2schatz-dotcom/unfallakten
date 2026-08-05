# Unfallakten-System – Datenmodell

Koch, Schatz & Kollegen · Rechtsanwaltskanzlei Offenbach  
Stand: 2026-05-02 · Schema-Version 40

Datenbank: SQLite · Datei `/app/data/unfallakten.db`  
PK-Konvention: `INTEGER PRIMARY KEY AUTOINCREMENT` wenn nicht anders markiert.  
`akte_id` ist überall `TEXT` und referenziert `unfallakte.az` (seit Migration 5).

---

## 1. Tabellenübersicht

### benutzer
*Erstellt: Basisschema (schema.py)*

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `name` | TEXT | NOT NULL |
| `email` | TEXT | NOT NULL UNIQUE |
| `passwort_hash` | TEXT | NOT NULL · bcrypt via passlib |
| `rolle` | TEXT | NOT NULL DEFAULT 'sachbearbeiter' · CHECK IN ('admin','sachbearbeiter') |
| `aktiv` | INTEGER | NOT NULL DEFAULT 1 · CHECK IN (0,1) |
| `erstellt_am` | TEXT | NOT NULL DEFAULT datetime() |
| `zuletzt_login` | TEXT | nullable |

---

### unfallakte
*Erstellt: Basisschema · Erweiterungen: Migration 19, 35, 38*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `az` | TEXT | **PK** · kein AUTOINCREMENT · Format z.B. `31/21 AS` · = RA-MICRO-Aktenzeichen |
| `unfalldatum` | TEXT | NOT NULL DEFAULT '' · ISO 8601 YYYY-MM-DD |
| `unfallort` | TEXT | nullable |
| `erstellt_am` | TEXT | NOT NULL DEFAULT datetime() |
| `geaendert_am` | TEXT | NOT NULL DEFAULT datetime() · wird per TRIGGER aktualisiert |
| `status` | TEXT | NOT NULL DEFAULT 'offen' · CHECK IN ('offen','in_regulierung','klage','abgeschlossen') |
| `bearbeiter_id` | INTEGER | FK benutzer(id) ON DELETE SET NULL |
| `notizen` | TEXT | nullable |
| `haftungsquote` | REAL | NOT NULL DEFAULT 100.0 · CHECK BETWEEN 0 AND 100 |
| `kurzbezeichnung` | TEXT | nullable · aus RA-MICRO gecacht |
| `sachbearbeiter` | TEXT | nullable · aus RA-MICRO gecacht |
| `aktion_erforderlich` | INTEGER | NOT NULL DEFAULT 0 · *Migration 19* |
| `aktion_typ` | TEXT | nullable · *Migration 19* |
| `aktion_seit` | TEXT | nullable · *Migration 19* |
| `auslandsbezug` | INTEGER | NOT NULL DEFAULT 0 · *Migration 35* · RVG-Gebührenassistent |
| `todesfall` | INTEGER | NOT NULL DEFAULT 0 · *Migration 35* |
| `haftung_streitig` | INTEGER | NOT NULL DEFAULT 0 · *Migration 35* |
| `portal_aktiv` | INTEGER | NOT NULL DEFAULT 0 · *Migration 38* |
| `portal_sync_pending` | INTEGER | NOT NULL DEFAULT 0 · *Migration 38* |
| `portal_last_sync` | TEXT | nullable · *Migration 38* |

Trigger: `unfallakte_geaendert` → setzt `geaendert_am = datetime('now','localtime')` bei UPDATE.

---

### beteiligte
*Erstellt: Basisschema · Erweiterungen: Migration 8, 23(root)/34, 39*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL FK unfallakte(az) ON DELETE CASCADE |
| `rolle` | TEXT | NOT NULL · CHECK IN ('mandant','gegner','zeuge','sachverstaendiger','sonstiger') |
| `name` | TEXT | NOT NULL |
| `vorname` | TEXT | nullable |
| `firma` | TEXT | nullable |
| `anschrift` | TEXT | nullable |
| `plz` | TEXT | nullable |
| `ort` | TEXT | nullable |
| `telefon` | TEXT | nullable |
| `email` | TEXT | nullable |
| `kfz_kennzeichen` | TEXT | nullable |
| `kfz_typ` | TEXT | nullable |
| `versicherung` | TEXT | nullable |
| `vers_nr` | TEXT | nullable · Versicherungsscheinnummer |
| `schaden_nr` | TEXT | nullable · Schadennummer bei Versicherung |
| `iban` | TEXT | nullable |
| `notizen` | TEXT | nullable |
| `gutachten_nr` | TEXT | nullable · Auftragsnummer aus Gutachten-Parse · *Mig 39* |
| `anrede` | TEXT | nullable · *Migration 8* · Freitext (z.B. "Herrn") |
| `vorsteuer` | TEXT | NOT NULL DEFAULT 'N' · *Mig 8* · 'J'/'N' |
| `vertreter_name` | TEXT | nullable · *Mig 23(root)* · für GmbH/AG im Klage-Rubrum |
| `vertreter_funktion` | TEXT | nullable · *Mig 23(root)* · z.B. "Geschäftsführer" |
| `ist_halter` | INTEGER | NOT NULL DEFAULT 0 · *Migration 34* · Unterscheidung Halter/Versicherung |

---

### schadenpositionen
*Erstellt: Basisschema · Erweiterungen: Migration 6, 8, 10, 12, 14*  
*Ein Datensatz pro Akte (INSERT OR UPDATE).*

| Spalte | Typ | Netto/Brutto · Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL FK unfallakte(az) ON DELETE CASCADE |
| `reparaturkosten` | REAL | NOT NULL DEFAULT 0.0 · Legacy-Brutto-Feld · wird durch `rep_gutachten_netto` ersetzt |
| `wiederbeschaffung` | REAL | NOT NULL DEFAULT 0.0 · WBW brutto |
| `restwert` | REAL | NOT NULL DEFAULT 0.0 · wird von WBW abgezogen |
| `wertminderung` | REAL | NOT NULL DEFAULT 0.0 |
| `nutzungsausfall` | REAL | NOT NULL DEFAULT 0.0 |
| `mietwagenkosten` | REAL | NOT NULL DEFAULT 0.0 · **Brutto-Fallback** |
| `mietwagenkosten_netto` | REAL | NOT NULL DEFAULT 0.0 · *Mig 14* |
| `mietwagenkosten_ust` | REAL | NOT NULL DEFAULT 0.0 · *Mig 14* |
| `sv_kosten` | REAL | NOT NULL DEFAULT 0.0 · **Brutto-Fallback** |
| `sv_kosten_netto` | REAL | NOT NULL DEFAULT 0.0 · *Migration 14* |
| `sv_kosten_ust` | REAL | NOT NULL DEFAULT 0.0 · *Migration 14* |
| `abschleppkosten` | REAL | NOT NULL DEFAULT 0.0 · **Brutto-Fallback** |
| `abschleppkosten_netto` | REAL | NOT NULL DEFAULT 0.0 · *Mig 14* |
| `abschleppkosten_ust` | REAL | NOT NULL DEFAULT 0.0 · *Mig 14* |
| `standkosten` | REAL | NOT NULL DEFAULT 0.0 · **Brutto-Fallback** |
| `standkosten_netto` | REAL | NOT NULL DEFAULT 0.0 · *Migration 14* |
| `standkosten_ust` | REAL | NOT NULL DEFAULT 0.0 · *Migration 14* |
| `anabmeldekosten` | REAL | NOT NULL DEFAULT 0.0 · **Brutto-Fallback** |
| `anabmeldekosten_netto` | REAL | NOT NULL DEFAULT 0.0 · *Mig 14* |
| `anabmeldekosten_ust` | REAL | NOT NULL DEFAULT 0.0 · *Mig 14* |
| `schmerzensgeld` | REAL | NOT NULL DEFAULT 0.0 |
| `sonstiges` | REAL | NOT NULL DEFAULT 0.0 |
| `sonstiges_beschr` | TEXT | nullable |
| `verdienstausfall` | REAL | NOT NULL DEFAULT 0.0 · *Migration 6* |
| `haushalt` | REAL | NOT NULL DEFAULT 0.0 · *Migration 6* |
| `unkostenpauschale` | REAL | NOT NULL DEFAULT 0.0 · *Migration 6* |
| `rep_gutachten_netto` | REAL | NOT NULL DEFAULT 0.0 · *Mig 6+10* · war früher `rep_fiktiv_netto` |
| `rep_gutachten_mwst` | REAL | NOT NULL DEFAULT 0.0 · *Mig 6+10* · war früher `rep_fiktiv_mwst` |
| `rep_rechnung_netto` | REAL | NOT NULL DEFAULT 0.0 · *Migration 10* |
| `rep_rechnung_brutto` | REAL | NOT NULL DEFAULT 0.0 · *Migration 10* |
| `kostennb` | REAL | NOT NULL DEFAULT 0.0 · *Mig 8* · Nachbesichtigungskosten netto |
| `kostennb_ust` | REAL | NOT NULL DEFAULT 0.0 · *Migration 8* |
| `wdm_extras_json` | TEXT | nullable · *Mig 6* · JSON-Array der WDM-Sonstiges-Positionen (varSSCHADEN1-6) |
| `wdm_info_json` | TEXT | nullable · *Mig 6* · WDM-Metadaten (varFKLASSE, varREPDAUER etc.) |
| `abrechnungsart` | TEXT | nullable · *Mig 12* · CHECK IN ('fiktiv','konkret','totalschaden') |
| `quelle` | TEXT | NOT NULL DEFAULT 'manuell' · CHECK IN ('manuell','gutachten_pdf','abrechnung_pdf','korrektur') |
| `erfasst_am` | TEXT | NOT NULL DEFAULT datetime() |
| `erfasst_von` | INTEGER | FK benutzer(id) ON DELETE SET NULL |

---

### regulierung
*Erstellt: Basisschema · **Deprecated**: wird nicht mehr aktiv befüllt (seit Option-B-Redesign)*  
*Läuft weiter als Fallback-Tabelle. Aktiver Pfad: abrechnungsschreiben + regulierung_positionen.*

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL FK unfallakte(az) ON DELETE CASCADE |
| `datum` | TEXT | NOT NULL |
| `betrag_gefordert` | REAL | NOT NULL DEFAULT 0.0 |
| `betrag_reguliert` | REAL | NOT NULL DEFAULT 0.0 |
| `status` | TEXT | NOT NULL DEFAULT 'offen' · CHECK IN ('offen','teilreguliert','vollreguliert','abgelehnt') |
| `vers_referenz` | TEXT | nullable |
| `kuerz_begruendung` | TEXT | nullable |
| `reguliert_positionen` | TEXT | nullable · JSON-String |
| `erfasst_am` | TEXT | NOT NULL DEFAULT datetime() |
| `erfasst_von` | INTEGER | FK benutzer(id) ON DELETE SET NULL |

---

### dokumente
*Erstellt: Basisschema · Erweiterungen: Migration 24, 26, 38*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL FK unfallakte(az) ON DELETE CASCADE |
| `typ` | TEXT | NOT NULL · CHECK IN ('gutachten','abrechnungsschreiben','forderungsschreiben','sachstandsanfrage','klage','sonstiges') |
| `dateiname` | TEXT | NOT NULL |
| `dateipfad` | TEXT | NOT NULL · relativer Pfad ab /uploads/ |
| `dateityp` | TEXT | NOT NULL DEFAULT 'pdf' · CHECK IN ('pdf','docx','jpg','png') |
| `dateigroesse` | INTEGER | nullable · Bytes |
| `hochgeladen_am` | TEXT | NOT NULL DEFAULT datetime() |
| `hochgeladen_von` | INTEGER | FK benutzer(id) ON DELETE SET NULL |
| `parse_status` | TEXT | NOT NULL DEFAULT 'ausstehend' · CHECK IN ('ausstehend','erfolgreich','fehler','manuell_korrigiert') |
| `parse_konfidenz` | REAL | nullable · 0.0–1.0 |
| `parse_json` | TEXT | nullable · Rohes Parse-Ergebnis als JSON |
| `parse_fehler` | TEXT | nullable |
| `notizen` | TEXT | nullable |
| `dokumentenklasse` | TEXT | nullable · *Mig 24* · z.B. 'gutachten','rechnung','regulierungsschreiben' |
| `pdf_hash` | TEXT | nullable · *Mig 24* · SHA-256 für Dedup |
| `eakte_nr` | INTEGER | nullable · *Mig 26* · PK aus raEloakte.tblElo_AktenArchiv |
| `eakte_pfad` | TEXT | nullable · *Mig 26* · Datei-Pfad im E-Akte-DMS |
| `quelle` | TEXT | nullable DEFAULT 'upload' · *Mig 26* · 'upload'/'eakte' |
| `portal_sichtbar` | INTEGER | NOT NULL DEFAULT 0 · *Mig 38* |

---

### aktivitaeten
*Erstellt: Basisschema · Repariert: Migration 11, 20*

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** · repariert in Migration 11 |
| `akte_id` | TEXT | FK unfallakte(az) ON DELETE CASCADE · *war INTEGER bis Migration 20* |
| `benutzer_id` | INTEGER | FK benutzer(id) ON DELETE SET NULL |
| `zeitstempel` | TEXT | NOT NULL DEFAULT datetime() |
| `aktion` | TEXT | NOT NULL · z.B. 'akte_erstellt','pdf_hochgeladen' |
| `beschreibung` | TEXT | NOT NULL |
| `tabelle` | TEXT | nullable · betroffene Tabelle |
| `datensatz_id` | INTEGER | nullable |
| `aenderung_json` | TEXT | nullable · `{"vorher": {...}, "nachher": {...}}` |

---

### schema_version

| Spalte | Typ | Constraint |
|---|---|---|
| `version` | INTEGER | **PK** |
| `beschreibung` | TEXT | nullable |
| `angewendet_am` | TEXT | NOT NULL DEFAULT datetime() |

---

### email_import_log
*Erstellt: Migration 2 · Komplett neu aufgebaut: Migration 17*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `message_id` | TEXT | NOT NULL UNIQUE · IMAP Message-ID |
| `betreff` | TEXT | nullable |
| `absender` | TEXT | nullable |
| `von_name` | TEXT | nullable · *Migration 17* |
| `empfangen_am` | TEXT | nullable |
| `importiert_am` | TEXT | NOT NULL DEFAULT datetime() |
| `akte_id` | TEXT | FK unfallakte(az) ON DELETE SET NULL · *war INTEGER bis Mig 17* |
| `status` | TEXT | NOT NULL DEFAULT 'nicht_zugeordnet' · CHECK IN ('zugeordnet','nicht_zugeordnet','fehler','ignoriert') |
| `erkannt_az` | TEXT | nullable · *Mig 17* · aus E-Mail-Body extrahiertes AZ |
| `erkannt_kfz` | TEXT | nullable · *Mig 17* |
| `match_methode` | TEXT | nullable · *Mig 17* |
| `manuell_zugeordnet` | INTEGER | NOT NULL DEFAULT 0 · *Mig 17* |
| `anhaenge_anzahl` | INTEGER | DEFAULT 0 |
| `importierte_dok` | TEXT | nullable |
| `notizen` | TEXT | nullable |
| `in_akte_importiert` | INTEGER | NOT NULL DEFAULT 0 · *Mig 18* |
| `in_akte_importiert_am` | TEXT | nullable · *Mig 18* |
| `absender_kategorie` | TEXT | nullable · *Mig 18* |
| `eml_pfad` | TEXT | nullable · *Mig 18* |
| `email_typ` | TEXT | nullable · *Mig 19* |

---

### kuerzungsarten
*Erstellt: Migration 3 · 19 Seed-Einträge · Erweiterung: Migration 22 · Taxonomie (typ_code A–F, +13 Seeds → 32): Migration 64*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `bezeichnung` | TEXT | NOT NULL UNIQUE |
| `kategorie` | TEXT | NOT NULL · CHECK IN ('fahrzeugschaden','ersatzbeschaffung','sonstiger_schaden','technisch_gutachten') |
| `standard_gegenargument` | TEXT | nullable |
| `rechtsgrundlagen` | TEXT | nullable |
| `hinweis_intern` | TEXT | nullable |
| `sv_stellungnahme_erforderlich` | INTEGER | NOT NULL DEFAULT 0 · CHECK IN (0,1) |
| `aktiv` | INTEGER | NOT NULL DEFAULT 1 · CHECK IN (0,1) |
| `sortierung` | INTEGER | NOT NULL DEFAULT 0 |
| `erstellt_am` | TEXT | NOT NULL DEFAULT datetime() |
| `textbaustein` | TEXT | nullable · *Migration 22* · briefreifer Gegenargument-Text |
| `typ_code` | TEXT | nullable · *Mig 64* · A–F-Taxonomie-Code (z. B. 'A02', 'E06') · UNIQUE-Partial-Index, per REST nicht schreibbar |
| `verifiziert_am` | TEXT | nullable · *Mig 64* · Verifikationsstempel der Typ-Zuordnung |

---

### abrechnungsschreiben
*Erstellt: Migration 3 · Erweiterung: Migration 16*  
*ACHTUNG: In Migration 3 war `akte_id` als `INTEGER REFERENCES unfallakte(id)` deklariert — nach Migration 5 (AZ als PK) ist die FK-Definition veraltet. Tatsächlicher Typ: TEXT.*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL · FK unfallakte(az) · *ursprünglich INTEGER in Mig 3* |
| `datum` | TEXT | NOT NULL |
| `versicherung` | TEXT | nullable |
| `referenz_nr` | TEXT | nullable |
| `haftungsquote` | REAL | NOT NULL DEFAULT 100.0 · CHECK BETWEEN 0 AND 100 |
| `haftungsart` | TEXT | NOT NULL DEFAULT 'vollhaftung' · CHECK IN ('vollhaftung','mithaftung','quote','ablehnung') |
| `haftungsbegruendung` | TEXT | nullable |
| `gesamt_gefordert` | REAL | NOT NULL DEFAULT 0.0 · wird aus Positionen summiert |
| `gesamt_reguliert` | REAL | NOT NULL DEFAULT 0.0 · wird aus Positionen summiert |
| `dokument_id` | INTEGER | FK dokumente(id) ON DELETE SET NULL |
| `parse_status` | TEXT | NOT NULL DEFAULT 'manuell' · CHECK IN ('ausstehend','erfolgreich','teilweise','manuell','fehlgeschlagen') |
| `notizen` | TEXT | nullable |
| `erfasst_am` | TEXT | NOT NULL DEFAULT datetime() |
| `erfasst_von` | INTEGER | FK benutzer(id) ON DELETE SET NULL |
| `quelle` | TEXT | NOT NULL DEFAULT 'pdf' · *Mig 16* · 'pdf'/'manuell'/'wdm' |
| `gesamt_kuerzung` | REAL | NOT NULL DEFAULT 0.0 · *Mig 16* · = gesamt_gefordert - gesamt_reguliert |
| `wdm_importiert` | INTEGER | NOT NULL DEFAULT 0 · *Mig 16* · verhindert Doppel-WDM-Import |
| `pruefdienstleister_id` | INTEGER | FK pruefdienstleister(id) · *Mig 64* |

---

### regulierung_positionen
*Erstellt: Migration 3 · Neu aufgebaut ohne CHECK-Constraint: Migration 16*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `abrechnungsschreiben_id` | INTEGER | NOT NULL FK abrechnungsschreiben(id) ON DELETE CASCADE |
| `position_key` | TEXT | NOT NULL · Enum-Werte (keine DB-CHECK seit Mig 16, nur Python) |
| `position_label` | TEXT | nullable · *Mig 16* · Freitext-Label für sonstiges_wdm_* |
| `betrag_gefordert` | REAL | NOT NULL DEFAULT 0.0 |
| `betrag_reguliert` | REAL | NOT NULL DEFAULT 0.0 |
| `kuerzungsart_id` | INTEGER | FK kuerzungsarten(id) ON DELETE SET NULL |
| `kuerzung_freitext` | TEXT | nullable |
| `parser_erkannt` | INTEGER | NOT NULL DEFAULT 0 · CHECK IN (0,1) |
| `parser_konfidenz` | REAL | nullable |
| `fuer_klage_vorgemerkt` | INTEGER | NOT NULL DEFAULT 0 · CHECK IN (0,1) |
| `sv_stellungnahme_ausstehend` | INTEGER | NOT NULL DEFAULT 0 · CHECK IN (0,1) |
| `typ_quelle` | TEXT | nullable · *Mig 64* · 'regel'/'llm'/'manuell' — Herkunft der kuerzungsart_id-Zuordnung |

Gültige `position_key`-Werte (Python-Enum `POSITION_KEYS` in `models/abrechnungsschreiben.py`):
```
reparaturkosten, wiederbeschaffung, restwert, wertminderung, nutzungsausfall,
mietwagenkosten, sv_kosten, abschleppkosten, restkraftstoff, standkosten,
anabmeldekosten, schmerzensgeld, sonstiges,
reparatur_brutto, reparatur_netto, wbw, wbw_netto, wbw_brutto, wba,
fahrzeugschaden, kostenpauschale, ra_gebuehren, mwst_abzug, pruefbericht_abzug,
rep_gutachten_netto, rep_rechnung_netto, rep_rechnung_brutto,
verdienstausfall, haushalt, unkostenpauschale, kostennb, vorschuss,
sonstiges_wdm_1 … sonstiges_wdm_6
```

---

### pruefberichte
*Erstellt: Migration 3 · PDF-Felder ergänzt: Migration 4*

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL FK unfallakte(az) ON DELETE CASCADE |
| `abrechnungsschreiben_id` | INTEGER | FK abrechnungsschreiben(id) ON DELETE SET NULL |
| `datum` | TEXT | NOT NULL |
| `gutachter` | TEXT | nullable |
| `dokument_id` | INTEGER | FK dokumente(id) ON DELETE SET NULL |
| `parse_status` | TEXT | NOT NULL DEFAULT 'manuell' |
| `pruefdienstleister` | TEXT | nullable · *Mig 4* · Freitext (Alt) |
| `pruefdienstleister_id` | INTEGER | FK pruefdienstleister(id) · *Mig 64* · strukturierter Stamm-Verweis |
| `vorgangsnummer` | TEXT | nullable · *Mig 4* |
| `schadennummer` | TEXT | nullable · *Mig 4* |
| `reparaturkosten_vor_pruefung` | REAL | nullable · *Mig 4* |
| `abzug_technisch` | REAL | nullable · *Mig 4* |
| `abzug_werkstattalternative` | REAL | nullable · *Mig 4* |
| `abzug_gesamt` | REAL | nullable · *Mig 4* |
| `reparaturkosten_nach_pruefung` | REAL | nullable · *Mig 4* |
| `referenzwerkstatt_name` | TEXT | nullable · *Mig 4* |
| `referenzwerkstatt_adresse` | TEXT | nullable · *Mig 4* |
| `referenzwerkstatt_entfernung` | REAL | nullable · *Mig 4* · km |
| `ist_image_pdf` | INTEGER | NOT NULL DEFAULT 0 · *Mig 4* |
| `fahrzeug_hersteller` | TEXT | nullable · *Mig 4* |
| `fahrzeug_typ` | TEXT | nullable · *Mig 4* |
| `fahrzeug_kennzeichen` | TEXT | nullable · *Mig 4* |
| `kuerzungen_json` | TEXT | nullable · JSON-Array der Kürzungspositionen |
| `notizen` | TEXT | nullable |
| `erfasst_am` | TEXT | NOT NULL DEFAULT datetime() |
| `erfasst_von` | INTEGER | FK benutzer(id) ON DELETE SET NULL |

---

### forderung_positionen
*Erstellt: Migration 9*

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL FK unfallakte(az) ON DELETE CASCADE |
| `dokument_id` | INTEGER | FK dokumente(id) ON DELETE SET NULL |
| `forderungsschreiben_nr` | INTEGER | NOT NULL DEFAULT 1 |
| `datum` | TEXT | NOT NULL DEFAULT date() |
| `position_key` | TEXT | NOT NULL |
| `position_label` | TEXT | NOT NULL |
| `betrag_gefordert` | REAL | NOT NULL DEFAULT 0.0 |
| `betrag_reguliert` | REAL | NOT NULL DEFAULT 0.0 |
| `status` | TEXT | NOT NULL DEFAULT 'gefordert' · CHECK IN ('gefordert','teilreguliert','vollreguliert','gekuerzt','abgelehnt') |
| `fuer_klage` | INTEGER | NOT NULL DEFAULT 0 · CHECK IN (0,1) |
| `kuerzungsart_id` | INTEGER | FK kuerzungsarten(id) ON DELETE SET NULL |
| `kuerzung_begruendung` | TEXT | nullable |
| `erfasst_am` | TEXT | NOT NULL DEFAULT datetime() |
| `erfasst_von` | INTEGER | FK benutzer(id) ON DELETE SET NULL |

---

### personenschaden
*Erstellt: Migration 13 · Erweiterungen: Migration 35, 36*  
*1:1 zur Akte (UNIQUE auf akte_id)*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL UNIQUE FK unfallakte(az) ON DELETE CASCADE |
| `verletzter_name` | TEXT | nullable |
| `verletzter_vorname` | TEXT | nullable |
| `geburtsdatum` | TEXT | nullable · ISO YYYY-MM-DD |
| `familienstand` | TEXT | nullable |
| `kinder_anzahl` | INTEGER | nullable |
| `kinder_alter_text` | TEXT | nullable · Freitext z.B. "11, 10, 6" |
| `beruf` | TEXT | nullable |
| `selbststaendig` | INTEGER | NOT NULL DEFAULT 0 |
| `nettoeinkommen_monatlich` | REAL | nullable |
| `arbeitgeber_name` | TEXT | nullable |
| `arbeitgeber_anschrift` | TEXT | nullable |
| `arbeitgeber_telefon` | TEXT | nullable |
| `rente_vor_unfall` | INTEGER | NOT NULL DEFAULT 0 |
| `rente_betrag_monatlich` | REAL | nullable |
| `verletzungen_text` | TEXT | nullable |
| `krankenhaus_name` | TEXT | nullable |
| `krankenhaus_anschrift` | TEXT | nullable |
| `krankenhaus_von` | TEXT | nullable |
| `krankenhaus_bis` | TEXT | nullable |
| `ambulante_aerzte_json` | TEXT | nullable · JSON-Array `[{"name","strasse","ort","telefon"}]` |
| `krankenhaus_aufenthalt` | INTEGER | NOT NULL DEFAULT 0 |
| `krankgeschrieben` | INTEGER | NOT NULL DEFAULT 0 |
| `krank_von` | TEXT | nullable |
| `krank_bis` | TEXT | nullable |
| `krankenkasse_name` | TEXT | nullable |
| `krankenkasse_anschrift` | TEXT | nullable |
| `berufsunfall` | INTEGER | NOT NULL DEFAULT 0 |
| `bg_name` | TEXT | nullable |
| `rentenversichert` | INTEGER | NOT NULL DEFAULT 0 |
| `rentenversicherung_name` | TEXT | nullable |
| `schweigepflicht_entbindung` | INTEGER | NOT NULL DEFAULT 0 |
| `heilbehandlung_abgeschlossen` | INTEGER | NOT NULL DEFAULT 0 |
| `heilbehandlung_ende` | TEXT | nullable |
| `dauerfolgen` | INTEGER | NOT NULL DEFAULT 0 |
| `dauerfolgen_text` | TEXT | nullable |
| `physiotherapie` | INTEGER | NOT NULL DEFAULT 0 |
| `physiotherapeut_name` | TEXT | nullable |
| `physiotherapeut_anschrift` | TEXT | nullable |
| `physiotherapie_anzahl` | INTEGER | nullable |
| `verletzungsgrad` | TEXT | nullable · *Mig 35* · 'keine'/'leicht'/'schwer'/'schwerst' |
| `pflegebedarf` | INTEGER | NOT NULL DEFAULT 0 · *Migration 35* |
| `sg_mindest` | REAL | nullable · *Mig 36* · Mindest-Schmerzensgeld aus Urteildatenbank |
| `sg_text` | TEXT | nullable · *Mig 36* · KI-generierter Klagetext |
| `sg_urteil_gericht` | TEXT | nullable · *Mig 36* |
| `sg_urteil_az` | TEXT | nullable · *Mig 36* |
| `sg_urteil_betrag` | REAL | nullable · *Mig 36* |
| `notizen` | TEXT | nullable |
| `erfasst_am` | TEXT | NOT NULL DEFAULT datetime() |
| `erfasst_von` | INTEGER | FK benutzer(id) ON DELETE SET NULL |
| `geaendert_am` | TEXT | NOT NULL DEFAULT datetime() |

---

### unfalldetails
*Erstellt: `backend/schema_manager.py` (Root-Level-Datei, nicht in `backend/db/schema_manager.py`!) · Erweiterung: Migration 28 (backend/db)*

| Spalte | Typ | Constraint / Herkunft |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL UNIQUE FK unfallakte(az) ON DELETE CASCADE · *Note: DDL verwendet `unfallakte(aktenzeichen)` — historischer Name* |
| `schilderung` | TEXT | nullable |
| `zeuge_1` | TEXT | nullable |
| `zeuge_1_anschrift` | TEXT | nullable |
| `zeuge_2` | TEXT | nullable |
| `zeuge_2_anschrift` | TEXT | nullable |
| `zeuge_3` | TEXT | nullable |
| `zeuge_3_anschrift` | TEXT | nullable |
| `ermittlungsakte_az` | TEXT | nullable |
| `ermittlungsakte_behoerde` | TEXT | nullable |
| `ermittlungsakte_ort` | TEXT | nullable |
| `fahrer_mandant` | TEXT | nullable |
| `fahrer_gegner` | TEXT | nullable |
| `vorsteuerabzug` | INTEGER | DEFAULT 0 |
| `haftungsquote` | REAL | DEFAULT 100 |
| `haftungsbegruendung` | TEXT | nullable |
| `aktivlegitimation_typ` | TEXT | NOT NULL DEFAULT 'eigentum' · *Mig 28* · 'eigentum'/'finanziert'/'geleast' |
| `aktivlegitimation_freigabe` | TEXT | NOT NULL DEFAULT 'freigabe' · *Mig 28* · 'freigabe'/'bedingungen'/'ungeklaert' |
| `aktivlegitimation_datum` | TEXT | nullable · *Mig 28* · Datum der Freigabeerklärung |
| `erstellt_am` | TEXT | DEFAULT datetime() |
| `geaendert_am` | TEXT | DEFAULT datetime() |

---

### todos
*Erstellt: Migration 23 (backend/db) · Neu aufgebaut mit korrekten FK: Migration 32*

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_az` | TEXT | NOT NULL FK unfallakte(az) |
| `text` | TEXT | NOT NULL |
| `erstellt_am` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP |
| `faellig_am` | TEXT | nullable |
| `frist_typ` | TEXT | nullable |
| `erledigt_am` | TEXT | nullable |
| `erledigt` | INTEGER | NOT NULL DEFAULT 0 · CHECK IN (0,1) |
| `quelle` | TEXT | NOT NULL DEFAULT 'benutzer' · CHECK IN ('benutzer','system') |
| `dok_id` | INTEGER | FK dokumente(id) |
| `regel_key` | TEXT | nullable |
| `sortierung` | INTEGER | NOT NULL DEFAULT 0 |

---

### klage_entwurf
*Erstellt: Migration 61 (backend/db) · Klage-Wizard „Entwurf speichern" (Paket 1)*

Ein Wizard-Entwurf je Akte (`akte_id` UNIQUE, Upsert per `ON CONFLICT`). `entwurf_json` trägt den kompletten Wizard-Zustand als JSON, `format_version` erkennt Entwürfe älterer Wizard-Stände — der Fortsetzen-Dialog bietet bei veralteter Version dann nur „Neu beginnen" statt „Fortsetzen" an.

| Spalte | Typ | Constraint |
|---|---|---|
| `id` | INTEGER | **PK AUTOINCREMENT** |
| `akte_id` | TEXT | NOT NULL UNIQUE FK unfallakte(az) ON DELETE CASCADE |
| `entwurf_json` | TEXT | NOT NULL — kompletter Wizard-Zustand als JSON |
| `format_version` | INTEGER | NOT NULL |
| `gespeichert_am` | TEXT | NOT NULL DEFAULT datetime('now','localtime') |

Endpunkte: `GET/PUT/DELETE /akten/<az>/klage/entwurf` (Router `backend/routers/klage_routes.py`).

---

### abschluss_status (Migration 67)
Kuratiertes Schlussfeld je Akte — `schluss_typ` ist zugleich der
Abschluss/Sachstand-Umschalter des Abschlussberichts.

| Spalte | Typ | Bedeutung |
|---|---|---|
| `akte_az` | TEXT PK → unfallakte(az) | Akte |
| `schluss_typ` | TEXT, CHECK: `offen` · `endgueltig` · `vorbehalt_spaetfolgen` · `restposten` | Default `offen` (= Sachstand) |
| `schluss_text` | TEXT | anwaltlicher Schlusstext |
| `verjaehrung_datum` | TEXT | nur bei `vorbehalt_spaetfolgen` |
| `naechste_schritte_text` | TEXT | Sachstand-Block „Woran wir arbeiten" |
| `kuratiert_am` / `kuratiert_von` | TEXT | Audit |

Endpunkte: `GET /akten/<az>/abschluss-uebersicht` (Übersichts-Objekt aus `services/abschluss_uebersicht.py`), `PUT /akten/<az>/abschluss-status` (Kuration). DOCX-Renderer: `word/abschlussbericht.py`.

---

### weitere Tabellen (Kurzform)

| Tabelle | Mig | Zweck | PK |
|---|---|---|---|
| `klassifikation_training` | 25 | Korrektur-Paare für TF-IDF-Retraining · rohtext_hash, klasse_auto, klasse_korrigiert | INTEGER PK AUTO |
| `eakte_klassifikation` | 26 | Batch-Klassifikation E-Akte-Dokumente · UNIQUE(eakte_nr) | INTEGER PK AUTO |
| `schadenposition_belege` | 27 | Beleg↔Position-Verknüpfung · UNIQUE(akte_az, position_key, dokument_id) | INTEGER PK AUTO |
| `rechnung_parse_cache` | 29 | Parse-Cache für E-Akte-PDFs · Key: eakte_nr + datei_groesse | eakte_nr INTEGER PK (kein AUTO) |
| `fragebogen_erstkontakt` | 30 | Website-Unfallbogen-Einsendungen ohne AZ | INTEGER PK AUTO |
| `email_absender_vorlagen` | 18+21 | Versicherer-Domain → Kategorie/Kürzel · ~70 Seed-Einträge | INTEGER PK AUTO |
| `personenschaden_beteiligte` | 15 | Beteiligte der Heilbehandlung als RA-MICRO-Adressnr | INTEGER PK AUTO |
| `konfiguration` | 33 | Key-Value-Store für System-Einstellungen · PK = schluessel TEXT | TEXT PK |
| `gebuehren_berechnung` | 35 | RVG Nr. 2300 VV Berechnung je Akte · UNIQUE(akte_id) | INTEGER PK (kein AUTO) |
| `portal_sync_queue` | 38 | Outbox für Stakeholder-Portal · kein FK auf unfallakte | INTEGER PK AUTO |
| `portal_einladungen` | 38 | Portal-Zugriffseinladungen je Beteiligter | INTEGER PK AUTO |
| `stellungnahme_texte` | 40 | Persistierte Gegenargument-Texte je Akte/Position | PK (az, gruppe_key) TEXT composite |
| `pruefdienstleister` | 64 | Stammtabelle Prüfdienstleister (name UNIQUE, erkennungsmuster, aktiv) · Seeds | INTEGER PK AUTO |

**Mig 64 außerdem:** `ereignis_positionen.begruendung_roh` TEXT (Versicherer-Wortlaut der Kürzungsbegründung, wird von `ereignis_service.schreibe_ereignis` persistiert).

---

## 2. Views

### v_schadensummen
*Liest aus: `schadenpositionen`*  
**ACHTUNG**: Berechnung verwendet `reparaturkosten` (Legacy-Feld), nicht `rep_gutachten_netto`. Ist damit für Akten die ausschließlich über die neuen Felder erfasst wurden veraltet.

```sql
fahrzeugschaden_netto = reparaturkosten + wiederbeschaffung - restwert + wertminderung
gesamt_brutto         = fahrzeugschaden_netto + nutzungsausfall + mietwagenkosten
                      + sv_kosten + abschleppkosten + standkosten + anabmeldekosten
                      + schmerzensgeld + sonstiges
```

### v_regulierungsstatus
*Liest aus: `unfallakte` + `v_schadensummen` + `abrechnungsschreiben` + `regulierung_positionen`*

```sql
betrag_gefordert = v_schadensummen.gesamt_brutto
betrag_reguliert = SUM(regulierung_positionen.betrag_reguliert) GROUP BY akte_id
differenz        = betrag_gefordert - betrag_reguliert
```

---

## 3. WDM-Mapping

### WDM_REGULIERUNG_MAP — regulierte Beträge (Suffix G = gezahlt)
*Quelle: `backend/ramicro/wdm_regulierung_service.py`*  
*Datenquelle: `_tbl0WDMDaten` in RA-MICRO SQL Server (Tabelle `RAMICRO`)*

```
WDM-Variable (sName)   → position_key (regulierung_positionen) / Python-Variable
──────────────────────────────────────────────────────────────────────────────────
varREPKOSTENSVG        → rep_gutachten_netto
varREPKOSTENG          → rep_rechnung_netto
varKOSTENSVG           → sv_kosten
varKOSTENNBG           → kostennb
varABSCHLEPPG          → abschleppkosten
varSTANDKOSTENG        → standkosten
varMIETWAGENG          → mietwagenkosten
varVERDIENSTG          → verdienstausfall
varANABKOSTENG         → anabmeldekosten
varHAUSHALTG           → haushalt
varUNKOSTENG           → unkostenpauschale
varWERTMINDG           → wertminderung
varNUTZUNGSAG          → nutzungsausfall
varSGVORSCHUSS         → schmerzensgeld
varVORSCHUSSG          → vorschuss
varSSCHADEN1G          → sonstiges_wdm_1   (regulierung_positionen.position_key)
varSSCHADEN2G          → sonstiges_wdm_2
varSSCHADEN3G          → sonstiges_wdm_3
varSSCHADEN4G          → sonstiges_wdm_4
varSSCHADEN5G          → sonstiges_wdm_5
varSSCHADEN6G          → sonstiges_wdm_6

Sondervariablen (kein Betrag, werden separat abgefragt):
varRGGDAT              → Datum der Regulierung (Format TT.MM.JJJJ → ISO)
varQUOTEG              → Haftungsquote (0–100)
```

### WDM_FORDERUNG_MAP — geforderte Beträge (Schadenseite, ohne Suffix G)

```
position_key           → WDM-Variable (Forderungsseite)
──────────────────────────────────────────────────────────────────────────────────
rep_gutachten_netto    → varREPKOSTENSV
rep_rechnung_netto     → varREPKOSTEN
sv_kosten              → varKOSTENSV
wertminderung          → varWERTMIND
nutzungsausfall        → varNUTZUNGSA
schmerzensgeld         → varSCHMGELD
verdienstausfall       → varVERDIENST
unkostenpauschale      → varUNKOSTEN
sonstiges_wdm_1        → varSSBETRAG1   (Betrag der Forderungsposition)
sonstiges_wdm_2        → varSSBETRAG2
sonstiges_wdm_3        → varSSBETRAG3
sonstiges_wdm_4        → varSSBETRAG4
sonstiges_wdm_5        → varSSBETRAG5A  ← SONDERFALL: "5A" nicht "5"!
sonstiges_wdm_6        → varSSBETRAG6

Labels für sonstiges_wdm_*:
varSSCHADEN1 … varSSCHADEN6  → Bezeichnungstext (kein Betrag)
```

### _schaden_dict() — DB-Spalten → Frontend-JSON
*Quelle: `backend/routers/schaden_routes.py` Funktion `_schaden_dict(s)`*

```
DB-Spalte (schadenpositionen)   → JSON-Key (Frontend)
──────────────────────────────────────────────────────
id                              → id
akte_id                         → akte_id
quelle                          → quelle
erfasst_am                      → erfasst_am
[berechnet]                     → gesamt_brutto  (Python-Property, nicht DB-Feld)
reparaturkosten                 → reparaturkosten
rep_gutachten_netto             → rep_gutachten_netto
rep_gutachten_mwst              → rep_gutachten_mwst
rep_rechnung_netto              → rep_rechnung_netto
rep_rechnung_brutto             → rep_rechnung_brutto
wiederbeschaffung               → wiederbeschaffung
restwert                        → restwert
wertminderung                   → wertminderung
abrechnungsart                  → abrechnungsart
nutzungsausfall                 → nutzungsausfall
mietwagenkosten                 → mietwagenkosten
mietwagenkosten_netto           → mietwagenkosten_netto
mietwagenkosten_ust             → mietwagenkosten_ust
sv_kosten                       → sv_kosten
sv_kosten_netto                 → sv_kosten_netto
sv_kosten_ust                   → sv_kosten_ust
kostennb                        → kostennb
kostennb_ust                    → kostennb_ust
abschleppkosten                 → abschleppkosten
abschleppkosten_netto           → abschleppkosten_netto
abschleppkosten_ust             → abschleppkosten_ust
standkosten                     → standkosten
standkosten_netto               → standkosten_netto
standkosten_ust                 → standkosten_ust
anabmeldekosten                 → anabmeldekosten
anabmeldekosten_netto           → anabmeldekosten_netto
anabmeldekosten_ust             → anabmeldekosten_ust
schmerzensgeld                  → schmerzensgeld
verdienstausfall                → verdienstausfall
haushalt                        → haushalt
unkostenpauschale               → unkostenpauschale
sonstiges                       → sonstiges
sonstiges_beschr                → sonstiges_beschr
wdm_extras_json                 → wdm_extras_json
wdm_info_json                   → wdm_info_json
[aus wdm_extras_json geparsed]  → _extras  (Liste von WDM-Sonstiges-Positionen)
```

---

## 4. Kritische Felder (Netto/Brutto/Berechnung)

### Fahrzeugschaden-Logik (`berechne_abrechnungsart()` in `models/schaden.py`)

Die Abrechnungsart wird serverseitig berechnet und ist die **einzige kanonische Quelle**:

```
rep_gut   = rep_gutachten_netto  (Fallback: reparaturkosten)
rep_rn    = rep_rechnung_netto
rep_rb    = rep_rechnung_brutto
wbw       = wiederbeschaffung
rst       = restwert
netto_fzg = wbw - rst

abrechnungsart = 'fiktiv'      → fahrzeugschaden = rep_gut
               = 'konkret'     → fahrzeugschaden = rep_rn (oder rep_gut falls rn=0)
               = 'totalschaden'→ fahrzeugschaden = wbw - rst

130%-Fall: rep_rn > netto_fzg UND rep_rn <= 1.3*wbw → gilt als 'konkret'
```

### Netto/Brutto-Dualität in Nebenkosten (Migration 14)

Für `sv_kosten`, `abschleppkosten`, `standkosten`, `anabmeldekosten`, `mietwagenkosten`:
- Das alte `*_kosten`-Feld = Brutto-Fallback (bleibt erhalten)
- `*_kosten_netto` + `*_kosten_ust` = neue Felder für vorsteuerabzugsberechtigte Mandanten
- Frontend zeigt je nach `vorsteuer='J'` den Netto-Wert (ohne USt)

### WDM-Betragsformat (parse_wdm_betrag)
```
'2.616,71 EUR' → 2616.71    (Tausenderpunkt entfernen, Komma→Punkt)
'650,00'       → 650.00     (kein EUR-Suffix)
EUR-Suffix:    inkonsistent, mal vorhanden mal nicht
```

---

## 5. Bekannte Fallstricke

| Nr. | Stelle | Problem |
|---|---|---|
| **F-01** | `v_schadensummen` (schema.py) | Berechnet `gesamt_brutto` aus Legacy-Feld `reparaturkosten`, nicht aus `rep_gutachten_netto`. View ist für neue Akten inhaltlich falsch. Python-Property `Schadenposition.gesamt_brutto` ist korrekt. |
| **F-02** | `abrechnungsschreiben.akte_id` | DDL in Migration 3 deklariert FK als `REFERENCES unfallakte(id)`. Nach Migration 5 (AZ als PK) ist die Constraint-Definition veraltet. SQLite prüft FKs nur wenn `PRAGMA foreign_keys = ON` — in der Praxis kein Problem, aber bei Schema-Export verwirrend. |
| **F-03** | `varSSBETRAG5A` | RA-MICRO schreibt Sonderfall "5A" statt "5" für den 5. sonstigen Schaden. Hartcodiert in `WDM_FORDERUNG_MAP`. Würde bei varSSBETRAG5 (ohne A) stille 0,00 zurückgeben. |
| **F-04** | `sAnrede` numerisch | RA-MICRO speichert Anrede als Zahl ("1"=Herr, "2"=Frau). In `_beteiligte_dict()` (`ramicro_akte_routes.py`) wird `sAnrede` als Rohzahl weitergegeben — Frontend oder Word-Service muss mappen. |
| **F-05** | Zwei `schema_manager.py` | Root-Level `backend/schema_manager.py` (legacy) und `backend/db/schema_manager.py` (aktiv). `app.py` importiert nur die DB-Version. `unfalldetails` und `vertreter_name/funktion` wurden ursprünglich über den Root-Manager erstellt — Migration 28 in der DB-Version setzt voraus dass `unfalldetails` bereits existiert. |
| **F-06** | `email_import_log.akte_id` | Ursprünglich `INTEGER REFERENCES unfallakte(id)` (Migration 2). Migration 17 baut die Tabelle neu als `TEXT REFERENCES unfallakte(az)`. Zwischen Migration 2 und 17 waren alle Zuordnungen inkonsistent. |
| **F-07** | `sonstiges_wdm_X` vs `extra_wdm_ssX` | Im Frontend sind WDM-Sonstiges-Positionen aus `wdm_extras_json` als `extra_wdm_ss1..6` gekeyed. In `regulierung_positionen.position_key` heißen dieselben Positionen `sonstiges_wdm_1..6`. Beim Remap-Fix muss explizit gemappt werden. |
| **F-08** | `gesamt_brutto` Property | `Schadenposition.gesamt_brutto` (Python) berechnet `rep_rechnung_netto` vs `rep_gutachten_netto` und nimmt den höheren Wert. `v_schadensummen.gesamt_brutto` (SQL) addiert einfach `reparaturkosten`. Beide können für dieselbe Akte verschiedene Werte liefern. |
| **F-09** | `unfallakte.az` Freiformat | Das Aktenzeichen ist ein beliebiger String aus RA-MICRO (z.B. `31/21 AS`, `285/26`). Kein normiertes Format. Alle FK-Lookups müssen exakt matchen. Stripps und Leerzeichen-Varianten können Fehler verursachen. |
| **F-10** | `rechnung_parse_cache.eakte_nr` | PK ist `eakte_nr` direkt (kein AUTOINCREMENT). Das ist die `eakte_nr` aus `raEloakte.tblElo_AktenArchiv`. Duplikat-Handling: `INSERT OR REPLACE` (Upsert). Separate Cache-Logik von `eakte_cache` (In-Memory). |
