"""
PDF-Pipeline – Dispatcher
==========================
Dreistufige Kaskade fuer automatische Dokumentenklassifikation.

Stufe 1: Registry-Lookup (Marker aus registry.json, ~1.200 Eintraege)
Stufe 2: TF-IDF Classifier (erst ab Phase 4, wenn Trainingsdaten vorhanden)
Stufe 3: Eskalation -> System-Todo in todos-Tabelle

Wird automatisch nach Upload aufgerufen (dokumente_routes.py).
Manueller Trigger bleibt als Fallback (pdf_parse_routes.py).

Python 3.9 kompatibel.
"""

import hashlib
import json
import logging
import os
import tempfile

from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

PARSER_MIN_KONFIDENZ = 0.70

# ── Registry laden ─────────────────────────────────────────────────────────────

_REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config", "registry.json"
)

_registry_cache = None  # type: Optional[Dict]


def _lade_registry():
    # type: () -> Dict
    """Laedt registry.json einmalig und cached."""
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache
    try:
        with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
            _registry_cache = json.load(f)
        logger.info(
            "Registry geladen: %d Marker aus %s",
            len(_registry_cache.get("marker", {})),
            _REGISTRY_PATH,
        )
    except FileNotFoundError:
        logger.warning("Registry nicht gefunden: %s – Stufe 1 deaktiviert.", _REGISTRY_PATH)
        _registry_cache = {"marker": {}}
    except Exception as e:
        logger.error("Registry-Ladefehler: %s", e)
        _registry_cache = {"marker": {}}
    return _registry_cache


def registry_neu_laden():
    """Erzwingt Neuladen der Registry (z.B. nach Seeding)."""
    global _registry_cache
    _registry_cache = None
    _lade_registry()


# ── Stufe 1: Registry-Lookup ──────────────────────────────────────────────────

def _registry_lookup(norm_text):
    # type: (str) -> Optional[Dict]
    """
    Durchsucht den normalisierten Text nach bekannten Markern.

    Intelligente Konflikt-Erkennung:
    - Wenn alle Treffer zur gleichen Klasse gehoeren → eindeutig
    - Wenn Treffer aus verschiedenen Klassen → Konflikt
    - Bei Konflikt wird 'konflikt': True gesetzt, damit der Dispatcher
      classify_document() als Tiebreaker nutzen kann

    Beispiel: Ein Abrechnungsschreiben der Allianz erwaehnt SV-Kosten
    eines Sachverstaendigen → Treffer fuer 'versicherung' UND 'gutachten'
    → Konflikt → classify_document() erkennt am Kontext dass es ein
    Abrechnungsschreiben ist.
    """
    registry = _lade_registry()
    marker_dict = registry.get("marker", {})

    treffer = []
    text_lower = norm_text.lower()

    for marker_key, marker_val in marker_dict.items():
        # Domain-Marker nur via _domain_lookup matchen, nicht im Fliesstext
        if marker_val.get("marker_typ") == "domain":
            # Ausnahme: Domain im Text pruefen (Briefkopf-Domains sind zuverlaessig)
            if marker_key.lower() in text_lower:
                treffer.append({
                    "key": marker_key,
                    "klasse": marker_val.get("klasse"),
                    "lieferant": marker_val.get("lieferant"),
                    "parser": marker_val.get("parser"),
                    "laenge": len(marker_key),
                    "ist_domain": True,
                })
            continue

        if marker_key.lower() in text_lower:
            treffer.append({
                "key": marker_key,
                "klasse": marker_val.get("klasse"),
                "lieferant": marker_val.get("lieferant"),
                "parser": marker_val.get("parser"),
                "laenge": len(marker_key),
                "ist_domain": False,
            })

    if not treffer:
        return None

    # Klassen gruppieren
    klassen = {}
    for t in treffer:
        k = t["klasse"]
        if k not in klassen:
            klassen[k] = []
        klassen[k].append(t)

    # Domain-Treffer im Text haben hoechste Prioritaet
    domain_klassen = set()
    for t in treffer:
        if t["ist_domain"]:
            domain_klassen.add(t["klasse"])

    # ── Eindeutig: Nur eine Klasse gefunden ──────────────────────────────
    if len(klassen) == 1:
        klasse = list(klassen.keys())[0]
        bester = max(treffer, key=lambda t: t["laenge"])
        logger.info(
            "Registry eindeutig: '%s' -> klasse=%s (%d Treffer)",
            bester["key"], klasse, len(treffer),
        )
        return {
            "marker_key": bester["key"],
            "klasse": klasse,
            "parser": bester["parser"],
            "lieferant": bester["lieferant"],
            "konfidenz": 0.95,
            "stufe": "registry",
            "konflikt": False,
        }

    # ── Domain-Treffer im Text → diese Klasse hat Vorrang ────────────────
    if len(domain_klassen) == 1:
        domain_klasse = list(domain_klassen)[0]
        bester = max(
            [t for t in treffer if t["ist_domain"]],
            key=lambda t: t["laenge"],
        )
        andere = [k for k in klassen if k != domain_klasse]
        logger.info(
            "Registry Domain-Vorrang: '%s' -> klasse=%s "
            "(ignoriert: %s)",
            bester["key"], domain_klasse, ", ".join(andere),
        )
        return {
            "marker_key": bester["key"],
            "klasse": domain_klasse,
            "parser": bester["parser"],
            "lieferant": bester["lieferant"],
            "konfidenz": 0.92,
            "stufe": "registry_domain",
            "konflikt": False,
        }

    # ── Konflikt: Mehrere Klassen gefunden ────────────────────────────────
    # z.B. SV-Name (gutachten) + Versicherungsname (versicherung)
    # → classify_document() soll entscheiden
    alle_klassen = sorted(klassen.keys())
    bester = max(treffer, key=lambda t: t["laenge"])
    logger.info(
        "Registry-Konflikt: Klassen=%s, bester='%s' (%s). "
        "Classifier entscheidet.",
        alle_klassen, bester["key"], bester["klasse"],
    )
    return {
        "marker_key": bester["key"],
        "klasse": bester["klasse"],  # Vorschlag, wird bei Konflikt ueberstimmt
        "parser": bester["parser"],
        "lieferant": bester["lieferant"],
        "konfidenz": 0.60,  # Niedrig weil unsicher
        "stufe": "registry_konflikt",
        "konflikt": True,
        "klassen_gefunden": alle_klassen,
    }


