# PRD-33 Session 6 — Politur + Regressionsschutz (KW-30–40 + V10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Letzte PRD-33-Session — Textqualität/Kleinkram im Klage-Renderer fixen (KW-30/31/32/33/34/37), Positions-Key-Vertrag sichern (KW-38), toten Code entfernen (KW-40), Rundungs-Parität dokumentiert abschließen (KW-36 großteils entfällt) und die V10-Render-Matrix als dauerhaften Regressionsschutz einziehen.

**Architecture:** Alle Backend-Änderungen in `backend/word/klage_service.py` (1951 Zeilen, Zeilenangaben = Stand HEAD `c003e962`), getestet im etablierten DOCX-Direkttest-Muster (`backend/tests/test_klage_service_docx.py`: echtes `generiere_klageschrift()` + zipfile + String-Asserts auf `word/document.xml`). Frontend-Änderungen in `KlageSection.jsx`/`KlageWizard.jsx` + neue geteilte Key-Map `frontend/src/config/klagePositionKeys.js`. V10 = neue Matrix-Testklasse im selben DOCX-Muster.

**Tech Stack:** Python/Flask (unittest, kein Mock im DOCX-Pfad), React (Vitest + Testing Library), python-docx-frei (rohes OOXML-Templating mit zipfile).

## Global Constraints

- **TDD strikt:** RED muss VERHALTENS-Rot sein (Export-only-Zwischenschritt); Import-/Referenzfehler zählt NICHT als RED. Falscher Fund → `entfällt` mit Begründung im Report.
- **RA-MICRO read-only.** Keine Migration in dieser Session.
- **Baseline:** Backend voller Lauf 204f/1059p/18s (204f = Alt-Cluster test_modul1–7, test_dashboard_uebersicht, test_sv_portal, test_prd27, test_modul6, test_migration_46; ±2 Test-Order-Rauschen im Auth-Cluster möglich — bei Abweichung Datei-Ebene vergleichen). **Null neue Failures.** Frontend 200 Vitest + Build grün.
- **Tests auf dem Host:** Backend `python -m pytest …` aus dem Projektroot; Frontend `npx vitest run …` und `npm run build` aus `frontend/`. Tests NIE `run_in_background`, immer Vordergrund, Timeout bis 600000 ms.
- **Git-Guardrail:** Repo-Root = HOME (`C:\Users\HAL9000`) → NIE `git add -A`/`git add .`, nur explizite Pfade. Branch `klage-wizard-fixes-s6`.
- **KW-24-Vertrag:** `ANTRAEGE_PLACEHOLDER` bleibt DAUERHAFT in `wizardAntraegeText`; `komponiereAntraege(antraegeText, gebuehrenText)` ersetzt nur beim Senden/Anzeigen. NIE wieder einbrennen.
- **V7-Vertrag:** Neue textrelevante Eingaben für den Anträge-Text MÜSSEN in `antraegeBasis` aufgenommen werden (diese Session plant KEINE neuen Anträge-Eingaben — falls doch, Basis erweitern).
- **Forderungsschreiben-Pfad** (`get_aktivlegitimation_text`, `word_service`, `forderungsschreiben_wv.py`) bleibt byte-gleich, sofern eine Task nichts anderes sagt.
- Bestehende Pin-Tests dürfen NUR angepasst werden, wenn die Task die Verhaltensänderung explizit anordnet (dann im Report begründen).
- Keine Kommentare im Code außer bei nicht-offensichtlichem Verhalten (CLAUDE.md).

---

### Task 1: KW-33 + KW-37 — SG-BEWEIS via `_beweis()` + RVG-Faktor mit Komma

**Files:**
- Modify: `backend/word/klage_service.py:1766` (KW-33), `:1823` (KW-37)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse `TestKw33SgBeweis`, `TestKw37FaktorKomma`)

**Interfaces:**
- Consumes: `_beweis(inhalt)` (`klage_service.py:677-689`), `baue_sg_abschnitt` liefert `sg_beweis`-String (beginnt mit „BEWEIS:…“? — Implementer prüft: falls der String selbst mit „BEWEIS:“ beginnt, Präfix vor Übergabe an `_beweis` abschneiden, sonst doppelt).
- Produces: SG-Abschnitt rendert den Beweisantritt als `_beweis()`-Absatz (fettes „BEWEIS:“ + `<w:tab/>`); RVG-Tabellenzeile zeigt „(1,3)“ mit Komma.

- [ ] **Step 1: Failing Tests schreiben**

```python
class TestKw33SgBeweis(unittest.TestCase):
    def test_sg_beweis_als_beweis_absatz_formatiert(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)],
                           mit_schmerzensgeld=True, schmerzensgeld_mindest=2000.0)
        # personenschaden so befüllen, dass baue_sg_abschnitt einen sg_beweis liefert
        # (Implementer: vorhandene SG-Fixtures in der Datei wiederverwenden)
        xml = _document_xml(generiere_klageschrift(akte))
        sg_idx = xml.index("Schmerzensgeld")
        # BEWEIS-Runs des _beweis()-Helpers: fettes "BEWEIS:" + <w:tab/>
        self.assertIn('<w:t xml:space="preserve">BEWEIS:</w:t>', xml[sg_idx:])

class TestKw37FaktorKomma(unittest.TestCase):
    def test_rvg_faktor_mit_komma(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("Nr. 2300 VV RVG (1,3):", xml)
        self.assertNotIn("Nr. 2300 VV RVG (1.3):", xml)
```

- [ ] **Step 2: RED verifizieren** — `python -m pytest backend/tests/test_klage_service_docx.py -k "Kw33 or Kw37" -v` → beide FAIL aus Verhaltensgrund (heute: SG-BEWEIS als `_p(einzug=True)`-Absatz ohne fettes BEWEIS-Run; Faktor „(1.3)“). KW-33-RED ggf. präzisieren: heute darf `BEWEIS:` als reiner Text im SG-Bereich stehen, aber NICHT im `_beweis()`-Format (Tab-Run) — Assert entsprechend schärfen.

