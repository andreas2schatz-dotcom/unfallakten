"""
backend/word/sg_text_builder.py
================================
Gemeinsamer Schmerzensgeld-Textbaustein (PRD-29).

Wird von klage_service.py UND forderungsschreiben_wv.py verwendet,
damit der Schmerzensgeld-Block immer dieselbe Qualität hat.

Gibt ein Tupel (absaetze, beweis, vgl) zurück:
  absaetze  – list[str]: Fließtextabsätze
  beweis    – str: Beweisantritt-Zeile
  vgl       – str | None: Vergleichsurteil-Zeile (wenn sg_urteil_az gesetzt)
"""
from ..utils.datum import parse_datum as _parse_datum


def _eur_str(betrag: float) -> str:
    """Deutsche Währungsformatierung: 12.000,00 €"""
    return f"{betrag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _fmt_datum(s: str) -> str:
    """
    Konvertiert Datum in deutsches Format DD.MM.YYYY.
    Akzeptiert ISO (YYYY-MM-DD) und bereits deutsches Format (DD.MM.YYYY).
    Gibt den Eingabewert unverändert zurück wenn kein bekanntes Format erkannt wird.
    """
    if not s:
        return ""
    s = s.strip()
    # Bereits deutsches Format DD.MM.YYYY
    if len(s) == 10 and s[2] == "." and s[5] == ".":
        return s
    # ISO-Format YYYY-MM-DD
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return f"{s[8:10]}.{s[5:7]}.{s[0:4]}"
    return s




def baue_sg_abschnitt(ps_data: dict, kl_nom: str, sg_mind: float):
    """
    Baut den Schmerzensgeld-Abschnitt aus den personenschaden-Daten.

    Parameter:
        ps_data   – dict aus der personenschaden-Tabelle (oder None)
        kl_nom    – Nominativ des Klägers/der Klägerin, z.B. "Die Klägerin"
        sg_mind   – Mindestbetrag in Euro (0 = kein Mindestbetrag)

    Rückgabe: (absaetze: list[str], beweis: str, vgl: str|None)
    """
    beweis = "BEWEIS: Ärztliche Atteste und Befundberichte (Anlage K 2)"

    if not ps_data:
        # Fallback ohne Daten
        if sg_mind > 0:
            text = (f"{kl_nom} hat durch den Unfall Verletzungen erlitten, "
                    f"die ein Schmerzensgeld von mindestens {_eur_str(sg_mind)} rechtfertigen.")
        else:
            text = (f"{kl_nom} hat durch den Unfall Verletzungen erlitten, "
                    f"die ein angemessenes Schmerzensgeld rechtfertigen.")
        return [text], beweis, None

    verletzungen    = (ps_data.get("verletzungen_text") or "").strip()
    kh_von          = _fmt_datum(ps_data.get("krankenhaus_von")  or "")
    kh_bis          = _fmt_datum(ps_data.get("krankenhaus_bis")  or "")
    kh_name         = (ps_data.get("krankenhaus_name")  or "").strip()
    au_von          = _fmt_datum(ps_data.get("krank_von")        or "")
    au_bis          = _fmt_datum(ps_data.get("krank_bis")        or "")
    dauerfolgen     = bool(ps_data.get("dauerfolgen"))
    dauerfolgen_txt = (ps_data.get("dauerfolgen_text")  or "").strip()
    sg_text_ki      = (ps_data.get("sg_text")           or "").strip()
    sg_urteil_az    = (ps_data.get("sg_urteil_az")      or "").strip()
    sg_urteil_g     = (ps_data.get("sg_urteil_gericht") or "").strip()
    sg_urteil_b     = float(ps_data.get("sg_urteil_betrag") or 0)

    # Vergleichsurteil-Zeile
    vgl = None
    if sg_urteil_az:
        vgl = f"Vgl. {sg_urteil_g}, {sg_urteil_az}: {_eur_str(sg_urteil_b)}" if sg_urteil_g \
              else f"Vgl. {sg_urteil_az}: {_eur_str(sg_urteil_b)}"

    # Wenn KI-Text vom Anwalt bestätigt → hat Vorrang
    if sg_text_ki:
        return [sg_text_ki], beweis, vgl

    # Abschnitt aus Strukturdaten aufbauen
    absaetze = []

    # Absatz 1: Verletzungen
    if verletzungen:
        absaetze.append(
            f"{kl_nom} hat durch den Unfall folgende Verletzungen erlitten: {verletzungen}."
        )
    else:
        absaetze.append(
            f"{kl_nom} hat durch den Unfall Verletzungen erlitten."
        )

    # Absatz 2: Behandlung (Krankenhaus + AU)
    behandlung_teile = []
    if kh_von and kh_bis:
        kh_teil = f"Vom {kh_von} bis {kh_bis} war ein stationärer Aufenthalt"
        if kh_name:
            kh_teil += f" im {kh_name}"
        kh_teil += " erforderlich."
        behandlung_teile.append(kh_teil)
    if au_von and au_bis:
        behandlung_teile.append(
            f"Eine Arbeitsunfähigkeit bestand vom {au_von} bis {au_bis}."
        )
    if behandlung_teile:
        absaetze.append(" ".join(behandlung_teile))

    # Absatz 3: Dauerfolgen + Schmerzensgeld-Begründung
    schluss_teile = []
    if dauerfolgen:
        if dauerfolgen_txt:
            schluss_teile.append(f"Es bestehen unfallbedingte Dauerfolgen: {dauerfolgen_txt}.")
        else:
            schluss_teile.append("Es bestehen unfallbedingte Dauerfolgen.")

    if sg_mind > 0:
        schluss_teile.append(
            f"Die erlittenen Verletzungen und Beeinträchtigungen rechtfertigen "
            f"ein Schmerzensgeld von mindestens {_eur_str(sg_mind)}."
        )
    else:
        schluss_teile.append(
            "Die erlittenen Verletzungen und Beeinträchtigungen rechtfertigen "
            "ein angemessenes Schmerzensgeld."
        )

    if schluss_teile:
        absaetze.append(" ".join(schluss_teile))

    return absaetze, beweis, vgl
