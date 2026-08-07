"""
Werkstatt-Verweisbetrieb-Prüfung
==================================
Parst Regulierungsschreiben / Prüfberichte nach Verweisbetrieben
und prüft die echte Entfernung via OpenRouteService.

Verwendung:
    from .services.werkstatt_service import extrahiere_verweisbetrieb, pruefe_entfernung

Ablauf:
    1. PDF-Text → extrahiere_verweisbetrieb() → {name, adresse, km_genannt}
    2. ORS Geocoding → Koordinaten Mandant + Werkstatt
    3. ORS Routing → echte Fahrkilometer
    4. Vergleich → Textbaustein wenn Abweichung erheblich (> 15 km Grenze)
"""

import os
import re
import json
import logging
import urllib.request
import urllib.parse
from datetime import date

logger = logging.getLogger(__name__)

ORS_API_KEY = os.environ.get("ORS_APIKEY", "")
ORS_BASE    = "https://api.openrouteservice.org"

# ── Schlagwörter für Verweisbetrieb-Erkennung ──────────────────────────────────
TRIGGER_MUSTER = re.compile(
    r"""(
        Verweisbetrieb|Verweis(?:betrieb)?|
        Referenzbetrieb|Referenzwerkstatt|
        Alternativwerkstatt|Alternativ(?:werkstatt)?|
        Werkstattalternative|
        alternative\s+Werkstatt|
        alternative\s+Reparaturm[öo]glichkeit|
        alternative\s+Reparatur|
        g[üu]nstigere?\s+(?:und\s+gleichwertige\s+)?Reparaturm[öo]glichkeit|
        g[üu]nstigere?\s+(?:und\s+gleichwertige\s+)?Werkstatt|
        freie\s+Fachwerkstatt|
        gleichwertige(?:r|n)?\s+(?:Fach)?[Ww]erkstatt|
        Karosserie(?:-|\s+)Fachbetrieb|
        Kfz[-\s]Meisterfachbetrieb
    )""",
    re.VERBOSE | re.IGNORECASE
)

# Entfernung: "3,2 km" / "ca. 8 km" / "ca.8km"
ENTFERNUNG_MUSTER = re.compile(
    r"(?:ca\.?\s*|ungef[äa]hr\s*)?(\d+[,.]?\d*)\s*km",
    re.IGNORECASE
)

# Werkstattname: Zeile die nach Trigger-Abschnitt kommt
# ControlExpert-Format: "Verwendeter Referenzbetrieb\nName\nStraße\nPLZ Ort\nTel"
REFERENZBETRIEB_BLOCK = re.compile(
    r"Verwendeter\s+Referenzbetrieb\s*\n(.*?)\n(.*?)\n(\d{5}\s+[^\n]+)",
    re.IGNORECASE | re.DOTALL
)

# Allgemeiner Adress-Block nach Trigger (Name, Straße, PLZ Ort)
WERKSTATT_ADRESSE = re.compile(
    r"(?:Verweisbetrieb|Referenzbetrieb|Referenzwerkstatt|Alternativwerkstatt"
    r"|Werkstattalternative)\s*[:\n]\s*"
    r"([^\n]{5,80})\n"         # Name
    r"([^\n]{5,80})\n"         # Straße
    r"(\d{5}[^\n]{3,40})",     # PLZ + Ort
    re.IGNORECASE
)

# ControlExpert-spezifisches Muster (Seite 3 des Prüfberichts)
CONTROLEXPERT_MUSTER = re.compile(
    r"(?:Verwendeter\s+Referenzbetrieb|Referenzbetrieb)\s*\n"
    r"([^\n]+)\n"                         # Name
    r"([^\n]+)\n"                         # Straße
    r"(\d{5}[^\n]+)\n"                    # PLZ Ort
    r"(?:(\d[\d\s/\-]+)\n)?"             # Telefon optional
    r"Entfernung\s+zum\s+Anspruchsteller:\s*(\d+[,.]?\d*)\s*km",
    re.IGNORECASE
)

# VHV-Blockformat: "Für die Korrekturberechnung haben wir den Reparaturbetrieb
# \n\n Name \n Straße \n PLZ Ort \n ... Entfernungskilometer: X km ... berücksichtigt."
VHV_KORREKTUR_BLOCK = re.compile(
    r"F[üu]r\s+die\s+Korrekturberechnung\s+haben\s+wir\s+den\s+Reparaturbetrieb\s*\n+"
    r"([^\n]{3,80})\n"          # Name
    r"([^\n]{3,80})\n"          # Straße
    r"(\d{5}\s+[^\n]{2,40})",   # PLZ + Ort
    re.IGNORECASE
)

