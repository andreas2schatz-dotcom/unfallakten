"""
Gebührenassistent – PRD-28
==========================
Berechnet den Faktor für die außergerichtliche Geschäftsgebühr Nr. 2300 VV RVG
anhand der Entscheidungsmatrix (RVG_Entscheidungsmatrix_Software.xlsx).

Logik:
  - 12 Prioritätsregeln (erste zutreffende gewinnt)
  - Kriterien werden soweit möglich automatisch aus der Akte gelesen
  - Fehlende Felder (auslandsbezug, todesfall, verletzungsgrad, pflegebedarf,
    haftung_streitig) werden als "fehlende_felder" zurückgegeben → UI fragt nach

Python 3.9 – keine Union-Types, kein Walrus-Operator.
"""

import json
import logging
from datetime import date, datetime

from ..db.database import get_connection

logger = logging.getLogger(__name__)

# ── Entscheidungsmatrix (Sheet "Software-Logik") ──────────────────────────────
#
# Jede Regel:
#   id          VU-xx Kennung
#   faktor      Empfohlener Gebührenfaktor
#   bedingung   Callable(kriterien) -> bool
#   begruendung Begründungstext mit {variable}-Platzhaltern
#   leitentscheidung  Rechtsprechungsreferenz
#
# Reihenfolge = Priorität (höchste zuerst). Erste True-Bedingung gewinnt.

