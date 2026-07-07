# Portal-B2: Sachverständigen-Cockpit – Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementiert das Sachverständigen-Cockpit im Stakeholder-Portal – ein professionelles Multi-Case-Dashboard mit KPI-Kacheln, sortier- und filterbarer Akten-Tabelle, Case-Detail-Ansicht mit Status-Timeline und Dokumenten-Download sowie einem Statistik-Tab mit echten Diagrammen.

**Architecture:** Baut auf Portal-B1 (Foundation) auf. Next.js 15 App Router: Server Components für initiales Data-Fetching, Client Components für interaktive Tabellen-Filter/Sort/Search und Theme-Toggle. Daten-Layer als pure TypeScript-Funktionen (`sv-data.ts`) die `getDb()` nutzen. Statistik- und Charts-Komponente ist ein dedizierter `"use client"` Wrapper um Recharts. Status-History wird beim Sync-Empfang geschrieben (10 neue Zeilen im Sync-Endpoint).

**Tech Stack:** Next.js 15 App Router, TypeScript, Tailwind v4 (CSS-Variablen-Architektur), `next-themes` (Light/Dark Toggle), `recharts` (Charts), `better-sqlite3`, Vitest (Tests)

**Projekt-Verzeichnis:** `C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal\`

---

## Voraussetzungen

- **Portal-B1 vollständig implementiert** (DB-Schema, Magic-Link-Auth, Session, Sync-Endpoint, Admin-Panel)
- **Portal-A2 (klein):** `gutachten_nr` muss im Sync-Payload mitgeliefert werden. Dokumentiert im **Appendix A** dieses Plans (~30 Min. A-seitige Änderung). B2 baut das Portal-seitige DB-Feld (`akte_zugriff.gutachten_nr`) und die Suche dafür — Feld bleibt NULL bis A2 deployed ist.
- Die Ampel-Funktion in `portal_sync.py` liefert aktuell 6 Status-Werte. Die Spec sieht 7 vor (fehlend: `zahlung_angekuendigt`, `gutachten_bestritten`). B2 baut die UI für alle 7 — die neuen Status werden erst nach einer A-seitigen Ergänzung aktiv.

---

## File Structure

```
stakeholder-portal/
├── src/
│   ├── app/
│   │   ├── globals.css                         # Erweitert: Design-Token-System
│   │   ├── layout.tsx                          # Erweitert: ThemeProvider + Onest Font
│   │   └── (authed)/
│   │       └── sv/
│   │           ├── page.tsx                    # Cockpit: KPI + Tabs (Akten | Statistik)
│   │           └── [az]/
│   │               └── page.tsx                # Detail-Ansicht je Gutachten
│   ├── components/
│   │   ├── ThemeProvider.tsx                   # Neu: next-themes Wrapper (Client)
│   │   ├── ThemeToggle.tsx                     # Neu: Sun/Moon Toggle (Client)
│   │   ├── AmpelBadge.tsx                      # Erweitert: alle 7 Zustände, neue Farb-CSS-Vars
│   │   ├── KpiCard.tsx                         # Neu: KPI-Kachel-Komponente (Server)
│   │   ├── AktenTable.tsx                      # Neu: Tabelle mit Filter/Sort/Search (Client)
│   │   ├── StatusTimeline.tsx                  # Neu: Zeitlinie der Statusübergänge (Server)
│   │   └── StatistikCharts.tsx                 # Neu: Recharts-Wrapper (Client)
│   ├── lib/
│   │   ├── db.ts                               # Erweitert: B2 Schema-Migration
│   │   └── sv-data.ts                          # Neu: Daten-Layer für SV-Cockpit
│   ├── types/
│   │   └── index.ts                            # Erweitert: B2 TypeScript-Typen
│   └── app/
│       └── api/
│           └── sync/
│               └── push/
│                   └── route.ts                # Erweitert: status_history schreiben
└── src/lib/__tests__/
    └── sv-data.test.ts                         # Neu: Vitest Tests für Daten-Layer
```

---

## Task 0: Rollenbasierte Session-Dauer (`src/lib/session.ts`)

**Files:**
- Modify: `src/lib/session.ts`

**Hintergrund:** B1 hat einen fixen 30-Minuten-Timeout für alle Rollen. Sachverständige sind Dauerkunden, die das Portal mehrmals wöchentlich nutzen — ein 30-Minuten-Sliding-Timeout bedeutet: jedes Mal wenn sie das Browser-Tab schließen und am nächsten Tag zurückkommen, brauchen sie einen neuen Magic Link. Das ist inakzeptabel für ein Partnertool. Privatmandanten hingegen greifen selten und sensibel auf ihren Fall zu — kurze Sessions sind hier richtig.

Lösung: unterschiedliche Session-Dauer je Rolle, realisiert mit einer Role-Map in `session.ts`.

- [ ] **Step 0.1: Test schreiben**

Erstelle `src/lib/__tests__/session.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { SESSION_DURATION_MINUTES } from "@/lib/session";

describe("SESSION_DURATION_MINUTES", () => {
  it("sachverstaendiger bekommt 30-Tage-Session", () => {
    expect(SESSION_DURATION_MINUTES.sachverstaendiger).toBe(60 * 24 * 30);
  });

  it("privatmandant bekommt 60-Minuten-Session", () => {
    expect(SESSION_DURATION_MINUTES.privatmandant).toBe(60);
  });

  it("kanzlei_admin bekommt 60-Minuten-Session", () => {
    expect(SESSION_DURATION_MINUTES.kanzlei_admin).toBe(60);
  });
});
```

- [ ] **Step 0.2: Test zum Scheitern bringen**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal\.worktrees\portal-b1"
npm test
```

Erwartetes Ergebnis: FAIL — `SESSION_DURATION_MINUTES` ist nicht exportiert.

- [ ] **Step 0.3: `src/lib/session.ts` anpassen**

Ersetze die bestehende Konstante `SESSION_MAX_AGE_MINUTES` durch eine Role-Map. Suche im bestehenden `session.ts` nach:

```typescript
const SESSION_MAX_AGE_MINUTES = 30;
```

Ersetze sie mit:

```typescript
export const SESSION_DURATION_MINUTES: Record<UserRole, number> = {
  kanzlei_admin:     60,
  sachverstaendiger: 60 * 24 * 30,  // 30 Tage — SV sind Dauerkunden
  privatmandant:     60,
};
```

Dann die beiden Stellen in `createSession` und `getSession` anpassen, die `SESSION_MAX_AGE_MINUTES` verwenden.

In `createSession` (erhält bereits `user: PortalUser` mit `rolle`):

```typescript
export async function createSession(
  user: PortalUser,
  response: NextResponse
): Promise<void> {
  const db = getDb();
  const sessionId = uuidv4();
  const durationMinutes = SESSION_DURATION_MINUTES[user.rolle] ?? 60;
  const expiresAt = new Date(
    Date.now() + durationMinutes * 60 * 1000
  ).toISOString();

  db.prepare("DELETE FROM portal_sessions WHERE user_id = ?").run(user.id);

  db.prepare(`
    INSERT INTO portal_sessions (id, user_id, expires_at)
    VALUES (?, ?, ?)
  `).run(sessionId, user.id, expiresAt);

  response.cookies.set(SESSION_COOKIE, sessionId, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: durationMinutes * 60,
    path: "/",
  });
}
```

In `getSession` — `newExpiry` nutzt jetzt die Rolle aus dem DB-Row:

```typescript
const durationMinutes = SESSION_DURATION_MINUTES[row.rolle as UserRole] ?? 60;
const newExpiry = new Date(
  Date.now() + durationMinutes * 60 * 1000
).toISOString();
```

Ersetze im bestehenden Code die Zeile:
```typescript
const newExpiry = new Date(Date.now() + SESSION_MAX_AGE_MINUTES * 60 * 1000).toISOString();
```
mit der obigen `durationMinutes`-Variante.

- [ ] **Step 0.4: Tests laufen lassen**

```bash
npm test
```

Erwartetes Ergebnis: PASS (3 Tests grün)

- [ ] **Step 0.5: TypeScript prüfen**

```bash
npm run typecheck
```

Erwartetes Ergebnis: Keine Fehler.

- [ ] **Step 0.6: Commit**

```bash
git add src/lib/session.ts src/lib/__tests__/session.test.ts
git commit -m "feat: rollenbasierte Session-Dauer – SV 30 Tage, Admin/Mandant 60 Min"
```

---

## Task 1: Design-System + Theme-Toggle

**Files:**
- Modify: `src/app/globals.css`
- Modify: `src/app/layout.tsx`
- Create: `src/components/ThemeProvider.tsx`
- Create: `src/components/ThemeToggle.tsx`

- [ ] **Step 1.1: next-themes und recharts installieren**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal"
npm install next-themes recharts
npm install --save-dev vitest @vitejs/plugin-react @testing-library/react @types/recharts
```

- [ ] **Step 1.2: `src/app/globals.css` — Design-Token-System einrichten**

Ersetze den kompletten Inhalt von `globals.css` mit:

```css
@import "tailwindcss";
@import url("https://fonts.googleapis.com/css2?family=Onest:wght@100..900&display=swap");

/* ───────────────────────────────────────────────
   DESIGN TOKENS — LIGHT MODE (default)
─────────────────────────────────────────────── */
:root {
  --font-sans: "Onest", system-ui, sans-serif;

  /* Surfaces */
  --bg:         oklch(0.98 0.008 70);
  --bg-subtle:  oklch(0.94 0.008 70);
  --bg-surface: oklch(1.00 0.000 0);
  --border:     oklch(0.88 0.006 200);
  --border-strong: oklch(0.75 0.008 200);

  /* Text */
  --text:        oklch(0.15 0.010 250);
  --text-muted:  oklch(0.42 0.010 250);
  --text-subtle: oklch(0.62 0.008 250);

  /* Accent — gedämpftes Teal */
  --accent:        oklch(0.42 0.14 200);
  --accent-hover:  oklch(0.35 0.14 200);
  --accent-subtle: oklch(0.93 0.04 200);
  --accent-text:   oklch(1.00 0.000 0);

  /* Ampel-Farben */
  --ampel-grau:       oklch(0.62 0.010 250);
  --ampel-blau:       oklch(0.50 0.160 230);
  --ampel-gelb:       oklch(0.70 0.170  85);
  --ampel-hellgruen:  oklch(0.65 0.150 150);
  --ampel-gruen:      oklch(0.50 0.180 150);
  --ampel-orange:     oklch(0.62 0.200  55);
  --ampel-rot:        oklch(0.50 0.210  25);
  --ampel-dunkelrot:  oklch(0.36 0.170  20);

  /* Rechnungs-Status */
  --status-offen:      oklch(0.62 0.010 250);
  --status-teilbez:    oklch(0.62 0.200  55);
  --status-bezahlt:    oklch(0.50 0.180 150);

  /* Radius */
  --radius-sm:  4px;
  --radius-md:  8px;
  --radius-lg: 12px;
}

