import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StepRubrum } from "./KlageWizard.jsx";

const KLAEGER = { id: 1, rolle_klage: "klaeger", vorname: "Fabrizio", name: "Caporiccio" };
const VERS = {
  id: 2, rolle_klage: "beklagter", checked: true,
  vorname: "", name: "ADAC Autoversicherung AG",
  versicherung: "ADAC Autoversicherung AG", anschrift: "Hansastr. 19", plz: "80686", ort: "München",
};
const FAHRER = {
  id: 3, rolle_klage: "beklagter", checked: true,
  vorname: "Kadir", name: "Kuzaytepe", anrede: "Herr",
  versicherung: "ADAC", anschrift: "Teststr. 1", plz: "63065", ort: "Offenbach",
};

describe("StepRubrum Parteianzeige (Bugfix 828/24)", () => {
  it("Fahrer erscheint mit Personennamen, nicht als Versicherung", () => {
    render(<StepRubrum beklagte={[KLAEGER, VERS, FAHRER]} onClose={() => {}} />);
    expect(screen.getByText(/Kadir Kuzaytepe/)).toBeInTheDocument();
    const adacZeilen = screen.getAllByText(/ADAC/);
    expect(adacZeilen.length).toBe(1);
  });

  it("Fahrer (Herr) wird als Beklagter bezeichnet, nicht als Beklagte", () => {
    render(<StepRubrum beklagte={[KLAEGER, VERS, FAHRER]} onClose={() => {}} />);
    expect(screen.getByText(/– Beklagter zu 2\) –/)).toBeInTheDocument();
  });

  it("Fahrer bekommt keinen Vertreten-durch-Zusatz", () => {
    render(<StepRubrum beklagte={[KLAEGER, FAHRER]} onClose={() => {}} />);
    expect(screen.queryByText(/Kuzaytepe.*vertreten durch/)).toBeNull();
  });

  it("Firma ohne Vertreter: Organ nach Rechtsform statt pauschal Vorstand", () => {
    const gmbh = { id: 4, rolle_klage: "beklagter", checked: true, firma: "Autohaus Müller GmbH" };
    render(<StepRubrum beklagte={[KLAEGER, gmbh]} onClose={() => {}} />);
    expect(screen.getByText(/vertreten durch den\/die Geschäftsführer/)).toBeInTheDocument();
  });

  it("AG ohne Vertreter weiterhin Vorstand", () => {
    render(<StepRubrum beklagte={[KLAEGER, VERS]} onClose={() => {}} />);
    expect(screen.getByText(/vertreten durch den Vorstand/)).toBeInTheDocument();
  });
});
