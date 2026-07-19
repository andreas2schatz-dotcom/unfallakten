import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EntwurfStatusLeiste, SchliessenGuardDialog, EntwurfAenderungenBox } from "./KlageWizard.jsx";

describe("EntwurfStatusLeiste", () => {
  it("zeigt Speichern-Knopf und ruft onSpeichern", () => {
    const onSpeichern = vi.fn();
    render(<EntwurfStatusLeiste dirty={true} gespeichertAm={null}
      fehler={null} laeuft={false} onSpeichern={onSpeichern} />);
    fireEvent.click(screen.getByRole("button", { name: /Entwurf speichern/ }));
    expect(onSpeichern).toHaveBeenCalledTimes(1);
  });

  it("dirty: zeigt 'Ungespeicherte Änderungen'", () => {
    render(<EntwurfStatusLeiste dirty={true} gespeichertAm={"2026-07-19 14:32:05"}
      fehler={null} laeuft={false} onSpeichern={() => {}} />);
    expect(screen.getByText(/Ungespeicherte Änderungen/)).toBeInTheDocument();
  });

  it("gespeichert: zeigt Zeitstempel", () => {
    render(<EntwurfStatusLeiste dirty={false} gespeichertAm={"2026-07-19 14:32:05"}
      fehler={null} laeuft={false} onSpeichern={() => {}} />);
    expect(screen.getByText(/Gespeichert 19\.07\., 14:32/)).toBeInTheDocument();
  });

  it("fehler hat Vorrang und Knopf ist waehrend laeuft gesperrt", () => {
    render(<EntwurfStatusLeiste dirty={true} gespeichertAm={null}
      fehler={"Entwurf konnte nicht gespeichert werden"} laeuft={true}
      onSpeichern={() => {}} />);
    expect(screen.getByText(/nicht gespeichert/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Entwurf speichern/ })).toBeDisabled();
  });
});

describe("SchliessenGuardDialog", () => {
  it("Speichern & Schließen: erst speichern, bei Erfolg schliessen", async () => {
    const onEntwurfSpeichern = vi.fn().mockResolvedValue(true);
    const onClose = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern}
      onClose={onClose} onZurueck={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(onEntwurfSpeichern).toHaveBeenCalledTimes(1);
  });

  it("Speichern schlaegt fehl: nicht schliessen, zurueck zum Wizard", async () => {
    const onEntwurfSpeichern = vi.fn().mockResolvedValue(false);
    const onClose = vi.fn();
    const onZurueck = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern}
      onClose={onClose} onZurueck={onZurueck} />);
    fireEvent.click(screen.getByRole("button", { name: /Speichern/ }));
    await waitFor(() => expect(onZurueck).toHaveBeenCalledTimes(1));
    expect(onClose).not.toHaveBeenCalled();
  });

  it("Verwerfen schliesst ohne zu speichern", () => {
    const onEntwurfSpeichern = vi.fn();
    const onClose = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={onEntwurfSpeichern}
      onClose={onClose} onZurueck={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Verwerfen/ }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onEntwurfSpeichern).not.toHaveBeenCalled();
  });

  it("Zurueck zum Wizard schliesst nur den Dialog", () => {
    const onZurueck = vi.fn();
    const onClose = vi.fn();
    render(<SchliessenGuardDialog onEntwurfSpeichern={() => {}}
      onClose={onClose} onZurueck={onZurueck} />);
    fireEvent.click(screen.getByRole("button", { name: /Zurück zum Wizard/ }));
    expect(onZurueck).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("EntwurfAenderungenBox", () => {
  it("rendert nichts bei leerer Liste", () => {
    const { container } = render(
      <EntwurfAenderungenBox aenderungen={[]} onSchliessen={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("listet Aenderungen und laesst sich schliessen", () => {
    const onSchliessen = vi.fn();
    render(<EntwurfAenderungenBox
      aenderungen={["Neue Position: Standkosten", "Betrag geändert: Reparaturkosten (1200,50 € → 900,00 €)"]}
      onSchliessen={onSchliessen} />);
    expect(screen.getByText(/Seit dem Entwurf geändert/)).toBeInTheDocument();
    expect(screen.getByText(/Neue Position: Standkosten/)).toBeInTheDocument();
    expect(screen.getByText(/1200,50 € → 900,00 €/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /✕/ }));
    expect(onSchliessen).toHaveBeenCalledTimes(1);
  });
});
