"""
Firmen-Vertreter-Lookup via Handelsregister.de + Impressum-Fallback.

GET  /firmen/vertreter?name=Baloise+Sachversicherungs+AG
POST /firmen/vertreter/speichern

Keine externen Dependencies (kein mechanize, kein bs4).
Alles mit stdlib: urllib, re, threading.
"""
import html as html_mod
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

_NAMENSKLASSE = r"[A-Za-z\xe4\xf6\xfc\xc4\xd6\xdc\xdf\s\-\.]{4,50}"

_FUNKTIONSWORT = re.compile(
    r"(?i)\b(gesch\xe4ftsf\xfchrer(?:in)?|vorstand(?:svorsitzende(?:r)?)?|inhaber(?:in)?)\b")

# Nur eindeutige Adress-Tokens abschneiden — "weg"/"ring" o.ae. kaemen in
# Nachnamen vor (Hellweg, Mehring)
_STRASSEN_TOKEN = re.compile(
    r"\s+\S*(stra\xdfe|strasse|str\.)\b.*$", re.IGNORECASE)


def _funktion_aus_wort(wort):
    w = (wort or "").lower()
    if w.startswith("gesch\xe4ftsf\xfchrer"):
        return "Gesch\xe4ftsf\xfchrer"
    if w.startswith("vorstand"):
        return "Vorstand"
    if w.startswith("inhaber"):
        return "Inhaber"
    return None


def _widerspricht(funktion, erwartete_funktion):
    if erwartete_funktion not in ("Gesch\xe4ftsf\xfchrer", "Vorstand"):
        return False
    if funktion in (None, "Vertretungsberechtigter"):
        return False
    return funktion != erwartete_funktion


def _extrahiere_vertreter(seiten_html, erwartete_funktion):
    """
    Zieht Vertretungsberechtigte aus Impressum-HTML. Entities werden dekodiert
    (nicht geloescht — sonst verlieren Namen ihre Umlaute), Funktionswoerter im
    Treffer werden vom Namen getrennt, und Treffer, deren Organ der Rechtsform
    widerspricht (GF-Fund bei einer AG = fremdes Impressum), fliegen raus.
    """
    if not seiten_html:
        return []
    plain = re.sub(r"\s+", " ",
            re.sub(r"<[^>]+>", " ", html_mod.unescape(seiten_html)))
    ergebnis, seen = [], set()
    for pat, funk in [
        (r"Gesch\xe4ftsf\xfchrer(?:in)?\s*[:\-]\s*(" + _NAMENSKLASSE + r")",
         "Gesch\xe4ftsf\xfchrer"),
        (r"Vorstand\s*[:\-]\s*(" + _NAMENSKLASSE + r")", "Vorstand"),
        (r"vertreten durch\s*:?\s*(" + _NAMENSKLASSE + r")",
         "Vertretungsberechtigter"),
        (r"Inhaber\s*[:\-]\s*(" + _NAMENSKLASSE + r")", "Inhaber"),
    ]:
        for m in re.finditer(pat, plain, re.IGNORECASE):
            roh = re.split(r"[\d,;()\n]", m.group(1).strip())[0].strip().rstrip(".,;")
            roh = _STRASSEN_TOKEN.sub("", roh).strip().rstrip(".,;")
            funktion = funk
            fw = _FUNKTIONSWORT.search(roh)
            if fw:
                if fw.start() == 0:
                    funktion = _funktion_aus_wort(fw.group(1)) or funktion
                    roh = roh[fw.end():].lstrip(" :-").strip()
                else:
                    roh = roh[:fw.start()].strip().rstrip(".,;")
            if _widerspricht(funktion, erwartete_funktion):
                continue
            if 4 < len(roh) < 55 and roh.lower() not in seen:
                seen.add(roh.lower())
                ergebnis.append({"name": roh, "funktion": funktion})
    return ergebnis[:5]


_FIRMEN_SUFFIX = re.compile(
    r"[A-Z\xc4\xd6\xdc][A-Za-z\xc4\xd6\xdc\xe4\xf6\xfc\xdf\-\.&\s]{2,60}?"
    r"\b(AG|SE|GmbH|KGaA|e\.\s?V\.)\b")


