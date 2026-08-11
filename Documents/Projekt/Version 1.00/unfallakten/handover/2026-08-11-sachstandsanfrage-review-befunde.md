# Code-Review Sachstandsanfrage — Befundkatalog

> Review: 2026-08-11 · Nur Bestandsaufnahme, kein Code geändert.
> Fokus: „Weiß die Sachstandsanfrage, was abgefragt wurde, ob es schon eine STA gab,
> und eskaliert sie den Text entsprechend?"
>
> **Fix-Status (Sofort-Fix-Runde am selben Tag, TDD):**
> ✅ behoben: M-1, M-2 (inkl. Dativ + Relativpronomen), G-1, G-2, G-3, G-7 (19 neue
> BE-Tests `test_sta_service.py` + 4 neue FE-Tests) ·
> ⏳ offen: K-1, K-2, K-3, M-3, M-4, M-5, M-6, G-4, G-5, G-6 (→ Neuplanung auf
> Ereignis-Modell, siehe Abschnitt 6 Punkt 2+3)

---

## 1. Bestandsaufnahme: Es gibt DREI Erzeugungswege

| Pfad | Einstieg | Code | Registriert in `dokumente`? | Eskalation? |
|---|---|---|---|---|
| **A – „Intelligent" (PRD-25d)** | StaDialog (WordSection-Karte „Sachstandsanfrage · Intelligent" + Button „📤 STA senden" in AkteDetailView) | `sta_routes.py` → `sta_service.py` → `word/sachstandsanfrage.py` (brieftext-Modus) | ✅ ja (+ 2-Wochen-Todo + P1.4-Ereignis) | ✅ 3 Stufen |
| **B – RA-MICRO-Vorlage** | `RaMicroSachstandsCard` (WordSection), WiedervorlageView (einzeln + Batch-ZIP) | `wiedervorlage_routes.py` → `word/sachstandsanfrage_wv.py` (echte Kanzlei-Vorlage, Unterschriftsbild) | ❌ nein — nur `aktivitaeten`-Logeintrag | ❌ keine |
| **C – Legacy-API** | kein Frontend-Einstieg mehr, aber API-erreichbar: `POST /akten/<az>/dokumente/word` mit `typ=sachstandsanfrage` (+ `/vorschau`) | `word_routes.py` → `word_service.py` → `word/sachstandsanfrage.py` (statischer Pfad Z. 106–210) | ✅ ja (+ Todo + Ereignis) | ❌ statischer Text, hartcodierte 7-Tage-Frist |

Die Stufenlogik in `sta_service.py` existiert und ist im Kern richtig gedacht
(Stufe 1 Erinnerung / 2 Mahnung / 3 Klage-Ankündigung, Texte + Fristen über die
`konfiguration`-Tabelle einstellbar, Einstellungen-Tab „⏱ Fristen" ist korrekt
verdrahtet). **Das Feature ist aber nicht „sauber":** die Analyse schaut auf die
falschen Datenquellen und zwei der drei Erzeugungswege sind für sie unsichtbar.

---

## 2. Kritische Befunde (Kernanspruch „die STA weiß Bescheid" verfehlt)

### K-1 · Eskalation ignoriert eingegangene Antworten der Versicherung
`analysiere_regulierung()` (`sta_service.py:70`) stützt sich auf offene
`antwort_2w`-Todos bzw. das neueste ausgehende Dokument. **Nichts im System
erledigt diese Todos automatisch**, wenn ein Regulierungs-/Abrechnungsschreiben
oder eine Zahlung eingeht (einziger Schreibweg auf `erledigt` ist der manuelle
Todo-Endpoint `todos_routes.py:161`). Folge: Auch wenn die Versicherung längst
geantwortet hat, zeigt der Dialog „X Tage ohne Antwort" und empfiehlt Stufe 2/3.
Das Ereignis-Modell (`ereignisse`, z. B. `abrechnung_eingegangen`) — seit
Pipeline v7 die SSOT für den Aktenverlauf — wird **gar nicht konsultiert**.
Genau das ist der in `docs/TODO.md` (PRD-25d-Backlogeintrag) notierte
Umstellungsbedarf.

