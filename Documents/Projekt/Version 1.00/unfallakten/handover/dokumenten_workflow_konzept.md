# Dokumenten-Workflow-System & Produktplanung
# Kanzlei Koch, Schatz & Kollegen – Unfallakten-Verwaltungssystem
> Version 3 – Session v18, 27. März 2026
> Trennung: PRD-## = Modulentwicklung | B-## = Bugfixing
> Ergänzt um: UX-Kritik, Tagesstart, Reiter-Ablauf, Single Source of Truth Abrechnungsart

---

## Legende

| Präfix | Bedeutung |
|---|---|
| `PRD-##` | Product Requirement – neues Modul oder Feature |
| `B-##` | Bug – Fehler in bestehendem Code |
| ⬜ | Offen |
| 🔄 | In Arbeit |
| ✅ | Erledigt |

---

## Aktuelle Bug-Liste

### B-01 ✅ Prüfbericht-Persistenz
**Datei:** `abrechnungsschreiben_routes.py`
Prüfbericht verschwand nach Neuanmelden. Behoben in v17.

### B-02 ✅ Kürzungskatalog Dauerspinner
**Datei:** `App.jsx` – `KuerzungskatalogSection`
`KATEGORIE_CFG` nie definiert → React Error Boundary fing Crash stumm ab.
`finally`-Block fehlte → `setLoading(false)` wurde nie erreicht.
Behoben in v18. Siehe `bugs_and_fixes.md` [v18-01].

### B-03 ⬜ Klagegenerator nicht vollständig getestet
**Datei:** `klage_service.py`, `klage_routes.py`
13 Blöcke müssen einzeln getestet werden. Noch kein Block abgenommen.
→ Gehört zu PRD-03.

### B-04 ⬜ Abrechnungsart-Logik an 4 Stellen gespiegelt
**Dateien:** `App.jsx` (3 Stellen), `klage_service.py`
Die Logik "fiktiv / konkret / Totalschaden → welcher Betrag gilt" ist mehrfach
vorhanden. Führte in v15 zu Bugs (B-15-02). Wird bei jeder Änderung erneut
inkonsistent.
→ Wird in PRD-14 als erstes behoben (Single Source of Truth).
**Risiko:** Hoch – Konsistenzfehler setzen sich in Klageschrift und Regulierung fort.

### B-05 ⬜ WDM-Daten werden nur auf Knopfdruck geladen
**Dateien:** `App.jsx`, `klage_routes.py`
WDM-Felder (Unfalldatum, Unfallort, Zeugen etc.) werden nicht automatisch
beim Öffnen einer Akte geladen. Wenn Sachbearbeiter "WDM laden" vergisst:
Klageschrift hat kein Unfalldatum.
→ Wird in PRD-15 behoben (automatischer WDM-Load).

---

## Produktplanung – Übersicht

```
── FUNDAMENT ──────────────────────────────────────────────────
PRD-14  Single Source of Truth: Abrechnungsart          [KRITISCH]
PRD-15  WDM automatisch laden                           [KRITISCH]
PRD-16  Reiter-Reihenfolge: Ablauf erkennbar            [UX]
PRD-17  Tagesstart-Dashboard                            [UX]
PRD-18  Statusmodell erweitern                          [Logik]

── BESTEHENDE FEATURES ABSCHLIESSEN ───────────────────────────
PRD-01  To-Do-System + Kachel                           [Fundament]
PRD-02  Kürzungsarten: Textbaustein-Feld                [Stellungnahme]
PRD-03  Klagegenerator Abschlusstest                    [Klage]
PRD-13  D4 Rechtliche Würdigung (Klage)                 [Klage]
PRD-12  Vorlagen-Verwaltung (Einstellungen)             [Einstellungen]

── DOKUMENTEN-WORKFLOW ────────────────────────────────────────
PRD-04  Erweiterte Dokumentenklassen                    [Workflow]
PRD-05  Betrag-Abgleich nach Upload                     [Workflow]
PRD-06  Parser: Reparaturrechnung (LLM)                 [Workflow]
PRD-07  Workflow-Regeln + automatische To-Dos           [Workflow]
PRD-08  Weitere Parser (je Dokumentenklasse)            [Workflow]
PRD-09  Vollständigkeits-Ampel (smart)                  [Workflow]
PRD-10  Mandanten-Anforderungsstatus                    [Workflow]
PRD-11  Dokument-Position-Verknüpfung                   [Integration]
PRD-19  RA-Micro DMS Integration (Read-Only)            [Integration]
```

---

## 🔴 PRD-14 – Single Source of Truth: Abrechnungsart
**Priorität:** 🔴 Kritisch – vor allen anderen PRDs
**Session-Schätzung:** 1 Session
**Abhängigkeiten:** keine – Voraussetzung für alle anderen PRDs die Beträge verwenden

### Problem (B-04)
Die Logik zur Bestimmung der Abrechnungsart und des maßgeblichen Fahrzeugschadens
ist an **4 Stellen** gespiegelt:
- `App.jsx` → `calcBrutto()` (Übersichtsberechnung)
- `App.jsx` → `_fzg()` in `UebersichtSection`
- `App.jsx` → `_fzg()` in `AktenDetail`
- `klage_service.py` → `berechne_fahrzeugschaden()`

