# PRD-33 Session 3 — Rubrum & Grammatik (KW-06, KW-15–KW-21) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die acht Rubrum-/Grammatik-Bugs des Klage-Wizards (KW-06, KW-15–KW-21) über ein zentrales Partei-Grammatik-Modell (V3) beheben: Genus-/Numerus-bewusste Bausteine statt verstreuter hart kodierter Singular-/Feminin-Formen, Gesamtschuldner-Anträge bei mehreren Beklagten, kanonische Beklagten-Liste für Rubrum UND Sachverhalt.

**Architektur:** Backend: kleine reine Grammatik-Helfer auf Modulebene von `backend/word/klage_service.py` (`_anrede_norm`, `_ist_maennliche_privatperson`, `_rechtsform_klasse`, `_beklagten_grammatik`, `_beklagten_rolle`, `_vertreter_suffix`); `generiere_klageschrift` konsumiert sie an den bekannten Stellen (Rubrum, Anträge, Einleitung, VK). Frontend: exportierte reine Funktionen in `KlageWizard.jsx` (`anredeNorm`, `kanonischeBeklagte`, `beklagtenGrammatik`, `versichererSuffix`) als Single Source für alle Beklagten-Filter/-Formulierungen. Tests: DOCX-Direkttest-Muster aus S2 (`test_klage_service_docx.py`) + reine Unit-Tests + Vitest.

**Tech Stack:** Python/Flask (Backend), python-docx-freies XML-Templating (bestehend), React + Vitest (Frontend), pytest.

## Global Constraints

