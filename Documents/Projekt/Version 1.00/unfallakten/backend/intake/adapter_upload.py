"""
S1.3 - Upload-Adapter.

Nimmt eine hochgeladene Datei (Bytes + Dateiname) und legt sie als
``intake_dokumente``-Zeile + ``zustellungen(quelle='upload')`` an.

Der Adapter beruehrt den Alt-Pfad nicht — die bestehende
``verarbeite_upload()`` in ``backend/pdf/upload_service.py`` bleibt
unveraendert. Der Alt-Pfad ruft diesen Adapter zusaetzlich auf
(Doppelschreiben).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ._persistenz import erzeuge_zustellung, oder_intake_dokument_fuer_datei

logger = logging.getLogger(__name__)


def verarbeite_datei(
    daten: bytes,
    *,
    dateiname: str,
    absender: str | None = None,
    hochgeladen_von: int | None = None,
    roh_referenz: str | None = None,
    ziel_akte: str | None = None,
) -> dict[str, Any]:
    """
    Legt eine hochgeladene Datei ins Intake-Datenmodell.

    ``ziel_akte``: Beim Upload ueber ``POST /akten/<id>/dokumente`` ist die
    Ziel-Akte bekannt. Sie wird als ``az``-Signal durchgereicht, damit
    ``akten_matching.finde_kandidaten`` sie als Top-Kandidat vorbelegt
    (BUG-03 -- sonst Text-Matching allein, Gefahr der Falschablage).

    Rueckgabe: ``{"intake_dokument_id": int, "zustellung_id": int, "sha256": str}``.
    """
    ext = Path(dateiname).suffix.lstrip(".").lower() or "bin"
    intake_id, sha = oder_intake_dokument_fuer_datei(daten, ext)

    signale = {"dateiname": dateiname}
    if hochgeladen_von is not None:
        signale["hochgeladen_von"] = hochgeladen_von
    if ziel_akte:
        signale["az"] = ziel_akte

    zust_id = erzeuge_zustellung(
        intake_id,
        quelle="upload",
        absender=absender,
        signale=signale,
        roh_referenz=roh_referenz or dateiname,
    )
    return {
        "intake_dokument_id": intake_id,
        "zustellung_id": zust_id,
        "sha256": sha,
    }
