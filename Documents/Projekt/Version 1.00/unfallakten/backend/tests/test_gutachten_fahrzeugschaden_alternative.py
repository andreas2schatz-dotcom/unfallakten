"""
Reparaturkosten und Wiederbeschaffungswert stehen im Alternativverhaeltnis.

Befund an Akte 589/26 (RA Schatz, 2026-08-26): Das Gutachten-Ereignis hat
Reparaturkosten (4.882,48) UND Wiederbeschaffungswert (13.500,00) als
``gefordert`` geschrieben. Die Uebersicht summiert alle Positionen und zeigte
darum 18.532,48 EUR statt der tatsaechlich geforderten 6.256,57 EUR.

Massgeblich ist ``berechne_abrechnungsart()`` (backend/models/schaden.py) --
dieselbe Quelle, aus der Schaden-Tab und Klage rechnen.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _Basis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="gut_alt_", suffix=".sqlite")
        os.close(fd)
        import backend.db.database as _db
        self._alt_db_path = _db.DB_PATH
        _db.DB_PATH = self._db_pfad
        os.environ["DB_PATH"] = self._db_pfad
        from backend.db.schema_manager import init_db
        init_db()

        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('589/26', '2026-06-11', 'offen')")
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, typ) VALUES ('589/26', 'g.pdf', 'x', 'pdf', "
                "'gutachten')")
            conn.commit()

    def tearDown(self):
        import backend.db.database as _db
        _db.DB_PATH = self._alt_db_path
        os.environ.pop("DB_PATH", None)
        try:
            os.unlink(self._db_pfad)
        except OSError:
            pass

    def _dok_id(self):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id FROM dokumente WHERE dateiname='g.pdf'"
            ).fetchone()["id"]

    def _setze_schaden(self, **felder):
        spalten = ", ".join(felder.keys())
        platz = ", ".join("?" for _ in felder)
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                f"INSERT INTO schadenpositionen (akte_id, {spalten}) "
                f"VALUES ('589/26', {platz})", tuple(felder.values()))
            conn.commit()

    def _betraege(self, eid):
        from backend.db.database import get_connection
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT position_key, betrag FROM ereignis_positionen "
                "WHERE ereignis_id=?", (eid,)).fetchall()
        return {r["position_key"]: r["betrag"] for r in rows}


class TestWaehleFahrzeugschaden(_Basis):
    """Reine Auswahl-Logik, ohne Ereignis-Schreiben."""

    def test_fiktiv_nimmt_reparaturkosten_ohne_wbw(self):
        from backend.services.eingehende_ereignisse import waehle_fahrzeugschaden
        # Akte 589/26: Reparatur 4.882,48 weit unter WBW 13.500 -> Reparaturfall
        self.assertEqual(
            waehle_fahrzeugschaden(
                {"reparaturkosten": 4882.48, "wiederbeschaffung": 13500.0},
                akte_az="589/26"),
            {"reparaturkosten": 4882.48},
        )

    def test_totalschaden_nimmt_wbw_minus_restwert(self):
        from backend.services.eingehende_ereignisse import waehle_fahrzeugschaden
        self.assertEqual(
            waehle_fahrzeugschaden(
                {"reparaturkosten": 14000.0, "wiederbeschaffung": 13500.0,
                 "restwert": 3000.0},
                akte_az="589/26"),
            {"wiederbeschaffung": 10500.0},
        )

    def test_restwert_wird_nie_als_eigene_forderung_geschrieben(self):
        from backend.services.eingehende_ereignisse import waehle_fahrzeugschaden
        for werte in (
            {"reparaturkosten": 4882.48, "wiederbeschaffung": 13500.0,
             "restwert": 3000.0},
            {"reparaturkosten": 14000.0, "wiederbeschaffung": 13500.0,
             "restwert": 3000.0},
        ):
            self.assertNotIn("restwert",
                             waehle_fahrzeugschaden(werte, akte_az="589/26"))

    def test_manuell_gesetzte_abrechnungsart_gewinnt(self):
        self._setze_schaden(abrechnungsart="totalschaden")
        from backend.services.eingehende_ereignisse import waehle_fahrzeugschaden
        # Automatik saehe hier einen Reparaturfall -- die Akte sagt Totalschaden
        self.assertEqual(
            waehle_fahrzeugschaden(
                {"reparaturkosten": 4882.48, "wiederbeschaffung": 13500.0,
                 "restwert": 500.0},
                akte_az="589/26"),
            {"wiederbeschaffung": 13000.0},
        )

    def test_konkrete_abrechnung_ueberlaesst_den_betrag_der_rechnung(self):
        # Liegt eine Reparaturrechnung vor, traegt deren eigenes Ereignis den
        # Fahrzeugschaden (rep_rechnung_netto) -- das Gutachten darf nicht
        # zusaetzlich buchen.
        self._setze_schaden(abrechnungsart="konkret", rep_rechnung_netto=4200.0)
        from backend.services.eingehende_ereignisse import waehle_fahrzeugschaden
        self.assertEqual(
            waehle_fahrzeugschaden(
                {"reparaturkosten": 4882.48, "wiederbeschaffung": 13500.0},
                akte_az="589/26"),
            {},
        )

    def test_ohne_fahrzeugwerte_leer(self):
        from backend.services.eingehende_ereignisse import waehle_fahrzeugschaden
        self.assertEqual(waehle_fahrzeugschaden({}, akte_az="589/26"), {})


class TestFreigabeGutachten(_Basis):

    def test_589_26_schreibt_nur_reparaturkosten_und_wertminderung(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="589/26", dokument_id=self._dok_id(),
            ereignistyp="gutachten_eingegangen", klasse="gutachten",
            felder={
                "reparaturkosten_netto": 4882.48,
                "reparaturkosten_brutto": 5810.15,
                "wiederbeschaffungswert": 13500.0,
                "wertminderung": 150.0,
            },
            datum="2026-08-26",
        )
        self.assertEqual(self._betraege(eid),
                         {"reparaturkosten": 4882.48, "wertminderung": 150.0})

    def test_totalschaden_schreibt_wbw_abzueglich_restwert(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="589/26", dokument_id=self._dok_id(),
            ereignistyp="gutachten_eingegangen", klasse="gutachten",
            felder={
                "reparaturkosten_netto": 14000.0,
                "wiederbeschaffungswert": 13500.0,
                "restwert": 3000.0,
                "wertminderung": 150.0,
            },
            datum="2026-08-26",
        )
        self.assertEqual(self._betraege(eid),
                         {"wiederbeschaffung": 10500.0, "wertminderung": 150.0})


class TestKiDialogGutachten(_Basis):
    """Die manuelle Gutachten-Korrektur nutzt dieselbe Auswahl."""

    def test_uebernahme_addiert_reparatur_und_wbw_nicht(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_gutachten
        eid = erzeuge_aus_gutachten(
            akte_az="589/26", dokument_id=self._dok_id(),
            datum="2026-08-26",
            positionen={
                "reparaturkosten": 4882.48,
                "wiederbeschaffung": 13500.0,
                "restwert": 0.0,
                "wertminderung": 150.0,
                "sv_kosten": 992.34,
            },
        )
        self.assertEqual(
            self._betraege(eid),
            {"reparaturkosten": 4882.48, "wertminderung": 150.0,
             "sv_kosten": 992.34},
        )


# Die Kopfzahl der Uebersicht speist sich seit DECISIONS 2026-08-26 aus den
# Schadenpositionen, nicht mehr aus den Ereignissen -- geprueft in
# test_positionsstatus_ssot.py.


if __name__ == "__main__":
    unittest.main()
