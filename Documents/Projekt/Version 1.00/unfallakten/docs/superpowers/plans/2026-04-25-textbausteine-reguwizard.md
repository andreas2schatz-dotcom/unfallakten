# Textbaustein-Import + ReguWizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 19 Word-Dateien (je eine pro Kürzungsart) in die DB importieren, Platzhalter `<XYZ>` automatisch aus Aktendaten ersetzen, und einen geführten Wizard zur Erstellung einer Stellungnahme auf Abrechnungsschreiben bauen.

**Architecture:** Import-Script liest Dateien per `python-docx`, schreibt per SQL direkt in SQLite. Replacement-Engine (`ersetze_platzhalter`) wird in `stellungnahme_service.py` aufgerufen. ReguWizard in `RegulierungSection.jsx` ruft einen neuen Vorschau-Endpoint auf, sammelt Anwalt-Edits und übergibt sie beim Generieren.

**Tech Stack:** Python/python-docx (Import), Flask/SQLite (Backend), React/JSX (Wizard-UI), python-docx/OOXML (Word-Export)

**Hinweis PRD-14:** Bereits erledigt (Commit 0e558d9). Nicht nochmals anfassen.

**Kritisches Mapping:** Nach Task 1 (Dry-Run) werden alle `<PLATZHALTER>` mit dem Anwalt besprochen. Task 2 (Replacement-Engine) erst nach Freigabe des Mappings beginnen.

---

## Datei-Übersicht

| Datei | Aktion | Zweck |
|---|---|---|
| `tools/import_textbausteine.py` | Erstellen | Einmal-Import der 19 Word-Dateien |
| `tools/textbausteine/` | Erstellen (leer) | Ordner für Word-Dateien |
| `backend/word/stellungnahme_service.py` | Erweitern | `ersetze_platzhalter()`, `_baue_kontext()`, `_aggregiere_kuerzungen()`, `custom_texte`-Parameter |
| `backend/routers/stellungnahme_routes.py` | Erweitern | GET `/vorschau`-Endpoint, `custom_texte` aus POST-Body |
| `frontend/src/api.js` | Erweitern | `stellungnahme.vorschau(az)` |
| `frontend/src/sections/RegulierungSection.jsx` | Erweitern | `<ReguWizard>`-Komponente |
| `frontend/src/views/KuerzungskatalogView.jsx` | Erweitern | Textbaustein-Preview in Liste |
| `backend/tests/test_prd27.py` | Erstellen | Unit-Tests Replacement-Engine + Vorschau-Endpoint |

---

## Task 1: Import-Script (Dry-Run zuerst)

**Files:**
- Create: `tools/import_textbausteine.py`
- Create: `tools/textbausteine/.gitkeep`

- [ ] **Schritt 1: Ordnerstruktur anlegen**

```bash
mkdir -p "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten\tools\textbausteine"
```

- [ ] **Schritt 2: Script schreiben**

Erstelle `tools/import_textbausteine.py`:

