"""
GLM-OCR-Service (S1.6a Stub, F-01).

Wrappt eine OpenAI-kompatible Vision-API (LM Studio auf einem zweiten Endpoint,
Default: http://host.docker.internal:1235/v1). Liest ein PIL-Bild und schickt es
als base64-image_url an das Modell.

Feature-Flag: ``GLM_OCR_ENABLED``. Solange False (Default), gibt jede Anfrage
``None`` zurueck. Das erlaubt es der Pipeline in S1.6a, Tesseract als
Primaerquelle zu betreiben (v7-Vorgabe fuer die Uebergangszeit) und das
Modell erst in S1.6b/S1.7 als Primaerquelle zu aktivieren.

Prompt-Logging in LM Studio muss auf dem Host deaktiviert sein (Art.-9-Daten,
F-12 aus freigabe.md).
"""
from __future__ import annotations

import base64
import io
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("OCR_LLM_BASE_URL", "http://host.docker.internal:1235/v1").rstrip("/")

# ── Modell-Verwaltung (zur Laufzeit umschaltbar, analog llm_service.py) ────────
_DEFAULT_MODEL = os.environ.get("OCR_LLM_MODEL", "glm-ocr").strip()
_aktives_modell: str = _DEFAULT_MODEL

_VERFUEGBARE_MODELLE: list = [
    m.strip()
    for m in os.environ.get("OCR_LLM_MODELS", _DEFAULT_MODEL).split(",")
    if m.strip()
]
if _aktives_modell not in _VERFUEGBARE_MODELLE:
    _VERFUEGBARE_MODELLE.insert(0, _aktives_modell)


def get_active_model() -> str:
    """Gibt das aktuell aktive GLM-OCR-Modell zurueck."""
    return _aktives_modell


def set_active_model(model: str) -> None:
    """Setzt das aktive GLM-OCR-Modell zur Laufzeit (kein Container-Neustart noetig)."""
    global _aktives_modell
    _aktives_modell = model
    logger.info("GLM-OCR-Modell gewechselt zu: %s", model)


def get_available_models() -> list:
    """Gibt die Liste aller konfigurierten GLM-OCR-Modelle zurueck."""
    return list(_VERFUEGBARE_MODELLE)


def init_from_db() -> None:
    """Laedt das gespeicherte GLM-OCR-Modell aus der DB (App-Start, wie llm_service)."""
    try:
        from ..db.database import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT wert FROM konfiguration WHERE schluessel='glm_ocr_aktives_modell'"
            ).fetchone()
            if row and row["wert"]:
                set_active_model(row["wert"])
    except Exception as e:
        logger.warning("GLM-OCR-Modell-Init aus DB fehlgeschlagen (nicht kritisch): %s", e)


def is_available() -> bool:
    """True wenn der GLM-OCR-Endpunkt erreichbar ist (GET /models, Timeout 3s)."""
    try:
        import requests
        resp = requests.get(f"{_BASE_URL}/models", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _bool_env(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in ("true", "1", "yes", "on")


def ist_aktiviert() -> bool:
    """Prueft das Feature-Flag."""
    return _bool_env("GLM_OCR_ENABLED")


def _make_client():
    """Kapselt die openai-Client-Instanziierung, damit sie in Tests
    ueberschrieben werden kann."""
    from openai import OpenAI
    # LM Studio verlangt einen (belanglosen) API-Key
    api_key = os.environ.get("OCR_LLM_API_KEY", "lm-studio-local")
    return OpenAI(base_url=_BASE_URL, api_key=api_key)


def _bild_zu_base64(bild) -> str:
    """PIL-Image -> data-URL fuer image_url-Content-Block."""
    buf = io.BytesIO()
    bild.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _ocr_bild(bild, prompt: str, max_tokens: int = 4096,
              timeout_s: Optional[int] = None) -> Optional[str]:
    """Kapselt den eigentlichen Vision-Aufruf, unabhaengig vom Feature-Flag."""
    try:
        client = _make_client()
    except Exception as exc:
        logger.error("GLM-OCR: Client-Init fehlgeschlagen: %s", exc)
        return None

    if timeout_s is None:
        timeout_s = int(os.environ.get("OCR_LLM_TIMEOUT", "120"))

    try:
        antwort = client.chat.completions.create(
            model=get_active_model(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": _bild_zu_base64(bild)}},
                ],
            }],
            temperature=0.0,
            max_tokens=max_tokens,
            timeout=timeout_s,
        )
        return (antwort.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.error("GLM-OCR-Aufruf fehlgeschlagen: %s", exc)
        return None


def glm_ocr_seite(bild, lang: str = "de",
                  prompt: Optional[str] = None) -> Optional[str]:
    """OCR einer Seite via Vision-LLM.

    Rueckgabe:
      * ``None`` wenn Feature-Flag GLM_OCR_ENABLED nicht gesetzt (Default).
      * Erkannter Text als String, sonst.

    Fehler (Netzwerk, Modell, Timeout) werden geloggt und liefern ``None``.
    Kein Retry hier -- der Retry passiert eine Ebene hoeher in der Pipeline
    ueber die Queue (versuch_zaehler + Backoff).
    """
    if not ist_aktiviert():
        return None

    if prompt is None:
        prompt = (
            "Extrahiere den kompletten Text der Seite in Lese-Reihenfolge. "
            "Nur der Text, keine Erklaerungen. Deutsch."
            if lang == "de" else
            "Extract the full page text in reading order. Text only."
        )

    return _ocr_bild(bild, prompt)


def test_verbindung() -> Optional[str]:
    """Verbindungstest fuer die Einstellungen-Seite (analog llm_service.chat()).

    Erzeugt ein Testbild mit bekanntem Text und schickt es durch den
    Vision-Endpunkt. Ignoriert bewusst das Feature-Flag GLM_OCR_ENABLED,
    damit der Verbindungstest auch vor der Aktivierung moeglich ist.
    """
    from PIL import Image, ImageDraw
    bild = Image.new("RGB", (400, 100), "white")
    ImageDraw.Draw(bild).text((10, 35), "Testverbindung 12345", fill="black")
    return _ocr_bild(
        bild,
        "Extrahiere den Text im Bild. Nur der Text, keine Erklaerungen.",
        max_tokens=256,
        timeout_s=30,
    )
