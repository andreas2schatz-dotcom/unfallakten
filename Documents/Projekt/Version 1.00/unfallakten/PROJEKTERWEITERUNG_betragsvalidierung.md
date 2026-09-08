# Projekterweiterung: Betragsvalidierung im Dokumentenintake

> **Status (2026-08-05): ZURÜCKGESTELLT — größtenteils redundant.** Der Konsens-Check
> (Stufe 1+2) existiert bereits in beiden Parser-Pfaden. Nicht bauen ohne neuen Anlass.
> Details siehe „Code-Abgleich" unten.
> **Kontext:** Dokumentenintake-Pipeline, Extraktion aus OCR-Text via Qwen (JSON-Output).
> **Auslöser:** Qwen neigt bei Geldbeträgen zu Rundung/Glättung („1.247,83" → „1.250,00"). Bei Abrechnungsbeträgen haftungsrelevant.

---

## Code-Abgleich 2026-08-05 (warum zurückgestellt)

Auslöser: RA Schatz — Rundungsfehler bislang nicht aufgefallen. Prüfung ergab, dass
Stufe 1+2 bereits umgesetzt sind:

- **Erwartetes JSON ist im Prompt definiert:** `backend/services/llm_service.py` —
  `_SYSTEM_PROMPT` (Z. 104 ff., Abrechnung) und `_SYSTEM_PROMPT_GUTACHTEN` (Z. 216 ff.).
  **Temperatur 0 ist bereits gesetzt** (`temperature=0.0` überall). Beträge werden
  aktuell als **Zahl** (`0.00`) angefordert, nicht als String — der einzige noch offene,
  quasi kostenlose Hebel aus diesem Dokument.
- **Regex↔LLM-Konsens existiert (Shadow-Mode, Regex = Wahrheit, LLM parallel):**
  - Gutachten `backend/parsers/gutachten_parser.py:685` — pro Feld `abs(Regex−LLM) > 1,00 €`
    → `llm_konflikt`; Z. 692 auch „Regex leer, LLM hat Wert" → Konflikt.
  - Abrechnung `backend/parsers/abrechnungsschreiben_parser.py:599` — Gesamtbetrag
    `abs(Regex−LLM) > 1,00 €` → `llm_konflikt`; ebenso Regex=0/LLM>0.
  - Anzeige im Frontend über 🔬-KI-Badge/-Dialog (`DokumenteSection.jsx`, `llm_konflikt`).
- **Deckt den Sorgen-Fall ab:** 1.247,83 → 1.250,00 = 2,17 € > 1 € ⇒ Konflikt wird angezeigt.
  Auch der „Regex blind"-Fall (nur LLM hat Wert) ist geflaggt.

