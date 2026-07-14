"""
Verarbeitungs-Queue fuer intake_dokumente (S1.6a).

Zustandsmaschine:
    neu -> laeuft -> bereit_zur_review              (Happy Path)
    neu -> laeuft -> neu (Retry, versuch_zaehler += 1)
                  -> pipeline_fehler (nach MAX_VERSUCHE Fehlversuchen)

Der Worker reserviert Dokumente per ``worker_lease`` ("<worker_id>|<ablauf_iso>").
Waehrend das Lease frisch ist, sieht kein anderer Worker den Eintrag. Laeuft
das Lease ab (Worker-Absturz), uebernimmt der naechste Worker (F-10).

Backoff bei Fehlversuchen: 1/5/30 Minuten. Nach ``MAX_VERSUCHE`` Fehlversuchen
landet der Eintrag in ``pipeline_fehler`` und die Queue laeuft weiter (kein
Poison-Pill-Blocking).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..db.database import get_connection

logger = logging.getLogger(__name__)

MAX_VERSUCHE = 3
BACKOFF_S = (60, 300, 1800)  # 1 min, 5 min, 30 min

_ZEITFORMAT = "%Y-%m-%d %H:%M:%S"


def _jetzt_iso() -> str:
    return datetime.now().strftime(_ZEITFORMAT)


def _iso(dt: datetime) -> str:
    return dt.strftime(_ZEITFORMAT)


RUECKSTELL_S = 900  # 15 min: Ressourcendruck-Rueckstellung (N-03)

_MUSTER_TIMEOUT = ("timeout", "timed out", "zeitueberschreitung",
                   "zeitüberschreitung")
_MUSTER_RESSOURCE = ("connection", "verbindung", "refused", "reset by peer",
                     "broken pipe", " 503", " 502", "overload", "ueberlast",
                     "überlast", "unavailable", "too many requests",
                     "temporarily")
_MUSTER_REPRODUZIERBAR = ("keine seiten extrahierbar", "ohne inhalt",
                          "cannot open", "damaged", "not a pdf", "no /root",
                          "invalid", "unsupported", "arbeitskopie fehlt")


def klassifiziere_fehler(meldung: str) -> str:
    """Ordnet eine Fehlermeldung einer Retry-Kategorie zu (N-03).

    Timeout hat Vorrang vor Ressourcendruck (ein Read-Timeout ist mit Backoff
    behebbar). Default 'unbekannt' -> wird wie 'timeout' retriet (sicher).
    """
    m = (meldung or "").lower()
    if any(s in m for s in _MUSTER_TIMEOUT):
        return "timeout"
    if any(s in m for s in _MUSTER_RESSOURCE):
        return "ressourcendruck"
    if any(s in m for s in _MUSTER_REPRODUZIERBAR):
        return "reproduzierbar"
    return "unbekannt"


def enqueue(intake_dokument_id: int) -> None:
    """Setzt ein Dokument (zurueck) auf 'neu', unabhaengig von Backoff/Fehlern.

    Nutzung: nach manueller Reklassifikation im Review-UI (S1.8), oder wenn
    ein pipeline_fehler-Dokument erneut versucht werden soll.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET "
            "queue_status='neu', versuch_zaehler=0, naechster_versuch=NULL, "
            "worker_lease=NULL, fehler_detail=NULL "
            "WHERE id=?",
            (intake_dokument_id,),
        )


def reserviere_naechsten(worker_id: str,
                         lease_dauer_s: int = 300) -> Optional[Dict[str, Any]]:
    """Reserviert den naechsten faelligen Eintrag fuer diesen Worker.

    Faellig bedeutet:
      * ``queue_status`` = 'neu'
      * ``naechster_versuch`` NULL oder <= jetzt
      * ``worker_lease`` NULL oder Ablauf-Zeitpunkt <= jetzt

    Der reservierte Eintrag bekommt Status 'laeuft' und ein neues Lease.
    Liefert ein dict mit id, queue_status, worker_lease oder None.
    """
    jetzt = _jetzt_iso()
    ablauf = _iso(datetime.now() + timedelta(seconds=lease_dauer_s))
    lease = f"{worker_id}|{ablauf}"

    with get_connection() as conn:
        # Schritt 1: abgelaufene Leases zuruecksetzen (Worker-Absturz, F-10).
        # 'laeuft' + Ablauf-Zeit in der Vergangenheit -> zurueck auf 'neu'.
        conn.execute(
            "UPDATE intake_dokumente SET queue_status='neu', worker_lease=NULL "
            "WHERE queue_status='laeuft' "
            "  AND worker_lease IS NOT NULL "
            "  AND substr(worker_lease, instr(worker_lease, '|') + 1) <= ?",
            (jetzt,),
        )

        # Schritt 2: naechsten faelligen Kandidaten suchen.
        row = conn.execute(
            "SELECT id FROM intake_dokumente "
            "WHERE queue_status='neu' "
            "  AND (naechster_versuch IS NULL OR naechster_versuch <= ?) "
            "ORDER BY id "
            "LIMIT 1",
            (jetzt,),
        ).fetchone()
        if not row:
            return None
        did = row["id"]

        # Reservieren — Race-Fenster ist minimal, weil SQLite Writes serialisiert.
        cur = conn.execute(
            "UPDATE intake_dokumente SET queue_status='laeuft', worker_lease=? "
            "WHERE id=? AND queue_status='neu'",
            (lease, did),
        )
        if cur.rowcount != 1:
            # Ein anderer Worker war schneller
            return None

        job = conn.execute(
            "SELECT id, sha256, queue_status, worker_lease, versuch_zaehler, "
            "arbeitskopie_pfad, original_pfad "
            "FROM intake_dokumente WHERE id=?", (did,)
        ).fetchone()
        return dict(job) if job else None


