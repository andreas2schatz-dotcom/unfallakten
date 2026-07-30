"""Aktenanlage-Vorgaenge: OMA-XML schreiben, RA-MICRO-Erkennung, Abschluss."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from ..db.database import get_connection
from ..ramicro.oma_xml import schreibe_oma_xml
from ..ramicro.akten_erkennung import finde_neue_akten

logger = logging.getLogger(__name__)

WARN_SEKUNDEN = 15 * 60


class VorgangExistiertFehler(Exception):
    pass


def _export_ordner() -> Path:
    return Path(os.environ.get("OMA_EXPORT_PFAD", "/app/oma_export"))


def _sekunden_seit(ts: str) -> int:
    try:
        t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return max(0, int((datetime.now() - t).total_seconds()))
    except Exception:
        return 0


def _vorgang_dict(row: dict, kandidaten=None) -> dict:
    name = " ".join(x for x in (row["mandant_vorname"],
                                row["mandant_nachname"]) if x)
    vor_s = _sekunden_seit(row["angelegt_am"])
    return {
        "id": row["id"],
        "intake_dokument_id": row["intake_dokument_id"],
        "zustellung_id": row["zustellung_id"],
        "status": row["status"],
        "mandant_name": name,
        "erkanntes_az": row["erkanntes_az"],
        "kandidaten": kandidaten or [],
        "angelegt_am": row["angelegt_am"],
        "angelegt_vor_s": vor_s,
        "warnung": row["status"] == "laeuft" and vor_s > WARN_SEKUNDEN,
    }


def hole_vorgang(vorgang_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM aktenanlage_vorgaenge WHERE id=?",
            (vorgang_id,)).fetchone()
    return _vorgang_dict(dict(row)) if row else None


def lege_vorgang_an(formular: dict, intake_dokument_id=None,
                    zustellung_id=None, benutzer_id=None) -> dict:
    mandant = formular.get("mandant") or {}
    unfall = formular.get("unfall") or {}
    nachname = (mandant.get("nachname") or "").strip()
    if not nachname:
        raise ValueError("Mandant-Nachname ist Pflicht.")
    if not (unfall.get("unfalldatum") or "").strip():
        raise ValueError("Unfalldatum ist Pflicht.")

    xml_pfad = schreibe_oma_xml(formular, _export_ordner())

    with get_connection() as conn:
        if intake_dokument_id is not None:
            offen = conn.execute(
                "SELECT id FROM aktenanlage_vorgaenge "
                "WHERE intake_dokument_id=? "
                "  AND status IN ('laeuft','akte_erkannt')",
                (intake_dokument_id,)).fetchone()
            if offen:
                try:
                    Path(xml_pfad).unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("XML %s nicht loeschbar (409-Pfad): %s",
                                   xml_pfad, exc)
                raise VorgangExistiertFehler(
                    f"Für dieses Dokument läuft bereits Aktenanlage-Vorgang "
                    f"{offen['id']}.")
        cur = conn.execute(
            "INSERT INTO aktenanlage_vorgaenge "
            "(intake_dokument_id, zustellung_id, formular_json, xml_pfad, "
            " mandant_nachname, mandant_vorname, mandant_adressnr, "
            " angelegt_von) VALUES (?,?,?,?,?,?,?,?)",
            (intake_dokument_id, zustellung_id, json.dumps(formular),
             str(xml_pfad), nachname,
             (mandant.get("vorname") or "").strip() or None,
             (mandant.get("bekannt_adressnr") or "").strip() or None,
             benutzer_id),
        )
        vorgang_id = cur.lastrowid
    logger.info("Aktenanlage-Vorgang %s angelegt (XML: %s)",
                vorgang_id, xml_pfad)
    return hole_vorgang(vorgang_id)


def _uebernimm_unfalldaten(akte_az: str, formular_json: str) -> None:
    try:
        unfall = (json.loads(formular_json).get("unfall") or {})
    except Exception:
        unfall = {}
    with get_connection() as conn:
        if (unfall.get("unfalldatum") or "").strip():
            conn.execute(
                "UPDATE unfallakte SET unfalldatum=? "
                "WHERE az=? AND (unfalldatum IS NULL OR unfalldatum='')",
                (unfall["unfalldatum"].strip(), akte_az))
        if (unfall.get("unfallort") or "").strip():
            conn.execute(
                "UPDATE unfallakte SET unfallort=? "
                "WHERE az=? AND (unfallort IS NULL OR unfallort='')",
                (unfall["unfallort"].strip(), akte_az))


def hole_offene_vorgaenge() -> dict:
    with get_connection() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM aktenanlage_vorgaenge "
            "WHERE status IN ('laeuft','akte_erkannt') ORDER BY id")]

    vorgaenge = []
    ramicro_ok = True
    for row in rows:
        kandidaten = []
        if row["status"] == "laeuft":
            erg = finde_neue_akten(row["angelegt_am"],
                                   nachname=row["mandant_nachname"],
                                   adressnr=row["mandant_adressnr"] or "")
            if not erg["verfuegbar"]:
                ramicro_ok = False
            elif len(erg["treffer"]) == 1:
                az = erg["treffer"][0]["az"]
                schatten_ok = True
                if row["intake_dokument_id"] is None:
                    try:
                        from ..models.akte import erstelle_oder_hole_akte
                        erstelle_oder_hole_akte(az)
                        _uebernimm_unfalldaten(az, row["formular_json"])
                    except Exception as exc:
                        schatten_ok = False
                        logger.warning(
                            "Schattenakte für %s nicht anlegbar: %s", az, exc)
                if schatten_ok:
                    with get_connection() as conn:
                        cur = conn.execute(
                            "UPDATE aktenanlage_vorgaenge "
                            "SET status='akte_erkannt', erkanntes_az=?, "
                            "    erkannt_am=datetime('now','localtime') "
                            "WHERE id=? AND status='laeuft'", (az, row["id"]))
                        aktualisiert = cur.rowcount > 0
                    if aktualisiert:
                        row["status"] = "akte_erkannt"
                        row["erkanntes_az"] = az
            elif len(erg["treffer"]) > 1:
                kandidaten = erg["treffer"]
        vorgaenge.append(_vorgang_dict(row, kandidaten))
    return {"vorgaenge": vorgaenge, "ramicro_verfuegbar": ramicro_ok}


def brich_vorgang_ab(vorgang_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT xml_pfad, status FROM aktenanlage_vorgaenge WHERE id=?",
            (vorgang_id,)).fetchone()
        if not row or row["status"] not in ("laeuft", "akte_erkannt"):
            return False
        conn.execute(
            "UPDATE aktenanlage_vorgaenge SET status='abgebrochen' "
            "WHERE id=?", (vorgang_id,))
    try:
        Path(row["xml_pfad"]).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("XML %s nicht löschbar: %s", row["xml_pfad"], exc)
    return True


def schliesse_vorgang_ab(vorgang_id: int) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE aktenanlage_vorgaenge SET status='abgeschlossen' "
            "WHERE id=? AND status='akte_erkannt'", (vorgang_id,))
        return cur.rowcount > 0


def _hat_offene_geschwister(gruppe: int) -> bool:
    """True, wenn in der E-Mail-Gruppe noch ein Dokument auf Freigabe wartet.

    Das soeben freigegebene Dokument hat zum Hook-Zeitpunkt bereits
    queue_status='freigegeben' (post_freigabe setzt das VOR dem Aufruf
    dieses Hooks) und zaehlt damit korrekt nicht als offen mit.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM zustellungen z "
            "JOIN intake_dokumente d ON d.id = z.intake_dokument_id "
            "WHERE COALESCE(z.parent_id, z.id) = ? "
            "  AND d.queue_status = 'bereit_zur_review' "
            "  AND d.verworfen_am IS NULL "
            "LIMIT 1", (gruppe,)).fetchone()
    return row is not None


