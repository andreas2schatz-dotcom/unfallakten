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
