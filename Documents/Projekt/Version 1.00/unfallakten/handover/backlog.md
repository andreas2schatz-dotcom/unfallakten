# Backlog – Unfallakten-Verwaltungssystem
> Geplante Features und Ideen, die noch nicht in Entwicklung sind.
> Format: Priorität | Titel | Kurzbeschreibung

---

## Offen

### [PRD-29] E-Akte Auto-Parser: Schlagwort-Filter E-Brief
**Priorität:** mittel  
**Status:** ✅ Abgeschlossen (2026-04-11)  
**Beschreibung:** Ausgehende E-Mails via `Schlagwort="E-Brief"` gefiltert.
DKz-Feld existiert nicht in tblElo_AktenArchiv – Schlagwort-Lösung gewählt.  
**PRD:** `handover/PRD-29_EAkte_Filter_DKz.md`

---

### [PRD-33] Feintuning Klage-Wizard
**Priorität:** mittel
**Status:** Debugging-Pass – nächste Session (2026-04-18)
**Beschreibung:** Qualitäts-Pass am generierten DOCX (PRD-26):
- Formatierung: Absätze, Leerzeilen, Zeilenumbrüche in `klage_service.py`
- Textbausteine einzelner Schritte inhaltlich überarbeiten (Sachverhalt, Anträge, Gebühren)
- Platzhalter-Kontrolle, Rubrum bei mehreren Beklagten, RVG-Betrags-Einbindung
**Debugging-Vorbereitung:** `handover/session_handover_v52.md` → Abschnitt "Nächste Session"

---

### [PRD-27] ReguWizard – Stellungnahme zum Abrechnungsschreiben
**Priorität:** mittel
**Status:** Planung offen
**Beschreibung:** Geführter Wizard zur Erstellung einer Stellungnahme auf ein
Abrechnungsschreiben des gegnerischen Haftpflichtversicherers. Schrittweise durch
Kürzungspositionen führen, Gegenargumente auswählen, Word-Export.
**PRD:** `handover/PRD-27_ReguWizard.md`

---

## In Entwicklung

### [PRD-32] Rechnungstypen-Parser: Subklassifizierung & Beleg-Mapping
**Priorität:** mittel
**Status:** ✅ Abgeschlossen Phase 1 (2026-04-14)
**Beschreibung:** `document_classifier.py` erkennt bisher nur generisch `"rechnung"`.
Standkosten- und Abschlepprechnung landen nicht automatisch bei der richtigen Schadenposition.
Lösung: Subklassen `standkostenrechnung`, `abschlepprechnung` etc. via Signallisten.
**Plan:** `handover/PRD-32_Rechnungstypen_Parser.md`

---

### [PRD-30] OCR + Streaming-Parser für Bild-PDFs
**Priorität:** hoch  
**Status:** ✅ Abgeschlossen (2026-04-12)  
**Beschreibung:** pytesseract + pdf2image, SSE-Streaming, Auth via ?token=  
**Plan:** `handover/PRD-30_OCR_SSE.md`

---

### [PRD-31] KI-Parsing für Gutachten
**Priorität:** mittel  
**Status:** ✅ Abgeschlossen (2026-04-14)  
**Beschreibung:** LLM Shadow-Mode für Gutachten. Qwen läuft parallel zum Regex-Parser.
Per-Position-Konfliktanzeige und Regex/KI-Auswahl im "🔬 KI"-Dialog.
KI-Werte können per Korrektur-Endpoint in parse_json gespeichert und für Schadenbelege genutzt werden.

---

## Abgeschlossen
- Regulierungs-Workflow Redesign (Option B) – 5 Phasen: Aggregationsbug, View-Migration 37, Legacy-Ablösung, Provenance-Map, UX (2026-04-18)
- PRD-34  – Inbox-Pattern Dokumente-Kachel (KLASSE_TO_POS, Inline-Zuordnung, Beleg-x-Button, Highlight)
- PRD-22c – Mandanten-Fragebogen
- PRD-22d – E-Mail-Import UI
- PRD-23b – Rechnungs-Parser
- PRD-25a – Automatische Fristen
- PRD-25b – Action-Dashboard
- PRD-26  – Klage-Wizard (10 Steps)
- PRD-28  – Gebührenassistent Nr. 2300 VV RVG (inkl. Kostennote DOCX)
- PRD-29  – Schmerzensgeld-Ermittlungstool
- PRD-29b – E-Akte Auto-Parser: Schlagwort-Filter E-Brief
- PRD-30  – OCR + SSE-Streaming für Bild-PDFs (pytesseract, pdf2image, EventSource)
- KI-Parsing Regulierungsschreiben – LLM Shadow-Mode, Konflikterkennung, Betrag-Auswahl UI, WBA, SV-Kosten-Fix, ADAC-Erkennung, Positions-Konflikt
- PRD-31 – KI-Parsing für Gutachten (Shadow-Mode, 7-Felder-Vergleich, Konflikt-Dialog, Korrektur-Endpoint)
