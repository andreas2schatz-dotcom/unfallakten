"""
Modul 8 – Wiedervorlage Service
==================================
Alle SQL-Abfragen gegen den RA-Micro SQL Server.
Nur Lesezugriff. Keine Schreiboperationen auf RA-Micro.

HV-Kennzeichen in RA-Micro (aus echten Daten ermittelt):
    'GHPV' = Gegnerische HaftPflichtVersicherung  ← Ziel des Briefs
    ''     = Mandant (Art=1, kein Kennzeichen)
    'SV'   = Sachverständiger
    'OA'   = Ordnungsamt / gegnerischer Anwalt
    'PO'   = Polizei
    'RSV'  = Rechtsschutzversicherung

Filter-Strategie für Stellungnahmen:
    sWiedervorlagegrund LIKE '%nahme%'
    → Fängt: "Stellungnahme Gegner", "Stellungnahme Gegner?schieben!", Tippfehler
    → Fängt NICHT: "Stellungnahme Mandant", "Stellungnahme SV"
"""

import logging
from datetime import date
from typing import Optional
from .connector import get_ramicro_connection

logger = logging.getLogger(__name__)

# Kennzeichen der gegnerischen Haftpflichtversicherung in tblAktenBeteiligte
# Aus echten RA-Micro Daten ermittelt (sbergebnis6.csv)
GHPV_KENNZEICHEN = "GHPV"


# Vordefinierte RA-Micro Wiedervorlagengründe (fest einprogrammiert, keine DB-Tabelle)
# Quelle: RA-Micro Handbuch / empirisch ermittelt
RAMICRO_WV_GRUENDE: dict[int, str] = {
    5:  "Stellungnahme Gegner",
    6:  "Stellungnahme Mandant",
    9:  "Entscheidung/Gericht",
    10: "Ermittlungsakte",
    11: "Stellungnahme Mandant",   # in dieser RA-Micro Installation
    12: "Zahlung Gegner",
    16: "Stellungnahme Gegner?",   # in dieser RA-Micro Installation
    17: "Reaktion Rechtsschutz",
    18: "Deckungszusage",
    19: "Sachstand",
    20: "Fristverlängerung",
    21: "Klage",
    22: "Urteil",
    23: "Vergleich",
    26: "Gutachten",
    28: "Sachverständiger",
    31: "Mahnbescheid",
    32: "Vollstreckung",
    34: "Erneute EV möglich",
    35: "Insolvenzverfahren",
    36: "Zwangsvollstreckung",
    38: "Kostenantrag",
    39: "Honorar",
    43: "Akteneinsicht",
    46: "Berufung",
    49: "Revision",
    51: "Einspruch",
    54: "Widerspruch",
    55: "Beschwerde",
    58: "Verhandlungstermin",
    60: "Anhörungstermin",
    62: "Schriftsatz",
    69: "Post",
    71: "Telefonat",
    75: "Fristablauf",
    81: "Rückruf",
    88: "Besprechung",
    91: "Abrechnung",
    94: "Akte schließen",
    99: "Sonstiges",
}


def _loeseWvGrund(sGrund: str, iGrund) -> str:
    """Gibt den WV-Grund als Text zurück.
    Nutzt sWiedervorlagegrund wenn vorhanden, sonst Lookup via iWiedervorlageGrund."""
    if sGrund:
        return sGrund
    if iGrund:
        try:
            return RAMICRO_WV_GRUENDE.get(int(iGrund), f"Grund {iGrund}")
        except (ValueError, TypeError):
            pass
    return ""



