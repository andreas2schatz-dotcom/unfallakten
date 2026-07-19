import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import KlageEntwurfDialog from "./KlageEntwurfDialog.jsx";

describe("KlageEntwurfDialog", () => {
  it("fortsetzen: zeigt Datum + Schritt und beide Optionen", () => {
    const onFortsetzen = vi.fn();
    const onNeuBeginnen = vi.fn();
    render(<KlageEntwurfDialog typ="fortsetzen" gespeichertAm="2026-07-19 14:32:05"
      step={7} onFortsetzen={onFortsetzen} onNeuBeginnen={onNeuBeginnen}
      onAbbrechen={() => {}} />);
    expect(screen.getByText(/Entwurf vom 19\.07\., 14:32/)).toBeInTheDocument();
    expect(screen.getByText(/Schritt 7 von 10/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Fortsetzen/ }));
    expect(onFortsetzen).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: /Neu beginnen/ }));
    expect(onNeuBeginnen).toHaveBeenCalledTimes(1);
  });

  it("mismatch: nur 'Neu beginnen' + Hinweis auf aeltere Programmversion", () => {
    render(<KlageEntwurfDialog typ="mismatch" onFortsetzen={() => {}}
      onNeuBeginnen={() => {}} onAbbrechen={() => {}} />);
    expect(screen.getByText(/älteren Programmversion/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Fortsetzen/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Neu beginnen/ })).toBeInTheDocument();
  });

  it("abbrechen ruft onAbbrechen", () => {
    const onAbbrechen = vi.fn();
    render(<KlageEntwurfDialog typ="fortsetzen" gespeichertAm="2026-07-19 14:32:05"
      step={2} onFortsetzen={() => {}} onNeuBeginnen={() => {}}
      onAbbrechen={onAbbrechen} />);
    fireEvent.click(screen.getByRole("button", { name: /Abbrechen/ }));
    expect(onAbbrechen).toHaveBeenCalledTimes(1);
  });
});
