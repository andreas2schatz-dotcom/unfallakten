"""
Modul 9 – Router: Abrechnungsschreiben & Prüfberichte
"""
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
try:
    from ..ramicro.wdm_regulierung_service import (
        lade_wdm_regulierung, wdm_zu_abrechnung, hat_wdm_regulierung
    )
    _WDM_VERFUEGBAR = True
except ImportError:
    _WDM_VERFUEGBAR = False
from ..models.akte import hole_akte_by_id
from ..services.portal_sync import _portal_flag
from ..models.abrechnungsschreiben import (
    hole_abrechnungsschreiben_by_akte, hole_abrechnungsschreiben_by_id,
    erstelle_abrechnungsschreiben, loesche_abrechnungsschreiben,
    aktualisiere_position, PositionNichtGefunden,
    hole_pruefberichte_by_akte, erstelle_pruefbericht,
    hole_klagebetrag, GUELTIGE_HAFTUNGSARTEN, POSITION_KEYS,
)

# Erweiterte Position-Keys (Migration 16: neue WDM + fehlende Frontend-Keys)
_POSITION_KEYS_ERWEITERT = set(POSITION_KEYS) | {
    "rep_gutachten_netto", "rep_rechnung_netto", "rep_rechnung_brutto",
    "verdienstausfall", "haushalt", "unkostenpauschale", "kostennb",
    "vorschuss",
    "sonstiges_wdm_1", "sonstiges_wdm_2", "sonstiges_wdm_3",
    "sonstiges_wdm_4", "sonstiges_wdm_5", "sonstiges_wdm_6",
}

logger = logging.getLogger(__name__)

abrechnung_bp  = Blueprint("abrechnung",  __name__, url_prefix="/akten/<path:akte_id>/abrechnungen")
pruefbericht_bp = Blueprint("pruefbericht", __name__, url_prefix="/akten/<path:akte_id>/pruefberichte")

def _j(d, s=200):     return jsonify(d), s
def _err(m, s, **kw): return jsonify({"fehler": m, "status": s, **kw}), s
def _body():           return request.get_json(silent=True) or {}
def _pruefe_akte(aid):
    """Akte in SQLite suchen; RA-Micro-Akten (Format X/YY) immer akzeptieren."""
    akte = hole_akte_by_id(aid)
    if akte:
        return akte
    # Akte existiert nur in RA-Micro (noch nicht in SQLite) → trotzdem erlauben
    if aid and "/" in str(aid):
        return True
    return None

def _parse_datum(datum_str: str) -> str:
    """Bug 7: Erzwingt YYYY-MM-DD. Leeres Datum → heutiges Datum."""
    s = (datum_str or "").strip()
    if not s:
        return datetime.today().strftime("%Y-%m-%d")
    # DD.MM.YYYY → YYYY-MM-DD konvertieren
    try:
        return datetime.strptime(s, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        raise ValueError(f"Ungültiges Datumsformat: {datum_str!r}. Erwartet: YYYY-MM-DD")


# ── Abrechnungsschreiben ──────────────────────────────────────────────────────

@abrechnung_bp.route("", methods=["GET"])
@login_erforderlich
def liste_abrechnungen(akte_id: str):
    """Bug 9: klagebetrag NICHT mehr hier enthalten."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    abrechnungen = hole_abrechnungsschreiben_by_akte(akte_id)
    return _j({"abrechnungen": [a.as_dict() for a in abrechnungen], "anzahl": len(abrechnungen)})


@abrechnung_bp.route("/<int:abid>", methods=["GET"])
@login_erforderlich
def hole_abrechnung(akte_id: str, abid: int):
    akte_obj = _pruefe_akte(akte_id)
    if not akte_obj:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte_obj.aktenzeichen if hasattr(akte_obj, "aktenzeichen") else akte_id
    ab = hole_abrechnungsschreiben_by_id(abid)
    if not ab or ab.akte_id != az:
        return _err(f"Abrechnungsschreiben {abid} nicht gefunden.", 404)
    return _j({"abrechnung": ab.as_dict()})


@abrechnung_bp.route("", methods=["POST"])
@login_erforderlich
def erstelle_abrechnung(akte_id: str):
    """Bug 7: Datum wird validiert."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    daten = _body()
    try:
        datum = _parse_datum(daten.get("datum", ""))
    except ValueError as e:
        return _err(str(e), 422, feld="datum")
    haftungsart = (daten.get("haftungsart") or "vollhaftung").strip()
    if haftungsart not in GUELTIGE_HAFTUNGSARTEN:
        return _err(f"Ungültige Haftungsart. Erlaubt: {', '.join(GUELTIGE_HAFTUNGSARTEN)}", 422)
    try:
        haftungsquote = float(daten.get("haftungsquote", 100.0))
        if not (0 <= haftungsquote <= 100):
            return _err("haftungsquote muss zwischen 0 und 100 liegen.", 422)
    except (TypeError, ValueError):
        return _err("haftungsquote muss eine Zahl sein.", 422)
    positionen = daten.get("positionen", [])
    if not isinstance(positionen, list):
        positionen = []
    for i, pos in enumerate(positionen):
        if pos.get("position_key") not in _POSITION_KEYS_ERWEITERT:
            return _err(f"Ungültiger position_key in Position {i}: {pos.get('position_key')!r}", 422)
    quelle = daten.get("quelle", "pdf")
    if quelle not in ("pdf", "manuell", "wdm"):
        quelle = "pdf"
    wdm_importiert = int(bool(daten.get("wdm_importiert", 0)))
    try:
        ab = erstelle_abrechnungsschreiben(
            akte_id=akte_id, datum=datum, haftungsart=haftungsart,
            haftungsquote=haftungsquote, bearbeiter_id=g.benutzer_id,
            versicherung=daten.get("versicherung"), referenz_nr=daten.get("referenz_nr"),
            haftungsbegruendung=daten.get("haftungsbegruendung"),
            notizen=daten.get("notizen"), dokument_id=daten.get("dokument_id"),
            positionen=positionen,
        )
    except ValueError as e:
        return _err(str(e), 422)
    # quelle + wdm_importiert per SQL setzen (Modell kennt die Felder evtl. noch nicht)
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE abrechnungsschreiben SET quelle=?, wdm_importiert=? WHERE id=?",
                (quelle, wdm_importiert, ab.id)
            )
            _portal_flag(conn, akte_id)
    except Exception:
        pass  # Spalten noch nicht vorhanden → ignorieren
    return _j({"abrechnung": ab.as_dict()}, 201)


