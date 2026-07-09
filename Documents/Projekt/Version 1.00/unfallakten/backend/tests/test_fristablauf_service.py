"""
Tests fuer backend/services/fristablauf_service.py (P1.6).

verarbeite_faellige_todos() liest fristen_service-todos (quelle='system')
und schreibt je faelliger, offener todo genau EIN Ereignis
``fristablauf`` (richtung=intern, quelle=system):

  * Verjaehrung / PflVG-Fristen -> Akten-Scope-Ereignis (keine Positionen,
    dokument_id=NULL).
  * antwort_2w_{dok_id} -> Positionen aus dem auslösenden ausgehenden
    Ereignis desselben Dokuments (stellungnahme_generiert /
    forderung_generiert / sachstandsanfrage_generiert), Wirkung 'keine',
    dokument_id=<dok_id des todo>.

Idempotenz-Anker: neue Spalte ``todos.fristablauf_ereignis_id`` (Mig 52).
Zweiter Lauf erzeugt keine Duplikate.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _insert_todo(conn, *, akte_az, text, faellig_am, frist_typ, regel_key,
                  quelle="system", erledigt=0, dok_id=None):
    conn.execute(
        "INSERT INTO todos "
        "(akte_az, text, faellig_am, frist_typ, quelle, regel_key, "
        " erledigt, dok_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (akte_az, text, faellig_am, frist_typ, quelle, regel_key,
         erledigt, dok_id),
    )
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


class TestFristablaufService(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p16_", suffix=".sqlite")
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

    # ── Akten-Scope: Verjaehrung ──────────────────────────────────────

    def test_verjaehrung_faellig_erzeugt_akten_scope_ereignis(self):
        from backend.db.database import get_connection
        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )

        gestern = (date.today() - timedelta(days=1)).isoformat()
        with get_connection() as conn:
            todo_id = _insert_todo(
                conn, akte_az="44/22",
                text="Verjaehrung heute", faellig_am=gestern,
                frist_typ="verjaehrung", regel_key="verjaehrung",
            )

        anzahl = verarbeite_faellige_todos()
        self.assertEqual(anzahl, 1)

        with get_connection() as conn:
            ev = conn.execute(
                "SELECT id, ereignistyp, richtung, quelle, dokument_id, "
                "       akte_az "
                "FROM ereignisse"
            ).fetchall()
            pos = conn.execute(
                "SELECT COUNT(*) AS n FROM ereignis_positionen"
            ).fetchone()
            todo = conn.execute(
                "SELECT fristablauf_ereignis_id FROM todos WHERE id=?",
                (todo_id,),
            ).fetchone()

        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["ereignistyp"], "fristablauf")
        self.assertEqual(ev[0]["richtung"], "intern")
        self.assertEqual(ev[0]["quelle"], "system")
        self.assertIsNone(ev[0]["dokument_id"])
        self.assertEqual(ev[0]["akte_az"], "44/22")
        self.assertEqual(pos["n"], 0)
        self.assertEqual(todo["fristablauf_ereignis_id"], ev[0]["id"])

    # ── Dokument-Scope: antwort_2w_{dok_id} ───────────────────────────

    def test_antwort_2w_kopiert_positionen_aus_auslösendem_ereignis(self):
        from backend.db.database import get_connection
        from backend.services.ausgehende_ereignisse import erzeuge
        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )

        # Auslösendes ausgehendes Ereignis (Forderungsschreiben)
        # zum Dokument 42, mit zwei Positionen.
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, dateiname, dateipfad, "
                " typ, dokumentenklasse, hochgeladen_am) "
                "VALUES (42, '44/22', 'fs.docx', '/tmp/fs.docx', "
                " 'forderungsschreiben', 'forderungsschreiben', '2026-05-01')"
            )
        forderung_id = erzeuge(
            akte_az="44/22",
            ereignistyp="forderung_generiert",
            dokument_id=42,
            positionen={"reparaturkosten": 5000.0, "wertminderung": 500.0},
            datum="2026-05-01",
        )
        self.assertIsInstance(forderung_id, int)

        # Faellige antwort_2w-Frist auf Dok 42
        gestern = (date.today() - timedelta(days=1)).isoformat()
        with get_connection() as conn:
            _insert_todo(
                conn, akte_az="44/22",
                text="Antwort ausstehend: Forderung vom 01.05.2026",
                faellig_am=gestern,
                frist_typ="antwort_2w", regel_key="antwort_2w_42", dok_id=42,
            )

        anzahl = verarbeite_faellige_todos()
        self.assertEqual(anzahl, 1)

        with get_connection() as conn:
            fa_ev = conn.execute(
                "SELECT id, dokument_id FROM ereignisse "
                "WHERE ereignistyp='fristablauf'"
            ).fetchone()
            pos = conn.execute(
                "SELECT position_key, wirkung "
                "FROM ereignis_positionen WHERE ereignis_id=?",
                (fa_ev["id"],),
            ).fetchall()

        self.assertEqual(fa_ev["dokument_id"], 42)
        keys = {r["position_key"] for r in pos}
        self.assertEqual(keys, {"reparaturkosten", "wertminderung"})
        for r in pos:
            self.assertEqual(r["wirkung"], "keine",
                              "Fristablauf hat wirkung 'keine' (dokumentarisch).")

    # ── Idempotenz ────────────────────────────────────────────────────

    def test_zweiter_lauf_erzeugt_kein_duplikat(self):
        from backend.db.database import get_connection
        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )

        gestern = (date.today() - timedelta(days=1)).isoformat()
        with get_connection() as conn:
            _insert_todo(
                conn, akte_az="44/22",
                text="Verjaehrung heute", faellig_am=gestern,
                frist_typ="verjaehrung", regel_key="verjaehrung",
            )

        self.assertEqual(verarbeite_faellige_todos(), 1)
        self.assertEqual(verarbeite_faellige_todos(), 0)

        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse "
                "WHERE ereignistyp='fristablauf'"
            ).fetchone()[0]
        self.assertEqual(n, 1)

    # ── Filter: nicht-faellig / erledigt / benutzer-Quelle ────────────

    def test_zukuenftige_frist_wird_ignoriert(self):
        from backend.db.database import get_connection
        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )

        morgen = (date.today() + timedelta(days=1)).isoformat()
        with get_connection() as conn:
            _insert_todo(
                conn, akte_az="44/22",
                text="Verjaehrung morgen", faellig_am=morgen,
                frist_typ="verjaehrung", regel_key="verjaehrung",
            )

        self.assertEqual(verarbeite_faellige_todos(), 0)

    def test_erledigte_todo_wird_ignoriert(self):
        from backend.db.database import get_connection
        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )

        gestern = (date.today() - timedelta(days=1)).isoformat()
        with get_connection() as conn:
            _insert_todo(
                conn, akte_az="44/22",
                text="Verjaehrung gestern", faellig_am=gestern,
                frist_typ="verjaehrung", regel_key="verjaehrung",
                erledigt=1,
            )

        self.assertEqual(verarbeite_faellige_todos(), 0)

    def test_benutzer_quelle_wird_ignoriert(self):
        from backend.db.database import get_connection
        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )

        gestern = (date.today() - timedelta(days=1)).isoformat()
        with get_connection() as conn:
            _insert_todo(
                conn, akte_az="44/22",
                text="Manuelles Todo", faellig_am=gestern,
                frist_typ="benutzer", regel_key=None,
                quelle="benutzer",
            )

        self.assertEqual(verarbeite_faellige_todos(), 0)

    # ── Robustheit: antwort_2w ohne auslösendes Ereignis ─────────────

    def test_antwort_2w_ohne_auslösendes_ereignis_bleibt_akten_scope(self):
        """Fehlt das auslösende Ereignis (z. B. Alt-Bestand vor P1.4),
        entsteht ein Fristablauf mit dokument_id (fuer Nachvollziehbarkeit),
        aber ohne Positionsbezug."""
        from backend.db.database import get_connection
        from backend.services.fristablauf_service import (
            verarbeite_faellige_todos,
        )

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO dokumente (id, akte_id, dateiname, dateipfad, "
                " typ, dokumentenklasse, hochgeladen_am) "
                "VALUES (99, '44/22', 'x.docx', '/tmp/x.docx', "
                " 'forderungsschreiben', 'forderungsschreiben', '2026-05-01')"
            )

        gestern = (date.today() - timedelta(days=1)).isoformat()
        with get_connection() as conn:
            _insert_todo(
                conn, akte_az="44/22",
                text="Antwort ausstehend zu Dok 99", faellig_am=gestern,
                frist_typ="antwort_2w", regel_key="antwort_2w_99", dok_id=99,
            )

        anzahl = verarbeite_faellige_todos()
        self.assertEqual(anzahl, 1)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, dokument_id FROM ereignisse "
                "WHERE ereignistyp='fristablauf'"
            ).fetchone()
            n_pos = conn.execute(
                "SELECT COUNT(*) FROM ereignis_positionen "
                "WHERE ereignis_id=?", (row["id"],),
            ).fetchone()[0]
        self.assertEqual(row["dokument_id"], 99)
        self.assertEqual(n_pos, 0)


if __name__ == "__main__":
    unittest.main()
