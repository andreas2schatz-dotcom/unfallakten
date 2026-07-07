# Portal-B3: Privatmandanten-Dashboard – Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementiert das Privatmandanten-Dashboard im Stakeholder-Portal — eine laienverstständliche Fallübersicht mit Ampel-Timeline, Schaden-Summary, Dokumenten-Download, echtem Datei-Upload und einer druckbaren Abschluss-Zusammenfassung.

**Architecture:** Baut auf Portal-B2 (Sachverständigen-Cockpit) auf. Mandanten haben genau eine Akte; `/mandant` leitet automatisch zu `/mandant/{az}` weiter. Die Detailseite ist ein Server Component; nur der Upload-Bereich und der Print-Button sind Client Components. Ein neuer POST `/api/upload` nimmt PDF-Uploads entgegen, prüft Row-Level-Security und schreibt in die bestehende `dokumente`-Tabelle. Die Abschluss-Summary ist eine druckoptimierte Serverseite mit `@media print` CSS — kein PDF-Generator-Dependency.

**Tech Stack:** Next.js 15 App Router, TypeScript, CSS-Variablen-System aus B2, `better-sqlite3`, `uuid`, Vitest, Lucide React

**Projekt-Verzeichnis:** `C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal\`

---

## Voraussetzungen

- **Portal-B2 auf `master` gemergt** ✅ (Design-System, Typen, DB-Schema inkl. status_history)
- **Portal-A2 deployed:** `gutachten_nr` kommt im Sync — für B3 irrelevant (nur SV-Cockpit)
- Kein neues DB-Schema nötig: alle benötigten Tabellen (`akten`, `schaden_snapshot`, `regulierung_snapshot`, `dokumente`, `status_history`, `akte_zugriff`) existieren bereits

---

## File Structure

```
stakeholder-portal/
├── src/
│   ├── app/
│   │   ├── (authed)/
│   │   │   └── mandant/
│   │   │       ├── page.tsx              # MOD: Redirect-oder-Liste-Logik
│   │   │       └── [az]/
│   │   │           ├── page.tsx          # NEU: Mandant-Detailseite
│   │   │           └── summary/
│   │   │               └── page.tsx      # NEU: Druckbare Abschluss-Zusammenfassung
│   │   └── api/
│   │       └── upload/
│   │           └── route.ts             # NEU: POST Multipart-Upload (mandant only)
│   ├── components/
│   │   ├── DokumentUpload.tsx           # NEU: Client Component für Upload-UI
│   │   └── PrintButton.tsx              # NEU: Client Component für window.print()
│   ├── lib/
│   │   ├── mandant-data.ts              # NEU: Daten-Layer für Mandanten-Cockpit
│   │   └── __tests__/
│   │       └── mandant-data.test.ts     # NEU: Vitest Tests
│   └── types/
│       └── index.ts                     # MOD: MandantAkteRow, MandantAkteDetail, AMPEL_LAIENTEXTE, SCHADEN_LABELS
```

---

## Task 0: Worktree + Branch

**Files:**
- (keine Code-Änderungen)

- [ ] **Step 0.1: Worktree erstellen**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal"
git worktree add .worktrees/portal-b3 -b feature/portal-b3
```

Erwartetes Ergebnis: Verzeichnis `.worktrees/portal-b3` existiert, Branch `feature/portal-b3` ist aus `master` abgezweigt.

- [ ] **Step 0.2: Prüfen**

```bash
cd ".worktrees/portal-b3"
git log --oneline -3
```

Erwartetes Ergebnis: Letzter Commit ist der B2-Merge-Commit auf `master`.

---

## Task 1: Typen + Mandant-Data-Layer + Tests

**Files:**
- Modify: `src/types/index.ts`
- Create: `src/lib/mandant-data.ts`
- Create: `src/lib/__tests__/mandant-data.test.ts`

### 1A – Typen

- [ ] **Step 1.1: Typen an `src/types/index.ts` anhängen**

Füge am Ende der Datei hinzu:

```typescript
// ─── B3 Erweiterungen ─────────────────────────────────────────────────────

export interface MandantAkteRow {
  az: string;
  unfalldatum: string | null;
  ampel_status: AmpelStatus;
  ampel_farbe: string;
  status: AktenStatus;
  letzter_sync: string | null;
  gesamt_brutto: number;
  gesamt_reguliert: number;
}

export interface MandantAkteDetail {
  az: string;
  unfalldatum: string | null;
  kennzeichen: string | null;
  haftungsquote: number | null;
  sachbearbeiter: string | null;
  status: AktenStatus;
  ampel_status: AmpelStatus;
  ampel_farbe: string;
  letzter_sync: string | null;
  schaden: Record<string, number>;
  gesamt_brutto: number;
  gesamt_reguliert: number;
  history: StatusHistoryEntry[];
  docs: Array<{ id: string; typ: string; dateiname: string; erstellt_am: string }>;
}

export const AMPEL_LAIENTEXTE: Record<AmpelStatus, { kurz: string; lang: string }> = {
  akte_eroeffnet:       { kurz: "Akte eröffnet",               lang: "Wir haben Ihren Fall aufgenommen." },
  gutachten_beauftragt: { kurz: "Gutachten läuft",             lang: "Ein Sachverständiger begutachtet Ihr Fahrzeug." },
  regulierung_laeuft:   { kurz: "Regulierung läuft",           lang: "Wir haben die gegnerische Versicherung angeschrieben." },
  zahlung_angekuendigt: { kurz: "Zahlung angekündigt",         lang: "Die Versicherung hat eine Zahlung zugesagt." },
  teilreguliert:        { kurz: "Teilregulierung eingegangen", lang: "Ein Teil Ihres Schadens wurde bereits reguliert." },
  vollreguliert:        { kurz: "Vollständig reguliert",       lang: "Ihr Schadensfall ist vollständig abgeschlossen." },
  klage_eingereicht:    { kurz: "Klage eingereicht",           lang: "Ihr Fall wird jetzt vor Gericht weiterverfolgt." },
  gutachten_bestritten: { kurz: "Gutachten bestritten",        lang: "Die Versicherung widerspricht — wir prüfen den Fall." },
};

export const SCHADEN_LABELS: Record<string, string> = {
  reparaturkosten:   "Reparaturkosten",
  wiederbeschaffung: "Wiederbeschaffungswert",
  restwert:          "Restwert (wird abgezogen)",
  wertminderung:     "Wertminderung",
  nutzungsausfall:   "Nutzungsausfall",
  mietwagenkosten:   "Mietwagenkosten",
  sv_kosten:         "Sachverständigenkosten",
  abschleppkosten:   "Abschleppkosten",
  standkosten:       "Standkosten",
  anabmeldekosten:   "An-/Abmeldekosten",
  schmerzensgeld:    "Schmerzensgeld",
  sonstiges:         "Sonstiges",
};
```

