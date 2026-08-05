"""
Abschluss-/Sachstandsbericht – Übersichts-Objekt (kanal-unabhängig)
====================================================================
Baut aus akte_daten (word_service._lade_akte_daten) ein reines dict,
das DOCX-Renderer und Vorschau-Endpoint speist. KEIN DB-Zugriff hier —
alle Daten kommen über akte_daten (hermetisch testbar).

Spec: docs/superpowers/specs/2026-08-05-abschlussbericht-design.md §6-§11
"""
from datetime import datetime

from ..word.abrechnungsuebersicht_service import (
    _normalise_key, _schadenpositionen_rows,
)


def _parse_datum(d):
    d = (d or "").strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(d[:10], fmt)
        except ValueError:
            continue
    return datetime.max


def _baue_pos_map_mit_verlauf(abrechnungen: list) -> tuple:
    """
    Wie _baue_pos_map (Option B: Summe der Zahlungs-Inkremente je Key),
    zusätzlich je Position: Einzelzahlungen (das "wann") + Kürzungsgrund.
    Roh-Key ra_gebuehren wird VOR der Normalisierung abgefangen (er ist
    kein Schadenersatz "für Sie") und separat summiert.

    Returns: (pos_map, ra_gebuehren_gezahlt)
      pos_map: key -> {reguliert, zahlungen: [{datum, betrag, versicherung}],
                       kuerzung_grund: str|None}
    """
    pos_map = {}
    ra_gebuehren = 0.0
    for ab in sorted(abrechnungen or [], key=lambda a: _parse_datum(a.get("datum"))):
        for p in (ab.get("positionen") or []):
            raw = p.get("position_key") or p.get("art") or "sonstiges"
            reg = p.get("betrag_reguliert")
            if reg is None:
                continue
            reg_f = round(float(reg), 2)
            if raw == "ra_gebuehren":
                ra_gebuehren = round(ra_gebuehren + reg_f, 2)
                continue
            key = _normalise_key(raw)
            eintrag = pos_map.setdefault(
                key, {"reguliert": 0.0, "zahlungen": [], "kuerzung_grund": None})
            eintrag["reguliert"] = round(eintrag["reguliert"] + reg_f, 2)
            eintrag["zahlungen"].append({
                "datum":        ab.get("datum") or "",
                "betrag":       reg_f,
                "versicherung": ab.get("versicherung") or "",
            })
            grund = (p.get("kuerzungsart_bezeichnung")
                     or p.get("kuerzung_freitext") or "").strip()
            if grund:
                eintrag["kuerzung_grund"] = grund
    return pos_map, ra_gebuehren


EMPFAENGER_DRITTE = {"sv_kosten", "mietwagenkosten", "abschleppkosten",
                     "standkosten", "kostennb"}
_FAHRZEUG_KEYS = {"rep_gutachten_netto", "rep_rechnung_netto",
                  "wiederbeschaffung", "restwert", "reparaturkosten"}


def _empfaenger_fuer(key: str) -> str:
    if key in EMPFAENGER_DRITTE:
        return "dritte"
    if key == "rep_rechnung_netto":
        return "dritte"
    return "mandant"


def _berechne_anwaltskosten_cta_plausi(akte_daten, ueb, ra_gebuehren):
    akte = akte_daten.get("akte") or {}
    abrechnungen = akte_daten.get("abrechnungen") or []
    kontext = akte_daten.get("gebuehren_kontext") or None

    rvg_betrag = None
    if kontext and float(kontext.get("streitwert") or 0) > 0:
        from ..word.klage_service import berechne_rvg
        rvg = berechne_rvg(
            float(kontext["streitwert"]),
            float(kontext.get("faktor") or 1.3),
            erstellt_am=kontext.get("erstellt_am"),
        )
        rvg_betrag = rvg["gesamt"]

    anwaltskosten = {
        "rvg_betrag":         rvg_betrag,
        "gezahlt_von_gegner": round(ra_gebuehren, 2),
        "getragen_von":       "gegner",
    }

    if abrechnungen:
        volle_haftung = all(
            float(ab.get("haftungsquote") or 100) >= 100 for ab in abrechnungen)
    else:
        volle_haftung = float(akte.get("haftungsquote") or 100) >= 100

    bewertung_cta = (
        ueb["modus"] == "abschluss"
        and ueb["schluss"]["typ"] == "endgueltig"
        and ueb["summen"]["differenz"] <= 0.01
        and volle_haftung
        and not any(p["status"] == "offen" for p in ueb["positionen"])
    )

    zeilensumme = round(ueb["summen"]["gezahlt"] + ra_gebuehren, 2)
    reguliert_gesamt = round(
        sum(float(ab.get("gesamt_reguliert") or 0) for ab in abrechnungen), 2)
    plausi = {
        "zeilensumme":      zeilensumme,
        "reguliert_gesamt": reguliert_gesamt,
        "differenz_ok":     abs(zeilensumme - reguliert_gesamt) <= 0.01,
    }
    return {"anwaltskosten": anwaltskosten,
            "bewertung_cta": bewertung_cta,
            "plausi": plausi}