- [ ] **Step 3: Fix**

```python
# klage_service.py:1766 — statt: sg_xml += _p(sg_beweis, einzug=True)
if sg_beweis:
    inhalt = re.sub(r"^BEWEIS:\s*", "", sg_beweis)
    sg_xml += _beweis(inhalt)

# klage_service.py:1823 — Faktor mit Komma:
f"Geschäftsgebühr §§ 13, 14, Nr. 2300 VV RVG ({str(rvg_fuer_tab.get('faktor', 1.3)).replace('.', ',')}):"
```

- [ ] **Step 4: GREEN + Regressionsfläche** — `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py -v` (Timeout 600000, Vordergrund). Erwartung: alle grün; bestehende SG-Pins nur anpassen, wenn sie exakt das alte `_p`-Format pinnen (im Report begründen).

- [ ] **Step 5: Commit** — `git add "Documents/Projekt/Version 1.00/unfallakten/backend/word/klage_service.py" "Documents/Projekt/Version 1.00/unfallakten/backend/tests/test_klage_service_docx.py" && git commit -m "fix(klage): KW-33 SG-Beweis als BEWEIS-Absatz, KW-37 RVG-Faktor mit Komma"`

---

### Task 2: KW-30 (Backend) — Bedingte Segmente bei leerem Unfallort/-datum

**Files:**
- Modify: `backend/word/klage_service.py:1421-1435` (Einleitung), `:1371-1387` (Feststellungsanträge)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse `TestKw30LeereFelder`)

**Interfaces:**
- Consumes: `unfalltag` (`:1011-1014`, leer wenn kein Datum), `unfallort` (`:1016-1019`, leer wenn kein Ort), `mit_feststellung_sg/sach`-Flags im Auto-Antrags-Pfad.
- Produces: Kein Satzfragment mit doppeltem Leerzeichen/„vom  “/„in  geltend“ mehr; Segmente „ vom {unfalltag}“ und „ in {unfallort}“ erscheinen nur, wenn der Wert gesetzt ist.

- [ ] **Step 1: Failing Tests**

```python
class TestKw30LeereFelder(unittest.TestCase):
    def _akte_ohne_ort(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["akte"]["unfallort"] = ""
        return akte

    def test_einleitung_ohne_ort_kein_in_fragment(self):
        xml = _document_xml(generiere_klageschrift(self._akte_ohne_ort()))
        self.assertNotIn("in  geltend", xml)
        self.assertIn("Verkehrsunfall vom", xml)   # Datum-Segment bleibt

    def test_einleitung_ohne_ort_und_datum(self):
        akte = self._akte_ohne_ort()
        akte["akte"]["unfalldatum"] = ""
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("aus einem Verkehrsunfall geltend", xml)

    def test_feststellung_ohne_datum_kein_vom_fragment(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["akte"]["unfalldatum"] = ""
        akte["klage_config"]["mit_feststellung_sach"] = True
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertNotIn("Unfallereignis vom  noch", xml)
        self.assertIn("aus dem Unfallereignis noch entstehen", xml)
```

(Implementer: `_akte_daten`-Fixture prüfen — `unfalldatum`/`unfallort` ggf. via WDM-Feldern `_wdm_u_tag`/`_wdm_u_ort` leeren; maßgeblich ist der Pfad `klage_service.py:1011-1019`.)

- [ ] **Step 2: RED verifizieren** — Tests FAIL mit heutigem Fragment („in  geltend“ bzw. „vom  noch“).

- [ ] **Step 3: Fix — bedingte Segmente**

```python
# :1421ff — Segmente zusammensetzen statt drei fester f-Strings:
unfall_seg = ""
if unfalltag:
    unfall_seg += f" vom {unfalltag}"
if unfallort:
    unfall_seg += f" in {unfallort}"
# in allen Zweigen: f"…aus einem Verkehrsunfall{unfall_seg} geltend."
# Wichtig: bestehende Zweig-Logik (mehrere_klaeger/nicht_vst) erhalten — nur das Ort/Datum-Segment vereinheitlichen.

# :1371-1387 — Feststellungsanträge:
ereignis_seg = f" vom {unfalltag}" if unfalltag else ""
# f"…aus dem Unfallereignis{ereignis_seg} noch entstehen…"
```

- [ ] **Step 4: GREEN + Pin-Schutz** — voller Lauf `test_klage_service_docx.py`: Standardfall (Datum+Ort gesetzt) muss byte-gleich bleiben („Verkehrsunfall vom X in Y geltend.“) — bestehende Einleitungs-Pins (KW-05/06/17) dürfen NICHT brechen.

- [ ] **Step 5: Commit** — `git commit -m "fix(klage): KW-30 bedingte Segmente bei leerem Unfallort/-datum"` (explizite Pfade wie Task 1).

---

### Task 3: KW-31 — `sachverhalt_override` zeilenweise verarbeiten

**Files:**
- Modify: `backend/word/klage_service.py:785-811` (`_sachverhalt_override_xml`)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse `TestKw31OverrideAbsaetze`)

**Interfaces:**
- Consumes: `_p()`, `_beweis()`; Aufrufstelle `:1415` unverändert.
- Produces: Neue Semantik: Text wird ZEILENWEISE verarbeitet; Leerzeile beendet den aktuellen Absatz; eine Zeile, die mit `BEWEIS:` beginnt (Tab oder Space danach), wird IMMER als `_beweis()`-Absatz gerendert — auch nach einfachem `\n`. Aufeinanderfolgende Nicht-BEWEIS-Zeilen ohne Leerzeile bleiben EIN Absatz (Join mit Leerzeichen, wie bisher).

- [ ] **Step 1: Failing Tests**

