import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EntwurfStatusLeiste } from "./KlageWizard.jsx";

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