```python
"""
import_textbausteine.py
========================
Liest 19 Word-Dateien aus ./textbausteine/ und schreibt den Text in
kuerzungsarten.textbaustein.

Verwendung:
    python import_textbausteine.py            # Dry-Run: zeigt Platzhalter + Mapping
    python import_textbausteine.py --write    # Schreibt in DB

Voraussetzung: pip install python-docx
DB-Pfad wird aus Umgebungsvariable DB_PATH gelesen oder Standard verwendet.
"""

import argparse
import os
import re
import sqlite3
import sys
from pathlib import Path

try:
    from docx import Document
except ImportError:
    sys.exit("python-docx nicht installiert. Bitte: pip install python-docx")

# ── Pfade ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).parent
DOCX_DIR    = SCRIPT_DIR / "textbausteine"
DEFAULT_DB  = SCRIPT_DIR.parent / "backend" / "data" / "unfallakten.db"
DB_PATH     = Path(os.environ.get("DB_PATH", DEFAULT_DB))

# ── Mapping: Dateiname (ohne .docx) → kuerzungsarten.id ──────────────────────
# Wird nach dem ersten Dry-Run gemeinsam mit dem Anwalt ausgefüllt.
# Schlüssel: Dateiname ohne Extension (Groß-/Kleinschreibung egal)
# Wert: id aus kuerzungsarten-Tabelle (1-19)

MAPPING: dict[str, int] = {
    # Beispiele – nach Dry-Run anpassen:
    # "stundenverrechnungssaetze": 1,
    # "nutzungsausfall":           2,
}


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def _lese_docx(pfad: Path) -> str:
    """Extrahiert den vollständigen Text aus einer Word-Datei."""
    doc = Document(str(pfad))
    absaetze = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            absaetze.append(text)
    return "\n\n".join(absaetze)


def _finde_platzhalter(text: str) -> list[str]:
    """Gibt alle <PLATZHALTER> im Text zurück (ohne Duplikate, sortiert)."""
    gefunden = re.findall(r"<([A-Z_]+)>", text)
    return sorted(set(gefunden))


def _lade_kuerzungsarten(conn: sqlite3.Connection) -> dict[int, str]:
    """Gibt {id: bezeichnung} für alle Kürzungsarten zurück."""
    rows = conn.execute("SELECT id, bezeichnung FROM kuerzungsarten ORDER BY id").fetchall()
    return {r[0]: r[1] for r in rows}


# ── Haupt-Logik ───────────────────────────────────────────────────────────────

def run(schreiben: bool) -> None:
    if not DOCX_DIR.exists():
        sys.exit(f"Ordner nicht gefunden: {DOCX_DIR}")

    dateien = sorted(DOCX_DIR.glob("*.docx"))
    if not dateien:
        sys.exit(f"Keine .docx-Dateien in {DOCX_DIR}")

    if not DB_PATH.exists():
        sys.exit(f"Datenbank nicht gefunden: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        kuerzungsarten = _lade_kuerzungsarten(conn)

        print(f"\n{'='*60}")
        print(f"Modus: {'SCHREIBEN' if schreiben else 'DRY-RUN (nur Analyse)'}")
        print(f"Datenbank: {DB_PATH}")
        print(f"Dateien gefunden: {len(dateien)}")
        print(f"{'='*60}\n")

        alle_platzhalter: set[str] = set()
        nicht_gemappt: list[str] = []

        for pfad in dateien:
            name_key = pfad.stem.lower()
            kuerzungsart_id = MAPPING.get(name_key) or MAPPING.get(pfad.stem)
            text = _lese_docx(pfad)
            platzhalter = _finde_platzhalter(text)
            alle_platzhalter.update(platzhalter)

            print(f"📄 {pfad.name}")
            print(f"   Mapping → ", end="")

            if kuerzungsart_id:
                bezeichnung = kuerzungsarten.get(kuerzungsart_id, "???")
                print(f"ID {kuerzungsart_id}: {bezeichnung}")
            else:
                print("KEIN MAPPING (→ in MAPPING-Dict eintragen)")
                nicht_gemappt.append(pfad.name)

            print(f"   Länge: {len(text)} Zeichen")
            if platzhalter:
                print(f"   Platzhalter: {', '.join(f'<{p}>' for p in platzhalter)}")
            else:
                print("   Platzhalter: keine")

            if schreiben and kuerzungsart_id:
                conn.execute(
                    "UPDATE kuerzungsarten SET textbaustein = ? WHERE id = ?",
                    (text, kuerzungsart_id)
                )
                print("   ✅ Geschrieben.")
            print()

        if schreiben:
            conn.commit()

        print(f"{'='*60}")
        print(f"ALLE GEFUNDENEN PLATZHALTER:")
        for p in sorted(alle_platzhalter):
            print(f"  <{p}>")

        if nicht_gemappt:
            print(f"\n⚠️  NICHT GEMAPPT ({len(nicht_gemappt)} Dateien):")
            for f in nicht_gemappt:
                print(f"  {f}")
            print("→ Bitte MAPPING-Dict im Script ergänzen und erneut ausführen.")

        print(f"{'='*60}\n")

    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Textbaustein-Import für Kürzungsarten")
    parser.add_argument("--write", action="store_true",
                        help="Werte in DB schreiben (ohne Flag: nur Dry-Run)")
    args = parser.parse_args()
    run(schreiben=args.write)
```

- [ ] **Schritt 3: `.gitkeep` für den leeren Ordner**

```bash
echo "" > "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten\tools\textbausteine\.gitkeep"
```

- [ ] **Schritt 4: Word-Dateien in den Ordner kopieren**

Kopieren Sie Ihre 19 `.docx`-Dateien nach `tools/textbausteine/`.

