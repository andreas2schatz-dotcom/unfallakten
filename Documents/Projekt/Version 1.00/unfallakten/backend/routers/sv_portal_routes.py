import logging
from flask import Blueprint, request, jsonify
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..ramicro.adress_service import hole_adresse_by_nr, suche_adressen
from ..ramicro.connector import get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler

logger = logging.getLogger(__name__)

sv_portal_bp = Blueprint("sv_portal", __name__, url_prefix="/einstellungen/sv-portal")


def _j(daten, status=200):
    return jsonify(daten), status


def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status


def _body():
    return request.get_json(silent=True) or {}


@sv_portal_bp.route("", methods=["GET"])
@login_erforderlich
def liste():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT s.adressnr, s.name, s.vorname, s.email,
                   s.portal_aktiv, s.einladung_gesendet_am, s.angelegt_am,
                   COUNT(DISTINCT b.akte_id) AS akten_anzahl
            FROM sv_portal_accounts s
            LEFT JOIN beteiligte b
                ON LOWER(b.email) = LOWER(s.email)
               AND b.rolle = 'sachverstaendiger'
            GROUP BY s.adressnr
            ORDER BY s.name
        """).fetchall()
    return _j([dict(r) for r in rows])


@sv_portal_bp.route("/suche", methods=["GET"])
@login_erforderlich
def suche():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return _j([])
    return _j(suche_adressen(q))


@sv_portal_bp.route("/vorschau/<int:adressnr>", methods=["GET"])
@login_erforderlich
def vorschau(adressnr: int):
    daten = hole_adresse_by_nr(adressnr)
    if daten is None:
        return _err("Adressnummer nicht gefunden oder RA-MICRO nicht erreichbar.", 404)
    return _j(daten)


@sv_portal_bp.route("", methods=["POST"])
@login_erforderlich
def anlegen():
    body = _body()
    try:
        adressnr = int(body.get("adressnr") or 0)
    except (TypeError, ValueError):
        return _err("adressnr muss eine Zahl sein.", 400)
    if not adressnr:
        return _err("adressnr fehlt.", 400)

    daten = hole_adresse_by_nr(adressnr)
    if daten is None:
        return _err("Adressnummer nicht gefunden oder RA-MICRO nicht erreichbar.", 404)
    if not daten.get("email"):
        return _err(
            "Diese Adresse hat keine E-Mail in RA-MICRO. Bitte dort nachtragen.", 422
        )

    with get_connection() as conn:
        if conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("Dieser SV hat bereits einen Portal-Account.", 409)
        conn.execute(
            "INSERT INTO sv_portal_accounts (adressnr, name, vorname, email) VALUES (?,?,?,?)",
            (adressnr, daten["name"], daten["vorname"], daten["email"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
    return _j(dict(row), 201)


@sv_portal_bp.route("/<int:adressnr>", methods=["DELETE"])
@login_erforderlich
def loeschen(adressnr: int):
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        conn.execute(
            "DELETE FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        )
        conn.commit()
    return _j({"geloescht": True})


@sv_portal_bp.route("/<int:adressnr>", methods=["PATCH"])
@login_erforderlich
def toggle_aktiv(adressnr: int):
    body = _body()
    aktiv = body.get("portal_aktiv")
    if aktiv not in (0, 1, True, False):
        return _err("portal_aktiv muss 0 oder 1 sein.", 400)
    aktiv_int = 1 if aktiv else 0
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        conn.execute(
            "UPDATE sv_portal_accounts SET portal_aktiv = ? WHERE adressnr = ?",
            (aktiv_int, adressnr),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
    return _j(dict(row))


@sv_portal_bp.route("/<int:adressnr>/einladung", methods=["POST"])
@login_erforderlich
def einladung_senden(adressnr: int):
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        conn.execute(
            "UPDATE sv_portal_accounts SET einladung_gesendet_am = datetime('now','localtime') WHERE adressnr = ?",
            (adressnr,),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
    return _j(dict(row))


def _hole_akten_fuer_sv(adressnr: int) -> list[dict]:
    """Fragt RA-MICRO nach allen Akten, in denen adressnr als SV eingetragen ist."""
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT DISTINCT a.sAktenNummer AS az, a.sAktenKurzBezeichnung AS ra_bezeichnung
                FROM tblAktenBeteiligte b
                INNER JOIN tblAkten a ON a.GUIDAkte = b.GUIDAkte
                WHERE b.iAdressnummer = %s
                  AND b.sBeteiligtenKennzeichen LIKE 'SV%%'
                  AND b.bDeaktiviert = 0
                """,
                (adressnr,),
            )
            return [{"az": r["az"], "ra_bezeichnung": r["ra_bezeichnung"] or ""}
                    for r in cur.fetchall() if r["az"]]
    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return []
    except Exception as e:
        logger.warning("SV-Akten-Lookup fehlgeschlagen (adressnr=%s): %s", adressnr, e)
        return []


