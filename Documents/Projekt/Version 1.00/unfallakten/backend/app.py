"""
Modul 2 – Flask Application Factory
======================================
Erstellt und konfiguriert die Flask-App.
Registriert alle Blueprints und globale Fehlerbehandlung.

Verwendung:
    # Entwicklung
    python -m backend.app

    # Produktion (mit gunicorn)
    gunicorn 'backend.app:erstelle_app()' --bind 0.0.0.0:5000
"""

import os
import logging
from flask import Flask, jsonify
from flask_apscheduler import APScheduler
from .db.schema_manager import init_db
from .routers.abrechnungsschreiben_routes import abrechnung_bp, pruefbericht_bp
from .routers.akten_routes import akten_bp
from .routers.aktensuche_routes import aktensuche_bp
from .routers.auth_routes import auth_bp
from .routers.belege_routes import belege_bp
from .routers.beteiligte_routes import beteiligte_bp
from .routers.dashboard_routes import dashboard_bp
from .routers.distanz_routes import distanz_bp
from .routers.dokumente_routes import dokumente_bp
from .routers.eakte_routes import eakte_bp
from .routers.einstellungen_routes import einstellungen_bp
from .routers.email_routes import email_bp
from .routers.firmen_routes import firmen_bp
from .routers.forderung_routes import forderung_bp
from .routers.gebuehren_routes import gebuehren_bp
from .routers.intake_routes import intake_bp
from .routers.klage_routes import klage_bp, unfalldetails_bp
from .routers.kuerzungsarten_routes import kuerzungsarten_bp
from .routers.pdf_parse_routes import pdf_parse_bp
from .routers.positionen_routes import positionen_bp
from .routers.personenschaden_routes import ps_bp
from .routers.pruefberichte_routes import pruefberichte_bp
from .routers.ramicro_akte_routes import ramicro_akte_bp
from .routers.schaden_routes import schaden_bp, regulierung_bp
from .routers.sta_routes import sta_bp
from .routers.standardtexte_routes import standardtexte_bp
from .routers.sv_portal_routes import sv_portal_bp
from .routers.stellungnahme_routes import stellungnahme_bp
from .routers.todos_routes import todos_bp
from .routers.wiedervorlage_routes import wiedervorlage_bp
from .routers.word_routes import word_bp
from .routers.portal_routes import portal_bp
from .routers.system_routes import system_bp


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def _ensure_admin_exists(app) -> None:
    """
    Legt beim ersten Start automatisch den Admin-Benutzer an,
    falls die Datenbank noch leer ist.
    Credentials kommen aus .env (ADMIN_EMAIL, ADMIN_PASSWORT) oder Defaults.
    """
    try:
        from .db.database import get_connection
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM benutzer").fetchone()["n"]
            if count > 0:
                return  # Benutzer bereits vorhanden

        from .models.benutzer import erstelle_benutzer
        admin_email    = os.environ.get("ADMIN_EMAIL",    "koch@anwalt-offenbach.de")
        admin_passwort = os.environ.get("ADMIN_PASSWORT", "Kanzlei2024!")
        admin_name     = os.environ.get("ADMIN_NAME",     "Peter Koch")

        erstelle_benutzer(name=admin_name, email=admin_email,
                          passwort=admin_passwort, rolle="admin")
        logger.info("Admin-Benutzer angelegt: %s", admin_email)

        # Zweiter Admin
        try:
            erstelle_benutzer(name="Andreas Schatz",
                              email="schatz@anwalt-offenbach.de",
                              passwort=os.environ.get("ADMIN_PASSWORT_2", "As155255"),
                              rolle="admin")
            logger.info("Admin-Benutzer angelegt: schatz@anwalt-offenbach.de")
        except Exception:
            pass

        # Weitere Benutzer aus .env (optional, kommagetrennt)
        # Format: EXTRA_USERS=Name|email|passwort|rolle,...
        extra = os.environ.get("EXTRA_USERS", "")
        for eintrag in extra.split(","):
            teile = eintrag.strip().split("|")
            if len(teile) == 4:
                try:
                    erstelle_benutzer(name=teile[0], email=teile[1],
                                      passwort=teile[2], rolle=teile[3])
                    logger.info("Benutzer angelegt: %s", teile[1])
                except Exception:
                    pass
    except Exception as e:
        logger.warning("_ensure_admin_exists fehlgeschlagen: %s", e)


