# Wiedervorlagecode-Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die an sechs Stellen verstreute Auslegung des RA-MICRO-Feldes `iWiedervorlageGrund` durch eine einzige Registry-YAML ersetzen und dabei den Freitext zur maßgeblichen Quelle machen.

**Architecture:** Eine YAML (`backend/registry/wiedervorlage_codes.yaml`) hält die 46 eingebauten RA-MICRO-Codes mit Bezeichnung und Kachelzuordnung. Ein Loader (`backend/services/wiedervorlage_code_registry.py`) nach dem Muster von `beteiligten_kuerzel_registry.py` liest sie fail-loud und bietet zwei Funktionen: `loese_wv_grund()` für die Anzeige und `sql_codeliste()` für die `IN`-Klauseln der SQL-Abfragen. Alle bisherigen Listen und SQL-Literale werden gelöscht.

**Tech Stack:** Python 3 / Flask / pymssql (read-only gegen RA-MICRO SQL Server 2014, TDS 7.0) · PyYAML · pytest · React / Vite / vitest

**Spec:** Abschnitt „Befundlage" in diesem Dokument (erhoben am 2026-09-01 gegen die Produktivdatenbank, alle 1.610 Zeilen `RAMICRO.dbo.tblAktenWiedervorlagen`)

## Global Constraints

- **RA-MICRO ist read-only.** Keine schreibende Anweisung, kein `COMMIT`. Nur `SELECT`.
- **Zielsprache Deutsch** in allen nutzersichtbaren Texten, Kommentaren und Commit-Botschaften.
- **Keine Kommentare im Code** außer bei nicht-offensichtlichem Verhalten (CLAUDE.md).
- **Registries sind fail-loud:** Ein fehlerhafter Eintrag wirft beim Laden `RuntimeError`, es gibt keinen stillen Auffang.
- **YAML ohne Umlaute in Kommentaren** — Konvention der bestehenden Registries (`beteiligten_kuerzel.yaml`). In den Werten (`bezeichnung`) sind Umlaute erlaubt, weil sie nutzersichtbar sind.
- **Backend-Tests:** `JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/ -q` auf dem **Host**, nicht im Container.
- **Frontend-Tests:** `npm test` (vitest run) im Ordner `frontend/`.
- **RA-MICRO-Mockpflicht in Tests:** Kein Test darf eine echte Verbindung öffnen. Muster: `monkeypatch.setattr(<modul>, "get_ramicro_connection", lambda: conn)` mit den Hilfsklassen aus `backend/tests/test_ablage_service.py`.

---

## Befundlage (Spec)

Erhoben am 2026-09-01 gegen die Produktivdatenbank.

### Das Feld `iWiedervorlageGrund` hat zwei Bedeutungen

| Sorte | Codes | Zeilen | `sWiedervorlagegrund` |
|---|---|---|---|
| A — eingebauter Katalog | 5–99 | 958 | **ausnahmslos leer** |
| B — laufende ID | ab 63912 | 652 | 648× gefüllt |

693 verschiedene Zahlen bei 1.610 Zeilen. Die Zahl allein ist also keine Kategorie. Der Katalogtext der eingebauten Gründe steht in **keiner** der acht Datenbanken auf dem Server (rund 500 Textspalten durchsucht). RA-MICRO hält ihn intern.

Beide Sorten sind parallel in aktivem Gebrauch, kein Altbestand: 2026 entfallen 886 von 1.428 Wiedervorlagen (62 %) auf Katalog-Codes. Je Sachbearbeiter stark unterschiedlich — SK 82 %, CS 97 %, AS 35 %.

`sBemerkung` ist die optionale Notiz: 155 von 1.610 gefüllt (~10 %), inhaltlich Hinweise wie „Deckungszusage ist da!" — wird bisher nirgends angezeigt.

### Die sechs Stellen, die dasselbe Feld auslegen

Bezeichnungen:

| Ort | Konstante | Einträge |
|---|---|---|
| `backend/ramicro/wiedervorlage_service.py:36` | `RAMICRO_WV_GRUENDE` | 40 |
| `backend/routers/dashboard_routes.py:358` | `_RAMICRO_GRUENDE` | 16 |
| `backend/routers/dashboard_routes.py:441` | `_TERMIN_LABELS` | 3 |
| `backend/routers/dashboard_routes.py:447` | `_FRIST_LABELS` | 7 |

Kachelzuordnung — dieselbe Information zusätzlich dreimal als SQL-Literal:

| Ort | Ausdruck |
|---|---|
| `dashboard_routes.py:436-438` | `_TERMIN_CODES` / `_FRIST_CODES` / `_WV_AUSSCHLUSS` |
| `_lade_termine_heute()` | `WHERE w.iWiedervorlageGrund IN (9, 58, 60)` |
| `_lade_ramicro_fristen_hart()` | `WHERE w.iWiedervorlageGrund IN (21, 22, 31, 46, 51, 55, 75)` |
| `_lade_wiedervorlagen()` | `WHERE w.iWiedervorlageGrund NOT IN (9, 21, 22, 31, 46, 51, 55, 58, 60, 75)` |

Dazu eine vierte Codeliste in `wiedervorlage_service.py`: `iWiedervorlageGrund IN (5, 6, 11, 16)` für den Stellungnahme-Filter.

**Die vier Bezeichnungslisten widersprechen sich nicht** — wo sie sich überschneiden, sind die Texte identisch. Sie unterscheiden sich nur in der Vollständigkeit. Die Zusammenführung ändert daher keine bestehende Beschriftung.

### Wichtige Folge für die Abnahme

`_RAMICRO_GRUENDE` (16 Einträge) ist die Liste, aus der die **Wiedervorlagen-Kachel** ihre Beschriftungen zieht. Sie kennt 21 der real vorkommenden Codes nicht — darunter Code 12 (169 Zeilen) und Code 16 (217 Zeilen). Diese Einträge zeigen heute pauschal „Wiedervorlage".

Nach der Zusammenführung bekommen **537 Wiedervorlagen** erstmals eine konkrete Beschriftung („Zahlung Gegner", „Ermittlungsakte", „Insolvenzverfahren" …) — und zwar eine **unverifizierte**. Sie stammt aus einer früheren Session („RA-Micro Handbuch / empirisch ermittelt") und ist gegen die echte RA-MICRO-Auswahlliste nie geprüft worden.

**Deshalb ist Task 0 ein Freigabe-Gate: Ohne die Verifikation durch RA Schatz darf Task 2 nicht ausgerollt werden.** Der Code darf gebaut und getestet werden; nur die Bezeichnungen müssen vor der produktiven Sichtbarkeit stimmen.

### Bewusst behaltene Codes

Die Codes 22 (Urteil), 38 (Kostenantrag), 46 (Berufung), 88 (Besprechung) und 94 (Akte schließen) kommen im Bestand **nie** vor. Sie werden trotzdem übernommen, damit der Umbau verhaltensgleich bleibt — 22 und 46 stehen heute in `_FRIST_CODES` und würden bei einem Wegfall stillschweigend von der Fristen- in die Wiedervorlagen-Kachel wandern. Ein SSOT-Umbau soll Verhalten vereinheitlichen, nicht ändern.

### Nicht Gegenstand dieses Plans