- **TDD strikt:** erst fehlschlagender Test, dann Fix. Falscher Fund → im Tracking-Doc `entfällt` mit Begründung.
- **RA-MICRO read-only.** Keine DB-Migration in dieser Session.
- **Baseline:** Backend 204f/1000p (204f = bekannte Alt-Cluster `test_modul2/3/4/7`, `test_sv_portal`, `test_prd27`) — **null neue Failures**. Frontend 122 Vitest + `npm run build` grün.
- **Bestehende DOCX-Tests dürfen nicht brechen:** Der Einzel-Beklagten-Fall (eine Versicherung) muss byte-gleiche Sätze liefern wie heute („Die Beklagte wird verurteilt…", „– Beklagte –", „Die Beklagte ist die Haftpflichtversicherung…").
- **Nicht anfassen:** Legacy-`generieren()`-Button (KW-08, Session 4), vertagte Minors KW-34/KW-36 (nur nicht verschlimmern), `get_aktivlegitimation_text`-Singular-Texte (Forderungsschreiben-Pfad, nicht Session-Scope).
- **Test-Ausführung durch Subagents:** NIEMALS `run_in_background`, immer blockierend im Vordergrund, Timeout bis 600000 ms; volle Suite notfalls in zwei Hälften splitten.
- Backend-Tests aus dem Projekt-Root `unfallakten/` starten: `python -m pytest backend/tests/<datei> -q`. Frontend: im Ordner `frontend/`: `npx vitest run` bzw. `npm run build`.
- Code-Kommentare nur bei nicht-offensichtlichem Verhalten (Projektregel).
- Commits auf Branch `klage-wizard-fixes-s3`, Commit-Messages deutsch im bestehenden Stil (`fix(klage): KW-NN …`).

**Zeilennummern** in diesem Plan: Stand `main` d19b9640 (Ist-Erhebung 2026-07-18). Vor jedem Edit die Stelle frisch per Grep/Read verifizieren — durch die eigenen Tasks verschieben sie sich.

---

### Task 1: Backend-Grammatik-Helfer + KW-21 Rechtsform-Heuristik

**Files:**
- Modify: `backend/word/klage_service.py` (Modulebene, direkt vor `_funktion_aus_rechtsform_str` bei `:672`; die zwei bestehenden Funktionen `:672–694` umbauen)
- Test (neu): `backend/tests/test_klage_partei_grammatik.py`

**Interfaces:**
- Consumes: nichts (reine Funktionen; `re` ist im Modul bereits importiert — verifizieren, sonst importieren).
- Produces (spätere Tasks nutzen exakt diese Namen):
  - `_anrede_norm(anrede) -> str` — `"herr" | "frau" | ""` (versteht `"1"`, `"2"`, `"Herr"`, `"Herrn"`, `"Frau"`, Groß/klein, None)
  - `_ist_maennliche_privatperson(bek: dict) -> bool` — True nur wenn weder `firma` noch `versicherung` gesetzt und Anrede „herr"
  - `_rechtsform_klasse(firmenname: str) -> str` — `"gf" | "vorstand" | "sonstige"` (Wortgrenzen statt Substring)
  - `_beklagten_grammatik(beklagte_gef: list) -> dict` — Keys `verurteilt`, `verpflichtet`, `kosten`, `nom_klein`, `haftet`
  - `_beklagten_rolle(bek: dict) -> str` — `"Beklagter" | "Beklagte"`
  - `_vertreter_suffix(funktion: str, name: str, firmenname: str) -> str` — kompletter `, vertreten durch …`-Suffix
  - `_funktion_aus_rechtsform_str` / `_vertretungs_hinweis` — Signaturen unverändert, intern auf `_rechtsform_klasse`

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`backend/tests/test_klage_partei_grammatik.py` (vollständig neu):

```python
"""
PRD-33 Session 3 (KW-06/15/16/21): Reine Grammatik-Helfer in klage_service.
"""
import unittest

from backend.word.klage_service import (
    _anrede_norm,
    _ist_maennliche_privatperson,
    _rechtsform_klasse,
    _funktion_aus_rechtsform_str,
    _vertretungs_hinweis,
    _beklagten_grammatik,
    _beklagten_rolle,
    _vertreter_suffix,
)


class TestAnredeNorm(unittest.TestCase):
    def test_numerisch_und_klartext(self):
        self.assertEqual(_anrede_norm("1"), "herr")
        self.assertEqual(_anrede_norm("2"), "frau")
        self.assertEqual(_anrede_norm("Herr"), "herr")
        self.assertEqual(_anrede_norm("Herrn"), "herr")
        self.assertEqual(_anrede_norm("FRAU"), "frau")
        self.assertEqual(_anrede_norm(""), "")
        self.assertEqual(_anrede_norm(None), "")
        self.assertEqual(_anrede_norm("Firma"), "")


class TestMaennlichePrivatperson(unittest.TestCase):
    def test_herr_ohne_firma(self):
        self.assertTrue(_ist_maennliche_privatperson({"name": "Huber", "anrede": "1"}))
        self.assertTrue(_ist_maennliche_privatperson({"name": "Huber", "anrede": "Herr"}))

    def test_firma_oder_versicherung_nie_maennlich(self):
        self.assertFalse(_ist_maennliche_privatperson({"firma": "Muster GmbH", "anrede": "1"}))
        self.assertFalse(_ist_maennliche_privatperson({"versicherung": "Test AG", "anrede": "1"}))

    def test_frau_oder_unbekannt(self):
        self.assertFalse(_ist_maennliche_privatperson({"name": "Meier", "anrede": "2"}))
        self.assertFalse(_ist_maennliche_privatperson({"name": "Meier"}))


class TestRechtsformKlasse(unittest.TestCase):
    def test_kw21_ug_nicht_in_fahrzeugbau(self):
        self.assertEqual(_rechtsform_klasse("Autohaus Fahrzeugbau"), "sonstige")

    def test_kw21_bindestrich_ag(self):
        self.assertEqual(_rechtsform_klasse("Allianz Versicherungs-AG"), "vorstand")

    def test_gf_formen(self):
        self.assertEqual(_rechtsform_klasse("Fahrzeugbau Müller GmbH"), "gf")
        self.assertEqual(_rechtsform_klasse("Muster UG (haftungsbeschränkt)"), "gf")
        self.assertEqual(_rechtsform_klasse("Spedition Krause GmbH & Co. KG"), "gf")
        self.assertEqual(_rechtsform_klasse("Bau OHG"), "gf")
        self.assertEqual(_rechtsform_klasse("Praxis GbR"), "gf")

    def test_vorstand_formen(self):
        self.assertEqual(_rechtsform_klasse("Muster AG"), "vorstand")
        self.assertEqual(_rechtsform_klasse("Muster SE"), "vorstand")
        self.assertEqual(_rechtsform_klasse("Muster KGaA"), "vorstand")
        self.assertEqual(_rechtsform_klasse("Sportfreunde e.V."), "vorstand")

    def test_se_nicht_in_hanse(self):
        self.assertEqual(_rechtsform_klasse("HANSE SPEDITION GMBH"), "gf")
        self.assertEqual(_rechtsform_klasse("HANSE SPEDITION"), "sonstige")

    def test_wrapper_funktionen(self):
        self.assertEqual(_funktion_aus_rechtsform_str("Muster GmbH"), "Geschäftsführer")
        self.assertEqual(_funktion_aus_rechtsform_str("Versicherungs-AG"), "Vorstand")
        self.assertEqual(_funktion_aus_rechtsform_str("Autohaus Fahrzeugbau"),
                         "gesetzlichen Vertreter")
        self.assertEqual(_vertretungs_hinweis("Muster GmbH"),
                         "– vertreten durch den/die Geschäftsführer –")
        self.assertEqual(_vertretungs_hinweis("Versicherungs-AG"),
                         "– vertreten durch den Vorstand –")
        self.assertEqual(_vertretungs_hinweis("Autohaus Fahrzeugbau"),
                         "– vertreten durch den gesetzlichen Vertreter –")


class TestBeklagtenGrammatik(unittest.TestCase):
    VERS = {"versicherung": "Test-Versicherung AG"}
    MANN = {"name": "Huber", "vorname": "Hans", "anrede": "1"}
    FRAU = {"name": "Meier", "vorname": "Eva", "anrede": "2"}

    def test_mehrere_gesamtschuldner(self):
        g = _beklagten_grammatik([self.VERS, self.MANN])
        self.assertEqual(g["verurteilt"], "Die Beklagten werden als Gesamtschuldner verurteilt")
        self.assertEqual(g["verpflichtet"], "die Beklagten als Gesamtschuldner verpflichtet sind")
        self.assertEqual(g["kosten"], "Die Beklagten tragen die Kosten des Rechtsstreits.")
        self.assertEqual(g["nom_klein"], "die Beklagten")
        self.assertEqual(g["haftet"], "haften")

    def test_einzeln_versicherung_wie_bisher(self):
        g = _beklagten_grammatik([self.VERS])
        self.assertEqual(g["verurteilt"], "Die Beklagte wird verurteilt")
        self.assertEqual(g["kosten"], "Die Beklagte trägt die Kosten des Rechtsstreits.")
        self.assertEqual(g["haftet"], "haftet")

    def test_einzeln_maennlich(self):
        g = _beklagten_grammatik([self.MANN])
        self.assertEqual(g["verurteilt"], "Der Beklagte wird verurteilt")
        self.assertEqual(g["verpflichtet"], "der Beklagte verpflichtet ist")
        self.assertEqual(g["kosten"], "Der Beklagte trägt die Kosten des Rechtsstreits.")
        self.assertEqual(g["nom_klein"], "der Beklagte")

    def test_leere_liste_wie_einzeln_feminin(self):
        g = _beklagten_grammatik([])
        self.assertEqual(g["verurteilt"], "Die Beklagte wird verurteilt")

    def test_rolle(self):
        self.assertEqual(_beklagten_rolle(self.MANN), "Beklagter")
        self.assertEqual(_beklagten_rolle(self.FRAU), "Beklagte")
        self.assertEqual(_beklagten_rolle(self.VERS), "Beklagte")


class TestVertreterSuffix(unittest.TestCase):
    def test_kw16_feminine_funktion(self):
        self.assertEqual(
            _vertreter_suffix("Geschäftsführerin", "Erika Musterfrau", "Muster GmbH"),
            ", vertreten durch die Geschäftsführerin Frau Erika Musterfrau",
        )

    def test_maskuline_funktion(self):
        self.assertEqual(
            _vertreter_suffix("Geschäftsführer", "Max Mustermann", "Muster GmbH"),
            ", vertreten durch den Geschäftsführer Herrn Max Mustermann",
        )

    def test_vorsitzende_feminin(self):
        self.assertEqual(
            _vertreter_suffix("Vorstandsvorsitzende", "Erika Musterfrau", "Muster AG"),
            ", vertreten durch die Vorstandsvorsitzende Frau Erika Musterfrau",
        )

    def test_kw16_leere_funktion_keine_anrede_geraten(self):
        s = _vertreter_suffix("", "Erika Musterfrau", "Muster GmbH")
        self.assertEqual(s, ", vertreten durch den Geschäftsführer Erika Musterfrau")
        self.assertNotIn("Herrn", s)
        self.assertNotIn("Frau ", s)

    def test_ohne_name(self):
        self.assertEqual(_vertreter_suffix("", "", "Muster AG"),
                         ", vertreten durch den Vorstand")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_partei_grammatik.py -q`
Expected: ImportError (`_anrede_norm` etc. existieren nicht) bzw. Failures bei `test_kw21_*` / `test_wrapper_funktionen`.

- [ ] **Step 3: Implementierung in `klage_service.py`**

Direkt VOR `_funktion_aus_rechtsform_str` (`:672`) einfügen (`import re` steht bereits im Modulkopf — verifizieren):

```python
def _anrede_norm(anrede) -> str:
    a = str(anrede or "").strip().lower()
    if a in ("1", "herr", "herrn"):
        return "herr"
    if a in ("2", "frau"):
        return "frau"
    return ""


def _ist_maennliche_privatperson(bek: dict) -> bool:
    ist_firma = bool(bek.get("firma") or bek.get("versicherung"))
    return (not ist_firma) and _anrede_norm(bek.get("anrede")) == "herr"


def _rechtsform_klasse(firmenname: str) -> str:
    """Wortgrenzen-Klassifikation statt Substring ("UG" in "FAHRZEUGBAU", KW-21)."""
    roh = (firmenname or "").upper()
    if re.search(r"\bE\.\s?V\b", roh):
        return "vorstand"
    tokens = set(re.split(r"[^A-ZÄÖÜ0-9]+", roh))
    if tokens & {"GMBH", "UG", "GBR", "OHG", "KG"}:
        return "gf"
    if tokens & {"AG", "SE", "KGAA", "EV"}:
        return "vorstand"
    return "sonstige"


def _beklagten_grammatik(beklagte_gef: list) -> dict:
    if len(beklagte_gef) > 1:
        return {
            "verurteilt":   "Die Beklagten werden als Gesamtschuldner verurteilt",
            "verpflichtet": "die Beklagten als Gesamtschuldner verpflichtet sind",
            "kosten":       "Die Beklagten tragen die Kosten des Rechtsstreits.",
            "nom_klein":    "die Beklagten",
            "haftet":       "haften",
        }
    if beklagte_gef and _ist_maennliche_privatperson(beklagte_gef[0]):
        return {
            "verurteilt":   "Der Beklagte wird verurteilt",
            "verpflichtet": "der Beklagte verpflichtet ist",
            "kosten":       "Der Beklagte trägt die Kosten des Rechtsstreits.",
            "nom_klein":    "der Beklagte",
            "haftet":       "haftet",
        }
    return {
        "verurteilt":   "Die Beklagte wird verurteilt",
        "verpflichtet": "die Beklagte verpflichtet ist",
        "kosten":       "Die Beklagte trägt die Kosten des Rechtsstreits.",
        "nom_klein":    "die Beklagte",
        "haftet":       "haftet",
    }


def _beklagten_rolle(bek: dict) -> str:
    return "Beklagter" if _ist_maennliche_privatperson(bek) else "Beklagte"


def _vertreter_suffix(funktion: str, name: str, firmenname: str) -> str:
    """KW-16: Artikel/Anrede aus dem Genus der Funktion; ohne Funktion keine Anrede raten."""
    funktion = (funktion or "").strip()
    name = (name or "").strip()
    if funktion:
        weiblich = funktion.endswith("in") or funktion.endswith("ende")
        artikel = "die" if weiblich else "den"
        anrede = "Frau" if weiblich else "Herrn"
        if name:
            return f", vertreten durch {artikel} {funktion} {anrede} {name}"
        return f", vertreten durch {artikel} {funktion}"
    funk_label = _funktion_aus_rechtsform_str(firmenname)
    if name:
        return f", vertreten durch den {funk_label} {name}"
    return f", vertreten durch den {funk_label}"
```

Dann die beiden Bestandsfunktionen (`:672–694`) ERSETZEN durch:

```python
def _funktion_aus_rechtsform_str(firmenname: str) -> str:
    """Gibt die korrekte Funktion (Geschäftsführer/Vorstand) für eine Rechtsform zurück."""
    k = _rechtsform_klasse(firmenname)
    if k == "gf":
        return "Geschäftsführer"
    if k == "vorstand":
        return "Vorstand"
    return "gesetzlichen Vertreter"


def _vertretungs_hinweis(firmenname: str) -> str:
    """Vertretungshinweis je Rechtsform (Kläger-Rubrum bei Firmen)."""
    k = _rechtsform_klasse(firmenname)
    if k == "gf":
        return "– vertreten durch den/die Geschäftsführer –"
    if k == "vorstand":
        return "– vertreten durch den Vorstand –"
    return "– vertreten durch den gesetzlichen Vertreter –"
```

(Achtung: `_vertreter_suffix` ruft `_funktion_aus_rechtsform_str` auf — Definitionsreihenfolge im Modul ist egal, da Aufruf zur Laufzeit.)

- [ ] **Step 4: Tests laufen lassen — grün**

Run: `python -m pytest backend/tests/test_klage_partei_grammatik.py backend/tests/test_klage_service_docx.py -q`
Expected: alle PASS (bestehende DOCX-Tests unverändert grün, da nur die Heuristik-Innereien präziser wurden — „Test-Versicherung AG" bleibt „Vorstand").

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/tests/test_klage_partei_grammatik.py
git commit -m "fix(klage): KW-21 Rechtsform-Wortgrenzen + Partei-Grammatik-Helfer (V3-Basis)"
```

---

### Task 2: KW-15 Rubrum-Rolle + KW-16 Vertreter-Grammatik (Backend)

**Files:**
- Modify: `backend/word/klage_service.py:1142–1179` (Beklagten-Rubrum-Schleife in `generiere_klageschrift`)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse ans Dateiende)

**Interfaces:**
- Consumes: `_beklagten_rolle(bek)`, `_vertreter_suffix(funktion, name, firmenname)` aus Task 1; bestehender Harness `_akte_daten(...)`, `_document_xml(...)`, `generiere_klageschrift`.
- Produces: Rubrum-Zeile `– Beklagter – / – Beklagte –` genus-korrekt; Vertreter-Suffix zentral. Keine neuen Symbole.

- [ ] **Step 1: Fehlschlagende Tests schreiben**

In `test_klage_service_docx.py` ans Ende (XML-Escaping beachten: `–` ist als UTF-8 direkt im XML):

```python
class TestKW15KW16RubrumGenus(unittest.TestCase):
    """KW-15: Rubrum-Rolle genus-korrekt; KW-16: Vertreter-Grammatik."""

    def _mit_beklagten(self, beklagte):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["klage_config"]["beklagte"] = beklagte
        return _document_xml(generiere_klageschrift(akte_daten))

    def test_kw15_maennlicher_beklagter_rubrum(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
            "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach",
        }])
        self.assertIn("– Beklagter –", xml)
        self.assertNotIn("– Beklagte –", xml)

    def test_kw15_versicherung_bleibt_beklagte(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
        }])
        self.assertIn("– Beklagte –", xml)

    def test_kw15_gemischt_nummeriert(self):
        xml = self._mit_beklagten([
            {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
             "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"},
            {"rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
             "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach"},
        ])
        self.assertIn("– Beklagte zu 1) –", xml)
        self.assertIn("– Beklagter zu 2) –", xml)

    def test_kw16_geschaeftsfuehrerin_artikel_und_anrede(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "firma": "Muster GmbH",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
            "vertreter_name": "Erika Musterfrau", "vertreter_funktion": "Geschäftsführerin",
        }])
        self.assertIn("vertreten durch die Geschäftsführerin Frau Erika Musterfrau", xml)
        self.assertNotIn("den Geschäftsführerin", xml)

    def test_kw16_leere_funktion_keine_geratene_anrede(self):
        xml = self._mit_beklagten([{
            "rolle_klage": "beklagter", "firma": "Muster GmbH",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
            "vertreter_name": "Erika Musterfrau", "vertreter_funktion": "",
        }])
        self.assertIn("vertreten durch den Geschäftsführer Erika Musterfrau", xml)
        self.assertNotIn("Herrn Erika Musterfrau", xml)
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW15KW16RubrumGenus -q`
Expected: FAIL (`– Beklagter –` nicht gefunden; „den Geschäftsführerin" vorhanden).

- [ ] **Step 3: Rubrum-Schleife umbauen**

In `generiere_klageschrift`, Beklagten-Schleife (`:1142 ff.`):

(a) Vertreter-Block (`:1152–1167`) ERSETZEN durch:

```python
        vertreter_name = (bek.get("vertreter_name") or "").strip()
        vertreter_funk = (bek.get("vertreter_funktion") or "").strip()
        if ist_firma:
            vertreter_suffix = _vertreter_suffix(vertreter_funk, vertreter_name, bek_name)
        else:
            vertreter_suffix = ""
