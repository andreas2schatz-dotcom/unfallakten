r"""Leser fuer die RA-MICRO-Fristen aus Z:\RA\Kalender\GT.

Fristen stehen in keiner SQL-Datenbank (nachgewiesen 2026-09-07 mit einer
Testfrist: keine der 141 Tabellen wuchs, keine der 119 Datumsspalten enthielt
das Datum). Sie liegen als CP437-Klartextdateien im Kalenderbaum -- ein Ordner
je Monat, eine Datei je Tag, benannt nach dem Fristende.

Die Fixtures hier bilden echte Saetze nach, damit die Tests ohne E-Akte-Mount
laufen.
"""
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-fristen-gt")

import datetime

import pytest

from backend.services.fristen_gt import (
    FristenQuelleNichtErreichbar,
    lade_fristen,
    standard_fenster,
    werktage_voraus,
)


def _schreibe(wurzel, monat, tag, *saetze):
    ordner = wurzel / f"{monat:02d}M"
    ordner.mkdir(parents=True, exist_ok=True)
    inhalt = "".join("\r\n".join(s) + "\r\n" for s in saetze)
    (ordner / f"{tag:02d}").write_bytes(inhalt.encode("cp437"))


# Aufbau eines echten Satzes, Feld fuer Feld:
#   Aktennummer, Fristende, Uhrzeit, Kennung, Fristbeginn, Text,
#   Sachbearbeiter, Aktenkurzbezeichnung, Fristengrund, Gerichtsaktenzeichen,
#   [Erledigt am, Erledigt von]
OFFEN = ["[322/26]", "17.09.26", "", "#Frist", "03.09.26", "",
         "PK", "Karic/DA Deutsche Allg.", "Klageerwiderung", "AZ: 2-15 S 68/25"]

ERLEDIGT = ["[65/20]", "17.09.26", "00:00", "#Frist", "20.08.26", "",
            "PK", "Di Carlo/Hossaini", "Schriftsatzschluss", "AZ: 2-15 S 68/25",
            "03.09.26", "PK"]

VORFRIST = ["[360/25]", "17.09.26", "00:00", "#Frist", "20.08.26", "",
            "PK", "Murray/Unbekannt", "Vorfrist Schriftsatzschluss",
            "AZ: 30 U 60/26"]

# Termine stehen in denselben Dateien, nur ohne die Kennung #Frist.
TERMIN = ["[820/25]", "17.09.26", "09:30", "AG", "OF", "18-262",
          "AH", "Versorgungswerk/Skaric", "GÜ", "300 C 12/25", "11:00", "11"]

# Aeltere Saetze hoeren nach dem Fristengrund auf.
OHNE_GERICHTS_AZ = ["[519/11]", "17.09.26", "00:00", "#Frist", "28.11.11", "",
                    "AH", "Opherk/Camli", "Vorfrist Verjährung"]


@pytest.fixture
def wurzel(tmp_path):
    return tmp_path / "GT"


class TestSatzAufbau:

    def test_liest_alle_felder(self, wurzel):
        _schreibe(wurzel, 9, 17, OFFEN)
        (e,) = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                            wurzel=str(wurzel))
        assert e["aktennummer"] == "322/26"
        assert e["frist_datum"] == "2026-09-17"
        assert e["frist_beginn"] == "2026-09-03"
        assert e["sb"] == "PK"
        assert e["kurzbezeichnung"] == "Karic/DA Deutsche Allg."
        assert e["frist_art"] == "Klageerwiderung"
        assert e["ist_vorfrist"] is False

    def test_umlaute_kommen_aus_cp437_richtig_an(self, wurzel):
        _schreibe(wurzel, 9, 17, OHNE_GERICHTS_AZ)
        (e,) = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                            wurzel=str(wurzel))
        assert e["frist_art"] == "Vorfrist Verjährung"

    def test_satz_ohne_gerichtsaktenzeichen(self, wurzel):
        _schreibe(wurzel, 9, 17, OHNE_GERICHTS_AZ)
        (e,) = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                            wurzel=str(wurzel))
        assert e["aktennummer"] == "519/11"
        assert e["ist_vorfrist"] is True

    def test_freitext_wird_zur_bemerkung(self, wurzel):
        satz = list(OFFEN)
        satz[5] = "Ladungsfrist beachten"
        _schreibe(wurzel, 9, 17, satz)
        (e,) = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                            wurzel=str(wurzel))
        assert e["bemerkung"] == "Ladungsfrist beachten"