def hole_faellige_wiedervorlagen(
    nur_heute: bool = False,
    sachbearbeiter: Optional[str] = None,
    limit: int = 200,
    nur_stellungnahme: bool = True,
    grund_filter: Optional[str] = None,
    aktenzeichen: Optional[str] = None,
) -> list[dict]:
    """
    Gibt fällige Wiedervorlagen zurück, inklusive Akten- und Adressdaten.

    Args:
        nur_heute:        True = nur exakt heute fällige WV
        sachbearbeiter:   Kürzel filtern (z.B. "AS"), None = alle
        limit:            Max. Anzahl Ergebnisse (max. 500)
        nur_stellungnahme: True = nur '%nahme%' Gründe, False = alle Gründe
        grund_filter:     Exakter WV-Grund als Filter, None = alle
        aktenzeichen:     Aktenzeichen filtern (z.B. "285/26TB"), None = alle
    """
    limit = min(int(limit), 500)

    datum_filter = (
        "CAST(w.dtWiedervorlage AS DATE) = CAST(GETDATE() AS DATE)"
        if nur_heute else
        "CAST(w.dtWiedervorlage AS DATE) <= CAST(GETDATE() AS DATE)"
    )

    sb_filter = "AND w.sWiedervorlageSachbearbeiter = %(sb)s" if sachbearbeiter else ""
    az_filter = "AND a.sAktenNummer = %(az)s" if aktenzeichen else ""

    if grund_filter:
        grund_sql = "AND w.sWiedervorlagegrund = %(grund)s"
    elif nur_stellungnahme:
        # Stellungnahmen können als Text (sWiedervorlagegrund LIKE '%nahme%')
        # ODER als Zahl (iWiedervorlageGrund IN (5,6,11,16)) gespeichert sein.
        # Beide Varianten abfragen.
        grund_sql = """AND (
            w.sWiedervorlagegrund LIKE '%nahme%'
            OR w.iWiedervorlageGrund IN (5, 6, 11, 16)
        )""" 
    else:
        grund_sql = ""

    # TOP statt OFFSET/FETCH NEXT - robuster in SQL Server 2014 mit pymssql
    sql = """
        SELECT TOP %(limit)s
            w.GUIDWiedervorlage,
            w.dtWiedervorlage,
            w.sWiedervorlagegrund,
            w.iWiedervorlageGrund,
            w.sBemerkung                        AS wv_bemerkung,
            w.sWiedervorlageSachbearbeiter       AS wv_sachbearbeiter_kuerzel,

            a.GUIDAkte,
            a.sAktenNummer,
            a.sAktenKurzBezeichnung,
            a.sAktenBezeichnung,
            a.iReferat,
            a.sAktenBezeichnung,
            a.sMandant,
            a.sGegner,
            a.sAktenSachbearbeiter              AS akte_sachbearbeiter_kuerzel,

            b.GUIDAdresse,
            b.sBeteiligtenKennzeichen,
            b.sBetreffZeile1,
            b.sBetreffZeile2,
            b.sBetreffZeile3,
            b.iAdressnummer,

            adr.sErsteAdresszeile,
            adr.sNachname                       AS adr_name,
            adr.sVorname                        AS adr_vorname,
            adr.[sStraße]                        AS adr_strasse,
            adr.sPLZ                            AS adr_plz,
            adr.sOrt                            AS adr_ort,
            adr.sEMail                          AS adr_email,
            adr.sBriefanrede                    AS adr_briefanrede,
            adr.sAnrede                         AS adr_anrede,
            adr.sTelefon                        AS adr_telefon,
            adr.sTelefax                        AS adr_telefax

        FROM tblAktenWiedervorlagen w
        INNER JOIN tblAkten a
            ON a.GUIDAkte = w.GUIDAkte

        OUTER APPLY (
            SELECT TOP 1
                GUIDAdresse, sBeteiligtenKennzeichen,
                sBetreffZeile1, sBetreffZeile2, sBetreffZeile3, iAdressnummer
            FROM tblAktenBeteiligte
            WHERE GUIDAkte = a.GUIDAkte
              AND iBeteiligtenArt = 2
              AND bDeaktiviert = 0
            ORDER BY CASE sBeteiligtenKennzeichen
                WHEN 'GHPV' THEN 1
                WHEN 'GH'   THEN 1
                WHEN 'G1'   THEN 2
                WHEN 'G2'   THEN 3
                WHEN 'G3'   THEN 4
                ELSE             5
            END
        ) b

        LEFT JOIN tblAdressen adr
            ON adr.GUIDAdresse = b.GUIDAdresse

        WHERE DATUM_FILTER
          GRUND_FILTER
          SB_FILTER
          AZ_FILTER
          AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')

        ORDER BY w.dtWiedervorlage ASC, a.sAktenNummer ASC
    """.replace("DATUM_FILTER", datum_filter) \
       .replace("GRUND_FILTER", grund_sql) \
       .replace("SB_FILTER", sb_filter) \
       .replace("AZ_FILTER", az_filter)

    params = {"limit": limit}
    if sachbearbeiter:
        params["sb"] = sachbearbeiter
    if grund_filter:
        params["grund"] = grund_filter
    if aktenzeichen:
        params["az"] = aktenzeichen

    with get_ramicro_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    logger.info(
        "Wiedervorlagen abgerufen: %d Einträge (nur_heute=%s, sb=%s)",
        len(rows), nur_heute, sachbearbeiter
    )
    return [dict(r) for r in rows]