/* ───────────────────────────────────────────────
   DARK MODE
─────────────────────────────────────────────── */
[data-theme="dark"] {
  --bg:         oklch(0.12 0.010 250);
  --bg-subtle:  oklch(0.17 0.010 250);
  --bg-surface: oklch(0.15 0.010 250);
  --border:     oklch(0.26 0.010 250);
  --border-strong: oklch(0.36 0.010 250);

  --text:        oklch(0.95 0.008  70);
  --text-muted:  oklch(0.68 0.010 250);
  --text-subtle: oklch(0.50 0.010 250);

  --accent:        oklch(0.62 0.150 200);
  --accent-hover:  oklch(0.70 0.150 200);
  --accent-subtle: oklch(0.22 0.060 200);
  --accent-text:   oklch(0.10 0.010 250);

  --ampel-grau:       oklch(0.55 0.010 250);
  --ampel-blau:       oklch(0.62 0.160 230);
  --ampel-gelb:       oklch(0.78 0.160  85);
  --ampel-hellgruen:  oklch(0.72 0.150 150);
  --ampel-gruen:      oklch(0.65 0.170 150);
  --ampel-orange:     oklch(0.72 0.190  55);
  --ampel-rot:        oklch(0.62 0.200  25);
  --ampel-dunkelrot:  oklch(0.52 0.160  20);

  --status-offen:      oklch(0.55 0.010 250);
  --status-teilbez:    oklch(0.72 0.190  55);
  --status-bezahlt:    oklch(0.65 0.170 150);
}

/* ───────────────────────────────────────────────
   BASE
─────────────────────────────────────────────── */
html {
  font-family: var(--font-sans);
  background-color: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

body {
  background-color: var(--bg);
}

* {
  box-sizing: border-box;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

- [ ] **Step 1.3: `src/components/ThemeProvider.tsx` erstellen**

```typescript
"use client";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider
      attribute="data-theme"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
```

- [ ] **Step 1.4: `src/components/ThemeToggle.tsx` erstellen**

```typescript
"use client";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) return <div className="w-9 h-9" aria-hidden />;

  const isDark = theme === "dark";
  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      aria-label={isDark ? "Hell-Modus aktivieren" : "Dunkel-Modus aktivieren"}
      style={{
        width: 36, height: 36,
        display: "flex", alignItems: "center", justifyContent: "center",
        borderRadius: "var(--radius-md)",
        color: "var(--text-muted)",
        transition: "background 0.15s, color 0.15s",
      }}
      onMouseEnter={e => (e.currentTarget.style.backgroundColor = "var(--bg-subtle)")}
      onMouseLeave={e => (e.currentTarget.style.backgroundColor = "transparent")}
    >
      {isDark ? <Sun size={16} strokeWidth={1.75} /> : <Moon size={16} strokeWidth={1.75} />}
    </button>
  );
}
```

- [ ] **Step 1.5: `src/app/layout.tsx` anpassen**

Ersetze die bestehende `layout.tsx` (aus B1) mit der erweiterten Version:

```typescript
import type { Metadata } from "next";
import { ThemeProvider } from "@/components/ThemeProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: `${process.env.NEXT_PUBLIC_KANZLEI_NAME ?? "Kanzlei"} – Mandantenportal`,
  description: "Sicherer Zugang zu Ihren Unterlagen und dem aktuellen Sachstand.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
```

**Hinweis:** `suppressHydrationWarning` auf `<html>` ist nötig, weil `next-themes` das `data-theme` Attribut client-seitig setzt. Ohne dieses Attribut gibt es React-Hydration-Warnungen.

- [ ] **Step 1.6: Vitest konfigurieren**

Erstelle `vitest.config.ts` im Projekt-Root:

```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

Füge in `package.json` unter `"scripts"` hinzu:
```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 1.7: Visuell prüfen**

```bash
npm run dev
```
Öffne http://localhost:3000. Das Layout sollte den Onest-Font laden und ein sauberes Off-White zeigen.
Hinweis: Der ThemeToggle ist noch nicht eingebaut (kommt mit dem Cockpit-Layout in Task 5).

- [ ] **Step 1.8: Commit**

```bash
git add src/app/globals.css src/app/layout.tsx src/components/ThemeProvider.tsx src/components/ThemeToggle.tsx vitest.config.ts package.json package-lock.json
git commit -m "feat: design-system – tokens, light/dark CSS vars, Onest font, ThemeToggle, Vitest setup"
```

---

## Task 2: DB-Schema-Erweiterungen + Sync-Endpoint-Update

**Files:**
- Modify: `src/lib/db.ts`
- Modify: `src/types/index.ts`
- Modify: `src/app/api/sync/push/route.ts`

**Hinweis zu B1-Besonderheiten (gefunden bei Code-Review):**
- `better-sqlite3` statt SQLCipher (vereinfacht Tests)
- `initSchema` ist privat → wird in Schritt 2.3 exportiert
- `processSync` liegt in `src/lib/sync.ts` (nicht `route.ts`) → Änderungen dort
- `regulierung_snapshot.positionen_json` ist ein `Record<string, number>` (z.B. `{"sv_kosten": 1500}`) — kein Array
- `akten.ampel_status` hat einen CHECK-Constraint mit 6 Werten → SQLite-Migration für neue Werte nötig

---

- [ ] **Step 2.1: Typen erweitern (`src/types/index.ts`)**

Füge am Ende der bestehenden `index.ts` (aus B1) hinzu:

```typescript
// ─── B2 Erweiterungen ─────────────────────────────────────────────────────

export type AmpelStatus =
  | "akte_eroeffnet"
  | "gutachten_beauftragt"
  | "regulierung_laeuft"
  | "zahlung_angekuendigt"   // NEU: kommt nach A-seitiger Ergänzung
  | "vollreguliert"
  | "teilreguliert"
  | "klage_eingereicht"
  | "gutachten_bestritten";  // NEU: kommt nach A-seitiger Ergänzung

export type GaRechnungStatus = "offen" | "teilbezahlt" | "bezahlt";

export interface SvAkteRow {
  az: string;
  unfalldatum: string | null;
  kennzeichen: string | null;
  haftungsquote: number | null;
  ampel_status: AmpelStatus;
  ampel_farbe: string;
  status: AktenStatus;
  gutachten_nr: string | null;
  sv_kosten_gefordert: number;
  sv_kosten_reguliert: number;
  ga_rechnung_status: GaRechnungStatus;
  letzter_sync: string | null;
  docs_count: number;
}

export interface SvKpiData {
  gesamt: number;
  offen: number;
  in_regulierung: number;
  abgeschlossen: number;
  summe_offene_rechnung: number;
}

export interface StatusHistoryEntry {
  ampel_status: AmpelStatus;
  ampel_farbe: string;
  timestamp: string;
}

export interface SvAkteDetail {
  az: string;
  unfalldatum: string | null;
  kennzeichen: string | null;
  haftungsquote: number | null;
  sachbearbeiter: string | null;
  status: AktenStatus;
  ampel_status: AmpelStatus;
  ampel_farbe: string;
  gutachten_nr: string | null;
  letzter_sync: string | null;
  sv_kosten_gefordert: number;
  sv_kosten_reguliert: number;
  ga_rechnung_status: GaRechnungStatus;
  history: StatusHistoryEntry[];
  docs: Array<{ id: string; typ: string; dateiname: string; erstellt_am: string }>;
}

export interface SvStatistik {
  gesamt: number;
  vollreguliert: number;
  teilreguliert: number;
  offen: number;
  gesamt_volumen: number;
  bezahlt_volumen: number;
  avg_regulierungszeit_tage: number | null;
  monatlich: Array<{ monat: string; anzahl: number }>;
}
```

**Hinweis:** Die `AmpelStatus`-Definition aus B1 (`types/index.ts`) muss ersetzt werden — B2 erweitert sie um `zahlung_angekuendigt` und `gutachten_bestritten`.

- [ ] **Step 2.2: Test schreiben für Schema-Migration**

Erstelle `src/lib/__tests__/sv-data.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";

// Holt initSchema direkt – wird in Step 2.3 exportiert
import { initSchema } from "@/lib/db";

function createTestDb() {
  const db = new Database(":memory:");
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  initSchema(db);
  return db;
}

describe("B2 Schema-Migration", () => {
  it("legt status_history Tabelle an", () => {
    const db = createTestDb();
    const tables = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all()
      .map((r: any) => r.name);
    expect(tables).toContain("status_history");
  });

  it("akten hat unfalldatum und kennzeichen Spalten", () => {
    const db = createTestDb();
    const cols = db
      .pragma("table_info(akten)")
      .map((c: any) => c.name);
    expect(cols).toContain("unfalldatum");
    expect(cols).toContain("kennzeichen");
    expect(cols).toContain("haftungsquote");
    expect(cols).toContain("sachbearbeiter");
  });

  it("akte_zugriff hat gutachten_nr Spalte", () => {
    const db = createTestDb();
    const cols = db
      .pragma("table_info(akte_zugriff)")
      .map((c: any) => c.name);
    expect(cols).toContain("gutachten_nr");
  });
});
```

- [ ] **Step 2.3: Test zum Scheitern bringen**

```bash
npm test
```

Erwartetes Ergebnis: FAIL — `initSchema` ist nicht exportiert, `status_history` fehlt.

- [ ] **Step 2.4: `src/lib/db.ts` erweitern**

In der bestehenden `db.ts` aus B1:

**a) `initSchema` exportieren** — ändere `function initSchema` zu `export function initSchema`:

```typescript
export function initSchema(db: InstanceType<typeof Database>) {
```

**b) SQLite-Migration für B2** — Am Ende von `initSchema`, nach dem bestehenden `db.exec(...)` Block, folgende Zeilen hinzufügen:

