"""
Distanz-Prüfung für Verweisbetriebe
=====================================
GET  /distanz/prüfen    – Entfernung zwischen Mandant und Werkstatt
POST /distanz/parsen    – Verweisbetrieb aus PDF-Text extrahieren
"""
import logging
from flask import Blueprint, request, jsonify
from ..auth.middleware import login_erforderlich

logger = logging.getLogger(__name__)
distanz_bp = Blueprint("distanz", __name__, url_prefix="/distanz")


def _j(d, s=200): return jsonify(d), s
def _err(m, s=400): return jsonify({"fehler": m}), s


@distanz_bp.route("/prüfen", methods=["GET", "POST"])
@login_erforderlich
def prüfen():
    """
    GET  /distanz/prüfen?mandant=Andréstr.+10,+63067+Offenbach&werkstatt=...&name=...&km=3.2
    POST /distanz/prüfen  body: {mandant_adresse, werkstatt_adresse, werkstatt_name, km_genannt}

    Prüft die echte Entfernung via OpenRouteService und erstellt Textbaustein.
    """
    if request.method == "POST":
        d = request.get_json(silent=True) or {}
        mandant_adresse   = (d.get("mandant_adresse") or "").strip()
        werkstatt_adresse = (d.get("werkstatt_adresse") or "").strip()
        werkstatt_name    = (d.get("werkstatt_name") or "").strip()
        km_genannt        = d.get("km_genannt")
    else:
        mandant_adresse   = (request.args.get("mandant") or "").strip()
        werkstatt_adresse = (request.args.get("werkstatt") or "").strip()
        werkstatt_name    = (request.args.get("name") or "").strip()
        km_genannt_str    = (request.args.get("km") or "").strip()
        try:
            km_genannt = float(km_genannt_str.replace(",", ".")) if km_genannt_str else None
        except ValueError:
            km_genannt = None

    if not mandant_adresse:
        return _err("mandant_adresse erforderlich")
    if not werkstatt_adresse:
        return _err("werkstatt_adresse erforderlich")

    try:
        km_genannt_f = float(str(km_genannt).replace(",", ".")) if km_genannt is not None else None
    except (ValueError, TypeError):
        km_genannt_f = None

    try:
        from ..services.werkstatt_service import pruefe_entfernung
        result = pruefe_entfernung(
            mandant_adresse=mandant_adresse,
            werkstatt_adresse=werkstatt_adresse,
            werkstatt_name=werkstatt_name,
            km_genannt=km_genannt_f,
        )
    except Exception as e:
        logger.error("Entfernungsprüfung: %s", e)
        return _err(f"Prüfung fehlgeschlagen: {e}", 500)

    return _j(result)


@distanz_bp.route("/debug", methods=["POST"])
@login_erforderlich
def debug_geocoding():
    """
    POST /distanz/debug
    Body: { mandant_adresse, werkstatt_adresse, werkstatt_name }
    Gibt alle Zwischenschritte zurück: bereinigte Adressen, Koordinaten,
    Routendetails – zum Debuggen von Geocoding-Problemen.
    """
    from ..services.werkstatt_service import (
        _bereinige_adresse, geocode, ORS_BASE, ORS_API_KEY
    )
    import urllib.request, json as _json

    d = request.get_json(silent=True) or {}
    mandant_adr   = (d.get("mandant_adresse") or "").strip()
    werkstatt_adr = (d.get("werkstatt_adresse") or "").strip()
    werkstatt_name = (d.get("werkstatt_name") or "").strip()

    result = {
        "eingabe": {
            "mandant_adresse":   mandant_adr,
            "werkstatt_adresse": werkstatt_adr,
            "werkstatt_name":    werkstatt_name,
        },
        "bereinigt": {
            "mandant":   _bereinige_adresse(mandant_adr),
            "werkstatt": _bereinige_adresse(werkstatt_adr),
        },
        "geocoding": {},
        "routing":   {},
        "fehler":    None,
    }

    def _geocode_debug(adresse):
        """Geocodiert und gibt alle ORS-Treffer zurück."""
        if not ORS_API_KEY:
            return {"fehler": "ORS_APIKEY nicht gesetzt"}
        clean = _bereinige_adresse(adresse)
        import urllib.parse
        q = urllib.parse.quote(clean)
        url = (f"{ORS_BASE}/geocode/search"
               f"?api_key={ORS_API_KEY}&text={q}&boundary.country=DE&size=3")
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json", "User-Agent": "Kanzlei-Debug/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = _json.loads(r.read())
            treffer = []
            for f in data.get("features", []):
                coords = f["geometry"]["coordinates"]
                props  = f.get("properties", {})
                treffer.append({
                    "label":      props.get("label", ""),
                    "confidence": props.get("confidence", 0),
                    "lat":        coords[1],
                    "lng":        coords[0],
                    "land":       props.get("country_a", ""),
                    "plz":        props.get("postalcode", ""),
                    "ort":        props.get("locality", ""),
                })
            return {"anfrage": clean, "treffer": treffer}
        except Exception as e:
            return {"fehler": str(e), "anfrage": clean}

    # Geocoding beider Adressen
    result["geocoding"]["mandant"]   = _geocode_debug(mandant_adr)
    result["geocoding"]["werkstatt"] = _geocode_debug(werkstatt_adr)

    # Routing wenn beide erfolgreich
    m_treffer = result["geocoding"]["mandant"].get("treffer", [])
    w_treffer = result["geocoding"]["werkstatt"].get("treffer", [])

    if m_treffer and w_treffer:
        m = m_treffer[0]
        w = w_treffer[0]
        try:
            url = f"{ORS_BASE}/v2/directions/driving-car"
            body = _json.dumps({
                "coordinates": [[m["lng"], m["lat"]], [w["lng"], w["lat"]]]
            }).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": ORS_API_KEY,
                "User-Agent": "Kanzlei-Debug/1.0",
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = _json.loads(r.read())
            summary = data["routes"][0]["summary"]
            # GeoJSON-Geometrie für Kartenanzeige
            geometry = data["routes"][0].get("geometry", "")
            result["routing"] = {
                "km":       round(summary["distance"] / 1000, 1),
                "minuten":  round(summary["duration"] / 60),
                "von":      {"lat": m["lat"], "lng": m["lng"], "label": m["label"]},
                "nach":     {"lat": w["lat"], "lng": w["lng"], "label": w["label"]},
                "geometry": geometry,  # encoded polyline
            }
        except Exception as e:
            result["routing"]["fehler"] = str(e)
    else:
        result["fehler"] = "Geocoding für eine oder beide Adressen fehlgeschlagen"

    return _j(result)


