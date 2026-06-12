import logging
from datetime import datetime

from ..ramicro.connector import verbindung_pruefen
from ..email_import.imap_client import ist_konfiguriert

logger = logging.getLogger(__name__)

_cache: dict = {
    "ramicro": {"ok": None, "letzter_sync_ts": None, "fehler": None}
}


def check_ramicro() -> None:
    result = verbindung_pruefen()
    war_ok = _cache["ramicro"]["ok"]
    jetzt_ok = result["status"] == "ok"
    if war_ok is not None and war_ok != jetzt_ok:
        if jetzt_ok:
            logger.info("RA-Micro: Verbindung wiederhergestellt")
        else:
            logger.warning("RA-Micro: Verbindung unterbrochen – %s", result.get("meldung", ""))
    _cache["ramicro"] = {
        "ok": jetzt_ok,
        "letzter_sync_ts": datetime.now(),
        "fehler": result.get("meldung") if not jetzt_ok else None,
    }


def get_status() -> dict:
    rm = _cache["ramicro"]
    letzter_sync_vor_s = None
    if rm["letzter_sync_ts"] is not None:
        letzter_sync_vor_s = int((datetime.now() - rm["letzter_sync_ts"]).total_seconds())
    try:
        imap_konfig = ist_konfiguriert()
    except Exception:
        imap_konfig = False
    return {
        "ramicro": {
            "ok": rm["ok"],
            "letzter_sync_vor_s": letzter_sync_vor_s,
            "fehler": rm["fehler"],
        },
        "imap": {"ok": None, "konfiguriert": imap_konfig},
        "sv_portal": {"ok": None, "konfiguriert": False},
    }
