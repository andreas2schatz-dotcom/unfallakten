"""
PATCH: abrechnungen_routes.py
==============================
Folgende Änderungen / Ergänzungen vornehmen:

1. Im POST (/erstelle): quelle aus Payload übernehmen
2. NEU: PUT  /<akte_id>/abrechnungen/<ab_id>  → Abrechnung bearbeiten
3. NEU: DELETE /<akte_id>/abrechnungen/<ab_id>  → Abrechnung löschen
4. NEU: GET /<akte_id>/abrechnungen/wdm-check   → WDM-Vorschau für Auto-Import
"""

# ──────────────────────────────────────────────────────────────────────────────
# ÄNDERUNG 1: POST-Route – quelle aus Payload übernehmen
# Bestehende Zeile beim INSERT suchen und ergänzen:
#
# ALT (in der INSERT-Anweisung):
#   ... haftungsart, haftungsquote, haftungsbegruendung,
#       notizen, gesamt_gefordert, gesamt_reguliert, gesamt_kuerzung,
#       parse_status, parse_quelle, erfasst_am
#
# NEU (quelle + wdm_importiert ergänzt):
#   ... haftungsart, haftungsquote, haftungsbegruendung,
#       notizen, gesamt_gefordert, gesamt_reguliert, gesamt_kuerzung,
#       parse_status, parse_quelle, erfasst_am,
#       quelle, wdm_importiert
#
# Und im VALUES-Teil entsprechend:
#   ..., data.get("quelle", "pdf"), int(data.get("wdm_importiert", 0))
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# NEU: PUT-Route – Abrechnung bearbeiten (nur quelle='manuell')
# ──────────────────────────────────────────────────────────────────────────────

PUT_ROUTE = '''
@bp.route("/<path:akte_id>/abrechnungen/<int:ab_id>", methods=["PUT"])
@login_required
def update_abrechnung(akte_id, ab_id):
    """Bearbeitet eine manuelle Abrechnung komplett (inkl. Positionen)."""
    data = request.get_json() or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT quelle FROM abrechnungen WHERE id=? AND akte_id=?",
            (ab_id, akte_id)
        ).fetchone()
        if not row:
            return {"error": "Nicht gefunden"}, 404
        if row["quelle"] != "manuell":
            return {"error": "Nur manuelle Abrechnungen sind bearbeitbar"}, 403

        positionen = data.get("positionen", [])
        gesamt_gefordert = round(sum(float(p.get("betrag_gefordert") or 0) for p in positionen), 2)
        gesamt_reguliert = round(sum(float(p.get("betrag_reguliert") or 0) for p in positionen), 2)
        gesamt_kuerzung  = round(gesamt_gefordert - gesamt_reguliert, 2)

        conn.execute("""
            UPDATE abrechnungen SET
                datum=?, versicherung=?, referenz_nr=?,
                haftungsart=?, haftungsquote=?,
                haftungsbegruendung=?, notizen=?,
                gesamt_gefordert=?, gesamt_reguliert=?, gesamt_kuerzung=?
            WHERE id=? AND akte_id=?
        """, (
            data.get("datum"), data.get("versicherung", ""),
            data.get("referenz_nr", ""),
            data.get("haftungsart", "vollhaftung"),
            float(data.get("haftungsquote") or 100),
            data.get("haftungsbegruendung", ""),
            data.get("notizen", ""),
            gesamt_gefordert, gesamt_reguliert, gesamt_kuerzung,
            ab_id, akte_id
        ))

        # Positionen komplett ersetzen
        conn.execute(
            "DELETE FROM abrechnungen_positionen WHERE abrechnung_id=?",
            (ab_id,)
        )
        for pos in positionen:
            g = round(float(pos.get("betrag_gefordert") or 0), 2)
            r = round(float(pos.get("betrag_reguliert") or 0), 2)
            if g <= 0 and r <= 0:
                continue
            conn.execute("""
                INSERT INTO abrechnungen_positionen
                    (abrechnung_id, position_key, position_label,
                     betrag_gefordert, betrag_reguliert,
                     kuerzungsart_id, kuerzung_freitext,
                     fuer_klage_vorgemerkt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ab_id,
                pos.get("position_key", "sonstiges"),
                pos.get("position_label"),
                g, r,
                pos.get("kuerzungsart_id"),
                pos.get("kuerzung_freitext", ""),
                1 if pos.get("fuer_klage_vorgemerkt") else 0,
            ))

        ab = _lade_abrechnung_mit_positionen(conn, ab_id)

    return {"abrechnung": ab}
'''

# ──────────────────────────────────────────────────────────────────────────────
# NEU: DELETE-Route – Abrechnung löschen (nur quelle='manuell')
# ──────────────────────────────────────────────────────────────────────────────

DELETE_ROUTE = '''
@bp.route("/<path:akte_id>/abrechnungen/<int:ab_id>", methods=["DELETE"])
@login_required
def delete_abrechnung(akte_id, ab_id):
    """Löscht eine manuelle Abrechnung inkl. aller Positionen."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT quelle FROM abrechnungen WHERE id=? AND akte_id=?",
            (ab_id, akte_id)
        ).fetchone()
        if not row:
            return {"error": "Nicht gefunden"}, 404
        if row["quelle"] != "manuell":
            return {"error": "Nur manuelle Abrechnungen sind löschbar"}, 403

        conn.execute(
            "DELETE FROM abrechnungen_positionen WHERE abrechnung_id=?",
            (ab_id,)
        )
        conn.execute(
            "DELETE FROM abrechnungen WHERE id=?",
            (ab_id,)
        )

    return {"deleted": True, "id": ab_id}
'''

