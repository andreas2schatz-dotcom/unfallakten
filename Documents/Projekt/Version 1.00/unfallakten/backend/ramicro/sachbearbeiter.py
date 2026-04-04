"""
Modul 8 – Sachbearbeiter-Konfiguration
=========================================
Ordnet RA-Micro Kürzel den vollständigen Namen und Titeln zu.
Diese Zuordnung einmalig pflegen wenn sich das Team ändert.

RA-Micro speichert nur Kürzel (z.B. "AS") in tblAkten.sAktenSachbearbeiter.
Eine Stammdatentabelle mit Vollnamen existiert in der DB nicht.
"""

# Kürzel → {"name": Vollname, "titel": Berufsbezeichnung}
SACHBEARBEITER: dict[str, dict] = {
    "AS": {"name": "Andreas Schatz",    "titel": "Rechtsanwalt"},
    "CO": {"name": "Claudia Ostarek",   "titel": "Rechtsanwältin"},
    "EI": {"name": "Elsa Ihl",          "titel": "Rechtsanwaltsfachangestellte"},
    "SK": {"name": "Sophie Koch",       "titel": "Rechtsanwaltsfachangestellte"},
    "SN": {"name": "Susanne Neumann",   "titel": "Rechtsanwaltsfachangestellte"},
    "TB": {"name": "Tanja Brunner",     "titel": "Rechtsanwalts- und Notarfachangestellte"},
    "PK": {"name": "Peter Koch",        "titel": "Rechtsanwalt"},
    "CS": {"name": "Carina Salvagnin",  "titel": "Rechtsanwältin"},
    "MM": {"name": "Monika Mieth",      "titel": "Rechtsanwältin"},
    "AH": {"name": "Alexander Herbert", "titel": "Rechtsanwalt"},
}

# Kennzeichen der gegnerischen Haftpflichtversicherung in tblAktenBeteiligte
# RA-Micro verwendet üblicherweise "HV" – bitte prüfen und ggf. anpassen
# Kennzeichen der GHPV in tblAktenBeteiligte (aus echten Daten ermittelt)
HV_KENNZEICHEN = ("GHPV", "G1", "G2", "G3")   # Priorität: GHPV > G1 > G2 > G3


def hole_sachbearbeiter(kuerzel: str) -> dict:
    """
    Gibt Name und Titel für ein Sachbearbeiter-Kürzel zurück.
    Fallback: Kürzel als Name, leerer Titel.
    """
    if not kuerzel:
        return {"name": "Kanzlei Koch, Schatz & Kollegen", "titel": "Rechtsanwälte"}
    sb = SACHBEARBEITER.get(kuerzel.upper())
    if sb and sb.get("name"):
        return sb
    # Kürzel unbekannt oder Name noch nicht gepflegt → Kürzel als Platzhalter
    return {"name": f"[{kuerzel}]", "titel": "Rechtsanwalt"}
