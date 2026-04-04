"""
wdm_regulierung_service.py
===========================
WDM-Regulierungsdaten aus RA-Micro lesen und in das
Abrechnungs-Format des Unfallakten-Systems überführen.

Spaltenstruktur _tbl0WDMDaten (verifiziert mit SQL-Test):
    lPoolId   int
    AktenNr   varchar(15)   – ohne Kürzel, z.B. '31/21'
    sName     nvarchar(53)  – Variablenname, z.B. 'varREPKOSTENSVG'
    Value     ntext         – Wert, z.B. '2.616,71 EUR' oder '650,00'

WDM-Wertformat (aus Testabfrage Akte 31/21):
    - Deutsches Zahlenformat: Punkt = Tausender, Komma = Dezimal
    - EUR-Suffix inkonsistent: '650,00' ODER '650,00 EUR'
    - Datum: 'TT.MM.JJJJ' (Länge 10, z.B. '23.03.2021')
    - Nullwerte: '0,00' oder '0,00 EUR' → ignorieren
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── WDM-Variable → position_key ──────────────────────────────────────────────
# Regulierungsvariablen (gezahlte Beträge, Suffix G)
WDM_REGULIERUNG_MAP: dict[str, str] = {
    "varREPKOSTENSVG": "rep_gutachten_netto",
    "varREPKOSTENG":   "rep_rechnung_netto",
    "varKOSTENSVG":    "sv_kosten",
    "varKOSTENNBG":    "kostennb",
    "varABSCHLEPPG":   "abschleppkosten",
    "varSTANDKOSTENG": "standkosten",
    "varMIETWAGENG":   "mietwagenkosten",
    "varVERDIENSTG":   "verdienstausfall",
    "varANABKOSTENG":  "anabmeldekosten",
    "varHAUSHALTG":    "haushalt",
    "varUNKOSTENG":    "unkostenpauschale",
    "varWERTMINDG":    "wertminderung",
    "varNUTZUNGSAG":   "nutzungsausfall",
    "varSGVORSCHUSS":  "schmerzensgeld",
    "varVORSCHUSSG":   "vorschuss",
    "varSSCHADEN1G":   "sonstiges_wdm_1",
    "varSSCHADEN2G":   "sonstiges_wdm_2",
    "varSSCHADEN3G":   "sonstiges_wdm_3",
    "varSSCHADEN4G":   "sonstiges_wdm_4",
    "varSSCHADEN5G":   "sonstiges_wdm_5",
    "varSSCHADEN6G":   "sonstiges_wdm_6",
}

# Geforderte Beträge (Schadenseite) für Gegenüberstellung
WDM_FORDERUNG_MAP: dict[str, str] = {
    "rep_gutachten_netto": "varREPKOSTENSV",
    "rep_rechnung_netto":  "varREPKOSTEN",
    "sv_kosten":           "varKOSTENSV",
    "wertminderung":       "varWERTMIND",
    "nutzungsausfall":     "varNUTZUNGSA",
    "schmerzensgeld":      "varSCHMGELD",
    "verdienstausfall":    "varVERDIENST",
    "unkostenpauschale":   "varUNKOSTEN",
    # Sonstige Schäden: Netto-Forderungsbetrag aus WDM (varSSCHADEN{i} = Label, varSSBETRAG{i} = Betrag)
    "sonstiges_wdm_1":    "varSSBETRAG1",
    "sonstiges_wdm_2":    "varSSBETRAG2",
    "sonstiges_wdm_3":    "varSSBETRAG3",
    "sonstiges_wdm_4":    "varSSBETRAG4",
    "sonstiges_wdm_5":    "varSSBETRAG5A",  # RA-Micro Sonderfall: 5A statt 5
    "sonstiges_wdm_6":    "varSSBETRAG6",
}

# Labels für sonstiges_wdm_* (werden auch in POSITION_LABELS_FE gebraucht)
WDM_SONSTIGES_LABELS: dict[str, str] = {
    "sonstiges_wdm_1": "Sonstiger Schaden 1",
    "sonstiges_wdm_2": "Sonstiger Schaden 2",
    "sonstiges_wdm_3": "Sonstiger Schaden 3",
    "sonstiges_wdm_4": "Sonstiger Schaden 4",
    "sonstiges_wdm_5": "Sonstiger Schaden 5",
    "sonstiges_wdm_6": "Sonstiger Schaden 6",
}


# ══════════════════════════════════════════════════════════════════════════════
# ÖFFENTLICHE SCHNITTSTELLE
# ══════════════════════════════════════════════════════════════════════════════

def lade_wdm_regulierung(akte_id: str) -> Optional[dict]:
    """
    Liest alle Regulierungsvariablen aus _tbl0WDMDaten für eine Akte.
    Nutzt get_ramicro_connection() aus connector.py (korrekte TDS-Version,
    RAMICRO_AKTIV-Prüfung, as_dict=True).

    akte_id: Aktenzeichen OHNE Kürzel, z.B. '31/21'
    Gibt Dict {sName: Value} zurück oder None bei Fehler/keine Daten.
    """
    from .connector import get_ramicro_connection, RaMicroNichtAktiv, RaMicroVerbindungsFehler

    variablen = list(WDM_REGULIERUNG_MAP.keys()) + [
        "varRGGDAT", "varQUOTEG",
        *WDM_FORDERUNG_MAP.values()
    ]

    sql = (
        "SELECT sName, CAST(Value AS NVARCHAR(500)) AS Wert "
        "FROM _tbl0WDMDaten "
        "WHERE AktenNr = %s "
        f"AND sName IN ({', '.join(['%s'] * len(variablen))})"
    )

    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, (akte_id, *variablen))
            rows = cur.fetchall()
        if not rows:
            return None
        # as_dict=True → row ist dict mit Spaltennamen als Key
        return {row["sName"]: row["Wert"] for row in rows}
    except RaMicroNichtAktiv:
        logger.info("WDM-Regulierung: RA-Micro nicht aktiv (RAMICRO_AKTIV != true)")
        return None
    except RaMicroVerbindungsFehler as e:
        logger.warning("WDM-Regulierung: Verbindung fehlgeschlagen: %s", e)
        return None
    except Exception as e:
        logger.warning("WDM-Regulierung Lesefehler für %s: %s", akte_id, e)
        return None


def wdm_zu_abrechnung(wdm_dict: dict) -> Optional[dict]:
    """
    Wandelt WDM-Dict in Abrechnungs-Format um.
    Gibt None zurück wenn keine Regulierungsdaten vorhanden.

    Beispiel Input:
    {
        "varREPKOSTENSVG": "2.616,71 EUR",
        "varKOSTENSVG":    "650,00",
        "varWERTMINDG":    "350,00 EUR",
        "varRGGDAT":       "23.03.2021",
        "varQUOTEG":       "100,00 EUR",
    }
    """
    positionen = []

    for wdm_var, position_key in WDM_REGULIERUNG_MAP.items():
        betrag_reguliert = parse_wdm_betrag(wdm_dict.get(wdm_var))
        if betrag_reguliert <= 0:
            continue

        # Geforderten Betrag aus WDM-Schadenseite
        forderungs_var = WDM_FORDERUNG_MAP.get(position_key)
        if forderungs_var:
            betrag_gefordert = parse_wdm_betrag(wdm_dict.get(forderungs_var))
        else:
            betrag_gefordert = 0.0

        # Fallback: gefordert = reguliert wenn kein Schadenwert vorhanden
        if betrag_gefordert <= 0:
            betrag_gefordert = betrag_reguliert

        positionen.append({
            "position_key":      position_key,
            "position_label":    WDM_SONSTIGES_LABELS.get(position_key),
            "betrag_gefordert":  betrag_gefordert,
            "betrag_reguliert":  betrag_reguliert,
            "kuerzungsart_id":   None,
            "kuerzung_freitext": "",
            "fuer_klage_vorgemerkt": False,
        })

    if not positionen:
        logger.debug("wdm_zu_abrechnung: keine Regulierungspositionen > 0 gefunden")
        return None

    datum_raw  = wdm_dict.get("varRGGDAT", "")
    datum_iso  = parse_wdm_datum(datum_raw)
    quote      = parse_wdm_betrag(wdm_dict.get("varQUOTEG", "100"))

    gesamt_gefordert = round(sum(p["betrag_gefordert"] for p in positionen), 2)
    gesamt_reguliert = round(sum(p["betrag_reguliert"] for p in positionen), 2)
    gesamt_kuerzung  = round(gesamt_gefordert - gesamt_reguliert, 2)

    return {
        "datum":               datum_iso,
        "versicherung":        "",      # WDM hat kein eigenes Versicherungsfeld
        "referenz_nr":         "",
        "haftungsart":         "vollhaftung" if quote >= 99.9 else "quote",
        "haftungsquote":       quote,
        "haftungsbegruendung": "",
        "notizen":             "Aus RA-Micro WDM importiert",
        "quelle":              "wdm",
        "wdm_importiert":      1,
        "gesamt_gefordert":    gesamt_gefordert,
        "gesamt_reguliert":    gesamt_reguliert,
        "gesamt_kuerzung":     max(0.0, gesamt_kuerzung),
        "positionen":          positionen,
    }


def hat_wdm_regulierung(wdm_dict: dict) -> bool:
    """Schnell-Check: Hat die Akte überhaupt WDM-Regulierungsdaten?"""
    if not wdm_dict:
        return False
    return any(
        parse_wdm_betrag(wdm_dict.get(v, "0")) > 0
        for v in WDM_REGULIERUNG_MAP
    )


# ══════════════════════════════════════════════════════════════════════════════
# PARSING
# ══════════════════════════════════════════════════════════════════════════════

def parse_wdm_betrag(wert_str: Optional[str]) -> float:
    """
    Parst WDM-Geldwerte in float.

    Eingabeformate (beide kommen vor):
        '2.616,71 EUR'  →  2616.71
        '650,00'        →  650.0
        '0,00 EUR'      →  0.0
        None / ''       →  0.0
    """
    if not wert_str:
        return 0.0
    s = str(wert_str).strip()
    s = s.replace(" EUR", "").strip()   # EUR-Suffix entfernen (inkonsistent!)
    s = s.replace(".", "")              # Tausenderpunkt entfernen
    s = s.replace(",", ".")             # Dezimalkomma → Punkt
    try:
        return round(float(s), 2)
    except (ValueError, TypeError):
        logger.debug("parse_wdm_betrag: konnte '%s' nicht parsen", wert_str)
        return 0.0


def parse_wdm_datum(datum_str: Optional[str]) -> str:
    """
    Parst WDM-Datum 'TT.MM.JJJJ' → ISO 'JJJJ-MM-TT'.
    Gibt Leerstring zurück wenn nicht parsebar.

    Aus SQL-Test verifiziert: Länge immer 10, Format 'TT.MM.JJJJ'.
    """
    if not datum_str:
        return ""
    s = str(datum_str).strip()
    if len(s) != 10:
        return s  # unbekanntes Format → unverändert
    try:
        return datetime.strptime(s, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        logger.debug("parse_wdm_datum: konnte '%s' nicht parsen", datum_str)
        return s
