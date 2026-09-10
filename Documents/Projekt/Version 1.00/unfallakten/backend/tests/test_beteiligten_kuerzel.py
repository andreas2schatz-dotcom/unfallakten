"""
Beteiligten-Kuerzel-Registry (SSOT)
===================================

Die RA-MICRO-Beteiligtenkennzeichen wurden bis 2026-08-31 an fuenf Stellen
unabhaengig voneinander ausgelegt. Ergebnis: Zeugen (Kuerzel 'Z') standen in
der Beteiligtenliste als Gegner und wurden im Klage-Wizard als Beklagte
vorgeschlagen.

Die Kuerzelbedeutungen stammen aus der Kuerzelliste der Kanzlei
(RA Schatz, 2026-08-31) und gelten fuer Beteiligtenart 4.
"""

import pytest

from backend.services.beteiligten_kuerzel_registry import (
    bestimme_beteiligten_rolle,
    lade_beteiligten_kuerzel,
)


class TestGemeldeterFehler:
    """Der Befund, der die Umstellung ausgeloest hat."""

    def test_zeuge_ist_kein_gegner(self):
        e = bestimme_beteiligten_rolle(4, "Z")
        assert e.rolle == "zeuge"
        assert e.bezeichnung == "Zeuge/Zeugin"

    def test_zeuge_wird_nicht_als_beklagter_vorgeschlagen(self):
        assert bestimme_beteiligten_rolle(4, "Z").beklagter_vorschlag is False


class TestPassivlegitimation:
    """RA Schatz 2026-08-31: Beklagter kann nur werden, wer
    passivlegitimiert ist -- der Gegner selbst und seine
    Haftpflichtversicherung (Direktanspruch § 115 VVG). Sonst niemand.
    Auch nicht, wer erkennbar zur Gegenseite gehoert."""

    def test_gegnerische_haftpflicht_ist_beklagte(self):
        e = bestimme_beteiligten_rolle(4, "GHPV")
        assert e.rolle == "gegner_hv"
        assert e.beklagter_vorschlag is True

    @pytest.mark.parametrize("kz", ["GH", "GHV"])
    def test_varianten_der_gegnerischen_haftpflicht(self, kz):
        assert bestimme_beteiligten_rolle(4, kz).rolle == "gegner_hv"

    @pytest.mark.parametrize("art,kz", [
        (4, "GR"), (4, "GR2"), (4, "GR3"), (4, "GBEV"), (9, "GBEV"),
    ])
    def test_bevollmaechtigte_der_gegner_sind_nie_beklagte(self, art, kz):
        """"Das sind keine Gegner, sondern Bevollmaechtigte der Gegner.
        Die sind nie passivlegitimiert." (RA Schatz)"""
        e = bestimme_beteiligten_rolle(art, kz)
        assert e.rolle == "gegner_anwalt"
        assert e.beklagter_vorschlag is False

    @pytest.mark.parametrize("kz", ["SAB", "SA"])
    def test_schadenabwickler_ist_kein_gegner(self, kz):
        """Schadenabwickler regulieren nur fuer den Versicherer.
        SA wird wie SAB behandelt (RA Schatz)."""
        e = bestimme_beteiligten_rolle(4, kz)
        assert e.rolle == "schadenabwickler"
        assert e.beklagter_vorschlag is False

    def test_sa_unter_beteiligtenart_2_wird_nicht_gegner(self):
        """Die drei SA-Faelle im Bestand stehen unter Art 2 -- dort wuerde
        die Auffangregel sie sonst zum Gegner machen."""
        e = bestimme_beteiligten_rolle(2, "SA")
        assert e.rolle == "schadenabwickler"
        assert e.beklagter_vorschlag is False


class TestEigeneSeite:
    def test_rechtsschutz_ist_nicht_sonstiger(self):
        e = bestimme_beteiligten_rolle(4, "RSV")
        assert e.rolle == "rechtsschutz"
        assert e.beklagter_vorschlag is False

    def test_rechtsschutz_auch_bei_beteiligtenart_3(self):
        assert bestimme_beteiligten_rolle(3, "RSV").rolle == "rechtsschutz"

    def test_eigene_haftpflicht(self):
        assert bestimme_beteiligten_rolle(4, "HPV").rolle == "eigene_versicherung"

    def test_kaskoversicherung(self):
        assert bestimme_beteiligten_rolle(4, "KASK").rolle == "eigene_versicherung"


