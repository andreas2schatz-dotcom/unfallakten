from datetime import date, datetime


def parse_datum(s: str):
    """YYYY-MM-DD / DD.MM.YYYY / DD.MM.YY → date-Objekt oder None."""
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime((s or "").strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def datum_zu_iso(s: str, leer_als_heute: bool = False) -> str:
    """DD.MM.YYYY oder YYYY-MM-DD → YYYY-MM-DD.

    leer_als_heute: True  → leere Eingabe liefert heutiges Datum
                   False → leere Eingabe liefert ''
    Wirft ValueError bei nicht-leerem, ungültigem Format.
    """
    s = (s or "").strip()
    if not s:
        return datetime.today().strftime("%Y-%m-%d") if leer_als_heute else ""
    try:
        return datetime.strptime(s, "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        raise ValueError(f"Ungültiges Datumsformat: {s!r}. Erwartet: YYYY-MM-DD oder DD.MM.YYYY")


def iso_zu_ramicro(iso: str) -> str:
    """YYYY-MM-DD → DD.MM.YY (zweistelliges Jahr für RA-MICRO WDM-Format)."""
    try:
        if len(iso) == 10 and iso[4] == "-":
            p = iso.split("-")
            return f"{p[2]}.{p[1]}.{p[0][2:]}"
    except Exception:
        pass
    return iso
