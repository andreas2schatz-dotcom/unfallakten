"""
Tests fuer intake/archiv.py (S1.2).

Anforderungen aus PIPELINE-REFACTORING-PLAN.md S1.2:
  * Original hash-adressiert unter ``uploads/originale/<sha256[:2]>/<sha256>.<ext>``
    ablegen (write-once: existiert Datei, wird nie geschrieben).
  * Arbeitskopie erzeugen: PDF = Kopie; DOCX -> PDF via LibreOffice-headless
    (word_service-Muster); JPG/PNG -> PDF via PyMuPDF; HEIC vertagt.
  * Kein bestehender Pfad wird umgestellt.
  * Testkriterien: Idempotenz (zweite Ablage desselben Hashs = No-Op);
    DOCX/JPG-Testdateien ergeben lesbare PDF-Arbeitskopie; Original-Bytes
    nach Normalisierung unveraendert (Hash-Vergleich).
"""
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _minimales_pdf_bytes() -> bytes:
    """Erzeugt ein minimales, valides PDF via PyMuPDF."""
    import fitz
    doc = fitz.open()
    doc.new_page(width=100, height=100)
    return doc.write()


def _minimales_jpg_bytes() -> bytes:
    """Erzeugt 1x1 JPEG via Pillow."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="white").save(buf, format="JPEG")
    return buf.getvalue()


def _minimales_png_bytes() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="black").save(buf, format="PNG")
    return buf.getvalue()


class _BaseArchivTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="archiv_test_")
        # Original- und Arbeitskopien-Wurzeln liegen unter dem tmp-Root.
        os.environ["INTAKE_ARCHIV_ROOT"] = self._tmp

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)
        os.environ.pop("INTAKE_ARCHIV_ROOT", None)


class TestOriginalAblage(_BaseArchivTest):
    """Hash-adressierte, write-once Ablage der Originaldatei."""

    def test_ablage_pfad_folgt_hash_konvention(self):
        from backend.intake.archiv import lege_original_ab
        daten = b"test-daten-abc"
        sha = _sha256(daten)
        pfad = lege_original_ab(daten, ext="pdf")
        self.assertTrue(pfad.endswith(f"{sha[:2]}/{sha}.pdf") or
                        pfad.endswith(f"{sha[:2]}\\{sha}.pdf"),
                        f"Pfad folgt nicht der Konvention <sha[:2]>/<sha>.<ext>: {pfad}")
        self.assertTrue(os.path.isfile(pfad))

    def test_ablage_erhaelt_original_bytes(self):
        """Original-Bytes nach Ablage unveraendert (Hash-Vergleich)."""
        from backend.intake.archiv import lege_original_ab
        daten = b"beliebige binary bytes \x00\x01\x02\xff"
        sha_vor = _sha256(daten)
        pfad = lege_original_ab(daten, ext="pdf")
        with open(pfad, "rb") as f:
            sha_nach = _sha256(f.read())
        self.assertEqual(sha_vor, sha_nach, "Original-Bytes wurden veraendert")

    def test_ablage_gibt_sha256_zurueck(self):
        """lege_original_ab liefert (pfad, sha256)."""
        from backend.intake.archiv import lege_original_ab
        daten = b"foo"
        pfad = lege_original_ab(daten, ext="pdf")
        # sha256("foo") ist bekannt
        expected_sha = hashlib.sha256(b"foo").hexdigest()
        self.assertIn(expected_sha, pfad,
                      "Der sha256 muss im Zielpfad enthalten sein")

    def test_ablage_idempotent_gleiche_bytes(self):
        """Zweiter Aufruf mit gleichen Bytes = No-Op (Datei nicht neu geschrieben)."""
        from backend.intake.archiv import lege_original_ab
        daten = b"stable-content"
        pfad1 = lege_original_ab(daten, ext="pdf")
        mtime1 = os.path.getmtime(pfad1)

        # Kleiner Sleep, damit sich mtime unterscheiden koennte, falls Datei neu geschrieben wird.
        import time
        time.sleep(0.05)

        pfad2 = lege_original_ab(daten, ext="pdf")
        mtime2 = os.path.getmtime(pfad2)

        self.assertEqual(pfad1, pfad2, "Zweiter Aufruf liefert anderen Pfad — write-once verletzt")
        self.assertEqual(mtime1, mtime2, "Datei wurde neu geschrieben — write-once verletzt")

    def test_ablage_verschiedene_bytes_verschiedene_pfade(self):
        from backend.intake.archiv import lege_original_ab
        p1 = lege_original_ab(b"a", ext="pdf")
        p2 = lege_original_ab(b"b", ext="pdf")
        self.assertNotEqual(p1, p2)


class TestArbeitskopiePdf(_BaseArchivTest):
    """PDF-Eingang: Arbeitskopie ist eine Kopie (kein Umbau)."""

    def test_pdf_arbeitskopie_ist_reine_kopie(self):
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        pdf = _minimales_pdf_bytes()
        original_pfad = lege_original_ab(pdf, ext="pdf")
        arbeit_pfad = erzeuge_arbeitskopie(original_pfad, quell_ext="pdf")
        self.assertTrue(arbeit_pfad.lower().endswith(".pdf"))
        with open(arbeit_pfad, "rb") as f:
            arbeit_bytes = f.read()
        self.assertEqual(arbeit_bytes, pdf, "PDF-Arbeitskopie muss byte-gleich zum Original sein")

    def test_pdf_arbeitskopie_idempotent(self):
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        pdf = _minimales_pdf_bytes()
        original_pfad = lege_original_ab(pdf, ext="pdf")
        p1 = erzeuge_arbeitskopie(original_pfad, quell_ext="pdf")
        p2 = erzeuge_arbeitskopie(original_pfad, quell_ext="pdf")
        self.assertEqual(p1, p2)


class TestArbeitskopieBilder(_BaseArchivTest):
    """JPG/PNG-Eingang: PyMuPDF wandelt in single-page PDF."""

    def _pruefe_arbeit_ist_lesbar_pdf(self, pfad):
        """Verifiziert dass die Arbeitskopie ein valides PDF ist (via PyMuPDF lesbar)."""
        import fitz
        with open(pfad, "rb") as f:
            head = f.read(4)
        self.assertEqual(head, b"%PDF", "Arbeitskopie hat keinen PDF-Header")
        doc = fitz.open(pfad)
        try:
            self.assertGreaterEqual(doc.page_count, 1)
        finally:
            doc.close()

    def test_jpg_arbeitskopie_ist_lesbares_pdf(self):
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        jpg = _minimales_jpg_bytes()
        original_pfad = lege_original_ab(jpg, ext="jpg")
        arbeit_pfad = erzeuge_arbeitskopie(original_pfad, quell_ext="jpg")
        self._pruefe_arbeit_ist_lesbar_pdf(arbeit_pfad)

    def test_png_arbeitskopie_ist_lesbares_pdf(self):
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        png = _minimales_png_bytes()
        original_pfad = lege_original_ab(png, ext="png")
        arbeit_pfad = erzeuge_arbeitskopie(original_pfad, quell_ext="png")
        self._pruefe_arbeit_ist_lesbar_pdf(arbeit_pfad)

    def test_bild_arbeitskopie_veraendert_original_nicht(self):
        """Nach Normalisierung muss die Originaldatei byte-identisch bleiben."""
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        jpg = _minimales_jpg_bytes()
        sha_vor = _sha256(jpg)
        original_pfad = lege_original_ab(jpg, ext="jpg")
        _ = erzeuge_arbeitskopie(original_pfad, quell_ext="jpg")
        with open(original_pfad, "rb") as f:
            sha_nach = _sha256(f.read())
        self.assertEqual(sha_vor, sha_nach)


def _soffice_verfuegbar() -> bool:
    """Fuer den DOCX-Test: prueft ob LibreOffice auf dem Host installiert ist."""
    for kandidat in ("soffice", "libreoffice"):
        if shutil.which(kandidat):
            return True
    for kandidat in (
        "/usr/bin/soffice", "/usr/bin/libreoffice",
        "/usr/local/bin/soffice",
    ):
        if os.path.exists(kandidat):
            return True
    return False


@unittest.skipUnless(_soffice_verfuegbar(),
                     "LibreOffice nicht installiert — DOCX-Test uebersprungen (laeuft im Docker)")
class TestArbeitskopieDocx(_BaseArchivTest):
    """DOCX-Eingang: LibreOffice-headless wandelt in PDF."""

    def _minimales_docx_bytes(self) -> bytes:
        """Nutzt python-docx (bereits in requirements) fuer eine minimale DOCX-Datei."""
        from docx import Document
        buf = io.BytesIO()
        doc = Document()
        doc.add_paragraph("Test")
        doc.save(buf)
        return buf.getvalue()

    def test_docx_arbeitskopie_ist_pdf(self):
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        docx = self._minimales_docx_bytes()
        original_pfad = lege_original_ab(docx, ext="docx")
        arbeit_pfad = erzeuge_arbeitskopie(original_pfad, quell_ext="docx")
        with open(arbeit_pfad, "rb") as f:
            self.assertEqual(f.read(4), b"%PDF")

    def test_docx_original_unveraendert(self):
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        docx = self._minimales_docx_bytes()
        sha_vor = _sha256(docx)
        original_pfad = lege_original_ab(docx, ext="docx")
        _ = erzeuge_arbeitskopie(original_pfad, quell_ext="docx")
        with open(original_pfad, "rb") as f:
            self.assertEqual(_sha256(f.read()), sha_vor)


class TestArbeitskopieVertagt(_BaseArchivTest):
    """HEIC ist vertagt bis Bedarf belegt."""

    def test_heic_wirft_notimplementederror(self):
        from backend.intake.archiv import lege_original_ab, erzeuge_arbeitskopie
        # Wir brauchen keine echten HEIC-Bytes — die Konvertierung wird abgelehnt,
        # bevor der Inhalt gelesen wird.
        original_pfad = lege_original_ab(b"fake-heic-content", ext="heic")
        with self.assertRaises(NotImplementedError):
            erzeuge_arbeitskopie(original_pfad, quell_ext="heic")


if __name__ == "__main__":
    unittest.main()
