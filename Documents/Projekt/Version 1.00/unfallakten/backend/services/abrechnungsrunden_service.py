"""
Abrechnungsrunden-Service — zweite, eigenstaendige Lese-Faltung auf dem
Ereignisstrom (strikt getrennt von der Positions-Faltung; liest, schreibt
nie). Runde n = n-tes nicht ersetztes ``abrechnung_eingegangen``-Ereignis
je Akte. Nachzahlung = Rueckgang des gekuerzt-Betrags je
(position_key, kuerzungsart_id) zwischen benachbarten Runden.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..db.database import get_connection

_TOLERANZ = 0.005


def leite_runden_ab(akte_az: str) -> Dict[str, Any]:
    with get_connection() as conn:
        koepfe = conn.execute(
            "SELECT id, datum, dokument_id FROM ereignisse "
            "WHERE akte_az=? AND ereignistyp='abrechnung_eingegangen' "
            "  AND ersetzt_durch IS NULL "
            "ORDER BY datum ASC, id ASC",
            (akte_az,),
        ).fetchall()

        runden: List[Dict[str, Any]] = []
        kuerzungen_je_runde: List[Dict[Tuple[str, Optional[int]], float]] = []
        typ_codes: Dict[Optional[int], Optional[str]] = {None: None}

        for kopf in koepfe:
            zeilen = conn.execute(
                "SELECT ep.position_key, ep.betrag, ep.kuerzungsart_id, "
                "       ka.typ_code "
                "FROM ereignis_positionen ep "
                "LEFT JOIN kuerzungsarten ka ON ka.id = ep.kuerzungsart_id "
                "WHERE ep.ereignis_id=? AND ep.ersetzt_durch IS NULL "
                "  AND ep.wirkung='gekuerzt'",
                (kopf["id"],),
            ).fetchall()

            kuerzungen: Dict[Tuple[str, Optional[int]], float] = {}
            positionen: Dict[str, Dict[str, Any]] = {}
            for z in zeilen:
                schluessel = (z["position_key"], z["kuerzungsart_id"])
                betrag = float(z["betrag"] or 0.0)
                kuerzungen[schluessel] = round(
                    kuerzungen.get(schluessel, 0.0) + betrag, 2)
                typ_codes[z["kuerzungsart_id"]] = z["typ_code"]
                eintrag = positionen.setdefault(
                    z["position_key"], {"gekuerzt": 0.0, "typen": {}})
                eintrag["gekuerzt"] = round(eintrag["gekuerzt"] + betrag, 2)
                typ_schluessel = ("null" if z["kuerzungsart_id"] is None
                                  else str(z["kuerzungsart_id"]))
                eintrag["typen"][typ_schluessel] = round(
                    eintrag["typen"].get(typ_schluessel, 0.0) + betrag, 2)

            runden.append({
                "ereignis_id": kopf["id"],
                "datum": kopf["datum"],
                "dokument_id": kopf["dokument_id"],
                "gekuerzt_gesamt": round(sum(kuerzungen.values()), 2),
                "positionen": positionen,
            })
            kuerzungen_je_runde.append(kuerzungen)

    vergleich: List[Dict[str, Any]] = []
    for i in range(1, len(kuerzungen_je_runde)):
        alt, neu = kuerzungen_je_runde[i - 1], kuerzungen_je_runde[i]
        for schluessel in sorted(set(alt) | set(neu),
                                 key=lambda s: (s[0], s[1] is None,
                                                s[1] or 0)):
            betrag_alt = round(alt.get(schluessel, 0.0), 2)
            betrag_neu = round(neu.get(schluessel, 0.0), 2)
            delta = round(betrag_neu - betrag_alt, 2)
            if abs(betrag_alt) <= _TOLERANZ and abs(betrag_neu) <= _TOLERANZ:
                continue
            if delta < -_TOLERANZ:
                status = "nachzahlung"
            elif delta > _TOLERANZ:
                status = "neu" if abs(betrag_alt) <= _TOLERANZ else "erhoeht"
            else:
                status = "aufrechterhalten"
            pk, art_id = schluessel
            vergleich.append({
                "position_key": pk,
                "kuerzungsart_id": art_id,
                "typ_code": typ_codes.get(art_id),
                "runde_alt": i,
                "runde_neu": i + 1,
                "betrag_alt": betrag_alt,
                "betrag_neu": betrag_neu,
                "delta": delta,
                "status": status,
            })

    return {"runden": runden, "vergleich": vergleich}
