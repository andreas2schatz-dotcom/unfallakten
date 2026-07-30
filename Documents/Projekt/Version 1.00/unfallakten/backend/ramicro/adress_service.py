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


def hole_adresse_details(adressnr: int) -> dict | None:
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT TOP 1
                    iAdressnummer     AS adressnr,
                    sAnrede           AS anrede,
                    sNachname         AS name,
                    sVorname          AS vorname,
                    sErsteAdresszeile AS firmenzeile,
                    [sStraße]         AS strasse,
                    sPLZ              AS plz,
                    sOrt              AS ort,
                    sTelefon          AS telefon,
                    sEMail            AS email
                FROM tblAdressen
                WHERE iAdressnummer = %s
                """,
                (adressnr,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {k: (row[k] if k == "adressnr" else (row[k] or ""))
                    for k in ("adressnr", "anrede", "name", "vorname",
                              "firmenzeile", "strasse", "plz", "ort",
                              "telefon", "email")}
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Adress-Detail nicht möglich: %s", e)
        return None
    except Exception as e:
        logger.warning("Adress-Detail fehlgeschlagen (adressnr=%s): %s",
                       adressnr, e)
        return None


def akten_zu_adresse(adressnr: int) -> list[dict]:
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT TOP 10
                    a.sAktenNummer          AS az,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung
                FROM tblAktenBeteiligte b
                INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
                WHERE b.iAdressnummer = %s
                  AND b.bDeaktiviert = 0
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer DESC
                """,
                (adressnr,),
            )
            return [{"az": r["az"], "kurzbezeichnung": r["kurzbezeichnung"] or ""}
                    for r in cur.fetchall()]
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler) as e:
        logger.warning("Akten-zu-Adresse nicht möglich: %s", e)
        return []
    except Exception as e:
        logger.warning("Akten-zu-Adresse fehlgeschlagen (adressnr=%s): %s",
                       adressnr, e)
        return []
