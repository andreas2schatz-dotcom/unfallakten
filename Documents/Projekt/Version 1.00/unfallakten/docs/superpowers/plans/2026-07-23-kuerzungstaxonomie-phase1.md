# Kürzungstaxonomie Phase 1 — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kürzungen werden als Differenz Forderung/Zahlung erkannt, per Stichwort-Matching (+ LLM-Fallback) einem A–F-Typ zugeordnet, mit Pflicht-Begründung und Betrag erfasst, über Runden verglichen — und steuern die Baustein-Vorauswahl in Stellungnahme UND Klage-Wizard.

**Architecture:** Option (b) aus DECISIONS 2026-07-23: Das Tripel (Position × Typ × Betrag) lebt im Ereignismodell (`ereignis_positionen`), `regulierung_positionen` bleibt Erfassungsweg im Doppelschreibmuster. Taxonomie-Metadaten (Codes, Keywords, `verifiziert_am`) leben in einer neuen fail-louden YAML-Registry `backend/registry/kuerzungstypen/`; die DB-Tabelle `kuerzungsarten` bleibt FK-Ziel und Träger des editierbaren `textbaustein`. Zwei getrennte Faltungen: Positions-Faltung (existiert) und neuer Runden-Vergleich (liest nur).

**Tech Stack:** Flask + SQLite (Migration 64), YAML-Registry (Muster `positionsmodell_registry.py`), React + Vitest, pytest (`unittest.TestCase`, temp-DB-Muster `_DBBasis`), LM Studio via `llm_service.klassifiziere_geschlossen`.

## Global Constraints

- **RA-MICRO strikt read-only** — kein Schreibzugriff auf den SQL Server.
- **Aktive DB = Docker-Volume** `/app/data/unfallakten.db` im Container `unfallakten-backend-dev` — NICHT `backend/data/`. Jedes Import-/Prüf-Kommando läuft via `docker exec`.
- **Flask-Reloader-Falle:** Vor JEDEM Edit an `backend/db/schema_manager.py`: `docker stop unfallakten-backend-dev`; nach Abschluss aller Edits: `docker start unfallakten-backend-dev`. Kein `executescript()`; `conn.commit()` vor UND nach jedem DDL.
- **TDD:** Test zuerst, Test rot sehen, implementieren, Test grün sehen, committen.
- **Ereignis-Invarianten:** `ereignis_service.schreibe_ereignis` bleibt einziger Ereignis-Schreibpunkt; Review-Freigabe bleibt einziger Schreibweg in Akten-Tabellen (`INTAKE_REVIEW_PFLICHT`); neue Faltungen lesen nur.
- **Typen sind append-only:** nie umdefinieren; Varianten bekommen Suffix-Codes (`A04b`), Statistik aggregiert über Code-Präfix.
- **`verifiziert_am` = „handgeprüft RA Schatz, Juli 2026"** für alle Bestandsbausteine (DECISIONS 2026-07-23).
- **Zielwerte** (Messung nach ~4 Wochen Betrieb): Abdeckung ≥ 90 %, Trefferquote Typ-Vorschlag ≥ 75 %, Positions-/Betragszuordnung auf Zahlmitteilungen ≥ 90 %.
- **Keine Kommentare im Code** außer bei nicht-offensichtlichem Verhalten. Zielsprache der UI: Deutsch.
- **Git:** Commits aus dem Projektordner heraus, NIE `git add -A` (Git-Wurzel = Home-Verzeichnis).

---

## Detail-Entscheidungen — BESTÄTIGT (RA Schatz, 2026-07-23, bei Plan-Freigabe)

Die A–F-Zuordnung aus DECISIONS ist übernommen. Drei offene Punkte wurden bei der Freigabe wie vorgeschlagen entschieden (alle drei Empfehlungen bestätigt):

