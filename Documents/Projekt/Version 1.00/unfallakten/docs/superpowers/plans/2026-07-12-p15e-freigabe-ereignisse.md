# P1.5e — Review-Freigabe schreibt Ereignisse für alle Klassen · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die im Freigabe-Dialog bestätigten Ereignistypen werden für alle Dokumentenklassen ins Positionsmodell gebucht (heute nur Gutachten), Positionen nur bei echten Beträgen.

**Architecture:** Neue Registry-YAML `klasse_ereignistyp.yaml` liefert je Klasse den vorbelegten eingehenden Ereignistyp. Ein neuer zentraler Helper `erzeuge_aus_freigabe()` in `eingehende_ereignisse.py` leitet je Ereignistyp Positionen ab (Gutachten aus Feldern, Rechnung via `rechnungstyp_mapping`, sonst Fakt-Ereignis) und ruft `schreibe_ereignis(herkunft='freigabe')`. Die Route `post_freigabe` ersetzt ihren Gutachten-Sonderfall durch eine einheitliche Schleife über die bestätigten (bzw. per Registry-Default vorbelegten) Ereignisse.

**Tech Stack:** Python 3 / Flask / SQLite (`backend/`), PyYAML-Registry, unittest; React / Vitest (`frontend/`).

## Global Constraints

- **RA-MICRO read-only** — niemals in die RA-MICRO SQL-Server-DB schreiben, nur SQLite.
- **`schreibe_ereignis()` ist der EINZIGE Schreibpunkt** für `ereignisse` / `ereignis_positionen` / `position_ereignis_cache`. Die Helper dürfen diese Tabellen NICHT direkt beschreiben.
- **Best-Effort:** Jede Ereignis-Panne wird geloggt, nie durchgereicht — die Freigabe (Dokument-Schreiben, `freigaben`-Zeile, `queue_status`) läuft immer regulär durch. Alt-Tabellen/`korrektur_log` bleiben unverändert (Doppelführung).
- **Keine Migration** — die `ereignisse`-Tabellen existieren seit P1.2. Kein Schema-Eingriff, kein DB-Backup nötig.
- **Doppelerfassungs-Guard:** pro `(akte_az, dokument_id, ereignistyp)` nur ein aktuelles Ereignis.
- **Registry fail-loud:** defekte/ungültige YAML → App-Start bricht ab (`RuntimeError`).
- **Zielsprache Deutsch**, keine Kommentare außer bei nicht-offensichtlichem Verhalten.
- **Branch:** `intake-stufe1`. Baseline vor Beginn: **208 failed / 712 passed / 18 skipped** (Backend) + 39 Frontend-Tests. Erwartung am Ende: nur neue grüne Tests, keine neuen Non-Alt-Failures (bekanntes Test-Order-Rauschen in Auth-401/haftungsquote/sv_portal darf wandern).

---

## File Structure

- **Create** `backend/registry/klasse_ereignistyp.yaml` — Mapping Klasse → eingehender Default-Ereignistyp.
- **Modify** `backend/services/positionsmodell_registry.py` — YAML laden + validieren, Feld `klasse_ereignistyp` auf `PositionsmodellRegistry`.
- **Modify** `backend/services/eingehende_ereignisse.py` — neuer Helper `erzeuge_aus_freigabe()` + geteilte Feld→Positionen-Ableitung für Gutachten.
- **Modify** `backend/routers/intake_routes.py` — `post_freigabe` Umbau (Schleife statt Gutachten-Sonderfall), `hole_detail` liefert `default_ereignistyp`; alte `_schreibe_gutachten_ereignis`/`_feld_zu_zahl` entfernen (Logik zieht in den Helper um), `_mandanten_vorsteuer` bleibt.
- **Modify** `frontend/src/views/ReviewQueueView.jsx` — Dropdown-Vorbelegung aus `default_ereignistyp`, Hinweistext aktualisieren, reine Helper-Funktion `initialeEreignisse()` exportieren.
- **Create** `backend/tests/test_p15e_freigabe_ereignisse.py` — Helper-Unit-Tests + HTTP-E2E je Klasse.
- **Modify** `backend/tests/test_positionsmodell_registry.py` — Registry lädt/validiert `klasse_ereignistyp`.
- **Create** `frontend/src/views/ReviewQueueView.prefill.test.jsx` — Vitest für `initialeEreignisse()`.

---

## Task 1: Registry `klasse_ereignistyp.yaml` + Loader

**Files:**
- Create: `backend/registry/klasse_ereignistyp.yaml`
- Modify: `backend/services/positionsmodell_registry.py`
- Test: `backend/tests/test_positionsmodell_registry.py`

