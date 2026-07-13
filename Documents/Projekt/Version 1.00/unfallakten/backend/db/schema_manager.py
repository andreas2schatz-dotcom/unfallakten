"""
Modul 1 – Schema-Manager
=========================
Erstellt, prüft und migriert das Datenbankschema.
Ersetzt Alembic für die SQLite-Phase.

Verwendung:
    python -m backend.db.schema_manager          # Schema anlegen
    python -m backend.db.schema_manager --check  # Nur prüfen
    python -m backend.db.schema_manager --reset  # VORSICHT: Alles löschen + neu
"""

import sys
import logging
import sqlite3
from .database import get_connection, get_db_path
from .schema import SCHEMA_DDL

logger = logging.getLogger(__name__)

# Migrations-Registry: version -> SQL
# Neue Migrationen hier eintragen (für Phase 2+)
MIGRATIONS: dict[int, str] = {
    # Modul 7: E-Mail-Import-Log
    2: """
CREATE TABLE IF NOT EXISTS email_import_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id       TEXT    NOT NULL UNIQUE,
    betreff          TEXT,
    absender         TEXT,
    empfangen_am     TEXT,
    importiert_am    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    akte_id          INTEGER REFERENCES unfallakte(id) ON DELETE SET NULL,
    status           TEXT    NOT NULL DEFAULT 'verarbeitet'
                     CHECK(status IN ('verarbeitet', 'kein_treffer',
                                      'fehler', 'ignoriert')),
    anhaenge_anzahl  INTEGER DEFAULT 0,
    importierte_dok  TEXT,
    notizen          TEXT
);
CREATE INDEX IF NOT EXISTS idx_email_log_akte_id ON email_import_log(akte_id);
CREATE INDEX IF NOT EXISTS idx_email_log_status  ON email_import_log(status);
    """,
    # Modul 9: Regulierungsverlauf & Kürzungskatalog
    3: """
-- ============================================================
-- KÜRZUNGSARTEN (Stammdaten / Wissensdatenbank)
-- ============================================================
CREATE TABLE IF NOT EXISTS kuerzungsarten (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    bezeichnung                     TEXT    NOT NULL UNIQUE,
    kategorie                       TEXT    NOT NULL
                                    CHECK(kategorie IN (
                                        'fahrzeugschaden',
                                        'ersatzbeschaffung',
                                        'sonstiger_schaden',
                                        'technisch_gutachten'
                                    )),
    standard_gegenargument          TEXT,
    rechtsgrundlagen                TEXT,
    hinweis_intern                  TEXT,
    sv_stellungnahme_erforderlich   INTEGER NOT NULL DEFAULT 0
                                    CHECK(sv_stellungnahme_erforderlich IN (0,1)),
    aktiv                           INTEGER NOT NULL DEFAULT 1
                                    CHECK(aktiv IN (0,1)),
    sortierung                      INTEGER NOT NULL DEFAULT 0,
    erstellt_am                     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Seed: 19 Kürzungsarten aus Kanzlei-Liste
INSERT OR IGNORE INTO kuerzungsarten
    (bezeichnung, kategorie, standard_gegenargument, hinweis_intern, sv_stellungnahme_erforderlich, sortierung)
VALUES
    ('Stundenverrechnungssätze',        'fahrzeugschaden',    'Werkstattrisiko liegt beim Schädiger; fiktiv nach Stundenverrechnungssatz der Fachwerkstatt zu ersetzen; Verweisbetrieb nur bei konkreter gleichwertiger Werkstatt zulässig.', 'Verweisbetrieb prüfen', 0, 10),
    ('Wertminderung',                   'fahrzeugschaden',    'Wertminderung ist nach Gutachten zu ersetzen; MwSt-Abzug nur bei gewerblicher Nutzung; abweichende Berechnung bedarf Begründung.', 'MwSt / Berechnungsmethode prüfen', 0, 20),
    ('Ersatzteilaufschläge / UPE-Zuschläge', 'fahrzeugschaden', 'UPE-Zuschläge sind auch bei fiktiver Abrechnung zu ersetzen; Händlerpreise sind marktüblich.', 'auch fiktiv zu ersetzen', 0, 30),
    ('Verbringungskosten',              'fahrzeugschaden',    'Verbringungskosten sind ortsüblich und auch fiktiv erstattungsfähig, wenn im Gutachten ausgewiesen.', 'auch fiktiv zu ersetzen', 0, 40),
    ('Beilackierung',                   'fahrzeugschaden',    'Beilackierung ist zu ersetzen wenn Sachverständiger dies für farbliche Anpassung vorsieht; kein Abzug zulässig.', 'SV-Gutachten maßgeblich', 0, 50),
    ('Kürzung Reparaturrechnung',       'fahrzeugschaden',    'Kürzung der Reparaturrechnung ist unzulässig; Werkstattrisiko liegt allein beim Schädiger (BGH VI ZR 398/02).', 'nie zulässig – Werkstattrisiko', 0, 60),
    ('Tankrest',                        'fahrzeugschaden',    'Tankrest ist als Teil des Fahrzeugzustands zu ersetzen wenn im Gutachten ausgewiesen.', 'Gutachten prüfen', 0, 70),
    ('Batteriestützbetrieb',            'fahrzeugschaden',    'Batteriestützbetrieb ist als notwendige Reparaturmaßnahme auch fiktiv erstattungsfähig.', 'auch fiktiv zu ersetzen', 0, 80),
    ('Fehlerspeicher auslesen',         'fahrzeugschaden',    'Kosten für Fehlerspeicher-Auslesung sind unfallbedingte Reparaturkosten, auch fiktiv zu ersetzen.', 'auch fiktiv zu ersetzen', 0, 90),
    ('Kleinteilpauschale',              'fahrzeugschaden',    'Kleinteilpauschale ist Bestandteil der Reparaturkalkulation und auch fiktiv zu ersetzen.', 'auch fiktiv zu ersetzen', 0, 100),
    ('Technische Kürzungen',            'technisch_gutachten','Abweichender Reparaturweg bedarf Stellungnahme des Sachverständigen; einseitige Kürzung durch Versicherung unzulässig.', 'SV-Stellungnahme erforderlich', 1, 110),
    ('Zulassungsdienst',                'ersatzbeschaffung',  'Kosten eines Zulassungsdienstes sind erstattungsfähige Nebenkosten bei Ersatzbeschaffung.', NULL, 0, 120),
    ('Kennzeichen / Schilderkosten',    'ersatzbeschaffung',  'Kennzeichenkosten sind notwendige Nebenkosten der Wiederbeschaffung und zu ersetzen.', NULL, 0, 130),
    ('Wunschkennzeichen',               'ersatzbeschaffung',  'Mehrkosten gegenüber Standardkennzeichen sind nicht erstattungsfähig; Grundkosten für Kennzeichen schon.', 'nur Grundbetrag erstattungsfähig', 0, 140),
    ('Unkostenpauschale',               'sonstiger_schaden',  'Unkostenpauschale mindestens 30 € nach ständiger Rechtsprechung; Kürzung auf 25 € ist unzulässig.', 'mind. 30 €', 0, 150),
    ('Nutzungsausfall',                 'sonstiger_schaden',  'Dauer des Nutzungsausfalls richtet sich nach Reparaturdauer laut Gutachten zzgl. Wiederbeschaffungszeit; Kürzung bedarf konkreter Begründung.', 'Dauer prüfen', 0, 160),
    ('Kürzung Sachverständigenrechnung','sonstiger_schaden',  'SV-Rechnung ist vollständig zu ersetzen; Werkstattrisiko-Grundsatz gilt analog (BGH VI ZR 67/06).', 'wie Werkstattrisiko', 0, 170),
    ('Mietwagenrechnung',               'sonstiger_schaden',  'Erstattung nach Schwacke-Liste oder Fraunhofer-Tabelle; Kürzung nur bei erheblicher Überschreitung des Marktüblichen zulässig.', 'Tabelle prüfen', 0, 180),
    ('Verdienstausfall',                'sonstiger_schaden',  'Verdienstausfall ist durch Lohnbescheinigung oder Einkommenssteuerbescheid zu belegen; Abzug nur bei fehlendem Nachweis zulässig.', 'Nachweis prüfen', 0, 190);

-- ============================================================
-- ABRECHNUNGSSCHREIBEN (Regulierungsverlauf)
-- ============================================================
CREATE TABLE IF NOT EXISTS abrechnungsschreiben (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id             INTEGER NOT NULL REFERENCES unfallakte(id) ON DELETE CASCADE,
    datum               TEXT    NOT NULL,
    versicherung        TEXT,
    referenz_nr         TEXT,
    haftungsquote       REAL    NOT NULL DEFAULT 100.0
                        CHECK(haftungsquote BETWEEN 0 AND 100),
    haftungsart         TEXT    NOT NULL DEFAULT 'vollhaftung'
                        CHECK(haftungsart IN (
                            'vollhaftung', 'mithaftung', 'quote', 'ablehnung'
                        )),
    haftungsbegruendung TEXT,
    gesamt_gefordert    REAL    NOT NULL DEFAULT 0.0,
    gesamt_reguliert    REAL    NOT NULL DEFAULT 0.0,
    dokument_id         INTEGER REFERENCES dokumente(id) ON DELETE SET NULL,
    parse_status        TEXT    NOT NULL DEFAULT 'manuell'
                        CHECK(parse_status IN (
                            'ausstehend', 'erfolgreich', 'teilweise', 'manuell', 'fehlgeschlagen'
                        )),
    notizen             TEXT,
    erfasst_am          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    erfasst_von         INTEGER REFERENCES benutzer(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_abrechnung_akte_id ON abrechnungsschreiben(akte_id);

-- ============================================================
-- REGULIERUNG_POSITIONEN (positionsgenaue Regulierung)
-- ============================================================
CREATE TABLE IF NOT EXISTS regulierung_positionen (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    abrechnungsschreiben_id     INTEGER NOT NULL
                                REFERENCES abrechnungsschreiben(id) ON DELETE CASCADE,
    position_key                TEXT    NOT NULL
                                CHECK(position_key IN (
                                    'reparaturkosten', 'wiederbeschaffung', 'restwert',
                                    'wertminderung', 'nutzungsausfall', 'mietwagenkosten',
                                    'sv_kosten', 'abschleppkosten', 'standkosten',
                                    'anabmeldekosten', 'schmerzensgeld', 'sonstiges',
                                    'reparatur_brutto', 'reparatur_netto',
                                    'wbw', 'wbw_netto', 'wbw_brutto',
                                    'fahrzeugschaden', 'kostenpauschale',
                                    'ra_gebuehren', 'mwst_abzug', 'pruefbericht_abzug'
                                )),
    betrag_gefordert            REAL    NOT NULL DEFAULT 0.0,
    betrag_reguliert            REAL    NOT NULL DEFAULT 0.0,
    kuerzungsart_id             INTEGER REFERENCES kuerzungsarten(id) ON DELETE SET NULL,
    kuerzung_freitext           TEXT,
    parser_erkannt              INTEGER NOT NULL DEFAULT 0
                                CHECK(parser_erkannt IN (0,1)),
    parser_konfidenz            REAL,
    fuer_klage_vorgemerkt       INTEGER NOT NULL DEFAULT 0
                                CHECK(fuer_klage_vorgemerkt IN (0,1)),
    sv_stellungnahme_ausstehend INTEGER NOT NULL DEFAULT 0
                                CHECK(sv_stellungnahme_ausstehend IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_regpos_abrechnung_id ON regulierung_positionen(abrechnungsschreiben_id);
CREATE INDEX IF NOT EXISTS idx_regpos_klage         ON regulierung_positionen(fuer_klage_vorgemerkt);

-- ============================================================
-- PRUEFBERICHTE
-- ============================================================
CREATE TABLE IF NOT EXISTS pruefberichte (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    akte_id                         INTEGER NOT NULL REFERENCES unfallakte(id) ON DELETE CASCADE,
    abrechnungsschreiben_id         INTEGER REFERENCES abrechnungsschreiben(id) ON DELETE SET NULL,
    datum                           TEXT    NOT NULL,
    gutachter                       TEXT,
    dokument_id                     INTEGER REFERENCES dokumente(id) ON DELETE SET NULL,
    parse_status                    TEXT    NOT NULL DEFAULT 'manuell'
                                    CHECK(parse_status IN (
                                        'ausstehend', 'erfolgreich', 'teilweise', 'manuell', 'fehlgeschlagen'
                                    )),
    -- PDF-Parser Felder
    pruefdienstleister              TEXT,
    vorgangsnummer                  TEXT,
    schadennummer                   TEXT,
    reparaturkosten_vor_pruefung    REAL,
    abzug_technisch                 REAL,
    abzug_werkstattalternative      REAL,
    abzug_gesamt                    REAL,
    reparaturkosten_nach_pruefung   REAL,
    referenzwerkstatt_name          TEXT,
    referenzwerkstatt_adresse       TEXT,
    referenzwerkstatt_entfernung    REAL,
    ist_image_pdf                   INTEGER NOT NULL DEFAULT 0,
    fahrzeug_hersteller             TEXT,
    fahrzeug_typ                    TEXT,
    fahrzeug_kennzeichen            TEXT,
    -- Allgemein
    kuerzungen_json                 TEXT,
    notizen                         TEXT,
    erfasst_am                      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    erfasst_von                     INTEGER REFERENCES benutzer(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pruefbericht_akte_id ON pruefberichte(akte_id);

INSERT OR IGNORE INTO schema_version (version, beschreibung)
VALUES (3, 'Modul 9 – Regulierungsverlauf, Kürzungskatalog, Abrechnungsschreiben');
    """,
    # Phase 2: PDF-Parser – Prüfbericht-Felder (als Marker, Ausführung via _run_migration_4)
    4: "-- migration_4_pruefbericht_felder",
    # Phase 3: AZ als Primary Key – Migration via Python-Handler
    5: "-- migration_5_az_als_pk",
    # Phase 4: Neue Schadenfelder aus WDM-Mapping
    6: "-- migration_6_schaden_felder",
    # Phase 5: v_regulierungsstatus GROUP BY a.id → a.az
    7: """
DROP VIEW IF EXISTS v_regulierungsstatus;
CREATE VIEW IF NOT EXISTS v_regulierungsstatus AS
SELECT
    a.az             AS akte_id,
    a.az             AS aktenzeichen,
    COALESCE(s.gesamt_brutto, 0.0)          AS betrag_gefordert,
    COALESCE(SUM(r.betrag_reguliert), 0.0)  AS betrag_reguliert,
    COALESCE(s.gesamt_brutto, 0.0)
      - COALESCE(SUM(r.betrag_reguliert), 0.0) AS differenz,
    a.status         AS akte_status
FROM unfallakte a
LEFT JOIN v_schadensummen s ON s.akte_id = a.az
LEFT JOIN regulierung r     ON r.akte_id = a.az
GROUP BY a.az;
INSERT OR IGNORE INTO schema_version (version, beschreibung)
VALUES (7, 'Migration 7 – v_regulierungsstatus GROUP BY az');
    """,
    # Migration 8: Anrede/Vorsteuer in beteiligte, Nachbesichtigungskosten in schadenpositionen
    8: "-- migration_8_forderungsschreiben_felder",
    # Migration 9: Forderungshistorie pro Position und Schreiben
    9: "-- migration_9_forderung_positionen",
    # Migration 10: Feldnamen-Harmonisierung rep_fiktiv_* → rep_gutachten_*, rep_rechnung_*
    10: "-- migration_10_feldnamen_harmonisierung",
    # Migration 11: aktivitaeten PRIMARY KEY reparieren (nach CREATE TABLE AS SELECT in Mig. 5)
    11: "-- migration_11_aktivitaeten_pk",
    # Migration 12: abrechnungsart in schadenpositionen
    12: "-- migration_12_abrechnungsart",
    # Migration 13: Neue Tabelle personenschaden
    13: "-- migration_13_personenschaden",
    # Migration 14: Netto/USt-Felder für Nebenkosten
    14: "-- migration_14_nebenkosten_netto_ust",
    # Migration 15: Tabelle personenschaden_beteiligte
    15: "-- migration_15_personenschaden_beteiligte",
    # Migration 16: Manuelle Regulierung + WDM-Fallback
    16: "-- migration_16_manuell_regulierung",
    # Migration 17: email_import_log - akte_id TEXT FK + neue Felder
    17: "-- migration_17_email_import_log_v2",
    # Migration 18: in_akte_importiert + email_absender_vorlagen
    18: "-- migration_18_email_absender_vorlagen",
    # Migration 19: email_typ + Aktion-Badge
    19: "-- migration_19_email_typ_aktion_badge",
    # Migration 20: aktivitaeten.akte_id TEXT (war INTEGER, inkompatibel mit az-PK)
    20: "-- migration_20_aktivitaeten_akte_id_text",
    # Migration 21: email_absender_vorlagen + versicherer_name/kuerzel + Seed-Daten
    21: "-- migration_21_versicherer_seed",
    22: "-- migration_22_kuerzungsarten_textbaustein",
    23: "-- migration_23_todos",
    24: "-- migration_24_dokumentenklassen",
    25: "-- migration_25_klassifikation_training",
    26: "-- migration_26_eakte_integration",
    27: "-- migration_27_schadenposition_belege",
    28: "-- migration_28_aktivlegitimation",
    29: "-- migration_29_rechnung_parse_cache",
    30: "-- migration_30_fragebogen_erstkontakt",
    31: "-- migration_31_fristen_index",
    32: "-- migration_32_todos_dok_ref_fix",
    33: "-- migration_33_konfiguration",
    34: "-- migration_34_ist_halter",
    35: "-- migration_35_gebuehren_assistent",
    36: "-- migration_36_sg_felder",
    # Migration 37: v_regulierungsstatus auf abrechnungsschreiben/regulierung_positionen
    37: """
DROP VIEW IF EXISTS v_regulierungsstatus;
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
INSERT OR IGNORE INTO schema_version (version, beschreibung)
VALUES (37, 'Migration 37 – v_regulierungsstatus aus abrechnungsschreiben/regulierung_positionen');
    """,
    38: "-- migration_38_portal_sync",  # Handled by _run_migration_38
    39: "-- migration_39_gutachten_nr",  # Handled by _run_migration_39
    40: "-- migration_40_stellungnahme_texte",  # Handled by _run_migration_40
    41: "-- migration_41_sv_portal_accounts",  # Handled by _run_migration_41
    42: "-- migration_42_eml_dateityp",  # Handled by _run_migration_42
    43: "-- migration_43_imap_polling",  # Handled by _run_migration_43
    44: "-- migration_44_email_konto",   # Handled by _run_migration_44
    45: "-- migration_45_regulierung_status",  # Handled by _run_migration_45
    46: "-- migration_46_intake_datenmodell",   # Handled by _run_migration_46 (S1.1 + K-P2)
    47: "-- migration_47_absender_registry",    # Handled by _run_migration_47 (S1.4)
    48: "-- migration_48_queue_felder",         # Handled by _run_migration_48 (S1.6a)
    49: "-- migration_49_email_import_log_ausgeblendet", # Handled by _run_migration_49 (S1.9a)
    50: "-- migration_50_unfalldetails_create", # Handled by _run_migration_50 (Root-Cause-Fix zu Migration 28)
    51: "-- migration_51_ereignisse",  # Handled by _run_migration_51 (P1.2)
    52: "-- migration_52_todos_fristablauf",  # Handled by _run_migration_52 (P1.6)
    53: "-- migration_53_intake_verworfen",  # Handled by _run_migration_53 (Verwerfen-Workflow)
    54: "-- migration_54_textquelle_email_text",  # Handled by _run_migration_54 (Text-Pfad Intake)
    55: "-- migration_55_intake_review_geoeffnet",  # Handled by _run_migration_55 (N-08 Baseline Sekunden pro Freigabe)
}