Jede Änderung muss an 4 Stellen gemacht werden. Jede Inkonsistenz führt dazu
dass Frontend und Klageschrift unterschiedliche Beträge zeigen.

### Lösung: Backend berechnet, Frontend zeigt nur an

```python
# backend/models/schaden.py – neue Funktion

def berechne_abrechnungsart(schaden: dict) -> dict:
    """
    Einzige Stelle im gesamten System wo die Abrechnungsart berechnet wird.
    Gibt vollständiges Ergebnis zurück – Frontend rechnet NIE selbst.

    Returns:
        {
          "abrechnungsart":     "fiktiv" | "konkret" | "totalschaden",
          "fahrzeugschaden":    1234.56,   # der maßgebliche Nettobetrag
          "fahrzeugschaden_key": "rep_gutachten_netto" | "rep_rechnung_netto" | "wiederbeschaffung",
          "ust_relevant":       True | False,
          "begruendung":        "Reparaturrechnung liegt vor (rep_rechnung_netto > 0)",
        }
    """
    def f(key): return float(schaden.get(key) or 0)

    rep_sv  = f("rep_gutachten_netto") or f("reparaturkosten")
    rep_rn  = f("rep_rechnung_netto")
    wbw     = f("wiederbeschaffung")
    rstwert = f("restwert")

    # Explizit gesetzte Abrechnungsart hat immer Vorrang
    explizit = (schaden.get("abrechnungsart") or "").strip()
    if explizit in ("fiktiv", "konkret", "totalschaden"):
        art = explizit
    else:
        # Auto-Logik
        if wbw > 0 and (rep_sv <= 0 or rep_sv > wbw - rstwert):
            art = "totalschaden"
        elif rep_rn > 0:
            art = "konkret"
        else:
            art = "fiktiv"

    if art == "totalschaden":
        betrag = wbw - rstwert
        key    = "wiederbeschaffung"
    elif art == "konkret":
        betrag = rep_rn
        key    = "rep_rechnung_netto"
    else:
        betrag = rep_sv
        key    = "rep_gutachten_netto"

    return {
        "abrechnungsart":      art,
        "fahrzeugschaden":     round(betrag, 2),
        "fahrzeugschaden_key": key,
        "ust_relevant":        art == "konkret",
    }
```

### API-Änderung
```
GET /akten/<az>/schaden
→ Response enthält künftig: { ...schaden, "abrechnungsberechnung": { ... } }
```

Frontend liest `abrechnungsberechnung` aus der API-Response.
Alle Frontend-Berechnungen (`calcBrutto`, `_fzg`) werden **gelöscht** und
durch den API-Wert ersetzt.

### Checkliste
- [ ] `berechne_abrechnungsart()` in `backend/models/schaden.py`
- [ ] `GET /akten/<az>/schaden` gibt `abrechnungsberechnung` zurück
- [ ] `App.jsx`: `calcBrutto()` entfernen, durch API-Wert ersetzen
- [ ] `App.jsx`: `_fzg()` in UebersichtSection entfernen
- [ ] `App.jsx`: `_fzg()` in AktenDetail entfernen
- [ ] `klage_service.py`: `berechne_fahrzeugschaden()` ruft jetzt `berechne_abrechnungsart()` auf
- [ ] Regressionstest: Summen in Übersicht == Summen in Klageschrift

**Abnahmekriterium:** Betrag in Übersicht, Regulierungsreiter und Klageschrift
sind identisch bei gleicher Akte – unabhängig davon ob fiktiv/konkret/Totalschaden.

---

## 🔴 PRD-15 – WDM automatisch laden
**Priorität:** 🔴 Hoch
**Session-Schätzung:** 1 Session
**Abhängigkeiten:** keine

### Problem (B-05)
WDM-Variablen (Unfalldatum, Unfallort, Zeugen, Fahrer, Kennzeichen Gegner etc.)
werden nur geladen wenn der Sachbearbeiter aktiv auf "WDM laden" klickt.
Vergisst er das → Klageschrift hat leere Felder.

### Lösung
Beim Öffnen einer Akte wird WDM automatisch im Hintergrund geladen und mit
SQLite-Daten gemergt (SQLite hat Vorrang – manuell Eingetragenes wird nie überschrieben).

```python
# In GET /akten/<az>/unfalldetails (bereits vorhanden)
# Schon implementiert für den Klage-Tab – auf alle Reiter ausweiten

# Erweitern auf:
# GET /akten/<az>  (Akten-Öffnen)
# → WDM-Merge direkt in der Antwort, kein separater Klick nötig
```

### UI-Änderung
- "WDM laden"-Button bleibt als manueller Refresh für den Fall dass RA-Micro
  nach dem Öffnen aktualisiert wurde
- Neu: kleines WDM-Status-Icon in der Kopfzeile:
  - ✅ grün: WDM geladen
  - ⚠️ gelb: WDM nicht erreichbar (RA-Micro offline)
  - Kein Icon: keine WDM-Integration konfiguriert

### Checkliste
- [ ] WDM-Merge in `GET /akten/<az>` integrieren
- [ ] WDM-Status-Icon in Akten-Kopfzeile
- [ ] "WDM laden"-Button bleibt als manueller Refresh
- [ ] Warnung wenn WDM-Pflichtfelder für Klage leer sind

