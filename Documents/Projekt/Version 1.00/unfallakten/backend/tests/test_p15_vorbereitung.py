"""
Tests fuer P1.5-Vorbereitung:
  * ersetzt_positions_ids in schreibe_ereignis (K-M2a).
  * pruefe_doppelerfassung() Helper.
  * rechnungstyp_mapping in der Positionsmodell-Registry.

Testkriterien aus dem P1.5-Prompt:
  (b) Doppelerfassung erzeugt keine Doppel-Ereignisse.
  (c) K-M2a: Ergaenzungsgutachten ersetzt nur die betroffenen Positions-
      Zeilen; unveraenderte Positionen bleiben aktuell.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _EreignisTestBasis(unittest.TestCase):
    """Standard-Setup: temporaere SQLite + eine Akte 44/22."""

    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15v_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass


class TestErsetztPositionsIds(_EreignisTestBasis):
    """K-M2a — Ergaenzungsgutachten ersetzt einzelne Positionszeilen."""

    def test_ersetzt_positions_ids_setzt_ersetzt_durch_an_alt_position(self):
        from backend.services.ereignis_service import schreibe_ereignis
        from backend.db.database import get_connection

        alt_id = schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-04-30",
            positionen=[
                {"position_key": "reparaturkosten",
                 "wirkung": "gefordert", "betrag": 5000.0},
                {"position_key": "wertminderung",
                 "wirkung": "gefordert", "betrag": 500.0},
            ],
        )
        with get_connection() as conn:
            pos_rows = conn.execute(
                "SELECT id, position_key FROM ereignis_positionen "
                "WHERE ereignis_id=? ORDER BY position_key", (alt_id,)
            ).fetchall()
            alt_pos = {r["position_key"]: r["id"] for r in pos_rows}

        # Ergaenzungsgutachten aendert NUR reparaturkosten.
        neu_id = schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-05-15",
            positionen=[
                {"position_key": "reparaturkosten",
                 "wirkung": "gefordert", "betrag": 6200.0},
            ],
            ersetzt_positions_ids=[alt_pos["reparaturkosten"]],
        )

        with get_connection() as conn:
            # Alt-Kopf bleibt aktuell (nicht ersetzt).
            alt_kopf = conn.execute(
                "SELECT ersetzt_durch FROM ereignisse WHERE id=?", (alt_id,)
            ).fetchone()
            # Alt-reparaturkosten-Zeile ist positionsscharf ersetzt.
            alt_rep = conn.execute(
                "SELECT ersetzt_durch FROM ereignis_positionen WHERE id=?",
                (alt_pos["reparaturkosten"],),
            ).fetchone()
            # Alt-wertminderung-Zeile bleibt aktuell.
            alt_wm = conn.execute(
                "SELECT ersetzt_durch FROM ereignis_positionen WHERE id=?",
                (alt_pos["wertminderung"],),
            ).fetchone()
            # Cache-Zustaende.
            cache = conn.execute(
                "SELECT ereignis_id, position_key, status "
                "FROM position_ereignis_cache "
                "WHERE akte_az='44/22' ORDER BY ereignis_id, position_key"
            ).fetchall()

        self.assertIsNone(
            alt_kopf["ersetzt_durch"],
            "Bei ersetzt_positions_ids darf der Alt-Kopf NICHT als ersetzt "
            "markiert werden (nur positionsscharf).",
        )
        self.assertIsNotNone(alt_rep["ersetzt_durch"])
        self.assertIsNone(alt_wm["ersetzt_durch"])
        cache_map = {
            (r["ereignis_id"], r["position_key"]): r["status"] for r in cache
        }
        self.assertEqual(cache_map[(alt_id, "reparaturkosten")], "ersetzt")
        self.assertEqual(cache_map[(alt_id, "wertminderung")], "aktuell")
        self.assertEqual(cache_map[(neu_id, "reparaturkosten")], "aktuell")

    def test_ersetzt_positions_ids_und_ersetzt_kopf_id_ist_typerror(self):
        from backend.services.ereignis_service import schreibe_ereignis
        with self.assertRaises(TypeError):
            schreibe_ereignis(
                akte_az="44/22", ereignistyp="gutachten_eingegangen",
                quelle="dokument", datum="2022-05-15",
                positionen=[{"position_key": "reparaturkosten",
                             "wirkung": "gefordert", "betrag": 6200.0}],
                ersetzt_kopf_id=1,
                ersetzt_positions_ids=[1],
            )

    def test_ableitung_ignoriert_ersetzte_position(self):
        """POSITIONSMODELL 4.3 Ableitungs-Invariante: ersetzte Cache-Zeilen
        fliessen NICHT in die Ableitung ein."""
        from backend.services.ereignis_service import schreibe_ereignis
        from backend.services.positionsstatus_service import (
            leite_positionsstatus_ab,
        )
        from backend.db.database import get_connection

        alt_id = schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-04-30",
            dokument_id=None,
            positionen=[
                {"position_key": "reparaturkosten",
                 "wirkung": "gefordert", "betrag": 5000.0},
                {"position_key": "wertminderung",
                 "wirkung": "gefordert", "betrag": 500.0},
            ],
        )
        with get_connection() as conn:
            alt_rep_id = conn.execute(
                "SELECT id FROM ereignis_positionen "
                "WHERE ereignis_id=? AND position_key='reparaturkosten'",
                (alt_id,),
            ).fetchone()["id"]

        schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-05-15",
            positionen=[
                {"position_key": "reparaturkosten",
                 "wirkung": "gefordert", "betrag": 6200.0},
            ],
            ersetzt_positions_ids=[alt_rep_id],
        )

        status = leite_positionsstatus_ab("44/22")
        # Neue reparaturkosten fliessen ein.
        self.assertEqual(status["reparaturkosten"]["gefordert"], 6200.0)
        # Alte wertminderung bleibt aktuell -- muss weiter zu sehen sein.
        self.assertEqual(status["wertminderung"]["gefordert"], 500.0)


class TestDoppelerfassungsGuard(_EreignisTestBasis):
    """Helper `pruefe_doppelerfassung()` verhindert Doppel-Ereignisse."""

    def test_kein_ereignis_kein_konflikt(self):
        from backend.services.ereignis_service import pruefe_doppelerfassung
        vorhandene = pruefe_doppelerfassung(
            akte_az="44/22",
            dokument_id=123,
            ereignistyp="abrechnung_eingegangen",
        )
        self.assertIsNone(vorhandene)

    def test_existierendes_ereignis_wird_gefunden(self):
        from backend.services.ereignis_service import (
            schreibe_ereignis, pruefe_doppelerfassung,
        )
        alt_id = schreibe_ereignis(
            akte_az="44/22", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2022-05-10", dokument_id=123,
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "anerkannt", "betrag": 4100.0}],
        )
        vorhandene = pruefe_doppelerfassung(
            akte_az="44/22",
            dokument_id=123,
            ereignistyp="abrechnung_eingegangen",
        )
        self.assertEqual(vorhandene, alt_id)

    def test_null_dokument_id_liefert_none(self):
        """WDM-Ereignisse haben dokument_id=NULL -- der Guard darf NULL
        nicht wie 'gleicher Dok' behandeln, sonst wuerde eine WDM-
        Registrierung eine ReguWizard-Registrierung ohne dokument_id
        faelschlich fangen."""
        from backend.services.ereignis_service import (
            schreibe_ereignis, pruefe_doppelerfassung,
        )
        schreibe_ereignis(
            akte_az="44/22", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2022-05-10", dokument_id=None,
            herkunft="wdm",
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "anerkannt", "betrag": 4100.0}],
        )
        vorhandene = pruefe_doppelerfassung(
            akte_az="44/22",
            dokument_id=None,
            ereignistyp="abrechnung_eingegangen",
        )
        self.assertIsNone(vorhandene)

    def test_anderer_ereignistyp_kein_konflikt(self):
        from backend.services.ereignis_service import (
            schreibe_ereignis, pruefe_doppelerfassung,
        )
        schreibe_ereignis(
            akte_az="44/22", ereignistyp="gutachten_eingegangen",
            quelle="dokument", datum="2022-04-30", dokument_id=123,
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "gefordert", "betrag": 5000.0}],
        )
        # Anderer Ereignistyp fuer dasselbe Dokument -> kein Konflikt.
        vorhandene = pruefe_doppelerfassung(
            akte_az="44/22",
            dokument_id=123,
            ereignistyp="abrechnung_eingegangen",
        )
        self.assertIsNone(vorhandene)

    def test_ersetztes_ereignis_zaehlt_nicht_als_bestehend(self):
        """Nach Kopf-Ersetzung (K-M2b) darf der Guard das Alt-Ereignis
        nicht als bestehend melden -- sonst blockiert der Guard das
        naechste Update."""
        from backend.services.ereignis_service import (
            schreibe_ereignis, pruefe_doppelerfassung,
        )
        alt_id = schreibe_ereignis(
            akte_az="44/22", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2022-05-10", dokument_id=123,
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "anerkannt", "betrag": 4100.0}],
        )
        schreibe_ereignis(
            akte_az="44/22", ereignistyp="abrechnung_eingegangen",
            quelle="dokument", datum="2022-05-11", dokument_id=123,
            positionen=[{"position_key": "reparaturkosten",
                         "wirkung": "anerkannt", "betrag": 4200.0}],
            ersetzt_kopf_id=alt_id,
        )
        # Beide bestehen, aber das alt ist ersetzt -> das neue ist aktuell.
        # Guard darf ID des NEUEN, aktuellen Ereignisses liefern (nicht des
        # ersetzten), damit ein weiterer Update-Aufruf wieder ersetzt.
        vorhandene = pruefe_doppelerfassung(
            akte_az="44/22",
            dokument_id=123,
            ereignistyp="abrechnung_eingegangen",
        )
        self.assertIsNotNone(vorhandene)
        self.assertNotEqual(vorhandene, alt_id)


class TestRechnungstypMapping(unittest.TestCase):
    """Die Registry stellt Dokumentklasse -> position_key bereit (aus zwei
    hartkodierten Kopien in belege_routes.py + constants.js konsolidiert)."""

    def test_registry_exponiert_rechnungstyp_mapping(self):
        from backend.services.positionsmodell_registry import (
            lade_positionsmodell,
        )
        reg = lade_positionsmodell(reload=True)
        # Mindestens die 5 alten Klassen sollten abgedeckt sein.
        self.assertIn("rechnungstyp_mapping", reg.__dict__)
        mapping = reg.rechnungstyp_mapping
        # Diese Klassen kamen aus dem alten _KLASSE_POSITION_MAP.
        self.assertIn("abschlepprechnung", mapping)
        self.assertIn("standkostenrechnung", mapping)
        self.assertIn("reparaturrechnung", mapping)
        self.assertIn("mietwagenrechnung", mapping)
        self.assertIn("sv_rechnung", mapping)

    def test_alle_ziel_position_keys_existieren_in_positionsarten(self):
        """Konsistenzcheck: jedes Ziel-position_key muss in positionsarten
        vorhanden sein -- damit die YAML nicht auf Phantasie-Keys zeigt."""
        from backend.services.positionsmodell_registry import (
            lade_positionsmodell,
        )
        reg = lade_positionsmodell(reload=True)
        for klasse, ziel in reg.rechnungstyp_mapping.items():
            if ziel == "__sv_kosten_vorsteuer__":
                # Sonder-Marker, wird zur Laufzeit aufgeloest.
                continue
            self.assertIn(
                ziel, reg.positionsarten,
                f"rechnungstyp_mapping[{klasse!r}]={ziel!r} "
                "nicht in positionsarten.yaml",
            )


if __name__ == "__main__":
    unittest.main()