# Neue Spalten für pruefberichte (SQLite kennt kein ADD COLUMN IF NOT EXISTS)
_PRUEFBERICHT_NEUE_SPALTEN = [
    ("pruefdienstleister",           "TEXT"),
    ("vorgangsnummer",               "TEXT"),
    ("schadennummer",                "TEXT"),
    ("reparaturkosten_vor_pruefung", "REAL"),
    ("abzug_technisch",              "REAL"),
    ("abzug_werkstattalternative",   "REAL"),
    ("abzug_gesamt",                 "REAL"),
    ("reparaturkosten_nach_pruefung","REAL"),
    ("referenzwerkstatt_name",       "TEXT"),
    ("referenzwerkstatt_adresse",    "TEXT"),
    ("referenzwerkstatt_entfernung", "REAL"),
    ("ist_image_pdf",                "INTEGER NOT NULL DEFAULT 0"),
    ("fahrzeug_hersteller",          "TEXT"),
    ("fahrzeug_typ",                 "TEXT"),
    ("fahrzeug_kennzeichen",         "TEXT"),
]


def _run_migration_4(conn: sqlite3.Connection) -> None:
    """Fügt neue Spalten zu pruefberichte hinzu – ignoriert OperationalError falls bereits vorhanden."""
    vorhandene = {row[1] for row in conn.execute("PRAGMA table_info(pruefberichte)").fetchall()}
    for spalte, typ in _PRUEFBERICHT_NEUE_SPALTEN:
        if spalte not in vorhandene:
            try:
                conn.execute(f"ALTER TABLE pruefberichte ADD COLUMN {spalte} {typ}")
                logger.info("Spalte pruefberichte.%s hinzugefügt.", spalte)
            except sqlite3.OperationalError as e:
                logger.warning("Spalte pruefberichte.%s: %s", spalte, e)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (4, "Phase 2 – Prüfbericht PDF-Felder"),
    )


def _run_migration_44(conn: sqlite3.Connection) -> None:
    """Migration 44: konto-Spalte in email_import_log für Account-Trennung (unfall/termin/bussgeld/info)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(email_import_log)").fetchall()}
    if "konto" not in cols:
        # Direktes Commit nötig: ALTER TABLE in sqlite3 läuft außerhalb des
        # impliziten Transaktionskontexts und braucht einen eigenen Commit.
        conn.commit()
        conn.execute("ALTER TABLE email_import_log ADD COLUMN konto TEXT")
        conn.commit()
        logger.info("Migration 44: email_import_log.konto hinzugefuegt.")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (44, "Migration 44 – email_import_log.konto (Account-Trennung)"),
    )
    logger.info("Migration 44 abgeschlossen.")


def _run_migration_45(conn: sqlite3.Connection) -> None:
    """Migration 45: regulierung_status in unfallakte (offen/abgelehnt/teilhaftung)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
    if "regulierung_status" not in cols:
        conn.commit()
        conn.execute(
            "ALTER TABLE unfallakte ADD COLUMN regulierung_status TEXT NOT NULL DEFAULT 'offen'"
        )
        conn.commit()
        logger.info("Migration 45: unfallakte.regulierung_status hinzugefuegt.")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (45, "Migration 45 – unfallakte.regulierung_status (offen/abgelehnt/teilhaftung)"),
    )
    logger.info("Migration 45 abgeschlossen.")


def _run_migration_46(conn: sqlite3.Connection) -> None:
    """
    Migration 46 (S1.1) — Intake-Datenmodell nach v7 + K-P2 (freigabe.md).

    Legt vier neue Tabellen an (additiv, altes Datenmodell bleibt unberuehrt):

    * ``intake_dokumente``  Zieltabelle des v7-Begriffs DOKUMENT. Hash-dedupliziert,
                            akte-unabhaengig. K-P2: enthaelt KEINE akte_az /
                            freigegeben_*-Spalten — diese liegen in ``freigaben``.
    * ``zustellungen``      n:1 auf intake_dokumente, wird nie geloescht. Traegt
                            Quelle/Absender/Auth-Status/Signale. FK-Spalte heisst
                            ``intake_dokument_id`` (nicht ``dokument_id``), um
                            Verwechslung mit der alten ``dokumente``-Tabelle
                            auszuschliessen.
    * ``freigaben``         K-P2: eigene Relation. Dasselbe intake_dokument kann in
                            mehrere Akten freigegeben werden (zwei Mandanten, ein
                            Unfall). ``dokument_id`` ist die FK-Bruecke zur alten
                            ``dokumente``-Zeile, die die Freigabe erzeugt hat.
    * ``korrektur_log``     Feld/Wert alt/neu/Klasse/Registry-Version je Aenderung.

    Backfill (K-P2 angepasst):
        Fuer jede bestehende ``dokumente``-Zeile werden erzeugt: eine intake_dokumente-Zeile
        (sha256-Duplikate ueber Akten hinweg werden zu EINER intake_dokumente-Zeile
        vereinigt), eine ``zustellungen``-Zeile mit quelle='altbestand' und eine
        ``freigaben``-Zeile. Dokumente ohne pdf_hash bekommen einen Synthese-Hash
        mit dem Prefix ``altbestand:`` — dieser Prefix kann mit echten SHA-256
        (hex, ohne ':') nicht kollidieren.

        Testkriterium: ``COUNT(zustellungen) == COUNT(freigaben) == COUNT(dokumente)``.

    Vollstaendig idempotent. Kein executescript; ALTER waere nicht noetig
    (nur CREATE + INSERT OR IGNORE), aber der Backfill-Loop prueft jeden Fall
    explizit ab.
    """

    # ------------------------------------------------------------------
    # 1) Tabellen anlegen (idempotent via IF NOT EXISTS)
    # ------------------------------------------------------------------
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intake_dokumente (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256              TEXT NOT NULL UNIQUE,
            original_pfad       TEXT,
            arbeitskopie_pfad   TEXT,
            payload_typ         TEXT NOT NULL DEFAULT 'datei'
                                CHECK (payload_typ IN ('datei','text','structured')),
            structured_payload  TEXT,
            klasse              TEXT,
            klasse_quelle       TEXT CHECK (klasse_quelle IN ('auto','manuell')),
            konfidenz           REAL,
            parse_json          TEXT,
            textquelle          TEXT CHECK (textquelle IN ('textebene','ocr','gemischt','email_text')),
            registry_version    TEXT,
            llm_stack           TEXT,
            queue_status        TEXT NOT NULL DEFAULT 'neu'
                                CHECK (queue_status IN
                                    ('neu','laeuft','bereit_zur_review',
                                     'pipeline_fehler','freigegeben')),
            prioritaet_frist    TEXT,
            loeschfrist_bis     TEXT,
            erstellt_am         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intake_dok_sha ON intake_dokumente(sha256)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_intake_dok_queue ON intake_dokumente(queue_status)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS zustellungen (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            intake_dokument_id  INTEGER NOT NULL REFERENCES intake_dokumente(id),
            quelle              TEXT NOT NULL
                                CHECK (quelle IN
                                    ('imap','upload','eakte','portal','altbestand')),
            absender            TEXT,
            auth_status         TEXT,
            betreff             TEXT,
            empfangen_am        TEXT,
            parent_id           INTEGER REFERENCES zustellungen(id),
            signale_json        TEXT,
            konto               TEXT,
            roh_referenz        TEXT,
            erstellt_am         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_zust_intake ON zustellungen(intake_dokument_id)")
    # Backfill-Idempotenz: pro alter dokumente(id) hoechstens eine altbestand-Zustellung.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_zust_altbestand_ref "
        "ON zustellungen(roh_referenz) WHERE quelle = 'altbestand'"
    )

    # Hinweis: dokument_id verweist semantisch auf ``dokumente(id)`` (K-P2-Bruecke).
    # Der FK-REFERENCES-Constraint wird NICHT deklariert, weil die Produktiv-DB
    # ``dokumente`` mit ``id INT`` ohne PRIMARY KEY fuehrt (DECISIONS.md F-02).
    # SQLite meldet dann bei jedem INSERT einen "foreign key mismatch", selbst
    # bei foreign_keys=OFF. Die Bruecke ist trotzdem stabil: dokumente.id ist
    # in der Praxis eindeutig (via schadenmanager erzeugt) — die Konvention wird
    # in der Anwendungsschicht durchgesetzt.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS freigaben (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            intake_dokument_id  INTEGER NOT NULL REFERENCES intake_dokumente(id),
            akte_az             TEXT NOT NULL REFERENCES unfallakte(az),
            dokument_id         INTEGER NOT NULL, -- REFERENCES dokumente(id) semantisch, s. Kommentar
            freigegeben_von     INTEGER REFERENCES benutzer(id),
            freigegeben_am      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE (intake_dokument_id, akte_az, dokument_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_freigaben_intake ON freigaben(intake_dokument_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_freigaben_akte ON freigaben(akte_az)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS korrektur_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            intake_dokument_id  INTEGER NOT NULL REFERENCES intake_dokumente(id),
            feld                TEXT NOT NULL,
            wert_alt            TEXT,
            wert_neu            TEXT,
            klasse              TEXT,
            registry_version    TEXT,
            benutzer_id         INTEGER REFERENCES benutzer(id),
            zeitstempel         TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_korrlog_intake ON korrektur_log(intake_dokument_id)")

    # ------------------------------------------------------------------
    # 2) Backfill aus bestehender dokumente-Tabelle
    # ------------------------------------------------------------------
    rows = conn.execute("""
        SELECT id, akte_id, pdf_hash, dokumentenklasse,
               parse_konfidenz, parse_json, dateipfad
        FROM dokumente
    """).fetchall()

    for row in rows:
        dok_id       = row[0]
        akte_az      = row[1]
        pdf_hash     = (row[2] or "").strip() if row[2] is not None else ""
        dok_klasse   = row[3]
        konfidenz    = row[4]
        parse_json   = row[5]
        dateipfad    = row[6]

        if akte_az is None or str(akte_az).strip() == "":
            # Ohne akte_id keine Freigabe rekonstruierbar — Alt-Zeile ueberspringen.
            continue

        # Orphan-Guard: dokumente kann auf eine bereits geloeschte Akte zeigen.
        # freigaben.akte_az hat FK → unfallakte(az); ohne diesen Check bricht
        # der komplette Backfill an der ersten Waise ab (statt sie zu ueber-
        # springen). Vgl. feedback_migration_executescript im Memory-Index:
        # frueher schlug der Fehler die schema_version-Stempelung durch --
        # nur der Datensatz selbst blieb aus.
        exists = conn.execute(
            "SELECT 1 FROM unfallakte WHERE az = ?", (akte_az,)
        ).fetchone()
        if not exists:
            logger.warning(
                "Migration 46 Backfill: Dokument %s zeigt auf unbekannte Akte "
                "%r — ueberspringe (Orphan-Dokument).", dok_id, akte_az,
            )
            continue

        if pdf_hash:
            sha = pdf_hash
        else:
            # Synthese-Hash. Prefix 'altbestand:' kollidiert nicht mit echten SHA-256 (hex).
            sha = f"altbestand:{dok_id}"

        # intake_dokument fuer diesen Hash (INSERT OR IGNORE nutzt UNIQUE-Constraint).
        conn.execute(
            """
            INSERT OR IGNORE INTO intake_dokumente
                (sha256, original_pfad, klasse, klasse_quelle, konfidenz,
                 parse_json, queue_status)
            VALUES (?, ?, ?, 'auto', ?, ?, 'freigegeben')
            """,
            (sha, dateipfad, dok_klasse, konfidenz, parse_json),
        )
        intake_id = conn.execute(
            "SELECT id FROM intake_dokumente WHERE sha256 = ?", (sha,)
        ).fetchone()[0]

        # Zustellung (idempotent ueber partial UNIQUE auf quelle='altbestand', roh_referenz)
        conn.execute(
            """
            INSERT OR IGNORE INTO zustellungen
                (intake_dokument_id, quelle, roh_referenz)
            VALUES (?, 'altbestand', ?)
            """,
            (intake_id, f"altbestand:{dok_id}"),
        )

        # Freigabe (idempotent ueber UNIQUE(intake_dokument_id, akte_az, dokument_id))
        conn.execute(
            """
            INSERT OR IGNORE INTO freigaben
                (intake_dokument_id, akte_az, dokument_id)
            VALUES (?, ?, ?)
            """,
            (intake_id, akte_az, dok_id),
        )

    # ------------------------------------------------------------------
    # 3) schema_version stempeln
    # ------------------------------------------------------------------
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (46, "Migration 46 – Intake-Datenmodell S1.1 (intake_dokumente, "
             "zustellungen, freigaben [K-P2], korrektur_log) + Backfill"),
    )
    logger.info("Migration 46 abgeschlossen (intake-Datenmodell + Backfill).")


def _run_migration_51(conn: sqlite3.Connection) -> None:
    """
    Migration 51 (P1.2) - Ereignis-Datenmodell fuer das Positionsmodell.

    Legt drei Tabellen an (POSITIONSMODELL-PLAN Abschnitt 4.1-4.4):

    * ``ereignisse``            Ebene 1 Kopf (Fakten-Log, kein UPDATE ausser
                                ersetzt_durch/versand_bestaetigt_am, kein DELETE)
    * ``ereignis_positionen``   Ebene 1 n:m mit positionsscharfer Wirkung.
                                K-M1 (freigabe.md): UNIQUE(ereignis_id,
                                position_key, wirkung, COALESCE(kuerzungsart_id, 0)).
    * ``position_ereignis_cache``  Ebene 2, Materialisierung fuer schnelle
                                Ableitung. Nur ``ereignis_service`` schreibt.

    Alles additiv, kein Datenverlust an bestehenden Tabellen.
    """
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ereignisse (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_az                TEXT NOT NULL REFERENCES unfallakte(az),
            ereignistyp            TEXT NOT NULL,
            richtung               TEXT NOT NULL
                                   CHECK (richtung IN
                                       ('eingehend','ausgehend','intern')),
            quelle                 TEXT NOT NULL
                                   CHECK (quelle IN
                                       ('dokument','system','manuell')),
            datum                  TEXT NOT NULL,
            dokument_id            INTEGER,
            herkunft               TEXT,
            betragswirkung_gesamt  REAL,
            ersetzt_durch          INTEGER REFERENCES ereignisse(id),
            versand_bestaetigt_am  TEXT,
            notiz                  TEXT,
            erfasst_von            INTEGER REFERENCES benutzer(id),
            erfasst_am             TEXT NOT NULL
                                   DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ereignisse_akte_datum "
        "ON ereignisse(akte_az, datum)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ereignisse_dokument "
        "ON ereignisse(dokument_id)"
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ereignis_positionen (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ereignis_id    INTEGER NOT NULL REFERENCES ereignisse(id),
            position_key   TEXT NOT NULL,
            wirkung        TEXT NOT NULL
                           CHECK (wirkung IN
                               ('gefordert','anerkannt','gekuerzt',
                                'abgelehnt','erledigt','beleg','keine')),
            betrag         REAL,
            kuerzungsart_id INTEGER REFERENCES kuerzungsarten(id),
            ersetzt_durch  INTEGER REFERENCES ereignis_positionen(id)
        )
    """)
    # K-M1: mehrere Kuerzungsarten auf derselben Position im selben Ereignis
    # sind der Normalfall (Prueberichts-Positionen). Unique auf
    # COALESCE(kuerzungsart_id, 0), damit NULL != NULL nicht die
    # Duplikat-Erkennung sabotiert.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "uidx_ereigpos_km1 ON ereignis_positionen "
        "(ereignis_id, position_key, wirkung, COALESCE(kuerzungsart_id, 0))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_ereigpos_position_key "
        "ON ereignis_positionen(position_key)"
    )

    # Ebene-2-Cache: id als PK + UNIQUE INDEX ueber die logischen Schluessel
    # (SQLite verbietet Ausdruecke in PRIMARY KEY, laesst sie aber in
    # UNIQUE INDEX zu).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS position_ereignis_cache (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_az         TEXT NOT NULL,
            position_key    TEXT NOT NULL,
            ereignis_id     INTEGER NOT NULL,
            ereignistyp     TEXT NOT NULL,
            richtung        TEXT NOT NULL,
            datum           TEXT NOT NULL,
            dokument_id     INTEGER,
            wirkung         TEXT NOT NULL,
            betrag          REAL,
            kuerzungsart_id INTEGER,
            status          TEXT NOT NULL
                            CHECK (status IN ('aktuell','ersetzt'))
        )
    """)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uidx_pec_km1 "
        "ON position_ereignis_cache "
        "(akte_az, position_key, ereignis_id, wirkung, "
        " COALESCE(kuerzungsart_id, 0))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pec_akte_position "
        "ON position_ereignis_cache(akte_az, position_key)"
    )

    conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (51,
         "Migration 51 - P1.2 Ereignis-Datenmodell (ereignisse, "
         "ereignis_positionen mit K-M1 UNIQUE, position_ereignis_cache)"),
    )
    logger.info(
        "Migration 51 abgeschlossen (P1.2 Ereignis-Datenmodell)."
    )


