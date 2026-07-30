"""Read-only-Erkennung neu angelegter RA-MICRO-Akten (Aktenanlage-Feature).

dtAnlage-Existenz ist nicht in jeder Installation belegt (siehe Spec
Abschnitt 9) -- bei Abfragefehlern wird 'nicht verfuegbar' gemeldet,
die manuelle Zuordnung bleibt immer moeglich.
"""
import logging

from .connector import (get_ramicro_connection, RaMicroNichtAktiv,
                        RaMicroVerbindungsFehler)

logger = logging.getLogger(__name__)


def finde_neue_akten(seit_iso: str, nachname: str = "",
                     adressnr: str = "") -> dict:
    nachname = (nachname or "").strip()
    adressnr = (adressnr or "").strip()
    if not nachname and not adressnr:
        return {"verfuegbar": True, "treffer": []}
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            if adressnr:
                person_filter = "b.iAdressnummer = %(adressnr)s"
            else:
                person_filter = "adr.sNachname LIKE %(nachname)s"
            cur.execute(
                f"""
                SELECT DISTINCT TOP 5
                    a.sAktenNummer          AS az,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung
                FROM tblAkten a
                INNER JOIN tblAktenBeteiligte b ON b.GUIDAkte = a.GUIDAkte
                LEFT JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.iBeteiligtenArt = 1
                  AND b.bDeaktiviert = 0
                  AND {person_filter}
                  AND a.dtAnlage >= %(seit)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                """,
                {"adressnr": adressnr, "nachname": f"%{nachname}%",
                 "seit": seit_iso},
            )
            treffer = [{"az": r["az"],
                        "kurzbezeichnung": r["kurzbezeichnung"] or ""}
                       for r in cur.fetchall()]
            return {"verfuegbar": True, "treffer": treffer}
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Akten-Erkennung nicht möglich: %s", e)
        return {"verfuegbar": False, "treffer": []}
    except Exception as e:
        logger.warning("Akten-Erkennung fehlgeschlagen: %s", e)
        return {"verfuegbar": False, "treffer": []}