### K-2 · Weg B (Kanzlei-Vorlage) ist für die Intelligenz unsichtbar
`wiedervorlage_routes.py` schreibt nur einen `aktivitaeten`-Text
(„Sachstandsanfrage generiert für AZ …"), aber **keinen `dokumente`-Eintrag,
kein Todo, kein Ereignis**. Wer die Karte „Daten aus RA-Micro Wiedervorlage"
oder die WiedervorlageView (inkl. Batch) benutzt, erzeugt STAs, die
`sta_anzahl` und `tage_ohne_antwort` nie sehen — der StaDialog empfiehlt danach
fälschlich Stufe 1 „erste STA". Der ✓-Marker „bereits erstellt" wird zudem per
Regex aus dem Beschreibungs-Freitext extrahiert
(`wiedervorlage_routes.py:342-349`) — fragil.

### K-3 · Stufenermittlung kennt keine Runden und misst die falsche Zeitspanne
`_empfohlene_stufe()` (`sta_service.py:229`): `sta_anzahl` zählt **alle jemals
registrierten** STA-Dokumente der Akte. Nach einer beantworteten ersten Runde
und einem neuen Forderungsschreiben (2. Abrechnungsrunde) startet die Empfehlung
sofort bei Stufe 2/3 statt bei 1. Außerdem misst `tage_ohne_antwort` die Tage
seit dem **letzten eigenen Schreiben** (also ggf. seit der letzten STA), während
das Stufe-3-Kriterium laut PRD „>42 Tage seit dem Forderungsschreiben" meint —
mit jedem Schreiben resettet der Zähler, die Eskalation verzögert sich beliebig.

---

## 3. Mittlere Befunde

### M-1 · Die zwei Dialog-Einstiege übergeben unterschiedliche AZ-Formate
`WordSection.jsx:105` übergibt `akte.az || akte.id`, `AkteDetailView.jsx:468`
`akte.az_roh || akte.az`. Je nach Öffnungsweg (z. B. aus dem ActionBoard, wo
`az_roh` die **volle** RA-MICRO-Form „312/26 AS" ist und `App.jsx:139` sie als
`akte.az` in den Tab schreibt) bekommt der StaDialog die AZ mit SB-Kürzel.
Backend-Abfragen (`unfallakte WHERE az = ?`, `todos.akte_az`,
`dokumente.akte_id`) laufen dann ins Leere: Kontext-Analyse liefert 0 Treffer,
`POST /sta/generieren` einen 404. WordSection sollte wie AkteDetailView die
Basis-AZ übergeben. (Generell: die `az`/`az_roh`-Semantik ist zwischen
ActionBoard und App.jsx invertiert — Aufräumkandidat.)

### M-2 · Genus-Fehler im generierten Anwaltsbrief
`generiere_sta_text()` baut `schreiben_ref = "unser {typ_label} vom …"`
(`sta_service.py:179`). Sobald das letzte Schreiben eine Sachstandsanfrage oder
Stellungnahme ist — bei Stufe 2/3 der Regelfall — steht im Brief **„unser
Sachstandsanfrage vom …"** statt „unsere Sachstandsanfrage". Zusätzlich passt
der Stufe-2-Satz „haben wir Ihnen mit {Schreiben} die Schadensersatzansprüche
angezeigt" inhaltlich nur, wenn {Schreiben} das Forderungsschreiben ist.
**Fix-Nachtrag:** Beim Fixen zeigte sich, dass der Fehler größer war als im
Review notiert — auch „mit {Schreiben}" (Stufe 2/3) war für JEDEN Typ falsch
dekliniert („mit unser Forderungsschreiben") und das Relativpronomen in Stufe 1
(„…, mit dem wir") passte nicht zu femininen Typen. Lösung: neuer Platzhalter
`{SchreibenDativ}` (Dativ), `{Schreiben}` jetzt genus-korrekt im
Nominativ/Akkusativ, Stufe-1-Default nutzt invariantes „womit". Kanzlei-eigene
Text-Overrides in der `konfiguration`-Tabelle, die noch „mit {Schreiben}"
enthalten, müssten manuell auf `{SchreibenDativ}` umgestellt werden
(Platzhalter-Hinweis in den Einstellungen ergänzt).

### M-3 · Kein RA-MICRO-Fallback und keine Kanzlei-Stammdaten im STA-Pfad
`sta_routes.py:84-116` lädt Mandant/Gegner ausschließlich aus SQLite
(`LIMIT 1` ohne `ORDER BY` → bei mehreren Gegnern nichtdeterministisch) und
übergibt `kanzlei=None`. Der RA-MICRO-Adress-Fallback aus `word_service.py`
gilt nur für `forderungsschreiben/abrechnungsuebersicht/abschlussbericht` —
die STA-Route umgeht `word_service` komplett. Folge bei Bestandsakten mit
RA-MICRO-only-Beteiligten: Empfängerblock „[Versicherung] / [PLZ Ort]".
`kanzlei=None` heißt außerdem: die per Env konfigurierbaren `KANZLEI_INFO`
werden ignoriert, der Briefkopf kommt aus dem Hardcode-Fallback in
`styling.py:117` (Duplikat der Stammdaten).

### M-4 · Legacy-Pfad C erzeugt einen abweichenden Zweitbrief desselben Typs
`typ=sachstandsanfrage` ist über die Registry (`richtung: ausgehend`) weiterhin
in `gueltige_dok_typen()` und damit per API generierbar: statischer Text,
hartcodierte 7-Tage-Frist (`sachstandsanfrage.py:59`), keine Stufen — aber mit
`dokumente`-Eintrag, der wiederum `sta_anzahl` hochzählt. Der statische
Briefkörper (Z. 106–210) ist vom Frontend aus **toter Code**. Empfehlung:
entweder Route auf `sta_service`-Text umleiten oder den Typ dort sperren und
den statischen Pfad entfernen.

### M-5 · „Best effort"-Registrierung meldet Erfolg, obwohl nichts registriert wurde
In `sta_generieren` (`sta_routes.py:138-151`) wird das DOCX auch dann
ausgeliefert, wenn `registriere_dokument`/`setze_antwort_frist` scheitern (nur
`logger.warning`). Der Dialog zeigt trotzdem „✓ … 2-Wochen-Todo angelegt".
Diese STA existiert dann für die Eskalationslogik nicht (Zähler, Todo, Ereignis
fehlen). Zudem wird die Datei **vor** der Registrierung auf Platte geschrieben —
bei Fehlern bleibt eine Waisen-Datei in `uploads/` zurück.

### M-6 · Die Stufe wird nirgends persistiert
Die gewählte Stufe landet nur im Dateinamen. Weder `dokumente` noch das
P1.4-Ereignis speichern sie — die Historie kann später nicht beantworten
„welche Mahnstufe hatte die letzte STA?", und die Stufenermittlung muss alles
aus der Anzahl ableiten (verstärkt K-3).

---

## 4. Geringe Befunde / Codeleichen

- **G-1 · PII-Debug-Logging in Produktion:** `wiedervorlage_routes.py:244-246`
  („DEBUG – temporär") loggt bei jeder WV-Generierung sämtliche Adressdaten des
  Empfängers auf WARNING-Level. Entfernen.
- **G-2 · Hartcodierte Fristanzeige im Dialog:** `StaDialog.jsx:16-20` zeigt
  „14/7/5 Tage" fest im Stufen-Chip — wer die Fristen in den Einstellungen
  ändert, sieht im Dialog weiterhin die alten Werte (der Brieftext stimmt, nur
  das Label nicht).
- **G-3 · Ungenutztes `textareaRef`** in `StaDialog.jsx:32` (gesetzt, nie gelesen).
- **G-4 · `RaMicroSachstandsCard` lädt bei jedem Mount die komplette WV-Liste**
  (`apiWV.liste()`), um per `startsWith` einen Treffer zu suchen — pro
  Akten-Öffnung ein RA-MICRO-Roundtrip über alle Wiedervorlagen.
- **G-5 · `sta_kontext` liefert für unbekannte AZ keinen 404**, sondern einen
  leeren Kontext mit Stufe 1 — Tippfehler/falsche AZ (siehe M-1) fallen nicht auf.
- **G-6 · Stille Fallbacks in `_frist_tage`/`_lese_text_template`:**
  `except Exception: pass` — eine kaputte Konfiguration (z. B. nicht-numerischer
  Wert) fällt unbemerkt auf die Defaults zurück; je Aufruf eine eigene
  DB-Verbindung (3 Verbindungen pro Kontext-Request).
- **G-7 · Null Testabdeckung für die Intelligenz:** Kein einziger Test für
  `sta_service` (`_empfohlene_stufe`, Template-Ersetzung), `sta_routes` oder
  `StaDialog`. Getestet sind nur der Legacy-Generator (test_modul5) und die
  WV-Variante (test_modul8). Die Stufenlogik — das Herzstück — ist ungetestet.

---

## 5. Gap-Analyse: Ist vs. Ziel (deine Beschreibung + PRD-25d)

| Anforderung | Status |
|---|---|
| Weiß, **was** abgefragt wurde (Bezug aufs letzte Schreiben) | ⚠️ teilweise — Typ+Datum ja, aber ohne Betrag (`{betrag_gesamt}` aus dem PRD fehlt) und ohne Prüfung, ob es beantwortet wurde (K-1) |
| Weiß, **ob es schon eine STA gab** | ⚠️ nur für Weg A/C; Weg B unsichtbar (K-2), keine Rundenlogik (K-3) |
| **Eskaliert den Text** je Mahnstufe | ✅ vorhanden (3 Stufen, konfigurierbar) — mit Textfehler M-2 |
| Erkennt Versicherer-Antwort (`letzte_antwort_versicherer`) | ❌ fehlt komplett (K-1) |
| §3a-PflVG-Bezug in Stufe 2/3 | ❌ fehlt (Todo `pflvg_3a` existiert, wird nicht ausgewertet) |
| Stufe 3 = Empfehlung „Klage statt weiterer STA" (Klage-Wizard-Verweis) | ❌ fehlt — Stufe 3 ist nur ein schärferer Brief |
| Integration: Action-Board-Chip „→ Sachstandsanfrage?" | ❌ fehlt |
| WiedervorlageView öffnet den intelligenten Dialog | ❌ fehlt — nutzt weiter den dummen Direktdownload (K-2) |
| Echtes Kanzlei-Briefpapier | ❌ nur Weg B hat die echte Vorlage; der intelligente Weg A rendert generisches python-docx-Design |

---

## 6. Empfehlung (Reihenfolge)

1. **Sofort-Fixes (klein, unabhängig):** M-1 (az_roh in WordSection), M-2
   (Genus über TYP_LABEL-Map mit Artikel), G-1 (Debug-Log raus), G-2, G-7
   (Tests für `_empfohlene_stufe` — lohnt vor jedem Umbau).
2. **Neuplanung der Analyse auf dem Ereignis-Modell** (wie in TODO/PRD-25d
   vorgesehen, eigenes Brainstorming): „letztes unbeantwortetes Schreiben" =
   letztes ausgehendes Ereignis ohne späteres eingehendes Ereignis;
   Antwort-Erkennung, Rundenlogik und §3a-Auswertung fallen dort natürlich an.
   Dabei M-6 mitnehmen (Stufe in die Ereignis-/Dokument-Metadaten).
3. **Vereinheitlichung der drei Wege:** Weg B registrieren (Dokument +
   Ereignis), perspektivisch Weg A und B fusionieren — Stufentext des
   `sta_service` in die echte Kanzlei-Vorlage einsetzen (Platzhalter-Mechanik
   aus `sachstandsanfrage_wv.py` existiert bereits, es fehlt nur ein
   `{{BRIEFTEXT}}`-Platzhalter). Weg C sperren oder umleiten (M-4).

## 7. Was sauber ist

Saubere Schichtung Service/Route/Generator; Konfigurierbarkeit der Texte und
Fristen über die `konfiguration`-Tabelle mit robusten Defaults und korrekt
verdrahtetem Einstellungen-Tab; durchdachte Dialog-UX (dirty-Warnung vor
Stufenwechsel, editierbarer Text, Stufen-Klemmung 1–3 an allen Eingängen);
P1.4-Ereignis wird im intelligenten Pfad korrekt best-effort geschrieben;
`sachstandsanfrage_wv.py` (Platzhalter-Ersetzung, XML-Escaping,
Unterschrifts-Fallback) ist solide gebaut.