- **Echte Fristen.** RA-MICRO speichert sie nicht im SQL Server (alle acht Datenbanken geprüft; `raKalender.dbo.Deadlist` existiert, ist aber leer). Was die Fristen-Kachel zeigt, sind Wiedervorlagen bestimmter Codes. Getrennt zu klären.
- **Freitext-Wiedervorlagen als Fristen erkennen.** Unter den 652 Freitext-Einträgen stehen echte Fristsachen („Anspruchsbegründung fertigen! DRINGEND!"). Sie bleiben in der Wiedervorlagen-Kachel. Stichwortsuche auf frei getippten Text ist eine eigene Entscheidung.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `backend/registry/wiedervorlage_codes.yaml` | **Neu.** Die 46 Codes: Bezeichnung, Kachelart, Verifikationsstand. Einzige Datenquelle. |
| `backend/services/wiedervorlage_code_registry.py` | **Neu.** Laden, Prüfen, Auflösen. Bietet `loese_wv_grund()`, `codes_fuer_art()`, `sql_codeliste()`. |
| `backend/tests/test_wiedervorlage_codes.py` | **Neu.** Loader-Verhalten, Auflösungsregel, Fail-loud-Prüfungen, Guard gegen neue hartcodierte Listen. |
| `backend/routers/dashboard_routes.py` | **Ändern.** Vier Listen und drei SQL-Literale entfernen, Registry nutzen, `sBemerkung` durchreichen, toten Endpoint löschen. |
| `backend/ramicro/wiedervorlage_service.py` | **Ändern.** `RAMICRO_WV_GRUENDE` und `_loeseWvGrund` entfernen, Stellungnahme-Filter aus der Registry. |
| `backend/routers/wiedervorlage_routes.py` | **Ändern.** Ein Importpfad und ein Aufruf. |
| `frontend/src/views/action_board/boardUi.jsx` | **Ändern.** `ZeileText` bekommt eine optionale dritte Zeile für die Bemerkung. |
| `frontend/src/views/action_board/FristenKachel.jsx` | **Ändern.** Bemerkung anzeigen. |
| `frontend/src/views/action_board/WiedervorlagenKachel.jsx` | **Ändern.** Bemerkung anzeigen. |
| `frontend/src/api.js` | **Ändern.** Toten Endpunkt `ramicroFristen` entfernen. |

---

### Task 0: Bezeichnungen verifizieren (Freigabe-Gate, ohne Code)

Diese Aufgabe erledigt **RA Schatz**, nicht der Umsetzende. Sie blockiert nicht den Bau der Tasks 1–5, wohl aber deren produktive Sichtbarkeit.

**Files:** keine

- [ ] **Schritt 1: RA-MICRO-Auswahlliste abfotografieren**

In RA-MICRO eine Wiedervorlage anlegen und das Feld „Wiedervorlagegrund" aufklappen. Der Screenshot der Liste ersetzt die gesamte Prüftabelle unten.

- [ ] **Schritt 2: Falls kein Screenshot möglich — Stichprobe je Fristen-Code**

Diese fünf Akten in RA-MICRO öffnen und den dortigen Wiedervorlagegrund ablesen:

| Code | Vermutung im Code | Belegakte | WV-Datum |
|---|---|---|---|
| 55 | Beschwerde | 158/25CO Hammer / Hess. Amt f. Versorgung | 25.11.2026 |
| 21 | Klage | 157/23AS Badran / Ermittlungsverfahren | 28.04.2027 |
| 51 | Einspruch | 361/25PK Morneweg / Kaapke | 10.09.2026 |
| 75 | Fristablauf | 403/26AH Reinhard / Susnjar | 02.09.2026 |
| 31 | Mahnbescheid | 808/26AS Kwakye / Strafsache | 25.09.2026 |

- [ ] **Schritt 3: Sechs unbeschriftete Codes klären**

Die Codes 25, 61, 63, 78, 93 und 98 kommen im Bestand vor, standen aber in keiner der vier alten Listen. Belegakten: 25 → 760/25PK, 61 → 568/26AH, 63 → 333/26PK, 78 → 754/24PK, 93 → 683/26AH, 98 → 488/25PK.

- [ ] **Schritt 4: Ergebnis in die YAML eintragen**

Je geprüftem Code `bezeichnung` korrigieren und `verifiziert: true` setzen. Bei den sechs offenen Codes zusätzlich `offen: true` entfernen.

---

### Task 1: Registry-YAML und Loader

**Files:**
- Create: `backend/registry/wiedervorlage_codes.yaml`
- Create: `backend/services/wiedervorlage_code_registry.py`
- Test: `backend/tests/test_wiedervorlage_codes.py`

**Interfaces:**
- Consumes: nichts (erste Aufgabe)
- Produces:
  - `GUELTIGE_ARTEN: frozenset[str]` = `{"frist", "termin", "wiedervorlage"}`
  - `WvGrund` — eingefrorene Dataclass mit `text: str`, `code: Optional[int]`, `art: str`, `aus_freitext: bool`, `unbekannt: bool`
  - `lade_wv_codes(pfad: Optional[str] = None, *, reload: bool = False) -> WvCodeRegistry`
  - `loese_wv_grund(grund_text: Any, grund_code: Any) -> WvGrund`
  - `codes_fuer_art(*arten: str) -> Tuple[int, ...]`
  - `sql_codeliste(*arten: str) -> str` — z. B. `"9, 58, 60"`
  - `stellungnahme_codes() -> Tuple[int, ...]`
  - Umgebungsvariable `WIEDERVORLAGE_CODES_REGISTRY_PFAD` überschreibt den Pfad (für Tests)

- [ ] **Schritt 1: Die Registry-YAML anlegen**

Datei `backend/registry/wiedervorlage_codes.yaml`:

```yaml
# RA-MICRO-Wiedervorlagecodes -- Uebersetzungshilfe, KEIN Katalog
# ================================================================
#
# Der Wiedervorlagegrund ist in RA-MICRO ein freier Text und die einzige
# massgebliche Angabe. Diese Datei deutet ihn NICHT und vereinheitlicht ihn
# NICHT -- sie springt nur dort ein, wo RA-MICRO den Text nicht in die
# SQL-Datenbank schreibt.
#
# Datenbefund 2026-09-01, alle 1.610 Zeilen tblAktenWiedervorlagen:
#   Codes 5..99      958 Zeilen  sWiedervorlagegrund AUSNAHMSLOS leer
#   Codes ab 63912   652 Zeilen  sWiedervorlagegrund gefuellt (648 von 652)
# Der Katalogtext der eingebauten Gruende steht in KEINER der acht
# Datenbanken auf dem Server (rund 500 Textspalten durchsucht).
#
# PFLEGE: keine. Legt die Kanzlei einen neuen Grund an, bekommt er eine
# Nummer ab 63912 und immer den Text dazu -- er landet nie hier.
#
# Die Bezeichnungen sind aus einer frueheren Session uebernommen und NICHT
# belegt ("RA-Micro Handbuch / empirisch ermittelt"), deshalb ueberall
# verifiziert: false. Die Haeufigkeit im Kommentar ist der Realitaetstest.
# verifiziert steuert die Anzeige NICHT -- es dokumentiert den Pruefstand
# und wird vom Guard-Test gezaehlt.

version: "1.0-unverifiziert"

# Ab hier ist die Zahl eine laufende ID, kein eingebauter Grund.
# Zwischen 99 und 63912 klafft eine Luecke; 1000 liegt sicher darin.
freitext_ab: 1000

# art steuert allein die Kachel-Zuordnung der Tagesuebersicht.
# stellungnahme: true ersetzt die Codeliste im Stellungnahme-Filter
# von hole_faellige_wiedervorlagen().
codes:

  # ── Fristen-Kachel ────────────────────────────────────────────────────
  21: {bezeichnung: "Klage",                 art: frist, verifiziert: false}  #  20x
  22: {bezeichnung: "Urteil",                art: frist, verifiziert: false}  #   0x
  31: {bezeichnung: "Mahnbescheid",          art: frist, verifiziert: false}  #   1x
  46: {bezeichnung: "Berufung",              art: frist, verifiziert: false}  #   0x
  51: {bezeichnung: "Einspruch",             art: frist, verifiziert: false}  #  10x
  55: {bezeichnung: "Beschwerde",            art: frist, verifiziert: false}  #  38x
  75: {bezeichnung: "Fristablauf",           art: frist, verifiziert: false}  #   3x

  # ── Termine-Kachel ────────────────────────────────────────────────────
   9: {bezeichnung: "Entscheidung/Gericht",  art: termin, verifiziert: false}  #   1x
  58: {bezeichnung: "Verhandlungstermin",    art: termin, verifiziert: false}  #  14x
  60: {bezeichnung: "Anhoerungstermin",      art: termin, verifiziert: false}  #   4x

  # ── Wiedervorlagen-Kachel ─────────────────────────────────────────────
   5: {bezeichnung: "Stellungnahme Gegner",  art: wiedervorlage, verifiziert: false, stellungnahme: true}  #   5x
   6: {bezeichnung: "Stellungnahme Mandant", art: wiedervorlage, verifiziert: false, stellungnahme: true}  #   7x
  10: {bezeichnung: "Ermittlungsakte",       art: wiedervorlage, verifiziert: false}  #  44x
  11: {bezeichnung: "Stellungnahme Mandant", art: wiedervorlage, verifiziert: false, stellungnahme: true}  #  80x
  12: {bezeichnung: "Zahlung Gegner",        art: wiedervorlage, verifiziert: false}  # 169x
  16: {bezeichnung: "Stellungnahme Gegner?", art: wiedervorlage, verifiziert: false, stellungnahme: true}  # 217x
  17: {bezeichnung: "Reaktion Rechtsschutz", art: wiedervorlage, verifiziert: false}  #  19x
  18: {bezeichnung: "Deckungszusage",        art: wiedervorlage, verifiziert: false}  #  10x
  19: {bezeichnung: "Sachstand",             art: wiedervorlage, verifiziert: false}  #  44x
  20: {bezeichnung: "Fristverlaengerung",    art: wiedervorlage, verifiziert: false}  #   5x
  23: {bezeichnung: "Vergleich",             art: wiedervorlage, verifiziert: false}  #   4x
  26: {bezeichnung: "Gutachten",             art: wiedervorlage, verifiziert: false}  #   5x
  28: {bezeichnung: "Sachverstaendiger",     art: wiedervorlage, verifiziert: false}  #   9x
  32: {bezeichnung: "Vollstreckung",         art: wiedervorlage, verifiziert: false}  #  69x
  34: {bezeichnung: "Erneute EV moeglich",   art: wiedervorlage, verifiziert: false}  #  10x
  35: {bezeichnung: "Insolvenzverfahren",    art: wiedervorlage, verifiziert: false}  #  49x
  36: {bezeichnung: "Zwangsvollstreckung",   art: wiedervorlage, verifiziert: false}  #  37x
  38: {bezeichnung: "Kostenantrag",          art: wiedervorlage, verifiziert: false}  #   0x
  39: {bezeichnung: "Honorar",               art: wiedervorlage, verifiziert: false}  #   2x
  43: {bezeichnung: "Akteneinsicht",         art: wiedervorlage, verifiziert: false}  #   8x
  49: {bezeichnung: "Revision",              art: wiedervorlage, verifiziert: false}  #   2x
  54: {bezeichnung: "Widerspruch",           art: wiedervorlage, verifiziert: false}  #   8x
  62: {bezeichnung: "Schriftsatz",           art: wiedervorlage, verifiziert: false}  #   2x
  69: {bezeichnung: "Post",                  art: wiedervorlage, verifiziert: false}  #  17x
  71: {bezeichnung: "Telefonat",             art: wiedervorlage, verifiziert: false}  #   1x
  81: {bezeichnung: "Rueckruf",              art: wiedervorlage, verifiziert: false}  #   2x
  88: {bezeichnung: "Besprechung",           art: wiedervorlage, verifiziert: false}  #   0x
  91: {bezeichnung: "Abrechnung",            art: wiedervorlage, verifiziert: false}  #  32x
  94: {bezeichnung: "Akte schliessen",       art: wiedervorlage, verifiziert: false}  #   0x
  99: {bezeichnung: "Sonstiges",             art: wiedervorlage, verifiziert: false}  #   1x

  # ── kommen im Bestand vor, standen aber in KEINER alten Liste ─────────
  # Bezeichnung offen -- siehe Task 0. offen: true erlaubt die leere
  # bezeichnung; angezeigt wird solange "Unbekannter Grund (<code>)".
  25: {bezeichnung: "", art: wiedervorlage, verifiziert: false, offen: true}  #  1x
  61: {bezeichnung: "", art: wiedervorlage, verifiziert: false, offen: true}  #  1x
  63: {bezeichnung: "", art: wiedervorlage, verifiziert: false, offen: true}  #  3x
  78: {bezeichnung: "", art: wiedervorlage, verifiziert: false, offen: true}  #  2x
  93: {bezeichnung: "", art: wiedervorlage, verifiziert: false, offen: true}  #  1x
  98: {bezeichnung: "", art: wiedervorlage, verifiziert: false, offen: true}  #  1x

standard:
  text_und_code_leer: "ohne Angabe"
  code_unbekannt:     "Unbekannter Grund"
  art:                wiedervorlage
```

- [ ] **Schritt 2: Die fehlschlagenden Tests schreiben**

Datei `backend/tests/test_wiedervorlage_codes.py`:

```python
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-wv-codes")

import textwrap

import pytest

from backend.services.wiedervorlage_code_registry import (
    codes_fuer_art,
    lade_wv_codes,
    loese_wv_grund,
    sql_codeliste,
    stellungnahme_codes,
)


class TestAufloesung:
    """Der Freitext ist die massgebliche Quelle, die Nummer nur der Notnagel."""

    def test_freitext_schlaegt_den_katalog(self):
        g = loese_wv_grund("Gegner gemeldet / gezahlt?", 63915)
        assert g.text == "Gegner gemeldet / gezahlt?"
        assert g.aus_freitext is True
        assert g.unbekannt is False

    def test_freitext_wird_nicht_gedeutet(self):
        g = loese_wv_grund("  Klage fertigen!  ", 63944)
        assert g.text == "Klage fertigen!"
        assert g.art == "wiedervorlage"

    def test_leerer_text_faellt_auf_den_katalog_zurueck(self):
        g = loese_wv_grund("", 55)
        assert g.text == "Beschwerde"
        assert g.aus_freitext is False
        assert g.art == "frist"

    def test_none_text_faellt_auf_den_katalog_zurueck(self):
        assert loese_wv_grund(None, 12).text == "Zahlung Gegner"

    def test_freitextcode_ohne_text_gibt_ohne_angabe(self):
        g = loese_wv_grund("", 63974)
        assert g.text == "ohne Angabe"
        assert g.art == "wiedervorlage"

    def test_unbekannter_katalogcode_nennt_die_nummer(self):
        g = loese_wv_grund("", 47)
        assert g.text == "Unbekannter Grund (47)"
        assert g.unbekannt is True
        assert g.art == "wiedervorlage"

    def test_offener_code_gilt_als_unbekannt(self):
        g = loese_wv_grund("", 61)
        assert g.text == "Unbekannter Grund (61)"
        assert g.unbekannt is True

    def test_kein_code_und_kein_text(self):
        g = loese_wv_grund(None, None)
        assert g.text == "ohne Angabe"
        assert g.code is None

    def test_code_als_string_wird_akzeptiert(self):
        assert loese_wv_grund("", "55").text == "Beschwerde"

    def test_unbrauchbarer_code_wird_wie_kein_code_behandelt(self):
        assert loese_wv_grund("", "abc").text == "ohne Angabe"


class TestKachelzuordnung:
    """Ersetzt _TERMIN_CODES / _FRIST_CODES / _WV_AUSSCHLUSS und die
    drei gleichlautenden SQL-Literale in dashboard_routes.py."""

    def test_fristcodes_unveraendert(self):
        assert codes_fuer_art("frist") == (21, 22, 31, 46, 51, 55, 75)

    def test_termincodes_unveraendert(self):
        assert codes_fuer_art("termin") == (9, 58, 60)

    def test_ausschluss_ist_die_vereinigung(self):
        assert codes_fuer_art("frist", "termin") == (
            9, 21, 22, 31, 46, 51, 55, 58, 60, 75)

    def test_sql_codeliste_ist_eine_kommaliste(self):
        assert sql_codeliste("termin") == "9, 58, 60"

    def test_unbekannte_art_wird_abgelehnt(self):
        with pytest.raises(ValueError):
            codes_fuer_art("quatsch")

    def test_stellungnahme_codes_unveraendert(self):
        assert stellungnahme_codes() == (5, 6, 11, 16)


class TestFailLoud:
    """Registries brechen bei fehlerhaften Eintraegen hart ab."""

    def _schreibe(self, tmp_path, inhalt):
        p = tmp_path / "wv.yaml"
        p.write_text(textwrap.dedent(inhalt), encoding="utf-8")
        return str(p)

    def test_unbekannte_art(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              5: {bezeichnung: "X", art: quatsch, verifiziert: false}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="art"):
            lade_wv_codes(p, reload=True)

    def test_leere_bezeichnung_ohne_offen(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              5: {bezeichnung: "", art: wiedervorlage, verifiziert: false}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="bezeichnung"):
            lade_wv_codes(p, reload=True)

    def test_fehlendes_verifiziert(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              5: {bezeichnung: "X", art: wiedervorlage}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="verifiziert"):
            lade_wv_codes(p, reload=True)

    def test_code_im_freitextbereich(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes:
              63912: {bezeichnung: "X", art: wiedervorlage, verifiziert: false}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="freitext_ab"):
            lade_wv_codes(p, reload=True)

    def test_leere_registry(self, tmp_path):
        p = self._schreibe(tmp_path, """
            freitext_ab: 1000
            codes: {}
            standard: {text_und_code_leer: "a", code_unbekannt: "b", art: wiedervorlage}
        """)
        with pytest.raises(RuntimeError, match="leer"):
            lade_wv_codes(p, reload=True)

    def test_datei_fehlt(self, tmp_path):
        with pytest.raises(RuntimeError, match="nicht lesbar"):
            lade_wv_codes(str(tmp_path / "gibtsnicht.yaml"), reload=True)


class TestPruefstand:
    """Dokumentiert den offenen Verifikationsstand, ohne ihn zu erzwingen."""

    def test_jeder_eintrag_traegt_ein_verifiziert_flag(self):
        r = lade_wv_codes()
        fehlend = [c for c, e in r.codes.items() if "verifiziert" not in e]
        assert fehlend == []

    def test_verifizierte_eintraege_haben_eine_bezeichnung(self):
        r = lade_wv_codes()
        leer = [c for c, e in r.codes.items()
                if e.get("verifiziert") and not e.get("bezeichnung")]
        assert leer == []
```

- [ ] **Schritt 3: Tests laufen lassen, Fehlschlag bestätigen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/test_wiedervorlage_codes.py -q
```

Erwartung: `ModuleNotFoundError: No module named 'backend.services.wiedervorlage_code_registry'`

- [ ] **Schritt 4: Den Loader schreiben**

Datei `backend/services/wiedervorlage_code_registry.py`:

```python
"""
Wiedervorlagecode-Registry -- SSOT fuer RA-MICRO-Wiedervorlagegruende.

Bis 2026-09-01 legten vier Konstanten und drei SQL-Literale dasselbe Feld
iWiedervorlageGrund unabhaengig voneinander aus. Folge: Die Fristen-Kachel
zeigte Kategorien ("Beschwerde", "Einspruch"), die niemand in der Kanzlei
kannte, und die Wiedervorlagen-Kachel beschriftete 537 Eintraege pauschal
mit "Wiedervorlage", weil ihre Liste 21 Codes nicht kannte.

Massgeblich ist der Freitext sWiedervorlagegrund. Die Registry springt nur
ein, wo RA-MICRO ihn nicht in die SQL-Datenbank schreibt (Codes 5..99).
"""

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import yaml

GUELTIGE_ARTEN = frozenset({"frist", "termin", "wiedervorlage"})

_PFLICHT_STANDARD = ("text_und_code_leer", "code_unbekannt", "art")


@dataclass(frozen=True)
class WvGrund:
    text: str
    code: Optional[int]
    art: str
    aus_freitext: bool
    unbekannt: bool


@dataclass(frozen=True)
class WvCodeRegistry:
    version: str
    pfad: str
    freitext_ab: int
    codes: Dict[int, Dict[str, Any]]
    standard: Dict[str, Any]


_cache: Dict[str, WvCodeRegistry] = {}


def standard_pfad() -> str:
    env = os.environ.get("WIEDERVORLAGE_CODES_REGISTRY_PFAD")
    if env:
        return env
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "registry", "wiedervorlage_codes.yaml"))