@abrechnung_bp.route("/<int:abid>", methods=["DELETE"])
@login_erforderlich
def loesche_abrechnung(akte_id: str, abid: int):
    # v14c: _pruefe_akte gibt akte-Objekt zurück – az normalisieren, nie rohen URL-Param nutzen
    akte_obj = _pruefe_akte(akte_id)
    if not akte_obj:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte_obj.aktenzeichen if hasattr(akte_obj, "aktenzeichen") else akte_id
    # Direktes sqlite3 ohne get_connection() – garantierter Commit
    from ..db.database import get_db_path
    import sqlite3 as _sqlite3
    db_path = get_db_path()
    conn = _sqlite3.connect(db_path)
    conn.row_factory = _sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id FROM abrechnungsschreiben WHERE id=? AND akte_id=?",
            (abid, az)
        ).fetchone()
        if not row:
            conn.close()
            return _err(f"Abrechnungsschreiben {abid} nicht gefunden.", 404)
        conn.execute("PRAGMA foreign_keys = OFF")
        # Child zuerst löschen, dann Parent
        conn.execute("DELETE FROM regulierung_positionen WHERE abrechnungsschreiben_id=?", (abid,))
        conn.execute("DELETE FROM abrechnungsschreiben WHERE id=?", (abid,))
        conn.commit()   # explizit committen
        logger.info("Abrechnung %s gelöscht.", abid)
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error("Fehler beim Löschen Abrechnung %s: %s", abid, e)
        return _err(f"Fehler beim Löschen: {e}", 500)
    conn.close()
    return _j({"geloescht": True, "id": abid})