### 1B – Daten-Layer (Tests first)

- [ ] **Step 1.2: Failing Tests schreiben**

Erstelle `src/lib/__tests__/mandant-data.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import Database from "better-sqlite3";
import { initSchema } from "@/lib/db";
import { getMandantAkten, getMandantAkteDetail } from "@/lib/mandant-data";

function buildDb() {
  const db = new Database(":memory:");
  db.pragma("foreign_keys = ON");
  initSchema(db);
  return db;
}

function seedData(db: InstanceType<typeof Database>) {
  db.prepare(
    "INSERT INTO portal_users (id, email, name, rolle) VALUES (?, ?, ?, ?)"
  ).run("user-1", "mandant@example.com", "Max Mustermann", "privatmandant");

  db.prepare(
    "INSERT INTO akten (az, status, ampel_status, ampel_farbe, unfalldatum, kennzeichen, haftungsquote, sachbearbeiter) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
  ).run("M/001/26", "in_regulierung", "regulierung_laeuft", "gelb",
        "2026-01-15", "OF-AA 123", 100.0, "Frau Koch");

  db.prepare(
    "INSERT INTO akte_zugriff (user_id, az) VALUES (?, ?)"
  ).run("user-1", "M/001/26");

  db.prepare(
    "INSERT INTO schaden_snapshot (az, gesamt_brutto, positionen_json) VALUES (?, ?, ?)"
  ).run("M/001/26", 8500.0, JSON.stringify({ reparaturkosten: 7000, schmerzensgeld: 1500 }));

  db.prepare(
    "INSERT INTO regulierung_snapshot (az, gesamt_reguliert) VALUES (?, ?)"
  ).run("M/001/26", 4000.0);
}

describe("getMandantAkten", () => {
  it("gibt Akten des Mandanten zurück", () => {
    const db = buildDb();
    seedData(db);
    const result = getMandantAkten("user-1", db);
    expect(result).toHaveLength(1);
    expect(result[0].az).toBe("M/001/26");
    expect(result[0].ampel_status).toBe("regulierung_laeuft");
  });

  it("gibt korrekte Schaden-Summen zurück", () => {
    const db = buildDb();
    seedData(db);
    const result = getMandantAkten("user-1", db);
    expect(result[0].gesamt_brutto).toBe(8500.0);
    expect(result[0].gesamt_reguliert).toBe(4000.0);
  });

  it("gibt keine Akten für andere User zurück", () => {
    const db = buildDb();
    seedData(db);
    expect(getMandantAkten("user-2", db)).toHaveLength(0);
  });

  it("gibt leere Liste zurück wenn kein Zugriff", () => {
    const db = buildDb();
    expect(getMandantAkten("user-1", db)).toHaveLength(0);
  });
});

describe("getMandantAkteDetail", () => {
  it("gibt null zurück wenn kein Zugriff", () => {
    const db = buildDb();
    seedData(db);
    expect(getMandantAkteDetail("user-2", "M/001/26", db)).toBeNull();
  });

  it("gibt null zurück für nicht existente Akte", () => {
    const db = buildDb();
    seedData(db);
    expect(getMandantAkteDetail("user-1", "M/999/99", db)).toBeNull();
  });

  it("gibt Akte mit Metadaten zurück", () => {
    const db = buildDb();
    seedData(db);
    const detail = getMandantAkteDetail("user-1", "M/001/26", db);
    expect(detail).not.toBeNull();
    expect(detail!.az).toBe("M/001/26");
    expect(detail!.kennzeichen).toBe("OF-AA 123");
    expect(detail!.sachbearbeiter).toBe("Frau Koch");
    expect(detail!.haftungsquote).toBe(100.0);
  });

  it("gibt korrekte Summen zurück", () => {
    const db = buildDb();
    seedData(db);
    const detail = getMandantAkteDetail("user-1", "M/001/26", db);
    expect(detail!.gesamt_brutto).toBe(8500.0);
    expect(detail!.gesamt_reguliert).toBe(4000.0);
  });

  it("parst schaden JSON korrekt", () => {
    const db = buildDb();
    seedData(db);
    const detail = getMandantAkteDetail("user-1", "M/001/26", db);
    expect(detail!.schaden.reparaturkosten).toBe(7000);
    expect(detail!.schaden.schmerzensgeld).toBe(1500);
  });

  it("gibt Status-History zurück", () => {
    const db = buildDb();
    seedData(db);
    db.prepare(
      "INSERT INTO status_history (id, az, ampel_status, ampel_farbe, timestamp) VALUES (?, ?, ?, ?, ?)"
    ).run("h1", "M/001/26", "akte_eroeffnet", "grau", "2026-01-15 09:00:00");
    db.prepare(
      "INSERT INTO status_history (id, az, ampel_status, ampel_farbe, timestamp) VALUES (?, ?, ?, ?, ?)"
    ).run("h2", "M/001/26", "regulierung_laeuft", "gelb", "2026-02-01 14:00:00");

    const detail = getMandantAkteDetail("user-1", "M/001/26", db);
    expect(detail!.history).toHaveLength(2);
    expect(detail!.history[0].ampel_status).toBe("akte_eroeffnet");
    expect(detail!.history[1].ampel_status).toBe("regulierung_laeuft");
  });

  it("gibt leere History zurück wenn keine Einträge", () => {
    const db = buildDb();
    seedData(db);
    const detail = getMandantAkteDetail("user-1", "M/001/26", db);
    expect(detail!.history).toHaveLength(0);
  });

  it("gibt Dokumente zurück", () => {
    const db = buildDb();
    seedData(db);
    db.prepare(
      "INSERT INTO dokumente (id, az, typ, dateiname) VALUES (?, ?, ?, ?)"
    ).run("doc-1", "M/001/26", "abrechnungsschreiben", "Abrechnung_Jan.pdf");

    const detail = getMandantAkteDetail("user-1", "M/001/26", db);
    expect(detail!.docs).toHaveLength(1);
    expect(detail!.docs[0].dateiname).toBe("Abrechnung_Jan.pdf");
  });
});
```