@distanz_bp.route("/parsen", methods=["POST"])
@login_erforderlich
def parsen():
    """
    POST /distanz/parsen
    Body: { text: "...", dok_id: 123 }  (text = extrahierter PDF-Text)

    Extrahiert Verweisbetrieb-Daten aus Regulierungsschreiben / Prüfbericht.
    """
    d    = request.get_json(silent=True) or {}
    text = (d.get("text") or "").strip()

    if not text:
        # Alternativ: dok_id → direkt aus DB laden
        dok_id = d.get("dok_id")
        if dok_id:
            text = _lade_dokument_text(dok_id)

    if not text:
        return _err("text oder dok_id erforderlich")

    try:
        from ..services.werkstatt_service import extrahiere_verweisbetrieb
        result = extrahiere_verweisbetrieb(text)
    except Exception as e:
        logger.error("Verweis-Parser: %s", e)
        return _err(f"Parsing fehlgeschlagen: {e}", 500)

    return _j(result)


@distanz_bp.route("/prüfen-aus-dokument", methods=["POST"])
@login_erforderlich
def prüfen_aus_dokument():
    """
    POST /distanz/prüfen-aus-dokument
    Body: { akte_id, dok_id?, pb_id?, km_genannt? }

    Variante A – dok_id: direkte Dokument-ID → PDF-Text lesen → Parser
    Variante B – pb_id:  Prüfbericht-ID → dokument_id + gespeicherte Werkstattdaten
    """
    from ..services.werkstatt_service import extrahiere_verweisbetrieb, pruefe_entfernung
    d       = request.get_json(silent=True) or {}
    akte_id = (d.get("akte_id") or "").strip()
    dok_id  = d.get("dok_id")
    pb_id   = d.get("pb_id")

    if not akte_id:
        return _err("akte_id erforderlich")
    if not dok_id and not pb_id:
        return _err("dok_id oder pb_id erforderlich")

    # Mandant-Adresse immer zuerst holen
    mandant_adresse = _mandant_adresse(akte_id)
    if not mandant_adresse:
        return _err(f"Mandant-Adresse für Akte {akte_id} nicht gefunden", 404)

    verweis_daten = None

    # ── Variante B: Prüfbericht-ID → gespeicherte Werkstattdaten direkt nutzen ──
    if pb_id:
        pb = _lade_pruefbericht(pb_id, akte_id)
        if pb:
            # Werkstattdaten direkt aus gespeichertem Prüfbericht
            wb_name  = pb.get("referenzwerkstatt_name") or ""
            wb_adr   = pb.get("referenzwerkstatt_adresse") or ""
            km_gen   = pb.get("referenzwerkstatt_entfernung")
            if wb_name or wb_adr:
                verweis_daten = {
                    "gefunden":   True,
                    "name":       wb_name,
                    "adresse":    wb_adr,
                    "plz_ort":    "",
                    "km_genannt": km_gen,
                    "quelle":     "pruefbericht_db",
                }
            # Fallback: dok_id aus Prüfbericht
            if not verweis_daten and pb.get("dokument_id"):
                dok_id = pb["dokument_id"]

    # ── Variante A oder Fallback: PDF-Text lesen + Parser ───────────────────
    if not verweis_daten and dok_id:
        text = _lade_dokument_text(dok_id)
        if not text:
            return _err("Dokument-Text konnte nicht geladen werden", 404)
        verweis_daten = extrahiere_verweisbetrieb(text)

    if not verweis_daten or not verweis_daten.get("gefunden"):
        return _j({
            "verweis_gefunden": False,
            "hinweis": "Kein Verweisbetrieb gefunden.",
        })

    # Werkstatt-Adresse zusammenbauen
    werkstatt_teile = [
        verweis_daten.get("name", ""),
        verweis_daten.get("adresse", ""),
        verweis_daten.get("plz_ort", ""),
    ]
    werkstatt_adresse = ", ".join(t for t in werkstatt_teile if t)

    if not werkstatt_adresse.strip():
        return _j({
            "verweis_gefunden": True,
            "ok": False,
            "werkstatt_name":    verweis_daten.get("name", ""),
            "werkstatt_adresse": "",
            "km_genannt":        verweis_daten.get("km_genannt"),
            "km_echt":           None,
            "fehler":            "Werkstatt-Adresse unvollständig – Entfernung manuell prüfen",
            "verweis_raw":       verweis_daten,
        })

    result = pruefe_entfernung(
        mandant_adresse=mandant_adresse,
        werkstatt_adresse=werkstatt_adresse,
        werkstatt_name=verweis_daten.get("name", ""),
        km_genannt=verweis_daten.get("km_genannt"),
    )
    result["verweis_gefunden"] = True
    result["verweis_raw"]      = verweis_daten
    return _j(result)


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _lade_pruefbericht(pb_id: int, akte_id: str):
    """Lädt einen Prüfbericht aus der DB und gibt ihn als dict zurück."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                """SELECT id, dokument_id, referenzwerkstatt_name,
                          referenzwerkstatt_adresse, referenzwerkstatt_entfernung
                   FROM pruefberichte WHERE id = ? AND akte_id = ?""",
                (pb_id, akte_id)
            ).fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error("Pruefbericht laden %s: %s", pb_id, e)
        return None


def _lade_dokument_text(dok_id: int):
    """
    Lädt den extrahierten Text eines Dokuments.
    Sucht in parse_json nach: volltext → gesamt_text → rohtext → text
    Falls keines vorhanden: holt Datei aus Filesystem und extrahiert Text.
    """
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, dateipfad, dateityp FROM dokumente WHERE id = ?",
                (dok_id,)
            ).fetchone()
        if not row:
            return None
        # Aus parse_json lesen
        if row["parse_json"]:
            import json
            data = json.loads(row["parse_json"])
            text = (data.get("volltext") or data.get("gesamt_text")
                    or data.get("rohtext") or data.get("text") or "")
            if text and len(text) > 50:
                return text
        # Fallback: Datei direkt lesen und Text extrahieren
        if row["dateipfad"] and row["dateityp"] == "pdf":
            try:
                import pdfplumber
                with pdfplumber.open(row["dateipfad"]) as pdf:
                    seiten = [p.extract_text() or "" for p in pdf.pages]
                    return "\n".join(seiten)
            except Exception as e2:
                logger.debug("pdfplumber fallback: %s", e2)
        return None
    except Exception as e:
        logger.error("Dokument-Text laden %s: %s", dok_id, e)
        return None


def _mandant_adresse(akte_id: str):
    """Liest Mandant-Adresse (Anschrift + PLZ + Ort) aus beteiligte.

    Fallback read-only aus RA-MICRO (Muster _lade_beteiligte_aus_ramicro,
    wie beteiligte_/klage_routes), wenn lokal kein Mandant mit Adresse
    erfasst ist -- frische RA-MICRO-Akten haben lokal 0 beteiligte-Zeilen."""
    def _baue(anschrift, plz, ort):
        teile = [
            anschrift or "",
            " ".join(filter(None, [plz or "", ort or ""])),
        ]
        return ", ".join(t for t in teile if t) or None

    try:
        from ..models.schaden import hole_beteiligte_by_akte
        for b in hole_beteiligte_by_akte(akte_id):
            if getattr(b, "rolle", "") == "mandant":
                adresse = _baue(getattr(b, "anschrift", ""),
                                getattr(b, "plz", ""), getattr(b, "ort", ""))
                if adresse:
                    return adresse
    except Exception as e:
        logger.error("Mandant-Adresse %s: %s", akte_id, e)

    try:
        from ..word.word_service import _lade_beteiligte_aus_ramicro
        mandant = (_lade_beteiligte_aus_ramicro(akte_id) or {}).get("mandant")
        if mandant:
            return _baue(mandant.get("anschrift"), mandant.get("plz"),
                         mandant.get("ort"))
    except Exception as e:
        logger.error("Mandant-Adresse RA-MICRO %s: %s", akte_id, e)
    return None
