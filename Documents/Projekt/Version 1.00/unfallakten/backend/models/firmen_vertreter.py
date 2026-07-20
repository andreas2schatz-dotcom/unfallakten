"""Single Source of Truth: globaler Firmen-Vertreter-Speicher.

Normalisierung, Upsert und Lookup fuer die Tabelle firmen_vertreter. Schreib-
weg (firmen_routes) und Leseweg (klage_routes-Serializer) nutzen dieselben
Funktionen, damit der normalisierte Schluessel garantiert identisch ist.
"""
import re


def firma_norm(firma) -> str:
    return re.sub(r"\s+", " ", (firma or "").strip().lower())


def upsert_firmen_vertreter(conn, firma_anzeige, vertreter_name,
                            vertreter_funktion="") -> bool:
    key = firma_norm(firma_anzeige)
    name = (vertreter_name or "").strip()
    if not key or not name:
        return False
    conn.execute(
        """INSERT INTO firmen_vertreter
               (firma_norm, firma_anzeige, vertreter_name, vertreter_funktion,
                aktualisiert_am)
           VALUES (?, ?, ?, ?, datetime('now','localtime'))
           ON CONFLICT(firma_norm) DO UPDATE SET
               firma_anzeige      = excluded.firma_anzeige,
               vertreter_name     = excluded.vertreter_name,
               vertreter_funktion = excluded.vertreter_funktion,
               aktualisiert_am    = excluded.aktualisiert_am""",
        (key, (firma_anzeige or "").strip(), name,
         (vertreter_funktion or "").strip()),
    )
    return True


def hole_firmen_vertreter(conn, firma):
    key = firma_norm(firma)
    if not key:
        return None
    row = conn.execute(
        "SELECT vertreter_name, vertreter_funktion "
        "FROM firmen_vertreter WHERE firma_norm = ?",
        (key,),
    ).fetchone()
    if not row:
        return None
    return {
        "vertreter_name": row["vertreter_name"] or "",
        "vertreter_funktion": row["vertreter_funktion"] or "",
    }
