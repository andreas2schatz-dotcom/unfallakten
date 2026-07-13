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


# ── BUG-29: date.today()-Block dedupliziert ───────────────────────────────
class TestBug29DatumHelper:
    def test_helper_setzt_heute_bei_none(self):
        from backend.services import eingehende_ereignisse

        assert eingehende_ereignisse._heute_wenn_leer(None) == date.today().isoformat()

    def test_helper_laesst_vorhandenes_datum_unveraendert(self):
        from backend.services import eingehende_ereignisse

        assert eingehende_ereignisse._heute_wenn_leer("2020-01-01") == "2020-01-01"
