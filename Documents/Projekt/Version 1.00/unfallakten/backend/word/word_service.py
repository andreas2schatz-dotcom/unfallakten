"""
Modul 5 – Word-Service
========================
Orchestriert die Word-Generierung:
  1. Aktendaten aus der Datenbank laden
  2. Richtigen Generator aufrufen
  3. Dokument in DB als "generiertes Dokument" registrieren
  4. Bytes zurückgeben

Unterstützte Dokumenttypen:
  forderungsschreiben   → Forderung an Versicherer
  sachstandsanfrage     → Nachfrage bei Versicherer
  abrechnungsuebersicht → Übersicht für Mandanten
"""

import os
import io
import uuid
import logging
from pathlib import Path
from typing import Optional

from ..models.akte import hole_akte_by_id
from ..services.fristen_service import setze_pflvg_frist, setze_antwort_frist
from ..models.schaden import (
    hole_beteiligte_by_akte, hole_schadenpositionen,
    hole_regulierungen_by_akte
)
from ..models.abrechnungsschreiben import hole_abrechnungsschreiben_by_akte
from ..models.dokument import registriere_dokument
from ..models.forderung import erfasse_forderung

from .forderungsschreiben_wv import (
    generiere_forderungsschreiben_wv, hat_schadensdaten, dateiendung as forderung_ext
)
from .sachstandsanfrage import generiere_sachstandsanfrage
from .abrechnungsuebersicht_service import generiere_abrechnungsuebersicht
from .klage_service import generiere_klageschrift

logger = logging.getLogger(__name__)

# ── Kanzlei-Stammdaten (konfigurierbar per Umgebungsvariable) ─────────────────

KANZLEI_INFO = {
    "name":    os.environ.get("KANZLEI_NAME",    "Rechtsanwaltskanzlei Koch, Schatz & Kollegen"),
    "strasse": os.environ.get("KANZLEI_STRASSE", "Frankfurter Straße 12"),
    "ort":     os.environ.get("KANZLEI_ORT",     "63065 Offenbach am Main"),
    "telefon": os.environ.get("KANZLEI_TEL",     "069 / 83 10 99 - 0"),
    "fax":     os.environ.get("KANZLEI_FAX",     "069 / 83 10 99 - 99"),
    "email":   os.environ.get("KANZLEI_EMAIL",   "info@anwalt-offenbach.de"),
    "web":     os.environ.get("KANZLEI_WEB",     "www.anwalt-offenbach.de"),
}

GUELTIGE_DOK_TYPEN = {
    "forderungsschreiben",
    "sachstandsanfrage",
    "abrechnungsuebersicht",
    "klage",          # Stub – Vorlage folgt
}


class WordFehler(Exception):
    def __init__(self, nachricht: str, status_code: int = 422):
        self.nachricht = nachricht
        self.status_code = status_code
        super().__init__(nachricht)


def _upload_verzeichnis() -> Path:
    default = Path(__file__).parent.parent / "uploads"
    pfad = Path(os.environ.get("UPLOAD_DIR", str(default)))
    pfad.mkdir(parents=True, exist_ok=True)
    return pfad