class TestWeitereRollen:
    @pytest.mark.parametrize("kz,rolle", [
        ("SV",   "sachverstaendiger"),
        ("SVR",  "sachverstaendiger"),
        ("PO",   "polizei"),
        ("ST",   "staatsanwaltschaft"),
        ("AM",   "staatsanwaltschaft"),
        ("I1",   "gericht"),
        ("I2",   "gericht"),
        ("VG",   "gericht"),
        ("BG",   "gericht"),
        ("AB",   "behoerde"),
        ("FA",   "behoerde"),
        ("GB",   "behoerde"),
        ("KI",   "bank"),
        ("GVZ",  "vollstreckung"),
        ("GV",   "vollstreckung"),
        ("INK",  "vollstreckung"),
        ("DS",   "vollstreckung"),
        ("SB",   "sonstiger"),
        ("SO",   "sonstiger"),
        ("BE",   "sonstiger"),
        ("KR",   "sonstiger"),
    ])
    def test_rolle_je_kuerzel(self, kz, rolle):
        assert bestimme_beteiligten_rolle(4, kz).rolle == rolle

    @pytest.mark.parametrize("kz", [
        "GVZ", "GV", "INK", "DS", "SB", "SO", "BE", "KR", "KI",
        "PO", "ST", "I1", "AB", "FA", "GB", "BG", "AM", "VG",
    ])
    def test_keiner_davon_wird_beklagter(self, kz):
        assert bestimme_beteiligten_rolle(4, kz).beklagter_vorschlag is False

    def test_bezeichnung_kommt_aus_der_kanzleiliste(self):
        assert bestimme_beteiligten_rolle(4, "GVZ").bezeichnung == "Gerichtsvollzieher"
        assert bestimme_beteiligten_rolle(4, "KR").bezeichnung == "Korrespondenzanwalt"
        assert bestimme_beteiligten_rolle(4, "GB").bezeichnung == "Grundbuchamt"


class TestLeeresKuerzel:
    """Bei leerem Kuerzel entscheidet die Beteiligtenart (RA Schatz, 2026-08-31).

    Ohne diese Ausnahme verloere jede Akte ihren Mandanten (928 Faelle) und
    ihren Gegner (579 Faelle) -- beide tragen in RA-MICRO regulaer kein
    Kennzeichen.
    """

    def test_art1_ohne_kuerzel_ist_mandant(self):
        assert bestimme_beteiligten_rolle(1, "").rolle == "mandant"

    def test_art2_ohne_kuerzel_ist_gegner(self):
        e = bestimme_beteiligten_rolle(2, "")
        assert e.rolle == "gegner"
        assert e.beklagter_vorschlag is True

    def test_art4_ohne_kuerzel_ist_sonstiger(self):
        assert bestimme_beteiligten_rolle(4, "").rolle == "sonstiger"

    def test_art6_ohne_kuerzel_ist_behoerde(self):
        assert bestimme_beteiligten_rolle(6, "").rolle == "behoerde"

    def test_none_wird_wie_leer_behandelt(self):
        assert bestimme_beteiligten_rolle(1, None).rolle == "mandant"


class TestUnbekanntesKuerzel:
    """Auffangregel: unbekannt heisst niemals stillschweigend 'Gegner'."""

    def test_unbekannt_bei_art4_wird_sonstiger(self):
        e = bestimme_beteiligten_rolle(4, "QQQ")
        assert e.rolle == "sonstiger"
        assert e.beklagter_vorschlag is False

    def test_unbekannt_bei_art4_wird_als_unbekannt_gekennzeichnet(self):
        assert bestimme_beteiligten_rolle(4, "QQQ").unbekannt is True

    def test_bekanntes_kuerzel_ist_nicht_unbekannt(self):
        assert bestimme_beteiligten_rolle(4, "Z").unbekannt is False

    def test_unbekannt_bei_art2_wird_sonstiger(self):
        """Auch unter Art 2 macht ein unbekanntes Kuerzel niemanden zum Gegner.

        Genau diese Grosszuegigkeit war der gemeldete Fehler. Ein leeres
        Kuerzel unter Art 2 bleibt Gegner (siehe TestLeeresKuerzel), ein
        unbekanntes nicht -- es faellt auf und wird nachgetragen.
        """
        e = bestimme_beteiligten_rolle(2, "QQQ")
        assert e.rolle == "sonstiger"
        assert e.unbekannt is True
        assert e.beklagter_vorschlag is False


class TestMandantenUndGegnerKuerzel:
    """Nicht aus der Art-4-Liste, aber in RA-MICRO in Gebrauch."""

    @pytest.mark.parametrize("kz", ["M", "M1", "M2"])
    def test_mandantenkuerzel(self, kz):
        e = bestimme_beteiligten_rolle(1, kz)
        assert e.rolle == "mandant"
        assert e.beklagter_vorschlag is False

    @pytest.mark.parametrize("kz", ["G", "G1", "G2", "G3"])
    def test_gegnerkuerzel_ist_beklagter(self, kz):
        e = bestimme_beteiligten_rolle(2, kz)
        assert e.rolle == "gegner"
        assert e.beklagter_vorschlag is True


