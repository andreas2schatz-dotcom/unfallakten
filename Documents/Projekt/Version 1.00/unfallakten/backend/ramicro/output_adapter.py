"""
Output-Adapter (S1.8, F-08).

Kapselt die eine Schreib-Operation aus der Review-Freigabe Richtung Akte:
das Anlegen einer dokumente-Zeile.

Stufe-1-Implementierung schreibt lokal ueber ``registriere_dokument``
(bestehendes Muster). Der spaetere XML-Scanner-Adapter (F-08) haengt sich
hinter dasselbe Interface -- ``schreibe_dokument(intake_dok, akte_az,
freigegeben_von) -> dokument_id``.

Die Klasse aus dem Intake wird auf die zulaessigen ``dokumente.typ``-Werte
gemappt. Nicht direkt darstellbare Klassen (pruefbericht, rechnung,
sv_rechnung, sonstiges, abschlepprechnung, standkostenrechnung) landen
als ``sonstiges`` -- die Feinklassifikation bleibt weiterhin in
``intake_dokumente.klasse`` erhalten.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from ..models.dokument import GUELTIGE_TYPEN, registriere_dokument


def _map_klasse(klasse: Optional[str]) -> str:
    """Mapt intake_dokumente.klasse -> dokumente.typ (CHECK-constraint)."""
    if klasse and klasse in GUELTIGE_TYPEN:
        return klasse
    return "sonstiges"


def _upload_verzeichnis() -> Path:
    default = Path(__file__).resolve().parent.parent / "uploads"
    pfad = Path(os.environ.get("UPLOAD_DIR", str(default)))
    pfad.mkdir(parents=True, exist_ok=True)
    return pfad


def _relativer_pfad(absolut: Path, base: Path) -> str:
    try:
        return str(absolut.relative_to(base))
    except ValueError:
        return str(absolut)


def schreibe_dokument(intake_dok: Dict[str, Any], akte_az: str,
                      freigegeben_von: Optional[int],
                      bezeichnung: Optional[str] = None) -> int:
    """Legt eine dokumente-Zeile fuer die Akte an. Liefert die dokument_id.

    Args:
        intake_dok: dict-Row aus intake_dokumente (mindestens klasse,
            arbeitskopie_pfad; original_pfad optional).
        akte_az: Ziel-Akte (unfallakte.az).
        freigegeben_von: benutzer_id des Freigebenden (fuer aktivitaeten).
        bezeichnung: effektive Dokumentenbezeichnung (PRD-37), falls gesetzt
            wird sie nach ``dokumente.bezeichnung`` uebernommen.

    Raises:
        FileNotFoundError: Arbeitskopie liegt nicht (mehr) im Dateisystem.
    """
    arbeitskopie = intake_dok.get("arbeitskopie_pfad")
    if not arbeitskopie or not os.path.isfile(arbeitskopie):
        raise FileNotFoundError(
            f"Arbeitskopie fehlt: {arbeitskopie!r}"
        )

    typ = _map_klasse(intake_dok.get("klasse"))

    # Datei in Upload-Ordner kopieren, damit die Akte einen stabilen Pfad
    # hat -- die Intake-Arbeitskopie kann per TSV-/Artefakt-Lifecycle
    # (Stufe 2) spaeter geloescht werden.
    upload_dir = _upload_verzeichnis()
    akte_dir = upload_dir / akte_az.replace("/", "_")
    akte_dir.mkdir(parents=True, exist_ok=True)

    quell_pfad = Path(arbeitskopie)
    ziel_pfad = akte_dir / quell_pfad.name
    if quell_pfad.resolve() != ziel_pfad.resolve():
        shutil.copy2(quell_pfad, ziel_pfad)

    relpfad = _relativer_pfad(ziel_pfad, upload_dir)
    ext = ziel_pfad.suffix.lower().lstrip(".")
    dateityp = ext if ext in ("pdf", "docx", "jpg", "png") else "sonstiges"
    if ext == "jpeg":
        dateityp = "jpg"

    dokument = registriere_dokument(
        akte_id=akte_az,
        typ=typ,
        dateiname=ziel_pfad.name,
        dateipfad=relpfad,
        bearbeiter_id=freigegeben_von,
        dateityp=dateityp,
        dateigroesse=ziel_pfad.stat().st_size if ziel_pfad.exists() else None,
    )
    if bezeichnung:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET bezeichnung=? WHERE id=?",
                (bezeichnung, dokument.id),
            )
    return int(dokument.id)
