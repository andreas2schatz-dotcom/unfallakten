import os
import sys

PROJEKT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJEKT)

import pytest
from tools.gen_dokumentenklassen import render_alles

FRONTEND = os.path.join(PROJEKT, "frontend")
pytestmark = pytest.mark.skipif(
    not os.path.isdir(FRONTEND),
    reason="frontend/ nicht vorhanden (Backend-Container) — Guard laeuft auf Host/CI",
)


def test_generate_ist_aktuell():
    for rel_pfad, soll in render_alles().items():
        voll = os.path.join(PROJEKT, rel_pfad)
        with open(voll, "r", encoding="utf-8") as f:
            ist = f.read()
        assert ist == soll, (
            f"{rel_pfad} ist veraltet — 'py tools/gen_dokumentenklassen.py' "
            "ausfuehren und committen."
        )