```typescript
  // ─── B2: Neue Spalten zu bestehenden Tabellen ────────────────────────────
  // SQLite hat kein ALTER TABLE ADD COLUMN IF NOT EXISTS → PRAGMA prüfen
  const aktenCols = (db.pragma("table_info(akten)") as Array<{name: string}>).map(c => c.name);
  if (!aktenCols.includes("unfalldatum"))    db.exec("ALTER TABLE akten ADD COLUMN unfalldatum TEXT");
  if (!aktenCols.includes("kennzeichen"))    db.exec("ALTER TABLE akten ADD COLUMN kennzeichen TEXT");
  if (!aktenCols.includes("haftungsquote"))  db.exec("ALTER TABLE akten ADD COLUMN haftungsquote REAL");
  if (!aktenCols.includes("sachbearbeiter")) db.exec("ALTER TABLE akten ADD COLUMN sachbearbeiter TEXT");

  const zugrifCols = (db.pragma("table_info(akte_zugriff)") as Array<{name: string}>).map(c => c.name);
  if (!zugrifCols.includes("gutachten_nr"))  db.exec("ALTER TABLE akte_zugriff ADD COLUMN gutachten_nr TEXT");

  // ─── B2: CHECK-Constraint auf akten.ampel_status/ampel_farbe erweitern ───
  // SQLite kann CHECK-Constraints nicht inplace ändern → Table-Rebuild via
  // user_version Marker (nur einmalig ausführen)
  const v = (db.pragma("user_version") as Array<{user_version: number}>)[0].user_version;
  if (v < 2) {
    db.exec(`
      BEGIN;
      ALTER TABLE akten RENAME TO _akten_b1;
      CREATE TABLE akten (
        az            TEXT PRIMARY KEY,
        status        TEXT NOT NULL DEFAULT 'offen'
          CHECK(status IN ('offen','in_regulierung','klage','abgeschlossen')),
        ampel_status  TEXT NOT NULL DEFAULT 'akte_eroeffnet',
        ampel_farbe   TEXT NOT NULL DEFAULT 'grau',
        sync_version  INTEGER NOT NULL DEFAULT 0,
        letzter_sync  TEXT,
        unfalldatum   TEXT,
        kennzeichen   TEXT,
        haftungsquote REAL,
        sachbearbeiter TEXT
      );
      INSERT INTO akten SELECT
        az, status, ampel_status, ampel_farbe, sync_version, letzter_sync,
        NULL, NULL, NULL, NULL
      FROM _akten_b1;
      DROP TABLE _akten_b1;
      PRAGMA user_version = 2;
      COMMIT;
    `);
  }

  // ─── B2: Neue Tabellen ────────────────────────────────────────────────────
  db.exec(`
    CREATE TABLE IF NOT EXISTS status_history (
      id           TEXT PRIMARY KEY,
      az           TEXT NOT NULL REFERENCES akten(az) ON DELETE CASCADE,
      ampel_status TEXT NOT NULL,
      ampel_farbe  TEXT NOT NULL,
      timestamp    TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_status_history_az ON status_history(az, timestamp);
  `);
```

**Hinweis:** `user_version = 2` ist ein SQLite-Marker der sicherstellt, dass der Table-Rebuild nur einmal läuft. Der bestehende `initSchema`-Code (B1) verwendet kein `user_version` — daher ist `0` der Startwert.

- [ ] **Step 2.5: Test laufen lassen**

```bash
npm test
```

Erwartetes Ergebnis: PASS (3 Tests grün)

- [ ] **Step 2.6: `src/lib/sync.ts` erweitern**

**Die gesamte Änderung passiert in `sync.ts`**, nicht in `route.ts`. Datei vollständig ersetzen:

```typescript
import { createHmac, timingSafeEqual } from "crypto";
import { v4 as uuid } from "uuid";
import { getDb } from "./db";

export function verifyHmacSignature(body: string, signature: string): boolean {
  const secret = process.env.SYNC_HMAC_SECRET ?? "";
  if (!secret) {
    console.error("SYNC_HMAC_SECRET ist nicht gesetzt — alle Sync-Anfragen werden abgelehnt");
    return false;
  }
  const expected = createHmac("sha256", secret).update(body).digest("hex");
  try {
    const expectedBuf = Buffer.from(expected, "hex");
    const sigBuf = Buffer.from(signature, "hex");
    if (expectedBuf.length !== sigBuf.length) return false;
    return timingSafeEqual(expectedBuf, sigBuf);
  } catch {
    return false;
  }
}

export interface SyncPayload {
  sync_version: number;
  akte: {
    az: string;
    status: string;
    unfalldatum?: string;
    kennzeichen?: string;
    haftungsquote?: number;
    sachbearbeiter?: string;
  };
  beteiligte?: Array<{
    id: string | number;
    rolle: string;
    name?: string;
    vorname?: string;
    firma?: string;
    email?: string;
    gutachten_nr?: string;       // PORTAL-A2: optional bis A-Seite deployed
  }>;
  schaden?: Record<string, number>;
  regulierung_positionen?: Array<{
    position_key: string;
    reguliert: number;
    letztes_datum?: string;
    versicherung?: string;
  }>;
  dokumente?: Array<{
    id: string | number;
    typ: string;
    dateiname: string;
    erstellt_am?: string;
  }>;
  ampel: {
    status: string;
    farbe: string;
  };
}

export function processSync(payload: SyncPayload): "processed" | "already_processed" {
  const db = getDb();
  const az = payload.akte.az;
  if (!az) throw new Error("az fehlt im Payload");

  const result = db.transaction((): "processed" | "already_processed" => {
    // Aktuellen Ampel-Status laden (für status_history Vergleich)
    const existing = db.prepare(
      "SELECT ampel_status FROM akten WHERE az = ?"
    ).get(az) as { ampel_status: string } | undefined;

    // Akte upserten (B2: neue Felder ergänzt)
    db.prepare(`
      INSERT INTO akten (az, status, ampel_status, ampel_farbe, sync_version, letzter_sync,
                         unfalldatum, kennzeichen, haftungsquote, sachbearbeiter)
      VALUES (?, ?, ?, ?, ?, datetime('now'), ?, ?, ?, ?)
      ON CONFLICT(az) DO UPDATE SET
        status        = excluded.status,
        ampel_status  = excluded.ampel_status,
        ampel_farbe   = excluded.ampel_farbe,
        sync_version  = excluded.sync_version,
        letzter_sync  = excluded.letzter_sync,
        unfalldatum   = excluded.unfalldatum,
        kennzeichen   = excluded.kennzeichen,
        haftungsquote = excluded.haftungsquote,
        sachbearbeiter = excluded.sachbearbeiter
    `).run(
      az,
      payload.akte.status,
      payload.ampel.status,
      payload.ampel.farbe,
      payload.sync_version,
      payload.akte.unfalldatum   ?? null,
      payload.akte.kennzeichen   ?? null,
      payload.akte.haftungsquote ?? null,
      payload.akte.sachbearbeiter ?? null
    );

    // Status-History: nur bei Statuswechsel schreiben
    if (!existing || existing.ampel_status !== payload.ampel.status) {
      db.prepare(`
        INSERT INTO status_history (id, az, ampel_status, ampel_farbe, timestamp)
        VALUES (?, ?, ?, ?, datetime('now'))
      `).run(uuid(), az, payload.ampel.status, payload.ampel.farbe);
    }

    // Beteiligte upserten (B2: gutachten_nr ergänzt)
    for (const b of payload.beteiligte ?? []) {
      const bId = String(b.id);
      db.prepare(`
        INSERT INTO beteiligte (id, az, rolle, name, firma, email)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          az = excluded.az, rolle = excluded.rolle,
          name = excluded.name, firma = excluded.firma, email = excluded.email
      `).run(bId, az, b.rolle, b.name ?? null, b.firma ?? null, b.email ?? null);

      // gutachten_nr in akte_zugriff (nur wenn Feld vorhanden, kommt nach PORTAL-A2)
      if (b.rolle === "sachverstaendiger" && b.gutachten_nr && b.email) {
        db.prepare(`
          UPDATE akte_zugriff SET gutachten_nr = ?
          WHERE az = ? AND user_id = (
            SELECT id FROM portal_users WHERE email = ? LIMIT 1
          )
        `).run(b.gutachten_nr, az, b.email);
      }
    }

    // Schaden-Snapshot
    if (payload.schaden && Object.keys(payload.schaden).length > 0) {
      const gesamt = Object.values(payload.schaden).reduce((s, v) => s + (v ?? 0), 0);
      db.prepare(`
        INSERT INTO schaden_snapshot (az, positionen_json, gesamt_brutto)
        VALUES (?, ?, ?)
        ON CONFLICT(az) DO UPDATE SET
          positionen_json = excluded.positionen_json,
          gesamt_brutto = excluded.gesamt_brutto
      `).run(az, JSON.stringify(payload.schaden), gesamt);
    }

    // Regulierung-Snapshot
    // B1 speichert als Record<string,number>: {"sv_kosten": 1500, "reparaturkosten": 5000}
    if (payload.regulierung_positionen && payload.regulierung_positionen.length > 0) {
      const posMap: Record<string, number> = {};
      let gesamt = 0;
      for (const p of payload.regulierung_positionen) {
        posMap[p.position_key] = p.reguliert;
        gesamt += p.reguliert;
      }
      db.prepare(`
        INSERT INTO regulierung_snapshot (az, positionen_json, gesamt_reguliert)
        VALUES (?, ?, ?)
        ON CONFLICT(az) DO UPDATE SET
          positionen_json = excluded.positionen_json,
          gesamt_reguliert = excluded.gesamt_reguliert
      `).run(az, JSON.stringify(posMap), gesamt);
    }

    // Dokument-Metadaten upserten
    for (const d of payload.dokumente ?? []) {
      const dId = String(d.id);
      db.prepare(`
        INSERT INTO dokumente (id, az, typ, dateiname, erstellt_am)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          az = excluded.az, typ = excluded.typ, dateiname = excluded.dateiname
      `).run(dId, az, d.typ, d.dateiname, d.erstellt_am ?? null);
    }

    // Idempotency-Check (atomic mit Log-Schreiben)
    const alreadyProcessed = db.prepare(
      "SELECT id FROM sync_log WHERE az = ? AND sync_version = ? AND status = 'ok'"
    ).get(az, payload.sync_version) as { id: number } | undefined;

    if (alreadyProcessed) return "already_processed";

    db.prepare("INSERT INTO sync_log (az, sync_version, status) VALUES (?, ?, 'ok')")
      .run(az, payload.sync_version);

    return "processed";
  })();

  return result;
}
```

- [ ] **Step 2.7: Commit**

```bash
git add src/lib/db.ts src/types/index.ts src/app/api/sync/push/route.ts src/lib/__tests__/sv-data.test.ts
git commit -m "feat: B2 DB-Schema – status_history, unfalldatum/kennzeichen, gutachten_nr; sync-endpoint status-history"
```

---

## Task 3: Daten-Layer (`src/lib/sv-data.ts`) + Tests

**Files:**
- Create: `src/lib/sv-data.ts`
- Modify: `src/lib/__tests__/sv-data.test.ts`

- [ ] **Step 3.1: Tests für Daten-Layer schreiben**

Ersetze `src/lib/__tests__/sv-data.test.ts` mit dem vollständigen Test:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import Database from "better-sqlite3";
import { v4 as uuid } from "uuid";
import { initSchema } from "@/lib/db";
import { getSvAkten, getSvKpi, getSvAkteDetail, getSvStatistik } from "@/lib/sv-data";

function createTestDb() {
  const db = new Database(":memory:") as any;
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  initSchema(db);
  return db;
}

function seed(db: any) {
  const userId = uuid();
  const az1 = "285/26";
  const az2 = "286/26";

  db.prepare(`
    INSERT INTO portal_users (id, email, name, rolle)
    VALUES (?, 'sv@test.de', 'Testgutachter', 'sachverstaendiger')
  `).run(userId);

  // Akte 1: regulierung_laeuft, sv_kosten 800, reguliert 0 → offen
  db.prepare(`
    INSERT INTO akten (az, status, ampel_status, ampel_farbe, sync_version, unfalldatum, kennzeichen, letzter_sync)
    VALUES (?, 'offen', 'regulierung_laeuft', 'gelb', 1, '2026-03-15', 'OF-AA-123', datetime('now'))
  `).run(az1);
  db.prepare(`
    INSERT INTO akte_zugriff (user_id, az, gutachten_nr) VALUES (?, ?, 'GA-2026-001')
  `).run(userId, az1);
  db.prepare(`
    INSERT INTO schaden_snapshot (az, positionen_json, gesamt_brutto)
    VALUES (?, '{"sv_kosten": 800}', 800)
  `).run(az1);
  db.prepare(`
    INSERT INTO regulierung_snapshot (az, positionen_json, gesamt_reguliert)
    VALUES (?, '[]', 0)
  `).run(az1);

  // Akte 2: vollreguliert, sv_kosten 600, reguliert 600 → bezahlt
  db.prepare(`
    INSERT INTO akten (az, status, ampel_status, ampel_farbe, sync_version, unfalldatum, kennzeichen, letzter_sync)
    VALUES (?, 'abgeschlossen', 'vollreguliert', 'gruen', 1, '2026-01-10', 'MKK-BB-456', datetime('now'))
  `).run(az2);
  db.prepare(`
    INSERT INTO akte_zugriff (user_id, az) VALUES (?, ?)
  `).run(userId, az2);
  db.prepare(`
    INSERT INTO schaden_snapshot (az, positionen_json, gesamt_brutto)
    VALUES (?, '{"sv_kosten": 600}', 600)
  `).run(az2);
  db.prepare(`
    INSERT INTO regulierung_snapshot (az, positionen_json, gesamt_reguliert)
    VALUES (?, '{"sv_kosten": 600}', 600)
  `).run(az2);
  // Hinweis: B1 speichert als Record<string,number>, nicht als Array

  // Status-History für az1
  db.prepare(`
    INSERT INTO status_history (id, az, ampel_status, ampel_farbe, timestamp)
    VALUES (?, ?, 'akte_eroeffnet', 'grau', '2026-03-10 10:00:00')
  `).run(uuid(), az1);
  db.prepare(`
    INSERT INTO status_history (id, az, ampel_status, ampel_farbe, timestamp)
    VALUES (?, ?, 'regulierung_laeuft', 'gelb', '2026-03-20 14:00:00')
  `).run(uuid(), az1);

  return { userId, az1, az2 };
}

describe("getSvAkten", () => {
  it("gibt nur Akten des angemeldeten Benutzers zurück", () => {
    const db = createTestDb();
    const { userId } = seed(db);
    const result = getSvAkten(userId, db);
    expect(result).toHaveLength(2);
  });

  it("berechnet ga_rechnung_status korrekt: offen wenn sv_kosten 800, reguliert 0", () => {
    const db = createTestDb();
    const { userId, az1 } = seed(db);
    const result = getSvAkten(userId, db);
    const akte = result.find(a => a.az === az1)!;
    expect(akte.ga_rechnung_status).toBe("offen");
    expect(akte.sv_kosten_gefordert).toBe(800);
    expect(akte.sv_kosten_reguliert).toBe(0);
  });

  it("berechnet ga_rechnung_status korrekt: bezahlt wenn vollständig reguliert", () => {
    const db = createTestDb();
    const { userId, az2 } = seed(db);
    const result = getSvAkten(userId, db);
    const akte = result.find(a => a.az === az2)!;
    expect(akte.ga_rechnung_status).toBe("bezahlt");
  });

  it("liefert gutachten_nr wenn vorhanden", () => {
    const db = createTestDb();
    const { userId, az1 } = seed(db);
    const result = getSvAkten(userId, db);
    const akte = result.find(a => a.az === az1)!;
    expect(akte.gutachten_nr).toBe("GA-2026-001");
  });

  it("gibt keine Akten anderer User zurück", () => {
    const db = createTestDb();
    seed(db);
    const result = getSvAkten("anderer-user-id", db);
    expect(result).toHaveLength(0);
  });
});

describe("getSvKpi", () => {
  it("berechnet KPI korrekt: 2 gesamt, 1 abgeschlossen, summe_offene_rechnung = 800", () => {
    const db = createTestDb();
    const { userId } = seed(db);
    const kpi = getSvKpi(userId, db);
    expect(kpi.gesamt).toBe(2);
    expect(kpi.abgeschlossen).toBe(1);
    expect(kpi.summe_offene_rechnung).toBe(800);
  });
});

describe("getSvAkteDetail", () => {
  it("gibt null zurück wenn Akte nicht dem User gehört", () => {
    const db = createTestDb();
    seed(db);
    const result = getSvAkteDetail("fremder-user", "285/26", db);
    expect(result).toBeNull();
  });

  it("liefert Status-History in chronologischer Reihenfolge", () => {
    const db = createTestDb();
    const { userId, az1 } = seed(db);
    const detail = getSvAkteDetail(userId, az1, db)!;
    expect(detail.history).toHaveLength(2);
    expect(detail.history[0].ampel_status).toBe("akte_eroeffnet");
    expect(detail.history[1].ampel_status).toBe("regulierung_laeuft");
  });
});

describe("getSvStatistik", () => {
  it("berechnet Gesamtvolumen korrekt: 800 + 600 = 1400", () => {
    const db = createTestDb();
    const { userId } = seed(db);
    const stat = getSvStatistik(userId, db);
    expect(stat.gesamt_volumen).toBe(1400);
    expect(stat.bezahlt_volumen).toBe(600);
  });

  it("liefert 12 Monats-Einträge", () => {
    const db = createTestDb();
    const { userId } = seed(db);
    const stat = getSvStatistik(userId, db);
    expect(stat.monatlich).toHaveLength(12);
  });
});
```

- [ ] **Step 3.2: Tests zum Scheitern bringen**

```bash
npm test
```

Erwartetes Ergebnis: FAIL — `sv-data.ts` existiert noch nicht.

- [ ] **Step 3.3: `src/lib/sv-data.ts` implementieren**

```typescript
import { getDb } from "./db";
import type { Database } from "better-sqlite3";
import type {
  SvAkteRow, SvKpiData, SvAkteDetail, SvStatistik, GaRechnungStatus, AmpelStatus,
} from "@/types";

// Alle Funktionen nehmen ein optionales db-Parameter für Testbarkeit
export function getSvAkten(userId: string, db = getDb()): SvAkteRow[] {
  const rows = (db as any).prepare(`
    SELECT
      a.az,
      a.unfalldatum,
      a.kennzeichen,
      a.haftungsquote,
      a.ampel_status,
      a.ampel_farbe,
      a.status,
      a.letzter_sync,
      az.gutachten_nr,
      COALESCE(s.positionen_json, '{}')  AS schaden_json,
      COALESCE(r.positionen_json, '[]')  AS reg_json,
      (SELECT COUNT(*) FROM dokumente d WHERE d.az = a.az) AS docs_count
    FROM akten a
    JOIN akte_zugriff az ON az.az = a.az AND az.user_id = ?
    LEFT JOIN schaden_snapshot s ON s.az = a.az
    LEFT JOIN regulierung_snapshot r ON r.az = a.az
    ORDER BY a.letzter_sync DESC
  `).all(userId);

  return rows.map((row: any) => {
    const schaden = _parseJson<Record<string, number>>(row.schaden_json, {});
    // B1 speichert regulierung_snapshot als Record<string,number>: {"sv_kosten": 1500}
    const regPos = _parseJson<Record<string, number>>(row.reg_json, {});

    const sv_gefordert = Number(schaden.sv_kosten ?? 0);
    const sv_reguliert = Number(regPos.sv_kosten ?? 0);

    return {
      az: row.az,
      unfalldatum: row.unfalldatum ?? null,
      kennzeichen: row.kennzeichen ?? null,
      haftungsquote: row.haftungsquote ?? null,
      ampel_status: row.ampel_status as AmpelStatus,
      ampel_farbe: row.ampel_farbe,
      status: row.status,
      gutachten_nr: row.gutachten_nr ?? null,
      sv_kosten_gefordert: sv_gefordert,
      sv_kosten_reguliert: sv_reguliert,
      ga_rechnung_status: _gaStatus(sv_gefordert, sv_reguliert),
      letzter_sync: row.letzter_sync ?? null,
      docs_count: row.docs_count,
    };
  });
}

export function getSvKpi(userId: string, db = getDb()): SvKpiData {
  const akten = getSvAkten(userId, db);
  const gesamt = akten.length;
  const abgeschlossen = akten.filter(a => a.status === "abgeschlossen").length;
  const in_regulierung = akten.filter(a =>
    ["regulierung_laeuft", "zahlung_angekuendigt", "teilreguliert"].includes(a.ampel_status)
  ).length;
  const offen = gesamt - abgeschlossen;
  const summe_offene_rechnung = akten
    .filter(a => a.ga_rechnung_status !== "bezahlt")
    .reduce((sum, a) => sum + Math.max(0, a.sv_kosten_gefordert - a.sv_kosten_reguliert), 0);

  return { gesamt, offen, in_regulierung, abgeschlossen, summe_offene_rechnung };
}

export function getSvAkteDetail(
  userId: string,
  az: string,
  db = getDb()
): SvAkteDetail | null {
  const akte = (db as any).prepare(`
    SELECT a.*, az.gutachten_nr
    FROM akten a
    JOIN akte_zugriff az ON az.az = a.az AND az.user_id = ?
    WHERE a.az = ?
  `).get(userId, az) as any;

  if (!akte) return null;

  const schadenRow = db.prepare("SELECT positionen_json FROM schaden_snapshot WHERE az = ?").get(az) as any;
  const regRow     = db.prepare("SELECT positionen_json FROM regulierung_snapshot WHERE az = ?").get(az) as any;
  const schaden  = _parseJson<Record<string, number>>(schadenRow?.positionen_json, {});
  const regPos   = _parseJson<Record<string, number>>(regRow?.positionen_json, {});

  const sv_gefordert = Number(schaden.sv_kosten ?? 0);
  const sv_reguliert = Number(regPos.sv_kosten ?? 0);

  const docs = (db as any).prepare(`
    SELECT id, typ, dateiname, erstellt_am
    FROM dokumente WHERE az = ? ORDER BY erstellt_am DESC
  `).all(az) as any[];

  const history = (db as any).prepare(`
    SELECT ampel_status, ampel_farbe, timestamp
    FROM status_history WHERE az = ? ORDER BY timestamp ASC
  `).all(az) as any[];

  return {
    az: akte.az,
    unfalldatum: akte.unfalldatum ?? null,
    kennzeichen: akte.kennzeichen ?? null,
    haftungsquote: akte.haftungsquote ?? null,
    sachbearbeiter: akte.sachbearbeiter ?? null,
    status: akte.status,
    ampel_status: akte.ampel_status as AmpelStatus,
    ampel_farbe: akte.ampel_farbe,
    gutachten_nr: akte.gutachten_nr ?? null,
    letzter_sync: akte.letzter_sync ?? null,
    sv_kosten_gefordert: sv_gefordert,
    sv_kosten_reguliert: sv_reguliert,
    ga_rechnung_status: _gaStatus(sv_gefordert, sv_reguliert),
    history: history.map((h: any) => ({
      ampel_status: h.ampel_status as AmpelStatus,
      ampel_farbe: h.ampel_farbe,
      timestamp: h.timestamp,
    })),
    docs: docs.map((d: any) => ({
      id: d.id, typ: d.typ, dateiname: d.dateiname, erstellt_am: d.erstellt_am,
    })),
  };
}

export function getSvStatistik(userId: string, db = getDb()): SvStatistik {
  const akten = getSvAkten(userId, db);
  const abgeschlossene = akten.filter(a => a.status === "abgeschlossen");

  const vollreguliert = abgeschlossene.filter(a => a.ampel_status === "vollreguliert").length;
  const teilreguliert = abgeschlossene.filter(a => a.ampel_status === "teilreguliert").length;
  const offen = akten.filter(a => a.status !== "abgeschlossen").length;

  const gesamt_volumen  = akten.reduce((s, a) => s + a.sv_kosten_gefordert, 0);
  const bezahlt_volumen = akten.reduce((s, a) => s + a.sv_kosten_reguliert, 0);

  // Durchschnittliche Regulierungszeit: aus status_history
  // Erste Eintrag je Akte = Eröffnung, letzter mit vollreguliert = Abschluss
  const regZeitenRaw = (db as any).prepare(`
    SELECT
      az,
      MIN(timestamp) AS first_ts,
      MAX(CASE WHEN ampel_status = 'vollreguliert' THEN timestamp ELSE NULL END) AS done_ts
    FROM status_history
    WHERE az IN (
      SELECT az FROM akte_zugriff WHERE user_id = ?
    )
    GROUP BY az
    HAVING done_ts IS NOT NULL
  `).all(userId) as Array<{ az: string; first_ts: string; done_ts: string }>;

  let avg_regulierungszeit_tage: number | null = null;
  if (regZeitenRaw.length > 0) {
    const tage = regZeitenRaw.map(r => {
      const diff = new Date(r.done_ts).getTime() - new Date(r.first_ts).getTime();
      return diff / (1000 * 60 * 60 * 24);
    });
    avg_regulierungszeit_tage = Math.round(tage.reduce((s, t) => s + t, 0) / tage.length);
  }

  // Monatliche Aktivität (letzter 12 Monate, basierend auf letzter_sync)
  const now = new Date();
  const monatlich = Array.from({ length: 12 }, (_, i) => {
    const d = new Date(now.getFullYear(), now.getMonth() - (11 - i), 1);
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const anzahl = akten.filter(a => (a.letzter_sync ?? "").startsWith(ym)).length;
    return { monat: ym, anzahl };
  });

  return {
    gesamt: akten.length,
    vollreguliert,
    teilreguliert,
    offen,
    gesamt_volumen,
    bezahlt_volumen,
    avg_regulierungszeit_tage,
    monatlich,
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function _parseJson<T>(raw: string | null | undefined, fallback: T): T {
  if (!raw) return fallback;
  try { return JSON.parse(raw); } catch { return fallback; }
}

function _gaStatus(gefordert: number, reguliert: number): GaRechnungStatus {
  if (gefordert === 0) return "offen";
  if (reguliert >= gefordert) return "bezahlt";
  if (reguliert > 0) return "teilbezahlt";
  return "offen";
}
```

- [ ] **Step 3.4: Tests laufen lassen**

```bash
npm test
```

Erwartetes Ergebnis: PASS (alle Tests grün — mind. 9 Tests)

- [ ] **Step 3.5: Commit**

```bash
git add src/lib/sv-data.ts src/lib/__tests__/sv-data.test.ts
git commit -m "feat: B2 Daten-Layer – getSvAkten/Kpi/Detail/Statistik mit Vitest-Tests"
```

---

## Task 4: UI-Komponenten (AmpelBadge · KpiCard · AktenTable)

**Files:**
- Modify: `src/components/AmpelBadge.tsx`
- Create: `src/components/KpiCard.tsx`
- Create: `src/components/AktenTable.tsx`

- [ ] **Step 4.1: `src/components/AmpelBadge.tsx` ersetzen**

```typescript
import type { AmpelStatus } from "@/types";

type AmpelCfg = { label: string; colorVar: string };

const AMPEL: Record<AmpelStatus, AmpelCfg> = {
  akte_eroeffnet:       { label: "Akte eröffnet",         colorVar: "var(--ampel-grau)"      },
  gutachten_beauftragt: { label: "Gutachten eingegangen",  colorVar: "var(--ampel-blau)"      },
  regulierung_laeuft:   { label: "Regulierung beantragt",  colorVar: "var(--ampel-gelb)"      },
  zahlung_angekuendigt: { label: "Zahlung angekündigt",    colorVar: "var(--ampel-hellgruen)" },
  vollreguliert:        { label: "Vollständig reguliert",  colorVar: "var(--ampel-gruen)"     },
  teilreguliert:        { label: "Teilregulierung",        colorVar: "var(--ampel-orange)"    },
  klage_eingereicht:    { label: "Klage erhoben",          colorVar: "var(--ampel-rot)"       },
  gutachten_bestritten: { label: "Gutachten bestritten",   colorVar: "var(--ampel-dunkelrot)" },
};

export function AmpelBadge({ status }: { status: AmpelStatus }) {
  const cfg = AMPEL[status] ?? AMPEL.akte_eroeffnet;
  return (
    <span
      style={{ color: cfg.colorVar }}
      className="inline-flex items-center gap-1.5 text-sm font-medium"
    >
      <span
        style={{ backgroundColor: cfg.colorVar }}
        className="w-2 h-2 rounded-full shrink-0"
      />
      {cfg.label}
    </span>
  );
}

export type { AmpelStatus };
```

- [ ] **Step 4.2: `src/components/KpiCard.tsx` erstellen**

```typescript
interface KpiCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  accent?: boolean;
}

export function KpiCard({ label, value, sublabel, accent }: KpiCardProps) {
  return (
    <div
      style={{
        backgroundColor: accent ? "var(--accent-subtle)" : "var(--bg-surface)",
        border: `1px solid ${accent ? "var(--accent)" : "var(--border)"}`,
        borderRadius: "var(--radius-lg)",
        padding: "20px 24px",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        minWidth: 0,
      }}
    >
      <span
        style={{
          fontSize: "0.75rem",
          fontWeight: 500,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          color: accent ? "var(--accent)" : "var(--text-subtle)",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: "2rem",
          fontWeight: 700,
          lineHeight: 1.1,
          color: accent ? "var(--accent)" : "var(--text)",
          fontVariantNumeric: "tabular-nums lining-nums",
        }}
      >
        {value}
      </span>
      {sublabel && (
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          {sublabel}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 4.3: `src/components/AktenTable.tsx` erstellen (Client Component)**

```typescript
"use client";
import { useState, useMemo } from "react";
import Link from "next/link";
import { ArrowUpDown, Search } from "lucide-react";
import { AmpelBadge } from "./AmpelBadge";
import type { SvAkteRow, GaRechnungStatus, AmpelStatus } from "@/types";

type SortKey = keyof Pick<SvAkteRow, "az" | "unfalldatum" | "ampel_status" | "ga_rechnung_status" | "letzter_sync">;
type SortDir = "asc" | "desc";

interface AktenTableProps {
  akten: SvAkteRow[];
}

const GA_STATUS_LABEL: Record<GaRechnungStatus, string> = {
  offen:       "Offen",
  teilbezahlt: "Teilbezahlt",
  bezahlt:     "Bezahlt",
};

const GA_STATUS_COLOR: Record<GaRechnungStatus, string> = {
  offen:       "var(--status-offen)",
  teilbezahlt: "var(--status-teilbez)",
  bezahlt:     "var(--status-bezahlt)",
};

export function AktenTable({ akten }: AktenTableProps) {
  const [query, setQuery]       = useState("");
  const [sortKey, setSortKey]   = useState<SortKey>("letzter_sync");
  const [sortDir, setSortDir]   = useState<SortDir>("desc");
  const [filterStatus, setFilterStatus] = useState<AmpelStatus | "alle">("alle");

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return akten
      .filter(a => {
        if (filterStatus !== "alle" && a.ampel_status !== filterStatus) return false;
        if (!q) return true;
        return (
          a.az.toLowerCase().includes(q) ||
          (a.kennzeichen ?? "").toLowerCase().includes(q) ||
          (a.gutachten_nr ?? "").toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        const va = a[sortKey] ?? "";
        const vb = b[sortKey] ?? "";
        const cmp = String(va).localeCompare(String(vb), "de");
        return sortDir === "asc" ? cmp : -cmp;
      });
  }, [akten, query, sortKey, sortDir, filterStatus]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }

  const uniqueStatuses = [...new Set(akten.map(a => a.ampel_status))];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Toolbar */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ position: "relative", flex: "1 1 240px", maxWidth: 360 }}>
          <Search
            size={15}
            style={{
              position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)",
              color: "var(--text-subtle)", pointerEvents: "none",
            }}
          />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Suche nach AZ, Kennzeichen, GA-Nr."
            style={{
              width: "100%",
              paddingLeft: 36, paddingRight: 12,
              height: 38,
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              color: "var(--text)",
              fontSize: "0.875rem",
              outline: "none",
              transition: "border-color 0.15s",
            }}
            onFocus={e => (e.target.style.borderColor = "var(--accent)")}
            onBlur={e => (e.target.style.borderColor = "var(--border)")}
          />
        </div>

        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value as AmpelStatus | "alle")}
          style={{
            height: 38,
            paddingInline: 12,
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-md)",
            color: "var(--text)",
            fontSize: "0.875rem",
            cursor: "pointer",
          }}
        >
          <option value="alle">Alle Status</option>
          {uniqueStatuses.map(s => (
            <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
          ))}
        </select>

        <span style={{ fontSize: "0.8rem", color: "var(--text-subtle)", marginLeft: "auto" }}>
          {filtered.length} von {akten.length}
        </span>
      </div>

      {/* Tabelle */}
      <div style={{
        overflowX: "auto",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        backgroundColor: "var(--bg-surface)",
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              {[
                { key: "az" as SortKey,              label: "Aktenzeichen" },
                { key: "unfalldatum" as SortKey,     label: "Unfalldatum" },
                { key: "ampel_status" as SortKey,    label: "Status" },
                { key: "ga_rechnung_status" as SortKey, label: "GA-Rechnung" },
                { key: "letzter_sync" as SortKey,   label: "Letztes Update" },
              ].map(col => (
                <th
                  key={col.key}
                  onClick={() => toggleSort(col.key)}
                  style={{
                    padding: "10px 16px",
                    textAlign: "left",
                    fontWeight: 500,
                    fontSize: "0.75rem",
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                    color: "var(--text-subtle)",
                    cursor: "pointer",
                    userSelect: "none",
                    whiteSpace: "nowrap",
                  }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    {col.label}
                    <ArrowUpDown size={11} style={{
                      opacity: sortKey === col.key ? 1 : 0.35,
                      color: sortKey === col.key ? "var(--accent)" : undefined,
                    }} />
                  </span>
                </th>
              ))}
              <th style={{ padding: "10px 16px", width: 48 }} />
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding: "48px 16px", textAlign: "center", color: "var(--text-subtle)" }}>
                  Keine Einträge gefunden
                </td>
              </tr>
            )}
            {filtered.map((a, i) => (
              <tr
                key={a.az}
                style={{
                  borderBottom: i < filtered.length - 1 ? "1px solid var(--border)" : undefined,
                  transition: "background-color 0.1s",
                }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = "var(--bg-subtle)")}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = "transparent")}
              >
                <td style={{ padding: "12px 16px" }}>
                  <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: 500 }}>
                    {a.az}
                  </span>
                  {a.gutachten_nr && (
                    <span style={{ display: "block", fontSize: "0.75rem", color: "var(--text-subtle)" }}>
                      GA: {a.gutachten_nr}
                    </span>
                  )}
                  {a.kennzeichen && (
                    <span style={{ display: "block", fontSize: "0.75rem", color: "var(--text-subtle)" }}>
                      {a.kennzeichen}
                    </span>
                  )}
                </td>
                <td style={{ padding: "12px 16px", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                  {a.unfalldatum ? new Date(a.unfalldatum).toLocaleDateString("de-DE") : "—"}
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <AmpelBadge status={a.ampel_status} />
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <span style={{ color: GA_STATUS_COLOR[a.ga_rechnung_status], fontWeight: 500, fontSize: "0.8rem" }}>
                    {GA_STATUS_LABEL[a.ga_rechnung_status]}
                  </span>
                  {a.sv_kosten_gefordert > 0 && (
                    <span style={{ display: "block", fontSize: "0.75rem", color: "var(--text-subtle)" }}>
                      {a.sv_kosten_reguliert.toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
                      {" / "}
                      {a.sv_kosten_gefordert.toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
                    </span>
                  )}
                </td>
                <td style={{ padding: "12px 16px", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                  {a.letzter_sync ? new Date(a.letzter_sync).toLocaleDateString("de-DE") : "—"}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right" }}>
                  <Link
                    href={`/sv/${encodeURIComponent(a.az)}`}
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--accent)",
                      textDecoration: "none",
                      padding: "4px 8px",
                      borderRadius: "var(--radius-sm)",
                      transition: "background 0.1s",
                    }}
                  >
                    Detail →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 4.4: Commit**

```bash
git add src/components/AmpelBadge.tsx src/components/KpiCard.tsx src/components/AktenTable.tsx
git commit -m "feat: B2 UI-Komponenten – AmpelBadge (7 Zustände), KpiCard, AktenTable mit Filter/Sort/Search"
```

---

## Task 5: Cockpit-Seite `/sv` (KPI + Tabs: Akten | Statistik)

**Files:**
- Modify: `src/app/(authed)/sv/page.tsx`
- Create: `src/components/StatistikCharts.tsx`

- [ ] **Step 5.1: `src/components/StatistikCharts.tsx` erstellen (Client Component)**

```typescript
"use client";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import type { SvStatistik } from "@/types";

interface StatistikChartsProps {
  statistik: SvStatistik;
}

export function StatistikCharts({ statistik }: StatistikChartsProps) {
  const pieData = [
    { name: "Vollreguliert", value: statistik.vollreguliert, color: "var(--ampel-gruen)" },
    { name: "Teilreguliert", value: statistik.teilreguliert, color: "var(--ampel-orange)" },
    { name: "Offen",         value: statistik.offen,         color: "var(--ampel-grau)"   },
  ].filter(d => d.value > 0);

  const barData = statistik.monatlich.map(m => ({
    name: m.monat.slice(5),  // "03" statt "2026-03"
    anzahl: m.anzahl,
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
      {/* KPI-Zeile */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
        <StatKpi
          label="Gutachten gesamt"
          value={String(statistik.gesamt)}
        />
        <StatKpi
          label="Ø Regulierungszeit"
          value={statistik.avg_regulierungszeit_tage !== null
            ? `${statistik.avg_regulierungszeit_tage} Tage`
            : "—"
          }
        />
        <StatKpi
          label="Gesamtvolumen GA-Rechnung"
          value={statistik.gesamt_volumen.toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
        />
        <StatKpi
          label="Reguliert"
          value={statistik.bezahlt_volumen.toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
          accent
        />
      </div>

      {/* Charts */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
        {/* Balkendiagramm: Aktivität je Monat */}
        <div>
          <h3 style={{
            fontSize: "0.75rem", fontWeight: 500, letterSpacing: "0.05em",
            textTransform: "uppercase", color: "var(--text-subtle)", marginBottom: 16,
          }}>
            Aktivität (letzte 12 Monate)
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={barData} barSize={18}>
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: "var(--text-subtle)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "var(--text-subtle)" }}
                axisLine={false}
                tickLine={false}
                width={24}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-surface)", border: "1px solid var(--border)",
                  borderRadius: 8, fontSize: 12, color: "var(--text)",
                }}
                cursor={{ fill: "var(--bg-subtle)" }}
              />
              <Bar dataKey="anzahl" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Donut: Erfolgsquote */}
        <div>
          <h3 style={{
            fontSize: "0.75rem", fontWeight: 500, letterSpacing: "0.05em",
            textTransform: "uppercase", color: "var(--text-subtle)", marginBottom: 16,
          }}>
            Abschlussquote
          </h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} stroke="none" />
                  ))}
                </Pie>
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(v) => (
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{v}</span>
                  )}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-surface)", border: "1px solid var(--border)",
                    borderRadius: 8, fontSize: 12, color: "var(--text)",
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p style={{ color: "var(--text-subtle)", fontSize: "0.875rem" }}>
              Noch keine abgeschlossenen Fälle.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function StatKpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div style={{
      padding: "16px 20px",
      backgroundColor: "var(--bg-surface)",
      border: `1px solid ${accent ? "var(--accent)" : "var(--border)"}`,
      borderRadius: "var(--radius-lg)",
    }}>
      <p style={{ fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-subtle)", marginBottom: 6 }}>
        {label}
      </p>
      <p style={{
        fontSize: "1.35rem", fontWeight: 700,
        color: accent ? "var(--accent)" : "var(--text)",
        fontVariantNumeric: "tabular-nums lining-nums",
      }}>
        {value}
      </p>
    </div>
  );
}
```

- [ ] **Step 5.2: `src/app/(authed)/sv/page.tsx` implementieren**

Ersetze den B1-Placeholder vollständig:

```typescript
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { getSvAkten, getSvKpi, getSvStatistik } from "@/lib/sv-data";
import { KpiCard } from "@/components/KpiCard";
import { AktenTable } from "@/components/AktenTable";
import { StatistikCharts } from "@/components/StatistikCharts";
import { ThemeToggle } from "@/components/ThemeToggle";
import { CockpitTabs } from "@/components/CockpitTabs";

export default async function SvCockpitPage() {
  const session = await getSession();
  if (!session || session.rolle !== "sachverstaendiger") redirect("/login");

  const [akten, kpi, statistik] = await Promise.all([
    Promise.resolve(getSvAkten(session.userId)),
    Promise.resolve(getSvKpi(session.userId)),
    Promise.resolve(getSvStatistik(session.userId)),
  ]);

  const kanzleiName = process.env.NEXT_PUBLIC_KANZLEI_NAME ?? "Kanzlei";

  return (
    <div style={{
      minHeight: "100vh",
      backgroundColor: "var(--bg)",
      display: "flex",
      flexDirection: "column",
    }}>
      {/* Header */}
      <header style={{
        backgroundColor: "var(--bg-surface)",
        borderBottom: "1px solid var(--border)",
        padding: "0 24px",
        height: 56,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}>
        <span style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text)" }}>
          {kanzleiName}
          <span style={{ color: "var(--text-muted)", fontWeight: 400 }}> · Sachverständigen-Portal</span>
        </span>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: "0.8rem", color: "var(--text-subtle)" }}>
            {session.name}
          </span>
          <ThemeToggle />
        </div>
      </header>

      {/* Main Content */}
      <main style={{ flex: 1, padding: "32px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {/* Page Title */}
        <div style={{ marginBottom: 32 }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--text)", margin: 0 }}>
            Meine Gutachten
          </h1>
          <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginTop: 4 }}>
            {kpi.gesamt} Vorgänge · {kpi.offen} offen
          </p>
        </div>

        {/* KPI-Kacheln */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 16,
          marginBottom: 40,
        }}>
          <KpiCard label="Gesamt"         value={kpi.gesamt}        />
          <KpiCard label="Offen"          value={kpi.offen}         />
          <KpiCard label="In Regulierung" value={kpi.in_regulierung} />
          <KpiCard label="Abgeschlossen"  value={kpi.abgeschlossen}  />
          <KpiCard
            label="Offene GA-Rechnung"
            value={kpi.summe_offene_rechnung.toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
            accent={kpi.summe_offene_rechnung > 0}
          />
        </div>

        {/* Tabs */}
        <CockpitTabs
          aktenContent={<AktenTable akten={akten} />}
          statistikContent={<StatistikCharts statistik={statistik} />}
        />
      </main>
    </div>
  );
}
```

- [ ] **Step 5.3: `src/components/CockpitTabs.tsx` erstellen**

```typescript
"use client";
import { useState } from "react";

interface CockpitTabsProps {
  aktenContent: React.ReactNode;
  statistikContent: React.ReactNode;
}

export function CockpitTabs({ aktenContent, statistikContent }: CockpitTabsProps) {
  const [active, setActive] = useState<"akten" | "statistik">("akten");

  const tabs = [
    { id: "akten"     as const, label: "Akten" },
    { id: "statistik" as const, label: "Statistik" },
  ];

  return (
    <div>
      {/* Tab-Leiste */}
      <div style={{
        display: "flex",
        gap: 0,
        borderBottom: "1px solid var(--border)",
        marginBottom: 28,
      }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActive(tab.id)}
            style={{
              padding: "8px 20px",
              fontSize: "0.875rem",
              fontWeight: active === tab.id ? 600 : 400,
              color: active === tab.id ? "var(--text)" : "var(--text-muted)",
              background: "none",
              border: "none",
              cursor: "pointer",
              borderBottom: active === tab.id
                ? "2px solid var(--accent)"
                : "2px solid transparent",
              marginBottom: -1,
              transition: "color 0.15s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab-Inhalt */}
      <div style={{ display: active === "akten" ? "block" : "none" }}>
        {aktenContent}
      </div>
      <div style={{ display: active === "statistik" ? "block" : "none" }}>
        {statistikContent}
      </div>
    </div>
  );
}
```

- [ ] **Step 5.4: Dev-Server testen**

```bash
npm run dev
```

Als SV-User anmelden (über `/login`). Die Cockpit-Seite unter `/sv` öffnen. Prüfen:
- KPI-Kacheln zeigen Werte aus DB
- Tabelle zeigt Akten (ggf. leer wenn keine Sync-Daten)
- Tab-Wechsel zwischen Akten und Statistik funktioniert
- Theme-Toggle wechselt Light/Dark korrekt

- [ ] **Step 5.5: Commit**

```bash
git add src/app/"(authed)"/sv/page.tsx src/components/CockpitTabs.tsx src/components/StatistikCharts.tsx
git commit -m "feat: B2 Cockpit-Seite /sv – KPI-Kacheln, Akten-Tabelle, Statistik-Tab, Theme-Toggle"
```

---

## Task 6: Case-Detail-Ansicht `/sv/[az]`

**Files:**
- Create: `src/app/(authed)/sv/[az]/page.tsx`
- Create: `src/components/StatusTimeline.tsx`

- [ ] **Step 6.1: `src/components/StatusTimeline.tsx` erstellen**

```typescript
import type { StatusHistoryEntry, AmpelStatus } from "@/types";

const AMPEL_LABEL: Partial<Record<AmpelStatus, string>> = {
  akte_eroeffnet:       "Akte eröffnet",
  gutachten_beauftragt: "Gutachten eingegangen",
  regulierung_laeuft:   "Regulierung beantragt",
  zahlung_angekuendigt: "Zahlung angekündigt",
  vollreguliert:        "Vollständig reguliert",
  teilreguliert:        "Teilregulierung",
  klage_eingereicht:    "Klage erhoben",
  gutachten_bestritten: "Gutachten bestritten",
};

const AMPEL_CSS_VAR: Partial<Record<string, string>> = {
  grau:       "var(--ampel-grau)",
  blau:       "var(--ampel-blau)",
  gelb:       "var(--ampel-gelb)",
  hellgruen:  "var(--ampel-hellgruen)",
  gruen:      "var(--ampel-gruen)",
  orange:     "var(--ampel-orange)",
  rot:        "var(--ampel-rot)",
  dunkelrot:  "var(--ampel-dunkelrot)",
};

interface StatusTimelineProps {
  history: StatusHistoryEntry[];
}

export function StatusTimeline({ history }: StatusTimelineProps) {
  if (history.length === 0) {
    return (
      <p style={{ color: "var(--text-subtle)", fontSize: "0.875rem" }}>
        Noch keine Statuseinträge vorhanden.
      </p>
    );
  }

  return (
    <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 0 }}>
      {history.map((entry, i) => {
        const isLast = i === history.length - 1;
        const color = AMPEL_CSS_VAR[entry.ampel_farbe] ?? "var(--ampel-grau)";
        return (
          <li key={i} style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
            {/* Dot + Line */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 3 }}>
              <div style={{
                width: 10, height: 10,
                borderRadius: "50%",
                backgroundColor: color,
                flexShrink: 0,
                boxShadow: isLast ? `0 0 0 3px color-mix(in oklch, ${color} 25%, transparent)` : "none",
              }} />
              {!isLast && (
                <div style={{
                  width: 1,
                  flex: 1,
                  minHeight: 28,
                  backgroundColor: "var(--border)",
                  marginTop: 4,
                }} />
              )}
            </div>

            {/* Content */}
            <div style={{ paddingBottom: isLast ? 0 : 20 }}>
              <p style={{
                margin: 0,
                fontSize: "0.875rem",
                fontWeight: isLast ? 600 : 400,
                color: isLast ? "var(--text)" : "var(--text-muted)",
              }}>
                {AMPEL_LABEL[entry.ampel_status] ?? entry.ampel_status}
              </p>
              <p style={{ margin: "2px 0 0", fontSize: "0.75rem", color: "var(--text-subtle)" }}>
                {new Date(entry.timestamp).toLocaleDateString("de-DE", {
                  day: "2-digit", month: "long", year: "numeric",
                })}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
```

- [ ] **Step 6.2: `src/app/(authed)/sv/[az]/page.tsx` erstellen**

```typescript
import { notFound, redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Download, FileText, Upload } from "lucide-react";
import { getSession } from "@/lib/session";
import { getSvAkteDetail } from "@/lib/sv-data";
import { AmpelBadge } from "@/components/AmpelBadge";
import { StatusTimeline } from "@/components/StatusTimeline";
import { ThemeToggle } from "@/components/ThemeToggle";

interface Props {
  params: Promise<{ az: string }>;
}

export default async function SvDetailPage({ params }: Props) {
  const session = await getSession();
  if (!session || session.rolle !== "sachverstaendiger") redirect("/login");

  const { az } = await params;
  const detail = getSvAkteDetail(session.userId, decodeURIComponent(az));
  if (!detail) notFound();

  const kanzleiName = process.env.NEXT_PUBLIC_KANZLEI_NAME ?? "Kanzlei";

  const GA_STATUS_COLOR = {
    offen:       "var(--status-offen)",
    teilbezahlt: "var(--status-teilbez)",
    bezahlt:     "var(--status-bezahlt)",
  } as const;

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--bg)" }}>
      {/* Header */}
      <header style={{
        backgroundColor: "var(--bg-surface)",
        borderBottom: "1px solid var(--border)",
        padding: "0 24px",
        height: 56,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}>
        <Link
          href="/sv"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: "0.875rem",
            color: "var(--text-muted)",
            textDecoration: "none",
          }}
        >
          <ArrowLeft size={15} />
          {kanzleiName}
        </Link>
        <ThemeToggle />
      </header>

      <main style={{ padding: "32px 24px", maxWidth: 900, margin: "0 auto" }}>
        {/* Titel-Zeile */}
        <div style={{ marginBottom: 32 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0, fontVariantNumeric: "tabular-nums" }}>
              {detail.az}
            </h1>
            <AmpelBadge status={detail.ampel_status} />
          </div>
          {detail.gutachten_nr && (
            <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginTop: 4 }}>
              GA-Nr.: {detail.gutachten_nr}
            </p>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
          {/* Linke Spalte */}
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* Metadaten */}
            <Section title="Falldetails">
              <MetaRow label="Unfalldatum"  value={detail.unfalldatum ? new Date(detail.unfalldatum).toLocaleDateString("de-DE") : "—"} />
              <MetaRow label="Kennzeichen"  value={detail.kennzeichen ?? "—"} />
              <MetaRow label="Haftungsquote" value={detail.haftungsquote !== null ? `${Math.round(detail.haftungsquote * 100)} %` : "—"} />
              <MetaRow label="Sachbearbeiterin" value={detail.sachbearbeiter ?? "—"} />
              <MetaRow label="Letztes Update" value={detail.letzter_sync ? new Date(detail.letzter_sync).toLocaleDateString("de-DE") : "—"} />
            </Section>

            {/* GA-Rechnung */}
            <Section title="Gutachterrechnung">
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "12px 0",
                borderBottom: "1px solid var(--border)",
              }}>
                <span style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>Status</span>
                <span style={{
                  fontWeight: 600,
                  fontSize: "0.875rem",
                  color: GA_STATUS_COLOR[detail.ga_rechnung_status],
                }}>
                  {detail.ga_rechnung_status === "offen" ? "Offen"
                   : detail.ga_rechnung_status === "teilbezahlt" ? "Teilbezahlt"
                   : "Bezahlt"}
                </span>
              </div>
              {detail.sv_kosten_gefordert > 0 && (
                <>
                  <MetaRow
                    label="Gefordert"
                    value={detail.sv_kosten_gefordert.toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
                  />
                  <MetaRow
                    label="Reguliert"
                    value={detail.sv_kosten_reguliert.toLocaleString("de-DE", { style: "currency", currency: "EUR" })}
                  />
                </>
              )}
            </Section>
          </div>

          {/* Rechte Spalte */}
          <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
            {/* Status-Timeline */}
            <Section title="Statusverlauf">
              <StatusTimeline history={detail.history} />
            </Section>
          </div>
        </div>

        {/* Dokumente */}
        <div style={{ marginTop: 32 }}>
          <Section title="Dokumente">
            {detail.docs.length === 0 ? (
              <p style={{ fontSize: "0.875rem", color: "var(--text-subtle)", padding: "12px 0" }}>
                Noch keine freigegebenen Dokumente vorhanden.
              </p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: "0 0 24px" }}>
                {detail.docs.map(doc => (
                  <li key={doc.id} style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 0",
                    borderBottom: "1px solid var(--border)",
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <FileText size={16} style={{ color: "var(--text-subtle)", flexShrink: 0 }} />
                      <div>
                        <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text)" }}>{doc.dateiname}</p>
                        <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--text-subtle)" }}>
                          {new Date(doc.erstellt_am).toLocaleDateString("de-DE")} · {doc.typ}
                        </p>
                      </div>
                    </div>
                    <a
                      href={`/api/dokumente/${doc.id}`}
                      download
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        fontSize: "0.8rem",
                        color: "var(--accent)",
                        textDecoration: "none",
                      }}
                    >
                      <Download size={13} />
                      Download
                    </a>
                  </li>
                ))}
              </ul>
            )}

            {/* Upload-Stub */}
            <div style={{
              border: "1px dashed var(--border-strong)",
              borderRadius: "var(--radius-md)",
              padding: "20px 24px",
              textAlign: "center",
              backgroundColor: "var(--bg-subtle)",
            }}>
              <Upload size={20} style={{ color: "var(--text-subtle)", marginBottom: 8 }} />
              <p style={{ margin: "0 0 4px", fontSize: "0.875rem", fontWeight: 500, color: "var(--text-muted)" }}>
                Dokument einreichen
              </p>
              <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--text-subtle)" }}>
                Upload-Funktion wird in Kürze verfügbar (z. B. Ergänzungsgutachten)
              </p>
            </div>
          </Section>
        </div>
      </main>
    </div>
  );
}