def _domain_lookup(domain):
    # type: (str) -> Optional[Dict]
    """
    Prueft ob die Absender-Domain in der Registry bekannt ist.
    Domains haben marker_typ='domain' und sind sehr zuverlaessig.
    """
    registry = _lade_registry()
    marker_dict = registry.get("marker", {})

    domain_lower = domain.lower().strip()

    # Exakter Domain-Match
    if domain_lower in marker_dict:
        val = marker_dict[domain_lower]
        logger.info(
            "Domain-Treffer: '%s' -> klasse=%s, lieferant=%s",
            domain_lower, val.get("klasse"), val.get("lieferant"),
        )
        return {
            "marker_key": domain_lower,
            "klasse": val.get("klasse"),
            "parser": val.get("parser"),
            "lieferant": val.get("lieferant"),
            "konfidenz": 0.98,
            "stufe": "domain",
        }

    return None


# ── SHA-256 Hash ──────────────────────────────────────────────────────────────

def _berechne_hash(datei_bytes):
    # type: (bytes) -> str
    return hashlib.sha256(datei_bytes).hexdigest()


def _pruefe_duplikat(pdf_hash, akte_az):
    # type: (str, str) -> Optional[Dict]
    """Prueft ob ein Dokument mit gleichem Hash bereits in der Akte existiert."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id, dateiname, dokumentenklasse FROM dokumente "
                "WHERE pdf_hash = ? AND akte_id = ?",
                (pdf_hash, akte_az),
            ).fetchone()
            if row:
                return {
                    "dok_id": row["id"],
                    "dateiname": row["dateiname"],
                    "klasse": row["dokumentenklasse"],
                }
    except Exception as e:
        logger.warning("Duplikat-Pruefung fehlgeschlagen: %s", e)
    return None


# ── Hauptfunktion ─────────────────────────────────────────────────────────────

def _kopiere_parse_ergebnis(quell_dok_id, ziel_dok_id):
    # type: (int, int) -> None
    """Kopiert parse_json, parse_status, parse_konfidenz und dokumentenklasse
    eines Duplikat-Dokuments, statt es neu zu parsen."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT parse_json, parse_status, parse_konfidenz, dokumentenklasse "
                "FROM dokumente WHERE id = ?",
                (quell_dok_id,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE dokumente SET parse_json = ?, parse_status = ?, "
                    "parse_konfidenz = ?, dokumentenklasse = ? WHERE id = ?",
                    (row["parse_json"], row["parse_status"],
                     row["parse_konfidenz"], row["dokumentenklasse"], ziel_dok_id),
                )
        logger.info(
            "Parse-Ergebnis von Dok %d nach Dok %d kopiert.", quell_dok_id, ziel_dok_id
        )
    except Exception as e:
        logger.warning("Parse-Ergebnis kopieren fehlgeschlagen: %s", e)