def erstelle_app(test_config: dict = None) -> Flask:
    """
    Application Factory Pattern.
    Ermöglicht verschiedene Konfigurationen (Entwicklung, Test, Produktion).
    """
    app = Flask(__name__)

    # ── Konfiguration ─────────────────────────────────────────────────────────
    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "FLASK_SECRET_KEY ist nicht gesetzt. "
            "Bitte in der .env-Datei konfigurieren (siehe .env.example)."
        )
    app.config.update(
        SECRET_KEY=secret_key,
        JSON_SORT_KEYS=False,          # JSON-Reihenfolge beibehalten
        PROPAGATE_EXCEPTIONS=False,
    )

    if test_config:
        app.config.update(test_config)

    # ── Dokumentklassen-Registry (S1.5): Fail-Loud vor DB-Init ────────────────
    # Ein defektes YAML muss den App-Start abbrechen, damit die Pipeline nicht
    # heimlich mit leerer Registry laeuft (behebt den heutigen registry.json-Bug).
    from .intake.registry_loader import lade_registry, standard_pfad
    _reg = lade_registry(standard_pfad(), reload=True)
    logger.info("Dokumentklassen-Registry geladen: %d Klassen (version=%s)",
                len(_reg.klassen), _reg.version)

    # ── Positionsmodell-Registry (P1.1): Fail-Loud vor DB-Init ────────────────
    # Analog S1.5 -- defektes positionsarten/ereignistypen/aktionen-YAML
    # bricht den App-Start ab.
    from .services.positionsmodell_registry import lade_positionsmodell
    _pmreg = lade_positionsmodell(reload=True)
    logger.info(
        "Positionsmodell-Registry geladen: %d Arten, %d Typen, %d Aktionen "
        "(version=%s)",
        len(_pmreg.positionsarten), len(_pmreg.ereignistypen),
        len(_pmreg.aktionen), _pmreg.version,
    )

    # ── Kürzungstyp-Registry (Kürzungstaxonomie Phase 1): Fail-Loud ───────────
    # Defektes YAML in registry/kuerzungstypen bricht den App-Start ab.
    from .services.kuerzungstyp_registry import lade_kuerzungstypen
    _ktreg = lade_kuerzungstypen(reload=True)
    logger.info("Kürzungstyp-Registry geladen: %d Typen (Version %s)",
                len(_ktreg.typen), _ktreg.version)

    # ── Rausch-Absender-Registry: Fail-Loud vor DB-Init ───────────────────────
    # Defektes YAML bricht den App-Start ab, statt spaeter jede Intake-Mail
    # scheitern zu lassen (sonst stiller Intake-Stillstand).
    from .intake.rausch_regel import lade_regeln as _lade_rausch
    _rausch = _lade_rausch(reload=True)
    logger.info("Rausch-Absender-Registry geladen: %d Absender", len(_rausch))

    # ── Klage-Standardtext-Registry: Fail-Loud vor DB-Init ────────────────────
    from .services.standardtext_registry import lade_standardtexte as _lade_standardtexte
    _standardtexte = _lade_standardtexte(reload=True)
    logger.info("Klage-Standardtext-Registry geladen: %d Bausteine", len(_standardtexte))

    # ── Datenbank initialisieren ───────────────────────────────────────────────
    with app.app_context():
        init_db()
        logger.info("Datenbank initialisiert.")

        # ── LLM-Modell aus DB laden (damit nicht "qwen" als Default bleibt) ──
        try:
            from .services.llm_service import init_from_db as _llm_init
            _llm_init()
        except Exception as _e:
            logger.warning("LLM-Init übersprungen: %s", _e)

        # ── Initialen Admin anlegen falls keine Benutzer vorhanden ────────────
        _ensure_admin_exists(app)

    # ── Blueprints registrieren ────────────────────────────────────────────────
    app.register_blueprint(abrechnung_bp)
    app.register_blueprint(akten_bp)
    app.register_blueprint(aktensuche_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(belege_bp)
    app.register_blueprint(beteiligte_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(distanz_bp)
    app.register_blueprint(dokumente_bp)
    app.register_blueprint(eakte_bp)
    app.register_blueprint(einstellungen_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(firmen_bp)
    app.register_blueprint(forderung_bp)
    app.register_blueprint(gebuehren_bp)
    app.register_blueprint(intake_bp)
    app.register_blueprint(klage_bp)
    app.register_blueprint(unfalldetails_bp)
    app.register_blueprint(kuerzungsarten_bp)
    app.register_blueprint(pdf_parse_bp)
    app.register_blueprint(positionen_bp)
    app.register_blueprint(pruefbericht_bp)
    app.register_blueprint(pruefberichte_bp)
    app.register_blueprint(ps_bp)
    app.register_blueprint(ramicro_akte_bp)
    app.register_blueprint(regulierung_bp)
    app.register_blueprint(schaden_bp)
    app.register_blueprint(standardtexte_bp)
    app.register_blueprint(sta_bp)
    app.register_blueprint(sv_portal_bp)
    app.register_blueprint(stellungnahme_bp)
    app.register_blueprint(todos_bp)
    app.register_blueprint(wiedervorlage_bp)
    app.register_blueprint(word_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(system_bp)
    logger.info("Alle Blueprints registriert.")

    # ── APScheduler: Hintergrund-Health-Checks ────────────────────────────────
    # BUG-10: Unter Gunicorn laufen mehrere Worker -- der Scheduler darf nur in
    # EINEM Prozess starten (sonst 4x Polling / vervielfachte Fristablauf-
    # Ereignisse). Prozessuebergreifender Lease via Loopback-Bind.
    from .services.scheduler_lease import erwirb_scheduler_lease
    if not app.testing and erwirb_scheduler_lease():
        from .system.health_service import check_ramicro as _check_ramicro
        from .email_import.polling_service import fuehre_polling_durch as _imap_polling
        from .intake.pipeline import tick as _intake_tick
        from .services.fristablauf_service import (
            verarbeite_faellige_todos as _fristablauf_tick,
        )
        scheduler = APScheduler()
        app.config["SCHEDULER_API_ENABLED"] = False
        scheduler.init_app(app)
        scheduler.add_job(
            id="health_ramicro",
            func=_check_ramicro,
            trigger="interval",
            seconds=60,
            replace_existing=True,
        )
        scheduler.add_job(
            id="imap_polling",
            func=_imap_polling,
            trigger="interval",
            seconds=60,
            replace_existing=True,
        )
        # S1.6a: Intake-Pipeline-Worker. Single-Instance per Worker-Lease (F-10);
        # max_instances=1 verhindert zusätzlich, dass mehrere Ticks im selben
        # Prozess überlappen. Kurzer Tick (10s), damit neue Dokumente zügig
        # verarbeitet werden; das Lease dauert 5 Min.
        scheduler.add_job(
            id="intake_worker",
            func=_intake_tick,
            trigger="interval",
            seconds=10,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        # P1.6: taeglicher Fristablauf-Job (nachts, 03:15 lokal). Liest
        # faellige system-todos und schreibt fuer jede ein fristablauf-
        # Ereignis (idempotent ueber todos.fristablauf_ereignis_id).
        scheduler.add_job(
            id="fristablauf_job",
            func=_fristablauf_tick,
            trigger="cron",
            hour=3,
            minute=15,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        import threading as _threading
        _threading.Thread(target=_check_ramicro, daemon=True).start()
        logger.info("APScheduler gestartet: RA-Micro Health-Check + "
                    "IMAP-Polling (60s) + Intake-Worker (10s) + "
                    "Fristablauf (taeglich 03:15)")

    @app.cli.command("sync-portal")
    def sync_portal_cmd():
        """Pusht ausstehende Portal-Sync-Eintraege (max 10 pro Aufruf)."""
        from .db.database import get_connection
        from .services.portal_sync import process_queue as _portal_process_queue
        with get_connection() as conn:
            n = _portal_process_queue(conn)
            print("Portal-Sync: {} Akte(n) synchronisiert.".format(n))

    # ── CORS-Header (für React-Frontend) ──────────────────────────────────────
    @app.after_request
    def cors_header(response):
        response.headers["Access-Control-Allow-Origin"]  = os.environ.get(
            "CORS_ORIGIN", "http://localhost:5173"   # Vite Dev-Server
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization"
        )
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        )
        return response

    @app.route("/", methods=["OPTIONS"])
    @app.route("/<path:path>", methods=["OPTIONS"])
    def handle_options(path=""):
        """Beantwortet CORS-Preflight-Anfragen."""
        return "", 204

    # ── Globale Fehlerbehandlung ───────────────────────────────────────────────
    @app.errorhandler(404)
    def nicht_gefunden(e):
        return jsonify({"fehler": "Endpunkt nicht gefunden.", "status": 404}), 404

    @app.errorhandler(405)
    def methode_nicht_erlaubt(e):
        return jsonify({"fehler": "HTTP-Methode nicht erlaubt.", "status": 405}), 405

    @app.errorhandler(500)
    def interner_fehler(e):
        logger.error("Interner Serverfehler: %s", e)
        return jsonify({"fehler": "Interner Serverfehler.", "status": 500}), 500

    # ── Health-Check (für Docker + nginx) ────────────────────────────────────
    @app.route("/health", methods=["GET"])
    def health():
        """
        Liefert den Gesundheitsstatus der Anwendung.
        Prüft: DB erreichbar, Schema aktuell.
        Wird von Docker HEALTHCHECK und nginx genutzt.
        """
        import time
        start = time.monotonic()
        db_ok = False
        db_fehler = None
        akte_anzahl = 0

        try:
            from .db.database import get_connection
            with get_connection() as conn:
                row = conn.execute("SELECT COUNT(*) as n FROM unfallakte").fetchone()
                akte_anzahl = row["n"] if row else 0
                db_ok = True
        except Exception as e:
            db_fehler = str(e)

        dauer_ms = round((time.monotonic() - start) * 1000, 1)
        status_code = 200 if db_ok else 503

        return jsonify({
            "status":    "ok" if db_ok else "fehler",
            "datenbank": "ok" if db_ok else f"fehler: {db_fehler}",
            "akten":     akte_anzahl,
            "version":   "1.0.0",
            "dauer_ms":  dauer_ms,
        }), status_code

    # ── Root-Endpunkt ─────────────────────────────────────────────────────────
    @app.route("/", methods=["GET"])
    def root():
        return jsonify({
            "name":    "Unfallakten-API",
            "version": "1.0.0",
            "module":  "Modul 1–6 aktiv",
            "endpunkte": {
                "auth":          "/auth/*",
                "akten":         "/akten/*",
                "beteiligte":    "/akten/<id>/beteiligte/*",
                "schaden":       "/akten/<id>/schaden",
                "regulierungen": "/akten/<id>/regulierungen/*",
                "dokumente":     "/akten/<id>/dokumente/*",
                "word":          "/akten/<id>/dokumente/word/*",
                "health":        "/health",
            }
        })

    return app


# Direkt ausführbar
if __name__ == "__main__":
    app = erstelle_app()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    logger.info("Server startet auf http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=debug)
