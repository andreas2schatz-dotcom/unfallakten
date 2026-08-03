# Dokumentenklassen-SSOT (Plan 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die 5 heute getrennten Definitionen einer „Dokumentenklasse" auf die Klassen-Registry (`backend/registry/klassen/*.yaml`) als alleinige handgepflegte Quelle vereinheitlichen und die Klassenliste auf 22 Klassen vervollständigen.

**Architecture:** Jede Klasse trägt alle Attribute in ihrer YAML (`parser`, `richtung`, `ereignistyp`, `schadenposition`, `regex_felder` — zusätzlich zu `label`/`fristrelevanz`/…). Das Backend liest direkt aus der Registry (`_PARSER_MAP` und `GUELTIGE_DOK_TYPEN` werden abgeleitet). Das Frontend erhält eine **generierte** Datei (`dokumentenklassen.generated.js`) plus die generierten YAMLs `klasse_ereignistyp.yaml`/`rechnungstyp_mapping.yaml`; ein Guard-Test sichert gegen Drift.

**Tech Stack:** Python 3.9 (Backend, PyYAML), pytest, React/Vite (Frontend, ESM-Konstanten). Codegen + Guard laufen auf dem **Host** (Python 3.14 + PyYAML + pytest vorhanden), Backend-Tests im Container.

## Global Constraints

- **RA-MICRO read-only** — nur SQLite/Registry-Dateien ändern, nie in die RA-MICRO-DB schreiben.
- **Fail-Loud-Loader** — defekte/inkonsistente Registry ⇒ App startet nicht (RuntimeError + ERROR-Log). Keine stillen Fallbacks.
- **Python 3.9 kompatibel** im Backend — keine 3.10+-Syntax.
- **Konvention Dateiname == `klasse:`-Feld** — `<klasse>.yaml`, sonst RuntimeError.
- **Neue Felder sind optional** — die 8 Bestandsklassen müssen ohne Änderung weiter laden.
- **Kommentare nur bei nicht-offensichtlichem Verhalten** (CLAUDE.md).
- **Bekannte Parser-Schlüssel:** `rechnung`, `gutachten`, `abrechnungsschreiben`, `pruefbericht`. Medizinische/Ablage-/ausgehende Klassen haben **keinen** `parser` (Feldextraktion läuft rein über `regex_felder`).
- **Gültige Richtungen:** `eingehend` (Default), `ausgehend`, `beides`.
- **Mount-Realität:** Backend-Container hat NUR `backend/` + `tools/` (kein `frontend/`). Backend-Tests: `docker exec unfallakten-backend-dev python -m pytest <pfad> -v`. Codegen + Guard-Test: auf dem Host mit `py` (Windows-Launcher) aus dem Projektwurzelverzeichnis.
- **Finale Klassenliste (22):** sv_rechnung, rechnung, reparaturrechnung, mietwagenrechnung, abschlepprechnung, standkostenrechnung, gutachten, abrechnungsschreiben, pruefbericht, arztbericht, krankenhausbericht, attest, arbeitsunfaehigkeitsbescheinigung, nachbesichtigung, kaufvertrag, verdienstausfall_nachweis, mahnschreiben, klagedrohung, forderungsschreiben, sachstandsanfrage, klage, sonstiges.

---

### Task 1: Loader — optionale Felder format-validieren

**Files:**
- Modify: `backend/intake/registry_loader.py` (Modul-Konstanten + `_validiere_eintrag`)
- Test: `backend/tests/test_registry_loader.py`

**Interfaces:**
- Consumes: bestehende `lade_registry(pfad)` / `_validiere_eintrag(dateiname, data, vorhandene_klassen)`.
- Produces: `BEKANNTE_PARSER: set[str]`, `RICHTUNGEN: set[str]`. `_validiere_eintrag` wirft RuntimeError bei ungültigem `parser`/`richtung`/`ereignistyp`/`schadenposition`-Format.

- [ ] **Step 1: Failing tests schreiben**