**Abnahmekriterium:** Akte öffnen → Unfalldatum, Unfallort, Kennzeichen Gegner
automatisch aus RA-Micro vorausgefüllt, ohne Klick.

---

## 🔴 PRD-16 – Reiter-Reihenfolge: Ablauf erkennbar
**Priorität:** 🔴 Hoch
**Session-Schätzung:** 0,5 Sessions (nur Umsortierung + UX-Anpassung)
**Abhängigkeiten:** PRD-01 (To-Dos als erster Reiter)

### Problem
Acht Reiter ohne erkennbare Reihenfolge. Der Sachbearbeiter muss selbst
wissen wo er steht und was als nächstes zu tun ist.

### Neue Reiter-Reihenfolge (Ablauf-Logik)

```
1. 📋 To-Dos          ← Was ist jetzt zu tun? (PRD-01)
2. 👥 Beteiligte      ← Wer ist beteiligt? (Grundlage für alles)
3. 🚗 Schaden         ← Was ist passiert / wie hoch ist der Schaden?
4. 📄 Dokumente       ← Welche Belege liegen vor?
5. 💶 Regulierung     ← Was hat die Versicherung gezahlt / gekürzt?
6. ⚖️ Klage           ← Gerichtliche Geltendmachung
7. 📝 Word            ← Alle generierbaren Dokumente
8. 🔍 Unfalldetails   ← Ergänzende Details (WDM-Daten, selten gebraucht)
```

**Begründung der Reihenfolge:**
- To-Dos zuerst: sofortiger Überblick was offen ist
- Beteiligte vor Schaden: ohne Gegner/GHPV kann kein Schreiben generiert werden
- Dokumente vor Regulierung: Belege müssen vor Regulierungsprüfung vorliegen
- Klage nach Regulierung: logischer Eskalationsweg
- Word nach Klage: Generierung als letzter Schritt, nicht als Einstieg
- Unfalldetails ans Ende: selten bearbeitet, meist durch WDM vorausgefüllt

### Visueller Fortschrittsindikator
Jeder Reiter bekommt einen Status-Punkt:
```
📋 To-Dos      🔴 3 offen
👥 Beteiligte  ✅ vollständig
🚗 Schaden     ✅ vollständig
📄 Dokumente   ⚠️ 2 fehlen
💶 Regulierung ⚠️ Kürzungen offen
⚖️ Klage       ⬜ noch nicht begonnen
```

### Checkliste
- [ ] Reiter umsortieren in `App.jsx`
- [ ] Status-Punkte je Reiter berechnen und anzeigen
- [ ] Reiter-Icons einheitlich

**Abnahmekriterium:** Neuer Sachbearbeiter öffnet Akte und erkennt ohne Einweisung
wo er steht und was als nächstes zu tun ist.

---

## 🔴 PRD-17 – Tagesstart-Dashboard
**Priorität:** 🔴 Hoch
**Session-Schätzung:** 1–2 Sessions
**Abhängigkeiten:** PRD-01 (To-Dos), PRD-04 (Dokumentenklassen)

### Vision
Der Sachbearbeiter öffnet morgens das System und sieht sofort:
was ist heute zu tun, was ist neu, was ist dringend.

### Dashboard-Struktur

```
┌─────────────────────────────────────────────────────────────┐
│  Guten Morgen, Peter Koch  ·  Freitag, 27. März 2026       │
├─────────────┬───────────────┬──────────────┬───────────────┤
│  🔴 Dringend │  📨 Neu heute  │  ⏳ In Arbeit │  ✅ Diese Woche│
│      3      │       2       │      12      │      8        │
└─────────────┴───────────────┴──────────────┴───────────────┘

🔴 HEUTE FÄLLIG
  322/25KS  Müller ./. Allianz    Stellungnahme überfällig – 18 Tage offen
  187/24AS  Schmidt ./. HUK       Verjährung in 12 Tagen ← frist_typ=verjaehrung
  091/25KS  Weber ./. DEVK        Warte auf Mietwagenrechnung – 21 Tage

📨 NEU EINGEGANGEN
  E-Mail von Allianz zu 244/24KS  [In Akte öffnen]
  Abrechnungsschreiben zu 311/25AS wurde geparst  [Prüfen]

🚀 BEREIT ZUR BEARBEITUNG
  Akten bei denen alle Dokumente vorliegen aber noch kein
  Forderungsschreiben generiert wurde (5 Akten)  [Alle anzeigen]
```

### Datenquellen
| Block | Quelle |
|---|---|
| Dringend | `todos`-Tabelle: `faellig_am` < heute + 3 Tage, oder Alter > 15 Tage |
| Verjährung | `todos`-Tabelle: `frist_typ = 'verjaehrung'` |
| Neu eingegangen | `email_import_log` + `dokumente` (heute erstellt) |
| Bereit zur Bearbeitung | Akten wo Klasse-A-Dokumente vorhanden aber kein Forderungsschreiben |