1. **Tankrest / Batteriestützbetrieb / Fehlerspeicher** (Bestand Nr. 7/8/9) haben keinen Code aus Phase 0 (nur „A05-nah" für Fehlerspeicher). **Vorschlag: A05a Fehlerspeicher, A05b Batteriestützbetrieb, A05c Tankrest** (Kalkulationspositionen nahe A05 Arbeitszeitwerte).
2. **Varianten-Modell:** Mehrere Bausteine zum selben Grundtyp (JVEG/HUK-Tableau zu E01, ghpfup2 zu E06, ghpfansprort zu A04, ghpfreprg zu B01) werden **als eigene `kuerzungsarten`-Zeilen mit Suffix-Code geführt** (E01b, E01c, E06b, A04b, B01b) — weil eine Zeile genau einen editierbaren Textbaustein trägt. Statistik aggregiert über den Präfix (E01* = SV-Grundhonorar).
3. **Technische Kürzungen** (Bestand Nr. 11, Sammel-Kürzung Reparaturweg): **Vorschlag A09** (Reparaturweg). Phase 0 nannte „A07/A08/A09" als Bereich; A07 ist jetzt Neu-für-alt (eigener Typ), A08 bleibt frei für künftige „nicht unfallkausal"-Fälle.

## A–F-Zuordnungstabelle (verbindlich nach Freigabe)

**Bestand (19 Zeilen, bekommen `typ_code` + `verifiziert_am`):**

| DB-id | Bezeichnung | typ_code |
|---|---|---|
| 1 | Stundenverrechnungssätze | A04 |
| 2 | Wertminderung | C01 |
| 3 | Ersatzteilaufschläge / UPE-Zuschläge | A01 |
| 4 | Verbringungskosten | A02 |
| 5 | Beilackierung | A03 |
| 6 | Kürzung Reparaturrechnung | B01 |
| 7 | Tankrest | A05c * |
| 8 | Batteriestützbetrieb | A05b * |
| 9 | Fehlerspeicher auslesen | A05a * |
| 10 | Kleinteilpauschale | A06 |
| 11 | Technische Kürzungen | A09 * |
| 12 | Zulassungsdienst | E05 |
| 13 | Kennzeichen / Schilderkosten | E05b |
| 14 | Wunschkennzeichen | E05c |
| 15 | Unkostenpauschale | E06 |
| 16 | Nutzungsausfall | D01 |
| 17 | Kürzung Sachverständigenrechnung | E01 |
| 18 | Mietwagenrechnung | D04 |
| 19 | Verdienstausfall | F03 |

(* = siehe „Zur Bestätigung", Punkte 1 und 3.)

**Neu (13 Zeilen, IDs 20–32 per Seed in Migration 64):**

| DB-id | Bezeichnung | typ_code | Baustein-Quelle |
|---|---|---|---|
| 20 | Neu-für-alt-Abzug | A07 | — (Baustein fehlt, RA Schatz schreibt später) |
| 21 | Reparaturbestätigung | A10 | repbest.RTF |
| 22 | Abrechnungszeitpunkt / Preissteigerung | A11 | ghpfzeitpunkt.rtf |
| 23 | Stundenverrechnungssätze (Variante Prüfbericht-Erwiderung) | A04b | ghpfansprort.doc (→ .rtf konvertieren) |
| 24 | Rechnungskürzung trotz Reparatur (Variante) | B01b | ghpfreprg.rtf |
| 25 | Wertminderung – Umsatzsteuer | C01b | wertminderungsteuer.rtf |
| 26 | Nutzungsausfall Schadentag / SV-Besichtigung | D01b | nutzungsausfall für schadentag und sv besichtigung.rtf |
| 27 | SV-Grundhonorar – JVEG | E01b | ghpfjveg.rtf |
| 28 | SV-Grundhonorar – HUK-Tableau | E01c | huktableau.rtf |
| 29 | SV-Nebenkosten-Pauschale | E02 | ghpvnkpauschal.rtf |
| 30 | Abschleppkosten | E03 | ghpfabschleppgeb.rtf |
| 31 | Unkostenpauschale – 2. Runde | E06b | ghpfup2.rtf |
| 32 | Schmerzensgeld-Zurückstellung (HWS/Nachweis) | F01 | hws.RTF |

**Kein Kürzungstyp** (DECISIONS + Sichtung 2026-07-23): ghpfandrohungsv (Eskalationsbaustein zu Nr. 11), heilverlauf (Mandantenkommunikation), ghpfstellung (Rahmentext), vertretungsanzeige (aussortieren), ghpfstverort.DOC (LEER — 0 Wörter, Sichtung 2026-07-23), verweis/werkstattrisiko/etc. (bereits Bestand).

`kategorie`-Altspalte für neue Zeilen (CHECK-kompatibel): A*/B*/C* → `fahrzeugschaden`, D*/E*/F* → `sonstiger_schaden`. Die A–F-Gruppierung der UI kommt aus dem `typ_code`-Präfix, nicht aus der Altspalte.

---

## Datei-Struktur (was entsteht / was sich ändert)

**Neu:**
- `backend/registry/kuerzungstypen/*.yaml` — 32 Typ-Dateien (eine je Typ, Dateiname = `<typ_code>.yaml`)
- `backend/services/kuerzungstyp_registry.py` — fail-louder Loader (Muster `positionsmodell_registry.py`)
- `backend/services/kuerzungstyp_matching.py` — Regel-Matching + LLM-Fallback
- `backend/services/abrechnungsrunden_service.py` — Runde-1↔Runde-2-Vergleich (Lese-Faltung)
- `backend/registry/positions_synonyme.yaml` — Positions-Synonymik je Versicherer-Template
- `frontend/src/components/TextbausteinEditor.jsx` (+ `.test.jsx`) — Editor-Komponente (V11 erbt)
- `backend/tests/test_kuerzungstaxonomie_migration.py`, `test_kuerzungstyp_registry.py`, `test_kuerzungstyp_matching.py`, `test_abrechnungsrunden.py`, `test_kuerzungsarten_textbaustein_rest.py`, `test_pruefbericht_verkettung.py`
- `tools/kuerzungsmatching_report.py` — Messanker für die 4-Wochen-Zielwerte

**Geändert:**
- `backend/db/schema_manager.py` — Migration 64 (Reloader-Regel beachten!)
- `tools/import_textbausteine.py` — Mapping-Erweiterung um 12 Dateien
- `backend/models/kuerzungsart.py` — `textbaustein`, `typ_code`, `verifiziert_am` in Dataclass/`as_dict`/Whitelists
- `backend/routers/kuerzungsarten_routes.py` — Platzhalter-Katalog + Vorschau-Endpoint
- `backend/routers/abrechnungsschreiben_routes.py` — Typ-Vorschlags-Endpoint, Pflichtfeld-Validierung, `typ_quelle`
- `backend/routers/pruefberichte_routes.py` — Verkettungs-Kandidaten + PATCH
- `backend/routers/stellungnahme_routes.py` — `textbaustein`-Fallback in Vorschau
- `backend/services/eingehende_ereignisse.py` — `begruendung_roh` durchreichen
- `backend/services/ereignis_service.py` — `begruendung_roh` in INSERT (+ `rebuild_cache` unverändert lassen: Spalte nur Ebene 1)
- `backend/workflow/dispatcher.py` — `abzuege_detail` nicht mehr verwerfen
- `frontend/src/sections/RegulierungSection.jsx` — Typ-Vorschlag-UI, `begruendung_roh`-Pflicht, Runden-Kachel
- `frontend/src/views/KuerzungskatalogView.jsx` — Editor-Einbau, A–F-Gruppierung
- `frontend/src/api.js` — neue Client-Funktionen

## Task-Reihenfolge und Session-Schnitte

Empfohlener Schnitt in 4 Umsetzungs-Sessions: **S1** = Tasks 1–3 (Datenfundament), **S2** = Tasks 4–6 (Matching), **S3** = Tasks 7–9 (Workflow/UI), **S4** = Tasks 10–12 (Editor + Konsistenz + Messanker). Jeder Task endet mit grünen Tests + Commit.

---

### Task 1: Migration 64 — Taxonomie-Datenfundament

**Files:**
- Modify: `backend/db/schema_manager.py` (3 Stellen: `MIGRATIONS`-Dict nach Eintrag 63, Dispatch-`elif` nach Migration 63, Handler-Funktion nach `_run_migration_63`)
- Test: `backend/tests/test_kuerzungstaxonomie_migration.py`

**Interfaces:**
- Produces: Spalten `kuerzungsarten.typ_code TEXT` (unique via Partial-Index), `kuerzungsarten.verifiziert_am TEXT`; Tabelle `pruefdienstleister(id, name, erkennungsmuster, aktiv, erstellt_am)`; Spalten `pruefberichte.pruefdienstleister_id`, `abrechnungsschreiben.pruefdienstleister_id`, `ereignis_positionen.begruendung_roh TEXT`, `regulierung_positionen.typ_quelle TEXT`; 13 neue `kuerzungsarten`-Zeilen (IDs 20–32 gemäß Zuordnungstabelle).

- [ ] **Step 1: Dev-Backend stoppen (Reloader-Falle)**

Run: `docker stop unfallakten-backend-dev`
Expected: Containername wird ausgegeben.

- [ ] **Step 2: Failing Test schreiben**

`backend/tests/test_kuerzungstaxonomie_migration.py` — nach dem `_DBBasis`-Muster aus `test_bugfix_p1_intake_v7.py` (temp-DB, `_db.DB_PATH` + `os.environ["DB_PATH"]` setzen, `init_db()`):

```python
import os
import sqlite3
import tempfile
import unittest


class TestMigration64(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()
        self.conn = sqlite3.connect(self._db_pfad)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        os.unlink(self._db_pfad)

    def _spalten(self, tabelle):
        return {r["name"] for r in self.conn.execute(f"PRAGMA table_info({tabelle})")}

    def test_kuerzungsarten_neue_spalten(self):
        self.assertIn("typ_code", self._spalten("kuerzungsarten"))
        self.assertIn("verifiziert_am", self._spalten("kuerzungsarten"))

    def test_bestand_hat_typ_codes_und_stempel(self):
        rows = self.conn.execute(
            "SELECT id, typ_code, verifiziert_am FROM kuerzungsarten WHERE id <= 19"
        ).fetchall()
        self.assertEqual(len(rows), 19)
        erwartet = {1: "A04", 2: "C01", 3: "A01", 4: "A02", 5: "A03", 6: "B01",
                    7: "A05c", 8: "A05b", 9: "A05a", 10: "A06", 11: "A09",
                    12: "E05", 13: "E05b", 14: "E05c", 15: "E06", 16: "D01",
                    17: "E01", 18: "D04", 19: "F03"}
        for r in rows:
            self.assertEqual(r["typ_code"], erwartet[r["id"]])
            self.assertEqual(r["verifiziert_am"], "handgeprüft RA Schatz, Juli 2026")

    def test_neue_typen_vorhanden(self):
        codes = {r["typ_code"] for r in self.conn.execute(
            "SELECT typ_code FROM kuerzungsarten WHERE id > 19")}
        self.assertEqual(codes, {"A07", "A10", "A11", "A04b", "B01b", "C01b",
                                 "D01b", "E01b", "E01c", "E02", "E03", "E06b", "F01"})

    def test_typ_code_unique(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO kuerzungsarten (bezeichnung, kategorie, typ_code) "
                "VALUES ('Dublette', 'fahrzeugschaden', 'A04')")

    def test_pruefdienstleister_tabelle_und_seeds(self):
        namen = {r["name"] for r in self.conn.execute(
            "SELECT name FROM pruefdienstleister")}
        self.assertTrue({"ControlExpert", "DEKRA", "Eucon", "SSH",
                         "Audatex", "GTÜ", "DA Direkt"} <= namen)

    def test_neue_fk_und_pflichtfeld_spalten(self):
        self.assertIn("pruefdienstleister_id", self._spalten("pruefberichte"))
        self.assertIn("pruefdienstleister_id", self._spalten("abrechnungsschreiben"))
        self.assertIn("begruendung_roh", self._spalten("ereignis_positionen"))
        self.assertIn("typ_quelle", self._spalten("regulierung_positionen"))

    def test_schema_version_64(self):
        v = self.conn.execute("SELECT MAX(version) v FROM schema_version").fetchone()["v"]
        self.assertGreaterEqual(v, 64)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Test rot sehen**

Run: `docker start unfallakten-backend-dev && docker exec unfallakten-backend-dev python -m pytest backend/tests/test_kuerzungstaxonomie_migration.py -v` — dann Container wieder stoppen: `docker stop unfallakten-backend-dev`
Expected: FAIL (`typ_code` fehlt).
(Falls Tests lokal ohne Container laufen — wie die bestehende Suite —, stattdessen lokal `python -m pytest backend/tests/test_kuerzungstaxonomie_migration.py -v`; der Container muss nur bei Edits an `schema_manager.py` gestoppt sein.)

- [ ] **Step 4: Migration 64 implementieren — alle 3 Edits, solange der Container gestoppt ist**

Edit A — `MIGRATIONS`-Dict, direkt nach dem 63er-Eintrag:

```python
    64: "-- migration_64_kuerzungstaxonomie",  # Handled by _run_migration_64
```

Edit B — Dispatch-Kette, nach dem `elif version == 63:`-Block:

```python
            elif version == 64:
                _run_migration_64(conn)
```

Edit C — Handler nach `_run_migration_63` (WICHTIG: kompletter Funktionskörper in EINEM Edit; kein `executescript`; `conn.commit()` vor und nach jedem DDL):

```python
_TYP_CODES_BESTAND = {
    1: "A04", 2: "C01", 3: "A01", 4: "A02", 5: "A03", 6: "B01",
    7: "A05c", 8: "A05b", 9: "A05a", 10: "A06", 11: "A09",
    12: "E05", 13: "E05b", 14: "E05c", 15: "E06", 16: "D01",
    17: "E01", 18: "D04", 19: "F03",
}

_KUERZUNGSARTEN_NEU = [
    ("Neu-für-alt-Abzug", "fahrzeugschaden", "A07", 200),
    ("Reparaturbestätigung", "fahrzeugschaden", "A10", 210),
    ("Abrechnungszeitpunkt / Preissteigerung", "fahrzeugschaden", "A11", 220),
    ("Stundenverrechnungssätze (Variante Prüfbericht-Erwiderung)",
     "fahrzeugschaden", "A04b", 230),
    ("Rechnungskürzung trotz Reparatur (Variante)", "fahrzeugschaden", "B01b", 240),
    ("Wertminderung – Umsatzsteuer", "fahrzeugschaden", "C01b", 250),
    ("Nutzungsausfall Schadentag / SV-Besichtigung", "sonstiger_schaden", "D01b", 260),
    ("SV-Grundhonorar – JVEG", "sonstiger_schaden", "E01b", 270),
    ("SV-Grundhonorar – HUK-Tableau", "sonstiger_schaden", "E01c", 280),
    ("SV-Nebenkosten-Pauschale", "sonstiger_schaden", "E02", 290),
    ("Abschleppkosten", "sonstiger_schaden", "E03", 300),
    ("Unkostenpauschale – 2. Runde", "sonstiger_schaden", "E06b", 310),
    ("Schmerzensgeld-Zurückstellung (HWS/Nachweis)", "sonstiger_schaden", "F01", 320),
]

_PRUEFDIENSTLEISTER_SEEDS = [
    ("ControlExpert", r"control.?expert"),
    ("DEKRA", r"dekra"),
    ("Eucon", r"eucon"),
    ("SSH", r"\bssh\b"),
    ("Audatex", r"audatex"),
    ("GTÜ", r"gtue|gtü"),
    ("DA Direkt", r"da\s+direkt"),
]

VERIFIKATIONS_STEMPEL = "handgeprüft RA Schatz, Juli 2026"


def _run_migration_64(conn: sqlite3.Connection) -> None:
    """
    Migration 64 - Kürzungstaxonomie Phase 1:
    typ_code/verifiziert_am auf kuerzungsarten, 13 neue A-F-Typen,
    Stammtabelle pruefdienstleister, FK-Spalten, begruendung_roh, typ_quelle.
    Kein executescript, explizite Commits um DDL (Reloader-Falle).
    """
    conn.commit()
    spalten = {r[1] for r in conn.execute("PRAGMA table_info(kuerzungsarten)").fetchall()}
    if "typ_code" not in spalten:
        conn.execute("ALTER TABLE kuerzungsarten ADD COLUMN typ_code TEXT")
    if "verifiziert_am" not in spalten:
        conn.execute("ALTER TABLE kuerzungsarten ADD COLUMN verifiziert_am TEXT")
    conn.commit()
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uidx_kuerzungsarten_typ_code "
        "ON kuerzungsarten(typ_code) WHERE typ_code IS NOT NULL"
    )
    conn.commit()
    for kid, code in _TYP_CODES_BESTAND.items():
        conn.execute(
            "UPDATE kuerzungsarten SET typ_code = ?, verifiziert_am = ? "
            "WHERE id = ? AND typ_code IS NULL",
            (code, VERIFIKATIONS_STEMPEL, kid),
        )
    for bezeichnung, kategorie, code, sort in _KUERZUNGSARTEN_NEU:
        conn.execute(
            "INSERT OR IGNORE INTO kuerzungsarten "
            "(bezeichnung, kategorie, typ_code, verifiziert_am, sortierung) "
            "VALUES (?, ?, ?, ?, ?)",
            (bezeichnung, kategorie, code, VERIFIKATIONS_STEMPEL, sort),
        )
    conn.commit()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pruefdienstleister (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT NOT NULL UNIQUE,
            erkennungsmuster TEXT,
            aktiv            INTEGER NOT NULL DEFAULT 1 CHECK(aktiv IN (0,1)),
            erstellt_am      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    for name, muster in _PRUEFDIENSTLEISTER_SEEDS:
        conn.execute(
            "INSERT OR IGNORE INTO pruefdienstleister (name, erkennungsmuster) "
            "VALUES (?, ?)",
            (name, muster),
        )
    conn.commit()
    for tabelle, spalte, ddl in [
        ("pruefberichte", "pruefdienstleister_id",
         "ALTER TABLE pruefberichte ADD COLUMN pruefdienstleister_id INTEGER "
         "REFERENCES pruefdienstleister(id)"),
        ("abrechnungsschreiben", "pruefdienstleister_id",
         "ALTER TABLE abrechnungsschreiben ADD COLUMN pruefdienstleister_id INTEGER "
         "REFERENCES pruefdienstleister(id)"),
        ("ereignis_positionen", "begruendung_roh",
         "ALTER TABLE ereignis_positionen ADD COLUMN begruendung_roh TEXT"),
        ("regulierung_positionen", "typ_quelle",
         "ALTER TABLE regulierung_positionen ADD COLUMN typ_quelle TEXT"),
    ]:
        vorhanden = {r[1] for r in conn.execute(f"PRAGMA table_info({tabelle})").fetchall()}
        if spalte not in vorhanden:
            conn.commit()
            conn.execute(ddl)
            conn.commit()
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (64, "Migration 64 - Kürzungstaxonomie: typ_code, pruefdienstleister, "
             "begruendung_roh, typ_quelle"),
    )
    conn.commit()
    logger.info("Migration 64 abgeschlossen (Kürzungstaxonomie-Fundament).")
```

- [ ] **Step 5: Container starten, Test grün sehen, aktive DB migriert prüfen**

Run: `docker start unfallakten-backend-dev`, dann `python -m pytest backend/tests/test_kuerzungstaxonomie_migration.py -v`
Expected: alle Tests PASS.
Dann gegen die aktive DB verifizieren: `docker exec unfallakten-backend-dev python -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print(c.execute('SELECT MAX(version) FROM schema_version').fetchone(), c.execute('SELECT COUNT(*) FROM kuerzungsarten').fetchone())"`
Expected: `(64,) (32,)`.

- [ ] **Step 6: Commit**

```bash
git add backend/db/schema_manager.py backend/tests/test_kuerzungstaxonomie_migration.py
git commit -m "feat(kuerzungstaxonomie): Migration 64 - typ_code A-F, pruefdienstleister-Stamm, begruendung_roh, typ_quelle"
```

---

### Task 2: YAML-Registry `kuerzungstypen/` + fail-louder Loader

**Files:**
- Create: `backend/registry/kuerzungstypen/<typ_code>.yaml` (32 Dateien, z. B. `A04.yaml`, `E01b.yaml`)
- Create: `backend/services/kuerzungstyp_registry.py`
- Modify: `backend/app.py` (Registry beim App-Start laden, nach `lade_positionsmodell`)
- Test: `backend/tests/test_kuerzungstyp_registry.py`

**Interfaces:**
- Consumes: Migration-64-Seeds (`typ_code` in DB).
- Produces: `lade_kuerzungstypen(pfad=None, *, reload=False) -> KuerzungstypRegistry` mit `KuerzungstypRegistry(version: str, pfad: str, typen: Dict[str, Dict])`; je Typ-Dict: `typ_code, name, kategorie_code (A-F), kategorie_label, baustein_pfad (bool), keywords (List[str]), keywords_erfordert (List[str], optional), llm_hinweis (str), verifiziert_am (str)`. Konstante `KATEGORIEN_AF = {"A": "Reparaturkosten fiktiv", "B": "Reparaturkosten konkret", "C": "Fahrzeugwert", "D": "Ausfall/Mobilität", "E": "Nebenkosten", "F": "Personenschaden"}`.

- [ ] **Step 1: Failing Test schreiben**

```python
import unittest


class TestKuerzungstypRegistry(unittest.TestCase):
    def test_laedt_32_typen(self):
        from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
        reg = lade_kuerzungstypen(reload=True)
        self.assertEqual(len(reg.typen), 32)
        self.assertIn("A04", reg.typen)
        self.assertIn("E01b", reg.typen)

    def test_pflichtfelder_und_kategorien(self):
        from backend.services.kuerzungstyp_registry import (
            lade_kuerzungstypen, KATEGORIEN_AF)
        reg = lade_kuerzungstypen(reload=True)
        for code, typ in reg.typen.items():
            self.assertEqual(code, typ["typ_code"])
            self.assertIn(typ["kategorie_code"], KATEGORIEN_AF)
            self.assertTrue(typ["name"])
            self.assertTrue(typ["verifiziert_am"])
            self.assertIsInstance(typ["keywords"], list)

    def test_fail_loud_bei_fehlendem_verzeichnis(self):
        from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
        with self.assertRaises(RuntimeError):
            lade_kuerzungstypen("/nicht/vorhanden", reload=True)

    def test_konsistenz_registry_gegen_migration_seeds(self):
        from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
        from backend.db.schema_manager import _TYP_CODES_BESTAND, _KUERZUNGSARTEN_NEU
        reg = lade_kuerzungstypen(reload=True)
        erwartet = set(_TYP_CODES_BESTAND.values()) | {c for _, _, c, _ in _KUERZUNGSARTEN_NEU}
        self.assertEqual(set(reg.typen), erwartet)
```

Run: `python -m pytest backend/tests/test_kuerzungstyp_registry.py -v` → Expected: FAIL (Modul fehlt).

- [ ] **Step 2: Loader implementieren**

`backend/services/kuerzungstyp_registry.py` — exakt dem Muster von `positionsmodell_registry.py` folgen (Cache-Singleton je Pfad, `RuntimeError` bei fehlendem Verzeichnis / leerem Verzeichnis / YAML-Syntaxfehler / IO-Fehler, `version` = 16-Zeichen-SHA256 über alle YAML-Bytes, Env-Override `KUERZUNGSTYP_REGISTRY_PFAD`, Default `../registry/kuerzungstypen` relativ zur Datei):

```python
import hashlib
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml

KATEGORIEN_AF = {
    "A": "Reparaturkosten fiktiv",
    "B": "Reparaturkosten konkret",
    "C": "Fahrzeugwert",
    "D": "Ausfall/Mobilität",
    "E": "Nebenkosten",
    "F": "Personenschaden",
}

_PFLICHT = ("typ_code", "name", "kategorie_code", "verifiziert_am")


@dataclass(frozen=True)
class KuerzungstypRegistry:
    version: str
    pfad: str
    typen: Dict[str, Dict[str, Any]]


_cache: Dict[str, KuerzungstypRegistry] = {}


def standard_pfad() -> str:
    env = os.environ.get("KUERZUNGSTYP_REGISTRY_PFAD")
    if env:
        return env
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "registry", "kuerzungstypen"))


def lade_kuerzungstypen(pfad: Optional[str] = None, *,
                        reload: bool = False) -> KuerzungstypRegistry:
    p = pfad or standard_pfad()
    if not reload and p in _cache:
        return _cache[p]
    if not os.path.isdir(p):
        raise RuntimeError(f"Kürzungstyp-Registry-Verzeichnis fehlt: {p}")
    dateien = sorted(f for f in os.listdir(p) if f.endswith(".yaml"))
    if not dateien:
        raise RuntimeError(f"Kürzungstyp-Registry ist leer: {p}")
    typen: Dict[str, Dict[str, Any]] = {}
    h = hashlib.sha256()
    for datei in dateien:
        voll = os.path.join(p, datei)
        try:
            with open(voll, "rb") as fh:
                roh = fh.read()
        except OSError as e:
            raise RuntimeError(f"Kürzungstyp-Registry nicht lesbar: {voll}: {e}") from e
        h.update(roh)
        try:
            data = yaml.safe_load(roh)
        except yaml.YAMLError as e:
            raise RuntimeError(f"YAML-Fehler in {voll}: {e}") from e
        _validiere(datei, data, typen)
        data.setdefault("keywords", [])
        data.setdefault("keywords_erfordert", [])
        data.setdefault("llm_hinweis", "")
        data.setdefault("baustein_pfad", True)
        typen[data["typ_code"]] = data
    reg = KuerzungstypRegistry(version=h.hexdigest()[:16], pfad=p, typen=typen)
    _cache[p] = reg
    return reg


def _validiere(datei: str, data: Any, vorhandene: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise RuntimeError(f"{datei}: kein YAML-Mapping")
    for feld in _PFLICHT:
        if not data.get(feld):
            raise RuntimeError(f"{datei}: Pflichtfeld '{feld}' fehlt")
    code = data["typ_code"]
    if datei != f"{code}.yaml":
        raise RuntimeError(f"{datei}: Dateiname muss '{code}.yaml' sein")
    if code in vorhandene:
        raise RuntimeError(f"{datei}: typ_code '{code}' doppelt")
    if data["kategorie_code"] not in KATEGORIEN_AF:
        raise RuntimeError(f"{datei}: kategorie_code '{data['kategorie_code']}' unbekannt")
```

- [ ] **Step 3: Die 32 YAML-Dateien anlegen**

Format je Datei (Beispiel `A02.yaml`; Keywords aus dem jeweiligen Textbaustein + Phase-0-Stichwort-Fixes ableiten — Wortgrenzen-kritische Keywords NICHT als Teilstrings anlegen):

```yaml
typ_code: A02
name: Verbringungskosten
kategorie_code: A
baustein_pfad: true
keywords: ["Verbringung", "Verbringungskosten", "Fremdlackierung"]
keywords_erfordert: []
llm_hinweis: "Kürzung der Kosten für Verbringung des Fahrzeugs zur Lackiererei bei fiktiver Abrechnung"
verifiziert_am: "handgeprüft RA Schatz, Juli 2026"
```

Phase-0-Stichwort-Fixes verbindlich einarbeiten:
- `A06.yaml` (Kleinteile): keywords `["Kleinteilepauschale", "Kleinteilkostenpauschale", "Kleinteile"]` — Matching nutzt Wortgrenzen, damit „Kleinteilekostenpauschale" NICHT auf E06 Unkostenpauschale fällt.
- `E06.yaml` (Unkostenpauschale): keywords `["Unkostenpauschale", "Kostenpauschale", "Auslagenpauschale"]`, `keywords_erfordert: []` — Verwechslung mit A06 wird durch exakte Wortgrenze verhindert (`Kostenpauschale` matcht nicht in `Kleinteilekostenpauschale`).
- `E05b.yaml` (Kennzeichen): keywords `["Schilderkosten", "Kennzeichen"]`, `keywords_erfordert: ["Schilder", "Prägung", "Erneuerung", "neue Kennzeichen"]` — „Kennzeichen" allein (Briefkopf/Fahrzeugdaten) zählt nicht.
- `A07.yaml` (Neu-für-alt): keywords `["neu für alt", "Neu-für-alt", "Abzug neu für alt", "Vorteilsausgleich"]`.
- `F01.yaml`: keywords `["Schmerzensgeld", "Verletzungsnachweis", "HWS"]`, `baustein_pfad: true`.
- `A05a/A05b/A05c`: keywords je `["Fehlerspeicher"]` / `["Batteriestützbetrieb", "Stützbetrieb"]` / `["Tankrest", "Restkraftstoff"]`.

Für alle übrigen Typen: `name` = DB-`bezeichnung`, Keywords aus Bezeichnung + offensichtlichen Synonymen (z. B. `A01`: `["UPE", "UPE-Aufschläge", "Ersatzteilaufschläge", "Aufschläge auf Ersatzteile"]`; `E01`: `["Sachverständigenkosten", "Sachverständigenhonorar", "SV-Honorar", "Grundhonorar"]`; `E01b`: `["JVEG"]`; `E01c`: `["Honorartableau", "HUK-Tableau", "Tableau"]`; `E02`: `["Nebenkosten", "Nebenkostenpauschale", "Fahrtkosten", "Fotokosten", "Schreibkosten"]` mit `keywords_erfordert: ["Sachverständig", "Gutacht"]`; `E03`: `["Abschleppkosten", "Abschleppgebühr", "Bergungskosten"]`; `D01b`: `["Schadentag", "Besichtigungstag"]` mit `keywords_erfordert: ["Nutzungsausfall"]`; `A10`: `["Reparaturbestätigung", "Reparaturnachweis"]`; `A11`: `["Preissteigerung", "Abrechnungszeitpunkt", "Zeitpunkt der Abrechnung"]`; `B01b`: `["Reparaturrechnung"]`; `C01b`: `["Umsatzsteuer", "Mehrwertsteuer"]` mit `keywords_erfordert: ["Wertminderung", "merkantil"]`).

- [ ] **Step 4: App-Start-Anbindung**

In `backend/app.py`, direkt nach dem `lade_positionsmodell`-Block (Z. 140–150), gleiches Muster:

```python
    from backend.services.kuerzungstyp_registry import lade_kuerzungstypen
    reg_kt = lade_kuerzungstypen(reload=True)
    app.logger.info("Kürzungstyp-Registry geladen: %d Typen (Version %s)",
                    len(reg_kt.typen), reg_kt.version)
```

- [ ] **Step 5: Tests grün sehen**

Run: `python -m pytest backend/tests/test_kuerzungstyp_registry.py backend/tests/test_kuerzungstaxonomie_migration.py -v`
Expected: PASS (inkl. Konsistenztest Registry ↔ Migration-Seeds).

- [ ] **Step 6: Commit**

```bash
git add backend/registry/kuerzungstypen backend/services/kuerzungstyp_registry.py backend/app.py backend/tests/test_kuerzungstyp_registry.py
git commit -m "feat(kuerzungstaxonomie): YAML-Registry kuerzungstypen (32 A-F-Typen) + fail-louder Loader"
```

---

### Task 3: Baustein-Import 19 → 32 (inkl. .doc-Konvertierung und Platzhalter-Check)

**Files:**
- Modify: `tools/import_textbausteine.py` (MAPPING-Dict Z. 48–69 erweitern)
- Create: `tools/textbausteine/ghpfansprort.doc.rtf` (Konvertat, via Word)
- Test: manueller Dry-Run + Verifikations-Query (Import-Tool hat bewusst keine pytest-Suite; Bestandsmuster)

**Interfaces:**
- Consumes: `kuerzungsarten`-IDs 20–32 aus Migration 64.
- Produces: `kuerzungsarten.textbaustein` befüllt für 28 von 32 Zeilen (leer bleiben: 20/A07 Neu-für-alt [Baustein fehlt], 11/A09 [SV-Stellungnahme statt Baustein], 14/E05c Wunschkennzeichen, 18/D04 Mietwagen, 19/F03 Verdienstausfall — wie bisher bewusst ohne).

- [ ] **Step 1: ghpfansprort.doc → RTF konvertieren (Word-COM, schreibgeschützt öffnen)**

PowerShell:
```powershell
$word = New-Object -ComObject Word.Application; $word.Visible = $false; $word.DisplayAlerts = 0
$doc = $word.Documents.Open("C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten\tools\textbausteine\ghpfansprort.doc", $false, $true, $false)
$out = "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten\tools\textbausteine\ghpfansprort.doc.rtf"
$doc.SaveAs([ref]$out, [ref]6); $doc.Close($false); $word.Quit()
```
Expected: Datei `ghpfansprort.doc.rtf` existiert, > 10 KB. (`ghpfstverort.DOC` NICHT konvertieren — leer, entfällt laut DECISIONS-Nachtrag.)

- [ ] **Step 2: MAPPING erweitern**

In `tools/import_textbausteine.py`, MAPPING-Dict ergänzen (Keys = Dateiname-Stem, lowercase — exakt wie Bestandseinträge):

```python
    "repbest": 21,
    "ghpfzeitpunkt": 22,
    "ghpfansprort.doc": 23,
    "ghpfreprg": 24,
    "wertminderungsteuer": 25,
    "nutzungsausfall für schadentag und sv besichtigung": 26,
    "ghpfjveg": 27,
    "huktableau": 28,
    "ghpvnkpauschal": 29,
    "ghpfabschleppgeb": 30,
    "ghpfup2": 31,
    "hws": 32,
```

WICHTIG: Die IDs 21–32 müssen den tatsächlichen AUTOINCREMENT-IDs aus Migration 64 entsprechen. Vor dem Eintragen gegen die aktive DB verifizieren:
`docker exec unfallakten-backend-dev python -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); [print(r) for r in c.execute('SELECT id, typ_code, bezeichnung FROM kuerzungsarten WHERE id>19 ORDER BY id')]"`
Bei Abweichung: MAPPING an die realen IDs anpassen (Zuordnung über `typ_code` aus der Tabelle in diesem Plan).

- [ ] **Step 2b: Masken-Zeilen beim Import strippen + Platzhalter-Bericht**

In `tools/import_textbausteine.py`, nach der Text-Extraktion und vor dem UPDATE: RA-MICRO-Maskenzeilen entfernen (der Stellungnahme-Pfad strippt sie NICHT — nur der Klage-Pfad via `_bereite_textbaustein_vor`; Beispiel `ghpfansprort` beginnt mit `&&*&&*Maske: HUKKOPIE`):

```python
_MASKE_RE = re.compile(r"^.*&&\*.*$", re.MULTILINE)

def _bereinige(text: str) -> str:
    return _MASKE_RE.sub("", text).strip()
```

`_bereinige(...)` auf jeden extrahierten Text anwenden. Zusätzlich im Dry-Run-Output je Datei die gefundenen `<PLATZHALTER>` gegen die bekannten Keys aus `PLATZHALTER_KATALOG` (Task 4) abgleichen und Unbekannte als `WARNUNG: unbekannter Platzhalter <X>` listen — die landen sonst als `[FEHLT: <X>]` in generierten Schreiben. Unbekannte Platzhalter in den 12 neuen Bausteinen im Task-Ergebnis protokollieren (Entscheidung Umbenennen-oder-Katalog-erweitern fällt in Task 4).

- [ ] **Step 3: Dry-Run gegen die aktive Docker-DB**

Run: `docker exec unfallakten-backend-dev python /app/tools/import_textbausteine.py`
(Der Container hat `/app/tools`; `DB_PATH` ist im Container auf die aktive DB gesetzt — verifizieren mit `docker exec unfallakten-backend-dev printenv DB_PATH`. Falls leer: `docker exec -e DB_PATH=/app/data/unfallakten.db unfallakten-backend-dev python /app/tools/import_textbausteine.py`.)
Expected: Dry-Run listet 12 neue Zuordnungen mit Zeichenzahlen > 500 und gefundene `<PLATZHALTER>`.

- [ ] **Step 4: Import schreiben + verifizieren**

Run: `docker exec -e DB_PATH=/app/data/unfallakten.db unfallakten-backend-dev python /app/tools/import_textbausteine.py --write`
Dann: `docker exec unfallakten-backend-dev python -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); print(c.execute('SELECT COUNT(*) FROM kuerzungsarten WHERE textbaustein IS NOT NULL AND length(textbaustein)>100').fetchone())"`
Expected: `(28,)`.

- [ ] **Step 5: Commit**

```bash
git add tools/import_textbausteine.py "tools/textbausteine/ghpfansprort.doc.rtf"
git commit -m "feat(kuerzungstaxonomie): Baustein-Import auf 32 Typen erweitert (12 neue Zuordnungen, ghpfansprort konvertiert)"
```

---

### Task 4: `textbaustein` REST-fähig machen + Platzhalter-Katalog + Vorschau-Endpoint

Hintergrund (Befund 2026-07-23): Die Spalte `kuerzungsarten.textbaustein` existiert seit Migration 22, wird aber vom Model weggefiltert — `KuerzungskatalogView` speichert ins Leere, `EinwaendeAuswahl` sieht `textbaustein` nie. Ohne diesen Fix ist jede Editor-UI folgenlos.

**Files:**
- Modify: `backend/models/kuerzungsart.py` (Dataclass Z. 30–41, `as_dict()` Z. 54–67, `erlaubt`-Sets in `erstelle_kuerzungsart` Z. 99–102 und `aktualisiere_kuerzungsart` Z. 122–126)
- Modify: `backend/routers/kuerzungsarten_routes.py` (2 neue Endpoints)
- Test: `backend/tests/test_kuerzungsarten_textbaustein_rest.py`

**Interfaces:**
- Consumes: `ersetze_platzhalter(text, kontext)` aus `backend/word/stellungnahme_service.py` (Z. 67); Platzhalter-Keys aus `_baue_kontext` (Z. 105–121).
- Produces: `GET/POST/PUT /kuerzungsarten` führen `textbaustein`, `typ_code`, `verifiziert_am` (typ_code/verifiziert_am nur lesend — Whitelists NICHT erweitern, append-only-Schutz); `GET /kuerzungsarten/platzhalter` → `[{key, beschreibung, beispiel}]`; `POST /kuerzungsarten/vorschau` Body `{"text": "..."}` → `{"vorschau": "..."}` (Beispiel-Kontext serverseitig).

- [ ] **Step 1: Failing Test schreiben**

Nach dem `_RouteBasis`-Muster aus `test_bugfix_p1_intake_v7.py` (temp-DB, `erstelle_app({"TESTING": True})`, `test_client()`, `_login()`):

```python
class TestTextbausteinRest(_RouteBasis):
    def test_put_und_get_textbaustein_roundtrip(self):
        r = self.client.put(
            "/kuerzungsarten/1",
            json={"textbaustein": "Die Kürzung der <GUTACHTER>-Sätze ist unbegründet."},
            headers=self._auth())
        self.assertEqual(r.status_code, 200)
        liste = self.client.get("/kuerzungsarten", headers=self._auth()).get_json()
        eintrag = next(k for k in liste if k["id"] == 1)
        self.assertIn("GUTACHTER", eintrag["textbaustein"])
        self.assertEqual(eintrag["typ_code"], "A04")

    def test_typ_code_nicht_schreibbar(self):
        self.client.put("/kuerzungsarten/1", json={"typ_code": "Z99"},
                        headers=self._auth())
        liste = self.client.get("/kuerzungsarten", headers=self._auth()).get_json()
        eintrag = next(k for k in liste if k["id"] == 1)
        self.assertEqual(eintrag["typ_code"], "A04")

    def test_platzhalter_katalog(self):
        r = self.client.get("/kuerzungsarten/platzhalter", headers=self._auth())
        keys = {p["key"] for p in r.get_json()}
        self.assertTrue({"MANDANT", "GUTACHTER", "VERSICHERER", "AZ"} <= keys)
        for p in r.get_json():
            self.assertTrue(p["beschreibung"])
            self.assertTrue(p["beispiel"])

    def test_vorschau_ersetzt_und_markiert_fehlende(self):
        r = self.client.post(
            "/kuerzungsarten/vorschau",
            json={"text": "Sehr geehrte Damen, <MANDANT> und <UNBEKANNT>."},
            headers=self._auth())
        v = r.get_json()["vorschau"]
        self.assertNotIn("<MANDANT>", v)
        self.assertIn("[FEHLT: <UNBEKANNT>]", v)
```

Run: `python -m pytest backend/tests/test_kuerzungsarten_textbaustein_rest.py -v` → FAIL.

- [ ] **Step 2: Model erweitern**

In `backend/models/kuerzungsart.py`: `textbaustein: Optional[str] = None`, `typ_code: Optional[str] = None`, `verifiziert_am: Optional[str] = None` in die Dataclass; alle drei in `as_dict()`; NUR `"textbaustein"` zusätzlich in beide `erlaubt`-Sets.

- [ ] **Step 3: Endpoints ergänzen**

In `backend/routers/kuerzungsarten_routes.py` (vor den `<int:kid>`-Routen registrieren, damit Flask `platzhalter` nicht als kid parst):

```python
PLATZHALTER_KATALOG = [
    {"key": "MANDANT", "beschreibung": "Name der Mandantschaft", "beispiel": "Herr Max Beispiel"},
    {"key": "AZ", "beschreibung": "Aktenzeichen der Kanzlei", "beispiel": "971/25"},
    {"key": "VERSICHERER", "beschreibung": "Gegnerische Versicherung", "beispiel": "HUK-COBURG"},
    {"key": "DATUM", "beschreibung": "Heutiges Datum", "beispiel": "23.07.2026"},
    {"key": "KFZ", "beschreibung": "Fahrzeug (Hersteller/Typ/Kennzeichen)", "beispiel": "VW Golf, OF-XY 123"},
    {"key": "RGGDAT", "beschreibung": "Datum des Regulierungsschreibens", "beispiel": "10.07.2026"},
    {"key": "GUTACHTER", "beschreibung": "Name des Sachverständigen", "beispiel": "Dipl.-Ing. Muster"},
    {"key": "FKLASSE", "beschreibung": "Fahrzeug-/Mietwagenklasse", "beispiel": "Gruppe F"},
    {"key": "NUTZUNGSA", "beschreibung": "Nutzungsausfall-Tagessatz", "beispiel": "50,00 €"},
    {"key": "NABETRAG", "beschreibung": "Nutzungsausfall-Gesamtbetrag", "beispiel": "350,00 €"},
    {"key": "REPDAUER", "beschreibung": "Reparaturdauer laut Gutachten", "beispiel": "5 Arbeitstage"},
    {"key": "KOSTENNB", "beschreibung": "Kostennote/Gebührenbetrag", "beispiel": "413,64 €"},
    {"key": "SCHMGELD", "beschreibung": "Schmerzensgeld-Forderung", "beispiel": "1.500,00 €"},
    {"key": "SGVORSCHUSS", "beschreibung": "Schmerzensgeld-Vorschuss", "beispiel": "500,00 €"},
]

_BEISPIEL_KONTEXT = {p["key"]: p["beispiel"] for p in PLATZHALTER_KATALOG}


@kuerzungsarten_bp.route("/kuerzungsarten/platzhalter", methods=["GET"])
@login_erforderlich
def platzhalter_katalog():
    return jsonify(PLATZHALTER_KATALOG)


@kuerzungsarten_bp.route("/kuerzungsarten/vorschau", methods=["POST"])
@login_erforderlich
def textbaustein_vorschau():
    from backend.word.stellungnahme_service import ersetze_platzhalter
    text = (request.get_json(silent=True) or {}).get("text", "")
    return jsonify({"vorschau": ersetze_platzhalter(text, _BEISPIEL_KONTEXT)})
```

(Route-Decorator-Name/Blueprint exakt an den Bestand in der Datei angleichen.)

- [ ] **Step 4: Tests grün sehen, dann Commit**

Run: `python -m pytest backend/tests/test_kuerzungsarten_textbaustein_rest.py -v` → PASS.

```bash
git add backend/models/kuerzungsart.py backend/routers/kuerzungsarten_routes.py backend/tests/test_kuerzungsarten_textbaustein_rest.py
git commit -m "fix(kuerzungsarten): textbaustein REST-faehig (Model-Whitelist) + Platzhalter-Katalog + Vorschau-Endpoint"
```

---

### Task 5: Regel-Matching-Service (Stichworte, Wortgrenzen, Briefkopf-Filter)

**Files:**
- Create: `backend/services/kuerzungstyp_matching.py`
- Test: `backend/tests/test_kuerzungstyp_matching.py`

**Interfaces:**
- Consumes: `lade_kuerzungstypen()` aus Task 2.
- Produces:
  ```python
  @dataclass
  class TypVorschlag:
      typ_code: str
      kuerzungsart_id: Optional[int]   # via DB-Lookup typ_code -> id
      snippet: str                     # ±120 Zeichen um den Treffer (= begruendung_roh-Vorschlag)
      quelle: str                      # 'regel' | 'llm'
      konfidenz: float

  def schlage_typen_vor(text: str, *, dokumentklasse: str,
                        llm_fallback: bool = True) -> List[TypVorschlag]
  ```
  Verhalten: liefert NUR auf Begründungsdokumenten (`dokumentklasse in ('pruefbericht', 'abrechnungsschreiben')`) Vorschläge; auf allen anderen Klassen leere Liste (DECISIONS: Matching liefert nur den Typ, Kürzungs-ERKENNUNG bleibt Betragsdifferenz).

- [ ] **Step 1: Failing Tests schreiben — die Phase-0-Fehlerfälle als Fixtures**

```python
import unittest


class TestRegelMatching(unittest.TestCase):
    def _vorschlaege(self, text, klasse="pruefbericht"):
        from backend.services.kuerzungstyp_matching import schlage_typen_vor
        return schlage_typen_vor(text, dokumentklasse=klasse, llm_fallback=False)

    def test_wortgrenze_kleinteilepauschale_ist_A06_nicht_E06(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kleinteilekostenpauschale in Höhe von 30,00 € wurde gekürzt.")}
        self.assertIn("A06", codes)
        self.assertNotIn("E06", codes)

    def test_kostenpauschale_allein_ist_E06(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kostenpauschale erstatten wir mit 25,00 €.",
            klasse="abrechnungsschreiben")}
        self.assertIn("E06", codes)

    def test_kennzeichen_im_briefkopf_matcht_nicht(self):
        text = "Amtl. Kennzeichen: OF-AB 123\nSchaden-Nr. 4711\n" + "x" * 200
        self.assertEqual(self._vorschlaege(text), [])

    def test_kennzeichen_mit_schilder_kontext_matcht(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Die Kosten für die Erneuerung der Kennzeichen (Schilderkosten) "
            "kürzen wir auf 20,00 €.")}
        self.assertIn("E05b", codes)

    def test_neu_fuer_alt(self):
        codes = {v.typ_code for v in self._vorschlaege(
            "Wir nehmen einen Abzug neu für alt in Höhe von 200,00 € vor.")}
        self.assertIn("A07", codes)

    def test_snippet_liefert_begruendung_roh(self):
        v = self._vorschlaege("Vorlauf. " * 30 +
                              "Die Verbringungskosten sind nicht erforderlich. " +
                              "Nachlauf. " * 30)
        treffer = next(x for x in v if x.typ_code == "A02")
        self.assertIn("Verbringungskosten", treffer.snippet)
        self.assertLessEqual(len(treffer.snippet), 260)

    def test_zahlmitteilung_ohne_begruendung_liefert_nichts(self):
        self.assertEqual(
            self._vorschlaege("Verbringungskosten 50,00 €", klasse="gutachten"), [])

    def test_dedup_pro_typ(self):
        v = self._vorschlaege("Verbringung hier. Verbringungskosten dort.")
        self.assertEqual(len([x for x in v if x.typ_code == "A02"]), 1)
```

Run: `python -m pytest backend/tests/test_kuerzungstyp_matching.py -v` → FAIL.

- [ ] **Step 2: Implementieren**

```python
import re
from dataclasses import dataclass
from typing import List, Optional

from backend.services.kuerzungstyp_registry import lade_kuerzungstypen

BEGRUENDUNGS_KLASSEN = ("pruefbericht", "abrechnungsschreiben")
_SNIPPET_RADIUS = 120
_BRIEFKOPF_ZEICHEN = 600


@dataclass
class TypVorschlag:
    typ_code: str
    kuerzungsart_id: Optional[int]
    snippet: str
    quelle: str
    konfidenz: float


def _wort_regex(keyword: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(keyword) +
                      r"(?![A-Za-zÄÖÜäöüß])", re.IGNORECASE)


def _kuerzungsart_id_map():
    from backend.db.database import get_connection
    with get_connection() as conn:
        return {r["typ_code"]: r["id"] for r in conn.execute(
            "SELECT typ_code, id FROM kuerzungsarten WHERE typ_code IS NOT NULL")}


def schlage_typen_vor(text: str, *, dokumentklasse: str,
                      llm_fallback: bool = True) -> List[TypVorschlag]:
    if dokumentklasse not in BEGRUENDUNGS_KLASSEN or not text:
        return []
    reg = lade_kuerzungstypen()
    id_map = _kuerzungsart_id_map()
    vorschlaege: List[TypVorschlag] = []
    for code, typ in reg.typen.items():
        treffer = _finde_regel_treffer(text, typ)
        if treffer is not None:
            vorschlaege.append(TypVorschlag(
                typ_code=code, kuerzungsart_id=id_map.get(code),
                snippet=treffer, quelle="regel", konfidenz=0.9))
    if not vorschlaege and llm_fallback:
        vorschlaege = _llm_fallback(text, reg, id_map)
    return sorted(vorschlaege, key=lambda v: v.typ_code)


def _finde_regel_treffer(text: str, typ: dict) -> Optional[str]:
    for kw in typ.get("keywords", []):
        for m in _wort_regex(kw).finditer(text):
            if m.start() < _BRIEFKOPF_ZEICHEN and not _hat_kuerzungskontext(text, m):
                continue
            if typ.get("keywords_erfordert"):
                fenster = text[max(0, m.start() - 200):m.end() + 200]
                if not any(_wort_regex(e).search(fenster) or e.lower() in fenster.lower()
                           for e in typ["keywords_erfordert"]):
                    continue
            a = max(0, m.start() - _SNIPPET_RADIUS)
            b = min(len(text), m.end() + _SNIPPET_RADIUS)
            return text[a:b].strip()
    return None


_KUERZUNGS_SIGNALE = re.compile(
    r"kürz|gekürzt|Abzug|nicht erstatt|nicht erforderlich|nicht ersatzfähig|"
    r"beanstand|korrigiert|streichen|erneuerung|nicht an", re.IGNORECASE)


def _hat_kuerzungskontext(text: str, m: re.Match) -> bool:
    fenster = text[max(0, m.start() - 150):m.end() + 150]
    return bool(_KUERZUNGS_SIGNALE.search(fenster))


def _llm_fallback(text, reg, id_map) -> List[TypVorschlag]:
    return []
```

(`_llm_fallback` bleibt in diesem Task ein Stub — Task 6 füllt ihn. `re.finditer` statt `re.search` wegen Briefkopf-Skip: der ERSTE Treffer darf verworfen werden, spätere zählen — Lektion aus `feedback_gutachten_parser_debugging`.)

- [ ] **Step 3: Tests grün sehen, dann Commit**

Run: `python -m pytest backend/tests/test_kuerzungstyp_matching.py -v` → PASS. Achtung: die Tests brauchen die temp-DB mit Migration 64 (Basisklasse aus Task 1 wiederverwenden — `_kuerzungsart_id_map` liest die DB).

```bash
git add backend/services/kuerzungstyp_matching.py backend/tests/test_kuerzungstyp_matching.py
git commit -m "feat(kuerzungstaxonomie): Regel-Matching mit Wortgrenzen, Briefkopf-Filter, Kontext-Pflicht-Keywords"
```

---

### Task 6: LLM-Fallback + Positions-Synonymik je Versicherer-Template

**Files:**
- Modify: `backend/services/kuerzungstyp_matching.py` (`_llm_fallback` implementieren)
- Create: `backend/registry/positions_synonyme.yaml`
- Modify: `backend/services/positionsmodell_registry.py` (`positions_synonyme.yaml` in `_YAML_DATEIEN` aufnehmen + Feld im Dataclass + Validierung gegen `positionsarten`)
- Test: `backend/tests/test_kuerzungstyp_matching.py` (erweitern)

**Interfaces:**
- Consumes: `llm_service.klassifiziere_geschlossen(labels, text) -> (label, konfidenz)` (Z. 484, closed-label, `/no_think`); `llm_service.is_available()`.
- Produces: `positions_synonyme`-Mapping im `PositionsmodellRegistry`-Dataclass: `Dict[str, str]` Synonym-Label (lowercase, normalisiert) → `position_key`; Hilfsfunktion `normalisiere_positionslabel(label: str) -> Optional[str]` in `kuerzungstyp_matching.py`.

- [ ] **Step 1: Failing Tests**

```python
class TestLlmFallback(unittest.TestCase):
    def test_fallback_nur_wenn_regeln_leer(self):
        from backend.services import kuerzungstyp_matching as m
        aufrufe = []
        def fake_klassifiziere(labels, text):
            aufrufe.append(labels)
            return ("A02", 0.8)
        with unittest.mock.patch.object(
                m, "_klassifiziere_via_llm", side_effect=fake_klassifiziere):
            v = m.schlage_typen_vor(
                "Die Position wird nicht anerkannt, unklarer Grund.",
                dokumentklasse="pruefbericht", llm_fallback=True)
        self.assertEqual([x.typ_code for x in v], ["A02"])
        self.assertEqual(v[0].quelle, "llm")
        self.assertEqual(len(aufrufe), 1)


class TestPositionsSynonymik(unittest.TestCase):
    def test_versicherer_synonyme(self):
        from backend.services.kuerzungstyp_matching import normalisiere_positionslabel
        self.assertEqual(normalisiere_positionslabel("Differenzbetrag"), "fahrzeugschaden")
        self.assertEqual(normalisiere_positionslabel("Kostenpauschale"), "kostenpauschale")
        self.assertEqual(normalisiere_positionslabel("Sachverständigenkosten"), "sv_kosten")
        self.assertIsNone(normalisiere_positionslabel("Völlig Unbekanntes"))
```

- [ ] **Step 2: `positions_synonyme.yaml` anlegen**

Startbestand aus den Phase-0-Stichproben (S11–S14, S23, HDI/LVM/HUK-Templates); Werte MÜSSEN in `positionsarten.yaml` existieren (Validierung analog `_validiere_rechnungstyp_mapping`):

```yaml
# Synonym (normalisiert, lowercase) -> position_key
"differenzbetrag": fahrzeugschaden
"fahrzeugschaden": fahrzeugschaden
"reparaturkosten gemäß prüfbericht": reparaturkosten
"kostenpauschale": kostenpauschale
"unkostenpauschale": kostenpauschale
"auslagenpauschale": kostenpauschale
"sachverständigenkosten": sv_kosten
"sachverständigenhonorar": sv_kosten
"sv-kosten": sv_kosten
"gutachterkosten": sv_kosten
"rechtsanwaltsgebühren": ra_gebuehren
"rechtsverfolgungskosten": ra_gebuehren
"wertminderung": wertminderung
"merkantile wertminderung": wertminderung
"nutzungsausfall": nutzungsausfall
"nutzungsausfallentschädigung": nutzungsausfall
"abschleppkosten": abschleppkosten
"mietwagenkosten": mietwagen
```

(Keys, die es in `positionsarten.yaml` nicht gibt — z. B. `abschleppkosten`, `mietwagen` — vor dem Anlegen gegen die Registry prüfen und ggf. auf die real existierenden `position_key`s mappen; der Validierungs-Test deckt das auf.)

- [ ] **Step 3: Implementieren**

`_llm_fallback` in `kuerzungstyp_matching.py`:

```python
def _klassifiziere_via_llm(labels, text):
    from backend.services import llm_service
    if not llm_service.is_available():
        return (None, 0.0)
    return llm_service.klassifiziere_geschlossen(labels, text)


def _llm_fallback(text, reg, id_map) -> List[TypVorschlag]:
    labels = [f"{c}: {t['name']} — {t.get('llm_hinweis', '')}"
              for c, t in sorted(reg.typen.items())] + ["KEINE: keine Kürzungsbegründung"]
    label, konf = _klassifiziere_via_llm(labels, text[:4000])
    if not label or label.startswith("KEINE"):
        return []
    code = label.split(":", 1)[0].strip()
    if code not in reg.typen:
        return []
    return [TypVorschlag(typ_code=code, kuerzungsart_id=id_map.get(code),
                         snippet=text[:240].strip(), quelle="llm",
                         konfidenz=min(konf, 0.7))]
```

`normalisiere_positionslabel`:

```python
def normalisiere_positionslabel(label: str) -> Optional[str]:
    from backend.services.positionsmodell_registry import lade_positionsmodell
    reg = lade_positionsmodell()
    norm = " ".join(label.strip().lower().split())
    return reg.positions_synonyme.get(norm)
```

- [ ] **Step 4: Tests grün sehen, dann Commit**

```bash
git add backend/services/kuerzungstyp_matching.py backend/registry/positions_synonyme.yaml backend/services/positionsmodell_registry.py backend/tests/test_kuerzungstyp_matching.py
git commit -m "feat(kuerzungstaxonomie): LLM-Fallback (closed-label) + Positions-Synonymik je Versicherer-Template"
```

---

### Task 7: Dokument-Verkettung Abrechnungsschreiben ↔ Prüfbericht

Hintergrund (Stichprobe 25): Das Abrechnungsschreiben zahlt („Nicht zu erstatten −7.734,55 €" unbegründet), der Prüfbericht begründet. Der FK `pruefberichte.abrechnungsschreiben_id` existiert seit Migration 3, wird aber nirgends automatisch befüllt. Zusätzlich verwirft der Dispatcher-Wrapper heute die Einzelabzüge (`abzuege_detail`).

**Files:**
- Modify: `backend/workflow/dispatcher.py` (`_parse_pruefbericht` Z. 595–622: `abzuege_detail` in den Rückgabe-Dict aufnehmen — Feld `kuerzungen` als Liste `{kategorie, bezeichnung, betrag}`)
- Modify: `backend/routers/pruefberichte_routes.py` (Kandidaten-Endpoint + PATCH Verkettung; beim POST Auto-Verkettung versuchen)
- Create: Service-Funktion `finde_abrechnungs_kandidaten` in `backend/services/kuerzungstyp_matching.py` (kein neues Modul nötig)
- Test: `backend/tests/test_pruefbericht_verkettung.py`

**Interfaces:**
- Produces:
  ```python
  def finde_abrechnungs_kandidaten(akte_az: str, *, datum: str,
                                   schadennummer: str = "") -> List[Dict]
  # Rückgabe absteigend nach Score: [{abrechnungsschreiben_id, datum, versicherung,
  #   gesamt_reguliert, score, grund}]
  ```
  Scoring: gleiche Akte ist Pflicht; +2 wenn `referenz_nr` die Schadennummer enthält (normalisiert, nur Ziffern); +1 wenn |Datumsdifferenz| ≤ 30 Tage; eindeutig = Score-Bestwert einzeln. Bei Eindeutigkeit setzt der POST-/Import-Pfad `abrechnungsschreiben_id` automatisch; sonst bleibt NULL und die UI bietet die Kandidaten an.
- API: `GET /akten/<akte_az>/pruefberichte/<int:pid>/abrechnungs-kandidaten` → Liste wie oben; `PATCH /akten/<akte_az>/pruefberichte/<int:pid>` Body `{"abrechnungsschreiben_id": 5}` (auch `null` zum Lösen).

- [ ] **Step 1: Failing Tests schreiben** — temp-DB-Basis aus Task 1; Fixtures: 1 Akte, 2 Abrechnungsschreiben (Datum ±10/±90 Tage, eines mit `referenz_nr` = Schadennummer), 1 Prüfbericht.

```python
class TestVerkettung(_DBBasis):
    def test_eindeutiger_kandidat_ueber_schadennummer(self):
        from backend.services.kuerzungstyp_matching import finde_abrechnungs_kandidaten
        k = finde_abrechnungs_kandidaten("971/25", datum="2026-07-01",
                                         schadennummer="30.278.811.1")
        self.assertEqual(k[0]["abrechnungsschreiben_id"], self.ab1_id)
        self.assertGreater(k[0]["score"], k[1]["score"])

    def test_datumsnaehe_zaehlt(self):
        from backend.services.kuerzungstyp_matching import finde_abrechnungs_kandidaten
        k = finde_abrechnungs_kandidaten("971/25", datum="2026-07-01")
        self.assertEqual(k[0]["abrechnungsschreiben_id"], self.ab1_id)

    def test_patch_verkettung(self):
        r = self.client.patch(
            f"/akten/971/25/pruefberichte/{self.pb_id}",
            json={"abrechnungsschreiben_id": self.ab1_id}, headers=self._auth())
        self.assertEqual(r.status_code, 200)
```

(Der PATCH-Test läuft in der `_RouteBasis`-Variante; URL-Format mit `/` im AZ exakt an die bestehenden `pruefberichte_routes`-URLs angleichen — dort nachsehen, wie `akte_id` kodiert wird.)

- [ ] **Step 2: Dispatcher-Fix** — in `_parse_pruefbericht` den Rückgabe-Dict ergänzen:

```python
        "kuerzungen": [
            {"kategorie": a.kategorie, "bezeichnung": a.bezeichnung, "betrag": a.betrag}
            for a in (result.abzuege_detail or [])
        ],
```

und in `abrechnungsschreiben_routes.py` (Z. 528–545, wo `kuerzungen_json` befüllt wird) sicherstellen, dass diese Liste ankommt.

- [ ] **Step 3: Service + Endpoints implementieren**

```python
def finde_abrechnungs_kandidaten(akte_az, *, datum, schadennummer=""):
    from backend.db.database import get_connection
    nur_ziffern = re.sub(r"\D", "", schadennummer or "")
    kandidaten = []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT a.id, a.datum, a.versicherung, a.referenz_nr, a.gesamt_reguliert "
            "FROM abrechnungsschreiben a JOIN unfallakte u ON a.akte_id = u.id "
            "WHERE u.az = ? ORDER BY a.datum DESC", (akte_az,)).fetchall()
    for r in rows:
        score, gruende = 0, []
        ref_ziffern = re.sub(r"\D", "", r["referenz_nr"] or "")
        if nur_ziffern and nur_ziffern in ref_ziffern:
            score += 2
            gruende.append("Schadennummer")
        try:
            tage = abs((date.fromisoformat(datum) -
                        date.fromisoformat(r["datum"])).days)
            if tage <= 30:
                score += 1
                gruende.append(f"{tage} Tage Abstand")
        except (ValueError, TypeError):
            pass
        kandidaten.append({"abrechnungsschreiben_id": r["id"], "datum": r["datum"],
                           "versicherung": r["versicherung"],
                           "gesamt_reguliert": r["gesamt_reguliert"],
                           "score": score, "grund": ", ".join(gruende)})
    return sorted(kandidaten, key=lambda k: -k["score"])
```

Auto-Verkettung im POST-/Import-Pfad der `pruefberichte_routes.py`: Kandidaten holen; wenn genau EINER den Bestwert > 0 hat → `abrechnungsschreiben_id` setzen, sonst NULL lassen.

- [ ] **Step 3b: `pruefdienstleister_id` befüllen**

Beim Speichern eines Prüfberichts (POST in `pruefberichte_routes.py` und `erstelle_pruefbericht`-Pfad aus `abrechnungsschreiben_routes.py`): den vom Parser erkannten String (`pruefdienstleister`, z. B. „ControlExpert") gegen die Stammtabelle auflösen und die FK-Spalte mitschreiben; unbekannte Namen legen KEINE neue Zeile an (Stammtabelle wird bewusst manuell gepflegt), FK bleibt dann NULL:

```python
def _pruefdienstleister_id(conn, name):
    if not name or name == "Unbekannt":
        return None
    row = conn.execute(
        "SELECT id FROM pruefdienstleister WHERE name = ? AND aktiv = 1",
        (name,)).fetchone()
    return row["id"] if row else None
```

Gleiches Mapping auf `abrechnungsschreiben.pruefdienstleister_id`, wenn der verkettete Prüfbericht einen Dienstleister trägt (Konzept 2.3: Achse Dienstleister × Typ).

- [ ] **Step 4: Frontend-Anbindung (klein):** In `RegulierungSection.jsx`, Prüfbericht-Anzeige: wenn `abrechnungsschreiben_id` NULL, Hinweis-Zeile „Nicht verkettet" + Auswahl-Dropdown aus dem Kandidaten-Endpoint, Speichern via neuem `api.js`-Client `pruefberichte.verkette(akteId, pid, abId)`.

- [ ] **Step 5: Tests grün sehen, dann Commit**

```bash
git add backend/workflow/dispatcher.py backend/routers/pruefberichte_routes.py backend/services/kuerzungstyp_matching.py backend/tests/test_pruefbericht_verkettung.py frontend/src/sections/RegulierungSection.jsx frontend/src/api.js
git commit -m "feat(kuerzungstaxonomie): Pruefbericht-Abrechnungs-Verkettung (Auto-Kandidat + PATCH) + abzuege_detail durchgereicht"
```

---

### Task 8: Typ-Zuordnung im Regulierungs-UI — Vorschlag, Pflicht-Begründung, Ereignis-Durchreichung

Kern des RA-Schatz-Workflows: Beim Erfassen/Prüfen einer Abrechnung schlägt das System je Kürzungsposition den Typ vor (aus dem VERKETTETEN Begründungsdokument), der Bearbeiter bestätigt; jede Kürzung führt Betrag (existiert: Differenz) und `begruendung_roh` als Pflicht.

**Files:**
- Modify: `backend/routers/abrechnungsschreiben_routes.py` (neuer Endpoint Typ-Vorschläge; Pflichtfeld-Validierung im Positions-PATCH; `typ_quelle` schreiben)
- Modify: `backend/services/eingehende_ereignisse.py` (`_regulierungs_wirkungen`: `begruendung_roh` aus `kuerzung_freitext` in die Positions-Dicts)
- Modify: `backend/services/ereignis_service.py` (INSERT um `begruendung_roh` erweitern — NUR Ebene 1 `ereignis_positionen`, Cache unverändert)
- Modify: `frontend/src/sections/RegulierungSection.jsx` (`PositionenTabelle`: Vorschlags-Chip + Begründungsfeld + Pflicht-Validierung)
- Modify: `frontend/src/api.js`
- Test: `backend/tests/test_kuerzungstyp_matching.py` (Routen-Teil), `frontend/src/sections/RegulierungSection.typvorschlag.test.jsx`

**Interfaces:**
- API: `GET /akten/<akteId>/abrechnungen/<abId>/typ-vorschlaege` → `{"vorschlaege": [TypVorschlag-Dicts], "quelle_dokument_id": <id|null>}`. Implementierung: verketteten Prüfbericht suchen (`pruefberichte.abrechnungsschreiben_id = abId`); dessen PDF-Volltext via `extract_text_from_pdf(dateipfad)` + `normalize_text` ziehen (kein persistierter Volltext vorhanden!); sonst Volltext des Abrechnungs-PDFs; darauf `schlage_typen_vor(...)`.
- Positions-PATCH (`updatePos`): Wenn `kuerzungsart_id` gesetzt WIRD (Wert im Payload, nicht NULL), verlangt der Server zusätzlich nicht-leeres `kuerzung_freitext` im Payload ODER bereits in der Zeile → sonst 400 `{"fehler": "Begründung (Wortlaut des Versicherers) ist Pflicht"}`. `typ_quelle` wird mitgeschrieben (`'regel'`/`'llm'`/`'manuell'`; Frontend sendet die Quelle des übernommenen Vorschlags, Default `'manuell'`).
- `_regulierungs_wirkungen`: jede erzeugte `gekuerzt`/`abgelehnt`-Zeile bekommt `"begruendung_roh": p.get("kuerzung_freitext")`; `schreibe_ereignis` schreibt das Feld in `ereignis_positionen`.

- [ ] **Step 1: Failing Backend-Tests** (Pflicht-Validierung + Ereignis-Durchreichung):

```python
    def test_patch_kuerzungsart_ohne_begruendung_400(self):
        r = self.client.patch(self._pos_url(), json={"kuerzungsart_id": 4},
                              headers=self._auth())
        self.assertEqual(r.status_code, 400)

    def test_patch_mit_begruendung_ok_und_typ_quelle(self):
        r = self.client.patch(self._pos_url(), json={
            "kuerzungsart_id": 4,
            "kuerzung_freitext": "Verbringungskosten fallen regional nicht an.",
            "typ_quelle": "regel"}, headers=self._auth())
        self.assertEqual(r.status_code, 200)

    def test_ereignis_traegt_begruendung_roh(self):
        from backend.services.eingehende_ereignisse import _regulierungs_wirkungen
        zeilen = _regulierungs_wirkungen([{
            "position_key": "wertminderung", "betrag_gefordert": 100.0,
            "betrag_reguliert": 40.0, "kuerzungsart_id": 2,
            "kuerzung_freitext": "Fällt regional nicht an."}])
        gekuerzt = next(z for z in zeilen if z["wirkung"] == "gekuerzt")
        self.assertEqual(gekuerzt["begruendung_roh"], "Fällt regional nicht an.")
        self.assertEqual(gekuerzt["betrag"], 60.0)
```

- [ ] **Step 2: Backend implementieren.** In `ereignis_service.schreibe_ereignis` das Positions-INSERT (Z. 131–137) erweitern:

```python
                conn.execute(
                    "INSERT INTO ereignis_positionen "
                    "(ereignis_id, position_key, wirkung, betrag, kuerzungsart_id, "
                    " begruendung_roh) VALUES (?, ?, ?, ?, ?, ?)",
                    (eid, p["position_key"], p["wirkung"], p.get("betrag"),
                     p.get("kuerzungsart_id"), p.get("begruendung_roh")),
                )
```

`rebuild_cache` NICHT anfassen (Cache führt kein `begruendung_roh`). In `_regulierungs_wirkungen` bei den `gekuerzt`- und `abgelehnt`-Zweigen `"begruendung_roh": p.get("kuerzung_freitext")` ergänzen. Pflicht-Validierung + `typ_quelle` im Positions-PATCH der `abrechnungsschreiben_routes.py`. Neuer Vorschlags-Endpoint wie oben.

- [ ] **Step 3: Frontend.** `PositionenTabelle` (Z. 19–134): Über der Tabelle einmalig Vorschläge laden (`apiAbrechnungen.typVorschlaege(akteId, abid)`); je Position mit Kürzungsbetrag > 0 und ohne `kuerzungsart_id` einen Chip „Vorschlag: <bezeichnung> (<typ_code>)" rendern; Klick übernimmt `kuerzungsart_id` + `kuerzung_freitext` (Snippet, editierbar in einem kleinen Textarea unter der Zeile) + `typ_quelle` in EINEM `updatePos`-Call. Speichern einer manuell gewählten Kürzungsart ohne Begründungstext: Feld rot markieren, Request erst absenden, wenn Text vorhanden (Server-400 zusätzlich abfangen und als Toast zeigen).

- [ ] **Step 4: Vitest** (`RegulierungSection.typvorschlag.test.jsx`, Muster `KlageWizard.einwaende.test.jsx`): Chip erscheint bei Vorschlag; Klick ruft `updatePos` mit `kuerzungsart_id` + `kuerzung_freitext` + `typ_quelle`; ohne Begründung kein Request.

- [ ] **Step 5: Tests grün sehen (pytest + `npx vitest run`), dann Commit**

```bash
git add backend/routers/abrechnungsschreiben_routes.py backend/services/eingehende_ereignisse.py backend/services/ereignis_service.py backend/tests frontend/src/sections/RegulierungSection.jsx frontend/src/sections/RegulierungSection.typvorschlag.test.jsx frontend/src/api.js
git commit -m "feat(kuerzungstaxonomie): Typ-Vorschlag im Regulierungs-UI, begruendung_roh Pflicht, Ereignis-Durchreichung"
```

---

### Task 9: Runde-1↔Runde-2-Vergleich auf dem Ereignisstrom

Zweite, eigene Lese-Faltung (DECISIONS: strikt getrennt von der Positions-Faltung; liest, schreibt nie). Nachzahlung = Rückgang des `gekuerzt`-Betrags je `position_key × kuerzungsart_id` zwischen aufeinanderfolgenden Abrechnungsrunden (Stichprobe 20: Kostenpauschale 25 € → +5 € = 30 €).

**Files:**
- Create: `backend/services/abrechnungsrunden_service.py`
- Modify: `backend/routers/abrechnungsschreiben_routes.py` (GET-Endpoint)
- Modify: `frontend/src/sections/RegulierungSection.jsx` (Runden-Kachel), `frontend/src/api.js`
- Test: `backend/tests/test_abrechnungsrunden.py`

**Interfaces:**
- Produces:
  ```python
  def leite_runden_ab(akte_az: str) -> Dict[str, Any]
  # {
  #   "runden": [{"ereignis_id", "datum", "dokument_id",
  #               "gekuerzt_gesamt", "positionen": {pk: {"gekuerzt": x,
  #                    "typen": {kuerzungsart_id: betrag}}}}],
  #   "vergleich": [{"position_key", "kuerzungsart_id", "typ_code",
  #                  "runde_alt": 1, "runde_neu": 2,
  #                  "betrag_alt": 25.0, "betrag_neu": 0.0, "delta": -25.0,
  #                  "status": "nachzahlung" | "aufrechterhalten" | "neu" | "erhoeht"}]
  # }
  ```
  Datenquelle: `ereignisse` mit `ereignistyp='abrechnung_eingegangen' AND ersetzt_durch IS NULL` je Akte, `ORDER BY datum ASC, id ASC` = Runden 1..n; Positionen aus `ereignis_positionen` (`ersetzt_durch IS NULL`). WICHTIG: `ersetzt_kopf_id`-Ersetzungen (ReguWizard-Edit derselben Abrechnung) sind KEINE neue Runde — sie sind durch den `ersetzt_durch IS NULL`-Filter bereits korrekt kollabiert; eine echte zweite Abrechnung ist ein eigenes, nicht-ersetztes Ereignis (i. d. R. anderes `dokument_id`).
  Vergleichslogik je (position_key, kuerzungsart_id) über benachbarte Runden: Betrag sinkt → `nachzahlung` (delta negativ); gleich → `aufrechterhalten`; taucht neu auf → `neu`; steigt → `erhoeht`. Kürzungen ohne Typ (kuerzungsart_id NULL) werden mit `typ_code: null` geführt, nicht verworfen.
- API: `GET /akten/<akteId>/abrechnungen/runden` → obiges Dict (+ `typ_code` via JOIN `kuerzungsarten`).

- [ ] **Step 1: Failing Tests** — Fixtures über `ereignis_service.schreibe_ereignis` (NICHT per Hand-INSERT):

```python
class TestRundenVergleich(_DBBasis):
    def _runde(self, datum, dok_id, kuerzung_betrag):
        from backend.services.ereignis_service import schreibe_ereignis
        return schreibe_ereignis(
            akte_az="971/25", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum=datum, dokument_id=dok_id,
            positionen=[
                {"position_key": "kostenpauschale", "wirkung": "anerkannt",
                 "betrag": 30.0 - kuerzung_betrag},
                {"position_key": "kostenpauschale", "wirkung": "gekuerzt",
                 "betrag": kuerzung_betrag, "kuerzungsart_id": 15},
            ])

    def test_nachzahlung_erkannt(self):
        self._runde("2026-06-01", 101, 5.0)
        self._runde("2026-07-01", 102, 0.0)
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        erg = leite_runden_ab("971/25")
        self.assertEqual(len(erg["runden"]), 2)
        v = next(x for x in erg["vergleich"]
                 if x["position_key"] == "kostenpauschale")
        self.assertEqual(v["status"], "nachzahlung")
        self.assertEqual(v["delta"], -5.0)

    def test_ersetzung_ist_keine_runde(self):
        e1 = self._runde("2026-06-01", 101, 5.0)
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az="971/25", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2026-06-01", dokument_id=101,
            positionen=[{"position_key": "kostenpauschale",
                         "wirkung": "gekuerzt", "betrag": 5.0,
                         "kuerzungsart_id": 15}],
            ersetzt_kopf_id=e1)
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        self.assertEqual(len(leite_runden_ab("971/25")["runden"]), 1)

    def test_aufrechterhalten_und_neu(self):
        self._runde("2026-06-01", 101, 5.0)
        from backend.services.ereignis_service import schreibe_ereignis
        schreibe_ereignis(
            akte_az="971/25", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2026-07-01", dokument_id=102,
            positionen=[
                {"position_key": "kostenpauschale", "wirkung": "gekuerzt",
                 "betrag": 5.0, "kuerzungsart_id": 15},
                {"position_key": "wertminderung", "wirkung": "gekuerzt",
                 "betrag": 800.0, "kuerzungsart_id": 2},
            ])
        from backend.services.abrechnungsrunden_service import leite_runden_ab
        stati = {(v["position_key"], v["status"])
                 for v in leite_runden_ab("971/25")["vergleich"]}
        self.assertIn(("kostenpauschale", "aufrechterhalten"), stati)
        self.assertIn(("wertminderung", "neu"), stati)
```

(Doppelerfassungs-Guard beachten: gleiche `(akte_az, dokument_id, ereignistyp)` würde geblockt — deshalb unterschiedliche `dokument_id` je Runde in den Fixtures; der Guard sitzt in `erzeuge_aus_*`, nicht in `schreibe_ereignis` selbst. VOR dem Schreiben der Fixtures prüfen, dass `kostenpauschale` und `wertminderung` in `backend/registry/positionsarten.yaml` existieren — `ereignis_service._validiere` lehnt unbekannte Keys ab; andernfalls in den Fixtures real existierende Keys aus der Registry verwenden.)

- [ ] **Step 2: Service implementieren** (reines SELECT + Python-Faltung, kein Schreibzugriff; Rundung `round(x, 2)` durchgängig; Toleranz 0.005 wie `positionsstatus_service._zustand`).

- [ ] **Step 3: Endpoint + Frontend-Kachel.** Kachel in `RegulierungSection` oberhalb der Abrechnungsliste, nur sichtbar ab 2 Runden: je Vergleichszeile Label + Typ-Badge + Delta mit Farbe (grün = Nachzahlung, grau = aufrechterhalten, rot = neu/erhöht). Zeilen mit Status `aufrechterhalten` sind die Arbeitsliste für die 2.-Runde-Eskalation (E06b-Baustein etc.).

- [ ] **Step 4: Tests grün sehen, dann Commit**

```bash
git add backend/services/abrechnungsrunden_service.py backend/routers/abrechnungsschreiben_routes.py backend/tests/test_abrechnungsrunden.py frontend/src/sections/RegulierungSection.jsx frontend/src/api.js
git commit -m "feat(kuerzungstaxonomie): Runde-1/Runde-2-Vergleich auf dem Ereignisstrom (Nachzahlung/aufrechterhalten/neu)"
```

---

### Task 10: Editor-Komponente `TextbausteinEditor` (V11 erbt sie)

Props-getrieben und frei von Kürzungs-Spezifika, damit V11 (Standardtexte, Spec `2026-07-19-klage-wizard-standardtexte-design.md`) sie unverändert übernehmen kann. Pflicht-Features aus der V11-Spec: Platzhalter-Chips mit Beschreibung+Beispiel (Einfügen an Cursor-Position), Live-Vorschau, Speicher-Prüfung (unbekannter Platzhalter blockiert), optional „Auf Standard zurücksetzen".

**Files:**
- Create: `frontend/src/components/TextbausteinEditor.jsx`
- Create: `frontend/src/components/TextbausteinEditor.test.jsx`
- Modify: `frontend/src/views/KuerzungskatalogView.jsx` (Editor ersetzt das rohe `textbaustein`-Textarea Z. 156–172; A–F-Gruppierung; `typ_code`-Badge; `verifiziert_am`-Anzeige)
- Modify: `frontend/src/api.js` (`kuerzungsarten.platzhalter()`, `kuerzungsarten.vorschau(text)`)

**Interfaces:**
- Consumes: `GET /kuerzungsarten/platzhalter`, `POST /kuerzungsarten/vorschau` (Task 4).
- Produces:
  ```jsx
  <TextbausteinEditor
    wert={string}
    onChange={(neuerText) => void}
    platzhalter={[{key, beschreibung, beispiel}]}
    onVorschau={async (text) => vorschauString}   // Server-Vorschau, debounced 400 ms
    standardText={string | null}                   // optional; aktiviert Reset-Button
    onReset={() => void}                           // optional
    pruefeSpeicherbar={(text) => {ok, unbekannte:[...]}}  // wird intern berechnet, via
                                                          // bekannte Keys aus `platzhalter`
  />
  ```
  Export zusätzlich: `pruefePlatzhalter(text, bekannteKeys) -> {ok: bool, unbekannte: string[]}` (reine Funktion, `<([A-Z_]+)>`-Regex — Gegenstück zu `ersetze_platzhalter`).

- [ ] **Step 1: Failing Vitest schreiben**

```jsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TextbausteinEditor, { pruefePlatzhalter } from "./TextbausteinEditor.jsx";

const PH = [
  { key: "MANDANT", beschreibung: "Name der Mandantschaft", beispiel: "Herr Beispiel" },
  { key: "GUTACHTER", beschreibung: "Sachverständiger", beispiel: "Dipl.-Ing. Muster" },
];

describe("pruefePlatzhalter", () => {
  it("erkennt unbekannte Platzhalter", () => {
    const r = pruefePlatzhalter("Hallo <MANDANT> und <TIPPFEHLER>", ["MANDANT"]);
    expect(r.ok).toBe(false);
    expect(r.unbekannte).toEqual(["TIPPFEHLER"]);
  });
  it("ok ohne Platzhalter", () => {
    expect(pruefePlatzhalter("Nur Text", []).ok).toBe(true);
  });
});

describe("TextbausteinEditor", () => {
  it("Chip-Klick fügt Platzhalter an Cursor ein", () => {
    const onChange = vi.fn();
    render(<TextbausteinEditor wert="Sehr geehrte," onChange={onChange}
                               platzhalter={PH} />);
    fireEvent.click(screen.getByRole("button", { name: /MANDANT/ }));
    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][0]).toContain("<MANDANT>");
  });
  it("zeigt Warnung bei unbekanntem Platzhalter", () => {
    render(<TextbausteinEditor wert="Text mit <FALSCH>" onChange={() => {}}
                               platzhalter={PH} />);
    expect(screen.getByText(/FALSCH/)).toBeTruthy();
  });
  it("Reset-Button nur mit standardText", () => {
    const { rerender } = render(
      <TextbausteinEditor wert="x" onChange={() => {}} platzhalter={PH} />);
    expect(screen.queryByText(/Auf Standard/)).toBeNull();
    rerender(<TextbausteinEditor wert="x" onChange={() => {}} platzhalter={PH}
                                 standardText="Std" onReset={() => {}} />);
    expect(screen.getByText(/Auf Standard/)).toBeTruthy();
  });
});
```

Run: `npx vitest run src/components/TextbausteinEditor.test.jsx` → FAIL.

- [ ] **Step 2: Komponente implementieren.** Aufbau: zweispaltig (links Textarea via `ref` für Cursor-Insert; rechts Chips gruppiert + Live-Vorschau-Box). Chip-Insert:

```jsx
const einfuegen = (key) => {
  const ta = taRef.current;
  const pos = ta ? ta.selectionStart : wert.length;
  const neu = wert.slice(0, pos) + `<${key}>` + wert.slice(pos);
  onChange(neu);
};
```

Vorschau: `useEffect` mit 400-ms-Debounce auf `wert`, ruft `onVorschau` (wenn Prop fehlt: lokale Ersetzung mit `beispiel`-Werten aus `platzhalter` — damit Tests ohne Server laufen). Warnbereich unter dem Textarea aus `pruefePlatzhalter(wert, platzhalter.map(p => p.key))`. Styling: Inline-Styles aus `config/theme.js`, Monospace wie `DokumentCard`.

- [ ] **Step 3: In `KuerzungskatalogView` einbauen.** Textarea Z. 156–172 ersetzen; `platzhalter` einmal beim Mount laden; `onVorschau` → `kuerzungsarten.vorschau(text)`; Speichern-Button deaktivieren solange `pruefePlatzhalter(...).ok === false`. Gruppierung der Liste auf `typ_code`-Präfix (A–F, Labels aus einer lokalen Konstante identisch zu `KATEGORIEN_AF`) umstellen; `typ_code` als Badge vor der Bezeichnung; `verifiziert_am` klein unter dem Titel.

- [ ] **Step 4: Tests grün sehen (`npx vitest run`), Browser-Kurztest (Katalog öffnen, Baustein editieren, Chip einfügen, Vorschau prüfen, speichern, neu laden), dann Commit**

```bash
git add frontend/src/components/TextbausteinEditor.jsx frontend/src/components/TextbausteinEditor.test.jsx frontend/src/views/KuerzungskatalogView.jsx frontend/src/api.js
git commit -m "feat(kuerzungstaxonomie): TextbausteinEditor (Chips, Live-Vorschau, Platzhalter-Pruefung) + Katalog auf A-F umgestellt"
```

---

### Task 11: Baustein-Vorauswahl konsistent in Stellungnahme UND Klage

Die Vorauswahl-Mechanik existiert (`kuerzungsart_id` an der Position → `ReguWizard`-Vorschlag bzw. `EinwaendeAuswahl`-Checkbox). Zwei Lücken schließen: (a) Die Stellungnahme-Vorschau nutzt `standard_gegenargument` statt `textbaustein` (Inkonsistenz zum Klage-Pfad und zum Service), (b) `begruendung_roh` soll im generierten Text als Zitat verfügbar sein.

**Files:**
- Modify: `backend/routers/stellungnahme_routes.py` (Vorschau Z. 190–191: Fallback-Kette `gespeicherter Text → textbaustein → standard_gegenargument`, identisch zur Kette in `stellungnahme_service` Z. 147–154)
- Modify: `backend/word/stellungnahme_service.py` (`_aggregiere_kuerzungen`: `begruendung_roh` [= `kuerzung_freitext` der Positionen] je Gruppe mitliefern; neuer Kontext-Platzhalter `<ZITAT>` = Versicherer-Wortlaut)
- Modify: `backend/routers/kuerzungsarten_routes.py` (`<ZITAT>` in `PLATZHALTER_KATALOG` aufnehmen: „Wortlaut der Kürzungsbegründung des Versicherers")
- Test: `backend/tests/test_kuerzungsarten_textbaustein_rest.py` erweitern + bestehende Stellungnahme-Tests laufen lassen

**Interfaces:**
- Consumes: `kuerzung_freitext`/`begruendung_roh` aus Task 8; `textbaustein` via REST aus Task 4.
- Produces: `vorschau`-Payload je Position zusätzlich `begruendung_roh`; `ersetze_platzhalter`-Kontext je Kürzungsgruppe um `ZITAT` erweitert (leer → `[FEHLT: <ZITAT>]` erscheint NICHT, weil `<ZITAT>` nur ersetzt wird, wenn der Baustein ihn nutzt — Semantik von `ersetze_platzhalter` bleibt unverändert; bei leerem Zitat wird `""` eingesetzt).

- [ ] **Step 1: Failing Test schreiben** (in `test_kuerzungsarten_textbaustein_rest.py`, `_RouteBasis`-Muster; Fixture: Akte + Abrechnungsschreiben + Position mit `kuerzungsart_id=2`, `kuerzung_freitext="Wertminderung nicht nachvollziehbar."`, `kuerzungsarten.textbaustein` für id 2 gesetzt, `standard_gegenargument` abweichend):

```python
    def test_vorschau_nutzt_textbaustein_vor_standard_gegenargument(self):
        self._setze_textbaustein(2, "BAUSTEIN-TEXT zur Wertminderung")
        r = self.client.get("/akten/971/25/stellungnahme/vorschau",
                            headers=self._auth())
        pos = next(p for p in r.get_json()["positionen"]
                   if p.get("kuerzungsart_id") == 2)
        self.assertIn("BAUSTEIN-TEXT", pos["textbaustein_vorschlag"])

    def test_vorschau_liefert_begruendung_roh(self):
        r = self.client.get("/akten/971/25/stellungnahme/vorschau",
                            headers=self._auth())
        pos = next(p for p in r.get_json()["positionen"]
                   if p.get("kuerzungsart_id") == 2)
        self.assertEqual(pos["begruendung_roh"],
                         "Wertminderung nicht nachvollziehbar.")
```

(URL-Kodierung des AZ mit `/` exakt an die bestehenden Stellungnahme-Route-Tests angleichen; gespeicherter Text in `stellungnahme_texte` muss weiterhin Vorrang haben — bestehende Tests decken das.)

- [ ] **Step 2: Implementieren** — in `stellungnahme_routes.py` Vorschau (Z. 190–191) die Kette auf `gespeichert → ka.textbaustein → ka.standard_gegenargument` erweitern (wortgleich zur Kette in `stellungnahme_service` Z. 147–154, inkl. `ersetze_platzhalter`-Aufruf); `_aggregiere_kuerzungen` liefert je Gruppe `begruendung_roh` (Konkatenation der nicht-leeren `kuerzung_freitext` der Gruppenpositionen, `" / "`-getrennt) und der Kontext bekommt `"ZITAT": begruendung_roh or ""`. In `ReguWizard` das gelieferte `begruendung_roh` als kursive read-only Zeile über dem Textarea anzeigen („Versicherer: …").

- [ ] **Step 3: Regressionsläufe:** `python -m pytest backend/tests -k "stellungnahme or klage" -v` und `npx vitest run` (deckt `KlageWizard.einwaende*`-Tests ab — der Klage-Pfad liest `textbaustein` jetzt erstmals wirklich über REST, [FEHLT]-Marker-Tests müssen grün bleiben).

- [ ] **Step 4: Commit**

```bash
git add backend/routers/stellungnahme_routes.py backend/word/stellungnahme_service.py backend/routers/kuerzungsarten_routes.py backend/tests frontend/src/sections/RegulierungSection.jsx
git commit -m "feat(kuerzungstaxonomie): Baustein-Fallback vereinheitlicht, ZITAT-Platzhalter, begruendung_roh in Stellungnahme-Vorschau"
```

---

### Task 12: Messanker, Doku-Nachführung, Abschluss

**Files:**
- Create: `tools/kuerzungsmatching_report.py`
- Modify: `docs/DATAMODEL.md` (Migration 64, `pruefdienstleister`, `begruendung_roh`, `typ_quelle`), `docs/ARCHITECTURE.md` (Kürzungstyp-Registry, Matching-Service, Runden-Faltung), `docs/CHANGELOG.md` (Phase-1-Protokoll), `docs/TODO.md` (Phase-1-Eintrag → erledigt; Phase-2-Backlog-Eintrag), `docs/DECISIONS.md` (nur falls in der Umsetzung neue Entscheidungen fielen — z. B. die 3 „Zur Bestätigung"-Punkte mit Ausgang)

**Interfaces:**
- Produces: `tools/kuerzungsmatching_report.py` — läuft via `docker exec`, liest die aktive DB und druckt die 3 Zielwert-Kennzahlen:

```python
"""
Kennzahlen-Report Kürzungstaxonomie (Zielwerte DECISIONS 2026-07-23:
Abdeckung >= 90 %, Trefferquote >= 75 %, Positionszuordnung >= 90 %).
Aufruf: docker exec unfallakten-backend-dev python /app/tools/kuerzungsmatching_report.py [--seit 2026-07-25]
"""
```

Kennzahlen-Definitionen (SQL über die aktive DB):
1. **Abdeckung:** Anteil der `regulierung_positionen` mit Kürzungsbetrag > 0 (`betrag_gefordert - betrag_reguliert > 0.005`), deren `kuerzungsart_id` auf eine Zeile mit nicht-leerem `textbaustein` zeigt.
2. **Trefferquote Typ-Vorschlag:** Anteil `typ_quelle IN ('regel','llm')` an allen Positionen mit `kuerzungsart_id`, bei denen der Vorschlag NICHT nachträglich geändert wurde (Näherung: `typ_quelle != 'manuell'`); Aufschlüsselung nach `typ_quelle`.
3. **Positions-/Betragszuordnung:** Anteil der `abrechnung_eingegangen`-Ereignisse (seit Stichtag), deren Positionssumme (`ereignis_positionen.betrag` je `anerkannt`) von `betragswirkung_gesamt` bzw. `gesamt_reguliert` um < 1 € abweicht.

- [ ] **Step 1: Report-Tool schreiben + gegen aktive DB laufen lassen** (druckt aktuell naturgemäß niedrige/leere Werte — Baseline dokumentieren).
- [ ] **Step 2: Doku-Dateien nachführen** (CHANGELOG-Protokoll mit Commits; TODO: „Messung nach ~4 Wochen Betrieb" als neuen Eintrag mit Datum ~2026-08-20 anlegen; STATE.md nur falls Deploy-Hinweise nötig — Migration 64 läuft beim nächsten Backend-Start automatisch).
- [ ] **Step 3: Gesamt-Regressionslauf:** `python -m pytest backend/tests -v` (voll) und `npx vitest run` (voll). Expected: alles grün.
- [ ] **Step 4: Commit**

```bash
git add tools/kuerzungsmatching_report.py docs/DATAMODEL.md docs/ARCHITECTURE.md docs/CHANGELOG.md docs/TODO.md docs/DECISIONS.md
git commit -m "docs(kuerzungstaxonomie): Phase 1 abgeschlossen - Messanker-Tool, Doku nachgefuehrt"
```

---

## Bewusst NICHT in Phase 1 (Abgrenzung)

- **Trigger-Umkehr Stellungnahme** (Queue liefert fertigen Entwurf statt manuellem Wizard-Aufruf) → Phase 2 (TODO-Eintrag PRD-39).
- **Vorgangsautomat** (zweite Faltung „wo steht der Prozess", Timer als Events) → Phase 2/3 (Konzept Abschnitt 3/7).
- **Zahlungs-Kaskade** (Betrags-Matching → Anfrage → Not-Zuordnung, DECISIONS 2026-07-23) → Phase 2; Phase 1 legt mit Pflicht-Betrag je Kürzung nur die Datenbasis.
- **Rechtsprechungstabelle + urteil-verifikation** → entfällt für Bestand (DECISIONS), Regel für Neuzugänge erst beim ersten Neuzugang.
- **OCR-Pfad für die 5 Image-PDFs** → existiert (PRD-30), keine Phase-1-Arbeit.
- **V11 Standardtexte** → erbt `TextbausteinEditor` nach Phase 1 (eigene Spec bleibt gültig).
- **Auswertungs-Views** (Kürzungsquote je Versicherer × Typ, Konzept 2.7) → „kommt zuletzt", nach belastbaren Betriebsdaten.
