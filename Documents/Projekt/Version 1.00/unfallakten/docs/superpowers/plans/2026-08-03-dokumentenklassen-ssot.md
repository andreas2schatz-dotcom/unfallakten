# Dokumentenklassen-SSOT (Plan 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die 5 heute getrennten Definitionen einer „Dokumentenklasse" auf die Klassen-Registry (`backend/registry/klassen/*.yaml`) als alleinige handgepflegte Quelle vereinheitlichen und dabei 7 neue Klassen anlegen.

**Architecture:** Jede Klasse trägt künftig alle Attribute in ihrer YAML (`parser`, `richtung`, `ereignistyp`, `schadenposition` — zusätzlich zu den bestehenden `label`/`fristrelevanz`/…). Das Backend liest direkt aus der Registry (`_PARSER_MAP` und `GUELTIGE_DOK_TYPEN` werden abgeleitet). Das Frontend erhält eine **generierte** Datei (`dokumentenklassen.generated.js`) plus die generierten YAMLs `klasse_ereignistyp.yaml`/`rechnungstyp_mapping.yaml`; ein Guard-Test sichert gegen Drift.

**Tech Stack:** Python 3.9 (Backend, PyYAML), pytest, React/Vite (Frontend, ESM-Konstanten).

## Global Constraints

- **RA-MICRO read-only** — nur SQLite/Registry-Dateien ändern, nie in die RA-MICRO-DB schreiben.
- **Fail-Loud-Loader** — defekte/inkonsistente Registry ⇒ App startet nicht (RuntimeError + ERROR-Log). Keine stillen Fallbacks.
- **Python 3.9 kompatibel** — keine `match`-Statements, keine 3.10+-Syntax in Backend-Code.
- **Konvention Dateiname == `klasse:`-Feld** — `<klasse>.yaml`, sonst RuntimeError.
- **Neue Felder sind optional** — die 8 Bestandsklassen müssen ohne Änderung weiter laden.
- **Kommentare nur bei nicht-offensichtlichem Verhalten** (Projektregel CLAUDE.md).
- **Bekannte Parser-Schlüssel:** `rechnung`, `gutachten`, `abrechnungsschreiben`, `pruefbericht`.
- **Gültige Richtungen:** `eingehend` (Default), `ausgehend`, `beides`.
- Backend-Tests laufen im Container: `docker exec unfallakten-backend-dev python -m pytest <pfad> -v`. Falls lokal venv vorhanden, geht auch `python -m pytest`.

---

### Task 1: Loader — optionale Felder format-validieren

**Files:**
- Modify: `backend/intake/registry_loader.py` (Modul-Konstanten + `_validiere_eintrag`)
- Test: `backend/tests/test_registry_loader.py`

**Interfaces:**
- Consumes: bestehende `lade_registry(pfad)` / `_validiere_eintrag(dateiname, data, vorhandene_klassen)`.
- Produces: `BEKANNTE_PARSER: set[str]`, `RICHTUNGEN: set[str]`. `_validiere_eintrag` wirft RuntimeError bei ungültigem `parser`/`richtung`/`ereignistyp`/`schadenposition`-Format.

- [ ] **Step 1: Failing tests schreiben**

In `backend/tests/test_registry_loader.py` ergänzen (nutzt eine tmp-Registry über `INTAKE_REGISTRY_PFAD` / direkten Pfad-Parameter — vorhandenes Test-Muster in der Datei wiederverwenden):

```python
import os
import textwrap
import pytest
from backend.intake import registry_loader


def _schreibe_klasse(dir_pfad, name, extra=""):
    inhalt = textwrap.dedent(f"""\
        klasse: {name}
        marker: []
        regex_felder: {{}}
        schema: {{}}
        pflichtfelder: []
        kritische_felder: []
        validierungsregeln: []
        fristrelevanz: false
        loeschfrist_jahre: 6
        label: {name.capitalize()}
    """) + extra
    with open(os.path.join(dir_pfad, f"{name}.yaml"), "w", encoding="utf-8") as f:
        f.write(inhalt)


def test_gueltiges_parser_feld_laedt(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "parser: rechnung\n")
    reg = registry_loader.lade_registry(str(tmp_path), reload=True)
    assert reg.klassen["rechnung"]["parser"] == "rechnung"


def test_unbekannter_parser_wirft(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "parser: quatsch\n")
    with pytest.raises(RuntimeError, match="parser"):
        registry_loader.lade_registry(str(tmp_path), reload=True)


def test_ungueltige_richtung_wirft(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "richtung: seitwaerts\n")
    with pytest.raises(RuntimeError, match="richtung"):
        registry_loader.lade_registry(str(tmp_path), reload=True)


def test_ereignistyp_muss_string_sein(tmp_path):
    _schreibe_klasse(str(tmp_path), "rechnung", "ereignistyp: 42\n")
    with pytest.raises(RuntimeError, match="ereignistyp"):
        registry_loader.lade_registry(str(tmp_path), reload=True)
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_loader.py -k "parser or richtung or ereignistyp" -v`
Expected: FAIL (die neuen Felder werden noch nicht validiert; `test_unbekannter_parser_wirft` schlägt fehl, weil kein RuntimeError kommt).