def _pruefe(code: int, eintrag: Dict[str, Any], freitext_ab: int) -> None:
    wo = f"Code {code}"
    if not isinstance(eintrag, dict):
        raise RuntimeError(f"Wiedervorlagecode-Registry: {wo} ist kein Eintrag")
    art = eintrag.get("art")
    if art not in GUELTIGE_ARTEN:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: unbekannte art '{art}' bei {wo}")
    if "verifiziert" not in eintrag:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: 'verifiziert' fehlt bei {wo}")
    if not eintrag.get("bezeichnung") and not eintrag.get("offen"):
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: leere 'bezeichnung' bei {wo} -- "
            f"entweder ausfuellen oder 'offen: true' setzen")
    if code >= freitext_ab:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: {wo} liegt ueber freitext_ab "
            f"({freitext_ab}) und ist damit kein eingebauter Grund")


def lade_wv_codes(pfad: Optional[str] = None, *,
                  reload: bool = False) -> WvCodeRegistry:
    p = pfad or standard_pfad()
    if not reload and p in _cache:
        return _cache[p]
    try:
        with open(p, "rb") as fh:
            roh = fh.read()
    except OSError as e:
        raise RuntimeError(f"Wiedervorlagecode-Registry nicht lesbar: {p}: {e}") from e
    try:
        data = yaml.safe_load(roh) or {}
    except yaml.YAMLError as e:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry ist kein gueltiges YAML: {p}: {e}") from e

    freitext_ab = int(data.get("freitext_ab") or 0)
    if freitext_ab <= 0:
        raise RuntimeError(f"Wiedervorlagecode-Registry: freitext_ab fehlt: {p}")

    codes_roh = data.get("codes") or {}
    if not codes_roh:
        raise RuntimeError(f"Wiedervorlagecode-Registry ist leer: {p}")

    codes: Dict[int, Dict[str, Any]] = {}
    for k, eintrag in codes_roh.items():
        code = int(k)
        _pruefe(code, eintrag, freitext_ab)
        codes[code] = eintrag

    standard = data.get("standard") or {}
    for feld in _PFLICHT_STANDARD:
        if not standard.get(feld):
            raise RuntimeError(
                f"Wiedervorlagecode-Registry: '{feld}' fehlt in 'standard': {p}")
    if standard["art"] not in GUELTIGE_ARTEN:
        raise RuntimeError(
            f"Wiedervorlagecode-Registry: unbekannte art in 'standard': {p}")

    registry = WvCodeRegistry(
        version=hashlib.sha256(roh).hexdigest()[:16],
        pfad=p,
        freitext_ab=freitext_ab,
        codes=codes,
        standard=standard,
    )
    _cache[p] = registry
    return registry