class TestWiderspruchArtGegenKuerzel:
    """Beteiligtenart 1 ist in RA-MICRO die Mandantenseite. Traegt so ein
    Eintrag ein Gegner-Kuerzel, widersprechen sich die beiden Angaben.

    Echtfall: Akte 668/23 fuehrt die Mandantin unter Art 1 mit dem Kuerzel
    'g' (klein). Aus einem Tippfehler darf keine Beklagte werden.
    """

    @pytest.mark.parametrize("kz", ["G", "g", "GHPV", "GR"])
    def test_mandantenseite_wird_nie_beklagte(self, kz):
        e = bestimme_beteiligten_rolle(1, kz)
        assert e.beklagter_vorschlag is False
        assert e.rolle == "sonstiger"

    def test_widerspruch_wird_vermerkt(self):
        e = bestimme_beteiligten_rolle(1, "G")
        assert e.rolle == "sonstiger"
        assert e.hinweis

    def test_unauffaelliger_eintrag_hat_keinen_hinweis(self):
        assert bestimme_beteiligten_rolle(4, "Z").hinweis == ""

    def test_unbekanntes_kuerzel_bekommt_einen_hinweis(self):
        assert bestimme_beteiligten_rolle(4, "QQQ").hinweis

    def test_mandantenkuerzel_unter_art1_bleibt_unauffaellig(self):
        e = bestimme_beteiligten_rolle(1, "M")
        assert e.rolle == "mandant"
        assert e.hinweis == ""

    def test_gegnerkuerzel_unter_art2_bleibt_beklagter(self):
        """Gegenprobe: nur Art 1 ist geschuetzt, nicht die Gegnerseite."""
        assert bestimme_beteiligten_rolle(2, "G").beklagter_vorschlag is True


class TestTerminsvertretung:
    """HBV/UBV sind Haupt- und Unterbevollmaechtigte fuer die
    Terminsvertretung -- nichts mit Versicherungen (RA Schatz 2026-08-31)."""

    def test_hauptbevollmaechtigter(self):
        e = bestimme_beteiligten_rolle(4, "HBV")
        assert e.rolle == "sonstiger"
        assert "bevollm" in e.bezeichnung.lower()
        assert e.offen is False
        assert e.beklagter_vorschlag is False

    def test_unterbevollmaechtigter(self):
        e = bestimme_beteiligten_rolle(4, "UBV")
        assert e.rolle == "sonstiger"
        assert e.offen is False


class TestNachgetrageneKuerzel:
    """Fuenf Kuerzel aus dem Bestand, die RA Schatz am 2026-09-10 geklaert
    hat. Vorher liefen KOAN/OA/UB in die Auffangregel und HV/VS trugen
    'offen: true'."""

    def test_unterbeteiligter(self):
        e = bestimme_beteiligten_rolle(4, "UB")
        assert e.bezeichnung == "Unterbeteiligter"
        assert e.rolle == "sonstiger"
        assert e.unbekannt is False

    def test_korrespondenzanwalt(self):
        e = bestimme_beteiligten_rolle(4, "KOAN")
        assert e.bezeichnung == "Korrespondenzanwalt"
        assert e.rolle == "sonstiger"
        assert e.unbekannt is False

    def test_ordnungsamt_ist_behoerde(self):
        """RA Schatz: OA gehoert immer in die Gruppe Behoerden/Gerichte."""
        from backend.routers.ramicro_akte_routes import _klassifiziere
        e = bestimme_beteiligten_rolle(4, "OA")
        assert e.bezeichnung == "Ordnungsamt"
        assert e.rolle == "behoerde"
        assert _klassifiziere(4, "OA") == "behoerde"

    def test_hv_ist_die_eigene_haftpflicht(self):
        """HV meint die eigene Haftpflicht -- die gegnerische traegt GHPV/GH/GHV.
        Ein Beklagtenvorschlag darf daraus nie werden."""
        e = bestimme_beteiligten_rolle(4, "HV")
        assert e.rolle == "eigene_versicherung"
        assert e.beklagter_vorschlag is False
        assert e.offen is False
        assert bestimme_beteiligten_rolle(4, "GHPV").rolle == "gegner_hv"

    def test_vs_bleibt_seitenneutral(self):
        """VS nennt nur die Sparte. Aus einer Sammelangabe darf weder eine
        eigene Versicherung noch ein Gegner werden."""
        e = bestimme_beteiligten_rolle(4, "VS")
        assert e.rolle == "sonstiger"
        assert e.beklagter_vorschlag is False
        assert e.unbekannt is False