def _entscheide_klasse(domain_treffer, registry_treffer, meta, dateipfad):
    # type: (Optional[Dict], Optional[Dict], Any, str) -> tuple
    """
    Entscheidet Dokumentenklasse, Konfidenz und Stufe anhand von
    Domain-Treffer, Registry-Treffer und Classifier-Ergebnis.
    Gibt (klasse, konfidenz, stufe) zurueck.
    """
    klasse = None
    konfidenz = 0.0
    stufe = "unbekannt"

    bester_treffer = domain_treffer or registry_treffer

    if bester_treffer:
        hat_konflikt = bester_treffer.get("konflikt", False)
        reg_klasse = bester_treffer["klasse"]

        if hat_konflikt:
            logger.info(
                "Konflikt-Aufloesung: Klassen=%s, Classifier sagt=%s (konf=%.2f), rg=%d sv_rg=%d",
                bester_treffer.get("klassen_gefunden"),
                meta.dokumenttyp, meta.konfidenz, meta.rg_score, meta.sv_rg_score,
            )
            if meta.dokumenttyp and meta.dokumenttyp != "unbekannt" and meta.konfidenz >= 0.30:
                klasse = meta.dokumenttyp
                konfidenz = max(meta.konfidenz, 0.75)
                stufe = "registry_konflikt+classifier"
            elif reg_klasse == "gutachten" and meta.dokumenttyp in ("sv_rechnung", "rechnung"):
                klasse = "sv_rechnung"
                konfidenz = max(meta.konfidenz, 0.80)
                stufe = "registry_konflikt+classifier_sv_rechnung"
            elif reg_klasse == "gutachten" and meta.rg_score >= 1:
                klasse = "sv_rechnung"
                konfidenz = 0.75
                stufe = "registry_konflikt_rg_signal"
            else:
                klasse = reg_klasse
                konfidenz = 0.60
                stufe = "registry_konflikt_fallback"

        elif reg_klasse == "versicherung":
            if meta.dokumenttyp in ("abrechnungsschreiben", "pruefbericht"):
                klasse = meta.dokumenttyp
                konfidenz = max(meta.konfidenz, 0.85)
                stufe = bester_treffer["stufe"] + "+classifier"
            else:
                klasse = "abrechnungsschreiben"
                konfidenz = 0.70
                stufe = bester_treffer["stufe"] + "_default"
        else:
            if reg_klasse == "gutachten" and (
                meta.dokumenttyp in ("sv_rechnung", "rechnung")
                or meta.rg_score >= 1
            ):
                klasse = "sv_rechnung"
                konfidenz = max(meta.konfidenz, 0.85)
                stufe = bester_treffer["stufe"] + "+classifier_sv_rechnung"
            else:
                klasse = reg_klasse
                konfidenz = bester_treffer["konfidenz"]
                stufe = bester_treffer["stufe"]

    elif meta.dokumenttyp and meta.dokumenttyp != "unbekannt" and meta.konfidenz >= 0.60:
        klasse = meta.dokumenttyp
        konfidenz = meta.konfidenz
        stufe = "classifier"

    # Gutachten-Guard: nur PDFs koennen ein Gutachten sein
    if klasse == "gutachten":
        ext = os.path.splitext(dateipfad)[1].lower().lstrip(".")
        if ext != "pdf":
            logger.info(
                "Gutachten-Klasse verworfen (.%s ist kein PDF) -> sonstiges.", ext,
            )
            klasse = "sonstiges"
            konfidenz = 0.40
            stufe = stufe + "_gutachten_nicht_pdf"

    return klasse, konfidenz, stufe