def _run_migration_52(conn: sqlite3.Connection) -> None:
    """
    Migration 52 (P1.6) - todos.fristablauf_ereignis_id.

    Idempotenz-Anker fuer den Scheduler-Job (verarbeite_faellige_todos):
    jede todo-Zeile darf nur EIN fristablauf-Ereignis erzeugen. Der Job
    setzt beim Anlegen des Ereignisses die Referenz und filtert kuenftig
    ueber WHERE fristablauf_ereignis_id IS NULL.

    Additiv (ALTER TABLE ADD COLUMN, nullable), kein Datenverlust an
    bestehenden todos. Explizites commit() umgibt das ALTER (siehe
    feedback_migration_executescript.md).
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(todos)"
        ).fetchall()
    }
    if "fristablauf_ereignis_id" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE todos ADD COLUMN fristablauf_ereignis_id "
            "INTEGER REFERENCES ereignisse(id)"
        )
        conn.commit()

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_todos_fristablauf_pending "
        "ON todos (quelle, erledigt, faellig_am, fristablauf_ereignis_id)"
    )

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (52,
         "Migration 52 - P1.6 todos.fristablauf_ereignis_id "
         "(Idempotenz-Anker fuer Fristablauf-Scheduler)"),
    )
    logger.info(
        "Migration 52 abgeschlossen (P1.6 todos.fristablauf_ereignis_id)."
    )


def _run_migration_53(conn: sqlite3.Connection) -> None:
    """
    Migration 53 - intake_dokumente.verworfen_* fuer Verwerfen-Workflow.

    Drei additive Spalten:
      * verworfen_grund  TEXT NULL   Kurzschluessel (spam/duplikat/...)
      * verworfen_am     TEXT NULL   ISO-Timestamp
      * verworfen_von    INTEGER NULL FK -> benutzer.id (nicht erzwungen,
                                     SQLite ignoriert FKs standardmaessig)

    queue_status kennt nach dieser Migration den Wert 'verworfen'. Keine
    CHECK-Constraint auf queue_status -- die Spalte ist historisch TEXT
    ohne Enum, s. intake_dokumente-DDL. Idempotent per PRAGMA table_info.
    Explizites conn.commit() umgibt die ALTERs (feedback_migration_execute
    script.md).
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(intake_dokumente)"
        ).fetchall()
    }
    if "verworfen_grund" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE intake_dokumente ADD COLUMN verworfen_grund TEXT"
        )
        conn.commit()
    if "verworfen_am" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE intake_dokumente ADD COLUMN verworfen_am TEXT"
        )
        conn.commit()
    if "verworfen_von" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE intake_dokumente ADD COLUMN verworfen_von INTEGER"
        )
        conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (53,
         "Migration 53 - intake_dokumente.verworfen_grund/am/von "
         "(Verwerfen-Workflow in Review-Queue)"),
    )
    logger.info(
        "Migration 53 abgeschlossen (intake_dokumente Verwerfen-Felder)."
    )


def _run_migration_55(conn: sqlite3.Connection) -> None:
    """
    Migration 55 (N-08) - intake_dokumente.review_geoeffnet_am.

    Baseline "Sekunden pro Freigabe": haelt fest, wann ein Bearbeiter das
    Dokument in der Review-Queue zum ersten Mal geoeffnet hat. Bei der
    Freigabe wird daraus die Bearbeitungsdauer (Queue-Oeffnung -> Freigabe)
    als korrektur_log-Zeile berechnet -- Vorher-Baseline fuer die
    Stufe-2-Entscheidung (Bounding-Boxes/PDF.js, FREIGABE-NACHTRAG-1 N-08).

    Ein additiver ALTER TABLE, nullable, kein Datenverlust. Idempotent per
    PRAGMA table_info. Explizites conn.commit() umgibt das ALTER
    (feedback_migration_executescript).
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(intake_dokumente)"
        ).fetchall()
    }
    if "review_geoeffnet_am" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE intake_dokumente ADD COLUMN review_geoeffnet_am TEXT"
        )
        conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (55,
         "Migration 55 - intake_dokumente.review_geoeffnet_am "
         "(N-08 Baseline Sekunden pro Freigabe)"),
    )
    logger.info(
        "Migration 55 abgeschlossen (intake_dokumente.review_geoeffnet_am)."
    )


def _run_migration_54(conn: sqlite3.Connection) -> None:
    """
    Migration 54 - intake_dokumente.textquelle erlaubt 'email_text'.

    Der Text-Zweig der Pipeline (payload_typ='text') stempelt textquelle=
    'email_text' -- ein E-Mail-Body ist weder PDF-Textebene noch OCR. Der
    bestehende CHECK-Constraint IN ('textebene','ocr','gemischt') verbietet
    diesen Wert.

    SQLite kann einen CHECK-Constraint nicht per ALTER TABLE aendern. Ein
    Tabellen-Rebuild waere teuer und riskant (intake_dokumente traegt viele
    ueber Migrationen gewachsene Spalten und wird von zustellungen/freigaben
    referenziert). Daher wird der in sqlite_master gespeicherte DDL-Text
    gezielt umgeschrieben (writable_schema) -- KEINE Datenbewegung, es waechst
    ausschliesslich die erlaubte Werteliste des textquelle-CHECK.

    Idempotent: kein Umschreiben, wenn 'email_text' bereits im DDL steht.
    Fail-Loud: fehlt der erwartete CHECK-Ausdruck, Abbruch statt stiller No-Op.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name='intake_dokumente'"
    ).fetchone()
    ddl = row[0] if row else ""
    if not ddl:
        raise RuntimeError(
            "Migration 54: intake_dokumente-DDL nicht in sqlite_master gefunden"
        )

    if "email_text" not in ddl:
        alt = "textquelle IN ('textebene','ocr','gemischt')"
        neu = "textquelle IN ('textebene','ocr','gemischt','email_text')"
        if alt not in ddl:
            raise RuntimeError(
                "Migration 54: erwarteter textquelle-CHECK nicht im DDL "
                "gefunden -- Abbruch statt stiller No-Op"
            )
        neuer_ddl = ddl.replace(alt, neu)

        conn.commit()
        schema_ver = conn.execute("PRAGMA schema_version").fetchone()[0]
        conn.execute("PRAGMA writable_schema=ON")
        conn.execute(
            "UPDATE sqlite_master SET sql=? "
            "WHERE type='table' AND name='intake_dokumente'",
            (neuer_ddl,),
        )
        conn.execute(f"PRAGMA schema_version={schema_ver + 1}")
        conn.execute("PRAGMA writable_schema=OFF")
        conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (?, ?)",
        (54,
         "Migration 54 - intake_dokumente.textquelle erlaubt 'email_text' "
         "(Text-Pfad Intake-Pipeline)"),
    )
    logger.info(
        "Migration 54 abgeschlossen (textquelle erlaubt email_text)."
    )


def _run_migration_49(conn: sqlite3.Connection) -> None:
    """
    Migration 49 (S1.9a) - email_import_log.ausgeblendet Flag.

    Zustellungen (E-Mails im Import-Log) werden nie geloescht -- der
    frontseitige Loesch-Button wird zum Ausblenden-Toggle. Additiver
    ALTER TABLE, kein Datenverlust.

    Idempotent: ALTER TABLE nur wenn Spalte fehlt (PRAGMA table_info).
    Explizites conn.commit() umgibt das ALTER, damit der Effekt im
    aufrufenden Kontext sichtbar wird (feedback_migration_executescript).
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(email_import_log)"
        ).fetchall()
    }
    if "ausgeblendet" not in vorhandene_spalten:
        conn.commit()
        conn.execute(
            "ALTER TABLE email_import_log "
            "ADD COLUMN ausgeblendet INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_eil_ausgeblendet "
        "ON email_import_log(ausgeblendet)"
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (49, "Migration 49 - S1.9a email_import_log.ausgeblendet Flag "
             "(Zustellungen werden nie geloescht, nur ausgeblendet)"),
    )
    logger.info("Migration 49 abgeschlossen (email_import_log.ausgeblendet).")


def _run_migration_48(conn: sqlite3.Connection) -> None:
    """
    Migration 48 (S1.6a) - Queue-Felder auf intake_dokumente.

    Erweitert die Tabelle ``intake_dokumente`` um vier additive Spalten fuer
    die Verarbeitungs-Queue:

    * ``versuch_zaehler``   INTEGER NOT NULL DEFAULT 0
                            Anzahl bisheriger Verarbeitungsversuche.
    * ``naechster_versuch`` TEXT NULL
                            ISO-Timestamp — wenn NULL, ist der Eintrag sofort
                            faellig; sonst darf er erst danach reserviert werden
                            (Backoff 1/5/30 min bei Fehlversuchen).
    * ``fehler_detail``     TEXT NULL
                            Letzte Fehlermeldung; bleibt auch nach erneutem
                            Versuch bis zum naechsten Ergebnis stehen.
    * ``worker_lease``      TEXT NULL
                            "<worker_id>|<ablauf_iso>". Nur waehrend Status
                            ``laeuft`` gesetzt. F-10 (Single-Instance-Worker
                            in Gunicorn mit 4 Workern).

    Idempotent: ALTER TABLE nur wenn Spalte fehlt (PRAGMA table_info).
    Explizites conn.commit() umgibt das ALTER, damit der Effekt im
    aufrufenden Kontext sichtbar wird (feedback_migration_executescript).

    Rollback: Spalten bleiben ungenutzt; kein Datenverlust moeglich.
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(intake_dokumente)"
        ).fetchall()
    }

    neu = (
        ("versuch_zaehler",   "INTEGER NOT NULL DEFAULT 0"),
        ("naechster_versuch", "TEXT"),
        ("fehler_detail",     "TEXT"),
        ("worker_lease",      "TEXT"),
    )

    braucht_alter = any(name not in vorhandene_spalten for name, _ in neu)
    if braucht_alter:
        conn.commit()
        for name, typ in neu:
            if name in vorhandene_spalten:
                continue
            conn.execute(
                f"ALTER TABLE intake_dokumente ADD COLUMN {name} {typ}"
            )
        conn.commit()

    # Praktischer Index fuer die Worker-Abfrage: naechster faelliger Eintrag.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_intake_dok_faellig "
        "ON intake_dokumente(queue_status, naechster_versuch)"
    )

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (48, "Migration 48 - S1.6a Queue-Felder (versuch_zaehler + "
             "naechster_versuch + fehler_detail + worker_lease)"),
    )
    logger.info("Migration 48 abgeschlossen (Queue-Felder auf intake_dokumente).")


def _run_migration_47(conn: sqlite3.Connection) -> None:
    """
    Migration 47 (S1.4) - Absender-Registry-Grundgeruest.

    Erweitert die bestehende Tabelle ``email_absender_vorlagen`` um drei
    Spalten (additiv, nicht destruktiv):

    * ``vertrauensstufe``  INTEGER NOT NULL DEFAULT 1
                           0 = unbekannt, 1 = Standard-Seed,
                           2 = aus registry.json konsolidiert (bekannter
                               Versicherer/Gutachter), 3 = manuell verifiziert
                               (z.B. via SPF/DKIM).
    * ``klasse_kandidat``  TEXT (Wert aus registry.json.marker.<...>.klasse,
                           z.B. 'versicherung', 'gutachten'). Fuer die S1.6-
                           Kaskade ist das ein Signal, kein Routing.
    * ``ramicro_adressnr`` TEXT (aus dem gleichen Marker-Eintrag; nur bei
                           Gutachter-Markern belegt).

    Die eigentliche Uebernahme der registry.json-Daten uebernimmt das
    Skript ``backend/scripts/konsolidiere_absender_registry.py`` — es wird
    hier bewusst NICHT automatisch angestossen, damit die Migration nicht
    von einer Datei abhaengt, die sich im laufenden Betrieb aendert.

    Idempotent: ALTER TABLE nur wenn Spalte fehlt (SQLite-Trick via
    PRAGMA table_info). Explizites ``conn.commit()`` davor + danach, damit
    der ALTER-Effekt im aufrufenden Kontext sichtbar wird
    (siehe feedback_migration_executescript).

    Rollback: Spalten bleiben ungenutzt; kein Datenverlust moeglich.
    """
    vorhandene_spalten = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(email_absender_vorlagen)"
        ).fetchall()
    }

    neu = (
        ("vertrauensstufe", "INTEGER NOT NULL DEFAULT 1"),
        ("klasse_kandidat", "TEXT"),
        ("ramicro_adressnr", "TEXT"),
    )

    braucht_alter = any(name not in vorhandene_spalten for name, _ in neu)
    if braucht_alter:
        conn.commit()
        for name, typ in neu:
            if name in vorhandene_spalten:
                continue
            conn.execute(
                f"ALTER TABLE email_absender_vorlagen ADD COLUMN {name} {typ}"
            )
        conn.commit()

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (47, "Migration 47 - S1.4 Absender-Registry (vertrauensstufe + "
             "klasse_kandidat + ramicro_adressnr)"),
    )
    logger.info("Migration 47 abgeschlossen (Absender-Registry-Grundgeruest).")


def _run_migration_42(conn: sqlite3.Connection) -> None:
    """Korrigiert dateityp fuer .eml-Dateien: 'docx' -> 'sonstiges', dokumentenklasse -> 'email'."""
    conn.execute("""
        UPDATE dokumente
        SET dateityp = 'sonstiges',
            dokumentenklasse = 'email'
        WHERE dateiname LIKE '%.eml'
          AND dateityp = 'docx'
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (42, "Migration 42 – .eml dateityp sonstiges + dokumentenklasse email"),
    )
    logger.info("Migration 42: .eml-Zeilen korrigiert.")


def _run_migration_43(conn: sqlite3.Connection) -> None:
    """Erstellt imap_polling_config Tabelle mit 4 Account-Seed-Rows."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS imap_polling_config (
            account        TEXT PRIMARY KEY,
            aktiv          INTEGER NOT NULL DEFAULT 1,
            intervall_min  INTEGER NOT NULL DEFAULT 5,
            letzter_lauf   TEXT,
            letzter_status TEXT,
            letzter_fehler TEXT
        )
    """)
    for account in ("unfall", "termin", "bussgeld", "info"):
        conn.execute(
            "INSERT OR IGNORE INTO imap_polling_config (account, aktiv, intervall_min) VALUES (?, 1, 5)",
            (account,),
        )
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (43, "Migration 43 – imap_polling_config (US-02)"),
    )
    logger.info("Migration 43: imap_polling_config angelegt.")


def create_schema() -> None:
    """
    Führt das initiale DDL aus.
    Alle Statements sind idempotent (IF NOT EXISTS).
    """
    with get_connection() as conn:
        conn.executescript(SCHEMA_DDL)
    logger.info("Schema erfolgreich erstellt/aktualisiert: %s", get_db_path())


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Liest die aktuelle Schema-Version aus der Datenbank."""
    try:
        row = conn.execute(
            "SELECT MAX(version) as v FROM schema_version"
        ).fetchone()
        return row["v"] if row and row["v"] else 0
    except sqlite3.OperationalError:
        return 0  # Tabelle existiert noch nicht


def run_migrations() -> None:
    """
    Führt ausstehende Migrationen aus.
    Jede Migration wird in einer eigenen Transaktion ausgeführt.
    """
    with get_connection() as conn:
        current = get_schema_version(conn)
        pending = {v: sql for v, sql in MIGRATIONS.items() if v > current}

        if not pending:
            logger.info("Datenbank ist aktuell (Version %d).", current)
            return

        for version in sorted(pending):
            logger.info("Migration %d wird ausgeführt ...", version)
            if version == 4:
                # SQLite kennt kein ADD COLUMN IF NOT EXISTS → Python-Handler
                _run_migration_4(conn)
            elif version == 5:
                _run_migration_5(conn)
            elif version == 6:
                _run_migration_6(conn)
            elif version == 8:
                _run_migration_8(conn)
            elif version == 9:
                _run_migration_9(conn)
            elif version == 10:
                _run_migration_10(conn)
            elif version == 11:
                _run_migration_11(conn)
            elif version == 12:
                _run_migration_12(conn)
            elif version == 13:
                _run_migration_13(conn)
            elif version == 14:
                _run_migration_14(conn)
            elif version == 15:
                _run_migration_15(conn)
            elif version == 16:
                _run_migration_16(conn)
            elif version == 17:
                _run_migration_17(conn)
            elif version == 18:
                _run_migration_18(conn)
            elif version == 19:
                _run_migration_19(conn)
            elif version == 20:
                _run_migration_20(conn)
            elif version == 21:
                _run_migration_21(conn)
            elif version == 22:
                _run_migration_22(conn)
            elif version == 23:
                _run_migration_23(conn)
            elif version == 24:
                _run_migration_24(conn)
            elif version == 25:
                _run_migration_25(conn)
            elif version == 26:
                _run_migration_26(conn)
            elif version == 27:
                _run_migration_27(conn)
            elif version == 28:
                _run_migration_28(conn)
            elif version == 29:
                _run_migration_29(conn)
            elif version == 30:
                _run_migration_30(conn)
            elif version == 31:
                _run_migration_31(conn)
            elif version == 32:
                _run_migration_32(conn)
            elif version == 33:
                _run_migration_33(conn)
            elif version == 34:
                _run_migration_34(conn)
            elif version == 35:
                _run_migration_35(conn)
            elif version == 36:
                _run_migration_36(conn)
            elif version == 38:
                _run_migration_38(conn)
            elif version == 39:
                _run_migration_39(conn)
            elif version == 40:
                _run_migration_40(conn)
            elif version == 41:
                _run_migration_41(conn)
            elif version == 42:
                _run_migration_42(conn)
            elif version == 43:
                _run_migration_43(conn)
            elif version == 44:
                _run_migration_44(conn)
            elif version == 45:
                _run_migration_45(conn)
            elif version == 46:
                _run_migration_46(conn)
            elif version == 47:
                _run_migration_47(conn)
            elif version == 48:
                _run_migration_48(conn)
            elif version == 49:
                _run_migration_49(conn)
            elif version == 51:
                _run_migration_51(conn)
            elif version == 50:
                _run_migration_50(conn)
            elif version == 52:
                _run_migration_52(conn)
            elif version == 53:
                _run_migration_53(conn)
            elif version == 54:
                _run_migration_54(conn)
            elif version == 55:
                _run_migration_55(conn)
            else:
                conn.executescript(pending[version])
                conn.execute(
                    "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
                    (version, f"Migration {version}")
                )
            logger.info("Migration %d erfolgreich.", version)