### Checkliste
- [ ] Neuer Reiter "Dashboard" in der Hauptnavigation (ganz links)
- [ ] Kacheln: Dringend / Neu / In Arbeit / Diese Woche
- [ ] Block "Heute fällig" (aus `todos`)
- [ ] Block "Neu eingegangen" (aus E-Mail-Import + Dokumente)
- [ ] Block "Bereit zur Bearbeitung" (aus Dokumenten-Vollständigkeit)
- [ ] Sachbearbeiter-Filter (eigene Akten / alle Akten)
- [ ] Klick auf Eintrag öffnet direkt die richtige Akte im richtigen Reiter

**Abnahmekriterium:** Sachbearbeiter öffnet das System morgens und kann ohne
eine einzige Akte manuell zu öffnen erkennen was heute prioritär ist.

---

## 🟡 PRD-18 – Statusmodell erweitern
**Priorität:** 🟡 Mittel
**Session-Schätzung:** 1 Session
**Abhängigkeiten:** PRD-14

### Problem
Eine Akte hat einen einzigen Status: `offen / abgeschlossen / klage`.
Das bildet die Realität nicht ab – eine Akte kann mehrere parallele Zustände haben.

### Neues Statusmodell

```sql
-- Bestehend (bleibt):
status TEXT  -- 'offen' | 'abgeschlossen' | 'klage'

-- Neu (zusätzliche Spalten):
ALTER TABLE unfallakte ADD COLUMN regulierungsstatus TEXT
    DEFAULT 'ausstehend';
    -- 'ausstehend' | 'teilreguliert' | 'vollreguliert' | 'abgelehnt' | 'strittig'

ALTER TABLE unfallakte ADD COLUMN klagestatus TEXT
    DEFAULT 'kein_verfahren';
    -- 'kein_verfahren' | 'vorbereitung' | 'eingereicht' | 'anhängig' | 'abgeschlossen'

ALTER TABLE unfallakte ADD COLUMN wv_status TEXT
    DEFAULT 'keine';
    -- 'keine' | 'fällig' | 'überfällig'
```

### Automatische Ableitung
- `regulierungsstatus` wird automatisch aus `regulierung_positionen` berechnet
- `klagestatus` wird manuell gesetzt (oder bei Klageschrift-Generierung auf 'vorbereitung')
- `wv_status` kommt aus RA-Micro Wiedervorlagen

### Checkliste
- [ ] DB-Migration: 3 neue Statusspalten
- [ ] `regulierungsstatus` automatisch berechnen nach jeder Regulierung
- [ ] Aktenübersicht: kombinierte Statusanzeige
- [ ] Filter in der Aktenübersicht nach allen Statusdimensionen

---

## PRD-01 – To-Do-System + Kachel
**Priorität:** 🔴 Hoch
**Session-Schätzung:** 1 Session
**Abhängigkeiten:** keine (aber PRD-16 bestimmt wo die Kachel landet)

### Ziel
Sachbearbeiter kann To-Dos manuell anlegen, abhaken und priorisieren.
To-Dos erscheinen als erster Reiter in der Akte (PRD-16) und im Tagesstart (PRD-17).

### DB-Schema
```sql
CREATE TABLE todos (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  akte_az      TEXT NOT NULL REFERENCES unfallakte(az),
  text         TEXT NOT NULL,
  erstellt_am  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
  faellig_am   TEXT,
  frist_typ    TEXT,   -- 'verjaehrung' | 'gericht' | 'intern' | NULL
  erledigt_am  TEXT,
  erledigt     INTEGER NOT NULL DEFAULT 0 CHECK(erledigt IN (0,1)),
  quelle       TEXT NOT NULL DEFAULT 'benutzer',  -- 'system' | 'benutzer'
  dok_id       INTEGER REFERENCES dokumente(id),
  regel_key    TEXT,
  sortierung   INTEGER NOT NULL DEFAULT 0
);
```

### Dringlichkeit (zwei Dimensionen)
```
Nach Alter (kein faellig_am):
  0–3 Tage   → grau
  4–7 Tage   → gelb
  8–14 Tage  → orange
  15+ Tage   → rot

Nach Frist (faellig_am gesetzt):
  > 14 Tage  → grau
  7–14 Tage  → gelb
  3–7 Tage   → orange
  < 3 Tage   → rot
  verjaehrung → immer eine Stufe höher
```

### Verhalten
- Erledigt: durchgestrichen, rote Schrift, bleibt in Liste am Ende
- System-To-Dos: Schloss-Icon, Text nicht editierbar
- Nutzer kann eigene anlegen, erledigen, wieder öffnen

### Checkliste
- [ ] DB-Migration: `todos`-Tabelle
- [ ] `todos_routes.py` + Blueprint in `app.py`
- [ ] To-Do-Reiter als erster Reiter in Aktenansicht
- [ ] Zeitbasierte Dringlichkeitsfarben
- [ ] Frist-Dringlichkeit
- [ ] Erledigt-Markierung (nicht gelöscht)
- [ ] Manuelles Anlegen + Text + optionales Fälligkeitsdatum

**Abnahmekriterium:** To-Do anlegen, Fälligkeitsdatum setzen, abhaken –
bleibt durchgestrichen in der Liste.

---

## PRD-02 – Kürzungsarten: Textbaustein-Feld
**Priorität:** 🔴 Hoch
**Session-Schätzung:** 1 Session
**Abhängigkeiten:** keine

### DB-Migration
```sql
ALTER TABLE kuerzungsarten ADD COLUMN textbaustein TEXT;
```

