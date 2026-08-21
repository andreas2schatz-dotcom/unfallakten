from flask import Blueprint, request, jsonify
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..ramicro.adress_service import hole_adresse_by_nr, suche_adressen
from ..services.sv_zugriff_sync import hole_akten_fuer_sv, zugriffe_abgleichen
from ..services.portal_sync import process_queue

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
            SELECT adressnr, name, vorname, email,
                   portal_aktiv, einladung_gesendet_am, angelegt_am
            FROM sv_portal_accounts
            ORDER BY name
        """).fetchall()
        ergebnis = []
        for r in rows:
            eintrag = dict(r)
            az_liste = [a["az"] for a in hole_akten_fuer_sv(r["adressnr"])]
            eintrag["akten_anzahl"] = len(az_liste)
            if az_liste:
                platzhalter = ",".join("?" * len(az_liste))
                eintrag["akten_laufend"] = conn.execute(
                    "SELECT COUNT(*) AS n FROM unfallakte "
                    "WHERE ramicro_abgelegt = 0 AND az IN ({})".format(platzhalter),
                    az_liste,
                ).fetchone()["n"]
            else:
                eintrag["akten_laufend"] = 0
            ergebnis.append(eintrag)
    return _j(ergebnis)


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


@sv_portal_bp.route("/<int:adressnr>/akten", methods=["GET"])
@login_erforderlich
def akten(adressnr: int):
    with get_connection() as conn:
        sv = conn.execute(
            "SELECT * FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone()
        if not sv:
            return _err("SV-Account nicht gefunden.", 404)

        ra_akten = hole_akten_fuer_sv(adressnr)
        if not ra_akten:
            return _j([])

        ra_az_liste = [a["az"] for a in ra_akten]
        ra_map = {a["az"]: a for a in ra_akten}

        placeholders = ",".join("?" * len(ra_az_liste))
        sqlite_rows = conn.execute(
            f"SELECT az, kurzbezeichnung, unfalldatum, portal_aktiv, portal_gesperrt, "
            f"ramicro_abgelegt FROM unfallakte WHERE az IN ({placeholders})",
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
                           "unfalldatum": None, "portal_aktiv": 0,
                           "portal_gesperrt": 0, "ramicro_abgelegt": 0,
                           "im_system": False})
    return _j(result)


@sv_portal_bp.route("/akten/<path:akte_az>/portal_gesperrt", methods=["PATCH"])
@login_erforderlich
def toggle_portal_gesperrt(akte_az: str):
    body = _body()
    gesperrt = body.get("portal_gesperrt")
    if gesperrt not in (0, 1, True, False):
        return _err("portal_gesperrt muss 0 oder 1 sein.", 400)
    wert = 1 if gesperrt else 0
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO unfallakte (az) VALUES (?)", (akte_az,))
        conn.execute(
            "UPDATE unfallakte SET portal_gesperrt = ?, portal_aktiv = ? WHERE az = ?",
            (wert, 0 if wert else 1, akte_az),
        )
        conn.commit()
    return _j({"az": akte_az, "portal_gesperrt": wert})


@sv_portal_bp.route("/<int:adressnr>/zugriffe-abgleichen", methods=["POST"])
@login_erforderlich
def zugriffe_abgleichen_route(adressnr: int):
    with get_connection() as conn:
        if not conn.execute(
            "SELECT 1 FROM sv_portal_accounts WHERE adressnr = ?", (adressnr,)
        ).fetchone():
            return _err("SV-Account nicht gefunden.", 404)
        process_queue(conn, max_batch=1000)
        bericht = zugriffe_abgleichen(conn, adressnr)
    return _j(bericht)