def _als_code(wert: Any) -> Optional[int]:
    if wert is None:
        return None
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def loese_wv_grund(grund_text: Any, grund_code: Any) -> WvGrund:
    """Wiedervorlagegrund zur Anzeige aufloesen.

    Reihenfolge:
      1. Freitext vorhanden  -> Freitext, unveraendert
      2. Freitext leer, Code im Katalog -> Bezeichnung aus der Registry
      3. sonst -> Auffangtext aus 'standard'
    """
    registry = lade_wv_codes()
    text = (str(grund_text).strip() if grund_text is not None else "")
    code = _als_code(grund_code)

    eintrag = None
    if code is not None and code < registry.freitext_ab:
        eintrag = registry.codes.get(code)
    art = eintrag["art"] if eintrag else registry.standard["art"]

    if text:
        return WvGrund(text=text, code=code, art=art,
                       aus_freitext=True, unbekannt=False)

    if eintrag and eintrag.get("bezeichnung"):
        return WvGrund(text=eintrag["bezeichnung"], code=code, art=art,
                       aus_freitext=False, unbekannt=False)

    if code is None or code >= registry.freitext_ab:
        return WvGrund(text=registry.standard["text_und_code_leer"], code=code,
                       art=art, aus_freitext=False, unbekannt=False)

    return WvGrund(text=f'{registry.standard["code_unbekannt"]} ({code})',
                   code=code, art=art, aus_freitext=False, unbekannt=True)


