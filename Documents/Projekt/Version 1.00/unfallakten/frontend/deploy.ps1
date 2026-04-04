# PRD-20: App.jsx Refactoring Deploy
# Entpacken und aus dem Verzeichnis mit dem src/ Ordner ausfuehren

# ══════════════════════════════════════════════════════════════
# 1. Alle neuen Verzeichnisse im Container anlegen
# ══════════════════════════════════════════════════════════════
docker exec unfallakten-frontend-dev mkdir -p /app/src/config
docker exec unfallakten-frontend-dev mkdir -p /app/src/components
docker exec unfallakten-frontend-dev mkdir -p /app/src/sections
docker exec unfallakten-frontend-dev mkdir -p /app/src/views
docker exec unfallakten-frontend-dev mkdir -p /app/src/state

# ══════════════════════════════════════════════════════════════
# 2. Config-Module
# ══════════════════════════════════════════════════════════════
docker cp src/config/theme.js unfallakten-frontend-dev:/app/src/config/theme.js
docker cp src/config/constants.js unfallakten-frontend-dev:/app/src/config/constants.js
docker cp src/config/icons.jsx unfallakten-frontend-dev:/app/src/config/icons.jsx
docker cp src/config/utils.js unfallakten-frontend-dev:/app/src/config/utils.js

# ══════════════════════════════════════════════════════════════
# 3. Common Components
# ══════════════════════════════════════════════════════════════
docker cp src/components/common.jsx unfallakten-frontend-dev:/app/src/components/common.jsx
docker cp src/components/LoginPage.jsx unfallakten-frontend-dev:/app/src/components/LoginPage.jsx
docker cp src/components/layout.jsx unfallakten-frontend-dev:/app/src/components/layout.jsx
docker cp src/components/AkteDetailView.jsx unfallakten-frontend-dev:/app/src/components/AkteDetailView.jsx

# ══════════════════════════════════════════════════════════════
# 4. State
# ══════════════════════════════════════════════════════════════
docker cp src/state/reducer.js unfallakten-frontend-dev:/app/src/state/reducer.js

# ══════════════════════════════════════════════════════════════
# 5. Sections (Akte-Reiter)
# ══════════════════════════════════════════════════════════════
docker cp src/sections/UebersichtSection.jsx unfallakten-frontend-dev:/app/src/sections/UebersichtSection.jsx
docker cp src/sections/BeteiligteSection.jsx unfallakten-frontend-dev:/app/src/sections/BeteiligteSection.jsx
docker cp src/sections/SchadenSection.jsx unfallakten-frontend-dev:/app/src/sections/SchadenSection.jsx
docker cp src/sections/RegulierungSection.jsx unfallakten-frontend-dev:/app/src/sections/RegulierungSection.jsx
docker cp src/sections/DokumenteSection.jsx unfallakten-frontend-dev:/app/src/sections/DokumenteSection.jsx
docker cp src/sections/RaMicroSachstandsCard.jsx unfallakten-frontend-dev:/app/src/sections/RaMicroSachstandsCard.jsx
docker cp src/sections/WordSection.jsx unfallakten-frontend-dev:/app/src/sections/WordSection.jsx
docker cp src/sections/UnfalldetailsSection.jsx unfallakten-frontend-dev:/app/src/sections/UnfalldetailsSection.jsx
docker cp src/sections/KlageSection.jsx unfallakten-frontend-dev:/app/src/sections/KlageSection.jsx

# ══════════════════════════════════════════════════════════════
# 6. Views (eigenstaendige Ansichten)
# ══════════════════════════════════════════════════════════════
docker cp src/views/StatistikenView.jsx unfallakten-frontend-dev:/app/src/views/StatistikenView.jsx
docker cp src/views/DashboardView.jsx unfallakten-frontend-dev:/app/src/views/DashboardView.jsx
docker cp src/views/KuerzungskatalogView.jsx unfallakten-frontend-dev:/app/src/views/KuerzungskatalogView.jsx
docker cp src/views/EinstellungenView.jsx unfallakten-frontend-dev:/app/src/views/EinstellungenView.jsx
docker cp src/views/EmailImportView.jsx unfallakten-frontend-dev:/app/src/views/EmailImportView.jsx
docker cp src/views/WiedervorlageView.jsx unfallakten-frontend-dev:/app/src/views/WiedervorlageView.jsx
docker cp src/views/AktensucheView.jsx unfallakten-frontend-dev:/app/src/views/AktensucheView.jsx

# ══════════════════════════════════════════════════════════════
# 7. App.jsx (slim shell – 176 Zeilen)
# ══════════════════════════════════════════════════════════════
docker cp src/App.jsx unfallakten-frontend-dev:/app/src/App.jsx

# ══════════════════════════════════════════════════════════════
# 8. Pruefen
# ══════════════════════════════════════════════════════════════
docker exec unfallakten-frontend-dev ls -la /app/src/config/
docker exec unfallakten-frontend-dev ls -la /app/src/components/
docker exec unfallakten-frontend-dev ls -la /app/src/sections/
docker exec unfallakten-frontend-dev ls -la /app/src/views/
docker exec unfallakten-frontend-dev ls -la /app/src/state/

# ══════════════════════════════════════════════════════════════
# Testen:
#   1. Browser oeffnen → Login
#   2. Dashboard pruefen
#   3. Akte oeffnen → alle Reiter durchklicken
#   4. PDF hochladen → Dropdown-Badge pruefen
#   5. Korrektur-Dropdown testen
#   6. E-Mail-Import pruefen
#   7. Einstellungen oeffnen
#
# Bei Fehler: Vite-Konsole im Browser pruefen (F12 → Console)
#
# Rollback: Alte App.jsx wiederherstellen:
#   docker cp App.jsx.backup unfallakten-frontend-dev:/app/src/App.jsx
# ══════════════════════════════════════════════════════════════
