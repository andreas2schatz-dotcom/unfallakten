"""
Fragebogen-Feld-Uebernahme bei Freigabe.

Einzige sanktionierte Stelle, die geparste Fragebogen-Felder in Akten-
Stammdaten (beteiligte / unfallakte / unfalldetails / personenschaden)
schreibt. Ausgeloest ausschliesslich durch die manuelle Review-Freigabe.

Semantik: leeres Aktenfeld -> fuellen; abweichendes Feld -> nur ueberschreiben,
wenn der bestaetigte Wert vom aktuellen Akten-Wert abweicht. Deckungsgleiche
oder unveraenderte Felder bleiben unangetastet.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..db.database import get_connection

logger = logging.getLogger(__name__)

ABSCHNITTE: Tuple[str, ...] = ("mandant", "gegner", "unfall", "personenschaden")
_LABELS = {
    "mandant": "Mandant",
    "gegner": "Gegner & Versicherung",
    "unfall": "Unfall",
    "personenschaden": "Personenschaden",
}


def parse_fragebogen_payload(structured_payload: Optional[str]) -> Optional[dict]:
    """Re-parst das rohe Fragebogen-JSON (intake_dokumente.structured_payload).

    Gibt das strukturierte Dict (mandant/gegner/unfall/personenschaden) zurueck
    oder None, wenn es kein gueltiger Unfallbogen ist.
    """
    if not structured_payload:
        return None
    from ..email_import.fragebogen_parser import parse_fragebogen_anhang
    return parse_fragebogen_anhang(structured_payload.encode("utf-8"))


def _norm(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _vorschau_felder(geparste: List[Tuple[str, str, Any]],
                     akte_werte: Dict[str, Any]) -> List[dict]:
    """Baut die Feldliste fuer die Vorschau. Nur Felder mit nichtleerem
    geparstem Wert werden gelistet."""
    out: List[dict] = []
    for feld, label, wert in geparste:
        if not _norm(wert):
            continue
        akte = akte_werte.get(feld)
        leer = _norm(akte) == ""
        konflikt = (not leer) and _norm(akte).casefold() != _norm(wert).casefold()
        out.append({
            "feld": feld, "label": label, "geparst": wert,
            "akte_wert": akte, "ist_leer": leer, "konflikt": konflikt,
        })
    return out


# ── Mandant / Gegner (beteiligte) ────────────────────────────────────────────

def _geparst_mandant(m: dict) -> List[Tuple[str, str, Any]]:
    vs = "Y" if (m.get("vorsteuerabzug") == "ja") else None
    return [
        ("name", "Name", m.get("name")),
        ("vorname", "Vorname", m.get("vorname")),
        ("anschrift", "Straße", m.get("strasse")),
        ("plz", "PLZ", m.get("plz")),
        ("ort", "Ort", m.get("ort")),
        ("email", "E-Mail", m.get("email")),
        ("telefon", "Telefon", m.get("telefon")),
        ("iban", "IBAN", m.get("iban")),
        ("vorsteuer", "Vorsteuer", vs),
    ]


def _akte_mandant(conn, akte_az: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT name, vorname, anschrift, plz, ort, email, telefon, iban, vorsteuer "
        "FROM beteiligte WHERE akte_id=? AND rolle='mandant'", (akte_az,)).fetchone()
    return dict(row) if row else {}


def _geparst_gegner(g: dict) -> List[Tuple[str, str, Any]]:
    fz = g.get("fahrzeug") or {}
    ver = g.get("versicherung") or {}
    return [
        ("name", "Fahrer", g.get("fahrer")),
        ("kfz_kennzeichen", "Kennzeichen", fz.get("kennzeichen")),
        ("notizen", "Fabrikat", fz.get("fabrikat")),
        ("versicherung", "Versicherung", ver.get("name")),
        ("vers_nr", "Vers.-Nr.", ver.get("nummer")),
        ("schaden_nr", "Schaden-Nr.", ver.get("schadennummer")),
    ]


def _akte_gegner(conn, akte_az: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT name, kfz_kennzeichen, notizen, versicherung, vers_nr, schaden_nr "
        "FROM beteiligte WHERE akte_id=? AND rolle='gegner'", (akte_az,)).fetchone()
    return dict(row) if row else {}


def _schreibe_beteiligte(conn, akte_az: str, rolle: str,
                         aenderungen: Dict[str, Any]) -> None:
    if not aenderungen:
        return
    row = conn.execute("SELECT id FROM beteiligte WHERE akte_id=? AND rolle=?",
                       (akte_az, rolle)).fetchone()
    if row is None:
        cols = ["akte_id", "rolle"] + list(aenderungen)
        werte = [akte_az, rolle] + list(aenderungen.values())
        platz = ", ".join(["?"] * len(cols))
        conn.execute(f"INSERT INTO beteiligte ({', '.join(cols)}) VALUES ({platz})",
                     werte)
    else:
        setzt = ", ".join(f"{k}=?" for k in aenderungen)
        conn.execute(f"UPDATE beteiligte SET {setzt} WHERE id=?",
                     list(aenderungen.values()) + [row["id"]])
