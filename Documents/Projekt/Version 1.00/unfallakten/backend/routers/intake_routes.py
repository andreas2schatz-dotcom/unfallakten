"""
Modul – Router: Intake-Review (S1.8)
====================================
Review-UI-Backend fuer den neuen Pipeline-Pfad. Verwaltet die
Verarbeitungs-Queue (bereit_zur_review + pipeline_fehler), erlaubt
manuelle Reklassifikation + Feldkorrekturen und schliesst die
Freigabe an die Akte ab.

Endpunkte:
  GET   /intake/queue                       Liste Alter -> Konfidenz
  GET   /intake/dokument/<id>               Detail + parse + Kandidaten
  PATCH /intake/dokument/<id>/klasse        manuelle Reklassifikation
  POST  /intake/dokument/<id>/reparse       erzwungener Re-Parse
  PATCH /intake/dokument/<id>/felder        Feld-Korrektur
  POST  /intake/dokument/<id>/freigabe      einzige Schreib-Op Richtung Akte
  POST  /intake/dokument/<id>/verwerfen     Soft-Delete aus der Queue
  GET   /intake/ereignistypen               Registry-Katalog fuer Freigabe-UI

Design:
  * Alle Endpunkte verlangen Auth (@login_erforderlich).
  * Nur JSON-Responses.
  * Keine Alt-Routen werden angefasst -- Umschaltung ist S1.9.
  * K-2: Freigabe-Detail liefert bereits `akten_kandidaten` fuer den
    Dialog. Die Payload kann `kandidaten_ereignisse` (Ereignis-Vorschlaege
    zur Bestaetigung) und `ersetzt_ids` (K-M2b positionsscharfe Ersetzung)
    enthalten. In S1.8 werden sie als Kontext ins korrektur_log geschrieben
    -- die Persistierung ins Positionsmodell uebernimmt P1.5.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Blueprint, g, jsonify, request, send_file, Response

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..intake.queue import enqueue
from ..intake import split_service
from ..ramicro.output_adapter import schreibe_dokument
from ..services.dokument_bezeichnung import baue_bezeichnung
from ..services.fragebogen_uebernahme import (
    parse_fragebogen_payload, vorschau_liste, uebernehme,
)

logger = logging.getLogger(__name__)

intake_bp = Blueprint("intake", __name__, url_prefix="/intake")


def _j(daten: Any, status: int = 200):
    return jsonify(daten), status


def _err(msg: str, status: int, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status


def _parse(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


def _lade_intake(intake_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM intake_dokumente WHERE id=?", (intake_id,)
        ).fetchone()
    return dict(row) if row else None


def _sekunden_seit(iso_ts: Optional[str]) -> Optional[int]:
    """Sekunden zwischen ``iso_ts`` (Format 'YYYY-MM-DD HH:MM:SS') und jetzt.

    N-08: Bearbeitungsdauer Queue-Oeffnung -> Freigabe. None bei fehlendem
    oder unparsbarem Zeitstempel; negative Differenzen (Uhr-Drift) -> 0.
    """
    if not iso_ts:
        return None
    try:
        start = datetime.fromisoformat(str(iso_ts)[:19])
    except (TypeError, ValueError):
        return None
    delta = (datetime.now() - start).total_seconds()
    return int(delta) if delta >= 0 else 0


def _log_korrektur(conn, intake_id: int, feld: str,
                    wert_alt: Any, wert_neu: Any, klasse: Optional[str],
                    registry_version: Optional[str],
                    benutzer_id: Optional[int]) -> None:
    """Schreibt eine korrektur_log-Zeile. wert_alt/neu duerfen JSON sein."""
    def _s(v):
        if v is None or isinstance(v, str):
            return v
        return json.dumps(v, ensure_ascii=False)
    conn.execute(
        "INSERT INTO korrektur_log "
        "(intake_dokument_id, feld, wert_alt, wert_neu, klasse, "
        " registry_version, benutzer_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (intake_id, feld, _s(wert_alt), _s(wert_neu), klasse,
         registry_version, benutzer_id),
    )


# ─── GET /intake/queue ────────────────────────────────────────────────────────

@intake_bp.route("/queue", methods=["GET"])
@login_erforderlich
def hole_queue():
    """Liste aller Dokumente in bereit_zur_review oder pipeline_fehler.

    Sortierung (Stufe 1, freigabe.md): Alter aufsteigend (aeltestes zuerst),
    dann Konfidenz absteigend. Fristen-Prio ist Stufe 2 (Spalte
    prioritaet_frist existiert seit Migration 46).
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT i.id, i.sha256, i.klasse, i.klasse_quelle, i.konfidenz, "
            "       i.queue_status, i.prioritaet_frist, i.erstellt_am, "
            "       i.fehler_detail, i.payload_typ, "
            "       i.ocr_ratio_salat, i.ocr_quote_woerter, i.llm_degradiert, "
            "       json_extract(i.parse_json, '$.akten_kandidaten[0]') "
            "         AS akte_kandidat_top_json, "
            "       json_extract(i.parse_json, '$.bildseiten_anzahl') "
            "         AS bildseiten_anzahl, "
            "       z.id AS zustellung_id, "
            "       z.parent_id AS parent_zustellung_id, "
            "       z.absender AS absender, "
            "       z.betreff AS betreff "
            "FROM intake_dokumente i "
            "LEFT JOIN (SELECT intake_dokument_id, MIN(id) AS min_id "
            "           FROM zustellungen GROUP BY intake_dokument_id) ze "
            "  ON ze.intake_dokument_id = i.id "
            "LEFT JOIN zustellungen z ON z.id = ze.min_id "
            "WHERE i.queue_status IN ('bereit_zur_review','pipeline_fehler') "
            "  AND i.verworfen_am IS NULL "
            "ORDER BY i.erstellt_am ASC, "
            "         COALESCE(i.konfidenz, 0) DESC, i.id ASC"
        ).fetchall()

    eintraege = []
    for r in rows:
        top_json = r["akte_kandidat_top_json"]
        top = json.loads(top_json) if top_json else None
        eintraege.append({
            "id": r["id"],
            "sha256": r["sha256"],
            "klasse": r["klasse"],
            "klasse_quelle": r["klasse_quelle"],
            "konfidenz": r["konfidenz"],
            "queue_status": r["queue_status"],
            "prioritaet_frist": r["prioritaet_frist"],
            "erstellt_am": r["erstellt_am"],
            "fehler_detail": r["fehler_detail"],
            "akte_kandidat_top": top,
            "payload_typ": r["payload_typ"],
            "ocr_ratio_salat": r["ocr_ratio_salat"],
            "ocr_quote_woerter": r["ocr_quote_woerter"],
            "llm_degradiert": r["llm_degradiert"],
            "bildseiten_anzahl": r["bildseiten_anzahl"] or 0,
            "zustellung_id": r["zustellung_id"],
            "parent_zustellung_id": r["parent_zustellung_id"],
            "absender": r["absender"],
            "betreff": r["betreff"],
        })
    return _j({"eintraege": eintraege})


