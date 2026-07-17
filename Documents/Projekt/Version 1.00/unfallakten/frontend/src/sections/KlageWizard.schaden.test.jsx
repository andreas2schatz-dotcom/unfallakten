import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepSchaden } from "./KlageWizard.jsx";

const BASIS_PROPS = {
  positionen: [
    { key: "wertminderung",   label: "Wertminderung",   betrag: 400,  checked: true },
    { key: "schmerzensgeld",  label: "Schmerzensgeld",  betrag: 2000, checked: true },
  ],
  onTogglePos: vi.fn(),
  mitSG: false,
  onMitSG: vi.fn(),
  sgMind: 0,
  onSGMind: vi.fn(),
  abrechnungen: [],
  az: null,
  kl_nom: "Der Kläger",
};

describe("StepSchaden – KW-07 Schmerzensgeld nicht doppelt", () => {
  it("ruft bei mitSG=true den echten Setter auf, um die SG-Position zu enthaken", () => {
    const onTogglePos = vi.fn();
    render(<StepSchaden {...BASIS_PROPS} mitSG={true} onTogglePos={onTogglePos} />);

    expect(onTogglePos).toHaveBeenCalledWith("schmerzensgeld");
    expect(onTogglePos).toHaveBeenCalledTimes(1);
  });

  it("zeigt die SG-Zeile bei mitSG=true als disabled+unchecked mit Hinweis", () => {
    const positionenNachToggle = [
      { key: "wertminderung",  label: "Wertminderung",  betrag: 400,  checked: true },
      { key: "schmerzensgeld", label: "Schmerzensgeld", betrag: 2000, checked: false },
    ];
    render(<StepSchaden {...BASIS_PROPS} mitSG={true} positionen={positionenNachToggle} />);

    const sgCheckbox = screen.getByRole("row", { name: /Schmerzensgeld/i })
      .querySelector('input[type="checkbox"]');
    expect(sgCheckbox).toBeDisabled();
    expect(sgCheckbox).not.toBeChecked();
    expect(screen.getByText(/Wird als unbezifferter Antrag geltend gemacht \(Schmerzensgeld-Toggle aktiv\)/i))
      .toBeInTheDocument();

    const wertminderungCheckbox = screen.getByRole("row", { name: /Wertminderung/i })
      .querySelector('input[type="checkbox"]');
    expect(wertminderungCheckbox).not.toBeDisabled();
  });

  it("macht die SG-Zeile bei mitSG=false wieder bedienbar (checked bleibt unverändert)", () => {
    const positionenUnchecked = [
      { key: "wertminderung",  label: "Wertminderung",  betrag: 400,  checked: true },
      { key: "schmerzensgeld", label: "Schmerzensgeld", betrag: 2000, checked: false },
    ];
    const onTogglePos = vi.fn();
    render(<StepSchaden {...BASIS_PROPS} mitSG={false} positionen={positionenUnchecked} onTogglePos={onTogglePos} />);

    const sgCheckbox = screen.getByRole("row", { name: /Schmerzensgeld/i })
      .querySelector('input[type="checkbox"]');
    expect(sgCheckbox).not.toBeDisabled();
    expect(sgCheckbox).not.toBeChecked();
    expect(screen.queryByText(/Schmerzensgeld-Toggle aktiv/i)).not.toBeInTheDocument();
    expect(onTogglePos).not.toHaveBeenCalled();
  });
});