def dispatch_dokument(dok_id, akte_az, dateipfad, benutzer_id=None, absender_domain=None,
                      ocr_text_override=None):
    # type: (int, str, str, Optional[int], Optional[str], Optional[str]) -> Dict[str, Any]
    """
    Wird automatisch nach Upload oder E-Mail-Import aufgerufen.

    1. Hash berechnen + Duplikat pruefen
    2. Text extrahieren (bestehendes pdf_utils)
    3. OCR falls Bild-PDF und kein ocr_text_override gegeben (PRD-30)
    4. Domain-Lookup (wenn absender_domain vorhanden)
    5. Registry-Lookup im PDF-Text (Stufe 1)
    6. classify_document() Fallback (Stufe 1b)
    7. Eskalation falls unbekannt (Stufe 3)
    8. Parser ausfuehren falls vorhanden
    9. Ergebnis in DB schreiben

    Args:
        dok_id:            Dokument-ID in der DB
        akte_az:           Aktenzeichen (PK der unfallakte)
        dateipfad:         Pfad zur PDF-Datei
        benutzer_id:       Hochladender Benutzer (optional)
        absender_domain:   E-Mail-Domain des Absenders (optional, z.B. 'allianz.de')
        ocr_text_override: Vorverarbeiteter OCR-Text (aus SSE-Endpoint, vermeidet doppeltes OCR)

    Returns: Ergebnis-Dict mit klasse, konfidenz, stufe, parse_ergebnis
    """
    from ..parsers.pdf_utils import extract_text_from_pdf, normalize_text
    from ..parsers.document_classifier import classify_document

    # ── Datei lesen ────────────────────────────────────────────────────────
    with open(dateipfad, "rb") as f:
        datei_bytes = f.read()

    # ── Hash + Duplikat ────────────────────────────────────────────────────
    pdf_hash = _berechne_hash(datei_bytes)
    _speichere_hash(dok_id, pdf_hash)

    duplikat = _pruefe_duplikat(pdf_hash, akte_az)
    if duplikat and duplikat["dok_id"] != dok_id:
        logger.info(
            "Duplikat erkannt: Dok %d ist identisch mit Dok %d (%s) – Parse-Ergebnis kopiert.",
            dok_id, duplikat["dok_id"], duplikat["dateiname"],
        )
        _kopiere_parse_ergebnis(duplikat["dok_id"], dok_id)
        _logge_dispatch(dok_id, akte_az, duplikat["klasse"], 1.0, "duplikat", benutzer_id)
        return {
            "klasse": duplikat["klasse"],
            "konfidenz": 1.0,
            "stufe": "duplikat",
            "parse_status": "kopiert",
            "parse_ergebnis": None,
        }

    # ── Text extrahieren ───────────────────────────────────────────────────
    if ocr_text_override is not None:
        # SSE-Endpoint hat OCR bereits durchgeführt – direkt verwenden
        norm_text = normalize_text(ocr_text_override)
        has_image_pages = True
        logger.info("Dok %d: OCR-Text-Override verwendet (%d Zeichen).", dok_id, len(norm_text))
    else:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(datei_bytes)
            tmp_pfad = tmp.name

        try:
            full_text, page_texts, has_image_pages = extract_text_from_pdf(tmp_pfad)
        finally:
            try:
                os.unlink(tmp_pfad)
            except OSError:
                pass

        norm_text = normalize_text(full_text)

        # ── OCR-Fallback für Bild-PDFs (PRD-30) ───────────────────────────
        if not norm_text or len(norm_text.strip()) < 50:
            try:
                from ..services.ocr_service import ist_bild_pdf, ocr_text as _ocr_text
                if ist_bild_pdf(has_image_pages, len(norm_text.strip())):
                    logger.info("Dok %d: Bild-PDF erkannt – starte OCR-Fallback.", dok_id)
                    ocr_roh = _ocr_text(datei_bytes)
                    if ocr_roh and len(ocr_roh.strip()) >= 20:
                        norm_text = normalize_text(ocr_roh)
                        logger.info(
                            "Dok %d: OCR-Fallback erfolgreich – %d Zeichen.",
                            dok_id, len(norm_text),
                        )
            except Exception as ocr_err:
                logger.warning("Dok %d: OCR-Fallback fehlgeschlagen: %s", dok_id, ocr_err)

    if not norm_text or len(norm_text.strip()) < 20:
        logger.warning("Dok %d: Zu wenig Text extrahiert (%d Zeichen).", dok_id, len(norm_text))
        _speichere_ergebnis(dok_id, None, "fehlgeschlagen", 0.0, "Zu wenig Text extrahiert")
        return {"klasse": None, "konfidenz": 0.0, "stufe": "fehler"}

    # ── Stufe 1: Registry-Lookup ───────────────────────────────────────────
    # Stufe 1a: Domain-Lookup (schnellster und zuverlaessigster Check)
    domain_treffer = None
    if absender_domain:
        domain_treffer = _domain_lookup(absender_domain)

    # Stufe 1b: Text-Lookup (Marker im PDF-Text suchen)
    registry_treffer = _registry_lookup(norm_text)

    # ── Stufe 1b: classify_document() (bestehendes System) ────────────────
    meta = classify_document(norm_text, has_image_pages)

    versicherer_kuerzel = meta.versicherer_kuerzel
    pruefdienstleister = meta.pruefdienstleister

    klasse, konfidenz, stufe = _entscheide_klasse(
        domain_treffer, registry_treffer, meta, dateipfad
    )

    # ── Stufe 3: Eskalation ────────────────────────────────────────────────
    if not klasse:
        logger.info("Dok %d: Nicht klassifiziert – Eskalation.", dok_id)
        from .escalation import eskaliere_dokument
        eskaliere_dokument(
            akte_az=akte_az,
            dok_id=dok_id,
            meta=meta,
            registry_treffer=registry_treffer,
        )
        _speichere_ergebnis(dok_id, None, "ausstehend", 0.0, None)
        return {"klasse": None, "konfidenz": 0.0, "stufe": "eskalation"}

    # ── Dokumentenklasse speichern ─────────────────────────────────────────
    _speichere_klasse(dok_id, klasse)

    # ── Parser ausfuehren ──────────────────────────────────────────────────
    parse_ergebnis = None
    parse_status = "ausstehend"

    if konfidenz >= PARSER_MIN_KONFIDENZ:
        try:
            parse_ergebnis = _fuehre_parser_aus(
                klasse, norm_text, meta,
                versicherer_kuerzel=versicherer_kuerzel,
                pruefdienstleister=pruefdienstleister,
                has_image_pages=has_image_pages,
            )
            parse_status = "erfolgreich" if parse_ergebnis is not None else "ausstehend"
        except Exception as e:
            logger.error("Parser-Fehler fuer Dok %d (klasse=%s): %s", dok_id, klasse, e, exc_info=True)
            parse_status = "fehlgeschlagen"
            parse_ergebnis = {"fehler": str(e)}
    else:
        logger.info(
            "Dok %d: Konfidenz %.2f < %.2f – Parser uebersprungen (klasse=%s).",
            dok_id, konfidenz, PARSER_MIN_KONFIDENZ, klasse,
        )

    # ── Ergebnis persistieren ──────────────────────────────────────────────
    ergebnis_json = json.dumps(parse_ergebnis, ensure_ascii=False) if parse_ergebnis else None
    _speichere_ergebnis(dok_id, ergebnis_json, parse_status, konfidenz, None)

    # ── Chronik ────────────────────────────────────────────────────────────
    _logge_dispatch(dok_id, akte_az, klasse, konfidenz, stufe, benutzer_id)

    logger.info(
        "Dok %d: klasse=%s, konfidenz=%.2f, stufe=%s, parse=%s",
        dok_id, klasse, konfidenz, stufe, parse_status,
    )

    return {
        "klasse": klasse,
        "konfidenz": konfidenz,
        "stufe": stufe,
        "parse_status": parse_status,
        "parse_ergebnis": parse_ergebnis,
    }