def codes_fuer_art(*arten: str) -> Tuple[int, ...]:
    for a in arten:
        if a not in GUELTIGE_ARTEN:
            raise ValueError(f"Unbekannte Kachel-Art: {a}")
    registry = lade_wv_codes()
    return tuple(sorted(c for c, e in registry.codes.items() if e["art"] in arten))


def sql_codeliste(*arten: str) -> str:
    """Kommaliste fuer eine IN-Klausel.

    Die Werte sind ints aus der Registry, nie Nutzereingaben -- die
    Interpolation in den SQL-String ist deshalb unbedenklich.
    """
    return ", ".join(str(int(c)) for c in codes_fuer_art(*arten))


def stellungnahme_codes() -> Tuple[int, ...]:
    registry = lade_wv_codes()
    return tuple(sorted(c for c, e in registry.codes.items()
                        if e.get("stellungnahme")))
```

- [ ] **Schritt 5: Tests laufen lassen, Erfolg bestätigen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/test_wiedervorlage_codes.py -q
```

Erwartung: alle Tests grün.

- [ ] **Schritt 6: Committen**

```bash
git add backend/registry/wiedervorlage_codes.yaml backend/services/wiedervorlage_code_registry.py backend/tests/test_wiedervorlage_codes.py
git commit -m "feat(wiedervorlage): Registry-YAML als SSOT fuer RA-MICRO-Wiedervorlagegruende"
```

---

### Task 2: dashboard_routes.py auf die Registry umstellen

**Files:**
- Modify: `backend/routers/dashboard_routes.py` (Zeilen 340–430 löschen, 436–458 ersetzen, SQL in `_lade_termine_heute`, `_lade_ramicro_fristen_hart`, `_lade_wiedervorlagen`)
- Modify: `frontend/src/api.js:936`
- Test: `backend/tests/test_dashboard_wv_registry.py` (neu)

**Interfaces:**
- Consumes: `loese_wv_grund`, `sql_codeliste` aus Task 1
- Produces: Die Endpunkte `/dashboard/fristen`, `/dashboard/termine-heute` und `/dashboard/wiedervorlagen` liefern zusätzlich das Feld `bemerkung: str` je Eintrag (leer, wenn keine Bemerkung hinterlegt ist).

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `backend/tests/test_dashboard_wv_registry.py`:

```python
import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-dashboard-wv")

import datetime

from backend.routers import dashboard_routes


class _Cursor:
    def __init__(self, antworten):
        self._antworten = list(antworten)
        self.sqls = []

    def execute(self, sql, params=None):
        self.sqls.append(sql)

    def fetchall(self):
        return self._antworten.pop(0) if self._antworten else []


class _Conn:
    def __init__(self, antworten):
        self._cursor = _Cursor(antworten)

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mit(monkeypatch, antworten):
    conn = _Conn(antworten)
    monkeypatch.setattr(dashboard_routes, "get_ramicro_connection", lambda: conn)
    return conn


def test_fristen_beschriftung_kommt_aus_der_registry(monkeypatch):
    _mit(monkeypatch, [[{
        "az_roh": "158/25", "az_sb": "CO", "mandant": "Hammer",
        "kurzbezeichnung": "Hammer/Amt", "frist_datum": datetime.date(2026, 11, 25),
        "grund_code": 55, "grund_text": "", "bemerkung": "",
    }]])
    e = dashboard_routes._lade_ramicro_fristen_hart()[0]
    assert e["frist_art"] == "Beschwerde"
    assert e["az"] == "158/25CO"


def test_fristen_freitext_schlaegt_den_code(monkeypatch):
    _mit(monkeypatch, [[{
        "az_roh": "100/26", "az_sb": "AS", "mandant": "M",
        "kurzbezeichnung": "M/G", "frist_datum": datetime.date(2026, 9, 2),
        "grund_code": 55, "grund_text": "Berufungsbegruendung raus!",
        "bemerkung": "",
    }]])
    assert dashboard_routes._lade_ramicro_fristen_hart()[0]["frist_art"] == \
        "Berufungsbegruendung raus!"


def test_fristen_reichen_die_bemerkung_durch(monkeypatch):
    _mit(monkeypatch, [[{
        "az_roh": "100/26", "az_sb": "AS", "mandant": "M",
        "kurzbezeichnung": "M/G", "frist_datum": datetime.date(2026, 9, 2),
        "grund_code": 75, "grund_text": "",
        "bemerkung": "Wenn nix mehr gekommen ist, ablegen",
    }]])
    assert dashboard_routes._lade_ramicro_fristen_hart()[0]["bemerkung"] == \
        "Wenn nix mehr gekommen ist, ablegen"


def test_fristen_sql_nutzt_die_registry_codes(monkeypatch):
    conn = _mit(monkeypatch, [[]])
    dashboard_routes._lade_ramicro_fristen_hart()
    assert "IN (21, 22, 31, 46, 51, 55, 75)" in conn.cursor().sqls[0]


def test_wiedervorlage_bekommt_jetzt_eine_konkrete_beschriftung(monkeypatch):
    """Code 12 stand nicht in _RAMICRO_GRUENDE und zeigte bisher
    pauschal 'Wiedervorlage'. 169 Zeilen im Bestand."""
    _mit(monkeypatch, [[{
        "az_roh": "200/26", "az_sb": "SK", "mandant": "M",
        "kurzbezeichnung": "M/G", "datum": datetime.date(2026, 9, 1),
        "grund_code": 12, "grund_text": "", "bemerkung": "",
    }], []])
    e = dashboard_routes._lade_wiedervorlagen()["wv"][0]
    assert e["grund"] == "Zahlung Gegner"


def test_wiedervorlage_sql_schliesst_frist_und_termincodes_aus(monkeypatch):
    conn = _mit(monkeypatch, [[], []])
    dashboard_routes._lade_wiedervorlagen()
    assert "NOT IN (9, 21, 22, 31, 46, 51, 55, 58, 60, 75)" in conn.cursor().sqls[0]


def test_alte_konstanten_sind_verschwunden():
    for name in ("_RAMICRO_GRUENDE", "_FRIST_LABELS", "_TERMIN_LABELS",
                 "_FRIST_CODES", "_TERMIN_CODES", "_WV_AUSSCHLUSS",
                 "_lade_ramicro_fristen"):
        assert not hasattr(dashboard_routes, name), \
            f"{name} lebt noch -- die Registry ist nicht die einzige Quelle"
```

