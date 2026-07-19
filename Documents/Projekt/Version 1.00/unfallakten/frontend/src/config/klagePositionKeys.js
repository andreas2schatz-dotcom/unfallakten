// KW-38: kanonischer Positions-Key-Vertrag zwischen den Regulierungs-Parser-Keys
// (regulierung_positionen.position_key, siehe POSITION_KEYS in
// backend/models/abrechnungsschreiben.py) und den Klage-Wizard-Positionen
// (pos_definitionen in backend/routers/klage_routes.py). Loest die vormals drei
// identischen Fahrzeugschaden-Maps ab (_KLAGEN_KEY_MAP + _KEY_MAP in KlageSection.jsx,
// _PROV_KEY_MAP in KlageWizard.jsx).

// Regulierungs-Key -> Wizard-Key. Keys ohne Eintrag hier UND ohne Eintrag in
// KEYS_OHNE_POSITION sind Identitaets-Keys (Regulierungs-Key == Wizard-Key, z.B.
// "fahrzeugschaden", "wertminderung", "sonstiges").
export const KLAGE_KEY_MAP = {
  // Fahrzeugschaden-Aliase: Reparatur/Wiederbeschaffung-Varianten des Parsers
  // laufen alle in die eine Wizard-Position "fahrzeugschaden" (8 bestehende
  // Aliase, byte-gleich zu den drei vormaligen Kopien).
  reparatur_netto: "fahrzeugschaden",
  reparatur_brutto: "fahrzeugschaden",
  reparaturkosten: "fahrzeugschaden",
  wba: "fahrzeugschaden",
  rep_gutachten_netto: "fahrzeugschaden",
  rep_rechnung_netto: "fahrzeugschaden",
  rep_rechnung_brutto: "fahrzeugschaden",
  wiederbeschaffung: "fahrzeugschaden",

  // Wiederbeschaffungswert-Varianten (WBW) sind derselbe Fahrzeugschaden-Topf.
  wbw: "fahrzeugschaden",
  wbw_netto: "fahrzeugschaden",
  wbw_brutto: "fahrzeugschaden",

  // Parser-Synonym: "kostenpauschale" und die Wizard-Position "unkostenpauschale"
  // bezeichnen denselben Betrag (siehe _REGULIERUNG_LABEL_MAP in klage_service.py,
  // beide -> "Unkostenpauschale").
  kostenpauschale: "unkostenpauschale",
};

// Bewusst NICHT positionsgebundene Regulierungs-Keys: pos_definitionen fuehrt
// dafuer keine eigene Klage-Position, weil sie entweder eine Gegenrechnung,
// eine ungebundene Zahlung, ein Abzugs-/Meta-Wert oder statisch nicht
// abbildbar sind.
export const KEYS_OHNE_POSITION = new Set([
  "restwert",          // Gegenrechnung auf den Fahrzeugschaden, keine eigene Klage-Position
  "restkraftstoff",    // keine eigene Wizard-Position (pos_definitionen kennt sie nicht)
  "ra_gebuehren",       // RA-Gebuehren werden im Wizard ueber die RVG-Berechnung ermittelt, nicht als Schaden-Position
  "mwst_abzug",         // Abzugs-Key (reduziert eine andere Position, keine eigene)
  "pruefbericht_abzug", // Abzugs-Key (reduziert eine andere Position, keine eigene)
  "vorschuss",          // ungebundene Zahlung, keiner Einzelposition zugeordnet
  // WDM-Sonstige-Schaeden: der Wizard erzeugt dafuer KEINEN vorhersagbaren
  // statischen Key. pos_definitionen baut ihn in klage_routes.py als
  // f"extra_{e.get('key', e.get('label', '?'))}" - die WDM-Extra-Dicts aus
  // ramicro_akte_routes.py liefern kein "key"-Feld (nur id/label/betrag/netto),
  // also greift der Label-Fallback: realer Key ist "extra_<Label>" (Beleg:
  // Fixture "extra_Bergungskosten" in test_klage_service_docx.py). Ein
  // statisches Mapping kann das nicht treffen -> bewusst ausgenommen statt
  // falsch gemappt; Zahlungen auf diese Keys fallen wie zuvor in den
  // _unassigned-Topf.
  "sonstiges_wdm_1",
  "sonstiges_wdm_2",
  "sonstiges_wdm_3",
  "sonstiges_wdm_4",
  "sonstiges_wdm_5",
  "sonstiges_wdm_6",
]);