```python
class TestKw31OverrideAbsaetze(unittest.TestCase):
    def _xml_fuer(self, override):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["unfalldetails"]["sachverhalt_override"] = override
        return _document_xml(generiere_klageschrift(akte))

    def test_beweis_nach_einfachem_umbruch_wird_beweis_absatz(self):
        xml = self._xml_fuer("Der Kläger ist Eigentümer.\nBEWEIS: Zeugnis des Herrn Meier")
        self.assertIn('BEWEIS:</w:t>', xml)                      # _beweis()-Format
        self.assertNotIn("Eigentümer. BEWEIS:", xml)             # nicht als Fließtext verkettet

    def test_leerzeile_erzeugt_zwei_absaetze(self):
        xml = self._xml_fuer("Absatz eins.\n\nAbsatz zwei.")
        self.assertIn(">Absatz eins.<", xml)
        self.assertIn(">Absatz zwei.<", xml)
        self.assertNotIn("Absatz eins. Absatz zwei.", xml)

    def test_einfacher_umbruch_bleibt_ein_absatz(self):
        xml = self._xml_fuer("Zeile eins\nZeile zwei")
        self.assertIn("Zeile eins Zeile zwei", xml)
```

- [ ] **Step 2: RED** — Test 1 FAIL (BEWEIS mit `\n` landet heute im Fließtext).

- [ ] **Step 3: Fix — zeilenweiser Parser**

```python
def _sachverhalt_override_xml(text):
    xml, fliess_teile = "", []
    def _flush():
        nonlocal xml, fliess_teile
        if fliess_teile:
            xml += _p(" ".join(fliess_teile))
            fliess_teile = []
    for zeile in text.split("\n"):
        z = zeile.strip()
        if not z:
            _flush()
        elif z.startswith("BEWEIS:\t") or z.upper().startswith("BEWEIS: ") or z.upper() == "BEWEIS:":
            _flush()
            inhalt = z[z.index("\t")+1:].strip() if "\t" in z else z[len("BEWEIS:"):].strip()
            xml += _beweis(inhalt)
        else:
            fliess_teile.append(z)
    _flush()
    return xml
```

- [ ] **Step 4: GREEN + Regressionsfläche** — `test_klage_service_docx.py` komplett: bestehende Override-Tests (KW-05/25-Umfeld) müssen grün bleiben (alte `\n\n`-Semantik ist Teilmenge der neuen).

- [ ] **Step 5: Commit** — `git commit -m "fix(klage): KW-31 sachverhalt_override zeilenweise (Leerzeile=Absatz, BEWEIS je Zeile)"`

---

### Task 4: KW-32 — Laufender Abschnittszähler + Verzug-Überschrift (+ Mini-Task S4-M5)

**Files:**
- Modify: `backend/word/klage_service.py:1414-1864` (Abschnitts-Überschriften), `:1841` (`vk_nr`), Verzug-Block `:1770-1792`
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse `TestKw32Abschnittszaehler`)

**Interfaces:**
- Consumes: bestehende `_p(f"{n}.) …", fett=True)`-Überschriften (1–4 hart codiert, SG=5, `vk_nr = 5 + int(mit_sg)`); Verzug-Block ohne Überschrift.
- Produces: Ein laufender Zähler `abschnitt_nr` (Funktion `naechste_nr()` o.ä. lokal in `generiere_klageschrift`): Sachverhalt=1, Unfallhergang=2, Unfallschaden=3, Rechtliche Würdigung=4, dann **in Dokumentreihenfolge** Schmerzensgeld (nur wenn `mit_sg`), **Verzug (NEU: eigene Überschrift „N.) Verzug“, nur wenn der Verzug-Block Inhalt hat)**, Vorgerichtliche Rechtsanwaltsgebühren. `vk_nr`-Arithmetik entfällt; die VK-Referenz „Der Klageantrag zu {rvg_antrag_nr}“ bleibt unberührt.

- [ ] **Step 1: Failing Tests**

```python
class TestKw32Abschnittszaehler(unittest.TestCase):
    def test_verzug_hat_nummer_und_ueberschrift_ohne_sg(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["klage_config"]["verzugsdatum"] = "2026-05-04"
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("5.) Verzug", xml)
        self.assertIn("6.) Vorgerichtliche Rechtsanwaltsgebühren", xml)

    def test_nummern_mit_sg(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)],
                           mit_schmerzensgeld=True, schmerzensgeld_mindest=2000.0)
        akte["klage_config"]["verzugsdatum"] = "2026-05-04"
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("5.) Schmerzensgeld", xml)
        self.assertIn("6.) Verzug", xml)
        self.assertIn("7.) Vorgerichtliche Rechtsanwaltsgebühren", xml)
```

(Implementer: prüfen, wann der Verzug-Block leer ist — rendert `verzug_xml` auch ohne Verzugsdaten einen Default-Text? Wenn der Block leer bleibt, darf KEINE Überschrift erscheinen und der Zähler überspringt ihn. Testfall dafür ergänzen.)

- [ ] **Step 2: RED** — FAIL: heute existiert „5.) Verzug“ nicht; VK ist „5.)“ ohne SG.

- [ ] **Step 3: Fix** — lokalen Zähler einführen:

```python
_nr = 0
def _abschnitt(titel):
    nonlocal-frei via Liste oder itertools.count; einfachste Form:
# konkret:
abschnitt_nr = [0]
def _abschnitt_kopf(titel):
    abschnitt_nr[0] += 1
    return _p(f"{abschnitt_nr[0]}.) {titel}", fett=True)
```
Alle sieben Kopfstellen (1414/1418, 1517, 1646, 1709/1721, 1757, NEU Verzug, 1842) auf `_abschnitt_kopf(...)` umstellen — **in Dokumentreihenfolge aufrufen** (Reihenfolge der Blöcke im Template beachten: SCHMERZENSGELD vor VERZUG vor VORGERICHTLICHE_KOSTEN; die XML-Bausteine werden im Code aber nicht in Dokumentreihenfolge gebaut → Implementer muss die Kopf-Erzeugung ggf. an eine Stelle nach hinten ziehen oder die Baureihenfolge prüfen. Anträge/Rubrum sind nicht nummeriert und bleiben unberührt). `vk_nr`-Zeile `:1841` entfernen.

