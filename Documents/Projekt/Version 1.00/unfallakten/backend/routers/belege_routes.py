"""
Schadenposition-Belege Routes (PRD-23a / PRD-23b)
===================================================
Verknuepft Schadenpositionen mit Beleg-Dokumenten.

Endpoints:
  GET    /akten/<az>/belege               Alle Belege einer Akte
  POST   /akten/<az>/belege               Beleg zuordnen
  DELETE /akten/<az>/belege/<id>          Zuordnung entfernen
  GET    /akten/<az>/belege/kandidaten    Rechnungs-Kandidaten (PRD-23b)

Python 3.9 kompatibel.
"""

import json as _json
import logging
import os as _os
import re as _re
from typing import Optional
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ..db.database import get_connection


# ── RA-Micro Beteiligte-Fallback ──────────────────────────────────────────────

# sBeteiligtenKennzeichen → interne Rolle
_KZ_ROLLE_MAP = {
    "M":    "mandant",
    "M1":   "mandant",
    "SV":   "sachverstaendiger",
    "SV1":  "sachverstaendiger",
    "GHPV": "gegner",
    "GH":   "gegner",
    "GHV":  "gegner",
    "GBEV": "gegner",
    "G":    "gegner",
    "G1":   "gegner",
}


def _az_basis(az_str: str) -> str:
    """Entfernt SB-Kuerzel (z.B. '1006/25AS' → '1006/25')."""
    return _re.sub(r'[A-Z]{2,3}$', '', (az_str or "").strip().upper()).strip() or az_str


def _lade_beteiligte_alle_ramicro(az: str) -> list:
    """
    Laedt alle aktiven Beteiligten einer Akte aus RA-Micro (inkl. SV, Mietwagen etc.).
    Gibt Liste von dicts mit {rolle, name, email} zurueck.
    Fehler werden stumm geschluckt (graceful degradation).
    """
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler,
        )
    except ImportError:
        return []

    az_like = _az_basis(az) + "%"
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 1 a.GUIDAkte
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": az_like})
            row = cur.fetchone()
            if not row:
                return []
            guid_akte = row["GUIDAkte"]

            cur.execute("""
                SELECT b.sBeteiligtenKennzeichen AS kz,
                       b.iBeteiligtenArt         AS art,
                       adr.sNachname, adr.sVorname,
                       adr.sErsteAdresszeile,
                       adr.sEMail
                FROM tblAktenBeteiligte b
                INNER JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.GUIDAkte = %(guid)s AND b.bDeaktiviert = 0
            """, {"guid": guid_akte})
            rows = cur.fetchall()

        from ..word.word_service import name_aus_ramicro_adresse
        result = []
        for r in rows:
            kz  = (r.get("kz") or "").strip().upper()
            art = r.get("art") or 0
            # Rolle bestimmen: erst KZ-Map, dann art-Fallback
            if kz in _KZ_ROLLE_MAP:
                rolle = _KZ_ROLLE_MAP[kz]
            elif kz.startswith("SV"):
                rolle = "sachverstaendiger"
            elif art == 1:
                rolle = "mandant"
            elif art in (2, 4, 9):
                rolle = "gegner"
            else:
                rolle = "sonstiger"

            nachname = (r.get("sNachname")         or "").strip()
            erste    = (r.get("sErsteAdresszeile") or "").strip()
            name = name_aus_ramicro_adresse(nachname, erste)
            email = (r.get("sEMail") or "").strip()

            result.append({"rolle": rolle, "name": name, "email": email})
        return result
    except Exception as e:
        logging.getLogger(__name__).debug(
            "_lade_beteiligte_alle_ramicro(%s): %s", az, e
        )
        return []


# ── PRD-23b: Hilfsfunktionen fuer Rechnungs-Kandidaten ───────────────────────

# Firmenname-Keyword → Schadenposition-Key
_FIRMA_POSITION_MAP = [
    (["ABSCHLEPP", "BERGUNG", "PANNENDIENST", "PANNENHILFE"],
     "abschleppkosten"),
    (["MIETWAGEN", "AUTOVERMIET", "LEIHWAGEN",
      "HERTZ", "SIXT", "EUROPCAR", "BUCHBINDER", "AVIS"],
     "mietwagenkosten_netto"),
    (["WERKSTATT", "KAROSSERIE", "LACKIER",
      "REPARATUR", "UNFALLINSTAND", "KFZ-MEISTER"],
     "rep_rechnung_netto"),
    (["STANDPLATZ", "DEPOT", "ABSTELLPLATZ", "LAGERPLATZ"],
     "standkosten_netto"),
]

# Dokumentenklasse (Registry) → Schadenposition-Key
# HINWEIS P1.5b: die semantisch aequivalente Registry-Quelle liegt in
# backend/registry/rechnungstyp_mapping.yaml und wird von
# services/eingehende_ereignisse.rechnungstyp_zu_position() ausgewertet.
# Die Alt-Konstante bleibt hier fuer die Kandidaten-Vorschlaege
# (kandidaten()-Endpoint) unangetastet, weil sie schadenpositionen-
# Spalten mit _netto-Suffix verwendet, die nicht in positionsarten.yaml
# liegen. Konsolidierung auf ein Mapping erfolgt mit P1.7.
_KLASSE_POSITION_MAP = {
    "abschlepprechnung":    "abschleppkosten",
    "standkostenrechnung":  "standkosten",
    "reparaturrechnung":    "rep_rechnung_netto",
    "mietwagenrechnung":    "mietwagenkosten_netto",
    "werkstattrechnung":    "rep_rechnung_netto",
    # sv_rechnung ist eine separate SV-Honorarrechnung → sv_kosten
    # (vorsteuer-abhängige Variante wird unten im Loop gesetzt)
    "sv_rechnung":          "__sv_kosten_vorsteuer__",
}

