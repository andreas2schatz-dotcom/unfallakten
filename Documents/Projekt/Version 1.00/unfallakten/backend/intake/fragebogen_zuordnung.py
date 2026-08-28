"""Verdichtet die Akten-Kandidaten eines Unfallbogens zu einer Ampel.

gruen    -- genau ein starker Kandidat, Zuordnung steht
pruefen  -- mehrere starke Kandidaten oder nur ein schwaches Merkmal
abgelegt -- passt nur zu einer abgeschlossenen Akte; keine Aktenanlage
            anbieten, sonst entsteht eine Dublette zu einem alten Fall
neu      -- kein Kandidat, vermutlich ein Neumandat
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

STARK_AB = 0.7

_BEGRUENDUNG = {
    "aktenzeichen":   "Aktenzeichen im Bogen",
    "az_exakt":       "Aktenzeichen im Bogen",
    "az_basis":       "Aktenzeichen im Bogen",
    "mandanten_mail": "Mandanten-E-Mail",
    "kfz_mandant":    "eigenes Kennzeichen",
    "unfalltag_name": "Unfalltag + Name",
    "unfalltag":      "Unfalltag",
    "kfz_gegner":     "Kennzeichen des Gegners",
    "nachname":       "Nachname",
    "mandantenname":  "Nachname",
}


def begruendung(quelle: Optional[str]) -> Optional[str]:
    if not quelle:
        return None
    return _BEGRUENDUNG.get(quelle, quelle)


def bewerte(kandidaten: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    liste = [k for k in (kandidaten or []) if k and k.get("akte_az")]
    if not liste:
        return {"ampel": "neu", "akte_az": None, "kurzbezeichnung": None,
                "begruendung": None, "kandidaten_anzahl": 0,
                "abgelegt_am": None}

    # Laufende Akten haben immer Vorrang; abgelegte sind nur der Rueckfall,
    # wenn gar keine laufende Akte zum Bogen passt.
    laufend = [k for k in liste if not k.get("abgelegt")]
    sortiert = sorted(laufend or liste,
                      key=lambda k: k.get("score") or 0.0, reverse=True)
    bester = sortiert[0]

    if not laufend:
        return {
            "ampel": "abgelegt",
            "akte_az": bester["akte_az"],
            "kurzbezeichnung": bester.get("bezeichnung"),
            "begruendung": begruendung(bester.get("quelle")),
            "kandidaten_anzahl": len(liste),
            "abgelegt_am": bester.get("abgelegt_am"),
        }

    starke = [k for k in sortiert if (k.get("score") or 0.0) >= STARK_AB]
    return {
        "ampel": "gruen" if len(starke) == 1 else "pruefen",
        "akte_az": bester["akte_az"],
        "kurzbezeichnung": bester.get("bezeichnung"),
        "begruendung": begruendung(bester.get("quelle")),
        "kandidaten_anzahl": len(liste),
        "abgelegt_am": None,
    }
