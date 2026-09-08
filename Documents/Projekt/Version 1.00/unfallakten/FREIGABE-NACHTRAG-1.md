# FREIGABE-NACHTRAG 1
Stand: 2026-07-10 · Freigegeben durch RA Schatz · ergänzt FREIGABE.md

Kontext: Stufe 1 ist bis einschließlich P1.7 implementiert (Review-Queue in
Betrieb), P1.8 (Backfill) bewusst zurückgestellt. Die folgenden Punkte sind
daher teils **Retrofit** an bestehendem Neu-Pfad-Code, teils Präzisierungen
für noch offene Stufe-2-Blöcke. Quelle: Review-Auswertung (extern) +
Besprechung. Kein Punkt ändert die Architektur — alles sind Ergänzungen
innerhalb der beschlossenen Struktur.

## A. Retrofit am bestehenden Code (Priorität in dieser Reihenfolge)

**N-01 — Textebenen-Qualitätscheck vervollständigen (Retrofit S1.6a).**
Der Brauchbarkeits-Check der Textebene umfasst zwingend BEIDE Prüfungen:
Zeichensalat-Ratio UND Wörterbuch-Abgleich (Liste häufiger deutscher Wörter
+ Rechtsbegriffe). Hohe Textdichte ohne Wörterbuch-Treffer = korruptes
Font-Encoding → harter Fallback auf Bild-Rendering + OCR. Golden-File mit
korrupter Font-Kodierung ins Testset. Prüfen, ob die aktuelle Implementierung
nur den Zeichen-Check macht — falls ja, nachrüsten.

**N-02 — OCR-Qualitätsmetriken persistieren (Retrofit S1.6a).**
Zeichensalat-Ratio und Wörterbuchquote nicht nur berechnen, sondern als
Felder am intake_dokument speichern; Review-Queue bietet sie als
Sortier-/Hinweissignal an (Badge bei schlechter OCR-Qualität).

**N-03 — Retry-Differenzierung (Retrofit S1.6a-Queue).**
GLM-/LLM-Fehler klassifizieren statt pauschal retrien:
- Timeout → Retry mit Backoff (wie bisher)
- Ressourcendruck (Verbindungsfehler/Überlast) → Dokument zurückstellen,
  naechster_versuch verschieben
- Reproduzierbarer Modellfehler → KEIN Retry; Dokument läuft im
  Tesseract-Primär-Modus weiter (bestehender Feature-Flag-Pfad),
  Hinweis am Dokument.

**N-04 — Seiten-Triage vor OCR (Retrofit S1.6a).**
Vor dem GLM-Aufruf billige Heuristik pro Seite (Tesseract-Schnellpass /
Textdichte): Foto-/Bildseiten ohne nennenswerten Text NICHT durch GLM,
sondern als Bildseite markieren (bleiben in der Arbeitskopie sichtbar).
GLM läuft nur auf texttragenden Seiten. Erwartung: größter
Durchsatzgewinn bei Gutachten mit Foto-Anlagen.

**N-05 — Kooperatives Yielding + Teilergebnisse (Retrofit S1.6a-Worker).**
Der Worker prüft zwischen den Seiten eines Dokuments, ob ein höher
priorisiertes Dokument in der Queue wartet — wenn ja: laufendes Dokument
nach der aktuellen Seite parken (Status laeuft_pausiert, Seitenfortschritt
persistiert), später fortsetzen. Bei Abbruch/pipeline_fehler bleiben
bereits verarbeitete Seiten erhalten; Review-UI zeigt Teiltext +
Fehlerdetail statt nichts. KEIN hartes Seitenlimit einführen.

**N-06 — Seitenauswahl für die Extraktion (Retrofit S1.6b).**
Bei mehrseitigen Dokumenten erhält die Qwen-Extraktion nicht die ersten
10.000 Zeichen, sondern: Seite 1 + letzte Seite + Seiten mit
Regex-Treffern + Seiten mit Tabellen. Die Klassifikation bleibt
unverändert bei Seite 1 + letzter Seite (F-11).

