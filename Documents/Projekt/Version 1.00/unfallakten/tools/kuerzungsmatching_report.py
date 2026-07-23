"""
Kennzahlen-Report Kürzungstaxonomie (Zielwerte DECISIONS 2026-07-23:
Abdeckung >= 90 %, Trefferquote >= 75 %, Positionszuordnung >= 90 %).
Aufruf: docker exec unfallakten-backend-dev python /app/tools/kuerzungsmatching_report.py [--seit 2026-07-25]
"""
import argparse
import os
import sqlite3
import sys


def _conn(db_pfad: str) -> sqlite3.Connection:
    if not os.path.exists(db_pfad):
        sys.exit(f"DB nicht gefunden: {db_pfad}")
    conn = sqlite3.connect(db_pfad)
    conn.row_factory = sqlite3.Row
    return conn


def _quote(zaehler: int, nenner: int) -> str:
    if nenner == 0:
        return "n/a (0 Faelle)"
    return f"{100.0 * zaehler / nenner:.1f} % ({zaehler}/{nenner})"


def abdeckung(conn: sqlite3.Connection) -> None:
    nenner = conn.execute(
        "SELECT COUNT(*) FROM regulierung_positionen "
        "WHERE betrag_gefordert - betrag_reguliert > 0.005"
    ).fetchone()[0]
    zaehler = conn.execute(
        "SELECT COUNT(*) FROM regulierung_positionen rp "
        "JOIN kuerzungsarten ka ON ka.id = rp.kuerzungsart_id "
        "WHERE rp.betrag_gefordert - rp.betrag_reguliert > 0.005 "
        "  AND TRIM(COALESCE(ka.textbaustein, '')) != ''"
    ).fetchone()[0]
    print(f"1. Abdeckung (Kuerzung -> Typ mit Baustein):  {_quote(zaehler, nenner)}"
          f"   [Ziel >= 90 %]")


def trefferquote(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT COALESCE(typ_quelle, 'manuell') AS q, COUNT(*) AS n "
        "FROM regulierung_positionen WHERE kuerzungsart_id IS NOT NULL "
        "GROUP BY COALESCE(typ_quelle, 'manuell')"
    ).fetchall()
    je_quelle = {r["q"]: r["n"] for r in rows}
    nenner = sum(je_quelle.values())
    zaehler = je_quelle.get("regel", 0) + je_quelle.get("llm", 0)
    print(f"2. Trefferquote Typ-Vorschlag:                {_quote(zaehler, nenner)}"
          f"   [Ziel >= 75 %]")
    for q in sorted(je_quelle):
        print(f"     - {q}: {je_quelle[q]}")


def positionszuordnung(conn: sqlite3.Connection, seit: str) -> None:
    koepfe = conn.execute(
        "SELECT e.id, e.dokument_id, e.betragswirkung_gesamt, "
        "       (SELECT SUM(ep.betrag) FROM ereignis_positionen ep "
        "        WHERE ep.ereignis_id = e.id AND ep.wirkung = 'anerkannt' "
        "          AND ep.ersetzt_durch IS NULL) AS summe_anerkannt "
        "FROM ereignisse e "
        "WHERE e.ereignistyp = 'abrechnung_eingegangen' "
        "  AND e.ersetzt_durch IS NULL AND e.datum >= ?",
        (seit,),
    ).fetchall()
    nenner = len(koepfe)
    zaehler = 0
    for k in koepfe:
        soll = k["betragswirkung_gesamt"]
        if soll is None and k["dokument_id"] is not None:
            row = conn.execute(
                "SELECT gesamt_reguliert FROM abrechnungsschreiben "
                "WHERE dokument_id = ?", (k["dokument_id"],),
            ).fetchone()
            soll = row["gesamt_reguliert"] if row else None
        ist = k["summe_anerkannt"] or 0.0
        if soll is not None and abs(float(soll) - float(ist)) < 1.0:
            zaehler += 1
    print(f"3. Positions-/Betragszuordnung (seit {seit}): {_quote(zaehler, nenner)}"
          f"   [Ziel >= 90 %]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seit", default="2026-07-25",
                        help="Stichtag fuer Kennzahl 3 (Default 2026-07-25)")
    parser.add_argument("--db", default=os.environ.get(
        "DB_PATH", "/app/data/unfallakten.db"))
    args = parser.parse_args()

    conn = _conn(args.db)
    print(f"Kennzahlen-Report Kuerzungstaxonomie  (DB: {args.db})")
    print("=" * 70)
    abdeckung(conn)
    trefferquote(conn)
    positionszuordnung(conn, args.seit)
    conn.close()


if __name__ == "__main__":
    main()
