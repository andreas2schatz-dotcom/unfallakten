import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("../api.js", () => ({
  API_BASE: "",
  ApiError: class ApiError extends Error {},
  tokenStore: { getAccess: () => "" },
  request: vi.fn(() => Promise.resolve({})),
  beteiligte: { erstellen: vi.fn(), aktualisieren: vi.fn(), loeschen: vi.fn() },
  portal: { einladen: vi.fn() },
}));

import BeteiligteSection from "./BeteiligteSection.jsx";
import { rolleLabel } from "../config/constants.js";

/**
 * Befund 2026-08-31: Zeugen standen als "Gegner" in der Liste, Rechtsschutz
 * und Schadenabwickler pauschal als "Sonstige Beteiligte". Das Backend
 * liefert jetzt die Rolle aus dem Kuerzelverzeichnis samt Bezeichnung --
 * die Liste muss beides anzeigen koennen.
 */

const basis = { id: 1, name: "Muster", vorname: "", akte_id: "1/26" };

/** Rendert und gibt die Rollen-Spalte der Tabelle zurueck -- die Rollennamen
 *  stehen sonst auch im Auswahlfeld des Hinzufuegen-Dialogs. */
function zeigeRollen(beteiligte) {
  const { container } = render(
    <BeteiligteSection
      beteiligte={beteiligte}
      dispatch={() => {}}
      akteId="1/26"
    />
  );
  const tabelle = container.querySelector("table");
  return {
    tabelle,
    texte: [...tabelle.querySelectorAll("tbody tr td:first-child")]
      .map((td) => td.textContent.trim()),
  };
}

describe("rolleLabel", () => {
  it("uebersetzt die neuen Rollen ins Deutsche", () => {
    expect(rolleLabel("zeuge")).toBe("Zeuge");
    expect(rolleLabel("gegner_hv")).toBe("Gegnerische Haftpflicht");
    expect(rolleLabel("gegner_anwalt")).toBe("Gegnerischer Anwalt");
    expect(rolleLabel("schadenabwickler")).toBe("Schadenabwickler");
    expect(rolleLabel("rechtsschutz")).toBe("Rechtsschutz");
    expect(rolleLabel("eigene_versicherung")).toBe("Eigene Versicherung");
    expect(rolleLabel("behoerde")).toBe("Behörde");
    expect(rolleLabel("bank")).toBe("Bank / Leasing");
    expect(rolleLabel("vollstreckung")).toBe("Vollstreckung");
  });

  it("laesst die bestehenden Rollen unveraendert", () => {
    expect(rolleLabel("mandant")).toBe("Mandant");
    expect(rolleLabel("gegner")).toBe("Gegner");
    expect(rolleLabel("sachverstaendiger")).toBe("Sachverständiger");
    expect(rolleLabel("sonstiger")).toBe("Sonstige Beteiligte");
  });

  it("gibt eine unbekannte Rolle unveraendert zurueck, statt zu leeren", () => {
    expect(rolleLabel("etwas_neues")).toBe("etwas_neues");
  });

  it("bevorzugt die Bezeichnung aus dem Kuerzelverzeichnis", () => {
    expect(rolleLabel("vollstreckung", "Gerichtsvollzieher")).toBe("Gerichtsvollzieher");
    expect(rolleLabel("sonstiger", "Korrespondenzanwalt")).toBe("Korrespondenzanwalt");
  });
});

describe("Beteiligtenliste – Rollenanzeige", () => {
  it("zeigt einen Zeugen als Zeuge und nicht als Gegner", () => {
    const { texte } = zeigeRollen([
      { ...basis, rolle: "zeuge", bezeichnung: "Zeuge/Zeugin" },
    ]);
    expect(texte).toEqual(["Zeuge/Zeugin"]);
  });

  it("zeigt die Rechtsschutzversicherung nicht mehr als Sonstige", () => {
    const { texte } = zeigeRollen([
      { ...basis, rolle: "rechtsschutz", bezeichnung: "Rechtsschutzversicherung" },
    ]);
    expect(texte).toEqual(["Rechtsschutzversicherung"]);
  });

  it("faellt ohne Bezeichnung auf die Rollenbeschriftung zurueck", () => {
    const { texte } = zeigeRollen([{ ...basis, rolle: "zeuge" }]);
    expect(texte).toEqual(["Zeuge"]);
  });

  it("kennzeichnet einen Beteiligten mit unbekanntem Kuerzel", () => {
    const { tabelle } = zeigeRollen([
      { ...basis, rolle: "sonstiger", kuerzel: "QQQ",
        kuerzel_hinweis: "Kürzel „QQQ“ ist im Kürzelverzeichnis nicht hinterlegt" },
    ]);
    expect(tabelle.querySelector("[title*='QQQ']")).toBeTruthy();
  });

  it("zeigt den Gegner unveraendert", () => {
    const { texte } = zeigeRollen([{ ...basis, rolle: "gegner" }]);
    expect(texte).toEqual(["Gegner"]);
  });
});
