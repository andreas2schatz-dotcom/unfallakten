import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { Fortschrittsbalken } from "./KlageWizard.jsx";

const STATUS = {
  1: { zustand: "erledigt", warnung: null },
  2: { zustand: "warnung", warnung: "Vertreter fehlt: HUK — Lookup in der Parteien-Karte." },
  3: { zustand: "aktiv", warnung: null },
};
const statusFuer = nr => STATUS[nr] || { zustand: "offen", warnung: null };

describe("Fortschrittsbalken mit Status-Symbolen", () => {
  it("zeigt Haken, Warnsymbol mit Tooltip und Nummer fuer offene Schritte", () => {
    const { getByText, getByTitle } = render(
      <Fortschrittsbalken step={3} maxStep={3} onStepChange={() => {}} statusFuer={statusFuer} />
    );
    expect(getByText("✓")).toBeTruthy();
    const warnKreis = getByTitle("Vertreter fehlt: HUK — Lookup in der Parteien-Karte.");
    expect(warnKreis.textContent).toBe("⚠");
    expect(getByText("4")).toBeTruthy();
  });

  it("Warnsymbol sperrt den Klick nicht (reine Anzeige)", () => {
    const onStepChange = vi.fn();
    const { getByTitle } = render(
      <Fortschrittsbalken step={3} maxStep={3} onStepChange={onStepChange} statusFuer={statusFuer} />
    );
    fireEvent.click(getByTitle("Vertreter fehlt: HUK — Lookup in der Parteien-Karte."));
    expect(onStepChange).toHaveBeenCalledWith(2);
  });
});
