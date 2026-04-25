# Akten Action Board – Design Spec
**Datum:** 2026-04-25  
**Status:** Freigegeben  
**PRD:** PRD-31

---

## Zusammenfassung

Der Übersicht-Tab der Aktendetailansicht wird vom bisherigen passiven Akkordeon-Stapel zu einem aktiven **Action Board** umgebaut. Es dient als primäre Arbeitsoberfläche für jede Akte und ist der erste Tab den der Anwalt beim Öffnen einer Akte sieht.

Kernziel: Mit einem Blick erfassen was jetzt zu tun ist, und die häufigsten Aktionen direkt auslösen können – ohne in andere Tabs wechseln zu müssen.

---

## Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `frontend/src/sections/UebersichtSection.jsx` | Hauptumbau – neuer Action Board Header |
| `frontend/src/views/AkteDetailView.jsx` | Übersicht-Tab an erste Position, Standard-Tab |
| `frontend/src/api.js` | Neuer Endpunkt `pwaMessage()` |
| `backend/routers/akten_routes.py` | Neuer Stub-Endpunkt `POST /akten/<az>/pwa-nachricht` |
| `backend/db/schema_manager.py` | Kein Schema-Change nötig (`aktivitaeten` reicht) |

---

## Design System

Das Design folgt dem etablierten System aus `theme.js` und `.impeccable.md`:

- **Fonts:** Bricolage Grotesque (Labels, Abschnittstitel, AZ) · Figtree (Body, Todos, Beträge)
- **Primär:** Navy `#1B2A4A` (Header-Hintergrund, Struktur)
- **Akzent:** Terrakotta `#A06B4A` / Pale `#F3EAE2` (primäre Aktionsbuttons)
- **Hintergrund:** Pergament-Weiß `#F6F4EF` · Surface `#FAFAF8`
- **Borders/Neutrals:** warm Richtung Navy getönt (`#E2DDD3`)
- **Kein** Startup-Blau (`#3b82f6`) als Primärfarbe · kein Gradient-Text · keine border-left-Akzentstreifen

---

## Aufbau des Action Boards

Das Action Board ersetzt den bisherigen Inhalt von `UebersichtSection` als oberste Sektion. Die bestehenden Klapp-Abschnitte (RA-Micro, Forderungshistorie, Chronik etc.) bleiben darunter erhalten.

### 1. Akte-Header (Navy-Hintergrund)

```
┌─────────────────────────────────────────────────────────┐
│ 322/25 KS          Riccio ./. Alders                    │  ← AZ + Kurz auf einer Zeile
│ Riccio Mario ./. Alders Versicherung AG – Kfz-Unfall …  │  ← Langbezeichnung darunter
│─────────────────────────────────────────────────────────│
│ [💬 Nachricht → Mandant]  [📤 STA]  [+ Todo]  [📄 Frd]  │  ← Aktionsleiste
└─────────────────────────────────────────────────────────┘
```