- [ ] **Step 3: Loader erweitern**

In `backend/intake/registry_loader.py` oben bei den Modul-Konstanten (nach `PFLICHT_FELDER`) einfügen:

```python
BEKANNTE_PARSER = {"rechnung", "gutachten", "abrechnungsschreiben", "pruefbericht"}
RICHTUNGEN = {"eingehend", "ausgehend", "beides"}
```

In `_validiere_eintrag(...)`, nach dem bestehenden `bezeichnung_felder`-Block, anhängen:

```python
    if "parser" in data:
        p = data["parser"]
        if not isinstance(p, str) or p not in BEKANNTE_PARSER:
            raise RuntimeError(
                f"'parser' {p!r} unbekannt in {dateiname} "
                f"(erlaubt: {sorted(BEKANNTE_PARSER)})"
            )
    if "richtung" in data:
        r = data["richtung"]
        if not isinstance(r, str) or r not in RICHTUNGEN:
            raise RuntimeError(
                f"'richtung' {r!r} ungueltig in {dateiname} "
                f"(erlaubt: {sorted(RICHTUNGEN)})"
            )
    if "ereignistyp" in data and not (
        isinstance(data["ereignistyp"], str) and data["ereignistyp"]
    ):
        raise RuntimeError(
            f"'ereignistyp' muss ein nichtleerer String sein in {dateiname}"
        )
    if "schadenposition" in data and not (
        isinstance(data["schadenposition"], str) and data["schadenposition"]
    ):
        raise RuntimeError(
            f"'schadenposition' muss ein nichtleerer String sein in {dateiname}"
        )
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_loader.py -v`
Expected: PASS (alle, inkl. der bestehenden Loader-Tests).

- [ ] **Step 5: Commit**

```bash
git add backend/intake/registry_loader.py backend/tests/test_registry_loader.py
git commit -m "feat(registry): optionale Klassen-Felder parser/richtung/ereignistyp/schadenposition validieren"
```

---

### Task 2: Startup — Kreuzvalidierung gegen Positionsmodell-Registry

**Files:**
- Modify: `backend/intake/registry_loader.py` (neue Funktion `validiere_gegen_positionsmodell`)
- Modify: `backend/app.py:137-138` (Aufruf nach dem Laden beider Registries)
- Test: `backend/tests/test_registry_loader.py`

**Interfaces:**
- Consumes: `Registry` (aus `lade_registry`), `PositionsmodellRegistry` (aus `positionsmodell_registry.lade_positionsmodell`). Sondermarker `__sv_kosten_vorsteuer__`.
- Produces: `validiere_gegen_positionsmodell(klassen_reg, pos_reg) -> None` — wirft RuntimeError, wenn ein `ereignistyp` nicht existiert / nicht `eingehend` ist oder eine `schadenposition` kein gültiger position_key ist.

- [ ] **Step 1: Failing test schreiben**

In `backend/tests/test_registry_loader.py`:

```python
from types import SimpleNamespace
from backend.intake.registry_loader import validiere_gegen_positionsmodell


def _pos_reg_stub():
    return SimpleNamespace(
        ereignistypen={"rechnung_eingegangen": {"richtung": "eingehend"},
                       "forderung_generiert": {"richtung": "ausgehend"}},
        positionsarten={"mietwagenkosten": {}, "rep_rechnung_netto": {}},
    )


def test_ereignistyp_nicht_eingehend_wirft():
    klassen_reg = SimpleNamespace(klassen={
        "x": {"klasse": "x", "ereignistyp": "forderung_generiert"}})
    with pytest.raises(RuntimeError, match="eingehend"):
        validiere_gegen_positionsmodell(klassen_reg, _pos_reg_stub())


def test_unbekannte_schadenposition_wirft():
    klassen_reg = SimpleNamespace(klassen={
        "x": {"klasse": "x", "schadenposition": "gibtsnicht"}})
    with pytest.raises(RuntimeError, match="schadenposition"):
        validiere_gegen_positionsmodell(klassen_reg, _pos_reg_stub())


def test_sv_vorsteuer_marker_erlaubt():
    klassen_reg = SimpleNamespace(klassen={
        "sv_rechnung": {"klasse": "sv_rechnung",
                        "schadenposition": "__sv_kosten_vorsteuer__"}})
    validiere_gegen_positionsmodell(klassen_reg, _pos_reg_stub())  # kein Fehler
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_loader.py -k "eingehend or schadenposition or vorsteuer" -v`
Expected: FAIL mit `ImportError: cannot import name 'validiere_gegen_positionsmodell'`.

