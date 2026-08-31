"""
Beteiligtenrollen am echten RA-MICRO-Bestand
============================================

Regressionstest zum Befund vom 2026-08-31: Zeugen (Kuerzel 'Z') standen in
der Beteiligtenliste als Gegner und wurden im Klage-Wizard als Beklagte
vorgeschlagen.

Diese Tests laufen ECHT gegen RA-MICRO (lesend) und werden ohne
RAMICRO_INTEGRATION=1 uebersprungen:

    RAMICRO_INTEGRATION=1 pytest -m ramicro_integration \
        backend/tests/test_beteiligten_rollen_ramicro.py

Die Akten sind bewusst fest verdrahtet -- es sind die Faelle, an denen der
Fehler nachgewiesen wurde.
"""

import pytest

from backend.word.word_service import _lade_beteiligte_aus_ramicro


# Akte -> Nachnamen der dort als Kuerzel 'Z' gefuehrten Zeugen
ZEUGENAKTEN = {
    "13/26": {"Müller", "Bukh"},
    "20/25": {"Jaiteh", "Hajji"},
    "249/26": {"Swoboda"},
}


def _alle(az):
    ra = _lade_beteiligte_aus_ramicro(az)
    assert ra.get("alle"), f"Keine Beteiligten aus RA-MICRO fuer Akte {az}"
    return ra


@pytest.mark.ramicro_integration
class TestZeugenSindKeineGegner:

    @pytest.mark.parametrize("az,namen", ZEUGENAKTEN.items())
    def test_zeuge_hat_die_rolle_zeuge(self, az, namen):
        gefunden = {
            b["name"] for b in _alle(az)["alle"]
            if b.get("kuerzel") == "Z"
        }
        assert gefunden >= namen, f"Zeugen fehlen in Akte {az}: {namen - gefunden}"
        for b in _alle(az)["alle"]:
            if b.get("kuerzel") == "Z":
                assert b["rolle"] == "zeuge", f"{b['name']} in {az}: {b['rolle']}"

    @pytest.mark.parametrize("az", list(ZEUGENAKTEN))
    def test_zeuge_steht_nicht_unter_den_gegnern(self, az):
        gegner_namen = {b["name"] for b in _alle(az)["alle_gegner"]}
        assert gegner_namen.isdisjoint(ZEUGENAKTEN[az]), (
            f"Zeuge steht in Akte {az} unter den Gegnern")

    @pytest.mark.parametrize("az", list(ZEUGENAKTEN))
    def test_zeuge_wird_nicht_als_beklagter_vorgeschlagen(self, az):
        for b in _alle(az)["alle"]:
            if b.get("kuerzel") == "Z":
                assert b["beklagter_vorschlag"] is False


@pytest.mark.ramicro_integration
class TestGegnerBleibtGegner:
    """Gegenprobe: die Umstellung darf die echte Gegenseite nicht verlieren."""

    @pytest.mark.parametrize("az", list(ZEUGENAKTEN))
    def test_gegnerische_haftpflicht_bleibt_beklagte(self, az):
        ghpv = [b for b in _alle(az)["alle"] if b.get("kuerzel") == "GHPV"]
        assert ghpv, f"Akte {az} hat keine gegnerische Haftpflicht mehr"
        for b in ghpv:
            assert b["rolle"] == "gegner_hv"
            assert b["beklagter_vorschlag"] is True

    def test_mandant_bleibt_erhalten(self):
        assert _alle("13/26")["mandant"]["name"] == "Stadtler"


@pytest.mark.ramicro_integration
class TestWeitereRollenAmEchtbestand:
    """Akte 108/26 fuehrte Rechtsschutz, Schadenabwickler, Gericht,
    Staatsanwaltschaft und Polizei allesamt als 'Sonstige'."""

    ERWARTET = {
        "RSV": "rechtsschutz",
        "SAB": "schadenabwickler",
        "ST":  "staatsanwaltschaft",
        "I1":  "gericht",
        "PO":  "polizei",
        "SB":  "sonstiger",
    }

    @pytest.mark.parametrize("kz,rolle", ERWARTET.items())
    def test_rolle_je_kuerzel(self, kz, rolle):
        treffer = [b for b in _alle("108/26")["alle"] if b.get("kuerzel") == kz]
        assert treffer, f"Kuerzel {kz} nicht mehr in Akte 108/26"
        for b in treffer:
            assert b["rolle"] == rolle

    def test_sachverstaendiger_unveraendert(self):
        svr = [b for b in _alle("13/26")["alle"] if b.get("kuerzel") == "SVR"]
        assert svr and all(b["rolle"] == "sachverstaendiger" for b in svr)


