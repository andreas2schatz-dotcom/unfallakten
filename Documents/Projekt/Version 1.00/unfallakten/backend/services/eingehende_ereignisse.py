"""
Helper fuer eingehende Ereignisse (P1.5).

Wird von den vier Bestaetigungswegen aufgerufen:

  * P1.5a  ReguWizard-Speichern    -> ``abrechnung_eingegangen``
  * P1.5b  Beleg-Zuordnung         -> ``rechnung_eingegangen``
  * P1.5c  Gutachten-Uebernahme    -> ``gutachten_eingegangen``
           (inkl. K-M2a fuer Ergaenzungsgutachten)
  * P1.5d  WDM-Import              -> ``abrechnung_eingegangen``
           mit herkunft='wdm' (unbestaetigter Vorschlag)

Gemeinsame Design-Regeln (aus P1.5-Prompt + freigabe.md):

  * ``ereignis_service.schreibe_ereignis`` ist der EINZIGE Schreibpunkt
    fuer die drei Ereignis-Tabellen. Diese Helper duerfen die Tabellen
    NICHT direkt beschreiben.
  * Doppelerfassungs-Guard: (akte_az, dokument_id, ereignistyp) darf nur
    ein aktuelles Ereignis haben. Bei bereits vorhandenem -> KEIN neues
    Ereignis, INFO-Log. Nur wenn der Aufrufer explizit ``ersetzt=True``
    uebergibt (ReguWizard-Edit, K-M2b) entsteht ein neues Ereignis mit
    ``ersetzt_kopf_id`` des Alt-Ereignisses.
  * Best-Effort: Alle Ausnahmen werden geloggt, aber nicht durchgereicht.
    Alt-Tabellen (regulierung_positionen etc.) laufen weiter -- eine
    Ereignis-Panne darf den Alt-Pfad NIE brechen (Sitzungsbeschluss aus
    freigabe.md 3 K-M2 sowie P1.4-Pattern).
  * Alt-Tabellen werden PARALLEL geschrieben (kein Big-Bang). Dieser
    Helper ist additiv.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from .ereignis_service import (
    pruefe_doppelerfassung,
    schreibe_ereignis,
)
from .positionsmodell_registry import lade_positionsmodell

logger = logging.getLogger(__name__)


def _heute_wenn_leer(datum: Optional[str]) -> str:
    """Gibt ``datum`` zurueck oder das heutige ISO-Datum, wenn es fehlt."""
    return datum if datum is not None else date.today().isoformat()


# ── Wirkungs-Ableitung (ReguWizard, P1.5a) ────────────────────────────────


def _regulierungs_wirkungen(
    positionen: List[Dict[str, Any]],
    haftungsart: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Zerlegt eine ReguWizard-Position in Ereignis-Positionen-Zeilen.

    Regeln (POSITIONSMODELL 5.2 Abschnitt 1):
      * ``haftungsart == 'ablehnung'``: jede Position -> ``abgelehnt``
        mit betrag=betrag_gefordert (unabhaengig von Kuerzungsart).
      * Sonst positionsscharfe Ableitung:
          - betrag_reguliert > 0        -> ``anerkannt`` mit betrag_reguliert.
          - betrag_gefordert - betrag_reguliert > 0
              a) betrag_reguliert == 0 und kuerzungsart_id -> ``abgelehnt``
                 mit betrag=betrag_gefordert (voller Ablehnungsbetrag).
              b) sonst kuerzungsart_id vorhanden -> ``gekuerzt``
                 mit betrag=(gefordert - reguliert).
      * Positionen mit gefordert=0 und reguliert=0 -> ignoriert.
    """
    ergebnis: List[Dict[str, Any]] = []
    for p in positionen:
        pk = p.get("position_key")
        if not pk:
            continue
        try:
            gefordert = float(p.get("betrag_gefordert", 0) or 0)
        except (TypeError, ValueError):
            gefordert = 0.0
        try:
            reguliert = float(p.get("betrag_reguliert", 0) or 0)
        except (TypeError, ValueError):
            reguliert = 0.0
        kart = p.get("kuerzungsart_id")

        if gefordert == 0.0 and reguliert == 0.0:
            continue

        if haftungsart == "ablehnung":
            ergebnis.append({
                "position_key": pk,
                "wirkung": "abgelehnt",
                "betrag": round(gefordert, 2),
                "kuerzungsart_id": kart,
            })
            continue

        if reguliert > 0:
            ergebnis.append({
                "position_key": pk,
                "wirkung": "anerkannt",
                "betrag": round(reguliert, 2),
                "kuerzungsart_id": None,
            })

        diff = round(gefordert - reguliert, 2)
        if diff > 0:
            if reguliert == 0.0 and kart is not None:
                ergebnis.append({
                    "position_key": pk,
                    "wirkung": "abgelehnt",
                    "betrag": round(gefordert, 2),
                    "kuerzungsart_id": kart,
                })
            elif kart is not None:
                ergebnis.append({
                    "position_key": pk,
                    "wirkung": "gekuerzt",
                    "betrag": diff,
                    "kuerzungsart_id": kart,
                })
            # Ohne Kuerzungsart: bewusst KEIN gekuerzt/abgelehnt-
            # Ereignis -- die Alt-Tabelle behaelt die Zahl, aber der
            # Freigabe-Dialog haette hier eine Kuerzungsart erzwungen.
    return ergebnis


