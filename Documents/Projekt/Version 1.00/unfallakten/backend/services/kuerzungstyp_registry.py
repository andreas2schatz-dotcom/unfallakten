import hashlib
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml

KATEGORIEN_AF = {
    "A": "Reparaturkosten fiktiv",
    "B": "Reparaturkosten konkret",
    "C": "Fahrzeugwert",
    "D": "Ausfall/Mobilität",
    "E": "Nebenkosten",
    "F": "Personenschaden",
}

_PFLICHT = ("typ_code", "name", "kategorie_code", "verifiziert_am")


@dataclass(frozen=True)
class KuerzungstypRegistry:
    version: str
    pfad: str
    typen: Dict[str, Dict[str, Any]]


_cache: Dict[str, KuerzungstypRegistry] = {}


def standard_pfad() -> str:
    env = os.environ.get("KUERZUNGSTYP_REGISTRY_PFAD")
    if env:
        return env
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "registry", "kuerzungstypen"))


def lade_kuerzungstypen(pfad: Optional[str] = None, *,
                        reload: bool = False) -> KuerzungstypRegistry:
    p = pfad or standard_pfad()
    if not reload and p in _cache:
        return _cache[p]
    if not os.path.isdir(p):
        raise RuntimeError(f"Kürzungstyp-Registry-Verzeichnis fehlt: {p}")
    dateien = sorted(f for f in os.listdir(p) if f.endswith(".yaml"))
    if not dateien:
        raise RuntimeError(f"Kürzungstyp-Registry ist leer: {p}")
    typen: Dict[str, Dict[str, Any]] = {}
    h = hashlib.sha256()
    for datei in dateien:
        voll = os.path.join(p, datei)
        try:
            with open(voll, "rb") as fh:
                roh = fh.read()
        except OSError as e:
            raise RuntimeError(f"Kürzungstyp-Registry nicht lesbar: {voll}: {e}") from e
        h.update(roh)
        try:
            data = yaml.safe_load(roh)
        except yaml.YAMLError as e:
            raise RuntimeError(f"YAML-Fehler in {voll}: {e}") from e
        _validiere(datei, data, typen)
        data.setdefault("keywords", [])
        data.setdefault("keywords_erfordert", [])
        data.setdefault("llm_hinweis", "")
        data.setdefault("baustein_pfad", True)
        data.setdefault("kategorie_label", KATEGORIEN_AF[data["kategorie_code"]])
        typen[data["typ_code"]] = data
    reg = KuerzungstypRegistry(version=h.hexdigest()[:16], pfad=p, typen=typen)
    _cache[p] = reg
    return reg


def _validiere(datei: str, data: Any, vorhandene: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise RuntimeError(f"{datei}: kein YAML-Mapping")
    for feld in _PFLICHT:
        if not data.get(feld):
            raise RuntimeError(f"{datei}: Pflichtfeld '{feld}' fehlt")
    code = data["typ_code"]
    if datei != f"{code}.yaml":
        raise RuntimeError(f"{datei}: Dateiname muss '{code}.yaml' sein")
    if code in vorhandene:
        raise RuntimeError(f"{datei}: typ_code '{code}' doppelt")
    if data["kategorie_code"] not in KATEGORIEN_AF:
        raise RuntimeError(f"{datei}: kategorie_code '{data['kategorie_code']}' unbekannt")