# ─── GET /intake/dokument/<id> ────────────────────────────────────────────────

def _lade_eltern_email(conn, intake_id: int) -> Optional[Dict[str, Any]]:
    """Voller E-Mail-Kontext eines Anhangs: ueber zustellung.parent_id die
    Body-Zustellung finden und aus deren intake_dokument Text + AZ ziehen."""
    kind = conn.execute(
        "SELECT parent_id FROM zustellungen "
        "WHERE intake_dokument_id=? AND parent_id IS NOT NULL "
        "ORDER BY id ASC LIMIT 1", (intake_id,)
    ).fetchone()
    if not kind:
        return None
    parent = conn.execute(
        "SELECT z.intake_dokument_id AS iid, z.absender, z.betreff, "
        "       z.empfangen_am, i.parse_json "
        "FROM zustellungen z JOIN intake_dokumente i "
        "  ON i.id = z.intake_dokument_id "
        "WHERE z.id=?", (kind["parent_id"],)
    ).fetchone()
    if not parent:
        return None
    parse = _parse(parent["parse_json"])
    kand = parse.get("akten_kandidaten") or []
    return {
        "intake_id": parent["iid"],
        "absender": parent["absender"],
        "betreff": parent["betreff"],
        "empfangen_am": parent["empfangen_am"],
        "text": parse.get("text_gesamt", ""),
        "akte_az": kand[0]["akte_az"] if kand else None,
    }


