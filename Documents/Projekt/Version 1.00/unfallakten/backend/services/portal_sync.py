"""
Portal-Sync-Service
====================
Berechnet Ampel-Status, baut JSON-Payload, verwaltet die Sync-Queue.
"""
import hashlib
import hmac as _hmac
import json
import logging
import os
import sqlite3
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

PORTAL_API_URL     = os.environ.get("PORTAL_API_URL", "")
PORTAL_API_KEY     = os.environ.get("PORTAL_API_KEY", "")
PORTAL_HMAC_SECRET = os.environ.get("PORTAL_HMAC_SECRET", "")


def _berechne_ampel(conn, akte_id):
    # type: (sqlite3.Connection, str) -> dict
    """Gibt {'status': str, 'farbe': str} zurueck."""
    akte = conn.execute(
        "SELECT status FROM unfallakte WHERE az = ?", (akte_id,)
    ).fetchone()
    if not akte:
        return {"status": "akte_eroeffnet", "farbe": "grau"}

    if akte["status"] == "klage":
        return {"status": "klage_eingereicht", "farbe": "rot"}

    sp = conn.execute("""
        SELECT COALESCE(
            reparaturkosten + wiederbeschaffung - restwert + wertminderung +
            nutzungsausfall + mietwagenkosten + sv_kosten + abschleppkosten +
            standkosten + anabmeldekosten + schmerzensgeld + sonstiges, 0.0
        ) AS gesamt
        FROM schadenpositionen WHERE akte_id = ?
    """, (akte_id,)).fetchone()
    gefordert = float(sp["gesamt"]) if sp else 0.0

    reg = conn.execute("""
        SELECT COALESCE(SUM(rp.betrag_reguliert), 0.0) AS reguliert
        FROM regulierung_positionen rp
        JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
        WHERE ab.akte_id = ?
    """, (akte_id,)).fetchone()
    reguliert = float(reg["reguliert"]) if reg else 0.0

    if akte["status"] == "abgeschlossen" and gefordert > 0 and reguliert >= gefordert * 0.95:
        return {"status": "vollreguliert", "farbe": "gruen"}

    if reguliert > 0 and gefordert > 0:
        return {"status": "teilreguliert", "farbe": "orange"}

    ab_count = conn.execute(
        "SELECT COUNT(*) AS n FROM abrechnungsschreiben WHERE akte_id = ?", (akte_id,)
    ).fetchone()["n"]
    if ab_count > 0:
        return {"status": "regulierung_laeuft", "farbe": "gelb"}

    sv = conn.execute("""
        SELECT COUNT(*) AS n FROM beteiligte
        WHERE akte_id = ? AND rolle = 'sachverstaendiger'
    """, (akte_id,)).fetchone()
    if sv["n"] > 0:
        return {"status": "gutachten_beauftragt", "farbe": "grau"}

    return {"status": "akte_eroeffnet", "farbe": "grau"}


def _portal_flag(conn, akte_id):
    # type: (sqlite3.Connection, str) -> None
    """Markiert eine Akte fuer Portal-Sync – NUR wenn portal_aktiv = 1."""
    row = conn.execute(
        "SELECT portal_aktiv FROM unfallakte WHERE az = ?", (akte_id,)
    ).fetchone()
    if row and row["portal_aktiv"]:
        queue_sync(conn, akte_id)


def queue_sync(conn, akte_id):
    # type: (sqlite3.Connection, str) -> None
    conn.execute(
        "UPDATE unfallakte SET portal_sync_pending = 1 WHERE az = ?", (akte_id,)
    )


