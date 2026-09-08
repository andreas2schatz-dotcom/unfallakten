# Nächste Session: Intelligente Sachstandsanfrage — Neuplanung auf dem Ereignis-Modell (PRD-25d v2)

## Prompt-Vorschlag

> Lies `handover/2026-08-11-sachstandsanfrage-review-befunde.md` (Abschnitte 1, 2, 5, 6)
> und starte ein Brainstorming zur Neuplanung der intelligenten Sachstandsanfrage auf
> dem Ereignis-Modell. Der alte Plan `handover/PRD-25d_Intelligente_Sachstandsanfrage.md`
> ist veraltet (basiert auf dem verworfenen aktenchronik_service). Kein Code, erst Design.

## Kontext

- **Review 2026-08-11 abgeschlossen**, Sofort-Fixes (M-1, M-2, G-1, G-2, G-3, G-7) sind
  umgesetzt und committet (`3787e24e`, Branch `abschlussbericht`). 19 BE-Tests in
  `backend/tests/test_sta_service.py` + 4 FE-Tests sichern den Bestand ab.
- Es gibt **drei Erzeugungswege** (Tabelle in Befund-Katalog Abschnitt 1):
  A StaDialog (intelligent), B RA-MICRO-Kanzleivorlage (nur aktivitaeten-Log),
  C Legacy-word_route (statisch, FE-tot).

## Zu lösende Kernbefunde

1. **K-1:** Eskalation ignoriert eingegangene Antworten — `antwort_2w`-Todos werden nie
   automatisch erledigt; das Ereignis-Modell (`ereignisse`, z. B. `abrechnung_eingegangen`)
   wird nicht konsultiert. Neue Analyse: „letztes unbeantwortetes Schreiben" = letztes
   ausgehendes Ereignis ohne späteres eingehendes.
2. **K-2:** Weg B registriert kein Dokument/Ereignis → für die Stufenlogik unsichtbar.
3. **K-3:** Keine Rundenlogik (`sta_anzahl` zählt lebenslang); Tage-Zähler resettet mit
   jedem eigenen Schreiben statt ab Forderungsschreiben zu messen.
4. **M-3–M-6 mitnehmen:** RA-MICRO-Adress-Fallback + KANZLEI_INFO im STA-Pfad,
   Legacy-Weg C sperren/umleiten, Best-effort-Registrierung ehrlich machen,
   Stufe persistieren (Dokument-/Ereignis-Metadaten).
5. **Aus dem alten PRD noch offen:** Betrag im Text, §3a-PflVG-Auswertung,
   „Klage statt 3. STA"-Empfehlung (Klage-Wizard-Verweis), Action-Board-Chip,
   WiedervorlageView → intelligenter Dialog.
6. **Zielbild:** Weg A + B fusionieren — Stufentext des `sta_service` in die echte
   Kanzlei-Vorlage (`sachstandsanfrage_wv.py`-Platzhaltermechanik + neuer
   `{{BRIEFTEXT}}`-Platzhalter in `sachstandsanfrage_vorlage.docx`).

## Randbedingungen

- RA-MICRO strikt read-only; Ereignisse NUR über `ereignis_service` schreiben
  (Pipeline-v7-Invariante); Registries fail-loud.
- Memory-Eintrag: `project_unfallakten_sachstandsanfrage_review` +
  `project_unfallakten_prd25d_ereignismodell`.
