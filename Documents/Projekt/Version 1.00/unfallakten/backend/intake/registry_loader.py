"""
Dokumentklassen-Registry-Loader (S1.5).

Laedt YAMLs aus backend/registry/klassen/*.yaml und berechnet einen
deterministischen Versionsstempel (kurzer sha256-Hash ueber alle YAML-Bytes).

Fail-Loud: Ladefehler = RuntimeError + ERROR-Log. Kein stiller Fallback auf
leere Registry (behebt den Bug des heutigen registry.json-Loaders).

Anwendung:
    from backend.intake.registry_loader import lade_registry, standard_pfad
    reg = lade_registry(standard_pfad())
    print(reg.version, list(reg.klassen))
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


PFLICHT_FELDER = (
    "marker",
    "regex_felder",
    "schema",
    "pflichtfelder",
    "kritische_felder",
    "validierungsregeln",
    "fristrelevanz",
    "loeschfrist_jahre",
)


@dataclass(frozen=True)
class Registry:
    version: str
    klassen: Dict[str, Dict[str, Any]]
    pfad: str


_cache: Dict[str, Registry] = {}


def standard_pfad() -> str:
    """Vorgabepfad: backend/registry/klassen/.

    Kann per Env-Var INTAKE_REGISTRY_PFAD ueberschrieben werden (fuer Tests).
    """
    env_pfad = os.environ.get("INTAKE_REGISTRY_PFAD")
    if env_pfad:
        return os.path.normpath(env_pfad)
    hier = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(hier, "..", "registry", "klassen"))


def lade_registry(pfad: Optional[str] = None, *, reload: bool = False) -> Registry:
    """Laedt Registry aus <pfad>. Cache-Singleton je Pfad.

    Ladefehler werfen RuntimeError (Fail-Loud). Beim App-Start heisst das:
    defektes YAML -> App startet nicht.
    """
    pfad_norm = os.path.normpath(pfad or standard_pfad())

    if not reload and pfad_norm in _cache:
        return _cache[pfad_norm]

    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML nicht installiert. In requirements.txt: PyYAML>=6.0"
        ) from exc

    if not os.path.isdir(pfad_norm):
        logger.error("Registry-Verzeichnis fehlt: %s", pfad_norm)
        raise RuntimeError(f"Registry-Verzeichnis fehlt: {pfad_norm}")

    yaml_dateien = sorted(
        f for f in os.listdir(pfad_norm)
        if f.endswith(".yaml") or f.endswith(".yml")
    )
    if not yaml_dateien:
        logger.error("Registry-Verzeichnis leer: %s", pfad_norm)
        raise RuntimeError(
            f"Registry-Verzeichnis enthaelt kein YAML: {pfad_norm}"
        )

    klassen: Dict[str, Dict[str, Any]] = {}
    hasher = hashlib.sha256()

    for dateiname in yaml_dateien:
        vollpfad = os.path.join(pfad_norm, dateiname)
        try:
            with open(vollpfad, "rb") as f:
                roh = f.read()
            hasher.update(dateiname.encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(roh)
            hasher.update(b"\x00")

            data = yaml.safe_load(roh)
        except yaml.YAMLError as exc:
            msg = f"YAML-Syntaxfehler in {dateiname}: {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc
        except OSError as exc:
            msg = f"IO-Fehler beim Lesen von {dateiname}: {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc

        _validiere_eintrag(dateiname, data, klassen)
        klassen[data["klasse"]] = data

    version = hasher.hexdigest()[:16]
    registry = Registry(
        version=version,
        klassen=klassen,
        pfad=pfad_norm,
    )
    _cache[pfad_norm] = registry
    logger.info(
        "Registry geladen: %d Klassen aus %s (version=%s)",
        len(klassen), pfad_norm, version,
    )
    return registry


def _validiere_eintrag(dateiname: str,
                       data: Any,
                       vorhandene_klassen: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise RuntimeError(
            f"YAML-Wurzel in {dateiname} muss ein Mapping sein, ist {type(data).__name__}"
        )

    klasse = data.get("klasse")
    if not isinstance(klasse, str) or not klasse:
        raise RuntimeError(
            f"Pflichtfeld 'klasse' fehlt oder ist leer in {dateiname}"
        )

    # Konvention: Dateiname (ohne .yaml/.yml) == klasse
    stem = os.path.splitext(dateiname)[0]
    if stem != klasse:
        raise RuntimeError(
            f"Dateiname '{dateiname}' passt nicht zur klasse '{klasse}' — Konvention: <klasse>.yaml"
        )

    if klasse in vorhandene_klassen:
        raise RuntimeError(
            f"Doppelte klasse '{klasse}' — bereits definiert (Datei {dateiname})"
        )

    fehlend = [f for f in PFLICHT_FELDER if f not in data]
    if fehlend:
        raise RuntimeError(
            f"Pflichtfelder fehlen in {dateiname}: {', '.join(fehlend)}"
        )

    if not isinstance(data["marker"], list):
        raise RuntimeError(
            f"'marker' muss eine Liste sein in {dateiname}"
        )
    if not isinstance(data["regex_felder"], dict):
        raise RuntimeError(
            f"'regex_felder' muss ein Mapping sein in {dateiname}"
        )
    if not isinstance(data["schema"], dict):
        raise RuntimeError(
            f"'schema' muss ein Mapping sein in {dateiname}"
        )
    if not isinstance(data["pflichtfelder"], list):
        raise RuntimeError(
            f"'pflichtfelder' muss eine Liste sein in {dateiname}"
        )
    if not isinstance(data["kritische_felder"], list):
        raise RuntimeError(
            f"'kritische_felder' muss eine Liste sein in {dateiname}"
        )
    if not isinstance(data["validierungsregeln"], list):
        raise RuntimeError(
            f"'validierungsregeln' muss eine Liste sein in {dateiname}"
        )
    if not isinstance(data["fristrelevanz"], bool):
        raise RuntimeError(
            f"'fristrelevanz' muss bool sein in {dateiname}"
        )
    if not isinstance(data["loeschfrist_jahre"], int) or data["loeschfrist_jahre"] < 0:
        raise RuntimeError(
            f"'loeschfrist_jahre' muss eine nichtnegative Ganzzahl sein in {dateiname}"
        )

    if "label" in data and not isinstance(data["label"], str):
        raise RuntimeError(
            f"'label' muss ein String sein in {dateiname}"
        )
    if "bezeichnung_felder" in data:
        bf = data["bezeichnung_felder"]
        if not isinstance(bf, dict):
            raise RuntimeError(
                f"'bezeichnung_felder' muss ein Mapping sein in {dateiname}"
            )
        for rolle, feld in bf.items():
            if rolle not in ("aussteller", "datum", "betrag"):
                raise RuntimeError(
                    f"'bezeichnung_felder' Rolle {rolle!r} unbekannt in "
                    f"{dateiname} (erlaubt: aussteller, datum, betrag)"
                )
            if not isinstance(feld, str) or not feld:
                raise RuntimeError(
                    f"'bezeichnung_felder.{rolle}' muss ein nichtleerer "
                    f"String sein in {dateiname}"
                )
