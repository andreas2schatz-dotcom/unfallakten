"""
Tests fuer intake/queue.py (S1.6a).

Zustandsmaschine:
    neu -> laeuft -> bereit_zur_review   (Happy Path)
    neu -> laeuft -> neu (Retry mit Backoff, versuch_zaehler += 1)
                  -> pipeline_fehler (nach 3 Fehlversuchen)

Anforderungen aus dem Plan:
  * Backoff 1/5/30 Minuten.
  * Single-instance-Worker via ``worker_lease`` (F-10 — Gunicorn mit 4 Workern).
  * Abgelaufene Leases werden zurueckgesetzt (Poison-Instance-Fall).
  * Queue laeuft weiter (kein Poison-Pill-Blocking).
"""
import os
import sys
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class _BaseQueueTest(unittest.TestCase):
    def setUp(self):
        import uuid
        self._uid = uuid.uuid4().hex  # fuer eindeutige sha256-Werte pro Test
        fd, self._db_pfad = tempfile.mkstemp(prefix="queue_", suffix=".sqlite")
        os.close(fd)
        # DB_PATH ist Modul-Attribut in backend.db.database, gecacht beim Import.
        # Env-Var reicht nicht -> direkt patchen.
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _lege_dokument_an(self, sha256: str = None) -> int:
        from backend.db.database import get_connection
        # Eindeutige sha pro Test-Instanz, damit Test-DB nicht kollidiert
        sha = sha256 or (self._uid + "0" * (64 - len(self._uid)))
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente (sha256, queue_status) VALUES (?, 'neu')",
                (sha,),
            )
            return cur.lastrowid


class TestReservieren(_BaseQueueTest):
    def test_neues_dokument_wird_reserviert(self):
        from backend.intake.queue import reserviere_naechsten
        did = self._lege_dokument_an()
        job = reserviere_naechsten(worker_id="w1", lease_dauer_s=60)
        self.assertIsNotNone(job)
        self.assertEqual(job["id"], did)
        self.assertEqual(job["queue_status"], "laeuft")
        self.assertIn("w1", job["worker_lease"])

    def test_keine_arbeit_gibt_none(self):
        from backend.intake.queue import reserviere_naechsten
        self.assertIsNone(reserviere_naechsten(worker_id="w1", lease_dauer_s=60))

    def test_bereits_reservierter_nicht_doppelt(self):
        """Zweiter Worker bekommt None solange das Lease frisch ist."""
        from backend.intake.queue import reserviere_naechsten
        self._lege_dokument_an()
        first = reserviere_naechsten(worker_id="w1", lease_dauer_s=60)
        self.assertIsNotNone(first)
        second = reserviere_naechsten(worker_id="w2", lease_dauer_s=60)
        self.assertIsNone(second)

    def test_abgelaufenes_lease_wird_uebernommen(self):
        """Wenn Worker A abgestuerzt ist, uebernimmt Worker B nach Lease-Ablauf."""
        from backend.intake.queue import reserviere_naechsten
        from backend.db.database import get_connection

        did = self._lege_dokument_an()
        # A reserviert mit sehr kurzem Lease
        job_a = reserviere_naechsten(worker_id="w1", lease_dauer_s=1)
        self.assertIsNotNone(job_a)

        # Simuliere Lease-Ablauf durch manuellen Update
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET worker_lease = ? WHERE id=?",
                (f"w1|{_iso(datetime.now() - timedelta(seconds=10))}", did),
            )

        job_b = reserviere_naechsten(worker_id="w2", lease_dauer_s=60)
        self.assertIsNotNone(job_b, "Abgelaufenes Lease muss uebernommen werden")
        self.assertEqual(job_b["id"], did)
        self.assertIn("w2", job_b["worker_lease"])

    def test_naechster_versuch_in_zukunft_wird_ignoriert(self):
        """Backoff: solange naechster_versuch in Zukunft liegt, keine Reservierung."""
        from backend.intake.queue import reserviere_naechsten
        from backend.db.database import get_connection

        did = self._lege_dokument_an()
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET naechster_versuch=? WHERE id=?",
                (_iso(datetime.now() + timedelta(minutes=5)), did),
            )

        self.assertIsNone(reserviere_naechsten(worker_id="w1", lease_dauer_s=60))