```

(Die Zeilen `_bek_person`/`bek_name`/`ist_firma`/`nr_suffix` davor bleiben unverändert.)

(b) Rollen-Zeile (`:1176`) ERSETZEN:

```python
        hpv_xml += _rolle_rechts(f"– {_beklagten_rolle(bek)}{nr_suffix} –")
```

- [ ] **Step 4: Tests laufen lassen — grün + Regression**

Run: `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py -q`
Expected: alle PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/tests/test_klage_service_docx.py
git commit -m "fix(klage): KW-15 Rubrum-Rolle genus-korrekt + KW-16 Vertreter-Grammatik"
```

---

### Task 3: KW-06 Gesamtschuldner-Anträge + Einleitung (Backend)

**Files:**
- Modify: `backend/word/klage_service.py` — Anträge-Auto-Zweig (`:1246–1296`), Einleitung (`:1317–1324`), VK-Abschnitt (`:1687–1688`); `bek_gram` direkt nach `beklagte_gef` (`:1141`) berechnen
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse)

**Interfaces:**
- Consumes: `_beklagten_grammatik`, `_anrede_norm` (Task 1); lokale Variablen `beklagte_gef`, `kl_dat`, `kl_dat3`, `klagebetrag`, `zins_sachsch`, `zins_rvg`, `rvg_antrag_betrag`, `gegner_kz`, `schadennummer`.
- Produces: lokale Variable `bek_gram` (dict) — wird in diesem Task überall dort konsumiert, wo bisher „Die Beklagte …" hart stand.

- [ ] **Step 1: Fehlschlagende Tests schreiben**

In `test_klage_service_docx.py` ans Ende:

```python
class TestKW06Gesamtschuldner(unittest.TestCase):
    """KW-06: Mehrere Beklagte -> Gesamtschuldner-Anträge + Einleitung je Beklagtem."""

    VERS = {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"}
    MANN = {"rolle_klage": "beklagter", "vorname": "Hans", "name": "Huber",
            "anrede": "1", "anschrift": "Weg 3", "plz": "63065", "ort": "Offenbach"}

    def _xml(self, beklagte, **kwargs):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)], **kwargs)
        akte_daten["klage_config"]["beklagte"] = beklagte
        akte_daten["klage_config"]["mit_feststellung_sach"] = True
        return _document_xml(generiere_klageschrift(akte_daten))

    def test_zwei_beklagte_gesamtschuldner_antrag1(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn(
            "Die Beklagten werden als Gesamtschuldner verurteilt, an den Kläger 400,00 € "
            "nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz "
            "seit Rechtshängigkeit zu zahlen.", xml)
        self.assertNotIn("Die Beklagte wird verurteilt", xml)

    def test_zwei_beklagte_feststellung_plural(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn("dass die Beklagten als Gesamtschuldner verpflichtet sind", xml)

    def test_zwei_beklagte_kosten_und_vk(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn("Die Beklagten tragen die Kosten des Rechtsstreits.", xml)
        self.assertIn("die Beklagten ebenfalls haften", xml)

    def test_zwei_beklagte_einleitung_je_beklagtem(self):
        xml = self._xml([self.VERS, self.MANN])
        self.assertIn("Die Beklagte zu 1) ist die Haftpflichtversicherung des "
                      "unfallverursachenden Fahrzeugs", xml)
        self.assertIn("Der Beklagte zu 2) war zum Unfallzeitpunkt der Fahrer des "
                      "unfallverursachenden Fahrzeugs.", xml)

    def test_ein_maennlicher_beklagter_singular_maskulin(self):
        xml = self._xml([self.MANN])
        self.assertIn("Der Beklagte wird verurteilt, an den Kläger 400,00 €", xml)
        self.assertIn("Der Beklagte trägt die Kosten des Rechtsstreits.", xml)

    def test_halter_beklagter_einleitung(self):
        halter = dict(self.MANN, ist_halter=1)
        xml = self._xml([self.VERS, halter])
        self.assertIn("Der Beklagte zu 2) ist der Halter des unfallverursachenden "
                      "Fahrzeugs.", xml)

    def test_regression_eine_versicherung_unveraendert(self):
        xml = self._xml([self.VERS])
        self.assertIn("Die Beklagte wird verurteilt, an den Kläger 400,00 €", xml)
        self.assertIn("Die Beklagte ist die Haftpflichtversicherung des "
                      "unfallverursachenden Fahrzeugs.", xml)
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW06Gesamtschuldner -q`
Expected: FAIL (Gesamtschuldner-Formulierungen fehlen; Regressions-Test PASS).