@sv_portal_bp.route("/<int:adressnr>/akten", methods=["GET"])
@login_erforderlich
def akten(adressnr: int):
    with get_connection() as conn:
        sv = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
        if not sv:
            return _err("SV-Account nicht gefunden.", 404)

        ra_akten = _hole_akten_fuer_sv(adressnr)
        if not ra_akten:
            return _j([])

        ra_az_liste = [a["az"] for a in ra_akten]
        ra_map = {a["az"]: a for a in ra_akten}

        placeholders = ",".join("?" * len(ra_az_liste))
        sqlite_rows = conn.execute(
            f"SELECT az, kurzbezeichnung, unfalldatum, portal_aktiv FROM unfallakte WHERE az IN ({placeholders})",
            ra_az_liste,
        ).fetchall()
        sqlite_map = {r["az"]: dict(r) for r in sqlite_rows}

    result = []
    for az in sorted(ra_az_liste):
        ra_bezeichnung = ra_map[az]["ra_bezeichnung"]
        if az in sqlite_map:
            row = sqlite_map[az]
            result.append({
                **row,
                "kurzbezeichnung": row["kurzbezeichnung"] or ra_bezeichnung,
                "im_system": True,
            })
        else:
            result.append({"az": az, "kurzbezeichnung": ra_bezeichnung,
                           "unfalldatum": None, "portal_aktiv": 0, "im_system": False})
    return _j(result)


@sv_portal_bp.route("/<int:adressnr>/akten/alle", methods=["PATCH"])
@login_erforderlich
def akten_alle_toggle(adressnr: int):
    body = _body()
    aktiv = body.get("portal_aktiv")
    if aktiv not in (0, 1, True, False):
        return _err("portal_aktiv muss 0 oder 1 sein.", 400)
    aktiv_int = 1 if aktiv else 0
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        ra_akten = _hole_akten_fuer_sv(adressnr)
        for a in ra_akten:
            conn.execute("INSERT OR IGNORE INTO unfallakte (az) VALUES (?)", (a["az"],))
            conn.execute("UPDATE unfallakte SET portal_aktiv = ? WHERE az = ?", (aktiv_int, a["az"]))
        conn.commit()
    return _j({"aktualisiert": len(ra_akten), "portal_aktiv": aktiv_int})


@sv_portal_bp.route("/akten/<path:akte_az>/portal_aktiv", methods=["PATCH"])
@login_erforderlich
def toggle_portal_aktiv(akte_az: str):
    body = _body()
    aktiv = body.get("portal_aktiv")
    if aktiv not in (0, 1, True, False):
        return _err("portal_aktiv muss 0 oder 1 sein.", 400)
    aktiv_int = 1 if aktiv else 0
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO unfallakte (az) VALUES (?)", (akte_az,))
        conn.execute(
            "UPDATE unfallakte SET portal_aktiv = ? WHERE az = ?",
            (aktiv_int, akte_az),
        )
        conn.commit()
    return _j({"az": akte_az, "portal_aktiv": aktiv_int})