In `backend/tests/test_registry_loader.py` ergänzen:

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
Expected: FAIL (`test_unbekannter_parser_wirft` bekommt keinen RuntimeError).

- [ ] **Step 3: Loader erweitern**

In `backend/intake/registry_loader.py` nach `PFLICHT_FELDER`:

```python
BEKANNTE_PARSER = {"rechnung", "gutachten", "abrechnungsschreiben", "pruefbericht"}
RICHTUNGEN = {"eingehend", "ausgehend", "beides"}
```

In `_validiere_eintrag(...)` nach dem `bezeichnung_felder`-Block anhängen:

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
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/intake/registry_loader.py backend/tests/test_registry_loader.py
git commit -m "feat(registry): optionale Klassen-Felder parser/richtung/ereignistyp/schadenposition validieren"
```

---

### Task 2: Startup — Kreuzvalidierung gegen Positionsmodell-Registry

**Files:**
- Modify: `backend/intake/registry_loader.py` (neue Funktion `validiere_gegen_positionsmodell`)
- Modify: `backend/app.py:137-138`
- Test: `backend/tests/test_registry_loader.py`

**Interfaces:**
- Consumes: `Registry`, `PositionsmodellRegistry`. Sondermarker `__sv_kosten_vorsteuer__`.
- Produces: `validiere_gegen_positionsmodell(klassen_reg, pos_reg) -> None` — RuntimeError bei ungültigem `ereignistyp`/`schadenposition`.

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
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Funktion implementieren**

In `backend/intake/registry_loader.py` unten:

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

In `backend/app.py` direkt nach den bestehenden Zeilen 137-138 (`_reg = lade_registry(...)`) anfügen:

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
- Consumes: heutige Werte aus `_PARSER_MAP`, `klasse_ereignistyp.yaml`, `rechnungstyp_mapping.yaml`.
- Produces: jede Bestandsklasse trägt `parser`/`richtung`/`ereignistyp`/`schadenposition`; `sv_rechnung` bekommt Label „SV-/Gutachterrechnung".

Zielwerte:

| Klasse | parser | richtung | ereignistyp | schadenposition | label |
|---|---|---|---|---|---|
| abrechnungsschreiben | abrechnungsschreiben | eingehend | abrechnung_eingegangen | — | (unverändert) |
| pruefbericht | pruefbericht | eingehend | pruefbericht_eingegangen | — | (unverändert) |
| gutachten | gutachten | eingehend | gutachten_eingegangen | — | (unverändert) |
| sv_rechnung | rechnung | eingehend | rechnung_eingegangen | `__sv_kosten_vorsteuer__` | **SV-/Gutachterrechnung** |
| rechnung | rechnung | eingehend | rechnung_eingegangen | — | Rechnung (Auffang) |
| abschlepprechnung | rechnung | eingehend | rechnung_eingegangen | abschleppkosten | (unverändert) |
| standkostenrechnung | rechnung | eingehend | rechnung_eingegangen | standkosten | (unverändert) |
| sonstiges | — | eingehend | — | — | (unverändert) |

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


def test_sv_rechnung_label_umbenannt():
    reg = lade_registry(standard_pfad(), reload=True)
    assert reg.klassen["sv_rechnung"]["label"] == "SV-/Gutachterrechnung"
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py -v`
Expected: FAIL (Felder fehlen).

- [ ] **Step 3: YAMLs ergänzen**

Jeweils am Dateiende die Felder anhängen (bei `sv_rechnung` zusätzlich die bestehende `label:`-Zeile auf `SV-/Gutachterrechnung` ändern):

`abschlepprechnung.yaml`:
```yaml
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: abschleppkosten
```

`standkostenrechnung.yaml`:
```yaml
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: standkosten
```

`sv_rechnung.yaml` (bestehende `label:`-Zeile ersetzen durch `label: SV-/Gutachterrechnung`, dann anhängen):
```yaml
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: __sv_kosten_vorsteuer__
```

