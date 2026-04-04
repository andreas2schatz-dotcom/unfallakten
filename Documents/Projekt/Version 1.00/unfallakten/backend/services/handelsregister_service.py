"""
Handelsregister-Service
========================
Sucht Vertretungsberechtigte (GF/Vorstand) einer deutschen Firma.

Strategie:
  1. bundesAPI/handelsregister → mechanize-basierter Scraper auf handelsregister.de
  2. Impressum-Fallback → DuckDuckGo Suche → Impressum der Firma scrapen
  3. Rate-Limit: max. 60 Requests/Stunde (Nutzungsordnung handelsregister.de)

Kein API-Key erforderlich. Kostenlos.
"""

import re
import time
import logging
import urllib.request
import urllib.parse
import urllib.error
from threading import Lock
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Rate-Limit-Schutz ─────────────────────────────────────────────────────────
_REQUESTS: list = []
_RATE_LOCK = Lock()
_MAX_PER_HOUR = 55  # konservativ unter 60


def _rate_ok() -> bool:
    """Prüft ob wir noch im Rate-Limit sind (max. 55/h)."""
    with _RATE_LOCK:
        jetzt = time.time()
        cutoff = jetzt - 3600
        _REQUESTS[:] = [t for t in _REQUESTS if t > cutoff]
        if len(_REQUESTS) >= _MAX_PER_HOUR:
            return False
        _REQUESTS.append(jetzt)
        return True


def _fetch(url: str, data: Optional[bytes] = None,
           headers: Optional[dict] = None) -> Optional[str]:
    """Einfacher HTTP-Fetch mit Timeout und Standard-Headers."""
    if not _rate_ok():
        logger.warning("Handelsregister: Rate-Limit erreicht.")
        return None
    base_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Kanzlei-Tool/1.0; +https://anwalt-offenbach.de)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de-DE,de;q=0.9",
    }
    if headers:
        base_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=base_headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            content_type = resp.headers.get("Content-Type", "")
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].strip()
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        logger.debug("_fetch %s: %s", url, e)
        return None


# ── Handelsregister.de ────────────────────────────────────────────────────────

_HR_BASE = "https://www.handelsregister.de/rp_web"
_HR_SEARCH = f"{_HR_BASE}/erweitertesuche.xhtml"