class TestWasNichtAngezeigtWird:

    def test_erledigte_fliegen_raus(self, wurzel):
        """Feld 11 traegt das Erledigt-Datum, Feld 12 das Kuerzel. 3010 der 4293
        vergangenen Fristen haben den Vermerk, aber nur 2 der zukuenftigen --
        daran ist die Bedeutung erkannt worden."""
        _schreibe(wurzel, 9, 17, OFFEN, ERLEDIGT)
        erg = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                           wurzel=str(wurzel))
        assert [e["aktennummer"] for e in erg] == ["322/26"]

    def test_termine_werden_uebersprungen(self, wurzel):
        _schreibe(wurzel, 9, 17, OFFEN, TERMIN)
        erg = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                           wurzel=str(wurzel))
        assert [e["aktennummer"] for e in erg] == ["322/26"]

    def test_andere_jahrgaenge_derselben_tagesdatei(self, wurzel):
        """Eine Tagesdatei sammelt alle Jahre seit 2003 -- ohne Jahresfilter
        stuenden 23 Jahrgaenge in der Kachel."""
        alt = list(OFFEN)
        alt[0], alt[1] = "[100/03]", "17.09.04"
        _schreibe(wurzel, 9, 17, OFFEN, alt)
        erg = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                           wurzel=str(wurzel))
        assert [e["aktennummer"] for e in erg] == ["322/26"]

    def test_datum_ausserhalb_des_fensters(self, wurzel):
        _schreibe(wurzel, 9, 17, OFFEN)
        assert lade_fristen(datetime.date(2026, 9, 18), datetime.date(2026, 9, 20),
                            wurzel=str(wurzel)) == []


class TestFensterUndSortierung:

    def test_liest_nur_die_tage_im_fenster(self, wurzel):
        _schreibe(wurzel, 9, 17, OFFEN)
        spaeter = list(OFFEN)
        spaeter[0], spaeter[1] = "[999/26]", "19.09.26"
        _schreibe(wurzel, 9, 19, spaeter)
        erg = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 18),
                           wurzel=str(wurzel))
        assert [e["aktennummer"] for e in erg] == ["322/26"]

    def test_sortiert_nach_fristende(self, wurzel):
        frueher = list(OFFEN)
        frueher[0], frueher[1] = "[111/26]", "15.09.26"
        _schreibe(wurzel, 9, 15, frueher)
        _schreibe(wurzel, 9, 17, OFFEN)
        erg = lade_fristen(datetime.date(2026, 9, 15), datetime.date(2026, 9, 17),
                           wurzel=str(wurzel))
        assert [e["frist_datum"] for e in erg] == ["2026-09-15", "2026-09-17"]

    def test_fenster_ueber_den_monatswechsel(self, wurzel):
        ende = list(OFFEN)
        ende[0], ende[1] = "[1/26]", "30.09.26"
        _schreibe(wurzel, 9, 30, ende)
        anfang = list(OFFEN)
        anfang[0], anfang[1] = "[2/26]", "01.10.26"
        _schreibe(wurzel, 10, 1, anfang)
        erg = lade_fristen(datetime.date(2026, 9, 30), datetime.date(2026, 10, 1),
                           wurzel=str(wurzel))
        assert [e["aktennummer"] for e in erg] == ["1/26", "2/26"]


class TestWerktagsfenster:
    """„Die naechsten drei Tage, bei Wochenende das miteinberechnen"
    (RA Schatz) -- gezaehlt werden Werktage, angezeigt der ganze Zeitraum."""

    def test_montag_reicht_bis_donnerstag(self):
        assert werktage_voraus(datetime.date(2026, 9, 7), 3) == datetime.date(2026, 9, 10)

    def test_freitag_ueberspringt_das_wochenende(self):
        assert werktage_voraus(datetime.date(2026, 9, 11), 3) == datetime.date(2026, 9, 16)

    def test_samstag_zaehlt_ab_montag(self):
        assert werktage_voraus(datetime.date(2026, 9, 12), 3) == datetime.date(2026, 9, 16)

    def test_standardfenster_blickt_14_tage_zurueck(self):
        von, bis = standard_fenster(datetime.date(2026, 9, 7))
        assert von == datetime.date(2026, 8, 24)
        assert bis == datetime.date(2026, 9, 10)