`rechnung.yaml` (falls `label:` fehlt, `label: Rechnung (Auffang)` setzen, dann anhängen):
```yaml
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
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

`sonstiges.yaml`:
```yaml
richtung: eingehend
```

- [ ] **Step 4: Test + Loader-Regression laufen lassen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py backend/tests/test_registry_golden.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klassen/abrechnungsschreiben.yaml backend/registry/klassen/abschlepprechnung.yaml backend/registry/klassen/gutachten.yaml backend/registry/klassen/pruefbericht.yaml backend/registry/klassen/rechnung.yaml backend/registry/klassen/sonstiges.yaml backend/registry/klassen/standkostenrechnung.yaml backend/registry/klassen/sv_rechnung.yaml backend/tests/test_registry_felder.py
git commit -m "feat(registry): Bestandsklassen um Felder ergaenzt, sv_rechnung Label SV-/Gutachterrechnung"
```

---

### Task 4: Neue Nicht-medizinische Klassen (9 YAMLs)

**Files:**
- Create: `backend/registry/klassen/reparaturrechnung.yaml`, `mietwagenrechnung.yaml`, `kaufvertrag.yaml`, `verdienstausfall_nachweis.yaml`, `mahnschreiben.yaml`, `klagedrohung.yaml`, `forderungsschreiben.yaml`, `sachstandsanfrage.yaml`, `klage.yaml`
- Test: `backend/tests/test_registry_felder.py` (erweitern)

**Interfaces:**
- Consumes: `BEKANNTE_PARSER`, `ereignistypen.yaml`, `positionsarten.yaml`.
- Produces: die 9 Klassen laut Spec §5 (Rechnungen, Fristsetzung, ausgehende Schreiben, Ablage).

- [ ] **Step 1: Failing test schreiben**

In `backend/tests/test_registry_felder.py` anhängen:

```python
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py::test_neue_nichtmed_klassen -v`
Expected: FAIL (KeyError).

- [ ] **Step 3: Die 9 YAMLs anlegen**

`reparaturrechnung.yaml`:
```yaml
klasse: reparaturrechnung

marker:
  - Reparaturrechnung
  - Reparatur-Rechnung
  - Werkstattrechnung
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
label: Reparatur-/Werkstattrechnung
parser: rechnung
richtung: eingehend
ereignistyp: rechnung_eingegangen
schadenposition: rep_rechnung_netto
bezeichnung_felder:
  datum: rechnungsdatum
```

`mietwagenrechnung.yaml`:
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

`kaufvertrag.yaml`:
```yaml
klasse: kaufvertrag

marker:
  - Kaufvertrag
  - Fahrzeug-Kaufvertrag

regex_felder: {}

schema:
  datum: date
  aussteller: string

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Kaufvertrag
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

`verdienstausfall_nachweis.yaml`:
```yaml
klasse: verdienstausfall_nachweis

marker:
  - Verdienstausfall
  - Lohnbescheinigung
  - Gehaltsnachweis

regex_felder: {}

schema:
  datum: date
  aussteller: string

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 10
label: Verdienstausfall-Nachweis
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

`mahnschreiben.yaml`:
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

`forderungsschreiben.yaml`:
```yaml
klasse: forderungsschreiben

marker: []

regex_felder: {}

schema:
  datum: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Forderungsschreiben
richtung: ausgehend
bezeichnung_felder:
  datum: datum
```

`sachstandsanfrage.yaml`:
```yaml
klasse: sachstandsanfrage

marker: []

regex_felder: {}

schema:
  datum: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Sachstandsanfrage
richtung: ausgehend
bezeichnung_felder:
  datum: datum
```