class TestErfolg(_BaseQueueTest):
    def test_markiere_bereit_setzt_status(self):
        from backend.intake.queue import reserviere_naechsten, markiere_bereit
        from backend.db.database import get_connection

        did = self._lege_dokument_an()
        reserviere_naechsten(worker_id="w1", lease_dauer_s=60)
        markiere_bereit(did)

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, worker_lease, fehler_detail "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "bereit_zur_review")
        self.assertIsNone(row["worker_lease"])
        self.assertIsNone(row["fehler_detail"])


class TestFehler(_BaseQueueTest):
    def test_erster_fehler_geht_zurueck_auf_neu_mit_backoff(self):
        from backend.intake.queue import (
            reserviere_naechsten, markiere_fehler
        )
        from backend.db.database import get_connection

        did = self._lege_dokument_an()
        reserviere_naechsten(worker_id="w1", lease_dauer_s=60)
        markiere_fehler(did, fehler_meldung="Boom 1")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, versuch_zaehler, naechster_versuch, "
                "fehler_detail, worker_lease FROM intake_dokumente WHERE id=?",
                (did,),
            ).fetchone()
        self.assertEqual(row["queue_status"], "neu")
        self.assertEqual(row["versuch_zaehler"], 1)
        self.assertIsNotNone(row["naechster_versuch"])
        self.assertEqual(row["fehler_detail"], "Boom 1")
        self.assertIsNone(row["worker_lease"])

    def test_dritter_fehler_landet_auf_pipeline_fehler(self):
        from backend.intake.queue import (
            reserviere_naechsten, markiere_fehler
        )
        from backend.db.database import get_connection

        did = self._lege_dokument_an()
        for i in range(3):
            # zaehler bei jedem Retry manuell zuruecksetzen, damit reserviere klappt
            with get_connection() as conn:
                conn.execute(
                    "UPDATE intake_dokumente SET queue_status='neu', "
                    "naechster_versuch=NULL WHERE id=?", (did,))
            reserviere_naechsten(worker_id="w1", lease_dauer_s=60)
            markiere_fehler(did, fehler_meldung=f"Boom {i+1}")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, versuch_zaehler, fehler_detail "
                "FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "pipeline_fehler")
        self.assertEqual(row["versuch_zaehler"], 3)
        self.assertEqual(row["fehler_detail"], "Boom 3")

    def test_pipeline_fehler_blockiert_nicht_naechstes_dokument(self):
        from backend.intake.queue import (
            reserviere_naechsten, markiere_fehler
        )
        d1 = self._lege_dokument_an(self._uid + "1" * (64 - len(self._uid)))
        d2 = self._lege_dokument_an(self._uid + "2" * (64 - len(self._uid)))

        # d1 durch 3 Fehler in pipeline_fehler bringen
        from backend.db.database import get_connection
        for i in range(3):
            with get_connection() as conn:
                conn.execute(
                    "UPDATE intake_dokumente SET queue_status='neu', "
                    "naechster_versuch=NULL WHERE id=?", (d1,))
            reserviere_naechsten(worker_id="w1", lease_dauer_s=60)
            markiere_fehler(d1, fehler_meldung=f"x{i}")

        # d2 muss weiter reservierbar sein
        job = reserviere_naechsten(worker_id="w1", lease_dauer_s=60)
        self.assertIsNotNone(job)
        self.assertEqual(job["id"], d2)


class TestEnqueue(_BaseQueueTest):
    def test_enqueue_setzt_status_und_faelligkeit(self):
        """enqueue(id) macht ein Dokument sofort faellig, unabhaengig von Backoff."""
        from backend.intake.queue import enqueue
        from backend.db.database import get_connection

        did = self._lege_dokument_an()
        with get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET queue_status='pipeline_fehler', "
                "naechster_versuch=?, versuch_zaehler=3 WHERE id=?",
                (_iso(datetime.now() + timedelta(hours=1)), did),
            )
        enqueue(did)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT queue_status, versuch_zaehler, naechster_versuch, "
                "worker_lease FROM intake_dokumente WHERE id=?", (did,)
            ).fetchone()
        self.assertEqual(row["queue_status"], "neu")
        self.assertEqual(row["versuch_zaehler"], 0)
        self.assertIsNone(row["naechster_versuch"])
        self.assertIsNone(row["worker_lease"])


if __name__ == "__main__":
    unittest.main()
