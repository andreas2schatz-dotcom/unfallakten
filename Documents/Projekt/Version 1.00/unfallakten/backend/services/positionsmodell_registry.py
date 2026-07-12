"""
Positionsmodell-Registry-Loader (P1.1).

Laedt drei YAMLs aus ``backend/registry/``:
  * ``positionsarten.yaml``   je position_key -> label, kategorie,
                              aggregation, checkliste
  * ``ereignistypen.yaml``    je ereignistyp -> label, richtung, ...
  * ``aktionen.yaml``         Type-Action-Matrix

und berechnet einen deterministischen Versionsstempel (sha256 ueber alle
YAML-Bytes). Fail-Loud: jeder Fehler wirft RuntimeError.

Der Loader ist der einzige Weg, die Konfiguration zu lesen. Konsistenz-
Checks:
  * alle POSITION_KEYS aus backend.models.abrechnungsschreiben sind in
    positionsarten abgedeckt.
  * checkliste-Referenzen zeigen auf existierende Ereignistypen.
  * aktionen.yaml-Schluessel sind Ereignistypen.

Analog zum S1.5-Klassen-Loader (backend/intake/registry_loader.py), aber
fuer das Positionsmodell.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_WIRKUNGEN = {"gefordert", "anerkannt", "gekuerzt", "abgelehnt",
              "erledigt", "beleg", "keine"}
_RICHTUNGEN = {"eingehend", "ausgehend", "intern"}
_QUELLEN = {"dokument", "system", "manuell"}
_KATEGORIEN = {"fahrzeugschaden", "nebenkosten", "personenschaden",
               "sonstiges"}

_YAML_DATEIEN = ("positionsarten.yaml", "ereignistypen.yaml",
                  "aktionen.yaml", "rechnungstyp_mapping.yaml",
                  "klasse_ereignistyp.yaml")

# Sondermarker aus dem alten _KLASSE_POSITION_MAP: wird zur Laufzeit
# auf sv_kosten resolved (belege_routes.py, abhaengig vom Vorsteuer-
# Flag). Loader laesst den Marker durch die Konsistenzpruefung fallen.
_SV_VORSTEUER_MARKER = "__sv_kosten_vorsteuer__"


@dataclass(frozen=True)
class PositionsmodellRegistry:
    version: str
    pfad: str
    positionsarten:        Dict[str, Dict[str, Any]]
    ereignistypen:         Dict[str, Dict[str, Any]]
    aktionen:              Dict[str, Dict[str, Any]]
    rechnungstyp_mapping:  Dict[str, str]
    klasse_ereignistyp:    Dict[str, str]


_cache: Dict[str, PositionsmodellRegistry] = {}


def standard_pfad() -> str:
    """Vorgabepfad: backend/registry/. Ueberschreibbar per Env-Var
    POSITIONSMODELL_REGISTRY_PFAD (fuer Tests)."""
    env_pfad = os.environ.get("POSITIONSMODELL_REGISTRY_PFAD")
    if env_pfad:
        return os.path.normpath(env_pfad)
    hier = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(hier, "..", "registry"))


def lade_positionsmodell(pfad: Optional[str] = None, *,
                          reload: bool = False) -> PositionsmodellRegistry:
    """Laedt die drei YAMLs und validiert sie. Cache-Singleton je Pfad.

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
        logger.error("Positionsmodell-Registry-Verzeichnis fehlt: %s",
                     pfad_norm)
        raise RuntimeError(
            f"Positionsmodell-Registry-Verzeichnis fehlt: {pfad_norm}"
        )

    hasher = hashlib.sha256()
    daten: Dict[str, Any] = {}
    for name in _YAML_DATEIEN:
        vollpfad = os.path.join(pfad_norm, name)
        if not os.path.isfile(vollpfad):
            raise RuntimeError(
                f"Positionsmodell-YAML fehlt: {vollpfad}"
            )
        try:
            with open(vollpfad, "rb") as f:
                roh = f.read()
            hasher.update(name.encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(roh)
            hasher.update(b"\x00")
            geparst = yaml.safe_load(roh)
        except yaml.YAMLError as exc:
            msg = f"YAML-Syntaxfehler in {name}: {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc
        except OSError as exc:
            msg = f"IO-Fehler beim Lesen von {name}: {exc}"
            logger.error(msg)
            raise RuntimeError(msg) from exc

        if not isinstance(geparst, dict):
            raise RuntimeError(
                f"YAML-Wurzel in {name} muss ein Mapping sein, "
                f"ist {type(geparst).__name__}"
            )
        daten[name] = geparst

    positionsarten = _extrahiere_mapping(daten["positionsarten.yaml"],
                                           "positionsarten",
                                           "positionsarten.yaml")
    ereignistypen = _extrahiere_mapping(daten["ereignistypen.yaml"],
                                          "ereignistypen",
                                          "ereignistypen.yaml")
    aktionen = _extrahiere_mapping(daten["aktionen.yaml"],
                                    "aktionen", "aktionen.yaml")
    rechnungstyp_mapping_roh = _extrahiere_mapping(
        daten["rechnungstyp_mapping.yaml"],
        "rechnungstyp_mapping", "rechnungstyp_mapping.yaml",
    )

    _validiere_positionsarten(positionsarten)
    _validiere_ereignistypen(ereignistypen)
    _validiere_kreuzreferenzen(positionsarten, ereignistypen, aktionen)
    _validiere_position_keys_katalog(positionsarten)
    rechnungstyp_mapping = _validiere_rechnungstyp_mapping(
        rechnungstyp_mapping_roh, positionsarten,
    )
    klasse_ereignistyp_roh = _extrahiere_mapping(
        daten["klasse_ereignistyp.yaml"],
        "klasse_ereignistyp", "klasse_ereignistyp.yaml",
    )
    klasse_ereignistyp = _validiere_klasse_ereignistyp(
        klasse_ereignistyp_roh, ereignistypen,
    )

    registry = PositionsmodellRegistry(
        version=hasher.hexdigest()[:16],
        pfad=pfad_norm,
        positionsarten=positionsarten,
        ereignistypen=ereignistypen,
        aktionen=aktionen,
        rechnungstyp_mapping=rechnungstyp_mapping,
        klasse_ereignistyp=klasse_ereignistyp,
    )
    _cache[pfad_norm] = registry
    logger.info(
        "Positionsmodell-Registry geladen: %d Arten, %d Typen, %d Aktionen, "
        "%d Rechnungstyp-Mappings (version=%s)",
        len(positionsarten), len(ereignistypen), len(aktionen),
        len(rechnungstyp_mapping), registry.version,
    )
    return registry


def _validiere_rechnungstyp_mapping(
    roh: Dict[str, Any],
    positionsarten: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    ergebnis: Dict[str, str] = {}
    for klasse, ziel in roh.items():
        if not isinstance(klasse, str) or not klasse.strip():
            raise RuntimeError(
                f"rechnungstyp_mapping: leere Klasse {klasse!r}"
            )
        if not isinstance(ziel, str) or not ziel.strip():
            raise RuntimeError(
                f"rechnungstyp_mapping[{klasse!r}]: Ziel muss String sein "
                f"(ist {type(ziel).__name__})"
            )
        if ziel != _SV_VORSTEUER_MARKER and ziel not in positionsarten:
            raise RuntimeError(
                f"rechnungstyp_mapping[{klasse!r}]={ziel!r} zeigt auf "
                "position_key, der nicht in positionsarten.yaml existiert"
            )
        ergebnis[klasse.strip()] = ziel.strip()
    return ergebnis


def _validiere_klasse_ereignistyp(
    roh: Dict[str, Any],
    ereignistypen: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    ergebnis: Dict[str, str] = {}
    for klasse, typ in roh.items():
        if not isinstance(klasse, str) or not klasse.strip():
            raise RuntimeError(
                f"klasse_ereignistyp: leere Klasse {klasse!r}"
            )
        if not isinstance(typ, str) or typ not in ereignistypen:
            raise RuntimeError(
                f"klasse_ereignistyp[{klasse!r}]={typ!r} ist kein "
                "existierender Ereignistyp"
            )
        if ereignistypen[typ]["richtung"] != "eingehend":
            raise RuntimeError(
                f"klasse_ereignistyp[{klasse!r}]={typ!r} ist nicht "
                "eingehend (richtung != 'eingehend')"
            )
        ergebnis[klasse.strip()] = typ.strip()
    return ergebnis


def _extrahiere_mapping(daten: Dict[str, Any], schluessel: str,
                         dateiname: str) -> Dict[str, Dict[str, Any]]:
    inner = daten.get(schluessel)
    if inner is None:
        raise RuntimeError(
            f"Pflicht-Schluessel {schluessel!r} fehlt in {dateiname}"
        )
    if not isinstance(inner, dict):
        raise RuntimeError(
            f"{schluessel!r} in {dateiname} muss ein Mapping sein"
        )
    return inner


def _validiere_positionsarten(positionsarten: Dict[str, Dict[str, Any]]) -> None:
    for key, art in positionsarten.items():
        if not isinstance(art, dict):
            raise RuntimeError(
                f"positionsarten[{key!r}] muss ein Mapping sein"
            )
        for feld in ("label", "kategorie", "aggregation", "checkliste"):
            if feld not in art:
                raise RuntimeError(
                    f"positionsarten[{key!r}] Pflichtfeld {feld!r} fehlt"
                )
        if art["kategorie"] not in _KATEGORIEN:
            raise RuntimeError(
                f"positionsarten[{key!r}].kategorie {art['kategorie']!r} "
                f"ungueltig (erlaubt: {sorted(_KATEGORIEN)})"
            )
        if not isinstance(art["checkliste"], list):
            raise RuntimeError(
                f"positionsarten[{key!r}].checkliste muss Liste sein"
            )


def _validiere_ereignistypen(ereignistypen: Dict[str, Dict[str, Any]]) -> None:
    for typ, spec in ereignistypen.items():
        if not isinstance(spec, dict):
            raise RuntimeError(f"ereignistypen[{typ!r}] muss Mapping sein")
        for feld in ("label", "richtung", "zulaessige_quellen",
                      "default_wirkung", "checklisten_relevanz"):
            if feld not in spec:
                raise RuntimeError(
                    f"ereignistypen[{typ!r}] Pflichtfeld {feld!r} fehlt"
                )
        if spec["richtung"] not in _RICHTUNGEN:
            raise RuntimeError(
                f"ereignistypen[{typ!r}].richtung {spec['richtung']!r} "
                f"ungueltig (erlaubt: {sorted(_RICHTUNGEN)})"
            )
        if spec["default_wirkung"] not in _WIRKUNGEN:
            raise RuntimeError(
                f"ereignistypen[{typ!r}].default_wirkung "
                f"{spec['default_wirkung']!r} ungueltig "
                f"(erlaubt: {sorted(_WIRKUNGEN)})"
            )
        quellen = spec["zulaessige_quellen"]
        if not isinstance(quellen, list) or not quellen:
            raise RuntimeError(
                f"ereignistypen[{typ!r}].zulaessige_quellen muss "
                "nicht-leere Liste sein"
            )
        for q in quellen:
            if q not in _QUELLEN:
                raise RuntimeError(
                    f"ereignistypen[{typ!r}].zulaessige_quellen: "
                    f"{q!r} ungueltig (erlaubt: {sorted(_QUELLEN)})"
                )


def _validiere_kreuzreferenzen(positionsarten: Dict[str, Dict[str, Any]],
                                 ereignistypen: Dict[str, Dict[str, Any]],
                                 aktionen: Dict[str, Dict[str, Any]]) -> None:
    for key, art in positionsarten.items():
        for typ in art["checkliste"]:
            if typ not in ereignistypen:
                raise RuntimeError(
                    f"positionsarten[{key!r}].checkliste -> {typ!r} ist "
                    "kein gueltiger Ereignistyp"
                )
    for typ, eintrag in aktionen.items():
        if typ not in ereignistypen:
            raise RuntimeError(
                f"aktionen.yaml: Ereignistyp {typ!r} nicht in "
                "ereignistypen.yaml"
            )
        if not isinstance(eintrag, dict):
            raise RuntimeError(
                f"aktionen[{typ!r}] muss Mapping sein"
            )
        folg = eintrag.get("folgeaktionen", [])
        if not isinstance(folg, list):
            raise RuntimeError(
                f"aktionen[{typ!r}].folgeaktionen muss Liste sein"
            )


def _validiere_position_keys_katalog(
    positionsarten: Dict[str, Dict[str, Any]],
) -> None:
    """Alle POSITION_KEYS aus abrechnungsschreiben.py muessen abgedeckt sein.

    Lazy-Import, damit Registry-Tests ohne DB laufen koennen.
    """
    from ..models.abrechnungsschreiben import POSITION_KEYS
    fehlend = sorted(k for k in POSITION_KEYS if k not in positionsarten)
    if fehlend:
        raise RuntimeError(
            "positionsarten.yaml deckt nicht alle POSITION_KEYS ab: "
            f"{fehlend}"
        )
