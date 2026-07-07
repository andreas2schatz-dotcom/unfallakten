"""
Gunicorn-Konfiguration für Produktion
=======================================
Starten: gunicorn -c gunicorn.conf.py 'backend.app:erstelle_app()'

Dokumentation: https://docs.gunicorn.org/en/stable/configure.html
"""

import os
import multiprocessing

# ── Bind & Workers ────────────────────────────────────────────────────────────

# An allen Interfaces lauschen; nginx terminiert nach außen
bind = "0.0.0.0:5000"

# Empfehlung: 2–4 × CPU-Kerne
# Bei einem 2-Core-Server: 4 Workers
workers = int(os.environ.get("GUNICORN_WORKERS",
                              min(4, multiprocessing.cpu_count() * 2 + 1)))

# Worker-Klasse: sync für SQLite, gthread für PostgreSQL
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "sync")

# Threads pro Worker (nur für gthread relevant)
threads = int(os.environ.get("GUNICORN_THREADS", 2))

# Maximale gleichzeitige Verbindungen pro Worker
worker_connections = 1000

# ── Timeouts ──────────────────────────────────────────────────────────────────

# Antwort-Timeout in Sekunden (PDF-Parsing kann 10–15s dauern)
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 60))

# Keep-Alive für HTTP/1.1
keepalive = 5

# Graceful-Restart-Timeout
graceful_timeout = 30

# ── Logging ───────────────────────────────────────────────────────────────────

loglevel     = os.environ.get("LOG_LEVEL", "info").lower()
accesslog    = "-"    # stdout (wird von Docker/nginx gesammelt)
errorlog     = "-"    # stderr
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(D)sµs'
)

# ── Prozess & Sicherheit ──────────────────────────────────────────────────────

# PID-Datei (für Systemd/Docker-Health-Check)
pidfile = "/tmp/gunicorn.pid"

# Maximale Requests pro Worker vor Neustart (Memory-Leak-Schutz)
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = 50    # ± Jitter verhindert synchrone Neustarts

# Forwarded-IPs von nginx vertrauen (für korrektes Logging)
forwarded_allow_ips = "127.0.0.1,::1"

# ── Hooks ─────────────────────────────────────────────────────────────────────

def on_starting(server):
    server.log.info("Unfallakten-Backend startet (Gunicorn).")

def worker_exit(server, worker):
    server.log.info("Worker %s beendet.", worker.pid)

def post_fork(server, worker):
    """Nach jedem Fork: DB-Verbindung neu aufbauen."""
    import os
    # SQLite-Verbindung ist prozess-lokal, kein Pool-Reset nötig
    server.log.debug("Worker %s gestartet.", worker.pid)
