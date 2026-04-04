# ─────────────────────────────────────────────────────────────────────────────
# Makefile – Unfallakten-System
# Verwendung: make <ziel>
# Hilfe:      make help
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help install install-all dev dev-frontend dev-all \
        test test-modul1 test-modul2 test-modul3 \
        test-modul4 test-modul5 test-modul6 test-modul7 test-alle lint seed \
        frontend-install frontend-dev frontend-build frontend-preview \
        docker-dev docker-prod docker-stop docker-logs docker-clean \
        backup deploy shell db-shell health frontend-logs backend-logs

# ── Standard: Hilfe anzeigen ──────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Unfallakten-System – Makefile-Befehle"
	@echo "  ══════════════════════════════════════"
	@echo ""
	@echo "  ENTWICKLUNG (Backend)"
	@echo "  ─────────────────────────────────────"
	@echo "  make install          Python-Abhängigkeiten installieren"
	@echo "  make dev              Flask Dev-Server (Port 5000)"
	@echo "  make seed             Testdaten laden"
	@echo "  make shell            Python-Shell mit App-Context"
	@echo "  make db-shell         SQLite-Shell"
	@echo ""
	@echo "  ENTWICKLUNG (Frontend)"
	@echo "  ─────────────────────────────────────"
	@echo "  make frontend-install  npm ci (Node-Abhängigkeiten)"
	@echo "  make frontend-dev      Vite Dev-Server (Port 5173)"
	@echo "  make frontend-build    Produktions-Build (→ frontend/dist/)"
	@echo "  make frontend-preview  Build-Vorschau (Port 4173)"
	@echo ""
	@echo "  ENTWICKLUNG (Beides)"
	@echo "  ─────────────────────────────────────"
	@echo "  make install-all      Backend + Frontend installieren"
	@echo "  make dev-all          Backend + Frontend parallel starten"
	@echo ""
	@echo "  TESTS"
	@echo "  ─────────────────────────────────────"
	@echo "  make test             Alle Backend-Tests (mit Coverage)"
	@echo "  make test-modul1..7   Einzelne Module"
	@echo ""
	@echo "  DOCKER"
	@echo "  ─────────────────────────────────────"
	@echo "  make docker-dev       Dev-Stack (Backend + Frontend)"
	@echo "  make docker-prod      Prod-Stack (mit nginx + TLS)"
	@echo "  make docker-stop      Stack stoppen"
	@echo "  make docker-logs      Alle Logs"
	@echo "  make frontend-logs    Nur Frontend-Logs"
	@echo "  make backend-logs     Nur Backend-Logs"
	@echo "  make docker-clean     Container + Volumes löschen (ACHTUNG!)"
	@echo "  make health           Health-Check"
	@echo ""
	@echo "  WARTUNG"
	@echo "  ─────────────────────────────────────"
	@echo "  make backup           Manuelles Backup"
	@echo "  make deploy           Produktions-Deployment"
	@echo ""

# ── Backend-Entwicklung ───────────────────────────────────────────────────────

install:
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "✓ Python-Abhängigkeiten installiert."

dev:
	@echo "Starte Flask Dev-Server auf http://localhost:5000 ..."
	@export FLASK_DEBUG=true; \
	 export JWT_SECRET_KEY=$${JWT_SECRET_KEY:-dev-secret-key-nicht-fuer-produktion}; \
	 export DB_PATH=$${DB_PATH:-./backend/data/unfallakten.db}; \
	 export UPLOAD_DIR=$${UPLOAD_DIR:-./backend/uploads}; \
	 python -m flask \
	   --app "backend.app:erstelle_app()" \
	   run --host 0.0.0.0 --port 5000 --reload --debug

seed:
	@echo "Lade Testdaten..."
	@export JWT_SECRET_KEY=$${JWT_SECRET_KEY:-dev-secret-key}; \
	 export DB_PATH=$${DB_PATH:-./backend/data/unfallakten.db}; \
	 python -m backend.scripts.seed_db

shell:
	@export JWT_SECRET_KEY=$${JWT_SECRET_KEY:-dev-secret-key}; \
	 export DB_PATH=$${DB_PATH:-./backend/data/unfallakten.db}; \
	 python -c "from backend.app import erstelle_app; app = erstelle_app(); ctx = app.app_context(); ctx.push(); print('App-Context aktiv.')" -i

db-shell:
	@sqlite3 $${DB_PATH:-./backend/data/unfallakten.db} \
	   ".headers on" ".mode column" \
	   ".tables"

# ── Frontend-Entwicklung ──────────────────────────────────────────────────────

frontend-install:
	@echo "Installiere Frontend-Abhängigkeiten..."
	cd frontend && npm install
	@echo "✓ Node-Abhängigkeiten installiert (package-lock.json erzeugt/aktualisiert)."
	@echo "  Tipp: package-lock.json einchecken: git add frontend/package-lock.json"