@abrechnung_bp.route("/<int:abid>/positionen/<int:pid>", methods=["PATCH"])
@login_erforderlich
def update_position(akte_id: str, abid: int, pid: int):
    """Bug 4: Ownership-Prüfung. Bug 6: Leerer Body → 422."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    daten = _body()
    felder = {}
    for f in ("betrag_gefordert", "betrag_reguliert"):
        if f in daten:
            try:    felder[f] = float(daten[f])
            except: return _err(f"{f} muss eine Zahl sein.", 422)
    if "kuerzungsart_id"           in daten: felder["kuerzungsart_id"]           = daten["kuerzungsart_id"]
    if "kuerzung_freitext"         in daten: felder["kuerzung_freitext"]         = daten["kuerzung_freitext"]
    if "fuer_klage_vorgemerkt"     in daten: felder["fuer_klage_vorgemerkt"]     = int(bool(daten["fuer_klage_vorgemerkt"]))
    if "sv_stellungnahme_ausstehend" in daten: felder["sv_stellungnahme_ausstehend"] = int(bool(daten["sv_stellungnahme_ausstehend"]))
    if not felder:  # Bug 6
        return _err("Keine aktualisierbaren Felder im Request-Body.", 422)
    try:
        pos = aktualisiere_position(pid, abid=abid, akte_id=akte_id, **felder)  # Bug 4
    except PositionNichtGefunden as e:
        return _err(str(e), 404)
    if pos is None:
        return _err(f"Position {pid} nicht gefunden.", 404)
    return _j({"position": pos.as_dict()})


@abrechnung_bp.route("/klagebetrag", methods=["GET"])
@login_erforderlich
def klagebetrag(akte_id: str):
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    return _j(hole_klagebetrag(akte_id))


# ── Hilfsfunktion: quelle direkt aus DB lesen ───────────────────────────────
def _hole_quelle(abid: int) -> str:
    """Liest quelle aus DB (Fallback wenn Modell das Feld noch nicht kennt)."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT quelle FROM abrechnungsschreiben WHERE id=?", (abid,)
            ).fetchone()
            return (row["quelle"] if row else None) or "pdf"
    except Exception:
        return "pdf"


# ── PUT: Manuelle Abrechnung bearbeiten ──────────────────────────────────────

@abrechnung_bp.route("/<int:abid>", methods=["PUT"])
@login_erforderlich
def aktualisiere_abrechnung(akte_id: str, abid: int):
    """Bearbeitet eine manuelle Abrechnung komplett (inkl. Positionen)."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    ab = hole_abrechnungsschreiben_by_id(abid)
    if not ab or ab.akte_id != akte_id:
        return _err(f"Abrechnungsschreiben {abid} nicht gefunden.", 404)
    quelle = getattr(ab, "quelle", None) or _hole_quelle(abid)
    if quelle not in (None, "manuell"):
        return _err("Nur manuell erfasste Abrechnungen sind bearbeitbar.", 403)

    daten = _body()
    try:
        datum = _parse_datum(daten.get("datum", ""))
    except ValueError as e:
        return _err(str(e), 422, feld="datum")

    positionen = daten.get("positionen", [])
    gesamt_gefordert = round(sum(float(p.get("betrag_gefordert") or 0) for p in positionen), 2)
    gesamt_reguliert = round(sum(float(p.get("betrag_reguliert") or 0) for p in positionen), 2)
    gesamt_kuerzung  = round(gesamt_gefordert - gesamt_reguliert, 2)

    from ..db.database import get_connection
    with get_connection() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("""
            UPDATE abrechnungsschreiben SET
                datum=?, versicherung=?, referenz_nr=?,
                haftungsart=?, haftungsquote=?,
                haftungsbegruendung=?, notizen=?,
                gesamt_gefordert=?, gesamt_reguliert=?
            WHERE id=? AND akte_id=?
        """, (
            datum,
            daten.get("versicherung", ""),
            daten.get("referenz_nr", ""),
            daten.get("haftungsart", "vollhaftung"),
            float(daten.get("haftungsquote") or 100),
            daten.get("haftungsbegruendung", ""),
            daten.get("notizen", ""),
            gesamt_gefordert, gesamt_reguliert,
            abid, akte_id
        ))
        # gesamt_kuerzung nur wenn Spalte existiert
        try:
            conn.execute(
                "UPDATE abrechnungsschreiben SET gesamt_kuerzung=? WHERE id=?",
                (gesamt_kuerzung, abid)
            )
        except Exception:
            pass

        # Positionen ersetzen
        conn.execute(
            "DELETE FROM regulierung_positionen WHERE abrechnungsschreiben_id=?",
            (abid,)
        )
        for pos in positionen:
            g = round(float(pos.get("betrag_gefordert") or 0), 2)
            r = round(float(pos.get("betrag_reguliert") or 0), 2)
            if g <= 0 and r <= 0:
                continue
            pkey = pos.get("position_key", "sonstiges")
            if pkey not in _POSITION_KEYS_ERWEITERT:
                pkey = "sonstiges"
            conn.execute("""
                INSERT INTO regulierung_positionen
                    (abrechnungsschreiben_id, position_key, position_label,
                     betrag_gefordert, betrag_reguliert,
                     kuerzungsart_id, kuerzung_freitext,
                     fuer_klage_vorgemerkt)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                abid, pkey,
                pos.get("position_label"),
                g, r,
                pos.get("kuerzungsart_id"),
                pos.get("kuerzung_freitext", ""),
                1 if pos.get("fuer_klage_vorgemerkt") else 0,
            ))

        conn.execute("PRAGMA foreign_keys = ON")
    ab_aktuell = hole_abrechnungsschreiben_by_id(abid)
    return _j({"abrechnung": ab_aktuell.as_dict()})