// ─── Hilfskomponenten ──────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 style={{
        fontSize: "0.75rem",
        fontWeight: 500,
        letterSpacing: "0.05em",
        textTransform: "uppercase",
        color: "var(--text-subtle)",
        margin: "0 0 16px",
      }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      padding: "8px 0",
      borderBottom: "1px solid var(--border)",
      gap: 16,
    }}>
      <span style={{ fontSize: "0.875rem", color: "var(--text-muted)", flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: "0.875rem", color: "var(--text)", textAlign: "right" }}>{value}</span>
    </div>
  );
}
```

- [ ] **Step 6.2b: Notizfeld-Stub + Kontaktbutton in Detail-Ansicht ergänzen**

Füge nach dem Upload-Stub-Block in `src/app/(authed)/sv/[az]/page.tsx` hinzu:

```typescript
{/* Notizfeld-Stub */}
<div style={{ marginTop: 24 }}>
  <Section title="Nachricht an die Kanzlei">
    <div style={{
      border: "1px solid var(--border)",
      borderRadius: "var(--radius-md)",
      padding: "20px 24px",
      backgroundColor: "var(--bg-subtle)",
      textAlign: "center",
    }}>
      <p style={{ margin: "0 0 4px", fontSize: "0.875rem", fontWeight: 500, color: "var(--text-muted)" }}>
        Kommunikation
      </p>
      <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--text-subtle)" }}>
        Nachrichten an die Kanzlei werden in Kürze verfügbar sein.
      </p>
    </div>
    {/* Kontaktbutton: zeigt Sachbearbeiterin direkt */}
    {detail.sachbearbeiter && (
      <p style={{ marginTop: 12, fontSize: "0.8rem", color: "var(--text-muted)" }}>
        Zuständige Sachbearbeiterin:{" "}
        <strong style={{ color: "var(--text)" }}>{detail.sachbearbeiter}</strong>
      </p>
    )}
  </Section>