- [ ] **Step 1.3: Tests zum Scheitern bringen**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal\.worktrees\portal-b3"
npm test -- src/lib/__tests__/mandant-data.test.ts
```

Erwartetes Ergebnis: FAIL — `Cannot find module '@/lib/mandant-data'`

- [ ] **Step 1.4: Daten-Layer implementieren**

Erstelle `src/lib/mandant-data.ts`:

```typescript
import { getDb } from "./db";
import type { MandantAkteRow, MandantAkteDetail, StatusHistoryEntry } from "@/types";

export function getMandantAkten(userId: string, db: any = getDb()): MandantAkteRow[] {
  return db.prepare(`
    SELECT
      a.az,
      a.unfalldatum,
      a.ampel_status,
      a.ampel_farbe,
      a.status,
      a.letzter_sync,
      COALESCE(s.gesamt_brutto, 0.0)    AS gesamt_brutto,
      COALESCE(r.gesamt_reguliert, 0.0) AS gesamt_reguliert
    FROM akte_zugriff az2
    JOIN akten a ON a.az = az2.az
    LEFT JOIN schaden_snapshot s ON s.az = a.az
    LEFT JOIN regulierung_snapshot r ON r.az = a.az
    WHERE az2.user_id = ?
    ORDER BY a.letzter_sync DESC
  `).all(userId) as MandantAkteRow[];
}

export function getMandantAkteDetail(
  userId: string,
  az: string,
  db: any = getDb()
): MandantAkteDetail | null {
  const akte = db.prepare(`
    SELECT
      a.az, a.unfalldatum, a.kennzeichen, a.haftungsquote, a.sachbearbeiter,
      a.status, a.ampel_status, a.ampel_farbe, a.letzter_sync,
      COALESCE(s.positionen_json, '{}') AS schaden_json,
      COALESCE(s.gesamt_brutto, 0.0)    AS gesamt_brutto,
      COALESCE(r.gesamt_reguliert, 0.0) AS gesamt_reguliert
    FROM akte_zugriff az2
    JOIN akten a ON a.az = az2.az
    LEFT JOIN schaden_snapshot s ON s.az = a.az
    LEFT JOIN regulierung_snapshot r ON r.az = a.az
    WHERE az2.user_id = ? AND a.az = ?
  `).get(userId, az);

  if (!akte) return null;

  const history = db.prepare(`
    SELECT ampel_status, ampel_farbe, timestamp
    FROM status_history
    WHERE az = ?
    ORDER BY timestamp ASC
  `).all(az) as StatusHistoryEntry[];

  const docs = db.prepare(`
    SELECT id, typ, dateiname, erstellt_am
    FROM dokumente
    WHERE az = ?
    ORDER BY erstellt_am DESC
  `).all(az) as Array<{ id: string; typ: string; dateiname: string; erstellt_am: string }>;

  return {
    az: akte.az,
    unfalldatum: akte.unfalldatum,
    kennzeichen: akte.kennzeichen,
    haftungsquote: akte.haftungsquote,
    sachbearbeiter: akte.sachbearbeiter,
    status: akte.status,
    ampel_status: akte.ampel_status,
    ampel_farbe: akte.ampel_farbe,
    letzter_sync: akte.letzter_sync,
    schaden: JSON.parse(akte.schaden_json || "{}"),
    gesamt_brutto: akte.gesamt_brutto,
    gesamt_reguliert: akte.gesamt_reguliert,
    history,
    docs,
  };
}
```

- [ ] **Step 1.5: Tests zum Bestehen bringen**

```bash
npm test -- src/lib/__tests__/mandant-data.test.ts
```

Erwartetes Ergebnis: 12 passed

- [ ] **Step 1.6: Alle Tests prüfen**

```bash
npm test
```

Erwartetes Ergebnis: Alle bestehenden Tests (sv-data, session) weiterhin grün.

- [ ] **Step 1.7: Commit**

```bash
git add src/types/index.ts src/lib/mandant-data.ts src/lib/__tests__/mandant-data.test.ts
git commit -m "feat: B3 Typen, AMPEL_LAIENTEXTE, mandant-data Daten-Layer + Tests"
```

---

## Task 2: Mandant-Dashboard (`/mandant`)

**Files:**
- Modify: `src/app/(authed)/mandant/page.tsx`

Die Seite leitet bei genau einer Akte sofort zu `/mandant/{az}` weiter. Bei keiner Akte: Leerstate. Bei mehreren: Link-Liste. Dies ist die Normalfall-Optimierung — Mandanten haben genau eine Akte.

- [ ] **Step 2.1: `mandant/page.tsx` ersetzen**

```tsx
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { getMandantAkten } from "@/lib/mandant-data";
import { getDb } from "@/lib/db";
import { AMPEL_LAIENTEXTE } from "@/types";
import AmpelBadge from "@/components/AmpelBadge";