def _suche_handelsregister(firmenname: str) -> list[dict]:
    """
    Sucht eine Firma im Handelsregister-Portal.
    Gibt Liste von Treffern zurück: {name, gericht, registernr, status, detail_url}
    """
    post_data = urllib.parse.urlencode({
        "schlagwoerter":       firmenname,
        "schlagwortOptionen":  "3",   # exakter Firmenname
        "suchTyp":             "n",
        "ergebnisseProSeite":  "10",
        "btnSuche":            "Suchen",
    }).encode("utf-8")

    html = _fetch(_HR_SEARCH, data=post_data,
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not html:
        # Fallback: ähnliche Suche
        post_data2 = urllib.parse.urlencode({
            "schlagwoerter":       firmenname,
            "schlagwortOptionen":  "2",
            "suchTyp":             "n",
            "ergebnisseProSeite":  "10",
            "btnSuche":            "Suchen",
        }).encode("utf-8")
        html = _fetch(_HR_SEARCH, data=post_data2,
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
    if not html:
        return []

    treffer = []
    # Ergebnis-Tabelle parsen: <td class="...">Firmenname</td>
    rows = re.findall(
        r'<tr[^>]*>(.*?)</tr>',
        html, re.DOTALL | re.IGNORECASE
    )
    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 4:
            continue
        def clean(s): return re.sub(r'<[^>]+>', '', s).strip()
        name_cell  = clean(cells[0])
        gericht    = clean(cells[1]) if len(cells) > 1 else ""
        registernr = clean(cells[2]) if len(cells) > 2 else ""
        status     = clean(cells[3]) if len(cells) > 3 else ""

        if not name_cell or len(name_cell) < 3:
            continue
        # Link zu Unternehmensträger-Details
        link_match = re.search(r'href="([^"]*unternehmenstraeger[^"]*)"', row, re.IGNORECASE)
        detail_url = (_HR_BASE + "/" + link_match.group(1).lstrip("/")) if link_match else None

        treffer.append({
            "name":       name_cell,
            "gericht":    gericht,
            "registernr": registernr,
            "status":     status,
            "detail_url": detail_url,
        })
    return treffer


def _hole_vertreter_aus_hr(detail_url: str) -> list[dict]:
    """
    Holt Vertretungsberechtigte aus der Unternehmensträger-Detailseite.
    Sucht nach Mustern wie 'Geschäftsführer', 'Vorstand', 'persönlich haftender Gesellschafter'.
    """
    if not detail_url:
        return []
    html = _fetch(detail_url)
    if not html:
        return []

    vertreter = []
    plain = re.sub(r'<[^>]+>', ' ', html)
    plain = re.sub(r'\s+', ' ', plain)

    # Muster: "Geschäftsführer: Mustermann, Max"
    muster = [
        (r'Geschäftsführer[in]*\s*[:\-]\s*([A-ZÄÖÜ][^,\n;]{3,50})',   "Geschäftsführer"),
        (r'Vorstand\s*[:\-]\s*([A-ZÄÖÜ][^,\n;]{3,50})',               "Vorstand"),
        (r'persönlich haftend[er\s]+Gesellschafter[:\-]\s*([A-ZÄÖÜ][^,\n;]{3,50})', "Persönlich haftender Gesellschafter"),
        (r'Liquidator[in]*\s*[:\-]\s*([A-ZÄÖÜ][^,\n;]{3,50})',        "Liquidator"),
    ]
    for pattern, funktion in muster:
        for m in re.finditer(pattern, plain, re.IGNORECASE):
            name = m.group(1).strip().rstrip(".,;")
            if 3 < len(name) < 60:
                vertreter.append({"name": name, "funktion": funktion})

    # Deduplizieren
    seen = set()
    result = []
    for v in vertreter:
        key = v["name"].lower()
        if key not in seen:
            seen.add(key)
            result.append(v)
    return result


# ── Impressum-Fallback ────────────────────────────────────────────────────────

def _suche_impressum_url(firmenname: str) -> Optional[str]:
    """
    Sucht die Impressum-URL der Firma via DuckDuckGo Instant Answer.
    Kein API-Key nötig.
    """
    # DuckDuckGo HTML-Suche (kein API-Key, Scraping erlaubt)
    q = urllib.parse.quote(f"{firmenname} Impressum")
    url = f"https://html.duckduckgo.com/html/?q={q}"
    html = _fetch(url)
    if not html:
        return None

    # Ergebnislinks extrahieren (DuckDuckGo HTML gibt <a class="result__url">)
    links = re.findall(r'class="result__url"[^>]*>([^<]+)<', html)
    links += re.findall(r'href="(https?://[^"]+(?:impressum|imprint)[^"]*)"', html, re.IGNORECASE)

    for link in links[:8]:
        link = link.strip()
        if not link.startswith("http"):
            link = "https://" + link
        # Bevorzuge direkte Impressum-URLs
        if "impressum" in link.lower() or "imprint" in link.lower():
            return link
        # Oder Firmenhomepage → /impressum anhängen
        domain_match = re.match(r'(https?://[^/]+)', link)
        if domain_match:
            return domain_match.group(1) + "/impressum"
    return None


def _parse_impressum(url: str) -> list[dict]:
    """
    Holt eine Impressum-Seite und extrahiert GF/Vorstand.
    Sucht nach §5-TMG-typischen Angaben.
    """
    html = _fetch(url)
    if not html:
        # Varianten probieren
        for suffix in ["/impressum", "/impressum.html", "/de/impressum",
                       "/ueber-uns/impressum", "/footer/impressum"]:
            base = re.match(r'(https?://[^/]+)', url)
            if base:
                html = _fetch(base.group(1) + suffix)
                if html:
                    break
    if not html:
        return []

    plain = re.sub(r'<[^>]+>', ' ', html)
    plain = re.sub(r'&[a-z]+;', ' ', plain)
    plain = re.sub(r'\s+', ' ', plain)

    vertreter = []
    muster = [
        (r'Geschäftsführer[in]*\s*[:\-]\s*([A-ZÄÖÜ][a-zA-ZäöüÄÖÜß\s\-\.]{4,50})', "Geschäftsführer"),
        (r'Vorstand\s*[:\-]\s*([A-ZÄÖÜ][a-zA-ZäöüÄÖÜß\s\-\.]{4,50})',              "Vorstand"),
        (r'Vertretungsberechtigte?[r]?\s*[:\-]\s*([A-ZÄÖÜ][^,\n;]{4,50})',          "Vertretungsberechtigter"),
        (r'vertreten durch\s*[:\-]?\s*([A-ZÄÖÜ][^,\n;]{4,50})',                     "Vertretungsberechtigter"),
        (r'Inhaber\s*[:\-]\s*([A-ZÄÖÜ][a-zA-ZäöüÄÖÜß\s\-\.]{4,50})',               "Inhaber"),
    ]
    for pattern, funktion in muster:
        for m in re.finditer(pattern, plain, re.IGNORECASE):
            name = m.group(1).strip().rstrip(".,;()")
            # Bereinigen: nur bis zum nächsten Satzzeichen/Zahl
            name = re.split(r'[\d,;()\n]', name)[0].strip()
            if 4 < len(name) < 55:
                vertreter.append({"name": name, "funktion": funktion})

    seen = set()
    result = []
    for v in vertreter:
        key = v["name"].lower()
        if key not in seen:
            seen.add(key)
            result.append(v)
    return result[:5]  # max. 5 Einträge


# ── Haupt-Funktion ────────────────────────────────────────────────────────────

def suche_vertreter(firmenname: str) -> dict:
    """
    Sucht Vertretungsberechtigte einer deutschen Firma.

    Reihenfolge:
      1. Handelsregister.de (bundesAPI-Methode)
      2. Impressum der Firma (Fallback)

    Returns:
      {
        gefunden:    bool,
        name:        str,          # Firmenname wie gefunden
        rechtsform:  str,
        registernr:  str,
        gericht:     str,
        vertreter:   [{name, funktion}],
        quelle:      "handelsregister" | "impressum" | "",
        hinweis:     str | None,
      }
    """
    name_clean = firmenname.strip()
    logger.info("Vertreter-Suche: '%s'", name_clean)

    # ── Schritt 1: Handelsregister ──────────────────────────────────────────
    try:
        treffer = _suche_handelsregister(name_clean)
        if treffer:
            bester = treffer[0]
            vertreter = []
            if bester.get("detail_url"):
                vertreter = _hole_vertreter_aus_hr(bester["detail_url"])

            if vertreter:
                return {
                    "gefunden":   True,
                    "name":       bester["name"],
                    "rechtsform": _erkenne_rechtsform(bester["name"]),
                    "registernr": bester["registernr"],
                    "gericht":    bester["gericht"],
                    "vertreter":  vertreter,
                    "quelle":     "handelsregister",
                    "hinweis":    None,
                }
            # Treffer ohne Vertreter-Details → weiter mit Impressum
    except Exception as e:
        logger.warning("Handelsregister-Suche fehlgeschlagen: %s", e)

    # ── Schritt 2: Impressum ────────────────────────────────────────────────
    try:
        impressum_url = _suche_impressum_url(name_clean)
        if impressum_url:
            vertreter = _parse_impressum(impressum_url)
            if vertreter:
                return {
                    "gefunden":   True,
                    "name":       name_clean,
                    "rechtsform": _erkenne_rechtsform(name_clean),
                    "registernr": "",
                    "gericht":    "",
                    "vertreter":  vertreter,
                    "quelle":     "impressum",
                    "hinweis":    f"Quelle: {impressum_url}",
                }
    except Exception as e:
        logger.warning("Impressum-Suche fehlgeschlagen: %s", e)

    # ── Kein Ergebnis ───────────────────────────────────────────────────────
    rechtsform = _erkenne_rechtsform(name_clean)
    funktion = _funktion_aus_rechtsform(rechtsform)
    return {
        "gefunden":   False,
        "name":       name_clean,
        "rechtsform": rechtsform,
        "registernr": "",
        "gericht":    "",
        "vertreter":  [],
        "quelle":     "",
        "hinweis":    f"Keine automatischen Daten gefunden. "
                      f"Bitte {funktion} manuell eintragen.",
    }


def _erkenne_rechtsform(name: str) -> str:
    n = name.upper()
    for form in ["GMBH & CO. KG", "GMBH & CO KG", "AG & CO. KG",
                 "GMBH", "AG", "SE", "KGAA", "KG", "OHG", "GBR",
                 "EV", "EG", "UG"]:
        if form in n:
            return form.replace("&", "&")
    return ""


def _funktion_aus_rechtsform(rechtsform: str) -> str:
    rf = rechtsform.upper()
    if any(x in rf for x in ("GMBH", "UG", "GBR", "KG", "OHG")):
        return "Geschäftsführer"
    if any(x in rf for x in ("AG", "SE", "KGAA")):
        return "Vorstand"
    return "gesetzlichen Vertreter"