- [ ] **Step 3: Funktion implementieren**

In `backend/intake/registry_loader.py` (unten, nach `_validiere_eintrag`):

```python
_SV_VORSTEUER_MARKER = "__sv_kosten_vorsteuer__"


def validiere_gegen_positionsmodell(klassen_reg, pos_reg):
    """Kreuzvalidierung: ereignistyp muss existieren + eingehend sein,
    schadenposition muss ein gueltiger position_key sein. Fail-Loud."""
    for klasse, data in klassen_reg.klassen.items():
        typ = data.get("ereignistyp")
        if typ is not None:
            spec = pos_reg.ereignistypen.get(typ)
            if spec is None:
                raise RuntimeError(
                    f"Klasse {klasse!r}: ereignistyp {typ!r} existiert nicht"
                )
            if spec["richtung"] != "eingehend":
                raise RuntimeError(
                    f"Klasse {klasse!r}: ereignistyp {typ!r} ist nicht eingehend"
                )
        pos = data.get("schadenposition")
        if pos is not None and pos != _SV_VORSTEUER_MARKER:
            if pos not in pos_reg.positionsarten:
                raise RuntimeError(
                    f"Klasse {klasse!r}: schadenposition {pos!r} ist kein "
                    "gueltiger position_key"
                )
```

- [ ] **Step 4: Startup-Aufruf einbauen**

In `backend/app.py` direkt nach den bestehenden Zeilen 137-138:

```python
    from .intake.registry_loader import lade_registry, standard_pfad
    _reg = lade_registry(standard_pfad(), reload=True)
```

anfügen:

```python
    from .intake.registry_loader import validiere_gegen_positionsmodell
    from .services.positionsmodell_registry import (
        lade_positionsmodell, standard_pfad as _pm_pfad)
    validiere_gegen_positionsmodell(_reg, lade_positionsmodell(_pm_pfad()))
```

- [ ] **Step 5: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_loader.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/intake/registry_loader.py backend/app.py backend/tests/test_registry_loader.py
git commit -m "feat(registry): Kreuzvalidierung Klassen<->Positionsmodell beim App-Start"
```

---

### Task 3: 8 Bestandsklassen um die neuen Felder ergänzen

**Files:**
- Modify: `backend/registry/klassen/abrechnungsschreiben.yaml`, `abschlepprechnung.yaml`, `gutachten.yaml`, `pruefbericht.yaml`, `rechnung.yaml`, `sonstiges.yaml`, `standkostenrechnung.yaml`, `sv_rechnung.yaml`
- Test: `backend/tests/test_registry_felder.py` (neu)

**Interfaces:**
- Consumes: heutige Werte aus `_PARSER_MAP` (dispatcher.py:694), `klasse_ereignistyp.yaml`, `rechnungstyp_mapping.yaml`.
- Produces: jede Bestandsklasse trägt die passenden `parser`/`richtung`/`ereignistyp`/`schadenposition`.

Zielwerte (aus den heutigen Maps abgeleitet):

| Klasse | parser | richtung | ereignistyp | schadenposition |
|---|---|---|---|---|
| abrechnungsschreiben | abrechnungsschreiben | eingehend | abrechnung_eingegangen | — |
| pruefbericht | pruefbericht | eingehend | pruefbericht_eingegangen | — |
| gutachten | gutachten | eingehend | gutachten_eingegangen | — |
| sv_rechnung | rechnung | eingehend | rechnung_eingegangen | `__sv_kosten_vorsteuer__` |
| rechnung | rechnung | eingehend | rechnung_eingegangen | — |
| abschlepprechnung | rechnung | eingehend | rechnung_eingegangen | abschleppkosten |
| standkostenrechnung | rechnung | eingehend | rechnung_eingegangen | standkosten |
| sonstiges | — | eingehend | — | — |

- [ ] **Step 1: Failing test schreiben**

`backend/tests/test_registry_felder.py`:

```python
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py -v`
Expected: FAIL (Felder fehlen noch).

- [ ] **Step 3: YAMLs ergänzen**

Beispiel `backend/registry/klassen/abschlepprechnung.yaml` — am Dateiende anhängen (analog für alle anderen laut Tabelle):

```yaml
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: abschleppkosten
```

`sv_rechnung.yaml`:

```yaml
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: __sv_kosten_vorsteuer__
```

`gutachten.yaml`:

```yaml
parser: gutachten
richtung: eingehend
ereignistyp: gutachten_eingegangen
```

`abrechnungsschreiben.yaml`:

```yaml
parser: abrechnungsschreiben
richtung: eingehend
ereignistyp: abrechnung_eingegangen
```

`pruefbericht.yaml`:

```yaml
parser: pruefbericht
richtung: eingehend
ereignistyp: pruefbericht_eingegangen
```

`rechnung.yaml` und `standkostenrechnung.yaml` analog (siehe Tabelle). `sonstiges.yaml` nur:

```yaml
richtung: eingehend
```

- [ ] **Step 4: Test + Loader-Regression laufen lassen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py backend/tests/test_registry_golden.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klassen/*.yaml backend/tests/test_registry_felder.py
git commit -m "feat(registry): Bestandsklassen um parser/richtung/ereignistyp/schadenposition ergaenzt"
```