def _run_migration_5(conn: sqlite3.Connection) -> None:
    """
    Migration 5: AZ als Primary Key.

    SQLite unterstützt kein ALTER TABLE zum Ändern des Primary Keys.
    Daher: Neue Tabellen anlegen → Daten migrieren → alte löschen → umbenennen.

    unfallakte.id (INTEGER PK AUTOINCREMENT) → unfallakte.az (TEXT PK)
    Alle akte_id INTEGER FK → akte_id TEXT FK

    Betroffene Tabellen: beteiligte, schadenpositionen, regulierung,
                         dokumente, aktivitaeten, email_import_log,
                         abrechnungsschreiben, regulierung_positionen, pruefberichte
    """
    # Prüfen ob unfallakte noch das alte Schema hat (id INTEGER PK)
    cols = [c[1] for c in conn.execute("PRAGMA table_info(unfallakte)").fetchall()]
    if "az" in cols and "id" not in cols:
        # Frische DB mit neuem Schema – Migration nicht nötig
        logger.info("Migration 5: Neues Schema bereits vorhanden – übersprungen.")
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (5, 'Migration 5 – AZ als PK (bereits aktuell)')"
        )
        return

    logger.info("Migration 5: Erstelle neue Tabellenstruktur mit AZ als PK ...")

    # ── 1. Neue unfallakte mit az als PK ──────────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS unfallakte_neu (
            az              TEXT    PRIMARY KEY,
            unfalldatum     TEXT    NOT NULL DEFAULT '',
            unfallort       TEXT,
            erstellt_am     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            geaendert_am    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            status          TEXT    NOT NULL DEFAULT 'offen'
                            CHECK(status IN ('offen','in_regulierung','klage','abgeschlossen')),
            bearbeiter_id   INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
            notizen         TEXT,
            haftungsquote   REAL    NOT NULL DEFAULT 100.0
                            CHECK(haftungsquote BETWEEN 0 AND 100),
            -- RA-Micro Stammdaten (gecacht)
            kurzbezeichnung TEXT,
            sachbearbeiter  TEXT
        );

        INSERT OR IGNORE INTO unfallakte_neu
            (az, unfalldatum, unfallort, erstellt_am, geaendert_am,
             status, bearbeiter_id, notizen, haftungsquote)
        SELECT aktenzeichen, unfalldatum, unfallort, erstellt_am, geaendert_am,
               status, bearbeiter_id, notizen, haftungsquote
        FROM unfallakte;
    """)

    # ── 2. Hilfsfunktion: Tabelle mit akte_id INTEGER → TEXT migrieren ────────
    def _migriere_fk_tabelle(tabelle: str, extra_cols_ddl: str, extra_cols_select: str):
        """Legt _neu-Variante an, migriert Daten, löscht alte, benennt um."""
        # Prüfen ob Tabelle existiert
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (tabelle,)
        ).fetchone()
        if not exists:
            return

        conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS {tabelle}_neu AS
                SELECT t.*, u.aktenzeichen AS az_key
                FROM {tabelle} t
                LEFT JOIN unfallakte u ON u.id = t.akte_id;
            DROP TABLE {tabelle}_neu;
        """)

        # Echte neue Tabelle erstellen und Daten migrieren
        # Wir lesen die Spaltennamen aus der alten Tabelle
        cols_info = conn.execute(f"PRAGMA table_info({tabelle})").fetchall()
        cols = [c[1] for c in cols_info if c[1] not in ("id", "akte_id")]
        cols_str = ", ".join(cols)

        conn.execute(f"""
            CREATE TABLE {tabelle}_new (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                akte_id     TEXT NOT NULL REFERENCES unfallakte_neu(az) ON DELETE CASCADE,
                {extra_cols_ddl}
                {(',' if cols else '')} {cols_str if cols else ''}
            )
        """)

    # Stattdessen einfacher: alle FK-Tabellen mit JOIN migrieren
    # ── 2. Views und Trigger zuerst droppen (referenzieren alte Tabellen) ─────
    conn.executescript("""
        DROP VIEW IF EXISTS v_schadensummen;
        DROP VIEW IF EXISTS v_regulierungsstatus;
        DROP TRIGGER IF EXISTS unfallakte_geaendert;
    """)

    fk_tabellen = [
        "beteiligte", "schadenpositionen", "regulierung",
        "dokumente", "aktivitaeten", "email_import_log",
        "abrechnungsschreiben", "regulierung_positionen", "pruefberichte",
    ]

    for tbl in fk_tabellen:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
        ).fetchone()
        if not exists:
            continue

        # Spalten ermitteln
        cols_info = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
        col_names = [c[1] for c in cols_info]

        # Nur Tabellen mit akte_id migrieren
        if "akte_id" not in col_names:
            logger.info("  Tabelle %s hat kein akte_id – übersprungen.", tbl)
            continue

        old_cols = [c for c in col_names if c != "akte_id"]

        # Da unfallakte_neu noch az-basiert ist, joinen wir auf die alte unfallakte
        # (die existiert noch unter unfallakte, unfallakte_neu ist die neue)
        conn.execute(f"ALTER TABLE {tbl} RENAME TO {tbl}_old")
        conn.execute(f"""
            CREATE TABLE {tbl} AS
            SELECT
                t.{', t.'.join(old_cols)},
                COALESCE(u.aktenzeichen, CAST(t.akte_id AS TEXT)) AS akte_id
            FROM {tbl}_old t
            LEFT JOIN unfallakte u ON CAST(u.id AS TEXT) = CAST(t.akte_id AS TEXT)
        """)
        conn.execute(f"DROP TABLE {tbl}_old")
        logger.info("  Tabelle %s migriert.", tbl)

    # ── 3. Views neu erstellen ─────────────────────────────────────────────────
    conn.executescript("""
        DROP TABLE IF EXISTS unfallakte;
        ALTER TABLE unfallakte_neu RENAME TO unfallakte;

        CREATE TRIGGER IF NOT EXISTS unfallakte_geaendert
            AFTER UPDATE ON unfallakte
            FOR EACH ROW
        BEGIN
            UPDATE unfallakte SET geaendert_am = datetime('now','localtime')
            WHERE az = OLD.az;
        END;

        CREATE VIEW IF NOT EXISTS v_schadensummen AS
        SELECT
            akte_id,
            reparaturkosten, wiederbeschaffung, restwert, wertminderung,
            nutzungsausfall, mietwagenkosten, sv_kosten, abschleppkosten,
            standkosten, anabmeldekosten, schmerzensgeld, sonstiges,
            (reparaturkosten + wiederbeschaffung - restwert + wertminderung)
                AS fahrzeugschaden_netto,
            (reparaturkosten + wiederbeschaffung - restwert + wertminderung
             + nutzungsausfall + mietwagenkosten + sv_kosten + abschleppkosten
             + standkosten + anabmeldekosten + schmerzensgeld + sonstiges)
                AS gesamt_brutto,
            quelle, erfasst_am
        FROM schadenpositionen;

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

        INSERT OR IGNORE INTO schema_version (version, beschreibung)
        VALUES (5, 'Migration 5 – AZ als Primary Key, RA-Micro Integration');
    """)
    logger.info("Migration 5 abgeschlossen.")


def _run_migration_6(conn: sqlite3.Connection) -> None:
    """
    Migration 6: Neue Schadenfelder aus WDM-Mapping.
    Ergänzt schadenpositionen um verdienstausfall und haushalt.
    """
    neue_spalten = [
        ("verdienstausfall", "REAL NOT NULL DEFAULT 0.0"),
        ("haushalt",         "REAL NOT NULL DEFAULT 0.0"),
        ("rep_fiktiv_netto", "REAL NOT NULL DEFAULT 0.0"),   # varREPKOSTENSV
        ("rep_fiktiv_mwst",  "REAL NOT NULL DEFAULT 0.0"),   # varUST-REPKOSTENSV
        ("unkostenpauschale","REAL NOT NULL DEFAULT 0.0"),    # varUNKOSTEN
        ("wdm_extras_json",  "TEXT"),                          # varSSCHADEN1-6 als JSON
        ("wdm_info_json",    "TEXT"),                          # varFKLASSE, varREPDAUER etc.
    ]
    for spalte, typ in neue_spalten:
        try:
            conn.execute(f"ALTER TABLE schadenpositionen ADD COLUMN {spalte} {typ}")
            logger.info("Migration 6: Spalte %s hinzugefügt.", spalte)
        except Exception:
            pass  # Spalte existiert bereits

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (6, 'Migration 6 – WDM-Schadenfelder')"
    )
    logger.info("Migration 6 abgeschlossen.")


def check_schema() -> dict:
    """
    Prüft ob alle erwarteten Tabellen und Views vorhanden sind.
    Gibt einen Status-Dict zurück.
    """
    expected_tables = [
        "benutzer", "unfallakte", "beteiligte",
        "schadenpositionen", "regulierung", "dokumente",
        "aktivitaeten", "schema_version",
        "kuerzungsarten", "abrechnungsschreiben",
        "regulierung_positionen", "pruefberichte",
    ]
    expected_views = [
        "v_schadensummen", "v_regulierungsstatus"
    ]

    result = {"ok": True, "tabellen": {}, "views": {}, "version": 0}

    try:
        with get_connection() as conn:
            result["version"] = get_schema_version(conn)

            # Tabellen prüfen
            for tbl in expected_tables:
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (tbl,)
                ).fetchone()
                result["tabellen"][tbl] = bool(exists)
                if not exists:
                    result["ok"] = False

            # Views prüfen
            for view in expected_views:
                exists = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='view' AND name=?",
                    (view,)
                ).fetchone()
                result["views"][view] = bool(exists)
                if not exists:
                    result["ok"] = False

    except Exception as e:
        result["ok"] = False
        result["fehler"] = str(e)

    return result


def reset_database() -> None:
    """
    VORSICHT: Löscht alle Tabellen und erstellt das Schema neu.
    Nur für Entwicklung/Tests verwenden!
    """
    import os
    db_path = get_db_path()
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.warning("Datenbank gelöscht: %s", db_path)
    init_db()   # create_schema() + run_migrations() → alle Felder korrekt
    logger.info("Datenbank neu erstellt.")


def _run_migration_8(conn: sqlite3.Connection) -> None:
    """
    Migration 8: Felder für das vorlagen-basierte Forderungsschreiben.

    beteiligte:
      anrede   TEXT  – sAnrede aus RA-Micro (Herrn / Frau / Firma)
      vorsteuer TEXT DEFAULT 'N' – Vorsteuerabzugsberechtigung (J/N)

    schadenpositionen:
      kostennb     REAL DEFAULT 0.0 – Nachbesichtigungskosten (netto)
      kostennb_ust REAL DEFAULT 0.0 – MwSt auf Nachbesichtigung
    """
    neue_beteiligte = [
        ("anrede",    "TEXT"),
        ("vorsteuer", "TEXT NOT NULL DEFAULT 'N'"),
    ]
    neue_schaden = [
        ("kostennb",     "REAL NOT NULL DEFAULT 0.0"),
        ("kostennb_ust", "REAL NOT NULL DEFAULT 0.0"),
    ]
    for tabelle, spalten in [
        ("beteiligte",       neue_beteiligte),
        ("schadenpositionen", neue_schaden),
    ]:
        for spalte, typ in spalten:
            try:
                conn.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {typ}")
                logger.info("Migration 8: %s.%s hinzugefügt.", tabelle, spalte)
            except Exception:
                pass  # Spalte existiert bereits
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (8, 'Migration 8 – Forderungsschreiben: Anrede, Vorsteuer, Nachbesichtigung')"
    )
    logger.info("Migration 8 abgeschlossen.")


def _run_migration_9(conn: sqlite3.Connection) -> None:
    """
    Migration 9: Forderungshistorie pro Schadenposition und Forderungsschreiben.

    forderung_positionen trackt welche Positionen mit welchem Schreiben wann
    gefordert wurden und ihren aktuellen Regulierungsstatus.

    So kann ein zweites Forderungsschreiben gezielt nur noch offene Positionen
    enthalten, und die Klage wird aus 'gekuerzt'/'abgelehnt'-Positionen gebaut.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS forderung_positionen (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id             TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,

            -- Verknüpfung zum generierten Dokument
            dokument_id         INTEGER REFERENCES dokumente(id) ON DELETE SET NULL,
            forderungsschreiben_nr  INTEGER NOT NULL DEFAULT 1,  -- 1, 2, 3 ...
            datum               TEXT    NOT NULL
                                DEFAULT (date('now', 'localtime')),

            -- Schadenposition
            position_key        TEXT    NOT NULL,
            -- position_key: Spaltenname aus schadenpositionen
            -- ODER 'extra_1'..'extra_6' für sonstige Schäden (wdm_extras_json)
            position_label      TEXT    NOT NULL,  -- Lesbare Bezeichnung für Dokument
            betrag_gefordert    REAL    NOT NULL DEFAULT 0.0,

            -- Regulierungsstatus (wird aktualisiert wenn Abrechnung eingeht)
            betrag_reguliert    REAL    NOT NULL DEFAULT 0.0,
            status              TEXT    NOT NULL DEFAULT 'gefordert'
                                CHECK(status IN (
                                    'gefordert',      -- noch keine Antwort
                                    'teilreguliert',  -- teilweise bezahlt
                                    'vollreguliert',  -- vollständig bezahlt
                                    'gekuerzt',       -- Versicherung hat gekürzt
                                    'abgelehnt'       -- vollständig abgelehnt
                                )),

            -- Klage-Vorbereitung
            fuer_klage          INTEGER NOT NULL DEFAULT 0
                                CHECK(fuer_klage IN (0,1)),
            kuerzungsart_id     INTEGER REFERENCES kuerzungsarten(id) ON DELETE SET NULL,
            kuerzung_begruendung TEXT,  -- Freitext-Begründung der Kürzung

            -- Metadaten
            erfasst_am          TEXT    NOT NULL
                                DEFAULT (datetime('now', 'localtime')),
            erfasst_von         INTEGER REFERENCES benutzer(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_fordpos_akte_id
            ON forderung_positionen(akte_id);
        CREATE INDEX IF NOT EXISTS idx_fordpos_status
            ON forderung_positionen(status);
        CREATE INDEX IF NOT EXISTS idx_fordpos_klage
            ON forderung_positionen(fuer_klage);
        CREATE INDEX IF NOT EXISTS idx_fordpos_dokument
            ON forderung_positionen(dokument_id);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (9, 'Migration 9 – Forderungshistorie pro Position (forderung_positionen)')"
    )
    logger.info("Migration 9 abgeschlossen.")


def _run_migration_11(conn: sqlite3.Connection) -> None:
    """
    Migration 11: aktivitaeten.id PRIMARY KEY reparieren.

    Migration 5 hat aktivitaeten per CREATE TABLE AS SELECT neu erstellt.
    Dabei gingen alle Constraints verloren — id war kein PRIMARY KEY mehr,
    was lastrowid-basierte SELECTs nach INSERT zum Scheitern brachte (500er).
    """
    cols_info = conn.execute("PRAGMA table_info(aktivitaeten)").fetchall()
    id_col = next((c for c in cols_info if c[1] == "id"), None)
    # pk=0 bedeutet kein Primary Key
    if id_col and id_col[5] == 1:
        logger.info("Migration 11: aktivitaeten.id ist bereits PRIMARY KEY — übersprungen.")
        conn.execute("INSERT OR IGNORE INTO schema_version (version, beschreibung) "
                     "VALUES (11, 'Migration 11 – aktivitaeten PK bereits OK')")
        return

    logger.info("Migration 11: Repariere aktivitaeten PRIMARY KEY ...")
    conn.executescript("""
        CREATE TABLE aktivitaeten_m11 (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id      TEXT    REFERENCES unfallakte(az) ON DELETE CASCADE,
            benutzer_id  INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
            zeitstempel  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            aktion       TEXT    NOT NULL,
            beschreibung TEXT    NOT NULL DEFAULT '',
            tabelle      TEXT,
            datensatz_id INTEGER,
            aenderung_json TEXT
        );
        INSERT INTO aktivitaeten_m11
            (akte_id, benutzer_id, zeitstempel, aktion, beschreibung,
             tabelle, datensatz_id, aenderung_json)
        SELECT
            akte_id, benutzer_id,
            COALESCE(zeitstempel, datetime('now','localtime')),
            aktion, COALESCE(beschreibung,''),
            tabelle, datensatz_id, aenderung_json
        FROM aktivitaeten
        WHERE aktion IS NOT NULL;
        DROP TABLE aktivitaeten;
        ALTER TABLE aktivitaeten_m11 RENAME TO aktivitaeten;
    """)
    conn.execute("INSERT OR IGNORE INTO schema_version (version, beschreibung) "
                 "VALUES (11, 'Migration 11 – aktivitaeten PRIMARY KEY repariert')")
    logger.info("Migration 11 abgeschlossen.")


def _run_migration_10(conn: sqlite3.Connection) -> None:
    """
    Migration 10: Feldnamen-Harmonisierung Schadenpositionen.

    rep_fiktiv_netto → rep_gutachten_netto  (konsistent mit Frontend/WDM-Endpunkt)
    rep_fiktiv_mwst  → rep_gutachten_mwst
    + rep_rechnung_netto  REAL DEFAULT 0.0  (neu, lt. Werkstattrechnung netto)
    + rep_rechnung_brutto REAL DEFAULT 0.0  (neu, lt. Werkstattrechnung brutto)
    """
    # SQLite ≥ 3.25 unterstützt RENAME COLUMN
    renames = [
        ("rep_fiktiv_netto", "rep_gutachten_netto"),
        ("rep_fiktiv_mwst",  "rep_gutachten_mwst"),
    ]
    cols = [c[1] for c in conn.execute(
        "PRAGMA table_info(schadenpositionen)").fetchall()]

    for old, new in renames:
        if old in cols and new not in cols:
            conn.execute(
                f"ALTER TABLE schadenpositionen RENAME COLUMN {old} TO {new}"
            )
            logger.info("Migration 10: %s → %s umbenannt.", old, new)
        elif new in cols:
            logger.info("Migration 10: %s bereits vorhanden.", new)

    for spalte, typ in [
        ("rep_rechnung_netto",  "REAL NOT NULL DEFAULT 0.0"),
        ("rep_rechnung_brutto", "REAL NOT NULL DEFAULT 0.0"),
    ]:
        if spalte not in cols:
            conn.execute(
                f"ALTER TABLE schadenpositionen ADD COLUMN {spalte} {typ}"
            )
            logger.info("Migration 10: Spalte %s hinzugefügt.", spalte)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (10, 'Migration 10 – Feldnamen rep_fiktiv_* → rep_gutachten_*, rep_rechnung_*')"
    )
    logger.info("Migration 10 abgeschlossen.")


def _run_migration_15(conn: sqlite3.Connection) -> None:
    """
    Migration 15: Neue Tabelle personenschaden_beteiligte.

    Speichert Beteiligte der Heilbehandlung (Ärzte, Krankenhaus, etc.)
    als Adressnummern-Referenzen auf tblAdressen in RA-Micro.
    Adressdaten werden immer live aus RA-Micro geladen (nur-lesend).

    Datenquellen-Hierarchie:
      quelle='manuell' → hat Vorrang, manuell erfasst/bestätigt
      quelle='wdm'     → automatisch aus WDM-Variablen geladen
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS personenschaden_beteiligte (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id     TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,
            adressnr    INTEGER NOT NULL,
            rolle       TEXT    NOT NULL
                        CHECK(rolle IN ('arzt','krankenhaus','physiotherapeut',
                                        'arbeitgeber','krankenkasse','bg')),
            sortierung  INTEGER NOT NULL DEFAULT 0,
            quelle      TEXT    NOT NULL DEFAULT 'manuell'
                        CHECK(quelle IN ('wdm','manuell')),
            notizen     TEXT,
            erfasst_am  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(akte_id, adressnr, rolle)
        );
        CREATE INDEX IF NOT EXISTS idx_ps_bet_akte_id
            ON personenschaden_beteiligte(akte_id);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (15, 'Migration 15 – Tabelle personenschaden_beteiligte')"
    )
    logger.info("Migration 15: Tabelle personenschaden_beteiligte angelegt.")