def generiere_und_speichere(
    akte_id:      int,
    dok_typ:      str,
    bearbeiter_id: Optional[int] = None,
    in_db:        bool = True,
    variante:     str  = "hoehe",
    adressat_id:  Optional[int] = None,
) -> dict:
    """
    Generiert ein Word-Dokument für eine Akte.

    Args:
        akte_id:      Ziel-Akte
        dok_typ:      'forderungsschreiben' | 'sachstandsanfrage' |
                      'abrechnungsuebersicht' | 'klage'
        bearbeiter_id: Wer das Dokument generiert
        in_db:        True → Dokument in DB als Eintrag speichern
        variante:     Für forderungsschreiben: 'hoehe' | 'grunde'
                      'hoehe'  → Forderungsschreiben der Höhe nach (DOCX-Vorlage)
                      'grunde' → Forderungsschreiben dem Grunde nach (RTF-Vorlage)

    Returns:
        {
          "bytes":     <Dokument-Bytes>,
          "dateiname": "42-25_forderungsschreiben.docx",
          "dokument":  { DB-Eintrag } oder None,
          "variante":  "hoehe" | "grunde" | None,
        }

    Raises:
        WordFehler bei ungültiger Akte oder unbekanntem Typ
    """
    if dok_typ not in GUELTIGE_DOK_TYPEN:
        raise WordFehler(
            f"Unbekannter Dokumenttyp '{dok_typ}'. "
            f"Erlaubt: {', '.join(sorted(GUELTIGE_DOK_TYPEN))}"
        )

    akte = hole_akte_by_id(akte_id)
    if not akte:
        raise WordFehler(f"Akte {akte_id} nicht gefunden.", 404)

    # ── Daten aus DB laden + Quellenprüfung ──────────────────────────────────
    akte_daten = _lade_akte_daten(akte_id, akte, dok_typ=dok_typ, variante=variante)

    # variante kommt aus _lade_akte_daten() — für alle anderen Dokumenttypen None
    # bereits korrekt bestimmt — für alle anderen Dokumenttypen None/unverändert
    tatsaechliche_variante = akte_daten.get("variante", variante)

    # ── Generator aufrufen ────────────────────────────────────────────────────
    def _forderung(ad): return generiere_forderungsschreiben_wv(ad, tatsaechliche_variante)

    generator_map = {
        "forderungsschreiben":   _forderung,
        "sachstandsanfrage":     generiere_sachstandsanfrage,
        "abrechnungsuebersicht": generiere_abrechnungsuebersicht,
        "klage":                 generiere_klageschrift,
    }
    generator = generator_map[dok_typ]

    try:
        doc_bytes = generator(akte_daten)
    except Exception as e:
        logger.error("Word-Generierung fehlgeschlagen (%s): %s", dok_typ, e)
        raise WordFehler(f"Fehler beim Erstellen des Dokuments: {e}", 500)

    az_clean = akte.aktenzeichen.replace("/", "-").replace(" ", "_")
    if dok_typ == "forderungsschreiben":
        ext       = forderung_ext(tatsaechliche_variante)
        suffix    = f"forderungsschreiben_{tatsaechliche_variante}"
        dateiname = f"{az_clean}_{suffix}.{ext}"
    else:
        dateiname = f"{az_clean}_{dok_typ}.docx"

    # ── Auf Disk speichern + DB-Eintrag ──────────────────────────────────────
    dok_eintrag = None
    if in_db:
        upload_dir = _upload_verzeichnis()
        pfad = upload_dir / f"{uuid.uuid4().hex}_{dateiname}"
        pfad.write_bytes(doc_bytes)

        # DB-Typ: 'forderungsschreiben' oder 'sonstiges' für die anderen
        db_typ = dok_typ if dok_typ in ("forderungsschreiben", "klage") else "sonstiges"
        try:
            dok = registriere_dokument(
                akte_id=akte_id,
                typ=db_typ,
                dateiname=dateiname,
                dateipfad=str(pfad),
                bearbeiter_id=bearbeiter_id,
                dateityp=dateiname.rsplit(".", 1)[-1] if "." in dateiname else "docx",
                dateigroesse=len(doc_bytes),
            )
            dok_eintrag = {
                "id":           dok.id,
                "dateiname":    dok.dateiname,
                "dateityp":     dok.dateityp,
                "dateigroesse": dok.dateigroesse,
                "hochgeladen_am": dok.hochgeladen_am,
            }
        except Exception as e:
            logger.warning("DB-Registrierung fehlgeschlagen: %s", e)
            dok = None

        # ── Forderungshistorie automatisch anlegen ────────────────────────
        # Nur für Forderungsschreiben der Höhe nach — dem Grunde nach hat
        # keine bezifferten Positionen die zu tracken wären.
        if dok_typ == "forderungsschreiben" and tatsaechliche_variante == "hoehe":
            schaden_fuer_forderung = akte_daten.get("schaden") or {}
            try:
                erfasse_forderung(
                    akte_id      = akte_id,
                    schaden      = schaden_fuer_forderung,
                    dokument_id  = dok.id if dok else None,
                    bearbeiter_id = bearbeiter_id,
                )
            except Exception as e:
                logger.warning("Forderungshistorie konnte nicht angelegt werden: %s", e)

    # ── Automatische Fristen anlegen (PRD-25a) ────────────────────────────────
    if in_db and dok and dok.id:
        try:
            if dok_typ == "forderungsschreiben":
                setze_pflvg_frist(akte_id)
            setze_antwort_frist(akte_id, dok.id, dok_typ)
        except Exception as e:
            logger.warning("fristen_service: Fristen konnten nicht angelegt werden: %s", e)

    logger.info(
        "Word-Dokument generiert: %s für Akte %s (%d Bytes)",
        dok_typ, akte.aktenzeichen, len(doc_bytes)
    )

    return {
        "bytes":     doc_bytes,
        "dateiname": dateiname,
        "dokument":  dok_eintrag,
        "variante":  tatsaechliche_variante if dok_typ == "forderungsschreiben" else None,
    }


