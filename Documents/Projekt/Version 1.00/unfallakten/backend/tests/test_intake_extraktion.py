"""
Unit-Tests fuer backend/intake/extraktion.py (S1.6b).

extrahiere_felder(text, klasse, registry) -> {"felder": {...},
                                                "llm_konflikt": {...}?}
LLM ist Primaerquelle (Umkehrung des heutigen Shadow-Modes -- gilt NUR im
Neu-Pfad), Regex dient als Anker und Konsistenzcheck.

LLM-Aufrufe sind gemockt.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def _mini_registry_mit_abrechnung():
    from backend.intake.registry_loader import Registry
    klassen = {
        "abrechnungsschreiben": {
            "klasse": "abrechnungsschreiben",
            "marker": [],
            "regex_felder": {
                "schadennummer": [
                    r"Schadennummer[:\s]+([A-Z0-9\-/]+)",
                    r"Schaden-Nr\.?[:\s]+([A-Z0-9\-/]+)",
                ],
                "schreibdatum": [r"\b(\d{2}\.\d{2}\.\d{4})\b"],
            },
            "schema": {
                "schadennummer": "string",
                "schreibdatum": "date",
                "gesamtbetrag": "number",
            },
            "pflichtfelder": [],
            "kritische_felder": [],
            "validierungsregeln": [],
            "fristrelevanz": True,
            "loeschfrist_jahre": 6,
        }
    }
    return Registry(version="test", klassen=klassen, pfad="")


class TestExtraktion(unittest.TestCase):
    def test_regex_felder_werden_extrahiert_wenn_llm_none(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = ("Schadennummer: 12-345-67890 "
                "Datum 22.04.2026 Gesamtbetrag 7.280 EUR")
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        felder = ergebnis["felder"]
        self.assertEqual(felder["schadennummer"], "12-345-67890")
        self.assertEqual(felder["schreibdatum"], "22.04.2026")

    def test_llm_ist_primaer_quelle_wenn_erfolgreich(self):
        """LLM primaer, Regex Fallback -- Freigabe-Vorgabe fuer den Neu-Pfad."""
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = ("Schadennummer: 12-345-67890 "
                "Datum 22.04.2026 Gesamtbetrag 7.280,00 EUR")
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value={
                "schadennummer": "12-345-67890-LLM",
                "schreibdatum": "2026-04-22",
                "gesamtbetrag": 7280.00,
            },
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        felder = ergebnis["felder"]
        self.assertEqual(felder["schadennummer"], "12-345-67890-LLM")
        self.assertEqual(felder["gesamtbetrag"], 7280.00)

    def test_llm_konflikt_wird_gestempelt_bei_divergenz(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = "Schadennummer: 12-345-67890 Datum 22.04.2026"
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value={
                "schadennummer": "99-999-99999",
                "schreibdatum": "22.04.2026",
            },
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        self.assertIn("llm_konflikt", ergebnis)
        self.assertIn("schadennummer", ergebnis["llm_konflikt"])
        konflikt = ergebnis["llm_konflikt"]["schadennummer"]
        self.assertEqual(konflikt["llm"], "99-999-99999")
        self.assertEqual(konflikt["regex"], "12-345-67890")

    def test_kein_llm_konflikt_wenn_werte_identisch(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        text = "Schadennummer: 12-345-67890 Datum 22.04.2026"
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value={"schadennummer": "12-345-67890",
                          "schreibdatum": "22.04.2026"},
        ):
            ergebnis = extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry,
            )
        self.assertNotIn("llm_konflikt", ergebnis)

    def test_gutachten_regex_extrahiert_restwert_netto_und_brutto(self):
        """Gutachten-Registry muss restwert_netto UND restwert_brutto als
        separate Felder liefern (DEKRA-Gutachten zeigen beide Werte)."""
        from backend.intake import extraktion
        from backend.intake.registry_loader import lade_registry, standard_pfad
        registry = lade_registry(standard_pfad())

        text = (
            "Wiederbeschaffungswert brutto: 15.900,00 EUR\n"
            "Restwert netto: 4.201,68 EUR\n"
            "Restwert brutto: 5.000,00 EUR\n"
        )
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            ergebnis = extraktion.extrahiere_felder(text, "gutachten", registry)
        felder = ergebnis["felder"]
        self.assertIn("restwert_netto", felder,
                      f"restwert_netto fehlt in {felder!r}")
        self.assertIn("restwert_brutto", felder,
                      f"restwert_brutto fehlt in {felder!r}")
        # Werte als Strings aus Regex; Konversion macht extrahiere_felder
        self.assertTrue(str(felder["restwert_netto"]).startswith("4"))
        self.assertTrue(str(felder["restwert_brutto"]).startswith("5"))

    def test_gutachten_regex_extrahiert_sv_kosten_netto_und_brutto(self):
        """DEKRA-Gutachten enthalten oft die SV-Rechnung im selben PDF.
        Gutachten-Schema muss sv_kosten_netto UND sv_kosten_brutto als
        separate Felder liefern (fuer Option A: Dual-Ereignis-Freigabe)."""
        from backend.intake import extraktion
        from backend.intake.registry_loader import lade_registry, standard_pfad
        registry = lade_registry(standard_pfad())

        text = (
            "Sachverstaendigenhonorar netto: 850,00 EUR\n"
            "Sachverstaendigenhonorar brutto: 1.011,50 EUR\n"
            "Rechnungsnummer: R-2026-4711\n"
        )
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            ergebnis = extraktion.extrahiere_felder(text, "gutachten", registry)
        felder = ergebnis["felder"]
        self.assertIn("sv_kosten_netto", felder,
                      f"sv_kosten_netto fehlt in {felder!r}")
        self.assertIn("sv_kosten_brutto", felder,
                      f"sv_kosten_brutto fehlt in {felder!r}")
        self.assertIn("sv_rechnungsnummer", felder,
                      f"sv_rechnungsnummer fehlt in {felder!r}")
        self.assertEqual(felder["sv_rechnungsnummer"], "R-2026-4711")

    def test_llm_text_param_geht_an_llm_regex_bleibt_volltext(self):
        """N-06: Die LLM-Extraktion bekommt den ausgewaehlten Seitenauszug,
        die Regex-Anker laufen weiter auf dem Volltext."""
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        volltext = "Schadennummer: 12-345-67890 Datum 22.04.2026"
        llm_auszug = "nur der ausgewaehlte Seitentext ohne Schadennummer"
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ) as m:
            ergebnis = extraktion.extrahiere_felder(
                volltext, "abrechnungsschreiben", registry,
                llm_text=llm_auszug,
            )
        # LLM bekommt den Auszug (zweites Positionsargument = text)
        self.assertEqual(m.call_args.args[1], llm_auszug)
        # Regex-Anker weiterhin auf dem Volltext
        self.assertEqual(ergebnis["felder"]["schadennummer"], "12-345-67890")

    def test_ohne_llm_text_bleibt_verhalten_gleich(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        volltext = "Schadennummer: 12-345-67890 Datum 22.04.2026"
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ) as m:
            extraktion.extrahiere_felder(
                volltext, "abrechnungsschreiben", registry,
            )
        self.assertEqual(m.call_args.args[1], volltext)

    def test_unbekannte_klasse_liefert_leere_felder(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ):
            ergebnis = extraktion.extrahiere_felder(
                "text", "fantasieklasse", registry,
            )
        self.assertEqual(ergebnis["felder"], {})

    def test_llm_service_bekommt_das_yaml_schema(self):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=None,
        ) as m:
            extraktion.extrahiere_felder(
                "text", "abrechnungsschreiben", registry,
            )
        # Erstes Argument ist das schema-dict
        args = m.call_args.args
        kwargs = m.call_args.kwargs
        schema_arg = args[0] if args else kwargs.get("schema", {})
        # Muss alle YAML-Schemafelder enthalten
        for feld in ("schadennummer", "schreibdatum", "gesamtbetrag"):
            self.assertIn(feld, schema_arg)


def test_ist_aktiviert_spiegelt_enabled_flag():
    from backend.services import llm_service
    assert llm_service.ist_aktiviert() is llm_service._ENABLED


class TestLlmStatus(unittest.TestCase):
    def _registry(self):
        class _R:
            klassen = {"abrechnung": {"schema": {"betrag": "geld"},
                                      "regex_felder": {}}}
        return _R()

    def test_status_ok_wenn_aktiv_und_werte(self):
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value={"betrag": "100"}):
            erg = extraktion.extrahiere_felder("txt", "abrechnung", self._registry())
        self.assertEqual(erg["llm_status"], "ok")

    def test_status_ausgefallen_wenn_aktiv_aber_none(self):
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value=None):
            erg = extraktion.extrahiere_felder("txt", "abrechnung", self._registry())
        self.assertEqual(erg["llm_status"], "ausgefallen")

    def test_status_aus_wenn_deaktiviert(self):
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=False), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value=None):
            erg = extraktion.extrahiere_felder("txt", "abrechnung", self._registry())
        self.assertEqual(erg["llm_status"], "aus")

    def test_status_aus_bei_unbekannter_klasse(self):
        from backend.intake import extraktion
        class _R:
            klassen = {}
        erg = extraktion.extrahiere_felder("txt", "gibtsnicht", _R())
        self.assertEqual(erg.get("llm_status"), "aus")


class TestPruefdienstleisterFallback(unittest.TestCase):
    """Befund 1280/25: VHV-eigener Pruefbericht ohne ControlExpert/DEKRA --
    das Pflichtfeld pruefdienstleister blieb leer."""

    def _registry(self):
        class _R:
            klassen = {"pruefbericht": {
                "schema": {"pruefdienstleister": "string",
                           "vorgangsnummer": "string"},
                "regex_felder": {},
            }}
        return _R()

    def _extrahiere(self, text, llm_werte):
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value=llm_werte):
            return extraktion.extrahiere_felder(
                text, "pruefbericht", self._registry())["felder"]

    def test_versicherer_als_fallback(self):
        felder = self._extrahiere(
            "Prüfbericht\nVHV Allgemeine Versicherung AG\nSchaden-Nr.: SD1",
            {"pruefdienstleister": None, "vorgangsnummer": "SD1"})
        self.assertEqual(felder["pruefdienstleister"],
                         "VHV Allgemeine Versicherung AG")

    def test_controlexpert_hat_vorrang_vor_versicherer(self):
        felder = self._extrahiere(
            "Prüfbericht der Control€xpert GmbH im Auftrag der "
            "VHV Allgemeine Versicherung AG",
            {"pruefdienstleister": None})
        self.assertEqual(felder["pruefdienstleister"], "ControlExpert")

    def test_llm_wert_wird_nicht_ueberschrieben(self):
        felder = self._extrahiere(
            "Prüfbericht\nVHV Allgemeine Versicherung AG",
            {"pruefdienstleister": "DEKRA"})
        self.assertEqual(felder["pruefdienstleister"], "DEKRA")

    def test_dekra_nur_in_qualitaetsmerkmalen_zaehlt_nicht(self):
        # Dok 516: "Dekra-Zertifizierung KL-Siegel" steht erst auf Seite 3
        # in der Werkstatt-Merkmalliste -- kein Beleg fuer den Absender.
        text = ("Prüfbericht\nSchaden-Nr.: SD1\n" + "Prüftext Zeile.\n" * 200 +
                "• Dekra-Zertifizierung KL-Siegel (Werkstattprüfung)")
        felder = self._extrahiere(text, {"pruefdienstleister": None})
        self.assertNotIn("pruefdienstleister", felder)

    def test_dekra_im_dokumentkopf_wird_erkannt(self):
        felder = self._extrahiere(
            "DEKRA Automobil GmbH\nPrüfbericht\nSchaden-Nr.: SD1",
            {"pruefdienstleister": None})
        self.assertEqual(felder["pruefdienstleister"], "DEKRA")

    def test_ohne_treffer_bleibt_feld_leer(self):
        felder = self._extrahiere(
            "Prüfbericht ohne erkennbaren Absender",
            {"pruefdienstleister": None})
        self.assertNotIn("pruefdienstleister", felder)

    def test_andere_klassen_unberuehrt(self):
        from backend.intake import extraktion
        class _R:
            klassen = {"gutachten": {
                "schema": {"pruefdienstleister": "string"},
                "regex_felder": {},
            }}
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value={"pruefdienstleister": None}):
            felder = extraktion.extrahiere_felder(
                "Text der VHV Allgemeine Versicherung AG",
                "gutachten", _R())["felder"]
        self.assertNotIn("pruefdienstleister", felder)


class TestReferenzwerkstattFallback(unittest.TestCase):
    """Befund 1280/25: Der VHV-Werkstatt-Block liegt auf Seite 4/5 ausserhalb
    des N-06-LLM-Seitenfensters -- felder.referenzwerkstatt blieb leer.
    Deterministischer Fallback via werkstatt_service (nur pruefbericht,
    nur wenn das LLM nichts liefert)."""

    VHV_TEXT = (
        "Für die Korrekturberechnung haben wir den Reparaturbetrieb\n"
        "\n"
        "Möser Arno - Karosseriefachbetrieb\n"
        "Philipp-Reis-Straße 9\n"
        "63128 Dietzenbach\n"
        "Telefon: 06074-25936\n"
        "Entfernungskilometer: 16,00 km\n"
        "berücksichtigt.\n"
    )

    def _registry(self):
        class _R:
            klassen = {"pruefbericht": {
                "schema": {"referenzwerkstatt": {"typ": "object"},
                           "vorgangsnummer": "string"},
                "regex_felder": {},
            }}
        return _R()

    def _extrahiere(self, text, llm_werte, klasse="pruefbericht",
                    registry=None):
        from backend.intake import extraktion
        with mock.patch("backend.intake.extraktion.llm_service.ist_aktiviert",
                        return_value=True), \
             mock.patch("backend.intake.extraktion.llm_service.extrahiere_nach_schema",
                        return_value=llm_werte):
            return extraktion.extrahiere_felder(
                text, klasse, registry or self._registry())["felder"]

    def test_vhv_block_fuellt_referenzwerkstatt(self):
        felder = self._extrahiere(self.VHV_TEXT,
                                  {"referenzwerkstatt": None})
        ws = felder.get("referenzwerkstatt")
        self.assertIsNotNone(ws)
        self.assertEqual(ws["name"], "Möser Arno - Karosseriefachbetrieb")
        self.assertEqual(ws["adresse"], "Philipp-Reis-Straße 9")
        self.assertEqual(ws["plz_ort"], "63128 Dietzenbach")
        self.assertEqual(ws["km_genannt"], 16.0)
        self.assertEqual(ws["quelle"], "vhv_block")

    def test_llm_wert_wird_nicht_ueberschrieben(self):
        felder = self._extrahiere(
            self.VHV_TEXT,
            {"referenzwerkstatt": {"name": "LLM-Werkstatt"}})
        ws = felder["referenzwerkstatt"]
        self.assertEqual(ws["name"], "LLM-Werkstatt")
        self.assertEqual(ws["adresse"], "")
        self.assertEqual(ws["plz_ort"], "")
        self.assertEqual(ws["telefon"], "")
        self.assertIsNone(ws["km_genannt"])
        self.assertEqual(ws["quelle"], "llm")

    def test_llm_shape_wird_auf_kanonische_keys_normalisiert(self):
        felder = self._extrahiere(
            self.VHV_TEXT,
            {"referenzwerkstatt": {"name": "LLM-Werkstatt",
                                    "entfernung": "16 km"}})
        ws = felder["referenzwerkstatt"]
        self.assertEqual(ws["name"], "LLM-Werkstatt")
        self.assertEqual(ws["adresse"], "")
        self.assertEqual(ws["plz_ort"], "")
        self.assertEqual(ws["telefon"], "")
        self.assertIsNone(ws["km_genannt"])
        self.assertEqual(ws["quelle"], "llm")
        self.assertEqual(ws["entfernung"], "16 km")

    def test_ohne_treffer_bleibt_feld_leer(self):
        felder = self._extrahiere("Prüfbericht ohne Werkstatt-Verweis",
                                  {"referenzwerkstatt": None})
        self.assertNotIn("referenzwerkstatt", felder)

    def test_andere_klassen_unberuehrt(self):
        class _R:
            klassen = {"gutachten": {
                "schema": {"referenzwerkstatt": {"typ": "object"}},
                "regex_felder": {},
            }}
        felder = self._extrahiere(self.VHV_TEXT,
                                  {"referenzwerkstatt": None},
                                  klasse="gutachten", registry=_R())
        self.assertNotIn("referenzwerkstatt", felder)


class TestDatumScheinkonflikt(unittest.TestCase):
    """Befund 1280/25 (c): llm_konflikt meldete schreibdatum '2026-04-28'
    (LLM) vs. '28.04.2026' (Regex) als Konflikt, obwohl derselbe Tag."""

    def _extrahiere(self, text, llm_werte):
        from backend.intake import extraktion
        registry = _mini_registry_mit_abrechnung()
        with mock.patch(
            "backend.intake.extraktion.llm_service.extrahiere_nach_schema",
            return_value=llm_werte,
        ):
            return extraktion.extrahiere_felder(
                text, "abrechnungsschreiben", registry)

    def test_gleicher_tag_verschiedene_formate_kein_konflikt(self):
        ergebnis = self._extrahiere(
            "Schadennummer: 12-345-67890 Datum 28.04.2026",
            {"schadennummer": "12-345-67890",
             "schreibdatum": "2026-04-28"})
        self.assertNotIn("llm_konflikt", ergebnis)

    def test_echter_datums_konflikt_bleibt(self):
        ergebnis = self._extrahiere(
            "Schadennummer: 12-345-67890 Datum 28.04.2026",
            {"schadennummer": "12-345-67890",
             "schreibdatum": "2026-04-29"})
        self.assertIn("llm_konflikt", ergebnis)
        self.assertIn("schreibdatum", ergebnis["llm_konflikt"])

    def test_nicht_datums_werte_unveraendert(self):
        ergebnis = self._extrahiere(
            "Schadennummer: 12-345-67890 Datum 28.04.2026",
            {"schadennummer": "99-999-99999",
             "schreibdatum": "28.04.2026"})
        self.assertIn("llm_konflikt", ergebnis)
        self.assertIn("schadennummer", ergebnis["llm_konflikt"])


if __name__ == "__main__":
    unittest.main()
