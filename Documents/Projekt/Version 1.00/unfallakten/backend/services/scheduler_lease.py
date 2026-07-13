"""
Scheduler-Lease (BUG-10) -- Single-Process-Guard fuer Hintergrund-Jobs.

Unter Gunicorn laufen mehrere Worker-Prozesse; ohne Guard registriert JEDER
Worker eigene APScheduler-Jobs (imap_polling, intake_worker, fristablauf).
Folge: dasselbe Postfach wird mehrfach gepollt, Fristablauf-Ereignisse
werden vervielfacht.

Loesung: ein prozessuebergreifender Lease via exklusivem TCP-Bind auf einen
festen Loopback-Port. Nur der erste Prozess bekommt den Bind; alle weiteren
scheitern mit ``EADDRINUSE`` und starten den Scheduler nicht. Der Socket
bleibt fuer die Prozesslaufzeit offen (Modul-Global), damit der Lease haelt.

Override fuer Einzelprozess-/Dev-/Test-Betrieb: ``SCHEDULER_LEASE_DISABLED=1``
laesst den Lease immer gelingen (kein Bind).
"""
from __future__ import annotations

import logging
import os
import socket
from typing import Optional

logger = logging.getLogger(__name__)

_LEASE_SOCKET: Optional[socket.socket] = None

STANDARD_PORT = 5051


def erwirb_scheduler_lease(port: Optional[int] = None) -> bool:
    """Versucht, den Scheduler-Lease zu erwerben.

    Rueckgabe: ``True`` wenn dieser Prozess den Scheduler starten soll,
    ``False`` wenn bereits ein anderer Prozess den Lease haelt.
    """
    global _LEASE_SOCKET

    if os.environ.get("SCHEDULER_LEASE_DISABLED") == "1":
        return True

    if port is None:
        port = int(os.environ.get("SCHEDULER_LEASE_PORT", str(STANDARD_PORT)))

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError as exc:
        s.close()
        logger.info("Scheduler-Lease (Port %s) nicht erhalten: %s -- "
                    "Scheduler laeuft in einem anderen Prozess.", port, exc)
        return False

    _LEASE_SOCKET = s
    logger.info("Scheduler-Lease (Port %s) erworben -- dieser Prozess startet "
                "die Hintergrund-Jobs.", port)
    return True


def gib_scheduler_lease_frei() -> None:
    """Gibt den Lease frei (v.a. fuer Tests)."""
    global _LEASE_SOCKET
    if _LEASE_SOCKET is not None:
        try:
            _LEASE_SOCKET.close()
        finally:
            _LEASE_SOCKET = None
