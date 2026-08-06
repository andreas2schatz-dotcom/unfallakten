from backend.intake.registry_loader import lade_registry, standard_pfad

ERWARTET = {
    "abrechnungsschreiben": ("abrechnungsschreiben", "abrechnung_eingegangen", None),
    "pruefbericht":         ("pruefbericht", "pruefbericht_eingegangen", None),
    "gutachten":            ("gutachten", "gutachten_eingegangen", None),
    "sv_rechnung":          ("rechnung", "rechnung_eingegangen", "__sv_kosten_vorsteuer__"),
    "rechnung":             ("rechnung", "rechnung_eingegangen", None),
    "abschlepprechnung":    ("rechnung", "rechnung_eingegangen", "abschleppkosten"),
    "standkostenrechnung":  ("rechnung", "rechnung_eingegangen", "standkosten"),
}


def test_bestandsklassen_haben_felder():
    reg = lade_registry(standard_pfad(), reload=True)
    for klasse, (parser, ereignis, pos) in ERWARTET.items():
        data = reg.klassen[klasse]
        assert data.get("parser") == parser, klasse
        assert data.get("ereignistyp") == ereignis, klasse
        assert data.get("schadenposition") == pos, klasse
        assert data.get("richtung", "eingehend") == "eingehend", klasse


def test_sv_rechnung_label_umbenannt():
    reg = lade_registry(standard_pfad(), reload=True)
    assert reg.klassen["sv_rechnung"]["label"] == "SV-/Gutachterrechnung"


def test_neue_nichtmed_klassen():
    reg = lade_registry(standard_pfad(), reload=True)
    assert reg.klassen["reparaturrechnung"]["schadenposition"] == "rep_rechnung_netto"
    assert reg.klassen["reparaturrechnung"]["label"] == "Reparatur-/Werkstattrechnung"
    assert reg.klassen["mietwagenrechnung"]["schadenposition"] == "mietwagenkosten"
    assert reg.klassen["klagedrohung"]["richtung"] == "beides"
    assert reg.klassen["klagedrohung"]["fristrelevanz"] is True
    assert reg.klassen["mahnschreiben"]["fristrelevanz"] is True
    for aus in ("forderungsschreiben", "sachstandsanfrage", "klage"):
        assert reg.klassen[aus]["richtung"] == "ausgehend"
    for ablage in ("kaufvertrag", "verdienstausfall_nachweis"):
        assert "parser" not in reg.klassen[ablage]


def _erster_regex_treffer(muster_liste, text):
    import re
    for muster in muster_liste:
        m = re.search(muster, text)
        if m:
            return m.group(1) if m.groups() else m.group(0)
    return ""


def test_schadennummer_regex_mit_leerzeichen():
    # Befund 1280/25: VHV-Schadennummer "SD0 0003 2129 28 T01" brach am
    # ersten Leerzeichen ab ("SD0").
    reg = lade_registry(standard_pfad(), reload=True)
    muster = reg.klassen["abrechnungsschreiben"]["regex_felder"]["schadennummer"]
    text = "Schaden-Nr.: SD0 0003 2129 28 T01\nSchadendatum: 17.11.2025"
    assert _erster_regex_treffer(muster, text) == "SD0 0003 2129 28 T01"


def test_schadennummer_regex_kompakt_weiterhin():
    reg = lade_registry(standard_pfad(), reload=True)
    muster = reg.klassen["abrechnungsschreiben"]["regex_felder"]["schadennummer"]
    text = "Schadennummer: 12-345-67890-001\nAktenzeichen Rechtsanwalt: 31-21"
    assert _erster_regex_treffer(muster, text) == "12-345-67890-001"


def test_pruefbericht_vorgangsnummer_aus_schaden_nr():
    # Der VHV-Pruefbericht traegt eine "Schaden-Nr.", keine "Vorgangs-Nr."
    reg = lade_registry(standard_pfad(), reload=True)
    muster = reg.klassen["pruefbericht"]["regex_felder"]["vorgangsnummer"]
    text = "Prüfbericht\nSchaden-Nr.: SD00003212928\nSchadendatum: 17.11.2025"
    assert _erster_regex_treffer(muster, text) == "SD00003212928"


def test_pruefbericht_schema_mit_beschreibungen():
    # Die Betragsfelder brauchen LLM-Anweisungen (Befund 1280/25:
    # abzug_gesamt wurde frei errechnet, brutto falsch belegt).
    reg = lade_registry(standard_pfad(), reload=True)
    schema = reg.klassen["pruefbericht"]["schema"]
    for feld in ("reparaturkosten_brutto", "abzug_gesamt",
                 "reparaturkosten_nach_pruefung",
                 "erstattung_konkrete_reparatur_netto",
                 "erstattung_fiktive_abrechnung_netto"):
        assert isinstance(schema[feld], dict), feld
        assert schema[feld].get("typ") == "number", feld
        assert schema[feld].get("beschreibung"), feld
    # auftraggeber wurde ohne Anweisung mit der Anspruchstellerin belegt
    assert isinstance(schema["auftraggeber"], dict)
    assert schema["auftraggeber"].get("beschreibung")


def test_pruefbericht_hat_netto_nach_abzug_regel():
    reg = lade_registry(standard_pfad(), reload=True)
    namen = [r["name"]
             for r in reg.klassen["pruefbericht"]["validierungsregeln"]]
    assert "netto_nach_abzug_konsistent" in namen


def test_med_und_nachbesichtigung():
    reg = lade_registry(standard_pfad(), reload=True)
    for med in ("arztbericht", "krankenhausbericht", "attest",
                "arbeitsunfaehigkeitsbescheinigung"):
        rf = reg.klassen[med]["regex_felder"]
        assert "datum" in rf, med
        assert "diagnoseschluessel" in rf, med
        assert "diagnoseschluessel" in reg.klassen[med]["schema"], med
        assert "parser" not in reg.klassen[med], med
    nb = reg.klassen["nachbesichtigung"]
    assert "reparaturtage" in nb["regex_felder"]
    assert nb["schema"]["reparaturtage"] == "integer"