def _hole_wdm_werte(akten_nr: str) -> dict:
    """
    Lädt alle WDM-Variablen für eine Akte aus _tbl0WDMDaten.
    Gibt ein Dict zurück: {'varU-TAG': '12.03.2026', 'varG-KZ': 'OF-AB 123', ...}
    Leere Werte werden nicht aufgenommen.
    """
    if not akten_nr:
        return {}
    sql = """
        SELECT sName, Value
        FROM _tbl0WDMDaten
        WHERE AktenNr = %(akten_nr)s
          AND Value IS NOT NULL
          AND CAST(Value AS nvarchar(max)) != ''
    """
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql, {"akten_nr": akten_nr})
            rows = cur.fetchall()
        if rows:
            logger.warning("WDM-DEBUG erste Zeile keys: %s", list(rows[0].keys()) if rows else "leer")
            logger.warning("WDM-DEBUG AktenNr=%s Anzahl=%d", akten_nr, len(rows))
        return {row["sName"]: row["Value"] for row in rows}
    except Exception as e:
        logger.warning("WDM-Werte konnten nicht geladen werden für %s: %s", akten_nr, e)
        return {}


def hole_wiedervorlage_details(guid_wiedervorlage: str, adress_nr: Optional[int] = None) -> Optional[dict]:
    """
    Gibt alle Details einer einzelnen Wiedervorlage zurück (für Brief-Generierung).

    Args:
        guid_wiedervorlage: GUID der Wiedervorlage
        adress_nr: Optionale Adressnummer – überschreibt die Fallback-Logik für den Empfänger.

    Returns:
        Dict mit allen Feldern, oder None wenn nicht gefunden.
    """
    sql = """
        SELECT
            w.GUIDWiedervorlage,
            w.dtWiedervorlage,
            w.sWiedervorlagegrund,
            w.iWiedervorlageGrund,
            w.sBemerkung                        AS wv_bemerkung,
            w.sWiedervorlageSachbearbeiter       AS wv_sachbearbeiter_kuerzel,

            a.GUIDAkte,
            a.sAktenNummer,
            a.sAktenKurzBezeichnung,
            a.sAktenBezeichnung,
            a.iReferat,
            a.sAktenBezeichnung,
            a.sMandant,
            a.sGegner,
            a.sAktenSachbearbeiter              AS akte_sachbearbeiter_kuerzel,

            b.GUIDAdresse,
            b.sBeteiligtenKennzeichen,
            b.sBetreffZeile1,
            b.sBetreffZeile2,
            b.sBetreffZeile3,
            b.iAdressnummer,

            adr.sErsteAdresszeile,
            adr.sNachname                       AS adr_name,
            adr.sVorname                        AS adr_vorname,
            adr.[sStraße]                        AS adr_strasse,
            adr.sPLZ                            AS adr_plz,
            adr.sOrt                            AS adr_ort,
            adr.sEMail                          AS adr_email,
            adr.sBriefanrede                    AS adr_briefanrede,
            adr.sAnrede                         AS adr_anrede,
            adr.sTelefon                        AS adr_telefon,
            adr.sTelefax                        AS adr_telefax

        FROM tblAktenWiedervorlagen w
        INNER JOIN tblAkten a
            ON a.GUIDAkte = w.GUIDAkte

        OUTER APPLY (
            SELECT TOP 1
                GUIDAdresse, sBeteiligtenKennzeichen,
                sBetreffZeile1, sBetreffZeile2, sBetreffZeile3, iAdressnummer
            FROM tblAktenBeteiligte
            WHERE GUIDAkte = a.GUIDAkte
              AND iBeteiligtenArt = 2
              AND bDeaktiviert = 0
            ORDER BY CASE sBeteiligtenKennzeichen
                WHEN 'GHPV' THEN 1
                WHEN 'GH'   THEN 1
                WHEN 'G1'   THEN 2
                WHEN 'G2'   THEN 3
                WHEN 'G3'   THEN 4
                ELSE             5
            END
        ) b

        LEFT JOIN tblAdressen adr
            ON adr.GUIDAdresse = b.GUIDAdresse

        WHERE w.GUIDWiedervorlage = %(guid)s
          AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
    """

    with get_ramicro_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, {"guid": guid_wiedervorlage})
        row = cur.fetchone()

    if not row:
        return None

    result = dict(row)

    # Adress-Override: wenn adress_nr angegeben, diese Adresse statt OUTER APPLY laden
    if adress_nr is not None:
        result = _lade_adress_override(result, adress_nr)

    # WDM-Variablen laden (für Platzhalter in Betreffzeilen)
    akten_nr = result.get("sAktenNummer", "")
    result["wdm_werte"] = _hole_wdm_werte(akten_nr)
    return result



