"""
Ablage-Status aus RA-MICRO (read-only).

RA-MICRO traegt in dtAblage fuer nicht abgelegte Akten den Nullwert
1899-12-30 ein. Massgeblich ist deshalb allein iAblageNummer.
"""
import logging

from .connector import (
    get_ramicro_connection,
    RaMicroNichtAktiv,
    RaMicroVerbindungsFehler,
)

logger = logging.getLogger(__name__)

BLOCKGROESSE = 500


def _datum(wert):
    if wert is None:
        return None
    if getattr(wert, "year", 0) < 1900:
        return None
    return wert.strftime("%Y-%m-%d")


def hole_ablage_status(az_liste):
    # type: (list) -> dict | None
    """
    Liefert je Aktenzeichen {'abgelegt', 'ablage_datum', 'kurzbezeichnung'}.
    None bedeutet: RA-MICRO nicht erreichbar. {} bedeutet: nichts gefunden.
    """
    if not az_liste:
        return {}

    ergebnis = {}
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            for start in range(0, len(az_liste), BLOCKGROESSE):
                block = az_liste[start:start + BLOCKGROESSE]
                platzhalter = ",".join(["%s"] * len(block))
                cur.execute(
                    "SELECT sAktenNummer AS az, iAblageNummer, dtAblage, "
                    "sAktenKurzBezeichnung AS kurz "
                    "FROM tblAkten WHERE sAktenNummer IN ({})".format(platzhalter),
                    tuple(block),
                )
                for zeile in cur.fetchall():
                    abgelegt = (zeile["iAblageNummer"] or 0) > 0
                    ergebnis[zeile["az"]] = {
                        "abgelegt": abgelegt,
                        "ablage_datum": _datum(zeile["dtAblage"]) if abgelegt else None,
                        "kurzbezeichnung": (zeile["kurz"] or "").strip(),
                    }
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as exc:
        logger.warning("Ablage-Abgleich: RA-MICRO nicht erreichbar (%s).", exc)
        return None
    except Exception as exc:
        logger.warning("Ablage-Abgleich: Abfrage fehlgeschlagen (%s).", exc)
        return None

    return ergebnis
