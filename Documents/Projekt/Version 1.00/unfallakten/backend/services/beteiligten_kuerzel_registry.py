"""
Beteiligten-Kuerzel-Registry -- SSOT fuer RA-MICRO-Beteiligtenkennzeichen.

Bis 2026-08-31 legten fuenf Stellen dieselben Kennzeichen unabhaengig
voneinander aus (word_service, beteiligte_routes, ramicro_akte_routes,
belege_routes, klage_routes). Folge: Zeugen (Kuerzel 'Z') standen als
Gegner in der Beteiligtenliste und wurden im Klage-Wizard als Beklagte
vorgeschlagen. Alle fuenf lesen jetzt hier.

Bezeichnungen: Kuerzelliste der Kanzlei (RA Schatz, 2026-08-31).
"""

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml

_PFLICHT = ("bezeichnung", "rolle")

# Passivlegitimiert: der Gegner selbst und seine Haftpflichtversicherung
# (Direktanspruch § 115 VVG). Sonst niemand -- Bevollmaechtigte der Gegner und
# Schadenabwickler ausdruecklich nicht (RA Schatz, 2026-08-31).
ROLLEN_BEKLAGTER = frozenset({"gegner", "gegner_hv"})

# Rollen, die unter Beteiligtenart 1 (Mandantenseite) nicht vorkommen koennen.
ROLLEN_UNVEREINBAR_MIT_MANDANT = frozenset({"gegner", "gegner_hv", "gegner_anwalt"})

GUELTIGE_ROLLEN = frozenset({
    "mandant", "gegner", "gegner_hv", "gegner_anwalt", "schadenabwickler",
    "eigene_versicherung", "rechtsschutz", "zeuge", "sachverstaendiger",
    "gericht", "polizei", "staatsanwaltschaft", "behoerde", "bank",
    "vollstreckung", "sonstiger",
})


@dataclass(frozen=True)
class BeteiligtenRolle:
    kuerzel: str
    bezeichnung: str
    rolle: str
    beklagter_vorschlag: bool
    unbekannt: bool
    offen: bool
    hinweis: str = ""


@dataclass(frozen=True)
class BeteiligtenKuerzelRegistry:
    version: str
    pfad: str
    kuerzel: Dict[str, Dict[str, Any]]
    art_standard: Dict[int, Dict[str, Any]]
    standard: Dict[str, Any]


_cache: Dict[str, BeteiligtenKuerzelRegistry] = {}


def standard_pfad() -> str:
    env = os.environ.get("BETEILIGTEN_KUERZEL_REGISTRY_PFAD")
    if env:
        return env
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "registry", "beteiligten_kuerzel.yaml"))


def _pruefe(eintrag: Dict[str, Any], wo: str) -> None:
    for feld in _PFLICHT:
        if not eintrag.get(feld):
            raise RuntimeError(f"Beteiligten-Kuerzel-Registry: '{feld}' fehlt bei {wo}")
    rolle = eintrag["rolle"]
    if rolle not in GUELTIGE_ROLLEN:
        raise RuntimeError(
            f"Beteiligten-Kuerzel-Registry: unbekannte Rolle '{rolle}' bei {wo}")
    if eintrag.get("beklagter_vorschlag") and rolle not in ROLLEN_BEKLAGTER:
        raise RuntimeError(
            f"Beteiligten-Kuerzel-Registry: {wo} soll Beklagter sein, ist als "
            f"'{rolle}' aber nicht passivlegitimiert")


def lade_beteiligten_kuerzel(pfad: Optional[str] = None, *,
                             reload: bool = False) -> BeteiligtenKuerzelRegistry:
    p = pfad or standard_pfad()
    if not reload and p in _cache:
        return _cache[p]
    try:
        with open(p, "rb") as fh:
            roh = fh.read()
    except OSError as e:
        raise RuntimeError(f"Beteiligten-Kuerzel-Registry nicht lesbar: {p}: {e}") from e
    try:
        data = yaml.safe_load(roh) or {}
    except yaml.YAMLError as e:
        raise RuntimeError(f"Beteiligten-Kuerzel-Registry ist kein gueltiges YAML: {p}: {e}") from e

    kuerzel_roh = data.get("kuerzel") or {}
    if not kuerzel_roh:
        raise RuntimeError(f"Beteiligten-Kuerzel-Registry ist leer: {p}")

    kuerzel: Dict[str, Dict[str, Any]] = {}
    for k, eintrag in kuerzel_roh.items():
        _pruefe(eintrag, f"Kuerzel '{k}'")
        kuerzel[str(k).strip().upper()] = eintrag

    art_standard: Dict[int, Dict[str, Any]] = {}
    for art, eintrag in (data.get("art_standard") or {}).items():
        _pruefe(eintrag, f"Beteiligtenart {art}")
        art_standard[int(art)] = eintrag

    standard = data.get("standard") or {}
    _pruefe(standard, "Auffangregel 'standard'")

    registry = BeteiligtenKuerzelRegistry(
        version=hashlib.sha256(roh).hexdigest()[:16],
        pfad=p,
        kuerzel=kuerzel,
        art_standard=art_standard,
        standard=standard,
    )
    _cache[p] = registry
    return registry


def _baue(kz: str, eintrag: Dict[str, Any], *, unbekannt: bool,
          hinweis: str = "") -> BeteiligtenRolle:
    return BeteiligtenRolle(
        kuerzel=kz,
        bezeichnung=eintrag["bezeichnung"],
        rolle=eintrag["rolle"],
        beklagter_vorschlag=bool(eintrag.get("beklagter_vorschlag", False)),
        unbekannt=unbekannt,
        offen=bool(eintrag.get("offen", False)),
        hinweis=hinweis,
    )


def bestimme_beteiligten_rolle(art: Any, kuerzel: Any) -> BeteiligtenRolle:
    """Rolle eines RA-MICRO-Beteiligten aus Beteiligtenart und Kennzeichen.

    Reihenfolge:
      1. bekanntes Kuerzel  -> Registry-Eintrag
      2. leeres Kuerzel     -> Auffang nach Beteiligtenart
      3. unbekanntes Kuerzel-> "Sonstige Beteiligte", als unbekannt vermerkt
    """
    registry = lade_beteiligten_kuerzel()
    kz = (str(kuerzel).strip().upper() if kuerzel is not None else "")
    try:
        art_nr = int(art)
    except (TypeError, ValueError):
        art_nr = 0

    eintrag = registry.kuerzel.get(kz)
    if eintrag:
        # Beteiligtenart 1 ist die Mandantenseite. Traegt so ein Eintrag ein
        # Gegner-Kuerzel, widersprechen sich beide Angaben -- meist ein
        # Tippfehler (Echtfall 668/23: Mandantin mit Kuerzel 'g'). Aus einem
        # Widerspruch darf nie ein Beklagter werden.
        if art_nr == 1 and eintrag["rolle"] in ROLLEN_UNVEREINBAR_MIT_MANDANT:
            return _baue(kz, registry.standard, unbekannt=False,
                         hinweis=f"Kürzel „{kz}“ widerspricht der "
                                 f"Beteiligtenart „Mandant“")
        return _baue(kz, eintrag, unbekannt=False)

    if not kz:
        return _baue(kz, registry.art_standard.get(art_nr, registry.standard),
                     unbekannt=False)

    return _baue(kz, registry.standard, unbekannt=True,
                 hinweis=f"Kürzel „{kz}“ ist im Kürzelverzeichnis nicht hinterlegt")
