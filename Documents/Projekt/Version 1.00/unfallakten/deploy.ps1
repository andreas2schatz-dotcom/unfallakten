# Pipeline Deploy v24 – Feedback-Loop + TF-IDF Training
# Ausfuehren aus dem Verzeichnis wo die ZIP entpackt wurde

# ══════════════════════════════════════════════════════════════
# 1. Backend-Dateien deployen
# ══════════════════════════════════════════════════════════════
docker cp backend/db/schema_manager.py unfallakten-backend-dev:/app/backend/db/schema_manager.py
docker cp backend/workflow/dispatcher.py unfallakten-backend-dev:/app/backend/workflow/dispatcher.py
docker cp backend/routers/dokumente_routes.py unfallakten-backend-dev:/app/backend/routers/dokumente_routes.py

# ══════════════════════════════════════════════════════════════
# 2. Frontend deployen
# ══════════════════════════════════════════════════════════════
docker cp frontend/src/App.jsx unfallakten-frontend-dev:/app/src/App.jsx
docker cp frontend/src/api.js unfallakten-frontend-dev:/app/src/api.js

# ══════════════════════════════════════════════════════════════
# 3. Backend neu starten (Migration 25 laeuft automatisch)
# ══════════════════════════════════════════════════════════════
docker restart unfallakten-backend-dev
docker logs unfallakten-backend-dev --tail 20

# ══════════════════════════════════════════════════════════════
# Erwartete Logs:
#   "Migration 25: klassifikation_training-Tabelle angelegt."
#   "Datenbank ist aktuell (Version 25)."
#
# Test:
#   1. PDF hochladen → Dispatcher klassifiziert automatisch
#   2. In Dokumentenliste: Klassen-Dropdown klicken
#   3. Andere Klasse waehlen → Parser laeuft → Badge aktualisiert
#   4. Trainingsdaten pruefen:
#      docker exec unfallakten-backend-dev python3 -c "import sqlite3; c=sqlite3.connect('/app/data/unfallakten.db'); [print(dict(r)) for r in c.execute('SELECT id, klasse_auto, klasse_korrigiert, korrigiert_am FROM klassifikation_training').fetchall()]"
# ══════════════════════════════════════════════════════════════