# ──────────────────────────────────────────────────────────────────────────────
# NEU: GET wdm-check – WDM-Regulierung prüfen (für Auto-Import-Hinweis)
# ──────────────────────────────────────────────────────────────────────────────

WDM_CHECK_ROUTE = '''
@bp.route("/<path:akte_id>/abrechnungen/wdm-check", methods=["GET"])
@login_required
def wdm_check(akte_id):
    """
    Prüft ob WDM-Regulierungsdaten vorhanden sind aber noch kein DB-Eintrag.
    Gibt { verfuegbar: bool, bereits_importiert: bool, vorschau: dict|null } zurück.
    """
    # 1. Bestehende DB-Einträge prüfen
    with get_db() as conn:
        anzahl = conn.execute(
            "SELECT COUNT(*) FROM abrechnungen WHERE akte_id=?",
            (akte_id,)
        ).fetchone()[0]
        wdm_bereits = conn.execute(
            "SELECT COUNT(*) FROM abrechnungen WHERE akte_id=? AND quelle=\'wdm\'",
            (akte_id,)
        ).fetchone()[0]

    if wdm_bereits > 0:
        return {"verfuegbar": False, "bereits_importiert": True, "vorschau": None}

    # 2. WDM laden
    try:
        from ..ramicro.verbindung import get_ramicro_conn
        from ..ramicro.wdm_regulierung_service import lade_wdm_regulierung, hat_wdm_regulierung, wdm_zu_abrechnung
        conn_ra = get_ramicro_conn()
        # Aktenzeichen ohne Kürzel
        az_kurz = akte_id.split("/")[0] + "/" + akte_id.split("/")[1] if "/" in akte_id else akte_id
        wdm = lade_wdm_regulierung(az_kurz, conn_ra)
    except Exception as e:
        return {"verfuegbar": False, "bereits_importiert": False,
                "vorschau": None, "fehler": str(e)}

    if not hat_wdm_regulierung(wdm or {}):
        return {"verfuegbar": False, "bereits_importiert": False, "vorschau": None}

    vorschau = wdm_zu_abrechnung(wdm)
    return {
        "verfuegbar": True,
        "bereits_importiert": False,
        "vorschau": vorschau,
    }
'''

# ──────────────────────────────────────────────────────────────────────────────
# NEU: POST wdm-import – WDM-Daten als Abrechnung speichern
# ──────────────────────────────────────────────────────────────────────────────

WDM_IMPORT_ROUTE = '''
@bp.route("/<path:akte_id>/abrechnungen/wdm-import", methods=["POST"])
@login_required
def wdm_import(akte_id):
    """
    Importiert WDM-Regulierungsdaten als Abrechnung (quelle=\'wdm\').
    Wird nur ausgeführt wenn noch kein WDM-Import existiert.
    """
    with get_db() as conn:
        bereits = conn.execute(
            "SELECT COUNT(*) FROM abrechnungen WHERE akte_id=? AND quelle=\'wdm\'",
            (akte_id,)
        ).fetchone()[0]
        if bereits > 0:
            return {"error": "WDM bereits importiert"}, 409

    try:
        from ..ramicro.verbindung import get_ramicro_conn
        from ..ramicro.wdm_regulierung_service import lade_wdm_regulierung, wdm_zu_abrechnung
        conn_ra = get_ramicro_conn()
        az_kurz = akte_id.split("/")[0] + "/" + akte_id.split("/")[1] if "/" in akte_id else akte_id
        wdm = lade_wdm_regulierung(az_kurz, conn_ra)
        ab_data = wdm_zu_abrechnung(wdm or {})
    except Exception as e:
        return {"error": f"WDM-Lesefehler: {e}"}, 500

    if not ab_data:
        return {"error": "Keine WDM-Regulierungsdaten gefunden"}, 404

    # Als normale Abrechnung speichern (quelle=\'wdm\')
    from flask import current_app
    # Bestehende erstelle-Logik wiederverwenden via request-Kontext simulieren
    # → Einfachste Lösung: direkt in DB schreiben
    with get_db() as conn:
        from datetime import datetime as dt
        cur = conn.execute("""
            INSERT INTO abrechnungen
                (akte_id, datum, versicherung, referenz_nr,
                 haftungsart, haftungsquote, haftungsbegruendung,
                 notizen, gesamt_gefordert, gesamt_reguliert,
                 gesamt_kuerzung, parse_status, quelle,
                 wdm_importiert, erfasst_am)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            akte_id,
            ab_data["datum"], ab_data.get("versicherung",""),
            ab_data.get("referenz_nr",""),
            ab_data.get("haftungsart","vollhaftung"),
            ab_data.get("haftungsquote",100),
            ab_data.get("haftungsbegruendung",""),
            ab_data.get("notizen",""),
            ab_data["gesamt_gefordert"], ab_data["gesamt_reguliert"],
            ab_data["gesamt_kuerzung"],
            "erfolgreich", "wdm", 1,
            dt.now().strftime("%d.%m.%Y"),
        ))
        ab_id = cur.lastrowid
        for pos in ab_data["positionen"]:
            conn.execute("""
                INSERT INTO abrechnungen_positionen
                    (abrechnung_id, position_key, position_label,
                     betrag_gefordert, betrag_reguliert,
                     kuerzungsart_id, kuerzung_freitext,
                     fuer_klage_vorgemerkt)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                ab_id,
                pos["position_key"], pos.get("position_label"),
                pos["betrag_gefordert"], pos["betrag_reguliert"],
                None, "", 0,
            ))
        ab = _lade_abrechnung_mit_positionen(conn, ab_id)

    return {"abrechnung": ab}, 201
'''