### Fallback-Kette in `stellungnahme_service.py`
```python
text = ka.textbaustein \
    or ka.standard_gegenargument \
    or "Die Kürzung ist nicht gerechtfertigt."
```

### Checkliste
- [ ] DB-Migration
- [ ] `schema_manager.py` Migration eintragen
- [ ] Kürzungskatalog-Formular: Textarea für Textbaustein
- [ ] `stellungnahme_service.py`: Fallback-Kette
- [ ] Kürzungskatalog-Liste: Textbaustein-Preview

---

## PRD-03 – Klagegenerator Abschlusstest
**Priorität:** 🔴 Hoch
**Session-Schätzung:** 1–2 Sessions
**Abhängigkeiten:** PRD-14 (Abrechnungsart muss konsistent sein bevor Test sinnvoll)

| Block | Was prüfen | Status |
|---|---|---|
| **Rubrum** | Kläger, Beklagte, Vertreter, Gericht | ⬜ |
| **Einleitung** | AZ, Unfalldatum, Unfallort, Kennzeichen, Schadennummer | ⬜ |
| **Tatbestand** | Unfallschilderung, Zeugen, Fahrer, KFZ-Daten | ⬜ |
| **Ermittlungsakte** | AZ, Behörde, Ort | ⬜ |
| **Schadentabelle** | Positionen je Abrechnungsart, Beträge, Pauschale | ⬜ |
| **Haftungsquote** | Block bei HQ < 100%, korrekte Berechnung | ⬜ |
| **Haftungsbegründung** | varANSP1 oder SQLite | ⬜ |
| **Schmerzensgeld** | Block bei Anhaken, Mindestbetrag optional | ⬜ |
| **Zinsen** | Verzugsdatum, Zinsbeginn, 5PP | ⬜ |
| **Klageanträge** | Hauptantrag, Leerzeilen, Versäumnisurteil | ⬜ |
| **Rechtliche Würdigung** | Platzhalter, Kürzungsargumente | ⬜ |
| **RVG** | Streitwert, §13-Tabelle, MwSt, Override | ⬜ |
| **Verweisbetrieb** | Textbaustein, Entfernungsangabe | ⬜ |

---

## PRD-04 – Erweiterte Dokumentenklassen
**Priorität:** 🔴 Hoch
**Session-Schätzung:** 1 Session

### Dokumentenklassen

**Klasse A – Immer vorhanden**
| Key | Label | Position-Key |
|---|---|---|
| `gutachterrechnung` | Gutachterrechnung | `sv_kosten` |
| `reparaturrechnung` | Reparaturrechnung | `rep_rechnung_netto` |
| `abschlepprechnung` | Abschlepprechnung | `abschleppkosten` |
| `abrechnungsschreiben` | Abrechnungsschreiben | ✅ vorhanden |
| `pruefbericht` | Prüfbericht | ✅ vorhanden |

**Klasse B – Personenschaden**
| Key | Label | Position-Key |
|---|---|---|
| `arztbericht` | Arztbericht | — (ICD-Codes) |
| `krankenhausbericht` | Krankenhausbericht | — |
| `verdienstausfall_nachweis` | Verdienstausfall-Nachweis | `verdienstausfall` |
| `haushalt_attest` | Attest Haushaltsführung | `haushalt` |

**Klasse C – Sonderfälle**
| Key | Label | Position-Key |
|---|---|---|
| `mietwagenrechnung` | Mietwagenrechnung | `mietwagenkosten` |
| `kaufvertrag` | Kaufvertrag | Vergleich WBW |
| `nachbesichtigung` | Nachbesichtigungsgutachten | Vergleich Erstgutachten |
| `feuerwehrrechnung` | Feuerwehrrechnung | `sonstiges` |
| `sachschadenbeleg` | Sachschadenbeleg | `sonstiges` |
| `sonstiges` | Sonstiges | — |

### DB-Migration
```sql
ALTER TABLE dokumente ADD COLUMN dokumentenklasse TEXT;
ALTER TABLE dokumente ADD COLUMN pdf_hash TEXT;  -- SHA-256
```

### Checkliste
- [ ] DB-Migration
- [ ] Upload-Dialog: Klassen-Dropdown
- [ ] SHA-256-Hash beim Upload + Duplikat-Warnung
- [ ] Dokumentenliste: Klassen-Badge
- [ ] Vollständigkeitsanzeige

---

## PRD-05 – Betrag-Abgleich nach Upload
**Priorität:** 🔴 Hoch
**Abhängigkeiten:** PRD-04, PRD-14

### Smarte Ampel (aus Schadentabelle ableiten)
```python
ERWARTUNGS_REGELN = [
  { "wenn_position": "schmerzensgeld",    "dann_klasse": "arztbericht" },
  { "wenn_position": "mietwagenkosten",   "dann_klasse": "mietwagenrechnung" },
  { "wenn_position": "rep_rechnung_netto","dann_klasse": "reparaturrechnung" },
  { "wenn_position": "sv_kosten",         "dann_klasse": "gutachterrechnung" },
  { "wenn_position": "verdienstausfall",  "dann_klasse": "verdienstausfall_nachweis" },
]
```

---

## PRD-06 – Parser: Reparaturrechnung (LLM-Ansatz)
**Priorität:** 🔴 Hoch
**Abhängigkeiten:** PRD-04, PRD-05

