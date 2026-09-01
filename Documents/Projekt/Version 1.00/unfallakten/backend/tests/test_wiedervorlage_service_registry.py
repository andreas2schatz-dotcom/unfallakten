import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-wv-service")

from backend.ramicro import wiedervorlage_service


def test_alte_liste_und_helfer_sind_verschwunden():
    for name in ("RAMICRO_WV_GRUENDE", "_loeseWvGrund"):
        assert not hasattr(wiedervorlage_service, name), \
            f"{name} lebt noch -- die Registry ist nicht die einzige Quelle"


def test_stellungnahme_filter_kommt_aus_der_registry():
    sql = wiedervorlage_service._stellungnahme_sql()
    assert "IN (5, 6, 11, 16)" in sql