@intake_bp.route("/dokument/<int:intake_id>", methods=["GET"])
@login_erforderlich
def hole_detail(intake_id: int):
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    parse = _parse(dok.get("parse_json"))

    with get_connection() as conn:
        # N-08: erstes Oeffnen in der Queue als Baseline-Start festhalten.
        # Nur setzen, wenn noch NULL und das Dokument in der Queue steht --
        # erneutes Anschauen aendert den Zeitstempel nicht (erstes gewinnt).
        conn.execute(
            "UPDATE intake_dokumente "
            "SET review_geoeffnet_am=datetime('now','localtime') "
            "WHERE id=? AND review_geoeffnet_am IS NULL "
            "  AND queue_status IN ('bereit_zur_review','pipeline_fehler')",
            (intake_id,),
        )
        zust = conn.execute(
            "SELECT id, quelle, absender, auth_status, betreff, "
            "       empfangen_am, konto, roh_referenz, erstellt_am "
            "FROM zustellungen WHERE intake_dokument_id=? "
            "ORDER BY id ASC",
            (intake_id,),
        ).fetchall()
        frg = conn.execute(
            "SELECT id, akte_az, dokument_id, freigegeben_von, freigegeben_am "
            "FROM freigaben WHERE intake_dokument_id=? "
            "ORDER BY id ASC",
            (intake_id,),
        ).fetchall()
        eltern_email = _lade_eltern_email(conn, intake_id)

    return _j({
        "id": dok["id"],
        "sha256": dok["sha256"],
        "payload_typ": dok.get("payload_typ"),
        "ist_fragebogen": parse_fragebogen_payload(dok.get("structured_payload")) is not None,
        "original_pfad": dok.get("original_pfad"),
        "arbeitskopie_pfad": dok.get("arbeitskopie_pfad"),
        "eltern_email": eltern_email,
        "klasse": dok.get("klasse"),
        "bezeichnung": dok.get("bezeichnung"),
        "bezeichnung_vorschlag": _bezeichnung_vorschlag(dok),
        "default_ereignistyp": _default_ereignistyp(dok.get("klasse")),
        "klasse_quelle": dok.get("klasse_quelle"),
        "konfidenz": dok.get("konfidenz"),
        "queue_status": dok.get("queue_status"),
        "textquelle": dok.get("textquelle"),
        "ocr_ratio_salat": dok.get("ocr_ratio_salat"),
        "ocr_quote_woerter": dok.get("ocr_quote_woerter"),
        "registry_version": dok.get("registry_version"),
        "llm_stack": dok.get("llm_stack"),
        "prioritaet_frist": dok.get("prioritaet_frist"),
        "fehler_detail": dok.get("fehler_detail"),
        "erstellt_am": dok.get("erstellt_am"),
        "parse": {
            "text_gesamt": parse.get("text_gesamt", ""),
            "seiten": parse.get("seiten", []),
            "klassifikation": parse.get("klassifikation", {}),
            "felder": parse.get("felder", {}),
            "akten_kandidaten": parse.get("akten_kandidaten", []),
            "llm_konflikt": parse.get("llm_konflikt"),
            "degradation": parse.get("degradation"),
            "bildseiten_anzahl": parse.get("bildseiten_anzahl", 0),
        },
        "zustellungen": [dict(z) for z in zust],
        "freigaben": [dict(f) for f in frg],
    })


@intake_bp.route("/dokument/<int:intake_id>/fragebogen-vorschau", methods=["GET"])
@login_erforderlich
def fragebogen_vorschau(intake_id: int):
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    akte_az = (request.args.get("akte_az") or "").strip()
    if not akte_az:
        return _err("Feld 'akte_az' fehlt", 422)
    parsed = parse_fragebogen_payload(dok.get("structured_payload"))
    if parsed is None:
        return _err("Dokument ist kein Fragebogen", 422)
    return _j({"akte_az": akte_az, "abschnitte": vorschau_liste(akte_az, parsed)})


# ─── GET /intake/dokument/<id>/pdf ────────────────────────────────────────────

@intake_bp.route("/dokument/<int:intake_id>/pdf", methods=["GET"])
@login_erforderlich
def hole_pdf(intake_id: int):
    """Liefert die Arbeitskopie fuer das iframe im Review-UI.

    Auth per Bearer-Header ODER ``?token=`` (SSE-Fallback der Middleware --
    das iframe-Element kann keinen Authorization-Header setzen).
    """
    import os
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    pfad = dok.get("arbeitskopie_pfad")
    if not pfad or not os.path.isfile(pfad):
        return _err("Arbeitskopie fehlt", 404)
    return send_file(pfad, mimetype="application/pdf")


# ─── PATCH /intake/dokument/<id>/klasse ───────────────────────────────────────

@intake_bp.route("/dokument/<int:intake_id>/klasse", methods=["PATCH"])
@login_erforderlich
def patch_klasse(intake_id: int):
    """Manuelle Reklassifikation -> re-enqueue mit korrektem Registry-Eintrag.

    Der Worker parst die Felder beim naechsten Tick mit dem neuen
    Klassen-Schema. klasse_quelle wird auf 'manuell' gesetzt.
    """
    payload = request.get_json(silent=True) or {}
    neue_klasse = (payload.get("klasse") or "").strip()
    if not neue_klasse:
        return _err("Feld 'klasse' fehlt oder ist leer", 400)

    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    alte_klasse = dok.get("klasse")
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente SET "
            "klasse=?, klasse_quelle='manuell' WHERE id=?",
            (neue_klasse, intake_id),
        )
        _log_korrektur(
            conn, intake_id, feld="klasse",
            wert_alt=alte_klasse, wert_neu=neue_klasse,
            klasse=neue_klasse,
            registry_version=dok.get("registry_version"),
            benutzer_id=getattr(g, "benutzer_id", None),
        )

    enqueue(intake_id)
    logger.info("Intake %s reklassifiziert: %r -> %r (manuell)",
                intake_id, alte_klasse, neue_klasse)
    return _j({"ok": True, "klasse": neue_klasse, "queue_status": "neu"})


# ─── POST /intake/dokument/<id>/reparse ───────────────────────────────────────