def _api():
    """Angemeldeter Test-Client gegen die echte App."""
    from backend.app import erstelle_app
    from backend.auth.jwt_handler import erstelle_access_token
    app = erstelle_app()
    tok = erstelle_access_token(1, "admin")
    return app.test_client(), {"Authorization": f"Bearer {tok}"}


@pytest.mark.ramicro_integration
class TestBeteiligtenlisteEndpunkt:
    """Das, was RA Schatz im Browser sieht."""

    def _liste(self, az):
        client, kopf = _api()
        antwort = client.get(f"/akten/{az}/beteiligte", headers=kopf)
        assert antwort.status_code == 200
        return antwort.get_json()["beteiligte"]

    @pytest.mark.parametrize("az,namen", ZEUGENAKTEN.items())
    def test_zeuge_erscheint_als_zeuge(self, az, namen):
        rollen = {b["name"]: b["rolle"] for b in self._liste(az)}
        for name in namen:
            assert rollen.get(name) == "zeuge", f"{name} in {az}: {rollen.get(name)}"

    def test_rechtsschutz_und_abwickler_sind_keine_sonstigen_mehr(self):
        rollen = {b.get("kuerzel"): b["rolle"] for b in self._liste("108/26")}
        assert rollen.get("RSV") == "rechtsschutz"
        assert rollen.get("SAB") == "schadenabwickler"
        assert rollen.get("I1") == "gericht"
        assert rollen.get("PO") == "polizei"

    def test_mandant_steht_an_erster_stelle(self):
        """Die Liste fuehrt mit dem Mandanten -- RA-MICRO sortiert sonst die
        gegnerische Haftpflicht nach vorne."""
        liste = self._liste("13/26")
        assert liste[0]["rolle"] == "mandant", (
            f"Erster Eintrag ist {liste[0]['rolle']} ({liste[0]['name']})")

    def test_mandant_und_gegner_bleiben_stehen(self):
        liste = self._liste("13/26")
        assert any(b["rolle"] == "mandant" for b in liste)
        assert any(b["rolle"] == "gegner_hv" for b in liste)


@pytest.mark.ramicro_integration
class TestKlageWizardEndpunkt:
    """Der rechtlich heikle Teil: wer wird zum Verklagen vorgeschlagen."""

    def _beteiligte(self, az):
        client, kopf = _api()
        antwort = client.get(f"/akten/{az}/klage/daten", headers=kopf)
        assert antwort.status_code == 200
        daten = antwort.get_json()
        return daten.get("beteiligte") or (daten.get("daten") or {}).get("beteiligte") or []

    @pytest.mark.parametrize("az,namen", ZEUGENAKTEN.items())
    def test_zeuge_wird_nicht_als_beklagter_vorgeschlagen(self, az, namen):
        for b in self._beteiligte(az):
            if b.get("name") in namen:
                assert b["vorschlag_beklagter"] is False, (
                    f"Zeuge {b['name']} in {az} ist als Beklagter vorausgewaehlt")
                assert b["rolle_klage"] != "beklagter"

    @pytest.mark.parametrize("az", list(ZEUGENAKTEN))
    def test_gegnerische_haftpflicht_bleibt_vorgeschlagen(self, az):
        ghpv = [b for b in self._beteiligte(az) if b.get("kuerzel") == "GHPV"]
        assert ghpv, f"Akte {az}: gegnerische Haftpflicht fehlt im Klage-Wizard"
        assert all(b["vorschlag_beklagter"] for b in ghpv)

    def test_mandant_bleibt_klaeger(self):
        klaeger = [b for b in self._beteiligte("13/26") if b.get("rolle_klage") == "klaeger"]
        assert len(klaeger) == 1


@pytest.mark.ramicro_integration
class TestKeinStillerGegner:
    """Kernzusage der Umstellung: Gegner wird nur, wessen Kuerzel das hergibt."""

    def test_niemand_ist_gegner_ohne_beleg_im_verzeichnis(self):
        from backend.services.beteiligten_kuerzel_registry import (
            bestimme_beteiligten_rolle)
        for az in list(ZEUGENAKTEN) + ["108/26"]:
            for b in _alle(az)["alle_gegner"]:
                e = bestimme_beteiligten_rolle(b.get("art"), b.get("kuerzel"))
                assert e.beklagter_vorschlag, (
                    f"Akte {az}: {b['name']} (Kuerzel {b.get('kuerzel')!r}) "
                    f"steht unter den Gegnern, das Verzeichnis gibt das nicht her")