class TestQuelleNichtErreichbar:
    """Ein fehlender E-Akte-Mount darf NIE als „keine Fristen" durchgehen --
    ausdrueckliche Anforderung RA Schatz."""

    def test_fehlende_wurzel_wirft(self, tmp_path):
        with pytest.raises(FristenQuelleNichtErreichbar, match="nicht erreichbar"):
            lade_fristen(datetime.date(2026, 9, 7), datetime.date(2026, 9, 10),
                         wurzel=str(tmp_path / "gibtsnicht"))

    def test_wurzel_ist_eine_datei(self, tmp_path):
        datei = tmp_path / "GT"
        datei.write_text("kein Verzeichnis", encoding="ascii")
        with pytest.raises(FristenQuelleNichtErreichbar):
            lade_fristen(datetime.date(2026, 9, 7), datetime.date(2026, 9, 10),
                         wurzel=str(datei))

    def test_leeres_verzeichnis_ist_kein_fehler(self, wurzel):
        """Ein Monat ohne Fristen ist ein gueltiger Zustand."""
        wurzel.mkdir(parents=True)
        assert lade_fristen(datetime.date(2026, 9, 7), datetime.date(2026, 9, 10),
                            wurzel=str(wurzel)) == []

    def test_fehlende_tagesdatei_ist_kein_fehler(self, wurzel):
        _schreibe(wurzel, 9, 17, OFFEN)
        assert lade_fristen(datetime.date(2026, 9, 18), datetime.date(2026, 9, 18),
                            wurzel=str(wurzel)) == []


class TestVorfristErkennung:
    """RA-MICRO schreibt Vorfristen auf drei Arten. Im Bestand: 1472x
    "Vorfrist ...", 239x die Kurzform "... VF ..." und 53x zusammengezogen
    wie "Berufungsvorfrist"."""

    @pytest.mark.parametrize("grund", [
        "Vorfrist Schriftsatzschluss",
        "Berufungsvorfrist",
        "Berufung VF Berufung",
        "sof. Beschwerde VF sof. Beschw.",
        "Klage gegen Wid Vorfrist Klage",
    ])
    def test_wird_als_vorfrist_erkannt(self, wurzel, grund):
        satz = list(OFFEN)
        satz[8] = grund
        _schreibe(wurzel, 9, 17, satz)
        (e,) = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                            wurzel=str(wurzel))
        assert e["ist_vorfrist"] is True

    @pytest.mark.parametrize("grund", [
        "Schriftsatzschluss",
        "Klageerwiderung",
        "Berufung",
        "Stellungnahme zu Gutachten",
    ])
    def test_echte_frist_bleibt_echte_frist(self, wurzel, grund):
        satz = list(OFFEN)
        satz[8] = grund
        _schreibe(wurzel, 9, 17, satz)
        (e,) = lade_fristen(datetime.date(2026, 9, 17), datetime.date(2026, 9, 17),
                            wurzel=str(wurzel))
        assert e["ist_vorfrist"] is False


class TestMehrjahresfenster:
    """Der Ordnername kennt kein Jahr: 09M/17 enthaelt den 17. September aller
    Jahrgaenge. Wer ueber die Datumswerte iteriert statt ueber die Dateien,
    liest dieselbe Datei je Jahr erneut und zaehlt ihre Saetze mehrfach."""

    def test_jede_tagesdatei_wird_nur_einmal_gelesen(self, wurzel):
        satz2004 = list(OFFEN)
        satz2004[0], satz2004[1] = "[100/03]", "17.09.04"
        satz2026 = list(OFFEN)
        satz2026[1] = "17.09.26"
        _schreibe(wurzel, 9, 17, satz2026, satz2004)

        erg = lade_fristen(datetime.date(2003, 1, 1), datetime.date(2030, 12, 31),
                           wurzel=str(wurzel))
        assert sorted(e["aktennummer"] for e in erg) == ["100/03", "322/26"]

    def test_zaehlt_auch_ueber_den_jahreswechsel_nicht_doppelt(self, wurzel):
        _schreibe(wurzel, 12, 30, OFFEN[:1] + ["30.12.25"] + OFFEN[2:])
        erg = lade_fristen(datetime.date(2024, 1, 1), datetime.date(2027, 12, 31),
                           wurzel=str(wurzel))
        assert len(erg) == 1
