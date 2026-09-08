"""
Gerichtsorte-Registry -- gepflegte Zuordnung Unfallort -> zustaendiges Gericht.

Hintergrund: Der Unfallort (RA-MICRO varU-ORT) nennt sehr oft eine Stadt
ohne eigenes Amtsgericht -- Muehlheim, Neu-Isenburg, Dietzenbach,
Heusenstamm, Obertshausen, Dreieich. Von 1607 Unfallorten im Bestand
betrifft das 525. Aus dem Namen laesst sich das zustaendige Gericht
grundsaetzlich nicht ableiten, dafuer braucht es die Gerichtsbezirke.

RA-MICRO fuehrt diese Zuordnung in Z:\\RA\\Mdb\\raplz.mdb (45 MB,
kennwortgeschuetzt); im SQL Server steht sie nicht -- dort gibt es weder
eine passende Tabelle noch eine Funktion. Statt die Fremddatei
vorzuhalten, pflegt die Kanzlei die wenigen relevanten Orte selbst
(Entscheidung RA Schatz, 2026-09-02): betroffen sind praktisch nur die
Bezirke Frankfurt und Darmstadt.

Diese Liste hat Vorrang vor dem Namensabgleich gegen die
Gerichtsadressen -- sie ist gepflegtes Wissen, der Abgleich nur Heuristik.
"""

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yaml

_ERLAUBTE_FELDER = frozenset({"gericht", "hinweis"})

# Woerter ab drei Zeichen; Hausnummern und PLZ fallen weg.
_WORT = re.compile(r"[a-zA-ZäöüßÄÖÜ]{3,}")


class GerichtsortFehler(RuntimeError):
    """Die Gerichtsorte-Liste ist unlesbar oder unvollstaendig gepflegt."""


@dataclass(frozen=True)
class GerichtsortRegistry:
    version: str
    pfad: str
    gerichtsorte: Dict[str, Dict[str, Any]]
    # Ort in Wortform, absteigend nach Wortzahl -- laengere Orte zuerst
    # pruefen, damit "Muehlheim am Main" vor "Muehlheim" greift.
    _suchreihen: Tuple[Tuple[Tuple[str, ...], str], ...] = ()


_cache: Dict[str, GerichtsortRegistry] = {}


def ort_woerter(text: Optional[str]) -> List[str]:
    """Zerlegt Freitext in kleingeschriebene Ortswoerter.

    Bindestriche trennen wie Leerzeichen: "Neu-Isenburg" wird zur Wortfolge
    ["neu", "isenburg"] und trifft damit sowohl "Neu-Isenburg" als auch
    "Neu Isenburg". Gleichzeitig findet "Muehlheim-Laemmerspiel" den
    Listeneintrag "Muehlheim" und "Frankfurt-Riederwald" das dortige
    Gericht -- als ein einziges Wort taeten sie das nicht.
    """
    return [w.lower() for w in _WORT.findall(text or "")]


def standard_pfad() -> str:
    env = os.environ.get("GERICHTSORTE_REGISTRY_PFAD")
    if env:
        return env
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "registry", "gerichtsorte.yaml"))


def _pruefe(ort: str, eintrag: Any) -> None:
    if not isinstance(eintrag, dict):
        raise GerichtsortFehler(
            f"Gerichtsorte-Registry: Eintrag '{ort}' ist keine Zuordnung")
    unbekannt = set(eintrag) - _ERLAUBTE_FELDER
    if unbekannt:
        raise GerichtsortFehler(
            f"Gerichtsorte-Registry: unbekanntes Feld {sorted(unbekannt)} bei '{ort}' "
            f"-- erlaubt sind {sorted(_ERLAUBTE_FELDER)}")
    if not str(eintrag.get("gericht") or "").strip():
        raise GerichtsortFehler(
            f"Gerichtsorte-Registry: '{ort}' nennt kein Gericht")


def lade_gerichtsorte(pfad: Optional[str] = None, *,
                      reload: bool = False) -> GerichtsortRegistry:
    p = pfad or standard_pfad()
    if not reload and p in _cache:
        return _cache[p]
    try:
        with open(p, "rb") as fh:
            roh = fh.read()
    except OSError as e:
        raise GerichtsortFehler(f"Gerichtsorte-Registry nicht lesbar: {p}: {e}") from e
    try:
        data = yaml.safe_load(roh) or {}
    except yaml.YAMLError as e:
        raise GerichtsortFehler(
            f"Gerichtsorte-Registry ist kein gueltiges YAML: {p}: {e}") from e

    roh_orte = data.get("gerichtsorte")
    if roh_orte is None:
        roh_orte = {}
    if not isinstance(roh_orte, dict):
        raise GerichtsortFehler(
            f"Gerichtsorte-Registry: 'gerichtsorte' muss eine Zuordnung sein: {p}")

    gerichtsorte: Dict[str, Dict[str, Any]] = {}
    reihen: List[Tuple[Tuple[str, ...], str]] = []
    for ort, eintrag in roh_orte.items():
        _pruefe(str(ort), eintrag)
        woerter = tuple(ort_woerter(str(ort)))
        if not woerter:
            raise GerichtsortFehler(
                f"Gerichtsorte-Registry: '{ort}' enthaelt keinen Ortsnamen")
        sauber = {"gericht": str(eintrag["gericht"]).strip(),
                  "hinweis": str(eintrag.get("hinweis") or "").strip()}
        gerichtsorte[str(ort).strip()] = sauber
        reihen.append((woerter, sauber["gericht"]))

    reihen.sort(key=lambda x: -len(x[0]))

    registry = GerichtsortRegistry(
        version=hashlib.sha256(roh).hexdigest()[:16],
        pfad=p,
        gerichtsorte=gerichtsorte,
        _suchreihen=tuple(reihen),
    )
    _cache[p] = registry
    return registry


def finde_gericht(unfallort: str,
                  registry: Optional[GerichtsortRegistry] = None) -> Optional[str]:
    """Name des zustaendigen Gerichts laut Liste, oder None.

    Der Ort muss als vollstaendige Wortfolge im Unfallort vorkommen --
    "Bad" trifft nicht "Badenweiler".
    """
    reg = registry or lade_gerichtsorte()
    woerter = ort_woerter(unfallort)
    if not woerter:
        return None
    for ort_woerter_, gericht in reg._suchreihen:
        n = len(ort_woerter_)
        for i in range(len(woerter) - n + 1):
            if tuple(woerter[i:i + n]) == ort_woerter_:
                return gericht
    return None