---

### Task 4: 7 neue Klassen-YAMLs anlegen

**Files:**
- Create: `backend/registry/klassen/reparaturrechnung.yaml`, `mietwagenrechnung.yaml`, `arztbericht.yaml`, `krankenhausbericht.yaml`, `attest.yaml`, `mahnschreiben.yaml`, `klagedrohung.yaml`
- Test: `backend/tests/test_registry_felder.py` (erweitern)

**Interfaces:**
- Consumes: `BEKANNTE_PARSER`, `ereignistypen.yaml`, `positionsarten.yaml`.
- Produces: Registry lädt 15 Klassen; die 7 neuen mit den Feldern aus Spec §5.

- [ ] **Step 1: Failing test schreiben**

In `backend/tests/test_registry_felder.py` anhängen:

```python
def test_neue_klassen_vorhanden():
    reg = lade_registry(standard_pfad(), reload=True)
    assert "reparaturrechnung" in reg.klassen
    assert reg.klassen["reparaturrechnung"]["schadenposition"] == "rep_rechnung_netto"
    assert reg.klassen["mietwagenrechnung"]["schadenposition"] == "mietwagenkosten"
    assert reg.klassen["klagedrohung"]["richtung"] == "beides"
    assert reg.klassen["klagedrohung"]["fristrelevanz"] is True
    assert reg.klassen["mahnschreiben"]["fristrelevanz"] is True
    for ablage in ("arztbericht", "krankenhausbericht", "attest"):
        assert "parser" not in reg.klassen[ablage]
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py::test_neue_klassen_vorhanden -v`
Expected: FAIL (KeyError, Klassen fehlen).

- [ ] **Step 3: Die 7 YAMLs anlegen**

`backend/registry/klassen/reparaturrechnung.yaml`:

```yaml
klasse: reparaturrechnung

marker:
  - Reparaturrechnung
  - Reparatur-Rechnung
  - Reparaturkostenrechnung

regex_felder:
  rechnungsnummer:
    - "Rechnungs?[\\-\\s]?nummer[:\\s]+([A-Z0-9\\-/]+)"
  rechnungsdatum:
    - "Rechnungsdatum[:\\s]+(\\d{2}\\.\\d{2}\\.\\d{4})"

schema:
  rechnungsnummer: string
  rechnungsdatum: date
  nettobetrag: number
  bruttobetrag: number

pflichtfelder: []
kritische_felder:
  - bruttobetrag
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Reparaturrechnung
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: rep_rechnung_netto
bezeichnung_felder:
  datum: rechnungsdatum
```

`mietwagenrechnung.yaml` (analog, aber):

```yaml
klasse: mietwagenrechnung

marker:
  - Mietwagen
  - Mietfahrzeug
  - Ersatzfahrzeug
  - Mietvertrag

regex_felder:
  rechnungsnummer:
    - "Rechnungs?[\\-\\s]?nummer[:\\s]+([A-Z0-9\\-/]+)"
  rechnungsdatum:
    - "Rechnungsdatum[:\\s]+(\\d{2}\\.\\d{2}\\.\\d{4})"

schema:
  rechnungsnummer: string
  rechnungsdatum: date
  nettobetrag: number
  bruttobetrag: number

pflichtfelder: []
kritische_felder:
  - bruttobetrag
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Mietwagenrechnung
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: mietwagenkosten
bezeichnung_felder:
  datum: rechnungsdatum
```

`arztbericht.yaml` (reines Ablage-Etikett — wenige, trennscharfe Marker):

```yaml
klasse: arztbericht

marker:
  - Arztbericht
  - Befundbericht
  - Aerztlicher Bericht

regex_felder: {}

schema:
  aussteller: string
  datum: date
  diagnose: string

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 10
label: Arztbericht
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

`krankenhausbericht.yaml` (analog `arztbericht`, aber):

```yaml
klasse: krankenhausbericht

