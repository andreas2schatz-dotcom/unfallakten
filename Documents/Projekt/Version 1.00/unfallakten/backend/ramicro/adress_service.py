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
