"""
Rausch-Absender-Regel.

Laedt backend/registry/rausch_absender.yaml (fail-loud) und beantwortet, ob
eine Absender-Domain automatisch aussortiert wird und mit welcher Policy:

    nur_body  -> E-Mail-Body verwerfen, Anhaenge behalten (Placetel: Fax bleibt)
    komplett  -> Body + alle Anhaenge verwerfen (beA-Benachrichtigung)

Kein Treffer -> None (unangetastet).
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_ERLAUBTE_POLICIES = ("nur_body", "komplett")

_cache: Dict[str, Dict[str, str]] = {}


def standard_pfad() -> str:
    env_pfad = os.environ.get("INTAKE_RAUSCH_REGISTRY_PFAD")
    if env_pfad:
        return os.path.normpath(env_pfad)
    hier = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(
        os.path.join(hier, "..", "registry", "rausch_absender.yaml")
    )


def lade_regeln(pfad: Optional[str] = None, *, reload: bool = False) -> Dict[str, str]:
    pfad_norm = os.path.normpath(pfad or standard_pfad())
    if not reload and pfad_norm in _cache:
        return _cache[pfad_norm]

    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyYAML nicht installiert (PyYAML>=6.0).") from exc

    if not os.path.isfile(pfad_norm):
        logger.error("Rausch-Registry fehlt: %s", pfad_norm)
        raise RuntimeError(f"Rausch-Registry fehlt: {pfad_norm}")

    try:
        with open(pfad_norm, "rb") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        msg = f"YAML-Syntaxfehler in {pfad_norm}: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    if not isinstance(data, list):
        raise RuntimeError(
            f"Rausch-Registry {pfad_norm}: Wurzel muss eine Liste sein, "
            f"ist {type(data).__name__}"
        )

    regeln: Dict[str, str] = {}
    for i, eintrag in enumerate(data):
        if not isinstance(eintrag, dict):
            raise RuntimeError(f"Eintrag {i} in {pfad_norm} ist kein Mapping.")
        domain = eintrag.get("domain")
        policy = eintrag.get("policy")
        if not isinstance(domain, str) or not domain.strip():
            raise RuntimeError(f"Eintrag {i} in {pfad_norm}: 'domain' fehlt/leer.")
        if policy not in _ERLAUBTE_POLICIES:
            raise RuntimeError(
                f"Eintrag {i} in {pfad_norm}: 'policy' {policy!r} unbekannt "
                f"(erlaubt: {_ERLAUBTE_POLICIES})."
            )
        dom = domain.strip().lower()
        if dom in regeln:
            raise RuntimeError(f"Doppelte domain {dom!r} in {pfad_norm}.")
        regeln[dom] = policy

    _cache[pfad_norm] = regeln
    logger.info("Rausch-Registry geladen: %d Absender aus %s", len(regeln), pfad_norm)
    return regeln


def policy_fuer_domain(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    return lade_regeln().get(domain.strip().lower())
