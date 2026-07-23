import re
from dataclasses import dataclass
from typing import List, Optional

from backend.services.kuerzungstyp_registry import lade_kuerzungstypen

BEGRUENDUNGS_KLASSEN = ("pruefbericht", "abrechnungsschreiben")
_SNIPPET_RADIUS = 120
_BRIEFKOPF_ZEICHEN = 600


@dataclass
class TypVorschlag:
    typ_code: str
    kuerzungsart_id: Optional[int]
    snippet: str
    quelle: str
    konfidenz: float


def _wort_regex(keyword: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-zÄÖÜäöüß])" + re.escape(keyword) +
                      r"(?![A-Za-zÄÖÜäöüß])", re.IGNORECASE)


def _kuerzungsart_id_map():
    from backend.db.database import get_connection
    with get_connection() as conn:
        return {r["typ_code"]: r["id"] for r in conn.execute(
            "SELECT typ_code, id FROM kuerzungsarten WHERE typ_code IS NOT NULL")}


def schlage_typen_vor(text: str, *, dokumentklasse: str,
                      llm_fallback: bool = True) -> List[TypVorschlag]:
    if dokumentklasse not in BEGRUENDUNGS_KLASSEN or not text:
        return []
    reg = lade_kuerzungstypen()
    id_map = _kuerzungsart_id_map()
    vorschlaege: List[TypVorschlag] = []
    for code, typ in reg.typen.items():
        treffer = _finde_regel_treffer(text, typ)
        if treffer is not None:
            vorschlaege.append(TypVorschlag(
                typ_code=code, kuerzungsart_id=id_map.get(code),
                snippet=treffer, quelle="regel", konfidenz=0.9))
    if not vorschlaege and llm_fallback:
        vorschlaege = _llm_fallback(text, reg, id_map)
    return sorted(vorschlaege, key=lambda v: v.typ_code)


def _finde_regel_treffer(text: str, typ: dict) -> Optional[str]:
    for kw in typ.get("keywords", []):
        for m in _wort_regex(kw).finditer(text):
            # Briefkopf-Unterdrueckung nur fuer vollstaendige Schreiben; Kurztexte sind Snippets ohne Kopfzone
            if (m.start() < _BRIEFKOPF_ZEICHEN and len(text) > _BRIEFKOPF_ZEICHEN
                    and not _hat_kuerzungskontext(text, m)):
                continue
            if typ.get("keywords_erfordert"):
                fenster = text[max(0, m.start() - 200):m.end() + 200]
                if not any(e.lower() in fenster.lower()
                           for e in typ["keywords_erfordert"]):
                    continue
            a = max(0, m.start() - _SNIPPET_RADIUS)
            b = min(len(text), m.end() + _SNIPPET_RADIUS)
            return text[a:b].strip()
    return None


_KUERZUNGS_SIGNALE = re.compile(
    r"kürz|gekürzt|Abzug|nicht erstatt|nicht erforderlich|nicht ersatzfähig|"
    r"beanstand|korrigiert|streichen|erneuerung|nicht an", re.IGNORECASE)


def _hat_kuerzungskontext(text: str, m: re.Match) -> bool:
    fenster = text[max(0, m.start() - 150):m.end() + 150]
    return bool(_KUERZUNGS_SIGNALE.search(fenster))


def _llm_fallback(text, reg, id_map) -> List[TypVorschlag]:
    return []
