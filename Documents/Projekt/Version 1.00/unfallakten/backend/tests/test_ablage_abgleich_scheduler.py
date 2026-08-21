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
    umfeld = quelltext[stelle:stelle + 600]
    assert "hour=3" in umfeld
    assert "minute=30" in umfeld
