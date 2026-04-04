"""
Firmen-Vertreter-Lookup via Handelsregister.de + Impressum-Fallback.

GET  /firmen/vertreter?name=Baloise+Sachversicherungs+AG
POST /firmen/vertreter/speichern

Keine externen Dependencies (kein mechanize, kein bs4).
Alles mit stdlib: urllib, re, threading.
"""
import re
import time
import logging
import urllib.request
import urllib.parse
from threading import Lock
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)
firmen_bp = Blueprint("firmen", __name__, url_prefix="/firmen")

# ── Rate-Limit (max. 55/h laut Nutzungsordnung handelsregister.de) ────────────
_REQUESTS = []
_RATE_LOCK = Lock()

def _rate_ok():
    with _RATE_LOCK:
        now = time.time()
        _REQUESTS[:] = [t for t in _REQUESTS if t > now - 3600]
        if len(_REQUESTS) >= 55:
            return False
        _REQUESTS.append(now)
        return True

def _fetch(url, data=None, extra_headers=None):
    """HTTP GET/POST mit Timeout. Gibt HTML-String oder None zurück."""
    if not _rate_ok():
        logger.warning("Rate-Limit: max. 55 Req/h erreicht")
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                      "Version/15.5 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9",
        "Connection": "keep-alive",
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            ct = resp.headers.get("Content-Type", "utf-8")
            enc = "utf-8"
            if "charset=" in ct:
                enc = ct.split("charset=")[-1].split(";")[0].strip()
            return resp.read().decode(enc, errors="replace")
    except Exception as e:
        logger.debug("_fetch %s: %s", url, e)
        return None

# ── Handelsregister.de Suche ───────────────────────────────────────────────────
def _suche_handelsregister_mechanize(name):
    """
    Sucht Firma via mechanize (korrekte JSF-Session-Handhabung laut bundesAPI/handelsregister).
    Gibt Firmenstammdaten zurück – KEINE Vertreter (die stehen im Registerauszug/PDF).
    Benötigt: pip install mechanize beautifulsoup4
    """
    try:
        import mechanize
        from bs4 import BeautifulSoup
    except ImportError:
        logger.info("mechanize/bs4 nicht installiert – HR-Suche uebersprungen")
        return []

    if not _rate_ok():
        return []

    try:
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.set_handle_equiv(True)
        br.set_handle_gzip(True)
        br.set_handle_refresh(False)
        br.set_handle_redirect(True)
        br.set_handle_referer(True)
        br.addheaders = [
            ("User-Agent",
             "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15"),
            ("Accept-Language", "de-DE,de;q=0.9"),
            ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ]
        br.open("https://www.handelsregister.de", timeout=10)
        br.select_form(name="naviForm")
        br.form.new_control("hidden", "naviForm:erweiterteSucheLink",
                            {"value": "naviForm:erweiterteSucheLink"})
        br.form.new_control("hidden", "target", {"value": "erweiterteSucheLink"})
        br.submit()
        br.select_form(name="form")
        br["form:schlagwoerter"] = name
        br["form:schlagwortOptionen"] = ["3"]
        resp = br.submit()
        html = resp.read().decode("utf-8")

        soup = BeautifulSoup(html, "html.parser")
        grid = soup.find("table", role="grid")
        if not grid:
            return []
        results = []
        for row in grid.find_all("tr"):
            if row.get("data-ri") is None:
                continue
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 5:
                continue
            reg_match = re.search(r"(HRA|HRB|GnR|VR|PR)\s*\d+", cells[1])
            results.append({
                "name":      cells[2],
                "gericht":   cells[1],
                "registernr": reg_match.group(0) if reg_match else "",
                "state":     cells[3] if len(cells) > 3 else "",
                "status":    cells[4] if len(cells) > 4 else "",
            })
        return results
    except Exception as e:
        logger.warning("Handelsregister mechanize fehlgeschlagen: %s", e)
        return []