def baue_abschluss_uebersicht(akte_daten: dict) -> dict:
    akte     = akte_daten.get("akte") or {}
    mandant  = akte_daten.get("mandant") or {}
    gegner   = akte_daten.get("gegner") or {}
    schaden  = akte_daten.get("schaden") or {}
    abrechnungen = akte_daten.get("abrechnungen") or []
    wdm_roh  = akte_daten.get("wdm_roh") or {}
    status   = akte_daten.get("abschluss_status") or {}

    vorsteuer = str(mandant.get("vorsteuer") or "N").strip().upper() in (
        "Y", "J", "JA", "1", "TRUE")

    pos_map, ra_gebuehren = _baue_pos_map_mit_verlauf(abrechnungen)
    rows = _schadenpositionen_rows(schaden, pos_map, vorsteuer)

    positionen = []
    s_gefordert = s_gezahlt = an_mandant = an_dritte = 0.0
    for r in rows:
        key, forderung = r["key"], r["forderung"]
        ist_abzug = r["ist_abzug"]
        info = pos_map.get(key) or {}
        gezahlt = r["reguliert"]
        vorz = -1.0 if ist_abzug else 1.0
        if ist_abzug:
            pos_status = "abzug"
        elif gezahlt is None:
            pos_status = "offen"
        elif abs(forderung) - gezahlt <= 0.005:
            pos_status = "voll"
        else:
            pos_status = "gekuerzt"
        empfaenger = _empfaenger_fuer(key)
        differenz = 0.0 if ist_abzug else round(abs(forderung) - (gezahlt or 0.0), 2)
        s_gefordert += vorz * abs(forderung)
        if gezahlt is not None:
            s_gezahlt += vorz * gezahlt
            if empfaenger == "mandant":
                an_mandant += vorz * gezahlt
            else:
                an_dritte += vorz * gezahlt
        positionen.append({
            "key":            key,
            "label":          r["label"],
            "kategorie":      "fahrzeug" if key in _FAHRZEUG_KEYS else "neben",
            "gefordert":      round(abs(forderung), 2),
            "gezahlt":        gezahlt,
            "differenz":      differenz,
            "kuerzung_grund": (info.get("kuerzung_grund")
                               if pos_status == "gekuerzt" else None),
            "empfaenger":     empfaenger,
            "status":         pos_status,
            "zahlungen":      info.get("zahlungen") or [],
        })

    schluss_typ = (status.get("schluss_typ") or "offen").strip() or "offen"
    modus = "sachstand" if schluss_typ == "offen" else "abschluss"

    def _wdm(k):
        return (wdm_roh.get(k) or "").strip()

    summen = {
        "gefordert": round(s_gefordert, 2),
        "gezahlt":   round(s_gezahlt, 2),
        "differenz": round(s_gefordert - s_gezahlt, 2),
        "an_mandant": round(an_mandant, 2),
        "an_dritte":  round(an_dritte, 2),
    }

    ueb = {
        "akte": {
            "az":         akte.get("aktenzeichen") or akte.get("az") or "",
            "unfalltag":  _wdm("varU-TAG") or akte.get("unfalldatum") or "",
            "unfallort":  _wdm("varU-ORT") or akte.get("unfallort") or "",
            "kz_mandant": _wdm("varM-KZ") or (mandant.get("kfz_kennzeichen") or ""),
            "kz_gegner":  _wdm("varG-KZ") or (gegner.get("kfz_kennzeichen") or ""),
            "gegner_versicherung": (gegner.get("versicherung")
                                    or (abrechnungen[0].get("versicherung")
                                        if abrechnungen else "") or ""),
        },
        "mandant": {
            "name":      " ".join(filter(None, [mandant.get("vorname"),
                                                mandant.get("name")])).strip()
                         or (mandant.get("firma") or ""),
            "anschrift": mandant.get("anschrift") or "",
            "plz_ort":   " ".join(filter(None, [mandant.get("plz"),
                                                mandant.get("ort")])).strip(),
            "anrede":    mandant.get("anrede") or "",
        },
        "modus":      modus,
        "positionen": positionen,
        "summen":     summen,
        "schluss": {
            "typ":                    schluss_typ,
            "text":                   status.get("schluss_text") or "",
            "verjaehrung_datum":      status.get("verjaehrung_datum") or None,
            "naechste_schritte_text": status.get("naechste_schritte_text") or "",
            "kuratiert_am":           status.get("kuratiert_am") or None,
            "kuratiert_von":          status.get("kuratiert_von") or None,
        },
    }
    ueb.update(_berechne_anwaltskosten_cta_plausi(
        akte_daten, ueb, ra_gebuehren))
    return ueb