VHV_ENTFERNUNG_MUSTER = re.compile(
    r"Entfernungskilometer:\s*(\d+[,.]?\d*)\s*km", re.IGNORECASE)

VHV_TELEFON_MUSTER = re.compile(r"Telefon:\s*([\d\s/\-]+)")


def extrahiere_verweisbetrieb(text: str) -> dict:
    """
    Extrahiert Verweisbetrieb-Daten aus dem Volltext eines Prüfberichts
    oder Regulierungsschreibens.

    Returns:
        {
            gefunden: bool,
            name: str,
            adresse: str,
            plz_ort: str,
            km_genannt: float | None,
            quelle: str,   # "controlexpert" | "regex" | "triggerkontext"
        }
    """
    if not text:
        return {"gefunden": False}

    # ── Stufe 1: ControlExpert-Format (häufigster Fall) ────────────────────
    m = CONTROLEXPERT_MUSTER.search(text)
    if m:
        km_str = (m.group(5) or "").replace(",", ".")
        return {
            "gefunden":   True,
            "name":       m.group(1).strip(),
            "adresse":    m.group(2).strip(),
            "plz_ort":    m.group(3).strip(),
            "telefon":    (m.group(4) or "").strip(),
            "km_genannt": float(km_str) if km_str else None,
            "quelle":     "controlexpert",
        }

    # ── Stufe 1b: VHV-Blockformat (verwendeter Betrieb der Korrekturberechnung) ──
    m = VHV_KORREKTUR_BLOCK.search(text)
    if m:
        # Nur bis "berücksichtigt." suchen — danach folgen Alternativ-Betriebe
        ende = text.find("berücksichtigt", m.end())
        fenster = text[m.end():ende] if ende != -1 else text[m.end():m.end() + 600]
        km_m = VHV_ENTFERNUNG_MUSTER.search(fenster)
        tel_m = VHV_TELEFON_MUSTER.search(fenster)
        return {
            "gefunden":   True,
            "name":       m.group(1).strip(),
            "adresse":    m.group(2).strip(),
            "plz_ort":    m.group(3).strip(),
            "telefon":    tel_m.group(1).strip() if tel_m else "",
            "km_genannt": float(km_m.group(1).replace(",", ".")) if km_m else None,
            "quelle":     "vhv_block",
        }

    # ── Stufe 2: Allgemeines Adress-Block-Muster ───────────────────────────
    m = WERKSTATT_ADRESSE.search(text)
    if m:
        # Entfernung aus umliegendem Kontext suchen
        kontext = text[max(0, m.start()-200):m.end()+300]
        km = _extrahiere_km(kontext)
        return {
            "gefunden":   True,
            "name":       m.group(1).strip(),
            "adresse":    m.group(2).strip(),
            "plz_ort":    m.group(3).strip(),
            "telefon":    "",
            "km_genannt": km,
            "quelle":     "regex_adresse",
        }

    # ── Stufe 3: Trigger-Kontext ohne strukturierte Adresse ───────────────
    m_trigger = TRIGGER_MUSTER.search(text)
    if m_trigger:
        # Kontext 500 Zeichen nach Trigger
        kontext = text[m_trigger.start():m_trigger.start()+500]
        km = _extrahiere_km(kontext)

        # PLZ suchen für Adress-Hinweis
        plz_m = re.search(r"(\d{5})\s+([A-ZÄÖÜ][a-zäöüA-Z\s\-]+)", kontext)
        plz_ort = f"{plz_m.group(1)} {plz_m.group(2).strip()}" if plz_m else ""

        # Name: erste Zeile nach Trigger die Großbuchstaben enthält
        zeilen = kontext.split("\n")
        name = ""
        for z in zeilen[1:5]:
            z = z.strip()
            if len(z) > 5 and any(c.isupper() for c in z[:3]):
                name = z
                break

        # Plausibilitätsbremse: ohne PLZ-Zeile ist der Trigger nur Floskel
        # ("Wird eine Referenzwerkstatt benannt, ...") — kein Treffer
        if plz_ort:
            return {
                "gefunden":   True,
                "name":       name,
                "adresse":    "",
                "plz_ort":    plz_ort,
                "telefon":    "",
                "km_genannt": km,
                "quelle":     "triggerkontext",
            }

    return {"gefunden": False}


