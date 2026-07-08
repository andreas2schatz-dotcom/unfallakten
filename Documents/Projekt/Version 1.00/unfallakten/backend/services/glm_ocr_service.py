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
    base_url = os.environ.get("OCR_LLM_BASE_URL",
                              "http://host.docker.internal:1235/v1")
    # LM Studio verlangt einen (belanglosen) API-Key
    api_key = os.environ.get("OCR_LLM_API_KEY", "lm-studio-local")
    return OpenAI(base_url=base_url, api_key=api_key)


def _bild_zu_base64(bild) -> str:
    """PIL-Image -> data-URL fuer image_url-Content-Block."""
    buf = io.BytesIO()
    bild.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


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

    try:
        client = _make_client()
    except Exception as exc:
        logger.error("GLM-OCR: Client-Init fehlgeschlagen: %s", exc)
        return None

    modell = os.environ.get("OCR_LLM_MODEL", "glm-ocr")
    timeout_s = int(os.environ.get("OCR_LLM_TIMEOUT", "120"))

    try:
        antwort = client.chat.completions.create(
            model=modell,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": _bild_zu_base64(bild)}},
                ],
            }],
            temperature=0.0,
            max_tokens=4096,
            timeout=timeout_s,
        )
        return (antwort.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.error("GLM-OCR-Aufruf fehlgeschlagen: %s", exc)
        return None