**Typografie:**
- Aktenzeichen: Bricolage Grotesque, 1.5rem, bold, weiß, Monospace nur für das AZ selbst
- Kurzbezeichnung: Bricolage Grotesque, 1.1rem, semi-bold, `accentLight` (#C08F6C)
- Langbezeichnung: Figtree, 0.88rem, `textFaint`-äquivalent auf Navy

**Aktionsleiste** (Buttons, durch `border-top: 1px solid rgba(255,255,255,.1)` getrennt):

| Button | Stil | Aktion |
|---|---|---|
| 💬 Nachricht → Mandant (PWA) | Primär (Terrakotta) | Öffnet PWA-Modal |
| 📤 STA senden | Sekundär-Warm (Amber) | Öffnet StaDialog |
| + Todo | Ghost (weiß/transparent) | Öffnet Todo-Formular |
| 📄 Forderungsschr. | Ghost | Navigiert zu Word-Tab |
| ⬇ Word | Ghost-Dimmed | Navigiert zu Word-Tab |

Reihenfolge der Buttons spiegelt Häufigkeit der Nutzung wider. PWA-Nachricht ist prominent, weil neu und strategisch wichtig.

---

### 2. Status-Band (kompakte Checks)

Einzeilige Leiste unter dem Header, Hintergrund `surface` (#FAFAF8):

```
Checks  [✓ Vollmacht]  [✗ IBAN fehlt]  [⚠ RSV: Anfrage]  |  HQ 100%  §3a-Frist: 5 Tage  Verjährung: 31.12.26
```

**Check-Pills** (aus `mandant-checks`-Endpunkt, bereits vorhanden):

| Zustand | Farbe | Bedingung |
|---|---|---|
| `✓ Vollmacht` | `greenBg` + `greenText` | `vollmacht_vorhanden === true` |
| `✗ Vollmacht fehlt` | `redBg` + `redText` | `vollmacht_vorhanden === false` |
| `✓ IBAN` | `greenBg` + `greenText` | `iban_vorhanden === true` |
| `✗ IBAN fehlt` | `redBg` + `redText` | `iban_vorhanden === false` |
| `✓ RSV` | `greenBg` + `greenText` | `rechtsschutz_deckung === true` |
| `⚠ RSV: Anfrage` | `amberMid` + `amberText` | `rechtsschutz_deckung === "anfrage"` |
| `○ RSV: keine` | `surface` + `textFaint` | kein RSV-Beteiligter |

**Meta-Pills** (rechts der Trennlinie, aus Aktenstammdaten):

| Pill | Quelle | Kritisch wenn |
|---|---|---|
| HQ X % | `akte.hq` | < 100 → Amber |
| §3a-Frist: N Tage | aus Todos `frist_typ='gerichtlich'` oder berechnet | ≤ 7 Tage → Rot |
| Verjährung: TT.MM.JJ | aus Todos `frist_typ='verjaehrung'` | ≤ 60 Tage → Amber, ≤ 14 → Rot |

Fehlen Fristen-Todos, werden die Meta-Pills für §3a und Verjährung nicht angezeigt.

---

### 3. Finanz-Band

Blauer Hintergrundsstreifen (`blueBg` #eff6ff, `border-bottom: 1px solid` blueish), vier Werte nebeneinander + kleiner Fortschrittsbalken:

```
Gefordert        Reguliert        Noch offen       Kürzungen        [Fortschrittsbalken]
4.850,00 €       3.200,00 €       1.650,00 €       850,00 €         66% · 2 Schreiben
```

- **Gefordert:** `navy`-Farbe · aus `gesamtForderung` (bestehende Berechnung)
- **Reguliert:** `green` · aus `gesamtReguliert`
- **Noch offen:** `red` wenn > 0 · `gesamtForderung - gesamtReguliert`
- **Kürzungen:** `amber` · aus `gesamtKuerzung`
- **Fortschrittsbalken:** 6px, einfarbig `accent` (kein Gradient), Prozentangabe + Anzahl Schreiben

Werte werden live aus dem bestehenden `posMap`/`alleRows`-Berechnungsblock in `UebersichtSection` gezogen – keine neuen API-Calls nötig.

---

### 4. Zwei-Spalten-Body (To-Dos & Wiedervorlagen)

```
┌──────────────────────────┬──────────────────────────┐
│ 📋 To-Dos  [3 offen]     │ 📅 Wiedervorlagen [2]    │
│                          │                          │
│ ● STA Stufe 2    28.04.  │ ┌─ Rückmeldung Vers. ──┐ │
│ ● IBAN anfordern 02.05.  │ │  fällig 28.04.2026   │ │
│ ● Prüfbericht            │ └──────────────────────┘ │
│ + Erledigt (5) ›         │ ┌─ IBAN nachfassen ───┐  │
│                          │ │  fällig 02.05.2026  │  │
└──────────────────────────┴──────────────────────────┘
```

**Todo-Einträge:** Bestehende `TodoKachelKompakt`-Logik und Dringlichkeits-Dots übernehmen.  
**Wiedervorlage-Karten:** Bestehende `wvListe`-Logik aus `TodoKachelKompakt` übernehmen.  
**Spaltenaufteilung:** `grid-template-columns: 1fr 1fr`, bei schmaler Ansicht auf 1 Spalte fallback.  
**Kein separater Card-Wrapper** um den Body – direkte Integration als Sektion im Action Board.

---

### 5. Akkordeon-Strip (bestehende Inhalte, komprimiert)

Unterhalb des 2-Spalten-Bodys: eine horizontale Buttonleiste, die die bisherigen Klapp-Abschnitte aufklappt:

```
[🏛 RA-Micro Stammdaten ▾]  [📜 Forderungshistorie ▾]  [⚖️ Regulierungsdetails ▾]  [🕒 Chronik ▾]  [📝 Notizen ▾]
```

- Buttons: `font-size: 0.72rem`, `Figtree`, Hintergrund `surface`, Hover → `accentPale`
- Aufgeklappter Inhalt: Bestehende Komponenten (`RaMicroAkteUebersicht`, `ForderungshistorieKarte`, `RegulierungsTabelle`, `AktenTimeline`, Notizen-Textarea) unverändert übernehmen
- localStorage-Keys für Offen/Zu-Zustand bleiben erhalten (Kompatibilität mit bestehenden `KlappAbschnitt`-Keys)

---

## Navigation-Änderungen

### Übersicht als erster Tab

In `AkteDetailView.jsx`: Übersicht-Tab an **Index 0** statt an letzte Stelle. Standard-Tab beim Öffnen einer Akte ist Übersicht.

Bisherige Reihenfolge: Beteiligte · Unfall · Schaden · Dokumente · Gebühren · Regulierung · Klage · Word · **Übersicht**  
Neue Reihenfolge: **Übersicht** · Beteiligte · Unfall · Schaden · Dokumente · Gebühren · Regulierung · Klage · Word

### Notification-Badges

Zwei Badge-Typen werden auf Tab-Labels ergänzt:

| Tab | Badge | Bedingung |
|---|---|---|
| Dokumente | Rote Zahl (z.B. `2`) | Anzahl neuer E-Akte-Dokumente seit letztem Besuch (via `localStorage` Timestamp-Vergleich mit `dokument.erstellt_am`) |
| Regulierung | Roter Punkt | Neuestes `abrechnungsschreiben.erstellt_am` > letzter Besuch des Regulierung-Tabs |

Badge-State wird per `localStorage` mit Key `tab-letztbesucht-{az}-{tabname}` verwaltet. Kein neuer API-Call – berechnet aus bereits geladenem State.

---

## PWA-Nachricht (Stub)

### Frontend

Neues Modal `PwaNachrichtModal` in `UebersichtSection.jsx`:

```
┌─ Nachricht an Mandant ──────────────────────────────┐
│ Vorlage: [Bitte IBAN mitteilen ▾]                   │
│                                                      │
│ ┌──────────────────────────────────────────────────┐ │
│ │ Sehr geehrte/r …,                                │ │
│ │                                                  │ │  ← Textarea, vorausgefüllt
│ │ für die weitere Bearbeitung …                    │ │
│ └──────────────────────────────────────────────────┘ │
│ [Abbrechen]                          [📤 Senden]     │
└──────────────────────────────────────────────────────┘
```

**Vorlagen** (hardcoded initial, später aus `konfiguration`):

| Key | Titel | Text |
|---|---|---|
| `iban_anfrage` | Bitte IBAN mitteilen | Kurzer Standardtext IBAN-Anfrage |
| `regulierung_eingegangen` | Regulierungszahlung eingegangen | Kurztext Zahlungseingang |
| `sachstand` | Sachstandsmitteilung | Freitext-Vorlage |
| `freitext` | Freitext | Leeres Feld |

### Backend (Stub)

Neuer Endpunkt in `akten_routes.py`:

```python
POST /akten/<az>/pwa-nachricht
Body: { "text": str, "vorlage_key": str }
Response: { "ok": true, "aktivitaet_id": int }
```

Implementierung: Speichert Eintrag in `aktivitaeten` mit `typ='pwa_nachricht'`, `beschreibung=text`. Sendet **keine** Push-Notification (Stub). Gibt 200 zurück.

Die eigentliche PWA-Integration (Web Push API, Service Worker, Subscription-Management) folgt in einem separaten PRD.

---

## Datenfluss

```
UebersichtSection
  ├── mandant-checks (bestehend)  →  Check-Pills (Vollmacht, IBAN, RSV)
  ├── todos.liste (bestehend)     →  Todo-Spalte + §3a/Verjährungs-Pills
  ├── wiedervorlage/ (bestehend)  →  WV-Spalte
  ├── st.abrechnungen (State)     →  Finanz-Band (keine neuen Calls)
  └── st.schaden (State)          →  Finanz-Band
```

Alle Daten sind bereits im `st`-State verfügbar oder werden durch bestehende Calls geladen. Keine neuen Backend-Queries für das Action Board selbst nötig (außer dem PWA-Stub-Endpunkt).

---

## Nicht im Scope

- Echte PWA-Push-Notification-Zustellung (separates PRD)
- Mandanten-Portal-Seite zum Empfangen von Nachrichten (separates PRD)
- RSV-Automatismus (Deckungsanfrage automatisch senden)
- Mobile-Ansicht (App läuft nur am Desktop)
- §3a-Frist-Berechnung aus Datum (nur aus vorhandenen Todos lesen)

---

## Offene Fragen (vor Implementierung klären)

1. **RSV-Deckungsstatus:** Woher kommt `rechtsschutz_deckung`? Aus `mandant-checks`-Endpunkt ergänzen oder eigenes Feld in `beteiligte`-Tabelle?
2. **Langer Aktenlangtext:** Wird die Langbezeichnung aus RA-MICRO `s.bezeichnung` oder aus einer eigenen SQLite-Spalte befüllt?
3. **Badge-Persistenz:** `localStorage` reicht für den Anfang, oder soll der „gelesen"-Status pro User in der DB gespeichert werden?