def _registry_kennt_alle(positionen: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtert Positionen mit nicht in positionsarten registrierten
    position_keys weg (Warn-Log). Analog ausgehende_ereignisse."""
    try:
        reg = lade_positionsmodell()
    except Exception as exc:
        logger.warning("Registry-Load fehlgeschlagen: %s", exc)
        return []
    ok: List[Dict[str, Any]] = []
    for p in positionen:
        if p.get("position_key") in reg.positionsarten:
            ok.append(p)
        else:
            logger.debug(
                "Eingehendes Ereignis: position_key %r nicht in Registry, "
                "ueberspringe", p.get("position_key"),
            )
    return ok


# ── P1.5a: ReguWizard-Speichern -> abrechnung_eingegangen ─────────────────


def erzeuge_aus_regulierung(
    *,
    akte_az: str,
    dokument_id: Optional[int],
    datum: str,
    positionen: List[Dict[str, Any]],
    haftungsart: Optional[str] = None,
    benutzer_id: Optional[int] = None,
    ersetzt: bool = False,
) -> Optional[int]:
    """Schreibt ``abrechnung_eingegangen`` fuer eine ReguWizard-Erfassung.

    ``positionen`` sind ReguWizard-Positionen im Format des Body-Feldes
    (position_key, betrag_gefordert, betrag_reguliert, kuerzungsart_id).

    ``ersetzt=True`` erzwingt die Neuerfassung als Kopf-Ersetzung
    (freigabe.md K-M2b). Ohne ``ersetzt`` wird der Doppelerfassungs-Guard
    aktiv: bei bereits existierendem Ereignis fuer (akte_az, dokument_id,
    abrechnung_eingegangen) wird die alte ID zurueckgegeben (INFO-Log)
    und KEIN neues Ereignis geschrieben.

    Liefert die neue oder wiederverwendete ereignis_id, oder ``None`` bei
    Fehlern (Best-Effort).
    """
    try:
        vorhandene_id: Optional[int] = None
        if dokument_id is not None:
            vorhandene_id = pruefe_doppelerfassung(
                akte_az=akte_az,
                dokument_id=dokument_id,
                ereignistyp="abrechnung_eingegangen",
            )
        ersetzt_kopf_id: Optional[int] = None
        if vorhandene_id is not None:
            if not ersetzt:
                logger.info(
                    "abrechnung_eingegangen bereits erfasst "
                    "(akte=%s, dokument=%s, alt_ereignis=%d) -- "
                    "kein neues Ereignis (Doppelerfassungs-Guard).",
                    akte_az, dokument_id, vorhandene_id,
                )
                return vorhandene_id
            ersetzt_kopf_id = vorhandene_id

        wirkungen = _regulierungs_wirkungen(positionen, haftungsart=haftungsart)
        wirkungen = _registry_kennt_alle(wirkungen)

        return schreibe_ereignis(
            akte_az=akte_az,
            ereignistyp="abrechnung_eingegangen",
            quelle="dokument",
            datum=datum,
            dokument_id=dokument_id,
            herkunft="regu_wizard",
            positionen=wirkungen,
            erfasst_von=benutzer_id,
            ersetzt_kopf_id=ersetzt_kopf_id,
        )
    except Exception as exc:
        logger.warning(
            "abrechnung_eingegangen fehlgeschlagen (akte %s, dok %s): %s",
            akte_az, dokument_id, exc,
        )
        return None


# ── P1.5b: Beleg-Zuordnung -> rechnung_eingegangen ────────────────────────


def erzeuge_aus_beleg(
    *,
    akte_az: str,
    dokument_id: int,
    position_key: str,
    betrag: Optional[float] = None,
    benutzer_id: Optional[int] = None,
    datum: Optional[str] = None,
) -> Optional[int]:
    """Schreibt ``rechnung_eingegangen`` fuer eine Beleg-Zuordnung.

    Wirkung: ``beleg`` (Dokument belegt Position ohne Betragsanspruch --
    POSITIONSMODELL 4.2). ``betrag`` ist optional.

    Doppelerfassungs-Guard aktiv (verhindert Doppel-Ereignis bei erneutem
    Aufruf desselben Beleges).
    """
    try:
        datum = _heute_wenn_leer(datum)

        vorhandene_id = pruefe_doppelerfassung(
            akte_az=akte_az,
            dokument_id=dokument_id,
            ereignistyp="rechnung_eingegangen",
        )
        if vorhandene_id is not None:
            logger.info(
                "rechnung_eingegangen bereits erfasst "
                "(akte=%s, dokument=%s) -- kein neues Ereignis "
                "(Doppelerfassungs-Guard).",
                akte_az, dokument_id,
            )
            return vorhandene_id

        reg = lade_positionsmodell()
        if position_key not in reg.positionsarten:
            logger.warning(
                "Beleg-Ereignis: position_key %r nicht in Registry",
                position_key,
            )
            return None

        return schreibe_ereignis(
            akte_az=akte_az,
            ereignistyp="rechnung_eingegangen",
            quelle="dokument",
            datum=datum,
            dokument_id=dokument_id,
            herkunft="beleg_zuordnung",
            positionen=[{
                "position_key": position_key,
                "wirkung": "beleg",
                "betrag": betrag,
            }],
            erfasst_von=benutzer_id,
        )
    except Exception as exc:
        logger.warning(
            "rechnung_eingegangen fehlgeschlagen (akte %s, dok %s, pos %s): %s",
            akte_az, dokument_id, position_key, exc,
        )
        return None


def rechnungstyp_zu_position(
    dokumentenklasse: str,
    vorsteuer: bool = False,
) -> Optional[str]:
    """Wertet das Registry-Mapping Dokumentenklasse -> position_key aus.

    Sondermarker ``__sv_kosten_vorsteuer__`` resolvet:
      vorsteuer=True   -> "sv_kosten"       (netto)
      vorsteuer=False  -> "sv_kosten"       (in P1.5 keine Trennung netto/brutto,
                                             positionsarten hat nur sv_kosten;
                                             die Frontend-Sonderart
                                             sv_kosten_netto bleibt bis P1.7).
    """
    try:
        reg = lade_positionsmodell()
    except Exception as exc:
        logger.warning("Registry-Load fehlgeschlagen: %s", exc)
        return None
    ziel = reg.rechnungstyp_mapping.get(dokumentenklasse)
    if ziel is None:
        return None
    if ziel == "__sv_kosten_vorsteuer__":
        return "sv_kosten"
    return ziel


# ── P1.5c: Gutachten-Uebernahme -> gutachten_eingegangen + K-M2a ──────────


_GUTACHTEN_POSITIONS_KEYS = (
    "reparaturkosten", "wiederbeschaffung", "restwert",
    "wertminderung", "sv_kosten",
)


def erzeuge_aus_gutachten(
    *,
    akte_az: str,
    dokument_id: int,
    positionen: Dict[str, Optional[float]],
    benutzer_id: Optional[int] = None,
    datum: Optional[str] = None,
    ersetzt_positions_ids: Optional[List[int]] = None,
) -> Optional[int]:
    """Schreibt ``gutachten_eingegangen`` fuer eine KI-Dialog-Uebernahme.

    ``positionen`` ist ein Dict ``{position_key: betrag}`` (aus der
    Gutachten-Bestaetigung -- Reparaturkosten / Wiederbeschaffung /
    Restwert / Wertminderung / SV-Kosten). Wirkung: ``gefordert``.

    ``ersetzt_positions_ids`` (K-M2a): Liste von ereignis_positionen.id
    aus dem Alt-Gutachten, die positionsscharf ersetzt werden sollen.
    Ergaenzungsgutachten: der Aufrufer identifiziert die Zeilen aus dem
    Erstgutachten, die von den neuen Zeilen abgeloest werden (z. B.
    nur reparaturkosten -- wertminderung bleibt aktuell).

    Doppelerfassungs-Guard: derselbe Gutachten-dokument_id darf nur ein
    aktuelles Ereignis liefern. Ergaenzungsgutachten haben eine
    ANDERE dokument_id -- der Guard traegt hier nicht.
    """
    try:
        datum = _heute_wenn_leer(datum)

        vorhandene_id = pruefe_doppelerfassung(
            akte_az=akte_az,
            dokument_id=dokument_id,
            ereignistyp="gutachten_eingegangen",
        )
        if vorhandene_id is not None and not ersetzt_positions_ids:
            logger.info(
                "gutachten_eingegangen bereits erfasst "
                "(akte=%s, dokument=%s, alt_ereignis=%d) -- "
                "kein neues Ereignis (Doppelerfassungs-Guard).",
                akte_az, dokument_id, vorhandene_id,
            )
            return vorhandene_id

        eintraege: List[Dict[str, Any]] = []
        for key in _GUTACHTEN_POSITIONS_KEYS:
            wert = positionen.get(key)
            if wert is None:
                continue
            try:
                b = float(wert)
            except (TypeError, ValueError):
                continue
            if b == 0.0:
                continue
            eintraege.append({
                "position_key": key,
                "wirkung": "gefordert",
                "betrag": round(b, 2),
            })
        eintraege = _registry_kennt_alle(eintraege)

        return schreibe_ereignis(
            akte_az=akte_az,
            ereignistyp="gutachten_eingegangen",
            quelle="dokument",
            datum=datum,
            dokument_id=dokument_id,
            herkunft="ki_dialog",
            positionen=eintraege,
            erfasst_von=benutzer_id,
            ersetzt_positions_ids=ersetzt_positions_ids,
        )
    except Exception as exc:
        logger.warning(
            "gutachten_eingegangen fehlgeschlagen (akte %s, dok %s): %s",
            akte_az, dokument_id, exc,
        )
        return None


# ── P1.5d: WDM-Import -> abrechnung_eingegangen (unbestaetigter Vorschlag)


def erzeuge_aus_wdm(
    *,
    akte_az: str,
    positionen: List[Dict[str, Any]],
    haftungsart: Optional[str] = None,
    datum: Optional[str] = None,
    benutzer_id: Optional[int] = None,
) -> Optional[int]:
    """Schreibt ``abrechnung_eingegangen`` fuer einen WDM-Import.

    quelle='dokument', dokument_id=NULL, herkunft='wdm' -- unbestaetigter
    Vorschlag (PF-08). Der Sachbearbeiter kann das Ereignis spaeter
    bestaetigen; die Ableitung erkennt es als 'unbestaetigt' via
    Cache-Attribut ``herkunft='wdm'`` (Stufe 2 P1.7).

    Doppelerfassungs-Guard laeuft NICHT (dokument_id=NULL) -- der
    WDM-Alt-Pfad verhindert Mehrfach-Importe bereits mit HTTP 409.
    """
    try:
        datum = _heute_wenn_leer(datum)

        wirkungen = _regulierungs_wirkungen(positionen, haftungsart=haftungsart)
        wirkungen = _registry_kennt_alle(wirkungen)

        return schreibe_ereignis(
            akte_az=akte_az,
            ereignistyp="abrechnung_eingegangen",
            quelle="dokument",
            datum=datum,
            dokument_id=None,
            herkunft="wdm",
            positionen=wirkungen,
            erfasst_von=benutzer_id,
        )
    except Exception as exc:
        logger.warning(
            "abrechnung_eingegangen (WDM) fehlgeschlagen (akte %s): %s",
            akte_az, exc,
        )
        return None


# ── P1.5e: Review-Freigabe -> eingehendes Ereignis fuer alle Klassen ──────

_GUTACHTEN_FELD_ALIASSE = {
    "reparaturkosten": ("reparaturkosten", "reparaturkosten_netto",
                        "reparaturkosten_brutto"),
    "wiederbeschaffung": ("wiederbeschaffung", "wiederbeschaffungswert"),
    "restwert": ("restwert", "restwert_netto", "restwert_brutto"),
    "wertminderung": ("wertminderung",),
}


def _feld_zu_zahl(wert):
    """'1.011,50' -> 1011.5 ; '850.00' -> 850.0 ; 850 -> 850.0 ; None/'' -> None.

    BUG-05: Format-sicherer Helper ``parse_betrag`` statt striktem Punkt-
    Entfernen -- '850.00' (LLM-Dezimalpunkt) darf NICHT 85000.0 werden.
    Unparsbare Werte -> None (lieber kein Betrag als ein falscher).
    """
    if wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    s = str(wert).strip()
    if not s:
        return None
    from ..parsers.pdf_utils import parse_betrag
    return parse_betrag(s)


def _gutachten_positionen(felder, vorsteuer):
    """Leitet {position_key: betrag} aus geparsten Gutachten-Feldern ab."""
    positionen = {}
    if not isinstance(felder, dict):
        return positionen
    for pk, aliase in _GUTACHTEN_FELD_ALIASSE.items():
        for name in aliase:
            wert = _feld_zu_zahl(felder.get(name))
            if wert:
                positionen[pk] = wert
                break
    sv_netto = _feld_zu_zahl(felder.get("sv_kosten_netto"))
    sv_brutto = _feld_zu_zahl(felder.get("sv_kosten_brutto"))
    if sv_netto or sv_brutto:
        if vorsteuer:
            wert = sv_netto if sv_netto is not None else sv_brutto
        else:
            wert = sv_brutto if sv_brutto is not None else sv_netto
        if wert:
            positionen["sv_kosten"] = wert
    return positionen


def erzeuge_aus_freigabe(
    *,
    akte_az: str,
    dokument_id: int,
    ereignistyp: str,
    klasse: str,
    felder: Dict[str, Any],
    vorsteuer: bool = False,
    benutzer_id: Optional[int] = None,
    datum: Optional[str] = None,
) -> Optional[int]:
    """Schreibt ein eingehendes Ereignis aus der Review-Freigabe (P1.5e).

    Positionen nur bei eindeutigen Betraegen:
      * gutachten_eingegangen -> Felder-Ableitung, Wirkung 'gefordert'.
      * rechnung_eingegangen  -> ein position_key aus rechnungstyp_mapping,
                                 Wirkung 'beleg', Betrag aus bruttobetrag/
                                 nettobetrag. Fehlt das Mapping -> Fakt.
      * sonst                 -> Fakt-Ereignis ohne Positionen.

    Doppelerfassungs-Guard aktiv. Best-Effort (Ausnahmen werden geloggt).
    """
    try:
        datum = _heute_wenn_leer(datum)

        vorhandene_id = pruefe_doppelerfassung(
            akte_az=akte_az, dokument_id=dokument_id, ereignistyp=ereignistyp,
        )
        if vorhandene_id is not None:
            logger.info(
                "%s bereits erfasst (akte=%s, dokument=%s, alt_ereignis=%d) "
                "-- kein neues Ereignis (Doppelerfassungs-Guard).",
                ereignistyp, akte_az, dokument_id, vorhandene_id,
            )
            return vorhandene_id

        positionen: List[Dict[str, Any]] = []
        if ereignistyp == "gutachten_eingegangen":
            for pk, betrag in _gutachten_positionen(felder, vorsteuer).items():
                positionen.append({
                    "position_key": pk, "wirkung": "gefordert",
                    "betrag": round(betrag, 2),
                })
        elif ereignistyp == "rechnung_eingegangen":
            pk = rechnungstyp_zu_position(klasse, vorsteuer=vorsteuer)
            if pk:
                betrag = (_feld_zu_zahl((felder or {}).get("bruttobetrag"))
                          or _feld_zu_zahl((felder or {}).get("nettobetrag")))
                positionen.append({
                    "position_key": pk, "wirkung": "beleg",
                    "betrag": round(betrag, 2) if betrag is not None else None,
                })

        positionen = _registry_kennt_alle(positionen)

        return schreibe_ereignis(
            akte_az=akte_az,
            ereignistyp=ereignistyp,
            quelle="dokument",
            datum=datum,
            dokument_id=dokument_id,
            herkunft="freigabe",
            positionen=positionen,
            erfasst_von=benutzer_id,
        )
    except Exception as exc:
        logger.warning(
            "%s aus Freigabe fehlgeschlagen (akte %s, dok %s): %s",
            ereignistyp, akte_az, dokument_id, exc,
        )
        return None