@intake_bp.route("/dokument/<int:intake_id>/reparse", methods=["POST"])
@login_erforderlich
def post_reparse(intake_id: int):
    """Erzwingt ein Re-Parsen: queue_status='neu' -> Worker greift beim
    naechsten Tick (max. 10s) und laeuft die Klassifikator-Kaskade sowie
    Feld-Extraktion gegen die aktuell gespeicherte klasse erneut durch.

    Kein Zwang, dass die Klasse sich vorher geaendert hat -- der Benutzer
    kann so LLM-Runs erneut anstossen, wenn er das erste Ergebnis fuer
    unplausibel haelt oder nach einer Feld-Korrektur eine Neubewertung
    will.
    """
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    enqueue(intake_id)
    logger.info("Intake %s manuell in Queue zurueckgestellt (reparse).",
                 intake_id)
    return _j({"ok": True, "queue_status": "neu"})


# ─── POST /intake/dokument/<id>/verwerfen ─────────────────────────────────────

_VERWERFEN_GRUENDE = {"spam", "duplikat", "nicht_relevant",
                       "falsche_kanzlei", "sonstiges", "aufgeteilt"}


@intake_bp.route("/dokument/<int:intake_id>/verwerfen", methods=["POST"])
@login_erforderlich
def post_verwerfen(intake_id: int):
    """Dokument aus der Review-Queue entfernen (Soft-Delete).

    Setzt verworfen_grund/am/von auf der intake_dokumente-Zeile
    (Migration 53). ``queue_status`` bleibt unangetastet -- der Wert
    'verworfen' ist im CHECK-Constraint auf queue_status historisch nicht
    vorgesehen, ein Table-Rebuild waere unverhaeltnismaessig. Verworfene
    Zeilen werden ueber ``verworfen_am IS NOT NULL`` aus der Queue
    ausgeblendet (siehe hole_queue).

    PDF-Datei bleibt am Filesystem, Zeile bleibt in der DB. Nur
    bereit_zur_review + pipeline_fehler + neu duerfen verworfen werden
    -- bereits freigegebene Dokumente sind tabu (die haben schon eine
    Akten-Wirkung).

    Payload:
      { "grund": "spam"|"duplikat"|"nicht_relevant"|"falsche_kanzlei"|
                 "sonstiges" (Pflicht),
        "kommentar": str (optional, Freitext) }
    """
    payload = request.get_json(silent=True) or {}
    grund = (payload.get("grund") or "").strip()
    if grund not in _VERWERFEN_GRUENDE:
        return _err(
            f"Feld 'grund' fehlt oder ungueltig. Erlaubt: "
            f"{sorted(_VERWERFEN_GRUENDE)}", 400,
        )
    kommentar = (payload.get("kommentar") or "").strip() or None

    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    if dok.get("verworfen_am"):
        return _err("Dokument ist bereits verworfen.", 409)

    status = dok.get("queue_status")
    if status not in ("bereit_zur_review", "pipeline_fehler", "neu"):
        return _err(
            f"Dokument im Status {status!r} kann nicht mehr verworfen "
            f"werden (Freigabe oder laufender Worker).", 409,
        )

    benutzer_id = getattr(g, "benutzer_id", None)
    from datetime import datetime, timezone
    jetzt = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_dokumente "
            "SET verworfen_grund=?, verworfen_am=?, verworfen_von=? "
            "WHERE id=?",
            (grund, jetzt, benutzer_id, intake_id),
        )
        _log_korrektur(
            conn, intake_id, feld="verworfen",
            wert_alt=status,
            wert_neu={"grund": grund, "kommentar": kommentar},
            klasse=dok.get("klasse"),
            registry_version=dok.get("registry_version"),
            benutzer_id=benutzer_id,
        )

    logger.info("Intake %s verworfen: grund=%s benutzer=%s",
                 intake_id, grund, benutzer_id)
    return _j({"ok": True, "verworfen": True,
                "verworfen_grund": grund, "verworfen_am": jetzt})


# ─── GET /intake/ereignistypen ────────────────────────────────────────────────

@intake_bp.route("/ereignistypen", methods=["GET"])
@login_erforderlich
def hole_ereignistypen():
    """Liefert die Ereignistypen aus der Positionsmodell-Registry fuer
    den Freigabe-Dialog. Kein Filter serverseitig -- das Frontend
    filtert nach richtung='eingehend' als Default.

    Response:
      { "ereignistypen": [
          {"typ": "gutachten_eingegangen",
           "label": "Gutachten eingegangen",
           "richtung": "eingehend",
           "default_wirkung": "gefordert"},
          ...],
        "wirkungen": ["gefordert", "anerkannt", ...] }
    """
    from ..services.positionsmodell_registry import lade_positionsmodell
    from ..services.ereignis_service import _WIRKUNGEN
    reg = lade_positionsmodell()
    liste = [
        {
            "typ": typ,
            "label": spec.get("label") or typ,
            "richtung": spec["richtung"],
            "default_wirkung": spec["default_wirkung"],
        }
        for typ, spec in sorted(reg.ereignistypen.items())
    ]
    return _j({
        "ereignistypen": liste,
        "wirkungen": sorted(_WIRKUNGEN),
    })


