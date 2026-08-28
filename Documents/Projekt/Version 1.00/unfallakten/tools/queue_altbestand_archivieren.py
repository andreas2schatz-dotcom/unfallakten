"""Verschiebt wartende Intake-Dokumente in den Papierkorb (Grund 'altbestand').

Fuer den Testbetrieb: die Review-Queue sammelt den kompletten Posteingang,
solange niemand sie abarbeitet. Das Skript setzt denselben Soft-Delete wie
intake/verwerfen.py -- die Zeilen bleiben in der Datenbank, erscheinen im
Papierkorb-Reiter und lassen sich dort einzeln wiederherstellen.

    docker exec unfallakten-backend-dev python /app/tools/queue_altbestand_archivieren.py --dry-run
    docker exec unfallakten-backend-dev python /app/tools/queue_altbestand_archivieren.py --ausnehmen 474,475,476

Zurueckholen laesst sich ein kompletter Lauf ueber sein Datum:

    UPDATE intake_dokumente SET verworfen_grund=NULL, verworfen_am=NULL
    WHERE verworfen_grund='altbestand' AND verworfen_am LIKE '2026-08-28%';
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from backend.db.database import get_connection  # noqa: E402

GRUND = "altbestand"
VERWERFBARE_STATUS = ("neu", "bereit_zur_review", "pipeline_fehler", "laeuft")


def _ids_mit_kindern(conn, ids):
    """Ergaenzt Anhaenge, die zur selben E-Mail gehoeren wie ein geschuetztes
    Dokument -- sonst bleibt der Bogen stehen und seine Anlagen verschwinden."""
    if not ids:
        return set()
    platz = ",".join("?" * len(ids))
    rows = conn.execute(
        "SELECT DISTINCT k.intake_dokument_id AS id "
        "FROM zustellungen z "
        "JOIN zustellungen k ON k.parent_id = z.id "
        f"WHERE z.intake_dokument_id IN ({platz})",
        tuple(ids),
    ).fetchall()
    return set(ids) | {r["id"] for r in rows}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stichtag", help="nur Dokumente vor diesem Datum (JJJJ-MM-TT)")
    p.add_argument("--ausnehmen", default="",
                   help="Intake-IDs, die stehen bleiben (kommagetrennt)")
    p.add_argument("--kommentar", default="Altbestand Testbetrieb, Sammelarchivierung")
    p.add_argument("--dry-run", action="store_true", help="nur zaehlen, nichts schreiben")
    args = p.parse_args()

    geschuetzt_roh = [int(x) for x in args.ausnehmen.split(",") if x.strip()]

    with get_connection() as conn:
        geschuetzt = _ids_mit_kindern(conn, geschuetzt_roh)

        sql = ("SELECT id, klasse, registry_version FROM intake_dokumente "
               f"WHERE queue_status IN ({','.join('?' * len(VERWERFBARE_STATUS))}) "
               "  AND verworfen_am IS NULL")
        params = list(VERWERFBARE_STATUS)
        if args.stichtag:
            sql += " AND erstellt_am < ?"
            params.append(args.stichtag)
        kandidaten = [r for r in conn.execute(sql, params)
                      if r["id"] not in geschuetzt]

        print(f"Kandidaten: {len(kandidaten)}")
        if geschuetzt:
            print(f"Ausgenommen: {sorted(geschuetzt)}")
        if args.dry_run:
            print("(dry-run -- nichts geschrieben)")
            return 0

        jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")
        wert_neu = json.dumps({"grund": GRUND, "kommentar": args.kommentar},
                              ensure_ascii=False)
        for r in kandidaten:
            conn.execute(
                "UPDATE intake_dokumente "
                "SET verworfen_grund=?, verworfen_am=?, verworfen_von=NULL "
                "WHERE id=?", (GRUND, jetzt, r["id"]))
            conn.execute(
                "INSERT INTO korrektur_log "
                "(intake_dokument_id, feld, wert_alt, wert_neu, klasse, "
                " registry_version, benutzer_id) "
                "VALUES (?, 'verworfen', NULL, ?, ?, ?, NULL)",
                (r["id"], wert_neu, r["klasse"], r["registry_version"]))

    print(f"Archiviert: {len(kandidaten)} (verworfen_am = {jetzt})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