# ── E-Akte Whitelist-Filter ──────────────────────────────────────────────────
# Rubrik-Werte → Dokument ist für den Schaden-Parser irrelevant
# (Gerichts- und Behördenkorrespondenz sowie ausgehende Kanzleischreiben)
_EAKTE_RUBRIK_SKIP = frozenset({
    "gerichtlich",
    "verwaltungsbehörde",
    "verwaltungsbehoerde",    # ASCII-Fallback ohne Umlaut
    "an mandant",             # Weiterleitungen zur Kenntnis → ausgehend, kein Schadendokument
})

# Gericht-Substrings im Empfänger-Feld (Fallback wenn Rubrik nicht gesetzt)
_EMPFAENGER_GERICHT_KW = (
    "amtsgericht", "landgericht", "oberlandesgericht",
    "bundesgerichtshof", "arbeitsgericht", "sozialgericht",
    "finanzgericht", "verwaltungsgericht",
    "gerichtskasse", "justizkasse",
)


def _ist_firma(b):
    # type: (dict) -> bool
    """Port aus KlageSection.jsx:209 – erkennt Firmenbeteiligte."""
    anrede = (b.get("anrede") or "").lower()
    vorname = b.get("vorname") or ""
    rolle = b.get("rolle") or ""
    return bool(anrede == "firma" or (not vorname and rolle != "mandant"))


def _position_aus_firmenname(name):
    # type: (str) -> Optional[str]
    n = (name or "").upper()
    for keywords, pos_key in _FIRMA_POSITION_MAP:
        if any(k in n for k in keywords):
            return pos_key
    return None


def _domain_aus_email(email):
    # type: (str) -> Optional[str]
    if not email or "@" not in email:
        return None
    return email.split("@")[-1].lower().strip()


def _routing_basis_eakte_dok(dok):
    # type: (dict) -> str
    """
    Bestimmt Routing-Signal für ein E-Akte-Dokument (für Debug-Anzeige in der UI).
    Gleiche Logik wie _bestimme_routing() in pdf_parse_routes.py.
    """
    domain = (dok.get("absender_domain") or "").lower()
    rubrik = (dok.get("rubrik") or "").lower()
    try:
        from ..parsers.document_classifier import VERSICHERER_PATTERNS
        if domain:
            for pattern, _k, _n, _p in VERSICHERER_PATTERNS:
                if _re.search(pattern, domain):
                    return "domain_versicherer"
    except Exception:
        pass
    if rubrik in {"von mandant", "außergerichtlich"}:
        return "rubrik"
    if not domain and not rubrik:
        return "fallback_kein_signal"
    return "fallback_domain_unbekannt"


def _eakte_dok_uberspringen(dok):
    # type: (dict) -> Optional[str]
    """
    Gibt Grund-String zurück wenn das Dokument übersprungen werden soll, sonst None.

    Übersprungen werden:
    - Schlagwort "E-Brief" (ausgehende E-Mails via RA-MICRO E-Brief-Modul)
    - Rubrik "Gerichtlich" / "Verwaltungsbehörde" / "An Mandant"
    - Empfänger-Feld enthält Gericht-Bezeichnung (Fallback ohne Rubrik)
    """
    if (dok.get("schlagwort") or "").lower().strip() == "e-brief":
        return "schlagwort_ebrief"
    rubrik = (dok.get("rubrik") or "").lower().strip()
    if rubrik in _EAKTE_RUBRIK_SKIP:
        # Normalisierter Key: Leerzeichen→Unterstrich, Umlaute→ASCII
        key = (rubrik
               .replace(" ", "_")
               .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
               .replace("ß", "ss"))
        return "rubrik_%s" % key
    empf = (dok.get("empfaenger") or "").lower()
    if any(kw in empf for kw in _EMPFAENGER_GERICHT_KW):
        return "empfaenger_gericht"
    return None