### LLM statt Regex
```python
# backend/workflow/parser_reparaturrechnung.py
def parse_reparaturrechnung(pdf_text: str) -> dict:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{"role": "user", "content": f"""
Extrahiere aus dieser Reparaturrechnung:
- betrag_netto (Zahl, Punkt als Dezimaltrennzeichen)
- betrag_brutto (Zahl)
- werkstatt_name
- rechnungsdatum (YYYY-MM-DD)
- rechnungsnummer (oder null)
Antworte NUR als JSON, ohne Erklärung.
Text: {pdf_text[:4000]}
"""}]
    )
    return json.loads(response.content[0].text)
```

### Dispatcher-Architektur
```python
# backend/workflow/dispatcher.py
PARSER_MAP = {
    "reparaturrechnung": parser_reparaturrechnung.parse,
    "gutachterrechnung": parser_rechnung_allgemein.parse,
    "arztbericht":       parser_arztbericht.parse,
    "mietwagenrechnung": parser_mietwagen.parse,
    "sonstiges":         None,
}
```

---

## PRD-07 – Workflow-Regeln + automatische To-Dos
**Priorität:** 🟡 Mittel
**Abhängigkeiten:** PRD-01, PRD-04, PRD-06

### Initiale Regeln
```python
WORKFLOW_REGELN = [
  { "key": "rep→nutzungsausfall",  "ausloeser": "reparaturrechnung",
    "pruefe": "nutzungsausfall",   "todo_text": "Nutzungsausfall prüfen – Reparaturrechnung liegt vor" },
  { "key": "rep→mietwagen",        "ausloeser": "reparaturrechnung",
    "pruefe": "mietwagenkosten",   "todo_text": "Mietwagenrechnung anfordern oder Nutzungsausfall berechnen" },
  { "key": "arzt→schmerzensgeld",  "ausloeser": "arztbericht",
    "pruefe": "schmerzensgeld",    "todo_text": "Schmerzensgeld prüfen – Arztbericht liegt vor" },
  { "key": "arzt→haushalt",        "ausloeser": "arztbericht",
    "pruefe": "haushalt",          "todo_text": "Haushaltsführungsschaden prüfen – Verletzung dokumentiert" },
  { "key": "gutachten→sv_kosten",  "ausloeser": "gutachterrechnung",
    "pruefe": "sv_kosten",         "todo_text": "SV-Kosten in Schadentabelle eintragen" },
]
```

---

## PRD-08 bis PRD-13 (unverändert aus v2)

PRD-08: Weitere Parser (Arztbericht, Mietwagen, Kaufvertrag, Gutachten)
PRD-09: Vollständigkeits-Ampel (smart)
PRD-10: Mandanten-Anforderungsstatus
PRD-11: Dokument-Position-Verknüpfung
PRD-12: Vorlagen-Verwaltung
PRD-13: D4 Rechtliche Würdigung

---

## Empfohlene Session-Reihenfolge (aktualisiert)

| Session | PRD | Titel | Kritisch weil |
|---|---|---|---|
| v19 | **PRD-14** | Single Source of Truth: Abrechnungsart | Alle anderen PRDs bauen darauf auf |
| v20 | **PRD-01** | To-Do-System + Kachel | Fundament für Dashboard + Workflow |
| v21 | **PRD-16** | Reiter-Reihenfolge | UX-Fundament, geringer Aufwand |
| v22 | **PRD-15** | WDM automatisch laden | Verhindert leere Klageschriften |
| v23 | **PRD-03** | Klagegenerator Abschlusstest | Nach PRD-14 erst sinnvoll testbar |
| v24 | **PRD-02** | Textbaustein Kürzungsarten | Stellungnahme-Qualität |
| v25 | **PRD-17** | Tagesstart-Dashboard | Braucht To-Dos (PRD-01) |
| v26 | **PRD-18** | Statusmodell erweitern | Braucht PRD-14 |
| v27 | **PRD-04** | Erweiterte Dokumentenklassen | Workflow-Fundament |
| v28 | **PRD-05** | Betrag-Abgleich | Braucht PRD-04 + PRD-14 |
| v29 | **PRD-06** | Parser Reparaturrechnung (LLM) | Pilotprojekt Parser |
| v30 | **PRD-07** | Workflow-Regeln + auto To-Dos | Braucht PRD-01 + PRD-06 |
| v31+ | PRD-08 | Weitere Parser | je Session eine Gruppe |
| v3x | PRD-09–13 | Vollständigkeit, Mandant, Verknüpfung | Später |

---

## Offene Entscheidungen

- [ ] Soll die globale To-Do-Übersicht in PRD-17 (Tagesstart) integriert werden oder als eigener Reiter? (Empfehlung: Tagesstart)
- [ ] Welche Dokumentenklassen initial in PRD-04? (Empfehlung: alle Klasse-A + Arztbericht)
- [ ] LLM-Parser (PRD-06): direkt Anthropic API oder über bestehendes Backend-Setup?
- [ ] ICD-Code-Lookup für Arztberichte (PRD-08B): eigene Tabelle oder externe API?
- [ ] Sachbearbeiter-Filter im Tagesstart (PRD-17): eigene Akten default oder alle?
- [ ] Verjährungs-Datum: manuell eingetragen oder automatisch aus Unfalldatum berechnen (3 Jahre)?