def _run_migration_14(conn: sqlite3.Connection) -> None:
    """
    Migration 14: Netto + USt-Felder für alle MwSt-pflichtigen Nebenkosten.

    Bisher speicherten sv_kosten, abschleppkosten, standkosten, anabmeldekosten
    und mietwagenkosten nur einen einzigen Bruttobetrag. Das ist für
    Vorsteuerabzugsberechtigte falsch (müsste Netto sein).

    Neue Felder je Position:
      sv_kosten_netto        sv_kosten_ust
      abschleppkosten_netto  abschleppkosten_ust
      standkosten_netto      standkosten_ust
      anabmeldekosten_netto  anabmeldekosten_ust
      mietwagenkosten_netto  mietwagenkosten_ust

    Die alten Felder bleiben als Brutto-Fallback erhalten.
    """
    neue_spalten = [
        ("sv_kosten_netto",        "REAL NOT NULL DEFAULT 0.0"),
        ("sv_kosten_ust",          "REAL NOT NULL DEFAULT 0.0"),
        ("abschleppkosten_netto",  "REAL NOT NULL DEFAULT 0.0"),
        ("abschleppkosten_ust",    "REAL NOT NULL DEFAULT 0.0"),
        ("standkosten_netto",      "REAL NOT NULL DEFAULT 0.0"),
        ("standkosten_ust",        "REAL NOT NULL DEFAULT 0.0"),
        ("anabmeldekosten_netto",  "REAL NOT NULL DEFAULT 0.0"),
        ("anabmeldekosten_ust",    "REAL NOT NULL DEFAULT 0.0"),
        ("mietwagenkosten_netto",  "REAL NOT NULL DEFAULT 0.0"),
        ("mietwagenkosten_ust",    "REAL NOT NULL DEFAULT 0.0"),
    ]
    vorhandene = {row[1] for row in conn.execute(
        "PRAGMA table_info(schadenpositionen)").fetchall()}
    for spalte, typ in neue_spalten:
        if spalte not in vorhandene:
            conn.execute(f"ALTER TABLE schadenpositionen ADD COLUMN {spalte} {typ}")
            logger.info("Migration 14: Spalte %s hinzugefügt.", spalte)
        else:
            logger.info("Migration 14: %s bereits vorhanden.", spalte)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (14, 'Migration 14 – Netto/USt-Felder für Nebenkosten')"
    )
    logger.info("Migration 14 abgeschlossen.")


def _run_migration_12(conn: sqlite3.Connection) -> None:
    """
    Migration 12: abrechnungsart in schadenpositionen.

    Neues Feld: abrechnungsart TEXT DEFAULT 'fiktiv'
    Erlaubte Werte: 'fiktiv' | 'konkret' | 'totalschaden'
    - fiktiv:      Abrechnung auf Gutachtenbasis (rep_gutachten_netto), netto
    - konkret:     Abrechnung lt. Werkstattrechnung (rep_rechnung_netto); 130%-Fall ist Unterfall
    - totalschaden: WBW − Restwert, kein Reparaturweg

    Das Feld wird bewusst leer (NULL) gelassen wenn noch nicht gesetzt,
    damit der Sachbearbeiter es explizit auswählt.
    """
    cols = [c[1] for c in conn.execute(
        "PRAGMA table_info(schadenpositionen)").fetchall()]

    if "abrechnungsart" not in cols:
        conn.execute("""
            ALTER TABLE schadenpositionen
            ADD COLUMN abrechnungsart TEXT
            CHECK(abrechnungsart IN ('fiktiv', 'konkret', 'totalschaden'))
        """)
        logger.info("Migration 12: Spalte schadenpositionen.abrechnungsart hinzugefügt.")
    else:
        logger.info("Migration 12: abrechnungsart bereits vorhanden – übersprungen.")

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (12, 'Migration 12 – abrechnungsart in schadenpositionen')"
    )
    logger.info("Migration 12 abgeschlossen.")


def _run_migration_13(conn: sqlite3.Connection) -> None:
    """
    Migration 13: Neue Tabelle personenschaden.

    1:1 zur Akte (FK auf unfallakte.az).
    Enthält alle Felder aus dem RA-Micro VU-Fragebogen Blatt 2 (Personenschäden),
    ergänzt um interne Felder für den Heilbehandlungsverlauf und die spätere Klageschrift.

    Datenquelle-Priorität beim Lesen:
      1. RA-Micro WDM-Variablen (varV-KHADR.NName, varVERLETZUNG1/2, etc.)
      2. SQLite (dieses Modell) als manuell erfasster Fallback / Ergänzung

    Ärzte werden als JSON-Array in ambulante_aerzte_json gespeichert:
      [{"name": "...", "strasse": "...", "ort": "...", "telefon": "..."}]
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS personenschaden (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id                     TEXT    NOT NULL UNIQUE
                                        REFERENCES unfallakte(az) ON DELETE CASCADE,

            -- Verletzte Person (i.d.R. identisch mit Mandant, aber explizit gespeichert)
            verletzter_name             TEXT,
            verletzter_vorname          TEXT,
            geburtsdatum                TEXT,           -- ISO: YYYY-MM-DD
            familienstand               TEXT,           -- ledig/verheiratet/geschieden/verwitwet/sonstiges
            kinder_anzahl               INTEGER,
            kinder_alter_text           TEXT,           -- Freitext z.B. "11, 10, 6"

            -- Beruf & Einkommen
            beruf                       TEXT,
            selbststaendig              INTEGER NOT NULL DEFAULT 0
                                        CHECK(selbststaendig IN (0,1)),
            nettoeinkommen_monatlich    REAL,
            arbeitgeber_name            TEXT,
            arbeitgeber_anschrift       TEXT,
            arbeitgeber_telefon         TEXT,
            rente_vor_unfall            INTEGER NOT NULL DEFAULT 0
                                        CHECK(rente_vor_unfall IN (0,1)),
            rente_betrag_monatlich      REAL,

            -- Verletzungen
            verletzungen_text           TEXT,           -- Freitext Diagnosen (varVERLETZUNG1+2)

            -- Krankenhausaufenthalt
            krankenhaus_name            TEXT,           -- varV-KHADR.NName
            krankenhaus_anschrift       TEXT,
            krankenhaus_von             TEXT,           -- varV-KHVON (ISO oder TT.MM.JJJJ)
            krankenhaus_bis             TEXT,           -- varV-KHBIS (voraussichtlich)

            -- Ambulante Ärzte (JSON-Array)
            -- [{"name": "...", "strasse": "...", "ort": "...", "telefon": "..."}]
            ambulante_aerzte_json       TEXT,

            -- Krankschreibung
            krankenhaus_aufenthalt      INTEGER NOT NULL DEFAULT 0
                                        CHECK(krankenhaus_aufenthalt IN (0,1)),
            krankgeschrieben            INTEGER NOT NULL DEFAULT 0
                                        CHECK(krankgeschrieben IN (0,1)),
            krank_von                   TEXT,           -- varV-KRVON
            krank_bis                   TEXT,           -- varV-KRBIS (voraussichtlich)

            -- Versicherung & BG
            krankenkasse_name           TEXT,
            krankenkasse_anschrift      TEXT,
            berufsunfall                INTEGER NOT NULL DEFAULT 0
                                        CHECK(berufsunfall IN (0,1)),
            bg_name                     TEXT,           -- Berufsgenossenschaft
            rentenversichert            INTEGER NOT NULL DEFAULT 0
                                        CHECK(rentenversichert IN (0,1)),
            rentenversicherung_name     TEXT,

            -- Schweigepflicht & Heilbehandlung
            schweigepflicht_entbindung  INTEGER NOT NULL DEFAULT 0
                                        CHECK(schweigepflicht_entbindung IN (0,1)),
            heilbehandlung_abgeschlossen INTEGER NOT NULL DEFAULT 0
                                        CHECK(heilbehandlung_abgeschlossen IN (0,1)),
            heilbehandlung_ende         TEXT,           -- ISO: YYYY-MM-DD

            -- Dauerfolgen
            dauerfolgen                 INTEGER NOT NULL DEFAULT 0
                                        CHECK(dauerfolgen IN (0,1)),
            dauerfolgen_text            TEXT,

            -- Physiotherapie (für Fahrtkosten-Berechnung spätere Klage)
            physiotherapie              INTEGER NOT NULL DEFAULT 0
                                        CHECK(physiotherapie IN (0,1)),
            physiotherapeut_name        TEXT,
            physiotherapeut_anschrift   TEXT,
            physiotherapie_anzahl       INTEGER,        -- Anzahl Sitzungen

            -- Sonstiges
            notizen                     TEXT,
            erfasst_am                  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            erfasst_von                 INTEGER REFERENCES benutzer(id) ON DELETE SET NULL,
            geaendert_am                TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_personenschaden_akte_id
            ON personenschaden(akte_id);
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (13, 'Migration 13 – Neue Tabelle personenschaden')"
    )
    logger.info("Migration 13: Tabelle personenschaden angelegt.")



def _run_migration_16(conn: sqlite3.Connection) -> None:
    """
    Migration 16: Manuelle Regulierungserfassung + WDM-Fallback.

    abrechnungsschreiben:
      + quelle         TEXT DEFAULT 'pdf'   →  'pdf' | 'manuell' | 'wdm'
      + wdm_importiert INTEGER DEFAULT 0    →  verhindert Doppel-Import

    regulierung_positionen:
      + position_label TEXT                 →  Freitext-Label für Sonstiges

    Die CHECK-Constraint auf position_key in regulierung_positionen wird
    erweitert (neue Keys: rep_gutachten_netto, rep_rechnung_netto,
    rep_rechnung_brutto, verdienstausfall, haushalt, unkostenpauschale,
    kostennb, vorschuss, sonstiges_wdm_1–6).
    Da SQLite keine CHECK-Constraint-Änderung via ALTER TABLE erlaubt,
    wird die Tabelle neu erstellt.
    """
    # ── 1. Neue Spalten in abrechnungsschreiben ──────────────────────────
    ab_cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(abrechnungsschreiben)").fetchall()}

    for spalte, typ in [
        ("quelle",         "TEXT NOT NULL DEFAULT 'pdf'"),
        ("gesamt_kuerzung","REAL NOT NULL DEFAULT 0.0"),
        ("wdm_importiert", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        if spalte not in ab_cols:
            conn.execute(
                f"ALTER TABLE abrechnungsschreiben ADD COLUMN {spalte} {typ}"
            )
            logger.info("Migration 16: abrechnungsschreiben.%s hinzugefügt.", spalte)

    # ── 2. Neue Spalte position_label in regulierung_positionen ─────────
    rp_cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(regulierung_positionen)").fetchall()}

    if "position_label" not in rp_cols:
        conn.execute(
            "ALTER TABLE regulierung_positionen ADD COLUMN position_label TEXT"
        )
        logger.info("Migration 16: regulierung_positionen.position_label hinzugefügt.")

    # ── 3. CHECK-Constraint auf position_key erweitern ───────────────────
    # SQLite kann CHECK-Constraints nicht nachträglich ändern.
    # Tabelle neu erstellen ohne CHECK (Validierung läuft über Python).
    # Nur durchführen wenn CHECK noch die alte Liste hat.
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' "
        "AND name='regulierung_positionen'"
    ).fetchone()
    if ddl and "'rep_gutachten_netto'" not in (ddl[0] or ""):
        logger.info("Migration 16: Erweitere CHECK-Constraint in regulierung_positionen ...")
        # Foreign-Keys temporär deaktivieren (executescript committet implizit)
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS regulierung_positionen_m16 (
                id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                abrechnungsschreiben_id     INTEGER NOT NULL,
                position_key                TEXT    NOT NULL,
                position_label              TEXT,
                betrag_gefordert            REAL    NOT NULL DEFAULT 0.0,
                betrag_reguliert            REAL    NOT NULL DEFAULT 0.0,
                kuerzungsart_id             INTEGER,
                kuerzung_freitext           TEXT,
                parser_erkannt              INTEGER NOT NULL DEFAULT 0
                                            CHECK(parser_erkannt IN (0,1)),
                parser_konfidenz            REAL,
                fuer_klage_vorgemerkt       INTEGER NOT NULL DEFAULT 0
                                            CHECK(fuer_klage_vorgemerkt IN (0,1)),
                sv_stellungnahme_ausstehend INTEGER NOT NULL DEFAULT 0
                                            CHECK(sv_stellungnahme_ausstehend IN (0,1))
            );

            INSERT INTO regulierung_positionen_m16
                (id, abrechnungsschreiben_id, position_key, position_label,
                 betrag_gefordert, betrag_reguliert,
                 kuerzungsart_id, kuerzung_freitext,
                 parser_erkannt, parser_konfidenz,
                 fuer_klage_vorgemerkt, sv_stellungnahme_ausstehend)
            SELECT
                id, abrechnungsschreiben_id, position_key, NULL,
                betrag_gefordert, betrag_reguliert,
                kuerzungsart_id, kuerzung_freitext,
                parser_erkannt, parser_konfidenz,
                fuer_klage_vorgemerkt, sv_stellungnahme_ausstehend
            FROM regulierung_positionen;

            DROP TABLE regulierung_positionen;
            ALTER TABLE regulierung_positionen_m16 RENAME TO regulierung_positionen;

            CREATE INDEX IF NOT EXISTS idx_regpos_abrechnung_id
                ON regulierung_positionen(abrechnungsschreiben_id);
            CREATE INDEX IF NOT EXISTS idx_regpos_klage
                ON regulierung_positionen(fuer_klage_vorgemerkt);
        """)
        conn.execute("PRAGMA foreign_keys = ON")
        logger.info("Migration 16: regulierung_positionen ohne CHECK-Constraint neu erstellt.")
    else:
        logger.info("Migration 16: CHECK-Constraint bereits aktuell – übersprungen.")

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (16, 'Migration 16 – Manuelle Regulierung, WDM-Fallback')"
    )
    logger.info("Migration 16 abgeschlossen.")