def _lade_akte_daten(akte_id: int, akte, dok_typ: str = "", variante: str = "auto", adressat_id: Optional[int] = None) -> dict:
    """
    Lädt alle relevanten Daten einer Akte für die Dokumentgenerierung.

    Für Forderungsschreiben wird zusätzlich die Quellenprüfung durchgeführt:
      1. SQLite-Schaden vorhanden?  → variante="hoehe"
      2. SQLite leer                → variante="grunde"
      Kontrollvariablen (Flags, Grammatik) werden immer aus WDM geladen.

    Das Ergebnis-Dict enthält zusätzlich:
      wdm_kontroll:  dict  – WDM-Kontrollvariablen (Flags, Grammatik, Personenschaden)
      variante:      str   – "hoehe" | "grunde" (nur für Forderungsschreiben)
      mandant_anrede: str  – sAnrede des Mandanten für Grammatik-Vars
    """
    # Nach Migration 5 ist beteiligte.akte_id TEXT (= Aktenzeichen), kein Integer mehr.
    # Daher immer akte.aktenzeichen verwenden, nie die numerische akte_id.
    az = akte.aktenzeichen
    beteiligte    = hole_beteiligte_by_akte(az)
    schaden       = hole_schadenpositionen(az)
    regulierungen = hole_regulierungen_by_akte(az)

    # v8: Abrechnungsübersicht lädt Abrechnungen inkl. Positionen
    abrechnungen_v8 = []
    if dok_typ == "abrechnungsuebersicht":
        try:
            abrechnungen_raw = hole_abrechnungsschreiben_by_akte(az)
            for ab in abrechnungen_raw:
                # as_dict() enthält bereits positionen mit position_key + betrag_reguliert
                ab_dict = ab.as_dict() if hasattr(ab, "as_dict") else {}
                g_gef = float(getattr(ab, "gesamt_gefordert", 0) or 0)
                g_reg = float(getattr(ab, "gesamt_reguliert", 0) or 0)
                g_kue = float(getattr(ab, "gesamt_kuerzung",  0) or 0)
                abrechnungen_v8.append({
                    "id":               ab.id,
                    "datum":            ab.datum,
                    "versicherung":     ab.versicherung or "",
                    "gesamt_gefordert": g_gef,
                    "gesamt_reguliert": g_reg,
                    "gesamt_kuerzung":  g_kue,
                    "quelle":           getattr(ab, "quelle", "pdf") or "pdf",
                    "haftungsart":      getattr(ab, "haftungsart", "vollhaftung") or "vollhaftung",
                    "haftungsquote":    float(getattr(ab, "haftungsquote", 100) or 100),
                    # Positionen mit position_key + betrag_reguliert für posMap
                    "positionen":       ab_dict.get("positionen", []),
                })
        except Exception as _e:
            logger.warning("Abrechnungsschreiben für Übersicht nicht ladbar: %s", _e)

    mandant = next((b for b in beteiligte if b.rolle == "mandant"), None)
    # Adressat: explizit gewählter Beteiligter (Dropdown) oder erster Gegner
    if adressat_id:
        gegner = next((b for b in beteiligte if b.id == adressat_id), None)
    if not adressat_id or gegner is None:
        # Fallback: GHPV-Beteiligter (kz="GHPV"/"GHV") oder erster Gegner
        ghpv = next((b for b in beteiligte
                     if getattr(b, "kuerzel", "").upper() in ("GHPV", "GH", "GHV", "GBEV")), None)
        gegner = ghpv or next((b for b in beteiligte if b.rolle == "gegner"), None)

    # ── Beteiligter → Dict (erweitertes Mapping inkl. Migration-8-Felder) ────
    def b_dict(b):
        if not b:
            return None
        return {
            "id": b.id, "rolle": b.rolle, "name": b.name,
            "vorname": b.vorname, "firma": b.firma,
            "anschrift": b.anschrift, "plz": b.plz, "ort": b.ort,
            "telefon": b.telefon, "email": b.email,
            "kfz_kennzeichen": b.kfz_kennzeichen, "kfz_typ": b.kfz_typ,
            "versicherung": b.versicherung, "vers_nr": b.vers_nr,
            "schaden_nr": b.schaden_nr, "iban": b.iban,
            "anrede":    getattr(b, "anrede",    "") or "",
            "vorsteuer": getattr(b, "vorsteuer", "N") or "N",
        }

    # ── Schaden → Dict (inkl. Migration-6/8-Felder) ─────────────────────────
    def s_dict(s):
        if not s:
            return None
        return {
            "reparaturkosten":   s.reparaturkosten,
            "wiederbeschaffung": s.wiederbeschaffung,
            "restwert":          s.restwert,
            "wertminderung":     s.wertminderung,
            "nutzungsausfall":   s.nutzungsausfall,
            "mietwagenkosten":   s.mietwagenkosten,
            "sv_kosten":         s.sv_kosten,
            "abschleppkosten":   s.abschleppkosten,
            "standkosten":       s.standkosten,
            "anabmeldekosten":   s.anabmeldekosten,
            "schmerzensgeld":    s.schmerzensgeld,
            "sonstiges":         s.sonstiges,
            "sonstiges_beschr":  s.sonstiges_beschr,
            "gesamt_brutto":     s.gesamt_brutto,
            "quelle":            s.quelle,
            "verdienstausfall":    getattr(s, "verdienstausfall",    0.0),
            "haushalt":            getattr(s, "haushalt",            0.0),
            "rep_gutachten_netto": getattr(s, "rep_gutachten_netto", 0.0),
            "rep_gutachten_mwst":  getattr(s, "rep_gutachten_mwst",  0.0),
            "unkostenpauschale":   getattr(s, "unkostenpauschale",   0.0),
            "wdm_extras_json":     getattr(s, "wdm_extras_json",    None),
            "wdm_info_json":       getattr(s, "wdm_info_json",     None),
            "kostennb":            getattr(s, "kostennb",            0.0),
            "kostennb_ust":        getattr(s, "kostennb_ust",        0.0),
            "rep_rechnung_netto":  getattr(s, "rep_rechnung_netto",  0.0),
            "rep_rechnung_brutto": getattr(s, "rep_rechnung_brutto", 0.0),
            "abrechnungsart":      getattr(s, "abrechnungsart",      None),
            # Netto/USt-Felder für _netto_oder_brutto (B-08)
            "sv_kosten_netto":         getattr(s, "sv_kosten_netto",         0.0),
            "sv_kosten_ust":           getattr(s, "sv_kosten_ust",           0.0),
            "mietwagenkosten_netto":   getattr(s, "mietwagenkosten_netto",   0.0),
            "mietwagenkosten_ust":     getattr(s, "mietwagenkosten_ust",     0.0),
            "abschleppkosten_netto":   getattr(s, "abschleppkosten_netto",   0.0),
            "abschleppkosten_ust":     getattr(s, "abschleppkosten_ust",     0.0),
            "standkosten_netto":       getattr(s, "standkosten_netto",       0.0),
            "standkosten_ust":         getattr(s, "standkosten_ust",         0.0),
            "anabmeldekosten_netto":   getattr(s, "anabmeldekosten_netto",   0.0),
            "anabmeldekosten_ust":     getattr(s, "anabmeldekosten_ust",     0.0),
        }

    def r_dict(r):
        return {
            "id": r.id, "datum": r.datum,
            "betrag_gefordert":  r.betrag_gefordert,
            "betrag_reguliert":  r.betrag_reguliert,
            "differenz":         r.differenz,
            "status":            r.status,
            "vers_referenz":     r.vers_referenz,
            "kuerz_begruendung": r.kuerz_begruendung,
        }

    schaden_dict = s_dict(schaden)
    mandant_dict = b_dict(mandant)
    gegner_dict  = b_dict(gegner)

    # ── Gegner-Adresse direkt aus RA-Micro (identische Logik wie Sachstandsanfrage) ──
    # Immer wenn Gegner keine vollständige Adresse hat → direkt auf SQL-Server
    if dok_typ in ("forderungsschreiben", "abrechnungsuebersicht"):
        _gegner_braucht_adresse = (
            gegner_dict is None or
            not (gegner_dict.get("anschrift") or gegner_dict.get("plz") or gegner_dict.get("ort"))
        )
        if _gegner_braucht_adresse:
            ra_g = _lade_gegner_adresse_aus_ramicro(akte.aktenzeichen)
            if ra_g:
                gegner_dict = ra_g
        # Mandant: RA-Micro ist primäre Quelle für Namen/Anrede/Anschrift — SQLite Fallback
        try:
            ra_alle = _lade_beteiligte_aus_ramicro(akte.aktenzeichen)
            ra_mandant = ra_alle.get("mandant")
            if ra_mandant:
                if mandant_dict is None:
                    mandant_dict = ra_mandant
                else:
                    # Namen, Anrede UND Adresse aus RA-Micro überschreiben
                    for feld in ("name", "vorname", "anrede", "briefanrede",
                                 "anschrift", "plz", "ort"):
                        if ra_mandant.get(feld):
                            mandant_dict[feld] = ra_mandant[feld]
                    if not mandant_dict.get("vorsteuer") or mandant_dict["vorsteuer"] == "N":
                        mandant_dict["vorsteuer"] = ra_mandant.get("vorsteuer", "N")
            elif mandant_dict is None:
                logger.debug("Mandant nicht in RA-Micro gefunden: %s", akte.aktenzeichen)
        except Exception as e:
            logger.debug("Mandant-Nachladen aus RA-Micro: %s", e)


    # Vorsteuer: WDM-Variable hat Vorrang vor SQLite-Feld
    # wdm_kontroll wird weiter unten geladen; hier nur als Fallback-Vorbelegung
    wdm_kontroll = {}
    if dok_typ == "forderungsschreiben" and mandant_dict:
        wdm_sstf = wdm_kontroll.get("varSSTF", "").strip().upper()
        if wdm_sstf in ("J", "JA", "Y", "1"):
            mandant_dict["vorsteuer"] = "Y"
        elif wdm_sstf in ("N", "NEIN", "0"):
            mandant_dict["vorsteuer"] = "N"
        # SQLite-Feld bleibt wenn WDM nichts liefert

    # ── Unfalldatum/Unfallort aus WDM wenn SQLite leer ───────────────────────
    akte_unfalldatum = akte.unfalldatum
    akte_unfallort   = akte.unfallort
    if dok_typ == "forderungsschreiben":
        try:
            wdm_extra = _lade_wdm_kontrollvars(akte.aktenzeichen)
            if not akte_unfalldatum:
                # varU-TAG enthält das Unfalldatum aus RA-Micro (z.B. "15.01.2026")
                u_tag = wdm_extra.get("varU-TAG") or wdm_extra.get("varu-tag") or ""
                if u_tag:
                    # DD.MM.YYYY → YYYY-MM-DD
                    import re as _re2
                    m = _re2.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", u_tag.strip())
                    if m:
                        d, mo, y = m.groups()
                        if len(y) == 2:
                            y = "20" + y
                        akte_unfalldatum = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
        except Exception:
            pass

    # ── Forderungsschreiben: Variante aus SQLite-Schaden ableiten ─────────────
    # Beträge kommen immer aus SQLite (bewusst gespeichert durch Sachbearbeiter).
    # WDM wird NUR für Kontrollvariablen (Flags, Grammatik, Personenschaden) genutzt.
    ermittelte_variante = variante

    if dok_typ == "forderungsschreiben":
        if variante == "grunde":
            ermittelte_variante = "grunde"
        else:
            # "hoehe" wenn Schaden erfasst, sonst "grunde"
            ermittelte_variante = "hoehe" if hat_schadensdaten(schaden_dict) else "grunde"
        # Kontrollvariablen immer aus WDM laden (unabhängig von Variante)
        wdm_kontroll = _lade_wdm_kontrollvars(akte.aktenzeichen)

    # ── Abrechnungsübersicht: Unfalldaten aus WDM laden ──────────────────────
    # varU-ORT, varU-TAG, varM-KZ, varG-KZ sind jetzt in KONTROLL_VARS →
    # einfach _lade_wdm_kontrollvars aufrufen und in wdm_kontroll mergen
    if dok_typ == "abrechnungsuebersicht":
        try:
            wdm_kontroll = _lade_wdm_kontrollvars(az)
        except Exception as _e2:
            logger.debug("WDM für Abrechnungsübersicht: %s", _e2)

    return {
        "akte": {
            "id":           akte.id,
            "aktenzeichen": akte.aktenzeichen,
            "unfalldatum":  akte_unfalldatum,
            "unfallort":    akte_unfallort,
            "status":       akte.status,
            "haftungsquote": akte.haftungsquote,
            "notizen":      akte.notizen,
            "sachbearbeiter": getattr(akte, "sachbearbeiter", "") or "",
            "kurzbezeichnung": getattr(akte, "kurzbezeichnung", "") or "",
        },
        "mandant":          mandant_dict,
        "gegner":           gegner_dict,
        "schaden":          schaden_dict,
        "regulierungen":    [r_dict(r) for r in regulierungen],
        "abrechnungen":     abrechnungen_v8,          # v8: für Abrechnungsübersicht
        "kanzlei":          KANZLEI_INFO,
        # Forderungsschreiben-spezifisch
        "wdm_roh":          wdm_kontroll,   # Kontrollvars aus WDM (Flags, Grammatik)
        "variante":         ermittelte_variante,
        "mandant_anrede":   (mandant_dict or {}).get("anrede", ""),
        # PRD-29: personenschaden für Schmerzensgeld-Textbaustein
        "personenschaden":  _lade_personenschaden(az),
    }


