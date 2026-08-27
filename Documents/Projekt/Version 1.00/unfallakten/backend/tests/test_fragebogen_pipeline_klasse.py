"""Die Pipeline erkennt einen Unfallbogen am Payload und stempelt die
Klasse verbindlich -- unabhaengig vom Textklassifikator, der auf dem
JSON-Text nur 'sonstiges' liefern wuerde.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BOGEN = {
    "meta": {"formular": "unfallbogen", "version": "2.1"},
    "mandant": {"name": "Golovin", "vorname": "Paul",
                 "email": "paulgolovin@web.de"},
    "gegner": {"fahrzeug": {"kennzeichen": "MTK-DB801"}},
    "unfall": {"datum": "2026-08-03", "ort": "Mainhausen"},
    "sachschaden": {"eigenes_fahrzeug": {"kennzeichen": "WÜ PG 777"}},
}


def _setup_db(name):
    fd, pfad = tempfile.mkstemp(prefix=f"fbklasse_{name}_", suffix=".sqlite")
    os.close(fd)
    import backend.db.database as _db
    _db.DB_PATH = pfad
    os.environ["DB_PATH"] = pfad
    from backend.db.schema_manager import init_db
    init_db()
    return pfad


class TestFragebogenKlasse(unittest.TestCase):
    def setUp(self):
        _setup_db(self._testMethodName)
        from backend.db.database import get_connection
        self.get_connection = get_connection

    def _lege_text_dokument(self, text):
        with self.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente "
                "(sha256, payload_typ, structured_payload, queue_status) "
                "VALUES (?, 'text', ?, 'neu')",
                (f"sha-{len(text)}-{hash(text) & 0xffff}", text),
            )
            return cur.lastrowid

    def _verarbeite(self, intake_id):
        from backend.intake import pipeline
        with mock.patch.object(pipeline, "klassifiziere_stufe2",
                                return_value=("sonstiges", 0.5)), \
             mock.patch.object(pipeline, "extrahiere_felder",
                                return_value={"felder": {}}), \
             mock.patch("backend.intake.akten_matching._suche_in_ramicro",
                         return_value=[]):
            return pipeline.verarbeite_dokument(intake_id)

    def _klasse(self, intake_id):
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT klasse, klasse_quelle, konfidenz "
                "FROM intake_dokumente WHERE id=?", (intake_id,)
            ).fetchone()
        return dict(row)

    def test_bogen_bekommt_klasse_fragebogen(self):
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        self.assertTrue(self._verarbeite(iid))
        d = self._klasse(iid)
        self.assertEqual(d["klasse"], "fragebogen")
        self.assertEqual(d["klasse_quelle"], "fragebogen")
        self.assertEqual(d["konfidenz"], 1.0)

    def test_normale_email_bleibt_unveraendert(self):
        iid = self._lege_text_dokument("Sehr geehrte Damen und Herren,\n\n"
                                        "anbei die Rechnung.")
        self.assertTrue(self._verarbeite(iid))
        d = self._klasse(iid)
        self.assertEqual(d["klasse"], "sonstiges")
        self.assertEqual(d["klasse_quelle"], "auto")

    def test_manuelle_klasse_bleibt_bindend(self):
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE intake_dokumente SET klasse='gutachten', "
                "klasse_quelle='manuell' WHERE id=?", (iid,))
        self.assertTrue(self._verarbeite(iid))
        self.assertEqual(self._klasse(iid)["klasse"], "gutachten")

    def test_reparse_haelt_die_klasse(self):
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        self._verarbeite(iid)
        self._verarbeite(iid)
        self.assertEqual(self._klasse(iid)["klasse"], "fragebogen")

    def test_signale_erreichen_das_matching(self):
        from backend.intake import pipeline
        iid = self._lege_text_dokument(json.dumps(BOGEN, ensure_ascii=False))
        gesehen = {}

        def _merke(text, signale):
            gesehen["signale"] = list(signale)
            return []

        with mock.patch.object(pipeline, "klassifiziere_stufe2",
                                return_value=("sonstiges", 0.5)), \
             mock.patch.object(pipeline, "extrahiere_felder",
                                return_value={"felder": {}}), \
             mock.patch.object(pipeline, "finde_kandidaten", _merke):
            pipeline.verarbeite_dokument(iid)

        zusammen = {k: v for s in gesehen["signale"] for k, v in s.items()}
        self.assertEqual(zusammen["mandant_email"], "paulgolovin@web.de")
        self.assertEqual(zusammen["kfz_mandant"], "WÜPG777")
        self.assertEqual(zusammen["unfalltag"], "2026-08-03")


if __name__ == "__main__":
    unittest.main()