marker:
  - Entlassungsbericht
  - Krankenhausbericht
  - Klinikbericht

regex_felder: {}

schema:
  aussteller: string
  datum: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 10
label: Krankenhausbericht
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

`attest.yaml`:

```yaml
klasse: attest

marker:
  - Arbeitsunfaehigkeitsbescheinigung
  - AU-Bescheinigung
  - Attest

regex_felder: {}

schema:
  aussteller: string
  datum: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 10
label: Attest (AU / Haushalt)
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

`mahnschreiben.yaml` (kein Parser in Plan 1 — Frist-Parser kommt in Plan 2; `richtung: beides`, fristrelevant):

```yaml
klasse: mahnschreiben

marker:
  - Mahnung
  - Zahlungserinnerung
  - letztmalige Aufforderung

regex_felder: {}

schema:
  datum: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: true
loeschfrist_jahre: 6
label: Mahnschreiben
richtung: beides
bezeichnung_felder:
  datum: datum
```

`klagedrohung.yaml`:

```yaml
klasse: klagedrohung

marker:
  - Klageandrohung
  - gerichtliche Geltendmachung
  - Klage einreichen
  - letztmalige Frist

regex_felder: {}

schema:
  datum: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: true
loeschfrist_jahre: 6
label: Klagedrohung / Fristsetzung
richtung: beides
bezeichnung_felder:
  datum: datum
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py backend/tests/test_registry_loader.py -v`
Expected: PASS (inkl. Kreuzvalidierung: alle `ereignistyp`/`schadenposition` gültig).

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klassen/reparaturrechnung.yaml backend/registry/klassen/mietwagenrechnung.yaml backend/registry/klassen/arztbericht.yaml backend/registry/klassen/krankenhausbericht.yaml backend/registry/klassen/attest.yaml backend/registry/klassen/mahnschreiben.yaml backend/registry/klassen/klagedrohung.yaml backend/tests/test_registry_felder.py
git commit -m "feat(registry): 7 neue Dokumentenklassen (reparatur-/mietwagenrechnung, arzt-/krankenhausbericht, attest, mahnschreiben, klagedrohung)"
```

---

### Task 5: Dispatcher — `_PARSER_MAP` durch Registry-Lookup ersetzen

**Files:**
- Modify: `backend/workflow/dispatcher.py` (`_PARSER_MAP` → `_PARSER_FUNKTIONEN` + `_fuehre_parser_aus`)
- Test: `backend/tests/test_dispatcher_parser_routing.py` (neu)

**Interfaces:**
- Consumes: `lade_registry`/`standard_pfad` aus `backend.intake.registry_loader`; die Parser-Wrapper `_parse_rechnung`/`_parse_gutachten`/`_parse_abrechnungsschreiben`/`_parse_pruefbericht`.
- Produces: `_fuehre_parser_aus(klasse, ...)` routet über das `parser`-Feld der Registry; unbekannte/parser-lose Klasse → None.

- [ ] **Step 1: Failing test schreiben**

`backend/tests/test_dispatcher_parser_routing.py`:

```python
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_dispatcher_parser_routing.py -v`
Expected: FAIL (`_PARSER_FUNKTIONEN` existiert nicht).

- [ ] **Step 3: dispatcher.py umbauen**

`_PARSER_MAP` (Zeilen 694-703) ersetzen durch eine parser-id → Funktion-Map:

```python
# parser-Schluessel (aus Klassen-Registry) -> Parser-Funktion
_PARSER_FUNKTIONEN = {
    "abrechnungsschreiben": _parse_abrechnungsschreiben,
    "pruefbericht":         _parse_pruefbericht,
    "gutachten":            _parse_gutachten,
    "rechnung":             _parse_rechnung,
}
```

`_fuehre_parser_aus` (Zeilen 708-720) anpassen:

```python
def _fuehre_parser_aus(klasse, norm_text, meta, versicherer_kuerzel=None,
                       pruefdienstleister=None, has_image_pages=False):
    # type: (str, str, Any, Optional[str], Optional[str], bool) -> Optional[Dict]
    """Routet ueber das 'parser'-Feld der Klassen-Registry.
    Neue Klasse braucht nur einen 'parser:'-Eintrag in ihrer YAML."""
    from ..intake.registry_loader import lade_registry, standard_pfad
    reg = lade_registry(standard_pfad())
    eintrag = reg.klassen.get(klasse) or {}
    parser_id = eintrag.get("parser")
    parser_fn = _PARSER_FUNKTIONEN.get(parser_id) if parser_id else None
    if parser_fn is None:
        logger.info("Kein Parser fuer klasse=%s (parser=%s).", klasse, parser_id)
        return None
    return parser_fn(norm_text, meta, versicherer_kuerzel, pruefdienstleister, has_image_pages)
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_dispatcher_parser_routing.py -v`
Expected: PASS.

