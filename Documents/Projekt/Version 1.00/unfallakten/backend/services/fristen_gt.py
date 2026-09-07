r"""Liest die RA-MICRO-Fristen aus dem Kalenderbaum.

    Z:\RA\Kalender\GT\<MM>M\<TT>

RA-MICRO fuehrt Fristen getrennt von den Wiedervorlagen und legt sie in
KEINER der acht SQL-Datenbanken ab. Nachgewiesen am 2026-09-07 mit einer
Testfrist (Beginn 31.12.2029, Ende 10.01.2030): keine der 141 Tabellen wuchs,
keine der 119 Datumsspalten enthielt das Datum -- geschrieben wurden die
Tagesdatei und ihr Index.

Aufbau eines Satzes, ein Feld je Zeile, CRLF, CP437:

    [274/25]                    Aktennummer, beginnt den Satz
    10.01.30                    Fristende -- danach heisst auch die Datei
                                Uhrzeit (bei Fristen fast immer leer/00:00)
    #Frist                      Kennung; ohne sie ist der Satz ein Termin
    31.12.29                    Fristbeginn
    ZZTESTFRIST0907             Freitext
    AS                          Sachbearbeiter der Frist
    Schatz/OWi                  Aktenkurzbezeichnung
    Berufung                    Fristengrund, aus der Maske Mas\FRIV.MSK
    AZ: 5 OWi 2871 Js 26177/2   Gerichtsaktenzeichen (optional)
    03.09.26                    Erledigt am (optional)
    PK                          Erledigt von (optional)

Der Erledigt-Vermerk ist statistisch erkannt: 3010 der 4293 vergangenen
Fristen tragen ihn, aber nur 2 der zukuenftigen.

Der Mount ist read-only. Erledigt wird weiterhin in RA-MICRO.
"""
import datetime
import os
import re
from typing import List, Optional, Tuple

# Feldpositionen im Satz
FELD_AKTENNUMMER = 0
FELD_FRISTENDE = 1
FELD_UHRZEIT = 2
FELD_KENNUNG = 3
FELD_FRISTBEGINN = 4
FELD_TEXT = 5
FELD_SACHBEARBEITER = 6
FELD_KURZBEZEICHNUNG = 7
FELD_GRUND = 8
FELD_GERICHTS_AZ = 9
FELD_ERLEDIGT_AM = 10
FELD_ERLEDIGT_VON = 11

KENNUNG_FRIST = "#Frist"
KODIERUNG = "cp437"

RUECKSCHAU_TAGE = 14
WERKTAGE_VORAUS = 3

_SATZBEGINN = re.compile(r"^\[([^\]]*)\]$")
_DATUM = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2})$")

# Vorfristen heissen im Bestand auf drei Arten: "Vorfrist Replik" (1472x),
# "Berufungsvorfrist" (53x) und die von RA-MICRO erzeugte Kurzform
# "Berufung VF Berufung" (239x). Nur auf den Wortanfang zu pruefen haette
# 292 Vorfristen wie echte Fristablaeufe aussehen lassen.
_VORFRIST = re.compile(r"vorfrist|\bVF\b", re.IGNORECASE)


class FristenQuelleNichtErreichbar(RuntimeError):
    """Der Kalenderbaum ist nicht lesbar -- typisch: E-Akte-Mount weg.

    Muss bis in die Kachel durchschlagen. Eine leere Liste waere hier die
    gefaehrlichste Antwort, weil sie wie "keine Fristen" aussieht.
    """


def standard_wurzel() -> str:
    env = os.environ.get("FRISTEN_GT_PFAD")
    if env:
        return env
    basis = os.environ.get("EAKTE_BASE_PATH")
    if basis:
        return os.path.join(basis, "Kalender", "GT")
    return r"Z:\RA\Kalender\GT"


def werktage_voraus(start: datetime.date, werktage: int) -> datetime.date:
    """Datum, das `werktage` Werktage nach `start` liegt.

    Samstag und Sonntag zaehlen nicht mit, liegen aber im Zeitraum: von einem
    Freitag aus sind drei Werktage der folgende Mittwoch.
    """
    tag = start
    gezaehlt = 0
    while gezaehlt < werktage:
        tag += datetime.timedelta(days=1)
        if tag.weekday() < 5:
            gezaehlt += 1
    return tag


