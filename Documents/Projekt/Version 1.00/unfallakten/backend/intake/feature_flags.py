"""
Feature-Flags fuer den Intake-Pfad (Pipeline v7).

INTAKE_REVIEW_PFLICHT (default True ab S1.9): Steuert, ob eingehende
Dokumente (E-Mail-Anhaenge, Uploads, E-Akte-Import) durch die Review-
Queue laufen muessen oder direkt in ``dokumente`` landen duerfen
(Alt-Pfad). Rollback-Anker fuer den BREAKING-Umbau: setze
``INTAKE_REVIEW_PFLICHT=false`` und die Auto-Pfade laufen wieder.
"""
from __future__ import annotations

import os

_TRUE = {"true", "1", "yes", "y", "on"}
_FALSE = {"false", "0", "no", "n", "off"}


def review_pflicht_aktiv() -> bool:
    """True, wenn Dokumente durch die Review-Queue laufen muessen.

    Default: True. Wird erst bei explizitem ``INTAKE_REVIEW_PFLICHT=false``
    ausgeschaltet (Rollback-Anker).
    """
    wert = os.environ.get("INTAKE_REVIEW_PFLICHT", "").strip().lower()
    if wert in _FALSE:
        return False
    if wert in _TRUE:
        return True
    return True