`klage.yaml`:
```yaml
klasse: klage

marker: []

regex_felder: {}

schema:
  datum: date

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Klage
richtung: ausgehend
bezeichnung_felder:
  datum: datum
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py backend/tests/test_registry_loader.py -v`
Expected: PASS (Kreuzvalidierung: alle `ereignistyp`/`schadenposition` gültig).

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klassen/reparaturrechnung.yaml backend/registry/klassen/mietwagenrechnung.yaml backend/registry/klassen/kaufvertrag.yaml backend/registry/klassen/verdienstausfall_nachweis.yaml backend/registry/klassen/mahnschreiben.yaml backend/registry/klassen/klagedrohung.yaml backend/registry/klassen/forderungsschreiben.yaml backend/registry/klassen/sachstandsanfrage.yaml backend/registry/klassen/klage.yaml backend/tests/test_registry_felder.py
git commit -m "feat(registry): Rechnungs-, Fristsetzungs-, ausgehende und Ablage-Klassen"
```

---

### Task 4b: Medizinische Klassen + Nachbesichtigung mit Extraktion (5 YAMLs)

**Files:**
- Create: `backend/registry/klassen/arztbericht.yaml`, `krankenhausbericht.yaml`, `attest.yaml`, `arbeitsunfaehigkeitsbescheinigung.yaml`, `nachbesichtigung.yaml`
- Test: `backend/tests/test_registry_felder.py` (erweitern)

**Interfaces:**
- Consumes: `regex_felder`/`schema`-Konventionen des Loaders; Intake-Pipeline (`extrahiere_felder`) nutzt die `regex_felder`.
- Produces: 4 medizinische Klassen (Extraktion Datum + ICD-10 + Diagnose-Freitext) + `nachbesichtigung` (Datum + Reparaturtage). Kein `parser`, kein `ereignistyp`, keine `schadenposition`.

- [ ] **Step 1: Failing test schreiben**

In `backend/tests/test_registry_felder.py` anhängen:

```python
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
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py::test_med_und_nachbesichtigung -v`
Expected: FAIL (KeyError).

- [ ] **Step 3: Die 5 YAMLs anlegen**

Gemeinsames medizinisches Muster — `arztbericht.yaml`:
```yaml
klasse: arztbericht

marker:
  - Arztbericht
  - Befundbericht
  - Aerztlicher Bericht

regex_felder:
  datum:
    - "(?:vom|Datum|ausgestellt am)[:\\s]+(\\d{2}\\.\\d{2}\\.\\d{4})"
    - "(\\d{2}\\.\\d{2}\\.\\d{4})"
  diagnoseschluessel:
    - "ICD[- ]?10[- ]?(?:GM)?[:\\s]*([A-Z]\\d{2}(?:\\.\\d{1,2})?)"
    - "\\b([A-Z]\\d{2}\\.\\d{1,2})\\b"
  diagnose:
    - "Diagnose[n]?[:\\s]+([^\\r\\n]+)"

schema:
  aussteller: string
  datum: date
  diagnoseschluessel: string
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

`krankenhausbericht.yaml` (gleiche `regex_felder`/`schema`/`bezeichnung_felder` wie `arztbericht`, nur Kopf abweichend):
```yaml
klasse: krankenhausbericht

marker:
  - Entlassungsbericht
  - Krankenhausbericht
  - Klinikbericht
  - stationaere Behandlung

regex_felder:
  datum:
    - "(?:vom|Datum|ausgestellt am)[:\\s]+(\\d{2}\\.\\d{2}\\.\\d{4})"
    - "(\\d{2}\\.\\d{2}\\.\\d{4})"
  diagnoseschluessel:
    - "ICD[- ]?10[- ]?(?:GM)?[:\\s]*([A-Z]\\d{2}(?:\\.\\d{1,2})?)"
    - "\\b([A-Z]\\d{2}\\.\\d{1,2})\\b"
  diagnose:
    - "Diagnose[n]?[:\\s]+([^\\r\\n]+)"

schema:
  aussteller: string
  datum: date
  diagnoseschluessel: string
  diagnose: string

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
  - Attest
  - aerztliches Attest

regex_felder:
  datum:
    - "(?:vom|Datum|ausgestellt am)[:\\s]+(\\d{2}\\.\\d{2}\\.\\d{4})"
    - "(\\d{2}\\.\\d{2}\\.\\d{4})"
  diagnoseschluessel:
    - "ICD[- ]?10[- ]?(?:GM)?[:\\s]*([A-Z]\\d{2}(?:\\.\\d{1,2})?)"
    - "\\b([A-Z]\\d{2}\\.\\d{1,2})\\b"
  diagnose:
    - "Diagnose[n]?[:\\s]+([^\\r\\n]+)"

schema:
  aussteller: string
  datum: date
  diagnoseschluessel: string
  diagnose: string

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 10
label: Attest
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

`arbeitsunfaehigkeitsbescheinigung.yaml`:
```yaml
klasse: arbeitsunfaehigkeitsbescheinigung

