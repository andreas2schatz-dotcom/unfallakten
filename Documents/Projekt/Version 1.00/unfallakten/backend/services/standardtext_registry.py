"""
V11 Standardtexte: YAML-Registry der pflegbaren Klageschrift-Bausteine.
Standardtexte bleiben im Programm (diese Registry); die DB-Tabelle
standardtext_override speichert nur Abweichungen. Fail-loud beim App-Start
(Muster: intake/rausch_regel.py).
"""
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

_cache = {}
_PLATZHALTER_RE = re.compile(r"<([A-Z_]+)>")
_KEY_RE = re.compile(r"^[a-z0-9_]+$")

ABSCHNITTE = {
    "antraege":       "Anträge",
    "sachverhalt":    "Sachverhalt",
    "unfallhergang":  "Unfallhergang",
    "schaden":        "Unfallschaden",
    "wuerdigung":     "Rechtliche Würdigung",
    "schmerzensgeld": "Schmerzensgeld",
    "verzug":         "Verzug",
    "gebuehren":      "Vorgerichtliche Kosten",
    "schluss":        "Schluss",
}


def standard_pfad() -> str:
    env_pfad = os.environ.get("KLAGE_STANDARDTEXTE_PFAD")
    if env_pfad:
        return os.path.normpath(env_pfad)
    hier = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(
        os.path.join(hier, "..", "registry", "klage_standardtexte.yaml"))


def lade_standardtexte(pfad: Optional[str] = None, *, reload: bool = False) -> dict:
    pfad_norm = os.path.normpath(pfad or standard_pfad())
    if not reload and pfad_norm in _cache:
        return _cache[pfad_norm]

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML nicht installiert (PyYAML>=6.0).") from exc

    if not os.path.isfile(pfad_norm):
        logger.error("Standardtext-Registry fehlt: %s", pfad_norm)
        raise RuntimeError(f"Standardtext-Registry fehlt: {pfad_norm}")

    try:
        with open(pfad_norm, "rb") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        msg = f"YAML-Syntaxfehler in {pfad_norm}: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc

    if not isinstance(data, dict) or "platzhalter" not in data or "bausteine" not in data:
        raise RuntimeError(
            f"{pfad_norm}: Wurzel muss ein Mapping mit 'platzhalter' und 'bausteine' sein.")

    katalog = data["platzhalter"]
    if not isinstance(katalog, dict):
        raise RuntimeError(f"{pfad_norm}: 'platzhalter' muss ein Mapping sein.")
    for pkey, pdef in katalog.items():
        if not _PLATZHALTER_RE.fullmatch(f"<{pkey}>"):
            raise RuntimeError(f"{pfad_norm}: Platzhalter-Key {pkey!r} ungueltig.")
        if not isinstance(pdef, dict) or not str(pdef.get("beschreibung") or "").strip() \
                or not str(pdef.get("beispiel") or "").strip():
            raise RuntimeError(
                f"{pfad_norm}: Platzhalter {pkey!r} braucht beschreibung + beispiel.")

    if not isinstance(data["bausteine"], list) or not data["bausteine"]:
        raise RuntimeError(f"{pfad_norm}: 'bausteine' muss eine nicht-leere Liste sein.")

    registry = {}
    for i, e in enumerate(data["bausteine"]):
        if not isinstance(e, dict):
            raise RuntimeError(f"{pfad_norm}: Baustein {i} ist kein Mapping.")
        key = e.get("key")
        if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
            raise RuntimeError(f"{pfad_norm}: Baustein {i}: 'key' fehlt/ungueltig.")
        if key in registry:
            raise RuntimeError(f"{pfad_norm}: Doppelter Baustein-Key {key!r}.")
        abschnitt = e.get("abschnitt")
        if abschnitt not in ABSCHNITTE:
            raise RuntimeError(f"{pfad_norm}: {key}: unbekannter Abschnitt {abschnitt!r}.")
        beschreibung = str(e.get("beschreibung") or "").strip()
        text = e.get("text")
        if not beschreibung or not isinstance(text, str) or not text.strip():
            raise RuntimeError(f"{pfad_norm}: {key}: beschreibung/text fehlt.")
        erlaubt = e.get("platzhalter") or []
        pflicht = e.get("pflicht") or []
        if not isinstance(erlaubt, list) or not isinstance(pflicht, list):
            raise RuntimeError(f"{pfad_norm}: {key}: platzhalter/pflicht muessen Listen sein.")
        fremd = [p for p in erlaubt if p not in katalog]
        if fremd:
            raise RuntimeError(f"{pfad_norm}: {key}: Platzhalter ohne Katalogeintrag: {fremd}.")
        nicht_erlaubt = [p for p in pflicht if p not in erlaubt]
        if nicht_erlaubt:
            raise RuntimeError(f"{pfad_norm}: {key}: pflicht nicht in platzhalter: {nicht_erlaubt}.")
        benutzt = set(_PLATZHALTER_RE.findall(text))
        unbekannt = sorted(benutzt - set(erlaubt))
        if unbekannt:
            raise RuntimeError(f"{pfad_norm}: {key}: unbekannte Platzhalter im Text: {unbekannt}.")
        fehlend = sorted(set(pflicht) - benutzt)
        if fehlend:
            raise RuntimeError(
                f"{pfad_norm}: {key}: Pflicht-Platzhalter fehlen im Standardtext: {fehlend}.")
        registry[key] = {
            "abschnitt": abschnitt,
            "beschreibung": beschreibung,
            "text": text,
            "platzhalter": [
                {"key": p,
                 "beschreibung": katalog[p]["beschreibung"],
                 "beispiel": katalog[p]["beispiel"],
                 "pflicht": p in pflicht}
                for p in erlaubt
            ],
        }

    _cache[pfad_norm] = registry
    logger.info("Klage-Standardtext-Registry geladen: %d Bausteine aus %s",
                len(registry), pfad_norm)
    return registry


def hole_texte_aufgeloest() -> dict:
    registry = lade_standardtexte()
    try:
        from ..models.standardtext_override import hole_alle_overrides
        overrides = hole_alle_overrides()
    except ImportError:
        overrides = {}
    return {k: overrides.get(k, e["text"]) for k, e in registry.items()}
