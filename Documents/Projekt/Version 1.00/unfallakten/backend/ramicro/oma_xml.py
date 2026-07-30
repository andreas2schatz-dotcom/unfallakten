"""OMA-XML-Generator (RA-MICRO Onlinemandat, Muster: beispieloma.xml)."""
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

ANREDEN = {"herr": ("HERR", "Herr"),
           "frau": ("FRAU", "Frau"),
           "firma": ("FIRMA", "Firma")}


def _feld(parent, tag, name, wert=""):
    el = ET.SubElement(parent, tag, {"typ": "feld", "name": name})
    el.text = (wert or "").strip()
    return el


def _option(parent, tag, name, value, text):
    el = ET.SubElement(parent, tag, {"typ": "option", "name": name})
    ET.SubElement(el, "value").text = value
    ET.SubElement(el, "text").text = text
    return el


def _person_block(parent, daten):
    person = ET.SubElement(parent, "Person")
    value, text = ANREDEN.get((daten.get("anrede") or "").lower(), ("", ""))
    _option(person, "Anrede", "Anrede", value, text)
    _feld(person, "AndereAnredeBezeichnung", "Andere Anrede")
    _feld(person, "Titel", "Titel", daten.get("titel"))
    _feld(person, "Adelstitel", "Adelstitel")
    _feld(person, "Vorname", "Vorname", daten.get("vorname"))
    _feld(person, "Nachname", "Nachname", daten.get("nachname"))
    _feld(person, "Geburtstag", "Geburtstag", daten.get("geburtstag"))
    _feld(person, "Geburtsort", "Geburtsort")
    _feld(person, "Geburtsname", "Geburtsname")
    _feld(person, "Staatsangehoerigkeit", "Staatsangehoerigkeit")
    _feld(person, "IdNr", "IdNr")


def _adresse_block(parent, daten):
    adresse = ET.SubElement(parent, "Adresse")
    _feld(adresse, "Strasse", "Straße Nr.", daten.get("strasse"))
    _feld(adresse, "Adresszusatz", "Adresszusatz")
    _feld(adresse, "PLZ", "PLZ", daten.get("plz"))
    _feld(adresse, "Ort", "Ort", daten.get("ort"))
    _feld(adresse, "Land", "Land", "Deutschland")
    ET.SubElement(adresse, "LKZ", {"typ": "data"}).text = "DE"


def _kontakt_block(parent, daten):
    kontakt = ET.SubElement(parent, "Kontakt")
    _feld(kontakt, "Telefon", "Telefon", daten.get("telefon"))
    _feld(kontakt, "Mobiltelefon", "Mobiltelefon")
    _feld(kontakt, "EMail", "E-Mail", daten.get("email"))


def _zusatz_text(formular):
    unfall = formular.get("unfall") or {}
    gutachter = formular.get("gutachter") or {}
    mandant = formular.get("mandant") or {}
    zeilen = []
    if unfall.get("unfalldatum"):
        zeilen.append(f"Unfalldatum: {unfall['unfalldatum']}")
    if unfall.get("unfallort"):
        zeilen.append(f"Unfallort: {unfall['unfallort']}")
    if unfall.get("kennzeichen"):
        zeilen.append(f"Amtl. Kennzeichen Mandant: {unfall['kennzeichen']}")
    if gutachter.get("gutachten_nr"):
        zeilen.append(f"Gutachten-Nr.: {gutachter['gutachten_nr']}")
    if mandant.get("bekannt_adressnr"):
        zeilen.append("Bestandsmandant, RA-MICRO Adressnummer: "
                      f"{mandant['bekannt_adressnr']}")
    zeilen.append("Angelegt über das Unfallakten-System (Aktenanlage).")
    return "\n".join(zeilen)


