"""
Gleicht den Ablage-Status aus RA-MICRO nach SQLite ab.

Beidseitig: Wird eine Akte in RA-MICRO reaktiviert, kehrt sie auch bei uns
zurueck. Der Aktenstatus, den der Abgleich beim Ablegen ueberschrieben hat,
steht in status_vor_ablage und wird dabei wiederhergestellt. Ein selbst
gesetzter Abschluss hat kein status_vor_ablage und bleibt unangetastet.
"""
import logging

from ..ramicro.ablage_service import hole_ablage_status
from .portal_sync import queue_sync

logger = logging.getLogger(__name__)

MAX_BEISPIELE = 5


def _leerer_bericht():
    return {
        "geprueft": 0,
        "abgelegt_neu": 0,
        "reaktiviert": 0,
        "angelegt": 0,
        "bezeichnung_aktualisiert": 0,
        "beispiele": {"abgelegt_neu": [], "reaktiviert": [], "angelegt": []},
        "ramicro_erreichbar": True,
    }


def _merke(bericht, schluessel, az):
    bericht[schluessel] += 1
    if len(bericht["beispiele"][schluessel]) < MAX_BEISPIELE:
        bericht["beispiele"][schluessel].append(az)


def abgleichen(conn, az_liste=None, vorschau=False):
    # type: (object, list, bool) -> dict
    """
    Ohne az_liste: alle Akten in unfallakte.
    Mit az_liste: genau diese Aktenzeichen; fehlende Zeilen werden angelegt.
    """
    bericht = _leerer_bericht()

    if az_liste is None:
        az_liste = [r["az"] for r in conn.execute("SELECT az FROM unfallakte")]
        anlegen = False
    else:
        az_liste = list(az_liste)
        anlegen = True

    if not az_liste:
        return bericht

    status = hole_ablage_status(az_liste)
    if status is None:
        bericht["ramicro_erreichbar"] = False
        return bericht

    bestand = {
        r["az"]: r for r in conn.execute(
            "SELECT az, status, kurzbezeichnung, ramicro_abgelegt, status_vor_ablage "
            "FROM unfallakte"
        )
    }

    for az in az_liste:
        daten = status.get(az)
        if daten is None:
            continue
        bericht["geprueft"] += 1

        zeile = bestand.get(az)
        if zeile is None:
            if not anlegen:
                continue
            _merke(bericht, "angelegt", az)
            if not vorschau:
                conn.execute("INSERT OR IGNORE INTO unfallakte (az) VALUES (?)", (az,))
            zeile = {
                "status": "offen", "kurzbezeichnung": None,
                "ramicro_abgelegt": 0, "status_vor_ablage": None,
            }

        war_abgelegt = bool(zeile["ramicro_abgelegt"])
        ist_abgelegt = daten["abgelegt"]

        if ist_abgelegt and not war_abgelegt:
            _merke(bericht, "abgelegt_neu", az)
            if not vorschau:
                if zeile["status"] != "abgeschlossen":
                    conn.execute(
                        "UPDATE unfallakte SET status_vor_ablage = ?, status = 'abgeschlossen' "
                        "WHERE az = ?",
                        (zeile["status"], az),
                    )
                conn.execute(
                    "UPDATE unfallakte SET ramicro_abgelegt = 1, ramicro_ablage_datum = ? "
                    "WHERE az = ?",
                    (daten["ablage_datum"], az),
                )
                queue_sync(conn, az)

        elif war_abgelegt and not ist_abgelegt:
            _merke(bericht, "reaktiviert", az)
            if not vorschau:
                if zeile["status_vor_ablage"]:
                    conn.execute(
                        "UPDATE unfallakte SET status = ?, status_vor_ablage = NULL "
                        "WHERE az = ?",
                        (zeile["status_vor_ablage"], az),
                    )
                conn.execute(
                    "UPDATE unfallakte SET ramicro_abgelegt = 0, ramicro_ablage_datum = NULL "
                    "WHERE az = ?",
                    (az,),
                )
                queue_sync(conn, az)

        neue_bezeichnung = daten["kurzbezeichnung"]
        if neue_bezeichnung and neue_bezeichnung != (zeile["kurzbezeichnung"] or ""):
            bericht["bezeichnung_aktualisiert"] += 1
            if not vorschau:
                conn.execute(
                    "UPDATE unfallakte SET kurzbezeichnung = ? WHERE az = ?",
                    (neue_bezeichnung, az),
                )

    if not vorschau:
        conn.commit()

    logger.info(
        "Ablage-Abgleich%s: %d geprueft, %d neu abgelegt, %d reaktiviert, %d angelegt.",
        " (Vorschau)" if vorschau else "",
        bericht["geprueft"], bericht["abgelegt_neu"],
        bericht["reaktiviert"], bericht["angelegt"],
    )
    return bericht