- [ ] **Step 3: Implementierung**

(a) Nach der `beklagte_gef`-Definition (`:1139–1141`) ergänzen:

```python
    bek_gram = _beklagten_grammatik(beklagte_gef)
```

(b) Im Anträge-Auto-Zweig alle hart kodierten Subjekte ersetzen:
- Antrag 1 (`:1246–1250`): `f"Die Beklagte wird verurteilt, an {kl_dat} …"` → `f"{bek_gram['verurteilt']}, an {kl_dat} …"` (Rest des Satzes unverändert).
- Beide SG-Anträge (`:1252–1266`): `"Die Beklagte wird verurteilt, an …"` → `f"{bek_gram['verurteilt']}, an …"`.
- Beide Feststellungsanträge (`:1268–1284`): `"dass die Beklagte verpflichtet ist, {kl_dat3} …"` → `f"dass {bek_gram['verpflichtet']}, {kl_dat3} …"`.
- RVG-Antrag (`:1285–1292`): `"Die Beklagte wird verurteilt, an {kl_dat} weitere …"` → `f"{bek_gram['verurteilt']}, an {kl_dat} weitere …"`.
- Kostenantrag (`:1293–1296`): die `kosten_text`-Ternary komplett ERSETZEN durch:

```python
        antraege_xml += antrag(bek_gram["kosten"], fett=False)
```

(c) VK-Abschnitt (`:1687–1688`) ERSETZEN:

```python
    bek_haften = bek_gram["haftet"]
    bek_nom    = bek_gram["nom_klein"]
```

(d) Einleitung (`:1317–1324`, die `beklagte_satz`-Ternary + `schadennummer`-Anhang) komplett ERSETZEN durch:

```python
        bek_saetze = []
        mehrere_bek = len(beklagte_gef) > 1
        schadennr_gesetzt = False
        for i, bek in enumerate(beklagte_gef):
            nr_str = f" zu {i+1})" if mehrere_bek else ""
            if bek.get("firma") or bek.get("versicherung"):
                satz = (
                    f"Die Beklagte{nr_str} ist die Haftpflichtversicherung des "
                    f"unfallverursachenden Fahrzeugs mit dem amtlichen Kennzeichen {gegner_kz}."
                    if gegner_kz else
                    f"Die Beklagte{nr_str} ist die Haftpflichtversicherung des "
                    f"unfallverursachenden Fahrzeugs."
                )
                if schadennummer and not schadennr_gesetzt:
                    satz += f" Sie führt den Vorgang unter der Schadennummer {schadennummer}."
                    schadennr_gesetzt = True
            else:
                weiblich_b = _anrede_norm(bek.get("anrede")) == "frau"
                art = "Die" if weiblich_b else "Der"
                if bek.get("ist_halter"):
                    bez = "die Halterin" if weiblich_b else "der Halter"
                    satz = f"{art} Beklagte{nr_str} ist {bez} des unfallverursachenden Fahrzeugs."
                else:
                    bez = "die Fahrerin" if weiblich_b else "der Fahrer"
                    satz = (f"{art} Beklagte{nr_str} war zum Unfallzeitpunkt {bez} "
                            f"des unfallverursachenden Fahrzeugs.")
            bek_saetze.append(satz)
        beklagte_satz = " ".join(bek_saetze)
```

Wichtig: Der Einzel-Versicherungs-Fall muss byte-identisch zum heutigen Text bleiben (Regressions-Test + bestehende Tests).

- [ ] **Step 4: Tests laufen lassen — grün + gezielte Regression**