def markiere_bereit(intake_dokument_id: int) -> None:
    """Erfolgs-Abschluss: Status 'bereit_zur_review', Lease/Fehler geloescht."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET "
            "queue_status='bereit_zur_review', worker_lease=NULL, "
            "fehler_detail=NULL "
            "WHERE id=?",
            (intake_dokument_id,),
        )


def markiere_fehler(intake_dokument_id: int, fehler_meldung: str) -> None:
    """Fehler-Abschluss mit kategorieabhaengigem Verhalten (N-03).

    * ressourcendruck -> zurueckstellen: bleibt 'neu', naechster_versuch=+15min,
      versuch_zaehler UNVERAENDERT (transienter Backend-Ausfall vergiftet nicht).
    * reproduzierbar  -> KEIN Retry: sofort 'pipeline_fehler'.
    * timeout/unbekannt -> Backoff 1/5/30, nach MAX_VERSUCHE 'pipeline_fehler'.
    """
    kategorie = klassifiziere_fehler(fehler_meldung)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT versuch_zaehler FROM intake_dokumente WHERE id=?",
            (intake_dokument_id,),
        ).fetchone()
        if not row:
            logger.error("markiere_fehler: ID %s nicht gefunden", intake_dokument_id)
            return
        zaehler = int(row["versuch_zaehler"] or 0)

        if kategorie == "ressourcendruck":
            naechster = _iso(datetime.now() + timedelta(seconds=RUECKSTELL_S))
            conn.execute(
                "UPDATE intake_dokumente SET queue_status='neu', "
                "worker_lease=NULL, fehler_detail=?, naechster_versuch=? "
                "WHERE id=?",
                (fehler_meldung, naechster, intake_dokument_id),
            )
            logger.warning(
                "Dokument %s: Ressourcendruck -> zurueckgestellt +%ds "
                "(Zaehler unveraendert %d): %s",
                intake_dokument_id, RUECKSTELL_S, zaehler, fehler_meldung,
            )
            return

        if kategorie == "reproduzierbar":
            conn.execute(
                "UPDATE intake_dokumente SET queue_status='pipeline_fehler', "
                "worker_lease=NULL, fehler_detail=? WHERE id=?",
                (fehler_meldung, intake_dokument_id),
            )
            logger.warning(
                "Dokument %s: reproduzierbarer Fehler -> pipeline_fehler "
                "(kein Retry): %s",
                intake_dokument_id, fehler_meldung,
            )
            return

        neuer_zaehler = zaehler + 1
        if neuer_zaehler >= MAX_VERSUCHE:
            conn.execute(
                "UPDATE intake_dokumente SET "
                "queue_status='pipeline_fehler', versuch_zaehler=?, "
                "worker_lease=NULL, fehler_detail=? "
                "WHERE id=?",
                (neuer_zaehler, fehler_meldung, intake_dokument_id),
            )
            logger.warning(
                "Dokument %s: pipeline_fehler nach %d Versuchen (%s)",
                intake_dokument_id, neuer_zaehler, fehler_meldung,
            )
        else:
            backoff_s = BACKOFF_S[min(neuer_zaehler - 1, len(BACKOFF_S) - 1)]
            naechster = _iso(datetime.now() + timedelta(seconds=backoff_s))
            conn.execute(
                "UPDATE intake_dokumente SET "
                "queue_status='neu', versuch_zaehler=?, worker_lease=NULL, "
                "fehler_detail=?, naechster_versuch=? "
                "WHERE id=?",
                (neuer_zaehler, fehler_meldung, naechster, intake_dokument_id),
            )
            logger.info(
                "Dokument %s: Fehler %d/%d, retry in %ds (%s)",
                intake_dokument_id, neuer_zaehler, MAX_VERSUCHE,
                backoff_s, fehler_meldung,
            )
