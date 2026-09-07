import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-wv-service")

from backend.ramicro import wiedervorlage_service


def test_alte_liste_und_helfer_sind_verschwunden():
    for name in ("RAMICRO_WV_GRUENDE", "_loeseWvGrund"):
        assert not hasattr(wiedervorlage_service, name), \
            f"{name} lebt noch -- die Registry ist nicht die einzige Quelle"


def test_stellungnahme_filter_kommt_aus_der_registry():
    """11 'Stellungnahme Mandant?', 16 'Stellungnahme Gegner?',
    99 'Stellungnahmefrist' -- dieselbe Regel wie das LIKE '%nahme%'
    auf den Freitext. Vorher standen hier 5 und 6, die laut
    RA-MICRO-Maske 'Rechtsschutz bewilligt?/gezahlt?' heissen."""
    sql = wiedervorlage_service._stellungnahme_sql()
    assert "IN (11, 16, 99)" in sql