Run: `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py backend/tests/test_klage_overrides_merge.py backend/tests/test_klage_s2_unkostenpauschale.py -q`
Expected: alle PASS. Insbesondere: KW-04-Klassen (Klagebetrag/Tabelle) unverändert grün — am Klagebetrag darf sich NICHTS ändern, nur an der Parteibenennung.

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/tests/test_klage_service_docx.py
git commit -m "fix(klage): KW-06 Gesamtschuldner-Antraege + Einleitung je Beklagtem"
```

---

### Task 4: KW-17 Kläger-Numerus + Vorsteuer + sg_text_builder (Backend)

**Files:**
- Modify: `backend/word/klage_service.py` — Genus-Block (`:952–967`), Einleitungssatz (`:1310–1316`), Eigentümer-/Halter-Satz (`:1329–1346`), RW-Satz Fall B eigen (`~:1596`), `baue_sg_abschnitt`-Aufruf (`:1610`), `kl_dat3`-Definition (per Grep lokalisieren)
- Modify: `backend/word/sg_text_builder.py:42–99`
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse) + `backend/tests/test_klage_partei_grammatik.py` (SG-Unit-Tests)

**Interfaces:**
- Consumes: bestehende Variablen `mehrere_klaeger`, `vorsteuer`, `anrede_m`, `kl_nom`.
- Produces: neue lokale Variablen `kl_macht` („macht"/„machen"), `kl_ist` („ist"/„sind"), `kl_laesst` („lässt"/„lassen") in allen 4 Zweigen des Genus-Blocks; `baue_sg_abschnitt(ps_data, kl_nom, sg_mind, verb_hat="hat")` (neuer optionaler Keyword-Parameter; Aufruf in `forderungsschreiben_wv.py:702` bleibt unverändert kompatibel).

- [ ] **Step 1: Fehlschlagende Tests schreiben**

In `test_klage_service_docx.py`:

```python
class TestKW17MehrereKlaeger(unittest.TestCase):
    """KW-17: Numerus bei mehreren Klaegern + Vorsteuer."""

    K1 = {"id": 1, "rolle_klage": "klaeger", "vorname": "Max", "name": "Mustermann",
          "anrede": "1", "anschrift": "Musterstr. 1", "plz": "63067", "ort": "Offenbach"}
    K2 = {"id": 2, "rolle_klage": "klaeger", "vorname": "Eva", "name": "Mustermann",
          "anrede": "2", "anschrift": "Musterstr. 1", "plz": "63067", "ort": "Offenbach"}

    def _xml(self, vorsteuer="N", mit_sg=False, sg_mind=0.0):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)],
                                 vorsteuer=vorsteuer,
                                 mit_schmerzensgeld=mit_sg,
                                 schmerzensgeld_mindest=sg_mind)
        akte_daten["klage_config"]["beklagte"] = [
            self.K1, self.K2,
            {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
             "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"},
        ]
        return _document_xml(generiere_klageschrift(akte_daten))

    def test_einleitung_plural_verb(self):
        xml = self._xml()
        self.assertIn("Die Kläger machen als nicht vorsteuerabzugsberechtigte "
                      "Geschädigte Schadensersatzforderungen", xml)
        self.assertNotIn("Die Kläger macht", xml)

    def test_eigentuemer_plural(self):
        xml = self._xml()
        self.assertIn("Die Kläger sind Eigentümer", xml)
        self.assertNotIn("Die Kläger ist", xml)

    def test_vorsteuer_bei_mehreren_klaegern_beruecksichtigt(self):
        xml = self._xml(vorsteuer="J")
        self.assertIn("als vorsteuerabzugsberechtigte Geschädigte", xml)
        self.assertNotIn("als nicht vorsteuerabzugsberechtigte Geschädigte", xml)

    def test_sg_plural_verb(self):
        xml = self._xml(mit_sg=True, sg_mind=1000.0)
        self.assertIn("Die Kläger haben durch den Unfall Verletzungen erlitten", xml)

    def test_feststellung_dativ_plural(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["klage_config"]["beklagte"] = [
            self.K1, self.K2,
            {"rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
             "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt"},
        ]
        akte_daten["klage_config"]["mit_feststellung_sach"] = True
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("den Klägern sämtliche", xml)
```

In `test_klage_partei_grammatik.py` ergänzen:

```python
from backend.word.sg_text_builder import baue_sg_abschnitt


class TestSgTextBuilderNumerus(unittest.TestCase):
    def test_default_singular(self):
        absaetze, _, _ = baue_sg_abschnitt({}, "Der Kläger", 0.0)
        self.assertTrue(absaetze[0].startswith("Der Kläger hat durch den Unfall"))

    def test_plural_verb(self):
        absaetze, _, _ = baue_sg_abschnitt({}, "Die Kläger", 0.0, verb_hat="haben")
        self.assertTrue(absaetze[0].startswith("Die Kläger haben durch den Unfall"))

    def test_plural_mit_verletzungen(self):
        absaetze, _, _ = baue_sg_abschnitt(
            {"verletzungen_text": "HWS-Distorsion"}, "Die Kläger", 0.0, verb_hat="haben")
        self.assertIn("Die Kläger haben durch den Unfall folgende Verletzungen "
                      "erlitten: HWS-Distorsion.", absaetze[0])
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW17MehrereKlaeger backend/tests/test_klage_partei_grammatik.py -q`
Expected: FAIL („Die Kläger macht", „Die Kläger ist", TypeError `verb_hat`).

- [ ] **Step 3: Implementierung**

(a) `sg_text_builder.py`: Signatur `def baue_sg_abschnitt(ps_data: dict, kl_nom: str, sg_mind: float, verb_hat: str = "hat"):`; die vier `{kl_nom} hat …`-Stellen (Z. 58, 61, 94, 98) auf `{kl_nom} {verb_hat} …` umstellen. Docstring um den Parameter ergänzen.

(b) `klage_service.py` Genus-Block (`:952–967`): in JEDEM der 4 Zweige drei Variablen ergänzen; Plural-Zweig zusätzlich `nicht_vst` korrigieren (Nominativ Plural ohne `-n`, vorsteuer-bewusst):

```python
    if mehrere_klaeger:
        kl_art  = "der"; kl_bez = "Kläger"; kl_nom = "Die Kläger"; kl_dat = "die Kläger"
        kl_einf = "Kläger"; kl_gesch = "Geschädigte"
        nicht_vst = "vorsteuerabzugsberechtigte" if vorsteuer else "nicht vorsteuerabzugsberechtigte"
        kl_macht = "machen"; kl_ist = "sind"; kl_laesst = "lassen"
```

und in den drei Singular-Zweigen jeweils: `kl_macht = "macht"; kl_ist = "ist"; kl_laesst = "lässt"`.

(c) `kl_dat3` per `Grep "kl_dat3" backend/word/klage_service.py` lokalisieren und im Plural-Fall auf `"den Klägern"` setzen (analog zu den anderen kl_*-Variablen im selben Block bzw. an seiner Definitionsstelle).

(d) Einleitungssatz (`:1310–1316`): beide Varianten `{kl_nom} macht` → `{kl_nom} {kl_macht}`.

(e) Eigentümer-/Halter-Satz (`:1329–1346`):

```python
        weiblich = anrede_m == "frau"
        if aktivlegitimation_typ in ("finanziert", "geleast"):
            if mehrere_klaeger:
                halter_besitzer = "Halter und unmittelbare Besitzer"
            elif weiblich:
                halter_besitzer = "Halterin und unmittelbare Besitzerin"
            else:
                halter_besitzer = "Halter und unmittelbarer Besitzer"
```

und in beiden Satz-Varianten `{kl_nom} ist` → `{kl_nom} {kl_ist}`; im else-Zweig `eigentuemer = "Eigentümer" if mehrere_klaeger else ("Eigentümerin" if weiblich else "Eigentümer")`.

(f) RW-Satz Fall B eigen (`~:1596`): `{kl_nom} lässt sich` → `{kl_nom} {kl_laesst} sich`.

(g) SG-Aufruf (`:1610`):

```python
        sg_absaetze, sg_beweis, sg_vgl = baue_sg_abschnitt(
            ps_data, kl_nom, sg_mind,
            verb_hat="haben" if mehrere_klaeger else "hat")
```

- [ ] **Step 4: Tests laufen lassen — grün + Regression Forderungsschreiben**

Run: `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py -q` und zusätzlich die bestehenden Tests, die `forderungsschreiben_wv`/SG berühren: `python -m pytest backend/tests -q -k "forderung or schmerzensgeld or sg_text"`
Expected: alle PASS (Default-Parameter hält den Forderungsschreiben-Pfad byte-gleich).

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/word/sg_text_builder.py backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py
git commit -m "fix(klage): KW-17 Klaeger-Numerus (Verben, Vorsteuer, Dativ, SG-Baustein)"
```

---

### Task 5: KW-18 Kläger-Fallback + harte Sperre (Backend + Route)

**Files:**
- Modify: `backend/word/klage_service.py` — nach der Kläger-Dedup-Schleife (`:944–950`), vor `mehrere_klaeger = …`
- Modify: `backend/routers/klage_routes.py:1379–1385` (try/except um `generiere_klageschrift`)
- Test: `backend/tests/test_klage_service_docx.py` (neue Klasse); `backend/tests/test_klage_overrides_merge.py` als Vorlage für einen 422-Route-Test (neue Testmethode dort ODER eigene kleine Datei `backend/tests/test_klage_kw18_route.py` nach demselben Harness-Muster)

**Interfaces:**
- Consumes: `mandant`-dict (bereits geladen `:929 ff.`), `klaeger_liste`.
- Produces: `generiere_klageschrift` wirft `ValueError("Kein Kläger ermittelbar – bitte Mandanten-/Parteidaten prüfen.")` wenn weder Kläger-Beteiligter noch brauchbare Mandantendaten; Route antwortet darauf mit HTTP 422.

- [ ] **Step 1: Fehlschlagende Tests schreiben**

In `test_klage_service_docx.py`:

```python
class TestKW18KlaegerFallback(unittest.TestCase):
    """KW-18: Rubrum ohne Klaeger -> Mandant-Fallback bzw. harte Sperre."""

    def test_fallback_auf_mandant(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["klage_config"]["beklagte"] = [{
            "rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
        }]
        xml = _document_xml(generiere_klageschrift(akte_daten))
        self.assertIn("Max Mustermann", xml)
        self.assertIn("– Kläger –", xml)

    def test_harte_sperre_ohne_mandant(self):
        akte_daten = _akte_daten([_position("wertminderung", "Wertminderung", 400.0)])
        akte_daten["mandant"] = {}
        akte_daten["klage_config"]["beklagte"] = [{
            "rolle_klage": "beklagter", "versicherung": "Test-Versicherung AG",
            "anschrift": "Teststr. 2", "plz": "12345", "ort": "Teststadt",
        }]
        with self.assertRaises(ValueError):
            generiere_klageschrift(akte_daten)
```

Hinweis: `_akte_daten` legt in `klage_config.beklagte` bislang KEINEN Kläger-Eintrag an — der Kläger kam bisher nie ins Rubrum (genau der Bug). `test_fallback_auf_mandant` schlägt vor dem Fix fehl, weil „– Kläger –" fehlt. Falls bestehende Harness-Tests bereits implizit auf leeres Kläger-Rubrum bauen (unwahrscheinlich — prüfen mit voller Datei), dort nachziehen.

Route-Test (Muster/Harness 1:1 aus `test_klage_overrides_merge.py` übernehmen — Flask-Client, Login, Temp-DB; dort wird `generiere_klageschrift` gepatcht):

```python
    def test_valueerror_wird_422(self):
        # im selben Harness wie test_klage_overrides_merge:
        with mock.patch.object(
            kr, "generiere_klageschrift",
            side_effect=ValueError("Kein Kläger ermittelbar – bitte Mandanten-/Parteidaten prüfen."),
        ):
            resp = self.client.post(self.url, json=self.body, headers=self.headers)
        self.assertEqual(resp.status_code, 422)
        self.assertIn("Kein Kläger ermittelbar", resp.get_json()["error"])
```

(Exakte Attributnamen/Fixtures aus der Vorlagendatei übernehmen; das Response-Format von `_err` dort nachschlagen — Feldname ggf. anpassen.)

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `python -m pytest backend/tests/test_klage_service_docx.py::TestKW18KlaegerFallback -q`
Expected: FAIL („– Kläger –" fehlt; kein ValueError).

- [ ] **Step 3: Implementierung**

(a) `klage_service.py`, direkt nach der Dedup-Schleife (`:944–950`), vor `mehrere_klaeger`:

```python
    if not klaeger_liste:
        _fb = {
            "rolle_klage": "klaeger",
            "name":      mandant.get("name") or "",
            "vorname":   mandant.get("vorname") or "",
            "firma":     mandant.get("firma") or "",
            "anschrift": mandant.get("anschrift") or "",
            "plz":       mandant.get("plz") or "",
            "ort":       mandant.get("ort") or "",
            "anrede":    mandant.get("anrede") or "",
        }
        if not (_fb["name"] or _fb["firma"]):
            raise ValueError("Kein Kläger ermittelbar – bitte Mandanten-/Parteidaten prüfen.")
        klaeger_liste = [_fb]
```

(b) `klage_routes.py` (`:1379–1385`) — `ValueError`-Zweig VOR dem generischen `except Exception` einfügen:

```python
    try:
        doc_bytes = generiere_klageschrift(akte_daten)
    except FileNotFoundError as e:
        return _err(str(e), 501)
    except ValueError as e:
        return _err(str(e), 422)
    except Exception as e:
        logger.error("Klage-Generierung fehlgeschlagen: %s", e, exc_info=True)
        return _err(f"Fehler beim Erstellen der Klageschrift: {e}", 500)
```

- [ ] **Step 4: Tests laufen lassen — grün**

Run: `python -m pytest backend/tests/test_klage_service_docx.py backend/tests/test_klage_partei_grammatik.py backend/tests/test_klage_overrides_merge.py backend/tests/test_klage_kw18_route.py -q` (Pfad je nachdem, wo der Route-Test gelandet ist)
Expected: alle PASS. Achtung: Durch den Fallback bekommen ALLE bestehenden DOCX-Tests jetzt einen Kläger-Rubrum-Block (Max Mustermann) — prüfen, dass keine bestehende Assertion dadurch bricht (z. B. `assertNotIn`-Prüfungen).

- [ ] **Step 5: Commit**

```bash
git add backend/word/klage_service.py backend/routers/klage_routes.py backend/tests/
git commit -m "fix(klage): KW-18 Klaeger-Fallback auf Mandant + 422 statt leerem Rubrum"
```

---

### Task 6: Frontend-Helfer + KW-20 kanonische Beklagten-Liste (Sachverhalt = Rubrum)

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` — neue Exporte vor `buildSachverhaltText` (`:87`); `buildSachverhaltText` umbauen (`:87–159`); `StepRubrum` (`:429–543`); `buildRwVorschau` (`:211–264`)
- Test (neu): `frontend/src/sections/KlageWizard.rubrum.test.jsx`

**Interfaces:**
- Consumes: bestehende `anrede`-Feldwerte (Klartext ODER RA-MICRO-numerisch „1"/„2").
- Produces (Task 7+8 nutzen exakt diese Namen aus `KlageWizard.jsx`):
  - `export function anredeNorm(anrede)` → `"herr" | "frau" | ""`
  - `export function kanonischeBeklagte(beklagte)` → Filter `rolle_klage !== "klaeger" && checked !== false` (Array-Reihenfolge = Rubrum = Backend)
  - `export function beklagtenGrammatik(beklagte)` → `{ anzahl, mehrere, verurteilt, verpflichtet, kosten }`
  - `export function versichererSuffix(beklagte)` → `" zu N)"` (Position der ersten Firma/Versicherung in der kanonischen Liste) oder `""`
  - `export function buildSachverhaltText(opts)` (neu exportiert)

- [ ] **Step 1: Fehlschlagende Tests schreiben**

`frontend/src/sections/KlageWizard.rubrum.test.jsx` (Setup-Kopf an bestehende Datei `KlageWizard.zusammenfassung.test.jsx` anlehnen — reine Funktionstests brauchen kein Rendering):

```jsx
import { describe, it, expect } from "vitest";
import {
  anredeNorm, kanonischeBeklagte, beklagtenGrammatik, versichererSuffix,
  buildSachverhaltText,
} from "./KlageWizard.jsx";

const VERS = { rolle_klage: "beklagter", versicherung: "Test-Versicherung AG", checked: true };
const MANN = { rolle_klage: "beklagter", name: "Huber", vorname: "Hans", anrede: "Herr", checked: true };
const FRAU_HALTER = { rolle_klage: "beklagter", name: "Meier", vorname: "Eva", anrede: "2", ist_halter: 1, checked: true };
const KLAEGER = { rolle_klage: "klaeger", name: "Mustermann", checked: true };

describe("anredeNorm", () => {
  it("versteht numerisch und Klartext", () => {
    expect(anredeNorm("1")).toBe("herr");
    expect(anredeNorm("2")).toBe("frau");
    expect(anredeNorm("Herr")).toBe("herr");
    expect(anredeNorm("")).toBe("");
  });
});

describe("kanonischeBeklagte (KW-20)", () => {
  it("filtert Klaeger und abgewaehlte, behaelt Reihenfolge", () => {
    const liste = [KLAEGER, VERS, { ...MANN, checked: false }, FRAU_HALTER];
    expect(kanonischeBeklagte(liste)).toEqual([VERS, FRAU_HALTER]);
  });
  it("checked=null zaehlt als angehakt (Backend-Default)", () => {
    expect(kanonischeBeklagte([{ rolle_klage: "beklagter", name: "X" }])).toHaveLength(1);
  });
});

describe("beklagtenGrammatik (KW-06)", () => {
  it("mehrere -> Gesamtschuldner", () => {
    const g = beklagtenGrammatik([VERS, MANN]);
    expect(g.verurteilt).toBe("Die Beklagten werden als Gesamtschuldner verurteilt");
    expect(g.verpflichtet).toBe("die Beklagten als Gesamtschuldner verpflichtet sind");
    expect(g.kosten).toBe("Die Beklagten tragen die Kosten des Rechtsstreits.");
  });
  it("einzelner Mann -> maskulin", () => {
    expect(beklagtenGrammatik([MANN]).verurteilt).toBe("Der Beklagte wird verurteilt");
  });
  it("einzelne Versicherung -> wie bisher", () => {
    expect(beklagtenGrammatik([VERS]).verurteilt).toBe("Die Beklagte wird verurteilt");
  });
});

describe("versichererSuffix", () => {
  it("nennt die Nummer der Versicherung in der kanonischen Liste", () => {
    expect(versichererSuffix([MANN, VERS])).toBe(" zu 2)");
    expect(versichererSuffix([VERS, MANN])).toBe(" zu 1)");
  });
  it("leer bei nur einem Beklagten", () => {
    expect(versichererSuffix([VERS])).toBe("");
  });
});

describe("buildSachverhaltText (KW-20)", () => {
  const basis = {
    klaeger: "Der Kläger", vorsteuer: false,
    unfalldatum: "01.02.2026", unfallort: "Offenbach",
    aktLegTyp: "eigentum", aktLegFreigabe: "freigabe", aktLegDatum: "",
    mandantKz: "OF-AB 1", mandantIstFahrer: false, auslandsunfall: false,
  };
  it("Nummerierung folgt der kanonischen Reihenfolge (= Rubrum)", () => {
    const text = buildSachverhaltText({ ...basis, beklagte: [VERS, MANN] });
    expect(text).toContain("Die Beklagte zu 1) ist die gegnerische Haftpflichtversicherung");
    expect(text).toContain("Der Beklagte zu 2) war zum Unfallzeitpunkt der Fahrer");
  });
  it("Nicht-Halter-Privatperson fehlt nicht mehr; Versicherung mit ist_halter nicht doppelt", () => {
    const versHalter = { ...VERS, ist_halter: 1 };
    const text = buildSachverhaltText({ ...basis, beklagte: [versHalter, MANN] });
    const saetze = text.split("\n").filter(z => z.includes("Beklagte"));
    expect(saetze).toHaveLength(2);
    expect(text).toContain("zu 2) war zum Unfallzeitpunkt der Fahrer");
  });
  it("Halterin mit korrektem Genus", () => {
    const text = buildSachverhaltText({ ...basis, beklagte: [VERS, FRAU_HALTER] });
    expect(text).toContain("Die Beklagte zu 2) ist die Halterin des unfallverursachenden Fahrzeugs.");
  });
});
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run (in `frontend/`): `npx vitest run src/sections/KlageWizard.rubrum.test.jsx`
Expected: FAIL (Exporte existieren nicht).

- [ ] **Step 3: Implementierung in `KlageWizard.jsx`**

(a) Vor `buildVorschauText` (`:47`) einfügen:

```jsx
export function anredeNorm(anrede) {
  const a = String(anrede || "").trim().toLowerCase();
  if (a === "1" || a === "herr" || a === "herrn") return "herr";
  if (a === "2" || a === "frau") return "frau";
  return "";
}

export function kanonischeBeklagte(beklagte) {
  return (beklagte || []).filter(b => b.rolle_klage !== "klaeger" && b.checked !== false);
}

export function beklagtenGrammatik(beklagte) {
  const gef = kanonischeBeklagte(beklagte);
  if (gef.length > 1) {
    return { anzahl: gef.length, mehrere: true,
      verurteilt: "Die Beklagten werden als Gesamtschuldner verurteilt",
      verpflichtet: "die Beklagten als Gesamtschuldner verpflichtet sind",
      kosten: "Die Beklagten tragen die Kosten des Rechtsstreits." };
  }
  const b = gef[0];
  const maennlich = !!b && !b.versicherung && !b.firma && anredeNorm(b.anrede) === "herr";
  if (maennlich) {
    return { anzahl: gef.length, mehrere: false,
      verurteilt: "Der Beklagte wird verurteilt",
      verpflichtet: "der Beklagte verpflichtet ist",
      kosten: "Der Beklagte trägt die Kosten des Rechtsstreits." };
  }
  return { anzahl: gef.length, mehrere: false,
    verurteilt: "Die Beklagte wird verurteilt",
    verpflichtet: "die Beklagte verpflichtet ist",
    kosten: "Die Beklagte trägt die Kosten des Rechtsstreits." };
}

export function versichererSuffix(beklagte) {
  const gef = kanonischeBeklagte(beklagte);
  if (gef.length <= 1) return "";
  const idx = gef.findIndex(b => b.versicherung || b.firma);
  return idx >= 0 ? ` zu ${idx + 1})` : "";
}
```

(b) `buildSachverhaltText` (`:87–159`): `export function …`; den kompletten Beklagten-Block (`:106–145`, von `const gegner = …` bis einschließlich der `bekSaetze.join`-Anfügung) ERSETZEN durch:

```jsx
  const gegner  = kanonischeBeklagte(beklagte);
  const mehrere = gegner.length > 1;
  const bekSaetze = gegner.map((b, i) => {
    const nrStr = mehrere ? ` zu ${i + 1})` : "";
    if (b.versicherung || b.firma) {
      const kz = b.kfz_kennzeichen || "";
      let satz = `Die Beklagte${nrStr} ist die gegnerische Haftpflichtversicherung des unfallverursachenden Fahrzeugs`;
      if (kz) satz += ` mit dem amtlichen Kennzeichen ${kz}`;
      return satz + ".";
    }
    const weiblichB = anredeNorm(b.anrede) === "frau";
    const art = weiblichB ? "Die" : "Der";
    if (b.ist_halter) {
      return `${art} Beklagte${nrStr} ist ${weiblichB ? "die Halterin" : "der Halter"} des unfallverursachenden Fahrzeugs.`;
    }
    return `${art} Beklagte${nrStr} war zum Unfallzeitpunkt ${weiblichB ? "die Fahrerin" : "der Fahrer"} des unfallverursachenden Fahrzeugs.`;
  });

  if (bekSaetze.length > 0) {
    text += "\n\n" + bekSaetze.join("\n");
  }
```

