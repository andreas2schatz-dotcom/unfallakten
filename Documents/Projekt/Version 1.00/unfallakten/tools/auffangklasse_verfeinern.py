"""Wendet die Auffangklassen-Verfeinerung auf den Bestand an.

Neue Klassen greifen sonst erst beim naechsten Pipeline-Lauf. Diese Nachfuehrung
aendert ausschliesslich die Klasse und nur dort, wo 'sonstiges' steht -- sie
ruehrt weder Felder noch Handkorrekturen an (klasse_quelle='manuell' bleibt
unberuehrt). Die Datumsfelder eines Versicherungsschreibens fuellt erst ein
echter Reparse.

    docker exec unfallakten-backend-dev python /app/tools/auffangklasse_verfeinern.py --dry-run
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from backend.db.database import get_connection
from backend.intake.klassifikator import verfeinere_auffangklasse


def sammle():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT i.id, i.klasse, i.klasse_quelle, z.signale_json "
            "FROM intake_dokumente i "
            "JOIN zustellungen z ON z.intake_dokument_id = i.id "
            "WHERE i.klasse = 'sonstiges' AND i.verworfen_grund IS NULL "
            "  AND i.queue_status = 'bereit_zur_review' "
            "  AND COALESCE(i.klasse_quelle, '') != 'manuell'"
        ).fetchall()

    signale_je_dok = {}
    for r in rows:
        try:
            s = json.loads(r["signale_json"] or "{}")
        except (ValueError, TypeError):
            s = {}
        signale_je_dok.setdefault(r["id"], []).append(s)

    treffer = []
    for dok_id, signale in signale_je_dok.items():
        neue, quelle = verfeinere_auffangklasse("sonstiges", signale)
        if quelle:
            treffer.append((dok_id, neue, quelle))
    return treffer


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    treffer = sammle()
    verteilung = Counter(f"{neu} ({q})" for _, neu, q in treffer)
    print(f"Kandidaten in der Queue: {len(treffer)}")
    for k, n in verteilung.most_common():
        print(f"  {n:5}  {k}")

    if args.dry_run:
        print("\nTrockenlauf -- nichts geaendert.")
        return

    with get_connection() as conn:
        for dok_id, neue, _ in treffer:
            conn.execute("UPDATE intake_dokumente SET klasse=? WHERE id=?", (neue, dok_id))
        conn.commit()
    print(f"\n{len(treffer)} Dokumente umgeklassifiziert.")


if __name__ == "__main__":
    main()