marker:
  - Arbeitsunfaehigkeitsbescheinigung
  - AU-Bescheinigung
  - arbeitsunfaehig

regex_felder:
  datum:
    - "(?:vom|Datum|ausgestellt am)[:\\s]+(\\d{2}\\.\\d{2}\\.\\d{4})"
    - "(\\d{2}\\.\\d{2}\\.\\d{4})"
  diagnoseschluessel:
    - "ICD[- ]?10[- ]?(?:GM)?[:\\s]*([A-Z]\\d{2}(?:\\.\\d{1,2})?)"
    - "\\b([A-Z]\\d{2}\\.\\d{1,2})\\b"
  diagnose:
    - "Diagnose[n]?[:\\s]+([^\\r\\n]+)"

schema:
  aussteller: string
  datum: date
  diagnoseschluessel: string
  diagnose: string

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 10
label: Arbeitsunfaehigkeitsbescheinigung (AU)
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

`nachbesichtigung.yaml`:
```yaml
klasse: nachbesichtigung

marker:
  - Nachbesichtigung
  - Nachbesichtigungsbericht

regex_felder:
  datum:
    - "Nachbesichtigung[^0-9]{0,30}(\\d{2}\\.\\d{2}\\.\\d{4})"
    - "(?:vom|am)\\s+(\\d{2}\\.\\d{2}\\.\\d{4})"
  reparaturtage:
    - "Reparaturdauer[^0-9]{0,20}(\\d{1,3})"
    - "Reparaturzeit[^0-9]{0,20}(\\d{1,3})"
    - "(\\d{1,3})\\s*(?:Arbeits)?tage?\\s+Reparatur"

schema:
  datum: date
  reparaturtage: integer

pflichtfelder: []
kritische_felder: []
validierungsregeln: []
fristrelevanz: false
loeschfrist_jahre: 6
label: Nachbesichtigung
richtung: eingehend
bezeichnung_felder:
  datum: datum
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_registry_felder.py backend/tests/test_registry_loader.py -v`
Expected: PASS. Registry lädt jetzt 22 Klassen.

- [ ] **Step 5: Commit**

```bash
git add backend/registry/klassen/arztbericht.yaml backend/registry/klassen/krankenhausbericht.yaml backend/registry/klassen/attest.yaml backend/registry/klassen/arbeitsunfaehigkeitsbescheinigung.yaml backend/registry/klassen/nachbesichtigung.yaml backend/tests/test_registry_felder.py
git commit -m "feat(registry): medizinische Klassen (Datum/ICD-10/Diagnose) + nachbesichtigung (Datum/Reparaturtage)"
```

---

### Task 5: Dispatcher — `_PARSER_MAP` durch Registry-Lookup ersetzen

**Files:**
- Modify: `backend/workflow/dispatcher.py` (`_PARSER_MAP` → `_PARSER_FUNKTIONEN` + `_fuehre_parser_aus`)
- Test: `backend/tests/test_dispatcher_parser_routing.py` (neu)

**Interfaces:**
- Consumes: `lade_registry`/`standard_pfad`; die Parser-Wrapper `_parse_rechnung`/`_parse_gutachten`/`_parse_abrechnungsschreiben`/`_parse_pruefbericht`.
- Produces: `_fuehre_parser_aus(klasse, ...)` routet über das `parser`-Feld der Registry; Klasse ohne `parser` → None.

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