def _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer):
    # type: (dict, list, bool) -> list
    """
    Versucht einem E-Akte-Dokument Schadenposition(en) zuzuordnen.
    Gibt eine Liste von Kandidat-Dicts zurück (leer = kein Treffer).

    Nutzt alle verfügbaren RA-MICRO-Felder:
      rubrik, schlagwort, bemerkung, anzeigename, absender_domain
    """
    domain = (dok.get("absender_domain") or "").lower()

    # Alle Textfelder für Keyword-Erkennung zusammenführen
    text = " ".join([
        dok.get("bemerkung")    or "",
        dok.get("rubrik")       or "",
        dok.get("schlagwort")   or "",
        dok.get("anzeigename")  or "",
    ]).lower()

    ist_gutachten = any(k in text for k in [
        "gutachten", "schadengutachten", "kfzgutachten", "kfz-gutachten",
        "fahrzeugbewertung", "schadensbewertung",
    ])
    ist_abrechnung = any(k in text for k in [
        "regulierung", "regulierungsschreiben", "schadensregulierung",
        "abrechnung", "abrechnungsschreiben", "schadensabrechnung",
        "zahlungsnachweis", "regulierungsangebot",
    ])
    # \brechnung\b: kein Match bei "Abrechnungsschreiben" (wäre Substring)
    ist_rechnung = (
        not ist_abrechnung and (
            any(k in text for k in ["honorar", "invoice", "honorarrechnung"])
            or bool(_re.search(r"\brechnung\b", text))
            or bool(_re.search(r"\brg\b", text))
        )
    )

    sv_pos = "sv_kosten_netto" if vorsteuer else "sv_kosten"

    def _gut_kandidaten(konfidenz, grund, lieferant):
        # type: (float, str, object) -> list
        return [
            {"position_key": p, "konfidenz": konfidenz,
             "grund": grund, "lieferant": lieferant}
            for p in ("rep_gutachten_netto", "wiederbeschaffung",
                      "restwert", "wertminderung")
        ]

    # ── Sachverständiger: Domain-Match hat höchste Priorität ─────────────────
    for b in beteiligte:
        if b.get("rolle") != "sachverstaendiger":
            continue
        b_domain = _domain_aus_email(b.get("email") or "")
        if not (domain and b_domain and domain == b_domain):
            continue
        name = b.get("name")
        if ist_gutachten and not ist_rechnung:
            return _gut_kandidaten(0.88, "domain_match_sv_gutachten", name)
        elif ist_rechnung and not ist_gutachten:
            return [{"position_key": sv_pos, "konfidenz": 0.90,
                     "grund": "domain_match_sv_rechnung", "lieferant": name}]
        else:
            # Unklar: Domain passt, aber kein eindeutiger Dokumenttyp
            # → Gutachten ist das häufigere primäre Dokument vom SV
            return _gut_kandidaten(0.72, "domain_match_sv_unklar", name)

    # ── Gutachten ohne Domain-Match (nur Keywords) ────────────────────────────
    if ist_gutachten and not ist_rechnung:
        return _gut_kandidaten(0.65, "keyword_gutachten", None)

    # ── Sonstige Firmen (Werkstatt, Abschlepper …) ────────────────────────────
    for b in beteiligte:
        if b.get("rolle") != "sonstiger" or not _ist_firma(b):
            continue
        b_domain = _domain_aus_email(b.get("email") or "")
        if domain and b_domain and domain == b_domain:
            pos = _position_aus_firmenname(b.get("name") or "")
            if pos:
                return [{"position_key": pos, "konfidenz": 0.90,
                         "grund": "domain_match", "lieferant": b.get("name")}]
        pos = _position_aus_firmenname(b.get("name") or "")
        if pos:
            return [{"position_key": pos, "konfidenz": 0.60,
                     "grund": "firmenname_keyword", "lieferant": b.get("name")}]

    # ── Dateiname-Fallback (Rechnung ohne zugeordneten Beteiligten) ───────────
    if ist_rechnung:
        return [{"position_key": None, "konfidenz": 0.40,
                 "grund": "dateiname_keyword_rechnung", "lieferant": None}]

    # ── Regulierungs-/Abrechnungsschreiben (Versicherer) ─────────────────────
    if ist_abrechnung:
        return [{"position_key": None, "konfidenz": 0.80,
                 "grund": "keyword_abrechnungsschreiben", "lieferant": None}]

    return []

logger = logging.getLogger(__name__)

belege_bp = Blueprint("belege", __name__, url_prefix="/akten/<path:akte_id>/belege")


def _j(daten, status=200):
    return jsonify(daten), status


def _err(msg, status):
    return jsonify({"fehler": msg, "status": status}), status


@belege_bp.route("", methods=["GET"])
@login_erforderlich
def liste(akte_id):
    """
    GET /akten/<az>/belege
    Gibt alle Beleg-Zuordnungen einer Akte zurueck, inkl. Dokument-Metadaten.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT b.id, b.akte_az, b.position_key, b.dokument_id,
                       b.betrag_aus_beleg, b.notiz, b.erstellt_am,
                       d.dateiname, d.dokumentenklasse, d.quelle, d.dateipfad
                FROM schadenposition_belege b
                LEFT JOIN dokumente d ON d.id = b.dokument_id
                WHERE b.akte_az = ?
                ORDER BY b.position_key
            """, (akte_id,)).fetchall()

        belege = []
        for r in rows:
            belege.append({
                "id": r["id"],
                "position_key": r["position_key"],
                "dokument_id": r["dokument_id"],
                "betrag_aus_beleg": r["betrag_aus_beleg"],
                "notiz": r["notiz"],
                "erstellt_am": r["erstellt_am"],
                "dateiname": r["dateiname"],
                "dokumentenklasse": r["dokumentenklasse"],
                "quelle": r["quelle"],
                "dateipfad": r["dateipfad"],
            })

        return _j({"belege": belege})
    except Exception as e:
        logger.error("Belege laden fehlgeschlagen: %s", e)
        return _err("Belege laden fehlgeschlagen: %s" % e, 500)


