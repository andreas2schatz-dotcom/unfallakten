"""
Akten-Matching als Kandidatenliste mit Score (S1.7).

Sammelt Akten-Kandidaten aus SQLite (unfallakte + beteiligte) und optional
RA-Micro (read-only). Score-Staffel laut Pipeline-Refactoring-Plan:

    az_exakt          1.0    Aktenzeichen exakt gefunden
    az_basis          0.9    Aktenzeichen ohne SB-Kuerzel getroffen
    mandanten_mail    0.8    Bogen-Signal: Mandanten-Mail trifft mandant-Zeile
    kfz_mandant       0.8    Bogen-Signal: eigenes Kennzeichen trifft mandant-Zeile
    kfz               0.7    KFZ-Kennzeichen matcht einen Beteiligten (Altweg)
    unfalltag_name    0.7    Bogen-Signal: Unfalltag + Nachname treffen zusammen
    beteiligten_mail  0.6    Absender-Mail matcht einen Beteiligten (Altweg)
    unfalltag         0.5    Bogen-Signal: Unfalltag allein trifft
    kfz_gegner        0.5    Bogen-Signal: Gegner-Kennzeichen trifft gegner-Zeile
    name_unfalldatum  0.5    Name im Text + Unfalldatum-Datumsangabe im Text (Altweg)
    mandantenname     0.4    Nachname allein im Text (Altweg-Fallback)

Kein Auto-Zuordnen -- die Funktion liefert eine sortierte KANDIDATENLISTE.
Duplikate (dieselbe akte_az via mehrerer Signale) werden zum hoechsten
Score zusammengefasst. Die Review-UI entscheidet.

RA-Micro-Zugriff ist gekapselt hinter ``_suche_in_ramicro`` -- Fehler
werden geloggt und ignoriert, kein Crash bei RA-Micro-Ausfall.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from ..db.database import get_connection

logger = logging.getLogger(__name__)

SCORE_AZ_EXAKT = 1.0
SCORE_AZ_BASIS = 0.9
SCORE_KFZ = 0.7
SCORE_MAIL = 0.6
SCORE_NAME_DATUM = 0.5
# Schwaechstes Signal: Mandantenname im Text, ohne AZ/KFZ/Mail-Anker.
# Nur relevant wenn KEIN staerkeres Signal getroffen hat -- sonst wuerde
# es die Kandidatenliste verwaessern.
SCORE_MANDANTENNAME = 0.4

# Fragebogen-Signale (strukturierte Bogenfelder, kein Regex-Raten).
SCORE_MANDANTEN_MAIL = 0.8
SCORE_KFZ_MANDANT = 0.8
SCORE_UNFALLTAG_NAME = 0.7
SCORE_UNFALLTAG = 0.5
SCORE_KFZ_GEGNER = 0.5

# AZ-Kandidatenmuster: 1-4 Ziffern / 2-4 Ziffern, optional SB-Kuerzel
# (2-3 Grossbuchstaben), z.B. "31/21", "31/21AS", "285/26"
_AZ_MUSTER = re.compile(r"\b(\d{1,4}/\d{2,4}[A-Z]{0,3})\b")

# KFZ-Kandidatenmuster: 1-3 Grossbuchstaben (inkl. Umlaute -- TOEL, FUE, BOE,
# GOE), Bindestrich, 1-2 Buchstaben, optional Leerzeichen, 1-4 Ziffern, z.B.
# "OF-MU 1234", "F-XY 9876", "TOEL-A 123". Python-Unicode-\b sieht Umlaute als
# Wortzeichen, daher matcht \b weiterhin an der Wortgrenze vor dem Kennzeichen.
_KFZ_MUSTER = re.compile(r"\b([A-ZÄÖÜ]{1,3}-[A-Z]{1,2}\s?\d{1,4})\b")

# Datums-Muster: DD.MM.YYYY
_DATUM_MUSTER = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")


@dataclass
class AktenKandidat:
    akte_az: str
    score: float
    quelle: str
    treffer: str  # was matched: kanonisches AZ, Kennzeichen, Mail, Name
    bezeichnung: Optional[str] = None  # sAktenKurzBezeichnung, nur RA-Micro


def _az_basis(az: str) -> str:
    """Entfernt SB-Kuerzel: '31/21AS' -> '31/21'."""
    az = (az or "").strip().upper()
    if "/" in az:
        az = re.sub(r"[A-Z]{2,3}$", "", az).strip()
    return az


def _kfz_norm(kfz: str) -> str:
    return (kfz or "").upper().replace(" ", "").replace("-", "")


def _datum_zu_iso(datum: str) -> Optional[str]:
    """DD.MM.YYYY -> YYYY-MM-DD. None bei Fehler."""
    try:
        tag, monat, jahr = datum.split(".")
        return f"{jahr}-{monat}-{tag}"
    except (ValueError, AttributeError):
        return None


def _sammle_signale_mails(signale: Iterable[dict]) -> List[str]:
    ergebnis: List[str] = []
    for s in signale or ():
        if not isinstance(s, dict):
            continue
        mail = s.get("absender") or s.get("absender_email")
        if mail:
            mail = str(mail).lower().strip()
            if mail and mail not in ergebnis:
                ergebnis.append(mail)
    return ergebnis


def _sammle_signale_kfz(signale: Iterable[dict]) -> List[str]:
    ergebnis: List[str] = []
    for s in signale or ():
        if not isinstance(s, dict):
            continue
        for feld in ("kfz", "kfz_kennzeichen"):
            wert = s.get(feld)
            if wert:
                wert = str(wert).strip().upper()
                if wert and wert not in ergebnis:
                    ergebnis.append(wert)
    return ergebnis


def _sammle_signale_feld(signale: Iterable[dict], feld: str) -> List[str]:
    """Einzelnes Signalfeld ueber alle Zustellungen einsammeln."""
    ergebnis: List[str] = []
    for s in signale or ():
        if not isinstance(s, dict):
            continue
        wert = s.get(feld)
        if wert:
            wert = str(wert).strip()
            if wert and wert not in ergebnis:
                ergebnis.append(wert)
    return ergebnis


def _suche_az_in_sqlite(az_kandidaten: Sequence[str]) -> List[AktenKandidat]:
    """AZ-Treffer in unfallakte -- exakt (1.0) oder Basis (0.9)."""
    ergebnis: List[AktenKandidat] = []
    if not az_kandidaten:
        return ergebnis
    with get_connection() as conn:
        for kandidat in az_kandidaten:
            kandidat_up = kandidat.strip().upper()
            basis = _az_basis(kandidat_up)

            row = conn.execute(
                "SELECT az FROM unfallakte WHERE UPPER(az) = ?",
                (kandidat_up,),
            ).fetchone()
            if row:
                ergebnis.append(AktenKandidat(
                    akte_az=row["az"], score=SCORE_AZ_EXAKT,
                    quelle="az_exakt", treffer=kandidat,
                ))
                continue

            if basis and basis != kandidat_up:
                row = conn.execute(
                    "SELECT az FROM unfallakte WHERE UPPER(az) = ?",
                    (basis,),
                ).fetchone()
                if row:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["az"], score=SCORE_AZ_BASIS,
                        quelle="az_basis", treffer=kandidat,
                    ))
    return ergebnis


def _suche_kfz_in_sqlite(kfz_kandidaten: Sequence[str]) -> List[AktenKandidat]:
    ergebnis: List[AktenKandidat] = []
    if not kfz_kandidaten:
        return ergebnis
    with get_connection() as conn:
        for kfz in kfz_kandidaten:
            norm = _kfz_norm(kfz)
            if not norm:
                continue
            rows = conn.execute(
                "SELECT DISTINCT akte_id FROM beteiligte "
                "WHERE UPPER(REPLACE(REPLACE(kfz_kennzeichen,' ',''),'-','')) = ?",
                (norm,),
            ).fetchall()
            for row in rows:
                if row["akte_id"]:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["akte_id"], score=SCORE_KFZ,
                        quelle="kfz", treffer=kfz,
                    ))
    return ergebnis


def _suche_kfz_rolle_in_sqlite(kfz_kandidaten: Sequence[str], rolle: str,
                               score: float, quelle: str
                               ) -> List[AktenKandidat]:
    """Kennzeichen-Suche mit Rollenfilter (Fragebogen-Weg)."""
    ergebnis: List[AktenKandidat] = []
    if not kfz_kandidaten:
        return ergebnis
    with get_connection() as conn:
        for kfz in kfz_kandidaten:
            norm = _kfz_norm(kfz)
            if not norm:
                continue
            rows = conn.execute(
                "SELECT DISTINCT akte_id FROM beteiligte "
                "WHERE rolle = ? "
                "  AND UPPER(REPLACE(REPLACE(kfz_kennzeichen,' ',''),'-','')) = ?",
                (rolle, norm),
            ).fetchall()
            for row in rows:
                if row["akte_id"]:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["akte_id"], score=score,
                        quelle=quelle, treffer=kfz,
                    ))
    return ergebnis


def _suche_mail_rolle_in_sqlite(mails: Sequence[str], rolle: str,
                                score: float, quelle: str
                                ) -> List[AktenKandidat]:
    """Mail-Suche mit Rollenfilter (Fragebogen-Weg)."""
    ergebnis: List[AktenKandidat] = []
    if not mails:
        return ergebnis
    with get_connection() as conn:
        for mail in mails:
            m = mail.lower().strip()
            if not m:
                continue
            rows = conn.execute(
                "SELECT DISTINCT akte_id FROM beteiligte "
                "WHERE rolle = ? AND LOWER(email) = ?",
                (rolle, m),
            ).fetchall()
            for row in rows:
                if row["akte_id"]:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["akte_id"], score=score,
                        quelle=quelle, treffer=mail,
                    ))
    return ergebnis


def _suche_unfalltag_in_sqlite(tage: Sequence[str], nachnamen: Sequence[str]
                               ) -> List[AktenKandidat]:
    """Unfalltag aus dem Bogenfeld (ISO), optional verstaerkt durch den
    Nachnamen des Mandanten."""
    ergebnis: List[AktenKandidat] = []
    if not tage:
        return ergebnis
    namen_oben = [n.upper() for n in nachnamen if n]
    with get_connection() as conn:
        for tag in tage:
            rows = conn.execute(
                "SELECT DISTINCT u.az, b.name "
                "FROM unfallakte u "
                "LEFT JOIN beteiligte b ON b.akte_id = u.az "
                "  AND b.rolle = 'mandant' "
                "WHERE u.unfalldatum = ?",
                (tag,),
            ).fetchall()
            for row in rows:
                name_oben = (row["name"] or "").upper()
                if name_oben and name_oben in namen_oben:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["az"], score=SCORE_UNFALLTAG_NAME,
                        quelle="unfalltag_name",
                        treffer=f"{row['name']} + {tag}",
                    ))
                else:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["az"], score=SCORE_UNFALLTAG,
                        quelle="unfalltag", treffer=tag,
                    ))
    return ergebnis


def _suche_mail_in_sqlite(mails: Sequence[str]) -> List[AktenKandidat]:
    ergebnis: List[AktenKandidat] = []
    if not mails:
        return ergebnis
    with get_connection() as conn:
        for mail in mails:
            m = mail.lower().strip()
            if not m:
                continue
            rows = conn.execute(
                "SELECT DISTINCT akte_id FROM beteiligte "
                "WHERE LOWER(email) = ?",
                (m,),
            ).fetchall()
            for row in rows:
                if row["akte_id"]:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["akte_id"], score=SCORE_MAIL,
                        quelle="beteiligten_mail", treffer=mail,
                    ))
    return ergebnis


def _suche_name_und_datum_in_sqlite(text: str) -> List[AktenKandidat]:
    """Kombinations-Match: Name (aus beteiligte.name) UND Unfalldatum
    (aus unfallakte.unfalldatum) tauchen beide im Text auf.

    Der Match ist bewusst locker (Substring-Suche im Text), damit einfache
    Formulierungen erkannt werden. Score 0.5 = schwaechstes Signal.
    """
    if not text:
        return []
    text_upper = text.upper()

    datums_iso: List[str] = []
    for treffer in _DATUM_MUSTER.finditer(text):
        iso = _datum_zu_iso(treffer.group(1))
        if iso and iso not in datums_iso:
            datums_iso.append(iso)
    if not datums_iso:
        return []

    ergebnis: List[AktenKandidat] = []
    with get_connection() as conn:
        # Fuer jedes Datum die Akten holen, dann pruefen, ob Name im Text steht.
        for iso in datums_iso:
            rows = conn.execute(
                "SELECT DISTINCT u.az, b.name "
                "FROM unfallakte u JOIN beteiligte b ON b.akte_id = u.az "
                "WHERE u.unfalldatum = ? AND b.name IS NOT NULL "
                "  AND LENGTH(b.name) >= 3",
                (iso,),
            ).fetchall()
            for row in rows:
                name = row["name"]
                if name and name.upper() in text_upper:
                    ergebnis.append(AktenKandidat(
                        akte_az=row["az"], score=SCORE_NAME_DATUM,
                        quelle="name_unfalldatum",
                        treffer=f"{name} + {iso}",
                    ))
    return ergebnis


def _suche_mandantenname_in_sqlite(text: str) -> List[AktenKandidat]:
    """Fallback: nur Mandantenname (rolle='mandant') im Text.

    Wird vom Aufrufer nur bemueht, wenn KEIN staerkeres Signal (AZ, KFZ,
    Mail, Name+Datum) getroffen hat -- sonst wuerden reine Namens-Treffer
    die Kandidatenliste bei jedem Dokument aufblaehen.

    Nur Nachnamen mit >=3 Zeichen, Case-insensitive Substring-Match. Score
    0.4 (schwaechstes Signal).
    """
    if not text:
        return []
    text_upper = text.upper()
    ergebnis: List[AktenKandidat] = []
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT b.akte_id, b.name "
            "FROM beteiligte b "
            "WHERE b.rolle = 'mandant' AND b.name IS NOT NULL "
            "  AND LENGTH(b.name) >= 3"
        ).fetchall()
        for row in rows:
            name = (row["name"] or "").strip()
            akte_az = row["akte_id"]
            if not name or not akte_az:
                continue
            if name.upper() in text_upper:
                ergebnis.append(AktenKandidat(
                    akte_az=akte_az, score=SCORE_MANDANTENNAME,
                    quelle="mandantenname", treffer=name,
                ))
    return ergebnis


def _suche_in_ramicro(text: str,
                     az_kandidaten: Sequence[str],
                     kfz_kandidaten: Sequence[str],
                     mails: Sequence[str],
                     bogen_merkmale: Optional[dict] = None,
                     ) -> List[AktenKandidat]:
    """Bruecke zu RA-Micro (nur lesend).

    Zwei Wege: der bestehende Einzeltreffer ueber
    ``suche_akte_in_ramicro`` und -- bei einem Fragebogen -- die
    Kandidatensuche ueber die strukturierten Bogenmerkmale.
    """
    ergebnis: List[AktenKandidat] = []

    try:
        from ..ramicro.email_matching import suche_akte_in_ramicro
    except Exception as exc:
        logger.debug("RA-Micro-Modul nicht importierbar: %s", exc)
        return ergebnis

    az, erkannt, methode = suche_akte_in_ramicro(
        list(az_kandidaten), list(kfz_kandidaten),
        mails[0] if mails else "",
    )
    if az:
        score_map = {
            "aktenzeichen":     SCORE_AZ_EXAKT,
            "kfz_kennzeichen":  SCORE_KFZ,
            "absender_email":   SCORE_MAIL,
        }
        ergebnis.append(AktenKandidat(
            akte_az=az,
            score=score_map.get(methode or "", SCORE_AZ_BASIS),
            quelle=methode or "az_exakt",
            treffer=erkannt or "",
        ))

    if bogen_merkmale:
        try:
            from ..ramicro.email_matching import suche_kandidaten_in_ramicro
            bogen_scores = {
                "mandanten_mail": SCORE_MANDANTEN_MAIL,
                "kfz_mandant":    SCORE_KFZ_MANDANT,
                "unfalltag":      SCORE_UNFALLTAG,
                "kfz_gegner":     SCORE_KFZ_GEGNER,
                "nachname":       SCORE_MANDANTENNAME,
            }
            for az_tr, meth, treffer, bez in suche_kandidaten_in_ramicro(
                    bogen_merkmale):
                ergebnis.append(AktenKandidat(
                    akte_az=az_tr,
                    score=bogen_scores.get(meth, SCORE_MANDANTENNAME),
                    quelle=meth, treffer=treffer, bezeichnung=bez,
                ))
        except Exception as exc:
            logger.warning("RA-Micro-Bogensuche fehlgeschlagen: %s", exc)

    return ergebnis


def finde_kandidaten(text: str,
                    signale: Iterable[dict]) -> List[AktenKandidat]:
    """Sammelt Akten-Kandidaten aus SQLite + RA-Micro und liefert eine
    nach Score absteigend sortierte Liste. Duplikate werden zum hoechsten
    Score zusammengefasst.

    Score-Staffel (siehe Modul-Docstring fuer die vollstaendige Tabelle):
    az_exakt 1.0, az_basis 0.9, mandanten_mail/kfz_mandant 0.8,
    kfz/unfalltag_name 0.7, beteiligten_mail 0.6, unfalltag/kfz_gegner/
    name_unfalldatum 0.5, mandantenname 0.4.

    Args:
        text:    Volltext des Dokuments (Klassifikations-/Extraktions-Text).
        signale: Iterable von Zustellungs-Signal-Dicts (aus
                 zustellungen.signale_json). Liefert absender_mail und
                 kfz_kennzeichen (Altweg) sowie, bei Fragebogen-Signalen,
                 mandant_email, kfz_mandant, kfz_gegner, nachname und
                 unfalltag (rollenrichtig, kein Regex-Raten).
    """
    text = text or ""

    # AZ-Kandidaten: aus Text + Signalen
    az_aus_text = list(dict.fromkeys(
        m.group(1) for m in _AZ_MUSTER.finditer(text)
    ))
    az_aus_signalen: List[str] = []
    for s in signale or ():
        if isinstance(s, dict):
            for feld in ("az", "aktenzeichen", "erkannt_az"):
                wert = s.get(feld)
                if wert:
                    wert = str(wert).strip()
                    if wert and wert not in az_aus_signalen:
                        az_aus_signalen.append(wert)
    az_kandidaten = list(dict.fromkeys(az_aus_text + az_aus_signalen))

    # KFZ-Kandidaten: aus Text + Signalen
    kfz_aus_text = list(dict.fromkeys(
        m.group(1).upper() for m in _KFZ_MUSTER.finditer(text)
    ))
    kfz_kandidaten = list(dict.fromkeys(
        kfz_aus_text + _sammle_signale_kfz(signale)
    ))

    # Absender-Mails: nur aus Signalen (Text-Mails sind unzuverlaessig)
    mails = _sammle_signale_mails(signale)

    # Fragebogen-Signale: strukturierte Felder, kein Regex-Raten.
    mandanten_mails = _sammle_signale_feld(signale, "mandant_email")
    kfz_mandant = _sammle_signale_feld(signale, "kfz_mandant")
    kfz_gegner = _sammle_signale_feld(signale, "kfz_gegner")
    nachnamen = _sammle_signale_feld(signale, "nachname")
    unfalltage = _sammle_signale_feld(signale, "unfalltag")

    ergebnisse: List[AktenKandidat] = []
    ergebnisse.extend(_suche_az_in_sqlite(az_kandidaten))
    ergebnisse.extend(_suche_kfz_in_sqlite(kfz_kandidaten))
    ergebnisse.extend(_suche_mail_in_sqlite(mails))
    ergebnisse.extend(_suche_name_und_datum_in_sqlite(text))

    ergebnisse.extend(_suche_mail_rolle_in_sqlite(
        mandanten_mails, "mandant", SCORE_MANDANTEN_MAIL, "mandanten_mail"))
    ergebnisse.extend(_suche_kfz_rolle_in_sqlite(
        kfz_mandant, "mandant", SCORE_KFZ_MANDANT, "kfz_mandant"))
    ergebnisse.extend(_suche_kfz_rolle_in_sqlite(
        kfz_gegner, "gegner", SCORE_KFZ_GEGNER, "kfz_gegner"))
    ergebnisse.extend(_suche_unfalltag_in_sqlite(unfalltage, nachnamen))

    # Namens-Fallback: nur wenn KEIN staerkeres Signal getroffen hat.
    # Sonst wuerde jeder Text mit einem Mandanten-Nachnamen zusaetzliche
    # 0.4-Kandidaten produzieren -- unerwuenscht.
    if not ergebnisse:
        ergebnisse.extend(_suche_mandantenname_in_sqlite(text))

    bogen_merkmale = None
    for s in signale or ():
        if isinstance(s, dict) and s.get("dokument_art") == "fragebogen":
            bogen_merkmale = s
            break
    try:
        ergebnisse.extend(_suche_in_ramicro(
            text, az_kandidaten, kfz_kandidaten, mails, bogen_merkmale,
        ))
    except Exception as exc:
        logger.warning("RA-Micro-Kandidaten-Suche fehlgeschlagen: %s", exc)

    # Duplikate zusammenfassen: pro akte_az nur den hoechsten Score.
    beste: dict = {}
    for k in ergebnisse:
        vorher = beste.get(k.akte_az)
        if vorher is None or k.score > vorher.score:
            if vorher is not None and k.bezeichnung is None:
                k.bezeichnung = vorher.bezeichnung
            beste[k.akte_az] = k
        elif vorher.bezeichnung is None and k.bezeichnung:
            vorher.bezeichnung = k.bezeichnung

    return sorted(beste.values(), key=lambda k: k.score, reverse=True)
