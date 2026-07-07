# ─────────────────────────────────────────────────────────────────────────────
# Unfallakten-Backend – Dockerfile
#
# Stages:
#   builder    – Dev-Modus: Flask + alle Pakete im System-Python, Hot-Reload
#   production – Prod-Modus: schlankes Image, non-root User, Gunicorn
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder (wird für Dev-Stack verwendet) ───────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# System-Pakete (gcc für pdfplumber, freetds-dev für pymssql → SQL Server)
# libreoffice-writer für DOCX→PDF (Vollmacht-Generator)
# fonts-liberation: Arial-kompatible Schriften für korrekte PDF-Darstellung
# tesseract-ocr + deu: OCR für gescannte PDFs (PRD-30)
# poppler-utils: pdf2image-Abhängigkeit (PDF → Bild)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    freetds-dev \
    freetds-bin \
    libreoffice-writer \
    fonts-liberation \
    tesseract-ocr \
    tesseract-ocr-deu \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Pakete direkt ins System-Python installieren (kein --prefix)
# → Flask ist sofort als `python -m flask` erreichbar
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Code kopieren (im Dev-Stack per Volume überschrieben → Hot-Reload)
COPY backend/ ./backend/
COPY gunicorn.conf.py .

RUN mkdir -p /app/data /app/uploads /app/logs

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/app/data/unfallakten.db \
    UPLOAD_DIR=/app/uploads \
    LOG_LEVEL=DEBUG \
    PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fs http://localhost:5000/health || exit 1


# ── Stage 2: production ────────────────────────────────────────────────────────
FROM python:3.12-slim AS production

# Sicherheit: Nicht als root laufen
RUN groupadd -r kanzlei && useradd -r -g kanzlei kanzlei

WORKDIR /app

# Runtime-Pakete (kein gcc nötig, aber freetds-bin für pymssql zur Laufzeit)
# libreoffice-writer für DOCX→PDF (Vollmacht-Generator)
# tesseract-ocr + deu + poppler: OCR für gescannte PDFs (PRD-30)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    freetds-bin \
    libreoffice-writer \
    fonts-liberation \
    tesseract-ocr \
    tesseract-ocr-deu \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Pakete aus builder-Stage kopieren
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Anwendungscode
COPY backend/ ./backend/
COPY gunicorn.conf.py .

# Verzeichnisse + Berechtigungen
RUN mkdir -p /app/data /app/uploads /app/logs \
 && chown -R kanzlei:kanzlei /app

USER kanzlei

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/app/data/unfallakten.db \
    UPLOAD_DIR=/app/uploads \
    LOG_LEVEL=INFO \
    PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fs http://localhost:5000/health || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "backend.app:erstelle_app()"]
