import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DiffAnsicht, EditorMitDiff, TextVeraltetBadge, StepVerzug, StepAntraege, buildVerzugAutoText } from "./KlageWizard.jsx";

describe("DiffAnsicht", () => {
  it("markiert Ergaenzungen gruen und Streichungen durchgestrichen", () => {
    render(<DiffAnsicht autoText="Der Beklagte zahlt" aktuellerText="Die Beklagte zahlt sofort" />);
    const box = screen.getByTestId("diff-ansicht");
    const spans = [...box.querySelectorAll("span[data-difftyp]")];
    const typen = spans.map(s => s.dataset.difftyp);
    expect(typen).toEqual(["weg", "neu", "gleich", "neu"]);
    expect(spans[0].style.textDecoration).toContain("line-through");
  });
});

describe("EditorMitDiff", () => {
  it("ohne Abweichung: kein Umschalter, Textarea editierbar", () => {
    render(<EditorMitDiff autoText="Gleich" text="Gleich" onText={() => {}} />);
    expect(screen.queryByText(/Änderungen anzeigen/)).toBeNull();
    expect(screen.getByDisplayValue("Gleich")).toBeTruthy();
  });

  it("mit Abweichung: Umschalter wechselt zwischen Editor und Diff", () => {
    render(<EditorMitDiff autoText="Alt" text="Neu" onText={() => {}} />);
    fireEvent.click(screen.getByText(/Änderungen anzeigen/));
    expect(screen.getByTestId("diff-ansicht")).toBeTruthy();
    fireEvent.click(screen.getByText(/Bearbeiten/));
    expect(screen.getByDisplayValue("Neu")).toBeTruthy();
  });

  it("Tippen im Editor ruft onText", () => {
    const onText = vi.fn();
    render(<EditorMitDiff autoText="Alt" text="Neu" onText={onText} />);
    fireEvent.change(screen.getByDisplayValue("Neu"), { target: { value: "Neuer" } });
    expect(onText).toHaveBeenCalledWith("Neuer");
  });
});

describe("TextVeraltetBadge mit Diff-Link", () => {
  it("zeigt Aenderungen-Button nur mit autoText/aktuellerText und klappt Diff auf", () => {
    const { rerender } = render(
      <TextVeraltetBadge sichtbar onNeuGenerieren={() => {}} onBehalten={() => {}} />
    );
    expect(screen.queryByText(/Änderungen anzeigen/)).toBeNull();
    rerender(<TextVeraltetBadge sichtbar onNeuGenerieren={() => {}} onBehalten={() => {}}
      autoText="Alt" aktuellerText="Neu" />);
    fireEvent.click(screen.getByText(/Änderungen anzeigen/));
    expect(screen.getByTestId("diff-ansicht")).toBeTruthy();
  });
});

describe("Diff-Integration", () => {
  it("StepVerzug zeigt Umschalter bei manuell geaendertem Text", () => {
    const auto = buildVerzugAutoText("2026-05-01", "2026-05-15");
    render(<StepVerzug zinsenAb="verzug" weiblich={false}
      wizardVerzugDatum="2026-05-15" onWizardVerzugDatum={() => {}}
      wizardVerzugDokDatum="2026-05-01" onWizardVerzugDokDatum={() => {}}
      wizardVerzugText={auto + " Zusatz."} onWizardVerzugText={() => {}}
      manuelleBearbeitung onManuelleBearbeitung={() => {}}
      verzugDokListe={[]} verzugDokId={null} onVerzugDokId={() => {}} />);
    fireEvent.click(screen.getByText(/Änderungen anzeigen/));
    expect(screen.getByTestId("diff-ansicht").textContent).toContain("Zusatz.");
  });

  it("StepAntraege reicht antraegeAuto an Badge und Editor durch", () => {
    render(<StepAntraege positionen={[]} mitSG={false} sgMind={0} beklagte={[]} weiblich={false}
      zinsenAb="rechtshaengigkeit" verzug="" unfalldatum=""
      mitFestSg={false} onMitFestSg={() => {}} mitFestSach={false} onMitFestSach={() => {}}
      antraegeText="Manuell geaendert" onAntraegeText={() => {}} onAntraegeManuell={() => {}}
      gebuehrenText="" antraegeVeraltet antraegeAuto="Automatik Fassung"
      onNeuGenerieren={() => {}} onBehalten={() => {}} />);
    const buttons = screen.getAllByText(/Änderungen anzeigen/);
    expect(buttons.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(buttons[0]);
    expect(screen.getAllByTestId("diff-ansicht")[0].textContent).toContain("Automatik Fassung");
  });
});