def _lade_personenschaden(az: str) -> dict:
    """Lädt personenschaden-Daten aus SQLite (PRD-29)."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM personenschaden WHERE akte_id = ?", (az,)
            ).fetchone()
            return dict(row) if row else {}
    except Exception:
        return {}


def _lade_beteiligte_aus_ramicro(az: str) -> dict:
    """
    Lädt Mandant und Gegner direkt aus RA-Micro.

    Fallback wenn Beteiligte nicht in SQLite erfasst sind.
    Gibt {"mandant": dict|None, "gegner": dict|None, "alle_gegner": list} zurück.
    "gegner" ist der erste/höchst-priorisierte Gegner (GHPV-Rang 0 für Briefe).
    "alle_gegner" enthält alle klassifizierten Gegner-Einträge (für Klagewizard).
    """
    result = {"mandant": None, "gegner": None, "alle_gegner": []}
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
    except ImportError:
        return result

    import re as _re

    def _az_basis(az_str: str) -> str:
        basis = _re.sub(r'[A-Z]{2,3}$', '', az_str.strip().upper()).strip()
        return basis if basis and "/" in basis else az_str

    az_basis = _az_basis(az)

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # AZ aus RA-Micro holen
            cur.execute("""
                SELECT TOP 1 a.sAktenNummer AS az_roh, a.GUIDAkte
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return result

            az_roh    = row["az_roh"]
            # WDM speichert AktenNr OHNE SB-Kürzel
            import re as _re2
            az_wdm = _re2.sub(r'[A-Z]{2,3}$', '', az_roh.strip().upper()).strip()
            az_wdm = az_wdm if az_wdm and "/" in az_wdm else az_roh
            guid_akte = row["GUIDAkte"]

            # Beteiligte laden
            cur.execute("""
                SELECT b.iBeteiligtenArt AS art, b.sBeteiligtenKennzeichen AS kz,
                       b.sBetreffZeile1, b.sBetreffZeile2, b.sBetreffZeile3,
                       b.iAdressnummer,
                       adr.sErsteAdresszeile,
                       adr.sNachname, adr.sVorname, adr.sAnrede, adr.sBriefanrede,
                       adr.[sStraße] AS sStrasse, adr.sPLZ, adr.sOrt,
                       adr.sTelefon, adr.sTelefax, adr.sEMail,
                       ISNULL(adr.bVorsteuerabzugsberechtigt, 0) AS bVorsteuerabzugsberechtigt
                FROM tblAktenBeteiligte b
                INNER JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.GUIDAkte = %(guid)s AND b.bDeaktiviert = 0
                ORDER BY
                    b.iBeteiligtenArt ASC,
                    CASE b.sBeteiligtenKennzeichen
                        WHEN 'GHPV' THEN 1
                        WHEN 'GH'   THEN 1
                        WHEN 'GHV'  THEN 2
                        WHEN 'GBEV' THEN 3
                        WHEN 'G1'   THEN 4
                        ELSE             9
                    END ASC
            """, {"guid": guid_akte})
            rows = cur.fetchall()

            # WDM für Betreff-Auflösung
            cur.execute("""
                SELECT sName, CAST(Value AS nvarchar(500)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_roh)s AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(500)) != ''
            """, {"az_roh": az_roh})
            wdm = {r["sName"]: r["wert"] for r in cur.fetchall()}

        def _klassifiziere(art: int, kz: str) -> str:
            kz_up = (kz or "").strip().upper()
            if art == 1 and kz_up not in ("SB", "SO", "G"):
                return "mandant"
            if art in (2, 4, 9) and kz_up not in ("HP", "HPV", "KASK"):
                return "gegner"
            return "andere"

        def _beteiligter_dict(r: dict, wdm_dict: dict) -> dict:
            vorname  = (r.get("sVorname")          or "").strip()
            nachname = (r.get("sNachname")         or "").strip()
            erste    = (r.get("sErsteAdresszeile") or "").strip()
            # sErsteAdresszeile nur als Firmenname wenn KEIN Vorname vorhanden
            # (sonst enthält es z.B. "Herrn" als Anredeform → falscher Name)
            if not vorname and erste:
                name = erste   # Firma oder Organisation
            else:
                name = nachname  # Person: nur Nachname, Vorname separat

            def _ersetze(text):
                if not text: return ""
                return _re.sub(r"<([^>]+)>",
                    lambda m: wdm_dict.get(f"var{m.group(1)}") or
                              wdm_dict.get(f"var{m.group(1).upper()}") or "", text).strip()

            # RA-Micro speichert sAnrede als Code ("1"=Herr, "2"=Frau) oder als Text
            _anrede_raw = (r.get("sAnrede") or "").strip()
            _ANREDE_NORM = {"1": "Herr", "2": "Frau"}
            _anrede = _ANREDE_NORM.get(_anrede_raw, _anrede_raw)

            return {
                "name":        name,
                "vorname":     vorname,
                "firma":       None,
                "anschrift":   (r.get("sStrasse") or "").strip(),
                "plz":         (r.get("sPLZ")     or "").strip(),
                "ort":         (r.get("sOrt")      or "").strip(),
                "telefon":     (r.get("sTelefon")  or "").strip(),
                "email":       (r.get("sEMail")    or "").strip(),
                "anrede":      _anrede,
                "briefanrede": (r.get("sBriefanrede") or "").strip(),
                "versicherung": None,
                "schaden_nr":  None,
                "kfz_kennzeichen": wdm.get("varG-KZ") or wdm.get("varM-KZ") or "",
                "betreff1":    _ersetze(r.get("sBetreffZeile1") or ""),
                "betreff2":    _ersetze(r.get("sBetreffZeile2") or ""),
                "betreff3":    _ersetze(r.get("sBetreffZeile3") or ""),
                "vorsteuer":   "Y" if r.get("bVorsteuerabzugsberechtigt") else "N",
            }

        seen = set()
        # Sortierung: GHPV/GH (direkte HV) → GHV → GBEV (Anwalt der Gegenseite) → Rest
        def _kz_rang(r):
            kz = (r.get("kz") or "").strip().upper()
            if kz in ("GHPV", "GH"):  return 0  # direkte Haftpflichtversicherung
            if kz in ("GHV",):         return 1  # Haftpflichtversicherer (Variante)
            if kz in ("GBEV",):        return 2  # Bevollmächtigter (Anwalt)
            if kz.startswith("G"):     return 3  # sonstige Gegner
            return 9
        rows_sorted = sorted(rows, key=_kz_rang)
        for row in rows_sorted:
            adr_nr = row.get("iAdressnummer")
            if adr_nr and adr_nr in seen:
                continue
            if adr_nr:
                seen.add(adr_nr)

            gruppe = _klassifiziere(row.get("art", 0), row.get("kz", ""))
            if gruppe == "mandant" and result["mandant"] is None:
                d = _beteiligter_dict(dict(row), wdm)
                d["id"] = adr_nr or 0
                result["mandant"] = d
            elif gruppe == "gegner":
                d = _beteiligter_dict(dict(row), wdm)
                d["id"] = adr_nr or 0
                kz_up = (row.get("kz") or "").strip().upper()
                # Firmennamen als versicherung setzen wenn kein Vorname oder sErsteAdresszeile gesetzt
                if not d.get("vorname") or not d.get("vorname").strip():
                    d["versicherung"] = d["name"]
                # Schadennummer aus Betreffzeile wenn GHPV-Beteiligter
                if kz_up in ("GHPV", "GH", "GBEV", "GHV") and not d.get("schaden_nr"):
                    d["schaden_nr"] = d.get("betreff1") or d.get("betreff2") or None
                # Erster Gegner bleibt in "gegner" (für Briefe/Word: GHPV-Priorität)
                if result["gegner"] is None:
                    result["gegner"] = d
                # Alle Gegner sammeln (für Klagewizard)
                result["alle_gegner"].append(d)

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        pass
    except Exception as e:
        logger.debug("_lade_beteiligte_aus_ramicro(%s): %s", az, e)

    return result