</div>
```

**Hinweis:** Der Kontaktbutton zeigt nur den Namen. Vollständige asynchrone Nachrichten-Funktion (Chat-UI, Posteingang für Kanzlei) kommt in Portal-B3.

- [ ] **Step 6.3: Download-Endpoint erstellen**

```typescript
// src/app/api/dokumente/[id]/route.ts
import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { getDb } from "@/lib/db";
import fs from "fs";
import path from "path";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getSession(req);
  if (!session) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { id } = await params;
  const db = getDb();
  const doc = (db as any).prepare(`
    SELECT d.id, d.az, d.dateiname, d.encrypted_path, d.typ
    FROM dokumente d
    JOIN akte_zugriff az ON az.az = d.az AND az.user_id = ?
    WHERE d.id = ?
  `).get(session.userId, id) as any;

  if (!doc) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (!doc.encrypted_path) return NextResponse.json({ error: "File not available" }, { status: 404 });

  const filePath = path.resolve(process.cwd(), doc.encrypted_path);
  if (!fs.existsSync(filePath)) return NextResponse.json({ error: "File missing" }, { status: 404 });

  const buffer = fs.readFileSync(filePath);
  return new NextResponse(buffer, {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${encodeURIComponent(doc.dateiname)}"`,
    },
  });
}
```

**Hinweis:** Dieser Endpoint liefert Dateien direkt. In B1 werden Dokumente verschlüsselt gespeichert (`encrypted_path` + AES-256). Falls B1 eine Entschlüsselungslogik implementiert hat, muss diese hier eingebunden werden.

- [ ] **Step 6.4: Dev-Server testen**

```bash
npm run dev
```

In der Akten-Tabelle auf „Detail →" klicken. Prüfen:
- Metadaten korrekt (Unfalldatum, Kennzeichen, etc.)
- GA-Rechnungs-Status korrekt
- Status-Timeline zeigt Einträge (falls status_history Daten vorhanden)
- Dokumente-Bereich zeigt freigegebene Docs
- Upload-Stub korrekt dargestellt (disabled)
- Back-Navigation zu `/sv` funktioniert

- [ ] **Step 6.5: Commit**

```bash
git add src/app/"(authed)"/sv/"[az]"/page.tsx src/components/StatusTimeline.tsx src/app/api/dokumente/
git commit -m "feat: B2 Detail-Ansicht /sv/[az] – Metadaten, GA-Rechnung, Status-Timeline, Dokumente, Upload-Stub"
```

---

## Task 7: End-to-End-Prüfung + Abschluss

- [ ] **Step 7.1: Alle Tests laufen lassen**

```bash
npm test
```

Erwartetes Ergebnis: PASS — alle Tests grün (mind. 9 Tests in sv-data.test.ts + 3 Schema-Tests)

- [ ] **Step 7.2: Produktions-Build prüfen**

```bash
npm run build
```

Erwartetes Ergebnis: Build erfolgreich, keine TypeScript-Fehler.
Falls Fehler: TypeScript-Typen prüfen, insbesondere `AmpelStatus` (B1 hatte 6 Werte, B2 hat 8).

- [ ] **Step 7.3: Manuelle Smoke-Tests (Light + Dark Mode)**

Checkliste:
- [ ] `/sv` lädt: 5 KPI-Kacheln sichtbar
- [ ] ThemeToggle wechselt Light ↔ Dark, alle Farben korrekt (insbesondere Ampelfarben)
- [ ] Tabelle: Suche nach AZ filtert korrekt
- [ ] Tabelle: Spalten-Sortierung (Klick auf Spalten-Header)
- [ ] Tabelle: Status-Filter Dropdown
- [ ] Tab „Statistik": Balken- und Donut-Diagramm rendern (kann leer sein wenn keine Daten)
- [ ] `/sv/[az]`: Falldetails korrekt
- [ ] `/sv/[az]`: Download-Link sichtbar (Klick: File-Download oder 404 wenn kein File)
- [ ] Nicht-SV-User bekommt Redirect zu `/login`

- [ ] **Step 7.4: Final Commit**

```bash
git add .
git commit -m "feat: Portal-B2 Sachverständigen-Cockpit vollständig implementiert"
```

---

## Appendix A: PORTAL-A2 – Gutachtennummer im Sync-Payload

**Datei:** `C:\Users\HAL9000\Documents\Projekt\Version 1.00\unfallakten\backend\services\portal_sync.py`

**Änderung:** `auftragsnummer` aus dem Gutachten-Parser in der unfallakten-DB persistieren und im Sync-Payload mitschicken.

**Schritt 1:** Feld in unfallakten-DB hinzufügen.
Entweder in `pruefberichte` (wenn dort der Bezug ist) oder als neues Feld in `beteiligte` für SVs:

```sql
-- Option A: neues Feld in beteiligte
ALTER TABLE beteiligte ADD COLUMN gutachten_nr TEXT;
```

**Schritt 2:** `_build_payload` in `portal_sync.py` erweitern:

```python
beteiligte = conn.execute("""
    SELECT id, rolle, name, vorname, firma, email, gutachten_nr
    FROM beteiligte WHERE akte_id = ?
""", (akte_id,)).fetchall()