# ─── GET /intake/klassen ──────────────────────────────────────────────────────

@intake_bp.route("/klassen", methods=["GET"])
@login_erforderlich
def hole_klassen():
    """Liefert die Dokumentklassen aus der Intake-Registry fuer das
    Reklassifikations-Dropdown, damit das Frontend die Klassenliste nicht
    hartcodieren muss (eine neue klassen/*.yaml erscheint automatisch).

    Response: { "klassen": ["abrechnungsschreiben", "gutachten", ...] }
    """
    from ..intake.registry_loader import lade_registry, standard_pfad
    reg = lade_registry(standard_pfad())
    return _j({"klassen": sorted(reg.klassen.keys())})


# ─── PATCH /intake/dokument/<id>/felder ───────────────────────────────────────

@intake_bp.route("/dokument/<int:intake_id>/felder", methods=["PATCH"])
@login_erforderlich
def patch_felder(intake_id: int):
    """Feld-Korrektur -> korrektur_log + parse_json.felder aktualisieren.

    Erwartet Payload ``{felder: {feldname: {alt, neu}}}``. Kein Re-Parse.
    """
    payload = request.get_json(silent=True) or {}
    felder_delta = payload.get("felder") or {}
    if not isinstance(felder_delta, dict) or not felder_delta:
        return _err("Feld 'felder' fehlt oder ist leer", 400)

    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    parse = _parse(dok.get("parse_json"))
    felder = parse.get("felder") or {}
    if not isinstance(felder, dict):
        felder = {}

    with get_connection() as conn:
        for feld, wert in felder_delta.items():
            if not isinstance(wert, dict):
                continue
            alt = wert.get("alt")
            neu = wert.get("neu")
            felder[feld] = neu
            _log_korrektur(
                conn, intake_id, feld=feld, wert_alt=alt, wert_neu=neu,
                klasse=dok.get("klasse"),
                registry_version=dok.get("registry_version"),
                benutzer_id=getattr(g, "benutzer_id", None),
            )
        parse["felder"] = felder
        conn.execute(
            "UPDATE intake_dokumente SET parse_json=? WHERE id=?",
            (json.dumps(parse, ensure_ascii=False), intake_id),
        )

    return _j({"ok": True, "felder": felder})


# ─── POST /intake/dokument/<id>/freigabe ──────────────────────────────────────

def _upload_basis() -> Path:
    default = Path(__file__).resolve().parent.parent / "uploads"
    return Path(os.environ.get("UPLOAD_DIR") or default)


def _sichere_text_arbeitskopie(dok: Dict[str, Any]) -> Optional[str]:
    """Materialisiert den Payload eines Text-Dokuments als Datei-Arbeitskopie.

    output_adapter.schreibe_dokument verlangt eine Datei; Text-Dokumente
    (Fragebogen/E-Mail-Body) haben keine. Gibt den (vorhandenen oder neu
    geschriebenen) Pfad zurueck, oder None, wenn es kein Text-Dokument ist.
    """
    if dok.get("payload_typ") != "text":
        return None
    vorhanden = dok.get("arbeitskopie_pfad")
    if vorhanden and os.path.isfile(vorhanden):
        return vorhanden
    inhalt = dok.get("structured_payload") or ""
    ziel_dir = _upload_basis() / "intake_text"
    ziel_dir.mkdir(parents=True, exist_ok=True)
    pfad = ziel_dir / f"dok_{dok['id']}.txt"
    pfad.write_text(inhalt, encoding="utf-8")
    return str(pfad)


