import logging
from flask import Blueprint, request, jsonify
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..ramicro.adress_service import hole_adresse_by_nr

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


@sv_portal_bp.route("/<int:adressnr>/akten", methods=["GET"])
@login_erforderlich
def akten(adressnr: int):
    with get_connection() as conn:
        sv = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
        if not sv:
            return _err("SV-Account nicht gefunden.", 404)
        rows = conn.execute(
            """
            SELECT DISTINCT u.az, u.kurzbezeichnung, u.unfalldatum, u.portal_aktiv
            FROM beteiligte b
            JOIN unfallakte u ON u.az = b.akte_id
            WHERE LOWER(b.email) = LOWER(?)
              AND b.rolle = 'sachverstaendiger'
            ORDER BY u.unfalldatum DESC
            """,
            (sv["email"],),
        ).fetchall()
    return _j([dict(r) for r in rows])


@sv_portal_bp.route("/akten/<path:akte_az>/portal_aktiv", methods=["PATCH"])
@login_erforderlich
def toggle_portal_aktiv(akte_az: str):
    body = _body()
    aktiv = body.get("portal_aktiv")
    if aktiv not in (0, 1, True, False):
        return _err("portal_aktiv muss 0 oder 1 sein.", 400)
    aktiv_int = 1 if aktiv else 0
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM unfallakte WHERE az = ?", (akte_az,)
        ).fetchone():
            return _err("Akte nicht gefunden.", 404)
        conn.execute(
            "UPDATE unfallakte SET portal_aktiv = ? WHERE az = ?",
            (aktiv_int, akte_az),
        )
        conn.commit()
    return _j({"az": akte_az, "portal_aktiv": aktiv_int})