`_PARSER_MAP` (Zeilen 694-703) ersetzen:

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

- [ ] **Step 4: Tests + Dispatcher-Regression laufen lassen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_dispatcher_parser_routing.py backend/tests/ -k dispatch -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/workflow/dispatcher.py backend/tests/test_dispatcher_parser_routing.py
git commit -m "refactor(dispatcher): Parser-Routing aus Klassen-Registry statt hartkodiertem _PARSER_MAP"
```

---

### Task 6: `GUELTIGE_DOK_TYPEN` aus der Registry ableiten

**Files:**
- Modify: `backend/word/word_service.py:54-59` und Zeilen 108/111
- Modify: `backend/routers/word_routes.py:17,64`
- Test: `backend/tests/test_word_gueltige_typen.py` (neu)

**Interfaces:**
- Consumes: `lade_registry`/`standard_pfad`; `richtung`-Feld.
- Produces: `gueltige_dok_typen() -> set[str]` = reine Word-Typen ∪ Registry-Klassen mit `richtung` ∈ {ausgehend, beides}.

- [ ] **Step 1: Failing test schreiben**

`backend/tests/test_word_gueltige_typen.py`:

```python
from backend.word import word_service


def test_ausgehende_klassen_sind_gueltige_word_typen():
    g = word_service.gueltige_dok_typen()
    for t in ("forderungsschreiben", "sachstandsanfrage", "klage",
              "mahnschreiben", "klagedrohung"):
        assert t in g, t


def test_reiner_word_typ_bleibt():
    assert "abrechnungsuebersicht" in word_service.gueltige_dok_typen()
```

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/test_word_gueltige_typen.py -v`
Expected: FAIL (`gueltige_dok_typen` existiert nicht).

- [ ] **Step 3: word_service.py umbauen**

`GUELTIGE_DOK_TYPEN`-Set (Zeilen 54-59) ersetzen:

```python
# Word-Typen ohne eigene Registry-Klasse (rein ausgehende Vorlagen)
_REINE_WORD_TYPEN = {"abrechnungsuebersicht"}


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

Prüfung in `generiere_und_speichere` (Zeile 108):

```python
    if dok_typ not in gueltige_dok_typen():
```

Fehlermeldung (Zeile 111): `sorted(gueltige_dok_typen())` statt `sorted(GUELTIGE_DOK_TYPEN)`.

In `backend/routers/word_routes.py`: Import (Zeile 17) `GUELTIGE_DOK_TYPEN` entfernen, `gueltige_dok_typen` importieren; Verwendung (Zeile 64) auf `gueltige_dok_typen()` umstellen.

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
- Modify: `backend/registry/klasse_ereignistyp.yaml`, `backend/registry/rechnungstyp_mapping.yaml` (generiert)
- Modify: `frontend/src/config/constants.js` (Re-Export statt Hardcode)
- Test: `backend/tests/test_gen_dokumentenklassen_guard.py` (neu)

**Interfaces:**
- Consumes: `lade_registry`; `label`/`richtung`/`ereignistyp`/`schadenposition`.
- Produces: `render_alles() -> dict[str, str]` (rel. Pfad → Inhalt) und `main()`. Generiert `DOK_TYPEN`, `KLASSE_TO_POS`, `klasse_ereignistyp`, `rechnungstyp_mapping`.

- [ ] **Step 1: Failing Guard-Test schreiben**

`backend/tests/test_gen_dokumentenklassen_guard.py`:

```python
import os
import sys

PROJEKT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJEKT)

import pytest
from tools.gen_dokumentenklassen import render_alles

FRONTEND = os.path.join(PROJEKT, "frontend")
pytestmark = pytest.mark.skipif(
    not os.path.isdir(FRONTEND),
    reason="frontend/ nicht vorhanden (Backend-Container) — Guard laeuft auf Host/CI",
)