---

## Architektur-Prinzipien (unveränderlich)

Diese Prinzipien gelten für alle PRDs und dürfen nicht gebrochen werden:

1. **Single Source of Truth:** Jede Berechnung findet genau einmal statt – im Backend. Frontend zeigt nur an.
2. **`az = akte.aktenzeichen`:** Nach `hole_akte_by_id()` immer `az` setzen, nie `akte_id` direkt in Queries verwenden.
3. **Kein stummer Catch:** Jeder `catch`-Block zeigt einen echten Fehlertext im Toast.
4. **`finally` für Loading-States:** `setLoading(false)` immer in `finally`, nie nach dem try-catch.
5. **Blueprint-Routing:** Fester `url_prefix` + `<path:akte_id>` pro Route – nie `<path:>` am Ende des Prefixes.
6. **Python 3.9 kompatibel:** Keine `str | None` Type-Hints, keine `list[dict]` Syntax.
7. **`hole_beteiligte_by_akte(az)`:** Immer diese Funktion, nie roher `SELECT * FROM beteiligte`.

---

## PRD-19 – RA-Micro DMS Integration (Read-Only)
**Priorität:** 🟡 Mittel
**Session-Schätzung:** 1–2 Sessions
**Abhängigkeiten:** Zugriff auf RA-Micro SQL-Server (Read-Only)

### Ziel
Alle in RA-Micro abgelegten Dokumente einer Akte erscheinen automatisch
im Dokumente-Reiter als Read-Only-Einträge – ohne Upload, ohne Kopieren,
immer aktuell. Die Datei bleibt in RA-Micro, das System verlinkt nur.

### Warum SQL und nicht Dateipfad
- SQL liefert Metadaten (Datum, Dokumentart, Sachbearbeiter) ohne Dateisystem-Analyse
- Funktioniert auch wenn Backend und RA-Micro auf verschiedenen Rechnern laufen
- Read-Only-Datenbankverbindung ist sicherer als Netzwerkfreigabe
- Einmal eingerichtet: vollautomatisch, kein manueller Pflegaufwand

### Architektur
```
RA-Micro SQL-Server (Read-Only-Verbindung)
    ↓
backend/ramicro/dms_connector.py
    ↓
GET /akten/<az>/ramicro-dokumente
    ↓
Frontend: Dokumente-Reiter zeigt RA-Micro-Dokumente mit Badge "📁 RA-Micro"
```

### Verbindung (Backend)
```python
# backend/ramicro/dms_connector.py
import pyodbc  # oder pymssql je nach SQL-Server-Typ

_DMS_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={os.environ['RAMICRO_SQL_SERVER']};"
    f"DATABASE={os.environ['RAMICRO_SQL_DB']};"
    f"UID={os.environ['RAMICRO_SQL_USER']};"
    f"PWD={os.environ['RAMICRO_SQL_PASS']};"
    "ReadOnly=Yes;"   # ← kein Schreiben möglich
)

def hole_dms_dokumente(az: str) -> list:
    """
    Lädt alle Dokumente einer Akte aus dem RA-Micro ELO-DMS.
    Zentrale Tabelle: tblElo_AktenArchiv (Datenbank: raEloakte)
    Mapping: AZ '322/25KS' → AktenNr=322, Jahrgang=25
    """
    # AZ parsen: '322/25KS' → nr=322, jahr=25
    import re
    m = re.match(r'(\d+)/(\d+)', az)
    if not m:
        return []
    akten_nr = int(m.group(1))
    jahrgang  = int(m.group(2))

    with pyodbc.connect(_DMS_CONN_STR, timeout=5) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.Nr,
                a.Dateiname,
                a.OrgDatei,
                a.Rubrik,
                a.Schlagwort,
                a.Sachbearb,
                a.EinfDatum,
                a.Geaendert,
                a.Status,
                t.Text AS RubrikText
            FROM tblElo_AktenArchiv a
            LEFT JOIN tblElo_Text t
                ON t.Pool = 'Rubrik' AND t.IDText = TRY_CAST(a.Rubrik AS numeric)
            WHERE a.AktenNr = ? AND a.Jahrgang = ?
            ORDER BY a.EinfDatum DESC
        """, (akten_nr, jahrgang))

        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
```

### Umgebungsvariablen (.env)
```
RAMICRO_SQL_SERVER=192.168.x.x\RAMICRO    # SQL-Server-Adresse
RAMICRO_SQL_DB=RA-MICRO                    # Datenbankname
RAMICRO_SQL_USER=readonly_user             # Read-Only-Benutzer
RAMICRO_SQL_PASS=...
RAMICRO_DMS_BASEPATH=\\RA-SERVER\DOCS      # Basispfad für Datei-Download
```

### Frontend-Integration
Im Dokumente-Reiter: zwei getrennte Bereiche:
```
── Hochgeladene Dokumente (eigenes System) ────────────────────
  [Liste wie bisher]

── RA-Micro Dokumente (Read-Only) ─────────────────────────────
  📁 Schreiben_Allianz_15032026.pdf     15.03.2026  [Öffnen]
  📁 Abrechnungsschreiben_220325.pdf    22.03.2026  [Öffnen]
  📁 Gutachten_Kfz_Koch.pdf            01.03.2026  [Öffnen]
```

