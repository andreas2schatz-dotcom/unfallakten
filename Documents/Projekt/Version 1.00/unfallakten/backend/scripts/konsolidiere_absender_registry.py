"""
S1.4 - Konsolidierungsskript: registry.json.marker -> email_absender_vorlagen.

Uebernimmt alle Marker-Eintraege mit ``domain``-Feld aus
``backend/config/registry.json`` in die Tabelle ``email_absender_vorlagen``.
Registry.json bleibt unveraendert im Alt-Pfad des Dispatchers (Doppel-
schreiben).

Regeln:
  * Idempotent: mehrfache Ausfuehrung ist unschaedlich.
  * Additiv: bestehende Zeilen werden nicht ueberschrieben. Fuer noch nicht
    gesetzte Felder (``klasse_kandidat``, ``ramicro_adressnr``, ...) wird
    ergaenzt, sofern der Registry-Eintrag einen Wert liefert.
  * ``vertrauensstufe`` fuer aus Registry uebernommene Domains: **2**
    (bekannter Absender, hoeher als Default-Seed = 1, niedriger als
    manuell verifiziert = 3).
  * Kategorie wird aus Registry-Klasse abgeleitet: ``versicherung``,
    ``gutachten`` (Spalten-CHECK erlaubt: gutachter, versicherung, gericht,
    sonstiges). Fuer ``gutachten``-Marker wird ``gutachter`` verwendet.

Direktaufruf::

    python -m backend.scripts.konsolidiere_absender_registry
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from ..db.database import get_connection

logger = logging.getLogger(__name__)

# Klasse aus registry.json -> Kategorie in email_absender_vorlagen.
# CHECK-Constraint erlaubt nur: gutachter, versicherung, gericht, sonstiges.
_KLASSE_ZU_KATEGORIE = {
    "versicherung": "versicherung",
    "gutachten":    "gutachter",
    "gericht":      "gericht",
}


def _registry_pfad() -> Path:
    return Path(__file__).parent.parent / "config" / "registry.json"


def _domain_eintraege() -> list[dict]:
    """
    Sammelt alle Marker-Eintraege mit ``domain``-Feld und dedupliziert
    ueber die Domain. Bei Doppelbelegung wird der erste Eintrag mit
    ``ramicro_adressnr`` bevorzugt (traegt die meisten Metadaten).
    """
    with open(_registry_pfad(), encoding="utf-8") as f:
        registry = json.load(f)

    marker = registry.get("marker", {}) or {}
    nach_domain: dict[str, dict] = {}

    for marker_key, val in marker.items():
        if not isinstance(val, dict):
            continue
        domain = (val.get("domain") or "").strip().lower()
        if not domain:
            continue

        eintrag = {
            "domain":           domain,
            "name":             val.get("lieferant") or marker_key,
            "klasse_kandidat":  val.get("klasse") or "sonstiges",
            "kuerzel":          val.get("kuerzel"),
            "ramicro_adressnr": val.get("ramicro_adressnr"),
        }

        bestehend = nach_domain.get(domain)
        if bestehend is None:
            nach_domain[domain] = eintrag
        else:
            # Nur ergaenzen — nie ueberschreiben.
            for k in ("name", "klasse_kandidat", "kuerzel", "ramicro_adressnr"):
                if not bestehend.get(k) and eintrag.get(k):
                    bestehend[k] = eintrag[k]

    return list(nach_domain.values())


def konsolidiere() -> dict:
    """
    Fuehrt die Konsolidierung durch und gibt einen Report zurueck.

    Report::

        {"neu": int, "ergaenzt": int, "unangetastet": int, "gesamt": int}
    """
    eintraege = _domain_eintraege()

    neu = ergaenzt = unangetastet = 0

    with get_connection() as conn:
        for e in eintraege:
            row = conn.execute(
                "SELECT id, klasse_kandidat, ramicro_adressnr, kuerzel, "
                "       versicherer_name, vertrauensstufe "
                "FROM email_absender_vorlagen WHERE LOWER(domain) = ?",
                (e["domain"],),
            ).fetchone()

            kategorie = _KLASSE_ZU_KATEGORIE.get(
                e["klasse_kandidat"], "sonstiges"
            )

            if row is None:
                conn.execute(
                    """
                    INSERT INTO email_absender_vorlagen
                        (name, domain, kategorie, klasse_kandidat,
                         ramicro_adressnr, kuerzel, versicherer_name,
                         vertrauensstufe, aktiv)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 2, 1)
                    """,
                    (
                        e["name"], e["domain"], kategorie,
                        e["klasse_kandidat"], e["ramicro_adressnr"],
                        e["kuerzel"],
                        # versicherer_name pflegt Alt-Pfad; bei versicherung
                        # sinnvoll vorbelegen.
                        e["name"] if kategorie == "versicherung" else None,
                    ),
                )
                neu += 1
                continue

            # Additives Ergaenzen — nie ueberschreiben.
            updates: dict[str, object] = {}
            if not row["klasse_kandidat"] and e["klasse_kandidat"]:
                updates["klasse_kandidat"] = e["klasse_kandidat"]
            if not row["ramicro_adressnr"] and e["ramicro_adressnr"]:
                updates["ramicro_adressnr"] = e["ramicro_adressnr"]
            if not row["kuerzel"] and e["kuerzel"]:
                updates["kuerzel"] = e["kuerzel"]
            if (not row["versicherer_name"] and kategorie == "versicherung"
                    and e["name"]):
                updates["versicherer_name"] = e["name"]
            # Vertrauensstufe nur nach oben schrauben (nie herabsetzen).
            if (row["vertrauensstufe"] or 0) < 2:
                updates["vertrauensstufe"] = 2

            if updates:
                set_clause = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE email_absender_vorlagen SET {set_clause} "
                    f"WHERE id = ?",
                    (*updates.values(), row["id"]),
                )
                ergaenzt += 1
            else:
                unangetastet += 1

    report = {
        "neu":          neu,
        "ergaenzt":     ergaenzt,
        "unangetastet": unangetastet,
        "gesamt":       len(eintraege),
    }
    logger.info(
        "Absender-Registry konsolidiert: %d neu, %d ergaenzt, "
        "%d unangetastet (gesamt: %d)",
        report["neu"], report["ergaenzt"],
        report["unangetastet"], report["gesamt"],
    )
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    r = konsolidiere()
    print(
        f"Absender-Registry konsolidiert: {r['neu']} neu, "
        f"{r['ergaenzt']} ergaenzt, {r['unangetastet']} unangetastet "
        f"(gesamt: {r['gesamt']})."
    )
    sys.exit(0)