# Im return-Dict:
"beteiligte": [
    {"id": b["id"], "rolle": b["rolle"], "name": b["name"],
     "vorname": b["vorname"], "firma": b["firma"], "email": b["email"],
     "gutachten_nr": b["gutachten_nr"]}   # NEU
    for b in beteiligte
],
```

**Schritt 3:** Beim Gutachten-Upload (`workflow/dispatcher.py`) die `auftragsnummer` in `beteiligte.gutachten_nr` schreiben — wenn der Gutachter als Beteiligter in der Akte eingetragen ist.

**Aufwand:** ~30 Minuten. Kann parallel zu B1 oder B2 gemacht werden. Portal-B2 zeigt `gutachten_nr` als `—` bis dieser Schritt deployed ist.

---

## Subsystem-Übersicht (Folge-Pläne)

| Plan | Scope | Status |
|------|-------|--------|
| Portal-B1 | Foundation (Scaffold, DB, Auth, Sync, Admin) | Geplant |
| Portal-B2 | **Sachverständigen-Cockpit** (dieser Plan) | Geplant |
| Portal-B3 | Privatmandanten-Dashboard (Timeline, Laiensprache, Abschluss-Summary PDF, Dokument-Upload vollständig) | Folgeplan |
| Portal-B4 | E-Mail-Benachrichtigungen, PWA (Service Worker, Manifest), Impressum/DSGVO | Folgeplan |
