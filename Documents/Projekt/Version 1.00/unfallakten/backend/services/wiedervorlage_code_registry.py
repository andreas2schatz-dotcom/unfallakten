"""
Wiedervorlagecode-Registry -- SSOT fuer RA-MICRO-Wiedervorlagegruende.

Bis 2026-09-01 legten vier Konstanten und drei SQL-Literale dasselbe Feld
iWiedervorlageGrund unabhaengig voneinander aus. Folge: Die Fristen-Kachel
zeigte Kategorien ("Beschwerde", "Einspruch"), die niemand in der Kanzlei
kannte, und die Wiedervorlagen-Kachel beschriftete 537 Eintraege pauschal
mit "Wiedervorlage", weil ihre Liste 21 Codes nicht kannte.

Massgeblich ist der Freitext sWiedervorlagegrund. Die Registry springt nur
ein, wo RA-MICRO ihn nicht in die SQL-Datenbank schreibt (Codes 5..99).
"""

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import yaml

GUELTIGE_ARTEN = frozenset({"frist", "termin", "wiedervorlage"})

_PFLICHT_STANDARD = ("text_und_code_leer", "code_unbekannt", "art")


@dataclass(frozen=True)
class WvGrund:
    text: str
    code: Optional[int]
    art: str
    aus_freitext: bool
    unbekannt: bool


@dataclass(frozen=True)
class WvCodeRegistry:
    version: str
    pfad: str
    freitext_ab: int
    codes: Dict[int, Dict[str, Any]]
    standard: Dict[str, Any]


_cache: Dict[str, WvCodeRegistry] = {}


def standard_pfad() -> str:
    env = os.environ.get("WIEDERVORLAGE_CODES_REGISTRY_PFAD")
    if env:
        return env
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "registry", "wiedervorlage_codes.yaml"))


def _pruefe(code: int, eintrag: Dict[str, Any], freitext_ab: int) -> None:
    wo = f"Code {code}"
    if not isinstance(eintrag, dict):
        raise RuntimeError(f"Wiedervorlagecode-Registry: {wo} ist kein Eintrag")
    art = eintrag.get("art")
    if art not in GUELTIGE_ARTEN:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: unbekannte art '{art}' bei {wo}")
    if "verifiziert" not in eintrag:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: 'verifiziert' fehlt bei {wo}")
    if not eintrag.get("bezeichnung") and not eintrag.get("offen"):
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: leere 'bezeichnung' bei {wo} -- "
            f"entweder ausfuellen oder 'offen: true' setzen")
    if code >= freitext_ab:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: {wo} liegt ueber freitext_ab "
            f"({freitext_ab}) und ist damit kein eingebauter Grund")


def lade_wv_codes(pfad: Optional[str] = None, *,
                  reload: bool = False) -> WvCodeRegistry:
    p = pfad or standard_pfad()
    if not reload and p in _cache:
        return _cache[p]
    try:
        with open(p, "rb") as fh:
            roh = fh.read()
    except OSError as e:
        raise RuntimeError(f"Wiedervorlagecode-Registry nicht lesbar: {p}: {e}") from e
    try:
        data = yaml.safe_load(roh) or {}
    except yaml.YAMLError as e:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry ist kein gueltiges YAML: {p}: {e}") from e

    freitext_ab = int(data.get("freitext_ab") or 0)
    if freitext_ab <= 0:
        raise RuntimeError(f"Wiedervorlagecode-Registry: freitext_ab fehlt: {p}")

    codes_roh = data.get("codes") or {}
    if not codes_roh:
        raise RuntimeError(f"Wiedervorlagecode-Registry ist leer: {p}")

    codes: Dict[int, Dict[str, Any]] = {}
    for k, eintrag in codes_roh.items():
        code = int(k)
        _pruefe(code, eintrag, freitext_ab)
        codes[code] = eintrag

    standard = data.get("standard") or {}
    for feld in _PFLICHT_STANDARD:
        if not standard.get(feld):
            raise RuntimeError(
                f"Wiedervorlagecode-Registry: '{feld}' fehlt in 'standard': {p}")
    if standard["art"] not in GUELTIGE_ARTEN:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: unbekannte art in 'standard': {p}")

    registry = WvCodeRegistry(
        version=hashlib.sha256(roh).hexdigest()[:16],
        pfad=p,
        freitext_ab=freitext_ab,
        codes=codes,
        standard=standard,
    )
    _cache[p] = registry
    return registry


def _als_code(wert: Any) -> Optional[int]:
    if wert is None:
        return None
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def loese_wv_grund(grund_text: Any, grund_code: Any) -> WvGrund:
    """Wiedervorlagegrund zur Anzeige aufloesen.

    Reihenfolge:
      1. Freitext vorhanden  -> Freitext, unveraendert
      2. Freitext leer, Code im Katalog -> Bezeichnung aus der Registry
      3. sonst -> Auffangtext aus 'standard'
    """
    registry = lade_wv_codes()
    text = (str(grund_text).strip() if grund_text is not None else "")
    code = _als_code(grund_code)

    eintrag = None
    if code is not None and code < registry.freitext_ab:
        eintrag = registry.codes.get(code)
    art = eintrag["art"] if eintrag else registry.standard["art"]

    if text:
        return WvGrund(text=text, code=code, art=art,
                       aus_freitext=True, unbekannt=False)

    if eintrag and eintrag.get("bezeichnung"):
        return WvGrund(text=eintrag["bezeichnung"], code=code, art=art,
                       aus_freitext=False, unbekannt=False)

    if code is None or code >= registry.freitext_ab:
        return WvGrund(text=registry.standard["text_und_code_leer"], code=code,
                       art=art, aus_freitext=False, unbekannt=False)

    return WvGrund(text=f'{registry.standard["code_unbekannt"]} ({code})',
                   code=code, art=art, aus_freitext=False, unbekannt=True)


def codes_fuer_art(*arten: str) -> Tuple[int, ...]:
    for a in arten:
        if a not in GUELTIGE_ARTEN:
            raise ValueError(f"Unbekannte Kachel-Art: {a}")
    registry = lade_wv_codes()
    return tuple(sorted(c for c, e in registry.codes.items() if e["art"] in arten))


def sql_codeliste(*arten: str) -> str:
    """Kommaliste fuer eine IN-Klausel.

    Die Werte sind ints aus der Registry, nie Nutzereingaben -- die
    Interpolation in den SQL-String ist deshalb unbedenklich.
    """
    codes = codes_fuer_art(*arten)
    if not codes:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: keine Codes fuer art {arten!r} -- "
            f"IN () waere ein SQL-Fehler")
    return ", ".join(str(int(c)) for c in codes)


def stellungnahme_codes() -> Tuple[int, ...]:
    registry = lade_wv_codes()
    return tuple(sorted(c for c, e in registry.codes.items()
                        if e.get("stellungnahme")))
