"""
Meldet dem Portal, welcher SV-Zugang welche Akten sehen darf.

Berechtigung und Akteninhalt sind getrennt: Diese Sendung transportiert nur
die Zuordnung. Die Akte selbst kommt ueber den Aktensync. Im Portal verweist
akte_zugriff.az per Fremdschluessel auf akten(az) - deshalb wird die
Warteschlange hier vorher geleert.
"""
import hashlib
import hmac as _hmac
import json
import logging
import os

import requests

from ..ramicro.ablage_service import hole_ablage_status  # noqa: F401  (Testbarkeit)
from ..ramicro.connector import (
    get_ramicro_connection,
    RaMicroNichtAktiv,
    RaMicroVerbindungsFehler,
)
from .ablage_abgleich import abgleichen
from .portal_sync import process_queue

logger = logging.getLogger(__name__)


def hole_akten_fuer_sv(adressnr):
    # type: (int) -> list
    """Alle Akten, in denen adressnr in RA-MICRO als SV eingetragen ist."""
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT a.sAktenNummer AS az,
                       a.sAktenKurzBezeichnung AS ra_bezeichnung
                FROM tblAktenBeteiligte b
                INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
                WHERE b.iAdressnummer = %s
                  AND b.sBeteiligtenKennzeichen LIKE 'SV%%'
                  AND b.bDeaktiviert = 0
                """,
                (adressnr,),
            )
            return [{"az": r["az"], "ra_bezeichnung": r["ra_bezeichnung"] or ""}
                    for r in cur.fetchall() if r["az"]]
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("SV-Akten-Lookup fehlgeschlagen (adressnr=%s): %s", adressnr, e)
        return []


def _sende_zugriffe(payload):
    # type: (dict) -> dict
    url = os.environ.get("PORTAL_API_URL", "")
    api_key = os.environ.get("PORTAL_API_KEY", "")
    secret = os.environ.get("PORTAL_HMAC_SECRET", "")
    if not url or not api_key or not secret:
        logger.info("Zugriffs-Abgleich: Portal nicht konfiguriert - nicht gesendet.")
        return None

    body = json.dumps(payload, ensure_ascii=False, default=str)
    signatur = _hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    try:
        resp = requests.post(
            url + "/api/sync/sv-zugriffe",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Sync-API-Key": api_key,
                "X-Sync-Signature": signatur,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("Zugriffs-Abgleich: HTTP %s", resp.status_code)
            return None
        return resp.json()
    except requests.exceptions.RequestException as exc:
        logger.error("Zugriffs-Abgleich fehlgeschlagen: %s", exc)
        return None


def zugriffe_abgleichen(conn, adressnr):
    # type: (object, int) -> dict
    sv = conn.execute(
        "SELECT adressnr, name, vorname, email FROM sv_portal_accounts WHERE adressnr = ?",
        (adressnr,),
    ).fetchone()

    ra_akten = [a["az"] for a in hole_akten_fuer_sv(adressnr)]
    bericht = {"gesamt": len(ra_akten), "gesperrt": 0, "uebertragen": 0,
               "gesendet": False, "antwort": None}

    if not sv or not ra_akten:
        return bericht

    abgleichen(conn, az_liste=ra_akten)

    platzhalter = ",".join("?" * len(ra_akten))
    gesperrt = {r["az"] for r in conn.execute(
        "SELECT az FROM unfallakte WHERE portal_gesperrt = 1 "
        "AND az IN ({})".format(platzhalter),
        ra_akten,
    )}
    frei = [az for az in ra_akten if az not in gesperrt]

    for az in frei:
        conn.execute("UPDATE unfallakte SET portal_aktiv = 1 WHERE az = ?", (az,))
    for az in gesperrt:
        conn.execute("UPDATE unfallakte SET portal_aktiv = 0 WHERE az = ?", (az,))
    conn.commit()

    bericht["gesperrt"] = len(gesperrt)
    bericht["uebertragen"] = len(frei)

    antwort = _sende_zugriffe({
        "adressnr": sv["adressnr"],
        "name": sv["name"],
        "vorname": sv["vorname"],
        "email": sv["email"],
        "akten": frei,
    })
    bericht["gesendet"] = antwort is not None
    bericht["antwort"] = antwort
    return bericht