@belege_bp.route("", methods=["POST"])
@login_erforderlich
def zuordnen(akte_id):
    """
    POST /akten/<az>/belege
    Ordnet ein Dokument einer Schadenposition zu.

    Body:
      {
        "position_key": "abschleppkosten",
        "dokument_id": 42,
        "betrag_aus_beleg": 380.00   (optional)
      }
    """
    body = request.get_json(silent=True) or {}
    pos_key = (body.get("position_key") or "").strip()
    dok_id = body.get("dokument_id")

    if not pos_key:
        return _err("position_key ist erforderlich.", 422)
    if not dok_id:
        return _err("dokument_id ist erforderlich.", 422)

    betrag = body.get("betrag_aus_beleg")
    notiz = body.get("notiz", "")

    try:
        with get_connection() as conn:
            # Pruefen ob Dokument existiert und zur Akte gehoert
            dok = conn.execute(
                "SELECT id, dateiname FROM dokumente WHERE id = ? AND akte_id = ?",
                (dok_id, akte_id),
            ).fetchone()
            if not dok:
                return _err("Dokument %d nicht in Akte %s gefunden." % (dok_id, akte_id), 404)

            # Upsert: bei Duplikat aktualisieren
            conn.execute("""
                INSERT INTO schadenposition_belege (akte_az, position_key, dokument_id, betrag_aus_beleg, notiz)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(akte_az, position_key, dokument_id)
                DO UPDATE SET betrag_aus_beleg = excluded.betrag_aus_beleg,
                              notiz = excluded.notiz
            """, (akte_id, pos_key, dok_id, betrag, notiz))
            conn.commit()

        logger.info("Beleg zugeordnet: %s/%s → Dok %d", akte_id, pos_key, dok_id)

        # P1.5b: Ereignis rechnung_eingegangen anlegen (Best-Effort).
        # Alt-Tabelle schadenposition_belege laeuft weiter.
        try:
            from ..services.eingehende_ereignisse import erzeuge_aus_beleg
            erzeuge_aus_beleg(
                akte_az=akte_id,
                dokument_id=int(dok_id),
                position_key=pos_key,
                betrag=(float(betrag) if betrag is not None else None),
                benutzer_id=getattr(g, "benutzer_id", None),
            )
        except Exception as exc:  # pragma: no cover -- Best-Effort
            logger.warning(
                "rechnung_eingegangen-Ereignis fehlgeschlagen "
                "(akte %s, dok %s, pos %s): %s",
                akte_id, dok_id, pos_key, exc,
            )
        return _j({"status": "ok", "position_key": pos_key, "dokument_id": dok_id})
    except Exception as e:
        logger.error("Beleg zuordnen fehlgeschlagen: %s", e)
        return _err("Zuordnung fehlgeschlagen: %s" % e, 500)


@belege_bp.route("/<int:beleg_id>", methods=["DELETE"])
@login_erforderlich
def entfernen(akte_id, beleg_id):
    """
    DELETE /akten/<az>/belege/<id>
    Entfernt eine Beleg-Zuordnung (nicht das Dokument selbst).
    """
    try:
        with get_connection() as conn:
            result = conn.execute(
                "DELETE FROM schadenposition_belege WHERE id = ? AND akte_az = ?",
                (beleg_id, akte_id),
            )
            if result.rowcount == 0:
                return _err("Beleg %d nicht gefunden." % beleg_id, 404)
            conn.commit()

        logger.info("Beleg %d entfernt fuer Akte %s", beleg_id, akte_id)
        return _j({"status": "ok"})
    except Exception as e:
        logger.error("Beleg entfernen fehlgeschlagen: %s", e)
        return _err("Entfernen fehlgeschlagen: %s" % e, 500)