def test_generate_ist_aktuell():
    for rel_pfad, soll in render_alles().items():
        voll = os.path.join(PROJEKT, rel_pfad)
        with open(voll, "r", encoding="utf-8") as f:
            ist = f.read()
        assert ist == soll, (
            f"{rel_pfad} ist veraltet — 'py tools/gen_dokumentenklassen.py' "
            "ausfuehren und committen."
        )
```

- [ ] **Step 2: Test laufen lassen (Host) — muss fehlschlagen**

Run: `py -m pytest backend/tests/test_gen_dokumentenklassen_guard.py -v`
Expected: FAIL (`ModuleNotFoundError: tools.gen_dokumentenklassen`).

- [ ] **Step 3: Codegen-Skript schreiben**

`tools/gen_dokumentenklassen.py`:

```python
"""Generiert aus der Klassen-Registry (SSOT) die abgeleiteten Artefakte:
  * frontend/src/config/dokumentenklassen.generated.js  (DOK_TYPEN, KLASSE_TO_POS)
  * backend/registry/klasse_ereignistyp.yaml            (Klasse -> Ereignistyp)
  * backend/registry/rechnungstyp_mapping.yaml          (Klasse -> position_key)

Aufruf (Host, Projektwurzel):  py tools/gen_dokumentenklassen.py
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

- [ ] **Step 4: Skript ausführen (Host, Artefakte erzeugen)**

Run: `py tools/gen_dokumentenklassen.py`
Expected: drei „geschrieben:"-Zeilen. `git diff` prüfen: `klasse_ereignistyp.yaml`/`rechnungstyp_mapping.yaml` enthalten jetzt auch die neuen Klassen (und keine `werkstattrechnung` mehr); `dokumentenklassen.generated.js` ist neu und listet alle 22 Klassen.

**Reconciliation prüfen:** In `dokumentenklassen.generated.js` steht `"reparaturrechnung": ["rep_rechnung_netto"]` (nicht `_brutto`).

- [ ] **Step 5: constants.js auf Re-Export umstellen**

In `frontend/src/config/constants.js`:
- Hardcode `DOK_TYPEN` (Zeile 191) und `KLASSE_TO_POS` (Zeilen 514-521) **entfernen**.
- Oben ergänzen: `import { DOK_TYPEN, KLASSE_TO_POS } from "./dokumentenklassen.generated.js";`
- Im `export { ... }`-Block bleiben `DOK_TYPEN` und `KLASSE_TO_POS` gelistet (öffentliche API identisch → `DokumenteSection.jsx` unverändert).

- [ ] **Step 6: Guard-Test (Host) + Frontend-Build**

Run: `py -m pytest backend/tests/test_gen_dokumentenklassen_guard.py -v`
Expected: PASS.

Run: `cd frontend && npm run build`
Expected: Build erfolgreich.

- [ ] **Step 7: Commit**

```bash
git add tools/gen_dokumentenklassen.py frontend/src/config/dokumentenklassen.generated.js frontend/src/config/constants.js backend/registry/klasse_ereignistyp.yaml backend/registry/rechnungstyp_mapping.yaml backend/tests/test_gen_dokumentenklassen_guard.py
git commit -m "feat(klassen): FE-Liste + Mapping-YAMLs aus Registry generieren, Guard-Test gegen Drift"
```

---

### Task 8: Gesamt-Regression + Browser-Nachtest

**Files:** keine Änderung — Verifikation.

- [ ] **Step 1: Volle Backend-Testsuite (Container)**

Run: `docker exec unfallakten-backend-dev python -m pytest backend/tests/ -q`
Expected: PASS. Der Guard-Test `test_gen_dokumentenklassen_guard` wird hier mit Grund **übersprungen** (frontend/ nicht im Container) — das ist erwartet.

- [ ] **Step 2: Guard-Test explizit auf Host**

Run: `py -m pytest backend/tests/test_gen_dokumentenklassen_guard.py -v`
Expected: PASS (läuft hier wirklich, weil frontend/ vorhanden).

- [ ] **Step 3: App-Start prüfen (Fail-Loud-Kreuzvalidierung)**

Run: `docker restart unfallakten-backend-dev && docker logs --tail 40 unfallakten-backend-dev`
Expected: „Registry geladen: 22 Klassen …", kein RuntimeError.

- [ ] **Step 4: Browser-Nachtest**

Im Dokumente-Reiter einer Testakte das Klassen-Dropdown öffnen: alle 22 Klassen erscheinen mit ihren Labels (u. a. „SV-/Gutachterrechnung", „Reparatur-/Werkstattrechnung", „Arbeitsunfaehigkeitsbescheinigung (AU)"). Eine Reparaturrechnung hochladen/zuordnen → Position „Reparaturkosten (Rechnung, netto)". Ergebnis notieren.

- [ ] **Step 5: Abschluss-Commit (Notizen, optional)**

```bash
git commit --allow-empty -m "test(klassen): Gesamt-Regression + Browser-Nachtest Plan 1 gruen"
```

---

## Self-Review

**Spec-Abdeckung:**
- §4 Schema-Erweiterung → Task 1 (Format) + Task 2 (Kreuzvalidierung). ✅
- §5 finale 22 Klassen → Task 3 (Bestand + sv_rechnung-Label), Task 4 (9 nicht-med.), Task 4b (5 med./nachbesichtigung). ✅
- §5 Rechnungen/ausgehend/Ablage/Fristsetzung → Task 4. ✅
- §5 medizinische Extraktion (Datum/ICD-10/Diagnose) + nachbesichtigung (Datum/Reparaturtage) → Task 4b `regex_felder`+`schema`. ✅
- §5 Zusammenführungen (gutachterrechnung→sv_rechnung-Label, werkstattrechnung→reparaturrechnung-Label, haushalt_attest→attest) → Task 3 (Label) + Task 4 (reparaturrechnung-Label) + Task 4b (attest). ✅
- §6 Backend-Ableitung → Task 5 (_PARSER_MAP), Task 6 (GUELTIGE_DOK_TYPEN); FE + generierte YAMLs → Task 7. ✅
- §6 Guard-Test → Task 7 Step 1/6, Task 8 Step 2. ✅
- §6 Reconciliation reparaturrechnung netto → Task 4 (schadenposition) + Task 7 Step 4. ✅
- §9 sv_rechnung-Sondermarker → Task 2 + Task 3. ✅
- §9 GUELTIGE reine Word-Typen = nur abrechnungsuebersicht → Task 6 `_REINE_WORD_TYPEN`. ✅
- **Plan 2 (Frist-/Verzugs-Automatik) bewusst NICHT hier** — eigener Plan nach Merge (Spec §7).

**Platzhalter-Scan:** kein TBD/TODO; jeder Code-Step zeigt vollständigen Code. ✅

**Typ-Konsistenz:** `_PARSER_FUNKTIONEN` (Task 5), `gueltige_dok_typen()` (Task 6, word_service + word_routes), `render_alles()` (Task 7, Skript + Guard) durchgängig gleich benannt. ✅

**Bekannte Grenzen / Umgebungs-Realität:**
- Codegen + Guard-Test laufen auf dem **Host** (`py`), weil `frontend/` nicht im Backend-Container gemountet ist. Im Container-Vollsuite-Lauf (Task 8 Step 1) wird der Guard mit Grund übersprungen; Task 8 Step 2 führt ihn auf dem Host wirklich aus.
- `mahnschreiben`/`klagedrohung` haben in Plan 1 **keinen** Parser und **kein** `frist_datum`-Schema — das kommt in Plan 2. In Plan 1 sind sie wählbare fristrelevante Klassen mit `richtung: beides`.
- Medizinische `regex_felder` erfassen den **primären** ICD-10-Code (erster Treffer) + Freitext; Mehrfachcodes sind Folgeschritt.
- `werkstattrechnung` verschwindet als eigenes Label (→ `reparaturrechnung`); `nachbesichtigung`-Rechnungen laufen als `sv_rechnung`.