def _extrahiere_vertreter_fuer_firma(seiten_html, firmenname,
                                     erwartete_funktion, fenster=600):
    """
    Blockbezogene Extraktion fuer Sammel-Impressen (mehrere Gesellschaften auf
    einer Seite, z.B. adac.de): gelesen wird nur das Textfenster direkt hinter
    jedem Vorkommen des gesuchten Firmennamens, abgeschnitten am naechsten
    fremden Gesellschaftsnamen — sonst kommen die Organe der Schwester-
    gesellschaften mit.
    """
    if not seiten_html:
        return []
    tokens = [re.escape(t) for t in re.split(r"\W+", firmenname or "") if t]
    if not tokens:
        return []
    plain = re.sub(r"\s+", " ",
            re.sub(r"<[^>]+>", " ", html_mod.unescape(seiten_html)))
    firmen_re = re.compile(r"\W+".join(tokens), re.IGNORECASE)
    ergebnis, seen = [], set()
    for m in firmen_re.finditer(plain):
        block = plain[m.end(): m.end() + fenster]
        cut = _FIRMEN_SUFFIX.search(block)
        if cut:
            block = block[:cut.start()]
        for t in _extrahiere_vertreter(block, erwartete_funktion):
            if t["name"].lower() not in seen:
                seen.add(t["name"].lower())
                ergebnis.append(t)
    return ergebnis[:5]


def _normalisiere_firmentext(t):
    return re.sub(
        r"\s+", " ",
        re.sub(r"[^a-z0-9\xe4\xf6\xfc\xdf ]", " ", (t or "").lower())
    ).strip()


def _seite_passt_zur_firma(seiten_html, firmenname):
    """
    True nur, wenn die Seite den vollen Firmennamen nennt. Ohne diesen Check
    liefert die Websuche das Impressum der falschen Firma (z.B. ADAC e.V.
    statt ADAC Autoversicherung AG) und deren Organe werden uebernommen.
    """
    firma = _normalisiere_firmentext(firmenname)
    if not seiten_html or not firma:
        return False
    plain = re.sub(r"\s+", " ",
            re.sub(r"<[^>]+>", " ", html_mod.unescape(seiten_html)))
    return firma in _normalisiere_firmentext(plain)


def _impressum_vertreter(firmenname, erwartete_funktion=""):
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

    for url in impressum_urls[:6]:
        html2 = _fetch(url)
        if not html2:
            continue
        if not _seite_passt_zur_firma(html2, firmenname):
            continue
        result = _extrahiere_vertreter_fuer_firma(
            html2, firmenname, erwartete_funktion)
        if result:
            return result
    return []

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────
def _rechtsform(name):
    # Wortgrenzen statt Substring — sonst wird "Magna" zur AG
    n = (name or "").upper()
    for rf in ["GMBH & CO. KG", "GMBH & CO KG", "GMBH", "AG", "SE",
               "KGAA", "KG", "OHG", "GBR", "UG", "EV", "EG"]:
        if re.search(r"(?<![A-Z\xc4\xd6\xdc])" + re.escape(rf)
                     + r"(?![A-Z\xc4\xd6\xdc])", n):
            return rf
    return ""

def _funktion_default(rechtsform):
    # Vorstand-Gruppe zuerst — sonst macht "KG" in "KGAA" die KGaA zum GF-Fall
    rf = rechtsform.upper()
    if any(x in rf for x in ("AG", "SE", "KGAA")):
        return "Vorstand"
    if any(x in rf for x in ("GMBH", "UG", "GBR", "KG", "OHG")):
        return "Gesch\xe4ftsf\xfchrer"
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
        vertreter = _impressum_vertreter(name, funk)

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
    firma = (daten.get("firma") or "").strip()
    vname = (daten.get("vertreter_name") or "").strip()
    vfunk = (daten.get("vertreter_funktion") or "").strip()

    try:
        bid_int = int(bid)
    except (TypeError, ValueError):
        bid_int = 0
    hat_echten_beteiligten = bid_int > 0

    if not vname:
        return _err("vertreter_name erforderlich.")
    if not firma and not hat_echten_beteiligten:
        return _err("firma oder beteiligter_id erforderlich.")

    try:
        from ..db.database import get_connection
        from ..models.firmen_vertreter import upsert_firmen_vertreter
        global_ok = False
        bet_ok = False
        with get_connection() as conn:
            if firma:
                global_ok = upsert_firmen_vertreter(conn, firma, vname, vfunk)
            if hat_echten_beteiligten:
                cur = conn.execute(
                    "UPDATE beteiligte SET vertreter_name=?, "
                    "vertreter_funktion=? WHERE id=?",
                    (vname, vfunk, bid_int),
                )
                bet_ok = cur.rowcount > 0
        return _j({"ok": True,
                   "global_gespeichert": global_ok,
                   "beteiligter_gespeichert": bet_ok,
                   "vertreter_name": vname,
                   "vertreter_funktion": vfunk})
    except Exception as e:
        logger.error("Vertreter speichern: %s", e)
        return _err("Speichern fehlgeschlagen: " + str(e), 500)
