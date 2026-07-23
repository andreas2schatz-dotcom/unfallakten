"""
Einmalige Umstellung der Textbausteine auf Genus-Platzhalter (Weg 2,
Phase-1-Nachtrag): übersetzt die beim RTF-Import nie aufgelösten
RA-MICRO-Grammatikcodes (<@a2A>, <@S2A>, <@PP1A> …) in die sprechenden
Platzhalter aus stellungnahme_service._GENUS_FORMEN.

Aufruf (Dry-Run):  docker exec unfallakten-backend-dev python /app/tools/genus_umstellung_bausteine.py
Anwenden:          docker exec unfallakten-backend-dev python /app/tools/genus_umstellung_bausteine.py --write
Backup der Altwerte: /app/data/genus_umstellung_backup_<ts>.json
"""
import argparse
import datetime
import json
import os
import sqlite3

# Reihenfolge: laengste Muster zuerst (Wort+Suffix-Kombis vor Einzelcodes).
ERSETZUNGEN = [
    ("Unser<@P1A>", "<UNSER_GROSS>"),
    ("unser<@P1A>", "<UNSER>"),
    ("Unser<@P2A>", "<UNSERES>"),
    ("unser<@P2A>", "<UNSERES>"),
    ("Unser<@P3A>", "<UNSEREM>"),
    ("unser<@P3A>", "<UNSEREM>"),
    ("Mandant<@S1A>", "<MANDANT_NOM>"),
    ("Mandant<@S2A>", "<MANDANT_OBL>"),
    ("Mandant<@S3A>", "<MANDANT_OBL>"),
    ("<@a1A>", "<UNSER>"),
    ("<@a2A>", "<UNSERES>"),
    ("<@A3A>", "<UNSEREM>"),
    ("<@a3P>", "<UNSEREM>"),
    ("<@PP1A>", "<PRON_GROSS>"),
    ("<@pp1A>", "<PRON>"),
    ("<@pp2A>", "<POSS_ER>"),
    ("<@pp4A>", "<PRON_AKK>"),
    ("<@ps11A>", "<POSS>"),
]

# Freitext-Stellen mit direktem Mandant-Bezug (handverifiziert 2026-07-23).
FREITEXT = {
    6: [("Unser Mandant aber muss sich",
         "<UNSER_GROSS> <MANDANT_NOM> aber muss sich")],
    16: [("für das Fahrzeug des Mandanten ist hier",
          "für das Fahrzeug <UNSERES> <MANDANT_OBL> ist hier")],
    28: [("Diese Kosten sind unserem Mandanten entstanden, der als Laie",
          "Diese Kosten sind unserer Mandantschaft entstanden, die als Laie")],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="Aenderungen in die DB schreiben (sonst Dry-Run)")
    parser.add_argument("--db", default=os.environ.get(
        "DB_PATH", "/app/data/unfallakten.db"))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, bezeichnung, textbaustein FROM kuerzungsarten "
        "WHERE TRIM(COALESCE(textbaustein,'')) != '' ORDER BY id").fetchall()

    backup, aenderungen = {}, []
    for r in rows:
        alt = r["textbaustein"]
        neu = alt
        for von, nach in ERSETZUNGEN:
            neu = neu.replace(von, nach)
        for von, nach in FREITEXT.get(r["id"], []):
            if von not in neu:
                print(f"WARNUNG id={r['id']}: Freitext-Anker nicht gefunden: {von!r}")
            neu = neu.replace(von, nach)
        if neu != alt:
            backup[r["id"]] = alt
            aenderungen.append((r["id"], r["bezeichnung"], alt, neu))

    print(f"{len(aenderungen)} Bausteine mit Aenderungen:")
    for bid, bez, alt, neu in aenderungen:
        print(f"  id={bid} {bez}")

    rest = conn.execute(
        "SELECT COUNT(*) FROM kuerzungsarten WHERE textbaustein LIKE '%<@%'"
    ).fetchone()[0]

    if not args.write:
        print("\nDry-Run — nichts geschrieben. Mit --write anwenden.")
        conn.close()
        return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_pfad = os.path.join(os.path.dirname(args.db),
                               f"genus_umstellung_backup_{ts}.json")
    with open(backup_pfad, "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1)
    print(f"Backup: {backup_pfad}")

    for bid, _bez, _alt, neu in aenderungen:
        conn.execute("UPDATE kuerzungsarten SET textbaustein=? WHERE id=?",
                     (neu, bid))
    conn.commit()

    rest = conn.execute(
        "SELECT id FROM kuerzungsarten WHERE textbaustein LIKE '%<@%'"
    ).fetchall()
    if rest:
        print(f"WARNUNG: uebrige RA-MICRO-Codes in ids {[x['id'] for x in rest]}")
    else:
        print("Keine RA-MICRO-@-Codes mehr in den Bausteinen.")
    conn.close()


if __name__ == "__main__":
    main()
