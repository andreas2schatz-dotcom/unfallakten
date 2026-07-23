import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TextbausteinEditor, { pruefePlatzhalter } from "./TextbausteinEditor.jsx";

const PH = [
  { key: "MANDANT", beschreibung: "Name der Mandantschaft", beispiel: "Herr Beispiel" },
  { key: "GUTACHTER", beschreibung: "Sachverständiger", beispiel: "Dipl.-Ing. Muster" },
];

describe("pruefePlatzhalter", () => {
  it("erkennt unbekannte Platzhalter", () => {
    const r = pruefePlatzhalter("Hallo <MANDANT> und <TIPPFEHLER>", ["MANDANT"]);
    expect(r.ok).toBe(false);
    expect(r.unbekannte).toEqual(["TIPPFEHLER"]);
  });
  it("ok ohne Platzhalter", () => {
    expect(pruefePlatzhalter("Nur Text", []).ok).toBe(true);
  });
});

describe("TextbausteinEditor", () => {
  it("Chip-Klick fügt Platzhalter an Cursor ein", () => {
    const onChange = vi.fn();
    render(<TextbausteinEditor wert="Sehr geehrte," onChange={onChange}
                               platzhalter={PH} />);
    fireEvent.click(screen.getByRole("button", { name: /MANDANT/ }));
    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][0]).toContain("<MANDANT>");
  });
  it("zeigt Warnung bei unbekanntem Platzhalter", () => {
    render(<TextbausteinEditor wert="Text mit <FALSCH>" onChange={() => {}}
                               platzhalter={PH} />);
    expect(screen.getByText(/Unbekannte Platzhalter/).textContent).toContain("FALSCH");
  });
  it("Reset-Button nur mit standardText", () => {
    const { rerender } = render(
      <TextbausteinEditor wert="x" onChange={() => {}} platzhalter={PH} />);
    expect(screen.queryByText(/Auf Standard/)).toBeNull();
    rerender(<TextbausteinEditor wert="x" onChange={() => {}} platzhalter={PH}
                                 standardText="Std" onReset={() => {}} />);
    expect(screen.getByText(/Auf Standard/)).toBeTruthy();
  });
});
