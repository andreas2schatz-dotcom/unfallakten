"""Generiert aus der Klassen-Registry (SSOT) die abgeleiteten Artefakte:
  * frontend/src/config/dokumentenklassen.generated.js  (DOK_TYPEN, KLASSE_TO_POS)
  * backend/registry/klasse_ereignistyp.yaml            (Klasse -> Ereignistyp)
  * backend/registry/rechnungstyp_mapping.yaml          (Klasse -> position_key)

Aufruf (Host, Projektwurzel):  py tools/gen_dokumentenklassen.py
Der Guard-Test test_gen_dokumentenklassen_guard.py schlaegt fehl, wenn eine
dieser Dateien nicht mehr zur Registry passt.
"""
import json
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)

from backend.intake.registry_loader import lade_registry, standard_pfad

_WARNUNG = "# GENERIERT von tools/gen_dokumentenklassen.py — NICHT von Hand editieren.\n"

_FE_POSITION_ANZEIGE = {
    "rep_rechnung_netto": "rep_rechnung_brutto",
    "__sv_kosten_vorsteuer__": "sv_kosten",
}


def _sortierte_klassen():
    reg = lade_registry(standard_pfad(), reload=True)
    return sorted(reg.klassen.items())


def _render_js():
    dok_typen = [{"value": k, "label": d.get("label", k)}
                 for k, d in _sortierte_klassen()]
    klasse_to_pos = {
        k: [_FE_POSITION_ANZEIGE.get(d["schadenposition"], d["schadenposition"])]
        for k, d in _sortierte_klassen()
        if d.get("schadenposition")
    }
    zeilen = [
        "// GENERIERT von tools/gen_dokumentenklassen.py — NICHT von Hand editieren.",
        "const DOK_TYPEN = " + json.dumps(dok_typen, ensure_ascii=False, indent=2) + ";",
        "const KLASSE_TO_POS = " + json.dumps(klasse_to_pos, ensure_ascii=False, indent=2) + ";",
        "export { DOK_TYPEN, KLASSE_TO_POS };",
        "",
    ]
    return "\n".join(zeilen)


def _render_klasse_ereignistyp():
    eintraege = {k: d["ereignistyp"] for k, d in _sortierte_klassen()
                 if d.get("ereignistyp")}
    zeilen = [_WARNUNG, "klasse_ereignistyp:"]
    for k, typ in sorted(eintraege.items()):
        zeilen.append(f"  {k}: {typ}")
    return "\n".join(zeilen) + "\n"


def _render_rechnungstyp_mapping():
    eintraege = {k: d["schadenposition"] for k, d in _sortierte_klassen()
                 if d.get("schadenposition")}
    zeilen = [_WARNUNG, "rechnungstyp_mapping:"]
    for k, pos in sorted(eintraege.items()):
        zeilen.append(f"  {k}: {pos}")
    return "\n".join(zeilen) + "\n"


def render_alles():
    return {
        "frontend/src/config/dokumentenklassen.generated.js": _render_js(),
        "backend/registry/klasse_ereignistyp.yaml": _render_klasse_ereignistyp(),
        "backend/registry/rechnungstyp_mapping.yaml": _render_rechnungstyp_mapping(),
    }


def main():
    for rel_pfad, inhalt in render_alles().items():
        voll = os.path.join(WURZEL, rel_pfad)
        with open(voll, "w", encoding="utf-8", newline="\n") as f:
            f.write(inhalt)
        print("geschrieben:", rel_pfad)


if __name__ == "__main__":
    main()
