from backend.word import word_service


def test_ausgehende_klassen_sind_gueltige_word_typen():
    g = word_service.gueltige_dok_typen()
    for t in ("forderungsschreiben", "sachstandsanfrage", "klage",
              "mahnschreiben", "klagedrohung"):
        assert t in g, t


def test_reiner_word_typ_bleibt():
    assert "abrechnungsuebersicht" in word_service.gueltige_dok_typen()