- [ ] **Step 4: Mini-Task S4-M5 (gleiche Stelle, vertagter Minor):** Im Verzug-BEWEIS nutzt das Backend bei fehlendem `verzug_schreiben_datum` das Eintrittsdatum als Fallback; das Frontend (`buildVerzugAutoText`) lässt den BEWEIS-Satz dann weg. Angleichen: BEWEIS-Zeile im Backend nur rendern, wenn `verzug_schreiben_datum` gesetzt (UI-unerreichbarer Zweig, Verhalten = FE). Ein Test: `verzugsdatum` gesetzt, `verzug_schreiben_datum` leer → kein „BEWEIS:“-Absatz im Verzug-Abschnitt.

- [ ] **Step 5: GREEN + Pin-Anpassung** — voller `test_klage_service_docx.py`-Lauf. Bestehende Pins auf „5.) Vorgerichtliche…“/„6.) Vorgerichtliche…“ (KW-10/KW-13-Tests) werden durch die neue Nummerierung legitim verschoben → anpassen und im Report je Test begründen.

- [ ] **Step 6: Commit** — `git commit -m "fix(klage): KW-32 laufender Abschnittszaehler, Verzug mit Nummer+Ueberschrift; S4-M5 BEWEIS-Fallback angeglichen"`

---

### Task 5: KW-34 — Kein RVG-Antrag/VK-Abschnitt über 0,00 € + Fall-B-Klammer-Randfall

**Files:**
- Modify: `backend/word/klage_service.py:1140-1149` (Betrag), `:1390-1394` (Auto-Antrag), `:1794-1864` (VK-Block), `:1654-1674` (Fall-B-Differenzsatz)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse `TestKw34RvgNull`)

**Interfaces:**
- Consumes: `rvg_antrag_betrag` (nach `max(0.0, …)`-Klemmung), `antraege_override`-Weiche, `fallb_aktiv`/`fallb_zahlungen`/`klagebetrag` (`:1108-1117`), `_zahlungen_anzeige` (`:1661`).
- Produces: (a) Bei `rvg_antrag_betrag <= 0` entfällt im **Auto-Pfad** der RVG-Antrag UND der komplette VK-Abschnitt (`vk_xml = ""` → `{{VORGERICHTLICHE_KOSTEN}}` leer; Abschnittszähler aus Task 4 überspringt ihn dann automatisch). Override-Pfad (`antraege_override`) bleibt unangetastet — Nutzertext ist Nutzertext. (b) Fall-B-Randfall: wenn `klagebetrag` auf 0 geklemmt wurde (`fallb_zahlungen > ersatzfaehig`), nennt der Differenz-Satz die ECHTE Zahlungssumme mit angepasster Formulierung statt der arithmetisch schöngerechneten.

- [ ] **Step 1: Failing Tests**

```python
class TestKw34RvgNull(unittest.TestCase):
    def test_kein_rvg_antrag_bei_null(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        akte["klage_config"]["rvg_ausserg"] = {"gesamt": 150.0, "faktor": 1.3, "streitwert": 1000.0}
        akte["klage_config"]["rvg_bereits_gezahlt"] = 500.0   # > gesamt → Betrag klemmt auf 0
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertNotIn("weitere 0,00", xml)
        self.assertNotIn("Vorgerichtliche Rechtsanwaltsgebühren", xml)

    def test_fall_b_zahlungen_ueber_quotiertem_anspruch(self):
        pos = [_position("fahrzeugschaden", "Fahrzeugschaden", 0.0, betrag_original=1000.0)]
        akte = _akte_daten(pos)
        akte["klage_config"]["haftungsquote"] = 50
        akte["klage_config"]["haftungsquote_typ"] = "eigen"
        # Zahlungen 1000 € > quotierter Anspruch 500 € → klagebetrag klemmt auf 0
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("1.000,00", xml)          # echte Zahlungssumme genannt
        self.assertNotIn("Zahlungen in Höhe von 500,00", xml)  # nicht mehr die geschönte Differenz
```

(Implementer: exakte cfg-Feldnamen aus den bestehenden KW-03/KW-13-Tests der Datei übernehmen — z.B. `test_g` bei `:435` nutzt genau diesen Klemm-Fall; dessen Assertions ggf. mit anpassen, im Report begründen.)

- [ ] **Step 2: RED** — FAIL: heute „weitere 0,00 €“ + VK-Block; Fall B zeigt `_zahlungen_anzeige = ersatzfaehig`.

- [ ] **Step 3: Fix**

```python
# (a) Auto-Antrag :1390 — nur wenn Betrag > 0:
if rvg_antrag_betrag > 0:
    antraege_xml += antrag(f"{bek_gram['verurteilt']}, an {kl_dat} weitere {_eur_str(rvg_antrag_betrag)} …")
# VK-Block :1842 — Guard um den gesamten vk_xml-Aufbau:
vk_xml = ""
if rvg_antrag_betrag > 0:
    vk_xml = _lz() + _abschnitt_kopf("Vorgerichtliche Rechtsanwaltsgebühren") + …

# (b) Fall-B-Satz :1654ff — Klemm-Zweig:
if fallb_aktiv and klagebetrag == 0.0 and fallb_zahlungen > _ersatzfaehig:
    # Formulierung: „…mithin {ersatzfaehig} ersatzfähig. Hierauf wurden bereits {fallb_zahlungen}
    #  gezahlt; der ersatzfähige Betrag ist damit vollständig ausgeglichen.“
else:
    # bestehender Satz unverändert
```
Wichtig: `fallb_zahlungen` ist bereits bei `:1112` berechnet — im Schaden-Abschnitt verfügbar machen (gleiche Variable, kein Re-Compute mit anderer Rundung).

- [ ] **Step 4: GREEN + Wechselwirkung Task 4** — `test_klage_service_docx.py` voll: Abschnittszähler darf bei entfallenem VK-Block keine Lücke lassen (Verzug bleibt dann letzter nummerierter Abschnitt).

