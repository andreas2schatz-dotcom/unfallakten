import importlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import fitz  # PyMuPDF
from backend.intake import split_service as ss

_tmp = tempfile.mkdtemp(prefix="split_svc_")


def _mehrseitiges_pdf(n: int) -> bytes:
    doc = fitz.open()
    for i in range(n):
        page = doc.new_page()
        page.insert_text((72, 72), f"Seite {i + 1}")
    out = doc.tobytes()
    doc.close()
    return out


def _setup_db(name):
    db_path = os.path.join(_tmp, f"{name}.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    os.environ["INTAKE_ARCHIV_ROOT"] = os.path.join(_tmp, f"archiv_{name}")
    import backend.db.database as db_mod
    import backend.db.schema_manager as sm
    importlib.reload(db_mod)
    importlib.reload(sm)
    sm.init_db()
    return db_mod


def _lege_original_an(db_mod, pdf_bytes, queue_status="bereit_zur_review",
                       payload_typ="datei", mit_zustellung=True):
    from backend.intake._persistenz import (
        oder_intake_dokument_fuer_datei, erzeuge_zustellung)
    intake_id, _sha = oder_intake_dokument_fuer_datei(pdf_bytes, "pdf")
    with db_mod.get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET queue_status=?, payload_typ=? WHERE id=?",
            (queue_status, payload_typ, intake_id))
    if mit_zustellung:
        erzeuge_zustellung(
            intake_id, "imap", absender="schaden@versicherer.de",
            betreff="Sammel-Anlage", empfangen_am="2026-07-15T09:00:00",
            signale={"az": "44/22"}, roh_referenz="msg-1")
    return intake_id


class TestPdfPrimitive(unittest.TestCase):
    def test_seiten_zahl(self):
        self.assertEqual(ss.pdf_seiten_zahl(_mehrseitiges_pdf(5)), 5)

    def test_extrahiere_seiten_pdf(self):
        teil = ss.extrahiere_seiten_pdf(_mehrseitiges_pdf(5), 1, 3)
        self.assertEqual(ss.pdf_seiten_zahl(teil), 3)
        teil2 = ss.extrahiere_seiten_pdf(_mehrseitiges_pdf(5), 4, 5)
        self.assertEqual(ss.pdf_seiten_zahl(teil2), 2)

    def test_rendere_thumbnail_ist_png(self):
        png = ss.rendere_thumbnail(_mehrseitiges_pdf(2), 1)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))


class TestValidiereGruppen(unittest.TestCase):
    def test_gueltig(self):
        ss.validiere_gruppen([[1, 2, 3], [4, 5]], 5)  # kein Fehler

    def test_zu_wenige_gruppen(self):
        with self.assertRaises(ss.SplitFehler) as ctx:
            ss.validiere_gruppen([[1, 2, 3, 4, 5]], 5)
        self.assertEqual(ctx.exception.status, 422)

    def test_luecke(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2], [4, 5]], 5)  # 3 fehlt

    def test_ueberdeckung_falsch(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2], [3, 4]], 5)  # 5 fehlt

    def test_nicht_zusammenhaengend(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 3], [2, 4, 5]], 5)

    def test_leere_gruppe(self):
        with self.assertRaises(ss.SplitFehler):
            ss.validiere_gruppen([[1, 2, 3], []], 5)


class TestTeileDokument(unittest.TestCase):
    def test_split_legt_teile_an_und_markiert_original(self):
        db_mod = _setup_db("happy")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(5))

        kinder = ss.teile_dokument(oid, [[1, 2, 3], [4, 5]], benutzer_id=7)

        self.assertEqual(len(kinder), 2)
        with db_mod.get_connection() as conn:
            for kid in kinder:
                row = conn.execute(
                    "SELECT queue_status, payload_typ, aufgeteilt_aus_id "
                    "FROM intake_dokumente WHERE id=?", (kid,)).fetchone()
                self.assertEqual(row["queue_status"], "neu")
                self.assertEqual(row["payload_typ"], "datei")
                self.assertEqual(row["aufgeteilt_aus_id"], oid)
                z = conn.execute(
                    "SELECT absender, signale_json, roh_referenz FROM zustellungen "
                    "WHERE intake_dokument_id=?", (kid,)).fetchone()
                self.assertEqual(z["absender"], "schaden@versicherer.de")
                self.assertIn("44/22", z["signale_json"])
                self.assertEqual(z["roh_referenz"], f"split:{oid}")
            orig = conn.execute(
                "SELECT verworfen_grund, verworfen_am, verworfen_von "
                "FROM intake_dokumente WHERE id=?", (oid,)).fetchone()
            self.assertEqual(orig["verworfen_grund"], "aufgeteilt")
            self.assertIsNotNone(orig["verworfen_am"])
            self.assertEqual(orig["verworfen_von"], 7)

    def test_teil_seitenzahl_stimmt(self):
        db_mod = _setup_db("seiten")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(5))
        kinder = ss.teile_dokument(oid, [[1, 2, 3], [4, 5]], benutzer_id=None)
        with db_mod.get_connection() as conn:
            pfade = [conn.execute(
                "SELECT arbeitskopie_pfad FROM intake_dokumente WHERE id=?",
                (k,)).fetchone()["arbeitskopie_pfad"] for k in kinder]
        with open(pfade[0], "rb") as f:
            self.assertEqual(ss.pdf_seiten_zahl(f.read()), 3)
        with open(pfade[1], "rb") as f:
            self.assertEqual(ss.pdf_seiten_zahl(f.read()), 2)

    def test_text_payload_wird_abgelehnt(self):
        db_mod = _setup_db("text")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(3), payload_typ="text")
        with self.assertRaises(ss.SplitFehler) as ctx:
            ss.teile_dokument(oid, [[1, 2], [3]], benutzer_id=None)
        self.assertEqual(ctx.exception.status, 422)

    def test_doppel_split_ist_409(self):
        db_mod = _setup_db("doppel")
        oid = _lege_original_an(db_mod, _mehrseitiges_pdf(4))
        ss.teile_dokument(oid, [[1, 2], [3, 4]], benutzer_id=None)
        with self.assertRaises(ss.SplitFehler) as ctx:
            ss.teile_dokument(oid, [[1, 2], [3, 4]], benutzer_id=None)
        self.assertEqual(ctx.exception.status, 409)


if __name__ == "__main__":
    unittest.main()
