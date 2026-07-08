"""
S1.3 - E-Akte-Adapter (raEloakte).

Beim E-Akte-Pull aus RA-MICRO wird ein PDF vom read-only Netzlaufwerk in
das Intake-Datenmodell uebernommen: einmalig als ``intake_dokumente`` (per
sha256 dedupliziert), pro Aufruf als ``zustellungen(quelle='eakte')``.

⛔ Read-only gegenueber raEloakte — die Quelldatei wird ausschliesslich
gelesen; das Archiv legt eine eigene Kopie im Original-Archiv ab.

Der bestehende Import-Weg (``eakte_routes.py: importieren``) bleibt
unveraendert; dieser Adapter wird zusaetzlich aufgerufen (Doppelschreiben).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ._persistenz import erzeuge_zustellung, oder_intake_dokument_fuer_datei

logger = logging.getLogger(__name__)


def verarbeite_eakte_dokument(
    quellpfad: str,
    *,
    akte_az: str,
    eakte_nr: int,
    dateiname: str | None = None,
    absender: str | None = None,
) -> dict[str, Any]:
    """
    Liest ``quellpfad`` und legt eine intake_dokumente-Zeile + eine
    zustellungen-Zeile mit ``quelle='eakte'`` an. ``roh_referenz`` traegt
    ``akte_az/eakte_nr`` als Anhalt, weil das Original in raEloakte wohnt.

    Rueckgabe: ``{"intake_dokument_id": int, "zustellung_id": int, "sha256": str}``.
    """
    pfad = Path(quellpfad)
    if not pfad.is_file():
        raise FileNotFoundError(f"E-Akte-Datei nicht gefunden: {quellpfad}")

    daten = pfad.read_bytes()
    ext = pfad.suffix.lstrip(".").lower() or "pdf"
    intake_id, sha = oder_intake_dokument_fuer_datei(daten, ext)

    signale = {
        "akte_az": akte_az,
        "eakte_nr": eakte_nr,
    }
    if dateiname:
        signale["dateiname"] = dateiname

    zust_id = erzeuge_zustellung(
        intake_id,
        quelle="eakte",
        absender=absender,
        signale=signale,
        roh_referenz=f"{akte_az}/{eakte_nr}",
    )
    return {
        "intake_dokument_id": intake_id,
        "zustellung_id": zust_id,
        "sha256": sha,
    }