@belege_bp.route("/kandidaten", methods=["GET"])
@login_erforderlich
def kandidaten(akte_id):
    """
    GET /akten/<az>/belege/kandidaten
    Gibt Rechnungs-Kandidaten fuer automatische Beleg-Zuordnung zurueck (PRD-23b).

    Zwei Quellen (Prio-Reihenfolge):
      1. Lokale dokumente WHERE dokumentenklasse LIKE 'rechnung%'
      2. E-Akte Metadaten (nur wenn RAMICRO_AKTIV + Mount erreichbar)

    Query-Parameter:
      force   "true" → Cache ignorieren (E-Akte neu laden)
    """
    try:
        with get_connection() as conn:
            # Beteiligte laden (fuer Beteiligten-Klassifikation)
            beteiligte_rows = conn.execute(
                "SELECT rolle, name, vorname, anrede, email, vorsteuer "
                "FROM beteiligte WHERE akte_id = ?",
                (akte_id,),
            ).fetchall()
            beteiligte = [dict(r) for r in beteiligte_rows]

            # Vorsteuer aus Mandant bestimmen
            mandant = next((b for b in beteiligte if b["rolle"] == "mandant"), None)
            vorsteuer_wert = str((mandant or {}).get("vorsteuer") or "N").upper()
            vorsteuer = vorsteuer_wert in ("J", "Y", "1")

            # Stufe 0: Lokale Dokumente mit bekannter Beleg-Klasse
            lokale_rows = conn.execute(
                "SELECT id, dateiname, dokumentenklasse, parse_json, parse_status, parse_konfidenz "
                "FROM dokumente "
                "WHERE akte_id = ? AND ("
                "  dokumentenklasse LIKE 'rechnung%'"
                "  OR dokumentenklasse = 'standkostenrechnung'"
                "  OR dokumentenklasse = 'gutachten'"
                "  OR dokumentenklasse = 'sv_rechnung'"
                "  OR dokumentenklasse = 'abrechnungsschreiben'"
                ")",
                (akte_id,),
            ).fetchall()

            # Bereits importierte E-Akte-Nummern (um Duplikate zu vermeiden)
            importierte = conn.execute(
                "SELECT eakte_nr FROM dokumente WHERE akte_id = ? AND eakte_nr IS NOT NULL",
                (akte_id,),
            ).fetchall()

        # ── RA-Micro-Fallback: fehlende Rollen ergaenzen ─────────────────────
        # Wenn SQLite keine sachverstaendiger-Rolle hat, aus RA-Micro nachladen.
        vorhandene_rollen = {b["rolle"] for b in beteiligte}
        if "sachverstaendiger" not in vorhandene_rollen:
            ra_beteiligte = _lade_beteiligte_alle_ramicro(akte_id)
            for rb in ra_beteiligte:
                if rb["rolle"] not in vorhandene_rollen:
                    beteiligte.append(rb)
                    vorhandene_rollen.add(rb["rolle"])
    except Exception as e:
        logger.error("Kandidaten laden fehlgeschlagen: %s", e)
        return _err("Kandidaten laden fehlgeschlagen: %s" % e, 500)

    importierte_nrs = {r["eakte_nr"] for r in importierte}
    kandidaten_liste = []
    lokal_geprueft = len(lokale_rows)
    eakte_geprueft = 0
    eakte_verfuegbar = False
    auto_importiert = 0   # Zählt in diesem Aufruf neu importierte E-Akte-Dokumente
    uebersprungen_nach_kategorie = {}   # Grund → Anzahl

    # ── Stufe 0: Lokale Dokumente auswerten ──────────────────────────────────
    for dok in lokale_rows:
        klasse = dok["dokumentenklasse"] or ""
        dok_id = dok["id"]
        dateiname = dok["dateiname"] or ""

        # ── Abrechnungsschreiben: Gesamt-Referenzdokument, keine Einzelposition ─
        if klasse == "abrechnungsschreiben":
            kandidaten_liste.append({
                "position_key":    None,
                "konfidenz":       0.85,
                "grund":           "klasse_abrechnungsschreiben",
                "quelle":          "lokal",
                "dok_id":          dok_id,
                "eakte_nr":        None,
                "dateiname":       dateiname,
                "betrag_vorschlag": None,
                "betrag_ist_netto": True,
                "lieferant":       None,
            })
            continue

        # ── Gutachten: liefert Fahrzeugschaden-Positionen (4 Kandidaten) ──────
        if klasse == "gutachten":
            # Beträge aus parse_json.schadenpositionen (Gutachten-Parser)
            gut_betraege = {}
            if dok["parse_status"] == "erfolgreich" and dok["parse_json"]:
                try:
                    pj = _json.loads(dok["parse_json"])
                    sp = pj.get("schadenpositionen") or {}
                    rep = sp.get("reparaturkosten") or sp.get("rep_gutachten_netto")
                    if rep:          gut_betraege["rep_gutachten_netto"] = rep
                    wbw = sp.get("wiederbeschaffung")
                    if wbw:          gut_betraege["wiederbeschaffung"]   = wbw
                    rw  = sp.get("restwert")
                    if rw is not None: gut_betraege["restwert"]          = rw
                    wm  = sp.get("wertminderung")
                    if wm is not None: gut_betraege["wertminderung"]     = wm
                except Exception:
                    pass

            for pos_key in ("rep_gutachten_netto", "wiederbeschaffung",
                            "restwert", "wertminderung"):
                kandidaten_liste.append({
                    "position_key":    pos_key,
                    "konfidenz":       0.88,
                    "grund":           "klasse_gutachten",
                    "quelle":          "lokal",
                    "dok_id":          dok_id,
                    "eakte_nr":        None,
                    "dateiname":       dateiname,
                    "betrag_vorschlag": gut_betraege.get(pos_key),
                    "betrag_ist_netto": True,
                    "lieferant":       None,
                })
            continue  # kein generischer Eintrag weiter unten

        # ── SV-Honorarrechnung: einzige Quelle für sv_kosten ─────────────────
        if klasse == "sv_rechnung":
            pos_key = "sv_kosten_netto" if vorsteuer else "sv_kosten"
            konfidenz = 0.93
            grund = "klasse_sv_rechnung"
        else:
            pos_key = _KLASSE_POSITION_MAP.get(klasse)
            if pos_key == "__sv_kosten_vorsteuer__":
                pos_key = "sv_kosten_netto" if vorsteuer else "sv_kosten"
            konfidenz = 0.85 if pos_key else 0.50
            grund = ("klasse_" + klasse) if pos_key else "klasse_rechnung_generisch"

        # Betrag aus parse_json (Rechnungs-Parser: nettobetrag / bruttobetrag)
        # Vorsteuer-Logik: nicht-VSt-berechtigter Mandant → Bruttobetrag verwenden
        betrag = None
        ist_netto = True
        if dok["parse_status"] == "erfolgreich" and dok["parse_json"]:
            try:
                pj = _json.loads(dok["parse_json"])
                netto = pj.get("nettobetrag")
                brutto = pj.get("bruttobetrag")
                if vorsteuer:
                    # VSt-berechtigt → Nettobetrag (MwSt wird separat abgezogen)
                    if netto is not None:
                        betrag, ist_netto = netto, True
                    elif brutto is not None:
                        betrag, ist_netto = brutto, False
                else:
                    # Nicht VSt-berechtigt → Bruttobetrag (inkl. MwSt ist der Schaden)
                    if brutto is not None:
                        betrag, ist_netto = brutto, False
                    elif netto is not None:
                        betrag, ist_netto = netto, True
            except Exception:
                pass

        kandidaten_liste.append({
            "position_key": pos_key,
            "konfidenz": konfidenz,
            "grund": grund,
            "quelle": "lokal",
            "dok_id": dok_id,
            "eakte_nr": None,
            "dateiname": dateiname,
            "betrag_vorschlag": betrag,
            "betrag_ist_netto": ist_netto,
            "lieferant": None,
        })

    # ── Stufe 1: E-Akte (graceful degradation bei Mount-Fehler) ──────────────

    # rechnung_parse_cache laden fuer Betrag-Vorschlaege aus E-Akte-Dokumenten
    eakte_cache = {}
    try:
        with get_connection() as conn:
            cache_rows = conn.execute(
                "SELECT eakte_nr, ergebnis_json FROM rechnung_parse_cache"
            ).fetchall()
            for cr in cache_rows:
                try:
                    eakte_cache[cr["eakte_nr"]] = _json.loads(cr["ergebnis_json"])
                except Exception:
                    pass
    except Exception:
        # Tabelle existiert noch nicht (vor Migration 29) → kein Fehler
        pass

    try:
        from ..ramicro.eakte_service import hole_eakte_dokumente
        eakte_docs = hole_eakte_dokumente(az=akte_id, nur_pdf=True)
        eakte_geprueft = len(eakte_docs)
        eakte_verfuegbar = True

        eakte_base_path = _os.environ.get("EAKTE_BASE_PATH", "")
        benutzer_id = getattr(g, "benutzer_id", None)

        for dok in eakte_docs:
            nr = dok.get("nr")
            if nr in importierte_nrs:
                continue  # Bereits lokal importiert

            # ── Whitelist-Filter: irrelevante Kategorien überspringen ─────────
            skip_grund = _eakte_dok_uberspringen(dok)
            if skip_grund:
                uebersprungen_nach_kategorie[skip_grund] = (
                    uebersprungen_nach_kategorie.get(skip_grund, 0) + 1
                )
                logger.debug(
                    "E-Akte nr=%d übersprungen [%s] (rubrik=%r, empf=%r)",
                    nr, skip_grund, dok.get("rubrik", ""),
                    (dok.get("empfaenger") or "")[:60],
                )
                continue

            treffer_liste = _klassifiziere_eakte_dok(dok, beteiligte, vorsteuer)
            if not treffer_liste:
                continue

            # ── Gutachten + SV-Rechnung: PDF auto-importieren und parsen ─────────
            # Positionen liegen erst vor, nachdem das PDF geparst wurde.
            # Wenn EAKTE_BASE_PATH konfiguriert und Datei erreichbar: direkt importieren.
            gut_betraege = {}    # befüllt wenn Auto-Import (Gutachten) erfolgreich
            auto_dok_id = None   # gesetzt wenn lokal registriert wurde
            # Konfidenz >= 0.85: verhindert Import von SV-Korrespondenz/E-Mails
            # (domain_match_sv_unklar hat nur 0.72)
            hat_gutachten_pos = any(
                t.get("position_key") in (
                    "rep_gutachten_netto", "wiederbeschaffung",
                    "restwert", "wertminderung",
                ) and (t.get("konfidenz") or 0) >= 0.85
                for t in treffer_liste
            )
            hat_sv_rechnung_pos = any(
                t.get("position_key") in ("sv_kosten", "sv_kosten_netto")
                and (t.get("konfidenz") or 0) >= 0.85
                for t in treffer_liste
            )
            if (hat_gutachten_pos or hat_sv_rechnung_pos) and eakte_base_path:
                try:
                    import hashlib as _hashlib
                    from ..ramicro.eakte_service import baue_dateipfad
                    from ..models.dokument import registriere_dokument
                    from ..workflow.dispatcher import dispatch_dokument
                    pfad = baue_dateipfad(dok.get("dateiname") or "")
                    if pfad and _os.path.exists(pfad):
                        # ── Hash-basierte Duplikat-Prüfung ─────────────────
                        # RA-MICRO kann dieselbe Datei unter verschiedenen
                        # eakte_nr-Einträgen führen – eakte_nr-Dedup reicht
                        # dafür nicht aus. SHA-256 des Datei-Inhalts ist eindeutig.
                        with open(pfad, "rb") as _fh:
                            _datei_bytes = _fh.read()
                        _pdf_hash = _hashlib.sha256(_datei_bytes).hexdigest()
                        with get_connection() as conn:
                            _dup = conn.execute(
                                "SELECT id, dateiname FROM dokumente "
                                "WHERE akte_id=? AND pdf_hash=?",
                                (akte_id, _pdf_hash),
                            ).fetchone()
                        if _dup:
                            logger.info(
                                "E-Akte nr=%d: Hash-Duplikat von dok_id=%d (%s) – Import übersprungen",
                                nr, _dup["id"], _dup["dateiname"],
                            )
                            importierte_nrs.add(nr)
                            continue  # Nächstes E-Akte-Dokument
                        dateigroesse = len(_datei_bytes)
                        db_dok = registriere_dokument(
                            akte_id=akte_id,
                            typ="sonstiges",
                            dateiname=(
                                dok.get("bemerkung") or dok.get("orgdatei")
                                or dok.get("anzeigename")
                                or ("eakte_%d.pdf" % nr)
                            ),
                            dateipfad=pfad,
                            bearbeiter_id=benutzer_id,
                            dateityp="pdf",
                            dateigroesse=dateigroesse,
                        )
                        with get_connection() as conn:
                            conn.execute(
                                "UPDATE dokumente SET eakte_nr=?, eakte_pfad=?, quelle='eakte' "
                                "WHERE id=?",
                                (nr, dok.get("dateiname"), db_dok.id),
                            )
                            conn.commit()
                        importierte_nrs.add(nr)
                        auto_dok_id = db_dok.id
                        auto_importiert += 1

                        # Dispatch-Pipeline (Text + Klassifikation + Parser)
                        from ..workflow.dispatcher import (
                            dispatch_dokument, korrigiere_klassifikation,
                        )
                        dispatch_res = dispatch_dokument(
                            dok_id=auto_dok_id,
                            akte_az=akte_id,
                            dateipfad=pfad,
                            benutzer_id=benutzer_id,
                        )
                        # Falls Dispatcher nicht "gutachten" erkannt hat (z.B. wegen
                        # Mietwagenkosten-Erwähnung im Text): Klasse korrigieren + neu parsen.
                        # korrigiere_klassifikation liest den Text erneut und ruft den
                        # Gutachten-Parser mit korrektem meta (inkl. pruefdienstleister) auf.
                        _klasse = dispatch_res.get("klasse")

                        if hat_gutachten_pos:
                            if _klasse != "gutachten":
                                logger.info(
                                    "E-Akte Gutachten %d: Dispatcher erkannte '%s' → korrigiere zu gutachten",
                                    nr, _klasse,
                                )
                                korr = korrigiere_klassifikation(
                                    dok_id=auto_dok_id,
                                    akte_az=akte_id,
                                    neue_klasse="gutachten",
                                    benutzer_id=benutzer_id,
                                )
                                _sp = (korr.get("parse_ergebnis") or {}).get("schadenpositionen") or {}
                            else:
                                _sp = (dispatch_res.get("parse_ergebnis") or {}).get("schadenpositionen") or {}
                            rep = _sp.get("reparaturkosten") or _sp.get("rep_gutachten_netto")
                            if rep: gut_betraege["rep_gutachten_netto"] = rep
                            wbw = _sp.get("wiederbeschaffung")
                            if wbw: gut_betraege["wiederbeschaffung"] = wbw
                            rw = _sp.get("restwert")
                            if rw is not None: gut_betraege["restwert"] = rw
                            wm = _sp.get("wertminderung")
                            if wm is not None: gut_betraege["wertminderung"] = wm
                            logger.info(
                                "E-Akte Gutachten %d auto-importiert: dok_id=%d klasse=%s betraege=%s",
                                nr, auto_dok_id, _klasse, list(gut_betraege.keys()),
                            )

                        elif hat_sv_rechnung_pos and _klasse in ("rechnung", "sv_rechnung"):
                            # SV-Rechnung: Betrag aus parse_json extrahieren
                            # und in-memory eakte_cache aktualisieren damit der
                            # Betrag-Lookup weiter unten im gleichen Aufruf greift.
                            _pr = dispatch_res.get("parse_ergebnis") or {}
                            _netto = _pr.get("nettobetrag")
                            _brutto = _pr.get("bruttobetrag")
                            eakte_cache[nr] = {
                                "nettobetrag": _netto,
                                "bruttobetrag": _brutto,
                            }
                            logger.info(
                                "E-Akte SV-Rechnung %d auto-importiert: dok_id=%d netto=%s brutto=%s",
                                nr, auto_dok_id, _netto, _brutto,
                            )
                        else:
                            logger.info(
                                "E-Akte %d auto-importiert (klasse=%s) – kein Betrag extrahiert",
                                nr, _klasse,
                            )
                except Exception as _auto_e:
                    logger.warning(
                        "Auto-Import E-Akte nr=%s fehlgeschlagen: %s", nr, _auto_e
                    )

            # Betrag aus Cache (nur für Rechnungen sinnvoll)
            cached = eakte_cache.get(nr) or {}
            cached_netto  = cached.get("nettobetrag")
            cached_brutto = cached.get("bruttobetrag")

            for treffer in treffer_liste:
                pos_key = treffer["position_key"]
                # Gutachten-Beträge aus Auto-Import; Rechnungsbeträge aus Cache
                ist_gutachten_pos = pos_key in (
                    "rep_gutachten_netto", "wiederbeschaffung",
                    "restwert", "wertminderung",
                )
                ist_rechnung_pos = pos_key in (
                    "sv_kosten", "sv_kosten_netto",
                    "rep_rechnung_netto", "mietwagenkosten_netto",
                    "abschleppkosten", "standkosten",
                ) or pos_key is None

                if ist_gutachten_pos:
                    betrag_vorschlag = gut_betraege.get(pos_key)
                    betrag_ist_netto = True
                elif ist_rechnung_pos:
                    if vorsteuer:
                        if cached_netto is not None:
                            betrag_vorschlag, betrag_ist_netto = cached_netto, True
                        elif cached_brutto is not None:
                            betrag_vorschlag, betrag_ist_netto = cached_brutto, False
                        else:
                            betrag_vorschlag, betrag_ist_netto = None, True
                    else:
                        if cached_brutto is not None:
                            betrag_vorschlag, betrag_ist_netto = cached_brutto, False
                        elif cached_netto is not None:
                            betrag_vorschlag, betrag_ist_netto = cached_netto, True
                        else:
                            betrag_vorschlag, betrag_ist_netto = None, True
                else:
                    betrag_vorschlag = None
                    betrag_ist_netto = True

                kandidaten_liste.append({
                    "position_key":    pos_key,
                    "konfidenz":       treffer["konfidenz"],
                    "grund":           treffer["grund"],
                    "quelle":          "lokal" if auto_dok_id else "eakte",
                    "dok_id":          auto_dok_id,
                    "eakte_nr":        nr,
                    "dateiname":       dok.get("bemerkung") or dok.get("orgdatei") or dok.get("anzeigename") or "",
                    "betrag_vorschlag": betrag_vorschlag,
                    "betrag_ist_netto": betrag_ist_netto,
                    "lieferant":       treffer.get("lieferant"),
                    # E-Akte-Metadaten für Debug-Dialog
                    "domain":          dok.get("absender_domain") or "",
                    "rubrik":          dok.get("rubrik") or "",
                    "einf_datum":      dok.get("einf_datum") or "",
                    "routing_basis":   _routing_basis_eakte_dok(dok),
                })

    except (ImportError, RuntimeError, ValueError):
        # RAMICRO nicht verfuegbar oder Mount nicht aktiv → kein Fehler
        pass
    except Exception as e:
        logger.warning("E-Akte Kandidaten fehlgeschlagen (nicht kritisch): %s", e)

    # ── E-Akte-Duplikat-Bereinigung ───────────────────────────────────────────
    # RA-MICRO speichert dasselbe Dokument manchmal mehrfach mit leicht
    # unterschiedlichen Namen (z.B. "gut.pdf", "gut.pdf.pdf", "gut.pdf.pdf.pdf").
    # Deduplizierung: je (position_key, normalisierter_name) nur bester Eintrag.
    def _norm_dateiname(name):
        # Mehrfach-Erweiterungen entfernen: "foo.pdf.pdf.pdf" → "foo.pdf"
        while name.lower().endswith(".pdf.pdf") or name.lower().endswith(".docx.docx"):
            name = name[:name.rfind(".", 0, len(name) - 4)]
        return name.lower().strip()

    eakte_seen = {}   # (position_key, norm_name) → index in kandidaten_liste
    bereinigt = []
    for k in kandidaten_liste:
        if k.get("quelle") != "eakte":
            bereinigt.append(k)
            continue
        key = (k.get("position_key"), _norm_dateiname(k.get("dateiname") or ""))
        if key not in eakte_seen:
            eakte_seen[key] = len(bereinigt)
            bereinigt.append(k)
        else:
            # Schon vorhanden: nur ersetzen wenn bessere Konfidenz oder Betrag vorhanden
            idx = eakte_seen[key]
            vorh = bereinigt[idx]
            if (k.get("konfidenz") or 0) > (vorh.get("konfidenz") or 0):
                bereinigt[idx] = k
            elif k.get("betrag_vorschlag") is not None and vorh.get("betrag_vorschlag") is None:
                bereinigt[idx] = k
    kandidaten_liste = bereinigt

    return _j({
        "kandidaten":       kandidaten_liste,
        "lokal_geprueft":               lokal_geprueft,
        "eakte_geprueft":               eakte_geprueft,
        "eakte_verfuegbar":             eakte_verfuegbar,
        "auto_importiert":              auto_importiert,
        "uebersprungen_nach_kategorie": uebersprungen_nach_kategorie,
    })