# ── Parser-Wrapper ────────────────────────────────────────────────────────────

def _llm_aktiv():
    # type: () -> bool
    """Prueft ob LLM-Parsing aktiviert ist (Env + DB)."""
    import os as _os
    if _os.environ.get("LLM_ENABLED", "false").strip().lower() != "true":
        return False
    try:
        from ..db.database import get_connection as _get_conn
        with _get_conn() as _c:
            _row = _c.execute(
                "SELECT wert FROM konfiguration WHERE schluessel='llm_parsing_enabled'"
            ).fetchone()
            return (_row["wert"] == "true") if _row else False
    except Exception:
        return False


def _parse_abrechnungsschreiben(norm_text, meta, versicherer_kuerzel,
                                pruefdienstleister, has_image_pages):
    # type: (str, Any, Optional[str], Optional[str], bool) -> Dict
    from ..parsers.abrechnungsschreiben_parser import parse_abrechnungsschreiben
    r = parse_abrechnungsschreiben(norm_text, versicherer_kuerzel, llm_aktiv=_llm_aktiv())
    positionen = [
        {
            "art": p.art, "bezeichnung": p.bezeichnung,
            "betrag_brutto": p.betrag_brutto, "betrag_netto": p.betrag_netto,
            "mwst_betrag": p.mwst_betrag, "pruefbericht_abzug": p.pruefbericht_abzug,
            "hinweis": p.hinweis, "konfidenz": round(p.konfidenz, 3),
        }
        for p in r.positionen
    ]
    zahlungen = [
        {
            "empfaenger": z.empfaenger, "betrag": z.betrag,
            "datum": z.datum, "konto_hinweis": z.konto_hinweis,
        }
        for z in r.zahlungen
    ]
    return {
        "dokumenttyp":      "abrechnungsschreiben",
        "abrechnungsart":   r.abrechnungsart,
        "gesamtbetrag":     r.gesamtbetrag,
        "mwst_hinweis":     r.mwst_hinweis,
        "positionen":       positionen,
        "zahlungen":        zahlungen,
        "parse_konfidenz":  round(r.konfidenz, 3),
        "llm_verwendet":    r.llm_verwendet,
        "llm_konflikt":     r.llm_konflikt,
        "llm_gesamtbetrag": r.llm_gesamtbetrag,
        "llm_positionen":   r.llm_positionen,
        "warnungen":        [w for w in r.warnungen if "LLM" not in w],
    }