- [ ] **Step 5: Dispatcher-Regression**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/ -k dispatch -v`
Expected: PASS (bestehende Dispatcher-Tests unberührt).

- [ ] **Step 6: Commit**

```bash
git add backend/workflow/dispatcher.py backend/tests/test_dispatcher_parser_routing.py
git commit -m "refactor(dispatcher): Parser-Routing aus Klassen-Registry statt hartkodiertem _PARSER_MAP"
```

---

### Task 6: `GUELTIGE_DOK_TYPEN` aus der Registry ableiten

**Files:**
- Modify: `backend/word/word_service.py:54-59`
- Test: `backend/tests/test_word_gueltige_typen.py` (neu)

**Interfaces:**
- Consumes: `lade_registry`/`standard_pfad`; `richtung`-Feld.
- Produces: `GUELTIGE_DOK_TYPEN` enthält alle Klassen mit `richtung` ∈ {ausgehend, beides} **plus** die bestehenden reinen Word-Typen ohne Registry-Klasse (`abrechnungsuebersicht`).

- [ ] **Step 1: Failing test schreiben**

`backend/tests/test_word_gueltige_typen.py`:

```python
from backend.word import word_service


def test_klagedrohung_ist_gueltiger_word_typ():
    assert "klagedrohung" in word_service.gueltige_dok_typen()
    assert "mahnschreiben" in word_service.gueltige_dok_typen()


def test_reine_word_typen_bleiben():
    assert "abrechnungsuebersicht" in word_service.gueltige_dok_typen()
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_word_gueltige_typen.py -v`
Expected: FAIL (`gueltige_dok_typen` existiert nicht; `klagedrohung` fehlt).

- [ ] **Step 3: word_service.py umbauen**

`GUELTIGE_DOK_TYPEN`-Set (Zeilen 54-59) ersetzen durch eine Funktion, die reine Word-Typen mit den ausgehenden Registry-Klassen vereint:

```python
# Word-Typen ohne eigene Registry-Klasse (rein ausgehende Vorlagen)
_REINE_WORD_TYPEN = {"forderungsschreiben", "sachstandsanfrage",
                     "abrechnungsuebersicht", "klage"}


def gueltige_dok_typen():
    """Erlaubte Dokumenttypen fuer den Word-Generator: reine Word-Vorlagen
    plus alle Registry-Klassen mit richtung ausgehend/beides."""
    from ..intake.registry_loader import lade_registry, standard_pfad
    reg = lade_registry(standard_pfad())
    aus_registry = {
        k for k, d in reg.klassen.items()
        if d.get("richtung") in ("ausgehend", "beides")
    }
    return _REINE_WORD_TYPEN | aus_registry
```

Die Prüfung in `generiere_und_speichere` (Zeile 108) anpassen:

```python
    if dok_typ not in gueltige_dok_typen():
```

und die Fehlermeldung (Zeile 111) auf `sorted(gueltige_dok_typen())` umstellen.

In `backend/routers/word_routes.py` den Import (Zeile 17) und die Verwendung (Zeile 64) von `GUELTIGE_DOK_TYPEN` auf `gueltige_dok_typen()` umstellen.

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_word_gueltige_typen.py backend/tests/ -k word -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/word/word_service.py backend/routers/word_routes.py backend/tests/test_word_gueltige_typen.py
git commit -m "refactor(word): GUELTIGE_DOK_TYPEN aus Registry (richtung ausgehend/beides) ableiten"
```

---

### Task 7: Codegen-Skript + generierte Artefakte + FE-Umstellung + Guard-Test

**Files:**
- Create: `tools/gen_dokumentenklassen.py`
- Create: `frontend/src/config/dokumentenklassen.generated.js` (generiert)
- Modify: `backend/registry/klasse_ereignistyp.yaml`, `backend/registry/rechnungstyp_mapping.yaml` (werden generiert, Header-Kommentar)
- Modify: `frontend/src/config/constants.js` (Re-Export statt Hardcode)
- Test: `backend/tests/test_gen_dokumentenklassen_guard.py` (neu)

**Interfaces:**
- Consumes: `lade_registry`; `label`/`richtung`/`ereignistyp`/`schadenposition`.
- Produces: `tools/gen_dokumentenklassen.py` mit `render_alles() -> dict[str, str]` (Pfad → Inhalt) und `main()` (schreibt Dateien). Generiert `DOK_TYPEN`, `KLASSE_TO_POS`, `klasse_ereignistyp`, `rechnungstyp_mapping`.