@intake_bp.route("/dokument/<int:intake_id>/freigabe", methods=["POST"])
@login_erforderlich
def post_freigabe(intake_id: int):
    """Freigabe an eine Akte.

    Payload:
      { "akte_az": str (Pflicht),
        "kandidaten_ereignisse": [...] optional (K-2),
        "ersetzt_ids": [...] optional (K-M2b) }

    Erzeugt (a) dokumente-Zeile via output_adapter,
            (b) freigaben-Zeile,
            (c) setzt intake_dokumente.queue_status='freigegeben'.
    Kandidaten-Ereignisse / ersetzt_ids landen als Kontext im korrektur_log
    (Persistierung ins Positionsmodell = P1.5).
    """
    payload = request.get_json(silent=True) or {}
    akte_az = (payload.get("akte_az") or "").strip()
    if not akte_az:
        return _err("Feld 'akte_az' fehlt -- Freigabe ohne Akte nicht erlaubt",
                    422)

    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    # BUG-06: Pendant zum Verwerfen-Guard -- verworfene oder bereits
    # freigegebene Dokumente sind tabu (sonst stille Doppel-Wirkung /
    # doppelte dokumente-Zeilen bei Doppel-Submit).
    if dok.get("verworfen_am"):
        return _err("Dokument ist verworfen und kann nicht freigegeben "
                    "werden.", 409)
    if dok.get("queue_status") == "freigegeben":
        return _err("Dokument ist bereits freigegeben.", 409)

    benutzer_id = getattr(g, "benutzer_id", None)

    with get_connection() as conn:
        akte = conn.execute(
            "SELECT az FROM unfallakte WHERE az=?", (akte_az,)
        ).fetchone()
    if not akte:
        # BUG-08: Akten-Kandidaten stammen auch aus RA-MICRO (tblAkten) und
        # existieren dort, aber noch nicht in SQLite. Statt 404 die Akte
        # on-demand in SQLite anlegen -- gleiches Muster wie beim ersten
        # Oeffnen einer RA-MICRO-Akte (models.akte.erstelle_oder_hole_akte).
        # RA-MICRO bleibt read-only; geschrieben wird nur in SQLite. Der
        # Verwerfen/Freigegeben-Guard (BUG-06) laeuft bewusst DAVOR, damit
        # ein verworfenes Dokument keine Akte anlegt.
        try:
            from ..models.akte import erstelle_oder_hole_akte
            erstelle_oder_hole_akte(akte_az, bearbeiter_id=benutzer_id)
        except Exception as exc:
            logger.error("Freigabe: Akte %r konnte nicht angelegt werden: %s",
                         akte_az, exc)
            return _err(f"Akte {akte_az!r} konnte nicht angelegt werden: {exc}",
                        400)

    text_pfad = _sichere_text_arbeitskopie(dok)
    if text_pfad:
        dok = {**dok, "arbeitskopie_pfad": text_pfad}
    try:
        dokument_id = schreibe_dokument(dok, akte_az,
                                         freigegeben_von=benutzer_id)
    except FileNotFoundError as exc:
        return _err(f"Arbeitskopie fehlt: {exc}", 500)
    except Exception as exc:
        logger.error("Freigabe intake=%s -> Akte %s fehlgeschlagen: %s",
                     intake_id, akte_az, exc, exc_info=True)
        return _err(f"Interner Fehler beim Schreiben: {exc}", 500)

    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO freigaben "
            "(intake_dokument_id, akte_az, dokument_id, freigegeben_von) "
            "VALUES (?, ?, ?, ?)",
            (intake_id, akte_az, dokument_id, benutzer_id),
        )
        freigabe_id = cur.lastrowid
        conn.execute(
            "UPDATE intake_dokumente SET queue_status='freigegeben' "
            "WHERE id=?",
            (intake_id,),
        )
        # K-2: Ereignis-Vorschlaege als Kontext festhalten (P1.5 uebernimmt
        # die Persistierung ins Positionsmodell).
        kandidaten_ereignisse = payload.get("kandidaten_ereignisse")
        if kandidaten_ereignisse:
            _log_korrektur(
                conn, intake_id, feld="kandidaten_ereignisse",
                wert_alt=None, wert_neu=kandidaten_ereignisse,
                klasse=dok.get("klasse"),
                registry_version=dok.get("registry_version"),
                benutzer_id=benutzer_id,
            )
        # K-M2b: positionsscharfe Ersetzung wird von P1.5 durchgezogen.
        ersetzt_ids = payload.get("ersetzt_ids")
        if ersetzt_ids:
            _log_korrektur(
                conn, intake_id, feld="ersetzt_ids",
                wert_alt=None, wert_neu=ersetzt_ids,
                klasse=dok.get("klasse"),
                registry_version=dok.get("registry_version"),
                benutzer_id=benutzer_id,
            )
        # N-08: Bearbeitungsdauer Queue-Oeffnung -> Freigabe als Baseline.
        # Best-Effort: nur wenn ein Oeffnungs-Zeitstempel vorliegt.
        sekunden = _sekunden_seit(dok.get("review_geoeffnet_am"))
        if sekunden is not None:
            _log_korrektur(
                conn, intake_id, feld="sekunden_bis_freigabe",
                wert_alt=dok.get("review_geoeffnet_am"), wert_neu=sekunden,
                klasse=dok.get("klasse"),
                registry_version=dok.get("registry_version"),
                benutzer_id=benutzer_id,
            )

    # P1.5e: Bestaetigte (oder per Registry-Default vorbelegte) Ereignistypen
    # ins Positionsmodell buchen. Positionen nur bei echten Betraegen.
    _schreibe_freigabe_ereignisse(
        dok=dok, akte_az=akte_az, dokument_id=dokument_id,
        payload=payload, benutzer_id=benutzer_id,
    )

    # Fragebogen-Feld-Uebernahme (nur wenn Payload-Block vorhanden UND das
    # Dokument tatsaechlich ein Fragebogen ist). Best-Effort: ein Fehler bricht
    # die bereits erfolgte Freigabe nicht ab.
    uebernahme_ergebnis = None
    ueb = payload.get("fragebogen_uebernahme")
    if ueb:
        try:
            parsed = parse_fragebogen_payload(dok.get("structured_payload"))
            if parsed is not None:
                uebernahme_ergebnis = uebernehme(
                    akte_az,
                    ueb.get("werte") or {},
                    ueb.get("abschnitte") or [],
                )
        except Exception as exc:
            logger.error("Freigabe %s: Fragebogen-Uebernahme fehlgeschlagen: %s",
                         intake_id, exc, exc_info=True)
            # Shape-Parität zum uebernehme()-Normalfall: fehler ist immer eine
            # Liste von {abschnitt, fehler}; Abschnitt "*" = globaler Fehler.
            uebernahme_ergebnis = {
                "geschrieben": [], "uebersprungen": [],
                "fehler": [{"abschnitt": "*", "fehler": str(exc)}],
            }

    logger.info("Freigabe intake=%s -> Akte %s (dokument_id=%s, freigabe_id=%s)",
                intake_id, akte_az, dokument_id, freigabe_id)
    return _j({
        "ok": True,
        "dokument_id": dokument_id,
        "freigabe_id": freigabe_id,
        "akte_az": akte_az,
        "fragebogen_uebernahme": uebernahme_ergebnis,
    })