frontend-dev:
	@echo "Starte Vite Dev-Server auf http://localhost:5173 ..."
	@echo "  Proxy: /auth /akten /email → http://localhost:5000"
	cd frontend && npm run dev

frontend-build:
	@echo "Baue Frontend für Produktion..."
	cd frontend && npm run build
	@echo "✓ Build fertig. Ausgabe: frontend/dist/"
	@du -sh frontend/dist/
	@echo "  Dateien:"
	@find frontend/dist -name "*.js" -o -name "*.css" | xargs ls -lh 2>/dev/null

frontend-preview:
	@echo "Starte Build-Vorschau auf http://localhost:4173 ..."
	cd frontend && npm run preview

# ── Kombiniert ────────────────────────────────────────────────────────────────

install-all: install frontend-install
	@echo "✓ Alle Abhängigkeiten installiert."

dev-all:
	@echo "Starte Backend + Frontend parallel..."
	@echo "  Backend:  http://localhost:5000"
	@echo "  Frontend: http://localhost:5173"
	@trap 'kill 0' INT; \
	 $(MAKE) dev & \
	 sleep 2 && $(MAKE) frontend-dev & \
	 wait

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	@export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!; \
	 python -m pytest backend/tests/ \
	   --tb=short -v \
	   --cov=backend \
	   --cov-report=term-missing \
	   --cov-report=html:htmlcov \
	   2>&1 | tail -40
	@echo "Coverage-Report: htmlcov/index.html"

test-modul1:
	@export JWT_SECRET_KEY=test-key; python -m backend.tests.test_modul1

test-modul2:
	@export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!; python -m backend.tests.test_modul2

test-modul3:
	@export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!; python -m backend.tests.test_modul3

test-modul4:
	@export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!; python -m backend.tests.test_modul4

test-modul5:
	@export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!; python -m backend.tests.test_modul5

test-modul6:
	@export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!; python -m backend.tests.test_modul6

test-modul7:
	@export JWT_SECRET_KEY=test-secret-key-minimum-32-chars!!; python -m backend.tests.test_modul7

test-alle: test
	@echo "✓ Alle Tests abgeschlossen."

# ── Docker ────────────────────────────────────────────────────────────────────

docker-dev:
	docker compose up --build

docker-prod:
	@if [ ! -f ".env" ]; then \
	   echo "FEHLER: .env fehlt. Aus .env.example kopieren und ausfüllen."; exit 1; fi
	@if [ ! -f "nginx/ssl/fullchain.pem" ]; then \
	   echo "FEHLER: nginx/ssl/fullchain.pem fehlt. TLS-Zertifikat einrichten."; exit 1; fi
	CACHEBUST=$(shell date +%s) docker compose -f docker-compose.prod.yml up -d --build
	@echo "✓ Prod-Stack gestartet."
	@$(MAKE) health

docker-stop:
	docker compose down 2>/dev/null || true
	docker compose -f docker-compose.prod.yml down 2>/dev/null || true
	@echo "✓ Stack gestoppt."

docker-logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100

frontend-logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100 frontend

backend-logs:
	docker compose -f docker-compose.prod.yml logs -f --tail=100 backend

docker-clean:
	@echo "ACHTUNG: Löscht alle Container und Volumes (Datenverlust möglich)!"
	@read -p "Wirklich fortfahren? [j/N] " confirm && [ "$$confirm" = "j" ] || exit 1
	docker compose down -v
	docker compose -f docker-compose.prod.yml down -v
	docker image rm unfallakten-backend:prod unfallakten-frontend:prod 2>/dev/null || true
	@echo "✓ Bereinigt."

health:
	@HTTP=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health 2>/dev/null || echo "000"); \
	 if [ "$$HTTP" = "200" ]; then \
	   echo "✓ Backend Health-Check OK (HTTP 200)"; \
	 else \
	   echo "✗ Health-Check fehlgeschlagen (HTTP $$HTTP)"; exit 1; fi
	@HTTP_FE=$$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000"); \
	 if [ "$$HTTP_FE" = "200" ] || [ "$$HTTP_FE" = "301" ]; then \
	   echo "✓ Frontend erreichbar (HTTP $$HTTP_FE)"; \
	 else \
	   echo "⚠ Frontend: HTTP $$HTTP_FE"; fi

# ── Wartung ───────────────────────────────────────────────────────────────────

backup:
	docker compose -f docker-compose.prod.yml exec backup sh /backup.sh

deploy:
	bash scripts/deploy.sh

# ── Lint ──────────────────────────────────────────────────────────────────────
lint:
	@echo "Prüfe Python-Code (flake8)..."
	@python -m flake8 backend/ --max-line-length=120 --exclude=__pycache__,*.pyc 2>/dev/null || true
	@echo "Prüfe Frontend (ESLint)..."
	@cd frontend && npm run lint 2>/dev/null || true