def _lade_adress_override(result: dict, adress_nr: int) -> dict:
    """
    Ersetzt die Adressfelder in result durch die Daten der angegebenen Adressnummer.
    Betreffzeilen werden aus tblAktenBeteiligte für diese Adresse geladen.
    Join über iAdressnummer (in tblAktenBeteiligte) → GUIDAdresse → tblAdressen.
    """
    sql_adr = """
        SELECT
            adr.sNachname                       AS adr_name,
            adr.sVorname                        AS adr_vorname,
            adr.[sStraße]                        AS adr_strasse,
            adr.sPLZ                            AS adr_plz,
            adr.sOrt                            AS adr_ort,
            adr.sEMail                          AS adr_email,
            adr.sBriefanrede                    AS adr_briefanrede,
            adr.sAnrede                         AS adr_anrede,
            adr.sTelefon                        AS adr_telefon,
            adr.sTelefax                        AS adr_telefax,
            b.sBetreffZeile1,
            b.sBetreffZeile2,
            b.sBetreffZeile3,
            b.sBeteiligtenKennzeichen
        FROM tblAktenBeteiligte b
        INNER JOIN tblAdressen adr
            ON adr.GUIDAdresse = b.GUIDAdresse
        WHERE b.GUIDAkte      = %(guid_akte)s
          AND b.iAdressnummer = %(adress_nr)s
          AND b.bDeaktiviert  = 0
    """
    try:
        with get_ramicro_connection() as conn:
            cur = conn.cursor()
            cur.execute(sql_adr, {
                "guid_akte": result.get("GUIDAkte"),
                "adress_nr": adress_nr,
            })
            row = cur.fetchone()
        if row:
            override = dict(row)
            result.update(override)
            result["sErsteAdresszeile"] = ""  # ignorieren
        else:
            logger.warning("Adress-Override: kein Beteiligter mit adress_nr=%s in Akte %s",
                           adress_nr, result.get("GUIDAkte"))
    except Exception as e:
        logger.warning("Adress-Override fehlgeschlagen (adress_nr=%s): %s", adress_nr, e)
    return result


def hole_aktenbeteiligte(guid_wiedervorlage: str) -> list:
    """
    Gibt alle aktiven Beteiligten einer Akte zurück (für Adressaten-Dropdown).

    Ermittelt die Akte über die WV-GUID, lädt dann alle Beteiligten
    mit Name und Adressnummer für die Dropdown-Auswahl im Frontend.
    Join über GUIDAdresse (wie alle anderen Abfragen).
    """
    sql = """
        SELECT
            b.iAdressnummer,
            b.GUIDAdresse,
            b.sBeteiligtenKennzeichen           AS kennzeichen,
            b.iBeteiligtenArt                   AS art,
            adr.sNachname,
            adr.sVorname,
            adr.sOrt
        FROM tblAktenWiedervorlagen w
        INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
        INNER JOIN tblAktenBeteiligte b
            ON  b.GUIDAkte    = a.GUIDAkte
            AND b.bDeaktiviert = 0
            AND b.GUIDAdresse IS NOT NULL
        LEFT JOIN tblAdressen adr
            ON adr.GUIDAdresse = b.GUIDAdresse
        WHERE w.GUIDWiedervorlage = %(guid)s
          AND (a.dtAblage IS NULL OR CAST(a.dtAblage AS DATE) = '1899-12-30')
        ORDER BY b.iBeteiligtenArt, b.sBeteiligtenKennzeichen
    """
    with get_ramicro_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, {"guid": guid_wiedervorlage})
        rows = cur.fetchall()

    result = []
    seen = set()
    for r in rows:
        guid_adr = r.get("GUIDAdresse")
        if not guid_adr or guid_adr in seen:
            continue
        seen.add(guid_adr)
        vorname  = r.get("sVorname") or ""
        nachname = r.get("sNachname") or ""
        name = (f"{vorname} {nachname}".strip() if vorname else nachname) or                f"[{r.get('kennzeichen') or 'Beteiligter'}]"
        ort  = r.get("sOrt") or ""
        kz   = r.get("kennzeichen") or ""
        # adress_nr für den Override – nutze iAdressnummer falls vorhanden,
        # sonst GUIDAdresse als Fallback-Identifier
        adress_nr = r.get("iAdressnummer")
        result.append({
            "adress_nr":   adress_nr,
            "guid_adresse": guid_adr,
            "name":        name,
            "ort":         ort,
            "kennzeichen": kz,
            "art":         r.get("art"),
        })
    return result

def hole_wiedervorlagen_statistik() -> dict:
    """
    Übersicht aller offenen WV-Gründe nach Häufigkeit.
    Tippfehler (z.B. "Stellunnahme") erscheinen als eigene Gruppen –
    das spiegelt die tatsächliche Verteilung in RA-Micro wider.
    """
    sql = """
        SELECT
            w.sWiedervorlagegrund,
            COUNT(*)                AS anzahl,
            MIN(w.dtWiedervorlage)  AS aelteste,
            MAX(w.dtWiedervorlage)  AS neueste
        FROM tblAktenWiedervorlagen w
        INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
        WHERE w.sWiedervorlagegrund != ''
        GROUP BY w.sWiedervorlagegrund
        ORDER BY anzahl DESC
    """

    with get_ramicro_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()

    return {"gruppen": [dict(r) for r in rows]}
