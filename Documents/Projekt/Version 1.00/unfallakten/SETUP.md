# Unfallakten-System – Einrichtungsanleitung

## Voraussetzungen
- Docker ≥ 24 + Docker Compose v2
- Domain mit A-Record auf den Server
- Offene Ports 80 und 443

---

## 1. Repo klonen
```bash
git clone <repo-url> unfallakten
cd unfallakten
```

## 2. Umgebungsvariablen setzen
```bash
cp .env.example .env
# .env öffnen und JWT_SECRET_KEY + CORS_ORIGIN + ggf. IMAP-Daten ausfüllen
# CORS_ORIGIN muss die echte Domain sein, z.B.: https://anwalt-offenbach.de
```

## 2a. Frontend-Abhängigkeiten installieren (einmalig nach Checkout)
```bash
# Erzeugt package-lock.json und installiert node_modules lokal
make frontend-install
# Lockfile einchecken, damit Docker-Build reproduzierbar ist:
git add frontend/package-lock.json && git commit -m "chore: add package-lock.json"
```

## 3. SSL-Zertifikat einrichten

**Option A – Let's Encrypt (empfohlen):**
```bash
# Certbot einmalig ausführen (vor dem ersten Start)
docker run --rm -p 80:80 \
  certbot/certbot certonly --standalone \
  -d anwalt-offenbach.de \
  --email it@anwalt-offenbach.de \
  --agree-tos --no-eff-email

# Zertifikate kopieren
cp /etc/letsencrypt/live/anwalt-offenbach.de/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/anwalt-offenbach.de/privkey.pem   nginx/ssl/
```

**Option B – Selbstsigniert (nur Entwicklung):**
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out    nginx/ssl/fullchain.pem \
  -subj "/CN=localhost"
```

## 4. Ersten Start durchführen
```bash
make docker-prod
# Oder direkt:
docker compose -f docker-compose.prod.yml up -d --build
```

## 5. Testdaten laden (optional)
```bash
docker compose -f docker-compose.prod.yml exec backend \
  python -m backend.scripts.seed_db
```

## 6. Health-Check
```bash
make health
# → ✓ Backend Health-Check OK (HTTP 200)
# → ✓ Frontend erreichbar (HTTP 301)
```

---

## Lokale Entwicklung (ohne Docker)

```bash
# Backend + Frontend parallel starten:
make install-all
make dev-all

# Nur Backend:
make install && make dev

# Nur Frontend:
make frontend-install && make frontend-dev
```

---

## Updates einspielen
```bash
./scripts/deploy.sh
# Oder nur Frontend:
./scripts/deploy.sh --only-fe
```

---

## Zugangsdaten (nach Seed)
| E-Mail | Passwort | Rolle |
|---|---|---|
| koch@anwalt-offenbach.de | Kanzlei2024! | Admin |
| schatz@anwalt-offenbach.de | Kanzlei2024! | Anwalt |
| ihl@anwalt-offenbach.de | Kanzlei2024! | Assistent |
