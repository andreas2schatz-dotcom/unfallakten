import { describe, it, expect, vi } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { schrittBlockiert, kannSpringen, Fortschrittsbalken } from "./KlageWizard.jsx";

describe("schrittBlockiert", () => {
  it("Step 1 blockiert ohne Gerichtsbestätigung", () => {
    expect(schrittBlockiert(1, { gerichtBestaetigt: false, positionen: [] })).toBe(true);
    expect(schrittBlockiert(1, { gerichtBestaetigt: true, positionen: [] })).toBe(false);
  });
  it("Step 5 blockiert ohne gecheckte Position", () => {
    expect(schrittBlockiert(5, { gerichtBestaetigt: true, positionen: [{ checked: false }] })).toBe(true);
    expect(schrittBlockiert(5, { gerichtBestaetigt: true, positionen: [{ checked: true }] })).toBe(false);
  });
});

describe("kannSpringen", () => {
  const ctx = { gerichtBestaetigt: true, positionen: [{ checked: false }] };
  it("rueckwaerts immer erlaubt", () => {
    expect(kannSpringen(2, 5, ctx)).toBe(true);
  });
  it("vorwaerts ueber gesperrten Step 5 hinweg verboten", () => {
    expect(kannSpringen(6, 5, ctx)).toBe(false);
    expect(kannSpringen(10, 3, ctx)).toBe(false);
  });
  it("vorwaerts erlaubt wenn alle Zwischen-Steps frei", () => {
    const frei = { gerichtBestaetigt: true, positionen: [{ checked: true }] };
    expect(kannSpringen(6, 5, frei)).toBe(true);
  });
});

describe("Fortschrittsbalken", () => {
  it("Klick auf Kreis hinter gesperrtem Step ruft onStepChange NICHT", () => {
    const onStepChange = vi.fn();
    const { getByText } = render(
      <Fortschrittsbalken step={5} maxStep={10} onStepChange={onStepChange}
        springenErlaubt={(nr) => kannSpringen(nr, 5, { gerichtBestaetigt: true, positionen: [{ checked: false }] })} />
    );
    const kreisVon = (label) => getByText(label).parentElement.querySelector("div");

    fireEvent.click(kreisVon("Anträge"));
    expect(onStepChange).not.toHaveBeenCalled();

    fireEvent.click(kreisVon("Rubrum"));
    expect(onStepChange).toHaveBeenCalledWith(2);
  });
});
