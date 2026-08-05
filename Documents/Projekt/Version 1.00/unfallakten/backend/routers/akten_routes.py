"""
Modul 3 – Router: Akten
========================
REST-Endpunkte für Unfallakten-Verwaltung.

Endpunkte:
  GET    /akten                  Alle Akten (gefiltert, paginiert)
  POST   /akten                  Neue Akte anlegen
  GET    /akten/<id>             Akte mit allen Details abrufen
  PATCH  /akten/<id>             Akte aktualisieren (Status, Notizen, etc.)
  DELETE /akten/<id>             Akte löschen (nur Admin)
  GET    /akten/<id>/aktivitaeten Aktivitätsfeed einer Akte
  GET    /akten/statistik        Dashboard-Statistiken

Alle Endpunkte erfordern Login (@login_erforderlich).
DELETE erfordert Admin-Rolle (@nur_admin).
"""

import logging
import re
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich, nur_admin
from ..db.database import get_connection
from ..models.beteiligte import beteiligter_as_dict as _beteiligter_dict
from ..models.akte import (
    erstelle_akte, erstelle_oder_hole_akte, hole_akte_by_id, hole_akte_by_aktenzeichen,
    liste_akten, aktualisiere_akte, loesche_akte, zaehle_akten_by_status
)
from ..models.schaden import (
    hole_beteiligte_by_akte, hole_schadenpositionen,
    hole_regulierungsstatus
)
from ..models.dokument import hole_aktivitaeten, hole_dokumente_by_akte, logge_aktivitaet
from ..services.fristen_service import setze_verjaerungs_fristen
from ..services.portal_sync import _portal_flag

logger = logging.getLogger(__name__)
akten_bp = Blueprint("akten", __name__, url_prefix="/akten")

GUELTIGE_REG_STATUS = frozenset({"offen", "abgelehnt", "teilhaftung"})


def _j(daten, status=200):
    return jsonify(daten), status

def _err(msg, status, **extra):
    return jsonify({"fehler": msg, "status": status, **extra}), status

def _body():
    return request.get_json(silent=True) or {}


def _hole_akte_aktion(akte_id: str) -> dict:
    """Gibt den aktiven Aktion-Badge einer Akte aus email_import_log zurück."""
    try:
        from ..db.database import get_connection as _gc
        with _gc() as conn:
            row = conn.execute(
                "SELECT aktion_erforderlich, aktion_typ, aktion_seit "
                "FROM email_import_log "
                "WHERE akte_id = ? AND aktion_erforderlich = 1 "
                "ORDER BY importiert_am DESC LIMIT 1",
                (akte_id,)
            ).fetchone()
        if row and row['aktion_erforderlich']:
            return {
                "aktiv": True,
                "typ":   row['aktion_typ'],
                "seit":  row['aktion_seit'],
            }
    except Exception:
        pass
    return {"aktiv": False, "typ": None, "seit": None}

