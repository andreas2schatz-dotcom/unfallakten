"""Fuellt dokumente.dokument_datum aus dem gespeicherten Parse-Ergebnis.

Einmalig nach Migration 75 auszufuehren. Setzt nur leere Felder -- ein von
Hand korrigiertes Datum bleibt unangetastet.

    py tools/dokument_datum_nachziehen.py            # Trockenlauf
    py tools/dokument_datum_nachziehen.py --schreiben
"""
import argparse
import json
import os
import sys
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def nachziehen(trockenlauf: bool = True) -> Dict[str, int]:
    from backend.db.database import get_connection
    from backend.intake.registry_loader import lade_registry, standard_pfad
    from backend.services.dokument_bezeichnung import (
        dokument_datum_aus_feldern,
    )

    reg = lade_registry(standard_pfad())
    bericht = {"geprueft": 0, "gesetzt": 0, "ohne_datum": 0}

    with get_connection() as conn:
        zeilen = conn.execute(
            "SELECT id, dokumentenklasse, parse_json "
            "FROM dokumente WHERE dokument_datum IS NULL"
        ).fetchall()

        for zeile in zeilen:
            bericht["geprueft"] += 1
            try:
                felder = (json.loads(zeile["parse_json"] or "{}")
                          .get("felder") or {})
            except (ValueError, TypeError):
                felder = {}

            datum = dokument_datum_aus_feldern(
                zeile["dokumentenklasse"], felder, reg,
            )
            if not datum:
                bericht["ohne_datum"] += 1
                continue

            bericht["gesetzt"] += 1
            if not trockenlauf:
                conn.execute(
                    "UPDATE dokumente SET dokument_datum=? WHERE id=?",
                    (datum, zeile["id"]),
                )

        if not trockenlauf:
            conn.commit()

    return bericht


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schreiben", action="store_true",
                   help="Aenderungen tatsaechlich speichern")
    args = p.parse_args()
    ergebnis = nachziehen(trockenlauf=not args.schreiben)
    modus = "GESCHRIEBEN" if args.schreiben else "TROCKENLAUF"
    wirkung = ("Datum wurde gesetzt" if args.schreiben
               else "Datum koennte gesetzt werden (nichts geschrieben)")
    print(f"[{modus}] geprueft: {ergebnis['geprueft']}, "
          f"{wirkung}: {ergebnis['gesetzt']}, "
          f"ohne Datum: {ergebnis['ohne_datum']}")