def _parse_pruefbericht(norm_text, meta, versicherer_kuerzel,
                        pruefdienstleister, has_image_pages):
    # type: (str, Any, Optional[str], Optional[str], bool) -> Dict
    from ..parsers.pruefbericht_parser import parse_pruefbericht
    r = parse_pruefbericht(norm_text, pruefdienstleister, has_image_pages)
    ref_ws = None
    if r.referenzwerkstatt:
        w = r.referenzwerkstatt
        ref_ws = {
            "name": w.name, "adresse": w.adresse, "plz_ort": w.plz_ort,
            "entfernung_km": w.entfernung_km,
            "lohn_mechanik": w.lohn_mechanik, "lohn_elektrik": w.lohn_elektrik,
            "lohn_karosserie": w.lohn_karosserie, "lohn_lack": w.lohn_lack,
        }
    return {
        "dokumenttyp":                        "pruefbericht",
        "pruefdienstleister":                 r.pruefdienstleister,
        "vorgangsnummer":                     r.vorgangsnummer,
        "reparaturkosten_netto_vor_pruefung": r.reparaturkosten_netto_vor_pruefung,
        "abzug_technisch":                    r.abzug_technisch,
        "abzug_werkstattalternative":         r.abzug_werkstattalternative,
        "abzug_gesamt":                       r.abzug_gesamt,
        "reparaturkosten_nach_pruefung":      r.reparaturkosten_nach_pruefung,
        "referenzwerkstatt":                  ref_ws,
        "ist_image_pdf":                      r.ist_image_pdf,
        "parse_konfidenz":                    round(r.konfidenz, 3),
        "warnungen":                          r.warnungen,
    }


def _parse_gutachten(norm_text, meta, versicherer_kuerzel,
                     pruefdienstleister, has_image_pages):
    # type: (str, Any, Optional[str], Optional[str], bool) -> Dict
    from ..parsers.gutachten_parser import parse_gutachten
    r = parse_gutachten(norm_text, pruefdienstleister, llm_aktiv=_llm_aktiv())
    fz = r.fahrzeug
    return {
        "dokumenttyp":    "gutachten",
        "sv_buero":       r.sv_buero,
        "gutachter":      r.gutachter,
        "auftragsnummer": r.auftragsnummer,
        "fahrzeug": {
            "hersteller": fz.hersteller, "typ": fz.typ,
            "kennzeichen": fz.kennzeichen, "erstzulassung": fz.erstzulassung,
            "kilometerstand": fz.kilometerstand, "farbe": fz.farbe, "vin": fz.vin,
        },
        "schadenart":                   r.schadenart,
        "abrechnungsart":               r.abrechnungsart,
        "wirtschaftlicher_totalschaden": r.wirtschaftlicher_totalschaden,
        "reparaturkosten_netto":        r.reparaturkosten_netto,
        "nutzungsausfall_tagessatz":    r.nutzungsausfall_tagessatz,
        "nutzungsausfall_tage":         r.nutzungsausfall_tage,
        "schadenpositionen": {
            "reparaturkosten":    r.reparaturkosten_netto or r.reparaturkosten_brutto,
            "rep_gutachten_netto": r.reparaturkosten_netto,
            "wiederbeschaffung":  r.wiederbeschaffungswert,
            "restwert":           r.restwert,
            "wertminderung":      r.wertminderung,
            "nutzungsausfall":    r.nutzungsausfall_gesamt,
            "sv_kosten":          r.sv_kosten_netto or r.sv_kosten_brutto,
            "sv_kosten_netto":    r.sv_kosten_netto,
        },
        "parse_konfidenz":                r.konfidenz,
        "warnungen":                      r.warnungen,
        "llm_verwendet":                  r.llm_verwendet,
        "llm_konflikt":                   r.llm_konflikt,
        "llm_wbw":                        r.llm_wbw,
        "llm_restwert":                   r.llm_restwert,
        "llm_reparaturkosten_netto":      r.llm_reparaturkosten_netto,
        "llm_wertminderung":              r.llm_wertminderung,
        "llm_nutzungsausfall_tagessatz":  r.llm_nutzungsausfall_tagessatz,
        "llm_nutzungsausfall_tage":       r.llm_nutzungsausfall_tage,
        "llm_sv_kosten_netto":            r.llm_sv_kosten_netto,
        "llm_schadenart":                 r.llm_schadenart,
    }


def _parse_rechnung(norm_text, meta, versicherer_kuerzel,
                    pruefdienstleister, has_image_pages):
    # type: (str, Any, Optional[str], Optional[str], bool) -> Dict
    from ..parsers.rechnung_parser import parse_rechnung
    r = parse_rechnung(norm_text)
    return {
        "dokumenttyp":     meta.dokumenttyp if meta and meta.dokumenttyp else "rechnung",
        "nettobetrag":     r.nettobetrag,
        "mwst_betrag":     r.mwst_betrag,
        "bruttobetrag":    r.bruttobetrag,
        "rechnungsnummer": r.rechnungsnummer,
        "rechnungsdatum":  r.rechnungsdatum,
        "parse_konfidenz": round(r.konfidenz, 3),
        "warnungen":       r.warnungen,
    }


# Klasse -> Parser-Funktion
_PARSER_MAP = {
    "abrechnungsschreiben": _parse_abrechnungsschreiben,
    "pruefbericht":         _parse_pruefbericht,
    "gutachten":            _parse_gutachten,
    "sv_rechnung":          _parse_rechnung,
    "rechnung":             _parse_rechnung,
    "reparaturrechnung":    _parse_rechnung,
    "mietwagenrechnung":    _parse_rechnung,
    "werkstattrechnung":    _parse_rechnung,
}