**Schmale Restlücken (bewusst offen, kein Bau-Anlass):** (a) Abrechnungs-Pfad vergleicht nur
den **Gesamtbetrag**, nicht jede Einzelposition — eine sich in der Summe aufhebende
Positions-Rundung fällt nicht auf; (b) Cross-Check läuft nur bei aktivem LLM-Shadow-Mode
(ist das LLM aus, gibt's keinen LLM-Rundungsfehler, aber auch keinen Abgleich).

**Wenn überhaupt umsetzen:** nur die eine Prompt-Zeile (Beträge als String ins JSON) — und
das eher, um die **Anzahl** der Konflikt-Flags zu senken, nicht um Fehler zu fangen. Der
Existenz-Validator (Stufe 3) bringt gegenüber dem bestehenden Konsens-Check kaum Zusatznutzen.

---

## Kernproblem

Ein LLM liest Zahlen nicht ab, sondern sagt Token voraus. Glatte, häufige Zahlen sind wahrscheinlichere Tokenfolgen als krumme Beträge. Das Runden ist damit **modellinhärent**, nicht wegprompbar. Konsequenz: die LLM-Ziffern dürfen bei haftungsrelevanten Beträgen **nicht die alleinige Wahrheitsquelle** sein.

---

## Zielarchitektur: dreistufig

Jede Stufe hat einen **distinkten** Fehlertyp, den sie fängt. Keine ist redundant.

### Stufe 1 + 2 — Konsens-Check (bereits vorhanden / geplant)

Zwei **unabhängige** Extraktionen über denselben OCR-Text:

- **Regex-Pass:** zieht alle Geldbeträge deterministisch. Kann per Definition nicht runden — liest exakt die dastehenden Ziffern.
- **Qwen-Pass:** zieht Beträge + semantische Zuordnung (welcher Betrag ist Netto-Reparatur, welcher Wertminderung, welcher SB).

**Regel:** Übereinstimmung → ok. Abweichung → Flag in Review-Queue.

Fängt: *Uneinigkeit* der beiden Extraktoren.

### Stufe 3 — Existenz-Validator (die neue Idee)

Läuft **ausschließlich** über das Qwen-JSON, **nach** dem Konsens-Check. Fragt pro Betrag:

> Lässt sich dieser von Qwen ausgegebene Betrag **normalisiert** wortwörtlich im OCR-Quelltext wiederfinden?

- Treffer → bestätigt.
- Kein Treffer (weil gerundet/geglättet) → Flag in Review-Queue.

Fängt: *Rundung durch Qwen* — auch dann, wenn der Regex-Pass an der Stelle **blind** war (z. B. OCR hat Tausenderpunkt verschluckt, Regex fand den Betrag gar nicht → Konsens-Check hatte nichts zum Vergleichen). Das ist das **Netz unter dem Netz** und adressiert exakt die Hauptsorge.

---

## Kritischer Implementierungspunkt: Normalisierung vor Vergleich

Qwen-JSON **nicht** stumpf im Roh-OCR suchen. Beide Seiten vorher auf eine **kanonische Ziffernform** bringen, sonst Fehlalarm-Flut durch reines Formatierungsrauschen (→ Validator wird zum Lärmgenerator, den niemand mehr ernst nimmt).

Zu normalisieren (beidseitig):
- Tausendertrenner entfernen (`.` bzw. schmales/normales Leerzeichen: `1.247` / `1 247` → `1247`)
- Dezimaltrenner vereinheitlichen (`,` ↔ `.`)
- Währungssymbol/-code strippen (`€`, `EUR`, ` E`)
- Whitespace-Varianten (NBSP, schmales Leerzeichen) glätten
- Vergleich dann auf **reiner Ziffernfolge** (z. B. `124783`)

## Randfälle deutsches Geldbetragsformat (für Regex + Normalisierung)

- fehlende Tausenderpunkte (`1247,83`)
- `EUR` vs. `€` vs. nachgestellt vs. vorangestellt
- Gutschriften/negative Beträge: nachgestelltes Minus (`1.247,83-`), Klammern (`(1.247,83)`), führendes Minus
- OCR-Artefakte: `O`/`0`-Verwechslung, verrutschtes Komma, doppelte Leerzeichen
- schmales Leerzeichen als Tausendertrenner (`1 247,83`)

## Grenze des Existenz-Checks (bewusst akzeptiert)

Steht dieselbe Ziffernfolge mehrfach auf der Seite (Zwischensumme = Endsumme), beweist ein Treffer nicht, *welches* Vorkommen gemeint war. **Für den Zweck hier irrelevant:** ein *gerundeter* Wert taucht gar nicht auf → der Rundungsfall wird zuverlässig gefangen. Die Mehrdeutigkeit „welches Vorkommen" ist ein separates Problem, nicht Teil dieser Erweiterung.

---

## Ergänzende Prompt-Hebel (dämpfen, ersetzen nicht)

- **Temperatur 0** → Modell folgt eher der exakten Ziffernfolge, rundet weniger.
- **Beträge als String ins JSON** (`"betrag": "1.247,83"`) statt als Zahl → Modell behandelt den Wert als zu *kopierende* Zeichenkette statt als zu *produzierenden* Zahlenwert; senkt den Glättungsdrang spürbar. Kostet nichts — als Erstes testen.

---

## Einordnung in bestehende Architektur

- Kosten: Millisekunden, deterministisch, keine zusätzliche Modellinferenz.
- Passt zum Prinzip „menschliche Freigabe = einzige Schreiboperation": Validator **korrigiert nichts still**, sondern legt jede Diskrepanz dem Menschen in der Review-Queue vor.
- Verwandelt „ich hoffe, Qwen hat nicht gerundet" in „jede Abweichung landet garantiert vor einem Menschen".

---

## Abgrenzung / nicht Teil dieser Erweiterung

- Läuft **parallel** zu den aktuellen Intake-Themen (OCR-Qualität, Text-/Bildseiten-Erkennung, damit nur Textseiten OCRt werden). Kein Abhängigkeitskonflikt.
- Nur Konzept — Regex-Muster und Normalisierungsfunktion werden in der Coding-Session ausformuliert.
