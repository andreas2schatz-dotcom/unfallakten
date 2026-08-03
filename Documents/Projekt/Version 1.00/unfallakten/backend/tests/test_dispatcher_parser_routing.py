from backend.workflow import dispatcher


class _Meta:
    dokumenttyp = "rechnung"


def test_reparaturrechnung_routet_auf_rechnungsparser(monkeypatch):
    aufgerufen = {}
    monkeypatch.setitem(dispatcher._PARSER_FUNKTIONEN, "rechnung",
                        lambda *a, **k: aufgerufen.setdefault("ok", True) or {})
    dispatcher._fuehre_parser_aus("reparaturrechnung", "text", _Meta())
    assert aufgerufen.get("ok") is True


def test_ablage_klasse_ohne_parser_gibt_none():
    assert dispatcher._fuehre_parser_aus("arztbericht", "text", _Meta()) is None