def _akte_komplett(akte_id: str) -> dict:
    """Gibt eine Akte mit allen verknüpften Daten zurück."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return None

    beteiligte      = hole_beteiligte_by_akte(akte_id)
    schaden         = hole_schadenpositionen(akte_id)
    reg_status      = hole_regulierungsstatus(akte_id)
    dokumente       = hole_dokumente_by_akte(akte_id)

    aktion = _hole_akte_aktion(akte_id)

    # Portal-Felder nachladen (nicht im Unfallakte-Dataclass)
    portal_aktiv = 0
    portal_last_sync = None
    try:
        with get_connection() as conn:
            portal_row = conn.execute(
                "SELECT portal_aktiv, portal_last_sync FROM unfallakte WHERE az = ?",
                (akte.az,)
            ).fetchone()
        if portal_row:
            portal_aktiv = portal_row["portal_aktiv"]
            portal_last_sync = portal_row["portal_last_sync"]
    except Exception:
        pass  # Portal-Felder sind nicht-fatal

    return {
        "id":               akte.az,
        "az":               akte.az,
        "unfalldatum":      akte.unfalldatum,
        "unfallort":        akte.unfallort,
        "status":           akte.status,
        "haftungsquote":    akte.haftungsquote,
        "hq":               akte.haftungsquote,
        "regulierung_status": akte.regulierung_status,
        "bearbeiter_id":    akte.bearbeiter_id,
        "notizen":          akte.notizen,
        "kurzbezeichnung":  akte.kurzbezeichnung,
        "sachbearbeiter":   akte.sachbearbeiter,
        "erstellt_am":      akte.erstellt_am,
        "geaendert_am":     akte.geaendert_am,
        "beteiligte":     [_beteiligter_dict(b) for b in beteiligte],
        "schaden":        _schaden_dict(schaden) if schaden else None,
        "regulierungsstatus": reg_status,
        "dokumente":      [_dokument_dict(d) for d in dokumente],
        "aktion_erforderlich": 1 if aktion.get("aktiv") else 0,
        "aktion_typ":          aktion.get("typ"),
        "aktion_seit":         aktion.get("seit"),
        "portal_aktiv":        portal_aktiv,
        "portal_last_sync":    portal_last_sync,
    }

def _akte_liste_dict(akte) -> dict:
    """Kompakte Darstellung für Listendarstellung (ohne Unterentitäten)."""
    return {
        "id":            akte.az,
        "az":            akte.az,
        "unfalldatum":   akte.unfalldatum,
        "unfallort":     akte.unfallort,
        "status":        akte.status,
        "haftungsquote": akte.haftungsquote,
        "regulierung_status": getattr(akte, "regulierung_status", "offen"),
        "bearbeiter_id": akte.bearbeiter_id,
        "erstellt_am":   akte.erstellt_am,
        "geaendert_am":  akte.geaendert_am,
        "aktion_erforderlich": getattr(akte, "aktion_erforderlich", 0),
        "aktion_typ":          getattr(akte, "aktion_typ", None),
        "aktion_seit":         getattr(akte, "aktion_seit", None),
    }

def _schaden_dict(s) -> dict:
    return {
        "id": s.id, "akte_id": s.akte_id,
        "reparaturkosten": s.reparaturkosten,
        "wiederbeschaffung": s.wiederbeschaffung, "restwert": s.restwert,
        "wertminderung": s.wertminderung, "nutzungsausfall": s.nutzungsausfall,
        "mietwagenkosten": s.mietwagenkosten, "sv_kosten": s.sv_kosten,
        "abschleppkosten": s.abschleppkosten, "standkosten": s.standkosten,
        "anabmeldekosten": s.anabmeldekosten, "schmerzensgeld": s.schmerzensgeld,
        "sonstiges": s.sonstiges, "sonstiges_beschr": s.sonstiges_beschr,
        "gesamt_brutto": s.gesamt_brutto,
        "quelle": s.quelle, "erfasst_am": s.erfasst_am,
    }

def _dokument_dict(d) -> dict:
    return {
        "id": d.id, "akte_id": d.akte_id, "typ": d.typ,
        "dateiname": d.dateiname, "dateityp": d.dateityp,
        "dateigroesse": d.dateigroesse,
        "hochgeladen_am": d.hochgeladen_am,
        "parse_status": d.parse_status,
        "parse_konfidenz": d.parse_konfidenz,
        "dokumentenklasse": getattr(d, "dokumentenklasse", None),
        "bezeichnung":      getattr(d, "bezeichnung", None),
        "eakte_nr":         getattr(d, "eakte_nr", None),
        "eakte_pfad":       getattr(d, "eakte_pfad", None),
        "quelle":           getattr(d, "quelle", "upload"),
    }

# ── Statistik / Dashboard ─────────────────────────────────────────────────────

@akten_bp.route("/statistik", methods=["GET"])
@login_erforderlich
def statistik():
    """
    GET /akten/statistik
    Gibt Übersichtsstatistiken für das Dashboard zurück.

    Response 200:
      {
        "akten_by_status": {"offen": 42, "in_regulierung": 17, ...},
        "gesamt": 100
      }
    """
    stats = zaehle_akten_by_status()
    gesamt = sum(stats.values())
    return _j({
        "akten_by_status": stats,
        "gesamt": gesamt,
    })


# ── Akten Liste & Erstellen ───────────────────────────────────────────────────

@akten_bp.route("", methods=["GET"])
@login_erforderlich
def liste():
    """
    GET /akten
    Gibt alle Akten zurück (kompakte Darstellung, paginiert).

    Query-Parameter:
      status       Filter nach Status (offen/in_regulierung/klage/abgeschlossen)
      bearbeiter   Filter nach Bearbeiter-ID
      suche        Freitext-Suche in Aktenzeichen und Unfallort
      limit        Max. Ergebnisse (Standard: 50, Max: 200)
      offset       Offset für Paginierung

    Response 200:
      { "akten": [...], "gesamt": 100, "limit": 50, "offset": 0 }
    """
    status      = request.args.get("status")
    bearbeiter  = request.args.get("bearbeiter", type=int)
    suche       = request.args.get("suche")
    limit       = min(request.args.get("limit", 50, type=int), 200)
    offset      = request.args.get("offset", 0, type=int)

    # Sachbearbeiter sehen nur ihre eigenen Akten (optional, je nach Kanzlei-Policy)
    # Aktuell: Alle sehen alle Akten (Admin kann bei Bedarf einschränken)

    akten = liste_akten(
        status=status,
        bearbeiter_id=bearbeiter,
        suchbegriff=suche,
        limit=limit,
        offset=offset,
    )

    return _j({
        "akten":  [_akte_liste_dict(a) for a in akten],
        "gesamt": len(akten),
        "limit":  limit,
        "offset": offset,
    })


@akten_bp.route("", methods=["POST"])
@login_erforderlich
def erstelle():
    """
    POST /akten
    Legt eine neue Unfallakte an.

    Body:
      {
        "aktenzeichen": "43/25",
        "unfalldatum":  "2025-03-01",
        "unfallort":    "Offenbach, ...",
        "haftungsquote": 100.0,
        "notizen":      "..."
      }

    Response 201:
      Vollständige Akte mit allen Unterentitäten
    """
    daten = _body()

    az   = daten.get("aktenzeichen", "").strip()
    datum = daten.get("unfalldatum", "").strip()

    if not az:
        return _err("aktenzeichen ist erforderlich.", 422, feld="aktenzeichen")
    # Format-Validierung: ####/YY (mit optionalem Sachbearbeiter-Kürzel, z.B. 42/25AS)
    import re as _re
    if not _re.match(r'^\d+/\d{2}([A-Z]{2})?$', az):
        return _err(
            "Aktenzeichen hat ungültiges Format. Erwartet: ####/YY oder ####/YYSB "
            "(z.B. 42/25 oder 42/25AS).",
            422, feld="aktenzeichen"
        )
    if not datum:
        return _err("unfalldatum ist erforderlich.", 422, feld="unfalldatum")

    try:
        akte = erstelle_akte(
            aktenzeichen=az,
            unfalldatum=datum,
            bearbeiter_id=g.benutzer_id,
            unfallort=daten.get("unfallort"),
            haftungsquote=float(daten.get("haftungsquote", 100.0)),
        )
        if daten.get("notizen"):
            aktualisiere_akte(akte.id, notizen=daten["notizen"])
    except ValueError as e:
        return _err(str(e), 422)

    # Automatische Verjährungsfristen anlegen (PRD-25a)
    try:
        setze_verjaerungs_fristen(az, datum)
    except Exception as e:
        logger.warning("fristen_service: Verjährungsfristen konnten nicht angelegt werden: %s", e)

    return _j(_akte_komplett(akte.id), 201)


# ── Einzelne Akte ─────────────────────────────────────────────────────────────

@akten_bp.route("/<path:akte_id>", methods=["GET"])
@login_erforderlich
def detail(akte_id: str):
    """
    GET /akten/<id>
    Gibt eine Akte mit allen Unterentitäten zurück.

    Response 200: Vollständige Akte
    Response 404: Akte nicht gefunden
    """
    daten = _akte_komplett(akte_id)
    if not daten:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    return _j(daten)


@akten_bp.route("/<path:akte_id>", methods=["PATCH"])
@login_erforderlich
def aktualisiere(akte_id: str):
    """
    PATCH /akten/<id>
    Aktualisiert eine oder mehrere Eigenschaften einer Akte.

    Body (alle Felder optional):
      {
        "status":       "in_regulierung",
        "notizen":      "...",
        "unfallort":    "...",
        "haftungsquote": 75.0,
        "bearbeiter_id": 2,
        "unfalldatum":  "2025-03-01"
      }

    Response 200: Aktualisierte Akte (vollständig)
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    daten = _body()
    erlaubte = {"status", "notizen", "unfallort",
                "haftungsquote", "bearbeiter_id", "unfalldatum",
                "regulierung_status"}
    felder = {k: v for k, v in daten.items() if k in erlaubte}

    # Validierung zuerst
    if "regulierung_status" in felder and felder["regulierung_status"] not in GUELTIGE_REG_STATUS:
        return _err(f"Ungültiger regulierung_status: {felder['regulierung_status']!r}. "
                    f"Erlaubt: {', '.join(sorted(GUELTIGE_REG_STATUS))}", 422)

    # Auto-haftungsquote nur nach erfolgreicher Validierung
    if "regulierung_status" in felder and "haftungsquote" not in felder:
        rs = felder["regulierung_status"]
        if rs == "abgelehnt":
            felder["haftungsquote"] = 0.0
        elif rs == "offen":
            felder["haftungsquote"] = 100.0

    if not felder:
        return _err("Keine aktualisierbaren Felder im Body.", 422)

    try:
        aktualisiere_akte(akte_id, g.benutzer_id, **felder)
    except ValueError as e:
        return _err(str(e), 422)

    # Verjährungsfristen neu setzen wenn unfalldatum geändert (PRD-25a)
    if "unfalldatum" in felder and felder["unfalldatum"]:
        try:
            setze_verjaerungs_fristen(akte_id, felder["unfalldatum"])
        except Exception as e:
            logger.warning("fristen_service: Verjährungsfristen konnten nicht aktualisiert werden: %s", e)

    # Aktivität loggen
    try:
        from ..models.dokument import logge_aktivitaet
        STATUS_LABELS = {"offen":"Offen","in_regulierung":"In Regulierung","klage":"Klage","abgeschlossen":"Abgeschlossen"}
        if "status" in felder:
            logge_aktivitaet("status_geaendert",
                f"Status geändert → {STATUS_LABELS.get(felder['status'], felder['status'])}",
                akte_id=akte_id, benutzer_id=g.benutzer_id)
        elif "notizen" in felder:
            logge_aktivitaet("notizen_geaendert", "Notizen aktualisiert",
                akte_id=akte_id, benutzer_id=g.benutzer_id)
        elif "regulierung_status" in felder:
            logge_aktivitaet("regulierung_status_geaendert",
                f"Regulierungsstatus → {felder['regulierung_status']}",
                akte_id=akte_id, benutzer_id=g.benutzer_id)
        elif "haftungsquote" in felder:
            logge_aktivitaet("haftungsquote_geaendert",
                f"Haftungsquote geändert → {felder['haftungsquote']} %",
                akte_id=akte_id, benutzer_id=g.benutzer_id)
    except Exception:
        pass  # Logging nicht-fatal

    # Portal-Sync Flagge setzen wenn Status geändert
    if "status" in felder:
        try:
            from ..db.database import get_connection
            with get_connection() as conn:
                _portal_flag(conn, akte_id)
        except Exception as exc:
            logger.warning("portal_flag fehlgeschlagen (Akte %s): %s", akte_id, exc)

    return _j(_akte_komplett(akte_id))