def _build_payload(conn, akte_id):
    # type: (sqlite3.Connection, str) -> dict
    """Baut vollstaendigen JSON-Snapshot einer Akte. Kein IBAN, keine internen Notizen."""
    akte = conn.execute("""
        SELECT az, status, unfalldatum, haftungsquote, sachbearbeiter
        FROM unfallakte WHERE az = ?
    """, (akte_id,)).fetchone()
    if not akte:
        return {}

    last = conn.execute("""
        SELECT COALESCE(MAX(sync_version), 0) AS v
        FROM portal_sync_queue WHERE akte_id = ? AND status = 'confirmed'
    """, (akte_id,)).fetchone()
    sync_version = (last["v"] or 0) + 1

    ampel = _berechne_ampel(conn, akte_id)

    beteiligte = conn.execute("""
        SELECT id, rolle, name, vorname, firma, email
        FROM beteiligte WHERE akte_id = ?
    """, (akte_id,)).fetchall()

    sp = conn.execute("""
        SELECT reparaturkosten, wiederbeschaffung, restwert, wertminderung,
               nutzungsausfall, mietwagenkosten, sv_kosten, abschleppkosten,
               standkosten, anabmeldekosten, schmerzensgeld, sonstiges
        FROM schadenpositionen WHERE akte_id = ?
    """, (akte_id,)).fetchone()

    reg_pos = conn.execute("""
        SELECT rp.position_key,
               SUM(rp.betrag_reguliert) AS reguliert,
               MAX(ab.datum)            AS letztes_datum,
               MAX(ab.versicherung)     AS versicherung
        FROM regulierung_positionen rp
        JOIN abrechnungsschreiben ab ON ab.id = rp.abrechnungsschreiben_id
        WHERE ab.akte_id = ?
        GROUP BY rp.position_key
    """, (akte_id,)).fetchall()

    docs = conn.execute("""
        SELECT id, typ, dateiname, hochgeladen_am
        FROM dokumente WHERE akte_id = ? AND portal_sichtbar = 1
    """, (akte_id,)).fetchall()

    return {
        "sync_version": sync_version,
        "akte": {
            "az": akte["az"],
            "status": akte["status"],
            "unfalldatum": akte["unfalldatum"],
            "haftungsquote": akte["haftungsquote"],
            "sachbearbeiter": akte["sachbearbeiter"],
        },
        "beteiligte": [
            {"id": b["id"], "rolle": b["rolle"], "name": b["name"],
             "vorname": b["vorname"], "firma": b["firma"], "email": b["email"]}
            for b in beteiligte
        ],
        "schaden": dict(sp) if sp else {},
        "regulierung_positionen": [
            {"position_key": r["position_key"], "reguliert": r["reguliert"],
             "letztes_datum": r["letztes_datum"], "versicherung": r["versicherung"]}
            for r in reg_pos
        ],
        "dokumente": [
            {"id": d["id"], "typ": d["typ"], "dateiname": d["dateiname"],
             "erstellt_am": d["hochgeladen_am"]}
            for d in docs
        ],
        "ampel": ampel,
    }


def _sign(payload_json):
    # type: (str) -> str
    return _hmac.new(
        PORTAL_HMAC_SECRET.encode(), payload_json.encode(), hashlib.sha256
    ).hexdigest()


def _send_to_portal(payload):
    # type: (dict) -> bool
    if not PORTAL_API_URL or not PORTAL_API_KEY:
        logger.debug("PORTAL_API_URL/KEY nicht konfiguriert – Sync uebersprungen.")
        return False
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    try:
        resp = requests.post(
            PORTAL_API_URL + "/api/sync/push",
            data=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Sync-API-Key": PORTAL_API_KEY,
                "X-Sync-Signature": _sign(payload_json),
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(
                "Portal-Push %s: HTTP %s",
                payload.get("akte", {}).get("az"), resp.status_code
            )
        return resp.status_code == 200
    except Exception as exc:
        logger.error("Portal-Push fehlgeschlagen: %s", exc)
        return False


def process_queue(conn, max_batch=10):
    # type: (sqlite3.Connection, int) -> int
    """Verarbeitet ausstehende Sync-Eintraege. Gibt Anzahl Erfolge zurueck."""
    pending = conn.execute("""
        SELECT az FROM unfallakte
        WHERE portal_sync_pending = 1 AND portal_aktiv = 1
        LIMIT ?
    """, (max_batch,)).fetchall()

    synced = 0
    for row in pending:
        akte_id = row["az"]
        payload = _build_payload(conn, akte_id)
        if not payload:
            continue

        sv = payload["sync_version"]
        conn.execute(
            "INSERT INTO portal_sync_queue (akte_id, sync_version, status) VALUES (?, ?, 'sending')",
            (akte_id, sv),
        )
        conn.commit()

        ok = _send_to_portal(payload)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if ok:
            conn.execute("""
                UPDATE portal_sync_queue SET status = 'confirmed', sent_at = ?
                WHERE akte_id = ? AND sync_version = ?
            """, (now, akte_id, sv))
            conn.execute("""
                UPDATE unfallakte SET portal_sync_pending = 0, portal_last_sync = ?
                WHERE az = ?
            """, (now, akte_id))
            synced += 1
        else:
            conn.execute("""
                UPDATE portal_sync_queue
                SET status = 'failed', retry_count = retry_count + 1, last_error = 'send_failed'
                WHERE akte_id = ? AND sync_version = ?
            """, (akte_id, sv))
        conn.commit()

    return synced