def _lade_gegner_adresse_aus_ramicro(az: str) -> dict:
    """
    Lädt Gegner-Adresse direkt aus RA-Micro (tblAdressen) für ein Aktenzeichen.
    Identische Logik wie hole_wiedervorlage_details() in der Sachstandsanfrage.
    Priorität: GHPV → GHV → GBEV → G1 → erster Beteiligter art=2/4/9.
    
    Gibt dict mit Feldern zurück die direkt in forderungsschreiben_wv._generiere() nutzbar sind:
        versicherung, name, vorname, anschrift, plz, ort, email,
        briefanrede, betreff1, betreff2, betreff3, kuerzel
    """
    LEER = {}
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
    except ImportError:
        return LEER

    import re as _re

    az_basis = _re.sub(r'[A-Z]{2,3}$', '', az.strip().upper()).strip()
    if not az_basis or "/" not in az_basis:
        az_basis = az

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()

            # Akte finden
            cur.execute("""
                SELECT TOP 1 a.sAktenNummer AS az_roh, a.GUIDAkte
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return LEER
            guid_akte = row["GUIDAkte"]

            # Gegner mit GHPV-Priorisierung laden — identisch zu hole_wiedervorlage_details
            cur.execute("""
                SELECT TOP 1
                    b.sBeteiligtenKennzeichen   AS kz,
                    b.sBetreffZeile1,
                    b.sBetreffZeile2,
                    b.sBetreffZeile3,
                    adr.sErsteAdresszeile,
                    adr.sNachname,
                    adr.sVorname,
                    adr.sBriefanrede,
                    adr.[sStraße]               AS adr_strasse,
                    adr.sPLZ                    AS adr_plz,
                    adr.sOrt                    AS adr_ort,
                    adr.sEMail                  AS adr_email,
                    ISNULL(adr.bVorsteuerabzugsberechtigt, 0) AS bVorsteuerabzugsberechtigt
                FROM tblAktenBeteiligte b
                INNER JOIN tblAdressen adr ON adr.GUIDAdresse = b.GUIDAdresse
                WHERE b.GUIDAkte      = %(guid)s
                  AND b.iBeteiligtenArt IN (2, 4, 9)
                  AND b.bDeaktiviert  = 0
                ORDER BY CASE b.sBeteiligtenKennzeichen
                    WHEN 'GHPV' THEN 1
                    WHEN 'GH'   THEN 1
                    WHEN 'GHV'  THEN 2
                    WHEN 'GBEV' THEN 3
                    WHEN 'G1'   THEN 4
                    ELSE             9
                END ASC
            """, {"guid": guid_akte})
            g = cur.fetchone()
            if not g:
                return LEER

            # sErsteAdresszeile = offizieller Firmenname (z.B. "HUK-COBURG Versicherungsgruppe")
            erste    = (g.get("sErsteAdresszeile") or "").strip()
            vorname  = (g.get("sVorname")          or "").strip()
            nachname = (g.get("sNachname")         or "").strip()
            name     = erste if erste else (f"{vorname} {nachname}".strip() if vorname else nachname)

            # WDM für Betreff-Token-Auflösung
            cur.execute("""
                SELECT sName, CAST(Value AS nvarchar(500)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_wdm2)s AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(500)) != ''
            """, {"az_wdm2": _re.sub(r'[A-Z]{2,3}$', '', (row["az_roh"] or "").strip().upper()).strip() or row["az_roh"]})
            wdm = {r["sName"]: r["wert"] for r in cur.fetchall()}

            def _ersetze(text):
                if not text: return ""
                return _re.sub(r"<([^>]+)>",
                    lambda m: wdm.get(f"var{m.group(1)}") or
                              wdm.get(f"var{m.group(1).upper()}") or "", text).strip()

            return {
                "versicherung": name if not vorname else None,
                "name":         name,
                "vorname":      vorname,
                "anschrift":    (g.get("adr_strasse") or "").strip(),
                "plz":          (g.get("adr_plz")     or "").strip(),
                "ort":          (g.get("adr_ort")      or "").strip(),
                "email":        (g.get("adr_email")    or "").strip(),
                "briefanrede":  (g.get("sBriefanrede") or "").strip(),
                "betreff1":     _ersetze(g.get("sBetreffZeile1") or ""),
                "betreff2":     _ersetze(g.get("sBetreffZeile2") or ""),
                "betreff3":     _ersetze(g.get("sBetreffZeile3") or ""),
                "kuerzel":      (g.get("kz") or "").strip(),
                "vorsteuer":    "Y" if g.get("bVorsteuerabzugsberechtigt") else "N",
            }

    except (RaMicroNichtAktiv, RaMicroVerbindungsFehler):
        return LEER
    except Exception as e:
        logger.warning("_lade_gegner_adresse_aus_ramicro(%s): %s", az, e)
        return LEER


def _lade_wdm_kontrollvars(az: str) -> dict:
    """
    Lädt ausschließlich Kontrollvariablen aus RA-Micro (_tbl0WDMDaten).

    Betragsfelder werden NICHT geladen — die kommen aus SQLite.
    Geladene Gruppen:
      - Anspruchsflags:   varANSPR-SG, varANSPR-SE, varVOLLMACHTERKL, varABTRETUNG-SV …
      - Personenschaden:  varVERLETZUNG1/2, varV-KHADR, varV-ARZT1-3 …
      - Gutachter/Info:   varGUTACHTER, varKOSTENVOR, varSOLLREP …
      - Grammatik wird aus sAnrede des Mandanten abgeleitet, nicht aus WDM

    Gibt leeres Dict zurück wenn RA-Micro nicht aktiv oder nicht erreichbar.
    """
    KONTROLL_VARS = {
        # Anspruchsflags
        "varANSPR-SE", "varANSPR-SG", "varVOLLMACHTERKL", "varABTRETUNG-SV",
        "varKOSTENVOR", "varRGREP", "varNACHWEISREP", "varSOLLREP",
        "varMITTEL", "varCARID", "varENTBINDUNG", "varSVEMAIL",
        # Gutachter
        "varGUTACHTER",
        # Sonstige Schadenbezeichnungen (Beträge kommen aus SQLite)
        "varSSCHADEN1", "varSSCHADEN2", "varSSCHADEN3",
        "varSSCHADEN4", "varSSCHADEN5", "varSSCHADEN6",
        # Personenschaden
        "varVERLETZUNG1", "varVERLETZUNG2",
        "varV-KHADR.NName", "varV-KHVON", "varV-KHBIS",
        "varV-KRVON", "varV-KRBIS", "varV-HKRANK",
        "varV-ARZT1.VNName", "varV-ARZT1.Strasse", "varV-ARZT1.Ort",
        "varV-ARZT2.VNName", "varV-ARZT2.Strasse", "varV-ARZT2.Ort",
        "varV-ARZT3.VNName", "varV-ARZT3.Strasse", "varV-ARZT3.Ort",
        "varSCHMGELD",   # Schmerzensgeld-Betrag für Freitext-Nennung im Schreiben
        # Vorsteuerabzug des Mandanten
        "varSSTF",          # Steuerpflicht/Vorsteuerabzug (J/N)
        # Unfalldaten (für Abrechnungsübersicht)
        "varU-ORT", "varU-TAG", "varU-ORTSTEIL", "varU-STRASSE",
        "varM-KZ", "varG-KZ",
    }
    try:
        from ..ramicro.connector import (
            get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler
        )
        import re as _re
        az_basis = _re.sub(r'[A-Z]{2,3}$', '', az.strip().upper()).strip()
        if not az_basis or "/" not in az_basis:
            az_basis = az

        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT TOP 1 a.sAktenNummer AS az_roh
                FROM tblAkten a
                WHERE a.sAktenNummer LIKE %(like)s
                  AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY a.sAktenNummer ASC
            """, {"like": f"{az_basis}%"})
            row = cur.fetchone()
            if not row:
                return {}
            az_roh = row["az_roh"]

            # Nur die benötigten Kontrollvariablen laden (IN-Clause)
            placeholders = ",".join([f"%(v{i})s" for i in range(len(KONTROLL_VARS))])
            params = {f"v{i}": v for i, v in enumerate(KONTROLL_VARS)}
            params["az_roh"] = az_roh
            cur.execute(f"""
                SELECT sName, CAST(Value AS nvarchar(500)) AS wert
                FROM _tbl0WDMDaten
                WHERE AktenNr = %(az_roh)s
                  AND sName IN ({placeholders})
                  AND Value IS NOT NULL
                  AND CAST(Value AS nvarchar(500)) != ''
            """, params)
            return {r["sName"]: (r["wert"] or "").strip() for r in cur.fetchall()}

    except Exception as e:
        cls_name = type(e).__name__
        if "NichtAktiv" in cls_name or "VerbindungsFehler" in cls_name:
            logger.debug("_lade_wdm_kontrollvars: RA-Micro nicht aktiv.")
        else:
            logger.warning("_lade_wdm_kontrollvars: Fehler AZ=%s: %s", az, e)
        return {}