def _extrahiere_km(text: str):
    """Extrahiert ersten Km-Wert aus Text. Gibt float oder None zurück."""
    m = ENTFERNUNG_MUSTER.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


# ── OpenRouteService ───────────────────────────────────────────────────────────

def _bereinige_adresse(adresse: str) -> str:
    """
    Entfernt Firmennamen aus einer Adresse.
    "Karosserie Hanselmann, Offenbacher Landstr. 368, 60599 Frankfurt"
    → "Offenbacher Landstr. 368, 60599 Frankfurt am Main"
    """
    teile = [t.strip() for t in adresse.split(",")]
    plz_idx = None
    for i, t in enumerate(teile):
        # PLZ = genau 5 aufeinanderfolgende Ziffern
        if re.search("[0-9]{5}", t):
            plz_idx = i
            break
    if plz_idx is None or plz_idx == 0:
        return adresse
    # Straße ist der Teil direkt vor PLZ, dann PLZ+Ort
    return ", ".join(teile[plz_idx - 1:])


def geocode(adresse: str):
    """
    Adresse → (lat, lng) via ORS Geocoding.
    Bereinigt Firmennamen aus der Adresse vor dem Geocoding.
    Returns (lat, lng) tuple oder None.
    """
    if not ORS_API_KEY:
        logger.warning("ORS_APIKEY nicht gesetzt")
        return None

    # Firmenname entfernen – ORS kommt mit reiner Straße+PLZ+Ort besser zurecht
    adresse_clean = _bereinige_adresse(adresse)
    if adresse_clean != adresse:
        logger.debug("Geocoding bereinigt: '%s' → '%s'", adresse, adresse_clean)

    try:
        q = urllib.parse.quote(adresse_clean)
        url = (f"{ORS_BASE}/geocode/search"
               f"?api_key={ORS_API_KEY}"
               f"&text={q}"
               f"&boundary.country=DE"
               f"&size=1")
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": "Kanzlei-Tool/1.0",
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        features = data.get("features", [])
        if not features:
            logger.warning("ORS Geocoding: Keine Treffer für '%s'", adresse_clean)
            return None
        coords = features[0]["geometry"]["coordinates"]  # GeoJSON: [lng, lat]
        lat, lng = coords[1], coords[0]
        logger.debug("Geocoding '%s' → lat=%.5f lng=%.5f", adresse_clean, lat, lng)
        # Plausibilitätsprüfung: Deutschland liegt zwischen lat 47–55, lng 6–15
        if not (47.0 <= lat <= 55.5 and 5.5 <= lng <= 15.5):
            logger.error(
                "Geocoding Plausibilitätsfehler: '%s' → lat=%.4f lng=%.4f (außerhalb DE)",
                adresse_clean, lat, lng
            )
            return None
        return (lat, lng)
    except Exception as e:
        logger.error("ORS Geocoding '%s': %s", adresse_clean, e)
        return None


