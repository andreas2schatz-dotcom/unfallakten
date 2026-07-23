# Prompt für die nächste Session: Kürzungstaxonomie Phase 0 (Handtest)

Kopiervorlage — als erste Nachricht einfügen:

---

Wir starten **Phase 0 der Kürzungstaxonomie: den Handtest**. Kein Produktivcode in dieser Phase — nur Analyse (Wegwerf-Skripte in `tools/` oder im Scratchpad sind erlaubt).

**Pflichtlektüre in dieser Reihenfolge:**
1. `docs/TODO.md` (Eintrag „Kürzungstaxonomie — Phase 0")
2. `handover/KONZEPT-Kuerzungstaxonomie-Vorgangsautomat.md` — **Abschnitt 12 ist der verbindliche Prozess-Stand** (revidiert + codebasis-verifiziert 2026-07-23); Abschnitte 2, 6 und 10 nur bei Bedarf als Hintergrund.
3. Die drei DECISIONS-Einträge vom 2026-07-23 in `docs/DECISIONS.md`.

**Auftrag (in dieser Reihenfolge):**
1. **Bestandsdaten ziehen:** Alle erfassten Kürzungen aus `pruefberichte.kuerzungen_json` und `regulierung_positionen` (`kuerzung_freitext`, `kuerzungsart_id`, Beträge). ⚠️ Aktive DB ist das Docker-Volume: `/app/data/unfallakten.db` im Container `unfallakten-backend-dev` — NICHT `backend/data/`. Jede Auswertung nennt Datum + DB (Prüfregel aus Abschnitt 12.1).
2. **Keyword-Matching-Prototyp:** Freitexte gegen die 19 `kuerzungsarten` (+ Stichworte aus den 34 Quelldateien in `tools/textbausteine/`) matchen. **Ground Truth = die manuell gesetzten `kuerzungsart_id`-Werte.**
3. **Zwei Kennzahlen berichten:** **Trefferquote** (Matching-Vorschlag = manuelle Zuordnung) und **Abdeckung** (Anteil realer Kürzungen, die überhaupt einen Baustein finden). Daraus: Empfehlung regelbasiert vs. LLM-Fallback + Vorschlag für die Phase-1-Zielwerte.
4. **Lücken-Liste:** Welche realen Kürzungen finden keinen Typ? Dazu die ~18 noch unzugeordneten Quelldateien aus `tools/textbausteine/` (Abschleppgebühren, JVEG, Reparaturbestätigung, HWS/Heilverlauf, Wertminderung-Steuer …) mit Zuordnungs-Vorschlag zur A–F-Taxonomie vorlegen — Entscheidung durch mich.
5. **30 Stichproben** mit mir durchgehen (Tiefenprüfung: passt der vorgeschlagene Baustein inhaltlich?).
6. **Nebenbei klären:** Warum ist `kuerzungsarten` Nr. 15 (Unkostenpauschale) leer, obwohl das Import-Mapping in `tools/import_textbausteine.py` sie vorsieht?

**Danach (noch in derselben oder der Folge-Session):** das Entscheidungs-Tor aus Abschnitt 12.6 vorbereiten — Ort der Kürzungsdaten (Tendenz Option b, siehe 12.5: Differenz-Mathematik existiert bereits in `eingehende_ereignisse._regulierungs_wirkungen()`) und Verhältnis der zwei Faltungen. Entscheidung dokumentieren in `docs/DECISIONS.md`, **bevor** Phase-1-Code entsteht.

**Regeln:** RA-MICRO strikt read-only · Befunde sofort in TODO/DECISIONS statt nur in Berichten · Deutsch, ich bin Anwalt, nicht Techniker · bei der Registry-Migration später: `verifiziert_am` = „handgeprüft RA Schatz, Juli 2026" stempeln (Urteilscheck entfällt, DECISIONS 2026-07-23).

---

*Erstellt 2026-07-23 nach Abschluss der Konzept-Verifikations-Session (Konzeptpapier Abschnitt 12, Klage-Wizard-Runde abgeschlossen, main gepusht bis `24b39b70`).*