export default async function MandantPage() {
  const session = await getSession();
  if (!session || session.rolle !== "privatmandant") redirect("/login");

  const akten = getMandantAkten(session.userId, getDb());

  if (akten.length === 1) {
    redirect(`/mandant/${encodeURIComponent(akten[0].az)}`);
  }

  return (
    <main style={{ maxWidth: 680, margin: "0 auto", padding: "40px 24px" }}>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: "0 0 8px" }}>
        Meine Unfallakten
      </h1>

      {akten.length === 0 ? (
        <p style={{ color: "var(--text-muted)", marginTop: 32, fontSize: "0.9rem" }}>
          Sie haben derzeit keinen Aktenzugriff. Bitte wenden Sie sich an die Kanzlei.
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: "24px 0 0", display: "flex", flexDirection: "column", gap: 12 }}>
          {akten.map(akte => {
            const txt = AMPEL_LAIENTEXTE[akte.ampel_status];
            return (
              <li key={akte.az}>
                <a
                  href={`/mandant/${encodeURIComponent(akte.az)}`}
                  style={{
                    display: "block",
                    padding: "16px 20px",
                    background: "var(--bg-surface)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-md)",
                    textDecoration: "none",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <div>
                      <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-subtle)" }}>
                        Unfall vom{" "}
                        {akte.unfalldatum
                          ? new Date(akte.unfalldatum).toLocaleDateString("de-DE")
                          : "–"}
                      </p>
                      <p style={{ margin: "4px 0 0", fontWeight: 600, color: "var(--text)" }}>
                        {txt.kurz}
                      </p>
                    </div>
                    <AmpelBadge status={akte.ampel_status} />
                  </div>
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
```

- [ ] **Step 2.2: Build-Check**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal\.worktrees\portal-b3"
npx tsc --noEmit 2>&1 | head -30
```

Erwartetes Ergebnis: Keine Fehler.

- [ ] **Step 2.3: Commit**

```bash
git add src/app/\(authed\)/mandant/page.tsx
git commit -m "feat: B3 Mandant-Dashboard – Redirect-oder-Liste-Logik"
```

---

## Task 3: Mandant-Detailseite + Upload-Client-Komponente

**Files:**
- Create: `src/app/(authed)/mandant/[az]/page.tsx`
- Create: `src/components/DokumentUpload.tsx`
- Create: `src/components/PrintButton.tsx`

### 3A – Client Components

- [ ] **Step 3.1: `PrintButton.tsx` erstellen**

```tsx
// src/components/PrintButton.tsx
"use client";

export default function PrintButton({ label = "Als PDF drucken / speichern" }: { label?: string }) {
  return (
    <button
      onClick={() => window.print()}
      style={{
        display: "inline-block",
        padding: "8px 16px",
        background: "var(--accent)",
        color: "var(--accent-text)",
        border: "none",
        borderRadius: "var(--radius-sm)",
        cursor: "pointer",
        fontSize: "0.875rem",
        fontFamily: "var(--font-sans)",
      }}
    >
      {label}
    </button>
  );
}
```

- [ ] **Step 3.2: `DokumentUpload.tsx` erstellen**

```tsx
// src/components/DokumentUpload.tsx
"use client";

import { useState, useRef } from "react";
import { Upload, CheckCircle, AlertCircle } from "lucide-react";

interface Props {
  az: string;
}

export default function DokumentUpload({ az }: Props) {
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setMessage("");

    const fd = new FormData();
    fd.append("az", az);
    fd.append("file", file);

    try {
      const res = await fetch("/api/upload", { method: "POST", body: fd });
      if (res.ok) {
        setStatus("success");
        setMessage("Dokument erfolgreich eingereicht. Die Kanzlei wird es prüfen.");
      } else {
        const data = await res.json().catch(() => ({}));
        setStatus("error");
        setMessage((data as any).error ?? "Upload fehlgeschlagen.");
      }
    } catch {
      setStatus("error");
      setMessage("Verbindungsfehler. Bitte versuchen Sie es erneut.");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        style={{ display: "none" }}
        onChange={handleChange}
        disabled={status === "uploading"}
        aria-label="PDF-Datei auswählen"
      />
      <div
        role="button"
        tabIndex={0}
        aria-disabled={status === "uploading"}
        onClick={() => status !== "uploading" && status !== "success" && inputRef.current?.click()}
        onKeyDown={e => e.key === "Enter" && status !== "uploading" && status !== "success" && inputRef.current?.click()}
        style={{
          border: status === "success"
            ? "1px solid var(--ampel-gruen)"
            : "1px dashed var(--border-strong)",
          borderRadius: "var(--radius-md)",
          padding: "20px 24px",
          textAlign: "center",
          background: "var(--bg-subtle)",
          cursor: status === "uploading" || status === "success" ? "default" : "pointer",
          transition: "border-color 0.15s",
        }}
      >
        {status === "success" ? (
          <>
            <CheckCircle size={20} style={{ color: "var(--ampel-gruen)", marginBottom: 8 }} />
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--ampel-gruen)" }}>{message}</p>
          </>
        ) : status === "error" ? (
          <>
            <AlertCircle size={20} style={{ color: "var(--ampel-rot)", marginBottom: 8 }} />
            <p style={{ margin: "0 0 8px", fontSize: "0.875rem", color: "var(--ampel-rot)" }}>{message}</p>
            <span style={{ fontSize: "0.8rem", color: "var(--accent)" }}>Erneut versuchen</span>
          </>
        ) : (
          <>
            <Upload size={20} style={{ color: "var(--text-subtle)", marginBottom: 8 }} />
            <p style={{ margin: "0 0 4px", fontSize: "0.875rem", fontWeight: 500, color: "var(--text-muted)" }}>
              {status === "uploading" ? "Wird hochgeladen…" : "Dokument einreichen"}
            </p>
            <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--text-subtle)" }}>
              PDF, max. 10 MB — z. B. Ergänzungsgutachten, ärztliches Attest
            </p>
          </>
        )}
      </div>
    </div>
  );
}
```

### 3B – Detail-Server-Component

- [ ] **Step 3.3: Verzeichnisstruktur prüfen**

```bash
ls "src/app/(authed)/mandant/"
```

Erwartetes Ergebnis: Nur `page.tsx` vorhanden (kein `[az]`-Verzeichnis).

- [ ] **Step 3.4: `mandant/[az]/page.tsx` erstellen**

```tsx
// src/app/(authed)/mandant/[az]/page.tsx
import { notFound, redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { getMandantAkteDetail } from "@/lib/mandant-data";
import { getDb } from "@/lib/db";
import { AMPEL_LAIENTEXTE, type AmpelStatus } from "@/types";
import AmpelBadge from "@/components/AmpelBadge";
import DokumentUpload from "@/components/DokumentUpload";
import { FileText, Download, ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

export default async function MandantDetailPage({
  params,
}: {
  params: Promise<{ az: string }>;
}) {
  const session = await getSession();
  if (!session || session.rolle !== "privatmandant") redirect("/login");

  const { az: rawAz } = await params;
  const az = decodeURIComponent(rawAz);
  const detail = getMandantAkteDetail(session.userId, az, getDb());
  if (!detail) notFound();

  const ampelText = AMPEL_LAIENTEXTE[detail.ampel_status];
  const offen = Math.max(0, detail.gesamt_brutto - detail.gesamt_reguliert);
  const kanzleiFahrzeugDocs = detail.docs.filter(d => d.typ !== "mandant_eingang");
  const mandantDocs = detail.docs.filter(d => d.typ === "mandant_eingang");

  return (
    <main style={{ maxWidth: 760, margin: "0 auto", padding: "40px 24px" }}>

      {/* Header */}
      <div style={{ marginBottom: 36 }}>
        <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-subtle)" }}>
          Unfall vom{" "}
          {detail.unfalldatum
            ? new Date(detail.unfalldatum).toLocaleDateString("de-DE")
            : "–"}
          {detail.kennzeichen && ` · ${detail.kennzeichen}`}
        </p>
        <h1 style={{ margin: "4px 0 12px", fontSize: "1.5rem", fontWeight: 700 }}>
          {ampelText.kurz}
        </h1>
        <p style={{ margin: "0 0 12px", color: "var(--text-muted)" }}>{ampelText.lang}</p>
        <AmpelBadge status={detail.ampel_status} />
      </div>

      {/* Status-Timeline */}
      <Section title="Verlauf Ihres Falles">
        {detail.history.length === 0 ? (
          <p style={{ color: "var(--text-subtle)", fontSize: "0.875rem" }}>
            Noch keine Statusänderungen aufgezeichnet.
          </p>
        ) : (
          <ol style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {detail.history.map((h, i) => {
              const isLast = i === detail.history.length - 1;
              const txt = AMPEL_LAIENTEXTE[h.ampel_status as AmpelStatus];
              return (
                <li
                  key={i}
                  style={{ display: "flex", gap: 12, paddingBottom: isLast ? 0 : 20 }}
                >
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <div
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        flexShrink: 0,
                        marginTop: 4,
                        background: isLast ? "var(--accent)" : "var(--border-strong)",
                        boxShadow: isLast ? "0 0 0 3px var(--accent-subtle)" : "none",
                      }}
                    />
                    {!isLast && (
                      <div
                        style={{
                          width: 1,
                          flexGrow: 1,
                          background: "var(--border)",
                          marginTop: 4,
                        }}
                      />
                    )}
                  </div>
                  <div style={{ paddingBottom: isLast ? 0 : 4 }}>
                    <p
                      style={{
                        margin: 0,
                        fontSize: "0.875rem",
                        fontWeight: isLast ? 600 : 400,
                        color: isLast ? "var(--text)" : "var(--text-muted)",
                      }}
                    >
                      {txt?.kurz ?? h.ampel_status}
                    </p>
                    <p style={{ margin: "2px 0 0", fontSize: "0.75rem", color: "var(--text-subtle)" }}>
                      {new Date(h.timestamp).toLocaleDateString("de-DE", {
                        day: "2-digit",
                        month: "long",
                        year: "numeric",
                      })}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </Section>

      {/* Schaden-Übersicht */}
      <Section title="Schadensübersicht">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 12,
            marginBottom: 16,
          }}
        >
          <DataTile
            label="Gefordert"
            value={`${detail.gesamt_brutto.toLocaleString("de-DE", { minimumFractionDigits: 2 })} €`}
          />
          <DataTile
            label="Reguliert"
            value={`${detail.gesamt_reguliert.toLocaleString("de-DE", { minimumFractionDigits: 2 })} €`}
            accent
          />
          <DataTile
            label="Ausstehend"
            value={`${offen.toLocaleString("de-DE", { minimumFractionDigits: 2 })} €`}
          />
        </div>

        {detail.status === "abgeschlossen" && (
          <a
            href={`/mandant/${encodeURIComponent(az)}/summary`}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: "0.875rem",
              color: "var(--accent)",
              textDecoration: "none",
            }}
          >
            <ExternalLink size={14} />
            Abschluss-Zusammenfassung (druckbar)
          </a>
        )}
      </Section>

      {/* Kanzlei-Dokumente */}
      <Section title="Dokumente der Kanzlei">
        {kanzleiFahrzeugDocs.length === 0 ? (
          <p style={{ color: "var(--text-subtle)", fontSize: "0.875rem" }}>
            Noch keine Dokumente für Sie freigegeben.
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: "0 0 20px" }}>
            {kanzleiFahrzeugDocs.map(doc => (
              <li
                key={doc.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "10px 0",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <FileText size={16} style={{ color: "var(--text-subtle)", flexShrink: 0 }} />
                  <div>
                    <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--text)" }}>
                      {doc.dateiname}
                    </p>
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
      </Section>

      {/* Dokument einreichen */}
      <Section title="Dokument einreichen">
        {mandantDocs.length > 0 && (
          <ul style={{ listStyle: "none", padding: 0, margin: "0 0 16px" }}>
            {mandantDocs.map(doc => (
              <li
                key={doc.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 0",
                  fontSize: "0.875rem",
                  color: "var(--text-muted)",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <FileText size={14} style={{ flexShrink: 0 }} />
                {doc.dateiname} ·{" "}
                {new Date(doc.erstellt_am).toLocaleDateString("de-DE")}
              </li>
            ))}
          </ul>
        )}
        <DokumentUpload az={az} />
      </Section>

      {detail.sachbearbeiter && (
        <p
          style={{
            marginTop: 40,
            fontSize: "0.8rem",
            color: "var(--text-subtle)",
            textAlign: "center",
          }}
        >
          Ihre Sachbearbeiterin:{" "}
          <strong style={{ color: "var(--text-muted)" }}>{detail.sachbearbeiter}</strong>
        </p>
      )}
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section style={{ marginBottom: 36 }}>
      <h2
        style={{
          fontSize: "0.75rem",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.07em",
          color: "var(--text-subtle)",
          margin: "0 0 16px",
        }}
      >
        {title}
      </h2>
      {children}
    </section>
  );
}

function DataTile({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div
      style={{
        padding: "12px 16px",
        background: "var(--bg-subtle)",
        borderRadius: "var(--radius-md)",
      }}
    >
      <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--text-subtle)" }}>{label}</p>
      <p
        style={{
          margin: "4px 0 0",
          fontSize: "1.1rem",
          fontWeight: 600,
          color: accent ? "var(--accent)" : "var(--text)",
        }}
      >
        {value}
      </p>
    </div>
  );
}
```

- [ ] **Step 3.5: Build-Check**

```bash
npx tsc --noEmit 2>&1 | head -30
```

Erwartetes Ergebnis: Keine TypeScript-Fehler.

- [ ] **Step 3.6: Commit**

```bash
git add src/app/\(authed\)/mandant/\[az\]/page.tsx src/components/DokumentUpload.tsx src/components/PrintButton.tsx
git commit -m "feat: B3 Mandant-Detailseite, DokumentUpload Client-Komponente, PrintButton"
```

---

## Task 4: Upload-API

**Files:**
- Create: `src/app/api/upload/route.ts`

- [ ] **Step 4.1: Failing Test schreiben**

Füge in `src/lib/__tests__/mandant-data.test.ts` am Ende hinzu:

```typescript
// Upload API kann nicht sinnvoll Unit-getestet werden (Next.js Request-Kontext),
// daher testen wir die Row-Level-Security-Logik direkt auf der DB.
describe("Upload RLS (DB-Ebene)", () => {
  it("findet Zugriff für berechtigten User", () => {
    const db = buildDb();
    seedData(db);
    const row = db.prepare(
      "SELECT 1 FROM akte_zugriff WHERE user_id = ? AND az = ?"
    ).get("user-1", "M/001/26");
    expect(row).not.toBeNull();
  });

  it("findet keinen Zugriff für fremden User", () => {
    const db = buildDb();
    seedData(db);
    const row = db.prepare(
      "SELECT 1 FROM akte_zugriff WHERE user_id = ? AND az = ?"
    ).get("user-2", "M/001/26");
    expect(row).toBeNull();
  });
});
```

- [ ] **Step 4.2: Tests zum Bestehen bringen**

```bash
npm test -- src/lib/__tests__/mandant-data.test.ts
```

Erwartetes Ergebnis: 14 passed (die 2 neuen RLS-Tests passen sofort, da sie DB-Logik testen).

- [ ] **Step 4.3: Upload-Route implementieren**

Erstelle `src/app/api/upload/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { getDb } from "@/lib/db";
import path from "path";
import fs from "fs";
import { v4 as uuid } from "uuid";

const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const UPLOAD_DIR = process.env.UPLOAD_DIR ?? "./data/uploads";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session || session.rolle !== "privatmandant") {
    return NextResponse.json({ error: "Nicht autorisiert" }, { status: 401 });
  }

  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json({ error: "Ungültiger Multipart-Request" }, { status: 400 });
  }

  const az = (formData.get("az") as string | null)?.trim() ?? "";
  const file = formData.get("file") as File | null;

  if (!az || !file) {
    return NextResponse.json({ error: "az und file sind erforderlich" }, { status: 422 });
  }

  const db = getDb();
  const access = (db as any).prepare(
    "SELECT 1 FROM akte_zugriff WHERE user_id = ? AND az = ?"
  ).get(session.userId, az);
  if (!access) {
    return NextResponse.json({ error: "Kein Zugriff auf diese Akte" }, { status: 403 });
  }

  if (file.size > MAX_SIZE_BYTES) {
    return NextResponse.json({ error: "Datei zu groß (max. 10 MB)" }, { status: 413 });
  }

  const ext = path.extname(file.name).toLowerCase();
  if (ext !== ".pdf") {
    return NextResponse.json({ error: "Nur PDF-Dateien erlaubt" }, { status: 422 });
  }

  const fileId = uuid();
  const sanitizedName = file.name.replace(/[^a-zA-Z0-9.\-_]/g, "_");
  const storedFilename = `${fileId}_${sanitizedName}`;
  const targetDir = path.join(UPLOAD_DIR, az.replace(/[/\\]/g, "_"));
  const targetPath = path.join(targetDir, storedFilename);

  fs.mkdirSync(targetDir, { recursive: true });
  const buffer = Buffer.from(await file.arrayBuffer());
  fs.writeFileSync(targetPath, buffer);

  (db as any).prepare(`
    INSERT INTO dokumente (id, az, typ, dateiname, encrypted_path)
    VALUES (?, ?, 'mandant_eingang', ?, ?)
  `).run(fileId, az, file.name, targetPath);

  return NextResponse.json({ id: fileId, dateiname: file.name }, { status: 201 });
}
```

- [ ] **Step 4.4: Build-Check**

```bash
npx tsc --noEmit 2>&1 | head -20
```

Erwartetes Ergebnis: Keine Fehler.

- [ ] **Step 4.5: Alle Tests**

```bash
npm test
```

Erwartetes Ergebnis: Alle Tests grün.

- [ ] **Step 4.6: Commit**

```bash
git add src/app/api/upload/route.ts
git commit -m "feat: B3 Upload-API POST /api/upload – Mandant-only, RLS, PDF-Validierung"
```

---

## Task 5: Abschluss-Summary (Druckseite)

**Files:**
- Create: `src/app/(authed)/mandant/[az]/summary/page.tsx`

Die Seite ist eine druckoptimierte Server Component. Ein `<PrintButton>` Client Component löst `window.print()` aus. `@media print` versteckt den Button und setzt weiße Hintergründe. Der Link erscheint auf der Detailseite nur wenn `status === "abgeschlossen"`.

- [ ] **Step 5.1: `summary/page.tsx` erstellen**

```tsx
// src/app/(authed)/mandant/[az]/summary/page.tsx
import { notFound, redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { getMandantAkteDetail } from "@/lib/mandant-data";
import { getDb } from "@/lib/db";
import { AMPEL_LAIENTEXTE, SCHADEN_LABELS, type AmpelStatus } from "@/types";
import PrintButton from "@/components/PrintButton";

export default async function MandantSummaryPage({
  params,
}: {
  params: Promise<{ az: string }>;
}) {
  const session = await getSession();
  if (!session || session.rolle !== "privatmandant") redirect("/login");

  const { az: rawAz } = await params;
  const az = decodeURIComponent(rawAz);
  const detail = getMandantAkteDetail(session.userId, az, getDb());
  if (!detail) notFound();

  const schadenEintraege = Object.entries(detail.schaden).filter(([, v]) => v > 0);

  return (
    <>
      <style>{`
        @media print {
          .no-print { display: none !important; }
          body { background: white !important; color: black !important; font-family: serif; }
          main { max-width: 100% !important; padding: 0 !important; }
        }
        main { max-width: 680px; margin: 40px auto; padding: 0 24px; font-family: var(--font-sans, system-ui); }
        h1  { font-size: 1.35rem; margin: 0 0 4px; }
        h2  { font-size: 0.95rem; margin: 28px 0 10px; font-weight: 600; }
        .subtitle { color: var(--text-subtle, #777); font-size: 0.875rem; margin: 0 0 28px; }
        table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
        th, td { padding: 7px 10px; text-align: left; }
        thead th { border-bottom: 2px solid var(--border, #ddd); color: var(--text-subtle, #777); font-weight: 600; }
        tbody tr { border-bottom: 1px solid var(--border, #eee); }
        tfoot td { border-top: 2px solid var(--border, #ddd); font-weight: 700; padding-top: 10px; }
        .right { text-align: right; }
        .accent { color: var(--accent, #1a7a6a); }
        .footer { margin-top: 48px; padding-top: 12px; border-top: 1px solid var(--border, #ddd); font-size: 0.75rem; color: var(--text-subtle, #999); }
      `}</style>

      <main>
        <div className="no-print" style={{ marginBottom: 24 }}>
          <PrintButton label="Drucken / Als PDF speichern" />
          <a
            href={`/mandant/${encodeURIComponent(az)}`}
            style={{ marginLeft: 16, fontSize: "0.875rem", color: "var(--accent)" }}
          >
            ← Zurück
          </a>
        </div>

        <h1>Regulierungsübersicht</h1>
        <p className="subtitle">
          Unfall vom{" "}
          {detail.unfalldatum
            ? new Date(detail.unfalldatum).toLocaleDateString("de-DE")
            : "–"}
          {detail.kennzeichen && ` · Fahrzeug: ${detail.kennzeichen}`}
          {detail.haftungsquote !== null && ` · Haftungsquote: ${detail.haftungsquote} %`}
          {detail.sachbearbeiter && ` · Sachbearbeiterin: ${detail.sachbearbeiter}`}
        </p>

        <h2>Schadenspositionen</h2>
        <table>
          <thead>
            <tr>
              <th>Position</th>
              <th className="right">Betrag (€)</th>
            </tr>
          </thead>
          <tbody>
            {schadenEintraege.map(([k, v]) => (
              <tr key={k}>
                <td>{SCHADEN_LABELS[k] ?? k}</td>
                <td className="right">
                  {v.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Gesamtforderung</td>
              <td className="right">
                {detail.gesamt_brutto.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
              </td>
            </tr>
            <tr>
              <td className="accent">Reguliert</td>
              <td className="right accent">
                {detail.gesamt_reguliert.toLocaleString("de-DE", { minimumFractionDigits: 2 })}
              </td>
            </tr>
          </tfoot>
        </table>

        {detail.history.length > 0 && (
          <>
            <h2>Fallverlauf</h2>
            <table>
              <thead>
                <tr>
                  <th>Datum</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {detail.history.map((h, i) => (
                  <tr key={i}>
                    <td>{new Date(h.timestamp).toLocaleDateString("de-DE")}</td>
                    <td>
                      {AMPEL_LAIENTEXTE[h.ampel_status as AmpelStatus]?.kurz ?? h.ampel_status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        <p className="footer">
          Erstellt am {new Date().toLocaleDateString("de-DE")} ·
          Kanzlei Koch &amp; Schatz GbR · Diese Übersicht dient als informelle Zusammenfassung
          und ersetzt keine rechtlich verbindlichen Schriftsätze.
        </p>
      </main>
    </>
  );
}
```

- [ ] **Step 5.2: Build-Check**

```bash
npx tsc --noEmit 2>&1 | head -20
```

Erwartetes Ergebnis: Keine Fehler.

- [ ] **Step 5.3: Alle Tests**

```bash
npm test
```

Erwartetes Ergebnis: Alle Tests weiterhin grün.

- [ ] **Step 5.4: Commit**

```bash
git add src/app/\(authed\)/mandant/\[az\]/summary/page.tsx
git commit -m "feat: B3 Abschluss-Summary – druckbare Regulierungsübersicht mit @media print"
```

---

## Task 6: Merge + Abschluss

**Files:**
- (keine Code-Änderungen)

- [ ] **Step 6.1: Alle Tests finaler Durchlauf**

```bash
npm test
```

Erwartetes Ergebnis: Alle Tests grün (session: 3, sv-data: 20, mandant-data: 14 = 37 total).

- [ ] **Step 6.2: TypeScript finaler Check**

```bash
npx tsc --noEmit
```

Erwartetes Ergebnis: Keine Fehler.

- [ ] **Step 6.3: Merge in master**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal"
git merge --no-ff feature/portal-b3 -m "feat: PORTAL-B3 Privatmandanten-Dashboard – Merge feature/portal-b3

Laienverständliche Fallübersicht für Privatmandanten:
- mandant/page.tsx: Redirect zu Einzelakte oder Link-Liste (Mehrfachfälle)
- mandant/[az]/page.tsx: Timeline, Schaden-Kacheln, Dokumente, Upload
- mandant/[az]/summary/page.tsx: Druckbare Abschluss-Zusammenfassung
- api/upload: POST PDF-Upload (mandant only, RLS, 10 MB, PDF-Only)
- AMPEL_LAIENTEXTE + SCHADEN_LABELS in types/index.ts
- mandant-data.ts Daten-Layer mit 14 Vitest-Tests"
```

- [ ] **Step 6.4: Worktree aufräumen**

```bash
git worktree remove .worktrees/portal-b3
```

---

## Subsystem-Übersicht (Gesamtportfolio)

| Plan     | Scope                                                                                  | Status       |
|----------|----------------------------------------------------------------------------------------|--------------|
| Portal-A1 | Unfallakten-Sync (flask sync-portal CLI)                                              | ✅ Abgeschlossen |
| Portal-A2 | gutachten_nr aus Gutachten-Parse → beteiligte → Sync-Payload                         | ✅ Abgeschlossen |
| Portal-B1 | Foundation (Scaffold, DB, Auth, Sync, Admin)                                          | ✅ Abgeschlossen |
| Portal-B2 | Sachverständigen-Cockpit (Dashboard, KPIs, Charts, Detail, Status-Timeline)           | ✅ Abgeschlossen |
| Portal-B3 | **Privatmandanten-Dashboard** (dieser Plan)                                           | Geplant      |
| Portal-B4 | E-Mail-Benachrichtigungen, PWA (Service Worker, Manifest), Rechtliches                | Folgeplan    |