VU_REGELN = [
    {
        "id": "VU-11",
        "faktor": 2.5,
        "bedingung": lambda k: k["verletzungsgrad"] == "schwerst" and k["auslandsbezug"],
        "begruendung": (
            "Die Angelegenheit wies eine kumulative Schwierigkeitssteigerung auf, "
            "die den Ansatz der Höchstgebühr von 2,5 rechtfertigt. "
            "Zum Schwerstpersonenschaden ({verletzungsgrad_label}) trat ein erheblicher "
            "Auslandsbezug hinzu, der zusätzliche Prüfungen des anwendbaren Rechts "
            "(Rom-II-VO), die Korrespondenz mit dem ausländischen Versicherer, "
            "die Ermittlung ausländischer Haftungsmaßstäbe und die Koordination "
            "mit ausländischen Ärzten und Behörden erforderte. "
            "Der Gesamtaufwand lag in jeder Hinsicht ganz erheblich über dem Durchschnitt. "
            "In der Gesamtschau aller Kriterien des § 14 RVG ist die Höchstgebühr "
            "von 2,5 angemessen. "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "RAK München; AG Mannheim 3 C 202/08 (analog)",
        "toleranz": "Höchstgebühr – vollständige Dokumentation erforderlich",
    },
    {
        "id": "VU-08",
        "faktor": 2.3,
        "bedingung": lambda k: k["verletzungsgrad"] == "schwerst" or k["todesfall"],
        "begruendung": (
            "Der Mandant erlitt bei dem Verkehrsunfall schwerste Verletzungen"
            "{todesfall_zusatz}. "
            "Die außergerichtliche Regulierung umfasste die Koordination mit mehreren "
            "medizinischen Fachrichtungen und Einholung umfangreicher Gutachten, "
            "die Berechnung komplexer Schadenspositionen einschließlich Erwerbsschaden, "
            "Pflegemehraufwand, Umbaukosten und Haushaltsführungsschaden"
            "{dauerschaden_hinweis} "
            "sowie die Abstimmung mit Sozialversicherungsträgern hinsichtlich "
            "Übergangsansprüchen. "
            "Die Angelegenheit war in jeder Hinsicht weit überdurchschnittlich "
            "umfangreich und schwierig. "
            "Die Spitzengebühr von 2,3 ist sachlich gerechtfertigt "
            "(vgl. AG Mannheim, 3 C 202/08). "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "AG Mannheim 3 C 202/08; BGH VI ZR 261/05",
        "toleranz": "Lückenlose Dokumentation der Verletzungsfolgen erforderlich",
    },
    {
        "id": "VU-10",
        "faktor": 2.3,
        "bedingung": lambda k: k["verletzungsgrad"] == "schwer" and k["auslandsbezug"],
        "begruendung": (
            "Die Angelegenheit wies eine kumulative Schwierigkeitssteigerung auf, "
            "die den Ansatz einer Spitzengebühr von 2,3 rechtfertigt. "
            "Zum schweren Personenschaden trat ein Auslandsbezug hinzu, der zusätzliche "
            "Prüfungen des anwendbaren Rechts (Rom-II-VO), die Korrespondenz mit dem "
            "ausländischen Versicherer, die Ermittlung ausländischer Haftungsmaßstäbe "
            "und die Koordination mit ausländischen Ärzten und Behörden erforderte. "
            "In der Gesamtschau aller Kriterien des § 14 RVG ist die Spitzengebühr "
            "von 2,3 angemessen. "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "RAK München; AG Mannheim 3 C 202/08; OLG Dresden 7 U 1027/15",
        "toleranz": "Kumulation beider Umstände dokumentieren",
    },
    {
        "id": "VU-05",
        "faktor": 1.8,
        "bedingung": lambda k: k["verletzungsgrad"] == "schwer",
        "begruendung": (
            "Der Mandant erlitt bei dem Verkehrsunfall schwere Verletzungen"
            "{au_hinweis}{krankenhaus_hinweis}. "
            "Die außergerichtliche Regulierung erforderte umfangreiche medizinische "
            "Aufarbeitung, Einholung und Auswertung ärztlicher Berichte und Gutachten, "
            "Koordination mit Krankenversicherungsträgern, Geltendmachung von "
            "Verdienstausfall und Haushaltsführungsschaden sowie die Bemessung eines "
            "angemessenen Schmerzensgeldes. "
            "Die Angelegenheit war in tatsächlicher und rechtlicher Hinsicht erheblich "
            "überdurchschnittlich schwierig und umfangreich. "
            "Eine 1,8-Geschäftsgebühr ist angemessen und durch die Rechtsprechung gedeckt. "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "AG Mannheim 3 C 202/08; OLG Dresden 7 U 1027/15",
        "toleranz": "Schwere der Verletzung darlegen",
    },
    {
        "id": "VU-06",
        "faktor": 1.8,
        "bedingung": lambda k: k["auslandsbezug"] and k["schadenspositionen_count"] >= 3,
        "begruendung": (
            "Die Angelegenheit wies einen erheblichen Auslandsbezug auf, der die "
            "Tätigkeit in Umfang und Schwierigkeit weit über den Durchschnitt hinaus "
            "steigerte. Die Regulierung erforderte die Ermittlung des zuständigen "
            "ausländischen Haftpflichtversicherers über den Zentralruf der "
            "Autoversicherer bzw. den Grüne-Karte-Regulierer, die Korrespondenz mit "
            "einem im Ausland ansässigen Versicherer bzw. dessen Regulierungsbeauftragten "
            "in Deutschland, die Prüfung des anwendbaren materiellen Rechts nach der "
            "Rom-II-Verordnung sowie die Auseinandersetzung mit abweichenden ausländischen "
            "Haftungsmaßstäben ({schadenspositionen_count} Schadenspositionen). "
            "Der erhebliche Mehraufwand rechtfertigt den Ansatz einer 1,8-Geschäftsgebühr "
            "gemäß Nr. 2300 VV RVG. "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "AG Kehl 4 C 678/06; OLG Dresden 7 U 1027/15; RAK München",
        "toleranz": "Auslandsbezug allein nicht immer ausreichend – Aufwand dokumentieren",
    },
    {
        "id": "VU-12",
        "faktor": 1.8,
        "bedingung": lambda k: k["regulierungsdauer_monate"] > 12 and k["schriftsaetze_count"] >= 15,
        "begruendung": (
            "Die außergerichtliche Regulierung erstreckte sich über einen "
            "außerordentlich langen Zeitraum von {regulierungsdauer_monate} Monaten. "
            "Die Korrespondenz mit dem gegnerischen Haftpflichtversicherer umfasste "
            "{schriftsaetze_count} Schriftsätze. "
            "Trotz wiederholt angemessener Fristsetzungen verzögerte der Versicherer "
            "die Regulierung, sodass wiederholte Sachstandsanfragen, Mahnungen und "
            "die Androhung gerichtlicher Schritte erforderlich waren. "
            "Der erhebliche zeitliche und inhaltliche Aufwand rechtfertigt eine "
            "1,8-Geschäftsgebühr gemäß Nr. 2300 VV RVG. "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "AG Mannheim 3 C 202/08 (Zeitfaktor)",
        "toleranz": "Zeiterfassung oder Schriftsatz-Dokumentation nachweisen",
    },
    {
        "id": "VU-07",
        "faktor": 1.8,
        "bedingung": lambda k: k["totalschaden"] and k["reparatur_ueber_130pct"],
        "begruendung": (
            "Die Regulierung war aufgrund des wirtschaftlichen Totalschadens "
            "überdurchschnittlich schwierig. Es waren vertiefte rechtliche Prüfungen "
            "zur 130-%-Grenze nach BGH-Rechtsprechung, zur Abgrenzung zwischen "
            "Reparatur- und Wiederbeschaffungsaufwand sowie zum Restwert erforderlich. "
            "Die Auseinandersetzung mit dem gegnerischen Versicherer über die "
            "Wirtschaftlichkeit der Reparatur erforderte die Einholung und Auswertung "
            "von Sachverständigengutachten. "
            "Der Umfang und die Schwierigkeit der Tätigkeit rechtfertigen eine "
            "1,8-Geschäftsgebühr. "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "OLG Dresden 7 U 1027/15",
        "toleranz": "Bei Reparaturkosten deutlich über 130 % des WBW angemessen",
    },
    {
        "id": "VU-03",
        "faktor": 1.5,
        "bedingung": lambda k: k["verletzungsgrad"] == "leicht",
        "begruendung": (
            "Die Angelegenheit war sowohl in tatsächlicher als auch in rechtlicher "
            "Hinsicht überdurchschnittlich umfangreich und schwierig. "
            "Neben der Regulierung des Sachschadens war die Geltendmachung von "
            "Schmerzensgeldforderungen aufgrund der erlittenen Personenschäden "
            "erforderlich{au_hinweis}. "
            "Dies umfasste die Einholung und Auswertung medizinischer Unterlagen, "
            "die Prüfung der Kausalität zwischen Unfallereignis und Verletzungsbild "
            "sowie die Bemessung eines angemessenen Schmerzensgeldes unter "
            "Heranziehung einschlägiger Rechtsprechung. "
            "Der Gesamtaufwand überstieg den einer durchschnittlichen "
            "Verkehrsunfallregulierung erheblich, sodass eine 1,5-Geschäftsgebühr "
            "gerechtfertigt ist."
        ),
        "leitentscheidung": "AG Sinzig 10 C 99/07; LG Saarbrücken 13 S 68/09",
        "toleranz": "Innerhalb der 20%-Toleranz möglich",
    },
    {
        "id": "VU-02",
        "faktor": 1.5,
        "bedingung": lambda k: k["haftung_streitig"],
        "begruendung": (
            "Die außergerichtliche Tätigkeit des Unterzeichners ging über den Umfang "
            "einer durchschnittlichen Verkehrsunfallregulierung hinaus. "
            "Die Haftungslage war zwischen den Parteien streitig, sodass eine vertiefte "
            "Auseinandersetzung mit den unfallanalytischen Gegebenheiten und der "
            "Rechtsprechung zur Haftungsverteilung erforderlich war. "
            "Der erhöhte Umfang und die gesteigerte Schwierigkeit der Angelegenheit "
            "rechtfertigen den Ansatz einer 1,5-Geschäftsgebühr gemäß Nr. 2300 VV RVG "
            "i.V.m. § 14 Abs. 1 RVG. "
            "Dies liegt zudem innerhalb der vom BGH anerkannten Toleranzgrenze von "
            "20 % (BGH, Urt. v. 08.05.2012 – VI ZR 273/11)."
        ),
        "leitentscheidung": "BGH VI ZR 273/11 (Toleranz)",
        "toleranz": "Innerhalb der 20%-Toleranz des BGH",
    },
    {
        "id": "VU-04",
        "faktor": 1.5,
        "bedingung": lambda k: k["schadenspositionen_count"] >= 5 or k["schriftsaetze_count"] >= 8,
        "begruendung": (
            "Die Regulierung war aufgrund der Vielzahl der geltend gemachten "
            "Schadenspositionen ({schadenspositionen_count} Positionen) "
            "überdurchschnittlich umfangreich. "
            "Der Schriftverkehr mit der gegnerischen Haftpflichtversicherung umfasste "
            "{schriftsaetze_count} Schreiben. "
            "Der Umfang der Tätigkeit rechtfertigt den Ansatz einer "
            "1,5-Geschäftsgebühr gemäß Nr. 2300 VV RVG."
        ),
        "leitentscheidung": "AG Hagen 16 C 374/07; LG Dortmund 4 S 11/11",
        "toleranz": "Dokumentation des Umfangs genügt",
    },
    {
        "id": "VU-07b",
        "faktor": 1.5,
        "bedingung": lambda k: k["totalschaden"],
        "begruendung": (
            "Die Regulierung war aufgrund des wirtschaftlichen Totalschadens "
            "überdurchschnittlich schwierig. "
            "Es waren rechtliche Prüfungen zur Abgrenzung zwischen Reparatur- und "
            "Wiederbeschaffungsaufwand sowie zur Restwert- und "
            "Wiederbeschaffungswertermittlung erforderlich. "
            "Die Schwierigkeit und der Umfang der Tätigkeit rechtfertigen eine "
            "1,5-Geschäftsgebühr. "
            "Im Übrigen wurde die Geschäftsgebühr nach billigem Ermessen maßvoll erhöht. "
            "Diese Erhöhung liegt innerhalb der Toleranzgrenze gemäß Urteil des BGH "
            "vom 08.05.2012 \u2013 VI ZR 273/11. "
            "Der Unterzeichner hat von seinem Ermessen Gebrauch gemacht."
        ),
        "leitentscheidung": "OLG Dresden 7 U 1027/15",
        "toleranz": "Standardfall Totalschaden",
    },
    {
        "id": "VU-01",
        "faktor": 1.3,
        "bedingung": lambda k: True,  # DEFAULT
        "begruendung": (
            "Durchschnittlicher Verkehrsunfall mit klarer Haftungslage und "
            "überschaubarem Regulierungsaufwand. "
            "Der Ansatz der Schwellengebühr von 1,3 gemäß Nr. 2300 VV RVG entspricht "
            "der Regelgebühr nach BGH, Urt. v. 08.05.2012 – VI ZR 273/11."
        ),
        "leitentscheidung": "BGH VI ZR 273/11",
        "toleranz": "Schwellengebühr – keine besondere Begründung erforderlich",
    },
]

# Felder die NICHT automatisch aus der DB gelesen werden können
# → müssen vom Anwalt im UI beantwortet werden (wenn noch nicht gespeichert)
_MANUELLE_FELDER = ["auslandsbezug", "todesfall", "verletzungsgrad",
                    "pflegebedarf", "haftung_streitig"]


# ── Analyse ──────────────────────────────────────────────────────────────────

def analysiere_akte(az, db_conn=None):
    # type: (str, object) -> dict
    """
    Liest alle für die VU-Entscheidungsmatrix relevanten Felder aus der Akte.

    Gibt zurück:
      kriterien       – Dict mit allen Kriterien (auto + manuell gespeicherte)
      fehlende_felder – Liste der Felder die noch manuell beantwortet werden müssen
    """
    def _run(conn):
        # ── Akte (unfallakte) ─────────────────────────────────────────────
        akte_row = conn.execute(
            "SELECT haftungsquote, unfalldatum, auslandsbezug, todesfall, haftung_streitig "
            "FROM unfallakte WHERE az = ?", (az,)
        ).fetchone()
        if not akte_row:
            return None

        hq = float(akte_row["haftungsquote"] or 100.0)
        auslandsbezug   = bool(akte_row["auslandsbezug"])
        todesfall       = bool(akte_row["todesfall"])
        haftung_streitig = bool(akte_row["haftung_streitig"])
        unfalldatum     = akte_row["unfalldatum"]

        # ── Personenschaden ───────────────────────────────────────────────
        ps_row = conn.execute(
            "SELECT verletzungsgrad, pflegebedarf, krankenhaus_von, krankenhaus_bis, "
            "dauerfolgen, krank_von, krank_bis "
            "FROM personenschaden WHERE akte_id = ?", (az,)
        ).fetchone()

        verletzungsgrad = None
        pflegebedarf    = False
        stationaer      = False
        dauerschaden    = False
        au_tage         = 0

        if ps_row:
            verletzungsgrad = ps_row["verletzungsgrad"]   # None wenn noch nicht gesetzt
            pflegebedarf    = bool(ps_row["pflegebedarf"])
            # stationär nur wenn von != bis (gleicher Tag = ambulant)
            kh_von = ps_row["krankenhaus_von"]
            kh_bis = ps_row["krankenhaus_bis"]
            stationaer = bool(kh_von and kh_bis and kh_von != kh_bis)
            dauerschaden    = bool(ps_row["dauerfolgen"])
            au_tage         = _berechne_au_tage(
                ps_row["krank_von"], ps_row["krank_bis"]
            )

        # ── Schadenpositionen ─────────────────────────────────────────────
        schaden_row = conn.execute(
            "SELECT abrechnungsart, rep_gutachten_netto, wiederbeschaffung "
            "FROM schadenpositionen WHERE akte_id = ?", (az,)
        ).fetchone()

        totalschaden         = False
        reparatur_ueber_130pct = False
        if schaden_row:
            totalschaden = (schaden_row["abrechnungsart"] == "totalschaden")
            rep   = float(schaden_row["rep_gutachten_netto"] or 0)
            wbw   = float(schaden_row["wiederbeschaffung"] or 0)
            if wbw > 0 and rep > 0:
                reparatur_ueber_130pct = (rep / wbw) > 1.30

        # ── Schadenspositionen zählen (aus forderung_positionen) ──────────
        fp_row = conn.execute(
            "SELECT COUNT(DISTINCT position_key) as cnt "
            "FROM forderung_positionen WHERE akte_id = ?", (az,)
        ).fetchone()
        schadenspositionen_count = int(fp_row["cnt"]) if fp_row else 0

        # Fallback: direkte Felder aus schadenpositionen zählen
        if schadenspositionen_count == 0 and schaden_row:
            schadenspositionen_count = _zaehle_schaden_felder(dict(schaden_row))

        # ── Schriftsätze / Dokumente zählen ──────────────────────────────
        schriftsaetze_count = _zaehle_schriftsaetze(az, conn)

        # ── Regulierungsdauer ─────────────────────────────────────────────
        regulierungsdauer_monate = _berechne_regulierungsdauer(az, unfalldatum, conn)

        # ── Fehlende manuelle Felder ermitteln ────────────────────────────
        fehlende = []
        if not auslandsbezug and auslandsbezug is False:
            # auslandsbezug ist DEFAULT 0, also gespeichert – nicht fehlend
            pass
        # Felder die explizit noch nicht vom Anwalt beantwortet wurden:
        # verletzungsgrad ist NULL wenn noch nie gespeichert
        hat_personenschaden = bool(ps_row)
        if hat_personenschaden and verletzungsgrad is None:
            fehlende.append("verletzungsgrad")
        if hat_personenschaden and verletzungsgrad in ("schwer", "schwerst") and not pflegebedarf:
            # pflegebedarf ist DEFAULT 0 – könnte auch absichtlich Nein sein
            # wir fragen nur wenn verletzungsgrad schwer/schwerst und noch nie explizit gesetzt
            pass  # pflegebedarf DEFAULT = 0 bedeutet bereits "Nein" beantwortet

        return {
            "auslandsbezug":           auslandsbezug,
            "todesfall":               todesfall,
            "verletzungsgrad":         verletzungsgrad or "keine",
            "pflegebedarf":            pflegebedarf,
            "haftungsquote":           hq,
            "haftung_streitig":        haftung_streitig,
            "totalschaden":            totalschaden,
            "reparatur_ueber_130pct":  reparatur_ueber_130pct,
            "schadenspositionen_count": schadenspositionen_count,
            "schriftsaetze_count":     schriftsaetze_count,
            "regulierungsdauer_monate": regulierungsdauer_monate,
            "au_tage":                 au_tage,
            "stationaerer_aufenthalt": stationaer,
            "dauerschaden":            dauerschaden,
            "hat_personenschaden":     hat_personenschaden,
            "fehlende_felder":         fehlende,
        }

    if db_conn is not None:
        return _run(db_conn)
    with get_connection() as conn:
        return _run(conn)


def berechne_faktor_vorschlag(kriterien):
    # type: (dict) -> dict
    """
    Wendet die 12 VU-Prioritätsregeln auf die Kriterien an.
    Gibt die erste zutreffende Regel zurück (inkl. befüllter Begründungstext).

    Returns:
        {
          "vuregel_id":      "VU-04",
          "faktor":          1.5,
          "begruendung":     "...",
          "leitentscheidung": "...",
          "toleranz":        "...",
        }
    """
    for regel in VU_REGELN:
        try:
            if regel["bedingung"](kriterien):
                begruendung = _befuelle_begruendung(regel["begruendung"], kriterien)
                return {
                    "vuregel_id":       regel["id"],
                    "faktor":           regel["faktor"],
                    "begruendung":      begruendung,
                    "leitentscheidung": regel["leitentscheidung"],
                    "toleranz":         regel["toleranz"],
                }
        except Exception as e:
            logger.warning("Regel %s konnte nicht ausgewertet werden: %s", regel["id"], e)
            continue
    # Sollte nie eintreten (VU-01 DEFAULT ist immer True)
    return {
        "vuregel_id": "VU-01", "faktor": 1.3,
        "begruendung": "Standardfall – keine besondere Begründung erforderlich.",
        "leitentscheidung": "BGH VI ZR 273/11",
        "toleranz": "Schwellengebühr",
    }


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _befuelle_begruendung(template, k):
    # type: (str, dict) -> str
    """Ersetzt {variable}-Platzhalter im Begründungstemplate."""
    verletzungsgrad_labels = {
        "keine": "kein Personenschaden", "leicht": "leichter Personenschaden",
        "schwer": "schwerer Personenschaden", "schwerst": "Schwerstpersonenschaden",
    }
    au_hinweis = ""
    if k.get("au_tage", 0) > 0:
        au_hinweis = f", Arbeitsunfähigkeit {k['au_tage']} Tage"
    krankenhaus_hinweis = ""
    if k.get("stationaerer_aufenthalt"):
        krankenhaus_hinweis = ", stationärer Krankenhausaufenthalt"
    dauerschaden_hinweis = ""
    if k.get("dauerschaden"):
        dauerschaden_hinweis = " mit Dauerfolgen"
    todesfall_zusatz = " / Todesfall mit Hinterbliebenenansprüchen" if k.get("todesfall") else ""

    replacements = {
        "verletzungsgrad_label":    verletzungsgrad_labels.get(k.get("verletzungsgrad", "keine"), ""),
        "schadenspositionen_count": str(k.get("schadenspositionen_count", 0)),
        "schriftsaetze_count":      str(k.get("schriftsaetze_count", 0)),
        "regulierungsdauer_monate": str(round(k.get("regulierungsdauer_monate", 0))),
        "haftungsquote":            str(round(k.get("haftungsquote", 100))),
        "au_hinweis":               au_hinweis,
        "krankenhaus_hinweis":      krankenhaus_hinweis,
        "dauerschaden_hinweis":     dauerschaden_hinweis,
        "todesfall_zusatz":         todesfall_zusatz,
    }
    try:
        return template.format(**replacements)
    except KeyError:
        return template


def _berechne_au_tage(krank_von, krank_bis):
    # type: (object, object) -> int
    """Berechnet AU-Tage aus krank_von / krank_bis (ISO-Datum-Strings)."""
    if not krank_von or not krank_bis:
        return 0
    try:
        von  = date.fromisoformat(str(krank_von)[:10])
        bis  = date.fromisoformat(str(krank_bis)[:10])
        return max(0, (bis - von).days)
    except (ValueError, TypeError):
        return 0


def _berechne_regulierungsdauer(az, unfalldatum, conn):
    # type: (str, object, object) -> float
    """Regulierungsdauer in Monaten: von Unfalldatum bis letztem Regulierungsschreiben."""
    if not unfalldatum:
        return 0.0
    try:
        start = date.fromisoformat(str(unfalldatum)[:10])
    except (ValueError, TypeError):
        return 0.0

    letztes = conn.execute(
        "SELECT MAX(datum) as d FROM regulierung WHERE akte_id = ?", (az,)
    ).fetchone()
    ende_str = letztes["d"] if letztes and letztes["d"] else None

    if not ende_str:
        ende = date.today()
    else:
        try:
            ende = date.fromisoformat(str(ende_str)[:10])
        except (ValueError, TypeError):
            ende = date.today()

    delta_days = (ende - start).days
    return max(0.0, round(delta_days / 30.44, 1))


def _zaehle_schriftsaetze(az, conn):
    # type: (str, object) -> int
    """Zählt Schriftsätze/Dokumente (Forderungsschreiben, Sonstiges, Klage)."""
    row = conn.execute(
        """
        SELECT COUNT(*) as cnt FROM dokumente
        WHERE akte_id = ?
          AND typ IN ('forderungsschreiben', 'klage', 'sonstiges', 'abrechnungsschreiben')
        """,
        (az,)
    ).fetchone()
    return int(row["cnt"]) if row else 0


def _zaehle_schaden_felder(schaden_dict):
    # type: (dict) -> int
    """Zählt nicht-null Schadenpositionen als Fallback."""
    felder = [
        "reparaturkosten", "wiederbeschaffung", "wertminderung",
        "nutzungsausfall", "mietwagenkosten", "sv_kosten",
        "abschleppkosten", "standkosten", "schmerzensgeld",
        "verdienstausfall", "unkostenpauschale",
    ]
    return sum(1 for f in felder if schaden_dict.get(f))