# ── Parser-Routing ─────────────────────────────────────────────────────────────

def _fuehre_parser_aus(klasse, norm_text, meta, versicherer_kuerzel=None,
                       pruefdienstleister=None, has_image_pages=False):
    # type: (str, str, Any, Optional[str], Optional[str], bool) -> Optional[Dict]
    """
    Ruft den passenden Parser auf.
    Gibt strukturiertes Ergebnis-Dict zurueck oder None wenn kein Parser existiert.
    Neuen Parser registrieren: Eintrag in _PARSER_MAP hinzufuegen.
    """
    parser_fn = _PARSER_MAP.get(klasse)
    if parser_fn is None:
        logger.info("Kein Parser fuer klasse=%s – nur Klassifikation gespeichert.", klasse)
        return None
    return parser_fn(norm_text, meta, versicherer_kuerzel, pruefdienstleister, has_image_pages)


# ── Klassifikation korrigieren (Feedback-Loop) ─────────────────────────────────

def korrigiere_klassifikation(dok_id, akte_az, neue_klasse, benutzer_id=None):
    # type: (int, str, str, Optional[int]) -> Dict[str, Any]
    """
    Korrigiert die Dokumentenklasse und loest den richtigen Parser aus.
    Speichert ein Trainingspaar fuer den TF-IDF-Classifier.

    Wird aufgerufen wenn der Sachbearbeiter die Klasse im Frontend aendert.

    Args:
        dok_id:      Dokument-ID
        akte_az:     Aktenzeichen
        neue_klasse: Korrekte Dokumentenklasse
        benutzer_id: Wer korrigiert hat

    Returns: Dict mit neuer Klasse, Parse-Status, Parse-Ergebnis
    """
    from ..db.database import get_connection

    # ── Alten Zustand laden ────────────────────────────────────────────────
    with get_connection() as conn:
        row = conn.execute(
            "SELECT dateipfad, dokumentenklasse, parse_konfidenz, parse_json "
            "FROM dokumente WHERE id = ?",
            (dok_id,),
        ).fetchone()

    if not row:
        return {"fehler": "Dokument nicht gefunden", "status": 404}

    alte_klasse = row["dokumentenklasse"]
    alte_konfidenz = row["parse_konfidenz"] or 0.0
    dateipfad = row["dateipfad"]

    if alte_klasse == neue_klasse:
        return {"klasse": neue_klasse, "hinweis": "Klasse unveraendert"}

    # ── Klasse aktualisieren ───────────────────────────────────────────────
    _speichere_klasse(dok_id, neue_klasse)

    # ── Trainingsdaten speichern ───────────────────────────────────────────
    _speichere_training(
        dok_id=dok_id,
        dateipfad=dateipfad,
        klasse_auto=alte_klasse,
        klasse_korrigiert=neue_klasse,
        konfidenz_auto=alte_konfidenz,
        benutzer_id=benutzer_id,
    )

    # ── Richtigen Parser ausfuehren ────────────────────────────────────────
    parse_ergebnis = None
    parse_status = "ausstehend"

    if dateipfad and os.path.exists(dateipfad):
        try:
            from ..parsers.pdf_utils import extract_text_from_pdf, normalize_text
            from ..parsers.document_classifier import classify_document

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                with open(dateipfad, "rb") as f:
                    tmp.write(f.read())
                tmp_pfad = tmp.name

            try:
                full_text, page_texts, has_image = extract_text_from_pdf(tmp_pfad)
            finally:
                try:
                    os.unlink(tmp_pfad)
                except OSError:
                    pass

            norm_text = normalize_text(full_text)
            meta = classify_document(norm_text, has_image)

            parse_ergebnis = _fuehre_parser_aus(
                neue_klasse, norm_text, meta,
                versicherer_kuerzel=meta.versicherer_kuerzel,
                pruefdienstleister=meta.pruefdienstleister,
                has_image_pages=has_image,
            )

            if parse_ergebnis:
                parse_status = "erfolgreich"
                ergebnis_json = json.dumps(parse_ergebnis, ensure_ascii=False)
                _speichere_ergebnis(dok_id, ergebnis_json, parse_status, 1.0, None)
            else:
                parse_status = "ausstehend"
                _speichere_ergebnis(dok_id, None, parse_status, 1.0, None)

        except Exception as e:
            logger.error("Re-Parse fehlgeschlagen fuer Dok %d: %s", dok_id, e)
            parse_status = "fehlgeschlagen"
            _speichere_ergebnis(dok_id, None, parse_status, 0.0, str(e))

    # ── Chronik ────────────────────────────────────────────────────────────
    try:
        from ..models.dokument import logge_aktivitaet
        logge_aktivitaet(
            aktion="klassifikation_korrigiert",
            beschreibung="Klassifikation korrigiert: %s -> %s" % (
                alte_klasse or "unbekannt", neue_klasse
            ),
            akte_id=akte_az,
            benutzer_id=benutzer_id,
            tabelle="dokumente",
        )
    except Exception as e:
        logger.warning("Chronik-Eintrag fehlgeschlagen: %s", e)

    logger.info(
        "Klassifikation korrigiert: Dok %d, %s -> %s, parse=%s",
        dok_id, alte_klasse, neue_klasse, parse_status,
    )

    return {
        "klasse": neue_klasse,
        "alte_klasse": alte_klasse,
        "parse_status": parse_status,
        "parse_ergebnis": parse_ergebnis,
    }


