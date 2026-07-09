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
  PATCH /intake/dokument/<id>/felder        Feld-Korrektur
  POST  /intake/dokument/<id>/freigabe      einzige Schreib-Op Richtung Akte

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
from typing import Any, Dict, Optional

from flask import Blueprint, g, jsonify, request, send_file

from ..auth.middleware import login_erforderlich
from ..db.database import get_connection
from ..intake.queue import enqueue
from ..ramicro.output_adapter import schreibe_dokument

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
            "SELECT id, sha256, klasse, klasse_quelle, konfidenz, "
            "       queue_status, prioritaet_frist, erstellt_am, "
            "       fehler_detail, parse_json "
            "FROM intake_dokumente "
            "WHERE queue_status IN ('bereit_zur_review','pipeline_fehler') "
            "ORDER BY erstellt_am ASC, id ASC, "
            "         COALESCE(konfidenz, 0) DESC"
        ).fetchall()

    eintraege = []
    for r in rows:
        parse = _parse(r["parse_json"])
        kandidaten = parse.get("akten_kandidaten") or []
        top = kandidaten[0] if kandidaten else None
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
        })
    return _j({"eintraege": eintraege})


# ─── GET /intake/dokument/<id> ────────────────────────────────────────────────

@intake_bp.route("/dokument/<int:intake_id>", methods=["GET"])
@login_erforderlich
def hole_detail(intake_id: int):
    dok = _lade_intake(intake_id)
    if not dok:
        return _err("Intake-Dokument nicht gefunden", 404)

    parse = _parse(dok.get("parse_json"))

    with get_connection() as conn:
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

    return _j({
        "id": dok["id"],
        "sha256": dok["sha256"],
        "original_pfad": dok.get("original_pfad"),
        "arbeitskopie_pfad": dok.get("arbeitskopie_pfad"),
        "klasse": dok.get("klasse"),
        "klasse_quelle": dok.get("klasse_quelle"),
        "konfidenz": dok.get("konfidenz"),
        "queue_status": dok.get("queue_status"),
        "textquelle": dok.get("textquelle"),
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
        },
        "zustellungen": [dict(z) for z in zust],
        "freigaben": [dict(f) for f in frg],
    })


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

    with get_connection() as conn:
        akte = conn.execute(
            "SELECT az FROM unfallakte WHERE az=?", (akte_az,)
        ).fetchone()
    if not akte:
        return _err(f"Akte {akte_az!r} nicht gefunden", 404)

    benutzer_id = getattr(g, "benutzer_id", None)

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

    # Option A: Gutachten-Freigabe schreibt gutachten_eingegangen mit den
    # extrahierten Positionen -- inklusive sv_kosten (DEKRA-Gutachten
    # enthalten die SV-Rechnung im selben PDF, POSITIONSMODELL 5.2).
    # Andere Klassen bleiben Alt-Pfad-getrieben (P1.5e kommt separat).
    if (dok.get("klasse") or "").lower() == "gutachten":
        try:
            _schreibe_gutachten_ereignis(
                akte_az=akte_az, dokument_id=dokument_id,
                parse_json=dok.get("parse_json"),
                benutzer_id=benutzer_id,
            )
        except Exception as exc:  # pragma: no cover -- Best-Effort
            logger.warning(
                "gutachten_eingegangen aus Freigabe fehlgeschlagen "
                "(intake=%s, akte=%s): %s", intake_id, akte_az, exc,
            )

    logger.info("Freigabe intake=%s -> Akte %s (dokument_id=%s, freigabe_id=%s)",
                intake_id, akte_az, dokument_id, freigabe_id)
    return _j({
        "ok": True,
        "dokument_id": dokument_id,
        "freigabe_id": freigabe_id,
        "akte_az": akte_az,
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


def _feld_zu_zahl(wert):
    """'1.011,50' -> 1011.5 ; 850 -> 850.0 ; None -> None."""
    if wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    s = str(wert).strip()
    if not s:
        return None
    # Deutsche Notation: Punkt = Tausender, Komma = Dezimal
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _schreibe_gutachten_ereignis(*, akte_az, dokument_id, parse_json,
                                  benutzer_id):
    """Leitet Positionen aus den extrahierten Feldern ab und ruft
    ``erzeuge_aus_gutachten``. sv_kosten mit brutto (Privat) oder netto
    (Vorsteuerabzug) je nach Mandanten-Flag."""
    from ..services.eingehende_ereignisse import erzeuge_aus_gutachten

    parse = _parse(parse_json)
    felder = parse.get("felder") or {}
    if not isinstance(felder, dict):
        return

    # Direkte Positions-Felder + Aliase (netto/brutto -> Position-Key)
    reparatur = (_feld_zu_zahl(felder.get("reparaturkosten"))
                 or _feld_zu_zahl(felder.get("reparaturkosten_netto"))
                 or _feld_zu_zahl(felder.get("reparaturkosten_brutto")))
    wbw = (_feld_zu_zahl(felder.get("wiederbeschaffung"))
           or _feld_zu_zahl(felder.get("wiederbeschaffungswert")))
    restwert = (_feld_zu_zahl(felder.get("restwert"))
                or _feld_zu_zahl(felder.get("restwert_netto"))
                or _feld_zu_zahl(felder.get("restwert_brutto")))
    wm = _feld_zu_zahl(felder.get("wertminderung"))

    positionen: Dict[str, Any] = {}
    if reparatur:
        positionen["reparaturkosten"] = reparatur
    if wbw:
        positionen["wiederbeschaffung"] = wbw
    if restwert:
        positionen["restwert"] = restwert
    if wm:
        positionen["wertminderung"] = wm

    # sv_kosten: Vorsteuer-Weiche (analog belege_routes.py Z. 619-627).
    sv_netto = _feld_zu_zahl(felder.get("sv_kosten_netto"))
    sv_brutto = _feld_zu_zahl(felder.get("sv_kosten_brutto"))
    if sv_netto or sv_brutto:
        if _mandanten_vorsteuer(akte_az):
            wert = sv_netto if sv_netto is not None else sv_brutto
        else:
            wert = sv_brutto if sv_brutto is not None else sv_netto
        if wert:
            positionen["sv_kosten"] = wert

    if not positionen:
        return

    erzeuge_aus_gutachten(
        akte_az=akte_az,
        dokument_id=dokument_id,
        positionen=positionen,
        benutzer_id=benutzer_id,
    )