- [ ] **Schritt 5: Dry-Run ausführen**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten"
pip install python-docx
python tools/import_textbausteine.py
```

Erwartete Ausgabe: Liste aller Dateien + alle gefundenen `<PLATZHALTER>`.
**→ STOP. Platzhalter-Mapping mit Anwalt besprechen, bevor weitergemacht wird.**

- [ ] **Schritt 6: MAPPING-Dict befüllen + erneut Dry-Run**

Im Script `MAPPING`-Dict mit echten Dateinamen → IDs befüllen.
Nochmals ohne `--write` prüfen, ob alle 19 Dateien grün sind.

- [ ] **Schritt 7: Import schreiben**

```bash
python tools/import_textbausteine.py --write
```

Erwartete Ausgabe: 19× `✅ Geschrieben.`

- [ ] **Schritt 8: Commit**

```bash
git add tools/import_textbausteine.py tools/textbausteine/.gitkeep
git commit -m "feat(prd02a): Import-Script fuer Textbausteine (python-docx)"
```

---

## Task 2: Replacement-Engine (NACH Mapping-Review)

**Files:**
- Modify: `backend/word/stellungnahme_service.py`

> **Voraussetzung:** Platzhalter-Mapping aus Task 1 ist mit dem Anwalt besprochen und festgelegt.

- [ ] **Schritt 1: Test schreiben**

Erstelle `backend/tests/test_prd27.py`:

```python
"""Tests: PRD-27 Replacement-Engine + Vorschau-Endpoint"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


class TestErsetzePlatzhalter(unittest.TestCase):

    def setUp(self):
        from backend.word.stellungnahme_service import ersetze_platzhalter
        self.fn = ersetze_platzhalter

    def test_einfache_ersetzung(self):
        text = "Sehr geehrte Damen und Herren von <VERSICHERER>,"
        kontext = {"VERSICHERER": "Allianz AG"}
        result = self.fn(text, kontext)
        self.assertEqual(result, "Sehr geehrte Damen und Herren von Allianz AG,")

    def test_mehrere_platzhalter(self):
        text = "Mandant: <MANDANT>, AZ: <AZ>"
        kontext = {"MANDANT": "Max Mustermann", "AZ": "31/21"}
        result = self.fn(text, kontext)
        self.assertEqual(result, "Mandant: Max Mustermann, AZ: 31/21")

    def test_unbekannter_platzhalter_wird_markiert(self):
        text = "Wert: <UNBEKANNT>"
        result = self.fn(text, {})
        self.assertIn("[FEHLT: <UNBEKANNT>]", result)

    def test_leerer_text(self):
        self.assertIsNone(self.fn(None, {"X": "y"}))

    def test_leerer_wert_bleibt_leer(self):
        text = "Hallo <MANDANT>"
        result = self.fn(text, {"MANDANT": ""})
        self.assertEqual(result, "Hallo ")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Schritt 2: Test ausführen (muss fehlschlagen)**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten"
python -m pytest backend/tests/test_prd27.py::TestErsetzePlatzhalter -v
```

Erwartete Ausgabe: `ImportError` oder `AttributeError` (Funktion existiert noch nicht).

- [ ] **Schritt 3: `ersetze_platzhalter()` und `_baue_kontext()` in `stellungnahme_service.py` einfügen**

Nach der bestehenden `_datum_deutsch()`-Funktion (~Zeile 62) einfügen:

```python
# ── Textbaustein-Replacement ──────────────────────────────────────────────────

def ersetze_platzhalter(text: str | None, kontext: dict) -> str | None:
    """
    Ersetzt <PLATZHALTER> im Text mit Werten aus kontext.
    Unbekannte Platzhalter werden als [FEHLT: <XYZ>] markiert.
    """
    if not text:
        return text
    for key, value in kontext.items():
        text = text.replace(f"<{key}>", str(value) if value else "")
    # Verbleibende unbekannte Platzhalter markieren
    text = re.sub(r"<([A-Z_]+)>", r"[FEHLT: <\1>]", text)
    return text


def _baue_kontext(az: str, akte_daten, beteiligte: list) -> dict:
    """
    Baut das Platzhalter-Kontext-Dict aus Aktendaten.
    Mapping wird gemeinsam mit dem Anwalt nach Task 1 Dry-Run festgelegt.
    """
    mandant = next(
        (b for b in (beteiligte or []) if getattr(b, "rolle", "") == "mandant"),
        None,
    )
    versicherung = next(
        (b for b in (beteiligte or [])
         if getattr(b, "rolle", "") in ("ghpv", "versicherung", "haftpflicht")),
        None,
    )

    def _name(b) -> str:
        if not b:
            return ""
        vn = getattr(b, "vorname", "") or ""
        nn = getattr(b, "name", "") or getattr(b, "nachname", "") or ""
        return f"{vn} {nn}".strip() or nn

    return {
        "MANDANT":     _name(mandant),
        "AZ":          az,
        "VERSICHERER": _name(versicherung),
        "DATUM":       date.today().strftime("%d.%m.%Y"),
        "KFZ":         getattr(akte_daten, "kfz_kennzeichen", "") or "",
        # Weitere Einträge nach Mapping-Review aus Task 1 ergänzen
    }
```

- [ ] **Schritt 4: `_aggregiere_kuerzungen()` extrahieren**

Den Aggregations-Block (~Zeile 389–440 in `generiere_stellungnahme()`) in eine eigene Funktion auslagern. In `generiere_stellungnahme()` ersetzen durch Aufruf.

Neue Funktion nach `_baue_kontext()`:

```python
def _aggregiere_kuerzungen(abrechnungen: list) -> tuple[list, float]:
    """
    Aggregiert Kürzungspositionen über alle Abrechnungen.
    Gibt (kuerzungen_liste, restbetrag) zurück.
    Jeder Eintrag hat: bezeichnung, label, standard_gegenargument,
                       kuerzung_gesamt, _gruppe_key
    """
    kuerzung_by_art: dict = {}
    restbetrag = 0.0

    for ab in (abrechnungen or []):
        positionen = (getattr(ab, "positionen", None)
                      or (ab.get("positionen") if isinstance(ab, dict) else None)
                      or [])
        for pos in positionen:
            pos_dict = (pos if isinstance(pos, dict)
                        else vars(pos) if hasattr(pos, "__dict__") else {})
            betrag_gef = float(pos_dict.get("betrag_gefordert") or 0)
            betrag_reg = float(pos_dict.get("betrag_reguliert") or 0)
            kuerzung   = round(betrag_gef - betrag_reg, 2)
            if kuerzung <= 0.005:
                continue

            restbetrag += kuerzung

            ka_id  = pos_dict.get("kuerzungsart_id")
            ka_bez = pos_dict.get("kuerzungsart_bezeichnung") or ""
            ka_arg = (
                pos_dict.get("textbaustein")
                or pos_dict.get("kuerzungsart_textbaustein")
                or pos_dict.get("standard_gegenargument")
                or pos_dict.get("kuerzungsart_standard_gegenargument")
                or ""
            )
            pos_key   = pos_dict.get("position_key") or "sonstiges"
            pos_label = pos_dict.get("position_label") or pos_key.replace("_", " ").title()
            gruppe_key = f"ka_{ka_id}" if ka_id else f"pos_{pos_key}"

            if gruppe_key not in kuerzung_by_art:
                kuerzung_by_art[gruppe_key] = {
                    "_gruppe_key":           gruppe_key,
                    "bezeichnung":           ka_bez or pos_label,
                    "label":                 ka_bez or pos_label,
                    "standard_gegenargument": ka_arg,
                    "kuerzung_gesamt":        0.0,
                    "positionen":             [],
                }
            kuerzung_by_art[gruppe_key]["kuerzung_gesamt"] += kuerzung
            kuerzung_by_art[gruppe_key]["positionen"].append(pos_label)

    kuerzungen = list(kuerzung_by_art.values())
    for k in kuerzungen:
        posis = list(dict.fromkeys(k["positionen"]))
        if len(posis) > 1:
            k["label"] = k["bezeichnung"] + f" ({', '.join(posis)})"

    return kuerzungen, restbetrag
```

- [ ] **Schritt 5: `generiere_stellungnahme()` auf neue Funktionen umstellen**

Signatur erweitern:

```python
def generiere_stellungnahme(
    az: str,
    akte_daten,
    beteiligte: list,
    abrechnungen: list,
    custom_texte: dict | None = None,   # gruppe_key → Anwalt-editierter Text
) -> bytes:
```

Den bisherigen Aggregations-Block (~Zeile 389–440) ersetzen durch:

```python
kuerzungen, restbetrag = _aggregiere_kuerzungen(abrechnungen)
kontext = _baue_kontext(az, akte_daten, beteiligte)
```

Den Argument-Block in `_xml_kuerzungstabelle()` erweitern. Die Funktion bekommt einen zusätzlichen Parameter `kontext` und `custom_texte`:

```python
def _xml_kuerzungstabelle(
    kuerzungen: list,
    kontext: dict,
    custom_texte: dict | None = None,
) -> str:
    # ...
    for k in kuerzungen:
        betrag = float(k.get("kuerzung_gesamt") or 0)
        gesamt_kuerzung += betrag
        gruppe_key = k.get("_gruppe_key", "")
        raw_text = (
            (custom_texte or {}).get(gruppe_key)
            or k.get("standard_gegenargument")
            or "Die Kürzung ist nicht gerechtfertigt."
        )
        argument = ersetze_platzhalter(raw_text, kontext)
        # ... rest bleibt gleich
```

Aufruf in `generiere_stellungnahme()` anpassen:

```python
xml_tabelle = _xml_kuerzungstabelle(kuerzungen, kontext, custom_texte)
```

- [ ] **Schritt 6: Tests ausführen (müssen bestehen)**

```bash
python -m pytest backend/tests/test_prd27.py::TestErsetzePlatzhalter -v
```

Erwartete Ausgabe: 5 Tests PASSED.

- [ ] **Schritt 7: Commit**

```bash
git add backend/word/stellungnahme_service.py backend/tests/test_prd27.py
git commit -m "feat(prd02b): Replacement-Engine ersetze_platzhalter() + _aggregiere_kuerzungen() refactor"
```

---

## Task 3: Vorschau-Endpoint (GET)

**Files:**
- Modify: `backend/routers/stellungnahme_routes.py`
- Modify: `backend/tests/test_prd27.py`

- [ ] **Schritt 1: Test für Vorschau-Endpoint schreiben**

In `backend/tests/test_prd27.py` ergänzen:

```python
import tempfile
import json


class TestVorschauEndpoint(unittest.TestCase):
    """Integration-Test: GET /akten/<az>/stellungnahme/vorschau"""

    def setUp(self):
        tmp = tempfile.mkdtemp()
        db_path = os.path.join(tmp, "test_prd27.db")
        os.environ["DB_PATH"] = db_path

        import importlib
        import backend.db.database as db_mod
        import backend.db.schema_manager as sm_mod
        importlib.reload(db_mod)
        importlib.reload(sm_mod)

        with db_mod.get_connection() as conn:
            sm_mod.initialisiere_schema(conn)

        import backend.app as app_mod
        importlib.reload(app_mod)
        app = app_mod.erstelle_app()
        app.config["TESTING"] = True
        self.client = app.test_client()
        self.db_mod = db_mod

    def _login(self) -> dict:
        r = self.client.post("/auth/login",
                             json={"benutzername": "admin", "passwort": "admin123"})
        return json.loads(r.data)

    def test_vorschau_ohne_akte_gibt_404(self):
        token = self._login()["access_token"]
        r = self.client.get(
            "/akten/NICHT_VORHANDEN/stellungnahme/vorschau",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 404)
```

- [ ] **Schritt 2: Test ausführen (muss fehlschlagen)**

```bash
python -m pytest backend/tests/test_prd27.py::TestVorschauEndpoint -v
```

Erwartete Ausgabe: FAIL (Route existiert noch nicht).

- [ ] **Schritt 3: GET-Route in `stellungnahme_routes.py` ergänzen**

Nach der bestehenden `generiere()`-Route einfügen:

```python
@stellungnahme_bp.route("/<path:akte_id>/stellungnahme/vorschau", methods=["GET"])
def vorschau(akte_id: str):
    """
    Gibt die aggregierten Kürzungspositionen mit vorausgefüllten Textbausteinen zurück.
    Wird vom ReguWizard verwendet, um die Wizard-Steps zu befüllen.

    Response: {
      "positionen": [
        {
          "_gruppe_key": "ka_5",
          "bezeichnung": "Stundenverrechnungssätze",
          "kuerzung_gesamt": 150.0,
          "textbaustein_vorschlag": "Die vorgenommene Kürzung ..."
        }
      ]
    }
    """
    from ..word.stellungnahme_service import (
        _aggregiere_kuerzungen, _baue_kontext, ersetze_platzhalter
    )

    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen

    beteiligte = hole_beteiligte_by_akte(az)
    alle_abrechnungen = hole_abrechnungsschreiben_by_akte(az)
    if not alle_abrechnungen:
        return jsonify({"positionen": []})

    kuerzungen, _ = _aggregiere_kuerzungen(alle_abrechnungen)
    kontext = _baue_kontext(az, akte, beteiligte)

    positionen_out = []
    for k in kuerzungen:
        raw = k.get("standard_gegenargument") or "Die Kürzung ist nicht gerechtfertigt."
        positionen_out.append({
            "_gruppe_key":          k.get("_gruppe_key", ""),
            "bezeichnung":          k.get("bezeichnung", ""),
            "label":                k.get("label", ""),
            "kuerzung_gesamt":      k.get("kuerzung_gesamt", 0.0),
            "textbaustein_vorschlag": ersetze_platzhalter(raw, kontext),
        })

    return jsonify({"positionen": positionen_out})
```

Außerdem: `custom_texte` aus POST-Body in `generiere()` übergeben:

```python
# In der bestehenden generiere()-Funktion, nach body-Parsing (~Zeile 51):
custom_texte = body.get("custom_texte") or {}   # gruppe_key → text

# Beim Aufruf generiere_stellungnahme():
docx_bytes = generiere_stellungnahme(
    az=az,
    akte_daten=akte,
    beteiligte=beteiligte,
    abrechnungen=abrechnungen,
    custom_texte=custom_texte,
)
```

- [ ] **Schritt 4: Tests ausführen**

```bash
python -m pytest backend/tests/test_prd27.py -v
```

Erwartete Ausgabe: alle Tests PASSED (inkl. `test_vorschau_ohne_akte_gibt_404`).

- [ ] **Schritt 5: Commit**

```bash
git add backend/routers/stellungnahme_routes.py backend/tests/test_prd27.py
git commit -m "feat(prd27a): GET /stellungnahme/vorschau + custom_texte in POST-Body"
```

---

## Task 4: Frontend api.js erweitern

**Files:**
- Modify: `frontend/src/api.js`

- [ ] **Schritt 1: `vorschau`-Methode hinzufügen**

In `api.js` das bestehende `stellungnahme`-Objekt suchen (hat `generieren`-Methode, ~Zeile 800).
Vor `generieren` die neue Methode einfügen:

```javascript
vorschau: async (az) => {
  const token = tokenStore.getAccess();
  const res = await fetch(`${API_BASE}/akten/${az}/stellungnahme/vorschau`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Vorschau fehlgeschlagen: ${res.status}`);
  return res.json();
},
```

`generieren` so erweitern, dass `custom_texte` mitgeschickt werden kann:

```javascript
generieren: async (az, { abrechnungsschreiben_id = null, custom_texte = {} } = {}) => {
  const token = tokenStore.getAccess();
  const res = await fetch(`${API_BASE}/akten/${az}/stellungnahme/generieren`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ abrechnungsschreiben_id, custom_texte }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.fehler || `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const cd   = res.headers.get('Content-Disposition') || '';
  const m    = cd.match(/filename="?([^"]+)"?/);
  const sicheresAz = az.replace(/\//g, '-');
  _triggerDownload(blob, m ? m[1] : `${sicheresAz}_stellungnahme.docx`);
},
```

- [ ] **Schritt 2: Commit**

```bash
git add frontend/src/api.js
git commit -m "feat(prd27b): api.js stellungnahme.vorschau() + custom_texte in generieren()"
```

---

## Task 5: ReguWizard UI

**Files:**
- Modify: `frontend/src/sections/RegulierungSection.jsx`

- [ ] **Schritt 1: `ReguWizard`-Komponente am Ende der Datei vor dem `export default` einfügen**

```jsx
// ── ReguWizard ────────────────────────────────────────────────────────────────

function ReguWizard({ az, onClose }) {
  const [step, setStep]             = useState(0);
  const [positionen, setPositionen] = useState([]);
  const [texte, setTexte]           = useState({});   // gruppe_key → text
  const [frist, setFrist]           = useState(14);
  const [laden, setLaden]           = useState(true);
  const [generieren, setGenerieren] = useState(false);
  const [fehler, setFehler]         = useState("");

  useEffect(() => {
    // apiStellungnahme ist bereits am Anfang von RegulierungSection.jsx importiert
    apiStellungnahme.vorschau(az)
      .then(data => {
        const posis = data.positionen || [];
        setPositionen(posis);
        const initTexte = {};
        posis.forEach(p => { initTexte[p._gruppe_key] = p.textbaustein_vorschlag || ""; });
        setTexte(initTexte);
      })
      .catch(e => setFehler(e.message))
      .finally(() => setLaden(false));
  }, [az]);

  const STEPS = [
    "start",
    ...positionen.map((_, i) => `pos_${i}`),
    "frist",
    "generieren",
  ];
  const total = STEPS.length;
  const pos_steps_count = positionen.length;

  async function handleGenerieren() {
    setGenerieren(true);
    try {
      await apiStellungnahme.generieren(az, { custom_texte: texte });
      onClose();
    } catch (e) {
      setFehler(e.message);
      setGenerieren(false);
    }
  }

  if (laden) return (
    <div style={{ padding: "2rem", textAlign: "center" }}>Lade Kürzungspositionen…</div>
  );

  if (fehler) return (
    <div style={{ padding: "2rem", color: "red" }}>
      <strong>Fehler:</strong> {fehler}
      <br /><button onClick={onClose}>Schließen</button>
    </div>
  );

  // Step 0: Info
  if (step === 0) return (
    <div style={{ padding: "1.5rem" }}>
      <h3 style={{ marginTop: 0 }}>Stellungnahme erstellen</h3>
      <p>
        Für diese Akte wurden <strong>{pos_steps_count}</strong> Kürzungsposition(en) gefunden.
        Der Assistent führt Sie durch jede Position und schlägt einen Gegenargument-Text vor.
      </p>
      {pos_steps_count === 0 && (
        <p style={{ color: "orange" }}>⚠️ Keine Kürzungspositionen gefunden.</p>
      )}
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        <button onClick={onClose}>Abbrechen</button>
        <button
          onClick={() => setStep(1)}
          disabled={pos_steps_count === 0}
          style={{ fontWeight: "bold" }}
        >
          Weiter →
        </button>
      </div>
    </div>
  );

  // Steps 1..pos_steps_count: Kürzungspositionen
  if (step >= 1 && step <= pos_steps_count) {
    const pos = positionen[step - 1];
    const key = pos._gruppe_key;
    return (
      <div style={{ padding: "1.5rem" }}>
        <div style={{ fontSize: "0.8rem", color: "#888", marginBottom: "0.5rem" }}>
          Position {step} von {pos_steps_count}
        </div>
        <h3 style={{ marginTop: 0 }}>{pos.label || pos.bezeichnung}</h3>
        <div style={{ marginBottom: "0.5rem" }}>
          Kürzungsbetrag: <strong>−{Number(pos.kuerzung_gesamt).toFixed(2).replace(".", ",")} €</strong>
        </div>
        <label style={{ display: "block", marginBottom: "0.25rem", fontWeight: "bold" }}>
          Gegenargument:
        </label>
        <textarea
          rows={8}
          style={{ width: "100%", fontFamily: "inherit", fontSize: "0.9rem", padding: "0.5rem" }}
          value={texte[key] || ""}
          onChange={e => setTexte(prev => ({ ...prev, [key]: e.target.value }))}
        />
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
          <button onClick={() => setStep(s => s - 1)}>← Zurück</button>
          <button onClick={() => setTexte(prev => ({ ...prev, [key]: "" }))}>
            Überspringen
          </button>
          <button
            onClick={() => setStep(s => s + 1)}
            style={{ fontWeight: "bold" }}
          >
            {step < pos_steps_count ? "Weiter →" : "Zur Frist →"}
          </button>
        </div>
      </div>
    );
  }

  // Frist-Step
  if (step === pos_steps_count + 1) return (
    <div style={{ padding: "1.5rem" }}>
      <h3 style={{ marginTop: 0 }}>Zahlungsfrist</h3>
      <label>
        Frist in Tagen ab heute:{" "}
        <input
          type="number"
          min={1}
          max={90}
          value={frist}
          onChange={e => setFrist(Number(e.target.value))}
          style={{ width: "4rem", textAlign: "center" }}
        />
      </label>
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        <button onClick={() => setStep(s => s - 1)}>← Zurück</button>
        <button onClick={() => setStep(s => s + 1)} style={{ fontWeight: "bold" }}>
          Zusammenfassung →
        </button>
      </div>
    </div>
  );

  // Generieren-Step
  return (
    <div style={{ padding: "1.5rem" }}>
      <h3 style={{ marginTop: 0 }}>Zusammenfassung</h3>
      <p>
        <strong>{positionen.filter(p => texte[p._gruppe_key]).length}</strong> von{" "}
        {pos_steps_count} Positionen mit Gegenargument. Frist: <strong>{frist} Tage</strong>.
      </p>
      {fehler && <div style={{ color: "red", marginBottom: "0.5rem" }}>{fehler}</div>}
      <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem" }}>
        <button onClick={() => setStep(s => s - 1)}>← Zurück</button>
        <button
          onClick={handleGenerieren}
          disabled={generieren}
          style={{ fontWeight: "bold", background: "#1a3a5c", color: "#fff", padding: "0.5rem 1rem" }}
        >
          {generieren ? "Generiere…" : "Word-Dokument generieren"}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Schritt 2: Wizard-Trigger-Button in `RegulierungSection.jsx` einbauen**

Drei Stellen anpassen:

**a) State ergänzen** (~Zeile 1671, direkt nach `useState(false)` für `stellungLaedt`):
```jsx
const [wizardOffen, setWizardOffen] = useState(false);
```

**b) Bestehenden Button bei Zeile 2235 ergänzen** (den bestehenden „📝 Stellungnahme"-Button behalten, Wizard-Button daneben einfügen):
```jsx
<Btn onClick={() => setWizardOffen(true)} title="Geführter Stellungnahme-Wizard">
  📋 Stellungnahme-Wizard
</Btn>
```

**c) `SlidePanel` am Ende des JSX der Section-Komponente** (vor dem letzten schließenden Tag).
`SlidePanel` nimmt `open`, `onClose`, `title` — die Variable für das AZ in RegulierungSection ist `akteId`:
```jsx
<SlidePanel
  open={wizardOffen}
  onClose={() => setWizardOffen(false)}
  title="Stellungnahme erstellen"
>
  <ReguWizard az={akteId} onClose={() => setWizardOffen(false)} />
</SlidePanel>
```

- [ ] **Schritt 3: Im Browser testen**

1. Backend starten, Frontend starten
2. Eine Akte öffnen, die mindestens ein Abrechnungsschreiben mit Kürzungen hat
3. Tab „Regulierung" → Button „Stellungnahme-Wizard" klicken
4. Alle Steps durchgehen, am Ende Word-Download prüfen
5. Prüfen: keine `[FEHLT: <XYZ>]`-Markierungen im Dokument

- [ ] **Schritt 4: Commit**

```bash
git add frontend/src/sections/RegulierungSection.jsx
git commit -m "feat(prd27c): ReguWizard UI – geführte Stellungnahme je Kürzungsposition"
```

---

## Task 6: Kürzungskatalog Textbaustein-Preview (PRD-02c)

**Files:**
- Modify: `frontend/src/views/KuerzungskatalogView.jsx`

- [ ] **Schritt 1: Preview-Zeile in der Listen-Darstellung einfügen**

In `KuerzungskatalogView.jsx` in der Render-Schleife der Kürzungsarten-Liste
nach dem Bezeichnungs-Element eine Preview-Zeile ergänzen:

```jsx
{art.textbaustein && (
  <div style={{
    fontSize: "0.78rem",
    color: "#666",
    marginTop: "0.2rem",
    fontStyle: "italic",
    maxWidth: "500px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  }}>
    {art.textbaustein.slice(0, 120)}{art.textbaustein.length > 120 ? "…" : ""}
  </div>
)}
```

- [ ] **Schritt 2: Im Browser prüfen**

Kürzungskatalog öffnen — nach dem Import (Task 1 `--write`) sollten alle 19
Einträge eine Vorschau-Zeile zeigen.

- [ ] **Schritt 3: Commit**

```bash
git add frontend/src/views/KuerzungskatalogView.jsx
git commit -m "feat(prd02c): Textbaustein-Preview in Kuerzungskatalog-Liste"
```

---

## Reihenfolge der Tasks

```
Task 1  → Word-Dateien kopieren → Dry-Run → MAPPING mit Anwalt → --write
Task 2  → Replacement-Engine + Refactor (nach Mapping-Freigabe)
Task 3  → Vorschau-Endpoint + Tests
Task 4  → api.js erweitern
Task 5  → ReguWizard UI + Browser-Test
Task 6  → Kürzungskatalog Preview
```

**Task 2 darf NICHT vor dem gemeinsamen Mapping-Review aus Task 1 begonnen werden.**
