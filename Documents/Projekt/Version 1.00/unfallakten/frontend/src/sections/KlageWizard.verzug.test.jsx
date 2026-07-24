import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { buildVerzugAutoText, StepVerzug } from "./KlageWizard.jsx";
import { verzugEintrittDefault } from "../config/utils.js";
import { STANDARDTEXTE_FIXTURE as TEXTE } from "../test/standardtexteFixture.js";

describe("buildVerzugAutoText (KW-10)", () => {
  it("nutzt Eintritt fuer den Eintrittssatz und Schreibdatum fuer den BEWEIS", () => {
    const t = buildVerzugAutoText("04.05.2026", "19.05.2026", TEXTE);
    expect(t).toContain("am 19.05.2026 eingetreten");
    expect(t).toContain("BEWEIS: Schreiben vom 04.05.2026");
  });
  it("ohne Eintritt -> Rechtshaengigkeit (Schreibdatum behauptet KEINEN Eintritt mehr)", () => {
    expect(buildVerzugAutoText("04.05.2026", "", TEXTE)).toBe("Verzug ist mit Rechtshängigkeit eingetreten.");
  });
  it("mit Eintritt, ohne Schreibdatum -> kein BEWEIS-Satz", () => {
    const t = buildVerzugAutoText("", "19.05.2026", TEXTE);
    expect(t).toContain("am 19.05.2026 eingetreten");
    expect(t).not.toContain("BEWEIS");
  });
});

describe("verzugEintrittDefault (KW-10)", () => {
  it("Schreibdatum + 14 Tage", () => expect(verzugEintrittDefault("04.05.2026")).toBe("18.05.2026"));
  it("ISO-Input wird verarbeitet", () => expect(verzugEintrittDefault("2026-05-04")).toBe("18.05.2026"));
  it("Monatsuebergang", () => expect(verzugEintrittDefault("20.12.2026")).toBe("03.01.2027"));
  it("leer -> leer", () => expect(verzugEintrittDefault("")).toBe(""));
});

const STEP_VERZUG_BASIS_PROPS = {
  zinsenAb: "verzug",
  weiblich: false,
  wizardVerzugDatum: "",
  onWizardVerzugDatum: vi.fn(),
  wizardVerzugDokDatum: "",
  onWizardVerzugDokDatum: vi.fn(),
  wizardVerzugText: "",
  onWizardVerzugText: vi.fn(),
  manuelleBearbeitung: false,
  onManuelleBearbeitung: vi.fn(),
  verzugDokListe: [{ id: 5, dateiname: "mahnschreiben.pdf" }, { id: 9, dateiname: "verzugsschreiben.pdf" }],
  verzugDokId: null,
  onVerzugDokId: vi.fn(),
  standardtexte: TEXTE,
};

describe("StepVerzug – KW-28 Step-8-Select-Wiring", () => {
  it("ruft onVerzugDokId mit der ausgewaehlten Dokument-ID auf", () => {
    render(<StepVerzug {...STEP_VERZUG_BASIS_PROPS} />);

    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "9" } });

    expect(STEP_VERZUG_BASIS_PROPS.onVerzugDokId).toHaveBeenCalledWith(9);
  });
});