def erzeuge_oma_xml(formular: dict) -> str:
    mandant = formular.get("mandant") or {}
    gegner = formular.get("gegner") or {}
    versicherung = formular.get("versicherung") or {}
    gutachter = formular.get("gutachter") or {}

    root = ET.Element("Onlinemandat", {
        "typ": "gruppe", "name": "Datenblatt für neue Mandanten"})

    ra = ET.SubElement(root, "Rechtsangelegenheiten", {
        "typ": "gruppe", "name": "Startseite"})
    _option(ra, "Rechtsangelegenheit", "Rechtsangelegenheit",
            "VERKEHRSUNFALL", "Verkehrsunfall")
    _feld(ra, "AndereAngelegenheitBezeichnung", "Andere Angelegenheit",
          "Verkehrsrecht")

    mliste = ET.SubElement(root, "Mandantenliste", {
        "typ": "gruppe", "name": "Daten zum Mandant"})
    m = ET.SubElement(mliste, "Mandant", {
        "typ": "gruppe", "name": "1. Mandant"})
    nr = ET.SubElement(m, "Nr", {"typ": "data"})
    nr.text = "1"
    if mandant.get("bekannt_adressnr"):
        _option(m, "Bekannt",
                "Waren Sie schon einmal Mandant in unserer Kanzlei?",
                "2", "Ja")
    else:
        _option(m, "Bekannt",
                "Waren Sie schon einmal Mandant in unserer Kanzlei?",
                "1", "Nein")
    _person_block(m, mandant)
    _adresse_block(m, mandant)
    _kontakt_block(m, mandant)
    konto = ET.SubElement(m, "Konto")
    _feld(konto, "IBAN", "IBAN", mandant.get("iban"))
    _feld(konto, "Bank", "Bank", mandant.get("bank"))
    _feld(konto, "BIC", "BIC")
    rsv = ET.SubElement(m, "Rechtsschutzversicherer")
    _feld(rsv, "Name", "Rechtsschutzversicherung", mandant.get("rsv_name"))
    _feld(rsv, "Versicherungsnummer", "Versicherungsnummer",
          mandant.get("rsv_nummer"))
    mv = ET.SubElement(m, "Versicherung")
    _feld(mv, "Name", "Name der Versicherung")
    _feld(mv, "Schadennummer", "Schadennummer, Vertragsnummer, o.ä.")

    gliste = ET.SubElement(root, "Gegnerliste", {
        "typ": "gruppe", "name": "Daten zum Gegner"})
    if (gegner.get("nachname") or "").strip():
        g = ET.SubElement(gliste, "Gegner", {
            "typ": "gruppe", "name": "1. Gegner"})
        nr = ET.SubElement(g, "Nr", {"typ": "data"})
        nr.text = "1"
        _person_block(g, gegner)
        _adresse_block(g, gegner)
        _kontakt_block(g, gegner)
        konto_g = ET.SubElement(g, "Konto")
        _feld(konto_g, "IBAN", "IBAN")
        _feld(konto_g, "Bank", "Bank")
        _feld(konto_g, "BIC", "BIC")
        vers_g = ET.SubElement(g, "Versicherung")
        _feld(vers_g, "Name", "Name der Versicherung")
        _feld(vers_g, "Schadennummer", "Schadennummer, Vertragsnummer, o.ä.")
        hinweise_g = ET.SubElement(g, "Hinweise")
        _feld(hinweise_g, "Text", "Weitere Hinweise")
        anwalt_g = ET.SubElement(g, "Anwalt")
        _feld(anwalt_g, "KanzleiBezeichnung", "Bezeichnung Kanzlei")
        _feld(anwalt_g, "Strasse", "Straße Nr.")
        _feld(anwalt_g, "Adresszusatz", "Adresszusatz")
        _feld(anwalt_g, "PLZ", "PLZ")
        _feld(anwalt_g, "Ort", "Ort")
        _feld(anwalt_g, "Land", "Land", "Deutschland")
        lkz = ET.SubElement(anwalt_g, "LKZ", {"typ": "data"})
        lkz.text = "DE"
        _feld(anwalt_g, "Aktenzeichen", "Aktenzeichen")

    bliste = ET.SubElement(root, "Beteiligtenliste", {
        "typ": "gruppe", "name": "Daten zu Beteiligten"})
    if (versicherung.get("name") or "").strip():
        b = ET.SubElement(bliste, "Beteiligter", {
            "typ": "gruppe", "name": "Beteiligter: Versicherung"})
        ET.SubElement(b, "Nr", {"typ": "data"})
        vgrp = ET.SubElement(b, "Versicherung", {
            "typ": "gruppe", "name": "Versicherung"})
        _feld(vgrp, "Bezeichnung", "Bezeichnung", versicherung.get("name"))
        _feld(vgrp, "Aktenzeichen", "Aktenzeichen/Vorgangsnummer",
              versicherung.get("schadennummer"))
    if (gutachter.get("bezeichnung") or "").strip():
        b = ET.SubElement(bliste, "Beteiligter", {
            "typ": "gruppe", "name": "Beteiligter: Gutachter"})
        ET.SubElement(b, "Nr", {"typ": "data"})
        agrp = ET.SubElement(b, "Andere", {
            "typ": "gruppe", "name": "Andere Beteiligte"})
        _feld(agrp, "Bezeichnung", "Bezeichnung", gutachter.get("bezeichnung"))
        _feld(agrp, "Aktenzeichen", "Aktenzeichen/Vorgangsnummer",
              gutachter.get("gutachten_nr"))
        _feld(agrp, "Strasse", "Straße Nr.", gutachter.get("strasse"))
        _feld(agrp, "Adresszusatz", "Adresszusatz")
        _feld(agrp, "PLZ", "PLZ", gutachter.get("plz"))
        _feld(agrp, "Ort", "Ort", gutachter.get("ort"))
        _feld(agrp, "Land", "Land", "Deutschland")
        ET.SubElement(agrp, "LKZ", {"typ": "data"}).text = "DE"
        _feld(agrp, "Telefon", "Telefon", gutachter.get("telefon"))
        _feld(agrp, "Mobiltelefon", "Mobiltelefon")
        _feld(agrp, "EMail", "E-Mail", gutachter.get("email"))

    zusatz = ET.SubElement(root, "Zusatzangaben", {
        "typ": "gruppe", "name": "Daten an Anwalt senden"})
    _feld(zusatz, "Text",
          "Falls Ihnen weitere Informationen zu dieser Sache vorliegen, die nicht bereits in dem Formular abgefragt wurden, geben Sie sie bitte in dem Textfeld unten ein. Sofern Ihnen bereits eine Terminsladung zugestellt wurde, geben Sie dies bitte unter Nennung des Termins mit Datum und Uhrzeit hier an.",
          _zusatz_text(formular))
    _feld(zusatz, "VerbindlicheAnfrageAkzeptiert",
          "Sie stellen eine rechtsverbindliche Anfrage. Sie sind damit einverstanden und verlangen ausdrücklich, dass vor Ende der 14-tägigen Widerrufsfrist mit der Bearbeitung des Mandats begonnen wird. Ihnen ist bekannt, dass Sie mit vollständiger Erledigung des Mandats Ihr Widerrufsrecht verlieren.",
          "X")
    _feld(zusatz, "DatenschutzVereinbarungAkzeptiert",
          "Hiermit bestätigen Sie, dass Sie die Datenschutzerklärung akzeptieren und der Weitergabe Ihrer Daten an RA-MICRO Server durch die Online Mandats-Aufnahme zustimmen.",
          "X")
    ET.SubElement(root, "tvm")

    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            + ET.tostring(root, encoding="unicode",
                          short_empty_elements=False))


def _slug(text: str) -> str:
    text = (text or "unbekannt").lower()
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(alt, neu)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unbekannt"


def schreibe_oma_xml(formular: dict, ziel_ordner) -> Path:
    ordner = Path(ziel_ordner)
    if not ordner.is_dir():
        raise OSError(f"OMA-Export-Ordner existiert nicht: {ordner}")
    nachname = _slug((formular.get("mandant") or {}).get("nachname"))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ziel = ordner / f"onlinemandat_{stamp}_{nachname}.xml"
    tmp = ziel.with_suffix(".tmp")
    tmp.write_text(erzeuge_oma_xml(formular), encoding="utf-8")
    os.replace(tmp, ziel)
    return ziel