`fahrGegnerName` wird damit nicht mehr benötigt: aus der Destructuring-Signatur von `buildSachverhaltText` entfernen. Danach `Grep "fahrGegnerName" frontend/src`: wird es NUR noch als Prop zu `buildSachverhaltText` durchgereicht (StepAktLeg → Aufruf), Prop-Kette mit entfernen (StepAktLeg-Signatur + Aufrufstelle + `KlageSection.jsx:605`); wird es anderweitig angezeigt, dort belassen.

(c) `StepRubrum` (`:431–432` + `:500–503` + `:526–538`):
- `const beklagteG = kanonischeBeklagte(beklagte);`
- Kläger-Genus: `const anrede = anredeNorm(b.anrede);` (statt `toLowerCase()`), Vergleich `anrede === "frau"` — repariert numerische RA-MICRO-Anreden in der Vorschau.
- Beklagten-Rolle genus-bewusst:

```jsx
          const maennlich = !b.versicherung && !b.firma && anredeNorm(b.anrede) === "herr";
          return <RubrumZeile key={b.id || i} links={zeile}
            rolle={`Beklagte${maennlich ? "r" : ""}${nr_suffix}`} warn={warn} />;
```

(d) `buildRwVorschau` (`:211–264`):
- `:217` → `const beklagteGef = kanonischeBeklagte(beklagte);`
- `:220–221` → `const bek1Maenl = bek1 && !bek1.versicherung && !bek1.firma && anredeNorm(bek1.anrede) === "herr";`
- `:218` (`" (zu 1)"`) → `const nrSuffix = versichererSuffix(beklagte) || (beklagteGef.length > 1 ? " zu 1)" : "");`
  — Achtung: der hq>=100-Satz meint die HPV; `versichererSuffix` liefert deren echte Nummer.
