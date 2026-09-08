"""
Gerichtsvorschlag aus dem Unfallort.

Zwei Stufen, die erste gewinnt:

  1. Gepflegte Ortsliste (gerichtsorte.yaml) -- Wissen ueber die
     Gerichtsbezirke, das aus keinem Namen ableitbar ist.
  2. Namensabgleich gegen die Gerichtsadressen aus RA-MICRO -- Heuristik
     fuer alles, was nicht in der Liste steht.

Der frueher benutzte Abgleich nahm das erste Wort des Unfallorts und
verglich es als Teilstring. Da varU-ORT Freitext ist ("Auf der Rosenhoehe
68, Offenbach", "A 66 Abfahrt zur A 5", "Parkplatz Globus, Maintal"), war
das Suchwort meist ein Strassen- oder Fuellwort: "auf" steckt in
"K-auf-beuren", "am" in "Am-berg", "bad" in "Bad-en-Baden". Hier wird
ausschliesslich wortgenau verglichen.
"""

from typing import Any, Dict, List, Optional

from .gerichtsort_registry import (
    GerichtsortRegistry, finde_gericht, ort_woerter,
)

# Gerichtsbezeichnungen, die dem Ortsnamen vorangehen und beim Zerlegen
# des Namens nicht als Ort zaehlen.
_GERICHTSARTEN = (
    "amtsgericht", "landgericht", "oberlandesgericht", "arbeitsgericht",
    "sozialgericht", "landessozialgericht", "verwaltungsgericht",
    "oberverwaltungsgericht", "finanzgericht", "kammergericht",
)

# Zweigstellen sollen nur gewinnen, wenn nichts anderes passt.
_ZWEIGSTELLE = ("ast", "zweigstelle", "zwst")

# Ortsnamen-Vorsilben, die fuer sich genommen nichts kennzeichnen: "Bad"
# steht vor Dutzenden Staedten. Beginnt der Gerichtssitz damit, muss der
# ganze Name im Unfallort vorkommen -- sonst landete "Bad Nauheim" beim
# Amtsgericht Bad Saulgau (oder frueher bei Baden-Baden).
_UNSPEZIFISCH = frozenset({
    "bad", "sankt", "neu", "alt", "groß", "gross", "klein",
    "ober", "unter", "bergisch", "hohen",
})


def _gerichtsstadt(gericht: Dict[str, Any]) -> List[str]:
    """Ortswoerter des Gerichtssitzes -- aus sOrt, ersatzweise aus dem Namen."""
    woerter = ort_woerter(gericht.get("ort"))
    if woerter:
        return woerter
    # Kein sOrt gepflegt (26 Adressen in tblAdressen): Ort aus dem Namen
    # ableiten, sonst kaeme so ein Eintrag ganz ohne Ortspruefung durch --
    # genau so schlug "Amtsgericht Alsfeld" bei "A 661" zu.
    aus_name = ort_woerter(gericht.get("name"))
    while aus_name and aus_name[0] in _GERICHTSARTEN:
        aus_name = aus_name[1:]
    for i, w in enumerate(aus_name):
        if w in _ZWEIGSTELLE:
            aus_name = aus_name[:i]
            break
    return aus_name


def _enthaelt_folge(woerter: List[str], folge: List[str]) -> bool:
    n = len(folge)
    if not n or n > len(woerter):
        return False
    return any(woerter[i:i + n] == folge for i in range(len(woerter) - n + 1))


def _bewerte(unfallort_woerter: List[str], gericht: Dict[str, Any]) -> int:
    stadt = _gerichtsstadt(gericht)
    if not stadt:
        return 0
    name_low = (gericht.get("name") or "").lower()

    if _enthaelt_folge(unfallort_woerter, stadt):
        # Ganzer Gerichtssitz kommt im Unfallort vor -- laenger ist genauer,
        # damit schlaegt "Frankfurt am Main" das "Frankfurt (Oder)".
        score = 100 + 10 * len(stadt)
    elif stadt[0] in unfallort_woerter and stadt[0] not in _UNSPEZIFISCH:
        # Nur das Kopfwort passt. Jeder unbelegte Zusatz des Gerichtssitzes
        # macht den Treffer unsicherer.
        offen = [w for w in stadt[1:] if w not in unfallort_woerter]
        score = 40 - 6 * len(offen)
    else:
        return 0

    if score <= 0:
        return 0
    if "amtsgericht" in name_low:
        score += 5
    if any(z in ort_woerter(name_low) for z in _ZWEIGSTELLE):
        score -= 8
    return score


def waehle_gericht(unfallort: Optional[str],
                   gerichte: List[Dict[str, Any]],
                   registry: Optional[GerichtsortRegistry] = None) -> List[Dict[str, Any]]:
    """Kandidaten fuer das zustaendige Gericht, bester zuerst.

    ``gerichte`` sind Adresszeilen aus RA-MICRO
    (adressnr, name, strasse, plz, ort).
    """
    woerter = ort_woerter(unfallort)
    if not woerter:
        return []

    # ── Stufe 1: gepflegte Ortsliste ────────────────────────────────────
    aus_liste = finde_gericht(unfallort, registry)
    if aus_liste:
        treffer = {"adressnr": None, "name": aus_liste, "strasse": "",
                   "plz": "", "ort": "", "quelle": "ortsliste", "_score": 1000}
        # Anschrift ergaenzen, wenn das Gericht in den Adressen steht.
        passend = [g for g in gerichte
                   if (g.get("name") or "").strip().lower() == aus_liste.strip().lower()]
        if passend:
            g = passend[0]
            treffer.update({
                "adressnr": g.get("adressnr"),
                "name":     (g.get("name") or "").strip(),
                "strasse":  (g.get("strasse") or "").strip(),
                "plz":      (g.get("plz") or "").strip(),
                "ort":      (g.get("ort") or "").strip(),
            })
        return [treffer]

    # ── Stufe 2: Namensabgleich ─────────────────────────────────────────
    beste: Dict[tuple, Dict[str, Any]] = {}
    for g in gerichte:
        score = _bewerte(woerter, g)
        if score <= 0:
            continue
        name = (g.get("name") or "").strip()
        ort  = (g.get("ort") or "").strip()
        schluessel = (name.lower(), ort.lower())
        vorhanden = beste.get(schluessel)
        if vorhanden and vorhanden["_score"] >= score:
            continue
        beste[schluessel] = {
            "adressnr": g.get("adressnr"),
            "name":     name,
            "strasse":  (g.get("strasse") or "").strip(),
            "plz":      (g.get("plz") or "").strip(),
            "ort":      ort,
            "quelle":   "unfallort_match",
            "_score":   score,
        }

    return sorted(beste.values(), key=lambda x: (-x["_score"], x["name"]))
