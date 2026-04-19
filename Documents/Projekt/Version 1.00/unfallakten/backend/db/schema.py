"""
Modul 1 – Datenbankschema (DDL)
================================
Alle CREATE TABLE Statements für das Unfallakten-System.
Wird von schema_manager.py ausgeführt.

Tabellen-Übersicht:
  1. benutzer          – Kanzleimitarbeiter, Rollen
  2. unfallakte        – Kernakte pro Unfall
  3. beteiligte        – Alle Personen/Firmen je Akte
  4. schadenpositionen – Alle Schadenposten je Akte
  5. regulierung       – Regulierungsvorgänge der Versicherung
  6. dokumente         – PDFs und Word-Dokumente je Akte
  7. aktivitaeten      – Audit-Log aller Aktionen
"""

SCHEMA_DDL = """

-- ============================================================
-- 1. BENUTZER
-- ============================================================
CREATE TABLE IF NOT EXISTS benutzer (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    passwort_hash   TEXT    NOT NULL,
    rolle           TEXT    NOT NULL DEFAULT 'sachbearbeiter'
                    CHECK(rolle IN ('admin', 'sachbearbeiter')),
    aktiv           INTEGER NOT NULL DEFAULT 1
                    CHECK(aktiv IN (0, 1)),
    erstellt_am     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    zuletzt_login   TEXT
);

-- ============================================================
-- 2. UNFALLAKTE
-- ============================================================
CREATE TABLE IF NOT EXISTS unfallakte (
    az              TEXT    PRIMARY KEY,          -- Aktenzeichen = RA-Micro PK
    unfalldatum     TEXT    NOT NULL DEFAULT '',   -- ISO 8601: YYYY-MM-DD
    unfallort       TEXT,
    erstellt_am     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    geaendert_am    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    status          TEXT    NOT NULL DEFAULT 'offen'
                    CHECK(status IN ('offen', 'in_regulierung', 'klage', 'abgeschlossen')),
    bearbeiter_id   INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
    notizen         TEXT,
    haftungsquote   REAL    NOT NULL DEFAULT 100.0
                    CHECK(haftungsquote BETWEEN 0 AND 100),
    -- RA-Micro Stammdaten (gecacht beim ersten Öffnen)
    kurzbezeichnung TEXT,
    sachbearbeiter  TEXT
);

-- Trigger: geaendert_am automatisch aktualisieren
CREATE TRIGGER IF NOT EXISTS unfallakte_geaendert
    AFTER UPDATE ON unfallakte
    FOR EACH ROW
BEGIN
    UPDATE unfallakte SET geaendert_am = datetime('now', 'localtime')
    WHERE az = OLD.az;
END;

-- ============================================================
-- 3. BETEILIGTE
-- ============================================================
CREATE TABLE IF NOT EXISTS beteiligte (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id         TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,
    rolle           TEXT    NOT NULL
                    CHECK(rolle IN ('mandant', 'gegner', 'zeuge',
                                    'sachverstaendiger', 'sonstiger')),
    name            TEXT    NOT NULL,
    vorname         TEXT,
    firma           TEXT,
    anschrift       TEXT,
    plz             TEXT,
    ort             TEXT,
    telefon         TEXT,
    email           TEXT,
    kfz_kennzeichen TEXT,
    kfz_typ         TEXT,
    versicherung    TEXT,
    vers_nr         TEXT,       -- Versicherungsscheinnummer
    schaden_nr      TEXT,       -- Schadennummer bei der Versicherung
    iban            TEXT,       -- Für Auszahlungen
    notizen         TEXT,
    gutachten_nr    TEXT        -- PORTAL-A2: Auftragsnummer aus Gutachten-Parse
);

CREATE INDEX IF NOT EXISTS idx_beteiligte_akte_id ON beteiligte(akte_id);

-- ============================================================
-- 4. SCHADENPOSITIONEN
-- ============================================================
CREATE TABLE IF NOT EXISTS schadenpositionen (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id             TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,
    -- Fahrzeugschaden
    reparaturkosten     REAL    NOT NULL DEFAULT 0.0,
    wiederbeschaffung   REAL    NOT NULL DEFAULT 0.0,
    restwert            REAL    NOT NULL DEFAULT 0.0,   -- wird abgezogen
    wertminderung       REAL    NOT NULL DEFAULT 0.0,
    -- Nutzung & Mobilität
    nutzungsausfall     REAL    NOT NULL DEFAULT 0.0,
    mietwagenkosten     REAL    NOT NULL DEFAULT 0.0,
    -- Nebenkosten
    sv_kosten           REAL    NOT NULL DEFAULT 0.0,   -- Sachverständigenkosten
    abschleppkosten     REAL    NOT NULL DEFAULT 0.0,
    standkosten         REAL    NOT NULL DEFAULT 0.0,
    anabmeldekosten     REAL    NOT NULL DEFAULT 0.0,
    -- Personenschaden
    schmerzensgeld      REAL    NOT NULL DEFAULT 0.0,
    -- Sonstiges
    sonstiges           REAL    NOT NULL DEFAULT 0.0,
    sonstiges_beschr    TEXT,   -- Beschreibung für "Sonstiges"
    -- Metadaten
    quelle              TEXT    NOT NULL DEFAULT 'manuell'
                        CHECK(quelle IN ('manuell', 'gutachten_pdf',
                                         'abrechnung_pdf', 'korrektur')),
    erfasst_am          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    erfasst_von         INTEGER REFERENCES benutzer(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_schaden_akte_id ON schadenpositionen(akte_id);

-- View: Berechnete Gesamtsumme pro Akte (ersetzt generated column für SQLite-Kompatibilität)
CREATE VIEW IF NOT EXISTS v_schadensummen AS
SELECT
    akte_id,
    reparaturkosten,
    wiederbeschaffung,
    restwert,
    wertminderung,
    nutzungsausfall,
    mietwagenkosten,
    sv_kosten,
    abschleppkosten,
    standkosten,
    anabmeldekosten,
    schmerzensgeld,
    sonstiges,
    -- Fahrzeugschaden-Netto (Wiederbeschaffung ODER Reparatur, je nach Fall)
    (reparaturkosten + wiederbeschaffung - restwert + wertminderung) AS fahrzeugschaden_netto,
    -- Gesamtforderung
    (reparaturkosten
     + wiederbeschaffung
     - restwert
     + wertminderung
     + nutzungsausfall
     + mietwagenkosten
     + sv_kosten
     + abschleppkosten
     + standkosten
     + anabmeldekosten
     + schmerzensgeld
     + sonstiges)                                                    AS gesamt_brutto,
    quelle,
    erfasst_am
FROM schadenpositionen;

-- ============================================================
-- 5. REGULIERUNG
-- ============================================================
CREATE TABLE IF NOT EXISTS regulierung (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id             TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,
    datum               TEXT    NOT NULL,   -- Datum des Abrechnungsschreibens
    betrag_gefordert    REAL    NOT NULL DEFAULT 0.0,
    betrag_reguliert    REAL    NOT NULL DEFAULT 0.0,
    -- Differenz als View-Feld (wird berechnet, nicht gespeichert)
    status              TEXT    NOT NULL DEFAULT 'offen'
                        CHECK(status IN ('offen', 'teilreguliert',
                                         'vollreguliert', 'abgelehnt')),
    vers_referenz       TEXT,   -- Referenznummer der Versicherung
    kuerz_begruendung   TEXT,   -- Begründung für Kürzungen
    -- Aufschlüsselung der regulierten Positionen (JSON-String)
    reguliert_positionen TEXT,  -- z.B. {"reparatur": 4200, "sv_kosten": 0}
    erfasst_am          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    erfasst_von         INTEGER REFERENCES benutzer(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_regulierung_akte_id ON regulierung(akte_id);

-- View: Regulierungsstatus pro Akte (Option B: Summe aus abrechnungsschreiben/regulierung_positionen)
CREATE VIEW IF NOT EXISTS v_regulierungsstatus AS
SELECT
    a.az AS akte_id,
    a.az AS aktenzeichen,
    COALESCE(s.gesamt_brutto, 0.0)      AS betrag_gefordert,
    COALESCE(rp_sum.total, 0.0)         AS betrag_reguliert,
    COALESCE(s.gesamt_brutto, 0.0)
      - COALESCE(rp_sum.total, 0.0)     AS differenz,
    a.status AS akte_status
FROM unfallakte a
LEFT JOIN v_schadensummen s ON s.akte_id = a.az
LEFT JOIN (
    SELECT ab.akte_id, SUM(rp.betrag_reguliert) AS total
    FROM abrechnungsschreiben ab
    JOIN regulierung_positionen rp ON rp.abrechnungsschreiben_id = ab.id
    GROUP BY ab.akte_id
) rp_sum ON rp_sum.akte_id = a.az
GROUP BY a.az;

-- ============================================================
-- 6. DOKUMENTE
-- ============================================================
CREATE TABLE IF NOT EXISTS dokumente (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id         TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,
    typ             TEXT    NOT NULL
                    CHECK(typ IN ('gutachten', 'abrechnungsschreiben',
                                  'forderungsschreiben', 'sachstandsanfrage',
                                  'klage', 'sonstiges')),
    dateiname       TEXT    NOT NULL,
    dateipfad       TEXT    NOT NULL,   -- Relativer Pfad ab /uploads/
    dateityp        TEXT    NOT NULL DEFAULT 'pdf'
                    CHECK(dateityp IN ('pdf', 'docx', 'jpg', 'png')),
    dateigroesse    INTEGER,            -- Bytes
    hochgeladen_am  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    hochgeladen_von INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
    -- PDF-Parsing Metadaten
    parse_status    TEXT    NOT NULL DEFAULT 'ausstehend'
                    CHECK(parse_status IN ('ausstehend', 'erfolgreich',
                                           'fehler', 'manuell_korrigiert')),
    parse_konfidenz REAL,               -- 0.0–1.0
    parse_json      TEXT,               -- Rohes Parse-Ergebnis als JSON
    parse_fehler    TEXT,               -- Fehlermeldung bei parse_status='fehler'
    notizen         TEXT
);

CREATE INDEX IF NOT EXISTS idx_dokumente_akte_id ON dokumente(akte_id);
CREATE INDEX IF NOT EXISTS idx_dokumente_typ     ON dokumente(typ);

-- ============================================================
-- 7. AKTIVITAETEN (Audit-Log)
-- ============================================================
CREATE TABLE IF NOT EXISTS aktivitaeten (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id         TEXT    REFERENCES unfallakte(az) ON DELETE SET NULL,
    benutzer_id     INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
    zeitstempel     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    aktion          TEXT    NOT NULL,   -- z.B. 'akte_erstellt', 'pdf_hochgeladen'
    beschreibung    TEXT    NOT NULL,   -- Lesbare Beschreibung
    -- Für Audit-Trail: Was hat sich geändert?
    tabelle         TEXT,               -- Betroffene Tabelle
    datensatz_id    INTEGER,            -- ID des betroffenen Datensatzes
    aenderung_json  TEXT                -- {"vorher": {...}, "nachher": {...}}
);

CREATE INDEX IF NOT EXISTS idx_aktivitaeten_akte_id ON aktivitaeten(akte_id);
CREATE INDEX IF NOT EXISTS idx_aktivitaeten_zeit    ON aktivitaeten(zeitstempel);

-- ============================================================
-- SCHEMA-VERSION (für spätere Migrationen)
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version         INTEGER PRIMARY KEY,
    beschreibung    TEXT,
    angewendet_am   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

INSERT OR IGNORE INTO schema_version (version, beschreibung)
VALUES (1, 'Initiales Schema – Modul 1');

"""