**N-07 — Bestandsakten-Hinweis statt Backfill (Retrofit P1.7-Dashboard).**
Da P1.8 zurückgestellt ist: Akten, deren Anlage vor dem Einführungsdatum
des Ereignismodells liegt (bzw. ohne Ereignis vor Datum X), zeigen im
Positions-Dashboard einmalig: „Ereignishistorie beginnt am [Datum] —
ältere Vorgänge siehe Regulierung." Nutzt die AbleitungBadge-Mechanik.
P1.8 bleibt jederzeit nachholbar (herkunft='backfill' unverändert
vorgesehen).

**N-08 — Baseline-Messung „Sekunden pro Freigabe" (Retrofit S1.8).**
Zeitstempel Queue-Öffnung → Freigabe erfassen (Umfeld korrektur_log).
Zweck: Vorher-Baseline für die Stufe-2-Entscheidung Bounding-Boxes/PDF.js —
ohne Baseline keine belastbare Lohnt-sich-Aussage.

## B. Betriebs-Prüfpunkte SQLite-Mehrbenutzerbetrieb (vor Kollegen-Rollout)

**N-09 — SQLite-Konfiguration verifizieren.** (a) PRAGMA journal_mode=WAL
aktiv; (b) busy_timeout (z. B. 5000 ms) zentral an der Connection-Erzeugung;
(c) keine offene Schreibtransaktion um OCR-/LLM-/RA-MICRO-Aufrufe —
Alt-Routen mit rohem sqlite3 daraufhin durchsehen.

**N-10 — Backup-Frequenz erhöhen.** Stündliches Online-Backup
(`sqlite3 <db> ".backup <ziel>"`) per Cron/Scheduler zusätzlich zum
bestehenden Backup, sobald mehrere Nutzer/Portal produktiv schreiben.

**Entschieden und abgehakt (nicht umsetzen):** PostgreSQL-Migration (nein —
WAL + busy_timeout genügen für 6 Arbeitsplätze + Portal-Volumen);
Tesseract nur on demand (nein — CPU-parallel, TSV wird für alle Seiten
gebraucht); Regex-führend statt LLM-führend (nein — Shadow-Mode-Umkehrung
bleibt beschlossen); Layout-Graph vor Extraktion (nein — dupliziert
GLM-Leistung); Embedding-Index fürs Beteiligten-Matching (nein —
deterministische Normalisierung lt. N-11); Perceptual-Hash-Dedup (Stufe 3,
nicht jetzt); nächtlicher RA-MICRO-Index fürs Matching (nein — Live-SELECTs
bleiben, veralteter Index wäre schädlich).

## C. Präzisierungen für kommende Stufe-2-Blöcke (nur vormerken)

**N-11 — Beteiligten-Matching:** deterministische Namensnormalisierung
(Umlaut-Transliteration, Rechtsform-Stripping, Whitespace) vor dem
Abgleich. Keine Embeddings.

**N-12 — Bounding-Box-Lokalisierung:** Fuzzy-Match mit Entnormalisierung —
für Datums-/Betragsfelder Oberflächenvarianten erzeugen (04.11.2026 →
4.11.26 / 04. Nov. 2026 / …) und alle Kandidaten in der TSV suchen;
Levenshtein-Toleranz für übrige Felder. Beim GLM-Setup Sekunden/Seite
messen und dokumentieren.

## Arbeitsauftrag für die Coding-Session

Abschnitt A in der Reihenfolge N-01 → N-08 umsetzen. Vor jedem Punkt kurz
prüfen, ob der bestehende Code das Verhalten schon teilweise abdeckt
(insbesondere N-01, N-03), und nur die Differenz bauen. Jeder Punkt einzeln
testbar, bestehende Golden-File-Tests bleiben grün. Abschnitt B ist
Konfigurations-/Betriebsprüfung (kein Feature-Code außer N-10-Cronjob).
Abschnitt C wird NICHT jetzt implementiert.