Kein Upload-Button für RA-Micro-Dokumente – nur Anzeigen und Öffnen.
Optional: "In eigenes System übernehmen" (kopiert + verknüpft).

### Drag & Drop aus RA-Micro (Diagnose ausstehend)
Aktuell: Cursor ändert sich beim Drop, aber keine Datei wird übergeben.
Mögliche Ursachen:
- RA-Micro übergibt nur Dateipfad als Text (nicht als File-Objekt)
- Debug-Code nötig um zu prüfen was `dataTransfer` enthält:
```javascript
onDrop={e => {
  console.log("files:", e.dataTransfer.files.length);
  console.log("types:", [...e.dataTransfer.types]);
  console.log("text:", e.dataTransfer.getData("text"));
}}
```
→ Nach Diagnose ggf. Pfad-Import-Endpunkt bauen.

### Checkliste
- [x] RA-Micro SQL-Tabellenstruktur analysieren → `tblElo_AktenArchiv` ist die zentrale Tabelle
- [x] Aktenzeichen-Mapping verifiziert: AktenNr + Jahrgang → AZ ohne SB-Kürzel
- [ ] Read-Only SQL-Benutzer in RA-Micro anlegen
- [ ] `backend/ramicro/dms_connector.py` mit korrekter Query
- [ ] `GET /akten/<az>/ramicro-dokumente` Route
- [ ] Frontend: RA-Micro-Dokumente-Block im Dokumente-Reiter
- [ ] Datei-Download über Backend (proxied, kein direkter Client-Zugriff auf SQL)
- [ ] Drag & Drop Diagnose + ggf. Pfad-Import
- [ ] `.env`-Dokumentation erweitern
- [ ] Fallback wenn RA-Micro SQL nicht erreichbar (graceful degradation)

### SQL-Tabellenstruktur (analysiert)

Datenbank: **raEloakte**

Zentrale Tabelle: **`tblElo_AktenArchiv`**

| Spalte | Typ | Bedeutung |
|---|---|---|
| `Nr` | int | PK / DMS-interne ID |
| `AktenNr` | int | Aktennummer (z.B. 322 aus "322/25KS") |
| `Jahrgang` | smallint | Jahr (z.B. 25 aus "322/25KS") |
| `Dateiname` | nvarchar(255) | Dateiname im DMS |
| `OrgDatei` | nvarchar(255) | Originaldateiname / Pfad |
| `Rubrik` | nvarchar(3) | Dokumentkategorie-Kürzel |
| `Schlagwort` | nvarchar(200) | Schlagwort / Dokumentbeschreibung |
| `Sachbearb` | nvarchar(2) | SB-Kürzel (z.B. "AS", "KS") |
| `EinfDatum` | datetime | Einstellungsdatum |
| `Geaendert` | datetime | Letzte Änderung |
| `Version` | datetime | Dokumentversion-Datum |
| `Status` | smallint | Dokumentstatus |
| `WDM_XML` | text | WDM-Variablen als XML (Metadaten) |
| `IDNode` | numeric | Verknüpfung zu tblElo_TreeNodes |
| `UAkte | int | Unterakte |

Weitere Tabellen:
- `tblElo__Attachments`: Anhänge (docnodeid, filename, contenttype)
- `tblElo__Knoten`: Baumstruktur des DMS (AktenNr, Jahrgang, NodeID, Header)
- `tblElo_TreeNodes`: Knotenstruktur (IDNode, IDParentNode, IDNodeText)
- `tblElo_Text`: Textkatalog (IDText, Pool, Text) – vermutlich Rubrik-Labels

### Aktenzeichen-Mapping (✅ verifiziert)

`AktenNr=276` + `Jahrgang=26` → AZ = **`276/26`**

**Regeln:**
- SB-Kürzel (`Sachbearb`-Spalte) wird **niemals** ins Aktenzeichen aufgenommen
- AZ-Format im Unfallakten-System: `{AktenNr}/{Jahrgang}` (z.B. `276/26`)
- Mapping-Code:
```python
import re
m = re.match(r'(\d+)/(\d+)', az)   # "276/26KS" → nr=276, jahr=26
akten_nr = int(m.group(1))
jahrgang  = int(m.group(2))
# Jahrgang kann 2-stellig sein (26) oder 4-stellig (2026) → normieren:
if jahrgang > 100: jahrgang = jahrgang % 100
```

### Dateipfad-Struktur
`Dateiname`-Spalte enthält relativen DMS-Pfad:
```
ea\as\26\03\27\274614400276-00-26~~AS~01.pdf
  ↑    ↑   ↑   ↑   ↑
pool  sb  jahr mo  tag
```
Vollständiger Pfad = `RAMICRO_DMS_BASEPATH` + `\` + `Dateiname`
→ z.B. `\\RA-SERVER\ELO\ea\as\26\03\27\...pdf`

`OrgDatei` = ursprünglicher Client-Pfad beim Einstellenden (für uns irrelevant).

**Abnahmekriterium:** Akte öffnen → RA-Micro-Dokumente erscheinen automatisch
im Dokumente-Reiter ohne Upload – immer aktuell, Read-Only.