- [ ] **Step 5: Commit** — `git commit -m "fix(klage): KW-34 kein RVG-Antrag/VK-Abschnitt ueber 0 EUR; Fall-B-Klammer nennt echte Zahlungen"`

---

### Task 6: KW-36 — Rest-Erhebung: `entfällt`-Nachweis + hq=0-Guard (FE)

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` (`buildRwVorschau` ~`:230-290`, ggf. `berechneKlagebetrag`-Kontext)
- Test: `frontend/src/sections/__tests__/…` (bestehende `KlageWizard.haftungsquote.test.jsx` erweitern)

**Interfaces:**
- Consumes: `pctStr` (`KlageWizard.jsx:188`), `round2` (`:197`), `buildRwVorschau`, `_pct_str` (`klage_service.py:265`).
- Produces: (a) Doku-Nachweis, dass die int-Truncation nicht mehr existiert (Grep-Beleg im Report → Tracking-Doc `entfällt`-Teilvermerk). (b) Rundungs-Helper-Angleich: **entfällt**, wenn der Implementer bestätigt, dass BE-`round(x,2)` (banker's) und FE-`Math.round` (half-up) an keiner Stelle denselben angezeigten Betrag doppelt berechnen (BE rechnet die DOCX-Beträge, FE nur Vorschau derselben Eingaben — 1-Cent-Divergenz wäre nur Vorschau≠DOCX bei .xx5-Grenzwerten). Falls doch eine Stelle beide Werte im SELBEN Dokument nennt → BE-Helfer `_round2_half_up` NUR im Fall-B-Pfad einführen (halbe Cents wie FE). (c) hq=0-Guard: `typ==="eigen" && hq<=0` wird in der RW-Vorschau wie „keine eigene Quote“ behandelt (kein „…anrechnen“-Baustein).
- **Explizit KEIN Scope:** flächige Umstellung der BE-Rundung (Baseline-Risiko).

- [ ] **Step 1: Failing Test (nur Guard)**

```jsx
test("hq=0 mit typ eigen erzeugt keinen Anrechnungs-Baustein", () => {
  const text = buildRwVorschau({ ...basisOpts, hq: 0, hqTyp: "eigen" });
  expect(text).not.toMatch(/anrechnen|Mithaftungsquote von 0/);
});
```

- [ ] **Step 2: RED verifizieren** — `npx vitest run src/sections/__tests__/KlageWizard.haftungsquote.test.jsx` (aus `frontend/`). Falls der Test GRÜN ist, weil `buildRwVorschau` hq=0 bereits sauber behandelt → dieser Teilpunkt `entfällt` mit Beleg (Testcode als Regressions-Pin trotzdem committen).

- [ ] **Step 3: Fix (Ein-Zeilen-Guard)** — in `buildRwVorschau` (und falls nötig `berechneSwAussergEffektiv`): eigene-Quote-Zweig nur bei `hq > 0 && hq < 100` betreten (Parität zum BE-`fallb_aktiv`-Prädikat `0 < hq < 100`).

- [ ] **Step 4: Rundungs-Erhebung (kein Code by default):** Implementer prüft mit konkretem Grenzwert (z.B. Position 33,335 € × hq 50) ob FE-Vorschau und BE-DOCX divergieren können; Ergebnis in den Report. Nur bei nachgewiesener Divergenz im selben Dokument → minimaler BE-Helfer (siehe Interfaces).

- [ ] **Step 5: GREEN + Commit** — `npx vitest run` (Datei) + `git commit -m "fix(klage): KW-36 hq=0-Guard bei typ=eigen; Truncation entfaellt (Nachweis)"`

---

### Task 7: KW-38 — Positions-Key-Vertrag: eine Key-Map + Contract-Tests

**Files:**
- Create: `frontend/src/config/klagePositionKeys.js`
- Modify: `frontend/src/sections/KlageSection.jsx:313-322` (`_KLAGEN_KEY_MAP`), `:421-430` (`_KEY_MAP`), `frontend/src/sections/KlageWizard.jsx:828-846` (`_PROV_KEY_MAP`)
- Test: `frontend/src/config/__tests__/klagePositionKeys.test.js` (neu), `backend/tests/test_klage_kw38_position_keys.py` (neu)

**Interfaces:**
- Consumes: `POSITION_KEYS` (`backend/models/abrechnungsschreiben.py:20-36`, 39 Keys — kanonische Liste für `regulierung_positionen.position_key`); Wizard-Positions-Keys aus `pos_definitionen` (`backend/routers/klage_routes.py`).
- Produces: `export const KLAGE_KEY_MAP` (Regulierungs-Key → Wizard-Key; enthält die 8 Fahrzeugschaden-Aliase + alle weiteren sinnvollen Zuordnungen, z.B. `wbw`/`wbw_netto`/`wbw_brutto`/`reparatur_brutto` → `fahrzeugschaden`, `kostenpauschale` → `unkostenpauschale` falls `pos_definitionen` das so führt — Implementer leitet die Zielseite aus `pos_definitionen` ab) + `export const KEYS_OHNE_POSITION` (Set bewusst NICHT positionsgebundener Keys: `vorschuss`, `ra_gebuehren`, `mwst_abzug`, `pruefbericht_abzug`, `restwert`, `sonstiges`, … — je mit Begründung als Objekt `{key: "grund"}` oder Kommentar). Beide Nutzungsstellen in KlageSection + `_PROV_KEY_MAP` in KlageWizard importieren aus der neuen Datei (keine drei Kopien mehr).

- [ ] **Step 1: Failing Contract-Tests**

```js
// klagePositionKeys.test.js
import { KLAGE_KEY_MAP, KEYS_OHNE_POSITION } from "../klagePositionKeys";
// Spiegel der Backend-POSITION_KEYS (bewusste Kopie — der BE-Test sichert die Synchronität):
const POSITION_KEYS = ["reparaturkosten", "wiederbeschaffung", /* … alle 39 … */];
test("jeder position_key ist gemappt, identisch oder bewusst ausgenommen", () => {
  for (const k of POSITION_KEYS) {
    const abgedeckt = k in KLAGE_KEY_MAP || KEYS_OHNE_POSITION.has(k)
      || WIZARD_KEYS.includes(k);   // Identitäts-Keys (fahrzeugschaden, wertminderung, …)
    expect(abgedeckt, `position_key ohne Vertrag: ${k}`).toBe(true);
  }
});
```

```python
# test_klage_kw38_position_keys.py
from backend.models.abrechnungsschreiben import POSITION_KEYS
ERWARTET = {"reparaturkosten", "wiederbeschaffung", ...}  # alle 39, wörtlich
class TestKw38KeyVertrag(unittest.TestCase):
    def test_position_keys_unveraendert(self):
        self.assertEqual(set(POSITION_KEYS), ERWARTET,
            "POSITION_KEYS geändert — frontend/src/config/klagePositionKeys.js nachziehen!")