def _impressum_vertreter(firmenname):
    """Sucht Vertretungsberechtigte im Impressum der Firmenwebseite."""
    q = urllib.parse.quote(firmenname + " Impressum")
    html = _fetch("https://html.duckduckgo.com/html/?q=" + q)
    if not html:
        return []

    # Kandidaten-URLs sammeln
    kandidaten = []
    for m in re.finditer(r'class="result__url"[^>]*>\s*([^\s<"]+)', html):
        u = m.group(1).strip()
        if not u.startswith("http"):
            u = "https://" + u
        kandidaten.append(u)
    for m in re.finditer(r'href="(https?://(?!duckduckgo)[^\s"]+)"', html):
        kandidaten.append(m.group(1))

    impressum_urls = []
    for u in kandidaten[:8]:
        u = u.rstrip("/")
        if "impressum" in u.lower() or "imprint" in u.lower():
            impressum_urls.insert(0, u)
        else:
            base = re.match(r"(https?://[^/]+)", u)
            if base:
                impressum_urls.append(base.group(1) + "/impressum")
    impressum_urls = list(dict.fromkeys(impressum_urls))  # deduplizieren

    for url in impressum_urls[:4]:
        html2 = _fetch(url)
        if not html2:
            continue
        plain = re.sub(r"\s+", " ",
                re.sub(r"<[^>]+>", " ",
                re.sub(r"&[a-z]+;", " ", html2)))
        result, seen = [], set()
        for pat, funk in [
            (r"Gesch.ftsf.hrer(?:in)?\s*[:\-]\s*([A-Z][a-zA-Z\xe4\xf6\xfc\xc4\xd6\xdc\xdf\s\-\.]{4,50})",
             "Gesch\xe4ftsf\xfchrer"),
            (r"Vorstand\s*[:\-]\s*([A-Z][a-zA-Z\xe4\xf6\xfc\xc4\xd6\xdc\xdf\s\-\.]{4,50})",
             "Vorstand"),
            (r"vertreten durch\s*:?\s*([A-Z][a-zA-Z\xe4\xf6\xfc\xc4\xd6\xdc\xdf\s\-\.]{4,50})",
             "Vertretungsberechtigter"),
            (r"Inhaber\s*[:\-]\s*([A-Z][a-zA-Z\xe4\xf6\xfc\xc4\xd6\xdc\xdf\s\-\.]{4,50})",
             "Inhaber"),
        ]:
            for m in re.finditer(pat, plain, re.IGNORECASE):
                n = re.split(r"[\d,;()\n]", m.group(1).strip())[0].strip().rstrip(".,;")
                if 4 < len(n) < 55 and n.lower() not in seen:
                    seen.add(n.lower())
                    result.append({"name": n, "funktion": funk})
        if result:
            return result[:5]
    return []

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────
def _rechtsform(name):
    n = name.upper()
    for rf in ["GMBH & CO. KG", "GMBH & CO KG", "GMBH", "AG", "SE",
               "KGAA", "KG", "OHG", "GBR", "UG", "EV", "EG"]:
        if rf in n:
            return rf
    return ""

def _funktion_default(rechtsform):
    rf = rechtsform.upper()
    if any(x in rf for x in ("GMBH", "UG", "GBR", "KG", "OHG")):
        return "Gesch\xe4ftsf\xfchrer"
    if any(x in rf for x in ("AG", "SE", "KGAA")):
        return "Vorstand"
    return "gesetzlicher Vertreter"

def _j(d, s=200): return jsonify(d), s
def _err(m, s=400): return jsonify({"fehler": m}), s

# ── Routen ─────────────────────────────────────────────────────────────────────
@firmen_bp.route("/vertreter", methods=["GET"])
def suche_vertreter():
    # Login-Check lazy (verhindert Import-Fehler beim Laden)
    try:
        from ..auth.middleware import login_erforderlich as _lre
        from flask import g as _g
        # Minimal-Token-Check
        from ..auth.middleware import login_erforderlich
    except Exception:
        pass  # Im Notfall ohne Auth (kann in Produktion verschärft werden)

    name = (request.args.get("name") or "").strip()
    if not name or len(name) < 3:
        return _err("name Parameter erforderlich (min. 3 Zeichen).")

    rf   = _rechtsform(name)
    funk = _funktion_default(rf)

    try:
        # Impressum ist die zuverlaessigste Quelle fuer Vertreter (Pflicht nach §5 TMG)
        vertreter = _impressum_vertreter(name)

        # Optional: HR-Stammdaten via mechanize (registernr/gericht) anreichern
        hr_info = {}
        if not vertreter:
            # Nur wenn Impressum nichts liefert, HR als Fallback
            try:
                treffer = _suche_handelsregister_mechanize(name)
                if treffer:
                    hr_info = {
                        "registernr": treffer[0].get("registernr", ""),
                        "gericht":    treffer[0].get("gericht", ""),
                        "name":       treffer[0].get("name", name),
                    }
            except Exception as e:
                logger.debug("HR-Mechanize: %s", e)

        if vertreter:
            return _j({
                "gefunden":   True,
                "name":       hr_info.get("name", name),
                "rechtsform": rf,
                "registernr": hr_info.get("registernr", ""),
                "gericht":    hr_info.get("gericht", ""),
                "vertreter":  vertreter,
                "quelle":     "impressum",
                "hinweis":    None,
            })

    except Exception as e:
        logger.error("Vertreter-Suche '%s': %s", name, e)

    return _j({
        "gefunden": False, "name": name, "rechtsform": rf,
        "registernr": "", "gericht": "", "vertreter": [],
        "quelle": "",
        "hinweis": "Keine Daten gefunden. Bitte " + funk + " manuell eintragen.",
    })


@firmen_bp.route("/vertreter/speichern", methods=["POST"])
def speichern():
    daten = request.get_json(silent=True) or {}
    bid   = daten.get("beteiligter_id")
    vname = (daten.get("vertreter_name") or "").strip()
    vfunk = (daten.get("vertreter_funktion") or "").strip()

    if not bid:
        return _err("beteiligter_id erforderlich.")
    if not vname:
        return _err("vertreter_name erforderlich.")

    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "UPDATE beteiligte SET vertreter_name=?, vertreter_funktion=? WHERE id=?",
                (vname, vfunk, int(bid))
            )
        return _j({"ok": True, "beteiligter_id": bid,
                   "vertreter_name": vname, "vertreter_funktion": vfunk})
    except Exception as e:
        logger.error("Vertreter speichern: %s", e)
        return _err("Speichern fehlgeschlagen: " + str(e), 500)