# ── WDM-Check: Regulierungsdaten in RA-Micro vorhanden? ─────────────────────

@abrechnung_bp.route("/wdm-check", methods=["GET"])
@login_erforderlich
def wdm_check(akte_id: str):
    """
    Prüft ob WDM-Regulierungsdaten vorhanden aber noch nicht importiert.
    → { verfuegbar: bool, bereits_importiert: bool, vorschau: dict|null }
    """
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    if not _WDM_VERFUEGBAR:
        return _j({"verfuegbar": False, "bereits_importiert": False,
                   "vorschau": None, "hinweis": "wdm_regulierung_service nicht verfügbar"})

    # Bereits importiert?
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as n FROM abrechnungsschreiben "
                "WHERE akte_id=? AND quelle='wdm'", (akte_id,)
            ).fetchone()
            if row and row["n"] > 0:
                return _j({"verfuegbar": False, "bereits_importiert": True, "vorschau": None})
    except Exception:
        pass

    # WDM laden
    try:
        # lade_wdm_regulierung baut Verbindung selbst auf
        wdm = lade_wdm_regulierung(akte_id)
    except Exception as e:
        return _j({"verfuegbar": False, "bereits_importiert": False,
                   "vorschau": None, "fehler": str(e)})

    if not hat_wdm_regulierung(wdm or {}):
        return _j({"verfuegbar": False, "bereits_importiert": False, "vorschau": None})

    vorschau = wdm_zu_abrechnung(wdm)
    return _j({"verfuegbar": True, "bereits_importiert": False, "vorschau": vorschau})


# ── WDM-Import: Regulierungsdaten als Abrechnung speichern ──────────────────

@abrechnung_bp.route("/wdm-import", methods=["POST"])
@login_erforderlich
def wdm_import(akte_id: str):
    """Importiert WDM-Regulierungsdaten als Abrechnung (quelle='wdm')."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    if not _WDM_VERFUEGBAR:
        return _err("wdm_regulierung_service nicht verfügbar – Patch einspielen.", 501)

    # Doppel-Import verhindern (auch ohne quelle-Spalte: über notizen-Feld)
    from ..db.database import get_connection
    with get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT COUNT(*) as n FROM abrechnungsschreiben "
                "WHERE akte_id=? AND quelle='wdm'", (akte_id,)
            ).fetchone()
            bereits = row["n"] > 0 if row else False
        except Exception:
            # Spalte quelle noch nicht vorhanden – Fallback auf notizen
            row2 = conn.execute(
                "SELECT COUNT(*) as n FROM abrechnungsschreiben "
                "WHERE akte_id=? AND notizen LIKE '%WDM importiert%'", (akte_id,)
            ).fetchone()
            bereits = (row2["n"] if row2 else 0) > 0
        if bereits:
            return _err("WDM bereits importiert.", 409)

    # WDM laden + konvertieren (Verbindung wird im Service selbst aufgebaut)
    try:
        wdm = lade_wdm_regulierung(akte_id)
        ab_data = wdm_zu_abrechnung(wdm or {})
    except Exception as e:
        return _err(f"WDM-Lesefehler: {e}", 500)

    if not ab_data:
        return _err("Keine WDM-Regulierungsdaten gefunden.", 404)

    # Als Abrechnung speichern
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            # FK-Checks temporär deaktivieren (regulierung_positionen hat FK auf abrechnungsschreiben)
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("""
                INSERT INTO abrechnungsschreiben
                    (akte_id, datum, versicherung, referenz_nr,
                     haftungsart, haftungsquote, haftungsbegruendung,
                     notizen, gesamt_gefordert, gesamt_reguliert,
                     parse_status, erfasst_von)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                akte_id, ab_data["datum"], "", "",
                ab_data.get("haftungsart", "vollhaftung"),
                ab_data.get("haftungsquote", 100),
                "", ab_data.get("notizen", "Aus RA-Micro WDM importiert"),
                ab_data["gesamt_gefordert"], ab_data["gesamt_reguliert"],
                "erfolgreich", g.benutzer_id,
            ))
            abid = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

            # quelle + wdm_importiert setzen (nach Migration 16)
            try:
                conn.execute(
                    "UPDATE abrechnungsschreiben SET quelle='wdm', wdm_importiert=1 WHERE id=?",
                    (abid,)
                )
            except Exception:
                pass

            for pos in ab_data["positionen"]:
                pkey = pos["position_key"]
                if pkey not in _POSITION_KEYS_ERWEITERT:
                    pkey = "sonstiges"
                conn.execute("""
                    INSERT INTO regulierung_positionen
                        (abrechnungsschreiben_id, position_key, position_label,
                         betrag_gefordert, betrag_reguliert,
                         fuer_klage_vorgemerkt)
                    VALUES (?,?,?,?,?,0)
                """, (
                    abid, pkey,
                    pos.get("position_label"),
                    pos["betrag_gefordert"],
                    pos["betrag_reguliert"],
                ))

            conn.execute("PRAGMA foreign_keys = ON")
        # Minimale Response mit der neuen ID – Frontend lädt danach selbst frisch
        return _j({"id": abid, "abrechnung": {"id": abid, "akte_id": akte_id,
            "datum": ab_data.get("datum",""), "quelle": "wdm",
            "gesamt_gefordert": ab_data.get("gesamt_gefordert", 0),
            "gesamt_reguliert": ab_data.get("gesamt_reguliert", 0),
            "positionen": []}}, 201)
    except Exception as e:
        logger.error("WDM-Import Fehler: %s", e, exc_info=True)
        return _err(f"Datenbankfehler beim WDM-Import: {e}", 500)


