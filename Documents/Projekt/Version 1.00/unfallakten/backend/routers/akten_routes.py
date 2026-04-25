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
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich, nur_admin
from ..db.database import get_connection
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
        "bearbeiter_id":    akte.bearbeiter_id,
        "notizen":          akte.notizen,
        "kurzbezeichnung":  akte.kurzbezeichnung,
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
        "bearbeiter_id": akte.bearbeiter_id,
        "erstellt_am":   akte.erstellt_am,
        "geaendert_am":  akte.geaendert_am,
        "aktion_erforderlich": getattr(akte, "aktion_erforderlich", 0),
        "aktion_typ":          getattr(akte, "aktion_typ", None),
        "aktion_seit":         getattr(akte, "aktion_seit", None),
    }

def _beteiligter_dict(b) -> dict:
    return {
        "id": b.id, "akte_id": b.akte_id, "rolle": b.rolle,
        "name": b.name, "vorname": b.vorname, "firma": b.firma,
        "anschrift": b.anschrift, "plz": b.plz, "ort": b.ort,
        "telefon": b.telefon, "email": b.email,
        "kfz_kennzeichen": b.kfz_kennzeichen, "kfz_typ": b.kfz_typ,
        "versicherung": b.versicherung, "vers_nr": b.vers_nr,
        "schaden_nr": b.schaden_nr, "iban": b.iban, "notizen": b.notizen,
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
                "haftungsquote", "bearbeiter_id", "unfalldatum"}
    felder = {k: v for k, v in daten.items() if k in erlaubte}

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

        # aktualisiere_akte() hat bereits committed; zweite Verbindung liest korrekte Daten.
        if felder["status"] == "abgeschlossen":
            _erzeuge_abschluss_summary(akte_id)

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


# ── Hilfsfunktion: Abschluss-Summary ─────────────────────────────────────────

def _erzeuge_abschluss_summary(az):
    import hashlib
    import os
    from ..word.abschluss_summary import generiere_abschluss_summary
    from ..db.database import get_connection as _gc

    try:
        with _gc() as conn:
            docx_bytes = generiere_abschluss_summary(conn, az)
            uploads_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "uploads",
                az.replace("/", "_")
            )
            os.makedirs(uploads_dir, exist_ok=True)
            fname = "abschluss_summary_{}.docx".format(az.replace("/", "_"))
            fpath = os.path.join(uploads_dir, fname)
            with open(fpath, "wb") as fh:
                fh.write(docx_bytes)
            pdf_hash = hashlib.sha256(docx_bytes).hexdigest()
            existing = conn.execute(
                "SELECT id FROM dokumente WHERE akte_id = ? AND pdf_hash = ?", (az, pdf_hash)
            ).fetchone()
            if not existing:
                rel_path = os.path.join(az.replace("/", "_"), fname)
                conn.execute("""
                    INSERT INTO dokumente
                        (akte_id, typ, dateiname, dateipfad, dateityp, dateigroesse,
                         pdf_hash, portal_sichtbar)
                    VALUES (?, 'sonstiges', ?, ?, 'docx', ?, ?, 1)
                """, (az, fname, rel_path, len(docx_bytes), pdf_hash))
            from ..services.portal_sync import _portal_flag
            _portal_flag(conn, az)
    except Exception as exc:
        logger.error("Abschluss-Summary fuer %s fehlgeschlagen: %s", az, exc)
