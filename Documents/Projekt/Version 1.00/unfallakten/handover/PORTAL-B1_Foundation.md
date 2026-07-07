# Portal-B1: Stakeholder Portal – Foundation Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrapt das neue Next.js 15 Stakeholder-Portal mit SQLCipher-Datenbank, Magic-Link-Auth (passwordless), HttpOnly-Session-Cookies, Sync-Empfangs-Endpunkt (von Unfallakten-System), und Kanzlei-Admin-Panel (User-Verwaltung, Akten-Übersicht, Status-Pflege).

**Architecture:** Next.js 15 App Router (TypeScript). SQLCipher via `@journeyapps/sqlcipher` (AES-256 DB). Magic Link: UUID-Token in DB, Nodemailer/Strato SMTP, HttpOnly-Session-Cookie (30 Min). Sync-Empfang: `POST /api/sync/push` mit API-Key + HMAC-SHA256. Admin-Panel: Server Components + Server Actions. Kein externer Auth-Provider.

**Tech Stack:** Next.js 15, TypeScript, `@journeyapps/sqlcipher` (Fallback: `better-sqlite3` + LUKS), Nodemailer, Tailwind CSS v4, shadcn/ui, uuid, Docker + Nginx (Let's Encrypt)

**Projekt-Verzeichnis:** `C:\Users\HAL9000\Documents\Projekt\Version 1.00\stakeholder-portal\`

**Domain:** `portal.anwalt-offenbach.de`

---

## Wichtiger Hinweis: SQLCipher-Kompilierung

`@journeyapps/sqlcipher` benötigt native Node.js-Binaries. In Docker kann die Kompilierung fehlschlagen.

**Empfohlenes Vorgehen:**
1. Direkt nach Projekt-Scaffold `@journeyapps/sqlcipher` in Docker testen (Task 1.6).
2. Falls Kompilierung fehlschlägt: Fallback auf `better-sqlite3` + LUKS Full-Disk-Encryption (Strato VPS). Das ist gleichwertig für DSGVO (AES-256 at rest), einfacher in der Wartung.
3. Entscheidung dokumentieren in `.env.local` Kommentar.

---

## Subsystem-Übersicht (Folge-Pläne)

Dieser Plan (Portal-B1) deckt nur die Foundation ab. Folge-Pläne:
- **Portal-B2:** Sachverständigen-Cockpit (Dashboard, Ampel-Tabelle, Rechnungsstatus, Dokument-Download)
- **Portal-B3:** Mandanten-Dashboard (Timeline, Laien-Sprache, Abschluss-Summary PDF)
- **Portal-B4:** E-Mail-Benachrichtigungen, PWA (Service Worker, Manifest), Rechtliches (Impressum, DSGVO)

---

## File Structure

```
stakeholder-portal/
├── src/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx                  # Root Layout, Kanzlei-Branding
│   │   ├── page.tsx                    # Redirect → /login oder /dashboard
│   │   ├── login/
│   │   │   ├── page.tsx                # Magic-Link-Anfrage-Formular
│   │   │   └── sent/page.tsx           # "Bitte prüfen Sie Ihre E-Mails"
│   │   ├── auth/
│   │   │   └── verify/route.ts         # GET: Token validieren → Session → Redirect
│   │   ├── (authed)/
│   │   │   ├── layout.tsx              # Auth-Guard (Session prüfen)
│   │   │   ├── dashboard/page.tsx      # Rollen-basierter Redirect
│   │   │   ├── admin/
│   │   │   │   ├── layout.tsx          # Admin-only Guard
│   │   │   │   ├── page.tsx            # Admin-Übersicht
│   │   │   │   ├── users/
│   │   │   │   │   └── page.tsx        # User-Verwaltung (Server Component)
│   │   │   │   └── akten/
│   │   │   │       └── page.tsx        # Akten-Übersicht + Status-Verwaltung
│   │   │   ├── sv/
│   │   │   │   └── page.tsx            # SV-Cockpit (Portal-B2)
│   │   │   └── mandant/
│   │   │       └── page.tsx            # PM-Dashboard (Portal-B3)
│   │   └── api/
│   │       ├── auth/
│   │       │   ├── login/route.ts      # POST: Token erzeugen + E-Mail senden
│   │       │   └── logout/route.ts     # POST: Session löschen
│   │       ├── me/route.ts             # GET: Aktueller User
│   │       ├── admin/
│   │       │   ├── users/route.ts      # GET/POST/PATCH
│   │       │   └── akten/route.ts      # GET/POST/PATCH (Status)
│   │       └── sync/
│   │           └── push/route.ts       # POST: Empfang Push-Sync vom Unfallakten-System
│   ├── lib/
│   │   ├── db.ts                       # SQLCipher-Verbindung + Schema-Init
│   │   ├── auth.ts                     # Magic-Link: Token erzeugen/validieren
│   │   ├── email.ts                    # Nodemailer + Strato SMTP
│   │   └── session.ts                  # Session-Cookie lesen/schreiben/löschen
│   ├── types/
│   │   └── index.ts                    # Gemeinsame TypeScript-Typen
│   └── components/
│       ├── MagicLinkForm.tsx           # Login-Formular (Client Component)
│       ├── AmpelBadge.tsx              # Status-Ampel (Farbe + Label)
│       └── AdminNav.tsx                # Admin-Navigation
├── data/                               # SQLite/SQLCipher DB (gitignored)
├── uploads/                            # Verschlüsselte Dokumente (gitignored)
├── .env.local                          # Secrets (gitignored)
├── .env.example                        # Template
├── docker-compose.yml
├── Dockerfile
├── nginx.conf
├── next.config.ts
└── package.json
```

---

## Task 1: Projekt-Scaffold + Docker

**Files:**
- Create: `stakeholder-portal/` (neues Verzeichnis)
- Create: `Dockerfile`, `docker-compose.yml`, `nginx.conf`
- Create: `.env.example`

- [ ] **Step 1.1: Next.js 15 Projekt anlegen**

```bash
cd "C:\Users\HAL9000\Documents\Projekt\Version 1.00"
npx create-next-app@latest stakeholder-portal \
  --typescript \
  --tailwind \
  --app \
  --src-dir \
  --no-eslint \
  --import-alias "@/*"
cd stakeholder-portal
```

- [ ] **Step 1.2: Abhängigkeiten installieren**

```bash
npm install @journeyapps/sqlcipher uuid nodemailer
npm install --save-dev @types/uuid @types/nodemailer
npm install lucide-react class-variance-authority clsx tailwind-merge
```

shadcn/ui initialisieren:
```bash
npx shadcn@latest init
# Optionen: Default style, Default base color, src/app/globals.css, yes CSS variables
```

shadcn-Komponenten:
```bash
npx shadcn@latest add button input label badge card table
```

- [ ] **Step 1.3: `.env.example` erstellen**

```bash
# Datenbank
DB_PATH=./data/portal.db
DB_ENCRYPTION_KEY=your-32-char-minimum-encryption-key

# Session
SESSION_SECRET=your-64-char-minimum-session-secret

# Strato SMTP
SMTP_HOST=smtp.strato.de
SMTP_PORT=465
SMTP_USER=portal@anwalt-offenbach.de
SMTP_PASS=your-strato-email-password
SMTP_FROM="Kanzlei Koch Schatz & Kollegen <portal@anwalt-offenbach.de>"

# Portal-URL (für Magic Link)
NEXT_PUBLIC_APP_URL=https://portal.anwalt-offenbach.de

# Sync (Authentifizierung des Push-Sync von Unfallakten-System)
SYNC_API_KEY=your-sync-api-key
SYNC_HMAC_SECRET=your-sync-hmac-secret

# Kanzlei-Branding
NEXT_PUBLIC_KANZLEI_NAME="Koch, Schatz & Kollegen"
NEXT_PUBLIC_KANZLEI_URL=https://www.anwalt-offenbach.de
```

Datei als `.env.local` kopieren und ausfüllen.

- [ ] **Step 1.4: `Dockerfile` erstellen**

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN apk add --no-cache python3 make g++ openssl-dev
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN apk add --no-cache openssl
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
RUN mkdir -p /app/data /app/uploads && chown nextjs:nodejs /app/data /app/uploads
USER nextjs
EXPOSE 3000
ENV PORT 3000
CMD ["node", "server.js"]
```

- [ ] **Step 1.5: `docker-compose.yml` erstellen**

```yaml
version: "3.9"
services:
  portal:
    build: .
    restart: unless-stopped
    env_file: .env.local
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
    expose:
      - "3000"
    networks:
      - portal-net

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    depends_on:
      - portal
    networks:
      - portal-net

networks:
  portal-net:
```

- [ ] **Step 1.6: SQLCipher-Kompilierung in Docker testen**

```bash
docker build -t portal-test .
docker run --rm portal-test node -e "require('@journeyapps/sqlcipher')" && echo "SQLCipher OK"
```
Erwartetes Ergebnis: `SQLCipher OK`

Falls FAIL: Fallback auf `better-sqlite3`:
```bash
npm uninstall @journeyapps/sqlcipher
npm install better-sqlite3
npm install --save-dev @types/better-sqlite3
```
Und in `src/lib/db.ts` (Task 2) `@journeyapps/sqlcipher` durch `better-sqlite3` ersetzen (ohne `key`-Option).

- [ ] **Step 1.7: Commit**

```bash
git init
git add .
git commit -m "feat: Next.js 15 Projekt-Scaffold + Docker + .env.example"
```

---

## Task 2: Datenbank-Schema (`src/lib/db.ts`)

**Files:**
- Create: `src/lib/db.ts`
- Create: `src/types/index.ts`

- [ ] **Step 2.1: `src/types/index.ts` erstellen**

```typescript
export type UserRole = "kanzlei_admin" | "sachverstaendiger" | "privatmandant";

export type AktenStatus =
  | "offen"
  | "in_regulierung"
  | "klage"
  | "abgeschlossen";

export type AmpelStatus =
  | "akte_eroeffnet"
  | "gutachten_beauftragt"
  | "regulierung_laeuft"
  | "teilreguliert"
  | "vollreguliert"
  | "klage_eingereicht";

export type AmpelFarbe = "grau" | "gelb" | "orange" | "gruen" | "rot";

export interface PortalUser {
  id: string;
  email: string;
  name: string;
  rolle: UserRole;
  aktiv: 0 | 1;
  erstellt_am: string;
}

export interface SessionData {
  userId: string;
  rolle: UserRole;
  email: string;
  name: string;
}

export interface PortalAkte {
  az: string;
  status: AktenStatus;
  ampel_status: AmpelStatus;
  ampel_farbe: AmpelFarbe;
  sync_version: number;
  letzter_sync: string | null;
}

export interface MagicToken {
  id: string;
  user_id: string;
  token: string;
  expires_at: string;
  used: 0 | 1;
}
```

- [ ] **Step 2.2: `src/lib/db.ts` erstellen**

```typescript
import Database from "@journeyapps/sqlcipher";
// Falls SQLCipher-Fallback: import Database from "better-sqlite3";
import path from "path";
import fs from "fs";

const DB_PATH = process.env.DB_PATH ?? "./data/portal.db";
const DB_KEY  = process.env.DB_ENCRYPTION_KEY ?? "";

let _db: ReturnType<typeof Database> | null = null;

export function getDb() {
  if (_db) return _db;

  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  _db = new Database(DB_PATH);

  // SQLCipher: Verschlüsselung aktivieren
  if (DB_KEY) {
    _db.pragma(`key = '${DB_KEY}'`);
  }

  _db.pragma("journal_mode = WAL");
  _db.pragma("foreign_keys = ON");

  initSchema(_db);
  return _db;
}

function initSchema(db: ReturnType<typeof Database>) {
  db.exec(`
    -- ============================================================
    -- USERS
    -- ============================================================
    CREATE TABLE IF NOT EXISTS portal_users (
      id          TEXT PRIMARY KEY,
      email       TEXT NOT NULL UNIQUE,
      name        TEXT NOT NULL,
      rolle       TEXT NOT NULL CHECK(rolle IN ('kanzlei_admin','sachverstaendiger','privatmandant')),
      aktiv       INTEGER NOT NULL DEFAULT 1,
      erstellt_am TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- ============================================================
    -- MAGIC LINK TOKENS
    -- ============================================================
    CREATE TABLE IF NOT EXISTS magic_tokens (
      id         TEXT PRIMARY KEY,
      user_id    TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      token      TEXT NOT NULL UNIQUE,
      expires_at TEXT NOT NULL,
      used       INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX IF NOT EXISTS idx_magic_tokens_token ON magic_tokens(token);

    -- ============================================================
    -- SESSIONS
    -- ============================================================
    CREATE TABLE IF NOT EXISTS portal_sessions (
      id          TEXT PRIMARY KEY,
      user_id     TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      created_at  TEXT NOT NULL DEFAULT (datetime('now')),
      last_active TEXT NOT NULL DEFAULT (datetime('now')),
      expires_at  TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_user ON portal_sessions(user_id);

    -- ============================================================
    -- AKTEN (Portal-Spiegel)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS akten (
      az            TEXT PRIMARY KEY,
      status        TEXT NOT NULL DEFAULT 'offen',
      ampel_status  TEXT NOT NULL DEFAULT 'akte_eroeffnet',
      ampel_farbe   TEXT NOT NULL DEFAULT 'grau',
      sync_version  INTEGER NOT NULL DEFAULT 0,
      letzter_sync  TEXT
    );

    -- ============================================================
    -- AKTE-ZUGRIFF (Row-Level Security)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS akte_zugriff (
      user_id TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      az      TEXT NOT NULL REFERENCES akten(az) ON DELETE CASCADE,
      PRIMARY KEY (user_id, az)
    );

    -- ============================================================
    -- BETEILIGTE (Portal-Spiegel, kein IBAN)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS beteiligte (
      id     TEXT PRIMARY KEY,
      az     TEXT NOT NULL REFERENCES akten(az) ON DELETE CASCADE,
      rolle  TEXT NOT NULL,
      name   TEXT,
      firma  TEXT,
      email  TEXT
    );

    -- ============================================================
    -- SCHADEN (Positionen als JSON)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS schaden_snapshot (
      az              TEXT PRIMARY KEY REFERENCES akten(az) ON DELETE CASCADE,
      positionen_json TEXT NOT NULL DEFAULT '{}',
      gesamt_brutto   REAL NOT NULL DEFAULT 0.0
    );

    -- ============================================================
    -- REGULIERUNG (aggregiert als JSON)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS regulierung_snapshot (
      az              TEXT PRIMARY KEY REFERENCES akten(az) ON DELETE CASCADE,
      positionen_json TEXT NOT NULL DEFAULT '{}',
      gesamt_reguliert REAL NOT NULL DEFAULT 0.0
    );

    -- ============================================================
    -- DOKUMENTE (Metadaten, verschlüsselte Dateien auf Disk)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS dokumente (
      id             TEXT PRIMARY KEY,
      az             TEXT NOT NULL REFERENCES akten(az) ON DELETE CASCADE,
      typ            TEXT NOT NULL,
      dateiname      TEXT NOT NULL,
      encrypted_path TEXT,
      erstellt_am    TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- ============================================================
    -- NACHRICHTEN (Portal-intern)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS nachrichten (
      id         TEXT PRIMARY KEY,
      az         TEXT NOT NULL REFERENCES akten(az) ON DELETE CASCADE,
      sender_id  TEXT NOT NULL REFERENCES portal_users(id),
      inhalt     TEXT NOT NULL,
      erstellt_am TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- ============================================================
    -- BENACHRICHTIGUNGEN
    -- ============================================================
    CREATE TABLE IF NOT EXISTS benachrichtigungen (
      id           TEXT PRIMARY KEY,
      user_id      TEXT NOT NULL REFERENCES portal_users(id) ON DELETE CASCADE,
      az           TEXT REFERENCES akten(az) ON DELETE SET NULL,
      typ          TEXT NOT NULL,
      titel        TEXT NOT NULL,
      gelesen      INTEGER NOT NULL DEFAULT 0,
      email_gesendet INTEGER NOT NULL DEFAULT 0,
      erstellt_am  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- ============================================================
    -- SYNC LOG (Debugging)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS sync_log (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      az           TEXT,
      sync_version INTEGER,
      status       TEXT,
      fehler       TEXT,
      empfangen_am TEXT NOT NULL DEFAULT (datetime('now'))
    );

    -- ============================================================
    -- RATE LIMITING (Magic Link)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS rate_limit (
      email      TEXT NOT NULL,
      fenster    TEXT NOT NULL,   -- 'hour' oder 'day'
      count      INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (email, fenster)
    );
  `);
}
```

- [ ] **Step 2.3: Commit**

```bash
git add src/lib/db.ts src/types/index.ts
git commit -m "feat(db): SQLCipher-Schema mit allen Portal-Tabellen"
```

---

## Task 3: E-Mail-Service (`src/lib/email.ts`)

**Files:**
- Create: `src/lib/email.ts`

- [ ] **Step 3.1: `src/lib/email.ts` erstellen**

```typescript
import nodemailer from "nodemailer";

const transporter = nodemailer.createTransport({
  host: process.env.SMTP_HOST ?? "smtp.strato.de",
  port: Number(process.env.SMTP_PORT ?? 465),
  secure: true,
  auth: {
    user: process.env.SMTP_USER,
    pass: process.env.SMTP_PASS,
  },
});

export async function sendMagicLink(email: string, token: string): Promise<void> {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "https://portal.anwalt-offenbach.de";
  const link = `${appUrl}/auth/verify?token=${token}`;
  const kanzlei = process.env.NEXT_PUBLIC_KANZLEI_NAME ?? "Kanzlei Koch, Schatz & Kollegen";

  await transporter.sendMail({
    from: process.env.SMTP_FROM,
    to: email,
    subject: `Ihr Zugang zum Portal – ${kanzlei}`,
    text: [
      `Guten Tag,`,
      ``,
      `Sie haben einen Zugangslink zum Mandanten-/Sachverständigenportal der ${kanzlei} angefordert.`,
      ``,
      `Klicken Sie hier, um sich anzumelden:`,
      link,
      ``,
      `Dieser Link ist 24 Stunden gültig und kann nur einmal verwendet werden.`,
      `Wenn Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.`,
      ``,
      `Mit freundlichen Grüßen`,
      kanzlei,
    ].join("\n"),
    html: `
      <p>Guten Tag,</p>
      <p>Sie haben einen Zugangslink zum Portal der <strong>${kanzlei}</strong> angefordert.</p>
      <p>
        <a href="${link}" style="display:inline-block;padding:12px 24px;background:#1d4ed8;
          color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">
          Jetzt anmelden
        </a>
      </p>
      <p style="color:#6b7280;font-size:0.875rem;">
        Dieser Link ist 24 Stunden gültig und kann nur einmal verwendet werden.<br>
        Falls Sie diesen Link nicht angefordert haben, ignorieren Sie diese E-Mail.
      </p>
      <p>Mit freundlichen Grüßen<br>${kanzlei}</p>
    `,
  });
}

export async function sendStatusNotification(
  email: string,
  name: string,
  az: string
): Promise<void> {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "https://portal.anwalt-offenbach.de";
  const kanzlei = process.env.NEXT_PUBLIC_KANZLEI_NAME ?? "Kanzlei Koch, Schatz & Kollegen";

  await transporter.sendMail({
    from: process.env.SMTP_FROM,
    to: email,
    subject: `Aktualisierung in Ihrer Akte – ${kanzlei}`,
    text: [
      `Guten Tag ${name},`,
      ``,
      `Es gibt eine Aktualisierung in Ihrer Akte (${az}).`,
      `Melden Sie sich im Portal an, um den aktuellen Stand zu sehen:`,
      `${appUrl}`,
      ``,
      `Mit freundlichen Grüßen`,
      kanzlei,
    ].join("\n"),
  });
}
```

- [ ] **Step 3.2: Commit**

```bash
git add src/lib/email.ts
git commit -m "feat(email): Nodemailer Magic-Link und Status-Notification"
```

---

## Task 4: Magic-Link-Auth (`src/lib/auth.ts` + API-Routes)

**Files:**
- Create: `src/lib/auth.ts`
- Create: `src/app/api/auth/login/route.ts`
- Create: `src/app/auth/verify/route.ts`

- [ ] **Step 4.1: `src/lib/auth.ts` erstellen**

```typescript
import { v4 as uuidv4 } from "uuid";
import { getDb } from "./db";
import type { PortalUser } from "@/types";

const TOKEN_EXPIRY_HOURS = 24;
const RATE_LIMIT_PER_HOUR = 3;
const RATE_LIMIT_PER_DAY = 10;

export function createMagicToken(userId: string): string {
  const db = getDb();
  const token = uuidv4();
  const expiresAt = new Date(
    Date.now() + TOKEN_EXPIRY_HOURS * 60 * 60 * 1000
  ).toISOString();

  db.prepare(`
    INSERT INTO magic_tokens (id, user_id, token, expires_at)
    VALUES (?, ?, ?, ?)
  `).run(uuidv4(), userId, token, expiresAt);

  return token;
}

export function verifyMagicToken(token: string): PortalUser | null {
  const db = getDb();
  const now = new Date().toISOString();

  const row = db.prepare(`
    SELECT mt.id AS token_id, mt.user_id, mt.expires_at, mt.used,
           u.id, u.email, u.name, u.rolle, u.aktiv
    FROM magic_tokens mt
    JOIN portal_users u ON u.id = mt.user_id
    WHERE mt.token = ? AND mt.used = 0 AND mt.expires_at > ?
  `).get(token, now) as (PortalUser & { token_id: string; used: number }) | undefined;

  if (!row || !row.aktiv) return null;

  db.prepare("UPDATE magic_tokens SET used = 1 WHERE id = ?").run(row.token_id);

  return {
    id: row.id,
    email: row.email,
    name: row.name,
    rolle: row.rolle,
    aktiv: row.aktiv,
    erstellt_am: "",
  };
}

export function isRateLimited(email: string): boolean {
  const db = getDb();
  const now = new Date();
  const hourKey = `${now.toISOString().slice(0, 13)}`;
  const dayKey  = `${now.toISOString().slice(0, 10)}`;

  const hour = db.prepare(
    "SELECT count FROM rate_limit WHERE email = ? AND fenster = ?"
  ).get(email, hourKey) as { count: number } | undefined;

  const day = db.prepare(
    "SELECT count FROM rate_limit WHERE email = ? AND fenster = ?"
  ).get(email, dayKey) as { count: number } | undefined;

  if ((hour?.count ?? 0) >= RATE_LIMIT_PER_HOUR) return true;
  if ((day?.count ?? 0) >= RATE_LIMIT_PER_DAY) return true;

  db.prepare(`
    INSERT INTO rate_limit (email, fenster, count) VALUES (?, ?, 1)
    ON CONFLICT(email, fenster) DO UPDATE SET count = count + 1
  `).run(email, hourKey);

  db.prepare(`
    INSERT INTO rate_limit (email, fenster, count) VALUES (?, ?, 1)
    ON CONFLICT(email, fenster) DO UPDATE SET count = count + 1
  `).run(email, dayKey);

  return false;
}

export function findUserByEmail(email: string): PortalUser | null {
  const db = getDb();
  return db.prepare(
    "SELECT * FROM portal_users WHERE email = ? AND aktiv = 1"
  ).get(email.toLowerCase().trim()) as PortalUser | null;
}
```

- [ ] **Step 4.2: `src/app/api/auth/login/route.ts` erstellen**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { findUserByEmail, createMagicToken, isRateLimited } from "@/lib/auth";
import { sendMagicLink } from "@/lib/email";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const email = (body.email ?? "").toString().toLowerCase().trim();

  if (!email || !email.includes("@")) {
    return NextResponse.json({ error: "Ungültige E-Mail-Adresse" }, { status: 400 });
  }

  if (isRateLimited(email)) {
    return NextResponse.json(
      { error: "Zu viele Anfragen. Bitte warten Sie." }, { status: 429 }
    );
  }

  const user = findUserByEmail(email);

  if (user) {
    const token = createMagicToken(user.id);
    try {
      await sendMagicLink(email, token);
    } catch (err) {
      console.error("E-Mail-Versand fehlgeschlagen:", err);
      // Kein Fehler zurückgeben – Sicherheit: E-Mail-Enumeration verhindern
    }
  }

  // Immer gleiche Antwort – verhindert User-Enumeration
  return NextResponse.json({ status: "sent" });
}
```

- [ ] **Step 4.3: `src/app/auth/verify/route.ts` erstellen**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { verifyMagicToken } from "@/lib/auth";
import { createSession } from "@/lib/session";

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get("token") ?? "";

  const user = verifyMagicToken(token);
  if (!user) {
    return NextResponse.redirect(new URL("/login?error=invalid_token", req.url));
  }

  const response = NextResponse.redirect(new URL("/dashboard", req.url));
  await createSession(user, response);
  return response;
}
```

- [ ] **Step 4.4: Commit**

```bash
git add src/lib/auth.ts src/app/api/auth/login/route.ts src/app/auth/verify/route.ts
git commit -m "feat(auth): Magic-Link Auth – Token erzeugen, E-Mail, Verify-Route, Rate-Limiting"
```

---

## Task 5: Session-Management (`src/lib/session.ts`)

**Files:**
- Create: `src/lib/session.ts`
- Create: `src/app/api/auth/logout/route.ts`
- Create: `src/app/api/me/route.ts`

- [ ] **Step 5.1: `src/lib/session.ts` erstellen**

```typescript
import { v4 as uuidv4 } from "uuid";
import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getDb } from "./db";
import type { PortalUser, SessionData } from "@/types";

const SESSION_COOKIE = "portal_session";
const SESSION_MAX_AGE_MINUTES = 30;

export async function createSession(
  user: PortalUser,
  response: NextResponse
): Promise<void> {
  const db = getDb();
  const sessionId = uuidv4();
  const expiresAt = new Date(
    Date.now() + SESSION_MAX_AGE_MINUTES * 60 * 1000
  ).toISOString();

  db.prepare(`
    INSERT INTO portal_sessions (id, user_id, expires_at)
    VALUES (?, ?, ?)
  `).run(sessionId, user.id, expiresAt);

  response.cookies.set(SESSION_COOKIE, sessionId, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: SESSION_MAX_AGE_MINUTES * 60,
    path: "/",
  });
}

export async function getSession(): Promise<SessionData | null> {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE)?.value;
  if (!sessionId) return null;

  const db = getDb();
  const now = new Date().toISOString();

  const row = db.prepare(`
    SELECT s.id AS session_id, u.id, u.email, u.name, u.rolle, u.aktiv
    FROM portal_sessions s
    JOIN portal_users u ON u.id = s.user_id
    WHERE s.id = ? AND s.expires_at > ?
  `).get(sessionId, now) as (SessionData & { session_id: string; aktiv: number }) | undefined;

  if (!row || !row.aktiv) return null;

  // Sliding expiry
  const newExpiry = new Date(Date.now() + SESSION_MAX_AGE_MINUTES * 60 * 1000).toISOString();
  db.prepare(
    "UPDATE portal_sessions SET last_active = datetime('now'), expires_at = ? WHERE id = ?"
  ).run(newExpiry, row.session_id);

  return {
    userId: row.id,
    rolle: row.rolle,
    email: row.email,
    name: row.name,
  };
}

export async function deleteSession(): Promise<void> {
  const cookieStore = await cookies();
  const sessionId = cookieStore.get(SESSION_COOKIE)?.value;
  if (!sessionId) return;

  const db = getDb();
  db.prepare("DELETE FROM portal_sessions WHERE id = ?").run(sessionId);
}
```

- [ ] **Step 5.2: `src/app/api/auth/logout/route.ts` erstellen**

```typescript
import { NextResponse } from "next/server";
import { deleteSession } from "@/lib/session";

export async function POST() {
  await deleteSession();
  const response = NextResponse.redirect(
    new URL("/login", process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000")
  );
  response.cookies.set("portal_session", "", { maxAge: 0, path: "/" });
  return response;
}
```

- [ ] **Step 5.3: `src/app/api/me/route.ts` erstellen**

```typescript
import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Nicht authentifiziert" }, { status: 401 });
  }
  return NextResponse.json({
    userId: session.userId,
    email: session.email,
    name: session.name,
    rolle: session.rolle,
  });
}
```

- [ ] **Step 5.4: Commit**

```bash
git add src/lib/session.ts src/app/api/auth/logout/route.ts src/app/api/me/route.ts
git commit -m "feat(session): HttpOnly Session-Cookie, Sliding Expiry, /api/me"
```

---

## Task 6: Auth-Guard-Layouts

**Files:**
- Create: `src/app/(authed)/layout.tsx`
- Create: `src/app/(authed)/admin/layout.tsx`
- Create: `src/app/(authed)/dashboard/page.tsx`
- Create: `src/app/page.tsx`

- [ ] **Step 6.1: Root-Redirect `src/app/page.tsx`**

```typescript
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

export default async function HomePage() {
  const session = await getSession();
  redirect(session ? "/dashboard" : "/login");
}
```

- [ ] **Step 6.2: Auth-Guard `src/app/(authed)/layout.tsx`**

```typescript
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

export default async function AuthedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (!session) redirect("/login?error=session_expired");
  return <>{children}</>;
}
```

- [ ] **Step 6.3: Admin-Guard `src/app/(authed)/admin/layout.tsx`**

```typescript
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  if (session?.rolle !== "kanzlei_admin") redirect("/dashboard");
  return <>{children}</>;
}
```

- [ ] **Step 6.4: Dashboard-Redirect `src/app/(authed)/dashboard/page.tsx`**

```typescript
import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";

export default async function DashboardPage() {
  const session = await getSession();
  if (!session) redirect("/login");

  switch (session.rolle) {
    case "kanzlei_admin":
      redirect("/admin");
    case "sachverstaendiger":
      redirect("/sv");
    case "privatmandant":
      redirect("/mandant");
    default:
      redirect("/login");
  }
}
```

- [ ] **Step 6.5: Commit**

```bash
git add src/app/page.tsx src/app/"(authed)"/layout.tsx
git add src/app/"(authed)"/admin/layout.tsx src/app/"(authed)"/dashboard/page.tsx
git commit -m "feat(auth): Auth-Guard Layouts + rollen-basierter Dashboard-Redirect"
```

---

## Task 7: Login-Page UI

**Files:**
- Create: `src/app/login/page.tsx`
- Create: `src/app/login/sent/page.tsx`
- Create: `src/components/MagicLinkForm.tsx`

- [ ] **Step 7.1: `src/components/MagicLinkForm.tsx` erstellen**

```typescript
"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

export function MagicLinkForm() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (res.status === 429) {
        setError("Zu viele Anfragen. Bitte warten Sie einige Minuten.");
        return;
      }
      router.push("/login/sent");
    } catch {
      setError("Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
          E-Mail-Adresse
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={loading}
          placeholder="ihre@email.de"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button
        type="submit"
        disabled={loading || !email}
        className="w-full py-2 px-4 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "Wird gesendet…" : "Zugangslink anfordern"}
      </button>
    </form>
  );
}
```

- [ ] **Step 7.2: `src/app/login/page.tsx` erstellen**

```typescript
import { MagicLinkForm } from "@/components/MagicLinkForm";

export default function LoginPage({
  searchParams,
}: {
  searchParams: { error?: string };
}) {
  const kanzlei = process.env.NEXT_PUBLIC_KANZLEI_NAME ?? "Koch, Schatz & Kollegen";

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-xl font-semibold text-gray-900">{kanzlei}</h1>
          <p className="text-sm text-gray-500 mt-1">Mandanten- & Sachverständigenportal</p>
        </div>

        <div className="bg-white shadow rounded-lg p-6 space-y-4">
          <h2 className="text-base font-medium text-gray-800">Anmelden</h2>
          <p className="text-sm text-gray-500">
            Geben Sie Ihre E-Mail-Adresse ein. Wir senden Ihnen einen Zugangslink – kein Passwort nötig.
          </p>
          {searchParams.error === "invalid_token" && (
            <p className="text-sm text-red-600 bg-red-50 p-2 rounded">
              Der Link ist abgelaufen oder wurde bereits verwendet.
            </p>
          )}
          {searchParams.error === "session_expired" && (
            <p className="text-sm text-amber-600 bg-amber-50 p-2 rounded">
              Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.
            </p>
          )}
          <MagicLinkForm />
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 7.3: `src/app/login/sent/page.tsx` erstellen**

```typescript
import Link from "next/link";

export default function LoginSentPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm text-center space-y-4">
        <div className="text-4xl">✉️</div>
        <h1 className="text-lg font-semibold text-gray-900">E-Mail wurde gesendet</h1>
        <p className="text-sm text-gray-600">
          Falls Ihre E-Mail-Adresse bei uns registriert ist, haben wir Ihnen soeben einen
          Zugangslink gesendet. Bitte prüfen Sie Ihren Posteingang.
        </p>
        <p className="text-xs text-gray-400">
          Der Link ist 24 Stunden gültig und kann nur einmal verwendet werden.
        </p>
        <Link href="/login" className="text-sm text-blue-600 hover:underline">
          Erneut anfordern
        </Link>
      </div>
    </main>
  );
}
```

- [ ] **Step 7.4: Visueller Test**

```bash
npm run dev
```
Browser öffnen → `http://localhost:3000` → Redirect zu `/login` → Formular sichtbar → E-Mail eingeben → `/login/sent` erscheint (auch wenn User nicht existiert – bewusste Sicherheitsentscheidung).

- [ ] **Step 7.5: Commit**

```bash
git add src/app/login/ src/components/MagicLinkForm.tsx
git commit -m "feat(ui): Login-Page mit Magic-Link-Formular und /sent-Seite"
```

---

## Task 8: Sync-Empfangs-Endpunkt

**Files:**
- Create: `src/app/api/sync/push/route.ts`
- Create: `src/lib/sync.ts`

- [ ] **Step 8.1: `src/lib/sync.ts` erstellen**

```typescript
import { createHmac } from "crypto";
import { getDb } from "./db";
import { v4 as uuidv4 } from "uuid";

export function verifyHmacSignature(body: string, signature: string): boolean {
  const secret = process.env.SYNC_HMAC_SECRET ?? "";
  const expected = createHmac("sha256", secret).update(body).digest("hex");
  return expected === signature;
}

interface SyncPayload {
  sync_version: number;
  akte: {
    az: string;
    status: string;
    unfalldatum?: string;
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

export function processSync(payload: SyncPayload): void {
  const db = getDb();
  const az = payload.akte.az;
  if (!az) throw new Error("az fehlt im Payload");

  const tx = db.transaction(() => {
    // Akte upserten
    db.prepare(`
      INSERT INTO akten (az, status, ampel_status, ampel_farbe, sync_version, letzter_sync)
      VALUES (?, ?, ?, ?, ?, datetime('now'))
      ON CONFLICT(az) DO UPDATE SET
        status = excluded.status,
        ampel_status = excluded.ampel_status,
        ampel_farbe = excluded.ampel_farbe,
        sync_version = excluded.sync_version,
        letzter_sync = excluded.letzter_sync
    `).run(
      az,
      payload.akte.status,
      payload.ampel.status,
      payload.ampel.farbe,
      payload.sync_version
    );

    // Beteiligte upserten (kein Mandantenname für SV sichtbar – gehandhabt in API)
    for (const b of payload.beteiligte ?? []) {
      const bId = String(b.id);
      db.prepare(`
        INSERT INTO beteiligte (id, az, rolle, name, firma, email)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          az = excluded.az, rolle = excluded.rolle,
          name = excluded.name, firma = excluded.firma, email = excluded.email
      `).run(bId, az, b.rolle, b.name ?? null, b.firma ?? null, b.email ?? null);
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

    // Sync-Log
    db.prepare(`
      INSERT INTO sync_log (az, sync_version, status)
      VALUES (?, ?, 'ok')
    `).run(az, payload.sync_version);
  });

  tx();
}
```

- [ ] **Step 8.2: `src/app/api/sync/push/route.ts` erstellen**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { verifyHmacSignature, processSync } from "@/lib/sync";
import { getDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  const apiKey = req.headers.get("X-Sync-API-Key") ?? "";
  const signature = req.headers.get("X-Sync-Signature") ?? "";

  if (apiKey !== (process.env.SYNC_API_KEY ?? "")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.text();

  if (!verifyHmacSignature(body, signature)) {
    return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
  }

  let payload: unknown;
  try {
    payload = JSON.parse(body);
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  if (typeof payload !== "object" || payload === null || !("akte" in payload)) {
    return NextResponse.json({ error: "Payload ungültig" }, { status: 400 });
  }

  // Idempotenz: bereits verarbeitete sync_version überspringen
  const db = getDb();
  const p = payload as { sync_version?: number; akte?: { az?: string } };
  if (p.sync_version && p.akte?.az) {
    const existing = db.prepare(
      "SELECT id FROM sync_log WHERE az = ? AND sync_version = ? AND status = 'ok'"
    ).get(p.akte.az, p.sync_version);
    if (existing) {
      return NextResponse.json({ status: "already_processed", sync_version: p.sync_version });
    }
  }

  try {
    processSync(payload as Parameters<typeof processSync>[0]);
  } catch (err) {
    console.error("Sync-Verarbeitung fehlgeschlagen:", err);
    return NextResponse.json({ error: "Verarbeitungsfehler" }, { status: 500 });
  }

  return NextResponse.json({ status: "processed", sync_version: p.sync_version });
}
```

- [ ] **Step 8.3: Manueller Test**

```bash
# SYNC_HMAC_SECRET in .env.local setzen, dann:
curl -X POST http://localhost:3000/api/sync/push \
  -H "X-Sync-API-Key: your-sync-api-key" \
  -H "X-Sync-Signature: $(echo -n '{"sync_version":1,...}' | openssl dgst -sha256 -hmac 'your-hmac-secret' | awk '{print $2}')" \
  -H "Content-Type: application/json" \
  -d '{"sync_version":1,"akte":{"az":"TEST/001","status":"offen"},"ampel":{"status":"akte_eroeffnet","farbe":"grau"}}'
# Erwartetes Ergebnis: {"status":"processed","sync_version":1}
```

- [ ] **Step 8.4: Commit**

```bash
git add src/lib/sync.ts src/app/api/sync/
git commit -m "feat(sync): POST /api/sync/push – HMAC-Verifikation, Upsert, Idempotenz"
```

---

## Task 9: Admin-Panel – User-Verwaltung

**Files:**
- Create: `src/app/api/admin/users/route.ts`
- Create: `src/app/(authed)/admin/users/page.tsx`
- Create: `src/app/(authed)/admin/page.tsx`

- [ ] **Step 9.1: `src/app/api/admin/users/route.ts` erstellen**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { getDb } from "@/lib/db";
import { v4 as uuidv4 } from "uuid";

async function requireAdmin() {
  const session = await getSession();
  if (session?.rolle !== "kanzlei_admin") return null;
  return session;
}

export async function GET() {
  if (!await requireAdmin()) return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const db = getDb();
  const users = db.prepare(
    "SELECT id, email, name, rolle, aktiv, erstellt_am FROM portal_users ORDER BY erstellt_am DESC"
  ).all();
  return NextResponse.json(users);
}

export async function POST(req: NextRequest) {
  if (!await requireAdmin()) return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const body = await req.json().catch(() => ({}));
  const { email, name, rolle } = body;
  if (!email || !name || !["sachverstaendiger", "privatmandant", "kanzlei_admin"].includes(rolle)) {
    return NextResponse.json({ error: "email, name und rolle erforderlich" }, { status: 400 });
  }
  const db = getDb();
  const id = uuidv4();
  try {
    db.prepare(
      "INSERT INTO portal_users (id, email, name, rolle) VALUES (?, ?, ?, ?)"
    ).run(id, email.toLowerCase().trim(), name.trim(), rolle);
  } catch {
    return NextResponse.json({ error: "E-Mail bereits vergeben" }, { status: 409 });
  }
  return NextResponse.json({ id, email, name, rolle, aktiv: 1 }, { status: 201 });
}

export async function PATCH(req: NextRequest) {
  if (!await requireAdmin()) return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const body = await req.json().catch(() => ({}));
  const { id, aktiv } = body;
  if (!id || typeof aktiv !== "boolean") {
    return NextResponse.json({ error: "id und aktiv erforderlich" }, { status: 400 });
  }
  const db = getDb();
  db.prepare("UPDATE portal_users SET aktiv = ? WHERE id = ?").run(aktiv ? 1 : 0, id);
  return NextResponse.json({ status: "ok" });
}
```

- [ ] **Step 9.2: `src/app/(authed)/admin/page.tsx` erstellen**

```typescript
import Link from "next/link";

export default function AdminPage() {
  return (
    <main className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-xl font-semibold">Admin-Bereich</h1>
      <div className="grid grid-cols-2 gap-4">
        <Link href="/admin/users"
          className="block p-4 bg-white border rounded-lg hover:shadow-sm">
          <h2 className="font-medium">Nutzer-Verwaltung</h2>
          <p className="text-sm text-gray-500 mt-1">Portal-User anlegen, aktivieren/deaktivieren</p>
        </Link>
        <Link href="/admin/akten"
          className="block p-4 bg-white border rounded-lg hover:shadow-sm">
          <h2 className="font-medium">Akten-Übersicht</h2>
          <p className="text-sm text-gray-500 mt-1">Sync-Status, Zugriffsvergabe, Status pflegen</p>
        </Link>
      </div>
    </main>
  );
}
```

- [ ] **Step 9.3: `src/app/(authed)/admin/users/page.tsx` erstellen**

```typescript
import { getDb } from "@/lib/db";
import type { PortalUser } from "@/types";

export default async function UsersPage() {
  const db = getDb();
  const users = db.prepare(
    "SELECT id, email, name, rolle, aktiv, erstellt_am FROM portal_users ORDER BY erstellt_am DESC"
  ).all() as PortalUser[];

  return (
    <main className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-semibold">Nutzer-Verwaltung</h1>
        <span className="text-sm text-gray-500">{users.length} Nutzer</span>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              {["Name", "E-Mail", "Rolle", "Status", "Erstellt"].map((h) => (
                <th key={h} className="px-4 py-2 font-medium text-gray-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-medium">{u.name}</td>
                <td className="px-4 py-2 text-gray-600">{u.email}</td>
                <td className="px-4 py-2">
                  <span className="inline-block px-2 py-0.5 rounded text-xs bg-blue-50 text-blue-700">
                    {u.rolle}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span className={`text-xs font-medium ${u.aktiv ? "text-green-600" : "text-gray-400"}`}>
                    {u.aktiv ? "Aktiv" : "Deaktiviert"}
                  </span>
                </td>
                <td className="px-4 py-2 text-gray-400 text-xs">
                  {new Date(u.erstellt_am).toLocaleDateString("de-DE")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && (
          <p className="text-center py-8 text-gray-400 text-sm">Noch keine Nutzer angelegt.</p>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 9.4: Commit**

```bash
git add src/app/api/admin/users/ src/app/"(authed)"/admin/
git commit -m "feat(admin): User-Verwaltung – GET/POST/PATCH /api/admin/users + Übersichts-Seite"
```

---

## Task 10: Admin-Panel – Akten-Übersicht + Zugriffsvergabe

**Files:**
- Create: `src/app/api/admin/akten/route.ts`
- Create: `src/app/(authed)/admin/akten/page.tsx`
- Create: `src/components/AmpelBadge.tsx`

- [ ] **Step 10.1: `src/components/AmpelBadge.tsx` erstellen**

```typescript
import type { AmpelFarbe, AmpelStatus } from "@/types";

const FARBE_KLASSE: Record<AmpelFarbe, string> = {
  grau:   "bg-gray-100 text-gray-600",
  gelb:   "bg-yellow-100 text-yellow-700",
  orange: "bg-orange-100 text-orange-700",
  gruen:  "bg-green-100 text-green-700",
  rot:    "bg-red-100 text-red-700",
};

const STATUS_LABEL: Record<AmpelStatus, string> = {
  akte_eroeffnet:       "Eröffnet",
  gutachten_beauftragt: "Gutachten",
  regulierung_laeuft:   "In Regulierung",
  teilreguliert:        "Teilreguliert",
  vollreguliert:        "Vollreguliert",
  klage_eingereicht:    "Klage",
};

export function AmpelBadge({
  status,
  farbe,
}: {
  status: AmpelStatus;
  farbe: AmpelFarbe;
}) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${FARBE_KLASSE[farbe] ?? FARBE_KLASSE.grau}`}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
```

- [ ] **Step 10.2: `src/app/api/admin/akten/route.ts` erstellen**

```typescript
import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { getDb } from "@/lib/db";

async function requireAdmin() {
  const session = await getSession();
  if (session?.rolle !== "kanzlei_admin") return null;
  return session;
}

export async function GET() {
  if (!await requireAdmin()) return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const db = getDb();
  const akten = db.prepare(
    "SELECT az, status, ampel_status, ampel_farbe, sync_version, letzter_sync FROM akten ORDER BY letzter_sync DESC"
  ).all();
  return NextResponse.json(akten);
}

// Zugriff für User auf Akte vergeben/entziehen
export async function POST(req: NextRequest) {
  if (!await requireAdmin()) return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  const body = await req.json().catch(() => ({}));
  const { user_id, az, aktion } = body;
  if (!user_id || !az || !["erteilen", "entziehen"].includes(aktion)) {
    return NextResponse.json({ error: "user_id, az und aktion (erteilen|entziehen) erforderlich" }, { status: 400 });
  }
  const db = getDb();
  if (aktion === "erteilen") {
    db.prepare(
      "INSERT OR IGNORE INTO akte_zugriff (user_id, az) VALUES (?, ?)"
    ).run(user_id, az);
  } else {
    db.prepare("DELETE FROM akte_zugriff WHERE user_id = ? AND az = ?").run(user_id, az);
  }
  return NextResponse.json({ status: "ok" });
}
```

- [ ] **Step 10.3: `src/app/(authed)/admin/akten/page.tsx` erstellen**

```typescript
import { getDb } from "@/lib/db";
import { AmpelBadge } from "@/components/AmpelBadge";
import type { PortalAkte } from "@/types";

export default async function AktenPage() {
  const db = getDb();
  const akten = db.prepare(
    "SELECT az, status, ampel_status, ampel_farbe, sync_version, letzter_sync FROM akten ORDER BY letzter_sync DESC"
  ).all() as PortalAkte[];

  return (
    <main className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-xl font-semibold">Akten-Übersicht</h1>
        <span className="text-sm text-gray-500">{akten.length} Akten im Portal</span>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              {["Aktenzeichen", "Status", "Ampel", "Sync-Version", "Letzter Sync"].map((h) => (
                <th key={h} className="px-4 py-2 font-medium text-gray-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {akten.map((a) => (
              <tr key={a.az} className="hover:bg-gray-50">
                <td className="px-4 py-2 font-mono text-xs">{a.az}</td>
                <td className="px-4 py-2 text-gray-600">{a.status}</td>
                <td className="px-4 py-2">
                  <AmpelBadge status={a.ampel_status} farbe={a.ampel_farbe} />
                </td>
                <td className="px-4 py-2 text-gray-400">{a.sync_version}</td>
                <td className="px-4 py-2 text-gray-400 text-xs">
                  {a.letzter_sync
                    ? new Date(a.letzter_sync).toLocaleString("de-DE")
                    : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {akten.length === 0 && (
          <p className="text-center py-8 text-gray-400 text-sm">
            Noch keine Akten synchronisiert. Sync im Unfallakten-System aktivieren.
          </p>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 10.4: Visueller Test**

Dev-Server starten → Als `kanzlei_admin` einloggen (User manuell in DB einfügen) → `/admin/akten` → Leere Tabelle sichtbar. Sync-Push absenden → Akte erscheint.

```bash
# Test-Admin direkt in DB einfügen:
node -e "
const db = require('@journeyapps/sqlcipher')('./data/portal.db');
if (process.env.DB_ENCRYPTION_KEY) db.pragma(\"key='\" + process.env.DB_ENCRYPTION_KEY + \"'\");
db.prepare(\"INSERT INTO portal_users (id, email, name, rolle) VALUES ('admin-1', 'admin@test.de', 'Admin', 'kanzlei_admin')\").run();
console.log('Admin angelegt');
"
```

- [ ] **Step 10.5: Commit**

```bash
git add src/app/api/admin/akten/ src/app/"(authed)"/admin/akten/ src/components/AmpelBadge.tsx
git commit -m "feat(admin): Akten-Übersicht + Zugriffsvergabe API + AmpelBadge"
```

---

## Task 11: `next.config.ts` + Gesamtverifikation

**Files:**
- Modify: `next.config.ts`
- Modify: `.gitignore`

- [ ] **Step 11.1: `next.config.ts` anpassen**

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    serverComponentsExternalPackages: ["@journeyapps/sqlcipher"],
    // Falls SQLCipher-Fallback: ["better-sqlite3"]
  },
};

export default nextConfig;
```

- [ ] **Step 11.2: `.gitignore` ergänzen**

```
.env.local
data/
uploads/
*.db
*.db-wal
*.db-shm
```

- [ ] **Step 11.3: Gesamttest Foundation**

```bash
npm run build
```
Erwartetes Ergebnis: Build erfolgreich, keine TypeScript-Fehler.

```bash
npm run dev
```
Checkliste:
1. `http://localhost:3000` → Redirect zu `/login` ✓
2. Login-Formular erscheint ✓
3. E-Mail eingeben → `/login/sent` erscheint ✓
4. `POST /api/sync/push` mit korrektem API-Key + HMAC → `{"status":"processed"}` ✓
5. `GET /api/me` ohne Cookie → 401 ✓
6. Admin-User in DB einfügen → Login per Magic Link → `/admin` sichtbar ✓
7. `/admin/users` → Tabelle leer (nur Admin-User) ✓
8. `/admin/akten` → Tabelle leer (noch kein Sync) ✓

- [ ] **Step 11.4: Final Commit**

```bash
git add next.config.ts .gitignore
git commit -m "chore: next.config.ts standalone output + .gitignore data/uploads"
```

---

## Verifikationscheckliste (Portal-B1 vollständig)

| Check | Kriterium |
|---|---|
| SQLCipher | DB wird verschlüsselt angelegt, `DB_ENCRYPTION_KEY` nötig zum Öffnen ✓ |
| Magic Link | E-Mail mit Token wird versendet (Nodemailer/Strato) ✓ |
| Auth | Nur registrierte + aktive User bekommen gültige Session ✓ |
| Rate Limit | Max 3 Tokens/Stunde, 10/Tag pro E-Mail ✓ |
| Session | HttpOnly Cookie, 30 Min Sliding Expiry, automatischer Logout ✓ |
| Auth Guard | `/admin/*` nur mit `rolle = kanzlei_admin` erreichbar ✓ |
| Sync Endpoint | `POST /api/sync/push` mit HMAC-Verifikation + Idempotenz ✓ |
| Row-Level Security | `akte_zugriff`-Tabelle vorhanden, Vergabe über Admin-API ✓ |
| Admin-Panel | User anlegen, Akten-Übersicht nach erstem Sync ✓ |
| Docker Build | `docker build` erfolgreich, SQLCipher kompiliert ✓ |

---

## Nächste Schritte (Folge-Pläne)

Nach Abschluss von Portal-B1 + Portal-A1 (Sprint 1 vollständig):

**Portal-B2 – Sachverständigen-Cockpit:**
- KPI-Kacheln (offene/regulierte/abgeschlossene Gutachten)
- Sortierbare Ampel-Tabelle mit Filter (Status, Zeitraum)
- Detailansicht: Schaden-Regulierung-Vergleich, Dokument-Download

**Portal-B3 – Mandanten-Dashboard:**
- 6-Phasen-Timeline in Laiensprache
- Dokument-Download (Gutachten, Forderungsschreiben)
- Abschluss-Summary PDF anzeigen

**Sprint-Reihenfolge:**
1. Portal-A1 vollständig → Migration 38 + Sync-Service läuft lokal
2. Portal-B1 vollständig → Portal auf VPS deployed, Sync-Endpoint erreichbar
3. End-to-End testen: Akte aktivieren → Sync → Portal zeigt Akte
4. Portal-B2 + Portal-B3 iterativ