def schliesse_vorgaenge_bei_freigabe(intake_dokument_id: int,
                                     akte_az: str) -> dict | None:
    with get_connection() as conn:
        zust = conn.execute(
            "SELECT id, parent_id FROM zustellungen "
            "WHERE intake_dokument_id=? ORDER BY id LIMIT 1",
            (intake_dokument_id,)).fetchone()
        gruppe = (zust["parent_id"] or zust["id"]) if zust else None
        rows = [dict(r) for r in conn.execute(
            "SELECT v.* FROM aktenanlage_vorgaenge v "
            "LEFT JOIN zustellungen z ON z.id = v.zustellung_id "
            "WHERE v.status IN ('laeuft','akte_erkannt') "
            "  AND (v.intake_dokument_id = ? "
            "       OR (? IS NOT NULL AND COALESCE(z.parent_id, z.id) = ?))",
            (intake_dokument_id, gruppe, gruppe))]

    if not rows:
        return None

    geschlossen = []
    hinweis = None
    for row in rows:
        # Unfalldaten-Uebernahme ist unabhaengig vom Schliessen und
        # idempotent (Leer-Guards in _uebernimm_unfalldaten) -- greift bei
        # JEDER Freigabe auf das erkannte AZ, auch wenn Geschwister noch
        # offen sind (Spec 3.4).
        if row["erkanntes_az"] and row["erkanntes_az"] == akte_az:
            _uebernimm_unfalldaten(akte_az, row["formular_json"])

        # Kein ermittelbares Gruppen-Kriterium (keine Zustellung zum
        # freigegebenen Dokument) -> wie bisher sofort schliessen.
        if gruppe is not None and _hat_offene_geschwister(gruppe):
            continue

        with get_connection() as conn:
            conn.execute(
                "UPDATE aktenanlage_vorgaenge SET status='abgeschlossen' "
                "WHERE id=?", (row["id"],))
        geschlossen.append(row["id"])
        if row["erkanntes_az"] and row["erkanntes_az"] != akte_az:
            hinweis = (f"Aktenanlage-Vorgang {row['id']} geschlossen; die in "
                       f"RA-MICRO angelegte Akte {row['erkanntes_az']} "
                       "bleibt bestehen.")
    return {"geschlossen": geschlossen, "hinweis": hinweis}
