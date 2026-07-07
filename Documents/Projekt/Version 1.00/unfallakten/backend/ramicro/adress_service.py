import logging
from .connector import get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler

logger = logging.getLogger(__name__)


def hole_adresse_by_nr(adressnr: int) -> dict | None:
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT TOP 1
                    iAdressnummer AS adressnr,
                    sNachname     AS name,
                    sVorname      AS vorname,
                    sEMail        AS email
                FROM tblAdressen
                WHERE iAdressnummer = %s
                """,
                (adressnr,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "adressnr": row["adressnr"],
                "name":     row["name"]    or "",
                "vorname":  row["vorname"] or "",
                "email":    row["email"]   or "",
            }
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Adress-Lookup nicht möglich: %s", e)
        return None
    except Exception as e:
        logger.warning("Adress-Lookup fehlgeschlagen (adressnr=%s): %s", adressnr, e)
        return None


def suche_adressen(q: str) -> list[dict]:
    q = q.strip()
    if not q:
        return []
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            if q.isdigit():
                cur.execute(
                    """
                    SELECT TOP 10
                        iAdressnummer AS adressnr,
                        sNachname     AS name,
                        sVorname      AS vorname,
                        sEMail        AS email
                    FROM tblAdressen
                    WHERE iAdressnummer = %s
                    """,
                    (int(q),),
                )
            else:
                cur.execute(
                    """
                    SELECT TOP 10
                        iAdressnummer AS adressnr,
                        sNachname     AS name,
                        sVorname      AS vorname,
                        sEMail        AS email
                    FROM tblAdressen
                    WHERE sNachname LIKE %s OR sVorname LIKE %s
                    ORDER BY sNachname, sVorname
                    """,
                    (f"%{q}%", f"%{q}%"),
                )
            rows = cur.fetchall()
            return [
                {
                    "adressnr": r["adressnr"],
                    "name":     r["name"]    or "",
                    "vorname":  r["vorname"] or "",
                    "email":    r["email"]   or "",
                }
                for r in rows
            ]
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Adressen-Suche nicht möglich: %s", e)
        return []
    except Exception as e:
        logger.warning("Adressen-Suche fehlgeschlagen (q=%s): %s", q, e)
        return []