@akten_bp.route("/<path:akte_id>", methods=["DELETE"])
@nur_admin
def loesche(akte_id: str):
    """
    DELETE /akten/<id>
    Löscht eine Akte inkl. aller verknüpften Daten (CASCADE).
    Nur für Admins.

    Response 200: { "nachricht": "Akte gelöscht." }
    Response 404: Akte nicht gefunden
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    loesche_akte(akte_id)
    return _j({"nachricht": f"Akte {akte_id} wurde gelöscht."})


# ── Aktivitätsfeed ────────────────────────────────────────────────────────────

@akten_bp.route("/<path:akte_id>/aktivitaeten", methods=["GET"])
@login_erforderlich
def aktivitaeten(akte_id: str):
    """
    GET /akten/<id>/aktivitaeten
    Gibt den Aktivitätsfeed einer Akte zurück.

    Query-Parameter:
      limit  Max. Einträge (Standard: 50)

    Response 200:
      { "aktivitaeten": [...] }
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    limit = request.args.get("limit", 50, type=int)
    acts = hole_aktivitaeten(akte_id, limit=limit)

    return _j({
        "aktivitaeten": [
            {
                "id":          a.id,
                "akte_id":     a.akte_id,
                "benutzer_id": a.benutzer_id,
                "zeitstempel": a.zeitstempel,
                "aktion":      a.aktion,
                "beschreibung": a.beschreibung,
            }
            for a in acts
        ]
    })