def berechne_fahrtstrecke(von_lat, von_lng, nach_lat, nach_lng):
    """
    Berechnet Fahrtstrecke in km und Fahrzeit in Minuten via ORS Routing.
    Returns {"km": float, "minuten": int} oder None.
    """
    if not ORS_API_KEY:
        return None
    try:
        url = f"{ORS_BASE}/v2/directions/driving-car"
        body = json.dumps({
            "coordinates": [
                [von_lng, von_lat],    # ORS erwartet [lng, lat]
                [nach_lng, nach_lat],
            ]
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": ORS_API_KEY,
            "User-Agent": "Kanzlei-Tool/1.0",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        summary = data["routes"][0]["summary"]
        km      = round(summary["distance"] / 1000, 1)
        minuten = round(summary["duration"] / 60)
        return {"km": km, "minuten": minuten}
    except Exception as e:
        logger.error("ORS Routing: %s", e)
        return None


def pruefe_entfernung(mandant_adresse: str, werkstatt_adresse: str,
                      werkstatt_name: str = "", km_genannt: float = None):
    """
    Vollständige Entfernungsprüfung: Geocoding + Routing + Vergleich.

    Returns:
        {
            ok: bool,
            mandant_adresse: str,
            werkstatt_adresse: str,
            werkstatt_name: str,
            km_genannt: float | None,
            km_echt: float | None,
            minuten: int | None,
            abweichung_km: float | None,     # positiv = weiter als behauptet
            unzumutbar: bool,                # > 15 km Grenze
            textbaustein: str,
            fehler: str | None,
        }
    """
    result = {
        "ok":                False,
        "mandant_adresse":   mandant_adresse,
        "werkstatt_adresse": werkstatt_adresse,
        "werkstatt_name":    werkstatt_name,
        "km_genannt":        km_genannt,
        "km_echt":           None,
        "minuten":           None,
        "abweichung_km":     None,
        "unzumutbar":        False,
        "textbaustein":      "",
        "fehler":            None,
    }

    # Geocoding
    koords_mandant  = geocode(mandant_adresse)
    koords_werkstatt = geocode(werkstatt_adresse)

    if not koords_mandant:
        result["fehler"] = f"Mandant-Adresse konnte nicht geocodiert werden: {mandant_adresse}"
        return result
    if not koords_werkstatt:
        result["fehler"] = f"Werkstatt-Adresse konnte nicht geocodiert werden: {werkstatt_adresse}"
        return result

    # Routing
    routing = berechne_fahrtstrecke(
        koords_mandant[0], koords_mandant[1],
        koords_werkstatt[0], koords_werkstatt[1],
    )
    if not routing:
        result["fehler"] = "Entfernungsberechnung fehlgeschlagen (ORS Routing)"
        return result

    km_echt = routing["km"]
    result["ok"]      = True
    result["km_echt"] = km_echt
    result["minuten"] = routing["minuten"]

    if km_genannt is not None:
        result["abweichung_km"] = round(km_echt - km_genannt, 1)

    # Unzumutbarkeit: BGH-Grenze ca. 15–20 km (Großraum Frankfurt: 15 km)
    result["unzumutbar"] = km_echt > 15.0

    # Textbaustein generieren
    result["textbaustein"] = _erstelle_textbaustein(
        werkstatt_name=werkstatt_name,
        werkstatt_adresse=werkstatt_adresse,
        km_echt=km_echt,
        km_genannt=km_genannt,
        minuten=routing["minuten"],
        datum=date.today().strftime("%d.%m.%Y"),
    )

    return result


def _erstelle_textbaustein(werkstatt_name, werkstatt_adresse, km_echt,
                           km_genannt, minuten, datum):
    """
    Erstellt den Textbaustein nach dem Muster der Kanzlei
    (basierend auf dem vorhandenem RTF-Textbaustein).
    """
    name_adresse = werkstatt_name
    if werkstatt_adresse and werkstatt_name:
        name_adresse = f"{werkstatt_name}, {werkstatt_adresse}"
    elif werkstatt_adresse:
        name_adresse = werkstatt_adresse

    km_echt_str   = str(km_echt).replace(".", ",")
    km_gen_str    = str(km_genannt).replace(".", ",") if km_genannt else None

    # Abweichungshinweis
    if km_genannt and km_echt > km_genannt:
        abw = round(km_echt - km_genannt, 1)
        abw_str = str(abw).replace(".", ",")
        abweichung_satz = (
            f" Damit ist die tatsächliche Entfernung um {abw_str} km größer "
            f"als von der Versicherung angegeben."
        )
    else:
        abweichung_satz = ""

    baustein = (
        f"Den dortigen Verweis auf den Referenzbetrieb {name_adresse} "
        f"können wir nicht akzeptieren: Der genannte Verweisbetrieb ist "
        f"von unserem Mandanten tatsächlich {km_echt_str} km entfernt "
        f"(Fahrzeit ca. {minuten} Minuten; Quelle: OpenRouteService / "
        f"OpenStreetMap, Abfrage vom {datum}).{abweichung_satz} "
        f"Im hiesigen Gerichtsbezirk wird aber im Großraum Frankfurt eine "
        f"Verweisung auf einen Betrieb in Entfernung von mehr als 15 km "
        f"bereits nicht mehr als zumutbar betrachtet. "
        f"Wir verweisen auf die Urteile des AG Darmstadt, Urteil vom "
        f"30.12.2016, Aktenzeichen 315 C 156, sowie des AG Frankfurt, "
        f"Urteil vom 29.01.2016, Aktenzeichen 32 C 3096/15. "
        f"Auch hat das AG Hanau jüngst entschieden, dass ein Verweisbetrieb "
        f"in einer Entfernung von mehr als 15 km nicht mehr möglich ist "
        f"(vgl. AG Hanau, Urteil vom 04.05.2023). "
        f"Es ist daher der volle Betrag wie im Gutachten angegeben zu erstatten. "
        f"Wir bitten um Prüfung und um Fortsetzung der Regulierung."
    )
    return baustein
