import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  abschnittHatAufgabe, initialUebernahme, baueUebernahmePayload,
  FragebogenUebernahme,
} from "./ReviewQueueView.jsx";

const ABSCHNITTE = [
  { key: "mandant", label: "Mandant", felder: [
    { feld: "name", label: "Name", geparst: "Riccio", akte_wert: "Riccio", ist_leer: false, konflikt: false },
    { feld: "telefon", label: "Telefon", geparst: "069 1", akte_wert: null, ist_leer: true, konflikt: false },
    { feld: "ort", label: "Ort", geparst: "Neu-Isenburg", akte_wert: "Offenbach", ist_leer: false, konflikt: true },
  ]},
  { key: "gegner", label: "Gegner", felder: [] },
];

describe("Fragebogen-Uebernahme Helfer", () => {
  it("abschnittHatAufgabe: leer oder konflikt = Aufgabe", () => {
    expect(abschnittHatAufgabe(ABSCHNITTE[0].felder)).toBe(true);
    expect(abschnittHatAufgabe([{ ist_leer: false, konflikt: false }])).toBe(false);
    expect(abschnittHatAufgabe([])).toBe(false);
  });

  it("initialUebernahme: alle Abschnitte mit Feldern aktiv, ohne Aufgabe eingeklappt", () => {
    const s = initialUebernahme(ABSCHNITTE);
    expect(s.aktive).toContain("mandant");
    expect(s.aktive).not.toContain("gegner");   // keine Felder
    // werte: leer -> geparst, konflikt -> akte_wert, gleich -> nicht enthalten
    expect(s.werte.mandant.telefon).toBe("069 1");
    expect(s.werte.mandant.ort).toBe("Offenbach");
    expect(s.werte.mandant.name).toBeUndefined();
  });

  it("baueUebernahmePayload: nur aktive Abschnitte + editierbare Felder", () => {
    const s = initialUebernahme(ABSCHNITTE);
    const p = baueUebernahmePayload(ABSCHNITTE, s);
    expect(p.abschnitte).toEqual(["mandant"]);
    expect(p.werte.mandant).toEqual({ telefon: "069 1", ort: "Offenbach" });
  });

  it("rendert leere, Konflikt- und gesperrte Felder", () => {
    const s = initialUebernahme(ABSCHNITTE);
    render(<FragebogenUebernahme abschnitte={ABSCHNITTE} state={s}
             onToggle={() => {}} onFeld={() => {}} onAdopt={() => {}} />);
    expect(screen.getByText("Telefon")).toBeInTheDocument();
    expect(screen.getByText(/Bogen übernehmen/)).toBeInTheDocument();  // Konflikt-Feld
  });
});