```

- [ ] **Step 2: RED** — FE-Test FAIL (Import-Fehler zählt nicht: erst Datei mit LEERER Map + Sets anlegen und exportieren, dann schlägt der Test aus VERHALTENS-Grund fehl: „position_key ohne Vertrag: …“). BE-Test direkt grün schreiben (reiner Wächter) — im Report als solcher ausweisen.

- [ ] **Step 3: Map vervollständigen + drei Kopien ablösen** — `KLAGE_KEY_MAP`/`KEYS_OHNE_POSITION` befüllen; `_KEY_MAP`, `_KLAGEN_KEY_MAP`, `_PROV_KEY_MAP` durch Importe ersetzen (Verhalten der 8 bisherigen Aliase byte-gleich; NEUE Zuordnungen wirken zusätzlich).

- [ ] **Step 4: GREEN + Fläche** — `npx vitest run` (voll) + `npm run build`; bestehende KlageSection/Wizard-Tests unverändert grün.

- [ ] **Step 5: Commit** — `git commit -m "fix(klage): KW-38 kanonische Positions-Key-Map + Contract-Tests BE/FE"`

---

### Task 8: KW-40 (Backend) — Toter Code raus, Merge über alle Platzhalter, Tab/GHPV/Label

**Files:**
- Modify: `backend/word/klage_service.py` — Löschungen: `_xml_absatz` (`:275`), `_xml_leerzeile` (`:297`), `_xml_tabelle_schaden` (`:306`), `_xml_tabelle_rvg` (`:358`), `_xml_antrag` (`:1914`), `_tab_rechts` (`:1162`), `_VORLAGE_FS` (`:39`), `kanzlei_str` (`:1160`), `mandant_anschr` (`:1023`), Top-Level `import zipfile` (`:25`); Änderungen: `_merge_split_placeholders`-Aufruf (`:590`), `antrag()` (`:1293`), GHPV-Auswahl (`:993-998`), Label-Fallback (`:907-910`)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse `TestKw40`)

**Interfaces:**
- Consumes: `_inject_block`/`_merge_split_placeholders` (`:590-618`), `ooxml_blocks` (15 Block-Platzhalter, `:1894-1910`), `beklagte_gef`-Filtermuster (`:1251-1253`).
- Produces: (a) `_merge_split_placeholders(xml, alle_16_platzhalter)` — Merge läuft über die 15 Blöcke + `{{GEGENSTANDSWERT}}` (Liste zentral definieren, `ooxml_blocks.keys()` + GEGENSTANDSWERT). (b) `antrag()` rendert die Antragsnummer als eigenen Run + `<w:tab/>`-Run statt rohem `\t` in `<w:t>` (analog `_beweis()`-Muster). (c) GHPV-Auswahl filtert wie `beklagte_gef` auf `checked !== false` und Nicht-Kläger-Rollen. (d) Label-Fallback: `extra_wdm_`-Präfix → „Sonstige Schäden“ (wie `sonstiges_wdm_`). (e) RVG-Antragsnummer-Raterei (`:1318-1320`): bleibt (kein besserer Vertrag ohne FE-Änderung) — im Report als bewusst belassen dokumentieren.

- [ ] **Step 1: Failing Tests (nur für Verhaltens-Fixes b–d)**

```python
class TestKw40(unittest.TestCase):
    def test_antrag_nutzt_tab_element(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertNotIn("1.\t", xml)            # kein roher Tab im w:t der Antraege
        self.assertIn("<w:tab/>", xml)           # Implementer: Assert auf den Antraege-Bereich eingrenzen (Anker "wird verurteilt")

    def test_ghpv_ueberspringt_nicht_gecheckte(self):
        pos = [_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)]
        akte = _akte_daten(pos)
        akte["beteiligte"] = [
            {"rolle": "beklagter", "checked": False, "versicherung": "FALSCHE VERS", "schaden_nr": "FALSCH-1"},
            {"rolle": "beklagter", "checked": True,  "versicherung": "RICHTIGE VERS", "schaden_nr": "RICHTIG-1"},
        ]
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertIn("RICHTIG-1", xml)
        self.assertNotIn("FALSCH-1", xml)

    def test_unbekannter_extra_key_wird_sonstige_schaeden(self):
        # Abrechnung mit position_key "extra_wdm_ss1" → Label "Sonstige Schäden", nicht "Extra Wdm Ss1"
        …
        self.assertNotIn("Extra Wdm Ss1", xml)
