from types import SimpleNamespace
from ..models.akte import hole_akte_by_id


def _normiere_az(az: str):
    if not az:
        return None
    az = az.strip()
    if "/" in az:
        return az
    digits = az.replace(" ", "")
    if digits.isdigit() and len(digits) >= 3:
        return f"{digits[:-2]}/{digits[-2:]}"
    return az


def pruefe_akte(akte_id: str):
    az = _normiere_az(akte_id)
    if not az:
        return None
    akte = hole_akte_by_id(az)
    if akte:
        return akte
    # Akte existiert nur in RA-MICRO (noch nicht in SQLite): normiertes AZ zurückgeben
    if "/" in az:
        return SimpleNamespace(aktenzeichen=az)
    return None