def standard_fenster(heute: datetime.date) -> Tuple[datetime.date, datetime.date]:
    """Rueckschau auf unerledigte Fristen plus drei Werktage Vorschau."""
    return (heute - datetime.timedelta(days=RUECKSCHAU_TAGE),
            werktage_voraus(heute, WERKTAGE_VORAUS))


def _datum(roh: str) -> Optional[datetime.date]:
    m = _DATUM.match((roh or "").strip())
    if not m:
        return None
    jahr = int(m.group(3))
    jahr += 2000 if jahr < 70 else 1900
    try:
        return datetime.date(jahr, int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _saetze(inhalt: str) -> List[List[str]]:
    """Zerlegt eine Tagesdatei in Saetze.

    Ein Satz beginnt mit einer Zeile, die nur aus der eingeklammerten
    Aktennummer besteht. Auf die eckige Klammer allein darf man nicht
    aufteilen -- sie kommt auch in Freitexten vor.
    """
    saetze: List[List[str]] = []
    for zeile in inhalt.split("\r\n"):
        if _SATZBEGINN.match(zeile):
            saetze.append([zeile])
        elif saetze:
            saetze[-1].append(zeile)
    return saetze


def _als_frist(felder: List[str], von: datetime.date, bis: datetime.date):
    if len(felder) <= FELD_GRUND:
        return None
    if felder[FELD_KENNUNG].strip() != KENNUNG_FRIST:
        return None

    ende = _datum(felder[FELD_FRISTENDE])
    if ende is None or not (von <= ende <= bis):
        return None

    # Eine Tagesdatei sammelt alle Jahrgaenge seit 2003; der Jahresvergleich
    # oben ist deshalb der eigentliche Filter, nicht der Dateiname.
    if len(felder) > FELD_ERLEDIGT_AM and _datum(felder[FELD_ERLEDIGT_AM]):
        return None

    grund = felder[FELD_GRUND].strip()
    beginn = _datum(felder[FELD_FRISTBEGINN])
    return {
        "aktennummer":     _SATZBEGINN.match(felder[FELD_AKTENNUMMER]).group(1).strip(),
        "frist_datum":     ende.isoformat(),
        "frist_beginn":    beginn.isoformat() if beginn else "",
        "frist_art":       grund,
        "bemerkung":       felder[FELD_TEXT].strip(),
        "sb":              felder[FELD_SACHBEARBEITER].strip(),
        "kurzbezeichnung": felder[FELD_KURZBEZEICHNUNG].strip(),
        "gerichts_az":     (felder[FELD_GERICHTS_AZ].strip()
                            if len(felder) > FELD_GERICHTS_AZ else ""),
        "ist_vorfrist":    bool(_VORFRIST.search(grund)),
    }


def lade_fristen(von: datetime.date, bis: datetime.date,
                 wurzel: Optional[str] = None) -> List[dict]:
    """Alle unerledigten Fristen mit Fristende zwischen `von` und `bis`.

    Liest nur die Tagesdateien im Zeitfenster, nicht den ganzen Baum.
    """
    pfad = wurzel or standard_wurzel()
    if not os.path.isdir(pfad):
        raise FristenQuelleNichtErreichbar(
            f"Fristenkalender nicht erreichbar: {pfad}")

    ergebnis = []
    tag = von
    while tag <= bis:
        datei = os.path.join(pfad, f"{tag.month:02d}M", f"{tag.day:02d}")
        tag += datetime.timedelta(days=1)
        if not os.path.isfile(datei):
            continue
        try:
            with open(datei, "rb") as fh:
                inhalt = fh.read().decode(KODIERUNG, "replace")
        except OSError as e:
            raise FristenQuelleNichtErreichbar(
                f"Fristenkalender nicht erreichbar: {datei}: {e}") from e

        for felder in _saetze(inhalt):
            frist = _als_frist(felder, von, bis)
            if frist:
                ergebnis.append(frist)

    ergebnis.sort(key=lambda e: (e["frist_datum"], e["aktennummer"]))
    return ergebnis