- [ ] **Step 1: Failing Guard-Test schreiben**

`backend/tests/test_gen_dokumentenklassen_guard.py`:

```python
import os
from tools.gen_dokumentenklassen import render_alles

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
PROJEKT = os.path.dirname(WURZEL)


def test_generate_ist_aktuell():
    for rel_pfad, soll in render_alles().items():
        voll = os.path.join(PROJEKT, rel_pfad)
        with open(voll, "r", encoding="utf-8") as f:
            ist = f.read()
        assert ist == soll, (
            f"{rel_pfad} ist veraltet — 'python tools/gen_dokumentenklassen.py' "
            "ausfuehren und committen."
        )
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_gen_dokumentenklassen_guard.py -v`
Expected: FAIL (`tools.gen_dokumentenklassen` existiert nicht).

- [ ] **Step 3: Codegen-Skript schreiben**

`tools/gen_dokumentenklassen.py`:

```python
"""Generiert aus der Klassen-Registry (SSOT) die abgeleiteten Artefakte:
  * frontend/src/config/dokumentenklassen.generated.js  (DOK_TYPEN, KLASSE_TO_POS)
  * backend/registry/klasse_ereignistyp.yaml            (Klasse -> Ereignistyp)
  * backend/registry/rechnungstyp_mapping.yaml          (Klasse -> position_key)

Aufruf:  python tools/gen_dokumentenklassen.py
Der Guard-Test test_gen_dokumentenklassen_guard.py schlaegt fehl, wenn eine
dieser Dateien nicht mehr zur Registry passt.
"""
import json
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WURZEL)

from backend.intake.registry_loader import lade_registry, standard_pfad

_WARNUNG = "# GENERIERT von tools/gen_dokumentenklassen.py — NICHT von Hand editieren.\n"


def _sortierte_klassen():
    reg = lade_registry(standard_pfad(), reload=True)
    return sorted(reg.klassen.items())


def _render_js():
    dok_typen = [{"value": k, "label": d.get("label", k)}
                 for k, d in _sortierte_klassen()]
    klasse_to_pos = {k: [d["schadenposition"]]
                     for k, d in _sortierte_klassen()
                     if d.get("schadenposition")
                     and d["schadenposition"] != "__sv_kosten_vorsteuer__"}
    zeilen = [
        "// GENERIERT von tools/gen_dokumentenklassen.py — NICHT von Hand editieren.",
        "const DOK_TYPEN = " + json.dumps(dok_typen, ensure_ascii=False, indent=2) + ";",
        "const KLASSE_TO_POS = " + json.dumps(klasse_to_pos, ensure_ascii=False, indent=2) + ";",
        "export { DOK_TYPEN, KLASSE_TO_POS };",
        "",
    ]
    return "\n".join(zeilen)


def _render_klasse_ereignistyp():
    eintraege = {k: d["ereignistyp"] for k, d in _sortierte_klassen()
                 if d.get("ereignistyp")}
    zeilen = [_WARNUNG, "klasse_ereignistyp:"]
    for k, typ in sorted(eintraege.items()):
        zeilen.append(f"  {k}: {typ}")
    return "\n".join(zeilen) + "\n"


def _render_rechnungstyp_mapping():
    eintraege = {k: d["schadenposition"] for k, d in _sortierte_klassen()
                 if d.get("schadenposition")}
    zeilen = [_WARNUNG, "rechnungstyp_mapping:"]
    for k, pos in sorted(eintraege.items()):
        zeilen.append(f"  {k}: {pos}")
    return "\n".join(zeilen) + "\n"


def render_alles():
    return {
        "frontend/src/config/dokumentenklassen.generated.js": _render_js(),
        "backend/registry/klasse_ereignistyp.yaml": _render_klasse_ereignistyp(),
        "backend/registry/rechnungstyp_mapping.yaml": _render_rechnungstyp_mapping(),
    }


def main():
    for rel_pfad, inhalt in render_alles().items():
        voll = os.path.join(WURZEL, rel_pfad)
        with open(voll, "w", encoding="utf-8", newline="\n") as f:
            f.write(inhalt)
        print("geschrieben:", rel_pfad)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Skript ausführen (Artefakte erzeugen)**

Run: `docker exec unfallakten-backend-dev python tools/gen_dokumentenklassen.py`
Expected: drei „geschrieben:"-Zeilen. Danach `git diff` prüfen: `klasse_ereignistyp.yaml`/`rechnungstyp_mapping.yaml` enthalten jetzt auch die neuen Klassen; `dokumentenklassen.generated.js` ist neu.

**Prüfen (Reconciliation):** In der neuen `dokumentenklassen.generated.js` steht `"reparaturrechnung": ["rep_rechnung_netto"]` (nicht `_brutto`). Das ist die bewusste Angleichung ans Backend (Spec §6).

- [ ] **Step 5: constants.js auf Re-Export umstellen**

In `frontend/src/config/constants.js`:
- Die Hardcode-Definitionen `DOK_TYPEN` (Zeile 191) und `KLASSE_TO_POS` (Zeilen 514-521) **entfernen**.
- Oben ergänzen: `import { DOK_TYPEN, KLASSE_TO_POS } from "./dokumentenklassen.generated.js";`
- Im `export { ... }`-Block bleiben `DOK_TYPEN` und `KLASSE_TO_POS` unverändert gelistet (öffentliche API identisch → `DokumenteSection.jsx` u. a. unverändert).

- [ ] **Step 6: Guard-Test + Frontend-Build**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_gen_dokumentenklassen_guard.py -v`
Expected: PASS.