- Teilregulierungs-Sätze (`:238`, `:243`): `Die Beklagte hat …` → `` `Die Beklagte${versichererSuffix(beklagte)} hat …` `` (beide Zweige).

- [ ] **Step 4: Tests laufen lassen — grün + bestehende Suite**

Run (in `frontend/`): `npx vitest run`
Expected: 122 Bestand + neue Tests PASS. Falls Bestands-Tests exakte RW-/Sachverhalt-Strings mit `(zu 1)` asserten (haftungsquote-Testdatei prüfen!), diese Assertions auf die neue ` zu N)`-Form anpassen — das ist die gewollte Vereinheitlichung mit dem Rubrum.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.rubrum.test.jsx frontend/src/sections/KlageSection.jsx
git commit -m "fix(klage): KW-20 kanonische Beklagten-Liste (Sachverhalt=Rubrum) + FE-Grammatik-Helfer"
```

---

### Task 7: KW-06 Frontend — Anträge/Gebühren/Einwände Gesamtschuldner

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` — `baueAntraegeText` (`:1866–1933`), `StepGebuehren`/`baueGebuehrenAntrag` (`:2048–2115`), `EinwandePanel` (`:1066–1102`)
- Test: `frontend/src/sections/KlageWizard.rubrum.test.jsx` (erweitern) bzw. bestehende `KlageWizard.gebuehren.test.jsx`

**Interfaces:**
- Consumes: `beklagtenGrammatik`, `kanonischeBeklagte`, `versichererSuffix`, `ANTRAEGE_PLACEHOLDER` (Task 6).
- Produces: keine neuen Symbole; Textänderungen.

- [ ] **Step 1: Fehlschlagende Tests schreiben**

In `KlageWizard.rubrum.test.jsx` ergänzen:

```jsx
import { baueAntraegeText, ANTRAEGE_PLACEHOLDER } from "./KlageWizard.jsx";

describe("baueAntraegeText (KW-06 FE)", () => {
  const POS = [{ key: "wertminderung", label: "WM", betrag: 400, betragOriginal: 400, checked: true }];
  const basis = { positionen: POS, mitSG: false, sgMind: 0, weiblich: false,
                  zinsenAb: "rechtshaengigkeit", verzug: "", unfalldatum: "01.02.2026",
                  mitFestSg: false, mitFestSach: false };

  it("mehrere Beklagte -> Gesamtschuldner, kein (zu 1)", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [VERS, MANN] });
    expect(text).toContain("Die Beklagten werden als Gesamtschuldner verurteilt, an den Kläger 400,00 €");
    expect(text).toContain("Die Beklagten tragen die Kosten des Rechtsstreits.");
    expect(text).not.toContain("(zu 1)");
    expect(text).toContain(ANTRAEGE_PLACEHOLDER);
  });

  it("Feststellungsantrag plural", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [VERS, MANN], mitFestSach: true });
    expect(text).toContain("dass die Beklagten als Gesamtschuldner verpflichtet sind,");
  });

  it("einzelner maennlicher Beklagter -> maskulin", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [MANN] });
    expect(text).toContain("Der Beklagte wird verurteilt, an den Kläger 400,00 €");
    expect(text).toContain("Der Beklagte trägt die Kosten des Rechtsstreits.");
  });

  it("einzelne Versicherung -> unveraendert wie bisher", () => {
    const text = baueAntraegeText({ ...basis, beklagte: [VERS] });
    expect(text).toContain("Die Beklagte wird verurteilt, an den Kläger 400,00 €");
    expect(text).toContain("Die Beklagte trägt die Kosten des Rechtsstreits.");
  });
});
```