def _speichere_training(dok_id, dateipfad, klasse_auto, klasse_korrigiert,
                        konfidenz_auto, benutzer_id):
    # type: (int, str, Optional[str], str, float, Optional[int]) -> None
    """Speichert ein Trainingspaar fuer den TF-IDF-Classifier."""
    try:
        from ..db.database import get_connection
        from ..parsers.pdf_utils import extract_text_from_pdf, normalize_text
        import hashlib

        # Rohtext + Hash berechnen
        snippet = ""
        rohtext_hash = ""
        if dateipfad and os.path.exists(dateipfad):
            try:
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    with open(dateipfad, "rb") as f:
                        tmp.write(f.read())
                    tmp_pfad = tmp.name
                try:
                    full_text, _, _ = extract_text_from_pdf(tmp_pfad)
                finally:
                    try:
                        os.unlink(tmp_pfad)
                    except OSError:
                        pass
                norm = normalize_text(full_text)
                snippet = norm[:2000]
                rohtext_hash = hashlib.sha256(norm.encode("utf-8")).hexdigest()
            except Exception as e:
                logger.warning("Text-Extraktion fuer Training fehlgeschlagen: %s", e)
                rohtext_hash = "fehler"

        with get_connection() as conn:
            conn.execute(
                "INSERT INTO klassifikation_training "
                "(dok_id, rohtext_hash, rohtext_snippet, klasse_auto, "
                " klasse_korrigiert, konfidenz_auto, stufe_auto, korrigiert_von) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (dok_id, rohtext_hash, snippet, klasse_auto,
                 klasse_korrigiert, konfidenz_auto, "korrektur", benutzer_id),
            )
        logger.info(
            "Trainingsdaten gespeichert: Dok %d, %s -> %s",
            dok_id, klasse_auto, klasse_korrigiert,
        )
    except Exception as e:
        logger.warning("Training speichern fehlgeschlagen: %s", e)


# ── DB-Hilfsfunktionen ─────────────────────────────────────────────────────────

def _speichere_hash(dok_id, pdf_hash):
    # type: (int, str) -> None
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET pdf_hash = ? WHERE id = ?",
                (pdf_hash, dok_id),
            )
    except Exception as e:
        logger.warning("Hash speichern fehlgeschlagen fuer Dok %d: %s", dok_id, e)


def _speichere_klasse(dok_id, klasse):
    # type: (int, str) -> None
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET dokumentenklasse = ? WHERE id = ?",
                (klasse, dok_id),
            )
    except Exception as e:
        logger.warning("Klasse speichern fehlgeschlagen fuer Dok %d: %s", dok_id, e)


def _speichere_ergebnis(dok_id, parse_json, parse_status, konfidenz, fehler):
    # type: (int, Optional[str], str, float, Optional[str]) -> None
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET parse_json = ?, parse_status = ?, "
                "parse_konfidenz = ?, parse_fehler = ? WHERE id = ?",
                (parse_json, parse_status, konfidenz, fehler, dok_id),
            )
    except Exception as e:
        logger.warning("Ergebnis speichern fehlgeschlagen fuer Dok %d: %s", dok_id, e)


def _speichere_warnung(dok_id, warnung_text):
    # type: (int, str) -> None
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE dokumente SET parse_fehler = ? WHERE id = ?",
                (warnung_text, dok_id),
            )
    except Exception as e:
        logger.warning("Warnung speichern fehlgeschlagen fuer Dok %d: %s", dok_id, e)


def _logge_dispatch(dok_id, akte_az, klasse, konfidenz, stufe, benutzer_id):
    # type: (int, str, str, float, str, Optional[int]) -> None
    try:
        from ..models.dokument import logge_aktivitaet
        logge_aktivitaet(
            aktion="pdf_dispatch_%s" % klasse,
            beschreibung=(
                "PDF klassifiziert: %s (Konfidenz %.0f%%, Stufe: %s)"
                % (klasse, konfidenz * 100, stufe)
            ),
            akte_id=akte_az,
            benutzer_id=benutzer_id,
            tabelle="dokumente",
        )
    except Exception as e:
        logger.warning("Chronik-Eintrag fehlgeschlagen: %s", e)