class TestSchreibweisen:
    """RA-MICRO enthaelt 'HVw', 'g' und 'r' -- Gross-/Kleinschreibung
    und Leerzeichen duerfen die Zuordnung nicht kippen."""

    @pytest.mark.parametrize("kz", ["z", " Z ", "Z"])
    def test_zeuge_unabhaengig_von_der_schreibweise(self, kz):
        assert bestimme_beteiligten_rolle(4, kz).rolle == "zeuge"

    def test_hausverwaltung_klein_geschrieben(self):
        assert bestimme_beteiligten_rolle(4, "HVw").bezeichnung == "Hausverwaltung"


class TestAktenansichtGruppen:
    """Die RA-MICRO-Aktenansicht gruppiert in sechs Kaesten. Auch sie muss
    aus dem Verzeichnis lesen, sonst gibt es wieder zwei Wahrheiten."""

    @pytest.mark.parametrize("art,kz,gruppe", [
        (1, "",     "mandant"),
        (2, "",     "gegner"),
        (4, "GHPV", "gegner"),
        (9, "GBEV", "weitere"),
        (4, "SAB",  "weitere"),
        (4, "SA",   "weitere"),
        (4, "GR",   "weitere"),
        (4, "HPV",  "eigene_versicherung"),
        (4, "KASK", "eigene_versicherung"),
        (4, "RSV",  "rechtsschutz"),
        (4, "RS",   "rechtsschutz"),
        (4, "PO",   "behoerde"),
        (4, "I1",   "behoerde"),
        (4, "ST",   "behoerde"),
        (4, "Z",    "weitere"),
        (4, "SV",   "weitere"),
        (4, "KI",   "weitere"),
        (4, "SB",   "weitere"),
    ])
    def test_gruppe(self, art, kz, gruppe):
        from backend.routers.ramicro_akte_routes import _klassifiziere
        assert _klassifiziere(art, kz) == gruppe


class TestRegistryVollstaendigkeit:
    """Die Kuerzelliste der Kanzlei muss vollstaendig hinterlegt sein."""

    KANZLEILISTE = [
        "GVZ", "GHPV", "GH", "GHV", "KASK", "HBV", "UBV", "WEG", "DS", "INK",
        "INS", "ZVW", "HPV", "SV", "SVR", "SB", "NPF", "Z", "SAB", "AB", "AM",
        "BA", "BE", "BF", "BG", "BV", "DT", "FA", "GB", "GE", "GR", "GR2",
        "GR3", "GV", "HR", "HV", "I1", "I2", "IN", "KI", "KR", "PO", "RS",
        "RSV", "REF", "SH", "SO", "ST", "TR", "TV", "UN", "VG", "VS", "HVW",
    ]

    def test_jedes_kuerzel_der_kanzleiliste_ist_hinterlegt(self):
        registry = lade_beteiligten_kuerzel()
        fehlend = [k for k in self.KANZLEILISTE if k not in registry.kuerzel]
        assert fehlend == [], f"Kuerzel fehlen in der Registry: {fehlend}"

    def test_jedes_kuerzel_hat_eine_bezeichnung(self):
        registry = lade_beteiligten_kuerzel()
        ohne = [k for k, v in registry.kuerzel.items() if not v.get("bezeichnung")]
        assert ohne == []

    def test_nur_gegner_und_seine_haftpflicht_koennen_beklagte_sein(self):
        """Harte Schranke gegen kuenftige Aufweichung: kein Bevollmaechtigter,
        kein Abwickler, kein Zeuge darf je einen Beklagtenvorschlag tragen."""
        registry = lade_beteiligten_kuerzel()
        erlaubt = {"gegner", "gegner_hv"}
        falsch = [
            k for k, v in registry.kuerzel.items()
            if v.get("beklagter_vorschlag") and v.get("rolle") not in erlaubt
        ]
        assert falsch == [], f"Nicht passivlegitimiert, aber Beklagter: {falsch}"

    def test_kein_eintrag_traegt_noch_das_feld_gegnerseite(self):
        """Entfernt am 2026-08-31: das Feld war deckungsgleich mit
        beklagter_vorschlag und verleitete zum Schluss "Gegnerseite =
        Beklagter" -- genau dem Fehler, um den es hier geht."""
        registry = lade_beteiligten_kuerzel()
        mit_feld = [k for k, v in registry.kuerzel.items() if "gegnerseite" in v]
        assert mit_feld == []

    def test_registry_hat_eine_version(self):
        assert lade_beteiligten_kuerzel().version