```

(Implementer: Fixture-Form für `beklagte`/`abrechnungen` aus bestehenden Tests der Datei übernehmen; cfg-`beklagte` vs. `akte_daten["beteiligte"]` — maßgeblich ist die Quelle, aus der `beklagte_liste` bei `:993` gespeist wird.)

- [ ] **Step 2: RED** — alle drei FAIL aus Verhaltensgrund.

- [ ] **Step 3: Fixes + Löschungen** — Verhaltens-Fixes wie in Interfaces; danach die 10 toten Symbole löschen (vor jedem Löschen: `grep -rn "<symbol>" backend/ frontend/` → 0 Treffer außer Definition). Merge-Änderung: `xml = _merge_split_placeholders(xml, _ALLE_PLATZHALTER)` mit Modul-Konstante.

- [ ] **Step 4: GREEN + volle Klage-Fläche** — `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/ -k "klage" -v`: null neue Failures. Löschungen sind test-neutral (tot) — Beleg: voller Klage-Sweep grün.

- [ ] **Step 5: Commit** (gern 2 Commits: „refactor(klage): KW-40 toten Code entfernt“ + „fix(klage): KW-40 w:tab-Element, GHPV-Filter, extra_wdm-Label, Merge ueber alle Platzhalter“)

---

### Task 9: KW-40 (Frontend) + KW-30-FE — Politur-Sammeltask

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx:1306-1311` (einwandeUebernehmen), `:1129-1151` (Kürzungssumme), `:725-731`+`KlageSection.jsx:474-480` (Mandant→Kläger), `:1773-1776` (ungeklaert-Warntext), `:1683/1747` (NaN-Guard), `:1698`+`:1750-1782` (Step-10-Warnung Unfallort/-datum), `KlageWizard.haftungsquote.test.jsx:205` (toter Fixture-Rest)
- Test: bestehende Testdateien erweitern (`KlageWizard.*.test.jsx`), ggf. neue `KlageWizard.kw40.test.jsx`

**Interfaces:**
- Consumes: `onRwText`/`rwText`, `kuerzungMap`, `fmtEuro`, `gesperrt`-Guard + Warnblock-Container in `StepZusammenfassung`, Props `unfallort`/`unfalldatum` (bereits durchgereicht, `KlageWizard.jsx:2463/2471`).
- Produces (je Punkt):
  1. **Einwände-Übernahme ersetzt statt appended:** eingefügter Block wird mit Markern `((EINWÄNDE-START))…((EINWÄNDE-ENDE))`? — NEIN, kein Marker-Gerüst (YAGNI): einfachste korrekte Lösung = Übernehmen ersetzt einen zuvor per Übernehmen eingefügten Block, indem der zuletzt eingefügte Text-Block gemerkt wird (`einwaendeEingefuegtRef`) und bei erneutem Übernehmen `rwText.replace(vorher, neu)` läuft; ist der alte Block nicht mehr im Text (Nutzer-Edit), wird angehängt wie bisher.
  2. **Negative Kürzungen:** `abzug`-Klemmung `Math.max(0, …)` in der SUMME (`:1151`-Pfad) — Anzeige-Guard `:1141` bleibt.
  3. **Mandant→Kläger dedupliziert + Artikel:** eine exportierte Funktion `ersetzeMandantDurchKlaeger(text, weiblich)` (Ablage: `KlageWizard.jsx` als named export, KlageSection importiert sie — Importrichtung Section→Wizard existiert bereits). Artikel-Fix: `/\bDer Mandant\b/g` → „Die Klägerin“ bei `weiblich`, `/\bDem Mandanten\b/g` → „Der Klägerin“, `/\bDen Mandanten\b/g` → „Die Klägerin“ (Akkusativ), sonst maskuline Formen; das nackte `\bMandant\b`-Fallback bleibt als letzte Regel.
  4. **ungeklaert-Warntext ehrlich:** Text zu „⚠ Aktivlegitimation ungeklärt – der Abschnitt enthält keinen Auto-Text; Ihr Sachverhaltstext wird unverändert übernommen.“ (Anzeige = Payload; Verhalten unverändert).
  5. **NaN-Guard:** `wizardRvgAussergOv` nicht-numerisch → Anzeige/Versand fallen auf `rvgAussergData?.gesamt || 0` zurück statt `fmtEuro(NaN)` (Helper `parseBetragOderNull`).
  6. **KW-30-FE:** Step-10-Warnblock (kein `gesperrt`-Eintrag — nur Warnung, das BE degradiert seit Task 2 sauber): `{!unfallort && <div>⚠ Kein Unfallort in der Akte — die Einleitung nennt keinen Ort.</div>}` analog `{!unfalldatum && …}` im bestehenden Container nach `:1776`.
  7. **Toter Fixture-Rest** `rvgData/rvgOverride` in `KlageWizard.haftungsquote.test.jsx:205` entfernen.
- **S4-M6** (StepVerzug zeigt ISO-Rohwert bei Vorbelegung): NUR mitnehmen, falls trivial beim NaN-Guard-Umfeld (Anzeige durch `fmtDatumDe` leiten); sonst vertagt lassen.

- [ ] **Step 1: Failing Tests** — je Punkt 1/2/3/5/6 ein Vitest (RTL bzw. reine Funktion); Muster:

```jsx
test("einwandeUebernehmen ersetzt vorherigen Block statt anzuhaengen", () => { … });
test("reguliert > gefordert senkt die Kuerzungssumme nicht", () => { … });
test("Der Mandant wird bei weiblich zu Die Klaegerin", () => {
  expect(ersetzeMandantDurchKlaeger("Der Mandant fuhr los.", true)).toBe("Die Klägerin fuhr los.");
});
test("nicht-numerisches RVG-Override zeigt kein NaN", () => { … });
test("Step 10 warnt bei fehlendem Unfallort", () => { … });
```

- [ ] **Step 2: RED je Test verifizieren** (Verhaltens-Rot; für Punkt 3 zuerst Export-only-Zwischenschritt).
- [ ] **Step 3: Fixes** gemäß Interfaces (Punkt 4 + 7 testfrei: Copy-Change + Fixture-Löschung, im Report ausweisen).
- [ ] **Step 4: GREEN + Fläche** — `npx vitest run` (voll) + `npm run build` grün.
- [ ] **Step 5: Commit** — `git commit -m "fix(klage): KW-40-FE Politur (Einwaende-Ersetzen, Kuerzungs-Klemmung, Mandant→Klaeger-Helfer, NaN-Guard) + KW-30 Step-10-Warnung"`