@belege_bp.route("/neu-parsen", methods=["POST"])
@login_erforderlich
def neu_parsen(akte_id):
    """
    POST /akten/<az>/belege/neu-parsen
    Parst alle lokalen Dokumente der Akte neu und aktualisiert parse_json in der DB.
    Wird vom Frontend nach Parser-Fixes aufgerufen, damit gecachte Werte refresht werden.
    """
    try:
        from ..workflow.dispatcher import dispatch_dokument
    except ImportError as e:
        return _err("Dispatcher nicht verfuegbar: %s" % e, 500)

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT id, dateipfad, dokumentenklasse "
                "FROM dokumente "
                "WHERE akte_id = ? AND dateipfad IS NOT NULL AND dateipfad != '' AND ("
                "  dokumentenklasse LIKE 'rechnung%'"
                "  OR dokumentenklasse = 'standkostenrechnung'"
                "  OR dokumentenklasse = 'gutachten'"
                "  OR dokumentenklasse = 'sv_rechnung'"
                "  OR dokumentenklasse = 'abrechnungsschreiben'"
                ")",
                (akte_id,),
            ).fetchall()
    except Exception as e:
        return _err("DB-Fehler: %s" % e, 500)

    neu_geparsed = 0
    fehler_liste = []
    benutzer_id = getattr(g, "benutzer_id", None)

    for row in rows:
        dok_id   = row["id"]
        pfad     = row["dateipfad"]
        if not _os.path.exists(pfad):
            fehler_liste.append("Datei nicht gefunden: %s" % pfad)
            continue
        try:
            dispatch_dokument(
                dok_id=dok_id,
                akte_az=akte_id,
                dateipfad=pfad,
                benutzer_id=benutzer_id,
            )
            neu_geparsed += 1
        except Exception as e:
            fehler_liste.append("Dok %d: %s" % (dok_id, e))
            logger.warning("neu-parsen Dok %d fehlgeschlagen: %s", dok_id, e)

    return jsonify({
        "neu_geparsed": neu_geparsed,
        "gesamt":       len(rows),
        "fehler":       fehler_liste,
    })
