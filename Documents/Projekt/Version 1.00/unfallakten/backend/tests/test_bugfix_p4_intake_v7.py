"""
Regressionstests fuer die P4-Bugs (BUG-20–30) des Intake-Pipeline-v7-Reviews.

Reine Performance-/Hygiene-Bugs. Jeder Test nagelt das Verhalten bzw. die
Signatur NACH dem Fix fest und ist vor dem Fix rot (Feld/Parameter/Duplikat
noch vorhanden).
"""
from __future__ import annotations

import dataclasses
import importlib
import inspect
from datetime import date


# ── BUG-25: Arbeitskopie-Set aus archiv._KONVERTER ableiten ───────────────
class TestBug25ArbeitskopieSet:
    def test_set_folgt_neuem_konverter(self):
        from backend.intake import archiv, _persistenz

        orig = archiv._KONVERTER
        try:
            archiv._KONVERTER = {**orig, "heic": orig["pdf"]}
            importlib.reload(_persistenz)
            assert "heic" in _persistenz._ARBEITSKOPIE_UNTERSTUETZT
            assert _persistenz._ARBEITSKOPIE_UNTERSTUETZT == set(
                archiv._KONVERTER.keys()
            )
        finally:
            archiv._KONVERTER = orig
            importlib.reload(_persistenz)


# ── BUG-27: Toter Parameter hat_bestritten_only ───────────────────────────
class TestBug27ToterParameter:
    def test_zustand_ohne_hat_bestritten_only(self):
        from backend.services import positionsstatus_service

        params = inspect.signature(positionsstatus_service._zustand).parameters
        assert "hat_bestritten_only" not in params


# ── BUG-28: Totes Feld Registry.fehler ────────────────────────────────────
class TestBug28RegistryFehler:
    def test_registry_hat_kein_fehler_feld(self):
        from backend.intake.registry_loader import Registry

        feldnamen = {f.name for f in dataclasses.fields(Registry)}
        assert "fehler" not in feldnamen


# ── BUG-23: IMAP-Config dedupliziert, EMAIL_FOLDER/MAX_FETCH respektiert ───
class TestBug23ImapConfig:
    def test_import_service_respektiert_email_folder_und_max_fetch(self, monkeypatch):
        from backend.email_import import import_service

        monkeypatch.setenv("EMAIL_HOST", "imap.example.de")
        monkeypatch.setenv("EMAIL_USER_UNFALL", "unfall@example.de")
        monkeypatch.setenv("EMAIL_PASSWORD_UNFALL", "geheim")
        monkeypatch.setenv("EMAIL_FOLDER", "Archiv/Unfall")
        monkeypatch.setenv("EMAIL_MAX_FETCH", "7")

        cfg = import_service._imap_cfg_fuer_konto("unfall")
        assert cfg is not None
        assert cfg["folder"] == "Archiv/Unfall"
        assert cfg["max_fetch"] == 7

    def test_polling_und_import_teilen_dieselbe_config_funktion(self):
        from backend.email_import import import_service, polling_service

        assert (
            polling_service._imap_config_fuer_account
            is import_service._imap_cfg_fuer_konto
        )


# ── BUG-24: _html_zu_text nicht mehr im Adapter dupliziert ────────────────
class TestBug24HtmlZuText:
    def test_adapter_definiert_kein_eigenes_html_zu_text(self):
        from backend.intake import adapter_imap

        # Duplikat entfernt: der Adapter nutzt email_parser._html_zu_text
        # (per lokalem Import), definiert es also nicht mehr selbst.
        assert "_html_zu_text" not in vars(adapter_imap)

    def test_adapter_konvertiert_html_ueber_email_parser(self):
        from backend.intake import adapter_imap
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = "a@b.de"
        msg.set_content("<p>Hallo<br>Welt</p>", subtype="html")

        from backend.email_import.email_parser import _html_zu_text
        text = adapter_imap._extrahiere_body_text(msg)
        assert text == _html_zu_text("<p>Hallo<br>Welt</p>")
        assert "Hallo" in text and "Welt" in text


# ── BUG-29: date.today()-Block dedupliziert ───────────────────────────────
class TestBug29DatumHelper:
    def test_helper_setzt_heute_bei_none(self):
        from backend.services import eingehende_ereignisse

        assert eingehende_ereignisse._heute_wenn_leer(None) == date.today().isoformat()

    def test_helper_laesst_vorhandenes_datum_unveraendert(self):
        from backend.services import eingehende_ereignisse

        assert eingehende_ereignisse._heute_wenn_leer("2020-01-01") == "2020-01-01"