@akten_bp.route("/<path:akte_id>/aktivitaeten/<int:aktivitaet_id>", methods=["DELETE"])
@login_erforderlich
def aktivitaet_loeschen(akte_id: str, aktivitaet_id: int):
    """
    DELETE /akten/<id>/aktivitaeten/<aktivitaet_id>
    Löscht einen einzelnen Aktivitätseintrag aus der DB.
    Response 200: { "ok": true }
    """
    if not hole_akte_by_id(akte_id):
        return _err(f"Akte {akte_id} nicht gefunden.", 404)

    from ..db.database import get_connection
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM aktivitaeten WHERE id = ? AND akte_id = ?",
            (aktivitaet_id, akte_id)
        )
        if result.rowcount == 0:
            return _err("Aktivitätseintrag nicht gefunden.", 404)

    return _j({"ok": True})


# ── Abschluss-/Sachstandsbericht ─────────────────────────────────────────────

_SCHLUSS_TYPEN = {"offen", "endgueltig", "vorbehalt_spaetfolgen", "restposten"}


@akten_bp.route("/<path:akte_id>/abschluss-uebersicht", methods=["GET"])
@login_erforderlich
def abschluss_uebersicht(akte_id: str):
    """
    GET /akten/<az>/abschluss-uebersicht
    Kanzlei-internes Übersichts-Objekt (Vorschau im Kurationsdialog).
    Read-only; Spec docs/superpowers/specs/2026-08-05-abschlussbericht-design.md §7.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    from ..word.word_service import _lade_akte_daten
    from ..services.abschluss_uebersicht import baue_abschluss_uebersicht
    daten = _lade_akte_daten(akte_id, akte, dok_typ="abschlussbericht")
    return _j(baue_abschluss_uebersicht(daten))


@akten_bp.route("/<path:akte_id>/abschluss-status", methods=["PUT"])
@login_erforderlich
def abschluss_status_speichern(akte_id: str):
    """
    PUT /akten/<az>/abschluss-status
    Body: { schluss_typ, schluss_text?, verjaehrung_datum?,
            naechste_schritte_text? }
    Upsert des kuratierten Schlussfelds (Migration 67).
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte {akte_id} nicht gefunden.", 404)
    az = akte.az

    data = request.get_json(silent=True) or {}
    schluss_typ = (data.get("schluss_typ") or "offen").strip()
    if schluss_typ not in _SCHLUSS_TYPEN:
        return _err(
            f"Ungültiger schluss_typ '{schluss_typ}'. "
            f"Erlaubt: {', '.join(sorted(_SCHLUSS_TYPEN))}", 422)

    from ..db.database import get_connection
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO abschluss_status
                (akte_az, schluss_typ, schluss_text, verjaehrung_datum,
                 naechste_schritte_text, kuratiert_am, kuratiert_von)
            VALUES (?, ?, ?, ?, ?, datetime('now','localtime'), ?)
            ON CONFLICT(akte_az) DO UPDATE SET
                schluss_typ            = excluded.schluss_typ,
                schluss_text           = excluded.schluss_text,
                verjaehrung_datum      = excluded.verjaehrung_datum,
                naechste_schritte_text = excluded.naechste_schritte_text,
                kuratiert_am           = excluded.kuratiert_am,
                kuratiert_von          = excluded.kuratiert_von
        """, (az, schluss_typ,
              (data.get("schluss_text") or "").strip() or None,
              (data.get("verjaehrung_datum") or "").strip() or None,
              (data.get("naechste_schritte_text") or "").strip() or None,
              str(getattr(g, "benutzer_id", "") or "")))
        row = conn.execute(
            "SELECT * FROM abschluss_status WHERE akte_az = ?", (az,)
        ).fetchone()

    try:
        logge_aktivitaet(
            "abschluss_status_kuratiert",
            f"Abschluss-Status gesetzt: {schluss_typ}",
            akte_id=az, benutzer_id=getattr(g, "benutzer_id", None))
    except Exception:
        pass

    return _j({"status": "ok", "abschluss_status": dict(row)})


@akten_bp.route("/<path:akte_id>/pwa-nachricht", methods=["POST"])
@login_erforderlich
def pwa_nachricht_senden(akte_id: str):
    """
    POST /akten/<az>/pwa-nachricht
    Body: { "text": str, "vorlage_key": str (optional) }
    Stub: speichert Nachricht als Aktivitätseintrag, sendet keine Push-Notification.
    """
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err("Akte nicht gefunden.", 404)
    az = akte.az

    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    vorlage_key = (data.get("vorlage_key") or "freitext").strip()
    if not text:
        return _err("text erforderlich.", 422)

    benutzer_id = getattr(g, "benutzer_id", None)
    beschreibung = f"[PWA:{vorlage_key}] {text[:500]}"

    eintrag = logge_aktivitaet("pwa_nachricht", beschreibung,
                               akte_id=az, benutzer_id=benutzer_id, tabelle="pwa")

    return jsonify({"ok": True, "aktivitaet_id": eintrag.id})

def _basis_az(az: str) -> str:
    """Streift ein optionales SB-Kuerzel ab ('670/26AS' -> '670/26').

    Gleiche Basis-Logik wie intake_routes._basis_az / akten_matching._az_basis,
    damit der Akte-Vergleich ueber Suffixe/fuehrende Nullen hinweg greift.
    """
    az = (az or "").strip()
    if "/" in az:
        az = re.sub(r"[A-Za-z]{2,3}$", "", az).strip()
    return az


@akten_bp.route("/<path:akte_az>/intake-pending", methods=["GET"])
@login_erforderlich
def intake_pending(akte_az: str):
    ziel = _basis_az(akte_az)
    with get_connection() as conn:
        docs = conn.execute(
            "SELECT i.id, i.klasse, i.queue_status, i.erstellt_am, "
            "       i.bezeichnung, "
            "       json_extract(i.parse_json, '$.akten_kandidaten[0].akte_az') "
            "         AS kandidat_az "
            "FROM intake_dokumente i "
            "WHERE i.queue_status != 'freigegeben' "
            "  AND i.verworfen_am IS NULL "
            "ORDER BY i.erstellt_am ASC, i.id ASC"
        ).fetchall()
        if not docs:
            return _j([])
        ids = [d["id"] for d in docs]
        platzhalter = ",".join("?" * len(ids))
        zust_rows = conn.execute(
            "SELECT intake_dokument_id, "
            "       json_extract(signale_json, '$.az') AS signal_az, "
            "       json_extract(signale_json, '$.dateiname') AS signal_dateiname, "
            "       roh_referenz "
            "FROM zustellungen "
            f"WHERE intake_dokument_id IN ({platzhalter}) "
            "ORDER BY id ASC",
            ids,
        ).fetchall()

    zust_nach_dok = {}
    for z in zust_rows:
        zust_nach_dok.setdefault(z["intake_dokument_id"], []).append(z)

    eintraege = []
    for d in docs:
        az_quellen = set()
        dateiname = None
        for z in zust_nach_dok.get(d["id"], []):
            if z["signal_az"]:
                az_quellen.add(_basis_az(z["signal_az"]))
            roh = z["roh_referenz"] or ""
            if roh.startswith("upload/akte:"):
                az_quellen.add(_basis_az(roh[len("upload/akte:"):]))
            if z["signal_dateiname"] and not dateiname:
                dateiname = z["signal_dateiname"]
        if d["kandidat_az"]:
            az_quellen.add(_basis_az(d["kandidat_az"]))
        if ziel not in az_quellen:
            continue
        bez = (d["bezeichnung"] or dateiname or d["klasse"] or "(unbenannt)")
        eintraege.append({
            "intake_id": d["id"],
            "bezeichnung": bez,
            "klasse": d["klasse"],
            "queue_status": d["queue_status"],
            "erstellt_am": d["erstellt_am"],
        })
    return _j(eintraege)