def _run_migration_17(conn: sqlite3.Connection) -> None:
    """
    Migration 17: email_import_log modernisieren.

    Aenderungen:
      - akte_id:    INTEGER REFERENCES unfallakte(id)
                 -> TEXT    REFERENCES unfallakte(az)
      - status CHECK: ('verarbeitet','kein_treffer','fehler','ignoriert')
                 -> ('zugeordnet','nicht_zugeordnet','fehler','ignoriert')
      - NEU erkannt_az         TEXT
      - NEU erkannt_kfz        TEXT
      - NEU match_methode      TEXT
      - NEU von_name           TEXT
      - NEU manuell_zugeordnet INTEGER DEFAULT 0

    Bestehende Daten:
      'verarbeitet'  -> 'zugeordnet'
      'kein_treffer' -> 'nicht_zugeordnet'
    """
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(email_import_log)").fetchall()}

    if "erkannt_az" in cols and "manuell_zugeordnet" in cols:
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
            "VALUES (17, 'Migration 17 - email_import_log v2 (bereits aktuell)')"
        )
        logger.info("Migration 17: email_import_log bereits aktuell - uebersprungen.")
        return

    logger.info("Migration 17: Erstelle email_import_log neu ...")

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS email_import_log_m17 (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id          TEXT    NOT NULL UNIQUE,
            betreff             TEXT,
            absender            TEXT,
            von_name            TEXT,
            empfangen_am        TEXT,
            importiert_am       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            akte_id             TEXT    REFERENCES unfallakte(az) ON DELETE SET NULL,
            status              TEXT    NOT NULL DEFAULT 'nicht_zugeordnet'
                                CHECK(status IN (
                                    'zugeordnet', 'nicht_zugeordnet',
                                    'fehler', 'ignoriert'
                                )),
            erkannt_az          TEXT,
            erkannt_kfz         TEXT,
            match_methode       TEXT,
            manuell_zugeordnet  INTEGER NOT NULL DEFAULT 0,
            anhaenge_anzahl     INTEGER DEFAULT 0,
            importierte_dok     TEXT,
            notizen             TEXT
        );

        INSERT INTO email_import_log_m17 (
            id, message_id, betreff, absender, empfangen_am, importiert_am,
            akte_id, status, anhaenge_anzahl, importierte_dok, notizen
        )
        SELECT
            id, message_id, betreff, absender, empfangen_am, importiert_am,
            CAST(akte_id AS TEXT),
            CASE status
                WHEN 'verarbeitet'  THEN 'zugeordnet'
                WHEN 'kein_treffer' THEN 'nicht_zugeordnet'
                ELSE status
            END,
            anhaenge_anzahl, importierte_dok, notizen
        FROM email_import_log;

        DROP TABLE email_import_log;
        ALTER TABLE email_import_log_m17 RENAME TO email_import_log;

        CREATE INDEX IF NOT EXISTS idx_email_log_akte_id
            ON email_import_log(akte_id);
        CREATE INDEX IF NOT EXISTS idx_email_log_status
            ON email_import_log(status);
        CREATE INDEX IF NOT EXISTS idx_email_log_importiert_am
            ON email_import_log(importiert_am DESC);
    """)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (17, 'Migration 17 - email_import_log v2: TEXT FK, neue Felder')"
    )
    logger.info("Migration 17 abgeschlossen.")


def _run_migration_18(conn: sqlite3.Connection) -> None:
    """
    Migration 18: E-Mail-Import Erweiterungen.

    email_import_log bekommt:
      + in_akte_importiert      INTEGER DEFAULT 0
      + in_akte_importiert_am   TEXT
      + absender_kategorie      TEXT  (aus email_absender_vorlagen)
      + eml_pfad               TEXT  (Pfad zur gespeicherten .eml-Datei)

    Neue Tabelle email_absender_vorlagen:
      Ordnet E-Mail-Domains einer Kategorie zu
      (gutachter, versicherung, gericht, sonstiges)
    """
    # Bereits migriert?
    cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(email_import_log)").fetchall()}
    if "in_akte_importiert" in cols:
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
            "VALUES (18, 'Migration 18 - bereits aktuell')"
        )
        logger.info("Migration 18: bereits aktuell - uebersprungen.")
        return

    logger.info("Migration 18: Felder + Tabelle anlegen ...")

    # Neue Spalten in email_import_log
    for spalte, typ in [
        ("in_akte_importiert",   "INTEGER NOT NULL DEFAULT 0"),
        ("in_akte_importiert_am","TEXT"),
        ("absender_kategorie",   "TEXT"),
        ("eml_pfad",             "TEXT"),
    ]:
        if spalte not in cols:
            conn.execute(
                f"ALTER TABLE email_import_log ADD COLUMN {spalte} {typ}"
            )
            logger.info("Migration 18: email_import_log.%s hinzugefuegt.", spalte)

    # Neue Tabelle email_absender_vorlagen
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS email_absender_vorlagen (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            domain      TEXT    NOT NULL UNIQUE,
            kategorie   TEXT    NOT NULL DEFAULT 'sonstiges'
                        CHECK(kategorie IN (
                            'gutachter', 'versicherung', 'gericht', 'sonstiges'
                        )),
            notizen     TEXT,
            aktiv       INTEGER NOT NULL DEFAULT 1,
            erstellt_am TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_absender_vorlagen_domain
            ON email_absender_vorlagen(domain);
    """)
    logger.info("Migration 18: email_absender_vorlagen erstellt.")

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (18, 'Migration 18 - in_akte_importiert + email_absender_vorlagen')"
    )
    logger.info("Migration 18 abgeschlossen.")


def _run_migration_19(conn: sqlite3.Connection) -> None:
    """Migration 19: email_typ in email_import_log + Aktion-Badge in unfallakte."""

    # email_import_log: email_typ Spalte
    email_cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(email_import_log)").fetchall()}
    if "email_typ" not in email_cols:
        conn.execute(
            "ALTER TABLE email_import_log ADD COLUMN email_typ TEXT"
        )
        logger.info("Migration 19: email_import_log.email_typ hinzugefuegt.")

    # unfallakte: Aktion-Badge Spalten
    akte_cols = {r[1] for r in conn.execute(
        "PRAGMA table_info(unfallakte)").fetchall()}
    for spalte, typ in [
        ("aktion_erforderlich", "INTEGER NOT NULL DEFAULT 0"),
        ("aktion_typ",          "TEXT"),
        ("aktion_seit",         "TEXT"),
    ]:
        if spalte not in akte_cols:
            conn.execute(
                f"ALTER TABLE unfallakte ADD COLUMN {spalte} {typ}"
            )
            logger.info("Migration 19: unfallakte.%s hinzugefuegt.", spalte)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (19, 'Migration 19 - email_typ + Aktion-Badge')"
    )
    logger.info("Migration 19 abgeschlossen.")

def _run_migration_20(conn: sqlite3.Connection) -> None:
    """
    Migration 20: aktivitaeten.akte_id TEXT statt INTEGER.

    Seit Migration 5 ist der PK von unfallakte TEXT (az), nicht mehr INTEGER.
    Die aktivitaeten-Tabelle hatte noch akte_id INTEGER → INSERT mit TEXT-az
    rollte die Transaktion zurück und verhinderte Dokument-Registrierung.

    SQLite kennt kein ALTER COLUMN TYPE → Tabelle neu bauen.
    """
    # Prüfen ob Migration nötig
    cols = conn.execute("PRAGMA table_info(aktivitaeten)").fetchall()
    col_map = {c[1]: c[2] for c in cols}  # name → type

    if col_map.get("akte_id", "").upper() == "TEXT":
        # Bereits migriert
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
            "VALUES (20, 'Migration 20 - aktivitaeten.akte_id TEXT')"
        )
        return

    logger.info("Migration 20: aktivitaeten.akte_id INTEGER → TEXT …")

    conn.executescript("""
        PRAGMA foreign_keys = OFF;

        CREATE TABLE IF NOT EXISTS aktivitaeten_neu (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id         TEXT REFERENCES unfallakte(az) ON DELETE CASCADE,
            benutzer_id     INTEGER,
            zeitstempel     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            aktion          TEXT NOT NULL,
            beschreibung    TEXT NOT NULL DEFAULT '',
            tabelle         TEXT,
            datensatz_id    INTEGER,
            aenderung_json  TEXT
        );

        INSERT INTO aktivitaeten_neu
            (id, akte_id, benutzer_id, zeitstempel, aktion,
             beschreibung, tabelle, datensatz_id, aenderung_json)
        SELECT
            id,
            CAST(akte_id AS TEXT),
            benutzer_id, zeitstempel, aktion,
            beschreibung, tabelle, datensatz_id, aenderung_json
        FROM aktivitaeten;

        DROP TABLE aktivitaeten;
        ALTER TABLE aktivitaeten_neu RENAME TO aktivitaeten;

        PRAGMA foreign_keys = ON;
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (20, 'Migration 20 - aktivitaeten.akte_id TEXT')"
    )
    logger.info("Migration 20 abgeschlossen.")


def _run_migration_21(conn: sqlite3.Connection) -> None:
    """
    Migration 21: email_absender_vorlagen um versicherer_name + kuerzel erweitern
    + Seed-Daten aller bekannten Versicherer-Domains einfügen.
    """
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(email_absender_vorlagen)").fetchall()}

    if "versicherer_name" not in cols:
        conn.execute(
            "ALTER TABLE email_absender_vorlagen ADD COLUMN versicherer_name TEXT"
        )
        logger.info("Migration 21: versicherer_name hinzugefuegt.")

    if "kuerzel" not in cols:
        conn.execute(
            "ALTER TABLE email_absender_vorlagen ADD COLUMN kuerzel TEXT"
        )
        logger.info("Migration 21: kuerzel hinzugefuegt.")

    # Seed-Daten: bekannte Versicherer-Domains
    SEED = [
        ('LVM Versicherungsagentur Hirsch', 'a-hirsch.lvm.de', 'AHIRSCHLVM'),
        ('ADAC Versicherung AG', 'adac.de', 'ADAC'),
        ('AdmiralDirekt Versicherung', 'admiraldirekt.de', 'ADMIRALDIREKT'),
        ('ADVOCARD Rechtsschutz', 'advocard.de', 'ADVOCARD'),
        ('Deutsche Ärzteversicherung AG', 'aerzteversicherung.de', 'DAEV'),
        ('Aioi Nissay Dowa Insurance', 'aioinissaydowa.eu', 'AIOI'),
        ('Allianz Versicherung', 'allianz.de', 'ALLIANZ'),
        ('Allianz Direct', 'allianzdirect.de', 'ALLIANZ_DIRECT'),
        ('ALLRECHT Rechtsschutz', 'allrecht.de', 'ALLRECHT'),
        ('ALTE LEIPZIGER Versicherung', 'alte-leipziger.de', 'ALTE_LEIPZIGER'),
        ('AachenMünchener Versicherung', 'amv.de', 'AMV'),
        ('ARAG Versicherungen', 'arag-partner.de', 'ARAG'),
        ('ARAG Allgemeine Versicherung', 'arag.de', 'ARAG'),
        ('AXA Versicherung', 'axa.de', 'AXA'),
        ('Balcia Insurance', 'balcia.com', 'BALCIA'),
        ('Baloise Sachversicherung', 'baloise.de', 'BALOISE'),
        ('Basler Sachversicherung', 'basler.de', 'BASLER'),
        ('BavariaDirekt Versicherung', 'bavariadirekt.de', 'BAVARIADIREKT'),
        ('BGV Versicherung', 'bgv.de', 'BGV'),
        ('Concordia Versicherungen', 'concordia.de', 'CONCORDIA'),
        ('Condor Allgemeine Versicherung', 'condor-versicherungen.de', 'CONDOR'),
        ('Continentale Versicherung', 'continentale.de', 'CONTINENTALE'),
        ('CosmosDirekt Versicherung', 'cosmosdirekt.de', 'COSMOS'),
        ('DA Direkt Versicherung', 'da-direkt.de', 'DA_DIREKT'),
        ('DAS Rechtsschutz', 'das.de', 'DAS'),
        ('DBV Deutsche Beamtenversicherung', 'dbv.de', 'DBV'),
        ('Debeka Versicherung', 'debeka.de', 'DEBEKA'),
        ('DEURAG Rechtsschutz', 'deurag.de', 'DEURAG'),
        ('DFV Deutsche Familienversicherung', 'deutsche-familienversicherung.de', 'DFV'),
        ('DEVK Versicherung', 'devk.de', 'DEVK'),
        ('Dialog Versicherung', 'dialog-versicherung.de', 'DIALOG'),
        ('die Bayerische Versicherung', 'diebayerische.de', 'BAYERISCHE'),
        ('DKV Krankenversicherung', 'dkv.com', 'DKV'),
        ('DMB Rechtsschutz', 'dmb-rechtsschutz.de', 'DMB'),
        ('ERGO Versicherung', 'ergo.de', 'ERGO'),
        ('ERGO Direkt', 'ergodirekt.de', 'ERGO_DIREKT'),
        ('EUROPA Versicherung', 'europa.de', 'EUROPA'),
        ('Friday Versicherung', 'friday.de', 'FRIDAY'),
        ('Generali Versicherung', 'generali.com', 'GENERALI'),
        ('Generali Versicherung', 'generali.de', 'GENERALI'),
        ('Gothaer Versicherungen', 'gothaer.de', 'GOTHAER'),
        ('GVV Kommunalversicherung', 'gvv.de', 'GVV'),
        ('HanseMerkur Versicherung', 'hansemerkur.de', 'HANSEMERKUR'),
        ('HDI Versicherung', 'hdi.de', 'HDI'),
        ('Helvetia Versicherung', 'helvetia.de', 'HELVETIA'),
        ('HUK-COBURG Versicherung', 'huk-coburg.de', 'HUK_COBURG'),
        ('InterRisk Versicherungen', 'interrisk.de', 'INTERRISK'),
        ('Itzehoer Versicherungen', 'itzehoer.de', 'ITZEHOER'),
        ('Janitos Versicherung', 'janitos.de', 'JANITOS'),
        ('KRAVAG Versicherung', 'kravag.de', 'KRAVAG'),
        ('AUXILIA Rechtsschutz', 'ks-auxilia.de', 'AUXILIA'),
        ('LVM Versicherungen', 'lvm.de', 'LVM'),
        ('Mannheimer Versicherung', 'mannheimer.de', 'MANNHEIMER'),
        ('MVK Versicherung', 'mvk-versicherung.de', 'MVK'),
        ('Neodigital Versicherung', 'neodigital.de', 'NEODIGITAL'),
        ('Nexible Versicherung', 'nexible.de', 'NEXIBLE'),
        ('Neue Rechtsschutz-Versicherung', 'nrv-rechtsschutz.de', 'NRV'),
        ('Nürnberger Versicherung', 'nuernberger.de', 'NUERNBERGER'),
        ('Öffentliche Versicherung', 'oeffentliche.de', 'OEFFENTLICHE'),
        ('ÖRAG Rechtsschutz', 'oerag.de', 'OERAG'),
        ('ÖSA Versicherungen', 'oesa.de', 'OESA'),
        ('ÖVB Versicherungen', 'oevb.de', 'OEVB'),
        ('Öffentliche Versicherung Oldenburg', 'oevo.de', 'OEVO'),
        ('Provinzial Versicherung', 'provinzial.com', 'PROVINZIAL'),
        ('Provinzial Versicherung', 'provinzial.de', 'PROVINZIAL'),
        ('RheinLand Versicherung', 'rheinland-versicherungen.de', 'RHEINLAND'),
        ('Rhion Versicherung', 'rhion.digital', 'RHION'),
        ('ROLAND Rechtsschutz', 'roland-rechtsschutz.de', 'ROLAND'),
        ('R+V Versicherung', 'ruv.de', 'RUV'),
        ('Saarland Versicherungen', 'saarland-versicherungen.de', 'SAARLAND'),
        ('SIGNAL IDUNA Versicherung', 'signal-iduna.de', 'SIGNAL_IDUNA'),
        ('Sparkassen Direkt Versicherung', 'sparkassen-direkt.de', 'SPARKASSE_DIREKT'),
        ('SV SparkassenVersicherung', 'sparkassenversicherung.de', 'SV_SPARKASSE'),
        ('SV Sparkasse Sachsen', 'sv-sachsen.de', 'SV_SACHSEN'),
        ('UNIQA Versicherung', 'uniqa.at', 'UNIQA'),
        ('uniVersa Versicherung', 'universa.de', 'UNIVERSA'),
        ('Verti Versicherung', 'verti.de', 'VERTI'),
        ('VGH Versicherung', 'vgh.de', 'VGH'),
        ('VHV Versicherung', 'vhv.de', 'VHV'),
        ('Victoria Versicherung', 'victoria.de', 'VICTORIA'),
        ('VKB Versicherung', 'vkb.de', 'VKB'),
        ('VOLKSWOHL-BUND Versicherung', 'volkswohl-bund.de', 'VOLKSWOHL'),
        ('VPV Versicherungen', 'vpv.de', 'VPV'),
        ('VRK Versicherung', 'vrk.de', 'VRK'),
        ('Volkswagen Autoversicherung', 'vwav.com', 'VW_AUTO'),
        ('Wefox Insurance', 'wefox.de', 'WEFOX'),
        ('WGV Versicherung', 'wgv.de', 'WGV'),
        ('Württembergische Versicherung', 'wuerttembergische.de', 'WUERTTEMBERGISCHE'),
        ('WWK Versicherung', 'wwk.de', 'WWK'),
        ('Zurich Insurance', 'zurich.com', 'ZURICH'),
        ('Zurich Versicherung', 'zurich.de', 'ZURICH'),
        ('ADAC Autoversicherung', 'auto.adac.de', 'ADAC_AUTO'),
        ('ADAC Autoversicherung', 'autoversicherung.adac.de', 'ADAC_AUTO'),
        ('Helvetia Versicherung Bremen', 'bremen.helvetia.de', 'HELVETIA_HB'),
        ('Helvetia Versicherung Frankfurt', 'frankfurt.helvetia.de', 'HELVETIA_FFM'),
        ('Alte Leipziger Schadenservice', 'schadenservice.net', 'ALTE_LEIPZIGER'),
        ('Baloise Assurance Luxemburg', 'baloise.lu', 'BALOISE_LU'),
        ('AGILA Haustier-Krankenversicherung', 'agila.de', 'AGILA'),
        ('BGV Badische Versicherungen', 'bgv.de', 'BGV'),
        ('Basler Securitas', 'basec.de', 'BASEC'),
        ('BTA Insurance', 'bta-versicherung.de', 'BTA'),
        ('Breitspire/Gefion Insurance', 'broadspire.de', 'BROADSPIRE'),
        ('Donau Versicherung', 'donauversicherung.at', 'DONAU'),
        ('Deutsche Rentenversicherung Bund', 'drv-bund.de', 'DRV_BUND'),
        ('Deutsche Rentenversicherung BW', 'drv-bw.de', 'DRV_BW'),
        ('DRV Hessen', 'drv-hessen.de', 'DRV_HE'),
        ('DFVR Familienversicherung', 'dfvr.de', 'DFVR'),
        ('Ecclesia Versicherungsdienst', 'ecclesia.de', 'ECCLESIA'),
        ('Familienschutz Lebensversicherung', 'familienschutz.de', 'FAMILIENSCHUTZ'),
        ('Feuersozietät Berlin Brandenburg', 'feuersozietaet.de', 'FEUERSOZIETT'),
        ('Fahrlehrerversicherung', 'fv.de', 'FV'),
        ('GVO Gegenseitigkeit Versicherung', 'g-v-o.de', 'GVO'),
        ('GHV Haftpflichtversicherung', 'ghv-versicherung.de', 'GHV'),
        ('Grundeigentümer-Versicherung', 'grundvers.de', 'GRUNDEIG'),
        ('Hava Kassel Haftpflicht', 'hava-kassel.de', 'HAVA'),
        ('IDEAL Versicherung', 'ideal-versicherung.de', 'IDEAL'),
        ('JVG Jeversche Versicherung', 'jvg.de', 'JVG'),
        ('Deutsche Rentenversicherung KBS', 'kbs.de', 'KBS'),
        ('KNAPPSCHAFT Krankenversicherung', 'knappschaft.de', 'KNAPPSCHAFT'),
        ('Lippische Landesbrandversicherung', 'lippische.de', 'LIPPISCHE'),
        ('Landesschadenhilfe Versicherung', 'lsh-versicherung.de', 'LSH'),
        ('MACIF Versicherung', 'macif.fr', 'MACIF'),
        ('Die Mobiliar Versicherung', 'mobiliar.ch', 'MOBILIAR'),
        ('MyCIC Insurance Claims', 'mycic.eu', 'MYCIC'),
        ('OAB Ostangler Versicherungen', 'oab.de', 'OAB'),
        ('OKV Ostdeutsche Kommunalversicherung', 'okv.de', 'OKV'),
        ('Ontos Versicherungen', 'ontos.de', 'ONTOS'),
        ('OVS Versicherung', 'ovs-versicherung.de', 'OVS'),
        ('Sovag Schwarzmeer Ostsee', 'sovag.de', 'SOVAG'),
        ('SV Landwirtschaft Forsten', 'svlfg.de', 'SVLFG'),
        ('SV Landwirtschaft Forsten', 'swlfg.de', 'SWLFG'),
        ('Vitosha Insurance', 'vitosha.bg', 'VITOSHA'),
        ('Vödag Versicherung', 'voedag.de', 'VOEDAG'),
        ('VVDE Eisenbahnen Versicherung', 'vvde.de', 'VVDE'),
        ('Waldenburger Versicherung', 'waldenburger.com', 'WALDENBURGER'),
        ('Wiener Städtische Versicherung', 'wienerstaedtische.at', 'WIENER_STAEDT'),
        ('Probus Insurance (Sedgwick)', 'de.sedgwick.com', 'SEDGWICK'),
        ('Deutsche Internet Versicherung', 'deutscheinternetversicherung.de', 'DIV'),
        ('CNP Santander Insurance', 'ger.cnpsantander.com', 'CNP_SANTANDER'),
        ('UPS International Insurance', 'crawco.de', 'CRAWCO'),
        ('Dittmeier Versicherungsmakler', 'dittmeier.de', 'DITTMEIER'),
        ('ATOS Versicherungsmakler', 'atos-fulda.de', 'ATOS'),
        ('Staun Versicherungsmakler', 'staun.de', 'STAUN'),
        ('Versteegen Assekuranz', 'versteegen.de', 'VERSTEEGEN'),
        ('Stuttgarter Lebensversicherung', 'stuttgarter.de', 'STUTTGARTER'),
        ('Baden-Badener Versicherung', 'baden-badener.e', 'BADENBADENER'),
        ('BHVG Bayerische Hausbesitzer', 'bhvg.de', 'BHVG'),
        ('LVA Schwaben', 'lva-schwaben.de', 'LVA_SCHWABEN'),
        ('Jurpartner/Bayerische Beamten', 'jurpartner-services.de', 'JURPARTNER'),
        ('Generali Deutschland', 'generali.com', 'GENERALI'),
        ('Zurich Insurance plc', 'zurich.com', 'ZURICH'),
    ]

    inserted = 0
    for name, domain, kuerzel in SEED:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO email_absender_vorlagen
                   (name, domain, kategorie, versicherer_name, kuerzel)
                   VALUES (?, ?, 'versicherung', ?, ?)""",
                (name, domain, name, kuerzel)
            )
            # Bestehende Einträge um versicherer_name/kuerzel ergänzen
            conn.execute(
                """UPDATE email_absender_vorlagen
                   SET versicherer_name = ?, kuerzel = ?, kategorie = 'versicherung'
                   WHERE domain = ? AND (versicherer_name IS NULL OR versicherer_name = '')""",
                (name, kuerzel, domain)
            )
            inserted += 1
        except Exception as e:
            logger.warning("Seed-Eintrag fehlgeschlagen (%s): %s", domain, e)

    logger.info("Migration 21: %d Versicherer-Einträge eingespielt.", inserted)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (21, 'Migration 21 - versicherer_name/kuerzel + Seed-Daten')"
    )
    logger.info("Migration 21 abgeschlossen.")