---

### Task 10: V10 — Render-Smoke + Golden-File-Matrix

**Files:**
- Test (nur Tests, kein Produktivcode): `backend/tests/test_klage_service_docx.py` (neue Klassen `TestV10RenderSmoke`, `TestV10Matrix`)

**Interfaces:**
- Consumes: `generiere_klageschrift`, `_akte_daten`/`_position`/`_document_xml`-Fixtures; alle Verhaltensänderungen aus Task 1–8 sind abgeschlossen (diese Matrix pinnt den End-Zustand).
- Produces: (a) Smoke: KEIN `{{` im Ergebnis-XML (fängt zersplitterte/unersetzte Platzhalter — Absicherung der Merge-Änderung aus Task 8). (b) Matrix über 24 Kombinationen: `mit_sg ∈ {False, True}` × `beklagte ∈ {1, 2}` × `aktivlegitimation_typ ∈ {eigentum, finanziert, geleast}` × `overrides ∈ {aus, an}` — je Kombination via `subTest`.

- [ ] **Step 1: Smoke-Test schreiben (direkt als Wächter — RED-Beleg per Mutation)**

```python
class TestV10RenderSmoke(unittest.TestCase):
    def test_kein_unersetzter_platzhalter(self):
        akte = _akte_daten([_position("fahrzeugschaden", "Fahrzeugschaden", 1000.0)])
        xml = _document_xml(generiere_klageschrift(akte))
        self.assertNotIn("{{", xml)
        self.assertNotIn("}}", xml)
```
RED-Beleg (Wächter-Wirksamkeit): temporär einen Block aus `ooxml_blocks` entfernen (lokale Mutation, nicht committen) → Test MUSS rot werden; Mutation zurücknehmen, Nachweis in den Report.

- [ ] **Step 2: Matrix schreiben**

```python
class TestV10Matrix(unittest.TestCase):
    def _cfg(self, mit_sg, n_bek, akt_typ, mit_overrides):
        pos = [_position("fahrzeugschaden", "Fahrzeugschaden", 3000.0)]
        akte = _akte_daten(pos, mit_schmerzensgeld=mit_sg,
                           schmerzensgeld_mindest=2000.0 if mit_sg else 0.0)
        akte["unfalldetails"]["aktivlegitimation_typ"] = akt_typ
        # n_bek Beklagte (Fixture-Form aus TestKw06 übernehmen)
        if mit_overrides:
            akte["klage_config"]["antraege_override"] = "1.\tDie Beklagten werden…\n2.\tKosten…"
            akte["unfalldetails"]["sachverhalt_override"] = "Absatz.\n\nBEWEIS: Zeugnis Meier"
        return akte

    def test_matrix(self):
        for mit_sg in (False, True):
          for n_bek in (1, 2):
            for akt_typ in ("eigentum", "finanziert", "geleast"):
              for ov in (False, True):
                with self.subTest(sg=mit_sg, bek=n_bek, typ=akt_typ, overrides=ov):
                    doc = generiere_klageschrift(self._cfg(mit_sg, n_bek, akt_typ, ov))
                    self.assertTrue(doc.startswith(b"PK"))
                    xml = _document_xml(doc)
                    self.assertNotIn("{{", xml)
                    if mit_sg and not ov: self.assertIn("Schmerzensgeld", xml)
                    if n_bek == 2 and not ov: self.assertIn("Gesamtschuldner", xml)
                    if akt_typ == "geleast" and not ov: self.assertNotIn("ist Eigentümer des", xml)
```

- [ ] **Step 3: Lauf** — `python -m pytest backend/tests/test_klage_service_docx.py -v` → alle grün (Matrix deckt 24 Renderings ab; Laufzeit prüfen, bei > 60 s je Matrix-Lauf Positionen-Fixture verschlanken).
- [ ] **Step 4: Commit** — `git commit -m "test(klage): V10 Render-Smoke + 24er-Golden-Matrix (SG x Beklagte x AktLeg x Overrides)"`

---

### Task 11: Abschluss — Baselines, Doku, Whole-Branch-Review

**Files:**
- Modify: `docs/BUGFIX_KLAGE_WIZARD.md` (KW-30–40 abhaken + Commit-Hashes, KW-36 `entfällt`-Teilvermerk, Status-Tabelle, PRD-33-KOMPLETT-Vermerk), `docs/TODO.md` (Session-6-Eintrag + PRD-33-Abschluss), Plan-Datei versionieren

- [ ] **Step 1: Volle Baselines** — Backend: `python -m pytest backend/ -p no:cacheprovider` (Vordergrund, Timeout 600000): Erwartung 204f-Alt-Cluster exakt (±2 Order-Rauschen → Datei-Ebene vergleichen), **null neue Failures**, Passes ≥ 1059 + neue Tests. Frontend: `npx vitest run` (≥ 200 + neue) + `npm run build`.
- [ ] **Step 2: Doku-Commit** — Tracking-Doc (`[x]` + Hashes je KW, KW-36 `entfällt (Truncation durch S2/S3 bereits beseitigt; Nachweis Grep …)`), TODO.md, Plan-Datei; expliziter `git add` der Einzelpfade.
- [ ] **Step 3: Finales Whole-Branch-Review** (Opus, `scripts/review-package c003e962 HEAD`), Critical/Important → EINE Fix-Wave, Re-Review.
- [ ] **Step 4: Abschlussbericht an RA Schatz** — inkl. der Session-Entscheidungen zum Vorlegen: Fall-B-Klammer-Formulierung (Task 5), KW-32-Nummerierungsänderung (Verzug jetzt nummeriert — Layoutänderung in jeder Klage mit Verzugsteil), offene Alt-Entscheidungen (KW-28-Fallback, KW-29-Retry, KW-27-Go-Live) unverändert offen. **FF-Merge nach main NUR nach Freigabe.**