**Interfaces:**
- Consumes: bestehende `lade_positionsmodell(pfad=None, *, reload=False) -> PositionsmodellRegistry`, `PositionsmodellRegistry`-Dataclass, `ereignistypen`-Feld (Dict mit je `{richtung, ...}`).
- Produces: `PositionsmodellRegistry.klasse_ereignistyp: Dict[str, str]` (Klasse → Ereignistyp, nur eingehende Typen).

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_positionsmodell_registry.py` am Dateiende (vor `if __name__`) neue Testklasse ergänzen. Zuerst die Imports der Datei prüfen; die vorhandenen Tests nutzen `lade_positionsmodell` mit `reload=True`. Neuer Test:

```python
class TestKlasseEreignistyp(unittest.TestCase):
    def test_mapping_geladen_und_nur_eingehende_typen(self):
        from backend.services.positionsmodell_registry import lade_positionsmodell
        reg = lade_positionsmodell(reload=True)
        self.assertIsInstance(reg.klasse_ereignistyp, dict)
        self.assertEqual(reg.klasse_ereignistyp["gutachten"], "gutachten_eingegangen")
        self.assertEqual(reg.klasse_ereignistyp["abschlepprechnung"], "rechnung_eingegangen")
        self.assertEqual(reg.klasse_ereignistyp["abrechnungsschreiben"], "abrechnung_eingegangen")
        for klasse, typ in reg.klasse_ereignistyp.items():
            self.assertIn(typ, reg.ereignistypen, f"{klasse}->{typ} kein Ereignistyp")
            self.assertEqual(
                reg.ereignistypen[typ]["richtung"], "eingehend",
                f"{klasse}->{typ} ist nicht eingehend",
            )

    def test_ungueltiger_typ_wirft(self):
        import tempfile, os, shutil
        from backend.services.positionsmodell_registry import (
            lade_positionsmodell, standard_pfad,
        )
        quelle = standard_pfad()
        tmp = tempfile.mkdtemp(prefix="reg_")
        try:
            for name in os.listdir(quelle):
                if name.endswith(".yaml"):
                    shutil.copy(os.path.join(quelle, name), os.path.join(tmp, name))
            with open(os.path.join(tmp, "klasse_ereignistyp.yaml"), "w",
                      encoding="utf-8") as f:
                f.write("klasse_ereignistyp:\n  gutachten: forderung_generiert\n")
            with self.assertRaises(RuntimeError):
                lade_positionsmodell(tmp, reload=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_positionsmodell_registry.py::TestKlasseEreignistyp -v`
Expected: FAIL — `AttributeError: ... has no attribute 'klasse_ereignistyp'` bzw. `RuntimeError` fehlt, weil YAML noch nicht existiert (`Positionsmodell-YAML fehlt`).

- [ ] **Step 3a: Create the YAML**

`backend/registry/klasse_ereignistyp.yaml`:

```yaml
# klasse_ereignistyp.yaml — P1.5e
#
# Mapping Dokumentenklasse (backend/registry/klassen/*.yaml) -> vorbelegter
# EINGEHENDER Ereignistyp (ereignistypen.yaml, richtung: eingehend).
#
# Diese Datei liefert im Freigabe-Dialog nur die Vorbelegung; die tatsaechlich
# gebuchten Ereignisse folgen der bestaetigten Dropdown-Auswahl (P1.5e).
#
# Der Loader (positionsmodell_registry.py) prueft: jeder Wert ist ein
# existierender Ereignistyp mit richtung == eingehend.

klasse_ereignistyp:
  gutachten:            gutachten_eingegangen
  rechnung:             rechnung_eingegangen
  abschlepprechnung:    rechnung_eingegangen
  standkostenrechnung:  rechnung_eingegangen
  sv_rechnung:          rechnung_eingegangen
  abrechnungsschreiben: abrechnung_eingegangen
  pruefbericht:         pruefbericht_eingegangen
```

- [ ] **Step 3b: Wire the loader**

In `backend/services/positionsmodell_registry.py`:

1. `_YAML_DATEIEN` erweitern (Zeile ~40):

```python
_YAML_DATEIEN = ("positionsarten.yaml", "ereignistypen.yaml",
                  "aktionen.yaml", "rechnungstyp_mapping.yaml",
                  "klasse_ereignistyp.yaml")
```

2. Dataclass-Feld ergänzen (nach `rechnungstyp_mapping`):

```python
@dataclass(frozen=True)
class PositionsmodellRegistry:
    version: str
    pfad: str
    positionsarten:        Dict[str, Dict[str, Any]]
    ereignistypen:         Dict[str, Dict[str, Any]]
    aktionen:              Dict[str, Dict[str, Any]]
    rechnungstyp_mapping:  Dict[str, str]
    klasse_ereignistyp:    Dict[str, str]
```

3. In `lade_positionsmodell`, nach dem `rechnungstyp_mapping_roh`-Block, extrahieren + validieren (vor dem `registry = PositionsmodellRegistry(...)`):

```python
    klasse_ereignistyp_roh = _extrahiere_mapping(
        daten["klasse_ereignistyp.yaml"],
        "klasse_ereignistyp", "klasse_ereignistyp.yaml",
    )
    klasse_ereignistyp = _validiere_klasse_ereignistyp(
        klasse_ereignistyp_roh, ereignistypen,
    )
```

4. Konstruktor-Aufruf um das Feld erweitern:

```python
    registry = PositionsmodellRegistry(
        version=hasher.hexdigest()[:16],
        pfad=pfad_norm,
        positionsarten=positionsarten,
        ereignistypen=ereignistypen,
        aktionen=aktionen,
        rechnungstyp_mapping=rechnungstyp_mapping,
        klasse_ereignistyp=klasse_ereignistyp,
    )
```

5. Neue Validierungsfunktion (neben `_validiere_rechnungstyp_mapping`):

```python
def _validiere_klasse_ereignistyp(
    roh: Dict[str, Any],
    ereignistypen: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    ergebnis: Dict[str, str] = {}
    for klasse, typ in roh.items():
        if not isinstance(klasse, str) or not klasse.strip():
            raise RuntimeError(
                f"klasse_ereignistyp: leere Klasse {klasse!r}"
            )
        if not isinstance(typ, str) or typ not in ereignistypen:
            raise RuntimeError(
                f"klasse_ereignistyp[{klasse!r}]={typ!r} ist kein "
                "existierender Ereignistyp"
            )
        if ereignistypen[typ]["richtung"] != "eingehend":
            raise RuntimeError(
                f"klasse_ereignistyp[{klasse!r}]={typ!r} ist nicht "
                "eingehend (richtung != 'eingehend')"
            )
        ergebnis[klasse.strip()] = typ.strip()
    return ergebnis
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_positionsmodell_registry.py -v`
Expected: PASS (alle bisherigen + 2 neue).

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klasse_ereignistyp.yaml backend/services/positionsmodell_registry.py backend/tests/test_positionsmodell_registry.py
git commit -m "feat(p15e): Registry klasse_ereignistyp.yaml + fail-loud Loader"
```

---

## Task 2: Helper `erzeuge_aus_freigabe()`

**Files:**
- Modify: `backend/services/eingehende_ereignisse.py`
- Test: `backend/tests/test_p15e_freigabe_ereignisse.py` (neu)

**Interfaces:**
- Consumes: `schreibe_ereignis(...)`, `pruefe_doppelerfassung(akte_az, dokument_id, ereignistyp) -> Optional[int]`, `lade_positionsmodell().rechnungstyp_mapping`, `_registry_kennt_alle(positionen)` (bestehend in derselben Datei).
- Produces:
  - `erzeuge_aus_freigabe(*, akte_az: str, dokument_id: int, ereignistyp: str, klasse: str, felder: Dict[str, Any], vorsteuer: bool = False, benutzer_id: Optional[int] = None, datum: Optional[str] = None) -> Optional[int]`
  - `_feld_zu_zahl(wert) -> Optional[float]` (aus `intake_routes.py` hierher verschoben)
  - `_gutachten_positionen(felder: Dict[str, Any], vorsteuer: bool) -> Dict[str, float]`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_p15e_freigabe_ereignisse.py` (neu) — Teil A, Helper-Unit-Tests. Basis-Fixture analog `test_p15c_gutachten.py`:

```python
"""P1.5e — Review-Freigabe erzeugt Ereignisse fuer alle Klassen."""
import importlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class _HelperBasis(unittest.TestCase):
    def setUp(self):
        fd, self._db_pfad = tempfile.mkstemp(prefix="p15e_", suffix=".sqlite")
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
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )
            conn.execute(
                "INSERT INTO dokumente (akte_id, dateiname, dateipfad, "
                "dateityp, typ) VALUES ('44/22', 'd.pdf', 'x', 'pdf', 'x')"
            )

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
                "SELECT id FROM dokumente WHERE dateiname='d.pdf'"
            ).fetchone()["id"]

    def _positionen(self, eid):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT position_key, wirkung, betrag FROM ereignis_positionen "
                "WHERE ereignis_id=? ORDER BY position_key", (eid,)
            ).fetchall()

    def _kopf(self, eid):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT ereignistyp, herkunft FROM ereignisse WHERE id=?",
                (eid,)
            ).fetchone()


