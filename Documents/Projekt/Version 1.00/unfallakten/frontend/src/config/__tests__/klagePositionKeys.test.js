import { describe, it, expect } from "vitest";
import { KLAGE_KEY_MAP, KEYS_OHNE_POSITION } from "../klagePositionKeys.js";

// Spiegel der Backend-POSITION_KEYS (backend/models/abrechnungsschreiben.py, KW-38) —
// bewusste Kopie, keine echte Cross-Language-Referenz. Synchronitaet sichert der
// BE-Waechter-Test backend/tests/test_klage_kw38_position_keys.py.
const POSITION_KEYS = [
  "reparaturkosten", "wiederbeschaffung", "restwert",
  "wertminderung", "nutzungsausfall", "mietwagenkosten",
  "sv_kosten", "abschleppkosten", "restkraftstoff", "standkosten",
  "anabmeldekosten", "schmerzensgeld", "sonstiges",
  "reparatur_brutto", "reparatur_netto",
  "wbw", "wbw_netto", "wbw_brutto", "wba",
  "fahrzeugschaden", "kostenpauschale",
  "ra_gebuehren", "mwst_abzug", "pruefbericht_abzug",
  "rep_gutachten_netto", "rep_rechnung_netto", "rep_rechnung_brutto",
  "verdienstausfall", "haushalt", "unkostenpauschale", "kostennb",
  "vorschuss",
  "sonstiges_wdm_1", "sonstiges_wdm_2", "sonstiges_wdm_3",
  "sonstiges_wdm_4", "sonstiges_wdm_5", "sonstiges_wdm_6",
];

// Identitaets-Keys: Regulierungs-Key == Wizard-Key aus pos_definitionen
// (backend/routers/klage_routes.py) — brauchen keinen Map-Eintrag.
const WIZARD_KEYS = [
  "fahrzeugschaden", "wertminderung", "sv_kosten", "nutzungsausfall",
  "mietwagenkosten", "abschleppkosten", "standkosten", "anabmeldekosten",
  "unkostenpauschale", "verdienstausfall", "haushalt", "schmerzensgeld",
  "kostennb", "sonstiges",
];

describe("klagePositionKeys (KW-38 Positions-Key-Vertrag)", () => {
  it("jeder position_key ist gemappt, identisch oder bewusst ausgenommen", () => {
    for (const k of POSITION_KEYS) {
      const abgedeckt =
        k in KLAGE_KEY_MAP || KEYS_OHNE_POSITION.has(k) || WIZARD_KEYS.includes(k);
      expect(abgedeckt, `position_key ohne Vertrag: ${k}`).toBe(true);
    }
  });

  it("die 8 bisherigen Fahrzeugschaden-Aliase bleiben byte-gleich", () => {
    const erwartet = {
      reparatur_netto: "fahrzeugschaden",
      reparatur_brutto: "fahrzeugschaden",
      reparaturkosten: "fahrzeugschaden",
      wba: "fahrzeugschaden",
      rep_gutachten_netto: "fahrzeugschaden",
      rep_rechnung_netto: "fahrzeugschaden",
      rep_rechnung_brutto: "fahrzeugschaden",
      wiederbeschaffung: "fahrzeugschaden",
    };
    for (const [k, v] of Object.entries(erwartet)) {
      expect(KLAGE_KEY_MAP[k]).toBe(v);
    }
  });
});
