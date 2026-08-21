import os
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret-key-scheduler")
import inspect
from backend import app as app_modul


def test_job_ist_registriert():
    quelltext = inspect.getsource(app_modul)
    assert "_ablage_abgleich_job" in quelltext


def test_job_laeuft_um_03_30():
    quelltext = inspect.getsource(app_modul)
    stelle = quelltext.index("_ablage_abgleich_job")
    umfeld = quelltext[stelle:stelle + 1100]
    assert "hour=3" in umfeld
    assert "minute=30" in umfeld


def test_job_stoesst_portal_sync_an():
    """
    B-2: Der Nachtlauf muss process_queue() aufrufen, sonst haengt die
    Uebertragung an einem Handgriff am naechsten Morgen.
    """
    quelltext = inspect.getsource(app_modul)
    stelle = quelltext.index("def _ablage_abgleich_job")
    ende = quelltext.index("scheduler.add_job", stelle)
    funktionskoerper = quelltext[stelle:ende]
    assert "process_queue" in funktionskoerper


def test_portal_sync_fehler_reisst_abgleich_nicht_mit():
    """
    Ein Fehler beim Versand darf den Abgleich nicht rueckwirkend als
    gescheitert erscheinen lassen - eigener try/except fuer process_queue.
    """
    quelltext = inspect.getsource(app_modul)
    stelle = quelltext.index("def _ablage_abgleich_job")
    ende = quelltext.index("scheduler.add_job", stelle)
    funktionskoerper = quelltext[stelle:ende]
    assert funktionskoerper.count("try:") >= 2
    assert funktionskoerper.count("except Exception:") >= 2