Run: `cd frontend && npm run build`
Expected: Build erfolgreich (Import der generierten Datei auflösbar, keine ungenutzten-Export-Fehler).

- [ ] **Step 7: Commit**

```bash
git add tools/gen_dokumentenklassen.py frontend/src/config/dokumentenklassen.generated.js frontend/src/config/constants.js backend/registry/klasse_ereignistyp.yaml backend/registry/rechnungstyp_mapping.yaml backend/tests/test_gen_dokumentenklassen_guard.py
git commit -m "feat(klassen): FE-Liste + Mapping-YAMLs aus Registry generieren, Guard-Test gegen Drift"
```

---

### Task 8: Gesamt-Regression + Browser-Nachtest

**Files:** keine Änderung — Verifikation.

- [ ] **Step 1: Volle Backend-Testsuite**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/ -q`
Expected: PASS (keine Regression durch die neue Ableitung).

- [ ] **Step 2: App-Start prüfen (Fail-Loud-Kreuzvalidierung)**

Run: `docker restart unfallakten-backend-dev && docker logs --tail 40 unfallakten-backend-dev`
Expected: „Registry geladen: 15 Klassen …", kein RuntimeError.

- [ ] **Step 3: Browser-Nachtest**

Im Dokumente-Reiter einer Testakte das Klassen-Dropdown öffnen: die 7 neuen Klassen erscheinen mit ihren Labels; eine Reparaturrechnung hochladen/zuordnen → landet auf Position „Reparaturkosten (Rechnung, netto)". Ergebnis notieren.

- [ ] **Step 4: Abschluss-Commit (falls Notizen/Doku)**

```bash
git add -A ':(exclude)../../*'
git commit -m "test(klassen): Gesamt-Regression + Browser-Nachtest Plan 1 gruen" --allow-empty
```

---

## Self-Review

**Spec-Abdeckung (Spec §-weise):**
- §4 Schema-Erweiterung → Task 1 (Format) + Task 2 (Kreuzvalidierung). ✅
- §5 Die 7 Klassen → Task 4. ✅
- §6 Ableitung (Backend direkt) → Task 5 (_PARSER_MAP), Task 6 (GUELTIGE_DOK_TYPEN); (FE + generierte YAMLs) → Task 7. ✅
- §6 Guard-Test → Task 7 Step 1/6. ✅
- §6 Reconciliation `reparaturrechnung` netto → Task 4 (schadenposition) + Task 7 Step 4 (Prüfhinweis). ✅
- §7 Plan 1 Schritte 1-6 → Tasks 1-8. ✅
- §9 sv_rechnung-Sondermarker → Task 2 (`_SV_VORSTEUER_MARKER`) + Task 3 (Wert). ✅
- **Plan 2 (Frist-/Verzugs-Automatik) ist bewusst NICHT hier** — eigener Plan nach Merge von Plan 1 (Spec §7 Plan 2).

**Platzhalter-Scan:** kein TBD/TODO; jeder Code-Step zeigt vollständigen Code. ✅

**Typ-Konsistenz:** `_PARSER_FUNKTIONEN` (Task 5) einheitlich benannt; `gueltige_dok_typen()` (Task 6) in word_service.py + word_routes.py konsistent; `render_alles()` (Task 7) in Skript + Guard-Test gleich. ✅

**Bekannte Grenzen:**
- `mahnschreiben`/`klagedrohung` haben in Plan 1 **keinen** Parser und **kein** `frist_datum`-Schema — das kommt in Plan 2. In Plan 1 sind sie wählbare Ablage-Etiketten mit `richtung: beides` (damit sie schon jetzt in `gueltige_dok_typen()` erscheinen).
- Marker der drei Personenschaden-Klassen sind bewusst schmal; Feinjustierung nach echtem Betrieb.