def init_db() -> None:
    """
    Hauptfunktion: Schema erstellen + Migrationen ausführen.
    Wird beim App-Start aufgerufen.
    """
    create_schema()
    run_migrations()


# CLI-Modus
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if "--check" in sys.argv:
        status = check_schema()
        print(f"\n=== Schema-Prüfung ===")
        print(f"Version : {status['version']}")
        print(f"Status  : {'✅ OK' if status['ok'] else '❌ FEHLER'}")
        print(f"\nTabellen:")
        for t, ok in status["tabellen"].items():
            print(f"  {'✅' if ok else '❌'} {t}")
        print(f"\nViews:")
        for v, ok in status["views"].items():
            print(f"  {'✅' if ok else '❌'} {v}")
        sys.exit(0 if status["ok"] else 1)

    elif "--reset" in sys.argv:
        confirm = input("⚠️  ALLE DATEN LÖSCHEN? Bitte 'ja' eingeben: ")
        if confirm.strip().lower() == "ja":
            reset_database()
        else:
            print("Abgebrochen.")

    else:
        init_db()
        print("✅ Datenbank initialisiert.")


def _run_migration_22(conn: sqlite3.Connection) -> None:
    """
    Migration 22: textbaustein-Feld in kuerzungsarten (PRD-02).
    Enthält den ausführlichen briefreifen Text für Stellungnahmen.
    Fallback-Kette: textbaustein → standard_gegenargument → Default-Text.
    """
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(kuerzungsarten)").fetchall()}

    if "textbaustein" not in cols:
        conn.execute(
            "ALTER TABLE kuerzungsarten ADD COLUMN textbaustein TEXT"
        )
        logger.info("Migration 22: textbaustein zu kuerzungsarten hinzugefuegt.")

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (22, 'Migration 22 – kuerzungsarten.textbaustein fuer Stellungnahmen')"
    )


def _run_migration_23(conn: sqlite3.Connection) -> None:
    """
    Migration 23: todos-Tabelle (PRD-01).
    Ermöglicht manuelle und automatische To-Dos je Akte.
    Dringlichkeit wird im Frontend aus erstellt_am / faellig_am berechnet.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS todos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_az      TEXT    NOT NULL REFERENCES unfallakte(az),
            text         TEXT    NOT NULL,
            erstellt_am  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            faellig_am   TEXT,
            frist_typ    TEXT,
            erledigt_am  TEXT,
            erledigt     INTEGER NOT NULL DEFAULT 0
                        CHECK(erledigt IN (0,1)),
            quelle       TEXT    NOT NULL DEFAULT 'benutzer'
                        CHECK(quelle IN ('benutzer','system')),
            dok_id       INTEGER REFERENCES dokumente(id),
            regel_key    TEXT,
            sortierung   INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_todos_akte_az
            ON todos (akte_az);

        CREATE INDEX IF NOT EXISTS idx_todos_erledigt
            ON todos (akte_az, erledigt);
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (23, 'Migration 23 – todos-Tabelle (PRD-01)')"
    )
    logger.info("Migration 23: todos-Tabelle angelegt.")


def _run_migration_24(conn: sqlite3.Connection) -> None:
    """
    Migration 24: dokumentenklasse + pdf_hash (PRD-04).
    Grundlage fuer Dispatcher + Vollstaendigkeitsampel.
    """
    cols = {c[1] for c in conn.execute(
        "PRAGMA table_info(dokumente)").fetchall()}

    if "dokumentenklasse" not in cols:
        conn.execute(
            "ALTER TABLE dokumente ADD COLUMN dokumentenklasse TEXT"
        )
        logger.info("Migration 24: dokumentenklasse hinzugefuegt.")

    if "pdf_hash" not in cols:
        conn.execute(
            "ALTER TABLE dokumente ADD COLUMN pdf_hash TEXT"
        )
        logger.info("Migration 24: pdf_hash hinzugefuegt.")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dok_hash ON dokumente(pdf_hash)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dok_klasse ON dokumente(dokumentenklasse)"
    )

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (24, 'Migration 24 - dokumentenklasse + pdf_hash (PRD-04)')"
    )
    logger.info("Migration 24 abgeschlossen.")


def _run_migration_25(conn: sqlite3.Connection) -> None:
    """
    Migration 25: klassifikation_training (PRD-04b).
    Speichert Korrektur-Paare fuer TF-IDF-Retraining.
    Jede manuelle Korrektur der Dokumentenklasse wird hier protokolliert.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS klassifikation_training (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            dok_id            INTEGER REFERENCES dokumente(id),
            rohtext_hash      TEXT    NOT NULL,
            rohtext_snippet   TEXT,
            klasse_auto       TEXT,
            klasse_korrigiert TEXT    NOT NULL,
            konfidenz_auto    REAL,
            stufe_auto        TEXT,
            korrigiert_am     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            korrigiert_von    INTEGER REFERENCES benutzer(id)
        );

        CREATE INDEX IF NOT EXISTS idx_training_klasse
            ON klassifikation_training (klasse_korrigiert);

        CREATE INDEX IF NOT EXISTS idx_training_dok
            ON klassifikation_training (dok_id);
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (25, 'Migration 25 - klassifikation_training (PRD-04b)')"
    )
    logger.info("Migration 25: klassifikation_training-Tabelle angelegt.")


def _run_migration_26(conn):
    # type: (sqlite3.Connection) -> None
    """
    Migration 26: E-Akte-Integration (PRD-21 Phase 3a).
    Erweitert dokumente-Tabelle um E-Akte-Referenzen.
    Neue Tabelle eakte_klassifikation fuer Batch-Klassifikation (Phase 3b).
    """
    # Spalten zur dokumente-Tabelle hinzufuegen
    existing = [row[1] for row in conn.execute("PRAGMA table_info(dokumente)").fetchall()]

    if "eakte_nr" not in existing:
        conn.execute("ALTER TABLE dokumente ADD COLUMN eakte_nr INTEGER")
    if "eakte_pfad" not in existing:
        conn.execute("ALTER TABLE dokumente ADD COLUMN eakte_pfad TEXT")
    if "quelle" not in existing:
        conn.execute("ALTER TABLE dokumente ADD COLUMN quelle TEXT DEFAULT 'upload'")

    # Index fuer schnelle Duplikat-Pruefung
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dokumente_eakte_nr "
        "ON dokumente (eakte_nr)"
    )

    # Tabelle fuer Batch-Klassifikation (Phase 3b, schon vorbereiten)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS eakte_klassifikation (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            eakte_nr         INTEGER NOT NULL,
            akte_az          TEXT    NOT NULL,
            dokumentenklasse TEXT,
            konfidenz        REAL,
            stufe            TEXT,
            absender_domain  TEXT,
            klassifiziert_am TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(eakte_nr)
        );

        CREATE INDEX IF NOT EXISTS idx_eakte_klass_az
            ON eakte_klassifikation (akte_az);
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (26, 'Migration 26 - E-Akte-Integration (PRD-21)')"
    )
    logger.info("Migration 26: E-Akte-Spalten + eakte_klassifikation angelegt.")


def _run_migration_27(conn: sqlite3.Connection) -> None:
    """
    Migration 27: Schadenposition-Belege (PRD-23a).
    Verknuepft Schadenpositionen mit ihren Belegen (Rechnungen, Gutachten).
    Ermoeglicht manuelle Zuordnung + spaeter automatische via Parser (PRD-23b).
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schadenposition_belege (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_az          TEXT    NOT NULL,
            position_key     TEXT    NOT NULL,
            dokument_id      INTEGER NOT NULL REFERENCES dokumente(id),
            betrag_aus_beleg REAL,
            notiz            TEXT,
            erstellt_am      TEXT    DEFAULT (datetime('now','localtime')),
            UNIQUE(akte_az, position_key, dokument_id)
        );

        CREATE INDEX IF NOT EXISTS idx_belege_akte
            ON schadenposition_belege (akte_az);

        CREATE INDEX IF NOT EXISTS idx_belege_dok
            ON schadenposition_belege (dokument_id);
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (27, 'Migration 27 - schadenposition_belege (PRD-23a)')"
    )
    logger.info("Migration 27: schadenposition_belege-Tabelle angelegt.")


def _run_migration_50(conn: sqlite3.Connection) -> None:
    """
    Migration 50: unfalldetails-Tabelle anlegen (Root-Cause-Fix).

    Die Tabelle wurde nie vom aktiven Schema-Manager erzeugt -- nur vom
    toten Root-Legacy-Manager (backend/schema_manager.py), der nie gegen
    die Live-DB lief. Migration 28 setzt seit v56 mit einem PRAGMA-
    table_info-Guard voraus, dass die Tabelle existiert, findet sie aber
    nicht und stempelt sich selbst als "SKIPPED" in schema_version.
    Ergebnis: `GET/PUT /akten/<az>/unfalldetails` und der geschaefts-
    kritische `POST /akten/<az>/klage/generieren` crashen mit 500
    (sqlite3.OperationalError: no such table: unfalldetails).

    Diese Migration holt das CREATE TABLE nach -- inklusive der drei
    Aktivlegitimations-Spalten aus Migration 28, damit ein Fresh-Setup
    nicht zusaetzlich auf Migration 28 angewiesen ist.

    Zu Migration 28 (SKIPPED-Zustand): Der schema_version-Eintrag von
    Migration 28 bleibt fuer Alt-Installationen auf "... SKIPPED"
    stehen -- INSERT OR IGNORE verhindert ein Update. Das ist harmlos
    (Migration 50 deckt die drei Aktivlegitimations-Spalten mit ab),
    aber Migration 28 ist damit redundant und effektiv tot.

    FK-Konvention (siehe bugs_and_fixes.md und DECISIONS.md F-02):
    unfalldetails.akte_id -> unfallakte(az), NIEMALS ...aktenzeichen.
    Der urspruengliche Legacy-DDL verwies auf unfallakte(aktenzeichen) --
    das war eine tickende Zeitbombe, hier korrigiert.

    Idempotent: CREATE TABLE IF NOT EXISTS + Spalten-Existenz-Check.
    Falls die Tabelle aus einem alten Dev-Stand bereits ohne die
    Aktivlegitimations-Spalten existiert, werden diese per ALTER TABLE
    ergaenzt (gleiche Logik wie Migration 28, aber diesmal mit
    existierender Tabelle).
    """
    # BUG-13: KEIN conn.executescript() -- executescript committet implizit
    # und laesst bei Abbruch/Dev-Reloader ALTER-Spalten und schema_version-
    # Stempel auseinanderfallen (feedback_migration_executescript). Statt-
    # dessen einzelne execute()-Aufrufe mit expliziten Commits, Muster wie
    # Migrationen 52-55.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unfalldetails (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id                     TEXT NOT NULL UNIQUE
                                         REFERENCES unfallakte(az) ON DELETE CASCADE,
            schilderung                 TEXT,
            zeuge_1                     TEXT,
            zeuge_1_anschrift           TEXT,
            zeuge_2                     TEXT,
            zeuge_2_anschrift           TEXT,
            zeuge_3                     TEXT,
            zeuge_3_anschrift           TEXT,
            ermittlungsakte_az          TEXT,
            ermittlungsakte_behoerde    TEXT,
            ermittlungsakte_ort         TEXT,
            fahrer_mandant              TEXT,
            fahrer_gegner               TEXT,
            vorsteuerabzug              INTEGER DEFAULT 0,
            haftungsquote               REAL    DEFAULT 100,
            haftungsbegruendung         TEXT,
            aktivlegitimation_typ       TEXT NOT NULL DEFAULT 'eigentum',
            aktivlegitimation_freigabe  TEXT NOT NULL DEFAULT 'freigabe',
            aktivlegitimation_datum     TEXT,
            erstellt_am                 TEXT DEFAULT (datetime('now','localtime')),
            geaendert_am                TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_unfalldetails_akte "
        "ON unfalldetails(akte_id)"
    )
    conn.commit()

    # Falls die Tabelle aus einem alten Dev-Stand noch ohne die
    # Aktivlegitimations-Spalten existiert (CREATE TABLE IF NOT EXISTS
    # greift dann nicht) -> gleiche ALTER-Logik wie Migration 28, jetzt mit
    # expliziten Commits um jedes ALTER.
    vorhandene = {r[1] for r in conn.execute(
        "PRAGMA table_info(unfalldetails)").fetchall()}
    for spalte, typ in (
        ("aktivlegitimation_typ",      "TEXT NOT NULL DEFAULT 'eigentum'"),
        ("aktivlegitimation_freigabe", "TEXT NOT NULL DEFAULT 'freigabe'"),
        ("aktivlegitimation_datum",    "TEXT"),
    ):
        if spalte not in vorhandene:
            conn.commit()
            conn.execute(f"ALTER TABLE unfalldetails ADD COLUMN {spalte} {typ}")
            conn.commit()
            logger.info("Migration 50: unfalldetails.%s per ALTER nachgetragen.", spalte)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (50, 'Migration 50 - unfalldetails-Tabelle nachtraeglich angelegt (Root-Cause-Fix zu Migration 28 SKIPPED)')"
    )
    conn.commit()
    logger.info("Migration 50: unfalldetails-Tabelle angelegt/geprueft.")


def _run_migration_28(conn: sqlite3.Connection) -> None:
    """
    Migration 28: Aktivlegitimation in unfalldetails (PRD-24).

    Neue Felder in unfalldetails:
      aktivlegitimation_typ      TEXT DEFAULT 'eigentum'
        Werte: 'eigentum' | 'finanziert' | 'geleast'
      aktivlegitimation_freigabe TEXT DEFAULT 'freigabe'
        Werte: 'freigabe' | 'bedingungen' | 'ungeklaert'
      aktivlegitimation_datum    TEXT DEFAULT NULL
        Format: DD.MM.YYYY – Datum der Freigabeerklärung (Fälle C+E)
    """
    # Check if unfalldetails table exists
    table_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='unfalldetails'"
    ).fetchone() is not None

    if not table_exists:
        # Table doesn't exist yet - skip migration
        logger.warning("Migration 28: Tabelle unfalldetails existiert nicht, überspringe Migration.")
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
            "VALUES (28, 'Migration 28 - Aktivlegitimation in unfalldetails (PRD-24) - SKIPPED')"
        )
        return

    vorhandene = {row[1] for row in conn.execute(
        "PRAGMA table_info(unfalldetails)").fetchall()}

    neue_spalten = [
        ("aktivlegitimation_typ",      "TEXT NOT NULL DEFAULT 'eigentum'"),
        ("aktivlegitimation_freigabe", "TEXT NOT NULL DEFAULT 'freigabe'"),
        ("aktivlegitimation_datum",    "TEXT"),
    ]

    for spalte, typ in neue_spalten:
        if spalte not in vorhandene:
            conn.execute(
                f"ALTER TABLE unfalldetails ADD COLUMN {spalte} {typ}"
            )
            logger.info("Migration 28: unfalldetails.%s hinzugefuegt.", spalte)
        else:
            logger.info("Migration 28: %s bereits vorhanden.", spalte)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (28, 'Migration 28 - Aktivlegitimation in unfalldetails (PRD-24)')"
    )
    logger.info("Migration 28 abgeschlossen.")


def _run_migration_29(conn: sqlite3.Connection) -> None:
    """
    Migration 29: Rechnungs-Parse-Cache fuer E-Akte-Dokumente (PRD-23b).

    Cacht Parse-Ergebnisse von E-Akte-PDFs (nicht lokal importiert).
    Cache-Key: eakte_nr (PK) + datei_groesse (Aenderungserkennung).
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rechnung_parse_cache (
            eakte_nr        INTEGER PRIMARY KEY,
            datei_groesse   INTEGER NOT NULL,
            geparst_am      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
            ergebnis_json   TEXT    NOT NULL
        );
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (29, 'Migration 29 - rechnung_parse_cache (PRD-23b)')"
    )
    logger.info("Migration 29: rechnung_parse_cache angelegt.")