# ── Prüfberichte ─────────────────────────────────────────────────────────────

@pruefbericht_bp.route("", methods=["GET"])
@login_erforderlich
def liste_pruefberichte(akte_id: str):
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    berichte = hole_pruefberichte_by_akte(akte_id)
    return _j({"pruefberichte": [b.as_dict() for b in berichte], "anzahl": len(berichte)})


@pruefbericht_bp.route("", methods=["POST"])
@login_erforderlich
def neuer_pruefbericht(akte_id: str):
    """Bug 7: Datum wird validiert. Bug 10: kuerzungen als Array."""
    if not _pruefe_akte(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    daten = _body()
    try:
        datum = _parse_datum(daten.get("datum", ""))
    except ValueError as e:
        return _err(str(e), 422, feld="datum")
    kuerzungen_raw  = daten.get("kuerzungen")
    kuerzungen_json = None
    if kuerzungen_raw is not None:
        if not isinstance(kuerzungen_raw, list):  # Bug 10
            return _err("kuerzungen muss ein Array sein.", 422, feld="kuerzungen")
        kuerzungen_json = json.dumps(kuerzungen_raw, ensure_ascii=False)

    def _float(key):
        v = daten.get(key)
        try: return float(v) if v is not None else None
        except (TypeError, ValueError): return None

    bericht = erstelle_pruefbericht(
        akte_id=akte_id, datum=datum, bearbeiter_id=g.benutzer_id,
        abrechnungsschreiben_id=daten.get("abrechnungsschreiben_id"),
        gutachter=daten.get("gutachter"),
        notizen=daten.get("notizen"),
        dokument_id=daten.get("dokument_id"),
        kuerzungen_json=kuerzungen_json,
        # PDF-Parser Felder
        pruefdienstleister=daten.get("pruefdienstleister") or None,
        vorgangsnummer=daten.get("vorgangsnummer") or None,
        schadennummer=daten.get("schadennummer") or None,
        reparaturkosten_vor_pruefung=_float("reparaturkosten_vor_pruefung"),
        abzug_technisch=_float("abzug_technisch"),
        abzug_werkstattalternative=_float("abzug_werkstattalternative"),
        abzug_gesamt=_float("abzug_gesamt"),
        reparaturkosten_nach_pruefung=_float("reparaturkosten_nach_pruefung"),
        referenzwerkstatt_name=daten.get("referenzwerkstatt_name") or None,
        referenzwerkstatt_adresse=daten.get("referenzwerkstatt_adresse") or None,
        referenzwerkstatt_plz_ort=daten.get("referenzwerkstatt_plz_ort") or None,
        referenzwerkstatt_entfernung=_float("referenzwerkstatt_entfernung"),
        ist_image_pdf=1 if daten.get("ist_image_pdf") else 0,
        fahrzeug_hersteller=daten.get("fahrzeug_hersteller") or None,
        fahrzeug_typ=daten.get("fahrzeug_typ") or None,
        fahrzeug_kennzeichen=daten.get("fahrzeug_kennzeichen") or None,
        parse_status="erfolgreich" if daten.get("pruefdienstleister") else "manuell",
    )
    return _j({"pruefbericht": bericht.as_dict()}, 201)