- [ ] **Schritt 2: Tests laufen lassen, Fehlschlag bestätigen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/test_dashboard_wv_registry.py -q
```

Erwartung: FAIL — `test_alte_konstanten_sind_verschwunden` und die Bemerkungs-Tests scheitern.

- [ ] **Schritt 3: Toten Endpunkt und alte Konstanten entfernen**

In `backend/routers/dashboard_routes.py` ersatzlos löschen:
- den Kommentarblock und `_RAMICRO_GRUENDE` (Zeilen 340–366)
- die Funktion `_lade_ramicro_fristen()` samt der Route `@dashboard_bp.route("/ramicro-fristen")` (Zeilen 368–433)
- `_TERMIN_CODES`, `_FRIST_CODES`, `_WV_AUSSCHLUSS`, `_TERMIN_LABELS`, `_FRIST_LABELS` (Zeilen 436–458)

In `frontend/src/api.js` Zeile 936 löschen:

```javascript
  ramicroFristen:  () => request("/dashboard/ramicro-fristen"),
```

Der Endpunkt hat keinen Aufrufer — `ramicroFristen` wird nirgends im Frontend verwendet.

Import am Kopf von `dashboard_routes.py` ergänzen:

```python
from backend.services.wiedervorlage_code_registry import loese_wv_grund, sql_codeliste
```

- [ ] **Schritt 4: `_lade_termine_heute()` umstellen**

Die zweite Abfrage (Codes 9/58/60) so ersetzen:

```python
            cur.execute(f"""
                SELECT TOP 30
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS termin_datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sWiedervorlagegrund   AS grund_text,
                    w.sBemerkung            AS bemerkung
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund IN ({sql_codeliste("termin")})
                  AND CAST(w.dtWiedervorlage AS DATE) BETWEEN %(heute)s AND %(morgen)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"heute": heute_s, "morgen": morgen_s})
```

Der f-String ist unbedenklich neben den `%(name)s`-Parametern: f-Strings werten `%` nicht aus, pymssql bekommt die Platzhalter unverändert.

Die Auswertung darunter ersetzen:

```python
                termin_art = loese_wv_grund(r.get("grund_text"), r.get("grund_code")).text
                bemerkung = (r.get("bemerkung") or "").strip()
                m = re.search(r"(\d{1,2}:\d{2})", bemerkung)
                uhrzeit = m.group(1) if m else None
```

und im angehängten Wörterbuch `"bemerkung": bemerkung,` ergänzen. Im ersten Ergebnisblock (Kalender-Events) `"bemerkung": "",` ergänzen, damit alle Einträge dasselbe Feld tragen.

- [ ] **Schritt 5: `_lade_ramicro_fristen_hart()` umstellen**

```python
            cur.execute(f"""
                SELECT TOP 50
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS frist_datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sWiedervorlagegrund   AS grund_text,
                    w.sBemerkung            AS bemerkung
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund IN ({sql_codeliste("frist")})
                  AND CAST(w.dtWiedervorlage AS DATE) BETWEEN %(minus365)s AND %(plus14)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage ASC
            """, {"plus14": plus14_s, "minus365": minus365_s})
```

und die Schleife:

```python
        for r in rows:
            az = _bilde_az(r)
            frist_iso, tage = _parse_datum(r.get("frist_datum"), heute_dt)

            ergebnis.append({
                "az":              az,
                "mandant":         (r.get("mandant") or "").strip(),
                "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                "frist_art":       loese_wv_grund(r.get("grund_text"),
                                                  r.get("grund_code")).text,
                "frist_datum":     frist_iso,
                "tage_bis":        tage,
                "bemerkung":       (r.get("bemerkung") or "").strip(),
            })
```

- [ ] **Schritt 6: `_lade_wiedervorlagen()` umstellen**

```python
            cur.execute(f"""
                SELECT TOP 500
                    a.sAktenNummer          AS az_roh,
                    a.sAktenSachbearbeiter  AS az_sb,
                    a.sMandant              AS mandant,
                    a.sAktenKurzBezeichnung AS kurzbezeichnung,
                    w.dtWiedervorlage       AS datum,
                    w.iWiedervorlageGrund   AS grund_code,
                    w.sWiedervorlagegrund   AS grund_text,
                    w.sBemerkung            AS bemerkung
                FROM tblAktenWiedervorlagen w
                INNER JOIN tblAkten a ON a.GUIDAkte = w.GUIDAkte
                WHERE w.iWiedervorlageGrund NOT IN ({sql_codeliste("frist", "termin")})
                  AND CAST(w.dtWiedervorlage AS DATE) BETWEEN %(minus90)s AND %(heute)s
                  AND (a.dtAblage IS NULL
                       OR CAST(a.dtAblage AS DATE) = '1899-12-30')
                ORDER BY w.dtWiedervorlage DESC
            """, {"heute": heute_s, "minus90": minus90_s})
            for r in cur.fetchall():
                az = _bilde_az(r)
                datum_iso, tage = _parse_datum(r.get("datum"), heute_dt)
                wv_eintraege.append({
                    "az":              az,
                    "mandant":         (r.get("mandant") or "").strip(),
                    "kurzbezeichnung": (r.get("kurzbezeichnung") or "").strip(),
                    "grund":           loese_wv_grund(r.get("grund_text"),
                                                      r.get("grund_code")).text,
                    "datum":           datum_iso,
                    "tage_bis":        tage,
                    "bemerkung":       (r.get("bemerkung") or "").strip(),
                    "hat_wv":          True,
                })
```

Im `ohne_wv`-Block darunter `"bemerkung": "",` ergänzen.

- [ ] **Schritt 7: Tests laufen lassen, Erfolg bestätigen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/test_dashboard_wv_registry.py backend/tests/test_dashboard_uebersicht.py -q
```

Erwartung: alle grün.

- [ ] **Schritt 8: Committen**

```bash
git add backend/routers/dashboard_routes.py backend/tests/test_dashboard_wv_registry.py frontend/src/api.js
git commit -m "refactor(dashboard): Wiedervorlagegruende aus der Registry statt aus vier Listen"
```

---

### Task 3: wiedervorlage_service.py auf die Registry umstellen

**Files:**
- Modify: `backend/ramicro/wiedervorlage_service.py:33-90` und die Stellungnahme-Abfrage
- Modify: `backend/routers/wiedervorlage_routes.py:35` und `:181`
- Test: `backend/tests/test_wiedervorlage_service_registry.py` (neu)

**Interfaces:**
- Consumes: `loese_wv_grund`, `stellungnahme_codes` aus Task 1
- Produces: keine neuen Schnittstellen. `RAMICRO_WV_GRUENDE` und `_loeseWvGrund` sind danach entfernt.

- [ ] **Schritt 1: Den fehlschlagenden Test schreiben**

Datei `backend/tests/test_wiedervorlage_service_registry.py`:

```python
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
```

- [ ] **Schritt 2: Test laufen lassen, Fehlschlag bestätigen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/test_wiedervorlage_service_registry.py -q
```

Erwartung: FAIL — `RAMICRO_WV_GRUENDE` existiert noch, `_stellungnahme_sql` nicht.

- [ ] **Schritt 3: Alte Liste und Helfer entfernen**

In `backend/ramicro/wiedervorlage_service.py` ersatzlos löschen:
- `RAMICRO_WV_GRUENDE` samt Kommentarblock (Zeilen 33–78)
- die Funktion `_loeseWvGrund` (Zeilen 80–90)

Import ergänzen:

```python
from backend.services.wiedervorlage_code_registry import sql_codeliste, stellungnahme_codes
```

- [ ] **Schritt 4: Stellungnahme-Filter aus der Registry bauen**

Neue Hilfsfunktion einfügen, wo `_loeseWvGrund` stand:

```python
def _stellungnahme_sql() -> str:
    codes = ", ".join(str(c) for c in stellungnahme_codes())
    return f"""AND (
            w.sWiedervorlagegrund LIKE '%nahme%'
            OR w.iWiedervorlageGrund IN ({codes})
        )"""
```

In `hole_faellige_wiedervorlagen` den `elif nur_stellungnahme`-Zweig ersetzen:

```python
    elif nur_stellungnahme:
        # Stellungnahmen stehen entweder als Freitext ('%nahme%') oder als
        # Katalogcode in der Registry.
        grund_sql = _stellungnahme_sql()
```

- [ ] **Schritt 5: Den Aufrufer umstellen**

In `backend/routers/wiedervorlage_routes.py` den Import in Zeile 35 ersetzen:

```python
from backend.services.wiedervorlage_code_registry import loese_wv_grund
```

und Zeile 181:

```python
            "grund":            loese_wv_grund(r.get("sWiedervorlagegrund", ""),
                                               r.get("iWiedervorlageGrund")).text,
```

- [ ] **Schritt 6: Tests laufen lassen, Erfolg bestätigen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/test_wiedervorlage_service_registry.py -q
```

Erwartung: alle grün.

- [ ] **Schritt 7: Committen**

```bash
git add backend/ramicro/wiedervorlage_service.py backend/routers/wiedervorlage_routes.py backend/tests/test_wiedervorlage_service_registry.py
git commit -m "refactor(wiedervorlage): Service liest Gruende und Stellungnahme-Codes aus der Registry"
```

---

### Task 4: Bemerkung im Frontend anzeigen

**Files:**
- Modify: `frontend/src/views/action_board/boardUi.jsx:81-90`
- Modify: `frontend/src/views/action_board/FristenKachel.jsx`
- Modify: `frontend/src/views/action_board/WiedervorlagenKachel.jsx`
- Test: `frontend/src/views/action_board/boardUi.test.jsx`, `FristenKachel.test.jsx`, `WiedervorlagenKachel.test.jsx`

**Interfaces:**
- Consumes: das Feld `bemerkung` aus Task 2
- Produces: `ZeileText` nimmt zusätzlich die Eigenschaft `zusatz` entgegen (String oder leer)

- [ ] **Schritt 1: Die fehlschlagenden Tests schreiben**

An `frontend/src/views/action_board/boardUi.test.jsx` anhängen:

```jsx
import { render, screen } from "@testing-library/react";
import { ZeileText } from "./boardUi";

describe("ZeileText Zusatzzeile", () => {
  it("zeigt die Bemerkung als dritte Zeile", () => {
    render(<ZeileText titel="100/26" meta="Fristablauf" zusatz="Deckungszusage ist da!" />);
    expect(screen.getByText("Deckungszusage ist da!")).toBeInTheDocument();
  });

  it("laesst die Zeile weg, wenn keine Bemerkung da ist", () => {
    const { container } = render(<ZeileText titel="100/26" meta="Fristablauf" zusatz="" />);
    expect(container.textContent).toBe("100/26Fristablauf");
  });
});
```

An `frontend/src/views/action_board/FristenKachel.test.jsx` anhängen:

```jsx
it("zeigt die Bemerkung zur Frist", () => {
  render(
    <FristenKachel
      status="ok"
      eintraege={[{
        az: "403/26AH", kurzbezeichnung: "Reinhard/Susnjar", mandant: "",
        frist_art: "Fristablauf", frist_datum: "2026-09-02", tage_bis: 0,
        bemerkung: "Wenn nix mehr gekommen ist, ablegen",
      }]}
      onOpenAkte={() => {}}
      onRetry={() => {}}
      retryLaeuft={false}
    />
  );
  expect(screen.getByText("Wenn nix mehr gekommen ist, ablegen")).toBeInTheDocument();
});
```

An `frontend/src/views/action_board/WiedervorlagenKachel.test.jsx` anhängen:

```jsx
it("zeigt die Bemerkung zur Wiedervorlage", () => {
  render(
    <WiedervorlagenKachel
      status="ok"
      wv={[{
        az: "200/26SK", kurzbezeichnung: "M/G", mandant: "",
        grund: "Zahlung Gegner", datum: "2026-09-01", tage_bis: 0,
        bemerkung: "Mandant hat mehrfach nachgefragt!",
      }]}
      ohne_wv={[]}
      onOpenAkte={() => {}}
      onRetry={() => {}}
      onAlleOeffnen={() => {}}
      retryLaeuft={false}
    />
  );
  expect(screen.getByText("Mandant hat mehrfach nachgefragt!")).toBeInTheDocument();
});
```

- [ ] **Schritt 2: Tests laufen lassen, Fehlschlag bestätigen**

```
cd frontend && npm test -- boardUi FristenKachel WiedervorlagenKachel
```

Erwartung: FAIL — die Bemerkungstexte werden nicht gefunden.

- [ ] **Schritt 3: `ZeileText` um die dritte Zeile erweitern**

In `frontend/src/views/action_board/boardUi.jsx`:

```jsx
export function ZeileText({ titel, meta, metaFarbe, zusatz }) {
  return (
    <span style={{ display: "block", minWidth: 0 }}>
      <span style={{ display: "block", fontSize: T.textSm, fontWeight: 500, color: T.text, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{titel}</span>
      {meta && (
        <span style={{ display: "block", fontSize: T.textXs, color: metaFarbe || T.textMuted, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: 1 }}>{meta}</span>
      )}
      {zusatz && (
        <span style={{ display: "block", fontSize: T.textXs, color: T.textMuted, fontStyle: "italic", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", marginTop: 1 }}>{zusatz}</span>
      )}
    </span>
  );
}
```

- [ ] **Schritt 4: Die beiden Kacheln die Bemerkung übergeben lassen**

In `FristenKachel.jsx` bei **beiden** `ZeileText`-Aufrufen (Abschnitt „Handlungsbedarf" und „Demnächst") ergänzen:

```jsx
                        zusatz={e.bemerkung}
```

In `WiedervorlagenKachel.jsx` in `wvZeile` ergänzen:

```jsx
            zusatz={e.bemerkung}
```

- [ ] **Schritt 5: Tests laufen lassen, Erfolg bestätigen**

```
cd frontend && npm test
```

Erwartung: alle grün.

- [ ] **Schritt 6: Committen**

```bash
git add frontend/src/views/action_board/
git commit -m "feat(tagesuebersicht): Bemerkung zur Wiedervorlage und zur Frist anzeigen"
```

---

### Task 5: Guard-Test, Vollsuite und Dokumentation

**Files:**
- Create: `backend/tests/test_wiedervorlage_registry_guard.py`
- Modify: `docs/DECISIONS.md`, `docs/CHANGELOG.md`, `docs/TODO.md`

**Interfaces:**
- Consumes: alles aus den Tasks 1–4
- Produces: keine

- [ ] **Schritt 1: Den Guard-Test schreiben**

Der Test verhindert, dass jemand später wieder eine Codeliste neben die Registry setzt. Datei `backend/tests/test_wiedervorlage_registry_guard.py`:

```python
"""
Statischer Guard: das Feld iWiedervorlageGrund darf nur noch in der
Registry ausgelegt werden.

Bis 2026-09-01 taten das vier Konstanten und drei SQL-Literale. Der Test
prueft die Quelltexte, nicht das Laufzeitverhalten -- eine neue Liste faellt
so sofort auf, auch wenn sie noch von keinem Test beruehrt wird.
"""

import os
import re

WURZEL = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

ERLAUBT = {
    os.path.join("services", "wiedervorlage_code_registry.py"),
    os.path.join("registry", "wiedervorlage_codes.yaml"),
}

MUSTER_SQL = re.compile(r"iWiedervorlageGrund\s+(?:NOT\s+)?IN\s*\(\s*\d")


def _quelldateien():
    for ordner, _, dateien in os.walk(WURZEL):
        if "tests" in ordner or "__pycache__" in ordner:
            continue
        for d in dateien:
            if d.endswith(".py"):
                yield os.path.join(ordner, d)


def test_keine_hartcodierte_codeliste_im_sql():
    treffer = []
    for pfad in _quelldateien():
        rel = os.path.relpath(pfad, WURZEL)
        if rel in ERLAUBT:
            continue
        with open(pfad, encoding="utf-8") as fh:
            for nr, zeile in enumerate(fh, 1):
                if MUSTER_SQL.search(zeile):
                    treffer.append(f"{rel}:{nr}")
    assert treffer == [], (
        "Codeliste direkt im SQL statt aus sql_codeliste(): "
        + ", ".join(treffer))


def test_offener_pruefstand_ist_sichtbar():
    """Kein Fehlschlag, nur ein Zaehler: solange Bezeichnungen unverifiziert
    sind, soll das im Testlauf sichtbar bleiben."""
    from backend.services.wiedervorlage_code_registry import lade_wv_codes
    r = lade_wv_codes()
    offen = [c for c, e in r.codes.items() if not e.get("verifiziert")]
    if offen:
        print(f"\nHINWEIS: {len(offen)} von {len(r.codes)} Wiedervorlagecodes "
              f"sind noch nicht gegen RA-MICRO verifiziert: {sorted(offen)}")
```

- [ ] **Schritt 2: Guard-Test laufen lassen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/test_wiedervorlage_registry_guard.py -q -s
```

Erwartung: grün, mit dem Hinweis auf die noch offenen Codes.

- [ ] **Schritt 3: Vollsuite laufen lassen**

```
JWT_SECRET_KEY='test-secret-key-minimum-32-chars!!' python -m pytest backend/tests/ -q
cd frontend && npm test
```

Erwartung: keine neuen Fehlschläge gegenüber dem Stand vor Task 1.

- [ ] **Schritt 4: Dokumentation nachziehen**

In `docs/DECISIONS.md` ergänzen:

> **Wiedervorlagegrund: Freitext ist die Quelle, die Nummer nur der Notnagel** (2026-09-01)
> RA-MICRO speichert den Wiedervorlagegrund in zwei Regimen: eingebaute Codes 5–99 ohne Text (958 von 1.610 Zeilen) und laufende IDs ab 63912 mit Freitext. Der Katalogtext der eingebauten Gründe steht in keiner der acht Serverdatenbanken. Deshalb: `sWiedervorlagegrund` hat immer Vorrang, `backend/registry/wiedervorlage_codes.yaml` springt nur bei leerem Text ein. Die Registry wird nicht gepflegt — neue Gründe der Kanzlei bekommen eine Nummer ab 63912 und bringen ihren Text mit.
> `sBemerkung` (optional, ~10 % der Zeilen) wird als Zusatzzeile angezeigt.
> Die Bezeichnungen der eingebauten Codes stammen aus einer frühen Session und sind bis zur Prüfung durch RA Schatz mit `verifiziert: false` gekennzeichnet.

In `docs/CHANGELOG.md` den Umbau protokollieren (vier Bezeichnungslisten und vier Codelisten zusammengeführt, toter Endpunkt `/dashboard/ramicro-fristen` entfernt, `sBemerkung` neu angezeigt).

In `docs/TODO.md` unter „Unklar" aufnehmen:

> **Echte RA-MICRO-Fristen** — liegen nicht im SQL Server (alle acht Datenbanken geprüft, `raKalender.dbo.Deadlist` existiert und ist leer). Offen: In welchem RA-MICRO-Modul werden sie geführt, und lässt sich die Synchronisation nach `Deadlist` einschalten?
> **Freitext-Wiedervorlagen mit Fristcharakter** — 652 Einträge, darunter „Anspruchsbegründung fertigen! DRINGEND!". Landen in der Wiedervorlagen-Kachel. Erkennung offen.

- [ ] **Schritt 5: Committen**

```bash
git add backend/tests/test_wiedervorlage_registry_guard.py docs/DECISIONS.md docs/CHANGELOG.md docs/TODO.md
git commit -m "test(wiedervorlage): Guard gegen neue Codelisten + Dokumentation des Umbaus"
```

---

## Abnahme im Betrieb

Nach Task 5 und **nach** der Verifikation aus Task 0:

- [ ] Tagesübersicht im Browser öffnen (`http://localhost:5173`)
- [ ] Fristen-Kachel: Beschriftungen stimmen mit RA-MICRO überein
- [ ] Wiedervorlagen-Kachel: die bisher pauschalen „Wiedervorlage"-Zeilen tragen jetzt konkrete Gründe
- [ ] Bemerkungen erscheinen als kursive dritte Zeile, wo hinterlegt
- [ ] Stichprobe gegen RA-MICRO: eine Akte je Kachel öffnen und den Grund vergleichen