def _run_migration_30(conn: sqlite3.Connection) -> None:
    """
    Migration 30: Fragebogen-Erstkontakt-Tabelle (PRD-22c).

    Speichert Website-Unfallbogen-Einsendungen ohne vorhandenes Aktenzeichen.
    Akte-Anlage (PRD-22d) ist noch nicht implementiert – dies ist der Stub.
    """
    conn.executescript("""
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
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (30, 'Migration 30 - fragebogen_erstkontakt (PRD-22c)')"
    )
    logger.info("Migration 30: fragebogen_erstkontakt angelegt.")


def _run_migration_31(conn):
    # type: (sqlite3.Connection) -> None
    """
    Migration 31: Performance-Index für Fristen-Abfragen (PRD-25a).

    Ermöglicht schnelles Laden aller offenen, fälligen Todos
    ohne Full-Table-Scan – wichtig für das Action-Dashboard (PRD-25b).
    """
    conn.executescript("""
        CREATE INDEX IF NOT EXISTS idx_todos_faellig
            ON todos (erledigt, faellig_am);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (31, 'Migration 31 - idx_todos_faellig (PRD-25a)')"
    )
    logger.info("Migration 31: idx_todos_faellig angelegt.")


def _run_migration_32(conn):
    # type: (sqlite3.Connection) -> None
    """
    Migration 32: todos.dok_id Referenz von 'dokumente_alt' auf 'dokumente' korrigieren.

    Die todos-Tabelle referenzierte die nicht mehr existierende Tabelle dokumente_alt,
    was bei PRAGMA foreign_keys = ON jeden INSERT in todos blockierte.
    """
    conn.executescript("""
        PRAGMA foreign_keys = OFF;

        CREATE TABLE IF NOT EXISTS todos_new (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_az      TEXT    NOT NULL REFERENCES unfallakte(az),
            text         TEXT    NOT NULL,
            erstellt_am  TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            faellig_am   TEXT,
            frist_typ    TEXT,
            erledigt_am  TEXT,
            erledigt     INTEGER NOT NULL DEFAULT 0
                        CHECK(erledigt IN (0,1)),
            quelle       TEXT    NOT NULL DEFAULT 'benutzer'
                        CHECK(quelle IN ('benutzer','system')),
            dok_id       INTEGER REFERENCES dokumente(id),
            regel_key    TEXT,
            sortierung   INTEGER NOT NULL DEFAULT 0
        );

        INSERT INTO todos_new
            SELECT id, akte_az, text, erstellt_am, faellig_am, frist_typ,
                   erledigt_am, erledigt, quelle, dok_id, regel_key, sortierung
            FROM todos;

        DROP TABLE todos;
        ALTER TABLE todos_new RENAME TO todos;

        CREATE INDEX IF NOT EXISTS idx_todos_faellig
            ON todos (erledigt, faellig_am);

        PRAGMA foreign_keys = ON;
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (32, 'Migration 32 - todos.dok_id Referenz auf dokumente korrigiert')"
    )
    logger.info("Migration 32: todos.dok_id Referenz korrigiert.")


def _run_migration_34(conn):
    # type: (sqlite3.Connection) -> None
    """
    Migration 34: ist_halter-Flag in beteiligte (PRD-26 Einleitungssatz).
    Ermöglicht Unterscheidung Gegner-Halter vs. Gegner-Versicherung im Klage-Wizard.
    """
    vorhandene = {row[1] for row in conn.execute("PRAGMA table_info(beteiligte)").fetchall()}
    if "ist_halter" not in vorhandene:
        conn.execute(
            "ALTER TABLE beteiligte ADD COLUMN ist_halter INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("Migration 34: beteiligte.ist_halter hinzugefuegt.")
    else:
        logger.info("Migration 34: ist_halter bereits vorhanden.")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (34, 'Migration 34 \u2013 ist_halter in beteiligte (PRD-26 Einleitungssatz)')"
    )
    logger.info("Migration 34 abgeschlossen.")


def _run_migration_33(conn):
    # type: (sqlite3.Connection) -> None
    """
    Migration 33: Konfigurationstabelle + STA-Fristen-Defaults (PRD-25d).

    Legt eine generische Key-Value-Tabelle 'konfiguration' an und
    befüllt die Standardwerte für die drei STA-Eskalationsstufen.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS konfiguration (
            schluessel   TEXT PRIMARY KEY,
            wert         TEXT NOT NULL,
            beschreibung TEXT,
            geaendert_am TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Defaults nur einfügen wenn noch nicht vorhanden
    defaults = [
        ("sta_stufe1_tage", "14", "STA Stufe 1 (Erinnerung): Frist in Tagen"),
        ("sta_stufe2_tage",  "7", "STA Stufe 2 (Mahnung): Frist in Tagen"),
        ("sta_stufe3_tage",  "5", "STA Stufe 3 (Klage-Ankündigung): Frist in Tagen"),
    ]
    for schluessel, wert, beschreibung in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO konfiguration (schluessel, wert, beschreibung) VALUES (?, ?, ?)",
            (schluessel, wert, beschreibung),
        )
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (33, 'Migration 33 - konfiguration + STA-Fristen-Defaults')"
    )
    logger.info("Migration 33: konfiguration angelegt, STA-Fristen-Defaults gesetzt.")


def _run_migration_35(conn):
    # type: (sqlite3.Connection) -> None
    """
    Migration 35: Gebührenassistent (PRD-28) – Nr. 2300 VV RVG.

    Erweitert bestehende Tabellen um Felder für die VU-Entscheidungsmatrix
    und legt die neue Tabelle gebuehren_berechnung an.
    """
    # ── unfallakte: Auslandsbezug, Todesfall, Haftung streitig ───────────────
    vorhandene_akte = {
        row[1] for row in conn.execute("PRAGMA table_info(unfallakte)").fetchall()
    }
    for spalte, typ in [
        ("auslandsbezug",   "INTEGER NOT NULL DEFAULT 0"),
        ("todesfall",       "INTEGER NOT NULL DEFAULT 0"),
        ("haftung_streitig","INTEGER NOT NULL DEFAULT 0"),
    ]:
        if spalte not in vorhandene_akte:
            conn.execute(f"ALTER TABLE unfallakte ADD COLUMN {spalte} {typ}")
            logger.info("Migration 35: unfallakte.%s hinzugefuegt.", spalte)
        else:
            logger.info("Migration 35: unfallakte.%s bereits vorhanden.", spalte)

    # ── personenschaden: Verletzungsgrad, Pflegebedarf ───────────────────────
    vorhandene_ps = {
        row[1] for row in conn.execute("PRAGMA table_info(personenschaden)").fetchall()
    }
    for spalte, typ in [
        ("verletzungsgrad", "TEXT"),                         # keine|leicht|schwer|schwerst
        ("pflegebedarf",    "INTEGER NOT NULL DEFAULT 0"),
    ]:
        if spalte not in vorhandene_ps:
            conn.execute(f"ALTER TABLE personenschaden ADD COLUMN {spalte} {typ}")
            logger.info("Migration 35: personenschaden.%s hinzugefuegt.", spalte)
        else:
            logger.info("Migration 35: personenschaden.%s bereits vorhanden.", spalte)

    # ── Neue Tabelle gebuehren_berechnung ─────────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS gebuehren_berechnung (
            id               INTEGER PRIMARY KEY,
            akte_id          TEXT NOT NULL REFERENCES unfallakte(az),
            vuregel_id       TEXT,
            faktor_vorschlag REAL,
            faktor_final     REAL,
            begruendung      TEXT,
            kriterien_json   TEXT,
            erfasst_am       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            erfasst_von      INTEGER REFERENCES benutzer(id),
            UNIQUE(akte_id)
        );
        CREATE INDEX IF NOT EXISTS idx_gebuehren_akte
            ON gebuehren_berechnung(akte_id);
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (35, 'Migration 35 - Gebuehrenassistent PRD-28')"
    )
    logger.info("Migration 35 abgeschlossen.")


def _run_migration_36(conn):
    # type: (sqlite3.Connection) -> None
    """
    Migration 36: Schmerzensgeld-Ermittlungstool (PRD-29).

    Neue Felder in personenschaden für gespeichertes Orientierungsurteil
    und KI-generierten Klagetext.
    """
    vorhandene = {
        row[1] for row in conn.execute("PRAGMA table_info(personenschaden)").fetchall()
    }
    for spalte, typ in [
        ("sg_mindest",         "REAL"),
        ("sg_text",            "TEXT"),
        ("sg_urteil_gericht",  "TEXT"),
        ("sg_urteil_az",       "TEXT"),
        ("sg_urteil_betrag",   "REAL"),
    ]:
        if spalte not in vorhandene:
            conn.execute(f"ALTER TABLE personenschaden ADD COLUMN {spalte} {typ}")
            logger.info("Migration 36: personenschaden.%s hinzugefuegt.", spalte)
        else:
            logger.info("Migration 36: personenschaden.%s bereits vorhanden.", spalte)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) "
        "VALUES (36, 'Migration 36 - Schmerzensgeld-Ermittlungstool PRD-29')"
    )
    logger.info("Migration 36 abgeschlossen.")


def _run_migration_38(conn):
    # type: (sqlite3.Connection) -> None
    """Portal-Sync-Spalten + Hilfstabellen."""
    vorhanden_ua = {r[1] for r in conn.execute("PRAGMA table_info(unfallakte)").fetchall()}
    for spalte, typ in [
        ("portal_aktiv",        "INTEGER NOT NULL DEFAULT 0"),
        ("portal_sync_pending", "INTEGER NOT NULL DEFAULT 0"),
        ("portal_last_sync",    "TEXT"),
    ]:
        if spalte not in vorhanden_ua:
            conn.execute("ALTER TABLE unfallakte ADD COLUMN {} {}".format(spalte, typ))
            logger.info("Migration 38: unfallakte.%s hinzugefuegt.", spalte)

    vorhanden_dok = {r[1] for r in conn.execute("PRAGMA table_info(dokumente)").fetchall()}
    if "portal_sichtbar" not in vorhanden_dok:
        conn.execute(
            "ALTER TABLE dokumente ADD COLUMN portal_sichtbar INTEGER NOT NULL DEFAULT 0"
        )
        logger.info("Migration 38: dokumente.portal_sichtbar hinzugefuegt.")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS portal_sync_queue (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id      TEXT    NOT NULL,  -- kein FK: Queue-Einträge bleiben auch nach Akten-Löschung erhalten
            sync_version INTEGER NOT NULL,
            status       TEXT    DEFAULT 'pending'
                         CHECK(status IN ('pending','sending','confirmed','failed')),
            created_at   TEXT    DEFAULT (datetime('now','localtime')),
            sent_at      TEXT,
            retry_count  INTEGER DEFAULT 0,
            last_error   TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS portal_einladungen (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            akte_id        TEXT    NOT NULL REFERENCES unfallakte(az) ON DELETE CASCADE,
            beteiligter_id INTEGER NOT NULL REFERENCES beteiligte(id) ON DELETE CASCADE,
            email          TEXT    NOT NULL,
            rolle          TEXT    NOT NULL
                           CHECK(rolle IN ('sachverstaendiger','privatmandant')),
            status         TEXT    DEFAULT 'ausstehend'
                           CHECK(status IN ('ausstehend','gesendet','angenommen')),
            eingeladen_am  TEXT    DEFAULT (datetime('now','localtime')),
            eingeladen_von INTEGER REFERENCES benutzer(id)
        )
    """)

    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (38, "Migration 38 - portal_aktiv, portal_sync_pending, portal_sync_queue, portal_einladungen"),
    )
    logger.info("Migration 38 abgeschlossen.")


def _run_migration_39(conn):
    # type: (sqlite3.Connection) -> None
    """PORTAL-A2: gutachten_nr in beteiligte für Sachverständigen-Auftragsnummer."""
    vorhanden = {r[1] for r in conn.execute("PRAGMA table_info(beteiligte)").fetchall()}
    if "gutachten_nr" not in vorhanden:
        conn.execute("ALTER TABLE beteiligte ADD COLUMN gutachten_nr TEXT")
        logger.info("Migration 39: beteiligte.gutachten_nr hinzugefuegt.")
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (39, "Migration 39 - beteiligte.gutachten_nr fuer Portal-A2"),
    )
    logger.info("Migration 39 abgeschlossen.")


def _run_migration_40(conn):
    # type: (sqlite3.Connection) -> None
    """Migration 40: stellungnahme_texte – gespeicherte Gegenargument-Texte je Akte/Position."""
    conn.execute("""
CREATE TABLE IF NOT EXISTS stellungnahme_texte (
    az              TEXT    NOT NULL,
    gruppe_key      TEXT    NOT NULL,
    gegenargument   TEXT,
    geaendert_am    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (az, gruppe_key)
)
    """)
    conn.execute(
        "INSERT OR IGNORE INTO schema_version (version, beschreibung) VALUES (?, ?)",
        (40, "Migration 40 – stellungnahme_texte fuer ReguWizard-Persistenz"),
    )
    logger.info("Migration 40 abgeschlossen.")


def _run_migration_41(conn: sqlite3.Connection) -> None:
    """Migration 41: sv_portal_accounts – SV-Portal-Account-Verwaltung."""
    conn.executescript("""
CREATE TABLE IF NOT EXISTS sv_portal_accounts (
    adressnr              INTEGER PRIMARY KEY,
    name                  TEXT    NOT NULL,
    vorname               TEXT,
    email                 TEXT    NOT NULL UNIQUE,
    portal_aktiv          INTEGER NOT NULL DEFAULT 1
                          CHECK(portal_aktiv IN (0,1)),
    einladung_gesendet_am TEXT,
    angelegt_am           TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
INSERT OR IGNORE INTO schema_version (version, beschreibung)
VALUES (41, 'Migration 41 – sv_portal_accounts: SV-Portal-Account-Verwaltung');
    """)
    logger.info("Migration 41 abgeschlossen.")