Für `baueGebuehrenAntrag` (lebt in der Komponente): bestehende `KlageWizard.gebuehren.test.jsx` ansehen — wird dort `StepGebuehren` gerendert, einen Fall mit 2 Beklagten ergänzen, der den generierten Gebühren-Antragstext auf `"Die Beklagten werden als Gesamtschuldner verurteilt"` prüft (Rendering-/Props-Muster 1:1 aus der Datei übernehmen; `onGebuehrenText`-Callback abgreifen).

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run (in `frontend/`): `npx vitest run src/sections/KlageWizard.rubrum.test.jsx src/sections/KlageWizard.gebuehren.test.jsx`
Expected: FAIL („Die Beklagte (zu 1) wird verurteilt" statt Gesamtschuldner).

- [ ] **Step 3: Implementierung**

(a) `baueAntraegeText` (`:1870–1932`): `beklagteGef`/`nrSuffix` ersetzen durch `const g = beklagtenGrammatik(beklagte);` und alle sechs Bausteine umstellen:
- Hauptantrag: `` `${g.verurteilt}, an ${kl_akk} ${fNr(klagebetrag)} nebst Zinsen …` ``
- beide SG-Anträge: `` `${g.verurteilt}, an ${kl_akk} ein angemessenes, …` ``
- beide Feststellungsanträge: `` `Es wird festgestellt, dass ${g.verpflichtet}, ${kl_dat} sämtliche …` ``
- Kostenantrag: `antraege.push(g.kosten);`

(b) `StepGebuehren` (`:2048–2049`): `beklagteGef`/`nrSuffix` ersetzen durch `const g = beklagtenGrammatik(beklagte);`; `baueGebuehrenAntrag` (`:2107–2115`):

```jsx
  function baueGebuehrenAntrag(betrag) {
    const b = betrag !== undefined ? betrag : rvgNetto;
    return (
      `${g.verurteilt}, an ${kl_akk} weitere ` +
      `${b.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} € ` +
      `nebst Zinsen in Höhe von 5 Prozentpunkten über dem jeweiligen Basiszinssatz ` +
      `${zinsDat} zu zahlen.`
    );
  }
```

(c) `EinwandePanel.uebernehmen` (`:1065–1067` + `:1102`): `zuSuffix` ersetzen durch `const zuSuffix = versichererSuffix(beklagte);` (die alte `beklagteGef`-Filterzeile entfällt); Einleitungszeile `:1102`: `` `Die Beklagte${zuSuffix} hat folgende Positionen zu Unrecht nicht oder nicht vollständig reguliert:` ``.

- [ ] **Step 4: Tests laufen lassen — grün + volle FE-Suite**

Run (in `frontend/`): `npx vitest run`
Expected: alles PASS (ggf. Bestands-Assertions mit `(zu 1)`-Form auf neue Texte anpassen — nur wo der Test exakt die alte fehlerhafte Form festschrieb).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.rubrum.test.jsx frontend/src/sections/KlageWizard.gebuehren.test.jsx
git commit -m "fix(klage): KW-06 FE Gesamtschuldner-Antraege (baueAntraegeText, Gebuehren, Einwaende)"
```

---

### Task 8: KW-19 Generieren-Sperre bei 0 Beklagten

**Files:**
- Modify: `frontend/src/sections/KlageWizard.jsx` — `StepZusammenfassung` (`:1634–1643`, Warnblock `:1691–1718`, Beklagte-Zeile `:1675–1676`)
- Test: `frontend/src/sections/KlageWizard.zusammenfassung.test.jsx` (erweitern)

**Interfaces:**
- Consumes: `kanonischeBeklagte` (Task 6), bestehende `gesperrt`-Logik inkl. KW-23-Platzhalter-Guard.
- Produces: keine neuen Symbole.

- [ ] **Step 1: Fehlschlagenden Test schreiben**

In `KlageWizard.zusammenfassung.test.jsx` (Render-Muster der Datei übernehmen — sie rendert `StepZusammenfassung` bereits mit Props):

```jsx
  it("KW-19: sperrt Generieren, wenn keine Beklagten angehakt sind", () => {
    // Props wie im bestehenden Basis-Setup der Datei, aber:
    // beklagte = [{ rolle_klage: "klaeger", name: "Mustermann" },
    //             { rolle_klage: "beklagter", name: "Huber", checked: false }]
    // gericht gesetzt, positionen mit checked-Position, antraegeText ohne Platzhalter
    // dann:
    expect(screen.getByText(/Keine Beklagten ausgewählt/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Als Word generieren/ })).toBeDisabled();
  });
```

(Exakte Render-Helper/Basis-Props aus der Datei übernehmen; nur `beklagte` variieren.)

- [ ] **Step 2: Test laufen lassen — muss fehlschlagen**

Run (in `frontend/`): `npx vitest run src/sections/KlageWizard.zusammenfassung.test.jsx`
Expected: FAIL (Button enabled, Warntext fehlt).

- [ ] **Step 3: Implementierung**

In `StepZusammenfassung`:

```jsx
  const beklagteG   = kanonischeBeklagte(beklagte);
  // …
  const keineBeklagten = beklagteG.length === 0;
  const gesperrt = laedt || keinGericht || keinPositionen || keineBeklagten
                 || firmenOhneVertreter.length > 0 || hatPlatzhalter;
```

Beklagte-Zeile (`:1675–1676`): `warn={keineBeklagten}` ergänzen und Wert `"— keine —"` wenn leer. Warnblock-Bedingung (`:1691`) um `|| keineBeklagten` erweitern und als neuen Block (Stil identisch zu `keinGericht`):

```jsx
          {keineBeklagten && <div style={{ fontFamily: PLEX, fontSize: "0.82rem", color: T.red,
            padding: "7px 12px", background: `${T.red}10`, borderRadius: 7, marginBottom: 6 }}>
            ⚠ Keine Beklagten ausgewählt – bitte im Parteien-Bereich mindestens einen Beklagten anhaken.
          </div>}
```

- [ ] **Step 4: Tests laufen lassen — grün + Build**

Run (in `frontend/`): `npx vitest run` und `npm run build`
Expected: alle Tests PASS, Build grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/sections/KlageWizard.jsx frontend/src/sections/KlageWizard.zusammenfassung.test.jsx
git commit -m "fix(klage): KW-19 Generieren-Sperre bei 0 Beklagten"
```

---

### Task 9: Volle Baselines + Tracking-Doku

**Files:**
- Modify: `docs/BUGFIX_KLAGE_WIZARD.md` (Status-Tabelle + 8 Bug-Abschnitte: `[x]` + Commit-Hashes + ggf. Umsetzungs-Notizen; Session-Tabelle Zeile 3)
- Modify: `docs/TODO.md` (Abschnitt „AKTIV — NÄCHSTE SCHRITTE": S3 als erledigt vermerken, nächste = S4)

**Interfaces:** —

- [ ] **Step 1: Volle Backend-Suite**

Run: `python -m pytest backend/tests -q` (blockierend, Timeout 600000 ms; notfalls in zwei Hälften)
Expected: 204 Failures ausschließlich in den bekannten Alt-Clustern (`test_modul2/3/4/7`, `test_sv_portal`, `test_prd27`), **null neue Failures**; Passes ≥ 1000 + neue Tests. Bei Abweichung: jede neue Failure einzeln aufklären, bevor weitergemacht wird.

- [ ] **Step 2: Volle Frontend-Suite + Build**

Run (in `frontend/`): `npx vitest run` und `npm run build`
Expected: ≥ 122 + neue Tests PASS, Build grün.

- [ ] **Step 3: Tracking-Doc aktualisieren**

In `docs/BUGFIX_KLAGE_WIZARD.md`: Status-Tabelle (KW-06, KW-15–21 → `✅ behoben <hash>`), die 8 Abschnitte auf `- [x] … — behoben <hash>, Session 3 <Datum>` setzen mit 1–3 Zeilen Umsetzungsnotiz (analog zum S2-Stil), Session-Aufteilungstabelle Zeile 3 abhaken. Falls sich ein Fund als falsch herausstellte: `entfällt` mit Begründung.

- [ ] **Step 4: TODO.md aktualisieren**

Im Abschnitt „🎯 AKTIV": Session-3-Erledigung mit Datum, Commits, Baseline-Zahlen; „nächste: S4 (KW-09/10/12/13/08 — Datum/RVG/Anlagen, V5+V6)".

- [ ] **Step 5: Commit**

```bash
git add docs/BUGFIX_KLAGE_WIZARD.md docs/TODO.md
git commit -m "docs(klage): PRD-33 Session 3 abgehakt (KW-06/15/16/17/18/19/20/21)"
```

---

## Nach Plan-Abschluss (Session-Workflow, nicht Teil der Tasks)

1. Abschluss-Review (Opus, Whole-Branch `klage-wizard-fixes-s3` gegen `main`), Fix-Wave falls nötig.
2. FF-Merge nach `main` **erst nach Freigabe durch RA Schatz**. Nicht pushen (main ist ohnehin ~55 Commits vor origin).