class TestErzeugeAusFreigabe(_HelperBasis):
    def test_gutachten_positionen_gefordert(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="gutachten_eingegangen", klasse="gutachten",
            felder={"reparaturkosten_netto": "6.200,00",
                    "wertminderung": "500,00"},
            datum="2022-04-30",
        )
        self.assertIsInstance(eid, int)
        rows = self._positionen(eid)
        keys = {r["position_key"] for r in rows}
        self.assertEqual(keys, {"reparaturkosten", "wertminderung"})
        for r in rows:
            self.assertEqual(r["wirkung"], "gefordert")
        self.assertEqual(self._kopf(eid)["herkunft"], "freigabe")

    def test_rechnung_beleg_position_aus_mapping(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="rechnung_eingegangen", klasse="abschlepprechnung",
            felder={"bruttobetrag": "350,00"}, datum="2022-05-01",
        )
        rows = self._positionen(eid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["position_key"], "abschleppkosten")
        self.assertEqual(rows[0]["wirkung"], "beleg")
        self.assertEqual(rows[0]["betrag"], 350.0)

    def test_abrechnung_ist_fakt_ohne_positionen(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={"bruttobetrag": "1.000,00"}, datum="2022-05-01",
        )
        self.assertIsInstance(eid, int)
        self.assertEqual(len(self._positionen(eid)), 0)

    def test_rechnung_ohne_mapping_ist_fakt(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        eid = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=self._dok_id(),
            ereignistyp="rechnung_eingegangen", klasse="rechnung",
            felder={"bruttobetrag": "80,00"}, datum="2022-05-01",
        )
        self.assertIsInstance(eid, int)
        self.assertEqual(len(self._positionen(eid)), 0)

    def test_doppelerfassungs_guard(self):
        from backend.services.eingehende_ereignisse import erzeuge_aus_freigabe
        from backend.db.database import get_connection
        did = self._dok_id()
        e1 = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=did,
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={}, datum="2022-05-01",
        )
        e2 = erzeuge_aus_freigabe(
            akte_az="44/22", dokument_id=did,
            ereignistyp="abrechnung_eingegangen", klasse="abrechnungsschreiben",
            felder={}, datum="2022-05-02",
        )
        self.assertEqual(e1, e2)
        with get_connection() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM ereignisse WHERE dokument_id=? "
                "AND ereignistyp='abrechnung_eingegangen'", (did,)
            ).fetchone()[0]
        self.assertEqual(n, 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py::TestErzeugeAusFreigabe -v`
Expected: FAIL — `ImportError: cannot import name 'erzeuge_aus_freigabe'`.

- [ ] **Step 3: Implement the helper**

In `backend/services/eingehende_ereignisse.py` am Dateiende ergänzen:

```python
# ── P1.5e: Review-Freigabe -> eingehendes Ereignis fuer alle Klassen ──────

_GUTACHTEN_FELD_ALIASSE = {
    "reparaturkosten": ("reparaturkosten", "reparaturkosten_netto",
                        "reparaturkosten_brutto"),
    "wiederbeschaffung": ("wiederbeschaffung", "wiederbeschaffungswert"),
    "restwert": ("restwert", "restwert_netto", "restwert_brutto"),
    "wertminderung": ("wertminderung",),
}


def _feld_zu_zahl(wert):
    """'1.011,50' -> 1011.5 ; 850 -> 850.0 ; None/'' -> None.

    Deutsche Notation: Punkt = Tausender, Komma = Dezimal.
    """
    if wert is None:
        return None
    if isinstance(wert, (int, float)):
        return float(wert)
    s = str(wert).strip()
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _gutachten_positionen(felder, vorsteuer):
    """Leitet {position_key: betrag} aus geparsten Gutachten-Feldern ab."""
    positionen = {}
    if not isinstance(felder, dict):
        return positionen
    for pk, aliase in _GUTACHTEN_FELD_ALIASSE.items():
        for name in aliase:
            wert = _feld_zu_zahl(felder.get(name))
            if wert:
                positionen[pk] = wert
                break
    sv_netto = _feld_zu_zahl(felder.get("sv_kosten_netto"))
    sv_brutto = _feld_zu_zahl(felder.get("sv_kosten_brutto"))
    if sv_netto or sv_brutto:
        if vorsteuer:
            wert = sv_netto if sv_netto is not None else sv_brutto
        else:
            wert = sv_brutto if sv_brutto is not None else sv_netto
        if wert:
            positionen["sv_kosten"] = wert
    return positionen


def erzeuge_aus_freigabe(
    *,
    akte_az: str,
    dokument_id: int,
    ereignistyp: str,
    klasse: str,
    felder: Dict[str, Any],
    vorsteuer: bool = False,
    benutzer_id: Optional[int] = None,
    datum: Optional[str] = None,
) -> Optional[int]:
    """Schreibt ein eingehendes Ereignis aus der Review-Freigabe (P1.5e).

    Positionen nur bei eindeutigen Betraegen:
      * gutachten_eingegangen -> Felder-Ableitung, Wirkung 'gefordert'.
      * rechnung_eingegangen  -> ein position_key aus rechnungstyp_mapping,
                                 Wirkung 'beleg', Betrag aus bruttobetrag/
                                 nettobetrag. Fehlt das Mapping -> Fakt.
      * sonst                 -> Fakt-Ereignis ohne Positionen.

    Doppelerfassungs-Guard aktiv. Best-Effort (Ausnahmen werden geloggt).
    """
    try:
        from datetime import date as _date
        if datum is None:
            datum = _date.today().isoformat()

        vorhandene_id = pruefe_doppelerfassung(
            akte_az=akte_az, dokument_id=dokument_id, ereignistyp=ereignistyp,
        )
        if vorhandene_id is not None:
            logger.info(
                "%s bereits erfasst (akte=%s, dokument=%s, alt_ereignis=%d) "
                "-- kein neues Ereignis (Doppelerfassungs-Guard).",
                ereignistyp, akte_az, dokument_id, vorhandene_id,
            )
            return vorhandene_id

        positionen: List[Dict[str, Any]] = []
        if ereignistyp == "gutachten_eingegangen":
            for pk, betrag in _gutachten_positionen(felder, vorsteuer).items():
                positionen.append({
                    "position_key": pk, "wirkung": "gefordert",
                    "betrag": round(betrag, 2),
                })
        elif ereignistyp == "rechnung_eingegangen":
            pk = rechnungstyp_zu_position(klasse, vorsteuer=vorsteuer)
            if pk:
                betrag = (_feld_zu_zahl((felder or {}).get("bruttobetrag"))
                          or _feld_zu_zahl((felder or {}).get("nettobetrag")))
                positionen.append({
                    "position_key": pk, "wirkung": "beleg", "betrag": betrag,
                })

        positionen = _registry_kennt_alle(positionen)

        return schreibe_ereignis(
            akte_az=akte_az,
            ereignistyp=ereignistyp,
            quelle="dokument",
            datum=datum,
            dokument_id=dokument_id,
            herkunft="freigabe",
            positionen=positionen,
            erfasst_von=benutzer_id,
        )
    except Exception as exc:
        logger.warning(
            "%s aus Freigabe fehlgeschlagen (akte %s, dok %s): %s",
            ereignistyp, akte_az, dokument_id, exc,
        )
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py::TestErzeugeAusFreigabe -v`
Expected: PASS (5 Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/eingehende_ereignisse.py backend/tests/test_p15e_freigabe_ereignisse.py
git commit -m "feat(p15e): erzeuge_aus_freigabe Helper (Positionen nur bei echten Betraegen)"
```

---

## Task 3: Route `post_freigabe` Umbau + HTTP-E2E

**Files:**
- Modify: `backend/routers/intake_routes.py`
- Test: `backend/tests/test_p15e_freigabe_ereignisse.py` (Teil B)

**Interfaces:**
- Consumes: `erzeuge_aus_freigabe(...)` (Task 2), `lade_positionsmodell().klasse_ereignistyp` (Task 1), bestehende `_mandanten_vorsteuer(akte_az) -> bool`, `_parse(text) -> dict`.
- Produces: unveränderte Response-Form von `POST /intake/dokument/<id>/freigabe` (`{ok, dokument_id, freigabe_id, akte_az}`). Neuer Nebeneffekt: ein `ereignisse`-Eintrag je bestätigtem/vorbelegtem Ereignistyp.

- [ ] **Step 1: Write the failing E2E tests**

In `backend/tests/test_p15e_freigabe_ereignisse.py` Teil B ergänzen (HTTP, Fixture analog `test_n08_baseline_freigabe.py`):

```python
class _RouteBasis(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="p15e_route_")
        self._db_pfad = os.path.join(self._tmp, "unfallakten.db")
        self._uploads = os.path.join(self._tmp, "uploads")
        self._artefakte = os.path.join(self._tmp, "artefakte")
        os.makedirs(self._uploads, exist_ok=True)
        os.makedirs(self._artefakte, exist_ok=True)
        os.environ["DB_PATH"] = self._db_pfad
        os.environ["UPLOAD_DIR"] = self._uploads
        os.environ["INTAKE_ARTEFAKTE_ROOT"] = self._artefakte

        import backend.db.database as db_mod
        import backend.models.benutzer as ben_mod
        import backend.models.akte as akte_mod
        import backend.models.dokument as dok_mod
        import backend.auth.jwt_handler as jwt_mod
        import backend.auth.middleware as mw_mod
        import backend.auth.service as svc_mod
        import backend.routers.auth_routes as routes_mod
        import backend.app as app_mod
        for m in (db_mod, ben_mod, akte_mod, dok_mod,
                  jwt_mod, mw_mod, svc_mod, routes_mod, app_mod):
            importlib.reload(m)
        self._app = app_mod.erstelle_app({"TESTING": True})
        self.client = self._app.test_client()
        from backend.db.database import get_connection
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO unfallakte (az, unfalldatum, status) "
                "VALUES ('44/22', '2022-04-27', 'offen')"
            )

    def tearDown(self):
        import shutil
        for var in ("DB_PATH", "UPLOAD_DIR", "INTAKE_ARTEFAKTE_ROOT"):
            os.environ.pop(var, None)
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _login(self):
        r = self.client.post("/auth/login", json={
            "email": os.environ.get("ADMIN_EMAIL", "admin@test.de"),
            "passwort": os.environ.get("ADMIN_PASSWORT", "Admin123!"),
        })
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return {"Authorization": f"Bearer {r.get_json()['access_token']}"}

    def _pdf(self):
        import fitz
        doc = fitz.open()
        doc.new_page(width=595, height=842).insert_text((72, 72), "T", fontsize=10)
        return doc.write()

    def _intake(self, klasse, felder, suffix):
        from backend.db.database import get_connection
        pfad = os.path.join(self._uploads, f"a_{suffix}.pdf")
        with open(pfad, "wb") as f:
            f.write(self._pdf())
        sha = (suffix * 64)[:64]
        parse = json.dumps({"felder": felder})
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO intake_dokumente (sha256, arbeitskopie_pfad, "
                "queue_status, klasse, parse_json) "
                "VALUES (?, ?, 'bereit_zur_review', ?, ?)",
                (sha, pfad, klasse, parse),
            )
            return cur.lastrowid

    def _ereignisse(self, ereignistyp):
        from backend.db.database import get_connection
        with get_connection() as conn:
            return conn.execute(
                "SELECT id, herkunft FROM ereignisse WHERE ereignistyp=?",
                (ereignistyp,),
            ).fetchall()


class TestFreigabeRouteE2E(_RouteBasis):
    def test_gutachten_schreibt_ereignis_mit_positionen(self):
        did = self._intake("gutachten",
                            {"reparaturkosten_netto": "6.200,00"}, "gut")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "gutachten_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        evs = self._ereignisse("gutachten_eingegangen")
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["herkunft"], "freigabe")

    def test_abschlepprechnung_schreibt_beleg(self):
        did = self._intake("abschlepprechnung", {"bruttobetrag": "350,00"}, "abs")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "rechnung_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("rechnung_eingegangen")), 1)

    def test_abrechnung_fakt_ohne_positionen(self):
        did = self._intake("abrechnungsschreiben", {}, "abr")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "abrechnung_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("abrechnung_eingegangen")), 1)

    def test_pruefbericht_fakt(self):
        did = self._intake("pruefbericht", {}, "prf")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22",
                  "kandidaten_ereignisse": [{"typ": "pruefbericht_eingegangen"}]})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("pruefbericht_eingegangen")), 1)

    def test_fallback_ohne_kandidaten_nutzt_registry_default(self):
        did = self._intake("gutachten", {"reparaturkosten_netto": "6.200,00"}, "fb")
        h = self._login()
        r = self.client.post(f"/intake/dokument/{did}/freigabe", headers=h,
            json={"akte_az": "44/22"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(len(self._ereignisse("gutachten_eingegangen")), 1)

    def test_re_freigabe_kein_duplikat(self):
        did = self._intake("abrechnungsschreiben", {}, "dup")
        h = self._login()
        body = {"akte_az": "44/22",
                "kandidaten_ereignisse": [{"typ": "abrechnung_eingegangen"}]}
        self.client.post(f"/intake/dokument/{did}/freigabe", headers=h, json=body)
        self.client.post(f"/intake/dokument/{did}/freigabe", headers=h, json=body)
        self.assertEqual(len(self._ereignisse("abrechnung_eingegangen")), 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py::TestFreigabeRouteE2E -v`
Expected: FAIL — die Nicht-Gutachten-Klassen erzeugen noch kein Ereignis (z. B. `test_abschlepprechnung_schreibt_beleg` findet 0 statt 1).

- [ ] **Step 3: Umbau `post_freigabe`**

In `backend/routers/intake_routes.py`, den Gutachten-Sonderblock (aktuell ca. Zeile 598–613, beginnend mit dem Kommentar `# Option A: Gutachten-Freigabe …` bis Ende des `if (dok.get("klasse") …`-Blocks) **ersetzen** durch:

```python
    # P1.5e: Bestaetigte (oder per Registry-Default vorbelegte) Ereignistypen
    # ins Positionsmodell buchen. Positionen nur bei echten Betraegen.
    _schreibe_freigabe_ereignisse(
        dok=dok, akte_az=akte_az, dokument_id=dokument_id,
        payload=payload, benutzer_id=benutzer_id,
    )
```

Danach — direkt nach `post_freigabe` — die neue Helferfunktion **hinzufügen** und die alten `_schreibe_gutachten_ereignis` + `_feld_zu_zahl` **entfernen** (`_mandanten_vorsteuer` bleibt):

```python
def _default_ereignistyp(klasse: Optional[str]) -> Optional[str]:
    if not klasse:
        return None
    try:
        from ..services.positionsmodell_registry import lade_positionsmodell
        return lade_positionsmodell().klasse_ereignistyp.get(klasse)
    except Exception:  # pragma: no cover -- Best-Effort
        return None


def _schreibe_freigabe_ereignisse(*, dok, akte_az, dokument_id, payload,
                                   benutzer_id):
    from ..services.eingehende_ereignisse import erzeuge_aus_freigabe

    klasse = dok.get("klasse") or ""
    felder = _parse(dok.get("parse_json")).get("felder") or {}
    vorsteuer = _mandanten_vorsteuer(akte_az)

    typen = [e.get("typ") for e in (payload.get("kandidaten_ereignisse") or [])
             if isinstance(e, dict) and e.get("typ")]
    if not typen:
        default = _default_ereignistyp(klasse)
        typen = [default] if default else []

    for typ in typen:
        try:
            erzeuge_aus_freigabe(
                akte_az=akte_az, dokument_id=dokument_id, ereignistyp=typ,
                klasse=klasse, felder=felder, vorsteuer=vorsteuer,
                benutzer_id=benutzer_id,
            )
        except Exception as exc:  # pragma: no cover -- Best-Effort
            logger.warning(
                "Freigabe-Ereignis %s fehlgeschlagen (intake=%s, akte=%s): %s",
                typ, dok.get("id"), akte_az, exc,
            )
```

Prüfen, dass `_mandanten_vorsteuer` weiterhin existiert und `_feld_zu_zahl`/`_schreibe_gutachten_ereignis` keine weiteren Aufrufer in der Datei haben (Grep: `_schreibe_gutachten_ereignis`, `_feld_zu_zahl` → nur die entfernten Stellen).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py -v`
Expected: PASS (Teil A + Teil B, alle).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/intake_routes.py backend/tests/test_p15e_freigabe_ereignisse.py
git commit -m "feat(p15e): post_freigabe bucht Ereignisse fuer alle Klassen (Dropdown + Registry-Default)"
```

---

## Task 4: Detail-Endpoint `default_ereignistyp` + Frontend-Vorbelegung

**Files:**
- Modify: `backend/routers/intake_routes.py` (`hole_detail`)
- Modify: `frontend/src/views/ReviewQueueView.jsx`
- Test: `backend/tests/test_p15e_freigabe_ereignisse.py` (Backend), `frontend/src/views/ReviewQueueView.prefill.test.jsx` (Vitest)

**Interfaces:**
- Consumes: `_default_ereignistyp(klasse)` (Task 3), `apiIntake.detail(id)` liefert nun `default_ereignistyp`.
- Produces: `GET /intake/dokument/<id>` Response-Feld `default_ereignistyp: str | null`; exportierte Helferfunktion `initialeEreignisse(defaultTyp)` in `ReviewQueueView.jsx`.

- [ ] **Step 1: Write the failing backend test**

In `backend/tests/test_p15e_freigabe_ereignisse.py`, Klasse `TestFreigabeRouteE2E` ergänzen:

```python
    def test_detail_liefert_default_ereignistyp(self):
        did = self._intake("abschlepprechnung", {}, "det")
        h = self._login()
        r = self.client.get(f"/intake/dokument/{did}", headers=h)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["default_ereignistyp"],
                         "rechnung_eingegangen")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py::TestFreigabeRouteE2E::test_detail_liefert_default_ereignistyp -v`
Expected: FAIL — `KeyError`/`None` statt `"rechnung_eingegangen"`.

- [ ] **Step 3: Add field to `hole_detail`**

In `backend/routers/intake_routes.py::hole_detail`, im Response-Dict (nach `"klasse": dok.get("klasse"),`) ergänzen:

```python
        "default_ereignistyp": _default_ereignistyp(dok.get("klasse")),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py::TestFreigabeRouteE2E::test_detail_liefert_default_ereignistyp -v`
Expected: PASS.

- [ ] **Step 5: Write the failing Vitest**

`frontend/src/views/ReviewQueueView.prefill.test.jsx` (neu):

```jsx
import { describe, it, expect } from "vitest";
import { initialeEreignisse } from "./ReviewQueueView.jsx";

describe("initialeEreignisse", () => {
  it("belegt mit dem Default vor", () => {
    expect(initialeEreignisse("rechnung_eingegangen")).toEqual([
      { typ: "rechnung_eingegangen" },
    ]);
  });
  it("liefert leere Liste ohne Default", () => {
    expect(initialeEreignisse(null)).toEqual([]);
    expect(initialeEreignisse(undefined)).toEqual([]);
  });
});
```

- [ ] **Step 6: Run Vitest to verify it fails**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.prefill.test.jsx`
Expected: FAIL — `initialeEreignisse is not a function` (nicht exportiert).

- [ ] **Step 7: Implement prefill in `ReviewQueueView.jsx`**

1. Reine Helferfunktion auf Modulebene exportieren (oberhalb von `DetailPanel`):

```jsx
export function initialeEreignisse(defaultTyp) {
  return defaultTyp ? [{ typ: defaultTyp }] : [];
}
```

2. In `DetailPanel.laden` (nach `setGewaehlteAkte(...)`) die Vorbelegung setzen:

```jsx
      setGewaehlteAkte(top?.akte_az || "");
      setEreignisse(initialeEreignisse(d.default_ereignistyp));
```

3. Den Hinweistext im `FreigabeDialog` (aktuell „Persistierung ins Positionsmodell folgt mit P1.5e — heute wird nur als Kontext ins korrektur_log geschrieben (Ausnahme: Gutachten …)") ersetzen durch:

```jsx
            Der bestaetigte Ereignistyp wird ins Positionsmodell gebucht.
            Betraege werden nur uebernommen, wenn sie eindeutig im Dokument
            stehen (Gutachten, Rechnungen); sonst wird das Ereignis als
            Faktum ohne Betrag festgehalten.
```

- [ ] **Step 8: Run Vitest + backend to verify pass**

Run: `cd frontend && npx vitest run src/views/ReviewQueueView.prefill.test.jsx`
Expected: PASS.
Run: `python -m pytest backend/tests/test_p15e_freigabe_ereignisse.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/routers/intake_routes.py frontend/src/views/ReviewQueueView.jsx frontend/src/views/ReviewQueueView.prefill.test.jsx backend/tests/test_p15e_freigabe_ereignisse.py
git commit -m "feat(p15e): Detail-Endpoint default_ereignistyp + Dropdown-Vorbelegung"
```

---

## Task 5: Volllauf-Verifikation + TODO-Update

**Files:**
- Modify: `docs/TODO.md`

- [ ] **Step 1: Volle Backend-Suite**

Run: `python -m pytest backend/tests/ -q`
Expected: keine neuen Non-Alt-Failures ggü. Baseline 208f/712p/18s; die ~13 neuen P1.5e-Tests grün. Failure-Wanderung nur in bekannten Alt-Clustern (Auth-401, haftungsquote, sv_portal, prd27, dashboard, s16a_golden_e2e, migration_46). Zahlen notieren.

- [ ] **Step 2: Volle Frontend-Suite**

Run: `cd frontend && npx vitest run`
Expected: bisherige 39 + 2 neue grün.

- [ ] **Step 3: App-Start-Rauchtest (Registry fail-loud greift nicht fälschlich)**

Run: `python -c "from backend.services.positionsmodell_registry import lade_positionsmodell as l; r=l(reload=True); print(len(r.klasse_ereignistyp), 'klassen gemappt')"`
Expected: Ausgabe `7 klassen gemappt`, kein Traceback.

- [ ] **Step 4: TODO fortschreiben**

In `docs/TODO.md` den Abschnitt „🎯 NÄCHSTE SESSION: P1.5e" auf „✅ ERLEDIGT" umstellen, neue Baseline-Zahlen (aus Step 1/2) eintragen, nächsten Schritt auf **P1.8** (Backfill) setzen. Kurzfassung analog der bestehenden P1.x-Einträge (umgesetzte Dateien, Testzahl-Delta, keine Migration).

- [ ] **Step 5: Commit**

```bash
git add docs/TODO.md
git commit -m "docs(todo): P1.5e erledigt, Baseline aktualisiert, naechster Schritt P1.8"
```

---

## Self-Review (durchgeführt beim Schreiben)

**Spec coverage:** Registry-YAML (Task 1) ✓ · `erzeuge_aus_freigabe` + Positions-Ehrlichkeit (Task 2) ✓ · Route-Umbau mit Dropdown-Steuerung + Registry-Default-Fallback + `herkunft='freigabe'` (Task 3) ✓ · Doppelerfassungs-Guard (Task 2/3) ✓ · Detail-`default_ereignistyp` + Frontend-Vorbelegung + Hinweistext (Task 4) ✓ · E2E je Klasse gutachten/abschlepprechnung/abrechnungsschreiben/pruefbericht (Task 3) ✓ · keine Migration (Global Constraints) ✓ · Verifikation (Task 5) ✓.

**Type consistency:** `erzeuge_aus_freigabe(akte_az, dokument_id, ereignistyp, klasse, felder, vorsteuer, benutzer_id, datum)` identisch in Task 2 (Def), Task 3 (Aufruf). `_default_ereignistyp(klasse)` in Task 3 def, Task 4 verwendet. `initialeEreignisse(defaultTyp)` in Task 4 überall gleich. `rechnungstyp_zu_position(klasse, vorsteuer=...)` = bestehende Signatur.

**Placeholder scan:** keine TBD/TODO/„handle edge cases"; jeder Code-Step zeigt vollständigen Code.
