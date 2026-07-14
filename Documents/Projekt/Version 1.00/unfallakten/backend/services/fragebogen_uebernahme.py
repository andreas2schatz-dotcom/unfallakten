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
        # beteiligte.name ist NOT NULL -> beim Neuanlegen ohne Namen leer setzen.
        spalten = dict(aenderungen)
        spalten.setdefault("name", "")
        cols = ["akte_id", "rolle"] + list(spalten)
        werte = [akte_az, rolle] + list(spalten.values())
        platz = ", ".join(["?"] * len(cols))
        conn.execute(f"INSERT INTO beteiligte ({', '.join(cols)}) VALUES ({platz})",
                     werte)
    else:
        setzt = ", ".join(f"{k}=?" for k in aenderungen)
        conn.execute(f"UPDATE beteiligte SET {setzt} WHERE id=?",
                     list(aenderungen.values()) + [row["id"]])


# ── Unfall (unfallakte + unfalldetails) ──────────────────────────────────────

def _geparst_unfall(u: dict) -> List[Tuple[str, str, Any]]:
    zeit = u.get("zeit")
    schild = u.get("schilderung")
    if zeit:
        schild_final = f"[Uhrzeit: {zeit}] {schild}" if schild else f"[Uhrzeit: {zeit}]"
    else:
        schild_final = schild
    pol = (u.get("polizei") or {}).get("aktenzeichen")
    return [
        ("unfalldatum", "Unfalldatum", u.get("datum")),
        ("unfallort", "Unfallort", u.get("ort")),
        ("schilderung", "Schilderung", schild_final),
        ("ermittlungsakte_az", "Ermittlungsakte-AZ", pol),
    ]


def _akte_unfall(conn, akte_az: str) -> Dict[str, Any]:
    a = conn.execute("SELECT unfalldatum, unfallort FROM unfallakte WHERE az=?",
                     (akte_az,)).fetchone()
    d = conn.execute("SELECT schilderung, ermittlungsakte_az FROM unfalldetails "
                     "WHERE akte_id=?", (akte_az,)).fetchone()
    return {
        "unfalldatum": a["unfalldatum"] if a else None,
        "unfallort": a["unfallort"] if a else None,
        "schilderung": d["schilderung"] if d else None,
        "ermittlungsakte_az": d["ermittlungsakte_az"] if d else None,
    }


def _schreibe_unfall(conn, akte_az: str, aenderungen: Dict[str, Any]) -> None:
    akte_cols = {k: v for k, v in aenderungen.items()
                 if k in ("unfalldatum", "unfallort")}
    det_cols = {k: v for k, v in aenderungen.items()
                if k in ("schilderung", "ermittlungsakte_az")}
    if akte_cols:
        setzt = ", ".join(f"{k}=?" for k in akte_cols)
        conn.execute(f"UPDATE unfallakte SET {setzt} WHERE az=?",
                     list(akte_cols.values()) + [akte_az])
    if det_cols:
        row = conn.execute("SELECT id FROM unfalldetails WHERE akte_id=?",
                           (akte_az,)).fetchone()
        if row is None:
            cols = ["akte_id"] + list(det_cols)
            platz = ", ".join(["?"] * len(cols))
            conn.execute(f"INSERT INTO unfalldetails ({', '.join(cols)}) VALUES ({platz})",
                         [akte_az] + list(det_cols.values()))
        else:
            setzt = ", ".join(f"{k}=?" for k in det_cols)
            conn.execute(f"UPDATE unfalldetails SET {setzt} WHERE id=?",
                         list(det_cols.values()) + [row["id"]])


# ── Personenschaden ──────────────────────────────────────────────────────────

def _geparst_personenschaden(ps: dict) -> List[Tuple[str, str, Any]]:
    ps = ps or {}
    verletzter = ps.get("verletzter") or {}
    kh = ps.get("krankenhaus") or {}
    hk = ps.get("hauskrank") or {}
    return [
        ("geburtsdatum", "Geburtsdatum", verletzter.get("geburtsdatum")),
        ("verletzungen_text", "Verletzungen", ps.get("verletzungen")),
        ("krankenhaus_name", "Krankenhaus", kh.get("name")),
        ("krankenhaus_von", "KH von", kh.get("von")),
        ("krankenhaus_bis", "KH bis", kh.get("bis")),
        ("krank_von", "AU von", hk.get("von")),
        ("krank_bis", "AU bis", hk.get("bis")),
    ]


def _akte_personenschaden(conn, akte_az: str) -> Dict[str, Any]:
    row = conn.execute(
        "SELECT geburtsdatum, verletzungen_text, krankenhaus_name, "
        "       krankenhaus_von, krankenhaus_bis, krank_von, krank_bis "
        "FROM personenschaden WHERE akte_id=?", (akte_az,)).fetchone()
    return dict(row) if row else {}


def _schreibe_personenschaden(conn, akte_az: str, aenderungen: Dict[str, Any]) -> None:
    voll = dict(aenderungen)
    if "krankenhaus_name" in voll:
        voll["krankenhaus_aufenthalt"] = 1
    if "krank_von" in voll:
        voll["krankgeschrieben"] = 1
    row = conn.execute("SELECT id FROM personenschaden WHERE akte_id=?",
                       (akte_az,)).fetchone()
    if row is None:
        cols = ["akte_id"] + list(voll)
        platz = ", ".join(["?"] * len(cols))
        conn.execute(f"INSERT INTO personenschaden ({', '.join(cols)}) VALUES ({platz})",
                     [akte_az] + list(voll.values()))
    else:
        setzt = ", ".join(f"{k}=?" for k in voll)
        conn.execute(f"UPDATE personenschaden SET {setzt} WHERE id=?",
                     list(voll.values()) + [row["id"]])
