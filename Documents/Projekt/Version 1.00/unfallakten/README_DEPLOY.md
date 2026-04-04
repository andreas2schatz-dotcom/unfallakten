# Pipeline-Deployment – Schritt-fuer-Schritt
# Stand: Session v23

## Reihenfolge

1. Migration 24 ausfuehren (neue DB-Spalten)
2. Workflow-Module deployen (dispatcher + escalation)
3. Test-Skript laufen lassen
4. dokumente_routes.py patchen (Auto-Parse-Trigger)
5. schema_manager.py patchen (damit Migration beim naechsten Restart automatisch laeuft)
6. Backend neu starten

## Befehle

### Schritt 1: Migration 24

```powershell
docker cp migration_24.py unfallakten-backend-dev:/app/migration_24.py
docker exec unfallakten-backend-dev python3 /app/migration_24.py
```

### Schritt 2: Workflow-Module

```powershell
docker exec unfallakten-backend-dev mkdir -p /app/backend/workflow
docker cp workflow/__init__.py unfallakten-backend-dev:/app/backend/workflow/__init__.py
docker cp workflow/dispatcher.py unfallakten-backend-dev:/app/backend/workflow/dispatcher.py
docker cp workflow/escalation.py unfallakten-backend-dev:/app/backend/workflow/escalation.py
```

### Schritt 3: Test

```powershell
docker cp test_pipeline.py unfallakten-backend-dev:/app/test_pipeline.py
docker exec unfallakten-backend-dev python3 /app/test_pipeline.py
```

Erwartete Ausgabe: "ALLE TESTS BESTANDEN"

### Schritt 4: dokumente_routes.py patchen

Siehe PATCH_dokumente_routes.py fuer den einzufuegenden Code-Block.

### Schritt 5: schema_manager.py patchen

Siehe PATCH_schema_manager.py fuer die drei Aenderungen.

### Schritt 6: Neustart

```powershell
docker restart unfallakten-backend-dev
docker logs unfallakten-backend-dev --tail 20
```

In den Logs sollte stehen:
- "Migration 24 abgeschlossen" (falls noch nicht gelaufen)
- "Registry geladen: 1210 Marker"

## Test: PDF hochladen

1. Ein bekanntes Gutachten hochladen → sollte als "gutachten" klassifiziert werden
2. Ein Abrechnungsschreiben hochladen → "abrechnungsschreiben"
3. Ein unbekanntes PDF hochladen → System-Todo im To-Do-Reiter