def _mandanten_vorsteuer(akte_az: str) -> bool:
    """Vorsteuerabzugsberechtigung des Mandanten der Akte.

    Analog belege_routes.py Z. 518: vorsteuer='J'/'Y'/'1' -> True.
    Default False (Privatmandant), damit die Brutto-Route greift.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT vorsteuer FROM beteiligte "
            "WHERE akte_id=? AND rolle='mandant' LIMIT 1",
            (akte_az,),
        ).fetchone()
    if not row:
        return False
    return str(row["vorsteuer"] or "N").upper() in ("J", "Y", "1")


def _default_ereignistyp(klasse: Optional[str]) -> Optional[str]:
    if not klasse:
        return None
    try:
        from ..services.positionsmodell_registry import lade_positionsmodell
        return lade_positionsmodell().klasse_ereignistyp.get(klasse)
    except Exception:  # pragma: no cover -- Best-Effort
        return None


def _ist_email(dok: Dict[str, Any]) -> bool:
    return (dok.get("payload_typ") == "text"
            or dok.get("textquelle") == "email_text")


def _eingangsdatum(intake_id: int) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT empfangen_am FROM zustellungen "
            "WHERE intake_dokument_id=? ORDER BY id ASC LIMIT 1",
            (intake_id,),
        ).fetchone()
    return row["empfangen_am"] if row else None


def _bezeichnung_vorschlag(dok: Dict[str, Any]) -> str:
    from ..intake.registry_loader import lade_registry, standard_pfad
    felder = _parse(dok.get("parse_json")).get("felder") or {}
    kontext = {
        "ist_email": _ist_email(dok),
        "eingangsdatum": _eingangsdatum(dok["id"]),
    }
    try:
        reg = lade_registry(standard_pfad())
    except Exception:  # pragma: no cover -- Best-Effort
        reg = None
    return baue_bezeichnung(dok.get("klasse"), felder, kontext, reg)


def _bezeichnung_effektiv(dok: Dict[str, Any]) -> str:
    gespeichert = (dok.get("bezeichnung") or "").strip()
    return gespeichert or _bezeichnung_vorschlag(dok)


def _anker_dokument_id(intake_id: Optional[int], dokument_id: int,
                       akte_az: str) -> int:
    """Stabile dokument_id fuer den Doppelerfassungs-Guard.

    schreibe_dokument() legt bei jeder Freigabe eine neue dokumente-Zeile
    an (nicht idempotent) -- bei Re-Freigabe desselben Intake-Dokuments
    waere die dokument_id sonst jedes Mal eine andere und der Guard in
    erzeuge_aus_freigabe (Task 2) wuerde nie greifen. Anker ist daher die
    dokument_id der ERSTEN je fuer dieses Intake-Dokument erfassten
    Freigabe.

    BUG-07: Der Anker muss sich auf die erste Freigabe DERSELBEN Ziel-Akte
    beziehen (``akte_az``-Filter). Sonst zeigt das Ereignis einer zweiten
    Akte auf ein Dokument der ersten (fremden) Akte.
    """
    if not intake_id:
        return dokument_id
    with get_connection() as conn:
        row = conn.execute(
            "SELECT dokument_id FROM freigaben WHERE intake_dokument_id=? "
            "AND akte_az=? ORDER BY id ASC LIMIT 1", (intake_id, akte_az),
        ).fetchone()
    return row["dokument_id"] if row else dokument_id


def _schreibe_freigabe_ereignisse(*, dok, akte_az, dokument_id, payload,
                                   benutzer_id):
    from ..services.eingehende_ereignisse import erzeuge_aus_freigabe

    try:
        klasse = dok.get("klasse") or ""
        felder = _parse(dok.get("parse_json")).get("felder") or {}
        vorsteuer = _mandanten_vorsteuer(akte_az)
        dokument_id = _anker_dokument_id(dok.get("id"), dokument_id, akte_az)

        typen = [e.get("typ") for e in (payload.get("kandidaten_ereignisse") or [])
                 if isinstance(e, dict) and e.get("typ")]
        if not typen:
            default = _default_ereignistyp(klasse)
            typen = [default] if default else []

        from ..services.positionsmodell_registry import lade_positionsmodell
        reg = lade_positionsmodell()
        gueltige = []
        for typ in typen:
            spec = reg.ereignistypen.get(typ)
            if spec and spec.get("richtung") == "eingehend":
                gueltige.append(typ)
            else:
                logger.warning(
                    "Freigabe-Ereignis %r uebersprungen (kein eingehender "
                    "Ereignistyp) intake=%s", typ, dok.get("id"),
                )
        typen = gueltige

        for typ in typen:
            try:
                erzeuge_aus_freigabe(
                    akte_az=akte_az, dokument_id=dokument_id, ereignistyp=typ,
                    klasse=klasse, felder=felder, vorsteuer=vorsteuer,
                    benutzer_id=benutzer_id,
                )
            except Exception as exc:  # pragma: no cover -- Best-Effort
                logger.warning(
                    "Freigabe-Ereignis %s fehlgeschlagen (intake=%s, akte=%s): %s",
                    typ, dok.get("id"), akte_az, exc,
                )
    except Exception as exc:  # pragma: no cover -- Best-Effort
        logger.warning(
            "Freigabe-Ereignisphase fehlgeschlagen (intake=%s, akte=%s): %s",
            dok.get("id"), akte_az, exc,
        )


# ─── PDF-Splitting (Aufteilen mehrseitiger Sammel-PDFs) ────────────────────

@intake_bp.route("/dokument/<int:intake_id>/split", methods=["POST"])
@login_erforderlich
def post_split(intake_id: int):
    """Teilt ein Sammel-PDF entlang Seitengrenzen in mehrere Intake-Dokumente.

    Payload: { "gruppen": [[1,2,3],[4,5]] }  (1-basierte, zusammenhaengende
    Seitenlisten, die 1..N lueckenlos abdecken).
    """
    payload = request.get_json(silent=True) or {}
    gruppen = payload.get("gruppen")
    if (not isinstance(gruppen, list) or not gruppen or not all(
            isinstance(g_, list) and g_ and all(isinstance(p, int) for p in g_)
            for g_ in gruppen)):
        return _err("Feld 'gruppen' muss eine Liste nicht-leerer Seitenlisten "
                    "(Ganzzahlen) sein.", 422)
    try:
        teile = split_service.teile_dokument(
            intake_id, gruppen, getattr(g, "benutzer_id", None))
    except split_service.SplitFehler as e:
        return _err(str(e), e.status)
    logger.info("Intake %s aufgeteilt in %s", intake_id, teile)
    return _j({"ok": True, "teile": teile})


@intake_bp.route("/dokument/<int:intake_id>/seiten", methods=["GET"])
@login_erforderlich
def hole_seitenzahl(intake_id: int):
    """Echte PDF-Seitenzahl (fuer den Aufteilen-Dialog, nicht die 30er-Kappung)."""
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    if dok.get("payload_typ") != "datei":
        return _err("Nur Datei-Dokumente haben Seiten", 422)
    pfad = dok.get("arbeitskopie_pfad")
    if not pfad or not os.path.isfile(pfad):
        return _err("Arbeitskopie fehlt", 404)
    with open(pfad, "rb") as f:
        return _j({"seiten": split_service.pdf_seiten_zahl(f.read())})


@intake_bp.route("/dokument/<int:intake_id>/seite/<int:seite_nr>/thumbnail",
                 methods=["GET"])
@login_erforderlich
def hole_thumbnail(intake_id: int, seite_nr: int):
    """PNG-Miniatur einer Seite fuer den Aufteilen-Dialog (Auth per ?token=)."""
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)
    if dok.get("payload_typ") != "datei":
        return _err("Nur Datei-Dokumente haben Seiten", 422)
    pfad = dok.get("arbeitskopie_pfad")
    if not pfad or not os.path.isfile(pfad):
        return _err("Arbeitskopie fehlt", 404)
    with open(pfad, "rb") as f:
        pdf_bytes = f.read()
    if seite_nr < 1 or seite_nr > split_service.pdf_seiten_zahl(pdf_bytes):
        return _err("Seite ausserhalb des Bereichs", 404)
    return Response(split_service.rendere_thumbnail(pdf_bytes, seite_nr),
                    mimetype="image/png")
